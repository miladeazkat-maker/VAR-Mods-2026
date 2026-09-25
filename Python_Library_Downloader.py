"""
PES MODS • Python & Libraries Suite
A modern glassmorphic environment suite for PES modders and developers.
Features host environment bridge for PyInstaller EXEs, native pip streaming,
and real-time download & installation progress.
"""

import ctypes
import html.parser
import importlib
import importlib.metadata as metadata
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import messagebox

APP_TITLE = "PES MODS • Python & Libraries Suite"
PYTHON_ORG_URL = "https://www.python.org/downloads/"
PYTHON_WIN_URL = "https://www.python.org/downloads/windows/"
PYPI_JSON_URL = "https://pypi.org/pypi/{}/json"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# Required Packages: (pip_name, display_title, modding_role_tag)
REQUIRED_PACKAGES = [
    ("PyInstaller", "PyInstaller", "Compiler"),
    ("PyQt6", "PyQt6", "GUI Engine"),
    ("PyQt6-WebEngine", "PyQt6 WebEngine", "Chromium"),
    ("pymem", "Pymem", "Memory Tool"),
    ("numpy", "NumPy", "Numerics"),
    ("matplotlib", "Matplotlib", "Charts"),
    ("Pillow", "Pillow", "Images"),
    ("customtkinter", "CustomTkinter", "Themes"),
    ("keyboard", "Keyboard", "Hotkey/Input"),
    ("panda3d", "Panda3D", "3D Engine"),
    ("ursina", "Ursina", "Game Engine"),
]


# ============================================================================
# ADMIN ELEVATION & DIRECTORY LOCK (NO SYSTEM32 JUMP)
# ============================================================================

