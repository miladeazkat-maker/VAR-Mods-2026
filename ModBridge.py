# -*- coding: utf-8 -*-
# [PROJECT RULE — DO NOT REMOVE] ENGLISH ONLY: this project must NEVER contain any Persian/Farsi text (UI strings, comments, docs).
# =============================================================================
#  ModBridge.py — MID END (layer 2 / the bridge)
# -----------------------------------------------------------------------------
#  Duties of this layer (exactly per the three-layer design):
#   1) Opens with a simple window so the user can see it is running.
#   2) Reads the user settings from ModsConfig.json and feeds each mod backend.
#   3) Runs as Administrator (direct ShellExecuteW, no cmd.exe and no
#      SysWOW64 jump) and attaches to the FL_2026.exe process.
#   4) It is the ONLY layer allowed to touch game memory: every hook,
#      injection and patch is applied from here so the game never crashes.
#   5) If two mods want the same address: the hook/patch is applied ONCE and
#      both mods are fed from one shared source (buffer). If two mods want
#      DIFFERENT bytes at the same address, the second request is rejected so
#      no invalid hook is installed and the game stays stable.
#   6) Listens to the user keys (chosen in the frontend) through a low-level
#      Windows keyboard hook (layout independent).
#   7) QUICK MODS card: compact live enable/disable switches for every mod.
#
#  Backend contract: each mod backend (the python file inside the mod folder,
#  no UI) is loaded dynamically into this process and only talks through
#  BridgeAPI; no backend ever touches game memory directly.
# ==============================================================================

import sys
import os
import json
import time
import queue
import struct
import ctypes
import socket
import secrets
import threading
import traceback
import importlib.util
import subprocess
from ctypes import wintypes

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Same field bug reported on the Heat Map backend: when stdout/stderr is
# a FILE or PIPE (spawned child streams, redirected runs) Python uses
# the legacy ANSI 'charmap' codec (cp1252), and ONE print of a
# non-Latin-1 string (a mod log line echoed with an Arabic/Persian name
# from game memory) raises UnicodeEncodeError that can kill a bridge
# thread. Hardened: console -> UTF-8 codepage, streams -> utf-8 +
# errors='replace', and a wrapper so a failing write degrades to
# sanitized ASCII, never raises.
# ---------------------------------------------------------------------
class _CrashProofStream:
    """write()/flush() can never raise; every other attribute is delegated."""

    def __init__(self, stream):
        self._s = stream

    def write(self, s):
        try:
            return self._s.write(s)
        except Exception:
            try:
                return self._s.write(
                    str(s).encode("ascii", "replace").decode("ascii"))
            except Exception:
                try:
                    return len(s)
                except Exception:
                    return 0

    def flush(self):
        try:
            self._s.flush()
        except Exception:
            pass

    def __getattr__(self, attr):
        return getattr(self._s, attr)


def _suite_harden_stdio():
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for _st in (sys.stdout, sys.stderr):
        if _st is None:
            continue                                  # pythonw / detached
        try:
            if hasattr(_st, "reconfigure"):
                _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stdout is not None and not isinstance(sys.stdout, _CrashProofStream):
        sys.stdout = _CrashProofStream(sys.stdout)
    if sys.stderr is not None and not isinstance(sys.stderr, _CrashProofStream):
        sys.stderr = _CrashProofStream(sys.stderr)


_suite_harden_stdio()


def _fatal_box(msg):
    try:
        ctypes.windll.user32.MessageBoxW(None, msg, "Mod Bridge", 0x10)
    except Exception:
        pass

def global_exception_handler(exctype, value, tb):
    txt = "".join(traceback.format_exception(exctype, value, tb))
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[" + time.strftime("%Y-%m-%d %H:%M:%S") + "] FATAL\n" + txt + "\n")
    except Exception:
        pass
    _fatal_box("An error occurred in Mod Bridge:\n" + str(value))
    sys.exit(1)

if getattr(sys, 'frozen', False):
    ROOT_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
BUNDLE_DIR = os.path.abspath(getattr(sys, "_MEIPASS", ROOT_DIR))
os.chdir(ROOT_DIR)

LOG_FILE = os.path.join(ROOT_DIR, "ModBridge_log.txt")
CONFIG_FILE = os.path.join(ROOT_DIR, "ModsConfig.json")
PROCESS_NAME = "FL_2026.exe"

# [suite] v2.1.6 / v1.0.0b — donation link (same policy as MyMods.py):
# LIVE — the DONATE buttons open the developer's NOWPayments page in the
# browser.  While it is empty the donate dialog only shows the message.
DONATE_URL = "https://nowpayments.io/donation/Milad"

# [suite] v2.1.6 (user spec #6) — AUTO MOD ACTIVATION SEQUENCE:
# the bridge keeps EVERY mod disabled while the game is not running.
# This many seconds after FL_2026.exe is detected, the mods marked
# enabled in ModsConfig.json are activated IN ORDER (registry order),
# each staggered so they never all patch at the same moment.
AUTO_ACT_DELAY_SEC = 3.0
AUTO_ACT_STAGGER_SEC = 1.2

def _log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[" + time.strftime("%Y-%m-%d %H:%M:%S") + "] " + msg + "\n")
    except Exception:
        pass

# -------------------------------------------------------------
# -------------------------------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def relaunch_as_admin():
    if getattr(sys, 'frozen', False):
        exe = sys.executable
        params = " ".join([f'"{a}"' for a in sys.argv[1:]])
    else:
        exe = sys.executable
        params = f'"{os.path.abspath(sys.argv[0])}"'
    res = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, ROOT_DIR, 1)
    return int(res) > 32

if sys.platform == "win32" and not is_admin():
    if relaunch_as_admin():
        sys.exit(0)
    _fatal_box("Mod Bridge must run as Administrator. Please approve the UAC prompt.")

# -------------------------------------------------------------
# Single instance guard (named mutex)
# -------------------------------------------------------------
def acquire_single_instance():
    try:
        ctypes.windll.kernel32.CreateMutexW(None, False, "Global\\FL2026_ModBridge_SingleInstance")
        return ctypes.windll.kernel32.GetLastError() != 183  # 183 = ERROR_ALREADY_EXISTS
    except Exception:
        return True

# -------------------------------------------------------------
# PyQt Imports
# -------------------------------------------------------------
try:
    from PyQt6.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QUrl
    from PyQt6.QtGui import (QFont, QColor, QPainter, QBrush, QPen,
                             QLinearGradient, QRadialGradient, QPolygonF,
                             QPainterPath, QDesktopServices)
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QDialog
    )
    IS_PYQT6 = True
except ImportError:
    from PyQt5.QtCore import Qt, QTimer, QRect, QRectF, QPointF, QUrl
    from PyQt5.QtGui import (QFont, QColor, QPainter, QBrush, QPen,
                             QLinearGradient, QRadialGradient, QPolygonF,
                             QPainterPath, QDesktopServices)
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect, QDialog
    )
    IS_PYQT6 = False

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtCore import QUrl
    from PyQt6.QtGui import QColor as _QC
    WEBENGINE_OK = True
except Exception:
    try:
        from PyQt5.QtWebEngineWidgets import QWebEngineView
        from PyQt5.QtWebEngineCore import QWebEngineSettings
        from PyQt5.QtCore import QUrl
        from PyQt5.QtGui import QColor as _QC
        WEBENGINE_OK = True
    except Exception:
        WEBENGINE_OK = False

try:
    import pymem
    import pymem.process
    import pymem.pattern
    PYMEM_OK = True
except Exception:
    PYMEM_OK = False

# -------------------------------------------------------------
# -------------------------------------------------------------
if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    kernel32.VirtualAllocEx.restype = ctypes.c_ulonglong
    kernel32.VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]
    kernel32.VirtualProtectEx.restype = ctypes.c_int
    kernel32.VirtualProtectEx.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_size_t, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    kernel32.WriteProcessMemory.restype = ctypes.c_int
    kernel32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_ulonglong, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

# =============================================================================
# =============================================================================
MOD_REGISTRY = {
    "Referee View": {
        "folder": "RefereeView",
        "module": "RefereeView",
        "class": "RefereeBackend",
    },
    # Goal Line Technology v3 runs as its own Administrator child process:
    # it is the user's ORIGINAL GLT2021 tool (full tkinter control panel +
    # ursina goal scene) kept 1:1 verbatim, so it must own its main thread
    # and its own hotkeys. The bridge only spawns/monitors it. glt_stop.flag
    # asks the tool to shut down gracefully (full memory restore) instead of
    # being killed.
    "Goal Line Technology": {
        "folder": "GLT",
        "module": "GLTMod",
        "class": "GLTBackend",      # unused in process mode (kept for reference)
        "mode": "process",
        "stop_flag": "glt_stop.flag",
    },
    # Match Momentum runs as its own Administrator child process: it is the
    # headless build of the standalone momentum engine (own memory hooks +
    # GPU overlay), so the bridge only spawns/monitors it — it never loads
    # it into this process.
    "Match Momentum": {
        "folder": "MomentumMatch",
        "module": "MomentumMod",
        "class": "MomentumApp",
        "mode": "process",
    },
    # Heat Map v1.0 runs as its own Administrator child process (same
    # architecture as Match Momentum): 30 Hz density tracker + GPU broadcast
    # overlay + hidden control panel (Ctrl+Alt+5). The bridge spawns and
    # monitors it; its THREE game hooks (ball 0x176A3A2 / time 0x20F1CDA /
    # player-code 0xA83964) are all requested from the HookBroker below —
    # the ball site is SHARED with Match Momentum, the time site is shared
    # with Momentum's local TimeHooker (adopt), the pcode site is unique.
    "Heat Map": {
        "folder": "HeatMap",
        "module": "HeatMapMod",
        "class": "PESLaLigaApp",
        "mode": "process",
    },
    # S.A.O.T v2.1.7 (Semi-Automated Offside Technology) runs as its own
    # Administrator child process: the familiar Milad77 tool GUI (view
    # picker / plane ON-OFF / distance slider) summoned in-game with the
    # CALL KEY from MyMods. THE MOD HOOKS NOTHING (user spec #8): it only
    # reads/writes game memory through its pointer chains, and it gets the
    # game pid/base from the bridge's game_status IPC — never scans the
    # process list while this bridge is answering.
    "S.A.O.T": {
        "folder": "SAOTMod",
        "module": "SAOTMod",
        "class": "SAOTApp",
        "mode": "process",
    },
}

DEFAULT_CONFIG = {
    "config_version": 3,
    "game_process": PROCESS_NAME,
    "mods": {
        "Referee View": {
            "enabled": False,
            "show_video_overlay": True,
            "apply_key_vk": "0x54",
            "apply_key_name": "T",
        },
        "Goal Line Technology": {
            "enabled": False,
            "glt_play_vk": "0x77",
            "glt_play_name": "F8",
            "glt_rec_vk": "0x76",
            "glt_rec_name": "F7",
            "glt_style": "T6",
        },
        "Heat Map": {
            "enabled": False,
        },
        "S.A.O.T": {
            "enabled": False,
            "apply_key_vk": "0x70",
            "apply_key_name": "F1",
        },
    },
}

def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        else:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        _log(f"config load failed: {e}")
    return cfg

class BridgeError(Exception):
    pass

