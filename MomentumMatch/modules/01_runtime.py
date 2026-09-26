# -*- coding: utf-8 -*-
# =============================================================================
#  MomentumMod.py — BACKEND of the "Match Momentum" mod (layer 3, no GUI)
#  PES \ eFOOTBALL MODS BY MILAD — targets FL_2026.exe ONLY
#
#  This is the headless build of "Live Match Momentum v10.29 (2026 Edition)".
#  Every engine of the original tool is preserved untouched:
#    Pass & Threat Engine | Shot & Threat Engine | Event Detection Engine |
#    Possession/Time/Goal memory hooks | Momentum engine (game-clock decay) |
#    TV chart renderer | GPU overlay (ModernGL + GLFW) | snapshot engine |
#    match archive | team identity & colors | RED CARD events (v10.27) |
#    smoother curve (GAUSSIAN_SIGMA 20 / TV_SMOOTH_SIGMA_SEC 55) |
#    transactional show lifecycle with auto-retry (v10.28) |
#    overlay duration watchdog (v10.29)
#
#  REMOVED in this build (per the three-layer mod architecture):
#    - the whole Tk control-panel GUI (MomentumApp window, tabs, lists,
#      buttons, snapshot settings dialog) — the mod shows NOTHING on screen
#      except the momentum chart overlay itself at the configured times
#    - settings dialog — settings now come from ModsConfig.json
#      (mods -> "Match Momentum"), written by the frontend (MyMods.py)
#
#  Display behaviour (unchanged core): the chart is captured one minute
#  before each enabled target minute (default 43 / 85 / 116), shown at the
#  target minute for 10 seconds (default) with an ease in/out animation,
#  and again when the match stops for good after 90+/120+ (20 s default).
#  Optional: keep a permanent PNG of the last chart per match
#  (Momentum_Saves) and stamp the chart with the match start date/time.
#
#  NOTE: this mod must be running while the game sits on its start screen,
#  and is activated from the "Select Team" screen (see the frontend page).
#
#  Launched by ModBridge.py as a dedicated Administrator child process.
#  CLI preserved:  --selftest | --render-archive <archive.zip|json>
# =============================================================================

import os
import sys
import time
import math
import json
import socket
import struct
import types
import threading
import traceback
import ctypes
from ctypes import wintypes
from collections import deque

# Physical install directories used by embedded execution inside ModBridge.exe.
# When running from the PyInstaller bundle, __file__ points into _MEIPASS;
# the environment variable keeps runtime data/log/config paths on disk.
_MOMENTUM_DATA_DIR = os.path.abspath(
    os.environ.get("VAR_MODS_BACKEND_DIR")
    or os.path.dirname(os.path.abspath(__file__))
)
_MOMENTUM_INSTALL_DIR = os.path.abspath(
    os.path.join(_MOMENTUM_DATA_DIR, os.pardir)
)
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any

import numpy as np

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Same field bug reported on the Heat Map backend: when stdout/stderr is
# a FILE or PIPE (ModBridge backend_log.txt child stream, redirected
# runs) Python uses the legacy ANSI 'charmap' codec (cp1252), and ONE
# print of a non-Latin-1 string (Persian status text, an Arabic team or
# player name from pes2017_teams.json / game memory) raises
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

