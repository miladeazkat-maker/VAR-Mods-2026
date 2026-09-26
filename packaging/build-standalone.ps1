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

function Add-CommonPyInstallerOptions {
  param([System.Collections.Generic.List[string]]$Args)
  $Args.Add("--clean")
  $Args.Add("--noconfirm")
  $Args.Add("--onefile")
  $Args.Add("--noconsole")
  $Args.Add("--collect-all"); $Args.Add("numpy")
  $Args.Add("--collect-all"); $Args.Add("matplotlib")
  $Args.Add("--collect-all"); $Args.Add("PIL")
}

Write-Host "== Build MyMods.exe =="
$myArgs = [System.Collections.Generic.List[string]]::new()
$myArgs.Add("--clean"); $myArgs.Add("--noconfirm"); $myArgs.Add("--onefile"); $myArgs.Add("--noconsole")
$myArgs.Add("--hidden-import"); $myArgs.Add("PyQt6.QtMultimedia")
$myArgs.Add("--hidden-import"); $myArgs.Add("PyQt6.QtMultimediaWidgets")
$myArgs.Add("--name"); $myArgs.Add("MyMods")
$myArgs.Add("MyMods.py")
& pyinstaller @myArgs
if($LASTEXITCODE -ne 0) { throw "MyMods build failed." }
Copy-Item "$Root\dist\MyMods.exe" "$Stage\MyMods.exe" -Force

Write-Host "== Build ModBridge.exe =="
$bridgeArgs = [System.Collections.Generic.List[string]]::new()
$bridgeArgs.Add("--clean"); $bridgeArgs.Add("--noconfirm"); $bridgeArgs.Add("--onefile"); $bridgeArgs.Add("--noconsole")
$bridgeArgs.Add("--name"); $bridgeArgs.Add("ModBridge")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("PyQt6.QtWebEngineWidgets")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("PyQt6.QtWebEngineCore")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("PyQt6.QtWebEngineQuick")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("pymem.process")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("pymem.pattern")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("numpy")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("matplotlib")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("matplotlib.backends.backend_tkagg")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("matplotlib.backends.backend_agg")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("PIL")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("moderngl")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("glfw")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("panda3d.core")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("panda3d.egg")
$bridgeArgs.Add("--hidden-import"); $bridgeArgs.Add("ursina")
$bridgeArgs.Add("--collect-data"); $bridgeArgs.Add("PyQt6.QtWebEngineCore")
$bridgeArgs.Add("--collect-binaries"); $bridgeArgs.Add("moderngl")
$bridgeArgs.Add("--collect-binaries"); $bridgeArgs.Add("glfw")
$bridgeArgs.Add("--collect-binaries"); $bridgeArgs.Add("panda3d")
$bridgeArgs.Add("--collect-data"); $bridgeArgs.Add("panda3d")
$bridgeArgs.Add("--collect-data"); $bridgeArgs.Add("ursina")
foreach($dir in @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView")) {
  $bridgeArgs.Add("--add-data")
  $bridgeArgs.Add("$Root\$dir;$dir")
}
$bridgeArgs.Add("ModBridge.py")
& pyinstaller @bridgeArgs
if($LASTEXITCODE -ne 0) { throw "ModBridge build failed." }
Copy-Item "$Root\dist\ModBridge.exe" "$Stage\ModBridge.exe" -Force

Write-Host "== Build Asset Downloader.exe =="
$assetArgs = [System.Collections.Generic.List[string]]::new()
$assetArgs.Add("--clean"); $assetArgs.Add("--noconfirm"); $assetArgs.Add("--onefile"); $assetArgs.Add("--noconsole")
$assetArgs.Add("--name"); $assetArgs.Add("Asset Downloader")
$assetArgs.Add("--hidden-import"); $assetArgs.Add("PyQt6")
$assetArgs.Add("PT\PE S_FootballLife_Asset_Downloader.py".Replace("PE S_","PES_"))
& pyinstaller @assetArgs
if($LASTEXITCODE -ne 0) { throw "Asset Downloader build failed." }
Copy-Item "$Root\dist\Asset Downloader.exe" "$Stage\Asset Downloader.exe" -Force

Write-Host "== Copy runtime data =="
foreach($dir in @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","PT","Background")) {
  Copy-Item "$Root\$dir" "$Stage\$dir" -Recurse -Force
}
foreach($file in @("MyMods.py","ModBridge.py","ModsConfig.json","requirements.txt","LICENSE")) {
  if(Test-Path "$Root\$file") { Copy-Item "$Root\$file" "$Stage\$file" -Force }
}

Write-Host "== Ensure no Python runtime is shipped =="
Get-ChildItem $Stage -Recurse -File | Where-Object {
  $_.Name -in @("python.exe","pythonw.exe","py.exe","python3.dll","python313.dll")
} | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "== Build validation =="
& "$Stage\MyMods.exe" "--package-smoke"
if($LASTEXITCODE -ne 0) { throw "MyMods standalone smoke test failed." }
& "$Stage\ModBridge.exe" "--package-smoke"
if($LASTEXITCODE -ne 0) { throw "ModBridge standalone smoke test failed." }
& "$Stage\Asset Downloader.exe" "--package-smoke"
if($LASTEXITCODE -ne 0) { throw "Asset Downloader standalone smoke test failed." }

$bad = Get-ChildItem $Stage -Recurse -File | Where-Object {
  $_.Name -match '^(python(\.exe|w\.exe|3\d+\.dll)|py\.exe)$' -or $_.Extension -eq ".pyc"
}
if($bad) {
  throw "Release stage contains forbidden Python runtime artifacts."
}

Write-Host "== Size report =="
function Get-FolderBytes($path) {
  return (Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum
}
$stageSize = Get-FolderBytes $Stage
$mySize = (Get-Item "$Stage\MyMods.exe").Length
$bridgeSize = (Get-Item "$Stage\ModBridge.exe").Length
$assetSize = (Get-Item "$Stage\Asset Downloader.exe").Length

$report = @(
  "Standalone VAR-Mods-2026 build",
  "Stage size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "MyMods.exe: $([math]::Round($mySize / 1MB, 2)) MB",
  "ModBridge.exe: $([math]::Round($bridgeSize / 1MB, 2)) MB",
  "Asset Downloader.exe: $([math]::Round($assetSize / 1MB, 2)) MB",
  "Python runtime shipped: NO"
)
$report | Set-Content "$Dist\standalone-size-report.txt" -Encoding UTF8
Get-Content "$Dist\standalone-size-report.txt"
