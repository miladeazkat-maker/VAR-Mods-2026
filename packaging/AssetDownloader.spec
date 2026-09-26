# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).resolve().parent

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
]
try:
    _, _, qt_hidden = collect_all("PyQt6")
    hiddenimports += qt_hidden
except Exception:
    pass

qt_datas, qt_bins, _ = collect_all("PyQt6")
datas = qt_datas
binaries = qt_bins

a = Analysis(
    [str(ROOT / "PT" / "PES_FootballLife_Asset_Downloader.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["PyQt5", "PyQt6.QtWebEngineWidgets", "PyQt6.QtWebEngineCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Asset Downloader",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
