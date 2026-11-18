<#
.SYNOPSIS
    Launches the 4 trip-planner-a2a agents locally, each in its own PowerShell
    window, wired together without needing a deployed AWS environment.

.DESCRIPTION
    agentcore dev locks every A2A agent to port 9000, so FlightsAgent,
    WeatherAgent and HotelsAgent can't run side by side through it. This
    script bypasses that by invoking each specialist's "python main.py"
    directly, giving WeatherAgent and HotelsAgent a different A2A_PORT.

    OrchestratorAgent is HTTP (not A2A), so it has no port-9000 conflict and
    is launched through "agentcore dev" itself (--skip-deploy, no --logs) so
    you get AgentCore's normal local web chat UI, with FLIGHTS_AGENT_URL /
    WEATHER_AGENT_URL / HOTELS_AGENT_URL pointed at the other three's local
    URLs.

    TripPlannerGateway (AgentCore Gateway) cannot be deployed from this account yet, so
    dev/local_gateway.py stands in for it on port 8090: it validates the Cognito OAuth
    token (CUSTOM_JWT settings read from agentcore.json) and serves the TravelTips tools.
    OrchestratorAgent gets GATEWAY_URL pointing at it, and fetches its OAuth token using the
    client id/secret that "agentcore add gateway" stored (encrypted) in agentcore/.env.local.

    GEMINI_API_KEY is read from agentcore/.env.local (see README.md).

.PARAMETER FreePorts
    Stop whatever is still listening on the ports this script uses (a previous run). Without it,
    the script refuses to start when one of them is busy, because a leftover process would keep
    serving old code while the new one fails to bind.

.EXAMPLE
    .\dev-all.ps1

.EXAMPLE
    .\dev-all.ps1 -FreePorts
#>

param([switch]$FreePorts)

$root = $PSScriptRoot
$envLocalPath = Join-Path $root "agentcore\.env.local"

if (-not (Test-Path $envLocalPath)) {
    Write-Error "agentcore/.env.local not found. Create it with GEMINI_API_KEY=<your-key>."
    exit 1
}

$geminiKeyLine = Get-Content $envLocalPath | Where-Object { $_ -match '^GEMINI_API_KEY=' } | Select-Object -First 1
if (-not $geminiKeyLine) {
    Write-Error "GEMINI_API_KEY not found in agentcore/.env.local."
    exit 1
}
$geminiKey = ($geminiKeyLine -replace '^GEMINI_API_KEY=', '').Trim().Trim('"')

# "agentcore add credential" re-encrypts secrets in .env.local (enc:v1:...). agentcore dev can
# decrypt them, but the specialists here run as plain "python main.py" and would send the
# ciphertext to Gemini as if it were the key.
if ($geminiKey -like 'enc:v1:*') {
    Write-Error "GEMINI_API_KEY in agentcore/.env.local is encrypted. Put your plaintext key on that line (keep the AGENTCORE_CREDENTIAL_GEMINI line as the CLI wrote it)."
    exit 1
}

$devPorts = 8080, 8081, 8090, 9000, 9001, 9002

function Get-PortHolders {
    Get-NetTCPConnection -LocalPort $devPorts -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
        $ownerPid = $_.OwningProcess
        $alive = Get-CimInstance Win32_Process -Filter "ProcessId=$ownerPid" -ErrorAction SilentlyContinue
        # A dead owner means a surviving child (e.g. uvicorn --reload's worker) kept the socket.
        $holderPids = if ($alive) { @($ownerPid) } else {
            @(Get-CimInstance Win32_Process | Where-Object { $_.ParentProcessId -eq $ownerPid } | ForEach-Object { $_.ProcessId })
        }
        [pscustomobject]@{ Port = $_.LocalPort; OwnerPid = $ownerPid; HolderPids = $holderPids }
    }
}

$holders = @(Get-PortHolders)
if ($holders.Count -gt 0 -and $FreePorts) {
    foreach ($h in $holders) {
        foreach ($holderPid in $h.HolderPids) { Stop-Process -Id $holderPid -Force -ErrorAction SilentlyContinue }
        Write-Host "Freed port $($h.Port)"
    }
    Start-Sleep -Seconds 2
    $holders = @(Get-PortHolders)
}
if ($holders.Count -gt 0) {
    foreach ($h in $holders) { Write-Warning ("Port {0} is in use (pid {1})." -f $h.Port, $h.OwnerPid) }
    Write-Error "Ports in use: a previous run is still alive and would keep serving old code. Close its windows or run .\dev-all.ps1 -FreePorts."
    exit 1
}

# Optional FlightPowers credential for the real flights MCP (see README). Without it FlightsAgent
# starts anyway and tells the user that flights are not configured.
function Get-OptionalEnvLocal([string]$Name) {
    $line = Get-Content $envLocalPath | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
    if (-not $line) { return $null }
    $value = ($line -replace "^$Name=", '').Trim().Trim('"')
    if (-not $value) { return $null }
    if ($value -like 'enc:v1:*') {
        Write-Error "$Name in agentcore/.env.local is encrypted. Put the plaintext value on that line."
        exit 1
    }
    return $value
}

