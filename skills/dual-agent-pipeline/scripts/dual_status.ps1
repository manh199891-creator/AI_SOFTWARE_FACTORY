param([Parameter(Mandatory=$true)][string]$Project,[switch]$AsJson)
. (Join-Path $PSScriptRoot "dual_paths.ps1")
$paths = Get-DualAgentPaths
$aliases = @{ "revit"="RevitAddinSolution"; "navis"="NavisAddinSolution"; "trend"="TrendingUpdate"; "factory"="factory" }
$projectName = if ($aliases.ContainsKey($Project)) { $aliases[$Project] } else { $Project }
$projectRoot = if ($projectName -eq "factory") { $paths.FactoryRoot } else { Join-Path $paths.FactoryRoot $projectName }
$authorityPath = Join-Path $projectRoot ".agent\state\pipeline_status.json"
$manifestPath = Join-Path $projectRoot ".agent\state\review_run.json"
$checkpointPath = Join-Path $projectRoot ".agent\state\writer_checkpoint.json"
$authority = if (Test-Path $authorityPath) { Get-Content -Raw $authorityPath | ConvertFrom-Json } else { $null }
$manifest = if (Test-Path $manifestPath) { Get-Content -Raw $manifestPath | ConvertFrom-Json } else { $null }
$checkpoint = if (Test-Path $checkpointPath) { Get-Content -Raw $checkpointPath | ConvertFrom-Json } else { $null }
$desync = $false; $desyncReason = ""
if (-not $authority -or [int]$authority.status_version -ne 2) { $desync=$true; $desyncReason="PIPELINE_STATUS_V2_REQUIRED" }
elseif ($manifest -and $authority.run_id -and $manifest.run_id -and [string]$authority.run_id -ne [string]$manifest.run_id) { $desync=$true; $desyncReason="REVIEW_RUN_ID_MISMATCH" }
elseif ($manifest -and $authority.snapshot_hash -and $manifest.snapshot_hash -and [string]$authority.snapshot_hash -ne [string]$manifest.snapshot_hash) { $desync=$true; $desyncReason="REVIEW_SNAPSHOT_MISMATCH" }
elseif ($checkpoint -and [string]$checkpoint.task_id -ne [string]$authority.task_id) { $desync=$true; $desyncReason="CHECKPOINT_TASK_MISMATCH" }
elseif ($checkpoint -and $authority.writer_checkpoint_id -and [string]$checkpoint.checkpoint_id -ne [string]$authority.writer_checkpoint_id) { $desync=$true; $desyncReason="CHECKPOINT_ID_MISMATCH" }
elseif ($checkpoint -and $authority.writer_checkpoint_id -and $authority.snapshot_hash -and [string]$checkpoint.snapshot_hash -ne [string]$authority.snapshot_hash) { $desync=$true; $desyncReason="CHECKPOINT_SNAPSHOT_MISMATCH" }
$result = if ($desync) {
  [ordered]@{ project=$projectName; status="STATE_DESYNC"; terminal=$true; reason_code=$desyncReason; ANTI_PHASE="UNKNOWN"; ANTI_PROGRESS="0/0"; ANTI_STATUS="UNKNOWN"; LAST_CHECKPOINT=""; READY_FOR_CODEX="NO"; CODEX_STATUS="BLOCKED"; NEXT_ACTION="Repair authoritative state" }
} else {
  $codexStatus = if ($manifest) { [string]$manifest.status } else { "NOT_STARTED" }
  [ordered]@{
    project=$projectName; status=[string]$authority.status; terminal=[bool]$authority.terminal; reason_code=[string]$authority.reason_code
    ANTI_PHASE=[string]$authority.lifecycle_phase; ANTI_PROGRESS="$($authority.work_item_current)/$($authority.work_item_total)"
    ANTI_STATUS=[string]$authority.writer_status; LAST_CHECKPOINT=[string]$authority.writer_checkpoint_id
    READY_FOR_CODEX=$(if ([bool]$authority.ready_for_codex) { "YES" } else { "NO" })
    CODEX_STATUS=$codexStatus; NEXT_ACTION=[string]$authority.next_action
    run_id=[string]$authority.run_id; snapshot_hash=[string]$authority.snapshot_hash
    phase_review_count=[int]$authority.phase_review_count; failure_budget_remaining=[int]$authority.failure_budget_remaining
  }
}
if ($AsJson) { $result | ConvertTo-Json -Compress } else {
  Write-Output "Status: $($result.status)"; Write-Output "Terminal: $($result.terminal)"
  Write-Output "ANTI_PHASE: $($result.ANTI_PHASE)"; Write-Output "ANTI_PROGRESS: $($result.ANTI_PROGRESS)"; Write-Output "ANTI_STATUS: $($result.ANTI_STATUS)"
  Write-Output "LAST_CHECKPOINT: $($result.LAST_CHECKPOINT)"; Write-Output "READY_FOR_CODEX: $($result.READY_FOR_CODEX)"; Write-Output "CODEX_STATUS: $($result.CODEX_STATUS)"; Write-Output "NEXT_ACTION: $($result.NEXT_ACTION)"; Write-Output "PIPELINE_STATUS: $($result.status)"
}
if ($result.status -eq "PASS") { exit 0 }; if ($result.terminal) { exit 2 }; exit 0
