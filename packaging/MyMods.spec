# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent.parent

hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtMultimedia",
]
try:
    hiddenimports += collect_submodules("PyQt6.QtMultimedia")
except Exception:
    pass

qt_datas, qt_bins, qt_hidden = collect_all("PyQt6")
datas = qt_datas
binaries = qt_bins
hiddenimports += qt_hidden

a = Analysis(
    [str(ROOT / "MyMods.py")],
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
    name="MyMods",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
