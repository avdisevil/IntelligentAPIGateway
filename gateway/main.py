from fastapi import FastAPI, Request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from contextlib import asynccontextmanager
import asyncio
import redis.asyncio as redis

from gateway.config import settings
from gateway.auth.middleware import AuthMiddleware
from gateway.ratelimit.middleware import RateLimitMiddleware
from gateway.metrics.middleware import MetricsMiddleware
from gateway.cache.middleware import ResponseCacheMiddleware
from gateway.coalescer.middleware import CoalescingMiddleware
from gateway.metrics.collector import metrics_app

from gateway.auth.repository import APIKeyRepository
from gateway.analyzer.stats import StatsCollector
from gateway.analyzer.processor import TrafficAnalyzer
from gateway.cache.manager import CacheManager
from gateway.ratelimit.limiter import TokenBucketLimiter
from gateway.simulator.service import router as simulator_router
from gateway.routing.router import DownstreamProxy
from gateway.admin.router import router as admin_router
from gateway.benchmark.router import router as benchmark_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Shared Components Initialization ---
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    repo = APIKeyRepository(redis_client)
    cache = CacheManager(redis_client)
    limiter = TokenBucketLimiter(redis_client)
    stats = StatsCollector(redis_client)
    analyzer = TrafficAnalyzer(stats, repo)
    proxy = DownstreamProxy()

    # Store in app.state for middleware/router access
    app.state.redis = redis_client
    app.state.repo = repo
    app.state.cache = cache
    app.state.limiter = limiter
    app.state.proxy = proxy
    app.state.stats = stats

    # Initialize admin routes (sets app.state references in admin/router.py)
    from gateway.admin.router import init_admin
    init_admin(app)

    # Seed default demo keys if not present
    from gateway.auth.models import APIKeyMetadata
    demo_keys = [
        ("my-key-001", "standard", 20, 30, 100),
        ("benchmark-key", "benchmark_plan", 10000, 10000, 10000),
        ("rate-limit-key", "rate_limit_plan", 10, 15, 50),
    ]
    for key_name, plan, qps, burst, hard_max in demo_keys:
        if not await repo.get_key_metadata(key_name):
            await repo.store_key_metadata(key_name, APIKeyMetadata(
                plan_name=plan,
                default_qps=qps,
                burst_capacity=burst,
                hard_max_qps=hard_max
            ))

    # Start analyzer background loop
    task = asyncio.create_task(analyzer.run_loop())

    yield

    # Cleanup
    analyzer.stop()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass

    await proxy.aclose()

    # Close shared Redis client
    await redis_client.aclose()


app = FastAPI(
    title="Intelligent API Gateway",
    description="A production-grade intelligent API gateway prototype.",
    version="0.1.0",
    lifespan=lifespan
)

# 1. Global Metrics (outermost — captures every request including 4xx/5xx)
app.add_middleware(MetricsMiddleware)

# 2. Authentication (sets request.state.api_key)
app.add_middleware(AuthMiddleware)

# 3. Rate Limiting (depends on context from AuthMiddleware)
app.add_middleware(RateLimitMiddleware)

# 4. Response Cache (intercept GETs after auth and rate limit checks)
app.add_middleware(ResponseCacheMiddleware)

# 5. Request Coalescing (aggregate concurrent identical GETs within 100ms window)
app.add_middleware(CoalescingMiddleware, window_ms=100)

# --- Routes & Routers ---

# Prometheus metrics endpoints (direct route avoids 307 redirect)
@app.get("/metrics", include_in_schema=False)
@app.get("/metrics/", include_in_schema=False)
async def get_metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

app.include_router(simulator_router, prefix="/simulator", tags=["simulator"])
app.include_router(admin_router, prefix="/admin", tags=["admin"])
app.include_router(benchmark_router, prefix="/benchmark", tags=["benchmark"])



@app.get("/")
async def root():
    return {"message": "Intelligent API Gateway is running"}


@app.post("/proxy/process")
@app.get("/proxy/process")
async def proxy_process(request: Request):
    """
    Proxies a request to the simulated paid API.
    Costs are tracked via simulated_cost_total Prometheus counter.
    Support both POST (JSON body) and GET (query param 'data').
    """
    if request.method == "POST":
        body = await request.json()
        data = body.get("data", "echo")
    else:
        data = request.query_params.get("data", "echo")
    
    return await request.app.state.proxy.forward_process(data)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
