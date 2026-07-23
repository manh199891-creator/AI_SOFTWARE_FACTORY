# Check for Admin rights (recommended to register scheduled tasks in Windows)
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Warning "PowerShell is not running as Administrator. Scheduled Task creation might fail."
    Write-Host "Please restart this terminal as Administrator and run the script again if it fails." -ForegroundColor Yellow
}

$ScriptPath = Join-Path (Get-Location) "scan_news.py"
$WorkingDirectory = (Get-Location).Path

# Define the action (run python pointing to our script)
$Action = New-ScheduledTaskAction -Execute "python.exe" -Argument "`"$ScriptPath`"" -WorkingDirectory $WorkingDirectory

# Define the trigger (Weekly on Monday at 9:00 AM)
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 9:00AM

# Settings (Run whether user is logged on or not, or just standard user-interactive)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Write-Host "Registering Weekly Scheduled Task 'BIM-AI_Academic_Scanner'..." -ForegroundColor Green

try {
    Register-ScheduledTask -TaskName "BIM-AI_Academic_Scanner" -Action $Action -Trigger $Trigger -Settings $Settings -Description "Weekly scan and summary of BIM & AI papers from Semantic Scholar." -Force
    Write-Host "Successfully registered Scheduled Task! It will run every Monday at 9:00 AM." -ForegroundColor Green
    Write-Host "You can manage this task in Windows Task Scheduler under the name 'BIM-AI_Academic_Scanner'." -ForegroundColor Cyan
} catch {
    Write-Error "Failed to register Scheduled Task: $_"
}
