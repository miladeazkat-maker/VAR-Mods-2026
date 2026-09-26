# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(ROOT / "PT" / "PES_FootballLife_Asset_Downloader.py")],
    pathex=[str(ROOT / "PT"), str(ROOT)],
    datas=[],
    binaries=[],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    excludes=[
        "PyQt5",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtWebEngineCore",
    ],
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
