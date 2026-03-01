import unittest

from benchmarks.python.perf.runner import json_parse_transform, monte_carlo_pi, run


class RunnerTests(unittest.TestCase):
    def test_monte_carlo_pi_bounds(self) -> None:
        estimate = monte_carlo_pi(10_000)
        self.assertGreater(estimate, 3.0)
        self.assertLess(estimate, 3.3)

    def test_json_parse_transform_checksum(self) -> None:
        checksum = json_parse_transform(100)
        self.assertEqual(checksum, sum(i % 17 for i in range(100)))

    def test_run_produces_two_records(self) -> None:
        data = run()
        self.assertEqual(len(data), 2)
        self.assertEqual(
            {d["benchmark_id"] for d in data},
            {"cpu_monte_carlo_pi", "string_json_parse_transform"},
        )


if __name__ == "__main__":
    unittest.main()
