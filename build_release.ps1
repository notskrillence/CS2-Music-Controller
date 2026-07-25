$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    py -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        python -m venv .venv
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the virtual environment. Install Python 3.11 or newer."
    }
}


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
    --hidden-import "winrt.windows.media" `
    --hidden-import "winrt.windows.media.control" `
    --hidden-import "winrt.windows.storage.streams" `
    --collect-submodules "pycaw" `
    --collect-submodules "comtypes" `
    --exclude-module "PySide6.QtMultimedia" `
    --exclude-module "PySide6.QtMultimediaWidgets" `
    --exclude-module "PySide6.QtQml" `
    --exclude-module "PySide6.QtQuick" `
    --exclude-module "PySide6.QtQuickControls2" `
    --exclude-module "PySide6.QtQuickWidgets" `
    --exclude-module "PySide6.QtSql" `
    --exclude-module "PySide6.QtTest" `
    --exclude-module "PySide6.QtUiTools" `
    app.py

& "$PSScriptRoot\tools\prune_runtime.ps1" -Root "$PSScriptRoot\dist\CS2MusicController"

$Inno = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
if (Test-Path $Inno) {
    & $Inno "installer\CS2MusicController.iss"
    $installer = Get-ChildItem "installer\output\CS2MusicController-Setup-*.exe" |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($installer) {
        $size = [math]::Round($installer.Length / 1MB, 1)
        Write-Host "Installer created: $($installer.FullName) ($size MB)"
    }
} else {
    Write-Host "Portable build created in dist\CS2MusicController"
    Write-Host "Install Inno Setup 6 and rerun to produce the setup executable."
}
