$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Stage = Join-Path $Root "stage"
$Dist = Join-Path $Root "dist"
$Packaging = Join-Path $Root "packaging"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage, $Dist | Out-Null

Write-Host "== Build self-contained EXEs =="
python -m PyInstaller --onefile --noconsole --clean --noconfirm "$PackagingMyMods.spec"
Copy-Item "$RootdistMyMods.exe" "$StageMyMods.exe" -Force
python -m PyInstaller --onefile --noconsole --clean --noconfirm "$PackagingModBridge.spec"
Copy-Item "$RootdistModBridge.exe" "$StageModBridge.exe" -Force
python -m PyInstaller --onefile --noconsole --clean --noconfirm "$PackagingAssetDownloader.spec"
Copy-Item "$RootdistAsset Downloader.exe" "$StageAsset Downloader.exe" -Force

Write-Host "== Copy project files =="
$topFiles = @("MyMods.py","ModBridge.py","LICENSE","requirements.txt")
foreach($file in $topFiles) { Copy-Item (Join-Path $Root $file) (Join-Path $Stage $file) -Force }
$dirs = @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","PT","Background")
foreach($dir in $dirs) { Copy-Item (Join-Path $Root $dir) (Join-Path $Stage $dir) -Recurse -Force }

Write-Host "== Remove build-only files =="
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Stage "packaging") -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Stage "Python Library Downloader.exe") -Force -ErrorAction SilentlyContinue

Write-Host "== Verify no separately shipped Python runtime =="
$forbiddenRuntimeNames = @("python.exe","pythonw.exe","python3.dll","python313.dll")
$runtimeHits = Get-ChildItem $Stage -Recurse -File | Where-Object { $forbiddenRuntimeNames -contains $_.Name.ToLower() }
if($runtimeHits) { throw "Release stage contains a separately shipped Python/runtime binary." }

Write-Host "== Embedded backend smoke tests =="
& "$StageModBridge.exe" --embedded-backend HeatMap HeatMapMod --selftest
if($LASTEXITCODE -ne 0) { throw "Heat Map embedded backend selftest failed: $LASTEXITCODE" }
& "$StageModBridge.exe" --embedded-backend SAOTMod SAOTMod --selftest
if($LASTEXITCODE -ne 0) { throw "S.A.O.T embedded backend selftest failed: $LASTEXITCODE" }
& "$StageModBridge.exe" --embedded-backend MomentumMatch MomentumMod --selftest
if($LASTEXITCODE -ne 0) { throw "Momentum embedded backend selftest failed: $LASTEXITCODE" }

Write-Host "== Source integrity compile check =="
python -m py_compile "$StageMyMods.py" "$StageModBridge.py" "$StageGLTGLTMod.py" "$StageHeatMapHeatMapMod.py" "$StageHeatMapBroadcastRenderer.py" "$StageMomentumMatchMomentumMod.py" "$StageSAOTModSAOTMod.py" "$StageRefereeViewRefereeView.py" "$StagePTPES_FootballLife_Asset_Downloader.py"
if($LASTEXITCODE -ne 0) { throw "Source compile check failed." }
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "== Build Inno Setup installer =="
$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if(!$Iscc) { $candidates = @("$env:ProgramFiles(x86)Inno Setup 6ISCC.exe","$env:ProgramFilesInno Setup 6ISCC.exe"); $Iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1 }
if(!$Iscc) { throw "Inno Setup compiler was not found." }
& $Iscc "$PackagingVAR-Mods-2026.iss"
if($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

$Installer = Join-Path $Dist "VAR-Mods-2026-v1.0.0-Setup.exe"
if(!(Test-Path $Installer)) { throw "Expected installer was not created." }
function Get-FolderBytes($path) { return (Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum }
$stageSize = Get-FolderBytes $Stage
$installerSize = (Get-Item $Installer).Length
$launchers = Get-ChildItem $Stage -Filter "*.exe" | Where-Object { $_.Name -in @("MyMods.exe","ModBridge.exe","Asset Downloader.exe") }
$report = @(
  "VAR-Mods-2026 v1.0.0 Self-Contained Release Preview",
  "Python installation required by end user: NO",
  "Separate Python runtime shipped beside EXEs: NO",
  "Stage size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "Installer size: $([math]::Round($installerSize / 1MB, 2)) MB",
  "",
  "Application EXEs:"
)
foreach($launcher in $launchers) { $report += ("  {0}: {1} MB" -f $launcher.Name, [math]::Round($launcher.Length / 1MB, 2)) }
$report += ""
$report += "Installer: $Installer"
$report | Set-Content (Join-Path $Dist "v1.0.0-size-report.txt") -Encoding UTF8
Get-Content (Join-Path $Dist "v1.0.0-size-report.txt")