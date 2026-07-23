[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet("init","run","checkpoint","status","reports","doctor")][string]$Action,
    [Parameter(Mandatory=$true)][string]$Project,
    [string]$TaskId = "", [string]$Feature = "",
    [ValidateSet("research","plan","code","release")][string]$Mode = "code",
    [string]$Allowed = "", [string]$Forbidden = "", [string]$Artifacts = "",
    [ValidateSet("checkpointed","continuous")][string]$ExecutionPolicy = "checkpointed",
    [int]$MaxCycles = 1, [switch]$SkipVerify, [switch]$Force,
    [string]$FixCommand = "", [string]$ResumeHypothesis = ""
)
$ErrorActionPreference = "Stop"
$factoryRoot = if ($env:AI_SOFTWARE_FACTORY_ROOT) { $env:AI_SOFTWARE_FACTORY_ROOT } else { "E:\AI_SOFTWARE_FACTORY" }
$pipelineRoot = Join-Path $factoryRoot "skills\dual-agent-pipeline"
if (-not (Test-Path -LiteralPath $pipelineRoot)) { throw "dual-agent-pipeline missing: $pipelineRoot" }
if ($Action -in @("init","run") -and ([string]::IsNullOrWhiteSpace($TaskId) -or [string]::IsNullOrWhiteSpace($Feature))) { throw "TaskId and Feature are required for $Action" }
switch ($Action) {
  "init" { & (Join-Path $pipelineRoot "scripts\dual_init.ps1") -Project $Project -TaskId $TaskId -Feature $Feature -Mode $Mode -Allowed $Allowed -Forbidden $Forbidden -Artifacts $Artifacts -ExecutionPolicy $ExecutionPolicy -Force:$Force }
  "run" { & (Join-Path $pipelineRoot "scripts\dual_run.ps1") -Project $Project -TaskId $TaskId -Feature $Feature -Mode $Mode -Artifacts $Artifacts -MaxCycles $MaxCycles -SkipVerify:$SkipVerify -FixCommand $FixCommand -ResumeHypothesis $ResumeHypothesis }
  "checkpoint" { & (Join-Path $pipelineRoot "scripts\dual_checkpoint.ps1") -Project $Project }
  "status" { & (Join-Path $pipelineRoot "scripts\dual_status.ps1") -Project $Project }
  "reports" { & (Join-Path $pipelineRoot "scripts\dual_read_reports.ps1") -Project $Project }
  "doctor" { & (Join-Path $pipelineRoot "scripts\dual_doctor.ps1") -Project $Project }
}
exit $LASTEXITCODE
