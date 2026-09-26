class _TeamWinAPI:
    """layertext textfromtext WinAPI — only read (text read_uint8/read_int32/read_uint64
    tool original text text textandtext safe_read textandtext text‌text). for test textandtext completetext
    text text‌text is (api=...)."""

    def open_process(self, pid: int):
        return kernel32.OpenProcess(TEAM_PROCESS_ACCESS, False, pid)

    def close_handle(self, h_process):
        kernel32.CloseHandle(h_process)

    def read(self, h_process, addr: int, size: int) -> Optional[bytes]:
        return safe_read(h_process, addr, size)


class TeamIdentityTracker:
    """
    version 10text5 — textandtext independent textandtext team Home/Away for text‌text logo.

    input read (text tool original):
      * byte andtext menu:   base + 0x36F9AE0  (uint8)  — only 9 ⇒ detection team
      * league Home:       resolve(base+0x37F89D8, [0x40, 0xA0, 0x118]) → int32
      * text‌text Home: resolve(base+0x36F9C10, [0x8, 0x0, 0x100, 0x64]) + i*112
      * league Away:        resolve(base+0x36F9C10, [0xC8, 0x118]) → int32
      * text‌text Away:  resolve(base+0x36F9C10, [0xC8, 0x100, 0x64]) + i*112
        (i = 0..36 — text text = league_id + 1 — textandtext = Football_Database/{league}/{value}.png)
    resolve exactly text resolve_pointer_chain tool original is: first deref address
    starttext after for text text to‌text text dereftext text only text text‌textandtext.

    output: ident text team = (league_id, image_id) or None.
    None text «still text validtext text text» → UI same textwithtext «Home/Away»
    text text text‌text (textortext text user).
    """

    # chaintechnical note pointertechnical note — technical note tool original
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

    def __init__(self, db_dir: Optional[str] = None, logger=None,
                 proc_names=TEAM_TRACKER_PROC_NAMES, api=None,
                 pid_finder=None, base_finder=None, pt=None):
        self.db_dir = db_dir or os.path.join(_MOMENTUM_DATA_DIR,
                                             TEAM_DB_DIRNAME)
        self.logger = logger
        self.proc_names = tuple(proc_names)
        self.api = api or _TeamWinAPI()
        self._pid_finder = pid_finder or get_pid_by_name
        self._base_finder = base_finder or get_module_base
        # [PT v2.3.0] source datatechnical note PT (team‌technical note/color‌technical note/logo) — None technical note path legacy
        self.pt = pt if (pt is not None and pt.available()) else None
        self.h_process = None
        self.pid: Optional[int] = None
        self.base_addr: Optional[int] = None
        self.proc_name: Optional[str] = None
        self.connected = False
        # latest technical note validtechnical note technical note‌display technical note team:
        #   PT mode → int Team ID technical note path legacy → (league_id, image_id)
        self.ident = {"home": None, "away": None}
        # [PT v2.3.0] latest technical note ID technical noteandtechnical note‌technical note with chaintechnical note new
        self._pt_ids_last = None
        # [PT v2.3.2] technical note‌technical notefrom log detectiontechnical note chain (TEAM_PT_CHAIN)
        self._pt_diag_last = {"t": 0.0, "msg": None}
        # v2.0.6 — if technical noteandtechnical note never in menu 9 technical note technical note withtechnical note (technical note andtechnical note withtechnical note)technical note
        # technical note 2 second technical note technical note «technical note» technical note‌technical noteandtechnical note technical note technical notewithtechnical noteagetechnical note
        # _read_side_ident same‌technical note (league 0..35 + technical note 1..37)
        self._rescue_last = 0.0
        # versiontechnical note 10technical note6 — numbertechnical note color technical note team from technical noteand byte istechnical note (base+0x36F5198/A0)technical note
        # address‌technical note istechnical note‌technical note and change technical note‌technical note ⇒ in «technical note technical note technical note» technical noteandtechnical note technical note‌technical noteandtechnical note
        # (without technical note andtechnical note menu). None technical note read technical note technical note failed technical noteandtechnical note.
        self.color_idx = {"home": None, "away": None}

    # ---------------- technical note (independent from code original) ----------------
    def _find_process(self):
        """text attach_process tool original: text text pid + address text textandtext.
        [suite v2.1.5] — bridge-first: when the ModBridge answers, its
        game_status IS the truth (the bridge polls FL_2026.exe every 2 s —
        a backend opened before the game still learns when it appears).
        The local toolhelp scan is ONLY the standalone / bridge-unreachable
        fallback."""
        cli = getattr(self, "_bridge_cli", None)
        if cli is None:
            try:
                cli = BridgeHookClient("Match Momentum")
            except Exception:
                cli = None
            self._bridge_cli = cli
        if cli is not None and cli.available():
            st = None
            try:
                st = cli.game_status()
            except Exception:
                st = None
            if st is not None:
                # the bridge answered — its answer is final (no local scan)
                if st.get("running") and st.get("pid"):
                    try:
                        pid = int(st["pid"])
                        base = int(str(st.get("base") or "0"), 16)
                    except Exception:
                        return None
                    if base:
                        return (str(st.get("name") or "FL_2026.exe"),
                                pid, base)
                return None
        for name in self.proc_names:
            try:
                pid = self._pid_finder(name)
            except Exception:
                pid = None
            if not pid:
                continue
            try:
                base = self._base_finder(pid, name)
            except Exception:
                base = None
            if base:
                return name, int(pid), int(base)
        return None

    def _connect(self, name: str, pid: int, base: int) -> bool:
        try:
            h = self.api.open_process(pid)
        except Exception:
            h = None
        if not h:
            return False
        self.proc_name, self.pid, self.base_addr = name, pid, base
        self.h_process = h
        self.connected = True
        # «when andtechnical note technical note technical note technical note technical note technical note‌technical note» — only technical note‌technical note OpenProcess technical note‌technical noteandtechnical note
        self._log_event("TEAM_CONNECT", pid=pid, proc=name, base=fmt_ptr(base))
        return True

    def _disconnect(self, reason: str):
        try:
            if self.h_process:
                self.api.close_handle(self.h_process)
        except Exception:
            pass
        self.h_process = None
        self.pid = None
        self.base_addr = None
        self.proc_name = None
        was = self.connected
        self.connected = False
        # technical note tool original: latest technical note valid technical note technical note‌technical noteandtechnical note (technical note technical note technical note‌technical noteandtechnical note)
        if was:
            self._log_event("TEAM_DISCONNECT", reason=reason)

    def close(self):
        self._disconnect("app-close")

    # ---------------- read memory (technical note tool original) ----------------
    def _read_u8(self, addr: int) -> Optional[int]:
        b = self.api.read(self.h_process, addr, 1)
        return b[0] if b else None

    def _read_i32(self, addr: int) -> Optional[int]:
        b = self.api.read(self.h_process, addr, 4)
        if b and len(b) == 4:
            return struct.unpack("<i", b)[0]
        return None

    def _read_u64(self, addr: int) -> Optional[int]:
        b = self.api.read(self.h_process, addr, 8)
        if b and len(b) == 8:
            return struct.unpack("<Q", b)[0]
        return None

    def _resolve_chain(self, start_addr: int, offsets) -> Optional[int]:
        """exactly text resolve_pointer_chain tool original (text text
        «if not curr» for text/readtext failed)."""
        try:
            curr = self._read_u64(start_addr)
            if not curr:
                return None
            for i, off in enumerate(offsets):
                target = curr + off
                if i == len(offsets) - 1:
                    return target
                curr = self._read_u64(target)
                if not curr:
                    return None
            return None
        except Exception:
            return None

    def _resolve_chain_u32(self, start_addr: int, offsets) -> Optional[int]:
        """[PT v2.3.2] text _resolve_chain andtext deref text «4 bytetext» — text text
        text user («pointer 4 bytetext» text «text textand address 4 byte text»). read
        8 bytetext 4 bytetext aftertext textandtext text to‌textandtext dword withtext text and address‌text
        text broken text‌text (text «team‌text text text‌textandtext» in test text). text
        text exactly text is."""
        try:
            curr = self._read_u32(start_addr)
            if not curr:
                return None
            for i, off in enumerate(offsets):
                target = (curr + off) & 0xFFFFFFFF
                if i == len(offsets) - 1:
                    return target
                curr = self._read_u32(target)
                if not curr:
                    return None
            return None
        except Exception:
            return None

    def _pt_chain_diag(self, msg: str, force: bool = False):
        """[PT v2.3.2] log detectiontext text chain (textandtext TEAM_PT_CHAIN) —
        text‌text: text message text text 3 second text‌withtext (force for successfultext)."""
        now = time.monotonic()
        if not force and msg == self._pt_diag_last["msg"] \
                and now - self._pt_diag_last["t"] < 3.0:
            return
        if not force and now - self._pt_diag_last["t"] < 0.5:
            return
        self._pt_diag_last["t"] = now
        self._pt_diag_last["msg"] = msg
        try:
            self._log_event("TEAM_PT_CHAIN", msg=msg)
        except Exception:
            pass

    def _read_team_ids_pt(self) -> Optional[Tuple[int, int]]:
        """[PT v2.3.0/v2.3.2] (home_id, away_id) with chaintext user:
        [[base+0x03705E20]+0x98]+0x228 ⇒ 4 byte Hometext +4 Away.
        [v2.3.2] pointertext chain «4 bytetext» textandtext text‌textandtext (text user) —
        textfromtext‌text text user: Home @6E948708 and Away @6E94870C text
        Away = address Home + 4 byte (text +1) and text textand value 4 bytetext‌text.
        if path 4 bytetext textwithtext text path 8 bytetext text fallback text‌textandtext
        text textand path same textwithtextagetext textuntiltext PT text text (textwithtext memory team
        text‌textfromtext) and text andtext text textandtext TEAM_PT_CHAIN text‌text text‌textandtext."""
        if self.pt is None or not self.h_process or not self.base_addr:
            return None
        try:
            for deref, tag in ((self._resolve_chain_u32, "u32"),
                               (self._resolve_chain, "u64")):
                final = deref(self.base_addr + TEAM_ID_PTR_OFFSET,
                              TEAM_ID_CHAIN)
                if final is None:
                    self._pt_chain_diag(
                        f"{tag}: chain resolve failed")
                    continue
                home = self._read_u32(final)
                # Away = address Home + 4 byte (user: 6E948708 → 6E94870C)
                away = self._read_u32(final + 4)
                if home is None or away is None:
                    self._pt_chain_diag(
                        f"{tag}: id read failed at final={fmt_ptr(final)}")
                    continue
                home, away = int(home), int(away)
                if self.pt.has_team(home) and self.pt.has_team(away):
                    self._pt_chain_diag(
                        f"{tag}: OK final={fmt_ptr(final)} home={home} "
                        f"({self.pt.team_name(home)}) away={away} "
                        f"({self.pt.team_name(away)})", force=True)
                    return (home, away)
                self._pt_chain_diag(
                    f"{tag}: rejected final={fmt_ptr(final)} raw "
                    f"home={home} away={away} (not in PT db)")
            return None
        except Exception:
            return None

    def _read_u32(self, addr: int) -> Optional[int]:
        b = self.api.read(self.h_process, addr, 4)
        if b and len(b) == 4:
            return struct.unpack("<I", b)[0]
        return None

    def _read_side_ident(self, side: str) -> Optional[Tuple[int, int]]:
        """(league_id, image_id) or None. league must valid withtext and text text
        (league+1) in withtext 1..37 text andtext None (text newtext is not and
        display beforetext text tool original text text‌textandtext)."""
        try:
            lg_base_off, lg_chain = self.SIDE_CHAINS[side]["league"]
            lg_addr = self._resolve_chain(self.base_addr + lg_base_off, lg_chain)
            league = self._read_i32(lg_addr) if lg_addr is not None else None
            if league is None:
                return None
            sl_base_off, sl_chain = self.SIDE_CHAINS[side]["slots"]
            first = self._resolve_chain(self.base_addr + sl_base_off, sl_chain)
            img = None
            if first is not None:
                target_slot = league + 1
                if 1 <= target_slot <= TEAM_SLOT_COUNT:
                    img = self._read_i32(first + (target_slot - 1) * TEAM_SLOT_STRIDE)
            if img is None:
                return None
            return (int(league), int(img))
        except Exception:
            return None

    # ---------------- technical note original ----------------
    # versiontechnical note 10technical note6 — exactly technical note technical noteortechnical note user:
    #   * until when andtechnical note is nottechnical note «technical note 1 second» (technical note technical note outsidetechnical note) technical note technical note
    #   * to technical note technical note from same moment to after read technical note‌technical note «technical note‌untiltechnical note» is
    #     (technical note outsidetechnical note withtechnical note technical note technical noteandtechnical note 50ms technical note‌technical note — technical note realtime_loop tool
    #     original) and technical note technical note technical note technical note/technical note technical noteandtechnical note in technical note‌technical note healthy technical note
    #     technical note‌technical noteandtechnical note («when andtechnical note technical note technical note technical note technical note technical note‌technical note»). technical noteortechnical note technical noteandtechnical note only from
    #     technical note read memory technical note technical note‌technical noteandtechnical note: technical note read ⇒ technical note‌withtechnical note technical note confirmation.
    def poll(self) -> Dict[str, Any]:
        """text text complete:
          1) if andtext is nottext → text text (text text textandtext + OpenProcess).
          2) if andtext → only read memory (text‌untiltext)text text textandtext only in
             text read for detection text/textandtext textandtext text text‌textandtext.
          3) [PT v2.3.1] text PT: chaintext new in «text text» textandtext text‌textandtext
             andtext registertext detection only when menu = 9 is (text text in textand path)text
             text andtext‌text → text textandtext latest text valid.
          4) path legacy (without PT): andtext menu = 9 → read livetext text textand teamtext
             text andtext‌text → text textandtext latest text valid (text tool original).
          5) in text text text textand byte istext numbertext color text textandtext text‌textandtext.
        output: {"home": ident|None, "away": ident|None,
                "color_idx": {"home": int|None, "away": int|None},
                "connected": bool, "menu": int|None}"""
        if not self.connected:
            # --- only technical note (and in technical note read) technical noteandtechnical note technical note‌andtechnical noteand technical note‌technical noteandtechnical note ---
            found = None
            try:
                found = self._find_process()
            except Exception:
                found = None
            if found is None:
                return self._snapshot(None)
            if not self._connect(*found):
                return self._snapshot(None)

        # --- technical note: read technical note‌untiltechnical note (without technical note technical note in technical note healthy) ---
        try:
            menu = self._read_u8(self.base_addr + TEAM_MENU_STATE_OFFSET)
        except Exception:
            menu = None
        if menu is None:
            # technical note read ⇒ technical note‌withtechnical note check technical noteortechnical note technical noteandtechnical note (technical note only technical note)
            found = None
            try:
                found = self._find_process()
            except Exception:
                found = None
            if found is None:
                self._disconnect("process-gone")
                return self._snapshot(None)
            if (int(found[1]) != int(self.pid)) or (int(found[2]) != int(self.base_addr)):
                # technical noteandtechnical note technical note (withtechnical note restart‌technical note) → technical note to technical noteandtechnical note new
                self._disconnect("process-changed")
                if not self._connect(*found):
                    return self._snapshot(None)
                try:
                    menu = self._read_u8(self.base_addr + TEAM_MENU_STATE_OFFSET)
                except Exception:
                    menu = None
            # else: Errortechnical note technical note read — technical note healthy technical note technical note‌technical noteandtechnical note

        # --- [PT v2.3.1] technical note PT: chaintechnical note new in «technical note technical note» technical noteandtechnical note technical note‌technical noteandtechnical note
        #     technical note registertechnical note detection only when menu = 9 is (technical note path legacy — technical note technical note
        #     andtechnical note for total detection team)technical note technical note andtechnical note‌technical note ⇒ latest ID valid technical note‌technical note ---
        if self.pt is not None:
            if menu == TEAM_MENU_DETECT_VALUE:
                ids = self._read_team_ids_pt()
                if ids is not None and ids != self._pt_ids_last:
                    first = (self._pt_ids_last is None)
                    self._pt_ids_last = ids
                    self.ident["home"] = int(ids[0])
                    self.ident["away"] = int(ids[1])
                    self._log_event("TEAM_IDENT_PT", home=ids[0], away=ids[1],
                                    home_name=(self.pt.team_name(ids[0]) or ""),
                                    away_name=(self.pt.team_name(ids[1]) or ""))
                    if first:
                        self._log("PT team IDs detected: "
                                  f"{self.pt.team_name(ids[0])} vs {self.pt.team_name(ids[1])}")
            # menu != 9 ⇒ technical note registertechnical note technical note technical note‌technical noteandtechnical note (technical note — technical note path legacy)
            for side, off in (("home", TEAM_COLOR_IDX_OFFSET_HOME),
                              ("away", TEAM_COLOR_IDX_OFFSET_AWAY)):
                try:
                    self.color_idx[side] = self._read_u8(self.base_addr + off)
                except Exception:
                    self.color_idx[side] = None
            return self._snapshot(menu)

        if menu == TEAM_MENU_DETECT_VALUE:
            # menu = 9: read livetechnical note technical note technical noteand team (technical note only outside from 9 — technical note PT)
            for side in ("home", "away"):
                ident = self._read_side_ident(side)
                if ident is not None and ident != self.ident[side]:
                    self.ident[side] = ident
                    self._log_event("TEAM_IDENT", side=side, league=ident[0], img=ident[1])
        elif self.ident["home"] is None or self.ident["away"] is None:
            # v2.0.6 — in technical note: if technical noteandtechnical note never in menu 9 technical note technical note (technical note
            # andtechnical note withtechnical note)technical note technical note 2 second technical note technical note if chain‌technical note in
            # withtechnical note valid withtechnical note same technical note real technical note‌technical note andtechnical note None technical note‌technical note
            # (technical notereadtechnical note invalid technical noteandtechnical note technical note _read_side_ident technical note technical note‌technical noteandtechnical note).
            # without technical note technical note technical note team‌technical note (minutetechnical note first) never display data technical note‌technical note.
            now = time.time()
            if now - self._rescue_last >= 2.0:
                self._rescue_last = now
                for side in ("home", "away"):
                    if self.ident[side] is not None:
                        continue
                    ident = self._read_side_ident(side)
                    if ident is not None and ident != self.ident[side]:
                        self.ident[side] = ident
                        self._log_event("TEAM_IDENT_RESCUE", side=side,
                                        league=ident[0], img=ident[1])
        # menu != 9 or read failed → technical note: latest technical note valid technical note‌technical note

        # --- versiontechnical note 10technical note6: numbertechnical note color technical note technical noteand team (istechnical note — without technical note menu) ---
        for side, off in (("home", TEAM_COLOR_IDX_OFFSET_HOME),
                          ("away", TEAM_COLOR_IDX_OFFSET_AWAY)):
            try:
                self.color_idx[side] = self._read_u8(self.base_addr + off)
            except Exception:
                self.color_idx[side] = None
        return self._snapshot(menu)

    def _snapshot(self, menu) -> Dict[str, Any]:
        return {"home": self.ident["home"], "away": self.ident["away"],
                "color_idx": {"home": self.color_idx["home"],
                              "away": self.color_idx["away"]},
                "connected": self.connected, "menu": menu}

    def logo_path_for(self, ident) -> Optional[str]:
        """[PT v2.3.0] text PT: Asset.zip → Teams/{team_id}.png (path text)text
        path legacy: Football_Database/{league}/{img}.pngtext if textandtextandtext textandtext None
        (None text UI same textwithtext «Home/Away» text text text)."""
        if not ident:
            return None
        if self.pt is not None and isinstance(ident, int):
            try:
                return self.pt.team_logo_path(int(ident))
            except Exception:
                return None
        try:
            league, img = ident
            if league is None or img is None:
                return None
            path = os.path.join(self.db_dir, str(int(league)), f"{int(img)}.png")
            return path if os.path.isfile(path) else None
        except Exception:
            return None

    # ---------------- log (in same momentum_debug_log.txt) ----------------
    def _log_event(self, tag: str, **kv):
        if self.logger is not None:
            try:
                self.logger.event(tag, **kv)
            except Exception:
                pass

    def _log(self, msg: str):
        if self.logger is not None:
            try:
                self.logger.write("TEAM", msg)
            except Exception:
                pass


