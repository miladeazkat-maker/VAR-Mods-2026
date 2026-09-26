# -*- coding: utf-8 -*-
# [PROJECT RULE — DO NOT REMOVE] ENGLISH ONLY: this project must NEVER contain any Persian/Farsi text (UI strings, comments, docs).
# =============================================================================
#  MyMods.py — FRONTEND (layer 1 of 3)
#  Main mods UI | PES \ eFOOTBALL MODS BY MILAD — targets FL_2026.exe ONLY
#
#  Responsibilities of this layer:
#    1) Show each mod's settings to the user (Referee View + Goal Line Technology)
#    2) Persist every setting into ModsConfig.json (next to this file)
#    3) Launch layer 2 (ModBridge.py = mid end) as Administrator
#       NOTE: the APPLY button never starts the game; it only saves the
#       settings and runs the mid end as admin.
# ==============================================================================

import sys
import os
import re
import shutil
import json
import time
import ctypes
import random
import math
import subprocess
import threading
import urllib.request

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Same field bug reported on the Heat Map backend: when stdout/stderr is
# a FILE or PIPE (launched from a shell with redirected output, bridge
# logs) Python uses the legacy ANSI 'charmap' codec (cp1252), and ONE
# print of a non-Latin-1 string (Arabic/Persian mod or team name read
# from the user's config) raises UnicodeEncodeError that can kill the
# printing thread. Hardened: console -> UTF-8 codepage, streams ->
# utf-8 + errors='replace', and a wrapper so a failing write degrades
# to sanitized ASCII, never raises.
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

# -------------------------------------------------------------
# Run with Administrator privileges while maintaining APP_DIR
# -------------------------------------------------------------
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.abspath(os.path.dirname(sys.executable))
else:
    APP_DIR = os.path.abspath(os.path.dirname(sys.argv[0]))
os.chdir(APP_DIR)

if "--package-smoke" in sys.argv:
    try:
        from PyQt6.QtCore import QT_VERSION_STR
        from PyQt6.QtMultimedia import QMediaPlayer
        sys.exit(0)
    except Exception as _exc:
        raise RuntimeError(f"Standalone MyMods package smoke test failed: {_exc}")

def check_and_elevate_admin():
    if sys.platform == "win32":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            is_admin = False
        if not is_admin:
            if getattr(sys, 'frozen', False):
                exe = sys.executable
                params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
            else:
                exe = sys.executable
                params = f'"{os.path.abspath(sys.argv[0])}" ' + " ".join([f'"{a}"' for a in sys.argv[1:]])
            res = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, APP_DIR, 1)
            if int(res) > 32:
                sys.exit(0)

if "--package-smoke" not in sys.argv:
    check_and_elevate_admin()

# -------------------------------------------------------------
# PyQt Widgets and GUI Imports (Compatible with PyQt6 and PyQt5)
# -------------------------------------------------------------
try:
    from PyQt6.QtCore import (
        Qt, QObject, QRect, QRectF, QPointF, QPoint, QSize, QUrl, pyqtProperty,
        QPropertyAnimation, QVariantAnimation, QEasingCurve, pyqtSignal, QTimer,
        QEventLoop, QEvent, QLineF
    )
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QSlider, QComboBox, QFrame, QButtonGroup,
        QGraphicsDropShadowEffect, QGridLayout,
        QFileDialog, QSizePolicy, QStackedWidget, QLineEdit, QScrollArea,
        QTabWidget, QColorDialog
    )
    from PyQt6.QtGui import (
        QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient,
        QConicalGradient, QFont, QPixmap, QDesktopServices, QPolygonF, QPainterPath,
        QImage
    )
    IS_PYQT6 = True
except ImportError:
    from PyQt5.QtCore import (
        Qt, QObject, QRect, QRectF, QPointF, QPoint, QSize, QUrl, pyqtProperty,
        QPropertyAnimation, QVariantAnimation, QEasingCurve, pyqtSignal, QTimer,
        QEventLoop, QEvent, QLineF
    )
    from PyQt5.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QSlider, QComboBox, QFrame, QButtonGroup,
        QGraphicsDropShadowEffect, QGridLayout,
        QFileDialog, QSizePolicy, QStackedWidget, QLineEdit, QScrollArea,
        QTabWidget, QColorDialog
    )
    from PyQt5.QtGui import (
        QColor, QPainter, QBrush, QPen, QLinearGradient, QRadialGradient,
        QConicalGradient, QFont, QPixmap, QDesktopServices, QPolygonF, QPainterPath,
        QImage
    )
    IS_PYQT6 = False

# -------------------------------------------------------------
# Video playback background (Background/Back.mp4).
#   * QMediaPlayer / QVideoSink live in the OPTIONAL PyQt6-Multimedia
#     package ("pip install PyQt6-Multimedia"). When it is missing —
#     or when Background/Back.mp4 does not exist — the app silently
#     falls back to the classic painted gradient background.
#   * Frames are decoded by the OS media stack (hardware-accelerated
#     on Windows) and painted with QPainter — deliberately NO raw
#     OpenGL: Qt 6.10+ removed QOpenGLFunctions, which made the old
#     GL-shader renderer fail silently on current PyQt6 builds.
# -------------------------------------------------------------
QMediaPlayer = None
QVideoSink = None
QVideoFrame = None
QVideoFrameFormat = None
HAS_VIDEO_PLAYBACK = False
if IS_PYQT6:
    try:
        from PyQt6.QtMultimedia import (
            QMediaPlayer, QVideoSink, QVideoFrame, QVideoFrameFormat
        )
        from PyQt6.QtGui import QImage
        HAS_VIDEO_PLAYBACK = True
    except ImportError:
        pass

SMOOTH_TRANSFORM = Qt.TransformationMode.SmoothTransformation if IS_PYQT6 else Qt.SmoothTransformation
IGNORE_ASPECT = Qt.AspectRatioMode.IgnoreAspectRatio if IS_PYQT6 else Qt.IgnoreAspectRatio

def get_global_pos(event):
    if hasattr(event, "globalPosition"):
        return event.globalPosition().toPoint()
    return event.globalPos()

def get_settings_dat_path():
    user_home = os.path.expanduser('~')
    candidates = [
        os.path.join(user_home, 'Documents', 'KONAMI', 'eFootball PES 2021 SEASON UPDATE', 'settings.dat'),
        os.path.join(user_home, 'OneDrive', 'Documents', 'KONAMI', 'eFootball PES 2021 SEASON UPDATE', 'settings.dat')
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return candidates[0]

def get_key_display_name(vk_code):
    vk_code = int(vk_code) & 0xFF
    if sys.platform != "win32":
        return VK_FALLBACK_NAMES.get(vk_code, f"VK 0x{vk_code:02X}")
    try:
        user32 = ctypes.windll.user32
        MAPVK_VK_TO_VSC = 0
        sc = user32.MapVirtualKeyW(int(vk_code), MAPVK_VK_TO_VSC)
        if not sc:
            return VK_FALLBACK_NAMES.get(vk_code, f"VK 0x{vk_code:02X}")
        lparam = (sc & 0xFF) << 16
        if vk_code in (0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
                       0x2D, 0x2E, 0x6F, 0x2C):
            lparam |= 0x01000000
        buf = ctypes.create_unicode_buffer(64)
        n = user32.GetKeyNameTextW(lparam, buf, 64)
        if n > 0 and buf.value.strip():
            return buf.value
        return VK_FALLBACK_NAMES.get(vk_code, f"VK 0x{vk_code:02X}")
    except Exception:
        return VK_FALLBACK_NAMES.get(vk_code, f"VK 0x{vk_code:02X}")

VK_FALLBACK_NAMES = {
    0x08: "BACKSPACE", 0x09: "TAB", 0x0D: "ENTER", 0x13: "PAUSE", 0x14: "CAPS LOCK",
    0x1B: "ESC", 0x20: "SPACE", 0x21: "PAGE UP", 0x22: "PAGE DOWN", 0x23: "END",
    0x24: "HOME", 0x25: "LEFT ARROW", 0x26: "UP ARROW", 0x27: "RIGHT ARROW", 0x28: "DOWN ARROW",
    0x2D: "INSERT", 0x2E: "DELETE", 0x5B: "LEFT WIN", 0x5C: "RIGHT WIN", 0x6A: "NUM *",
    0x6B: "NUM +", 0x6D: "NUM -", 0x6E: "NUM .", 0x6F: "NUM /",
    0xBA: ";", 0xBB: "=", 0xBC: ",", 0xBD: "-", 0xBE: ".", 0xBF: "/", 0xC0: "`",
    0xDB: "[", 0xDC: "\\", 0xDD: "]", 0xDE: "'",
}
for _i in range(10):
    VK_FALLBACK_NAMES[0x30 + _i] = str(_i)
    VK_FALLBACK_NAMES[0x60 + _i] = f"NUM {_i}"
for _i in range(26):
    VK_FALLBACK_NAMES[0x41 + _i] = chr(ord("A") + _i)
for _i in range(24):
    VK_FALLBACK_NAMES[0x70 + _i] = f"F{_i + 1}"

def lerp_color(c1, c2, t):
    r = int(c1.red() + (c2.red() - c1.red()) * t)
    g = int(c1.green() + (c2.green() - c1.green()) * t)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * t)
    a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
    return QColor(r, g, b, a)

# -------------------------------------------------------------
# 1. Themes Definition (11 Unique Deep-Dark Cyber Palettes)
# -------------------------------------------------------------
class CyberTheme:
    def __init__(self, name, primary, secondary, accent, bg_dark, glow_color):
        self.name = name
        self.primary = QColor(primary)
        self.secondary = QColor(secondary)
        self.accent = QColor(accent)
        self.bg_dark = [QColor(c) for c in bg_dark]
        self.glow_color = QColor(glow_color)

    def clone(self):
        return CyberTheme(
            self.name,
            self.primary.name(),
            self.secondary.name(),
            self.accent.name(),
            [c.name() for c in self.bg_dark],
            self.glow_color.name()
        )

    def interpolate(self, target, t):
        p = lerp_color(self.primary, target.primary, t)
        s = lerp_color(self.secondary, target.secondary, t)
        a = lerp_color(self.accent, target.accent, t)
        bg = [lerp_color(c1, c2, t) for c1, c2 in zip(self.bg_dark, target.bg_dark)]
        gl = lerp_color(self.glow_color, target.glow_color, t)
        return CyberTheme(target.name, p.name(), s.name(), a.name(), [c.name() for c in bg], gl.name())

THEMES = {
    "S.A.O.T": CyberTheme(
        "Cyber Cyan",
        "#00f0ff", "#0066ff", "#7dd3fc",
        ["#010612", "#030e22", "#041430", "#020917"],
        "#00f0ff"
    ),
    "Goal Line Technology": CyberTheme(
        "Matrix Emerald",
        "#00ff88", "#008f4c", "#86efac",
        ["#010e06", "#021c0e", "#032b16", "#010c05"],
        "#00ff88"
    ),
    "Referee View": CyberTheme(
        "Amber Gold",
        "#ffb700", "#d97706", "#fde68a",
        ["#120a01", "#211402", "#301e04", "#0d0700"],
        "#ffb700"
    ),
    "Match Momentum": CyberTheme(
        "Crimson Blaze",
        "#ff1e56", "#b8002e", "#fda4af",
        ["#120106", "#24020e", "#360315", "#0d0005"],
        "#ff1e56"
    ),
    "Shots Info": CyberTheme(
        "Electric Purple",
        "#b026ff", "#6b00b6", "#d8b4fe",
        ["#0a0114", "#17022d", "#250348", "#07000e"],
        "#b026ff"
    ),
    "Heat Map": CyberTheme(
        "Solar Plasma",
        "#ff5e00", "#b33600", "#fdba74",
        ["#120501", "#220a02", "#331003", "#0e0400"],
        "#ff5e00"
    ),
    "3D Analysis": CyberTheme(
        "Quantum Teal",
        "#00f5c4", "#008f75", "#5eead4",
        ["#010f0d", "#02201b", "#033029", "#010c0a"],
        "#00f5c4"
    ),
    "Penalty Data": CyberTheme(
        "Cyber Magenta",
        "#ff009d", "#a80064", "#f472b6",
        ["#14010b", "#270217", "#3d0324", "#0d0007"],
        "#ff009d"
    ),
    "Players Speed": CyberTheme(
        "Hyper Volt",
        "#a6ff00", "#639900", "#bef264",
        ["#0a1200", "#152600", "#203a00", "#070d00"],
        "#a6ff00"
    ),
    "New Replay View": CyberTheme(
        "Royal Sapphire",
        "#3b82f6", "#1d4ed8", "#93c5fd",
        ["#020817", "#041130", "#061b4b", "#020718"],
        "#3b82f6"
    ),
    "FOV Gaming": CyberTheme(
        "Synthwave Orchid",
        "#e040fb", "#7c00a8", "#f0abfc",
        ["#110117", "#21022d", "#340348", "#0b0010"],
        "#e040fb"
    ),
}

# -------------------------------------------------------------
# v2.2.0 (user request #4) — PERMANENT APP COLOUR.
# The user can pick ONE colour in Application Settings and the whole
# app keeps it forever — switching mods no longer changes the theme.
# The colour is expanded into a complete CyberTheme (primary / darker
# secondary / lighter accent / tinted dark backgrounds / glow) so every
# themed widget keeps working exactly as with the built-in themes.
# -------------------------------------------------------------
def build_custom_theme(color_hex, name="Custom Colour"):
    """Build a full CyberTheme out of one user-chosen colour."""
    base = QColor(color_hex)
    if not base.isValid():
        return None
    base = QColor(base.red(), base.green(), base.blue())   # drop alpha
    secondary = QColor(max(0, int(base.red() * 0.42)),
                       max(0, int(base.green() * 0.42)),
                       max(0, int(base.blue() * 0.42)))
    accent = QColor(min(255, int(base.red() * 0.55 + 255 * 0.45)),
                    min(255, int(base.green() * 0.55 + 255 * 0.45)),
                    min(255, int(base.blue() * 0.55 + 255 * 0.45)))
    bg = []
    for k, anchor in ((0.22, QColor("#010612")), (0.30, QColor("#030e22")),
                      (0.38, QColor("#041430")), (0.16, QColor("#020917"))):
        bg.append(QColor(int(anchor.red() * (1 - k) + base.red() * k),
                         int(anchor.green() * (1 - k) + base.green() * k),
                         int(anchor.blue() * (1 - k) + base.blue() * k)))
    return CyberTheme(name, base.name(), secondary.name(), accent.name(),
                      [c.name() for c in bg], base.name())

# -------------------------------------------------------------
# 2. Dynamic Particle Sprite Texture Library & Instant Flush
# -------------------------------------------------------------
class ParticleSpriteLibrary:
    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.sparkles = []
        self.motes = []
        self.bokehs = []
        self.set_theme(THEMES["S.A.O.T"])

    def set_theme(self, theme):
        self.sparkles.clear()
        self.motes.clear()
        self.bokehs.clear()

        p_rgb = (theme.primary.red(), theme.primary.green(), theme.primary.blue())
        s_rgb = (theme.secondary.red(), theme.secondary.green(), theme.secondary.blue())

        for size in (8, 12, 16, 20):
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent if IS_PYQT6 else Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
            rad = QRadialGradient(size / 2, size / 2, size / 2)
            rad.setColorAt(0.0, QColor(255, 255, 255, 255))
            rad.setColorAt(0.2, QColor(p_rgb[0], p_rgb[1], p_rgb[2], 235))
            rad.setColorAt(0.45, QColor(p_rgb[0], p_rgb[1], p_rgb[2], 170))
            rad.setColorAt(0.75, QColor(s_rgb[0], s_rgb[1], s_rgb[2], 50))
            rad.setColorAt(1.0, QColor(s_rgb[0], s_rgb[1], s_rgb[2], 0))
            p.setBrush(rad)
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(0, 0, size, size)
            p.end()
            self.sparkles.append(pm)

        for size in (18, 26, 36):
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent if IS_PYQT6 else Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
            rad = QRadialGradient(size / 2, size / 2, size / 2)
            rad.setColorAt(0.0, QColor(255, 255, 255, 240))
            rad.setColorAt(0.25, QColor(p_rgb[0], p_rgb[1], p_rgb[2], 190))
            rad.setColorAt(0.55, QColor(p_rgb[0], p_rgb[1], p_rgb[2], 100))
            rad.setColorAt(0.8, QColor(s_rgb[0], s_rgb[1], s_rgb[2], 30))
            rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(rad)
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(0, 0, size, size)
            p.end()
            self.motes.append(pm)

        for size in (48, 76, 110):
            pm = QPixmap(size, size)
            pm.fill(Qt.GlobalColor.transparent if IS_PYQT6 else Qt.transparent)
            p = QPainter(pm)
            p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
            rad = QRadialGradient(size / 2, size / 2, size / 2)
            rad.setColorAt(0.0, QColor(p_rgb[0], p_rgb[1], p_rgb[2], 45))
            rad.setColorAt(0.5, QColor(s_rgb[0], s_rgb[1], s_rgb[2], 30))
            rad.setColorAt(0.8, QColor(s_rgb[0], s_rgb[1], s_rgb[2], 15))
            rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(rad)
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(0, 0, size, size)
            p.end()
            self.bokehs.append(pm)

class SmoothParticle:
    def __init__(self, w, h, sprite_lib, init=False):
        self.sprite_lib = sprite_lib
        self.category = 'sparkles'
        self.sprite_idx = 0
        self.reset(w, h, init)

    def reset(self, w, h, init=False):
        self.x = random.uniform(0, max(w, 100))
        self.y = random.uniform(0, max(h, 100)) if init else h + random.uniform(5, 40)
        rand = random.random()
        if rand < 0.60:
            self.category = 'sparkles'
            self.sprite_idx = random.randint(0, len(self.sprite_lib.sparkles) - 1)
            self.vy = -random.uniform(0.4, 1.2)
            self.vx = random.uniform(-0.25, 0.25)
            self.sway_amp = random.uniform(0.2, 0.5)
            self.phase = random.uniform(0, math.pi * 2)
            self.phase_speed = random.uniform(0.03, 0.08)
            self.max_alt = h * random.uniform(0.35, 0.75)
        elif rand < 0.88:
            self.category = 'motes'
            self.sprite_idx = random.randint(0, len(self.sprite_lib.motes) - 1)
            self.vy = -random.uniform(0.3, 0.7)
            self.vx = random.uniform(-0.2, 0.2)
            self.sway_amp = random.uniform(0.3, 0.7)
            self.phase = random.uniform(0, math.pi * 2)
            self.phase_speed = random.uniform(0.015, 0.04)
            self.max_alt = h * random.uniform(0.1, 0.35)
        else:
            self.category = 'bokehs'
            self.sprite_idx = random.randint(0, len(self.sprite_lib.bokehs) - 1)
            self.vy = -random.uniform(0.1, 0.3)
            self.vx = random.uniform(-0.15, 0.15)
            self.sway_amp = random.uniform(0.15, 0.4)
            self.phase = random.uniform(0, math.pi * 2)
            self.phase_speed = random.uniform(0.008, 0.02)
            self.max_alt = -60

        self.refresh_sprite()

    def refresh_sprite(self):
        arr = getattr(self.sprite_lib, self.category)
        if arr:
            self.sprite = arr[self.sprite_idx % len(arr)]
            self.half_w = self.sprite.width() / 2.0
            self.half_h = self.sprite.height() / 2.0

    def update(self, w, h):
        self.phase += self.phase_speed
        self.x += self.vx + math.sin(self.phase) * self.sway_amp
        self.y += self.vy
        if self.y < self.max_alt or self.x < -60 or self.x > w + 60:
            self.reset(w, h, False)

# -------------------------------------------------------------
# 3. Adaptive Clean Cyber Slider (Vector, Neon, No Clipping)
# -------------------------------------------------------------
class CleanCyberSlider(QSlider):
    def __init__(self, master_window, orientation=None, parent=None):
        if orientation is None:
            orientation = Qt.Orientation.Horizontal if IS_PYQT6 else Qt.Horizontal
        super().__init__(orientation, parent)
        self.master_window = master_window
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.is_hovered = False
        self.is_dragging = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self.is_dragging = True
            pos_x = event.position().x() if hasattr(event, "position") else event.pos().x()
            self._update_val_from_mouse(pos_x)

    def mouseMoveEvent(self, event):
        if not self.isEnabled():
            return
        if self.is_dragging:
            pos_x = event.position().x() if hasattr(event, "position") else event.pos().x()
            self._update_val_from_mouse(pos_x)

    def mouseReleaseEvent(self, event):
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self.is_dragging = False
            self.update()
        super().mouseReleaseEvent(event)

    def _update_val_from_mouse(self, mx):
        margin = 14.0
        track_w = self.width() - 2 * margin
        if track_w <= 0:
            return
        clamped_x = max(margin, min(mx, self.width() - margin))
        ratio = (clamped_x - margin) / track_w
        val = self.minimum() + ratio * (self.maximum() - self.minimum())
        self.setValue(int(round(val)))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        cy = h / 2.0
        margin = 14.0
        track_w = w - 2 * margin
        thumb_r = 8.5

        val_range = self.maximum() - self.minimum()
        ratio = 0.0 if val_range <= 0 else (self.value() - self.minimum()) / val_range
        ratio = max(0.0, min(1.0, ratio))
        thumb_x = margin + ratio * track_w

        is_on = self.isEnabled()

        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        if is_on:
            p.setBrush(QColor(10, 20, 36, 220))
        else:
            p.setBrush(QColor(14, 18, 24, 180))
        p.drawRoundedRect(QRectF(margin, cy - 2.5, track_w, 5.0), 2.5, 2.5)

        if is_on:
            fill_grad = QLinearGradient(margin, 0, thumb_x, 0)
            fill_grad.setColorAt(0.0, theme.secondary)
            fill_grad.setColorAt(1.0, theme.primary)
            p.setBrush(fill_grad)
        else:
            p.setBrush(QColor(42, 52, 65))

        if thumb_x > margin:
            p.drawRoundedRect(QRectF(margin, cy - 2.5, thumb_x - margin, 5.0), 2.5, 2.5)

        if is_on and (self.is_hovered or self.is_dragging):
            glow_rad = QRadialGradient(thumb_x, cy, 18)
            glow_rad.setColorAt(0.0, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 140))
            glow_rad.setColorAt(0.5, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 50))
            glow_rad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(glow_rad)
            p.drawEllipse(QPointF(thumb_x, cy), 18, 18)

        if is_on:
            p.setBrush(QColor(255, 255, 255))
            border_color = theme.primary if (self.is_hovered or self.is_dragging) else QColor(255, 255, 255, 220)
            p.setPen(QPen(border_color, 2.0))
            p.drawEllipse(QPointF(thumb_x, cy), thumb_r, thumb_r)
        else:
            p.setBrush(QColor(55, 68, 85))
            p.setPen(QPen(QColor(80, 95, 115), 1.6))
            p.drawEllipse(QPointF(thumb_x, cy), thumb_r - 1.0, thumb_r - 1.0)

# -------------------------------------------------------------
# 4. Adaptive Neon Toggle Widget
# -------------------------------------------------------------
class NeonToggle(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, master_window=None, checked=False, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(48, 24)
        hand_cursor = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        self.setCursor(hand_cursor)
        self._checked = checked
        self._thumb_position = 1.0 if checked else 0.0

        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(170)
        curve = QEasingCurve.Type.InOutCubic if IS_PYQT6 else QEasingCurve.InOutCubic
        self._anim.setEasingCurve(curve)

    @pyqtProperty(float)
    def thumb_position(self):
        return self._thumb_position

    @thumb_position.setter
    def thumb_position(self, pos):
        self._thumb_position = pos
        self.update()

    def isChecked(self):
        return self._checked

    def setChecked(self, checked):
        if self._checked != checked:
            self._checked = checked
            self._anim.stop()
            self._anim.setEndValue(1.0 if checked else 0.0)
            self._anim.start()
            self.toggled.emit(self._checked)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self.setChecked(not self._checked)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme if self.master_window else THEMES["S.A.O.T"]

        if not self.isEnabled():
            p.setOpacity(0.38)

        w, h = self.width(), self.height()
        rect = QRectF(1.0, 1.0, w - 2, h - 2)

        if self._checked:
            track_grad = QLinearGradient(0, 0, w, 0)
            track_grad.setColorAt(0.0, theme.secondary)
            track_grad.setColorAt(1.0, theme.primary)
            p.setBrush(track_grad)
            p.setPen(QPen(theme.primary, 1.2))
        else:
            p.setBrush(QColor(6, 16, 30, 190))
            p.setPen(QPen(QColor(60, 90, 130, 80), 1.0))

        p.drawRoundedRect(rect, h / 2, h / 2)

        thumb_r = 8.0
        x_min = 3 + thumb_r
        x_max = w - 3 - thumb_r
        thumb_x = x_min + (x_max - x_min) * self._thumb_position
        thumb_y = h / 2.0

        no_pen = Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen
        if self._checked:
            p.setBrush(QColor(255, 255, 255))
            p.setPen(QPen(theme.primary, 1.4))
        else:
            p.setBrush(QColor(65, 95, 130))
            p.setPen(no_pen)

        p.drawEllipse(QPointF(thumb_x, thumb_y), thumb_r, thumb_r)

# -------------------------------------------------------------
# 5. Adaptive Cyber Launch Button
# -------------------------------------------------------------
class CyberLaunchButton(QPushButton):
    def __init__(self, master_window, text="APPLY & RUN MOD BRIDGE", parent=None):
        super().__init__(text, parent)
        self.master_window = master_window
        self.setFixedHeight(54)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.glow_phase = 0.0
        self.shimmer_x = -0.3

    def advance_animation(self, delta):
        self.glow_phase = (self.glow_phase + 0.038) % (2 * math.pi)
        self.shimmer_x += 0.015
        if self.shimmer_x > 1.3:
            self.shimmer_x = -0.3
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        radius = 13.0

        bg = QLinearGradient(0, 0, w, 0)
        if self.isDown():
            bg.setColorAt(0.0, theme.secondary.darker(140))
            bg.setColorAt(1.0, theme.primary.darker(120))
        elif self.underMouse():
            bg.setColorAt(0.0, theme.secondary)
            bg.setColorAt(0.5, theme.primary)
            bg.setColorAt(1.0, theme.accent)
        else:
            bg.setColorAt(0.0, theme.secondary.darker(110))
            bg.setColorAt(0.5, theme.secondary)
            bg.setColorAt(1.0, theme.primary)

        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        p.save()
        p.setClipRect(QRectF(1, 1, w - 2, h - 2))
        shimmer_pos = self.shimmer_x * w
        shimmer_w = 90.0
        shimmer_grad = QLinearGradient(shimmer_pos - shimmer_w, 0, shimmer_pos + shimmer_w, 0)
        shimmer_grad.setColorAt(0.0, QColor(255, 255, 255, 0))
        shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, 65))
        shimmer_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(shimmer_grad)
        p.drawRect(QRectF(shimmer_pos - shimmer_w, 0, shimmer_w * 2, h))
        p.restore()

        angle_deg = math.degrees(self.glow_phase) % 360
        conic = QConicalGradient(w / 2.0, h / 2.0, angle_deg)
        conic.setColorAt(0.0, QColor(255, 255, 255, 255))
        conic.setColorAt(0.08, theme.accent)
        conic.setColorAt(0.2, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 40))
        conic.setColorAt(0.8, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 40))
        conic.setColorAt(0.92, theme.accent)
        conic.setColorAt(1.0, QColor(255, 255, 255, 255))

        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(QBrush(conic), 1.6))
        p.drawRoundedRect(QRectF(0.8, 0.8, w - 1.6, h - 1.6), radius, radius)

        p.setFont(QFont("Segoe UI", 12, QFont.Weight.Black if IS_PYQT6 else 95))
        p.setPen(QColor(255, 255, 255))
        text_rect = self.rect()
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter,
                   self.text() if self.text() else "APPLY & RUN MOD BRIDGE")

# -------------------------------------------------------------
# 5b. LIQUID-GLASS PILL BUTTON  (user reference image, v2.1.6)
# A dark translucent capsule with a coloured circular icon badge on the
# left, a bold white label and a soft under-glow. Fully custom-painted
# and 100% theme-driven: every colour is read from the LIVE
# active_theme at paint time, so the button follows all 11 mod themes
# AND morphs smoothly while the theme transition animation runs.
# -------------------------------------------------------------
def _draw_pill_glyph(p, kind, cx, cy, r, color):
    """Vector glyphs for the glass badge (no fonts, no emoji)."""
    pen = QPen(color, max(1.6, r * 0.22))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap if IS_PYQT6 else Qt.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin if IS_PYQT6 else Qt.RoundJoin)
    p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
    p.setPen(pen)

    if kind == "sliders":
        # v2.1.9 — mixer-sliders glyph for "DISPLAY SETTINGS"
        for yy, kx in ((-0.45, 0.18), (0.0, -0.30), (0.45, 0.32)):
            y = cy + r * yy
            p.drawLine(QPointF(cx - r * 0.62, y), QPointF(cx + r * 0.62, y))
            p.setBrush(QBrush(color))
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(QPointF(cx + r * kx, y), r * 0.17, r * 0.17)
            p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
            p.setPen(pen)
    if kind == "play":
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        s = r * 0.62
        tri = QPolygonF([QPointF(cx - s * 0.55, cy - s),
                         QPointF(cx - s * 0.55, cy + s),
                         QPointF(cx + s * 0.95, cy)])
        p.drawPolygon(tri)
    elif kind == "heart":
        s = r * 0.95
        path = QPainterPath()
        path.moveTo(cx, cy + s * 0.78)
        path.cubicTo(cx - s * 1.35, cy - s * 0.25, cx - s * 0.45, cy - s * 1.1, cx, cy - s * 0.32)
        path.cubicTo(cx + s * 0.45, cy - s * 1.1, cx + s * 1.35, cy - s * 0.25, cx, cy + s * 0.78)
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawPath(path)
    elif kind == "restore":
        p.drawEllipse(QRectF(cx - r * 0.55, cy - r * 0.55, r * 1.1, r * 1.1))
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(cx + r * 0.10, cy - r * 0.95),
                                 QPointF(cx + r * 0.75, cy - r * 0.42),
                                 QPointF(cx - r * 0.02, cy - r * 0.18)]))
    elif kind == "power":
        # open circle (gap at the top) + vertical stem = power glyph
        # QPainterPath.arcTo works on BOTH PyQt5 and PyQt6 (Qt6 dropped
        # the integer-rect drawEllipse arc overload)
        box = QRectF(cx - r * 0.52, cy - r * 0.40, r * 1.04, r * 0.94)
        path = QPainterPath()
        path.arcMoveTo(box, 30)
        path.arcTo(box, 30, 300)
        p.drawPath(path)
        p.drawLine(QPointF(cx, cy - r * 0.72), QPointF(cx, cy + r * 0.05))
    elif kind == "check":
        p.drawPolyline(QPolygonF([QPointF(cx - r * 0.55, cy + r * 0.02),
                                  QPointF(cx - r * 0.10, cy + r * 0.48),
                                  QPointF(cx + r * 0.60, cy - r * 0.45)]))
    elif kind == "dot":
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.42, r * 0.42)
    elif kind == "download":
        # arrow down into a tray — "DOWNLOAD" actions
        p.setPen(pen)
        p.drawPolyline(QPolygonF([QPointF(cx - r * 0.45, cy - r * 0.25),
                                  QPointF(cx, cy + r * 0.30),
                                  QPointF(cx + r * 0.45, cy - r * 0.25)]))
        p.drawLine(QPointF(cx, cy - r * 0.70), QPointF(cx, cy + r * 0.28))
        p.drawLine(QPointF(cx - r * 0.62, cy + r * 0.72),
                   QPointF(cx + r * 0.62, cy + r * 0.72))
    elif kind == "copy":
        # two overlapping rounded sheets — "COPY" actions
        p.setPen(pen)
        p.drawRoundedRect(QRectF(cx - r * 0.70, cy - r * 0.70,
                                 r * 0.95, r * 1.05), r * 0.18, r * 0.18)
        p.setBrush(QBrush(color))
        p.setPen(QPen(color, max(1.6, r * 0.22)))
        path = QPainterPath()
        path.moveTo(cx - r * 0.18, cy - r * 0.42)
        path.lineTo(cx + r * 0.52, cy - r * 0.42)
        path.quadTo(cx + r * 0.70, cy - r * 0.42, cx + r * 0.70, cy - r * 0.24)
        path.lineTo(cx + r * 0.70, cy + r * 0.48)
        path.quadTo(cx + r * 0.70, cy + r * 0.62, cx + r * 0.52, cy + r * 0.62)
        path.lineTo(cx - r * 0.18, cy + r * 0.62)
        path.quadTo(cx - r * 0.36, cy + r * 0.62, cx - r * 0.36, cy + r * 0.48)
        path.lineTo(cx - r * 0.36, cy - r * 0.24)
        path.quadTo(cx - r * 0.36, cy - r * 0.42, cx - r * 0.18, cy - r * 0.42)
        p.drawPath(path)
    elif kind == "book":
        # open book / guide — "VIEW INSTRUCTIONS"
        p.setPen(pen)
        p.drawPolyline(QPolygonF([QPointF(cx, cy - r * 0.55),
                                  QPointF(cx, cy + r * 0.55)]))
        path = QPainterPath()
        path.moveTo(cx, cy - r * 0.50)
        path.cubicTo(cx - r * 0.35, cy - r * 0.75, cx - r * 0.80, cy - r * 0.55,
                     cx - r * 0.80, cy - r * 0.35)
        path.lineTo(cx - r * 0.80, cy + r * 0.45)
        path.cubicTo(cx - r * 0.80, cy + r * 0.62, cx - r * 0.35, cy + r * 0.60,
                     cx, cy + r * 0.55)
        p.drawPath(path)
        path = QPainterPath()
        path.moveTo(cx, cy - r * 0.50)
        path.cubicTo(cx + r * 0.35, cy - r * 0.75, cx + r * 0.80, cy - r * 0.55,
                     cx + r * 0.80, cy - r * 0.35)
        path.lineTo(cx + r * 0.80, cy + r * 0.45)
        path.cubicTo(cx + r * 0.80, cy + r * 0.62, cx + r * 0.35, cy + r * 0.60,
                     cx, cy + r * 0.55)
        p.drawPath(path)
    else:  # "star" fallback
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.45, r * 0.45)


class GlassPillButton(QPushButton):
    """Liquid-glass pill button — the app-wide primary button style.

    Features (matching the user's reference image):
      * rounded-full dark glass capsule with top bevel + light border
      * coloured circular icon badge (radial gradient + glow ring)
      * bold white label, centred in the space right of the badge
      * soft theme-coloured under-glow, brighter on hover
      * optional checkable mode: checked = accent border + filled dot
      * optional shimmer animation for the main launch button
    Theme compatibility: badge/glow colours default to the live theme
    primary (or a fixed accent colour), so the same button works under
    every mod theme without any extra code."""

    def __init__(self, master_window, text="", icon="play", accent=None,
                 parent=None, height=48, font_px=12.5, min_width=0,
                 checkable=False, animated=False, center_text=False,
                 compact=False):
        super().__init__(parent)
        self.master_window = master_window
        self._label = text
        self._icon = icon
        self._fixed_accent = QColor(accent) if accent else None
        self._font_px = font_px
        self._center_text = center_text
        self._animated = animated
        self._compact = bool(compact)      # small option pill: dot + label only
        self._shimmer_x = -0.35
        self.setFixedHeight(height)
        if min_width:
            self.setMinimumWidth(min_width)
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.setText(text)

    # ---- theme plumbing ------------------------------------------------
    def _accent(self):
        if self._fixed_accent is not None:
            return QColor(self._fixed_accent)
        mw = self.master_window
        theme = getattr(mw, "active_theme", None)
        return QColor(theme.primary) if theme is not None else QColor("#00f0ff")

    def _glass_base(self):
        theme = getattr(self.master_window, "active_theme", None)
        if theme is not None and getattr(theme, "bg_dark", None):
            return QColor(theme.bg_dark[2])
        return QColor("#101a2e")

    def advance_animation(self, delta=0.016):
        """Shimmer sweep — driven by the master window's frame timer."""
        if not self._animated:
            return
        self._shimmer_x += 0.014
        if self._shimmer_x > 1.35:
            self._shimmer_x = -0.35
        self.update()

    def setText(self, text):
        self._label = text
        super().setText(text)

    def text(self):
        return self._label

    # ---- painting -------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        w, h = self.width(), self.height()
        radius = h / 2.0
        accent = self._accent()
        ar, ag, ab = accent.red(), accent.green(), accent.blue()
        base = self._glass_base()
        checked = self.isCheckable() and self.isChecked()
        down = self.isDown()
        hover = self.underMouse()

        # 1) soft under-glow (the "floating" glass look)
        glow_alpha = 95 if hover else 62
        if down:
            glow_alpha = 40
        if not self.isEnabled():
            glow_alpha = 22
        glow = QRadialGradient(w / 2.0, h * 0.92, max(w * 0.62, h))
        glow.setColorAt(0.0, QColor(ar, ag, ab, glow_alpha))
        glow.setColorAt(0.55, QColor(ar, ag, ab, glow_alpha // 3))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(2, 4, w - 4, h - 2), radius, radius)

        # 2) glass capsule body
        body = QLinearGradient(0, 1, 0, h - 1)
        if down:
            body.setColorAt(0.0, QColor(max(0, base.red() - 22), max(0, base.green() - 22), max(0, base.blue() - 22), 235))
            body.setColorAt(1.0, QColor(max(0, base.red() - 38), max(0, base.green() - 38), max(0, base.blue() - 38), 245))
        else:
            body.setColorAt(0.0, QColor(min(255, base.red() + 26), min(255, base.green() + 26), min(255, base.blue() + 26), 205))
            body.setColorAt(0.5, QColor(base.red(), base.green(), base.blue(), 225))
            body.setColorAt(1.0, QColor(max(0, base.red() - 18), max(0, base.green() - 18), max(0, base.blue() - 18), 240))
        p.setBrush(QBrush(body))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # 3) accent wash from the badge side (colour tint like the image)
        wash = QLinearGradient(0, 0, w, 0)
        wash_alpha = 70 if (hover or checked) else 44
        wash.setColorAt(0.0, QColor(ar, ag, ab, wash_alpha))
        wash.setColorAt(0.55, QColor(ar, ag, ab, wash_alpha // 4))
        wash.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setBrush(QBrush(wash))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # 4) shimmer sweep (animated launch button only)
        if self._animated and self.isEnabled():
            p.save()
            # Clip the reflection to the REAL rounded capsule, not a
            # rectangular clip. This prevents the shimmer from leaking
            # into the transparent corner areas of the pill.
            clip_path = QPainterPath()
            clip_path.addRoundedRect(
                QRectF(1, 1, w - 2, h - 2), radius, radius)
            p.setClipPath(clip_path)
            sx = self._shimmer_x * w
            sw = 62.0
            sh = QLinearGradient(sx - sw, 0, sx + sw, 0)
            sh.setColorAt(0.0, QColor(255, 255, 255, 0))
            sh.setColorAt(0.5, QColor(255, 255, 255, 50))
            sh.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(sh))
            p.drawRect(QRectF(sx - sw, 0, sw * 2, h))
            p.restore()

        # 5) top bevel highlight
        bevel = QLinearGradient(2, 2, w - 2, 2)
        bevel.setColorAt(0.0, QColor(255, 255, 255, 0))
        bevel.setColorAt(0.5, QColor(255, 255, 255, 80 if hover else 55))
        bevel.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(QBrush(bevel), 1.1))
        p.drawLine(QPointF(radius * 0.9, 2.2), QPointF(w - radius * 0.9, 2.2))

        # 6) capsule border
        if checked:
            border = QColor(255, 255, 255, 210)
        elif hover:
            border = QColor(min(255, ar + 70), min(255, ag + 70), min(255, ab + 70), 190)
        else:
            border = QColor(255, 255, 255, 60 if self.isEnabled() else 30)
        p.setPen(QPen(border, 1.35 if (checked or hover) else 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        # 7) icon badge (circular, radial gradient + glow ring).
        # Compact pills skip the big badge: a tiny state dot + full-width
        # label so short option captions NEVER elide.
        if self._compact:
            dot_x, dot_y = 15.0, h / 2.0
            dot_r = 4.4
            if self.isEnabled() and checked:
                dg = QRadialGradient(dot_x, dot_y, dot_r * 3.2)
                dg.setColorAt(0.0, QColor(ar, ag, ab, 170))
                dg.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(dg))
                p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
                p.drawEllipse(QPointF(dot_x, dot_y), dot_r * 3.0, dot_r * 3.0)
            if checked:
                p.setBrush(QBrush(accent))
                p.setPen(QPen(QColor(255, 255, 255, 235), 1.3))
            elif self.isCheckable():
                p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
                p.setPen(QPen(QColor(170, 182, 198, 190), 1.4))
            else:
                # non-checkable compact pill (e.g. RESTORE DEFAULT MODE):
                # a solid accent bullet instead of a hollow ring
                p.setBrush(QBrush(accent))
                p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(QPointF(dot_x, dot_y), dot_r, dot_r)
            text_left = 27.0
            badge_r = 0
            bcx = 0
        else:
            badge_r = (h - 16) / 2.0
            bcx = 8 + badge_r + 2
            bcy = h / 2.0
            if self.isEnabled():
                ring = QRadialGradient(bcx, bcy, badge_r * 2.0)
                ring.setColorAt(0.0, QColor(ar, ag, ab, 90))
                ring.setColorAt(0.62, QColor(ar, ag, ab, 42))
                ring.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setBrush(QBrush(ring))
                p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
                p.drawEllipse(QPointF(bcx, bcy), badge_r * 1.75, badge_r * 1.75)

            badge_grad = QRadialGradient(bcx - badge_r * 0.35, bcy - badge_r * 0.4, badge_r * 1.7)
            if self.isEnabled():
                badge_grad.setColorAt(0.0, QColor(min(255, ar + 90), min(255, ag + 90), min(255, ab + 90)))
                badge_grad.setColorAt(0.55, QColor(ar, ag, ab))
                badge_grad.setColorAt(1.0, QColor(max(0, ar - 95), max(0, ag - 95), max(0, ab - 95)))
            else:
                badge_grad.setColorAt(0.0, QColor(70, 82, 98))
                badge_grad.setColorAt(1.0, QColor(44, 52, 64))
            p.setBrush(QBrush(badge_grad))
            if checked:
                p.setPen(QPen(QColor(255, 255, 255, 235), 1.5))
            else:
                p.setPen(QPen(QColor(255, 255, 255, 90), 1.1))
            p.drawEllipse(QPointF(bcx, bcy), badge_r, badge_r)

            glyph_color = QColor(255, 255, 255) if self.isEnabled() else QColor(150, 160, 175)
            _draw_pill_glyph(p, self._icon, bcx, bcy, badge_r * 0.72, glyph_color)
            text_left = bcx + badge_r + 9

        # 8) label — bold white, in the space right of the badge/dot
        font = QFont("Segoe UI", int(round(self._font_px)))
        font.setWeight(QFont.Weight.Black if IS_PYQT6 else 92)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing,
                              0.5 if self._compact else 0.9)
        p.setFont(font)
        p.setPen(QColor(255, 255, 255) if self.isEnabled() else QColor(110, 122, 138))
        text_rect = QRectF(text_left, 0, w - text_left - 10, h)
        flags = (Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter)
        flags |= (Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignHCenter) \
            if self._center_text else (Qt.AlignmentFlag.AlignLeft if IS_PYQT6 else Qt.AlignLeft)
        fm = p.fontMetrics()
        elided = fm.elidedText(self._label,
                               Qt.TextElideMode.ElideRight if IS_PYQT6 else Qt.ElideRight,
                               int(text_rect.width()))
        p.drawText(text_rect, flags, elided)


# -------------------------------------------------------------
# 5c. CATEGORY HEADER — collapsible group title row (v2.1.6)
# A compact glass divider row: chevron + category name + member count.
# Clicking it expands/collapses its block of mod rows; the state is
# persisted by the master window (ModsConfig.json -> ui.expanded).
# -------------------------------------------------------------
class CategoryHeader(QFrame):
    toggled = pyqtSignal(str, bool)

    def __init__(self, master_window, name, n_total, n_live, expanded=True, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.name = name
        self.n_total = int(n_total)
        self.n_live = int(n_live)
        self.expanded = bool(expanded)
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)

    def mousePressEvent(self, event):
        self.expanded = not self.expanded
        self.update()
        self.toggled.emit(self.name, self.expanded)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()

        # subtle glass strip
        strip = QLinearGradient(0, 0, w, 0)
        strip.setColorAt(0.0, QColor(pr, pg, pb, 34))
        strip.setColorAt(0.5, QColor(pr, pg, pb, 12))
        strip.setColorAt(1.0, QColor(pr, pg, pb, 0))
        p.setBrush(QBrush(strip))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h - 4), 8, 8)

        # chevron
        p.setBrush(QBrush(theme.primary))
        cx, cy = 14, (h - 4) / 2.0
        if self.expanded:
            tri = QPolygonF([QPointF(cx - 4.5, cy - 3.5), QPointF(cx + 4.5, cy - 3.5),
                             QPointF(cx, cy + 4.0)])
        else:
            tri = QPolygonF([QPointF(cx - 3.5, cy - 4.5), QPointF(cx + 4.0, cy),
                             QPointF(cx - 3.5, cy + 4.5)])
        p.drawPolygon(tri)

        # title
        font = QFont("Segoe UI", 10)
        font.setWeight(QFont.Weight.Black if IS_PYQT6 else 95)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.0)
        p.setFont(font)
        p.setPen(QColor(theme.primary))
        p.drawText(QRectF(30, 0, w - 110, h - 4),
                   Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter,
                   self.name)

        # counters (published vs total)
        font2 = QFont("Segoe UI", 8)
        font2.setWeight(QFont.Weight.Bold if IS_PYQT6 else 70)
        font2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        p.setFont(font2)
        p.setPen(QColor(148, 163, 184))
        p.drawText(QRectF(w - 108, 0, 100, h - 4),
                   (Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                   if IS_PYQT6 else (Qt.AlignVCenter | Qt.AlignRight),
                   f"{self.n_live} LIVE / {self.n_total}")

        # bottom hairline
        p.setPen(QPen(QColor(pr, pg, pb, 60), 1.0))
        p.drawLine(QPointF(2, h - 2.0), QPointF(w - 2, h - 2.0))


# -------------------------------------------------------------
# 5d. MANUFACTURER BOX — themed footer brand plate (v2.1.6)
# The "MODS BY MILAD" manufacturer text lives in a proper frosted
# glass plate at the bottom of MyMods; every colour follows the live
# theme so it always matches the rest of the program.
# -------------------------------------------------------------
class ManufacturerBox(QFrame):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedHeight(46)

    # ---- v2.1.8 real frosted-glass backdrop ------------------------------
    def _video_blur_behind(self):
        """Sample the CURRENT video frame in the region right behind this
        bar and return a heavily blurred QImage of it (frosted glass).
        Returns None when the video background is not rendering."""
        m = self.master_window
        vb = getattr(m, "video_bg", None)
        if vb is None or not m.video_active() or vb._frame_img is None:
            return None
        central = m.centralWidget()
        if central is None:
            return None
        try:
            tl = self.mapTo(central, QPoint(0, 0))
            vw, vh = central.width(), central.height()
            if vw <= 0 or vh <= 0:
                return None
            img = vb._frame_img
            W, H = img.width(), img.height()
            # same cover-fit crop the video widget paints (bottom->top)
            wa = vw / float(vh)
            fa = W / float(max(1, H))
            if fa > wa:                       # source wider -> crop sides
                cw = int(round(H * wa))
                sx, sy, sw, sh = (W - cw) // 2, 0, cw, H
            else:                             # source taller -> crop top/bottom
                ch = int(round(W / wa))
                sx, sy, sw, sh = 0, (H - ch) // 2, W, ch
            bx, by = tl.x(), tl.y()
            bw, bh = self.width(), self.height()
            fx = sx + int(sw * (bx / float(vw)))
            fy = sy + int(sh * (by / float(vh)))
            fw = max(2, int(sw * (bw / float(vw))))
            fh = max(2, int(sh * (bh / float(vh))))
            crop = img.copy(QRect(fx, fy, fw, fh))
            if crop.isNull():
                return None
            # cheap, smooth gaussian-ish blur: downscale -> upscale
            small = crop.scaled(max(1, bw // 16), max(1, bh // 16),
                                IGNORE_ASPECT,
                                Qt.TransformationMode.SmoothTransformation
                                if IS_PYQT6 else Qt.SmoothTransformation)
            return small.scaled(bw, bh, IGNORE_ASPECT,
                                Qt.TransformationMode.SmoothTransformation
                                if IS_PYQT6 else Qt.SmoothTransformation)
        except Exception:
            return None

    def paintEvent(self, event):
        # v2.1.9 - COMPLETELY REDESIGNED bottom plate. The old flat strip
        # looked ugly and disconnected from the rest of the program. The new
        # plate is built from the SAME glass language as the frosted panels
        # and the glass pills: a deep glass body, a theme-coloured sweep, a
        # top bevel, an inner bottom shade, a rotating conic glint border
        # and refined typography - with the live blurred video still
        # glowing through when the background video is playing.
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()
        sr, sg, sb = theme.secondary.red(), theme.secondary.green(), theme.secondary.blue()
        radius = 14.0

        blurred = self._video_blur_behind()
        b1 = theme.bg_dark[1]
        b2 = theme.bg_dark[2]
        b3 = theme.bg_dark[3]

        # clip everything to the rounded plate
        path = QPainterPath()
        path.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)
        p.setClipPath(path)

        # 1) the live blurred video glowing through (when playing)
        if blurred is not None:
            p.drawImage(0, 0, blurred)

        # 2) glass body - the same deep glass gradient as the panels
        body = QLinearGradient(0, 0, 0, h)
        if blurred is not None:
            # Stronger modal-like frost: the video remains perceptible,
            # but the plate has a clearly readable glass body on top.
            body.setColorAt(0.0, QColor(255, 255, 255, 48))
            body.setColorAt(0.22, QColor(b1.red(), b1.green(), b1.blue(), 176))
            body.setColorAt(0.55, QColor(b2.red(), b2.green(), b2.blue(), 204))
            body.setColorAt(1.0, QColor(b3.red(), b3.green(), b3.blue(), 232))
        else:
            body.setColorAt(0.0, QColor(b1.red(), b1.green(), b1.blue(), 220))
            body.setColorAt(0.55, QColor(b2.red(), b2.green(), b2.blue(), 235))
            body.setColorAt(1.0, QColor(b3.red(), b3.green(), b3.blue(), 248))
        p.fillRect(QRectF(0, 0, w, h), QBrush(body))

        # 3) theme sweep - a soft accent wash entering from the left
        sweep = QLinearGradient(0, 0, w, 0)
        sweep.setColorAt(0.0, QColor(sr, sg, sb, 66))
        sweep.setColorAt(0.4, QColor(sr, sg, sb, 20))
        sweep.setColorAt(1.0, QColor(pr, pg, pb, 0))
        p.fillRect(QRectF(0, 0, w, h), QBrush(sweep))

        # 4) top bevel highlight + inner bottom shade (the "liquid glass")
        bevel = QLinearGradient(0, 1, w, 1)
        bevel.setColorAt(0.0, QColor(255, 255, 255, 0))
        bevel.setColorAt(0.2, QColor(255, 255, 255, 72))
        bevel.setColorAt(0.5, QColor(255, 255, 255, 105))
        bevel.setColorAt(0.8, QColor(255, 255, 255, 72))
        bevel.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(bevel), 1.2))
        p.drawLine(QPointF(radius, 1.2), QPointF(w - radius, 1.2))
        shade = QLinearGradient(0, h - 12, 0, h)
        shade.setColorAt(0.0, QColor(0, 0, 0, 0))
        shade.setColorAt(1.0, QColor(0, 0, 0, 80))
        p.fillRect(QRectF(0, h - 12, w, 12), QBrush(shade))

        # 5) inner bottom theme glow - the plate "floats" on its own colour
        glow = QRadialGradient(w / 2.0, h + 10, max(w * 0.55, h * 2.2))
        glow.setColorAt(0.0, QColor(pr, pg, pb, 74))
        glow.setColorAt(0.55, QColor(pr, pg, pb, 22))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(0, h - 16, w, 16), QBrush(glow))
        p.setClipping(False)

        # 6) rotating conic glint border - identical to the frosted panels
        angle_deg = math.degrees(self.master_window.border_phase) % 360
        glint = QConicalGradient(w / 2.0, h / 2.0, angle_deg)
        glint.setColorAt(0.0, QColor(255, 255, 255, 190))
        glint.setColorAt(0.05, theme.primary)
        glint.setColorAt(0.12, QColor(sr, sg, sb, 0))
        glint.setColorAt(0.88, QColor(sr, sg, sb, 0))
        glint.setColorAt(0.95, theme.primary)
        glint.setColorAt(1.0, QColor(255, 255, 255, 190))
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(QBrush(glint), 1.35))
        p.drawRoundedRect(QRectF(0.9, 0.9, w - 1.8, h - 1.8), radius, radius)

        # 7) brand (left) - the manufacturer's text
        f1 = QFont("Segoe UI", 10)
        f1.setWeight(QFont.Weight.Black if IS_PYQT6 else 95)
        f1.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2.2)
        p.setFont(f1)
        p.setPen(QColor(theme.primary))
        p.drawText(QRectF(18, 0, w * 0.52, h),
                   Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter,
                   "PES \\ eFOOTBALL  \u2022  MODS BY MILAD")

        # legal / version (right)
        f2 = QFont("Segoe UI", 8)
        f2.setWeight(QFont.Weight.Bold if IS_PYQT6 else 75)
        f2.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.8)
        p.setFont(f2)
        p.setPen(QColor(theme.accent))
        p.drawText(QRectF(w * 0.52, 0, w * 0.48 - 18, h),
                   (Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)
                   if IS_PYQT6 else (Qt.AlignVCenter | Qt.AlignRight),
                   f"FOOTBALL LIFE 2026 READY  \u2022  SOFTWARE v{APP_VERSION}  \u2022  \u00a9 2026 MILAD MODS. ALL RIGHTS RESERVED")

# -------------------------------------------------------------
# 5d-b. CONTACT BADGES — external image assets from Background/
# The About window uses user-supplied logo files instead of drawing
# brand glyphs in code. Keep one image per channel beside the app:
#   Background/youtube.png
#   Background/instagram.png
#   Background/telegram.png
#   Background/email.png
#   Background/github.png
# PNG is the recommended format because transparent backgrounds are
# preserved cleanly on the glass badges. SVG/WebP/JPG are also accepted.
# -------------------------------------------------------------
CONTACT_LOGO_FOLDER = os.path.join(APP_DIR, "Background")
CONTACT_LOGO_FILES = {
    "youtube": "youtube",
    "instagram": "instagram",
    "telegram": "telegram",
    "email": "email",
    "github": "github",
}
CONTACT_LOGO_EXTENSIONS = (".png", ".svg", ".webp", ".jpg", ".jpeg")

CONTACT_BRANDS = (
    ("youtube",   "YouTube — tutorials & updates",   QColor("#ff0033")),
    ("instagram", "Instagram — behind the scenes",   QColor("#e1306c")),
    ("telegram",  "Telegram — community & support",  QColor("#229ed9")),
    ("email",     "E-mail — report a bug directly",  QColor("#38bdf8")),
    ("github",    "GitHub — the developer's Gist & mod updates", QColor("#f0f6fc")),
)

CONTACT_LABELS = {"youtube": "YOUTUBE", "instagram": "INSTAGRAM",
                  "telegram": "TELEGRAM", "email": "E-MAIL",
                  "github": "GITHUB"}


def _find_contact_logo(kind):
    """Return the first available logo asset for a contact channel."""
    stem = CONTACT_LOGO_FILES.get(str(kind), "")
    if not stem:
        return ""
    for ext in CONTACT_LOGO_EXTENSIONS:
        path = os.path.join(CONTACT_LOGO_FOLDER, stem + ext)
        if os.path.isfile(path):
            return path
    return ""


class _ContactIconButton(QPushButton):
    """Glass contact badge that displays a user-supplied logo asset.

    No brand glyph is painted in code. The supplied image is loaded once
    and scaled smoothly into the badge, preserving transparent pixels.
    """

    BADGE_SIZE = 58
    LOGO_SIZE = 34

    def __init__(self, master_window, kind, brand_color, tooltip, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.kind = kind
        self.brand = QColor(brand_color)
        self.logo_path = _find_contact_logo(kind)
        self.logo_pixmap = QPixmap(self.logo_path) if self.logo_path else QPixmap()
        self.setFixedSize(self.BADGE_SIZE, self.BADGE_SIZE)
        self.setCursor(Qt.CursorShape.PointingHandCursor
                       if IS_PYQT6 else Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def _logo_for_paint(self):
        if self.logo_pixmap.isNull():
            return QPixmap()
        return self.logo_pixmap.scaled(
            self.LOGO_SIZE,
            self.LOGO_SIZE,
            Qt.AspectRatioMode.KeepAspectRatio if IS_PYQT6 else Qt.KeepAspectRatio,
            SMOOTH_TRANSFORM,
        )

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing
                        if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform
                        if IS_PYQT6 else QPainter.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0
        theme = self.master_window.active_theme
        hover = self.is_hovered or self.isDown()

        # Soft theme halo.
        halo = QRadialGradient(cx, cy, w * 0.74)
        a0 = 100 if hover else 52
        halo.setColorAt(0.0, QColor(theme.primary.red(), theme.primary.green(),
                                   theme.primary.blue(), a0))
        halo.setColorAt(0.58, QColor(theme.primary.red(), theme.primary.green(),
                                     theme.primary.blue(), a0 // 4))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QRectF(0, 0, w, h))

        # Glass disc.
        base = theme.bg_dark[2] if getattr(theme, "bg_dark", None) else QColor("#101a2e")
        disc = QLinearGradient(0, 1, 0, h - 1)
        disc.setColorAt(0.0, QColor(min(255, base.red() + 42),
                                    min(255, base.green() + 42),
                                    min(255, base.blue() + 42), 228))
        disc.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 242))
        p.setBrush(QBrush(disc))
        p.drawEllipse(QRectF(2.5, 2.5, w - 5, h - 5))

        ring_a = 245 if hover else 145
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, ring_a), 1.4))
        p.drawEllipse(QRectF(2.5, 2.5, w - 5, h - 5))

        # The brand mark itself comes ONLY from Background/<name>.*.
        logo = self._logo_for_paint()
        if not logo.isNull():
            x = (w - logo.width()) / 2.0
            y = (h - logo.height()) / 2.0
            p.setOpacity(1.0 if self.isEnabled() else 0.45)
            if hover:
                glow = QRadialGradient(cx, cy, max(18.0, self.LOGO_SIZE * 0.85))
                glow.setColorAt(0.0, QColor(theme.primary.red(), theme.primary.green(),
                                            theme.primary.blue(), 38))
                glow.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setOpacity(1.0)
                p.setBrush(QBrush(glow))
                p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
                p.drawEllipse(QPointF(cx, cy), self.LOGO_SIZE * 0.76, self.LOGO_SIZE * 0.76)
                p.setOpacity(1.0 if self.isEnabled() else 0.45)
            p.drawPixmap(int(round(x)), int(round(y)), logo)
            p.setOpacity(1.0)
        else:
            # Missing asset state: no generated brand symbol. Show a small
            # neutral marker so the badge still has a stable footprint.
            p.setPen(QPen(QColor(148, 163, 184, 170), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 5.0, 5.0)
            p.drawLine(QPointF(cx - 8, cy), QPointF(cx + 8, cy))
            p.drawLine(QPointF(cx, cy - 8), QPointF(cx, cy + 8))

        p.end()

# (v2.1.9) the old top ContactBarWidget was REMOVED - the contact badges
# now live in the ABOUT window's "CONTACT & REPORT" tab (AboutModal).

# -------------------------------------------------------------
# 6. Adaptive Premium Frosted Glass Panel
# -------------------------------------------------------------
class PremiumFrostedGlassPanel(QFrame):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        radius = 16.0

        dark_glass = QLinearGradient(0, 0, 0, h)
        dark_glass.setColorAt(0.0, QColor(theme.bg_dark[1].red(), theme.bg_dark[1].green(), theme.bg_dark[1].blue(), 210))
        dark_glass.setColorAt(0.55, QColor(theme.bg_dark[2].red(), theme.bg_dark[2].green(), theme.bg_dark[2].blue(), 220))
        dark_glass.setColorAt(1.0, QColor(theme.bg_dark[3].red(), theme.bg_dark[3].green(), theme.bg_dark[3].blue(), 235))
        p.setBrush(dark_glass)
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        top_bevel = QLinearGradient(0, 1, w, 1)
        top_bevel.setColorAt(0.0, QColor(255, 255, 255, 0))
        top_bevel.setColorAt(0.2, QColor(255, 255, 255, 45))
        top_bevel.setColorAt(0.5, QColor(255, 255, 255, 65))
        top_bevel.setColorAt(0.8, QColor(255, 255, 255, 45))
        top_bevel.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(QPen(QBrush(top_bevel), 1.2))
        p.drawLine(QPointF(radius, 1.2), QPointF(w - radius, 1.2))

        base_border = QLinearGradient(0, 0, w, h)
        base_border.setColorAt(0.0, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 55))
        base_border.setColorAt(0.4, QColor(theme.secondary.red(), theme.secondary.green(), theme.secondary.blue(), 25))
        base_border.setColorAt(1.0, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 40))
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(base_border, 1.0))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), radius, radius)

        angle_deg = math.degrees(self.master_window.border_phase) % 360
        glint = QConicalGradient(w / 2.0, h / 2.0, angle_deg)
        glint.setColorAt(0.0, QColor(255, 255, 255, 200))
        glint.setColorAt(0.05, theme.primary)
        glint.setColorAt(0.12, QColor(theme.secondary.red(), theme.secondary.green(), theme.secondary.blue(), 0))
        glint.setColorAt(0.88, QColor(theme.secondary.red(), theme.secondary.green(), theme.secondary.blue(), 0))
        glint.setColorAt(0.95, theme.primary)
        glint.setColorAt(1.0, QColor(255, 255, 255, 200))

        p.setPen(QPen(QBrush(glint), 1.2))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1.0, h - 1.0), radius, radius)

        super().paintEvent(event)

# -------------------------------------------------------------
# 7. Standalone Circular Info Icon
# -------------------------------------------------------------
class PaintInfoIcon(QWidget):
    def __init__(self, master_window, tooltip_html, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(26, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.setToolTip(tooltip_html)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        color = QColor(255, 255, 255) if self.is_hovered else theme.primary

        pen = QPen(color, 1.8)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.drawEllipse(QRectF(2.5, 2.5, 21.0, 21.0))

        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QPointF(13.0, 7.8), 1.6, 1.6)
        p.drawRoundedRect(QRectF(11.8, 11.5, 2.4, 7.5), 1.2, 1.2)


class SectionHintIcon(QWidget):
    """v2.1.9 — the circular '!' section-description icon.

    Every static description that used to be printed UNDER a section
    title in a mod menu now lives in this icon's hover TOOLTIP instead:
    the user hovers the '!' and a styled glass bubble shows the section
    description. Used by ALL five mod pages so the menus stay clean and
    every design follows the same language."""

    TOOLTIP_DURATION_MS = 12000

    def __init__(self, master_window, title, text, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self._title = str(title)
        self._text = str(text)
        self.setFixedSize(19, 19)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6
                       else Qt.PointingHandCursor)
        self.setToolTipDuration(self.TOOLTIP_DURATION_MS)
        self.is_hovered = False
        self._build_tooltip()

    def set_hint(self, text):
        self._text = str(text)
        self._build_tooltip()

    def _build_tooltip(self):
        theme = self.master_window.active_theme
        bg = theme.bg_dark[1]
        self.setToolTip(f"""
        <div style='background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 246);
                    border: 1.2px solid {theme.primary.name()};
                    border-radius: 8px; padding: 8px 12px; color: #e0f2fe; font-family: Segoe UI;'>
            <b style='color: {theme.accent.name()}; font-size: 12.5px;'>{self._title}</b><br>
            <span style='color: #cbd5e1; font-size: 11.5px; line-height: 1.45;'>{self._text}</span>
        </div>
        """)

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme

        # soft theme halo, brighter on hover
        halo = QRadialGradient(9.5, 9.5, 9.5)
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()
        halo.setColorAt(0.0, QColor(pr, pg, pb, 70 if self.is_hovered else 34))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QRectF(0, 0, 19, 19))

        color = QColor(255, 255, 255) if self.is_hovered else theme.primary
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(color, 1.5))
        p.drawEllipse(QRectF(2.2, 2.2, 14.6, 14.6))

        # the "!" glyph: stem + dot
        p.setBrush(QBrush(color))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(8.6, 5.4, 1.8, 5.2), 0.9, 0.9)
        p.drawEllipse(QPointF(9.5, 13.2), 1.1, 1.1)
        p.end()

# -------------------------------------------------------------
# 8. Clean Mod Row Widget with Adaptive Selection
# -------------------------------------------------------------
class CleanModRow(QFrame):
    selected_signal = pyqtSignal(str)
    toggled_signal = pyqtSignal(bool)

    def __init__(self, master_window, name, desc, is_selected=False, is_enabled=True,
                 coming_soon=False, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.name = name
        self.desc = desc
        self.is_selected = is_selected
        self.coming_soon = bool(coming_soon)   # v2.1.2 — not-yet-submitted mod
        # v2.1.6 — 52px rows so the three collapsible categories + 11 mods
        # fit the fixed-height manager panel when everything is expanded.
        self.setFixedHeight(52)
        # v2.1.2 — coming-soon rows are NOT clickable: default cursor, no
        # row-click select, inert toggle. The info tooltip stays available.
        if self.coming_soon:
            self.setCursor(Qt.CursorShape.ArrowCursor if IS_PYQT6
                           else Qt.ArrowCursor)
        else:
            hand_cursor = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
            self.setCursor(hand_cursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(14)

        self.info_icon = PaintInfoIcon(self.master_window, "", self)
        layout.addWidget(self.info_icon)

        self.lbl_title = QLabel(name)
        # v2.1.2 — grey title for not-yet-submitted mods
        self.lbl_title.setStyleSheet(
            "font-size: 14.5px; font-weight: 700; color: %s; background: transparent; border: none;"
            % ("#5b6b80" if self.coming_soon else "#ffffff"))
        layout.addWidget(self.lbl_title)

        # "COMING SOON" badge — shown for mods that do not have a working
        # page yet (see IMPLEMENTED_MOD_NAMES). A subtle amber pill so it
        # reads at a glance but does not fight with the theme colors.
        self.badge_coming_soon = None
        if coming_soon:
            self.badge_coming_soon = QLabel("COMING SOON")
            self.badge_coming_soon.setStyleSheet(
                "color: #fbbf24; font-size: 8px; font-weight: 900; letter-spacing: 0.5px; "
                "background: rgba(251, 191, 36, 0.10); border: 1px solid rgba(251, 191, 36, 0.38); "
                "border-radius: 8px; padding: 2px 6px 3px 6px;")
            layout.addWidget(self.badge_coming_soon, 0,
                             Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter)

        layout.addStretch()

        self.toggle = NeonToggle(master_window=self.master_window, checked=is_enabled)
        self.toggle.toggled.connect(self.toggled_signal.emit)
        # v2.1.2 — not-yet-submitted mods are always INACTIVE: the toggle is
        # disabled (NeonToggle paints itself at 38% opacity when disabled and
        # ignores clicks) and the row ignores every press.
        if self.coming_soon:
            self.toggle.setEnabled(False)
        layout.addWidget(self.toggle)

        self.applyStyle()

    def _build_tooltip(self):
        theme = self.master_window.active_theme
        bg = theme.bg_dark[1]
        tooltip_html = f"""
        <div style='background-color: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 246);
                    border: 1.2px solid {theme.primary.name()};
                    border-radius: 8px; padding: 8px 12px; color: #e0f2fe; font-family: Segoe UI;'>
            <b style='color: {theme.primary.name()}; font-size: 13px;'>{self.name}</b><br>
            <span style='color: {theme.accent.name()}; font-size: 11.5px; line-height: 1.4;'>{self.desc}</span>
        </div>
        """
        self.info_icon.setToolTip(tooltip_html)

    def applyStyle(self):
        theme = self.master_window.active_theme
        if self.is_selected:
            r, g, b = theme.primary.red(), theme.primary.green(), theme.primary.blue()
            sr, sg, sb = theme.secondary.red(), theme.secondary.green(), theme.secondary.blue()
            self.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba({r}, {g}, {b}, 0.28), stop:0.65 rgba({sr}, {sg}, {sb}, 0.08), stop:1 transparent);
                    border: none;
                    border-radius: 10px;
                }}
            """)
        elif self.coming_soon:
            # v2.1.2 — no hover glow for not-yet-submitted mods
            self.setStyleSheet("""
                QFrame {
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                }
            """)
        else:
            self.setStyleSheet("""
                QFrame {
                    background: transparent;
                    border: none;
                    border-radius: 10px;
                }
                QFrame:hover {
                    background: rgba(255, 255, 255, 0.05);
                }
            """)
        self._build_tooltip()

    def setSelected(self, state):
        self.is_selected = state
        self.applyStyle()

    def mousePressEvent(self, event):
        # v2.1.2 — not-yet-submitted mods never react to clicks
        if self.coming_soon:
            event.accept()
            return
        self.selected_signal.emit(self.name)
        super().mousePressEvent(event)

# -------------------------------------------------------------
# 9. Adaptive Tactical Pitch Live Preview
# -------------------------------------------------------------
class TacticalPitchPreview(QWidget):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setMinimumSize(310, 255)
        self.opacity_val = 0.8
        self.intensity_val = 0.75
        self.is_active = True
        self.pitch_base_cache = None
        self.heatmap_cache = None

    def setActive(self, active):
        self.is_active = active
        self.update()

    def setOpacityVal(self, val):
        self.opacity_val = val / 100.0
        self._rebuild_heatmap_cache()
        self.update()

    def setIntensityVal(self, val):
        self.intensity_val = val / 100.0
        self._rebuild_heatmap_cache()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._rebuild_base_cache()
        self._rebuild_heatmap_cache()

    def _rebuild_base_cache(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        self.pitch_base_cache = QPixmap(w, h)
        self.pitch_base_cache.fill(Qt.GlobalColor.transparent if IS_PYQT6 else Qt.transparent)
        p = QPainter(self.pitch_base_cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        # v2.3.5 — the theme-coloured frame around the live pitch preview is
        # the same stray line the user asked to remove from every preview;
        # only the dark backdrop + the accent pitch markings remain.
        p.setBrush(QColor(6, 18, 14, 240))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)

        pen = QPen(theme.accent, 1.1)
        p.setPen(pen)
        no_brush = Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush
        p.setBrush(no_brush)

        p.drawRect(QRectF(16, 16, w - 32, h - 32))
        p.drawLine(QPointF(w / 2, 16), QPointF(w / 2, h - 16))
        p.drawEllipse(QPointF(w / 2, h / 2), 34, 34)
        p.drawRect(QRectF(16, h / 2 - 42, 32, 84))
        p.drawRect(QRectF(w - 48, h / 2 - 42, 32, 84))
        p.end()

    def _rebuild_heatmap_cache(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        self.heatmap_cache = QPixmap(w, h)
        self.heatmap_cache.fill(Qt.GlobalColor.transparent if IS_PYQT6 else Qt.transparent)
        p = QPainter(self.heatmap_cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        p.setOpacity(self.opacity_val)
        spots = [
            (w * 0.52, h * 0.50, 62 * self.intensity_val),
            (w * 0.76, h * 0.54, 48 * self.intensity_val),
            (w * 0.68, h * 0.28, 42 * self.intensity_val),
            (w * 0.66, h * 0.76, 40 * self.intensity_val)
        ]

        no_pen = Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen
        for sx, sy, radius in spots:
            rad = QRadialGradient(sx, sy, radius)
            rad.setColorAt(0.0, QColor(255, 30, 0, 230))
            rad.setColorAt(0.4, QColor(255, 210, 0, 175))
            rad.setColorAt(0.7, QColor(0, 255, 140, 100))
            rad.setColorAt(1.0, QColor(0, 140, 255, 0))
            p.setBrush(rad)
            p.setPen(no_pen)
            p.drawEllipse(QPointF(sx, sy), radius, radius)
        p.end()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme

        if not self.is_active:
            p.setOpacity(0.35)

        if self.pitch_base_cache:
            p.drawPixmap(0, 0, self.pitch_base_cache)
        if self.heatmap_cache:
            p.drawPixmap(0, 0, self.heatmap_cache)

        if not self.is_active:
            p.setOpacity(1.0)
            w, h = self.width(), self.height()
            p.setBrush(QColor(4, 12, 24, 195))
            p.setPen(QPen(theme.primary, 1.2))
            badge_w, badge_h = 190, 36
            badge_rect = QRectF((w - badge_w) / 2, (h - badge_h) / 2, badge_w, badge_h)
            p.drawRoundedRect(badge_rect, 8, 8)
            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if IS_PYQT6 else 75))
            p.setPen(QColor(148, 163, 184))
            p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter, "MOD DEACTIVATED")

# -------------------------------------------------------------
# 10. Blinking Alert Button
# -------------------------------------------------------------
class BlinkingAlertButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(320, 34)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.has_issue = True
        self.blink_phase = 0.0

    def advance_pulse(self):
        self.blink_phase = (self.blink_phase + 0.08) % (2 * math.pi)
        self.update()

    def setStatus(self, has_issue):
        self.has_issue = has_issue
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        w, h = self.width(), self.height()
        radius = 9.0

        if self.has_issue:
            intensity = 0.5 + 0.5 * math.sin(self.blink_phase)
            bg_alpha = int(45 + 55 * intensity)
            border_alpha = int(140 + 115 * intensity)

            p.setBrush(QColor(255, 0, 50, bg_alpha))
            p.setPen(QPen(QColor(255, 40, 70, border_alpha), 1.3))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if IS_PYQT6 else 75))
            p.setPen(QColor(255, 120, 140))
            rect = self.rect()
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter, "⚠  ISSUE DETECTED • CLICK TO RESOLVE")
        else:
            p.setBrush(QColor(0, 190, 100, 35))
            p.setPen(QPen(QColor(0, 255, 140, 190), 1.3))
            p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

            p.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if IS_PYQT6 else 75))
            p.setPen(QColor(110, 255, 190))
            rect = self.rect()
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter, "✔  ALL CHECKS PASSED • FL 2026 READY")

# -------------------------------------------------------------
# 11. Diagnostic Cyber Card with Lagging Light Halo
# -------------------------------------------------------------
class DiagnosticCyberCard(QFrame):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self.setMouseTracking(True)

        self.target_x = 350.0
        self.target_y = 250.0
        self.glow_x = 350.0
        self.glow_y = 250.0

        self.halo_timer = QTimer(self)
        self.halo_timer.timeout.connect(self.update_lagging_halo)
        self.halo_timer.start(16)

    def mouseMoveEvent(self, event):
        pos = event.position() if hasattr(event, "position") else event.pos()
        self.target_x = pos.x()
        self.target_y = pos.y()
        super().mouseMoveEvent(event)

    def update_lagging_halo(self):
        dx = self.target_x - self.glow_x
        dy = self.target_y - self.glow_y
        if abs(dx) > 0.15 or abs(dy) > 0.15:
            self.glow_x += dx * 0.08
            self.glow_y += dy * 0.08
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        radius = 18.0

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(theme.bg_dark[1].red(), theme.bg_dark[1].green(), theme.bg_dark[1].blue(), 252))
        grad.setColorAt(0.4, QColor(theme.bg_dark[2].red(), theme.bg_dark[2].green(), theme.bg_dark[2].blue(), 253))
        grad.setColorAt(1.0, QColor(theme.bg_dark[3].red(), theme.bg_dark[3].green(), theme.bg_dark[3].blue(), 255))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        grid_pen = QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 14), 1)
        p.setPen(grid_pen)
        grid_step = 28
        for x in range(grid_step, int(w), grid_step):
            p.drawLine(x, 10, x, int(h) - 10)
        for y in range(grid_step, int(h), grid_step):
            p.drawLine(10, y, int(w) - 10, y)

        halo = QRadialGradient(self.glow_x, self.glow_y, 145.0)
        halo.setColorAt(0.0, QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 38))
        halo.setColorAt(0.45, QColor(theme.secondary.red(), theme.secondary.green(), theme.secondary.blue(), 18))
        halo.setColorAt(0.8, QColor(theme.secondary.red(), theme.secondary.green(), theme.secondary.blue(), 6))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(halo)
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)

        border_grad = QLinearGradient(0, 0, w, h)
        border_grad.setColorAt(0.0, theme.primary)
        border_grad.setColorAt(0.5, theme.secondary)
        border_grad.setColorAt(1.0, theme.accent)
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(QPen(border_grad, 1.4))
        p.drawRoundedRect(QRectF(1.2, 1.2, w - 2.4, h - 2.4), radius, radius)

        p.setPen(QPen(theme.primary, 2.2))
        accent_len = 16.0
        p.drawLine(QPointF(radius, 1.2), QPointF(radius + accent_len, 1.2))
        p.drawLine(QPointF(1.2, radius), QPointF(1.2, radius + accent_len))
        p.drawLine(QPointF(w - radius - accent_len, 1.2), QPointF(w - radius, 1.2))
        p.drawLine(QPointF(w - 1.2, radius), QPointF(w - 1.2, radius + accent_len))

# =============================================================================
# =============================================================================
CONFIG_FILE = "ModsConfig.json"
TARGET_PROCESS = "FL_2026.exe"

DEFAULT_REF_SETTINGS = {
    "enabled": False,
    "overlay": True,
    "vk": "0x54",
    "name": "T",
    "url": "",
}

# ------------------------------------------------------------------
# ------------------------------------------------------------------
REF_MOD_FOLDER = os.path.join(APP_DIR, "RefereeView")
REF_PREVIEW_FILE = os.path.join(REF_MOD_FOLDER, "RefereePreview.png")
REF_OVERLAY_FILE = os.path.join(REF_MOD_FOLDER, "RefereeOverlay.png")
REF_OVERLAY_RECT = (0.7989, 0.7692, 0.1407, 0.0880)

# ------------------------------------------------------------------
# Goal Line Technology settings — default OFF.
#   play_vk / play_name : play-animation key (default F8), stored as hex VK
#                         so it is keyboard-layout independent.
#   rec_vk  / rec_name  : manual record key (default F7). F7 used to open the
#                         old GLT window; now it ONLY starts manual recording.
#   style               : "T5" (Style 1) or "T6" (Style 2) animation scene.
#
# ------------------------------------------------------------------
# v1.0.0 — ONLINE UPDATE CHECK + YOUTUBE TUTORIALS (the developer Gist)
# The launcher reads ONE plain-text Gist for two features, strictly ON
# DEMAND (never at import time, never preloaded):
#   * UPDATE CHECK — "Latest Version" vs APP_VERSION. When it is higher,
#     a modal pops up on program entry with a glass DOWNLOAD UPDATE pill
#     that opens the "Github Link" ("null" -> friendly try-later error).
#   * YOUTUBE TUTORIALS — every mod's tutorial button fetches the Gist at
#     CLICK TIME and opens that mod's line ("SAOT Tut", "GLT Tut",
#     "Referee Tut", "Momentum Tut", "HeatMap Tut"). A "null" line (or an
#     unreachable Gist with no local fallback) shows the try-later error.
#   * CONTACT BADGES (v1.0.1) — the ABOUT window's YouTube / Instagram /
#     Telegram / E-mail badges also fetch the Gist AT CLICK TIME and open
#     their own line ("Youtube", "Instagram", "Telegram", "E-mail"); same
#     null / offline-fallback policy as the tutorials. The GitHub badge
#     opens the developer's Gist page on github.com directly (GIST_PAGE_URL
#     below) — always available, no fetch, no configuration.
# Gist layout (plain text, "Key: value" lines, "null" = not published):
#   Latest Version: 1.0.0
#   Github Link: null
#   SAOT Tut: null
#   GLT Tut: null
#   Referee Tut: null
#   Momentum Tut: null
#   HeatMap Tut: null
#   Youtube: null
#   Instagram: null
#   Telegram: null
#   E-mail: null
# The developer edits the Gist online — the program never needs a new
# build just to publish a new link.
# ------------------------------------------------------------------
GIST_PAGE_URL = ("https://gist.github.com/miladeazkat-maker/"
                 "6c355f2bdbf7c87424601437891dd9fa")
UPDATE_GIST_RAW_URL = ("https://gist.githubusercontent.com/miladeazkat-maker/"
                       "6c355f2bdbf7c87424601437891dd9fa/raw/gistfile1.txt")
GIST_API_URL = "https://api.github.com/gists/6c355f2bdbf7c87424601437891dd9fa"
APP_VERSION = "1.0.0"
# The entry check pops the UPDATE AVAILABLE modal on program entry. Flip
# to False to make checking strictly manual (ABOUT -> CHECKING FOR UPDATES).
UPDATE_CHECK_AT_STARTUP = True
GIST_FETCH_TIMEOUT = 8.0
GIST_TUTORIAL_KEYS = ("SAOT", "GLT", "REFEREE", "MOMENTUM", "HEATMAP")
_GIST_NULL_VALUES = ("", "null", "none", "n/a", "tbd", "todo", "-")


def _gist_clean_value(value):
    v = str(value or "").strip()
    return "" if v.lower() in _GIST_NULL_VALUES else v


def parse_update_manifest(text):
    """Parse the Gist's plain-text 'Key: value' lines into a manifest:
    {"latest_version": str|None, "github": str|None,
     "tutorials": {"SAOT": str|None, "GLT": ..., "REFEREE": ...,
                    "MOMENTUM": ..., "HEATMAP": ...},
     "social": {"YOUTUBE": str|None, "INSTAGRAM": ..., "TELEGRAM": ...,
                "EMAIL": ...}}
    Returns None when the text is not a manifest (no Latest Version line)."""
    if not text:
        return None
    manifest = {"latest_version": None, "github": None,
                "tutorials": {}, "social": {}}
    seen_version = False
    for raw_line in str(text).splitlines():
        if ":" not in raw_line:
            continue
        key, _, value = raw_line.partition(":")
        key = key.strip().lower()
        value = _gist_clean_value(value)
        if key == "latest version":
            manifest["latest_version"] = value or None
            seen_version = True
        elif key in ("github link", "github"):
            manifest["github"] = value or None
        elif key.endswith(" tut") or key.endswith(" tutorial"):
            mod = (key[:-4] if key.endswith(" tut") else key[:-9]).strip()
            mod = re.sub(r"[^a-z0-9]", "", mod).upper()
            if mod:
                manifest["tutorials"][mod] = value or None
        else:
            # v1.0.1 — social contact lines: Youtube / Instagram / Telegram
            # / E-mail ("e-mail", "e mail", "email", "mail" all accepted).
            soc = re.sub(r"[^a-z]", "", key)
            if soc == "mail":
                soc = "email"
            if soc in ("youtube", "instagram", "telegram", "email"):
                manifest["social"][soc.upper()] = value or None
    return manifest if seen_version else None


def _version_tuple(value):
    nums = re.findall(r"\d+", str(value or ""))
    if not nums:
        return None
    return tuple(int(n) for n in nums[:4])


def version_is_newer(latest, current):
    """True when latest > current (dotted numeric compare; 'v' prefixes,
    missing parts and junk all fail safe to False -> no nag modal)."""
    a, b = _version_tuple(latest), _version_tuple(current)
    if a is None or b is None:
        return False
    n = max(len(a), len(b))
    a += (0,) * (n - len(a))
    b += (0,) * (n - len(b))
    return a > b


def _gist_http_get(url, timeout):
    req = urllib.request.Request(url, headers={
        "User-Agent": "MyMods-Launcher/" + APP_VERSION,
        "Accept": "*/*",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _gist_api_text(timeout):
    """Fallback path: the GitHub API JSON of the same Gist (used when the
    raw endpoint is unreachable). Returns the manifest file's content."""
    raw = _gist_http_get(GIST_API_URL, timeout)
    data = json.loads(raw)
    files = (data or {}).get("files") or {}
    first = None
    for info in files.values():
        text = str((info or {}).get("content") or "")
        if not text:
            continue
        if "latest version" in text.lower():
            return text
        if first is None:
            first = text
    return first


def fetch_update_manifest(timeout=GIST_FETCH_TIMEOUT):
    """Fetch + parse the developer Gist. Returns the manifest dict, or
    None when the Gist cannot be reached / parsed (offline, timeout)."""
    try:
        manifest = parse_update_manifest(
            _gist_http_get(UPDATE_GIST_RAW_URL, timeout))
        if manifest is not None:
            return manifest
    except Exception:
        pass
    try:
        return parse_update_manifest(_gist_api_text(timeout))
    except Exception:
        return None


class GistSignalBus(QObject):
    """Cross-thread bridge: the Gist fetch runs in a daemon thread and
    hands its result back to the GUI thread through these queued signals."""
    update_checked = pyqtSignal(object, bool)        # manifest|None, manual
    tutorial_fetched = pyqtSignal(str, str, object)  # mod_key, fallback, manifest|None
    contact_fetched = pyqtSignal(str, str, object)   # kind, fallback, manifest|None (v1.0.1)


# ------------------------------------------------------------------
# YouTube tutorial FALLBACK links — only used when the Gist cannot be
# reached (offline). Since v1.0.0 the PRIMARY source is the Gist above:
# a "null" line in the Gist means "not published yet", even when a
# constant below is filled. Normally just leave these empty.
# ------------------------------------------------------------------
REF_TUTORIAL_URL = ""          # local fallback for the Gist's "Referee Tut"
GLT_TUTORIAL_URL = ""          # local fallback for the Gist's "GLT Tut"

DEFAULT_GLT_SETTINGS = {
    "enabled": False,
    "play_vk": "0x77",            # F8
    "play_name": "F8",
    "rec_vk": "0x76",             # F7
    "rec_name": "F7",
    "style": "T6",
}
GLT_MOD_NAME = "Goal Line Technology"
GLT_MOD_FOLDER = os.path.join(APP_DIR, "GLT")
GLT_PREVIEW_FILE = os.path.join(GLT_MOD_FOLDER, "GLTPreview.png")
GLT_TEX_DIR = os.path.join(GLT_MOD_FOLDER, "tex")

# ------------------------------------------------------------------
# GLT style PREVIEW images (16:9 landscape, one per animation style).
# The old 178x104 style-button thumbnails were removed — the main MOD
# PREVIEW box now shows the preview of the CURRENTLY selected style and
# swaps the image automatically whenever the style changes.
#   Style 1 (T5) ->  GLT/GLTPreview_T5.png
#   Style 2 (T6) ->  GLT/GLTPreview_T6.png
# Recommended size: 1920 x 1080 (any 16:9 image works; it is displayed
# at 400 x 225). If a per-style file is missing the box falls back to
# the bundled GLTPreview.png, then to a placeholder text.
# ------------------------------------------------------------------
GLT_PREVIEW_T5_FILE = os.path.join(GLT_MOD_FOLDER, "GLTPreview_T5.png")
GLT_PREVIEW_T6_FILE = os.path.join(GLT_MOD_FOLDER, "GLTPreview_T6.png")

# ------------------------------------------------------------------
# Animated VIDEO background — Background/Back.mp4 (user-provided,
# 1920 x 1080, looks identical to the previously painted gradient).
# The video is rendered by the GPU: OS/hardware-decoded playback
# (QMediaPlayer -> QVideoSink) plus a fragment shader that applies a
# per-mod color grade (hue rotation + saturation/brightness/contrast)
# so the very same clip matches each mod's color scheme. The grade is
# derived automatically from the live (interpolating) theme color, so
# it even animates smoothly while the theme morphs between mods.
# Manual per-mod overrides can be added to MOD_VIDEO_GRADE_OVERRIDES.
# ------------------------------------------------------------------
BACKGROUND_FOLDER = os.path.join(APP_DIR, "Background")
BACKGROUND_VIDEO_FILE = os.path.join(BACKGROUND_FOLDER, "Back.mp4")
BACKGROUND_VIDEO_CORNER_RADIUS = 22.0   # matches the window's rounded frame

# Donation link used by the DONATE buttons and the exit prompt (v1.0.0b —
# LIVE: every DONATE button opens the developer's NOWPayments page in the
# browser).  Leave it empty to fall back to the friendly thank-you message.
DONATE_URL = "https://nowpayments.io/donation/Milad"

# ------------------------------------------------------------------
# [v2.2.0 -> v1.0.0] UPDATE CHECKING moved to the developer Gist (see the
# Gist block near the top of this file) — this placeholder is retired.
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# [v2.1.9 / v1.0.1] CONTACT THE DEVELOPER — five hand-painted glass
# badges (YouTube / Instagram / Telegram / E-mail / GitHub) live in the
# ABOUT window's contact centre: report a bug / suggest a feature.
# v1.0.1 — the four social links are fetched from the developer Gist AT
# CLICK TIME ("Youtube" / "Instagram" / "Telegram" / "E-mail" lines;
# "null" -> friendly try-again note), so the constants below are ONLY
# offline fallbacks used when the Gist cannot be reached — normally
# leave them empty. The GitHub badge opens the developer's Gist page on
# github.com (GIST_PAGE_URL) directly — always available, no fetch.
# ------------------------------------------------------------------
CONTACT_YOUTUBE_URL = ""      # e.g. "https://youtube.com/@yourchannel"
CONTACT_INSTAGRAM_URL = ""    # e.g. "https://instagram.com/yourname"
CONTACT_TELEGRAM_URL = ""     # e.g. "https://t.me/yourchannel"
CONTACT_EMAIL_ADDRESS = ""    # e.g. "milad.mods@gmail.com"

# ------------------------------------------------------------------
# [v2.1.9] FL 2026 DOWNLOAD PAGE — opened when the user CLICKS the big
# "FL 2026" name in the top box of the header.
# ------------------------------------------------------------------
FL2026_DOWNLOAD_URL = "https://www.pessmokepatch.com/2025/10/spfl26.html"

# Base hue of the clip = the hue of the default (S.A.O.T) theme primary
# (#00f0ff); every other mod's grade is computed as the shortest hue
# distance from this color, so the default theme is exactly neutral.
def _base_hue_of_clip():
    try:
        h = QColor("#00f0ff").hueF()
        if h is not None and h >= 0.0:
            return h
    except Exception:
        pass
    return 0.5111


BACKGROUND_GRADE_BASE_HUE = _base_hue_of_clip()

# Optional manual overrides:  mod name -> {hue, saturation, brightness,
# contrast}.  hue = degrees (-180..180), the rest are multipliers
# (1.0 = neutral). Empty by default — the automatic theme-derived grade
# already matches each mod's scheme.
MOD_VIDEO_GRADE_OVERRIDES = {
    # "Goal Line Technology": {"hue": -33.0, "saturation": 1.15},
}


def video_grade_for_theme(theme):
    """Automatic color grade (tint/saturation/brightness/contrast) that
    retints the base video toward the current theme. Returns a dict of
    shader-ready values. Applied per frame, so theme transitions morph
    the background smoothly.

    v2.1.2 — the source clip (Back.mp4) is BLACK & WHITE, so EVERY theme
    needs a real tint. The old strength formula scaled the tint by the
    hue DISTANCE from the clip's base hue, which left near-base-hue
    themes (S.A.O.T itself, Quantum Teal, ...) practically uncolored —
    the video stayed grey on those mods. Strength now follows the
    theme's own saturation instead: every chromatic theme gets a full,
    vivid tint; hue distance no longer matters."""
    hue = 0.0
    sat = 1.0
    strength = 0.0
    try:
        c = theme.primary
        if c.saturationF() >= 0.02 and c.hueF() >= 0.0:
            # shortest-path hue rotation, result in degrees -180..180
            # (kept for the optional manual overrides below)
            d = (c.hueF() - BACKGROUND_GRADE_BASE_HUE + 0.5) % 1.0 - 0.5
            hue = d * 360.0
            # v2.1.2 — saturation-driven tint strength: vivid themes
            # (all shipped ones are) always reach full tint.
            strength = min(1.0, 0.55 + 0.45 * min(1.0, c.saturationF() * 1.25))
            # gentle saturation boost so the grey clip picks up the hue
            sat = 1.0 + 0.10 * c.saturationF()
    except Exception:
        hue, sat, strength = 0.0, 1.0, 0.0
    grade = {"hue": hue, "saturation": sat, "brightness": 1.0, "contrast": 1.0,
             "tint_strength": strength, "hue_is_override": False}
    try:
        ov = MOD_VIDEO_GRADE_OVERRIDES.get(theme.name)
        if isinstance(ov, dict):
            for k in ("hue", "saturation", "brightness", "contrast",
                      "tint_strength"):
                if k in ov:
                    grade[k] = float(ov[k])
            if "hue" in ov:
                grade["hue_is_override"] = True
    except Exception:
        pass
    return grade

# ------------------------------------------------------------------
# MOD PREVIEW standard size — every user-provided preview image is
# 16:9 landscape; all mod preview boxes now use the same compact slot
# (previously the boxes stretched over the whole page bottom).
# ------------------------------------------------------------------
PREVIEW_BOX_W = 400
PREVIEW_BOX_H = 225            # exactly 16:9

# Mods that already have a working page. Every other row in the Mods
# Manager gets a small "COMING SOON" badge next to its name.


# ------------------------------------------------------------------
# HEAT MAP — settings stored in ModsConfig.json under
# mods -> "Heat Map" (hm_* keys). The backend (HeatMap/HeatMapMod.py)
# receives them through the bridge (MODBRIDGE_SETTINGS env) AND reads
# the same block directly. The display minute is the user spec: 71-79
# (default 75); viewer side picks which team's players are eligible
# for the automatic heat map (random = original behaviour).
# ------------------------------------------------------------------
HEATMAP_MOD_NAME = "Heat Map"
HEATMAP_MOD_FOLDER = os.path.join(APP_DIR, "HeatMap")

DEFAULT_HEATMAP_SETTINGS = {
    "hm_display_minute": 75,      # auto display minute (71..79)
    "hm_viewer_side": "random",   # random | home | away
    "hm_gain": 3.3,               # sensitivity        0.2..8.0
    "hm_ceiling": 0.4,            # heat ceiling (s)   0.1..8.0
    "hm_gamma": 0.85,             # gamma              0.2..1.5
    "hm_blur_m": 1.4,             # softness (m)       0.5..3.0
    "hm_feather": 9.0,            # edge feather (px)  0..25
    "hm_cutoff": 0.2,             # minimum filter     0..0.35
}
HEATMAP_DISPLAY_RANGE = (71, 79)


def heatmap_clamp_display_minute(value):
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        return DEFAULT_HEATMAP_SETTINGS["hm_display_minute"]
    return max(HEATMAP_DISPLAY_RANGE[0], min(HEATMAP_DISPLAY_RANGE[1], v))


def heatmap_clamp_side(value):
    s = str(value or "random").strip().lower()
    return s if s in ("random", "home", "away") else "random"


def heatmap_clamp_float(value, lo, hi, default):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float(default)
    return max(lo, min(hi, v))

# ------------------------------------------------------------------
# [suite v2.1.7] S.A.O.T — SEMI-AUTOMATED OFFSIDE TECHNOLOGY (new mod)
# The original standalone tool (v1.2.0 by Milad77) is now a suite mod:
#   * FL 2026 is the ONLY supported game (all other game versions were
#     removed from the tool, user spec #2);
#   * English is the ONLY language (user spec #4);
#   * the tool itself has NO settings and NO training sections any more
#     — MyMods hosts the dedicated menu with the single CALL KEY option
#     (user spec #3) and the ReShade setup section (user spec #6);
#   * the tool GUI is summoned in-game with the call key (user spec #5);
#   * the tool hooks NOTHING and asks the Bridge for the game process
#     (user spec #8);
#   * the ReShade files + tutorial images live in SAOTMod\\textut
#     (user spec #6/#7).
# ------------------------------------------------------------------
SAOT_MOD_NAME = "S.A.O.T"
SAOT_MOD_FOLDER = os.path.join(APP_DIR, "SAOTMod")
SAOT_PREVIEW_FILE = os.path.join(SAOT_MOD_FOLDER, "SAOTPreview.png")
SAOT_TEXTUT_DIR = os.path.join(SAOT_MOD_FOLDER, "textut")
SAOT_TUTORIAL_URL = ""        # local fallback for the Gist's "SAOT Tut"
# The ONLY option of the SAOT menu: the CALL KEY that shows/hides the
# tool's GUI in-game (default F1 — the original tool's own default).
DEFAULT_SAOT_SETTINGS = {"call_vk": "0x70", "call_name": "F1"}
# ReShade — the mod depends on it. MyMods checks the MAIN GAME
# FOLDER and copies the 2026 files from SAOTMod\\textut (user spec #6).
RESHADE_DOWNLOAD_URL = "https://reshade.me/"
RESHADE_SHADER_2026 = "OffsidePlane.fx"             # the 2026 shader
RESHADE_SHADER_2017 = "OffsidePlane(PES_2017).fx"   # old variant = NOT 2026
RESHADE_TEXTURE = "Offside_Tex.png"

def saot_reshade_status(game_dir, textut_dir=None):
    """ReShade status inside the MAIN GAME FOLDER (user spec #6).

    Checks, relative to game_dir:
      * ReShade software — reshade-shaders folder or a ReShade dll;
      * the 2026 offside shader  — Shaders/OffsidePlane.fx;
      * the old 2017 shader — Shaders/OffsidePlane(PES_2017).fx
        (its presence means the installed version is NOT 2026);
      * the offside texture — Textures/Offside_Tex.png.
    Also verifies the COPY SOURCE (SAOTMod\\textut) so the UI can disable
    the copy button when the files are not shipped.
    Returns a plain dict — never raises (missing folder = False flags)."""
    if textut_dir is None:
        textut_dir = SAOT_TEXTUT_DIR
    gd = str(game_dir or "")
    out = {
        "game_dir": gd,
        "game_dir_ok": bool(gd) and os.path.isdir(gd),
        "reshade_ok": False,
        "reshade_marker": "",
        "fx_2026": False,
        "fx_2017": False,
        "tex": False,
        "version_2026": False,
        "files_ok": False,
        "need_copy": False,
        "need_download": False,
        "shaders_dir": "",
        "source_fx": False,
        "source_tex": False,
        "source_ok": False,
        "textut_dir": textut_dir,
    }
    if not out["game_dir_ok"]:
        out["need_download"] = True
        return out
    shaders_dir = os.path.join(gd, "reshade-shaders")
    out["shaders_dir"] = shaders_dir
    # ReShade marker: the shaders folder (the original tool's own check)
    # or a ReShade injection dll next to the game exe.
    if os.path.isdir(shaders_dir):
        out["reshade_ok"] = True
        out["reshade_marker"] = "reshade-shaders folder"
    else:
        for dll in ("dxgi.dll", "d3d11.dll", "d3d9.dll", "ReShade64.dll",
                    "ReShade32.dll"):
            if os.path.exists(os.path.join(gd, dll)):
                out["reshade_ok"] = True
                out["reshade_marker"] = dll
                break
    fx26 = os.path.join(shaders_dir, "Shaders", RESHADE_SHADER_2026)
    fx17 = os.path.join(shaders_dir, "Shaders", RESHADE_SHADER_2017)
    tex = os.path.join(shaders_dir, "Textures", RESHADE_TEXTURE)
    out["fx_2026"] = os.path.exists(fx26)
    out["fx_2017"] = os.path.exists(fx17)
    out["tex"] = os.path.exists(tex)
    out["version_2026"] = out["fx_2026"] and not out["fx_2017"]
    out["files_ok"] = out["version_2026"] and out["tex"]
    # ReShade missing           -> show the DOWNLOAD key
    # files missing / not 2026  -> show the COPY key
    out["need_download"] = not out["reshade_ok"]
    out["need_copy"] = out["reshade_ok"] and not out["files_ok"]
    out["source_fx"] = os.path.exists(os.path.join(textut_dir,
                                                   RESHADE_SHADER_2026))
    out["source_tex"] = os.path.exists(os.path.join(textut_dir,
                                                    RESHADE_TEXTURE))
    out["source_ok"] = out["source_fx"] and out["source_tex"]
    return out

def saot_copy_reshade_files(game_dir, textut_dir=None):
    """Copy the 2026 ReShade files from SAOTMod\\textut into the MAIN GAME
    FOLDER (user spec #6): OffsidePlane.fx -> reshade-shaders\\Shaders,
    Offside_Tex.png -> reshade-shaders\\Textures; a stale 2017 shader is
    removed so the installed version becomes exactly 2026.
    Returns (ok, english_message)."""
    if textut_dir is None:
        textut_dir = SAOT_TEXTUT_DIR
    st = saot_reshade_status(game_dir, textut_dir)
    if not st["game_dir_ok"]:
        return False, "Main game folder is not set — choose it in SETTINGS."
    if not st["source_fx"] or not st["source_tex"]:
        return False, ("The source files are missing in SAOTMod\\textut "
                       "(OffsidePlane.fx / Offside_Tex.png).")
    try:
        sh_dir = os.path.join(st["shaders_dir"], "Shaders")
        tx_dir = os.path.join(st["shaders_dir"], "Textures")
        os.makedirs(sh_dir, exist_ok=True)
        os.makedirs(tx_dir, exist_ok=True)
        shutil.copy(os.path.join(textut_dir, RESHADE_SHADER_2026),
                    os.path.join(sh_dir, RESHADE_SHADER_2026))
        shutil.copy(os.path.join(textut_dir, RESHADE_TEXTURE),
                    os.path.join(tx_dir, RESHADE_TEXTURE))
        old_fx = os.path.join(sh_dir, RESHADE_SHADER_2017)
        if os.path.exists(old_fx):
            os.remove(old_fx)
        return True, ("2026 files copied successfully into the game "
                      "folder (reshade-shaders).")
    except Exception as e:
        return False, "Error copying files: %s" % e

IMPLEMENTED_MOD_NAMES = ("Referee View", GLT_MOD_NAME, "Match Momentum",
                         HEATMAP_MOD_NAME, SAOT_MOD_NAME)

# ------------------------------------------------------------------
# [v2.1.6] MOD CATEGORIES — the mods manager groups the 11 mods into
# three collapsible families (user spec #10):
#   1. VAR MODS        — S.A.O.T + Goal Line Technology
#   2. CAMERA MODS     — Referee View + FOV Gaming + New Replay View
#   3. MATCH ANALYSIS  — every remaining mod
# Inside every category the PUBLISHED (working) mods are listed first
# and the coming-soon mods keep their relative order after them.
# The last expanded/collapsed state of every category is persisted in
# ModsConfig.json under "ui" -> "expanded" and restored on startup.
# ------------------------------------------------------------------
MOD_CATEGORIES = (
    ("VAR MODS", ("S.A.O.T", GLT_MOD_NAME)),
    ("CAMERA MODS", ("Referee View", "FOV Gaming", "New Replay View")),
    ("MATCH ANALYSIS", ("Match Momentum", HEATMAP_MOD_NAME, "Shots Info",
                        "3D Analysis", "Penalty Data", "Players Speed")),
)

def ordered_category_members(members):
    """Published mods first, then the not-yet-submitted ones (stable)."""
    live = [n for n in members if n in IMPLEMENTED_MOD_NAMES]
    soon = [n for n in members if n not in IMPLEMENTED_MOD_NAMES]
    return live + soon

# ------------------------------------------------------------------
# GAMEPAD BUTTONS — read automatically, never typed by the user anymore.
# The game stores the keyboard binding of every replay/gamepad action as a
# Make Code (scan code of the pressed key, e.g. M = 0x32) inside the SAME
# binary settings file that also stores Windowed/Fullscreen mode:
#   Documents\KONAMI\eFootball PES 2021 SEASON UPDATE\settings.dat
# The values below are the file offsets of each binding. The UI shows the
# English button name; clicking it opens a small modal with the live value
# (address + make code + English key name) read straight from that file.
# ------------------------------------------------------------------
GLT_GAMEPAD_BINDINGS = [
    ("L1",        0x000041),
    ("RIGHT VIEW", 0x000053),
    ("LEFT VIEW",  0x000051),
    ("CIRCLE",     0x000039),
    ("TRIANGLE",   0x00003B),
]

# IBM Set-1 Make Code -> English key name (covers everything the game can
# store for these bindings; unknown codes are shown as raw hex).
SCAN_CODE_NAMES = {
    0x01: "ESC", 0x02: "1", 0x03: "2", 0x04: "3", 0x05: "4", 0x06: "5",
    0x07: "6", 0x08: "7", 0x09: "8", 0x0A: "9", 0x0B: "0",
    0x0C: "MINUS", 0x0D: "EQUALS", 0x0E: "BACKSPACE", 0x0F: "TAB",
    0x10: "Q", 0x11: "W", 0x12: "E", 0x13: "R", 0x14: "T", 0x15: "Y",
    0x16: "U", 0x17: "I", 0x18: "O", 0x19: "P", 0x1A: "[", 0x1B: "]",
    0x1C: "ENTER", 0x1D: "LEFT CTRL", 0x1E: "A", 0x1F: "S", 0x20: "D",
    0x21: "F", 0x22: "G", 0x23: "H", 0x24: "J", 0x25: "K", 0x26: "L",
    0x27: "SEMICOLON", 0x28: "APOSTROPHE", 0x29: "`", 0x2A: "LEFT SHIFT",
    0x2B: "BACKSLASH", 0x2C: "Z", 0x2D: "X", 0x2E: "C", 0x2F: "V",
    0x30: "B", 0x31: "N", 0x32: "M", 0x33: "COMMA", 0x34: "PERIOD",
    0x35: "SLASH", 0x36: "RIGHT SHIFT", 0x37: "NUM *", 0x38: "LEFT ALT",
    0x39: "SPACE", 0x3A: "CAPS LOCK", 0x3B: "F1", 0x3C: "F2", 0x3D: "F3",
    0x3E: "F4", 0x3F: "F5", 0x40: "F6", 0x41: "F7", 0x42: "F8", 0x43: "F9",
    0x44: "F10", 0x45: "NUM LOCK", 0x46: "SCROLL LOCK", 0x47: "HOME",
    0x48: "UP ARROW", 0x49: "PAGE UP", 0x4A: "NUM -", 0x4B: "LEFT ARROW",
    0x4C: "NUM 5", 0x4D: "RIGHT ARROW", 0x4E: "NUM +", 0x4F: "END",
    0x50: "DOWN ARROW", 0x51: "PAGE DOWN", 0x52: "INSERT", 0x53: "DELETE",
    0x57: "F11", 0x58: "F12",
}


def make_code_to_key_name(code):
    """Make Code (scan code) -> English key name; None for unbound."""
    try:
        code = int(code) & 0xFF
    except (TypeError, ValueError):
        return None
    if code == 0x00:
        return None
    return SCAN_CODE_NAMES.get(code, "KEY 0x%02X" % code)


def read_glt_gamepad_bindings(path=None):
    """Read every GLT gamepad binding straight from the game settings binary.

    Returns {label: {"offset": int, "ok": bool, "code": int|None, "file": str}}.
    'ok' is False when settings.dat is missing or too small — the UI then
    shows N/A for that binding (never a crash).
    """
    if path is None:
        path = get_settings_dat_path()
    result = {}
    data = b""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        data = b""
    for label, offset in GLT_GAMEPAD_BINDINGS:
        ok = len(data) > offset
        result[label] = {
            "offset": offset,
            "ok": ok,
            "code": data[offset] if ok else None,
            "file": path,
        }
    return result


# ------------------------------------------------------------------
# GLT ANIMATION BUTTON BINDINGS — automatic, zero user input.
# The dedicated GLT tool has five "Animation Button Bindings" (its panel
# rows: Right Arrow / Left Arrow / L1 / Triangle / Circle). Those keys are
# NOT typed by the user and NOT set in the tool any more: MyMods reads the
# game's own keymap from settings.dat (via read_glt_gamepad_bindings above),
# converts every Make Code into the key-name format the tool understands
# ('d', 'q', 'left', 'space', ...) and stores the result in ModsConfig.json
# under mods -> "Goal Line Technology" -> glt_key_*.
# The GLT tool loads ONLY this JSON at startup, so the bindings still reach
# it even when MyMods itself is not running.
# ------------------------------------------------------------------
_GLTPANEL_TO_SETTINGS_LABELS = (
    # (ModsConfig key,  settings.dat binding label, GLT panel row)
    ("glt_key_action", "RIGHT VIEW", "Right Arrow Key"),
    ("glt_key_back",   "LEFT VIEW",  "Left Arrow Key"),
    ("glt_key_q",      "L1",         "L1 Key"),
    ("glt_key_w",      "TRIANGLE",   "Triangle Key"),
    ("glt_key_d",      "CIRCLE",     "Circle Key"),
)

# SCAN_CODE_NAMES entries -> the key names GLT's get_vk() understands.
_SCAN_CODE_GLT_NAME_MAP = {
    "UP ARROW": "up", "LEFT ARROW": "left", "RIGHT ARROW": "right",
    "DOWN ARROW": "down", "SPACE": "space", "ENTER": "enter",
    "LEFT CTRL": "ctrl", "RIGHT CTRL": "ctrl",
    "LEFT SHIFT": "shift", "RIGHT SHIFT": "shift",
    "LEFT ALT": "alt", "BACKSPACE": "backspace", "TAB": "tab",
}


def scan_code_to_glt_key(code):
    """settings.dat Make Code -> key name accepted by the GLT tool.

    Returns '' for unbound (0x00) / unknown codes — the caller then keeps
    the previous binding instead of writing something the tool cannot use.
    """
    try:
        code = int(code) & 0xFF
    except (TypeError, ValueError):
        return ""
    if code == 0x00:
        return ""
    name = SCAN_CODE_NAMES.get(code)
    if not name:
        return ""
    if name in _SCAN_CODE_GLT_NAME_MAP:
        return _SCAN_CODE_GLT_NAME_MAP[name]
    return name.lower() if len(name) == 1 else ""


def glt_animation_keys_from_settings_dat(path=None):
    """Build the GLT animation-button bindings from the game settings file.

    Returns {"glt_key_action": "d", ...} — only bindings that were actually
    read from settings.dat are included; an empty dict means "keep whatever
    is already stored" (missing file, unreadable, nothing bound).
    """
    bindings = read_glt_gamepad_bindings(path)
    keys = {}
    for cfg_key, label, _row in _GLTPANEL_TO_SETTINGS_LABELS:
        info = bindings.get(label) or {}
        if not info.get("ok"):
            continue
        name = scan_code_to_glt_key(info.get("code"))
        if name:
            keys[cfg_key] = name
    return keys


def apply_glt_animation_keys_to_config():
    """Refresh ModsConfig.json with the settings.dat-driven GLT bindings.

    Reads the existing config (created by MyMods.save_config), updates ONLY
    the five glt_key_* values and writes it back. Safe to call at any time —
    a missing/corrupt file or a missing settings.dat is a silent no-op that
    leaves the tool's current bindings untouched.
    """
    try:
        keys = glt_animation_keys_from_settings_dat()
        if not keys:
            return False
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return False
        glt = (cfg.setdefault("mods", {})).setdefault(GLT_MOD_NAME, {})
        glt.update(keys)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

# ------------------------------------------------------------------
# GLT preview images — EXACT DIMENSIONS / FILE NAMES
# ------------------------------------------------------------------
# 1) ANIMATION STYLE previews (replaces the old style-button thumbnails):
#      - GLT/GLTPreview_T5.png  (Style 1)
#      - GLT/GLTPreview_T6.png  (Style 2)
#      - 16:9 landscape, recommended 1920 x 1080. The MOD PREVIEW box
#        displays the image of the currently selected style and swaps
#        automatically whenever the style changes. Missing files fall
#        back to the bundled GLTPreview.png.
# 2) MOD PREVIEW (GLTPreview.png, bottom of the GLT page):
#      - 16:9 landscape (bundled file: 1344 x 768). All mod preview
#        boxes are displayed at a fixed 400 x 225 px slot.
# ------------------------------------------------------------------
def glt_style_preview_path(style_key):
    """Preview image file for a GLT style key (without fallback), or None."""
    path = GLT_PREVIEW_T5_FILE if str(style_key) == "T5" else GLT_PREVIEW_T6_FILE
    return path if os.path.exists(path) else None


# ------------------------------------------------------------------
# MATCH MOMENTUM — settings stored in ModsConfig.json under
# mods -> "Match Momentum" (mm_* keys). Defaults follow the momentum
# engine's own defaults, EXCEPT the on-screen display duration which is
# 10 seconds (user request). The backend (MomentumMatch/MomentumMod.py)
# reads this same block when ModBridge starts it.
# ------------------------------------------------------------------
MOMENTUM_MOD_NAME = "Match Momentum"
MOMENTUM_MOD_FOLDER = os.path.join(APP_DIR, "MomentumMatch")
MOMENTUM_PREVIEW_FILE = os.path.join(MOMENTUM_MOD_FOLDER, "MomentumPreview.png")

# YouTube tutorial link: intentionally NOT user-editable (v1.0.0: the
# link comes from the developer Gist at click time; this is only a fallback).
MOMENTUM_TUTORIAL_URL = ""     # local fallback for the Gist's "Momentum Tut"
HEATMAP_TUTORIAL_URL = ""      # local fallback for the Gist's "HeatMap Tut"

DEFAULT_MOMENTUM_SETTINGS = {
    "mm_h1_enabled": True,   "mm_h1_minute": 43,   # first half snapshot
    "mm_h2_enabled": True,   "mm_h2_minute": 85,   # second half snapshot
    "mm_et_enabled": True,   "mm_et_minute": 116,  # extra time snapshot
    "mm_show_seconds": 10,                          # on screen (REAL seconds)
    "mm_end_enabled": True,  "mm_end_seconds": 20,  # end-of-match display
    "mm_permanent_save": False,                     # keep last chart per match
    "mm_save_shown_charts": False,                  # keep EVERY shown chart (new)
    "mm_timestamp": False,                          # date/time stamp on chart
}
MOMENTUM_MINUTE_RANGES = {"h1": (38, 44), "h2": (80, 89), "et": (110, 119)}
MOMENTUM_SECONDS_RANGE = (5, 300)


def momentum_clamp_minutes(key, value):
    lo, hi = MOMENTUM_MINUTE_RANGES.get(key, (0, 130))
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = DEFAULT_MOMENTUM_SETTINGS["mm_%s_minute" % key]
    return max(lo, min(hi, v))


def momentum_clamp_seconds(value, default=10):
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = int(default)
    return max(MOMENTUM_SECONDS_RANGE[0], min(MOMENTUM_SECONDS_RANGE[1], v))


# =============================================================================
#
# =============================================================================
class BaseModalDialog(QWidget):
    RESULT_REJECTED = 0
    RESULT_ACCEPTED = 1

    def __init__(self, master_window, width, height, title, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(width, height)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        strong = Qt.FocusPolicy.StrongFocus if IS_PYQT6 else Qt.StrongFocus
        self.setFocusPolicy(strong)

        self._modal_result = BaseModalDialog.RESULT_REJECTED
        self._modal_loop = None

        theme = self.master_window.active_theme
        self.card = DiagnosticCyberCard(self.master_window, self)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.addWidget(self.card)
        inner = QVBoxLayout(self.card)
        inner.setContentsMargins(28, 24, 28, 24)
        inner.setSpacing(14)
        self.v = inner

        head = QHBoxLayout()
        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 15.5px; font-weight: 900; color: {theme.primary.name()}; letter-spacing: 1.2px; background: transparent; border: none;")
        btn_close = QPushButton("✕")
        btn_close.setObjectName("ModalCloseBtn")
        btn_close.clicked.connect(self.reject)
        head.addWidget(lbl_title)
        head.addStretch()
        head.addWidget(btn_close)
        self.v.addLayout(head)

        div = QFrame()
        div.setFixedHeight(1)
        div.setStyleSheet(f"background: rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.3); border: none;")
        self.v.addWidget(div)

    def make_text(self, html, color="#e0f2fe", size="13px"):
        lbl = QLabel(html)
        lbl.setWordWrap(True)
        lbl.setTextFormat(Qt.TextFormat.RichText if IS_PYQT6 else Qt.RichText)
        lbl.setAlignment(Qt.AlignmentFlag.AlignLeft if IS_PYQT6 else Qt.AlignLeft)
        lbl.setStyleSheet(f"color: {color}; font-size: {size}; line-height: 1.55; background: transparent; border: none;")
        return lbl

    def add_ok(self, text="OK", on_ok=None):
        btn = QPushButton(text)
        btn.setObjectName("NeonActionBtn")
        btn.setFixedHeight(46)
        btn.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn.clicked.connect(self.accept if on_ok is None else on_ok)
        self.v.addWidget(btn)
        return btn

    def exec_local(self):
        if self._modal_loop is not None:
            return
        self._modal_result = BaseModalDialog.RESULT_REJECTED
        self._modal_loop = QEventLoop(self)
        self.show()
        self.raise_()
        self.setFocus()
        self._modal_loop.exec()
        self._modal_loop = None

    def done(self, code):
        self._modal_result = code
        if self._modal_loop is not None and self._modal_loop.isRunning():
            self._modal_loop.quit()
        self.hide()

    def accept(self):
        self.done(BaseModalDialog.RESULT_ACCEPTED)

    def reject(self):
        self.done(BaseModalDialog.RESULT_REJECTED)

    def result(self):
        return self._modal_result

    def keyPressEvent(self, event):
        esc_key = Qt.Key.Key_Escape if IS_PYQT6 else Qt.Key_Escape
        if event.key() == esc_key:
            self.reject()
        else:
            super().keyPressEvent(event)

# -------------------------------------------------------------
# 11-b. Real Diagnostic Modal
# -------------------------------------------------------------
class RealDiagnosticModal(BaseModalDialog):
    def __init__(self, master_window, parent=None):
        super().__init__(master_window, 700, 520, "SYSTEM INTEGRITY & DIAGNOSTICS", parent)
        self.initUI()
        self.run_diagnostics()

    def _section_style(self):
        theme = self.master_window.active_theme
        bg = theme.bg_dark[2]
        return f"""
            QFrame {{
                background: rgba({bg.red()}, {bg.green()}, {bg.blue()}, 0.72);
                border: 1px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.3);
                border-radius: 12px;
            }}
        """

    @staticmethod
    def _rebind(btn, slot):
        try:
            btn.clicked.disconnect()
        except Exception:
            pass
        btn.clicked.connect(slot)

    def initUI(self):
        # Section 1
        sec1_container = QFrame()
        sec1_container.setMinimumHeight(84)
        sec1_container.setStyleSheet(self._section_style())
        sec1_layout = QVBoxLayout(sec1_container)
        sec1_layout.setContentsMargins(16, 12, 16, 12)
        sec1_layout.setSpacing(8)

        lbl_sec1 = QLabel("1. Display Mode Verification (settings.dat)")
        lbl_sec1.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; border: none; background: transparent;")
        sec1_layout.addWidget(lbl_sec1)

        self.sec1_box = QHBoxLayout()
        self.lbl_status1 = QLabel("Inspecting settings configuration...")
        self.lbl_status1.setWordWrap(True)
        self.lbl_status1.setMinimumHeight(34)
        self.lbl_status1.setStyleSheet("color: #93c5fd; font-size: 12.5px; border: none; background: transparent;")
        self.btn_fix1 = QPushButton("Fix Now")
        self.btn_fix1.setObjectName("DiagBtn")
        self.btn_fix1.setFixedSize(140, 36)
        self.btn_fix1.setVisible(False)
        self.sec1_box.addWidget(self.lbl_status1, 1)
        self.sec1_box.addStretch()
        self.sec1_box.addWidget(self.btn_fix1)
        sec1_layout.addLayout(self.sec1_box)
        self.v.addWidget(sec1_container)

        # Section 2
        sec2_container = QFrame()
        sec2_container.setMinimumHeight(84)
        sec2_container.setStyleSheet(self._section_style())
        sec2_layout = QVBoxLayout(sec2_container)
        sec2_layout.setContentsMargins(16, 12, 16, 12)
        sec2_layout.setSpacing(8)

        lbl_sec2 = QLabel("2. Game Executable Check")
        lbl_sec2.setStyleSheet("font-size: 13px; font-weight: 800; color: #ffffff; border: none; background: transparent;")
        sec2_layout.addWidget(lbl_sec2)

        self.sec2_box = QHBoxLayout()
        self.lbl_status2 = QLabel("Checking game binaries...")
        self.lbl_status2.setWordWrap(True)
        self.lbl_status2.setMinimumHeight(34)
        self.lbl_status2.setStyleSheet("color: #93c5fd; font-size: 12.5px; border: none; background: transparent;")
        self.btn_browse2 = QPushButton("Browse Folder")
        self.btn_browse2.setObjectName("DiagBtn")
        self.btn_browse2.setFixedSize(150, 36)
        self.btn_browse2.setVisible(False)
        self.btn_browse2.clicked.connect(self.browse_game_folder)
        self.sec2_box.addWidget(self.lbl_status2, 1)
        self.sec2_box.addStretch()
        self.sec2_box.addWidget(self.btn_browse2)
        sec2_layout.addLayout(self.sec2_box)
        self.v.addWidget(sec2_container)

        self.v.addStretch()

        btn_recheck = QPushButton("RE-RUN DIAGNOSTICS")
        btn_recheck.setObjectName("DiagRecheckBtn")
        btn_recheck.setFixedHeight(46)
        btn_recheck.clicked.connect(self.run_diagnostics)
        self.v.addWidget(btn_recheck)

    def run_diagnostics(self):
        all_passed = True

        path = get_settings_dat_path()
        self.btn_fix1.setVisible(False)

        if not os.path.exists(path):
            all_passed = False
            self.lbl_status1.setText("<span style='color: #ff4770; font-weight: bold;'>✖ Error: Settings configuration file was not found.</span>")
            self.btn_fix1.setText("Run Settings")
            self.btn_fix1.setVisible(True)
            self._rebind(self.btn_fix1, self.run_settings_exe)
        else:
            try:
                with open(path, 'rb') as f:
                    data = bytearray(f.read())

                if len(data) < 9:
                    all_passed = False
                    self.lbl_status1.setText("<span style='color: #ff4770; font-weight: bold;'>✖ Error: Settings file is corrupt or unreadable.</span>")
                    self.btn_fix1.setText("Run Settings")
                    self.btn_fix1.setVisible(True)
                    self._rebind(self.btn_fix1, self.run_settings_exe)
                else:
                    byte9 = data[8]
                    if byte9 == 0x6E:
                        self.lbl_status1.setText("<span style='color: #00ff88; font-weight: bold;'>✔ Windowed display mode is active and verified.</span>")
                    elif byte9 == 0x6F:
                        all_passed = False
                        self.lbl_status1.setText("<span style='color: #ff9900; font-weight: bold;'>✖ Fullscreen mode active. Windowed mode is required.</span>")
                        self.btn_fix1.setText("Fix Now")
                        self.btn_fix1.setVisible(True)
                        self._rebind(self.btn_fix1, self.fix_settings_dat)
                    else:
                        all_passed = False
                        self.lbl_status1.setText("<span style='color: #ff4770; font-weight: bold;'>✖ Invalid display configuration detected.</span>")
                        self.btn_fix1.setText("Run Settings")
                        self.btn_fix1.setVisible(True)
                        self._rebind(self.btn_fix1, self.run_settings_exe)
            except Exception as e:
                all_passed = False
                self.lbl_status1.setText(f"<span style='color: #ff4770; font-weight: bold;'>✖ Read Error: {str(e)}</span>")

        game_dir = getattr(self.master_window, 'custom_game_dir', APP_DIR)
        exe1 = os.path.join(game_dir, "FL_2026.exe")

        if not os.path.exists(exe1):
            all_passed = False
            self.lbl_status2.setText("<span style='color: #ff4770; font-weight: bold;'>✖ Missing: FL_2026.exe</span>")
            self.btn_browse2.setVisible(True)
        else:
            self.lbl_status2.setText("<span style='color: #00ff88; font-weight: bold;'>✔ FL_2026.exe verified.</span>")
            self.btn_browse2.setVisible(False)

        self.master_window.btn_alert.setStatus(not all_passed)

    def fix_settings_dat(self):
        path = get_settings_dat_path()
        try:
            with open(path, 'rb') as f:
                data = bytearray(f.read())
            if len(data) >= 9:
                data[8] = 0x6E
                with open(path, 'wb') as f:
                    f.write(data)
                self.master_window.show_message(
                    "info", "Display Mode Configured",
                    "Windowed display mode was successfully applied and saved."
                )
                self.run_diagnostics()
        except Exception as e:
            self.master_window.show_message(
                "error", "Configuration Error",
                f"Could not update settings file:<br>{str(e)}"
            )

    def run_settings_exe(self):
        game_dir = getattr(self.master_window, 'custom_game_dir', APP_DIR)
        candidates = [
            os.path.join(APP_DIR, "Settings.exe"),
            os.path.join(game_dir, "Settings.exe")
        ]
        settings_exe = None
        for c in candidates:
            if os.path.exists(c):
                settings_exe = c
                break

        if not settings_exe:
            self.master_window.show_message(
                "error", "Missing Tool",
                "Settings.exe was not found in the app or game directory."
            )
            return

        self.master_window.show_message(
            "warn", "Windowed Mode Required",
            "Please configure the display to 'Windowed' mode inside the Settings tool and save before returning."
        )
        try:
            subprocess.Popen([settings_exe], cwd=os.path.dirname(settings_exe))
        except Exception as e:
            self.master_window.show_message(
                "error", "Error",
                f"Failed to run Settings.exe:<br>{str(e)}"
            )

    def browse_game_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Football Life 2026 Game Directory", APP_DIR)
        if folder:
            exe1 = os.path.join(folder, "FL_2026.exe")
            if os.path.exists(exe1):
                self.master_window.custom_game_dir = folder
                self.master_window.save_config()
                self.master_window.show_message(
                    "success", "Verified",
                    f"FL_2026.exe confirmed in:<br>{folder}"
                )
                self.run_diagnostics()
            else:
                self.master_window.show_message(
                    "warn", "Not Found",
                    "Selected directory does not contain FL_2026.exe!"
                )

# =============================================================================
# =============================================================================
class ThemedMessageModal(BaseModalDialog):
    def __init__(self, master_window, kind="info", title="INFO", message="", parent=None, height=300):
        super().__init__(master_window, 520, height, title, parent)
        theme = self.master_window.active_theme

        kind_colors = {
            "info": theme.primary.name(),
            "success": "#00ff88",
            "warn": "#ff9900",
            "error": "#ff4770",
        }
        kind_icons = {"info": "i", "success": "✔", "warn": "!", "error": "✖"}
        color = kind_colors.get(kind, theme.primary.name())

        icon_lbl = QLabel(kind_icons.get(kind, "i"))
        icon_lbl.setFixedSize(54, 54)
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        icon_lbl.setStyleSheet(f"""
            color: {color}; font-size: 26px; font-weight: 900;
            border: 1.6px solid {color}; border-radius: 27px; background: transparent;
        """)

        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon_lbl)
        icon_row.addStretch()
        self.v.addLayout(icon_row)

        self.v.addWidget(self.make_text(message, "#e0f2fe", "13px"))
        self.v.addStretch()
        self.add_ok("GOT IT")

# =============================================================================
#
# =============================================================================
class KeyCaptureButton(QPushButton):
    keyCaptured = pyqtSignal(int, str)      # (vk_code, english_name)
    captureStarted = pyqtSignal()
    captureFinished = pyqtSignal()
    captureMessage = pyqtSignal(str)

    def __init__(self, master_window, parent=None):
        super().__init__("NOT SET", parent)
        self.master_window = master_window
        self.capturing = False
        self._dots = 0
        strong = Qt.FocusPolicy.StrongFocus if IS_PYQT6 else Qt.StrongFocus
        self.setFocusPolicy(strong)
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        self.setCursor(hand)
        self.setMinimumHeight(44)
        self.setMinimumWidth(170)

        self._dots_timer = QTimer(self)
        self._dots_timer.setInterval(420)
        self._dots_timer.timeout.connect(self._animate_dots)

    def start_capture(self):
        if self.capturing:
            self.cancel_capture()
            return
        self.capturing = True
        self._dots = 0
        self.setStyleSheet("""
            QPushButton {
                background: rgba(255, 153, 0, 0.16);
                border: 2px solid #ff9900; border-radius: 10px;
                color: #ffd27a; font-size: 13px; font-weight: 900; letter-spacing: 1.5px;
            }
        """)
        self.captureStarted.emit()
        self.setFocus()
        self.grabKeyboard()
        self._animate_dots()
        self._dots_timer.start()

    def cancel_capture(self):
        if not self.capturing:
            return
        self.capturing = False
        self._dots_timer.stop()
        self.releaseKeyboard()
        self.setStyleSheet("")
        self.captureFinished.emit()

    def _finish_with_key(self, vk, name):
        self.capturing = False
        self._dots_timer.stop()
        self.releaseKeyboard()
        self.setStyleSheet("")
        self.captureFinished.emit()
        self.keyCaptured.emit(int(vk), str(name))

    def _animate_dots(self):
        self._dots = (self._dots + 1) % 4
        self.setText("PRESS ANY KEY" + "." * self._dots)

    def mousePressEvent(self, event):
        if self.capturing:
            self.cancel_capture()
            return
        self.start_capture()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if not self.capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        esc_key = Qt.Key.Key_Escape if IS_PYQT6 else Qt.Key_Escape
        if key == esc_key:
            self.cancel_capture()
            return

        if IS_PYQT6:
            modifier_keys = (Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt,
                             Qt.Key.Key_Meta, Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock,
                             Qt.Key.Key_NumLock, Qt.Key.Key_ScrollLock)
        else:
            modifier_keys = (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt,
                             Qt.Key_Meta, Qt.Key_AltGr, Qt.Key_CapsLock,
                             Qt.Key_NumLock, Qt.Key_ScrollLock)
        if key in modifier_keys:
            self.captureMessage.emit("Modifier keys (Shift / Ctrl / Alt / Caps...) are not allowed — press a normal key.")
            return

        vk = event.nativeVirtualKey()
        if not vk:
            vk = int(key) & 0xFF
        if not vk:
            self.captureMessage.emit("This key cannot be registered — try another one.")
            return

        name = get_key_display_name(int(vk))
        self._finish_with_key(int(vk), name)

# =============================================================================
# =============================================================================
class KeyConflictModal(BaseModalDialog):
    def __init__(self, master_window, key_name, self_mod_label, other_key_label, parent=None):
        super().__init__(master_window, 560, 330, "KEY ALREADY IN USE", parent)
        theme = self.master_window.active_theme
        self.v.addStretch()
        self.v.addWidget(self.make_text(
            f"The key <b style='color:#ff9900;'>\"{key_name}\"</b> is already assigned to "
            f"<b style='color:{theme.primary.name()};'>{other_key_label}</b> — and that mod is "
            f"currently <b style='color:#ff4770;'>ENABLED</b>.<br><br>",
            "#e0f2fe", "13px"))
        self.v.addWidget(self.make_text(
            "Two enabled mods cannot use the same key.<br>"
            "If you continue, this key will be registered for "
            f"<b style='color:{theme.primary.name()};'>{self_mod_label}</b> and the key box of "
            f"<b>{other_key_label}</b> will be cleared (<b>NOT SET</b>) until you "
            "choose a new key for it.",
            "#94a3b8", "12px"))
        self.v.addStretch()

        row = QHBoxLayout()
        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("DiagBtn")
        btn_cancel.setFixedHeight(46)
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        btn_cancel.setCursor(hand)
        btn_cancel.clicked.connect(self.reject)
        btn_anyway = QPushButton("USE ANYWAY")
        btn_anyway.setObjectName("DangerBtn")
        btn_anyway.setFixedHeight(46)
        btn_anyway.setCursor(hand)
        btn_anyway.clicked.connect(self.accept)
        row.addWidget(btn_cancel)
        row.addStretch()
        row.addWidget(btn_anyway)
        self.v.addLayout(row)

# =============================================================================
# 11-g-1. Referee Preview Box (fixed 16:9 MOD PREVIEW slot)
# =============================================================================
def draw_cover_pixmap(p, pixmap, w, h, radius=11.0, inset=1.0):
    """Draw `pixmap` filling a w x h rect cover-style (aspect kept, center
    crop) with rounded-corner clipping. Returns the visible image rect so
    callers can anchor overlay elements on it."""
    if pixmap is None or pixmap.isNull():
        return QRect(int(inset), int(inset), max(1, int(w - 2 * inset)),
                     max(1, int(h - 2 * inset)))
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(inset, inset, w - 2 * inset, h - 2 * inset), radius, radius)
    p.setClipPath(clip)
    expand = Qt.AspectRatioMode.KeepAspectRatioByExpanding if IS_PYQT6 else Qt.KeepAspectRatioByExpanding
    scaled = pixmap.scaled(max(2, int(w - 2 * inset)), max(2, int(h - 2 * inset)),
                           expand, SMOOTH_TRANSFORM)
    sx = inset + (w - 2 * inset - scaled.width()) / 2.0
    sy = inset + (h - 2 * inset - scaled.height()) / 2.0
    p.drawPixmap(QRectF(sx, sy, scaled.width(), scaled.height()), pixmap,
                 QRectF(0, 0, pixmap.width(), pixmap.height()))
    p.setClipping(False)
    vis_x = max(inset, sx)
    vis_y = max(inset, sy)
    vis_w = min(w - 2 * inset, scaled.width())
    vis_h = min(h - 2 * inset, scaled.height())
    return QRect(int(vis_x), int(vis_y), int(vis_w), int(vis_h))


class RefereePreviewBox(QWidget):
    """MOD PREVIEW slot for the Referee View page. Fixed 16:9 slot
    (PREVIEW_BOX_W x PREVIEW_BOX_H = 400 x 225) — user-provided preview
    images are 16:9 landscape and fill the box edge-to-edge with rounded
    corners. The small live-overlay demo (RefereeOverlay.png) is anchored
    on top of the image when 'SHOW VIDEO OVERLAY' is on."""

    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(PREVIEW_BOX_W, PREVIEW_BOX_H)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)

        self.preview_pixmap = QPixmap(REF_PREVIEW_FILE) if os.path.exists(REF_PREVIEW_FILE) else QPixmap()
        self.overlay_pixmap = QPixmap(REF_OVERLAY_FILE) if os.path.exists(REF_OVERLAY_FILE) else QPixmap()
        self.overlay_on = False
        self._overlay_opacity = 0.0

        self._fade = QVariantAnimation(self)
        self._fade.setDuration(260)
        start_v = 0.0
        end_v = 1.0
        self._fade.setStartValue(start_v)
        self._fade.setEndValue(end_v)
        ease = QEasingCurve.Type.OutCubic if IS_PYQT6 else QEasingCurve.OutCubic
        self._fade.setEasingCurve(ease)
        self._fade.valueChanged.connect(self._on_fade_step)

    def set_overlay_on(self, on, animate=True):
        on = bool(on)
        if on == self.overlay_on:
            return
        self.overlay_on = on
        if animate:
            self._fade.stop()
            self._fade.setStartValue(self._overlay_opacity)
            self._fade.setEndValue(1.0 if on else 0.0)
            self._fade.start()
        else:
            self._overlay_opacity = 1.0 if on else 0.0
            self.update()

    def _on_fade_step(self, value):
        self._overlay_opacity = float(value)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()

        # v2.3.5 — full-bleed card like every preview box: NO theme border
        # and NO inner rect over the image (the user found the same stray
        # line in ALL previews — the border showed through semi-transparent
        # texture pixels and the 9.5px inset rect sat on top of the image).
        # The frame is kept only for the missing-image placeholder.
        if self.preview_pixmap.isNull():
            p.setPen(QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 120), 1.2))
            p.setBrush(QColor(4, 8, 18, 160))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
            p.setPen(QColor("#94a3b8"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter,
                       "PREVIEW IMAGE NOT FOUND\n"
                       "Put  RefereePreview.png  (16:9 landscape)\n"
                       "inside the  RefereeView  folder")
            p.end()
            return

        img_rect = draw_cover_pixmap(p, self.preview_pixmap, w, h)

        if self.overlay_on and (not self.overlay_pixmap.isNull()) and self._overlay_opacity > 0.001:
            fx, fy, fw, fh = REF_OVERLAY_RECT
            ox = img_rect.x() + int(fx * img_rect.width())
            oy = img_rect.y() + int(fy * img_rect.height())
            ow = max(1, int(fw * img_rect.width()))
            oh = max(1, int(fh * img_rect.height()))
            p.setOpacity(self._overlay_opacity)
            p.drawPixmap(QRect(ox, oy, ow, oh), self.overlay_pixmap)
            p.setOpacity(1.0)

        p.end()

# =============================================================================
# =============================================================================
class RefereeUsageModal(BaseModalDialog):
    def __init__(self, master_window, key_name="T", parent=None):
        super().__init__(master_window, 620, 360, "HOW TO USE — REFEREE VIEW", parent)
        theme = self.master_window.active_theme
        k = key_name or "T"
        html = (
            "To access this mod, enter <b style='color:" + theme.primary.name() + ";'>\"Replay\"</b> mode "
            "and press <b style='color:" + theme.primary.name() + ";'>\"" + k + "\"</b>.<br><br>"
            "You now have access to the referee's view.<br><br>"
            "To exit the referee view, press the same key again."
        )
        self.v.addStretch()
        self.v.addWidget(self.make_text(html, "#e0f2fe", "14px"))
        self.v.addStretch()
        self.add_ok("UNDERSTOOD")

# =============================================================================
# 11-g-2. GLT Usage Modal — Goal Line Technology instructions
#   The manual-record key name is injected automatically where the user's
#   configured key must appear.
# =============================================================================
class GLTUsageModal(BaseModalDialog):
    def __init__(self, master_window, rec_key_name="F7", parent=None):
        super().__init__(master_window, 680, 420, "HOW TO USE — GOAL LINE TECHNOLOGY", parent)
        theme = self.master_window.active_theme
        k = rec_key_name or "F7"
        en_html = (
            "To review the goal scene, enter <b style='color:" + theme.primary.name() + ";'>Replay Mode</b>. "
            "Then press <b style='color:" + theme.primary.name() + ";'>\"" + k + "\"</b> to start recording "
            "the animation <b>manually</b>.<br><br>"
            "From this moment on, you don't need to do anything — just wait until the recording finishes "
            "and the goal scene is shown to you.<br><br>"
            "After the animation ends, wait until the camera is reset and the animation fully completes."
        )
        self.v.addStretch()
        self.v.addWidget(self.make_text(en_html, "#e0f2fe", "13.5px"))
        self.v.addStretch()
        self.add_ok("UNDERSTOOD")

# =============================================================================
# =============================================================================
class GLTPreviewBox(QWidget):
    """MOD PREVIEW slot for the Goal Line Technology page. Fixed 16:9 slot
    (400 x 225). It shows the preview of the CURRENTLY selected animation
    style and swaps the image automatically whenever the style changes:
      Style 1 (T5) -> GLT/GLTPreview_T5.png
      Style 2 (T6) -> GLT/GLTPreview_T6.png
    A missing per-style file falls back to the bundled GLTPreview.png,
    then to a placeholder text."""

    def __init__(self, master_window, style_key="T6", parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(PREVIEW_BOX_W, PREVIEW_BOX_H)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self.style_key = str(style_key)
        self.preview_pixmap = QPixmap()
        self.preview_source = ""
        self.set_style(self.style_key)

    def set_style(self, style_key):
        """Swap the preview image for the given style (dynamic update).
        Priority: per-style 16:9 preview -> bundled GLTPreview.png."""
        self.style_key = str(style_key)
        path = glt_style_preview_path(self.style_key)
        if path is None and os.path.exists(GLT_PREVIEW_FILE):
            path = GLT_PREVIEW_FILE          # bundled fallback
        if path:
            pm = QPixmap(path)
            self.preview_pixmap = pm if not pm.isNull() else QPixmap()
            self.preview_source = path if not self.preview_pixmap.isNull() else ""
        else:
            self.preview_pixmap = QPixmap()
            self.preview_source = ""
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()

        # v2.3.5 — full-bleed card: NO theme border / inner rect over the
        # image (same stray line removed from every preview). The frame is
        # kept only for the missing-image placeholder.
        if self.preview_pixmap.isNull():
            p.setPen(QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 120), 1.2))
            p.setBrush(QColor(3, 10, 6, 160))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
            p.setPen(QColor("#94a3b8"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter,
                       "PREVIEW IMAGE NOT FOUND\n"
                       "Put  GLTPreview_T5.png / GLTPreview_T6.png  (16:9)\n"
                       "inside the  GLT  folder — falls back to GLTPreview.png")
            p.end()
            return

        draw_cover_pixmap(p, self.preview_pixmap, w, h)
        p.end()


# =============================================================================
# GLTStyleButton — ANIMATION STYLE selector (Style 1 = T5, Style 2 = T6).
# The old 178 x 104 image-thumbnail buttons were removed; this is now a
# compact text chip (178 x 44) — the per-style preview images live in the
# MOD PREVIEW box (GLTPreviewBox.set_style), which swaps automatically
# whenever the user picks a different style.
# =============================================================================
class GLTStyleButton(QPushButton):
    def __init__(self, master_window, style_key, caption, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.style_key = style_key
        self.caption = caption
        self.setCheckable(True)
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        self.setCursor(hand)
        self.setFixedSize(166, 42)      # v2.1.9 — fits two chips per card

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        checked = self.isChecked()
        w, h = self.width(), self.height()
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()

        p.setPen(QPen(QColor(pr, pg, pb, 235 if checked else 90), 2.0 if checked else 1.2))
        p.setBrush(QColor(4, 12, 8, 200) if checked else QColor(6, 14, 10, 150))
        p.drawRoundedRect(QRectF(1, 1, w - 2, h - 2), 10, 10)

        fnt = QFont("Segoe UI", 9)
        fnt.setBold(True)
        p.setFont(fnt)
        p.setPen(QColor("#ffffff") if checked else QColor("#94a3b8"))
        cap = self.caption + ("  •  SELECTED ✓" if checked else "")
        p.drawText(QRectF(0, 0, w, h),
                   Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter, cap)
        p.end()


# =============================================================================
# AllControlsModal — the comprehensive controls overview, opened by clicking
# the small gamepad icon on the GLT page. It lists EVERY control this app
# manages — the mod keyboard keys plus all gamepad buttons read live from
# the game settings binary (settings.dat) — as simple  NAME -> KEY  rows.
# Names only: no addresses, no make codes, no file paths.
# =============================================================================
class AllControlsModal(BaseModalDialog):
    def __init__(self, master_window, parent=None):
        super().__init__(master_window, 560, 560, "ALL CONTROLS", parent)
        theme = self.master_window.active_theme

        def control_row(name, key_text, key_color="#ffffff"):
            row = QFrame()
            row.setStyleSheet(f"""
                QFrame {{
                    background: rgba({theme.bg_dark[2].red()}, {theme.bg_dark[2].green()}, {theme.bg_dark[2].blue()}, 0.65);
                    border: 1.2px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.35);
                    border-radius: 10px;
                }}
            """)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 8, 14, 8)
            lbl = QLabel(str(name))
            lbl.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 700; "
                              "background: transparent; border: none;")
            key = QLabel(str(key_text))
            key.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
            key.setMinimumWidth(110)
            key.setStyleSheet("color: %s; font-size: 12.5px; font-weight: 900; letter-spacing: 1px; "
                              "background: transparent; border: none;" % key_color)
            rl.addWidget(lbl)
            rl.addStretch()
            rl.addWidget(key)
            return row

        def section(label):
            box = QVBoxLayout()
            box.setSpacing(6)
            cap = QLabel(label)
            cap.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {theme.accent.name()}; "
                              "letter-spacing: 1.5px; background: transparent; border: none;")
            box.addWidget(cap)
            return box

        # --- Section 1: mod keyboard keys --------------------------------
        sec1 = section("MOD KEYS")
        mk = getattr(master_window, "mod_keys", {}).get("Referee View", {})
        gc = getattr(master_window, "glt_cfg", {})
        ref_name = str(mk.get("name", "") or "").strip()
        sec1.addWidget(control_row("Referee View — Apply Key",
                                   ref_name if ref_name else "NOT SET",
                                   "#ffffff" if ref_name else "#94a3b8"))
        play_name = str(gc.get("play_name", "") or "").strip()
        sec1.addWidget(control_row("Goal Line Technology — Play Animation",
                                   play_name if play_name else "NOT SET",
                                   "#ffffff" if play_name else "#94a3b8"))
        rec_name = str(gc.get("rec_name", "") or "").strip()
        sec1.addWidget(control_row("Goal Line Technology — Manual Record",
                                   rec_name if rec_name else "NOT SET",
                                   "#ffffff" if rec_name else "#94a3b8"))
        sk = getattr(master_window, "mod_keys", {}).get(SAOT_MOD_NAME, {})
        saot_name = str(sk.get("name", "") or "").strip()
        sec1.addWidget(control_row("S.A.O.T — Call Key",
                                   saot_name if saot_name else "NOT SET",
                                   "#ffffff" if saot_name else "#94a3b8"))
        self.v.addLayout(sec1)

        # --- Section 2: gamepad buttons (live from settings.dat) ---------
        sec2 = section("GAMEPAD BUTTONS")
        bindings = read_glt_gamepad_bindings()
        for pad_label, _pad_offset in GLT_GAMEPAD_BINDINGS:
            info = bindings.get(pad_label, {})
            ok = bool(info.get("ok", False))
            code = info.get("code")
            key = make_code_to_key_name(code) if (ok and code is not None) else None
            if ok and key:
                sec2.addWidget(control_row(pad_label, key, "#00ff88"))
            elif ok:
                sec2.addWidget(control_row(pad_label, "UNBOUND", "#94a3b8"))
            else:
                sec2.addWidget(control_row(pad_label, "N/A", "#ff9900"))
        self.v.addLayout(sec2)

        self.v.addStretch()
        self.add_ok("CLOSE")


# =============================================================================
# BindingsHoverPanel — floating panel (a child of the master window, ignored
# by the mouse) shown while the small gamepad icon is hovered. It lists every
# gamepad binding as one simple  BUTTON  ->  KEY  row, read live from
# settings.dat. Names only — nothing else.
# =============================================================================
class BindingsHoverPanel(QWidget):
    ROW_H = 24
    PAD = 12
    WIDTH = 252

    def __init__(self, master_window, parent=None):
        super().__init__(master_window)
        self.master_window = master_window
        self.bindings = {}
        transparent_for_mouse = Qt.WidgetAttribute.WA_TransparentForMouseEvents if IS_PYQT6 else Qt.WA_TransparentForMouseEvents
        self.setAttribute(transparent_for_mouse)
        show_without_activating = Qt.WidgetAttribute.WA_ShowWithoutActivating if IS_PYQT6 else Qt.WA_ShowWithoutActivating
        self.setAttribute(show_without_activating)
        self.setFixedHeight(2 * self.PAD + len(GLT_GAMEPAD_BINDINGS) * self.ROW_H)
        self.setFixedWidth(self.WIDTH)

    def refresh_bindings(self):
        self.bindings = read_glt_gamepad_bindings()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()

        p.setPen(QPen(QColor(pr, pg, pb, 220), 1.4))
        p.setBrush(QColor(8, 13, 24, 248))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)

        fnt = QFont("Segoe UI", 9)
        fnt.setBold(True)
        p.setFont(fnt)
        y = float(self.PAD)
        for pad_label, _pad_offset in GLT_GAMEPAD_BINDINGS:
            info = self.bindings.get(pad_label, {})
            ok = bool(info.get("ok", False))
            code = info.get("code")
            key = make_code_to_key_name(code) if (ok and code is not None) else None

            p.setPen(QColor("#cbd5e1"))
            p.drawText(QRectF(self.PAD, y, 108, self.ROW_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft if IS_PYQT6 else Qt.AlignVCenter | Qt.AlignLeft,
                       str(pad_label))

            p.setPen(QColor(pr, pg, pb, 200))
            p.drawText(QRectF(self.PAD + 108, y, 24, self.ROW_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignVCenter | Qt.AlignHCenter,
                       "→")

            if ok and key:
                key_text, key_color = key, QColor("#ffffff")
            elif ok:
                key_text, key_color = "UNBOUND", QColor("#94a3b8")
            else:
                key_text, key_color = "N/A", QColor("#ff9900")
            p.setPen(key_color)
            p.drawText(QRectF(w - self.PAD - 100, y, 100, self.ROW_H),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight if IS_PYQT6 else Qt.AlignVCenter | Qt.AlignRight,
                       key_text)
            y += self.ROW_H
        p.end()


# =============================================================================
# GamepadBindingsIcon — the small icon that replaces the old gamepad chips
# row on the GLT page. Hovering it shows a floating panel with every assigned
# button -> key mapping (names only); clicking it opens the comprehensive
# AllControlsModal. Nothing else is displayed.
# =============================================================================
class GamepadBindingsIcon(QWidget):
    clicked = pyqtSignal()

    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(40, 40)
        self.is_hovered = False
        self._hover_panel = None
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)

    # --- hover panel management ------------------------------------------
    def _ensure_panel(self):
        if self._hover_panel is None:
            self._hover_panel = BindingsHoverPanel(self.master_window)
        return self._hover_panel

    def _show_hover_panel(self):
        panel = self._ensure_panel()
        panel.refresh_bindings()
        mw = self.master_window
        origin = self.mapTo(mw, QPoint(0, 0))
        x = origin.x() + self.width() + 10
        y = origin.y() - 4
        if x + panel.width() > mw.width() - 14:
            x = origin.x() - panel.width() - 10
        y = max(12, min(y, mw.height() - panel.height() - 12))
        panel.move(x, y)
        panel.show()
        panel.raise_()

    def _hide_hover_panel(self):
        if self._hover_panel is not None:
            self._hover_panel.hide()

    # --- events ------------------------------------------------------------
    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        self._show_hover_panel()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        self._hide_hover_panel()
        super().leaveEvent(event)

    def hideEvent(self, event):
        self._hide_hover_panel()
        super().hideEvent(event)

    def mouseReleaseEvent(self, event):
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self._hide_hover_panel()
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    # --- painting ------------------------------------------------------------
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()
        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()

        # clickable plate
        p.setPen(QPen(QColor(pr, pg, pb, 200 if self.is_hovered else 90), 1.2))
        p.setBrush(QColor(10, 16, 28, 215 if self.is_hovered else 140))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)

        # gamepad body
        p.setPen(QPen(QColor(pr, pg, pb, 240 if self.is_hovered else 150), 1.3))
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.drawRoundedRect(QRectF(6, 13, w - 12, 15), 7.5, 7.5)

        # d-pad (plus) on the left
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.setBrush(QColor(pr, pg, pb, 240 if self.is_hovered else 170))
        cx, cy = 13.0, 20.5
        p.drawRoundedRect(QRectF(cx - 1.4, cy - 4.6, 2.8, 9.2), 1.2, 1.2)
        p.drawRoundedRect(QRectF(cx - 4.6, cy - 1.4, 9.2, 2.8), 1.2, 1.2)

        # two round action buttons on the right
        p.drawEllipse(QPointF(26.5, 18.0), 2.1, 2.1)
        p.drawEllipse(QPointF(31.0, 22.0), 2.1, 2.1)
        p.end()


# =============================================================================
# Match Momentum widgets
# =============================================================================
class MomentumMinuteSelector(QWidget):
    """Compact cyber stepper ( - value + ) for minute/second values.
    Matches the app aesthetic; clamps to [lo, hi]."""

    valueChanged = pyqtSignal(int)

    def __init__(self, master_window, value, lo, hi, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.lo = int(lo)
        self.hi = int(hi)
        self._value = int(value)
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self.btn_dec = QPushButton("−")
        self.btn_inc = QPushButton("+")
        for b in (self.btn_dec, self.btn_inc):
            b.setFixedSize(30, 30)
            b.setCursor(hand)
            b.setObjectName("MomStepBtn")
        self.lbl_val = QLabel(str(self._value))
        self.lbl_val.setFixedSize(46, 30)
        self.lbl_val.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        self.lbl_val.setObjectName("MomStepVal")
        row.addWidget(self.btn_dec)
        row.addWidget(self.lbl_val)
        row.addWidget(self.btn_inc)
        self.btn_dec.clicked.connect(lambda: self.step(-1))
        self.btn_inc.clicked.connect(lambda: self.step(+1))
        self._apply_theme()

    def _apply_theme(self):
        t = self.master_window.active_theme
        pr, pg, pb = t.primary.red(), t.primary.green(), t.primary.blue()
        self.btn_dec.setStyleSheet(f"""
            QPushButton#MomStepBtn {{
                background: rgba({t.bg_dark[2].red()}, {t.bg_dark[2].green()}, {t.bg_dark[2].blue()}, 0.85);
                color: {t.primary.name()}; font-size: 16px; font-weight: 900;
                border: 1.2px solid rgba({pr}, {pg}, {pb}, 0.55); border-radius: 8px;
            }}
            QPushButton#MomStepBtn:hover {{ background: rgba({pr}, {pg}, {pb}, 0.25); }}
        """)
        self.btn_inc.setStyleSheet(self.btn_dec.styleSheet())
        self.lbl_val.setStyleSheet(f"""
            QLabel#MomStepVal {{
                background: rgba({t.bg_dark[1].red()}, {t.bg_dark[1].green()}, {t.bg_dark[1].blue()}, 0.9);
                color: #ffffff; font-size: 13px; font-weight: 900; letter-spacing: 0.5px;
                border: 1.2px solid rgba({pr}, {pg}, {pb}, 0.75); border-radius: 8px;
            }}
        """)

    def refresh_theme(self):
        self._apply_theme()

    def step(self, delta):
        self.setValue(self._value + delta)

    def value(self):
        return self._value

    def setValue(self, v):
        v = max(self.lo, min(self.hi, int(v)))
        if v == self._value:
            return
        self._value = v
        self.lbl_val.setText(str(v))
        self.valueChanged.emit(v)



class HeatMapPreviewBox(QWidget):
    """LIVE example image for the Heat Map settings page (fixed 16:9 slot,
    same size as the other mod previews). It renders a sample density grid
    through the SAME colour pipeline as the mod itself — blur, sensitivity
    (gain), heat ceiling, gamma, minimum filter (cutoff), edge feather and
    the broadcast green->yellow->orange->red palette — so every slider
    change is immediately visible. Pure-python render (no numpy needed),
    drawn as a QImage and scaled by Qt."""

    GRID_W = 110
    GRID_H = 71

    # broadcast palette stops (alpha interpolated), ported from the mod's
    # build_broadcast_lut(): green -> yellow -> orange -> bright red
    _STOPS = (
        (0.00, (60, 190, 30, 0)),
        (0.06, (80, 208, 18, 80)),
        (0.30, (148, 226, 0, 170)),
        (0.50, (238, 232, 0, 210)),
        (0.72, (252, 142, 0, 238)),
        (0.88, (248, 58, 0, 248)),
        (1.00, (247, 25, 0, 252)),
    )

    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self.setFixedSize(PREVIEW_BOX_W, PREVIEW_BOX_H)
        self._lut = self._build_lut()
        self._density = self._build_density()
        self._img = None
        self._params = None

    # --- pipeline pieces (mirrors the mod 1:1, pure python) -------------
    @classmethod
    def _build_lut(cls):
        lut = []
        for i in range(256):
            t = i / 255.0
            out = cls._STOPS[-1][1]
            for s in range(len(cls._STOPS) - 1):
                t0, c0 = cls._STOPS[s]
                t1, c1 = cls._STOPS[s + 1]
                if t0 <= t <= t1:
                    f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                    out = tuple(int(c0[k] * (1 - f) + c1[k] * f)
                                for k in range(4))
                    break
            lut.append(out)
        return lut

    @classmethod
    def _build_density(cls):
        """Sample 'seconds spent' field: a few Gaussian blobs like a real
        half of play (amplitudes in calibrated seconds)."""
        W, H = cls.GRID_W, cls.GRID_H
        g = [[0.0] * W for _ in range(H)]
        blobs = (
            (0.50, 0.52, 3.6, 0.055),   # x, y, amplitude (s), sigma (norm)
            (0.62, 0.44, 2.6, 0.050),
            (0.40, 0.60, 2.2, 0.060),
            (0.72, 0.58, 1.7, 0.045),
            (0.30, 0.40, 1.2, 0.050),
            (0.55, 0.30, 0.9, 0.040),
        )
        for cx, cy, amp, sig in blobs:
            s2 = 2.0 * sig * sig
            x0, x1 = max(0, int((cx - 3.2 * sig) * W)), min(W, int((cx + 3.2 * sig) * W) + 1)
            y0, y1 = max(0, int((cy - 3.2 * sig) * H)), min(H, int((cy + 3.2 * sig) * H) + 1)
            for y in range(y0, y1):
                dy2 = ((y + 0.5) / H - cy) ** 2
                row = g[y]
                for x in range(x0, x1):
                    d2 = ((x + 0.5) / W - cx) ** 2 + dy2
                    row[x] += amp * math.exp(-d2 / s2)
        return g

    @staticmethod
    def _box_blur(g, radius):
        if radius <= 0:
            return g
        H, W = len(g), len(g[0])
        # horizontal
        out = []
        for y in range(H):
            row = g[y]
            orow = [0.0] * W
            acc = 0.0
            for x in range(W):
                acc += row[x]
                if x >= 2 * radius + 1:
                    acc -= row[x - 2 * radius - 1]
                orow[x] = acc
            div = min(W, 2 * radius + 1)
            out.append([v / div for v in orow])
        # vertical
        out2 = [[0.0] * W for _ in range(H)]
        for x in range(W):
            acc = 0.0
            for y in range(H):
                acc += out[y][x]
                if y >= 2 * radius + 1:
                    acc -= out[y - 2 * radius - 1][x]
                out2[y][x] = acc / min(H, 2 * radius + 1)
        return out2

    def render(self, params):
        """params: dict with hm_gain/hm_ceiling/hm_gamma/hm_blur_m/
        hm_feather/hm_cutoff — rebuild the RGBA QImage."""
        if self._params == params and self._img is not None:
            return
        self._params = dict(params)
        W, H = self.GRID_W, self.GRID_H
        gain = float(params.get("hm_gain", 3.3))
        ceiling = max(0.1, float(params.get("hm_ceiling", 0.4))) * 2.8  # TEAM mode
        gamma = float(params.get("hm_gamma", 0.85))
        blur = float(params.get("hm_blur_m", 1.4))
        feather = float(params.get("hm_feather", 9.0))
        cutoff = float(params.get("hm_cutoff", 0.2))

        sigma = max(blur / 0.5 * 0.7, 0.8)
        r = max(1, int(round(sigma * 2)))
        g = self._box_blur(self._density, r)
        fr = int(round(feather / 4.0))
        if fr > 0:
            # edge feather == an extra soft pass on the field (the mod
            # blurs the finished heat layer; visually the same softening)
            g = self._box_blur(g, max(1, fr // 2))

        lut = self._lut
        img = QImage(W, H, QImage.Format.Format_RGBA8888 if IS_PYQT6 else QImage.Format_RGBA8888)
        img.fill(QColor(0, 0, 0, 0))
        buf = bytearray(W * H * 4)
        for y in range(H):
            row = g[y]
            for x in range(W):
                v = row[x] * gain / ceiling
                v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)
                v = v ** gamma
                if cutoff > 0.001:
                    if v >= cutoff:
                        v = (v - cutoff) / (1.0 - cutoff + 1e-6)
                    else:
                        v = 0.0
                cr, cg, cb, ca = lut[min(255, int(v * 255 + 0.5))]
                o = (y * W + x) * 4
                buf[o] = cr
                buf[o + 1] = cg
                buf[o + 2] = cb
                buf[o + 3] = ca
        img = QImage(bytes(buf), W, H,
                     QImage.Format.Format_RGBA8888 if IS_PYQT6 else QImage.Format_RGBA8888)
        self._img = img
        self.update()

    # ------------------------------------------------------------------
    # v2.2.0 (user request #3) — PRECISE FIFA-STANDARD PITCH MARKINGS.
    # The example pitch is drawn with the exact IFAB Laws of the Game
    # geometry (105 m x 68 m), proportion-correct and height-fitted:
    # touch/goal lines, halfway line, centre circle + centre spot,
    # penalty areas (16.5 m), goal areas (5.5 m), penalty spots (11 m),
    # penalty arcs (9.15 m, only outside the penalty area), corner arcs
    # (1 m) and the 7.32 m goals behind each goal line.
    # ------------------------------------------------------------------
    PITCH_L = 105.0            # touchline length (m)
    PITCH_W = 68.0             # goal-line width (m)
    CENTRE_R = 9.15            # centre circle radius (m)
    PENALTY_DEPTH = 16.5       # penalty area depth (m)
    PENALTY_WIDTH = 40.32      # 7.32 + 2 x 16.5 (m)
    GOAL_AREA_DEPTH = 5.5      # goal area depth (m)
    GOAL_AREA_WIDTH = 18.32    # 7.32 + 2 x 5.5 (m)
    PENALTY_DIST = 11.0        # penalty spot distance from goal line (m)
    CORNER_R = 1.0             # corner arc radius (m)
    GOAL_WIDTH = 7.32          # goal mouth width (m)
    GOAL_DEPTH = 2.44          # goal depth behind the goal line (m)

    @classmethod
    def _pitch_geometry(cls, w, h):
        """Map every FIFA marking from metres into widget coordinates.
        The pitch keeps its true 105:68 proportion (fitted by height,
        centred horizontally) so circles stay true circles. Returned as
        a dict of paint-ready QRectF / QPointF / arc tuples."""
        m = 14.0                                   # outer margin
        avail_w, avail_h = w - 2 * m, h - 2 * m
        scale = avail_h / cls.PITCH_W
        fw = cls.PITCH_L * scale
        if fw > avail_w:                           # very wide box safety
            scale = avail_w / cls.PITCH_L
            fw = cls.PITCH_L * scale
        fh = cls.PITCH_W * scale
        x0 = (w - fw) / 2.0
        y0 = m + (avail_h - fh) / 2.0

        def X(metres):
            return x0 + metres * scale

        def Y(metres):
            return y0 + metres * scale

        def R(metres):
            return metres * scale

        L, Wp = cls.PITCH_L, cls.PITCH_W
        cy = Wp / 2.0
        # penalty-arc opening angle: acos((16.5 - 11) / 9.15) ~= 53.06 deg
        arc_deg = math.degrees(math.acos(
            (cls.PENALTY_DEPTH - cls.PENALTY_DIST) / cls.CENTRE_R))
        arc_span = int(round(2 * arc_deg * 16))

        geo = {
            "scale": scale,
            "field": QRectF(x0, y0, fw, fh),
            "halfway": QLineF(QPointF(X(L / 2), Y(0)), QPointF(X(L / 2), Y(Wp))),
            "centre_circle": QRectF(X(L / 2) - R(cls.CENTRE_R),
                                    Y(cy) - R(cls.CENTRE_R),
                                    2 * R(cls.CENTRE_R), 2 * R(cls.CENTRE_R)),
            "centre_spot": QPointF(X(L / 2), Y(cy)),
            "penalty_l": QRectF(X(0), Y(cy - cls.PENALTY_WIDTH / 2),
                                R(cls.PENALTY_DEPTH), R(cls.PENALTY_WIDTH)),
            "penalty_r": QRectF(X(L - cls.PENALTY_DEPTH),
                                Y(cy - cls.PENALTY_WIDTH / 2),
                                R(cls.PENALTY_DEPTH), R(cls.PENALTY_WIDTH)),
            "goal_area_l": QRectF(X(0), Y(cy - cls.GOAL_AREA_WIDTH / 2),
                                  R(cls.GOAL_AREA_DEPTH), R(cls.GOAL_AREA_WIDTH)),
            "goal_area_r": QRectF(X(L - cls.GOAL_AREA_DEPTH),
                                  Y(cy - cls.GOAL_AREA_WIDTH / 2),
                                  R(cls.GOAL_AREA_DEPTH), R(cls.GOAL_AREA_WIDTH)),
            "pen_spot_l": QPointF(X(cls.PENALTY_DIST), Y(cy)),
            "pen_spot_r": QPointF(X(L - cls.PENALTY_DIST), Y(cy)),
            # left arc bulges toward the centre (screen angles: -53..+53)
            "pen_arc_l": (QRectF(X(cls.PENALTY_DIST) - R(cls.CENTRE_R),
                                 Y(cy) - R(cls.CENTRE_R),
                                 2 * R(cls.CENTRE_R), 2 * R(cls.CENTRE_R)),
                          int(round(-arc_deg * 16)), arc_span),
            # right arc mirrored (bulges left)
            "pen_arc_r": (QRectF(X(L - cls.PENALTY_DIST) - R(cls.CENTRE_R),
                                 Y(cy) - R(cls.CENTRE_R),
                                 2 * R(cls.CENTRE_R), 2 * R(cls.CENTRE_R)),
                          int(round((180 - arc_deg) * 16)), arc_span),
            # corner arcs: quarter circles curving INTO the field
            # v2.3.4 — Qt arcs: 0°=3 o'clock, positive counter-clockwise on
            # screen. The old starts (0,90,180,270) drew every arc in the
            # MIRRORED quadrant OUTSIDE the pitch (the stray hooks the user
            # saw at each corner). Correct inside quadrants: TL 270→360,
            # TR 180→270, BR 90→180, BL 0→90.
            "corners": (
                (QRectF(X(0) - R(cls.CORNER_R), Y(0) - R(cls.CORNER_R),
                        2 * R(cls.CORNER_R), 2 * R(cls.CORNER_R)), 270),
                (QRectF(X(L) - R(cls.CORNER_R), Y(0) - R(cls.CORNER_R),
                        2 * R(cls.CORNER_R), 2 * R(cls.CORNER_R)), 180),
                (QRectF(X(L) - R(cls.CORNER_R), Y(Wp) - R(cls.CORNER_R),
                        2 * R(cls.CORNER_R), 2 * R(cls.CORNER_R)), 90),
                (QRectF(X(0) - R(cls.CORNER_R), Y(Wp) - R(cls.CORNER_R),
                        2 * R(cls.CORNER_R), 2 * R(cls.CORNER_R)), 0),
            ),
            # the goals sit BEHIND the goal lines
            "goal_l": QRectF(X(0) - R(cls.GOAL_DEPTH),
                             Y(cy - cls.GOAL_WIDTH / 2),
                             R(cls.GOAL_DEPTH), R(cls.GOAL_WIDTH)),
            "goal_r": QRectF(X(L), Y(cy - cls.GOAL_WIDTH / 2),
                             R(cls.GOAL_DEPTH), R(cls.GOAL_WIDTH)),
        }
        return geo

    def _draw_pitch_lines(self, p, w, h):
        """Paint the precise FIFA pitch markings over the heat layer."""
        geo = self._pitch_geometry(w, h)
        pen = QPen(QColor(236, 250, 244, 138), 1.3)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)

        p.drawRect(geo["field"])
        p.drawLine(geo["halfway"])
        p.drawEllipse(geo["centre_circle"])
        p.drawRect(geo["penalty_l"])
        p.drawRect(geo["penalty_r"])
        p.drawRect(geo["goal_area_l"])
        p.drawRect(geo["goal_area_r"])
        arc_l = geo["pen_arc_l"]
        p.drawArc(arc_l[0], arc_l[1], arc_l[2])
        arc_r = geo["pen_arc_r"]
        p.drawArc(arc_r[0], arc_r[1], arc_r[2])
        for rect, start_deg in geo["corners"]:
            p.drawArc(rect, int(start_deg * 16), 90 * 16)
        p.drawRect(geo["goal_l"])
        p.drawRect(geo["goal_r"])

        # solid spots: centre + both penalty spots
        p.setBrush(QBrush(QColor(236, 250, 244, 190)))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        r_spot = 1.7
        for pt in (geo["centre_spot"], geo["pen_spot_l"], geo["pen_spot_r"]):
            p.drawEllipse(pt, r_spot, r_spot)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        # v2.3.5 — no theme border around the live heat map (the same stray
        # line the user asked to remove from every preview). The dark base
        # stays so the semi-transparent heat layer keeps its backdrop.
        w, h = self.width(), self.height()
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.setBrush(QColor(8, 14, 10, 200))
        p.drawRoundedRect(QRectF(0, 0, w, h), 12, 12)
        p.setClipRect(QRectF(1, 1, w - 2, h - 2))
        if self._img is not None:
            p.drawImage(self.rect(), self._img)
        # v2.2.0 — precise FIFA-standard pitch lines (user request #3),
        # replacing the old 5-line sketch
        self._draw_pitch_lines(p, w, h)
        p.end()


class MomentumNoticeBanner(QFrame):
    """Amber info banner: the mod must be active on the game's start screen."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 14, 6)
        lbl = QLabel("⚠   " + text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("""
            color: #ffd27a; font-size: 11.5px; font-weight: 800;
            background: transparent; border: none;
        """)
        lay.addWidget(lbl)
        self.setStyleSheet("""
            MomentumNoticeBanner {
                background: rgba(255, 183, 0, 0.10);
                border: 1.2px solid #b37e00; border-radius: 10px;
            }
        """)


class MomentumPreviewBox(QWidget):
    """MOD PREVIEW slot for the Match Momentum page (fixed 16:9 slot,
    same compact size as the Referee View / GLT boxes; image:
    MomentumMatch/MomentumPreview.png, 16:9 landscape)."""

    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(PREVIEW_BOX_W, PREVIEW_BOX_H)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self.preview_pixmap = QPixmap(MOMENTUM_PREVIEW_FILE) if os.path.exists(MOMENTUM_PREVIEW_FILE) else QPixmap()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()

        # v2.3.4 — full-bleed card: the MomentumPreview texture carries its
        # own frame, so the code no longer paints the theme border / inner
        # rect on top of it (the border's bottom edge used to show as a
        # stray crimson line under the "PES MODS BY MILAD" band — removed
        # per user report). The frame is kept only for the missing-image
        # placeholder.
        if self.preview_pixmap.isNull():
            p.setPen(QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 120), 1.2))
            p.setBrush(QColor(12, 2, 6, 160))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
            p.setPen(QColor("#94a3b8"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter,
                       "PREVIEW IMAGE NOT FOUND\n"
                       "Put  MomentumPreview.png  (16:9 landscape)\n"
                       "inside the  MomentumMatch  folder")
            p.end()
            return

        draw_cover_pixmap(p, self.preview_pixmap, w, h)
        p.end()


# =============================================================================
# MomentumSettingsModal — the "AUTO CHART DISPLAY" settings of the Match
# Momentum mod (options mirror the momentum engine's own Settings dialog):
#   * auto snapshot schedule (first half / second half / extra time),
#     each with an enable toggle and its target minute,
#   * on-screen display duration (default 10 s),
#   * end-of-match display (90+/120+) with its own duration,
#   * permanent chart saving (Momentum_Saves) and date/time stamping.
# Values persist into ModsConfig.json -> mods -> "Match Momentum".
# =============================================================================
# =============================================================================
# [suite v2.1.7] S.A.O.T preview slot — same 16:9 box as the other mods;
# image: SAOTMod/SAOTPreview.png (replay scene with the offside plane).
# =============================================================================
class SAOTPreviewBox(QWidget):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedSize(PREVIEW_BOX_W, PREVIEW_BOX_H)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self.preview_pixmap = QPixmap(SAOT_PREVIEW_FILE) if os.path.exists(SAOT_PREVIEW_FILE) else QPixmap()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()

        # v2.3.5 — full-bleed card: NO theme border / inner rect over the
        # image (same stray line removed from every preview). The frame is
        # kept only for the missing-image placeholder.
        if self.preview_pixmap.isNull():
            p.setPen(QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 120), 1.2))
            p.setBrush(QColor(10, 8, 20, 160))
            p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)
            p.setPen(QColor("#94a3b8"))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter,
                       "PREVIEW IMAGE NOT FOUND\n"
                       "Put  SAOTPreview.png  (16:9 landscape)\n"
                       "inside the  SAOTMod  folder")
            p.end()
            return

        draw_cover_pixmap(p, self.preview_pixmap, w, h)
        p.end()


# =============================================================================
# [suite v2.1.7 / v2.1.8] S.A.O.T instructions modal — contains ALL the
# teaching content of the original tool (8 installation steps + 10 usage
# steps, English) split into TWO TABS: INSTALLATION and USAGE.
# v2.1.8 improvements:
#   * the ReShade DOWNLOAD and the COPY 2026 FILES actions are real
#     liquid-glass buttons matching the main UI (inside the guide);
#   * clicking a tutorial image opens an IN-APP full-size viewer — the
#     old external-viewer handler had a broken signature (the mouse
#     event replaced the file path -> TypeError -> hard crash);
#   * tutorial images that are not shipped (e.g. tex13.jpg) are skipped
#     SILENTLY — no more "image not found" notices.
# =============================================================================
SAOT_INSTALL_STEPS = [
    ("1. Download ReShade inside your game folder from the button below:",
     "link", RESHADE_DOWNLOAD_URL, "DOWNLOAD RESHADE", None),
    ("2. Install it and make sure to check DirectX 11/12.",
     "text", None, None, "tex1.jpg"),
    ("3. Copy the required offside files straight from here — the button "
     "below copies OffsidePlane.fx + Offside_Tex.png from "
     "SAOTMod\\textut into the main game folder:",
     "note", None, None, None),
    ("4. Before starting, set your game to 'Windowed Mode' and set the "
     "resolution. The tool won't work in Fullscreen.",
     "text", None, None, "tex2.jpg"),
    ("5. If you want to hide the window borders, use Borderless Gaming:",
     "link", "https://borderlessgaming.net/", "DOWNLOAD BORDERLESS GAMING",
     None),
    ("6. Open the game and press the 'Home' key to open the ReShade menu.",
     "text", None, None, "tex3.jpg"),
    ("7. Ensure OffsidePlane is the FIRST effect loaded. If you have "
     "other effects, disable them, load OffsidePlane, then re-enable.",
     "text", None, None, "tex4.jpg"),
    ("8. Everything is ready! Play the game.",
     "text", None, None, None),
]

SAOT_USAGE_STEPS = [
    ("1. Ensure all prerequisites are installed (see the INSTALLATION "
     "tab and the RESHADE SETUP section of the S.A.O.T page).",
     "text", None, None, None),
    ("2. The Bridge activates the tool automatically 3 seconds after the "
     "game launches — press your CALL KEY to summon this window.",
     "text", None, None, "tex5.jpg"),
    ("3. Play the game. Go to 'Replay' when you see a suspicious offside.",
     "text", None, None, "tex6.jpg"),
    ("4. Do not change the camera! Pause exactly when the ball leaves "
     "the foot.", "text", None, None, "tex7.jpg"),
    ("5. Use the keys to center the camera on the suspicious player.",
     "text", None, None, "tex8.jpg"),
    ("6. Press your Call Key to bring up this tool (might need 2 presses).",
     "text", None, None, "tex9.jpg"),
    ("7. Select the best view using the first option.",
     "text", None, None, "tex10.jpg"),
    ("8. Turn the plane ON using the second option.",
     "text", None, None, "tex11.jpg"),
    ("9. Use the slider to move the plane into the correct position.",
     "text", None, None, "tex12.jpg"),
    ("10. Turn the plane OFF before exiting the replay mode.",
     "text", None, None, "tex13.jpg"),
]


class SAOTImageViewerModal(BaseModalDialog):
    """v2.1.8 — in-app FULL-SIZE tutorial image viewer. Replaces the old
    'open with the system viewer' handler whose broken signature crashed
    the whole program on every click. Click the picture or CLOSE to exit.
    v2.1.9 (user request #5) — the viewer is now NEAR-FULLSCREEN: it grows
    to ~94% of the available screen so guide pictures are finally big."""

    def __init__(self, master_window, image_path, parent=None):
        scr = QApplication.primaryScreen()
        ag = scr.availableGeometry() if scr is not None else QRect(0, 0, 1280, 800)
        vw = max(760, min(ag.width() - 30, 1560))
        vh = max(600, min(ag.height() - 30, 1040))
        super().__init__(master_window, vw, vh,
                         "TUTORIAL IMAGE — %s"
                         % os.path.basename(str(image_path or "")), parent)
        theme = self.master_window.active_theme
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 \
            else Qt.PointingHandCursor
        pm = QPixmap(str(image_path)) \
            if image_path and os.path.exists(str(image_path)) else QPixmap()

        holder = QLabel()
        holder.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6
                            else Qt.AlignCenter)
        if pm.isNull():
            holder.setText("This image could not be loaded.")
            holder.setStyleSheet("color: #94a3b8; font-size: 13px; "
                                 "background: transparent; border: none;")
        else:
            avail_w = vw - 2 * 12 - 2 * 28 - 8
            avail_h = vh - 2 * 12 - 2 * 24 - 30 - 1 - 46 - 3 * 14
            scaled = pm.scaled(
                max(50, avail_w), max(50, avail_h),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            holder.setPixmap(scaled)
            holder.setCursor(hand)
            holder.setToolTip("Click to close")

            def _close_on_click(_event):
                self.accept()
            holder.mousePressEvent = _close_on_click
        self.v.addWidget(holder, 1)
        self.add_ok("CLOSE")


class SAOTUsageModal(BaseModalDialog):
    def __init__(self, master_window, parent=None):
        # v2.1.9 — slightly larger guide window + larger thumbnails
        super().__init__(master_window, 800, 730,
                         "HOW TO USE — S.A.O.T (INSTALLATION & USAGE)", parent)
        theme = self.master_window.active_theme

        tabs = QTabWidget()
        tabs.setObjectName("SaotHelpTabs")
        tabs.setStyleSheet(_help_tabs_stylesheet(theme))
        tabs.addTab(self._build_step_page(SAOT_INSTALL_STEPS),
                    "INSTALLATION  (%d)" % len(SAOT_INSTALL_STEPS))
        tabs.addTab(self._build_step_page(SAOT_USAGE_STEPS),
                    "USAGE  (%d)" % len(SAOT_USAGE_STEPS))
        self.v.addWidget(tabs, 1)
        self.add_ok("UNDERSTOOD")

    # ------------------------------------------------------------------
    def _build_step_page(self, steps):
        """One tab page: a scroll area full of step cards."""
        page = QWidget()
        pv = QVBoxLayout(page)
        pv.setContentsMargins(2, 2, 2, 2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QWidget { background: transparent; }
        """)
        body = QWidget()
        bv = QVBoxLayout(body)
        bv.setContentsMargins(2, 2, 10, 2)
        bv.setSpacing(7)
        for step in steps:
            bv.addWidget(self._step_card(*step))
        bv.addStretch()
        scroll.setWidget(body)
        pv.addWidget(scroll)
        return page

    def _step_card(self, text, kind, url, btn_label, img_name):
        theme = self.master_window.active_theme
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: rgba({theme.bg_dark[2].red()},
                                 {theme.bg_dark[2].green()},
                                 {theme.bg_dark[2].blue()}, 0.65);
                border: 1px solid rgba({theme.primary.red()},
                                       {theme.primary.green()},
                                       {theme.primary.blue()}, 0.3);
                border-radius: 10px;
            }}
        """)
        cv = QVBoxLayout(card)
        cv.setContentsMargins(14, 10, 14, 12)
        cv.setSpacing(7)
        cv.addWidget(self.make_text(text, "#e0f2fe", "12.5px"))

        if kind == "link":
            # v2.1.8 — a real liquid-glass button (main-UI style) instead
            # of a bare text link. 400px keeps even the longest caption
            # ("DOWNLOAD BORDERLESS GAMING") fully readable.
            btn = GlassPillButton(self.master_window, str(btn_label),
                                  icon="download", height=44, font_px=11.5,
                                  min_width=400)
            btn.clicked.connect(
                lambda _=False, _u=str(url or ""):
                QDesktopServices.openUrl(QUrl(_u)))
            cv.addWidget(btn)

        if kind == "note":
            # v2.1.8 — the COPY 2026 FILES action lives right here in the
            # guide, as a glass button, with an inline result line.
            btn = GlassPillButton(self.master_window, "COPY 2026 FILES",
                                  icon="copy", height=44, font_px=11.5,
                                  min_width=250)
            status = self.make_text("", "#00ff88", "11.5px")
            status.hide()

            def _do_copy(_checked=False):
                ok, msg = saot_copy_reshade_files(
                    self.master_window.custom_game_dir)
                status.setText(("&#10004;  " if ok else "&#10008;  ") + msg)
                status.setStyleSheet(
                    "color: %s; font-size: 11.5px; font-weight: 700; "
                    "line-height: 1.5; background: transparent; border: none;"
                    % ("#00ff88" if ok else "#ff4770"))
                status.show()
                try:
                    self.master_window.refresh_saot_reshade()
                except Exception:
                    pass
            btn.clicked.connect(_do_copy)
            cv.addWidget(btn)
            cv.addWidget(status)

        if img_name:
            # v2.1.8 — missing pictures (tex13.jpg was never shipped) are
            # skipped SILENTLY: no "image not found" notice is shown.
            img_path = os.path.join(SAOT_TEXTUT_DIR, img_name)
            if os.path.exists(img_path):
                try:
                    pm = QPixmap(img_path)
                    if not pm.isNull():
                        tw = 400
                        th = max(24, int(pm.height() * (tw / pm.width())))
                        thumb = QLabel()
                        thumb.setPixmap(pm.scaled(
                            tw, th,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation))
                        hand_cur = Qt.CursorShape.PointingHandCursor \
                            if IS_PYQT6 else Qt.PointingHandCursor
                        thumb.setCursor(hand_cur)
                        thumb.setToolTip("Click to view full size")

                        def _open_full(event, _p=img_path):
                            # correct signature: the mouse event is the
                            # FIRST argument (this was the crash — the
                            # event used to replace the path default).
                            self.master_window.show_modal(
                                SAOTImageViewerModal, _p)
                        thumb.mousePressEvent = _open_full
                        cv.addWidget(thumb)
                except Exception:
                    pass
        return card


# =============================================================================
class MomentumSettingsModal(BaseModalDialog):
    ROW_LABELS = (
        ("h1", "FIRST HALF"),
        ("h2", "SECOND HALF"),
        ("et", "EXTRA TIME"),
    )

    def __init__(self, master_window, parent=None):
        # v2.3.5 — 820 high: the schedule rows no longer squeeze the
        # description lines against the SAVE button (content min 701 px).
        super().__init__(master_window, 640, 820, "MATCH MOMENTUM — AUTO CHART DISPLAY", parent)
        theme = self.master_window.active_theme
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        cfg = master_window.mom_cfg

        def section_label(text):
            cap = QLabel(text)
            cap.setStyleSheet(f"font-size: 11px; font-weight: 800; color: {theme.accent.name()}; "
                              "letter-spacing: 1.5px; background: transparent; border: none;")
            return cap

        def row_frame():
            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background: rgba({theme.bg_dark[2].red()}, {theme.bg_dark[2].green()}, {theme.bg_dark[2].blue()}, 0.65);
                    border: 1.2px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.35);
                    border-radius: 10px;
                }}
            """)
            return frame

        self._toggles = {}
        self._selectors = {}

        # --- Section 1: automatic display schedule --------------------------
        self.v.addWidget(section_label("AUTO SNAPSHOT SCHEDULE"))
        self.v.addWidget(self.make_text(
            "The chart is captured one minute before the target minute and shown "
            "automatically at that minute.", "#94a3b8", "11px"))
        for key, name in self.ROW_LABELS:
            lo, hi = MOMENTUM_MINUTE_RANGES[key]
            frame = row_frame()
            rl = QHBoxLayout(frame)
            rl.setContentsMargins(14, 8, 14, 8)
            rl.setSpacing(10)
            tg = NeonToggle(master_window=master_window,
                            checked=bool(cfg.get(f"mm_{key}_enabled")))
            tg.toggled.connect(lambda state, k=f"mm_{key}_enabled": self._on_toggle(k, state))
            self._toggles[key] = tg
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 700; "
                              "background: transparent; border: none;")
            hint = QLabel(f"minute ({lo}–{hi})")
            hint.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 700; "
                               "background: transparent; border: none;")
            sel = MomentumMinuteSelector(master_window, momentum_clamp_minutes(key, cfg.get(f"mm_{key}_minute")), lo, hi)
            sel.valueChanged.connect(lambda v, k=key: self._on_minute(k, v))
            self._selectors[key] = sel
            rl.addWidget(tg)
            rl.addWidget(lbl)
            rl.addStretch()
            rl.addWidget(hint)
            rl.addWidget(sel)
            self.v.addWidget(frame)

        # --- Section 2: display duration ------------------------------------
        self.v.addWidget(section_label("DISPLAY"))
        frame_secs = row_frame()
        rl = QHBoxLayout(frame_secs)
        rl.setContentsMargins(14, 8, 14, 8)
        lbl = QLabel("ON-SCREEN DURATION")
        lbl.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 700; "
                          "background: transparent; border: none;")
        hint = QLabel("real seconds (5–300)")
        hint.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 700; "
                           "background: transparent; border: none;")
        self.sel_show = MomentumMinuteSelector(
            master_window, momentum_clamp_seconds(cfg.get("mm_show_seconds")),
            MOMENTUM_SECONDS_RANGE[0], MOMENTUM_SECONDS_RANGE[1])
        self.sel_show.valueChanged.connect(
            lambda v: self._on_seconds("mm_show_seconds", v))
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(hint)
        rl.addWidget(self.sel_show)
        self.v.addWidget(frame_secs)

        # end-of-match row
        frame_end = row_frame()
        rl = QHBoxLayout(frame_end)
        rl.setContentsMargins(14, 8, 14, 8)
        tg_end = NeonToggle(master_window=master_window,
                            checked=bool(cfg.get("mm_end_enabled")))
        tg_end.toggled.connect(lambda state: self._on_toggle("mm_end_enabled", state))
        self._toggles["mm_end_enabled"] = tg_end
        lbl = QLabel("END-OF-MATCH DISPLAY (90+ / 120+)")
        lbl.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 700; "
                          "background: transparent; border: none;")
        hint = QLabel("seconds")
        hint.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 700; "
                           "background: transparent; border: none;")
        self.sel_end = MomentumMinuteSelector(
            master_window, momentum_clamp_seconds(cfg.get("mm_end_seconds"), 20),
            MOMENTUM_SECONDS_RANGE[0], MOMENTUM_SECONDS_RANGE[1])
        self.sel_end.valueChanged.connect(
            lambda v: self._on_seconds("mm_end_seconds", v))
        rl.addWidget(tg_end)
        rl.addWidget(lbl)
        rl.addStretch()
        rl.addWidget(hint)
        rl.addWidget(self.sel_end)
        self.v.addWidget(frame_end)

        # permanent save + timestamp toggles
        for key, name, hint_text in (
            ("mm_permanent_save", "PERMANENT CHART SAVE",
             "keep the last chart in Momentum_Saves"),
            ("mm_save_shown_charts", "SAVE EVERY SHOWN CHART",
             "keep each 43/85/116 & end chart in Momentum_Saves"),
            ("mm_timestamp", "MATCH START TIMESTAMP",
             "date/time printed on the saved chart"),
        ):
            frame_t = row_frame()
            rl = QHBoxLayout(frame_t)
            rl.setContentsMargins(14, 8, 14, 8)
            tg = NeonToggle(master_window=master_window,
                            checked=bool(cfg.get(key)))
            tg.toggled.connect(lambda state, k=key: self._on_toggle(k, state))
            self._toggles[key] = tg
            lbl = QLabel(name)
            lbl.setStyleSheet("color: #e2e8f0; font-size: 12.5px; font-weight: 700; "
                              "background: transparent; border: none;")
            hint = QLabel(hint_text)
            hint.setStyleSheet("color: #94a3b8; font-size: 10.5px; font-weight: 700; "
                               "background: transparent; border: none;")
            rl.addWidget(tg)
            rl.addWidget(lbl)
            rl.addStretch()
            rl.addWidget(hint)
            self.v.addWidget(frame_t)

        # --- buttons ----------------------------------------------------------
        btn_row = QHBoxLayout()
        btn_defaults = QPushButton("RESTORE DEFAULTS")
        btn_defaults.setObjectName("DiagBtn")
        btn_defaults.setFixedHeight(46)
        btn_defaults.setCursor(hand)
        btn_defaults.clicked.connect(self._restore_defaults)
        btn_save = QPushButton("SAVE & CLOSE")
        btn_save.setObjectName("NeonActionBtn")
        btn_save.setFixedHeight(46)
        btn_save.setCursor(hand)
        btn_save.clicked.connect(self._save_and_close)
        btn_row.addWidget(btn_defaults)
        btn_row.addStretch()
        btn_row.addWidget(btn_save)
        self.v.addLayout(btn_row)

    # --- handlers -----------------------------------------------------------
    def _on_toggle(self, key, state):
        self.master_window.mom_cfg[key] = bool(state)

    def _on_minute(self, key, value):
        self.master_window.mom_cfg[f"mm_{key}_minute"] = int(value)

    def _on_seconds(self, key, value):
        self.master_window.mom_cfg[key] = int(value)

    def _restore_defaults(self):
        mw = self.master_window
        mw.mom_cfg.update(dict(DEFAULT_MOMENTUM_SETTINGS))
        for key, _name in self.ROW_LABELS:
            self._toggles[key].setChecked(True)
            self._selectors[key].setValue(DEFAULT_MOMENTUM_SETTINGS[f"mm_{key}_minute"])
        self.sel_show.setValue(DEFAULT_MOMENTUM_SETTINGS["mm_show_seconds"])
        self._toggles["mm_end_enabled"].setChecked(True)
        self.sel_end.setValue(DEFAULT_MOMENTUM_SETTINGS["mm_end_seconds"])
        self._toggles["mm_permanent_save"].setChecked(False)
        self._toggles["mm_save_shown_charts"].setChecked(False)
        self._toggles["mm_timestamp"].setChecked(False)

    def _save_and_close(self):
        mw = self.master_window
        cfg = mw.mom_cfg
        for key, _name in self.ROW_LABELS:
            cfg[f"mm_{key}_enabled"] = bool(cfg.get(f"mm_{key}_enabled"))
            cfg[f"mm_{key}_minute"] = momentum_clamp_minutes(key, cfg.get(f"mm_{key}_minute"))
        cfg["mm_show_seconds"] = momentum_clamp_seconds(cfg.get("mm_show_seconds"))
        cfg["mm_end_enabled"] = bool(cfg.get("mm_end_enabled"))
        cfg["mm_end_seconds"] = momentum_clamp_seconds(cfg.get("mm_end_seconds"), 20)
        cfg["mm_permanent_save"] = bool(cfg.get("mm_permanent_save"))
        cfg["mm_save_shown_charts"] = bool(cfg.get("mm_save_shown_charts"))
        cfg["mm_timestamp"] = bool(cfg.get("mm_timestamp"))
        mw.save_config()
        if hasattr(mw, "refresh_momentum_summary"):
            mw.refresh_momentum_summary()
        self.accept()


# =============================================================================
# MomentumUsageModal — HOW TO USE instructions for Match Momentum.
# =============================================================================
class MomentumUsageModal(BaseModalDialog):
    def __init__(self, master_window, parent=None):
        super().__init__(master_window, 620, 360, "HOW TO USE — MATCH MOMENTUM", parent)
        theme = self.master_window.active_theme
        html = (
            "Activate the mod from the <b style='color:" + theme.primary.name() + ";'>"
            "'Select Team'</b> screen and then play the game.<br><br>"
            "At the designated times, the code will display the momentum match chart."
        )
        self.v.addStretch()
        self.v.addWidget(self.make_text(html, "#e0f2fe", "14px"))
        self.v.addStretch()
        self.add_ok("UNDERSTOOD")


# =============================================================================
# ConflictWarningBanner — yellow warning shown while BOTH the Referee View and
# Goal Line Technology mods are enabled at the same time (they may crash the
# game together).
# =============================================================================
class ConflictWarningBanner(QWidget):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.setFixedHeight(48)
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setAttribute(translucent)
        self._phase = 0.0
        self._frozen = False          # v2.2.0 — STATIC MODE freeze
        self._anim = QTimer(self)
        self._anim.setInterval(50)
        self._anim.timeout.connect(self._tick)

    def set_frozen(self, frozen):
        """v2.2.0 STATIC MODE — stop/start the pulse animation."""
        self._frozen = bool(frozen)
        if self._frozen:
            self._anim.stop()
        elif self.isVisible():
            self._anim.start()

    def _tick(self):
        self._phase = (self._phase + 0.08) % (2 * math.pi)
        self.update()

    def showEvent(self, event):
        if not self._frozen:
            self._anim.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._anim.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        w, h = self.width(), self.height()
        t = 0.5 + 0.5 * math.sin(self._phase)   # pulsing brightness 0..1

        bg = lerp_color(QColor("#e6a800"), QColor("#ffd24d"), t)
        bg.setAlpha(242)
        p.setPen(QPen(QColor("#ffe9a8"), 1.6))
        p.setBrush(bg)
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 12, 12)

        fnt = QFont("Segoe UI", 10)
        fnt.setBold(True)
        p.setFont(fnt)
        p.setPen(QColor("#1a1000"))
        text = ("⚠   WARNING — Referee View and Goal Line Technology are both ENABLED.  "
                "Running them at the same time may crash the game.")
        p.drawText(QRectF(16, 0, w - 32, h),
                   Qt.AlignmentFlag.AlignVCenter if IS_PYQT6 else Qt.AlignVCenter, text)
        p.end()

# =============================================================================
# =============================================================================
class UpdateAvailableModal(BaseModalDialog):
    """v1.0.0 — 'A new version is available' modal. Shown on program entry
    (and from ABOUT -> CHECKING FOR UPDATES…) when the developer Gist's
    'Latest Version' is higher than APP_VERSION. The glass DOWNLOAD UPDATE
    pill at the bottom opens the Gist's 'Github Link'; when that link is
    null the button shows the friendly try-again-later error instead."""

    def __init__(self, master_window, latest_version, github_url, parent=None):
        super().__init__(master_window, 560, 360, "UPDATE AVAILABLE", parent)
        mw = self.master_window
        theme = mw.active_theme
        self.github_url = str(github_url or "").strip()
        self.latest_version = str(latest_version or "").strip()

        lbl_big = QLabel(f"v{self.latest_version}")
        lbl_big.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6
                             else Qt.AlignCenter)
        lbl_big.setStyleSheet(
            f"font-size: 34px; font-weight: 1000; letter-spacing: 3px; "
            f"color: {theme.primary.name()}; background: transparent; "
            f"border: none;")
        self.v.addWidget(lbl_big)

        self.v.addWidget(self.make_text(
            "<div align='center'>A new version of "
            "<b>PES \\ eFOOTBALL — MODS BY MILAD</b> is out!</div>",
            "#e0f2fe", "13px"))
        self.v.addWidget(self.make_text(
            f"<div align='center'>Installed version: <b>v{APP_VERSION}</b>"
            f" &nbsp;&bull;&nbsp; Latest version: "
            f"<b>v{self.latest_version}</b></div>",
            "#93c5fd", "12px"))
        self.v.addStretch()

        btn = GlassPillButton(mw, "DOWNLOAD UPDATE", icon="download",
                              height=48, font_px=12.5, min_width=340)
        btn.clicked.connect(self.open_github_link)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(btn)
        row.addStretch()
        self.v.addLayout(row)
        self.v.addStretch()

    def open_github_link(self):
        url = str(self.github_url or "").strip()
        if url:
            try:
                QDesktopServices.openUrl(QUrl(url))
            except Exception:
                pass
            self.accept()
            return
        # "Github Link: null" in the Gist -> ask the user to retry later
        self.master_window.show_message(
            "error", "LINK NOT AVAILABLE",
            "The download link hasn't been published yet.<br>"
            "Please try again later.")


class SettingsModal(BaseModalDialog):
    def __init__(self, master_window, parent=None):
        # NOTE: YouTube links are intentionally NOT part of the general app
        # settings — each mod keeps its own link on its own settings page.
        # v2.2.0 — PERMANENT APP COLOUR (user request #4) and the
        # STATIC-MODE animation freeze (user request #5) live here.
        # v2.3.5 — the window grew again: the v2.2.0 sections pushed the
        # content past the fixed height, so the layout squeezed every row
        # (clipped descriptions, the AUTOMATIC label colliding with its
        # button, SAVE & CLOSE touching the card edge) — the "settings menu
        # overlaps the other menus" report. 640x720 fits the full content.
        super().__init__(master_window, 640, 720, "APPLICATION SETTINGS", parent)
        mw = self.master_window
        theme = mw.active_theme

        lbl_tp = self.make_text("TARGET PROCESS", theme.accent.name(), "11.5px")
        self.v.addWidget(lbl_tp)
        chip = QLabel("FL_2026.exe")
        chip.setFixedHeight(36)
        chip.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        chip.setStyleSheet(f"""
            color: #ffffff; font-weight: 900; font-size: 13px; letter-spacing: 1px;
            background: rgba({theme.bg_dark[1].red()}, {theme.bg_dark[1].green()}, {theme.bg_dark[1].blue()}, 0.85);
            border: 1.2px solid {theme.primary.name()}; border-radius: 8px;
        """)
        self.v.addWidget(chip)

        # --- Game Folder ---
        lbl_gd = self.make_text("GAME FOLDER", theme.accent.name(), "11.5px")
        self.v.addWidget(lbl_gd)
        gd_row = QHBoxLayout()
        self.lbl_gd_status = QLabel()
        self.lbl_gd_status.setWordWrap(True)
        self.lbl_gd_status.setStyleSheet("color: #93c5fd; font-size: 12px; background: transparent; border: none;")
        btn_browse = QPushButton("BROWSE")
        btn_browse.setObjectName("DiagBtn")
        btn_browse.setFixedSize(120, 38)
        btn_browse.clicked.connect(self.browse_folder)
        gd_row.addWidget(self.lbl_gd_status, 1)
        gd_row.addWidget(btn_browse)
        self.v.addLayout(gd_row)
        self.refresh_game_dir_status()

        # --- Background Video Colour Intensity (v2.1.2) ---
        # The clip is black & white; this slider sets how strongly it is
        # colour-graded toward the active mod's theme (0 = pure greyscale).
        lbl_vc = self.make_text("BACKGROUND VIDEO COLOUR", theme.accent.name(), "11.5px")
        self.v.addWidget(lbl_vc)
        vc_row = QHBoxLayout()
        self.slider_vc = CleanCyberSlider(mw)
        self.slider_vc.setRange(0, 100)
        try:
            self.slider_vc.setValue(int(getattr(mw, "video_color_intensity", 100)))
        except Exception:
            self.slider_vc.setValue(100)
        self.lbl_vc_val = QLabel(f"{self.slider_vc.value()}%")
        self.lbl_vc_val.setStyleSheet(
            f"color: {theme.primary.name()}; font-weight: bold; min-width: 44px; background: transparent;")
        vc_row.addWidget(self.slider_vc)
        vc_row.addWidget(self.lbl_vc_val)
        self.v.addLayout(vc_row)
        self.v.addWidget(self.make_text(
            "How strongly the black & white background video is colour-graded "
            "toward each mod's theme.", "#93c5fd", "11px"))
        self.slider_vc.valueChanged.connect(self._on_vc_changed)

        # --- PERMANENT APP COLOUR (v2.2.0, user request #4) -------------
        # Pick ONE colour and the app keeps it forever: switching mods no
        # longer changes the theme. Empty = every mod brings its own theme.
        lbl_pc = self.make_text("PERMANENT APP COLOUR", theme.accent.name(), "11.5px")
        self.v.addWidget(lbl_pc)
        pc_row = QHBoxLayout()
        pc_row.setSpacing(10)
        self.btn_pc_swatch = QPushButton()
        self.btn_pc_swatch.setFixedSize(46, 38)
        self.btn_pc_swatch.setCursor(Qt.CursorShape.PointingHandCursor
                                     if IS_PYQT6 else Qt.PointingHandCursor)
        self.btn_pc_swatch.setToolTip("Pick the permanent app colour")
        self.btn_pc_swatch.clicked.connect(self.pick_permanent_color)
        pc_row.addWidget(self.btn_pc_swatch)
        self.lbl_pc_val = QLabel()
        self.lbl_pc_val.setStyleSheet("font-size: 12px; font-weight: 800; "
                                      "color: #e0f2fe; background: transparent; border: none;")
        pc_row.addWidget(self.lbl_pc_val, 1)
        btn_pc_auto = QPushButton("AUTOMATIC")
        btn_pc_auto.setObjectName("DiagBtn")
        btn_pc_auto.setFixedSize(120, 38)
        btn_pc_auto.setCursor(Qt.CursorShape.PointingHandCursor
                              if IS_PYQT6 else Qt.PointingHandCursor)
        btn_pc_auto.setToolTip("Let every mod bring its own theme colours back")
        btn_pc_auto.clicked.connect(lambda: self.apply_permanent_color(""))
        pc_row.addWidget(btn_pc_auto)
        self.v.addLayout(pc_row)
        self.v.addWidget(self.make_text(
            "Pick one colour and the whole app keeps it permanently — "
            "switching mods will no longer change the theme. AUTOMATIC "
            "returns to each mod's own colours.", "#93c5fd", "11px"))
        self.refresh_permanent_color()

        # --- ANIMATIONS — STATIC MODE (v2.2.0, user request #5) ----------
        lbl_sm = self.make_text("ANIMATIONS", theme.accent.name(), "11.5px")
        self.v.addWidget(lbl_sm)
        sm_row = QHBoxLayout()
        self.lbl_sm = QLabel("FREEZE ALL ANIMATIONS (STATIC MODE)")
        self.lbl_sm.setStyleSheet("font-size: 12px; font-weight: 800; "
                                  "color: #e0f2fe; background: transparent; border: none;")
        self.toggle_static = NeonToggle(master_window=mw,
                                        checked=bool(getattr(mw, "ui_static_mode", False)))
        self.toggle_static.toggled.connect(self._on_static_toggled)
        sm_row.addWidget(self.lbl_sm)
        sm_row.addStretch()
        sm_row.addWidget(self.toggle_static)
        self.v.addLayout(sm_row)
        self.v.addWidget(self.make_text(
            "When this option is ON every animation stops playing and the "
            "whole app becomes a fixed picture: the background video pauses "
            "on its current frame and the particles, glints and pulses "
            "freeze. Turn it off to bring everything back to life.",
            "#93c5fd", "11px"))

        # NOTE: YouTube tutorial links are NOT editable here — since v1.0.0
        # they come from the developer Gist (fetched at the moment a mod's
        # tutorial button is clicked), so no link field exists in the UI.

        self.v.addStretch()
        self.add_ok("SAVE & CLOSE", self.save_and_close)

    # ---------------- permanent colour helpers (v2.2.0) --------------
    def refresh_permanent_color(self):
        mw = self.master_window
        val = str(getattr(mw, "ui_permanent_color", "") or "")
        if val:
            self.btn_pc_swatch.setStyleSheet(
                f"background: {val}; border: 2px solid #ffffff; border-radius: 8px;")
            self.lbl_pc_val.setText(f"FIXED COLOUR — {val.upper()}")
        else:
            self.btn_pc_swatch.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
                " stop:0 #00f0ff, stop:0.33 #00ff88, stop:0.66 #ffb700, stop:1 #ff1e56);"
                " border: 2px solid rgba(255,255,255,120); border-radius: 8px;")
            self.lbl_pc_val.setText("AUTOMATIC — each mod brings its own theme")

    def pick_permanent_color(self):
        mw = self.master_window
        start = str(getattr(mw, "ui_permanent_color", "") or "#00f0ff")
        color = QColorDialog.getColor(QColor(start), self, "Pick the permanent app colour")
        if color.isValid():
            self.apply_permanent_color(color.name())

    def apply_permanent_color(self, hex_or_empty):
        self.master_window.apply_permanent_color(hex_or_empty)
        self.refresh_permanent_color()

    def _on_static_toggled(self, checked):
        self.master_window.set_static_mode(bool(checked))

    def refresh_game_dir_status(self):
        gd = getattr(self.master_window, 'custom_game_dir', APP_DIR)
        exe = os.path.join(gd, "FL_2026.exe")
        if os.path.exists(exe):
            self.lbl_gd_status.setText(f"<span style='color:#00ff88;'>✔ {gd}</span>")
        else:
            self.lbl_gd_status.setText(f"<span style='color:#ff4770;'>✖ FL_2026.exe not found in: {gd}</span>")

    def _on_vc_changed(self, v):
        """v2.1.2 — live-update the background video colour grade."""
        self.lbl_vc_val.setText(f"{v}%")
        mw = self.master_window
        mw.video_color_intensity = int(v)
        if hasattr(mw, "video_bg"):
            mw.video_bg.set_color_intensity(v)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Football Life 2026 Game Directory",
                                                  getattr(self.master_window, 'custom_game_dir', APP_DIR))
        if folder:
            self.master_window.custom_game_dir = folder
            self.refresh_game_dir_status()

    def save_and_close(self):
        mw = self.master_window
        mw.save_config()
        self.accept()

# =============================================================================
# =============================================================================
def _help_tabs_stylesheet(theme):
    """Shared QTabWidget QSS for the ABOUT window and the S.A.O.T guide
    modal (v2.1.9) - one identical glass tab look across the suite."""
    return f"""
        QTabWidget#SaotHelpTabs::pane {{
            border: 1px solid rgba({theme.primary.red()},
                                   {theme.primary.green()},
                                   {theme.primary.blue()}, 90);
            border-radius: 10px;
            top: -1px;
            background: transparent;
        }}
        QTabWidget#SaotHelpTabs > QTabBar::tab {{
            background: rgba({theme.bg_dark[2].red()},
                             {theme.bg_dark[2].green()},
                             {theme.bg_dark[2].blue()}, 0.55);
            color: #93a3b8;
            font-size: 11.5px; font-weight: 900; letter-spacing: 1.5px;
            padding: 8px 30px;
            border: 1px solid rgba({theme.primary.red()},
                                   {theme.primary.green()},
                                   {theme.primary.blue()}, 70);
            border-bottom: none;
            border-top-left-radius: 9px;
            border-top-right-radius: 9px;
            margin-right: 5px;
        }}
        QTabWidget#SaotHelpTabs > QTabBar::tab:selected {{
            color: #ffffff;
            background: rgba({theme.primary.red()},
                             {theme.primary.green()},
                             {theme.primary.blue()}, 120);
            border: 1.4px solid rgba({theme.primary.red()},
                                     {theme.primary.green()},
                                     {theme.primary.blue()}, 200);
        }}
    """


# =============================================================================
# 5d-c. FOOTBALL HUD MORPH MARK — Task 32 redesign
# =============================================================================
# A larger, animation-led identity mark for the header. The mark cycles through
# four football-native visual languages and morphs between them:
#   1) pitch geometry  ->  2) VAR frame / replay reticle
#   3) football core  ->  4) goal-line / offside telemetry
#
# The transitions are deliberately geometric instead of simple icon swaps:
# lines contract toward a common center, rotate, and expand into the next
# football symbol while a restrained scan pulse carries the eye through the
# change. QPainter only — no SVG, Qt Quick, mesh, OBJ, OpenGL scene, or assets.
# =============================================================================

FOOTBALL_HUD_SIZE = 68


class MatchCoreMark(QWidget):
    """Animated football HUD emblem for the main application header."""

    # Seconds spent on each visual language before morphing onward.
    HOLD = 1.65
    MORPH = 0.72
    FPS_MS = 32  # ~31 fps; intentionally light for the tiny header widget.

    def __init__(self, parent=None, size=FOOTBALL_HUD_SIZE):
        super().__init__(parent)
        self._size = max(56, int(size))
        self.setFixedSize(self._size, self._size)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground
                          if IS_PYQT6 else Qt.WA_NoSystemBackground)
        self.setToolTip("PES \\ eFOOTBALL — FOOTBALL HUD")

        self._t = 0.0
        self._last = None
        self._hover = False
        self._frozen = False

        self._timer = QTimer(self)
        self._timer.setInterval(self.FPS_MS)
        self._timer.timeout.connect(self._tick)

    def set_frozen(self, frozen):
        self._frozen = bool(frozen)
        if self._frozen:
            self._timer.stop()
            self._last = None
        elif self.isVisible():
            self._last = time.monotonic()
            self._timer.start()
        self.update()

    def _tick(self):
        now = time.monotonic()
        if self._last is not None:
            dt = max(0.0, min(0.08, now - self._last))
            cycle = self.HOLD + self.MORPH
            self._t = (self._t + dt) % (cycle * 4.0)
        self._last = now
        self.update()

    def showEvent(self, event):
        self._last = time.monotonic()
        if not self._frozen:
            self._timer.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        self._last = None
        super().hideEvent(event)

    def enterEvent(self, event):
        self._hover = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _ease(t):
        t = max(0.0, min(1.0, t))
        return t * t * (3.0 - 2.0 * t)

    @staticmethod
    def _mix(a, b, t):
        return a + (b - a) * t

    @staticmethod
    def _pt(cx, cy, x, y, scale=1.0, rot=0.0):
        a = math.radians(rot)
        xr = x * math.cos(a) - y * math.sin(a)
        yr = x * math.sin(a) + y * math.cos(a)
        return QPointF(cx + xr * scale, cy + yr * scale)

    def _pen(self, rgb, alpha, width):
        pen = QPen(QColor(rgb[0], rgb[1], rgb[2], max(0, min(255, int(alpha)))), width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap if IS_PYQT6 else Qt.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin if IS_PYQT6 else Qt.RoundJoin)
        return pen

    def _draw_glow_line(self, p, a, b, rgb, alpha, width):
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(self._pen(rgb, alpha * 0.18, width * 3.8))
        p.drawLine(a, b)
        p.setPen(self._pen(rgb, alpha, width))
        p.drawLine(a, b)

    def _draw_pitch(self, p, cx, cy, s, alpha, rot=0.0):
        rgb = (84, 230, 255)
        a = max(0, min(255, alpha))
        # Compact top-down pitch with halfway line and penalty-box geometry.
        left, right = -0.34, 0.34
        top, bottom = -0.34, 0.34
        corners = [
            self._pt(cx, cy, left, top, s, rot),
            self._pt(cx, cy, right, top, s, rot),
            self._pt(cx, cy, right, bottom, s, rot),
            self._pt(cx, cy, left, bottom, s, rot),
        ]
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(self._pen(rgb, a, s * 0.028))
        p.drawPolygon(QPolygonF(corners))
        # Halfway line.
        self._draw_glow_line(p,
            self._pt(cx, cy, 0, top, s, rot),
            self._pt(cx, cy, 0, bottom, s, rot),
            rgb, a * 0.78, s * 0.020)
        # Centre circle.
        p.setPen(self._pen(rgb, a * 0.82, s * 0.020))
        p.drawEllipse(self._pt(cx, cy, 0, 0, s, rot), s * 0.085, s * 0.085)
        # Penalty boxes.
        for x0, x1 in ((-0.34, -0.19), (0.19, 0.34)):
            pts = [
                self._pt(cx, cy, x0, -0.18, s, rot),
                self._pt(cx, cy, x1, -0.18, s, rot),
                self._pt(cx, cy, x1, 0.18, s, rot),
                self._pt(cx, cy, x0, 0.18, s, rot),
            ]
            p.drawPolyline(QPolygonF(pts))
        # Corner sparks make the pitch feel like an instrument panel.
        for x, y in ((left, top), (right, top), (right, bottom), (left, bottom)):
            c = self._pt(cx, cy, x, y, s, rot)
            p.setPen(self._pen((218, 251, 255), a * 0.95, s * 0.022))
            p.drawPoint(c)

    def _draw_var(self, p, cx, cy, s, alpha, rot=0.0):
        rgb = (146, 116, 255)
        ice = (226, 244, 255)
        a = max(0, min(255, alpha))
        # Offset monitor corners = VAR/replay framing language.
        k = 0.27
        seg = 0.10
        for sx, sy in ((-1,-1),(1,-1),(1,1),(-1,1)):
            x = sx * k
            y = sy * k
            pts = [
                self._pt(cx, cy, x, y, s, rot),
                self._pt(cx, cy, x - sx * seg, y, s, rot),
                self._pt(cx, cy, x - sx * seg, y + sy * seg, s, rot),
            ]
            p.setPen(self._pen(rgb, a, s * 0.030))
            p.drawPolyline(QPolygonF(pts))
        # Central VAR panel / screen.
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(self._pen(ice, a * 0.78, s * 0.020))
        p.drawRoundedRect(QRectF(cx - s * 0.19, cy - s * 0.15,
                                 s * 0.38, s * 0.30), s * 0.045, s * 0.045)
        # Camera reticle.
        cross = s * 0.13
        self._draw_glow_line(p, QPointF(cx - cross, cy), QPointF(cx + cross, cy), ice, a * 0.9, s * 0.020)
        self._draw_glow_line(p, QPointF(cx, cy - cross), QPointF(cx, cy + cross), ice, a * 0.9, s * 0.020)
        p.setPen(self._pen(rgb, a * 0.60, s * 0.014))
        p.drawEllipse(QPointF(cx, cy), s * 0.09, s * 0.09)

    def _draw_ball(self, p, cx, cy, s, alpha, rot=0.0):
        rgb = (44, 174, 255)
        ice = (231, 250, 255)
        a = max(0, min(255, alpha))
        r = s * 0.22
        # Futuristic pentagon/football core with orbit cuts.
        pts = []
        for i in range(5):
            ang = -90 + i * 72 + rot
            pts.append(self._pt(cx, cy, 0, 0, 0, 0))
            # reset last append below; kept separate to avoid trig duplication
            ar = math.radians(ang)
            pts[-1] = QPointF(cx + math.cos(ar) * r, cy + math.sin(ar) * r)
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        p.setPen(self._pen(ice, a, s * 0.024))
        p.drawPolygon(QPolygonF(pts))
        # Five petals around the pentagon: football-inspired, not a stock glyph.
        for i in range(5):
            ang = math.radians(-90 + i * 72 + rot)
            qx = cx + math.cos(ang) * r * 0.58
            qy = cy + math.sin(ang) * r * 0.58
            p.setPen(self._pen(rgb, a * 0.9, s * 0.018))
            p.drawEllipse(QPointF(qx, qy), s * 0.050, s * 0.050)
            self._draw_glow_line(
                p, QPointF(cx, cy), QPointF(cx + math.cos(ang) * r * 0.78,
                                             cy + math.sin(ang) * r * 0.78),
                rgb, a * 0.72, s * 0.014)
        # Core dot.
        p.setBrush(QBrush(QColor(242, 253, 255, int(a * 0.95))))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawEllipse(QPointF(cx, cy), s * 0.035, s * 0.035)

    def _draw_goal_line(self, p, cx, cy, s, alpha, rot=0.0, scan=0.0):
        rgb = (76, 255, 193)
        ice = (229, 255, 246)
        a = max(0, min(255, alpha))
        # Goal-line / offside telemetry: three parallel field lines + markers.
        for yy, width in ((-0.19, 0.024), (0.0, 0.030), (0.19, 0.024)):
            self._draw_glow_line(p,
                self._pt(cx, cy, -0.30, yy, s, rot),
                self._pt(cx, cy, 0.30, yy, s, rot),
                rgb, a * (0.76 if yy else 1.0), s * width)
        # Vertical goal posts / sampling gates.
        for xx in (-0.27, 0.27):
            self._draw_glow_line(p,
                self._pt(cx, cy, xx, -0.27, s, rot),
                self._pt(cx, cy, xx, 0.27, s, rot),
                ice, a * 0.58, s * 0.016)
        # Moving offside/goal-line telemetry beam.
        beam_x = self._mix(-0.29, 0.29, scan)
        self._draw_glow_line(p,
            self._pt(cx, cy, beam_x, -0.30, s, rot),
            self._pt(cx, cy, beam_x, 0.30, s, rot),
            ice, a * 0.92, s * 0.028)
        # Two receiver nodes.
        for yy in (-0.27, 0.27):
            q = self._pt(cx, cy, beam_x, yy, s, rot)
            p.setBrush(QBrush(QColor(*ice, int(a * 0.95))))
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(q, s * 0.030, s * 0.030)

    def _draw_energy_bracket(self, p, cx, cy, s, alpha, angle):
        rgb = (118, 223, 255)
        a = max(0, min(255, alpha))
        r0 = s * 0.36
        for side in (-1, 1):
            ang = math.radians(angle + side * 90)
            c = QPointF(cx + math.cos(ang) * r0, cy + math.sin(ang) * r0)
            p.setPen(self._pen(rgb, a * 0.78, s * 0.018))
            p.drawPoint(c)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing
                        if IS_PYQT6 else QPainter.Antialiasing)

        w = float(self.width())
        h = float(self.height())
        size = min(w, h)
        cx, cy = w * 0.5, h * 0.5
        # Gentle hover lift: the emblem becomes slightly more alive without
        # stealing attention from the title.
        hover = 1.0 if self._hover else 0.0

        segment = self.HOLD + self.MORPH
        raw = self._t / segment
        index = int(raw) % 4
        local = (raw - int(raw))
        morphing = local > (self.HOLD / segment)
        mt = 0.0 if not morphing else self._ease(
            (local - self.HOLD / segment) / (self.MORPH / segment))
        nxt = (index + 1) % 4

        # Hold weight is intentionally stable; during morph the outgoing and
        # incoming shapes overlap and share the same HUD core.
        weights = [0.0, 0.0, 0.0, 0.0]
        weights[index] = 1.0 - mt
        weights[nxt] = mt

        # Breathing pulse is tied to the full four-state loop.
        pulse = 0.5 + 0.5 * math.sin(self._t * math.pi * 0.95)
        energy = 0.72 + 0.28 * pulse + hover * 0.07
        rotation = math.sin(self._t * 1.3) * 2.0
        scale = size * (0.96 + hover * 0.015)

        # Ambient halo.
        halo_r = size * (0.42 + 0.04 * pulse)
        halo = QRadialGradient(cx, cy, halo_r)
        halo.setColorAt(0.0, QColor(39, 199, 255, int(26 + 22 * pulse)))
        halo.setColorAt(0.50, QColor(42, 112, 255, int(12 + 9 * pulse)))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.setBrush(QBrush(halo))
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

        # State colour accents blend smoothly during the morph.
        state_rgbs = [(84, 230, 255), (146, 116, 255), (44, 174, 255), (76, 255, 193)]
        r = g = b = 0.0
        for i, wt in enumerate(weights):
            r += state_rgbs[i][0] * wt
            g += state_rgbs[i][1] * wt
            b += state_rgbs[i][2] * wt
        core_rgb = (int(r), int(g), int(b))

        # A thin rotating orbit is the connective tissue between all four symbols.
        orbit_r = size * 0.365
        p.setBrush(Qt.BrushStyle.NoBrush if IS_PYQT6 else Qt.NoBrush)
        orbit_pen = self._pen(core_rgb, (78 + 78 * pulse) * energy, size * 0.012)
        p.setPen(orbit_pen)
        start = -52 + self._t * 34.0
        p.drawArc(QRectF(cx - orbit_r, cy - orbit_r, orbit_r * 2, orbit_r * 2),
                  int(-start * 16), int(-82 * 16))
        p.setPen(self._pen((228, 249, 255), (62 + 48 * pulse) * energy, size * 0.009))
        p.drawArc(QRectF(cx - orbit_r * 1.04, cy - orbit_r * 1.04,
                         orbit_r * 2.08, orbit_r * 2.08),
                  int(-(start + 148) * 16), int(-44 * 16))

        # Shared inner core: makes the morph feel like one object transforming,
        # rather than four unrelated icons flashing one after another.
        inner_r = size * 0.115
        core_grad = QRadialGradient(cx - size * 0.025, cy - size * 0.03, inner_r * 2.5)
        core_grad.setColorAt(0.0, QColor(16, 55, 92, int(208 + 26 * pulse)))
        core_grad.setColorAt(0.68, QColor(4, 17, 34, 235))
        core_grad.setColorAt(1.0, QColor(2, 8, 18, 245))
        p.setBrush(QBrush(core_grad))
        p.setPen(self._pen(core_rgb, 135 + 70 * pulse, size * 0.017))
        p.drawEllipse(QPointF(cx, cy), inner_r, inner_r)

        # Draw the four states according to their morph weights.
        if weights[0] > 0.001:
            self._draw_pitch(p, cx, cy, scale, 255 * weights[0] * energy, rotation)
        if weights[1] > 0.001:
            self._draw_var(p, cx, cy, scale, 255 * weights[1] * energy, rotation * 0.55)
        if weights[2] > 0.001:
            self._draw_ball(p, cx, cy, scale, 255 * weights[2] * energy, rotation * 1.3)
        if weights[3] > 0.001:
            scan = 0.5 + 0.5 * math.sin(self._t * math.pi * 1.35)
            self._draw_goal_line(p, cx, cy, scale, 255 * weights[3] * energy,
                                 rotation * 0.7, scan)

        # Micro telemetry points travel with the active state. They create the
        # "lock-on" feeling without introducing another animation system.
        marker_phase = (self._t * 1.15) % 1.0
        markers = [
            (-0.33, -0.33), (0.33, -0.33), (0.33, 0.33), (-0.33, 0.33),
            (0.0, -0.39), (0.0, 0.39),
        ]
        for i, (mx, my) in enumerate(markers):
            twinkle = 0.55 + 0.45 * math.sin((marker_phase + i * 0.17) * math.pi * 2)
            q = self._pt(cx, cy, mx, my, scale, rotation * 0.35)
            p.setBrush(QBrush(QColor(224, 250, 255, int(95 * twinkle * energy))))
            p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
            p.drawEllipse(q, size * 0.016, size * 0.016)

        # Final scan streak: this ties the whole loop together visually.
        streak = (self._t * 0.42) % 1.0
        sy = self._mix(-size * 0.34, size * 0.34, streak)
        p.setPen(self._pen((220, 252, 255), (28 + 42 * pulse) * energy, size * 0.012))
        p.drawLine(QPointF(cx - size * 0.27, cy + sy),
                   QPointF(cx + size * 0.27, cy + sy))

        # Small directional brackets pulse at the two horizontal extremes.
        self._draw_energy_bracket(p, cx, cy, size,
                                  (52 + 56 * pulse) * energy, 0 + self._t * 26.0)

        p.end()


class AboutModal(BaseModalDialog):
    """The identity row uses the animated football HUD mark. It morphs
    between pitch geometry, VAR framing, a football core and goal-line
    telemetry. It is entirely QPainter-based and has no mesh, scene-graph,
    or temporary-asset dependency.

    v2.1.9 - the ABOUT window used to carry TWO tabs; v1.0.1 merges
    them into ONE clean page (user request): the suite identity, the
    short description and the Gist-backed "CHECKING FOR UPDATES…"
    button on top, a hairline divider, then the CONTACT THE DEVELOPER
    centre with FIVE monochrome white glass badges (YouTube, Instagram,
    Telegram, E-mail + GitHub). The four social links are fetched from
    the developer Gist at click time; the GitHub badge opens the
    developer's Gist page on github.com.

    v2.2.0 - the long architecture essay was replaced with a SHORT
    description (user request #6); the contact badges grew to 52 px
    (user request #2)."""

    def __init__(self, master_window, parent=None):
        # v1.2.0 — 640x660: the v1.1.0 spinning jewel (150x170 above the
        # title) is gone and the identity is ONE calm emblem+title row now;
        # the extra 20 px over v1.0.1 keep the v2.3.5 overflow audit green
        # with the same comfortable slack the old merged page had.
        super().__init__(master_window, 760, 780, "ABOUT", parent)
        self.v.addWidget(self._build_page(), 1)
        self.add_ok("CLOSE")

    # ------------------------------------------------------------------
    def _about_support_notice_qss(self, theme):
        r, g, b = theme.primary.red(), theme.primary.green(), theme.primary.blue()
        bg = theme.bg_dark[2]
        br, bgc, bb = theme.bg_dark[1].red(), theme.bg_dark[1].green(), theme.bg_dark[1].blue()
        return f"""
            QFrame#AboutSupportNotice {{
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba({br}, {bgc}, {bb}, 0.86),
                    stop:0.52 rgba({bg.red()}, {bg.green()}, {bg.blue()}, 0.78),
                    stop:1 rgba({r}, {g}, {b}, 0.12));
                border: 1px solid rgba({r}, {g}, {b}, 0.58);
                border-radius: 13px;
            }}
        """

    def _build_page(self):
        """v1.0.1 - the merged single-page layout (the former ABOUT +
        CONTACT & REPORT tabs). One calm top-to-bottom flow, nothing
        overlapping: identity -> description -> update check ->
        divider -> contact centre."""
        theme = self.master_window.active_theme
        page = QWidget()
        v = QVBoxLayout(page)
        # v1.2.1 — expanded ABOUT canvas and removed the top spacer so the
        # content uses the extra height instead of being squeezed into a
        # narrow 640x660 card. This keeps every line fully visible.
        v.setSpacing(12)
        v.addWidget(self._build_identity_block())
        # v2.2.0 (user request #6) — SHORT, concise description: the old
        # three-paragraph architecture essay is gone.
        v.addWidget(self.make_text(
            "One launcher for the FL 2026 mod suite: pick your mods here, "
            "press APPLY and the Bridge wires them into the game.<br>"
            "<b>Compatible exclusively with FL_2026.exe.</b>",
            "#e0f2fe", "12.5px"))

        # Support-cycle notice — a dedicated glass warning keeps the
        # lifecycle message impossible to miss without breaking the
        # visual language of the main modal.
        notice = QFrame()
        notice.setObjectName("AboutSupportNotice")
        nr = QVBoxLayout(notice)
        nr.setContentsMargins(20, 14, 20, 14)
        nr.setSpacing(7)
        nr_title = QLabel("⚠  SUPPORT NOTICE")
        nr_title.setStyleSheet(
            f"font-size: 12px; font-weight: 950; letter-spacing: 1.8px; "
            f"color: {theme.primary.name()}; background: transparent; border: none;")
        nr_text = QLabel(
            "FL 2026 has reached the end of its support cycle.<br>"
            "New mods and future updates will be developed exclusively for FL 2027.")
        nr_text.setWordWrap(True)
        nr_text.setStyleSheet(
            "font-size: 12.5px; font-weight: 700; color: #e2e8f0; "
            "background: transparent; border: none; line-height: 1.45;")
        nr.addWidget(nr_title)
        nr.addWidget(nr_text)
        notice.setStyleSheet(self._about_support_notice_qss(theme))
        v.addWidget(notice)

        # v1.0.0 — the "CHECKING FOR UPDATES…" button runs the REAL update
        # check: it fetches the developer Gist and pops the UPDATE AVAILABLE
        # modal on a newer release (an "UP TO DATE" note otherwise).
        upd_row = QHBoxLayout()
        upd_row.addStretch()
        self.btn_updates = GlassPillButton(
            self.master_window, "CHECKING FOR UPDATES\u2026", icon="restore",
            height=44, font_px=11.5, min_width=340)
        self.btn_updates.clicked.connect(self.check_for_updates)
        upd_row.addWidget(self.btn_updates)
        upd_row.addStretch()
        v.addLayout(upd_row)

        # v1.0.1 — hairline divider: the old tab bar became one calm line
        # separating the suite info from the contact centre.
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: rgba(255,255,255,26); border: none;")
        v.addSpacing(5)
        v.addWidget(divider)
        v.addSpacing(3)

        v.addWidget(self.make_text(
            "<div align='center' style='font-size:16px; font-weight:900; "
            "color:#ffffff; letter-spacing:2px;'>CONTACT THE DEVELOPER</div>",
            "#ffffff", "12px"))
        v.addWidget(self.make_text(
            "Found a <b>bug</b>? Want to <b>suggest a feature</b>? "
            "Pick any channel below and message the developer directly — "
            "every report and every idea helps the mods improve.",
            "#e0f2fe", "12px"))

        grid = QGridLayout()
        grid.setHorizontalSpacing(26)
        grid.setVerticalSpacing(8)
        for i, (kind, tip, _unused_color) in enumerate(CONTACT_BRANDS):
            badge = _ContactIconButton(self.master_window, kind,
                                       QColor("#ffffff"), tip)
            badge.clicked.connect(
                lambda _=False, k=kind: self.master_window.on_contact_clicked(k))
            cap = QLabel(CONTACT_LABELS.get(kind, kind.upper()))
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6
                             else Qt.AlignCenter)
            cap.setStyleSheet("font-size: 11px; font-weight: 800; "
                              "color: #cbd5e1; letter-spacing: 1.4px; "
                              "background: transparent; border: none;")
            col = QVBoxLayout()
            col.setSpacing(6)
            cr = QHBoxLayout()
            cr.addStretch()
            cr.addWidget(badge)
            cr.addStretch()
            col.addLayout(cr)
            col.addWidget(cap)
            gcell = QWidget()
            gcell.setLayout(col)
            grid.addWidget(gcell, 0, i)
        badge_row = QHBoxLayout()
        badge_row.addStretch()
        badge_row.addLayout(grid)
        badge_row.addStretch()
        v.addLayout(badge_row)

        v.addWidget(self.make_text(
            "<div align='center' style='font-size:11px; color:#8ea0b5;'>"
            "E-mail opens your mail app — the other badges open the browser."
            "<br>Thank you for helping the mods grow! ❤</div>",
            "#8ea0b5", "11px"))
        # No trailing stretch: the expanded card now gives the About page
        # natural breathing room while preserving predictable vertical layout.
        return page

    # ------------------------------------------------------------------
    def _build_identity_block(self):
        r"""The suite identity is one calm centred lock-up: the signature
        MatchCore mark sits strictly to the LEFT of the PES \\ eFOOTBALL /
        MODS BY MILAD title lines and remains vertically centred with them."""
        theme = self.master_window.active_theme
        box = QWidget()
        bv = QVBoxLayout(box)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(0)
        row = QHBoxLayout()
        row.setSpacing(16)
        row.addStretch()
        self.emblem = MatchCoreMark(box)
        row.addWidget(self.emblem, 0,
                      Qt.AlignmentFlag.AlignVCenter if IS_PYQT6
                      else Qt.AlignVCenter)
        row.addWidget(self.make_text(
            f"<div align='left' style='font-size:20px; font-weight:900; color:#ffffff; letter-spacing:2px;'>"
            f"PES \\ eFOOTBALL</div>"
            f"<div align='left' style='font-size:12px; font-weight:900; color:{theme.primary.name()}; letter-spacing:3px;'>"
            f"MODS BY MILAD</div>", "#ffffff", "12px"))
        row.addStretch()
        bv.addLayout(row)
        return box

    # ------------------------------------------------------------------
    def check_for_updates(self):
        """v1.0.0 — manual update check: fetches the developer Gist and
        pops the UPDATE AVAILABLE modal on a newer release, shows a
        friendly 'up to date' note otherwise, a try-later error offline."""
        self.master_window.check_for_updates_clicked()

# =============================================================================
# =============================================================================
class CloseConfirmModal(BaseModalDialog):
    """v2.1.2 — friendly DONATION prompt shown on every normal close.
    The old "are you sure you want to close MyMods?" text is gone; the
    user gets a warm thank-you with real donation options instead."""

    def __init__(self, master_window, parent=None):
        # v2.3.5 — 430 high: the donate buttons and note no longer overflow
        # the card (content min 314 px vs 288 px available at 360).
        super().__init__(master_window, 560, 430, "THANK YOU", parent)
        theme = self.master_window.active_theme
        p_name = theme.primary.name()
        a_name = theme.accent.name()

        # heart badge
        heart = QLabel("\u2764")
        heart.setFixedSize(58, 58)
        heart.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        heart.setStyleSheet(f"""
            color: #ff2d78; font-size: 27px; font-weight: 900;
            border: 1.8px solid #ff2d78; border-radius: 29px; background: transparent;
        """)
        heart_row = QHBoxLayout()
        heart_row.addStretch()
        heart_row.addWidget(heart)
        heart_row.addStretch()
        self.v.addLayout(heart_row)

        self.v.addWidget(self.make_text(
            f"<div align='center' style='font-size:16.5px; font-weight:900; "
            f"color:#ffffff; letter-spacing:1.5px;'>THANK YOU FOR USING<br>"
            f"FL 2026 MODS BY MILAD</div>", "#ffffff", "12px"))
        self.v.addWidget(self.make_text(
            "Every mod is built and updated with love, for free.<br>"
            "If they make your game more fun, please consider a small "
            "donation — it keeps the updates coming. \u2764",
            "#e0f2fe", "12.5px"))
        self.v.addStretch()

        row = QHBoxLayout()
        btn_donate = QPushButton("\u2764 DONATE")
        btn_donate.setObjectName("VibrantDonateBtn")
        btn_donate.setFixedHeight(46)
        btn_donate.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_donate.clicked.connect(self._donate)

        btn_cancel = QPushButton("CANCEL")
        btn_cancel.setObjectName("DiagBtn")
        btn_cancel.setFixedHeight(46)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)

        btn_exit = QPushButton("EXIT")
        btn_exit.setObjectName("DangerBtn")
        btn_exit.setFixedHeight(46)
        btn_exit.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        btn_exit.clicked.connect(self.accept)

        row.addWidget(btn_donate)
        row.addStretch()
        row.addWidget(btn_cancel)
        row.addWidget(btn_exit)
        self.v.addLayout(row)

    def _donate(self):
        mw = self.master_window
        if mw.open_donate():
            self.accept()          # link opened — close the app warmly
        else:
            mw.on_donate_clicked()  # friendly "options coming soon" note

# =============================================================================
# =============================================================================
class YouTubeButton(QWidget):
    clicked = pyqtSignal()

    def __init__(self, master_window, caption="WATCH VIDEO TUTORIAL", parent=None):
        super().__init__(parent)
        self.master_window = master_window
        self.caption = caption
        self.setFixedSize(300, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor)
        self.is_hovered = False

    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)
        theme = self.master_window.active_theme
        w, h = self.width(), self.height()

        bg_alpha = 245 if self.is_hovered else 215
        p.setBrush(QColor(12, 18, 32, bg_alpha))
        if self.is_hovered:
            p.setPen(QPen(theme.primary, 1.4))
        else:
            p.setPen(QPen(QColor(theme.primary.red(), theme.primary.green(), theme.primary.blue(), 90), 1.2))
        p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 10, 10)

        logo = QRectF(10, (h - 30) / 2, 46, 30)
        p.setBrush(QColor("#FF0000") if not self.is_hovered else QColor("#FF1E1E"))
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(logo, 8, 8)

        cx = logo.center()
        tri = QPolygonF([QPointF(cx.x() - 6, cx.y() - 9),
                         QPointF(cx.x() - 6, cx.y() + 9),
                         QPointF(cx.x() + 10, cx.y())])
        p.setBrush(QColor(255, 255, 255))
        p.drawPolygon(tri)

        fnt = QFont("Segoe UI", 10)
        fnt.setBold(True)
        p.setFont(fnt)
        p.setPen(QColor(255, 255, 255))
        p.drawText(QRectF(66, 0, w - 70, h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft if IS_PYQT6 else Qt.AlignVCenter | Qt.AlignLeft,
                   self.caption)
        p.end()

# =============================================================================
# 12. Master Cyber Window with Smooth Fluid Theme Transitions
#        - Show Video Overlay
# =============================================================================
class MasterCyberWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PES \\ eFOOTBALL MODS BY MILAD - FL 2026")
        self.resize(1560, 960)
        self.setMinimumSize(1480, 930)

        frameless = Qt.WindowType.FramelessWindowHint if IS_PYQT6 else Qt.FramelessWindowHint
        translucent = Qt.WidgetAttribute.WA_TranslucentBackground if IS_PYQT6 else Qt.WA_TranslucentBackground
        self.setWindowFlags(frameless)
        self.setAttribute(translucent)

        self.drag_position = QPoint()
        self.border_phase = 0.0
        # v2.1.2 — True while closing because the Bridge was just launched
        # (that close skips the donation exit prompt by design)
        self._bridge_launch_close = False

        self.custom_game_dir = APP_DIR
        self._syncing_toggle = False
        self.current_mod_name = "S.A.O.T"
        self.ref_cfg = dict(DEFAULT_REF_SETTINGS)

        self.load_config()

        # Active dynamic theme + start/target themes for smooth interpolation
        self.active_theme = THEMES["S.A.O.T"].clone()
        self.start_theme = THEMES["S.A.O.T"].clone()
        self.target_theme = THEMES["S.A.O.T"].clone()
        # v2.2.0 — PERMANENT APP COLOUR: if the user picked one, the whole
        # UI builds in that theme right away and mod switching never
        # changes it (see _theme_for_selection).
        _perm = self.permanent_theme()
        if _perm is not None:
            self.active_theme = _perm.clone()
            self.start_theme = _perm.clone()
            self.target_theme = _perm.clone()

        # Smooth theme transition animation
        self.theme_anim = QVariantAnimation(self)
        self.theme_anim.setDuration(350)
        self.theme_anim.setStartValue(0.0)
        self.theme_anim.setEndValue(1.0)
        curve = QEasingCurve.Type.InOutCubic if IS_PYQT6 else QEasingCurve.InOutCubic
        self.theme_anim.setEasingCurve(curve)
        self.theme_anim.valueChanged.connect(self._on_theme_anim_step)
        self.theme_anim.finished.connect(self._on_theme_anim_finished)

        self.bg_cache = None
        self.sprite_lib = ParticleSpriteLibrary.get_instance()
        self.particles = [SmoothParticle(1560, 960, self.sprite_lib, True) for _ in range(380)]

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.on_frame_update)
        self.timer.start(16)

        # v1.0.0 — Gist signal bus: the background fetch threads hand their
        # results to the GUI thread through these queued signals.
        self.gist_bus = GistSignalBus(self)
        self.gist_bus.update_checked.connect(self._on_update_checked)
        self.gist_bus.tutorial_fetched.connect(self._on_tutorial_fetched)
        self.gist_bus.contact_fetched.connect(self._on_contact_fetched)

        self.initUI()
        self.applyStyles()

        if self.current_mod_name in THEMES:
            self.onModSelected(self.current_mod_name)
            self._on_theme_anim_finished()

        # v2.2.0 — STATIC MODE (user request #5): if the user saved the
        # freeze option, every animation stops right after startup — the
        # video pauses on its current frame, particles/glints never run.
        self.apply_static_mode()

        QTimer.singleShot(250, self.quick_check_diagnostics)

        # v1.0.0 — update check on program entry: the Gist is fetched in a
        # background thread; a newer release pops the UPDATE AVAILABLE modal.
        # Flip UPDATE_CHECK_AT_STARTUP to False to make checking strictly
        # manual (ABOUT -> CHECKING FOR UPDATES…).
        QTimer.singleShot(1400, self._startup_update_check)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def load_config(self):
        cfg = {
            "config_version": 3,
            "game_process": TARGET_PROCESS,
            "game_dir": APP_DIR,
            "last_selected_mod": "S.A.O.T",
            "mods": {},
        }
        needs_migration = False
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    try:
                        old_ver = int(data.get("config_version") or 2)
                    except (TypeError, ValueError):
                        old_ver = 2
                    needs_migration = old_ver < 3
                    cfg.update(data)
            except Exception:
                pass

        if needs_migration:
            for m in cfg.get("mods", {}).values():
                if isinstance(m, dict):
                    m["enabled"] = False

        self.custom_game_dir = cfg.get("game_dir", APP_DIR)
        if not os.path.isdir(self.custom_game_dir):
            self.custom_game_dir = APP_DIR
        mods_raw = cfg.get("mods", {})
        if isinstance(mods_raw, dict) and "GLT" in mods_raw and GLT_MOD_NAME not in mods_raw:
            mods_raw[GLT_MOD_NAME] = dict(mods_raw["GLT"])
        self.current_mod_name = cfg.get("last_selected_mod", "Referee View")
        if self.current_mod_name == "GLT":
            self.current_mod_name = GLT_MOD_NAME
        # v2.1.2 — only IMPLEMENTED mods can be selected: a saved
        # not-yet-submitted selection (or the old S.A.O.T default) falls
        # back to the first working mod.
        if (self.current_mod_name not in THEMES
                or self.current_mod_name not in IMPLEMENTED_MOD_NAMES):
            self.current_mod_name = "Referee View"

        self.mods_state = {}
        for name in THEMES.keys():
            saved = cfg.get("mods", {}).get(name, {})
            enabled = bool(saved.get("enabled", False))
            # v2.1.2 — not-yet-submitted mods are always INACTIVE, no matter
            # what an old config file says.
            if name not in IMPLEMENTED_MOD_NAMES:
                enabled = False
            self.mods_state[name] = {"enabled": enabled, "opacity": 80, "intensity": 75}

        # v2.1.2 — background video colour intensity (0..100, 100 = full
        # theme tint). The clip is black & white, so this controls how
        # strongly it is colour-graded toward the active mod's theme.
        try:
            self.video_color_intensity = max(0, min(100, int(cfg.get("video_color_intensity", 100))))
        except Exception:
            self.video_color_intensity = 100

        # v2.2.0 — PERMANENT APP COLOUR + STATIC MODE (user requests #4/#5).
        # ui_permanent_color: hex string; empty = follow each mod's theme.
        # ui_static_mode: True = every animation frozen (video paused on
        # its current frame, particles/glints/pulses stopped).
        color_val = str(cfg.get("ui_permanent_color", "") or "").strip()
        self.ui_permanent_color = color_val if QColor(color_val).isValid() else ""
        self.ui_static_mode = bool(cfg.get("ui_static_mode", False))

        ref_saved = cfg.get("mods", {}).get("Referee View", {})
        self.ref_cfg = {
            "enabled": bool(ref_saved.get("enabled", False)),
            "overlay": bool(ref_saved.get("show_video_overlay", True)),
            "vk": str(ref_saved.get("apply_key_vk", "0x54")),
            "name": str(ref_saved.get("apply_key_name", "T")),
            "url": str(ref_saved.get("tutorial_url", "")),
        }

        glt_saved = cfg.get("mods", {}).get(GLT_MOD_NAME, {})
        if not glt_saved:
            glt_saved = cfg.get("mods", {}).get("GLT", {}) or {}
        self.glt_cfg = {
            "enabled": bool(glt_saved.get("enabled", False)),
        }
        for vk_f, name_f, d_vk, d_name in (
            ("glt_play_vk", "glt_play_name", DEFAULT_GLT_SETTINGS["play_vk"], DEFAULT_GLT_SETTINGS["play_name"]),
            ("glt_rec_vk", "glt_rec_name", DEFAULT_GLT_SETTINGS["rec_vk"], DEFAULT_GLT_SETTINGS["rec_name"]),
        ):
            if vk_f in glt_saved:
                self.glt_cfg[vk_f.replace("glt_", "").replace("_vk", "_vk")] = str(glt_saved.get(vk_f) or "")
                self.glt_cfg[vk_f.replace("glt_", "").replace("_vk", "_name")] = str(glt_saved.get(name_f) or "")
            else:
                self.glt_cfg[vk_f.replace("glt_", "").replace("_vk", "_vk")] = d_vk
                self.glt_cfg[vk_f.replace("glt_", "").replace("_vk", "_name")] = d_name
        self.glt_cfg["style"] = str(glt_saved.get("glt_style", DEFAULT_GLT_SETTINGS["style"]) or "T6")

        mom_saved = cfg.get("mods", {}).get(MOMENTUM_MOD_NAME, {})
        self.mom_cfg = dict(DEFAULT_MOMENTUM_SETTINGS)
        self.mom_cfg["enabled"] = bool(mom_saved.get("enabled", False))
        for key in DEFAULT_MOMENTUM_SETTINGS:
            if key in mom_saved:
                self.mom_cfg[key] = mom_saved[key]
        for key in ("h1", "h2", "et"):
            self.mom_cfg[f"mm_{key}_minute"] = momentum_clamp_minutes(
                key, self.mom_cfg.get(f"mm_{key}_minute"))
            self.mom_cfg[f"mm_{key}_enabled"] = bool(self.mom_cfg.get(f"mm_{key}_enabled"))
        self.mom_cfg["mm_show_seconds"] = momentum_clamp_seconds(
            self.mom_cfg.get("mm_show_seconds"))
        self.mom_cfg["mm_end_enabled"] = bool(self.mom_cfg.get("mm_end_enabled"))
        self.mom_cfg["mm_end_seconds"] = momentum_clamp_seconds(
            self.mom_cfg.get("mm_end_seconds"), 20)
        self.mom_cfg["mm_permanent_save"] = bool(self.mom_cfg.get("mm_permanent_save"))
        self.mom_cfg["mm_save_shown_charts"] = bool(self.mom_cfg.get("mm_save_shown_charts"))
        self.mom_cfg["mm_timestamp"] = bool(self.mom_cfg.get("mm_timestamp"))

        hm_saved = cfg.get("mods", {}).get(HEATMAP_MOD_NAME, {})
        self.hm_cfg = dict(DEFAULT_HEATMAP_SETTINGS)
        self.hm_cfg["enabled"] = bool(hm_saved.get("enabled", False))
        for key in DEFAULT_HEATMAP_SETTINGS:
            if key in hm_saved:
                self.hm_cfg[key] = hm_saved[key]
        self.hm_cfg["hm_display_minute"] = heatmap_clamp_display_minute(
            self.hm_cfg.get("hm_display_minute"))
        self.hm_cfg["hm_viewer_side"] = heatmap_clamp_side(
            self.hm_cfg.get("hm_viewer_side"))
        self.hm_cfg["hm_gain"] = heatmap_clamp_float(self.hm_cfg.get("hm_gain"), 0.2, 8.0, 3.3)
        self.hm_cfg["hm_ceiling"] = heatmap_clamp_float(self.hm_cfg.get("hm_ceiling"), 0.1, 8.0, 0.4)
        self.hm_cfg["hm_gamma"] = heatmap_clamp_float(self.hm_cfg.get("hm_gamma"), 0.2, 1.5, 0.85)
        self.hm_cfg["hm_blur_m"] = heatmap_clamp_float(self.hm_cfg.get("hm_blur_m"), 0.5, 3.0, 1.4)
        self.hm_cfg["hm_feather"] = heatmap_clamp_float(self.hm_cfg.get("hm_feather"), 0.0, 25.0, 9.0)
        self.hm_cfg["hm_cutoff"] = heatmap_clamp_float(self.hm_cfg.get("hm_cutoff"), 0.0, 0.35, 0.2)

        # [suite v2.1.7] S.A.O.T — the menu's ONLY option is the CALL KEY
        # (mods -> S.A.O.T -> apply_key_vk / apply_key_name, default F1).
        saot_saved = cfg.get("mods", {}).get(SAOT_MOD_NAME, {})
        self.saot_cfg = {
            "enabled": bool(saot_saved.get("enabled", False)),
            "call_vk": str(saot_saved.get("apply_key_vk","") or ""),
            "call_name": str(saot_saved.get("apply_key_name","") or ""),
        }

        # v2.1.6 — category expanded/collapsed state (ModsConfig ui key).
        # Missing key / old config = every category expanded (default).
        ui_cfg = cfg.get("ui", {}) if isinstance(cfg.get("ui", {}), dict) else {}
        exp_cfg = ui_cfg.get("expanded", {}) if isinstance(ui_cfg.get("expanded", {}), dict) else {}
        self.cat_expanded = {}
        for cat_name, _members in MOD_CATEGORIES:
            self.cat_expanded[cat_name] = bool(exp_cfg.get(cat_name, True))

        self.mod_keys = {}
        for name in THEMES.keys():
            saved_key = cfg.get("mods", {}).get(name, {})
            self.mod_keys[name] = {
                "vk": str(saved_key.get("apply_key_vk", "") or ""),
                "name": str(saved_key.get("apply_key_name", "") or ""),
            }
        # [suite v2.1.7] S.A.O.T call key — a config without a key falls
        # back to the original tool's own default (F1) so the summoned
        # GUI can never become unreachable.
        saot_k = self.mod_keys.get(SAOT_MOD_NAME) or {"vk": "", "name": ""}
        if not saot_k.get("vk"):
            self.mod_keys[SAOT_MOD_NAME] = {
                "vk": DEFAULT_SAOT_SETTINGS["call_vk"],
                "name": DEFAULT_SAOT_SETTINGS["call_name"],
            }
        self.saot_cfg["call_vk"] = self.mod_keys[SAOT_MOD_NAME]["vk"]
        self.saot_cfg["call_name"] = self.mod_keys[SAOT_MOD_NAME]["name"]
        if "apply_key_vk" in ref_saved:
            self.mod_keys["Referee View"] = {
                "vk": str(ref_saved.get("apply_key_vk") or ""),
                "name": str(ref_saved.get("apply_key_name") or ""),
            }
        else:
            self.mod_keys["Referee View"] = {"vk": DEFAULT_REF_SETTINGS["vk"], "name": DEFAULT_REF_SETTINGS["name"]}
        self.ref_cfg["vk"] = self.mod_keys["Referee View"]["vk"]
        self.ref_cfg["name"] = self.mod_keys["Referee View"]["name"]

        if needs_migration:
            self.save_config()

    def save_config(self):
        cfg = {
            "config_version": 3,
            "game_process": TARGET_PROCESS,
            "game_dir": self.custom_game_dir,
            "last_selected_mod": self.current_mod_name,
            "video_color_intensity": int(getattr(self, "video_color_intensity", 100)),
            # v2.2.0 — permanent app colour + static animation mode
            "ui_permanent_color": str(getattr(self, "ui_permanent_color", "") or ""),
            "ui_static_mode": bool(getattr(self, "ui_static_mode", False)),
            "mods": {},
        }
        for name, st in self.mods_state.items():
            cfg["mods"][name] = {"enabled": bool(st["enabled"])}
        ref = cfg["mods"].setdefault("Referee View", {})
        ref["enabled"] = bool(self.mods_state.get("Referee View", {}).get("enabled", False))
        ref["show_video_overlay"] = bool(self.ref_cfg.get("overlay", True))
        ref["apply_key_vk"] = str(self.ref_cfg.get("vk", "0x54"))
        ref["apply_key_name"] = str(self.ref_cfg.get("name", "T"))
        ref["tutorial_url"] = str(self.ref_cfg.get("url", ""))
        glt = cfg["mods"].setdefault(GLT_MOD_NAME, {})
        glt["enabled"] = bool(self.mods_state.get(GLT_MOD_NAME, {}).get("enabled", False))
        glt["glt_play_vk"] = str(self.glt_cfg.get("play_vk", "") or "")
        glt["glt_play_name"] = str(self.glt_cfg.get("play_name", "") or "")
        glt["glt_rec_vk"] = str(self.glt_cfg.get("rec_vk", "") or "")
        glt["glt_rec_name"] = str(self.glt_cfg.get("rec_name", "") or "")
        glt["glt_style"] = str(self.glt_cfg.get("style", "T6") or "T6")
        # Animation button bindings are NEVER user-typed: they are read from
        # the game settings file (settings.dat) and shipped to the dedicated
        # GLT tool through this JSON (the tool runs without MyMods).
        try:
            glt.update(glt_animation_keys_from_settings_dat())
        except Exception:
            pass
        cfg["mods"].pop("GLT", None)
        mom = cfg["mods"].setdefault(MOMENTUM_MOD_NAME, {})
        mom["enabled"] = bool(self.mods_state.get(MOMENTUM_MOD_NAME, {}).get("enabled", False))
        for key, val in self.mom_cfg.items():
            if key != "enabled":
                mom[key] = val
        hm = cfg["mods"].setdefault(HEATMAP_MOD_NAME, {})
        hm["enabled"] = bool(self.mods_state.get(HEATMAP_MOD_NAME, {}).get("enabled", False))
        for key, val in self.hm_cfg.items():
            if key != "enabled":
                hm[key] = val
        for name, entry in self.mod_keys.items():
            if name in ("Referee View", GLT_MOD_NAME):
                continue
            m = cfg["mods"].setdefault(name, {})
            m["apply_key_vk"] = str(entry.get("vk", "") or "")
            m["apply_key_name"] = str(entry.get("name", "") or "")
        try:
            cfg["ui"] = {"expanded": dict(getattr(self, "cat_expanded", {}))}
        except Exception:
            pass
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def quick_check_diagnostics(self):
        has_issue = False
        path = get_settings_dat_path()
        if not os.path.exists(path):
            has_issue = True
        else:
            try:
                with open(path, 'rb') as f:
                    data = f.read()
                if len(data) < 9 or data[8] != 0x6E:
                    has_issue = True
            except Exception:
                has_issue = True

        exe1 = os.path.join(self.custom_game_dir, "FL_2026.exe")
        if not os.path.exists(exe1):
            has_issue = True

        self.btn_alert.setStatus(has_issue)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'dim_overlay') and self.dim_overlay:
            self.dim_overlay.setGeometry(self.centralWidget().rect())
        self._sync_overlay_geometry()
        self._rebuild_bg_cache()

    def _sync_overlay_geometry(self):
        """Keep the video background covering the whole central canvas and
        visible only while it actually renders. v2.1.8 — the particle
        layer above the video was REMOVED: when the video plays, nothing
        code-drawn runs on top of it (the painted gradient + particles
        are now a strict fallback for a missing video)."""
        c = self.centralWidget()
        if c is None:
            return
        r = c.rect()
        vb = getattr(self, "video_bg", None)
        if vb is not None:
            vb.setGeometry(r)
            vb.setVisible(vb.is_active())

    def video_active(self):
        """True while the GPU video background is actually rendering."""
        vb = getattr(self, "video_bg", None)
        return bool(vb is not None and vb.is_active() and vb.isVisible())

    def _rebuild_bg_cache(self):
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        self.bg_cache = QPixmap(w, h)
        p = QPainter(self.bg_cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing if IS_PYQT6 else QPainter.Antialiasing)

        theme = self.active_theme
        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, theme.bg_dark[0])
        bg.setColorAt(0.35, theme.bg_dark[1])
        bg.setColorAt(0.75, theme.bg_dark[2])
        bg.setColorAt(1.0, theme.bg_dark[3])
        p.setBrush(bg)
        p.setPen(Qt.PenStyle.NoPen if IS_PYQT6 else Qt.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), 22, 22)

        pr, pg, pb = theme.primary.red(), theme.primary.green(), theme.primary.blue()
        sr, sg, sb = theme.secondary.red(), theme.secondary.green(), theme.secondary.blue()

        top_glow = QRadialGradient(w / 2, -h * 0.1, h * 0.75)
        top_glow.setColorAt(0.0, QColor(pr, pg, pb, 45))
        top_glow.setColorAt(0.5, QColor(sr, sg, sb, 16))
        top_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(top_glow)
        p.drawRect(QRectF(0, 0, w, h * 0.75))

        bottom_glow = QRadialGradient(w / 2, h + 40, h * 0.55)
        bottom_glow.setColorAt(0.0, QColor(pr, pg, pb, 80))
        bottom_glow.setColorAt(0.4, QColor(sr, sg, sb, 35))
        bottom_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(bottom_glow)
        p.drawRect(QRectF(0, h * 0.45, w, h * 0.55))

        p.end()

    def on_frame_update(self):
        w, h = self.width(), self.height()
        self.border_phase = (self.border_phase + 0.024) % (2 * math.pi)

        # v2.1.8 — the painted-gradient + particle background is a FALLBACK
        # only: it runs exclusively while the video background is NOT
        # active (file missing / codec missing / player failed). While the
        # video plays, none of the code-drawn background work happens at
        # all — no particle animation, no overlay repaints, no full-window
        # repaints (user request: only the video must run; the code
        # background must not keep working behind it).
        if not self.video_active():
            for pt in self.particles:
                pt.update(w, h)
            self.update()          # repaint the painted fallback canvas

        if hasattr(self, 'btn_launch'):
            self.btn_launch.advance_animation(0.016)

        if hasattr(self, 'btn_alert'):
            self.btn_alert.advance_pulse()

    def _fl_link_stylesheet(self, theme):
        """Theme-aware styling for the clickable FL 2026 header label."""
        normal = theme.accent.name()
        hover = theme.primary.name()
        return f"""
            QLabel#FlLinkLabel {{
                font-size: 34px; font-weight: 1000; color: {normal};
                letter-spacing: 3px; background: transparent; border: none;
            }}
            QLabel#FlLinkLabel:hover {{
                color: {hover};
            }}
        """

    def initUI(self):
        central_widget = MainCanvasWidget(self)
        self.setCentralWidget(central_widget)

        # --- GPU video background (Background/Back.mp4). v2.1.8 — this is
        # the ONLY live background: while it renders, nothing code-drawn
        # runs behind or above it. The classic painted gradient + particles
        # take over ONLY when the video file/stack is unavailable.
        self.video_bg = VideoBackgroundWidget(self, central_widget)
        # v2.1.2 — apply the persisted colour-intensity to the B&W video
        try:
            self.video_bg.set_color_intensity(self.video_color_intensity)
        except Exception:
            pass

        self.dim_overlay = QWidget(central_widget)
        self.dim_overlay.setObjectName("DimOverlay")
        self.dim_overlay.setStyleSheet("background-color: rgba(2, 6, 16, 175);")
        self.dim_overlay.hide()

        root_vbox = QVBoxLayout(central_widget)
        root_vbox.setContentsMargins(32, 14, 32, 14)
        root_vbox.setSpacing(12)

        # ------------------ Header ------------------
        header_layout = QHBoxLayout()

        logo_box = QHBoxLayout()
        logo_box.setSpacing(10)

        # Task 32 — signature 2D MatchCore mark.
        # Pure QPainter; no 3D scene graph, temporary mesh/object files,
        # Qt Quick widgets, SVG assets, or renderer fallback path.
        self.logo_icon = MatchCoreMark(central_widget, size=68)
        logo_box.addWidget(self.logo_icon, 0,
                           Qt.AlignmentFlag.AlignVCenter if IS_PYQT6
                           else Qt.AlignVCenter)

        title_vbox = QVBoxLayout()
        title_vbox.setSpacing(1)

        lbl_app = QLabel("PES \\ eFOOTBALL")
        lbl_app.setStyleSheet("font-size: 24px; font-weight: 950; letter-spacing: 2px; color: #ffffff; background: transparent;")

        self.lbl_sub = QLabel("MODS BY MILAD")
        self.lbl_sub.setStyleSheet(f"font-size: 12px; font-weight: 900; color: {self.active_theme.primary.name()}; letter-spacing: 3px; background: transparent;")

        title_vbox.addWidget(lbl_app)
        title_vbox.addWidget(self.lbl_sub)
        logo_box.addLayout(title_vbox)
        header_layout.addLayout(logo_box)

        header_layout.addStretch()

        center_banner_vbox = QVBoxLayout()
        center_banner_vbox.setSpacing(4)
        center_banner_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)

        self.lbl_compat_title = QLabel("COMPATIBLE WITH")
        self.lbl_compat_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; letter-spacing: 3px; background: transparent; border: none;")
        self.lbl_compat_title.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)

        # v2.1.9 (user request #4) — the big "FL 2026" name in the top box
        # is now CLICKABLE: it opens the official FL 2026 download page
        # (pessmokepatch.com). Hand cursor + hover tint + tooltip make the
        # affordance obvious.
        self.lbl_compat_fl = QLabel("FL 2026")
        self.lbl_compat_fl.setObjectName("FlLinkLabel")
        self.lbl_compat_fl.setStyleSheet(
            self._fl_link_stylesheet(self.active_theme))
        self.lbl_compat_fl.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)
        self.lbl_compat_fl.setCursor(Qt.CursorShape.PointingHandCursor if IS_PYQT6
                                     else Qt.PointingHandCursor)
        self.lbl_compat_fl.setToolTip("Open the official FL 2026 download page\n"
                                      + FL2026_DOWNLOAD_URL)

        def _open_fl2026_page(_event):
            QDesktopServices.openUrl(QUrl(FL2026_DOWNLOAD_URL))

        self.lbl_compat_fl.mouseReleaseEvent = _open_fl2026_page

        self.fl_glow = QGraphicsDropShadowEffect(self)
        self.fl_glow.setBlurRadius(22)
        self.fl_glow.setColor(self.active_theme.glow_color)
        self.fl_glow.setOffset(0, 0)
        self.lbl_compat_fl.setGraphicsEffect(self.fl_glow)

        center_banner_vbox.addWidget(self.lbl_compat_title)
        center_banner_vbox.addWidget(self.lbl_compat_fl)

        self.btn_alert = BlinkingAlertButton()
        self.btn_alert.clicked.connect(self.openRealDiagnostics)
        center_banner_vbox.addWidget(self.btn_alert)

        header_layout.addLayout(center_banner_vbox)
        header_layout.addStretch()

        btn_gear = QPushButton("⚙")
        btn_gear.setObjectName("IconBtn")
        btn_gear.clicked.connect(self.openSettingsModal)
        header_layout.addWidget(btn_gear)

        btn_info = QPushButton("ⓘ")
        btn_info.setObjectName("IconBtn")
        btn_info.clicked.connect(self.openAboutModal)
        header_layout.addWidget(btn_info)

        # v2.1.6 — the header sponsor button is now a liquid-glass pill
        # with a heart badge (user spec #2): far more attractive than the
        # old flat gradient rectangle, and it follows every theme's glass.
        # v2.1.8 — min_width so the label always reads "DONATE" (previously
        # the header squeezed the pill until the text elided into "…",
        # which looked like a mysterious three-dots button).
        self.btn_donate = GlassPillButton(self, "DONATE", icon="heart",
                                          accent="#ff2d78", height=40,
                                          font_px=12, min_width=150)
        self.btn_donate.clicked.connect(self.on_donate_clicked)
        header_layout.addWidget(self.btn_donate)

        btn_min = QPushButton("🗕")
        btn_min.setObjectName("WindowBtn")
        btn_min.clicked.connect(self.showMinimized)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseBtn")
        btn_close.clicked.connect(self.confirm_exit)

        header_layout.addWidget(btn_min)
        header_layout.addWidget(btn_close)

        root_vbox.addLayout(header_layout)

        # (v2.1.9) the old top CONTACT bar was removed - the contact
        # badges + bug/feature reporting now live in the ABOUT window
        # (its "CONTACT & REPORT" tab, user request #1).

        # ------------------ Dual-Mod Yellow Warning Banner ------------------
        # Visible whenever Referee View + Goal Line Technology are enabled at
        # the same time (they may crash the game together).
        self.warning_banner = ConflictWarningBanner(self)
        self.warning_banner.hide()
        root_vbox.addWidget(self.warning_banner)

        # ------------------ Main Body ------------------
        body_container = QHBoxLayout()
        body_container.setSpacing(24)
        body_container.setAlignment(Qt.AlignmentFlag.AlignCenter if IS_PYQT6 else Qt.AlignCenter)

        # Left Panel: 11 Mods
        self.left_panel = PremiumFrostedGlassPanel(self)
        self.left_panel.setFixedSize(430, 770)

        left_vbox = QVBoxLayout(self.left_panel)
        left_vbox.setContentsMargins(16, 12, 16, 12)
        # v2.1.6 — tighter spacing: 3 category headers + 11 rows must fit
        left_vbox.setSpacing(3)

        self.lbl_mgr = QLabel("MODS MANAGER")
        self.lbl_mgr.setStyleSheet(f"font-size: 14.5px; font-weight: 900; color: {self.active_theme.primary.name()}; letter-spacing: 2px; margin-bottom: 3px; background: transparent; border: none;")
        left_vbox.addWidget(self.lbl_mgr)

        mods_data = [
            ("S.A.O.T", "Semi-Automated Offside Technology: 3D offside plane, camera views and distance tuning inside Replay mode (ReShade powered)."),
            ("Goal Line Technology", "Goal-Line Technology: Multi-angle camera verification with instant goal confirmation."),
            ("Referee View", "Body-cam perspective simulation from referee POV during crucial fouls and cards."),
            ("Match Momentum", "Live match dynamic momentum index based on ball possession and passing speed."),
            ("Heat Map", "High-precision density mapping for player position, runs, and ball coverage zones."),
            ("Shots Info", "Expected Goals (xG) metrics, shot vectors, ball velocity, and trajectory arc overlay."),
            ("3D Analysis", "Tactical top-down bird-eye view with live player spacing and defensive press vectors."),
            ("Penalty Data", "Goalkeeper dive prediction telemetry and shooter quadrant tendencies analysis."),
            ("Players Speed", "Kinematic radar displaying top sprint bursts, acceleration, and total meters run."),
            ("New Replay View", "Cinematic TV broadcast replays and free-orbit orbital highlight replay camera."),
            ("FOV Gaming", "Custom stadium camera angle, wide lens field-of-view, and pitch curvature tuning."),
        ]
        mods_desc = dict(mods_data)

        # v2.1.6 — CATEGORIZED mods manager (user spec #10): three
        # collapsible families, published mods first inside each one.
        self.mod_rows = []
        self.category_headers = {}
        self.cat_row_map = {}
        for cat_name, members in MOD_CATEGORIES:
            ordered = ordered_category_members(members)
            n_live = sum(1 for n in ordered if n in IMPLEMENTED_MOD_NAMES)
            expanded = bool(self.cat_expanded.get(cat_name, True))
            # the category of the saved selection always opens expanded so
            # the current mod is never hidden inside a collapsed block
            if self.current_mod_name in ordered:
                expanded = True
            hdr = CategoryHeader(self, cat_name, len(ordered), n_live,
                                 expanded=expanded)
            hdr.toggled.connect(self._on_category_toggled)
            left_vbox.addWidget(hdr)
            self.category_headers[cat_name] = hdr
            self.cat_row_map[cat_name] = rows_for_cat = []
            for name in ordered:
                is_sel = (name == self.current_mod_name)
                is_en = self.mods_state[name]["enabled"]
                row = CleanModRow(self, name, mods_desc[name], is_selected=is_sel,
                                  is_enabled=is_en,
                                  coming_soon=(name not in IMPLEMENTED_MOD_NAMES))
                row.selected_signal.connect(self.onModSelected)
                row.toggled_signal.connect(lambda state, n=name: self.onModRowToggled(n, state))
                row.setVisible(expanded)
                self.mod_rows.append(row)
                rows_for_cat.append(row)
                left_vbox.addWidget(row)
        self.cat_expanded = {c: self.category_headers[c].expanded
                             for c in self.category_headers}

        body_container.addWidget(self.left_panel)

        # Right Panel: Settings
        self.right_panel = PremiumFrostedGlassPanel(self)
        self.right_panel.setFixedSize(860, 770)

        right_vbox = QVBoxLayout(self.right_panel)
        right_vbox.setContentsMargins(28, 20, 28, 20)
        right_vbox.setSpacing(14)

        self.lbl_mod_title = QLabel(f"MOD SETTINGS: {self.current_mod_name.upper()}")
        self.lbl_mod_title.setStyleSheet("font-size: 20px; font-weight: 900; color: #ffffff; letter-spacing: 1px; background: transparent; border: none;")
        right_vbox.addWidget(self.lbl_mod_title)

        master_box = QHBoxLayout()
        self.lbl_enable = QLabel("ENABLE MOD")
        self.lbl_enable.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; background: transparent; border: none;")
        self.master_toggle = NeonToggle(master_window=self, checked=self.mods_state[self.current_mod_name]["enabled"])
        self.master_toggle.toggled.connect(self.onMasterToggleChanged)
        master_box.addWidget(self.lbl_enable)
        master_box.addWidget(self.master_toggle)
        master_box.addStretch()
        right_vbox.addLayout(master_box)

        # ------------------ Options Stack ------------------
        self.options_container = QWidget()
        options_vbox = QVBoxLayout(self.options_container)
        options_vbox.setContentsMargins(0, 0, 0, 0)
        options_vbox.setSpacing(14)

        inner_content = QHBoxLayout()
        inner_content.setSpacing(28)

        form_vbox = QVBoxLayout()
        form_vbox.setSpacing(13)

        self.lbl_op_title = self.makeLabel("Heat Map Opacity")
        form_vbox.addWidget(self.lbl_op_title)
        op_box = QHBoxLayout()
        self.slider_op = CleanCyberSlider(self)
        self.slider_op.setRange(0, 100)
        self.slider_op.setValue(80)
        self.lbl_op_val = QLabel("80%")
        self.lbl_op_val.setStyleSheet(f"color: {self.active_theme.primary.name()}; font-weight: bold; min-width: 44px; background: transparent;")
        op_box.addWidget(self.slider_op)
        op_box.addWidget(self.lbl_op_val)
        form_vbox.addLayout(op_box)

        self.lbl_int_title = self.makeLabel("Intensity Level")
        form_vbox.addWidget(self.lbl_int_title)
        int_box = QHBoxLayout()
        self.slider_int = CleanCyberSlider(self)
        self.slider_int.setRange(0, 100)
        self.slider_int.setValue(75)
        self.lbl_int_val = QLabel("75%")
        self.lbl_int_val.setStyleSheet(f"color: {self.active_theme.accent.name()}; font-weight: bold; min-width: 44px; background: transparent;")
        int_box.addWidget(self.slider_int)
        int_box.addWidget(self.lbl_int_val)
        form_vbox.addLayout(int_box)

        self.lbl_freq_title = self.makeLabel("Data Update Frequency")
        form_vbox.addWidget(self.lbl_freq_title)
        self.combo_freq = QComboBox()
        self.combo_freq.addItems(["Real-Time (FL 2026 Engine)", "Every 3 Seconds", "Every 10 Seconds", "Half-Time Only"])
        form_vbox.addWidget(self.combo_freq)

        self.lbl_mode_title = self.makeLabel("Render Mode")
        form_vbox.addWidget(self.lbl_mode_title)
        mode_box = QHBoxLayout()
        mode_box.setSpacing(8)
        self.mode_group = QButtonGroup(self)
        for i, m in enumerate(["Classic", "Thermal", "Contours"]):
            btn = QPushButton(m)
            btn.setCheckable(True)
            if m == "Thermal":
                btn.setChecked(True)
            btn.setObjectName("ModeSelectBtn")
            self.mode_group.addButton(btn, i)
            mode_box.addWidget(btn)
        form_vbox.addLayout(mode_box)

        form_vbox.addLayout(self.makeToggleRow("Display Player IDs", False))
        form_vbox.addLayout(self.makeToggleRow("Focus ball carrier only", True))
        form_vbox.addLayout(self.makeToggleRow("Historical Tracking", True))

        form_vbox.addStretch()
        inner_content.addLayout(form_vbox, 5)

        preview_vbox = QVBoxLayout()
        self.lbl_preview = QLabel("LIVE IN-GAME PREVIEW")
        self.lbl_preview.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; letter-spacing: 0.5px; background: transparent; border: none;")
        preview_vbox.addWidget(self.lbl_preview)

        self.pitch = TacticalPitchPreview(self)
        preview_vbox.addWidget(self.pitch, 1)

        self.slider_op.valueChanged.connect(lambda v: (
            self.lbl_op_val.setText(f"{v}%"),
            self.pitch.setOpacityVal(v)
        ))
        self.slider_int.valueChanged.connect(lambda v: (
            self.lbl_int_val.setText(f"{v}%"),
            self.pitch.setIntensityVal(v)
        ))

        inner_content.addLayout(preview_vbox, 5)
        options_vbox.addLayout(inner_content)

        self.ref_container = self.build_referee_page()
        self.glt_container = self.build_glt_page()
        self.mom_container = self.build_momentum_page()
        self.hm_container = self.build_heatmap_page()
        self.saot_container = self.build_saot_page()

        self.options_stack = QStackedWidget()
        self.options_stack.addWidget(self.options_container)
        self.options_stack.addWidget(self.ref_container)              # 1: Referee View
        self.options_stack.addWidget(self.glt_container)              # 2: Goal Line Technology
        self.options_stack.addWidget(self.mom_container)              # 3: Match Momentum
        self.options_stack.addWidget(self.hm_container)               # 4: Heat Map
        self.options_stack.addWidget(self.saot_container)             # 5: S.A.O.T
        self.options_stack.setCurrentIndex(self._options_index_for(self.current_mod_name))
        right_vbox.addWidget(self.options_stack, 1)

        self.btn_launch = GlassPillButton(self, "APPLY & RUN MOD BRIDGE",
                                          icon="play", height=54, font_px=12.5,
                                          animated=True, center_text=True)
        self.btn_launch.clicked.connect(self.on_apply_launch)

        right_vbox.addWidget(self.btn_launch)
        # v2.1.6 (user spec #2) — the big “SUPPORT THE MODS — DONATE”
        # button that used to sit here was REMOVED; the improved glass
        # DONATE pill in the header is the single sponsor button now.

        body_container.addWidget(self.right_panel)
        root_vbox.addLayout(body_container)

        # ------------------ Footer (v2.1.6 manufacturer plate) ----------
        # The manufacturer's text now lives in a proper frosted-glass box
        # whose colours follow the program theme (user spec #9).
        self.manufacturer_box = ManufacturerBox(self)
        root_vbox.addWidget(self.manufacturer_box)

        self.updateOptionsPanelState(self.mods_state[self.current_mod_name]["enabled"])
        self.update_conflict_warning()
        # activate/position the video + particle layers now that the layout
        # exists (they were created before it on purpose for stacking order)
        self._sync_overlay_geometry()

    def _options_index_for(self, mod_name):
        if mod_name == "Referee View":
            return 1
        if mod_name == GLT_MOD_NAME:
            return 2
        if mod_name == MOMENTUM_MOD_NAME:
            return 3
        if mod_name == HEATMAP_MOD_NAME:
            return 4
        if mod_name == SAOT_MOD_NAME:
            return 5
        return 0

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ==================================================================
    # v2.1.9 — SHARED OPTION-CARD KIT (user request #3 + #7)
    # Every mod menu is built from the same primitives, so ALL pages
    # share the exact S.A.O.T-page design language:
    #   _option_card()    -> (frame, vbox): one glass option card
    #   _card_title_row() -> (row, SectionHintIcon|None): the section
    #                        title + the circular "!" icon whose hover
    #                        TOOLTIP carries the section description
    #                        (descriptions are no longer printed on the
    #                        page — user request #7, applied to ALL mods).
    # v2.2.0 — the card glass + title colours are no longer baked in at
    # build time: both widgets carry stable objectNames and are restyled
    # from _option_card_qss()/_card_title_qss() on EVERY theme frame, so
    # the boxes on each mod page always match the CURRENT theme.
    # ==================================================================
    def _option_card_qss(self, t):
        return f"""
            QFrame#SaotOptionCard {{
                background: rgba({t.bg_dark[2].red()}, {t.bg_dark[2].green()},
                                 {t.bg_dark[2].blue()}, 0.55);
                border: 1px solid rgba({t.primary.red()}, {t.primary.green()},
                                       {t.primary.blue()}, 0.35);
                border-radius: 12px;
            }}
        """

    def _card_title_qss(self, t):
        return (f"font-size: 12.5px; font-weight: 900; color: {t.accent.name()}; "
                "letter-spacing: 1.6px; background: transparent; border: none;")

    def _option_card(self):
        f = QFrame()
        f.setObjectName("SaotOptionCard")
        f.setStyleSheet(self._option_card_qss(self.active_theme))
        fv = QVBoxLayout(f)
        fv.setContentsMargins(16, 12, 16, 12)
        fv.setSpacing(7)
        return f, fv

    def _card_title_row(self, text, hint=None):
        row = QHBoxLayout()
        row.setSpacing(8)
        lbl = QLabel(text)
        lbl.setObjectName("SaotCardTitle")
        lbl.setStyleSheet(self._card_title_qss(self.active_theme))
        row.addWidget(lbl)
        icon = None
        if hint:
            icon = SectionHintIcon(self, text, hint)
            row.addWidget(icon)
        row.addStretch()
        return row, icon

    def _refresh_option_cards_theme(self):
        """v2.2.0 — restyle every shared option card (and every card
        title) with the CURRENT theme. Called from
        _apply_current_theme_frame() on each theme-morph frame, so the
        boxes on all five mod pages always match the live theme."""
        t = self.active_theme
        card_qss = self._option_card_qss(t)
        title_qss = self._card_title_qss(t)
        for f in self.findChildren(QFrame):
            if f.objectName() in ("SaotOptionCard", "SaotReshadeCard"):
                f.setStyleSheet(card_qss)
        for l in self.findChildren(QLabel):
            if l.objectName() == "SaotCardTitle":
                l.setStyleSheet(title_qss)

    def build_referee_page(self):
        # v2.1.9 — rebuilt with the shared option-card kit: same glass
        # cards, same glass pills, same "!" hover icons as the S.A.O.T page.
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # --- (0, 0) SHOW VIDEO OVERLAY -----------------------------------
        card1, cv1 = self._option_card()
        row1, _ic1 = self._card_title_row(
            "SHOW VIDEO OVERLAY",
            "Plays the overlay on top of the game while the referee camera "
            "is active. Turn it off if you prefer the clean game picture.")
        self.ref_overlay_toggle = NeonToggle(master_window=self,
                                             checked=self.ref_cfg.get("overlay", True))
        self.ref_overlay_toggle.toggled.connect(self.on_ref_overlay_changed)
        row1.addWidget(self.ref_overlay_toggle)
        cv1.addLayout(row1)
        grid.addWidget(card1, 0, 0)

        # --- (0, 1) APPLY KEY ---------------------------------------------
        card2, cv2 = self._option_card()
        row2, _ic2 = self._card_title_row(
            "APPLY KEY",
            "The key that shows the referee view inside Replay mode. Click "
            "the box — it waits right there for the new key (no window "
            "opens). Stored as a hexadecimal virtual-key code, so it works "
            "on any keyboard layout (including Persian). Esc cancels.")
        self.btn_apply_key = KeyCaptureButton(self)
        self.btn_apply_key.keyCaptured.connect(self.on_ref_key_captured)
        self.btn_apply_key.captureMessage.connect(self.on_ref_key_message)
        self.btn_apply_key.captureStarted.connect(self.on_ref_key_capture_started)
        self.btn_apply_key.captureFinished.connect(self.on_ref_key_capture_ended)
        self.refresh_key_button_text()
        row2.addWidget(self.btn_apply_key)
        cv2.addLayout(row2)
        # dynamic capture status line — hidden until a capture is running
        self.lbl_key_hint = self.makeHintLabel("")
        self.lbl_key_hint.hide()
        cv2.addWidget(self.lbl_key_hint)
        grid.addWidget(card2, 0, 1)

        # --- (1, 0) HOW TO USE ---------------------------------------------
        card3, cv3 = self._option_card()
        row3, _ic3 = self._card_title_row(
            "HOW TO USE",
            "Enter Replay mode, press the apply key to get the referee's "
            "view, press the same key again to exit.")
        cv3.addLayout(row3)
        self.btn_usage = GlassPillButton(self, "VIEW INSTRUCTIONS",
                                         icon="book", height=44,
                                         font_px=11.5, min_width=268)
        self.btn_usage.clicked.connect(self.open_usage_modal)
        cv3.addWidget(self.btn_usage)
        grid.addWidget(card3, 1, 0)

        # --- (1, 1) YOUTUBE TUTORIAL ----------------------------------------
        card4, cv4 = self._option_card()
        row4, _ic4 = self._card_title_row(
            "YOUTUBE TUTORIAL",
            "Opens the official video tutorial of the Referee View mod on "
            "YouTube.")
        cv4.addLayout(row4)
        self.yt_btn = GlassPillButton(self, "WATCH TUTORIAL", icon="play",
                                      accent="#ff0033", height=44,
                                      font_px=11.5, min_width=245)
        self.yt_btn.clicked.connect(self.open_tutorial)
        cv4.addWidget(self.yt_btn)
        grid.addWidget(card4, 1, 1)

        v.addLayout(grid)

        # --- IN-GAME PREVIEW -------------------------------------------------
        prev_card, pv = self._option_card()
        rowp, _icp = self._card_title_row("IN-GAME PREVIEW — REFEREE POV")
        pv.addLayout(rowp)
        self.ref_preview = RefereePreviewBox(self)
        self.ref_preview.set_overlay_on(bool(self.ref_cfg.get("overlay", True)),
                                        animate=False)
        pv.addWidget(self.ref_preview, 0,
                     Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignHCenter)
        v.addWidget(prev_card)
        return page

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def build_glt_page(self):
        # v2.1.9 — rebuilt with the shared option-card kit (SAOT design).
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(10)

        # --- (0, 0) PLAY ANIMATION KEY ------------------------------------
        card1, cv1 = self._option_card()
        row1, _ic1 = self._card_title_row(
            "PLAY ANIMATION KEY",
            "Replays the recorded goal scene with the GLT camera animation. "
            "Click the box and press the new key — no window opens. "
            "Esc cancels.")
        cv1.addLayout(row1)
        self.btn_glt_play = KeyCaptureButton(self)
        self.btn_glt_play.keyCaptured.connect(lambda vk, name: self.on_glt_key_captured("play", vk, name))
        self.btn_glt_play.captureMessage.connect(lambda msg: self.on_glt_key_message("play", msg))
        self.btn_glt_play.captureStarted.connect(lambda: self.on_glt_key_capture_started("play"))
        self.btn_glt_play.captureFinished.connect(lambda: self.on_glt_key_capture_ended("play"))
        # v2.1.9 — the button lives on its OWN row (centred) so the section
        # title can never truncate against it
        btnrow1 = QHBoxLayout()
        btnrow1.addStretch()
        btnrow1.addWidget(self.btn_glt_play)
        btnrow1.addStretch()
        cv1.addLayout(btnrow1)
        self.lbl_glt_play_hint = self.makeHintLabel("")
        self.lbl_glt_play_hint.hide()
        cv1.addWidget(self.lbl_glt_play_hint)
        grid.addWidget(card1, 0, 0)

        # --- (0, 1) MANUAL RECORD KEY --------------------------------------
        card2, cv2 = self._option_card()
        row2, _ic2 = self._card_title_row(
            "MANUAL RECORD KEY",
            "Starts manual recording of the replay while you are inside "
            "Replay Mode. Click the box and press the new key — no window "
            "opens. Esc cancels.")
        cv2.addLayout(row2)
        self.btn_glt_rec = KeyCaptureButton(self)
        self.btn_glt_rec.keyCaptured.connect(lambda vk, name: self.on_glt_key_captured("rec", vk, name))
        self.btn_glt_rec.captureMessage.connect(lambda msg: self.on_glt_key_message("rec", msg))
        self.btn_glt_rec.captureStarted.connect(lambda: self.on_glt_key_capture_started("rec"))
        self.btn_glt_rec.captureFinished.connect(lambda: self.on_glt_key_capture_ended("rec"))
        btnrow2 = QHBoxLayout()
        btnrow2.addStretch()
        btnrow2.addWidget(self.btn_glt_rec)
        btnrow2.addStretch()
        cv2.addLayout(btnrow2)
        self.lbl_glt_rec_hint = self.makeHintLabel("")
        self.lbl_glt_rec_hint.hide()
        cv2.addWidget(self.lbl_glt_rec_hint)
        grid.addWidget(card2, 0, 1)

        # --- (1, 0) ANIMATION STYLE ------------------------------------------
        card3, cv3 = self._option_card()
        row3, _ic3 = self._card_title_row(
            "ANIMATION STYLE",
            "Style 1 = real generated turf with light/dark mowing stripes.  "
            "Style 2 = classic T6 stadium turf texture. The MOD PREVIEW box "
            "below swaps automatically when you change the style.")
        cv3.addLayout(row3)
        self.glt_style_group = QButtonGroup(self)
        # compact text chips on their OWN row — the per-style preview images
        # are shown in the MOD PREVIEW box below and swap automatically on
        # style change
        self.btn_glt_style1 = GLTStyleButton(self, "T5", "STYLE 1")
        self.btn_glt_style2 = GLTStyleButton(self, "T6", "STYLE 2")
        for i, b in enumerate((self.btn_glt_style1, self.btn_glt_style2)):
            self.glt_style_group.addButton(b, i)
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        chips_row.addWidget(self.btn_glt_style1)
        chips_row.addWidget(self.btn_glt_style2)
        chips_row.addStretch()
        cv3.addLayout(chips_row)
        self.glt_style_group.idClicked.connect(self.on_glt_style_changed)
        self._sync_glt_style_buttons()
        grid.addWidget(card3, 1, 0)

        # --- (1, 1) HOW TO USE ------------------------------------------------
        card4, cv4 = self._option_card()
        row4, _ic4 = self._card_title_row(
            "HOW TO USE",
            "The complete Goal Line Technology guide: how the mod verifies "
            "goals, when the animation plays and how to record replays.")
        cv4.addLayout(row4)
        self.btn_glt_usage = GlassPillButton(self, "VIEW INSTRUCTIONS",
                                             icon="book", height=44,
                                             font_px=11.5, min_width=268)
        self.btn_glt_usage.clicked.connect(self.open_glt_usage_modal)
        cv4.addWidget(self.btn_glt_usage)
        grid.addWidget(card4, 1, 1)

        # --- (2, 0) YOUTUBE TUTORIAL --------------------------------------------
        # WATCH TUTORIAL is always visible; while GLT_TUTORIAL_URL is still
        # empty, clicking it shows a "TUTORIAL COMING SOON" note.
        card5, cv5 = self._option_card()
        row5, _ic5 = self._card_title_row(
            "YOUTUBE TUTORIAL",
            "Opens the official video tutorial of the Goal Line Technology "
            "mod on YouTube.")
        cv5.addLayout(row5)
        self.glt_yt_btn = GlassPillButton(self, "WATCH TUTORIAL", icon="play",
                                          accent="#ff0033", height=44,
                                          font_px=11.5, min_width=245)
        self.glt_yt_btn.clicked.connect(self.open_glt_tutorial)
        cv5.addWidget(self.glt_yt_btn)
        grid.addWidget(card5, 2, 0)

        # --- (2, 1) GAMEPAD BUTTONS ------------------------------------------
        # Hovering the small icon lists every assigned button -> key (read
        # live from the game settings.dat); clicking it opens the
        # comprehensive ALL CONTROLS modal.
        card6, cv6 = self._option_card()
        row6, _ic6 = self._card_title_row(
            "GAMEPAD BUTTONS",
            "Hover the controller icon to list every assigned gamepad "
            "button, click it to open the full ALL CONTROLS list.")
        self.btn_glt_pad_icon = GamepadBindingsIcon(self)
        self.btn_glt_pad_icon.clicked.connect(self.open_all_controls_modal)
        row6.addWidget(self.btn_glt_pad_icon)
        cv6.addLayout(row6)
        grid.addWidget(card6, 2, 1)

        v.addLayout(grid)

        # --- MOD PREVIEW --------------------------------------------------------
        prev_card, pv = self._option_card()
        rowp, _icp = self._card_title_row(
            "MOD PREVIEW — GOAL LINE TECHNOLOGY",
            "Shows the turf of the CURRENTLY selected animation style; it "
            "swaps automatically whenever the style changes.")
        pv.addLayout(rowp)
        # 16:9 preview slot showing the CURRENT style's image; swaps
        # automatically whenever the animation style changes.
        self.glt_preview = GLTPreviewBox(self, style_key=str(self.glt_cfg.get("style", "T6")))
        pv.addWidget(self.glt_preview, 0,
                     Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignHCenter)
        v.addWidget(prev_card)

        self.refresh_glt_key_buttons()
        return page

    # ------------------------------------------------------------------
    # MATCH MOMENTUM page — settings, notice, instructions, YouTube and
    # preview, all consistent with the Referee View / GLT pages.
    # ------------------------------------------------------------------
    def build_momentum_page(self):
        # v2.1.9 — rebuilt with the shared option-card kit (SAOT design).
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # --- (0, 0) IMPORTANT NOTICE ----------------------------------------
        card1, cv1 = self._option_card()
        row1, _ic1 = self._card_title_row(
            "IMPORTANT NOTICE",
            "Read this before enabling the mod — it only works when it is "
            "active from the game's start screen.")
        cv1.addLayout(row1)
        cv1.addWidget(MomentumNoticeBanner(
            "For proper functionality, this mod must be active on the game's "
            "start screen."))
        grid.addWidget(card1, 0, 0)

        # --- (0, 1) AUTO CHART DISPLAY ----------------------------------------
        card2, cv2 = self._option_card()
        row2, _ic2 = self._card_title_row(
            "AUTO CHART DISPLAY",
            "Choose WHEN the momentum chart is shown automatically and for "
            "how long — open DISPLAY SETTINGS to pick the minutes of each "
            "half / extra time and the on-screen seconds.")
        self.btn_mom_settings = GlassPillButton(self, "DISPLAY SETTINGS",
                                                icon="sliders", height=44,
                                                font_px=11.5, min_width=245)
        self.btn_mom_settings.clicked.connect(self.open_momentum_settings)
        cv2.addLayout(row2)
        cv2.addWidget(self.btn_mom_settings)
        self.lbl_mom_summary = self.makeHintLabel("")
        cv2.addWidget(self.lbl_mom_summary)
        grid.addWidget(card2, 0, 1)

        # --- (1, 0) HOW TO USE ------------------------------------------------
        card3, cv3 = self._option_card()
        row3, _ic3 = self._card_title_row(
            "HOW TO USE",
            "Activate the mod from the 'Select Team' screen and then play "
            "the game. At the designated times, the code will display the "
            "momentum match chart.")
        cv3.addLayout(row3)
        self.btn_mom_usage = GlassPillButton(self, "VIEW INSTRUCTIONS",
                                             icon="book", height=44,
                                             font_px=11.5, min_width=268)
        self.btn_mom_usage.clicked.connect(self.open_momentum_usage_modal)
        cv3.addWidget(self.btn_mom_usage)
        grid.addWidget(card3, 1, 0)

        # --- (1, 1) YOUTUBE TUTORIAL -------------------------------------------
        card4, cv4 = self._option_card()
        row4, _ic4 = self._card_title_row(
            "YOUTUBE TUTORIAL",
            "Opens the official video tutorial of the Match Momentum mod "
            "on YouTube.")
        cv4.addLayout(row4)
        self.mom_yt_btn = GlassPillButton(self, "WATCH TUTORIAL", icon="play",
                                          accent="#ff0033", height=44,
                                          font_px=11.5, min_width=245)
        self.mom_yt_btn.clicked.connect(self.open_momentum_tutorial)
        cv4.addWidget(self.mom_yt_btn)
        grid.addWidget(card4, 1, 1)

        v.addLayout(grid)

        # --- MOD PREVIEW ---------------------------------------------------------
        prev_card, pv = self._option_card()
        rowp, _icp = self._card_title_row(
            "MOD PREVIEW — MATCH MOMENTUM",
            "A live example of the momentum chart the mod draws over the "
            "game at the moments you selected above.")
        pv.addLayout(rowp)
        self.mom_preview = MomentumPreviewBox(self)
        pv.addWidget(self.mom_preview, 0,
                     Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignHCenter)
        v.addWidget(prev_card)

        self.refresh_momentum_summary()
        return page

    def build_heatmap_page(self):
        """Heat Map settings page — v2.1.9: rebuilt with the shared
        option-card kit so the page matches the S.A.O.T design exactly,
        and every static description moved onto the circular "!" hover
        icons. Display minute (71-79), viewer side, the mod's own
        calibration sliders with a RESTORE-DEFAULT-MODE button and a LIVE
        example image that re-renders with every change."""
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)

        # --- (0, 0) IMPORTANT NOTICE ----------------------------------------
        card1, cv1 = self._option_card()
        row1, _ic1 = self._card_title_row(
            "IMPORTANT NOTICE",
            "Read this before enabling the mod — the mod must be active "
            "before the match starts, because heat data is recorded live "
            "at 30 Hz from the opening whistle.")
        cv1.addLayout(row1)
        cv1.addWidget(MomentumNoticeBanner(
            "For proper functionality this mod must be active before the "
            "match starts."))
        grid.addWidget(card1, 0, 0)

        # --- (0, 1) AUTO HEAT MAP DISPLAY (71-79) -----------------------------
        card2, cv2 = self._option_card()
        row2, _ic2 = self._card_title_row(
            "AUTO HEAT MAP DISPLAY",
            "Match minute when the heat map is shown automatically — "
            "currently 75'. You can choose any value between 71 and 79.")
        self.hm_minute_selector = MomentumMinuteSelector(
            self, self.hm_cfg["hm_display_minute"],
            HEATMAP_DISPLAY_RANGE[0], HEATMAP_DISPLAY_RANGE[1])
        self.hm_minute_selector.valueChanged.connect(self.on_hm_display_minute)
        row2.addWidget(self.hm_minute_selector)
        cv2.addLayout(row2)
        grid.addWidget(card2, 0, 1)

        # --- (1, 0) SHOW HEAT MAP FOR ------------------------------------------
        card3, cv3 = self._option_card()
        row3, _ic3 = self._card_title_row(
            "SHOW HEAT MAP FOR",
            "Which team's players can be picked for the automatic heat map "
            "— the HOME side, the AWAY side, or a RANDOM player (default). "
            "The lit pill with the glowing dot is the ACTIVE choice.")
        row_side2 = QHBoxLayout()
        row_side2.setSpacing(8)
        cv3.addLayout(row3)               # title + "!" icon (v2.1.9 fix)
        self.hm_btn_random = GlassPillButton(self, "RANDOM", icon="dot",
                                             height=36, font_px=10.5,
                                             checkable=True, compact=True)
        self.hm_btn_home = GlassPillButton(self, "HOME", icon="dot",
                                           height=36, font_px=10.5,
                                           checkable=True, compact=True)
        self.hm_btn_away = GlassPillButton(self, "AWAY", icon="dot",
                                           height=36, font_px=10.5,
                                           checkable=True, compact=True)
        self.hm_side_group = QButtonGroup(self)
        self.hm_side_group.setExclusive(True)
        for btn, sid in ((self.hm_btn_random, 0), (self.hm_btn_home, 1),
                         (self.hm_btn_away, 2)):
            self.hm_side_group.addButton(btn)
            btn.clicked.connect(lambda _checked=False, i=sid: self.on_hm_viewer_side(i))
        for b in (self.hm_btn_random, self.hm_btn_home, self.hm_btn_away):
            row_side2.addWidget(b, 1)          # equal flex — labels never clip
        cv3.addLayout(row_side2)
        grid.addWidget(card3, 1, 0)

        # --- (1, 1) YOUTUBE TUTORIAL ---------------------------------------------
        card4, cv4 = self._option_card()
        row4, _ic4 = self._card_title_row(
            "YOUTUBE TUTORIAL",
            "Opens the official video tutorial of the Heat Map mod on "
            "YouTube.")
        cv4.addLayout(row4)
        self.hm_yt_btn = GlassPillButton(self, "WATCH TUTORIAL", icon="play",
                                         accent="#ff0033", height=44,
                                         font_px=11.5, min_width=245)
        self.hm_yt_btn.clicked.connect(self.open_heatmap_tutorial)
        cv4.addWidget(self.hm_yt_btn)
        grid.addWidget(card4, 1, 1)

        v.addLayout(grid)

        # --- bottom two-column block: calibration | preview + summary --------
        bottom_h = QHBoxLayout()
        bottom_h.setSpacing(16)

        # LEFT — CALIBRATION & FILTERS (+ restore defaults)
        cal_card, calv = self._option_card()
        cal_head, _icc = self._card_title_row(
            "CALIBRATION & FILTERS",
            "Fine-tune the heat rendering: sensitivity, heat ceiling, "
            "gamma, initial softness, edge feather and the minimum filter. "
            "Every change re-renders the preview instantly.")
        calv.addLayout(cal_head)

        cal_grid = QGridLayout()
        cal_grid.setHorizontalSpacing(18)
        cal_grid.setVerticalSpacing(8)
        self.hm_sliders = {}
        self.hm_captions = {}
        specs = (
            ("hm_gain", "SENSITIVITY", 20, 800, 100, lambda val: f"{val / 100:.2f}"),
            ("hm_ceiling", "HEAT CEILING (S)", 1, 80, 10, lambda val: f"{val / 10:.1f}s"),
            ("hm_gamma", "GAMMA", 20, 150, 100, lambda val: f"{val / 100:.2f}"),
            ("hm_blur_m", "INITIAL SOFTNESS (M)", 5, 30, 10, lambda val: f"{val / 10:.1f}m"),
            ("hm_feather", "EDGE FEATHER (PX)", 0, 25, 1, lambda val: f"{val:d}px"),
            ("hm_cutoff", "MINIMUM FILTER", 0, 35, 100, lambda val: f"{val / 100:.2f}"),
        )
        hand = Qt.CursorShape.PointingHandCursor if IS_PYQT6 else Qt.PointingHandCursor
        for i, (key, title, lo, hi, div, fmt) in enumerate(specs):
            cell = QVBoxLayout()
            cell.setSpacing(3)
            cur = fmt(int(round(self.hm_cfg[key] * div)))
            cap = QLabel(f"{title}: {cur}")
            cap.setStyleSheet("font-size: 11px; font-weight: 800; color: #cbd5e1; "
                              "background: transparent; border: none;")
            cap.setMinimumHeight(16)
            slider = QSlider(Qt.Orientation.Horizontal if IS_PYQT6 else Qt.Horizontal)
            slider.setRange(lo, hi)
            slider.setValue(int(round(self.hm_cfg[key] * div)))
            slider.setCursor(hand)
            slider.valueChanged.connect(
                lambda val, k=key, d=div, c=cap, f=fmt: self.on_hm_slider(k, val, d, c, f))
            cell.addWidget(cap)
            cell.addWidget(slider)
            self.hm_sliders[key] = (slider, div, fmt)
            self.hm_captions[key] = (cap, title, div, fmt)
            cal_grid.addLayout(cell, i // 2, i % 2)     # 2 columns x 3 rows
        calv.addLayout(cal_grid)

        # RESTORE DEFAULT MODE — own full-width row so the label can never
        # clip against the section title
        restore_row = QHBoxLayout()
        self.btn_hm_restore = GlassPillButton(
            self, "RESTORE DEFAULT MODE", icon="restore", height=36,
            font_px=10.5, min_width=246, compact=True)
        self.btn_hm_restore.setToolTip(
            "Resets the auto-display minute, the viewer side and all six "
            "calibration filters back to the mod's shipped defaults.")
        self.btn_hm_restore.clicked.connect(self.on_hm_restore_defaults)
        restore_row.addWidget(self.btn_hm_restore)
        restore_row.addStretch()
        calv.addLayout(restore_row)
        bottom_h.addWidget(cal_card, 5)

        # RIGHT — preview + one-line summary (word-wrapped, never cut)
        prev_card, pv = self._option_card()
        prev_head, _icp = self._card_title_row(
            "MOD PREVIEW — HEAT MAP",
            "A live example image rendered through the SAME colour "
            "pipeline as the mod itself — it re-renders with every "
            "change you make.")
        pv.addLayout(prev_head)
        self.hm_preview = HeatMapPreviewBox(self)
        pv.addWidget(self.hm_preview, 0,
                     Qt.AlignmentFlag.AlignHCenter if IS_PYQT6 else Qt.AlignHCenter)
        self.lbl_hm_summary = self.makeHintLabel("")
        self.lbl_hm_summary.setMinimumHeight(30)
        pv.addWidget(self.lbl_hm_summary)
        bottom_h.addWidget(prev_card, 5)

        v.addLayout(bottom_h)

        self._sync_hm_side_buttons()
        self.refresh_heatmap_summary()
        self.refresh_heatmap_preview()
        return page

    # ---------------- Heat Map page callbacks ----------------------------
    def on_hm_display_minute(self, val):
        self.hm_cfg["hm_display_minute"] = heatmap_clamp_display_minute(val)
        self.save_config()
        self.refresh_heatmap_summary()

    def on_hm_viewer_side(self, btn_id):
        side = ("random", "home", "away")[int(btn_id)]
        self.hm_cfg["hm_viewer_side"] = side
        self._sync_hm_side_buttons()
        self.save_config()
        self.refresh_heatmap_summary()

    def _sync_hm_side_buttons(self):
        side = str(self.hm_cfg.get("hm_viewer_side", "random"))
        self.hm_btn_random.setChecked(side == "random")
        self.hm_btn_home.setChecked(side == "home")
        self.hm_btn_away.setChecked(side == "away")

    def on_hm_slider(self, key, val, div, cap, fmt):
        self.hm_cfg[key] = heatmap_clamp_float(val / div, 0.0001, 1e9, val / div)
        cap.setText(f"{cap.text().split(':')[0]}: {fmt(val)}")
        if getattr(self, "_hm_restoring", False):
            return                      # programmatic restore — saved once at the end
        self.save_config()
        self.refresh_heatmap_summary()
        self.refresh_heatmap_preview()

    def on_hm_restore_defaults(self):
        """v2.1.6 (user spec #5) — RESTORE DEFAULT MODE: resets the whole
        Heat Map page (auto-display minute 75, viewer side RANDOM and all
        six calibration filters) back to the shipped defaults, updates
        every control on screen and persists the change."""
        d = DEFAULT_HEATMAP_SETTINGS
        self._hm_restoring = True
        try:
            self.hm_cfg["hm_display_minute"] = heatmap_clamp_display_minute(
                d["hm_display_minute"])
            self.hm_minute_selector.setValue(self.hm_cfg["hm_display_minute"])
            self.hm_cfg["hm_viewer_side"] = "random"
            for key, (slider, div, fmt) in self.hm_sliders.items():
                self.hm_cfg[key] = heatmap_clamp_float(
                    d[key], 0.0001, 1e9, d[key])
                slider.setValue(int(round(self.hm_cfg[key] * div)))
            self._sync_hm_side_buttons()
        finally:
            self._hm_restoring = False
        # captions may not fire valueChanged when a slider was already at
        # the default value — refresh them explicitly
        for key, (cap, title, div, fmt) in self.hm_captions.items():
            cap.setText(f"{title}: {fmt(int(round(self.hm_cfg[key] * div)))}")
        self.save_config()
        self.refresh_heatmap_summary()
        self.refresh_heatmap_preview()

    def refresh_heatmap_summary(self):
        c = self.hm_cfg
        side_txt = {"random": "RANDOM PLAYER", "home": "HOME SIDE ONLY",
                    "away": "AWAY SIDE ONLY"}[str(c.get("hm_viewer_side"))]
        self.lbl_hm_summary.setText(
            f"Auto display at minute {c.get('hm_display_minute')}  \u2022  shown for: {side_txt}  \u2022  "
            f"gain {float(c.get('hm_gain')):.2f}  \u2022  ceiling {float(c.get('hm_ceiling')):.1f}s  \u2022  "
            f"gamma {float(c.get('hm_gamma')):.2f}  \u2022  blur {float(c.get('hm_blur_m')):.1f}m  \u2022  "
            f"feather {float(c.get('hm_feather')):.0f}px  \u2022  cutoff {float(c.get('hm_cutoff')):.2f}")

    def refresh_heatmap_preview(self):
        try:
            self.hm_preview.render(dict(self.hm_cfg))
        except Exception:
            pass

    def open_heatmap_tutorial(self):
        # v1.0.0 — the "HeatMap Tut" line of the developer Gist, fetched at
        # click time; HEATMAP_TUTORIAL_URL is only an offline fallback.
        self.open_mod_tutorial("HEATMAP", str(HEATMAP_TUTORIAL_URL).strip())

    # ==================================================================
    # [suite v2.1.7 / v2.1.8] S.A.O.T — the mod's dedicated menu. The ONLY
    # option is the CALL KEY (user spec #3); the usual tutorial-video,
    # preview and instructions sections are here as for every other mod,
    # plus the dedicated RESHADE SETUP section (user spec #6) that checks
    # the ReShade software in the main game folder and copies the 2026
    # files from SAOTMod\textut.
    # v2.1.8 — every option now lives in its own titled glass card with a
    # large liquid-glass button: nothing is tucked away in a corner any
    # more (user feedback: some options were placed too hidden).
    # ==================================================================
    def build_saot_page(self):
        # v2.1.9 — the REFERENCE design, now built from the same shared
        # option-card kit as every other mod page, with the circular "!"
        # hover icons carrying the descriptions (user request #7).
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(4, 4, 4, 4)
        v.setSpacing(10)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # --- (0, 0) CALL KEY — the menu's ONLY option (user spec #3) ------
        key_card, kv = self._option_card()
        self.btn_saot_call_key = KeyCaptureButton(self)
        self.btn_saot_call_key.keyCaptured.connect(self.on_saot_key_captured)
        self.btn_saot_call_key.captureMessage.connect(self.on_saot_key_message)
        self.btn_saot_call_key.captureStarted.connect(self.on_saot_key_capture_started)
        self.btn_saot_call_key.captureFinished.connect(self.on_saot_key_capture_ended)
        self.refresh_saot_key_button_text()
        head_k, _ic_k = self._card_title_row(
            "CALL KEY",
            "The key that SHOWS/HIDES the S.A.O.T tool window inside the "
            "game (default F1). Click the box — it waits right there for "
            "the new key (no window opens). Esc cancels.")
        head_k.addWidget(self.btn_saot_call_key)
        kv.addLayout(head_k)
        # dynamic capture status line — hidden until a capture is running
        self.lbl_saot_key_hint = self.makeHintLabel("")
        self.lbl_saot_key_hint.hide()
        kv.addWidget(self.lbl_saot_key_hint)
        grid.addWidget(key_card, 0, 0)

        # --- (0, 1) YOUTUBE TUTORIAL ---------------------------------------
        yt_card, yv = self._option_card()
        head_y, _ic_y = self._card_title_row(
            "YOUTUBE TUTORIAL",
            "Opens the official video tutorial of the S.A.O.T mod on YouTube.")
        yv.addLayout(head_y)
        self.saot_yt_btn = GlassPillButton(self, "WATCH TUTORIAL",
                                           icon="play", accent="#ff0033",
                                           height=44, font_px=11.5,
                                           min_width=245)
        self.saot_yt_btn.clicked.connect(self.open_saot_tutorial)
        yv.addWidget(self.saot_yt_btn)
        grid.addWidget(yt_card, 0, 1)

        # --- (1, 0) HOW TO USE (all teaching content of the original) ------
        use_card, uv = self._option_card()
        head_u, _ic_u = self._card_title_row(
            "HOW TO USE",
            "The complete Installation + Usage guide in two tabs (18 "
            "illustrated steps): ReShade setup, windowed mode, replay "
            "workflow, plane ON/OFF and distance tuning.")
        uv.addLayout(head_u)
        self.btn_saot_usage = GlassPillButton(self, "VIEW INSTRUCTIONS",
                                              icon="book", height=44,
                                              font_px=11.5, min_width=268)
        self.btn_saot_usage.clicked.connect(self.open_saot_usage_modal)
        uv.addWidget(self.btn_saot_usage)
        grid.addWidget(use_card, 1, 0)

        # --- (1, 1) MOD PREVIEW --------------------------------------------
        prev_card, pv = self._option_card()
        head_p, _ic_p = self._card_title_row(
            "MOD PREVIEW — OFFSIDE PLANE IN REPLAY",
            "The 3D offside plane exactly as it appears over the replay "
            "camera inside the game.")
        pv.addLayout(head_p)
        self.saot_preview = SAOTPreviewBox(self)
        row_prev = QHBoxLayout()
        row_prev.addStretch()
        row_prev.addWidget(self.saot_preview)
        row_prev.addStretch()
        pv.addLayout(row_prev)
        grid.addWidget(prev_card, 1, 1)

        v.addLayout(grid)

        # --- RESHADE SETUP (dedicated section, user spec #6) ----------------
        reshade_frame = QFrame()
        reshade_frame.setObjectName("SaotReshadeCard")
        # v2.2.0 — same themed glass as the option cards, refreshed live
        # by _refresh_option_cards_theme() on every theme frame.
        reshade_frame.setStyleSheet(self._option_card_qss(self.active_theme))
        rv = QVBoxLayout(reshade_frame)
        rv.setContentsMargins(18, 12, 18, 14)
        rv.setSpacing(7)

        head_r, _ic_r = self._card_title_row(
            "RESHADE SETUP — MAIN GAME FOLDER",
            "ReShade must be installed inside the main game folder with "
            "the 2026 offside files. If it is missing, use DOWNLOAD "
            "RESHADE (reshade.me). If the installed files are not the "
            "2026 version, use COPY 2026 FILES — MyMods copies "
            "OffsidePlane.fx + Offside_Tex.png from SAOTMod\\textut into "
            "the game folder and removes any old 2017 shader.")
        btn_refresh = GlassPillButton(self, "REFRESH", icon="restore",
                                      height=38, font_px=10.5, min_width=130)
        btn_refresh.clicked.connect(self.refresh_saot_reshade)
        head_r.addWidget(btn_refresh)
        rv.addLayout(head_r)

        self.lbl_saot_reshade_rows = self.makeHintLabel("")
        self.lbl_saot_reshade_rows.setTextFormat(
            Qt.TextFormat.RichText if IS_PYQT6 else Qt.RichText)
        self.lbl_saot_reshade_rows.setMinimumHeight(74)
        rv.addWidget(self.lbl_saot_reshade_rows)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        self.btn_reshade_download = GlassPillButton(
            self, "DOWNLOAD RESHADE", icon="download", accent="#00d4ff",
            height=44, font_px=11.5, min_width=295)
        self.btn_reshade_download.clicked.connect(self.on_saot_download_reshade)
        self.btn_reshade_copy = GlassPillButton(
            self, "COPY 2026 FILES", icon="copy", height=44, font_px=11.5,
            min_width=245)
        self.btn_reshade_copy.clicked.connect(self.on_saot_copy_reshade)
        btn_row.addWidget(self.btn_reshade_download)
        btn_row.addWidget(self.btn_reshade_copy)
        btn_row.addStretch()
        rv.addLayout(btn_row)

        # dynamic result line for the copy action — hidden until used
        self.lbl_saot_reshade_msg = self.makeHintLabel("")
        self.lbl_saot_reshade_msg.hide()
        rv.addWidget(self.lbl_saot_reshade_msg)
        v.addWidget(reshade_frame)

        self.refresh_saot_reshade()
        return page

    # ---------------- S.A.O.T page callbacks ------------------------------
    def refresh_saot_key_button_text(self):
        name = str(self.mod_keys.get(SAOT_MOD_NAME, {}).get("name", "") or "")
        self.btn_saot_call_key.setText(name if name else "NOT SET")

    def on_saot_key_capture_started(self):
        self.lbl_saot_key_hint.setText("Waiting for the new key… press it now. Esc cancels.")
        self.lbl_saot_key_hint.setStyleSheet("font-size: 11px; color: #ff9900; font-weight: 700; line-height: 1.45; background: transparent; border: none;")
        self.lbl_saot_key_hint.show()

    def on_saot_key_capture_ended(self):
        # v2.1.9 — the static description lives on the "!" icon now; the
        # status line simply hides when the capture ends.
        self.lbl_saot_key_hint.hide()

    def on_saot_key_message(self, msg):
        self.lbl_saot_key_hint.setText(msg)
        self.lbl_saot_key_hint.show()

    def on_saot_key_captured(self, vk, name):
        conflict = self.find_key_conflict(vk, SAOT_MOD_NAME, "apply")
        if conflict:
            dlg = self.show_modal(KeyConflictModal, name, SAOT_MOD_NAME, conflict["label"])
            if not (dlg and dlg.result() == BaseModalDialog.RESULT_ACCEPTED):
                return
            conflict["clear"]()
        self.mod_keys[SAOT_MOD_NAME] = {"vk": f"0x{int(vk):02X}",
                                        "name": str(name)}
        self.saot_cfg["call_vk"] = self.mod_keys[SAOT_MOD_NAME]["vk"]
        self.saot_cfg["call_name"] = str(name)
        self.refresh_saot_key_button_text()
        self.save_config()

    def _clear_saot_key(self):
        self.mod_keys[SAOT_MOD_NAME] = {
            "vk": DEFAULT_SAOT_SETTINGS["call_vk"],
            "name": DEFAULT_SAOT_SETTINGS["call_name"],
        }
        self.saot_cfg["call_vk"] = self.mod_keys[SAOT_MOD_NAME]["vk"]
        self.saot_cfg["call_name"] = self.mod_keys[SAOT_MOD_NAME]["name"]
        self.refresh_saot_key_button_text()

    def open_saot_usage_modal(self):
        self.show_modal(SAOTUsageModal)

    def open_saot_tutorial(self):
        # v1.0.0 — the "SAOT Tut" line of the developer Gist, fetched at
        # click time; SAOT_TUTORIAL_URL is only an offline fallback.
        self.open_mod_tutorial("SAOT", str(SAOT_TUTORIAL_URL).strip())

    def refresh_saot_reshade(self):
        """Re-check ReShade + 2026 files in the main game folder and
        redraw the status rows (user spec #6: display BEAUTIFULLY and
        clearly whether ReShade and its files exist)."""
        st = saot_reshade_status(self.custom_game_dir)
        ok = "#00ff88"
        bad = "#ff4770"
        warn = "#ffd27a"

        def mark(flag, warn_flag=False):
            if flag:
                return f"<span style='color:{ok};'>&#10004;</span>"
            if warn_flag:
                return f"<span style='color:{warn};'>~</span>"
            return f"<span style='color:{bad};'>&#10008;</span>"

        if not st["game_dir_ok"]:
            rows = (f"{mark(False)} &nbsp;<b style='color:{bad};'>Main game "
                    "folder is not set</b> — choose it in SETTINGS first.")
            self.lbl_saot_reshade_rows.setText(rows)
            self.btn_reshade_download.setEnabled(True)
            self.btn_reshade_copy.setEnabled(False)
            return
        ver_txt = f"<span style='color:{ok};'>2026</span>"
        if st["fx_2017"] and not st["fx_2026"]:
            ver_txt = f"<span style='color:{bad};'>2017 (not 2026)</span>"
        elif st["fx_2017"] and st["fx_2026"]:
            ver_txt = f"<span style='color:{warn};'>2026 + old 2017 file present</span>"
        elif not st["fx_2026"]:
            ver_txt = f"<span style='color:{bad};'>unknown (2026 shader missing)</span>"
        rows = (
            f"{mark(st['reshade_ok'])} &nbsp;<b>ReShade software</b> — "
            f"{'installed (' + st['reshade_marker'] + ')' if st['reshade_ok'] else 'NOT installed in the game folder'}"
            "<br>"
            f"{mark(st['version_2026'], st['fx_2017'])} &nbsp;<b>Offside files version</b> — {ver_txt}"
            "<br>"
            f"{mark(st['tex'])} &nbsp;<b>Offside texture</b> (Offside_Tex.png) — "
            f"{'present' if st['tex'] else 'missing'}"
            "<br>"
            f"{mark(st['source_ok'])} &nbsp;<b>Copy source</b> — SAOTMod\\textut "
            f"{'found (OffsidePlane.fx + Offside_Tex.png)' if st['source_ok'] else 'MISSING the files to copy'}"
        )
        self.lbl_saot_reshade_rows.setText(rows)
        self.btn_reshade_copy.setEnabled(st["reshade_ok"] and not st["files_ok"]
                                        and st["source_ok"])
        if st["need_download"]:
            self.btn_reshade_download.setEnabled(True)
        else:
            self.btn_reshade_download.setEnabled(False)

    def on_saot_download_reshade(self):
        # the "download key" — reshade.me (user spec #6)
        QDesktopServices.openUrl(QUrl(RESHADE_DOWNLOAD_URL))
        self.show_message(
            "info", "DOWNLOAD RESHADE",
            "The ReShade website just opened.<br>"
            "Install ReShade <b>inside your main game folder</b> and check "
            "<b>DirectX 11/12</b> during setup, then press REFRESH here.")

    def on_saot_copy_reshade(self):
        ok, msg = saot_copy_reshade_files(self.custom_game_dir)
        self.refresh_saot_reshade()
        self.show_message(
            "info" if ok else "error",
            "COPY 2026 FILES" if ok else "COPY FAILED", msg)

    def refresh_momentum_summary(self):
        """One-line summary of the current auto-display settings."""
        c = self.mom_cfg
        parts = []
        for key, name in (("h1", "1st"), ("h2", "2nd"), ("et", "ET")):
            if c.get(f"mm_{key}_enabled"):
                parts.append(f"{name} {c.get(f'mm_{key}_minute')}'")
            else:
                parts.append(f"{name} off")
        end_txt = (f"{momentum_clamp_seconds(c.get('mm_end_seconds'), 20)}s"
                   if c.get("mm_end_enabled") else "off")
        self.lbl_mom_summary.setText(
            f"Auto display at: {', '.join(parts)}  •  on screen "
            f"{momentum_clamp_seconds(c.get('mm_show_seconds'))}s  •  end of match {end_txt}")

    def open_momentum_settings(self):
        self.show_modal(MomentumSettingsModal)

    def open_momentum_usage_modal(self):
        self.show_modal(MomentumUsageModal)

    def open_momentum_tutorial(self):
        # v1.0.0 — the "Momentum Tut" line of the developer Gist, fetched
        # at click time; MOMENTUM_TUTORIAL_URL is only an offline fallback.
        self.open_mod_tutorial("MOMENTUM", str(MOMENTUM_TUTORIAL_URL).strip())

    def _sync_glt_style_buttons(self):
        style = str(self.glt_cfg.get("style", "T6"))
        self.btn_glt_style1.setChecked(style == "T5")
        self.btn_glt_style2.setChecked(style == "T6")

    def on_glt_style_changed(self, btn_id):
        self.glt_cfg["style"] = "T5" if btn_id == 0 else "T6"
        self._sync_glt_style_buttons()
        # dynamic preview swap: the MOD PREVIEW box now shows the image of
        # the newly selected style (GLTPreview_T5.png / GLTPreview_T6.png)
        if hasattr(self, "glt_preview"):
            self.glt_preview.set_style(self.glt_cfg["style"])
        self.save_config()

    def open_glt_usage_modal(self):
        self.show_modal(GLTUsageModal, str(self.glt_cfg.get("rec_name", "F7") or "F7"))

    def open_all_controls_modal(self):
        self.show_modal(AllControlsModal)

    def open_glt_tutorial(self):
        # v1.0.0 — the "GLT Tut" line of the developer Gist, fetched at
        # click time; GLT_TUTORIAL_URL is only an offline fallback.
        self.open_mod_tutorial("GLT", str(GLT_TUTORIAL_URL).strip())

    def refresh_glt_key_buttons(self):
        self.btn_glt_play.setText(str(self.glt_cfg.get("play_name", "") or "NOT SET"))
        self.btn_glt_rec.setText(str(self.glt_cfg.get("rec_name", "") or "NOT SET"))

    _GLT_HINTS = {
        "play": ("Click the box — it waits right here for the new key (no window opens). "
                 "This key replays the recorded goal scene. Esc cancels."),
        "rec": ("Click the box — it waits right here for the new key (no window opens). "
                "This key starts manual recording inside Replay Mode. Esc cancels."),
    }

    def _glt_hint_label(self, slot):
        return self.lbl_glt_play_hint if slot == "play" else self.lbl_glt_rec_hint

    def on_glt_key_capture_started(self, slot):
        lbl = self._glt_hint_label(slot)
        lbl.setText("Waiting for the new key… press it now. Esc cancels.")
        lbl.setStyleSheet("font-size: 11px; color: #ff9900; font-weight: 700; line-height: 1.45; background: transparent; border: none;")
        lbl.show()

    def on_glt_key_capture_ended(self, slot):
        # v2.1.9 — the static description lives on the "!" icon now; the
        # status line simply hides when the capture ends.
        self._glt_hint_label(slot).hide()

    def on_glt_key_message(self, slot, msg):
        lbl = self._glt_hint_label(slot)
        lbl.setText(msg)
        lbl.show()

    def on_glt_key_captured(self, slot, vk, name):
        conflict = self.find_key_conflict(vk, GLT_MOD_NAME, slot)
        if conflict:
            dlg = self.show_modal(KeyConflictModal, name, GLT_MOD_NAME, conflict["label"])
            if not (dlg and dlg.result() == BaseModalDialog.RESULT_ACCEPTED):
                return
            conflict["clear"]()
        self.glt_cfg[f"{slot}_vk"] = f"0x{int(vk):02X}"
        self.glt_cfg[f"{slot}_name"] = str(name)
        self.refresh_glt_key_buttons()
        self.save_config()

    def makeHintLabel(self, text):
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("font-size: 11px; color: #94a3b8; line-height: 1.45; background: transparent; border: none;")
        return lbl

    def on_ref_overlay_changed(self, state):
        self.ref_cfg["overlay"] = bool(state)
        if hasattr(self, "ref_preview"):
            self.ref_preview.set_overlay_on(bool(state))
        self.save_config()

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def find_key_conflict(self, vk, exclude_mod, exclude_slot="apply"):
        try:
            vk_int = int(vk)
        except (TypeError, ValueError):
            return None
        for entry in self._key_conflict_entries():
            if entry["mod"] == exclude_mod and entry["slot"] == exclude_slot:
                continue
            if not entry["vk"] or not entry["enabled"]:
                continue
            try:
                if int(str(entry["vk"]), 16) == vk_int:
                    return entry
            except (TypeError, ValueError):
                continue
        return None

    def _key_conflict_entries(self):
        rv = self.mod_keys.get("Referee View", {})
        return [
            {
                "mod": "Referee View", "slot": "apply", "label": "Referee View",
                "vk": str(rv.get("vk", "") or ""),
                "enabled": bool(self.mods_state.get("Referee View", {}).get("enabled", False)),
                "clear": self._clear_referee_key,
            },
            {
                "mod": GLT_MOD_NAME, "slot": "play", "label": GLT_MOD_NAME + " — Play Animation",
                "vk": str(self.glt_cfg.get("play_vk", "") or ""),
                "enabled": bool(self.mods_state.get(GLT_MOD_NAME, {}).get("enabled", False)),
                "clear": self._clear_glt_play_key,
            },
            {
                "mod": GLT_MOD_NAME, "slot": "rec", "label": GLT_MOD_NAME + " — Manual Record",
                "vk": str(self.glt_cfg.get("rec_vk", "") or ""),
                "enabled": bool(self.mods_state.get(GLT_MOD_NAME, {}).get("enabled", False)),
                "clear": self._clear_glt_rec_key,
            },
            {
                "mod": SAOT_MOD_NAME, "slot": "apply", "label": SAOT_MOD_NAME + " — Call Key",
                "vk": str(self.mod_keys.get(SAOT_MOD_NAME, {}).get("vk", "") or ""),
                "enabled": bool(self.mods_state.get(SAOT_MOD_NAME, {}).get("enabled", False)),
                "clear": self._clear_saot_key,
            },
        ]

    def _clear_referee_key(self):
        self.mod_keys["Referee View"] = {"vk": "", "name": ""}
        self.ref_cfg["vk"] = ""
        self.ref_cfg["name"] = ""
        self.refresh_key_button_text()

    def _clear_glt_play_key(self):
        self.glt_cfg["play_vk"] = ""
        self.glt_cfg["play_name"] = ""
        self.refresh_glt_key_buttons()

    def _clear_glt_rec_key(self):
        self.glt_cfg["rec_vk"] = ""
        self.glt_cfg["rec_name"] = ""
        self.refresh_glt_key_buttons()

    def refresh_key_button_text(self):
        name = str(self.mod_keys.get("Referee View", {}).get("name", "") or "")
        self.btn_apply_key.setText(name if name else "NOT SET")

    def on_ref_key_capture_started(self):
        self.lbl_key_hint.setText("Waiting for the new key… press it now. Esc cancels.")
        self.lbl_key_hint.setStyleSheet("font-size: 11px; color: #ff9900; font-weight: 700; line-height: 1.45; background: transparent; border: none;")
        self.lbl_key_hint.show()

    def on_ref_key_capture_ended(self):
        # v2.1.9 — the static description lives on the "!" icon now; the
        # status line simply hides when the capture ends.
        self.lbl_key_hint.hide()

    def on_ref_key_message(self, msg):
        self.lbl_key_hint.setText(msg)
        self.lbl_key_hint.show()

    def on_ref_key_captured(self, vk, name):
        conflict = self.find_key_conflict(vk, "Referee View", "apply")
        if conflict:
            dlg = self.show_modal(KeyConflictModal, name, "Referee View", conflict["label"])
            if not (dlg and dlg.result() == BaseModalDialog.RESULT_ACCEPTED):
                return
            conflict["clear"]()
        self.mod_keys["Referee View"]["vk"] = f"0x{int(vk):02X}"
        self.mod_keys["Referee View"]["name"] = str(name)
        self.ref_cfg["vk"] = self.mod_keys["Referee View"]["vk"]
        self.ref_cfg["name"] = str(name)
        self.refresh_key_button_text()
        self.save_config()

    def open_usage_modal(self):
        self.show_modal(RefereeUsageModal, self.ref_cfg.get("name", "T"))

    def open_tutorial(self):
        # v1.0.0 — the "Referee Tut" line of the developer Gist, fetched
        # at click time. The old hardcoded constants (and the legacy saved
        # per-mod URL) only act as an offline fallback.
        fallback = (str(REF_TUTORIAL_URL).strip()
                    or str(self.ref_cfg.get("url", "")).strip())
        self.open_mod_tutorial("REFEREE", fallback)

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    def on_apply_launch(self):
        self.save_config()
        ok = self.launch_bridge()
        if ok:
            # v2.1.2 — the Bridge takes over from here: close MyMods
            # automatically (no exit prompt — this close is intentional and
            # ModsConfig.json was already saved just above).
            self._bridge_launch_close = True
            self.close()
        else:
            self.show_message(
                "error", "LAUNCH FAILED",
                "Mod Bridge could not be started.<br>"
                "The UAC prompt may have been cancelled, or <b>ModBridge.exe</b> is missing "
                "next to MyMods.exe.")

    def launch_bridge(self):
        if sys.platform != "win32":
            return False
        # Refresh the GLT animation bindings straight from the game settings
        # file right before the bridge spawns the mods — the user may have
        # changed keys inside the game while this launcher was open.
        try:
            apply_glt_animation_keys_to_config()
        except Exception:
            pass
        try:
            shell32 = ctypes.windll.shell32
            bridge_exe = os.path.join(APP_DIR, "ModBridge.exe")
            if not os.path.exists(bridge_exe):
                return False
            res = shell32.ShellExecuteW(None, "runas", bridge_exe, None, APP_DIR, 1)
            return int(res) > 32
        except Exception:
            return False

    def show_message(self, kind, title, message):
        self.show_modal(ThemedMessageModal, kind, title, message)

    # ------------------------------------------------------------------
    # v2.1.2 — donation support: one handler for every DONATE button
    # ------------------------------------------------------------------
    def open_donate(self):
        """Open the donation page when DONATE_URL is configured.
        Returns True when a link was opened, False when none is set."""
        url = str(DONATE_URL).strip()
        if not url:
            return False
        try:
            # v1.0.0b — respect openUrl's result: False means the OS could
            # not hand the URL to a browser (no handler / shell failure),
            # so the caller must fall back to the friendly error note.
            if not QDesktopServices.openUrl(QUrl(url)):
                return False
        except Exception:
            return False
        return True

    def on_donate_clicked(self):
        """Standalone DONATE buttons (header + above the Bridge button)."""
        if not self.open_donate():
            # v1.0.0b — the link is LIVE now, so reaching this branch means
            # the browser could not be opened (offline / no handler).
            self.show_message(
                "error", "DONATE",
                "Couldn't open the donation page. \u2764<br><br>"
                "Please check your internet connection and try again "
                "in a moment.<br><br>"
                "Thank you for supporting <b>FL 2026 Mods by Milad</b>!")

    # ------------------------------------------------------------------
    # v2.1.8 / v1.0.1 — CONTACT THE DEVELOPER (ABOUT window badges)
    # ------------------------------------------------------------------
    def on_contact_clicked(self, kind):
        """v1.0.1 — a badge click fetches the developer Gist NOW and opens
        that channel's line ("Youtube" / "Instagram" / "Telegram" /
        "E-mail"). The Gist is authoritative ('null' -> friendly
        try-again note); when the Gist is unreachable the CONTACT_*
        constants act as offline fallbacks. The GitHub badge opens the
        developer's Gist page (GIST_PAGE_URL) directly — no fetch."""
        kind = str(kind)
        if kind == "github":
            try:
                QDesktopServices.openUrl(QUrl(GIST_PAGE_URL))
            except Exception:
                pass
            return
        fallback = {
            "youtube":   CONTACT_YOUTUBE_URL,
            "instagram": CONTACT_INSTAGRAM_URL,
            "telegram":  CONTACT_TELEGRAM_URL,
            "email":     CONTACT_EMAIL_ADDRESS,
        }.get(kind, "")

        def worker():
            manifest = fetch_update_manifest()
            self.gist_bus.contact_fetched.emit(kind, str(fallback or ""),
                                               manifest)
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            self._on_contact_fetched(kind, str(fallback or ""), None)

    def _on_contact_fetched(self, kind, fallback, manifest):
        kind = str(kind)
        label = CONTACT_LABELS.get(kind, kind.upper())
        url = ""
        if manifest is not None:
            # the Gist is authoritative: 'null' means 'not published yet'
            url = str((manifest.get("social") or {}).get(kind.upper())
                      or "").strip()
        else:
            # Gist unreachable -> honour the local fallback constant, if any
            url = str(fallback or "").strip()
        if not url:
            if manifest is not None:
                self.show_message(
                    "info", "CONTACT — %s" % label,
                    "This link hasn't been published yet.<br>"
                    "The developer will add it soon — please try again later.")
            else:
                self.show_message(
                    "info", "CONTACT — %s" % label,
                    "This contact channel is being connected right now.<br>"
                    "The link will appear here in a future update — thank you "
                    "for wanting to report bugs and suggest features! \u2764")
            return
        if kind == "email" and "@" in url and not url.startswith(
                ("mailto:", "http:", "https:")):
            url = "mailto:" + url       # plain address -> mailto link
        try:
            QDesktopServices.openUrl(QUrl(url))
        except Exception:
            pass

    # ------------------------------------------------------------------
    def makeLabel(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("font-size: 12px; font-weight: 700; color: #e0f2fe; margin-top: 1px; background: transparent; border: none;")
        return lbl

    def makeToggleRow(self, title, default=False):
        box = QHBoxLayout()
        lbl = QLabel(title)
        lbl.setStyleSheet("font-size: 12px; color: #bae6fd; font-weight: 600; background: transparent; border: none;")
        toggle = NeonToggle(master_window=self, checked=default)
        box.addWidget(lbl)
        box.addStretch()
        box.addWidget(toggle)
        return box

    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # ==================================================================
    # v2.2.0 — PERMANENT APP COLOUR + STATIC ANIMATION MODE
    # (user requests #4 and #5)
    # ==================================================================
    def permanent_theme(self):
        """The user-fixed CyberTheme (Application Settings colour picker),
        or None when the app should follow each mod's own theme."""
        val = str(getattr(self, "ui_permanent_color", "") or "").strip()
        if not val:
            return None
        return build_custom_theme(val)

    def _theme_for_selection(self, mod_name):
        """Theme that belongs to a mod selection: the user's permanent
        colour when one is set, otherwise the mod's own theme."""
        perm = self.permanent_theme()
        if perm is not None:
            return perm.clone()
        return THEMES.get(mod_name, THEMES["S.A.O.T"]).clone()

    def apply_permanent_color(self, color_hex_or_empty):
        """Called live by the Application Settings colour picker.
        Empty string = go back to the automatic per-mod themes."""
        val = str(color_hex_or_empty or "").strip()
        if val and QColor(val).isValid():
            self.ui_permanent_color = QColor(val).name()
        else:
            self.ui_permanent_color = ""
        self.save_config()
        # morph the running UI to the theme that now belongs to the UI
        # (static mode skips the morph — everything is fixed)
        self.start_theme = self.active_theme.clone()
        self.target_theme = self._theme_for_selection(self.current_mod_name)
        self.theme_anim.stop()
        if getattr(self, "ui_static_mode", False):
            self._on_theme_anim_finished()
        else:
            self.theme_anim.start()

    def set_static_mode(self, enabled):
        """v2.2.0 (user request #5) — FREEZE EVERYTHING: when enabled all
        animations stop — the background video pauses on its current
        frame, particles, the glass glints and every pulse freeze. The
        UI becomes a fixed, static picture until the option is turned
        off again."""
        self.ui_static_mode = bool(enabled)
        self.save_config()
        self.apply_static_mode()

    def apply_static_mode(self):
        """Apply self.ui_static_mode to every animated component."""
        on = bool(getattr(self, "ui_static_mode", False))
        # 1. the master 16 ms frame timer (particles, border glints, the
        #    launch-button shimmer and the alert pulse all hang off it)
        if on:
            self.timer.stop()
        else:
            self.timer.start(16)
        # 2. the background video — pause on the current frame / resume
        vb = getattr(self, "video_bg", None)
        if vb is not None:
            if on:
                vb.freeze()
            else:
                vb.unfreeze()
        # 3. the conflict warning banner pulse (only runs while visible)
        banner = getattr(self, "warning_banner", None)
        if banner is not None and hasattr(banner, "set_frozen"):
            banner.set_frozen(on)
        # 4. Task 32 — freeze/resume the dedicated football HUD animation too.
        mark = getattr(self, "logo_icon", None)
        if mark is not None and hasattr(mark, "set_frozen"):
            mark.set_frozen(on)
        # 5. one repaint so a frozen-but-never-painted state shows instantly
        self.update()

    def onModSelected(self, name):
        # v2.1.2 — not-yet-submitted mods are not selectable
        if name not in IMPLEMENTED_MOD_NAMES:
            return
        if self.current_mod_name == name and not self.theme_anim.state() == QVariantAnimation.State.Running:
            return

        self.current_mod_name = name
        self.lbl_mod_title.setText(f"MOD SETTINGS: {name.upper()}")

        # Initiate smooth morphing transition to the new target theme.
        # v2.2.0 — the target is the PERMANENT colour when the user set
        # one (theme never changes when switching mods), and in static
        # mode the morph is skipped entirely — the UI simply jumps.
        self.start_theme = self.active_theme.clone()
        self.target_theme = self._theme_for_selection(name)

        if getattr(self, "ui_static_mode", False):
            self._on_theme_anim_finished()
        else:
            self.theme_anim.stop()
            self.theme_anim.start()

        # Update left rows selection style immediately
        for r in self.mod_rows:
            r.setSelected(r.name == name)

        if hasattr(self, 'options_stack'):
            self.options_stack.setCurrentIndex(self._options_index_for(name))

        # Sync master toggle
        is_enabled = self.mods_state[name]["enabled"]
        self._syncing_toggle = True
        try:
            self.master_toggle.setChecked(is_enabled)
            self.updateOptionsPanelState(is_enabled)
        finally:
            self._syncing_toggle = False

        self.save_config()

    def _on_theme_anim_step(self, progress):
        self.active_theme = self.start_theme.interpolate(self.target_theme, progress)
        self._apply_current_theme_frame()

    def _on_theme_anim_finished(self):
        self.active_theme = self.target_theme.clone()
        self._apply_current_theme_frame()

    def _apply_current_theme_frame(self):
        # 1. Instantly regenerate particle sprites with the new theme
        self.sprite_lib.set_theme(self.active_theme)
        # 2. Immediately refresh EVERY active particle on screen (no old colors left!)
        for pt in self.particles:
            pt.refresh_sprite()

        # 3. Dynamic header accents
        # The football HUD mark is self-painted and keeps its fixed identity;
        # only the surrounding text follows the active application theme.
        self.logo_icon.update()
        self.lbl_sub.setStyleSheet(f"font-size: 12px; font-weight: 900; color: {self.active_theme.primary.name()}; letter-spacing: 3px; background: transparent;")
        self.lbl_compat_title.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; letter-spacing: 3px; background: transparent; border: none;")
        self.lbl_compat_fl.setStyleSheet(self._fl_link_stylesheet(self.active_theme))
        self.fl_glow.setColor(self.active_theme.glow_color)
        self.lbl_mgr.setStyleSheet(f"font-size: 14.5px; font-weight: 900; color: {self.active_theme.primary.name()}; letter-spacing: 2px; margin-bottom: 3px; background: transparent; border: none;")
        self.lbl_enable.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; background: transparent; border: none;")
        self.lbl_preview.setStyleSheet(f"font-size: 13px; font-weight: 800; color: {self.active_theme.accent.name()}; letter-spacing: 0.5px; background: transparent; border: none;")

        # 4. Update left rows selection gradient & info icons
        for r in self.mod_rows:
            r.applyStyle()
            r.info_icon.update()
            r.toggle.update()

        # 4b. v2.1.6 — repaint the theme-driven glass widgets (buttons,
        # category headers, manufacturer plate) with the new colours
        for b in self.findChildren(GlassPillButton):
            b.update()
        for h in getattr(self, "category_headers", {}).values():
            h.update()
        if hasattr(self, "manufacturer_box"):
            self.manufacturer_box.update()
        # v2.2.0 — restyle the shared option cards / card titles so the
        # boxes on EVERY mod page match the current theme instantly
        self._refresh_option_cards_theme()
        # (v2.1.9) the old top contact-bar repaint is gone with the bar;
        # the ABOUT badges live inside a modal that is never open while a
        # theme morph runs, so no extra repaint is needed here.

        # 5. Re-render background gradient and tactical pitch
        self._rebuild_bg_cache()
        self.pitch._rebuild_base_cache()

        # 6. Apply comprehensive dynamic stylesheet
        self.applyStyles()
        self.update()

    def onModRowToggled(self, name, state):
        # v2.1.2 — not-yet-submitted mods can never be activated
        if name not in IMPLEMENTED_MOD_NAMES:
            self.mods_state[name]["enabled"] = False
            self.save_config()
            return
        self.mods_state[name]["enabled"] = state
        self.save_config()
        # Yellow warning when Referee View + GLT end up enabled together
        self.update_conflict_warning(notify=bool(state))
        if name == self.current_mod_name:
            if not self._syncing_toggle:
                self._syncing_toggle = True
                try:
                    self.master_toggle.setChecked(state)
                    self.updateOptionsPanelState(state)
                finally:
                    self._syncing_toggle = False

    def _on_category_toggled(self, cat_name, expanded):
        """v2.1.6 — expand/collapse one category block and PERSIST the
        state (ModsConfig.json -> ui.expanded) so the manager reopens
        exactly the way the user left it."""
        self.cat_expanded[cat_name] = bool(expanded)
        for row in self.cat_row_map.get(cat_name, []):
            row.setVisible(bool(expanded))
        self.save_config()

    def onMasterToggleChanged(self, state):
        self.mods_state[self.current_mod_name]["enabled"] = state
        self.save_config()
        self.updateOptionsPanelState(state)
        # Yellow warning when Referee View + GLT end up enabled together
        self.update_conflict_warning(notify=bool(state))
        if not self._syncing_toggle:
            self._syncing_toggle = True
            try:
                for r in self.mod_rows:
                    if r.name == self.current_mod_name:
                        r.toggle.setChecked(state)
                        break
            finally:
                self._syncing_toggle = False

    def update_conflict_warning(self, notify=False):
        """Show the yellow banner while Referee View AND Goal Line Technology
        are both enabled; when notify=True (a mod was just switched ON) also
        raise a one-time yellow warning dialog."""
        if not hasattr(self, "warning_banner"):
            return False
        both = (bool(self.mods_state.get("Referee View", {}).get("enabled", False)) and
                bool(self.mods_state.get(GLT_MOD_NAME, {}).get("enabled", False)))
        self.warning_banner.setVisible(both)
        if both and notify:
            self.show_modal(ThemedMessageModal, "warn", "COMPATIBILITY WARNING",
                            "<b>Referee View</b> and <b>Goal Line Technology</b> are both enabled.<br><br>"
                            "Running these two mods at the same time <b>may crash the game</b>. "
                            "If you experience crashes, enable only one of them at a time.",
                            height=380)
        return both

    # ------------------------------------------------------------------
    # v2.1.2 — per-mod disabled state: every mod's dedicated page follows
    # ITS OWN enabled flag. A disabled page gets setEnabled(False) (which
    # blocks ALL interaction) plus a translucent dark veil so every element
    # visually reads as greyed-out and unresponsive.
    # ------------------------------------------------------------------
    def _ensure_page_veil(self, page):
        veil = getattr(page, "_disabled_veil", None)
        if veil is None:
            veil = QWidget(page)
            veil.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents
                              if IS_PYQT6 else Qt.WA_TransparentForMouseEvents)
            veil.setStyleSheet(
                "background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
                "stop:0 rgba(2, 8, 18, 165), stop:1 rgba(2, 8, 18, 210)); "
                "border-radius: 16px;")
            page._disabled_veil = veil
            page.installEventFilter(self)
        return veil

    def eventFilter(self, obj, event):
        # keep each disabled-veil sized to its page while the layout lives
        veil = getattr(obj, "_disabled_veil", None)
        et = event.type()
        resize_t = (QEvent.Type.Resize if IS_PYQT6 else QEvent.Resize)
        if veil is not None and et == resize_t:
            veil.setGeometry(obj.rect())
        return super().eventFilter(obj, event)

    def _set_page_enabled(self, page, enabled):
        page.setEnabled(enabled)
        veil = self._ensure_page_veil(page)
        if enabled:
            veil.hide()
        else:
            veil.setGeometry(page.rect())
            veil.raise_()
            veil.show()

    def updateOptionsPanelState(self, enabled=None):
        """v2.1.2 — per-mod: a deactivated mod's dedicated menu is greyed
        out and unresponsive, while every OTHER mod's page keeps its own
        state. (The `enabled` argument is kept for compatibility and only
        used as the fallback for the generic page.)"""
        st = self.mods_state
        self._set_page_enabled(
            self.ref_container,
            bool(st.get("Referee View", {}).get("enabled", False)))
        self._set_page_enabled(
            self.glt_container,
            bool(st.get(GLT_MOD_NAME, {}).get("enabled", False)))
        self._set_page_enabled(
            self.mom_container,
            bool(st.get(MOMENTUM_MOD_NAME, {}).get("enabled", False)))
        self._set_page_enabled(
            self.hm_container,
            bool(st.get(HEATMAP_MOD_NAME, {}).get("enabled", False)))
        self._set_page_enabled(
            self.saot_container,
            bool(st.get(SAOT_MOD_NAME, {}).get("enabled", False)))
        # the generic page follows the currently selected mod
        cur = bool(st.get(self.current_mod_name, {}).get("enabled", False))
        self._set_page_enabled(self.options_container, cur)
        self.pitch.setActive(cur)
        val_color = self.active_theme.primary.name() if cur else "#475569"
        self.lbl_op_val.setStyleSheet(f"color: {val_color}; font-weight: bold; min-width: 44px; background: transparent;")
        val_color2 = self.active_theme.accent.name() if cur else "#475569"
        self.lbl_int_val.setStyleSheet(f"color: {val_color2}; font-weight: bold; min-width: 44px; background: transparent;")

    def show_modal(self, modal_class, *args, **kwargs):
        central = self.centralWidget()
        self.dim_overlay.setGeometry(central.rect())
        self.dim_overlay.show()
        self.dim_overlay.raise_()

        dlg = None
        try:
            dlg = modal_class(self, *args, **kwargs)
            dlg.setParent(central)
            dlg.move((central.width() - dlg.width()) // 2,
                     (central.height() - dlg.height()) // 2)
            dlg.show()
            dlg.raise_()
            dlg.setFocus()
            dlg.exec_local()
        finally:
            self.dim_overlay.hide()
            if dlg is not None:
                dlg.deleteLater()
        return dlg

    def openRealDiagnostics(self):
        self.show_modal(RealDiagnosticModal)

    def openSettingsModal(self):
        self.show_modal(SettingsModal)

    def openAboutModal(self):
        self.show_modal(AboutModal)

    # ------------------------------------------------------------------
    # v1.0.0 — ONLINE UPDATE CHECK + GIST-BACKED YOUTUBE TUTORIALS.
    # The developer Gist is fetched strictly on demand: once on program
    # entry (update check) and once per YOUTUBE TUTORIAL click — never at
    # import time and never preloaded. Results cross the thread boundary
    # through self.gist_bus signals.
    # ------------------------------------------------------------------
    def _startup_update_check(self):
        if UPDATE_CHECK_AT_STARTUP:
            self._start_update_check(manual=False)

    def check_for_updates_clicked(self):
        self._start_update_check(manual=True)

    def _start_update_check(self, manual):
        def worker():
            manifest = fetch_update_manifest()
            self.gist_bus.update_checked.emit(manifest, bool(manual))
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            self._on_update_checked(None, bool(manual))

    def _on_update_checked(self, manifest, manual):
        if manifest is None:
            if manual:
                self.show_message(
                    "error", "UPDATE CHECK FAILED",
                    "Could not reach the update server.<br>"
                    "Please check your internet connection and try again "
                    "later.")
            # a failed entry check stays silent — never nag at startup
            return
        latest = manifest.get("latest_version")
        if version_is_newer(latest, APP_VERSION):
            self.show_modal(UpdateAvailableModal, latest,
                            manifest.get("github"))
        elif manual:
            self.show_message(
                "info", "UP TO DATE",
                f"You are on the latest release (v{APP_VERSION}). \u2764")

    def open_mod_tutorial(self, mod_key, fallback_url=""):
        """Fetch the Gist NOW (the user clicked a YOUTUBE TUTORIAL button)
        and open that mod's link. A 'null' line in the Gist — or an
        unreachable Gist with no local fallback — shows the friendly
        try-again-later error."""
        mod_key = str(mod_key)
        fallback_url = str(fallback_url or "")

        def worker():
            manifest = fetch_update_manifest()
            self.gist_bus.tutorial_fetched.emit(mod_key, fallback_url,
                                                manifest)
        try:
            threading.Thread(target=worker, daemon=True).start()
        except Exception:
            self._on_tutorial_fetched(mod_key, fallback_url, None)

    def _on_tutorial_fetched(self, mod_key, fallback_url, manifest):
        url = ""
        if manifest is not None:
            # the Gist is authoritative: 'null' means 'not published yet'
            url = str((manifest.get("tutorials") or {}).get(mod_key) or "").strip()
        else:
            # Gist unreachable -> honour the local fallback link, if any
            url = str(fallback_url or "").strip()
        if url:
            try:
                QDesktopServices.openUrl(QUrl(url))
            except Exception:
                pass
        else:
            self.show_message(
                "error", "LINK NOT AVAILABLE",
                "This link hasn't been published yet.<br>"
                "Please try again later.")

    def confirm_exit(self):
        # v2.1.2 — all normal closes flow through closeEvent, which shows
        # the friendly donation prompt (the old "are you sure" text is gone)
        self.close()

    def closeEvent(self, event):
        """v2.1.2 — every NORMAL close (X button, Alt+F4, taskbar) shows the
        friendly donation prompt.  Closing because the Bridge was just
        launched is intentional and skips the prompt."""
        if getattr(self, "_bridge_launch_close", False):
            self._bridge_launch_close = False
            event.accept()
            return
        dlg = self.show_modal(CloseConfirmModal)
        if dlg is not None and dlg.result() == BaseModalDialog.RESULT_ACCEPTED:
            event.accept()
        else:
            event.ignore()

    def mousePressEvent(self, event):
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.button() == left_btn:
            self.drag_position = get_global_pos(event) - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        left_btn = Qt.MouseButton.LeftButton if IS_PYQT6 else Qt.LeftButton
        if event.buttons() == left_btn:
            self.move(get_global_pos(event) - self.drag_position)
            event.accept()

    def applyStyles(self):
        theme = self.active_theme
        p_name = theme.primary.name()
        s_name = theme.secondary.name()
        a_name = theme.accent.name()
        bg1 = theme.bg_dark[1]
        bg2 = theme.bg_dark[2]

        self.setStyleSheet(f"""
            QToolTip {{
                background-color: rgba({bg1.red()}, {bg1.green()}, {bg1.blue()}, 246);
                color: #e0f2fe;
                border: 1px solid {p_name};
                border-radius: 6px;
                padding: 6px;
                font-family: 'Segoe UI';
                font-size: 11px;
            }}

            QWidget#MainContainer {{
                border: 1.5px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.45);
                border-radius: 22px;
            }}

            QFrame#ModalCard {{
                background: rgba(4, 13, 28, 0.96);
                border: 1.5px solid {p_name};
                border-radius: 18px;
            }}

            QPushButton#ModalCloseBtn {{
                background: transparent;
                border: none;
                color: {a_name};
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton#ModalCloseBtn:hover {{
                color: #ff3366;
            }}

            QPushButton#IconBtn {{
                background: rgba(8, 25, 48, 0.7);
                border: 1px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.35);
                color: {p_name};
                font-size: 14.5px;
                border-radius: 8px;
                min-width: 36px;
                min-height: 36px;
            }}
            QPushButton#IconBtn:hover {{
                background: rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.2);
                border-color: {p_name};
                color: #ffffff;
            }}

            QPushButton#VibrantDonateBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ff2d78, stop:0.5 #ff5e3a, stop:1 #b845ff);
                border: 1.6px solid rgba(255, 255, 255, 0.85);
                color: #ffffff;
                font-weight: 950;
                font-size: 12.5px;
                letter-spacing: 1.8px;
                border-radius: 10px;
                padding: 8px 24px;
            }}
            QPushButton#VibrantDonateBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #ff4a8d, stop:0.5 #ff7a52, stop:1 #cc63ff);
                border-color: #ffffff;
            }}
            QPushButton#VibrantDonateBtn:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #d91f60, stop:0.5 #e64a2e, stop:1 #9333ea);
                border-color: rgba(255, 255, 255, 0.65);
            }}

            QPushButton#WindowBtn, QPushButton#CloseBtn {{
                background: transparent;
                border: none;
                color: {a_name};
                font-size: 15px;
                min-width: 30px;
                min-height: 30px;
            }}
            QPushButton#WindowBtn:hover {{ color: #ffffff; }}
            QPushButton#CloseBtn:hover {{ color: #ff3366; }}

            QPushButton#DiagBtn {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.10), stop:0.5 rgba(255, 255, 255, 0.04), stop:1 rgba(0, 0, 0, 0.30));
                border: 1.2px solid rgba(255, 255, 255, 0.28);
                border-radius: 19px;
                color: #dbe4f0;
                font-size: 12.5px;
                font-weight: 800;
                letter-spacing: 0.8px;
                padding: 0px 18px;
            }}
            QPushButton#DiagBtn:hover {{
                border-color: {a_name};
                color: #ffffff;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.30),
                    stop:1 rgba({theme.secondary.red()}, {theme.secondary.green()}, {theme.secondary.blue()}, 0.16));
            }}
            /* v2.1.6 — UNMISSABLE active state for checkable option pills
               (Heat Map viewer side: RANDOM / HOME ONLY / AWAY ONLY) */
            QPushButton#DiagBtn:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {s_name}, stop:1 {p_name});
                border: 1.6px solid #ffffff;
                color: #ffffff;
                font-weight: 900;
            }}
            QPushButton#DiagBtn:disabled {{
                border-color: rgba(70, 90, 115, 0.35);
                color: #5a6b80;
                background: rgba(10, 18, 30, 0.45);
            }}

            QPushButton#DiagRecheckBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {s_name}, stop:1 {p_name});
                border: 1.4px solid {a_name};
                border-radius: 12px;
                color: #ffffff;
                font-size: 13.5px;
                font-weight: 900;
                letter-spacing: 1.2px;
                padding: 0px 20px;
            }}

            QPushButton#KeySelectBtn {{
                background: rgba({bg1.red()}, {bg1.green()}, {bg1.blue()}, 0.85);
                border: 1.4px solid {p_name};
                border-radius: 10px;
                color: #ffffff;
                font-size: 13px;
                font-weight: 900;
                letter-spacing: 1px;
                padding: 0px 18px;
            }}
            QPushButton#KeySelectBtn:hover {{
                background: rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.25);
                border-color: {a_name};
            }}

            QPushButton#DangerBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #b91c1c);
                border: 1.2px solid #fca5a5;
                border-radius: 10px;
                color: #ffffff;
                font-size: 12.5px;
                font-weight: 900;
                letter-spacing: 1.2px;
                padding: 0px 22px;
            }}
            QPushButton#DangerBtn:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f87171, stop:1 #dc2626);
                border-color: #ffffff;
            }}

            QLineEdit#LineEntry {{
                background: rgba({bg1.red()}, {bg1.green()}, {bg1.blue()}, 0.85);
                border: 1.2px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.45);
                border-radius: 8px;
                padding: 4px 12px;
                color: #ffffff;
                font-weight: 600;
                font-size: 12.5px;
                selection-background-color: {s_name};
            }}
            QLineEdit#LineEntry:focus {{
                border-color: {p_name};
            }}

            /* Completely Themed ComboBox with Smooth Glass Look */
            QComboBox {{
                background: rgba({bg1.red()}, {bg1.green()}, {bg1.blue()}, 0.85);
                border: 1.2px solid rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.45);
                border-radius: 8px;
                padding: 6px 12px;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
            }}
            QComboBox:hover {{
                border-color: {p_name};
            }}
            QComboBox:disabled {{
                background: rgba(8, 16, 28, 0.5);
                border-color: rgba(50, 80, 110, 0.25);
                color: #64748b;
            }}
            QComboBox QAbstractItemView {{
                background: {bg2.name()};
                border: 1.2px solid {p_name};
                selection-background-color: {s_name};
                selection-color: #ffffff;
                color: #ffffff;
                border-radius: 6px;
                padding: 4px;
            }}

            /* v2.1.6 — liquid-glass option pills (render mode etc.) */
            QPushButton#ModeSelectBtn {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 rgba(255, 255, 255, 0.09), stop:1 rgba(0, 0, 0, 0.28));
                border: 1.1px solid rgba(255, 255, 255, 0.24);
                color: rgba({theme.accent.red()}, {theme.accent.green()}, {theme.accent.blue()}, 0.85);
                font-size: 11px;
                font-weight: 700;
                padding: 6px 17px;
                border-radius: 15px;
            }}
            QPushButton#ModeSelectBtn:hover {{
                border-color: rgba({theme.primary.red()}, {theme.primary.green()}, {theme.primary.blue()}, 0.75);
                color: #ffffff;
            }}
            QPushButton#ModeSelectBtn:checked {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {s_name}, stop:1 {p_name});
                border: 1.5px solid #ffffff;
                color: #ffffff;
                font-weight: 900;
            }}
            QPushButton#ModeSelectBtn:disabled {{
                background: rgba(6, 14, 24, 0.4);
                border-color: rgba(40, 65, 90, 0.2);
                color: #475569;
            }}

            QPushButton#NeonActionBtn {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {s_name}, stop:1 {p_name});
                border: 1.4px solid {a_name};
                border-radius: 12px;
                color: #ffffff;
                font-size: 14.5px;
                font-weight: 900;
                letter-spacing: 1.5px;
                padding: 10px 18px;
            }}
        """)

# -------------------------------------------------------------
# 13. Main Canvas Widget
# -------------------------------------------------------------
class MainCanvasWidget(QWidget):
    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master = master_window
        self.setObjectName("MainContainer")

    def paintEvent(self, event):
        # v2.1.8 — while the GPU video background is active it covers the
        # canvas and NOTHING code-drawn runs (no gradient, no particles).
        # When the video is unavailable the classic painted gradient +
        # particles take over automatically as the fallback.
        if self.master.video_active():
            super().paintEvent(event)
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform if IS_PYQT6 else QPainter.SmoothPixmapTransform)

        if self.master.bg_cache:
            p.drawPixmap(0, 0, self.master.bg_cache)

        for pt in self.master.particles:
            p.drawPixmap(QPointF(pt.x - pt.half_w, pt.y - pt.half_h), pt.sprite)

        super().paintEvent(event)

# =============================================================
# ANIMATED VIDEO BACKGROUND  (Background/Back.mp4)
# ---------------------------------------------------------------
# VideoBackgroundWidget plays the user-provided 1920x1080 clip as the
# app's animated background:
#   * Decoding runs in the OS media stack (hardware-accelerated on
#     Windows: Media Foundation / D3D11) via QMediaPlayer -> QVideoSink.
#   * Every decoded frame is converted to a QImage and painted with
#     QPainter, cover-fitted inside the rounded window frame. The
#     per-mod color grade uses the PDF blend modes (CompositionMode_Hue
#     / _Saturation), so the same clip follows each mod's color scheme
#     and even morphs during live theme transitions.
#   * The renderer deliberately does NOT use raw OpenGL: Qt 6.10
#     removed QOpenGLFunctions / QOpenGLContext::functions(), which
#     made the previous GL-shader pipeline fail silently (the video
#     never showed) on current PyQt6 builds. QPainter works on every
#     Qt/PyQt build; the video itself is still decoded in hardware.
#   * Requirements:  pip install PyQt6-Multimedia   (optional package).
# When the video, the multimedia stack or the codec is unavailable the
# widget deactivates itself and the classic painted gradient background
# is used automatically (zero behavior change for the user). Failures
# are reported on the console with a  [VideoBackground]  prefix.
# =============================================================


class VideoBackgroundWidget(QWidget):
    """Full-window video background (Background/Back.mp4). Inactive
    (hidden) whenever the file, the PyQt6-Multimedia package or the
    codec is unavailable — the painted gradient fallback takes over."""

    def __init__(self, master_window, parent=None):
        super().__init__(parent)
        self.master = master_window
        self._failed = False
        self._frame_img = None          # most recent decoded frame (QImage)
        self._frame_seq = 0             # increments once per delivered frame
        self._scaled_img = None         # widget-sized cache of _frame_img
        self._scaled_key = None         # (frame_seq, w, h, dpr)
        self._player = None
        self._sink = None
        # v2.2.0 — STATIC MODE flag (all animations frozen)
        self._static = False
        # v2.1.2 — user colour-intensity (0..1): how strongly the B&W clip
        # is graded toward the mod theme. 1.0 = full theme colour.
        self._color_intensity = 1.0

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents
                          if IS_PYQT6 else Qt.WA_TransparentForMouseEvents)

        self._available = bool(HAS_VIDEO_PLAYBACK and QMediaPlayer is not None
                               and os.path.isfile(BACKGROUND_VIDEO_FILE))
        if self._available:
            self._init_player()
        else:
            self._log("deactivated at init:",
                      "PyQt6-Multimedia package missing"
                      if not HAS_VIDEO_PLAYBACK
                      else "video file not found: " + BACKGROUND_VIDEO_FILE)

    # -------------------------------------------------- helpers
    @staticmethod
    def _log(*args):
        try:
            print("[VideoBackground]", *args, flush=True)
        except Exception:
            pass

    def is_active(self):
        return bool(self._available and not self._failed
                    and self._player is not None)

    def set_color_intensity(self, value_0_100):
        """v2.1.2 — user control: how strongly the black & white clip is
        colour-graded toward the active mod's theme (0 = pure greyscale,
        100 = full theme colour). Live: the next repaint applies it."""
        try:
            self._color_intensity = max(0.0, min(1.0, float(value_0_100) / 100.0))
        except Exception:
            self._color_intensity = 1.0
        self.update()

    # -------------------------------------------------- v2.2.0 static mode
    def freeze(self):
        """STATIC MODE (user request #5): pause the player on its current
        frame. The widget keeps painting the last delivered frame, so the
        background becomes a perfectly still picture instead of a black
        hole. No new frames arrive while paused."""
        self._static = True
        try:
            if self._player is not None:
                self._player.pause()
                self._log("static mode: video paused on the current frame")
        except Exception as exc:
            self._log("freeze failed:", repr(exc))
        self.update()

    def unfreeze(self):
        """Leave STATIC MODE: resume normal looping playback."""
        was = getattr(self, "_static", False)
        self._static = False
        if was and self.is_active():
            try:
                self._player.play()
                self._log("static mode off: video resumed")
            except Exception as exc:
                self._log("unfreeze failed:", repr(exc))

    # -------------------------------------------------- playback
    def _init_player(self):
        try:
            self._player = QMediaPlayer(self)
            self._sink = QVideoSink(self)
            self._player.setVideoSink(self._sink)
            self._sink.videoFrameChanged.connect(self._on_video_frame)
            self._player.mediaStatusChanged.connect(self._on_media_status)
            self._player.errorOccurred.connect(self._on_player_error)
            # Attach a MUTED audio output: some Windows builds advance the
            # playback clock through the audio sink, and attaching one keeps
            # the engine happy while never producing any sound.
            try:
                from PyQt6.QtMultimedia import QAudioOutput
                self._audio_out = QAudioOutput(self)
                self._audio_out.setMuted(True)
                self._player.setAudioOutput(self._audio_out)
            except Exception:
                self._audio_out = None
            try:
                self._player.setLoops(-1)          # infinite loop (Qt >= 6.1)
            except Exception:
                pass
            self._player.setSource(QUrl.fromLocalFile(BACKGROUND_VIDEO_FILE))
            self._player.play()
            self._log("player started:", BACKGROUND_VIDEO_FILE)
            # Safety net: if not a single frame has arrived shortly after
            # startup, drop back to the gradient (broken codec / file).
            QTimer.singleShot(6000, self._no_frame_watchdog)
        except Exception as exc:
            self._log("player init failed:", repr(exc))
            self._failed = True

    def _no_frame_watchdog(self):
        if (not self._failed and self._frame_img is None
                and self._player is not None):
            self._log("no frames arrived — deactivating (codec/file issue)")
            self._deactivate()

    def _deactivate(self):
        if self._failed:
            return
        self._failed = True
        try:
            self.hide()
        except Exception:
            pass
        m = self.master
        if hasattr(m, "_sync_overlay_geometry"):
            try:
                m._sync_overlay_geometry()
            except Exception:
                pass
        # v2.1.8 — the painted fallback takes over the instant the video
        # dies: force one repaint so the canvas never shows a stale frame.
        try:
            m.update()
        except Exception:
            pass

    def _on_video_frame(self, frame):
        if frame is None or not frame.isValid():
            return
        try:
            img = frame.toImage()
        except Exception:
            return
        if img is None or img.isNull():
            return
        self._frame_img = img
        self._frame_seq += 1
        self._scaled_img = None
        if self.isVisible():
            self.update()
        # v2.1.8 — keep the frosted footer glass "live": repaint the
        # manufacturer plate (with a fresh blur sample) every 10th frame
        # (~6 fps at 60 fps video) — cheap and always in sync.
        if self._frame_seq % 10 == 0:
            box = getattr(self.master, "manufacturer_box", None)
            if box is not None:
                try:
                    box.update()
                except Exception:
                    pass

    def _on_media_status(self, status):
        # loop fallback for players without setLoops()
        try:
            end = getattr(QMediaPlayer.MediaStatus, "EndOfMedia", None)
            if end is not None and status == end:
                self._player.setPosition(0)
                self._player.play()
        except Exception:
            pass

    def _on_player_error(self, *args):
        # Log loudly; only fatal (media) errors kill the background.
        err = args[0] if args else None
        err_str = args[1] if len(args) > 1 else ""
        try:
            err_name = str(err).split(".")[-1]
        except Exception:
            err_name = str(err)
        self._log("player error:", err_name, "|", err_str)
        if err_name in ("ResourceError", "FormatError", "AccessDeniedError"):
            self._log("fatal media error — deactivating video background")
            self._deactivate()
        # Anything else (e.g. a transient audio-device hiccup) is logged
        # and ignored: as long as frames keep arriving, the video stays on.

    # -------------------------------------------------- painting
    def _scaled_for_paint(self):
        """Widget-sized cache of the current frame. The 1920x1080 source is
        cropped ("cover fit") and rescaled only once per delivered frame —
        not on every repaint in between."""
        img = self._frame_img
        if img is None:
            return None
        dpr = self.devicePixelRatioF()
        key = (self._frame_seq, self.width(), self.height(), dpr)
        if self._scaled_key == key and self._scaled_img is not None:
            return self._scaled_img
        try:
            # cover fit: fill the widget, crop the excess of the source
            wa = self.width() / float(max(1, self.height()))
            fa = img.width() / float(max(1, img.height()))
            if fa > wa:      # source wider than the window -> crop sides
                cw = int(round(img.height() * wa))
                src = img.copy((img.width() - cw) // 2, 0, cw, img.height())
            else:            # source taller -> crop top/bottom
                ch = int(round(img.width() / wa))
                src = img.copy(0, (img.height() - ch) // 2, img.width(), ch)
            tw = max(1, int(self.width() * dpr))
            th = max(1, int(self.height() * dpr))
            scaled = src.scaled(
                tw, th, IGNORE_ASPECT,
                Qt.TransformationMode.FastTransformation
                if IS_PYQT6 else Qt.FastTransformation)
            scaled.setDevicePixelRatio(dpr)
            self._scaled_img = scaled
            self._scaled_key = key
            return self._scaled_img
        except Exception:
            return img

    def paintEvent(self, event):
        p = QPainter(self)
        r = self.rect()
        p.setRenderHint(QPainter.RenderHint.Antialiasing
                        if IS_PYQT6 else QPainter.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform
                        if IS_PYQT6 else QPainter.SmoothPixmapTransform)
        path = QPainterPath()
        path.addRoundedRect(QRectF(r), BACKGROUND_VIDEO_CORNER_RADIUS,
                            BACKGROUND_VIDEO_CORNER_RADIUS)
        p.setClipPath(path)

        img = self._scaled_for_paint()
        if img is None:
            # player warming up: keep the canvas at the base theme color
            try:
                p.fillRect(r, self.master.active_theme.bg_dark[0])
            except Exception:
                p.fillRect(r, QColor(1, 6, 18))
            p.end()
            return

        p.drawImage(0, 0, img)
        self._paint_grade(p, r)
        p.end()

    def _paint_grade(self, p, r):
        """Per-mod color grade: tint the video toward the active theme's
        hue with the Multiply + SoftLight blend modes (keep the clip's
        texture, shadows and contrast while shifting its color cast),
        plus optional desaturation / brightness tweaks. Applied on every
        paint, so theme transitions morph the background live."""
        if IS_PYQT6:
            ModeOver = QPainter.CompositionMode.CompositionMode_SourceOver
            try:
                ModeMult = QPainter.CompositionMode.CompositionMode_Multiply
            except Exception:
                ModeMult = ModeOver
            try:
                ModeSoft = QPainter.CompositionMode.CompositionMode_SoftLight
            except Exception:
                ModeSoft = ModeOver
        else:
            ModeOver = QPainter.CompositionMode_SourceOver
            ModeMult = QPainter.CompositionMode_Multiply
            ModeSoft = QPainter.CompositionMode_SoftLight
        try:
            theme = self.master.active_theme
            grade = video_grade_for_theme(theme)
            # v2.1.2 — the tint strength now comes from the theme's own
            # saturation (see video_grade_for_theme): the clip is BLACK &
            # WHITE, so EVERY chromatic theme must colour it — hue distance
            # from the old cyan base no longer decides visibility (that was
            # why some mods' video stayed grey). The user's colour-intensity
            # setting scales the whole grade.
            strength = float(grade.get("tint_strength", 0.0))
            strength *= float(getattr(self, "_color_intensity", 1.0))
            if strength > 0.01:
                h = theme.primary.hueF()
                if grade.get("hue_is_override"):
                    h = (h + float(grade.get("hue", 0.0)) / 360.0) % 1.0
                h = min(max(h, 0.0), 0.9999)
                tint = QColor.fromHsvF(h, 0.72, 0.95)
                if tint is not None:
                    tint.setAlphaF(0.46 * strength)
                    p.setCompositionMode(ModeMult)
                    p.fillRect(r, tint)
                deep = QColor.fromHsvF(h, 0.60, 0.72)
                if deep is not None:
                    deep.setAlphaF(0.34 * strength)
                    p.setCompositionMode(ModeSoft)
                    p.fillRect(r, deep)
                p.setCompositionMode(ModeOver)
            sat = float(grade.get("saturation", 1.0))
            if sat < 0.98:                       # desaturating themes
                g = QColor(128, 128, 128)
                g.setAlphaF(min(0.45, (1.0 - sat) * 3.0))
                p.fillRect(r, g)
            bright = float(grade.get("brightness", 1.0))
            if bright < 0.98:                    # manual overrides only
                d = QColor(0, 0, 0)
                d.setAlphaF(min(0.5, (1.0 - bright) * 1.6))
                p.fillRect(r, d)
            elif bright > 1.02:
                w = QColor(255, 255, 255)
                w.setAlphaF(min(0.35, (bright - 1.0) * 1.2))
                p.fillRect(r, w)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._scaled_img = None
        self._scaled_key = None
        self.update()


# -------------------------------------------------------------
# Main Application Entry Point
# -------------------------------------------------------------
if __name__ == "__main__":
    if "--package-smoke" in sys.argv:
        if not IS_PYQT6:
            raise RuntimeError("PyQt6 is unavailable in the packaged MyMods executable")
        if not callable(QApplication):
            raise RuntimeError("QApplication is unavailable in the packaged MyMods executable")
        print("Standalone MyMods package smoke test passed")
        sys.exit(0)

    app = QApplication(sys.argv)

    ltr = Qt.LayoutDirection.LeftToRight if IS_PYQT6 else Qt.LeftToRight
    app.setLayoutDirection(ltr)

    font = QFont("Segoe UI", 10)
    app.setFont(font)

    window = MasterCyberWindow()
    window.show()

    exec_fn = getattr(app, "exec", getattr(app, "exec_", None))
    sys.exit(exec_fn())
