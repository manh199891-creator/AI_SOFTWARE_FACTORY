param(
    [Parameter(Mandatory=$true)][string]$Project
)

. (Join-Path $PSScriptRoot "dual_paths.ps1")
$paths = Get-DualAgentPaths
$factoryRoot = $paths.FactoryRoot

$aliases = @{
    "revit" = "RevitAddinSolution"
    "navis" = "NavisAddinSolution"
    "trend" = "TrendingUpdate"
}

$projectName = if ($aliases.ContainsKey($Project)) { $aliases[$Project] } else { $Project }
$projectRoot = Join-Path $factoryRoot $projectName

$reports = @(
    "DUAL_AGENT_REPORT.md",
    "CODEX_REVIEW.md",
    "FIXER_HANDOFF.md",
    "CONVERGENCE_REPORT.md",
    "RELEASE_GATE_REPORT.md"
)

$checkpointPath = Join-Path $projectRoot ".agent\state\writer_checkpoint.json"
if (Test-Path $checkpointPath) {
    Write-Output "--- writer_checkpoint.json ---"
    $checkpoint = Get-Content -Raw $checkpointPath | ConvertFrom-Json
    Write-Output "Checkpoint: $($checkpoint.checkpoint_id) $($checkpoint.status) $($checkpoint.work_item_current)/$($checkpoint.work_item_total)"
}

foreach ($report in $reports) {
    $path = Join-Path $projectRoot ".agent\reports\$report"
    if (Test-Path $path) {
        Write-Output "--- $report ---"
        Write-Output "Path: $path"
        
        $content = Get-Content $path
        $summary = $content | Where-Object { $_ -match "^## Status:" -or $_ -match "^## Summary:" }
        if ($summary) {
            Write-Output $summary
        } else {
            $firstLines = $content | Where-Object { $_.Trim() -ne "" } | Select-Object -First 2
            Write-Output $firstLines
        }
        Write-Output ""
    }
}
