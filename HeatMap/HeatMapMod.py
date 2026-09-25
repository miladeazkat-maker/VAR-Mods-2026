# -*- coding: utf-8 -*-
# =====================================================================
# HeatMapMod.py — HEAT MAP mod, PES MODS SUITE EDITION v1.0.0
# ---------------------------------------------------------------------
# Built from the user's standalone HeatMap_FL2026.py (1:1 algorithm
# preservation). Suite additions only:
#   * Runs as a ModBridge child process (mode "process"); its THREE
#     game hooks are requested from the ModBridge HookBroker
#     (ball 0x176A3A2 kind=xmm0 SHARED with Match Momentum,
#      time 0x20F1CDA kind=rsi  adoptable with Momentum's TimeHooker,
#      player-code 0xA83964 kind=r12d unique to this mod).
#   * Settings arrive through the bridge (MODBRIDGE_SETTINGS env) and
#     from ../ModsConfig.json mods["Heat Map"] (hm_* keys), re-read
#     live every 5 s: display minute 71-79 (default 75), viewer side
#     random/home/away (default random), 6 calibration parameters.
#   * The original GUI starts HIDDEN; Ctrl+Alt+5 shows/hides it.
#   * At the 91st minute a small badge pops up top-right; clicking it
#     opens the match summary: a player list (photo + name) where every
#     player's heat map can be viewed (and shown on the GPU broadcast).
# =====================================================================
# =====================================================================
# HeatMap FL_2026 — پورت نسخهٔ 2017 روی بازی 2026
# ---------------------------------------------------------------------
# این فایل عین HeatMap_PES2017.py است؛ فقط «لایهٔ دریافت داده از بازی»
# با معماری finalmomentum_2026 (Momentum) جایگزین شده است:
#
#   ۱) پروسهٔ بازی: FL_2026.exe (به‌جای pes2017.exe)
#
#   ۲) مختصات بازیکنان — بدون هیچ هوکی (عین Momentum):
#      آرایهٔ پوینتری FL_2026.exe+0x036F3FC0 → ۲۲ صندلی ۸ بایتی؛
#      زنجیرهٔ هر صندلی:  [seat] → +0x7D8 → +0xA08 → +0x188 → +0xD0
#      (x طولی در +0x0 و z عرضی در +0x8 — مقیاس 1.0 مثل Momentum)
#      صندلی‌های 0..10 = میزبان و 11..21 = مهمان — بدون منطق پیچیدهٔ
#      تفکیک تیم (برخلاف 2017 که ۲۵ موجودیت با هوک شکار می‌شد).
#
#   ۳) مختصات توپ — هوک Momentum:
#      FL_2026.exe+0x176A3A2 - 0F 29 80 50 04 00 00 - movaps [rax+450],xmm0
#      Cave دستور اصلی را اجرا + xmm0 را در slot ذخیره می‌کند؛
#      خواندن ۱۲ بایت: (x طولی، y ارتفاع، z عرضی).
#
#   ۴) زمان مسابقه — عین TimeHooker در Momentum (هیچ تغییری نه):
#      FL_2026.exe+0x20F1CDA - 89 86 40010000 - mov [rsi+140],eax
#      Minutes = [RSI+0x13C] ، Seconds = [RSI+0x140]
#      (Fallback: float در FL_2026.exe+0x0372D114)
#
#   ۵) کد بازیکن — هوک جدید (مشخصات کاربر):
#      FL_2026.exe+A83964 - 44 89 67 08 - mov [rdi+08],r12d   ← خط اول
#      FL_2026.exe+A83968 - 89 77 0C    - mov [rdi+0C],esi    ← خط دوم (پشتیبان)
#      خط اول همیشه «شمارهٔ بازیکن» را می‌نویسد (r12d)؛ Cave هر دو دستور
#      اصلی را اجرا و r12d را در slot ذخیره می‌کند. مقدار 1..11 = میزبان و
#      12..22 = مهمان (برای مهمان همیشه ۱۱ کم می‌شود: 12 → 1).
#
#   ۶) تشخیص لیگ/تیم، منوی انتخاب، شروع مسابقه و نیمه‌ها — عین Momentum:
#      * بایت منو: FL_2026.exe+0x36F9AE0 — فقط ۹ ⇒ اجرای تشخیص تیم
#        (خواندن زندهٔ دو طرف؛ بقیهٔ وضعیت‌ها = قفل روی آخرین انتخاب)
#      * زنجیره‌های home/away و اسلات‌ها (عرض 112) عین Momentum
#      * وضعیت مسابقه: FL_2026.exe+0x372D148 — بایت 128/129 = PLAYING
#      * چرخهٔ عمر: Watchdog/TimeDrop/TRB (عین نسخهٔ ۱۰٫۳/۱۰٫۷ Momentum)
#        → HT / ET1 / ET2 / NEW_MATCH ؛ قرینه در نیمهٔ دوم و وقت اضافهٔ دوم
#
#   ۷) بقیهٔ برنامه (رسم هیت‌مپ، رندر سه‌بعدی، اورلی خودکار، GUI،
#      پایگاه دادهٔ قابل‌ویرایش pes2017_teams.json و بقیهٔ فایل‌های JSON)
#      عیناً و بدون هیچ تغییری از نسخهٔ 2017 حفظ شده است.
#
# نکتهٔ اجرا: مانند قبل نیاز به Run as Admin و نصب numpy/pillow دارد.
# اگر برنامه بدون Restore بسته شود، هوک‌های مانده از جلسهٔ قبل در اتصال
# بعدی «پذیرفته» می‌شوند (Adopt) یا به منبع جایگزین سقوط می‌کند.
# =====================================================================
import os
import sys
import time
import struct
import math
import random
import threading
import traceback
import ctypes
import io
import json
import zipfile
import re
import socket
from ctypes import wintypes

# -------------------------------------------------------------
# سیستم مدیریت خطا و بارگذاری کتابخانه‌ها
# -------------------------------------------------------------
def fatal_error(msg):
    ctypes.windll.user32.MessageBoxW(0, f"خطایی رخ داد:\n\n{msg}", "FL_2026 Tracker Error", 0x10)
    sys.exit(1)

try:
    import tkinter as tk
    from tkinter import messagebox, ttk, filedialog
except Exception as e:
    fatal_error(f"کتابخانه Tkinter یافت نشد:\n{e}")

try:
    import numpy as np
    from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageFont
except ImportError:
    fatal_error("برای رسم هیت‌مپ نصب numpy و pillow الزامی است:\npip install numpy pillow")

# پوشه اجرای اسکریپت (مبنای مسیر پوشه‌های players و Football_Database و renders)
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0])) if (sys.argv and sys.argv[0]) else os.getcwd()

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Field report: "'charmap' codec can't encode characters in position
# 10-13: character maps to <undefined>" right under the AUTO status bar.
# Root cause: Python wraps stdout/stderr in the legacy ANSI codepage
# (cp1252 = 'charmap') whenever the stream is a FILE or a PIPE — exactly
# what a ModBridge child's backend_log.txt stream is — and ONE print of
# a Persian log line ([MatchLifecycle] / [NewHand] / [ENTITIES] ...) or
# an Arabic player/team name (PLAYER_SELECTED=...) then raises
# UnicodeEncodeError.  That exception killed the 30 Hz tracker thread
# (feed froze at 00:00) and aborted the auto-overlay state machine
# mid-transition (stuck WAITING) — "the mod barely works".
# Three hardening layers:
#   1) real console switched to UTF-8 codepage 65001 (best effort)
#   2) stdout/stderr reconfigured to utf-8 + errors='replace' — a print
#      can never raise an encode error again, whatever the locale is
#   3) crash-proof wrapper — even a failing write (closed console,
#      broken pipe, exotic codec) degrades to sanitized ASCII instead
#      of raising into the caller's thread
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

# ---------------------------------------------------------------------
# [PT v2.3.0] PT DATA SOURCE — مشترک با Match Momentum (فایل‌های یکسان):
#   PES MODS/PT/Asset.zip + PES MODS/PT/teams_players_PES2021.txt
#   (پوشهٔ PT کنار MyMods.py است — یک سطح بالاتر از این اسکریپت)
# محتوا: نام/رنگ تیم‌ها از txt ؛ لوگو/پرچم (Teams/{id}.png) و عکس چهرهٔ
# 192x192 بازیکن (Players/{pes_id}.png) از Asset.zip — بدون بازکردن کل zip
# (استخراج تک‌فایلی با کش PT_Cache/). دیتابیس قدیمی pes2017 همان‌طور که
# هست به‌عنوان fallback می‌ماند: PT نبود ⇒ رفتار قبلی بدون هیچ تغییر.
# (بعد از _suite_harden_stdio — هر print باید روی استریم سخت‌شده برود)
# ---------------------------------------------------------------------
# [PT v2.3.3] خوانندهٔ PT «داخل همین فایل» جاسازی شده است — دیگر هیچ
# نیازی به فایل بیرونی PTData.py نیست. قبل از این نسخه، استقراری که
# PTData.py را نداشت بی‌صدا همهٔ امکانات PT را از دست می‌داد (بدون نام
# تیم/رنگ/لوگو/چهره). سورس پایین عین PTData.py رسمی است — بدون تغییر.
_PTDATA_EMBEDDED_SOURCE = r'''# -*- coding: utf-8 -*-
"""
PTData.py — PT 数据源（Heat Map / Broadcast 与 Match Momentum 共用）
================================================================================
用户规格（v2.3.0 / PT 数据源改造）：

  * PT 文件夹位于主程序 MyMods.py 的“旁边”（不是脚本旁边）：
        PES MODS/MyMods.py
        PES MODS/PT/Asset.zip
        PES MODS/PT/teams_players_PES2021.txt
    本模块从脚本目录向上解析：  <script_dir>/../PT/  为主路径，
    依次回退 <script_dir>/PT/ 与 <script_dir>/../../PT/。

  * teams_players_PES2021.txt 结构（必须完整读取）：
        [TEAM n] / Team Record Index / Name / Short Name / Team ID
        TEAM COLORS:  "0 | RGB6=(r,g,b) | RGB=(r,g,b) | HEX=#xxxxxx"（每队多色）
        PLAYERS (n):  "00 | Slot: 00 | Name | PES ID: 110644 | Age: 29 | Shirt: 11"

  * Asset.zip 结构：
        Teams/{teamID}.png      → 球队队徽/队旗（例如 108.png）
        Players/{PES_ID}.png    → 球员头像 192x192（例如 110644.png）

  * 队徽/队旗/头像不落盘解压整个 zip —— 按需读取成员并缓存单文件到
    <script_dir>/PT_Cache/，zip 更新（mtime 变化）后自动重新提取。

  * 线程安全（后端 30 Hz worker 线程 + Tk 主线程并发调用）；
    纯标准库，无 Qt/tkinter 依赖；两个项目各自携带一份完全相同的本文件。

内存指针（在各自模组中实现，这里只提供数据）：
  主/客队 ID：  "FL_2026.exe"+03705E20 → +98 → +228（4 字节 = 主队 ID；
                其“后”4 字节 = 客队 ID）
  球员 Slot：   "FL_2026.exe"+036F4270 → +74（1 字节 = 该球员在球队名单中的 Slot）
================================================================================
"""

import os
import io
import re
import time
import threading
import zipfile

__all__ = ["PTDataSource", "PT_TEAM_LEAGUE_TAG", "FACE_PX", "pt_version"]

pt_version = "1.0"

# HeatMap/Momentum 的 team_key 里用这个“league”哨兵值标记 PT 模式：
# 旧链路的 league 合法范围是 0..36，-1 永远不会冲突。
PT_TEAM_LEAGUE_TAG = -1

# Asset.zip 中球员头像的原始尺寸（用户规格：所有头像均为 192x192）
FACE_PX = 192

_RE_TEAM_HDR = re.compile(r"^\[TEAM\s+(\d+)\]")
_RE_KV = re.compile(r"^([A-Za-z][A-Za-z0-9 _/]*)\s*:\s*(.*)$")
_RE_COLOR = re.compile(
    r"^\s*(\d+)\s*\|\s*RGB6\s*=\s*\(([^)]*)\)\s*\|\s*RGB\s*=\s*\(([^)]*)\)"
    r"(?:\s*\|\s*HEX\s*=\s*(#[0-9A-Fa-f]{6}))?")
_RE_PLAYER = re.compile(
    r"^\s*(\d+)\s*\|\s*Slot\s*:\s*(\d+)\s*\|\s*(.+?)\s*\|\s*PES ID\s*:\s*(\d+)"
    r"\s*\|\s*Age\s*:\s*(\d+)\s*\|\s*Shirt\s*:\s*(\d+)", re.IGNORECASE)


def _parse_rgb(txt):
    """'(0,154,101)' → (0,154,101)；非法 ⇒ None"""
    try:
        parts = [p.strip() for p in txt.split(",")]
        if len(parts) != 3:
            return None
        r, g, b = (max(0, min(255, int(float(p)))) for p in parts)
        return (r, g, b)
    except Exception:
        return None


class PTDataSource(object):
    """PT/Asset.zip + PT/teams_players_PES2021.txt 的统一读取器。

    用法：
        pt = PTDataSource(script_dir)
        if pt.available():
            ent  = pt.find_team(108)                 # → dict 或 None
            name = pt.team_name(108)
            cols = pt.team_colors(108)               # → [(r,g,b), ...]
            px   = pt.team_logo_path(108)            # → 缓存 PNG 路径或 None
            p    = pt.player_by_slot(108, 4)         # → {"name","pes_id",...}
            face = pt.player_face_path(110644)       # → 缓存 PNG 路径或 None
    """

    def __init__(self, script_dir, logger=None):
        self.script_dir = os.path.abspath(script_dir)
        self._log = logger if callable(logger) else (lambda msg: None)
        self._lock = threading.RLock()
        # ---- 候选目录（优先级从高到低）----
        # 用户规格：PT 与 MyMods.py 同级；模组脚本在 PES MODS/ 的子文件夹里
        # ⇒ <script_dir>/../PT 是主路径。其余为容错回退。
        # 注意：宿主脚本（HeatMapMod）用 sys.argv[0] 推导目录，个别启动
        # 方式下会失真；PTData.py 自身永远在模组文件夹里，所以自己的
        # __file__ 目录也加入候选（双保险）。
        try:
            self_dirs = [self.script_dir,
                         os.path.dirname(os.path.abspath(__file__))]
        except Exception:
            self_dirs = [self.script_dir]
        try:
            self_dirs.append(os.getcwd())
        except Exception:
            pass
        cands = []
        for base in self_dirs:
            cands += [
                os.path.join(base, "PT"),
                os.path.join(base, "..", "PT"),
                os.path.join(base, "..", "..", "PT"),
            ]
        seen = set()
        self._dir_candidates = []
        for c in cands:
            ap = os.path.abspath(c)
            if ap not in seen:
                seen.add(ap)
                self._dir_candidates.append(ap)
        self._zip_path = None       # 解析后的 Asset.zip 绝对路径
        self._txt_path = None       # 解析后的 txt 绝对路径
        # ---- 解析结果 ----
        self._teams = {}            # team_id(int) → {"index","name","short","colors","colors6"}
        self._txt_mtime = None
        self._zip_mtime = None
        self._parsed_ok = False
        self._missing_logged = False
        # ---- zip 成员索引（小写规范化名 → ZipInfo）----
        self._zip_index = {}
        self._cache_dir = os.path.join(self.script_dir, "PT_Cache")
        # 周期性重新定位的节流（用户可能运行中途才放入 PT 文件夹）
        self._refresh_min_interval = 5.0
        self._last_refresh = 0.0
        # 首次装载（失败不抛出——调用方用 available() 判断）
        try:
            self._locate()
        except Exception as ex:
            self._log(f"[PT] init error: {ex}")

    def _maybe_refresh(self):
        """限频重定位（每 5 秒一次 getmtime 级别的轻量检查）。"""
        now = time.monotonic()
        if now - self._last_refresh >= self._refresh_min_interval:
            self._last_refresh = now
            try:
                self._locate()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # 路径解析
    # ------------------------------------------------------------------
    def _locate(self):
        """定位 PT 文件夹 + 两个文件；找到新 txt 时（重新）解析。"""
        with self._lock:
            zip_path = txt_path = None
            for d in self._dir_candidates:
                z = os.path.join(d, "Asset.zip")
                t = os.path.join(d, "teams_players_PES2021.txt")
                z_ok = os.path.isfile(z)
                t_ok = os.path.isfile(t)
                if z_ok or t_ok:
                    if zip_path is None and z_ok:
                        zip_path = z
                    if txt_path is None and t_ok:
                        txt_path = t
                if zip_path and txt_path:
                    break
            # 只有一个文件也接受（另一路数据源缺席时优雅降级）
            changed = (txt_path != self._txt_path)
            self._zip_path, self._txt_path = zip_path, txt_path
            if txt_path is None and zip_path is None:
                if not self._missing_logged:
                    self._missing_logged = True
                    self._log("[PT] PT folder NOT found - tried: "
                              + " ; ".join(self._dir_candidates)
                              + " (need Asset.zip and/or teams_players_PES2021.txt)")
                self._teams = {}
                self._parsed_ok = False
                return
            try:
                zm = os.path.getmtime(zip_path) if zip_path else None
            except OSError:
                zm = None
            try:
                tm = os.path.getmtime(txt_path) if txt_path else None
            except OSError:
                tm = None
            if txt_path and (changed or tm != self._txt_mtime or not self._parsed_ok):
                self._parse_txt(txt_path)
            self._txt_mtime = tm
            self._zip_mtime = zm

    # ------------------------------------------------------------------
    # txt 解析（完整结构）
    # ------------------------------------------------------------------
    def _parse_txt(self, path):
        """解析 teams_players_PES2021.txt 的完整结构（749 支球队 + 颜色 + 名单）。"""
        teams = {}
        cur = None
        try:
            with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
                for raw in f:
                    line = raw.rstrip("\r\n")
                    m = _RE_TEAM_HDR.match(line)
                    if m:
                        tid = int(m.group(1))
                        cur = {"index": tid, "id": None, "name": None,
                               "short": None, "colors": [], "colors6": [],
                               "players": {}}
                        teams[tid] = cur
                        continue
                    if cur is None:
                        continue
                    m = _RE_KV.match(line)
                    if m:
                        key = m.group(1).strip().lower()
                        val = m.group(2).strip()
                        if key == "name" and not cur["name"]:
                            cur["name"] = val or None
                        elif key == "short name":
                            cur["short"] = val or None
                        elif key == "team id":
                            try:
                                cur["id"] = int(val)
                            except ValueError:
                                pass
                        continue
                    m = _RE_COLOR.match(line)
                    if m:
                        idx = int(m.group(1))
                        c6 = _parse_rgb(m.group(2))
                        c = _parse_rgb(m.group(3))
                        hexv = (m.group(4) or "").upper()
                        if c is None and hexv:
                            try:
                                c = (int(hexv[1:3], 16), int(hexv[3:5], 16),
                                     int(hexv[5:7], 16))
                            except Exception:
                                c = None
                        # 以颜色编号为序插入（空洞也保留占位，保证编号对齐）
                        while len(cur["colors"]) <= idx:
                            cur["colors"].append(None)
                            cur["colors6"].append(None)
                        cur["colors"][idx] = c if c is not None else (255, 255, 255)
                        cur["colors6"][idx] = c6 if c6 is not None else cur["colors"][idx]
                        continue
                    m = _RE_PLAYER.match(line)
                    if m:
                        try:
                            slot = int(m.group(2))
                        except ValueError:
                            continue
                        cur["players"][slot] = {
                            "slot": slot,
                            "name": m.group(3).strip(),
                            "pes_id": int(m.group(4)),
                            "age": int(m.group(5)),
                            "shirt": int(m.group(6)),
                        }
        except Exception as ex:
            self._log(f"[PT] parse error ({os.path.basename(path)}): {ex}")
            with self._lock:
                self._parsed_ok = False
            return
        # 规范化：以文件里的 "Team ID" 为准（回退到块序号）
        norm = {}
        for tid, ent in teams.items():
            key = ent["id"] if isinstance(ent["id"], int) else tid
            ent["colors"] = [c if c is not None else (255, 255, 255)
                             for c in ent["colors"]]
            ent["colors6"] = [c if c is not None else (255, 255, 255)
                              for c in ent["colors6"]]
            norm[int(key)] = ent
        with self._lock:
            self._teams = norm
            self._parsed_ok = True
        n_players = sum(len(t["players"]) for t in norm.values())
        self._log(f"[PT] teams_players_PES2021.txt parsed: teams={len(norm)} "
                  f"players={n_players} ({os.path.basename(path)})")

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------
    def refresh(self):
        """重新定位/重新解析（txt 或 zip 的 mtime 变化后自动生效）。"""
        try:
            self._locate()
        except Exception:
            pass

    def available(self):
        """txt 已解析出球队 ⇒ True（Asset.zip 缺席时队徽/头像路径返回 None）。"""
        self._maybe_refresh()
        with self._lock:
            return bool(self._parsed_ok and self._teams)

    def status(self):
        """简短状态串（诊断用）。"""
        with self._lock:
            return (f"txt={'OK' if self._parsed_ok else 'NO'}"
                    f"(teams={len(self._teams)}) zip={'OK' if self._zip_path else 'NO'} "
                    f"txt_file={self._txt_path} zip_file={self._zip_path}")

    @staticmethod
    def is_pt_key(key):
        """HeatMap/Momentum 的 team_key 是否为 PT 模式：(‑1, team_id)。"""
        try:
            return (key is not None and int(key[0]) == PT_TEAM_LEAGUE_TAG
                    and int(key[1]) >= 0)
        except Exception:
            return False

    @staticmethod
    def make_key(team_id):
        """team_id → 统一 team_key 元组 (-1, team_id)。"""
        return (PT_TEAM_LEAGUE_TAG, int(team_id))

    def find_team(self, team_id):
        """完整球队条目或 None。team_id 不存在 ⇒ None（垃圾内存值被拒）。"""
        self._maybe_refresh()
        try:
            tid = int(team_id)
        except (TypeError, ValueError):
            return None
        with self._lock:
            return self._teams.get(tid)

    def has_team(self, team_id):
        return self.find_team(team_id) is not None

    def team_name(self, team_id):
        ent = self.find_team(team_id)
        if not ent:
            return None
        return ent.get("name") or ent.get("short") or f"TEAM {team_id}"

    def team_short_name(self, team_id):
        ent = self.find_team(team_id)
        if not ent:
            return None
        return ent.get("short") or ent.get("name") or f"TEAM {team_id}"

    def team_colors(self, team_id):
        """主色列表（RGB 列，即 HEX 标注的那组）— 编号 0..n。"""
        ent = self.find_team(team_id)
        return list(ent["colors"]) if ent else []

    def team_colors6(self, team_id):
        """次色列表（RGB6 列）。"""
        ent = self.find_team(team_id)
        return list(ent["colors6"]) if ent else []

    def players(self, team_id):
        """{slot(int) → {"slot","name","pes_id","age","shirt"}} 或 {}。"""
        ent = self.find_team(team_id)
        return dict(ent["players"]) if ent else {}

    def player_by_slot(self, team_id, slot):
        try:
            s = int(slot)
        except (TypeError, ValueError):
            return None
        ent = self.find_team(team_id)
        if not ent:
            return None
        return ent["players"].get(s)

    def player_by_pes_id(self, team_id, pes_id):
        ent = self.find_team(team_id)
        if not ent:
            return None
        try:
            pid = int(pes_id)
        except (TypeError, ValueError):
            return None
        for p in ent["players"].values():
            if p["pes_id"] == pid:
                return p
        return None

    # ------------------------------------------------------------------
    # Asset.zip 成员提取（队徽 / 队旗 / 头像）
    # ------------------------------------------------------------------
    def _open_zip(self):
        """返回 (ZipFile, zip_mtime) 或 (None, None)；mtime 变化时重建索引。"""
        self._maybe_refresh()
        with self._lock:
            path, known_mtime = self._zip_path, self._zip_mtime
        if not path:
            return None, None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return None, None
        try:
            zf = zipfile.ZipFile(path, "r")
        except Exception as ex:
            self._log(f"[PT] Asset.zip open error: {ex}")
            return None, None
        if mtime != known_mtime or not self._zip_index:
            idx = {}
            try:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    nm = info.filename.replace("\\", "/").strip("/").lower()
                    idx[nm] = info
            except Exception:
                pass
            with self._lock:
                self._zip_index = idx
                self._zip_mtime = mtime
        return zf, mtime

    def _zip_find(self, zf, wanted_names):
        """按候选名（小写规范化）查 zip 成员。"""
        with self._lock:
            idx = dict(self._zip_index)
        for w in wanted_names:
            info = idx.get(w.lower())
            if info is not None:
                return info
        return None

    def _extract_member(self, wanted_names, cache_subdir, cache_name):
        """按需提取一个 zip 成员到缓存目录；返回缓存路径或 None。

        zip 更新（mtime 变大）后缓存自动失效并重新提取；
        提取为“临时文件 + 原子替换”，读取方永远不会拿到半个 PNG。"""
        zf, zmtime = self._open_zip()
        if zf is None:
            return None
        try:
            info = self._zip_find(zf, wanted_names)
            if info is None:
                return None
            cache_dir = os.path.join(self._cache_dir, cache_subdir)
            out = os.path.join(cache_dir, cache_name)
            try:
                if os.path.isfile(out) and zmtime is not None \
                        and os.path.getmtime(out) >= zmtime - 1e-6:
                    return out           # 缓存仍然有效
            except OSError:
                pass
            data = zf.read(info)
            os.makedirs(cache_dir, exist_ok=True)
            tmp = out + f".tmp{os.getpid()}"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, out)
            return out
        except Exception as ex:
            self._log(f"[PT] extract error ({wanted_names[0]}): {ex}")
            return None
        finally:
            try:
                zf.close()
            except Exception:
                pass

    def team_logo_path(self, team_id):
        """球队队徽/队旗 → 缓存 PNG 路径（Asset.zip → Teams/{id}.png）或 None。"""
        try:
            tid = int(team_id)
        except (TypeError, ValueError):
            return None
        names = [f"Teams/{tid}.png", f"Teams/{tid}.PNG", f"teams/{tid}.png"]
        return self._extract_member(names, "Teams", f"{tid}.png")

    def player_face_path(self, pes_id):
        """球员头像（192x192）→ 缓存 PNG 路径（Asset.zip → Players/{PES_ID}.png）或 None。"""
        try:
            pid = int(pes_id)
        except (TypeError, ValueError):
            return None
        names = [f"Players/{pid}.png", f"Players/{pid}.PNG", f"players/{pid}.png"]
        return self._extract_member(names, "Players", f"{pid}.png")


# ----------------------------------------------------------------------
# 自检：python PTData.py [脚本目录]   （默认 = 本文件所在目录）
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    _base = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(
        os.path.abspath(__file__))
    _pt = PTDataSource(_base, logger=lambda m: print(m, flush=True))
    print("[PT] status:", _pt.status())
    if _pt.available():
        _ids = sorted(_pt._teams.keys())[:5]
        for _tid in _ids:
            _e = _pt.find_team(_tid)
            print(f"  team {_tid}: {_e['name']} ({_e['short']}) "
                  f"colors={_e['colors']} players={len(_e['players'])}")
        _p = _pt.player_by_slot(_ids[0], 0)
        if _p:
            print("  sample player:", _p)
            _fp = _pt.player_face_path(_p["pes_id"])
            print("  face path:", _fp, "<- extracted" if _fp else "<- zip member missing")
        _lp = _pt.team_logo_path(_ids[0])
        print("  logo path:", _lp, "<- extracted" if _lp else "<- zip member missing")
'''


def _load_embedded_ptdata():
    """اجرای سورس جاسازی‌شدهٔ PTData در یک ماژول ایزوله — همان API قدیمی."""
    import types
    _mod = types.ModuleType("PTData_embedded")
    _g = _mod.__dict__
    _g["__name__"] = "PTData_embedded"
    _g["__file__"] = os.path.abspath(__file__)
    _mod.__file__ = _g["__file__"]
    exec(compile(_PTDATA_EMBEDDED_SOURCE, "<PTData embedded>", "exec"), _g)
    return _mod

try:
    PTData = _load_embedded_ptdata()
except Exception as _pt_load_ex:
    PTData = None
    print(f"[PT] embedded PT reader failed to load: {_pt_load_ex}")
PT = None
if PTData is not None:
    try:
        PT = PTData.PTDataSource(SCRIPT_DIR,
                                 logger=lambda m: print(m, flush=True))
        print("[PT] reader ready (embedded) - " + str(PT.status()))
    except Exception as _pt_init_ex:
        PT = None
        print(f"[PT] data source init failed: {_pt_init_ex}")

def pt_active():
    """PT data source فعال یا None — همهٔ شاخه‌های PT از همین گیت می‌روند"""
    if PT is not None and PT.available():
        return PT
    return None

# -------------------------------------------------------------
# ۱. مجوز دسترسی ادمین
# -------------------------------------------------------------
def check_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

if (not check_admin()) and sys.platform == "win32" \
        and os.environ.get("HM_NO_ELEVATE", "") != "1":
    try:
        script_path = os.path.abspath(sys.argv[0])
        current_dir = os.path.dirname(script_path)
        params = f'"{script_path}"'
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, current_dir, 1)
        sys.exit(0)
    except SystemExit:
        raise
    except Exception as e:
        fatal_error(f"خطا در دریافت مجوز ادمین: {e}")
# [SUITE v1.0.0] non-Windows (tests) / HM_NO_ELEVATE: continue unelevated

# -------------------------------------------------------------
# ۲. پایگاه تیم‌ها و بازیکنان — فقط از pes2017_teams.json (نسخه ۱۶٫۰)
#    هیچ لیست داخلی در کد وجود ندارد؛ نام تیم، مسیر پرچم/لوگو و نام + مسیر
#    عکس تک‌تک بازیکنان از فایل قابل‌ویرایش کاربر خوانده می‌شود:
#        pes2017_teams.json   (کنار اسکریپت یا داخل Football_Database)
#    ساختار: {"teams": {"league:team": {"name", "flag", "players": {...}}}}
#    اگر فایل نبود، برنامه یک اسکلت خالیِ مستند می‌سازد تا شما آن را پر کنید
#    (نسخهٔ کاملِ ۷۵ تیم/۱۷۵۲ بازیکن همراه ZIP ارائه می‌شود).
#    عکس چهره (360x360): players/{league}/{team}/{code}.png   (پیش‌فرض)
#    لوگو       (512x512): Football_Database/{league}/{team}.png (پیش‌فرض)
# -------------------------------------------------------------
# تیم‌های پیش‌فرض تا قبل از تشخیص (کلاسیک: بارسلونا - رئال مادرید)
DEFAULT_HOME_KEY = (7, 3)
DEFAULT_AWAY_KEY = (7, 15)

# -------------------------------------------------------------
# ۳. تعاریف Win32 API و ثابت‌های حافظه — نسخهٔ FL_2026
#    (ساختارها/ابزارها عین finalmomentum_2026 — هوک‌های 2017 حذف شدند)
# -------------------------------------------------------------
# [SUITE v1.0.0] platform guard: the module must import on non-Windows
# (bridge tests run headless Linux); every memory API stays Windows-only.
if sys.platform == "win32":
    kernel32 = ctypes.windll.kernel32
    psapi = ctypes.windll.psapi
else:
    kernel32 = None
    psapi = None

PROCESS_ALL_ACCESS     = 0x1F0FFF
TH32CS_SNAPPROCESS     = 0x00000002
TH32CS_SNAPMODULE      = 0x00000008
TH32CS_SNAPMODULE32    = 0x00000010
MEM_COMMIT             = 0x1000
MEM_RESERVE            = 0x2000
MEM_RELEASE            = 0x8000
PAGE_EXECUTE_READWRITE = 0x40

class PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * 260)
    ]

class MODULEENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", wintypes.HMODULE),
        ("szModule", ctypes.c_char * 256),
        ("szExePath", ctypes.c_char * 260)
    ]

class MEMORY_BASIC_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", wintypes.DWORD),
        ("RegionSize", ctypes.c_size_t),
        ("State", wintypes.DWORD),
        ("Protect", wintypes.DWORD),
        ("Type", wintypes.DWORD)
    ]

# --- امضای توابع (عین Momentum — بازگشت c_void_p برای آدرس‌های ۶۴ بیتی) ---
if sys.platform == "win32":   # [SUITE v1.0.0] Windows-only prototypes
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.VirtualAllocEx.restype = ctypes.c_void_p
    kernel32.VirtualAllocEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    kernel32.VirtualProtectEx.restype = wintypes.BOOL
    kernel32.VirtualProtectEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    kernel32.VirtualQueryEx.restype = ctypes.c_size_t
    kernel32.VirtualQueryEx.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.POINTER(MEMORY_BASIC_INFORMATION), ctypes.c_size_t]
    kernel32.WriteProcessMemory.restype = wintypes.BOOL
    kernel32.WriteProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
    kernel32.ReadProcessMemory.restype = wintypes.BOOL
    kernel32.ReadProcessMemory.argtypes = [wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]

def get_fl_pid():
    """پیدا کردن PID بازی — عین get_pid_by_name در Momentum (FL_2026.exe)"""
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    if kernel32.Process32First(snapshot, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.decode('utf-8', errors='ignore').lower() == GAME_PROCESS_NAME.lower():
                kernel32.CloseHandle(snapshot)
                return entry.th32ProcessID
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snapshot)
    return None

def get_fl_base(pid):
    """آدرس پایهٔ ماژول FL_2026.exe — عین get_module_base در Momentum"""
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)
    if kernel32.Module32First(snapshot, ctypes.byref(entry)):
        while True:
            if entry.szModule.decode('utf-8', errors='ignore').lower() == GAME_PROCESS_NAME.lower():
                kernel32.CloseHandle(snapshot)
                return entry.modBaseAddr
            if not kernel32.Module32Next(snapshot, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snapshot)
    return None

def safe_read(hp, addr, size):
    """خواندن امن حافظه — عین Momentum"""
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(hp, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)) and read.value == size:
        return buf.raw
    return None

