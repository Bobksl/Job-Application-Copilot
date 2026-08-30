$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "..\workspace-skill-source\job-application-copilot"
$destination = if ($args.Count -gt 0) {
    $args[0]
} else {
    Join-Path $PSScriptRoot "..\.agents\skills\job-application-copilot"
}

if (-not (Test-Path -LiteralPath $source)) {
    throw "Validated skill source was not found: $source"
}

New-Item -ItemType Directory -Force -Path (Join-Path $destination "references") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $destination "agents") | Out-Null
Copy-Item -LiteralPath (Join-Path $source "SKILL.md") -Destination (Join-Path $destination "SKILL.md") -Force
Copy-Item -LiteralPath (Join-Path $source "references\workflow.md") -Destination (Join-Path $destination "references\workflow.md") -Force
Copy-Item -LiteralPath (Join-Path $source "agents\openai.yaml") -Destination (Join-Path $destination "agents\openai.yaml") -Force

Write-Output "Installed workspace skill at $destination"
