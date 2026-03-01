from __future__ import annotations

import argparse
import json
from collections import defaultdict
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

PERFORMANCE_PARITY: dict[str, dict[str, float]] = {
    "cpu_monte_carlo_pi": {"pi_estimate": 1e-9},
    "string_json_parse_transform": {"checksum": 0.0},
    "io_concurrent_http_client": {"requests_completed": 0.0, "checksum": 0.0, "request_errors": 0.0},
    "data_pipeline_etl_minibatch": {"records_processed": 0.0, "aggregate_value": 0.0},
}


def metric_value(item: dict, name: str) -> float | None:
    metric = item.get("metrics", {}).get(name)
    if not isinstance(metric, dict) or "value" not in metric:
        return None
    try:
        return float(metric["value"])
    except (TypeError, ValueError):
        return None


def validate_performance_parity(results: list[dict]) -> list[str]:
    errors: list[str] = []
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))

    for item in results:
        if item.get("category") != "performance":
            continue
        benchmark_id = item.get("benchmark_id")
        language = item.get("language")
        if isinstance(benchmark_id, str) and isinstance(language, str):
            grouped[benchmark_id][language].append(item)

    for benchmark_id, checks in PERFORMANCE_PARITY.items():
        by_language = grouped.get(benchmark_id, {})
        python_rows = by_language.get("python", [])
        rust_rows = by_language.get("rust", [])
        if not python_rows and not rust_rows:
            continue
        if len(python_rows) != 1 or len(rust_rows) != 1:
            errors.append(
                f"[{benchmark_id}] expected exactly one python and one rust performance record, "
                f"found python={len(python_rows)} rust={len(rust_rows)}"
            )
            continue

        py = python_rows[0]
        rs = rust_rows[0]
        for metric_name, tolerance in checks.items():
            py_value = metric_value(py, metric_name)
            rs_value = metric_value(rs, metric_name)
            if py_value is None or rs_value is None:
                errors.append(f"[{benchmark_id}] metric {metric_name} missing in python or rust record")
                continue

            if tolerance == 0.0:
                if py_value != rs_value:
                    errors.append(
                        f"[{benchmark_id}] metric {metric_name} mismatch python={py_value} rust={rs_value}"
                    )
            elif abs(py_value - rs_value) > tolerance:
                errors.append(
                    f"[{benchmark_id}] metric {metric_name} differs more than tolerance {tolerance}: "
                    f"python={py_value} rust={rs_value}"
                )

    return errors


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
    errors.extend(validate_performance_parity(results))
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
