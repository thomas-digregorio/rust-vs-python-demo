from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import json
import os
import platform
import socket
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def monte_carlo_pi(samples: int) -> float:
    inside = 0
    state = 42
    for _ in range(samples):
        state, x = next_f64(state)
        state, y = next_f64(state)
        if x * x + y * y <= 1.0:
            inside += 1
    return 4.0 * inside / samples


def next_f64(state: int) -> tuple[int, float]:
    state ^= (state << 13) & 0xFFFFFFFFFFFFFFFF
    state ^= state >> 7
    state ^= (state << 17) & 0xFFFFFFFFFFFFFFFF
    state &= 0xFFFFFFFFFFFFFFFF
    return state, state / float(0xFFFFFFFFFFFFFFFF)


def json_parse_transform(records: int) -> int:
    payload = [{"id": i, "value": i % 17, "name": f"row-{i}"} for i in range(records)]
    encoded = json.dumps(payload)
    decoded = json.loads(encoded)
    return sum(item["value"] for item in decoded)


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], text=True, cwd=ROOT).strip()
    except Exception:
        return "unknown00"


def metric(value: float, unit: str) -> dict[str, float | str]:
    return {"value": float(value), "unit": unit}


def make_base(
    benchmark_id: str,
    category: str,
    metrics: dict[str, dict[str, float | str]],
    run_id: str,
) -> dict:
    return {
        "benchmark_id": benchmark_id,
        "category": category,
        "language": "python",
        "variant": {"runtime": "cpython", "version": platform.python_version()},
        "environment": {"os": platform.platform(), "cpu_count": os.cpu_count() or 1},
        "metrics": metrics,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "commit_sha": git_sha(),
        "run_id": run_id,
    }


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


def resolve_dataset_path() -> Path:
    raw = os.environ.get("BENCHMARK_ETL_DATASET", "benchmarks/shared/datasets/etl_input.jsonl.gz")
    path = Path(raw)
    if path.is_absolute():
        return path
    return ROOT / path


