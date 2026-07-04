import asyncio
import logging
import time
from gateway.analyzer.stats import StatsCollector
from gateway.auth.repository import APIKeyRepository
from gateway.auth.models import APIKeyMetadata
from gateway.metrics.collector import gateway_api_key_capacity_qps

logger = logging.getLogger(__name__)

class TrafficAnalyzer:
    """
    Background analyzer that monitors traffic burstiness and adjusts rate limits.
    """
    def __init__(
        self, 
        stats_collector: StatsCollector, 
        repository: APIKeyRepository,
        burst_threshold: float = 2.0,
        cooldown_seconds: int = 10
    ):
        self.stats = stats_collector
        self.repo = repository
        self.burst_threshold = burst_threshold
        self.cooldown_seconds = cooldown_seconds
        self._cooldowns = {} # key -> last_adjustment_ts
        self._running = False

    async def run_loop(self):
        self._running = True
        logger.info("Traffic analyzer loop started")
        while self._running:
            try:
                await self.analyze_once()
            except Exception as e:
                logger.error(f"Error in analyzer loop: {e}")
            await asyncio.sleep(1)

    def stop(self):
        self._running = False

    async def analyze_once(self):
        active_keys = await self.stats.get_active_keys()
        now = time.time()

        for api_key in active_keys:
            # Check cooldown
            if now - self._cooldowns.get(api_key, 0) < self.cooldown_seconds:
                continue

            # Fetch stats concurrently
            rps_1s_task = self.stats.get_stats(api_key, "1s", 1)
            total_60s_task = self.stats.get_stats(api_key, "60s", 60)
            rps_1s, total_60s = await asyncio.gather(rps_1s_task, total_60s_task)
            
            rps_60s = total_60s / 60.0

            # Compute burstiness
            burstiness = rps_1s / max(rps_60s, 0.1)

            # Get current metadata
            metadata = await self.repo.get_key_metadata(api_key)
            if not metadata:
                continue

            # Record current capacity in Prometheus for dashboard
            gateway_api_key_capacity_qps.labels(api_key=api_key).set(metadata.default_qps)

            adjusted = False
            
            # Rule 1: High burstiness -> Throttle
            if burstiness > self.burst_threshold:
                # Reduce refill_rate (default_qps) by 20%, min 1
                new_qps = max(1, int(metadata.default_qps * 0.8))
                if new_qps < metadata.default_qps:
                    metadata.default_qps = new_qps
                    logger.warning(f"Throttling key {api_key} due to burstiness {burstiness:.2f}. New QPS: {new_qps}")
                    adjusted = True

            # Rule 2: Stable & Under Hard Cap -> Gently Increase
            elif burstiness < 1.2 and metadata.default_qps < metadata.hard_max_qps:
                # Recover 10% or at least 1 unit
                new_qps = min(metadata.hard_max_qps, metadata.default_qps + max(1, int(metadata.default_qps * 0.1)))
                if new_qps > metadata.default_qps:
                    metadata.default_qps = new_qps
                    logger.info(f"Recovering key {api_key} QPS to {new_qps}")
                    adjusted = True

            if adjusted:
                await self.repo.store_key_metadata(api_key, metadata)
                self._cooldowns[api_key] = now
