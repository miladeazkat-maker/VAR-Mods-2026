# -*- coding: utf-8 -*-
# [PROJECT RULE — DO NOT REMOVE] ENGLISH ONLY: this project must NEVER contain any Persian/Farsi text (UI strings, comments, docs).
# =============================================================================
#  RefereeView.py — BACKEND of the "Referee View" mod (no GUI)
#  Lifecycle is owned by the mid end (ModBridge.py):
#    bind(api) -> start() -> on_connected() -> [toggle_request(vk) per user key]
#             -> on_disconnected() -> stop()
#
#  BridgeAPI surface used here:
#     api.read_int / read_longlong / read_float / read_bytes
#     api.write_float / write_bytes
#     api.apply_patch(addr) / api.revert_patch(addr)
#     api.release_ball_hook(site)
#     api.request_camera_control() / api.release_camera_control()
#     api.status(text, color) / api.log(text)
#     api.overlay_show() / api.overlay_hide()
# ==============================================================================

import math
import struct
import threading
import time

PROCESS_NAME = "FL_2026.exe"

# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
STATE_STATIC_OFF = 0x372D148
STATE_REPLAY     = 131
STATE_PLAYING    = 128
STATE_CUTSCENE   = 138
AUX_PTR_OFFSET   = 0x037F4820
AUX_PTR_DISP     = 0xA20
AUX_REPLAY_VAL   = 15
STATE_DEBOUNCE   = 15

PATCH_LNG_A_OFF  = 0x217A379
PATCH_LNG_B_OFF  = 0x217A3EE
PATCH_MISC_OFF   = 0x217A293
ROT_MAX_OFF      = 0x2179F91
ROT_MIN_OFF      = 0x2179F9B
HEIGHT_STATIC_OFF = 0x259BDD8
ZOOM_OFF         = 0x217A4BA

BALL_HOOK_OFF    = 0x176A3A2
ORIG_HOOK4_BALL  = b'\x0F\x29\x80\x50\x04\x00\x00'

LNG_CHAIN = [0x37F4A08, 0x8, 0x10, 0x8, 0x10]
LAT_CHAIN = [0x037F4A08, 0x8, 0x10, 0x8, 0x18]
HOR_CHAIN = [0x037F4A08, 0x8, 0x10, 0x0, 0xC]
VER_CHAIN = [0x037F4A08, 0x8, 0x10, 0x0, 0x8]

CAM4_CHAIN   = [0x037F0AC8, 0x18, 0x140, 0x418, 0x48, 0x5FC]
CAM4_LOCK_VAL = 0x03
CAM4_SETTLE_DELAY_MS = 80

POINTER_SRC_1 = 0x036F3DC8
OFFSET_SRC_2  = 0xD20
OFFSET_SRC_3  = 0x5D4

T_OFF_X = -0.3
T_OFF_Z = 0.0
T_OFF_Y = 0.2
T_CAM_SMOOTH_TIME = 0.10
T_SMOOTH_TIME     = 0.60
REF_ZOOM = 1.0

def _smooth_damp(current, target, vel, smooth_time, dt):
    smooth_time = max(0.0001, smooth_time)
    omega = 2.0 / smooth_time
    x = omega * dt
    exp = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
    change = current - target
    temp = (vel + omega * change) * dt
    vel = (vel - omega * temp) * exp
    output = target + (change + temp) * exp
    if (target - current > 0.0) == (output > target):
        output = target
        vel = 0.0
    return output, vel