# =====================================================================
# 26-technical note — technical note color chart from leagues_data.json (versiontechnical note 10technical note6technical note path 10technical note9)
# ---------------------------------------------------------------------
# source color: file leagues_data.json inside foldertechnical note «Football_Database» technical note
# technical note (if technical note technical noteandtechnical note versiontechnical note technical note technical note technical note check technical note‌technical noteandtechnical note technical note data‌technical note from
# inside code technical notecode technical note‌technical noteandtechnical note). structure: { league_id: { "teams": { team_id:
# { "colors": {"Color 0": [r,g,b], "Color 1": ..., ...} } } } } technical note
# r/g/b decimaltechnical note 0..1 is (value real ÷ 255 ⇒ for color original ×255).
#
# numbertechnical note colortechnical note technical note team from technical noteand byte istechnical note 1 technical note technical noteandtechnical note technical note‌technical noteandtechnical note:
#   Home: base + 0x36F5198   (technical note: 0x1436F5198)
#   Away:  base + 0x36F51A0   (technical note: 0x1436F51A0)
# value technical note byte exactly technical note color is (from technical note start technical note‌technical noteandtechnical note).
#
# technical noteandtechnical note technical note (technical note specification user):
#   1) if numbertechnical note color from count color‌technical note technical note‌technical note technical note technical noteandtechnical note (technical note 2 when
#      technical note‌technical note numbertechnical note team 1 is) ⇒ latest color technical noteandtechnical noteandtechnical note istechnical note technical note‌technical noteandtechnical note.
#   2) color technical noteortechnical note/technical note technical note technical note technical noteandtechnical note technical note‌pitchtechnical note untiltechnical note chart technical noteandtechnical note technical note technical note‌technical noteandtechnical note
#      ⇒ with colortechnical note fallback technical note‌technical noteandtechnical note technical note technical note with technical note‌pitchtechnical note technical note with color team technical note
#      technical noteis technical note withtechnical note.
#   3) if color technical noteand team technical note technical note technical noteandtechnical note (technical noteis technical note) ⇒ color «Away» technical noteandtechnical note
#      technical note‌technical noteandtechnical note (with technical noteis technical note ratio to technical note‌pitchtechnical note and color Home).
#   4) technical note technical note team always technical note technical note (color technical note chart)technical note currentlytechnical note‌technical note 2 and 3
#      technical noteand technical note: color original + color technical noteandtechnical note (render in MomentumApp).
#   5) if technical note‌codetechnical note color technical note ⇒ technical note technical note/technical note if only technical note technical note ⇒
#      for team technical note technical note‌colortechnical note automatic colortechnical note technical note‌technical noteis technical note technical note‌technical noteandtechnical note.
#   6) technical note file decimaltechnical note 0..1 is (÷255) ⇒ in technical note in 255 technical note technical note‌technical noteandtechnical note.
# untiltechnical note resolve completetechnical note pure is (without memory/TK) and for test technical noteandtechnical note withtechnical note is.
# =====================================================================

