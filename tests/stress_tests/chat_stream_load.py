from __future__ import annotations

import argparse
import asyncio
import csv
import json
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx
from tqdm import tqdm


DEFAULT_PROMPT = (
    "Answer in two short paragraphs: explain why streaming responses are useful "
    "for chat applications."
)
DEFAULT_BASE_URL = "https://llm-backend.cloudlab.zhaw.ch"
CSV_FIELDS = [
    "run_id",
    "concurrency",
    "user_id",
    "request_id",
    "prompt_chars",
    "started_at",
    "ended_at",
    "status_code",
    "success",
    "done_seen",
    "ttfb_ms",
    "total_latency_ms",
    "chunk_count",
    "bytes_received",
    "error_type",
    "error_message",
]


@dataclass
class RequestResult:
    run_id: str
    concurrency: int
    user_id: int
    request_id: int
    prompt_chars: int
    started_at: str
    ended_at: str
    status_code: int | None
    success: bool
    done_seen: bool
    ttfb_ms: float | None
    total_latency_ms: float
    chunk_count: int
    bytes_received: int
    error_type: str
    error_message: str


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def build_url(base_url: str, endpoint: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", endpoint.lstrip("/"))


async def check_health(client: httpx.AsyncClient, health_url: str | None) -> dict[str, Any]:
    if not health_url:
        return {"enabled": False}

    started = time.perf_counter()
    try:
        response = await client.get(health_url)
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "enabled": True,
            "ok": response.is_success,
            "status_code": response.status_code,
            "latency_ms": round(latency_ms, 3),
            "error": "",
        }
    except httpx.HTTPError as exc:
        latency_ms = (time.perf_counter() - started) * 1000
        return {
            "enabled": True,
            "ok": False,
            "status_code": None,
            "latency_ms": round(latency_ms, 3),
            "error": type(exc).__name__,
        }


async def run_one_request(
    client: httpx.AsyncClient,
    *,
    run_id: str,
    url: str,
    prompt: str,
    concurrency: int,
    user_id: int,
    request_id: int,
) -> RequestResult:
    started_perf = time.perf_counter()
    started_at = utc_now_iso()
    status_code: int | None = None
    ttfb_ms: float | None = None
    chunk_count = 0
    bytes_received = 0
    done_seen = False
    error_type = ""
    error_message = ""

    try:
        async with client.stream("POST", url, json={"userMessage": prompt}) as response:
            status_code = response.status_code
            async for line in response.aiter_lines():
                if ttfb_ms is None:
                    ttfb_ms = (time.perf_counter() - started_perf) * 1000
                if not line:
                    continue

                encoded_line = line.encode("utf-8")
                bytes_received += len(encoded_line) + 1
                chunk_count += 1

                if line.strip() == "data: [DONE]":
                    done_seen = True

            if not response.is_success:
                error_type = "http_status"
                error_message = f"HTTP {response.status_code}"
            elif not done_seen:
                error_type = "incomplete_stream"
                error_message = "stream ended without data: [DONE]"
    except httpx.TimeoutException as exc:
        error_type = "timeout"
        error_message = str(exc) or type(exc).__name__
    except httpx.ConnectError as exc:
        error_type = "connect_error"
        error_message = str(exc) or type(exc).__name__
    except httpx.HTTPError as exc:
        error_type = type(exc).__name__
        error_message = str(exc)

    ended_at = utc_now_iso()
    total_latency_ms = (time.perf_counter() - started_perf) * 1000
    success = bool(status_code and 200 <= status_code < 300 and done_seen and not error_type)

    return RequestResult(
        run_id=run_id,
        concurrency=concurrency,
        user_id=user_id,
        request_id=request_id,
        prompt_chars=len(prompt),
        started_at=started_at,
        ended_at=ended_at,
        status_code=status_code,
        success=success,
        done_seen=done_seen,
        ttfb_ms=round(ttfb_ms, 3) if ttfb_ms is not None else None,
        total_latency_ms=round(total_latency_ms, 3),
        chunk_count=chunk_count,
        bytes_received=bytes_received,
        error_type=error_type,
        error_message=error_message[:500],
    )


async def run_user(
    client: httpx.AsyncClient,
    *,
    run_id: str,
    url: str,
    prompt: str,
    concurrency: int,
    user_id: int,
    requests_per_user: int,
) -> list[RequestResult]:
    results: list[RequestResult] = []
    for request_index in range(requests_per_user):
        results.append(
            await run_one_request(
                client,
                run_id=run_id,
                url=url,
                prompt=prompt,
                concurrency=concurrency,
                user_id=user_id,
                request_id=(user_id * requests_per_user) + request_index,
            )
        )
    return results


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * pct
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return round(sorted_values[lower], 3)
    fraction = index - lower
    interpolated = sorted_values[lower] + (
        (sorted_values[upper] - sorted_values[lower]) * fraction
    )
    return round(interpolated, 3)


