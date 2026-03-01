# Rust vs Python Demo

Initial implementation of the benchmarking program plan.

## What is implemented

- Monorepo directory layout from `IMPLEMENTATION_PLAN.md`.
- Python and Rust performance benchmark runners for two shared workloads.
- Shared JSON schema and validator.
- Cross-language orchestrator script.
- Browser dashboard UI that loads normalized results and renders a comparison table + summary cards.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r benchmarks/python/requirements.txt
python3 benchmarks/shared/scripts/run_all.py
```


## View the dashboard UI

1. Generate fresh benchmark results:

```bash
python3 benchmarks/shared/scripts/run_all.py
```

2. Serve the repository root so the dashboard can load `/results/normalized/latest.json`:

```bash
python3 -m http.server 8000
```

3. Open your browser at:

- `http://localhost:8000/web/apps/dashboard/`

## Test commands

```bash
python3 -m unittest discover -s benchmarks/python/tests -v
cargo test --manifest-path benchmarks/rust/Cargo.toml
cd web/apps/dashboard && npm install && npm test && npm run build
```
