#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./e2e/benchmark.sh [options]

Starts the Docker Compose stack, generates N sample PDFs, waits for the
lister/indexer pipeline to process them, measures search latency and container
memory usage, and writes a JSON report.

Options:
  -n, --docs COUNT        Number of sample PDFs to generate (default: 25)
  -o, --output PATH       Output JSON path (default: e2e/benchmark-results.json)
      --library PATH      Host path bound as E2E library (default: /tmp/aithena-benchmark-library)
      --no-start          Reuse an already running stack instead of calling docker compose up -d
      --no-build          Skip --build when starting the stack
      --api-user USER     Login user for protected /v1/search benchmarking
      --api-pass PASS     Login password for protected /v1/search benchmarking
  -h, --help              Show this help text

Environment overrides:
  DOC_COUNT, OUTPUT_JSON, E2E_LIBRARY_PATH, QUEUE_NAME, WAIT_TIMEOUT,
  POLL_INTERVAL, SEARCH_ITERATIONS, SEARCH_API_URL, SOLR_COLLECTION_URL,
  EMBEDDINGS_URL, API_USER, API_PASS

Notes:
  - Requires Docker Compose and published debug ports from docker-compose.override.yml.
  - If API credentials are omitted, keyword/semantic/hybrid latency is measured
    directly against Solr + embeddings-server instead of the protected /v1/search API.
EOF
}

DOC_COUNT="${DOC_COUNT:-25}"
OUTPUT_JSON="${OUTPUT_JSON:-e2e/benchmark-results.json}"
E2E_LIBRARY_PATH="${E2E_LIBRARY_PATH:-/tmp/aithena-benchmark-library}"
QUEUE_NAME="${QUEUE_NAME:-shortembeddings}"
WAIT_TIMEOUT="${WAIT_TIMEOUT:-900}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
SEARCH_ITERATIONS="${SEARCH_ITERATIONS:-7}"
SEARCH_API_URL="${SEARCH_API_URL:-http://localhost:8080}"
SOLR_COLLECTION_URL="${SOLR_COLLECTION_URL:-http://localhost:8983/solr/books}"
EMBEDDINGS_URL="${EMBEDDINGS_URL:-http://localhost:8085/v1/embeddings/}"
API_USER="${API_USER:-}"
API_PASS="${API_PASS:-}"
START_STACK=1
BUILD_STACK=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--docs)
      DOC_COUNT="$2"
      shift 2
      ;;
    -o|--output)
      OUTPUT_JSON="$2"
      shift 2
      ;;
    --library)
      E2E_LIBRARY_PATH="$2"
      shift 2
      ;;
    --no-start)
      START_STACK=0
      shift
      ;;
    --no-build)
      BUILD_STACK=0
      shift
      ;;
    --api-user)
      API_USER="$2"
      shift 2
      ;;
    --api-pass)
      API_PASS="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

case "$DOC_COUNT" in
  ''|*[!0-9]*)
    echo "DOC_COUNT must be a positive integer" >&2
    exit 1
    ;;
esac

if [[ "$DOC_COUNT" -le 0 ]]; then
  echo "DOC_COUNT must be greater than zero" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$OUTPUT_JSON" != /* ]]; then
  OUTPUT_JSON="$REPO_ROOT/$OUTPUT_JSON"
fi
mkdir -p "$E2E_LIBRARY_PATH"
mkdir -p "$(dirname "$OUTPUT_JSON")"

compose_cmd=(docker compose -f docker-compose.yml -f docker-compose.e2e.yml)
startup_started="$(python3 - <<'PY'
import time
print(time.time())
PY
)"

if [[ "$START_STACK" -eq 1 ]]; then
  start_args=(up -d)
  if [[ "$BUILD_STACK" -eq 1 ]]; then
    start_args+=(--build)
  fi
  echo "[benchmark] Starting stack..."
  (
    cd "$REPO_ROOT"
    E2E_LIBRARY_PATH="$E2E_LIBRARY_PATH" "${compose_cmd[@]}" "${start_args[@]}"
  )
fi