def safe_write(hp, addr, data):
    """نوشتن امن حافظه (با VirtualProtectEx) — عین Momentum"""
    size = len(data)
    old = wintypes.DWORD()
    if not kernel32.VirtualProtectEx(hp, ctypes.c_void_p(addr), size, PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        return False
    buf = ctypes.create_string_buffer(data)
    written = ctypes.c_size_t()
    res = kernel32.WriteProcessMemory(hp, ctypes.c_void_p(addr), buf, size, ctypes.byref(written))
    kernel32.VirtualProtectEx(hp, ctypes.c_void_p(addr), size, old, ctypes.byref(old))
    return bool(res and written.value == size)

def allocate_near_target(hp, target_addr, size=4096):
    """تخصیص Cave نزدیک هدف (برای jmp rel32) — عین Momentum"""
    mbi = MEMORY_BASIC_INFORMATION()
    curr = (target_addr - 0x10000) & ~0xFFFF
    min_addr = max(0x10000, target_addr - 0x70000000)
    while curr > min_addr:
        if kernel32.VirtualQueryEx(hp, ctypes.c_void_p(curr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0: break
        if mbi.State == 0x10000 and mbi.RegionSize >= size:
            alloc = kernel32.VirtualAllocEx(hp, ctypes.c_void_p(curr), size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if alloc: return alloc
        curr = (mbi.BaseAddress if mbi.BaseAddress else curr) - 0x10000

    curr = (target_addr + 0x10000) & ~0xFFFF
    max_addr = target_addr + 0x70000000
    while curr < max_addr:
        if kernel32.VirtualQueryEx(hp, ctypes.c_void_p(curr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0: break
        if mbi.State == 0x10000 and mbi.RegionSize >= size:
            alloc = kernel32.VirtualAllocEx(hp, ctypes.c_void_p(curr), size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if alloc: return alloc
        curr = (mbi.BaseAddress if mbi.BaseAddress else curr) + (mbi.RegionSize if mbi.RegionSize else 0x10000)
    return None

# -------------------------------------------------------------
# ثابت‌های بازی FL_2026 — همه عین finalmomentum_2026
# -------------------------------------------------------------
GAME_PROCESS_NAME   = "FL_2026.exe"

# --- هوک توپ (GameEngine در Momentum) ---
BALL_HOOK_OFFSET    = 0x176A3A2
BALL_ORIG_BYTES     = b'\x0F\x29\x80\x50\x04\x00\x00'   # movaps [rax+0x450],xmm0

# --- هوک زمان مسابقه (TimeHooker در Momentum — بدون هیچ تغییری) ---
TIME_HOOK_OFFSET    = 0x20F1CDA
TIME_ORIG_BYTES     = b'\x89\x86\x40\x01\x00\x00'       # mov [rsi+00000140],eax
TIME_MINUTES_OFFSET = 0x13C
TIME_SECONDS_OFFSET = 0x140

# --- هوک کد بازیکن (مشخصات کاربر — FL_2026.exe+A83964) ---
PLAYER_CODE_HOOK_OFFSET = 0xA83964
PLAYER_CODE_ORIG_BYTES  = b'\x44\x89\x67\x08\x89\x77\x0C'  # mov [rdi+08],r12d ; mov [rdi+0C],esi

# --- آرایهٔ بازیکنان (بدون هوک — فقط پوینتر؛ عین Momentum) ---
PLAYERS_ARRAY_OFFSET = 0x036F3FC0
PLAYER_SEAT_COUNT    = 22
PLAYER_LINK_OFFSETS  = (0x7D8, 0xA08, 0x188)   # p1 → p2 → p3 → p4
PLAYER_COORD_OFFSET  = 0xD0                    # x طولی در +0x0 ، z عرضی در +0x8

# --- وضعیت مسابقه و زمان جایگزین ---
MATCH_STATE_OFFSET = 0x372D148    # بایت — 128/129 = PLAYING (عین Momentum)
MATCH_TIME_OFFSET  = 0x0372D114   # float — فقط Fallback (عین Momentum)

# --- تشخیص تیم‌ها (TeamIdentityTracker در Momentum) ---
TEAM_MENU_STATE_OFFSET = 0x036F9AE0   # بایت وضعیت منو (خواندن مستقیم base+آفست — عین بقیهٔ آفست‌ها)
# [PT v2.3.1] شرط اجرای تشخیص تیم: فقط وقتی بایت منو = ۹ باشد (قبلاً ۱۰۰ بود).
TEAM_MENU_DETECT_VALUE = 9
TEAM_SLOT_COUNT        = 37           # تعداد اسلات‌های هر لیگ
TEAM_SLOT_STRIDE       = 112          # فاصلهٔ اسلات‌ها (بایت)

# --- [PT v2.3.0] NEW POINTER SPECS (user spec — Cheat Engine hex notation) ---
# شناسهٔ تیم میزبان/مهمان (روش جدید — جایگزین زنجیرهٔ league/slots):
#   پایه  = "FL_2026.exe"+0x03705E20 → deref → +0x98 → deref → +0x228
#   [پایانی]     (۴ بایت) = Team ID میزبان
#   [پایانی + 4] (۴ بایت) = Team ID مهمان
# نام/رنگ تیم از teams_players_PES2021.txt ؛ لوگو/پرچم از Asset.zip
# (Teams/{id}.png). اعتبارسنجی: هر دو ID باید در دیتابیس PT باشند.
TEAM_ID_PTR_OFFSET   = 0x03705E20
TEAM_ID_CHAIN        = (0x98, 0x228)
# اسلاتِ بازیکن جاری در لیست تیمش (روش جدید — جایگزین کد 1..22 برای هویت):
#   پایه = "FL_2026.exe"+0x036F4270 → deref → +0x74 ⇒ ۱ بایت = Slot
#   (نمونهٔ کاربر: بارسلونا Slot 04 = Eric García — در txt همین‌گونه است)
PLAYER_SLOT_PTR_OFFSET = 0x036F4270
PLAYER_SLOT_CHAIN      = (0x74,)

# --- چرخهٔ عمر مسابقه (MomentumScoringConfig در Momentum) ---
MATCH_RESTART_DELTA    = 5.0      # افت ناگهانی زمان بازی = ری‌استارت
HT_HARD_MIN_FIRST_HALF = 2700.0   # 45*60 — حداقل زمان نیمه اول برای HT واقعی
HT_RESUME_LOWER_SLACK  = 30.0
HT_RESUME_TOLERANCE    = 600.0
NEW_GAME_MAX_START     = 180.0    # از سرگیری زیر این مقدار = بازی جدید
ET_RESET_TOLERANCE     = 720.0
TRB_ZERO_T             = 1.0      # تایمر ≤ ۱ ثانیه ⇒ «صفر شده»
TRB_RISE_T             = 2.0      # عبور به بالای ۲ ثانیه ⇒ «شروع به بالا رفتن»
TRB_COOLDOWN_SEC       = 20.0     # فاصلهٔ حداقلی دو نوسازی متوالی

# عنوان نیمه + قرینه — مطابق نسخهٔ 2017 (نیمهٔ دوم و وقت اضافهٔ دوم قرینه)
PERIOD_TITLES = {
    1: ("نیمه اول", False),
    2: ("نیمه دوم", True),
    3: ("وقت اضافه اول", False),
    4: ("وقت اضافه دوم", True),
}

# -------------------------------------------------------------
# وضعیت اجرا، هوک‌ها و داده‌های زنده
# -------------------------------------------------------------
h_process = None
base_addr = None

ball_hook_addr = 0; ball_cave_addr = 0; ball_data_addr = 0
time_hook_addr = 0; time_cave_addr = 0; time_data_addr = 0
pcode_hook_addr = 0; pcode_cave_addr = 0; pcode_data_addr = 0

is_hooked = False
is_running = True

status_msg = "در حال اتصال به بازی..."
current_code = None      # کد بازیکن از هوک A83964 (1..22 خام)

display_minute = 0
display_second = 0
period_title = "در انتظار شروع"
is_clock_active = False
is_inverted_active = False
diff_val = 0
total_samples_taken = 0
actual_sampling_rate = 0.0

entities = []
entities_lock = threading.Lock()
entities_ready = False
match_reset_event = False

ball_pos = {"x": 0.0, "z": 0.0, "valid": False}
initial_discovered_codes = set()

# وضعیت چرخهٔ عمر مسابقه (عین Momentum — Worker تغییر می‌دهد)
half_number = 1          # 1=نیمه اول 2=نیمه دوم 3=وقت اضافه اول 4=وقت اضافه دوم
ht_pending = False
ht_prev_end_t = 0.0
seen_max_t = 0.0
prev_total_t = None
trb_armed = False
trb_last_fire_wall = 0.0
last_auto_reset_wall = 0.0
match_entities_built = False

# متغیرهای تیمی پویا (کلید تیم = "league:team" در pes2017_teams.json)
home_team_key = DEFAULT_HOME_KEY
away_team_key = DEFAULT_AWAY_KEY
home_team_name = None       # مقدار واقعی بعد از تعریف توابع (پایین‌تر)
away_team_name = None
home_players_dict = {}
away_players_dict = {}

# جفت خام تشخیص‌داده‌شده از حافظه (league_id, val) + مسیر لوگوی باشگاه
home_team_id_info = None
away_team_id_info = None
home_team_logo = None      # مسیر PNG لوگو (Football_Database)
away_team_logo = None

# -------------------------------------------------------------
# ابعاد فیزیکی و کالیبراسیون (عین 2017 — بدون تغییر)
# -------------------------------------------------------------
TOTAL_ENGINE_X_MIN = -55.0
TOTAL_ENGINE_X_MAX =  55.0
TOTAL_ENGINE_Z_MIN = -37.0
TOTAL_ENGINE_Z_MAX =  37.0

PITCH_LINE_X_MIN = -52.5
PITCH_LINE_X_MAX =  52.5
PITCH_LINE_Z_MIN = -34.0
PITCH_LINE_Z_MAX =  34.0

GRID_W = 220
GRID_H = 148
entity_heatmaps = np.zeros((25, GRID_H, GRID_W), dtype=np.float32)
heatmap_lock = threading.Lock()

calib_gain = 3.30
calib_ceiling = 0.4
calib_gamma = 0.85
calib_blur_m = 1.4
calib_feather = 9.0
calib_cutoff = 0.2

# [SUITE v1.0.6] shipped defaults of the six calibration parameters — used
# by the panel's restore-default button so the user can always come back
# to the values the mod was tuned with.
CALIB_DEFAULTS = {"gain": 3.30, "ceiling": 0.4, "gamma": 0.85,
                  "blur_m": 1.4, "feather": 9.0, "cutoff": 0.2}

OUTFIELD_INDICES = list(range(1, 11)) + list(range(12, 22))
active_filter_indices = list(OUTFIELD_INDICES)
current_filter_label = "همه بازیکنان (۲۰ بازیکن فعال)"
current_mode_type = "TEAM"

# -------------------------------------------------------------
# چرخهٔ عمر مسابقه — توابع خالص (عین Momentum نسخهٔ ۱۰٫۳؛ قابل تست)
# -------------------------------------------------------------

# =====================================================================
# [SUITE v1.0.0] ModBridge HOOK BROKER client + MOD SETTINGS + 91'
# match-summary trigger.  Pure stdlib, fully fail-safe: when the bridge
# is not running every function falls back to the original local path
# (the standalone mod behaviour is preserved byte-for-byte).
# =====================================================================
class BridgeHookClient:
    """Client for the ModBridge HookBroker (localhost JSON-line TCP).
    The bridge is the single owner of hook bytes:
      hook_request -> installs once / returns the EXISTING shared buffer
      hook_status  -> cheap liveness check
      hook_release -> bytes are restored only when the LAST consumer leaves
      hook_reset_request -> bridge restores + rebuilds a dead feed
    Discovery: MODBRIDGE_IPC_PORT / MODBRIDGE_IPC_TOKEN env (bridge spawn),
    else <PES MODS>/bridge_ipc.json. RLock: hello runs inside connect."""
    MOD_NAME = "Heat Map"

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
        self._ipc_file = ipc_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bridge_ipc.json")
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
                s = socket.create_connection(("127.0.0.1", int(self._port)),
                                             timeout=self._rpc_timeout)
                s.settimeout(self._rpc_timeout)
            except Exception as e:
                self.last_error = f"connect-failed:{e.__class__.__name__}"
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
            self.last_error = f"hello:{e.__class__.__name__}"
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
                    if resp.get("error") in ("hello first", "bad token or mod name"):
                        self._close_sock()
                    return None
                return resp
            except Exception as e:
                self.last_error = f"{e.__class__.__name__}"
                self._close_sock()
                return None

    def ping(self):
        return self._rpc({"cmd": "ping"})

    def hook_request(self, site_rva, orig_bytes, nop, kind="xmm0"):
        r = self._rpc({"cmd": "hook_request", "site_rva": int(site_rva),
                       "orig_hex": bytes(orig_bytes).hex(), "nop": int(nop),
                       "kind": kind})
        if r is None:
            return None
        try:
            return int(r.get("buffer"))
        except Exception:
            return None

    def hook_status(self, site_rva):
        return self._rpc({"cmd": "hook_status", "site_rva": int(site_rva)})

    def hook_release(self, site_rva):
        r = self._rpc({"cmd": "hook_release", "site_rva": int(site_rva)})
        return bool(r)

    def hook_reset_request(self, site_rva, orig_bytes, nop, kind="xmm0"):
        r = self._rpc({"cmd": "hook_reset_request", "site_rva": int(site_rva),
                       "orig_hex": bytes(orig_bytes).hex(), "nop": int(nop),
                       "kind": kind})
        if r is None:
            return None
        try:
            return int(r.get("buffer"))
        except Exception:
            return None

    def game_status(self):
        """[SUITE v2.1.5] is FL_2026.exe running? PROCESS DETECTION IS THE
        BRIDGE'S JOB (user architecture): the bridge polls the game every
        2 s, so this backend opened BEFORE the game asks and waits instead
        of trusting its own one-shot process scan. Returns
        {running, pid, base, name} or None when no bridge answers at all
        (standalone run — the caller may then scan locally)."""
        return self._rpc({"cmd": "game_status"})


_HM_BRIDGE = None
_HM_BRIDGE_TRIED = False
_HM_BRIDGE_LAST_FAIL = 0.0


def hm_bridge():
    """Lazy, cached broker client. None = bridge absent (local path).
    [SUITE v2.1.5] a failed discovery is retried every >= 5 s: the backend
    may be started before the bridge writes bridge_ipc.json, and BOTH the
    game detection and the hook ownership live in the bridge now — giving
    up forever would lock the mod out of both."""
    global _HM_BRIDGE, _HM_BRIDGE_TRIED, _HM_BRIDGE_LAST_FAIL
    if _HM_BRIDGE is not None:
        return _HM_BRIDGE
    if _HM_BRIDGE_TRIED:
        if time.time() - _HM_BRIDGE_LAST_FAIL < 5.0:
            return None
        _HM_BRIDGE_TRIED = False
    _HM_BRIDGE_TRIED = True
    _HM_BRIDGE_LAST_FAIL = time.time()
    try:
        cli = BridgeHookClient()
        if cli.available() and cli.ping() is not None:
            _HM_BRIDGE = cli
            print(f"[HOOK] HookBroker reachable — hook bytes owned by the "
                  f"bridge ({cli._port})", flush=True)
            return cli
        print(f"[HOOK] no HookBroker ({cli.last_error}) — local hook path",
              flush=True)
    except Exception as e:
        print(f"[HOOK] broker discovery failed: {e.__class__.__name__}: {e}",
              flush=True)
    return None


# ---------------------------------------------------------------------
# [SUITE v1.0.0] MOD SETTINGS — sent by MyMods through the bridge
# (MODBRIDGE_SETTINGS env JSON) and persisted in ../ModsConfig.json
# mods["Heat Map"]. Both are read; the file wins (it is the live copy).
# ---------------------------------------------------------------------
HM_SETTINGS_DEFAULTS = {
    "hm_display_minute": 75,      # auto heat map display minute (71..79)
    "hm_viewer_side": "random",   # random | home | away
    "hm_gain": 3.3,               # sensitivity
    "hm_ceiling": 0.4,            # heat ceiling (s)
    "hm_gamma": 0.85,             # gamma
    "hm_blur_m": 1.4,             # initial softness (m)
    "hm_feather": 9.0,            # edge feather (px)
    "hm_cutoff": 0.2,             # minimum filter
}
HM_DISPLAY_MINUTE = HM_SETTINGS_DEFAULTS["hm_display_minute"]
HM_VIEWER_SIDE = HM_SETTINGS_DEFAULTS["hm_viewer_side"]
_HM_CFG_PATH = os.path.join(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))), "ModsConfig.json")
_hm_last_cfg_check = 0.0
_hm_settings_sig = None


def hm_clamp(v, lo, hi, default):
    try:
        v = type(default)(v)
    except Exception:
        return default
    return max(lo, min(hi, v))


def hm_load_settings(silent=False):
    """Load + clamp + apply the mod settings. Safe to call repeatedly
    (the tracker re-reads every 5 s so edits land without a restart)."""
    global HM_DISPLAY_MINUTE, HM_VIEWER_SIDE, calib_gain, calib_ceiling
    global calib_gamma, calib_blur_m, calib_feather, calib_cutoff
    global _hm_last_cfg_check, _hm_settings_sig
    d = dict(HM_SETTINGS_DEFAULTS)
    raw = os.environ.get("MODBRIDGE_SETTINGS", "")
    if raw:
        try:
            env_d = json.loads(raw)
            if isinstance(env_d, dict):
                for k in HM_SETTINGS_DEFAULTS:
                    if k in env_d:
                        d[k] = env_d[k]
        except Exception:
            pass
    try:
        with open(_HM_CFG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        saved = (cfg.get("mods", {}) or {}).get("Heat Map", {}) or {}
        for k in HM_SETTINGS_DEFAULTS:
            if k in saved:
                d[k] = saved[k]
    except Exception:
        pass

    new_min = hm_clamp(d["hm_display_minute"], 71, 79, 75)
    side = str(d["hm_viewer_side"] or "random").strip().lower()
    new_side = side if side in ("random", "home", "away") else "random"
    new_gain = hm_clamp(d["hm_gain"], 0.2, 8.0, 3.3)
    new_ceil = hm_clamp(d["hm_ceiling"], 0.1, 8.0, 0.4)
    new_gamma = hm_clamp(d["hm_gamma"], 0.2, 1.5, 0.85)
    new_blur = hm_clamp(d["hm_blur_m"], 0.5, 3.0, 1.4)
    new_feather = hm_clamp(d["hm_feather"], 0.0, 25.0, 9.0)
    new_cutoff = hm_clamp(d["hm_cutoff"], 0.0, 0.35, 0.2)

    sig = (new_min, new_side, new_gain, new_ceil, new_gamma, new_blur,
           new_feather, new_cutoff)
    HM_DISPLAY_MINUTE = new_min
    HM_VIEWER_SIDE = new_side
    calib_gain, calib_ceiling, calib_gamma = new_gain, new_ceil, new_gamma
    calib_blur_m, calib_feather, calib_cutoff = new_blur, new_feather, new_cutoff
    if sig != _hm_settings_sig:
        first = _hm_settings_sig is None
        _hm_settings_sig = sig
        if not silent or first:
            print(f"[SETTINGS] Heat Map settings applied: display_minute="
                  f"{new_min} viewer_side={new_side} gain={new_gain:.2f} "
                  f"ceiling={new_ceil:.1f} gamma={new_gamma:.2f} "
                  f"blur={new_blur:.1f} feather={new_feather:.0f} "
                  f"cutoff={new_cutoff:.2f}", flush=True)


def hm_settings_tick(now_wall):
    """Called from the 30 Hz loop — re-reads the config at most every 5 s."""
    global _hm_last_cfg_check
    if now_wall - _hm_last_cfg_check >= 5.0:
        _hm_last_cfg_check = now_wall
        try:
            hm_load_settings(silent=True)
        except Exception:
            pass


def _start_backend_once():
    """Start the tracker worker + overlay engine exactly once (both the GUI
    and the headless main path go through here)."""
    global _BACKEND_STARTED
    if _BACKEND_STARTED:
        return
    _BACKEND_STARTED = True
    hm_load_settings()
    try:
        threading.Thread(target=tracker_worker, daemon=True,
                         name="hm-tracker").start()
    except Exception as e:
        print(f"[HeatMap] tracker worker start failed: {e}", flush=True)
    try:
        ensure_auto_overlay_engine()
    except Exception:
        pass


_BACKEND_STARTED = False


def shutdown_backend():
    """Full teardown: engine, hooks (bridge release or local restore)."""
    global is_running
    is_running = False
    try:
        if _AUTO_ENGINE is not None:
            _AUTO_ENGINE.shutdown(timeout=2.0)
    except Exception:
        pass
    try:
        cleanup_hooks()
    except Exception:
        pass


# ---------------------------------------------------------------------
# [SUITE v1.0.0] Ctrl+Alt+5 global hotkey — shows/hides the hidden panel.
# Same edge-detected poller pattern as Match Momentum's Alt+Ctrl+Y.
# ---------------------------------------------------------------------
_HM_TEST = None            # tests may inject {"hotkey_down": bool}
_HM_TOGGLE_REQ = threading.Event()


def _hm_hotkey_down():
    """True while Ctrl+Alt+5 (or Ctrl+Alt+NumPad5) is physically held."""
    if sys.platform == "win32":
        try:
            user32 = ctypes.windll.user32
            alt = bool(user32.GetAsyncKeyState(0x12) & 0x8000)   # VK_MENU
            ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)  # VK_CONTROL
            k5 = bool(user32.GetAsyncKeyState(0x35) & 0x8000)    # '5'
            np5 = bool(user32.GetAsyncKeyState(0x65) & 0x8000)   # VK_NUMPAD5
            return alt and ctrl and (k5 or np5)
        except Exception:
            return False
    return bool(getattr(_HM_TEST, "hotkey_down", False)) if _HM_TEST else False


def _hm_hotkey_loop():
    was_down = False
    while is_running:
        try:
            down = _hm_hotkey_down()
            if down and not was_down:
                _HM_TOGGLE_REQ.set()
            was_down = down
        except Exception:
            pass
        time.sleep(0.04)


# ---------------------------------------------------------------------
# [SUITE v1.0.0] 91st-minute match summary trigger (user spec #5):
# once per match, when the game clock reaches 91:00, queue ONE request;
# the GUI thread consumes it and pops the small top-right badge which
# opens the player-list summary window.
# ---------------------------------------------------------------------
class MatchSummaryController:
    SUMMARY_MINUTE = 91

    def __init__(self):
        self._lock = threading.Lock()
        self._pending = False
        self._fired = False

    def reset(self):
        with self._lock:
            if self._fired or self._pending:
                print("[SUMMARY] reset for the new match", flush=True)
            self._pending = False
            self._fired = False

    def tick(self, game_sec):
        try:
            g = int(game_sec or 0)
        except Exception:
            return
        with self._lock:
            if self._fired:
                return
            if g >= self.SUMMARY_MINUTE * 60:
                self._fired = True
                self._pending = True
                print(f"[SUMMARY] {g // 60:02d}:{g % 60:02d} match summary "
                      f"available (minute {self.SUMMARY_MINUTE} reached)",
                      flush=True)

    def consume(self):
        with self._lock:
            p = self._pending
            self._pending = False
            return p


SUMMARY_CTRL = MatchSummaryController()


def fl_compute_total_seconds(minutes, seconds):
    """عین TimeHooker.compute_total_seconds در Momentum:
       ثانیه معمولی (0..59) ⇒ minutes*60+seconds ؛ در غیر این صورت خودِ مقدار"""
    if seconds <= 59:
        return float(minutes * 60 + seconds)
    return float(seconds)

def should_flag_time_drop(prev_t, current_t, min_delta):
    """آیا افت بزرگ زمان بازی باید «علامت» بخورد؟ (عین Momentum)"""
    if prev_t is None or prev_t <= 0:
        return False
    return (prev_t - current_t) > min_delta

def classify_resume_after_drop(prev_end_t, current_t, half_number, *,
                               ht_hard_min=2700.0,
                               ht_resume_lower_slack=30.0,
                               ht_resume_tolerance=600.0,
                               new_game_max_start=180.0,
                               et_reset_tolerance=720.0):
    """تصمیم قطعی پس از از سرگیری PLAYING (عین Momentum — بدون تغییر):
       خروجی: HT | NEW_MATCH | ET1 | ET2 | KEPT"""
    # ۱) بازی جدید — تایمر ≈ صفر (قوی‌ترین سیگنال؛ مقدم بر HT)
    if current_t <= new_game_max_start:
        return "NEW_MATCH"
    # ۲-د) شروع نیمهٔ دوم وقت اضافه — ریست ۱۰۵ از بالای ۱۰۵
    if (half_number == 3
            and prev_end_t > 105.0 * 60.0
            and (105.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 105.0 * 60.0 + et_reset_tolerance):
        return "ET2"
    # ۲-ج) شروع وقت اضافه — ریست ۹۰ از بالای ۹۰
    if (half_number == 2
            and prev_end_t > 90.0 * 60.0
            and (90.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 90.0 * 60.0 + et_reset_tolerance):
        return "ET1"
    # ۲) HT — قانون سخت
    if (half_number == 1
            and prev_end_t >= ht_hard_min
            and (ht_hard_min - ht_resume_lower_slack) <= current_t
            and current_t <= ht_hard_min + ht_resume_tolerance):
        return "HT"
    # ۳) حفظ نمودار
    return "KEPT"

def is_new_match_watchdog(seen_max_t, current_t, new_game_max_start, min_delta):
    """Watchdog مستقل بازی جدید (عین Momentum — بدون تغییر)"""
    if current_t > new_game_max_start:
        return False
    return seen_max_t > (max(new_game_max_start, current_t) + min_delta)

# -------------------------------------------------------------
# نصب / برداشتن هوک‌ها (توپ / زمان / کد بازیکن)
# -------------------------------------------------------------
def fl_install_ball_hook():
    """نصب هوک توپ — عین GameEngine._install_ball_hook در Momentum
    [SUITE v2.1.5] bridge-only when the bridge answers: a refused request
    NEVER falls back to a local install — a second local hook on this
    shared site (Match Momentum reads the same buffer) is exactly what
    breaks the other mod's feed. Returns False and the periodic bridge
    retry re-requests it. The original local install is ONLY the
    standalone path (no bridge at all)."""
    global ball_hook_addr, ball_cave_addr, ball_data_addr
    cli = hm_bridge()
    if cli is not None:
        buf = cli.hook_request(BALL_HOOK_OFFSET, BALL_ORIG_BYTES, 2)
        if buf:
            ball_hook_addr = base_addr + BALL_HOOK_OFFSET
            ball_cave_addr = 0
            ball_data_addr = buf
            print(f"[HOOK] ball hook via BRIDGE (shared buffer 0x{buf:X})",
                  flush=True)
            return True
        print(f"[HOOK] bridge ball hook refused ({cli.last_error}) — "
              f"NO local fallback (the bridge owns the bytes); will retry",
              flush=True)
        return False
    ball_hook_addr = base_addr + BALL_HOOK_OFFSET
    ball_cave_addr = allocate_near_target(h_process, ball_hook_addr, 128)
    if not ball_cave_addr:
        return False
    ball_data_addr = ball_cave_addr + 64

    cave_b = bytearray(BALL_ORIG_BYTES)
    cave_b.append(0x53)                                      # push rbx
    cave_b.extend(b'\x48\xBB')                               # mov rbx, imm64
    cave_b.extend(struct.pack('<Q', ball_data_addr))
    cave_b.extend(b'\x0F\x11\x03')                           # movups [rbx], xmm0
    cave_b.append(0x5B)                                      # pop rbx
    cave_b.extend(b'\xFF\x25\x00\x00\x00\x00')               # jmp qword [rip+0]
    cave_b.extend(struct.pack('<Q', ball_hook_addr + 7))

    safe_write(h_process, ball_cave_addr, bytes(cave_b))
    rel_jmp = ball_cave_addr - (ball_hook_addr + 5)
    patch = b'\xE9' + struct.pack('<i', rel_jmp) + b'\x90\x90'
    return bool(safe_write(h_process, ball_hook_addr, patch))

def fl_adopt_ball_hook():
    """اتصال به هوک توپِ نصب‌مانده از جلسهٔ قبل — عین Momentum"""
    global ball_hook_addr, ball_cave_addr, ball_data_addr
    curr = safe_read(h_process, base_addr + BALL_HOOK_OFFSET, 7)
    if not curr or curr[0] != 0xE9:
        return False
    rel = struct.unpack('<i', curr[1:5])[0]
    ball_hook_addr = base_addr + BALL_HOOK_OFFSET
    ball_cave_addr = ball_hook_addr + 5 + rel
    ball_data_addr = ball_cave_addr + 64
    return True

def fl_install_time_hook():
    """نصب هوک زمان — عین TimeHooker.hook در Momentum (بدون هیچ تغییری)
    [SUITE v2.1.5] bridge-only when the bridge answers (kind=rsi): the
    SAME site is used by Momentum's TimeHooker, so ONE bridge-owned hook
    feeds both mods from one RSI slot; a refusal NEVER falls back to a
    local install (double hooks on this site are exactly what disturbed
    the time when both mods were enabled). Local install = standalone
    path only."""
    global time_hook_addr, time_cave_addr, time_data_addr
    cli = hm_bridge()
    if cli is not None:
        buf = cli.hook_request(TIME_HOOK_OFFSET, TIME_ORIG_BYTES, 1, kind="rsi")
        if buf:
            time_hook_addr = base_addr + TIME_HOOK_OFFSET
            time_cave_addr = 0
            time_data_addr = buf
            print(f"[HOOK] time hook via BRIDGE (RSI slot 0x{buf:X})",
                  flush=True)
            return True
        print(f"[HOOK] bridge time hook refused ({cli.last_error}) — "
              f"NO local fallback (the bridge owns the bytes); will retry",
              flush=True)
        return False
    time_hook_addr = base_addr + TIME_HOOK_OFFSET

    # راستی‌آزمایی امضای دستور اصلی قبل از هرگونه نوشتن
    curr = safe_read(h_process, time_hook_addr, len(TIME_ORIG_BYTES))
    if curr is None:
        raise Exception("خواندن حافظه Time Hook ممکن نشد.")
    if curr == TIME_ORIG_BYTES:
        pass  # حالت عادی
    elif curr[0] == 0xE9:
        raise Exception("Time Hook قبلا نصب شده است (اجرای قبلی Restore نشده). بازی را ری‌استارت کنید.")
    else:
        raise Exception("امضای دستور زمان مطابقت ندارد: " + curr.hex().upper() +
                        " (آفست 0x20F1CDA نیاز به بازبینی دارد)")

    time_cave_addr = allocate_near_target(h_process, time_hook_addr, 128)
    if not time_cave_addr:
        raise Exception("خطا در تخصیص حافظه برای Time Hook.")

    time_data_addr = time_cave_addr + 0x40   # slot 8 بایتی RSI
    code_start = time_cave_addr + 0x20

    # ---------- Cave (عین Momentum) ----------
    # mov [rsi+0x140], eax      ; دستور اصلی بازی       (6)
    # push rax                  ;                        (1)
    # pushfq                    ;                        (1)
    # mov rax, rsi              ;                        (3)
    # mov [data_addr], rax      ; capture RSI           (10)
    # popfq                     ;                        (1)
    # pop rax                   ;                        (1)
    # jmp rel32 -> target+6                              (5)
    rel_jmp_back = (time_hook_addr + 6) - (code_start + 28)

    cave = bytearray([
        0x89, 0x86, 0x40, 0x01, 0x00, 0x00,       # mov [rsi+140],eax
        0x50,                                     # push rax
        0x9C,                                     # pushfq
        0x48, 0x89, 0xF0,                         # mov rax, rsi
        0x48, 0xA3                                # mov [qword], rax
    ]) + struct.pack('<Q', time_data_addr)
    cave += bytearray([0x9D, 0x58, 0xE9])         # popfq, pop rax, jmp
    cave += struct.pack('<i', rel_jmp_back)

    if not safe_write(h_process, time_cave_addr, b'\x00' * 8):
        raise Exception("پاک‌سازی slot زمان ناموفق بود.")
    if not safe_write(h_process, code_start, bytes(cave)):
        raise Exception("نوشتن کد Time Hook در Cave ناموفق بود.")

    patch = b'\xE9' + struct.pack('<i', code_start - (time_hook_addr + 5)) + b'\x90'
    if not safe_write(h_process, time_hook_addr, patch):
        raise Exception("نصب Patch Time Hook روی بازی ناموفق بود.")
    return True

def fl_adopt_time_hook():
    """اتصال به Time Hookِ نصب‌مانده از جلسهٔ قبل — فقط با راستی‌آزمایی
       بایت‌های Cave (الگوی عین GoalHooker._parse_existing_cave_code)"""
    global time_hook_addr, time_cave_addr, time_data_addr
    curr = safe_read(h_process, base_addr + TIME_HOOK_OFFSET, len(TIME_ORIG_BYTES))
    if not curr or curr[0] != 0xE9:
        return False
    rel = struct.unpack('<i', curr[1:5])[0]
    cave = base_addr + TIME_HOOK_OFFSET + 5 + rel
    code = safe_read(h_process, cave + 0x20, 28)
    if not code or len(code) < 28:
        return False
    expected = bytes(bytearray(TIME_ORIG_BYTES) + bytearray([0x50, 0x9C, 0x48, 0x89, 0xF0, 0x48, 0xA3]))
    if bytes(code[:13]) != expected:
        return False
    slot = struct.unpack('<Q', code[13:21])[0]     # imm64 دستور mov [slot], rax
    if not slot or slot < 0x10000:
        return False
    time_hook_addr = base_addr + TIME_HOOK_OFFSET
    time_cave_addr = cave
    time_data_addr = slot
    return True

def fl_install_pcode_hook():
    """نصب هوک کد بازیکن (FL_2026.exe+A83964 — مشخصات کاربر):
       خط اول (4 بایت): mov [rdi+08],r12d — همیشه شمارهٔ بازیکن را می‌نویسد
       خط دوم (3 بایت): mov [rdi+0C],esi — کد پشتیبان (بازیابی هر دو خط)
       Cave هر دو دستور اصلی را اجرا + r12d را در slot ذخیره می‌کند
       و به target+7 برمی‌گردد (پچ ۷ بایتی: E9 rel32 + دو NOP).
    [SUITE v2.1.5] bridge-only when the bridge answers (kind=r12d) —
    unique site, but still owned by the bridge so it participates in
    adopt/reset/ref-count hygiene; a refusal NEVER falls back to a local
    install. Local install = standalone path only.
    """
    global pcode_hook_addr, pcode_cave_addr, pcode_data_addr
    cli = hm_bridge()
    if cli is not None:
        buf = cli.hook_request(PLAYER_CODE_HOOK_OFFSET,
                               PLAYER_CODE_ORIG_BYTES, 2, kind="r12d")
        if buf:
            pcode_hook_addr = base_addr + PLAYER_CODE_HOOK_OFFSET
            pcode_cave_addr = 0
            pcode_data_addr = buf
            print(f"[HOOK] player-code hook via BRIDGE (slot 0x{buf:X})",
                  flush=True)
            return True
        print(f"[HOOK] bridge pcode hook refused ({cli.last_error}) — "
              f"NO local fallback (the bridge owns the bytes); will retry",
              flush=True)
        return False
    pcode_hook_addr = base_addr + PLAYER_CODE_HOOK_OFFSET

    curr = safe_read(h_process, pcode_hook_addr, len(PLAYER_CODE_ORIG_BYTES))
    if curr is None:
        raise Exception("خواندن حافظه هوک کد بازیکن ممکن نشد.")
    if curr == PLAYER_CODE_ORIG_BYTES:
        pass  # حالت عادی
    elif curr[0] == 0xE9:
        raise Exception("هوک کد بازیکن قبلا نصب شده است (اجرای قبلی Restore نشده).")
    else:
        raise Exception("امضای دستور کد بازیکن مطابقت ندارد: " + curr.hex().upper() +
                        " (آفست 0xA83964 نیاز به بازبینی دارد)")

    pcode_cave_addr = allocate_near_target(h_process, pcode_hook_addr, 128)
    if not pcode_cave_addr:
        raise Exception("خطا در تخصیص حافظه برای هوک کد بازیکن.")

    pcode_data_addr = pcode_cave_addr + 0x60    # slot 8 بایتی کد بازیکن
    code_start = pcode_cave_addr + 0x20

    # ---------- Cave ----------
    # mov [rdi+08], r12d        ; دستور اصلی بازی — خط اول   (4)
    # mov [rdi+0C], esi         ; دستور اصلی بازی — خط دوم   (3)
    # push rax                  ;                              (1)
    # pushfq                    ;                              (1)
    # mov eax, r12d             ; کد بازیکن                    (3)
    # mov [data_addr], rax      ; capture کد بازیکن           (10)
    # popfq                     ;                              (1)
    # pop rax                   ;                              (1)
    # jmp rel32 -> target+7                                  (5)
    rel_jmp_back = (pcode_hook_addr + 7) - (code_start + 29)

    cave = bytearray([
        0x44, 0x89, 0x67, 0x08,                  # mov [rdi+08],r12d
        0x89, 0x77, 0x0C,                        # mov [rdi+0C],esi
        0x50,                                    # push rax
        0x9C,                                    # pushfq
        0x44, 0x89, 0xE0,                        # mov eax, r12d
        0x48, 0xA3                               # mov [qword], rax
    ]) + struct.pack('<Q', pcode_data_addr)
    cave += bytearray([0x9D, 0x58, 0xE9])        # popfq, pop rax, jmp
    cave += struct.pack('<i', rel_jmp_back)

    if not safe_write(h_process, pcode_cave_addr, b'\x00' * 128):
        raise Exception("پاک‌سازی Cave کد بازیکن ناموفق بود.")
    if not safe_write(h_process, code_start, bytes(cave)):
        raise Exception("نوشتن کد هوک کد بازیکن در Cave ناموفق بود.")

    patch = b'\xE9' + struct.pack('<i', code_start - (pcode_hook_addr + 5)) + b'\x90\x90'
    if not safe_write(h_process, pcode_hook_addr, patch):
        raise Exception("نصب Patch هوک کد بازیکن ناموفق بود.")
    return True

def fl_adopt_pcode_hook():
    """اتصال به هوک کد بازیکنِ نصب‌مانده از جلسهٔ قبل — با راستی‌آزمایی Cave"""
    global pcode_hook_addr, pcode_cave_addr, pcode_data_addr
    curr = safe_read(h_process, base_addr + PLAYER_CODE_HOOK_OFFSET, len(PLAYER_CODE_ORIG_BYTES))
    if not curr or curr[0] != 0xE9:
        return False
    rel = struct.unpack('<i', curr[1:5])[0]
    cave = base_addr + PLAYER_CODE_HOOK_OFFSET + 5 + rel
    code = safe_read(h_process, cave + 0x20, 29)
    if not code or len(code) < 29:
        return False
    expected = bytes(bytearray(PLAYER_CODE_ORIG_BYTES) + bytearray([0x50, 0x9C, 0x44, 0x89, 0xE0, 0x48, 0xA3]))
    if bytes(code[:14]) != expected:
        return False
    slot = struct.unpack('<Q', code[14:22])[0]    # imm64 دستور mov [slot], rax
    if not slot or slot < 0x10000:
        return False
    pcode_hook_addr = base_addr + PLAYER_CODE_HOOK_OFFSET
    pcode_cave_addr = cave
    pcode_data_addr = slot
    return True

def fl_install_all_hooks():
    """نصب سه هوک در لحظهٔ اتصال — عین جریان initialize در Momentum
    [SUITE v2.1.5] bridge mode: the three installs are pure REQUESTS —
    the bridge builds/adopts/shares each hook and hands back the shared
    data address; a refusal never falls back to local bytes (the periodic
    retry re-requests it). The old local adopt pre-checks read game bytes
    themselves and are now ONLY the standalone path (no bridge at all)."""
    warnings = []

    if hm_bridge() is not None:
        if not fl_install_ball_hook():
            warnings.append("هوک توپ: درخواست پل رد شد — تلاش مجدد خودکار")
        try:
            if not fl_install_time_hook():
                warnings.append("Time Hook: درخواست پل رد شد — تلاش مجدد خودکار")
        except Exception as e:
            warnings.append(f"Time Hook: {e}")
        try:
            if not fl_install_pcode_hook():
                warnings.append("Player-Code Hook: درخواست پل رد شد — تلاش مجدد خودکار")
        except Exception as e:
            warnings.append(f"Player-Code Hook: {e}")
        for w in warnings:
            print(f"[HOOK] {w}", flush=True)
        return warnings

    # --- standalone path (no bridge at all — verbatim original flow) ---

    # --- هوک توپ ---
    curr_b = safe_read(h_process, base_addr + BALL_HOOK_OFFSET, 7)
    if curr_b and curr_b[0] == 0xE9:
        if fl_adopt_ball_hook():
            warnings.append("هوک توپ: نصب جلسهٔ قبل پذیرفته شد (Adopt)")
        else:
            warnings.append("هوک توپ: Adopt ناموفق بود")
    elif curr_b and bytes(curr_b) == BALL_ORIG_BYTES:
        if not fl_install_ball_hook():
            warnings.append("خطا در نصب هوک توپ")
    else:
        warnings.append("امضای هوک توپ مطابقت ندارد")

    # --- هوک زمان (عین Momentum) ---
    try:
        fl_install_time_hook()
    except Exception as e:
        if fl_adopt_time_hook():
            warnings.append("Time Hook: نصب جلسهٔ قبل پذیرفته شد (Adopt)")
        else:
            warnings.append(f"Time Hook: {e} (از زمان جایگزین استفاده می‌شود)")

    # --- هوک کد بازیکن (A83964) ---
    try:
        fl_install_pcode_hook()
    except Exception as e:
        if fl_adopt_pcode_hook():
            warnings.append("Player-Code Hook: نصب جلسهٔ قبل پذیرفته شد (Adopt)")
        else:
            warnings.append(f"Player-Code Hook: {e} (شناسایی اسامی غیرفعال)")

    for w in warnings:
        print(f"[HOOK] {w}", flush=True)
    return warnings

def fl_verify_and_repair_hooks():
    """نوسازی سریع هوک‌ها در شروع دست جدید — عین verify_and_repair_hooks
       در Momentum (فقط هوک‌های توپ/زمان/کد بازیکن این برنامه).
       [SUITE v1.0.0] bridge mode: status + reset_request only — the bridge
       rebuilds a dead hook and hands back the (possibly new) slot."""
    global ball_hook_addr, ball_cave_addr, ball_data_addr
    global time_hook_addr, time_cave_addr, time_data_addr
    global pcode_hook_addr, pcode_cave_addr, pcode_data_addr
    rep = {"ball": "skip", "time": "skip", "pcode": "skip"}
    if not h_process or not base_addr:
        return {**rep, "_": "not-connected"}

    cli = hm_bridge()
    if cli is not None:
        plan = (
            ("ball", BALL_HOOK_OFFSET, BALL_ORIG_BYTES, 2, "xmm0"),
            ("time", TIME_HOOK_OFFSET, TIME_ORIG_BYTES, 1, "rsi"),
            ("pcode", PLAYER_CODE_HOOK_OFFSET, PLAYER_CODE_ORIG_BYTES, 2, "r12d"),
        )
        for name, off, orig, nop, kind in plan:
            try:
                st = cli.hook_status(off)
                if st and st.get("hooked") and st.get("buffer"):
                    if not st.get("adopted") and not st.get("applied"):
                        # bridge record exists but the site was restored
                        # (e.g. another consumer's release) — re-apply
                        buf = cli.hook_request(off, orig, nop, kind=kind)
                        rep[name] = "re-applied" if buf else "re-apply-fail"
                    else:
                        rep[name] = "ok(bridge)"
                        if name == "ball":
                            ball_hook_addr = base_addr + off
                            ball_data_addr = int(st["buffer"])
                        elif name == "time":
                            time_hook_addr = base_addr + off
                            time_data_addr = int(st["buffer"])
                        else:
                            pcode_hook_addr = base_addr + off
                            pcode_data_addr = int(st["buffer"])
                else:
                    buf = cli.hook_reset_request(off, orig, nop, kind=kind)
                    rep[name] = "reset-ok" if buf else "reset-fail"
                    if buf:
                        if name == "ball":
                            ball_hook_addr = base_addr + off
                            ball_cave_addr = 0
                            ball_data_addr = buf
                        elif name == "time":
                            time_hook_addr = base_addr + off
                            time_cave_addr = 0
                            time_data_addr = buf
                        else:
                            pcode_hook_addr = base_addr + off
                            pcode_cave_addr = 0
                            pcode_data_addr = buf
            except Exception as ex:
                rep[name] = f"error:{type(ex).__name__}"
        return rep

    # --- local path (verbatim original) ---
    # --- توپ: امضا E9 = نصب (Adopt) | ORIG = نصب مجدد ---
    try:
        curr = safe_read(h_process, base_addr + BALL_HOOK_OFFSET, 7)
        if curr is None:
            rep["ball"] = "read-fail"
        elif curr[0] == 0xE9:
            rep["ball"] = "ok(already)" if fl_adopt_ball_hook() else "adopt-fail"
        elif bytes(curr) == BALL_ORIG_BYTES:
            rep["ball"] = "reinstalled" if fl_install_ball_hook() else "install-fail"
        else:
            rep["ball"] = "signature-mismatch"
    except Exception as ex:
        rep["ball"] = f"error:{type(ex).__name__}"

    # --- زمان: ORIG ⇒ نصب مجدد | E9 ⇒ نصب مانده (خوب) ---
    try:
        curr = safe_read(h_process, base_addr + TIME_HOOK_OFFSET, len(TIME_ORIG_BYTES))
        if curr is None:
            rep["time"] = "read-fail"
        elif bytes(curr) == TIME_ORIG_BYTES:
            try:
                fl_install_time_hook()
                rep["time"] = "reinstalled"
            except Exception as ex:
                rep["time"] = f"install-fail:{type(ex).__name__}"
        elif curr[0] == 0xE9:
            if time_data_addr:
                rep["time"] = "ok(already)"
            else:
                rep["time"] = "adopted" if fl_adopt_time_hook() else "signature-mismatch"
        else:
            rep["time"] = "signature-mismatch"
    except Exception as ex:
        rep["time"] = f"error:{type(ex).__name__}"

    # --- کد بازیکن: همان الگوی زمان ---
    try:
        curr = safe_read(h_process, base_addr + PLAYER_CODE_HOOK_OFFSET, len(PLAYER_CODE_ORIG_BYTES))
        if curr is None:
            rep["pcode"] = "read-fail"
        elif bytes(curr) == PLAYER_CODE_ORIG_BYTES:
            try:
                fl_install_pcode_hook()
                rep["pcode"] = "reinstalled"
            except Exception as ex:
                rep["pcode"] = f"install-fail:{type(ex).__name__}"
        elif curr[0] == 0xE9:
            if pcode_data_addr:
                rep["pcode"] = "ok(already)"
            else:
                rep["pcode"] = "adopted" if fl_adopt_pcode_hook() else "signature-mismatch"
        else:
            rep["pcode"] = "signature-mismatch"
    except Exception as ex:
        rep["pcode"] = f"error:{type(ex).__name__}"

    return rep


def cleanup_hooks():
    """بازیابی کامل بایت‌های اصلی بازی + آزادسازی Cave‌ها + بستن هندل
    [SUITE v1.0.0] bridge mode: the bridge OWNS the bytes — we only send
    hook_release for the three sites and close the process handle."""
    global h_process, is_hooked
    global ball_cave_addr, time_cave_addr, pcode_cave_addr
    cli = hm_bridge()
    if cli is not None:
        for off in (BALL_HOOK_OFFSET, TIME_HOOK_OFFSET, PLAYER_CODE_HOOK_OFFSET):
            try:
                cli.hook_release(off)
            except Exception:
                pass
        ball_cave_addr = time_cave_addr = pcode_cave_addr = 0
        is_hooked = False
        print("[HOOK] bridge mode — hook references released (bytes untouched)",
              flush=True)
        if h_process:
            try:
                kernel32.CloseHandle(h_process)
            except Exception:
                pass
            h_process = None
        return

    if h_process and base_addr:
        try:
            if ball_hook_addr:
                safe_write(h_process, ball_hook_addr, BALL_ORIG_BYTES)
            if time_hook_addr:
                safe_write(h_process, time_hook_addr, TIME_ORIG_BYTES)
            if pcode_hook_addr:
                safe_write(h_process, pcode_hook_addr, PLAYER_CODE_ORIG_BYTES)
        except Exception:
            pass
        is_hooked = False

    for cave in (ball_cave_addr, time_cave_addr, pcode_cave_addr):
        if cave and h_process:
            try:
                kernel32.VirtualFreeEx(h_process, ctypes.c_void_p(cave), 0, MEM_RELEASE)
            except Exception:
                pass
    ball_cave_addr = time_cave_addr = pcode_cave_addr = 0

    if h_process:
        kernel32.CloseHandle(h_process)
        h_process = None


# -------------------------------------------------------------
# خوانندگان دادهٔ بازی (توپ / زمان / بازیکنان / کد بازیکن)
# -------------------------------------------------------------
def _mem_read_u64(addr):
    if not h_process or not addr or addr < 0x10000:
        return None
    buf = ctypes.c_uint64()
    rd = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(addr), ctypes.byref(buf), 8, ctypes.byref(rd)):
        return buf.value
    return None

def fl_read_match_state():
    """بایت وضعیت مسابقه — عین GameEngine.read_match_state در Momentum:
       128/129 = PLAYING ، بقیه = STOP"""
    if not h_process or not base_addr:
        return "STOP"
    raw = _mem_read_u8(base_addr + MATCH_STATE_OFFSET)
    if raw is not None:
        return "PLAYING" if raw in (128, 129) else "STOP"
    return "STOP"

def fl_read_game_clock():
    """منبع واحد زمان مسابقه — عین GameEngine.read_game_clock در Momentum:
       ۱) TimeHooker (RSI+0x13C دقیقه / RSI+0x140 ثانیه) — منبع اصلی
       ۲) MATCH_TIME_OFFSET (float) — فقط Fallback
       خروجی: (total_match_seconds, minutes|None, seconds|None)"""
    if time_data_addr and h_process:
        raw = safe_read(h_process, time_data_addr, 8)
        if raw:
            rsi_val = struct.unpack('<Q', raw)[0]
            if rsi_val and rsi_val >= 0x10000:
                raw_m = safe_read(h_process, rsi_val + TIME_MINUTES_OFFSET, 4)
                raw_s = safe_read(h_process, rsi_val + TIME_SECONDS_OFFSET, 4)
                if raw_m and raw_s:
                    minutes = struct.unpack('<I', raw_m)[0]
                    seconds = struct.unpack('<I', raw_s)[0]
                    # گاردهای عقلایی بودن مقادیر (عین Momentum)
                    if not (minutes > 300 or seconds > 10800):
                        return fl_compute_total_seconds(minutes, seconds), minutes, seconds
    # --- زمان جایگزین (Fallback — عین Momentum) ---
    if h_process and base_addr:
        raw = safe_read(h_process, base_addr + MATCH_TIME_OFFSET, 4)
        if raw:
            return max(0.0, struct.unpack('<f', raw)[0]), None, None
    return None, None, None

def fl_read_ball_xz():
    """مختصات توپ از slot هوک — عین GameEngine.read_ball در Momentum:
       Raw Float0 = طولی (x) ، Float1 = ارتفاع ، Float2 = عرضی (z)"""
    if not ball_data_addr or not h_process:
        return None
    raw = safe_read(h_process, ball_data_addr, 12)
    if raw:
        raw_x, _raw_h, raw_z = struct.unpack('<fff', raw)
        return raw_x, raw_z
    return None

def fl_read_player_coords(seat):
    """مختصات یک صندلی از آرایهٔ بازیکنان — زنجیرهٔ عین Momentum:
       [base+0x36F3FC0 + seat*8] → +0x7D8 → +0xA08 → +0x188 → +0xD0"""
    if not h_process or not base_addr or seat is None:
        return None
    if not (0 <= seat < PLAYER_SEAT_COUNT):
        return None
    p1 = _mem_read_u64(base_addr + PLAYERS_ARRAY_OFFSET + seat * 8)
    if not p1:
        return None
    p2 = _mem_read_u64(p1 + PLAYER_LINK_OFFSETS[0])
    if not p2:
        return None
    p3 = _mem_read_u64(p2 + PLAYER_LINK_OFFSETS[1])
    if not p3:
        return None
    p4 = _mem_read_u64(p3 + PLAYER_LINK_OFFSETS[2])
    if not p4:
        return None
    raw = safe_read(h_process, p4 + PLAYER_COORD_OFFSET, 12)
    if not raw:
        return None
    x = struct.unpack('<f', raw[0:4])[0]    # طولی
    z = struct.unpack('<f', raw[8:12])[0]   # عرضی
    return x, z

def fl_read_all_players():
    """همهٔ ۲۲ صندلی — عین GameEngine.read_players در Momentum
       (صندلی 0..10 = میزبان / 11..21 = مهمان).
       اگر «هر» صندلی نامعتبر بود None برمی‌گردد (ساخت موجودیت‌ها
       تا تیک بعدی به تعویق می‌افتد)."""
    if not h_process or not base_addr:
        return None
    out = []
    for i in range(PLAYER_SEAT_COUNT):
        seat_addr = base_addr + PLAYERS_ARRAY_OFFSET + (i * 8)
        p1 = _mem_read_u64(seat_addr)
        if not p1:
            return None
        p2 = _mem_read_u64(p1 + PLAYER_LINK_OFFSETS[0])
        if not p2:
            return None
        p3 = _mem_read_u64(p2 + PLAYER_LINK_OFFSETS[1])
        if not p3:
            return None
        p4 = _mem_read_u64(p3 + PLAYER_LINK_OFFSETS[2])
        if not p4:
            return None
        raw = safe_read(h_process, p4 + PLAYER_COORD_OFFSET, 12)
        if not raw:
            return None
        x = struct.unpack('<f', raw[0:4])[0]
        z = struct.unpack('<f', raw[8:12])[0]
        if not (math.isfinite(x) and math.isfinite(z)):
            return None
        out.append((i, x, z))
    return out

def fl_read_player_code():
    """آخرین کد بازیکن نوشته‌شده توسط هوک A83964 (r12d).
       مقدار خام 1..22 — 1..11 میزبان / 12..22 مهمان (منهای ۱۱)."""
    if not pcode_data_addr or not h_process:
        return None
    raw = safe_read(h_process, pcode_data_addr, 4)
    if raw:
        return struct.unpack('<I', raw)[0]
    return None

# -------------------------------------------------------------
# ۴. خواندن حافظه + پایگاه دادهٔ تیم‌ها (لایهٔ داده — بدون تغییر از 2017)
#    تشخیص تیم از حافظه: FL2026TeamTracker (بخش ۴٫۵) عین Momentum
# -------------------------------------------------------------
def _mem_read_u8(addr):
    if not h_process or not addr or addr < 0x10000:
        return None
    buf = ctypes.c_uint8()
    rd = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(addr), ctypes.byref(buf), 1, ctypes.byref(rd)):
        return buf.value
    return None

def _mem_read_u32(addr):
    if not h_process or not addr or addr < 0x10000:
        return None
    buf = ctypes.c_uint32()
    rd = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(addr), ctypes.byref(buf), 4, ctypes.byref(rd)):
        return buf.value
    return None

def _mem_read_i32(addr):
    if not h_process or not addr or addr < 0x10000:
        return None
    buf = ctypes.c_int32()
    rd = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(addr), ctypes.byref(buf), 4, ctypes.byref(rd)):
        return buf.value
    return None

def _mem_resolve_chain(base_address, offsets):
    curr = _mem_read_u32(base_address)
    if not curr or curr < 0x10000:
        return None
    for i, off in enumerate(offsets):
        target = (curr + off) & 0xFFFFFFFF
        if i == len(offsets) - 1:
            return target
        curr = _mem_read_u32(target)
        if not curr or curr < 0x10000:
            return None
    return None

def _mem_resolve_chain_u64(base_address, offsets):
    """[PT v2.3.0] زنجیرهٔ ۶۴بیتی — دقیقاً معنای FL2026TeamTracker._resolve_chain:
       اول deref آدرس شروع، بعد برای هر آفست به‌جز آخری deref؛ آخری فقط جمع
       می‌شود (معنای «if not curr» برای صفر/خواندن ناموفق حفظ شده است)."""
    try:
        curr = _mem_read_u64(base_address)
        if not curr:
            return None
        for i, off in enumerate(offsets):
            target = (curr + off) & 0xFFFFFFFFFFFFFFFF
            if i == len(offsets) - 1:
                return target
            curr = _mem_read_u64(target)
            if not curr:
                return None
        return None
    except Exception:
        return None

def _mem_resolve_chain_u32(base_address, offsets):
    """[PT v2.3.2] زنجیره با «پوینترهای ۴ بایتی» — طبق تأکید صریح کاربر
    («پوینتر ۴ بایتی» ، «هر دو آدرس ۴ بایت هستند») سلول‌های این زنجیره باید
    ۴ بایتی خوانده شوند. خواندن ۸ بایتی، ۴ بایتِ بعدیِ سلول را به‌عنوان
    dword بالا بلعیده و آدرس‌ها را خراب می‌کند (دلیلِ «تیم‌ها پیدا نمی‌شوند»
    در تست میدانی). معنا دقیقاً عین _mem_resolve_chain_u64 است: اول deref
    آدرس شروع، برای هر آفست به‌جز آخری deref، آخری فقط جمع می‌شود."""
    try:
        curr = _mem_read_u32(base_address)
        if not curr:
            return None
        for i, off in enumerate(offsets):
            target = (curr + off) & 0xFFFFFFFF
            if i == len(offsets) - 1:
                return target
            curr = _mem_read_u32(target)
            if not curr:
                return None
        return None
    except Exception:
        return None

_PT_CHAIN_DIAG = {"t": 0.0, "msg": None}

def _pt_chain_diag(msg, force=False):
    """[PT v2.3.2] لاگ تشخیصی میدانی — هر تغییر وضعیت زنجیره یک خط
    کنترل‌شده در backend_log می‌نویسد (حداقل فاصله ۳ ثانیه؛ force برای
    پیام‌های موفقیت). با این لاگ، اولین تست میدانی نشان می‌دهد کدام hop
    با Cheat Engine فرق دارد (پهنای deref، آدرس نهایی، مقادیر خام)."""
    now = time.monotonic()
    if not force and msg == _PT_CHAIN_DIAG["msg"] \
            and now - _PT_CHAIN_DIAG["t"] < 3.0:
        return
    if not force and now - _PT_CHAIN_DIAG["t"] < 0.5:
        return
    _PT_CHAIN_DIAG["t"] = now
    _PT_CHAIN_DIAG["msg"] = msg
    try:
        print(f"[PT-CHAIN] {msg}", flush=True)
    except Exception:
        pass

def fl_read_team_ids():
    """[PT v2.3.0/v2.3.2] شناسهٔ تیم میزبان/مهمان با زنجیرهٔ کاربر:
       [[base+0x03705E20]+0x98]+0x228 ⇒ ۴ بایت = میزبان ؛ +۴ بایت بعد = مهمان.
       [v2.3.2] پوینترهای زنجیره «۴ بایتی» خوانده می‌شوند (تأکید کاربر) —
       اندازه‌گیری میدانی کاربر: میزبان @6E948708 و مهمان @6E94870C یعنی
       مهمان = آدرس میزبان + ۴ بایت (معادل آخرین آفست 0x22C) و هر دو مقدار
       ۴ بایتی‌اند. اگر مسیر ۴ بایتی اعتبار نگشت، مسیر ۸ بایتیِ قدیم به‌عنوان
       fallback امتحان می‌شود؛ هر دو مسیر در پایان همان اعتبارسنجی دیتابیس
       PT را دارند (مقدار زبالهٔ حافظه هرگز تیم نمی‌سازد)."""
    PTx = pt_active()
    if PTx is None or not h_process or not base_addr:
        return None
    for deref, tag in ((_mem_resolve_chain_u32, "u32"),
                       (_mem_resolve_chain_u64, "u64")):
        final = deref(base_addr + TEAM_ID_PTR_OFFSET, TEAM_ID_CHAIN)
        if final is None:
            _pt_chain_diag(f"{tag}: chain resolve failed "
                           f"(base+{TEAM_ID_PTR_OFFSET:#x} {TEAM_ID_CHAIN})")
            continue
        home = _mem_read_u32(final)
        # مهمان = آدرس میزبان + ۴ بایت (کاربر: 6E948708 → 6E94870C) — نه +۱
        away = _mem_read_u32(final + 4)
        if home is None or away is None:
            _pt_chain_diag(f"{tag}: id read failed at final={final:#x}")
            continue
        home, away = int(home), int(away)
        if PTx.has_team(home) and PTx.has_team(away):
            _pt_chain_diag(f"{tag}: OK final={final:#x} home={home} "
                           f"({PTx.team_name(home)}) away={away} "
                           f"({PTx.team_name(away)})", force=True)
            return (home, away)
        _pt_chain_diag(f"{tag}: rejected final={final:#x} raw home={home} "
                       f"away={away} (not in PT db)")
    return None

def fl_read_player_slot():
    """[PT v2.3.0/v2.3.2] اسلاتِ بازیکن جاری: [[base+0x036F4270]+0x74] — ۱ بایت.
       این مقدار «Slot بازیکن در لیست تیمش» است (مثلاً بارسلونا 04 =
       Eric García)؛ با teams_players_PES2021.txt به نام/پس‌زمینه/سن/
       شماره پیراهن و PES ID (عکس چهره از Asset.zip) ترجمه می‌شود.
       [v2.3.2] deref های زنجیره ۴ بایتی (پوینتر ۴ بایتی — تأکید کاربر)
       با fallback ۸ بایتی؛ خودِ Slot همان ۱ بایت می‌ماند."""
    PTx = pt_active()
    if PTx is None or not h_process or not base_addr:
        return None
    for deref in (_mem_resolve_chain_u32, _mem_resolve_chain_u64):
        final = deref(base_addr + PLAYER_SLOT_PTR_OFFSET,
                      PLAYER_SLOT_CHAIN)
        if final is None:
            continue
        slot = _mem_read_u8(final)
        if slot is None:
            continue
        return slot
    return None

def classify_team_selection(a, b):
    """نسخه ۱۲٫۰ — هویت تیم = جفت خام (league_id, val) عین momentum
    (TeamIdentityTracker: ident = (league, img) خام — بدون lookup برعکس).
    نسخه ۱۶٫۰ — مرجع نام/رستر: pes2017_teams.json؛ مرجع کمکی نام:
    pes2017_leagues_data.json؛ مرجع لوگو: مسیر دلخواه فایل یا
    Football_Database/{lg}/{val}.png — برای «همهٔ» تیم‌های بازی کار می‌کند.
    اعتبارسنجی عین momentum: league در 0..25، val >= 0"""
    try:
        lg, val = int(a), int(b)
    except (TypeError, ValueError):
        return None
    if not (0 <= lg <= 36) or val < 0:
        return None
    return (lg, val)

# ---------------------------------------------------------------------
# نسخه ۱۱٫۰ — منبع رسمی نام تیم‌ها: pes2017_leagues_data.json (عین momentum)
# ساختار: { "league": { "teams": { "team": {"name": ..., "colors": {...}} } } }
# اولویت مسیر: ۱) Football_Database/pes2017_leagues_data.json کنار اسکریپت
#              ۲) pes2017_leagues_data.json کنار اسکریپت (سازگاری)
# خواندن با کش mtime است — اگر کاربر فایل را ویرایش کند بدون ری‌استارت اعمال می‌شود.
# نسخه ۱۶٫۰ — این فایل فقط «کمکی» است؛ مرجع اصلی pes2017_teams.json است.
# نسخه ۱۳٫۰ — لایهٔ مستعار pes2017_team_aliases.json (پایین‌تر) + شاهدسنجی
# خواندن جبرانی اضافه شد (رفع «اسپانیا L20T49» و «تیم خیالی وسط بازی»).
# ---------------------------------------------------------------------
TEAM_DATA_JSON_CANDIDATES = (
    os.path.join(SCRIPT_DIR, "Football_Database", "pes2017_leagues_data.json"),
    os.path.join(SCRIPT_DIR, "pes2017_leagues_data.json"),
)
_team_json_cache = {"path": None, "mtime": None, "data": None,
                    "missing_logged": False}
_team_json_lock = threading.Lock()

def _team_json_data():
    """خواندن pes2017_leagues_data.json با کش mtime — عین رویکرد momentum
    (فایل نبود/خراب بود ⇒ None و ادامه با pes2017_teams.json/مستعارها)"""
    active_path = None
    for cand in TEAM_DATA_JSON_CANDIDATES:
        try:
            os.path.getmtime(cand)
            active_path = cand
            break
        except OSError:
            continue
    if active_path is None:
        with _team_json_lock:
            if not _team_json_cache["missing_logged"]:
                _team_json_cache["missing_logged"] = True
                print("[TEAM] pes2017_leagues_data.json not found - tried: "
                      + " ; ".join(TEAM_DATA_JSON_CANDIDATES)
                      + " - names from pes2017_teams.json/alias file")
            _team_json_cache["data"] = None
            _team_json_cache["path"] = None
            _team_json_cache["mtime"] = None
        return None
    try:
        mtime = os.path.getmtime(active_path)
    except OSError:
        return None
    with _team_json_lock:
        if (_team_json_cache["data"] is not None
                and _team_json_cache["mtime"] == mtime
                and _team_json_cache["path"] == active_path):
            return _team_json_cache["data"]
    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("root of pes2017_leagues_data.json is not a dict")
    except Exception:
        with _team_json_lock:
            _team_json_cache["data"] = None
            _team_json_cache["path"] = active_path
            _team_json_cache["mtime"] = mtime
        return None
    with _team_json_lock:
        _team_json_cache["data"] = data
        _team_json_cache["path"] = active_path
        _team_json_cache["mtime"] = mtime
    return data

# ---------------------------------------------------------------------
# نسخه ۱۳٫۰ — لایهٔ مستعار تیم‌ها: pes2017_team_aliases.json
#
# مسئله: مقدار خامِ خوانده‌شده از حافظهٔ بازی برای «همان» تیم می‌تواند با
# شمارهٔ پوشه‌های دانلودشده (players/{lg}/{tm}/ و Football_Database/{lg}/{tm}.png)
# فرق کند — مثال کاربر: اسپانیا در پوشه‌ها 20/28 است ولی بازی 20/49 گزارش
# می‌کند ⇒ نام/لوگو/رستر پیدا نمی‌شد و «L20T49» نمایش داده می‌شد؛ یا خواندن
# جبرانی خارج از منو مقدار بی‌معنا می‌گرفت و «تیم خیالی» ثبت می‌شد.
#
# راه‌حل: فایل اختیاری کنار اسکریپت (بدون ری‌استارت اعمال می‌شود — کش mtime):
#   {
#     "aliases": { "20:49": [20, 28] },   ← شناسهٔ خام بازی → شناسهٔ واقعی پوشه‌ها
#     "names":   { "20:49": "SPAIN" }     ← نام دستی برای شناسه‌ای که پوشه ندارد
#   }
# ترتیب اعمال در apply_team_detection: شناسهٔ خام → alias_team_key → بقیهٔ زنجیره
# (نام/لوگو/رستر/عکس همه با شناسهٔ واقعی پوشه‌ها کار می‌کنند)
# ---------------------------------------------------------------------
ALIAS_JSON_CANDIDATES = (
    os.path.join(SCRIPT_DIR, "pes2017_team_aliases.json"),
    os.path.join(SCRIPT_DIR, "Football_Database", "pes2017_team_aliases.json"),
)
_alias_cache = {"path": None, "mtime": None, "data": None, "logged": False}
_alias_lock = threading.Lock()
_catchup_ignored_logged = set()

def _alias_data():
    """خواندن pes2017_team_aliases.json با کش mtime (عین رویکرد leagues_data);
    فایل نبود/خراب بود ⇒ None و ادامه بدون مستعار"""
    active_path = None
    for cand in ALIAS_JSON_CANDIDATES:
        try:
            os.path.getmtime(cand)
            active_path = cand
            break
        except OSError:
            continue
    if active_path is None:
        with _alias_lock:
            _alias_cache["data"] = None
            _alias_cache["path"] = None
            _alias_cache["mtime"] = None
        return None
    try:
        mtime = os.path.getmtime(active_path)
    except OSError:
        return None
    with _alias_lock:
        if (_alias_cache["data"] is not None
                and _alias_cache["mtime"] == mtime
                and _alias_cache["path"] == active_path):
            return _alias_cache["data"]
    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("root of pes2017_team_aliases.json is not a dict")
    except Exception:
        with _alias_lock:
            _alias_cache["data"] = None
            _alias_cache["path"] = active_path
            _alias_cache["mtime"] = mtime
        return None
    with _alias_lock:
        first_load = not _alias_cache["logged"]
        _alias_cache["logged"] = True
        _alias_cache["data"] = data
        _alias_cache["path"] = active_path
        _alias_cache["mtime"] = mtime
    if first_load:
        try:
            print(f"[TEAM] pes2017_team_aliases.json loaded: "
                  f"{len(data.get('aliases') or {})} alias(es), "
                  f"{len(data.get('names') or {})} name(s) from {active_path}")
        except Exception:
            pass
    return data

def _alias_raw_id(team_key):
    """کلید (lg,tm) → شناسهٔ متنی 'lg:tm' برای جست‌وجو در فایل مستعارها"""
    try:
        return f"{int(team_key[0])}:{int(team_key[1])}"
    except Exception:
        return None

def alias_team_key(team_key):
    """کلید خام تشخیصی → کلید واقعی پوشه‌ها (بخش aliases)؛
    بدون نگاشت معتبر ⇒ همان کلید ورودی (بدون تغییر)"""
    if team_key is None:
        return None
    raw = _alias_raw_id(team_key)
    if raw is None:
        return team_key
    data = _alias_data()
    if not data:
        return team_key
    ent = (data.get("aliases") or {}).get(raw)
    if isinstance(ent, (list, tuple)) and len(ent) == 2:
        try:
            ck = (int(ent[0]), int(ent[1]))
            if 0 <= ck[0] <= 36 and ck[1] >= 0:
                return ck
        except Exception:
            pass
    return team_key

def alias_team_name(team_key):
    """نام دستی از بخش names — برای کلیدی که در هیچ منبع دیگری نیست؛
    ناشناخته ⇒ None"""
    if team_key is None:
        return None
    raw = _alias_raw_id(team_key)
    if raw is None:
        return None
    data = _alias_data()
    if not data:
        return None
    v = (data.get("names") or {}).get(raw)
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None

# ---------------------------------------------------------------------
# نسخه ۱۵٫۰ — دیتابیس قابل‌ویرایش کاربر: pes2017_teams.json
#
# یک فایل واحد برای «نام نمایشی تیم + مسیر لوگو/پرچم + نام و عکس تک‌تک
# بازیکنان». کاربر خودش این فایل را ویرایش می‌کند (مثلاً اضافه‌کردن تیم‌های
# ملی) و برنامه بدون ری‌استارت تغییرات را می‌گیرد (کش mtime — عین leagues_data).
#
# ساختار:
# {
#   "teams": {
#     "league:team": {                      ← همان شماره‌های پوشه‌های واقعی
#         "name":  "SPAIN"  یا  null,       ← null = خودکار (leagues_data)
#         "flag":  "Football_Database/20/28.png"  یا null,  ← null = مسیر پیش‌فرض
#         "players": {
#             "9": "L. Messi",                                   ← فقط نام
#             "10": {"name": "X. Y", "photo": "players/7/3/10.png"}  ← نام + عکس
#         }
#     }
#   }
# }
#
# قواعد:
#  • کلید = "league:team" — هم با شمارهٔ پوشه‌ها («20:28») و هم با شناسهٔ خام
#    بازی («20:49») کار می‌کند؛ لودر هر دو سبک را می‌گردد (نسخه ۱۶٫۰). برای
#    لوگوی قراردادی بهتر است نگاشت در بخش aliases فایل pes2017_team_aliases.json
#    هم بماند (مثال: «20:49»: [20, 28]).
#  • مسیر نسبی نسبت به پوشهٔ برنامه است؛ / و \ هر دو پذیرفته می‌شوند.
#  • اگر مسیر دلخواه پیدا نشد، مسیر پیش‌فرضِ «همان تیم» امتحان می‌شود —
#    برنامه هرگز لوگوی/عکسِ تیم دیگری نمایش نمی‌دهد (درس باگ v11).
#  • اگر فایل اصلاً نباشد، برنامه یک «اسکلت خالیِ مستند» می‌سازد (نسخه ۱۶٫۰ —
#    لیست داخلی حذف شد؛ دیتابیس کامل را از ZIP کپی کنید یا دستی پر کنید).
# ---------------------------------------------------------------------
TEAMS_JSON_CANDIDATES = (
    os.path.join(SCRIPT_DIR, "pes2017_teams.json"),
    os.path.join(SCRIPT_DIR, "Football_Database", "pes2017_teams.json"),
)
_teams_db_json_cache = {"path": None, "mtime": None, "data": None,
                        "logged": False, "seed_tried": False}
_teams_db_json_lock = threading.Lock()

def _seed_teams_json():
    """نسخه ۱۶٫۰ — اگر pes2017_teams.json نبود → ساخت «اسکلت خالیِ مستند».
    هیچ لیست داخلی وجود ندارد؛ دیتابیس کامل (۷۵ تیم/۱۷۵۲ بازیکن) همراه ZIP
    ارائه می‌شود — این فقط برای اولین اجرای بدون فایل است."""
    path = TEAMS_JSON_CANDIDATES[0]
    try:
        doc = {
            "_help": {
                "what": "Editable team database: display name + flag/logo path + "
                        "player names and photo paths. Edits apply WITHOUT restart "
                        "(mtime cache). This file is the ONLY source of team/player "
                        "data (v16.0 - no builtin list).",
                "key": "'league:team' = the same numbers as the real folders "
                       "players/{lg}/{tm}/ and Football_Database/{lg}/{tm}.png",
                "name": "string = shown everywhere; null = automatic "
                        "(pes2017_leagues_data.json / alias names)",
                "flag": "path to the 512x512 crest image; null = default "
                        "Football_Database/{lg}/{tm}.png; relative paths start at "
                        "the program folder; if a custom path is missing the default "
                        "path of the SAME team is tried (a wrong team's logo is never shown)",
                "players": "'code': 'Name'  (photo = default players/{lg}/{tm}/{code}.png)  "
                           "or  'code': {'name': 'Name', 'photo': 'custom/path.png'}",
                "note": "If the raw in-game id differs from the folder ids "
                        "(example: Spain 20:49 -> 20:28), also keep the mapping in "
                        "pes2017_team_aliases.json (aliases section).",
            },
            "teams": {},
        }
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2)
        print(f"[TEAM] pes2017_teams.json NOT FOUND - created EMPTY skeleton: {path}",
              flush=True)
        print("[TEAM] teams/players come ONLY from this file - copy the full "
              "pes2017_teams.json (shipped in the ZIP) or fill it manually",
              flush=True)
        return True
    except Exception as ex:
        print(f"[TEAM] could not seed pes2017_teams.json: {ex}", flush=True)
        return False

def _teams_db_json_data():
    """خواندن pes2017_teams.json با کش mtime (عین leagues_data/aliases)؛
    فایل نبود ⇒ بذر خودکار یک‌بار، سپس خواندن؛ خراب ⇒ None (فقط لیست داخلی)"""
    active_path = None
    for cand in TEAMS_JSON_CANDIDATES:
        try:
            os.path.getmtime(cand)
            active_path = cand
            break
        except OSError:
            continue
    if active_path is None:
        with _teams_db_json_lock:
            if not _teams_db_json_cache["seed_tried"]:
                _teams_db_json_cache["seed_tried"] = True
                seed_ok = _seed_teams_json()
            else:
                seed_ok = False
        if seed_ok:
            try:
                os.path.getmtime(TEAMS_JSON_CANDIDATES[0])
                active_path = TEAMS_JSON_CANDIDATES[0]
            except OSError:
                active_path = None
        if active_path is None:
            with _teams_db_json_lock:
                _teams_db_json_cache["data"] = None
                _teams_db_json_cache["path"] = None
                _teams_db_json_cache["mtime"] = None
            return None
    try:
        mtime = os.path.getmtime(active_path)
    except OSError:
        return None
    with _teams_db_json_lock:
        if (_teams_db_json_cache["data"] is not None
                and _teams_db_json_cache["mtime"] == mtime
                and _teams_db_json_cache["path"] == active_path):
            return _teams_db_json_cache["data"]
    try:
        with open(active_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError("root of pes2017_teams.json is not a dict")
    except Exception:
        with _teams_db_json_lock:
            _teams_db_json_cache["data"] = None
            _teams_db_json_cache["path"] = active_path
            _teams_db_json_cache["mtime"] = mtime
        return None
    with _teams_db_json_lock:
        first_load = not _teams_db_json_cache["logged"]
        _teams_db_json_cache["logged"] = True
        _teams_db_json_cache["data"] = data
        _teams_db_json_cache["path"] = active_path
        _teams_db_json_cache["mtime"] = mtime
    if first_load:
        try:
            print(f"[TEAM] pes2017_teams.json loaded: "
                  f"{len(data.get('teams') or {})} team(s) from {active_path}",
                  flush=True)
        except Exception:
            pass
    return data

def _alias_reverse_raw(team_key):
    """نسخه ۱۶٫۰ — وارونِ نگاشت مستعارها: کلید واقعی پوشه‌ها → شناسهٔ خام بازی.
    مثال: aliases «20:49»: [20, 28] ⇒ برای (20, 28) رشتهٔ «20:49» برگردانده
    می‌شود. کاربرد: کاربر ممکن است در pes2017_teams.json تیم را با شناسهٔ خام
    بازی کلید بزند (اسپانیا «20:49») در حالی که زنجیره با شناسهٔ پوشه‌ها
    ((20, 28)) کار می‌کند — با این جست‌وجو هر دو سبک کلیدزنی کار می‌کند."""
    if team_key is None:
        return None
    try:
        lg, tm = int(team_key[0]), int(team_key[1])
    except Exception:
        return None
    data = _alias_data()
    if not data:
        return None
    for raw, target in (data.get("aliases") or {}).items():
        try:
            if (isinstance(target, (list, tuple)) and len(target) == 2
                    and int(target[0]) == lg and int(target[1]) == tm):
                return str(raw)
        except Exception:
            continue
    return None

def _teams_db_entry(team_key):
    """ورودی کامل تیم از pes2017_teams.json — dict یا None
    نسخه ۱۶٫۰ — جست‌وجوی کلید به سه شکل: «lg:tm» مستقیم، شکل کانونیِ
    مستعارشده، و وارونِ مستعار (شناسهٔ خام بازی) — تا هم کلیدزنی با
    شناسهٔ پوشه‌ها («20:28») و هم با شناسهٔ خام بازی («20:49») کار کند."""
    if team_key is None:
        return None
    raw = _alias_raw_id(team_key)
    if raw is None:
        return None
    data = _teams_db_json_data()
    if not data:
        return None
    teams = data.get("teams") or {}
    ent = teams.get(raw)
    if isinstance(ent, dict):
        return ent
    try:
        ck = alias_team_key(team_key)
        if ck != team_key:
            ent = teams.get(_alias_raw_id(ck))
            if isinstance(ent, dict):
                return ent
    except Exception:
        pass
    try:
        rev = _alias_reverse_raw(team_key)
        if rev and rev != raw:
            ent = teams.get(rev)
            if isinstance(ent, dict):
                return ent
    except Exception:
        pass
    return None

def team_json_name(team_key):
    """نام نمایشی از pes2017_teams.json — فقط اگر کاربر صریحاً مقدار داده باشد
    (null/رشتهٔ خالی ⇒ None تا منابع خودکار حفظ شوند)"""
    ent = _teams_db_entry(team_key)
    if not ent:
        return None
    v = ent.get("name")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None

def team_json_flag(team_key):
    """مسیر دلخواه لوگو/پرچم از pes2017_teams.json — رشته یا None"""
    ent = _teams_db_entry(team_key)
    if not ent:
        return None
    v = ent.get("flag")
    if isinstance(v, str) and v.strip():
        return v.strip()
    return None

def _resolve_asset_path(p):
    """مسیر نسبی نسبت به پوشهٔ برنامه؛ / و \\ هر دو؛ نامعتبر ⇒ None"""
    if not isinstance(p, str) or not p.strip():
        return None
    p = p.strip()
    if os.path.isabs(p):
        return p
    norm = p.replace("\\", "/").strip("/")
    if not norm:
        return None
    return os.path.join(SCRIPT_DIR, *norm.split("/"))

def team_json_player_entry(team_key, code):
    """ورودی بازیکن از pes2017_teams.json → {"name": str|None, "photo": str|None}
    دو شکل پذیرفته می‌شود: "9": "Name"  یا  "9": {"name": ..., "photo": ...}"""
    if code is None or team_key is None:
        return None
    ent = _teams_db_entry(team_key)
    if not ent:
        return None
    players = ent.get("players")
    if not isinstance(players, dict):
        return None
    v = None
    try:
        v = players.get(str(int(code)))
    except Exception:
        v = None
    if v is None:
        v = players.get(str(code))
    if isinstance(v, str):
        return {"name": v.strip() or None, "photo": None}
    if isinstance(v, dict):
        nm = v.get("name")
        ph = v.get("photo")
        return {"name": (nm.strip() or None) if isinstance(nm, str) else None,
                "photo": (ph.strip() or None) if isinstance(ph, str) else None}
    return None

def team_roster(team_key):
    """رستر نهایی {code: name} — [PT v2.3.0] حالت PT: کلید = Slot بازیکن در
    لیست تیم (۰..۲۵ — مستقیم از teams_players_PES2021.txt)؛ در غیر این صورت
    فقط pes2017_teams.json (نسخه ۱۶٫۰)؛ کلیدهای عددی به int نرمال می‌شوند"""
    PTx = pt_active()
    if PTx is not None and PTData is not None \
            and PTData.PTDataSource.is_pt_key(team_key):
        roster = {}
        for slot, info in PTx.players(int(team_key[1])).items():
            nm = (info or {}).get("name")
            if nm:
                roster[int(slot)] = nm
        return roster
    roster = {}
    jent = _teams_db_entry(team_key)
    if jent:
        players = jent.get("players")
        if isinstance(players, dict):
            for k, v in players.items():
                nm = None
                if isinstance(v, str):
                    nm = v.strip() or None
                elif isinstance(v, dict):
                    nv = v.get("name")
                    nm = (nv.strip() or None) if isinstance(nv, str) else None
                if nm is None:
                    continue
                try:
                    ck = int(k)
                except Exception:
                    ck = k
                roster[ck] = nm
    return roster

def team_name_from_json(team_key):
    """نام تیم (league, team) از pes2017_leagues_data.json — منطق عین
    TeamColorResolver.team_name در momentum: کلیدهای رایج نام بررسی می‌شوند؛
    در ساختارهای قدیمی هر مقدار رشته‌ای غیر colors هم پذیرفته می‌شود.
    ناشناخته ⇒ None"""
    if team_key is None:
        return None
    try:
        league, team = int(team_key[0]), int(team_key[1])
    except Exception:
        return None
    data = _team_json_data()
    if not data:
        return None
    try:
        lnode = data.get(str(league)) or {}
        tnode = (lnode.get("teams") or {}).get(str(team))
        if not isinstance(tnode, dict):
            return None
        for key in ("name", "Name", "team_name", "teamName", "title",
                    "label", "short_name", "displayName"):
            v = tnode.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()
        for k, v in tnode.items():
            if isinstance(v, str) and v.strip() and k.lower() != "colors":
                return v.strip()
        return None
    except Exception:
        return None

def team_display_name(team_key):
    """نام نمایشی تیم — اولویت ۰: [PT v2.3.0] teams_players_PES2021.txt
       (کلید (-1, team_id) — دیتابیس رسمی ۷۴۹ تیمی)
       اولویت ۱: pes2017_teams.json (دیتابیس قابل‌ویرایش کاربر —
       نسخه ۱۵٫۰؛ فقط وقتی کاربر صریحاً نام گذاشته باشد)
       اولویت ۲: pes2017_leagues_data.json (مرجع رسمی momentum)
       اولویت ۳: بخش names در pes2017_team_aliases.json
       ناشناخته ⇒ شناسه L{league}T{team} (نسخه ۱۶٫۰ — لیست داخلی حذف شد)
       (مطابق momentum: تشخیص تیم باید همیشه برای کاربر visible باشد)"""
    PTx = pt_active()
    if PTx is not None and PTData is not None \
            and PTData.PTDataSource.is_pt_key(team_key):
        return PTx.team_name(int(team_key[1])) or f"TEAM {int(team_key[1])}"
    nm = team_json_name(team_key)
    if nm:
        return nm
    nm = team_name_from_json(team_key)
    if nm:
        return nm
    nm = alias_team_name(team_key)
    if nm:
        return nm
    try:
        return f"L{int(team_key[0])}T{int(team_key[1])}"
    except Exception:
        return "UNKNOWN TEAM"

def team_logo_path(key):
    """مسیر لوگوی 512x512 — اولویت ۰: [PT v2.3.0] Asset.zip →
    Teams/{team_id}.png (استخراج تک‌فایلی با کش PT_Cache)؛ اولویت ۱: مسیر دلخواه
    کاربر در pes2017_teams.json (نسخه ۱۵٫۰)؛ اولویت ۲: قرارداد momentum
    Football_Database/{league}/{team}.png (نسخه ۱۱٫۰ — fallback ترتیب برعکس حذف شده؛ هر دو مسیر برای «همان تیم» اند و
    برنامه هرگز لوگوی تیم دیگری نمایش نمی‌دهد؛ نبود تصویر = نمایش متنی)"""
    PTx = pt_active()
    if PTx is not None and PTData is not None \
            and PTData.PTDataSource.is_pt_key(key):
        try:
            return PTx.team_logo_path(int(key[1]))
        except Exception:
            return None
    if key is None:
        return None
    try:
        lg, tm = int(key[0]), int(key[1])
    except Exception:
        return None
    p_custom = _resolve_asset_path(team_json_flag(key))
    if p_custom:
        try:
            if os.path.isfile(p_custom):
                return p_custom
        except Exception:
            pass
    p = os.path.join(SCRIPT_DIR, "Football_Database", str(lg), f"{tm}.png")
    try:
        return p if os.path.isfile(p) else None
    except Exception:
        return None

def team_photo_dir(key):
    """پوشه عکس‌های چهره تیم: players/{league}/{team}/ (عکس‌ها 360x360)"""
    if key is None:
        return None
    lg, tm = key
    return os.path.join(PLAYERS_DIR, str(lg), str(tm))

def team_has_evidence(team_key):
    """نسخه ۱۳٫۰ — آیا برای این کلید «شاهد» واقعی وجود دارد؟
    [PT v2.3.0] حالت PT: شاهد = وجود Team ID در teams_players_PES2021.txt.
    شاهد = عضویت در pes2017_teams.json یا نام در leagues_data.json یا بخش
    names مستعارها یا فایل لوگو (Football_Database/{lg}/{tm}.png) یا پوشهٔ عکس
    (players/{lg}/{tm}/) — نسخه ۱۶٫۰: لیست داخلی حذف شد.
    کاربرد: خواندن جبرانیِ خارج از منوی ۴۴ فقط وقتی ثبت می‌شود که شاهد باشد —
    یعنی مقدار زبالهٔ حافظه در میانهٔ بازی هرگز «تیم خیالی» نمی‌سازد
    (رفع گزارش L20T49 اسپانیا و کلاً «تیمی که چند دقیقه بعد عوض می‌شد»)."""
    PTx = pt_active()
    if PTx is not None and PTData is not None \
            and PTData.PTDataSource.is_pt_key(team_key):
        try:
            return PTx.has_team(int(team_key[1]))
        except Exception:
            return False
    if team_key is None:
        return False
    try:
        lg, tm = int(team_key[0]), int(team_key[1])
    except Exception:
        return False
    if _teams_db_entry((lg, tm)) is not None:
        return True
    if team_name_from_json((lg, tm)):
        return True
    if alias_team_name((lg, tm)):
        return True
    try:
        if os.path.isfile(os.path.join(SCRIPT_DIR, "Football_Database",
                                       str(lg), f"{tm}.png")):
            return True
        if os.path.isdir(os.path.join(PLAYERS_DIR, str(lg), str(tm))):
            return True
    except Exception:
        pass
    return False

# -------------------------------------------------------------
# نسخه ۱۵٫۱ — مقدار اولیهٔ نام نمایشی و رستر از pes2017_teams.json
# (اگر کاربر در فایل نام/رستر گذاشته باشد، حتی قبل از اولین تشخیص هم
#  اعمال می‌شود — نسخه ۱۶٫۰: دیگر هیچ منبع داخلی وجود ندارد). این همان زنجیرهٔ اولویتِ کامل
# است: pes2017_teams.json → pes2017_leagues_data.json → مستعارها.
# با اولین تشخیص تیم، update_team_assignment همین مقادیر را دوباره از همان
# زنجیره تازه‌سازی می‌کند — پس رفتار در تمام طول برنامه یکدست است.
# -------------------------------------------------------------
home_team_name = team_display_name(home_team_key)
away_team_name = team_display_name(away_team_key)
home_players_dict = team_roster(home_team_key)
away_players_dict = team_roster(away_team_key)
def update_team_assignment(home_key, away_key):
    """اعمال تیم‌های تشخیص‌داده‌شده روی اسم‌ها، رستر بازیکنان و لیست موجودیت‌ها"""
    global home_team_key, away_team_key, home_team_name, away_team_name
    global home_players_dict, away_players_dict, entities_ready

    home_team_key = home_key
    away_team_key = away_key
    home_team_name = team_display_name(home_key)
    away_team_name = team_display_name(away_key)
    # نسخه ۱۵٫۰ — رستر از دیتابیس قابل‌ویرایش pes2017_teams.json (لیست داخلی fallback)
    home_players_dict = team_roster(home_key)
    away_players_dict = team_roster(away_key)

    with entities_lock:
        for e in entities:
            if e.get("team") == 1: e["team_name"] = home_team_name
            elif e.get("team") == 2: e["team_name"] = away_team_name

    entities_ready = True

def apply_team_detection(side, a, b):
    """اعمال نتیجه تشخیص تیم (عین momentum) + بروزرسانی مسیر لوگوی باشگاه
       (نسخه ۱۲٫۰ — رفع «میزبانی که ناگهان رئال‌مادرید می‌شود»:
       منطق _other_team_key حذف شد — هرگز سمت مقابل به دیفالت forcibly
       بازنویسی نمی‌شود؛ هر سمت فقط با تشخیص واقعی خودش عوض می‌شود.
       لوگوی باقی‌مانده هم با تغییر تیم پاک می‌شود — عین momentum:
       نبود تصویر = نمایش متنی «میزبان/مهمان»)
       [PT v2.3.0] حالت جدید: a = PT_TEAM_LEAGUE_TAG (-1) و b = Team ID خام
       از زنجیرهٔ پوینتری جدید؛ اعتبار = وجود ID در teams_players_PES2021.txt."""
    global home_team_id_info, away_team_id_info, home_team_logo, away_team_logo
    PTx = pt_active()
    if PTx is not None and PTData is not None:
        try:
            pt_mode = (int(a) == PTData.PT_TEAM_LEAGUE_TAG)
        except Exception:
            pt_mode = False
    else:
        pt_mode = False
    if pt_mode:
        try:
            key = PTData.PTDataSource.make_key(int(b)) \
                  if PTx.has_team(int(b)) else None
        except Exception:
            key = None
    else:
        key = classify_team_selection(a, b)
        if key is not None:
            # نسخه ۱۳٫۰ — نگاشت مستعار: شناسهٔ خام بازی → شناسهٔ واقعی پوشه‌ها
            # (مثال کاربر: بازی 20/49 گزارش می‌کند ولی پوشه‌ها players/20/28 هستند؛
            # بعد از نگاشت، نام/لوگو/رستر/عکس همه با شناسهٔ واقعی کار می‌کنند)
            key = alias_team_key(key)
    logo = team_logo_path(key)
    if side == "home":
        changed = (home_team_id_info != (a, b))
        home_team_id_info = (a, b)
        if key and key != home_team_key:
            home_team_logo = logo            # لوگوی تیم جدید یا None (پاک‌سازی)
            update_team_assignment(key, away_team_key)   # سمت مقابل دست‌نخورده
        elif key and key == home_team_key and logo and logo != home_team_logo:
            home_team_logo = logo            # همان تیم — مسیر تازه‌شده
        return changed
    else:
        changed = (away_team_id_info != (a, b))
        away_team_id_info = (a, b)
        if key and key != away_team_key:
            away_team_logo = logo            # لوگوی تیم جدید یا None (پاک‌سازی)
            update_team_assignment(home_team_key, key)   # سمت مقابل دست‌نخورده
        elif key and key == away_team_key and logo and logo != away_team_logo:
            away_team_logo = logo            # همان تیم — مسیر تازه‌شده
        return changed

# -------------------------------------------------------------
# ۴٫۵ ردیاب هویت تیم‌ها — عین TeamIdentityTracker در Momentum (نسخهٔ ۱۰٫۵)
#      بایت منو (base+0x36F9AE0): فقط ۹ ⇒ اجرای تشخیص → خواندن زندهٔ
#      هر دو طرف؛ بقیهٔ وضعیت‌ها → قفل روی آخرین انتخاب معتبر.
#      زنجیره‌ها و عرض اسلات (112) عین Momentum؛ خروجی (league, image).
# -------------------------------------------------------------
class FL2026TeamTracker:
    SIDE_CHAINS = {
        "home": {
            "league": (0x037F89D8, (0x40, 0xA0, 0x118)),
            "slots":  (0x036F9C10, (0x8, 0x0, 0x100, 0x64)),
        },
        "away": {
            "league": (0x036F9C10, (0xC8, 0x118)),
            "slots":  (0x036F9C10, (0xC8, 0x100, 0x64)),
        },
    }

    def __init__(self):
        self.ident = {"home": None, "away": None}
        # [PT v2.3.0] آخرین جفت ID معتبر خوانده‌شده با زنجیرهٔ جدید
        self._pt_ids_last = None

    def _resolve_chain(self, start_addr, offsets):
        """دقیقاً مثل resolve_pointer_chain ابزار اصلی (عین Momentum):
           اول deref آدرس شروع، بعد برای هر آفست به‌جز آخری deref؛
           آخری فقط جمع می‌شود."""
        try:
            curr = _mem_read_u64(start_addr)
            if not curr:
                return None
            for i, off in enumerate(offsets):
                target = (curr + off) & 0xFFFFFFFFFFFFFFFF
                if i == len(offsets) - 1:
                    return target
                curr = _mem_read_u64(target)
                if not curr:
                    return None
            return None
        except Exception:
            return None

    def _read_side_ident(self, side):
        """(league_id, image_id) یا None — عین Momentum: league باید معتبر
           باشد و اسلات هدف (league+1) در بازهٔ 1..37 بیفتد."""
        try:
            lg_base_off, lg_chain = self.SIDE_CHAINS[side]["league"]
            lg_addr = self._resolve_chain(base_addr + lg_base_off, lg_chain)
            league = _mem_read_i32(lg_addr) if lg_addr is not None else None
            if league is None:
                return None
            sl_base_off, sl_chain = self.SIDE_CHAINS[side]["slots"]
            first = self._resolve_chain(base_addr + sl_base_off, sl_chain)
            img = None
            if first is not None:
                target_slot = league + 1
                if 1 <= target_slot <= TEAM_SLOT_COUNT:
                    img = _mem_read_i32(first + (target_slot - 1) * TEAM_SLOT_STRIDE)
            if img is None:
                return None
            return (int(league), int(img))
        except Exception:
            return None

    def tick(self):
        """یک گام ردیابی — از حلقهٔ ۳۰ هرتزی worker صدا زده می‌شود.
           [PT v2.3.1] بایت منو یک‌بار در هر تیک خوانده می‌شود (همان
           _mem_read_u8 که بقیهٔ مقادیر پوینتری را می‌خواند) و «هر دو» مسیر
           فقط با منو = ۹ تشخیص را اجرا می‌کنند؛ بقیهٔ وضعیت‌ها ⇒ قفل روی
           آخرین انتخاب معتبر (عین Momentum).
           [PT v2.3.0] حالت PT: زنجیرهٔ پوینتری جدید کاربر (03705E20/98/228)
           در هر تیکِ منو-۹ خوانده می‌شود؛ اعتبارسنجی = هر دو Team ID در
           دیتابیس PT؛ تغییر ⇒ apply.
           PT نبود ⇒ مسیر قدیمی (_legacy_tick — منو ۹ + league/slots)."""
        if not h_process or not base_addr:
            return
        menu = _mem_read_u8(base_addr + TEAM_MENU_STATE_OFFSET)
        if menu is None:
            return   # خواندن ناموفق ⇒ هیچ؛ آخرین انتخاب معتبر می‌ماند
        PTx = pt_active()
        if PTx is not None:
            if menu == TEAM_MENU_DETECT_VALUE:
                ids = fl_read_team_ids()
                if ids is not None and ids != self._pt_ids_last:
                    self._pt_ids_last = ids
                    try:
                        print(f"[TEAM] PT ids: home={ids[0]} away={ids[1]} "
                              f"({PTx.team_name(ids[0])} vs {PTx.team_name(ids[1])})",
                              flush=True)
                    except Exception:
                        pass
                    apply_team_detection("home", PTData.PT_TEAM_LEAGUE_TAG, ids[0])
                    apply_team_detection("away", PTData.PT_TEAM_LEAGUE_TAG, ids[1])
            # منو != ۹ ⇒ قفل: آخرین Team ID معتبر می‌ماند (عین مسیر قدیمی)
            return
        self._legacy_tick(menu)

    def _legacy_tick(self, menu):
        """مسیر قدیمی (بدون PT) — خواندن فقط در منو ۹؛ بایت منو حالا یک‌بار
           در tick بالاتر و با همان Reader بقیهٔ پوینترها خوانده می‌شود؛
           بیرون از منو ۹ آخرین انتخاب معتبر قفل می‌ماند (عین Momentum)."""
        if not h_process or not base_addr:
            return
        if menu == TEAM_MENU_DETECT_VALUE:
            for side in ("home", "away"):
                ident = self._read_side_ident(side)
                if ident is not None and ident != self.ident[side]:
                    self.ident[side] = ident
                    print(f"[TEAM] ident {side} = league {ident[0]} / img {ident[1]}", flush=True)
                    apply_team_detection(side, ident[0], ident[1])
        # منو != ۹ یا خواندن ناموفق → قفل: آخرین انتخاب معتبر می‌ماند

# -------------------------------------------------------------
# ۵. ساخت موجودیت‌های مسابقه + ریست + ترد پس‌زمینهٔ ۳۰ هرتز — نسخهٔ 2026
# -------------------------------------------------------------
def build_match_entities():
    """ساخت ۲۲ موجودیت از آرایهٔ پوینتری بازی (بدون هیچ هوکی):
       صندلی‌های 0..10 = میزبان و 11..21 = مهمان (عین Momentum)؛
       درون هر تیم، دروازه‌بان با کمینه/بیشینهٔ x مشخص می‌شود و ترتیب
       نهایی مثل 2017 می‌شود:  [GK میزبان][۱۰ بازیکن میزبان مرتب‌شده با x]
       [GK مهمان][۱۰ بازیکن مهمان مرتب‌شده با -x]  تا ایندکس‌های فیلتر
       (OUTFIELD_INDICES = 1..10 و 12..21) و بقیهٔ برنامه بدون تغییر بمانند."""
    global entities, initial_discovered_codes, entities_ready, match_reset_event
    global entity_heatmaps, total_samples_taken, current_code

    raw_players = fl_read_all_players()
    if raw_players is None:
        return False

    home = raw_players[0:11]
    away = raw_players[11:22]

    # تفکیک گلرها (عین 2017: گلر میزبان کمینهٔ x / گلر مهمان بیشینهٔ x)
    home_gk = min(home, key=lambda p: p[1])
    away_gk = max(away, key=lambda p: p[1])
    home_fld = sorted([p for p in home if p is not home_gk], key=lambda p: p[1])
    away_fld = sorted([p for p in away if p is not away_gk], key=lambda p: -p[1])

    ordered = [home_gk] + home_fld + [away_gk] + away_fld   # ۲۲ موجودیت

    # ۱. پاکسازی کامل دیتای بازی قبل (هیت‌مپ + سمپل‌ها)
    with heatmap_lock:
        entity_heatmaps.fill(0.0)
    total_samples_taken = 0
    current_code = None

    # ۲. صفر کردن slot کد بازیکن تا مقدار بازی قبل منتقل نشود
    if pcode_data_addr and h_process:
        try:
            safe_write(h_process, pcode_data_addr, b"\x00" * 8)
        except Exception:
            pass

    temp_entities = []
    for idx, (seat, x, z) in enumerate(ordered):
        team = 1 if idx < 11 else 2
        role = "GK" if idx in (0, 11) else "Field"
        team_title = home_team_name if team == 1 else away_team_name
        if role == "GK":
            name = f"دروازه‌بان {team_title}"
        else:
            name = f"بازیکن {team_title}"
        temp_entities.append({
            "id": idx + 1,
            "seat": seat,               # صندلی آرایهٔ بازی (0..21) — پایدار در کل مسابقه
            "x": x,
            "z": z,
            "role": role,
            "team": team,
            "confirmed_name": None,
            "name": name,
            "code": None,
            "status": "در انتظار لمس",
            "is_locked": False,
            "touch_start_time": None
        })

    # ۳. ریست لیست موجودیت‌ها، کدهای کشف‌شده و ارسال سیگنال به GUI
    with entities_lock:
        entities = temp_entities
        initial_discovered_codes.clear()
        entities_ready = True
        match_reset_event = True
    return True

def perform_match_reset(start_t, now_wall, source=""):
    """ریست کامل مسابقه (هیت‌مپ/کدها/فاز) — معادل _perform_reset در Momentum:
       تایمر صفر شده و بالا رفته (TRB) یا Watchdog بازی جدید یا NEW_MATCH.
       موجودیت‌ها در اولین تیک PLAYING بعدی دوباره ساخته می‌شوند."""
    global half_number, ht_pending, ht_prev_end_t, seen_max_t, last_auto_reset_wall
    global match_entities_built, entity_heatmaps, total_samples_taken
    global current_code, initial_discovered_codes, status_msg

    half_number = 1
    ht_pending = False
    ht_prev_end_t = 0.0
    with heatmap_lock:
        entity_heatmaps.fill(0.0)
    total_samples_taken = 0
    current_code = None
    initial_discovered_codes.clear()
    seen_max_t = float(start_t if start_t is not None else 0.0)
    last_auto_reset_wall = now_wall
    match_entities_built = False
    try:
        AUTO_CTRL.reset()   # مسابقه جدید — از WAITING (بند ۳۶)
    except Exception:
        pass
    try:
        SUMMARY_CTRL.reset()   # [SUITE v1.0.0] new match — re-arm the 91' popup
    except Exception:
        pass
    print(f"[MatchLifecycle] NEW_MATCH ({source}) — تایمر "
          f"{(start_t if start_t is not None else 0.0):.1f}s — ریست کامل مسابقه", flush=True)

def hm_wait_for_game():
    """[SUITE v2.1.5] GAME DETECTION IS THE BRIDGE'S JOB: the bridge polls
    FL_2026.exe every 2 s and owns the truth, so a backend opened BEFORE
    the game simply waits for the bridge to report it running (the old
    local toolhelp scan ran in THIS process and could not be trusted for
    that timing). Returns (pid, base) once the game is attachable;
    (None, None) when is_running goes False. The local snapshot scan is
    ONLY used while no bridge answers at all (standalone run)."""
    global status_msg
    while is_running:
        cli = hm_bridge()
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
                status_msg = ("در انتظار اجرای FL_2026.exe... "
                              "(پل در حال پایش بازی است)")
                time.sleep(1.0)
                continue
            # bridge unreachable right now — fall through to the local
            # scan below until it answers again (standalone / restarting)
        pid = get_fl_pid()
        if pid:
            base = get_fl_base(pid)
            if base:
                return pid, base
        time.sleep(1.0)
    return None, None


_hm_last_hook_retry = 0.0


def hm_hooks_retry_tick(now):
    """[SUITE v2.1.5] the bridge owns every byte: any of the three feeds
    that came back REFUSED at attach (or whose data address is still
    missing) is re-requested through the bridge every 5 s until it is
    granted. No local fallback exists anywhere in this pipeline."""
    global _hm_last_hook_retry
    global ball_hook_addr, ball_cave_addr, ball_data_addr
    global time_hook_addr, time_cave_addr, time_data_addr
    global pcode_hook_addr, pcode_cave_addr, pcode_data_addr
    if now - _hm_last_hook_retry < 5.0:
        return
    _hm_last_hook_retry = now
    cli = hm_bridge()
    if cli is None or not base_addr or not h_process:
        return
    try:
        if not ball_data_addr:
            buf = cli.hook_request(BALL_HOOK_OFFSET, BALL_ORIG_BYTES, 2)
            if buf:
                ball_hook_addr = base_addr + BALL_HOOK_OFFSET
                ball_cave_addr = 0
                ball_data_addr = buf
                print(f"[HOOK] ball feed granted on retry (buffer 0x{buf:X})",
                      flush=True)
        if not time_data_addr:
            buf = cli.hook_request(TIME_HOOK_OFFSET, TIME_ORIG_BYTES, 1,
                                   kind="rsi")
            if buf:
                time_hook_addr = base_addr + TIME_HOOK_OFFSET
                time_cave_addr = 0
                time_data_addr = buf
                print(f"[HOOK] time feed granted on retry (RSI slot 0x{buf:X})",
                      flush=True)
        if not pcode_data_addr:
            buf = cli.hook_request(PLAYER_CODE_HOOK_OFFSET,
                                   PLAYER_CODE_ORIG_BYTES, 2, kind="r12d")
            if buf:
                pcode_hook_addr = base_addr + PLAYER_CODE_HOOK_OFFSET
                pcode_cave_addr = 0
                pcode_data_addr = buf
                print(f"[HOOK] player-code feed granted on retry "
                      f"(slot 0x{buf:X})", flush=True)
    except Exception:
        pass


def tracker_worker():
    global h_process, base_addr, is_hooked, status_msg
    global ball_hook_addr, ball_cave_addr, ball_data_addr
    global time_hook_addr, time_cave_addr, time_data_addr
    global pcode_hook_addr, pcode_cave_addr, pcode_data_addr
    global display_minute, display_second, period_title
    global is_clock_active, is_inverted_active, diff_val
    global total_samples_taken, actual_sampling_rate
    global entities, entities_ready, match_reset_event
    global ball_pos, initial_discovered_codes, current_code
    global entity_heatmaps
    global half_number, ht_pending, ht_prev_end_t, seen_max_t, prev_total_t
    global trb_armed, trb_last_fire_wall, last_auto_reset_wall, match_entities_built

    try:
        status_msg = "در انتظار اجرای FL_2026.exe..."
        # [SUITE v2.1.5] bridge-first game detection (the bridge owns the
        # truth — this backend may have been opened BEFORE the game)
        pid, _gbase = hm_wait_for_game()
        if not is_running or not pid:
            return

        status_msg = "بازی پیدا شد. در حال فعال‌سازی هوک‌های پایدار..."
        h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not h_process:
            status_msg = "خطا در دسترسی OpenProcess"
            return

        base_addr = _gbase or get_fl_base(pid)
        if not base_addr:
            status_msg = "ماژول FL_2026.exe یافت نشد."
            return

        # نصب سه هوک (توپ / زمان / کد بازیکن) — عین جریان Momentum
        warnings = fl_install_all_hooks()

        is_hooked = True
        status_msg = "سیستم آماده است. در انتظار شروع مسابقه (PLAYING)..."
        if warnings:
            status_msg += " | هشدار: " + " | ".join(warnings)

        team_tracker = FL2026TeamTracker()

        # --- وضعیت چرخهٔ عمر (عین Momentum) ---
        half_number = 1
        ht_pending = False
        ht_prev_end_t = 0.0
        seen_max_t = 0.0
        prev_total_t = None
        trb_armed = False
        trb_last_fire_wall = 0.0
        last_auto_reset_wall = 0.0
        match_entities_built = False
        build_fail_count = 0

        last_raw_time = -1
        last_change_wall_time = time.time()

        TARGET_HZ = 30.0
        TICK_DURATION = 1.0 / TARGET_HZ
        next_tick = time.monotonic()
        last_sample_time = time.monotonic()
        hz_sample_count = 0
        hz_timer = time.monotonic()

        while is_running:
            loop_start = time.monotonic()
            now = time.time()

            dt = loop_start - last_sample_time
            last_sample_time = loop_start
            if dt > 0.08: dt = TICK_DURATION
            elif dt < 0.005: dt = 0.005

            # ---------------------------------------------------------
            # ۱) وضعیت مسابقه (بایت — 128/129 = PLAYING؛ عین Momentum)
            # ---------------------------------------------------------
            # [SUITE v1.0.0] live settings refresh (MyMods may rewrite
            # ModsConfig.json; the bridge also hands settings at spawn)
            hm_settings_tick(now)

            # [SUITE v2.1.5] re-request any feed the bridge has not granted
            # yet (refusals never fall back to local bytes)
            hm_hooks_retry_tick(now)

            m_state = fl_read_match_state()
            is_playing = (m_state == "PLAYING")

            # ---------------------------------------------------------
            # ۲) ساعت بازی — منبع واحد عین Momentum (TimeHooker → Fallback)
            # ---------------------------------------------------------
            total_t, g_min, g_sec = fl_read_game_clock()
            if total_t is not None:
                display_minute = int(g_min if g_min is not None else total_t // 60)
                display_second = int(g_sec if g_sec is not None else total_t % 60)
                diff_val = 0

                curr_raw_time = (display_minute << 16) | (display_second & 0xFFFF)
                if curr_raw_time != last_raw_time and display_minute < 300:
                    last_raw_time = curr_raw_time
                    last_change_wall_time = now
                    is_clock_active = is_playing
                else:
                    if (now - last_change_wall_time > 1.0) or not is_playing:
                        is_clock_active = False
            else:
                is_clock_active = False

            # ---------------------------------------------------------
            # ۳) عنوان نیمه از ماشین فاز (عین Momentum: 1/2/3/4)
            # ---------------------------------------------------------
            period_title, is_inverted_active = PERIOD_TITLES.get(
                half_number, ("نامشخص", False))

            # ---------------------------------------------------------
            # ۴) چرخهٔ عمر مسابقه — عین Momentum (نسخهٔ ۱۰٫۳ / ۱۰٫۷)
            #    ردیاب‌های ساعت + علامت افت زمان (قبل از هر گیت داده‌ای)
            # ---------------------------------------------------------
            if total_t is not None:
                if total_t > seen_max_t:
                    seen_max_t = total_t
                if should_flag_time_drop(prev_total_t, total_t, MATCH_RESTART_DELTA):
                    if not ht_pending:
                        ht_pending = True
                        ht_prev_end_t = prev_total_t
                        print(f"[MatchLifecycle] افت زمان: {prev_total_t:.1f} → "
                              f"{total_t:.1f} — در انتظار از سرگیری PLAYING", flush=True)
                prev_total_t = total_t

            # --- TRB: تایمر صفر شد و شروع به بالا رفتن کرد = دست جدید ---
            if total_t is not None:
                t_val = float(total_t)
                if t_val <= TRB_ZERO_T:
                    if not trb_armed:
                        trb_armed = True
                elif trb_armed and t_val > TRB_RISE_T:
                    trb_armed = False
                    if ((now - trb_last_fire_wall) >= TRB_COOLDOWN_SEC
                            and (now - last_auto_reset_wall) >= TRB_COOLDOWN_SEC):
                        trb_last_fire_wall = now
                        rep = fl_verify_and_repair_hooks()
                        print(f"[NewHand] شروع دست جدید (TRB) — hooks: {rep}", flush=True)
                        perform_match_reset(t_val, now, source="trb")

            if is_playing and total_t is not None:
                # --- Watchdog بازی جدید (عین Momentum نسخهٔ ۱۰٫۳) ---
                if is_new_match_watchdog(seen_max_t, total_t,
                                         NEW_GAME_MAX_START, MATCH_RESTART_DELTA):
                    rep = fl_verify_and_repair_hooks()
                    print(f"[MatchLifecycle] NEW_MATCH (watchdog) — hooks: {rep}", flush=True)
                    perform_match_reset(total_t, now, source="watchdog")
                elif ht_pending:
                    # --- تصمیم پس از افت زمان (عین Momentum نسخهٔ ۱۰٫۳) ---
                    verdict = classify_resume_after_drop(
                        ht_prev_end_t, total_t, half_number,
                        ht_hard_min=HT_HARD_MIN_FIRST_HALF,
                        ht_resume_lower_slack=HT_RESUME_LOWER_SLACK,
                        ht_resume_tolerance=HT_RESUME_TOLERANCE,
                        new_game_max_start=NEW_GAME_MAX_START,
                        et_reset_tolerance=ET_RESET_TOLERANCE)
                    ht_pending = False
                    if verdict == "HT":
                        half_number = 2
                        print("[MatchLifecycle] HT تأیید شد — شروع نیمه دوم (قرینه)", flush=True)
                    elif verdict == "ET1":
                        half_number = 3
                        print("[MatchLifecycle] ET1 — شروع وقت اضافه اول", flush=True)
                    elif verdict == "ET2":
                        half_number = 4
                        print("[MatchLifecycle] ET2 — شروع وقت اضافه دوم (قرینه)", flush=True)
                    elif verdict == "NEW_MATCH":
                        perform_match_reset(total_t, now, source="time-drop")
                    # KEPT → حفظ نمودار (پایان مسابقه/صفحه آمار)

            # ---------------------------------------------------------
            # ۵) تشخیص تیم‌ها — عین Momentum (منوی ۱۰۰ + زنجیره‌ها)
            # ---------------------------------------------------------
            try:
                team_tracker.tick()
            except Exception:
                pass

            # ─── Second Broadcast Layer — تیک کنترلر اورلی خودکار (زمان بازی؛ بند ۳)
            #     فقط ماشین حالت سبک — Preload/رندر هرگز روی ترد ۳۰Hz انجام نمی‌شود
            #     v14.0: اگر «زمان تقلبی» فعال باشد feed ساعت تقلبی جایگزین ساعت
            #     واقعی بازی می‌شود (فقط برای همین کنترلر؛ GUI/شناسایی دست‌نخورده)
            try:
                feed_sec = FAKE_CLOCK.game_sec()
                if feed_sec is None:
                    feed_sec = int(display_minute) * 60 + int(display_second)
                AUTO_CTRL.tick(feed_sec)
            except Exception:
                pass

            # [SUITE v1.0.0] 91' match summary trigger (state machine only;
            # the GUI thread consumes the request and pops the badge)
            try:
                SUMMARY_CTRL.tick(feed_sec)
            except Exception:
                pass

            # ---------------------------------------------------------
            # ۶) شروع مسابقه: ساخت ۲۲ موجودیت در اولین تیک PLAYING هر مسابقه
            #    (اتصال وسط بازی هم همین‌جا پوشش داده می‌شود — عین Momentum)
            # ---------------------------------------------------------
            if is_playing and not match_entities_built:
                if build_match_entities():
                    match_entities_built = True
                    build_fail_count = 0
                    status_msg = ("بازی جدید شناسایی شد. هیت‌مپ و اسامی ریست شدند؛ "
                                  "ردیابی ۲۲ نفر (بدون هوک مختصات) فعال است.")
                else:
                    build_fail_count += 1
                    if build_fail_count == 30:
                        print("[ENTITIES] هنوز همهٔ ۲۲ صندلی بازیکن معتبر نیست — "
                              "در حال تلاش مجدد در هر تیک...", flush=True)

            # ---------------------------------------------------------
            # ۷) رصد توپ (هوک Momentum — slot xmm0)
            # ---------------------------------------------------------
            b_valid = False
            ball_xz = fl_read_ball_xz()
            if ball_xz is not None:
                b_valid = True

            # ---------------------------------------------------------
            # ۸) کد بازیکن (هوک A83964 — مقدار خام 1..22)
            # ---------------------------------------------------------
            raw_code = fl_read_player_code()
            if raw_code is not None and 1 <= raw_code <= 22:
                current_code = raw_code

            # ---------------------------------------------------------
            # ۹) بروزرسانی مختصات ۲۲ بازیکن (زنجیرهٔ پوینتری — بدون هوک)
            # ---------------------------------------------------------
            with entities_lock:
                if ball_xz is not None:
                    ball_pos["x"] = ball_xz[0]
                    ball_pos["z"] = ball_xz[1]
                ball_pos["valid"] = b_valid

                for e in entities:
                    c = fl_read_player_coords(e.get("seat"))
                    if c is not None:
                        e["x"], e["z"] = c

                cur_list = list(entities)

            # ---------------------------------------------------------
            # ۱۰) انباشت هیت‌مپ (عین 2017 — فقط ۲۲ موجودیت بدون داور)
            # ---------------------------------------------------------
            if is_clock_active and len(cur_list) == 22:
                with heatmap_lock:
                    for idx, ent in enumerate(cur_list):
                        if ent.get("role") == "GK" or ent.get("team") == 0:
                            continue

                        raw_x = ent["x"]
                        raw_z = ent["z"]
                        final_x = -raw_x if is_inverted_active else raw_x
                        final_z = -raw_z if is_inverted_active else raw_z

                        gx = int(((final_x - TOTAL_ENGINE_X_MIN) / (TOTAL_ENGINE_X_MAX - TOTAL_ENGINE_X_MIN)) * (GRID_W - 1))
                        gy = int(((final_z - TOTAL_ENGINE_Z_MIN) / (TOTAL_ENGINE_Z_MAX - TOTAL_ENGINE_Z_MIN)) * (GRID_H - 1))

                        if 0 <= gx < GRID_W and 0 <= gy < GRID_H:
                            entity_heatmaps[idx, gy, gx] += dt

                total_samples_taken += 1
                hz_sample_count += 1

            # ---------------------------------------------------------
            # ۱۱) کشف تدریجی اسامی بازیکنان هنگام لمس توپ
            #     [PT v2.3.0] هویت بازیکن = Slot پوینتر جدید (۱ بایت در
            #     [[base+0x036F4270]+0x74]) + دیتابیس PT: نام/سن/شماره
            #     پیراهن/PES ID (چهرهٔ 192x192 از Asset.zip). تیم از سمتِ
            #     نزدیک‌ترین بازیکن به توپ (صندلی‌ها ثابت‌اند). PT نبود ⇒
            #     روش قبلی: کد خام 1..22 از هوک A83964 (میزبان = 1..11).
            # ---------------------------------------------------------
            PTx = pt_active()
            if PTx is not None:
                _gate_ok = len(cur_list) == 22
                _verified_team = None
                _code = None
            else:
                _gate_ok = (current_code is not None and len(cur_list) == 22)
                _verified_team = (1 if current_code <= 11 else 2) \
                    if current_code is not None else None
                _code = (current_code if current_code <= 11
                         else current_code - 11) if current_code is not None \
                    else None
            if is_clock_active and b_valid and _gate_ok:
                verified_team = _verified_team
                code = _code

                candidates = [ent for ent in cur_list if ent.get("team") in (1, 2)]
                if candidates:
                    closest_p = min(candidates, key=lambda p: math.hypot(p["x"] - ball_pos["x"], p["z"] - ball_pos["z"]))
                    dist_to_ball = math.hypot(closest_p["x"] - ball_pos["x"], closest_p["z"] - ball_pos["z"])

                    for ent in candidates:
                        if ent is not closest_p or dist_to_ball > 1.6:
                            ent["touch_start_time"] = None

                    if dist_to_ball <= 1.6:
                        other_players = [p for p in cur_list if p is not closest_p and p["role"] not in ["REF", "AR"]]
                        is_crowded = any(math.hypot(p["x"] - closest_p["x"], p["z"] - closest_p["z"]) < 2.2 for p in other_players)

                        if not is_crowded:
                            if closest_p["touch_start_time"] is None:
                                closest_p["touch_start_time"] = now
                            else:
                                elapsed = now - closest_p["touch_start_time"]
                                if elapsed >= 1.0:
                                    # [PT v2.3.0] هویت از Slot پوینتر + دیتابیس PT؛
                                    # fallback = کد هوک (روش قبلی) وقتی PT نباشد.
                                    # در حالت PT اگر Slot این تیک نخواند ⇒ تأیید
                                    # به تعویق می‌افتد (هویت قفل‌شده خراب نمی‌شود).
                                    slot_val = fl_read_player_slot()
                                    if PTx is not None and slot_val is None:
                                        closest_p["touch_start_time"] = None
                                    else:
                                        _pt_info = None
                                        if PTx is not None and slot_val is not None:
                                            target_team = closest_p.get("team") or 1
                                            team_key_now = home_team_key \
                                                if target_team == 1 else away_team_key
                                            _info = None
                                            if PTData is not None and \
                                                    PTData.PTDataSource.is_pt_key(team_key_now):
                                                _info = PTx.player_by_slot(
                                                    int(team_key_now[1]), int(slot_val))
                                            code = int(slot_val)
                                            player_name = (_info.get("name")
                                                           if _info else None) \
                                                or f"بازیکن ({slot_val})"
                                            _pt_info = _info
                                        else:
                                            if verified_team is None:
                                                verified_team = closest_p.get("team") or 1
                                            target_team = verified_team

                                            roster = home_players_dict if target_team == 1 else away_players_dict
                                            _nm = roster.get(code)
                                            player_name = _nm if isinstance(_nm, str) \
                                                else f"بازیکن ({code})"

                                        team_title = home_team_name if target_team == 1 else away_team_name

                                        need_menu_update = False
                                        with entities_lock:
                                            if not closest_p["is_locked"]:
                                                closest_p["is_locked"] = True
                                                closest_p["code"] = code
                                                closest_p["confirmed_name"] = player_name
                                                closest_p["name"] = f"[{team_title}] {player_name}"
                                                closest_p["status"] = "ثبت اولیه"
                                                if len(initial_discovered_codes) < 22:
                                                    initial_discovered_codes.add((target_team, code))
                                                need_menu_update = True
                                            else:
                                                if closest_p["code"] != code:
                                                    if (target_team, code) in initial_discovered_codes:
                                                        closest_p["status"] = "جابجایی"
                                                    else:
                                                        closest_p["status"] = "تعویض"
                                                    closest_p["code"] = code
                                                    closest_p["confirmed_name"] = player_name
                                                    closest_p["name"] = f"[{team_title}] {player_name}"
                                                    need_menu_update = True
                                            # [PT v2.3.0] اطلاعات کامل بازیکن روی موجودیت
                                            if _pt_info is not None:
                                                closest_p["slot"] = int(slot_val) if slot_val is not None else closest_p.get("slot")
                                                closest_p["pes_id"] = _pt_info.get("pes_id")
                                                closest_p["shirt"] = _pt_info.get("shirt")
                                                closest_p["age"] = _pt_info.get("age")

                                        if need_menu_update:
                                            entities_ready = True

                                        closest_p["touch_start_time"] = None
                        else:
                            closest_p["touch_start_time"] = None
            else:
                for ent in cur_list:
                    ent["touch_start_time"] = None

            if loop_start - hz_timer >= 1.0:
                actual_sampling_rate = hz_sample_count / (loop_start - hz_timer)
                hz_sample_count = 0
                hz_timer = loop_start

            next_tick += TICK_DURATION
            sleep_time = next_tick - time.monotonic()
            if sleep_time > 0: time.sleep(sleep_time)
            else: next_tick = time.monotonic()

    except Exception as ex:
        status_msg = f"خطا: {ex}"
        traceback.print_exc()
# -------------------------------------------------------------
# ۶. پالت لالیگا و رندر زمین
# -------------------------------------------------------------
def build_laliga_smooth_lut():
    lut = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        if t < 0.005: lut[i] = [0, 0, 0, 0]
        elif t < 0.28:
            f = (t - 0.005) / 0.275
            lut[i] = [int(95 * (1 - f) + 165 * f), int(195 * (1 - f) + 225 * f), int(40 * (1 - f) + 30 * f), int(145 * (f ** 1.25))]
        elif t < 0.58:
            f = (t - 0.28) / 0.30
            lut[i] = [int(165 * (1 - f) + 235 * f), int(225 * (1 - f) + 185 * f), int(30 * (1 - f) + 20 * f), int(145 * (1 - f) + 190 * f)]
        elif t < 0.82:
            f = (t - 0.58) / 0.24
            lut[i] = [int(235 * (1 - f) + 215 * f), int(185 * (1 - f) + 90 * f), int(20 * (1 - f) + 18 * f), int(190 * (1 - f) + 225 * f)]
        else:
            f = (t - 0.82) / 0.18
            lut[i] = [int(215 * (1 - f) + 160 * f), int(90 * (1 - f) + 25 * f), int(18 * (1 - f) + 15 * f), int(225 * (1 - f) + 245 * f)]
    return lut

LALIGA_LUT = build_laliga_smooth_lut()

def render_calibrated_pitch(w, h):
    # چمن کمی روشن‌تر از قبل (به درخواست کاربر) — همچنان تم تیره، نه به روشنایی عکس مرجع
    img = Image.new("RGBA", (w, h), (24, 46, 28, 255))
    draw = ImageDraw.Draw(img)
    px, py = 20, 20
    fw = w - (px * 2); fh = h - (py * 2)

    def w2c(x, z):
        cx = px + ((x - TOTAL_ENGINE_X_MIN) / (TOTAL_ENGINE_X_MAX - TOTAL_ENGINE_X_MIN)) * fw
        cy = py + ((z - TOTAL_ENGINE_Z_MIN) / (TOTAL_ENGINE_Z_MAX - TOTAL_ENGINE_Z_MIN)) * fh
        return cx, cy

    stripes = 14
    sw = w / float(stripes)
    for i in range(stripes):
        if i % 2 == 0:
            draw.rectangle([i * sw, 0, (i + 1) * sw, h], fill=(29, 54, 33, 255))

    line_col = (200, 220, 210, 222)
    lw = 2
    c1 = w2c(PITCH_LINE_X_MIN, PITCH_LINE_Z_MIN)
    c2 = w2c(PITCH_LINE_X_MAX, PITCH_LINE_Z_MAX)
    mid = w2c(0.0, 0.0)

    draw.rectangle([c1[0], c1[1], c2[0], c2[1]], outline=line_col, width=lw)
    draw.line([mid[0], c1[1], mid[0], c2[1]], fill=line_col, width=lw)

    r_cx = (9.15 / (TOTAL_ENGINE_X_MAX - TOTAL_ENGINE_X_MIN)) * fw
    r_cy = (9.15 / (TOTAL_ENGINE_Z_MAX - TOTAL_ENGINE_Z_MIN)) * fh
    draw.ellipse([mid[0] - r_cx, mid[1] - r_cy, mid[0] + r_cx, mid[1] + r_cy], outline=line_col, width=lw)
    draw.ellipse([mid[0] - 2.5, mid[1] - 2.5, mid[0] + 2.5, mid[1] + 2.5], fill=line_col)

    p_l1 = w2c(-52.5, -20.16); p_l2 = w2c(-36.0, 20.16)
    draw.rectangle([p_l1[0], p_l1[1], p_l2[0], p_l2[1]], outline=line_col, width=lw)
    g_l1 = w2c(-52.5, -9.16); g_l2 = w2c(-47.0, 9.16)
    draw.rectangle([g_l1[0], g_l1[1], g_l2[0], g_l2[1]], outline=line_col, width=lw)
    spot_l = w2c(-41.5, 0.0)
    draw.ellipse([spot_l[0] - 2.5, spot_l[1] - 2.5, spot_l[0] + 2.5, spot_l[1] + 2.5], fill=line_col)
    draw.arc([spot_l[0] - r_cx, spot_l[1] - r_cy, spot_l[0] + r_cx, spot_l[1] + r_cy], start=307, end=53, fill=line_col, width=lw)

    p_r1 = w2c(36.0, -20.16); p_r2 = w2c(52.5, 20.16)
    draw.rectangle([p_r1[0], p_r1[1], p_r2[0], p_r2[1]], outline=line_col, width=lw)
    g_r1 = w2c(47.0, -9.16); g_r2 = w2c(52.5, 9.16)
    draw.rectangle([g_r1[0], g_r1[1], g_r2[0], g_r2[1]], outline=line_col, width=lw)
    spot_r = w2c(41.5, 0.0)
    draw.ellipse([spot_r[0] - 2.5, spot_r[0] - 2.5, spot_r[0] + 2.5, spot_r[0] + 2.5], fill=line_col)
    draw.arc([spot_r[0] - r_cx, spot_r[1] - r_cy, spot_r[0] + r_cx, spot_r[1] + r_cy], start=127, end=233, fill=line_col, width=lw)

    r_crn_x = (1.0 / (TOTAL_ENGINE_X_MAX - TOTAL_ENGINE_X_MIN)) * fw
    r_crn_y = (1.0 / (TOTAL_ENGINE_Z_MAX - TOTAL_ENGINE_Z_MIN)) * fh
    draw.arc([c1[0] - r_crn_x, c1[1] - r_crn_y, c1[0] + r_crn_x, c1[1] + r_crn_y], start=0, end=90, fill=line_col, width=lw)
    draw.arc([c1[0] - r_crn_x, c2[1] - r_crn_y, c1[0] + r_crn_x, c2[1] + r_crn_y], start=270, end=360, fill=line_col, width=lw)
    draw.arc([c2[0] - r_crn_x, c1[1] - r_crn_y, c2[0] + r_crn_x, c1[1] + r_crn_y], start=90, end=180, fill=line_col, width=lw)
    draw.arc([c2[0] - r_crn_x, c2[1] - r_crn_y, c2[0] + r_crn_x, c2[1] + r_crn_y], start=180, end=270, fill=line_col, width=lw)

    draw.rectangle([w2c(-54.5, -3.66)[0], w2c(-54.5, -3.66)[1], w2c(-52.5, 3.66)[0], w2c(-52.5, 3.66)[1]], outline=(125, 148, 135, 175), width=1)
    draw.rectangle([w2c(52.5, -3.66)[0], w2c(52.5, -3.66)[1], w2c(54.5, 3.66)[0], w2c(54.5, 3.66)[1]], outline=(125, 148, 135, 175), width=1)
    return img

# =============================================================
# ۶.۵ رندر سه‌بعدی برودکاستی — کلید R یا دکمه «رندر سه‌بعدی»
#     خروجی: تصویر گرافیکی شبیه پخش تلویزیونی؛ هیت‌مپ به‌عنوان
#     تکسچر روی زمین سه‌بعدی (پرسپکتیو) + دروازه‌های تخت سه‌خطی
# === [3D-RENDER-BEGIN] ===
# =============================================================

PLAYERS_DIR = os.path.join(SCRIPT_DIR, "players")          # players/{league}/{team}/{code}.png
RENDER_DIR  = os.path.join(SCRIPT_DIR, "renders")
RENDER_HOTKEY = "R"

PHOTO_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

# ---------- ابعاد خروجی (مطابق تصویر مرجع) ----------
RENDER_W, RENDER_H = 1774, 887
CANVAS_W_REF = 1012.0   # عرض بوم دوبعدی برای مقیاس‌گیری فیدر لبه‌ها

# ---------- هندسه سکوی چمن (پرسپکتیو، اندازه‌گیری‌شده از مرجع) ----------
PFL = (255.0, 288.0)    # گوشه دور-چپ سکوی چمن
PFR = (1531.0, 288.0)   # گوشه دور-راست
PNR = (1723.0, 783.0)   # گوشه نزدیک-راست
PNL = (53.0, 783.0)     # گوشه نزدیک-چپ

R_PLAT_X = 3.6           # حاشیه چمن بیرون خطوط زمین (متر - محور طولی)
R_PLAT_Z = 1.9           # حاشیه چمن بیرون خطوط زمین (متر - محور عرضی)
TEX_X_MIN = PITCH_LINE_X_MIN - R_PLAT_X
TEX_X_MAX = PITCH_LINE_X_MAX + R_PLAT_X
TEX_Z_MIN = PITCH_LINE_Z_MIN - R_PLAT_Z
TEX_Z_MAX = PITCH_LINE_Z_MAX + R_PLAT_Z
TEX_W = 2244             # رزولوشن تکسچر تخت (حدود ۲۰ پیکسل بر متر)
TEX_H = int(TEX_W * (TEX_Z_MAX - TEX_Z_MIN) / (TEX_X_MAX - TEX_X_MIN))

# ---------- پالت چمن واقعی بازی (سبز اشباع، مطابق مرجع) ----------
R_GRASS_DARK  = (34, 116, 16)          # راه‌راه تیره
R_GRASS_LIGHT = (46, 172, 25)          # راه‌راه روشن
R_LINE_COL    = (243, 250, 244, 240)   # خطوط سفید زمین

# ---------- رنگ‌های قاب، پس‌زمینه و پنل‌ها ----------
BG_BASE_TOP  = (2, 24, 62)
BG_BASE_BOT  = (0, 12, 34)
BG_GLOW_COL  = (16, 78, 158)
FRAME_COL    = (134, 174, 222, 255)
FRAME_INNER  = (60, 105, 170, 90)
PANEL_TOP    = (15, 52, 100)
PANEL_BOT    = (6, 34, 78)
PANEL_EDGE_T = (108, 152, 214)
PANEL_EDGE_B = (208, 224, 246)
BAR_COL_L    = (7, 66, 168)
BAR_COL_R    = (10, 84, 196)
RING_COL     = (150, 192, 235, 255)
TXT_WHITE    = (246, 250, 255, 255)

_FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
def _f(name): return os.path.join(_FONT_DIR, name)

# فونت‌های ویندوز که روی هر سیستم ویندوزی نصب هستند (Segoe UI / Arial)
F_TITLE_PATHS = [_f("seguibl.ttf"),  _f("segoeuib.ttf"), _f("arialbd.ttf")]
F_BOLD_PATHS  = [_f("segoeuib.ttf"), _f("seguisb.ttf"),  _f("arialbd.ttf")]
F_SEMI_PATHS  = [_f("seguisb.ttf"),  _f("segoeuib.ttf"), _f("arial.ttf")]
F_REG_PATHS   = [_f("segoeui.ttf"),  _f("arial.ttf")]

def load_font(candidates, size):
    for path in candidates:
        try:
            return ImageFont.truetype(path, int(size))
        except Exception:
            continue
    try:
        return ImageFont.truetype("arial.ttf", int(size))
    except Exception:
        return ImageFont.load_default()

def fit_font(draw, text, candidates, max_size, max_width):
    size = max_size
    while size > 12:
        f = load_font(candidates, size)
        try:
            if draw.textlength(text, font=f) <= max_width:
                return f
        except Exception:
            return f
        size -= 2
    return load_font(candidates, 12)

def _tracked_text_width(draw, text, font, tracking):
    """عرض متن با احتساب فاصله اضافه بین حروف (letter-spacing)"""
    if not text:
        return 0.0
    ws = [draw.textlength(ch, font=font) for ch in text]
    return sum(ws) + tracking * (len(text) - 1)

def fit_font_tracked(draw, text, candidates, max_size, max_width, track_ratio=0.16):
    """مثل fit_font ولی عرض با فاصله بین حروف محاسبه می‌شود؛ (فونت، فاصله) برمی‌گرداند"""
    size = max_size
    while size > 12:
        f = load_font(candidates, size)
        tracking = max(2, int(round(size * track_ratio)))
        try:
            if _tracked_text_width(draw, text, f, tracking) <= max_width:
                return f, tracking
        except Exception:
            return f, tracking
        size -= 2
    return load_font(candidates, 12), max(2, int(round(12 * track_ratio)))

def _draw_tracked_text(draw, cx, cy, text, font, fill, tracking):
    """متن با فاصله بین حروف، به‌صورت حرف‌به‌حرف؛ cx مرکز افقی متن است"""
    if not text:
        return
    ws = [draw.textlength(ch, font=font) for ch in text]
    total = sum(ws) + tracking * (len(text) - 1)
    x = cx - total / 2.0
    for ch, w in zip(text, ws):
        draw.text((x, cy), ch, font=font, fill=fill, anchor="lm")
        x += w + tracking

def find_player_photo(team_key, code):
    """مسیر عکس چهره بازیکن — اولویت ۰: [PT v2.3.0] Asset.zip →
    Players/{pes_id}.png (192x192) — کد در حالت PT = Slot بازیکن در لیست تیم؛
    اولویت ۱: مسیر دلخواه کاربر در pes2017_teams.json (نسخه ۱۵٫۰)؛
    اولویت ۲: قرارداد players/{league}/{team}/{code}.png (همهٔ پسوندهای PHOTO_EXTS)"""
    if code is None or team_key is None:
        return None
    PTx = pt_active()
    if PTx is not None and PTData is not None \
            and PTData.PTDataSource.is_pt_key(team_key):
        try:
            info = PTx.player_by_slot(int(team_key[1]), int(code))
            if info and info.get("pes_id"):
                p = PTx.player_face_path(info["pes_id"])
                if p and os.path.isfile(p):
                    return p
        except Exception:
            pass
        return None
    pe = team_json_player_entry(team_key, code)
    if pe and pe.get("photo"):
        p = _resolve_asset_path(pe["photo"])
        if p:
            try:
                if os.path.isfile(p):
                    return p
            except Exception:
                pass
    folder = team_photo_dir(team_key)
    if not folder:
        return None
    for ext in PHOTO_EXTS:
        p = os.path.join(folder, f"{code}{ext}")
        if os.path.isfile(p):
            return p
    return None

def find_team_logo(team_key):
    """مسیر لوگوی 512x512 — اولویت: مسیر دلخواه pes2017_teams.json، سپس
    قرارداد Football_Database/{league}/{team}.png (هر دو برای همان تیم)"""
    return team_logo_path(team_key)

def compute_density_snapshot(filter_indices):
    with heatmap_lock:
        if len(filter_indices) == 1:
            return np.copy(entity_heatmaps[filter_indices[0]])
        return np.sum(entity_heatmaps[filter_indices], axis=0)

def density_to_heat_rgba(density, w, h, feather_px, mode_type="TEAM", lut=None):
    """مثل لایه دوبعدی: بلور، کالیبراسیون، فیلتر کمینه و پالت → تصویر RGBA"""
    raw_max = float(density.max())
    if raw_max <= 0.01:
        return None

    sigma_cells = max(calib_blur_m / 0.5 * 0.7, 0.8)
    radius_cells = int(math.ceil(sigma_cells * 2.5))
    k_1d = np.exp(-0.5 * (np.arange(-radius_cells, radius_cells + 1) / sigma_cells) ** 2)
    k_1d /= k_1d.sum()

    temp = np.apply_along_axis(lambda m: np.convolve(m, k_1d, mode='same'), axis=1, arr=density)
    smoothed = np.apply_along_axis(lambda m: np.convolve(m, k_1d, mode='same'), axis=0, arr=temp)

    effective_ceiling = calib_ceiling * (2.8 if mode_type == "TEAM" else 1.0)
    ratio = np.clip(smoothed * calib_gain / effective_ceiling, 0.0, 1.0)
    norm = np.power(ratio, calib_gamma)

    if calib_cutoff > 0.001:
        mask = norm >= calib_cutoff
        norm_filtered = np.zeros_like(norm)
        norm_filtered[mask] = (norm[mask] - calib_cutoff) / (1.0 - calib_cutoff + 1e-6)
        norm = norm_filtered

    gray_img = Image.fromarray((norm * 255).astype(np.uint8))
    gray = gray_img.resize((int(w), int(h)), resample=Image.Resampling.BICUBIC)
    if feather_px > 0.5:
        gray = gray.filter(ImageFilter.GaussianBlur(radius=feather_px))

    lut_img = LALIGA_LUT if lut is None else lut
    return Image.fromarray(lut_img[np.array(gray)])

def build_broadcast_lut():
    """پالت پخش تلویزیونی مطابق مرجع: سبز → زرد → نارنجی → قرمز روشن"""
    stops = [
        (0.00, 60, 190, 30, 0),
        (0.06, 80, 208, 18, 80),
        (0.30, 148, 226, 0, 170),
        (0.50, 238, 232, 0, 210),
        (0.72, 252, 142, 0, 238),
        (0.88, 248, 58, 0, 248),
        (1.00, 247, 25, 0, 252),
    ]
    lut = np.zeros((256, 4), dtype=np.uint8)
    for i in range(256):
        t = i / 255.0
        for s in range(len(stops) - 1):
            t0, c0 = stops[s][0], stops[s][1:]
            t1, c1 = stops[s + 1][0], stops[s + 1][1:]
            if t0 <= t <= t1:
                f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                lut[i] = [int(c0[k] * (1 - f) + c1[k] * f) for k in range(4)]
                break
        else:
            lut[i] = stops[-1][1:]
    return lut

BROADCAST_LUT = build_broadcast_lut()

def _find_coeffs(pa, pb):
    """هاوموگرافی خروجی→تکسچر برای Image.transform (چهار جفت نقطه)"""
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0] * p1[0], -p2[0] * p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1] * p1[0], -p2[1] * p1[1]])
    A = np.array(matrix, dtype=np.float64)
    B = np.array(pb, dtype=np.float64).reshape(8)
    try:
        return np.linalg.solve(A, B)
    except np.linalg.LinAlgError:
        return np.linalg.lstsq(A, B, rcond=None)[0]

