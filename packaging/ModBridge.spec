# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Backend source files are embedded as runtime data. They are extracted only
# into PyInstaller's temporary _MEIPASS directory while ModBridge is running.
backend_sources = [
    ("GLT/GLTMod.py", "GLT"),
    ("HeatMap/HeatMapMod.py", "HeatMap"),
    ("HeatMap/BroadcastRenderer.py", "HeatMap"),
    ("SAOTMod/SAOTMod.py", "SAOTMod"),
    ("RefereeView/RefereeView.py", "RefereeView"),
    ("MomentumMatch/MomentumMod.py", "MomentumMatch"),
]
for i in range(1, 13):
    if i == 11:
        continue
    path = f"MomentumMatch/modules/{i:02d}_"
    # The module filenames are handled explicitly below because names include
    # descriptive suffixes and are not guaranteed to be sequential.
momentum_modules = [
    "01_runtime.py",
    "02_memory.py",
    "03_models.py",
    "04_engines.py",
    "05_chart_tv.py",
    "06_snapshot_core.py",
    "07_overlay_renderers.py",
    "08_scene_archive.py",
    "09_team_identity.py",
    "10_app_gui_snapshot.py",
    "12_selftest_entry.py",
]
backend_sources += [
    (f"MomentumMatch/modules/{name}", "MomentumMatch/modules")
    for name in momentum_modules
]

datas = backend_sources
binaries = []
hiddenimports = [
    "PyQt6",
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",
    "pymem",
    "pymem.process",
    "pymem.pattern",
    "numpy",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "moderngl",
    "glcontext",
    "glfw",
    "panda3d",
    "ursina",
]
for pkg in ("PyQt6", "matplotlib", "panda3d", "ursina", "moderngl", "glcontext", "glfw", "PIL", "pymem"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        try:
            hiddenimports += collect_submodules(pkg)
        except Exception:
            pass

a = Analysis(
    ["ModBridge.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
)
