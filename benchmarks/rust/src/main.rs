use chrono::Utc;
use flate2::read::GzDecoder;
use flate2::write::GzEncoder;
use flate2::Compression;
use serde::{Deserialize, Serialize};
use serde_json::{json, Map, Value};
use std::cmp::min;
use std::env;
use std::fs::{self, File};
use std::io::{BufRead, BufReader, Read, Write};
use std::net::TcpStream;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::thread;
use std::time::Instant;

#[derive(Deserialize, Serialize)]
struct JsonRow {
    id: usize,
    value: u64,
    name: String,
}

#[derive(Deserialize)]
struct EtlRow {
    group: u64,
    value: u64,
}

fn repo_root() -> PathBuf {
    env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

fn env_usize(name: &str, default: usize) -> usize {
    env::var(name)
        .ok()
        .and_then(|v| v.parse::<usize>().ok())
        .unwrap_or(default)
}

fn metric(value: f64, unit: &str) -> Value {
    json!({"value": value, "unit": unit})
}

fn next_f64(state: &mut u64) -> f64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    (*state as f64) / (u64::MAX as f64)
}

fn monte_carlo_pi(samples: usize) -> f64 {
    let mut inside = 0usize;
    let mut state: u64 = 42;
    for _ in 0..samples {
        let x = next_f64(&mut state);
        let y = next_f64(&mut state);
        if x * x + y * y <= 1.0 {
            inside += 1;
        }
    }
    4.0 * inside as f64 / samples as f64
}

fn json_parse_transform(records: usize) -> u64 {
    let payload: Vec<JsonRow> = (0..records)
        .map(|i| JsonRow {
            id: i,
            value: (i % 17) as u64,
            name: format!("row-{i}"),
        })
        .collect();
    let encoded = serde_json::to_string(&payload).unwrap_or_else(|_| "[]".to_string());
    let decoded: Vec<JsonRow> = serde_json::from_str(&encoded).unwrap_or_default();
    decoded.iter().map(|row| row.value).sum()
}

fn git_sha() -> String {
    Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .current_dir(repo_root())
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown00".to_string())
}

fn rust_runtime_version() -> String {
    Command::new("rustc")
        .arg("--version")
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| env!("CARGO_PKG_VERSION").to_string())
}

fn make_record(benchmark_id: &str, category: &str, metrics: Map<String, Value>, run_id: &str) -> Value {
    json!({
        "benchmark_id": benchmark_id,
        "category": category,
        "language": "rust",
        "variant": {
            "runtime": "rust",
            "version": rust_runtime_version(),
        },
        "environment": {
            "os": env::consts::OS,
            "cpu_count": thread::available_parallelism().map(|x| x.get()).unwrap_or(1),
        },
        "metrics": metrics,
        "timestamp": Utc::now().to_rfc3339(),
        "commit_sha": git_sha(),
        "run_id": run_id,
    })
}

fn parse_base_url(base_url: &str) -> Option<(String, u16)> {
    let trimmed = base_url.strip_prefix("http://")?;
    let host_port = trimmed.split('/').next()?;
    if let Some((host, port)) = host_port.rsplit_once(':') {
        return Some((host.to_string(), port.parse::<u16>().ok()?));
    }
    Some((host_port.to_string(), 80))
}

