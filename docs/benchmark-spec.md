# Benchmark Specification (Phase 0)

This repository contains executable parity benchmarks in Python and Rust for the full 8-test matrix:

- `cpu_monte_carlo_pi`
- `string_json_parse_transform`
- `io_concurrent_http_client`
- `data_pipeline_etl_minibatch`
- `dependency_vulnerability_scan_scorecard`
- `static_security_lint_benchmark`
- `test_robustness_reliability`
- `build_startup_feedback_loop`

Both implementations emit normalized records following `benchmarks/shared/schemas/result.schema.json`.

For full security findings, install:
- Python: `pip-audit`, `bandit`
- Rust: `cargo-audit`, `cargo-outdated`

## Runbook

```bash
python3 benchmarks/shared/scripts/run_all.py
```

Outputs:
- `results/raw/python_perf.json`
- `results/raw/rust_perf.json`
- `results/normalized/latest.json` (16 records total)
