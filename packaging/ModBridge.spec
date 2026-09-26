# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

ROOT = Path.cwd().resolve()

backend_datas = []
for folder in ("RefereeView", "GLT", "HeatMap", "MomentumMatch", "SAOTMod"):
    source_root = ROOT / folder
    for item in source_root.rglob("*"):
        if not item.is_file():
            continue
        if "__pycache__" in item.parts:
            continue
        relative = item.relative_to(source_root)
        destination = str(Path(folder) / relative)
        backend_datas.append((str(item), destination))

native_binaries = []
native_datas = []
for _pkg in ("glfw", "moderngl", "panda3d"):
    try:
        native_binaries.extend(collect_dynamic_libs(_pkg))
    except Exception:
        pass
    try:
        native_datas.extend(collect_data_files(_pkg))
    except Exception:
        pass

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
    datas=backend_datas + native_datas,
    binaries=native_binaries,
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