# =============================================================================
# =============================================================================
class GlobalKeyListener(threading.Thread):
    WH_KEYBOARD_LL = 13
    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105
    WM_QUIT = 0x0012

    def __init__(self, vk_code, on_press):
        super().__init__(daemon=True)
        self.vk_code = int(vk_code) & 0xFF
        self.on_press = on_press
        self._down = False
        self._stop_evt = threading.Event()
        self.user32 = ctypes.windll.user32
        LRESULT = ctypes.c_ssize_t
        self.HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        self._proc_ref = self.HOOKPROC(self._proc)
        self._hook = None
        self.user32.SetWindowsHookExW.restype = ctypes.c_void_p
        self.user32.SetWindowsHookExW.argtypes = [ctypes.c_int, self.HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        self.user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        self.user32.CallNextHookEx.restype = LRESULT
        self.user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        self.user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
        self.user32.PostThreadMessageW.argtypes = [wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [("vkCode", wintypes.DWORD),
                    ("scanCode", wintypes.DWORD),
                    ("flags", wintypes.DWORD),
                    ("time", wintypes.DWORD),
                    ("dwExtraInfo", ctypes.c_void_p)]

    def _proc(self, n_code, w_param, l_param):
        try:
            if n_code == 0:
                kb = ctypes.cast(l_param, ctypes.POINTER(GlobalKeyListener.KBDLLHOOKSTRUCT)).contents
                if kb.vkCode == self.vk_code:
                    if w_param in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN):
                        if not self._down:
                            self._down = True
                            try:
                                self.on_press()
                            except Exception:
                                pass
                    elif w_param in (self.WM_KEYUP, self.WM_SYSKEYUP):
                        self._down = False
        except Exception:
            pass
        return self.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def run(self):
        try:
            self._hook = self.user32.SetWindowsHookExW(
                self.WH_KEYBOARD_LL, self._proc_ref, None, 0)
            if not self._hook:
                _log("SetWindowsHookExW failed")
                return
            msg = wintypes.MSG()
            while not self._stop_evt.is_set():
                r = self.user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if r <= 0:
                    break
        except Exception as e:
            _log(f"key listener crashed: {e}")
        finally:
            if self._hook:
                try:
                    self.user32.UnhookWindowsHookEx(self._hook)
                except Exception:
                    pass

    def stop(self):
        self._stop_evt.set()
        try:
            self.user32.PostThreadMessageW(self.ident, self.WM_QUIT, 0, 0)
        except Exception:
            pass

# =============================================================================
# =============================================================================
class CodeBuilder:
    def __init__(self, start_addr):
        self.code = bytearray()
        self.start_addr = start_addr

    def get_ip(self):
        return self.start_addr + len(self.code)

    def add(self, bytes_data):
        self.code += bytes_data

    def add_mov_reg_rel32(self, prefix, target_addr):
        self.add(prefix)
        rel = int(target_addr - (self.get_ip() + 4))
        self.add(struct.pack('<i', rel))

    def add_jmp(self, target_addr):
        self.add(b'\xE9')
        rel = int(target_addr - (self.get_ip() + 4))
        self.add(struct.pack('<i', rel))

# =============================================================================
# =============================================================================
class BridgeAPI:
    def __init__(self, bridge, mod_id):
        self._bridge = bridge
        self.mod_id = mod_id

    @property
    def connected(self):
        return self._bridge.connected

    def base(self):
        base = self._bridge.base_address
        if not base:
            raise BridgeError("not connected")
        return base

    def log(self, msg):
        self._bridge.log(f"[{self.mod_id}] {msg}")

    def status(self, text, color="#93c5fd"):
        self._bridge.status(f"[{self.mod_id}] {text}", color)

    def read_int(self, addr):
        return self._bridge.mem_read_int(addr)

    def read_longlong(self, addr):
        return self._bridge.mem_read_longlong(addr)

    def read_float(self, addr):
        return self._bridge.mem_read_float(addr)

    def read_bytes(self, addr, size):
        return self._bridge.mem_read_bytes(addr, size)

    def write_float(self, addr, value):
        self._bridge.mem_write_float(addr, value)

    def write_bytes(self, addr, data):
        self._bridge.mem_write_bytes(addr, data)

    def register_patch(self, addr, new_bytes, note=""):
        return self._bridge.register_patch(self.mod_id, addr, new_bytes, note)

    def apply_patch(self, addr):
        self._bridge.apply_patch(self.mod_id, addr)

    def revert_patch(self, addr):
        self._bridge.revert_patch(self.mod_id, addr)

    def request_ball_hook(self, site_addr, orig_bytes, nop_count):
        return self._bridge.request_data_hook(self.mod_id, site_addr, orig_bytes, nop_count)

    def release_ball_hook(self, site_addr):
        self._bridge.release_data_hook(self.mod_id, site_addr)

    def request_camera_control(self):
        return self._bridge.request_camera_control(self.mod_id)

    def release_camera_control(self):
        self._bridge.release_camera_control(self.mod_id)

    def pattern_scan(self, pattern):
        return self._bridge.pattern_scan(pattern)

    def overlay_show(self):
        self._bridge.ui_events.put(("overlay_show",))

    def overlay_hide(self):
        self._bridge.ui_events.put(("overlay_hide",))

# =============================================================================
# =============================================================================
class Bridge:
    def __init__(self, cfg):
        self.cfg = cfg
        self.lock = threading.RLock()

        self.pm = None
        self.base_address = None
        self.alloc_base = None
        self.connected = False
        # [suite] v2.1.5 — the bridge is the SINGLE detector of FL_2026.exe
        # (mods ASK, they never scan): remember the game pid so the
        # HookBroker can answer game_status queries from the mod children.
        self.game_pid = None

        self.patches = {}    # addr -> {orig, cur, note, refs:{mod: applied_bool}, applied}
        self.hooks = {}      # site -> {orig, nop, cave, buffer, refs:set, applied}
        self.camera_owner = None

        self.backends = {}   # mod_name -> BackendHost
        self.status_q = queue.Queue()
        self.ui_events = queue.Queue()
        self.key_events = queue.Queue()

        self.stop_flag = threading.Event()
        self.key_listeners = []
        self.overlay = None
        self.overlay_visible = False

        # [suite] v2.0.6 — the single owner of all hook bytes (see HookBroker)
        self.hook_broker = None

        # [suite] v2.1.6 (user spec #6) — AUTO MOD ACTIVATION: connect_loop
        # queues enabled mod names here ~3 s after the game is detected;
        # the GUI thread drains the queue in drain_queues() and starts the
        # hosts through the exact same code path as the quick-mods buttons.
        self.activation_q = queue.Queue()
        self.auto_activation_done = False

    # ------------------------------------------------------------------
    # Logging / status
    # ------------------------------------------------------------------
    def log(self, msg):
        _log(msg)
        self.status_q.put((msg, "#93c5fd", False))

    def status(self, text, color="#93c5fd"):
        self.status_q.put((text, color, True))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def connect_loop(self):
        if not PYMEM_OK:
            self.status("pymem is not installed — run: pip install pymem", "#ff4770")
            return
        while not self.stop_flag.is_set():
            if not self.connected:
                try:
                    self.pm = pymem.Pymem(PROCESS_NAME)
                except Exception as e:
                    cname = e.__class__.__name__
                    if cname == "ProcessNotFound":
                        self.status("Waiting for FL_2026.exe ... (start the game first)", "#f39c12")
                    elif cname == "CouldNotOpenProcess":
                        self.status("Access denied — Mod Bridge must run as Administrator", "#ff4770")
                    else:
                        self.status(f"Open process failed ({cname})", "#ff4770")
                    self.stop_flag.wait(2.0)
                    continue
                try:
                    module = pymem.process.module_from_name(self.pm.process_handle, PROCESS_NAME)
                    if not module:
                        self.status("Process opened but module not found (bitness mismatch?)", "#ff4770")
                        self.pm = None
                        self.stop_flag.wait(2.0)
                        continue
                    with self.lock:
                        self.base_address = module.lpBaseOfDll
                        if not self.alloc_base:
                            self.alloc_base = self._alloc_near(self.base_address, 4096)
                        if not self.alloc_base:
                            self.status("Memory allocation near game module failed", "#ff4770")
                            self.pm = None
                            self.stop_flag.wait(2.0)
                            continue
                        self.connected = True
                        # [suite] v2.1.5 — capture the game pid for game_status
                        try:
                            _gpid = getattr(self.pm, "process_id", None)
                            if not _gpid and sys.platform == "win32":
                                _gpid = ctypes.windll.kernel32.GetProcessId(
                                    self.pm.process_handle)
                            self.game_pid = int(_gpid) if _gpid else None
                        except Exception:
                            self.game_pid = None
                    self.status(f"CONNECTED to FL_2026.exe  (base 0x{self.base_address:X})", "#2ecc71")
                    self.log(f"connected, base=0x{self.base_address:X}, "
                             f"alloc=0x{self.alloc_base:X}, "
                             f"pid={self.game_pid if self.game_pid else '?'}")
                    # [suite] v2.1.6 (user spec #6) — every mod is disabled
                    # while the game is closed. The activation sequence
                    # thread waits 3 s from THIS moment, then queues the
                    # enabled mods for activation in order.
                    self.status("FL_2026.exe detected — mods activate "
                                "automatically in 3 s ...", "#f39c12")
                    threading.Thread(target=self._auto_activation_sequence,
                                     daemon=True, name="AutoActivate").start()
                except Exception as e:
                    self.log(f"connect error: {e.__class__.__name__}: {e}")
                    self.pm = None
                    self.stop_flag.wait(2.0)
                    continue
            else:
                try:
                    self.pm.read_bytes(self.base_address, 1)
                except Exception:
                    self._on_game_lost()
                self.stop_flag.wait(2.0)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _auto_activation_sequence(self):
        """[suite] v2.1.6 (user spec #6) — runs in its own daemon thread:
        wait AUTO_ACT_DELAY_SEC seconds after the game launch was detected,
        then queue every enabled-but-not-running mod for activation, in
        MOD_REGISTRY order, staggered AUTO_ACT_STAGGER_SEC apart so the
        mods come up one after another instead of all at once.  The GUI
        thread performs the actual start (drain_queues -> _on_quick_toggle).
        Aborts cleanly if the bridge stops or the game disappears again."""
        if self.stop_flag.wait(AUTO_ACT_DELAY_SEC):
            return
        if not self.connected:
            return
        mods_cfg = self.cfg.get("mods", {})
        pending = [name for name in MOD_REGISTRY
                   if bool(mods_cfg.get(name, {}).get("enabled", False))
                   and name not in self.backends]
        if not pending:
            self.log("auto activation: no mods staged — nothing to activate")
            self.auto_activation_done = True
            return
        self.log(f"auto activation: {len(pending)} mod(s) in order — "
                 f"{', '.join(pending)}")
        for i, name in enumerate(pending, 1):
            if self.stop_flag.is_set() or not self.connected:
                return
            self.activation_q.put(name)
            self.log(f"[{name}] queued for activation ({i}/{len(pending)})")
            if i < len(pending):
                self.stop_flag.wait(AUTO_ACT_STAGGER_SEC)
        self.auto_activation_done = True

    def _on_game_lost(self):
        with self.lock:
            self.connected = False
            self.patches.clear()
            self.hooks.clear()
            self.camera_owner = None
            self.pm = None
            self.base_address = None
            self.alloc_base = None
            self.game_pid = None
        self.status("FL_2026.exe closed — waiting for the game ...", "#f39c12")
        # [suite] v2.1.6 (user spec #6) — ALL mods are disabled again when
        # the game closes (they will auto-activate 3 s after the next
        # launch).  The enabled flags in ModsConfig.json are preserved so
        # the activation sequence knows what to bring back.
        for name, host in list(self.backends.items()):
            try:
                host.stop()
            except Exception:
                pass
            self.log(f"[{name}] DEACTIVATED — game closed (auto-activates "
                     "3 s after the next game launch)")
        self.backends.clear()
        self.auto_activation_done = False

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _ensure(self):
        if not self.connected or self.pm is None or not self.base_address:
            raise BridgeError("not connected")

    def mem_read_int(self, addr):
        with self.lock:
            self._ensure()
            return self.pm.read_int(addr)

    def mem_read_longlong(self, addr):
        with self.lock:
            self._ensure()
            return self.pm.read_longlong(addr)

    def mem_read_float(self, addr):
        with self.lock:
            self._ensure()
            return self.pm.read_float(addr)

    def mem_read_bytes(self, addr, size):
        with self.lock:
            self._ensure()
            return bytes(self.pm.read_bytes(addr, size))

    def mem_write_float(self, addr, value):
        with self.lock:
            self._ensure()
            self.pm.write_float(addr, float(value))

    def mem_write_bytes(self, addr, data):
        with self.lock:
            self._ensure()
            if isinstance(data, bytearray):
                data = bytes(data)
            self.pm.write_bytes(addr, data, len(data))

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _alloc_near(self, base_addr, size):
        for offset in range(0x10000, 0x7FFF0000, 0x10000):
            for direction in (1, -1):
                target_addr = base_addr + (offset * direction)
                try:
                    res = kernel32.VirtualAllocEx(self.pm.process_handle, ctypes.c_ulonglong(target_addr),
                                                  ctypes.c_size_t(size), 0x3000, 0x40)
                    if res:
                        return res
                except Exception:
                    pass
        return None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def register_patch(self, mod_id, addr, new_bytes, note=""):
        new_bytes = bytes(new_bytes)
        with self.lock:
            self._ensure()
            rec = self.patches.get(addr)
            if rec is None:
                try:
                    orig = bytes(self.pm.read_bytes(addr, len(new_bytes)))
                except Exception as e:
                    self.log(f"[{mod_id}] patch register read failed @0x{addr:X}: {e}")
                    return None
                rec = {"orig": orig, "cur": new_bytes, "note": note, "refs": {mod_id: False}, "applied": False}
                self.patches[addr] = rec
                self.log(f"[{mod_id}] patch registered @0x{addr:X} ({note})")
            else:
                if rec["cur"] != new_bytes:
                    self.log(f"[{mod_id}] PATCH CONFLICT @0x{addr:X} ({note}) — request rejected, "
                             f"already owned with different bytes")
                    return None
                rec["refs"].setdefault(mod_id, False)
                self.log(f"[{mod_id}] patch SHARED @0x{addr:X} ({note})")
            return addr

    def apply_patch(self, mod_id, addr):
        with self.lock:
            rec = self.patches.get(addr)
            if rec is None or mod_id not in rec["refs"]:
                self.log(f"[{mod_id}] apply_patch: not registered @0x{addr:X}")
                return
            rec["refs"][mod_id] = True
            if not rec["applied"]:
                self._ensure()
                try:
                    if isinstance(rec["cur"], bytearray):
                        rec["cur"] = bytes(rec["cur"])
                    self.pm.write_bytes(addr, rec["cur"], len(rec["cur"]))
                    rec["applied"] = True
                    self.log(f"[{mod_id}] patch applied @0x{addr:X} ({rec['note']})")
                except Exception as e:
                    self.log(f"[{mod_id}] patch apply failed @0x{addr:X}: {e}")

    def revert_patch(self, mod_id, addr):
        with self.lock:
            rec = self.patches.get(addr)
            if rec is None:
                return
            if mod_id in rec["refs"]:
                rec["refs"][mod_id] = False
            if rec["applied"] and not any(rec["refs"].values()):
                try:
                    self._ensure()
                    self.pm.write_bytes(addr, rec["orig"], len(rec["orig"]))
                    rec["applied"] = False
                    self.log(f"patch reverted @0x{addr:X} ({rec['note']})")
                except Exception as e:
                    self.log(f"patch revert failed @0x{addr:X}: {e}")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # v2.0.1 — data-hook fixes
    # 1) ADDRESS NORMALIZATION: backends (Referee View / GLT) request the
    #    ball hook with an ABSOLUTE address (base + offset). The old code
    #    added the module base a SECOND time and wrote the patch to a
    #    bogus address — WriteProcessMemory failed, the hook returned None
    #    and ball tracking never worked. Now both conventions accepted.
    # 2) HOOK COEXISTENCE: the Match Momentum child process installs its
    #    own hook on the SAME ball site (FL_2026.exe+0x176A3A2) from its
    #    own process. If this site is already hooked (E9), the bridge now
    #    ADOPTS the existing cave and reads its data buffer instead of
    #    overwriting it — one live hook feeds every consumer, and the
    #    momentum integrity check can adopt a bridge-style cave back.
    # ------------------------------------------------------------------
    BRIDGE_CAVE_SIG  = b'\x0F\x11\x05'                  # movups [rel32], xmm0
    MOMENTUM_CAVE_SIG = b'\x0F\x29\x80\x50\x04\x00\x00'  # original movaps first

    @staticmethod
    def _parse_cave_buffer_addr(cave_addr, code, kind="xmm0"):
        """Find the data buffer an existing cave writes the captured value
        into. Returns the absolute buffer address or None.
        kind xmm0 : rip-relative movups @code start, or momentum's orig-first
                    layout with the data slot at cave+64
        kind rsi  : orig + 50 9C 48 89 F0 48 A3 + imm64 (RSI slot)
        kind r12d : orig + 50 9C 44 89 E0 48 A3 + imm64 (r12d slot)"""
        try:
            code = bytes(code)
            if kind == "rsi":
                # code here starts at the cave CODE (adopt passes cave+0x20)
                return None  # handled by _parse_kind_slot (needs orig bytes)
            if kind == "r12d":
                return None
            if code[0:3] == Bridge.BRIDGE_CAVE_SIG and len(code) >= 7:
                rel = struct.unpack('<i', code[3:7])[0]
                return cave_addr + 7 + rel              # movups [rip-style rel32]
            if code[0:7] == Bridge.MOMENTUM_CAVE_SIG:
                return cave_addr + 64                   # momentum data slot
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_kind_slot(code, orig_bytes, kind):
        """Parse an orig-first capture cave (rsi/r12d kinds). `code` begins
        at the cave CODE (cave+0x20). Returns the imm64 data-slot address or
        None. Byte patterns are identical to Momentum's local TimeHooker
        cave (rsi) and HeatMap's local pcode cave (r12d), so a cave built
        by ANY of the three programs is adoptable by the bridge."""
        try:
            orig = bytes(orig_bytes)
            code = bytes(code)
            if kind == "rsi":
                tail = Bridge.RSI_CAPTURE_TAIL
                head = len(orig) + len(tail)
                if code[0:len(orig)] != orig or code[len(orig):head] != tail:
                    return None
                slot = struct.unpack('<Q', code[head:head + 8])[0]
            elif kind == "r12d":
                tail = Bridge.R12D_CAPTURE_TAIL
                head = len(orig) + len(tail)
                if code[0:len(orig)] != orig or code[len(orig):head] != tail:
                    return None
                slot = struct.unpack('<Q', code[head:head + 8])[0]
            else:
                return None
            if slot and slot >= 0x10000:
                return slot
        except Exception:
            pass
        return None

    def _adopt_existing_hook(self, mod_id, site, orig_bytes, kind="xmm0"):
        """If site already holds a live E9 hook (e.g. momentum's), adopt it:
        build a hook record whose buffer is the existing cave's data slot.
        Returns the record or None (site not hooked / cave unreadable)."""
        try:
            curr = self.pm.read_bytes(site, 7)
        except Exception:
            return None
        if not curr or curr[0] != 0xE9:
            return None
        try:
            rel = struct.unpack('<i', bytes(curr[1:5]))[0]
            cave = site + 5 + rel
            # NOTE: `cave` is the E9 TARGET == the first cave instruction
            # (bridge-built rsi/r12d caves put their code at cave_base+0x20
            # and the E9 target IS that code address; momentum's local
            # TimeHooker cave is laid out the same way). So the parse always
            # reads from the target itself.
            code = self.pm.read_bytes(cave, 48)
        except Exception as e:
            self.log(f"[{mod_id}] adopt failed @0x{site:X}: cave read error {e}")
            return None
        if not code:
            return None
        if kind == "xmm0":
            buf = self._parse_cave_buffer_addr(cave, code)
        else:
            buf = self._parse_kind_slot(code, orig_bytes, kind)
        if not buf:
            self.log(f"[{mod_id}] adopt failed @0x{site:X}: unknown {kind} cave "
                     f"signature at 0x{cave:X}")
            return None
        self.log(f"[{mod_id}] hook ADOPTED @0x{site:X} — existing cave "
                 f"0x{cave:X} (buffer 0x{buf:X}) shared, no overwrite")
        return {"orig": bytes(orig_bytes), "nop": 2, "cave": cave,
                "buffer": buf, "refs": set(), "applied": True,
                "adopted": True, "kind": kind}

    # --- capture kinds -------------------------------------------------------
    # kind "xmm0" (ball / default) : cave = movups [buf],xmm0 ; orig ; jmp
    #                                buffer = shared alloc_base+0x20 (16 B)
    # kind "rsi"  (time hook)      : cave = orig ; push rax ; pushfq ;
    #                                mov rax,rsi ; mov [data],rax ; popfq ;
    #                                pop rax ; jmp   (code @cave+0x20,
    #                                8-byte RSI slot @cave+0x40 — byte-
    #                                identical to Momentum's local TimeHooker
    #                                cave so cross-adoption works both ways)
    # kind "r12d" (player-code)    : cave = orig(7 B) ; push rax ; pushfq ;
    #                                mov eax,r12d ; mov [data],rax ; popfq ;
    #                                pop rax ; jmp   (code @cave+0x20,
    #                                8-byte code slot @cave+0x60 — identical
    #                                to HeatMap's local pcode cave)
    RSI_CAPTURE_TAIL = bytes(bytearray([0x50, 0x9C, 0x48, 0x89, 0xF0, 0x48, 0xA3]))
    R12D_CAPTURE_TAIL = bytes(bytearray([0x50, 0x9C, 0x44, 0x89, 0xE0, 0x48, 0xA3]))

    @staticmethod
    def _build_kind_cave(kind, cave_base, buffer_addr, orig_bytes, site):
        """Return the cave bytes for the requested capture kind.
        xmm0 -> (movups-first, capture at buffer_addr, jmp past orig)
        rsi  -> orig-first + RSI capture, data slot at cave+0x40
        r12d -> orig-first + r12d capture, data slot at cave+0x60"""
        orig = bytes(orig_bytes)
        if kind == "xmm0":
            cb = CodeBuilder(cave_base)
            cb.add_mov_reg_rel32(b'\x0F\x11\x05', buffer_addr)  # movups [buf], xmm0
            cb.add(orig)
            cb.add_jmp(site + len(orig))
            return bytes(cb.code), None
        if kind == "rsi":
            data_slot = cave_base + 0x40
            code_start = cave_base + 0x20
            rel_back = (site + len(orig)) - (code_start + 28)
            cave = bytearray(orig)
            cave += Bridge.RSI_CAPTURE_TAIL          # push rax; pushfq; mov rax,rsi; mov [q],rax
            cave += struct.pack('<Q', data_slot)
            cave += bytearray([0x9D, 0x58, 0xE9])    # popfq; pop rax; jmp
            cave += struct.pack('<i', rel_back)
            return bytes(cave), data_slot
        if kind == "r12d":
            data_slot = cave_base + 0x60
            code_start = cave_base + 0x20
            rel_back = (site + len(orig)) - (code_start + 29)
            cave = bytearray(orig)
            cave += Bridge.R12D_CAPTURE_TAIL         # push rax; pushfq; mov eax,r12d; mov [q],rax
            cave += struct.pack('<Q', data_slot)
            cave += bytearray([0x9D, 0x58, 0xE9])    # popfq; pop rax; jmp
            cave += struct.pack('<i', rel_back)
            return bytes(cave), data_slot
        raise ValueError(f"unknown hook kind {kind!r}")

    def request_data_hook(self, mod_id, site_addr, orig_bytes, nop_count,
                          kind="xmm0"):
        orig_bytes = bytes(orig_bytes)
        with self.lock:
            self._ensure()
            # --- address normalization (absolute in, RVA tolerated) ---
            site = int(site_addr)
            base = int(self.base_address or 0)
            if base and site < base:
                site = base + site
            h = self.hooks.get(site)
            if h is not None and h.get("kind", "xmm0") != kind:
                # same site requested with a DIFFERENT capture kind: refuse
                # cleanly (the two mods would read different data layouts)
                self.log(f"[{mod_id}] hook REFUSED @0x{site:X} — already owned "
                         f"with kind {h.get('kind', 'xmm0')!r}, {kind!r} requested")
                return None
            if h is None:
                adopted = self._adopt_existing_hook(mod_id, site, orig_bytes, kind)
                if adopted is not None:
                    h = adopted
                    self.hooks[site] = h
                else:
                    idx = len(self.hooks)
                    cave_base = self.alloc_base + 0x500 + 0x100 * idx
                    buffer_addr = self.alloc_base + 0x20
                    # refuse to patch unknown bytes — a stale offset would
                    # corrupt the game instead of failing cleanly
                    try:
                        curr = self.pm.read_bytes(site, len(orig_bytes))
                    except Exception as e:
                        self.log(f"[{mod_id}] site read failed @0x{site:X}: {e}")
                        return None
                    if bytes(curr) != orig_bytes:
                        self.log(f"[{mod_id}] hook REFUSED @0x{site:X} — "
                                 f"signature mismatch (game updated?) "
                                 f"got {bytes(curr).hex(' ')}")
                        return None
                    try:
                        cave_code, kind_buffer = self._build_kind_cave(
                            kind, cave_base, buffer_addr, orig_bytes, site)
                        code_addr = cave_base if kind == "xmm0" else cave_base + 0x20
                        self.pm.write_bytes(code_addr, cave_code, len(cave_code))
                        if kind_buffer is not None:
                            # fresh zeroed data slot for rsi/r12d captures
                            self.pm.write_bytes(kind_buffer, b'\x00' * 8, 8)
                            buffer_addr = kind_buffer
                    except Exception as e:
                        self.log(f"[{mod_id}] cave build failed @0x{site:X}: {e}")
                        return None
                    h = {"orig": orig_bytes, "nop": nop_count,
                         # "cave" = the address the E9 patch points at (the
                         # first executed cave instruction) — for rsi/r12d
                         # kinds the code starts at cave_base+0x20
                         "cave": code_addr,
                         "cave_base": cave_base,
                         "buffer": buffer_addr, "refs": set(), "applied": False,
                         "adopted": False, "kind": kind}
                    self.hooks[site] = h
                    self.log(f"[{mod_id}] data hook built @0x{site:X} cave=0x{cave_base:X} "
                             f"kind={kind} buffer=0x{buffer_addr:X}")
            h["refs"].add(mod_id)
            if not h["applied"] and not h.get("adopted"):
                try:
                    rel = int(h["cave"] - (site + 5))
                    patch = b'\xE9' + struct.pack('<i', rel) + (b'\x90' * h["nop"])
                    self.pm.write_bytes(site, patch, len(patch))
                    # v2.0.7 — write-verify: WriteProcessMemory succeeding is
                    # NOT proof the bytes landed (protection/race edge cases
                    # were unobservable in the field). Read back and compare;
                    # on mismatch roll the site back and fail cleanly so the
                    # mod falls back instead of reading a dead buffer.
                    try:
                        back = bytes(self.pm.read_bytes(site, len(patch)))
                    except Exception as e:
                        back = None
                        self.log(f"[{mod_id}] hook verify read failed @0x{site:X}: {e}")
                    if back != bytes(patch):
                        self.log(f"[{mod_id}] hook VERIFY FAILED @0x{site:X} — "
                                 f"wrote {bytes(patch).hex(' ')} "
                                 f"read {(back.hex(' ') if back else '<unreadable>')}")
                        try:
                            self.pm.write_bytes(site, orig_bytes, len(orig_bytes))
                        except Exception:
                            pass
                        self.hooks.pop(site, None)
                        return None
                    h["applied"] = True
                    self.log(f"[{mod_id}] hook installed @0x{site:X} (shared buffer 0x{h['buffer']:X})")
                except Exception as e:
                    self.log(f"[{mod_id}] hook install failed @0x{site:X}: {e}")
                    return None
            else:
                self.log(f"[{mod_id}] hook SHARED @0x{site:X} — fed from one source")
            return h["buffer"]

    def release_data_hook(self, mod_id, site_addr):
        with self.lock:
            site = int(site_addr)
            base = int(self.base_address or 0)
            if base and site < base:
                site = base + site
            h = self.hooks.get(site)
            if h is None:
                return
            h["refs"].discard(mod_id)
            if h.get("adopted"):
                # the site belongs to another owner (e.g. the momentum child
                # process) — never restore bytes we do not own
                return
            if not h["refs"] and h["applied"] and self.connected:
                try:
                    self.pm.write_bytes(site, h["orig"], len(h["orig"]))
                    h["applied"] = False
                    self.log(f"data hook removed @0x{site:X}")
                except Exception:
                    pass

    def reset_data_hook(self, mod_id, site_addr, orig_bytes, nop_count,
                        kind="xmm0"):
        """v2.0.7 — ARBITRATED RESET (the user's architecture): a mod asks,
        the bridge DECIDES and EXECUTES. Used when a live hook looks dead
        (data buffer frozen): restore the original bytes, drop the old
        record and rebuild the hook from scratch (fresh cave + buffer or a
        fresh adoption). Restoring bytes on reset is the bridge's call even
        for a hook it merely adopted earlier — the requester only ever
        sends requests, never touches bytes itself."""
        orig_bytes = bytes(orig_bytes)
        with self.lock:
            self._ensure()
            site = int(site_addr)
            base = int(self.base_address or 0)
            if base and site < base:
                site = base + site
            h = self.hooks.get(site)
            if h is not None:
                try:
                    self.pm.write_bytes(site, orig_bytes or h["orig"],
                                        len(orig_bytes or h["orig"]))
                    self.log(f"[{mod_id}] hook RESET: bytes restored @0x{site:X} "
                             f"(was applied={h.get('applied')} "
                             f"adopted={h.get('adopted')})")
                except Exception as e:
                    self.log(f"[{mod_id}] hook RESET write failed @0x{site:X}: {e}")
                self.hooks.pop(site, None)
            else:
                self.log(f"[{mod_id}] hook RESET @0x{site:X} — no record "
                         f"(site may hold orphan bytes); rebuilding anyway")
                try:
                    curr = bytes(self.pm.read_bytes(site, len(orig_bytes)))
                    if curr != orig_bytes:
                        # unknown bytes on an untracked site: restore the
                        # caller-declared originals before rebuilding
                        self.pm.write_bytes(site, orig_bytes, len(orig_bytes))
                        self.log(f"[{mod_id}] hook RESET: orphan bytes "
                                 f"{curr.hex(' ')} restored to originals")
                except Exception as e:
                    self.log(f"[{mod_id}] hook RESET orphan check failed: {e}")
            return self.request_data_hook(mod_id, site, orig_bytes, nop_count,
                                          kind=kind)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def request_camera_control(self, mod_id):
        with self.lock:
            if self.camera_owner is None or self.camera_owner == mod_id:
                self.camera_owner = mod_id
                self.log(f"camera control granted to [{mod_id}]")
                return True
            self.log(f"camera control DENIED to [{mod_id}] — owned by [{self.camera_owner}]")
            return False

    def release_camera_control(self, mod_id):
        with self.lock:
            if self.camera_owner == mod_id:
                self.camera_owner = None
                self.log(f"camera control released by [{mod_id}]")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def pattern_scan(self, pattern):
        with self.lock:
            try:
                self._ensure()
                module = pymem.process.module_from_name(self.pm.process_handle, PROCESS_NAME)
                if not module:
                    return None
                return pymem.pattern.pattern_scan_module(self.pm.process_handle, module, bytes(pattern))
            except Exception as e:
                self.log(f"pattern scan failed: {e.__class__.__name__}: {e}")
                return None

# =============================================================================
# HookBroker — the ONE place where hook bytes are installed / restored.
# -----------------------------------------------------------------------------
# v2.0.6 architecture change requested by the user:
#   * Mods must NOT hook or reset game bytes themselves anymore. Every mod
#     (in-process backends AND child-process mods like Match Momentum / GLT)
#     sends its hook / reset REQUEST to the bridge over a small localhost
#     JSON-line TCP channel and the bridge decides:
#       - site not hooked yet       -> the bridge installs the hook ONCE
#       - site already hooked       -> NO new hook; the bridge returns the
#                                      EXISTING data-buffer address so the
#                                      mod reads the shared feed
#       - last consumer released it -> only then the bridge restores bytes
#   * Reference counting now covers EVERY consumer: in-process backends and
#     child processes alike. A mod crash is detected by the dropped socket
#     and its references are released automatically, so a shared hook is
#     never destroyed while somebody still needs it.
# Protocol (one JSON object per line, terminated by \n):
#   -> {"id":1,"cmd":"hello","mod":"Match Momentum","token":"..."}
#   <- {"id":1,"ok":true,"connected":true,"base":"0x..."}
#   -> {"id":2,"cmd":"hook_request","site_rva":24661922,"orig_hex":"...","nop":2}
#   <- {"id":2,"ok":true,"buffer":"0x...","site":"0x...","adopted":false,"refs":[...]}
#   -> {"id":3,"cmd":"hook_status","site_rva":24661922}
#   <- {"id":3,"ok":true,"hooked":true,"buffer":"0x...","refs":[...]}
#   -> {"id":4,"cmd":"hook_release","site_rva":24661922}
#   <- {"id":4,"ok":true}
#   -> {"id":5,"cmd":"game_status"}
#   <- {"id":5,"ok":true,"running":true,"pid":1234,"base":"0x...",
#       "name":"FL_2026.exe"}
# [suite v2.1.5] PROCESS DETECTION IS THE BRIDGE'S JOB TOO: a mod that
# was opened before the game must not scan the process list itself (its
# one-shot scan errs on that timing). The bridge polls the game every 2 s
# anyway, so every child simply asks game_status (ping/hello carry the
# same fields). running=false is a NORMAL answer, never an error.
# The port + token are handed to spawned children through the environment
# (MODBRIDGE_IPC_PORT / MODBRIDGE_IPC_TOKEN) and also written to
# bridge_ipc.json so manually-started mods can find the broker.
# =============================================================================
class HookBroker:
    IPC_FILE = os.path.join(ROOT_DIR, "bridge_ipc.json")
    BASE_PORT = 57310

    def __init__(self, bridge):
        self.bridge = bridge
        self.token = secrets.token_hex(16)
        self.port = None
        self._listen = None
        self._thread = None
        self._stop = threading.Event()
        self._conns = set()          # sockets
        self._conn_mods = {}         # socket -> mod name
        self._lock = threading.Lock()

    # --- lifecycle ----------------------------------------------------------
    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="HookBroker")
        self._thread.start()

    def stop(self):
        self._stop.set()
        try:
            if self._listen:
                self._listen.close()
        except Exception:
            pass
        with self._lock:
            for c in list(self._conns):
                try:
                    c.close()
                except Exception:
                    pass
            self._conns.clear()
            self._conn_mods.clear()
        try:
            if os.path.exists(self.IPC_FILE):
                os.remove(self.IPC_FILE)
        except Exception:
            pass

    def _run(self):
        srv = None
        for attempt in range(20):
            port = self.BASE_PORT + attempt
            try:
                srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                srv.bind(("127.0.0.1", port))
                srv.listen(8)
                self.port = port
                break
            except OSError:
                try:
                    srv.close()
                except Exception:
                    pass
                srv = None
        if srv is None:
            self.bridge.log("HookBroker: could not bind a localhost port — "
                            "child mods will fall back to their local path")
            return
        self._listen = srv
        try:
            with open(self.IPC_FILE, "w", encoding="utf-8") as f:
                json.dump({"port": self.port, "token": self.token}, f)
        except Exception:
            pass
        self.bridge.log(f"HookBroker listening on 127.0.0.1:{self.port} "
                        "(hook bytes are owned by the bridge only)")
        srv.settimeout(0.5)
        while not self._stop.is_set():
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(None)
            with self._lock:
                self._conns.add(conn)
            threading.Thread(target=self._serve, args=(conn, addr),
                             daemon=True, name="HookBrokerConn").start()
        try:
            srv.close()
        except Exception:
            pass

    # --- per-connection loop -------------------------------------------------
    def _serve(self, conn, addr):
        mod = None
        buf = b""
        try:
            while not self._stop.is_set():
                while b"\n" not in buf:
                    chunk = conn.recv(4096)
                    if not chunk:
                        raise ConnectionError("closed")
                    buf += chunk
                line, buf = buf.split(b"\n", 1)
                line = line.strip()
                if not line:
                    continue
                try:
                    req = json.loads(line.decode("utf-8"))
                except Exception:
                    self._send(conn, None, False, "bad json")
                    continue
                rid = req.get("id")
                cmd = str(req.get("cmd", ""))
                if cmd == "hello":
                    mod = self._hello(conn, req)
                    if mod is None:
                        self._send(conn, rid, False,
                                   "bad token or mod name")
                        break
                    self._send(conn, rid, True,
                               connected=bool(self.bridge.connected),
                               running=bool(self.bridge.connected),
                               pid=(int(self.bridge.game_pid)
                                    if getattr(self.bridge, "game_pid", None)
                                    else None),
                               base=(f"0x{self.bridge.base_address:X}"
                                     if self.bridge.base_address else None),
                               name=PROCESS_NAME)
                    continue
                if mod is None:
                    self._send(conn, rid, False, "hello first")
                    break
                handler = {
                    "hook_request": self._cmd_hook_request,
                    "hook_status":  self._cmd_hook_status,
                    "hook_release": self._cmd_hook_release,
                    "hook_reset_request": self._cmd_hook_reset_request,
                    "game_status":  self._cmd_game_status,
                    "ping":         self._cmd_ping,
                }.get(cmd)
                if handler is None:
                    self._send(conn, rid, False, f"unknown cmd {cmd!r}")
                    continue
                try:
                    handler(conn, rid, mod, req)
                except BridgeError as e:
                    self._send(conn, rid, False, f"bridge not connected: {e}")
                except Exception as e:
                    self._send(conn, rid, False,
                               f"{e.__class__.__name__}: {e}")
        except (ConnectionError, OSError):
            pass
        finally:
            with self._lock:
                self._conns.discard(conn)
                self._conn_mods.pop(conn, None)
            try:
                conn.close()
            except Exception:
                pass
            if mod:
                self._drop_mod_refs(mod)

    def _send(self, conn, rid, ok, error=None, **data):
        try:
            resp = {"id": rid, "ok": bool(ok)}
            if error:
                resp["error"] = error
            resp.update(data)
            conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
        except Exception:
            pass

    def _hello(self, conn, req):
        if str(req.get("token", "")) != self.token:
            return None
        mod = str(req.get("mod", "")).strip()
        if not mod:
            return None
        with self._lock:
            self._conn_mods[conn] = mod
        self.bridge.log(f"HookBroker: [{mod}] connected "
                        f"({len(self._conn_mods)} client(s))")
        return mod

    # --- commands -------------------------------------------------------------
    @staticmethod
    def _norm_site(bridge, site_rva):
        site = int(site_rva)
        base = int(bridge.base_address or 0)
        if base and site < base:
            site = base + site
        return site

    def _hook_info(self, site):
        with self.bridge.lock:
            h = self.bridge.hooks.get(site)
            if h is None:
                return {"hooked": False}
            return {"hooked": True, "buffer": h["buffer"],
                    "applied": bool(h.get("applied")),
                    "adopted": bool(h.get("adopted")),
                    "refs": sorted(h["refs"])}

    def _cmd_hook_request(self, conn, rid, mod, req):
        site_rva = int(req.get("site_rva", 0))
        orig = bytes.fromhex(str(req.get("orig_hex", "")))
        nop = int(req.get("nop", 2))
        kind = str(req.get("kind", "xmm0") or "xmm0")
        buf = self.bridge.request_data_hook(mod, site_rva, orig, nop, kind=kind)
        if buf is None:
            self._send(conn, rid, False,
                       "hook request refused (see ModBridge_log.txt)")
            return
        site = self._norm_site(self.bridge, site_rva)
        info = self._hook_info(site)
        self._send(conn, rid, True, buffer=int(buf), site=site,
                   adopted=info.get("adopted", False),
                   refs=info.get("refs", []),
                   connected=bool(self.bridge.connected))

    def _cmd_hook_status(self, conn, rid, mod, req):
        site = self._norm_site(self.bridge, int(req.get("site_rva", 0)))
        info = self._hook_info(site)
        self._send(conn, rid, True, site=site,
                   connected=bool(self.bridge.connected), **info)

    def _cmd_hook_release(self, conn, rid, mod, req):
        self.bridge.release_data_hook(mod, int(req.get("site_rva", 0)))
        self._send(conn, rid, True)

    def _cmd_hook_reset_request(self, conn, rid, mod, req):
        """v2.0.7 — the mod reports the feed looks DEAD; the bridge
        restores the original bytes, drops the old record and rebuilds
        the hook, then hands back the (possibly new) buffer address."""
        site_rva = int(req.get("site_rva", 0))
        orig = bytes.fromhex(str(req.get("orig_hex", "")))
        nop = int(req.get("nop", 2))
        kind = str(req.get("kind", "xmm0") or "xmm0")
        buf = self.bridge.reset_data_hook(mod, site_rva, orig, nop, kind=kind)
        if buf is None:
            self._send(conn, rid, False,
                       "hook reset refused (see ModBridge_log.txt)")
            return
        site = self._norm_site(self.bridge, site_rva)
        info = self._hook_info(site)
        self._send(conn, rid, True, buffer=int(buf), site=site,
                   adopted=info.get("adopted", False),
                   refs=info.get("refs", []),
                   connected=bool(self.bridge.connected))

    def _cmd_ping(self, conn, rid, mod, req):
        self._send(conn, rid, True,
                   connected=bool(self.bridge.connected),
                   running=bool(self.bridge.connected),
                   pid=(int(self.bridge.game_pid)
                        if getattr(self.bridge, "game_pid", None) else None),
                   base=(f"0x{self.bridge.base_address:X}"
                         if self.bridge.base_address else None),
                   name=PROCESS_NAME)

    def _cmd_game_status(self, conn, rid, mod, req):
        """[suite v2.1.5] — is FL_2026.exe running? The mod children ask
        THIS instead of scanning the process list themselves (user's
        architecture: detection is the bridge's job, because a mod opened
        before the game cannot trust its own one-shot scan). Always
        answers ok — running=false is a normal answer, not an error."""
        gpid = getattr(self.bridge, "game_pid", None)
        self._send(conn, rid, True,
                   name=PROCESS_NAME,
                   running=bool(self.bridge.connected),
                   connected=bool(self.bridge.connected),
                   pid=(int(gpid) if gpid else None),
                   base=(f"0x{self.bridge.base_address:X}"
                         if self.bridge.base_address else None))

    # --- crash / disconnect hygiene -------------------------------------------
    def _drop_mod_refs(self, mod):
        """A child died or disconnected: release every hook reference it
        holds (same semantics as an explicit hook_release)."""
        cleaned = []
        with self.bridge.lock:
            if not self.bridge.connected:
                # hooks table was already wiped on game loss
                return
            for site, h in list(self.bridge.hooks.items()):
                if mod in h["refs"]:
                    h["refs"].discard(mod)
                    cleaned.append(site)
        for site in cleaned:
            try:
                self.bridge.release_data_hook(mod, site)
            except Exception:
                pass
            self.bridge.log(f"HookBroker: [{mod}] disconnected — released "
                            f"its hook @0x{site:X} (refs now: "
                            f"{sorted(self.bridge.hooks.get(site, {}).get('refs', []))})")