fn http_get_value(host: &str, port: u16, item_id: usize) -> Result<u64, String> {
    let mut stream = TcpStream::connect((host, port)).map_err(|e| e.to_string())?;
    let request = format!(
        "GET /item/{item_id} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|e| e.to_string())?;

    let mut raw = Vec::new();
    stream.read_to_end(&mut raw).map_err(|e| e.to_string())?;
    let body_offset = raw
        .windows(4)
        .position(|window| window == b"\r\n\r\n")
        .map(|idx| idx + 4)
        .ok_or_else(|| "response body missing".to_string())?;
    let body = &raw[body_offset..];
    let payload: Value = serde_json::from_slice(body).map_err(|e| e.to_string())?;
    payload["value"]
        .as_u64()
        .ok_or_else(|| "missing value".to_string())
}

fn io_http_benchmark(base_url: &str, requests: usize, rows: usize, concurrency: usize) -> (usize, u64, usize) {
    let Some((host, port)) = parse_base_url(base_url) else {
        return (0, 0, 1);
    };

    let workers = concurrency.max(1);
    let chunk = (requests + workers - 1) / workers;
    let mut handles = Vec::new();

    for worker in 0..workers {
        let start = worker * chunk;
        let end = min(start + chunk, requests);
        if start >= end {
            continue;
        }
        let host = host.clone();
        handles.push(thread::spawn(move || {
            let mut completed = 0usize;
            let mut checksum = 0u64;
            let mut errors = 0usize;
            for request_id in start..end {
                match http_get_value(&host, port, request_id % rows.max(1)) {
                    Ok(value) => {
                        completed += 1;
                        checksum += value;
                    }
                    Err(_) => {
                        errors += 1;
                    }
                }
            }
            (completed, checksum, errors)
        }));
    }

    let mut completed = 0usize;
    let mut checksum = 0u64;
    let mut errors = 0usize;
    for handle in handles {
        if let Ok((c, s, e)) = handle.join() {
            completed += c;
            checksum += s;
            errors += e;
        } else {
            errors += 1;
        }
    }
    (completed, checksum, errors)
}

fn resolve_dataset() -> PathBuf {
    let raw = env::var("BENCHMARK_ETL_DATASET")
        .unwrap_or_else(|_| "benchmarks/shared/datasets/etl_input.jsonl.gz".to_string());
    let path = PathBuf::from(raw);
    if path.is_absolute() {
        path
    } else {
        repo_root().join(path)
    }
}

fn build_etl_dataset(path: &Path, rows: usize) {
    if path.exists() {
        return;
    }
    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    let Ok(file) = File::create(path) else {
        return;
    };
    let mut encoder = GzEncoder::new(file, Compression::default());
    for idx in 0..rows {
        let record = json!({
            "id": idx,
            "group": idx % 50,
            "value": (idx * 7 + 11) % 10_000,
            "score": (idx * 13 + 17) % 10_000
        });
        let _ = writeln!(encoder, "{record}");
    }
    let _ = encoder.finish();
}

fn etl_benchmark(path: &Path) -> (usize, u64, u64) {
    build_etl_dataset(path, 20_000);
    let size_bytes = fs::metadata(path).map(|m| m.len()).unwrap_or(0);
    let file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return (0, 0, size_bytes),
    };

    let decoder = GzDecoder::new(file);
    let reader = BufReader::new(decoder);
    let mut rows = 0usize;
    let mut aggregate = 0u64;

    for line in reader.lines().map_while(Result::ok) {
        if let Ok(row) = serde_json::from_str::<EtlRow>(&line) {
            aggregate += (row.value * 3 + row.group) % 1000;
            rows += 1;
        }
    }

    (rows, aggregate, size_bytes)
}

fn command_output(mut cmd: Command) -> (i32, String, String) {
    match cmd.output() {
        Ok(output) => {
            let code = output.status.code().unwrap_or(1);
            let stdout = String::from_utf8_lossy(&output.stdout).to_string();
            let stderr = String::from_utf8_lossy(&output.stderr).to_string();
            (code, stdout, stderr)
        }
        Err(err) => (1, String::new(), err.to_string()),
    }
}

fn has_cargo_subcommand(name: &str) -> bool {
    let mut cmd = Command::new("cargo");
    cmd.args([name, "--version"]).current_dir(repo_root());
    let (code, _, _) = command_output(cmd);
    code == 0
}

fn count_from_section(section: &Value) -> Option<u64> {
    if let Some(count) = section.get("count").and_then(Value::as_u64) {
        return Some(count);
    }
    if let Some(count) = section.get("found_count").and_then(Value::as_u64) {
        return Some(count);
    }
    if let Some(arr) = section.get("list").and_then(Value::as_array) {
        return Some(arr.len() as u64);
    }
    if let Some(arr) = section.get("items").and_then(Value::as_array) {
        return Some(arr.len() as u64);
    }
    if let Some(arr) = section.as_array() {
        return Some(arr.len() as u64);
    }
    None
}

fn count_vulnerability_findings(payload: &Value) -> u64 {
    for key in ["vulnerabilities", "advisories"] {
        if let Some(section) = payload.get(key) {
            if let Some(count) = count_from_section(section) {
                return count;
            }
        }
    }
    count_from_section(payload).unwrap_or(0)
}

fn count_outdated_dependencies(payload: &Value) -> u64 {
    if let Some(arr) = payload.as_array() {
        return arr.len() as u64;
    }
    if let Some(obj) = payload.as_object() {
        for key in ["outdated", "dependencies", "packages", "results"] {
            if let Some(arr) = obj.get(key).and_then(Value::as_array) {
                return arr.len() as u64;
            }
        }
        if !obj.is_empty() && obj.values().all(Value::is_object) {
            return obj.len() as u64;
        }
    }
    0
}

