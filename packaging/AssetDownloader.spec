# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

SPEC_DIR = Path(__file__).resolve().parent
ROOT = SPEC_DIR.parent

a = Analysis(
    [str(ROOT / "PT" / "PES_FootballLife_Asset_Downloader.py")],
    pathex=[str(ROOT / "PT"), str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5"],
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
    disable_windowed_traceback=False,
    argv_emulation=False,
)
