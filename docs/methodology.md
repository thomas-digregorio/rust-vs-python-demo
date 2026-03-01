# Methodology

## Fairness controls in current implementation

- Fixed random seed for Monte Carlo in both languages.
- Same sample counts and record counts for each benchmark ID in both languages.
- Shared mock HTTP service started once by the orchestrator and reused by both runners.
- Shared gzipped ETL dataset generated once by the orchestrator and reused by both runners.
- JSON parse/transform benchmark now performs actual serialize + parse + transform in both languages.
- Monte Carlo benchmark now uses the same xorshift RNG logic in both languages.
- HTTP client benchmark now uses equivalent raw TCP HTTP request loops in both languages.
- Security benchmark parsers now handle multiple tool JSON shapes and track parser/exit-code diagnostics.
- Shared schema validation for merged output, including cross-language performance parity checks for deterministic metrics.

## Next steps

- Add repeated runs and p50/p95 summaries.
- Capture memory and CPU telemetry per benchmark run.
