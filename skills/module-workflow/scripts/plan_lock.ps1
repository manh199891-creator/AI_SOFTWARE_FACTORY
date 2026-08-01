[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [ValidateSet("create", "verify")]
    [string]$Action,

    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$ModuleRoot,

    [Parameter(Mandatory = $false)]
    [string]$ApprovalFile,

    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "plan_lock.py"

if (-not (Test-Path $pythonScript)) {
    Write-Error "Python script not found: $pythonScript"
    exit 2
}

# Resolve python runner
$pythonExe = $null
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
    $pythonArgs = @("-3", $pythonScript)
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
    $pythonArgs = @($pythonScript)
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $pythonExe = "python3"
    $pythonArgs = @($pythonScript)
} else {
    Write-Error "No suitable Python interpreter found (py, python, python3)."
    exit 2
}

$cliArgs = @($Action, "--repository-root", $RepositoryRoot, "--module-root", $ModuleRoot)

if ($PSBoundParameters.ContainsKey("ApprovalFile") -and $ApprovalFile) {
    $cliArgs += @("--approval-file", $ApprovalFile)
}

if ($DryRun) {
    $cliArgs += "--dry-run"
}

$allArgs = $pythonArgs + $cliArgs

$process = Start-Process -FilePath $pythonExe -ArgumentList $allArgs -NoNewWindow -PassThru -Wait
exit $process.ExitCode
