from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "results" / "raw"
NORM = ROOT / "results" / "normalized"


def run_cmd(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT)


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    NORM.mkdir(parents=True, exist_ok=True)

    py_raw = RAW / "python_perf.json"
    rs_raw = RAW / "rust_perf.json"

    run_cmd(["python3", "benchmarks/python/perf/runner.py", "--output", str(py_raw)])
    run_cmd(["cargo", "run", "--manifest-path", "benchmarks/rust/Cargo.toml", "--", "--output", str(rs_raw)])

    combined = load(py_raw) + load(rs_raw)
    normalized = NORM / "latest.json"
    normalized.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    run_cmd(["python3", "benchmarks/shared/scripts/validate_results.py", str(normalized)])
    print(f"Wrote {normalized}")


if __name__ == "__main__":
    main()
