"""Measure local gateway latency, cache behavior, and duplicate-request savings."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import math
import re
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from collections import Counter


def request(
    method: str,
    url: str,
    *,
    api_key: str | None = None,
    payload: dict | None = None,
    timeout: float = 15.0,
) -> dict:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["X-Api-Key"] = api_key
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            response.read()
            status = response.status
            response_headers = dict(response.headers.items())
            error = None
    except urllib.error.HTTPError as exc:
        exc.read()
        status = exc.code
        response_headers = dict(exc.headers.items())
        error = None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        status = None
        response_headers = {}
        error = str(exc)
    return {
        "status": status,
        "latency_ms": (time.perf_counter() - started) * 1000,
        "headers": {key.lower(): value for key, value in response_headers.items()},
        "error": error,
    }


def run_requests(
    calls: list[tuple[str, str, str | None, dict | None]],
    concurrency: int,
    timeout: float,
) -> dict:
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(
            lambda call: request(
                call[0], call[1], api_key=call[2], payload=call[3], timeout=timeout
            ),
            calls,
        ))
    elapsed = time.perf_counter() - started
    latencies = sorted(result["latency_ms"] for result in results)

    def percentile(value: float) -> float:
        return latencies[max(0, math.ceil(value * len(latencies)) - 1)]

    status_counts = Counter(
        str(result["status"]) if result["status"] is not None else "connection_error"
        for result in results
    )
    return {
        "requests": len(results),
        "elapsed_seconds": round(elapsed, 4),
        "requests_per_second": round(len(results) / elapsed, 2) if elapsed else 0,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 2) if latencies else None,
            "p50": round(percentile(0.50), 2) if latencies else None,
            "p95": round(percentile(0.95), 2) if latencies else None,
            "p99": round(percentile(0.99), 2) if latencies else None,
        },
        "status_counts": dict(status_counts),
        "responses": results,
    }


_METRIC_LINE = re.compile(
    r'^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+0-9.eE]+)$'
)
_LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:\\.|[^"])*)"')


def scrape_metrics(url: str) -> dict[str, list[dict]]:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            text = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"Unable to scrape gateway metrics at {url}: {exc}") from exc

    metrics: dict[str, list[dict]] = {}
    for line in text.splitlines():
        match = _METRIC_LINE.match(line)
        if not match:
            continue
        name, raw_labels, raw_value = match.groups()
        labels = dict(_LABEL.findall(raw_labels or ""))
        metrics.setdefault(name, []).append({
            "labels": labels,
            "value": float(raw_value),
        })
    return metrics


def metric_total(metrics: dict, name: str, required_labels: dict | None = None) -> float:
    required_labels = required_labels or {}
    return sum(
        sample["value"]
        for sample in metrics.get(name, [])
        if all(sample["labels"].get(key) == value
               for key, value in required_labels.items())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument("--backend", default="http://localhost:8001")
    parser.add_argument("--api-key", default="benchmark-key")
    parser.add_argument("--rate-limit-api-key", default="rate-limit-key")
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", help="Optional path for the JSON results.")
    args = parser.parse_args()
    if args.iterations < 1 or args.concurrency < 2:
        parser.error("--iterations must be positive and --concurrency must be at least 2")

    gateway = args.gateway.rstrip("/")
    backend = args.backend.rstrip("/")
    run_id = uuid.uuid4().hex
    result = {
        "run_id": run_id,
        "configuration": {
            "gateway": gateway,
            "backend": backend,
            "iterations": args.iterations,
            "concurrency": args.concurrency,
        },
        "scenarios": {},
        "notes": [
            "Run against an otherwise idle local stack; results depend on host and Docker resources.",
            "Gateway POST passthrough is compared with direct simulator POST using the same 50 ms default workload.",
            "Cache/coalescing compare a warm cache path and one fresh identical-request burst.",
            "Rate-limit counts are observed, not an accuracy score; the adaptive analyzer may change policy during the run.",
        ],
    }

    direct_calls = [
        ("POST", f"{backend}/v1/process", None, {"data": f"direct-{i}"})
        for i in range(args.iterations)
    ]
    gateway_calls = [
        ("POST", f"{gateway}/proxy/process", args.api_key, {"data": f"passthrough-{i}"})
        for i in range(args.iterations)
    ]
    result["scenarios"]["direct_backend"] = run_requests(
        direct_calls, args.concurrency, args.timeout
    )
    result["scenarios"]["gateway_post_passthrough"] = run_requests(
        gateway_calls, args.concurrency, args.timeout
    )

    warm_url = (
        f"{gateway}/proxy/process?"
        + urllib.parse.urlencode({"data": f"cache-{run_id}"})
    )
    cold = request("GET", warm_url, api_key=args.api_key, timeout=args.timeout)
    warm_calls = [("GET", warm_url, args.api_key, None) for _ in range(args.iterations)]
    warm = run_requests(warm_calls, 1, args.timeout)
    result["scenarios"]["cache"] = {
        "cold_request": cold,
        "warm_requests": warm,
        "warm_cache_header_counts": dict(Counter(
            response["headers"].get("x-cache", "missing")
            for response in warm["responses"]
        )),
    }

    coalesce_url = (
        f"{gateway}/proxy/process?"
        + urllib.parse.urlencode({"data": f"coalesce-{run_id}"})
    )
    coalesce_calls = [
        ("GET", coalesce_url, args.api_key, None)
        for _ in range(args.concurrency)
    ]

    def run_coalescing_burst() -> dict:
        burst = run_requests(coalesce_calls, args.concurrency, args.timeout)
        burst["x_cache_header_counts"] = dict(Counter(
            response["headers"].get("x-cache", "missing")
            for response in burst["responses"]
        ))
        return burst

    metrics_url = f"{gateway}/metrics"
    metrics_before = scrape_metrics(metrics_url)
    burst = run_coalescing_burst()
    metrics_after = scrape_metrics(metrics_url)
    coalescing = {
        "measurement": burst,
        "counter_deltas": {
            "upstream_requests_total": metric_total(
                metrics_after, "upstream_requests_total",
                {"service": "simulator", "status": "200"},
            ) - metric_total(
                metrics_before, "upstream_requests_total",
                {"service": "simulator", "status": "200"},
            ),
            "batch_saved_total": metric_total(
                metrics_after, "batch_saved_total"
            ) - metric_total(metrics_before, "batch_saved_total"),
            "coalesced_requests": metric_total(
                metrics_after, "coalesced_requests_total", {"status": "coalesced"}
            ) - metric_total(
                metrics_before, "coalesced_requests_total", {"status": "coalesced"}
            ),
            "cache_hits": metric_total(
                metrics_after, "cache_hit_total"
            ) - metric_total(metrics_before, "cache_hit_total"),
            "cache_misses": metric_total(
                metrics_after, "cache_miss_total"
            ) - metric_total(metrics_before, "cache_miss_total"),
        },
    }
    result["scenarios"]["identical_get_burst"] = coalescing

    rate_calls = [
        ("POST", f"{gateway}/proxy/process", args.rate_limit_api_key,
         {"data": f"rate-{run_id}-{i}"})
        for i in range(args.concurrency)
    ]
    result["scenarios"]["rate_limit_burst"] = run_requests(
        rate_calls, args.concurrency, args.timeout
    )

    rendered = json.dumps(result, indent=2)
    print(rendered)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output_file:
            output_file.write(rendered + "\n")


if __name__ == "__main__":
    main()