def get_app_dir():
    """Get absolute path to current application directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = get_app_dir()
    return os.path.join(base_path, relative_path)


def ensure_admin():
    """Ensure Administrator privileges without jumping to System32."""
    if os.name != "nt":
        return

    app_dir = get_app_dir()
    os.chdir(str(app_dir))

    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if not is_admin:
        if getattr(sys, 'frozen', False):
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv[1:])
        else:
            exe = sys.executable
            params = " ".join(f'"{a}"' for a in sys.argv)

        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, str(app_dir), 1
        )
        if ret > 32:
            sys.exit(0)


def get_real_python_exe():
    """Locate real python.exe on the host system."""
    if not getattr(sys, 'frozen', False):
        return sys.executable

    try:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        r = subprocess.run(
            ["py", "-3", "-c", "import sys; print(sys.executable)"],
            capture_output=True, text=True, creationflags=flags, timeout=4
        )
        if r.returncode == 0 and r.stdout.strip():
            p = r.stdout.strip()
            if os.path.exists(p):
                return p
    except Exception:
        pass

    py_path = shutil.which("python")
    if py_path and not py_path.lower().endswith(os.path.basename(sys.executable).lower()):
        return py_path

    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        base_py = Path(local_app) / "Programs" / "Python"
        if base_py.exists():
            candidates = sorted(base_py.glob("Python3*/python.exe"), reverse=True)
            if candidates:
                return str(candidates[0])

    for env_var in ["ProgramFiles", "ProgramFiles(x86)"]:
        pf = os.environ.get(env_var, "")
        if pf:
            base_py = Path(pf) / "Python"
            if base_py.exists():
                candidates = sorted(base_py.glob("Python3*/python.exe"), reverse=True)
                if candidates:
                    return str(candidates[0])

    return "python"


# ============================================================================
# HOST ENVIRONMENT DISCOVERY (SOLVES FROZEN EXE NOT SEEING LIBRARIES)
# ============================================================================

def inject_host_site_packages():
    """Inject host Python site-packages into sys.path so the frozen EXE sees packages."""
    try:
        py_bin = get_real_python_exe()
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = [py_bin, "-c", "import site, sys; print('\\n'.join(sys.path + site.getsitepackages() + [site.getusersitepackages()]))"]
        res = subprocess.run(cmd, capture_output=True, text=True, creationflags=flags, timeout=5)
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                p = line.strip()
                if p and os.path.isdir(p) and p not in sys.path:
                    sys.path.append(p)
            importlib.invalidate_caches()
    except Exception:
        pass


def get_host_installed_packages():
    """
    Directly query the host Python for all installed packages and versions.
    Works flawlessly inside standalone PyInstaller EXE files.
    """
    py_bin = get_real_python_exe()
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    # 1. Fast metadata distributions probe
    script = (
        "import importlib.metadata as m, json; "
        "d_map = {}; "
        "[d_map.update({d.metadata['Name'].lower(): d.version}) for d in m.distributions() if d.metadata and 'Name' in d.metadata]; "
        "print(json.dumps(d_map))"
    )
    try:
        r = subprocess.run([py_bin, "-c", script], capture_output=True, text=True, creationflags=flags, timeout=6)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip())
    except Exception:
        pass

    # 2. Pip fallback probe
    try:
        r = subprocess.run([py_bin, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, creationflags=flags, timeout=7)
        if r.returncode == 0 and r.stdout.strip():
            data = json.loads(r.stdout.strip())
            return {item["name"].lower(): item["version"] for item in data if "name" in item and "version" in item}
    except Exception:
        pass

    return {}


# ============================================================================
# COLOR MATH & ARCHITECTURE HELPERS
# ============================================================================

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#{:02x}{:02x}{:02x}".format(
        max(0, min(255, int(rgb[0]))),
        max(0, min(255, int(rgb[1]))),
        max(0, min(255, int(rgb[2])))
    )


def lerp_color(c1, c2, t):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    return rgb_to_hex((r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t))


def get_windows_arch():
    m = platform.machine().upper()
    if "ARM64" in m or "AARCH64" in m:
        return "arm64"
    if "AMD64" in m or "X86_64" in m:
        return "amd64"
    return "win32"


def version_tuple(v_str):
    nums = re.findall(r"\d+", str(v_str))
    return tuple(int(x) for x in nums[:6]) if nums else (0,)


def compare_versions(installed, latest):
    try:
        from packaging.version import Version
        a, b = Version(installed), Version(latest)
        return (a > b) - (a < b)
    except Exception:
        a, b = version_tuple(installed), version_tuple(latest)
        return (a > b) - (a < b)


def format_bytes(b):
    if b is None or b <= 0:
        return "—"
    for unit in ["B", "KB", "MB", "GB"]:
        if b < 1024.0:
            return f"{b:.1f} {unit}" if unit != "B" else f"{int(b)} B"
        b /= 1024.0
    return f"{b:.1f} GB"


def run_process(command):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    startup = None
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
        startupinfo=startup,
    )


def check_url_exists(url):
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Range": "bytes=0-10"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status in (200, 206):
                return True
    except Exception:
        pass
    return False


# ============================================================================
# METADATA & PYTHON INSTALLER DOWNLOADER
# ============================================================================

def fetch_latest_python_installer():
    arch = get_windows_arch()

    def make_url(ver):
        fname = f"python-{ver}.exe" if arch == "win32" else f"python-{ver}-{arch}.exe"
        return f"https://www.python.org/ftp/python/{ver}/{fname}"

    try:
        req = urllib.request.Request(PYTHON_ORG_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html_text = resp.read().decode("utf-8", errors="ignore")
        match = re.search(r'href=["\'](https?://www\.python\.org/ftp/python/(\d+\.\d+\.\d+)/python-\2[^"\']*\.exe)["\']', html_text)
        if match:
            ver = match.group(2)
            cand_url = make_url(ver)
            if check_url_exists(cand_url):
                return ver, cand_url
    except Exception:
        pass

    try:
        req = urllib.request.Request("https://endoflife.date/api/python.json", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                for item in data:
                    cand_ver = item.get("latest")
                    if cand_ver:
                        cand_url = make_url(cand_ver)
                        if check_url_exists(cand_url):
                            return cand_ver, cand_url
    except Exception:
        pass

    cur = platform.python_version()
    return cur, make_url(cur)


def download_file_monitored(url, destination, progress_cb=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        total = int(response.headers.get("Content-Length") or 0)
        done = 0
        start_time = time.time()
        last_time = start_time
        last_bytes = 0
        speed = 0.0

        with open(destination, "wb") as out:
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                now = time.time()
                dt = now - last_time
                if dt >= 0.25:
                    speed = (done - last_bytes) / dt
                    last_time = now
                    last_bytes = done
                    if progress_cb:
                        pct = (done / total * 100.0) if total > 0 else 0.0
                        progress_cb(done, total, pct, speed)

        if progress_cb:
            progress_cb(done, total, 100.0, speed)


def get_installed_package_size(pkg_name):
    try:
        importlib.invalidate_caches()
        dist = metadata.distribution(pkg_name)
        if not dist.files:
            return None
        total = 0
        count = 0
        for f in dist.files:
            try:
                p = dist.locate_file(f)
                if p.is_file():
                    total += p.stat().st_size
                count += 1
                if count > 2500:
                    break
            except Exception:
                continue
        return total if total > 0 else None
    except Exception:
        return None


def fetch_pypi_metadata(pkg_name):
    req = urllib.request.Request(PYPI_JSON_URL.format(pkg_name), headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=12) as response:
        data = json.loads(response.read().decode("utf-8"))
        info = data.get("info", {})
        ver = info.get("version", None)
        size = None
        urls = data.get("urls", [])
        if urls:
            size = urls[0].get("size")
        return ver, size


# ============================================================================
# SMOOTH GLASS BUTTON & SPINNER
# ============================================================================

class GlassButton(tk.Canvas):
    THEMES = {
        "primary": {
            "top": "#0284c7", "bottom": "#0369a1", "border": "#38bdf8", "rim": "#7dd3fc", "text": "#ffffff",
            "h_top": "#0ea5e9", "h_bottom": "#0284c7", "h_border": "#bae6fd",
            "a_top": "#0369a1", "a_bottom": "#075985",
            "d_top": "#16202c", "d_bottom": "#0f1722", "d_border": "#1e2b3b", "d_text": "#475569",
        },
        "secondary": {
            "top": "#1e293b", "bottom": "#111827", "border": "#2d3c52", "rim": "#475569", "text": "#f1f5f9",
            "h_top": "#29374d", "h_bottom": "#172133", "h_border": "#475c7a",
            "a_top": "#111827", "a_bottom": "#0b0f19",
            "d_top": "#131a24", "d_bottom": "#0d131c", "d_border": "#192230", "d_text": "#475569",
        },
        "warning": {
            "top": "#d97706", "bottom": "#92400e", "border": "#f59e0b", "rim": "#fef3c7", "text": "#ffffff",
            "h_top": "#f59e0b", "h_bottom": "#b45309", "h_border": "#fde68a",
            "a_top": "#92400e", "a_bottom": "#78350f",
            "d_top": "#261a10", "d_bottom": "#1c130c", "d_border": "#332215", "d_text": "#594433",
        },
        "success": {
            "top": "#059669", "bottom": "#065f46", "border": "#10b981", "rim": "#a7f3d0", "text": "#ffffff",
            "h_top": "#10b981", "h_bottom": "#047857", "h_border": "#6ee7b7",
            "a_top": "#047857", "a_bottom": "#064e3b",
            "d_top": "#13241d", "d_bottom": "#0e1a15", "d_border": "#1c3328", "d_text": "#3d5c4e",
        },
        "danger": {
            "top": "#e11d48", "bottom": "#9f1239", "border": "#f43f5e", "rim": "#ffe4e6", "text": "#ffffff",
            "h_top": "#f43f5e", "h_bottom": "#be123c", "h_border": "#fecdd3",
            "a_top": "#be123c", "a_bottom": "#881337",
            "d_top": "#291319", "d_bottom": "#1f0e13", "d_border": "#3b1a23", "d_text": "#5c3d45",
        },
    }

    def __init__(self, parent, text="", command=None, kind="secondary",
                 width=92, height=28, radius=7, font=("Segoe UI", 9, "bold"),
                 bg=None, **kwargs):
        bg_val = bg if bg is not None else (parent.cget("bg") if hasattr(parent, "cget") else "#0b0f17")
        super().__init__(parent, width=width, height=height, bg=bg_val, bd=0,
                         highlightthickness=0, cursor="hand2", **kwargs)
        self.btn_text = text
        self.command = command
        self.kind = kind
        self.w = width
        self.h = height
        self.r = radius
        self.font = font
        self.state_str = "normal"
        self.is_hover = False
        self.is_down = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)

        self.render()

    def _on_enter(self, _):
        if self.state_str != "disabled":
            self.is_hover = True
            self.render()

    def _on_leave(self, _):
        self.is_hover = False
        self.is_down = False
        self.render()

    def _on_press(self, _):
        if self.state_str != "disabled":
            self.is_down = True
            self.render()

    def _on_release(self, _):
        if self.state_str != "disabled" and self.is_down:
            self.is_down = False
            self.render()
            if self.command:
                self.command()

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.btn_text = str(kwargs.pop("text"))
        if "state" in kwargs:
            self.state_str = str(kwargs.pop("state"))
            super().configure(cursor="hand2" if self.state_str == "normal" else "arrow")
        if "kind" in kwargs:
            self.kind = str(kwargs.pop("kind"))
        if "command" in kwargs:
            self.command = kwargs.pop("command")
        if "width" in kwargs:
            self.w = int(kwargs.pop("width"))
            super().configure(width=self.w)
        if kwargs:
            super().configure(**kwargs)
        self.render()

    config = configure

    def cget(self, key):
        if key == "text":
            return self.btn_text
        if key == "state":
            return self.state_str
        return super().cget(key)

    def __getitem__(self, item):
        return self.cget(item)

    def render(self):
        self.delete("all")
        theme = self.THEMES.get(self.kind, self.THEMES["secondary"])

        if self.state_str == "disabled":
            t_col, b_col, border, text_col = theme["d_top"], theme["d_bottom"], theme["d_border"], theme["d_text"]
            rim = None
        elif self.is_down:
            t_col, b_col, border, text_col = theme["a_top"], theme["a_bottom"], theme["border"], theme["text"]
            rim = None
        elif self.is_hover:
            t_col, b_col, border, text_col = theme["h_top"], theme["h_bottom"], theme["h_border"], theme["text"]
            rim = theme["rim"]
        else:
            t_col, b_col, border, text_col = theme["top"], theme["bottom"], theme["border"], theme["text"]
            rim = theme["rim"]

        w, h, r = self.w, self.h, self.r
        x1, y1, x2, y2 = 1, 1, w - 2, h - 2

        points = [
            x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r, x2, y1 + r, x2, y2 - r,
            x2, y2 - r, x2, y2, x2 - r, y2, x2 - r, y2,
            x1 + r, y2, x1 + r, y2, x1, y2, x1, y2 - r,
            x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1
        ]
        self.create_polygon(points, smooth=True, fill=b_col, outline=border, width=1)

        if self.state_str != "disabled":
            h_span = max(1, y2 - y1 - 2)
            for y in range(int(y1 + 1), int(y2)):
                t = (y - (y1 + 1)) / h_span
                line_col = lerp_color(t_col, b_col, t)
                inset = 0
                if y < y1 + r:
                    dy = (y1 + r) - y
                    diff = r * r - dy * dy
                    inset = int(r - (diff ** 0.5)) if diff > 0 else 0
                elif y > y2 - r:
                    dy = y - (y2 - r)
                    diff = r * r - dy * dy
                    inset = int(r - (diff ** 0.5)) if diff > 0 else 0
                self.create_line(x1 + 1 + inset, y, x2 - 1 - inset, y, fill=line_col, width=1)

            if rim:
                self.create_line(x1 + r + 1, y1 + 1, x2 - r - 1, y1 + 1, fill=rim, width=1)

        y_offset = 1 if self.is_down else 0
        self.create_text(w // 2, (h // 2) + y_offset, text=self.btn_text,
                         fill=text_col, font=self.font)


class CanvasSpinner(tk.Canvas):
    def __init__(self, parent, size=18, color="#38bdf8", track="#162030", bg=None, **kwargs):
        bg_val = bg if bg is not None else (parent.cget("bg") if hasattr(parent, "cget") else "#0f1522")
        super().__init__(parent, width=size, height=size, bg=bg_val, bd=0, highlightthickness=0, **kwargs)
        self.size = size
        self.color = color
        self.track = track
        self.angle = 0
        self.running = False
        self._timer = None

    def start(self):
        if not self.running:
            self.running = True
            self._tick()

    def stop(self):
        self.running = False
        if self._timer:
            self.after_cancel(self._timer)
            self._timer = None
        self.delete("all")

    def _tick(self):
        if not self.running:
            return
        self.delete("all")
        pad = 2
        s = self.size
        self.create_oval(pad, pad, s - pad, s - pad, outline=self.track, width=2)
        self.create_arc(pad, pad, s - pad, s - pad, start=self.angle, extent=110,
                        style="arc", outline=self.color, width=2)
        self.angle = (self.angle + 16) % 360
        self._timer = self.after(35, self._tick)


# ============================================================================
# MAIN SUITE APPLICATION
# ============================================================================

class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.configure(bg="#080c14")

        self.setup_icon()
        inject_host_site_packages()

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        win_w = min(840, max(680, int(sw * 0.48)))
        win_h = min(900, max(680, int(sh * 0.90)))
        self.root.geometry(f"{win_w}x{win_h}")

        # Theme Colors
        self.bg = "#080c14"
        self.card_bg = "#0f1522"
        self.card_hover = "#131a28"
        self.border = "#1c2638"
        self.text = "#f8fafc"
        self.muted = "#94a3b8"
        self.submuted = "#64748b"
        self.cyan = "#38bdf8"
        self.green = "#10b981"
        self.amber = "#f59e0b"
        self.red = "#f43f5e"

        # Internal State
        self.events_queue = []
        self.queue_lock = threading.Lock()
        self.busy = False
        self.python_target_ver = None
        self.python_target_url = None
        self.rows = {}

        self.build_ui()
        self.root.after(100, self.startup)
        self.root.after(60, self.process_queue)

    def setup_icon(self):
        icon_file = resource_path("library-icon.png")
        if os.path.exists(icon_file):
            try:
                self.icon_photo = tk.PhotoImage(file=icon_file)
                self.root.iconphoto(True, self.icon_photo)
            except Exception as e:
                print("Could not set icon:", e)

    def build_ui(self):
        self.main_canvas = tk.Canvas(self.root, bg=self.bg, bd=0, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.content_frame = tk.Frame(self.main_canvas, bg=self.bg)

        self.content_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        self.canvas_win = self.main_canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.main_canvas.bind(
            "<Configure>",
            lambda e: self.main_canvas.itemconfig(self.canvas_win, width=e.width)
        )
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        container = tk.Frame(self.content_frame, bg=self.bg)
        container.pack(fill="both", expand=True, padx=18, pady=12)

        # 1. Header Section
        header = tk.Frame(container, bg=self.bg)
        header.pack(fill="x", pady=(0, 10))

        head_left = tk.Frame(header, bg=self.bg)
        head_left.pack(side="left")

        title_box = tk.Frame(head_left, bg=self.bg)
        title_box.pack(anchor="w")
        tk.Label(title_box, text="PES MODS", bg=self.bg, fg=self.cyan,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(title_box, text=" • Environment Suite", bg=self.bg, fg=self.text,
                 font=("Segoe UI", 16, "bold")).pack(side="left")

        tk.Label(head_left, text="Automated Python runtime, Pip & modding libraries manager",
                 bg=self.bg, fg=self.muted, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 0))

        self.status_badge = tk.Label(
            header, text="READY", bg="#0a2a1d", fg=self.green,
            font=("Segoe UI", 9, "bold"), padx=11, pady=4, relief="flat"
        )
        self.status_badge.pack(side="right", pady=4)

        # 2. Hero Card: Automatic Download & Install
        self.hero = tk.Frame(container, bg="#0d233a", highlightthickness=1,
                             highlightbackground="#1d4ed8", padx=14, pady=10, cursor="hand2")
        self.hero.pack(fill="x", pady=(0, 10))
        self.hero.bind("<Button-1>", lambda _: self.quick_install())

        hero_left = tk.Frame(self.hero, bg="#0d233a")
        hero_left.pack(side="left", fill="x", expand=True)
        hero_left.bind("<Button-1>", lambda _: self.quick_install())

        hero_title_box = tk.Frame(hero_left, bg="#0d233a")
        hero_title_box.pack(anchor="w")
        hero_title_box.bind("<Button-1>", lambda _: self.quick_install())

        tk.Label(hero_title_box, text="Automatic Download & Install", bg="#0d233a",
                 fg="#ffffff", font=("Segoe UI", 9, "bold")).pack(side="left")

        self.hero_size_badge = tk.Label(
            hero_title_box, text="Ready", bg="#172e47", fg="#93c5fd",
            font=("Segoe UI", 9, "bold"), padx=8, pady=2
        )
        self.hero_size_badge.pack(side="left", padx=(10, 0))
        self.hero_size_badge.bind("<Button-1>", lambda _: self.quick_install())

        hero_desc = tk.Label(hero_left,
                             text="Automatically update Python runtime, pip, and all modding libraries via native pip",
                             bg="#0d233a", fg="#93c5fd", font=("Segoe UI", 9))
        hero_desc.pack(anchor="w", pady=(2, 0))
        hero_desc.bind("<Button-1>", lambda _: self.quick_install())

        self.hero_btn = GlassButton(self.hero, text="Install All", kind="primary",
                                    width=96, height=30, bg="#0d233a", command=self.quick_install)
        self.hero_btn.pack(side="right")

        # 3. Python Runtime Card
        py_card = tk.Frame(container, bg=self.card_bg, highlightthickness=1,
                           highlightbackground=self.border, padx=14, pady=10)
        py_card.pack(fill="x", pady=(0, 10))

        py_top = tk.Frame(py_card, bg=self.card_bg)
        py_top.pack(fill="x")

        tk.Label(py_top, text="CPython Runtime", bg=self.card_bg, fg=self.text,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        self.py_spinner = CanvasSpinner(py_top, size=16, color=self.cyan, bg=self.card_bg)
        self.py_spinner.pack(side="left", padx=(8, 0))

        self.py_badge = tk.Label(py_top, text="CHECKING", bg="#192333", fg=self.muted,
                                 font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        self.py_badge.pack(side="right")

        self.py_main_info = tk.Label(py_card, text="Inspecting installed Python interpreter...",
                                     bg=self.card_bg, fg=self.text, font=("Segoe UI", 9, "bold"), anchor="w")
        self.py_main_info.pack(fill="x", pady=(5, 1))

        self.py_sub_info = tk.Label(py_card, text="Verifying remote releases from python.org",
                                    bg=self.card_bg, fg=self.muted, font=("Segoe UI", 9), anchor="w")
        self.py_sub_info.pack(fill="x")

        py_actions = tk.Frame(py_card, bg=self.card_bg)
        py_actions.pack(fill="x", pady=(8, 0))

        self.py_action_btn = GlassButton(py_actions, text="Checking...", kind="secondary",
                                         width=130, height=28, bg=self.card_bg, command=self.python_action)
        self.py_action_btn.pack(side="left")

        self.py_refresh_btn = GlassButton(py_actions, text="↻ Refresh", kind="secondary",
                                          width=85, height=28, bg=self.card_bg, command=self.check_python)
        self.py_refresh_btn.pack(side="left", padx=(8, 0))

        # 4. LIVE ACTIVITY & PROGRESS PANEL
        self.activity_card = tk.Frame(container, bg="#0c121e", highlightthickness=1,
                                      highlightbackground=self.border, padx=14, pady=10)
        self.activity_card.pack(fill="x", pady=(0, 10))

        act_top = tk.Frame(self.activity_card, bg="#0c121e")
        act_top.pack(fill="x")

        self.act_title = tk.Label(act_top, text="Task Monitor: Idle", bg="#0c121e",
                                  fg=self.cyan, font=("Segoe UI", 9, "bold"))
        self.act_title.pack(side="left")

        self.act_speed_badge = tk.Label(act_top, text="Engine: Pip Ready", bg="#162235",
                                        fg="#93c5fd", font=("Segoe UI", 9, "bold"), padx=8, pady=2)
        self.act_speed_badge.pack(side="right")

        # Progress Status
        self.inst_label = tk.Label(self.activity_card, text="Status: Ready",
                                   bg="#0c121e", fg=self.muted, font=("Segoe UI", 9), anchor="w")
        self.inst_label.pack(fill="x", pady=(6, 2))

        self.inst_bar_bg = tk.Frame(self.activity_card, bg="#1a2333", height=6)
        self.inst_bar_bg.pack(fill="x")
        self.inst_bar_fill = tk.Frame(self.inst_bar_bg, bg=self.green, height=6)
        self.inst_bar_fill.place(x=0, y=0, relheight=1, relwidth=0)

        # 5. Compact 2-Column Libraries Grid
        lib_card = tk.Frame(container, bg=self.card_bg, highlightthickness=1,
                            highlightbackground=self.border, padx=12, pady=10)
        lib_card.pack(fill="both", expand=True)

        lib_header = tk.Frame(lib_card, bg=self.card_bg)
        lib_header.pack(fill="x", pady=(0, 8))

        tk.Label(lib_header, text="Required Modding Libraries", bg=self.card_bg, fg=self.text,
                 font=("Segoe UI", 9, "bold")).pack(side="left")

        self.lib_spinner = CanvasSpinner(lib_header, size=16, color=self.cyan, bg=self.card_bg)
        self.lib_spinner.pack(side="left", padx=(8, 0))

        self.lib_refresh_btn = GlassButton(lib_header, text="↻ Recheck All", kind="secondary",
                                           width=105, height=26, bg=self.card_bg, command=self.check_libraries)
        self.lib_refresh_btn.pack(side="right")

        grid_frame = tk.Frame(lib_card, bg=self.card_bg)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.grid_columnconfigure(0, weight=1, uniform="lib_col")
        grid_frame.grid_columnconfigure(1, weight=1, uniform="lib_col")

        for idx, (pkg_name, label, tag) in enumerate(REQUIRED_PACKAGES):
            r, c = divmod(idx, 2)
            self.create_package_tile(grid_frame, pkg_name, label, tag, r, c)

        # 6. Footer & Console Drawer
        footer = tk.Frame(container, bg="#0d131d", highlightthickness=1,
                          highlightbackground=self.border, padx=10, pady=6)
        footer.pack(fill="x", pady=(10, 0))

        self.footer_dot = tk.Label(footer, text="●", bg="#0d131d", fg=self.green, font=("Segoe UI", 9))
        self.footer_dot.pack(side="left")

        self.footer_msg = tk.Label(footer, text="System Ready.", bg="#0d131d",
                                   fg=self.muted, font=("Segoe UI", 9), anchor="w")
        self.footer_msg.pack(side="left", fill="x", expand=True, padx=(6, 0))

        self.console_btn = GlassButton(footer, text="Console Logs", kind="secondary",
                                       width=100, height=24, bg="#0d131d", command=self.toggle_console)
        self.console_btn.pack(side="right")

        self.console_frame = tk.Frame(container, bg="#06090f", highlightthickness=1,
                                      highlightbackground=self.border, padx=8, pady=8)
        self.console_text = tk.Text(self.console_frame, height=6, bg="#06090f", fg="#cbd5e1",
                                    insertbackground="white", relief="flat", bd=0,
                                    font=("Consolas", 9), wrap="word")
        self.console_text.pack(fill="both", expand=True)
        self.console_text.configure(state="disabled")

    def create_package_tile(self, parent, pkg_name, label, tag, row, col):
        card = tk.Frame(parent, bg=self.card_hover, highlightthickness=1,
                        highlightbackground=self.border, padx=10, pady=6)
        card.grid(row=row, column=col, sticky="nsew",
                  padx=(0 if col == 0 else 4, 4 if col == 0 else 0), pady=3)

        left = tk.Frame(card, bg=self.card_hover)
        left.pack(side="left", fill="both", expand=True)

        top_line = tk.Frame(left, bg=self.card_hover)
        top_line.pack(fill="x")

        name_lbl = tk.Label(top_line, text=label, bg=self.card_hover, fg=self.text,
                            font=("Segoe UI", 9, "bold"))
        name_lbl.pack(side="left")

        tag_lbl = tk.Label(top_line, text=tag, bg="#1a2536", fg=self.cyan,
                           font=("Segoe UI", 9, "bold"), padx=5, pady=1)
        tag_lbl.pack(side="left", padx=(6, 0))

        bot_line = tk.Frame(left, bg=self.card_hover)
        bot_line.pack(fill="x", pady=(2, 0))

        spinner = CanvasSpinner(bot_line, size=14, color=self.cyan, bg=self.card_hover)
        spinner.pack(side="left", padx=(0, 4))
        spinner.start()

        ver_lbl = tk.Label(bot_line, text="Verifying...", bg=self.card_hover,
                           fg=self.muted, font=("Segoe UI", 9), anchor="w")
        ver_lbl.pack(side="left")

        size_lbl = tk.Label(bot_line, text="", bg=self.card_hover,
                            fg=self.submuted, font=("Segoe UI", 9), anchor="w")
        size_lbl.pack(side="left", padx=(6, 0))

        btn = GlassButton(card, text="Checking...", kind="secondary",
                          width=88, height=27, bg=self.card_hover,
                          command=lambda p=pkg_name: self.package_action(p))
        btn.pack(side="right", padx=(6, 0))

        self.rows[pkg_name] = {
            "name": pkg_name,
            "label": label,
            "tag": tag,
            "spinner": spinner,
            "ver_label": ver_lbl,
            "size_label": size_lbl,
            "button": btn,
            "installed_ver": None,
            "latest_ver": None,
            "remote_size": None,
        }

    def _on_mousewheel(self, event):
        if self.main_canvas.winfo_exists():
            self.main_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def post(self, fn, *args):
        with self.queue_lock:
            self.events_queue.append((fn, args))

    def process_queue(self):
        with self.queue_lock:
            items = self.events_queue[:]
            self.events_queue.clear()
        for fn, args in items:
            try:
                fn(*args)
            except Exception as e:
                print("UI Event Error:", e)
        self.root.after(60, self.process_queue)

    def log(self, text, level="INFO"):
        time_str = datetime.now().strftime("%H:%M:%S")
        line = f"[{time_str}] [{level}] {text}\n"
        self.footer_msg.config(text=text)

        self.console_text.configure(state="normal")
        self.console_text.insert("end", line)
        self.console_text.see("end")
        self.console_text.configure(state="disabled")

    def toggle_console(self):
        if self.console_frame.winfo_ismapped():
            self.console_frame.pack_forget()
            self.console_btn.configure(text="Console Logs")
        else:
            self.console_frame.pack(fill="x", pady=(8, 0))
            self.console_btn.configure(text="Hide Console")

    def set_inst_progress(self, percent, text=None):
        pct = max(0.0, min(100.0, float(percent)))
        self.inst_bar_fill.place_configure(relwidth=pct / 100.0)
        if text:
            self.inst_label.config(text=text)

    def startup(self):
        self.log("Initializing environment diagnostics...")
        self.check_python()
        self.root.after(200, self.check_libraries)

    def check_python(self):
        self.py_spinner.start()
        self.py_badge.config(text="CHECKING", bg="#192333", fg=self.muted)
        self.py_action_btn.configure(text="Checking...", state="disabled", kind="secondary")
        self.py_refresh_btn.configure(state="disabled")

        def worker():
            installed = platform.python_version()
            try:
                latest, url = fetch_latest_python_installer()
                self.post(self.python_checked, installed, latest, url, None)
            except Exception as exc:
                self.post(self.python_checked, installed, None, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def python_checked(self, installed, latest, url, error):
        self.py_spinner.stop()
        self.py_refresh_btn.configure(state="normal")

        if error or not latest:
            self.py_badge.config(text="OFFLINE", bg="#331c1f", fg=self.red)
            self.py_main_info.config(text=f"Python {installed} Detected", fg=self.amber)
            self.py_sub_info.config(text=f"Unable to query python.org: {error or 'Check connection'}")
            self.py_action_btn.configure(text="Retry Detection", state="normal", kind="secondary")
            self.log(f"Python check could not connect to python.org: {error}", "WARN")
            return

        self.python_target_ver = latest
        self.python_target_url = url

        cmp = compare_versions(installed, latest)
        if cmp < 0:
            self.py_badge.config(text="UPDATE AVAILABLE", bg="#382914", fg=self.amber)
            self.py_main_info.config(text=f"Python Update Available: {installed} → {latest}", fg=self.amber)
            self.py_sub_info.config(text=f"Official Windows Installer verified ({get_windows_arch().upper()})")
            self.py_action_btn.configure(text="Update Python", state="normal", kind="warning")
            self.log(f"Python update available: {installed} -> {latest}")
        elif cmp == 0:
            self.py_badge.config(text="UP TO DATE", bg="#0a2a1d", fg=self.green)
            self.py_main_info.config(text=f"Python {installed} • Current Stable Release", fg=self.green)
            self.py_sub_info.config(text="CPython interpreter is up to date and optimal.")
            self.py_action_btn.configure(text="Up to Date", state="disabled", kind="secondary")
            self.log(f"Python {installed} is up to date.")
        else:
            self.py_badge.config(text="NEWER / DEV", bg="#0a2a1d", fg=self.cyan)
            self.py_main_info.config(text=f"Python {installed} (Preview / Newer)", fg=self.cyan)
            self.py_sub_info.config(text=f"Current stable is {latest}. No downgrade needed.")
            self.py_action_btn.configure(text="Up to Date", state="disabled", kind="secondary")

    def python_action(self):
        if self.busy:
            return
        self.install_python()

    def install_python(self):
        self.busy = True
        self.status_badge.config(text="WORKING", bg="#382914", fg=self.amber)
        self.py_action_btn.configure(text="Installing...", state="disabled", kind="secondary")
        self.act_title.config(text="Task Monitor: Installing CPython Runtime...")

        cache_dir = Path.home() / "Downloads" / "PES_MODS_Python"
        cache_dir.mkdir(parents=True, exist_ok=True)

        def worker():
            try:
                latest, url = self.python_target_ver, self.python_target_url
                if not latest or not url:
                    latest, url = fetch_latest_python_installer()

                installer_path = cache_dir / Path(url).name
                self.post(self.log, f"Downloading Python {latest} installer...")

                def dl_callback(done, total, pct, speed):
                    txt = f"Downloading Python {latest} ({format_bytes(done)} / {format_bytes(total)} - {pct:.1f}%)"
                    self.post(self.set_inst_progress, int(pct * 0.5), txt)

                download_file_monitored(url, installer_path, dl_callback)

                self.post(self.set_inst_progress, 60, "Executing silent CPython installation...")
                self.post(self.log, "Executing automatic silent CPython installation...")

                res = run_process([
                    str(installer_path), "/quiet", "InstallAllUsers=0", "PrependPath=1",
                    "Include_pip=1", "Include_launcher=1", "Include_test=0", "SimpleInstall=0"
                ])
                if res.returncode not in (0, 3010):
                    err_msg = res.stderr.strip() or res.stdout.strip() or f"Installer exit code {res.returncode}"
                    raise RuntimeError(err_msg)

                inject_host_site_packages()
                self.post(self.set_inst_progress, 100, "Python installation completed (100%)")
                self.post(self.python_done, True, f"Python {latest} successfully installed/updated.")
            except Exception as e:
                self.post(self.python_done, False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def python_done(self, ok, msg):
        self.busy = False
        self.status_badge.config(text="READY", bg="#0a2a1d", fg=self.green)
        self.log(msg, "INFO" if ok else "ERROR")
        self.act_title.config(text="Task Monitor: Idle")
        if ok:
            messagebox.showinfo("Python Installer", msg)
            self.check_python()
            self.check_libraries()
        else:
            messagebox.showerror("Installation Failed", msg)
            self.py_action_btn.configure(text="Retry", state="normal", kind="warning")

    # ------------------------------------------------------------------------
    # NATIVE PIP INSTALLATION (RELIABLE & HOST BRIDGED)
    # ------------------------------------------------------------------------

    def check_libraries(self):
        self.lib_spinner.start()
        self.lib_refresh_btn.configure(state="disabled")
        self.log("Inspecting host Python packages and querying PyPI...")

        for row in self.rows.values():
            row["spinner"].start()
            row["ver_label"].config(text="Verifying...", fg=self.muted)
            row["size_label"].config(text="")
            row["button"].configure(text="Checking...", state="disabled", kind="secondary")

        def worker():
            # Bridge directly into the host Python's package index
            host_installed = get_host_installed_packages()

            results = []
            with ThreadPoolExecutor(max_workers=6) as pool:
                def inspect_single(pkg_name):
                    importlib.invalidate_caches()
                    # 1. First consult host packages (Solves frozen EXE blind-spot)
                    inst_ver = host_installed.get(pkg_name.lower())

                    # 2. Fallback to direct metadata search
                    if not inst_ver:
                        try:
                            inst_ver = metadata.version(pkg_name)
                        except Exception:
                            pass

                    inst_size = get_installed_package_size(pkg_name) if inst_ver else None
                    remote_ver, remote_size = None, None
                    err = None

                    try:
                        remote_ver, remote_size = fetch_pypi_metadata(pkg_name)
                    except Exception as exc:
                        err = str(exc)

                    return pkg_name, inst_ver, remote_ver, inst_size, remote_size, err

                futures = [pool.submit(inspect_single, name) for name, _, _ in REQUIRED_PACKAGES]
                for f in as_completed(futures):
                    results.append(f.result())

            self.post(self.libraries_checked, results)

        threading.Thread(target=worker, daemon=True).start()

    def libraries_checked(self, results):
        self.lib_spinner.stop()
        self.lib_refresh_btn.configure(state="normal")

        for pkg_name, inst_ver, latest_ver, inst_sz, remote_sz, err in results:
            row = self.rows[pkg_name]
            row["spinner"].stop()
            row["installed_ver"] = inst_ver
            row["latest_ver"] = latest_ver
            row["remote_size"] = remote_sz

            if inst_sz:
                row["size_label"].config(text=f"• Disk: {format_bytes(inst_sz)}")
            elif remote_sz:
                row["size_label"].config(text=f"• PyPI: {format_bytes(remote_sz)}")
            else:
                row["size_label"].config(text="")

            if not inst_ver:
                row["ver_label"].config(text=f"Not Installed ({latest_ver or '?'})", fg=self.red)
                row["button"].configure(text="Install", state="normal", kind="primary")
            elif latest_ver and compare_versions(inst_ver, latest_ver) < 0:
                row["ver_label"].config(text=f"{inst_ver} → {latest_ver}", fg=self.amber)
                row["button"].configure(text="Update", state="normal", kind="warning")
            elif err:
                row["ver_label"].config(text=f"v{inst_ver} (Check error)", fg=self.muted)
                row["button"].configure(text="Reinstall", state="normal", kind="secondary")
            else:
                row["ver_label"].config(text=f"v{inst_ver} • Ready", fg=self.green)
                row["button"].configure(text="Up to Date", state="disabled", kind="secondary")

        self.log("Library status synchronization complete.")

    def package_action(self, pkg_name):
        """Native, direct pip execution with live stream output."""
        if self.busy:
            return
        row = self.rows[pkg_name]
        action = row["button"].cget("text")
        if action not in ("Install", "Update", "Reinstall"):
            return

        self.busy = True
        self.status_badge.config(text="WORKING", bg="#382914", fg=self.amber)
        row["button"].configure(text="Working...", state="disabled", kind="secondary")
        row["spinner"].start()

        self.act_title.config(text=f"Task Monitor: {action}ing {row['label']}...")
        self.set_inst_progress(10, f"Initializing pip install for {row['label']}...")

        def worker():
            python_bin = get_real_python_exe()
            self.post(self.log, f"Running: {python_bin} -m pip install --upgrade {pkg_name}")

            cmd = [python_bin, "-m", "pip", "install", "--upgrade", pkg_name]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", creationflags=flags
            )

            progress_val = 20
            error_lines = []
            for line in proc.stdout:
                clean_line = line.strip()
                if clean_line:
                    self.post(self.log, f"[pip] {clean_line}")
                    if "ERROR:" in clean_line:
                        error_lines.append(clean_line)
                    if "Downloading" in clean_line:
                        progress_val = min(65, progress_val + 10)
                        self.post(self.set_inst_progress, progress_val, f"Downloading: {clean_line[:60]}...")
                    elif "Installing collected packages" in clean_line or "Running setup.py" in clean_line:
                        progress_val = 85
                        self.post(self.set_inst_progress, progress_val, "Installing package files...")

            proc.wait()
            if proc.returncode != 0:
                err_msg = "\n".join(error_lines) if error_lines else f"Pip exit code {proc.returncode}"
                self.post(self.package_failed, pkg_name, err_msg)
                return

            inject_host_site_packages()
            self.post(self.set_inst_progress, 100, f"{row['label']} successfully installed! (100%)")
            self.post(self.log, f"{row['label']} installed successfully.")
            self.post(self.package_succeeded, pkg_name)

        threading.Thread(target=worker, daemon=True).start()

    def package_succeeded(self, pkg_name):
        self.busy = False
        self.status_badge.config(text="READY", bg="#0a2a1d", fg=self.green)
        self.rows[pkg_name]["spinner"].stop()
        self.act_title.config(text="Task Monitor: Idle")
        self.check_libraries()

    def package_failed(self, pkg_name, err_msg):
        self.busy = False
        self.status_badge.config(text="READY", bg="#0a2a1d", fg=self.green)
        self.rows[pkg_name]["spinner"].stop()
        self.rows[pkg_name]["button"].configure(text="Retry", state="normal", kind="danger")
        self.act_title.config(text="Task Monitor: Failed")
        self.log(f"Failed to install {pkg_name}: {err_msg}", "ERROR")
        messagebox.showerror("Installation Error", f"{pkg_name}\n\n{err_msg}")

    # ------------------------------------------------------------------------
    # FULLY AUTOMATIC INSTALL ALL (PURE PIP SEQUENTIAL PIPELINE)
    # ------------------------------------------------------------------------

    def quick_install(self):
        if self.busy:
            return
        self.busy = True
        self.status_badge.config(text="WORKING", bg="#382914", fg=self.amber)
        self.hero_btn.configure(state="disabled", text="Installing...")
        self.lib_refresh_btn.configure(state="disabled")
        self.act_title.config(text="Task Monitor: Running Full Automatic Setup...")
        self.log("Automatic setup initiated: Running native pip install for all libraries...")

        cache_dir = Path.home() / "Downloads" / "PES_MODS_Python"
        cache_dir.mkdir(parents=True, exist_ok=True)

        def worker():
            python_bin = get_real_python_exe()
            try:
                # 1. Update Python if needed
                installed_py = platform.python_version()
                latest_py, url_py = fetch_latest_python_installer()

                if compare_versions(installed_py, latest_py) < 0:
                    installer_path = cache_dir / Path(url_py).name
                    self.post(self.log, f"Downloading Python {latest_py}...")

                    def py_dl_cb(done, total, pct, speed):
                        txt = f"Downloading Python {latest_py} ({format_bytes(done)} / {format_bytes(total)} - {pct:.1f}%)"
                        self.post(self.set_inst_progress, int(pct * 0.4), txt)

                    download_file_monitored(url_py, installer_path, py_dl_cb)

                    self.post(self.set_inst_progress, 40, "Executing silent CPython installation...")
                    res = run_process([
                        str(installer_path), "/quiet", "InstallAllUsers=0", "PrependPath=1",
                        "Include_pip=1", "Include_launcher=1", "Include_test=0", "SimpleInstall=0"
                    ])
                    if res.returncode not in (0, 3010):
                        raise RuntimeError(f"Python Installer failed with code {res.returncode}")
                    python_bin = get_real_python_exe()

                # 2. Update pip
                self.post(self.set_inst_progress, 45, "Updating pip package manager...")
                res = run_process([python_bin, "-m", "pip", "install", "--upgrade", "pip"])
                if res.returncode != 0:
                    raise RuntimeError(f"Pip upgrade failed: {res.stderr.strip() or res.stdout.strip()}")

                # 3. Sequentially run pip install on all packages
                total_pkgs = len(REQUIRED_PACKAGES)
                flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

                for idx, (pkg_name, label, _) in enumerate(REQUIRED_PACKAGES, start=1):
                    row = self.rows[pkg_name]
                    inst_ver = row.get("installed_ver")
                    latest_ver = row.get("latest_ver")

                    if not inst_ver or (latest_ver and compare_versions(inst_ver, latest_ver) < 0):
                        self.post(self.log, f"Running pip install for {label}...")
                        step_pct = int(45 + (idx / total_pkgs) * 50)
                        self.post(self.set_inst_progress, step_pct, f"Installing {label} ({idx}/{total_pkgs})...")

                        cmd = [python_bin, "-m", "pip", "install", "--upgrade", pkg_name]
                        proc = subprocess.Popen(
                            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags
                        )

                        errs = []
                        for line in proc.stdout:
                            c_line = line.strip()
                            if c_line:
                                self.post(self.log, f"[{label}] {c_line}")
                                if "ERROR:" in c_line:
                                    errs.append(c_line)

                        proc.wait()
                        if proc.returncode != 0:
                            raise RuntimeError(f"{label} error: " + ("\n".join(errs) if errs else f"code {proc.returncode}"))

                inject_host_site_packages()
                self.post(self.set_inst_progress, 100, "All packages successfully installed! (100%)")
                self.post(self.quick_done, True, "Automatic setup completed! Python and all libraries are installed and ready.")
            except Exception as e:
                self.post(self.quick_done, False, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def quick_done(self, ok, msg):
        self.busy = False
        self.status_badge.config(text="READY", bg="#0a2a1d", fg=self.green)
        self.hero_btn.configure(state="normal", text="Install All")
        self.lib_refresh_btn.configure(state="normal")
        self.act_title.config(text="Task Monitor: Idle")
        self.log(msg, "INFO" if ok else "ERROR")

        self.check_python()
        self.check_libraries()

        if ok:
            messagebox.showinfo("Setup Completed", msg)
        else:
            messagebox.showerror("Setup Error", msg)


# ============================================================================
# ENTRY POINT WITH ADMIN PRIVILEGES
# ============================================================================

def main():
    if os.name != "nt":
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror("Windows Required", "This utility is optimized specifically for Windows 10/11.")
        temp_root.destroy()
        return

    # 1. Elevate to Admin without jumping to System32
    ensure_admin()

    # 2. High-DPI Display Scaling
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()