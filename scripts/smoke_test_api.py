"""Boot the API, seed an index, and exercise the search endpoint."""

import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = ROOT / "data" / "smoke"


def main() -> int:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{(TMP_DIR / 'smoke.sqlite').as_posix()}"
    env["PRIVATESEARCH_LOG_LEVEL"] = "WARNING"
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "apps.api.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8768",
        "--log-level",
        "warning",
    ]
    proc = subprocess.Popen(cmd, cwd=str(ROOT), env=env)
    try:
        time.sleep(2)

        # 1. Health
        with urllib.request.urlopen("http://127.0.0.1:8768/api/v1/health", timeout=2) as response:
            print("HEALTH", response.status, response.read().decode())

        # 2. Search (empty index)
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8768/api/v1/search?q=hello", timeout=2
            ) as response:
                print("SEARCH", response.status, response.read().decode())
        except urllib.error.HTTPError as e:
            print("SEARCH HTTP", e.code, e.read().decode())

        # 3. Invalid query
        try:
            urllib.request.urlopen("http://127.0.0.1:8768/api/v1/search?q=", timeout=2)
            print("EMPTY QUERY unexpectedly succeeded")
            return 1
        except urllib.error.HTTPError as e:
            print("EMPTY QUERY HTTP", e.code)

        # 4. Suggestions
        with urllib.request.urlopen(
            "http://127.0.0.1:8768/api/v1/suggestions?q=mac", timeout=2
        ) as response:
            print("SUGGESTIONS", response.status, response.read().decode())

        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())