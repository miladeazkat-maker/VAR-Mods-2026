import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(sys.executable).resolve().parent
PYTHON_EXE = ROOT_DIR / "runtime" / "pythonw.exe"
SCRIPT = ROOT_DIR / "ModBridge.py"

def fail(message):
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, "VAR-Mods-2026", 0x10)
    except Exception:
        pass
    return 1

def main():
    if not PYTHON_EXE.exists():
        return fail(f"Embedded Python runtime not found:\n{PYTHON_EXE}")
    if not SCRIPT.exists():
        return fail(f"Application script not found:\n{SCRIPT}")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    try:
        return subprocess.call(
            [str(PYTHON_EXE), str(SCRIPT), *sys.argv[1:]],
            cwd=str(ROOT_DIR),
            env=env,
        )
    except Exception as exc:
        return fail(f"Failed to start the application:\n{exc}")

if __name__ == "__main__":
    raise SystemExit(main())