# ---------------------------------------------------------------------
# [PT v2.3.0] PT DATA SOURCE — shared with Heat Map (same file‌technical note):
#   PES MODS/PT/Asset.zip + PES MODS/PT/teams_players_PES2021.txt
#   (foldertechnical note PT technical note MyMods.py is — technical note level above from technical note technical note)
# technical note/color team‌technical note from txt technical note logo/technical note (Teams/{id}.png) from Asset.zip
# (istechnical note technical note‌filetechnical note with technical note PT_Cache/). technical noteuntiltechnical note legacy leagues_data.json /
# Football_Database same‌technical noteandtechnical note technical note technical note to‌technical noteandtechnical note fallback technical note‌technical note: PT technical noteandtechnical note ⇒
# technical noteuntiltechnical note beforetechnical note without technical note changetechnical note.
# ---------------------------------------------------------------------
# [PT v2.3.3] technical noteandtechnical note PT «inside technical note file» technical notefromtechnical note technical note is — technical note technical note
# technical noteortechnical note to file outsidetechnical note PTData.py is not. before from technical note versiontechnical note istechnical note technical note
# PTData.py technical note technical note technical note‌technical note technical note technical note PT technical note from technical note technical note‌technical note (without technical note
# team/color/logo). technical noteandtechnical note below technical note PTData.py technical note is — unchanged.
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
    """text textandtext textfromtext‌text PTData in text textandtext textandtext — same API legacy."""
    import types
    _mod = types.ModuleType("PTData_embedded")
    _g = _mod.__dict__
    _g["__name__"] = "PTData_embedded"
    _g["__file__"] = os.path.abspath(__file__)
    _mod.__file__ = _g["__file__"]
    exec(compile(_PTDATA_EMBEDDED_SOURCE, "<PTData embedded>", "exec"), _g)
    return _mod

try:
    _PT_SCRIPT_DIR = os.environ.get(
    "VAR_MODS_BACKEND_DIR",
    _MOMENTUM_DATA_DIR
)
except Exception:
    _PT_SCRIPT_DIR = os.getcwd()
try:
    PTData = _load_embedded_ptdata()
except Exception as _pt_load_ex:
    PTData = None
    print(f"[PT] embedded PT reader failed to load: {_pt_load_ex}")
PT = None
if PTData is not None:
    try:
        PT = PTData.PTDataSource(_PT_SCRIPT_DIR,
                                 logger=lambda m: print(m, flush=True))
        print("[PT] reader ready (embedded) - " + str(PT.status()))
    except Exception as _pt_init_ex:
        PT = None
        print(f"[PT] data source init failed: {_pt_init_ex}")


def pt_active():
    """PT data source active or None — text text‌text PT from text text text‌textandtext"""
    if PT is not None and PT.available():
        return PT
    return None


def _pt_team_label(ident, side) -> str:
    """[PT v2.3.0] text text team for text file/archive —
    text PT (ident = int Team ID) ⇒ text textanduntiltext real team from textuntiltext
    path legacy (league, img) ⇒ L{lg}T{img} text text ⇒ Home/Away.
    (text file only character‌text ASCII text — text‌textfromtext with andtextandtext)"""
    PTx = pt_active()
    if PTx is not None and isinstance(ident, int):
        try:
            nm = PTx.team_short_name(ident) or PTx.team_name(ident)
            if nm:
                safe = "".join(ch for ch in nm
                               if (ch.isalnum() and ord(ch) < 128) or ch in " -_.")
                if safe.strip():
                    return safe.strip()[:40]
        except Exception:
            pass
        return f"TEAM{int(ident)}"
    try:
        if ident and len(ident) >= 2:
            return f"L{int(ident[0])}T{int(ident[1])}"
    except Exception:
        pass
    return "Home" if side == "home" else "Away"


# Chart rendering backend: v2.1.0 — TkAgg when the restored GUI is enabled
# (MOM_GUI, default on Windows) so the TV-tab canvas works; Agg (offscreen)
# for the pure headless build. The MOM_GUI decision happens HERE because
# matplotlib's backend must be selected before the first Figure is made.
def _mom_gui_env_early() -> bool:
    try:
        v = os.environ.get("MOM_GUI")
        if v is None:
            v = "1" if sys.platform == "win32" else "0"
        return str(v).strip().lower() not in ("0", "false", "no", "off")
    except Exception:
        return False


MOM_GUI_REQUESTED = _mom_gui_env_early()
if (MOM_GUI_REQUESTED and sys.platform != "win32"
        and not os.environ.get("DISPLAY")):
    MOM_GUI_REQUESTED = False     # no X display available — stay offscreen

import matplotlib
matplotlib.use("TkAgg" if MOM_GUI_REQUESTED else "Agg")
from matplotlib.figure import Figure
try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception:
    FigureCanvasTkAgg = None      # headless/Agg — never used
from matplotlib.ticker import FuncFormatter, MultipleLocator
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

try:
    from PIL import Image, ImageTk   # v2.1.0 — ImageTk back for the GUI/legacy overlay
