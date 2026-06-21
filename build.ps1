param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
$iconPath = Join-Path $root "assets\timekeeper.ico"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python is not installed or not available in PATH."
}

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

$python = Join-Path $root ".venv\Scripts\python.exe"

& $python -m pip install --upgrade pip
& $python -m pip install -r requirements-build.txt

if (-not (Test-Path $iconPath)) {
    throw "Icon file not found: $iconPath"
}

if ($Clean) {
    if (Test-Path "build") {
        Remove-Item "build" -Recurse -Force
    }
    if (Test-Path "dist") {
        Remove-Item "dist" -Recurse -Force
    }
}

& $python -m PyInstaller `
    --noconfirm `
    --clean `
    --noconsole `
    --onefile `
    --name "TimeKeeper" `
    --icon "$iconPath" `
    --hidden-import "pystray._win32" `
    --hidden-import "PIL._tkinter_finder" `
    --hidden-import "win32timezone" `
    main.py

Write-Host ""
Write-Host "Build complete."
Write-Host "Executable: $root\dist\TimeKeeper.exe"
