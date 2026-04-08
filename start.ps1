# IncidentEnv Startup Script

# 1. Build the environment image (if needed)
docker build -t incident_env:latest .

# 2. Start the environment server in a new window
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\.venv\Scripts\python -m incident_env.server.app --port 8000"

# 3. Wait for server to be ready
Write-Host "Waiting for environment server to start..." -ForegroundColor Cyan
while (!(Test-NetConnection -ComputerName localhost -Port 8000 -InformationLevel Quiet)) { Start-Sleep -Seconds 1 }

# 4. Run the baseline agent
Write-Host "Starting Agent Inference..." -ForegroundColor Green
.\.venv\Scripts\python inference.py
