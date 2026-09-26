# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.building.datastruct import Tree

ROOT = Path.cwd().resolve()

backend_datas = []
for folder, prefix in (
    ("RefereeView", "RefereeView"),
    ("GLT", "GLT"),
    ("HeatMap", "HeatMap"),
    ("MomentumMatch", "MomentumMatch"),
    ("SAOTMod", "SAOTMod"),
):
    tree = Tree(str(ROOT / folder), prefix=prefix, excludes=["__pycache__"])
    backend_datas.extend(tree)

hiddenimports = [
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "pymem",
    "pymem.process",
    "pymem.pattern",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.ImageDraw",
    "PIL.ImageFilter",
    "PIL.ImageFont",
    "matplotlib",
    "matplotlib.figure",
    "matplotlib.image",
    "matplotlib.colors",
    "matplotlib.ticker",
    "matplotlib.patches",
    "matplotlib.lines",
    "matplotlib.offsetbox",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.font_manager",
    "matplotlib.ft2font",
    "moderngl",
    "glfw",
    "panda3d",
    "panda3d.core",
    "ursina",
    "customtkinter",
    "keyboard",
    "psutil",
    "pywinstyles",
]

a = Analysis(
    [str(ROOT / "ModBridge.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=backend_datas,
    hiddenimports=hiddenimports,
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
    name="ModBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
)
