$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -3.11 -m venv .venv
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

& .\.venv\Scripts\pyinstaller.exe `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name "CS2MusicController" `
    --icon "assets\app.ico" `
    --add-data "assets;assets" `
    --paths "src" `
    --hidden-import "PySide6.QtMultimedia" `
    --hidden-import "winrt.windows.media.control" `
    --hidden-import "winrt.windows.storage.streams" `
    --collect-submodules "pycaw" `
    --collect-submodules "comtypes" `
    app.py

$Inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $Inno) {
    & $Inno "installer\CS2MusicController.iss"
    Write-Host "Installer created in installer\output"
} else {
    Write-Host "Portable build created in dist\CS2MusicController"
    Write-Host "Install Inno Setup 6 and rerun to produce the setup executable."
}
