from __future__ import annotations

import gzip
import json
import os
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import sleep

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "results" / "raw"
NORM = ROOT / "results" / "normalized"
DATASETS = ROOT / "benchmarks" / "shared" / "datasets"

HTTP_REQUESTS = 400
HTTP_CONCURRENCY = 16
HTTP_ROWS = 1_000
ETL_ROWS = 20_000
TEST_REPEAT = 3


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if not self.path.startswith("/item/"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            item_id = int(self.path.split("/")[-1])
        except ValueError:
            self.send_response(400)
            self.end_headers()
            return

        payload = json.dumps(
            {"id": item_id, "value": item_id % 17, "name": f"row-{item_id}"},
            separators=(",", ":"),
        ).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args: object) -> None:
        return


def build_etl_dataset(path: Path, rows: int = ETL_ROWS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for idx in range(rows):
            record = {
                "id": idx,
                "group": idx % 50,
                "value": (idx * 7 + 11) % 10_000,
                "score": (idx * 13 + 17) % 10_000,
            }
            handle.write(json.dumps(record, separators=(",", ":")) + "\n")


def start_http_server() -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def run_cmd(cmd: list[str], env: dict[str, str]) -> None:
    subprocess.run(cmd, check=True, cwd=ROOT, env=env)


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_prereqs() -> None:
    missing = [tool for tool in ("python3", "cargo") if shutil.which(tool) is None]
    if missing:
        missing_joined = ", ".join(missing)
        raise SystemExit(f"Missing required tool(s): {missing_joined}")


def configure_linker_env(env: dict[str, str]) -> None:
    if shutil.which("cc"):
        return

    path_value = env.get("PATH", "")
    conda_bin = Path.home() / "miniconda3" / "bin"
    extra_path = f"{conda_bin}:{path_value}" if conda_bin.exists() else path_value
    cc = shutil.which("x86_64-conda-linux-gnu-cc", path=extra_path)
    cxx = shutil.which("x86_64-conda-linux-gnu-c++", path=extra_path)
    if not cc:
        return

    env["PATH"] = f"{Path(cc).parent}:{path_value}" if path_value else str(Path(cc).parent)
    env.setdefault("CC", cc)
    if cxx:
        env.setdefault("CXX", cxx)
    env.setdefault("CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER", cc)


def main() -> None:
    ensure_prereqs()
    RAW.mkdir(parents=True, exist_ok=True)
    NORM.mkdir(parents=True, exist_ok=True)
    DATASETS.mkdir(parents=True, exist_ok=True)

    py_raw = RAW / "python_perf.json"
    rs_raw = RAW / "rust_perf.json"
    etl_dataset = DATASETS / "etl_input.jsonl.gz"

    build_etl_dataset(etl_dataset)
    server, base_url = start_http_server()
    sleep(0.05)

    env = os.environ.copy()
    env["BENCHMARK_HTTP_BASE_URL"] = base_url
    env["BENCHMARK_HTTP_REQUESTS"] = str(HTTP_REQUESTS)
    env["BENCHMARK_HTTP_CONCURRENCY"] = str(HTTP_CONCURRENCY)
    env["BENCHMARK_HTTP_ROWS"] = str(HTTP_ROWS)
    env["BENCHMARK_ETL_DATASET"] = str(etl_dataset)
    env["BENCHMARK_TEST_REPEAT"] = str(TEST_REPEAT)
    configure_linker_env(env)

    try:
        run_cmd(["python3", "benchmarks/python/perf/runner.py", "--output", str(py_raw)], env=env)
        run_cmd(
            ["cargo", "run", "--manifest-path", "benchmarks/rust/Cargo.toml", "--", "--output", str(rs_raw)],
            env=env,
        )
    finally:
        server.shutdown()
        server.server_close()

    combined = load(py_raw) + load(rs_raw)
    normalized = NORM / "latest.json"
    normalized.write_text(json.dumps(combined, indent=2), encoding="utf-8")

    run_cmd(["python3", "benchmarks/shared/scripts/validate_results.py", str(normalized)], env=env)
    print(f"Wrote {normalized}")


if __name__ == "__main__":
    main()
