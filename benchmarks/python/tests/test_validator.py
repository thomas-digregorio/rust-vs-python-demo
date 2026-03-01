import json
import unittest
from pathlib import Path

from benchmarks.shared.scripts.validate_results import validate


class ValidatorTests(unittest.TestCase):
    def test_validate_happy_path(self) -> None:
        schema = Path("benchmarks/shared/schemas/result.schema.json")
        sample = [
            {
                "benchmark_id": "id",
                "category": "performance",
                "language": "python",
                "variant": {"runtime": "cpython", "version": "3.12"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {"runtime_seconds": {"value": 1.0, "unit": "s"}},
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            }
        ]
        path = Path("results/raw/test_result.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample), encoding="utf-8")
        self.assertEqual(validate(path, schema), [])
        path.unlink()

    def test_validate_detects_performance_parity_mismatch(self) -> None:
        schema = Path("benchmarks/shared/schemas/result.schema.json")
        sample = [
            {
                "benchmark_id": "string_json_parse_transform",
                "category": "performance",
                "language": "python",
                "variant": {"runtime": "cpython", "version": "3.12"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 1.0, "unit": "s"},
                    "checksum": {"value": 100.0, "unit": "count"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "string_json_parse_transform",
                "category": "performance",
                "language": "rust",
                "variant": {"runtime": "rust", "version": "1.0"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 0.5, "unit": "s"},
                    "checksum": {"value": 99.0, "unit": "count"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "cpu_monte_carlo_pi",
                "category": "performance",
                "language": "python",
                "variant": {"runtime": "cpython", "version": "3.12"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 1.0, "unit": "s"},
                    "pi_estimate": {"value": 3.14, "unit": "ratio"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "cpu_monte_carlo_pi",
                "category": "performance",
                "language": "rust",
                "variant": {"runtime": "rust", "version": "1.0"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 0.5, "unit": "s"},
                    "pi_estimate": {"value": 3.14, "unit": "ratio"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "io_concurrent_http_client",
                "category": "performance",
                "language": "python",
                "variant": {"runtime": "cpython", "version": "3.12"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 1.0, "unit": "s"},
                    "requests_completed": {"value": 10.0, "unit": "count"},
                    "checksum": {"value": 20.0, "unit": "count"},
                    "request_errors": {"value": 0.0, "unit": "count"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "io_concurrent_http_client",
                "category": "performance",
                "language": "rust",
                "variant": {"runtime": "rust", "version": "1.0"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 0.5, "unit": "s"},
                    "requests_completed": {"value": 10.0, "unit": "count"},
                    "checksum": {"value": 20.0, "unit": "count"},
                    "request_errors": {"value": 0.0, "unit": "count"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "data_pipeline_etl_minibatch",
                "category": "performance",
                "language": "python",
                "variant": {"runtime": "cpython", "version": "3.12"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 1.0, "unit": "s"},
                    "records_processed": {"value": 10.0, "unit": "count"},
                    "aggregate_value": {"value": 100.0, "unit": "count"},
                    "throughput_mb_s": {"value": 10.0, "unit": "mb/s"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
            {
                "benchmark_id": "data_pipeline_etl_minibatch",
                "category": "performance",
                "language": "rust",
                "variant": {"runtime": "rust", "version": "1.0"},
                "environment": {"os": "linux", "cpu_count": 2},
                "metrics": {
                    "runtime_seconds": {"value": 0.5, "unit": "s"},
                    "records_processed": {"value": 10.0, "unit": "count"},
                    "aggregate_value": {"value": 100.0, "unit": "count"},
                    "throughput_mb_s": {"value": 20.0, "unit": "mb/s"},
                },
                "timestamp": "2026-01-01T00:00:00+00:00",
                "commit_sha": "abcdef1",
                "run_id": "run",
            },
        ]
        path = Path("results/raw/test_result_mismatch.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sample), encoding="utf-8")
        errors = validate(path, schema)
        self.assertTrue(any("string_json_parse_transform" in error for error in errors))
        path.unlink()


if __name__ == "__main__":
    unittest.main()
