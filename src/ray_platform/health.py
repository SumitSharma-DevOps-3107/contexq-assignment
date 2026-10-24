"""HTTP health probe without curl/wget dependencies in the application image."""
import os
import sys
from urllib.request import Request, urlopen

headers = {}
if os.getenv("RAY_AUTH_TOKEN"):
    headers["Authorization"] = "Bearer " + os.environ["RAY_AUTH_TOKEN"]
for url in sys.argv[1:]:
    with urlopen(Request(url, headers=headers), timeout=2) as response:
        if response.status != 200:
            raise SystemExit(1)