DEFAULT_HOME_CHART_COLOR = (230, 57, 70)    # ‎#e63946 — technical note always‌beforetechnical note Home
DEFAULT_AWAY_CHART_COLOR = (245, 245, 245)  # ‎#f5f5f5 — technical note always‌beforetechnical note Away
CHART_PANEL_BG_RGB = (17, 26, 43)           # ‎#111a2b — technical note‌pitchtechnical note technical note chart

# technical noteandtechnical note technical note (firsttechnical note colortechnical note technical note‌technical noteandtechnical note technical note technical note‌technical noteandtechnical note order = technical note):
# Home with technical note start technical note‌technical noteandtechnical note Away with technical note — until currentlytechnical note‌technical note automatic until
# technical note technical note same technical note totaltechnical note technical note/technical note technical note technical noteandtechnical note.
TEAM_COLOR_HOME_PREF = ('#e63946', '#ff8c42', '#ffd166', '#4cc9f0',
                        '#a3e635', '#f5f5f5', '#ff5d8f')
TEAM_COLOR_AWAY_PREF = ('#f5f5f5', '#4cc9f0', '#ffd166', '#a3e635',
                        '#ff9f1c', '#ff5d8f', '#c77dff')


def _hex_to_rgb(hx: str) -> Tuple[int, int, int]:
    hx = (hx or "").lstrip("#")
    if len(hx) != 6:
        return (255, 255, 255)
    try:
        return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))
    except Exception:
        return (255, 255, 255)


