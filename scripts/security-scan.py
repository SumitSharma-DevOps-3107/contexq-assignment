"""Fail closed on high/critical IaC findings; never print plan resource values."""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def summarize(report, target=None, layer=None):
    if report.get("SchemaVersion") != 2 or not isinstance(report.get("Results"), list) or not report["Results"]:
        raise ValueError("Scanner returned no configuration results")
    findings = []
    for result in report["Results"]:
        for item in result.get("Misconfigurations", []):
            if item["Severity"] in ("HIGH", "CRITICAL") and item.get("Status", "FAIL") == "FAIL":
                if target is not None:
                    from security_exception import permitted
                    if permitted(result, item, target, layer):
                        print("Temporary AWS-0104 exception used for the CI runner only; expires 2026-11-01 UTC")
                        continue
                # Deliberately omit paths, resource names, code snippets and resolved values.
                findings.append({key: item.get(key, "") for key in ("ID", "Severity", "Title", "Resolution", "PrimaryURL")})
    return list({json.dumps(item, sort_keys=True): item for item in findings}.values())

def scan(target, layer=None):
    with tempfile.TemporaryDirectory(prefix="ray-security-") as folder:
        output = Path(folder) / "report.json"
        subprocess.run([str(ROOT / ".tools/trivy"), "config", "--misconfig-scanners", "terraform" if target.is_dir() else "terraformplan-json", "--severity", "HIGH,CRITICAL", "--skip-dirs", "**/.terraform", "--format", "json", "--output", str(output), str(target)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return summarize(json.loads(output.read_text()), target, layer)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default="infra")
    args = parser.parse_args()
    findings = scan(Path(args.target).resolve())
    for item in findings:
        print(f"{item['Severity']} {item['ID']}: {item['Title']}\n  Fix: {item['Resolution']}\n  {item['PrimaryURL']}")
    if findings:
        raise SystemExit(f"Blocked by {len(findings)} distinct high/critical checks. Fix the configuration; do not bypass the gate.")
    print("IaC security scan passed")

if __name__ == "__main__":
    main()
