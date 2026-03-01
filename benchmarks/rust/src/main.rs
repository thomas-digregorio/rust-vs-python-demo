use std::env;
use std::fs;
use std::process::Command;
use std::time::Instant;

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

fn next_f64(state: &mut u64) -> f64 {
    *state ^= *state << 13;
    *state ^= *state >> 7;
    *state ^= *state << 17;
    (*state as f64) / (u64::MAX as f64)
}

fn json_parse_transform(records: usize) -> u64 {
    (0..records).map(|i| (i % 17) as u64).sum()
}

fn git_sha() -> String {
    Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .output()
        .ok()
        .and_then(|o| String::from_utf8(o.stdout).ok())
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| "unknown00".to_string())
}

fn record_json(id: &str, runtime: f64, aux_name: &str, aux_val: f64) -> String {
    format!(
        concat!(
            "{{",
            "\"benchmark_id\":\"{}\",",
            "\"category\":\"performance\",",
            "\"language\":\"rust\",",
            "\"variant\":{{\"runtime\":\"rust\",\"version\":\"{}\"}},",
            "\"environment\":{{\"os\":\"{}\",\"cpu_count\":{}}},",
            "\"metrics\":{{",
            "\"runtime_seconds\":{{\"value\":{},\"unit\":\"s\"}},",
            "\"{}\":{{\"value\":{},\"unit\":\"{}\"}}",
            "}},",
            "\"timestamp\":\"1970-01-01T00:00:00+00:00\",",
            "\"commit_sha\":\"{}\",",
            "\"run_id\":\"rust-run\"",
            "}}"
        ),
        id,
        env!("CARGO_PKG_VERSION"),
        env::consts::OS,
        std::thread::available_parallelism().map(|x| x.get()).unwrap_or(1),
        runtime,
        aux_name,
        aux_val,
        if aux_name == "pi_estimate" { "ratio" } else { "count" },
        git_sha(),
    )
}

fn run() -> String {
    let start = Instant::now();
    let pi = monte_carlo_pi(200_000);
    let elapsed = start.elapsed().as_secs_f64();

    let start = Instant::now();
    let checksum = json_parse_transform(20_000) as f64;
    let parse_elapsed = start.elapsed().as_secs_f64();

    format!(
        "[{},{}]",
        record_json("cpu_monte_carlo_pi", elapsed, "pi_estimate", pi),
        record_json(
            "string_json_parse_transform",
            parse_elapsed,
            "checksum",
            checksum
        )
    )
}

fn main() {
    let mut args = env::args();
    let _ = args.next();
    let flag = args.next();
    let output = args.next();
    if flag.as_deref() != Some("--output") || output.is_none() {
        eprintln!("Usage: rust-benchmarks --output <path>");
        std::process::exit(2);
    }
    fs::write(output.unwrap(), run()).expect("write output");
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
