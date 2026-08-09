# Build (if needed) and run the FinAlly container on http://localhost:8000
# Usage: .\scripts\start_windows.ps1 [-Build] [-NoOpen]
[CmdletBinding()]
param(
    [switch]$Build,
    [switch]$NoOpen
)

$ErrorActionPreference = "Stop"
# PowerShell 7.4+ turns non-zero native exit codes into terminating errors under
# ErrorActionPreference=Stop; the docker inspect probes below rely on exit codes.
$PSNativeCommandUseErrorActionPreference = $false

$Image = "finally:latest"
$Container = "finally"
$Port = "8000"
$Volume = "finally-data"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if (-not (Test-Path ".env")) {
    Write-Host "No .env found. Copying .env.example to .env - add your OPENROUTER_API_KEY."
    Copy-Item ".env.example" ".env"
}

docker image inspect $Image *> $null
$imageExists = ($LASTEXITCODE -eq 0)

if ($Build -or -not $imageExists) {
    Write-Host "Building $Image ..."
    docker build -t $Image .
    if ($LASTEXITCODE -ne 0) { throw "docker build failed" }
}

# Remove any previous container (running or stopped) so this is safe to re-run.
docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Removing existing container $Container ..."
    docker rm -f $Container *> $null
}

Write-Host "Starting $Container ..."
docker run -d `
    --name $Container `
    -p "${Port}:8000" `
    -v "${Volume}:/app/db" `
    --env-file .env `
    --restart unless-stopped `
    $Image *> $null
if ($LASTEXITCODE -ne 0) { throw "docker run failed" }

$Url = "http://localhost:$Port"
Write-Host "FinAlly is starting at $Url"
Write-Host "Logs:  docker logs -f $Container"
Write-Host "Stop:  .\scripts\stop_windows.ps1"

if (-not $NoOpen) {
    Start-Process $Url
}
