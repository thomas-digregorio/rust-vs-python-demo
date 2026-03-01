from __future__ import annotations

import argparse
import json
import math
import os
import platform
import random
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path


def monte_carlo_pi(samples: int) -> float:
    inside = 0
    rng = random.Random(42)
    for _ in range(samples):
        x = rng.random()
        y = rng.random()
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * inside / samples


def json_parse_transform(records: int) -> int:
    payload = [{"id": i, "value": i % 17, "name": f"row-{i}"} for i in range(records)]
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    return sum(item["value"] for item in decoded)


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown00"


def make_base(benchmark_id: str, metrics: dict[str, dict[str, float | str]]) -> dict:
    return {
        "benchmark_id": benchmark_id,
        "category": "performance",
        "language": "python",
        "variant": {"runtime": "cpython", "version": platform.python_version()},
        "environment": {"os": platform.platform(), "cpu_count": os.cpu_count() or 1},
        "metrics": metrics,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "commit_sha": git_sha(),
        "run_id": str(uuid.uuid4()),
    }


def run() -> list[dict]:
    start = time.perf_counter()
    pi = monte_carlo_pi(200_000)
    elapsed = time.perf_counter() - start

    start = time.perf_counter()
    checksum = json_parse_transform(20_000)
    parse_elapsed = time.perf_counter() - start

    return [
        make_base(
            "cpu_monte_carlo_pi",
            {
                "runtime_seconds": {"value": elapsed, "unit": "s"},
                "pi_estimate": {"value": pi, "unit": "ratio"},
            },
        ),
        make_base(
            "string_json_parse_transform",
            {
                "runtime_seconds": {"value": parse_elapsed, "unit": "s"},
                "checksum": {"value": float(checksum), "unit": "count"},
            },
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
