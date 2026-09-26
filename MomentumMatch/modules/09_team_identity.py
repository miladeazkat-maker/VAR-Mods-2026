class _TeamWinAPI:
    """لایهٔ نازک WinAPI — فقط خواندن (معادل read_uint8/read_int32/read_uint64
    ابزار اصلی که اینجا روی safe_read سوار شده‌اند). برای تست مصنوعی، کاملاً
    قابل جای‌گذاری است (api=...)."""

    def open_process(self, pid: int):
        return kernel32.OpenProcess(TEAM_PROCESS_ACCESS, False, pid)

    def close_handle(self, h_process):
        kernel32.CloseHandle(h_process)

    def read(self, h_process, addr: int, size: int) -> Optional[bytes]:
        return safe_read(h_process, addr, size)


class TeamIdentityTracker:
    """
    نسخه ۱۰٫۵ — خوانندهٔ مستقل هویت تیم میزبان/مهمان برای اسلات‌های لوگو.

    ورودی خواندن (عین ابزار اصلی):
      * بایت وضعیت منو:   base + 0x36F9AE0  (uint8)  — فقط ۹ ⇒ تشخیص تیم
      * لیگ میزبان:       resolve(base+0x37F89D8, [0x40, 0xA0, 0x118]) → int32
      * اسلات‌های میزبان: resolve(base+0x36F9C10, [0x8, 0x0, 0x100, 0x64]) + i*112
      * لیگ مهمان:        resolve(base+0x36F9C10, [0xC8, 0x118]) → int32
      * اسلات‌های مهمان:  resolve(base+0x36F9C10, [0xC8, 0x100, 0x64]) + i*112
        (i = 0..36 — اسلات هدف = league_id + 1 — تصویر = Football_Database/{league}/{value}.png)
    resolve دقیقاً مثل resolve_pointer_chain ابزار اصلی است: اول deref آدرس
    شروع، بعد برای هر آفست به‌جز آخری deref؛ آخری فقط جمع می‌شود.

    خروجی: ident هر تیم = (league_id, image_id) یا None.
    None یعنی «هنوز انتخاب معتبری دیده نشده» → UI همان عبارت «میزبان/مهمان»
    را نشان می‌دهد (نیاز صریح کاربر).
    """

    # زنجیرهٔ پوینترها — عین ابزار اصلی
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
        self.db_dir = db_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                             TEAM_DB_DIRNAME)
        self.logger = logger
        self.proc_names = tuple(proc_names)
        self.api = api or _TeamWinAPI()
        self._pid_finder = pid_finder or get_pid_by_name
        self._base_finder = base_finder or get_module_base
        # [PT v2.3.0] منبع دادهٔ PT (تیم‌ها/رنگ‌ها/لوگو) — None یعنی مسیر قدیمی
        self.pt = pt if (pt is not None and pt.available()) else None
        self.h_process = None
        self.pid: Optional[int] = None
        self.base_addr: Optional[int] = None
        self.proc_name: Optional[str] = None
        self.connected = False
        # آخرین انتخاب معتبرِ قابل‌نمایش هر تیم:
        #   PT mode → int Team ID ؛ مسیر قدیمی → (league_id, image_id)
        self.ident = {"home": None, "away": None}
        # [PT v2.3.0] آخرین جفت ID خوانده‌شده با زنجیرهٔ جدید
        self._pt_ids_last = None
        # [PT v2.3.2] کنترل‌ساز لاگ تشخیصی زنجیره (TEAM_PT_CHAIN)
        self._pt_diag_last = {"t": 0.0, "msg": None}
        # v2.0.6 — اگر هویت هرگز در منو ۹ دیده نشده باشد (اتصالِ وسط بازی)،
        # هر ۲ ثانیه یک تلاشِ «نجات» می‌شود؛ گاردهای اعتبارسنجیِ
        # _read_side_ident همان‌اند (لیگ ۰..۳۵ + اسلات ۱..۳۷)
        self._rescue_last = 0.0
        # نسخهٔ ۱۰٫۶ — شمارهٔ رنگ هر تیم از دو بایت استاتیک (base+0x36F5198/A0)؛
        # آدرس‌ها استاتیک‌اند و تغییر نمی‌کنند ⇒ در «هر تیکِ متصل» خوانده می‌شوند
        # (بدون قفل وضعیت منو). None یعنی خواندن این تیک ناموفق بوده.
        self.color_idx = {"home": None, "away": None}

    # ---------------- اتصال (مستقل از کد اصلی) ----------------
    def _find_process(self):
        """مثل attach_process ابزار اصلی: پیدا کردن pid + آدرس پایهٔ ماژول.
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
        # «وقتی وصل شد دیگر دست نگه می‌دارد» — فقط همین‌جا OpenProcess می‌شود
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
        # مثل ابزار اصلی: آخرین انتخاب معتبر حفظ می‌شود (اسلات پاک نمی‌شود)
        if was:
            self._log_event("TEAM_DISCONNECT", reason=reason)

    def close(self):
        self._disconnect("app-close")

    # ---------------- خواندن حافظه (عین ابزار اصلی) ----------------
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
        """دقیقاً مثل resolve_pointer_chain ابزار اصلی (شامل معنای
        «if not curr» برای صفر/خواندنِ ناموفق)."""
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
        """[PT v2.3.2] مثل _resolve_chain ولی deref های «۴ بایتی» — طبق تأکید
        صریح کاربر («پوینتر ۴ بایتی» ، «هر دو آدرس ۴ بایت هستند»). خواندن
        ۸ بایتی، ۴ بایتِ بعدیِ سلول را به‌عنوان dword بالا بلعیده و آدرس‌ها
        را خراب می‌کند (دلیلِ «تیم‌ها پیدا نمی‌شوند» در تست میدانی). بقیهٔ
        معنا دقیقاً یکسان است."""
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
        """[PT v2.3.2] لاگ تشخیصی میدانی زنجیره (رویداد TEAM_PT_CHAIN) —
        کنترل‌شده: هر پیام حداکثر هر ۳ ثانیه یک‌بار (force برای موفقیت)."""
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
        """[PT v2.3.0/v2.3.2] (home_id, away_id) با زنجیرهٔ کاربر:
        [[base+0x03705E20]+0x98]+0x228 ⇒ ۴ بایت میزبان، +۴ مهمان.
        [v2.3.2] پوینترهای زنجیره «۴ بایتی» خوانده می‌شوند (تأکید کاربر) —
        اندازه‌گیری میدانی کاربر: میزبان @6E948708 و مهمان @6E94870C یعنی
        مهمان = آدرس میزبان + ۴ بایت (نه +۱) و هر دو مقدار ۴ بایتی‌اند.
        اگر مسیر ۴ بایتی اعتبار نگشت، مسیر ۸ بایتیِ قدیم fallback می‌شود؛
        هر دو مسیر همان اعتبارسنجی دیتابیس PT را دارند (زبالهٔ حافظه تیم
        نمی‌سازد) و هر وضعیت یک رویداد TEAM_PT_CHAIN کنترل‌شده می‌نویسد."""
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
                # مهمان = آدرس میزبان + ۴ بایت (کاربر: 6E948708 → 6E94870C)
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
        """(league_id, image_id) یا None. league باید معتبر باشد و اسلات هدف
        (league+1) در بازهٔ 1..37 بیفتد؛ وگرنه None (انتخاب جدیدی نیست و
        نمایش قبلی مثل ابزار اصلی حفظ می‌شود)."""
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

    # ---------------- تیک اصلی ----------------
    # نسخهٔ ۱۰٫۶ — دقیقاً طبق نیاز کاربر:
    #   * تا وقتی وصل نیستیم «هر ۱ ثانیه» (زیرکنترل حلقهٔ بیرونی) تلاش اتصال؛
    #   * به محض اتصال، از همان لحظه به بعد خواندن اسلات‌ها «ریل‌تایم» است
    #     (حلقهٔ بیرونی بازه را روی ۵۰ms می‌گذارد — مثل realtime_loop ابزار
    #     اصلی) و دیگر هیچ تلاش اتصالی/اسکن پروسه در تیک‌های سالم انجام
    #     نمی‌شود («وقتی وصل شد دیگر دست نگه می‌دارد»). حیات پروسه فقط از
    #     راه خواندن حافظه کنترل می‌شود: شکست خواندن ⇒ یک‌بار اسکن تأیید.
    def poll(self) -> Dict[str, Any]:
        """یک تیک کامل:
          ۱) اگر وصل نیستیم → تلاش اتصال (پیدا کردن پروسه + OpenProcess).
          ۲) اگر وصلیم → فقط خواندن حافظه (ریل‌تایم)؛ اسکن پروسه فقط در
             شکست خواندن برای تشخیص مرگ/تعویض پروسه انجام می‌شود.
          ۳) [PT v2.3.1] حالت PT: زنجیرهٔ جدید در «هر تیک» خوانده می‌شود،
             ولی ثبتِ تشخیص فقط وقتی منو = ۹ است (قفل یکسان در دو مسیر)؛
             بقیهٔ وضعیت‌ها → قفل روی آخرین انتخاب معتبر.
          ۴) مسیر قدیمی (بدون PT): وضعیت منو = ۹ → خواندن زندهٔ هر دو تیم؛
             بقیهٔ وضعیت‌ها → قفل روی آخرین انتخاب معتبر (مثل ابزار اصلی).
          ۵) در هر تیکِ متصل، دو بایت استاتیک شمارهٔ رنگ هم خوانده می‌شود.
        خروجی: {"home": ident|None, "away": ident|None,
                "color_idx": {"home": int|None, "away": int|None},
                "connected": bool, "menu": int|None}"""
        if not self.connected:
            # --- فقط اینجا (و در شکست خواندن) پروسه جست‌وجو می‌شود ---
            found = None
            try:
                found = self._find_process()
            except Exception:
                found = None
            if found is None:
                return self._snapshot(None)
            if not self._connect(*found):
                return self._snapshot(None)

        # --- متصل: خواندن ریل‌تایم (بدون هیچ اسکن در تیک سالم) ---
        try:
            menu = self._read_u8(self.base_addr + TEAM_MENU_STATE_OFFSET)
        except Exception:
            menu = None
        if menu is None:
            # شکست خواندن ⇒ یک‌بار بررسی حیات پروسه (اسکن فقط اینجا)
            found = None
            try:
                found = self._find_process()
            except Exception:
                found = None
            if found is None:
                self._disconnect("process-gone")
                return self._snapshot(None)
            if (int(found[1]) != int(self.pid)) or (int(found[2]) != int(self.base_addr)):
                # پروسهٔ دیگری (بازی ری‌استارت‌شده) → اتصال به پروسهٔ جدید
                self._disconnect("process-changed")
                if not self._connect(*found):
                    return self._snapshot(None)
                try:
                    menu = self._read_u8(self.base_addr + TEAM_MENU_STATE_OFFSET)
                except Exception:
                    menu = None
            # else: خطای گذرای خواندن — اتصال سالم حفظ می‌شود

        # --- [PT v2.3.1] حالت PT: زنجیرهٔ جدید در «هر تیک» خوانده می‌شود،
        #     اما ثبتِ تشخیص فقط وقتی منو = ۹ است (عین مسیر قدیمی — یک قفل
        #     واحد برای کل تشخیص تیم)؛ بقیهٔ وضعیت‌ها ⇒ آخرین ID معتبر می‌ماند ---
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
            # منو != ۹ ⇒ هیچ ثبتی انجام نمی‌شود (قفل — عین مسیر قدیمی)
            for side, off in (("home", TEAM_COLOR_IDX_OFFSET_HOME),
                              ("away", TEAM_COLOR_IDX_OFFSET_AWAY)):
                try:
                    self.color_idx[side] = self._read_u8(self.base_addr + off)
                except Exception:
                    self.color_idx[side] = None
            return self._snapshot(menu)

        if menu == TEAM_MENU_DETECT_VALUE:
            # منو = ۹: خواندن زندهٔ هر دو تیم (قفل فقط بیرون از ۹ — عین PT)
            for side in ("home", "away"):
                ident = self._read_side_ident(side)
                if ident is not None and ident != self.ident[side]:
                    self.ident[side] = ident
                    self._log_event("TEAM_IDENT", side=side, league=ident[0], img=ident[1])
        elif self.ident["home"] is None or self.ident["away"] is None:
            # v2.0.6 — در مسابقه: اگر هویت هرگز در منو ۹ دیده نشده (اتصالِ
            # وسطِ بازی)، هر ۲ ثانیه تلاشِ نجات؛ اگر زنجیره‌ها در
            # بازی معتبر باشند همان مقادیر واقعی برمی‌گردند وگرنه None می‌ماند
            # (بخواندنِ نامعتبر توسط گاردهای _read_side_ident رد می‌شود).
            # بدون این، بنرِ نشانِ تیم‌ها (دقیقهٔ اول) هرگز نمایش داده نمی‌شد.
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
        # منو != ۹ یا خواندن ناموفق → قفل: آخرین انتخاب معتبر می‌ماند

        # --- نسخهٔ ۱۰٫۶: شمارهٔ رنگ هر دو تیم (استاتیک — بدون قفل منو) ---
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
        """[PT v2.3.0] حالت PT: Asset.zip → Teams/{team_id}.png (مسیر کش)؛
        مسیر قدیمی: Football_Database/{league}/{img}.png؛ اگر موجود نبود None
        (None یعنی UI همان عبارت «میزبان/مهمان» را نشان دهد)."""
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

    # ---------------- لاگ (در همان momentum_debug_log.txt) ----------------
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
# ۲۶-ب — انتخاب رنگ نمودار از leagues_data.json (نسخهٔ ۱۰٫۶؛ مسیر ۱۰٫۹)
# ---------------------------------------------------------------------
# منبع رنگ: فایل leagues_data.json داخل پوشهٔ «Football_Database» کنار
# اسکریپت (اگر آنجا نبود، نسخهٔ کنار اسکریپت هم بررسی می‌شود؛ هیچ داده‌ای از
# داخل کد هاردکد نمی‌شود). ساختار: { league_id: { "teams": { team_id:
# { "colors": {"Color 0": [r,g,b], "Color 1": ..., ...} } } } } که
# r/g/b اعشاریِ 0..1 است (مقدار واقعی ÷ 255 ⇒ برای رنگ اصلی ×255).
#
# شمارهٔ رنگِ هر تیم از دو بایت استاتیک ۱ بیتی خوانده می‌شود:
#   میزبان: base + 0x36F5198   (مطلق: 0x1436F5198)
#   مهمان:  base + 0x36F51A0   (مطلق: 0x1436F51A0)
# مقدار هر بایت دقیقاً اندیس رنگ است (از صفر شروع می‌شود).
#
# قوانین انتخاب (طبق مشخصات کاربر):
#   ۱) اگر شمارهٔ رنگ از تعداد رنگ‌های تعریف‌شده بیشتر بود (مثلاً 2 وقتی
#      بزرگ‌ترین شمارهٔ تیم 1 است) ⇒ آخرین رنگ موجود استفاده می‌شود.
#   ۲) رنگ سیاه/خیلی تیره که روی پس‌زمینهٔ تاریک نمودار خوب دیده نمی‌شود
#      ⇒ با رنگی جایگزین می‌شود که هم با پس‌زمینه هم با رنگ تیم مقابل
#      کنتراست داشته باشد.
#   ۳) اگر رنگ دو تیم شبیه هم بود (کنتراست ناکافی) ⇒ رنگ «مهمان» تعویض
#      می‌شود (با کنتراست کافی نسبت به پس‌زمینه و رنگ میزبان).
#   ۴) کنار هر تیم همیشه یک دایره (رنگ انتخابی نمودار)؛ در حالت‌های ۲ و ۳
#      دو دایره: رنگ اصلی + رنگ تعویضی (رندر در MomentumApp).
#   ۵) اگر هیچ‌کدام رنگ نداشتند ⇒ دیفالت قرمز/سفید؛ اگر فقط یکی داشت ⇒
#      برای تیم مقابلِ بی‌رنگ، خودکار رنگِ هم‌کنتراست انتخاب می‌شود.
#   ۶) مقادیر فایل اعشاری 0..1 است (÷255) ⇒ در تبدیل در 255 ضرب می‌شود.
# تابعِ resolve کاملاً pure است (بدون حافظه/TK) و برای تست مصنوعی باز است.
# =====================================================================

DEFAULT_HOME_CHART_COLOR = (230, 57, 70)    # ‎#e63946 — قرمزِ همیشه‌قبلی میزبان
DEFAULT_AWAY_CHART_COLOR = (245, 245, 245)  # ‎#f5f5f5 — سفیدِ همیشه‌قبلی مهمان
CHART_PANEL_BG_RGB = (17, 26, 43)           # ‎#111a2b — پس‌زمینهٔ پنل نمودار

# سکوی کاندیدها (اولین رنگِ قابل‌قبول انتخاب می‌شود؛ ترتیب = ترجیح):
# میزبان با قرمز شروع می‌شود؛ مهمان با سفید — تا در حالت‌های خودکار تا
# حد امکان همان ظاهر کلاسیک قرمز/سفید حفظ شود.
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
    """روشنایی نسبی WCAG (0..1) — برای سنجش کنتراست واقعی با پس‌زمینه."""
    def _lin(c):
        c = max(0.0, min(1.0, c / 255.0))
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (_lin(rgb[0]), _lin(rgb[1]), _lin(rgb[2]))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(rgb_a, rgb_b) -> float:
    """نسبت کنتراست WCAG (1..21) — معیار «دیده‌شدن روی پس‌زمینه»."""
    la, lb = _relative_luminance(rgb_a), _relative_luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _rgb_distance(a, b) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


class TeamColorResolver:
    """
    نسخهٔ ۱۰٫۶ — حل‌کنندهٔ رنگ fill نمودار برای میزبان/مهمان.

    ورودی‌ها از TeamIdentityTracker می‌آیند:
      * ident هر تیم = (league_id, image_id)  — کلید جست‌وجو در JSON
      * idx هر تیم = بایت استاتیک شمارهٔ رنگ (یا None اگر خوانده نشد)
    خروجی resolve: برای هر تیم
      {"final": (r,g,b),        # رنگ نهایی رسم نمودار
       "original": (r,g,b)|None, # رنگ اصلیِ انتخاب‌شده از فایل (None = از فایل نبود)
       "replaced": bool}         # True ⇒ دو دایره (اصلی + تعویضی) کنار تیم
    فایل JSON با کش بر اساس mtime خوانده می‌شود ⇒ اگر کاربر فایل را ویرایش
    کند، بدون ری‌استارت برنامه اعمال می‌شود.
    """

    # کمینهٔ کنتراست قابل‌قبول با پس‌زمینهٔ پنل (WCAG) — زیرِ آن «تاریک» تلقی
    # می‌شود (مشکی ≈ 0.8 ، سرمه‌ای ≈ 1.0 ، خاکستری تیره ≈ 1.7 ، قرمزِ فعلی ≈ 4.2)
    MIN_CONTRAST_BG = 2.0
    # کمینهٔ فاصلهٔ مجاز بین رنگ دو تیم (فاصلهٔ RGB در 0..441 و اختلاف روشنایی)
    MIN_RGB_DIST_OPPONENT = 90.0
    MIN_LUM255_DIFF_OPPONENT = 30.0
    # رنگ جایگزین باید از رنگ اصلیِ تعویض‌شده هم به‌قدر کافی متفاوت باشد
    MIN_RGB_DIST_FROM_ORIGINAL = 60.0

    def __init__(self, json_path: Optional[str] = None, logger=None, pt=None):
        # نسخهٔ ۱۰٫۹ — مسیر پیش‌فرض: پوشهٔ Football_Database کنار اسکریپت؛
        # اگر آنجا نبود، مسیر قدیمی (کنار اسکریپت) هم بررسی می‌شود.
        # [PT v2.3.0] اگر PT فعال باشد رنگ‌ها از teams_players_PES2021.txt
        # می‌آیند (RGB ستون اصلی) و JSON فقط fallback است.
        self.pt = pt if (pt is not None and pt.available()) else None
        self.json_path = json_path          # None = انتخاب خودکار از کاندیدها
        self.logger = logger
        self._cache = None            # آخرین JSON سالم
        self._cache_mtime = None
        self._active_path = None      # مسیر فایل فعال آخرین خواندن
        self._failed_mtime = None     # برای «فقط یک‌بار» لاگ‌کردن فایل خراب
        self._logged_loaded = False
        self._logged_missing = False

    # ---------------- فایل leagues_data.json ----------------
    def _log(self, msg: str):
        if self.logger is not None:
            try:
                self.logger.write("TEAMCOLOR", msg)
            except Exception:
                pass

    def _resolve_json_path(self) -> Optional[str]:
        """نسخهٔ ۱۰٫۹ — انتخاب فایل leagues_data.json:
        اولویت ۱: Football_Database/leagues_data.json کنار اسکریپت
        اولویت ۲: leagues_data.json کنار اسکریپت (سازگاری با نسخه‌های قبل)
        مسیر صریح داده‌شده (json_path) همیشه اولویت دارد."""
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
        """خواندن فایل با کش mtime؛ فایل نبود/خراب بود ⇒ None (دیفالت‌ها)."""
        path = self._resolve_json_path()
        if path is None:
            if not self._logged_missing:
                self._logged_missing = True
                self._log("leagues_data.json پیدا نشد (Football_Database/ و کنار "
                          "اسکریپت) — رنگ‌های پیش‌فرض قرمز/سفید استفاده می‌شود")
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
                self._log(f"leagues_data.json بارگذاری شد از {path}: "
                          f"leagues={len(data)} teams={n_teams}")
                self._logged_loaded = True
        except Exception as ex:
            # فایل خراب ⇒ تا تغییر mtime دوباره تلاش نکن (فقط یک‌بار لاگ)
            if self._failed_mtime != mtime:
                self._failed_mtime = mtime
                self._log(f"خطا در leagues_data.json ({type(ex).__name__}: {ex}) — "
                          f"رنگ‌های پیش‌فرض قرمز/سفید استفاده می‌شود")
            self._cache, self._cache_mtime = None, mtime
        return self._cache

    @staticmethod
    def _parse_colors(raw) -> List[Tuple[int, int, int]]:
        """{"Color 0": [f,f,f], ...} → [(r,g,b), ...] با اندیس ۰ مبنا (×255)."""
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
        """رنگ‌های تعریف‌شدهٔ تیم — [PT v2.3.0] حالت PT (ident = int Team ID):
        از teams_players_PES2021.txt (شمارهٔ رنگ = اندیس سطر)؛ مسیر قدیمی
        (league, team) از JSON؛ ناشناخته ⇒ []"""
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

    # ---------------- قوانین ۱ تا ۶ ----------------
    @staticmethod
    def _pick_by_index(colors, idx) -> Optional[Tuple[int, int, int]]:
        """قانون ۱ — اندیس از حافظه؛ None ⇒ رنگ اول؛ خارج از بازه ⇒ آخرین رنگ."""
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
        """قانون ۲ — سیاه/خیلی تیره روی پس‌زمینهٔ تاریک نمودار."""
        return _contrast_ratio(rgb, CHART_PANEL_BG_RGB) < cls.MIN_CONTRAST_BG

    @classmethod
    def _too_similar(cls, a, b) -> bool:
        """قانون ۳ — دو رنگ به‌هم شبیه‌اند (کنتراست ناکافی)."""
        return (_rgb_distance(a, b) < cls.MIN_RGB_DIST_OPPONENT
                or abs(_relative_luminance(a) * 255.0 - _relative_luminance(b) * 255.0)
                < cls.MIN_LUM255_DIFF_OPPONENT)

    @classmethod
    def _pick_color(cls, candidates, original, opponent) -> Tuple[int, int, int]:
        """اولین کاندید که: با پس‌زمینه کنتراست داشته باشد، از رنگ اصلی
        (تعویض‌شونده) و رنگ حریف به‌قدر کافی متفاوت باشد؛ وگرنه بهترین."""
        for hx in candidates:
            c = _hex_to_rgb(hx)
            if original is not None and _rgb_distance(c, original) < cls.MIN_RGB_DIST_FROM_ORIGINAL:
                continue
            if cls._too_dark_on_bg(c):
                continue
            if opponent is not None and cls._too_similar(c, opponent):
                continue
            return c
        # هیچ کاندیدی شرط‌ها را کامل نداشت ⇒ کمینه‌فاصله‌ترین (بیشینهٔ بدترین فاصله)
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
        """منطق کامل قوانین ۱..۶ — pure و بدون اثر جانبی."""
        home_cols = self.team_colors(home_ident)
        away_cols = self.team_colors(away_ident)
        h_base = self._pick_by_index(home_cols, home_idx)
        a_base = self._pick_by_index(away_cols, away_idx)

        h_final, a_final = h_base, a_base
        # قانون ۲ — رنگ خیلی تیره ⇒ تعویض (با درنظرگرفتن رنگ حریف)
        if h_final is not None and self._too_dark_on_bg(h_final):
            h_final = self._pick_color(TEAM_COLOR_HOME_PREF, h_final, a_final)
        if a_final is not None and self._too_dark_on_bg(a_final):
            a_final = self._pick_color(TEAM_COLOR_AWAY_PREF, a_final, h_final)
        # قانون ۵ — تیمِ بدون رنگ ⇒ خودکار رنگِ هم‌کنتراست (دیفالت اولِ لیست)
        if h_final is None:
            h_final = self._pick_color(
                (_rgb_to_hex(DEFAULT_HOME_CHART_COLOR),) + TEAM_COLOR_HOME_PREF,
                None, a_final)
        if a_final is None:
            a_final = self._pick_color(
                (_rgb_to_hex(DEFAULT_AWAY_CHART_COLOR),) + TEAM_COLOR_AWAY_PREF,
                None, h_final)
        # قانون ۳ — دو رنگ شبیه ⇒ فقط رنگ مهمان تعویض می‌شود
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
        _base = snap_load_settings(os.path.dirname(os.path.abspath(__file__)))
        if isinstance(_base, dict):
            s.update(_base)
    except Exception:
        pass
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
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