# =============================================================================
# =============================================================================
class BackendHost:
    def __init__(self, bridge, mod_name, entry, mod_settings):
        self.bridge = bridge
        self.mod_name = mod_name
        self.entry = entry
        self.settings = mod_settings or {}
        self.instance = None
        self.state = "LOADING"
        self.state_color = "#f39c12"
        self.load()

    def load(self):
        if getattr(sys, "frozen", False):
            folder = os.path.join(BUNDLE_DIR, self.entry["folder"])
        else:
            folder = os.path.join(ROOT_DIR, self.entry["folder"])
        path = os.path.join(folder, self.entry["module"] + ".py")
        if not os.path.exists(path):
            self._set_state("BACKEND NOT FOUND", "#ff4770")
            self.bridge.log(f"[{self.mod_name}] backend file missing: {path}")
            return
        try:
            if folder not in sys.path:
                sys.path.insert(0, folder)
            spec = importlib.util.spec_from_file_location(
                f"modbridge_backend_{self.entry['module']}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls = getattr(module, self.entry["class"])
            self.instance = cls()
            api = BridgeAPI(self.bridge, self.mod_name)
            self.instance.bind(api, self.settings)
            self._set_state("LOADED", "#93c5fd")
            self.bridge.log(f"[{self.mod_name}] backend loaded from {path}")
        except Exception as e:
            self.instance = None
            self._set_state("LOAD ERROR", "#ff4770")
            self.bridge.log(f"[{self.mod_name}] backend load failed: {e.__class__.__name__}: {e}")
            _log("".join(traceback.format_exception(type(e), e, e.__traceback__)))

    def _set_state(self, text, color):
        self.state = text
        self.state_color = color
        self.bridge.ui_events.put(("refresh",))

    def start(self):
        if self.instance:
            try:
                self.instance.start()
            except Exception as e:
                self._set_state("START ERROR", "#ff4770")
                self.bridge.log(f"[{self.mod_name}] start failed: {e}")

    def stop(self):
        if self.instance:
            try:
                self.instance.stop()
            except Exception:
                pass

    def on_connected(self):
        if self.instance:
            try:
                self.instance.on_connected()
            except Exception as e:
                self._set_state("INIT ERROR", "#ff4770")
                self.bridge.log(f"[{self.mod_name}] on_connected failed: {e}")

    def on_disconnected(self):
        if self.instance:
            try:
                self.instance.on_disconnected()
            except Exception:
                pass

    def on_key(self, vk=None):
        if self.instance:
            try:
                try:
                    self.instance.toggle_request(vk)
                except TypeError:
                    self.instance.toggle_request()
            except Exception as e:
                self.bridge.log(f"[{self.mod_name}] toggle failed: {e}")

    def refresh_ui_state(self):
        if self.instance is None:
            return
        try:
            text, color = self.instance.ui_state()
            self.state, self.state_color = text, color
        except Exception:
            pass

    def video_file_path(self):
        try:
            if self.instance and getattr(self.instance, "META", None):
                vf = self.instance.META.get("video_file")
                if vf:
                    return os.path.join(ROOT_DIR, self.entry["folder"], vf)
        except Exception:
            pass
        return None

# =============================================================================
# ProcessHost — backend host for "process mode" mods (Match Momentum).
# Same duck-type interface as BackendHost (state / start / stop / on_key /
# refresh_ui_state / video_file_path) but the backend runs as its own
# Administrator child process; the bridge just spawns, watches and stops it.
# =============================================================================
class _ProcessHost:
    def __init__(self, bridge, mod_name, entry, mod_settings):
        self.bridge = bridge
        self.mod_name = mod_name
        self.entry = entry
        self.settings = mod_settings or {}
        self.proc = None
        self.state = "LOADING"
        self.state_color = "#f39c12"
        self._watch_stop = threading.Event()
        self._watcher = None
        # [suite] v2.0.5 — the headless backends print their hook/display
        # diagnostics to stdout; without a console those lines were
        # silently dropped (charts "invisible/empty" were undiagnosable).
        # Everything the child prints now lands in backend_log.txt next
        # to the mod script.
        self._log_fh = None
        # [suite] v2.1.1 — crash-loop backoff: a backend that dies again and
        # again must not flap RUNNING/EXITED every ~3 s (v2.1.0 field report:
        # a one-line AttributeError in the child made "running"/"exited"
        # alternate forever while nothing actually ran).  Consecutive FAST
        # deaths now grow the restart delay; a stable child clears it.
        self._last_spawn_mono = None     # time.monotonic() of last successful spawn
        self._crash_burst = 0            # consecutive fast-death restarts
        self.WATCH_POLL_SEC = 2.0        # watcher poll interval
        self.RESTART_DELAY_SEC = 1.0     # pause before a normal restart
        self.CRASH_FAST_SEC = 10.0       # died faster than this == fast death
        self.CRASH_BURST_MIN = 3         # consecutive fast deaths before backoff
        self.CRASH_BACKOFF_BASE = 4.0    # first backoff delay (seconds)
        self.CRASH_BACKOFF_CAP = 60.0    # maximum backoff delay
        self.CRASH_STABLE_SEC = 60.0     # alive this long resets the burst counter

    # --- process management -------------------------------------------------
    def _backend_path(self):
        base = BUNDLE_DIR if getattr(sys, "frozen", False) else ROOT_DIR
        return os.path.join(base, self.entry["folder"],
                            self.entry["module"] + ".py")

    def _spawn(self):
        path = self._backend_path()
        if not os.path.exists(path):
            self._set_state("BACKEND NOT FOUND", "#ff4770")
            self.bridge.log(f"[{self.mod_name}] backend file missing: {path}")
            return False
        try:
            # [suite] v2.0.5 — child console output -> backend_log.txt
            # (rotated at 5 MB so it can never grow unbounded).
            try:
                log_path = os.path.join(ROOT_DIR, self.entry["folder"],
                                        "backend_log.txt")
                if os.path.exists(log_path) \
                        and os.path.getsize(log_path) > 5 * 1024 * 1024:
                    os.remove(log_path)
                self._log_fh = open(log_path, "a", encoding="utf-8",
                                    buffering=1)
            except Exception:
                self._log_fh = None
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if self._log_fh is not None:
                kwargs["stdout"] = self._log_fh
                kwargs["stderr"] = subprocess.STDOUT
            # [suite] v2.0.6 — hand the child the HookBroker coordinates so it
            # can REQUEST hooks from the bridge instead of writing bytes itself
            broker = getattr(self.bridge, "hook_broker", None)
            if broker is not None and broker.port:
                env = os.environ.copy()
                env["MODBRIDGE_IPC_PORT"] = str(broker.port)
                env["MODBRIDGE_IPC_TOKEN"] = broker.token
                kwargs["env"] = env
            # [suite] v2.1.3 — SEND THE MOD'S SETTINGS THROUGH THE BRIDGE:
            # the settings block MyMods wrote for this mod is handed to the
            # child as a JSON env var (and the child still reads
            # ModsConfig.json directly as a fallback — belt and braces).
            try:
                if self.settings:
                    env = kwargs.get("env") or os.environ.copy()
                    env["MODBRIDGE_SETTINGS"] = json.dumps(
                        self.settings, ensure_ascii=False)
                    kwargs["env"] = env
            except Exception:
                pass
            # [suite] v2.1.4 — children must write their logs as UTF-8 no
            # matter what the user's Windows locale is (field report: the
            # legacy 'charmap' codec raised UnicodeEncodeError inside a
            # backend thread on a cp1252 stream and killed it).  Hardened
            # backends also reconfigure their own streams — this env is
            # the belt for any older/foreign child.
            try:
                env = kwargs.get("env") or os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                env["PYTHONUTF8"] = "1"
                kwargs["env"] = env
            except Exception:
                pass
            if getattr(sys, "frozen", False):
                env = kwargs.get("env") or os.environ.copy()
                env["VAR_MODS_BACKEND_DIR"] = os.path.join(
                    ROOT_DIR, self.entry["folder"])
                env["VAR_MODS_INSTALL_DIR"] = ROOT_DIR
                kwargs["env"] = env
                backend_args = [
                    sys.executable,
                    "--embedded-backend",
                    self.entry["folder"],
                    self.entry["module"],
                ]
                spawn_cwd = ROOT_DIR
            else:
                backend_args = [sys.executable, os.path.abspath(path)]
                spawn_cwd = os.path.dirname(path)

            self.proc = subprocess.Popen(
                backend_args,
                cwd=spawn_cwd, **kwargs)
            self._last_spawn_mono = time.monotonic()   # [suite] v2.1.1
            self._set_state("RUNNING", "#2ecc71")
            self.bridge.log(f"[{self.mod_name}] backend process started "
                            f"(pid {self.proc.pid})")
            if self._watcher is None or not self._watcher.is_alive():
                self._watch_stop.clear()
                self._watcher = threading.Thread(target=self._watch,
                                                 daemon=True, name="mom-watch")
                self._watcher.start()
            return True
        except Exception as e:
            self.proc = None
            self._set_state("START ERROR", "#ff4770")
            self.bridge.log(f"[{self.mod_name}] process spawn failed: "
                            f"{e.__class__.__name__}: {e}")
            return False

    def _watch(self):
        """Restart the child if it dies while the mod is still enabled.
        [suite] v2.1.1 — crash-loop backoff: repeated FAST deaths no longer
        restart every ~3 s; the delay doubles (4 s -> 8 s -> ... capped at
        60 s), the log names the CRASH LOOP and points at backend_log.txt,
        and a child that stays alive 60 s clears the counter."""
        while not self._watch_stop.wait(self.WATCH_POLL_SEC):
            p = self.proc
            if p is None or p.poll() is None:
                # alive — credit stability and clear the burst counter
                if (p is not None and self._last_spawn_mono is not None
                        and time.monotonic() - self._last_spawn_mono
                        >= self.CRASH_STABLE_SEC
                        and self._crash_burst):
                    self._crash_burst = 0
                    self.bridge.log(f"[{self.mod_name}] backend stable "
                                    f"(>={self.CRASH_STABLE_SEC:.0f}s) — "
                                    "restart backoff cleared")
                continue
            mods_cfg = (self.bridge.cfg or {}).get("mods", {})
            if not bool(mods_cfg.get(self.mod_name, {}).get("enabled", False)):
                continue
            code = p.returncode
            lived = None
            if self._last_spawn_mono is not None:
                lived = max(0.0, time.monotonic() - self._last_spawn_mono)
            if lived is not None and lived < self.CRASH_FAST_SEC:
                self._crash_burst += 1
            else:
                self._crash_burst = 0
            if self._crash_burst >= self.CRASH_BURST_MIN:
                delay = min(self.CRASH_BACKOFF_BASE
                            * (2 ** (self._crash_burst - self.CRASH_BURST_MIN)),
                            self.CRASH_BACKOFF_CAP)
                self.bridge.log(
                    f"[{self.mod_name}] backend exited (code {code}) after "
                    f"{lived:.1f}s — CRASH LOOP x{self._crash_burst}: holding "
                    f"restart {delay:.0f}s (see {self.entry['folder']}/"
                    "backend_log.txt for the child traceback)")
                self._set_state("CRASH LOOP", "#ff4770")
                if self._watch_stop.wait(delay):
                    break
                self._spawn()
            else:
                self.bridge.log(f"[{self.mod_name}] backend exited (code {code}) "
                                "— restarting")
                self._set_state("RESTARTING", "#f39c12")
                time.sleep(self.RESTART_DELAY_SEC)
                self._spawn()

    def _terminate(self):
        self._watch_stop.set()
        p = self.proc
        self.proc = None
        if p is None:
            return
        try:
            if p.poll() is None:
                # [suite] graceful stop: backends that restore game memory on
                # exit (GLT) watch for this flag file and shut themselves
                # down cleanly; the hard kill below is only the fallback.
                flag_name = self.entry.get("stop_flag")
                if flag_name:
                    try:
                        flag_path = os.path.join(ROOT_DIR, self.entry["folder"], flag_name)
                        with open(flag_path, "w", encoding="utf-8") as f:
                            f.write("stop")
                    except Exception:
                        pass
                    try:
                        p.wait(timeout=6)
                    except Exception:
                        pass
                if p.poll() is None:
                    p.terminate()
                    try:
                        p.wait(timeout=5)
                    except Exception:
                        p.kill()
                if flag_name:
                    try:
                        os.remove(os.path.join(ROOT_DIR, self.entry["folder"], flag_name))
                    except Exception:
                        pass
            self.bridge.log(f"[{self.mod_name}] backend process stopped")
        except Exception:
            pass
        finally:
            try:
                if self._log_fh is not None:
                    self._log_fh.close()
            except Exception:
                pass
            self._log_fh = None

    def _set_state(self, text, color):
        self.state = text
        self.state_color = color
        self.bridge.ui_events.put(("refresh",))

    # --- BackendHost-compatible interface ----------------------------------
    def load(self):
        path = self._backend_path()
        if not os.path.exists(path):
            self._set_state("BACKEND NOT FOUND", "#ff4770")
            self.bridge.log(f"[{self.mod_name}] backend file missing: {path}")
        else:
            self._set_state("LOADED", "#93c5fd")
            self.bridge.log(f"[{self.mod_name}] process backend registered: {path}")

    def start(self):
        if self.proc is None or self.proc.poll() is not None:
            self._spawn()

    def stop(self):
        self._terminate()

    def on_connected(self):
        pass                      # the child attaches to the game by itself

    def on_disconnected(self):
        pass

    def on_key(self, vk=None):
        pass                      # no hotkeys for this mod

    def refresh_ui_state(self):
        p = self.proc
        if p is not None and p.poll() is None:
            self.state, self.state_color = "RUNNING", "#2ecc71"
        elif p is not None:
            self.state, self.state_color = "EXITED", "#ff4770"

    def video_file_path(self):
        return None

# =============================================================================
# =============================================================================
class TransparentVideoOverlay(QWidget if WEBENGINE_OK else object):
    def __init__(self, video_path):
        super().__init__()
        from PyQt6.QtWidgets import QVBoxLayout
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool |
                            Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.webview = QWebEngineView(self)
        self.webview.page().setBackgroundColor(_QC(0, 0, 0, 0))
        self.webview.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        settings = self.webview.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.PlaybackRequiresUserGesture, False)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        abs_path = os.path.abspath(video_path)
        base_dir = os.path.dirname(abs_path) + "/"
        base_url = QUrl.fromLocalFile(base_dir)
        filename = os.path.basename(abs_path)
        html_content = ("""<!DOCTYPE html><html><head><style>body {margin:0; padding:0; overflow:hidden; """
                        """background-color:transparent;} video {width:100vw; height:100vh; object-fit:fill;}"""
                        """</style></head><body><video autoplay loop muted><source src=\"""" + filename +
                        """\" type="video/webm"></video></body></html>""")
        self.webview.setHtml(html_content, baseUrl=base_url)
        layout.addWidget(self.webview)

    def show_overlay(self):
        self.showFullScreen()

    def hide_overlay(self):
        self.hide()

