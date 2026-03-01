# Benchmark Specification (Phase 0)

This repository now contains initial executable parity benchmarks in Python and Rust:

- `cpu_monte_carlo_pi`
- `string_json_parse_transform`

Both implementations emit normalized records following `benchmarks/shared/schemas/result.schema.json`.

## Runbook

```bash
python3 benchmarks/shared/scripts/run_all.py
```

Outputs:
- raw per-language files under `results/raw`
- merged normalized file under `results/normalized/latest.json`
