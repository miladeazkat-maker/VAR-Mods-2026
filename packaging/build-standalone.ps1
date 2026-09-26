$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Dist = Join-Path $Root "dist"
$Build = Join-Path $Root "build"
$Stage = Join-Path $Root "release-stage"
$Packaging = Join-Path $Root "packaging"

Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dist, $Build, $Stage | Out-Null

function Build-Exe($specFile, $exeName) {
  Write-Host "== Build $exeName =="
  python -m PyInstaller --clean --noconfirm (Join-Path $Packaging $specFile)
  if($LASTEXITCODE -ne 0) { throw "$exeName build failed." }
  $built = Join-Path $Root ("dist\" + $exeName + ".exe")
  if(!(Test-Path $built)) { throw "PyInstaller did not produce $built" }
  Copy-Item $built (Join-Path $Stage ($exeName + ".exe")) -Force
}

Build-Exe "MyMods.spec" "MyMods"
Build-Exe "ModBridge.spec" "ModBridge"
Build-Exe "AssetDownloader.spec" "Asset Downloader"

Write-Host "== Copy project source and mod assets =="
$topFiles = @("MyMods.py","ModBridge.py","LICENSE","requirements.txt")
foreach($file in $topFiles) {
  if(Test-Path (Join-Path $Root $file)) { Copy-Item (Join-Path $Root $file) (Join-Path $Stage $file) -Force }
}
$dirs = @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","PT","Background")
foreach($dir in $dirs) { Copy-Item (Join-Path $Root $dir) (Join-Path $Stage $dir) -Recurse -Force }

Write-Host "== Exclude Python installer/download helper from release =="
Remove-Item (Join-Path $Stage "Python Library Downloader.exe") -Force -ErrorAction SilentlyContinue
Remove-Item (Join-Path $Stage "Python_Library_Downloader.py") -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "== Verify application EXEs =="
$requiredExes = @("MyMods.exe","ModBridge.exe","Asset Downloader.exe")
foreach($name in $requiredExes) {
  if(!(Test-Path (Join-Path $Stage $name))) { throw "Required release EXE missing: $name" }
}

Write-Host "== Verify no separately shipped Python runtime =="
$forbidden = Get-ChildItem $Stage -Recurse -File | Where-Object {
  $_.Name.ToLower() -in @("python.exe","pythonw.exe","py.exe","python3.dll","python313.dll","python312.dll","python311.dll") -or $_.Extension.ToLower() -in @(".pyc",".pyo")
}
if($forbidden) {
  $forbidden | Select-Object FullName,Length | Format-Table -AutoSize
  throw "Release stage contains a separately shipped Python runtime artifact."
}

Write-Host "== Self-contained package smoke tests =="
& (Join-Path $Stage "MyMods.exe") --package-smoke
if($LASTEXITCODE -ne 0) { throw "MyMods.exe package smoke test failed." }
& (Join-Path $Stage "ModBridge.exe") --package-smoke
if($LASTEXITCODE -ne 0) { throw "ModBridge.exe package smoke test failed." }

Write-Host "== Embedded backend smoke tests =="
& (Join-Path $Stage "ModBridge.exe") --embedded-backend HeatMap HeatMapMod --selftest
if($LASTEXITCODE -ne 0) { throw "Heat Map embedded backend selftest failed." }
& (Join-Path $Stage "ModBridge.exe") --embedded-backend SAOTMod SAOTMod --selftest
if($LASTEXITCODE -ne 0) { throw "S.A.O.T embedded backend selftest failed." }
& (Join-Path $Stage "ModBridge.exe") --embedded-backend MomentumMatch MomentumMod --selftest
if($LASTEXITCODE -ne 0) { throw "Momentum embedded backend selftest failed." }

Write-Host "== Asset Downloader package smoke test =="
& (Join-Path $Stage "Asset Downloader.exe") --package-smoke
if($LASTEXITCODE -ne 0) { throw "Asset Downloader.exe package smoke test failed." }

Write-Host "== Compile source integrity check (build machine only) =="
python -m py_compile (Join-Path $Stage "MyMods.py") (Join-Path $Stage "ModBridge.py") (Join-Path $Stage "GLT\GLTMod.py") (Join-Path $Stage "HeatMap\HeatMapMod.py") (Join-Path $Stage "MomentumMatch\MomentumMod.py") (Join-Path $Stage "SAOTMod\SAOTMod.py") (Join-Path $Stage "RefereeView\RefereeView.py") (Join-Path $Stage "PT\PES_FootballLife_Asset_Downloader.py")
if($LASTEXITCODE -ne 0) { throw "Source compile check failed." }
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "== Build Inno Setup v1.0.0 =="
$Iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if(!$Iscc) {
  $candidates = @("$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe","$env:ProgramFiles\Inno Setup 6\ISCC.exe")
  $Iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if(!$Iscc) { throw "Inno Setup compiler was not found." }
& $Iscc (Join-Path $Packaging "VAR-Mods-2026-standalone.iss")
if($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed." }

$Installer = Join-Path $Dist "VAR-Mods-2026-v1.0.0-Setup.exe"
if(!(Test-Path $Installer)) { throw "Expected installer was not created." }
function Get-FolderBytes($path) { return (Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum }
$stageSize = Get-FolderBytes $Stage
$installerSize = (Get-Item $Installer).Length
$launchers = Get-ChildItem $Stage -File -Filter "*.exe" | Sort-Object Name

$report = @(
  "VAR-Mods-2026 v1.0.0 Self-Contained Release Preview",
  "End-user Python installation required: NO",
  "Separate Python runtime shipped: NO",
  "Python Library Downloader shipped: NO",
  "Release stage size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "Installer size: $([math]::Round($installerSize / 1MB, 2)) MB",
  "",
  "Application EXEs:"
)
foreach($launcher in $launchers) { $report += ("  {0}: {1} MB" -f $launcher.Name, [math]::Round($launcher.Length / 1MB, 2)) }
$report += ""
$report += "Installer: $Installer"
$report | Set-Content (Join-Path $Dist "standalone-size-report.txt") -Encoding UTF8
Get-Content (Join-Path $Dist "standalone-size-report.txt")