except Exception:
    Image = None
    ImageTk = None

# The tkinter MODULE object is still referenced by a few legacy
# except-clauses in preserved pipeline code (e.g. `except tk.TclError`).
# Importing the module is harmless here: this build never creates a
# window (matplotlib runs Agg-only, no widget is ever instantiated).
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except Exception:                  # pragma: no cover — exotic minimal Python
    tk = None
    ttk = None
    messagebox = None

# =====================================================================
# 0-technical note) versiontechnical note 10technical note10 — log technical noteandtechnical note/file technical note technical note (request user)
# ---------------------------------------------------------------------
# technical note printtechnical note detectiontechnical note time technical note to‌technical note print direct from clog() istechnical note
# technical note‌technical note. (Self-test and test‌technical note independent from technical note technical note technical noteandtechnical note logger technical note technical note‌technical notefromtechnical note.)
# v2.0.7 — THIS IS THE BACKEND-ONLY FILE (the standalone GUI build keeps
# its own copy with False): diagnosis of the field report "charts visible
# but empty" requires the lifecycle evidence ([NewHand]/[PossHook]/
# pipeline heartbeat/gate counts) on stdout (captured to backend_log.txt
# by ModBridge) AND in momentum_debug_log.txt.
# =====================================================================
DEBUG_LOG_ENABLED = True


def clog(*args, **kw):
    """log textandtext time text — versiontext 10text10: disabled (text log‌text)."""
    if DEBUG_LOG_ENABLED:
        try:
            print(*args, **kw)
        except Exception:
            pass

# =====================================================================
# 1. technical note automatic technical note technical note technical note (Run as Administrator)
# =====================================================================
def enforce_admin_and_cwd():
    current_dir = _MOMENTUM_DATA_DIR
    try:
        os.chdir(current_dir)
    except Exception:
        pass
    if os.name != "nt":
        # technical noteandtechnical note/technical note (only for --selftest or technical noteandtechnical note) — technical note UAC andtechnical noteandtechnical note technical notefromtechnical note is not
        return
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        is_admin = False

    if not is_admin:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{os.path.abspath(__file__)}"', None, 1
        )
        sys.exit(0)

enforce_admin_and_cwd()

# --- technical note technical note for technical note «--selftest» technical noteandtechnical note technical note technical note andtechnical noteandtechnical note (technical noteandtechnical note/CI) ---
# in andtechnical noteandtechnical note technical note changetechnical note technical note technical note‌technical note only technical note Windows API to‌technical noteandtechnical note technical note
# technical note technical note‌technical noteandtechnical note until technical noteandtechnical note technical noteandtechnical note complete technical note (read memory only andtechnical noteandtechnical note is).
if os.name != "nt":
    class _FakeFunc:
        restype = None
        argtypes = []
        def __call__(self, *a, **k):
            raise OSError("Windows-only API (selftest to text textortext text)")
    class _FakeWinDLL:
        def __getattr__(self, name):
            f = _FakeFunc()
            object.__setattr__(self, name, f)
            return f
    class _FakeWintypes:
        DWORD = ctypes.c_uint32
        WORD = ctypes.c_uint16
        BYTE = ctypes.c_ubyte
        BOOL = ctypes.c_int32
        HANDLE = ctypes.c_void_p
        HMODULE = ctypes.c_void_p
        ULONG = ctypes.c_uint64
        LONG = ctypes.c_int64
        LPVOID = ctypes.c_void_p
        LPCWSTR = ctypes.c_wchar_p
        LPCSTR = ctypes.c_char_p
        SIZE_T = ctypes.c_size_t
        def __getattr__(self, name):
            t = ctypes.c_uint64
            object.__setattr__(self, name, t)
            return t
    ctypes.WinDLL = lambda *a, **k: _FakeWinDLL()   # type: ignore[attr-defined]
    wintypes = _FakeWintypes()                       # type: ignore[assignment]

# =====================================================================
# 2. technical note 64 technical note Windows API  (technical note — version andtechnical note for total technical note)
# =====================================================================
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)