export REPO_ROOT OUTPUT_JSON E2E_LIBRARY_PATH QUEUE_NAME WAIT_TIMEOUT POLL_INTERVAL \
  SEARCH_ITERATIONS SEARCH_API_URL SOLR_COLLECTION_URL EMBEDDINGS_URL API_USER API_PASS \
  DOC_COUNT STARTUP_STARTED="$startup_started"

python3 - <<'PY'
from __future__ import annotations

import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(os.environ["REPO_ROOT"])
OUTPUT_JSON = Path(os.environ["OUTPUT_JSON"]).resolve()
LIBRARY_ROOT = Path(os.environ["E2E_LIBRARY_PATH"])
QUEUE_NAME = os.environ["QUEUE_NAME"]
WAIT_TIMEOUT = int(os.environ["WAIT_TIMEOUT"])
POLL_INTERVAL = int(os.environ["POLL_INTERVAL"])
SEARCH_ITERATIONS = int(os.environ["SEARCH_ITERATIONS"])
SEARCH_API_URL = os.environ["SEARCH_API_URL"].rstrip("/")
SOLR_COLLECTION_URL = os.environ["SOLR_COLLECTION_URL"].rstrip("/")
EMBEDDINGS_URL = os.environ["EMBEDDINGS_URL"].rstrip("/")
API_USER = os.environ.get("API_USER", "")
API_PASS = os.environ.get("API_PASS", "")
DOC_COUNT = int(os.environ["DOC_COUNT"])
STARTUP_STARTED = float(os.environ["STARTUP_STARTED"])
COMPOSE_BASE = ["docker", "compose", "-f", "docker-compose.yml", "-f", "docker-compose.e2e.yml"]

SERVICES_TO_SAMPLE = [
    "redis",
    "rabbitmq",
    "embeddings-server",
    "document-lister",
    "document-indexer",
    "solr-search",
    "solr",
    "solr2",
    "solr3",
    "aithena-ui",
    "nginx",
    "zoo1",
    "zoo2",
    "zoo3",
]