$flightsCredentialEnv = @{}
foreach ($name in "FLIGHTS_RAPIDAPI_KEY", "FLIGHTS_MCP_TOKEN") {
    $value = Get-OptionalEnvLocal $name
    if ($value) { $flightsCredentialEnv[$name] = $value }
}
if ($flightsCredentialEnv.Count -eq 0) {
    Write-Warning "No FLIGHTS_RAPIDAPI_KEY / FLIGHTS_MCP_TOKEN in agentcore/.env.local: FlightsAgent will report that flights are not configured."
}

function Start-AgentWindow {
    param(
        [string]$Name,
        [hashtable]$ExtraEnv = @{}
    )

    $dir = Join-Path $root "app\$Name"
    $pythonExe = Join-Path $dir ".venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        Write-Error "$pythonExe not found. Run 'uv sync' in app/$Name first."
        exit 1
    }

    $envSetup = "`$env:GEMINI_API_KEY = '$geminiKey'; "
    foreach ($key in $ExtraEnv.Keys) {
        $envSetup += "`$env:$key = '$($ExtraEnv[$key])'; "
    }

    $command = "$envSetup Set-Location '$dir'; Write-Host '== $Name ==' -ForegroundColor Cyan; .\.venv\Scripts\python.exe main.py"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WindowStyle Normal
    Write-Host "Started $Name"
}

function Start-LocalGatewayWindow {
    $pythonExe = Join-Path $root "app\OrchestratorAgent\.venv\Scripts\python.exe"
    if (-not (Test-Path $pythonExe)) {
        Write-Error "$pythonExe not found. Run 'uv sync' in app/OrchestratorAgent first."
        exit 1
    }
    $command = "Set-Location '$root'; Write-Host '== Local TripPlannerGateway ==' -ForegroundColor Cyan; & '$pythonExe' dev\local_gateway.py --port 8090"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WindowStyle Normal
    Write-Host "Started local TripPlannerGateway"
}

function Start-OrchestratorDevWindow {
    param([hashtable]$ExtraEnv = @{})

    # agentcore dev refuses to run from anywhere but the project root
    # (it errors with "Please run this command from your project root
    # directory" otherwise) — unlike the specialists above, which are
    # invoked as plain python scripts and do need their own directory.
    $envSetup = "`$env:GEMINI_API_KEY = '$geminiKey'; "
    foreach ($key in $ExtraEnv.Keys) {
        $envSetup += "`$env:$key = '$($ExtraEnv[$key])'; "
    }

    # No --logs here on purpose: that flag forces CLI mode and skips the
    # default local web chat UI that "agentcore dev" normally opens.
    # --skip-deploy avoids trying (and failing) to deploy to AWS first.
    $command = "$envSetup Set-Location '$root'; Write-Host '== OrchestratorAgent ==' -ForegroundColor Cyan; agentcore dev --runtime OrchestratorAgent --skip-deploy --port 8080"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $command -WindowStyle Normal
    Write-Host "Started OrchestratorAgent (agentcore dev)"
}

Start-AgentWindow -Name "FlightsAgent" -ExtraEnv $flightsCredentialEnv
Start-Sleep -Seconds 3

Start-AgentWindow -Name "WeatherAgent" -ExtraEnv @{ A2A_PORT = "9001" }
Start-Sleep -Seconds 3

Start-AgentWindow -Name "HotelsAgent" -ExtraEnv @{ A2A_PORT = "9002" }
Start-Sleep -Seconds 3

Start-LocalGatewayWindow
Start-Sleep -Seconds 3

# The OAuth discovery URL is not a secret; take it from the gateway's own CUSTOM_JWT config.
$spec = Get-Content (Join-Path $root "agentcore\agentcore.json") -Raw | ConvertFrom-Json
$gatewaySpec = $spec.agentCoreGateways | Where-Object { $_.name -eq "TripPlannerGateway" }
$discoveryUrl = $gatewaySpec.authorizerConfiguration.customJwtAuthorizer.discoveryUrl

Start-OrchestratorDevWindow -ExtraEnv @{
    FLIGHTS_AGENT_URL            = "http://localhost:9000"
    WEATHER_AGENT_URL            = "http://localhost:9001"
    HOTELS_AGENT_URL             = "http://localhost:9002"
    GATEWAY_URL                  = "http://127.0.0.1:8090/mcp"
    GATEWAY_OAUTH_DISCOVERY_URL  = $discoveryUrl
}

Write-Host ""
Write-Host "Everything is starting in separate windows:" -ForegroundColor Green
Write-Host "  FlightsAgent       -> http://localhost:9000  (raw python, no UI)"
Write-Host "  WeatherAgent       -> http://localhost:9001  (raw python, no UI)"
Write-Host "  HotelsAgent        -> http://localhost:9002  (raw python, no UI)"
Write-Host "  Local gateway      -> http://127.0.0.1:8090/mcp  (Cognito JWT-protected MCP, stands in for AWS)"
Write-Host "  OrchestratorAgent  -> agentcore dev's own web chat UI (opens in your browser)"
Write-Host ""
Write-Host "Wait for the specialist and gateway windows to show they are running before chatting"
Write-Host "with the orchestrator in the UI that agentcore dev opens."
Write-Host "Try: 'Dame consejos para viajar a Cartagena y cuanto son 2000000 COP en USD'."
Write-Host ""
Write-Host "To stop everything, close the 5 PowerShell windows (or Ctrl+C in each)."
