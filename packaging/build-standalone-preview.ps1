$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Stage = Join-Path $Root "stage"
$Dist = Join-Path $Root "dist"
$Packaging = Join-Path $Root "packaging"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage, $Dist | Out-Null

Write-Host "== Build standalone EXE #1: MyMods =="
python -m PyInstaller --clean --noconfirm "$Packaging\MyMods.spec"
Copy-Item "$Dist\MyMods.exe" "$Stage\MyMods.exe" -Force

Write-Host "== Build standalone EXE #2: ModBridge =="
python -m PyInstaller --clean --noconfirm "$Packaging\ModBridge.spec"
Copy-Item "$Dist\ModBridge.exe" "$Stage\ModBridge.exe" -Force

Write-Host "== Build standalone EXE #3: Asset Downloader =="
python -m PyInstaller --clean --noconfirm "$Packaging\AssetDownloader.spec"
Copy-Item "$Dist\Asset Downloader.exe" "$Stage\Asset Downloader.exe" -Force

Write-Host "== Copy non-code release assets =="

$topFiles = @("LICENSE","requirements.txt")
foreach($file in $topFiles) {
  Copy-Item (Join-Path $Root $file) (Join-Path $Stage $file) -Force
}

$dirs = @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","Background")
foreach($dir in $dirs) {
  Copy-Item (Join-Path $Root $dir) (Join-Path $Stage $dir) -Recurse -Force
}

# Source code is compiled into the EXEs and must never be installed separately.
Get-ChildItem $Stage -Recurse -File -Include "*.py","*.pyc","*.pyo" |
  Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" |
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "== Standalone package validation =="

$pythonFiles = @(Get-ChildItem $Stage -Recurse -File -Include "*.py","*.pyc","*.pyo")
if($pythonFiles.Count -ne 0) {
  $pythonFiles | ForEach-Object { Write-Host "FORBIDDEN PYTHON FILE: $($_.FullName)" }
  throw "Standalone package validation failed: Python files are present in the install stage."
}

$runtimeDirs = @(Get-ChildItem $Stage -Recurse -Directory | Where-Object {
  $_.Name -in @("runtime","venv",".venv")
})
if($runtimeDirs.Count -ne 0) {
  throw "Standalone package validation failed: a Python runtime directory is present."
}

$executables = @(Get-ChildItem $Stage -Recurse -File -Filter "*.exe")
if($executables.Count -ne 3) {
  $executables | ForEach-Object { Write-Host "EXE: $($_.FullName)" }
  throw "Standalone package validation failed: expected exactly 3 installed EXE files."
}

$requiredExeNames = @("MyMods.exe","ModBridge.exe","Asset Downloader.exe")

Write-Host "Standalone EXE smoke tests:"
& "$StageMyMods.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "MyMods standalone smoke test failed." }
& "$StageModBridge.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "ModBridge embedded-backend smoke test failed." }
& "$StageAsset Downloader.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "Asset Downloader standalone smoke test failed." }
foreach($name in $requiredExeNames) {
  if(!(Test-Path (Join-Path $Stage $name))) {
    throw "Required executable is missing: $name"
  }
}

Write-Host "Standalone EXE inventory:"
foreach($exe in $executables) {
  Write-Host ("  {0}: {1} MB" -f $exe.Name, [math]::Round($exe.Length / 1MB, 2))
}

Write-Host "== Build Inno Setup installer =="

$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if(!$Iscc) {
  $candidates = @(
    "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
  )
  $Iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if(!$Iscc) { throw "Inno Setup compiler was not found." }

& $Iscc "$Packaging\VAR-Mods-2026.iss"
if($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$Installer = Join-Path $Dist "VAR-Mods-2026-v1.0.0-Setup.exe"
if(!(Test-Path $Installer)) { throw "Expected installer was not created." }

function Get-FolderBytes($path) {
  $sum = (Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum
  if($null -eq $sum) { return 0 }
  return [double]$sum
}

$stageSize = Get-FolderBytes $Stage
$installerSize = (Get-Item $Installer).Length

$report = @(
  "VAR-Mods-2026 v1.0.0 Standalone Release Preview",
  "Installed payload size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "Installer size: $([math]::Round($installerSize / 1MB, 2)) MB",
  "",
  "Installed executables (exactly 3):"
)

foreach($exe in ($executables | Sort-Object Name)) {
  $report += ("  {0}: {1} MB" -f $exe.Name, [math]::Round($exe.Length / 1MB, 2))
}

$report += ""
$report += "Python source files in stage: 0"
$report += "Separate Python runtime directories: 0"
$report += "Installer: $Installer"

$report | Set-Content (Join-Path $Dist "v1.0.0-standalone-size-report.txt") -Encoding UTF8
Get-Content (Join-Path $Dist "v1.0.0-standalone-size-report.txt")
