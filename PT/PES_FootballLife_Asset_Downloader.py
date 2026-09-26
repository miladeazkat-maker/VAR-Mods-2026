# -*- coding: utf-8 -*-
"""
PES MODS • Face & Team Asset Suite
Vertical Portrait Edition · Step-by-Step Wizard · 100% English
Full Integration of the Verified Reference Engine (PyQt5 / PyQt6 Compatible).
"""

from __future__ import annotations

import concurrent.futures
import difflib
import json
import os
import re
import shutil
import ssl
import struct
import sys
import threading
import types
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

APP_PATH = Path(__file__).resolve()
APP_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else APP_PATH.parent
)
CACHE_DIR = APP_DIR / ".asset_downloader_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

# Global SSL context to prevent handshake/cert issues on Windows
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

QT_API = None
QT_AVAILABLE = False
try:
    from PyQt5 import QtCore, QtGui, QtWidgets
    QT_API = "PyQt5"
    QT_AVAILABLE = True
except Exception:
    try:
        from PyQt6 import QtCore, QtGui, QtWidgets
        QT_API = "PyQt6"
        QT_AVAILABLE = True
    except Exception:
        QT_API = None
        QT_AVAILABLE = False


def _load_embedded_module(name: str, source: str) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__file__ = str(APP_PATH)
    module.__name__ = name
    module.__package__ = ""
    exec(compile(source, f"<{name}>", "exec"), module.__dict__)
    return module

# ============================================================================
# VERIFIED REFERENCE EXTRACTION & DOWNLOAD ENGINES
# ============================================================================
PES2017_EXPORTER_SOURCE = """# -*- coding: utf-8 -*-
from __future__ import annotations
import os, struct, sys
from pathlib import Path
from typing import List, Tuple, Dict, Optional

PES17_MASTER_KEY = bytes.fromhex(
    "9B C7 13 28 2D E8 47 75 4D 52 9E 35 90 AA 6A 7A "
    "5C FA 60 9F 6A 32 04 57 B8 9F 59 A5 5F AC 7D 62 "
    "FE 10 2A D6 95 FA DF A0 68 BD 40 95 47 9C BB 40 "
    "F2 94 49 3C C8 E0 94 9D 7B 01 6F F2 C5 3A 2C E5"
)
ENCRYPTION_HEADER_SIZE = 0x140
PES17_FILE_HEADER_SIZE = 0xB0
PES17_PLAYER_COUNT_OFFSET = 0x5C
PES17_TEAM_COUNT_OFFSET = 0x60
PES17_PLAYER_DATA_OFFSET = 0x78
PES17_PLAYER_ENTRY_SIZE = 0xBC
PES17_TEAM_DATA_OFFSET = 0x3C3E58
PES17_TEAM_ENTRY_SIZE = 0x1E0
PES17_ROSTER_DATA_OFFSET = 0x475A90
PES17_ROSTER_ENTRY_SIZE = 0xA4
PES17_ROSTER_SLOTS = 32

class MT19937:
    def __init__(self) -> None:
        self.mt = [0] * 624
        self.mti = 625

    def init_genrand(self, s: int) -> None:
        self.mt[0] = s & 0xFFFFFFFF
        for i in range(1, 624):
            self.mt[i] = (1812433253 * (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        self.mti = 624

    def init_by_array(self, key: List[int]) -> None:
        self.init_genrand(19650218)
        i = 1; j = 0; k = max(624, len(key))
        for _ in range(k):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1664525)) + key[j] + j) & 0xFFFFFFFF
            i += 1; j += 1
            if i >= 624: self.mt[0] = self.mt[623]; i = 1
            if j >= len(key): j = 0
        for _ in range(623):
            self.mt[i] = ((self.mt[i] ^ ((self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1566083941)) - i) & 0xFFFFFFFF
            i += 1
            if i >= 624: self.mt[0] = self.mt[623]; i = 1
        self.mt[0] = 0x80000000; self.mti = 624

    def genrand_int32(self) -> int:
        if self.mti >= 624:
            for kk in range(227):
                y = (self.mt[kk] & 0x80000000) | (self.mt[kk + 1] & 0x7FFFFFFF)
                self.mt[kk] = (self.mt[kk + 397] ^ (y >> 1) ^ (0x9908B0DF if (y & 1) else 0)) & 0xFFFFFFFF
            for kk in range(227, 623):
                y = (self.mt[kk] & 0x80000000) | (self.mt[kk + 1] & 0x7FFFFFFF)
                self.mt[kk] = (self.mt[kk - 227] ^ (y >> 1) ^ (0x9908B0DF if (y & 1) else 0)) & 0xFFFFFFFF
            y = (self.mt[623] & 0x80000000) | (self.mt[0] & 0x7FFFFFFF)
            self.mt[623] = (self.mt[396] ^ (y >> 1) ^ (0x9908B0DF if (y & 1) else 0)) & 0xFFFFFFFF
            self.mti = 0
        y = self.mt[self.mti]; self.mti += 1
        y ^= (y >> 11); y ^= (y << 7) & 0x9D2C5680; y ^= (y << 15) & 0xEFC60000; y ^= (y >> 18)
        return y & 0xFFFFFFFF

def rol32(v, s): return ((v << s) | (v >> (32 - s))) & 0xFFFFFFFF
def ror32(v, s): return ((v >> s) | (v << (32 - s))) & 0xFFFFFFFF
def xor_repeating_blocks(output, inp):
    for i, byte in enumerate(inp): output[i & 63] ^= byte
def xor_with_long_param(data, param):
    return bytes(a ^ b for a, b in zip(data, struct.pack("<Q", param) * 8))
def reverse_longs(data):
    return b"".join(data[i:i + 8][::-1] for i in range(0, 64, 8))

def crypt_stream(output_len, key, inp):
    mt = MT19937(); mt.init_by_array(list(struct.unpack("<16I", key)))
    c0, c1, c2, c3 = mt.genrand_int32(), mt.genrand_int32(), mt.genrand_int32(), mt.genrand_int32()
    out = bytearray(output_len)
    for i in range(output_len // 4):
        c4 = mt.genrand_int32()
        val = struct.unpack_from("<I", inp, i * 4)[0]
        struct.pack_into("<I", out, i * 4, (c4 ^ c3 ^ c2 ^ c1 ^ c0 ^ val) & 0xFFFFFFFF)
        c0 = ror32(c1, 15); c1 = rol32(c2, 11); c2 = rol32(c3, 7); c3 = ror32(c4, 13)
    rem = output_len & 3
    if rem:
        off = output_len & ~3
        val = int.from_bytes(inp[off:off + rem].ljust(4, b"\\x00"), "little") ^ mt.genrand_int32() ^ c3 ^ c2 ^ c1 ^ c0
        out[off:off + rem] = (val & 0xFFFFFFFF).to_bytes(4, "little")[:rem]
    return bytes(out)

def decrypt_pes17_file(blob: bytes) -> Dict[str, bytes]:
    enc = blob[:ENCRYPTION_HEADER_SIZE]
    key = bytearray(enc[0x100:0x140])
    xor_repeating_blocks(key, reverse_longs(PES17_MASTER_KEY))
    dec_hdr = bytearray(crypt_stream(ENCRYPTION_HEADER_SIZE, bytes(key), enc))
    dec_hdr[0x100:0x140] = enc[0x100:0x140]
    rkey = bytearray(dec_hdr[:64])
    xor_repeating_blocks(rkey, bytes(dec_hdr[64:320]))
    fhdr = crypt_stream(PES17_FILE_HEADER_SIZE, xor_with_long_param(bytes(rkey), PES17_FILE_HEADER_SIZE), blob[ENCRYPTION_HEADER_SIZE:ENCRYPTION_HEADER_SIZE + PES17_FILE_HEADER_SIZE])
    dsz, lsz, dcsz, ssz = struct.unpack_from("<4I", fhdr, 64)
    file_type = fhdr[144:176].split(b"\\x00", 1)[0].decode("ascii", errors="replace").strip()
    if not file_type.startswith("EDIT"):
        raise ValueError(f"Not a PES 2017 EDIT file: {file_type!r}")
    cur = ENCRYPTION_HEADER_SIZE + PES17_FILE_HEADER_SIZE
    def read_block(sz, p):
        nonlocal cur
        res = crypt_stream(sz, xor_with_long_param(bytes(rkey), p), blob[cur:cur + sz]); cur += sz; return res
    desc = read_block(dcsz, 0); logo = read_block(lsz, 1); data = read_block(dsz, 2); serial = read_block(ssz * 2, 3)
    return {"description": desc, "logo": logo, "data": data, "serial": serial}

def read_u32_le(buf, offset): return struct.unpack_from("<I", buf, offset)[0]

def read_pes_bitfield(data, current_byte, start_bit, bits_to_read):
    if bits_to_read <= 0: return 0, current_byte
    output = 0; bit = start_bit; bytes_advanced = 0
    for ii in range(bits_to_read):
        if bit == 8: bit = 0; current_byte += 1
        if ii % 8 == 0 and ii > 0: bytes_advanced += 1
        shift = bit - (ii % 8)
        piece = ((data[current_byte] >> shift) & (1 << (ii % 8))) if shift >= 0 else ((data[current_byte] << (-shift)) & (1 << (ii % 8)))
        output += piece << (bytes_advanced * 8)
        bit += 1
    if bit == 8: current_byte += 1
    return output, current_byte

def read_utf8_c_string(data, max_len):
    return data[:max_len].split(b"\\x00", 1)[0].decode("utf-8", errors="replace").strip()

def parse_pes17_players(data, player_count):
    players = {}
    for i in range(player_count):
        st = PES17_PLAYER_DATA_OFFSET + i * PES17_PLAYER_ENTRY_SIZE
        pid = read_u32_le(data, st)
        name = data[st + 0x34:st + 0x34 + 46].split(b"\\x00", 1)[0].decode("utf-8", errors="replace").strip()
        age = data[st + 0x20] & 0x3F
        players[pid] = {"id": pid, "name": name, "age": age, "entry_index": i}
    return players

def parse_pes17_teams(data, team_count):
    teams = []
    current_byte = PES17_TEAM_DATA_OFFSET
    for i in range(team_count):
        start = current_byte
        expected_end = start + PES17_TEAM_ENTRY_SIZE
        team_id, current_byte = read_pes_bitfield(data, current_byte, 0, 32)
        current_byte += 0xE
        c1r, current_byte = read_pes_bitfield(data, current_byte, 0, 6)
        c1g, current_byte = read_pes_bitfield(data, current_byte, 6, 6)
        current_byte += 1
        c2r, current_byte = read_pes_bitfield(data, current_byte, 0, 6)
        c2g, current_byte = read_pes_bitfield(data, current_byte, 6, 6)
        c2b, current_byte = read_pes_bitfield(data, current_byte, 4, 6)
        c1b, current_byte = read_pes_bitfield(data, current_byte, 2, 6)
        current_byte += 0x2
        b_edit_name, current_byte = read_pes_bitfield(data, current_byte, 4, 1)
        current_byte += 1
        b_edit_strip, current_byte = read_pes_bitfield(data, current_byte, 5, 1)
        current_byte += 2
        for _ in range(10): current_byte += 4
        current_byte += 0x54
        name = read_utf8_c_string(data[current_byte:], 0x46)
        current_byte += 0x46
        raw_s = data[current_byte:current_byte + 4]
        short_name = "".join(ch for ch in raw_s[:3].decode("latin-1", errors="replace") if 33 <= ord(ch) <= 95)
        current_byte = expected_end
        def to_rgb8(c): return round(c * 255 / 63)
        teams.append({
            "id": team_id, "name": name, "short_name": short_name, "entry_index": i,
            "colors": [
                {"index": 0, "r": to_rgb8(c1r), "g": to_rgb8(c1g), "b": to_rgb8(c1b)},
                {"index": 1, "r": to_rgb8(c2r), "g": to_rgb8(c2g), "b": to_rgb8(c2b)},
            ]
        })
    return teams

def parse_pes17_rosters(data, team_count, teams, players):
    rosters = {t["id"]: [] for t in teams}
    cur = PES17_ROSTER_DATA_OFFSET
    for _ in range(team_count):
        tid = read_u32_le(data, cur); cur += 4
        pids = [read_u32_le(data, cur + i * 4) for i in range(PES17_ROSTER_SLOTS)]
        cur += PES17_ROSTER_SLOTS * 4
        shirts = list(data[cur:cur + PES17_ROSTER_SLOTS]); cur += PES17_ROSTER_SLOTS
        if tid not in rosters: continue
        res = []
        for slot, pid in enumerate(pids):
            if pid == 0: continue
            pl = players.get(pid, {})
            res.append({
                "code": len(res), "slot": slot, "player_id": pid,
                "name": pl.get("name", f"<PLAYER {pid}>"),
                "shirt_number": shirts[slot] if slot < len(shirts) else 0
            })
        rosters[tid] = res
    return rosters

def extract_pes17(edit_path: Path):
    blob = edit_path.read_bytes()
    decoded = decrypt_pes17_file(blob)
    data = decoded["data"]
    p_count = data[PES17_PLAYER_COUNT_OFFSET] | (data[PES17_PLAYER_COUNT_OFFSET + 1] << 8)
    t_count = data[PES17_TEAM_COUNT_OFFSET] | (data[PES17_TEAM_COUNT_OFFSET + 1] << 8)
    players = parse_pes17_players(data, p_count)
    teams = parse_pes17_teams(data, t_count)
    rosters = parse_pes17_rosters(data, t_count, teams, players)
    return teams, rosters, {}, players, {"player_count": p_count, "team_count": t_count, "description": decoded["description"]}

def write_combined_txt(output_path: Path, teams, rosters, players, meta):
    lines = ["PES 2017 TEAM / PLAYER EXPORT", "=" * 100, f"Teams exported: {len(teams)}", ""]
    for idx, team in enumerate(teams):
        tid = team["id"]
        lines.extend(["=" * 100, f"[TEAM {idx}]", f"Team Record Index: {team['entry_index']}", f"Name: {team['name']}", f"Short Name: {team.get('short_name','')}", f"Team ID: {tid}", ""])
        lines.append(f"PLAYERS ({len(rosters.get(tid, []))})")
        lines.append("-" * 80)
        for p in rosters.get(tid, []):
            age = players.get(p["player_id"], {}).get("age", "")
            lines.append(f"{p['code']:02d} | Slot: {p['slot']:02d} | {p['name']} | PES ID: {p['player_id']} | Age: {age} | Shirt: {p['shirt_number']}")
        lines.append("")
    output_path.write_text("\\n".join(lines), encoding="utf-8-sig")
"""

