# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

ROOT = Path.cwd().resolve()

a = Analysis(
    [str(ROOT / "MyMods.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "PyQt6.QtMultimedia",
        "PyQt6.QtMultimediaWidgets",
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
    name="MyMods",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
