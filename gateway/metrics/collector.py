from prometheus_client import Counter, Histogram, Gauge, make_asgi_app
from starlette.middleware.gzip import GZipMiddleware

# 1. Total requests tracked by endpoint, status, and api_key
gateway_requests_total = Counter(
    "gateway_requests_total",
    "Total number of requests processed by the gateway",
    ["endpoint", "status", "api_key"],
)

# 2. Request duration histogram
gateway_request_duration_seconds = Histogram(
    "gateway_request_duration_seconds",
    "Request duration in seconds",
    ["endpoint"]
)

# 3. Rate limit denials tracked by api_key
rate_limit_denied_total = Counter(
    "rate_limit_denied_total",
    "Total number of requests denied due to rate limiting",
    ["api_key"],
)

# 4. Cache hit/miss counters
cache_hit_total = Counter(
    "cache_hit_total",
    "Total number of cache hits"
)
cache_miss_total = Counter(
    "cache_miss_total",
    "Total number of cache misses"
)

cache_swr_hit_total = Counter(
    "cache_swr_hit_total",
    "Total number of stale-while-revalidate cache hits",
)

# 5. Batching metrics (Coalescer)
batch_calls_total = Counter(
    "batch_calls_total",
    "Total number of batched/coalesced calls"
)
batch_saved_total = Counter(
    "batch_saved_total",
    "Total number of downstream calls saved by batching"
)

# 6. Simulated cost tracker
simulated_cost_total = Counter(
    "simulated_cost_total",
    "Estimated cost of operations in simulated units"
)

# 7. Dynamic capacity tracking (set by analyzer)
gateway_api_key_capacity_qps = Gauge(
    "gateway_api_key_capacity_qps",
    "Current dynamic QPS limit assigned to the API key",
    ["api_key"]
)

# 8. Benchmark specific metrics
gateway_overhead_seconds = Histogram(
    "gateway_overhead_seconds",
    "Gateway overhead in seconds (total duration minus downstream duration)",
    ["endpoint"]
)

active_requests = Gauge(
    "active_requests",
    "Number of concurrent requests currently being processed by the gateway"
)

coalesced_requests_total = Counter(
    "coalesced_requests_total",
    "Total requests processed by the coalescer",
    ["status"]
)

upstream_requests_total = Counter(
    "upstream_requests_total",
    "Total requests forwarded to downstream services",
    ["service", "status"]
)

# ASG I app for /metrics exposure
metrics_app = make_asgi_app(disable_compression=True)

