from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

REQUIRED_TOP = {
    "benchmark_id",
    "category",
    "language",
    "variant",
    "environment",
    "metrics",
    "timestamp",
    "commit_sha",
    "run_id",
}


def validate(results_path: Path, _schema_path: Path | None = None) -> list[str]:
    results = json.loads(results_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    for idx, item in enumerate(results):
        missing = REQUIRED_TOP - set(item)
        if missing:
            errors.append(f"[{idx}] missing keys: {sorted(missing)}")
            continue
        if item["category"] not in {"performance", "security", "quality"}:
            errors.append(f"[{idx}] invalid category")
        if item["language"] not in {"python", "rust"}:
            errors.append(f"[{idx}] invalid language")
        if not isinstance(item["metrics"], dict) or not item["metrics"]:
            errors.append(f"[{idx}] metrics must be a non-empty object")
        else:
            for name, metric in item["metrics"].items():
                if not isinstance(metric, dict) or "value" not in metric or "unit" not in metric:
                    errors.append(f"[{idx}] metric {name} malformed")
        try:
            datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
        except Exception:
            errors.append(f"[{idx}] timestamp must be ISO-8601")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("results")
    parser.add_argument("--schema", default="benchmarks/shared/schemas/result.schema.json")
    args = parser.parse_args()

    errors = validate(Path(args.results), Path(args.schema))
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    print(f"Validated {args.results}")


if __name__ == "__main__":
    main()
