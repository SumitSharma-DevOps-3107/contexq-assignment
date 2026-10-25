"""Install reviewed, checksum-pinned scanner binaries; no root privileges."""
import hashlib
import io
import json
import platform
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    arch = platform.machine().lower()
    arch = {"aarch64": "arm64", "amd64": "x86_64"}.get(arch, arch)
    key = f"{platform.system()}-{arch}"
    tools = ROOT / ".tools"
    tools.mkdir(exist_ok=True)
    for name, spec in json.loads((ROOT / "security/tools.lock.json").read_text()).items():
        target = spec["platforms"][key]
        url = f"https://github.com/{spec['repository']}/releases/download/v{spec['version']}/{target['asset']}"
        with urllib.request.urlopen(url, timeout=120) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != target["sha256"]:
            raise ValueError(f"{name}: checksum mismatch")
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            binary = archive.extractfile(name)
            if binary is None:
                raise ValueError(f"{name}: binary missing")
            (tools / name).write_bytes(binary.read())
        (tools / name).chmod(0o755)
        print(f"Installed {name} {spec['version']}")

if __name__ == "__main__":
    main()
