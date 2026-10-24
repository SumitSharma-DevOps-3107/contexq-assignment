"""Failed private builds must never publish their raw deployment diagnostics."""
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("status", ["FAILED", "SUCCEEDED"])
def test_deployment_artifact_contains_only_public_fields(monkeypatch, tmp_path, status):
    scripts = Path(__file__).parents[1] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location("ci_trigger", scripts / "ci-trigger.py")
    trigger = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trigger)
    monkeypatch.chdir(tmp_path)
    Path("runtime").mkdir()
    monkeypatch.setenv("CI_BUCKET", "private-ci")
    monkeypatch.setenv("CODEBUILD_PROJECT", "deploy")
    monkeypatch.setattr(sys, "argv", ["ci-trigger.py", "deploy", "--image", "image@sha256:digest"])
    monkeypatch.setattr(trigger, "load_config", lambda: {})
    monkeypatch.setattr(trigger, "check_budget", lambda config: None)
    monkeypatch.setattr(trigger, "image_uri", lambda config, image: image)
    monkeypatch.setattr(trigger.signal, "signal", lambda *args: None)
    monkeypatch.setattr(trigger.subprocess, "check_output", lambda *args, **kwargs: "commit\n")
    def aws(service, operation, *args):
        return {"put-object": {"VersionId": "1"}, "start-build": {"build": {"id": "deploy:uuid"}},
                "batch-get-builds": {"builds": [{"buildStatus": status}]}}[operation]
    monkeypatch.setattr(trigger, "aws", aws)
    def run(args, **kwargs):
        if args[0] == "git":
            with zipfile.ZipFile(kwargs["stdout"], "w"):
                pass
        else:
            Path(args[4]).write_text(json.dumps({"commit": "commit", "image": "image@sha256:digest",
                "status": status, "private_metadata": "must remain private"}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(trigger.subprocess, "run", run)
    if status == "FAILED":
        with pytest.raises(SystemExit):
            trigger.main()
        assert not Path("runtime/deploy-result.json").exists()
    else:
        trigger.main()
        assert json.loads(Path("runtime/deploy-result.json").read_text()) == {
            "commit": "commit", "image_digest": "sha256:digest", "status": status}
