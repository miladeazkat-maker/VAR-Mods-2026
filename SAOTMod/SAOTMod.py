#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 S.A.O.T — Semi-Automated Offside Technology  (FL 2026 suite edition)
=====================================================================
Suite build v2.1.7 — integrated with the PES MODS suite (MyMods +
ModBridge). Based on the original standalone S.A.O.T tool v1.2.0 by
Milad77. English is the ONLY language of this build (user spec #4)
and FL_2026.exe is the ONLY supported game (user spec #2) — every
other game version's settings, pointers and features were removed.

WHAT CHANGED COMPARED TO THE ORIGINAL STANDALONE TOOL
-----------------------------------------------------
1.  MyMods hosts the mod's dedicated menu: the only option there is
    the CALL KEY (user spec #3) plus the usual tutorial-video,
    preview and instructions sections and the Rashid (ReShade)
    setup section (user spec #6). All in-app settings (sidebar,
    language picker, theme picker, game-version picker) were
    removed from the tool itself.
2.  The call key (chosen in MyMods, default F1) shows/hides this
    exact familiar GUI — view picker, plane ON/OFF, distance
    slider — WITHOUT the settings and training sections (user
    spec #5). The GUI starts hidden.
3.  GAME DETECTION IS THE BRIDGE'S JOB (user spec #8): this mod
    never scans the process list while a Bridge is answering. It
    asks the Bridge (game_status IPC) and attaches to the pid/base
    the Bridge reports. A local scan is used ONLY when no Bridge
    answers at all (standalone double-click run).
4.  THIS MOD HOOKS NOTHING (user spec #8): S.A.O.T never installs
    a code hook. It only reads/writes game memory through the
    pointer chains below, exactly like the original tool. All
    hook requests in the suite belong to the Bridge/HookBroker.
5.  The Rashid existence check + file copy moved to MyMods
    (SAOT menu -> RASHID SETUP). The texture/shader files live in
    SAOTMod\\textut (user spec #6/#7).
"""

import os
import re
import sys
import json
import time
import ctypes
import queue
import threading

try:
    import tkinter as tk
except Exception:                                   # pragma: no cover
    tk = None

try:
    import customtkinter as ctk
    HAS_CTK = True
except Exception:
    ctk = None
    HAS_CTK = False

try:
    import keyboard
    HAS_KEYBOARD = True
except Exception:
    keyboard = None
    HAS_KEYBOARD = False

try:
    import pywinstyles
    HAS_PYWINSTYLES = True
except Exception:
    pywinstyles = None
    HAS_PYWINSTYLES = False

try:
    import pymem
    import pymem.process
    import pymem.pattern
    PYMEM_OK = True
except Exception:
    pymem = None
    PYMEM_OK = False

try:
    import psutil
    PSUTIL_OK = True
except Exception:
    psutil = None
    PSUTIL_OK = False

# ---------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------
if getattr(sys, "frozen", False):
    _MOD_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    _MOD_DIR = os.path.abspath(os.path.dirname(__file__))
_SUITE_DIR = os.path.dirname(_MOD_DIR)
CONFIG_FILE = os.path.join(_SUITE_DIR, "ModsConfig.json")
IPC_FILE = os.path.join(_SUITE_DIR, "bridge_ipc.json")

PROCESS_NAME = "FL_2026.exe"
MOD_NAME = "S.A.O.T"

# --- FL 2026 memory layout (the ONLY game this build supports) --------
BASE_OFFSET = 0x037F8DD0
BASE_OFFSET_3 = 0x037F8DD0

POINTER_OFFSETS_1 = [0x8, 0x10, 0x20, 0x108, 0x18, 0x0, 0x20, 0x1D8, 0x500, 0x4]
POINTER_OFFSETS_2 = [0x8, 0x10, 0x38, 0x108, 0x18, 0x0, 0x20, 0x1D8, 0x500, 0x8]
POINTER_OFFSETS_3 = [0x8, 0x10, 0x20, 0x108, 0x28, 0x20, 0x20, 0x1D8, 0x500, 0x0]
POINTER_OFFSETS_IMAGE = [0x8, 0x10, 0x20, 0x108, 0x28, 0x20, 0x20, 0x1D8, 0x500, 0xC]

# Camera view chains (rot / distance) — FL 2026 only.
CAM_ROT_BASE = 0x037F89E0
CAM_DIST_BASE = 0x036F0260

# View presets: index -> (rot, distance-ptr, height, zoom)
VIEW_TABLE = {
    0: (0.687, 7.5, 1.70, 1.00),
    1: (2.675, 7.5, 1.70, 1.00),
    2: (-0.515, 7.5, 1.70, 1.00),
    3: (-2.823, 7.5, 1.70, 1.00),
}

# Pattern scans for the camera height / zoom floats (FL 2026).
PATTERN_CAM0_HEIGHT = (b"\xc7\x45\xab\xcd\xcc\xcc\x3e\xf3\x41\x0f\x58\xc0"
                       b"\xf3\x0f\x11\x45\xa7\x0f\x28\xc6")
PATTERN_ZOOM = (b"\xc7\x46\x30\xc3\xf5\x28\x3f\xf3\x44\x0f\x10\x06"
                b"\xf3\x44\x0f\x10\x4e\x08\xf3\x44\x0f\x11\x45\xc7")

# Call key chosen in MyMods (mods -> "S.A.O.T" -> apply_key_vk/name).
DEFAULT_CALL_KEY = {"vk": "0x70", "name": "F1"}

# Settings refresh cadence (config re-read + hotkey re-register).
CONFIG_POLL_SEC = 5.0
# Main-thread UI queue drain cadence (worker -> GUI marshalling).
UI_QUEUE_POLL_MS = 60
# Game-state poll cadence for the GUI read loop (the original tool
# re-polled every 20 ms — unnecessary for the suite build where the
# GUI stays hidden most of the time; 0.3 s keeps the sliders in sync
# instantly while keeping the CPU footprint at Heat-Map level).
GUI_POLL_MS = 300

# ---------------------------------------------------------------------
# English strings — the ONLY language of this build (user spec #4)
# ---------------------------------------------------------------------
EN = {
    "title": "\u26bd Semi-Automated Offside",
    "view_title": "Camera View Selection",
    "view_label": "Select View:",
    "view_desc": "Choose the optimal camera angle.",
    "views": ["View 1", "View 2", "View 3", "View 4", "Custom", "N/A"],
    "act_title": "Plane Activation",
    "act_label": "State:",
    "act_desc": "Enable or disable the 3D offside plane.",
    "states": ["OFF", "ON", "N/A"],
    "dist_title": "Plane Distance",
    "dist_desc": "Adjust the plane to align with the offside line.",
    "dist_prefix": "Distance: ",
    "status_prefix": "Status: ",
    "ready": "Ready",
    "mod_not_found": "Game module not found",
    "proc_not_running": "Game not running",
    "waiting_bridge": "Waiting for FL_2026.exe (the Bridge monitors the game)",
    "monitoring": "Monitoring...",
    "view_updated": "View updated",
    "err_view": "Error updating view",
    "dist_updated": "Distance updated",
    "err_dist": "Error updating distance",
    "act_toggled": "Activation toggled",
    "err_act": "Error toggling",
    "footer": "Version 2.1.7 | Created by Milad77",
    "custom_hint": ("\U0001F4A1 Minimize the app and use the ReShade menu "
                    "(Home key) to adjust manually."),
    "game_label": "Game Version:",
    "hotkey_label": "Toggle Hotkey:",
    "press_key": "Press any key...",
}

STATUS_COLORS = {
    "ready": ("#64748B", "#94A3B8"),
    "mod_not_found": ("#EF4444", "#F87171"),
    "proc_not_running": ("#EF4444", "#F87171"),
    "waiting_bridge": ("#3B82F6", "#60A5FA"),
    "monitoring": ("#3B82F6", "#60A5FA"),
    "view_updated": ("#10B981", "#34D399"),
    "err_view": ("#EF4444", "#F87171"),
    "dist_updated": ("#10B981", "#34D399"),
    "err_dist": ("#EF4444", "#F87171"),
    "act_toggled": ("#10B981", "#34D399"),
    "err_act": ("#EF4444", "#F87171"),
}

VIEW_INDEX_BY_NAME = {"View 1": 0, "View 2": 1, "View 3": 2, "View 4": 3,
                      "Custom": 4, "N/A": 5}
STATE_INDEX_BY_NAME = {"OFF": 0, "ON": 1, "N/A": 2}


def log_line(msg):
    """Append a line to the mod's backend_log.txt (bridge captures it)."""
    try:
        with open(os.path.join(_MOD_DIR, "backend_log.txt"), "a",
                  encoding="utf-8") as f:
            f.write("[" + time.strftime("%Y-%m-%d %H:%M:%S") + "] " + msg
                    + "\n")
    except Exception:
        pass


# =====================================================================
# BRIDGE CLIENT — game detection IPC (user spec #8)
# =====================================================================
# S.A.O.T asks the Bridge whether FL_2026.exe is running and for its
# pid/base. There are deliberately NO hook methods here: this mod never
# hooks anything, so the client only speaks hello / ping / game_status.
# =====================================================================
class BridgeClient:
    """JSON-line localhost client for the ModBridge HookBroker socket.

    Discovery: MODBRIDGE_IPC_PORT / MODBRIDGE_IPC_TOKEN env (bridge
    spawn), else <suite>/bridge_ipc.json. Only game-status commands —
    S.A.O.T installs no hooks and requests no hooks (user spec #8)."""
    MOD_NAME = MOD_NAME

    def __init__(self, port=None, token=None, ipc_file=None):
        self.last_error = "not-configured"
        self._lock = threading.RLock()
        self._sock = None
        self._buf = b""
        self._req_id = 0
        self._rpc_timeout = 6.0
        if port is None:
            try:
                port = int(os.environ.get("MODBRIDGE_IPC_PORT", "") or 0) or None
            except Exception:
                port = None
        if token is None:
            token = os.environ.get("MODBRIDGE_IPC_TOKEN") or None
        self._token = token
        self._port = port
        self._ipc_file = ipc_file or IPC_FILE
        if self._port is None and self._token is None:
            try:
                with open(self._ipc_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self._port = int(d.get("port") or 0) or None
                self._token = str(d.get("token") or "") or None
            except Exception:
                pass

    def available(self):
        return bool(self._port and self._token)

    def _refresh_from_file(self):
        try:
            with open(self._ipc_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            port = int(d.get("port") or 0) or None
            token = str(d.get("token") or "") or None
            if port and token:
                self._port, self._token = port, token
                return True
        except Exception:
            pass
        return False

    def _close_sock(self):
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self._buf = b""

    def _try_handshake(self):
        if self._sock is None:
            try:
                s = __import__("socket").create_connection(
                    ("127.0.0.1", int(self._port)), timeout=self._rpc_timeout)
                s.settimeout(self._rpc_timeout)
            except Exception as e:
                self.last_error = "connect-failed:" + e.__class__.__name__
                return False
            self._sock = s
            self._buf = b""
        try:
            hello = {"id": 0, "cmd": "hello", "mod": self.MOD_NAME,
                     "token": self._token}
            self._sock.sendall((json.dumps(hello) + "\n").encode("utf-8"))
            while b"\n" not in self._buf:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("closed")
                self._buf += chunk
            line, self._buf = self._buf.split(b"\n", 1)
            resp = json.loads(line.decode("utf-8"))
            if not resp.get("ok"):
                self.last_error = resp.get("error") or "hello-refused"
                return False
            return True
        except Exception as e:
            self.last_error = "hello:" + e.__class__.__name__
            self._close_sock()
            return False

    def _connect(self):
        if not self.available():
            self.last_error = "not-configured"
            return False
        if self._try_handshake():
            return True
        if self._refresh_from_file() and self._try_handshake():
            return True
        return False

    def _rpc(self, payload):
        with self._lock:
            if not self._connect():
                return None
            try:
                self._req_id += 1
                payload = dict(payload)
                payload["id"] = self._req_id
                self._sock.sendall(
                    (json.dumps(payload) + "\n").encode("utf-8"))
                while b"\n" not in self._buf:
                    chunk = self._sock.recv(4096)
                    if not chunk:
                        raise ConnectionError("closed")
                    self._buf += chunk
                line, self._buf = self._buf.split(b"\n", 1)
                resp = json.loads(line.decode("utf-8"))
                if not resp.get("ok"):
                    self.last_error = resp.get("error") or "refused"
                    if resp.get("error") in ("hello first",
                                             "bad token or mod name"):
                        self._close_sock()
                    return None
                return resp
            except Exception as e:
                self.last_error = e.__class__.__name__
                self._close_sock()
                return None

    def ping(self):
        return self._rpc({"cmd": "ping"})

    def game_status(self):
        """Is FL_2026.exe running? THE BRIDGE ANSWERS (user spec #8):
        the bridge polls the game every 2 s, so this mod opened BEFORE
        the game waits for the bridge's answer instead of trusting its
        own one-shot scan. Returns {running, pid, base, name} or None
        when no bridge answers at all (standalone run)."""
        return self._rpc({"cmd": "game_status"})


_BRIDGE = None
_BRIDGE_TRIED = False
_BRIDGE_LAST_FAIL = 0.0


def saot_bridge():
    """Lazy, cached bridge client. None = no bridge (standalone path).
    A failed discovery is retried every >= 5 s: the mod may be started
    before the bridge writes bridge_ipc.json — giving up forever would
    lock the mod out of game detection."""
    global _BRIDGE, _BRIDGE_TRIED, _BRIDGE_LAST_FAIL
    if _BRIDGE is not None:
        return _BRIDGE
    if _BRIDGE_TRIED:
        if time.time() - _BRIDGE_LAST_FAIL < 5.0:
            return None
        _BRIDGE_TRIED = False
    _BRIDGE_TRIED = True
    _BRIDGE_LAST_FAIL = time.time()
    try:
        cli = BridgeClient()
        if cli.available() and cli.ping() is not None:
            _BRIDGE = cli
            log_line("[BRIDGE] HookBroker reachable — game detection is "
                     "owned by the bridge (port %s)" % cli._port)
            return cli
        log_line("[BRIDGE] no bridge (%s) — standalone local scan path"
                 % cli.last_error)
    except Exception as e:
        log_line("[BRIDGE] discovery failed: %s: %s"
                 % (e.__class__.__name__, e))
    return None


def get_fl_pid_local():
    """Standalone-only fallback process scan (no bridge answering)."""
    if not PSUTIL_OK:
        return None
    try:
        for p in psutil.process_iter(["name"]):
            nm = (p.info.get("name") or "").lower()
            if nm == PROCESS_NAME.lower():
                return p.pid
    except Exception:
        pass
    return None


def get_fl_base_local(pid):
    """Standalone-only fallback base-address lookup."""
    if not PYMEM_OK or not pid:
        return 0
    try:
        pm = pymem.Pymem()
        pm.open_process_from_id(int(pid))
        module = pymem.process.module_from_name(pm.process_handle,
                                                PROCESS_NAME)
        if module:
            base = int(module.lpBaseOfDll)
            pm.close_process()
            return base
        pm.close_process()
    except Exception:
        pass
    return 0


def saot_wait_for_game(stop_event):
    """GAME DETECTION IS THE BRIDGE'S JOB (user spec #8). Bridge-first:
    ask game_status until the bridge reports FL_2026.exe running; a
    local scan happens ONLY while no bridge answers at all (standalone
    run). Returns (pid, base); (None, None) when stop_event fires."""
    while not stop_event.is_set():
        cli = saot_bridge()
        if cli is not None:
            st = None
            try:
                st = cli.game_status()
            except Exception:
                st = None
            if st is not None:
                # the bridge answered — its answer is final (no local scan)
                if st.get("running") and st.get("pid"):
                    try:
                        pid = int(st.get("pid") or 0)
                        base = int(str(st.get("base") or "0"), 16)
                    except Exception:
                        pid, base = 0, 0
                    if pid and base:
                        return pid, base
                stop_event.wait(1.0)
                continue
            # bridge unreachable right now — fall through to the local
            # scan below until it answers again (standalone / restarting)
        pid = get_fl_pid_local()
        if pid:
            base = get_fl_base_local(pid)
            if base:
                return pid, base
        stop_event.wait(1.0)
    return None, None


# =====================================================================
# MOD SETTINGS — MyMods writes mods["S.A.O.T"] in ModsConfig.json
# (the bridge also hands the same block via MODBRIDGE_SETTINGS env).
# The ONLY option is the CALL KEY (user spec #3).
# =====================================================================
def saot_load_settings():
    d = dict(DEFAULT_CALL_KEY)
    raw = os.environ.get("MODBRIDGE_SETTINGS", "")
    if raw:
        try:
            env_d = json.loads(raw)
            if isinstance(env_d, dict):
                if env_d.get("apply_key_vk"):
                    d["vk"] = str(env_d["apply_key_vk"])
                if env_d.get("apply_key_name"):
                    d["name"] = str(env_d["apply_key_name"])
        except Exception:
            pass
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        saved = (cfg.get("mods", {}) or {}).get(MOD_NAME, {}) or {}
        if saved.get("apply_key_vk"):
            d["vk"] = str(saved["apply_key_vk"])
        if saved.get("apply_key_name"):
            d["name"] = str(saved["apply_key_name"])
    except Exception:
        pass
    # sane fallbacks — never empty (an unset key would hide the GUI forever)
    try:
        if int(str(d.get("vk") or "0"), 16) <= 0:
            d = dict(DEFAULT_CALL_KEY)
    except Exception:
        d = dict(DEFAULT_CALL_KEY)
    if not str(d.get("name") or "").strip():
        d["name"] = DEFAULT_CALL_KEY["name"]
    return d


def vk_to_hotkey_name(vk_hex, fallback_name):
    """Virtual-key code hex -> keyboard-lib key name (best effort).
    The stored English display name (MyMods) is usually usable as-is
    after lowercasing; the vk table below covers the common keys."""
    table = {
        0x01: "esc", 0x02: "1", 0x03: "2", 0x04: "3", 0x05: "4", 0x06: "5",
        0x07: "6", 0x08: "7", 0x09: "8", 0x0A: "9", 0x0B: "0",
        0x0C: "-", 0x0D: "=", 0x0E: "backspace", 0x0F: "tab",
        0x10: "q", 0x11: "w", 0x12: "e", 0x13: "r", 0x14: "t", 0x15: "y",
        0x16: "u", 0x17: "i", 0x18: "o", 0x19: "p", 0x1A: "[", 0x1B: "]",
        0x1C: "enter", 0x1D: "left ctrl", 0x1E: "a", 0x1F: "s", 0x20: "d",
        0x21: "f", 0x22: "g", 0x23: "h", 0x24: "j", 0x25: "k", 0x26: "l",
        0x27: ";", 0x28: "'", 0x29: "`", 0x2A: "left shift", 0x2B: "\\",
        0x2C: "z", 0x2D: "x", 0x2E: "c", 0x2F: "v", 0x30: "b", 0x31: "n",
        0x32: "m", 0x33: ",", 0x34: ".", 0x35: "/", 0x36: "right shift",
        0x37: "*", 0x38: "left alt", 0x39: "space", 0x3A: "caps lock",
        0x3B: "f1", 0x3C: "f2", 0x3D: "f3", 0x3E: "f4", 0x3F: "f5",
        0x40: "f6", 0x41: "f7", 0x42: "f8", 0x43: "f9", 0x44: "f10",
        0x45: "num lock", 0x46: "scroll lock", 0x47: "home",
        0x48: "up", 0x49: "page up", 0x4A: "-", 0x4B: "left",
        0x4C: "clear", 0x4D: "right", 0x4E: "+", 0x4F: "end",
        0x50: "down", 0x51: "page down", 0x52: "insert", 0x53: "delete",
        0x57: "f11", 0x58: "f12",
    }
    try:
        vk = int(str(vk_hex or "0"), 16)
    except Exception:
        vk = 0
    if vk in table:
        return table[vk]
    name = str(fallback_name or "").strip().lower()
    return name or DEFAULT_CALL_KEY["name"].lower()


# =====================================================================
# MEMORY ENGINE — FL 2026 pointer chains, 1:1 with the original tool.
# NO HOOKS: S.A.O.T only reads/writes game memory values (user spec #8).
# =====================================================================
class SAOTMemory:
    def __init__(self):
        self.pm = None
        self.pid = 0
        self.base = 0
        self.module = None
        self.cam0_height_addr = None
        self.zoom_addr = None

    # --- attach ---------------------------------------------------------
    def attach(self, pid, base):
        """Attach to the pid the BRIDGE reported (never a fresh scan)."""
        if not PYMEM_OK:
            return False
        try:
            pm = pymem.Pymem()
            pm.open_process_from_id(int(pid))
        except Exception as e:
            log_line("[MEM] attach failed: %s: %s"
                     % (e.__class__.__name__, e))
            return False
        try:
            module = pymem.process.module_from_name(pm.process_handle,
                                                    PROCESS_NAME)
        except Exception:
            module = None
        self.pm = pm
        self.pid = int(pid)
        self.base = int(base) if base else (
            int(module.lpBaseOfDll) if module else 0)
        self.module = module
        log_line("[MEM] attached pid=%s base=0x%X" % (self.pid, self.base))
        return bool(self.base)

    def close(self):
        try:
            if self.pm is not None:
                self.pm.close_process()
        except Exception:
            pass
        self.pm = None
        self.pid = 0
        self.base = 0
        self.module = None
        self.cam0_height_addr = None
        self.zoom_addr = None

    # --- helpers ----------------------------------------------------------
    @staticmethod
    def _read_longlong(pm, addr):
        return pm.read_longlong(addr)

    def get_ptr(self, b_off, offsets):
        try:
            pm = self.pm
            addr = self._read_longlong(pm, self.base + b_off)
            if addr == 0:
                return 0
            for off in offsets[:-1]:
                addr = self._read_longlong(pm, addr + off)
                if addr == 0:
                    return 0
            return addr + offsets[-1]
        except Exception:
            return 0

    def safe_write(self, pm, address, value, is_float=False):
        try:
            PAGE_EXECUTE_READWRITE = 0x40
            old_protect = ctypes.c_ulong()
            ctypes.windll.kernel32.VirtualProtectEx(
                pm.process_handle, ctypes.c_void_p(address), 4,
                PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect))
            if is_float:
                pm.write_float(address, float(value))
            else:
                pm.write_int(address, int(value))
            ctypes.windll.kernel32.VirtualProtectEx(
                pm.process_handle, ctypes.c_void_p(address), 4,
                old_protect.value, ctypes.byref(old_protect))
            return True
        except Exception:
            return False

    # --- state read (view / distance / plane) -----------------------------
    def read_state(self):
        """Returns (view_idx, dist_slider_or_None, state_idx)."""
        if self.pm is None or not self.base:
            return 5, None, 2
        view_idx = 5
        slider_val = None
        state_idx = 2
        addr1 = self.get_ptr(BASE_OFFSET, POINTER_OFFSETS_1)
        if addr1 != 0:
            try:
                view_idx = int(self.pm.read_int(addr1))
            except Exception:
                view_idx = 5
            if view_idx not in (0, 1, 2, 3, 4):
                view_idx = 5
        addr2 = self.get_ptr(BASE_OFFSET, POINTER_OFFSETS_2)
        if addr2 != 0:
            try:
                real_val2 = self.pm.read_float(addr2)
                s_val = round(real_val2 * 1000.0, 1)
                if 0.0 <= s_val <= 100.0:
                    slider_val = s_val
            except Exception:
                slider_val = None
        addr3 = self.get_ptr(BASE_OFFSET_3, POINTER_OFFSETS_3)
        if addr3 != 0:
            try:
                val3 = self.pm.read_int(addr3)
                state_idx = 1 if val3 == 1 else 0
            except Exception:
                state_idx = 2
        return view_idx, slider_val, state_idx

    # --- writes -----------------------------------------------------------
    def apply_view(self, value):
        """View 1-4 + camera preset chains (FL 2026 paths only)."""
        if self.pm is None or not self.base:
            return False
        pm = self.pm
        try:
            final_address = self.get_ptr(BASE_OFFSET, POINTER_OFFSETS_1)
            if final_address != 0:
                pm.write_int(final_address, int(value))

            if value in VIEW_TABLE:
                rot, new_ptr, height, zoom = VIEW_TABLE[value]

                ptr1 = self._read_longlong(pm, self.base + CAM_ROT_BASE)
                if ptr1 != 0:
                    ptr1 = self._read_longlong(pm, ptr1 + 0x138)
                    if ptr1 != 0:
                        ptr1 = self._read_longlong(pm, ptr1 + 0x20)
                        if ptr1 != 0:
                            ptr1 = self._read_longlong(pm, ptr1 + 0x8)
                            if ptr1 != 0:
                                pm.write_float(ptr1 + 0xC, rot)

                ptr2 = self._read_longlong(pm, self.base + CAM_DIST_BASE)
                if ptr2 != 0:
                    ptr2 = self._read_longlong(pm, ptr2 + 0x138)
                    if ptr2 != 0:
                        ptr2 = self._read_longlong(pm, ptr2 + 0x20)
                        if ptr2 != 0:
                            ptr2 = self._read_longlong(pm, ptr2 + 0x8)
                            if ptr2 != 0:
                                pm.write_float(ptr2 + 0x10, new_ptr)

                if self.cam0_height_addr is None and self.module is not None:
                    try:
                        loc1 = pymem.pattern.pattern_scan_module(
                            pm.process_handle, self.module,
                            re.escape(PATTERN_CAM0_HEIGHT))
                        if loc1:
                            self.cam0_height_addr = loc1 + 3
                    except Exception:
                        self.cam0_height_addr = None

                if self.zoom_addr is None and self.module is not None:
                    try:
                        loc2 = pymem.pattern.pattern_scan_module(
                            pm.process_handle, self.module,
                            re.escape(PATTERN_ZOOM))
                        if loc2:
                            self.zoom_addr = loc2 + 3
                    except Exception:
                        self.zoom_addr = None

                if self.cam0_height_addr:
                    pm.write_float(self.cam0_height_addr, height)
                if self.zoom_addr:
                    pm.write_float(self.zoom_addr, zoom)
            return True
        except Exception as e:
            log_line("[MEM] apply_view failed: %s: %s"
                     % (e.__class__.__name__, e))
            return False

    def apply_distance(self, value_float):
        if self.pm is None or not self.base:
            return False
        try:
            final_address = self.get_ptr(BASE_OFFSET, POINTER_OFFSETS_2)
            if final_address != 0:
                self.safe_write(self.pm, final_address,
                                float(value_float) / 1000.0, is_float=True)
            return True
        except Exception as e:
            log_line("[MEM] apply_distance failed: %s: %s"
                     % (e.__class__.__name__, e))
            return False

    def apply_plane(self, value):
        """value 1 = ON, 0 = OFF (also mirrors the image pointer)."""
        if self.pm is None or not self.base:
            return False
        try:
            final_address = self.get_ptr(BASE_OFFSET_3, POINTER_OFFSETS_3)
            if final_address != 0:
                self.safe_write(self.pm, final_address, int(value),
                                is_float=False)
            final_address_img = self.get_ptr(BASE_OFFSET_3,
                                             POINTER_OFFSETS_IMAGE)
            if final_address_img != 0:
                self.safe_write(self.pm, final_address_img, int(value),
                                is_float=False)
            return True
        except Exception as e:
            log_line("[MEM] apply_plane failed: %s: %s"
                     % (e.__class__.__name__, e))
            return False

    def plane_off(self):
        """Best-effort plane OFF (attach safety + exit)."""
        return self.apply_plane(0)


# =====================================================================
# GUI — the SAME familiar interface as the original tool (view picker,
# plane ON/OFF, distance slider) WITHOUT the settings sidebar and the
# training/tutorial sections (user spec #5). It starts hidden and the
# CALL KEY chosen in MyMods shows/hides it (user spec #3/#5).
# =====================================================================
class SAOTApp:
    def __init__(self, root):
        self.root = root
        self.root.minsize(540, 740)
        self.root.geometry("540x740")
        self.root.configure(fg_color=("#F8FAFC", "#090910"))
        self.root.attributes("-topmost", True)
        self.root.title(EN["title"])

        self.mem = SAOTMemory()
        self.updating_ui = False
        self.is_visible = False            # starts HIDDEN (call key summons)
        self.initial_off_triggered = False
        self.user_wants_plane_on = False

        self.settings = saot_load_settings()
        self._call_hotkey = None
        self._settings_sig = None
        self._last_cfg_poll = 0.0

        self._stop_event = threading.Event()
        self._monitor = None
        # Thread-safe GUI marshalling: worker threads (monitor / memory
        # writes) never touch tkinter directly — they post callables to
        # this queue and the MAIN thread drains it in an after() loop.
        # (root.after() from a secondary thread is not reliable on every
        # Tcl build; the queue is deterministic on all of them.)
        self._ui_q = queue.Queue()

        ctk.set_appearance_mode("Dark")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.build_ui()
        self.apply_texts()

        if HAS_PYWINSTYLES:
            try:
                pywinstyles.apply_style(self.root, "acrylic")
            except Exception:
                pass

        # start hidden — the user summons it with the CALL KEY
        self.root.after(50, self.root.withdraw)
        self.register_call_key()

        # bridge-first monitor thread (game detection is the bridge's job)
        self._monitor = threading.Thread(target=self.monitor_worker,
                                         daemon=True, name="saot-monitor")
        self._monitor.start()

        self.root.after(int(CONFIG_POLL_SEC * 1000), self.poll_config)
        self.root.after(UI_QUEUE_POLL_MS, self._poll_ui_queue)

    def _ui_post(self, fn):
        """Queue a GUI callable from ANY thread (never touches tkinter
        from the worker thread)."""
        self._ui_q.put(fn)

    def _poll_ui_queue(self):
        """MAIN-thread drain of the GUI callback queue."""
        try:
            while True:
                fn = self._ui_q.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        try:
            self.root.after(UI_QUEUE_POLL_MS, self._poll_ui_queue)
        except Exception:
            pass

    # ---------------- UI construction (settings/training REMOVED) --------
    def build_ui(self):
        self.header_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.header_frame.pack(fill="x", pady=(18, 14), padx=24)

        self.title_label = ctk.CTkLabel(self.header_frame, text="")
        self.title_label.pack(side=tk.LEFT, expand=True)

        self.main_content_frame = ctk.CTkFrame(self.root,
                                               fg_color="transparent")
        self.main_content_frame.pack(fill="both", expand=True)

        self.build_main_frames()

        self.status_frame = ctk.CTkFrame(
            self.root, fg_color=("#E2E8F0", "#06060B"), height=42,
            corner_radius=0, border_color=("#CBD5E1", "#1F1F2E"),
            border_width=1)
        self.status_frame.pack(side=tk.BOTTOM, fill="x")
        self.status_label = ctk.CTkLabel(self.status_frame, text="",
                                         text_color=("#475569", "#71717A"))
        self.status_label.pack(side=tk.LEFT, padx=20, pady=8)
        self.footer_label = ctk.CTkLabel(self.status_frame, text="",
                                         text_color=("#64748B", "#52525B"))
        self.footer_label.pack(side=tk.RIGHT, padx=20, pady=8)

    def _update_wrap(self, event, label):
        if event.width > 40:
            label.configure(wraplength=event.width - 40)

    def build_main_frames(self):
        frame_border = ("#CBD5E1", "#27273A")
        frame_bg = ("#FFFFFF", "#121222")

        # frame1 — camera view selection
        self.frame1 = ctk.CTkFrame(self.main_content_frame,
                                   fg_color=frame_bg,
                                   border_color=frame_border,
                                   border_width=1.2, corner_radius=16)
        self.frame1.pack(pady=8, padx=24, fill="x")
        self.label1 = ctk.CTkLabel(self.frame1, text="",
                                   text_color=("#2563EB", "#3B82F6"))
        self.label1.pack(anchor="w", padx=18, pady=(12, 2))
        self.inner_frame1 = ctk.CTkFrame(self.frame1, fg_color="transparent")
        self.inner_frame1.pack(pady=6, padx=18, fill="x")
        self.input_label = ctk.CTkLabel(self.inner_frame1, text="",
                                        text_color=("#475569", "#A1A1AA"))
        self.value_segmented = ctk.CTkSegmentedButton(
            self.inner_frame1, values=[], command=self.on_segmented_change,
            fg_color=("#F1F5F9", "#181826"), selected_color=("#3B82F6", "#2563EB"),
            selected_hover_color=("#2563EB", "#3B82F6"),
            unselected_color=("#F1F5F9", "#181826"),
            unselected_hover_color=("#E2E8F0", "#27273A"),
            text_color=("#1E293B", "#FFFFFF"))
        self.desc_label1 = ctk.CTkLabel(self.frame1, text="",
                                        text_color=("#64748B", "#71717A"),
                                        justify="left")
        self.desc_label1.pack(anchor="w", padx=18, pady=(2, 8), fill="x",
                              expand=True)
        self.custom_hint_label = ctk.CTkLabel(self.frame1, text="",
                                              text_color=("#D97706", "#F59E0B"),
                                              justify="left")
        self.frame1.bind("<Configure>", lambda e: self._update_wrap(
            e, self.desc_label1))
        self.frame1.bind("<Configure>", lambda e: self._update_wrap(
            e, self.custom_hint_label), add="+")

        # frame2 — plane activation
        self.frame2 = ctk.CTkFrame(self.main_content_frame,
                                   fg_color=frame_bg,
                                   border_color=frame_border,
                                   border_width=1.2, corner_radius=16)
        self.frame2.pack(pady=8, padx=24, fill="x")
        self.label2 = ctk.CTkLabel(self.frame2, text="",
                                   text_color=("#9333EA", "#A855F7"))
        self.label2.pack(anchor="w", padx=18, pady=(12, 2))
        self.inner_frame2 = ctk.CTkFrame(self.frame2, fg_color="transparent")
        self.inner_frame2.pack(pady=6, padx=18, fill="x")
        self.toggle_label = ctk.CTkLabel(self.inner_frame2, text="",
                                         text_color=("#475569", "#A1A1AA"))
        self.toggle_segmented = ctk.CTkSegmentedButton(
            self.inner_frame2, values=[],
            command=self.on_toggle_segmented_change,
            fg_color=("#F1F5F9", "#181826"), selected_color=("#8B5CF6", "#7C3AED"),
            selected_hover_color=("#7C3AED", "#8B5CF6"),
            unselected_color=("#F1F5F9", "#181826"),
            unselected_hover_color=("#E2E8F0", "#27273A"),
            text_color=("#1E293B", "#FFFFFF"))
        self.desc_label2 = ctk.CTkLabel(self.frame2, text="",
                                        text_color=("#64748B", "#71717A"),
                                        justify="left")
        self.desc_label2.pack(anchor="w", padx=18, pady=(2, 12), fill="x",
                              expand=True)
        self.frame2.bind("<Configure>", lambda e: self._update_wrap(
            e, self.desc_label2))

        # frame3 — distance slider
        self.frame3 = ctk.CTkFrame(self.main_content_frame,
                                   fg_color=frame_bg,
                                   border_color=frame_border,
                                   border_width=1.2, corner_radius=16)
        self.frame3.pack(pady=8, padx=24, fill="x")
        self.label3 = ctk.CTkLabel(self.frame3, text="",
                                   text_color=("#059669", "#10B981"))
        self.label3.pack(anchor="w", padx=18, pady=(12, 2))
        inner_frame3 = ctk.CTkFrame(self.frame3, fg_color="transparent")
        inner_frame3.pack(pady=6, padx=12, fill="x")
        self.btn_left = ctk.CTkButton(
            inner_frame3, text="\u25C0", width=42, height=34,
            fg_color=("#E2E8F0", "#1F1F2E"), hover_color=("#CBD5E1", "#2D2D44"),
            text_color=("#1E293B", "#E4E4E7"), corner_radius=8,
            command=self.decrease_slider)
        self.btn_left.pack(side=tk.LEFT, padx=6)
        self.slider = ctk.CTkSlider(
            inner_frame3, from_=0.0, to=100.0, number_of_steps=500,
            command=self.on_slider_change,
            fg_color=("#E2E8F0", "#1F1F2E"),
            progress_color=("#10B981", "#10B981"),
            button_color=("#059669", "#10B981"),
            button_hover_color=("#047857", "#34D399"))
        self.slider.set(25.0)
        self.slider.pack(side=tk.LEFT, padx=6, expand=True, fill="x")
        self.btn_right = ctk.CTkButton(
            inner_frame3, text="\u25B6", width=42, height=34,
            fg_color=("#E2E8F0", "#1F1F2E"), hover_color=("#CBD5E1", "#2D2D44"),
            text_color=("#1E293B", "#E4E4E7"), corner_radius=8,
            command=self.increase_slider)
        self.btn_right.pack(side=tk.LEFT, padx=6)
        self.slider_val_label = ctk.CTkLabel(self.frame3, text="",
                                             text_color=("#059669", "#34D399"))
        self.slider_val_label.pack(pady=(2, 2))
        self.desc_label3 = ctk.CTkLabel(self.frame3, text="",
                                        text_color=("#64748B", "#71717A"),
                                        justify="left")
        self.desc_label3.pack(anchor="w", padx=18, pady=(2, 12), fill="x",
                              expand=True)
        self.frame3.bind("<Configure>", lambda e: self._update_wrap(
            e, self.desc_label3))

    def apply_texts(self):
        self.root.title(EN["title"])
        self.title_label.configure(
            text=EN["title"],
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"))
        self.label1.configure(text=EN["view_title"],
                              font=ctk.CTkFont(size=14, weight="bold"))
        self.input_label.configure(text=EN["view_label"],
                                   font=ctk.CTkFont(size=13))
        self.desc_label1.configure(text=EN["view_desc"],
                                   font=ctk.CTkFont(size=11), justify="left")
        self.label2.configure(text=EN["act_title"],
                              font=ctk.CTkFont(size=14, weight="bold"))
        self.toggle_label.configure(text=EN["act_label"],
                                    font=ctk.CTkFont(size=13))
        self.desc_label2.configure(text=EN["act_desc"],
                                   font=ctk.CTkFont(size=11), justify="left")
        self.label3.configure(text=EN["dist_title"],
                              font=ctk.CTkFont(size=14, weight="bold"))
        self.desc_label3.configure(text=EN["dist_desc"],
                                   font=ctk.CTkFont(size=11), justify="left")
        self.input_label.pack(side=tk.LEFT, padx=6)
        self.value_segmented.pack(side=tk.RIGHT, padx=6, fill="x", expand=True)
        self.toggle_label.pack(side=tk.LEFT, padx=6)
        self.toggle_segmented.pack(side=tk.RIGHT, padx=6, fill="x",
                                   expand=True)
        font_seg = ctk.CTkFont(family="Segoe UI", size=11, weight="bold")
        self.value_segmented.configure(values=EN["views"], font=font_seg)
        self.value_segmented.set(EN["views"][5])
        self.toggle_segmented.configure(values=EN["states"], font=font_seg)
        self.toggle_segmented.set(EN["states"][2])
        self.slider_val_label.configure(
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"))
        self.footer_label.configure(text=EN["footer"], font=font_seg)
        self.update_status("ready")
        self.update_slider_label_text()

    # ---------------- status / labels -------------------------------------
    def update_status(self, status_key):
        color = STATUS_COLORS.get(status_key, ("#64748B", "#94A3B8"))
        text = EN.get(status_key, status_key)
        try:
            self.status_label.configure(
                text="%s%s" % (EN["status_prefix"], text),
                text_color=color)
        except Exception:
            pass

    def update_slider_label_text(self):
        try:
            if self.slider.cget("state") == "normal":
                txt = "%s%.1f" % (EN["dist_prefix"], float(self.slider.get()))
            else:
                txt = EN["dist_prefix"] + "N/A"
            self.slider_val_label.configure(text=txt)
        except Exception:
            pass

    def check_and_update_custom_hint(self, index):
        if index == 4:
            self.custom_hint_label.configure(text=EN["custom_hint"],
                                             justify="left")
            self.custom_hint_label.pack(anchor="w", padx=18, pady=(0, 10),
                                        fill="x", expand=True)
        else:
            self.custom_hint_label.pack_forget()

    def set_all_na(self):
        self.value_segmented.set(EN["views"][5])
        self.toggle_segmented.set(EN["states"][2])
        self.toggle_slider_state_by_index(2)
        self.update_slider_label_text()
        self.custom_hint_label.pack_forget()

    def toggle_slider_state_by_index(self, index):
        if index == 1:
            self.slider.configure(state="normal",
                                  progress_color=("#10B981", "#10B981"),
                                  button_color=("#059669", "#10B981"))
            self.btn_left.configure(state="normal",
                                    fg_color=("#E2E8F0", "#1F1F2E"))
            self.btn_right.configure(state="normal",
                                     fg_color=("#E2E8F0", "#1F1F2E"))
        else:
            self.slider.configure(state="disabled",
                                  progress_color=("#CBD5E1", "#2D2D44"),
                                  button_color=("#94A3B8", "#2D2D44"))
            self.btn_left.configure(state="disabled",
                                    fg_color=("#F1F5F9", "#0D0D15"))
            self.btn_right.configure(state="disabled",
                                     fg_color=("#F1F5F9", "#0D0D15"))

    # ---------------- call key (user spec #3/#5) --------------------------
    def register_call_key(self, hotkey_name=None):
        """(Re-)register the call-key hotkey. The key comes from MyMods
        (mods -> S.A.O.T -> apply_key_vk/name in ModsConfig.json)."""
        if not HAS_KEYBOARD:
            return False
        if hotkey_name is None:
            hotkey_name = vk_to_hotkey_name(self.settings.get("vk"),
                                            self.settings.get("name"))
        try:
            if self._call_hotkey is not None:
                keyboard.remove_hotkey(self._call_hotkey)
        except Exception:
            pass
        self._call_hotkey = None
        try:
            self._call_hotkey = keyboard.add_hotkey(
                str(hotkey_name), self.toggle_visibility_from_thread)
            log_line("[HOTKEY] call key registered: %r" % hotkey_name)
            return True
        except Exception as e:
            log_line("[HOTKEY] register failed for %r: %s: %s"
                     % (hotkey_name, e.__class__.__name__, e))
            return False

    def poll_config(self):
        """MyMods may rewrite the call key while this mod runs — re-read
        the settings block every CONFIG_POLL_SEC and re-register on
        change (same live-refresh pattern as the Heat Map settings)."""
        try:
            d = saot_load_settings()
            sig = (str(d.get("vk")), str(d.get("name")))
            if sig != self._settings_sig:
                old = (str(self.settings.get("vk")),
                       str(self.settings.get("name")))
                self._settings_sig = sig
                self.settings = d
                if sig != old:
                    self.register_call_key()
                    log_line("[HOTKEY] call key changed -> %s (%s)"
                             % (d.get("name"), d.get("vk")))
        except Exception:
            pass
        self.root.after(int(CONFIG_POLL_SEC * 1000), self.poll_config)

    def toggle_visibility_from_thread(self):
        self._ui_post(self.toggle_window_state)

    def toggle_window_state(self):
        if self.is_visible:
            self.root.withdraw()
            self.is_visible = False
        else:
            self.root.deiconify()
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.is_visible = True

    # ---------------- monitor thread (bridge-first, user spec #8) ---------
    def monitor_worker(self):
        """Waits for the game through the BRIDGE, attaches to the pid the
        bridge reports, then keeps the GUI values in sync. No process
        scan while a bridge answers; no hooks anywhere."""
        pid, base = saot_wait_for_game(self._stop_event)
        if self._stop_event.is_set() or not pid:
            return
        if not self.mem.attach(pid, base):
            self._ui_post(lambda: self.update_status("mod_not_found"))
            return
        # first attach — force the plane OFF exactly like the original
        # tool did on load (safety: never leave the plane drawing in play)
        if not self.initial_off_triggered:
            try:
                self.mem.plane_off()
            except Exception:
                pass
            self.initial_off_triggered = True
        self._ui_post(lambda: self.update_status("ready"))

        while not self._stop_event.is_set():
            try:
                view_idx, slider_val, state_idx = self.mem.read_state()
            except Exception:
                view_idx, slider_val, state_idx = 5, None, 2
            # auto-OFF: the user did not turn the plane on and the view
            # is not Custom — same protective behaviour as the original
            if state_idx == 1 and not self.user_wants_plane_on \
                    and view_idx != 4:
                try:
                    self.mem.plane_off()
                except Exception:
                    pass
                state_idx = 0
            self._ui_post(lambda v=view_idx, s=slider_val, st=state_idx:
                          self.update_gui_elements(v, s, st))
            self._stop_event.wait(GUI_POLL_MS / 1000.0)

    def update_gui_elements(self, view_idx, slider_val, state_idx):
        self.updating_ui = True
        try:
            views = EN["views"]
            states = EN["states"]
            v_idx = view_idx if view_idx in (0, 1, 2, 3, 4) else 5
            if self.value_segmented.get() != views[v_idx]:
                self.value_segmented.set(views[v_idx])
            if self.toggle_segmented.get() != states[state_idx]:
                self.toggle_segmented.set(states[state_idx])
            self.toggle_slider_state_by_index(state_idx)
            if slider_val is not None:
                if abs(float(self.slider.get()) - float(slider_val)) > 0.01:
                    self.slider.set(float(slider_val))
            self.check_and_update_custom_hint(v_idx)
            self.update_slider_label_text()
        finally:
            self.updating_ui = False

    # ---------------- user actions (identical behaviour) ------------------
    def on_segmented_change(self, choice):
        if self.updating_ui:
            return
        try:
            index = self.value_segmented.cget("values").index(choice)
        except ValueError:
            return
        self.check_and_update_custom_hint(index)
        if index == 5:
            return
        threading.Thread(target=self._write_view, args=(index,),
                         daemon=True).start()

    def _write_view(self, index):
        ok = self.mem.apply_view(index)
        self._ui_post(lambda: self.update_status(
            "view_updated" if ok else "err_view"))

    def on_slider_change(self, val):
        if self.updating_ui:
            return
        self.update_slider_label_text()
        threading.Thread(target=self._write_distance, args=(float(val),),
                         daemon=True).start()

    def _write_distance(self, value_float):
        ok = self.mem.apply_distance(value_float)
        self._ui_post(lambda: self.update_status(
            "dist_updated" if ok else "err_dist"))

    def on_toggle_segmented_change(self, choice):
        if self.updating_ui:
            return
        try:
            index = self.toggle_segmented.cget("values").index(choice)
        except ValueError:
            return
        if index == 2:
            return
        self.user_wants_plane_on = (index == 1)
        self.toggle_slider_state_by_index(index)
        threading.Thread(target=self._write_plane, args=(index,),
                         daemon=True).start()

    def _write_plane(self, index):
        ok = self.mem.apply_plane(1 if index == 1 else 0)
        self._ui_post(lambda: self.update_status(
            "act_toggled" if ok else "err_act"))

    def decrease_slider(self):
        if self.slider.cget("state") == "disabled":
            return
        current = float(self.slider.get())
        if current > 0.0:
            new_val = max(0.0, current - 0.2)
            self.slider.set(new_val)
            self.on_slider_change(new_val)

    def increase_slider(self):
        if self.slider.cget("state") == "disabled":
            return
        current = float(self.slider.get())
        if current < 100.0:
            new_val = min(100.0, current + 0.2)
            self.slider.set(new_val)
            self.on_slider_change(new_val)

    # ---------------- shutdown ---------------------------------------------
    def on_closing(self):
        try:
            self._stop_event.set()
            self.mem.plane_off()          # best-effort plane OFF on exit
        except Exception:
            pass
        try:
            if self._call_hotkey is not None and HAS_KEYBOARD:
                keyboard.remove_hotkey(self._call_hotkey)
        except Exception:
            pass
        try:
            self.mem.close()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass


# =====================================================================
# SELFTEST — headless-safe runtime checks (GUI-free; the GUI itself is
# exercised by the suite's Xvfb test).
# =====================================================================
def _selftest():                                  # pragma: no cover
    fails = []

    def check(name, cond):
        print(("PASS" if cond else "FAIL") + " | " + name)
        if not cond:
            fails.append(name)

    check("customtkinter importable", HAS_CTK)
    check("pymem importable", PYMEM_OK)
    check("single game constant", PROCESS_NAME == "FL_2026.exe")
    check("no multi-game table", ("GAME_" + "PROCESSES") not in globals())
    check("no PES17 pointers", not any(k.startswith("PES" + "17")
                                       for k in globals()))
    check("no admin self-relaunch",
          ("shell" + "32") not in open(__file__, encoding="utf-8").read())
    check("no hook methods on client",
          not any(hasattr(BridgeClient, m) for m in
                  ("hook_" + "request", "hook_" + "release",
                   "hook_" + "reset_request", "hook_" + "status")))
    check("client speaks game_status", hasattr(BridgeClient, "game_status"))

    d = saot_load_settings()
    check("settings have a usable call key",
          int(str(d.get("vk") or "0"), 16) > 0)
    check("settings English name", bool(str(d.get("name") or "").strip()))

    try:
        vk_to_hotkey_name("0x70", "F1") == "f1"
        check("vk mapping F1", vk_to_hotkey_name("0x70", "F1") == "f1")
        check("vk mapping T", vk_to_hotkey_name("0x54", "T") == "t")
        check("vk mapping fallback",
              vk_to_hotkey_name("0xFF", "F9") == "f9")
    except Exception as e:
        check("vk mapping raised: %s" % e, False)

    mem = SAOTMemory()
    check("engine starts detached", mem.pm is None and mem.base == 0)
    check("engine refuses writes while detached",
          mem.apply_plane(1) is False and mem.plane_off() is False)
    st = mem.read_state()
    check("detached read is N/A state", tuple(st) == (5, None, 2))

    cli = BridgeClient(ipc_file="/nonexistent/bridge_ipc.json")
    check("client without config unavailable", cli.available() is False)
    check("client ping without config is None", cli.ping() is None)

    texts = " ".join(str(v) for v in EN.values())
    for banned in ("\u0641\u0627\u0631\u0633\u06cc",
                   "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
                   "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
                   "\ud55c\uad6d\uc5b4"):
        check("no banned language string (%d chars)" % len(banned),
              banned not in texts)
    # whole-file language audit: the ONLY non-ASCII characters allowed in
    # this source are typography (dashes/quotes) — no CJK/Arabic/Cyrillic/
    # Hangul text may exist anywhere in the code (user spec #4).
    src_chars = set(open(__file__, encoding="utf-8").read())
    non_ascii = {c for c in src_chars if ord(c) > 0x7E}
    allowed_non_ascii = set("\u2014\u2019\u201c\u201d\u00b7\u2022\u2192"
                            "\u2190\u26bd\U0001F4A1\u25c0\u25b6\u00e9")
    check("source is ASCII/English-only",
          non_ascii <= allowed_non_ascii)

    print("SELFTEST SUMMARY: %d failed" % len(fails))
    return 0 if not fails else 1


def main():
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    if not HAS_CTK:
        print("customtkinter is required for the S.A.O.T GUI "
              "(pip install customtkinter)")
        sys.exit(3)
    root = ctk.CTk()
    app = SAOTApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
