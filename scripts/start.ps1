# scripts/start.ps1
# AutoPilot Template — Windows Startup Script
# Clears WSL2 relay port conflicts, starts Docker services, verifies health.
#
# Usage:  .\scripts\start.ps1
# Why:    On Windows with WSL2, wslrelay.exe can bind to [::1] on ports
#         used by Docker (3001, 8001, etc.), causing ERR_CONNECTION_RESET
#         when browsers resolve "localhost" to IPv6. This script clears
#         that conflict before starting containers.

param(
    [switch]$SkipWSL,       # Skip WSL shutdown (if you know there's no conflict)
    [switch]$NoBuild        # Skip --build flag (faster restart)
)

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AutoPilot Command Center - Starting"   -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# -------------------------------------------------------------------
# Step 1: Clear WSL relay port conflicts
# -------------------------------------------------------------------
if (-not $SkipWSL) {
    Write-Host "`n[1/3] Clearing WSL2 port reservations..." -ForegroundColor Yellow

    # Check if wslrelay is actually holding any of our ports
    $conflictPorts = @(3001, 8001, 5432)
    $hasConflict = $false
    foreach ($port in $conflictPorts) {
        $relay = netstat -ano 2>$null | Select-String "::1\]:$port\s+.*LISTENING"
        if ($relay) {
            $hasConflict = $true
            Write-Host "  Found wslrelay conflict on port $port" -ForegroundColor Red
        }
    }

    if ($hasConflict) {
        Write-Host "  Running wsl --shutdown to clear conflicts..." -ForegroundColor Yellow
        wsl --shutdown 2>$null
        Start-Sleep -Seconds 3
        Write-Host "  WSL2 relay conflicts cleared." -ForegroundColor Green
    } else {
        Write-Host "  No port conflicts detected. Skipping WSL shutdown." -ForegroundColor Green
    }
} else {
    Write-Host "`n[1/3] Skipping WSL check (--SkipWSL flag)." -ForegroundColor Gray
}

# -------------------------------------------------------------------
# Step 2: Start Docker services
# -------------------------------------------------------------------
Write-Host "`n[2/3] Starting Docker services..." -ForegroundColor Yellow

if ($NoBuild) {
    docker compose up -d
} else {
    docker compose up --build -d
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n  ERROR: Docker Compose failed." -ForegroundColor Red
    Write-Host "  Is Docker Desktop running?" -ForegroundColor Red
    Write-Host "  Try: Start Docker Desktop, then re-run this script.`n" -ForegroundColor Yellow
    exit 1
}

# -------------------------------------------------------------------
# Step 3: Wait for frontend to be reachable
# -------------------------------------------------------------------
Write-Host "`n[3/3] Waiting for services to be ready..." -ForegroundColor Yellow

$maxAttempts = 30
$attempt = 0
$ready = $false

do {
    $attempt++
    Start-Sleep -Seconds 2
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:3001" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        # Still starting up — keep waiting
    }

    if ($attempt % 5 -eq 0) {
        Write-Host "  Still waiting... ($attempt/$maxAttempts)" -ForegroundColor Gray
    }
} while ($attempt -lt $maxAttempts)

# -------------------------------------------------------------------
# Result
# -------------------------------------------------------------------
Write-Host ""
if ($ready) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  All services are running!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Dashboard:  http://localhost:3001"          -ForegroundColor White
    Write-Host "  API Docs:   http://localhost:8001/api/docs" -ForegroundColor White
    Write-Host "  Database:   localhost:5432"                  -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "  WARNING: Frontend did not respond"     -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Services may still be starting. Check logs:" -ForegroundColor White
    Write-Host "    docker compose logs frontend"              -ForegroundColor Gray
    Write-Host "    docker compose logs backend"               -ForegroundColor Gray
    Write-Host ""
    Write-Host "  If the issue persists, try:"                 -ForegroundColor White
    Write-Host "    http://127.0.0.1:3001  (bypass DNS)"       -ForegroundColor Gray
    Write-Host ""
}
