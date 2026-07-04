"""
Standalone simulated paid API service.

Runs as a separate Docker service so the gateway can proxy to it
via a real network hop (simulating an actual third-party API).
"""
import asyncio
import time
from typing import List, Dict, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Simulated Paid API",
    description="Simulates a third-party paid inference API for gateway testing.",
    version="1.0.0",
)


class ProcessRequest(BaseModel):
    data: str
    metadata: Dict[str, Any] = {}


class BatchProcessRequest(BaseModel):
    items: List[ProcessRequest]


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/v1/process")
async def process_single(request: ProcessRequest):
    """Simulates a single paid API call (e.g., an LLM inference call)."""
    latency_ms = request.metadata.get("simulate_latency_ms", 50)
    await asyncio.sleep(latency_ms / 1000.0)

    cost = 0.5  # fixed cost per single call (USD)

    return {
        "id": f"sim_{int(time.time() * 1000)}",
        "result": f"processed: {request.data}",
        "billing": {
            "cost": cost,
            "currency": "USD",
        },
    }


@app.post("/v1/batch")
async def process_batch(request: BatchProcessRequest):
    """Simulates a batched paid API call with volume discount pricing."""
    if not request.items:
        raise HTTPException(status_code=400, detail="Empty batch")

    await asyncio.sleep(0.1)  # slightly higher latency for batch overhead

    # Volume discount: 0.2 base + 0.3 per item (vs 0.5 per item for singles)
    cost = 0.2 + (len(request.items) * 0.3)

    results = [
        {"id": f"sim_b_{i}", "result": f"processed: {item.data}"}
        for i, item in enumerate(request.items)
    ]

    return {
        "batch_id": f"batch_{int(time.time() * 1000)}",
        "results": results,
        "billing": {
            "cost": cost,
            "currency": "USD",
        },
    }