def _rgb_to_hex(rgb) -> str:
    try:
        r, g, b = (max(0, min(255, int(round(float(c))))) for c in rgb)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return "#ffffff"


def _relative_luminance(rgb) -> float:
    """textandtext text WCAG (0..1) — for agetext textis real with text‌pitchtext."""
    def _lin(c):
        c = max(0.0, min(1.0, c / 255.0))
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(rgb[0]), _lin(rgb[1]), _lin(rgb[2]))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(rgb_a, rgb_b) -> float:
    """ratio textis WCAG (1..21) — textortext «text‌text textandtext text‌pitchtext»."""
    la, lb = _relative_luminance(rgb_a), _relative_luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _rgb_distance(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class TeamColorResolver:
    """
    versiontext 10text6 — text‌text color fill chart for Home/Away.

    input‌text from TeamIdentityTracker text‌text:
      * ident text team = (league_id, image_id)  — totaltext text‌andtextand in JSON
      * idx text team = byte istext numbertext color (or None if textandtext text)
    output resolve: for text team
      {"final": (r,g,b),        # color text text chart
       "original": (r,g,b)|None, # color originaltext text‌text from file (None = from file textandtext)
       "replaced": bool}         # True ⇒ textand text (original + textandtext) text team
    file JSON with text text text mtime textandtext text‌textandtext ⇒ if user file text andtext
    text without restart text text text‌textandtext.
    """

    # technical note technical noteis technical note‌technical noteandtechnical note with technical note‌pitchtechnical note technical note (WCAG) — technical note technical note «untiltechnical note» technical note
    # technical note‌technical noteandtechnical note (technical note ≈ 0.8 technical note technical note‌technical note ≈ 1.0 technical note technical note technical note ≈ 1.7 technical note technical note technical note ≈ 4.2)
    MIN_CONTRAST_BG = 2.0
    # technical note distancetechnical note technical notefrom technical note color technical noteand team (distancetechnical note RGB in 0..441 and technical note technical noteandtechnical note)
    MIN_RGB_DIST_OPPONENT = 90.0
    MIN_LUM255_DIFF_OPPONENT = 30.0
    # color fallback must from color originaltechnical note technical noteandtechnical note‌technical note technical note to‌technical notein technical note technical noteandtechnical note withtechnical note
    MIN_RGB_DIST_FROM_ORIGINAL = 60.0

    def __init__(self, json_path: Optional[str] = None, logger=None, pt=None):
        # versiontechnical note 10technical note9 — path default: foldertechnical note Football_Database technical note technical note
        # if technical note technical noteandtechnical note path legacy (technical note technical note) technical note check technical note‌technical noteandtechnical note.
        # [PT v2.3.0] if PT active withtechnical note color‌technical note from teams_players_PES2021.txt
        # technical note‌technical note (RGB technical noteandtechnical note original) and JSON only fallback is.
        self.pt = pt if (pt is not None and pt.available()) else None
        self.json_path = json_path          # None = technical note automatic from technical note
        self.logger = logger
        self._cache = None            # latest JSON healthy
        self._cache_mtime = None
        self._active_path = None      # path file active latest read
        self._failed_mtime = None     # for «only technical note‌withtechnical note» log‌technical note file broken
        self._logged_loaded = False
        self._logged_missing = False

    # ---------------- file leagues_data.json ----------------
    def _log(self, msg: str):
        if self.logger is not None:
            try:
                self.logger.write("TEAMCOLOR", msg)
            except Exception:
                pass

    def _resolve_json_path(self) -> Optional[str]:
        """versiontext 10text9 — text file leagues_data.json:
        firstandtext 1: Football_Database/leagues_data.json text text
        firstandtext 2: leagues_data.json text text (textfromtext with version‌text before)
        path text data‌text (json_path) always firstandtext text."""
        if self.json_path:
            return self.json_path
        for cand in team_json_candidates():
            try:
                os.path.getmtime(cand)
                return cand
            except OSError:
                continue
        return None

    def _data(self) -> Optional[dict]:
        """read file with text mtimetext file textandtext/broken textandtext ⇒ None (text‌text)."""
        path = self._resolve_json_path()
        if path is None:
            if not self._logged_missing:
                self._logged_missing = True
                self._log("leagues_data.json text text (Football_Database/ and text "
                          "text) — color‌text default text/text istext text‌textandtext")
            self._cache, self._cache_mtime = None, None
            return None
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            self._cache, self._cache_mtime = None, None
            return None
        if self._cache is not None and self._cache_mtime == mtime \
                and self._active_path == path:
            return self._cache
        self._active_path = path
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("root of leagues_data.json is not a dict")
            self._cache = data
            self._cache_mtime = mtime
            if not self._logged_loaded:
                n_teams = sum(len((v or {}).get("teams") or {}) for v in data.values())
                self._log(f"leagues_data.json withtext text from {path}: "
                          f"leagues={len(data)} teams={n_teams}")
                self._logged_loaded = True
        except Exception as ex:
            # file broken ⇒ until change mtime again technical note technical note (only technical note‌withtechnical note log)
            if self._failed_mtime != mtime:
                self._failed_mtime = mtime
                self._log(f"Error in leagues_data.json ({type(ex).__name__}: {ex}) — "
                          f"color‌text default text/text istext text‌textandtext")
            self._cache, self._cache_mtime = None, mtime
        return self._cache

    @staticmethod
    def _parse_colors(raw) -> List[Tuple[int, int, int]]:
        """{"Color 0": [f,f,f], ...} → [(r,g,b), ...] with text 0 text (×255)."""
        out: List[Tuple[int, int, int]] = []
        if not isinstance(raw, dict):
            return out

        def _key_num(k):
            try:
                return int(str(k).strip().split()[-1])
            except Exception:
                return None

        items = []
        for k, v in raw.items():
            if not isinstance(v, (list, tuple)) or len(v) < 3:
                continue
            try:
                rgb = tuple(max(0, min(255, int(round(float(v[ch]) * 255.0))))
                            for ch in range(3))
            except Exception:
                continue
            items.append((_key_num(k), rgb))
        numbered = sorted((it for it in items if it[0] is not None), key=lambda it: it[0])
        unnumbered = [it for it in items if it[0] is None]
        out.extend(rgb for _, rgb in numbered)
        out.extend(rgb for _, rgb in unnumbered)
        return out

    def team_colors(self, ident) -> List[Tuple[int, int, int]]:
        """color‌text text‌text team — [PT v2.3.0] text PT (ident = int Team ID):
        from teams_players_PES2021.txt (numbertext color = text text)text path legacy
        (league, team) from JSONtext unknown ⇒ []"""
        if not ident:
            return []
        if self.pt is not None and isinstance(ident, int):
            try:
                cols = self.pt.team_colors(int(ident))
                return [(int(c[0]), int(c[1]), int(c[2])) for c in cols
                        if c and len(c) >= 3]
            except Exception:
                return []
        try:
            league, team = int(ident[0]), int(ident[1])
        except Exception:
            return []
        data = self._data()
        if not data:
            return []
        try:
            lnode = data.get(str(league)) or {}
            tnode = (lnode.get("teams") or {}).get(str(team))
            if not tnode:
                return []
            return self._parse_colors(tnode.get("colors"))
        except Exception:
            return []

    # ---------------- technical noteandtechnical note 1 until 6 ----------------
    @staticmethod
    def _pick_by_index(colors, idx) -> Optional[Tuple[int, int, int]]:
        """rule 1 — text from memorytext None ⇒ color firsttext text from withtext ⇒ latest color."""
        if not colors:
            return None
        i = 0 if idx is None else int(idx)
        if i < 0:
            i = 0
        if i >= len(colors):
            i = len(colors) - 1
        return colors[i]

    @classmethod
    def _too_dark_on_bg(cls, rgb) -> bool:
        """rule 2 — textortext/text text textandtext text‌pitchtext untiltext chart."""
        return _contrast_ratio(rgb, CHART_PANEL_BG_RGB) < cls.MIN_CONTRAST_BG

    @classmethod
    def _too_similar(cls, a, b) -> bool:
        """rule 3 — textand color to‌text text‌text (textis text)."""
        return (_rgb_distance(a, b) < cls.MIN_RGB_DIST_OPPONENT
                or abs(_relative_luminance(a) * 255.0 - _relative_luminance(b) * 255.0)
                < cls.MIN_LUM255_DIFF_OPPONENT)

    @classmethod
    def _pick_color(cls, candidates, original, opponent) -> Tuple[int, int, int]:
        """firsttext text text: with text‌pitchtext textis text withtext from color original
        (textandtext‌textandtext) and color text to‌textin text textandtext withtext andtext totext."""
        for hx in candidates:
            c = _hex_to_rgb(hx)
            if original is not None and _rgb_distance(c, original) < cls.MIN_RGB_DIST_FROM_ORIGINAL:
                continue
            if cls._too_dark_on_bg(c):
                continue
            if opponent is not None and cls._too_similar(c, opponent):
                continue
            return c
        # technical note technical note technical note‌technical note technical note complete technical note ⇒ technical note‌distance‌technical note (technical note technical note distance)
        best, best_score = None, -1.0
        for hx in candidates:
            c = _hex_to_rgb(hx)
            score = _contrast_ratio(c, CHART_PANEL_BG_RGB) * 40.0
            if original is not None:
                score = min(score, _rgb_distance(c, original))
            if opponent is not None:
                score = min(score, _rgb_distance(c, opponent),
                            abs(_relative_luminance(c) - _relative_luminance(opponent)) * 255.0 * 2.0)
            if score > best_score:
                best, best_score = c, score
        return best if best is not None else _hex_to_rgb(candidates[0])

    def resolve(self, home_ident, home_idx, away_ident, away_idx) -> Dict[str, Dict[str, Any]]:
        """text complete textandtext 1..6 — pure and without impact text."""
        home_cols = self.team_colors(home_ident)
        away_cols = self.team_colors(away_ident)
        h_base = self._pick_by_index(home_cols, home_idx)
        a_base = self._pick_by_index(away_cols, away_idx)

        h_final, a_final = h_base, a_base
        # rule 2 — color technical note technical note ⇒ technical noteandtechnical note (with intechnical note color technical note)
        if h_final is not None and self._too_dark_on_bg(h_final):
            h_final = self._pick_color(TEAM_COLOR_HOME_PREF, h_final, a_final)
        if a_final is not None and self._too_dark_on_bg(a_final):
            a_final = self._pick_color(TEAM_COLOR_AWAY_PREF, a_final, h_final)
        # rule 5 — teamtechnical note without color ⇒ automatic colortechnical note technical note‌technical noteis (technical note firsttechnical note technical note)
        if h_final is None:
            h_final = self._pick_color(
                (_rgb_to_hex(DEFAULT_HOME_CHART_COLOR),) + TEAM_COLOR_HOME_PREF,
                None, a_final)
        if a_final is None:
            a_final = self._pick_color(
                (_rgb_to_hex(DEFAULT_AWAY_CHART_COLOR),) + TEAM_COLOR_AWAY_PREF,
                None, h_final)
        # rule 3 — technical noteand color technical note ⇒ only color Away technical noteandtechnical note technical note‌technical noteandtechnical note
        if self._too_similar(h_final, a_final):
            a_final = self._pick_color(TEAM_COLOR_AWAY_PREF, a_final, h_final)

        return {
            "home": {"final": h_final, "original": h_base,
                     "replaced": (h_base is not None and h_final != h_base)},
            "away": {"final": a_final, "original": a_base,
                     "replaced": (a_base is not None and a_final != a_base)},
        }



# =============================================================================
# Headless base — replaces tk.Tk. Provides after()-timers on a daemon thread,
# screen metrics via WinAPI and a UI-absorber so the few remaining legacy
# UI-touching lines can never raise or open a window.
# =============================================================================
class _UIAbsorber(object):
    """Accepts any attribute access / call without doing anything."""
    def _absorb(self, *a, **k):
        return self
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return self._absorb
    def __call__(self, *a, **k):
        return self
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False
    def __bool__(self):
        return False
    def __iter__(self):
        return iter(())
    def __nonzero__(self):
        return False


class _HeadlessTkBase(object):
    """Minimal tk.Tk replacement: after()/after_cancel() timers driven by a
    daemon thread, WinAPI screen metrics, no window is ever created."""

    def __init__(self):
        self._after_seq = 0
        self._after_jobs = {}
        self._after_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._after_thread = threading.Thread(target=self._after_loop,
                                              daemon=True, name="after-timer")
        self._after_thread.start()

    # --- timer loop -------------------------------------------------------
    def _after_loop(self):
        while not self._stop_event.is_set():
            now = time.perf_counter()
            due = []
            with self._after_lock:
                for aid in list(self._after_jobs.keys()):
                    run_at, fn, args = self._after_jobs[aid]
                    if now >= run_at:
                        del self._after_jobs[aid]
                        due.append((fn, args))
            for fn, args in due:
                try:
                    fn(*args)
                except Exception:
                    pass
            self._stop_event.wait(0.005)

    def after(self, ms, func=None, *args):
        with self._after_lock:
            self._after_seq += 1
            aid = self._after_seq
            self._after_jobs[aid] = (time.perf_counter() + max(0, ms) / 1000.0,
                                     func, args)
        return aid

    def after_cancel(self, aid):
        with self._after_lock:
            self._after_jobs.pop(aid, None)

    # --- screen metrics -----------------------------------------------------
    @staticmethod
    def _screen_size():
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                return (int(user32.GetSystemMetrics(0)),
                        int(user32.GetSystemMetrics(1)))
            except Exception:
                pass
        return 1920, 1080

    def winfo_screenwidth(self):
        return self._screen_size()[0]

    def winfo_screenheight(self):
        return self._screen_size()[1]

    # --- window API stubs ---------------------------------------------------
    def winfo_exists(self):
        return not self._stop_event.is_set()
    def update_idletasks(self):
        pass
    def update(self):
        pass
    def destroy(self):
        self._stop_event.set()
    def mainloop(self, *a, **k):
        self.run_forever()
    def run_forever(self):
        """v2.1.0 — GUI build: run the real Tk mainloop (the window starts
        hidden; Alt+Ctrl+Y toggles it). Headless build: block until
        on_close()/destroy()/terminate()."""
        self.run_forever_called = True
        if getattr(self, "_gui_active", False) or hasattr(self, "tk"):
            try:
                self.mainloop()
            except Exception:
                pass
            return
        self._stop_event.wait()
    def protocol(self, *a, **k):
        pass
    def title(self, *a, **k):
        pass
    def geometry(self, *a, **k):
        pass
    def minsize(self, *a, **k):
        pass
    def configure(self, *a, **k):
        pass
    def bind(self, *a, **k):
        pass

    def __getattr__(self, name):
        # UI widget attributes are never built in the headless build; every
        # remaining reference resolves to a no-op absorber instead of raising.
        if name.startswith("_"):
            raise AttributeError(name)
        absorber = _UIAbsorber()
        try:
            object.__setattr__(self, name, absorber)
        except Exception:
            pass
        return absorber


# =============================================================================
# Match Momentum settings — read from ModsConfig.json (mods -> Match Momentum).
# The frontend (MyMods.py) writes this block; ModBridge.py starts this backend
# only when the mod is enabled. Unknown/missing keys fall back to defaults.
# =============================================================================
MODS_CONFIG_FILENAME = "ModsConfig.json"
MOM_SETTINGS_KEYMAP = {
    "mm_h1_enabled": "h1_enabled",     "mm_h1_minute": "h1_minute",
    "mm_h2_enabled": "h2_enabled",     "mm_h2_minute": "h2_minute",
    "mm_et_enabled": "et_enabled",     "mm_et_minute": "et_minute",
    "mm_show_seconds": "show_seconds",
    "mm_end_enabled": "end_enabled",   "mm_end_seconds": "end_seconds",
    "mm_permanent_save": "permanent_save",
    "mm_timestamp": "timestamp",
    # NEW (user request): permanently save EVERY chart prepared for display
    # (h1/h2/et + end-of-match), not just the last chart of the match.
    "mm_save_shown_charts": "save_shown_charts",
}


def mom_load_settings():
    """v2.1.0 — TV snapshot settings, two layers: the ORIGINAL GUI settings
    dialog file (momentum_settings.json, written by the restored ⚙ dialog)
    is the base; ModsConfig.json mm_* keys (frontend) override it."""
    s = dict(TV_SNAP_DEFAULTS)
    try:
        _base = snap_load_settings(_MOMENTUM_DATA_DIR)
        if isinstance(_base, dict):
            s.update(_base)
    except Exception:
        pass
    try:
        path = os.path.join(_MOMENTUM_DATA_DIR,
                            "..", MODS_CONFIG_FILENAME)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            mc = (cfg or {}).get("mods", {}).get("Match Momentum", {}) or {}
            if isinstance(mc, dict):
                for src_key, dst_key in MOM_SETTINGS_KEYMAP.items():
                    if src_key in mc:
                        s[dst_key] = mc[src_key]
    except Exception:
        pass
    for key in TV_SNAP_KEYS:
        s[f"{key}_minute"] = snap_clamp_minute(key, s.get(f"{key}_minute"))
        s[f"{key}_enabled"] = bool(s.get(f"{key}_enabled"))
    s["show_seconds"] = snap_clamp_seconds(s.get("show_seconds"))
    s["end_seconds"] = snap_clamp_seconds(s.get("end_seconds"))
    s["end_enabled"] = bool(s.get("end_enabled"))
    s["permanent_save"] = bool(s.get("permanent_save"))
    s["timestamp"] = bool(s.get("timestamp"))
    s["save_shown_charts"] = bool(s.get("save_shown_charts"))
    return s


def acquire_single_instance():
    """One momentum backend per Windows session (named mutex)."""
    if sys.platform != "win32":
        return True
    try:
        mutex = ctypes.windll.kernel32.CreateMutexW(None, False,
                                                    "PES_MatchMomentum_SingleInstance")
        return bool(mutex) and ctypes.windll.kernel32.GetLastError() != 183
    except Exception:
        return True

_MOM_BASE = tk.Tk if (MOM_GUI_REQUESTED and tk is not None) else _HeadlessTkBase


