$ErrorActionPreference = "Stop"

$workspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$marketplaceRoot = Join-Path $workspaceRoot "distribution"
$marketplaceFile = Join-Path $marketplaceRoot ".agents\plugins\marketplace.json"

if (-not (Test-Path -LiteralPath $marketplaceFile)) {
    throw "Marketplace manifest was not found: $marketplaceFile"
}

codex plugin marketplace add $marketplaceRoot
if ($LASTEXITCODE -ne 0) {
    throw "Codex could not register the local marketplace."
}

codex plugin add job-application-copilot@job-applications-local
if ($LASTEXITCODE -ne 0) {
    throw "Codex could not install job-application-copilot."
}

Write-Output "Installed job-application-copilot. Start a new Codex chat to load it."
