import asyncio
import time
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from gateway.metrics.collector import simulated_cost_total

router = APIRouter()


class ProcessRequest(BaseModel):
    data: str
    metadata: Dict[str, Any] = {}


class BatchProcessRequest(BaseModel):
    items: List[ProcessRequest]


@router.post("/v1/process")
async def process_single(request: ProcessRequest):
    """Simulates a single paid API call (e.g., LLM inference)."""
    latency_ms = request.metadata.get("simulate_latency_ms", 50)
    await asyncio.sleep(latency_ms / 1000.0)

    cost = 0.5  # Fixed cost per single call

    simulated_cost_total.inc(cost)

    return {
        "id": f"sim_{int(time.time() * 1000)}",
        "result": f"processed: {request.data}",
        "billing": {
            "cost": cost,
            "currency": "USD"
        }
    }


@router.post("/v1/batch")
async def process_batch(request: BatchProcessRequest):
    """Simulates a batched paid API call."""
    if not request.items:
        raise HTTPException(status_code=400, detail="Empty batch")

    await asyncio.sleep(0.1)

    # Batch cost: 0.2 base + 0.3 per item (volume discount vs 0.5 each)
    cost = 0.2 + (len(request.items) * 0.3)

    simulated_cost_total.inc(cost)

    results = [
        {"id": f"sim_b_{i}", "result": f"processed: {item.data}"}
        for i, item in enumerate(request.items)
    ]

    return {
        "batch_id": f"batch_{int(time.time() * 1000)}",
        "results": results,
        "billing": {
            "cost": cost,
            "currency": "USD"
        }
    }
