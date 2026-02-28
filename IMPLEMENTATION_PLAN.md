# Python vs Rust Benchmarking Program Plan

## 1) Goals and Success Criteria

### Primary goal
Build a reproducible benchmarking program that compares **Python vs Rust** across:
- Performance (latency, throughput, memory/CPU footprint)
- Security posture (dependency and code-level findings)
- Engineering metrics (test reliability, static analysis findings, build/runtime ergonomics)

### Success criteria
- 5–10 benchmark categories implemented with executable code in both languages.
- Identical (or as close as possible) workloads and datasets per benchmark.
- Results exported to a shared machine-readable format (JSON/CSV).
- TypeScript web app that ingests results and renders side-by-side comparisons and trends.
- CI pipeline that can run a subset on each PR and full benchmark suite on demand.

---

## 2) Recommended Benchmark Matrix (8 tests)

Use 8 tests to balance breadth and implementation effort.

## A. Performance Benchmarks (4)

1. **CPU-bound numeric workload**  
   - Example: matrix multiplication, FFT, or Monte Carlo Pi.
   - Metrics: p50/p95 runtime, CPU utilization, memory peak.

2. **String + parsing workload**  
   - Example: large JSON/CSV parse-transform-serialize.
   - Metrics: records/sec, allocation count (if available), peak RSS.

3. **I/O-bound concurrent HTTP client benchmark**  
   - Example: fetch N URLs concurrently from a local mock server.
   - Metrics: req/sec, tail latency, error rate under load.

4. **Data pipeline / ETL mini-batch**  
   - Example: read gzipped files, transform, aggregate, output.
   - Metrics: end-to-end runtime, throughput MB/s, memory peak.

## B. Security Benchmarks (2)

5. **Dependency vulnerability scan scorecard**  
   - Python: `pip-audit` + `safety` (optional).  
   - Rust: `cargo audit`.  
   - Metrics: # known vulns (by severity), mean time to patch, outdated deps.

6. **Static security lint benchmark**  
   - Python: `bandit`, optional Semgrep ruleset.  
   - Rust: `clippy` security-relevant lints + optional Semgrep Rust rules.  
   - Metrics: high/medium findings normalized per KLOC.

## C. Engineering / Quality Metrics (2)

7. **Test robustness and reliability**  
   - Run unit/integration tests repeatedly (e.g., 30 iterations) to detect flakiness.
   - Metrics: flaky test rate, total test runtime, setup overhead.

8. **Build/startup/developer feedback loop**  
   - Python: cold start script runtime + optional package install time.
   - Rust: `cargo build` cold/warm timings + binary startup time.
   - Metrics: build time, startup latency, artifact size.

> Optional extras if you want 10 tests:
> - Memory leak / long-run stability test
> - Serialization benchmark (JSON/MessagePack/Protobuf)

---

## 3) Project Structure (Monorepo)

Suggested structure:

```text
/benchmarks
  /python
    /perf
    /security
    /quality
  /rust
    /perf
    /security
    /quality
  /shared
    /datasets
    /schemas
    /scripts
/results
  /raw
  /normalized
/web
  /apps
    /dashboard   # TypeScript web app (React + Vite or Next.js)
/docs
  benchmark-spec.md
  methodology.md
```

Key principle: every benchmark has a **shared spec** and two implementations.

---

## 4) Standardized Result Schema

Define one schema early (JSON preferred):

- `benchmark_id` (string)
- `category` (`performance | security | quality`)
- `language` (`python | rust`)
- `variant` (runtime/library/toolchain metadata)
- `environment` (CPU, RAM, OS, container hash)
- `metrics` (key/value map, numeric values with unit)
- `timestamp`
- `commit_sha`
- `run_id`

Store raw tool output and normalized output:
- Raw: exact command outputs for auditing.
- Normalized: schema-conformant records consumed by the dashboard.

---

## 5) Fairness and Experimental Controls

To keep comparisons credible:

1. Pin versions:
   - Python version + dependency lock file
   - Rust toolchain + `Cargo.lock`
2. Isolate environment:
   - Prefer Docker/Dev Container with fixed CPU/memory limits.
3. Warmup strategy:
   - Exclude first run or explicitly report cold vs warm.
