"""Package the checked-out commit and wait for one bounded private CodeBuild job."""
import argparse
import json
import os
import signal
import subprocess
import time
import zipfile
from pathlib import Path

from ci_common import aws, check_budget, image_uri, load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["plan", "deploy"])
    parser.add_argument("--image")
    args = parser.parse_args()
    config = load_config()
    check_budget(config)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    request = {"commit": commit}
    if args.mode == "deploy":
        request["image"] = image_uri(config, args.image or "")
    archive = Path("runtime/ci-source.zip")
    with archive.open("wb") as stream:
        subprocess.run(["git", "archive", "--format=zip", "HEAD"], stdout=stream, check=True)
    with zipfile.ZipFile(archive, "a") as z:
        z.writestr("ci-request.json", json.dumps(request))
    run = os.environ.get("GITHUB_RUN_ID", "local")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "1")
    key = f"source/{args.mode}/{commit}-{run}-{attempt}.zip"
    uploaded = aws("s3api", "put-object", "--bucket", os.environ["CI_BUCKET"], "--key", key, "--body", str(archive))
    build = aws("codebuild", "start-build", "--project-name", os.environ["CODEBUILD_PROJECT"],
                "--source-location-override", f"{os.environ['CI_BUCKET']}/{key}",
                "--source-version", uploaded["VersionId"])["build"]
    build_id = build["id"]
    print(f"Started {build_id}", flush=True)
    # Cancellation stops AWS compute rather than leaving it running after Actions exits.
    def cancelled(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, cancelled)
    finished = False
    try:
        deadline = time.monotonic() + (900 if args.mode == "plan" else 1500)
        while time.monotonic() < deadline:
            state = aws("codebuild", "batch-get-builds", "--ids", build_id)["builds"][0]
            status = state["buildStatus"]
            print(f"{build_id}: {status} ({state.get('currentPhase', '')})", flush=True)
            if status != "IN_PROGRESS":
                finished = True
                result_key = f"results/{args.mode}/{build_id.split(':', 1)[1]}/result.json"
                result_path = Path(f"runtime/{args.mode}-result.json")
                private_path = Path("runtime/private-codebuild-result.json")
                copied = subprocess.run(["aws", "s3", "cp", f"s3://{os.environ['CI_BUCKET']}/{result_key}", str(private_path), "--only-show-errors"])
                if status != "SUCCEEDED" or copied.returncode:
                    phases = [{"phase": p["phaseType"], "status": p.get("phaseStatus"), "contexts": p.get("contexts")} for p in state.get("phases", []) if p.get("phaseStatus") in ("FAILED", "FAULT", "TIMED_OUT")]
                    print(json.dumps(phases, indent=2))
                    raise SystemExit("CodeBuild failed or result is missing; inspect the project log in AWS")
                result = json.loads(private_path.read_text())
                if args.mode == "deploy":
                    result = {"commit": result["commit"], "status": result["status"],
                              "image_digest": result["image"].split("@", 1)[1]}
                result_path.write_text(json.dumps(result, indent=2))
                if summary := os.getenv("GITHUB_STEP_SUMMARY"):
                    with open(summary, "a") as stream:
                        stream.write(f"### {args.mode.title()} result\n\n```json\n{json.dumps(result, indent=2)}\n```\n")
                        if args.mode == "plan":
                            stream.write("\nDetailed plans remain in the private CI bucket (one-day retention); no state or plan binaries are published.\n")
                return
            time.sleep(15)
        raise TimeoutError("CI wait exceeded its deadline")
    finally:
        if not finished:
            aws("codebuild", "stop-build", "--id", build_id)


if __name__ == "__main__":
    main()