fn classify_clippy_finding(code: &str) -> &'static str {
    let high_patterns = [
        "unwrap_used",
        "expect_used",
        "panic",
        "todo",
        "unimplemented",
        "indexing_slicing",
    ];
    if high_patterns.iter().any(|pattern| code.contains(pattern)) {
        return "high";
    }
    let medium_patterns = ["suspicious", "correctness", "perf", "complexity"];
    if medium_patterns.iter().any(|pattern| code.contains(pattern)) {
        return "medium";
    }
    "low"
}

fn parse_clippy_messages(output: &str) -> (f64, f64, f64, f64) {
    let mut high = 0.0;
    let mut medium = 0.0;
    let mut low = 0.0;
    let mut parse_errors = 0.0;

    for line in output.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }
        let Ok(payload) = serde_json::from_str::<Value>(trimmed) else {
            if trimmed.starts_with('{') {
                parse_errors += 1.0;
            }
            continue;
        };
        if payload.get("reason").and_then(Value::as_str) != Some("compiler-message") {
            continue;
        }
        let Some(message) = payload.get("message") else {
            parse_errors += 1.0;
            continue;
        };
        if message.get("level").and_then(Value::as_str) != Some("warning") {
            continue;
        }

        let code = message
            .get("code")
            .and_then(|c| c.get("code"))
            .and_then(Value::as_str)
            .unwrap_or("");
        if !code.is_empty() && !code.starts_with("clippy::") {
            continue;
        }

        match classify_clippy_finding(code) {
            "high" => high += 1.0,
            "medium" => medium += 1.0,
            _ => low += 1.0,
        }
    }

    (high, medium, low, parse_errors)
}

fn dependency_scan_metrics() -> Map<String, Value> {
    let start = Instant::now();
    let rust_dir = repo_root().join("benchmarks/rust");
    let mut map = Map::new();
    let mut vulnerability_findings = 0.0;
    let mut outdated_dependencies = 0.0;
    let mut audit_exit_code = -1.0;
    let mut outdated_exit_code = -1.0;
    let mut scan_errors = 0.0;
    let tool_available = if has_cargo_subcommand("audit") { 1.0 } else { 0.0 };

    if tool_available > 0.0 {
        let mut audit_cmd = Command::new("cargo");
        audit_cmd.args(["audit", "--json"]).current_dir(&rust_dir);
        let (code, stdout, _) = command_output(audit_cmd);
        audit_exit_code = code as f64;
        if let Ok(parsed) = serde_json::from_str::<Value>(&stdout) {
            vulnerability_findings = count_vulnerability_findings(&parsed) as f64;
        } else {
            scan_errors += 1.0;
        }
        if code != 0 {
            scan_errors += 1.0;
        }
    } else {
        scan_errors += 1.0;
    }

    if has_cargo_subcommand("outdated") {
        let mut outdated_cmd = Command::new("cargo");
        outdated_cmd
            .args([
                "outdated",
                "--format",
                "json",
            ])
            .current_dir(&rust_dir);
        let (code, stdout, _) = command_output(outdated_cmd);
        outdated_exit_code = code as f64;
        if code == 0 {
            if let Ok(parsed) = serde_json::from_str::<Value>(&stdout) {
                outdated_dependencies = count_outdated_dependencies(&parsed) as f64;
            } else {
                scan_errors += 1.0;
            }
        } else {
            scan_errors += 1.0;
        }
    }

    let runtime = start.elapsed().as_secs_f64();
    map.insert("runtime_seconds".to_string(), metric(runtime, "s"));
    map.insert(
        "vulnerability_findings".to_string(),
        metric(vulnerability_findings, "count"),
    );
    map.insert(
        "outdated_dependencies".to_string(),
        metric(outdated_dependencies, "count"),
    );
    map.insert("audit_exit_code".to_string(), metric(audit_exit_code, "code"));
    map.insert(
        "outdated_exit_code".to_string(),
        metric(outdated_exit_code, "code"),
    );
    map.insert("tool_available".to_string(), metric(tool_available, "flag"));
    map.insert("scan_errors".to_string(), metric(scan_errors, "count"));
    map
}

