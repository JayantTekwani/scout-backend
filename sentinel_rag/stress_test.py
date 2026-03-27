"""
SCOUT Backend Stress Test

Usage examples:
  python3 stress_test.py --total 100 --concurrency 10
  python3 stress_test.py --total 500 --concurrency 25 --base-url http://127.0.0.1:8008
  python3 stress_test.py --total 200 --concurrency 20 --token YOUR_SCOUT_AUTH_TOKEN
"""

import argparse
import base64
import json
import random
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_QUERIES = [
    "What are the API rate limits?",
    "Summarize the main support policy.",
    "What is the recommended onboarding flow?",
    "List key security-related points from docs.",
    "What are the major technical constraints mentioned?",
]


@dataclass
class Result:
    ok: bool
    status: int
    latency_ms: float
    error: str = ""


def req_json(
    base_url: str,
    path: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    token: str = "",
    session_id: str = "",
    timeout: float = 30.0,
) -> tuple[int, dict[str, Any], str]:
    url = f"{base_url.rstrip('/')}{path}"
    body = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Scout-Token"] = token
    if session_id:
        headers["X-Session-Id"] = session_id
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = Request(url=url, data=body, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="ignore")
            data = json.loads(raw) if raw else {}
            return int(resp.status), data, ""
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="ignore")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {}
        return int(e.code), data, f"HTTPError {e.code}"
    except URLError as e:
        return 0, {}, f"URLError {e}"
    except Exception as e:
        return 0, {}, str(e)


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round((p / 100.0) * (len(sorted_vals) - 1)))
    return sorted_vals[max(0, min(idx, len(sorted_vals) - 1))]


def chat_once(
    base_url: str,
    token: str,
    session_id: str,
    query: str,
    access_level: int,
    timeout: float,
) -> Result:
    start = time.perf_counter()
    status, data, err = req_json(
        base_url=base_url,
        path="/chat",
        method="POST",
        payload={
            "query": query,
            "user_access_level": access_level,
            "load_demo_if_empty": True,
            "session_id": session_id,
        },
        token=token,
        session_id=session_id,
        timeout=timeout,
    )
    latency_ms = (time.perf_counter() - start) * 1000.0
    ok = status == 200 and data.get("ok") is True
    return Result(ok=ok, status=status, latency_ms=latency_ms, error=err or data.get("error", ""))


def main() -> None:
    parser = argparse.ArgumentParser(description="Stress test SCOUT backend chat endpoint.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8008")
    parser.add_argument("--token", default="")
    parser.add_argument("--total", type=int, default=100, help="Total chat requests")
    parser.add_argument("--concurrency", type=int, default=10, help="Concurrent workers")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--access-level", type=int, default=2)
    parser.add_argument("--project", default="")
    parser.add_argument(
        "--ingest-seed-doc",
        action="store_true",
        help="Ingest one synthetic doc before load (recommended for fresh project).",
    )
    args = parser.parse_args()

    if args.total <= 0 or args.concurrency <= 0:
        raise SystemExit("total and concurrency must be > 0")

    # 1) Health check
    s, d, e = req_json(args.base_url, "/health", token=args.token, timeout=args.timeout)
    if s != 200 or not d.get("ok"):
        raise SystemExit(f"Backend not ready: status={s}, err={e or d}")

    # 2) Session bootstrap
    sid = f"stress_{uuid.uuid4().hex[:10]}"
    s, d, e = req_json(
        args.base_url,
        "/session",
        method="POST",
        payload={"session_id": sid},
        token=args.token,
        timeout=args.timeout,
    )
    if s != 200 or not d.get("ok"):
        raise SystemExit(f"Session bootstrap failed: status={s}, err={e or d}")

    session_id = d.get("session_id", sid)
    project_name = args.project or f"stress-proj-{uuid.uuid4().hex[:6]}"

    # 3) Project select
    s, d, e = req_json(
        args.base_url,
        "/projects/select",
        method="POST",
        payload={"name": project_name, "create_if_missing": True, "session_id": session_id},
        token=args.token,
        session_id=session_id,
        timeout=args.timeout,
    )
    if s != 200 or not d.get("ok"):
        raise SystemExit(f"Project select failed: status={s}, err={e or d}")

    # 4) Optional seed ingest
    if args.ingest_seed_doc:
        seed_text = (
            "SCOUT seed document. API rate limits: standard 1000 requests/minute. "
            "Enterprise plan includes higher burst and priority support. "
            "Support policy includes onboarding and troubleshooting guidance."
        )
        b64 = base64.b64encode(seed_text.encode("utf-8")).decode("ascii")
        s, d, e = req_json(
            args.base_url,
            "/ingest",
            method="POST",
            payload={
                "files": [{"name": "seed.txt", "content_base64": b64}],
                "authority_score": 0.85,
                "access_level": args.access_level,
                "session_id": session_id,
            },
            token=args.token,
            session_id=session_id,
            timeout=args.timeout,
        )
        if s != 200 or not d.get("ok"):
            raise SystemExit(f"Seed ingest failed: status={s}, err={e or d}")

    print(f"Running stress test: total={args.total}, concurrency={args.concurrency}, session={session_id}")

    results: list[Result] = []
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futures = []
        for _ in range(args.total):
            q = random.choice(DEFAULT_QUERIES)
            futures.append(
                ex.submit(
                    chat_once,
                    args.base_url,
                    args.token,
                    session_id,
                    q,
                    args.access_level,
                    args.timeout,
                )
            )
        for f in as_completed(futures):
            results.append(f.result())

    elapsed = time.perf_counter() - started

    ok_count = sum(1 for r in results if r.ok)
    fail_count = len(results) - ok_count
    latencies = sorted(r.latency_ms for r in results if r.status > 0)
    rps = (len(results) / elapsed) if elapsed > 0 else 0.0

    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)
    avg = statistics.mean(latencies) if latencies else 0.0

    status_counts: dict[int, int] = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1

    print("\n=== SCOUT Stress Test Summary ===")
    print(f"Requests        : {len(results)}")
    print(f"Success         : {ok_count}")
    print(f"Failures        : {fail_count}")
    print(f"Duration (s)    : {elapsed:.2f}")
    print(f"Throughput (RPS): {rps:.2f}")
    print(f"Latency avg ms  : {avg:.1f}")
    print(f"Latency p50 ms  : {p50:.1f}")
    print(f"Latency p95 ms  : {p95:.1f}")
    print(f"Latency p99 ms  : {p99:.1f}")
    print(f"HTTP statuses   : {status_counts}")

    if fail_count:
        top_errors = [r.error for r in results if not r.ok and r.error][:10]
        if top_errors:
            print("\nSample errors:")
            for e in top_errors:
                print(f"- {e}")

    # Non-zero exit for CI-like use when failures exceed 5%
    fail_rate = (fail_count / len(results)) if results else 1.0
    if fail_rate > 0.05:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
