param([Parameter(Mandatory=$true)][string]$Project)
. (Join-Path $PSScriptRoot "dual_paths.ps1")
$paths = Get-DualAgentPaths
$aliases = @{ "revit"="RevitAddinSolution"; "navis"="NavisAddinSolution"; "factory"="factory" }
$projectName = if ($aliases.ContainsKey($Project)) { $aliases[$Project] } else { $Project }
& python $paths.Harness $projectName writer-checkpoint
exit $LASTEXITCODE