fn static_lint_metrics() -> Map<String, Value> {
    let start = Instant::now();
    let mut map = Map::new();
    let mut high_findings = 0.0;
    let mut medium_findings = 0.0;
    let mut low_findings = 0.0;
    let mut finding_count = 0.0;
    let mut lint_exit_code = -1.0;
    let mut scan_errors = 0.0;
    let tool_available = if has_cargo_subcommand("clippy") { 1.0 } else { 0.0 };

    if tool_available > 0.0 {
        let mut cmd = Command::new("cargo");
        cmd.args([
            "clippy",
            "--manifest-path",
            "benchmarks/rust/Cargo.toml",
            "--message-format",
            "json",
            "--",
            "-W",
            "clippy::suspicious",
            "-W",
            "clippy::correctness",
        ])
        .current_dir(repo_root());
        let (code, stdout, stderr) = command_output(cmd);
        lint_exit_code = code as f64;
        let joined = format!("{stdout}\n{stderr}");
        let (high, medium, low, parse_errors) = parse_clippy_messages(&joined);
        high_findings = high;
        medium_findings = medium;
        low_findings = low;
        finding_count = high + medium + low;
        scan_errors += parse_errors;
        if code != 0 {
            scan_errors += 1.0;
        }
    } else {
        scan_errors += 1.0;
    }

    let runtime = start.elapsed().as_secs_f64();
    map.insert("runtime_seconds".to_string(), metric(runtime, "s"));
    map.insert("finding_count".to_string(), metric(finding_count, "count"));
    map.insert("high_findings".to_string(), metric(high_findings, "count"));
    map.insert("medium_findings".to_string(), metric(medium_findings, "count"));
    map.insert("low_findings".to_string(), metric(low_findings, "count"));
    map.insert("lint_exit_code".to_string(), metric(lint_exit_code, "code"));
    map.insert("tool_available".to_string(), metric(tool_available, "flag"));
    map.insert("scan_errors".to_string(), metric(scan_errors, "count"));
    map
}

fn test_reliability_metrics(iterations: usize) -> Map<String, Value> {
    let start = Instant::now();
    let mut failures = 0.0;
    for _ in 0..iterations {
        let mut cmd = Command::new("cargo");
        cmd.args(["test", "--manifest-path", "benchmarks/rust/Cargo.toml"])
            .current_dir(repo_root());
        let (code, _, _) = command_output(cmd);
        if code != 0 {
            failures += 1.0;
        }
    }
    let runtime = start.elapsed().as_secs_f64();
    let mut map = Map::new();
    map.insert("runtime_seconds".to_string(), metric(runtime, "s"));
    map.insert("iterations".to_string(), metric(iterations as f64, "count"));
    map.insert("failed_iterations".to_string(), metric(failures, "count"));
    map.insert(
        "flaky_rate".to_string(),
        metric(failures / iterations.max(1) as f64, "ratio"),
    );
    map
}

fn build_startup_metrics() -> Map<String, Value> {
    let total_start = Instant::now();

    let build_start = Instant::now();
    let mut build_cmd = Command::new("cargo");
    build_cmd
        .args(["build", "--manifest-path", "benchmarks/rust/Cargo.toml"])
        .current_dir(repo_root());
    let (build_code, _, _) = command_output(build_cmd);
    let build_elapsed = build_start.elapsed().as_secs_f64();

    let startup_start = Instant::now();
    let startup_code = match env::current_exe() {
        Ok(exe) => Command::new(exe)
            .arg("--noop")
            .output()
            .ok()
            .and_then(|output| output.status.code())
            .unwrap_or(1),
        Err(_) => 1,
    };
    let startup_elapsed = startup_start.elapsed().as_secs_f64();

    let artifact_size_kb = env::current_exe()
        .ok()
        .and_then(|path| fs::metadata(path).ok())
        .map(|m| m.len() as f64 / 1024.0)
        .unwrap_or(0.0);

    let mut map = Map::new();
    map.insert(
        "runtime_seconds".to_string(),
        metric(total_start.elapsed().as_secs_f64(), "s"),
    );
    map.insert("build_seconds".to_string(), metric(build_elapsed, "s"));
    map.insert("startup_seconds".to_string(), metric(startup_elapsed, "s"));
    map.insert("artifact_size_kb".to_string(), metric(artifact_size_kb, "kb"));
    map.insert(
        "operation_errors".to_string(),
        metric(((build_code != 0) as u8 + (startup_code != 0) as u8) as f64, "count"),
    );
    map
}

