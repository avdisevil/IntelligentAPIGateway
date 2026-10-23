@echo off
setlocal enabledelayedexpansion

echo ==========================================================
echo        Intelligent API Gateway - Startup Manager
echo ==========================================================

REM 1. Verify Docker Engine
echo [1/5] Checking Docker daemon status...
docker info >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker is not running or is paused!
    echo Please start Docker Desktop or unpause it through the Whale menu.
    pause
    exit /b 1
)
echo   -^> Docker is running.

REM 2. Start containers
echo [2/5] Starting containers with Docker Compose...
docker compose up -d --build
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Docker compose failed to start.
    pause
    exit /b 1
)

REM 3. Wait for services
echo [3/5] Waiting for services to initialize (10s)...
timeout /t 10 /nobreak >nul

REM 4. Seed traffic
echo [4/5] Sending initial test traffic to populate Grafana metrics...
python generate_traffic.py --cycles 2 --delay 0.5

REM 5. Display Dashboard Links
echo.
echo ==========================================================
echo            All Services are UP and Running!
echo ==========================================================
echo   * Grafana Dashboard:  http://localhost:3001/d/api_gateway_demo
echo                         (Login: admin / admin)
echo   * API Gateway:        http://localhost:8000
echo   * API Documentation:  http://localhost:8000/docs
echo   * Prometheus:         http://localhost:9090
echo   * Simulator API:      http://localhost:8001
echo ==========================================================
echo.

:menu
echo Quick Actions:
echo   [1] Send another traffic burst
echo   [2] Start continuous traffic stream
echo   [3] Open Grafana in web browser
echo   [4] Stream Gateway logs
echo   [Q] Exit (containers stay running)
echo.

set /p choice="Enter choice (1-4, Q): "

if /i "%choice%"=="1" (
    python generate_traffic.py --cycles 1
    goto menu
)
if /i "%choice%"=="2" (
    python generate_traffic.py --continuous
    goto menu
)
if /i "%choice%"=="3" (
    start http://localhost:3001/d/api_gateway_demo
    goto menu
)
if /i "%choice%"=="4" (
    docker compose logs -f gateway
    goto menu
)
if /i "%choice%"=="Q" (
    echo Done. Use 'docker compose down' to stop containers.
    exit /b 0
)

echo Invalid choice.
goto menu