PES2021_EXPORTER_SOURCE = '# -*- coding: utf-8 -*-\n"""\nPES 2021 / SP Football Life 2026 Team + Player Exporter\n========================================================\n\nThis exporter is designed specifically for SP Football Life 2026 EDIT files\nwhose decrypted EDIT player-count field is zero.\n\nImportant architecture:\n    EDIT00000000\n        -> Team records (names, IDs, colors)\n        -> Team rosters (40 player IDs + 40 shirt numbers)\n\n    Football Life native database (Player.bin)\n        -> Player ID\n        -> Player name\n        -> Player age\n\nThis is necessary for FL26 because the supplied EDIT can legitimately contain\nzero editable Player.bin-style player records while still containing populated\nteam rosters.\n\nOutput format intentionally matches the PES 2017 exporter developed in this\nproject:\n    - all teams\n    - Team Record Index\n    - Name / Short Name / Team ID\n    - Team Color 0 and 1\n    - roster order 0, 1, 2, ...\n    - Slot\n    - Player Name\n    - PES Player ID\n    - Age\n    - Shirt number\n\nIt intentionally does NOT output:\n    - EDIT Name Flag\n    - EDIT Strip Flag\n    - KIT / STRIP REFERENCES\n    - TACTICS\n\nThe script is standalone and uses only Python\'s standard library.\n\nExamples:\n    python pes2021_fl26_team_exporter.py\n    python pes2021_fl26_team_exporter.py "C:\\\\path\\\\EDIT00000000"\n    python pes2021_fl26_team_exporter.py "C:\\\\path\\\\EDIT00000000" --game-root "C:\\\\SP Football Life 2026"\n    python pes2021_fl26_team_exporter.py --self-test\n"""\n\nfrom __future__ import annotations\n\nimport argparse\nimport json\nimport os\nimport struct\nimport sys\nimport tkinter as tk\nimport urllib.parse\nfrom pathlib import Path\nfrom tkinter import filedialog\nfrom typing import Any, Dict, Iterable, List, Optional, Tuple\n\n\n# ---------------------------------------------------------------------------\n# EDIT / PES 2021 encryption layout\n# ---------------------------------------------------------------------------\n\nENCRYPTION_HEADER_SIZE = 0x140\nFILE_HEADER_SIZE = 0xD0\n\n# FL26 EDIT data layout. These are the same PES20/21 locations used by\n# 4ccEditor for the native EDIT format.\nPLAYER_COUNT_OFFSET = 0x60\nTEAM_COUNT_OFFSET = 0x64\nPLAYER_DATA_OFFSET = 0x7C\nTEAM_DATA_OFFSET = 0x8ED2FC\nROSTER_DATA_OFFSET = 0x9D4648\n\nPLAYER_ENTRY_SIZE = 0x138\nTEAM_ENTRY_SIZE = 0x24C\nROSTER_SLOTS = 40\nROSTER_ENTRY_SIZE = 4 + (ROSTER_SLOTS * 4) + (ROSTER_SLOTS * 2) + ROSTER_SLOTS\n\n\n# ---------------------------------------------------------------------------\n# Native Football Life database layout (Player.bin)\n# ---------------------------------------------------------------------------\n\nPLAYER_BIN_RECORD_SIZE = 312\nPLAYER_BIN_PLAYER_ID_OFFSET = 0x08\nPLAYER_BIN_AGE_OFFSET = 0x33\nPLAYER_BIN_POSITION_OFFSET = 0x36\nPLAYER_BIN_NAME_OFFSET = 0x44\nPLAYER_BIN_NAME_SIZE = 61\nPLAYER_BIN_PRINT_NAME_OFFSET = 0x81\n\nPOSITION_NAMES = (\n    "GK", "CB", "LB", "RB", "DMF", "CMF", "LMF", "RMF",\n    "AMF", "LWF", "RWF", "SS", "CF",\n)\n\n\n# ---------------------------------------------------------------------------\n# Football Life database archives\n# ---------------------------------------------------------------------------\n\nDATABASE_MEMBERS = {\n    "Player.bin": "common/etc/pesdb/Player.bin",\n    "Team.bin": "common/etc/pesdb/Team.bin",\n    "PlayerAssignment.bin": "common/etc/pesdb/PlayerAssignment.bin",\n}\n\nPRIORITY_ARCHIVES = (\n    "data_s2526.cpk",\n    "data_extra.cpk",\n)\n\n\n# ---------------------------------------------------------------------------\n# PESX decryption helpers - pure Python port\n# ---------------------------------------------------------------------------\n\n# Master key used by the PES20/21 "new" EDIT encryption family.\n# The key itself is the public PES X decrypter master key used by the\n# 4ccEditor/pesXdecrypter ecosystem.\nPES20_MASTER_KEY = bytes.fromhex(\n    "90 61 D8 66 43 77 24 F8 "\n    "92 BA B8 71 21 C7 60 63 "\n    "F0 91 9A 7D ED 47 80 DE "\n    "51 F5 DD D1 08 FE 32 84 "\n    "F5 09 92 00 B2 3E 88 9F "\n    "EB 24 43 05 58 76 00 22 "\n    "9B FE EC F6 50 00 29 D3 "\n    "42 75 50 B9 EC D2 F6 75"\n)\n\n\nclass MT19937:\n    N = 624\n    M = 397\n    MATRIX_A = 0x9908B0DF\n    UPPER_MASK = 0x80000000\n    LOWER_MASK = 0x7FFFFFFF\n\n    def __init__(self) -> None:\n        self.mt = [0] * self.N\n        self.mti = self.N + 1\n\n    @staticmethod\n    def u32(value: int) -> int:\n        return value & 0xFFFFFFFF\n\n    def init_genrand(self, seed: int) -> None:\n        self.mt[0] = seed & 0xFFFFFFFF\n        for i in range(1, self.N):\n            self.mt[i] = self.u32(\n                1812433253 * (\n                    self.mt[i - 1] ^ (self.mt[i - 1] >> 30)\n                ) + i\n            )\n        self.mti = self.N\n\n    def init_by_array(self, init_key: List[int]) -> None:\n        self.init_genrand(19650218)\n        i = 1\n        j = 0\n        k = max(self.N, len(init_key))\n\n        for _ in range(k):\n            self.mt[i] = self.u32(\n                (self.mt[i] ^ (\n                    (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1664525\n                )) + init_key[j] + j\n            )\n            i += 1\n            j += 1\n            if i >= self.N:\n                self.mt[0] = self.mt[self.N - 1]\n                i = 1\n            if j >= len(init_key):\n                j = 0\n\n        for _ in range(self.N - 1):\n            self.mt[i] = self.u32(\n                (self.mt[i] ^ (\n                    (self.mt[i - 1] ^ (self.mt[i - 1] >> 30)) * 1566083941\n                )) - i\n            )\n            i += 1\n            if i >= self.N:\n                self.mt[0] = self.mt[self.N - 1]\n                i = 1\n\n        self.mt[0] = 0x80000000\n        self.mti = self.N\n\n    def genrand_int32(self) -> int:\n        if self.mti >= self.N:\n            if self.mti == self.N + 1:\n                self.init_genrand(5489)\n\n            for kk in range(self.N - self.M):\n                y = (\n                    (self.mt[kk] & self.UPPER_MASK)\n                    | (self.mt[kk + 1] & self.LOWER_MASK)\n                )\n                self.mt[kk] = self.u32(\n                    self.mt[kk + self.M]\n                    ^ (y >> 1)\n                    ^ (self.MATRIX_A if y & 1 else 0)\n                )\n\n            kk = self.N - self.M\n            while kk < self.N - 1:\n                y = (\n                    (self.mt[kk] & self.UPPER_MASK)\n                    | (self.mt[kk + 1] & self.LOWER_MASK)\n                )\n                self.mt[kk] = self.u32(\n                    self.mt[kk + (self.M - self.N)]\n                    ^ (y >> 1)\n                    ^ (self.MATRIX_A if y & 1 else 0)\n                )\n                kk += 1\n\n            y = (\n                (self.mt[self.N - 1] & self.UPPER_MASK)\n                | (self.mt[0] & self.LOWER_MASK)\n            )\n            self.mt[self.N - 1] = self.u32(\n                self.mt[self.M - 1]\n                ^ (y >> 1)\n                ^ (self.MATRIX_A if y & 1 else 0)\n            )\n            self.mti = 0\n\n        y = self.mt[self.mti]\n        self.mti += 1\n\n        y ^= y >> 11\n        y ^= (y << 7) & 0x9D2C5680\n        y ^= (y << 15) & 0xEFC60000\n        y ^= y >> 18\n        return y & 0xFFFFFFFF\n\n\ndef rol32(value: int, shift: int) -> int:\n    value &= 0xFFFFFFFF\n    return ((value << shift) | (value >> (32 - shift))) & 0xFFFFFFFF\n\n\ndef ror32(value: int, shift: int) -> int:\n    value &= 0xFFFFFFFF\n    return ((value >> shift) | (value << (32 - shift))) & 0xFFFFFFFF\n\n\ndef reverse_longs(data: bytes) -> bytes:\n    if len(data) != 64:\n        raise ValueError("reverse_longs requires 64 bytes")\n    return b"".join(\n        data[i:i + 8][::-1] for i in range(0, 64, 8)\n    )\n\n\ndef xor_repeating_blocks(output: bytearray, data: bytes) -> None:\n    for i, byte in enumerate(data):\n        output[i & 63] ^= byte\n\n\ndef xor_with_long_param(data: bytes, param: int) -> bytes:\n    block = struct.pack("<Q", param) * 8\n    return bytes(a ^ b for a, b in zip(data, block))\n\n\ndef crypt_stream(output_len: int, key: bytes, data: bytes) -> bytes:\n    if len(key) != 64:\n        raise ValueError("crypt_stream key must be 64 bytes")\n\n    mt = MT19937()\n    mt.init_by_array(list(struct.unpack("<16I", key)))\n\n    c0 = mt.genrand_int32()\n    c1 = mt.genrand_int32()\n    c2 = mt.genrand_int32()\n    c3 = mt.genrand_int32()\n\n    out = bytearray(output_len)\n    words = output_len // 4\n\n    for i in range(words):\n        c4 = mt.genrand_int32()\n        inp = struct.unpack_from("<I", data, i * 4)[0]\n        value = c4 ^ c3 ^ c2 ^ c1 ^ c0 ^ inp\n        struct.pack_into("<I", out, i * 4, value & 0xFFFFFFFF)\n        c0 = ror32(c1, 15)\n        c1 = rol32(c2, 11)\n        c2 = rol32(c3, 7)\n        c3 = ror32(c4, 13)\n\n    rem = output_len & 3\n    if rem:\n        offset = output_len & ~3\n        value = int.from_bytes(\n            data[offset:offset + rem].ljust(4, b"\\0"),\n            "little",\n        )\n        value ^= mt.genrand_int32() ^ c3 ^ c2 ^ c1 ^ c0\n        out[offset:offset + rem] = value.to_bytes(4, "little")[:rem]\n\n    return bytes(out)\n\n\ndef decrypt_header(blob: bytes) -> bytes:\n    enc = blob[:ENCRYPTION_HEADER_SIZE]\n    header_key = enc[0x100:0x140]\n    reversed_master = reverse_longs(PES20_MASTER_KEY)\n    key = bytearray(header_key)\n    xor_repeating_blocks(key, reversed_master)\n    header = bytearray(crypt_stream(ENCRYPTION_HEADER_SIZE, bytes(key), enc))\n    header[0x100:0x140] = enc[0x100:0x140]\n    return bytes(header)\n\n\ndef decrypt_edit_file(path: Path) -> Tuple[bytes, str, str, Dict[str, int]]:\n    blob = path.read_bytes()\n    minimum = ENCRYPTION_HEADER_SIZE + FILE_HEADER_SIZE\n    if len(blob) < minimum:\n        raise ValueError("EDIT file is too small")\n\n    header = decrypt_header(blob)\n    rolling_key = bytearray(header[:64])\n    xor_repeating_blocks(rolling_key, header[64:320])\n\n    cursor = ENCRYPTION_HEADER_SIZE\n    header_key = xor_with_long_param(bytes(rolling_key), FILE_HEADER_SIZE)\n    file_header = crypt_stream(\n        FILE_HEADER_SIZE,\n        header_key,\n        blob[cursor:cursor + FILE_HEADER_SIZE],\n    )\n    cursor += FILE_HEADER_SIZE\n\n    data_size, logo_size, desc_size, serial_length = struct.unpack_from(\n        "<4I", file_header, 64\n    )\n    file_type = (\n        file_header[144:176]\n        .split(b"\\0", 1)[0]\n        .decode("ascii", errors="replace")\n        .strip()\n    )\n    game_version = (\n        file_header[176:208]\n        .split(b"\\0", 1)[0]\n        .decode("ascii", errors="replace")\n        .strip()\n    )\n\n    if not file_type.startswith("EDIT"):\n        raise ValueError(\n            f"Decrypted file is not EDIT: {file_type!r}"\n        )\n    if data_size <= 0:\n        raise ValueError(f"Invalid data size: {data_size}")\n\n    sizes = {\n        "data_size": data_size,\n        "logo_size": logo_size,\n        "description_size": desc_size,\n        "serial_length": serial_length,\n    }\n\n    for index, (size, key_param) in enumerate(\n        (\n            (desc_size, 0),\n            (logo_size, 1),\n            (data_size, 2),\n        )\n    ):\n        if cursor + size > len(blob):\n            raise ValueError("EDIT file is truncated")\n        block = crypt_stream(\n            size,\n            xor_with_long_param(bytes(rolling_key), key_param),\n            blob[cursor:cursor + size],\n        )\n        cursor += size\n        if index == 2:\n            edit_data = block\n\n    serial_size = serial_length * 2\n    if cursor + serial_size > len(blob):\n        raise ValueError("EDIT serial block is truncated")\n\n    return edit_data, file_type, game_version, sizes\n\n\n# ---------------------------------------------------------------------------\n# 4ccEditor bit reader\n# ---------------------------------------------------------------------------\n\nPOW2 = (1, 2, 4, 8, 16, 32, 64, 128)\n\n\ndef read_data(buf: bytes, start_bit: int, bits_to_read: int, current_byte: int) -> Tuple[int, int]:\n    bytes_advanced = 0\n    output = 0\n    bit = start_bit\n\n    for ii in range(bits_to_read):\n        if bit == 8:\n            bit = 0\n            current_byte += 1\n        if ii % 8 == 0 and ii > 0:\n            bytes_advanced += 1\n\n        shift = bit - (ii % 8)\n        if shift >= 0:\n            output += (\n                (buf[current_byte] >> shift) & POW2[ii % 8]\n            ) << (bytes_advanced * 8)\n        else:\n            output += (\n                (buf[current_byte] << (-shift)) & POW2[ii % 8]\n            ) << (bytes_advanced * 8)\n\n        bit += 1\n\n    if bit == 8:\n        current_byte += 1\n\n    return output, current_byte\n\n\n# ---------------------------------------------------------------------------\n# Team / roster parsing from the FL26 EDIT\n# ---------------------------------------------------------------------------\n\n\ndef decode_utf8_fixed(data: bytes, size: int) -> str:\n    return data[:size].split(b"\\0", 1)[0].decode(\n        "utf-8", errors="replace"\n    ).strip()\n\n\ndef rgb6_to_255(value: int) -> int:\n    return int(round(value * 255 / 63))\n\n\ndef parse_team_entry(data: bytes, base: int) -> Dict[str, Any]:\n    cb = base\n\n    team_id, cb = read_data(data, 0, 32, cb)\n    manager_id, cb = read_data(data, 0, 32, cb)\n\n    cb += 2  # team emblem\n    stadium_id, cb = read_data(data, 0, 16, cb)\n\n    cb += 0xA\n\n    c1r, cb = read_data(data, 2, 6, cb)\n    c1g, cb = read_data(data, 0, 6, cb)\n    _edit_name, cb = read_data(data, 6, 1, cb)\n    cb += 1\n    c2g, cb = read_data(data, 0, 6, cb)\n    c2b, cb = read_data(data, 6, 6, cb)\n\n    cb += 2\n    _edit_stadium, cb = read_data(data, 6, 1, cb)\n    cb += 1\n    cb += 2\n\n    c1b, cb = read_data(data, 0, 6, cb)\n    c2r, cb = read_data(data, 6, 6, cb)\n\n    cb += 0x39\n    cb += 4  # rival 1\n    cb += 4  # rival 2\n    cb += 4  # rival 3\n    cb += 4  # banner edited flags\n\n    name = decode_utf8_fixed(data[cb:cb + 0x46], 0x46)\n    name_offset = cb\n    cb += 0x46\n\n    short_name = decode_utf8_fixed(data[cb:cb + 4], 4)\n    short_offset = cb\n\n    # Match 4ccEditor cleaning of the short name.\n    short_name = "".join(\n        ch for ch in short_name\n        if 33 <= ord(ch) <= 95\n    )\n\n    return {\n        "id": team_id,\n        "manager_id": manager_id,\n        "stadium_id": stadium_id,\n        "name": name,\n        "short_name": short_name,\n        "color1": (c1r, c1g, c1b),\n        "color2": (c2r, c2g, c2b),\n        "name_offset": name_offset,\n        "short_offset": short_offset,\n    }\n\n\ndef parse_teams(data: bytes, team_count: int) -> List[Dict[str, Any]]:\n    teams: List[Dict[str, Any]] = []\n    for index in range(team_count):\n        base = TEAM_DATA_OFFSET + index * TEAM_ENTRY_SIZE\n        end = base + TEAM_ENTRY_SIZE\n        if end > len(data):\n            raise ValueError(\n                f"Team #{index} exceeds decrypted EDIT data"\n            )\n        info = parse_team_entry(data, base)\n        info["record_index"] = index\n        info["roster"] = []\n        teams.append(info)\n    return teams\n\n\ndef parse_roster_block(data: bytes, base: int) -> Tuple[int, List[int], List[int]]:\n    cb = base\n    team_id, cb = read_data(data, 0, 32, cb)\n\n    player_ids: List[int] = []\n    for _ in range(ROSTER_SLOTS):\n        pid, cb = read_data(data, 0, 32, cb)\n        player_ids.append(pid)\n\n    shirt_numbers: List[int] = []\n    for _ in range(ROSTER_SLOTS):\n        number, cb = read_data(data, 0, 16, cb)\n        shirt_numbers.append(number)\n\n    cb += ROSTER_SLOTS  # unknown A\n    return team_id, player_ids, shirt_numbers\n\n\ndef parse_rosters(\n    data: bytes,\n    team_count: int,\n    teams: List[Dict[str, Any]],\n) -> Tuple[int, int]:\n    by_team_id = {team["id"]: team for team in teams}\n    total_slots = 0\n    unique_player_ids: set[int] = set()\n\n    for index in range(team_count):\n        base = ROSTER_DATA_OFFSET + index * ROSTER_ENTRY_SIZE\n        end = base + ROSTER_ENTRY_SIZE\n        if end > len(data):\n            raise ValueError(\n                f"Roster #{index} exceeds decrypted EDIT data"\n            )\n\n        team_id, player_ids, shirt_numbers = parse_roster_block(data, base)\n        team = by_team_id.get(team_id)\n        if team is None:\n            continue\n\n        roster: List[Dict[str, Any]] = []\n        local_code = 0\n\n        for slot, (pid, shirt) in enumerate(\n            zip(player_ids, shirt_numbers)\n        ):\n            if pid == 0:\n                continue\n            roster.append(\n                {\n                    "code": local_code,\n                    "slot": slot,\n                    "player_id": pid,\n                    "shirt_number": shirt,\n                }\n            )\n            total_slots += 1\n            unique_player_ids.add(pid)\n            local_code += 1\n\n        team["roster"] = roster\n\n    return total_slots, len(unique_player_ids)\n\n\n# ---------------------------------------------------------------------------\n# WESYS decompression\n# ---------------------------------------------------------------------------\n\n\ndef decompress_wesys(raw: bytes, label: str) -> bytes:\n    if len(raw) < 8 or raw[3:8] != b"WESYS":\n        return raw\n\n    if len(raw) < 16:\n        raise ValueError(f"{label} WESYS header truncated")\n\n    compressed_size = struct.unpack_from("<I", raw, 8)[0]\n    expected_size = struct.unpack_from("<I", raw, 12)[0]\n    end = 16 + compressed_size\n\n    if compressed_size <= 0 or end > len(raw):\n        raise ValueError(f"{label} WESYS payload truncated")\n\n    import zlib\n\n    result = zlib.decompress(raw[16:end])\n    if expected_size and len(result) != expected_size:\n        raise ValueError(\n            f"{label} decompressed size mismatch: "\n            f"{len(result)} != {expected_size}"\n        )\n    return result\n\n\n# ---------------------------------------------------------------------------\n# Minimal CRIWARE CPK reader (standard-library only)\n# ---------------------------------------------------------------------------\n\nCPK_DATA_BASE = 0x800\n\n\ndef require_bounds(data: bytes, offset: int, size: int, label: str) -> None:\n    if offset < 0 or size < 0 or offset + size > len(data):\n        raise ValueError(\n            f"{label} out of bounds: 0x{offset:X} + {size}"\n        )\n\n\ndef read_utf_table(data: bytes, offset: int) -> List[Dict[str, Any]]:\n    require_bounds(data, offset, 24, "@UTF header")\n    if data[offset:offset + 4] != b"@UTF":\n        raise ValueError("Expected @UTF")\n\n    table_size = struct.unpack_from(">I", data, offset + 4)[0]\n    table_start = offset + 8\n    require_bounds(data, table_start, table_size, "@UTF table")\n    table = data[table_start:table_start + table_size]\n\n    rows_offset, strings_offset, data_offset = struct.unpack_from(\n        ">III", table, 0\n    )\n    number_columns, row_length = struct.unpack_from(">HH", table, 16)\n    number_rows = struct.unpack_from(">I", table, 20)[0]\n\n    def read_string(string_offset: int) -> str:\n        start = strings_offset + string_offset\n        if not 0 <= start < len(table):\n            raise ValueError("@UTF string out of bounds")\n        end = table.find(b"\\0", start)\n        if end < 0:\n            raise ValueError("unterminated @UTF string")\n        return table[start:end].decode("utf-8", errors="replace")\n\n    def read_value(cursor: int, content_type: int) -> Tuple[Any, int]:\n        formats = {\n            0: (">B", 1),\n            1: (">b", 1),\n            2: (">H", 2),\n            3: (">h", 2),\n            4: (">I", 4),\n            5: (">i", 4),\n            6: (">Q", 8),\n            7: (">q", 8),\n            8: (">f", 4),\n            9: (">d", 8),\n        }\n        if content_type == 10:\n            require_bounds(table, cursor, 4, "@UTF string value")\n            string_offset = struct.unpack_from(">I", table, cursor)[0]\n            return read_string(string_offset), cursor + 4\n        if content_type == 11:\n            require_bounds(table, cursor, 8, "@UTF data value")\n            data_off, data_size = struct.unpack_from(">II", table, cursor)\n            start = data_offset + data_off\n            require_bounds(table, start, data_size, "@UTF data payload")\n            return bytes(table[start:start + data_size]), cursor + 8\n        fmt, size = formats[content_type]\n        require_bounds(table, cursor, size, "@UTF scalar value")\n        return struct.unpack_from(fmt, table, cursor)[0], cursor + size\n\n    columns: List[Tuple[str, int, int, Any]] = []\n    column_offset = 24\n\n    for _ in range(number_columns):\n        flags = table[column_offset]\n        column_offset += 1\n        name_offset = struct.unpack_from(">I", table, column_offset)[0]\n        column_offset += 4\n        storage = flags & 0xF0\n        content_type = flags & 0x0F\n        constant = None\n        if storage == 0x30:\n            constant, column_offset = read_value(\n                column_offset,\n                content_type,\n            )\n        elif storage not in (0x00, 0x10, 0x50):\n            raise ValueError(\n                f"Unsupported @UTF storage type 0x{storage:02X}"\n            )\n        columns.append(\n            (\n                read_string(name_offset),\n                content_type,\n                storage,\n                constant,\n            )\n        )\n\n    rows: List[Dict[str, Any]] = []\n    for row_number in range(number_rows):\n        cursor = rows_offset + row_number * row_length\n        require_bounds(table, cursor, row_length, "@UTF row")\n        row: Dict[str, Any] = {}\n\n        for name, content_type, storage, constant in columns:\n            if storage == 0x00:\n                row[name] = None\n            elif storage == 0x10:\n                row[name] = 0\n            elif storage == 0x30:\n                row[name] = constant\n            else:\n                value, cursor = read_value(cursor, content_type)\n                row[name] = value\n\n        rows.append(row)\n\n    return rows\n\n\ndef parse_cpk_rows(cpk_data: bytes) -> Tuple[int, List[Dict[str, Any]]]:\n    if len(cpk_data) < 32:\n        raise ValueError("CPK too small")\n\n    header_rows = read_utf_table(cpk_data, 16)\n    if len(header_rows) != 1:\n        raise ValueError("CPK header row count is not 1")\n\n    header = header_rows[0]\n    toc_offset = int(header.get("TocOffset", -1))\n    if toc_offset == 0xFFFFFFFFFFFFFFFF or toc_offset < 0:\n        toc_offset = cpk_data.find(b"TOC ")\n\n    if toc_offset < 0:\n        raise ValueError("CPK TOC not found")\n\n    try:\n        rows = read_utf_table(cpk_data, toc_offset + 16)\n        return toc_offset, rows\n    except ValueError:\n        # Football Life\'s mode-5 TOC uses a stable 8-column 32-byte row shape.\n        utf_offset = toc_offset + 16\n        require_bounds(cpk_data, utf_offset, 32, "CPK mode-5 TOC")\n        if cpk_data[utf_offset:utf_offset + 4] != b"@UTF":\n            raise\n\n        table_size = struct.unpack_from(">I", cpk_data, utf_offset + 4)[0]\n        table_start = utf_offset + 8\n        require_bounds(cpk_data, table_start, table_size, "CPK mode-5 table")\n        table = cpk_data[table_start:table_start + table_size]\n        rows_offset, strings_offset, data_offset = struct.unpack_from(">III", table, 0)\n        number_columns, row_length = struct.unpack_from(">HH", table, 16)\n        number_rows = struct.unpack_from(">I", table, 20)[0]\n        if (number_columns, row_length) != (8, 32):\n            raise ValueError("Unsupported CPK mode-5 TOC shape")\n\n        def s(off: int) -> str:\n            pos = strings_offset + off\n            end = table.find(b"\\0", pos)\n            if pos < 0 or end < 0:\n                raise ValueError("CPK TOC string out of bounds")\n            return table[pos:end].decode("utf-8", errors="replace")\n\n        rows = []\n        for i in range(number_rows):\n            row_off = rows_offset + i * row_length\n            directory_off, filename_off, file_size, extract_size = struct.unpack_from(\n                ">IIII", table, row_off\n            )\n            file_offset = struct.unpack_from(">Q", table, row_off + 16)[0]\n            file_id = struct.unpack_from(">I", table, row_off + 24)[0]\n            crc = struct.unpack_from(">I", table, row_off + 28)[0]\n            rows.append(\n                {\n                    "DirName": s(directory_off),\n                    "FileName": s(filename_off),\n                    "FileSize": file_size,\n                    "ExtractSize": extract_size,\n                    "FileOffset": file_offset,\n                    "ID": file_id,\n                    "CRC": crc,\n                }\n            )\n\n        return toc_offset, rows\n\n\ndef full_cpk_name(row: Dict[str, Any]) -> str:\n    directory = str(row.get("DirName") or "").strip("/")\n    filename = str(row.get("FileName") or "").strip("/")\n    if directory and filename:\n        return f"{directory}/{filename}"\n    return filename or directory\n\n\ndef extract_cpk_member(cpk_path: Path, member: str) -> bytes:\n    raw = cpk_path.read_bytes()\n    toc_offset, rows = parse_cpk_rows(raw)\n\n    requested = member.replace("\\\\", "/").strip("/")\n    matches = [\n        row for row in rows\n        if full_cpk_name(row) == requested\n    ]\n    if not matches:\n        matches = [\n            row for row in rows\n            if str(row.get("FileName") or "").strip("/") == requested\n            or full_cpk_name(row).endswith("/" + requested)\n        ]\n    if not matches:\n        raise FileNotFoundError(\n            f"{member} not found in {cpk_path.name}"\n        )\n    if len(matches) > 1:\n        raise ValueError(\n            f"Ambiguous {member} in {cpk_path.name}"\n        )\n\n    row = matches[0]\n    file_offset = int(row["FileOffset"])\n    file_size = int(row.get("FileSize", row.get("ExtractSize", 0)))\n    candidates = (\n        file_offset + int(CPK_DATA_BASE),\n        file_offset + toc_offset,\n        file_offset,\n    )\n\n    for start in dict.fromkeys(candidates):\n        if 0 <= start <= len(raw) and start + file_size <= len(raw):\n            return raw[start:start + file_size]\n\n    raise ValueError(\n        f"Payload for {member} is out of CPK bounds"\n    )\n\n\ndef database_cpk_candidates(game_root: Path) -> List[Path]:\n    download = game_root / "download"\n    if game_root.name.lower() == "download":\n        download = game_root\n    if not download.is_dir():\n        return []\n\n    result: List[Path] = []\n    seen: set[str] = set()\n\n    def add(p: Path) -> None:\n        key = str(p).casefold()\n        if key in seen:\n            return\n        if p.is_file():\n            seen.add(key)\n            result.append(p)\n\n    for name in PRIORITY_ARCHIVES:\n        add(download / name)\n\n    patterns = ("*liveupd*.cpk", "*datapack*.cpk", "*.cpk")\n    for pattern in patterns:\n        try:\n            files = sorted(\n                download.glob(pattern),\n                key=lambda x: (str(x).casefold(), str(x)),\n            )\n        except OSError:\n            files = []\n        for p in files:\n            add(p)\n\n    return result\n\n\ndef discover_game_root(explicit: Optional[Path]) -> Optional[Path]:\n    if explicit:\n        return explicit.expanduser().resolve()\n\n    env_names = (\n        "FL_GAME_ROOT",\n        "FOOTBALL_LIFE_ROOT",\n        "PES_GAME_ROOT",\n    )\n    for name in env_names:\n        value = os.environ.get(name)\n        if value:\n            candidate = Path(value).expanduser()\n            if (candidate / "download").is_dir():\n                return candidate.resolve()\n\n    roots = []\n    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):\n        base = os.environ.get(env)\n        if not base:\n            continue\n        base_path = Path(base)\n        roots.extend(\n            [\n                base_path / "SP Football Life 2026",\n                base_path / "Football Life 2026",\n                base_path / "PES 2021",\n            ]\n        )\n\n    for candidate in roots:\n        if (candidate / "download").is_dir():\n            return candidate.resolve()\n\n    return None\n\n\ndef load_database_member(\n    game_root: Path,\n    member_name: str,\n) -> Tuple[bytes, Path]:\n    member_path = DATABASE_MEMBERS[member_name]\n\n    candidates = database_cpk_candidates(game_root)\n    errors: List[str] = []\n\n    for cpk in candidates:\n        try:\n            raw = extract_cpk_member(cpk, member_path)\n            return decompress_wesys(raw, member_name), cpk\n        except FileNotFoundError:\n            continue\n        except Exception as exc:\n            errors.append(f"{cpk.name}: {exc}")\n            continue\n\n    raise FileNotFoundError(\n        f"{member_name} was not found in the Football Life database CPKs.\\n"\n        + ("\\n".join(errors) if errors else "No database CPKs were found.")\n    )\n\n\n# ---------------------------------------------------------------------------\n# Player.bin parser\n# ---------------------------------------------------------------------------\n\n\ndef read_text(data: bytes, offset: int, size: int) -> str:\n    return data[offset:offset + size].split(b"\\0", 1)[0].decode(\n        "utf-8", errors="replace"\n    ).strip()\n\n\ndef parse_player_bin(raw: bytes) -> Dict[int, Dict[str, Any]]:\n    data = decompress_wesys(raw, "Player.bin")\n\n    if len(data) % PLAYER_BIN_RECORD_SIZE:\n        raise ValueError(\n            "Player.bin data size is not divisible by 312: "\n            f"{len(data)}"\n        )\n\n    players: Dict[int, Dict[str, Any]] = {}\n\n    for offset in range(\n        0,\n        len(data),\n        PLAYER_BIN_RECORD_SIZE,\n    ):\n        pid = struct.unpack_from(\n            "<I",\n            data,\n            offset + PLAYER_BIN_PLAYER_ID_OFFSET,\n        )[0]\n        if pid == 0:\n            continue\n\n        name = read_text(\n            data,\n            offset + PLAYER_BIN_NAME_OFFSET,\n            PLAYER_BIN_NAME_SIZE,\n        )\n        if not name:\n            continue\n\n        age = (\n            data[offset + PLAYER_BIN_AGE_OFFSET] & 0x3F\n        ) + 15\n\n        position_index = (\n            data[offset + PLAYER_BIN_POSITION_OFFSET] >> 2\n        ) & 0x0F\n        position = (\n            POSITION_NAMES[position_index]\n            if position_index < len(POSITION_NAMES)\n            else f"UNKNOWN({position_index})"\n        )\n\n        print_name = read_text(\n            data,\n            offset + PLAYER_BIN_PRINT_NAME_OFFSET,\n            PLAYER_BIN_NAME_SIZE,\n        )\n\n        players[pid] = {\n            "id": pid,\n            "name": name,\n            "age": age,\n            "position": position,\n            "print_name": print_name,\n        }\n\n    return players\n\n\n# ---------------------------------------------------------------------------\n# Output\n# ---------------------------------------------------------------------------\n\n\ndef write_output(\n    output_path: Path,\n    teams: List[Dict[str, Any]],\n    edit_player_count: int,\n    edit_team_count: int,\n    roster_entry_count: int,\n    unique_roster_players: int,\n    player_source: str,\n    game_version: str,\n) -> None:\n    lines: List[str] = []\n    lines.append("PES 2021 / FOOTBALL LIFE 2026 TEAM / PLAYER EXPORT")\n    lines.append("=" * 100)\n    lines.append(f"EDIT Game Version: {game_version}")\n    lines.append(f"Player records in EDIT: {edit_player_count}")\n    lines.append(f"Team records in EDIT:   {edit_team_count}")\n    lines.append(f"Teams exported:         {len(teams)}")\n    lines.append(f"Players appearing in rosters: {roster_entry_count}")\n    lines.append(f"Unique Players in rosters:    {unique_roster_players}")\n    lines.append(f"Player Name/Age Source: {player_source}")\n    lines.append("")\n\n    for team in teams:\n        lines.append("=" * 100)\n        lines.append(f"[TEAM {team[\'record_index\']}]")\n        lines.append(f"Team Record Index: {team[\'record_index\']}")\n        lines.append(f"Name: {team[\'name\']}")\n        lines.append(f"Short Name: {team[\'short_name\']}")\n        lines.append(f"Team ID: {team[\'id\']}")\n        lines.append("")\n\n        lines.append("TEAM COLORS")\n        lines.append("-" * 60)\n        for idx, color in enumerate((team["color1"], team["color2"])):\n            r6, g6, b6 = color\n            r = rgb6_to_255(r6)\n            g = rgb6_to_255(g6)\n            b = rgb6_to_255(b6)\n            lines.append(\n                f"{idx} | RGB6=({r6},{g6},{b6}) | "\n                f"RGB=({r},{g},{b}) | HEX=#{r:02X}{g:02X}{b:02X}"\n            )\n\n        roster = team.get("roster", [])\n        lines.append("")\n        lines.append(f"PLAYERS ({len(roster)})")\n        lines.append("-" * 90)\n\n        for player in roster:\n            if "name" in player:\n                name = player["name"]\n                age = player["age"]\n                pid = player["player_id"]\n            else:\n                name = f"<UNKNOWN PLAYER {player[\'player_id\']}>"\n                age = "?"\n                pid = player["player_id"]\n\n            lines.append(\n                f"{player[\'code\']:02d} | Slot: {player[\'slot\']:02d} | "\n                f"{name} | PES ID: {pid} | Age: {age} | "\n                f"Shirt: {player[\'shirt_number\']}"\n            )\n\n        lines.append("")\n\n    output_path.write_text(\n        "\\n".join(lines),\n        encoding="utf-8-sig",\n    )\n\n\n# ---------------------------------------------------------------------------\n# Input helpers\n# ---------------------------------------------------------------------------\n\n\ndef choose_edit_file() -> Optional[Path]:\n    try:\n        root = tk.Tk()\n        root.withdraw()\n        root.update()\n        filename = filedialog.askopenfilename(\n            title="Select Football Life 2026 EDIT00000000",\n            filetypes=[\n                ("EDIT00000000", "EDIT00000000"),\n                ("All files", "*.*"),\n            ],\n        )\n        root.destroy()\n        if not filename:\n            return None\n        return Path(filename)\n    except Exception:\n        return None\n\n\ndef choose_game_root() -> Optional[Path]:\n    try:\n        root = tk.Tk()\n        root.withdraw()\n        root.update()\n        directory = filedialog.askdirectory(\n            title="Select SP Football Life 2026 game folder"\n        )\n        root.destroy()\n        if not directory:\n            return None\n        return Path(directory)\n    except Exception:\n        return None\n\n\n# ---------------------------------------------------------------------------\n# Self-tests\n# ---------------------------------------------------------------------------\n\n\ndef self_test() -> int:\n    """Synthetic layout tests plus the bundled FL26 EDIT when available."""\n    print("PES 2021 / FL26 exporter self-test")\n    print("=" * 70)\n\n    # Bit reader sanity.\n    sample = struct.pack("<I", 0x12345678)\n    value, end = read_data(sample, 0, 32, 0)\n    assert value == 0x12345678\n    assert end == 4\n    print("Bit reader: PASS")\n\n    # Player.bin synthetic record.\n    fake = bytearray(PLAYER_BIN_RECORD_SIZE)\n    struct.pack_into("<I", fake, PLAYER_BIN_PLAYER_ID_OFFSET, 114022)\n    fake[PLAYER_BIN_NAME_OFFSET:PLAYER_BIN_NAME_OFFSET + 9] = b"Test One\\0"\n    fake[PLAYER_BIN_AGE_OFFSET] = 25 - 15\n    players = parse_player_bin(bytes(fake))\n    assert players[114022]["name"] == "Test One"\n    assert players[114022]["age"] == 25\n    print("Player.bin parser: PASS")\n\n    # Test the user\'s uploaded EDIT if it is present in the local workspace.\n    candidates = [\n        Path("/mnt/data/EDIT00000000"),\n        Path(__file__).resolve().parent / "EDIT00000000",\n    ]\n    edit_path = next((p for p in candidates if p.is_file()), None)\n    if edit_path:\n        data, file_type, game_version, sizes = decrypt_edit_file(edit_path)\n        players_count = int.from_bytes(\n            data[PLAYER_COUNT_OFFSET:PLAYER_COUNT_OFFSET + 2],\n            "little",\n        )\n        teams_count = int.from_bytes(\n            data[TEAM_COUNT_OFFSET:TEAM_COUNT_OFFSET + 2],\n            "little",\n        )\n        teams = parse_teams(data, teams_count)\n        roster_entries, unique_players = parse_rosters(\n            data,\n            teams_count,\n            teams,\n        )\n\n        assert file_type == "EDIT"\n        assert game_version == "SP Football Life 2026"\n        assert players_count == 0\n        assert teams_count == 749\n        assert roster_entries == 21353\n        assert unique_players == 19389\n        assert teams[0]["id"] == 1\n        assert teams[0]["name"] == "Ireland"\n        assert teams[0]["short_name"] == "IRL"\n        assert teams[0]["roster"][0]["player_id"] == 114022\n\n        print("Uploaded FL26 EDIT decrypt: PASS")\n        print("  Game version: SP Football Life 2026")\n        print("  Player records in EDIT: 0")\n        print("  Team records in EDIT:   749")\n        print("  Roster player entries:  21353")\n        print("  Unique roster players: 19389")\n        print("  First team:             Ireland (Team ID 1)")\n        print("  First roster player ID: 114022")\n    else:\n        print("Uploaded FL26 EDIT: not present in local test workspace")\n\n    print("ALL SELF-TESTS: PASS")\n    return 0\n\n\n# ---------------------------------------------------------------------------\n# Main\n# ---------------------------------------------------------------------------\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(\n        description="Extract FL26 teams and roster players with native Player.bin names/ages."\n    )\n    parser.add_argument(\n        "input",\n        nargs="?",\n        help="Path to EDIT00000000",\n    )\n    parser.add_argument(\n        "output",\n        nargs="?",\n        help="Output TXT path",\n    )\n    parser.add_argument(\n        "--game-root",\n        type=Path,\n        help="SP Football Life 2026 game root containing download/*.cpk",\n    )\n    parser.add_argument(\n        "--player-bin",\n        type=Path,\n        help="Optional extracted Player.bin (overrides CPK search)",\n    )\n    parser.add_argument(\n        "--self-test",\n        action="store_true",\n        help="Run self-tests",\n    )\n    parser.add_argument(\n        "--no-gui",\n        action="store_true",\n        help="Do not open file/folder selection dialogs",\n    )\n\n    args = parser.parse_args()\n\n    if args.self_test:\n        return self_test()\n\n    if args.input:\n        edit_path = Path(args.input).expanduser().resolve()\n    else:\n        candidates = [\n            Path(__file__).resolve().parent / "EDIT00000000",\n            Path.cwd() / "EDIT00000000",\n        ]\n        edit_path = next(\n            (p.resolve() for p in candidates if p.is_file()),\n            None,\n        )\n        if edit_path is None and not args.no_gui:\n            edit_path = choose_edit_file()\n        if edit_path is None:\n            print("ERROR: EDIT00000000 was not selected.")\n            return 1\n\n    if not edit_path.is_file():\n        print(f"ERROR: EDIT not found:\\n{edit_path}")\n        return 1\n\n    output_path = (\n        Path(args.output).expanduser().resolve()\n        if args.output\n        else edit_path.with_name("teams_players_PES2021.txt")\n    )\n\n    print("=" * 70)\n    print("PES 2021 / SP Football Life 2026 Team / Player Exporter")\n    print("=" * 70)\n    print(f"Input : {edit_path}")\n    print(f"Output: {output_path}")\n    print("")\n\n    try:\n        edit_data, file_type, game_version, sizes = decrypt_edit_file(edit_path)\n\n        print(f"Game version: {game_version}")\n        print(f"EDIT data size: {len(edit_data):,} bytes")\n\n        if not game_version.lower().startswith("sp football life"):\n            print("WARNING: game version is not identified as SP Football Life.")\n\n        edit_player_count = int.from_bytes(\n            edit_data[PLAYER_COUNT_OFFSET:PLAYER_COUNT_OFFSET + 2],\n            "little",\n        )\n        team_count = int.from_bytes(\n            edit_data[TEAM_COUNT_OFFSET:TEAM_COUNT_OFFSET + 2],\n            "little",\n        )\n\n        print(f"Player records in EDIT: {edit_player_count}")\n        print(f"Team records in EDIT:   {team_count}")\n\n        if team_count <= 0:\n            raise ValueError(\n                "Team count is zero; the EDIT could not be parsed as PES20/21."\n            )\n\n        teams = parse_teams(edit_data, team_count)\n        roster_entries, unique_players = parse_rosters(\n            edit_data,\n            team_count,\n            teams,\n        )\n\n        print(f"Roster entries:         {roster_entries}")\n        print(f"Unique roster players:  {unique_players}")\n\n        # -------------------------------------------------------------------\n        # Load native FL26 Player.bin.\n        # -------------------------------------------------------------------\n        if args.player_bin:\n            player_bin_path = args.player_bin.expanduser().resolve()\n            if not player_bin_path.is_file():\n                raise FileNotFoundError(\n                    f"Player.bin not found: {player_bin_path}"\n                )\n            player_bin_data = player_bin_path.read_bytes()\n            player_source = str(player_bin_path)\n        else:\n            game_root = discover_game_root(args.game_root)\n            if game_root is None and not args.no_gui:\n                print("Player records are not stored in this FL26 EDIT.")\n                print("Select the SP Football Life 2026 game folder so the script can read Player.bin.")\n                game_root = choose_game_root()\n\n            if game_root is None:\n                raise FileNotFoundError(\n                    "Could not locate SP Football Life 2026 game root. "\n                    "Use --game-root or --player-bin."\n                )\n\n            player_bin_data, player_cpk = load_database_member(\n                game_root,\n                "Player.bin",\n            )\n            player_source = f"{player_cpk} :: common/etc/pesdb/Player.bin"\n\n        players = parse_player_bin(player_bin_data)\n        print(f"Players in native Player.bin: {len(players)}")\n        print(f"Player source: {player_source}")\n\n        matched = 0\n        missing = 0\n\n        by_player = players\n        for team in teams:\n            for player in team["roster"]:\n                meta = by_player.get(player["player_id"])\n                if meta is None:\n                    missing += 1\n                else:\n                    player.update(\n                        {\n                            "name": meta["name"],\n                            "age": meta["age"],\n                        }\n                    )\n                    matched += 1\n\n        write_output(\n            output_path,\n            teams,\n            edit_player_count,\n            team_count,\n            roster_entries,\n            unique_players,\n            player_source,\n            game_version,\n        )\n\n        print("")\n        print("=" * 70)\n        print("Finished")\n        print("=" * 70)\n        print(f"Teams exported:       {len(teams)}")\n        print(f"Roster player entries: {roster_entries}")\n        print(f"Player IDs matched:    {matched}")\n        print(f"Player IDs missing:    {missing}")\n        print(f"Output:                {output_path}")\n\n        return 0\n\n    except Exception as exc:\n        print("")\n        print("ERROR:")\n        print(str(exc))\n        return 1\n\n\nif __name__ == "__main__":\n    sys.exit(main())\n'