class RefereeBackend:
    """
      → on_disconnected() → stop()
    """

    META = {
        "name": "Referee View",
        "version": "2.0.0",
        "video_file": "RefereeOverlay.webm",
        "required_files": ["RefereeOverlay.webm"],
        "description": "Body-cam referee POV camera during replays (FL_2026.exe)",
    }

    def __init__(self):
        self.api = None
        self.settings = {}
        self.mod_id = "Referee View"
        self.key_name = "T"

        self.connected_ok = False
        self.master = False
        self.active = False
        self.just_enabled = False

        self.patch_ids = []
        self.ball_buffer = None
        self.ball_hooked = False

        self.cam4_lock = False
        self.cam4_saved = None

        self.backup_floats = None

        self.current_cam_x = 0.0; self.target_cam_x = 0.0
        self.current_cam_z = 0.0; self.target_cam_z = 0.0
        self.current_cam_y = 0.0; self.target_cam_y = 0.0
        self.current_ball_x = 0.0; self.target_ball_x = 0.0
        self.current_ball_z = 0.0; self.target_ball_z = 0.0
        self.current_ball_y = 0.0; self.target_ball_y = 0.0
        self.cur_yaw = 0.0; self.cur_pitch = 0.0
        self.tgt_vel_x = 0.0; self.tgt_vel_z = 0.0; self.tgt_vel_y = 0.0
        self.cam_vel_x = 0.0; self.cam_vel_z = 0.0; self.cam_vel_y = 0.0
        self._last_loop_time = 0.0

        self.current_state_str = "STOP"
        self.candidate_state_str = "STOP"
        self.state_stable_count = 0

        self.running = False
        self.tlock = threading.RLock()
        self._last_status = ("", "")
        self._threads = []

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def bind(self, api, settings):
        self.api = api
        self.settings = settings or {}
        self.key_name = str(self.settings.get("apply_key_name", "T"))
        self.mod_id = "Referee View"
        self.log("backend bound — settings loaded from ModsConfig.json")

    def start(self):
        if self.running:
            return
        self.running = True
        t1 = threading.Thread(target=self.state_loop, daemon=True, name="RV-State")
        t2 = threading.Thread(target=self.memory_loop, daemon=True, name="RV-Memory")
        self._threads = [t1, t2]
        t1.start()
        t2.start()
        self.log("backend threads started")

    def stop(self):
        self.running = False
        try:
            self._deactivate()
        except Exception:
            pass

    def ui_state(self):
        if self.active:
            return ("ACTIVE", "#2ecc71")
        if self.master:
            return ("ARMED — waiting for Replay", "#f39c12")
        return ("READY — press the apply key in Replay", "#93c5fd")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def on_connected(self):
        try:
            base = self.api.base()

            self.patch_ids = []
            for off, size, note in [
                (PATCH_LNG_A_OFF, 6, "lng A NOP"),
                (PATCH_LNG_B_OFF, 6, "lng B NOP"),
                (PATCH_MISC_OFF,  5, "misc NOP"),
                (ROT_MAX_OFF,     8, "rotation max NOP"),
                (ROT_MIN_OFF,     8, "rotation min NOP"),
            ]:
                pid = self.api.register_patch(base + off, b'\x90' * size, note)
                if pid is None:
                    self.status(f"patch rejected at 0x{off:X} (conflict) — continuing", "#e67e22")
                else:
                    self.patch_ids.append(pid)

            zpid = self.api.register_patch(base + ZOOM_OFF, struct.pack('f', float(REF_ZOOM)), "zoom var")
            if zpid is not None:
                self.patch_ids.append(zpid)

            self.connected_ok = True
            self.status("Referee View ready — press the apply key inside Replay", "#93c5fd")
        except Exception as e:
            self.log(f"on_connected failed: {e.__class__.__name__}: {e}")

    def on_disconnected(self):
        self.connected_ok = False
        self.active = False
        self.master = False
        self.patch_ids = []
        self.ball_buffer = None
        self.ball_hooked = False
        self.backup_floats = None
        self.cam4_lock = False
        self.cam4_saved = None
        self._last_status = ("", "")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def toggle_request(self, vk=None):
        with self.tlock:
            if not (self.api and self.api.connected):
                self.status("Bridge is not connected to FL_2026.exe yet", "#e67e22")
                return
            if self.master:
                self.master = False
                self._deactivate()
                self.status("Referee View OFF — camera restored", "#3498db")
            else:
                raw = self._raw_state()
                if raw == "REPLAY":
                    self.master = True
                    self._activate()
                    self.status("Referee View ON — you are in the referee's view", "#2ecc71")
                else:
                    self.status(f'You are not in Replay mode — enter Replay, then press "{self.key_name}"', "#e67e22")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _ptr(self, offsets):
        addr = self.api.read_longlong(self.api.base() + offsets[0])
        for off in offsets[1:-1]:
            addr = self.api.read_longlong(addr + off)
        return addr + offsets[-1]

    def _raw_state(self):
        status = self.api.read_int(self.api.base() + STATE_STATIC_OFF)
        aux_val = -1
        try:
            aux_addr = self._ptr([AUX_PTR_OFFSET, AUX_PTR_DISP])
            aux_val = self.api.read_int(aux_addr) if aux_addr else -1
        except Exception:
            aux_val = -1
        if status == STATE_REPLAY or aux_val == AUX_REPLAY_VAL:
            return "REPLAY"
        if status == STATE_PLAYING:
            return "PLAYING"
        if status == STATE_CUTSCENE:
            return "CUTSCENE"
        return "STOP"

    def state_loop(self):
        while self.running:
            if not (self.api and self.api.connected and self.connected_ok):
                time.sleep(1.0)
                continue
            try:
                raw = self._raw_state()
            except Exception:
                time.sleep(1.0)
                continue

            if raw != self.current_state_str:
                if raw == self.candidate_state_str:
                    self.state_stable_count += 1
                else:
                    self.candidate_state_str = raw
                    self.state_stable_count = 1
                if self.state_stable_count >= STATE_DEBOUNCE:
                    self.current_state_str = self.candidate_state_str
                    self.state_stable_count = 0
            else:
                self.state_stable_count = 0

            replay_ok = (self.current_state_str == "REPLAY")

            with self.tlock:
                if not self.master:
                    if self.active:
                        self._deactivate()
                    self.status(f'Ready — press "{self.key_name}" inside Replay mode', "#3498db")
                else:
                    if replay_ok:
                        if not self.active:
                            self._activate()
                        self.status("ACTIVE & INJECTING — referee view", "#2ecc71")
                    else:
                        if self.active:
                            self._deactivate()
                        self.status("Out of Replay — waiting for Replay ...", "#e67e22")

            time.sleep(0.015)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _activate(self):
        if self.active:
            return
        if not self.api.request_camera_control():
            self.status("Camera is owned by another mod — activation denied", "#e67e22")
            self.master = False
            return
        if not self.ball_hooked:
            base = self.api.base()
            self.ball_buffer = self.api.request_ball_hook(
                base + BALL_HOOK_OFF, ORIG_HOOK4_BALL, 2)
            if self.ball_buffer is None:
                self.status("ball hook failed — ball tracking disabled", "#e67e22")
            else:
                self.ball_hooked = True

        self._capture_camera_floats()
        self._cam4_capture_and_lock()
        if not self._cam4_hard_barrier():
            self._cam4_restore()
            try:
                self.api.release_camera_control()
            except Exception:
                pass
            self.master = False
            self.status("Camera 4 (03) lock failed — activation denied", "#e67e22")
            return
        for pid in self.patch_ids:
            self.api.apply_patch(pid)
        self.active = True
        self.just_enabled = True
        self.api.overlay_show()
        self.api.log("referee view ACTIVATED (patches applied by bridge)")

    def _deactivate(self):
        if not self.active:
            return
        self.active = False
        self._cam4_restore()
        if self.ball_hooked:
            try:
                self.api.release_ball_hook(self.api.base() + BALL_HOOK_OFF)
            except Exception:
                pass
            self.ball_hooked = False
            self.ball_buffer = None
        for pid in self.patch_ids:
            try:
                self.api.revert_patch(pid)
            except Exception:
                pass
        self._restore_camera_floats()
        try:
            self.api.release_camera_control()
        except Exception:
            pass
        self.api.overlay_hide()
        self.api.log("referee view DEACTIVATED (state restored by bridge)")

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _capture_camera_floats(self):
        if self.backup_floats is not None:
            return
        try:
            base = self.api.base()
            self.backup_floats = {
                "base": self.api.read_float(base + HEIGHT_STATIC_OFF),
                "lng": self.api.read_float(self._ptr(LNG_CHAIN)),
                "lat": self.api.read_float(self._ptr(LAT_CHAIN)),
                "hor_rot": self.api.read_float(self._ptr(HOR_CHAIN)),
                "ver_rot": self.api.read_float(self._ptr(VER_CHAIN)),
            }
        except Exception:
            self.backup_floats = {}

    def _restore_camera_floats(self):
        if not self.backup_floats:
            return
        try:
            base = self.api.base()
            f = self.backup_floats
            try:
                if f.get("base") is not None:
                    self.api.write_float(base + HEIGHT_STATIC_OFF, f["base"])
                if f.get("lng") is not None:
                    self.api.write_float(self._ptr(LNG_CHAIN), f["lng"])
                if f.get("lat") is not None:
                    self.api.write_float(self._ptr(LAT_CHAIN), f["lat"])
                if f.get("hor_rot") is not None:
                    self.api.write_float(self._ptr(HOR_CHAIN), f["hor_rot"])
                if f.get("ver_rot") is not None:
                    self.api.write_float(self._ptr(VER_CHAIN), f["ver_rot"])
            except Exception:
                pass
        finally:
            self.backup_floats = None

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def _cam4_addr(self):
        return self._ptr(CAM4_CHAIN)

    def _cam4_capture_and_lock(self):
        self.cam4_saved = None
        try:
            a = self._cam4_addr()
            if a:
                self.cam4_saved = self.api.read_bytes(a, 1)[0]
                self.api.write_bytes(a, bytes([CAM4_LOCK_VAL]))
        except Exception:
            self.cam4_saved = None
        self.cam4_lock = True

    def _cam4_enforce(self):
        try:
            a = self._cam4_addr()
            if a and self.api.read_bytes(a, 1)[0] != CAM4_LOCK_VAL:
                self.api.write_bytes(a, bytes([CAM4_LOCK_VAL]))
        except Exception:
            pass

    def _cam4_restore(self):
        self.cam4_lock = False
        try:
            a = self._cam4_addr()
            if a and self.cam4_saved is not None:
                self.api.write_bytes(a, bytes([self.cam4_saved]))
        except Exception:
            pass
        self.cam4_saved = None

    def _cam4_hard_barrier(self, settle_ms=None):
        ms = CAM4_SETTLE_DELAY_MS if settle_ms is None else settle_ms
        deadline = time.time() + ms / 1000.0
        while time.time() < deadline:
            time.sleep(0.01)
        try:
            a = self._cam4_addr()
            return bool(a) and self.api.read_bytes(a, 1)[0] == CAM4_LOCK_VAL
        except Exception:
            return False

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def memory_loop(self):
        while self.running:
            if self.api and self.api.connected and self.active:
                snap_now = False
                if self.just_enabled:
                    snap_now = True
                    self.just_enabled = False

                _now = time.perf_counter()
                _dt = (_now - self._last_loop_time) if self._last_loop_time > 0.0 else 0.004
                self._last_loop_time = _now
                _dt = min(max(_dt, 0.0005), 0.05)
                try:
                    if self.cam4_lock:
                        self._cam4_enforce()

                    base = self.api.base()
                    ptr1 = self.api.read_longlong(base + POINTER_SRC_1)
                    ptr2 = self.api.read_longlong(ptr1 + OFFSET_SRC_2)
                    source_addr = ptr2 + OFFSET_SRC_3

                    self.target_cam_x = self.api.read_float(source_addr) + T_OFF_X
                    self.target_cam_z = self.api.read_float(source_addr + 0x4) + T_OFF_Z
                    self.target_cam_y = self.api.read_float(source_addr + 0x8) + T_OFF_Y

                    if snap_now:
                        self.current_cam_x = self.target_cam_x
                        self.current_cam_z = self.target_cam_z
                        self.current_cam_y = self.target_cam_y
                        self.cam_vel_x = 0.0; self.cam_vel_z = 0.0; self.cam_vel_y = 0.0
                    else:
                        self.current_cam_x, self.cam_vel_x = _smooth_damp(
                            self.current_cam_x, self.target_cam_x, self.cam_vel_x, T_CAM_SMOOTH_TIME, _dt)
                        self.current_cam_z, self.cam_vel_z = _smooth_damp(
                            self.current_cam_z, self.target_cam_z, self.cam_vel_z, T_CAM_SMOOTH_TIME, _dt)
                        self.current_cam_y, self.cam_vel_y = _smooth_damp(
                            self.current_cam_y, self.target_cam_y, self.cam_vel_y, T_CAM_SMOOTH_TIME, _dt)

                    if self.ball_buffer:
                        buf = self.ball_buffer
                        self.target_ball_x = self.api.read_float(buf)        # x
                        self.target_ball_z = self.api.read_float(buf + 0x4)
                        self.target_ball_y = self.api.read_float(buf + 0x8)

                        if snap_now:
                            self.current_ball_x = self.target_ball_x
                            self.current_ball_z = self.target_ball_z
                            self.current_ball_y = self.target_ball_y
                            self.tgt_vel_x = 0.0; self.tgt_vel_z = 0.0; self.tgt_vel_y = 0.0
                        else:
                            self.current_ball_x, self.tgt_vel_x = _smooth_damp(
                                self.current_ball_x, self.target_ball_x, self.tgt_vel_x, T_SMOOTH_TIME, _dt)
                            self.current_ball_z, self.tgt_vel_z = _smooth_damp(
                                self.current_ball_z, self.target_ball_z, self.tgt_vel_z, T_SMOOTH_TIME, _dt)
                            self.current_ball_y, self.tgt_vel_y = _smooth_damp(
                                self.current_ball_y, self.target_ball_y, self.tgt_vel_y, T_SMOOTH_TIME, _dt)

                        dx = self.current_ball_x - self.current_cam_x
                        dh = self.current_ball_z - self.current_cam_z
                        dd = self.current_ball_y - self.current_cam_y
                        hd = math.sqrt(dx * dx + dd * dd)
                        t_yaw = math.degrees(math.atan2(dx, dd)) % 360.0
                        t_pitch = math.degrees(math.atan2(-dh, hd)) % 360.0
                        self.cur_yaw, self.cur_pitch = t_yaw, t_pitch

                    lng_addr = self._ptr(LNG_CHAIN)
                    if lng_addr:
                        self.api.write_float(lng_addr, self.current_cam_x)
                    lat_addr = self._ptr(LAT_CHAIN)
                    if lat_addr:
                        self.api.write_float(lat_addr, self.current_cam_y)
                    hor_addr = self._ptr(HOR_CHAIN)
                    if hor_addr:
                        self.api.write_float(hor_addr, self.cur_yaw)         # hor_rot
                    ver_addr = self._ptr(VER_CHAIN)
                    if ver_addr:
                        self.api.write_float(ver_addr, self.cur_pitch)       # vert_rot

                    self.api.write_float(base + HEIGHT_STATIC_OFF, self.current_cam_z)
                    self.api.write_float(base + ZOOM_OFF, REF_ZOOM)
                except Exception:
                    pass
            time.sleep(0.002)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def status(self, text, color="#93c5fd"):
        key = (text, color)
        if key != self._last_status:
            self._last_status = key
            try:
                self.api.status(text, color)
            except Exception:
                pass

    def log(self, msg):
        try:
            self.api.log(msg)
        except Exception:
            pass
