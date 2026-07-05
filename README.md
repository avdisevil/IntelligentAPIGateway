# API Gateway

A production-grade async API gateway built with FastAPI. Designed around three concerns: **access control**, **cost reduction via caching and request coalescing**, and **adaptive rate limiting** driven by live traffic analysis.

---

## Architecture

Requests pass through a layered middleware stack before reaching any downstream service. Each layer has a single responsibility and fails gracefully when its backing store is unavailable.

```
Client Request
      │
      ▼
┌─────────────────────┐
│  MetricsMiddleware  │  → Records latency + status for every request (Prometheus)
├─────────────────────┤
│  AuthMiddleware     │  → Validates X-Api-Key. Injects key metadata into request state.
│                     │    Returns 503 on Redis failure (fail-closed).
├─────────────────────┤
│  RateLimitMiddleware│  → Token bucket enforced via Lua script in Redis.
│                     │    Reads key metadata from request state. Fail-open on error.
├─────────────────────┤
│  ResponseCache      │  → Serves cached GET responses. Stale-While-Revalidate (SWR)
│  Middleware         │    in background. Bypasses on Redis error.
├─────────────────────┤
│  CoalescingMiddleware│  → Collapses identical concurrent GET requests into one
└─────────────────────┘
      │
      ▼
 Downstream / Proxy
```

### Component Map

```
gateway/
├── main.py                  # App factory, lifespan, middleware registration
├── config.py                # Settings via pydantic-settings (env-driven)
├── auth/
│   ├── middleware.py        # AuthMiddleware: extracts + validates API keys
│   ├── logic.py             # extract_api_key(), authenticate_key()
│   ├── repository.py        # Redis-backed API key store (JSON serialized)
│   └── models.py            # APIKeyMetadata: plan_name, default_qps, burst_capacity, hard_max_qps
├── ratelimit/
│   ├── middleware.py        # RateLimitMiddleware: reads app.state.limiter
│   ├── limiter.py           # TokenBucketLimiter: evalsha against Lua script
│   └── lua/token_bucket.lua # Atomic token bucket refill + consume
├── cache/
│   ├── middleware.py        # ResponseCacheMiddleware: SWR, lock-based stampede prevention
│   └── manager.py           # CacheManager: get/set/lock, canonical key generation
├── coalescer/
│   ├── middleware.py        # CoalescingMiddleware: wraps coalescer per GET request
│   ├── manager.py           # RequestCoalescer: in-memory flight deduplication
│   └── engine.py            # Re-export module for RequestCoalescer
├── analyzer/
│   ├── processor.py         # TrafficAnalyzer: background loop, adjusts QPS per key
│   └── stats.py             # StatsCollector: sliding-window counters in Redis
├── metrics/
│   ├── middleware.py        # MetricsMiddleware: per-request Prometheus instrumentation
│   └── collector.py         # All Counter/Histogram definitions
├── admin/
│   ├── router.py            # /admin endpoints: key inspect/upsert, cache inspect, metrics
│   └── security.py          # IPAllowlist dependency (checks X-Forwarded-For)
├── routing/
│   └── router.py            # DownstreamProxy: forwards to simulator via httpx
├── proxy/
│   └── handler.py           # Low-level HTTP forwarding with retry/timeout support
├── benchmark/
│   └── router.py            # Benchmark endpoints: /slow, /cache, /coalesce
├── utils/
│   └── helpers.py           # Utility functions
├── deps.py                  # Dependency injection utilities
├── simulator/
│   └── service.py           # Embedded simulator service (for testing)
└── simulator/ (project root)
    └── main.py              # Standalone simulated paid API service
```

### Shared State via `app.state`

All long-lived objects (Redis client, repo, cache, limiter) are initialized once in the `lifespan` context manager and stored on `app.state`. Middleware fetches them per-request via `getattr(request.app.state, "...", None)`. This avoids duplicate connections and makes dependency injection trivial in tests.

---

## How Rate Limiting Works

### Mechanism

Rate limiting uses a **token bucket** implemented as a Lua script executed atomically inside Redis (`EVALSHA`). Each API key has its own bucket.

