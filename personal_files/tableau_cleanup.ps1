# tableau_cleanup.ps1 - Enhanced Tableau removal script
# Run as Administrator AFTER manually uninstalling through Control Panel

Write-Host "⚠️  IMPORTANT: Have you uninstalled Tableau through Control Panel first?" -ForegroundColor Yellow
Write-Host "   Settings → Apps → Tableau → Uninstall" -ForegroundColor Yellow
$response = Read-Host "Continue? (y/n)"
if ($response -ne 'y') { 
    Write-Host "Please uninstall through Control Panel first, then run this script."
    exit 
}

Write-Host "🗑️ Starting Tableau deep cleanup..." -ForegroundColor Red

# Stop any running Tableau processes
Write-Host "Stopping Tableau processes..."
Get-Process | Where-Object { $_.ProcessName -like "*Tableau*" } | Stop-Process -Force -ErrorAction SilentlyContinue

# Remove program directories
Write-Host "Removing program files..."
$tableuPaths = @(
    "C:\Program Files\Tableau",
    "C:\Program Files (x86)\Tableau",
    "$env:LOCALAPPDATA\Tableau", 
    "$env:APPDATA\Tableau",
    "$env:USERPROFILE\Documents\My Tableau Repository"
)

foreach ($path in $tableuPaths) {
    if (Test-Path $path) {
        Write-Host "Removing: $path"
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# Clean up Start Menu shortcuts
Write-Host "Removing shortcuts..."
$shortcutPaths = @(
    "$env:ALLUSERSPROFILE\Microsoft\Windows\Start Menu\Programs\Tableau",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Tableau"
)

foreach ($path in $shortcutPaths) {
    if (Test-Path $path) {
        Remove-Item $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "✅ Tableau cleanup complete!" -ForegroundColor Green

# Optional registry cleanup
Write-Host "🔧 Optional: Clean registry entries? (y/n)" -ForegroundColor Yellow
$regClean = Read-Host
if ($regClean -eq 'y') {
    Write-Host "Cleaning registry entries..."
    try {
        Remove-Item "HKCU:\Software\Tableau" -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item "HKLM:\SOFTWARE\Tableau" -Recurse -Force -ErrorAction SilentlyContinue  
        Remove-Item "HKLM:\SOFTWARE\WOW6432Node\Tableau" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Registry cleanup complete!" -ForegroundColor Green
    }
    catch {
        Write-Host "Registry cleanup failed - you may need to do this manually" -ForegroundColor Yellow
    }
}

Write-Host "📋 Next steps:" -ForegroundColor Yellow
Write-Host "1. Restart your computer"
Write-Host "2. Download Tableau Public from: https://public.tableau.com"
Write-Host "3. Run installer as administrator"