$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root
python -m pytest
if ($LASTEXITCODE -ne 0) { throw "Les tests ont échoué." }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name "ArcanaMapStudio" --paths "src" "src\arcana_editor\__main__.py"
Write-Host "Executable créé : dist\ArcanaMapStudio.exe"