def run_compose(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        COMPOSE_BASE + args,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def http_json(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, str] | None = None,
    data: object | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> object:
    request_url = url
    if params:
        request_url += ("&" if "?" in request_url else "?") + urllib.parse.urlencode(params, doseq=True)
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    payload = None
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(request_url, data=payload, headers=request_headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_http(url: str, *, timeout: int, label: str) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            http_json(url, timeout=5)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(2)
    raise RuntimeError(f"Timed out waiting for {label} at {url}: {last_error}")


def wait_for_stack() -> dict[str, float]:
    wait_for_http("http://localhost:8983/solr/admin/info/system", timeout=WAIT_TIMEOUT, label="Solr node")
    wait_for_http(f"{SOLR_COLLECTION_URL}/admin/ping", timeout=WAIT_TIMEOUT, label="Solr books collection")
    wait_for_http("http://localhost:8085/health", timeout=WAIT_TIMEOUT, label="embeddings-server")
    wait_for_http(f"{SEARCH_API_URL}/health", timeout=WAIT_TIMEOUT, label="solr-search")
    return {
        "startup_seconds": round(time.time() - STARTUP_STARTED, 3),
    }


def build_pdf(text: str) -> bytes:
    stream_body = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R"
            b" /MediaBox [0 0 612 792]"
            b" /Contents 4 0 R"
            b" /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Length "
            + str(len(stream_body)).encode()
            + b" >>\nstream\n"
            + stream_body
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    header = b"%PDF-1.4\n"
    body = b""
    offsets: list[int] = []
    offset = len(header)
    for obj in objects:
        offsets.append(offset)
        body += obj
        offset += len(obj)
    xref_offset = len(header) + len(body)
    xref = b"xref\n" + f"0 {len(objects) + 1}\n".encode()
    xref += b"0000000000 65535 f \n"
    for off in offsets:
        xref += f"{off:010d} 00000 n \n".encode()
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    ).encode()
    return header + body + xref + trailer


def sha256_hex(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_documents(run_id: str, token: str, semantic_phrase: str) -> list[dict[str, str]]:
    run_dir = LIBRARY_ROOT / run_id
    if run_dir.exists():
        shutil.rmtree(run_dir)
    docs: list[dict[str, str]] = []
    for index in range(DOC_COUNT):
        author = f"BenchAuthor{index % 10:02d}"
        relative_dir = Path(run_id) / f"bucket-{index % 5:02d}" / author
        filename = f"{author} - {token} Search Benchmark {index:04d} (2026).pdf"
        relative_path = relative_dir / filename
        absolute_path = LIBRARY_ROOT / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        text = (
            f"{semantic_phrase}. This benchmark document number {index}. "
            f"Keyword token {token}. Search benchmark library document."
        )
        absolute_path.write_bytes(build_pdf(text))
        rel_posix = relative_path.as_posix()
        docs.append(
            {
                "relative_path": rel_posix,
                "absolute_path": str(absolute_path),
                "container_path": f"/data/documents/{rel_posix}",
                "redis_key": f"/{QUEUE_NAME}//data/documents/{rel_posix}",
                "solr_id": sha256_hex(rel_posix),
            }
        )
    return docs


def fetch_redis_states(keys: list[str]) -> dict[str, str | None]:
    if not keys:
        return {}
    script = (
        "import json, os, redis, sys; "
        "client = redis.Redis(host=os.environ['REDIS_HOST'], port=int(os.environ['REDIS_PORT']), "
        "decode_responses=True); "
        "print(json.dumps({key: client.get(key) for key in sys.argv[1:]}))"
    )
    result = run_compose(["exec", "-T", "solr-search", "python", "-c", script, *keys])
    return json.loads(result.stdout or "{}")


def fetch_queue_depth() -> dict[str, int]:
    result = run_compose(["exec", "-T", "rabbitmq", "rabbitmqctl", "list_queues", "name", "messages", "messages_ready", "messages_unacknowledged", "-q"])
    metrics = {"messages": 0, "messages_ready": 0, "messages_unacknowledged": 0}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        name, messages, ready, unacked = parts
        if name == QUEUE_NAME:
            metrics = {
                "messages": int(messages),
                "messages_ready": int(ready),
                "messages_unacknowledged": int(unacked),
            }
            break
    return metrics


def wait_for_indexing(redis_keys: list[str]) -> dict[str, object]:
    history: list[dict[str, object]] = []
    started = time.perf_counter()
    deadline = started + WAIT_TIMEOUT
    last_snapshot: dict[str, object] | None = None
    while time.perf_counter() < deadline:
        raw_states = fetch_redis_states(redis_keys)
        processed = 0
        failed = 0
        queued = 0
        latest_states: dict[str, object] = {}
        for key in redis_keys:
            payload = raw_states.get(key)
            if payload is None:
                queued += 1
                latest_states[key] = None
                continue
            state = json.loads(payload)
            latest_states[key] = state
            if state.get("failed"):
                failed += 1
            elif state.get("processed"):
                processed += 1
            else:
                queued += 1
        queue_depth = fetch_queue_depth()
        elapsed = round(time.perf_counter() - started, 3)
        snapshot = {
            "elapsed_seconds": elapsed,
            "processed": processed,
            "failed": failed,
            "queued": queued,
            "queue_depth": queue_depth,
        }
        history.append(snapshot)
        last_snapshot = snapshot
        if processed + failed >= len(redis_keys):
            break
        time.sleep(POLL_INTERVAL)
    else:
        raise RuntimeError(f"Timed out waiting for {len(redis_keys)} benchmark documents to finish indexing")

    elapsed = max(time.perf_counter() - started, 0.001)
    assert last_snapshot is not None
    return {
        "elapsed_seconds": round(elapsed, 3),
        "processed": last_snapshot["processed"],
        "failed": last_snapshot["failed"],
        "queued": last_snapshot["queued"],
        "throughput_docs_per_sec": round(last_snapshot["processed"] / elapsed, 4),
        "history": history,
    }


def login_headers() -> tuple[dict[str, str] | None, str]:
    if not API_USER or not API_PASS:
        return None, "direct-services"
    try:
        payload = http_json(
            f"{SEARCH_API_URL}/v1/auth/login",
            method="POST",
            data={"username": API_USER, "password": API_PASS},
            timeout=15,
        )
        token = payload.get("access_token")  # type: ignore[assignment]
        if not isinstance(token, str) or not token:
            return None, "direct-services"
        return {"Authorization": f"Bearer {token}"}, "search-api"
    except Exception:
        return None, "direct-services"


def measure_once(url: str, *, params: dict[str, str], headers: dict[str, str] | None = None) -> float:
    started = time.perf_counter()
    http_json(url, params=params, headers=headers, timeout=60)
    return (time.perf_counter() - started) * 1000.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    index = (len(values) - 1) * p
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return values[int(index)]
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def summarize_latencies(samples: list[float]) -> dict[str, float | int]:
    ordered = sorted(samples)
    return {
        "iterations": len(samples),
        "min_ms": round(min(ordered), 3),
        "mean_ms": round(statistics.mean(ordered), 3),
        "p50_ms": round(percentile(ordered, 0.50), 3),
        "p95_ms": round(percentile(ordered, 0.95), 3),
        "max_ms": round(max(ordered), 3),
    }


def build_solr_keyword_params(query: str) -> dict[str, str | list[str]]:
    return {
        "q": query,
        "rows": "10",
        "defType": "edismax",
        "wt": "json",
        "fl": "id,title_s,score",
        "facet": "false",
        "hl": "false",
    }


def fetch_embedding(query: str) -> list[float]:
    payload = http_json(EMBEDDINGS_URL, method="POST", data={"input": query}, timeout=60)
    data = payload["data"]
    return data[0]["embedding"]


def solr_knn_query(vector: list[float], query_filter: str | None = None) -> object:
    vector_str = "[" + ",".join(str(value) for value in vector) + "]"
    params: dict[str, str] = {
        "q": f"{{!knn f=book_embedding topK=10}}{vector_str}",
        "rows": "10",
        "fl": "id,title_s,score",
        "wt": "json",
    }
    if query_filter:
        params["fq"] = query_filter
    return http_json(
        f"{SOLR_COLLECTION_URL}/select",
        params=params,
        timeout=60,
    )


def direct_keyword_latency(query: str) -> float:
    started = time.perf_counter()
    http_json(f"{SOLR_COLLECTION_URL}/select", params=build_solr_keyword_params(query), timeout=60)
    return (time.perf_counter() - started) * 1000.0


def direct_semantic_latency(query: str, query_filter: str | None = None) -> float:
    started = time.perf_counter()
    vector = fetch_embedding(query)
    solr_knn_query(vector, query_filter)
    return (time.perf_counter() - started) * 1000.0


def direct_hybrid_latency(query: str, keyword_token: str, query_filter: str | None = None) -> float:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as pool:
        keyword_future = pool.submit(
            http_json,
            f"{SOLR_COLLECTION_URL}/select",
            params=build_solr_keyword_params(keyword_token),
            timeout=60,
        )
        embedding_future = pool.submit(fetch_embedding, query)
        keyword_future.result()
        vector = embedding_future.result()
    solr_knn_query(vector, query_filter)
    return (time.perf_counter() - started) * 1000.0


def benchmark_search(keyword_token: str, semantic_phrase: str) -> dict[str, object]:
    headers, backend = login_headers()
    warmup_modes = ("keyword", "semantic", "hybrid")
    if headers is not None:
        try:
            for mode in warmup_modes:
                http_json(
                    f"{SEARCH_API_URL}/v1/search",
                    params={"q": semantic_phrase if mode != "keyword" else keyword_token, "mode": mode, "limit": "10"},
                    headers=headers,
                    timeout=60,
                )
            keyword_samples = [
                measure_once(
                    f"{SEARCH_API_URL}/v1/search",
                    params={"q": keyword_token, "mode": "keyword", "limit": "10"},
                    headers=headers,
                )
                for _ in range(SEARCH_ITERATIONS)
            ]
            semantic_samples = [
                measure_once(
                    f"{SEARCH_API_URL}/v1/search",
                    params={"q": semantic_phrase, "mode": "semantic", "limit": "10"},
                    headers=headers,
                )
                for _ in range(SEARCH_ITERATIONS)
            ]
            hybrid_samples = [
                measure_once(
                    f"{SEARCH_API_URL}/v1/search",
                    params={"q": semantic_phrase, "mode": "hybrid", "limit": "10"},
                    headers=headers,
                )
                for _ in range(SEARCH_ITERATIONS)
            ]
            return {
                "backend": backend,
                "keyword": summarize_latencies(keyword_samples),
                "semantic": summarize_latencies(semantic_samples),
                "hybrid": summarize_latencies(hybrid_samples),
            }
        except Exception:  # noqa: BLE001
            backend = "direct-services"

    direct_keyword_latency(keyword_token)
    direct_semantic_latency(semantic_phrase)
    direct_hybrid_latency(semantic_phrase, keyword_token)
    keyword_samples = [direct_keyword_latency(keyword_token) for _ in range(SEARCH_ITERATIONS)]
    semantic_samples = [direct_semantic_latency(semantic_phrase) for _ in range(SEARCH_ITERATIONS)]
    hybrid_samples = [direct_hybrid_latency(semantic_phrase, keyword_token) for _ in range(SEARCH_ITERATIONS)]
    return {
        "backend": backend,
        "keyword": summarize_latencies(keyword_samples),
        "semantic": summarize_latencies(semantic_samples),
        "hybrid": summarize_latencies(hybrid_samples),
    }


def parse_memory_usage(mem_usage: str) -> float:
    current = mem_usage.split("/")[0].strip()
    number = ""
    unit = ""
    for char in current:
        if char.isdigit() or char == ".":
            number += char
        else:
            unit += char
    value = float(number or 0)
    unit = unit.strip().lower()
    scale = {
        "b": 1 / (1024 * 1024),
        "kib": 1 / 1024,
        "kb": 1 / 1024,
        "mib": 1,
        "mb": 1,
        "gib": 1024,
        "gb": 1024,
    }.get(unit, 1)
    return round(value * scale, 3)


def collect_service_memory() -> dict[str, dict[str, object]]:
    memory: dict[str, dict[str, object]] = {}
    for service in SERVICES_TO_SAMPLE:
        ps_result = run_compose(["ps", "-q", service], check=False)
        container_id = ps_result.stdout.strip()
        if not container_id:
            continue
        stats = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", container_id],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        line = (stats.stdout or "").strip()
        if not line:
            continue
        payload = json.loads(line)
        memory[service] = {
            "container": payload.get("Name"),
            "memory_mb": parse_memory_usage(str(payload.get("MemUsage", "0MiB / 0MiB"))),
            "memory_percent": payload.get("MemPerc"),
            "cpu_percent": payload.get("CPUPerc"),
        }
    return memory


startup = wait_for_stack()
run_timestamp = time.strftime("%Y%m%d-%H%M%S")
run_id = f"benchmark-run-{run_timestamp}"
keyword_token = run_id.replace("-", "")
semantic_phrase = "historical catalan folklore archive benchmark"
documents = create_documents(run_id, keyword_token, semantic_phrase)
indexing = wait_for_indexing([doc["redis_key"] for doc in documents])
search = benchmark_search(keyword_token, semantic_phrase)
queue_depth = fetch_queue_depth()
services = collect_service_memory()

report = {
    "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "config": {
        "doc_count": DOC_COUNT,
        "library_root": str(LIBRARY_ROOT),
        "queue_name": QUEUE_NAME,
        "search_iterations": SEARCH_ITERATIONS,
        "search_api_url": SEARCH_API_URL,
        "solr_collection_url": SOLR_COLLECTION_URL,
        "embeddings_url": EMBEDDINGS_URL,
        "authenticated_search": bool(API_USER and API_PASS),
    },
    "dataset": {
        "run_id": run_id,
        "keyword_token": keyword_token,
        "semantic_phrase": semantic_phrase,
        "documents": documents,
    },
    "startup": startup,
    "indexing": indexing,
    "search": search,
    "queue": queue_depth,
    "services": services,
}

OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "output": str(OUTPUT_JSON),
    "startup_seconds": startup["startup_seconds"],
    "throughput_docs_per_sec": indexing["throughput_docs_per_sec"],
    "search_backend": search["backend"],
}, indent=2))
PY
