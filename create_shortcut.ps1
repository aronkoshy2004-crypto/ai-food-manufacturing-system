# Food Man - Desktop Shortcut Creator
# Creates "Food Man" and "Stop Food Man" desktop shortcuts with custom icons.

$ErrorActionPreference = "Stop"
$ProjectDir = $PSScriptRoot
if (-not $ProjectDir) {
    $ProjectDir = (Get-Location).Path
}

Write-Host "Creating Food Man Desktop Shortcuts..." -ForegroundColor Cyan

# 1. Ensure custom icons exist
$IconDir = Join-Path $ProjectDir "static\icons"
$FoodManIco = Join-Path $IconDir "foodman.ico"
$StopIco = Join-Path $IconDir "stop_foodman.ico"

if (-not (Test-Path $FoodManIco) -or -not (Test-Path $StopIco)) {
    Write-Host "Generating custom .ico icons from project logo..." -ForegroundColor Yellow
    python (Join-Path $ProjectDir "scratch\generate_icons.py")
}

# 2. Get User Desktop Path
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
if (-not (Test-Path $DesktopPath)) {
    $DesktopPath = Join-Path $env:USERPROFILE "Desktop"
}

$WshShell = New-Object -ComObject WScript.Shell

# 3. Create "Food Man" Shortcut
$Lnk1 = Join-Path $DesktopPath "Food Man.lnk"
$S1 = $WshShell.CreateShortcut($Lnk1)
$S1.TargetPath = Join-Path $ProjectDir "FoodMan.bat"
$S1.WorkingDirectory = $ProjectDir
$S1.IconLocation = "$FoodManIco,0"
$S1.Description = "Food Man Smart Manufacturing and Cold-Chain Management"
$S1.WindowStyle = 7
$S1.Save()
Write-Host "[OK] Created Desktop Shortcut: 'Food Man' -> $Lnk1" -ForegroundColor Green
Write-Host "     Icon: $FoodManIco" -ForegroundColor Gray

# 4. Create "Stop Food Man" Shortcut
$Lnk2 = Join-Path $DesktopPath "Stop Food Man.lnk"
$S2 = $WshShell.CreateShortcut($Lnk2)
$S2.TargetPath = Join-Path $ProjectDir "StopFoodMan.bat"
$S2.WorkingDirectory = $ProjectDir
$S2.IconLocation = "$StopIco,0"
$S2.Description = "Stop Food Man Server and Cloudflare Tunnel"
$S2.WindowStyle = 1
$S2.Save()
Write-Host "[OK] Created Desktop Shortcut: 'Stop Food Man' -> $Lnk2" -ForegroundColor Green
Write-Host "     Icon: $StopIco" -ForegroundColor Gray

# Also create in local desktop folder if OneDrive desktop is active
$AltDesktop = Join-Path $env:USERPROFILE "Desktop"
if ($AltDesktop -ne $DesktopPath -and (Test-Path $AltDesktop)) {
    Copy-Item $Lnk1 -Destination (Join-Path $AltDesktop "Food Man.lnk") -Force -ErrorAction SilentlyContinue
    Copy-Item $Lnk2 -Destination (Join-Path $AltDesktop "Stop Food Man.lnk") -Force -ErrorAction SilentlyContinue
}

Write-Host "`nAll desktop shortcuts successfully created with custom icons!" -ForegroundColor Green
