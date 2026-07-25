param(
    [Parameter(Mandatory = $true)]
    [string]$Root
)

$ErrorActionPreference = "Stop"

function Get-DirectorySizeMB([string]$Path) {
    if (-not (Test-Path $Path)) { return 0 }
    $bytes = (Get-ChildItem $Path -Recurse -File | Measure-Object Length -Sum).Sum
    if ($null -eq $bytes) { return 0 }
    return [math]::Round($bytes / 1MB, 1)
}

$before = Get-DirectorySizeMB $Root

# The application uses QtCore, QtGui, QtWidgets, the Windows platform plugin,
# and image codecs. These optional trees are not used by its widget-only UI.
$optionalPaths = @(
    "_internal\PySide6\Qt\qml",
    "_internal\PySide6\Qt\translations",
    "_internal\PySide6\Qt\plugins\designer",
    "_internal\PySide6\Qt\plugins\qmltooling",
    "_internal\PySide6\Qt\plugins\sqldrivers",
    "_internal\PySide6\Qt\plugins\networkinformation",
    "_internal\PySide6\Qt\plugins\tls",
    "_internal\PySide6\Qt\plugins\styles"
)

foreach ($relative in $optionalPaths) {
    $target = Join-Path $Root $relative
    if (Test-Path $target) {
        Remove-Item $target -Recurse -Force
    }
}

Get-ChildItem $Root -Recurse -File -Include *.pdb,*.lib,*.exp | Remove-Item -Force -ErrorAction SilentlyContinue

$after = Get-DirectorySizeMB $Root
Write-Host "Portable runtime: $before MB -> $after MB"
