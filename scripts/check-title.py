"""Validate a PR title or the first line of a commit message."""
import os
import re
import sys
from pathlib import Path

def valid(title):
    return len(title) <= 72 and re.fullmatch(
        r"(?:feat|fix|docs|style|refactor|perf|test|build|ci|chore|security|revert)(?:\([a-z0-9_.-]+\))?!?: [^\s].{9,}", title
    ) is not None

if __name__ == "__main__":
    title = Path(sys.argv[1]).read_text().splitlines()[0] if len(sys.argv) > 1 else os.environ.get("PR_TITLE", "")
    if not valid(title):
        raise SystemExit("Use a Conventional Commit title, <=72 characters, with a descriptive subject of at least 10 characters. Example: security(ci): enforce reviewed deployments")