def summarize_results(results: list[RequestResult]) -> dict[str, Any]:
    by_concurrency: dict[int, list[RequestResult]] = {}
    for result in results:
        by_concurrency.setdefault(result.concurrency, []).append(result)

    summaries: list[dict[str, Any]] = []
    for concurrency, group in sorted(by_concurrency.items()):
        successful = [result for result in group if result.success]
        latencies = [result.total_latency_ms for result in successful]
        ttfbs = [result.ttfb_ms for result in successful if result.ttfb_ms is not None]
        error_counts: dict[str, int] = {}
        for result in group:
            if result.success:
                continue
            error_counts[result.error_type or "unknown"] = (
                error_counts.get(result.error_type or "unknown", 0) + 1
            )

        started_values = [datetime.fromisoformat(result.started_at) for result in group]
        ended_values = [datetime.fromisoformat(result.ended_at) for result in group]
        wall_seconds = max(
            (max(ended_values) - min(started_values)).total_seconds(),
            0.001,
        )

        summaries.append(
            {
                "concurrency": concurrency,
                "requests": len(group),
                "successes": len(successful),
                "failures": len(group) - len(successful),
                "success_rate": round(len(successful) / len(group), 4) if group else 0.0,
                "throughput_requests_per_second": round(len(group) / wall_seconds, 3),
                "latency_ms": {
                    "mean": round(statistics.fmean(latencies), 3) if latencies else None,
                    "p50": percentile(latencies, 0.50),
                    "p90": percentile(latencies, 0.90),
                    "p95": percentile(latencies, 0.95),
                    "p99": percentile(latencies, 0.99),
                },
                "ttfb_ms": {
                    "mean": round(statistics.fmean(ttfbs), 3) if ttfbs else None,
                    "p50": percentile(ttfbs, 0.50),
                    "p90": percentile(ttfbs, 0.90),
                    "p95": percentile(ttfbs, 0.95),
                    "p99": percentile(ttfbs, 0.99),
                },
                "error_counts": error_counts,
            }
        )

    return {"by_concurrency": summaries}


def write_csv(path: Path, results: list[RequestResult]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


async def run_load_test(args: argparse.Namespace) -> dict[str, Path]:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target_url = build_url(args.base_url, args.endpoint)
    health_url = args.health_url
    if health_url is None and args.health_endpoint:
        health_url = build_url(args.base_url, args.health_endpoint)

    max_connections = max(args.concurrency_levels)
    timeout = httpx.Timeout(
        connect=args.connect_timeout,
        read=args.read_timeout,
        write=args.connect_timeout,
        pool=args.connect_timeout,
    )
    limits = httpx.Limits(
        max_connections=max_connections,
        max_keepalive_connections=max_connections,
    )

    all_results: list[RequestResult] = []
    health_checks: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=timeout, limits=limits) as client:
        for concurrency in args.concurrency_levels:
            before = await check_health(client, health_url)
            before.update({"concurrency": concurrency, "phase": "before"})
            health_checks.append(before)

            started = time.perf_counter()
            user_tasks = [
                run_user(
                    client,
                    run_id=run_id,
                    url=target_url,
                    prompt=args.prompt,
                    concurrency=concurrency,
                    user_id=user_id,
                    requests_per_user=args.requests_per_user,
                )
                for user_id in range(concurrency)
            ]
            grouped_results = []
            progress = tqdm(
                asyncio.as_completed(user_tasks),
                total=len(user_tasks),
                desc=f"concurrency={concurrency}",
                unit="user",
            )
            for completed_task in progress:
                grouped_results.append(await completed_task)
            level_results = [
                result for user_results in grouped_results for result in user_results
            ]
            all_results.extend(level_results)
            elapsed = time.perf_counter() - started

            after = await check_health(client, health_url)
            after.update(
                {
                    "concurrency": concurrency,
                    "phase": "after",
                    "level_wall_seconds": round(elapsed, 3),
                }
            )
            health_checks.append(after)

            successes = sum(1 for result in level_results if result.success)
            print(
                f"concurrency={concurrency} requests={len(level_results)} "
                f"successes={successes} failures={len(level_results) - successes} "
                f"wall_seconds={elapsed:.3f}"
            )

    csv_path = output_dir / "chat_stream_results.csv"
    summary_path = output_dir / "chat_stream_summary.json"
    write_csv(csv_path, all_results)

    summary = {
        "run_id": run_id,
        "target_url": target_url,
        "prompt_chars": len(args.prompt),
        "requests_per_user": args.requests_per_user,
        "concurrency_levels": args.concurrency_levels,
        "generated_at": utc_now_iso(),
        "health_checks": health_checks,
        **summarize_results(all_results),
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    return {"csv": csv_path, "summary": summary_path}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stress test the LLM backend POST /chat/stream endpoint."
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--endpoint", default="/chat/stream")
    parser.add_argument("--health-endpoint", default="/healthz")
    parser.add_argument(
        "--health-url",
        default=None,
        help="Override the health URL. Use an empty string to disable health checks.",
    )
    parser.add_argument(
        "--concurrency-levels",
        type=int,
        nargs="+",
        default=[30, 60, 100],
    )
    parser.add_argument("--requests-per-user", type=int, default=1)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--connect-timeout", type=float, default=10.0)
    parser.add_argument("--read-timeout", type=float, default=120.0)
    parser.add_argument("--output-dir", default="stress_results")
    args = parser.parse_args()

    if args.health_url == "":
        args.health_url = None
        args.health_endpoint = None
    if any(level < 1 for level in args.concurrency_levels):
        parser.error("--concurrency-levels must contain positive integers")
    if args.requests_per_user < 1:
        parser.error("--requests-per-user must be positive")

    return args


def main() -> None:
    paths = asyncio.run(run_load_test(parse_args()))
    print(f"wrote {paths['csv']}")
    print(f"wrote {paths['summary']}")


if __name__ == "__main__":
    main()