Every request calls:
```
EVALSHA <sha> 1 ratelimit:<api_key> <now_ms> <tokens_needed> <capacity> <rate_per_ms>
```

The Lua script:
1. Reads the last-recorded token count and timestamp.
2. Computes elapsed time since the last request.
3. Refills tokens: `new_tokens = min(capacity, stored_tokens + elapsed_ms * rate_per_ms)`.
4. Consumes `tokens_needed` if sufficient tokens exist.
5. Writes the new state atomically.

Returns `1` (allowed) or `0` (denied). The middleware issues a `429` with `Retry-After: 1` on denial and increments `rate_limit_denied_total{api_key=...}`.

### Adaptive Adjustment

A `TrafficAnalyzer` background loop runs every second. For each active API key it computes **burstiness**:

```python
burstiness = rps_last_1s / max(rps_avg_60s, 0.1)
```

| Condition | Action |
|---|---|
| `burstiness > 2.0` | Reduce `default_qps` by 20% (floor: 1) |
| `burstiness < 1.2` and `qps < hard_max_qps` | Increase `default_qps` by 10% (ceil: `hard_max_qps`) |

A **10-second cooldown** per key prevents thrashing. The adjusted `default_qps` is persisted back to Redis so subsequent requests immediately see the new limit.

The hard cap (`hard_max_qps`) is never exceeded regardless of traffic pattern. Normal traffic recovers automatically without operator intervention.

---

## How Request Coalescing Saves Cost

The `RequestCoalescer` deduplicates identical concurrent GET requests before they hit the downstream service.

### Mechanism

```python
# Canonical hash: MD5(method + url + body)
request_hash = coalescer.generate_hash("GET", "https://api.example.com/data", b"")

# First arrival creates a Future and executes the real request.
# All subsequent arrivals with the same hash await the same Future.
result = await coalescer.coalesce(request_hash, execute_request)
```

The coalescing window (`window_ms=100` by default) is a deliberate sleep before executing the downstream call. This gives concurrent arrivals time to register before the one real call is made.

### Cost Impact

```
Without coalescing: 50 concurrent identical requests → 50 downstream calls
With coalescing:    50 concurrent identical requests → 1 downstream call
```

For paid APIs billed per call, this is a direct cost multiplier. Tracked via:

- `batch_calls_total` — number of unique downstream calls made
- `batch_saved_total` — number of requests served from an in-flight result

### Interaction with Cache

The full request lifecycle for a cacheable GET:

```
Request arrives
    │
    ├─ Cache HIT (fresh)   → return immediately, X-Cache: HIT
    ├─ Cache HIT (stale)   → return stale immediately, refresh in background, X-Cache: STALE
    ├─ Cache MISS          → pass to Coalescer
    │       │
    │       ├─ In-flight exists  → await existing Future (no downstream call)
    │       └─ No in-flight      → call downstream, cache result, resolve Future
    └─ Non-GET             → bypass both layers entirely
```

---

## Running the Gateway

### Prerequisites

- Python 3.10+
- Redis 7+ (or Docker)

### With Docker Compose

```bash
git clone <repo>
cd API_Gateway_v2
docker-compose up --build
```

The gateway is available at `http://localhost:8000`.  
Redis is available at `localhost:6379`.

### Manual Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
source .venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt

# Start Redis (if not using Docker)
redis-server

# Start the gateway
uvicorn gateway.main:app --reload --port 8000
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `ENVIRONMENT` | `development` | Runtime environment tag |
| `DEBUG` | `True` | Enable debug logging |

Place overrides in a `.env` file at the project root.

---

## API Key Management

Keys are stored in Redis under `apikey:<key>`. Metadata includes the rate limit plan.

### Provision a key via the Admin API

The admin API is restricted to `127.0.0.1` by IP allowlist.