FOTMOB_SOURCE = '# -*- coding: utf-8 -*-\n"""\nPES 2017 -> FotMob Player Face Downloader (TEAM-FIRST)\n========================================================\n\nInput:\n    teams_players.txt\n\nOutput assets:\n    Asset\\\\Players\\\\<PES_PLAYER_ID>.png\n\nImportant behavior:\n    1) Existing PNG files are checked FIRST. If the file already exists,\n       absolutely no FotMob search/download is performed for that player.\n    2) Player resolution is TEAM-FIRST:\n         a) Resolve the PES team name -> FotMob team ID.\n         b) Fetch that FotMob team\'s squad.\n         c) Match the PES player against that squad using name + age + shirt\n            number + team context.\n         d) Only if the team squad path fails, fall back to FotMob player\n            search using "player name + team" and then player name.\n    3) Team IDs from the previous team-logo downloader cache are reused when\n       available: fotmob_team_cache.json\n    4) Team squad responses are cached in:\n         fotmob_team_squad_cache.json\n    5) Successful PES -> FotMob player mappings are cached in:\n         fotmob_player_teamfirst_cache.json\n    6) Downloads/searches are concurrent and configurable.\n    7) No TXT containing image paths is created.\n\nThe source TXT is the combined exporter file produced by this project.\n"""\n\nfrom __future__ import annotations\n\nimport argparse\nimport concurrent.futures\nimport json\nimport re\nimport threading\nimport time\nimport unicodedata\nimport urllib.error\nimport urllib.parse\nimport urllib.request\nfrom pathlib import Path\nfrom typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple\n\n\n# -----------------------------------------------------------------------------\n# Paths / endpoints\n# -----------------------------------------------------------------------------\n\nSCRIPT_DIR = Path(__file__).resolve().parent\nDEFAULT_INPUT = SCRIPT_DIR / "teams_players.txt"\nASSET_DIR = SCRIPT_DIR / "Asset" / "Players"\n\n# Reuse the team cache created by pes2017_team_asset_downloader.py when it is\n# available. This avoids re-discovering hundreds of team IDs.\nTEAM_CACHE_FILE = SCRIPT_DIR / "fotmob_team_cache.json"\nTEAM_SQUAD_CACHE_FILE = SCRIPT_DIR / "fotmob_team_squad_cache.json"\nPLAYER_CACHE_FILE = SCRIPT_DIR / "fotmob_player_teamfirst_cache.json"\nFAILURE_FILE = SCRIPT_DIR / "fotmob_player_failures.txt"\n\nFOTMOB_SEARCH_URL = "https://www.fotmob.com/api/data/search/suggest"\nFOTMOB_TEAMS_URL = "https://www.fotmob.com/api/data/teams?id={}"\nFOTMOB_PLAYER_IMAGE_URL = (\n    "https://images.fotmob.com/image_resources/playerimages/{}.png"\n)\n\nUSER_AGENT = (\n    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "\n    "AppleWebKit/537.36 (KHTML, like Gecko) "\n    "Chrome/153.0 Safari/537.36"\n)\n\nREQUEST_TIMEOUT = 25\nSEARCH_RETRIES = 4\nIMAGE_RETRIES = 4\nDEFAULT_TEAM_WORKERS = 10\nDEFAULT_PLAYER_WORKERS = 24\nREQUEST_DELAY = 0.02\n\n\n# -----------------------------------------------------------------------------\n# Source parser\n# -----------------------------------------------------------------------------\n\nPLAYER_LINE_RE = re.compile(\n    r"^\\s*\\d+\\s+\\|\\s*"\n    r"Slot:\\s*\\d+\\s+\\|\\s*"\n    r"(?P<name>.*?)\\s+\\|\\s*"\n    r"PES ID:\\s*(?P<pes_id>\\d+)\\s+\\|\\s*"\n    r"Age:\\s*(?P<age>\\d+)\\s+\\|\\s*"\n    r"Shirt:\\s*(?P<shirt>\\d+)\\s*$"\n)\n\nTEAM_HEADER_RE = re.compile(r"^\\[TEAM\\s+(\\d+)\\]\\s*$")\nTEAM_RECORD_RE = re.compile(r"^Team Record Index:\\s*(\\d+)\\s*$")\nTEAM_NAME_RE = re.compile(r"^Name:\\s*(.*?)\\s*$")\nTEAM_SHORT_RE = re.compile(r"^Short Name:\\s*(.*?)\\s*$")\nTEAM_ID_RE = re.compile(r"^Team ID:\\s*(\\d+)\\s*$")\n\n\ndef parse_source(source_text: str) -> Tuple[List[Dict[str, Any]], Dict[int, Dict[str, Any]]]:\n    """Parse teams and roster players while preserving team context."""\n    teams: List[Dict[str, Any]] = []\n    players: Dict[int, Dict[str, Any]] = {}\n\n    current_team: Optional[Dict[str, Any]] = None\n\n    for raw_line in source_text.splitlines():\n        line = raw_line.strip()\n\n        match = TEAM_HEADER_RE.match(line)\n        if match:\n            current_team = {\n                "team_index": int(match.group(1)),\n                "record_index": None,\n                "name": "",\n                "short_name": "",\n                "pes_team_id": None,\n                "players": [],\n            }\n            teams.append(current_team)\n            continue\n\n        if current_team is None:\n            continue\n\n        m = TEAM_RECORD_RE.match(line)\n        if m:\n            current_team["record_index"] = int(m.group(1))\n            continue\n\n        m = TEAM_NAME_RE.match(line)\n        if m:\n            current_team["name"] = m.group(1).strip()\n            continue\n\n        m = TEAM_SHORT_RE.match(line)\n        if m:\n            current_team["short_name"] = m.group(1).strip()\n            continue\n\n        m = TEAM_ID_RE.match(line)\n        if m:\n            current_team["pes_team_id"] = int(m.group(1))\n            continue\n\n        m = PLAYER_LINE_RE.match(line)\n        if not m:\n            continue\n\n        pes_id = int(m.group("pes_id"))\n        player_name = m.group("name").strip()\n        age = int(m.group("age"))\n        shirt = int(m.group("shirt"))\n\n        if not player_name:\n            continue\n\n        entry = {\n            "pes_id": pes_id,\n            "name": player_name,\n            "age": age,\n            "shirt": shirt,\n            "team_index": current_team["team_index"],\n            "team_name": current_team["name"],\n            "team_short_name": current_team["short_name"],\n            "pes_team_id": current_team["pes_team_id"],\n        }\n\n        current_team["players"].append(entry)\n\n        player = players.setdefault(\n            pes_id,\n            {\n                "pes_id": pes_id,\n                "name": player_name,\n                "age": age,\n                "teams": [],\n                "occurrences": [],\n            },\n        )\n\n        # Keep the first name/age, but keep every team context.\n        if not player.get("name"):\n            player["name"] = player_name\n        if not player.get("age"):\n            player["age"] = age\n\n        context_key = (\n            current_team["team_index"],\n            current_team["name"],\n            current_team["short_name"],\n        )\n\n        if context_key not in [\n            (x["team_index"], x["team_name"], x["team_short_name"])\n            for x in player["teams"]\n        ]:\n            player["teams"].append(\n                {\n                    "team_index": current_team["team_index"],\n                    "team_name": current_team["name"],\n                    "team_short_name": current_team["short_name"],\n                    "pes_team_id": current_team["pes_team_id"],\n                }\n            )\n\n        player["occurrences"].append(entry)\n\n    # Only valid team records.\n    teams = [\n        team\n        for team in teams\n        if team.get("pes_team_id") is not None\n        and team.get("name")\n    ]\n\n    return teams, players\n\n\n# -----------------------------------------------------------------------------\n# Text/name matching\n# -----------------------------------------------------------------------------\n\n\ndef normalize_text(value: str) -> str:\n    value = unicodedata.normalize("NFKD", value)\n    value = "".join(\n        ch for ch in value\n        if not unicodedata.combining(ch)\n    )\n    value = value.lower()\n    value = value.replace("&", " and ")\n    value = re.sub(r"[^a-z0-9]+", " ", value)\n    value = re.sub(r"\\s+", " ", value).strip()\n    return value\n\n\ndef compact(value: str) -> str:\n    return normalize_text(value).replace(" ", "")\n\n\ndef name_tokens(value: str) -> List[str]:\n    return normalize_text(value).split()\n\n\ndef first_initial(value: str) -> str:\n    tokens = name_tokens(value)\n    return tokens[0][0] if tokens and tokens[0] else ""\n\n\ndef surname(value: str) -> str:\n    tokens = name_tokens(value)\n    return tokens[-1] if tokens else ""\n\n\ndef team_name_score(source: str, candidate: str) -> int:\n    a = normalize_text(source)\n    b = normalize_text(candidate)\n    if not a or not b:\n        return 0\n    if a == b:\n        return 1000\n    if compact(a) == compact(b):\n        return 950\n    if a in b or b in a:\n        return 650\n    a_tokens = set(a.split())\n    b_tokens = set(b.split())\n    common = len(a_tokens & b_tokens)\n    return common * 150\n\n\ndef candidate_score(\n    source: Dict[str, Any],\n    candidate: Dict[str, Any],\n    source_team_name: str = "",\n) -> int:\n    source_name = str(source.get("name", ""))\n    candidate_name = str(candidate.get("name", ""))\n\n    q = normalize_text(source_name)\n    c = normalize_text(candidate_name)\n    if not q or not c:\n        return -10_000\n\n    score = 0\n\n    if q == c:\n        score += 1800\n    elif compact(q) == compact(c):\n        score += 1650\n\n    q_tokens = name_tokens(source_name)\n    c_tokens = name_tokens(candidate_name)\n\n    q_surname = surname(source_name)\n    c_surname = surname(candidate_name)\n\n    if q_surname and c_surname:\n        if q_surname == c_surname:\n            score += 800\n        elif q_surname in c_surname or c_surname in q_surname:\n            score += 450\n\n    # The PES file often stores initials while FotMob stores full first names.\n    # Matching the first initial is therefore a strong signal.\n    qi = first_initial(source_name)\n    ci = first_initial(candidate_name)\n    if qi and ci and qi == ci:\n        score += 350\n\n    common_tokens = len(set(q_tokens) & set(c_tokens))\n    score += common_tokens * 140\n\n    if source_team_name and candidate.get("team_name"):\n        score += int(\n            team_name_score(\n                source_team_name,\n                str(candidate["team_name"]),\n            )\n            * 1.25\n        )\n\n    source_age = source.get("age")\n    candidate_age = candidate.get("age")\n    if isinstance(source_age, int) and isinstance(candidate_age, int):\n        diff = abs(source_age - candidate_age)\n        if diff == 0:\n            score += 240\n        elif diff == 1:\n            score += 180\n        elif diff <= 3:\n            score += 80\n        elif diff <= 6:\n            score += 20\n        else:\n            score -= 120\n\n    source_shirt = source.get("shirt")\n    candidate_shirt = candidate.get("shirt")\n    if isinstance(source_shirt, int) and isinstance(candidate_shirt, int):\n        if source_shirt == candidate_shirt:\n            score += 180\n\n    return score\n\n\n# -----------------------------------------------------------------------------\n# JSON / HTTP helpers\n# -----------------------------------------------------------------------------\n\n\ndef atomic_write_json(path: Path, data: Dict[str, Any]) -> None:\n    tmp = path.with_suffix(path.suffix + ".tmp")\n    tmp.write_text(\n        json.dumps(data, ensure_ascii=False, indent=2),\n        encoding="utf-8",\n    )\n    tmp.replace(path)\n\n\ndef load_json(path: Path) -> Dict[str, Any]:\n    if not path.exists():\n        return {}\n    try:\n        value = json.loads(path.read_text(encoding="utf-8"))\n        return value if isinstance(value, dict) else {}\n    except Exception:\n        return {}\n\n\ncache_write_lock = threading.Lock()\n\ndef save_json(path: Path, data: Dict[str, Any]) -> None:\n    with cache_write_lock:\n        atomic_write_json(path, data)\n\n\ndef http_get(\n    url: str,\n    *,\n    accept: str,\n    retries: int,\n) -> bytes:\n    last_error: Optional[Exception] = None\n\n    for attempt in range(retries):\n        try:\n            request = urllib.request.Request(\n                url,\n                headers={\n                    "User-Agent": USER_AGENT,\n                    "Accept": accept,\n                    "Referer": "https://www.fotmob.com/",\n                },\n            )\n\n            with urllib.request.urlopen(\n                request,\n                timeout=REQUEST_TIMEOUT,\n            ) as response:\n                data = response.read()\n\n            if REQUEST_DELAY:\n                time.sleep(REQUEST_DELAY)\n\n            return data\n\n        except (\n            urllib.error.HTTPError,\n            urllib.error.URLError,\n            TimeoutError,\n            ConnectionError,\n        ) as exc:\n            last_error = exc\n            if attempt + 1 < retries:\n                time.sleep(0.7 * (2 ** attempt))\n\n    raise RuntimeError(\n        f"Request failed after {retries} attempts: {url}\\n"\n        f"Last error: {last_error}"\n    )\n\n\ndef get_json(url: str) -> Any:\n    raw = http_get(\n        url,\n        accept="application/json",\n        retries=SEARCH_RETRIES,\n    )\n    return json.loads(raw.decode("utf-8"))\n\n\ndef walk_dicts(value: Any) -> Iterable[Dict[str, Any]]:\n    if isinstance(value, dict):\n        yield value\n        for child in value.values():\n            yield from walk_dicts(child)\n    elif isinstance(value, list):\n        for item in value:\n            yield from walk_dicts(item)\n\n\n# -----------------------------------------------------------------------------\n# Generic FotMob entity extraction\n# -----------------------------------------------------------------------------\n\n\ndef extract_id(obj: Dict[str, Any], keys: Sequence[str]) -> Optional[int]:\n    for key in keys:\n        value = obj.get(key)\n        if isinstance(value, bool):\n            continue\n        if isinstance(value, int):\n            return value\n        if isinstance(value, str) and value.strip().isdigit():\n            return int(value.strip())\n    return None\n\n\ndef extract_name(obj: Dict[str, Any]) -> str:\n    for key in ("name", "playerName", "fullName", "title"):\n        value = obj.get(key)\n        if isinstance(value, str) and value.strip():\n            return value.strip()\n        if isinstance(value, dict):\n            full = value.get("fullName")\n            if isinstance(full, str) and full.strip():\n                return full.strip()\n    return ""\n\n\ndef extract_team_name(obj: Dict[str, Any]) -> str:\n    for key in ("teamName", "primaryTeamName"):\n        value = obj.get(key)\n        if isinstance(value, str) and value.strip():\n            return value.strip()\n\n    for key in ("team", "primaryTeam"):\n        value = obj.get(key)\n        if isinstance(value, dict):\n            name = value.get("name") or value.get("teamName")\n            if isinstance(name, str) and name.strip():\n                return name.strip()\n\n    return ""\n\n\ndef extract_age(obj: Dict[str, Any]) -> Optional[int]:\n    for key in ("age", "playerAge"):\n        value = obj.get(key)\n        if isinstance(value, int):\n            return value\n        if isinstance(value, str) and value.strip().isdigit():\n            return int(value.strip())\n    return None\n\n\ndef extract_shirt(obj: Dict[str, Any]) -> Optional[int]:\n    for key in (\n        "shirtNumber",\n        "shirtNo",\n        "number",\n        "jerseyNumber",\n    ):\n        value = obj.get(key)\n        if isinstance(value, int):\n            return value\n        if isinstance(value, str) and value.strip().isdigit():\n            return int(value.strip())\n    return None\n\n\ndef looks_like_team(obj: Dict[str, Any]) -> bool:\n    for key in (\n        "type",\n        "entityType",\n        "entity_type",\n        "kind",\n        "category",\n        "objectType",\n        "subType",\n    ):\n        value = obj.get(key)\n        if isinstance(value, str) and "team" in value.lower():\n            return True\n\n    return (\n        ("teamId" in obj)\n        and bool(extract_name(obj))\n    )\n\n\ndef looks_like_player(obj: Dict[str, Any]) -> bool:\n    for key in (\n        "type",\n        "entityType",\n        "entity_type",\n        "kind",\n        "category",\n        "objectType",\n        "subType",\n    ):\n        value = obj.get(key)\n        if isinstance(value, str) and value.lower() in {\n            "player",\n            "squadmember",\n            "squad_member",\n        }:\n            return True\n\n    # Require a player-ish property so the parent TEAM object does not become\n    # a fake player candidate.\n    return (\n        ("playerId" in obj or "id" in obj)\n        and bool(extract_name(obj))\n        and (\n            "age" in obj\n            or "position" in obj\n            or "nationality" in obj\n            or "shirtNumber" in obj\n            or "shirtNo" in obj\n            or "number" in obj\n        )\n    )\n\n\n# -----------------------------------------------------------------------------\n# Team-first discovery\n# -----------------------------------------------------------------------------\n\n\ndef search_team_id(team_name: str, short_name: str) -> Tuple[Optional[int], Optional[str]]:\n    queries = [team_name]\n    if short_name and short_name not in queries:\n        queries.append(short_name)\n\n    aliases = {\n        "czech republic": "Czechia",\n        "turkey": "Türkiye",\n        "korea republic": "South Korea",\n        "usa": "United States",\n        "uae": "United Arab Emirates",\n        "ivory coast": "Côte d\'Ivoire",\n    }\n    alias = aliases.get(normalize_text(team_name))\n    if alias and alias not in queries:\n        queries.append(alias)\n\n    best: Tuple[int, Optional[int], Optional[str]] = (-10_000, None, None)\n\n    for query in queries:\n        params = urllib.parse.urlencode(\n            {\n                "hits": 50,\n                "lang": "en",\n                "term": query,\n            }\n        )\n        url = f"{FOTMOB_SEARCH_URL}?{params}"\n\n        try:\n            payload = get_json(url)\n        except Exception:\n            continue\n\n        for obj in walk_dicts(payload):\n            if not looks_like_team(obj):\n                continue\n            team_id = extract_id(obj, ("teamId", "id", "entityId"))\n            candidate_name = extract_name(obj)\n            if team_id is None or not candidate_name:\n                continue\n\n            score = team_name_score(team_name, candidate_name)\n            if normalize_text(candidate_name) == normalize_text(team_name):\n                score += 500\n\n            if score > best[0]:\n                best = (score, team_id, candidate_name)\n\n        if best[0] >= 1500:\n            break\n\n    if best[1] is None or best[0] < 500:\n        return None, None\n\n    return best[1], best[2]\n\n\ndef extract_squad_candidates(payload: Any, fallback_team_name: str) -> List[Dict[str, Any]]:\n    candidates_by_id: Dict[int, Dict[str, Any]] = {}\n\n    for obj in walk_dicts(payload):\n        if not looks_like_player(obj):\n            continue\n\n        player_id = extract_id(obj, ("playerId", "id", "entityId"))\n        name = extract_name(obj)\n        if player_id is None or not name:\n            continue\n\n        candidate = {\n            "fotmob_id": player_id,\n            "name": name,\n            "team_name": extract_team_name(obj) or fallback_team_name,\n            "age": extract_age(obj),\n            "shirt": extract_shirt(obj),\n        }\n\n        candidates_by_id[player_id] = candidate\n\n    return list(candidates_by_id.values())\n\n\ndef fetch_team_squad(\n    fotmob_team_id: int,\n    team_name: str,\n) -> List[Dict[str, Any]]:\n    url = FOTMOB_TEAMS_URL.format(fotmob_team_id)\n    payload = get_json(url)\n    return extract_squad_candidates(payload, team_name)\n\n\ndef resolve_team(\n    team: Dict[str, Any],\n    team_cache: Dict[str, Any],\n) -> Dict[str, Any]:\n    pes_team_id = int(team["pes_team_id"])\n    cache_key = str(pes_team_id)\n\n    cached = team_cache.get(cache_key)\n    if isinstance(cached, dict):\n        fotmob_id = cached.get("fotmob_id")\n        if isinstance(fotmob_id, int):\n            return {\n                "pes_team_id": pes_team_id,\n                "name": team["name"],\n                "short_name": team["short_name"],\n                "fotmob_id": fotmob_id,\n                "matched_name": cached.get("matched_name", ""),\n                "source": "CACHE",\n            }\n\n    fotmob_id, matched_name = search_team_id(\n        team["name"],\n        team["short_name"],\n    )\n\n    if fotmob_id is None:\n        return {\n            "pes_team_id": pes_team_id,\n            "name": team["name"],\n            "short_name": team["short_name"],\n            "fotmob_id": None,\n            "matched_name": None,\n            "source": "NOT_FOUND",\n        }\n\n    team_cache[cache_key] = {\n        "pes_team_id": pes_team_id,\n        "name": team["name"],\n        "short_name": team["short_name"],\n        "fotmob_id": fotmob_id,\n        "matched_name": matched_name,\n    }\n\n    return {\n        "pes_team_id": pes_team_id,\n        "name": team["name"],\n        "short_name": team["short_name"],\n        "fotmob_id": fotmob_id,\n        "matched_name": matched_name,\n        "source": "SEARCH",\n    }\n\n\ndef match_player_against_squad(\n    player: Dict[str, Any],\n    squad: Sequence[Dict[str, Any]],\n    team_name: str,\n) -> Tuple[Optional[Dict[str, Any]], int]:\n    best: Optional[Dict[str, Any]] = None\n    best_score = -10_000\n\n    for candidate in squad:\n        score = candidate_score(\n            player,\n            candidate,\n            source_team_name=team_name,\n        )\n        if score > best_score:\n            best_score = score\n            best = candidate\n\n    return best, best_score\n\n\n# -----------------------------------------------------------------------------\n# Fallback player search\n# -----------------------------------------------------------------------------\n\n\ndef fallback_player_search(\n    player: Dict[str, Any],\n) -> Tuple[Optional[int], Optional[str], int]:\n    """Used ONLY after all available team-squad matches failed."""\n    source_name = player["name"]\n    source_teams = player.get("teams", [])\n\n    queries: List[str] = []\n    for team in source_teams[:3]:\n        if team.get("team_name"):\n            queries.append(\n                f"{source_name} {team[\'team_name\']}"\n            )\n    queries.append(source_name)\n\n    best: Tuple[int, Optional[int], Optional[str]] = (-10_000, None, None)\n    seen_ids: set[int] = set()\n\n    for query in queries:\n        params = urllib.parse.urlencode(\n            {\n                "hits": 50,\n                "lang": "en",\n                "term": query,\n            }\n        )\n        url = f"{FOTMOB_SEARCH_URL}?{params}"\n\n        try:\n            payload = get_json(url)\n        except Exception:\n            continue\n\n        for obj in walk_dicts(payload):\n            if not looks_like_player(obj):\n                continue\n\n            candidate_id = extract_id(obj, ("playerId", "id", "entityId"))\n            candidate_name = extract_name(obj)\n            candidate_team = extract_team_name(obj)\n\n            if candidate_id is None or not candidate_name:\n                continue\n            if candidate_id in seen_ids:\n                continue\n            seen_ids.add(candidate_id)\n\n            candidate = {\n                "fotmob_id": candidate_id,\n                "name": candidate_name,\n                "team_name": candidate_team,\n                "age": extract_age(obj),\n                "shirt": extract_shirt(obj),\n            }\n\n            score = candidate_score(\n                player,\n                candidate,\n                source_team_name=(\n                    player.get("teams", [{}])[0].get("team_name", "")\n                    if player.get("teams")\n                    else ""\n                ),\n            )\n\n            # Explicit team hit is strongly preferred.\n            for team in source_teams:\n                if candidate_team and normalize_text(\n                    str(team.get("team_name", ""))\n                ) == normalize_text(candidate_team):\n                    score += 700\n                    break\n\n            if score > best[0]:\n                best = (score, candidate_id, candidate_name)\n\n        if best[1] is not None and best[0] >= 1900:\n            break\n\n    if best[1] is None or best[0] < 800:\n        return None, None, best[0]\n\n    return best[1], best[2], best[0]\n\n\n# -----------------------------------------------------------------------------\n# Image download\n# -----------------------------------------------------------------------------\n\n\ndef download_face(fotmob_id: int, target: Path) -> None:\n    # Re-check immediately before network I/O because another worker/process\n    # could have produced the same file after the initial scan.\n    if target.exists():\n        return\n\n    url = FOTMOB_PLAYER_IMAGE_URL.format(fotmob_id)\n    raw = http_get(\n        url,\n        accept="image/png,image/*;q=0.9,*/*;q=0.8",\n        retries=IMAGE_RETRIES,\n    )\n\n    if not raw.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):\n        raise RuntimeError(\n            f"FotMob returned a non-PNG response: {url}"\n        )\n\n    target.parent.mkdir(parents=True, exist_ok=True)\n    temp = target.with_suffix(".part")\n    temp.write_bytes(raw)\n    temp.replace(target)\n\n\n# -----------------------------------------------------------------------------\n# Main workflow\n# -----------------------------------------------------------------------------\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(\n        description=(\n            "Team-first FotMob player-face downloader for the PES 2017 "\n            "teams_players.txt file."\n        )\n    )\n    parser.add_argument(\n        "--input",\n        default=str(DEFAULT_INPUT),\n        help="Input TXT (default: teams_players.txt)",\n    )\n    parser.add_argument(\n        "--team-workers",\n        type=int,\n        default=DEFAULT_TEAM_WORKERS,\n        help=f"Concurrent team workers (default: {DEFAULT_TEAM_WORKERS})",\n    )\n    parser.add_argument(\n        "--player-workers",\n        type=int,\n        default=DEFAULT_PLAYER_WORKERS,\n        help=f"Concurrent player/download workers (default: {DEFAULT_PLAYER_WORKERS})",\n    )\n    parser.add_argument(\n        "--limit",\n        type=int,\n        default=0,\n        help="Process only the first N missing players (0 = all).",\n    )\n    parser.add_argument(\n        "--dry-run",\n        action="store_true",\n        help="Parse and report counts; do not access the network or download.",\n    )\n    parser.add_argument(\n        "--retry-failed",\n        action="store_true",\n        help="Ignore previous player-cache entries and retry unresolved mappings.",\n    )\n\n    args = parser.parse_args()\n\n    if args.team_workers < 1 or args.player_workers < 1:\n        print("ERROR: worker counts must be >= 1")\n        return 1\n\n    input_path = Path(args.input).expanduser().resolve()\n    if not input_path.exists():\n        print(f"ERROR: input file not found:\\n{input_path}")\n        return 1\n\n    source_text = input_path.read_text(encoding="utf-8-sig")\n    teams, players = parse_source(source_text)\n\n    ASSET_DIR.mkdir(parents=True, exist_ok=True)\n\n    all_player_list = sorted(\n        players.values(),\n        key=lambda p: int(p["pes_id"]),\n    )\n\n    # Existing files are NEVER searched again.\n    missing_players = [\n        player\n        for player in all_player_list\n        if not (ASSET_DIR / f"{player[\'pes_id\']}.png").exists()\n    ]\n\n    if args.limit > 0:\n        missing_players = missing_players[:args.limit]\n\n    print("=" * 78)\n    print("PES 2017 -> FotMob PLAYER FACE DOWNLOADER (TEAM-FIRST)")\n    print("=" * 78)\n    print(f"Input            : {input_path}")\n    print(f"Asset folder     : {ASSET_DIR}")\n    print(f"Teams parsed     : {len(teams)}")\n    print(f"Unique players   : {len(players)}")\n    print(f"Already existed  : {len(all_player_list) - len([p for p in all_player_list if p in missing_players]) if args.limit == 0 else \'N/A\'}")\n    print(f"Missing this run : {len(missing_players)}")\n    print(f"Team workers     : {args.team_workers}")\n    print(f"Player workers   : {args.player_workers}")\n    print("")\n\n    if args.dry_run:\n        print("DRY RUN: no network requests were made.")\n        return 0\n\n    team_cache = load_json(TEAM_CACHE_FILE)\n    squad_cache = load_json(TEAM_SQUAD_CACHE_FILE)\n    player_cache = load_json(PLAYER_CACHE_FILE)\n\n    # Determine only the teams relevant to players that are still missing.\n    needed_team_indices = sorted({\n        context["team_index"]\n        for player in missing_players\n        for context in player.get("teams", [])\n    })\n    teams_by_index = {\n        int(team["team_index"]): team\n        for team in teams\n    }\n    needed_teams = [\n        teams_by_index[idx]\n        for idx in needed_team_indices\n        if idx in teams_by_index\n    ]\n\n    print(f"Teams needed for missing players: {len(needed_teams)}")\n\n    # -------------------------------------------------------------------------\n    # Stage 1: resolve FotMob team IDs.\n    # -------------------------------------------------------------------------\n\n    resolved_teams: Dict[int, Dict[str, Any]] = {}\n\n    def resolve_worker(team: Dict[str, Any]) -> Dict[str, Any]:\n        try:\n            return resolve_team(team, team_cache)\n        except Exception as exc:\n            return {\n                "pes_team_id": team["pes_team_id"],\n                "name": team["name"],\n                "short_name": team["short_name"],\n                "fotmob_id": None,\n                "matched_name": None,\n                "source": "ERROR",\n                "error": str(exc),\n            }\n\n    with concurrent.futures.ThreadPoolExecutor(\n        max_workers=args.team_workers\n    ) as executor:\n        futures = [\n            executor.submit(resolve_worker, team)\n            for team in needed_teams\n        ]\n        for future in concurrent.futures.as_completed(futures):\n            result = future.result()\n            pes_team_id = result.get("pes_team_id")\n            if pes_team_id is not None:\n                resolved_teams[int(pes_team_id)] = result\n\n    save_json(TEAM_CACHE_FILE, team_cache)\n\n    teams_found = sum(\n        1\n        for x in resolved_teams.values()\n        if isinstance(x.get("fotmob_id"), int)\n    )\n    print(f"FotMob teams resolved: {teams_found}/{len(needed_teams)}")\n\n    # -------------------------------------------------------------------------\n    # Stage 2: fetch FotMob squads for resolved teams.\n    # -------------------------------------------------------------------------\n\n    squads_by_pes_team: Dict[int, List[Dict[str, Any]]] = {}\n    squad_errors: List[Dict[str, Any]] = []\n\n    def squad_worker(item: Tuple[int, Dict[str, Any]]) -> Tuple[int, Optional[List[Dict[str, Any]]], Optional[str]]:\n        pes_team_id, team_info = item\n        fotmob_id = team_info.get("fotmob_id")\n        team_name = team_info.get("matched_name") or team_info.get("name") or ""\n        if not isinstance(fotmob_id, int):\n            return pes_team_id, None, "NO_FOTMOB_TEAM_ID"\n\n        cache_key = str(fotmob_id)\n        cached = squad_cache.get(cache_key)\n        if isinstance(cached, dict) and isinstance(cached.get("players"), list):\n            return pes_team_id, cached["players"], None\n\n        try:\n            squad = fetch_team_squad(\n                fotmob_id,\n                str(team_name),\n            )\n            squad_cache[cache_key] = {\n                "fotmob_team_id": fotmob_id,\n                "team_name": team_name,\n                "players": squad,\n            }\n            return pes_team_id, squad, None\n        except Exception as exc:\n            return pes_team_id, None, str(exc)\n\n    with concurrent.futures.ThreadPoolExecutor(\n        max_workers=args.team_workers\n    ) as executor:\n        futures = [\n            executor.submit(squad_worker, item)\n            for item in resolved_teams.items()\n        ]\n        for future in concurrent.futures.as_completed(futures):\n            pes_team_id, squad, error = future.result()\n            if squad is not None:\n                squads_by_pes_team[pes_team_id] = squad\n            else:\n                squad_errors.append({\n                    "pes_team_id": pes_team_id,\n                    "error": error,\n                })\n\n    save_json(TEAM_SQUAD_CACHE_FILE, squad_cache)\n\n    print(\n        f"Team squads loaded: {len(squads_by_pes_team)}/"\n        f"{len(resolved_teams)}"\n    )\n\n    # -------------------------------------------------------------------------\n    # Stage 3: team-first local matching.\n    # -------------------------------------------------------------------------\n\n    matched: Dict[int, Dict[str, Any]] = {}\n    unmatched: List[Dict[str, Any]] = []\n\n    for player in missing_players:\n        best: Optional[Dict[str, Any]] = None\n        best_score = -10_000\n\n        for context in player.get("teams", []):\n            pes_team_id = context.get("pes_team_id")\n            team_name = context.get("team_name", "")\n            if pes_team_id is None:\n                continue\n\n            squad = squads_by_pes_team.get(int(pes_team_id), [])\n            candidate, score = match_player_against_squad(\n                player,\n                squad,\n                str(team_name),\n            )\n\n            if candidate is not None and score > best_score:\n                best = candidate\n                best_score = score\n\n        # High confidence team-squad match.\n        if best is not None and best_score >= 950:\n            matched[int(player["pes_id"])] = {\n                "fotmob_id": int(best["fotmob_id"]),\n                "matched_name": best["name"],\n                "score": best_score,\n                "method": "TEAM_SQUAD",\n            }\n        else:\n            unmatched.append(player)\n\n    print(\n        f"Team-first matches: {len(matched)} | "\n        f"Fallback needed: {len(unmatched)}"\n    )\n\n    # -------------------------------------------------------------------------\n    # Stage 4: only unmatched players use player search fallback.\n    # -------------------------------------------------------------------------\n\n    fallback_errors: List[Dict[str, Any]] = []\n\n    def fallback_worker(player: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:\n        pes_id = int(player["pes_id"])\n\n        if not args.retry_failed:\n            cached = player_cache.get(str(pes_id))\n            if isinstance(cached, dict) and isinstance(cached.get("fotmob_id"), int):\n                return pes_id, {\n                    "fotmob_id": int(cached["fotmob_id"]),\n                    "matched_name": cached.get("matched_name", ""),\n                    "score": cached.get("score"),\n                    "method": "CACHE",\n                }\n\n        try:\n            fotmob_id, matched_name, score = fallback_player_search(player)\n            if fotmob_id is None:\n                return pes_id, {\n                    "fotmob_id": None,\n                    "matched_name": matched_name,\n                    "score": score,\n                    "method": "NOT_FOUND",\n                    "name": player["name"],\n                }\n            return pes_id, {\n                "fotmob_id": fotmob_id,\n                "matched_name": matched_name,\n                "score": score,\n                "method": "SEARCH_FALLBACK",\n            }\n        except Exception as exc:\n            return pes_id, {\n                "fotmob_id": None,\n                "matched_name": None,\n                "score": None,\n                "method": "SEARCH_ERROR",\n                "name": player["name"],\n                "error": str(exc),\n            }\n\n    if unmatched:\n        with concurrent.futures.ThreadPoolExecutor(\n            max_workers=args.player_workers\n        ) as executor:\n            futures = [\n                executor.submit(fallback_worker, player)\n                for player in unmatched\n            ]\n            for future in concurrent.futures.as_completed(futures):\n                pes_id, result = future.result()\n                if isinstance(result.get("fotmob_id"), int):\n                    matched[pes_id] = result\n                elif result.get("method") == "SEARCH_ERROR":\n                    fallback_errors.append(result)\n\n    # Store successful mappings. Do NOT cache NOT_FOUND; the next execution\n    # should be allowed to try again with newly improved matching logic.\n    for pes_id, result in matched.items():\n        player_cache[str(pes_id)] = {\n            "pes_id": pes_id,\n            "fotmob_id": result["fotmob_id"],\n            "matched_name": result.get("matched_name", ""),\n            "score": result.get("score"),\n            "method": result.get("method", ""),\n        }\n    save_json(PLAYER_CACHE_FILE, player_cache)\n\n    # -------------------------------------------------------------------------\n    # Stage 5: concurrent image download.\n    # -------------------------------------------------------------------------\n\n    download_candidates = [\n        player\n        for player in missing_players\n        if int(player["pes_id"]) in matched\n        and isinstance(matched[int(player["pes_id"])].get("fotmob_id"), int)\n    ]\n\n    stats = {\n        "EXISTS": 0,\n        "DOWNLOADED": 0,\n        "NOT_FOUND": len(missing_players) - len(matched),\n        "SEARCH_ERRORS": len(fallback_errors) + len(squad_errors),\n        "DOWNLOAD_ERRORS": 0,\n        "TEAM_SQUAD": sum(\n            1 for x in matched.values()\n            if x.get("method") == "TEAM_SQUAD"\n        ),\n        "FALLBACK": sum(\n            1 for x in matched.values()\n            if x.get("method") in {"SEARCH_FALLBACK", "CACHE"}\n        ),\n    }\n\n    failure_records: List[Dict[str, Any]] = []\n    failure_records.extend(fallback_errors)\n    failure_records.extend(squad_errors)\n\n    if download_candidates:\n        def download_worker(player: Dict[str, Any]) -> Dict[str, Any]:\n            pes_id = int(player["pes_id"])\n            target = ASSET_DIR / f"{pes_id}.png"\n\n            # Strict existing-file rule: do not download over an existing file.\n            if target.exists():\n                return {\n                    "status": "EXISTS",\n                    "pes_id": pes_id,\n                    "name": player["name"],\n                }\n\n            mapping = matched[pes_id]\n            try:\n                download_face(\n                    int(mapping["fotmob_id"]),\n                    target,\n                )\n                return {\n                    "status": "DOWNLOADED",\n                    "pes_id": pes_id,\n                    "name": player["name"],\n                }\n            except Exception as exc:\n                return {\n                    "status": "DOWNLOAD_ERROR",\n                    "pes_id": pes_id,\n                    "name": player["name"],\n                    "fotmob_id": mapping.get("fotmob_id"),\n                    "error": str(exc),\n                }\n\n        completed = 0\n        with concurrent.futures.ThreadPoolExecutor(\n            max_workers=args.player_workers\n        ) as executor:\n            futures = [\n                executor.submit(download_worker, player)\n                for player in download_candidates\n            ]\n            for future in concurrent.futures.as_completed(futures):\n                completed += 1\n                result = future.result()\n                status = result.get("status")\n                if status == "DOWNLOADED":\n                    stats["DOWNLOADED"] += 1\n                elif status == "EXISTS":\n                    stats["EXISTS"] += 1\n                else:\n                    stats["DOWNLOAD_ERRORS"] += 1\n                    failure_records.append(result)\n\n                if completed == 1 or completed % 250 == 0 or completed == len(download_candidates):\n                    print(\n                        f"Download progress {completed:>5}/{len(download_candidates)} | "\n                        f"downloaded={stats[\'DOWNLOADED\']} | "\n                        f"errors={stats[\'DOWNLOAD_ERRORS\']}"\n                    )\n\n    # -------------------------------------------------------------------------\n    # Final report\n    # -------------------------------------------------------------------------\n\n    if failure_records:\n        FAILURE_FILE.write_text(\n            "\\n".join(\n                json.dumps(item, ensure_ascii=False)\n                for item in failure_records\n            )\n            + "\\n",\n            encoding="utf-8",\n        )\n    elif FAILURE_FILE.exists():\n        FAILURE_FILE.unlink()\n\n    save_json(TEAM_CACHE_FILE, team_cache)\n    save_json(TEAM_SQUAD_CACHE_FILE, squad_cache)\n    save_json(PLAYER_CACHE_FILE, player_cache)\n\n    print("")\n    print("=" * 78)\n    print("FINISHED")\n    print("=" * 78)\n    print(f"Unique players       : {len(players)}")\n    print(f"Missing this run     : {len(missing_players)}")\n    print(f"Team-first matched   : {stats[\'TEAM_SQUAD\']}")\n    print(f"Fallback matched     : {stats[\'FALLBACK\']}")\n    print(f"Downloaded           : {stats[\'DOWNLOADED\']}")\n    print(f"Already existed      : {stats[\'EXISTS\']}")\n    print(f"Not found            : {stats[\'NOT_FOUND\']}")\n    print(f"Search/team errors   : {stats[\'SEARCH_ERRORS\']}")\n    print(f"Download errors      : {stats[\'DOWNLOAD_ERRORS\']}")\n    print(f"Assets folder        : {ASSET_DIR}")\n    if failure_records:\n        print(f"Failure log          : {FAILURE_FILE}")\n\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'

