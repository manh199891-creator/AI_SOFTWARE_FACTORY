[CmdletBinding()]
param(
  [string]$FactoryRoot="E:\AI_SOFTWARE_FACTORY",
  [string[]]$Targets=@("E:\Antigravity\RevitAddinSolution","E:\Antigravity\NavisAddinSolution"),
  [switch]$ValidateOnly,
  [string]$BackupRoot="",
  [string]$BackupRunId="",
  [switch]$RestoreBackup,
  [string]$CrashAfterStep=""
)
$ErrorActionPreference="Stop"
$FactoryRoot=[IO.Path]::GetFullPath($FactoryRoot).TrimEnd('\')
if (-not $BackupRoot) { $BackupRoot=Join-Path $FactoryRoot "scratch\deploy-backups" }
$runtimeFiles=@("harness.py","review_pipeline.py","dual_agent_runtime.py","learning_guard.py","evolution_pipeline.py","workflow_governance.py","convergence_pipeline.py","runtime_integrity.py")

function Write-Journal([string]$Target,[string]$Status,[string]$Step,[string]$RunId) {
  $path=Join-Path $Target ".agents\deployment_journal.json"; New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force|Out-Null
  @{schema_version=1;status=$Status;step=$Step;run_id=$RunId;updated_at=[DateTime]::UtcNow.ToString("o")} | ConvertTo-Json | Set-Content -LiteralPath $path -Encoding UTF8
}
function Assert-SafeTarget([string]$Target) {
  $full=[IO.Path]::GetFullPath($Target).TrimEnd('\'); $live="E:\Antigravity\"; $fake=(Join-Path $FactoryRoot "scratch\sync-tests").TrimEnd('\')+'\'
  if (-not ($full.StartsWith($live,[StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($fake,[StringComparison]::OrdinalIgnoreCase))) { throw "UNSAFE_TARGET: $full" }
  if ($FactoryRoot.StartsWith($full+'\',[StringComparison]::OrdinalIgnoreCase) -or $full.StartsWith($FactoryRoot+'\skills',[StringComparison]::OrdinalIgnoreCase)) { throw "OVERLAPPING_PATHS: $full" }
  if (-not (Test-Path -LiteralPath $full)) { throw "UNSAFE_TARGET_MISSING: $full" }; return $full
}
function Get-Hash([string]$Path) { (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant() }
function Get-ProjectName([string]$Target) { Split-Path $Target -Leaf }
function Get-Managed([object]$Profile) {
  $d=$Profile.dual_agents; [ordered]@{auto_fix=$d.auto_fix;convergence_v2=$d.convergence_v2;convergence_shadow=$d.convergence_shadow;max_reviews_per_phase=$d.max_reviews_per_phase;execution_policy=$d.execution_policy;review_boundaries=$d.review_boundaries}
}
function Merge-Profile([string]$Existing,[string]$Canonical,[string]$Output) {
  $target=if(Test-Path $Existing){Get-Content -Raw $Existing|ConvertFrom-Json}else{[pscustomobject]@{}}
  $source=Get-Content -Raw $Canonical|ConvertFrom-Json
  if(-not $target.dual_agents){$target|Add-Member NoteProperty dual_agents ([pscustomobject]@{})}
  foreach($key in @("auto_fix","convergence_v2","convergence_shadow","max_reviews_per_phase","execution_policy","review_boundaries")){
    $value=$source.dual_agents.$key
    if($null -ne $value){$target.dual_agents|Add-Member NoteProperty $key $value -Force}
  }
  New-Item -ItemType Directory -Path (Split-Path $Output -Parent) -Force|Out-Null
  $target|ConvertTo-Json -Depth 20|Set-Content -LiteralPath $Output -Encoding UTF8
}
function New-Stage([string]$Target,[string]$Stage) {
  $project=Get-ProjectName $Target; $agents=Join-Path $Stage ".agents"; New-Item -ItemType Directory -Path (Join-Path $agents "runtime") -Force|Out-Null
  foreach($name in $runtimeFiles){$source=Join-Path $FactoryRoot $name;if(-not(Test-Path $source)){throw "MISSING_RUNTIME_MODULE: $name"};Copy-Item -LiteralPath $source -Destination (Join-Path $agents "runtime\$name") -Force}
  Copy-Item -LiteralPath (Join-Path $FactoryRoot "schemas") -Destination (Join-Path $agents "runtime\schemas") -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $FactoryRoot "skills\dual-agent") -Destination (Join-Path $agents "skills\dual-agent") -Recurse -Force
  Copy-Item -LiteralPath (Join-Path $FactoryRoot "skills\dual-agent-pipeline") -Destination (Join-Path $agents "skills\dual-agent-pipeline") -Recurse -Force
  $canonical=Join-Path $FactoryRoot "$project\.agent\project_profile.json";if(-not(Test-Path $canonical)){throw "PROFILE_DRIFT: canonical profile missing for $project"}
  Merge-Profile (Join-Path $Target ".agents\factory\$project\.agent\project_profile.json") $canonical (Join-Path $agents "factory\$project\.agent\project_profile.json")
  $entries=@();Get-ChildItem -LiteralPath $agents -Recurse -File|Where-Object{$_.FullName -notmatch 'runtime_manifest.json$'}|ForEach-Object{$entries+=@{path=$_.FullName.Substring($Stage.Length+1).Replace('\','/');sha256=Get-Hash $_.FullName;size=$_.Length}}
  @{manifest_version=1;project=$project;files=$entries|Sort-Object path;managed_profile=Get-Managed (Get-Content -Raw $canonical|ConvertFrom-Json)}|ConvertTo-Json -Depth 20|Set-Content -LiteralPath (Join-Path $agents "runtime\runtime_manifest.json") -Encoding UTF8
}
function Test-Stage([string]$Stage) {
  foreach($name in $runtimeFiles){if(-not(Test-Path (Join-Path $Stage ".agents\runtime\$name"))){throw "MISSING_RUNTIME_MODULE: $name"}}
  $env:PYTHONDONTWRITEBYTECODE='1'; & python -c "import sys;sys.path.insert(0,r'$Stage\.agents\runtime');import harness,review_pipeline,dual_agent_runtime,workflow_governance,convergence_pipeline,runtime_integrity";if($LASTEXITCODE-ne 0){throw "IMPORT_SMOKE_FAILED"}
}
function Test-Target([string]$Target,[string]$Stage) {
  $manifest=Get-Content -Raw (Join-Path $Stage ".agents\runtime\runtime_manifest.json")|ConvertFrom-Json
  foreach($entry in $manifest.files){$actual=Join-Path $Target $entry.path;if(-not(Test-Path $actual)){throw "MISSING_RUNTIME_MODULE: $($entry.path)"};if((Get-Hash $actual)-ne $entry.sha256){throw "RUNTIME_DRIFT: $($entry.path)"}}
  $project=Get-ProjectName $Target;$actualProfile=Get-Content -Raw (Join-Path $Target ".agents\factory\$project\.agent\project_profile.json")|ConvertFrom-Json
  if((Get-Managed $actualProfile|ConvertTo-Json -Depth 10 -Compress)-ne($manifest.managed_profile|ConvertTo-Json -Depth 10 -Compress)){throw "PROFILE_DRIFT: $project"}
}
function Restore([string]$Target,[string]$Backup) {
  Write-Journal $Target "ROLLING_BACK" "restore" $BackupRunId
  foreach($rel in @(".agents\runtime",".agents\skills\dual-agent",".agents\skills\dual-agent-pipeline")){ $src=Join-Path $Backup $rel;$dst=Join-Path $Target $rel;if(Test-Path $dst){Remove-Item -LiteralPath $dst -Recurse -Force};if(Test-Path $src){New-Item -ItemType Directory -Path (Split-Path $dst -Parent)-Force|Out-Null;Copy-Item -LiteralPath $src -Destination $dst -Recurse -Force}}
  $project=Get-ProjectName $Target;$srcProfile=Join-Path $Backup "project_profile.json";$dstProfile=Join-Path $Target ".agents\factory\$project\.agent\project_profile.json";if(Test-Path $srcProfile){Copy-Item -LiteralPath $srcProfile -Destination $dstProfile -Force}
  Write-Journal $Target "ROLLED_BACK" "complete" $BackupRunId
}

foreach($raw in $Targets){
  $target=Assert-SafeTarget $raw;$project=Get-ProjectName $target;$backup=Join-Path $BackupRoot "$BackupRunId\$project"
  if($RestoreBackup){if(-not $BackupRunId -or -not(Test-Path $backup)){throw "BACKUP_NOT_FOUND: $backup"};Restore $target $backup;Write-Output "RESTORED: $project";continue}
  $stage=Join-Path $FactoryRoot "scratch\deploy-stage\$([guid]::NewGuid())\$project";New-Item -ItemType Directory -Path $stage -Force|Out-Null
  try{New-Stage $target $stage;Test-Stage $stage
    if($ValidateOnly){Test-Target $target $stage;Write-Output "VALID: $project";continue}
    if(-not $BackupRunId){throw "BACKUP_RUN_ID_REQUIRED"};if(Test-Path $backup){throw "IMMUTABLE_BACKUP_EXISTS: $backup"}
    New-Item -ItemType Directory -Path $backup -Force|Out-Null
    foreach($rel in @(".agents\runtime",".agents\skills\dual-agent",".agents\skills\dual-agent-pipeline")){if(Test-Path(Join-Path $target $rel)){New-Item -ItemType Directory -Path (Split-Path (Join-Path $backup $rel)-Parent)-Force|Out-Null;Copy-Item -LiteralPath (Join-Path $target $rel) -Destination (Join-Path $backup $rel) -Recurse -Force}}
    $profile=Join-Path $target ".agents\factory\$project\.agent\project_profile.json";if(Test-Path $profile){Copy-Item -LiteralPath $profile -Destination (Join-Path $backup "project_profile.json")}
    Get-ChildItem -LiteralPath $backup -Recurse -File|ForEach-Object{"$((Get-Hash $_.FullName))  $($_.FullName.Substring($backup.Length+1))"}|Set-Content -LiteralPath (Join-Path $backup "SHA256SUMS") -Encoding UTF8
    Write-Journal $target "DEPLOYING" "backup_complete" $BackupRunId
    foreach($rel in @(".agents\runtime",".agents\skills\dual-agent",".agents\skills\dual-agent-pipeline")){Write-Journal $target "DEPLOYING" $rel $BackupRunId;if($CrashAfterStep-eq$rel){throw "INJECTED_CRASH: $rel"};$dst=Join-Path $target $rel;if(Test-Path $dst){Remove-Item -LiteralPath $dst -Recurse -Force};New-Item -ItemType Directory -Path (Split-Path $dst -Parent)-Force|Out-Null;Copy-Item -LiteralPath (Join-Path $stage $rel) -Destination $dst -Recurse -Force}
    Copy-Item -LiteralPath (Join-Path $stage ".agents\factory\$project\.agent\project_profile.json") -Destination $profile -Force
    Test-Target $target $stage;Write-Journal $target "COMMITTED" "post_deploy_validated" $BackupRunId;Write-Output "SYNCED: $project"
  }catch{if(-not $ValidateOnly -and $BackupRunId -and(Test-Path $backup)){Restore $target $backup};throw}finally{$stageRunRoot=Split-Path $stage -Parent;if(Test-Path $stageRunRoot){Remove-Item -LiteralPath $stageRunRoot -Recurse -Force -ErrorAction SilentlyContinue}}
}