# =============================================================================
# =============================================================================
# =============================================================================
# [suite] v2.1.6 (user spec #7) — GlassToggle: the quick-mods ENABLE /
# DISABLE button redesigned as a liquid-glass pill with a glowing power
# badge (same design language as the MyMods glass buttons).
# =============================================================================
def _bridge_draw_glyph(p, kind, cx, cy, r, color):
    pen = QPen(color, max(1.6, r * 0.22))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap if IS_PYQT6 else Qt.RoundCap)
    p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
    p.setPen(pen)
    if kind == "power":
        # open circle (gap at the top) + vertical stem = power glyph
        # QPainterPath.arcTo works on BOTH PyQt5 and PyQt6 (Qt6 dropped
        # the integer-rect drawEllipse arc overload)
        box = QRectF(cx - r * 0.52, cy - r * 0.40, r * 1.04, r * 0.94)
        path = QPainterPath()
        path.arcMoveTo(box, 30)
        path.arcTo(box, 30, 300)
        p.drawPath(path)
        p.drawLine(QPointF(cx, cy - r * 0.72), QPointF(cx, cy + r * 0.05))
    elif kind == "heart":
        s = r * 0.95
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.78)
        path.cubicTo(cx - s * 1.35, cy - s * 0.25, cx - s * 0.45, cy - s * 1.1, cx, cy - s * 0.32)
        path.cubicTo(cx + s * 0.45, cy - s * 1.1, cx + s * 1.35, cy - s * 0.25, cx, cy + s * 0.78)
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawPath(path)