pes17 = _load_embedded_module("embedded_pes2017_exporter", PES2017_EXPORTER_SOURCE)
pes21 = _load_embedded_module("embedded_pes2021_exporter", PES2021_EXPORTER_SOURCE)
fotmob = _load_embedded_module("embedded_fotmob_downloader", FOTMOB_SOURCE)

# ============================================================================
# HELPER FUNCTIONS & CACHE
# ============================================================================

FLAG_CODES = {
    "AFG": "af", "ALB": "al", "ALG": "dz", "ANG": "ao", "ARG": "ar", "ARM": "am", "AUS": "au", "AUT": "at",
    "AZE": "az", "BAH": "bs", "BAN": "bd", "BEL": "be", "BEN": "bj", "BER": "bm", "BFA": "bf", "BHR": "bh",
    "BIH": "ba", "BLR": "by", "BOL": "bo", "BRA": "br", "BRU": "bn", "BUL": "bg", "BUR": "bi", "CAM": "cm",
    "CAN": "ca", "CHI": "cl", "CHN": "cn", "COL": "co", "COM": "km", "COD": "cd", "CGO": "cg", "CRC": "cr",
    "CRO": "hr", "CUB": "cu", "CUW": "cw", "CYP": "cy", "CZE": "cz", "DEN": "dk", "DJI": "dj", "DMA": "dm",
    "DOM": "do", "ECU": "ec", "EGY": "eg", "ENG": "gb-eng", "EQG": "gq", "ERI": "er", "ESP": "es", "EST": "ee",
    "ETH": "et", "FIJ": "fj", "FIN": "fi", "FRA": "fr", "FRO": "fo", "GAB": "ga", "GAM": "gm", "GEO": "ge",
    "GER": "de", "GHA": "gh", "GIB": "gi", "GRE": "gr", "GUI": "gn", "GUM": "gu", "GUY": "gy", "HAI": "ht",
    "HON": "hn", "HUN": "hu", "IDN": "id", "IND": "in", "IRL": "ie", "IRN": "ir", "IRQ": "iq", "ISL": "is",
    "ISR": "il", "ITA": "it", "JAM": "jm", "JPN": "jp", "JOR": "jo", "KAZ": "kz", "KEN": "ke", "KGZ": "kg",
    "KOR": "kr", "KSA": "sa", "KUW": "kw", "LAO": "la", "LBN": "lb", "LBR": "lr", "LBY": "ly", "LIE": "li",
    "LTU": "lt", "LUX": "lu", "LVA": "lv", "MAC": "mo", "MAD": "mg", "MAS": "my", "MEX": "mx", "MLI": "ml",
    "MLT": "mt", "MNE": "me", "MNG": "mn", "MOZ": "mz", "MRI": "mu", "MTN": "mr", "NAM": "na", "NED": "nl",
    "NEP": "np", "NER": "ne", "NGA": "ng", "NIG": "ng", "NIR": "gb-nir", "NOR": "no", "NZL": "nz", "OMA": "om",
    "PAK": "pk", "PAN": "pa", "PAR": "py", "PER": "pe", "PHI": "ph", "POL": "pl", "POR": "pt", "PRK": "kp",
    "PUR": "pr", "QAT": "qa", "ROU": "ro", "RSA": "za", "RUS": "ru", "RWA": "rw", "SAM": "ws", "SCO": "gb-sct",
    "SEN": "sn", "SEY": "sc", "SLE": "sl", "SLV": "sv", "SMR": "sm", "SOL": "sb", "SOM": "so", "SRB": "rs",
    "SUD": "sd", "SUI": "ch", "SVK": "sk", "SVN": "si", "SWE": "se", "SWZ": "sz", "SYR": "sy", "TAN": "tz",
    "THA": "th", "TJK": "tj", "TKM": "tm", "TLS": "tl", "TOG": "tg", "TRI": "tt", "TUN": "tn", "TUR": "tr",
    "UAE": "ae", "UGA": "ug", "UKR": "ua", "URU": "uy", "USA": "us", "UZB": "uz", "VEN": "ve", "VIE": "vn",
    "WAL": "gb-wls", "YEM": "ye", "ZAM": "zm", "ZIM": "zw", "PRT": "pt", "NLD": "nl", "CHE": "ch", "DEU": "de",
    "DNK": "dk", "BGR": "bg", "GRC": "gr", "SAU": "sa", "CRI": "cr", "HND": "hn", "CHL": "cl", "PRY": "py",
    "URY": "uy", "CIV": "ci"
}
NATIONAL_NAMES = {
    "england", "scotland", "wales", "northern ireland", "ireland", "france", "germany", "spain", "italy",
    "portugal", "netherlands", "belgium", "switzerland", "austria", "bulgaria", "greece", "romania", "latvia",
    "denmark", "norway", "sweden", "finland", "poland", "czech republic", "czechia", "slovakia", "croatia",
    "serbia", "slovenia", "bosnia and herzegovina", "montenegro", "north macedonia", "albania", "turkey",
    "ukraine", "russia", "iceland", "united states", "canada", "mexico", "brazil", "argentina", "uruguay",
    "chile", "colombia", "peru", "ecuador", "bolivia", "paraguay", "venezuela", "costa rica", "honduras",
    "jamaica", "japan", "south korea", "republic of korea", "korea republic", "china", "australia", "new zealand",
    "iran", "iraq", "saudi arabia", "united arab emirates", "qatar", "egypt", "morocco", "algeria", "tunisia",
    "senegal", "nigeria", "ghana", "cameroon", "south africa", "zambia", "zimbabwe", "angola", "mali",
    "guinea", "cape verde", "ivory coast", "cote d ivoire"
}

