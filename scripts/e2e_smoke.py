"""End-to-end smoke test that runs the crawler, indexes and queries."""

import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "e2e"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, **kwargs)


def main() -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{(DATA / 'e2e.sqlite').as_posix()}"
    env["PRIVATESEARCH_LOG_LEVEL"] = "WARNING"

    print("== Step 1: crawl example.com ==")
    crawl = _run(
        [
            sys.executable,
            "-m",
            "apps.crawler",
            "--seed-urls",
            "https://example.com",
            "--allowed-domains",
            "example.com",
            "--max-depth",
            "1",
            "--max-pages",
            "5",
            "--delay",
            "0.0",
            "--print-stats",
        ],
        env=env,
    )
    print(crawl.stdout)
    if crawl.returncode != 0:
        print("CRAWLER STDERR:", crawl.stderr)
        return 1

    print("== Step 2: boot the API ==")
    api_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8769",
            "--log-level",
            "warning",
        ],
        cwd=str(ROOT),
        env=env,
    )
    try:
        time.sleep(2)

        print("== Step 3: rebuild the index from storage ==")
        try:
            with urllib.request.urlopen(
                "http://127.0.0.1:8769/api/v1/index/rebuild", timeout=3
            ) as response:
                print(response.read().decode())
        except urllib.error.HTTPError as e:
            print("REBUILD HTTP", e.code, e.read().decode())

        print("== Step 4: query the API ==")
        with urllib.request.urlopen(
            "http://127.0.0.1:8769/api/v1/search?q=example",
            timeout=3,
        ) as response:
            payload = response.read().decode()
            print(payload)

        print("== Step 5: hybrid search ==")
        with urllib.request.urlopen(
            "http://127.0.0.1:8769/api/v1/search/hybrid?q=example",
            timeout=3,
        ) as response:
            payload = response.read().decode()
            print(payload)

        return 0
    finally:
        api_proc.terminate()
        try:
            api_proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            api_proc.kill()


if __name__ == "__main__":
    sys.exit(main())