class GlassToggle(QPushButton):
    """Liquid-glass capsule used by the QUICK MODS rows. The badge shows a
    power glyph that turns red (disable) or green (enable) with the state,
    plus a soft under-glow; hover brightens the glass."""

    def __init__(self, parent=None):
        super().__init__("ENABLE", parent)
        self._on = False          # current runtime state (mod enabled?)
        self.setFixedSize(116, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)

    def set_state(self, enabled):
        self._on = bool(enabled)
        self.setText("DISABLE" if self._on else "ENABLE")
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2.0
        # red accent when the click will DISABLE, green when it will ENABLE
        accent = QColor("#ef4444") if self._on else QColor("#22c55e")
        ar, ag, ab = accent.red(), accent.green(), accent.blue()
        hover, down = self.underMouse(), self.isDown()

        glow_a = 66 if not hover else 96
        if down:
            glow_a = 42
        glow = QRadialGradient(w / 2.0, h * 0.94, w * 0.7)
        glow.setColorAt(0.0, QColor(ar, ag, ab, glow_a))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(2, 3, w - 4, h - 2), radius, radius)

        body = QLinearGradient(0, 1, 0, h - 1)
        if down:
            body.setColorAt(0.0, QColor(10, 16, 28, 235))
            body.setColorAt(1.0, QColor(6, 10, 20, 245))
        else:
            body.setColorAt(0.0, QColor(38, 52, 74, 215))
            body.setColorAt(0.5, QColor(22, 32, 50, 228))
            body.setColorAt(1.0, QColor(12, 18, 32, 238))
        p.setBrush(QBrush(body))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        wash = QLinearGradient(0, 0, w, 0)
        wash.setColorAt(0.0, QColor(ar, ag, ab, 66 if hover else 42))
        wash.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setBrush(QBrush(wash))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        border = QColor(255, 255, 255, 150 if hover else 64)
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(border, 1.2 if hover else 1.0))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # glowing power badge
        badge_r = (h - 12) / 2.0
        bcx, bcy = 6 + badge_r + 2, h / 2.0
        ring = QRadialGradient(bcx, bcy, badge_r * 2.0)
        ring.setColorAt(0.0, QColor(ar, ag, ab, 110))
        ring.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(ring))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QPointF(bcx, bcy), badge_r * 1.7, badge_r * 1.7)
        badge = QRadialGradient(bcx - badge_r * 0.3, bcy - badge_r * 0.35, badge_r * 1.7)
        badge.setColorAt(0.0, QColor(min(255, ar + 80), min(255, ag + 80), min(255, ab + 80)))
        badge.setColorAt(1.0, QColor(max(0, ar - 90), max(0, ag - 90), max(0, ab - 90)))
        p.setBrush(QBrush(badge))
        p.setPen(QPen(QColor(255, 255, 255, 110), 1.0))
        p.drawEllipse(QPointF(bcx, bcy), badge_r, badge_r)
        _bridge_draw_glyph(p, "power", bcx, bcy, badge_r * 0.66, QColor(255, 255, 255))

        font = QFont("Segoe UI", 9)
        font.setWeight(QFont.Weight.Black if IS_PYQT6 else 92)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(bcx + badge_r + 6, 0, w - bcx - badge_r - 10, h),
                   Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter,
                   self.text())


