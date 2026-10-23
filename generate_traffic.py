"""
Traffic generator script for Intelligent API Gateway.
Sends real-time requests to the gateway to demonstrate metrics, caching,
request coalescing, cost simulation, and rate limiting in Grafana.
"""

import sys
import time
import json
import argparse
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

GATEWAY_URL = "http://localhost:8000"
API_KEY = "my-key-001"


def send_request(url: str, method: str = "GET", data: dict = None, api_key: str = API_KEY) -> int:
    req = urllib.request.Request(url, method=method)
    if api_key:
        req.add_header("X-Api-Key", api_key)
    if data:
        req.add_header("Content-Type", "application/json")
        encoded_data = json.dumps(data).encode("utf-8")
    else:
        encoded_data = None

    try:
        with urllib.request.urlopen(req, data=encoded_data, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def generate_traffic_cycle(cycle_num: int = 1):
    print(f"\n[Cycle #{cycle_num}] Generating traffic burst across gateway features...")

    # 1. Cache traffic: 1 Cold MISS + 9 Warm HITS
    print("  -> Testing Caching (/benchmark/cache)...")
    for _ in range(10):
        send_request(f"{GATEWAY_URL}/benchmark/cache")

    # 2. Coalescing traffic: 15 concurrent identical requests
    print("  -> Testing Request Coalescing (/benchmark/coalesce)...")
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [
            executor.submit(send_request, f"{GATEWAY_URL}/benchmark/coalesce")
            for _ in range(15)
        ]
        for f in futures:
            f.result()

    # 3. Simulated paid proxy requests (adds simulated cost)
    print("  -> Testing Paid Proxy & Cost Tracking (/proxy/process)...")
    for i in range(5):
        send_request(
            f"{GATEWAY_URL}/proxy/process",
            method="POST",
            data={"data": f"inference_sample_{cycle_num}_{i}"}
        )

    # 4. Trigger intentional rate limiting burst (exceed burst limit)
    print("  -> Testing Rate Limiting burst (expecting 429s)...")
    denied = 0
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [
            executor.submit(
                send_request,
                f"{GATEWAY_URL}/proxy/process",
                "POST",
                {"data": "rate_burst"},
                "rate-limit-key"
            )
            for _ in range(25)
        ]
        for f in futures:
            code = f.result()
            if code == 429:
                denied += 1
    print(f"  -> Rate limiting successfully triggered {denied} requests with 429")

    print(f"[Cycle #{cycle_num}] Completed! Live metrics published to Prometheus & Grafana.")


def main():
    parser = argparse.ArgumentParser(description="Intelligent API Gateway Traffic Generator")
    parser.add_argument("-c", "--continuous", action="store_true", help="Run continuously every 3 seconds")
    parser.add_argument("-n", "--cycles", type=int, default=1, help="Number of traffic cycles to run (default: 1)")
    parser.add_argument("-d", "--delay", type=float, default=3.0, help="Delay between cycles in seconds (default: 3.0)")
    args = parser.parse_args()

    # Check health first
    try:
        with urllib.request.urlopen(f"{GATEWAY_URL}/health", timeout=3) as resp:
            if resp.status != 200:
                print(f"Warning: Gateway returned status {resp.status}")
    except Exception as e:
        print(f"Error connecting to Gateway at {GATEWAY_URL}: {e}")
        print("Please ensure docker containers are running (`docker compose up -d`).")
        sys.exit(1)

    print("Connected to API Gateway successfully.")
    
    if args.continuous:
        print("Starting continuous traffic generation loop (Ctrl+C to stop)...")
        c = 1
        try:
            while True:
                generate_traffic_cycle(c)
                c += 1
                time.sleep(args.delay)
        except KeyboardInterrupt:
            print("\nStopped continuous traffic generation.")
    else:
        for c in range(1, args.cycles + 1):
            generate_traffic_cycle(c)
            if c < args.cycles:
                time.sleep(args.delay)


if __name__ == "__main__":
    main()