4. Repetitions:
   - Minimum 10 iterations for perf tests.
5. Statistical summary:
   - Report p50/p95/stdev and confidence intervals where feasible.
6. Same dataset and algorithmic intent:
   - Do not compare radically different algorithmic complexity.

---

## 6) Library/Tool Recommendations

## Python
- Perf helpers: `pytest-benchmark`, `timeit`, `pyperf`
- Concurrency/HTTP: `asyncio`, `httpx`, `aiohttp`
- Security: `pip-audit`, `bandit`
- Quality: `pytest`, `ruff`, `mypy`

## Rust
- Benchmarking: `criterion`
- Concurrency/HTTP: `tokio`, `reqwest`
- Security: `cargo-audit`
- Quality: `cargo test`, `clippy`, `rustfmt`

## Shared orchestration
- Task runner: `just` or `make`
- Data normalization: Python script or small Rust CLI
- CI: GitHub Actions matrix jobs

---

## 7) Implementation Phases

## Phase 0 (Week 1): Foundations
- Set up monorepo layout and lockfiles.
- Write benchmark spec template.
- Implement results schema and a validator.
- Add CI skeleton and lint/test jobs.

## Phase 1 (Weeks 2–3): Core performance benchmarks
- Implement 4 performance tests in both languages.
- Add runner scripts and result normalization.
- Validate reproducibility on at least 2 machines/runners.

## Phase 2 (Week 4): Security and quality metrics
- Add security scans and static checks.
- Add reliability/build-loop metrics.
- Normalize all outputs into shared schema.

## Phase 3 (Weeks 5–6): TypeScript dashboard
- Build dashboard MVP with filters and benchmark drill-down.
- Add comparative charts and trend lines by commit/time.
- Add export (CSV/JSON snapshot).

## Phase 4 (Week 7): Hardening and publication
- Add methodology docs and caveats.
- Add automated scheduled full benchmark run.
- Freeze v1 benchmark suite and baseline report.

---

## 8) TypeScript Web App Plan

### Stack recommendation
- **React + Vite + TypeScript** for fast iteration.
- Charting: `ECharts` or `Recharts`.
- Table: `TanStack Table`.
- Styling: Tailwind or minimal CSS modules.

### Core pages
1. **Overview Dashboard**
   - Winner counts by category
   - Aggregate normalized scorecards
2. **Benchmark Detail**
   - Per-test charts (runtime, memory, findings)
   - Raw-output links and run metadata
3. **Trends**
   - Metric evolution by commit/date
4. **Methodology**
   - Fairness rules, environment settings, caveats

### Data flow
- Web app loads normalized JSON from `/results/normalized` (or API later).
- Optionally generate pre-computed summary files during CI for faster UI.

---

## 9) CI/CD Strategy

- PR pipeline:
  - Lint + unit tests for Python/Rust/web
  - Run lightweight benchmark subset (quick sanity only)
- Scheduled pipeline (nightly/weekly):
  - Full benchmark matrix
  - Publish normalized results artifacts
  - Deploy dashboard with latest results

Use tags/labels to trigger full runs manually when needed.

---

## 10) Risks and Mitigations

- **Risk:** Apples-to-oranges implementations.  
  **Mitigation:** Shared benchmark specs + code review checklist.

- **Risk:** Noisy measurements in shared CI runners.  
  **Mitigation:** Repetitions, pinned resources, nightly dedicated runner if possible.

- **Risk:** Security tools produce incomparable finding semantics.  
  **Mitigation:** Normalize severities and report tool-specific caveats.

- **Risk:** Overfitting to microbenchmarks.  
  **Mitigation:** Include mixed real-world ETL + IO benchmarks.

---

## 11) Concrete Next Steps (Start Here)

1. Create the repo scaffolding and benchmark spec templates.
2. Implement one end-to-end benchmark pair (CPU numeric) with normalized output.
3. Stand up a minimal TypeScript dashboard that renders this single benchmark.
4. Add 2nd and 3rd benchmarks (string parse + IO concurrency).
5. Add security scan ingestion and scorecard view.
6. Expand to full 8-test matrix.

This sequence gives early visible value while steadily building toward a robust comparison platform.