USER_HOME = Path.home()
DEFAULT_EDIT_PES21 = USER_HOME / "Documents" / "KONAMI" / "eFootball PES 2021 SEASON UPDATE" / "2026" / "save" / "EDIT00000000"
DEFAULT_EDIT_PES17 = USER_HOME / "Documents" / "KONAMI" / "Pro Evolution Soccer 2017" / "save" / "EDIT00000000"

def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower().replace("&", " and ")
    value = value.replace("’", "'").replace("–", "-").replace("—", "-")
    value = re.sub(r"\butd\b", "united", value)
    value = re.sub(r"\bfc\b|\bafc\b|\bsc\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()

def calculate_est_size(player_count: int) -> str:
    # Requirement: Players * 15 KB
    bytes_val = player_count * 15 * 1024
    if bytes_val >= 1024 * 1024 * 1024:
        return f"{bytes_val / (1024**3):.2f} GB"
    elif bytes_val >= 1024 * 1024:
        return f"{bytes_val / (1024**2):.2f} MB"
    elif bytes_val >= 1024:
        return f"{bytes_val / 1024:.1f} KB"
    return f"{bytes_val} B"

@dataclass
class TeamRec:
    index: int
    name: str
    short_name: str
    team_id: int

@dataclass
class PlayerRec:
    name: str
    pes_id: int
    age: Optional[int]
    team_name: str
    team_id: int
    slot: int
    shirt: Optional[int]

def parse_export_txt(path: Path) -> Tuple[List[TeamRec], List[PlayerRec]]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")

    player_rx = re.compile(
        r"^\s*\d+\s*\|\s*"
        r"(?:Slot:\s*(\d+)\s*\|\s*)?"
        r"(.*?)\s*\|\s*"
        r"PES ID:\s*(\d+)\s*\|\s*"
        r"Age:\s*([^|]+)\s*\|\s*"
        r"Shirt:\s*(\d+)\s*$"
    )

    teams: List[TeamRec] = []
    players: List[PlayerRec] = []

    matches = list(re.finditer(r"(?m)^\[TEAM\s+(\d+)\]\s*$", text))

    for pos, match in enumerate(matches):
        end = matches[pos + 1].start() if pos + 1 < len(matches) else len(text)
        block = text[match.start():end]

        nm = re.search(r"^Name:\s*(.*?)\s*$", block, re.M)
        sm = re.search(r"^Short Name:\s*(.*?)\s*$", block, re.M)
        tm = re.search(r"^Team ID:\s*(\d+)\s*$", block, re.M)

        if not (nm and sm and tm):
            continue

        team = TeamRec(
            index=int(match.group(1)),
            name=nm.group(1).strip(),
            short_name=sm.group(1).strip(),
            team_id=int(tm.group(1)),
        )
        teams.append(team)

        section = block.split("PLAYERS", 1)
        if len(section) < 2:
            continue

        for line in section[1].splitlines():
            pm = player_rx.match(line)
            if not pm:
                continue

            age_text = pm.group(4).strip()
            try:
                age: Optional[int] = int(age_text)
            except ValueError:
                age = None

            players.append(
                PlayerRec(
                    name=pm.group(2).strip(),
                    pes_id=int(pm.group(3)),
                    age=age,
                    team_name=team.name,
                    team_id=team.team_id,
                    slot=int(pm.group(1) or 0),
                    shirt=int(pm.group(5)),
                )
            )

    return teams, players

def is_national(team: TeamRec) -> bool:
    return team.short_name.upper() in FLAG_CODES or normalize_text(team.name) in NATIONAL_NAMES

def flag_code(team: TeamRec) -> Optional[str]:
    short = team.short_name.upper()
    if short in FLAG_CODES: return FLAG_CODES[short]
    aliases = {
        "united states": "us", "korea republic": "kr", "south korea": "kr",
        "czech republic": "cz", "czechia": "cz", "turkey": "tr", "iran": "ir",
        "ivory coast": "ci", "cote d ivoire": "ci", "england": "gb-eng",
        "scotland": "gb-sct", "wales": "gb-wls", "northern ireland": "gb-nir"
    }
    return aliases.get(normalize_text(team.name))

def load_json(path: Path) -> Dict[str, Any]:
    try:
        if path.is_file():
            obj = json.loads(path.read_text(encoding="utf-8"))
            return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    return {}

cache_write_lock = threading.Lock()

def save_json(path: Path, obj: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)

def locate_edit(version: str) -> Optional[Path]:
    candidates = [DEFAULT_EDIT_PES17] if version == "PES 2017" else [DEFAULT_EDIT_PES21]
    candidates.extend([APP_DIR / "EDIT00000000", Path.cwd() / "EDIT00000000"])
    for p in candidates:
        if p.is_file(): return p.resolve()
    return None

def export_selected(version: str, edit_path: Path, output_txt: Path, log, game_root: Optional[Path] = None) -> Dict[str, Any]:
    if version == "PES 2017":
        log("Decrypting PES 2017 EDIT00000000...")
        teams, rosters, tactics, players, meta = pes17.extract_pes17(edit_path)
        pes17.write_combined_txt(output_txt, teams, rosters, players, meta)
        return {"teams": len(teams), "players": sum(len(v) for v in rosters.values()), "unique_players": len(players)}

    log("Decrypting Football Life EDIT00000000...")
    edit_data, file_type, game_version, sizes = pes21.decrypt_edit_file(edit_path)
    player_count = int.from_bytes(edit_data[pes21.PLAYER_COUNT_OFFSET:pes21.PLAYER_COUNT_OFFSET + 2], "little")
    team_count = int.from_bytes(edit_data[pes21.TEAM_COUNT_OFFSET:pes21.TEAM_COUNT_OFFSET + 2], "little")
    if team_count <= 0: raise ValueError("Team count is zero; EDIT is unreadable.")
    teams = pes21.parse_teams(edit_data, team_count)
    roster_entries, unique_players = pes21.parse_rosters(edit_data, team_count, teams)
    game_root = game_root or pes21.discover_game_root(None)
    if game_root is None:
        raise FileNotFoundError("Football Life installation folder not found.")
    log(f"Loading Player.bin from: {game_root}")
    player_bin_data, player_cpk = pes21.load_database_member(game_root, "Player.bin")
    player_db = pes21.parse_player_bin(player_bin_data)
    matched = missing = 0
    for team in teams:
        for player in team.get("roster", []):
            meta = player_db.get(player["player_id"])
            if meta is None: missing += 1
            else:
                player.update({"name": meta["name"], "age": meta["age"]})
                matched += 1
    pes21.write_output(output_txt, teams, player_count, team_count, roster_entries, unique_players, f"{player_cpk} :: Player.bin", game_version)
    log(f"Player database: {matched:,} matched / {missing:,} unassigned")
    return {"teams": len(teams), "players": roster_entries, "unique_players": unique_players}

def download_binary(url: str, target: Path) -> None:
    if target.exists():
        return
    raw = fotmob.http_get(url, accept="image/png,image/*;q=0.9,*/*;q=0.8", retries=4)
    if not raw.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("Remote response is not a PNG image.")
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".part")
    temp.write_bytes(raw)
    temp.replace(target)