def build_flat_pitch_texture(heat_rgba):
    """تکسچر تخت سکوی چمن: چمن واقعی بازی (سبز اشباع + دانه علف + لکه) + راه‌راه + خطوط + هیت‌مپ"""
    rng = np.random.default_rng(7)

    xs = np.arange(TEX_W)
    light_cols = ((xs // (TEX_W / 14.0)).astype(int) % 2) == 0

    base = np.empty((TEX_H, TEX_W, 3), dtype=np.float32)
    base[:] = R_GRASS_DARK
    base[:, light_cols] = R_GRASS_LIGHT

    # دانه‌های ریز علف
    base += rng.normal(0.0, 8.5, (TEX_H, TEX_W, 1)).astype(np.float32)

    # لکه‌های نرم بزرگ‌مقیاس (بافت طبیعی چمن بازی)
    m_small = rng.integers(0, 256, (max(2, TEX_H // 26), max(2, TEX_W // 26)), dtype=np.uint8)
    m_img = Image.fromarray(m_small).resize((TEX_W, TEX_H), Image.Resampling.BILINEAR)
    mottle = (np.asarray(m_img).astype(np.float32) - 127.5) / 127.5 * 14.0
    base[:, :, 0] += mottle * 0.45
    base[:, :, 1] += mottle
    base[:, :, 2] += mottle * 0.25

    base = np.clip(base, 0, 255).astype(np.uint8)
    img = Image.fromarray(base).convert("RGBA")
    draw = ImageDraw.Draw(img)

    def w2c(x, z):
        cx = ((x - TEX_X_MIN) / (TEX_X_MAX - TEX_X_MIN)) * TEX_W
        cy = ((z - TEX_Z_MIN) / (TEX_Z_MAX - TEX_Z_MIN)) * TEX_H
        return cx, cy

    ppm = TEX_W / (TEX_X_MAX - TEX_X_MIN)     # پیکسل بر متر (در هر دو محور یکسان)
    lw = max(4, int(round(0.34 * ppm)))
    spot_r = max(4, int(round(0.22 * ppm)))

    c1 = w2c(PITCH_LINE_X_MIN, PITCH_LINE_Z_MIN)
    c2 = w2c(PITCH_LINE_X_MAX, PITCH_LINE_Z_MAX)
    mid = w2c(0.0, 0.0)
    r_c = 9.15 * ppm

    draw.rectangle([c1[0], c1[1], c2[0], c2[1]], outline=R_LINE_COL, width=lw)
    draw.line([mid[0], c1[1], mid[0], c2[1]], fill=R_LINE_COL, width=lw)
    draw.ellipse([mid[0] - r_c, mid[1] - r_c, mid[0] + r_c, mid[1] + r_c], outline=R_LINE_COL, width=lw)
    draw.ellipse([mid[0] - spot_r, mid[1] - spot_r, mid[0] + spot_r, mid[1] + spot_r], fill=R_LINE_COL)

    for sgn in (-1.0, 1.0):
        p_a = w2c(sgn * 52.5, -20.16); p_b = w2c(sgn * 36.0, 20.16)
        draw.rectangle([min(p_a[0], p_b[0]), p_a[1], max(p_a[0], p_b[0]), p_b[1]], outline=R_LINE_COL, width=lw)
        g_a = w2c(sgn * 52.5, -9.16); g_b = w2c(sgn * 47.0, 9.16)
        draw.rectangle([min(g_a[0], g_b[0]), g_a[1], max(g_a[0], g_b[0]), g_b[1]], outline=R_LINE_COL, width=lw)
        spot = w2c(sgn * 41.5, 0.0)
        draw.ellipse([spot[0] - spot_r, spot[1] - spot_r, spot[0] + spot_r, spot[1] + spot_r], fill=R_LINE_COL)
        if sgn < 0:
            draw.arc([spot[0] - r_c, spot[1] - r_c, spot[0] + r_c, spot[1] + r_c], start=307, end=53, fill=R_LINE_COL, width=lw)
        else:
            draw.arc([spot[0] - r_c, spot[1] - r_c, spot[0] + r_c, spot[1] + r_c], start=127, end=233, fill=R_LINE_COL, width=lw)

    r_crn = 1.0 * ppm
    draw.arc([c1[0] - r_crn, c1[1] - r_crn, c1[0] + r_crn, c1[1] + r_crn], start=0, end=90, fill=R_LINE_COL, width=lw)
    draw.arc([c1[0] - r_crn, c2[1] - r_crn, c1[0] + r_crn, c2[1] + r_crn], start=270, end=360, fill=R_LINE_COL, width=lw)
    draw.arc([c2[0] - r_crn, c1[1] - r_crn, c2[0] + r_crn, c1[1] + r_crn], start=90, end=180, fill=R_LINE_COL, width=lw)
    draw.arc([c2[0] - r_crn, c2[1] - r_crn, c2[0] + r_crn, c2[1] + r_crn], start=180, end=270, fill=R_LINE_COL, width=lw)

    if heat_rgba is not None:
        img.alpha_composite(heat_rgba)

    # دروازه‌ها — دقیقاً مثل نمای زنده برنامه: سه خط تخت روی چمن
    # (دو تیرک + خط عقب؛ خط دروازه خودش جزو خطوط زمین است — بدون حجم سه‌بعدی و بدون تور)
    glw = max(3, int(round(lw * 0.72)))
    gcol = (238, 246, 239, 225)
    for sgn in (-1.0, 1.0):
        g_out = w2c(sgn * 54.5, -3.66)            # گوشه بیرونی نزدیک
        g_out2 = w2c(sgn * 54.5, 3.66)            # گوشه بیرونی دور
        g_in  = w2c(sgn * 52.5, -3.66)            # تیرک نزدیک روی خط دروازه
        g_in2 = w2c(sgn * 52.5, 3.66)             # تیرک دور روی خط دروازه
        draw.line([g_in,  g_out],  fill=gcol, width=glw)   # تیرک نزدیک
        draw.line([g_in2, g_out2], fill=gcol, width=glw)   # تیرک دور
        draw.line([g_out, g_out2], fill=gcol, width=glw)   # خط عقب

    return img

def _circle_photo(canvas, photo_path, center, r, team_key=None, header_name=""):
    """برش دایره‌ای عکس چهره بازیکن (منبع 360x360) + حلقه آبی روشن مطابق مرجع"""
    cx, cy = center
    glow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], fill=(70, 130, 220, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    canvas.alpha_composite(glow)

    d = ImageDraw.Draw(canvas)
    if photo_path and os.path.isfile(photo_path):
        try:
            im = Image.open(photo_path).convert("RGB")
            w, h = im.size
            s = min(w, h)
            im = im.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
            im = im.resize((2 * r, 2 * r), resample=Image.Resampling.LANCZOS)
            mask = Image.new("L", (2 * r, 2 * r), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
            canvas.paste(im, (cx - r, cy - r), mask)
        except Exception:
            pass
    else:
        # عکس پیدا نشد → سیلوئت با حروف اول اسم
        fill = (150, 12, 62, 255) if team_key == DEFAULT_HOME_KEY else (16, 45, 96, 255)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        initials = "".join(w[0] for w in str(header_name).split()[:2]).upper() if header_name else "?"
        f_ini = load_font(F_BOLD_PATHS, int(r * 0.9))
        try:
            iw = d.textlength(initials, font=f_ini)
            d.text((cx - iw / 2, cy - r * 0.62), initials, font=f_ini, fill=(244, 248, 252, 255))
        except Exception:
            pass

    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RING_COL, width=7)

def _paste_logo(canvas, logo_path, box, fallback_key=None):
    """چسباندن لوگوی 512x512 باشگاه در جعبه؛ در نبود فایل، سپر ساده با رنگ تیم"""
    x0, y0, max_w, max_h = box[0], box[1], box[2], box[3]
    if logo_path and os.path.isfile(logo_path):
        try:
            lg = Image.open(logo_path).convert("RGBA")
            bbox = lg.getbbox()
            if bbox:
                lg = lg.crop(bbox)
            s = min(max_w / lg.width, max_h / lg.height, 4.0)
            lg = lg.resize((max(1, int(lg.width * s)), max(1, int(lg.height * s))), Image.Resampling.LANCZOS)
            canvas.alpha_composite(lg, (int(x0 + (max_w - lg.width) / 2), int(y0 + (max_h - lg.height) / 2)))
            return
        except Exception:
            pass
    # سپر جایگزین با رنگ‌های تیم
    lay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    dd = ImageDraw.Draw(lay)
    cx, cy = x0 + max_w / 2.0, y0 + max_h / 2.0
    w, h = max_w * 0.88, max_h * 0.96
    shield = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h * 0.10),
              (cx + w * 0.30, cy + h * 0.36), (cx, cy + h / 2), (cx - w * 0.30, cy + h * 0.36),
              (cx - w / 2, cy + h * 0.10)]
    dd.polygon(shield, fill=(238, 244, 250, 255), outline=(255, 255, 255, 255), width=3)
    if fallback_key == DEFAULT_HOME_KEY:
        cols = [(0, 77, 152, 255), (165, 0, 68, 255), (0, 77, 152, 255)]
    elif fallback_key == DEFAULT_AWAY_KEY:
        cols = [(200, 16, 46, 255), (235, 240, 248, 255), (200, 16, 46, 255)]
    else:
        cols = [(24, 52, 110, 255), (222, 230, 242, 255), (24, 52, 110, 255)]
    for i, col in enumerate(cols):
        sx = cx - w * 0.27 + i * w * 0.19
        dd.polygon([(sx, cy - h * 0.32), (sx + w * 0.13, cy - h * 0.32),
                    (sx + w * 0.13, cy + h * 0.14), (sx, cy + h * 0.14)], fill=col)
    canvas.alpha_composite(lay)

def _h_gradient_img(w, h, c_l, c_r):
    w, h = max(1, int(w)), max(1, int(h))
    t = np.linspace(0.0, 1.0, w).reshape(1, w, 1)
    a = np.array(c_l, dtype=np.float64).reshape(1, 1, 3)
    b = np.array(c_r, dtype=np.float64).reshape(1, 1, 3)
    row = a * (1 - t) + b * t               # (1, w, 3)
    return Image.fromarray(np.repeat(row, h, axis=0).astype(np.uint8)).convert("RGBA")

def _build_background():
    """پس‌زمینه سرمه‌ای با هاله روشن مرکز-بالا (مطابق مرجع)"""
    W, H = RENDER_W, RENDER_H
    t = np.linspace(0.0, 1.0, H).reshape(H, 1, 1)
    top = np.array(BG_BASE_TOP, dtype=np.float64).reshape(1, 1, 3)
    bot = np.array(BG_BASE_BOT, dtype=np.float64).reshape(1, 1, 3)
    bg = top * (1 - t) + bot * t
    yy, xx = np.mgrid[0:H, 0:W]
    dist = np.sqrt(((xx - W * 0.5) / (W * 0.42)) ** 2 + ((yy - H * 0.24) / (H * 0.42)) ** 2)
    glow_a = np.clip(1.0 - dist, 0.0, 1.0) ** 1.6
    glow = np.array(BG_GLOW_COL, dtype=np.float64).reshape(1, 1, 3)
    bg = bg * (1 - glow_a[..., None] * 0.95) + glow * (glow_a[..., None] * 0.95)
    return Image.fromarray(np.clip(bg, 0, 255).astype(np.uint8)).convert("RGBA")

def render_broadcast_heatmap(density, header, mode_type="TEAM"):
    """ساخت فریم نهایی 1774×887 — هیت‌مپ برنامه به‌صورت تکسچر روی چمن پرسپکتیو"""
    W, H = RENDER_W, RENDER_H

    feather_tex = calib_feather * (TEX_W / CANVAS_W_REF)
    heat_rgba = density_to_heat_rgba(density, TEX_W, TEX_H, feather_tex, mode_type, lut=BROADCAST_LUT)
    texture = build_flat_pitch_texture(heat_rgba)

    canvas = _build_background()
    d = ImageDraw.Draw(canvas, "RGBA")

    # ---------- لایه اول: روبان‌ها، قاب، پنل عنوان، کارت ----------
    # (عناصر نیمه‌شفاف روی Overlay رسم می‌شوند تا درست ترکیب شوند)
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)

    # روبان‌های مورب ظریف گوشه‌ها
    od.polygon([(22, 128), (22, 54), (148, 22), (226, 22)], fill=(120, 170, 235, 14))
    od.polygon([(W - 22, 128), (W - 22, 54), (W - 226, 22), (W - 148, 22)], fill=(120, 170, 235, 14))

    # قاب نئونی (هاله جدا برای بلور)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.rounded_rectangle([22, 22, W - 22, H - 22], radius=42, outline=(120, 168, 230, 190), width=8)
    glow = glow.filter(ImageFilter.GaussianBlur(10))
    canvas.alpha_composite(glow)
    od.rounded_rectangle([22, 22, W - 22, H - 22], radius=42, outline=FRAME_COL, width=5)
    od.rounded_rectangle([34, 34, W - 34, H - 34], radius=32, outline=FRAME_INNER, width=1)

    # پنل عنوان
    PTL, PTR, PBR, PBL = (408, 6), (1408, 6), (1443, 106), (373, 106)
    tt = np.linspace(0.0, 1.0, 100).reshape(100, 1, 1)
    c_top = np.array(PANEL_TOP, dtype=np.float64).reshape(1, 1, 3)
    c_bot = np.array(PANEL_BOT, dtype=np.float64).reshape(1, 1, 3)
    grad = np.repeat(c_top * (1 - tt) + c_bot * tt, 1080, axis=1).astype(np.uint8)
    pgrad = Image.fromarray(grad).convert("RGBA")
    pmask = Image.new("L", (1080, 100), 0)
    ImageDraw.Draw(pmask).polygon([(PTL[0] - 373, 0), (PTR[0] - 373, 0), (PBR[0] - 373, 100), (PBL[0] - 373, 100)], fill=255)
    canvas.paste(pgrad, (373, 6), pmask)

    # برش‌های مورب ظریف داخل پنل
    od.polygon([(560, 6), (700, 6), (640, 106), (500, 106)], fill=(255, 255, 255, 7))
    od.polygon([(1180, 6), (1300, 6), (1252, 106), (1132, 106)], fill=(0, 0, 0, 16))

    # پنل کارت بازیکن/تیم
    od.rounded_rectangle([55, 96, 1085, 278], radius=18, fill=(13, 42, 92, 55), outline=(86, 132, 198, 70), width=2)

    # خطوط لبه پنل عنوان — بعد از پنل کارت تا زیرشان پنهان نشود
    for x in range(PTL[0], PTR[0], 4):
        f1 = math.exp(-(((x + 2) - W / 2) / 470.0) ** 2)
        od.rectangle([x, 5, x + 4, 7], fill=PANEL_EDGE_T + (int(30 + 200 * f1),))
        f2 = math.exp(-(((x + 2) - W / 2) / 620.0) ** 2)
        od.rectangle([x, 104, x + 4, 108], fill=PANEL_EDGE_B + (int(50 + 205 * f2),))

    # عنوان (با فاصله بین حروف — درخواست کاربر)
    title = "HEATMAP"
    f_title, tr_title = fit_font_tracked(od, title, F_TITLE_PATHS, 88, 620)
    _draw_tracked_text(od, W / 2 + 2, 62 + 3, title, f_title, (0, 10, 30, 150), tr_title)
    _draw_tracked_text(od, W / 2, 62, title, f_title, TXT_WHITE, tr_title)
    bar_x0, bar_y0, bar_y1 = 312, 127, 182
    bar_slant = 22

    kind = header.get("kind", "all")
    circle_c = (202, 192)
    circle_r = 127

    if kind == "player":
        name = header.get("name", "PLAYER")
        max_bar_w = 1000
    elif kind == "team":
        name = header.get("text", "TEAM")
        max_bar_w = 1000
    else:
        name = header.get("text", "")
        max_bar_w = 1150

    # ---------- نوار گرادیانی اسم ----------
    f_name = fit_font(d, name, F_BOLD_PATHS, 48, 900)
    text_x = 385
    name_w = d.textlength(name, font=f_name)
    bar_w = int(max(150, min(max_bar_w, (text_x - bar_x0) + name_w + 55)))
    bar_grad = _h_gradient_img(bar_w, bar_y1 - bar_y0, BAR_COL_L, BAR_COL_R)
    bmask = Image.new("L", (bar_w, bar_y1 - bar_y0), 0)
    ImageDraw.Draw(bmask).polygon([(0, 0), (bar_w, 0), (bar_w - bar_slant, bar_y1 - bar_y0), (0, bar_y1 - bar_y0)], fill=255)
    canvas.paste(bar_grad, (bar_x0, bar_y0), bmask)

    # خط ظریف زیر نوار (در مرکز روشن‌تر)
    for x in range(bar_x0, bar_x0 + bar_w + 120, 4):
        f3 = math.exp(-((x - (bar_x0 + 160)) / 420.0) ** 2)
        od.rectangle([x, 187, x + 4, 190], fill=(110, 158, 225, int(60 + 150 * f3)))

    # متن اسم
    od.text((text_x, 154), name, font=f_name, fill=TXT_WHITE, anchor="lm")

    # ترکیب لایه اول با بوم
    canvas.alpha_composite(ov)
    d = ImageDraw.Draw(canvas, "RGBA")

    # ---------- زمین سه‌بعدی (پرسپکتیو از تکسچر برنامه) ----------
    # دروازه‌ها به‌صورت سه خط تخت داخل تکسچر چمن رسم شده‌اند و با همین
    # تبدیل پرسپکتیو روی زمین می‌نشینند (شبیه نمای زنده برنامه)
    coeffs = _find_coeffs([PFL, PFR, PNR, PNL], [(0, 0), (TEX_W, 0), (TEX_W, TEX_H), (0, TEX_H)])
    pitched = texture.transform((W, H), Image.PERSPECTIVE, tuple(coeffs), resample=Image.Resampling.BICUBIC)
    canvas.alpha_composite(pitched)

    # نوار روشن زیر لبه پایین سکو (سطح بریده چمن)
    strip_w = int(PNR[0] - PNL[0])
    strip_h = 13
    strip = np.zeros((strip_h, strip_w, 4), dtype=np.uint8)
    st = np.linspace(0.0, 1.0, strip_h).reshape(strip_h, 1)
    strip[:, :, :3] = (206, 238, 198)
    strip[:, :, 3] = (200 * (1 - st)).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(strip), (int(PNL[0]), int(PNL[1])))

    # لبه ظریف دور سکو (دروازه‌ها تخت داخل تکسچر چمن رسم می‌شوند)
    ov2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od2 = ImageDraw.Draw(ov2)
    od2.polygon([PFL, PFR, PNR, PNL], outline=(4, 30, 12, 90), width=2)
    canvas.alpha_composite(ov2)

    # ---------- دایره بازیکن / نشان تیم ----------
    cx, cy = circle_c
    if kind == "player":
        _circle_photo(canvas, header.get("photo_path"), circle_c, circle_r,
                      header.get("team_key"), header.get("name", ""))
    else:
        glow2 = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        g2 = ImageDraw.Draw(glow2)
        g2.ellipse([cx - circle_r - 10, cy - circle_r - 10, cx + circle_r + 10, cy + circle_r + 10],
                   fill=(70, 130, 220, 80))
        glow2 = glow2.filter(ImageFilter.GaussianBlur(14))
        canvas.alpha_composite(glow2)
        d.ellipse([cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r], fill=(10, 34, 78, 255))
        if kind == "team":
            _paste_logo(canvas, header.get("logo_path"),
                        (cx - circle_r * 0.62, cy - circle_r * 0.62, circle_r * 1.24, circle_r * 1.24),
                        header.get("team_key"))
        else:
            _paste_logo(canvas, header.get("logo_home"),
                        (cx - circle_r * 0.92, cy - circle_r * 0.58, circle_r * 0.84, circle_r * 1.16),
                        home_team_key)
            _paste_logo(canvas, header.get("logo_away"),
                        (cx + circle_r * 0.08, cy - circle_r * 0.58, circle_r * 0.84, circle_r * 1.16),
                        away_team_key)
        d.ellipse([cx - circle_r, cy - circle_r, cx + circle_r, cy + circle_r], outline=RING_COL, width=7)

    # ---------- لوگوی باشگاه زیر نوار اسم ----------
    if kind == "player":
        _paste_logo(canvas, header.get("logo_path"), (330, 205, 78, 72), header.get("team_key"))
    elif kind == "team":
        _paste_logo(canvas, header.get("logo_path"), (330, 205, 78, 72), header.get("team_key"))
    else:
        _paste_logo(canvas, header.get("logo_home"), (330, 205, 72, 66), home_team_key)
        _paste_logo(canvas, header.get("logo_away"), (418, 205, 72, 66), away_team_key)

    return canvas

def build_broadcast_gpu_assets(density, header, mode_type="TEAM"):
    """[Broadcast GPU] تنها منبع داده‌ی موتور BroadcastRenderer — بدون هیچ الگوریتم جدید:
         heat_rgba   = عیناً خروجی density_to_heat_rgba برنامه (همان هیت‌مپ)
         pitch_plate = عیناً خروجی build_flat_pitch_texture بدون گرما (چمن+خطوط+دروازه تخت)
         tex_range   = بازه تکسچر سکو برای نگاشت دقیق uv داخل شیدر (قرارداد مختصات)
         fonts       = مسیر فونت‌های ویندوز برنامه"""
    feather_tex = calib_feather * (TEX_W / CANVAS_W_REF)
    heat_rgba = density_to_heat_rgba(density, TEX_W, TEX_H, feather_tex, mode_type, lut=BROADCAST_LUT)
    pitch_plate = build_flat_pitch_texture(None)
    return {"heat_rgba": heat_rgba, "pitch_plate": pitch_plate,
            "header": dict(header), "mode_type": mode_type,
            "tex_range": (TEX_X_MIN, TEX_X_MAX, TEX_Z_MIN, TEX_Z_MAX),
            "fonts": {"title": list(F_TITLE_PATHS), "bold": list(F_BOLD_PATHS)}}

# === [3D-RENDER-END] ===
# =============================================================
# ۶.۸ — Second Broadcast Layer: کنترلر خودکار اورلی هیت‌مپ بازیکن
# =============================================================
#  پنجره برودکاست در دقیقه مشخص مسابقه «خودش» ظاهر می‌شود — عین قوانین غیرقابل‌مذاکره:
#    ① انتخاب تصادفی فقط از «بازیکنان واقعی شناسایی‌شده هر دو تیم» (بدون وزن)
#    ② Preload کامل (آپلود GPU) چند ثانیه قبل از لحظه نمایش؛ Show فقط یک پیام
#    ③ پنجره یک‌بار در boot ساخته می‌شود، مخفی می‌ماند و هرگز جابه‌جا نمی‌شود —
#       تمام انیمیشن‌ها روی GPU. glfw.init فقط یک‌بار در کل پروسه (ریشه‌کن‌شدن
#       باگ «Class already exists» و «glfw.init failed»).
#  Trigger با «زمان بازی» است (نه time.time) —跨越 ساعت هم یک‌بار آتش می‌گیرد؛
#  مدت نمایش با Wall Clock (مستقل از توقف/ریپلی).

AUTO_HEATMAP_ENABLED         = True
AUTO_HEATMAP_MINUTE          = 75      # دقیقه تریگر (مجاز: 70 تا 80)
AUTO_HEATMAP_DISPLAY_SEC     = 10.0    # مدت نمایش (پیشنهاد: 3 تا 60)
AUTO_HEATMAP_SELECT_LEAD_SEC = 8.0     # فاصله انتخاب/Preload قبل از تریگر
AUTO_HEATMAP_RETRY_MAX       = 6       # حداکثر تلاش (بند ۳۲)
AUTO_HEATMAP_RETRY_DELAY     = 3.0     # فاصله تلاش مجدد (ثانیه)
OVERLAY_WIDTH_FRAC           = 0.33    # عرض پنجره = کسر از عرض صفحه
OVERLAY_HEIGHT_FRAC          = 0.32    # ارتفاع پنجره = کسر از ارتفاع صفحه

# ─────────────────────────────────────────────────────────────────────────────
#  حالت آزمون «زمانِ تقلبی» (FAKE TIME TEST) — نسخه ۱۴٫۰
#  اگر هیت‌مپ هرگز نمایش داده نمی‌شود: این گزینه را True کنید تا ساعتِ واقعی
#  بازی نادیده گرفته شود و تریگر اورلی با ساعت تقلبی کار کند.
#    ● AUTO_HEATMAP_FAKE_TIME_ENABLED   = False/True  (پیش‌فرض: False)
#    ● AUTO_HEATMAP_FAKE_TIME_START_MIN = دقیقه شروع (عدد اعشاری مجاز؛ 74.5 = 74:30)
#    ● AUTO_HEATMAP_FAKE_TIME_SPEED     = سرعت ساعت تقلبی: ثانیه‌بازی در هر
#      ثانیه‌واقعی (1.0 = مثل ساعت پخش تلویزیونی؛ 0 = ثابت روی minute شروع)
#  تفسیر نتیجه:
#    ✔ پنجره ظاهر شد ⇒ کل مسیر نمایش سالم است؛ مشکل از خواندن ساعت بازی بود
#      (هوک دقیقه/ثانیه روی دستگاه شما کار نمی‌کند — لاگ [AUTO_HEATMAP] را ببینید)
#    ✘ پنجره ظاهر نشد ⇒ لاگ [AUTO_HEATMAP] + نوار «AUTO overlay» پایین پنجره
#      برنامه علت دقیق را می‌گوید (موتور قطع؟ بازیکن واجد شرایط نیست؟ ...)
#  توجه: در این حالت با هر ورود مجدد به مسابقه، اورلی یک‌بار دیگر هم نمایش
#  داده می‌شود (reset مسابقه) — برای تکرار آزمون عالی است.
AUTO_HEATMAP_FAKE_TIME_ENABLED   = False
AUTO_HEATMAP_FAKE_TIME_START_MIN = 75.0
AUTO_HEATMAP_FAKE_TIME_SPEED     = 1.0


class _FakeGameClock:
    """ساعت تقلبی برای آزمون مسیر نمایش اورلی — فقط جایگزین feed کنترلر
       AUTO_CTRL می‌شود (ساعت نمایشی GUI و منطق شناسایی دست‌نخورده می‌مانند)."""

    def __init__(self):
        self.enabled = bool(AUTO_HEATMAP_FAKE_TIME_ENABLED)
        self.start_min = float(AUTO_HEATMAP_FAKE_TIME_START_MIN)
        self.start_sec = max(0.0, self.start_min) * 60.0
        self.speed = max(0.0, float(AUTO_HEATMAP_FAKE_TIME_SPEED))
        self._t0 = time.monotonic()

    def game_sec(self):
        """None = غیرفعال (feed واقعی مسابقه)؛ وگرنه ثانیه‌بازیِ تقلبی int"""
        if not self.enabled:
            return None
        return int(self.start_sec + self.speed * (time.monotonic() - self._t0))

    def label(self):
        m = int(self.start_min)
        s = int(round((float(self.start_min) - m) * 60.0))
        if s >= 60:
            m, s = m + 1, 0
        return f"{m:02d}:{s:02d}"


FAKE_CLOCK = _FakeGameClock()
if FAKE_CLOCK.enabled:
    print(f"[AUTO_HEATMAP] *** FAKE TIME MODE ON — clock starts at {FAKE_CLOCK.label()} "
          f"speed={FAKE_CLOCK.speed} — REAL MATCH CLOCK IS IGNORED ***", flush=True)

_AUTO_BR_MODULE = None       # ماژول BroadcastRenderer (یک‌بار import)
_AUTO_ENGINE = None          # OverlayEngine مقیم
_AUTO_ENGINE_FAIL_REASON = None   # علت شکست boot موتور (برای نوار وضعیت GUI)


def ensure_auto_overlay_engine():
    """boot موتور اورلی — فقط یک‌بار، در شروع برنامه، non-blocking.
       شکست → لاگ شفاف + اورلی خودکار غیرفعال برای «همین اجرا» (کلید R سالم می‌ماند)."""
    global _AUTO_BR_MODULE, _AUTO_ENGINE, _AUTO_ENGINE_FAIL_REASON
    if _AUTO_ENGINE is not None:
        return _AUTO_ENGINE
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        import BroadcastRenderer as _br
        _AUTO_BR_MODULE = _br
        _AUTO_ENGINE = _br.OverlayEngine.start(
            width_frac=OVERLAY_WIDTH_FRAC, height_frac=OVERLAY_HEIGHT_FRAC)
    except Exception as ex:
        _AUTO_ENGINE_FAIL_REASON = f"{type(ex).__name__}: {ex}"
        print(f"[AUTO_HEATMAP] ENGINE INIT FAILED — {_AUTO_ENGINE_FAIL_REASON}",
              file=sys.stderr, flush=True)
        _AUTO_ENGINE = None
    return _AUTO_ENGINE


class AutoPlayerBroadcastController:
    """ماشین حالت اورلی خودکار — فقط منطق و تایمینگ؛ رندر صفر.

       WAITING → PREPARING → READY → SHOWING → VISIBLE → EXITING → DONE
       (خطا → FAILED REASON → تلاش مجدد هر ۳ ثانیه، حداکثر ۶ بار)
       tick از ترد ردیاب ۳۰Hz با «زمان بازی» صدا زده می‌شود؛ کار سنگین هرگز
       در همین ترد انجام نمی‌شود (Preload در ترد جدا — بند ۹/۱۰)."""

    def __init__(self):
        self.state = "WAITING"
        self.triggered = False          # تریگر این مسابقه آتش گرفته؟ (یک‌بار)
        self.selected = None
        self.attempt = 0
        self._t_visible_wall = None     # شروع شمارش مدت نمایش (Wall Clock)
        self._t_triggered_wall = None
        self._next_retry_wall = 0.0
        self._prep_thread = None
        self._prep_error = None
        self._reshow_after_ready = False
        self._last_game_sec = 0
        # — تشخیص‌پذیری (v14.0): هرگز بدون توضیح ساکت نمی‌مانیم —
        self._eng_missing_logged = False   # «موتور نیست» فقط یک‌بار در هر مسابقه
        self._armed_logged = False         # «ساعت رسید، تریگر مسلح شد» یک‌بار
        self._fake_wait_log_wall = 0.0     # لاگ دوره‌ای انتظار در حالت زمان تقلبی

    # ---------------- کمکی ----------------
    def _log(self, game_sec, msg):
        try:
            m, s = int(game_sec) // 60, int(game_sec) % 60
            print(f"[AUTO_HEATMAP] {m:02d}:{s:02d} {msg}", flush=True)
        except Exception:
            # [SUITE v2.1.4] the old fallback re-printed the SAME (possibly
            # non-encodable) text and raised a SECOND time from inside the
            # except handler — aborting the caller (e.g. _start_prepare)
            # mid-state-transition and wedging the AUTO overlay in WAITING.
            # Sanitize instead; with the v2.1.4 stdio hardening this path is
            # belt-and-braces only.
            try:
                safe = str(msg).encode("ascii", "replace").decode("ascii")
                print(f"[AUTO_HEATMAP] --:-- {safe}", flush=True)
            except Exception:
                pass

    def _engine(self):
        eng = _AUTO_ENGINE
        if eng is None or not eng.is_alive():
            return None
        return eng

    def reset(self):
        """Match-aware reset: مسابقه جدید/ری‌استارت → همه‌چیز از WAITING (بند ۳۶)"""
        if self.state == "WAITING" and not self.triggered and self.selected is None:
            return                      # از قبل ریست — بدون لاگ تکراری
        eng = self._engine()
        if eng is not None:
            try:
                eng.hide_now()
            except Exception:
                pass
        self.state = "WAITING"
        self.triggered = False
        self.selected = None
        self.attempt = 0
        self._t_visible_wall = None
        self._t_triggered_wall = None
        self._prep_error = None
        self._reshow_after_ready = False
        self._eng_missing_logged = False
        self._armed_logged = False
        self._log(self._last_game_sec, "STATE=WAITING (match reset)")

    # ---------------- انتخاب بازیکن (بند ۶/۷) ----------------
    def _eligible_pool(self):
        """ادغام دو تیم — فقط هویت واقعی شناسایی‌شده؛ اعتبارسنجی ۴گانه Name/Photo/Logo/Heat
           خروجی: (pool, stats) — stats علت خالی‌بودن استخر را شمارش می‌کند (v14.0)"""
        pool = []
        stats = {"checked": 0, "unnamed": 0, "no_photo": 0, "no_logo": 0,
                 "no_heat": 0, "other_side": 0}
        with entities_lock:
            ents = list(entities)
        for idx in OUTFIELD_INDICES:
            if idx >= len(ents):
                continue
            stats["checked"] += 1
            ent = ents[idx]
            name_fa = ent.get("confirmed_name")
            code = ent.get("code")
            if not name_fa or code is None:
                stats["unnamed"] += 1
                continue                                    # هویت تأییدنشده
            team = ent.get("team", 1) or 1
            # [SUITE v1.0.0] viewer-side filter (user setting):
            # home = only home players, away = only away players,
            # random (default) = both teams as before
            if HM_VIEWER_SIDE == "home" and team != 1:
                stats["other_side"] += 1
                continue
            if HM_VIEWER_SIDE == "away" and team != 2:
                stats["other_side"] += 1
                continue
            team_key = home_team_key if team == 1 else away_team_key
            roster = team_roster(team_key)
            name_en = roster.get(code) or str(name_fa)
            photo = find_player_photo(team_key, code)
            logo = find_team_logo(team_key)
            if not photo or not os.path.isfile(photo):
                stats["no_photo"] += 1
                continue                                    # عکس بازیکن ✗
            if not logo or not os.path.isfile(logo):
                stats["no_logo"] += 1
                continue                                    # لوگوی باشگاه ✗
            try:
                with heatmap_lock:
                    if float(np.sum(entity_heatmaps[idx])) < 30.0:
                        stats["no_heat"] += 1
                        continue                            # هیت‌مپ خالی ✗
            except Exception:
                stats["no_heat"] += 1
                continue
            pool.append({"idx": idx, "team_key": team_key, "code": code,
                         "name": name_en.upper(), "photo": photo, "logo": logo})
        return pool, stats

    @staticmethod
    def _pool_stats_text(s):
        """متن فشرده شمارش ردشدگان — در لاگ FAILED/انتظار می‌آید"""
        try:
            return (f"checked={s['checked']} unnamed={s['unnamed']} "
                    f"no_photo={s['no_photo']} no_logo={s['no_logo']} no_heat={s['no_heat']} "
                    f"other_side={s.get('other_side', 0)} side={HM_VIEWER_SIDE}")
        except Exception:
            return "stats=?"

    def _start_prepare(self, game_sec, cand):
        """Preload در ترد جدا — هرگز روی ترد ۳۰Hz (بند ۹)"""
        self.selected = cand
        self._prep_error = None
        self._log(game_sec,
                  f"PLAYER_SELECTED={cand['name']} "
                  f"TEAM={'HOME' if cand['team_key'] == home_team_key else 'AWAY'} "
                  f"({team_display_name(cand['team_key'])}) CODE={cand['code']}")
        self.state = "PREPARING"
        self._log(game_sec, f"STATE=PREPARING attempt={self.attempt}/{AUTO_HEATMAP_RETRY_MAX}")
        self._prep_thread = threading.Thread(
            target=self._prepare_worker, args=(dict(cand),), daemon=True)
        self._prep_thread.start()

    def _prepare_worker(self, cand):
        """ساخت Asset (عیناً از توابع موجود — هیچ الگوریتم جدیدی) + آپلود GPU"""
        try:
            eng = self._engine()
            if eng is None:
                raise RuntimeError("overlay engine is not alive")
            density = compute_density_snapshot([cand["idx"]])
            header = {"kind": "player", "name": cand["name"],
                      "team_en": team_display_name(cand["team_key"]),
                      "team_key": cand["team_key"], "code": cand["code"],
                      "photo_path": cand["photo"], "logo_path": cand["logo"]}
            assets = build_broadcast_gpu_assets(density, header, "PLAYER")
            if assets.get("heat_rgba") is None:
                raise RuntimeError("heat_rgba is empty")
            eng.prepare_player_overlay(assets)      # فقط پیام — چند میلی‌ثانیه
        except Exception as ex:
            self._prep_error = f"{type(ex).__name__}: {ex}"

    # ---------------- تیک اصلی (از ترد ۳۰Hz — سبک) ----------------
    def tick(self, game_sec):
        if not AUTO_HEATMAP_ENABLED:
            return
        self._last_game_sec = int(game_sec)
        st = self.state
        target_sec = int(HM_DISPLAY_MINUTE) * 60   # [SUITE] settings-driven

        if st == "WAITING":
            eng = self._engine()
            if eng is None:
                # v14.0 — هرگز ساکت نیستیم: اگر موتور اورلی از boot نیامده،
                # هیت‌مپ به‌هیچ‌وجه نمایش داده نمی‌شود؛ علت را یک‌بار می‌گوییم
                if not self._eng_missing_logged:
                    self._eng_missing_logged = True
                    self._log(game_sec,
                              "OVERLAY ENGINE NOT AVAILABLE — overlay can NEVER show this run "
                              f"(reason: {_AUTO_ENGINE_FAIL_REASON or 'see ENGINE INIT FAILED above'})")
                return
            # تریگر آتشیده و در حالت بازیابی (FAILED→READY→SHOWING) نیستیم → هیچ
            if self.triggered and not self._reshow_after_ready:
                return
            now_w = time.monotonic()
            if now_w < self._next_retry_wall:
                return
            # v14.0 — «مسلح‌شدن»: اولین‌بار که ساعت به ۵ دقیقهٔ آخر قبل از تریگر
            # رسید اعلام می‌کنیم که feed ساعت زنده است (اگر این لاگ نیامد، یعنی
            # هوک دقیقه/ثانیهٔ بازی هیچ‌وقت به پنجرهٔ تریگر نرسیده)
            if (not self._armed_logged
                    and target_sec - 300.0 <= game_sec < target_sec):
                self._armed_logged = True
                self._log(game_sec,
                          f"CLOCK FEED OK — trigger armed for "
                          f"{int(HM_DISPLAY_MINUTE):02d}:00 (feed {int(game_sec)//60:02d}:{int(game_sec)%60:02d})")
            # انتخاب فقط از دو تیم — بدون وزن (بند ۶)
            if game_sec >= target_sec - AUTO_HEATMAP_SELECT_LEAD_SEC:
                pool, pool_stats = self._eligible_pool()
                if not pool:
                    if FAKE_CLOCK.enabled:
                        # حالت آزمون زمان تقلبی: در منو/قبل از شناسایی بازیکنان
                        # «شکست» حساب نمی‌شود — فقط صبر؛ تا هویت/عکس/لوگو آماده شود
                        # (attempt هم زیاد نمی‌شود — بند ۳۲ فقط برای مسابقه واقعی)
                        if now_w >= self._fake_wait_log_wall:
                            self._fake_wait_log_wall = now_w + 10.0
                            self._log(game_sec,
                                      "FAKE-TIME waiting for eligible player... "
                                      f"[{self._pool_stats_text(pool_stats)}]")
                        self._next_retry_wall = now_w + 5.0
                        return
                    self.attempt += 1
                    self._log(game_sec,
                              f"FAILED REASON=no eligible player "
                              f"[{self._pool_stats_text(pool_stats)}] "
                              f"(attempt={self.attempt}/{AUTO_HEATMAP_RETRY_MAX})")
                    self._schedule_retry_or_giveup(game_sec)
                    return
                self.attempt += 1
                cand = random.choice(pool)          # تصادفی خالص — بعد از انتخاب freeze
                self._start_prepare(game_sec, cand)

        elif st == "PREPARING":
            eng = self._engine()
            if eng is None:
                self._log(game_sec, "FAILED REASON=engine dead")
                self._schedule_retry_or_giveup(game_sec)
                return
            if self._prep_error is not None:
                self._log(game_sec, f"FAILED REASON={self._prep_error} "
                                    f"(attempt={self.attempt}/{AUTO_HEATMAP_RETRY_MAX})")
                self._schedule_retry_or_giveup(game_sec)
                return
            es = eng.state()
            if es == "READY":
                self.state = "READY"
                self._log(game_sec, "STATE=READY (GPU scene preloaded)")
            elif es == "FAILED":
                self._log(game_sec, f"FAILED REASON={eng.fail_reason()} "
                                    f"(attempt={self.attempt}/{AUTO_HEATMAP_RETRY_MAX})")
                self._schedule_retry_or_giveup(game_sec)

        elif st == "READY":
            eng = self._engine()
            if eng is None or eng.state() == "FAILED":
                self._log(game_sec, f"FAILED REASON={eng.fail_reason() if eng else 'engine dead'}")
                self._schedule_retry_or_giveup(game_sec)
                return
            # مسیر FAILED→READY→SHOWING — اگر تریگر در پنجره نمایش بود، دوباره Show
            if self.triggered and self._reshow_after_ready:
                self._reshow_after_ready = False
                if (self._t_triggered_wall is not None
                        and time.monotonic() - self._t_triggered_wall
                        < AUTO_HEATMAP_DISPLAY_SEC + 90.0):
                    eng.show_player_overlay()
                    self.state = "SHOWING"
                    self._log(game_sec, "STATE=SHOWING (retry after failure)")
                else:
                    self.state = "DONE"
                    self._log(game_sec, "STATE=DONE")
                return
            # Transactional Trigger — پرش/گذر از ساعت هم دقیقاً یک‌بار (بند ۳۱)
            if game_sec >= target_sec and not self.triggered:
                self.triggered = True
                self._t_triggered_wall = time.monotonic()
                eng.show_player_overlay()           # فقط یک پیام (زیر 0.1ms)
                self.state = "SHOWING"
                self._log(game_sec, "STATE=SHOWING (entry animation)")

        elif st == "SHOWING":
            eng = self._engine()
            if eng is None:
                self._log(game_sec, "FAILED REASON=engine dead")
                self._schedule_retry_or_giveup(game_sec, allow_reshow=True)
                return
            es = eng.state()
            if es == "VISIBLE":
                self._t_visible_wall = time.monotonic()
                self.state = "VISIBLE"
                self._log(game_sec, "STATE=VISIBLE (live micro-animation)")
            elif es == "FAILED":
                self._log(game_sec, f"FAILED REASON={eng.fail_reason()}")
                self._schedule_retry_or_giveup(game_sec, allow_reshow=True)

        elif st == "VISIBLE":
            eng = self._engine()
            if eng is None:
                self._log(game_sec, "FAILED REASON=engine dead")
                self.state = "DONE"
                self._log(game_sec, "STATE=DONE")
                return
            es = eng.state()
            if es == "FAILED":
                self._log(game_sec, f"FAILED REASON={eng.fail_reason()}")
                self.state = "DONE"
                self._log(game_sec, "STATE=DONE")
                return
            # مدت نمایش با Wall Clock — مستقل از توقف/ریپلی بازی (بند ۴)
            if (self._t_visible_wall is not None
                    and time.monotonic() - self._t_visible_wall >= AUTO_HEATMAP_DISPLAY_SEC):
                eng.hide_player_overlay()
                self.state = "EXITING"
                self._log(game_sec, "STATE=EXITING (layered exit)")

        elif st == "EXITING":
            eng = self._engine()
            if eng is None:
                self.state = "DONE"
                self._log(game_sec, "STATE=DONE")
                return
            if eng.state() in ("HIDDEN", "READY"):
                self.state = "DONE"
                self._log(game_sec, "STATE=DONE")

        elif st == "RETRY":
            if time.monotonic() >= self._next_retry_wall:
                self.state = "WAITING"

        # DONE / FAILED_FINAL → در این مسابقه دیگر نمایشی نیست (بند ۳۵)

    def _schedule_retry_or_giveup(self, game_sec, allow_reshow=False):
        """۳ ثانیه بعد تلاش مجدد؛ بعد از ۶ بار → رها برای «همین مسابقه» (بند ۳۲)"""
        self.selected = None
        self._prep_error = None
        if self.attempt >= AUTO_HEATMAP_RETRY_MAX:
            self.state = "FAILED_FINAL"
            self._log(game_sec, "STATE=FAILED_FINAL (give up for this match)")
            return
        self.state = "RETRY"
        self._next_retry_wall = time.monotonic() + AUTO_HEATMAP_RETRY_DELAY
        # اگر تریگر قبلاً آتش گرفته بود و در پنجره نمایش هستیم → بعد از READY دوباره Show
        self._reshow_after_ready = bool(allow_reshow and self.triggered
                                        and self._t_triggered_wall is not None
                                        and (time.monotonic() - self._t_triggered_wall)
                                        < AUTO_HEATMAP_DISPLAY_SEC + 90.0)


AUTO_CTRL = AutoPlayerBroadcastController()


def auto_overlay_status_text():
    """متن زنده وضعیت اورلی خودکار برای نوار پایین GUI (v14.0) —
       کاربر بدون دیدن کنسول هم می‌فهمد چرا نمایش داده نمی‌شود"""
    st = getattr(AUTO_CTRL, "state", "?")
    fake = " [FAKE TIME]" if FAKE_CLOCK.enabled else ""
    if _AUTO_ENGINE is None:
        alive = False
        eng = "engine: NOT STARTED"
        if _AUTO_ENGINE_FAIL_REASON:
            eng += f" — {str(_AUTO_ENGINE_FAIL_REASON)[:70]}"
    else:
        try:
            alive = bool(_AUTO_ENGINE.is_alive())
        except Exception:
            alive = False
        if alive:
            eng = "engine: OK"
        else:
            r = ""
            try:
                r = str(_AUTO_ENGINE.fail_reason() or "")
            except Exception:
                pass
            eng = f"engine: DEAD" + (f" — {r[:70]}" if r else "")
    gs = int(getattr(AUTO_CTRL, "_last_game_sec", 0) or 0)
    feed = f"{gs // 60:02d}:{gs % 60:02d}"
    trig = f"{int(AUTO_HEATMAP_MINUTE):02d}:00"
    sel = ""
    try:
        if AUTO_CTRL.selected:
            sel = f" | {AUTO_CTRL.selected.get('name', '?')}"
    except Exception:
        pass
    return f"AUTO overlay: {st}{fake} | {eng} | feed {feed} | trigger {trig}{sel}"


def auto_overlay_status_color(txt):
    """رنگ نوار وضعیت بر اساس محتوا (قرمز=مشکل، سبز=در حال نمایش، کهربایی=آماده‌سازی، آبی=عادی)"""
    t = str(txt)
    if ("NOT STARTED" in t or "engine: DEAD" in t
            or "FAILED" in t or "REASON" in t):
        return "#F7768E"
    if "SHOWING" in t or "VISIBLE" in t:
        return "#9ECE6A"
    if "PREPARING" in t or "READY" in t:
        return "#E0AF68"
    return "#7AA2F7"
# -------------------------------------------------------------
# ۷. پنجره کاربری و رابط گرافیکی (GUI)
# -------------------------------------------------------------
class PESLaLigaApp:
    def __init__(self, root):
        self.root = root
        self.root.title("FL_2026 Heatmap - Synchronized Real-time Player Identification")
        self.root.geometry("1210x890")
        self.root.configure(bg="#12131D")
        self.root.resizable(False, False)

        # [SUITE v1.0.6] TOP BAR REBUILT (user report: several labels were
        # CUT OFF because one single row tried to hold title + clock + four
        # buttons + the filter combobox on a 1210px window — the last-packed
        # widgets were clipped).  Everything now lives on TWO roomy rows:
        #   row 1 -> title + match clock box
        #   row 2 -> action buttons + filter label + player filter combobox
        top_bar = tk.Frame(root, bg="#1A1B28", padx=12, pady=4)
        top_bar.pack(fill=tk.X)

        lbl_title = tk.Label(top_bar, text="هیت‌مپ ۳۰ هرتز لالیگا", font=("Segoe UI", 12, "bold"), fg="#FF9E3B", bg="#1A1B28")
        lbl_title.pack(side=tk.LEFT, padx=4)

        self.time_box = tk.Frame(top_bar, bg="#24283B", padx=8, pady=3, relief=tk.RIDGE, bd=1)
        self.time_box.pack(side=tk.LEFT, padx=10)

        self.lbl_match_time = tk.Label(self.time_box, text="00:00", font=("Consolas", 13, "bold"), fg="#7AA2F7", bg="#24283B")
        self.lbl_match_time.pack(side=tk.LEFT)

        self.lbl_period = tk.Label(self.time_box, text="[نیمه اول]", font=("Segoe UI", 9, "bold"), fg="#9ECE6A", bg="#24283B")
        self.lbl_period.pack(side=tk.LEFT, padx=5)

        self.lbl_hz_badge = tk.Label(self.time_box, text="30 Hz", font=("Consolas", 9, "bold"), fg="#2AC3DE", bg="#24283B")
        self.lbl_hz_badge.pack(side=tk.LEFT, padx=3)

        self.lbl_clock_status = tk.Label(self.time_box, text="[متوقف]", font=("Segoe UI", 9), fg="#F7768E", bg="#24283B")
        self.lbl_clock_status.pack(side=tk.LEFT, padx=3)

        btn_clear = tk.Button(top_bar, text="پاکسازی مپ", font=("Segoe UI", 9, "bold"), bg="#C62828", fg="#FFFFFF",
                              activebackground="#D32F2F", relief=tk.FLAT, padx=8, command=self.clear_all_heatmaps)
        btn_clear.pack(side=tk.RIGHT, padx=4)

        self.filter_combobox = ttk.Combobox(top_bar, state="readonly", width=32, font=("Segoe UI", 9))
        self.filter_combobox.pack(side=tk.RIGHT, padx=6)
        self.filter_combobox.set("در انتظار شروع مسابقه (PLAYING)...")
        self.filter_combobox.bind("<<ComboboxSelected>>", self.on_combobox_select)

        tk.Label(top_bar, text="فیلتر:", font=("Segoe UI", 9, "bold"), fg="#9AA5CE", bg="#1A1B28").pack(side=tk.RIGHT)

        top_bar2 = tk.Frame(root, bg="#1A1B28", padx=12, pady=4)
        top_bar2.pack(fill=tk.X)

        btn_save = tk.Button(top_bar2, text="💾 ذخیره ZIP", font=("Segoe UI", 9, "bold"), bg="#2E7D32", fg="#FFFFFF",
                             activebackground="#388E3C", relief=tk.FLAT, padx=10, pady=2, command=self.save_to_zip)
        btn_save.pack(side=tk.LEFT, padx=4)

        btn_load = tk.Button(top_bar2, text="📂 باز کردن ZIP", font=("Segoe UI", 9, "bold"), bg="#1565C0", fg="#FFFFFF",
                             activebackground="#1976D2", relief=tk.FLAT, padx=10, pady=2, command=self.load_from_zip)
        btn_load.pack(side=tk.LEFT, padx=4)

        btn_3d = tk.Button(top_bar2, text=f"📺 برودکاست زنده ({RENDER_HOTKEY})", font=("Segoe UI", 9, "bold"), bg="#00838F", fg="#FFFFFF",
                           activebackground="#00ACC1", relief=tk.FLAT, padx=10, pady=2, command=self.render_3d_command)
        btn_3d.pack(side=tk.LEFT, padx=4)

        tk.Label(top_bar2, text="پنل با Ctrl+Alt+5 باز و بسته می‌شود", font=("Segoe UI", 8),
                 fg="#5C6785", bg="#1A1B28").pack(side=tk.RIGHT, padx=6)

        self.cw = 1012
        self.ch = 555
        self.canvas = tk.Canvas(root, width=self.cw, height=self.ch, bg="#0D1810", highlightthickness=1, highlightbackground="#2A2F3D")
        self.canvas.pack(pady=4)

        self.base_pitch_img = render_calibrated_pitch(self.cw, self.ch)
        self.current_tk_img = ImageTk.PhotoImage(self.base_pitch_img)
        self.img_container = self.canvas.create_image(0, 0, anchor=tk.NW, image=self.current_tk_img)

        # [SUITE v1.0.6] CALIBRATION AREA REBUILT (user report: the options
        # were hard to read — six sliders squeezed into ONE row with tiny
        # 8px labels).  Now a 3x2 grid with 10px labels, numeric scale
        # values, and a one-click RESTORE DEFAULTS button.
        tuner_frame = tk.LabelFrame(root, text=" ⚙️ تنظیمات کالیبراسیون و فیلترهای هیت‌مپ ", font=("Segoe UI", 10, "bold"), fg="#E0AF68", bg="#161622", padx=10, pady=4)
        tuner_frame.pack(fill=tk.X, padx=35, pady=2)

        def _cal_cell(r, c, caption, from_, to, res, fg, attr, val):
            holder = tk.Frame(tuner_frame, bg="#161622")
            holder.grid(row=r, column=c, padx=6, pady=2, sticky="nsew")
            lbl = tk.Label(holder, text=caption, font=("Segoe UI", 10, "bold"), fg=fg, bg="#161622", anchor="w")
            lbl.pack(anchor=tk.W)
            scale = tk.Scale(holder, from_=from_, to=to, resolution=res, orient=tk.HORIZONTAL,
                             bg="#161622", fg="#7AA2F7", highlightthickness=0,
                             showvalue=0, length=280, command=self.on_param_change)
            scale.set(val)
            scale.pack(fill=tk.X)
            setattr(self, attr, scale)
            return lbl

        self.lbl_gain_val = _cal_cell(0, 0, f"حساسیت: {calib_gain:.2f}", 0.2, 8.0, 0.1, "#C0CAF5", "scale_gain", calib_gain)
        self.lbl_ceil_val = _cal_cell(0, 1, f"سقف گرما: {calib_ceiling:.1f}s", 0.1, 8.0, 0.1, "#C0CAF5", "scale_ceil", calib_ceiling)
        self.lbl_gm_val   = _cal_cell(0, 2, f"گاما: {calib_gamma:.2f}", 0.2, 1.5, 0.05, "#C0CAF5", "scale_gm", calib_gamma)
        self.lbl_b_val    = _cal_cell(1, 0, f"نرمی اولیه: {calib_blur_m:.1f}m", 0.5, 3.0, 0.1, "#C0CAF5", "scale_blur", calib_blur_m)
        self.lbl_ft_val   = _cal_cell(1, 1, f"فیدر لبه‌ها: {calib_feather:.0f}px", 0.0, 25.0, 1.0, "#9ECE6A", "scale_feather", calib_feather)
        self.lbl_cut_val  = _cal_cell(1, 2, f"فیلتر کمینه: {calib_cutoff:.2f}", 0.0, 0.35, 0.01, "#FF7A93", "scale_cutoff", calib_cutoff)
        for cc in range(3):
            tuner_frame.columnconfigure(cc, weight=1)

        btn_cal_reset = tk.Button(tuner_frame, text="↺ بازنشانی پیش‌فرض",
                                  font=("Segoe UI", 9, "bold"), bg="#4A3B1F", fg="#FFD27A",
                                  activebackground="#5C4A26", relief=tk.FLAT, padx=10, pady=2,
                                  command=self.restore_calib_defaults)
        btn_cal_reset.grid(row=2, column=0, columnspan=3, sticky="w", padx=6, pady=(3, 1))

        info_panel = tk.Frame(root, bg="#12131D")
        info_panel.pack(fill=tk.X, padx=35, pady=2)

        self.lbl_current_player = tk.Label(info_panel, text="در حال نمایش: همه بازیکنان (۲۰ بازیکن فعال)", font=("Segoe UI", 9, "bold"), fg="#7DCFFF", bg="#12131D")
        self.lbl_current_player.pack(side=tk.LEFT)

        self.lbl_samples = tk.Label(info_panel, text="سمپل‌های ۳۰ هرتز: 0", font=("Segoe UI", 9), fg="#A9B1D6", bg="#12131D")
        self.lbl_samples.pack(side=tk.RIGHT)

        # نشان لوگوی تیم‌های تشخیص‌داده‌شده (میزبان در برابر مهمان)
        self._home_logo_photo = None
        self._away_logo_photo = None
        self._logo_badge_key = None
        self.logo_away_lbl = tk.Label(info_panel, text="مهمان: --", font=("Segoe UI", 8, "bold"), fg="#F38BA8", bg="#12131D")
        self.logo_away_lbl.pack(side=tk.RIGHT, padx=4)
        tk.Label(info_panel, text="VS", font=("Segoe UI", 8, "bold"), fg="#6C7A9C", bg="#12131D").pack(side=tk.RIGHT)
        self.logo_home_lbl = tk.Label(info_panel, text="میزبان: --", font=("Segoe UI", 8, "bold"), fg="#89B4FA", bg="#12131D")
        self.logo_home_lbl.pack(side=tk.RIGHT, padx=(14, 4))

        self.lbl_status = tk.Label(root, text="وضعیت: در حال راه‌اندازی...", font=("Segoe UI", 9), fg="#9ECE6A", bg="#16161E", bd=1, relief=tk.SUNKEN, anchor=tk.W, padx=12, pady=2)
        self.lbl_status.pack(side=tk.BOTTOM, fill=tk.X)

        # v14.0 — نوار وضعیت اورلی خودکار: وضعیت ماشین حالت + موتور + feed ساعت + تریگر
        # (اگر هیت‌مپ نمایش داده نمی‌شود، علت بدون کنسول همین‌جا دیده می‌شود)
        self._last_auto_text = None
        self.lbl_auto = tk.Label(root, text="AUTO overlay: --", font=("Consolas", 9),
                                 fg="#7AA2F7", bg="#16161E", bd=1, relief=tk.SUNKEN,
                                 anchor=tk.W, padx=12, pady=2)
        self.lbl_auto.pack(side=tk.BOTTOM, fill=tk.X)

        # [SUITE v1.0.0] the X button HIDES the panel — it never kills the
        # tracker; the real teardown stays in on_close()/shutdown_backend().
        self.root.protocol("WM_DELETE_WINDOW", self._hide_window)
        # کلید میانبر رندر سه‌بعدی (R) — با حروف کوچک و بزرگ
        self.root.bind(f"<{RENDER_HOTKEY.lower()}>", self.render_3d_command)
        self.root.bind(f"<{RENDER_HOTKEY.upper()}>", self.render_3d_command)
        self.menu_items_map = {}
        self.previous_valid_selection = "همه بازیکنان (۲۰ بازیکن فعال)"

        # [SUITE v1.0.0] worker + overlay engine boot (once, shared with
        # the headless main path)
        _start_backend_once()

        # [SUITE v1.0.0] the panel starts HIDDEN; Ctrl+Alt+5 shows/hides it
        try:
            self.root.withdraw()
        except Exception:
            pass
        try:
            threading.Thread(target=_hm_hotkey_loop, daemon=True,
                             name="hm-hotkey").start()
        except Exception:
            pass
        self._hm_toggle_tick()
        self._poll_summary()

        self.poll_ui()
        self.render_heatmap_loop()

    def on_param_change(self, val=None):
        global calib_gain, calib_ceiling, calib_gamma, calib_blur_m, calib_feather, calib_cutoff
        calib_gain = float(self.scale_gain.get())
        calib_ceiling = float(self.scale_ceil.get())
        calib_gamma = float(self.scale_gm.get())
        calib_blur_m = float(self.scale_blur.get())
        calib_feather = float(self.scale_feather.get())
        calib_cutoff = float(self.scale_cutoff.get())

        self.lbl_gain_val.config(text=f"حساسیت: {calib_gain:.2f}")
        self.lbl_ceil_val.config(text=f"سقف گرما: {calib_ceiling:.1f}s")
        self.lbl_gm_val.config(text=f"گاما: {calib_gamma:.2f}")
        self.lbl_b_val.config(text=f"نرمی اولیه: {calib_blur_m:.1f}m")
        self.lbl_ft_val.config(text=f"فیدر لبه‌ها: {calib_feather:.0f}px")
        self.lbl_cut_val.config(text=f"فیلتر کمینه: {calib_cutoff:.2f}")

    def restore_calib_defaults(self):
        """[SUITE v1.0.6] one-click restore of the six calibration sliders
        back to the mod's shipped defaults (CALIB_DEFAULTS)."""
        d = CALIB_DEFAULTS
        try:
            self.scale_gain.set(d["gain"])
            self.scale_ceil.set(d["ceiling"])
            self.scale_gm.set(d["gamma"])
            self.scale_blur.set(d["blur_m"])
            self.scale_feather.set(d["feather"])
            self.scale_cutoff.set(d["cutoff"])
        except Exception:
            pass
        # every set() already fires on_param_change; this final call is
        # belt-and-braces so the labels always match the globals
        self.on_param_change()

    def save_to_zip(self):
        default_name = f"FL2026_Heatmap_{time.strftime('%Y%m%d_%H%M%S')}.zip"
        filename = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("فایل فشرده هیت‌مپ", "*.zip")], initialfile=default_name)
        if not filename: return
        try:
            with heatmap_lock: heatmaps_copy = np.copy(entity_heatmaps)
            with entities_lock:
                ent_copy = [{"name": e.get("name", f"Player {i}"), "team": e.get("team", 1), "role": e.get("role", "Field"), "confirmed_name": e.get("confirmed_name")} for i, e in enumerate(entities)] if entities else []

            metadata = {
                "home_team": home_team_name,
                "away_team": away_team_name,
                "match_minute": display_minute,
                "display_second": display_second,
                "period_title": period_title,
                "total_samples": total_samples_taken,
                "gain": calib_gain, "ceiling": calib_ceiling, "gamma": calib_gamma, "blur_m": calib_blur_m, "feather": calib_feather,
                "cutoff": calib_cutoff,
                "entities": ent_copy
            }

            with zipfile.ZipFile(filename, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                buf = io.BytesIO()
                np.save(buf, heatmaps_copy)
                zf.writestr("heatmaps.npy", buf.getvalue())
                zf.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2))

            messagebox.showinfo("ذخیره موفق", f"فایل هیت‌مپ با موفقیت ذخیره شد:\n{os.path.basename(filename)}")
        except Exception as ex:
            messagebox.showerror("خطا در ذخیره", f"خطا در ایجاد فایل ZIP:\n{ex}")

    def load_from_zip(self):
        filename = filedialog.askopenfilename(filetypes=[("فایل فشرده هیت‌مپ", "*.zip")])
        if not filename: return
        try:
            with zipfile.ZipFile(filename, 'r') as zf:
                if "heatmaps.npy" not in zf.namelist():
                    messagebox.showerror("خطا", "فایل نامعتبر است.")
                    return
                npy_bytes = zf.read("heatmaps.npy")
                loaded_heatmaps = np.load(io.BytesIO(npy_bytes))
                meta = {}
                if "metadata.json" in zf.namelist():
                    meta = json.loads(zf.read("metadata.json").decode('utf-8'))

            global entity_heatmaps, total_samples_taken, entities, entities_ready
            with heatmap_lock:
                entity_heatmaps = loaded_heatmaps.astype(np.float32)
                total_samples_taken = meta.get("total_samples", int(np.sum(entity_heatmaps > 0)))

            if meta.get("entities"):
                with entities_lock: entities = meta["entities"]
                self.populate_combobox()

            if "gain" in meta:
                self.scale_gain.set(meta["gain"])
                self.scale_ceil.set(meta["ceiling"])
                self.scale_gm.set(meta["gamma"])
                self.scale_blur.set(meta["blur_m"])
                self.scale_feather.set(meta["feather"])
                if "cutoff" in meta:
                    self.scale_cutoff.set(meta["cutoff"])
                self.on_param_change()

            if "match_minute" in meta and "display_second" in meta:
                self.lbl_match_time.config(text=f"{meta['match_minute']:02d}:{meta['display_second']:02d}")
            if "period_title" in meta:
                self.lbl_period.config(text=f"[{meta['period_title']}]", fg="#7AA2F7")

            self.lbl_samples.config(text=f"سمپل‌های آرشیو: {total_samples_taken:,}")
            self.lbl_status.config(text=f"فایل باز شد: {os.path.basename(filename)}")
            messagebox.showinfo("بارگذاری موفق", "اطلاعات با موفقیت بازخوانی شد.")
        except Exception as ex:
            messagebox.showerror("خطا در بارگذاری", f"خطا: {ex}")

    def populate_combobox(self):
        current_selection = self.filter_combobox.get()
        items = []
        self.menu_items_map.clear()

        items.append("─── نماهای تیمی ───")
        self.menu_items_map["─── نماهای تیمی ───"] = None

        items.append("همه بازیکنان (۲۰ بازیکن فعال)")
        self.menu_items_map["همه بازیکنان (۲۰ بازیکن فعال)"] = (OUTFIELD_INDICES, "TEAM")

        home_label = f"کل تیم میزبان ({home_team_name} - ۱۰ بازیکن)"
        items.append(home_label)
        self.menu_items_map[home_label] = (list(range(1, 11)), "TEAM")

        away_label = f"کل تیم مهمان ({away_team_name} - ۱۰ بازیکن)"
        items.append(away_label)
        self.menu_items_map[away_label] = (list(range(12, 22)), "TEAM")

        items.append(f"─── بازیکنان {home_team_name} (میزبان) ───")
        self.menu_items_map[f"─── بازیکنان {home_team_name} (میزبان) ───"] = None

        with entities_lock:
            for i in range(1, 11):
                if i < len(entities):
                    ent = entities[i]
                    p_name = ent.get("confirmed_name") or ent.get("name")
                    item_text = f"[{home_team_name}] {p_name}"
                    items.append(item_text)
                    self.menu_items_map[item_text] = ([i], "PLAYER")

            items.append(f"─── بازیکنان {away_team_name} (مهمان) ───")
            self.menu_items_map[f"─── بازیکنان {away_team_name} (مهمان) ───"] = None

            for i in range(12, 22):
                if i < len(entities):
                    ent = entities[i]
                    p_name = ent.get("confirmed_name") or ent.get("name")
                    item_text = f"[{away_team_name}] {p_name}"
                    items.append(item_text)
                    self.menu_items_map[item_text] = ([i], "PLAYER")

        self.filter_combobox["values"] = items
        if current_selection in self.menu_items_map and self.menu_items_map[current_selection] is not None:
            self.filter_combobox.set(current_selection)
        else:
            self.filter_combobox.set("همه بازیکنان (۲۰ بازیکن فعال)")

    def on_combobox_select(self, event):
        global active_filter_indices, current_filter_label, current_mode_type
        selected = self.filter_combobox.get()
        target = self.menu_items_map.get(selected)

        if target is None:
            self.filter_combobox.set(self.previous_valid_selection)
            return

        indices, mode = target
        self.previous_valid_selection = selected
        active_filter_indices = indices
        current_filter_label = selected
        current_mode_type = mode
        mode_text = "Player Mode" if mode == "PLAYER" else "Team Mode"
        self.lbl_current_player.config(text=f"در حال نمایش: {selected} ({mode_text})")

    def clear_all_heatmaps(self):
        global entity_heatmaps, total_samples_taken
        with heatmap_lock:
            entity_heatmaps.fill(0)
            total_samples_taken = 0

    def poll_ui(self):
        global entities_ready, match_reset_event
        global active_filter_indices, current_filter_label, current_mode_type

        # بررسی سیگنال شروع بازی جدید و ریست کامل نمایشگرهای UI
        if match_reset_event:
            match_reset_event = False
            active_filter_indices = list(OUTFIELD_INDICES)
            current_filter_label = "همه بازیکنان (۲۰ بازیکن فعال)"
            current_mode_type = "TEAM"
            self.previous_valid_selection = current_filter_label
            self.lbl_current_player.config(text=f"در حال نمایش: {current_filter_label} (Team Mode)")

        self.lbl_status.config(text=f"وضعیت: {status_msg}")
        self.lbl_samples.config(text=f"سمپل‌های ۳۰ هرتز: {total_samples_taken:,}")

        # v14.0 — نوار وضعیت اورلی خودکار (هر ۱۰۰ms فقط هنگام تغییر متن آپدیت)
        try:
            auto_txt = auto_overlay_status_text()
            if auto_txt != self._last_auto_text:
                self._last_auto_text = auto_txt
                self.lbl_auto.config(text=auto_txt, fg=auto_overlay_status_color(auto_txt))
        except Exception:
            pass
        self.lbl_hz_badge.config(text=f"{actual_sampling_rate:.1f} Hz")
        self._refresh_team_badges()

        if period_title == "نیمه اول" and display_minute > 45:
            extra = display_minute - 45
            self.lbl_match_time.config(text=f"45:00 +{extra:02d}:{display_second:02d}")
            self.lbl_period.config(text="[وقت اضافه ن۱]", fg="#E0AF68")
        elif period_title == "نیمه دوم" and display_minute > 90:
            extra = display_minute - 90
            self.lbl_match_time.config(text=f"90:00 +{extra:02d}:{display_second:02d}")
            self.lbl_period.config(text="[وقت اضافه ن۲ - قرینه]", fg="#E0AF68")
        else:
            self.lbl_match_time.config(text=f"{display_minute:02d}:{display_second:02d}")
            if is_inverted_active:
                self.lbl_period.config(text=f"[{period_title} - قرینه]", fg="#7AA2F7")
            else:
                self.lbl_period.config(text=f"[{period_title}]", fg="#9ECE6A")

        if is_clock_active:
            self.lbl_clock_status.config(text="[در جریان]", fg="#9ECE6A")
        else:
            self.lbl_clock_status.config(text="[متوقف]", fg="#F7768E")

        if entities_ready:
            entities_ready = False
            self.populate_combobox()

        if is_running:
            self.root.after(100, self.poll_ui)

    def _load_logo_thumb(self, path, size=30):
        if not path or not os.path.isfile(path):
            return None
        try:
            im = Image.open(path).convert("RGBA")
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
            im.thumbnail((size, size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            return None

    def _refresh_team_badges(self):
        """نمایش لوگوی تیم‌های تشخیص‌داده‌شده در نوار اطلاعات"""
        key = (home_team_name, home_team_logo, away_team_name, away_team_logo)
        if key == self._logo_badge_key:
            return
        self._logo_badge_key = key
        self._home_logo_photo = self._load_logo_thumb(home_team_logo)
        self._away_logo_photo = self._load_logo_thumb(away_team_logo)
        if self._home_logo_photo is not None:
            self.logo_home_lbl.config(image=self._home_logo_photo, text=f" {home_team_name} ", compound="left")
        else:
            self.logo_home_lbl.config(image="", text=f"میزبان: {home_team_name}")
        if self._away_logo_photo is not None:
            self.logo_away_lbl.config(image=self._away_logo_photo, text=f"{away_team_name} ", compound="right")
        else:
            self.logo_away_lbl.config(image="", text=f"مهمان: {away_team_name}")

    def render_heatmap_loop(self):
        if is_running:
            try:
                raw_density = compute_density_snapshot(active_filter_indices)

                composite = self.base_pitch_img.copy()
                heat_img = density_to_heat_rgba(raw_density, self.cw, self.ch, calib_feather, current_mode_type)
                if heat_img is not None:
                    composite = Image.alpha_composite(composite, heat_img)

                self.current_tk_img = ImageTk.PhotoImage(composite)
                self.canvas.itemconfig(self.img_container, image=self.current_tk_img)
            except Exception:
                pass

            self.root.after(40, self.render_heatmap_loop)

    def resolve_render_header(self):
        """تعیین هدر رندر: بازیکن انتخابی یا نمای تیمی —
           [PT v2.3.0] حالت PT: نام/چهره (Asset.zip، 192x192)/شماره پیراهن/سن
           از teams_players_PES2021.txt + Asset.zip؛ در غیر این صورت
           اسم/عکس/لوگو از pes2017_teams.json (نسخه ۱۶٫۰)"""
        with entities_lock:
            ents = list(entities)

        if current_mode_type == "PLAYER" and len(active_filter_indices) == 1:
            idx = active_filter_indices[0]
            ent = ents[idx] if idx < len(ents) else {}
            team = ent.get("team", 1) or 1
            team_key = home_team_key if team == 1 else away_team_key
            roster = team_roster(team_key)
            PTx = pt_active()
            pt_id = None
            if PTx is not None and PTData is not None and \
                    PTData.PTDataSource.is_pt_key(team_key):
                pt_id = int(team_key[1])

            code = ent.get("code")
            if code is None and ent.get("confirmed_name"):
                for c, nm in roster.items():
                    nm_s = nm if isinstance(nm, str) else (nm or {}).get("name")
                    if nm_s == ent.get("confirmed_name"):
                        code = c
                        break

            role = ent.get("role", "Field")
            if pt_id is not None:
                # --- PT: نام/چهره/شماره/سن از دیتابیس PT + Asset.zip ---
                info = PTx.player_by_slot(pt_id, code) if code is not None else None
                if info is None and ent.get("confirmed_name"):
                    for c, nm in roster.items():
                        if nm == ent.get("confirmed_name"):
                            info = PTx.player_by_slot(pt_id, c)
                            if info is not None:
                                code = c
                            break
                if info is not None:
                    name_en = info.get("name") or f"PLAYER {code}"
                elif role == "GK":
                    name_en = "GOALKEEPER"
                elif code is not None:
                    name_en = f"PLAYER {code}"
                else:
                    name_en = f"PLAYER {idx}"
                face_path = None
                if info is not None and info.get("pes_id"):
                    try:
                        face_path = PTx.player_face_path(info["pes_id"])
                    except Exception:
                        face_path = None
                if face_path is None and code is not None:
                    face_path = find_player_photo(team_key, code)
                return {
                    "kind": "player",
                    "name": name_en.upper(),
                    "team_en": team_display_name(team_key),
                    "team_key": team_key,
                    "code": code,
                    "slot": (info or {}).get("slot", code),
                    "pes_id": (info or {}).get("pes_id"),
                    "shirt": (info or {}).get("shirt"),
                    "age": (info or {}).get("age"),
                    "photo_path": face_path,
                    "logo_path": find_team_logo(team_key),
                }

            # --- مسیر قدیمی (بدون PT) ---
            if code is not None:
                name_en = roster.get(code, f"PLAYER {code}")
                name_en = name_en if isinstance(name_en, str) else f"PLAYER {code}"
            elif role == "GK":
                name_en = "GOALKEEPER"
            else:
                name_en = f"PLAYER {idx}"

            return {
                "kind": "player",
                "name": name_en.upper(),
                "team_en": team_display_name(team_key),
                "team_key": team_key,
                "code": code,
                "slot": ent.get("slot"),
                "pes_id": ent.get("pes_id"),
                "shirt": ent.get("shirt"),
                "age": ent.get("age"),
                "photo_path": find_player_photo(team_key, code),
                "logo_path": find_team_logo(team_key),
            }

        if current_mode_type == "TEAM":
            if sorted(active_filter_indices) == list(range(1, 11)):
                k = home_team_key
                return {"kind": "team", "text": team_display_name(k), "team_key": k,
                        "logo_path": find_team_logo(k)}
            if sorted(active_filter_indices) == list(range(12, 22)):
                k = away_team_key
                return {"kind": "team", "text": team_display_name(k), "team_key": k,
                        "logo_path": find_team_logo(k)}

        return {"kind": "all",
                "text": f"{team_display_name(home_team_key)}  VS  {team_display_name(away_team_key)}",
                "logo_home": find_team_logo(home_team_key),
                "logo_away": find_team_logo(away_team_key)}

    def render_3d_command(self, event=None):
        """کلید R: پنجره برودکاست زنده GPU — انیمیشن ورود → حالت Live → خروج انیمیشنی.
           موتور GPU فقط «نمایش» است؛ هیت‌مپ عیناً از توابع همین برنامه می‌آید.
           در نبود کتابخانه‌های GPU، رندر ثابت قبلی جایگزین می‌شود."""
        try:
            self.lbl_status.config(text="وضعیت: در حال اجرای Broadcast Engine (GPU)...")
            self.root.update()

            density = compute_density_snapshot(active_filter_indices)
            header = self.resolve_render_header()

            ev = None
            try:
                if SCRIPT_DIR not in sys.path:
                    sys.path.insert(0, SCRIPT_DIR)
                import BroadcastRenderer
                assets = build_broadcast_gpu_assets(density, header, current_mode_type)
                ev = BroadcastRenderer.launch(assets, interactive=True)
            except ImportError:
                messagebox.showwarning(
                    "Broadcast Engine (GPU)",
                    "کتابخانه‌های GPU پیدا نشدند. برای پنجره برودکاست زنده اجرا کنید:\n\n"
                    "pip install moderngl glfw\n\n"
                    "فعلاً رندر ثابت ساخته می‌شود.")
            except Exception as ex:
                print("[BroadcastRenderer] launch error:", ex, file=sys.stderr)

            if ev is not None:
                t0 = time.time()
                while time.time() - t0 < 4.0:          # انتظار کوتاه برای آماده‌شدن پنجره
                    if ev["ready"].is_set():
                        self.lbl_status.config(
                            text="وضعیت: پنجره Broadcast فعال — R: پخش مجدد | S: ذخیره فریم | ESC: خروج انیمیشنی")
                        return
                    if ev["failed"].is_set():
                        break
                    time.sleep(0.05)

            # ---- fallback: رندر ثابت قبلی (بدون تغییر)
            img = render_broadcast_heatmap(density, header, current_mode_type)

            os.makedirs(RENDER_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            slug_src = header.get("name") or header.get("text") or ""
            slug = re.sub(r"[^A-Za-z0-9]+", "_", slug_src).strip("_")
            fname = f"HEATMAP_3D_{slug}_{ts}.png" if slug else f"HEATMAP_3D_{ts}.png"
            path = os.path.join(RENDER_DIR, fname)
            img.convert("RGB").save(path, "PNG")

            try:
                os.startfile(path)  # نمایش خودکار تصویر در ویندوز
            except Exception:
                pass

            self.lbl_status.config(text=f"وضعیت: رندر ثابت ذخیره شد ← {fname}")
            messagebox.showinfo("رندر سه‌بعدی", f"تصویر هیت‌مپ ذخیره شد:\n{path}")
        except Exception as ex:
            messagebox.showerror("خطا در رندر", f"خطا در ساخت رندر:\n{ex}")

    # =================================================================
    # [SUITE v1.0.0] hidden-panel hotkey (Ctrl+Alt+5) + 91' summary UI
    # =================================================================
    def _hide_window(self):
        """X button — hide only (the pipeline keeps running)."""
        try:
            self.root.withdraw()
        except Exception:
            pass

    def _hm_toggle_tick(self):
        """UI-thread tick: applies queued Ctrl+Alt+5 toggles."""
        if not is_running:
            return
        try:
            if _HM_TOGGLE_REQ.is_set():
                _HM_TOGGLE_REQ.clear()
                try:
                    if self.root.state() == "withdrawn":
                        self.root.deiconify()
                        self.root.attributes("-topmost", True)
                        self.root.lift()
                        self.root.focus_force()
                    else:
                        self.root.withdraw()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            self.root.after(100, self._hm_toggle_tick)
        except Exception:
            pass

    def _poll_summary(self):
        """UI-thread poller for the 91' summary request (thread-safe queue)."""
        if not is_running:
            return
        try:
            if SUMMARY_CTRL.consume():
                self._open_summary_badge()
        except Exception:
            pass
        try:
            self.root.after(150, self._poll_summary)
        except Exception:
            pass

    @staticmethod
    def _hm_photo_icon(path, size, name="", team=None):
        """Circular photo icon as a tk PhotoImage (fallback: initials)."""
        r = max(8, int(size) // 2)
        canvas = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        if path and os.path.isfile(path):
            try:
                im = Image.open(path).convert("RGB")
                w, h = im.size
                s = min(w, h)
                im = im.crop(((w - s) // 2, (h - s) // 2,
                              (w - s) // 2 + s, (h - s) // 2 + s))
                im = im.resize((2 * r, 2 * r), resample=Image.Resampling.LANCZOS)
                mask = Image.new("L", (2 * r, 2 * r), 0)
                ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
                canvas.paste(im, (0, 0), mask)
            except Exception:
                pass
        else:
            fill = (37, 99, 235, 255) if team == 1 else (220, 38, 38, 255)
            d.ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=fill)
            initials = "".join(w[0] for w in str(name).split()[:2]).upper() or "?"
            f_ini = load_font(F_BOLD_PATHS, int(r * 0.9))
            try:
                iw = d.textlength(initials, font=f_ini)
                d.text(((2 * r - iw) / 2, r - r * 0.62), initials,
                       font=f_ini, fill=(244, 248, 252, 255))
            except Exception:
                pass
        d.ellipse([0, 0, 2 * r - 1, 2 * r - 1], outline=RING_COL, width=3)
        return ImageTk.PhotoImage(canvas)

    def _open_summary_badge(self):
        """The small top-right popup option (user spec #5). Clicking it
        opens the full match-summary player list."""
        try:
            sw = self.root.winfo_screenwidth()
        except Exception:
            sw = 1920
        badge = tk.Toplevel(self.root)
        badge.overrideredirect(True)
        try:
            badge.attributes("-topmost", True)
        except Exception:
            pass
        bw, bh = 220, 44
        bx = max(8, sw - bw - 18)
        badge.geometry(f"{bw}x{bh}+{bx}+18")
        badge.configure(bg="#111527")
        lbl = tk.Label(badge, text="📊  MATCH SUMMARY  ▸",
                       font=("Segoe UI", 11, "bold"), fg="#FFD166",
                       bg="#1C2340", cursor="hand2", padx=14, pady=8)
        lbl.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        lbl.bind("<Button-1>", lambda e: (self.open_match_summary(), badge.destroy()))
        badge.bind("<Button-1>", lambda e: (self.open_match_summary(), badge.destroy()))
        try:
            badge.lift()
        except Exception:
            pass
        print("[SUMMARY] badge popup shown top-right", flush=True)

    def open_match_summary(self):
        """Beautiful player list (photos + names) — click a card to view
        that player's heat map."""
        with entities_lock:
            ents = list(entities)
        win = tk.Toplevel(self.root)
        win.title("MATCH SUMMARY — PLAYER HEAT MAPS (91')")
        win.configure(bg="#0E1018")
        win.geometry("1060x680")
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        # header: home VS away (with logos when available)
        head = tk.Frame(win, bg="#141A2E")
        head.pack(fill=tk.X)
        for side, key, nm, lg in (("w", home_team_key, home_team_name, home_team_logo),
                                  ("e", away_team_key, away_team_name, away_team_logo)):
            cell = tk.Frame(head, bg="#141A2E")
            cell.pack(side=side, expand=True, fill=tk.X, padx=16, pady=10)
            try:
                if lg and os.path.isfile(lg):
                    im = Image.open(lg).convert("RGBA").resize((44, 44))
                    ph = ImageTk.PhotoImage(im)
                    tk.Label(cell, image=ph, bg="#141A2E").pack(
                        side=side, padx=6)
                    if side == "w":
                        self._sum_logo_l = ph
                    else:
                        self._sum_logo_r = ph
            except Exception:
                pass
            anchor = "w" if side == "w" else "e"
            tk.Label(cell, text=str(nm or ("HOME" if side == "w" else "AWAY")).upper(),
                     font=("Segoe UI", 13, "bold"), fg="#F8FAFC",
                     bg="#141A2E").pack(side=side, padx=8)
        tk.Label(head, text="VS", font=("Segoe UI", 12, "bold"),
                 fg="#64748B", bg="#141A2E").pack(side=tk.TOP)

        body = tk.Frame(win, bg="#0E1018")
        body.pack(fill=tk.BOTH, expand=True)
        self._fill_summary_columns(body, ents)
        print("[SUMMARY] player list window opened", flush=True)

    def _fill_summary_columns(self, parent, ents):
        """Two scrollable columns: HOME (idx 0..10) and AWAY (idx 11..21)."""
        cols = [("HOME", "#1D4ED8", range(0, 11)),
                ("AWAY", "#B91C1C", range(11, 22))]
        for title, accent, rng in cols:
            col_wrap = tk.Frame(parent, bg="#0E1018")
            col_wrap.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=8, pady=8)
            tk.Label(col_wrap, text=title, font=("Segoe UI", 11, "bold"),
                     fg=accent, bg="#0E1018").pack(anchor="w", pady=(2, 4))
            canvas = tk.Canvas(col_wrap, bg="#0E1018", highlightthickness=0)
            sb = tk.Scrollbar(col_wrap, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg="#0E1018")
            inner.bind("<Configure>",
                       lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            win_id = canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=sb.set)
            canvas.bind("<Configure>",
                        lambda e, c=canvas, w=win_id: c.itemconfig(w, width=e.width - 4))
            canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            sb.pack(side=tk.RIGHT, fill=tk.Y)
            try:
                canvas.bind_all("<MouseWheel>",
                                lambda e, c=canvas: c.yview_scroll(
                                    int(-e.delta / 120), "units"))
            except Exception:
                pass
            for idx in rng:
                ent = ents[idx] if idx < len(ents) else {}
                self._summary_card(inner, idx, ent)

    def _summary_card(self, parent, idx, ent):
        team = ent.get("team", 1) if idx < 11 else 2
        accent = "#2563EB" if team == 1 else "#DC2626"
        roster = home_players_dict if team == 1 else away_players_dict
        team_key = home_team_key if team == 1 else away_team_key
        code = ent.get("code")
        if ent.get("confirmed_name") and code is not None:
            name = str(roster.get(code) or ent.get("confirmed_name") or
                       f"PLAYER {code}")
            photo = find_player_photo(team_key, code)
        elif ent.get("role") == "GK":
            name = "GOALKEEPER"
            photo = None
        else:
            name = f"PLAYER {idx + 1}"
            photo = None
        try:
            with heatmap_lock:
                heat_total = float(np.sum(entity_heatmaps[idx]))
        except Exception:
            heat_total = 0.0
        card = tk.Frame(parent, bg="#151A2C", highlightthickness=1,
                        highlightbackground=accent, cursor="hand2")
        card.pack(fill=tk.X, padx=4, pady=3)
        icon = self._hm_photo_icon(photo, 40, name, team)
        if not hasattr(self, "_sum_icons"):
            self._sum_icons = []
        self._sum_icons.append(icon)          # keep a reference (GC!)
        tk.Label(card, image=icon, bg="#151A2C").pack(side=tk.LEFT, padx=8, pady=6)
        info = tk.Frame(card, bg="#151A2C")
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(info, text=name.upper()[:26], font=("Segoe UI", 10, "bold"),
                 fg="#F1F5F9", bg="#151A2C", anchor="w").pack(anchor="w")
        # [PT v2.3.0] شماره پیراهن/سن از دیتابیس PT (وقتی موجود باشد)
        if ent.get("shirt") is not None:
            sub = f"#{ent['shirt']}"
            if ent.get("age") is not None:
                sub += f"  •  age {ent['age']}"
        elif code is not None:
            sub = f"#{code}"
        else:
            sub = "GK" if ent.get("role") == "GK" else "—"
        tk.Label(info, text=f"{sub}  •  heat samples: {heat_total:,.0f}",
                 font=("Segoe UI", 8), fg="#94A3B8",
                 bg="#151A2C", anchor="w").pack(anchor="w")
        tk.Label(card, text="▸", font=("Segoe UI", 12, "bold"),
                 fg=accent, bg="#151A2C").pack(side=tk.RIGHT, padx=10)
        for w in (card, info):
            w.bind("<Button-1>", lambda e, i=idx: self.open_player_heatmap(i))

    def open_player_heatmap(self, idx):
        """Detail view: the chosen player's heat map, rendered by the mod's
        own pipeline (density → calibration → LALIGA LUT → pitch)."""
        with entities_lock:
            ents = list(entities)
        ent = ents[idx] if idx < len(ents) else {}
        team = 1 if idx < 11 else 2
        team_key = home_team_key if team == 1 else away_team_key
        roster = home_players_dict if team == 1 else away_players_dict
        code = ent.get("code")
        if ent.get("confirmed_name") and code is not None:
            name = str(roster.get(code) or ent.get("confirmed_name"))
            photo = find_player_photo(team_key, code)
        elif ent.get("role") == "GK":
            name, photo = "GOALKEEPER", None
        else:
            name, photo = f"PLAYER {idx + 1}", None

        win = tk.Toplevel(self.root)
        win.title(f"HEAT MAP — {name.upper()}")
        win.configure(bg="#0E1018")
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass
        head = tk.Frame(win, bg="#141A2E")
        head.pack(fill=tk.X)
        icon = self._hm_photo_icon(photo, 48, name, team)
        if not hasattr(self, "_sum_icons"):
            self._sum_icons = []
        self._sum_icons.append(icon)
        tk.Label(head, image=icon, bg="#141A2E").pack(side=tk.LEFT, padx=12, pady=8)
        tk.Label(head, text=name.upper(), font=("Segoe UI", 14, "bold"),
                 fg="#F8FAFC", bg="#141A2E").pack(side=tk.LEFT, padx=6)
        tk.Label(head, text=team_display_name(team_key) or ("HOME" if team == 1 else "AWAY"),
                 font=("Segoe UI", 10), fg="#94A3B8",
                 bg="#141A2E").pack(side=tk.LEFT, padx=6)

        cw, ch = 640, 440
        try:
            density = compute_density_snapshot([idx])
            composite = render_calibrated_pitch(cw, ch)
            heat = density_to_heat_rgba(density, cw, ch, calib_feather,
                                        "PLAYER" if ent.get("role") != "GK" else "TEAM")
            if heat is not None:
                composite = Image.alpha_composite(composite, heat)
        except Exception as ex:
            print(f"[SUMMARY] heat render failed: {ex}", flush=True)
            composite = render_calibrated_pitch(cw, ch)
        self._sum_heat_img = ImageTk.PhotoImage(composite)
        cv = tk.Label(win, image=self._sum_heat_img, bg="#0E1018")
        cv.pack(padx=10, pady=8)

        row = tk.Frame(win, bg="#0E1018")
        row.pack(fill=tk.X, pady=(0, 12))
        def _gpu_broadcast():
            try:
                density = compute_density_snapshot([idx])
                header = {"kind": "player", "name": name.upper(),
                          "team_en": team_display_name(team_key),
                          "team_key": team_key, "code": code,
                          "photo_path": photo, "logo_path": find_team_logo(team_key)}
                assets = build_broadcast_gpu_assets(density, header, "PLAYER")
                if SCRIPT_DIR not in sys.path:
                    sys.path.insert(0, SCRIPT_DIR)
                import BroadcastRenderer
                BroadcastRenderer.launch(assets, interactive=True)
            except Exception as ex:
                messagebox.showwarning("Broadcast Engine (GPU)",
                                       f"GPU broadcast could not start:\n{ex}")
        tk.Button(row, text="▶  SHOW ON GPU BROADCAST", font=("Segoe UI", 10, "bold"),
                  bg="#00838F", fg="#FFFFFF", activebackground="#00ACC1",
                  relief=tk.FLAT, padx=14, pady=6,
                  command=_gpu_broadcast).pack(side=tk.LEFT, padx=12)
        tk.Button(row, text="CLOSE", font=("Segoe UI", 10, "bold"),
                  bg="#334155", fg="#FFFFFF", relief=tk.FLAT, padx=14, pady=6,
                  command=win.destroy).pack(side=tk.RIGHT, padx=12)

    def on_close(self):
        """Real teardown (main() finally / bridge stop)."""
        global is_running
        is_running = False
        try:
            self.lbl_status.config(text="در حال بازیابی کدهای بازی...")
            self.root.update()
        except Exception:
            pass
        shutdown_backend()
        try:
            self.root.destroy()
        except Exception:
            pass

def run_selftest():
    """[SUITE v1.0.0] quick self-check of the suite additions (no game,
    no window, no admin): settings clamp/apply, viewer-side pool filter,
    91' summary state machine, hotkey detector wiring."""
    failures = []

    def check(name, cond):
        print(f"  [{'PASS' if cond else 'FAIL'}] {name}")
        if not cond:
            failures.append(name)

    print("HeatMapMod selftest:")
    # --- settings ---
    global HM_DISPLAY_MINUTE, HM_VIEWER_SIDE, calib_gain
    global _HM_CFG_PATH
    old = (HM_DISPLAY_MINUTE, HM_VIEWER_SIDE, calib_gain)
    old_cfg_path = _HM_CFG_PATH
    try:
        # v1.0.6 — the config FILE (ModsConfig.json) deliberately outranks
        # the env override, so during this check point the reader at a
        # missing path: the test env values are then the only source and
        # the clamp/normalise behaviour is proven even on machines whose
        # ModsConfig.json already carries hm_* keys.
        _HM_CFG_PATH = os.path.join(os.path.dirname(old_cfg_path),
                                    "_selftest_missing_config.json")
        os.environ["MODBRIDGE_SETTINGS"] = json.dumps(
            {"hm_display_minute": 200, "hm_viewer_side": "AWAY", "hm_gain": 99})
        hm_load_settings(silent=True)
        check("display minute clamped to 79", HM_DISPLAY_MINUTE == 79)
        check("viewer side normalised to away", HM_VIEWER_SIDE == "away")
        check("gain clamped to 8.0", abs(calib_gain - 8.0) < 1e-6)
        os.environ["MODBRIDGE_SETTINGS"] = json.dumps({"hm_viewer_side": "home"})
        hm_load_settings(silent=True)
        check("viewer side home", HM_VIEWER_SIDE == "home")
        del os.environ["MODBRIDGE_SETTINGS"]
        hm_load_settings(silent=True)
        check("defaults restored (75/random)", HM_DISPLAY_MINUTE == 75
              and HM_VIEWER_SIDE == "random")
    finally:
        (HM_DISPLAY_MINUTE, HM_VIEWER_SIDE, calib_gain) = old
        _HM_CFG_PATH = old_cfg_path

    # --- summary controller ---
    try:
        SUMMARY_CTRL.reset()
        check("summary idle below 91'", not SUMMARY_CTRL.consume()
              and SUMMARY_CTRL.tick(90 * 60 - 1) is None
              and not SUMMARY_CTRL.consume())
        SUMMARY_CTRL.reset()
        SUMMARY_CTRL.tick(91 * 60)
        check("summary fires at 91:00", SUMMARY_CTRL.consume())
        check("summary fires once per match", not SUMMARY_CTRL.consume())
        SUMMARY_CTRL.reset()
        SUMMARY_CTRL.tick(5000)
        SUMMARY_CTRL.reset()
        SUMMARY_CTRL.tick(5461)
        check("summary re-armed after reset", SUMMARY_CTRL.consume())
    except Exception as ex:
        check(f"summary controller raised {ex}", False)

    # --- hotkey detector wiring ---
    check("hotkey detector importable", callable(_hm_hotkey_down))
    check("toggle event present", isinstance(_HM_TOGGLE_REQ, threading.Event))

    # --- bridge client (offline — must fail safe) ---
    try:
        cli = BridgeHookClient(port=1, token="x")
        check("bridge client fails safe offline", cli.hook_request(
            BALL_HOOK_OFFSET, BALL_ORIG_BYTES, 2) is None)
    except Exception as ex:
        check(f"bridge client raised {ex}", False)

    print(f"SELFTEST: {'ALL PASS' if not failures else str(len(failures)) + ' FAILURES'}")
    return 0 if not failures else 1


def main():
    """[SUITE v1.0.0] dual-mode entry (mirrors Match Momentum v2.1.0):
    GUI build -> the original panel starts HIDDEN (Ctrl+Alt+5 toggles it)
    and the Tk mainloop runs in the main thread; headless build (HM_GUI=0,
    tests, non-Windows) -> tracker + overlay engine only, no window."""
    hm_load_settings()
    _start_backend_once()
    gui_on = (sys.platform == "win32") and (os.environ.get("HM_GUI", "1") != "0")
    if not gui_on:
        print("[HeatMap] headless backend mode (no control panel) — "
              "auto overlay stays active", flush=True)
        try:
            while is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            pass
        finally:
            shutdown_backend()
        return
    try:
        root = tk.Tk()
        app = PESLaLigaApp(root)
        root.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            fatal_error(f"خطای بحرانی در اجرای برنامه:\n{traceback.format_exc()}")
        except SystemExit:
            raise
        except Exception:
            pass
    finally:
        shutdown_backend()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()