```bash
# Create or update a key
curl -X POST http://localhost:8000/admin/keys/my-key-001 \
  -H "Content-Type: application/json" \
  -d '{
    "plan_name": "standard",
    "default_qps": 10,
    "burst_capacity": 20,
    "hard_max_qps": 50
  }'

# Inspect a key
curl http://localhost:8000/admin/keys/my-key-001

# View live metrics summary
curl http://localhost:8000/admin/metrics/summary
```

---

## Example `curl` Commands

### Health check

```bash
curl http://localhost:8000/health
# {"status":"healthy"}
```

### Authenticated request

```bash
curl http://localhost:8000/proxy/process \
  -X POST \
  -H "X-Api-Key: my-key-001" \
  -H "Content-Type: application/json" \
  -d '{"data": "hello"}'
```

### Trigger rate limiting

```bash
# Hammer the endpoint — 429 after burst_capacity is exhausted
for i in $(seq 1 30); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/proxy/process \
    -H "X-Api-Key: my-key-001" \
    -H "Content-Type: application/json" \
    -d '{"data": "ping"}'
done
```

### Observe cache behaviour

```bash
# First request: MISS (cold cache)
curl -v http://localhost:8000/simulator/data | grep X-Cache
# X-Cache: MISS

# Second request: HIT
curl -v http://localhost:8000/simulator/data | grep X-Cache
# X-Cache: HIT

# After soft TTL, next request serves stale immediately and revalidates
# X-Cache: STALE
```

### Inspect a cache entry

```bash
# Generate the cache key (MD5 of the normalized URL)
python - <<'EOF'
import hashlib
from urllib.parse import urlencode, parse_qsl, urlparse
url = "http://localhost:8000/simulator/data"
parsed = urlparse(url)
q = urlencode(sorted(parse_qsl(parsed.query)))
norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{q}"
print("cache:" + hashlib.md5(norm.encode()).hexdigest())
EOF

# Then fetch it from the admin API
curl http://localhost:8000/admin/cache/cache:<hash_from_above>
```

### Prometheus metrics

```bash
curl http://localhost:8000/metrics | grep -E 'gateway_|cache_|batch_|rate_limit'
```

---

## Load Testing

Install [hey](https://github.com/rakyll/hey) or [vegeta](https://github.com/tsenart/vegeta).

### Measure coalescing effectiveness (hey)

```bash
# 200 concurrent requests to the same endpoint
hey -n 200 -c 50 \
  -m GET \
  -H "X-Api-Key: my-key-001" \
  http://localhost:8000/simulator/data

# Compare batch_saved_total before and after:
curl -s http://localhost:8000/admin/metrics/summary
```

### Sustained rate limit test (vegeta)

```bash
echo 'POST http://localhost:8000/proxy/process' | \
  vegeta attack \
    -header "X-Api-Key: my-key-001" \
    -header "Content-Type: application/json" \
    -body '{"data":"load"}' \
    -rate 20/s \
    -duration 30s | \
  vegeta report
```

Expected: `429` responses appear once burst is exhausted; rate recovers as tokens refill. Observe `rate_limit_denied_total` in `/metrics`.

### Watch adaptive throttling in action

```bash
# Start a high-rate burst (above burst_threshold) for 10s, then back off
# The analyzer will detect the burst and reduce default_qps within ~2s
# After traffic subsides it will gradually recover over the next ~60s

# Check what the analyzer did to the key:
curl http://localhost:8000/admin/keys/my-key-001
```

---

## Observability

All metrics are exposed at `/metrics` in Prometheus text format.

| Metric | Type | Labels |
|---|---|---|
| `gateway_requests_total` | Counter | `endpoint`, `status`, `api_key` |
| `gateway_request_duration_seconds` | Histogram | `endpoint` |
| `rate_limit_denied_total` | Counter | `api_key` |
| `cache_hit_total` | Counter | — |
| `cache_miss_total` | Counter | — |
| `cache_swr_hit_total` | Counter | — |
| `batch_calls_total` | Counter | — |
| `batch_saved_total` | Counter | — |
| `simulated_cost_total` | Counter | — |

To wire up Grafana, uncomment the relevant service block in `docker-compose.yml` and point it at `http://gateway:8000/metrics`.
