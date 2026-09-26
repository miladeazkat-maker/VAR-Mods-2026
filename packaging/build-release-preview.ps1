$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Stage = Join-Path $Root "stage"
$Dist = Join-Path $Root "dist"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage, $Dist | Out-Null

function Build-OneFile($name, $entry, $extraArgs) {
  Write-Host "== Building $name as a fully self-contained EXE =="
  $args = @(
    "--onefile",
    "--windowed",
    "--clean",
    "--noconfirm",
    "--name", $name,
    "--exclude-module", "PyQt5"
  )
  $args += $extraArgs
  $args += $entry
  python -m PyInstaller @args
  if($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $name." }

  $built = Join-Path $Root "dist\$name.exe"
  if(!(Test-Path $built)) { throw "Expected $built was not created." }
  Copy-Item $built (Join-Path $Stage "$name.exe") -Force
  Remove-Item $built -Force
}

# MyMods is a direct frozen application. It launches ModBridge.exe.
Build-OneFile "MyMods" (Join-Path $Root "MyMods.py") @(
  "--hidden-import", "PyQt6.QtMultimedia"
)

# ModBridge is the only process host. It contains the backend Python sources
# and their assets internally so no backend .py files are installed.
$bridgeData = @(
  "--add-data", "$Root\GLT;GLT",
  "--add-data", "$Root\HeatMap;HeatMap",
  "--add-data", "$Root\MomentumMatch;MomentumMatch",
  "--add-data", "$Root\SAOTMod;SAOTMod",
  "--add-data", "$Root\RefereeView;RefereeView",
  "--hidden-import", "PyQt6.QtWebEngineWidgets",
  "--hidden-import", "PyQt6.QtWebEngineCore",
  "--hidden-import", "PyQt6.QtMultimedia",
  "--hidden-import", "numpy",
  "--hidden-import", "matplotlib",
  "--hidden-import", "pymem",
  "--hidden-import", "pymem.process",
  "--hidden-import", "pymem.pattern",
  "--hidden-import", "moderngl",
  "--hidden-import", "glfw",
  "--hidden-import", "panda3d.core",
  "--hidden-import", "ursina",
  "--hidden-import", "customtkinter",
  "--hidden-import", "keyboard",
  "--hidden-import", "psutil",
  "--hidden-import", "pywinstyles",
  "--collect-data", "PyQt6",
  "--collect-data", "panda3d",
  "--collect-data", "ursina",
  "--collect-data", "matplotlib",
  "--collect-data", "customtkinter",
  "--collect-data", "pywinstyles"
)
Build-OneFile "ModBridge" (Join-Path $Root "ModBridge.py") $bridgeData

# Asset Downloader is fully standalone and uses only its frozen PyQt6 environment.
$assetData = @(
  "--hidden-import", "PyQt6.QtCore",
  "--hidden-import", "PyQt6.QtGui",
  "--hidden-import", "PyQt6.QtWidgets"
)
Build-OneFile "Asset Downloader" (Join-Path $Root "PT\PES_FootballLife_Asset_Downloader.py") $assetData

Write-Host "== Copy only non-Python release assets =="
$topFiles = @("LICENSE")
foreach($file in $topFiles) {
  Copy-Item (Join-Path $Root $file) (Join-Path $Stage $file) -Force
}

$dirs = @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","Background")
foreach($dir in $dirs) {
  Copy-Item (Join-Path $Root $dir) (Join-Path $Stage $dir) -Recurse -Force
}

# The installed package must contain only compiled executables plus runtime
# assets/configuration. All Python source files used by the embedded bridge
# are bundled inside ModBridge.exe and must never be installed separately.
Get-ChildItem $Stage -Recurse -File -Filter "*.py" | Remove-Item -Force
Get-ChildItem $Stage -Recurse -File -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
$pythonFiles = @(Get-ChildItem $Stage -Recurse -File -Filter "*.py")
if($pythonFiles.Count -ne 0) {
  $pythonFiles | ForEach-Object { Write-Host "FORBIDDEN PYTHON FILE: $($_.FullName)" }
  throw "Release staging contains Python source files."
}

Write-Host "== Remove caches and developer-only files =="
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo","*.pdb" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Filter "backend_log.txt" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Filter "debug_log.txt" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "== Smoke test self-contained EXEs =="
& "$Stage\MyMods.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "MyMods standalone smoke test failed." }

& "$Stage\ModBridge.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "ModBridge standalone smoke test failed." }

& "$Stage\Asset Downloader.exe" --package-smoke
if($LASTEXITCODE -ne 0) { throw "Asset Downloader standalone smoke test failed." }

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

& $Iscc "$PSScriptRoot\VAR-Mods-2026.iss"
if($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$Installer = Join-Path $Dist "VAR-Mods-2026-v1.0.0-Setup.exe"
if(!(Test-Path $Installer)) { throw "Expected installer was not created." }

function Get-FolderBytes($path) {
  $m = Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum
  return [int64]$m.Sum
}

$stageSize = Get-FolderBytes $Stage
$installerSize = (Get-Item $Installer).Length
$launchers = Get-ChildItem $Stage -Filter "*.exe" | Where-Object {
  $_.Name -in @("MyMods.exe","ModBridge.exe","Asset Downloader.exe")
}

$report = @(
  "VAR-Mods-2026 v1.0.0 Self-Contained Release Preview",
  "Stage size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "Installer size: $([math]::Round($installerSize / 1MB, 2)) MB",
  "",
  "Installed executables (exactly three):"
)
foreach($launcher in $launchers) {
  $report += ("  {0}: {1} MB" -f $launcher.Name, [math]::Round($launcher.Length / 1MB, 2))
}
$report += ""
$report += "Python source files in install stage: $($pythonFiles.Count)"
$report += "Portable/shared Python runtime folder present: $(Test-Path (Join-Path $Stage "runtime"))"
$report += "Installed Python source files: $pythonFiles.Count"
$report += "Installer: $Installer"

$report | Set-Content (Join-Path $Dist "v1.0.0-size-report.txt") -Encoding UTF8
Get-Content (Join-Path $Dist "v1.0.0-size-report.txt")
