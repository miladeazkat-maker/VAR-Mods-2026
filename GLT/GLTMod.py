# -*- coding: utf-8 -*-
# [PROJECT RULE — DO NOT REMOVE] ENGLISH ONLY: this project must NEVER contain any Persian/Farsi text (UI strings, comments, docs).
# =============================================================================
#  GLTMod.py — "Goal Line Technology" tool, ORIGINAL v4 code (PLAYBACK-FIXED)
#  kept 1:1 VERBATIM — every key sequence, timing, dialog and the full
#  control panel behave exactly like the standalone GLT2021 v2 tool.
#
#  Suite integration (PES MODS launcher): the mod runs as its OWN process
#  spawned by ModBridge.py (like Match Momentum).  Only four fail-safe
#  adapters were added, all marked with [suite]:
#    1. startup read of ModsConfig.json (MyMods hotkeys F8/F7 + T5/T6 style)
#    2. the MyMods manual-record key triggers the panel's own record action
#    3. an existing ball-hook cave written by another suite member is
#       adopted (both bridge-style and momentum-style layouts) so GLT,
#       Referee View and Momentum can share one hook
#    4. ModBridge creates glt_stop.flag to stop the tool gracefully
#       (full memory restore) instead of killing the process
# =============================================================================
import os
import sys
import ctypes
import json
import socket
import time
import math
import struct
import threading
import tkinter as tk
from tkinter import messagebox
import pymem
import pymem.process
import pymem.pattern
import traceback
import atexit
from panda3d.core import load_prc_file_data, Filename, WindowProperties

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Same field bug reported on the Heat Map backend: when stdout/stderr is
# a FILE or PIPE (bridge child stream, redirected runs) Python uses the
# legacy ANSI 'charmap' codec (cp1252), and ONE print of a non-Latin-1
# string (Persian status text, Arabic team/player names) raises
# UnicodeEncodeError that can kill the printing thread. Hardened:
# console -> UTF-8 codepage, streams -> utf-8 + errors='replace', and a
# wrapper so a failing write degrades to sanitized ASCII, never raises.
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

# گرفتن دسترسی ادمین
if not ctypes.windll.shell32.IsUserAnAdmin():
    script_path = os.path.abspath(sys.argv[0])
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script_path}"', None, 1)
    sys.exit()

import traceback as _traceback
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CRASH_LOG = os.path.join(CURRENT_DIR, "crash_log.txt")
_LOG_PATH = os.path.join(CURRENT_DIR, "debug_log.txt")

_log_file = open(_LOG_PATH, "w", encoding="utf-8", buffering=1)
def flog(tag, msg):
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}][{tag}] {msg}"
    try:
        _log_file.write(line + "\n")
        _log_file.flush()  # ذخیره درجا روی هارد دیسک
    except: pass

# ============================================================================
# [suite] PES MODS integration helpers (pure stdlib — no Windows calls here)
# ============================================================================
STOP_FLAG_FILE = os.path.join(CURRENT_DIR, "glt_stop.flag")

BRIDGE_CAVE_SIG = b'\x0F\x11\x05'                    # movups [rel32], xmm0
GLT_MOMENTUM_CAVE_SIG = b'\x0F\x29\x80\x50\x04\x00\x00'  # original movaps

def _resolve_existing_cave_buffer(pm, cave_address):
    """[suite] Data-slot address of an ALREADY-INSTALLED ball-hook cave.

    GLT, the ModBridge in-process backends (Referee View) and the Match
    Momentum child all install the same kind of code cave on the ball
    write site (FL_2026.exe+0x176A3A2). Two cave layouts exist:
      bridge style   : starts with 0F 11 05 rel32 (movups [buf], xmm0)
                       -> data buffer = cave + 7 + rel32
      glt/momentum   : starts with the original movaps bytes
                       -> data buffer = cave + 64
    Returns the buffer address, or None when the cave cannot be decoded
    (the caller then falls back to the classic cave+64 layout).
    """
    try:
        code = bytes(pm.read_bytes(cave_address, 7))
    except Exception:
        return None
    try:
        if code[0:3] == BRIDGE_CAVE_SIG:
            rel = struct.unpack('<i', code[3:7])[0]
            return cave_address + 7 + rel
        if code[0:7] == GLT_MOMENTUM_CAVE_SIG:
            return cave_address + 64
    except Exception:
        return None
    return None

def _glt_ball_site_is_ours(pm, hook_address, cave_address):
    """[suite] v2.0.5 — True ONLY when the live E9 at the ball site jumps
    into OUR cave (we own the hook and may restore the original bytes).

    The site is SHARED: the Match Momentum child process adopts whatever
    cave is live and reads its data buffer. If we restored the original
    bytes while a foreign hook owned the site, their data feed would die
    silently and their charts would freeze/go empty. Used by the
    clean-shutdown restore so an adopted/foreign hook always survives
    our exit.
    """
    try:
        if not (pm and hook_address and cave_address):
            return False
        curr = bytes(pm.read_bytes(hook_address, 7))
        if not curr or curr[0] != 0xE9:
            return False          # site is back to the original code
        rel = struct.unpack('<i', curr[1:5])[0]
        return (hook_address + 5 + rel) == cave_address
    except Exception:
        return False

def _glt_stop_flag_watchdog():
    """[suite] Graceful-shutdown trigger used by ModBridge.

    Killing this process outright would skip the memory restore (NOP
    patches, camera floats, HUD byte, CAM4 lock).  Instead the bridge
    creates STOP_FLAG_FILE; the tool then runs the exact same cleanup
    path as a normal window close and exits by itself."""
    while True:
        try:
            if os.path.exists(STOP_FLAG_FILE):
                try:
                    os.remove(STOP_FLAG_FILE)
                except Exception:
                    pass
                _cleanup = globals().get("_shutdown_cleanup")
                if callable(_cleanup):
                    try:
                        _cleanup()
                    except Exception:
                        pass
                os._exit(0)
        except Exception:
            pass
        time.sleep(0.4)

# ============================================================================
# [suite] v2.0.6 — ModBridge HOOK BROKER client.
# ARCHITECTURE (user request): mods must NOT hook or reset game bytes
# themselves anymore — the bridge is the single owner of hook bytes. This
# tool only SENDS a hook request to the broker and receives the address of
# the shared data buffer to read (no second hook, no byte writes, and on
# exit only a "release" — the bridge restores the original bytes itself,
# and only when the LAST consumer leaves). Pure stdlib so these helpers
# stay testable outside Windows; every call is fail-safe (None/False +
# _bridge_broker["err"]).
# Discovery: MODBRIDGE_IPC_PORT / MODBRIDGE_IPC_TOKEN env (set when the
# bridge spawns this tool), else <PES MODS>/bridge_ipc.json.
# ============================================================================
_BRIDGE_IPC_FILE = os.path.join(os.path.dirname(CURRENT_DIR), "bridge_ipc.json")
_bridge_broker = {"port": None, "token": None, "sock": None,
                  "buf": b"", "rid": 0, "err": "not-configured"}
BALL_SITE_RVA = 0x176A3A2          # the shared ball-coordinate write site
_ball_hook_via_bridge = False      # True -> site bytes are NEVER touched here

def _bridge_broker_available():
    """Resolve broker coordinates once (env first, then bridge_ipc.json)."""
    if _bridge_broker["port"] and _bridge_broker["token"]:
        return True
    try:
        _bridge_broker["port"] = int(
            os.environ.get("MODBRIDGE_IPC_PORT", "") or 0) or None
        _bridge_broker["token"] = (
            os.environ.get("MODBRIDGE_IPC_TOKEN") or None)
    except Exception:
        pass
    if not (_bridge_broker["port"] and _bridge_broker["token"]):
        try:
            with open(_BRIDGE_IPC_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            _bridge_broker["port"] = int(d.get("port") or 0) or None
            _bridge_broker["token"] = str(d.get("token") or "") or None
        except Exception:
            pass
    if not (_bridge_broker["port"] and _bridge_broker["token"]):
        _bridge_broker["err"] = "not-configured"
        return False
    return True

def _bridge_broker_close():
    try:
        if _bridge_broker["sock"] is not None:
            _bridge_broker["sock"].close()
    except Exception:
        pass
    _bridge_broker["sock"] = None
    _bridge_broker["buf"] = b""

def _bridge_rpc(cmd, _noreconnect=False, **fields):
    """One JSON-line request -> one response dict (or None). Reconnects
    once when the pipe dropped; the broker keeps our hook refs meanwhile."""
    if not _bridge_broker_available():
        return None
    for attempt in (0, 1):
        if _bridge_broker["sock"] is None:
            try:
                s = socket.create_connection(
                    ("127.0.0.1", int(_bridge_broker["port"])), timeout=6.0)
                s.settimeout(6.0)
                _bridge_broker["sock"] = s
                _bridge_broker["rid"] = 0
            except Exception as e:
                _bridge_broker["err"] = f"connect-failed:{e.__class__.__name__}"
                return None
            if not _noreconnect:
                resp = _bridge_rpc("hello", _noreconnect=True,
                                   mod="Goal Line Technology",
                                   token=_bridge_broker["token"])
                if not resp or not resp.get("ok"):
                    _bridge_broker["err"] = (
                        (resp or {}).get("error") or "hello-refused")
                    _bridge_broker_close()
                    return None
        _bridge_broker["rid"] += 1
        rid = _bridge_broker["rid"]
        req = {"id": rid, "cmd": cmd}
        req.update(fields)
        try:
            _bridge_broker["sock"].sendall(
                (json.dumps(req) + "\n").encode("utf-8"))
            buf = _bridge_broker["buf"]
            while b"\n" not in buf:
                chunk = _bridge_broker["sock"].recv(4096)
                if not chunk:
                    raise ConnectionError("closed")
                buf += chunk
            _bridge_broker["buf"] = b""
            line = buf.split(b"\n", 1)[0]
            resp = json.loads(line.decode("utf-8"))
            if int(resp.get("id", -1)) != rid:
                raise ValueError("response id mismatch")
            return resp
        except Exception as e:
            _bridge_broker["err"] = f"{cmd}:{e.__class__.__name__}"
            _bridge_broker_close()
            if _noreconnect or attempt == 1:
                return None
    return None

def _bridge_hook_request(site_rva, orig_bytes, nop=2):
    """Ask the bridge to hook `site_rva` (or SHARE its existing hook).
    Returns the absolute data-buffer address, or None."""
    resp = _bridge_rpc("hook_request", site_rva=int(site_rva),
                       orig_hex=bytes(orig_bytes).hex(), nop=int(nop))
    if not resp or not resp.get("ok"):
        if resp:
            _bridge_broker["err"] = f"hook_request:{resp.get('error', 'refused')}"
        return None
    try:
        return int(resp.get("buffer"))
    except Exception:
        _bridge_broker["err"] = "hook_request:bad-buffer"
        return None

def _bridge_hook_release(site_rva):
    """Give our reference back — the bridge decides when (if ever) the
    original bytes go back (only when the LAST consumer leaves)."""
    resp = _bridge_rpc("hook_release", site_rva=int(site_rva))
    if not resp or not resp.get("ok"):
        if resp:
            _bridge_broker["err"] = f"hook_release:{resp.get('error', 'refused')}"
        return False
    return True

VirtualAllocEx = ctypes.windll.kernel32.VirtualAllocEx
VirtualAllocEx.restype = ctypes.c_uint64
VirtualAllocEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.c_ulong]

# Direct WinAPI memory access for the CAM4 byte/pointer chain.
# This deliberately bypasses pymem's typed pointer readers for CAM4 so the
# chain behaves exactly like Cheat Engine: DWORD pointers for PES2017 and
# QWORD pointers for FL_2026.
k32 = ctypes.windll.kernel32
ReadProcessMemory = k32.ReadProcessMemory
ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
ReadProcessMemory.restype = ctypes.c_bool
WriteProcessMemory = k32.WriteProcessMemory
WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
WriteProcessMemory.restype = ctypes.c_bool

def _rpm(handle, address, size):
    buf = ctypes.create_string_buffer(size)
    n = ctypes.c_size_t(0)
    ok = ReadProcessMemory(ctypes.c_void_p(handle), ctypes.c_void_p(int(address)), buf, size, ctypes.byref(n))
    if not ok or n.value != size:
        raise ctypes.WinError()
    return bytes(buf.raw)

def _wpm(handle, address, data):
    raw = bytes(data)
    buf = ctypes.create_string_buffer(raw, len(raw))
    n = ctypes.c_size_t(0)
    ok = WriteProcessMemory(ctypes.c_void_p(handle), ctypes.c_void_p(int(address)), buf, len(raw), ctypes.byref(n))
    if not ok or n.value != len(raw):
        raise ctypes.WinError()
    return n.value


WIN_W = 1920
WIN_H = 1079

try:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except: pass

    user32 = ctypes.windll.user32
    screen_width = int(user32.GetSystemMetrics(0))
    screen_height = int(user32.GetSystemMetrics(1))

    load_prc_file_data("", "win-size 1920 1079")
    load_prc_file_data("", "win-origin 0 0")
    load_prc_file_data("", "audio-library-name null")
    load_prc_file_data("", "window-title GLT Camera System")
    load_prc_file_data("", "undecorated 1")
    load_prc_file_data("", "sync-video 1")

    from ursina import *
    from panda3d.core import WindowProperties
    
    app = Ursina(audio=False)
    window.exit_button.enabled = False
    window.fps_counter.enabled = False
    try: window.entity_counter.enabled = False
    except: pass
    try: window.collider_counter.enabled = False
    except: pass

    _wp = WindowProperties()
    _wp.setSize(WIN_W, WIN_H)
    _wp.setOrigin(0, 0)
    _wp.setCursorHidden(True)   # ماوس روی پنجره‌ی اورسینا دیده نمی‌شود
    base.win.requestProperties(_wp)

    GWL_EXSTYLE = -20
    WS_EX_LAYERED = 0x00080000
    WS_EX_TRANSPARENT = 0x00000020
    LWA_ALPHA = 0x00000002
    HWND_TOPMOST = -1
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOACTIVATE = 0x0010

    JSON_PATH = os.path.join(CURRENT_DIR, "record.json")
    CONFIG_PATH = os.path.join(CURRENT_DIR, "config.json")
    BACKUP_FILE = os.path.join(CURRENT_DIR, "mem_backup.json")
    TEX_DIR = os.path.join(CURRENT_DIR, "tex")

    default_keys = {
        "hotkey_toggle": "f7",
        "hotkey_play": "f8",
        "key_action": "d",
        "key_back": "left",
        "key_q": "q",
        "key_w": "w",
        "key_d": "d"
    }
    
    default_config = {
        "process_name": "FL_2026.exe",
        "scene_theme": "T6",
        "profiles": {
            "FL_2026.exe": default_keys.copy(),
            "PES2021.exe": default_keys.copy()
        }
    }

    def load_config():
        data = default_config.copy()
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r") as f:
                    file_data = json.load(f)
                    data["process_name"] = file_data.get("process_name", "FL_2026.exe")
                    data["scene_theme"] = file_data.get("scene_theme", "T6")
                    
                    if "profiles" not in file_data:
                        prof = default_keys.copy()
                        for k in default_keys:
                            if k in file_data: prof[k] = file_data[k]
                        data["profiles"]["FL_2026.exe"] = prof
                    else:
                        for p in default_config["profiles"]:
                            data["profiles"][p] = {**default_keys, **file_data["profiles"].get(p, {})}
            except: pass
        return data

    config_data = load_config()

    def save_config():
        try:
            with open(CONFIG_PATH, "w") as f:
                json.dump(config_data, f, indent=4)
        except: pass

    def get_profile_keys():
        proc = config_data["process_name"]
        if proc not in config_data["profiles"]:
            config_data["profiles"][proc] = default_keys.copy()
        return config_data["profiles"][proc]

    def set_profile_key(key_name, val):
        proc = config_data["process_name"]
        if proc not in config_data["profiles"]:
            config_data["profiles"][proc] = default_keys.copy()
        config_data["profiles"][proc][key_name] = val
        save_config()

    def get_vk(key_name):
        if not key_name: return 0
        key_name = str(key_name).lower()
        vk_map = {
            'left': 0x25, 'up': 0x26, 'right': 0x27, 'down': 0x28,
            'enter': 0x0D, 'space': 0x20, 'shift': 0x10, 'ctrl': 0x11, 'alt': 0x12,
            'f1': 0x70, 'f2': 0x71, 'f3': 0x72, 'f4': 0x73, 'f5': 0x74,
            'f6': 0x75, 'f7': 0x76, 'f8': 0x77, 'f9': 0x78, 'f10': 0x79,
            'f11': 0x7A, 'f12': 0x7B
        }
        if key_name in vk_map: return vk_map[key_name]
        if len(key_name) == 1:
            c = key_name.upper()
            if 'A' <= c <= 'Z': return ord(c)
            if '0' <= c <= '9': return ord(c)
            try:
                return ctypes.windll.user32.VkKeyScanW(ord(key_name)) & 0xFF
            except: return 0
        return 0

    def vk_to_key_name(vk):
        vk_map_rev = {
            0x25: 'left', 0x26: 'up', 0x27: 'right', 0x28: 'down',
            0x0D: 'enter', 0x20: 'space', 0x10: 'shift', 0x11: 'ctrl', 0x12: 'alt',
            0x70: 'f1', 0x71: 'f2', 0x72: 'f3', 0x73: 'f4', 0x74: 'f5',
            0x75: 'f6', 0x76: 'f7', 0x77: 'f8', 0x78: 'f9', 0x79: 'f10',
            0x7A: 'f11', 0x7B: 'f12'
        }
        if vk in vk_map_rev: return vk_map_rev[vk]
        if 0x41 <= vk <= 0x5A: return chr(vk).lower()
        if 0x30 <= vk <= 0x39: return chr(vk)
        return None

    # =================================================================
    # [suite] MyMods settings — ModsConfig.json is the single source of
    # truth for the hotkeys and animation style chosen in the launcher.
    # Fail-safe: when the file is missing or a value is unusable the
    # tool keeps its own config.json defaults.
    #
    # BACKGROUND MODE: the control panel is NOT raised anymore — every
    # setting (style, play/record hotkeys, animation button bindings)
    # arrives through ModsConfig.json, so the tool runs invisibly in the
    # background. Flip GLT_START_HIDDEN to False to restore the original
    # front-raised startup.
    # =================================================================
    GLT_START_HIDDEN = True
    SUITE_REC_VK = 0

    def _sync_style_to_mods_config(style_name):
        """[suite] Write the style chosen in the tool panel back to
        ModsConfig.json so the MyMods GLT page preview stays in sync."""
        try:
            _cfg_path = os.path.join(os.path.dirname(CURRENT_DIR), "ModsConfig.json")
            if not os.path.exists(_cfg_path):
                return
            with open(_cfg_path, "r", encoding="utf-8") as _f:
                _mc = json.load(_f)
            _glt = (_mc.get("mods") or {}).get("Goal Line Technology")
            if isinstance(_glt, dict):
                _glt["glt_style"] = str(style_name).strip().upper()
                with open(_cfg_path, "w", encoding="utf-8") as _f:
                    json.dump(_mc, _f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def _apply_mods_config_overrides():
        """[suite] One-time startup sync: MyMods -> this tool.

        glt_play_vk   -> hotkey_play (REPLAY ANIMATION)
        glt_rec_vk    -> the manual-record key (same action as the panel
                         MANUAL RECORD button; see poll_global_hotkeys)
        glt_style     -> scene_theme (T5/T6)
        glt_key_*     -> the five ANIMATION BUTTON BINDINGS (key_action,
                         key_back, key_q, key_w, key_d). MyMods reads them
                         automatically from the game settings file
                         (settings.dat) and stores them in ModsConfig.json;
                         unknown/empty values keep this tool's own defaults.
        """
        global SUITE_REC_VK
        try:
            _cfg_path = os.path.join(os.path.dirname(CURRENT_DIR), "ModsConfig.json")
            if not os.path.exists(_cfg_path):
                return
            with open(_cfg_path, "r", encoding="utf-8") as _f:
                _mc = json.load(_f)
            _glt = (_mc.get("mods") or {}).get("Goal Line Technology") or {}
            _prof = get_profile_keys()
            try:
                _vk_play = int(str(_glt.get("glt_play_vk") or "").strip(), 16)
            except Exception:
                _vk_play = 0
            if _vk_play:
                _play_name = vk_to_key_name(_vk_play)
                if _play_name:
                    _prof["hotkey_play"] = _play_name
            try:
                _vk_rec = int(str(_glt.get("glt_rec_vk") or "").strip(), 16)
            except Exception:
                _vk_rec = 0
            if _vk_rec:
                SUITE_REC_VK = _vk_rec
            # [suite] animation button bindings delivered by MyMods through
            # ModsConfig.json — the tool never asks for them itself.
            for _ck, _pk in (
                ("glt_key_action", "key_action"),
                ("glt_key_back",   "key_back"),
                ("glt_key_q",      "key_q"),
                ("glt_key_w",      "key_w"),
                ("glt_key_d",      "key_d"),
            ):
                _kname = str(_glt.get(_ck) or "").strip().lower()
                if _kname:
                    _prof[_pk] = _kname
            _style = str(_glt.get("glt_style") or "").strip().upper()
            if _style in ("T5", "T6"):
                config_data["scene_theme"] = _style
                save_config()
            flog("SUITE", f"ModsConfig applied: play_vk=0x{_vk_play:02X} "
                           f"rec_vk=0x{SUITE_REC_VK:02X} style={config_data['scene_theme']} "
                           f"anim={_prof.get('key_action')}/{_prof.get('key_back')}"
                           f"/{_prof.get('key_q')}/{_prof.get('key_w')}/{_prof.get('key_d')}")
        except Exception as _e:
            try:
                flog("SUITE", f"ModsConfig overrides skipped: {_e!r}")
            except Exception:
                pass

    _apply_mods_config_overrides()

    def set_taskbar_visible(visible):
        try:
            hwnd_tray = ctypes.windll.user32.FindWindowW("Shell_TrayWnd", None)
            hwnd_secondary = ctypes.windll.user32.FindWindowW("Shell_SecondaryTrayWnd", None)
            show_cmd = 5 if visible else 0
            if hwnd_tray: ctypes.windll.user32.ShowWindow(hwnd_tray, show_cmd)
            if hwnd_secondary: ctypes.windll.user32.ShowWindow(hwnd_secondary, show_cmd)
        except: pass
        
    def set_window_opacity(opacity):
        try:
            hwnd = base.win.get_window_handle().get_int_handle()
            style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
            alpha = int(max(0.0, min(opacity, 1.0)) * 255)
            user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)
        except: pass

    def get_game_hwnd():
        if not pm or not pm.process_handle: return None
        hwnd_box = []
        def callback(hwnd, extra):
            lpdw_pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(lpdw_pid))
            if lpdw_pid.value == pm.process_id and user32.IsWindowVisible(hwnd):
                hwnd_box.append(hwnd)
                return False
            return True
        CMPFUNC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        user32.EnumWindows(CMPFUNC(callback), 0)
        return hwnd_box[0] if hwnd_box else None

    def focus_game_only():
        hwnd = get_game_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)

    tex_paths = {
        "t5": os.path.join(TEX_DIR, "T5.jpg"),
        "t6": os.path.join(TEX_DIR, "T6.jpg"),
        "line_t5": os.path.join(TEX_DIR, "Line_T5.jpg"),
        "line_t6": os.path.join(TEX_DIR, "Line_T6.jpg"),
        "ball": os.path.join(TEX_DIR, "ball.jpg"),
        "grass_gen": os.path.join(TEX_DIR, "T5_Grass_Detail.jpg"),
        "grass_overlay": os.path.join(TEX_DIR, "T5_Goal_Env4.png"),
        "board_strip": os.path.join(TEX_DIR, "Boards_Strip.jpg"),
        "net": os.path.join(TEX_DIR, "T5_Goal_Net2.png")
    }
    
    def get_safe_texture(path_str):
        if path_str and os.path.exists(path_str):
            try:
                panda_path = Filename.fromOsSpecific(os.path.abspath(path_str))
                raw_tex = loader.loadTexture(panda_path)
                if raw_tex:
                    tex = Texture(raw_tex) 
                    tex._cached_image = None 
                    return tex
            except: pass
        return 'white_cube'

    def generate_grass_texture(path_str, flog=None):
        # بافت جزئیات چمن (خاکستری خنثی) — دانه‌ریز یکنواخت بدون لکه‌های تیره، سبک عکس‌های مرجع
        if os.path.exists(path_str):
            return True
        try:
            from PIL import Image, ImageFilter
            import numpy as np
            size = 1024
            rng = np.random.default_rng(20170)
            fine = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)
            fine = (fine - fine.min()) / (fine.max() - fine.min() + 1e-6)
            fine = np.asarray(Image.fromarray((fine * 255.0).astype('uint8')).filter(ImageFilter.GaussianBlur(0.5)), dtype=np.float32) / 255.0 - 0.5
            med = rng.normal(0.0, 1.0, (size // 4, size // 4)).astype(np.float32)
            med = (med - med.min()) / (med.max() - med.min() + 1e-6)
            med = np.asarray(Image.fromarray((med * 255.0).astype('uint8')).resize((size, size), Image.BICUBIC).filter(ImageFilter.GaussianBlur(1.1)), dtype=np.float32) / 255.0 - 0.5
            val = np.clip(0.76 + 0.10 * fine + 0.13 * med, 0.0, 1.0)
            img = Image.fromarray((val * 255.0).astype('uint8')).convert('RGB')
            os.makedirs(os.path.dirname(path_str), exist_ok=True)
            img.save(path_str, quality=92)
            if flog: flog("GLT", "grass detail texture generated: " + os.path.basename(path_str))
            return True
        except Exception as e:
            if flog: flog("GLT", "grass texture generation failed: " + repr(e))
            return False


    def generate_goal_env_overlay(path_str, flog=None):
        # لایه محیطی پشت دروازه (RGBA):
        #   * لکه‌های زرد فرسوده فقط در نوار بین خط دروازه و تابلوها (z = 0 تا 10.5)
        #   * سایه سقف: قوس موازی خط عرضی زمین روی نوار زرد + تابلوها (مثل عکس مرجع)
        #   * تاریکی فقط برای قسمت‌های دورتر از تابلوها (z > 10.5)
        # مختصات بافت: بالای تصویر = لبه جلویی (z=-24 سمت زمین)، پایین تصویر = z=+45.5 پشت تابلوها
        if os.path.exists(path_str):
            return True
        try:
            from PIL import Image, ImageFilter
            import numpy as np
            W, H = 2048, 1024
            Z_FRONT, Z_BACK = -24.0, 45.5   # پوشش 69.5 متری: از روی چمن زمین تا پشت تابلوها
            BOARD_Z = 10.5
            rng = np.random.default_rng(777)
            zz = Z_FRONT + (np.arange(H, dtype=np.float32) / (H - 1)) * (Z_BACK - Z_FRONT)
            xs = ((np.arange(W, dtype=np.float32) / (W - 1)) - 0.5) * 120.0
            ZZ = np.repeat(zz[:, None], W, axis=1)

            def smoothstep(e0, e1, v):
                t = np.clip((v - e0) / (e1 - e0 + 1e-6), 0.0, 1.0)
                return t * t * (3.0 - 2.0 * t)

            # --- لکه‌های زرد فرسوده — کم، نامنظم و کم‌رنگ مثل عکس مرجع:
            #     * آستانه بالاتر => تعداد لکه‌ها کمتر
            #     * نزدیک خط دروازه ماسک می‌شوند (تا z~3.6 تقریباً هیچ لکه‌ای نیست)
            #     * شفافیت هر ناحیه تصادفی (نویز کم‌فرکانس) ---
            cells = rng.normal(0.0, 1.0, (9, 44)).astype(np.float32)
            cells = (cells - cells.min()) / (cells.max() - cells.min() + 1e-6)
            blotch = np.asarray(Image.fromarray((cells * 255.0).astype('uint8')).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(9)), dtype=np.float32) / 255.0
            cells2 = rng.normal(0.0, 1.0, (30, 150)).astype(np.float32)
            cells2 = (cells2 - cells2.min()) / (cells2.max() - cells2.min() + 1e-6)
            blotch2 = np.asarray(Image.fromarray((cells2 * 255.0).astype('uint8')).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(2.6)), dtype=np.float32) / 255.0
            blotch = np.clip(blotch * 0.74 + blotch2 * 0.36 - 0.08, 0.0, 1.0)
            strip = smoothstep(0.5, 2.0, ZZ) * (1.0 - smoothstep(7.0, 10.2, ZZ))
            near_fade = 1.0 - 0.85 * smoothstep(3.6, 0.7, ZZ)   # ماسک نزدیک دروازه
            arand_c = rng.normal(0.0, 1.0, (7, 26)).astype(np.float32)
            arand_c = (arand_c - arand_c.min()) / (arand_c.max() - arand_c.min() + 1e-6)
            arand = np.asarray(Image.fromarray((arand_c * 255.0).astype('uint8')).resize((W, H), Image.BICUBIC).filter(ImageFilter.GaussianBlur(4)), dtype=np.float32) / 255.0
            ascale = 0.25 + 0.75 * arand    # شفافیت تصادفی هر ناحیه
            # تراکم بیشتر سمت گوشه سایه‌دار (x منفی) مثل مرجع
            side_bias = np.clip((-xs - 10.0) / 40.0, 0.0, 1.0) * 0.10
            ymask = np.clip((blotch - 0.47 + side_bias[None, :]) * 3.4, 0.0, 1.0) * strip * near_fade
            yalpha = ymask * 0.42 * ascale
            grain = rng.normal(0.0, 1.0, (H, W)).astype(np.float32)
            grain = (grain - grain.min()) / (grain.max() - grain.min() + 1e-6)
            grain = np.asarray(Image.fromarray((grain * 255.0).astype('uint8')).filter(ImageFilter.GaussianBlur(0.7)), dtype=np.float32) / 255.0
            ycol = np.zeros((H, W, 3), dtype=np.float32)
            ycol[..., 0] = 0.62 + 0.16 * grain
            ycol[..., 1] = 0.60 + 0.16 * grain
            ycol[..., 2] = 0.25 + 0.10 * grain

            # --- سایه خود تابلوها: نوار باریک نرم چسبیده به جلوی تابلو (سراسر عرض) ---
            dark = np.exp(-((ZZ - (BOARD_Z - 1.0)) ** 2) / (2.0 * 1.2 ** 2)) * 0.12

            # --- سایه سقف استادیوم: قوس موازی خط عرضی زمین (مثل عکس مرجع) —
            #     خمیدگی به سمت «داخل» زمین (مثل مرجع): میانه قوس (x=0) عقب‌ترین نقطه (z≈4.6) و
            #     دو سر قوس به سمت خط دروازه می‌آیند؛ سایه 4.6-0.0032x² موازی لبه سقف است و
            #     در کل عرض زمین روی لکه‌های زرد + تابلوهای تبلیغاتی می‌افتد
            #     سایه روی لکه‌های زرد + تابلوهای تبلیغاتی پشت زمین می‌افتد ---
            z_edge = 4.6 - 0.0032 * xs ** 2
            s_cur = smoothstep(0.0, 2.6, ZZ - z_edge[None, :]) * 0.52
            s_cur *= (1.0 - smoothstep(48.0, 58.0, np.abs(xs)))[None, :]   # محو سایه قبل از لبه بافت

            # --- تاریکی فقط دورتر از تابلوها ---
            dark += smoothstep(BOARD_Z + 0.6, BOARD_Z + 3.6, ZZ) * 0.42
            dark += smoothstep(BOARD_Z + 7.0, BOARD_Z + 19.0, ZZ) * 0.18

            total_dark = np.clip(dark + s_cur, 0.0, 0.62)
            alpha = np.clip(yalpha + total_dark, 0.0, 0.62)
            dark_w = np.clip(total_dark / (total_dark + yalpha + 1e-6), 0.0, 1.0)[..., None]
            rgb = ycol * (1.0 - dark_w)
            rgba = np.dstack([rgb, alpha])
            rgba = rgba[::-1, :, :]   # Panda3D کارت را V-برعکس نمونه‌برداری می‌کند: سطر ۰ تصویر <- حاشیه پایین کارت (z دور)
            img = Image.fromarray((np.clip(rgba, 0.0, 1.0) * 255.0).astype('uint8'))
            os.makedirs(os.path.dirname(path_str), exist_ok=True)
            img.save(path_str)
            if flog: flog("GLT", "goal env overlay generated: " + os.path.basename(path_str))
            return True
        except Exception as e:
            if flog: flog("GLT", "goal env overlay generation failed: " + repr(e))
            return False
    def generate_board_strip(path_str, flog=None):
        # نوار تابلوهای تبلیغاتی LED — 8 پیام انگلیسی درباره PES MODS BY MILAD
        if os.path.exists(path_str):
            return True
        try:
            from PIL import Image, ImageDraw, ImageFont
            PW, PH = 512, 128
            phrases = [
                "PES MODS BY MILAD",
                "GLT GOAL LINE TECHNOLOGY",
                "VAR REVIEW SYSTEM",
                "PES 2017 \u2022 PES 2021",
                "MILAD MODS & TOOLS",
                "PES MODS BY MILAD",
                "PRO EVOLUTION MODDING",
                "PES MODS COMMUNITY",
            ]
            font = None
            for fname in ("arialbd.ttf", "segoeuib.ttf", "calibrib.ttf", "arial.ttf", "tahoma.ttf",
                          "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
                try:
                    font = ImageFont.truetype(fname, 42)
                    break
                except Exception:
                    continue
            if font is None:
                font = ImageFont.load_default()
            strip = Image.new("RGB", (PW * 8, PH), (22, 56, 150))
            d = ImageDraw.Draw(strip)
            for i, txt in enumerate(phrases):
                x0 = i * PW
                d.rectangle([x0, 0, x0 + PW - 1, 4], fill=(46, 100, 215))
                d.rectangle([x0, PH - 6, x0 + PW - 1, PH - 1], fill=(14, 36, 104))
                bbox = d.textbbox((0, 0), txt, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                scale = min(1.0, (PW - 40.0) / max(tw, 1.0))
                if scale < 1.0:
                    f2 = ImageFont.truetype(font.path, int(42 * scale)) if hasattr(font, "path") else font
                    bbox = d.textbbox((0, 0), txt, font=f2)
                    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    font_use = f2
                else:
                    font_use = font
                d.text((x0 + (PW - tw) / 2 - bbox[0], (PH - 12 - th) / 2 - bbox[1]), txt, font=font_use, fill=(235, 245, 255))
            # بافت نقطه‌ای LED (خطوط افقی محو)
            for yy in range(1, PH, 3):
                d.line([(0, yy), (PW * 8, yy)], fill=(17, 44, 126), width=1)
            os.makedirs(os.path.dirname(path_str), exist_ok=True)
            strip.save(path_str, quality=90)
            if flog: flog("GLT", "board strip generated: " + os.path.basename(path_str))
            return True
        except Exception as e:
            if flog: flog("GLT", "board strip generation failed: " + repr(e))
            return False
    def generate_goal_net_texture(path_str, flog=None):
        # تور دروازه — شبکه مربعی سفید با نخ‌های ضخیم نیمه‌مات روی پس‌زمینه‌ی کاملا شفاف
        if os.path.exists(path_str):
            return True
        try:
            from PIL import Image, ImageDraw
            S = 512
            cell = 64          # ۸ خانه در هر تایل؛ هر خانه معادل 0.12 متر تور
            lw = 12            # نخ‌های ضخیم‌تر تا تور در فواصل دور و زوایای مایل هم دیده شود
            img = Image.new("RGBA", (S, S), (255, 255, 255, 0))
            d = ImageDraw.Draw(img)
            col = (255, 255, 255, 235)   # آلفای بالا برای دیده شدن تور از فاصله‌ی دور
            for i in range(0, S + 1, cell):
                d.line([(i, 0), (i, S)], fill=col, width=lw)
                d.line([(0, i), (S, i)], fill=col, width=lw)
            os.makedirs(os.path.dirname(path_str), exist_ok=True)
            img.save(path_str)
            if flog: flog("GLT", "goal net texture generated: " + os.path.basename(path_str))
            return True
        except Exception as e:
            if flog: flog("GLT", "goal net texture generation failed: " + repr(e))
            return False
    generate_grass_texture(tex_paths["grass_gen"], flog)
    generate_goal_env_overlay(tex_paths["grass_overlay"], flog)
    generate_board_strip(tex_paths["board_strip"], flog)
    generate_goal_net_texture(tex_paths["net"], flog)
    
    ground_tex = get_safe_texture(tex_paths["t5"] if config_data["scene_theme"] == "T5" else tex_paths["t6"])
    initial_line_tex = get_safe_texture(tex_paths["line_t5"] if config_data["scene_theme"] == "T5" else tex_paths["line_t6"])
    ball_tex = get_safe_texture(tex_paths["ball"])

    ground = Entity(model='plane', scale=600, texture=ground_tex, texture_scale=(200, 200))
    goal_line = Entity(model='cube', scale=(60, 0.01, 0.12), texture=initial_line_tex, texture_scale=(250, 1), z=0, y=0.007)
    
    post_l = Entity(model='cube', scale=(0.12, 2.44, 0.12), x=-3.66, y=1.22, color=color.white, unlit=True)
    post_r = Entity(model='cube', scale=(0.12, 2.44, 0.12), x=3.66, y=1.22, color=color.white, unlit=True)
    bar = Entity(model='cube', scale=(7.44, 0.12, 0.12), y=2.50, color=color.white, unlit=True)

    # --- تور دروازه: با افزودن net_parts به حلقه‌های تیرک، تور همیشه همگام با تیرک‌ها نمایان/مخفی می‌شود ---
    net_tex = get_safe_texture(tex_paths["net"])
    # تور از دور و در زوایای مایل محو می‌شد: mipmap + anisotropic برای وضوح نخ‌ها در هر فاصله و زاویه
    try:
        from panda3d.core import SamplerState
        net_tex.filtering = 'mipmap'
        net_tex._texture.setMagfilter(SamplerState.FT_linear)
        net_tex._texture.setAnisotropicDegree(8)
    except Exception:
        pass
    # تور سقف: از زیر بردار به‌صورت کاملا افقی تا عمق 1.7 متر پشت خط دروازه — فرم مکعبی مدرن
    net_top = Entity(model='cube', scale=(7.44, 0.02, 1.7), position=(0, 2.44, 0.85), texture=net_tex, texture_scale=(7.75, 1.77), unlit=True)
    # دیوار پشت تور: کاملا عمودی تا سطح زمین — جعبه‌ی مکعبی مدرن
    net_back = Entity(model='cube', scale=(7.44, 2.44, 0.02), position=(0, 1.22, 1.7), texture=net_tex, texture_scale=(7.75, 2.54), unlit=True)

    def _net_side_mesh():
        # مستطیل تور کناری در صفحه‌ی x=0: (z,y) = (0,0),(1.7,0),(1.7,2.44),(0,2.44) — پروفیل مکعبی مدرن
        vs = [Vec3(0, 0, 0), Vec3(0, 0, 1.7), Vec3(0, 2.44, 1.7), Vec3(0, 2.44, 0)]
        uvs = [(v[2] / 0.96, v[1] / 0.96) for v in vs]
        tris = [(0, 1, 2), (0, 2, 3), (0, 2, 1), (0, 3, 2)]   # دو جهت برای دوسویه دیده شدن
        return Mesh(vertices=vs, triangles=tris, uvs=uvs)

    net_side_l = Entity(model=_net_side_mesh(), position=(-3.66, 0, 0), texture=net_tex, unlit=True)
    net_side_r = Entity(model=_net_side_mesh(), position=(3.66, 0, 0), texture=net_tex, unlit=True)
    # قاب پشت تور: دو تیرک عمودی عقب + ریل بالا و پایین — ظاهر مدرن دروازه‌های جعبه‌ای
    net_frame_l = Entity(model='cube', scale=(0.06, 2.44, 0.06), position=(-3.66, 1.22, 1.7), color=color.white, unlit=True)
    net_frame_r = Entity(model='cube', scale=(0.06, 2.44, 0.06), position=(3.66, 1.22, 1.7), color=color.white, unlit=True)
    net_frame_top = Entity(model='cube', scale=(7.44, 0.06, 0.06), position=(0, 2.44, 1.7), color=color.white, unlit=True)
    net_frame_bottom = Entity(model='cube', scale=(7.44, 0.06, 0.06), position=(0, 0.03, 1.7), color=color.white, unlit=True)
    net_parts = [net_top, net_back, net_side_l, net_side_r, net_frame_l, net_frame_r, net_frame_top, net_frame_bottom]

    ball = Entity(model='sphere', scale=0.22, x=0, y=0.11, z=0, texture=ball_tex, rotation=(90, 45, 0))
    ball_shadow = Entity(model='circle', scale=0.22, y=0.01, x=0, z=0, color=color.hsv(0, 0, 0, 0.4), rotation_x=90)

    line_thickness = 0.12
    six_yard_depth = 5.5   # استاندارد؛ دقیقاً روی مرز نوار اول چمن
    six_yard_x = 9.16      # استاندارد؛ عرض محوطه دروازه 18.32 متر
    side_length = six_yard_depth + (line_thickness / 2)
    side_z = -(side_length / 2)
    front_length = (six_yard_x * 2) + line_thickness
    six_yard_left = Entity(model='cube', scale=(line_thickness, 0.01, side_length), x=-six_yard_x, z=side_z, y=0.008, color=color.white)
    six_yard_right = Entity(model='cube', scale=(line_thickness, 0.01, side_length), x=six_yard_x, z=side_z, y=0.008, color=color.white)
    six_yard_front = Entity(model='cube', scale=(front_length, 0.01, line_thickness), x=0, z=-six_yard_depth, y=0.008, color=color.white)
    
    pen_area_left = Entity(model='cube', scale=(line_thickness, 0.01, 16.5), x=-20.16, z=-8.25, y=0.008, color=color.white)
    pen_area_right = Entity(model='cube', scale=(line_thickness, 0.01, 16.5), x=20.16, z=-8.25, y=0.008, color=color.white)
    pen_area_front = Entity(model='cube', scale=(40.32 + line_thickness, 0.01, line_thickness), x=0, z=-16.5, y=0.008, color=color.white)

    # 2. نقطه پنالتی (فاصله 11 متری)
    pen_spot = Entity(model=Circle(resolution=32), scale=(0.24, 0.24, 0.24), x=0, z=-11.0, y=0.008, color=color.white, rotation_x=90)

    # 3. اصلاح عرض خط دروازه برای پوشش کل زمین و اضافه کردن خطوط طولی (Touchlines)
    # زمین استاندارد عرض 68 متر دارد، پس مرزها در 34 و -34 هستند.
    goal_line.scale = (68.0, 0.01, line_thickness)
    touchline_l = Entity(model='cube', scale=(line_thickness, 0.01, 52.5), x=-34.0, z=-26.25, y=0.008, color=color.white)
    touchline_r = Entity(model='cube', scale=(line_thickness, 0.01, 52.5), x=34.0, z=-26.25, y=0.008, color=color.white)

    # --- تابع کمکی هوشمند برای رسم خطوط قوسی کاملاً نرم ---
    # این تابع با استفاده از ریاضیات، مستطیل‌های ریزی را با زاویه دقیق به هم می‌چسباند 
    # تا هیچ فاصله‌ای بینشان نیفتد و قوس کاملاً صاف (Vector-like) دیده شود.
    def create_smooth_arc(center_x, center_z, radius, start_angle, end_angle, segments=50):
        arc_parent = Entity()
        angle_step = (end_angle - start_angle) / segments
        for i in range(segments):
            a1 = math.radians(start_angle + i * angle_step)
            a2 = math.radians(start_angle + (i + 1) * angle_step)
            
            x1, z1 = center_x + math.cos(a1) * radius, center_z + math.sin(a1) * radius
            x2, z2 = center_x + math.cos(a2) * radius, center_z + math.sin(a2) * radius
            
            # فاصله دقیق دو نقطه
            dist = math.sqrt((x2 - x1)**2 + (z2 - z1)**2)
            mid_x, mid_z = (x1 + x2) / 2, (z1 + z2) / 2
            
            seg = Entity(parent=arc_parent, model='cube', color=color.white)
            seg.position = Vec3(mid_x, 0.008, mid_z)
            seg.look_at(Vec3(x2, 0.008, z2))
            
            # طول را کمی بیشتر میدهیم (dist + 0.02) تا گوشه‌ها کاملاً در هم فرو بروند و بریدگی دیده نشود
            seg.scale = (line_thickness, 0.01, dist + 0.02)
        return arc_parent

    # 4. قوس پشت محوطه جریمه (Penalty Arc)
    # این قوس دقیقا قسمتی از دایره به مرکز نقطه پنالتی و شعاع 9.15 است که بیرون محوطه میفتد
    penalty_arc = create_smooth_arc(0, -11.0, 9.15, -143.04, -36.96, segments=50)

    # 5. خطوط کرنر (Corner Arcs) - شعاع استاندارد 1 متر
    corner_arc_left = create_smooth_arc(-34.0, 0, 1.0, -90, 0, segments=20)
    corner_arc_right = create_smooth_arc(34.0, 0, 1.0, 180, 270, segments=20)

    # جبران دقت بافر عمق در فواصل دور (ضد پرپر زدن): خطوط سفید همیشه روی چمن و لایه محیطی
    for _ln in (goal_line, six_yard_left, six_yard_right, six_yard_front, pen_area_left,
                pen_area_right, pen_area_front, touchline_l, touchline_r, penalty_arc,
                corner_arc_left, corner_arc_right, pen_spot, ball_shadow):
        try:
            _ln.setDepthOffset(4)
        except Exception:
            pass

    # --- استایل 1 (T5): زمین چمن واقعی با نوارهای استاندارد روشن/تیره ---
    STRIPE_LENGTH = 5.5   # مرز هر نوار روی خط محوطه دروازه (5.5) و محوطه جریمه (16.5=3×5.5)
    STRIPE_COUNT = 21            # 21 نوار × 5.5 متر = 115.5 متر (پوشش کامل زمین ۱۰۵ متری + حاشیه)
    STRIPE_HALF_WIDTH = 34.06    # نیم‌عرض استاندارد زمین (34) + نصف ضخامت خط لمسی
    STRIPE_COLOR_LIGHT = color.rgb(0.435, 0.685, 0.170)   # سبز کمرنگ — کالیبره با عکس خود بازی
    STRIPE_COLOR_DARK = color.rgb(0.355, 0.565, 0.130)    # سبز پررنگ — کالیبره با عکس خود بازی
    # رنگ نوار اولِ چسبیده به خط عرضی زمین بر اساس دروازه تشخیص داده شده:
    #   دروازه چپ (x منفی)   -> نوار اول کمرنگ (سپس کمرنگ/پررنگ یکی‌درمیان)
    #   دروازه راست (x مثبت) -> نوار اول پررنگ
    # (برای تغییر، مقدار True/False هر سمت را عوض کنید)
    FIRST_STRIPE_DARK = {"left": False, "right": True}
    stripe_group = Entity(enabled=False)
    stripe_entities = []
    _stripe_tex = get_safe_texture(tex_paths["grass_gen"] if os.path.exists(tex_paths["grass_gen"]) else tex_paths["t5"])
    for _i in range(STRIPE_COUNT):
        _st = Entity(parent=stripe_group, model='cube',
                     scale=(STRIPE_HALF_WIDTH * 2.0, 0.006, STRIPE_LENGTH),
                     x=0, y=0.0035, z=-(_i * STRIPE_LENGTH + STRIPE_LENGTH / 2.0),
                     texture=_stripe_tex,
                     texture_scale=(STRIPE_HALF_WIDTH * 2.0 / 3.0, STRIPE_LENGTH / 3.0),
                     color=STRIPE_COLOR_DARK if _i % 2 == 0 else STRIPE_COLOR_LIGHT)
        stripe_entities.append(_st)
    for _st in stripe_entities:
        try:
            _st.setDepthOffset(1)
        except Exception:
            pass

    def update_stripe_colors():
        # اعمال رنگ نوارها بر اساس دروازه تشخیص داده شده (چپ/راست) — در شروع انیمیشن صدا زده می‌شود
        try:
            first_dark = FIRST_STRIPE_DARK[get_goal_side()]
        except Exception:
            first_dark = True
        for i, st in enumerate(stripe_entities):
            is_dark = (i % 2 == 0) if first_dark else (i % 2 == 1)
            st.color = STRIPE_COLOR_DARK if is_dark else STRIPE_COLOR_LIGHT

    def apply_ground_theme(theme_name):
        # تم زمین: استایل 1 = چمن تولیدشده + نوارهای واقعی | استایل 2 = تکسچر T6 (دقیقاً مانند قبل)
        if theme_name == "T5":
            _gen = tex_paths["grass_gen"] if os.path.exists(tex_paths["grass_gen"]) else tex_paths["t5"]
            ground.texture = get_safe_texture(_gen)
            ground.color = color.rgb(0.368, 0.553, 0.158)
            stripe_group.enabled = True
            for _env in t5_env_nodes:
                _env.show()
        else:
            ground.texture = get_safe_texture(tex_paths["t6"])
            ground.color = color.white
            stripe_group.enabled = False
            for _env in t5_env_nodes:
                _env.hide()

    # --- محیط استادیوم استایل 1: لایه پشت دروازه + تابلوهای تبلیغاتی (Panda3D خام برای کنترل دقیق جهت) ---
    from panda3d.core import CardMaker, TransparencyAttrib, TextureStage as _P3DTexStage, Texture as _P3DTexture
    t5_env_nodes = []

    def _make_env_card(_name, _fx0, _fx1, _fy0, _fy1, _tex_path, _pos, _h=0.0, _p=0.0, _alpha=False, _bias=0):
        try:
            if not os.path.exists(_tex_path):
                return None
            _cm = CardMaker(_name)
            _cm.setFrame(_fx0, _fx1, _fy0, _fy1)
            _np = render.attachNewNode(_cm.generate())
            _np.setPos(*_pos)
            _np.setH(_h)
            _np.setP(_p)
            _tex = loader.loadTexture(Filename.fromOsSpecific(os.path.abspath(_tex_path)))
            if _tex is None:
                _np.removeNode()
                return None
            _np.setTexture(_tex, 1)
            try:
                _tex.setMinfilter(_P3DTexture.FTLinearMipmapLinear)
                _tex.setMagfilter(_P3DTexture.FTLinear)
                _tex.setAnisotropicDegree(8)
            except Exception:
                pass
            if _bias:
                _np.setDepthOffset(_bias)
            if _alpha:
                _np.setTransparency(TransparencyAttrib.MAlpha)
            return _np
        except Exception as _e:
            try: flog("GLT", "env card failed: " + _name + " " + repr(_e))
            except: pass
            return None

    # لایه محیطی پشت دروازه (120x69.5 متر، از روی چمن زمین z=-24 تا پشت تابلوها z=+45.5)
    _env_ov = _make_env_card("t5_goal_env", -60, 60, -24, 45.5, tex_paths["grass_overlay"], (0, 0.0075, 0), _p=-90.0, _alpha=True, _bias=2)
    # تابلوی پشت دروازه (رو به زمین در z=+10.5؛ تا x=±45.4 امتداد یافته برای آب‌بندی گوشه‌ها)
    _env_b1 = _make_env_card("t5_board_back", -45.4, 45.4, 0, 1, tex_paths["board_strip"], (0, 0, 10.5), _h=0.0)
    # تابلوهای کناری دقیقاً روی x=±45 (لبه تابلوی پشت) از z=+10.7 تا z=-45 — گوشه کامل بدون روزنه
    _env_b2 = _make_env_card("t5_board_left", -27.85, 27.85, 0, 1, tex_paths["board_strip"], (-45, 0, -17.15), _h=90.0)
    _env_b3 = _make_env_card("t5_board_right", -27.85, 27.85, 0, 1, tex_paths["board_strip"], (45, 0, -17.15), _h=-90.0)
    for _env_n in (_env_ov, _env_b1, _env_b2, _env_b3):
        if _env_n is not None:
            _env_n.hide()
            t5_env_nodes.append(_env_n)

    # --- لبه استادیوم: دیوار سکو + سقف قوسی — بخش خمیده موازی خط عرضی زمین (مثل عکس مرجع):
    #     خمیدگی به سمت «داخل» زمین: مرکز قوس (x=0) عقب‌ترین نقطه (z=15.5) و دو سر قوس
    #     به سمت خط دروازه/خطوط لمسی می‌آیند — هم‌شکل سایه (4.6-0.0032x²) → سایه موازی سقف
    #     (کاسه استادیوم)؛ unlit برای سیلوئت تیره یکدست ---
    _ROOF_Z = 15.5
    _ROOF_K = 0.0032
    _ROOF_SEGS = 19
    _ROOF_SEGW = 150.0 / _ROOF_SEGS
    _roof_group = Entity(enabled=False)
    for _si in range(_ROOF_SEGS):
        _sx = -75.0 + (_si + 0.5) * _ROOF_SEGW
        _sz = _ROOF_Z - _ROOF_K * _sx * _sx
        _tang = math.degrees(math.atan(-2.0 * _ROOF_K * _sx))
        _sw = _ROOF_SEGW + 1.6
        Entity(parent=_roof_group, model='cube', scale=(_sw, 16, 2.0), position=(_sx, 8.5, _sz + 4.5),
               rotation_y=_tang, color=color.rgb(0.10, 0.11, 0.16), unlit=True)
        Entity(parent=_roof_group, model='cube', scale=(_sw, 0.7, 17.0), position=(_sx, 22.0, _sz + 11.0),
               rotation_y=_tang, color=color.rgb(0.12, 0.13, 0.18), unlit=True)
        Entity(parent=_roof_group, model='cube', scale=(_sw, 0.55, 3.4), position=(_sx, 21.4, _sz + 2.6),
               rotation_y=_tang, rotation_x=16, color=color.rgb(0.12, 0.13, 0.18), unlit=True)
    t5_env_nodes.append(_roof_group)

    def update_env_mirror():
        # آینه‌سازی لایه محیطی برای دروازه چپ تا سایه همیشه سمت گوشه‌ی نزدیک به دوربین باشد
        try:
            _mir = -1.0 if get_goal_side() == "left" else 1.0
            if _env_ov is not None:
                _env_ov.setTexScale(_P3DTexStage.getDefault(), _mir, 1.0)
        except Exception:
            pass

    kernel32 = ctypes.windll.kernel32
    kernel32.VirtualProtectEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
    kernel32.VirtualProtectEx.restype = ctypes.c_int
    kernel32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.WriteProcessMemory.restype = ctypes.c_int

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_size_t)]
    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort), ("wParamH", ctypes.c_ushort)]
    class INPUT_UNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]
    class INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", INPUT_UNION)]
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    # --- Pointers & Constants FL 2026 / PES 2021 ---
    PATCHES = {0x217A379: b'\x90\x90\x90\x90\x90\x90', 0x217A3EE: b'\x90\x90\x90\x90\x90\x90', 0x217A293: b'\x90\x90\x90\x90\x90'}
    ROTATION_MAX_OFFSET = 0x2179F91
    ROTATION_MIN_OFFSET = 0x2179F9B
    NOP_8 = b'\x90\x90\x90\x90\x90\x90\x90\x90'
    NEW_HEIGHT_STATIC_OFFSET = 0x259BDD8
    CAM3_HEIGHT_PATTERN = b'\xf3\x0f\x58\xe0\xf3\x0f\x11\x46\x14\xc7\x46\x10'
    ZOOM_INSTRUCTION_OFFSET = 0x217A4BA
    ZOOM_ORIG_BYTES = b'\xE9\x26\xF1\x3E'
    
    presets_right = {
        1: {"base": 39.00, "height": 40.00, "long": 52.50, "lat": -80.00, "hor_rot": 356.35, "vert_rot": 321.80, "zoom": 0.20},
        2: {"base": 39.00, "height": 40.00, "long": 52.50, "lat": -80.00, "hor_rot": 356.35, "vert_rot": 321.80, "zoom": 0.20}
    }
    presets_left = {
        1: {"base": 39.00, "height": 40.00, "long": -52.50, "lat": -80.00, "hor_rot": 3.65, "vert_rot": 321.80, "zoom": 0.20},
        2: {"base": 39.00, "height": 40.00, "long": -52.50, "lat": -80.00, "hor_rot": 3.65, "vert_rot": 321.80, "zoom": 0.20}
    }

    pm = None
    base_address = None
    cam3_height_address = None
    state_static_address = None
    aux_state_address = None
    
    hook_address = 0
    cave_address = 0
    data_address = 0
    orig_bytes = b'\x0F\x29\x80\x50\x04\x00\x00'
    is_hooked = False
    
    recorded_frames = []
    freeze_frame = None
    freeze_idx = -1
    
    current_state_str = "STOP"
    candidate_state_str = "STOP"
    state_stable_count = 0
    last_state_str = "STOP"
    
    connection_time = 0.0
    
    
    playback_state = "IDLE"
    last_live_coords = None
    unchanged_count = 0
    tap_min_diff = float('inf')
    tap_target_coords = None       # مختصات فریم کمترین خطا در فاز تپ (هدف برگشت)
    back_best_diff = float('inf')  # بهترین اختلاف در فاز برگشت
    back_taps = 0                  # شمارنده تپ‌های برگشت
    speed_ok_count = 0
    current_glt_scenario = 0
    manual_record_state = "IDLE"
    manual_last_coords = None
    manual_unchanged_count = 0
    
    backup_data = {}
    backup_captured = False
    
    is_goal_scored = False
    overlay_win = None
    overlay_canvas = None
    ui_progress = 0.0

    is_animating_camera = False
    goal_ui_fired = False   # آیا GOAL/NO GOAL در این پخش نمایش داده شده است
    anim_state = None
    anim_start_time = 0
    anim_duration = 1.0
    anim_callback = None
    pending_animation = None

    f1_pos = Vec3(0, 0, 0)
    f1_rot = Vec3(0, 0, 0)
    f1_look_rot = Vec3(0, 0, 0)         # زاویه‌ی look_at از f1_pos به توپ (برای pre_align)
    f1_look_rot_actual = Vec3(0, 0, 0)  # زاویه‌ی واقعی پایان move_backward (برای post_unalign)
    f2_pos = Vec3(0, 0, 0)
    f2_pos_end = Vec3(0, 0, 0)          # موقعیت دوربین پس از جابجایی 0.11 در hold_top
    f2_rot_start = Vec3(0, 0, 0) 
    f2_rot_end = Vec3(0, 0, 0)
    target_yaw_anim = 0.0


    root = tk.Tk()
    root.title("Goal Line Technology  [v2 PLAYBACK-FIXED]")
    root.geometry("400x720")
    root.configure(bg="#121212")

    # [suite] background mode — hide the control panel immediately so it
    # never flashes or steals focus; all settings come from MyMods through
    # ModsConfig.json. The panel-toggle hotkey still works as before.
    if GLT_START_HIDDEN:
        root.withdraw()

    _tk_alive = True
    goal_side_val = "right"
    ui_images = {}

    def load_ui_images():
        img_list = {
            "icon_action": "icon_action.png",
            "icon_back": "icon_back.png",
            "icon_q": "icon_q.png",
            "icon_w": "icon_w.png",
            "icon_d": "icon_d.png",
            "thumb_t5": "thumb_t5.png",
            "thumb_t6": "thumb_t6.png"
        }
        for key, filename in img_list.items():
            try:
                path = os.path.join(TEX_DIR, filename)
                if os.path.exists(path):
                    ui_images[key] = tk.PhotoImage(file=path)
            except: pass

    load_ui_images()

    def _on_root_close():
        global _tk_alive
        _tk_alive = False
        set_taskbar_visible(True)
        _shutdown_cleanup()
        if os.path.exists(JSON_PATH):
            try: os.remove(JSON_PATH)
            except: pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", _on_root_close)

    # --- Animated Action Log ---
    actions_list = []
    _anim_log_job = None
    
    def blend_color(fg_hex, bg_hex, alpha):
        fg = tuple(int(fg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        bg = tuple(int(bg_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
        r = int(fg[0] * alpha + bg[0] * (1 - alpha))
        g = int(fg[1] * alpha + bg[1] * (1 - alpha))
        b = int(fg[2] * alpha + bg[2] * (1 - alpha))
        return f"#{r:02x}{g:02x}{b:02x}"

    def set_action_status(text, color="#f1c40f"):
        global actions_list
        prefixes = ["Manual Rec:"]
        
        if actions_list:
            top_text = actions_list[0]["text"]
            if top_text == text:
                return
                
            is_update = False
            for prefix in prefixes:
                if text.startswith(prefix) and top_text.startswith(prefix):
                    is_update = True
                    break
                    
            if is_update:
                actions_list[0]["text"] = text
                actions_list[0]["color"] = color
                animate_action_log() 
                return

        actions_list.insert(0, {"text": text, "color": color, "current_y": 70, "target_y": 50, "alpha": 1.0})
        
        for i, act in enumerate(actions_list):
            act["target_y"] = 50 - (i * 20)
        
        if len(actions_list) > 3:
            actions_list.pop()
        
        animate_action_log()

    def animate_action_log():
        global _anim_log_job
        if not _tk_alive: return
        
        if _anim_log_job is not None:
            root.after_cancel(_anim_log_job)
            _anim_log_job = None
            
        action_canvas.delete("all")
        needs_anim = False
        
        for i, act in enumerate(actions_list):
            if abs(act["current_y"] - act["target_y"]) > 0.5:
                act["current_y"] += (act["target_y"] - act["current_y"]) * 0.2
                needs_anim = True
            
            if i == 0: act["alpha"] = 1.0
            elif i == 1: act["alpha"] = 0.5
            else: act["alpha"] = 0.2
            
            blended = blend_color(act["color"], "#121212", act["alpha"])
            font_w = "bold" if i == 0 else "normal"
            action_canvas.create_text(5, act["current_y"], text=act["text"], fill=blended, font=("Segoe UI", 10, font_w), anchor="w")
            
        if needs_anim:
            _anim_log_job = root.after(16, animate_action_log)

    def init_overlay():
        global overlay_win, overlay_canvas
        if overlay_win is not None: return
        overlay_win = tk.Toplevel(root)
        overlay_win.overrideredirect(True)
        overlay_win.wm_attributes("-transparentcolor", "black")
        overlay_win.wm_attributes("-topmost", True)
        W, H = 500, 100
        x = (screen_width - W) // 2
        y = screen_height - H - 80
        overlay_win.geometry(f"{W}x{H}+{x}+{y}")
        overlay_canvas = tk.Canvas(overlay_win, width=W, height=H, bg="black", highlightthickness=0)
        overlay_canvas.pack()
        overlay_win.withdraw()

    def draw_ui(progress, is_goal):
        overlay_canvas.delete("all")
        W, H = 500, 100
        cx, cy = W / 2, H / 2
        color1 = (0, 144, 0) if is_goal else (120, 0, 0)
        color2 = (0, 197, 30) if is_goal else (200, 0, 0)
        text_str = "G O A L" if is_goal else "N O  G O A L"
        box_w, box_h = 350, 50
        left = (W - box_w) / 2
        top = (H - box_h) / 2
        for i in range(box_h):
            ratio = i / box_h
            intensity = 1.0 - ratio 
            r = int(color1[0] + (color2[0] - color1[0]) * intensity)
            g = int(color1[1] + (color2[1] - color1[1]) * intensity)
            b = int(color1[2] + (color2[2] - color1[2]) * intensity)
            hex_color = f"#{r:02x}{g:02x}{b:02x}"
            overlay_canvas.create_line(left, top + i, left + box_w, top + i, fill=hex_color, width=1)
        overlay_canvas.create_rectangle(left, top, left + box_w, top + box_h, outline="white", width=2)
        overlay_canvas.create_text(cx, cy, text=text_str, fill="white", font=("Impact", 24))
        if progress < 1.0:
            visible_half = (box_w * progress) / 2
            mask_left = cx - visible_half - 2
            mask_right = cx + visible_half + 2
            if mask_left > 0: overlay_canvas.create_rectangle(0, 0, mask_left, H, fill="black", outline="")
            if mask_right < W: overlay_canvas.create_rectangle(mask_right, 0, W, H, fill="black", outline="")

    def update_ui_anim(target_progress, step=0.05):
        global ui_progress
        if overlay_win and overlay_win.winfo_viewable():
            try:
                hwnd_u = base.win.get_window_handle().get_int_handle()
                hwnd_o = int(overlay_win.frame(), 16)
                user32.SetWindowPos(hwnd_o, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                user32.SetWindowPos(hwnd_u, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                user32.SetWindowPos(hwnd_o, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
                overlay_win.lift()
                overlay_win.wm_attributes("-topmost", True)
            except: pass
        if target_progress > ui_progress:
            ui_progress += step
            if ui_progress >= target_progress: ui_progress = target_progress
        else:
            ui_progress -= step
            if ui_progress <= target_progress: ui_progress = target_progress
        draw_ui(ui_progress, is_goal_scored)
        if ui_progress == target_progress:
            if ui_progress == 0.0: overlay_win.withdraw()
            return
        root.after(16, lambda: update_ui_anim(target_progress, step))

    def show_goal_ui_animation():
        init_overlay()
        overlay_win.deiconify()
        overlay_win.lift()
        overlay_win.wm_attributes("-topmost", True)
        global ui_progress
        ui_progress = 0.0
        update_ui_anim(1.0, step=0.07)

    def hide_goal_ui_animation():
        update_ui_anim(0.0, step=0.07)

    def get_goal_side():
        return goal_side_val

    def get_presets():
        return presets_right if get_goal_side() == "right" else presets_left

    def get_goal_x():
        return 52.6701 if get_goal_side() == "right" else -52.6701

    def safe_write_bytes(address, data_bytes):
        if not pm or not pm.process_handle: return False
        try:
            f_process = pm.process_handle
            size = len(data_bytes)
            old_protect = ctypes.c_ulong(0)
            if kernel32.VirtualProtectEx(f_process, ctypes.c_void_p(address), ctypes.c_size_t(size), 0x40, ctypes.byref(old_protect)) == 0: return False
            bytes_written = ctypes.c_size_t(0)
            buffer = ctypes.create_string_buffer(data_bytes)
            success = kernel32.WriteProcessMemory(f_process, ctypes.c_void_p(address), buffer, ctypes.c_size_t(size), ctypes.byref(bytes_written))
            kernel32.VirtualProtectEx(f_process, ctypes.c_void_p(address), ctypes.c_size_t(size), old_protect, ctypes.byref(old_protect))
            return bool(success)
        except: return False

    def safe_write_float(address, float_val):
        return safe_write_bytes(address, struct.pack('f', float(float_val)))

    def safe_read_bytes(address, size):
        try:
            if address: return pm.read_bytes(address, size)
        except: pass
        return None

    def safe_read_float(address):
        try:
            if address: return pm.read_float(address)
        except: pass
        return None

    def safe_read_int(address):
        try:
            if address: return pm.read_int(address)
        except: pass
        return -1

    def allocate_near(process_handle, target_addr, size):
        for offset in range(0x00100000, 0x7FFF0000, 0x00100000):
            addr = VirtualAllocEx(process_handle, target_addr + offset, size, 0x1000 | 0x2000, 0x40)
            if addr: return addr
            if target_addr - offset > 0:
                addr = VirtualAllocEx(process_handle, target_addr - offset, size, 0x1000 | 0x2000, 0x40)
                if addr: return addr
        return None

    def health_check_and_restore():
        """Restore a crash-recovery snapshot, deleting the marker only when
        every memory write succeeds."""
        if not os.path.exists(BACKUP_FILE) or not pm or not base_address:
            return False
        all_ok = True
        try:
            with open(BACKUP_FILE, "r") as f:
                data = json.load(f)
            # بازیابی مقدار HUD از بکاپ ضدکرش (Crash Persistence) پیش از پردازش آفست‌ها
            if "hud" in data:
                try:
                    h_info = data.pop("hud")
                    _wpm(pm.process_handle, int(h_info["address"]), bytes((int(h_info["val"]),)))
                    flog("RECOVERY", "Restored HUD value from crash backup.")
                except Exception as e:
                    flog("RECOVERY", f"HUD crash-recovery failed: {e!r}")
            for offset_str, hex_str in data.items():
                try:
                    addr = base_address + int(offset_str)
                    b = bytes.fromhex(hex_str)
                    # [suite] v2.0.5 — never let a crash snapshot kill a
                    # LIVE hook owned by another suite member (momentum /
                    # bridge). An E9 at the ball site means someone owns
                    # it right now — skip the entry, keep the rest.
                    if int(offset_str) == 0x176A3A2:
                        try:
                            _cur = bytes(pm.read_bytes(addr, 1))
                            if _cur and _cur[0] == 0xE9:
                                flog("RECOVERY", "ball site skipped — a live "
                                     "hook belongs to another mod; not restoring")
                                continue
                        except Exception:
                            pass
                    if not safe_write_bytes(addr, b):
                        all_ok = False
                        flog("RECOVERY", f"write failed @ +0x{int(offset_str):X}")
                except Exception as e:
                    all_ok = False
                    flog("RECOVERY", f"restore +{offset_str} failed: {e!r}")
            if all_ok:
                os.remove(BACKUP_FILE)
                set_action_status("Recovered from previous crash!", "#2ecc71")
                flog("RECOVERY", "Previous-session backup fully restored")
                return True
        except Exception as e:
            flog("RECOVERY", f"backup recovery exception: {e!r}")
        return False

    def capture_original_state():
        global backup_data, backup_captured
        if backup_captured or not pm: return
        backup_data = {}
        try:
            b1 = safe_read_bytes(base_address + 0x217A379, 6)
            b2 = safe_read_bytes(base_address + 0x217A3EE, 6)
            b3 = safe_read_bytes(base_address + 0x217A293, 5)
            b4 = safe_read_bytes(base_address + ROTATION_MAX_OFFSET, 8)
            b5 = safe_read_bytes(base_address + ROTATION_MIN_OFFSET, 8)
            # Main replay/data hook is fixed at +0x176A3A2.  Do not depend on
            # hook_address being populated yet: the crash-recovery snapshot
            # must exist BEFORE the JMP is written.
            b_main = safe_read_bytes(base_address + 0x176A3A2, 7)
            
            backup_data["patches"] = {
                0x217A379: b1 if b1 != b'\x90'*6 else None,
                0x217A3EE: b2 if b2 != b'\x90'*6 else None,
                0x217A293: b3 if b3 != b'\x90'*5 else None,
                ROTATION_MAX_OFFSET: b4 if b4 != b'\x90'*8 else None,
                ROTATION_MIN_OFFSET: b5 if b5 != b'\x90'*8 else None
            }
            
            if b_main and b_main[0] != 0xE9:
                backup_data["patches"][0x176A3A2] = b_main
            
            backup_data["floats"] = {
                "base": safe_read_float(base_address + NEW_HEIGHT_STATIC_OFFSET),
                "lng": safe_read_float(get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x10])),
                "lat": safe_read_float(get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x18])),
                "hor_rot": safe_read_float(get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0xC])),
                "ver_rot": safe_read_float(get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0x8]))
            }
            if cam3_height_address:
                backup_data["floats"]["height"] = safe_read_float(cam3_height_address)

            out_json = {}
            for offset, b in backup_data["patches"].items():
                if b: out_json[str(offset)] = b.hex()
            # Crash Persistence: ذخیره آدرس و مقدار اصلی HUD در بکاپ ضدکرش
            if hud_address and hud_original_val is not None:
                out_json["hud"] = {"address": hud_address, "val": hud_original_val}
            os.makedirs(os.path.dirname(BACKUP_FILE), exist_ok=True)
            with open(BACKUP_FILE, "w") as f:
                json.dump(out_json, f)
                
            backup_captured = True
        except: pass

    def restore_original_state():
        global backup_captured, is_hooked
        set_taskbar_visible(True)

        try:
            cam4_lock_end()
        except Exception as e:
            flog("CLEANUP", f"CAM4 restore exception: {e!r}")

        if not pm or not base_address:
            # Keep BACKUP_FILE if the game process is already gone. The next
            # launch can use it for recovery if necessary.
            return

        base = base_address
        failures = []
        patch_backup = backup_data.get("patches", {}) if backup_captured else {}

        def restore_bytes(offset, data, label):
            if not data:
                return
            try:
                if not safe_write_bytes(base + offset, data):
                    failures.append(label + " write failed")
                else:
                    flog("CLEANUP", f"restored {label} @ +0x{offset:X}")
            except Exception as e:
                failures.append(f"{label}: {e!r}")

        # Restore the main hook independently, even if a previous operation
        # failed. The backup contains the exact original 7 bytes.
        # [suite] v2.0.5 — ONLY when the live hook (if any) points at OUR
        # cave. The site is shared (Momentum / ModBridge adopt it); if a
        # foreign hook owned it, restoring here would silently kill their
        # data feed and their charts would freeze/go empty.
        # [suite] v2.0.6 — ARCHITECTURE CHANGE: when the hook came from the
        # ModBridge broker, the site bytes are NEVER ours to restore — just
        # hand the reference back; the bridge restores them only when the
        # LAST consumer leaves (this is what keeps momentum/GLT/Referee
        # View sharing one live hook safely).
        global _ball_hook_via_bridge
        main_orig = patch_backup.get(0x176A3A2) or orig_bytes
        if _ball_hook_via_bridge:
            try:
                _bridge_hook_release(BALL_SITE_RVA)
                flog("CLEANUP", "ball hook RELEASED to the ModBridge broker "
                                "(site bytes untouched — the bridge owns them)")
            except Exception as e:
                flog("CLEANUP", f"broker release failed: {e!r}")
            _ball_hook_via_bridge = False
        elif main_orig and _glt_ball_site_is_ours(pm, hook_address, cave_address):
            restore_bytes(0x176A3A2, main_orig, "main hook")
        elif main_orig:
            flog("CLEANUP", "main hook left untouched — live E9 at the "
                 "ball site belongs to another mod (adopted/shared)")

        # Restore every other code patch independently.
        for offset, orig_b in patch_backup.items():
            if offset == 0x176A3A2:
                continue
            restore_bytes(offset, orig_b, f"patch +0x{offset:X}")

