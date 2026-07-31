<#
.SYNOPSIS
    Initialize the canonical AI workflow structure inside an existing module directory.

.DESCRIPTION
    Wrapper that delegates all logic to module_bootstrap.py.
    This script contains NO business logic — it only resolves paths, finds Python,
    and forwards parameters.

.PARAMETER RepositoryRoot
    Absolute path to the Git working tree root.

.PARAMETER ModuleRoot
    Repository-relative path to the module directory (e.g. src\Antigravity.DrawBeams).

.PARAMETER ModuleId
    Lowercase machine identifier, e.g. antigravity.drawbeams

.PARAMETER ModuleName
    Human-readable module name, e.g. Antigravity.DrawBeams

.PARAMETER ProjectFile
    Repository-relative path to the .csproj file inside ModuleRoot.

.PARAMETER Platform
    Target platform: revit | navisworks | dotnet

.PARAMETER DllName
    Output DLL filename (default: <ModuleName>.dll)

.PARAMETER DefaultTestPaths
    Repeatable: repository-relative test paths added to MODULE.json

.PARAMETER SharedDependencies
    Repeatable: repository-relative shared dependency paths

.PARAMETER WorkflowVersion
    Semantic version, e.g. 1.0.0 (default: 1.0.0)

.PARAMETER DryRun
    Preview mode — no files written.

.EXAMPLE
    .\module_init.ps1 `
      -RepositoryRoot "E:\AI_SOFTWARE_FACTORY" `
      -ModuleRoot "src\Antigravity.DrawBeams" `
      -ModuleId "antigravity.drawbeams" `
      -ModuleName "Antigravity.DrawBeams" `
      -ProjectFile "src\Antigravity.DrawBeams\Antigravity.DrawBeams.csproj" `
      -Platform "revit"
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory = $true)]
    [string]$RepositoryRoot,

    [Parameter(Mandatory = $true)]
    [string]$ModuleRoot,

    [Parameter(Mandatory = $true)]
    [string]$ModuleId,

    [Parameter(Mandatory = $true)]
    [string]$ModuleName,

    [Parameter(Mandatory = $true)]
    [string]$ProjectFile,

    [Parameter(Mandatory = $true)]
    [ValidateSet("revit", "navisworks", "dotnet")]
    [string]$Platform,

    [Parameter(Mandatory = $false)]
    [string]$DllName = "",

    [Parameter(Mandatory = $false)]
    [string[]]$DefaultTestPaths = @(),

    [Parameter(Mandatory = $false)]
    [string[]]$SharedDependencies = @(),

    [Parameter(Mandatory = $false)]
    [string]$WorkflowVersion = "1.0.0",

    [Parameter(Mandatory = $false)]
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Resolve script directory and Python script path
# ---------------------------------------------------------------------------
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path $ScriptDir "module_bootstrap.py"

if (-not (Test-Path $PythonScript -PathType Leaf)) {
    Write-Error "module_bootstrap.py not found at: $PythonScript"
    exit 1
}

# ---------------------------------------------------------------------------
# Find Python interpreter (py -3, then python, then python3)
# ---------------------------------------------------------------------------
$PythonExe = $null
$Candidates = @("py", "python", "python3")

foreach ($candidate in $Candidates) {
    try {
        $testArgs = if ($candidate -eq "py") { @("-3", "--version") } else { @("--version") }
        $result = & $candidate @testArgs 2>&1
        if ($LASTEXITCODE -eq 0) {
            $PythonExe = if ($candidate -eq "py") { $candidate } else { $candidate }
            $UsePyLauncher = ($candidate -eq "py")
            break
        }
    } catch {
        # Not found, try next
    }
}

if ($null -eq $PythonExe) {
    Write-Error "No Python interpreter found. Tried: py, python, python3"
    exit 1
}

# ---------------------------------------------------------------------------
# Build argument list for Python script
# ---------------------------------------------------------------------------
$PyArgs = @()
if ($UsePyLauncher) { $PyArgs += "-3" }
$PyArgs += $PythonScript
$PyArgs += "--repository-root", $RepositoryRoot
$PyArgs += "--module-root", ($ModuleRoot -replace '\\', '/')
$PyArgs += "--module-id", $ModuleId
$PyArgs += "--module-name", $ModuleName
$PyArgs += "--project-file", ($ProjectFile -replace '\\', '/')
$PyArgs += "--platform", $Platform

if ($DllName -ne "") {
    $PyArgs += "--dll-name", $DllName
}

foreach ($tp in $DefaultTestPaths) {
    $PyArgs += "--default-test-path", ($tp -replace '\\', '/')
}

foreach ($sd in $SharedDependencies) {
    $PyArgs += "--shared-dependency", ($sd -replace '\\', '/')
}

$PyArgs += "--workflow-version", $WorkflowVersion

if ($DryRun) {
    $PyArgs += "--dry-run"
}

# ---------------------------------------------------------------------------
# Delegate to Python — forward exit code unchanged
# ---------------------------------------------------------------------------
& $PythonExe @PyArgs
exit $LASTEXITCODE
