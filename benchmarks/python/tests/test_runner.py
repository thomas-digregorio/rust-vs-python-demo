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

    def test_run_produces_full_matrix(self) -> None:
        data = run()
        self.assertEqual(len(data), 8)
        self.assertEqual(
            {d["benchmark_id"] for d in data},
            {
                "cpu_monte_carlo_pi",
                "string_json_parse_transform",
                "io_concurrent_http_client",
                "data_pipeline_etl_minibatch",
                "dependency_vulnerability_scan_scorecard",
                "static_security_lint_benchmark",
                "test_robustness_reliability",
                "build_startup_feedback_loop",
            },
        )


if __name__ == "__main__":
    unittest.main()