PROCESS_ALL_ACCESS = 0x1F0FFF
TH32CS_SNAPPROCESS = 0x00000002
TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
MEM_COMMIT = 0x1000
MEM_RESERVE = 0x2000
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

def get_pid_by_name(process_name: str) -> Optional[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    entry = PROCESSENTRY32()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32)
    if kernel32.Process32First(snapshot, ctypes.byref(entry)):
        while True:
            if entry.szExeFile.decode('utf-8', errors='ignore').lower() == process_name.lower():
                kernel32.CloseHandle(snapshot)
                return entry.th32ProcessID
            if not kernel32.Process32Next(snapshot, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snapshot)
    return None

def get_module_base(pid: int, module_name: str) -> Optional[int]:
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    entry = MODULEENTRY32()
    entry.dwSize = ctypes.sizeof(MODULEENTRY32)
    if kernel32.Module32First(snapshot, ctypes.byref(entry)):
        while True:
            if entry.szModule.decode('utf-8', errors='ignore').lower() == module_name.lower():
                kernel32.CloseHandle(snapshot)
                return entry.modBaseAddr
            if not kernel32.Module32Next(snapshot, ctypes.byref(entry)):
                break
    kernel32.CloseHandle(snapshot)
    return None

def allocate_near_target(h_process, target_addr: int, size: int = 4096) -> Optional[int]:
    mbi = MEMORY_BASIC_INFORMATION()
    curr = (target_addr - 0x10000) & ~0xFFFF
    min_addr = max(0x10000, target_addr - 0x70000000)
    while curr > min_addr:
        if kernel32.VirtualQueryEx(h_process, ctypes.c_void_p(curr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0: break
        if mbi.State == 0x10000 and mbi.RegionSize >= size:
            alloc = kernel32.VirtualAllocEx(h_process, ctypes.c_void_p(curr), size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if alloc: return alloc
        curr = (mbi.BaseAddress if mbi.BaseAddress else curr) - 0x10000

    curr = (target_addr + 0x10000) & ~0xFFFF
    max_addr = target_addr + 0x70000000
    while curr < max_addr:
        if kernel32.VirtualQueryEx(h_process, ctypes.c_void_p(curr), ctypes.byref(mbi), ctypes.sizeof(mbi)) == 0: break
        if mbi.State == 0x10000 and mbi.RegionSize >= size:
            alloc = kernel32.VirtualAllocEx(h_process, ctypes.c_void_p(curr), size, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE)
            if alloc: return alloc
        curr = (mbi.BaseAddress if mbi.BaseAddress else curr) + (mbi.RegionSize if mbi.RegionSize else 0x10000)
    return None

def safe_read(h_process, addr: int, size: int) -> Optional[bytes]:
    buf = ctypes.create_string_buffer(size)
    read = ctypes.c_size_t()
    if kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(addr), buf, size, ctypes.byref(read)) and read.value == size:
        return buf.raw
    return None

def safe_write(h_process, addr: int, data: bytes) -> bool:
    size = len(data)
    old = wintypes.DWORD()
    if not kernel32.VirtualProtectEx(h_process, ctypes.c_void_p(addr), size, PAGE_EXECUTE_READWRITE, ctypes.byref(old)):
        return False
    buf = ctypes.create_string_buffer(data)
    written = ctypes.c_size_t()
    res = kernel32.WriteProcessMemory(h_process, ctypes.c_void_p(addr), buf, size, ctypes.byref(written))
    kernel32.VirtualProtectEx(h_process, ctypes.c_void_p(addr), size, old, ctypes.byref(old))
    return bool(res and written.value == size)

def closest_player(x: float, z: float, players: List[Dict], team_filter: Optional[str] = None) -> Tuple[Optional[Dict], float]:
    """textdecreasetext nearest player to text text (tool shared Pass/Shot/Event)"""
    best_p = None
    min_d = 999.0
    for p in players:
        if team_filter and p["team"] != team_filter:
            continue
        d = math.hypot(x - p["x"], z - p["z"])
        if d < min_d:
            min_d = d
            best_p = p
    return best_p, min_d

# =====================================================================
# 3. technical note technical note technical note pitch (technical note PitchConfig technical note technical note file)
# =====================================================================
