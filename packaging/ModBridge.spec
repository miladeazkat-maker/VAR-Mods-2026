# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

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

# Bundle backend resource files internally for --embedded-backend execution.
runtime_asset_roots = ["GLT", "HeatMap", "MomentumMatch", "SAOTMod", "RefereeView"]
for folder in runtime_asset_roots:
    root = ROOT / folder
    if root.exists():
        for item in root.rglob("*"):
            if item.is_file() and item.suffix.lower() not in {".py", ".pyc", ".pyo"}:
                dest = folder + "/" + str(item.relative_to(root).parent).replace("\\", "/")
                datas.append((str(item), dest))

hiddenimports = [
    # Bridge UI
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtWebEngineCore",

    # Native memory / process packages
    "pymem",
    "pymem.process",
    "pymem.pattern",

    # Backend dependencies
    "numpy",
    "matplotlib",
    "matplotlib.backends.backend_agg",
    "matplotlib.backends.backend_tkagg",
    "matplotlib.ticker",
    "matplotlib.patches",
    "matplotlib.lines",
    "matplotlib.offsetbox",
    "PIL",
    "PIL.Image",
    "PIL.ImageTk",
    "PIL.ImageDraw",
    "PIL.ImageFilter",
    "moderngl",
    "glcontext",
    "glfw",
    "panda3d",
    "panda3d.core",
    "ursina",
    "customtkinter",
    "keyboard",
    "psutil",
    "pywinstyles",

    # Dynamically loaded backend modules
    "GLTMod",
    "HeatMapMod",
    "BroadcastRenderer",
    "SAOTMod",
    "RefereeView",
    "MomentumMod",
]

a = Analysis(
    [str(ROOT / "ModBridge.py")],
    pathex=[
        str(ROOT),
        str(ROOT / "GLT"),
        str(ROOT / "HeatMap"),
        str(ROOT / "SAOTMod"),
        str(ROOT / "RefereeView"),
        str(ROOT / "MomentumMatch"),
    ],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=[
        "PyQt5",
        # PyQt6 modules unrelated to this bridge/backend stack.
        "PyQt6.Qt3DCore",
        "PyQt6.Qt3DAnimation",
        "PyQt6.Qt3DExtras",
        "PyQt6.Qt3DInput",
        "PyQt6.Qt3DLogic",
        "PyQt6.Qt3DRender",
        "PyQt6.Qt3DQuick",
        "PyQt6.Qt3DQuickAnimation",
        "PyQt6.Qt3DQuickExtras",
        "PyQt6.Qt3DQuickInput",
        "PyQt6.Qt3DQuickRender",
        "PyQt6.Qt3DQuickScene2D",
        "PyQt6.Qt3DQuickScene3D",
        "PyQt6.QtSql",
        "PyQt6.QtQuick3D",
        "PyQt6.QtQuick3DAssetUtils",
        "PyQt6.QtQuick3DHelpers",
        "PyQt6.QtQuick3DParticleEffects",
        "PyQt6.QtQuick3DPhysics",
        "PyQt6.QtWebView",
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
    name="ModBridge",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
