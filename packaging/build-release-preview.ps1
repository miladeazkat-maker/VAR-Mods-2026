$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Stage = Join-Path $Root "stage"
$Dist = Join-Path $Root "dist"
$Packaging = Join-Path $Root "packaging"

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item $Dist -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Stage, $Dist | Out-Null

Write-Host "== Build launcher EXEs =="
python -m PyInstaller --onefile --noconsole --clean --name "MyMods" "$Packaging\MyMods_launcher.py"
Copy-Item "$Root\dist\MyMods.exe" "$Stage\MyMods.exe" -Force
Remove-Item "$Root\dist\MyMods.exe" -Force

python -m PyInstaller --onefile --noconsole --clean --name "ModBridge" "$Packaging\ModBridge_launcher.py"
Copy-Item "$Root\dist\ModBridge.exe" "$Stage\ModBridge.exe" -Force
Remove-Item "$Root\dist\ModBridge.exe" -Force

python -m PyInstaller --onefile --noconsole --clean --name "Asset Downloader" "$Packaging\AssetDownloader_launcher.py"
Copy-Item "$Root\dist\Asset Downloader.exe" "$Stage\Asset Downloader.exe" -Force

Write-Host "== Copy release application files =="
$topFiles = @("MyMods.py","ModBridge.py","LICENSE","requirements.txt")
foreach($file in $topFiles) {
  Copy-Item (Join-Path $Root $file) (Join-Path $Stage $file) -Force
}
$dirs = @("GLT","HeatMap","MomentumMatch","SAOTMod","RefereeView","PT","Background")
foreach($dir in $dirs) {
  Copy-Item (Join-Path $Root $dir) (Join-Path $Stage $dir) -Recurse -Force
}

Write-Host "== Prepare portable Python runtime =="
$pyVersion = "3.13.13"
$pyInstaller = Join-Path $env:TEMP "python-$pyVersion-amd64.exe"
$pyUrl = "https://www.python.org/ftp/python/$pyVersion/python-$pyVersion-amd64.exe"

Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller
$Runtime = Join-Path $Stage "runtime"
Start-Process -FilePath $pyInstaller -Wait -ArgumentList @(
  "/quiet",
  "InstallAllUsers=0",
  "TargetDir=$Runtime",
  "PrependPath=0",
  "Include_pip=0",
  "Include_launcher=0",
  "Include_test=0",
  "SimpleInstall=0"
)

$RuntimePython = Join-Path $Runtime "python.exe"
$RuntimePythonW = Join-Path $Runtime "pythonw.exe"
if(!(Test-Path $RuntimePython) -or !(Test-Path $RuntimePythonW)) { throw "Portable Python runtime was not created correctly." }

Write-Host "== Install runtime dependencies =="
python -m pip install --upgrade pip
python -m pip install --disable-pip-version-check --no-cache-dir --no-compile --only-binary=:all: --target "$Runtime\Lib\site-packages" -r "$Packaging\runtime-requirements.txt"

Write-Host "== Remove build-only files and caches =="
Get-ChildItem $Runtime -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Runtime -Recurse -File -Include "*.pyc","*.pyo","*.pdb" | Remove-Item -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Scripts" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\pip" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\pip-*.dist-info" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\setuptools" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\setuptools-*.dist-info" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\wheel" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$Runtime\Lib\site-packages\wheel-*.dist-info" -Recurse -Force -ErrorAction SilentlyContinue

Write-Host "== Validate staged runtime =="
$env:PYTHONPATH = "$Runtime\Lib\site-packages"
& $RuntimePython -c "import PyQt6, numpy, PIL, matplotlib, pymem, moderngl, glfw, panda3d, ursina, customtkinter, psutil, pywinstyles; print('Runtime imports OK')"
& $RuntimePython -m py_compile "$Stage\MyMods.py" "$Stage\ModBridge.py" "$Stage\PT\PES_FootballLife_Asset_Downloader.py"
$env:PYTHONPATH = $null

# py_compile creates bytecode caches only for validation; do not ship them.
Get-ChildItem $Stage -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $Stage -Recurse -File -Include "*.pyc","*.pyo" | Remove-Item -Force -ErrorAction SilentlyContinue

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
  return (Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum
}

$stageSize = Get-FolderBytes $Stage
$runtimeSize = Get-FolderBytes $Runtime
$installerSize = (Get-Item $Installer).Length
$launchers = Get-ChildItem $Stage -Filter "*.exe" | Where-Object { $_.Name -in @("MyMods.exe","ModBridge.exe","Asset Downloader.exe") }

$report = @(
  "VAR-Mods-2026 v1.0.0 Release Preview",
  "Stage size: $([math]::Round($stageSize / 1MB, 2)) MB",
  "Shared runtime size: $([math]::Round($runtimeSize / 1MB, 2)) MB",
  "Installer size: $([math]::Round($installerSize / 1MB, 2)) MB",
  "",
  "Application launchers:"
)
foreach($launcher in $launchers) {
  $report += ("  {0}: {1} MB" -f $launcher.Name, [math]::Round($launcher.Length / 1MB, 2))
}
$report += ""
$report += "Installer: $Installer"

$report | Set-Content (Join-Path $Dist "v1.0.0-size-report.txt") -Encoding UTF8
Get-Content (Join-Path $Dist "v1.0.0-size-report.txt")
