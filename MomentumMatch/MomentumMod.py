# -*- coding: utf-8 -*-
"""
Match Momentum modular loader.

The implementation is split into focused source files under modules/.
Each component is executed in the original module namespace, preserving
the legacy public API, initialization order, globals, and entry points.
"""

from pathlib import Path as _MomentumPath

_MOMENTUM_MODULE_DIR = _MomentumPath(__file__).resolve().parent / "modules"

_MOMENTUM_MODULES = (
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
)

for _momentum_module_name in _MOMENTUM_MODULES:
    _momentum_module_path = _MOMENTUM_MODULE_DIR / _momentum_module_name
    with _momentum_module_path.open("r", encoding="utf-8") as _momentum_file:
        _momentum_source = _momentum_file.read()
    exec(compile(
        _momentum_source,
        str(_momentum_module_path),
        "exec",
    ), globals(), globals())

del _momentum_module_name
del _momentum_module_path
del _momentum_source
del _momentum_file
del _MOMENTUM_MODULE_DIR
del _MomentumPath
del _MOMENTUM_MODULES

if __name__ == "__main__":
    if "--render-archive" in sys.argv:
        try:
            _idx = sys.argv.index("--render-archive")
            _path = sys.argv[_idx + 1] if len(sys.argv) > _idx + 1 else ""
            if not _path:
                print("usage: python MomentumMod.py --render-archive "
                      "<archive.zip|match_data.json>")
                sys.exit(2)
            _out = render_archive_chart(_path)
            if _out:
                print("CHART RENDERED: " + str(_out))
                sys.exit(0)
            print("RENDER FAILED: " + str(_path))
            sys.exit(1)
        except SystemExit:
            raise
        except Exception as _ex:
            print(f"RENDER ERROR: {type(_ex).__name__}: {_ex}")
            sys.exit(1)
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()
