# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent

backend_sources = [
    (ROOT / "GLT" / "GLTMod.py", "GLT"),
    (ROOT / "HeatMap" / "HeatMapMod.py", "HeatMap"),
    (ROOT / "HeatMap" / "BroadcastRenderer.py", "HeatMap"),
    (ROOT / "SAOTMod" / "SAOTMod.py", "SAOTMod"),
    (ROOT / "RefereeView" / "RefereeView.py", "RefereeView"),
    (ROOT / "MomentumMatch" / "MomentumMod.py", "MomentumMatch"),
]
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
    (ROOT / "MomentumMatch" / "modules" / name, "MomentumMatch/modules")
    for name in momentum_modules
]

datas = [(str(src), dest) for src, dest in backend_sources]

# Backend assets are bundled as internal resources. The installed copy of
# these files is still kept for frontend previews/configuration, but ModBridge
# must also work when its backend code executes from PyInstaller's bundle.
runtime_asset_roots = [
    ("GLT", "GLT"),
    ("HeatMap", "HeatMap"),
    ("MomentumMatch", "MomentumMatch"),
    ("SAOTMod", "SAOTMod"),
    ("RefereeView", "RefereeView"),
]
for folder, dest in runtime_asset_roots:
    root = ROOT / folder
    if root.exists():
        for item in root.rglob("*"):
            if item.is_file() and item.suffix.lower() not in {".py", ".pyc", ".pyo"}:
                datas.append((str(item), dest + "/" + str(item.relative_to(root).parent).replace("\\", "/")))
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
    [str(ROOT / "ModBridge.py")],
    pathex=[str(ROOT)],
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