fn run() -> Vec<Value> {
    let run_id = format!(
        "rust-{}-{}",
        std::process::id(),
        Utc::now().timestamp_millis()
    );
    let base_url =
        env::var("BENCHMARK_HTTP_BASE_URL").unwrap_or_else(|_| "http://127.0.0.1:8000".to_string());
    let requests = env_usize("BENCHMARK_HTTP_REQUESTS", 400);
    let rows = env_usize("BENCHMARK_HTTP_ROWS", 1000);
    let concurrency = env_usize("BENCHMARK_HTTP_CONCURRENCY", 16);
    let iterations = env_usize("BENCHMARK_TEST_REPEAT", 3);
    let dataset = resolve_dataset();

    let mut records = Vec::new();

    let start = Instant::now();
    let pi = monte_carlo_pi(200_000);
    let elapsed = start.elapsed().as_secs_f64();
    let mut cpu_metrics = Map::new();
    cpu_metrics.insert("runtime_seconds".to_string(), metric(elapsed, "s"));
    cpu_metrics.insert("pi_estimate".to_string(), metric(pi, "ratio"));
    records.push(make_record(
        "cpu_monte_carlo_pi",
        "performance",
        cpu_metrics,
        &run_id,
    ));

    let start = Instant::now();
    let checksum = json_parse_transform(20_000) as f64;
    let elapsed = start.elapsed().as_secs_f64();
    let mut json_metrics = Map::new();
    json_metrics.insert("runtime_seconds".to_string(), metric(elapsed, "s"));
    json_metrics.insert("checksum".to_string(), metric(checksum, "count"));
    records.push(make_record(
        "string_json_parse_transform",
        "performance",
        json_metrics,
        &run_id,
    ));

    let start = Instant::now();
    let (completed, http_checksum, http_errors) =
        io_http_benchmark(&base_url, requests, rows, concurrency);
    let elapsed = start.elapsed().as_secs_f64();
    let mut io_metrics = Map::new();
    io_metrics.insert("runtime_seconds".to_string(), metric(elapsed, "s"));
    io_metrics.insert(
        "requests_completed".to_string(),
        metric(completed as f64, "count"),
    );
    io_metrics.insert("checksum".to_string(), metric(http_checksum as f64, "count"));
    io_metrics.insert("request_errors".to_string(), metric(http_errors as f64, "count"));
    records.push(make_record(
        "io_concurrent_http_client",
        "performance",
        io_metrics,
        &run_id,
    ));

    let start = Instant::now();
    let (etl_rows, etl_aggregate, etl_bytes) = etl_benchmark(&dataset);
    let elapsed = start.elapsed().as_secs_f64();
    let mut etl_metrics = Map::new();
    etl_metrics.insert("runtime_seconds".to_string(), metric(elapsed, "s"));
    etl_metrics.insert(
        "records_processed".to_string(),
        metric(etl_rows as f64, "count"),
    );
    etl_metrics.insert(
        "aggregate_value".to_string(),
        metric(etl_aggregate as f64, "count"),
    );
    etl_metrics.insert(
        "throughput_mb_s".to_string(),
        metric(
            ((etl_bytes as f64) / (1024.0 * 1024.0)) / elapsed.max(1e-9),
            "mb/s",
        ),
    );
    records.push(make_record(
        "data_pipeline_etl_minibatch",
        "performance",
        etl_metrics,
        &run_id,
    ));

    records.push(make_record(
        "dependency_vulnerability_scan_scorecard",
        "security",
        dependency_scan_metrics(),
        &run_id,
    ));
    records.push(make_record(
        "static_security_lint_benchmark",
        "security",
        static_lint_metrics(),
        &run_id,
    ));
    records.push(make_record(
        "test_robustness_reliability",
        "quality",
        test_reliability_metrics(iterations),
        &run_id,
    ));
    records.push(make_record(
        "build_startup_feedback_loop",
        "quality",
        build_startup_metrics(),
        &run_id,
    ));

    records
}

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() == 2 && args[1] == "--noop" {
        return;
    }
    if args.len() != 3 || args[1] != "--output" {
        eprintln!("Usage: rust-benchmarks --output <path>");
        std::process::exit(2);
    }

    let out = PathBuf::from(&args[2]);
    let records = run();
    let payload = serde_json::to_string_pretty(&records).expect("serialize results");
    fs::write(out, payload).expect("write output");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn monte_carlo_reasonable() {
        let estimate = monte_carlo_pi(10_000);
        assert!(estimate > 3.0 && estimate < 3.3);
    }

    #[test]
    fn parse_checksum() {
        let checksum = json_parse_transform(100);
        let expected: u64 = (0..100).map(|i| (i % 17) as u64).sum();
        assert_eq!(checksum, expected);
    }
}