def parse_base_url(base_url: str) -> tuple[str, int]:
    if not base_url.startswith("http://"):
        raise ValueError("Only http:// base URLs are supported")
    host_port = base_url.removeprefix("http://").split("/", 1)[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
        return host, int(port)
    return host_port, 80


def http_fetch_value(host: str, port: int, item_id: int) -> int:
    with socket.create_connection((host, port), timeout=10) as conn:
        request = f"GET /item/{item_id} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
        conn.sendall(request.encode("utf-8"))
        chunks: list[bytes] = []
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    raw = b"".join(chunks)
    if b"\r\n\r\n" not in raw:
        raise ValueError("Invalid HTTP response")
    body = raw.split(b"\r\n\r\n", 1)[1]
    payload = json.loads(body.decode("utf-8"))
    return int(payload["value"])


def fetch_chunk(host: str, port: int, start: int, end: int, rows: int) -> tuple[int, int]:
    completed = 0
    checksum = 0
    for request_id in range(start, end):
        try:
            value = http_fetch_value(host, port, request_id % max(1, rows))
        except Exception:
            continue
        completed += 1
        checksum += value
    return completed, checksum


def io_http_benchmark(base_url: str, requests: int, rows: int, concurrency: int) -> tuple[int, int]:
    host, port = parse_base_url(base_url)
    workers = max(1, concurrency)
    chunk_size = (requests + workers - 1) // workers
    checksum = 0
    completed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futures: list[concurrent.futures.Future[tuple[int, int]]] = []
        for worker_id in range(workers):
            start = worker_id * chunk_size
            end = min(start + chunk_size, requests)
            if start >= end:
                continue
            futures.append(pool.submit(fetch_chunk, host, port, start, end, rows))
        for future in concurrent.futures.as_completed(futures):
            try:
                done, partial_checksum = future.result()
                completed += done
                checksum += partial_checksum
            except Exception:
                continue
    return completed, checksum


def etl_benchmark(dataset_path: Path) -> tuple[int, int, int]:
    if not dataset_path.exists():
        dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with gzip.open(dataset_path, "wt", encoding="utf-8") as handle:
            for idx in range(20_000):
                record = {
                    "id": idx,
                    "group": idx % 50,
                    "value": (idx * 7 + 11) % 10_000,
                    "score": (idx * 13 + 17) % 10_000,
                }
                handle.write(json.dumps(record, separators=(",", ":")) + "\n")

    rows = 0
    aggregate = 0
    with gzip.open(dataset_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            transformed = (int(row["value"]) * 3 + int(row["group"])) % 1000
            aggregate += transformed
            rows += 1
    return rows, aggregate, dataset_path.stat().st_size


def run_capture(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    return proc.returncode, proc.stdout, proc.stderr


def safe_json_load(payload: str) -> object | None:
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return None


def count_pip_audit_vulns(payload: object) -> int:
    dependencies: list[object] = []
    if isinstance(payload, list):
        dependencies = payload
    elif isinstance(payload, dict):
        for key in ("dependencies", "packages"):
            value = payload.get(key)
            if isinstance(value, list):
                dependencies = value
                break

    count = 0
    for dep in dependencies:
        if not isinstance(dep, dict):
            continue
        vulns = dep.get("vulns")
        if not isinstance(vulns, list):
            vulns = dep.get("vulnerabilities")
        if isinstance(vulns, list):
            count += len(vulns)

    if count:
        return count

    if isinstance(payload, dict):
        for key in ("vulnerabilities", "advisories"):
            section = payload.get(key)
            if isinstance(section, list):
                count += len(section)
            elif isinstance(section, dict):
                if isinstance(section.get("list"), list):
                    count += len(section["list"])
                elif isinstance(section.get("items"), list):
                    count += len(section["items"])
                elif isinstance(section.get("count"), (int, float)):
                    count += int(section["count"])
                elif isinstance(section.get("found_count"), (int, float)):
                    count += int(section["found_count"])

    return count


def count_outdated_dependencies(payload: object) -> int:
    if isinstance(payload, list):
        return len(payload)
    if not isinstance(payload, dict):
        return 0

    for key in ("outdated", "dependencies", "packages", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return len(value)

    if payload and all(isinstance(value, dict) for value in payload.values()):
        return len(payload)
    return 0


def parse_bandit_counts(payload: object) -> tuple[float, float, float, float]:
    if not isinstance(payload, dict):
        return 0.0, 0.0, 0.0, 1.0

    high = 0.0
    medium = 0.0
    low = 0.0
    parse_errors = 0.0

    results = payload.get("results")
    if isinstance(results, list):
        for finding in results:
            if not isinstance(finding, dict):
                continue
            severity = str(finding.get("issue_severity", "")).upper()
            if severity == "HIGH":
                high += 1.0
            elif severity == "MEDIUM":
                medium += 1.0
            elif severity == "LOW":
                low += 1.0
    else:
        parse_errors += 1.0

    totals_obj = payload.get("metrics")
    if isinstance(totals_obj, dict):
        totals = totals_obj.get("_totals", totals_obj)
        if isinstance(totals, dict):
            if high == 0.0:
                high = float(totals.get("SEVERITY.HIGH", totals.get("HIGH", 0)) or 0)
            if medium == 0.0:
                medium = float(totals.get("SEVERITY.MEDIUM", totals.get("MEDIUM", 0)) or 0)
            if low == 0.0:
                low = float(totals.get("SEVERITY.LOW", totals.get("LOW", 0)) or 0)

    errors = payload.get("errors")
    if isinstance(errors, list):
        parse_errors += float(len(errors))

    return high, medium, low, parse_errors


def dependency_scan_metrics() -> dict[str, dict[str, float | str]]:
    start = time.perf_counter()
    tool_available = 1.0 if shutil.which("pip-audit") else 0.0
    vulnerability_count = 0.0
    audit_exit_code = -1.0
    outdated_exit_code = -1.0
    scan_errors = 0.0

    if tool_available:
        code, out, _err = run_capture(["pip-audit", "--format", "json"])
        audit_exit_code = float(code)
        parsed = safe_json_load(out or "[]")
        if parsed is None:
            scan_errors += 1.0
        else:
            vulnerability_count = float(count_pip_audit_vulns(parsed))
        if code not in {0, 1, 2}:
            scan_errors += 1.0
    else:
        scan_errors += 1.0

    outdated_dependencies = 0.0
    code, out, _err = run_capture([sys.executable, "-m", "pip", "list", "--outdated", "--format", "json"])
    outdated_exit_code = float(code)
    if code == 0:
        parsed = safe_json_load(out or "[]")
        if parsed is None:
            scan_errors += 1.0
        else:
            outdated_dependencies = float(count_outdated_dependencies(parsed))
    else:
        scan_errors += 1.0

    elapsed = time.perf_counter() - start
    return {
        "runtime_seconds": metric(elapsed, "s"),
        "vulnerability_findings": metric(vulnerability_count, "count"),
        "outdated_dependencies": metric(outdated_dependencies, "count"),
        "audit_exit_code": metric(audit_exit_code, "code"),
        "outdated_exit_code": metric(outdated_exit_code, "code"),
        "tool_available": metric(tool_available, "flag"),
        "scan_errors": metric(scan_errors, "count"),
    }


def static_security_lint_metrics() -> dict[str, dict[str, float | str]]:
    start = time.perf_counter()
    tool_available = 1.0 if shutil.which("bandit") else 0.0
    high = 0.0
    medium = 0.0
    low = 0.0
    lint_exit_code = -1.0
    scan_errors = 0.0

    if tool_available:
        code, out, _err = run_capture(["bandit", "-r", "benchmarks/python", "-f", "json", "-q"])
        lint_exit_code = float(code)
        parsed = safe_json_load(out or "{}")
        if parsed is None:
            scan_errors += 1.0
        else:
            high, medium, low, parse_errors = parse_bandit_counts(parsed)
            scan_errors += parse_errors
        if code not in {0, 1}:
            scan_errors += 1.0
    else:
        scan_errors += 1.0

    elapsed = time.perf_counter() - start
    total = high + medium + low
    return {
        "runtime_seconds": metric(elapsed, "s"),
        "finding_count": metric(total, "count"),
        "high_findings": metric(high, "count"),
        "medium_findings": metric(medium, "count"),
        "low_findings": metric(low, "count"),
        "lint_exit_code": metric(lint_exit_code, "code"),
        "tool_available": metric(tool_available, "flag"),
        "scan_errors": metric(scan_errors, "count"),
    }


def test_reliability_metrics(iterations: int) -> dict[str, dict[str, float | str]]:
    start = time.perf_counter()
    failures = 0.0
    test_targets = [
        "benchmarks.python.tests.test_runner.RunnerTests.test_monte_carlo_pi_bounds",
        "benchmarks.python.tests.test_runner.RunnerTests.test_json_parse_transform_checksum",
        "benchmarks.python.tests.test_validator.ValidatorTests",
    ]
    for _ in range(iterations):
        code, _out, _err = run_capture([sys.executable, "-m", "unittest", *test_targets])
        if code != 0:
            failures += 1.0
    elapsed = time.perf_counter() - start
    flaky_rate = failures / float(iterations)
    return {
        "runtime_seconds": metric(elapsed, "s"),
        "iterations": metric(float(iterations), "count"),
        "failed_iterations": metric(failures, "count"),
        "flaky_rate": metric(flaky_rate, "ratio"),
    }


def build_startup_metrics() -> dict[str, dict[str, float | str]]:
    total_start = time.perf_counter()

    build_start = time.perf_counter()
    build_code, _out, _err = run_capture([sys.executable, "-m", "compileall", "-q", "benchmarks/python"])
    build_elapsed = time.perf_counter() - build_start

    startup_start = time.perf_counter()
    startup_code, _out, _err = run_capture([sys.executable, "-c", "pass"])
    startup_elapsed = time.perf_counter() - startup_start

    artifact_size = 0
    for file in (ROOT / "benchmarks" / "python").rglob("*.pyc"):
        artifact_size += file.stat().st_size

    total_elapsed = time.perf_counter() - total_start
    return {
        "runtime_seconds": metric(total_elapsed, "s"),
        "build_seconds": metric(build_elapsed, "s"),
        "startup_seconds": metric(startup_elapsed, "s"),
        "artifact_size_kb": metric(artifact_size / 1024.0, "kb"),
        "operation_errors": metric(float((build_code != 0) + (startup_code != 0)), "count"),
    }


def run() -> list[dict]:
    run_id = str(uuid.uuid4())
    base_url = os.environ.get("BENCHMARK_HTTP_BASE_URL", "http://127.0.0.1:8000")
    requests = env_int("BENCHMARK_HTTP_REQUESTS", 400)
    concurrency = env_int("BENCHMARK_HTTP_CONCURRENCY", 16)
    rows = env_int("BENCHMARK_HTTP_ROWS", 1000)
    dataset = resolve_dataset_path()
    iterations = max(1, env_int("BENCHMARK_TEST_REPEAT", 3))

    start = time.perf_counter()
    pi = monte_carlo_pi(200_000)
    elapsed = time.perf_counter() - start

    start = time.perf_counter()
    checksum = json_parse_transform(20_000)
    parse_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    completed, http_checksum = io_http_benchmark(base_url, requests, rows, concurrency)
    http_elapsed = time.perf_counter() - start

    start = time.perf_counter()
    etl_rows, etl_aggregate, etl_bytes = etl_benchmark(dataset)
    etl_elapsed = time.perf_counter() - start
    etl_mb = etl_bytes / (1024.0 * 1024.0)

    return [
        make_base(
            "cpu_monte_carlo_pi",
            "performance",
            {
                "runtime_seconds": metric(elapsed, "s"),
                "pi_estimate": metric(pi, "ratio"),
            },
            run_id,
        ),
        make_base(
            "string_json_parse_transform",
            "performance",
            {
                "runtime_seconds": metric(parse_elapsed, "s"),
                "checksum": metric(float(checksum), "count"),
            },
            run_id,
        ),
        make_base(
            "io_concurrent_http_client",
            "performance",
            {
                "runtime_seconds": metric(http_elapsed, "s"),
                "requests_completed": metric(float(completed), "count"),
                "checksum": metric(float(http_checksum), "count"),
                "request_errors": metric(float(max(0, requests - completed)), "count"),
            },
            run_id,
        ),
        make_base(
            "data_pipeline_etl_minibatch",
            "performance",
            {
                "runtime_seconds": metric(etl_elapsed, "s"),
                "records_processed": metric(float(etl_rows), "count"),
                "aggregate_value": metric(float(etl_aggregate), "count"),
                "throughput_mb_s": metric(etl_mb / etl_elapsed if etl_elapsed > 0 else 0.0, "mb/s"),
            },
            run_id,
        ),
        make_base(
            "dependency_vulnerability_scan_scorecard",
            "security",
            dependency_scan_metrics(),
            run_id,
        ),
        make_base(
            "static_security_lint_benchmark",
            "security",
            static_security_lint_metrics(),
            run_id,
        ),
        make_base(
            "test_robustness_reliability",
            "quality",
            test_reliability_metrics(iterations),
            run_id,
        ),
        make_base(
            "build_startup_feedback_loop",
            "quality",
            build_startup_metrics(),
            run_id,
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run(), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