# =============================================================================
# [suite] v2.1.6 (user spec #8) — friendly donation prompt shown BEFORE the
# Bridge window closes (CLOSE button, X button); the DONATE button inside
# opens the configured link (or shows a note while none is configured).
# =============================================================================
class BridgeDonateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thank you")
        self.setModal(True)
        self.setFixedSize(470, 300)
        self.setStyleSheet("""
            QDialog { background: #0b1220; border-radius: 14px; }
            QLabel { color: #e2e8f0; font-size: 12px; background: transparent; }
        """)
        v = QVBoxLayout(self)
        v.setContentsMargins(26, 20, 26, 18)
        v.setSpacing(10)

        heart = QLabel("\u2764")
        heart.setFixedSize(54, 54)
        heart.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        heart.setStyleSheet("""
            color: #ff2d78; font-size: 25px; font-weight: 900;
            border: 1.8px solid #ff2d78; border-radius: 27px; background: transparent;
        """)
        row_h = QHBoxLayout()
        row_h.addStretch()
        row_h.addWidget(heart)
        row_h.addStretch()
        v.addLayout(row_h)

        t = QLabel("THANK YOU FOR USING\nFL 2026 MODS BY MILAD")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        t.setStyleSheet("color: #f8fafc; font-size: 15px; font-weight: 900; letter-spacing: 1.4px;")
        v.addWidget(t)

        msg = QLabel("The mods are built and updated with love, for free.\n"
                     "If they make your game more fun, please consider a small\n"
                     "donation — it keeps the updates coming. \u2764")
        msg.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        msg.setStyleSheet("color: #94a3b8; font-size: 11.5px;")
        v.addWidget(msg)
        v.addStretch()

        row = QHBoxLayout()
        btn_donate = QPushButton("\u2764  DONATE")
        btn_donate.setFixedHeight(44)
        btn_donate.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_donate.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                          stop:0 #ff2d78, stop:0.5 #ff5e3a, stop:1 #b845ff);
                          color: white; font-weight: 900; font-size: 12.5px;
                          letter-spacing: 1.4px; border: 1.6px solid rgba(255,255,255,0.85);
                          border-radius: 10px; padding: 0 22px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                          stop:0 #ff4a8d, stop:0.5 #ff7a52, stop:1 #cc63ff); }
        """)
        btn_donate.clicked.connect(self._donate)

        btn_close = QPushButton("CLOSE ANYWAY")
        btn_close.setFixedHeight(44)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { background: #1e293b; color: #cbd5e1; font-weight: 900;
                          font-size: 12px; letter-spacing: 1.2px;
                          border: 1px solid #334155; border-radius: 10px; padding: 0 20px; }
            QPushButton:hover { background: #26334a; color: #ffffff; }
        """)
        btn_close.clicked.connect(self.accept)

        row.addWidget(btn_donate)
        row.addStretch()
        row.addWidget(btn_close)
        v.addLayout(row)

        self._donate_note = None

    def _donate(self):
        url = str(DONATE_URL).strip()
        opened = False
        if url:
            try:
                # v1.0.0b — only treat the donation as handled when the OS
                # actually handed the URL to a browser; otherwise keep the
                # dialog open and show the friendly error note instead of
                # silently closing the bridge.
                opened = bool(QDesktopServices.openUrl(QUrl(url)))
            except Exception:
                opened = False
        if opened:
            self.accept()          # donated -> proceed with the close
            return
        # no link configured (or the browser would not open) — show the note
        if self._donate_note is None:
            self._donate_note = QLabel(
                "Couldn't open the donation page — please check your\n"
                "internet connection and try again in a moment.")
            self._donate_note.setAlignment(
                Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
            self._donate_note.setStyleSheet("color: #fbbf24; font-size: 10.5px;")
            self.layout().addWidget(self._donate_note)
        self._donate_note.show()


class BridgeWindow(QMainWindow):
    def __init__(self, bridge):
        super().__init__()
        self.bridge = bridge
        self.setWindowTitle("FL 2026 • MOD BRIDGE")
        # sized so every card is fully visible — no scrolling needed
        # (v2.1.6: +45px for the taller glass quick-mod toggles + donate row)
        self.setFixedSize(560, 775)
        self.log_lines = []
        self._quick_cache = {}

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(22, 18, 22, 16)
        root.setSpacing(12)

        central.setStyleSheet("QWidget { background-color: #0b1220; }")

        # ---- Header ----
        head = QHBoxLayout()
        self.dot = QLabel("●")
        self.dot.setStyleSheet("color: #f39c12; font-size: 18px;")
        head.addWidget(self.dot)
        t_box = QVBoxLayout()
        t_box.setSpacing(0)
        title = QLabel("MOD BRIDGE RUNNING")
        title.setStyleSheet("color: #f8fafc; font-size: 16px; font-weight: 900; letter-spacing: 2px;")
        sub = QLabel("Coordinator between mods and FL_2026.exe")
        sub.setStyleSheet("color: #64748b; font-size: 11px;")
        t_box.addWidget(title)
        t_box.addWidget(sub)
        head.addLayout(t_box)
        head.addStretch()

        # [suite] v2.1.6 (user spec #8) — DONATE button at the top of the
        # Bridge window (liquid-glass heart pill, same language as MyMods).
        self.btn_donate = QPushButton("❤  DONATE")
        self.btn_donate.setFixedHeight(36)
        self.btn_donate.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.btn_donate.setStyleSheet("""
            QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                          stop:0 #ff2d78, stop:0.5 #ff5e3a, stop:1 #b845ff);
                          color: white; font-weight: 900; font-size: 11.5px;
                          letter-spacing: 1.2px; border: 1.4px solid rgba(255,255,255,0.8);
                          border-radius: 18px; padding: 0 18px; }
            QPushButton:hover { background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                          stop:0 #ff4a8d, stop:0.5 #ff7a52, stop:1 #cc63ff); }
        """)
        self.btn_donate.clicked.connect(self._show_donate_dialog)
        head.addWidget(self.btn_donate)
        root.addLayout(head)

        # ---- Connection ----
        self.lbl_conn = self.card("CONNECTION", "Starting ...", "#f39c12")
        root.addWidget(self.lbl_conn)

        # ---- QUICK MODS (compact live enable/disable for every mod) ----
        root.addWidget(self._build_quick_mods())

        self.lbl_key = self.card("MOD KEYS", "\n".join(self._key_lines()), "#93c5fd")
        root.addWidget(self.lbl_key)

        # ---- Mods ----
        self.lbl_mods = self.card("LOADED MODS", "...", "#93c5fd")
        root.addWidget(self.lbl_mods, 1)

        # ---- Shared resources ----
        self.lbl_hooks = self.card("SHARED PATCHES & HOOKS", "...", "#93c5fd")
        root.addWidget(self.lbl_hooks)

        self.lbl_log = QLabel("—")
        self.lbl_log.setWordWrap(True)
        self.lbl_log.setMinimumHeight(92)
        self.lbl_log.setMaximumHeight(120)
        self.lbl_log.setAlignment(Qt.AlignmentFlag.AlignTop if IS_PYQT6 else Qt.AlignTop)
        self.lbl_log.setStyleSheet("""
            color: #64748b; font-size: 10.5px;
            background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;
            padding: 8px 10px;
        """)
        root.addWidget(self.lbl_log)

        # ---- Close ----
        btn_close = QPushButton("CLOSE & RESTORE GAME STATE")
        btn_close.setFixedHeight(42)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { background: #ef4444; color: white; font-weight: 900;
                          font-size: 12px; letter-spacing: 1px; border: none; border-radius: 9px; }
            QPushButton:hover { background: #dc2626; }
        """)
        btn_close.clicked.connect(self.close)
        root.addWidget(btn_close)

        # ---- Timers ----
        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.drain_queues)
        self.ui_timer.start(120)

        self.ph = 0.0
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self._pulse)
        self.anim_timer.start(400)

        self.overlay = self._build_overlay()

    def _build_overlay(self):
        ref_cfg = self.bridge.cfg.get("mods", {}).get("Referee View", {})
        want_overlay = bool(ref_cfg.get("show_video_overlay", True))
        if not want_overlay:
            self.bridge.log("video overlay disabled in settings")
            return None
        if not WEBENGINE_OK:
            self.bridge.log("PyQt6-WebEngine not installed — video overlay disabled (pip install PyQt6-WebEngine)")
            return None
        host = self.bridge.backends.get("Referee View")
        if not host:
            return None
        vpath = host.video_file_path()
        if not vpath or not os.path.exists(vpath):
            self.bridge.log(f"overlay video not found: {vpath} — put RefereeOverlay.webm inside the mod folder")
            return None
        try:
            ov = TransparentVideoOverlay(vpath)
            self.bridge.log(f"overlay ready: {os.path.basename(vpath)}")
            return ov
        except Exception as e:
            self.bridge.log(f"overlay init failed: {e}")
            return None

    # ==================================================================
    # QUICK MODS — compact section to enable/disable every mod live.
    # The switch flips the backend immediately AND persists the state
    # into ModsConfig.json so MyMods and the backends stay in sync.
    # ==================================================================
    def _build_quick_mods(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame { background: #101a2e; border: 1px solid #1e2a44; border-radius: 10px; }
        """)
        v = QVBoxLayout(frame)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(5)

        t = QLabel("QUICK MODS — FAST ENABLE / DISABLE")
        t.setStyleSheet("color: #475569; font-size: 9.5px; font-weight: 900; letter-spacing: 2px; border: none; background: transparent;")
        v.addWidget(t)

        self.quick_buttons = {}
        self.quick_status = {}
        for mod_name in MOD_REGISTRY.keys():
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet("color: #64748b; font-size: 12px; border: none; background: transparent;")
            name = QLabel(mod_name)
            name.setStyleSheet("color: #e2e8f0; font-size: 12px; font-weight: 700; border: none; background: transparent;")
            status = QLabel("OFF")
            status.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; border: none; background: transparent;")
            # [suite] v2.1.6 (user spec #7) — the old flat ENABLE/DISABLE
            # rectangle is now a liquid-glass pill with a glowing power badge
            btn = GlassToggle()
            btn.clicked.connect(lambda _, n=mod_name: self._on_quick_toggle(n))
            row.addWidget(dot)
            row.addWidget(name)
            row.addStretch()
            row.addWidget(status)
            row.addWidget(btn)
            v.addLayout(row)
            self.quick_buttons[mod_name] = (btn, dot)
            self.quick_status[mod_name] = status

        self.lbl_quick_warn = QLabel(
            "⚠  Both mods are enabled at the same time — this may crash the game.")
        self.lbl_quick_warn.setWordWrap(True)
        self.lbl_quick_warn.setStyleSheet("""
            color: #ffd27a; font-size: 10.5px; font-weight: 800;
            background: rgba(255, 183, 0, 0.12); border: 1px solid #b37e00;
            border-radius: 7px; padding: 5px 8px;
        """)
        self.lbl_quick_warn.hide()
        v.addWidget(self.lbl_quick_warn)

        self._sync_quick_cards(force=True)
        return frame

    def _on_quick_toggle(self, mod_name, source="quick mods"):
        entry = MOD_REGISTRY.get(mod_name)
        if not entry:
            return
        if entry.get("mode") == "process":
            self._on_quick_toggle_process(mod_name, entry, source)
            return
        host = self.bridge.backends.get(mod_name)
        mods_cfg = self.bridge.cfg.setdefault("mods", {})
        mc = mods_cfg.setdefault(mod_name, {})

        if host is None:
            # ---- ENABLE ----
            host = BackendHost(self.bridge, mod_name, entry, mc)
            self.bridge.backends[mod_name] = host
            if self.bridge.connected:
                host.on_connected()
            host.start()
            mc["enabled"] = True
            self.bridge.log(f"[{mod_name}] ACTIVATED ({source})")
            if mod_name == "Referee View":
                self._rebuild_overlay_for_quick_toggle()
        else:
            # ---- DISABLE ----
            host.stop()
            del self.bridge.backends[mod_name]
            mc["enabled"] = False
            self.bridge.log(f"[{mod_name}] DEACTIVATED ({source})")
            if mod_name == "Referee View":
                if self.overlay and self.bridge.overlay_visible:
                    try:
                        self.overlay.hide_overlay()
                    except Exception:
                        pass
                self.bridge.overlay_visible = False
                if self.overlay is not None:
                    try:
                        self.overlay.close()
                    except Exception:
                        pass
                    self.overlay = None

        self._save_cfg()
        self._sync_quick_cards(force=True)

    def _on_quick_toggle_process(self, mod_name, entry, source="quick mods"):
        """ENABLE/DISABLE for process-mode mods (spawn/terminate child)."""
        host = self.bridge.backends.get(mod_name)
        mods_cfg = self.bridge.cfg.setdefault("mods", {})
        mc = mods_cfg.setdefault(mod_name, {})
        if host is None:
            host = _ProcessHost(self.bridge, mod_name, entry, mc)
            self.bridge.backends[mod_name] = host
            host.load()
            host.start()
            mc["enabled"] = True
            self.bridge.log(f"[{mod_name}] ACTIVATED ({source})")
        else:
            host.stop()
            del self.bridge.backends[mod_name]
            mc["enabled"] = False
            self.bridge.log(f"[{mod_name}] DEACTIVATED ({source})")
        self._save_cfg()
        self._sync_quick_cards(force=True)

    def _rebuild_overlay_for_quick_toggle(self):
        if self.overlay is not None:
            try:
                self.overlay.close()
            except Exception:
                pass
            self.overlay = None
            self.bridge.overlay_visible = False
        self.overlay = self._build_overlay()

    def _save_cfg(self):
        """Persist the (possibly quick-toggled) config back to ModsConfig.json."""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.bridge.cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.bridge.log(f"config save failed: {e.__class__.__name__}: {e}")

    def _sync_quick_cards(self, force=False):
        """Refresh QUICK MODS rows from the live runtime state."""
        for mod_name in MOD_REGISTRY.keys():
            host = self.bridge.backends.get(mod_name)
            enabled = host is not None
            btn, dot = self.quick_buttons[mod_name]
            status = self.quick_status[mod_name]
            state_txt = host.state if host else "OFF"
            cache_key = (enabled, state_txt)
            if not force and self._quick_cache.get(mod_name) == cache_key:
                continue
            self._quick_cache[mod_name] = cache_key
            if enabled:
                color = "#2ecc71" if host.state_color in ("#2ecc71", "#93c5fd") else host.state_color
                status.setText(state_txt)
                status.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: 700; border: none; background: transparent;")
                dot.setStyleSheet(f"color: {color}; font-size: 12px; border: none; background: transparent;")
                btn.set_state(True)
            else:
                status.setText("OFF")
                status.setStyleSheet("color: #64748b; font-size: 11px; font-weight: 700; border: none; background: transparent;")
                dot.setStyleSheet("color: #64748b; font-size: 12px; border: none; background: transparent;")
                btn.set_state(False)
        # yellow warning line when Referee View + Goal Line Technology are
        # on together (that specific pair may crash the game)
        show_warn = ("Referee View" in self.bridge.backends
                     and "Goal Line Technology" in self.bridge.backends)
        if self.lbl_quick_warn.isVisible() != show_warn:
            self.lbl_quick_warn.setVisible(show_warn)

    def _key_lines(self):
        mods_cfg = self.bridge.cfg.get("mods", {})
        lines = []

        def fmt(vk_raw, name_raw, fallback_name):
            vk = str(vk_raw or "").strip()
            name = str(name_raw or fallback_name or "")
            return name if vk else None

        rv = mods_cfg.get("Referee View", {})
        rv_name = fmt(rv.get("apply_key_vk"), rv.get("apply_key_name"), "T")
        lines.append(f"● Referee View (Apply): {rv_name} — inside Replay mode" if rv_name
                     else "● Referee View (Apply): NOT SET — choose it in MyMods")

        glt = mods_cfg.get("Goal Line Technology", {})
        play = fmt(glt.get("glt_play_vk"), glt.get("glt_play_name"), "F8")
        rec = fmt(glt.get("glt_rec_vk"), glt.get("glt_rec_name"), "F7")
        lines.append(f"● Goal Line Tech (Play Animation): {play}" if play
                     else "● Goal Line Tech (Play Animation): NOT SET")
        lines.append(f"● Goal Line Tech (Manual Record): {rec}" if rec
                     else "● Goal Line Tech (Manual Record): NOT SET")
        saot = mods_cfg.get("S.A.O.T", {})
        call = fmt(saot.get("apply_key_vk"), saot.get("apply_key_name"), "F1")
        lines.append(f"● S.A.O.T (Call Key): {call} — shows/hides the "
                     "offside tool in-game" if call
                     else "● S.A.O.T (Call Key): NOT SET — choose it in MyMods")
        return lines

    @staticmethod
    def card(title, text, color):
        f = QFrame()
        f.setStyleSheet("""
            QFrame { background: #101a2e; border: 1px solid #1e2a44; border-radius: 10px; }
        """)
        v = QVBoxLayout(f)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(3)
        t = QLabel(title)
        t.setStyleSheet("color: #475569; font-size: 9.5px; font-weight: 900; letter-spacing: 2px; border: none; background: transparent;")
        body = QLabel(text)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700; border: none; background: transparent;")
        v.addWidget(t)
        v.addWidget(body)
        f._body = body
        return f

    def _set_card(self, card, text, color):
        card._body.setText(text)
        card._body.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 700; border: none; background: transparent;")

    def _pulse(self):
        self.ph = (self.ph + 1) % 2
        connected = self.bridge.connected
        color = "#2ecc71" if connected else ("#f39c12" if not self.bridge.stop_flag.is_set() else "#64748b")
        self.dot.setStyleSheet(f"color: {color}; font-size: 18px;")

    def drain_queues(self):
        # [suite] v2.1.6 (user spec #6) — auto-activation requests queued by
        # the connect-loop's sequence thread are executed HERE on the GUI
        # thread, through the same code path as the quick-mods buttons.
        try:
            while True:
                mod_name = self.bridge.activation_q.get_nowait()
                if mod_name not in self.bridge.backends:
                    self._on_quick_toggle(mod_name, source="auto activation sequence")
        except queue.Empty:
            pass

        # statuses
        changed_log = False
        try:
            while True:
                text, color, is_status = self.bridge.status_q.get_nowait()
                stamp = time.strftime("%H:%M:%S")
                self.log_lines.append(f"[{stamp}] {text}")
                self.log_lines = self.log_lines[-4:]
                changed_log = True
        except queue.Empty:
            pass
        if changed_log:
            self.lbl_log.setText("<br>".join(self.log_lines))
            self.lbl_log.setStyleSheet("""
                color: #64748b; font-size: 10.5px;
                background: #0f172a; border: 1px solid #1e293b; border-radius: 8px;
                padding: 8px 10px;
            """)

        # connection card
        if self.bridge.connected:
            self._set_card(self.lbl_conn,
                           f"CONNECTED — FL_2026.exe (base 0x{self.bridge.base_address:X})",
                           "#2ecc71")
        else:
            self._set_card(self.lbl_conn, "Waiting for FL_2026.exe ...", "#f39c12")

        # mods card
        rows = []
        for name, host in list(self.bridge.backends.items()):
            host.refresh_ui_state()
            rows.append(f"● {name} — {host.state}")
        if not rows:
            # v2.1.6 — explain the staged auto-activation state
            staged = [n for n in MOD_REGISTRY
                      if bool(self.bridge.cfg.get("mods", {}).get(n, {}).get("enabled", False))]
            if staged and not self.bridge.connected:
                rows.append(f"{len(staged)} mod(s) staged — they activate "
                            "automatically 3 s after FL_2026.exe launches.")
            elif staged:
                rows.append("Mods are being activated in order — wait a moment ...")
            else:
                rows.append("No mod enabled in MyMods settings.")
        self._set_card(self.lbl_mods, "<br>".join(rows), "#93c5fd")

        # quick mods card (live enable/disable rows)
        self._sync_quick_cards()

        # shared resources card
        n_patch = len(self.bridge.patches)
        n_hook = len(self.bridge.hooks)
        owner = self.bridge.camera_owner or "—"
        self._set_card(self.lbl_hooks,
                       f"Patches: {n_patch}   •   Data hooks: {n_hook}   •   Camera owner: {owner}",
                       "#93c5fd")

        try:
            while True:
                vk = self.bridge.key_events.get_nowait()
                for host in self.bridge.backends.values():
                    host.on_key(vk)
        except queue.Empty:
            pass

        # ui events (overlay / refresh)
        try:
            while True:
                ev, = self.bridge.ui_events.get_nowait()
                if ev == "overlay_show" and self.overlay and not self.bridge.overlay_visible:
                    self.overlay.show_overlay()
                    self.bridge.overlay_visible = True
                elif ev == "overlay_hide" and self.bridge.overlay_visible:
                    if self.overlay:
                        self.overlay.hide_overlay()
                    self.bridge.overlay_visible = False
        except queue.Empty:
            pass

    def _show_donate_dialog(self):
        """v2.1.6 (user spec #8) — the DONATE button shows the friendly
        thank-you dialog without closing the bridge."""
        try:
            dlg = BridgeDonateDialog(self)
            exec_fn = getattr(dlg, "exec", getattr(dlg, "exec_", None))
            exec_fn()
        except Exception:
            pass

    def closeEvent(self, event):
        # v2.1.6 (user spec #8) — the FIRST close attempt (CLOSE button or
        # window X) shows the friendly donation prompt; only after the user
        # picks CLOSE ANYWAY (or DONATE opens the link) does the bridge
        # really shut down.  ESC / dialog-reject cancels the close.
        if getattr(self, "_close_confirmed", False):
            self.bridge.shutdown()
            super().closeEvent(event)
            return
        try:
            dlg = BridgeDonateDialog(self)
            exec_fn = getattr(dlg, "exec", getattr(dlg, "exec_", None))
            result = exec_fn()
        except Exception:
            result = None
        accepted = (result == (QDialog.DialogCode.Accepted if IS_PYQT6
                               else QDialog.Accepted))
        if accepted:
            self._close_confirmed = True
            self.close()
        else:
            event.ignore()

# =============================================================================
# Startup / Shutdown
# =============================================================================
def main():
    if "--embedded-backend" in sys.argv:
        run_embedded_backend()
        return
    if sys.platform == "win32" and not acquire_single_instance():
        _fatal_box("Mod Bridge is already running.")
        return

    cfg = load_config()
    bridge = Bridge(cfg)

    # --- [suite] v2.1.6 (user spec #6) — STAGE, don't start -------------
    # Every mod stays DISABLED at this point (the game is not running
    # yet). Mods enabled in ModsConfig.json are only REGISTERED in the
    # log here; connect_loop fires the activation sequence 3 s after
    # FL_2026.exe appears, activating them in order.
    mods_cfg = cfg.get("mods", {})
    for mod_name in MOD_REGISTRY:
        mc = mods_cfg.get(mod_name, {})
        if not bool(mc.get("enabled", False)):
            bridge.log(f"[{mod_name}] disabled in ModsConfig.json — skipped")
        else:
            bridge.log(f"[{mod_name}] staged — activates automatically "
                       "3 s after FL_2026.exe launches")

    #   Referee View → Apply Key | Goal Line Technology → Play (F8) + Record (F7)
    def _parse_vk(raw):
        try:
            s = str(raw or "").strip()
            return int(s, 16) if s else None
        except Exception:
            return None

    key_defs = []
    rv_vk = _parse_vk(mods_cfg.get("Referee View", {}).get("apply_key_vk", "0x54"))
    if rv_vk is not None:
        key_defs.append((rv_vk, "Referee View (Apply)"))
    # [suite] GLT runs as its own process and polls its hotkeys itself
    # (GetAsyncKeyState inside the tool, keys from ModsConfig.json), so the
    # bridge must NOT also listen on those keys — one key, one owner.

    started = {}
    for vk, label in key_defs:
        if vk in started:
            continue
        started[vk] = label
        listener = GlobalKeyListener(vk, lambda v=vk: bridge.key_events.put(v))
        bridge.key_listeners.append(listener)
        listener.start()
        bridge.log(f"global key listener started (VK 0x{vk:02X} — {label})")
    if not started:
        bridge.log("no hotkeys set — listeners disabled")

    # --- threads ---
    # [suite] v2.0.6 — the bridge owns ALL hook bytes: child-process mods
    # (Match Momentum / GLT) request them through this broker instead of
    # hooking/restoring game memory themselves.
    broker = HookBroker(bridge)
    bridge.hook_broker = broker
    broker.start()
    threading.Thread(target=bridge.connect_loop, daemon=True, name="BridgeConnect").start()
    # [suite] v2.1.6 — NOTE: hosts are NOT started here any more. The
    # auto-activation sequence starts them (in order) 3 s after the game
    # is detected; until then every mod stays disabled (user spec #6).

    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = BridgeWindow(bridge)
    window.show()
    bridge.status("Mod Bridge is running — keep this window open while playing.", "#2ecc71")

    exec_fn = getattr(app, "exec", getattr(app, "exec_", None))
    exec_fn()
    bridge.shutdown()

def _shutdown(bridge):
    bridge.stop_flag.set()
    for listener in getattr(bridge, "key_listeners", []):
        try:
            listener.stop()
        except Exception:
            pass
    for host in bridge.backends.values():
        host.stop()
    broker = getattr(bridge, "hook_broker", None)
    if broker is not None:
        broker.stop()
    bridge.patches.clear()
    bridge.hooks.clear()
    bridge.log("Mod Bridge shut down — game state restored.")

Bridge.shutdown = _shutdown

if __name__ == "__main__":
    if "--package-smoke" in sys.argv:
        _required = [
            ("GLT", "GLTMod.py"),
            ("HeatMap", "HeatMapMod.py"),
            ("HeatMap", "BroadcastRenderer.py"),
            ("SAOTMod", "SAOTMod.py"),
            ("RefereeView", "RefereeView.py"),
            ("MomentumMatch", "MomentumMod.py"),
        ]
        for _folder, _name in _required:
            _p = os.path.join(BUNDLE_DIR, _folder, _name)
            if not os.path.exists(_p):
                raise FileNotFoundError(f"Embedded backend missing: {_p}")
        import numpy as _np
        import matplotlib as _mpl
        import pymem as _pm
        import moderngl as _mg
        import glfw as _glfw
        import panda3d.core as _p3d
        import ursina as _ursina
        print("Standalone ModBridge package smoke test passed")
        sys.exit(0)
    if "--embedded-backend" in sys.argv:
        _idx = sys.argv.index("--embedded-backend")
        try:
            _folder = sys.argv[_idx + 1]
            _module = sys.argv[_idx + 2]
        except IndexError:
            _log("Embedded backend failed: incomplete command line")
            raise SystemExit(2)

        _source = os.path.join(BUNDLE_DIR, _folder, _module + ".py")
        if not os.path.exists(_source):
            _log("Embedded backend failed: source not found: " + _source)
            raise SystemExit(2)

        os.environ["VAR_MODS_INSTALL_DIR"] = ROOT_DIR
        os.environ["VAR_MODS_BACKEND_DIR"] = os.path.join(ROOT_DIR, _folder)

        _backend_dir = os.path.dirname(_source)
        if _backend_dir not in sys.path:
            sys.path.insert(0, _backend_dir)

        _original_argv = sys.argv[:]
        sys.argv = [_source] + sys.argv[_idx + 3:]
        _namespace = {
            "__name__": "__main__",
            "__file__": _source,
            "__package__": None,
            "__cached__": None,
        }

        try:
            with open(_source, "r", encoding="utf-8") as _backend_file:
                _backend_source = _backend_file.read()
            exec(
                compile(_backend_source, _source, "exec"),
                _namespace,
                _namespace,
            )
        except SystemExit:
            raise
        except Exception as _exc:
            _log("Embedded backend failed: " + repr(_exc))
            raise SystemExit(1)
        finally:
            sys.argv = _original_argv
    else:
        main()
