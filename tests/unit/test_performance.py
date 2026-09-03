"""Smoke tests for the performance benchmark script."""

from __future__ import annotations

import json
from pathlib import Path

from benchmarks.performance.measure import main as perf_main


def test_performance_main_writes_json(tmp_path: Path, capsys) -> None:
    output = tmp_path / "perf.json"
    rc = perf_main([
        "--documents",
        "100",
        "--queries",
        "20",
        "--output",
        str(output),
    ])
    assert rc == 0
    assert output.exists()
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["indexing"]["documents"] == 100.0
    assert payload["search"]["queries"] == 20.0
    # Latencies must be measured in milliseconds and stay non-negative.
    assert payload["search"]["p50_ms"] >= 0.0