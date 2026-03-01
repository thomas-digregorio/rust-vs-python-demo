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


if __name__ == "__main__":
    unittest.main()
