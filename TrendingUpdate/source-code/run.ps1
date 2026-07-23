# Install dependencies if needed
Write-Host "Checking python dependencies..." -ForegroundColor Green
pip install -r requirements.txt --quiet

# Run the scanner
Write-Host "Running BIM-AI News Scanner..." -ForegroundColor Green
python scan_news.py

# Find the latest HTML newsletter and open it in the default browser
$latestFile = Get-ChildItem -Path "newsletters" -Filter "*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1

if ($latestFile) {
    Write-Host "Opening latest newsletter in your browser: $($latestFile.FullName)" -ForegroundColor Cyan
    Start-Process $latestFile.FullName
} else {
    Write-Host "No newsletter HTML was created." -ForegroundColor Red
}
