#!/usr/bin/env bash
set -e

echo "=========================================================="
echo "       Intelligent API Gateway - Startup Manager          "
echo "=========================================================="

# 1. Check Docker
echo "[1/5] Checking Docker daemon status..."
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker is not running or is paused!"
    echo "Please ensure Docker Desktop is started and unpaused."
    exit 1
fi
echo "  -> Docker is running."

# 2. Build & run compose
echo "[2/5] Starting containers with Docker Compose..."
docker compose up -d --build

# 3. Wait for services
echo "[3/5] Waiting for services to become healthy..."
wait_for() {
    local url=$1
    local name=$2
    for _ in $(seq 1 30); do
        if curl -s -f "$url" >/dev/null 2>&1; then
            echo "  -> $name is ready ($url)"
            return 0
        fi
        sleep 1
    done
    echo "  -> WARNING: $name timed out"
    return 1
}

wait_for "http://localhost:8000/health" "API Gateway"
wait_for "http://localhost:8001/health" "Simulated Paid API"
wait_for "http://localhost:9090/-/healthy" "Prometheus"
wait_for "http://localhost:3001/api/health" "Grafana"

# 4. Generate traffic
echo "[4/5] Sending initial test traffic to populate Grafana metrics..."
if command -v python3 >/dev/null 2>&1; then
    python3 generate_traffic.py --cycles 2 --delay 0.5
elif command -v python >/dev/null 2>&1; then
    python generate_traffic.py --cycles 2 --delay 0.5
fi

# 5. Summary
echo ""
echo "=========================================================="
echo "           All Services are UP and Running!               "
echo "=========================================================="
echo "  * Grafana Dashboard:  http://localhost:3001/d/api_gateway_demo"
echo "                        (Login: admin / admin)"
echo "  * API Gateway:        http://localhost:8000"
echo "  * API Documentation:  http://localhost:8000/docs"
echo "  * Prometheus:         http://localhost:9090"
echo "  * Simulator API:      http://localhost:8001"
echo "=========================================================="
echo ""