def make_zip(asset_root: Path, output_zip: Path) -> int:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    temp = output_zip.with_suffix(".tmp.zip")
    file_count = 0
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for dirname in ("Teams", "Players"):
            folder = asset_root / dirname
            if not folder.is_dir(): continue
            for p in folder.rglob("*"):
                if p.is_file():
                    archive.write(p, f"{dirname}/{p.relative_to(folder).as_posix()}")
                    file_count += 1
    temp.replace(output_zip)
    return file_count

# ============================================================================
# GUI WORKERS & INTERFACE (PORTRAIT WIZARD)
# ============================================================================

if QT_AVAILABLE:
    IS_QT6 = QT_API == "PyQt6"
    USER_ROLE = int(QtCore.Qt.ItemDataRole.UserRole) if IS_QT6 else int(QtCore.Qt.UserRole)
    SEARCH_ROLE = USER_ROLE + 1
    CHECKED = QtCore.Qt.CheckState.Checked if IS_QT6 else QtCore.Qt.Checked
    UNCHECKED = QtCore.Qt.CheckState.Unchecked if IS_QT6 else QtCore.Qt.Unchecked
    ITEM_IS_CHECKABLE = QtCore.Qt.ItemFlag.ItemIsUserCheckable if IS_QT6 else QtCore.Qt.ItemIsUserCheckable
    MSG_OK = QtWidgets.QMessageBox.StandardButton.Ok if IS_QT6 else QtWidgets.QMessageBox.Ok
    FRAME_NO_FRAME = QtWidgets.QFrame.Shape.NoFrame if IS_QT6 else QtWidgets.QFrame.NoFrame

    class ExportWorker(QtCore.QThread):
        progress = QtCore.pyqtSignal(int)
        status = QtCore.pyqtSignal(str)
        done = QtCore.pyqtSignal(dict)
        failed = QtCore.pyqtSignal(str)

        def __init__(self, version: str, edit_path: Path, output_txt: Path, game_root: Optional[Path] = None, parent=None):
            super().__init__(parent)
            self.version = version
            self.edit_path = edit_path
            self.output_txt = output_txt
            self.game_root = game_root

        def run(self) -> None:
            try:
                self.status.emit("Reading and decrypting save data...")
                self.progress.emit(15)
                summary = export_selected(self.version, self.edit_path, self.output_txt, self.status.emit, self.game_root)
                self.progress.emit(85)
                teams, players = parse_export_txt(self.output_txt)
                self.progress.emit(100)
                self.done.emit({"summary": summary, "teams": teams, "players": players, "export_txt": str(self.output_txt)})
            except Exception as exc:
                self.failed.emit(f"{type(exc).__name__}: {exc}")

    class DownloadWorker(QtCore.QThread):
            progress = QtCore.pyqtSignal(int)
            status = QtCore.pyqtSignal(str)
            log_msg = QtCore.pyqtSignal(str)
            done = QtCore.pyqtSignal(dict)
            failed = QtCore.pyqtSignal(str)
    
            def __init__(
                self,
                version: str,
                output_dir: Path,
                selected_ids: set[int],
                export_txt: Path,
                parent=None,
            ):
                super().__init__(parent)
                self.version = version
                self.output_dir = output_dir
                self.selected_ids = selected_ids
                self.export_txt = export_txt
    
            def run(self) -> None:
                try:
                    asset_root = self.output_dir / "Asset"
                    teams_dir = asset_root / "Teams"
                    players_dir = asset_root / "Players"
                    teams_dir.mkdir(parents=True, exist_ok=True)
                    players_dir.mkdir(parents=True, exist_ok=True)
    
                    teams, players = parse_export_txt(self.export_txt)
                    selected_teams = [
                        team for team in teams
                        if team.team_id in self.selected_ids
                    ]
    
                    # One PES player can appear more than once in the source TXT.
                    # Keep one download job per PES ID while retaining the first
                    # team context represented by the export parser.
                    selected_players: Dict[int, PlayerRec] = {}
                    for player in players:
                        if player.team_id in self.selected_ids:
                            selected_players.setdefault(player.pes_id, player)
    
                    self.progress.emit(3)
                    self.log_msg.emit(
                        f"Starting team-first pipeline for "
                        f"{len(selected_teams):,} teams & "
                        f"{len(selected_players):,} unique player faces..."
                    )
                    self.status.emit(
                        f"Prepared {len(selected_teams):,} team(s) and "
                        f"{len(selected_players):,} unique player face(s)."
                    )
    
                    # ------------------------------------------------------------------
                    # Stage 1: Resolve/download team logos and national-team flags.
                    # ------------------------------------------------------------------
                    team_cache_path = CACHE_DIR / "fotmob_team_cache.json"
                    team_cache = load_json(team_cache_path)
    
                    team_lock = threading.Lock()
    
                    def team_worker(team: TeamRec):
                        target = teams_dir / f"{team.team_id}.png"
    
                        if target.exists():
                            return "exists", team.name
    
                        try:
                            if is_national(team):
                                code = flag_code(team)
                                if not code:
                                    return (
                                        "failed",
                                        f"{team.name}: country flag code not found",
                                    )
    
                                download_binary(
                                    f"https://flagcdn.com/w320/{code}.png",
                                    target,
                                )
                                return "downloaded", f"{team.name} [FlagCDN]"
    
                            cache_item = team_cache.get(str(team.team_id), {})
                            fid = (
                                cache_item.get("fotmob_id")
                                if isinstance(cache_item, dict)
                                else None
                            )
    
                            if not isinstance(fid, int):
                                fid, matched_name = fotmob.search_team_id(
                                    team.name,
                                    team.short_name,
                                )
    
                                if fid is None:
                                    return (
                                        "failed",
                                        f"{team.name}: FotMob team not found",
                                    )
    
                                with team_lock:
                                    team_cache[str(team.team_id)] = {
                                        "pes_team_id": team.team_id,
                                        "name": team.name,
                                        "short_name": team.short_name,
                                        "fotmob_id": fid,
                                        "matched_name": matched_name,
                                    }
    
                            download_binary(
                                f"https://images.fotmob.com/image_resources/logo/teamlogo/{fid}.png",
                                target,
                            )
                            return "downloaded", f"{team.name} [FotMob]"
    
                        except Exception as exc:
                            return "failed", f"{team.name}: {exc}"
    
                    team_done = 0
                    team_failed = 0
    
                    self.status.emit(
                        f"Processing {len(selected_teams):,} team logo/flag(s)..."
                    )
    
                    with concurrent.futures.ThreadPoolExecutor(
                        max_workers=8
                    ) as executor:
                        futures = [
                            executor.submit(team_worker, team)
                            for team in selected_teams
                        ]
    
                        for future in concurrent.futures.as_completed(futures):
                            state, message = future.result()
                            team_done += 1
    
                            if state == "failed":
                                team_failed += 1
                                self.log_msg.emit(f"[Team ERROR] {message}")
                            elif state == "downloaded":
                                self.log_msg.emit(f"[Team] {message}")
    
                            self.progress.emit(
                                5 + int(
                                    team_done
                                    * 25
                                    / max(1, len(selected_teams))
                                )
                            )
                            self.status.emit(
                                f"Teams {team_done}/{len(selected_teams)}: {message}"
                            )
    
                    save_json(team_cache_path, team_cache)
    
                    # ------------------------------------------------------------------
                    # Stage 2: Resolve each club's FotMob squad before matching players.
                    # This is the key team-first behavior from Asset_Downloader.
                    # ------------------------------------------------------------------
                    player_cache_path = CACHE_DIR / "fotmob_player_cache.json"
                    squad_cache_path = CACHE_DIR / "fotmob_squad_cache.json"
    
                    player_cache = load_json(player_cache_path)
                    squad_cache = load_json(squad_cache_path)
    
                    resolved: Dict[int, Optional[int]] = {}
                    squads: Dict[int, List[Dict[str, Any]]] = {}
    
                    clubs = [
                        team for team in selected_teams
                        if not is_national(team)
                    ]
    
                    def resolve_team(team: TeamRec):
                        cache_item = team_cache.get(str(team.team_id), {})
                        fid = (
                            cache_item.get("fotmob_id")
                            if isinstance(cache_item, dict)
                            else None
                        )
    
                        if isinstance(fid, int):
                            return team.team_id, fid
    
                        try:
                            fid2, matched_name = fotmob.search_team_id(
                                team.name,
                                team.short_name,
                            )
    
                            if isinstance(fid2, int):
                                with team_lock:
                                    team_cache[str(team.team_id)] = {
                                        "pes_team_id": team.team_id,
                                        "name": team.name,
                                        "short_name": team.short_name,
                                        "fotmob_id": fid2,
                                        "matched_name": matched_name,
                                    }
    
                            return team.team_id, fid2
    
                        except Exception:
                            return team.team_id, None
    
                    if clubs:
                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=8
                        ) as executor:
                            futures = [
                                executor.submit(resolve_team, team)
                                for team in clubs
                            ]
                            for future in concurrent.futures.as_completed(futures):
                                team_id, fid = future.result()
                                resolved[team_id] = fid
    
                        def get_squad(team: TeamRec):
                            fid = resolved.get(team.team_id)
                            if not isinstance(fid, int):
                                return team.team_id, []
    
                            cached = squad_cache.get(str(fid))
    
                            # Accept both formats: the reference Asset_Downloader
                            # may store a dict with metadata + players, while older
                            # runs may have stored the raw list.
                            if isinstance(cached, dict) and isinstance(
                                cached.get("players"), list
                            ):
                                return team.team_id, cached["players"]
                            if isinstance(cached, list):
                                return team.team_id, cached
    
                            try:
                                data = fotmob.fetch_team_squad(
                                    fid,
                                    team.name,
                                )
                                squad_cache[str(fid)] = {
                                    "fotmob_team_id": fid,
                                    "team_name": team.name,
                                    "players": data,
                                }
                                return team.team_id, data
                            except Exception:
                                return team.team_id, []
    
                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=8
                        ) as executor:
                            futures = [
                                executor.submit(get_squad, team)
                                for team in clubs
                            ]
    
                            for future in concurrent.futures.as_completed(futures):
                                team_id, squad = future.result()
                                squads[team_id] = squad
    
                    save_json(squad_cache_path, squad_cache)
                    save_json(team_cache_path, team_cache)
    
                    # ------------------------------------------------------------------
                    # Stage 3: Team-first player resolution.
                    # Match by player name + team context + age + shirt number.
                    # Only unresolved players use the global player-search fallback.
                    # ------------------------------------------------------------------
                    jobs = [
                        (player, players_dir / f"{player.pes_id}.png")
                        for player in selected_players.values()
                        if not (players_dir / f"{player.pes_id}.png").exists()
                    ]
    
                    failures: List[str] = []
                    downloaded = 0
                    existing = len(selected_players) - len(jobs)
    
                    resolved_mappings: Dict[int, Dict[str, Any]] = {}
    
                    for player, target in jobs:
                        try:
                            cache_item = player_cache.get(str(player.pes_id), {})
                            fid = (
                                cache_item.get("fotmob_id")
                                if isinstance(cache_item, dict)
                                else None
                            )
                            matched_name = (
                                cache_item.get("matched_name", "")
                                if isinstance(cache_item, dict)
                                else ""
                            )
    
                            # Cache is reused only when it already contains a real ID.
                            if not isinstance(fid, int):
                                payload = {
                                    "name": player.name,
                                    "age": player.age,
                                    "shirt": player.shirt,
                                    "teams": [
                                        {
                                            "team_name": player.team_name,
                                            "pes_team_id": player.team_id,
                                        }
                                    ],
                                    "pes_id": player.pes_id,
                                }
    
                                squad = squads.get(player.team_id, [])
    
                                best, score = fotmob.match_player_against_squad(
                                    payload,
                                    squad,
                                    player.team_name,
                                )
    
                                # Use the stronger Asset_Downloader confidence
                                # threshold for the team-first path.
                                if best is not None and score >= 950:
                                    fid = int(best["fotmob_id"])
                                    matched_name = str(best.get("name", ""))
                                    method = "TEAM_SQUAD"
                                else:
                                    fid, matched_name, fallback_score = (
                                        fotmob.fallback_player_search(payload)
                                    )
                                    method = "SEARCH_FALLBACK"
                                    score = fallback_score
    
                                if not isinstance(fid, int):
                                    failures.append(
                                        f"{player.pes_id} {player.name}: "
                                        "FotMob player not found"
                                    )
                                    continue
    
                                player_cache[str(player.pes_id)] = {
                                    "pes_id": player.pes_id,
                                    "name": player.name,
                                    "team_name": player.team_name,
                                    "fotmob_id": fid,
                                    "matched_name": matched_name,
                                    "score": score,
                                    "method": method,
                                }
    
                            resolved_mappings[player.pes_id] = {
                                "fotmob_id": int(fid),
                                "matched_name": matched_name,
                                "method": (
                                    player_cache.get(
                                        str(player.pes_id), {}
                                    ).get("method", "CACHE")
                                    if isinstance(
                                        player_cache.get(
                                            str(player.pes_id), {}
                                        ),
                                        dict,
                                    )
                                    else "CACHE"
                                ),
                            }
    
                        except Exception as exc:
                            failures.append(
                                f"{player.pes_id} {player.name}: {exc}"
                            )
    
                    save_json(player_cache_path, player_cache)
    
                    # ------------------------------------------------------------------
                    # Stage 4: Concurrent image download using resolved IDs.
                    # ------------------------------------------------------------------
                    download_jobs = [
                        (
                            player,
                            players_dir / f"{player.pes_id}.png",
                        )
                        for player in selected_players.values()
                        if player.pes_id in resolved_mappings
                        and not (
                            players_dir / f"{player.pes_id}.png"
                        ).exists()
                    ]
    
                    self.status.emit(
                        f"Downloading {len(download_jobs):,} missing player face(s)..."
                    )
    
                    total_jobs = max(1, len(download_jobs))
                    done_count = 0
    
                    def player_download_worker(job):
                        player, target = job
                        mapping = resolved_mappings[player.pes_id]
    
                        try:
                            # download_face performs its own existence check and
                            # validates that the response is a real PNG.
                            fotmob.download_face(
                                int(mapping["fotmob_id"]),
                                target,
                            )
                            return (
                                "downloaded",
                                player,
                                mapping,
                            )
                        except Exception as exc:
                            return (
                                "failed",
                                player,
                                {
                                    **mapping,
                                    "error": str(exc),
                                },
                            )
    
                    if download_jobs:
                        with concurrent.futures.ThreadPoolExecutor(
                            max_workers=12
                        ) as executor:
                            futures = [
                                executor.submit(
                                    player_download_worker,
                                    job,
                                )
                                for job in download_jobs
                            ]
    
                            for future in concurrent.futures.as_completed(futures):
                                state, player, detail = future.result()
                                done_count += 1
    
                                if state == "downloaded":
                                    downloaded += 1
                                    self.log_msg.emit(
                                        f"[Face] Downloaded: "
                                        f"{player.name} "
                                        f"(PES ID: {player.pes_id})"
                                    )
                                else:
                                    error_text = detail.get(
                                        "error",
                                        "unknown download error",
                                    )
                                    failures.append(
                                        f"{player.pes_id} "
                                        f"{player.name}: {error_text}"
                                    )
                                    self.log_msg.emit(
                                        f"[Face ERROR] "
                                        f"{player.name} "
                                        f"(PES ID: {player.pes_id}): "
                                        f"{error_text}"
                                    )
    
                                self.progress.emit(
                                    30 + int(
                                        done_count
                                        * 58
                                        / total_jobs
                                    )
                                )
    
                                if (
                                    done_count == 1
                                    or done_count % 15 == 0
                                    or done_count == len(download_jobs)
                                ):
                                    self.status.emit(
                                        f"Faces: {done_count}/"
                                        f"{len(download_jobs)} "
                                        f"({downloaded} downloaded)"
                                    )
    
                    save_json(player_cache_path, player_cache)
    
                    # ------------------------------------------------------------------
                    # Stage 5: Create Asset.zip.
                    # ------------------------------------------------------------------
                    self.status.emit("Compressing into Asset.zip...")
                    self.progress.emit(92)
    
                    zip_path = self.output_dir / "Asset.zip"
                    archived_count = make_zip(
                        asset_root,
                        zip_path,
                    )
    
                    self.progress.emit(100)
                    self.log_msg.emit(
                        f"Packaging complete: "
                        f"{archived_count:,} files archived into "
                        f"{zip_path.name}"
                    )
    
                    self.done.emit(
                        {
                            "zip": str(zip_path),
                            "teams": len(selected_teams),
                            "players": len(selected_players),
                            "downloaded": downloaded,
                            "existing": existing,
                            "archived_count": archived_count,
                            "asset_root": str(asset_root),
                            "failures": failures,
                            "teams_failed": team_failed,
                            "team_first_matched": sum(
                                1
                                for item in player_cache.values()
                                if isinstance(item, dict)
                                and item.get("method") == "TEAM_SQUAD"
                            ),
                        }
                    )
    
                except Exception as exc:
                    self.failed.emit(
                        f"{type(exc).__name__}: {exc}"
                    )
    
    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("PES MODS • Face & Team Asset Suite")
            
            # Vertical Portrait Geometry
            self.setMinimumSize(620, 820)
            self.resize(680, 880)

            self.teams: List[TeamRec] = []
            self.players: List[PlayerRec] = []
            self.items: List[QtWidgets.QListWidgetItem] = []
            self.export_txt: Optional[Path] = None
            self.game_root: Optional[Path] = None
            self.export_worker: Optional[ExportWorker] = None
            self.worker: Optional[DownloadWorker] = None
            self.download_finished: bool = False

            self.build_ui()
            self.apply_style()
            self.init_paths()
            self.update_step_navigation()

        def build_ui(self) -> None:
            central = QtWidgets.QWidget()
            self.setCentralWidget(central)
            main_layout = QtWidgets.QVBoxLayout(central)
            main_layout.setContentsMargins(18, 16, 18, 14)
            main_layout.setSpacing(10)

            # Header
            header_layout = QtWidgets.QHBoxLayout()
            title_box = QtWidgets.QVBoxLayout()
            title = QtWidgets.QLabel("PES MODS")
            title.setObjectName("appTitle")
            subtitle = QtWidgets.QLabel("Face & Team Asset Suite · Vertical Wizard")
            subtitle.setObjectName("appSubtitle")
            title_box.addWidget(title)
            title_box.addWidget(subtitle)
            header_layout.addLayout(title_box, 1)

            self.step_badge = QtWidgets.QLabel("STEP 1 OF 4")
            self.step_badge.setObjectName("stepBadge")
            header_layout.addWidget(self.step_badge, 0, QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter if IS_QT6 else QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            main_layout.addLayout(header_layout)

            # Wizard Tab Widget
            self.tabs = QtWidgets.QTabWidget()
            self.tabs.setDocumentMode(True)
            main_layout.addWidget(self.tabs, 1)

            self.build_tab_1()
            self.build_tab_2()
            self.build_tab_3()
            self.build_tab_4()

            # Bottom Navigation Card
            nav_card = QtWidgets.QFrame()
            nav_card.setObjectName("navCard")
            nav_layout = QtWidgets.QHBoxLayout(nav_card)
            nav_layout.setContentsMargins(12, 10, 12, 10)

            self.nav_info = QtWidgets.QLabel("Select game version and locate EDIT file.")
            self.nav_info.setObjectName("navInfo")
            nav_layout.addWidget(self.nav_info, 1)

            self.btn_back = QtWidgets.QPushButton("← Back")
            self.btn_back.setObjectName("btnNav")
            self.btn_next = QtWidgets.QPushButton("Next →")
            self.btn_next.setObjectName("btnNext")

            nav_layout.addWidget(self.btn_back)
            nav_layout.addWidget(self.btn_next)
            main_layout.addWidget(nav_card)

            # Signal Connections
            self.tabs.currentChanged.connect(self.on_tab_changed)
            self.btn_back.clicked.connect(self.go_back)
            self.btn_next.clicked.connect(self.go_next)

        def create_scroll_pane(self):
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(FRAME_NO_FRAME)
            content = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(content)
            layout.setContentsMargins(14, 14, 14, 14)
            layout.setSpacing(12)
            scroll.setWidget(content)
            return scroll, layout

        # -------------------------------------------------------------------
        # STEP 1: GAME & SOURCE
        # -------------------------------------------------------------------
        def build_tab_1(self):
            scroll, layout = self.create_scroll_pane()

            game_group = QtWidgets.QGroupBox("Game Edition & Environment")
            gl = QtWidgets.QVBoxLayout(game_group)

            self.rb_fl = QtWidgets.QRadioButton("Football Life (PES 2021 Engine)")
            self.rb_pes17 = QtWidgets.QRadioButton("Pro Evolution Soccer 2017")
            self.rb_fl.setChecked(True)

            gl.addWidget(self.rb_fl)
            gl.addWidget(self.rb_pes17)

            self.active_game_banner = QtWidgets.QLabel("Active Target: Football Life")
            self.active_game_banner.setObjectName("activeBanner")
            gl.addWidget(self.active_game_banner)
            layout.addWidget(game_group)

            edit_group = QtWidgets.QGroupBox("Save File (EDIT00000000)")
            el = QtWidgets.QVBoxLayout(edit_group)
            self.edit_path = QtWidgets.QLineEdit()
            self.edit_path.setPlaceholderText("Path to EDIT00000000")
            btn_row = QtWidgets.QHBoxLayout()
            self.btn_auto_detect = QtWidgets.QPushButton("Auto-Detect")
            self.btn_browse_edit = QtWidgets.QPushButton("Browse File...")
            btn_row.addWidget(self.btn_auto_detect)
            btn_row.addWidget(self.btn_browse_edit)
            el.addWidget(self.edit_path)
            el.addLayout(btn_row)
            self.edit_status_lbl = QtWidgets.QLabel("Click Auto-Detect or Browse for your EDIT file.")
            self.edit_status_lbl.setObjectName("subStatus")
            el.addWidget(self.edit_status_lbl)
            layout.addWidget(edit_group)

            self.game_root_group = QtWidgets.QGroupBox("Football Life Game Directory")
            grl = QtWidgets.QVBoxLayout(self.game_root_group)
            self.game_root_path = QtWidgets.QLineEdit()
            self.game_root_path.setPlaceholderText("Path to SP Football Life main directory")
            self.btn_browse_root = QtWidgets.QPushButton("Browse Game Root...")
            grl.addWidget(self.game_root_path)
            grl.addWidget(self.btn_browse_root)
            self.root_status_lbl = QtWidgets.QLabel("Required to read Player.bin directly from CPK archives.")
            self.root_status_lbl.setObjectName("subStatus")
            grl.addWidget(self.root_status_lbl)
            layout.addWidget(self.game_root_group)

            layout.addStretch()
            self.tabs.addTab(scroll, "1 · Source")

            self.rb_fl.toggled.connect(self.init_paths)
            self.rb_pes17.toggled.connect(self.init_paths)
            self.btn_auto_detect.clicked.connect(self.auto_detect_edit)
            self.btn_browse_edit.clicked.connect(self.browse_edit)
            self.btn_browse_root.clicked.connect(self.browse_game_root)
            self.edit_path.textChanged.connect(self.validate_step_1)
            self.game_root_path.textChanged.connect(self.validate_step_1)

        # -------------------------------------------------------------------
        # STEP 2: OUTPUT & EXPORT
        # -------------------------------------------------------------------
        def build_tab_2(self):
            scroll, layout = self.create_scroll_pane()

            dest_group = QtWidgets.QGroupBox("Destination Mod (PT) Folder")
            dl = QtWidgets.QVBoxLayout(dest_group)
            self.dest_path = QtWidgets.QLineEdit(str(APP_DIR))
            self.btn_browse_dest = QtWidgets.QPushButton("Browse Output Folder...")
            dl.addWidget(self.dest_path)
            dl.addWidget(self.btn_browse_dest)
            layout.addWidget(dest_group)

            action_group = QtWidgets.QGroupBox("Extraction & Decryption")
            al = QtWidgets.QVBoxLayout(action_group)
            self.btn_run_export = QtWidgets.QPushButton("Decrypt & Export Data (TXT)")
            self.btn_run_export.setObjectName("btnPrimary")
            al.addWidget(self.btn_run_export)

            self.export_progress = QtWidgets.QProgressBar()
            self.export_progress.setValue(0)
            al.addWidget(self.export_progress)

            self.export_status = QtWidgets.QLabel("Status: Waiting for user action.")
            self.export_status.setObjectName("subStatus")
            al.addWidget(self.export_status)

            self.export_summary_card = QtWidgets.QFrame()
            self.export_summary_card.setObjectName("summaryCard")
            scl = QtWidgets.QVBoxLayout(self.export_summary_card)
            self.lbl_exp_teams = QtWidgets.QLabel("Teams: —")
            self.lbl_exp_players = QtWidgets.QLabel("Players: —")
            self.lbl_exp_txt = QtWidgets.QLabel("Output TXT: —")
            self.lbl_exp_txt.setWordWrap(True)
            scl.addWidget(self.lbl_exp_teams)
            scl.addWidget(self.lbl_exp_players)
            scl.addWidget(self.lbl_exp_txt)
            al.addWidget(self.export_summary_card)

            layout.addWidget(action_group)
            layout.addStretch()
            self.tabs.addTab(scroll, "2 · Export")

            self.btn_browse_dest.clicked.connect(self.browse_dest)
            self.btn_run_export.clicked.connect(self.start_export)

        # -------------------------------------------------------------------
        # STEP 3: TEAMS SELECTION & 15 KB ESTIMATOR
        # -------------------------------------------------------------------
        def build_tab_3(self):
            scroll, layout = self.create_scroll_pane()

            strip = QtWidgets.QFrame()
            strip.setObjectName("metricStrip")
            sl = QtWidgets.QHBoxLayout(strip)
            self.m_teams = QtWidgets.QLabel("0 Teams")
            self.m_teams.setObjectName("metricValue")
            self.m_faces = QtWidgets.QLabel("0 Faces")
            self.m_faces.setObjectName("metricValue")
            self.m_size = QtWidgets.QLabel("0 KB")
            self.m_size.setObjectName("metricHighlight")
            sl.addWidget(self.m_teams)
            sl.addStretch()
            sl.addWidget(self.m_faces)
            sl.addStretch()
            sl.addWidget(self.m_size)
            layout.addWidget(strip)

            team_box = QtWidgets.QGroupBox("Filter & Select Teams")
            tl = QtWidgets.QVBoxLayout(team_box)

            search_row = QtWidgets.QHBoxLayout()
            self.search_input = QtWidgets.QLineEdit()
            self.search_input.setPlaceholderText("Search teams by name...")
            self.btn_all = QtWidgets.QPushButton("Select All")
            self.btn_none = QtWidgets.QPushButton("Clear")
            search_row.addWidget(self.search_input, 1)
            search_row.addWidget(self.btn_all)
            search_row.addWidget(self.btn_none)
            tl.addLayout(search_row)

            self.team_list = QtWidgets.QListWidget()
            self.team_list.setMinimumHeight(350)
            tl.addWidget(self.team_list)
            layout.addWidget(team_box)

            self.tabs.addTab(scroll, "3 · Teams")

            self.search_input.textChanged.connect(self.filter_teams)
            self.btn_all.clicked.connect(lambda: self.set_all_teams(True))
            self.btn_none.clicked.connect(lambda: self.set_all_teams(False))
            self.team_list.itemChanged.connect(self.on_team_toggled)

        # -------------------------------------------------------------------
        # STEP 4: DOWNLOAD & PACKAGE
        # -------------------------------------------------------------------
        def build_tab_4(self):
            scroll, layout = self.create_scroll_pane()

            summary_box = QtWidgets.QGroupBox("Final Download Summary")
            sl = QtWidgets.QVBoxLayout(summary_box)

            self.lbl_sum_game = QtWidgets.QLabel("Game Engine: —")
            self.lbl_sum_teams = QtWidgets.QLabel("Selected Teams: 0")
            self.lbl_sum_faces = QtWidgets.QLabel("Unique Player Faces: 0")
            self.lbl_sum_est = QtWidgets.QLabel("Estimated Total Download (15 KB / face): 0 KB")
            self.lbl_sum_est.setObjectName("metricHighlight")

            sl.addWidget(self.lbl_sum_game)
            sl.addWidget(self.lbl_sum_teams)
            sl.addWidget(self.lbl_sum_faces)
            sl.addWidget(self.lbl_sum_est)
            layout.addWidget(summary_box)

            run_box = QtWidgets.QGroupBox("Download & Zip Packaging")
            rl = QtWidgets.QVBoxLayout(run_box)

            self.btn_start_sync = QtWidgets.QPushButton("START ASSET DOWNLOAD & ZIP")
            self.btn_start_sync.setObjectName("btnAction")
            self.btn_start_sync.setMinimumHeight(44)
            rl.addWidget(self.btn_start_sync)

            self.dl_bar = QtWidgets.QProgressBar()
            self.dl_bar.setValue(0)
            rl.addWidget(self.dl_bar)

            self.dl_status = QtWidgets.QLabel("Status: Idle. Click button to begin.")
            self.dl_status.setObjectName("subStatus")
            rl.addWidget(self.dl_status)

            self.console_log = QtWidgets.QPlainTextEdit()
            self.console_log.setReadOnly(True)
            self.console_log.setMaximumBlockCount(800)
            self.console_log.setMinimumHeight(180)
            rl.addWidget(self.console_log)

            layout.addWidget(run_box)
            self.tabs.addTab(scroll, "4 · Download")

            self.btn_start_sync.clicked.connect(self.start_download)

        # -------------------------------------------------------------------
        # STYLING (VERTICAL MODERN GLASSMORPHISM)
        # -------------------------------------------------------------------
        def apply_style(self):
            self.setStyleSheet("""
                QWidget {
                    background: #080c14;
                    color: #f8fafc;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    font-size: 9.5pt;
                }
                QLabel#appTitle {
                    font-size: 17pt;
                    font-weight: 900;
                    color: #38bdf8;
                    letter-spacing: 0.5px;
                }
                QLabel#appSubtitle {
                    font-size: 9pt;
                    color: #94a3b8;
                }
                QLabel#stepBadge {
                    background: #17253b;
                    color: #38bdf8;
                    border: 1px solid #1e3a5f;
                    border-radius: 12px;
                    padding: 5px 12px;
                    font-weight: 800;
                    font-size: 8.5pt;
                }
                QTabWidget::pane {
                    border: 1px solid #1c2638;
                    border-radius: 10px;
                    background: #0d1522;
                    top: -1px;
                }
                QTabBar::tab {
                    background: #111a28;
                    color: #94a3b8;
                    border: 1px solid #1c2638;
                    border-bottom: none;
                    padding: 8px 14px;
                    margin-right: 2px;
                    border-top-left-radius: 6px;
                    border-top-right-radius: 6px;
                }
                QTabBar::tab:selected {
                    background: #192a42;
                    color: #38bdf8;
                    font-weight: bold;
                    border-color: #38bdf8;
                }
                QGroupBox {
                    border: 1px solid #1c2638;
                    border-radius: 8px;
                    margin-top: 10px;
                    padding: 14px 10px 10px 10px;
                    background: #0b111c;
                    font-weight: 700;
                    color: #cbd5e1;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                }
                QRadioButton {
                    spacing: 8px;
                    padding: 4px;
                    font-size: 10pt;
                    font-weight: 600;
                    color: #f1f5f9;
                }
                QRadioButton::indicator {
                    width: 16px;
                    height: 16px;
                    border-radius: 8px;
                    border: 2px solid #475569;
                    background: #0b111c;
                }
                QRadioButton::indicator:checked {
                    border: 2px solid #38bdf8;
                    background: qradialgradient(cx:0.5, cy:0.5, radius:0.4, fx:0.5, fy:0.5, stop:0 #38bdf8, stop:1 #0284c7);
                }
                QLabel#activeBanner {
                    background: #102338;
                    border: 1px solid #1d4ed8;
                    border-radius: 6px;
                    padding: 6px 8px;
                    color: #93c5fd;
                    font-size: 8.5pt;
                    margin-top: 4px;
                }
                QLineEdit, QListWidget, QPlainTextEdit {
                    background: #080d15;
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    padding: 7px;
                    color: #f8fafc;
                }
                QLineEdit:focus, QListWidget:focus {
                    border: 1px solid #38bdf8;
                }
                QPushButton {
                    background: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 7px 12px;
                    color: #f8fafc;
                    font-weight: 600;
                }
                QPushButton:hover { background: #28374d; }
                QPushButton:disabled { color: #576a78; background: #0e1520; border-color: #1a2536; }
                QPushButton#btnPrimary {
                    background: #0284c7;
                    border-color: #38bdf8;
                    font-weight: 700;
                }
                QPushButton#btnPrimary:hover { background: #0369a1; }
                QPushButton#btnAction {
                    background: #059669;
                    border-color: #10b981;
                    font-weight: 800;
                    font-size: 10.5pt;
                }
                QPushButton#btnAction:hover { background: #047857; }
                QProgressBar {
                    border: 1px solid #1e293b;
                    border-radius: 6px;
                    text-align: center;
                    background: #080d15;
                    height: 18px;
                    font-size: 8.5pt;
                }
                QProgressBar::chunk { background: #0284c7; border-radius: 5px; }
                QFrame#metricStrip, QFrame#summaryCard, QFrame#navCard {
                    background: #0e1726;
                    border: 1px solid #1e293b;
                    border-radius: 8px;
                }
                QLabel#metricValue {
                    font-size: 11pt;
                    font-weight: 800;
                    color: #f8fafc;
                }
                QLabel#metricHighlight {
                    font-size: 11pt;
                    font-weight: 800;
                    color: #10b981;
                }
                QLabel#subStatus { color: #94a3b8; font-size: 8.5pt; }
                QLabel#navInfo { color: #94a3b8; font-size: 9pt; }
                QPushButton#btnNext {
                    background: #0284c7;
                    border-color: #38bdf8;
                    font-weight: 700;
                    padding: 8px 16px;
                }
                QPushButton#btnNext:hover { background: #0369a1; }
                QListWidget::item { padding: 5px; border-radius: 4px; }
                QListWidget::item:hover { background: #162438; }
            """)

        # -------------------------------------------------------------------
        # NAVIGATION & CONTROLS
        # -------------------------------------------------------------------
        def current_game(self) -> str:
            return "Football Life" if self.rb_fl.isChecked() else "PES 2017"

        def init_paths(self):
            game = self.current_game()
            is_fl = game == "Football Life"
            self.game_root_group.setVisible(is_fl)

            if is_fl:
                self.active_game_banner.setText("Active Target: SP Football Life (PES 2021 Database Architecture)")
            else:
                self.active_game_banner.setText("Active Target: Pro Evolution Soccer 2017 (EDIT00000000 Roster Data)")

            detected = locate_edit(game)
            if detected:
                self.edit_path.setText(str(detected))
                self.edit_status_lbl.setText(f"Auto-detected EDIT: {detected.name}")
            else:
                self.edit_path.clear()
                self.edit_status_lbl.setText("EDIT not found automatically. Please browse.")

            if is_fl:
                root = pes21.discover_game_root(None)
                if root: self.game_root_path.setText(str(root))

            self.update_step_navigation()

        def auto_detect_edit(self):
            self.init_paths()

        def browse_edit(self):
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select EDIT00000000", self.edit_path.text() or str(APP_DIR))
            if path: self.edit_path.setText(path)

        def browse_game_root(self):
            dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Football Life Root Folder", self.game_root_path.text() or str(APP_DIR))
            if dir_path: self.game_root_path.setText(dir_path)

        def browse_dest(self):
            dir_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Output Folder", self.dest_path.text() or str(APP_DIR))
            if dir_path: self.dest_path.setText(dir_path)

        def validate_step_1(self) -> bool:
            edit_valid = Path(self.edit_path.text().strip()).is_file()
            if self.current_game() == "Football Life":
                root_valid = bool(self.game_root_path.text().strip()) and Path(self.game_root_path.text().strip()).is_dir()
            else:
                root_valid = True
            self.update_step_navigation()
            return edit_valid and root_valid

        def update_step_navigation(self):
            idx = self.tabs.currentIndex()
            self.step_badge.setText(f"STEP {idx + 1} OF 4")
            self.btn_back.setEnabled(idx > 0 and self.worker is None)

            prompts = [
                "Select game version and locate EDIT00000000.",
                "Choose destination and decrypt team/player database.",
                "Filter and select which teams to download.",
                "Start download and build package. Button below exits when complete."
            ]
            self.nav_info.setText(prompts[idx])

            if idx == 0:
                self.btn_next.setText("Next →")
                self.btn_next.setEnabled(Path(self.edit_path.text().strip()).is_file())
            elif idx == 1:
                self.btn_next.setText("Next →")
                self.btn_next.setEnabled(bool(self.export_txt and self.export_txt.is_file()))
            elif idx == 2:
                self.btn_next.setText("Next →")
                self.btn_next.setEnabled(len(self.selected_ids()) > 0)
            elif idx == 3:
                # Requirement: Complete button is DISABLED until download finishes; then closes app
                if not self.download_finished:
                    self.btn_next.setText("Complete")
                    self.btn_next.setEnabled(False)
                else:
                    self.btn_next.setText("Exit / Close")
                    self.btn_next.setEnabled(True)

            self.update_summary_labels()

        def on_tab_changed(self, idx):
            self.update_step_navigation()

        def go_back(self):
            cur = self.tabs.currentIndex()
            if cur > 0 and self.worker is None:
                self.tabs.setCurrentIndex(cur - 1)

        def go_next(self):
            cur = self.tabs.currentIndex()
            if cur == 0:
                if not Path(self.edit_path.text().strip()).is_file():
                    QtWidgets.QMessageBox.warning(self, "Missing File", "Please select a valid EDIT00000000 file.", MSG_OK)
                    return
                self.tabs.setCurrentIndex(1)
            elif cur == 1:
                if not (self.export_txt and self.export_txt.is_file()):
                    QtWidgets.QMessageBox.information(self, "Export Required", "Click 'Decrypt & Export Data' first.", MSG_OK)
                    return
                self.tabs.setCurrentIndex(2)
            elif cur == 2:
                if not self.selected_ids():
                    QtWidgets.QMessageBox.warning(self, "No Teams", "Please select at least one team.", MSG_OK)
                    return
                self.tabs.setCurrentIndex(3)
            elif cur == 3:
                if self.download_finished:
                    self.close()

        # -------------------------------------------------------------------
        # EXPORT LOGIC
        # -------------------------------------------------------------------
        def start_export(self):
            edit_file = Path(self.edit_path.text().strip())
            if not edit_file.is_file():
                QtWidgets.QMessageBox.warning(self, "Error", "EDIT file does not exist.", MSG_OK)
                return

            game = self.current_game()
            fl_root = Path(self.game_root_path.text().strip()) if game == "Football Life" else None
            out_folder = Path(self.dest_path.text().strip() or APP_DIR)
            out_folder.mkdir(parents=True, exist_ok=True)
            txt_name = "teams_players.txt" if game == "PES 2017" else "teams_players_PES2021.txt"
            self.export_txt = out_folder / txt_name

            self.btn_run_export.setEnabled(False)
            self.export_progress.setValue(10)
            self.export_status.setText("Decrypting database...")

            self.export_worker = ExportWorker(game, edit_file, self.export_txt, fl_root, self)
            self.export_worker.progress.connect(self.export_progress.setValue)
            self.export_worker.status.connect(self.export_status.setText)
            self.export_worker.done.connect(self.on_export_done)
            self.export_worker.failed.connect(lambda e: QtWidgets.QMessageBox.critical(self, "Export Error", e, MSG_OK))
            self.export_worker.start()

        def on_export_done(self, res):
            self.btn_run_export.setEnabled(True)
            self.teams = res["teams"]
            self.players = res["players"]
            self.export_status.setText("Export completed successfully.")

            self.lbl_exp_teams.setText(f"Teams Exported: {len(self.teams):,}")
            self.lbl_exp_players.setText(f"Players Parsed: {len(self.players):,}")
            self.lbl_exp_txt.setText(f"Output TXT: {self.export_txt.name}")

            self.team_list.blockSignals(True)
            self.team_list.clear()
            self.items.clear()
            for t in self.teams:
                item = QtWidgets.QListWidgetItem(f"{t.name} ({t.short_name})")
                item.setData(USER_ROLE, t.team_id)
                item.setData(SEARCH_ROLE, f"{t.name} {t.short_name} {t.team_id}")
                item.setFlags(item.flags() | ITEM_IS_CHECKABLE)
                item.setCheckState(CHECKED)
                self.team_list.addItem(item)
                self.items.append(item)
            self.team_list.blockSignals(False)

            self.update_team_metrics()
            self.tabs.setCurrentIndex(2)

        # -------------------------------------------------------------------
        # TEAMS & 15 KB METRIC UPDATER
        # -------------------------------------------------------------------
        def filter_teams(self, query):
            q = normalize_text(query)
            for it in self.items:
                search_data = normalize_text(str(it.data(SEARCH_ROLE) or it.text()))
                it.setHidden(bool(q) and q not in search_data)

        def set_all_teams(self, check: bool):
            self.team_list.blockSignals(True)
            st = CHECKED if check else UNCHECKED
            for it in self.items: it.setCheckState(st)
            self.team_list.blockSignals(False)
            self.update_team_metrics()

        def on_team_toggled(self, item):
            self.update_team_metrics()

        def selected_ids(self) -> set[int]:
            return {int(it.data(USER_ROLE)) for it in self.items if it.checkState() == CHECKED}

        def update_team_metrics(self):
            sids = self.selected_ids()
            unique_faces = {p.pes_id for p in self.players if p.team_id in sids}
            n_teams = len(sids)
            n_faces = len(unique_faces)
            est_size_str = calculate_est_size(n_faces)

            self.m_teams.setText(f"{n_teams:,} Teams")
            self.m_faces.setText(f"{n_faces:,} Faces")
            self.m_size.setText(f"~{est_size_str}")

            self.update_step_navigation()

        def update_summary_labels(self):
            sids = self.selected_ids()
            unique_faces = {p.pes_id for p in self.players if p.team_id in sids}
            n_faces = len(unique_faces)
            
            self.lbl_sum_game.setText(f"Game Engine: {self.current_game()}")
            self.lbl_sum_teams.setText(f"Selected Teams: {len(sids):,}")
            self.lbl_sum_faces.setText(f"Unique Player Faces: {n_faces:,}")
            self.lbl_sum_est.setText(f"Estimated Total Download (15 KB / face): ~{calculate_est_size(n_faces)}")

        # -------------------------------------------------------------------
        # DOWNLOAD & ZIP
        # -------------------------------------------------------------------
        def write_log(self, text: str):
            self.console_log.appendPlainText(text)
            cursor = self.console_log.textCursor()
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.End if IS_QT6 else QtGui.QTextCursor.End)
            self.console_log.setTextCursor(cursor)

        def start_download(self):
            if not self.export_txt or not self.export_txt.is_file():
                QtWidgets.QMessageBox.warning(self, "Export Required", "Please run Step 2 first.", MSG_OK)
                return
            sids = self.selected_ids()
            if not sids:
                QtWidgets.QMessageBox.warning(self, "No Scope", "Select at least one team in Step 3.", MSG_OK)
                return

            self.download_finished = False
            self.btn_start_sync.setEnabled(False)
            self.btn_next.setEnabled(False)
            self.btn_back.setEnabled(False)
            self.dl_bar.setValue(0)
            self.console_log.clear()
            self.write_log("Starting Face & Team Asset workflow...")

            dest = Path(self.dest_path.text().strip() or APP_DIR)
            self.worker = DownloadWorker(self.current_game(), dest, sids, self.export_txt, self)
            self.worker.progress.connect(self.dl_bar.setValue)
            self.worker.status.connect(self.dl_status.setText)
            self.worker.log_msg.connect(self.write_log)
            self.worker.done.connect(self.on_download_complete)
            self.worker.failed.connect(lambda e: self.on_download_error(e))
            self.worker.start()

        def on_download_error(self, err_msg: str):
            self.worker = None
            self.btn_start_sync.setEnabled(True)
            self.btn_back.setEnabled(True)
            self.dl_status.setText("Error during download. Check log.")
            self.write_log(f"ERROR: {err_msg}")
            QtWidgets.QMessageBox.critical(self, "Download Error", err_msg, MSG_OK)

        def on_download_complete(self, res):
            self.worker = None
            self.download_finished = True
            self.btn_start_sync.setEnabled(True)
            self.btn_back.setEnabled(True)
            self.dl_bar.setValue(100)
            self.dl_status.setText("All assets synchronized and packed.")
            self.write_log(f"Success! Output saved to: {res['zip']}")
            self.write_log(f"Total files archived in zip: {res['archived_count']:,}")

            # Requirement: Enable Complete button to close app
            self.btn_next.setEnabled(True)
            self.btn_next.setText("Exit / Close")
            self.btn_next.setStyleSheet("background: #059669; border-color: #10b981; font-weight: bold;")
            self.nav_info.setText("Download completed! Click 'Exit / Close' to exit.")

            msg = (
                "Asset Workflow Completed Successfully!\n\n"
                f"Teams Processed: {res['teams']:,}\n"
                f"Faces Processed: {res['players']:,}\n"
                f"Downloaded Faces: {res['downloaded']:,}\n"
                f"Files Archived in ZIP: {res['archived_count']:,}\n\n"
                f"Output Package: {res['zip']}"
            )
            QtWidgets.QMessageBox.information(self, "Sync Complete", msg, MSG_OK)


def launch():
    if not QT_AVAILABLE:
        print("PyQt is required. Run: pip install PyQt6")
        return 1
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    return app.exec() if QT_API == "PyQt6" else app.exec_()


if __name__ == "__main__":
    raise SystemExit(launch())
