# Stop and remove the FinAlly container. The finally-data volume is preserved.
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
# PowerShell 7.4+ turns non-zero native exit codes into terminating errors under
# ErrorActionPreference=Stop; the docker inspect probe below relies on exit codes.
$PSNativeCommandUseErrorActionPreference = $false

$Container = "finally"

docker container inspect $Container *> $null
if ($LASTEXITCODE -eq 0) {
    docker rm -f $Container *> $null
    Write-Host "Stopped and removed container $Container (volume finally-data kept)."
} else {
    Write-Host "Container $Container is not present. Nothing to do."
}
