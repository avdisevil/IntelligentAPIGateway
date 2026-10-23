# ==============================================================================
# Intelligent API Gateway - Startup & Management Script (PowerShell)
# ==============================================================================

param (
    [switch]$Clean,
    [switch]$NoBuild,
    [switch]$Traffic,
    [switch]$ContinuousTraffic
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "       Intelligent API Gateway - Startup Manager          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Verify Docker Engine is running and unpaused
Write-Host "[1/5] Checking Docker daemon status..." -ForegroundColor Yellow
try {
    $dockerCheck = docker info --format '{{.ServerVersion}}' 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Docker is not ready." -ForegroundColor Red
        Write-Host $dockerCheck -ForegroundColor DarkRed
        Write-Host "If Docker Desktop is paused, please unpause it from the system tray Whale menu." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  -> Docker is running (Engine version $dockerCheck)." -ForegroundColor Green
} catch {
    Write-Host "ERROR: Could not communicate with Docker. Make sure Docker Desktop is started." -ForegroundColor Red
    exit 1
}

# 2. Optional clean-up
if ($Clean) {
    Write-Host "[*] Cleaning old containers and volumes..." -ForegroundColor Yellow
    docker compose down -v --remove-orphans
    Write-Host "  -> Volumes removed." -ForegroundColor Green
}

# 3. Build & start containers
Write-Host "[2/5] Starting containers with Docker Compose..." -ForegroundColor Yellow
$composeArgs = @("compose", "up", "-d")
if (-not $NoBuild) {
    $composeArgs += "--build"
}

& docker @composeArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker compose failed to start." -ForegroundColor Red
    exit 1
}

# 4. Wait for services to be healthy
Write-Host "[3/5] Waiting for services to become healthy..." -ForegroundColor Yellow

function Wait-For-Url {
    param ($Url, $Name, $TimeoutSeconds = 40)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 400) {
                Write-Host "  -> $Name is ready! ($Url)" -ForegroundColor Green
                return $true
            }
        } catch {}
        Start-Sleep -Seconds 1
    }
    Write-Host "  -> WARNING: $Name timed out waiting on $Url" -ForegroundColor Red
    return $false
}

Wait-For-Url "http://localhost:8000/health" "API Gateway"
Wait-For-Url "http://localhost:8001/health" "Simulated Paid API"
Wait-For-Url "http://localhost:9090/-/healthy" "Prometheus"
Wait-For-Url "http://localhost:3001/api/health" "Grafana"

# 5. Seed traffic so Grafana displays data immediately
Write-Host "[4/5] Sending initial test traffic to populate Grafana metrics..." -ForegroundColor Yellow
if (Get-Command python -ErrorAction SilentlyContinue) {
    python generate_traffic.py --cycles 2 --delay 0.5
} else {
    Write-Host "  -> Python not detected on PATH, skipping traffic generator." -ForegroundColor DarkYellow
}

# 6. Display Dashboard Links
Write-Host ""
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "           All Services are UP and Running!               " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  * Grafana Dashboard:  http://localhost:3001/d/api_gateway_demo" -ForegroundColor Cyan
Write-Host "                        (Login: admin / admin)" -ForegroundColor DarkGray
Write-Host "  * API Gateway:        http://localhost:8000" -ForegroundColor Cyan
Write-Host "  * API Documentation:  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "  * Prometheus:         http://localhost:9090" -ForegroundColor Cyan
Write-Host "  * Simulator API:      http://localhost:8001" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
Write-Host ""

if ($ContinuousTraffic) {
    Write-Host "Starting continuous traffic generator (Ctrl+C to stop)..." -ForegroundColor Yellow
    python generate_traffic.py --continuous
    exit 0
}

# Interactive Helper Menu
Write-Host "Quick Actions:" -ForegroundColor Yellow
Write-Host "  [1] Send another traffic burst (keep Grafana graphs moving)"
Write-Host "  [2] Start continuous traffic stream"
Write-Host "  [3] Open Grafana in default web browser"
Write-Host "  [4] Stream Gateway logs (docker compose logs -f gateway)"
Write-Host "  [Q] Exit script (containers remain running in background)"
Write-Host ""

while ($true) {
    $choice = Read-Host "Select option (1-4, Q)"
    switch ($choice.ToUpper()) {
        "1" {
            python generate_traffic.py --cycles 1
        }
        "2" {
            Write-Host "Starting continuous traffic stream... Press Ctrl+C to return to menu." -ForegroundColor Cyan
            try {
                python generate_traffic.py --continuous
            } catch {}
        }
        "3" {
            Start-Process "http://localhost:3001/d/api_gateway_demo"
        }
        "4" {
            docker compose logs -f gateway
        }
        "Q" {
            Write-Host "Exiting. Containers are still running in the background." -ForegroundColor Green
            Write-Host "Run 'docker compose down' whenever you want to stop them." -ForegroundColor DarkGray
            exit 0
        }
        default {
            Write-Host "Invalid option. Choose 1, 2, 3, 4, or Q." -ForegroundColor Red
        }
    }
}