# ZOOM_INSTRUCTION_OFFSET is intentionally restored even if it was not
        # part of the backup set, because this program owns that modification.
        restore_bytes(ZOOM_INSTRUCTION_OFFSET, ZOOM_ORIG_BYTES, "zoom instruction")

        # Restore live camera floats captured before playback.
        floats = backup_data.get("floats", {}) if backup_captured else {}
        try:
            if floats.get("base") is not None: safe_write_float(base + NEW_HEIGHT_STATIC_OFFSET, floats["base"])
        except Exception as e: failures.append(f"base float: {e!r}")
        try:
            if cam3_height_address and floats.get("height") is not None: safe_write_float(cam3_height_address, floats["height"])
        except Exception as e: failures.append(f"height float: {e!r}")
        try:
            lng_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x10])
            if lng_addr and floats.get("lng") is not None: safe_write_float(lng_addr, floats["lng"])
        except Exception as e: failures.append(f"lng float: {e!r}")
        try:
            lat_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x18])
            if lat_addr and floats.get("lat") is not None: safe_write_float(lat_addr, floats["lat"])
        except Exception as e: failures.append(f"lat float: {e!r}")
        try:
            hor_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0xC])
            if hor_addr and floats.get("hor_rot") is not None: safe_write_float(hor_addr, floats["hor_rot"])
        except Exception as e: failures.append(f"hor rot float: {e!r}")
        try:
            ver_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0x8])
            if ver_addr and floats.get("ver_rot") is not None: safe_write_float(ver_addr, floats["ver_rot"])
        except Exception as e: failures.append(f"ver rot float: {e!r}")

        is_hooked = False
        if not failures:
            backup_captured = False

        if failures:
            flog("CLEANUP", "FAILURES: " + " | ".join(failures))
        else:
            flog("CLEANUP", "All FL_2026/PES2021 hooks restored to original state")

        if not failures and os.path.exists(BACKUP_FILE):
            try:
                os.remove(BACKUP_FILE)
            except Exception as e:
                flog("CLEANUP", f"backup-file removal failed: {e!r}")

        # بازگردانی امن مقدار اصلی HUD (پوشش خروج اضطراری و _shutdown_cleanup نیز)
        try:
            restore_hud()
        except Exception as e:
            flog("CLEANUP", f"HUD restore exception: {e!r}")

    _shutdown_cleanup_done = False

    def _shutdown_cleanup():
        global _shutdown_cleanup_done
        if _shutdown_cleanup_done:
            return
        try:
            restore_original_state()
        except Exception as e:
            flog("CLEANUP", f"shutdown cleanup exception: {e!r}")
        try:
            set_taskbar_visible(True)
        except: pass
        try:
            if pm:
                pm.close_process()
        except: pass
        _shutdown_cleanup_done = True

    atexit.register(_shutdown_cleanup)

    # --- Injection Logic ---
    def inject_code_hook():
        global hook_address, cave_address, data_address, state_static_address, is_hooked, orig_bytes
        global _ball_hook_via_bridge
        if is_hooked: return True
        try:
            module = pymem.process.module_from_name(pm.process_handle, config_data["process_name"])
            module_base = module.lpBaseOfDll
            hook_address = module_base + 0x176A3A2
            state_static_address = module_base + 0x372D148

            # [suite] v2.0.6 — ARCHITECTURE CHANGE (user request): the
            # bridge owns ALL hook bytes. REQUEST the shared feed from the
            # HookBroker instead of writing a cave ourselves; the bridge
            # either points us at the EXISTING hook's data buffer or
            # installs the hook once. This process never writes hook bytes
            # while the broker is reachable.
            _ball_hook_via_bridge = False
            if _bridge_broker_available():
                _buf = _bridge_hook_request(BALL_SITE_RVA,
                                            GLT_MOMENTUM_CAVE_SIG, 2)
                if _buf:
                    data_address = int(_buf)
                    cave_address = 0
                    is_hooked = True
                    _ball_hook_via_bridge = True
                    set_action_status("Hooks Deployed (shared via bridge)!", "#2ecc71")
                    flog("HOOK", f"ball hook via ModBridge broker — shared "
                                 f"data buffer 0x{data_address:X} (site bytes "
                                 f"owned by the bridge)")
                    return True
                flog("HOOK", f"broker request failed "
                             f"({_bridge_broker['err']}) — falling back to "
                             f"the legacy local hook")

            current_bytes = pm.read_bytes(hook_address, 7)
            if current_bytes[0] == 0xE9:
                relative_offset = struct.unpack('<i', current_bytes[1:5])[0]
                cave_address = relative_offset + hook_address + 5
                # [suite] the cave may belong to another suite member
                # (bridge / momentum). Resolve its data slot from the cave
                # code itself; fall back to the classic cave+64 layout.
                _resolved = _resolve_existing_cave_buffer(pm, cave_address)
                data_address = _resolved if _resolved is not None else cave_address + 64
                is_hooked = True
                flog("HOOK", f"adopted existing hook @ +0x176A3A2 "
                              f"(cave 0x{cave_address:X}, data 0x{data_address:X})")
                return True
            else:
                orig_bytes = current_bytes
                
            cave_address = allocate_near(pm.process_handle, hook_address, 128)
            if not cave_address: return False
            data_address = cave_address + 64
            
            cave_bytes = bytearray(orig_bytes)
            cave_bytes.append(0x53)
            cave_bytes.extend(b'\x48\xBB')
            cave_bytes.extend(struct.pack('<Q', data_address))
            cave_bytes.extend(b'\x0F\x11\x03')
            cave_bytes.append(0x5B)
            cave_bytes.extend(b'\xFF\x25\x00\x00\x00\x00')
            cave_bytes.extend(struct.pack('<Q', hook_address + 7))
            
            pm.write_bytes(cave_address, bytes(cave_bytes), len(cave_bytes))
            
            relative_offset = cave_address - (hook_address + 5)
            hook_bytes = bytearray()
            hook_bytes.append(0xE9)
            hook_bytes.extend(struct.pack('<i', relative_offset))
            hook_bytes.extend(b'\x90\x90')
            pm.write_bytes(hook_address, bytes(hook_bytes), 7)
            
            is_hooked = True
            set_action_status("Hooks Deployed Successfully!", "#2ecc71")
            return True
        except Exception as e:
            flog("HOOK", f"Error: {e}")
            set_action_status("Hook Injection Failed!", "#e74c3c")
            return False

    # ------------------------------------------------------------------
    # سیستم مخفی‌سازی HUD (AOB Scan پس‌زمینه):
    # اسکن یک‌باره الگوی بایتی HUD در یک ترد مجزا بلافاصله پس از اتصال؛
    # آدرس کش می‌شود، هنگام قفل دوربین 0x00 نوشته شده و در بازگردانی/خروج
    # اضطراری مقدار اصلی ترمیم می‌شود. بکاپ ضدکرش در mem_backup.json.
    # ------------------------------------------------------------------
    class _MBI64(ctypes.Structure):
        _fields_ = [
            ("BaseAddress", ctypes.c_uint64),
            ("AllocationBase", ctypes.c_uint64),
            ("AllocationProtect", ctypes.c_ulong),
            ("__alignment1", ctypes.c_ulong),
            ("RegionSize", ctypes.c_size_t),
            ("State", ctypes.c_ulong),
            ("Protect", ctypes.c_ulong),
            ("Type", ctypes.c_ulong),
            ("__alignment2", ctypes.c_ulong)
        ]

    def scan_hud_pattern_async():
        global hud_address, hud_scan_done
        # الگوی دقیق 30 بایتی بعد از بایت اول (هدف) برای نسخه 2021 / FL 2026
        pattern = b'\x00\x78\x00\x00\x00\x00\x00\x00\x00\x41\x46\x47\x00\x42\x48\x52\x00\x42\x47\x44\x00\x42\x54\x4E\x00\x42\x52\x4E\x00\x4B\x48'
        mbi = _MBI64()
        mbi_size = ctypes.sizeof(mbi)
        VirtualQueryEx = k32.VirtualQueryEx
        VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
        VirtualQueryEx.restype = ctypes.c_size_t

        flog("HUD", "Starting 64-bit Full RAM AOB scanner for PES 2021...")

        # تا زمان پیدا شدن آدرس در حین بازی، اسکن در پس‌زمینه تکرار می‌شود
        while _tk_alive and not hud_address:
            if not pm or not pm.process_handle:
                time.sleep(1)
                continue

            curr_addr = 0x00010000
            max_addr = 0x00007FFFFFFF0000  # فضای آدرس‌دهی 64 بیتی برنامه در ویندوز

            try:
                while curr_addr < max_addr and not hud_address:
                    if VirtualQueryEx(pm.process_handle, ctypes.c_void_p(curr_addr), ctypes.byref(mbi), mbi_size) == 0:
                        break

                    # فقط بلاک‌های تخصیص‌یافته (MEM_COMMIT = 0x1000) و قابل‌خواندن
                    is_committed = (mbi.State == 0x1000)
                    is_readable = not (mbi.Protect & 0x101)  # حذف PAGE_NOACCESS و PAGE_GUARD

                    if is_committed and is_readable and mbi.RegionSize > 0:
                        # محدود کردن سقف خواندن به 16 مگابایت در هر صفحه جهت مصرف بهینه رم
                        read_size = min(mbi.RegionSize, 16 * 1024 * 1024)
                        try:
                            page_bytes = _rpm(pm.process_handle, curr_addr, read_size)
                            idx = page_bytes.find(pattern)
                            if idx != -1:
                                matched_addr = curr_addr + idx
                                hud_address = matched_addr - 1  # بایت اول هدایت به مقدار اصلی HUD
                                hud_scan_done = True
                                flog("HUD", f"PES 2021 HUD byte found in RAM at: 0x{hud_address:X}")
                                return
                        except Exception:
                            pass

                    curr_addr += mbi.RegionSize
            except Exception as e:
                flog("HUD", f"RAM scan loop error: {repr(e)}")

            if not hud_address:
                time.sleep(2)

    def hide_hud():
        global hud_original_val
        if not hud_address or not pm: return False
        try:
            curr_val = _rpm(pm.process_handle, hud_address, 1)[0]
            if hud_original_val is None:
                hud_original_val = curr_val
                flog("HUD", f"Original HUD value captured: 0x{curr_val:02X}")
            if curr_val != 0x00:
                _wpm(pm.process_handle, hud_address, bytes((0x00,)))
                flog("HUD", "HUD hidden successfully (wrote 0x00)")
            return True
        except Exception as e:
            flog("HUD", f"hide_hud exception: {repr(e)}")
            return False

    def restore_hud():
        global hud_original_val
        if not hud_address or not pm or hud_original_val is None: return False
        try:
            _wpm(pm.process_handle, hud_address, bytes((hud_original_val,)))
            flog("HUD", f"HUD restored to original: 0x{hud_original_val:02X}")
            hud_original_val = None
            return True
        except Exception as e:
            flog("HUD", f"restore_hud exception: {repr(e)}")
            return False

    def connect_to_game():
        # متغیر aux_state_address به خط زیر اضافه شد
        global pm, base_address, cam3_height_address, state_static_address, aux_state_address, connection_time
        try:
            pm = pymem.Pymem(config_data["process_name"])
            module = pymem.process.module_from_name(pm.process_handle, config_data["process_name"])
            base_address = module.lpBaseOfDll
            state_static_address = base_address + 0x372D148
            aux_state_address = base_address + 0x36F33D8
            if not cam3_height_address:
                try:
                    pattern_location = pymem.pattern.pattern_scan_module(pm.process_handle, module, CAM3_HEIGHT_PATTERN)
                    if pattern_location: cam3_height_address = pattern_location + 12
                except: pass
            connection_time = time.time()
            # One-Time Background Scan: شروع اسکن AOB صفحه HUD در ترد مجزا
            threading.Thread(target=scan_hud_pattern_async, daemon=True).start()
            return True
        except: return False

    def unlock_all_silent():
        if not connect_to_game(): return False
        capture_original_state() 
        try:
            for offset, nop_bytes in PATCHES.items():
                safe_write_bytes(base_address + offset, nop_bytes)
            safe_write_bytes(base_address + ROTATION_MAX_OFFSET, NOP_8)
            safe_write_bytes(base_address + ROTATION_MIN_OFFSET, NOP_8)
            return True
        except: return False

    def get_ptr_addr(offsets):
        if not pm or not base_address: return None
        try:
            addr = pm.read_longlong(base_address + offsets[0])
            for offset in offsets[1:-1]: addr = pm.read_longlong(addr + offset)
            return addr + offsets[-1]
        except: return None

    def write_memory_pure(base_val, h, lng, lat, h_rot, v_rot, zoom_val=None, lock_cam4=False):
        if not pm or not base_address: return False
        try:
            safe_write_float(base_address + NEW_HEIGHT_STATIC_OFFSET, base_val)
            if cam3_height_address: safe_write_float(cam3_height_address, h)
            lng_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x10])
            if lng_addr: safe_write_float(lng_addr, lng)
            lat_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x8, 0x18])
            if lat_addr: safe_write_float(lat_addr, lat)
            hor_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0xC])
            if hor_addr: safe_write_float(hor_addr, h_rot)
            ver_addr = get_ptr_addr([0x037F4A08, 0x8, 0x10, 0x0, 0x8])
            if ver_addr: safe_write_float(ver_addr, v_rot)
            
            # تزریق مستقیم مقدار زوم (عدد اعشاری) به آفست مد نظر
            if zoom_val is not None:
                safe_write_float(base_address + ZOOM_INSTRUCTION_OFFSET, zoom_val)
            return True
        except Exception as e:
            flog("MEM", f"write_memory_pure error: {repr(e)}")
            return False

    # ------------------------------------------------------------------
    # قفل دوربین چهارم (کد 03): مود GLT فقط باید روی دوربین چهارم اجرا شود
    # پوینتر ۱ بایتی انتخاب دوربین: 00=دوربین اول ... 03=دوربین ما (چهارم)
    # ------------------------------------------------------------------
    # Cheat Engine equivalent pointer chain for FL_2026 / PES2021.
    # FL_2026.exe + 037F0AC8 -> QWORD
    # +18 -> QWORD -> +140 -> QWORD -> +418 -> QWORD -> +48 -> QWORD
    # +5FC -> final BYTE address
    CAM4_BASE_OFFSET = 0x037F0AC8
    CAM4_OFFSETS = (0x18, 0x140, 0x418, 0x48)
    CAM4_FINAL_OFFSET = 0x5FC
    CAM4_LOCK_VAL = 0x03
    CAM4_SETTLE_DELAY_MS = 80
    cam4_lock_flag = False
    cam4_saved_value = None
    cam4_saved_address = None
    cam4_thread_started = False
    cam4_mutex = threading.Lock()

    # متغیرهای سیستم مخفی‌سازی HUD
    hud_address = None
    hud_original_val = None
    hud_scan_done = False

    def cam4_read_u64(address):
        try:
            return pm.read_longlong(address)
        except:
            return 0

    def cam4_read_byte(address):
        try:
            return pm.read_bytes(address, 1)[0]
        except:
            return 0xFF

    def cam4_write_byte(address, value):
        try:
            pm.write_bytes(address, bytes((value & 0xFF,)), 1)
        except:
            pass

    def cam4_addr():
        # پیمایش دقیق زنجیره پوینتر 64 بیتی دقیقاً مثل استایل نسخه 2017
        if not pm or not base_address:
            return None
        try:
            curr = pm.read_longlong(base_address + CAM4_BASE_OFFSET)
            if not curr:
                return None
            for off in CAM4_OFFSETS:
                curr = pm.read_longlong(curr + off)
                if not curr:
                    return None
            target = curr + CAM4_FINAL_OFFSET
            return target
        except Exception as e:
            flog('CAM4', f'CE chain FAILED: {repr(e)}')
            return None

    def cam4_lock_start():
        global cam4_lock_flag, cam4_saved_value, cam4_saved_address, cam4_thread_started
        a = cam4_addr()
        if a is None:
            flog('CAM4', 'LOCK FAIL: CE pointer chain unresolved')
            return False
        try:
            with cam4_mutex:
                curr_b = cam4_read_byte(a)
                if curr_b == 0xFF:
                    return False
                
                # رفع کرش: اگر مقدار None بود ذخیره کن حتی اگر 03 باشد (مقدار پیش‌فرض 00 در نظر گرفته شود)
                if cam4_saved_value is None:
                    cam4_saved_address = a
                    cam4_saved_value = curr_b if curr_b != CAM4_LOCK_VAL else 0x00
                    flog('CAM4', f'CAPTURE {cam4_saved_value:02X} @ {a:X}')

                cam4_write_byte(a, CAM4_LOCK_VAL)

            # حلقه پایدارسازی خواندن
            rb = None
            for _ in range(10):
                time.sleep(0.01)
                rb = cam4_read_byte(a)
                if rb == CAM4_LOCK_VAL:
                    break

            if rb != CAM4_LOCK_VAL:
                flog('CAM4', f'LOCK FAIL: readback={rb:02X} @ {a:X}')
                return False

            cam4_lock_flag = True
            if not cam4_thread_started:
                cam4_thread_started = True
                threading.Thread(target=cam4_enforce_loop, daemon=True).start()
            
            orig_str = f"{cam4_saved_value:02X}" if cam4_saved_value is not None else "00"
            flog('CAM4', f'LOCK OK: 03 @ {a:X}; original={orig_str}')
            hide_hud()
            return True
        except Exception as e:
            flog('CAM4', f'LOCK EXCEPTION @ {a:X}: {repr(e)}')
            return False

    def cam4_enforce_loop():
        # رفع باگ قفل مداوم Mutex: شرط بیرون از lock قرار گرفت دقیقاً مانند 2017
        while True:
            if cam4_lock_flag:
                try:
                    with cam4_mutex:
                        if cam4_lock_flag:
                            a = cam4_addr()
                            if a is not None and cam4_read_byte(a) != CAM4_LOCK_VAL:
                                cam4_write_byte(a, CAM4_LOCK_VAL)
                except Exception:
                    pass
            time.sleep(0.001)

    def cam4_lock_end():
        global cam4_lock_flag, cam4_saved_value, cam4_saved_address
        cam4_lock_flag = False
        try:
            with cam4_mutex:
                a = cam4_addr()
                if a is not None and cam4_saved_value is not None:
                    original = cam4_saved_value
                    cam4_write_byte(a, original)
                    rb = cam4_read_byte(a)
                    flog('CAM4', f'RESTORE: {original:02X} @ {a:X}; readback={rb:02X}')
                elif cam4_saved_value is not None:
                    flog('CAM4', f'RESTORE FAIL: chain unresolved; original={cam4_saved_value:02X}')
        except Exception as e:
            flog('CAM4', f'RESTORE EXCEPTION: {repr(e)}')
        cam4_saved_value = None
        cam4_saved_address = None
        
    def verify_cam4_hard_barrier():
        a = cam4_addr()
        if a is None:
            return False
        return cam4_read_byte(a) == CAM4_LOCK_VAL

    def apply_preset(num, lock_cam4=False):
        # Camera 4 selection is controlled separately; do not lock it here.
        p = get_presets()[num]
        if not unlock_all_silent():
            return False
        return write_memory_pure(p["base"], p["height"], p["long"], p["lat"], p["hor_rot"], p["vert_rot"], p.get("zoom"))

    def start_custom_anim(state_name, duration, callback=None):
        global pending_animation
        pending_animation = (state_name, duration, callback)

    def _do_start_custom_anim(state_name, duration, callback):
        global is_animating_camera, anim_state, anim_start_time, anim_duration, anim_callback
        anim_state = state_name
        anim_start_time = time.time()
        anim_duration = duration
        anim_callback = callback
        is_animating_camera = True
        
        if state_name == "fade_in":
            global goal_ui_fired
            goal_ui_fired = False   # برای هر پخش جدید، تریگر ۹۰٪ ریست می‌شود
            camera.position = f1_pos
            camera.rotation = f1_rot
            for post_ent in [post_l, post_r, bar] + net_parts:
                post_ent.enabled = True
                post_ent.color = color.rgba(1, 1, 1, 0.0)
        elif state_name == "pre_align":
            # دوربین در f1_pos با f1_rot است؛ شروع چرخش نرم به سمت توپ
            camera.position = f1_pos
            camera.rotation = f1_rot
            # تیرک‌ها و تور در طول چرخش سر دوربین نمایان می‌مانند (بدون خاموشی ناگهانی)
            for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = True
        elif state_name == "move_forward":
            for post_ent in [post_l, post_r, bar] + net_parts: 
                post_ent.enabled = True
                post_ent.color = color.white
        elif state_name == "post_unalign":
            # دوربین در f1_pos است و از زاویه‌ی واقعی پایان move_backward به f1_rot برمی‌گردد
            camera.position = f1_pos
            # تیرک‌ها و تور در طول چرخش برگشت سر دوربین نمایان می‌مانند
            for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = True
        elif state_name == "fade_out":
            camera.position = f1_pos
            camera.rotation = f1_rot
            for post_ent in [post_l, post_r, bar] + net_parts:
                post_ent.enabled = True
                post_ent.color = color.rgba(1, 1, 1, 1.0)

    def focus_and_click_game():
        hwnd = get_game_hwnd()
        if hwnd:
            user32.ShowWindow(hwnd, 9)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            cx, cy = (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
            user32.SetCursorPos(cx, cy)
            time.sleep(0.1)
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.4)

    def press_key(vk, scan):
        if scan is None or vk is None or vk == 0: return
        flags = 0x0008 | (0x0001 if 37 <= vk <= 40 else 0)
        ii_ = INPUT_UNION()
        ii_.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        x = INPUT(1, ii_)
        user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

    def release_key(vk, scan):
        if scan is None or vk is None or vk == 0: return
        flags = 0x0008 | 0x0002 | (0x0001 if 37 <= vk <= 40 else 0)
        ii_ = INPUT_UNION()
        ii_.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        x = INPUT(1, ii_)
        user32.SendInput(1, ctypes.byref(x), ctypes.sizeof(x))

    def calc_dist(p1, p2):
        return math.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2 + (p1[2]-p2[2])**2)

    def is_valid_glt_frame(frame):
        x, h, y = frame[0], frame[1], frame[2]
        return ((51.0 <= x <= 57.0) or (-57.0 <= x <= -51.0)) and (-4.5 <= y <= 4.5) and (-1.0 <= h <= 3.5)

    def analyze_trajectory():
        global is_goal_scored, freeze_frame, freeze_idx, goal_side_val, current_glt_scenario
        if not recorded_frames:
            freeze_idx = -1; freeze_frame = None; return
        valid_indices = [i for i, f in enumerate(recorded_frames) if is_valid_glt_frame(f)]
        if not valid_indices:
            freeze_idx = -1; freeze_frame = None; return
            
        last_valid_frame = recorded_frames[valid_indices[-1]]
        if last_valid_frame[0] > 0: goal_side_val = "right"
        else: goal_side_val = "left"
        
        side = get_goal_side()
        goal_x = get_goal_x()
        is_goal_scored = False
        valid_frames = [(recorded_frames[i], i) for i in valid_indices]
        
        if side == "right":
            goal_frames = [(f, idx) for (f, idx) in valid_frames if f[0] >= 52.6701 and -3.66 <= f[2] <= 3.66 and 0.0 <= f[1] <= 2.44]
            if goal_frames:
                is_goal_scored = True
                max_x = max(f[0] for (f, idx) in valid_frames)
                if 52.6701 <= max_x <= 54.0:
                    current_glt_scenario = 1
                    freeze_idx = max(valid_indices, key=lambda i: recorded_frames[i][0])
                    fx, fh, fy = recorded_frames[freeze_idx]
                    freeze_frame = (fx, fh, fy)
                else:
                    current_glt_scenario = 2
                    first_goal_frame, first_idx = goal_frames[0]
                    freeze_idx = first_idx
                    fx, fh, fy = first_goal_frame
                    freeze_frame = (goal_x, fh, fy)
            else:
                current_glt_scenario = 3
                turning_points_x = []
                for i in range(len(valid_indices)):
                    idx = valid_indices[i]
                    if idx > 0 and idx < len(recorded_frames) - 1:
                        if recorded_frames[idx][0] > recorded_frames[idx-1][0] and recorded_frames[idx][0] >= recorded_frames[idx+1][0]:
                            h, y = recorded_frames[idx][1], recorded_frames[idx][2]
                            if not ((abs(h - 2.44) < 0.15 and abs(y) <= 3.7) or (abs(y - 3.66) < 0.15 and h <= 2.5) or (abs(y - (-3.66)) < 0.15 and h <= 2.5)):
                                turning_points_x.append(idx)
                if turning_points_x: freeze_idx = max(turning_points_x, key=lambda idx: recorded_frames[idx][0])
                else: freeze_idx = max(valid_indices, key=lambda idx: recorded_frames[idx][0])
                fx, fh, fy = recorded_frames[freeze_idx]
                freeze_frame = (fx, fh, fy)
        else:
            goal_frames = [(f, idx) for (f, idx) in valid_frames if f[0] <= -52.6701 and -3.66 <= f[2] <= 3.66 and 0.0 <= f[1] <= 2.44]
            if goal_frames:
                is_goal_scored = True
                min_x = min(f[0] for (f, idx) in valid_frames)
                if -54.0 <= min_x <= -52.6701:
                    current_glt_scenario = 1
                    freeze_idx = min(valid_indices, key=lambda i: recorded_frames[i][0])
                    fx, fh, fy = recorded_frames[freeze_idx]
                    freeze_frame = (fx, fh, fy)
                else:
                    current_glt_scenario = 2
                    first_goal_frame, first_idx = goal_frames[0]
                    freeze_idx = first_idx
                    fx, fh, fy = first_goal_frame
                    freeze_frame = (goal_x, fh, fy)
            else:
                current_glt_scenario = 3
                turning_points_x = []
                for i in range(len(valid_indices)):
                    idx = valid_indices[i]
                    if idx > 0 and idx < len(recorded_frames) - 1:
                        if recorded_frames[idx][0] < recorded_frames[idx-1][0] and recorded_frames[idx][0] <= recorded_frames[idx+1][0]:
                            h, y = recorded_frames[idx][1], recorded_frames[idx][2]
                            if not ((abs(h - 2.44) < 0.15 and abs(y) <= 3.7) or (abs(y - 3.66) < 0.15 and h <= 2.5) or (abs(y - (-3.66)) < 0.15 and h <= 2.5)):
                                turning_points_x.append(idx)
                if turning_points_x: freeze_idx = min(turning_points_x, key=lambda idx: recorded_frames[idx][0])
                else: freeze_idx = min(valid_indices, key=lambda idx: recorded_frames[idx][0])
                fx, fh, fy = recorded_frames[freeze_idx]
                freeze_frame = (fx, fh, fy)
                
        if freeze_idx >= len(recorded_frames): freeze_idx = len(recorded_frames) - 1

    def execute_animation():
        global f1_pos, f1_rot, f2_pos, f2_rot_start, f2_rot_end, target_yaw_anim
        global f1_look_rot, f1_look_rot_actual, f2_pos_end
        if not freeze_frame: return

        freeze_gx, freeze_gh, freeze_gy = freeze_frame
        side = get_goal_side()
        
        update_stripe_colors()
        update_env_mirror()
        if side == "right":
            f1_pos = Vec3(-80.00, 40.00, 0)
            f1_rot = Vec3(25.90, 93.70, 0)
            camera.fov = 20.50
            target_yaw_anim = -90.0
            ball.z = freeze_gx - 52.50
            ball.x = freeze_gy
        else:
            f1_pos = Vec3(80.00, 40.00, 0)
            f1_rot = Vec3(25.90, 266.32, 0)
            camera.fov = 20.50
            target_yaw_anim = 90.0
            ball.z = -52.50 - freeze_gx
            ball.x = -freeze_gy
            
        ball.y = freeze_gh
        ball_shadow.x = ball.x
        ball_shadow.z = ball.z
        
        # محل قرارگیری دوربین بالای توپ
        cam_glt_y = ball.y + 5.3
        cam_glt_z = ball.z - 0.11
        
        f2_pos = Vec3(ball.x, cam_glt_y, cam_glt_z)
        # چون فقط چرخش داریم، نقطه پایان جابجایی برابر با همان نقطه است
        f2_pos_end = Vec3(ball.x, cam_glt_y, cam_glt_z)
        
        # محاسبه‌ی زاویه‌ی look_at از f1_pos به توپ برای pre_align (بدون پرش)
        camera.position = f1_pos
        camera.look_at(Vec3(ball.x, ball.y, ball.z))
        f1_look_rot = Vec3(camera.rotation[0], camera.rotation[1], camera.rotation[2])
        camera.rotation = f1_rot  # بازگشت به زاویه‌ی کالیبره‌شده
        
        # مقادیر placeholder؛ زاویه‌ی واقعی در پایان move_forward با مثلثات محاسبه می‌شود
        f2_rot_start = Vec3(0, 0, 0)
        f2_rot_end = Vec3(0, 0, 0)
        
        get_presets()[2]["lat"] = freeze_gy
        if apply_preset(1) is False:
            return
        try:
            hwnd = base.win.get_window_handle().get_int_handle()
            user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, screen_width, screen_height - 1, 0)
            user32.SetForegroundWindow(hwnd)
            user32.SetCursorPos(2, screen_height - 3)   # ماوس به گوشه‌ی پایین چپ منتقل می‌شود
        except: pass
        
        # ترتیب انیمیشن: ظاهر شدن → تراز کردن توپ (pre_align) → حرکت (2.5s) → چرخش+جابجایی (1s)
        root.after(400, lambda: start_custom_anim("fade_in", 1.0, 
            lambda: start_custom_anim("pre_align", 1.0,
            lambda: start_custom_anim("move_forward", 2.5, 
            lambda: start_custom_anim("hold_top", 1.0, seq_anim_1_done)))))

    def seq_anim_1_done():
        # شروع/پنهان‌سازی GOAL/NO GOAL به تیک ۹۰٪ move_forward منتقل شد (+۴۴۵۰ms = دقیقاً زمان پایان قبلی)
        
        # ترتیب برگشت: توقف (3s) → چرخش+جابجایی برگشت (1s) → حرکت برگشت (2.5s) → unalign (0.4s) → محو شدن
        root.after(3000, lambda: start_custom_anim("hold_top", 1.0, 
            lambda: start_custom_anim("move_backward", 2.5, 
            lambda: start_custom_anim("post_unalign", 1.0,
            lambda: start_custom_anim("fade_out", 1.0, seq_anim_2_done)))))

    def seq_anim_2_done():
        # پایان انیمیشن اورسینا: هنوز قفل 03 نباید آزاد شود.
        # بازی اکنون به مرحله ادامه Replay برمی‌گردد و قفل تا ریست نهایی نگه داشته می‌شود.
        root.after(400, seq_resume_playback)

    def seq_resume_playback():
        global playback_state, unchanged_count, last_live_coords
        playback_state = "POST_PLAYBACK"
        unchanged_count = 0
        last_live_coords = None
        focus_game_only()
        
        vk_action = get_vk(get_profile_keys()["key_action"])
        scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
        press_key(vk_action, scan_action)
        
        playback_routine()

    FREEZE_SPHERE_RADIUS = 6.0    # شعاع کره‌ی اطراف محل فریم فریز برای ورود به اسلوموشن (متر)
    FREEZE_CIRCLE_RADIUS = 1.5    # شعاع کره‌ی اطراف محل فریم فریز برای ورود به تپینگ (متر) - مخصوص نسخه 2021
    SLOWDOWN_EXIT_MARGIN = 0.5    # هیسترزیس خروج از اسلوموشن؛ اگر توپ از کره خارج شد، برگشت به سرعت عادی (متر)
    SPEED_ARM_LIMIT = 1.0         # حداکثر جابجایی طبیعی توپ در هر تیک (متر)؛ بیشتر از این یعنی پرش/جاروبِ ریوایند
    SPEED_ARM_TICKS = 4           # تعداد تیک متوالی با جابجایی طبیعی لازم برای فعال شدن تریگرهای کره‌ی فریز

    _log_tick_counter = 0

    def playback_routine():
        global playback_state, unchanged_count, last_live_coords, tap_min_diff, tap_target_coords, back_best_diff, back_taps
        global speed_ok_count, _log_tick_counter
        if playback_state == "IDLE": return
        if not freeze_frame:
            playback_state = "IDLE"
            return

        live = get_live_coords()
        if not live:
            root.after(16, playback_routine)
            return

        vk_action = get_vk(get_profile_keys()["key_action"])
        scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
        vk_back = get_vk(get_profile_keys()["key_back"])
        scan_back = user32.MapVirtualKeyW(vk_back, 0) if vk_back else 0

        tick_move = calc_dist(live, last_live_coords) if last_live_coords else 0.0
        if last_live_coords and tick_move < 0.0001:
            unchanged_count += 1
        else:
            unchanged_count = 0
        last_live_coords = live

        if tick_move < SPEED_ARM_LIMIT:
            speed_ok_count += 1
        else:
            speed_ok_count = 0
        armed = speed_ok_count >= SPEED_ARM_TICKS

        dist_freeze = calc_dist(live, freeze_frame)

        # ثبت وضعیت توپ هر ۵۰ فریم در لاگ جهت اطمینان از پیشرفت
        _log_tick_counter += 1
        if _log_tick_counter % 50 == 0:
            flog("TRACK", f"State: {playback_state} | Dist: {dist_freeze:.2f}m | Ball: ({live[0]:.2f}, {live[1]:.2f}, {live[2]:.2f})")

        if playback_state == "WAITING_FOR_REWIND":
            set_action_status("Waiting for replay to rewind...", "#3498db")
            playback_state = "NORMAL_SPEED"
            root.after(16, playback_routine)
            return

        if playback_state == "POST_PLAYBACK":
            if unchanged_count > 250:
                playback_state = "IDLE"
                release_key(vk_action, scan_action)
                restore_original_state()
                update_main_button_text("done")
            else:
                root.after(16, playback_routine)
            return

        max_unchanged = 600 if playback_state in ("INIT", "NORMAL_SPEED") else 250

        if unchanged_count > max_unchanged:
            flog("GLT", f"Emergency stop: Ball stuck for {max_unchanged} frames.")
            playback_state = "IDLE"
            release_key(vk_action, scan_action)
            restore_original_state()
            update_main_button_text("idle")
            return

        if playback_state == "NORMAL_SPEED":
            set_action_status("Playing (Normal Speed)...", "#e67e22")
            if armed and dist_freeze <= FREEZE_SPHERE_RADIUS:
                playback_state = "SLOW_DOWN"
                press_key(vk_action, scan_action)
                flog("GLT", f"Slow-motion zone entered (dist={dist_freeze:.2f}m)")
            root.after(16, playback_routine)

        elif playback_state == "SLOW_DOWN":
            set_action_status("Playing (Slow Motion)...", "#f1c40f")
            if dist_freeze <= FREEZE_CIRCLE_RADIUS:
                release_key(vk_action, scan_action)
                tap_min_diff = float('inf')
                tap_target_coords = None
                back_best_diff = float('inf')
                back_taps = 0
                playback_state = "TAP"
                flog("GLT", f"Tapping zone entered (dist={dist_freeze:.2f}m)")
                root.after(100, playback_routine)
            elif dist_freeze > FREEZE_SPHERE_RADIUS + SLOWDOWN_EXIT_MARGIN:
                release_key(vk_action, scan_action)
                playback_state = "NORMAL_SPEED"
                root.after(16, playback_routine)
            else:
                root.after(16, playback_routine)

        elif playback_state == "TAP":
            set_action_status("Tapping (Finding point)...", "#8e44ad")
            diff_x = abs(live[0] - freeze_frame[0])
            diff_h = abs(live[1] - freeze_frame[1])
            diff_y = abs(live[2] - freeze_frame[2])
            worst_axis_diff = max(diff_x, diff_h, diff_y)

            if worst_axis_diff > tap_min_diff:
                playback_state = "STEP_BACK"
                back_best_diff = worst_axis_diff
                back_taps = 1  # تپ اول همینجا ثبت می‌شود
                last_live_coords = None
                unchanged_count = 0
                press_key(vk_back, scan_back)
                root.after(15, lambda: release_key(vk_back, scan_back))
                flog("GLT", f"Overshoot -> step-back tap 1 executed")
                root.after(80, playback_routine)
                return
            elif unchanged_count > 8:
                playback_state = "IDLE"
                flog("GLT", f"Freeze point locked! Starting execute_animation...")
                root.after(150, execute_animation)
                return
            else:
                tap_min_diff = worst_axis_diff
                tap_target_coords = tuple(live)

            press_key(vk_action, scan_action)
            root.after(15, lambda: release_key(vk_action, scan_action))
            root.after(80, playback_routine)

        elif playback_state == "STEP_BACK":
            set_action_status("Stepping back to exact frame...", "#8e44ad")
            _tgt = tap_target_coords if tap_target_coords else freeze_frame
            diff_x = abs(live[0] - _tgt[0])
            diff_h = abs(live[1] - _tgt[1])
            diff_y = abs(live[2] - _tgt[2])
            worst_axis_diff = max(diff_x, diff_h, diff_y)

            # اگر با تپ اول به هدف رسیدیم یا قبلاً ۲ تپ انجام شده، انیمیشن اجرا شود
            if worst_axis_diff <= 0.005 or back_taps >= 2 or unchanged_count > 8:
                playback_state = "IDLE"
                flog("GLT", f"Step-back finished at tap {back_taps}! Starting execute_animation...")
                root.after(150, execute_animation)
                return

            # در غیر این صورت تپ دوم (نهایی) زده می‌شود
            back_taps += 1
            press_key(vk_back, scan_back)
            root.after(15, lambda: release_key(vk_back, scan_back))
            root.after(80, playback_routine)

        elif playback_state == "STEP_BACK":
            set_action_status("Stepping back to exact frame...", "#8e44ad")
            _tgt = tap_target_coords if tap_target_coords else freeze_frame
            diff_x = abs(live[0] - _tgt[0])
            diff_h = abs(live[1] - _tgt[1])
            diff_y = abs(live[2] - _tgt[2])
            worst_axis_diff = max(diff_x, diff_h, diff_y)
            back_taps += 1

            if worst_axis_diff <= 0.005 or back_taps >= 40 or unchanged_count > 8:
                playback_state = "IDLE"
                flog("GLT", f"Step-back finished! Starting execute_animation...")
                root.after(150, execute_animation)
                return

            press_key(vk_back, scan_back)
            root.after(15, lambda: release_key(vk_back, scan_back))
            root.after(80, playback_routine)
            
    def get_live_coords():
        try:
            if pm and data_address:
                data = pm.read_bytes(data_address, 12)
                x, h, y = struct.unpack('<fff', data)
                return (x, h, y)
        except: pass
        return None

    def fetch_memory_step():
        global pm, current_state_str, candidate_state_str, state_stable_count, last_state_str, connection_time, is_hooked

        if not _tk_alive: return
        try:
            if not pm:
                if connect_to_game():
                    lbl_conn_status.config(text=f"CONNECTED: {config_data['process_name']}", fg="#2ecc71")
                    set_action_status("Attached to process. Verifying memory...", "#2ecc71")
                    health_check_and_restore()
                else:
                    lbl_conn_status.config(text="DISCONNECTED", fg="#e74c3c")
                return

            if not is_hooked:
                if time.time() - connection_time >= 2.0:
                    set_action_status("Deploying Memory Hooks...", "#3498db")
                    inject_code_hook()
                return
            
            raw_state_str = "STOP"
            if state_static_address:
                # خواندن وضعیت پیش‌فرض
                status = safe_read_int(state_static_address)
                
                # خواندن وضعیت از طریق پوینتر کمکی
                aux_val = -1
                aux_addr = get_ptr_addr([0x037F4820, 0xA20])
                if aux_addr:
                    aux_val = safe_read_int(aux_addr)

                # بررسی شروط (اگر استاتوس 131 بود یا مقدار پوینتر کمکی 18 بود)
                if status == 131 or aux_val == 15: 
                    raw_state_str = "REPLAY"
                elif status == 128: 
                    raw_state_str = "PLAYING"
                elif status == 138: 
                    raw_state_str = "CUTSCENE"
                else: 
                    raw_state_str = "STOP"
                
            if raw_state_str != current_state_str:
                if raw_state_str == candidate_state_str:
                    state_stable_count += 1
                else:
                    candidate_state_str = raw_state_str
                    state_stable_count = 1
                
                if state_stable_count >= 15:
                    current_state_str = candidate_state_str
                    state_stable_count = 0
            else:
                state_stable_count = 0

            state_display = "Stop"
            if current_state_str == "PLAYING": state_display = "Playing"
            elif current_state_str == "REPLAY": state_display = "Replay Mode"
            elif current_state_str == "CUTSCENE": state_display = "Cutscene"
            lbl_game_state_val.config(text=state_display)
            
            if current_state_str == "REPLAY":
                live = get_live_coords()
                if live:
                    lbl_val_x.config(text=f"{live[0]:+.4f}")
                    lbl_val_y.config(text=f"{live[2]:+.4f}")
                    lbl_val_z.config(text=f"{live[1]:+.4f}")

            if last_state_str == "REPLAY" and current_state_str != "REPLAY":
                if playback_state in ("IDLE", "POST_PLAYBACK") and manual_record_state == "IDLE":
                    update_main_button_text("idle")
            
            last_state_str = current_state_str
        except: 
            pm = None
            is_hooked = False

    def adjust_brightness(hex_color, factor):
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        new_rgb = tuple(max(0, min(int(c * factor), 255)) for c in rgb)
        return f"#{new_rgb[0]:02x}{new_rgb[1]:02x}{new_rgb[2]:02x}"

    class RoundedButton(tk.Canvas):
        def __init__(self, parent, text, bg, fg, command, width=320, height=55, radius=20, font=("Segoe UI", 14, "bold")):
            super().__init__(parent, width=width, height=height, bg="#121212", highlightthickness=0)
            self.bg_color = bg
            self.command = command
            
            self.last_click_time = 0  
            
            x1, y1, x2, y2 = 0, 0, width, height
            points = [
                x1+radius, y1, x2-radius, y1, x2, y1, x2, y1+radius, x2, y2-radius, 
                x2, y2, x2-radius, y2, x1+radius, y2, x1, y2, x1, y2-radius, 
                x1, y1+radius, x1, y1
            ]
            self.rect = self.create_polygon(points, fill=bg, smooth=True)
            self.txt = self.create_text(width/2, height/2, text=text, fill=fg, font=font)
            
            self.bind("<Enter>", self.on_enter)
            self.bind("<Leave>", self.on_leave)
            
            self.bind("<Button-1>", self.on_click)
            
        def on_enter(self, e): self.itemconfig(self.rect, fill=adjust_brightness(self.bg_color, 1.2))
        def on_leave(self, e): self.itemconfig(self.rect, fill=self.bg_color)
        
        def on_click(self, e): 
            import time
            if time.time() - self.last_click_time < 0.5:
                return "break"
                
            self.last_click_time = time.time()
            
            if self.command: 
                self.command()
            return "break"
            
        def configure(self, text=None, bg=None):
            if text is not None: self.itemconfig(self.txt, text=text)
            if bg is not None:
                self.bg_color = bg
                self.itemconfig(self.rect, fill=bg)

    def update_main_button_text(state):
        global current_glt_scenario
        if state == "idle":
            btn_play.configure(text="START PLAYBACK", bg="#2ecc71")
            btn_manual.configure(text="MANUAL RECORD", bg="#8e44ad")
            set_action_status("Idle", "#a0a0a0")
        elif state == "playing":
            btn_play.configure(text="PLAYING...", bg="#e67e22")
            set_action_status("Auto Playing...", "#e67e22")
        elif state == "recording":
            btn_manual.configure(text="RECORDING...", bg="#c0392b")
            set_action_status("Manual Recording...", "#c0392b")
        elif state == "done":
            btn_play.configure(text="REPLAY ANIMATION", bg="#3498db")
            btn_manual.configure(text="MANUAL RECORD", bg="#8e44ad")
            scen_txt = f"Ready (Scenario {current_glt_scenario})" if current_glt_scenario else "Waiting for User..."
            set_action_status("Waiting for User...", "#3498db")

    def play_btn_click():
        global playback_state, recorded_frames, freeze_frame
        if playback_state != "IDLE":
            playback_state = "IDLE"
            vk_action = get_vk(get_profile_keys()["key_action"])
            scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
            release_key(vk_action, scan_action)
            restore_original_state()
            update_main_button_text("idle")
            return

        try:
            if not os.path.exists(JSON_PATH):
                os.makedirs(os.path.dirname(JSON_PATH) if os.path.dirname(JSON_PATH) else CURRENT_DIR, exist_ok=True)
                with open(JSON_PATH, "w") as f:
                    json.dump({"frames": [], "freeze_frame": None, "is_goal": False}, f)
            with open(JSON_PATH, "r") as f:
                data = json.load(f)
                recorded_frames = data.get("frames", [])
        except:
            messagebox.showerror("Error", "No valid goal-line frames found.")
            return

        if not recorded_frames:
            messagebox.showerror("Error", "No valid goal-line frames found.")
            return

        analyze_trajectory()

        if not freeze_frame:
            messagebox.showerror("Error", "Could not determine freeze frame.")
            return

        # ================================================================
        # REPLAY ANIMATION boundary:
        # This is the FIRST game-state change for the animation.
        # CAM4 must become 03 BEFORE any replay/rewind input and BEFORE
        # the game-camera coordinates are applied by start_play_chain().
        # It must remain locked until the complete playback/reset cycle
        # finishes.
        # ================================================================
        if not cam4_lock_start():
            set_action_status("Camera 4 lock failed - replay cancelled", "#e74c3c")
            return

        # IMPORTANT: let the game process Camera 4 = 03 before the replay
        # chain starts.  Only after this settle interval are camera coordinates
        # allowed to be applied.
        root.after(CAM4_SETTLE_DELAY_MS, start_play_chain)
        
    def manual_record_btn_click():
        global manual_record_state, recorded_frames
        if manual_record_state != "IDLE":
            manual_record_state = "IDLE"
            prof = get_profile_keys()
            vk_action = get_vk(prof["key_action"])
            scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
            release_key(vk_action, scan_action)
            
            analyze_trajectory()
            try:
                data = {"frames": recorded_frames, "freeze_frame": freeze_frame, "is_goal": is_goal_scored}
                os.makedirs(os.path.dirname(JSON_PATH) if os.path.dirname(JSON_PATH) else CURRENT_DIR, exist_ok=True)
                with open(JSON_PATH, "w") as f: json.dump(data, f)
            except: pass
            
            if freeze_frame:
                start_manual_playback_chain()
            else:
                update_main_button_text("idle")
            return

        if current_state_str != "REPLAY":
            messagebox.showwarning("Warning", "Please enter Replay Mode first!")
            return

        recorded_frames.clear()
        
        try:
            os.makedirs(os.path.dirname(JSON_PATH) if os.path.dirname(JSON_PATH) else CURRENT_DIR, exist_ok=True)
            with open(JSON_PATH, "w") as f:
                json.dump({"frames": [], "freeze_frame": None, "is_goal": False}, f)
        except: pass
        
        start_manual_recording_sequence()

    def start_manual_recording_sequence():
        global manual_record_state, manual_unchanged_count, manual_last_coords
        
        manual_record_state = "RECORDING"
        manual_unchanged_count = 0
        manual_last_coords = None
        
        update_main_button_text("recording")
        
        focus_and_click_game()
        
        prof = get_profile_keys()
        
        vk_q = get_vk(prof["key_q"])
        vk_w = get_vk(prof["key_w"])
        scan_q = user32.MapVirtualKeyW(vk_q, 0) if vk_q else 0
        scan_w = user32.MapVirtualKeyW(vk_w, 0) if vk_w else 0
        
        vk_action = get_vk(prof["key_action"])
        scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
        
        press_key(vk_q, scan_q)
        press_key(vk_w, scan_w)
        
        def step2():
            release_key(vk_q, scan_q)
            release_key(vk_w, scan_w)
            
            press_key(vk_action, scan_action)
            root.after(16, manual_recording_routine)
            
        root.after(150, step2)

    def manual_recording_routine():
        global manual_record_state, manual_unchanged_count, manual_last_coords, recorded_frames
        if manual_record_state != "RECORDING": return
        
        live = get_live_coords()
        if not live:
            root.after(16, manual_recording_routine)
            return
            
        recorded_frames.append(live)
        
        min_frames_reached = len(recorded_frames) >= 800
        
        if min_frames_reached:
            if manual_last_coords and calc_dist(live, manual_last_coords) < 0.005:
                manual_unchanged_count += 1
            else:
                manual_unchanged_count = 0
        else:
            manual_unchanged_count = 0
            
        manual_last_coords = live
        ball_stopped = manual_unchanged_count >= 200
        
        if len(recorded_frames) >= 1200 or (min_frames_reached and ball_stopped):
            manual_record_state = "IDLE"
            
            vk_action = get_vk(get_profile_keys()["key_action"])
            scan_action = user32.MapVirtualKeyW(vk_action, 0) if vk_action else 0
            release_key(vk_action, scan_action)
            
            analyze_trajectory()
            try:
                data = {"frames": recorded_frames, "freeze_frame": freeze_frame, "is_goal": is_goal_scored}
                os.makedirs(os.path.dirname(JSON_PATH) if os.path.dirname(JSON_PATH) else CURRENT_DIR, exist_ok=True)
                with open(JSON_PATH, "w") as f: json.dump(data, f)
            except: pass
            
            if not freeze_frame:
                update_main_button_text("idle")
                set_action_status("Failed to find proper target point!", "#e74c3c")
                return

            # Manual recording has ended. Enter the exact same playback boundary
            # as REPLAY ANIMATION: first select camera 4 (03), then begin rewind.
            if not cam4_lock_start():
                update_main_button_text("idle")
                set_action_status("Camera 4 lock failed - playback cancelled", "#e74c3c")
                return

            # Same Camera-4 settle interval as REPLAY ANIMATION.
            # The game gets one or more frames to commit Camera 4 before
            # playback preparation and game-camera coordinates begin.
            root.after(CAM4_SETTLE_DELAY_MS, start_manual_playback_chain)
        else:
            if min_frames_reached:
                set_action_status(f"Manual Rec: {len(recorded_frames)} | Waiting to stop: {manual_unchanged_count}/200", "#c0392b")
            else:
                set_action_status(f"Manual Rec: {len(recorded_frames)}/800 minimum", "#c0392b")
                
            root.after(16, manual_recording_routine)

    # ------------------------------------------------------------------
    # سد محکم (Hard Barrier): پیش از هرگونه نوشتن مختصات دوربین، باید مقدار
    # انتخاب‌گر دوربین دقیقاً 0x03 باقی مانده باشد؛ در غیر این صورت کل
    # پروسه بازپخش ABORT شده، هیچ مختصاتی نوشته نمی‌شود و قفل آزاد می‌گردد.
    # ------------------------------------------------------------------


    
    def start_manual_playback_chain():
        if not verify_cam4_hard_barrier():
            flog("PLAY", "Hard Barrier Failed (manual): Camera is not 03 after delay. Aborting playback!")
            restore_original_state()
            update_main_button_text("idle")
            set_action_status("Playback Aborted: Cam 03 Failed", "#e74c3c")
            return

        global playback_state, unchanged_count, last_live_coords, speed_ok_count
        set_taskbar_visible(False)
        update_main_button_text("playing")
        playback_state = "INIT"
        unchanged_count = 0
        speed_ok_count = 0
        last_live_coords = None
        
        # ۱. فوکوس قطعی روی بازی تا دکمه‌های ریوایند دریافت شوند
        focus_and_click_game()
        
        prof = get_profile_keys()
        vk_q = get_vk(prof["key_q"])
        vk_w = get_vk(prof["key_w"])
        vk_d = get_vk(prof["key_d"])
        scan_q = user32.MapVirtualKeyW(vk_q, 0) if vk_q else 0
        scan_w = user32.MapVirtualKeyW(vk_w, 0) if vk_w else 0
        scan_d = user32.MapVirtualKeyW(vk_d, 0) if vk_d else 0
        
        flog("PLAY", "Manual playback chain started. Applying preset 1...")
        if not apply_preset(1):
            flog("PLAY", "Apply preset failed (manual). Aborting!")
            restore_original_state()
            update_main_button_text("idle")
            return
        
        def step2():
            flog("PLAY", "Sending Q+W (Reset view)...")
            press_key(vk_q, scan_q)
            press_key(vk_w, scan_w)
            root.after(150, step3)
            
        def step3():
            release_key(vk_q, scan_q)
            release_key(vk_w, scan_w)
            root.after(200, step4)
            
        def step4():
            flog("PLAY", "Sending D (Rewind replay)...")
            press_key(vk_d, scan_d)
            root.after(120, lambda: release_key(vk_d, scan_d))
            # فرصت ۱ ثانیه‌ای به بازی برای بازگشت ریپلی به ابتدای حرکت
            root.after(1000, step5)
            
        def step5():
            global playback_state
            flog("PLAY", "Rewind wait complete. Starting playback routine...")
            playback_state = "NORMAL_SPEED"
            playback_routine()
            
        root.after(100, step2)

    def start_play_chain():
        # بررسی مجدد سد محکم پس از اتمام 80 میلی‌ثانیه تاخیر
        if not verify_cam4_hard_barrier():
            flog("PLAY", "Hard Barrier Failed: Camera is not 03 after delay. Aborting playback!")
            restore_original_state()
            update_main_button_text("idle")
            set_action_status("Playback Aborted: Cam 03 Failed", "#e74c3c")
            return

        global playback_state, unchanged_count, last_live_coords, speed_ok_count
        set_taskbar_visible(False)
        update_main_button_text("playing")
        playback_state = "INIT"
        unchanged_count = 0
        speed_ok_count = 0
        last_live_coords = None
        focus_and_click_game()
        
        prof = get_profile_keys()
        vk_q = get_vk(prof["key_q"])
        vk_w = get_vk(prof["key_w"])
        scan_q = user32.MapVirtualKeyW(vk_q, 0) if vk_q else 0
        scan_w = user32.MapVirtualKeyW(vk_w, 0) if vk_w else 0
        
        press_key(vk_q, scan_q)
        press_key(vk_w, scan_w)
        
        def step2():
            release_key(vk_q, scan_q)
            release_key(vk_w, scan_w)
            root.after(200, step3)
            
        def step3():
            # اعمال قطعی پریست فقط پس از رد شدن از سد محکم
            if not apply_preset(1):
                flog("PLAY", "Apply preset failed. Aborting!")
                restore_original_state()
                update_main_button_text("idle")
                return
            root.after(100, step4)
            
        def step4():
            vk_d = get_vk(prof["key_d"])
            scan_d = user32.MapVirtualKeyW(vk_d, 0) if vk_d else 0
            press_key(vk_d, scan_d)
            root.after(100, lambda: release_key(vk_d, scan_d))
            root.after(200, step5)
            
        def step5():
            global playback_state
            playback_state = "WAITING_FOR_REWIND"
            playback_routine()
            
        root.after(100, step2)

    settings_panel = None
    def toggle_menu():
        global settings_panel
        if settings_panel.winfo_viewable():
            settings_panel.place_forget()
        else:
            settings_panel.place(x=0, y=75, width=400, height=565)
            settings_panel.lift()

    active_binding_key = None
    active_binding_btn = None

    def begin_binding(config_key, btn):
        global active_binding_key, active_binding_btn
        if active_binding_btn:
            active_binding_btn.configure(text=get_profile_keys()[active_binding_key].upper(), bg="#1e1e1e")
        active_binding_key = config_key
        active_binding_btn = btn
        btn.configure(text="PRESS KEY...", bg="#e67e22")
        root.bind("<KeyPress>", capture_key_event)

    def capture_key_event(event):
        global active_binding_key, active_binding_btn
        if not active_binding_key: return
        key_name = vk_to_key_name(event.keycode)
        if not key_name:
            key_name = event.keysym.lower()
            if key_name == "return": key_name = "enter"
        set_profile_key(active_binding_key, key_name)
        active_binding_btn.configure(text=key_name.upper(), bg="#1e1e1e")
        root.unbind("<KeyPress>")
        active_binding_key = None
        active_binding_btn = None

    def on_process_change(val):
        config_data["process_name"] = val
        save_config()
        refresh_settings_ui()
        if pm: 
            global is_hooked, connection_time
            is_hooked = False
            connection_time = 0
            connect_to_game()

    def refresh_settings_ui():
        prof = get_profile_keys()
        for k, btn in bind_btns.items():
            btn.configure(text=prof[k].upper())

    # --- UI Design ---
    conn_frame = tk.Frame(root, bg="#1a1a1a", height=20)
    conn_frame.pack(fill="x")
    lbl_conn_status = tk.Label(conn_frame, text="DISCONNECTED", fg="#e74c3c", bg="#1a1a1a", font=("Segoe UI", 8, "bold"))
    lbl_conn_status.pack(pady=2)

    header_frame = tk.Frame(root, bg="#1a1a1a", height=55)
    header_frame.pack(fill="x")
    header_frame.pack_propagate(False)

    btn_menu = tk.Button(header_frame, text="≡", bg="#1a1a1a", fg="white", font=("Segoe UI", 20, "bold"),
                         activebackground="#1a1a1a", activeforeground="white", bd=0, relief="flat", cursor="hand2", command=toggle_menu)
    btn_menu.pack(side="left", padx=15)

    lbl_title = tk.Label(header_frame, text="GOAL LINE TECHNOLOGY", bg="#1a1a1a", fg="white", font=("Impact", 18))
    lbl_title.pack(side="left", padx=5)

    coords_frame = tk.Frame(root, bg="#1a1a1a", bd=0, highlightthickness=1, highlightbackground="#333333")
    coords_frame.pack(pady=15, padx=20, fill="x")

    lbl_coords_title = tk.Label(coords_frame, text="LIVE BALL COORDINATES", bg="#1a1a1a", fg="#a0a0a0", font=("Segoe UI", 10, "bold"))
    lbl_coords_title.pack(pady=(10, 5))

    c_grid = tk.Frame(coords_frame, bg="#1a1a1a")
    c_grid.pack(pady=5)

    tk.Label(c_grid, text="X:", bg="#1a1a1a", fg="#e74c3c", font=("Segoe UI", 14, "bold")).grid(row=0, column=0, padx=10, pady=2)
    lbl_val_x = tk.Label(c_grid, text="0.0000", bg="#1a1a1a", fg="white", font=("Consolas", 14, "bold"))
    lbl_val_x.grid(row=0, column=1, padx=10, pady=2)

    tk.Label(c_grid, text="Y:", bg="#1a1a1a", fg="#2ecc71", font=("Segoe UI", 14, "bold")).grid(row=1, column=0, padx=10, pady=2)
    lbl_val_y = tk.Label(c_grid, text="0.0000", bg="#1a1a1a", fg="white", font=("Consolas", 14, "bold"))
    lbl_val_y.grid(row=1, column=1, padx=10, pady=2)

    tk.Label(c_grid, text="Z:", bg="#1a1a1a", fg="#f1c40f", font=("Segoe UI", 14, "bold")).grid(row=2, column=0, padx=10, pady=2)
    lbl_val_z = tk.Label(c_grid, text="0.0000", bg="#1a1a1a", fg="white", font=("Consolas", 14, "bold"))
    lbl_val_z.grid(row=2, column=1, padx=10, pady=2)

    state_frame = tk.Frame(root, bg="#121212")
    state_frame.pack(pady=5)

    lbl_status_title = tk.Label(state_frame, text="STATUS:", bg="#121212", fg="#a0a0a0", font=("Segoe UI", 12, "bold"))
    lbl_status_title.pack(side="left", padx=5)

    lbl_game_state_val = tk.Label(state_frame, text="Stop", bg="#121212", fg="#3498db", font=("Segoe UI", 14, "bold"))
    lbl_game_state_val.pack(side="left", padx=5)
    
    action_frame = tk.Frame(root, bg="#121212", width=350, height=80)
    action_frame.pack(pady=(0, 10))
    action_frame.pack_propagate(False)

    action_canvas = tk.Canvas(action_frame, bg="#121212", width=350, height=80, highlightthickness=0)
    action_canvas.pack(fill="both", expand=True)

    btn_play = RoundedButton(root, text="START PLAYBACK", bg="#2ecc71", fg="white", command=play_btn_click)
    btn_play.pack(pady=(10, 10), padx=40)

    btn_manual = RoundedButton(root, text="MANUAL RECORD", bg="#8e44ad", fg="white", command=manual_record_btn_click)
    btn_manual.pack(pady=(0, 20), padx=40)

    style_frame = tk.Frame(root, bg="#121212")
    style_frame.pack(pady=10, fill="x")

    lbl_style_title = tk.Label(style_frame, text="Animation Style", bg="#121212", fg="#a0a0a0", font=("Segoe UI", 10, "bold"))
    lbl_style_title.pack(pady=2)

    styles_container = tk.Frame(style_frame, bg="#121212")
    styles_container.pack()

    btn_style1 = tk.Button(styles_container, text="STYLE 1", bg="#1a1a1a", fg="white", font=("Segoe UI", 9, "bold"), activebackground="#1a1a1a", activeforeground="white", bd=0, cursor="hand2")
    btn_style2 = tk.Button(styles_container, text="STYLE 2", bg="#1a1a1a", fg="white", font=("Segoe UI", 9, "bold"), activebackground="#1a1a1a", activeforeground="white", bd=0, cursor="hand2")
    
    if "thumb_t5" in ui_images: btn_style1.configure(image=ui_images["thumb_t5"], text="", width=140, height=80)
    else: btn_style1.configure(padx=15, pady=8)
    
    if "thumb_t6" in ui_images: btn_style2.configure(image=ui_images["thumb_t6"], text="", width=140, height=80)
    else: btn_style2.configure(padx=15, pady=8)
    
    btn_style1.pack(side="left", padx=10)
    btn_style2.pack(side="left", padx=10)

    def change_style(style_name):
        config_data["scene_theme"] = style_name
        save_config()
        _sync_style_to_mods_config(style_name)   # [suite] keep MyMods in sync
        btn_style1.configure(bg="#27ae60" if style_name == "T5" else "#1a1a1a")
        btn_style2.configure(bg="#27ae60" if style_name == "T6" else "#1a1a1a")
        
        apply_ground_theme(style_name)
        
        line_key = f"line_{style_name.lower()}"
        line_tex_path = tex_paths[line_key]
        goal_line.texture = get_safe_texture(line_tex_path)

    change_style(config_data["scene_theme"])
    btn_style1.configure(command=lambda: change_style("T5"))
    btn_style2.configure(command=lambda: change_style("T6"))

    lbl_footer = tk.Label(root, text="Goal Line Technology By Milad Version 2.0.0", bg="#121212", fg="gray", font=("Segoe UI", 9))
    lbl_footer.pack(side="bottom", pady=10)

    settings_panel = tk.Frame(root, bg="#1a1a1a", bd=0, highlightthickness=1, highlightbackground="#333333")
    
    settings_canvas = tk.Canvas(settings_panel, bg="#1a1a1a", highlightthickness=0)
    settings_scrollbar = tk.Scrollbar(settings_panel, orient="vertical", command=settings_canvas.yview,
                                      bg="#1a1a1a", activebackground="#333333", troughcolor="#121212", bd=0, highlightthickness=0)
    
    scrollable_frame = tk.Frame(settings_canvas, bg="#1a1a1a")
    
    scrollable_frame.bind(
        "<Configure>",
        lambda e: settings_canvas.configure(
            scrollregion=settings_canvas.bbox("all")
        )
    )
    
    settings_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=376)
    settings_canvas.configure(yscrollcommand=settings_scrollbar.set)
    
    settings_canvas.pack(side="left", fill="both", expand=True)
    settings_scrollbar.pack(side="right", fill="y")
    
    def _on_mousewheel(event):
        if settings_panel.winfo_viewable():
            settings_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            
    settings_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    bind_btns = {}
    
    ctk_label_proc = tk.Label(scrollable_frame, text="Process Name:", bg="#1a1a1a", fg="white", font=("Segoe UI", 10, "bold"))
    ctk_label_proc.pack(pady=(15, 0), padx=20, anchor="w")

    proc_var = tk.StringVar(value=config_data["process_name"])
    # حذف PES 2017 از گزینه‌های لیست دراپ‌داون
    proc_menu = tk.OptionMenu(scrollable_frame, proc_var, "FL_2026.exe", "PES2021.exe",
                              command=on_process_change)
    proc_menu.configure(bg="#242424", fg="white", activebackground="#242424", activeforeground="white", bd=0, relief="flat", highlightthickness=0)
    proc_menu.pack(pady=5, padx=20, fill="x")

    short_frame = tk.Frame(scrollable_frame, bg="#1a1a1a")
    short_frame.pack(pady=10, padx=20, fill="x")
    tk.Label(short_frame, text="Global Shortcuts", bg="#1a1a1a", fg="#a0a0a0", font=("Segoe UI", 11, "bold")).pack(pady=5, anchor="w")

    def make_shortcut_row(parent, label_text, config_key):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label_text, bg="#1a1a1a", fg="white", font=("Segoe UI", 10)).pack(side="left")
        btn = tk.Button(row, text=get_profile_keys()[config_key].upper(), bg="#242424", fg="white", bd=0, relief="flat", font=("Segoe UI", 9, "bold"), width=12)
        btn.pack(side="right")
        btn.configure(command=lambda: begin_binding(config_key, btn))
        bind_btns[config_key] = btn

    make_shortcut_row(short_frame, "Toggle UI Window:", "hotkey_toggle")
    make_shortcut_row(short_frame, "Play Animation:", "hotkey_play")

    macro_frame = tk.Frame(scrollable_frame, bg="#1a1a1a")
    macro_frame.pack(pady=10, padx=20, fill="x")
    tk.Label(macro_frame, text="Animation Button Bindings", bg="#1a1a1a", fg="#a0a0a0", font=("Segoe UI", 11, "bold")).pack(pady=5, anchor="w")

    def make_macro_row(parent, label_text, config_key, icon_key):
        row = tk.Frame(parent, bg="#1a1a1a")
        row.pack(fill="x", pady=5)
        if icon_key in ui_images:
            tk.Label(row, image=ui_images[icon_key], bg="#1a1a1a").pack(side="left", padx=(0, 5))
        tk.Label(row, text=label_text, bg="#1a1a1a", fg="white", font=("Segoe UI", 10)).pack(side="left")
        btn = tk.Button(row, text=get_profile_keys()[config_key].upper(), bg="#242424", fg="white", bd=0, relief="flat", font=("Segoe UI", 9, "bold"), width=12)
        btn.pack(side="right")
        btn.configure(command=lambda: begin_binding(config_key, btn))
        bind_btns[config_key] = btn

    make_macro_row(macro_frame, "Right Arrow Key:", "key_action", "icon_action")
    make_macro_row(macro_frame, "Left Arrow Key:", "key_back", "icon_back")
    make_macro_row(macro_frame, "L1 Key:", "key_q", "icon_q")
    make_macro_row(macro_frame, "△ Key:", "key_w", "icon_w")
    make_macro_row(macro_frame, "〇 Key:", "key_d", "icon_d")

    toggle_was_down = False
    play_was_down = False
    rec_was_down = False          # [suite] MyMods manual-record key

    def poll_global_hotkeys():
        global toggle_was_down, play_was_down, rec_was_down
        prof = get_profile_keys()
        vk_toggle = get_vk(prof["hotkey_toggle"])
        vk_play = get_vk(prof["hotkey_play"])

        # [suite] manual-record key configured in MyMods (ModsConfig.json).
        # It runs the panel's own MANUAL RECORD action.  When it collides
        # with the panel-toggle key, the toggle is suspended so one key
        # never fires two actions.
        vk_rec = SUITE_REC_VK
        if vk_rec and vk_rec == vk_toggle:
            vk_toggle = 0
        
        if vk_toggle:
            is_down = bool(user32.GetAsyncKeyState(vk_toggle) & 0x8000)
            if is_down and not toggle_was_down:
                if root.state() == "normal": root.withdraw()
                else: root.deiconify(); root.lift(); root.focus_force()
            toggle_was_down = is_down

        if vk_play:
            is_down = bool(user32.GetAsyncKeyState(vk_play) & 0x8000)
            if is_down and not play_was_down:
                play_btn_click()
            play_was_down = is_down

        # [suite] MyMods manual-record key -> the panel's own record flow
        # (identical to clicking MANUAL RECORD; it validates Replay Mode,
        # records, analyzes and starts the goal scene automatically).
        if vk_rec:
            is_down = bool(user32.GetAsyncKeyState(vk_rec) & 0x8000)
            if is_down and not rec_was_down:
                manual_record_btn_click()
            rec_was_down = is_down

    def lerp_rot(r1, r2, t):
        return Vec3(
            r1[0] + ((r2[0] - r1[0] + 180) % 360 - 180) * t,
            r1[1] + ((r2[1] - r1[1] + 180) % 360 - 180) * t,
            r1[2] + ((r2[2] - r1[2] + 180) % 360 - 180) * t
        )
    def ease_in_out_bezier(t):
        return (1.0 - math.cos(t * math.pi)) / 2.0

    last_fetch_time = 0.0
    is_first_frame = True

    def update():
        global last_fetch_time, pending_animation, is_first_frame
        global is_animating_camera, anim_state, anim_start_time, anim_duration, anim_callback
        global f2_rot_start, f2_rot_end, f1_look_rot_actual, goal_ui_fired
        
        if not _tk_alive:
            application.quit()
            return
            
        try:
            root.update()
            poll_global_hotkeys()
        except: pass

        if is_first_frame:
            set_window_opacity(0.0)
            is_first_frame = False

        if pending_animation is not None:
            args = pending_animation
            pending_animation = None
            _do_start_custom_anim(*args)

        ct = time.perf_counter()
        if ct - last_fetch_time >= 0.016:
            fetch_memory_step()
            last_fetch_time = ct

        if is_animating_camera:
            t = min((time.time() - anim_start_time) / anim_duration, 1.0)
            progress = ease_in_out_bezier(t) # استفاده از تابع نرم‌کننده برای تمام حرکات
            
            if anim_state == "fade_in":
                set_window_opacity(t)
                camera.position = f1_pos
                camera.rotation = f1_rot
                for post_ent in [post_l, post_r, bar] + net_parts: post_ent.color = color.rgba(1, 1, 1, t)
                
            elif anim_state == "pre_align":
                # چرخش بسیار نرم بدون پرش
                camera.position = f1_pos
                camera.rotation = lerp_rot(f1_rot, f1_look_rot, progress)
                camera.fov = 20.69
                set_window_opacity(1.0)
                # تیرک‌ها و تور در طول چرخش سر دوربین نمایان می‌مانند (بدون خاموشی ناگهانی)
                for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = True

            elif anim_state == "move_forward":
                # حرکت با پیشروی نرم، قفل روی توپ
                camera.position = lerp(f1_pos, f2_pos, progress)
                camera.look_at(Vec3(ball.x, ball.y, ball.z))
                camera.fov = 20.69 
                set_window_opacity(1.0)
                FADE_POST = 1.8 / 2.5
                if t <= FADE_POST:
                    post_alpha = 1.0 - (t / FADE_POST)
                    for post_ent in [post_l, post_r, bar] + net_parts:
                        post_ent.enabled = True; post_ent.color = color.rgba(1, 1, 1, post_alpha)
                else:
                    for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = False
                # نمایش GOAL/NO GOAL وقتی دوربین ۹۰٪ مسیر پرواز را رفته (۱۰٪ مانده به بالای توپ)
                if not goal_ui_fired and t >= 0.9:
                    goal_ui_fired = True
                    show_goal_ui_animation()
                    root.after(4450, hide_goal_ui_animation)   # ۲۵۰ms باقی‌مانده پرواز + ۱۰۰۰ms hold_top + ۳۲۰۰ms مثل قبل

                    
            elif anim_state == "hold_top":
                # بدون چرخش ۹۰ درجه: دوربین دقیقاً بالای توپ می‌ماند (همان f2_pos با آفست 0.11)
                # و با همان جهت look_at از بغل به توپ نگاه می‌کند؛ خط دروازه در کادر عمود دیده می‌شود
                camera.position = f2_pos
                camera.rotation = f2_rot_start
                camera.fov = 20.69
                set_window_opacity(1.0)
                for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = False


            elif anim_state == "move_backward":
                # برگشت نرم مسیر، دوباره قفل روی توپ
                camera.position = lerp(f2_pos, f1_pos, progress)
                camera.look_at(Vec3(ball.x, ball.y, ball.z))
                camera.fov = 20.69
                set_window_opacity(1.0)
                FADE_POST = 1.8 / 2.5
                fade_post_start = 1.0 - FADE_POST
                if t >= fade_post_start:
                    post_alpha = (t - fade_post_start) / FADE_POST
                    for post_ent in [post_l, post_r, bar] + net_parts:
                        post_ent.enabled = True; post_ent.color = color.rgba(1, 1, 1, post_alpha)
                else:
                    for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = False

            elif anim_state == "post_unalign":
                # برگشت زاویه به حالت اولیه کالیبره شده
                camera.position = f1_pos
                camera.rotation = lerp_rot(f1_look_rot_actual, f1_rot, progress)
                camera.fov = 20.69
                set_window_opacity(1.0)
                # تیرک‌ها و تور در طول چرخش برگشت سر دوربین نمایان می‌مانند
                for post_ent in [post_l, post_r, bar] + net_parts: post_ent.enabled = True
                    
            elif anim_state == "fade_out":
                set_window_opacity(1.0 - t)
                camera.position = f1_pos
                camera.rotation = f1_rot
                camera.fov = 20.50   # دقیقا fov نمای اولیه؛ فریم آخر بدون هیچ انحرافی بر اولین فریم انیمیشن منطبق می‌شود
                for post_ent in [post_l, post_r, bar] + net_parts: post_ent.color = color.rgba(1, 1, 1, 1.0 - t)

            # --- لاجیک اتمام هر انیمیشن ---
            if t >= 1.0:
                if anim_state == "move_forward":
                    # مختصات دوربینی که با look_at به توپ نگاه می‌کرد دقیقاً ذخیره می‌شود
                    f2_rot_start = Vec3(camera.rotation[0], camera.rotation[1], camera.rotation[2])
                    # زاویه نهایی تعریف می‌شود: شیب (Pitch) و انحراف (Roll) دست نخورده می‌ماند، فقط افق (Yaw) 90 می‌شود
                    f2_rot_end = Vec3(f2_rot_start[0], target_yaw_anim, f2_rot_start[2])
                    
                elif anim_state == "move_backward":
                    # ذخیره زاویه برگشت
                    f1_look_rot_actual = Vec3(camera.rotation[0], camera.rotation[1], camera.rotation[2])
                    
                is_animating_camera = False
                if anim_state == "fade_out":
                    set_window_opacity(0.0)
                    focus_game_only()
                if anim_callback: anim_callback()

    # [suite] background mode — keep the panel hidden at startup; the
    # original front-raised startup is kept behind GLT_START_HIDDEN.
    if not GLT_START_HIDDEN:
        root.deiconify()
        root.lift()
        root.focus_force()

    set_action_status("Initializing System...", "#a0a0a0")
    set_window_opacity(0.0)
    
    # [suite] graceful-shutdown watchdog (ModBridge stop flag)
    try:
        threading.Thread(target=_glt_stop_flag_watchdog, daemon=True,
                         name="GLT-StopWatch").start()
    except Exception:
        pass

    try:
        app.run()
    except Exception as _e:
        _tb = traceback.format_exc()
        flog("CRASH", _tb)
    finally:
        try: _shutdown_cleanup()
        except: pass
        set_taskbar_visible(True)
        try: _log_file.close()
        except: pass

except Exception as _ex:
    _tb = _traceback.format_exc()
    try:
        with open(_CRASH_LOG, "w", encoding="utf-8") as _f:
            _f.write(_tb)
    except: pass
    try:
        import tkinter as _tk; import tkinter.messagebox as _mb
        _r = _tk.Tk(); _r.withdraw()
        _mb.showerror("Crash", f"Error:\n{_tb[:800]}")
        _r.destroy()
    except: pass