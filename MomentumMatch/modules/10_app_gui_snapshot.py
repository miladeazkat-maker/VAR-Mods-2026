class MomentumApp(_MOM_BASE):
    """v2.1.0 — the ORIGINAL Match Momentum application (full tkinter
    panel: live TV chart, event timeline, possession sequences, details,
    debug tab) restored from the user's original code. Differences from
    the original: the panel starts HIDDEN and Alt+Ctrl+Y toggles it, the
    window close button hides instead of exiting, snapshot settings come
    from ModsConfig.json (frontend) layered over the original settings
    file, and every v2.0.x backend enhancement is kept (hook broker,
    crest banner, feed self-heal, Win32 fallback overlay)."""
    POLL_INTERVAL = 0.015
    GRAPH_REFRESH_MS = 100
    DEBUG_REFRESH_MS = 2000
    _UI_FAIL_LOG_MIN_SEC = 5.0   # v10.28 — min log gap per callback name

    def __init__(self):
        super().__init__()

        # --- core (unchanged) ---
        self.config = MomentumScoringConfig()
        self.engine = GameEngine()
        self.event_engine = EventDetectionEngine(self.config)
        self.momentum = MomentumEngine(self.config)
        self.event_engine.event_bus.subscribe(self.momentum.on_event)
        self.pass_engine = PassEngine()
        self.shot_engine = ShotEngine()

        self.dbg = DebugLogger(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            DEBUG_LOG_FILENAME))
        self._init_pipeline_health()

        self.runtime = RuntimeState()
        self.runtime.events = self.event_engine.events
        self.runtime.sequences = self.event_engine.sequences
        self.runtime.momentum_history = self.momentum.history

        self.is_monitoring = False
        self.frame_buffer: deque[SnapshotFrame] = deque(maxlen=320)
        self._frame_seq: int = 0

        self.current_possession: Optional[str] = None
        self.team1_side_name = "---"
        self.team2_side_name = "---"
        self.team1_attack_dir = 1
        self.geometry_ready = False

        self.pass_counters = {"Home": None, "Away": None}
        self.shot_counter_baseline: Optional[int] = None

        self._reset_requested = False
        self._last_ev_count = 0
        self._last_seq_count = 0
        self._last_imp_count = 0
        self._display_peak = 1.0
        self._last_wall = None
        self._poll_ema = 0.0
        self._ui_pass_list: List[PassEventData] = []
        self._ui_shot_list: List[ShotEventData] = []
        self._seq_row_items: Dict[int, str] = {}
        self._seq_last_values: Dict[int, tuple] = {}
        self.shot_debug_log: deque = deque(maxlen=150)
        self.shot_engine.debug_sink = self._shot_debug_push
        self._registered_shot_ids: set = set()
        self._registered_shot_order: deque = deque(maxlen=64)
        self._goal_glyph_ok = True
        self.half_number: int = 1
        self._ht_pending: bool = False
        self._ht_prev_end_t: float = 0.0
        self.goal_counters: Dict[str, Optional[int]] = {"Home": None, "Away": None}
        self._gh_fc_pending: Dict[str, bool] = {"Home": True, "Away": True}
        self._match_phase: MatchPhase = MatchPhase.HALF_1
        try:
            self.momentum.set_phase_label(MatchPhase.HALF_1.value)
        except Exception:
            pass
        self._match_seen_max_t: float = 0.0
        self._gh_diag = {
            "last_hb": None, "notified_no_hook": False,
            "last_captured": None, "last_rcx": None,
            "last_home": None, "last_away": None,
            "baselined": {"Home": False, "Away": False},
            "n_ok": 0, "n_wait": 0, "n_err": 0, "n_nohook": 0,
        }
        self._goal_hook_status: Dict[str, Any] = {"hooked": False, "captured": False,
                                                   "secondary": False, "rcx": None,
                                                   "home": None, "away": None, "events": 0}
        self._goal_hook_label_txt = ""

        # --- v10.27 — red card: pointer-counter baseline + cards waiting for
        # team assignment + seen exiles (player seats) ---
        self._rc_state: Dict[str, Any] = {"baseline": None, "pending": [],
                                          "exiles": set()}
        self._rc_diag: Dict[str, Any] = {"n_ok": 0, "n_none": 0, "n_err": 0,
                                         "n_cards": 0, "n_attr": 0,
                                         "n_timeout": 0}

        self._chart_colors = {"home": _rgb_to_hex(DEFAULT_HOME_CHART_COLOR),
                              "away": _rgb_to_hex(DEFAULT_AWAY_CHART_COLOR)}
        self._team_color_state = {
            "home": {"final": DEFAULT_HOME_CHART_COLOR, "original": None, "replaced": False},
            "away": {"final": DEFAULT_AWAY_CHART_COLOR, "original": None, "replaced": False},
        }
        self._team_color_sig = None
        self.team_colors = TeamColorResolver(
            json_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    TEAM_COLOR_JSON_FILENAME),
            logger=self.dbg,
            pt=PT)   # [PT v2.3.0] رنگ‌ها از PT/teams_players_PES2021.txt

        self._auto_connect_running = True
        self._auto_connect_busy = False
        self._engine_dead_streak = 0
        self._team_rehook_pending = False
        self._closing = False
        self._worker_thread = None
        self.after(AUTO_CONNECT_FIRST_DELAY_MS, self._auto_connect_tick)

        self._trb_armed = False
        self._trb_last_fire_wall = 0.0
        self._last_auto_reset_wall = 0.0
        self._poss_first_playing_seen = False

        self._tv_dirty = True
        self._tv_visible = False
        self._tv_bg_kind = "half"
        self._tv_last_sig = None
        self._tv_flag_arr = {"home": None, "away": None}
        self._tv_flag_sig = {"home": None, "away": None}
        self._tv_max_half2_t = 0.0
        self._team_ident_last = {"home": None, "away": None}

        # --- snapshot display (GPU overlay only — settings from ModsConfig) ---
        self._script_dir = os.path.dirname(os.path.abspath(__file__))
        self.snap_engine = TVSnapshotEngine(mom_load_settings())
        self._snap_overlay = None
        self._snap_overlay_photo = None
        self._snap_overlay_state = None
        self._snap_pre = None
        self._snap_pre_photo = None
        self._snap_pre_fail = None
        self._snap_pre_retry_wall = {}
        self._snap_pre_build_gen = 0
        self._snap_pre_built_gen = 0
        self._snap_life = {}
        self._snap_seq = 0
        self._snap_pre_dispatch_wall = {}
        self._snap_pre_pending_key = None
        self._snap_state = SnapshotState.EMPTY
        self._snap_state_key = None
        self._snap_state_since = time.perf_counter()
        self._snap_state_t0 = self._snap_state_since
        self._snap_overlay_after = []
        self._snap_dlg = None
        self._snap_capture_cache = {}
        # --- v10.28/10.29 — transactional show lifecycle: confirm/fail events
        # from ANY thread queue here and are drained by the Worker before each
        # snapshot tick (TVSnapshotEngine stays single-threaded); plus the
        # overlay duration watchdog deadline bookkeeping.
        self._snap_show_events = deque()
        self._snap_show_lock = threading.Lock()
        self._snap_end_dispatch_lvl = None
        self._snap_half_block_noted = set()
        self._snap_abandon_noted = set()
        self._ui_fail_last = {}
        self._snap_overlay_deadline_wall = None
        self._snap_overdue_watchdog_fired = 0
        try:
            self._snap_screen = (int(self.winfo_screenwidth()),
                                 int(self.winfo_screenheight()))
        except Exception:
            self._snap_screen = (1920, 1080)
        self._snap_anim_thread = None
        self._snap_anim_gen = 0
        self._snap_anim_alive = False
        self._tune_deb_after = None
        self._snap_retune_busy = False
        self._snap_gpu = None
        self._gpu_overlay_boot()
        # v2.0.1 — if the GPU renderer failed to boot for any reason,
        # fall back to the pure-Win32 overlay so charts ALWAYS display.
        self._boot_win32_fallback()

        # --- v2.0.5 — crest signal banner + ball-link watchdog state ---
        self._crest_banner_reset()
        self._ball_link_last_check = 0.0
        self._ball_link_last_state = None
        # v2.0.6 — ball-feed freshness evidence (charts 'visible but empty'
        # field reports): last time read_ball() produced a CHANGED value
        self._ball_feed_last = None
        self._ball_feed_change_t = 0.0
        self._ball_feed_stale_warned = None
        # v2.0.7 — feed self-heal + data-gate diagnostics state
        self._feed_heal_last_wall = 0.0
        self._ball_buf_dumped = False
        self._gate_diag_last = 0.0
        self._gate_blocked_since = 0.0

        # v10.29 — snapshot duration watchdog (self-reschedules every 2 s;
        # dies with the after()-timer thread in on_close)
        try:
            self.after(2000, self._snap_overlay_duration_watchdog)
        except Exception:
            pass

        # --- team identity tracker (feeds chart flags/colors) ---
        self._team_logo_path = {"home": None, "away": None}
        self._team_logo_photo = {"home": None, "away": None}
        self.team_tracker = TeamIdentityTracker(
            db_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), TEAM_DB_DIRNAME),
            logger=self.dbg,
            pt=PT)   # [PT v2.3.0] Team ID از زنجیرهٔ جدید + لوگو از Asset.zip
        self._team_loop_running = True
        self.after(TEAM_TRACKER_INTERVAL_MS, self._team_tick)

        # --- v2.1.0 — ORIGINAL GUI restored: built hidden, Alt+Ctrl+Y
        # toggles it. The headless build keeps zero windows. ---
        self._gui_active = not isinstance(self, _HeadlessTkBase)
        self._gui_shown = False
        self._gui_toggle_request = threading.Event()
        self._hotkey_thread = None
        if self._gui_active:
            try:
                self.title("⚡ Live Match Momentum v9 — Unified Pass • Shot • Event Engine (FL_2026)")
                self.geometry("1420x980")
                self.configure(bg="#090c12")
                self.minsize(1260, 880)
            except Exception:
                pass
            try:
                self.build_ui()
            except Exception as _gui_ex:
                try:
                    clog(f"[GUI] build_ui failed: "
                         f"{type(_gui_ex).__name__}: {_gui_ex}")
                except Exception:
                    pass
                self._gui_active = False
            try:
                # X button HIDES the panel — it never kills the pipeline
                self.protocol("WM_DELETE_WINDOW", self._gui_hide_window)
            except Exception:
                pass
            try:
                self.withdraw()   # start hidden — Alt+Ctrl+Y shows it
            except Exception:
                pass
            self._start_hotkey_thread()
            self.after(100, self._gui_toggle_tick)
        try:
            self._refresh_color_dots()   # رسم اولیهٔ دایره‌های رنگ (دیفالت قرمز/سفید)
        except Exception:
            pass

    def run_forever(self):
        """v2.1.1 BUGFIX — dual-mode entry, defined here ONCE and
        self-contained so no base-class ordering can ever shadow it again.

        v2.1.0 field bug: a second, headless-only `run_forever`
        (`self._stop_event.wait()`) was left in the class body BELOW the
        merged one, silently overriding it.  On the Windows GUI build
        (`tk.Tk` base) `_stop_event` never exists, so tkinter's
        `Misc.__getattr__` fallback raised
        `AttributeError: '_tkinter.tkapp' object has no attribute
        '_stop_event'` the instant the backend started — the process died,
        ModBridge restarted it in a loop (running/exited flapping) and the
        Alt+Ctrl+Y poller never survived long enough to answer a press.

        GUI build  -> run the real Tk mainloop (window starts hidden;
                       Alt+Ctrl+Y toggles it; X button only hides).
        Headless   -> block until on_close()/destroy()/terminate()."""
        self.run_forever_called = True
        if getattr(self, "_gui_active", False) or hasattr(self, "tk"):
            try:
                self.mainloop()
            except Exception as _rf_ex:
                try:
                    clog(f"[GUI] mainloop ended: "
                         f"{type(_rf_ex).__name__}: {_rf_ex}")
                except Exception:
                    pass
            return
        self._stop_event.wait()


    # =====================================================================
    # v2.1.0 — Alt+Ctrl+Y global hotkey: shows/hides the ORIGINAL panel.
    # The panel is built at startup but withdrawn; the poller thread only
    # sets an Event, the after()-driven tick applies the toggle on the UI
    # thread (tkinter stays single-threaded). In the headless build the
    # toggle just logs (no window exists).
    # =====================================================================
    GUI_HOTKEY_POLL_SEC = 0.04

    def _start_hotkey_thread(self):
        if self._hotkey_thread is not None and self._hotkey_thread.is_alive():
            return
        self._hotkey_thread = threading.Thread(target=self._gui_hotkey_loop,
                                               daemon=True, name="gui-hotkey")
        self._hotkey_thread.start()

    def _gui_hotkey_down(self) -> bool:
        """True while Alt+Ctrl+Y is physically held. Windows:
        GetAsyncKeyState; other platforms/tests: the _test_hotkey_down
        attribute (edge-detected the same way)."""
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                alt = bool(user32.GetAsyncKeyState(0x12) & 0x8000)   # VK_MENU
                ctrl = bool(user32.GetAsyncKeyState(0x11) & 0x8000)  # VK_CONTROL
                y = bool(user32.GetAsyncKeyState(0x59) & 0x8000)     # 'Y'
                return alt and ctrl and y
            except Exception:
                return False
        return bool(getattr(self, "_test_hotkey_down", False))

    def _gui_hotkey_loop(self):
        """Edge-detecting poller: a FRESH Alt+Ctrl+Y press queues exactly
        one toggle request."""
        was_down = False
        while not getattr(self, "_closing", False):
            try:
                down = self._gui_hotkey_down()
                if down and not was_down:
                    self._gui_toggle_request.set()
                was_down = down
            except Exception:
                pass
            time.sleep(self.GUI_HOTKEY_POLL_SEC)

    def _gui_toggle_tick(self):
        """UI-thread tick: applies queued hotkey toggles."""
        if getattr(self, "_closing", False):
            return
        try:
            if self._gui_toggle_request.is_set():
                self._gui_toggle_request.clear()
                self._toggle_gui_window()
        except Exception:
            pass
        try:
            self.after(100, self._gui_toggle_tick)
        except Exception:
            pass

    def _toggle_gui_window(self):
        """Alt+Ctrl+Y — show/hide the original panel (v2.1.0)."""
        if not getattr(self, "_gui_active", False):
            clog("[GUI] Alt+Ctrl+Y received — headless build has no window")
            return
        try:
            if self._gui_shown:
                self.withdraw()
                self._gui_shown = False
                clog("[GUI] panel hidden (Alt+Ctrl+Y)")
            else:
                self.deiconify()
                try:
                    self.attributes("-topmost", True)
                    self.lift()
                    self.focus_force()
                except Exception:
                    pass
                self._gui_shown = True
                clog("[GUI] panel shown (Alt+Ctrl+Y)")
        except Exception as ex:
            clog(f"[GUI] toggle failed: {type(ex).__name__}: {ex}")

    def _gui_hide_window(self):
        """Window close button — HIDE the panel; the backend keeps running
        (stop the mod from MyMods / ModBridge instead)."""
        try:
            self.withdraw()
            self._gui_shown = False
            clog("[GUI] panel hidden (close button — backend keeps running)")
        except Exception:
            pass

    def _begin_monitoring(self, msg: str, manual: bool = False):
        """Common start path: monitoring + worker thread. v2.1.0 — the GUI
        build also updates the header buttons/status and starts the live
        TV-tab refresh + debug table loops (original behaviour)."""
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("CONNECT", ok=True, msg=msg, pid=self.engine.pid,
                     base=fmt_ptr(self.engine.base_addr),
                     mode=("manual" if manual else "auto"))
        if getattr(self, "_gui_active", False):
            try:
                self.btn_connect.config(state="disabled", text="متصل شد ✅", bg="#2a9d8f")
                self.btn_reset.config(state="normal")
            except Exception:
                pass
            if "هشدار" in msg:
                try:
                    self.lbl_status.config(text="وضعیت: متصل (با هشدار هوک‌ها) ⚠", fg="#fca311")
                except Exception:
                    pass
            else:
                try:
                    self.lbl_status.config(text="وضعیت: متصل — در انتظار بازی 🟢", fg="#2ecc71")
                except Exception:
                    pass
        self.is_monitoring = True
        self._engine_dead_streak = 0
        self.runtime.connected = True
        self._poss_first_playing_seen = False
        clog(f"[Momentum] attached: {msg}")
        self._worker_thread = threading.Thread(target=self.worker_loop,
                                               daemon=True, name="app-worker")
        self._worker_thread.start()
        if getattr(self, "_gui_active", False):
            self.after(self.GRAPH_REFRESH_MS, self._graph_loop)
            self.after(self.DEBUG_REFRESH_MS, self.refresh_debug_table)

    def _auto_connect_tick(self):
        if not self._auto_connect_running:
            return
        try:
            if self.is_monitoring:
                if self._engine_dead_streak >= ENGINE_DEAD_STREAK_LIMIT:
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("AUTO_DISCONNECT",
                                 note="game process stopped answering")
                    self.is_monitoring = False
                    self.runtime.connected = False
                    self._engine_dead_streak = 0
                    try:
                        self.engine.cleanup()
                    except Exception:
                        pass
                    try:
                        self.btn_connect.config(state="normal", text="اتصال به پروسه بازی",
                                                bg="#00b4d8")
                        self.lbl_status.config(text="وضعیت: پروسهٔ بازی بسته شد — "
                                                    "انتظار اتصال خودکار ⏳", fg="#fca311")
                    except Exception:
                        pass
            elif not self._auto_connect_busy:
                self._auto_connect_busy = True

                def _try():
                    ok, msg = False, ""
                    try:
                        ok, msg = self.engine.initialize()
                    except Exception as ex:
                        ok, msg = False, f"{type(ex).__name__}: {ex}"
                    self._ui_post(self._auto_connect_done, ok, msg)

                threading.Thread(target=_try, daemon=True).start()
        except Exception:
            pass
        if self._auto_connect_running:
            self.after(AUTO_CONNECT_INTERVAL_MS, self._auto_connect_tick)

    def _auto_connect_done(self, ok: bool, msg: str):
        """Result of an auto-connect attempt (worker thread)."""
        self._auto_connect_busy = False
        if ok and not self.is_monitoring:
            self._begin_monitoring(msg, manual=False)
        elif not ok and not self.is_monitoring:
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("AUTO_CONNECT_RETRY", msg=str(msg))

    def build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#101624", foreground="#ffffff", rowheight=22, fieldbackground="#101624", font=("Segoe UI", 8))
        style.configure("Treeview.Heading", background="#1a2336", foreground="#00f5d4", font=("Segoe UI", 8, "bold"))

        # ---------------- Header ----------------
        header = tk.Frame(self, bg="#111622", height=56, padx=15)
        header.pack(fill="x")

        lbl_app = tk.Label(header, text="⚡ Live Match Momentum — Unified Engine",
                           font=("Segoe UI", 12, "bold"), fg="#00f5d4", bg="#111622")
        lbl_app.pack(side="left", pady=8)

        # کارت Match Time (زنده)
        time_card = tk.Frame(header, bg="#0d1a26", highlightbackground="#00b4d8", highlightthickness=1, padx=12, pady=3)
        time_card.pack(side="left", padx=25)
        tk.Label(time_card, text="MATCH TIME", font=("Segoe UI", 7, "bold"), fg="#7f8fa6", bg="#0d1a26").pack()
        self.lbl_match_time = tk.Label(time_card, text="00:00", font=("Consolas", 17, "bold"), fg="#00f5d4", bg="#0d1a26")
        self.lbl_match_time.pack()
        self.lbl_clock_src = tk.Label(time_card, text="Game Clock: --", font=("Segoe UI", 7), fg="#ffd166", bg="#0d1a26")
        self.lbl_clock_src.pack()

        self.lbl_status = tk.Label(header, text="وضعیت: در انتظار اتصال",
                                   font=("Segoe UI", 9, "bold"), fg="#fca311", bg="#111622")
        self.lbl_status.pack(side="right", padx=12)

        self.btn_connect = tk.Button(header, text="اتصال به پروسه بازی", font=("Segoe UI", 9, "bold"),
                                     bg="#00b4d8", fg="#ffffff", relief="flat", padx=16, pady=4,
                                     cursor="hand2", command=self.start_monitoring)
        self.btn_connect.pack(side="right")

        self.btn_reset = tk.Button(header, text="ریست مسابقه", font=("Segoe UI", 9, "bold"),
                                   bg="#415a77", fg="#ffffff", relief="flat", padx=14, pady=4,
                                   cursor="hand2", state="disabled", command=self.request_reset)
        self.btn_reset.pack(side="right", padx=6)

        # ---------------- Field Bar ----------------
        field_bar = tk.Frame(self, bg="#151d2c", padx=15, pady=4)
        field_bar.pack(fill="x")
        self.lbl_field_info = tk.Label(field_bar, text="هندسه زمین: در انتظار شناسایی گلرها...",
                                       font=("Segoe UI", 9), fg="#ffd166", bg="#151d2c")
        self.lbl_field_info.pack(side="left")
        # نسخه ۴: وضعیت زندهٔ هوک گل (سمت راست نوار زمین)
        self.lbl_goal_hook = tk.Label(field_bar, text="Goal Hook: -- ",
                                      font=("Consolas", 9, "bold"), fg="#7f8fa6", bg="#151d2c")
        self.lbl_goal_hook.pack(side="right")

        # ---------------- Possession Cards ----------------
        poss_box = tk.Frame(self, bg="#090c12", padx=15, pady=5)
        poss_box.pack(fill="x")

        self.card_home = tk.Frame(poss_box, bg="#131a28", relief="groove", bd=2, padx=12, pady=5)
        self.card_home.pack(side="left", fill="both", expand=True, padx=(0, 5))
        # نسخه ۱۰٫۵ — اسلات لوگو/پرچم میزبان (پیش‌فرض: «میزبان» تا لوگو خوانده شود)
        self.lbl_home_logo = tk.Label(self.card_home, text="میزبان", font=("Segoe UI", 10, "bold"),
                                      fg="#6b7a90", bg="#0d1117", bd=1, relief="groove",
                                      width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)
        self.lbl_home_logo.pack(side="left", padx=(0, 10), pady=2, fill="y")
        home_txt = tk.Frame(self.card_home, bg="#131a28")
        home_txt.pack(side="left", fill="both", expand=True)
        # نسخهٔ ۱۰٫۶ — ردیف نام: [نام تیم] [دایره‌های رنگ نمودار]
        home_name_row = tk.Frame(home_txt, bg="#131a28")
        home_name_row.pack(fill="x")
        self.lbl_home_team = tk.Label(home_name_row, text="میزبان (Home / صندلی ۱-۱۱)", font=("Segoe UI", 10, "bold"), fg="#a6e3a1", bg="#131a28")
        self.lbl_home_team.pack(side="left")
        self.cvs_home_colors = tk.Canvas(home_name_row, width=TEAM_COLOR_DOT_H, height=TEAM_COLOR_DOT_H,
                                         bg="#131a28", highlightthickness=0)
        self.cvs_home_colors.pack(side="left", padx=(7, 0))
        self.lbl_home_status = tk.Label(home_txt, text="مالکیت: ندارد", font=("Segoe UI", 8), fg="#94a3b8", bg="#131a28")
        self.lbl_home_status.pack(anchor="w")

        self.card_away = tk.Frame(poss_box, bg="#131a28", relief="groove", bd=2, padx=12, pady=5)
        self.card_away.pack(side="right", fill="both", expand=True, padx=(5, 0))
        # نسخه ۱۰٫۵ — اسلات لوگو/پرچم مهمان (پیش‌فرض: «مهمان» تا لوگو خوانده شود)
        self.lbl_away_logo = tk.Label(self.card_away, text="مهمان", font=("Segoe UI", 10, "bold"),
                                      fg="#6b7a90", bg="#0d1117", bd=1, relief="groove",
                                      width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)
        self.lbl_away_logo.pack(side="right", padx=(10, 0), pady=2, fill="y")
        away_txt = tk.Frame(self.card_away, bg="#131a28")
        away_txt.pack(side="right", fill="both", expand=True)
        # نسخهٔ ۱۰٫۶ — ردیف نام: [نام تیم] [دایره‌های رنگ نمودار]
        away_name_row = tk.Frame(away_txt, bg="#131a28")
        away_name_row.pack(fill="x")
        self.lbl_away_team = tk.Label(away_name_row, text="میهمان (Away / صندلی ۱۲-۲۲)", font=("Segoe UI", 10, "bold"), fg="#f38ba8", bg="#131a28")
        self.lbl_away_team.pack(side="left")
        self.cvs_away_colors = tk.Canvas(away_name_row, width=TEAM_COLOR_DOT_H, height=TEAM_COLOR_DOT_H,
                                         bg="#131a28", highlightthickness=0)
        self.cvs_away_colors.pack(side="left", padx=(7, 0))
        self.lbl_away_status = tk.Label(away_txt, text="مالکیت: ندارد", font=("Segoe UI", 8), fg="#94a3b8", bg="#131a28")
        self.lbl_away_status.pack(anchor="w")

        # ---------------- Tabs ----------------
        tabs_frame = tk.Frame(self, bg="#090c12")
        tabs_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.tab_control = ttk.Notebook(tabs_frame)
        # نسخهٔ ۱۰٫۱۲ — تب «Live Match Momentum» حذف شد (درخواست کاربر)؛
        # تب TV Momentum کامل حفظ شده و تب اول است.
        # نسخهٔ ۱۰٫۹ — پس‌زمینهٔ تب TV: مشکی خالص (حول تصویر/letterbox هم مشکی)
        self.tab_tv = tk.Frame(self.tab_control, bg="#000000")
        self.tab_events = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_seq = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_details = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_debug = tk.Frame(self.tab_control, bg="#090c12")

        # نسخهٔ ۱۰٫۷ — تب نمودار روی تصویر پنل (Half/Full/Extra)
        self.tab_control.add(self.tab_tv, text="  📺 TV Match Momentum  ")
        self.tab_control.add(self.tab_events, text="  📋 Event Timeline  ")
        self.tab_control.add(self.tab_seq, text="  📊 Possession Sequences  ")
        self.tab_control.add(self.tab_details, text="  🎯 Event / Threat Details  ")
        self.tab_control.add(self.tab_debug, text="  🧪 Momentum Debug  ")
        self.tab_control.pack(fill="both", expand=True)
        # رندر TV فقط وقتی تب دیده می‌شود + رندر فوری هنگام سوییچ
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.build_tv_tab(self.tab_tv)
        self.build_events_tab(self.tab_events)
        self.build_sequences_tab(self.tab_seq)
        self.build_details_tab(self.tab_details)
        self.build_debug_tab(self.tab_debug)


    def _detect_goal_glyph(self):
        """بررسی وجود گلیف ⚽ (U+26BD) در فونت پیش‌فرض matplotlib؛
        در نبود آن، مارکر گرافیکی استاندارد (دایره سفید با حاشیه تیره) استفاده می‌شود."""
        try:
            from matplotlib import font_manager
            from matplotlib.ft2font import FT2Font
            fp = font_manager.FontProperties(family="DejaVu Sans")
            font_path = font_manager.findfont(fp)
            ft = FT2Font(font_path)
            self._goal_glyph_ok = ft.get_char_index(0x26BD) != 0
        except Exception:
            self._goal_glyph_ok = False

    def build_tv_tab(self, parent):
        """تب TV: فقط و فقط نمودار روی تصویر — بدون هیچ متن/تیک/عددی.
        نسخهٔ ۱۰٫۱۰ — Figure دیگر شفاف نیست: پس‌زمینهٔ مشکی خالص (#000000)
        روی خودِ Figure/محور/ویدجت بوم اعمال می‌شود (رفع «شفید» دیده‌شدن).
        نسخهٔ ۱۰٫۱۱ — آیکون چرخ‌دندهٔ ⚙ بالای تب: مودال تنظیمات اسنپ‌شات
        (زمان‌بندی نمایش روی صفحهٔ بازی + مدت + ذخیرهٔ دائمی + تاریخ/زمان)."""
        bar = tk.Frame(parent, bg="#000000", height=30)
        bar.pack(fill="x")
        tk.Label(bar, text="TV Match Momentum",
                 font=("Segoe UI", 8), fg="#22304d", bg="#000000").pack(side="left",
                                                                        padx=10)
        self.btn_snap_settings = tk.Button(
            bar, text="⚙", font=("Segoe UI", 13, "bold"),
            bg="#000000", fg="#00f5d4", relief="flat", bd=0,
            activebackground="#000000", activeforeground="#ffffff",
            highlightthickness=0, cursor="hand2",
            command=self.open_snapshot_settings)
        self.btn_snap_settings.pack(side="right", padx=10, pady=1)
        tk.Label(bar, text="تنظیمات اسنپ‌شات",
                 font=("Segoe UI", 8), fg="#22304d", bg="#000000").pack(side="right")

        # --- نسخهٔ ۱۰٫۱۶ — ابزار موقت تنظیم ظاهر (شرط کاربر — بعداً حذف می‌شود) ---
        # الف) نرمی لبهٔ نمودار (عدد → گاوسی اضافهٔ لبه)
        # ب) دو گزینهٔ نرمی/شدت نور نئون منحنی‌ها
        bar2 = tk.Frame(parent, bg="#000000", height=30)
        bar2.pack(fill="x", side="bottom")   # قبل از canvas — نمودار وسط می‌ماند
        self._tv_edge_var = tk.StringVar(value=f"{TV_EDGE_SMOOTH_PX:g}")
        self._tv_glow_soft_var = tk.StringVar(value=f"{TV_GLOW_SOFTNESS_MUL:g}")
        self._tv_glow_int_var = tk.StringVar(value=f"{TV_GLOW_INTENSITY_MUL:g}")

        def _tune_lbl(txt):
            tk.Label(bar2, text=txt, font=("Segoe UI", 8),
                     fg="#7f8fa6", bg="#000000").pack(side="right", padx=(12, 2))

        def _tune_ent(var, w=6):
            e = tk.Entry(bar2, textvariable=var, width=w, justify="center",
                         font=("Consolas", 9, "bold"), bg="#101a2c",
                         fg="#ffd166", relief="flat", highlightthickness=1,
                         highlightbackground="#2e384d",
                         insertbackground="#ffd166")
            e.pack(side="right", padx=2)
            e.bind("<Return>", lambda _e: self._apply_tv_tuning())
            # نسخهٔ ۱۰٫۱۷ — «ریل‌تایم»: تایپ در کافیست؛ ۲۲۰ms بعد از مکث،
            # نمودارِ رسم‌شده (تب و PNG روی بازی) با مقدار تازه رندر می‌شود
            e.bind("<KeyRelease>", self._tune_key_live)
            return e

        tk.Label(bar2, text="ابزار موقت (در آپدیت بعدی حذف می‌شود):",
                 font=("Segoe UI", 8), fg="#55627a",
                 bg="#000000").pack(side="right", padx=(6, 10))
        _tune_lbl("نرمی لبه (px):")
        _tune_ent(self._tv_edge_var)
        _tune_lbl("نرمی نئون (×):")
        _tune_ent(self._tv_glow_soft_var)
        _tune_lbl("شدت نئون (×):")
        _tune_ent(self._tv_glow_int_var)
        tk.Button(bar2, text="اعمال", font=("Segoe UI", 8, "bold"),
                  bg="#1a2336", fg="#00f5d4", relief="flat", cursor="hand2",
                  activebackground="#1a2336", activeforeground="#ffffff",
                  command=self._apply_tv_tuning).pack(side="right", padx=(2, 8))
        tk.Button(bar2, text="پیش‌فرض (۰ / ۱ / ۱)", font=("Segoe UI", 8),
                  bg="#141b2b", fg="#7f8fa6", relief="flat", cursor="hand2",
                  activebackground="#141b2b", activeforeground="#c0c8d8",
                  command=self._reset_tv_tuning).pack(side="left", padx=8)
        self.tv_fig = Figure(figsize=(9.9, 6.0), dpi=100)
        self.tv_fig.patch.set_facecolor("#000000")
        self.tv_fig.patch.set_alpha(1.0)
        self.tv_ax = self.tv_fig.add_subplot(111)
        self.tv_ax.set_facecolor("#000000")
        self.tv_canvas = FigureCanvasTkAgg(self.tv_fig, master=parent)
        self.tv_canvas.get_tk_widget().configure(bg="#000000",
                                                 highlightthickness=0)
        self.tv_canvas.get_tk_widget().pack(fill="both", expand=True,
                                            padx=6, pady=(0, 6))
        self._style_tv_axes_empty()


    def _style_tv_axes_empty(self):
        """حالت انتظار تب TV — بدون هیچ متن اضافه (پس‌زمینهٔ مشکی خالص).
        نسخهٔ ۱۰٫۱۰ — بعد از clear() رنگ‌ها دوباره صراحتاً مشکی می‌شوند
        (clear() رنگ محور را به پیش‌فرض برمی‌گرداند)."""
        self.tv_ax.clear()
        self.tv_ax.set_facecolor("#000000")
        self.tv_ax.axis("off")
        _fig = getattr(self.tv_ax, "figure", None)
        if _fig is not None:
            _fig.patch.set_facecolor("#000000")
            _fig.patch.set_alpha(1.0)


    def _apply_tv_tuning(self):
        """بند ۳ پیام کاربر — کادرهای موقت کنار نمودار:
          * «نرمی لبه (px)» → TV_EDGE_SMOOTH_PX (گاوسی اضافهٔ لبه + کلمپ شکل)
          * «نرمی نئون (×)» → TV_GLOW_SOFTNESS_MUL (سیگمای بلور درخشش)
          * «شدت نئون (×)» → TV_GLOW_INTENSITY_MUL (آلفای اوج درخشش)
        نسخهٔ ۱۰٫۱۷ — «ریل‌تایم روی نمودارِ رسم‌شده» (شرط تازهٔ کاربر:
        نه فقط نمودارِ جدید!):
          * هر تایپ در کادرها خودش این متد را با تأخیر ۲۲۰ms صدا می‌زند؛
          * تب زندهٔ TV فوراً با همان دادهٔ رسم‌شده دوباره رندر می‌شود
            (force از پرچم stale-visible عبور می‌کند)؛
          * اگر PNG اسنپ‌شات همین حالا روی صفحهٔ بازی است، همان پنجره
            در جای خودش با ظاهر تازه re-blit می‌شود (بدون قطع انیمیشن
            و بدون ریست ماشین حالت)؛
          * کش/پیش‌بارگذاری برای PNGهای بعدی هم باطل/بازمسلح می‌شود.
        (این مقادیر موقت‌اند و در آپدیت بعدی هاردکد می‌شوند.)"""
        global TV_EDGE_SMOOTH_PX, TV_GLOW_SOFTNESS_MUL, TV_GLOW_INTENSITY_MUL

        def _f(var, default, lo, hi):
            try:
                v = float(str(var.get()).strip().replace(",", "."))
            except Exception:
                return default
            return max(lo, min(hi, v))

        TV_EDGE_SMOOTH_PX = _f(self._tv_edge_var, 0.0, 0.0, 300.0)
        TV_GLOW_SOFTNESS_MUL = _f(self._tv_glow_soft_var, 1.0, 0.05, 6.0)
        TV_GLOW_INTENSITY_MUL = _f(self._tv_glow_int_var, 1.0, 0.0, 6.0)
        try:
            self._tv_edge_var.set(f"{TV_EDGE_SMOOTH_PX:g}")
            self._tv_glow_soft_var.set(f"{TV_GLOW_SOFTNESS_MUL:g}")
            self._tv_glow_int_var.set(f"{TV_GLOW_INTENSITY_MUL:g}")
        except Exception:
            pass
        # نسخهٔ ۱۰٫۱۷ — هر کار «مستقل» است تا یک خطا بقیه را فلج نکند
        try:
            self._snap_capture_cache.clear()          # PNGها با ظاهر تازه
        except Exception as ex:
            clog(f"[TVTune] cache: {type(ex).__name__}: {ex}")
        try:
            self.snap_engine.reset_preload_flags()    # پیش‌بارگذاری دوباره مسلح
        except Exception as ex:
            clog(f"[TVTune] preflags: {type(ex).__name__}: {ex}")
        try:
            self._discard_snapshot_preload()          # پنجرهٔ پیش‌ساختهٔ کهنه
        except Exception as ex:
            clog(f"[TVTune] prediscard: {type(ex).__name__}: {ex}")
        try:
            self._tv_dirty = True
            self._refresh_tv_chart(force=True)        # تبِ رسم‌شده — فوری
        except Exception as ex:
            clog(f"[TVTune] tab: {type(ex).__name__}: {ex}")
        try:
            self._retune_live_overlay()               # PNGِ در حال نمایش — فوری
        except Exception as ex:
            clog(f"[TVTune] overlay: {type(ex).__name__}: {ex}")


    def _tune_key_live(self, _event=None):
        """نسخهٔ ۱۰٫۱۷ — اعمال «ریل‌تایم» هنگام تایپ: هر کلید، تایمرِ
        ۲۲۰ms را از نو کوک می‌کند؛ بعد از مکثِ کوتاه، مقدار اعمال و
        نمودارِ رسم‌شده همان لحظه تازه می‌شود (بدون نیاز به Enter)."""
        try:
            aid = getattr(self, "_tune_deb_after", None)
            if aid:
                self.after_cancel(aid)
        except Exception:
            pass
        try:
            self._tune_deb_after = self.after(220, self._tune_live_apply)
        except Exception:
            pass


    def _tune_live_apply(self):
        try:
            self._tune_deb_after = None
        except Exception:
            pass
        self._apply_tv_tuning()


    def _retune_live_overlay(self):
        """نسخهٔ ۱۰٫۱۷ — اگر پنجرهٔ اسنپ‌شات همین حالا روی صفحهٔ بازی است،
        همان نمودارِ «در حال نمایش» با پیچ‌های تازه، در همان مکان و بدون
        قطع انیمیشن، دوباره رندر و re-blit می‌شود (ریل‌تایمِ واقعی —
        رندر سنگین در ترد Worker است و UI هیچ لگی نمی‌بیند).
        نسخهٔ ۱۰٫۲۳ — مسیر GPU: همان «re-blit» — texture در جا عوض
        می‌شود (بدون ساخت پنجره، بدون قطع نمایش)."""
        if getattr(self, "_snap_gpu", None) is not None:
            st = getattr(self, "_snap_overlay_state", None)
            if st is None or not st.get("gpu"):
                return
            if getattr(self, "_snap_retune_busy", False):
                return
            self._snap_retune_busy = True

            def _worker_gpu():
                try:
                    # نسخهٔ ۱۰٫۲۴ — اول مسیر برداری (سریع — بدون matplotlib)
                    scene = None
                    try:
                        scene = self._build_gpu_scene_now()
                    except Exception:
                        scene = None
                    if scene is not None:
                        self.after(0, self._gpu_scene_reblit, scene, st)
                        return
                    img = self._snapshot_render_current(out_path=None)
                    if img is None:
                        return
                    disp, _arr, _geo = snap_prepare_display(
                        img, *self._snap_screen)
                    if disp is None:
                        return
                    self.after(0, self._gpu_reblit, disp, st)
                except Exception as ex:
                    clog(f"[SnapRetune] worker(GPU): "
                         f"{type(ex).__name__}: {ex}")
                finally:
                    try:
                        self._snap_retune_busy = False
                    except Exception:
                        pass

            threading.Thread(target=_worker_gpu, daemon=True,
                             name="snap-retune").start()
            return
        st = getattr(self, "_snap_overlay_state", None)
        win = getattr(self, "_snap_overlay", None)
        if st is None or win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        if getattr(self, "_snap_retune_busy", False):
            return                                    # یکی در جریان است — کافی است
        try:
            cur_y = int(win.winfo_rooty())
        except Exception:
            cur_y = int(st.get("y_final", 0))
        if cur_y > int(self.winfo_screenheight()):
            cur_y = int(st.get("y_final", cur_y))     # زیر صفحه — جای نهایی
        self._snap_retune_busy = True

        def _worker():
            try:
                img = self._snapshot_render_current(out_path=None)
                if img is None:
                    return
                disp, arr, geo = snap_prepare_display(img, *self._snap_screen)
                if disp is None:
                    return
                self.after(0, self._reblit_overlay_window, disp, arr, st,
                           cur_y)
            except Exception as ex:
                clog(f"[SnapRetune] worker: {type(ex).__name__}: {ex}")
            finally:
                try:
                    self._snap_retune_busy = False
                except Exception:
                    pass

        threading.Thread(target=_worker, daemon=True,
                         name="snap-retune").start()


    def _reblit_overlay_window(self, disp, arr, st, cur_y):
        """نسخهٔ ۱۰٫۱۷ — اعمال بیت‌مپ تازه روی «همان» پنجرهٔ زندهٔ
        اسنپ‌شات، در همان مکان (بدون ساخت پنجرهٔ جدید/بدون ریست انیمیشن).
        پنجرهٔ لایه‌ای → یک UpdateLayeredWindow؛ پنجرهٔ معمولی → عوض‌کردن
        تصویر Label."""
        win = st.get("win")
        if win is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        x, w, h = int(st.get("x", 0)), int(st.get("w", 1)), int(st.get("h", 1))
        try:
            cur_y = int(cur_y)
        except (TypeError, ValueError):
            cur_y = int(st.get("y_final", 0))
        try:
            if st.get("layered"):
                if win32_show_layered(win, disp, x, cur_y, w, h, arr=arr):
                    st["disp"], st["arr"] = disp, arr
                    try:
                        ph = ImageTk.PhotoImage(disp)   # برای fallback/مسیر غیرلایه‌ای
                        st["photo"] = ph
                    except Exception:
                        pass
                    return
            ph = ImageTk.PhotoImage(disp)
            lbl = st.get("lbl")
            if lbl is not None:
                lbl.configure(image=ph)
            st["photo"] = ph
            st["disp"], st["arr"] = disp, arr
        except Exception as ex:
            clog(f"[SnapRetune] reblit: {type(ex).__name__}: {ex}")


    def _reset_tv_tuning(self):
        """بازگشت پیچ‌های موقت به پیش‌فرض (۰ / ۱ / ۱)."""
        global TV_EDGE_SMOOTH_PX, TV_GLOW_SOFTNESS_MUL, TV_GLOW_INTENSITY_MUL
        TV_EDGE_SMOOTH_PX = 0.0
        TV_GLOW_SOFTNESS_MUL = 1.0
        TV_GLOW_INTENSITY_MUL = 1.0
        try:
            self._tv_edge_var.set("0")
            self._tv_glow_soft_var.set("1")
            self._tv_glow_int_var.set("1")
        except Exception:
            pass
        self._apply_tv_tuning()


    def _on_tab_changed(self, _event=None):
        try:
            sel = self.tab_control.select()
            self._tv_visible = bool(sel) and sel == str(self.tab_tv)
            if self._tv_visible:
                self._tv_dirty = True     # رندر فوری هنگام سوییچ
        except Exception:
            pass


    def _tv_bg_kind_for_state(self) -> str:
        """انتخاب تصویر پس‌زمینه بر اساس فاز مسابقه:
        نیمه اول → Half | نیمه دوم → Full | وقت اضافه → Extra
        نسخهٔ ۱۰٫۱۳ — شرط کاربر: نمودارِ بخش بعدی فقط وقتی «فراخوانی» می‌شود
        که بخش بعدی واقعاً شروع شده باشد (بازی Playing + تایمر از مرز بیشتر):
          * Full: نیمه دوم + تایمرِ دیده‌شده در جریان بازی از ۴۵:۰۰ بیشتر
            شده باشد (تا قبل از آن، نمودار نیمهٔ اول روی صفحه می‌ماند)؛
          * Extra: ری‌استارتِ ۹۰ در تایم‌لاین «تأیید» شده باشد — تایمر به
            ۹۰:۰۰ ریست شده و بعدش در جریان PLAYING از ۹۰:۰۰ بیشتر شده است.
            وقت تلف‌شدهٔ بلند نیمهٔ دوم (حتی بالای ۹۵ دقیقه) و ریستِ بدون
            ادامهٔ بازی، دیگر نمودار ET را فراخوانی نمی‌کند (رفع باگ)."""
        if (self.half_number >= 2
                and self._match_phase in (MatchPhase.HALF_2, MatchPhase.ET1,
                                          MatchPhase.ET2, MatchPhase.FULL_TIME)):
            if float(getattr(self, "_tv_max_half2_t", 0.0) or 0.0) > 45.0 * 60.0:
                mom = getattr(self, "momentum", None)
                hist = None
                if mom is not None:
                    try:
                        with mom._lock:
                            hist = list(mom.history)
                    except Exception:
                        hist = None
                if hist and tv_restart_flags(hist).get(90.0, False):
                    return "extra"
                return "full"
        return "half"

    def _tv_update_flags(self):
        """آماده‌سازی آرایهٔ لوگو/پرچم هر تیم (استروک سفید گوشه‌گرد) — فقط
        وقتی مسیر تصویر عوض شده دوباره پردازش می‌شود."""
        for side in ("home", "away"):
            path = self.team_tracker.logo_path_for(self._team_ident_last.get(side))
            sig = path
            if sig != self._tv_flag_sig[side]:
                self._tv_flag_sig[side] = sig
                self._tv_flag_arr[side] = tv_process_flag(path) if path else None
                self._tv_dirty = True

    def _tv_signature(self, bg_kind: str) -> tuple:
        """امضای وضعیت برای رندر تنها در صورت تغییر (کارایی ~10fps).
        نسخهٔ ۱۰٫۱۳ — مُهر تاریخ دیگر جزو رندر تب نیست (فقط فایل دائمی)."""
        with self.momentum._lock:
            hist = self.momentum.history
            n_hist = len(hist)
            last = hist[-1] if hist else None
            last_key = (round(float(last["disp_time"]), 2),
                        round(float(last["net"]), 3)) if last else None
            n_markers = len(self.momentum.hook_goal_markers)
            mk_key = (round(float(self.momentum.hook_goal_markers[-1]["disp_time"]), 2),
                      self.momentum.hook_goal_markers[-1].get("team")) \
                if n_markers else None
        return (bg_kind, n_hist, last_key, n_markers, mk_key,
                self._chart_colors["home"], self._chart_colors["away"],
                self._tv_flag_sig["home"], self._tv_flag_sig["away"])

    def _refresh_tv_chart(self, force: bool = False):
        """رندر زندهٔ تب TV — فقط وقتی تب دیده می‌شود و وضعیت عوض شده است.
        نسخهٔ ۱۰٫۱۳ — طبق درخواست کاربر، تاریخ/ساعت فقط روی «فایل دائمی»
        نوشته می‌شود؛ نه روی نمودار نمایش داده‌شده روی صفحهٔ بازی و نه تب.
        نسخهٔ ۱۰٫۱۷ — force=True یعنی «همین حالا رندر کن»: از پرچم
        _tv_visible عبور می‌کند (اگر پرچم به هر دلیلی stale باشد،
        «اعمال پیچ‌ها» دیگر قربانی آن نمی‌شود؛ فقط canvas باید باشد)."""
        try:
            if getattr(self, "tv_canvas", None) is None:
                return
            if not force and not self._tv_visible:
                return
            bg_kind = self._tv_bg_kind_for_state()
            self._tv_update_flags()
            sig = self._tv_signature(bg_kind)
            if not force and sig == self._tv_last_sig and not self._tv_dirty:
                return
            self._tv_last_sig = sig
            self._tv_dirty = False
            draw_tv_momentum(
                self.tv_ax, self.momentum, self.config, self._display_value,
                bg_kind,
                home_color=self._chart_colors["home"],
                away_color=self._chart_colors["away"],
                home_flag_arr=self._tv_flag_arr["home"],
                away_flag_arr=self._tv_flag_arr["away"],
            )
            self.tv_canvas.draw_idle()
        except Exception as ex:
            clog(f"[TVChart] {type(ex).__name__}: {ex}")


    def _snapshot_timestamp_text(self) -> Optional[str]:
        """مُهر تاریخ/ساعت «شروع» بازی از ساعت سیستم (اگر تیک فعال باشد)."""
        try:
            if not self.snap_engine.s.get("timestamp"):
                return None
            w = self.snap_engine.match_start_wall
            if w is None:
                return None
            return time.strftime("%Y-%m-%d %H:%M", time.localtime(w))
        except Exception:
            return None

    def _snapshot_tmp_path(self, key: str) -> str:
        safe = "".join(ch for ch in str(key) if ch.isalnum() or ch in "-_")
        return os.path.join(self._script_dir, TV_SNAP_TMP_DIRNAME,
                            f"snap_{safe or 'chart'}.png")

    def _build_gpu_scene_now(self, timestamp_text: Optional[str] = None):
        """نسخهٔ ۱۰٫۲۴ — ساخت صحنهٔ برداری GPU در ترد Worker (خالص — بدون
        Tk/GL). از همان رنگ/پرچم/bg_kind مسیر فعلی استفاده می‌کند؛ شکل منحنی
        از _tv_curve_core — مو‌به‌مو همان مسیر matplotlib. خروجی None =
        ساخت ناموفق (فراخوان به مسیر بیت‌مپ قبلی برمی‌گردد)."""
        return build_gpu_graph_scene(
            self.momentum, self.config, self._tv_bg_kind_for_state(),
            self._chart_colors["home"], self._chart_colors["away"],
            self._tv_flag_arr["home"], self._tv_flag_arr["away"],
            timestamp_text=timestamp_text, screen=self._snap_screen)

    def _snapshot_render_current(self, out_path: Optional[str] = None,
                                 with_timestamp: bool = False):
        """رندر آفلاین وضعیت فعلی نمودار TV (با آلفای شفاف) — همان شکلِ تب،
        همراه گل‌ها. خروجی: PIL.Image یا None. (از Worker فراخوانی می‌شود؛
        Figure مستقل دارد و با تب اصلی تداخل ندارد.)
        نسخهٔ ۱۰٫۱۳ — مُهر تاریخ/ساعت «فقط» برای فایل ذخیرهٔ دائمی تولید
        می‌شود (with_timestamp=True)؛ نموداری که روی صفحهٔ بازی می‌آید
        هرگز مُهر ندارد."""
        return render_tv_snapshot(
            self.momentum, self.config, self._display_value,
            self._tv_bg_kind_for_state(),
            self._chart_colors["home"], self._chart_colors["away"],
            self._tv_flag_arr["home"], self._tv_flag_arr["away"],
            timestamp_text=(self._snapshot_timestamp_text()
                            if with_timestamp else None),
            out_path=out_path, transparent=True)

    def _snap_life_mark(self, key, stage: str, note: str = "") -> None:
        """ثبت یک مرحله از چرخهٔ عمر Snapshot در دفترترتیب — امن برای هر
        تردی (Worker/Main-UI/Anim) و هر کلیدی (h1/h2/et/end)."""
        try:
            if key is None:
                key = "?"
            life = self._snap_life.setdefault(key, {})
            if "seq" not in life:
                self._snap_seq += 1
                life["seq"] = self._snap_seq
                life["t0"] = time.perf_counter()
            life.setdefault("stages", []).append(
                (stage, time.perf_counter(), _snap_thread_tag(), note))
        except Exception:
            pass

    def _snap_life_dump(self, key, title: str = "") -> None:
        """چاپ تایم‌لاین کامل چرخهٔ عمر Snapshot (بلوک [SNAPSHOT SEQ #N])
        + RACE CHECK: فاصلهٔ PRELOAD COMPLETE تا SHOW یا تحلیل علت Race."""
        if not TV_SNAP_SHOW_DEBUG:
            return
        try:
            life = self._snap_life.get(key) or {}
            seq = life.get("seq", 0)
            stages = life.get("stages") or []
            t0 = life.get("t0") or (stages[0][1] if stages
                                    else time.perf_counter())
            print("=" * 60, flush=True)
            print(f"[SNAPSHOT SEQ #{seq} (key={key})] LIFECYCLE"
                  + (f" — {title}" if title else ""), flush=True)
            print("-" * 60, flush=True)
            for i, (stg, ts, th, note) in enumerate(stages, 1):
                print(f"  #{i:02d} {stg:<42s} "
                      f"T+{(ts - t0):9.3f}s | {th}"
                      + (f" | {note}" if note else ""), flush=True)
            names = [s[0] for s in stages]
            pre_done = next((ts for (stg, ts, _th, _nt) in stages
                             if "PRELOAD COMPLETE" in stg), None)
            show_ui = next((ts for (stg, ts, _th, _nt) in stages
                            if stg.startswith("SHOW (UI")), None)
            if pre_done is not None and show_ui is not None:
                print(f"RACE CHECK: window PRELOAD COMPLETE → SHOW gap: "
                      f"{(show_ui - pre_done) * 1000.0:.1f} ms "
                      "(positive = prebuilt window was ready before "
                      "show — OK)", flush=True)
            elif show_ui is not None:
                self._snap_race_analysis(key)
            print("=" * 60, flush=True)
        except Exception:
            pass

    def _snap_race_analysis(self, key) -> None:
        """نسخهٔ ۱۰٫۲۱ — تست ۶: چرا Show قبل از PRELOAD COMPLETE اجرا شد؟
        بر اساس «آخرین مرحلهٔ ثبت‌شده»، نقطهٔ توقف دقیق + علت محتمل لاگ
        می‌شود (بند E کاربر). فقط تشخیص — هیچ تغییر رفتاری.
        نسخهٔ ۱۰٫۲۴ — فقط با TV_SNAP_SHOW_DEBUG."""
        if not TV_SNAP_SHOW_DEBUG:
            return
        try:
            life = self._snap_life.get(key) or {}
            stages = life.get("stages") or []
            names = [s[0] for s in stages]

            def _have(tag: str) -> bool:
                return any(tag in n for n in names)

            print("RACE ANALYSIS — show arrived BEFORE preload completed:",
                  flush=True)
            if not _have("PRELOAD REQUESTED"):
                print("  • PRELOAD REQUESTED missing → engine never "
                      "entered the 2s preload window (timer tick jumped "
                      "over it / state gating) → nothing was ever "
                      "dispatched", flush=True)
            elif not _have("PRELOAD DISPATCHED"):
                print("  • PRELOAD DISPATCHED missing → worker saw the "
                      "request but render/prepare/dispatch never "
                      "completed (worker busy — see PRELOAD log)",
                      flush=True)
            elif not _have("PRELOAD UI CALLBACK EXECUTED"):
                disp = next((ts for (stg, ts, _th, _nt) in stages
                             if "DISPATCHED" in stg), None)
                lag = (f" — callback was queued "
                       f"{(time.perf_counter() - disp):.3f}s ago and "
                       "still has not executed (UI thread busy/blocked?)"
                       if disp is not None else "")
                print("  • PRELOAD UI CALLBACK EXECUTED missing → build "
                      "callback never ran on UI thread" + lag,
                      flush=True)
                print(f"    build_gen="
                      f"{getattr(self, '_snap_pre_build_gen', 0)} | "
                      f"built_gen="
                      f"{getattr(self, '_snap_pre_built_gen', 0)} | "
                      f"pending_key="
                      f"{getattr(self, '_snap_pre_pending_key', None)}",
                      flush=True)
            else:
                print("  • build callback executed but PRELOAD COMPLETE "
                      "is missing → build failed/superseded midway "
                      "(see [SNAPSHOT PRELOAD] NOT READY block)",
                      flush=True)
            f = getattr(self, "_snap_pre_fail", None)
            if f and f.get("reason"):
                print(f"  • last preload failure: {f.get('reason')}",
                      flush=True)
        except Exception:
            pass

    def _snap_state_event(self, event: str, state: "SnapshotState",
                          key=None, extra: str = "",
                          only_from: Optional[tuple] = None) -> None:
        """ثبت یک گذر ماشین حالت + چاپ بلوک [SNAPSHOT_STATE].
        only_from: اگر داده شود، فقط وقتی «حالت قبلی» یکی از این‌هاست
        event ثبت می‌شود (جلوگیری از لاگ گمراه‌کننده در مسیرهای
        تکراری مثل hideِ لحظهٔ Show).
        امن برای هر تردی (Worker/Main-UI) — فقط تخصیص اتمی + print."""
        try:
            prev = getattr(self, "_snap_state", SnapshotState.EMPTY)
            if only_from is not None and prev not in only_from:
                return
            self._snap_state = state
            if key is not None:
                self._snap_state_key = key
            self._snap_state_since = time.perf_counter()
            if state == SnapshotState.PREPARING:
                # مرجع اندازه‌گیری prepare= (فقط شروع PRELOAD ریست می‌شود
                # تا event های بین راه اندازهٔ «prepare» را خراب نکنند)
                self._snap_state_t0 = self._snap_state_since
            if not TV_SNAP_SHOW_DEBUG:
                return
            print("[SNAPSHOT_STATE]", flush=True)
            print(event, flush=True)
            print(f"time={time.time():.2f}", flush=True)
            bits = []
            k = self._snap_state_key
            if k is not None:
                bits.append(f"key={k}")
            if extra:
                bits.append(extra)
            if bits:
                print(" | ".join(bits), flush=True)
            print(f"previous: {prev.name} → {state.name}", flush=True)
            print("-" * 40, flush=True)
        except Exception:
            pass

    def _snap_show_stage(self, key, stage: str, extra: str = "") -> None:
        """لاگ همیشه-فعل یک مرحله از چرخهٔ نمایش (فایل کوچک
        momentum_2026_snapshot.log کنار اسکریپت — عین mlog نسخهٔ 2017؛
        هیچ چاپ کنسولی ندارد). قابل‌اتکا در آزمون میدانی بدون فلگ دیباگ."""
        try:
            if key in (None, ""):
                key = "?"
            msg = f"[{key}] {stage}" + (f" | {extra}" if extra else "")
            self._snap_life_mark(key, stage, note=extra)
            _snap_stage_write(msg)
        except Exception:
            pass

    def _snap_show_event(self, kind: str, key, reason: str = "") -> None:
        """ثبت رویداد چرخهٔ تراکنشی از «هر تردی» (Worker/UI/انیمیشن):
        ("confirm", key)         → نمایش به SHOWING رسید — مصرف مجاز
        ("confirm_end", lvl)     → show_end به SHOWING رسید
        ("fail", key, reason)    → شکست dispatch/UI — مسلح‌سازی مجدد
        ("fail_end", lvl, reason)→ شکست show_end — پس گرفتن shows"""
        try:
            with self._snap_show_lock:
                self._snap_show_events.append((kind, key, reason))
        except Exception:
            pass

    def _snap_drain_show_events(self) -> None:
        """اعمال رویدادهای confirm/fail روی موتور — فقط در ترد Worker،
        در ابتدای هر _snapshot_tick (موتور خالص/تک‌ترد می‌ماند)."""
        try:
            while True:
                try:
                    with self._snap_show_lock:
                        kind, key, reason = self._snap_show_events.popleft()
                except IndexError:
                    return
                if kind == "confirm":
                    _att = self.snap_engine.show_attempt(key)
                    if self.snap_engine.confirm_shown(key):
                        self._snap_show_stage(
                            key, "SHOW CONFIRMED (consumed)",
                            extra=(f"attempt={_att}" if _att else ""))
                elif kind == "confirm_end":
                    if self.snap_engine.confirm_show_end():
                        self._snap_show_stage("end", "SHOW CONFIRMED (consumed)")
                elif kind == "fail":
                    _att = self.snap_engine.show_attempt(key)
                    if self.snap_engine.fail_show(key, time.time(), reason):
                        self._snap_show_stage(
                            key, "SHOW FAILED — re-armed for retry",
                            extra=(f"reason={reason or '?'} attempt={_att} "
                                   f"max={TV_SNAP_SHOW_MAX_RETRIES}"))
                elif kind == "fail_end":
                    _lvl = key or self._snap_end_dispatch_lvl or "end90"
                    if self.snap_engine.fail_show_end(_lvl, time.time(), reason):
                        self._snap_show_stage(
                            "end", "SHOW FAILED (end) — re-armed",
                            extra=f"lvl={_lvl} reason={reason or '?'}")
        except Exception:
            pass

    # =================================================================
    # v2.0.5 — CREST SIGNAL BANNER + BALL-LINK WATCHDOG
    # (see the CREST BANNER block above snap_overlay_geometry)
    # =================================================================
    def _crest_banner_reset(self):
        """New match — the banner may fire exactly once per match."""
        self._crest_banner_shown = False
        self._crest_banner_deadline = None
        self._crest_banner_noted = set()

    def _ball_link_verify(self, m_state: Optional[str] = None):
        """v2.0.5 — run GameEngine.verify_ball_link() and report every
        state CHANGE (to stdout/backend_log.txt + the debug log). Any
        're-adopt'/'reinstall' proves the shared hook had been broken by
        another tool and was repaired automatically.
        v2.0.6 — the bridge owns the hook bytes now, so this also reports
        WHICH feed we read (buffer address) and how STALE the ball data is
        (user field report: 'charts visible but empty' — a stale feed line
        in backend_log.txt is the direct evidence of where it died).
        v2.0.7 — STALE is no longer a dead end: while PLAYING, a feed
        frozen for FEED_HEAL_AFTER_SEC triggers an ARBITRATED RESET —
        a hook_reset_request to the bridge (restore bytes + rebuild the
        hook), then this process adopts the buffer the bridge hands back.
        Throttled to one attempt per FEED_HEAL_RETRY_SEC."""
        try:
            st = self.engine.verify_ball_link()
        except Exception as e:
            st = f"error:{type(e).__name__}"
        if st != self._ball_link_last_state:
            prev, self._ball_link_last_state = self._ball_link_last_state, st
            try:
                self.dbg.event("BALL_LINK", state=str(st), prev=str(prev))
            except Exception:
                pass
            mode = ("bridge" if getattr(self.engine,
                                         "ball_hook_via_bridge", False)
                    else "local")
            print(f"[BALL LINK] {st} (mode={mode}, buffer="
                  f"0x{int(self.engine.ball_data_addr or 0):X})", flush=True)
            if str(st).startswith(("re-adopt", "reinstall", "reset-rehooked")):
                print("[BALL LINK] shared ball hook was broken — repaired "
                      "through the bridge, data feed restored",
                      flush=True)
            elif st in ("install-fail", "signature-mismatch",
                        "install-fail(bridge)") or "bridge-lost" in str(st):
                print("[BALL LINK] repair FAILED — charts will have no "
                      "ball data until the next successful retry",
                      flush=True)
        # --- v2.0.7 — one-shot byte-level evidence of the buffer content
        if (not getattr(self, "_ball_buf_dumped", False)
                and self.engine.ball_data_addr and self.engine.h_process):
            try:
                raw = safe_read(self.engine.h_process,
                                self.engine.ball_data_addr, 16)
                print(f"[BALL FEED] buffer 0x{self.engine.ball_data_addr:X} "
                      f"first16={raw.hex(' ') if raw else '<unreadable>'} "
                      "(all-zero here means the hook has never captured "
                      "XMM0 — patch not executing)", flush=True)
            except Exception:
                pass
            self._ball_buf_dumped = True
        # --- [suite v2.1.5] TIME-LINK WATCHDOG — the shared time hook is
        # kept alive exactly like the ball link: status + re-request
        # through the bridge; the bytes are the bridge's, never ours.
        try:
            if (getattr(self.engine, "time_hook_via_bridge", False)
                    and getattr(self.engine, "is_ready", False)):
                _tst = self.engine._bridge_verify_time_hook()
                if _tst != getattr(self, "_time_link_last_state", None):
                    self._time_link_last_state = _tst
                    print(f"[TIME LINK] {_tst} (mode=bridge)", flush=True)
        except Exception:
            pass
        # --- ball feed freshness (same 2 s cadence) ---
        try:
            age = time.time() - float(getattr(self, "_ball_feed_change_t", 0.0)
                                      or 0.0)
            stale = (self.engine.ball_data_addr and age > 15.0)
            if stale and self._ball_feed_stale_warned is None:
                self._ball_feed_stale_warned = True
                print(f"[BALL FEED] STALE for {age:.0f}s (buffer "
                      f"0x{int(self.engine.ball_data_addr):X}) — no ball "
                      "coordinates are arriving; charts would be empty.",
                      flush=True)
            elif age <= 1.0 and self._ball_feed_stale_warned:
                self._ball_feed_stale_warned = None
                self._feed_heal_last_wall = 0.0
                print("[BALL FEED] fresh again — ball coordinates are "
                      "arriving", flush=True)
            # --- v2.0.7 — ARBITRATED SELF-HEAL (bridge mode, PLAYING only:
            # during stoppages the ball legitimately does not move) ---
            if (stale and m_state == "PLAYING"
                    and getattr(self.engine, "ball_hook_via_bridge", False)
                    and age > FEED_HEAL_AFTER_SEC
                    and time.time() - getattr(self, "_feed_heal_last_wall",
                                              0.0) > FEED_HEAL_RETRY_SEC):
                self._feed_heal_last_wall = time.time()
                print(f"[BALL FEED] frozen {age:.0f}s while PLAYING — "
                      "sending hook_reset_request to the bridge "
                      "(restore bytes + rebuild the hook)", flush=True)
                try:
                    self.dbg.event("BALL_FEED_HEAL", age=round(age, 1))
                except Exception:
                    pass
                try:
                    buf = self.engine.reset_ball_hook_via_bridge()
                except Exception as e:
                    buf = None
                    print(f"[BALL FEED] reset request errored: "
                          f"{type(e).__name__}: {e}", flush=True)
                if buf:
                    self._ball_feed_last = None      # force a fresh sample
                    self._ball_feed_change_t = time.time()
                    self._ball_link_last_state = None  # re-report next tick
                    print(f"[BALL FEED] bridge rebuilt the hook — now "
                          f"reading buffer 0x{int(buf):X} "
                          "(reset-rehooked via arbitration)", flush=True)
                else:
                    err = getattr(self.engine.bridge_client, "last_error", "")
                    print(f"[BALL FEED] reset request refused/failed "
                          f"({err or 'not bridge-managed'}) — will retry",
                          flush=True)
        except Exception:
            pass
        return st

    def _crest_banner_tick(self, total_t, m_state):
        """Worker-side banner state machine (thread-safe: every renderer
        call below is just a message-queue put — same mechanism the
        chart path uses). Called from _snapshot_tick on every poll."""
        gpu = getattr(self, "_snap_gpu", None)
        if gpu is None:
            return
        now = time.time()
        # --- phase 2: auto-hide after the on-screen duration ---
        if self._crest_banner_deadline is not None:
            if now >= self._crest_banner_deadline:
                self._crest_banner_deadline = None
                try:
                    gpu.hide_now()
                    print(f"[CREST BANNER] hidden after "
                          f"{CREST_BANNER_SECONDS:.0f}s — overlay pipeline "
                          "VERIFIED on the exact chart rectangle",
                          flush=True)
                except Exception:
                    pass
            return
        if self._crest_banner_shown:
            return
        # --- trigger conditions (first minute of a match, PLAYING) ---
        if m_state != "PLAYING":
            return
        try:
            t = float(total_t)
        except (TypeError, ValueError):
            return
        if t > CREST_BANNER_WINDOW_SEC:
            if "late" not in self._crest_banner_noted:
                self._crest_banner_noted.add("late")
                print("[CREST BANNER] first minute over — banner was NOT "
                      "shown (teams unknown or display path dead; charts "
                      "will likely be empty/absent too)", flush=True)
            return
        if t < CREST_BANNER_MIN_T_SEC:
            return
        try:
            if self._snap_state in (SnapshotState.SHOWING,
                                    SnapshotState.VISIBLE):
                return   # a real chart is on screen — never fight it
        except Exception:
            pass
        # --- team crests (identity slots + Football_Database files) ---
        try:
            home_ident = self._team_ident_last.get("home")
            away_ident = self._team_ident_last.get("away")
            p_home = self.team_tracker.logo_path_for(home_ident)
            p_away = self.team_tracker.logo_path_for(away_ident)
        except Exception:
            home_ident = away_ident = p_home = p_away = None
        if p_home is None or p_away is None:
            return   # identity not resolved yet — keep waiting in-window
        img = _build_crest_banner_image(p_home, p_away)
        if img is None:
            if "img" not in self._crest_banner_noted:
                self._crest_banner_noted.add("img")
                print(f"[CREST BANNER] crest files unreadable "
                      f"(home={p_home} away={p_away})", flush=True)
            return
        try:
            disp, arr, geo = snap_prepare_display(img, *self._snap_screen)
        except Exception:
            disp = arr = geo = None
        if disp is None or arr is None or not geo:
            return
        x, y, w, h = geo
        try:
            gpu.upload_png_rgba(arr.tobytes(), w, h, x, y, 0,
                                CREST_BANNER_KEY)
            gpu.show(dur_ms=0, key=CREST_BANNER_KEY)
            self._crest_banner_shown = True
            self._crest_banner_deadline = now + CREST_BANNER_SECONDS
            print(f"[CREST BANNER] visible at t={t:.0f}s — both team "
                  f"crests side-by-side in the chart corner (home={home_ident} "
                  f"away={away_ident}); auto-hide in "
                  f"{CREST_BANNER_SECONDS:.0f}s. Hook + display pipeline "
                  "verified.", flush=True)
        except Exception as e:
            self._crest_banner_shown = True   # never retry-loop
            print(f"[CREST BANNER] show failed: "
                  f"{type(e).__name__}: {e}", flush=True)

    def _snapshot_tick(self, total_t, m_state, now_wall):
        """تیک ماشین حالت اسنپ‌شات — هر تیک Worker (حتی خارج از PLAYING).
        نسخهٔ ۱۰٫۱۵ — «preload/preload_end»: ۱-۲ ثانیه قبل از لحظهٔ نمایش،
        رندر + ساخت پنجرهٔ زیرِ صفحه انجام می‌شود تا ورود بدون لگ باشد.
        نسخهٔ ۱۰٫۱۸ — ابزار دقیق (بند ۱/۲/۴ کاربر): کل مسیر Worker
        (Render/Resize/Premultiply/Cached-check) با perf_counter ثبت می‌شود؛
        در لحظهٔ Show هیچ Render/Resize/I/O پنهانی انجام نمی‌شود — اگر کش
        آماده نبود، با [SNAPSHOT WARNING] شفاف ثبت می‌شود.
        v10.28 — چرخهٔ تراکنشی (پورت v1.3 از 2017): رویدادهای confirm/fail
        اول drain می‌شوند؛ صدور («show», key) دیگر کلید را مصرف نمی‌کند
        (مصرف = تأیید SHOWING). اگر dispatch/UI گم شود، مهلت
        TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC پاس شود و همان کلید خودکار Retry
        می‌شود — بدون ری‌استارت بازی."""
        self._snap_drain_show_events()
        # --- v10.28 — دیده‌بانی «مسدود توسط نیمه»: اگر ساعت از هدف گذشته
        # ولی half هنوز به مقدار لازم نرسیده، یک‌بار لاگ می‌شود تا در آزمون
        # میدانی معلوم شود مشکل از ماشین فاز است نه مسیر Show.
        try:
            _t = float(total_t) if total_t is not None else None
        except (TypeError, ValueError):
            _t = None
        if _t is not None:
            for _bkey, _need in (("h1", (1,)), ("h2", (2,)), ("et", (2, 3, 4))):
                _bst = self.snap_engine.mid.get(_bkey)
                if not _bst or _bst.get("shown") or _bst.get("show_state"):
                    continue
                if not self.snap_engine.s.get(f"{_bkey}_enabled"):
                    continue
                if int(self.half_number or 1) in _need:
                    continue
                if _t >= self.snap_engine.target_minute(_bkey) * 60.0:
                    if _bkey not in self._snap_half_block_noted:
                        self._snap_half_block_noted.add(_bkey)
                        self._snap_show_stage(
                            _bkey, "SHOW BLOCKED (half not reached yet)",
                            extra=(f"half={self.half_number} need={list(_need)} "
                                   f"t={_fmt_clock(_t)} — waiting for phase "
                                   "machine (time-drop verdict)"))
        try:
            acts = self.snap_engine.tick(total_t, m_state, self.half_number,
                                         now_wall)
        except Exception as ex:
            clog(f"[SnapShot] [engine] tick error: {type(ex).__name__}: {ex}")
            return
        for kind, key in acts:
            try:
                if kind == "show_abandoned":
                    # v10.28 — سقف تلاش‌ها پر شد؛ نمایش رها می‌شود (یک‌بار لاگ)
                    if key not in self._snap_abandon_noted:
                        self._snap_abandon_noted.add(key)
                        self._snap_show_stage(
                            key, "SHOW ABANDONED (max retries reached)",
                            extra=(f"max={TV_SNAP_SHOW_MAX_RETRIES} "
                                   f"last_fail="
                                   f"{self.snap_engine.mid.get(key, {}).get('last_fail', '')}"))
                elif kind == "capture":
                    # نسخهٔ ۱۰٫۲۱ — تست ۶: شروع چرخهٔ عمر این Snapshot
                    self._snap_life_mark(key, "CAPTURE REQUESTED (engine act)")
                    tr = SnapShowTrace("CAPTURE (target-1min) DEBUG",
                                       TV_SNAP_SHOW_DEBUG)
                    path = self._snapshot_tmp_path(key)
                    t0 = tr.begin()
                    img = self._snapshot_render_current(out_path=path)
                    tr.end("Render (worker: matplotlib+draw+buffer)", t0,
                           size=(getattr(img, "width", 0) or 0,
                                 getattr(img, "height", 0) or 0))
                    tr.finish()
                    self._snap_capture_cache[key] = img
                    self._snap_life_mark(
                        key, "CAPTURE RENDERED (worker)",
                        note=f"{getattr(img, 'width', 0)}x"
                             f"{getattr(img, 'height', 0)}")
                elif kind == "preload":
                    # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری میان‌بازی
                    # نسخهٔ ۱۰٫۱۹ — مسیر یکپارچهٔ dispatch (act + self-heal
                    # retry هر دو از همین متد می‌روند)
                    # نسخهٔ ۱۰٫۲۱ — تست ۶: مرحلهٔ PRELOAD REQUESTED
                    self._snap_life_mark(key, "PRELOAD REQUESTED (engine act)")
                    self._snapshot_preload_dispatch(key, "PRELOAD DEBUG",
                                                    at_end=False)
                elif kind == "preload_end":
                    # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری نمایش پایان (~۲ ثانیه قبل
                    # از تأیید توقفِ پایان)
                    self._snap_life_mark("end", "PRELOAD REQUESTED (engine act)")
                    self._snapshot_preload_dispatch("end", "PRELOAD-END DEBUG",
                                                    at_end=True)
                elif kind == "show":
                    # نسخهٔ ۱۰٫۱۸ — لحظهٔ نمایش: فقط «پنجرهٔ آماده» جابه‌جا
                    # می‌شود؛ هر عمل سنگین این‌جا باید با لاگ شفاف دیده شود
                    # نسخهٔ ۱۰٫۲۱ — تست ۶: SHOW REQUESTED (از Worker)
                    self._snap_life_mark(key, "SHOW REQUESTED (engine act)")
                    tr = SnapShowTrace("SHOW DEBUG", TV_SNAP_SHOW_DEBUG)
                    tr.step("Show request received")
                    t0 = tr.begin()
                    img = self._snap_capture_cache.get(key)
                    tr.end("Cached image check", t0,
                           note=("hit" if img is not None else "MISS"))
                    # نسخهٔ ۱۰٫۱۹ — فقط وضعیت «ready» صریح پذیرفته می‌شود
                    pre_ready = (getattr(self, "_snap_pre", None) is not None
                                 and self._snap_pre.get("key") == key
                                 and self._snap_pre.get("state") == "ready")
                    if img is None:
                        # بند ۴ کاربر — رندر سنگین هرگز نباید پنهان باشد
                        # (نسخهٔ ۱۰٫۲۴ — فقط با TV_SNAP_SHOW_DEBUG)
                        if TV_SNAP_SHOW_DEBUG:
                            print("[SNAPSHOT WARNING] Cached image was NOT ready "
                                  "at show time (key=" + str(key) + ")",
                                  flush=True)
                        t1 = tr.begin()
                        path = self._snapshot_tmp_path(key)
                        if not os.path.isfile(path):
                            img = self._snapshot_render_current(out_path=path)
                            self._snap_capture_cache[key] = img
                        tr.end("Emergency render/pick (worker)", t1,
                               note="preload failed — investigate PRELOAD log")
                    else:
                        tr.step("Image validation",
                                note="cache hit — no disk I/O at show time")
                    path = self._snapshot_tmp_path(key)
                    if pre_ready:
                        # پنجرهٔ پیش‌ساختهٔ همان کلید زنده است → هیچ آماده‌سازی
                        # پیکسلی در لحظهٔ Show لازم نیست (بند ۳ کاربر)
                        tr.step("Prepare display (worker)",
                                note="skipped — prebuilt window ready")
                        ui_img, payload = None, None
                    else:
                        t2 = tr.begin()
                        disp, arr, geo = snap_prepare_display(
                            img, *self._snap_screen)
                        tr.end("Prepare display (worker)", t2,
                               note="NO prebuilt window — fallback prepare")
                        ui_img = disp if disp is not None else img
                        payload = (disp, arr, geo) if disp is not None else None
                    secs = snap_clamp_seconds(
                        self.snap_engine.s.get("show_seconds"))
                    tr.step("Dispatch show to UI (after)")
                    # v10.28 — REQUESTED + QUEUED با شماره تلاش؛ اگر صف
                    # after شکست خورد، بلافاصله fail → تلاش مجدد خودکار
                    _att = self.snap_engine.show_attempt(key)
                    self._snap_show_stage(
                        key, "TARGET REACHED → SHOW REQUESTED (engine)",
                        extra=(f"t={_fmt_clock(_t if _t is not None else total_t)} "
                               f"half={self.half_number} attempt={_att} "
                               f"pre={('ready' if pre_ready else 'MISS')}"))
                    sent = time.perf_counter()
                    _qok = self._ui_post(self._show_snapshot_overlay, ui_img,
                                         path, secs, False, payload, tr,
                                         sent, key)
                    self._save_shown_chart_copy(key, path)
                    if _qok:
                        self._snap_show_stage(
                            key, "SHOW QUEUED TO UI (after(0) scheduled)",
                            extra=f"attempt={_att}")
                    else:
                        self._snap_show_event(
                            "fail", key, "ui-queue-failed (after() raised)")
                elif kind == "show_end":
                    # نسخهٔ ۱۰٫۲۱ — تست ۶: SHOW REQUESTED (پایان بازی)
                    self._snap_life_mark("end", "SHOW REQUESTED (engine act)")
                    tr = SnapShowTrace("SHOW-END DEBUG", TV_SNAP_SHOW_DEBUG)
                    tr.step("Show request received")
                    t0 = tr.begin()
                    img = self._snap_capture_cache.get("end")
                    tr.end("Cached image check", t0,
                           note=("hit" if img is not None else "MISS"))
                    pre_ready = (getattr(self, "_snap_pre", None) is not None
                                 and self._snap_pre.get("key") == "end"
                                 and self._snap_pre.get("state") == "ready")
                    if img is None:
                        if TV_SNAP_SHOW_DEBUG:
                            print("[SNAPSHOT WARNING] Cached image was NOT ready "
                                  "at show time (key=end)", flush=True)
                        t1 = tr.begin()
                        path = self._snapshot_tmp_path("end")
                        if not os.path.isfile(path):
                            img = self._snapshot_render_current(out_path=path)
                            self._snap_capture_cache["end"] = img
                        tr.end("Emergency render/pick (worker)", t1,
                               note="preload failed — investigate PRELOAD log")
                    else:
                        tr.step("Image validation",
                                note="cache hit — no disk I/O at show time")
                    path = self._snapshot_tmp_path("end")
                    if pre_ready:
                        tr.step("Prepare display (worker)",
                                note="skipped — prebuilt window ready")
                        ui_img, payload = None, None
                    else:
                        t2 = tr.begin()
                        disp, arr, geo = snap_prepare_display(
                            img, *self._snap_screen)
                        tr.end("Prepare display (worker)", t2,
                               note="NO prebuilt window — fallback prepare")
                        ui_img = disp if disp is not None else img
                        payload = (disp, arr, geo) if disp is not None else None
                    secs = snap_clamp_seconds(
                        self.snap_engine.s.get("end_seconds"))
                    tr.step("Dispatch show to UI (after)")
                    # v10.28 — سطح در پرواز ثبت می‌شود تا fail_end بداند کدام
                    # سطح را بازمسلح کند (end90/end120)
                    self._snap_end_dispatch_lvl = key
                    self._snap_show_stage(
                        "end", "END SHOW REQUESTED (engine)",
                        extra=(f"lvl={key} t={_fmt_clock(_t if _t is not None else total_t)} "
                               f"pre={('ready' if pre_ready else 'MISS')}"))
                    sent = time.perf_counter()
                    _qok = self._ui_post(self._show_snapshot_overlay, ui_img,
                                         path, secs, True, payload, tr, sent,
                                         "end")
                    self._save_shown_chart_copy(key, path)
                    if _qok:
                        self._snap_show_stage(
                            "end", "SHOW QUEUED TO UI (after(0) scheduled)",
                            extra=f"lvl={key}")
                    else:
                        self._snap_show_event(
                            "fail_end", key,
                            "ui-queue-failed (after() raised)")
            except Exception as ex:
                clog(f"[SnapShot] {kind}/{key}: {type(ex).__name__}: {ex}")
                # v10.28 — شکست خودِ پردازش action در Worker هم fail می‌شود
                if kind == "show" and key in ("h1", "h2", "et"):
                    self._snap_show_event(
                        "fail", key,
                        f"worker-act-error: {type(ex).__name__}: {ex}")
                elif kind == "show_end":
                    self._snap_show_event(
                        "fail_end", self._snap_end_dispatch_lvl or key,
                        f"worker-act-error: {type(ex).__name__}: {ex}")
        # نسخهٔ ۱۰٫۱۹ — self-heal پیش‌بارگذاری: اگر پنجرهٔ پیش‌ساخته آماده
        # نبود، تا «قبل» از لحظهٔ نمایش دوباره تلاش می‌شود (محدود نرخ)
        self._snapshot_preload_selfheal(total_t, now_wall)

    def _snapshot_preload_dispatch(self, key, trace_title, at_end: bool,
                                   reason: str = ""):
        """مسیر یکپارچهٔ Preload پنجره (act «preload/preload_end» موتور و
        self-heal retry هر دو از همین‌جا می‌روند) — از ترد Worker:
          ۱) تصویر از کش (یا رندر اگر نبود — همان قرارداد قبلی)
          ۲) LANCZOS resize + پیش‌ضرب آلفا (خارج از UI-Thread)
          ۳) dispatch ساخت پنجره به UI-Thread (زیرِ صفحه)
        همهٔ کارهای سنگین «قبل» از لحظهٔ Show انجام می‌شود؛ در لحظهٔ Show
        فقط show/position/animation باقی می‌ماند (بند ۳/۴ کاربر).
        reason: اگر retry self-heal باشد، علت در لاگ می‌آید."""
        try:
            if getattr(self, "_closing", False):
                return
            # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] PRELOAD START (EMPTY → PREPARING)
            self._snap_state_event(
                "PRELOAD START", SnapshotState.PREPARING, key=key,
                extra=(f"reason={reason}" if reason
                       else "engine preload window"))
            tr = SnapShowTrace(trace_title, TV_SNAP_SHOW_DEBUG)
            if reason:
                tr.step("Preload re-dispatch (self-heal)", note=reason)
            path = self._snapshot_tmp_path(key)
            t0 = tr.begin()
            img = self._snap_capture_cache.get(key)
            if img is None or not os.path.isfile(path):
                img = self._snapshot_render_current(out_path=path)
                self._snap_capture_cache[key] = img
            tr.end("Render (worker: matplotlib+draw+buffer)", t0,
                   size=(getattr(img, "width", 0) or 0,
                         getattr(img, "height", 0) or 0))
            t1 = tr.begin()
            # --- نسخهٔ ۱۰٫۲۴ — مسیر برداری GPU: scene در Worker ساخته می‌شود
            # (خارج از لحظهٔ Show)؛ LANCZOS/premultiply/matplotlib-draw از
            # مسیر نمایش حذف می‌شوند. شکست → مسیر بیت‌مپ قبلی.
            scene = None
            if (getattr(self, "_snap_gpu", None) is not None
                    and self._snap_gpu.is_alive()
                    and getattr(self._snap_gpu, "supports_scene", True)):
                try:
                    scene = self._build_gpu_scene_now()
                except Exception:
                    scene = None
            if scene is not None:
                tr.end("GPU vector scene build (worker — no matplotlib)",
                       t1, size=(scene["W"], scene["H"]),
                       note=(f"items={scene['n_items']} "
                             f"verts={scene['n_verts']}"))
                disp, arr, geo = None, None, None
            else:
                disp, arr, geo = snap_prepare_display(img, *self._snap_screen)
                tr.end("Prepare display (LANCZOS resize + premultiply)", t1,
                       size=((geo[2], geo[3]) if geo else None))
            tr.step("Dispatch build-window to UI (after)")
            try:
                self._snap_pre_build_gen += 1
                gen = self._snap_pre_build_gen
            except Exception:
                gen = None
            try:
                self._snap_pre_retry_wall[key] = time.time()
            except Exception:
                pass
            # نسخهٔ ۱۰٫۲۱ — تست ۶: PRELOAD DISPATCHED → صف UI + ثبت زمان
            # ارسال (برای تشخیص «صف بیش از 1s اجرا نشد» در self-heal)
            try:
                self._snap_life_mark(key, "PRELOAD DISPATCHED → UI queue",
                                     note=f"build_gen={gen}")
                self._snap_pre_dispatch_wall[key] = time.time()
                self._snap_pre_pending_key = key
            except Exception:
                pass
            if disp is not None:
                self._ui_post(self._prepare_snapshot_overlay, disp, path,
                              at_end, (disp, arr, geo), tr, key, gen, None)
            else:
                self._ui_post(self._prepare_snapshot_overlay, img, path,
                              at_end, None, tr, key, gen, scene)
        except Exception as ex:
            clog(f"[SnapPreload] {key}: {type(ex).__name__}: {ex}")
            try:
                self._snap_pre_fail = {
                    "key": key,
                    "reason": (f"worker dispatch failed: "
                               f"{type(ex).__name__}: {ex}"),
                    "wall": time.time()}
            except Exception:
                pass

    def _snap_pre_ready_for(self, key) -> bool:
        """بررسی آمادگی پنجرهٔ پیش‌ساخته از دید Worker (بدون هیچ فراخوانی Tk):
        وضعیت صریح «ready» + همان کلید + پنجره موجود."""
        pre = getattr(self, "_snap_pre", None)
        # نسخهٔ ۱۰٫۲۳ — معماری GPU: prebuilt بدون پنجرهٔ Tk هم معتبر است
        return bool(pre is not None
                    and pre.get("key") == key
                    and pre.get("state") == "ready"
                    and (pre.get("win") is not None
                         or pre.get("gpu") is True))

    def _snap_pre_fail_reason_text(self, key) -> str:
        """آخرین دلیل شکست Preload برای کلید (برای لاگ self-heal/Show)."""
        f = getattr(self, "_snap_pre_fail", None)
        if f and f.get("key") in (None, key) and f.get("reason"):
            return f"previous attempt failed — {f.get('reason')}"
        return "previous attempt did not produce a ready window"

    @staticmethod
    def _preload_not_ready_print(reason: str) -> None:
        """بلوک لاگ «NOT READY» با دلیل دقیق (بند ۷ کاربر).
        نسخهٔ ۱۰٫۲۴ — فقط با TV_SNAP_SHOW_DEBUG چاپ می‌شود (حذف لاگ کنسول)."""
        if not TV_SNAP_SHOW_DEBUG:
            return
        try:
            print("=" * 60, flush=True)
            print("[SNAPSHOT PRELOAD]", flush=True)
            print("Window state: NOT READY", flush=True)
            print(f"Reason: {reason}", flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass

    def _snapshot_preload_selfheal(self, total_t, now_wall):
        """نسخهٔ ۱۰٫۱۹ — ترمیم خودکار Preload (شرط کاربر: «اگر Window باید
        Rebuild شود، این کار باید قبل از زمان Show بعدی انجام شود»):
          * اگر پنجرهٔ پیش‌ساختهٔ کلید آماده نیست (ساخت UI شکست خورده/
            دیر اجرا شده/پنجره نابود شده)، دوباره dispatch می‌شود —
            با محدود نرخ و فقط تا TV_SNAP_PRELOAD_MIN_REMAIN_SEC
            قبل از لحظهٔ نمایش (ساخت در لحظهٔ Show دیگر معنا ندارد)؛
          * زمان‌بندی/تریگر موتور دست‌نخورده است — این مسیر فقط «بک‌فیلِ»
            idempotent است و وقتی پنجره آماده است کاری نمی‌کند.
        نسخهٔ ۱۰٫۲۱ — تست ۶ (Race واقعی کاربر: «PRELOAD UI CALLBACK هرگز
        قبل از Show اجرا نشد»):
          ۱) دیگر شرط «فلگ pre ست شده باشد» لازم نیست — اگر تیک Worker از
             پنجرهٔ preload پریده باشد (فلگ pre هرگز ست نشده)، همین‌جا
             backfill می‌شود (علت در reason لاگ می‌شود)؛
          ۲) اگر صف ساخت بیش از 1.0s بدون اجرا مانده باشد (UI-Thread
             مشغول/کال‌بک گم‌شده)، برای «همان کلید» دوباره dispatch
             می‌شود (supersede — ساخت قدیمی خودش را باطل می‌کند).
        نسخهٔ ۱۰٫۲۲ — Snapshot Window Lifecycle Manager (اولویت ۱/۲
        گزارش فنی کاربر): پنجرهٔ «آستانه‌ای پهن» — برای میان‌بازی‌ها
        dispatch از «هدف − TV_SNAP_PRELOAD_WIDE_LEAD_SEC (۱۰s)» باز
        می‌شود (if match_time >= preload_start — مشخصات کاربر):
        دیگر پنجرهٔ ۲ ثانیه‌ایِ تک‌شانس نیست؛ حتی اگر UI/Worker در
        پنجرهٔ باریک گیر کند، تلاش‌های نرخ‌محدود ۰٫۵s چند ثانیه
        فرصت دارند. امن بودن محتوا: تصویر میان‌بازی همان PNG کپچرشدهٔ
        T-60s است (کش ثابت) → ساخت زودترِ پنجره محتوای نمایش را
        تغییر نمی‌دهد. نمایش «پایان» عمداً پنجرهٔ باریک قبلی را
        دارد (رندرش به لحظهٔ توقف وابسته است)."""
        try:
            if getattr(self, "_closing", False):
                return
            eng = self.snap_engine
            now = float(now_wall) if now_wall is not None else time.time()
            try:
                t = float(total_t) if total_t is not None else None
            except (TypeError, ValueError):
                t = None
            # نسخهٔ ۱۰٫۲۱ — «در حال ساخت» دیگر مهلت مطلق نیست: اگر صف بیش
            # از 1.0s بدون اجرا بماند، برای همان کلید دوباره dispatch می‌شود
            in_flight = (getattr(self, "_snap_pre_build_gen", 0)
                         > getattr(self, "_snap_pre_built_gen", 0))
            pending_key = getattr(self, "_snap_pre_pending_key", None)

            def _in_flight_block(key) -> Optional[str]:
                """اگر صف ساخت جلوی dispatchِ این کلید را بگیرد، دلیل را
                برمی‌گرداند (None = اجازهٔ dispatch)."""
                if not in_flight:
                    return None
                if pending_key != key:
                    return "another key's build is in flight"
                dw = self._snap_pre_dispatch_wall.get(key, 0.0)
                if (now - dw) < 1.0:
                    return "queued build still fresh (<1.0s)"
                return None          # گیرکرده → اجازهٔ re-dispatch (supersede)

            # ---------- میان‌بازی ----------
            for key in TV_SNAP_KEYS:
                st = eng.mid.get(key)
                # نسخهٔ ۱۰٫۲۱ — فلگ pre دیگر شرط نیست (پرش تیک از پنجرهٔ
                # ۲ ثانیه‌ای هم باید backfill شود)
                if st is None or st.get("shown"):
                    continue
                if t is None:
                    continue
                tgt = eng.target_minute(key) * 60.0
                # نسخهٔ ۱۰٫۲۲ — پنجرهٔ آستانه‌ای پهن (اولویت ۱ کاربر):
                # if match_time >= preload_start → هر تیک بعد از آستانه
                # شانس dispatch دارد (نه فقط پنجرهٔ ۲ ثانیه‌ای تک‌شانس).
                if not ((tgt - TV_SNAP_PRELOAD_WIDE_LEAD_SEC) <= t
                        < (tgt - TV_SNAP_PRELOAD_MIN_REMAIN_SEC)):
                    continue
                if self._snap_pre_ready_for(key):
                    continue
                _blk = _in_flight_block(key)
                if _blk is not None:
                    continue
                if now - self._snap_pre_retry_wall.get(key, 0.0) \
                        < TV_SNAP_PRELOAD_RETRY_MIN_GAP_SEC:
                    continue
                if not st.get("pre"):
                    _reason = ("engine pre flag was never set — worker "
                               "tick skipped the preload window "
                               "(timer jump?) — threshold backfill "
                               "dispatch (wide window T-"
                               f"{TV_SNAP_PRELOAD_WIDE_LEAD_SEC:.0f}s)")
                else:
                    dw = self._snap_pre_dispatch_wall.get(key, 0.0)
                    if in_flight and pending_key == key:
                        _reason = ("queued build did not execute within "
                                   "1.0s (UI thread busy or callback "
                                   "lost) — re-dispatch (supersede)")
                    else:
                        _reason = self._snap_pre_fail_reason_text(key)
                self._snapshot_preload_dispatch(
                    key, "PRELOAD-RETRY DEBUG", at_end=False,
                    reason=_reason)
            # ---------- پایان بازی ----------
            if eng.s.get("end_enabled"):
                for lvl in ("end120", "end90"):
                    st = eng.end.get(lvl)
                    if st is None or st.get("shows", 0):
                        continue
                    stop_since = st.get("stop_since")
                    if stop_since is None:
                        continue
                    elapsed = now - stop_since
                    if not ((TV_SNAP_END_STOP_CONFIRM_SEC
                             - TV_SNAP_PRELOAD_LEAD_SEC) <= elapsed
                            < (TV_SNAP_END_STOP_CONFIRM_SEC
                               - TV_SNAP_PRELOAD_MIN_REMAIN_SEC)):
                        continue
                    if self._snap_pre_ready_for("end"):
                        continue
                    _blk = _in_flight_block("end")
                    if _blk is not None:
                        continue
                    if now - self._snap_pre_retry_wall.get("end", 0.0) \
                            < TV_SNAP_PRELOAD_RETRY_MIN_GAP_SEC:
                        continue
                    if in_flight and pending_key == "end":
                        _reason = ("queued build did not execute within "
                                   "1.0s (UI thread busy or callback "
                                   "lost) — re-dispatch (supersede)")
                    else:
                        _reason = self._snap_pre_fail_reason_text("end")
                    self._snapshot_preload_dispatch(
                        "end", "PRELOAD-RETRY-END DEBUG", at_end=True,
                        reason=_reason)
        except Exception:
            pass

    def _export_match_archive(self) -> Optional[str]:
        """نسخهٔ ۱۰٫۲۴ — خروجی کامل رخدادهای بازی (ZIP) از وضعیت فعلی.
        از ترد Worker فراخوانی می‌شود (پایان بازی/دکمهٔ دستی) — هیچ Tk.
        خروجی: مسیر ZIP یا None."""
        try:
            teams = {}
            for side in ("home", "away"):
                ident = self._team_ident_last.get(side)
                teams[side] = {
                    "ident": ([int(ident)] if isinstance(ident, int)
                              else ([int(ident[0]), int(ident[1])]
                                    if ident and len(ident) >= 2 else None)),
                    "label": _pt_team_label(ident, side),   # [PT v2.3.0]
                }
            return export_match_archive(
                self.momentum, snap_engine=self.snap_engine,
                seen_max_t=self._match_seen_max_t, teams=teams,
                colors=dict(self._chart_colors),
                bg_kind=self._tv_bg_kind_for_state(),
                settings=dict(self.snap_engine.s),
                tuning={"edge_smooth_px": float(TV_EDGE_SMOOTH_PX),
                        "glow_softness_mul": float(TV_GLOW_SOFTNESS_MUL),
                        "glow_intensity_mul": float(TV_GLOW_INTENSITY_MUL)},
                display_cfg=self.config,
                flag_images={"home": self._tv_flag_arr["home"],
                             "away": self._tv_flag_arr["away"]})
        except Exception:
            return None

    def _snapshot_finalize_previous_match(self):
        """«ذخیرهٔ دائمی نمودارها» — آخرین نمودار بازی قبلی، درست قبل از
        پاک‌شدن تاریخچه (تایمر به ۰۰:۰۰ ریست شده = شروع دست جدید) در
        Momentum_Saves با نام مخصوص خودش ذخیره می‌شود. (از Worker)
        نسخهٔ ۱۰٫۱۳ — فقط همین فایل دائمی مُهر تاریخ/ساعت دارد (کاربر:
        نموداری که روی صفحهٔ بازی می‌آید نباید مُهر داشته باشد).
        نسخهٔ ۱۰٫۲۴ — آرشیو کامل رخدادها (ZIP) «همیشه» قبل از هر چیز
        نوشته می‌شود (مستقل از permanent_save — درخواست صریح کاربر)."""
        s = self.snap_engine.s
        with self.momentum._lock:
            n_hist = len(self.momentum.history)
        if n_hist < 2 or self._match_seen_max_t < TV_SNAP_MIN_HIST_SEC:
            return    # بازی هنوز دادهٔ معناداری ندارد
        # --- نسخهٔ ۱۰٫۲۴ — آرشیو کامل رخدادها (خودکار — همیشه) ---
        try:
            self._export_match_archive()
        except Exception:
            pass
        if not s.get("permanent_save"):
            return
        img = self._snapshot_render_current(out_path=None, with_timestamp=True)
        if img is None:
            return
        save_dir = os.path.join(self._script_dir, TV_SNAP_SAVE_DIRNAME)
        os.makedirs(save_dir, exist_ok=True)
        w = self.snap_engine.match_start_wall
        stamp = time.strftime("%Y-%m-%d_%H-%M", time.localtime(w)) if w \
            else time.strftime("%Y-%m-%d_%H-%M")
        names = {}
        for side in ("home", "away"):
            ident = self._team_ident_last.get(side)
            names[side] = _pt_team_label(ident, side)   # [PT v2.3.0]
        base = f"momentum_{stamp}_{names['home']}_vs_{names['away']}"
        path = os.path.join(save_dir, base + ".png")
        n = 2
        while os.path.exists(path):
            path = os.path.join(save_dir, f"{base}_{n}.png")
            n += 1
        img.save(path)

    def _discard_snapshot_preload(self):
        """نسخهٔ ۱۰٫۱۵ — نابودی پنجرهٔ «پیش‌ساختهٔ» اسنپ‌شات (زیرِ صفحه).
        نسخهٔ ۱۰٫۲۲ — اگر پنجرهٔ پیش‌ساختهٔ «آماده» دور انداخته شد
        (retune/hide/reset)، ماشین حالت به EMPTY برمی‌گردد و لاگ می‌شود
        (self-heal پهن ۱۰٫۲۲ تا قبل از Show دوباره می‌سازد)."""
        pre = getattr(self, "_snap_pre", None)
        if pre is not None:
            try:
                self._snap_pre = None
                win = pre.get("win")
                if win is not None:
                    try:
                        win.destroy()
                    except Exception:
                        pass
            except Exception:
                pass
            self._snap_pre_photo = None
            # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] پنجرهٔ آماده دور انداخته شد
            self._snap_state_event(
                "PREBUILT DISCARDED", SnapshotState.EMPTY, key=None,
                extra="prebuilt window discarded (retune/hide/reset)",
                only_from=(SnapshotState.READY,))

    def _hide_snapshot_overlay(self, expect_win=None):
        """پنهان‌سازی نمودار روی صفحه.
        نسخهٔ ۱۰٫۱۷ — expect_win: اگر داده شود، فقط وقتی پنجرهٔ فعلی
        «همان» پنجره است نابود/لغو می‌شود؛ hideِ دیرهنگامِ یک نمودار
        قبلی (مثلاً after(0,hide) تردِ خروجِ قدیمی) دیگر نمی‌تواند
        پنجرهٔ نمودار تازه را نابود یا انیمیشنش را لغو کند.
        نسخهٔ ۱۰٫۲۳ — مسیر GPU: پنجره‌ای برای نابود کردن نیست؛ تایمرها
        لغو و سطح در همان فریم شفاف می‌شود (hide_now — یک پیام)."""
        # v10.29 — پنهان‌سازی انجام شد → ضرب‌الاجل نگهبان مدت نمایش نیز
        # باطل می‌شود (مسیرهای GPU و Tk هر دو از همین‌جا می‌گذرند)
        self._snap_overlay_deadline_wall = None
        if getattr(self, "_snap_gpu", None) is not None:
            return self._hide_snapshot_overlay_gpu(expect_win)
        win = getattr(self, "_snap_overlay", None)
        if expect_win is not None and win is not expect_win:
            return                      # پنجره عوض شده — دست به نسل جدید نمی‌زنیم
        # نسخهٔ ۱۰٫۱۳ — لغو تایمرهای انیمیشن در جریان قبل از نابودی پنجره
        for aid in list(getattr(self, "_snap_overlay_after", []) or []):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._snap_overlay_after = []
        # نسخهٔ ۱۰٫۱۶ — لغو ترد انیمیشن (نسل جدید + پرچم توقف؛ ترد daemon است
        # و با نسل جدید در همان فریم بعدی خارج می‌شود — بدون join مسدود)
        try:
            self._snap_anim_gen += 1
            self._snap_anim_alive = False
        except Exception:
            pass
        if win is not None:
            try:
                win.destroy()
            except Exception:
                pass
            self._snap_overlay = None
            self._snap_overlay_photo = None
            self._snap_overlay_state = None
            # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] پنهان‌سازی واقعی → EMPTY
            # (فقط وقتی overlay «دیده‌شدنی/در حال نمایش» بود — hideِ
            # لحظهٔ Show که پنجرهٔ قبلی ندارد، لاگ گمراه‌کننده نمی‌سازد)
            self._snap_state_event(
                "HIDDEN", SnapshotState.EMPTY, key=None,
                extra="overlay window destroyed",
                only_from=(SnapshotState.VISIBLE, SnapshotState.SHOWING))
        # نسخهٔ ۱۰٫۱۵ — پیش‌ساخته هم با پنهان‌سازی زنده باطل می‌شود
        self._discard_snapshot_preload()

    def _gpu_overlay_boot(self):
        """راه‌اندازی Renderer GPU — فقط «یک‌بار در شروع». تصمیم GPU/legacy
        هرگز در لحظهٔ Show گرفته نمی‌شود (هیچ ساختی هنگام نمایش انجام
        نمی‌شود). شکست → لاگ شفاف + مسیر قبلی (۱۰٫۲۲) برای «همین اجرا»."""
        self._snap_gpu = None
        if not TV_SNAP_GPU_OVERLAY:
            if TV_SNAP_SHOW_DEBUG:
                print("[OVERLAY_STATE] INIT SKIPPED — TV_SNAP_GPU_OVERLAY=0 "
                      "(legacy Tk layered path)", flush=True)
            # v2.0.1 — the legacy Tk path does not exist in this headless
            # build; the Win32 fallback IS the display path then.
            self._boot_win32_fallback()
            return
        try:
            sx, sy, sw_, sh_ = _gpu_surface_geo(*self._snap_screen)
        except Exception as ex:
            if TV_SNAP_SHOW_DEBUG:
                print(f"[OVERLAY_STATE] INIT SKIPPED — surface geo: {ex}",
                      flush=True)
            return
        try:
            rend = GPUOverlayRenderer(
                sx, sy, sw_, sh_,
                click_through=TV_SNAP_GPU_CLICKTHROUGH,
                vsync=TV_SNAP_GPU_VSYNC,
                anim_debug=TV_SNAP_GPU_ANIM_DEBUG)
        except Exception as ex:
            if TV_SNAP_SHOW_DEBUG:
                print(f"[OVERLAY_STATE] INIT FAILED — {type(ex).__name__}: {ex} "
                      "→ legacy Tk path", flush=True)
            return
        if not rend.wait_init(TV_SNAP_GPU_INIT_WAIT_SEC):
            err = rend.init_error() or "timeout waiting for GPU context"
            if TV_SNAP_SHOW_DEBUG:
                try:
                    print("=" * 60, flush=True)
                    print("[OVERLAY_STATE] INIT FAILED (GPU Overlay Renderer)",
                          flush=True)
                    print("=" * 60, flush=True)
                    print(f"Reason: {err}", flush=True)
                    print("Falling back to legacy Tk layered path (v10.22).",
                          flush=True)
                    print("برای فعال‌سازی معماری GPU اجرا کنید: "
                          "pip install moderngl glfw", flush=True)
                    print("=" * 60, flush=True)
                except Exception:
                    pass
            try:
                rend.shutdown(timeout=0.5)
            except Exception:
                pass
            return
        info = rend.init_info()
        if not info.get("transparent", False):
            if TV_SNAP_SHOW_DEBUG:
                try:
                    print("[OVERLAY_STATE] INIT FAILED — transparent "
                          "framebuffer not supported on this system "
                          "→ legacy Tk path", flush=True)
                except Exception:
                    pass
            try:
                rend.shutdown(timeout=0.5)
            except Exception:
                pass
            return
        self._snap_gpu = rend
        # v2.0.1 — GPU renderer booted OK; nothing else to do here.
        return

    def _boot_win32_fallback(self):
        """v2.0.1 — last-resort display path: a pure-Win32 layered-window
        renderer (no moderngl/glfw/Tk). Guarantees the charts can ALWAYS be
        displayed by this headless build; duck-types GPUOverlayRenderer so
        the whole show pipeline runs unchanged."""
        if self._snap_gpu is not None:
            return
        if sys.platform != "win32":
            if TV_SNAP_SHOW_DEBUG:
                print("[OVERLAY_STATE] Win32 fallback skipped "
                      "(non-Windows platform)", flush=True)
            return
        try:
            sx, sy, sw_, sh_ = _gpu_surface_geo(*self._snap_screen)
        except Exception as ex:
            if TV_SNAP_SHOW_DEBUG:
                print(f"[OVERLAY_STATE] Win32 fallback skipped — surface "
                      f"geo: {ex}", flush=True)
            return
        try:
            rend = Win32OverlayRenderer(
                sx, sy, sw_, sh_,
                click_through=TV_SNAP_GPU_CLICKTHROUGH,
                vsync=False,
                anim_debug=TV_SNAP_GPU_ANIM_DEBUG)
        except Exception as ex:
            if TV_SNAP_SHOW_DEBUG:
                print(f"[OVERLAY_STATE] Win32 fallback init failed — "
                      f"{type(ex).__name__}: {ex}", flush=True)
            return
        if not rend.wait_init(TV_SNAP_GPU_INIT_WAIT_SEC):
            err = rend.init_error() or "timeout waiting for window"
            try:
                rend.shutdown(timeout=0.5)
            except Exception:
                pass
            if TV_SNAP_SHOW_DEBUG:
                print(f"[OVERLAY_STATE] Win32 fallback init failed — "
                      f"{err}", flush=True)
            return
        self._snap_gpu = rend
        try:
            clog("[OVERLAY_STATE] display path = Win32 fallback overlay "
                 "(no GPU renderer available — charts still shown)")
        except Exception:
            pass

    @staticmethod
    def _gpu_rgba_bytes(disp):
        """PIL RGBA آماده (خروجی LANCZOS Worker) → (bytes, w, h) برای GPU
        Texture. کیفیت عیناً همان تصویر قبلی است — هیچ تغییری نکرده."""
        if disp is None:
            return None
        try:
            if getattr(disp, "mode", "RGBA") != "RGBA":
                disp = disp.convert("RGBA")
            arr = np.asarray(disp, dtype=np.uint8)
            if arr.ndim != 3 or int(arr.shape[2]) != 4:
                return None
            return arr, int(arr.shape[1]), int(arr.shape[0])
        except Exception:
            return None

    def _prepare_snapshot_overlay_gpu(self, img, path, at_end: bool,
                                      prepared=None, trace=None,
                                      key_tag=None, build_gen=None,
                                      scene=None):
        """نسخهٔ ۱۰٫۲۳ — Preload روی معماری GPU:
        هیچ پنجرهٔ Tk ساخته نمی‌شود؛ بیت‌مپ آمادهٔ Worker (LANCZOS) یک GPU
        Texture آپلود می‌شود (فقط پیام به ترد رندر — زیر چند ms) و State
        به READY می‌رود. تمام لاگ‌های چرخهٔ عمر ([SNAPSHOT_STATE]/[SNAPSHOT
        PRELOAD]/دفترترتیب) با همان قالب قبلی حفظ شده‌اند.
        نسخهٔ ۱۰٫۲۴ — اگر scene برداری از Worker رسیده باشد، به‌جای بیت‌مپ
        «صحنهٔ برداری» آپلود می‌شود (رندر خط/fill با AA واقعی روی GPU) —
        matplotlib دیگر هیچ نقشی در مسیر نمایش ندارد."""
        try:
            if (build_gen is not None
                    and build_gen != getattr(self, "_snap_pre_build_gen",
                                             build_gen)):
                self._snap_life_mark(key_tag,
                                     "PRELOAD SUPERSEDED (newer dispatch)")
                if trace is not None:
                    trace.step("Preload attempt superseded (newer dispatch)")
                    trace.finish()
                return
            self._snap_life_mark(key_tag, "PRELOAD UI CALLBACK EXECUTED")
            try:
                self._snap_pre_built_gen = int(build_gen or 0)
            except Exception:
                pass
            t_ui0 = time.perf_counter()
            if trace is not None:
                trace.step("Preload started (UI) — uploading GPU texture "
                           "(no Tk window)")
            self._discard_snapshot_preload()
            # --- نسخهٔ ۱۰٫۲۴ — مسیر برداری: هیچ بیت‌مپی لازم نیست ---
            if scene is not None:
                try:
                    gpu = self._snap_gpu
                    if gpu is None or not gpu.is_alive():
                        raise RuntimeError("GPU renderer not alive")
                    gpu.upload_scene(scene, key_tag)
                    ui_ms = (time.perf_counter() - t_ui0) * 1000.0
                    img_rect = scene.get("img") or (0, 0, 1, 1)
                    st = {"gpu": True, "key": key_tag,
                          "at_end": bool(at_end), "scene": True,
                          "x": int(img_rect[0]),
                          "y_final": int(img_rect[1]),
                          "w": int(img_rect[2]), "h": int(img_rect[3]),
                          "surf": scene.get("surf"),
                          "place": scene.get("place"),
                          "state": "ready",
                          "built_wall": time.perf_counter()}
                    self._snap_pre_photo = None          # جلوگیری از GC لازم نیست
                    self._snap_pre = st
                    self._snap_life_mark(
                        key_tag,
                        "PRELOAD COMPLETE (GPU VECTOR SCENE READY)",
                        note=(f"UI {ui_ms:.1f} ms | items={scene.get('n_items')}"
                              f" verts={scene.get('n_verts')}"))
                    self._snap_life_dump(key_tag, "PRELOAD COMPLETE")
                    try:
                        _prep_ms = ((time.perf_counter()
                                     - getattr(self, "_snap_state_t0",
                                               time.perf_counter())) * 1000.0)
                    except Exception:
                        _prep_ms = 0.0
                    self._snap_state_event("READY", SnapshotState.READY,
                                           key=key_tag,
                                           extra=f"prepare={_prep_ms:.0f}ms")
                    try:
                        f = getattr(self, "_snap_pre_fail", None)
                        if f is not None and f.get("key") in (None, key_tag):
                            self._snap_pre_fail = None
                    except Exception:
                        pass
                    if trace is not None:
                        trace.step("GPU vector scene ready (fixed surface — "
                                   "no window, no bitmap, no matplotlib)",
                                   size=(int(img_rect[2]), int(img_rect[3])),
                                   note=(f"key={key_tag} — waiting for show "
                                         "time"))
                        trace.finish()
                    if TV_SNAP_SHOW_DEBUG:
                        try:
                            print("-" * 60, flush=True)
                            print("[SNAPSHOT PRELOAD]", flush=True)
                            print("PRELOAD COMPLETE", flush=True)
                            print("Renderer: GPU VECTOR (OpenGL — AA shader)",
                                  flush=True)
                            print(f"Scene: READY (items={scene.get('n_items')}"
                                  f" verts={scene.get('n_verts')})", flush=True)
                            print(f"Total preload (UI upload): {ui_ms:.3f} ms "
                                  f"| key={key_tag}", flush=True)
                            print("-" * 60, flush=True)
                        except Exception:
                            pass
                    return
                except Exception as ex:
                    scene = None            # افت به مسیر بیت‌مپ قبلی
                    if trace is not None:
                        trace.step("Vector scene upload failed — bitmap "
                                   f"fallback ({type(ex).__name__}: {ex})")
            if img is None and path and os.path.isfile(path) \
                    and Image is not None:
                t_open = trace.begin() if trace is not None else 0.0
                img = Image.open(path).convert("RGBA")
                if trace is not None:
                    trace.end("Image.open (disk) in prepare", t_open)
            if img is None:
                reason = ("image was not available "
                          "(render failed and no temp file)")
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
                self._snap_life_mark(key_tag, "PRELOAD FAILED", note=reason)
                if trace is not None:
                    trace.step("Prepare aborted (no image)",
                               note=f"Reason: {reason}")
                    trace.finish()
                self._preload_not_ready_print(reason)
                return
            sw, sh = self._snap_screen
            disp, geo = None, None
            if prepared is not None and prepared[0] is not None:
                try:
                    disp, _arr, geo = prepared
                    x, y_final, w, h = (int(geo[0]), int(geo[1]),
                                        int(geo[2]), int(geo[3]))
                    if disp.size != (w, h):
                        disp = None
                except Exception:
                    disp, geo = None, None
            if disp is None:
                t_rz = trace.begin() if trace is not None else 0.0
                x, y_final, w, h = snap_overlay_geometry(
                    img.width, img.height, sw, sh)
                disp = img.resize((max(1, w), max(1, h)),
                                  Image.Resampling.LANCZOS)
                if trace is not None:
                    trace.end("Local resize (UI fallback — LANCZOS)", t_rz,
                              size=(w, h))
            if TV_SNAP_DEBUG_SMALL_BITMAP:
                sz = max(32, int(TV_SNAP_DEBUG_BITMAP_SIZE))
                disp = Image.new("RGBA", (sz, sz), (0, 200, 255, 170))
                x, y_final, w, h = snap_overlay_geometry(sz, sz, sw, sh)
                if trace is not None:
                    trace.step("DEBUG SMALL-BITMAP TEST ACTIVE",
                               size=(sz, sz),
                               note=f"{sz}x{sz} instead of real snapshot")
            pb = self._gpu_rgba_bytes(disp)
            if pb is None:
                reason = ("GPU texture bytes unavailable "
                          "(image convert failed)")
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
                self._snap_life_mark(key_tag, "PRELOAD FAILED", note=reason)
                if trace is not None:
                    trace.step("PRELOAD FAILED", note=f"Reason: {reason}")
                    trace.finish()
                self._preload_not_ready_print(reason)
                return
            arr, tw, th = pb
            surf = _gpu_surface_geo(sw, sh)
            place = _gpu_image_placement(sw, sh, x, y_final,
                                         surf[0], surf[1])
            self._snap_gpu.upload_png_rgba(arr, tw, th, place["dx"],
                                           place["dy"], place["travel"],
                                           key_tag)
            ui_ms = (time.perf_counter() - t_ui0) * 1000.0
            st = {"gpu": True, "key": key_tag, "at_end": bool(at_end),
                  "x": int(x), "y_final": int(y_final),
                  "w": int(w), "h": int(h),
                  "surf": surf, "place": place,
                  "state": "ready", "built_wall": time.perf_counter()}
            self._snap_pre_photo = disp          # جلوگیری از GC
            self._snap_pre = st
            self._snap_life_mark(key_tag,
                                 "PRELOAD COMPLETE (GPU TEXTURE READY)",
                                 note=f"UI {ui_ms:.1f} ms")
            self._snap_life_dump(key_tag, "PRELOAD COMPLETE")
            try:
                _prep_ms = ((time.perf_counter()
                             - getattr(self, "_snap_state_t0",
                                       time.perf_counter())) * 1000.0)
            except Exception:
                _prep_ms = 0.0
            self._snap_state_event("READY", SnapshotState.READY,
                                   key=key_tag,
                                   extra=f"prepare={_prep_ms:.0f}ms")
            try:
                f = getattr(self, "_snap_pre_fail", None)
                if f is not None and f.get("key") in (None, key_tag):
                    self._snap_pre_fail = None
            except Exception:
                pass
            if trace is not None:
                trace.step("GPU texture ready (fixed surface — no window)",
                           size=(int(w), int(h)),
                           note=(f"key={key_tag} — waiting for show time"))
                trace.finish()
            if TV_SNAP_SHOW_DEBUG:
                try:
                    print("-" * 60, flush=True)
                    print("[SNAPSHOT PRELOAD]", flush=True)
                    print("PRELOAD COMPLETE", flush=True)
                    print("Renderer: GPU (OpenGL shader — no Tk window)",
                          flush=True)
                    print(f"Texture: READY ({int(w)}x{int(h)})", flush=True)
                    print("HWND: N/A — fixed GPU surface "
                          f"{surf[2]}x{surf[3]} @ ({surf[0]},{surf[1]})",
                          flush=True)
                    print(f"Total preload (UI upload): {ui_ms:.3f} ms "
                          f"| key={key_tag}", flush=True)
                    print("-" * 60, flush=True)
                except Exception:
                    pass
        except Exception as ex:
            reason = f"{type(ex).__name__}: {ex}"
            try:
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
                self._snap_life_mark(key_tag, "PRELOAD FAILED", note=reason)
            except Exception:
                pass
            clog(f"[SnapPrepGPU] {type(ex).__name__}: {ex}")
            self._preload_not_ready_print(reason)
            if trace is not None:
                try:
                    trace.step(f"Prepare ERROR: {type(ex).__name__}: {ex}")
                    trace.finish()
                except Exception:
                    pass

    def _show_snapshot_overlay_gpu(self, img, path, seconds: float,
                                   at_end: bool, prepared=None, trace=None,
                                   sent_perf=None, key=None):
        """نسخهٔ ۱۰٫۲۳ — Show روی معماری GPU (فلسفهٔ کاربر):
          Show = renderer.show()  ←  فقط یک queue.put (زیر ~۰٫۱ms)
        در این لحظه هیچ Toplevel/PhotoImage/UpdateLayeredWindow/
        SetWindowPos/Image.open/Render انجام نمی‌شود. ورود/ماندن/خروج
        کاملاً داخل GPU با Shader است و پنجره ثابت می‌ماند. چرخهٔ عمر
        ([SNAPSHOT_STATE] + تضمین پایان) با همان قالب قبلی حفظ شده."""
        try:
            gpu = self._snap_gpu
            if gpu is None:
                return
            if trace is not None and sent_perf is not None:
                lat = (time.perf_counter() - sent_perf) * 1000.0
                trace.step("UI dispatch latency (after → show)",
                           note=f"{lat:.3f} ms")
            _lat_ms = None
            if sent_perf is not None:
                try:
                    _lat_ms = (time.perf_counter()
                               - float(sent_perf)) * 1000.0
                except Exception:
                    _lat_ms = None
            if trace is not None:
                try:
                    _mt = threading.main_thread()
                    trace.step("Thread IDs (current | Main/UI)",
                               note=(f"current: {_snap_tid_text()} | "
                                     f"Main/UI: {_mt.ident}"))
                except Exception:
                    pass
                try:
                    _mode = ("DEBUG NO-ANIM — direct GPU show (progress=1)"
                             if TV_SNAP_DEBUG_NO_ANIM else
                             "GPU SHADER ANIMATION (v10.23 — window never "
                             "moves; no SetWindowPos in this path)")
                    trace.step("Animation mode: " + _mode)
                except Exception:
                    pass
            self._snap_life_mark(key if key is not None
                                 else ("end" if at_end else "?"),
                                 "SHOW (UI callback)")
            # پیش‌ساخته «قبل از» hide جدا می‌شود (hide آن را باطل می‌کند)
            pre = getattr(self, "_snap_pre", None)
            self._snap_pre = None
            t_hide = trace.begin() if trace is not None else 0.0
            self._hide_snapshot_overlay()
            if trace is not None:
                trace.end("Hide previous overlay", t_hide)
            self._snap_state_event(
                "SHOW", SnapshotState.SHOWING, key=key,
                extra=((f"latency={_lat_ms:.1f}ms")
                       if _lat_ms is not None else "latency=?"))
            # --- پذیرش Prebuilt GPU (بدون هیچ کار سنگینی) ---
            pre_key_ok = (key is None or pre is None
                          or pre.get("key") in (None, key))
            tex_ready = (gpu.state() in (GPUOverlayRenderer.ST_READY,
                                         GPUOverlayRenderer.ST_VISIBLE,
                                         GPUOverlayRenderer.ST_ANIM)
                         and gpu.texture_key() in (None, key))
            accepted = (pre is not None and pre_key_ok
                        and bool(pre.get("gpu"))
                        and pre.get("state") == "ready" and tex_ready)
            if accepted:
                st = pre
                if trace is not None:
                    age = ((time.perf_counter()
                            - st.get("built_wall", time.perf_counter()))
                           * 1000.0)
                    trace.step("Prebuilt GPU texture: YES",
                               size=(st["w"], st["h"]),
                               note=(f"Preload completed: {age:.2f} ms ago "
                                     f"(key={st.get('key')})"))
                    trace.step("Window state: READY (fixed GPU surface — "
                               "no HWND involved)")
                    trace.step("Show cost: queue.put only — zero window "
                               "calls, zero raster work")
                self._snap_life_mark(key,
                                     "PREBUILT ACCEPTED AT SHOW (GPU)")
                self._snap_life_dump(key,
                                     "SHOW — prebuilt accepted (no race)")
            else:
                # --- مسیر اضطراری (هرگز در عملیات عادی نباید رخ دهد) ---
                if pre is None:
                    _why = ("prebuilt texture missing — preload was never "
                            "dispatched or its UI callback did not execute")
                elif not pre_key_ok:
                    _why = (f"key mismatch (pre={pre.get('key')}, "
                            f"want={key})")
                elif not tex_ready:
                    _why = ("GPU texture not ready (state="
                            + str(gpu.state()) + ", tex_key="
                            + str(gpu.texture_key()) + ")")
                else:
                    _why = ("prebuilt state not ready ("
                            + str(pre.get("state")) + ")")
                self._snap_life_mark(key, "SHOW — NO PREBUILT (RACE)",
                                     note=_why)
                self._snap_life_dump(key,
                                     "RACE — show before PRELOAD COMPLETE")
                if TV_SNAP_SHOW_DEBUG:
                    try:
                        print("[SNAPSHOT ERROR] PRELOAD INCOMPLETE", flush=True)
                        print(f"  Reason: {_why}", flush=True)
                        print("[SNAPSHOT WARNING] Prebuilt texture unavailable "
                              "at show time!", flush=True)
                        print("Using emergency fallback (GPU upload at show "
                              "time).", flush=True)
                        print("This should NEVER happen during normal "
                              "operation.", flush=True)
                    except Exception:
                        pass
                if trace is not None:
                    trace.step("NO PREBUILT TEXTURE — uploading now at "
                               "show time (!)",
                               note=f"this is the heavy path — {_why}")
                # ساخت بیت‌مپ در لحظهٔ Show (سنگین — فقط اضطراری)
                sw, sh = self._snap_screen
                disp = None
                if prepared is not None and prepared[0] is not None:
                    try:
                        disp, _arr, geo = prepared
                        x, y_final, w, h = (int(geo[0]), int(geo[1]),
                                            int(geo[2]), int(geo[3]))
                        if disp.size != (w, h):
                            disp = None
                    except Exception:
                        disp = None
                if disp is None and img is not None:
                    x, y_final, w, h = snap_overlay_geometry(
                        img.width, img.height, sw, sh)
                    disp = img.resize((max(1, w), max(1, h)),
                                      Image.Resampling.LANCZOS)
                if disp is None:
                    if trace is not None:
                        trace.step("Show aborted (no image)")
                        trace.finish()
                    return
                pb = self._gpu_rgba_bytes(disp)
                if pb is None:
                    if trace is not None:
                        trace.step("Show aborted (texture bytes failed)")
                        trace.finish()
                    return
                arr, tw, th = pb
                surf = _gpu_surface_geo(sw, sh)
                place = _gpu_image_placement(sw, sh, x, y_final,
                                             surf[0], surf[1])
                gpu.upload_png_rgba(arr, tw, th, place["dx"], place["dy"],
                                    place["travel"], key)
                st = {"gpu": True, "key": key, "at_end": bool(at_end),
                      "x": int(x), "y_final": int(y_final),
                      "w": int(w), "h": int(h), "surf": surf,
                      "place": place, "state": "ready",
                      "built_wall": time.perf_counter()}
            self._snap_overlay = None
            self._snap_overlay_photo = None
            self._snap_overlay_state = st
            self._snap_overlay_after = []
            self._snap_anim_alive = True
            # --- Show (فقط یک پیام — زیر ~۰٫۱ms) ---
            anim_ms = 0 if TV_SNAP_DEBUG_NO_ANIM else int(TV_SNAP_ANIM_MS)
            # v10.29 — ضرب‌الاجل خروج: مدت تنظیم‌شده + انیمیشن + مهلت؛
            # پس از آن نگهبان UI پنهان‌سازی اجباری می‌کند (تضمین پایان
            # همهٔ نمایش‌ها — رفع «نمودار 116 تا ابد ماند»)؛ ست شدنِ آن
            # قبل از gpu.show است تا حتی در صورت خطای بعدی، ضرب‌الاجل
            # فعال بماند و نگهبان پاک‌سازی کند.
            self._snap_overlay_deadline_wall = (
                time.time() + float(seconds) + TV_SNAP_ANIM_MS / 1000.0
                + TV_SNAP_OVERDUE_GRACE_SEC)
            t_show = gpu.show(anim_ms, key=key)
            show_ms = (time.perf_counter() - t_show) * 1000.0
            # v10.28 — SHOWING: پذیرش renderer.show == نقطهٔ مصرف تراکنشی؛
            # از این‌جا به بعد کلید در موتور consumed می‌شود (تأیید در
            # تیک بعدی Worker از صف رویداد اعمال می‌شود).
            _ck = key if key is not None else ("end" if at_end else "?")
            if at_end or _ck == "end":
                self._snap_show_event("confirm_end", _ck)
            else:
                self._snap_show_event("confirm", _ck)
            self._snap_show_stage(
                _ck, "SHOWING (renderer.show accepted — GPU)",
                extra=f"dispatch={show_ms:.3f}ms anim={anim_ms}ms")
            if trace is not None:
                trace.step("Animation start",
                           note="(GPU shader — entry animation start)")
                trace.step("Show: renderer.show() done",
                           note=(f"{show_ms:.3f} ms — queue put only; "
                                 "zero window calls"))
            life = {"entry_done": False}

            def _sched(delay_ms, fn):
                try:
                    aid = self.after(max(1, int(delay_ms)), fn)
                    self._snap_overlay_after.append(aid)
                except Exception:
                    pass

            def _gpu_hide_this():
                self._hide_snapshot_overlay()

            def _begin_exit():
                if getattr(self, "_closing", False):
                    return
                if self._snap_overlay_state is not st:
                    return              # نسل جدید آمد — کاری نکن
                if TV_SNAP_DEBUG_NO_ANIM:
                    gpu.hide_now()
                    _gpu_hide_this()
                    return
                exit_tr = SnapShowTrace("EXIT DEBUG (GPU)",
                                        TV_SNAP_SHOW_DEBUG)
                exit_tr.step("Exit animation start (GPU shader)")
                gpu.hide(int(TV_SNAP_ANIM_MS))
                exit_tr.step("Exit: renderer.hide() done (queue put only)")
                exit_tr.finish()
                _sched(int(TV_SNAP_ANIM_MS) + 80, _gpu_hide_this)

            def _entry_done():
                if life["entry_done"] or getattr(self, "_closing", False):
                    return
                life["entry_done"] = True
                if trace is not None:
                    try:
                        trace.step("Overlay fully visible (entry "
                                   "complete) — GPU",
                                   note=(f"hold {float(seconds):.0f}s "
                                         "starts now"))
                        trace.finish()
                    except Exception:
                        pass
                self._snap_state_event(
                    "VISIBLE", SnapshotState.VISIBLE, key=key,
                    extra=("entry=%.0fms"
                           % ((time.perf_counter()
                               - self._snap_state_since) * 1000.0)))
                _sched(max(1, int(float(seconds) * 1000.0)), _begin_exit)
                # تضمین پایان (لایهٔ ۳): حتی اگر خروجِ نرم گیر کند
                _sched(max(1, int((float(seconds)
                                   + TV_SNAP_ANIM_MS / 1000.0 + 1.2)
                                  * 1000.0)), _gpu_hide_this)

            def _entry_watchdog():
                # لایهٔ ۲ — اگر زنجیرهٔ after گم شده بود
                if life["entry_done"] or getattr(self, "_closing", False):
                    return
                clog("[SnapShow] watchdog (GPU): entry rescued")
                if trace is not None:
                    try:
                        trace.step("Entry watchdog FIRED (GPU)")
                    except Exception:
                        pass
                _entry_done()

            _sched(anim_ms + 900, _entry_watchdog)
            _sched(anim_ms + 40, _entry_done)
        except Exception as ex:
            clog(f"[SnapShowGPU] {type(ex).__name__}: {ex}")
            if trace is not None:
                try:
                    trace.step(f"Show ERROR (GPU): {type(ex).__name__}: {ex}")
                    trace.finish()
                except Exception:
                    pass

    def _hide_snapshot_overlay_gpu(self, expect_win=None):
        """نسخهٔ ۱۰٫۲۳ — پنهان‌سازی روی GPU:
          * تایمرهای after چرخه لغو و نسل انیمیشن bump می‌شود؛
          * hide_now = یک پیام → ترد رندر در همان فریم شفاف می‌کند؛
          * [SNAPSHOT_STATE] HIDDEN فقط اگر overlay واقعاً بالاست."""
        if expect_win is not None:
            cur = getattr(self, "_snap_overlay_state", None)
            if cur is not None and cur.get("win") is not expect_win:
                return
        for aid in list(getattr(self, "_snap_overlay_after", []) or []):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._snap_overlay_after = []
        try:
            self._snap_anim_gen += 1
            self._snap_anim_alive = False
        except Exception:
            pass
        st = getattr(self, "_snap_overlay_state", None)
        self._snap_overlay = None
        self._snap_overlay_photo = None
        self._snap_overlay_state = None
        if st is not None:
            gpu = getattr(self, "_snap_gpu", None)
            if gpu is not None:
                gpu.hide_now()
            self._snap_state_event(
                "HIDDEN", SnapshotState.EMPTY, key=None,
                extra="GPU overlay cleared (hide_now)",
                only_from=(SnapshotState.VISIBLE, SnapshotState.SHOWING))
        self._discard_snapshot_preload()

    def _snap_overlay_duration_watchdog(self):
        """v10.29 (پورت v1.2.2 از 2017) — تضمین «پایان نمایش همهٔ
        نمودارها»: هر ۲ ثانیه در UI-Thread اجرا می‌شود؛ اگر نموداری
        بعد از گذشتن «مدت تنظیم‌شده + انیمیشن + مهلت» هنوز روی صفحه
        باشد (یعنی کل زنجیرهٔ خروج سه‌لایه گم شده باشد)، پنهان‌سازی
        اجباری idempotent اجرا می‌شود: تایمرها لغو + پنجره در سطح خود
        ویندوز مخفی (GPU) / نابود (Tk). رفع باگ میدانی «نمودار دقیقهٔ
        116 نمایش داده شد و دیگر تمام نشد و برای همیشه در گوشهٔ تصویر
        ماند». این متد در نمایش عادی هرگز کاری انجام نمی‌دهد — فقط
        وقتی فعال می‌شود که همهٔ لایه‌های دیگر شکست خورده باشند."""
        try:
            if getattr(self, "_closing", False):
                return          # بستن برنامه — زنجیرهٔ باززمان‌بندی می‌ایستد
            _dl = getattr(self, "_snap_overlay_deadline_wall", None)
            if _dl is not None and time.time() >= _dl:
                _st = getattr(self, "_snap_overlay_state", None)
                if _st is not None:
                    _key = _st.get("key")
                    self._snap_overdue_watchdog_fired = \
                        int(getattr(self, "_snap_overdue_watchdog_fired",
                                    0)) + 1
                    self._snap_show_stage(
                        (_key if _key else "?"),
                        "HIDE WATCHDOG FIRED (overlay overstayed its "
                        "deadline — force hide)",
                        extra=(f"overdue_by={time.time() - _dl:.1f}s "
                               f"gpu={self._snap_gpu is not None} "
                               f"fire#{self._snap_overdue_watchdog_fired}"))
                    self._snap_overlay_deadline_wall = None
                    self._hide_snapshot_overlay()
            self.after(2000, self._snap_overlay_duration_watchdog)
        except Exception:
            try:
                self.after(2000, self._snap_overlay_duration_watchdog)
            except Exception:
                pass

    def _gpu_scene_reblit(self, scene, st):
        """نسخهٔ ۱۰٫۲۴ — re-blit برداری (ریل‌تایم پیچ‌ها): scene تازه در
        همان مکان/حالت نمایش قبلی (keep_state) — بدون قطع انیمیشن، بدون
        matplotlib، بدون بیت‌مپ."""
        gpu = getattr(self, "_snap_gpu", None)
        if gpu is None or scene is None:
            return
        if st is None or st is not getattr(self, "_snap_overlay_state",
                                           None):
            return
        try:
            gpu.upload_scene(scene, st.get("key"), keep_state=True)
        except Exception:
            pass


    def _gpu_reblit(self, disp, st):
        """نسخهٔ ۱۰٫۲۳ — معادل UpdateLayeredWindowِ «همان پنجره» در معماری
        GPU: texture در همان مکان عوض می‌شود؛ هیچ انیمیشن/وضعیتی ریست
        نمی‌شود (keep_state=True)."""
        gpu = getattr(self, "_snap_gpu", None)
        if gpu is None or disp is None:
            return
        if st is None or st is not getattr(self, "_snap_overlay_state",
                                           None):
            return
        pb = self._gpu_rgba_bytes(disp)
        if pb is None:
            return
        arr, tw, th = pb
        surf = st.get("surf") or _gpu_surface_geo(*self._snap_screen)
        place = st.get("place") or _gpu_image_placement(
            self._snap_screen[0], self._snap_screen[1],
            int(st.get("x", 0)), int(st.get("y_final", 0)),
            surf[0], surf[1])
        gpu.upload_png_rgba(arr, tw, th, place["dx"], place["dy"],
                            place["travel"], st.get("key"), keep_state=True)


    def _build_snapshot_window(self, img, path, prepared=None, trace=None,
                               key=None):
        """ساخت پنجرهٔ شفاف اسنپ‌شات «کاملاً زیرِ صفحه» (مشترک بین
        پیش‌بارگذاری و مسیر فوری — خروجی: dict وضعیت پنجره).
        نسخهٔ ۱۰٫۲۱ — تست ۶: اگر key داده شود، مراحل WINDOW CREATED /
        PHOTOIMAGE READY / LAYERED READY در دفترترتیب چرخهٔ عمر ثبت
        می‌شوند (بقیهٔ رفتار مو‌به‌مو قبلی است).
        نسخهٔ ۱۰٫۱۶ — اگر prepared=(disp, arr, geo) از ترد Worker رسیده
        باشد، هیچ کار سنگینی این‌جا انجام نمی‌شود (فقط ساخت پنجره + یک
        blit آماده)؛ وگرنه مثل قبل محلی resize/premultiply می‌شود.
        نسخهٔ ۱۰٫۱۷ — «اعتبارسنجی» بارپکت Worker: اگر arr/disp/geo با
        هم نخوانند (dtype/shape/اندازه)، بارپکت دور ریخته می‌شود و
        مسیر محلیِ مطمئن (۱۰٫۱۵) اجرا می‌شود — پنجره هیچ‌گاه با
        بیت‌مپِ خراب ساخته نمی‌شود.
        نسخهٔ ۱۰٫۱۸ — هر زیرمرحلهٔ UI (Toplevel/PhotoImage/update_idletasks/
        UpdateLayeredWindow) با trace زمان‌گیری می‌شود (بند ۵ کاربر)؛
        TV_SNAP_DEBUG_SMALL_BITMAP=True → بیت‌مپ آزمایشی 256×256 (بند ۱۱).
        نسخهٔ ۱۰٫۱۹ — PhotoImage و Label جداگانه زمان‌گیری می‌شوند
        (قالب بند ۱۰ب کاربر)؛ در خطا، پنجرهٔ نیمه‌ساخته نابود و خطا
        بالا فرستاده می‌شود (بدون نشتی پنجرهٔ زیر صفحه)."""
        sw = max(1, int(self.winfo_screenwidth()))
        sh = max(1, int(self.winfo_screenheight()))
        win = None
        try:
            disp, arr = None, None
            if prepared is not None and prepared[0] is not None:
                try:
                    disp, arr, geo = prepared
                    x, y_final, w, h = (int(geo[0]), int(geo[1]),
                                        int(geo[2]), int(geo[3]))
                    _ok = (arr is not None
                           and getattr(arr, "dtype", None) == np.uint8
                           and arr.ndim == 3 and int(arr.shape[2]) == 4
                           and int(arr.shape[0]) == h
                           and int(arr.shape[1]) == w
                           and disp.size == (w, h))
                except Exception:
                    _ok, disp, arr = False, None, None
                if not _ok:                 # بارپکت خراب → مسیر مطمئن محلی
                    if trace is not None:
                        trace.step("Worker payload validation",
                                   note="INVALID — local fallback prepare")
                    prepared = None
                    disp, arr = None, None
            if prepared is None or disp is None:
                t0 = trace.begin() if trace is not None else 0.0
                x, y_final, w, h = snap_overlay_geometry(
                    img.width, img.height, sw, sh)
                disp = img.resize((w, h), Image.Resampling.LANCZOS)  # نسبت حفظ
                arr = None
                if trace is not None:
                    trace.end("Local resize (UI fallback — LANCZOS)", t0,
                              size=(w, h))
            if TV_SNAP_DEBUG_SMALL_BITMAP:
                # --- بند ۱۱ کاربر — تست سطح کوچک: 256×256 به‌جای PNG واقعی ---
                sz = max(32, int(TV_SNAP_DEBUG_BITMAP_SIZE))
                disp = Image.new("RGBA", (sz, sz), (0, 200, 255, 170))
                arr = _premultiply_rgba(disp)
                x, y_final, w, h = snap_overlay_geometry(sz, sz, sw, sh)
                if trace is not None:
                    trace.step("DEBUG SMALL-BITMAP TEST ACTIVE",
                               size=(sz, sz),
                               note=f"{sz}x{sz} instead of real snapshot")
            y_start = sh + 4                   # کاملاً زیرِ صفحه

            t_tk = trace.begin() if trace is not None else 0.0
            win = tk.Toplevel(self)
            if trace is not None:
                trace.end("Toplevel creation", t_tk)
            t_cfg = trace.begin() if trace is not None else 0.0
            win.overrideredirect(True)
            win.attributes("-topmost", True)   # Topmost فقط همین‌جا — یک‌بار
            win.configure(bg="#000000")
            win.geometry(f"{w}x{h}+{x}+{y_start}")
            if trace is not None:
                trace.end("Window configuration (geometry/topmost)", t_cfg,
                          size=(w, h))
            if key is not None:
                self._snap_life_mark(key, "WINDOW CREATED (Toplevel+config)")
            photo, lbl = None, None
            if ImageTk is not None:
                # نسخهٔ ۱۰٫۱۹ — زمان‌گیری جدا (قالب بند ۱۰ب کاربر)
                t_ph = trace.begin() if trace is not None else 0.0
                photo = ImageTk.PhotoImage(disp)
                if trace is not None:
                    trace.end("PhotoImage creation", t_ph, size=(w, h))
                if key is not None:
                    self._snap_life_mark(key, "PHOTOIMAGE READY")
                t_lb = trace.begin() if trace is not None else 0.0
                lbl = tk.Label(win, image=photo, bd=0, bg="#000000",
                               highlightthickness=0)
                lbl.pack(fill="both", expand=True)
                if trace is not None:
                    trace.end("Label creation", t_lb, size=(w, h))
            t_idle = trace.begin() if trace is not None else 0.0
            win.update_idletasks()
            if trace is not None:
                trace.end("update_idletasks()", t_idle)
            t_layered = trace.begin() if trace is not None else 0.0
            layered = win32_show_layered(win, disp, x, y_start, w, h, arr=arr,
                                         trace=trace)
            if trace is not None:
                trace.end("Layered window setup (total)", t_layered,
                          size=(w, h),
                          note=("UpdateLayeredWindow path" if layered
                                else "FAILED → plain fallback"))
            if key is not None:
                self._snap_life_mark(
                    key,
                    "LAYERED READY (UpdateLayeredWindow)" if layered
                    else "LAYERED FAILED → plain fallback")
            if not layered:
                win.deiconify()
                win.lift()
                win.geometry(f"{w}x{h}+{x}+{y_start}")
            hwnd = win32_hwnd_of(win) if layered else None
            return {"win": win, "photo": photo, "lbl": lbl, "disp": disp,
                    "arr": arr, "x": x, "y_start": y_start,
                    "y_final": y_final, "w": w, "h": h, "layered": layered,
                    "hwnd": hwnd,
                    "built_wall": time.perf_counter()}   # نسخهٔ ۱۰٫۱۸
        except Exception:
            if win is not None:
                try:
                    win.destroy()
                except Exception:
                    pass
            raise

    def _prepare_snapshot_overlay(self, img, path, at_end: bool,
                                  prepared=None, trace=None, key_tag=None,
                                  build_gen=None, scene=None):
        """پیش‌بارگذاری (UI-Thread): رندر/تصویر آماده + ساخت پنجرهٔ زیرِ
        صفحه ۱-۲ ثانیه قبل از لحظهٔ نمایش؛ ورود بعدی فقط انیمیشن است و
        هیچ لود/رندری در لحظهٔ ورود انجام نمی‌شود.
        نسخهٔ ۱۰٫۱۶ — resize + پیش‌ضرب آلفا قبلاً در ترد Worker انجام شده
        (prepared)؛ این‌جا فقط پنجره ساخته می‌شود.
        نسخهٔ ۱۰٫۱۸ — کلید پنجره ثبت می‌شود تا در لحظهٔ Show فقط «پنجرهٔ
        همان کلید» پذیرفته شود + trace کامل مراحل UI.
        نسخهٔ ۱۰٫۱۹ (بندهای ۵/۷/۱۰ کاربر):
          * وضعیت صریح «ready» فقط وقتی ثبت می‌شود که پنجره «قابل استفاده»
            باشد (Layered+arr+HWND در ویندوز / PhotoImage در مسیر ساده)؛
          * بلوک [SNAPSHOT PRELOAD] PRELOAD COMPLETE با Window/HWND/Size/
            مدت ساخت UI چاپ می‌شود؛ در شکست: NOT READY + Reason دقیق؛
          * build_gen: اگر dispatch جدیدتری در صف است، این تلاش باطل می‌شود.
        نسخهٔ ۱۰٫۲۳ — اگر معماری GPU فعال باشد، کل این مسیر به
        _prepare_snapshot_overlay_gpu می‌رود (هیچ پنجرهٔ Tk ساخته
        نمی‌شود؛ فقط GPU Texture آپلود می‌شود).
        نسخهٔ ۱۰٫۲۴ — scene برداری (در صورت وجود) به مسیر GPU پاس می‌شود."""
        if getattr(self, "_snap_gpu", None) is not None:
            return self._prepare_snapshot_overlay_gpu(
                img, path, at_end, prepared=prepared, trace=trace,
                key_tag=key_tag, build_gen=build_gen, scene=scene)
        try:
            if (build_gen is not None
                    and build_gen != getattr(self, "_snap_pre_build_gen",
                                             build_gen)):
                # یک dispatch جدیدتر آمده — این تلاش کهنه است (superseded)
                # نسخهٔ ۱۰٫۲۱ — تست ۶: در دفترترتیب هم ثبت می‌شود
                self._snap_life_mark(key_tag,
                                     "PRELOAD SUPERSEDED (newer dispatch)")
                if trace is not None:
                    trace.step("Preload attempt superseded (newer dispatch)")
                    trace.finish()
                return
            # نسخهٔ ۱۰٫۲۱ — تست ۶: callback UI واقعاً اجرا شد
            self._snap_life_mark(key_tag, "PRELOAD UI CALLBACK EXECUTED")
            try:
                self._snap_pre_built_gen = int(build_gen or 0)
            except Exception:
                pass
            t_ui0 = time.perf_counter()
            if trace is not None:
                trace.step("Preload started (UI) — building window below "
                           "screen")
            self._discard_snapshot_preload()
            if img is None and path and os.path.isfile(path) and Image is not None:
                t_open = trace.begin() if trace is not None else 0.0
                img = Image.open(path).convert("RGBA")
                if trace is not None:
                    trace.end("Image.open (disk) in prepare", t_open)
            if img is None:
                reason = ("image was not available "
                          "(render failed and no temp file)")
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
                self._snap_life_mark(key_tag, "PRELOAD FAILED",
                                     note=reason)
                if trace is not None:
                    trace.step("Prepare aborted (no image)",
                               note=f"Reason: {reason}")
                    trace.finish()
                self._preload_not_ready_print(reason)
                return
            st = self._build_snapshot_window(img, path, prepared=prepared,
                                             trace=trace, key=key_tag)
            st["key"] = key_tag                        # نسخهٔ ۱۰٫۱۸
            st["at_end"] = bool(at_end)
            # --- نسخهٔ ۱۰٫۱۹ — گزارش منابع + قابلیت استفاده ---
            hwnd = st.get("hwnd")
            photo_ok = st.get("photo") is not None
            arr_ok = st.get("arr") is not None
            layered = bool(st.get("layered"))
            usable = (layered and arr_ok and bool(hwnd)) or \
                     ((not layered) and photo_ok)
            ui_ms = (time.perf_counter() - t_ui0) * 1000.0
            if not usable:
                reason = ("window built but resources incomplete ("
                          f"layered={layered}, "
                          f"arr={'OK' if arr_ok else 'MISSING'}, "
                          f"photo={'OK' if photo_ok else 'MISSING'}, "
                          f"hwnd={'OK' if hwnd else 'MISSING'})")
                try:
                    if st.get("win") is not None:
                        st["win"].destroy()
                except Exception:
                    pass
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
                self._snap_pre = None
                self._snap_pre_photo = None
                self._snap_life_mark(key_tag, "PRELOAD FAILED", note=reason)
                if trace is not None:
                    trace.step("PRELOAD FAILED",
                               note=f"Reason: {reason}")
                    trace.finish()
                self._preload_not_ready_print(reason)
                return
            st["state"] = "ready"                  # نسخهٔ ۱۰٫۱۹
            st["built_wall"] = time.perf_counter()
            self._snap_pre_photo = st["photo"]     # جلوگیری از GC
            self._snap_pre = st
            # نسخهٔ ۱۰٫۲۱ — تست ۶: PRELOAD COMPLETE / WINDOW READY + دامپ
            # چرخهٔ عمر (تا این لحظه) — قابل مقایسه با SHOW بعدی
            self._snap_life_mark(key_tag, "PRELOAD COMPLETE (WINDOW READY)",
                                 note=f"UI build {ui_ms:.1f} ms")
            self._snap_life_dump(key_tag, "PRELOAD COMPLETE")
            # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] READY (PREPARING → READY)
            try:
                _prep_ms = ((time.perf_counter()
                             - getattr(self, "_snap_state_t0",
                                       time.perf_counter())) * 1000.0)
            except Exception:
                _prep_ms = 0.0
            self._snap_state_event("READY", SnapshotState.READY,
                                   key=key_tag,
                                   extra=f"prepare={_prep_ms:.0f}ms")
            try:
                f = getattr(self, "_snap_pre_fail", None)
                if f is not None and f.get("key") in (None, key_tag):
                    self._snap_pre_fail = None
            except Exception:
                pass
            if trace is not None:
                trace.step("Prebuilt window ready (below screen)",
                           hwnd=hwnd, size=(st["w"], st["h"]),
                           note=(f"key={key_tag} layered={layered}"
                                 " — waiting for show time"))
                trace.finish()
            if TV_SNAP_SHOW_DEBUG:
                # --- بند ۱۰ج کاربر — بلوک پایان کامل Preload ---
                try:
                    print("-" * 60, flush=True)
                    print("[SNAPSHOT PRELOAD]", flush=True)
                    print("PRELOAD COMPLETE", flush=True)
                    print("Window: READY", flush=True)
                    print(f"HWND: "
                          + (f"0x{int(hwnd):08X}" if hwnd else "N/A"),
                          flush=True)
                    print(f"Size: {st['w']}x{st['h']}", flush=True)
                    print(f"Layered: {layered} | "
                          f"PhotoImage: {'READY' if photo_ok else 'MISSING'}",
                          flush=True)
                    print(f"Total preload (UI build): {ui_ms:.3f} ms "
                          f"| key={key_tag}", flush=True)
                    print("-" * 60, flush=True)
                except Exception:
                    pass
        except Exception as ex:
            reason = f"{type(ex).__name__}: {ex}"
            try:
                self._snap_pre_fail = {"key": key_tag, "reason": reason,
                                       "wall": time.time()}
            except Exception:
                pass
            try:
                self._snap_life_mark(key_tag, "PRELOAD FAILED", note=reason)
            except Exception:
                pass
            clog(f"[SnapPrep] {type(ex).__name__}: {ex}")
            self._preload_not_ready_print(reason)
            if trace is not None:
                try:
                    trace.step(f"Prepare ERROR: {type(ex).__name__}: {ex}")
                    trace.finish()
                except Exception:
                    pass

    def _spawn_snap_anim_thread(self, gen, hwnd, x, y0, y1, box, trace=None,
                                anim_tag: str = "ENTRY"):
        """نسخهٔ ۱۰٫۱۶ — انیمیشن ورود/خروج در «ترد اختصاصی» (رفع لگ ورود —
        شرط کاربر: سپردن به یک ترد جدا):
          * هر فریم با زمان‌بندی مطلق perf_counter محاسبه می‌شود (اگر UI
            یا سیستم momentarily کند شود، فریم بعدی دقیقاً روی مکانِ
            زمان‌درست می‌پرد — حرکت هرگز عقب نمی‌ماند)؛
          * اعمال با SetWindowPos خام (win32_move_hwnd) بدون هیچ فراخوانی
            Tk — صف شلوغ UI-Thread دیگر روی حرکت اثر ندارد؛
          * لغو با نسل (gen) — hide/پنجرهٔ جدید بلافاصله ترد قبلی را می‌کشد.
        نسخهٔ ۱۰٫۱۷ — «تضمین ظهور» (رفع «PNG اصلاً بالا نیامد»):
          * موفقیتِ هر SetWindowPos سنجیده می‌شود؛ اولین ردشدن → نتیجهٔ
            «fail» در box نوشته می‌شود؛
          * ترد «هیچ» فراخوانی Tk ندارد (حتی after) — چون پس‌زدنِ
            afterِ کراس‌ترد توسط بعضی ساخت‌های Tcl دیده شد (پروب دیباگ:
            after(0) از ترد هرگز پردازش نمی‌شد = همان علت واقعی
            «بالا نیامدن PNG»)؛ نتیجه در box می‌نشیند و «پالرِ»
            UI-Thread (لایهٔ ۱-ب) آن را تا ۴۰ms بعد می‌خواند و خودش
            fallback (حلقهٔ after) را اجرا می‌کند.
        نسخهٔ ۱۰٫۱۸ (بندهای ۸/۹ کاربر):
          * SetThreadPriority(...,2) حذف شد — ترد انیمیشن «عادی» است؛
            Game > Overlay از نظر اولویت منابع (بند ۸)؛
          * مدت با perf_counter روی زمان واقعی کنترل می‌شود (۱۰۰۰ms
            ثابت — کاهش 60→40fps مدت را عوض نمی‌کند)؛
          * شروع/پایان/نتیجه/تعداد فریم و FPS مؤثر در trace ثبت می‌شود.
        نسخهٔ ۱۰٫۲۰ (بندهای ۴/۵/۸ پیام جدید کاربر) — ابزار دقیق هر فریم:
          * «تمام» فریم‌ها ثبت می‌شوند: شماره / elapsed / مکان هدف /
            y واقعی (GetWindowRect — تشخیص عقب‌ماندگی DWM) / مدت و
            پرچم واقعی SetWindowPos (از تلمتری _SWP_LAST) / interval
            واقعی از فریم قبل / مدت واقعی sleep؛
          * بلوک [SNAPSHOT ANIMATION DEBUG] «بعد از پایان حرکت» یک‌جا
            چاپ می‌شود تا خودِ لاگ‌گیری روی زمان‌بندی فریم اثر نگذارد؛
          * خلاصه: میانگین/بیشینه/کمینهٔ interval و SetWindowPos (با
            شمارهٔ فریم) + لیست Stallها (interval > ۲× گام)؛
          * TV_SNAP_DEBUG_ANIM_NO_MOVE (تست ب): ترد و زمان‌بندی ۴۰fps
            فعال می‌ماند ولی هیچ SetWindowPos انجام نمی‌شود؛
          * ترد همچنان «هیچ» فراخوانی Tk ندارد (فقط win32 + print)."""
        import threading as _th
        dur = max(0.05, TV_SNAP_ANIM_MS / 1000.0)
        step = max(0.008, TV_SNAP_ANIM_STEP_MS / 1000.0)
        no_move = bool(TV_SNAP_DEBUG_ANIM_NO_MOVE)

        def _dump(recs, note: str, total_ms: float) -> None:
            """نسخهٔ ۱۰٫۲۰ — چاپ بلوک [SNAPSHOT ANIMATION DEBUG] (بند ۴).
            نسخهٔ ۱۰٫۲۴ — فقط با TV_SNAP_SHOW_DEBUG (حذف لاگ کنسول)."""
            if not TV_SNAP_SHOW_DEBUG:
                return
            try:
                stag = "TEST-B ANIM-NO-MOVE (SetWindowPos skipped)" \
                    if no_move else "NORMAL"
                print("=" * 60, flush=True)
                print("[SNAPSHOT ANIMATION DEBUG]", flush=True)
                print("=" * 60, flush=True)
                print(f"HWND: "
                      + (f"0x{int(hwnd):08X}" if hwnd else "N/A"),
                      flush=True)
                print(f"Thread: Anim | {_snap_tid_text()}", flush=True)
                print(f"Priority: normal | Phase: {anim_tag} | "
                      f"Mode: {stag}", flush=True)
                print(f"Target duration: {TV_SNAP_ANIM_MS} ms | "
                      f"Target FPS: "
                      f"{int(1000.0 // max(1, TV_SNAP_ANIM_STEP_MS))} "
                      f"(step {TV_SNAP_ANIM_STEP_MS} ms) | "
                      f"Path: y0={y0} → y1={y1} (x={x})", flush=True)
                if note:
                    print(f"Note: {note}", flush=True)
                print("-" * 60, flush=True)
                ivals = [r["interval_ms"] for r in recs if r["no"] > 1]
                sdurs = [r["swp_ms"] for r in recs if not r["skipped"]]
                for r in recs:
                    pos = (f"x={r['x']} y={r['y']}"
                           + ("" if r["ay"] is None
                              else f" | actual y: {r['ay']}"))
                    swp = ("skipped (TEST-B NO-MOVE)" if r["skipped"]
                           else f"{r['swp_ms']:.3f} ms | flags: "
                                + _swp_flags_text(r["flags"])
                                + f" | ok={r['ok']}")
                    print(f"Frame #{r['no']:02d}", flush=True)
                    print(f"  elapsed: {r['el_ms']:.2f} ms", flush=True)
                    print(f"  position: {pos}", flush=True)
                    print(f"  SetWindowPos: {swp}", flush=True)
                    print(f"  frame interval: {r['interval_ms']:.2f} ms",
                          flush=True)
                    print(f"  sleep: {r['sleep_ms']:.2f} ms", flush=True)
                    # --- نسخهٔ ۱۰٫۲۱ — تست ۵: تلمتری کامل ویندوزی فریم ---
                    w = r.get("wrec")
                    if w:
                        try:
                            print("  Win32 detail (TEST 5):", flush=True)
                            print(f"    old x,y: {w.get('old')} → "
                                  f"requested: {w.get('new_req')} | "
                                  f"actual after: {w.get('new')}",
                                  flush=True)
                            print(f"    HWND: "
                                  + (f"0x{int(w.get('hwnd') or 0):08X}")
                                  + f" | thread native: {w.get('tid')} | "
                                  f"priority: {w.get('prio')} | "
                                  f"return: {int(bool(w.get('ok')))} | "
                                  f"lasterror: {w.get('err')}",
                                  flush=True)
                            print(f"    before: "
                                  f"fg=0x{int(w.get('fg0') or 0):08X} | "
                                  f"visible="
                                  f"{int(bool(w.get('vis0')))} | ex: "
                                  + _snap_exstyle_text(w.get("ex0")),
                                  flush=True)
                            print(f"    after:  "
                                  f"fg=0x{int(w.get('fg1') or 0):08X} | "
                                  f"visible="
                                  f"{int(bool(w.get('vis1')))} | ex: "
                                  + _snap_exstyle_text(w.get("ex1")),
                                  flush=True)
                            us = w.get("ui_stack") or ""
                            if us:
                                print(f"    UI thread stack during "
                                      f"block: {us}", flush=True)
                        except Exception:
                            pass
                print("-" * 60, flush=True)
                print(f"Animation total: {total_ms:.1f} ms", flush=True)
                print(f"Frames: {len(recs)}", flush=True)
                if ivals:
                    mi = max(ivals)
                    mni = min(ivals)
                    imx = next(r["no"] for r in recs
                               if r["no"] > 1
                               and r["interval_ms"] == mi)
                    imn = next(r["no"] for r in recs
                               if r["no"] > 1
                               and r["interval_ms"] == mni)
                    print(f"Average frame interval: "
                          f"{(sum(ivals) / len(ivals)):.3f} ms", flush=True)
                    print(f"Maximum frame interval: {mi:.3f} ms "
                          f"(frame #{imx:02d})", flush=True)
                    print(f"Minimum frame interval: {mni:.3f} ms "
                          f"(frame #{imn:02d})", flush=True)
                    stall = [f"#{r['no']:02d}={r['interval_ms']:.1f}ms"
                             for r in recs
                             if r["no"] > 1
                             and r["interval_ms"] > 2.0 * step * 1000.0]
                    print(f"Stall frames (interval > 2× step = "
                          f"{2.0 * step * 1000.0:.0f} ms): "
                          + (", ".join(stall) if stall else "none"),
                          flush=True)
                if sdurs:
                    ms_ = max(sdurs)
                    mn_ = min(sdurs)
                    smx = next(r["no"] for r in recs
                               if not r["skipped"] and r["swp_ms"] == ms_)
                    print(f"Average SetWindowPos: "
                          f"{(sum(sdurs) / len(sdurs)):.3f} ms", flush=True)
                    print(f"Maximum SetWindowPos: {ms_:.3f} ms "
                          f"(frame #{smx:02d})", flush=True)
                    print(f"Minimum SetWindowPos: {mn_:.3f} ms", flush=True)
                else:
                    print("SetWindowPos: none (TEST-B NO-MOVE)",
                          flush=True)
                # --- نسخهٔ ۱۰٫۲۱ — خلاصهٔ تست ۴/۵ ---
                slow_txt = _anim_slow_swp_text(recs, thr_ms=5.0)
                print("Slow SetWindowPos frames (duration > 5 ms): "
                      + (slow_txt if slow_txt else "none"), flush=True)
                print("Flags policy (TEST 4): "
                      + _anim_flags_policy_text(recs), flush=True)
                print("=" * 60, flush=True)
            except Exception:
                pass

        def _work():
            frames = 0
            recs = []                 # نسخهٔ ۱۰٫۲۰ — رکورد هر فریم
            prev_it = None            # لحظهٔ شروع فریم قبل (interval)
            t0 = time.perf_counter()
            try:
                # --- نسخهٔ ۱۰٫۱۸ — بند ۸ کاربر: اولویت ترد انیمیشن دستکاری
                # نمی‌شود (SetThreadPriority حذف شد). انیمیشن Overlay باید
                # کاملاً Non-Intrusive باشد: Game > Overlay.
                if trace is not None:
                    trace.step("Animation thread started (priority: normal)",
                               hwnd=hwnd,
                               note=("Phase: " + anim_tag + " | "
                                     + _snap_tid_text()))
                nxt = t0
                while True:
                    if self._snap_anim_gen != gen:
                        box["result"] = "cancel"   # لغو شد
                        if trace is not None:
                            trace.step("Animation cancelled (generation)")
                        _dump(recs, "CANCELLED (generation superseded)",
                              (time.perf_counter() - t0) * 1000.0)
                        return
                    it = time.perf_counter()
                    p = (it - t0) / dur
                    if p >= 1.0:
                        # --- حرکت نهایی (نسخهٔ ۱۰٫۲۰: ثبت جدا از فریم‌ها) ---
                        if no_move:
                            ok = True
                            _fdur, _ffl = 0.0, 0
                        else:
                            ok = bool(win32_move_hwnd(hwnd, x,
                                                      int(round(y1))))
                            _fdur = float(_SWP_LAST.get("dur_ms", 0.0))
                            _ffl = int(_SWP_LAST.get("flags", 0))
                        box["result"] = "ok" if ok else "fail"
                        el = time.perf_counter() - t0
                        if trace is not None:
                            trace.step(
                                "Animation end",
                                hwnd=hwnd,
                                note=(f"result={'ok' if ok else 'fail'} "
                                      f"frames={frames} "
                                      f"elapsed={el * 1000.0:.1f}ms "
                                      f"fps≈{(frames / max(1e-6, el)):.0f}"
                                      + ("" if no_move else
                                         f" | final SetWindowPos: "
                                         f"{_fdur:.3f} ms | flags: "
                                         + _swp_flags_text(_ffl))))
                        _dump(recs, "completed"
                              if ok else "final move REJECTED",
                              el * 1000.0)
                        break
                    e = snap_ease_in_out(p)
                    ty = int(round(y0 + (y1 - y0) * e))
                    # --- نسخهٔ ۱۰٫۲۰ — بند ۶: مدتِ دقیق همین فریم از تلمتری
                    if no_move:
                        ok = True
                        swp_ms, fl, skipped = 0.0, 0, True
                        wrec = None
                    else:
                        ok = bool(win32_move_hwnd(hwnd, x, ty))
                        swp_ms = float(_SWP_LAST.get("dur_ms", 0.0))
                        fl = int(_SWP_LAST.get("flags", 0))
                        skipped = False
                        # نسخهٔ ۱۰٫۲۱ — تست ۵: رکورد کامل ویندوزی همین فریم
                        try:
                            wrec = dict(_SWP_LAST_EXTRA) \
                                if _SWP_LAST_EXTRA else None
                        except Exception:
                            wrec = None
                    ay = win32_window_y(hwnd) if (hwnd and not no_move) \
                        else None
                    frames += 1
                    recs.append({
                        "no": frames, "el_ms": (it - t0) * 1000.0,
                        "x": x, "y": ty, "ay": ay,
                        "swp_ms": swp_ms, "flags": fl, "ok": ok,
                        "skipped": skipped, "wrec": wrec,
                        "interval_ms": (0.0 if prev_it is None
                                        else (it - prev_it) * 1000.0),
                        "sleep_ms": 0.0})
                    prev_it = it
                    if not ok and not skipped:
                        box["result"] = "fail"     # جابه‌جایی رد شد
                        if trace is not None:
                            trace.step("Animation end",
                                       hwnd=hwnd,
                                       note="SetWindowPos REJECTED → fail")
                        _dump(recs, "SetWindowPos REJECTED → fail",
                              (time.perf_counter() - t0) * 1000.0)
                        break
                    nxt += step
                    dly = nxt - time.perf_counter()
                    if dly > 0:
                        _s0 = time.perf_counter()   # بند ۴: مدت واقعی sleep
                        time.sleep(dly)
                        recs[-1]["sleep_ms"] = \
                            (time.perf_counter() - _s0) * 1000.0
                    else:
                        nxt = time.perf_counter()   # عقب افتادیم — بازچینش
            except Exception:
                box["result"] = "fail"
                if trace is not None:
                    try:
                        trace.step("Animation thread ERROR", hwnd=hwnd)
                    except Exception:
                        pass
                _dump(recs, "THREAD ERROR (see trace above)",
                      (time.perf_counter() - t0) * 1000.0)

        th = _th.Thread(target=_work, name="snap-anim", daemon=True)
        self._snap_anim_thread = th
        th.start()

    def _show_snapshot_overlay(self, img, path, seconds: float, at_end: bool,
                               prepared=None, trace=None, sent_perf=None,
                               key=None):
        """نمایش نمودار روی صفحه (باید از UI-Thread صدا زده شود):
        سایز/محل از فرمول snap_overlay_geometry (پایین-چپ، تا 8K،
        نسبت ابعاد دقیقاً حفظ می‌شود — هیچ کشیدگی ندارد).
        نسخهٔ ۱۰٫۱۳ — نمودار یک‌دفعه ظاهر «نمی‌شود»: از زیر صفحه طی
        ۱ ثانیه با ease-in-out وارد می‌شود، به مدت تنظیم‌شده می‌ماند و
        با همان سبک به زیر صفحه برمی‌گردد و بعد بسته می‌شود.
        نسخهٔ ۱۰٫۱۵ — پنجرهٔ پیش‌ساخته (۱-۲ ثانیه قبل، زیرِ صفحه) پذیرفته
        می‌شود؛ ورود بدون هیچ لگِ لود انجام می‌شود.
        نسخهٔ ۱۰٫۱۶ — خودِ حرکت هم از UI-Thread جدا شد: روی ویندوزِ لایه‌ای
        انیمیشن در «ترد اختصاصی» با SetWindowPos خام اجرا می‌شود؛ در
        محیط‌های دیگر همان حلقهٔ after قبلی (fallback) کار می‌کند.
        نسخهٔ ۱۰٫۱۷ — «سه لایهٔ تضمین ظهور» (کاربر: PNG اصلاً بالا نیامد!):
          لایه ۱) ترد اختصاصی فقط win32 — نتیجه در box می‌نشیند (بدون هیچ
                  فراخوانی Tk؛ afterِ کراس‌ترد در بعضی ساخت‌های Tcl هرگز
                  پردازش نمی‌شود — علتِ واقعیِ «بالا نیامدن»)؛ پالرِ
                  UI-Thread نتیجه را تا ۴۰ms بعد می‌خواند: "ok" → پایان
                  عادی؛ "fail" → خودش حلقهٔ after محافظ‌شده را اجرا
                  می‌کند (fallback کامل تا geometry)؛
          لایه ۲) «واچ‌داگ ورود» بعد از انیمیشن+۶۰۰ms: اگر پنجره هنوز
                  به مکان نهایی نرسیده (ترد مرده/کراس‌ترد رد شده/after
                  کار نکرده)، UI خودش پنجره را به مکان نهایی می‌برد و
                  چرخهٔ ماندن/خروج را کامل می‌کند؛
          لایه ۳) «تضمین پایان»: بعد از مدت نمایش+انیمیشن+حاشیه،
                  پنهان‌سازی اجباری idempotent — هیچ‌چیز گیر نمی‌کند.
        + وضعیت کامل پنجره در _snap_overlay_state نگه داشته می‌شود تا
          «اعمال ریل‌تایم پیچ‌ها» بتواند همان پنجره را در جا re-blit کند.
        نسخهٔ ۱۰٫۱۸ — (بند ۳ کاربر) در لحظهٔ Show «هیچ» عمل سنگینی انجام
        نمی‌شود: پنجرهٔ پیش‌ساخته فقط باید همان کلید باشد؛ در غیر این
        صورت ساختِ کامل در لحظهٔ Show با لاگ شفاف ثبت می‌شود. تأخیر صف
        after، hide پنجرهٔ قبلی، مسیر پذیرش/ساخت و شروع/پایان انیمیشن
        همه در trace ثبت می‌شوند. TV_SNAP_DEBUG_NO_ANIM (بند ۱۰) =
        نمایش بدون انیمیشن (پرش مستقیم) برای تفکیک علت لگ.
        نسخهٔ ۱۰٫۲۳ — اگر معماری GPU فعال باشد، کل این مسیر به
        _show_snapshot_overlay_gpu می‌رود: Show فقط یک queue.put است
        (زیر ~۰٫۱ms) و انیمیشن کاملاً داخل GPU (Shader) اجرا می‌شود —
        هیچ SetWindowPos/Toplevel/PhotoImage در مسیر نیست."""
        if getattr(self, "_snap_gpu", None) is not None:
            return self._show_snapshot_overlay_gpu(
                img, path, seconds, at_end, prepared=prepared, trace=trace,
                sent_perf=sent_perf, key=key)
        try:
            if trace is not None and sent_perf is not None:
                lat = (time.perf_counter() - sent_perf) * 1000.0
                trace.step("UI dispatch latency (after → show)", 
                           note=f"{lat:.3f} ms")
            _lat_ms = None
            if sent_perf is not None:
                try:
                    _lat_ms = (time.perf_counter()
                               - float(sent_perf)) * 1000.0
                except Exception:
                    _lat_ms = None
            # نسخهٔ ۱۰٫۲۰ — بند ۸: شناسهٔ ترد جاری و Main/UI در لحظهٔ Show
            if trace is not None:
                try:
                    _mt = threading.main_thread()
                    trace.step("Thread IDs (current | Main/UI)",
                               note=(f"current: {_snap_tid_text()} | "
                                      f"Main/UI: {_mt.ident}"))
                except Exception:
                    pass
                # نسخهٔ ۱۰٫۲۰ — بند ۹/۱۰: حالت انیمیشن در لاگ (مقایسهٔ تست‌ها)
                # نسخهٔ ۱۰٫۲۱ — تست ۳ (SINGLE-MOVE) هم به فهرست حالت‌ها اضافه شد
                try:
                    _mode = ("DEBUG NO-ANIM — test A (static show, no "
                             "animation thread)"
                             if TV_SNAP_DEBUG_NO_ANIM else
                             "DEBUG ANIM-NO-MOVE — test B (animation thread "
                             "timing WITHOUT SetWindowPos)"
                             if TV_SNAP_DEBUG_ANIM_NO_MOVE else
                             "DEBUG SINGLE-MOVE — test C (ONE measured "
                             "SetWindowPos at entry, no animation)"
                             if TV_SNAP_DEBUG_ANIM_SINGLE_MOVE else
                             "NORMAL (entry/exit animation ON)")
                    trace.step("Animation mode: " + _mode)
                except Exception:
                    pass
            # نسخهٔ ۱۰٫۲۱ — تست ۶: SHOW (UI) در دفترترتیب چرخهٔ عمر
            self._snap_life_mark(key if key is not None
                                 else ("end" if at_end else "?"),
                                 "SHOW (UI callback)")
            # نسخهٔ ۱۰٫۱۵ — پیش‌ساخته «قبل از» hide جدا می‌شود (hide در
            # پایان کارِ خودش preload را هم باطل می‌کند) تا پذیرفته شود
            pre = getattr(self, "_snap_pre", None)
            self._snap_pre = None
            t_hide = trace.begin() if trace is not None else 0.0
            self._hide_snapshot_overlay()
            if trace is not None:
                trace.end("Hide previous overlay", t_hide)
            # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] SHOW (READY → SHOWING)
            self._snap_state_event(
                "SHOW", SnapshotState.SHOWING, key=key,
                extra=((f"latency={_lat_ms:.1f}ms")
                       if _lat_ms is not None else "latency=?"))
            st = None
            # نسخهٔ ۱۰٫۱۸ — فقط پنجرهٔ پیش‌ساختهٔ «همان کلید» پذیرفته می‌شود
            # نسخهٔ ۱۰٫۱۹ — گزارش کامل منابع (بند ۱۲ کاربر): پنجره باید
            # «آمادهٔ» استفاده باشد؛ منابع گمشده با نام دقیق لاگ می‌شوند.
            pre_key_ok = (key is None or pre is None
                          or pre.get("key") in (None, key))
            pre_win = pre.get("win") if pre is not None else None
            pre_win_ok = False
            if pre_win is not None:
                try:
                    pre_win_ok = bool(pre_win.winfo_exists())
                except Exception:
                    pre_win_ok = False
            pre_state_ok = bool(pre is not None
                                and pre.get("state") == "ready")
            if (pre is not None and pre_key_ok and pre_win_ok
                    and pre_state_ok):
                st = pre                              # پنجرهٔ پیش‌ساخته — آمادهٔ ورود
                if trace is not None:
                    age = ((time.perf_counter() - st.get("built_wall",
                                                          time.perf_counter()))
                           * 1000.0)
                    hwnd_p = st.get("hwnd")
                    layered_p = bool(st.get("layered"))
                    photo_p = st.get("photo") is not None
                    arr_p = st.get("arr") is not None
                    trace.step("Prebuilt window: YES",
                               hwnd=hwnd_p, size=(st["w"], st["h"]),
                               note=(f"Preload completed: {age:.2f} ms ago "
                                     f"(key={st.get('key')})"))
                    trace.step("Window state: READY",
                               note=("HWND: "
                                     + (f"0x{int(hwnd_p):08X}" if hwnd_p
                                        else "N/A (plain window)")))
                    trace.step("PhotoImage: "
                               + ("READY" if photo_p else "MISSING"))
                    trace.step("Layered resources: "
                               + ("READY"
                                  if (layered_p and arr_p and hwnd_p)
                                  else ("N.A. (plain window path)"
                                        if not layered_p else "MISSING")),
                               note="zero heavy work at show time")
                # نسخهٔ ۱۰٫۲۱ — تست ۶: پنجرهٔ پیش‌ساخته پذیرفته شد — دامپ
                # چرخهٔ عمر با RACE CHECK (باید gap مثبتِ ~۲s باشد)
                self._snap_life_mark(key, "PREBUILT ACCEPTED AT SHOW")
                self._snap_life_dump(key, "SHOW — prebuilt accepted (no race)")
            else:
                # --- نسخهٔ ۱۰٫۱۹ — دلیل دقیق + مسیر اضطراری (بند ۷/۸ کاربر) ---
                if pre is None:
                    _why = ("prebuilt window missing — preload was never "
                            "dispatched or its UI callback did not execute")
                elif not pre_key_ok:
                    _why = f"key mismatch (pre={pre.get('key')}, want={key})"
                elif not pre_win_ok:
                    _why = ("prebuilt window was destroyed before show time "
                            "(hide/reset/retune?)")
                else:
                    _why = ("prebuilt window state not ready ("
                            + str(pre.get("state")) + ")")
                _fail = getattr(self, "_snap_pre_fail", None)
                if _fail and _fail.get("key") in (None, key):
                    _why += f" | last preload failure: {_fail.get('reason')}"
                # نسخهٔ ۱۰٫۲۱ — تست ۶: قبل از هر چیز، علت دقیق Race از روی
                # دفترترتیب چرخهٔ عمر لاگ می‌شود (بند E کاربر)
                self._snap_life_mark(key, "SHOW — NO PREBUILT (RACE)",
                                     note=_why)
                self._snap_life_dump(key, "RACE — show before PRELOAD COMPLETE")
                if TV_SNAP_SHOW_DEBUG:
                    try:
                        print("[SNAPSHOT ERROR] PRELOAD INCOMPLETE", flush=True)
                        print(f"  Reason: {_why}", flush=True)
                        print("[SNAPSHOT WARNING] Prebuilt window unavailable "
                              "at show time!", flush=True)
                        print("Using emergency fallback.", flush=True)
                        print("This should NEVER happen during normal "
                              "operation.", flush=True)
                    except Exception:
                        pass
                # پنجرهٔ یتیمِ غیرقابل استفاده نابود می‌شود (بدون نشتی)
                if pre is not None and pre_win is not None:
                    try:
                        pre_win.destroy()
                    except Exception:
                        pass
                if pre is not None and not pre_key_ok:
                    if trace is not None:
                        trace.step("Prebuilt window REJECTED (key mismatch)",
                                   note=(f"pre={pre.get('key')} "
                                         f"want={key}"))
                if trace is not None:
                    trace.step("NO PREBUILT WINDOW — building now at "
                               "show time (!)",
                               note=f"this is the heavy path — {_why}")
                if img is None and path and os.path.isfile(path) and Image is not None:
                    t_open = trace.begin() if trace is not None else 0.0
                    img = Image.open(path).convert("RGBA")
                    if trace is not None:
                        trace.end("Image.open (disk) at show time (!)", t_open)
                if img is None:
                    if trace is not None:
                        trace.step("Show aborted (no image)")
                        trace.finish()
                    return
                st = self._build_snapshot_window(img, path, prepared=prepared,
                                                 trace=trace, key=key)
                st["state"] = "ready"
            self._snap_overlay = st["win"]
            self._snap_overlay_photo = st["photo"]    # جلوگیری از GC
            self._snap_overlay_state = st             # نسخهٔ ۱۰٫۱۷
            self._snap_overlay_after = []
            self._snap_anim_alive = True
            # v10.29 — ضرب‌الاجل خروج (مسیر Tk/Legacy) — همان فرمول GPU
            self._snap_overlay_deadline_wall = (
                time.time() + float(seconds) + TV_SNAP_ANIM_MS / 1000.0
                + TV_SNAP_OVERDUE_GRACE_SEC)
            win = st["win"]
            x, y_start, y_final = st["x"], st["y_start"], st["y_final"]
            w, h, layered = st["w"], st["h"], st["layered"]

            def _move(y: int) -> None:
                if not win.winfo_exists():
                    return
                if layered:
                    if st.get("hwnd") and win32_move_hwnd(st["hwnd"], x, y):
                        return
                    if win32_move_window(win, x, y):
                        return
                try:
                    win.geometry(f"{w}x{h}+{x}+{int(y)}")
                except Exception:
                    pass

            def _current_y():
                """y واقعی پنجره — اول از خود ویندوز (GetWindowRect)، بعد Tk."""
                yy = win32_window_y(st.get("hwnd")) if st.get("hwnd") else None
                if yy is not None:
                    return int(yy)
                try:
                    return int(win.winfo_rooty())
                except Exception:
                    return None

            _cb_seq = [0]

            def _schedule(delay_ms: int, fn) -> None:
                """نسخهٔ ۱۰٫۲۰ — بند ۱۲ کاربر: هر callback مرتبط با
                اسنپ‌شات روی Main/UI (زنجیرهٔ poll انیمیشن، watchdog،
                ورود/خروج/پنهان‌سازی) با Name / Scheduled / Executed /
                Latency / Duration لاگ می‌شود تا تداخل احتمالی‌اش با
                انیمیشن دقیقاً دیده شود. زمان‌ها نسبت به شروع trace
                (لحظهٔ dispatch Show) هستند — همان خط‌زمان مراحل
                [SNAPSHOT SHOW DEBUG]."""
                _cb_seq[0] += 1
                _name = getattr(fn, "__name__", "callback")
                _sched = time.perf_counter()
                _ref = trace.t0 if trace is not None else _sched

                def _cb_logged():
                    _t_exec = time.perf_counter()
                    try:
                        fn()
                    finally:
                        if TV_SNAP_SHOW_DEBUG:
                            try:
                                _dur = (time.perf_counter()
                                        - _t_exec) * 1000.0
                                print(
                                    f"[UI CALLBACK] Name: {_name} | "
                                    f"Scheduled: T+{(_sched - _ref) * 1000.0:.1f} ms | "
                                    f"Executed: T+{(_t_exec - _ref) * 1000.0:.1f} ms | "
                                    f"Latency: {(_t_exec - _sched) * 1000.0:.2f} ms | "
                                    f"Duration: {_dur:.3f} ms | "
                                    f"Thread: {_snap_thread_tag()}",
                                    flush=True)
                            except Exception:
                                pass
                try:
                    aid = win.after(max(1, int(delay_ms)), _cb_logged)
                except Exception:
                    return
                try:
                    self._snap_overlay_after.append(aid)
                except Exception:
                    pass

            def _anim_afterloop(y0: int, y1: int, done) -> None:
                """مسیر fallback (غیرویندوز/بدون hwnd/شکست ترد): همان
                حلقهٔ after نسخهٔ ۱۰٫۱۳ — روی UI-Thread با زنجیرهٔ کامل
                fallback (win32 → win32 → geometry) — همیشه کار می‌کند.
                نسخهٔ ۱۰٫۱۸ — زمان‌بندی با perf_counter (بند ۹ کاربر)."""
                t0 = time.perf_counter()
                dur = max(0.05, TV_SNAP_ANIM_MS / 1000.0)

                def _step():
                    if not win.winfo_exists():
                        return
                    p = (time.perf_counter() - t0) / dur
                    if p >= 1.0:
                        if not TV_SNAP_DEBUG_ANIM_NO_MOVE:
                            _move(int(round(y1)))
                        done()
                        return
                    e = snap_ease_in_out(p)
                    if not TV_SNAP_DEBUG_ANIM_NO_MOVE:
                        _move(int(round(y0 + (y1 - y0) * e)))
                    _schedule(TV_SNAP_ANIM_STEP_MS, _step)

                _step()

            # --- نسخهٔ ۱۰٫۱۷ — لایهٔ ۱: ترد + box + پالرِ UI-Thread ---
            # ترد فقط نتیجه را در box می‌نویسد (بدون هیچ فراخوانی Tk —
            # afterِ کراس‌ترد در بعضی ساخت‌های Tcl هرگز پردازش نمی‌شود!).
            # پالر (UI-Thread) تا ۴۰ms بعد نتیجه را می‌خواند:
            #   "ok"   → پایان عادی (done)؛
            #   "fail" → خودش حلقهٔ after محافظ‌شده را اجرا می‌کند؛
            #   هیچ    → تا ضرب‌الاجل صبر، بعد زورِ نهایی + done.

            def _run_anim(y0: int, y1: int, done, anim_trace=None,
                          anim_tag: str = "ENTRY") -> None:
                hwnd = st.get("hwnd") if layered else None
                if os.name == "nt" and hwnd:
                    box = {"result": None}
                    self._spawn_snap_anim_thread(
                        self._snap_anim_gen, hwnd, x, y0, y1, box,
                        trace=anim_trace, anim_tag=anim_tag)
                    # نسخهٔ ۱۰٫۲۰ — بند ۸: شناسهٔ ترد انیمیشن در همان لحظهٔ
                    # spawn (correlation با بلوک ANIMATION DEBUG)
                    if anim_trace is not None:
                        try:
                            _at = getattr(self, "_snap_anim_thread", None)
                            anim_trace.step("Animation thread spawned",
                                            hwnd=hwnd,
                                            note=(f"Phase: {anim_tag} | "
                                                  f"Thread ID: "
                                                  + (str(_at.ident)
                                                     if _at is not None
                                                     else "?")))
                        except Exception:
                            pass
                    deadline = time.perf_counter() + \
                        (TV_SNAP_ANIM_MS / 1000.0) + 0.6
                    fb = {"used": False}

                    def _poll():
                        if not win.winfo_exists():
                            return
                        res = box.get("result")
                        if res == "ok":
                            # نسخهٔ ۱۰٫۲۰ — بند ۱۱: پایان انیمیشن از دید
                            # UI-Thread (فاصله تا "Animation end" = تاخیر
                            # پالر ۴۰ms یا کندی UI-Thread — عدد تشخیصی)
                            if anim_trace is not None:
                                try:
                                    anim_trace.step(
                                        ("Entry" if anim_tag == "ENTRY"
                                         else "Exit")
                                        + " animation end (UI poller "
                                          "received result=ok)")
                                except Exception:
                                    pass
                            done()
                            return
                        if res == "fail":
                            if not fb["used"]:
                                fb["used"] = True
                                if anim_trace is not None:
                                    anim_trace.step(
                                        "Thread result: fail → after fallback")
                                _anim_afterloop(y0, y1, done)
                            return
                        if res == "cancel":
                            return
                        if time.perf_counter() >= deadline:
                            # ترد هیچ نگاشتی نگذاشت (مرده/قفل) — زورِ نهایی
                            # (نسخهٔ ۱۰٫۲۰: در تست ب هیچ حرکتی مجاز نیست)
                            if not TV_SNAP_DEBUG_ANIM_NO_MOVE:
                                _move(int(round(y1)))
                            done()
                            return
                        _schedule(40, _poll)

                    _schedule(40, _poll)
                else:
                    _anim_afterloop(y0, y1, done)

            # --- نسخهٔ ۱۰٫۱۷ — چرخهٔ عمر با «تضمین سه‌لایه» ---
            life = {"entry_done": False}

            def _hide_this():
                self._hide_snapshot_overlay(expect_win=win)

            def _begin_exit():
                """پایان ماندن → خروج با همان سبک (نسخهٔ ۱۰٫۱۳؛ نام تاریخی
                حفظ شد — تضمین‌های ۱۰٫۱۷ روی آن سوارند).
                نسخهٔ ۱۰٫۱۸ — خروج هم trace مستقل دارد (مقایسهٔ ورود/خروج:
                کاربر — «هنگام خروج معمولاً لگ دیده نمی‌شود»)."""
                if not win.winfo_exists():
                    return
                if TV_SNAP_DEBUG_NO_ANIM:
                    _move(int(round(y_start)))
                    _hide_this()
                    return
                exit_tr = SnapShowTrace("EXIT DEBUG", TV_SNAP_SHOW_DEBUG)
                exit_tr.step("Exit animation start")   # نسخهٔ ۱۰٫۲۰ — بند ۱۱
                _run_anim(y_final, y_start, _hide_this, anim_trace=exit_tr,
                          anim_tag="EXIT")

            def _entry_done():
                if life["entry_done"] or not win.winfo_exists():
                    return
                life["entry_done"] = True
                if trace is not None:
                    try:
                        trace.step("Overlay fully visible (entry "
                                   "complete)",
                                   note=(f"hold {float(seconds):.0f}s "
                                         "starts now — delta vs "
                                         "'Animation end' = UI poller "
                                         "latency"))
                        trace.finish()
                    except Exception:
                        pass
                # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] VISIBLE (SHOWING → VISIBLE)
                self._snap_state_event(
                    "VISIBLE", SnapshotState.VISIBLE, key=key,
                    extra=("entry=%.0fms"
                           % ((time.perf_counter()
                               - self._snap_state_since) * 1000.0)))
                # پایان ورود → ماندن به مدت تنظیم‌شده → خروج با همان سبک
                _schedule(max(1, int(float(seconds) * 1000.0)), _begin_exit)
                # لایهٔ ۳ — تضمین پایان: حتی اگر خروجِ نرم گیر کند،
                # بعد از (ماندن + انیمیشن + حاشیه) پنهان‌سازی اجباری
                _schedule(max(1, int((float(seconds)
                                      + TV_SNAP_ANIM_MS / 1000.0 + 1.2)
                                     * 1000.0)), _hide_this)

            def _entry_watchdog():
                """لایهٔ ۲ — اگر ورود کامل نشده بود، UI خودش کار را تمام
                می‌کند: پنجره زور به مکان نهایی می‌رود و چرخه ادامه
                می‌یابد. (ترد مرده / ردشدن کراس‌ترد / afterِ کارنکرده —
                هیچ‌کدام دیگر نمی‌توانند جلوی دیده‌شدن نمودار را بگیرند.)"""
                if life["entry_done"] or not win.winfo_exists():
                    return
                cur = _current_y()
                if trace is not None:
                    try:
                        trace.step("Entry watchdog FIRED (entry did not "
                                   "complete by itself)",
                                   note=f"cur_y={cur} → {y_final}")
                    except Exception:
                        pass
                if TV_SNAP_DEBUG_ANIM_NO_MOVE:
                    # نسخهٔ ۱۰٫۲۰ — تست ب: هیچ حرکتی مجاز نیست؛ فقط چرخهٔ
                    # عمر کامل شود (پنجره ثابت زیر صفحه می‌ماند)
                    if trace is not None:
                        try:
                            trace.step("Watchdog rescue move suppressed "
                                       "(TEST-B ANIM-NO-MOVE)")
                        except Exception:
                            pass
                elif cur is None or cur > y_final:
                    _move(int(round(y_final)))
                clog(f"[SnapShow] watchdog: entry rescued "
                     f"(cur_y={cur} → {y_final})")
                _entry_done()

            _schedule(int(TV_SNAP_ANIM_MS + 600), _entry_watchdog)
            # v10.28 — SHOWING (مسیر Tk/Legacy): پنجره ساخته/پذیرفته شده و
            # ورود در همین تیک شروع می‌شود (هر سه شاخه: انیمیشن/پرش/
            # SINGLE-MOVE) — نقطهٔ مصرف تراکنشی.
            _ck_tk = key if key is not None else ("end" if at_end else "?")
            if at_end or _ck_tk == "end":
                self._snap_show_event("confirm_end", _ck_tk)
            else:
                self._snap_show_event("confirm", _ck_tk)
            self._snap_show_stage(
                _ck_tk, "SHOWING (Tk window accepted — entry starting)")
            if TV_SNAP_DEBUG_NO_ANIM:
                # --- بند ۱۰ کاربر — تست بدون انیمیشن: Show → ثابت ---
                # (نسخهٔ ۱۰٫۲۱ = TEST 1 — ENTRY ANIMATION OFF؛ مدت همان یک
                # SetWindowPosِ پرش مستقیم هم ثبت می‌شود — شاهد تست ۱)
                if trace is not None:
                    trace.step("DEBUG NO-ANIM: direct jump to final position")
                t_mv = trace.begin() if trace is not None else 0.0
                _move(int(round(y_final)))
                if trace is not None:
                    try:
                        _swp = dict(_SWP_LAST)
                        trace.end("Direct-jump SetWindowPos duration "
                                  "(TEST 1 evidence)", t_mv,
                                  hwnd=_swp.get("hwnd"),
                                  note=(f"duration "
                                        f"{float(_swp.get('dur_ms', 0.0)):.3f} "
                                        f"ms | flags: "
                                        + _swp_flags_text(
                                            int(_swp.get("flags", 0)))))
                    except Exception:
                        pass
                _entry_done()
                return
            if TV_SNAP_DEBUG_ANIM_SINGLE_MOVE:
                # --- نسخهٔ ۱۰٫۲۱ — تست ۳ کاربر: فقط «یک» SetWindowPos در
                # لحظهٔ ورود + بلوک اندازه‌گیری کامل [SNAPSHOT SINGLE-MOVE
                # TEST]؛ بدون انیمیشن/ترد/هیچ حرکت دیگری در ثانیهٔ اول.
                if trace is not None:
                    trace.step("DEBUG SINGLE-MOVE: one measured SetWindowPos "
                               "to final position (TEST 3)")
                self._snap_single_move_test(st, x, y_final, trace=trace)
                _entry_done()
                return
            if trace is not None:
                trace.step("Animation start",
                           note="(entry animation start)")
            _run_anim(y_start, y_final, _entry_done, anim_tag="ENTRY")
        except Exception as ex:
            clog(f"[SnapShow] {type(ex).__name__}: {ex}")
            if trace is not None:
                try:
                    trace.step(f"Show ERROR: {type(ex).__name__}: {ex}")
                    trace.finish()
                except Exception:
                    pass

    def _snap_single_move_test(self, st, x: int, y_final: int,
                               trace=None) -> None:
        """نسخهٔ ۱۰٫۲۱ — تست ۳ کاربر: «فقط یک SetWindowPos در لحظهٔ ورود».
        پنجره از قبل Preload شده و زیر صفحه است؛ Show انجام شده؛ این‌جا
        فقط «همان یک» جابه‌جایی به مکان نهایی انجام و با Performance
        Counter اندازه‌گیری می‌شود (بعدش هیچ حرکتی انجام نمی‌شود).
        نکتهٔ تشخیصی مهم: این فراخوانی «روی UI-Thread» است (هم‌ترد با
        مالک پنجره) — پس انتظارِ پیام کراس‌ترد در کار نیست؛ اگر همین هم
        ~100-200ms طول بکشد، هزینه داخل خود فراخوانی/DWM/composition
        است، نه زمان‌بندی انیمیشن یا صف UI."""
        hwnd = st.get("hwnd")
        y0 = st.get("y_start")
        try:
            print("=" * 60, flush=True)
            print("[SNAPSHOT SINGLE-MOVE TEST] (TEST 3 — ONE SetWindowPos "
                  "at entry)", flush=True)
            print("-" * 60, flush=True)
            print("HWND: " + (f"0x{int(hwnd):08X}" if hwnd else "N/A"),
                  flush=True)
            print(f"From: x={x} y={y0} (below screen)  →  "
                  f"To: x={x} y={int(y_final)} (final)", flush=True)
            print(f"Thread: {_snap_thread_tag()} | {_snap_tid_text()}",
                  flush=True)
            t0 = time.perf_counter()
            rec = None
            if os.name == "nt" and hwnd:
                # مسیر تلمتری کامل (تست ۵): قبل/بعد + GetLastError + پشته
                rec = _win32_swp_debug(hwnd, x, int(y_final),
                                       "single_move_test")
            else:
                win32_move_hwnd(hwnd, x, int(y_final))
            wall_ms = (time.perf_counter() - t0) * 1000.0
            if rec is not None:
                print(f"SetWindowPos duration: {rec['dur_ms']:.3f} ms | "
                      "flags: " + _swp_flags_text(rec["flags"])
                      + f" | return: {int(bool(rec['ok']))} | "
                      f"lasterror: {rec['err']}", flush=True)
                print(f"old x,y: {rec['old']} → actual after: {rec['new']}",
                      flush=True)
                print(f"thread native: {rec['tid']} | priority: "
                      f"{rec['prio']}", flush=True)
                print(f"before: fg=0x{int(rec['fg0'] or 0):08X} | "
                      f"visible={int(bool(rec['vis0']))} | ex: "
                      + _snap_exstyle_text(rec["ex0"]), flush=True)
                print(f"after:  fg=0x{int(rec['fg1'] or 0):08X} | "
                      f"visible={int(bool(rec['vis1']))} | ex: "
                      + _snap_exstyle_text(rec["ex1"]), flush=True)
                if rec.get("ui_stack"):
                    print("UI thread stack during call: " + rec["ui_stack"],
                          flush=True)
            else:
                print(f"SetWindowPos duration: {wall_ms:.3f} ms "
                      "(plain path — no Win32 detail)", flush=True)
            print("Interpretation: if THIS single call blocks ~100-200ms, "
                  "the cost is inside the call itself (DWM/composition), "
                  "NOT in animation timing or cross-thread waits.",
                  flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass
        if trace is not None:
            try:
                trace.step("SINGLE-MOVE test executed",
                           note=f"duration "
                                f"{float(_SWP_LAST.get('dur_ms', 0.0)):.3f} ms")
            except Exception:
                pass

    def open_snapshot_settings(self):
        prev = getattr(self, "_snap_dlg", None)
        if prev is not None:
            try:
                if prev.winfo_exists():
                    prev.lift()
                    prev.focus_force()
                    return
            except Exception:
                pass
        s = self.snap_engine.s
        win = tk.Toplevel(self)
        self._snap_dlg = win
        win.title("⚙ تنظیمات اسنپ‌شات نمودار TV")
        win.configure(bg="#0d1420")
        win.resizable(False, False)
        win.transient(self)

        v = {
            "h1_enabled": tk.BooleanVar(value=bool(s.get("h1_enabled"))),
            "h2_enabled": tk.BooleanVar(value=bool(s.get("h2_enabled"))),
            "et_enabled": tk.BooleanVar(value=bool(s.get("et_enabled"))),
            "end_enabled": tk.BooleanVar(value=bool(s.get("end_enabled"))),
            "permanent_save": tk.BooleanVar(value=bool(s.get("permanent_save"))),
            "timestamp": tk.BooleanVar(value=bool(s.get("timestamp"))),
            "h1_minute": tk.StringVar(value=str(self.snap_engine.target_minute("h1"))),
            "h2_minute": tk.StringVar(value=str(self.snap_engine.target_minute("h2"))),
            "et_minute": tk.StringVar(value=str(self.snap_engine.target_minute("et"))),
            "show_seconds": tk.StringVar(value=str(snap_clamp_seconds(s.get("show_seconds")))),
            "end_seconds": tk.StringVar(value=str(snap_clamp_seconds(s.get("end_seconds")))),
        }

        def _title(txt):
            tk.Label(win, text=txt, font=("Segoe UI", 10, "bold"),
                     fg="#00f5d4", bg="#0d1420", anchor="e").pack(
                fill="x", padx=16, pady=(12, 2))

        def _spin_row(parent, label, var, lo, hi, unit="دقیقه", enabled_var=None):
            row = tk.Frame(parent, bg="#0d1420")
            row.pack(fill="x", padx=20, pady=3)
            chk = tk.Checkbutton(row, text=label, variable=enabled_var,
                                 font=("Segoe UI", 10), fg="#e6edf5",
                                 bg="#0d1420", activebackground="#0d1420",
                                 selectcolor="#101a2c", anchor="e",
                                 justify="right")
            chk.pack(side="right")
            tk.Label(row, text=unit, font=("Segoe UI", 9), fg="#7f8fa6",
                     bg="#0d1420").pack(side="left", padx=(4, 0))
            sp = tk.Spinbox(row, textvariable=var, from_=lo, to=hi,
                            width=5, justify="center",
                            font=("Consolas", 10, "bold"),
                            bg="#101a2c", fg="#ffd166",
                            buttonbackground="#1a2336",
                            relief="flat", highlightthickness=1,
                            highlightbackground="#2e384d")
            sp.pack(side="left")
            return sp

        _title("زمان‌بندی نمایش در حین بازی (اسنپ یک دقیقه قبل گرفته می‌شود)")
        _spin_row(win, "نیمهٔ اول", v["h1_minute"],
                  *TV_SNAP_RANGES["h1"], enabled_var=v["h1_enabled"])
        _spin_row(win, "نیمهٔ دوم", v["h2_minute"],
                  *TV_SNAP_RANGES["h2"], enabled_var=v["h2_enabled"])
        _spin_row(win, "وقت‌های اضافه", v["et_minute"],
                  *TV_SNAP_RANGES["et"], enabled_var=v["et_enabled"])

        def _restore_defaults():
            for key in TV_SNAP_KEYS:
                v[f"{key}_minute"].set(str(TV_SNAP_DEFAULT_MINUTE[key]))
                v[f"{key}_enabled"].set(True)
            v["show_seconds"].set("20")
            v["end_seconds"].set("20")
            v["end_enabled"].set(True)

        tk.Button(win, text="↺ بازگشت به پیش‌فرض (۴۳ / ۸۵ / ۱۱۶)",
                  font=("Segoe UI", 9, "bold"), bg="#1a2336", fg="#00b4d8",
                  relief="flat", cursor="hand2", activebackground="#1a2336",
                  activeforeground="#ffffff",
                  command=_restore_defaults).pack(fill="x", padx=20, pady=(6, 0))

        _title("نمایش و ذخیره")
        row_secs = tk.Frame(win, bg="#0d1420")
        row_secs.pack(fill="x", padx=20, pady=3)
        tk.Label(row_secs, text="مدت نمایش روی صفحه (ثانیهٔ واقعی)",
                 font=("Segoe UI", 10), fg="#e6edf5", bg="#0d1420").pack(side="right")
        sp_secs = tk.Spinbox(row_secs, textvariable=v["show_seconds"],
                             from_=5, to=300, width=5, justify="center",
                             font=("Consolas", 10, "bold"), bg="#101a2c",
                             fg="#ffd166", buttonbackground="#1a2336",
                             relief="flat", highlightthickness=1,
                             highlightbackground="#2e384d")
        sp_secs.pack(side="left")

        row_end = tk.Frame(win, bg="#0d1420")
        row_end.pack(fill="x", padx=20, pady=3)
        tk.Checkbutton(row_end, text="نمایش در پایان بازی (پایان ۹۰+ و ۱۲۰+)",
                       variable=v["end_enabled"], font=("Segoe UI", 10),
                       fg="#e6edf5", bg="#0d1420", activebackground="#0d1420",
                       selectcolor="#101a2c", anchor="e",
                       justify="right").pack(side="right")
        sp_end = tk.Spinbox(row_end, textvariable=v["end_seconds"],
                            from_=5, to=300, width=5, justify="center",
                            font=("Consolas", 10, "bold"), bg="#101a2c",
                            fg="#ffd166", buttonbackground="#1a2336",
                            relief="flat", highlightthickness=1,
                            highlightbackground="#2e384d")
        sp_end.pack(side="left")
        tk.Label(row_end, text="ثانیه", font=("Segoe UI", 9), fg="#7f8fa6",
                 bg="#0d1420").pack(side="left", padx=(4, 0))

        tk.Checkbutton(win, text="ذخیرهٔ دائمی نمودارها (آخرین نمودار هر بازی در پوشهٔ Momentum_Saves)",
                       variable=v["permanent_save"], font=("Segoe UI", 10),
                       fg="#e6edf5", bg="#0d1420", activebackground="#0d1420",
                       selectcolor="#101a2c", anchor="e",
                       justify="right").pack(fill="x", padx=20, pady=3)
        tk.Checkbutton(win, text="ثبت تاریخ و زمان شروع بازی (بالای نمودار)",
                       variable=v["timestamp"], font=("Segoe UI", 10),
                       fg="#e6edf5", bg="#0d1420", activebackground="#0d1420",
                       selectcolor="#101a2c", anchor="e",
                       justify="right").pack(fill="x", padx=20, pady=3)

        # --- نسخهٔ ۱۰٫۲۴ — آرشیو کامل رخدادهای بازی (خروجی/ورودی) ---
        _title("آرشیو رخدادهای بازی (خروجی ZIP + رندر دوباره)")

        def _archive_export_now():
            def _w():
                p = self._export_match_archive()
                self.after(0, lambda: _done(p))

            def _done(p):
                try:
                    if p:
                        messagebox.showinfo(
                            "آرشیو رخدادهای بازی",
                            "آرشیو کامل ساخته شد:\n" + str(p), parent=win)
                    else:
                        messagebox.showerror(
                            "آرشیو رخدادهای بازی",
                            "ساخت آرشیو ناموفق بود "
                            "(دادهٔ بازیِ کافی در دسترس نیست؟)", parent=win)
                except Exception:
                    pass

            threading.Thread(target=_w, daemon=True,
                             name="archive-export").start()

        def _archive_render_pick():
            try:
                from tkinter import filedialog as _fd
                p = _fd.askopenfilename(
                    parent=win, title="انتخاب فایل آرشیو (ZIP یا JSON)",
                    filetypes=[("آرشیو Momentum", "*.zip *.json"),
                               ("همهٔ فایل‌ها", "*.*")])
            except Exception:
                return
            if not p:
                return

            def _w():
                out = render_archive_chart(p)
                self.after(0, lambda: _done(out))

            def _done(out):
                try:
                    if out:
                        try:
                            if os.name == "nt":
                                os.startfile(out)   # باز شدن در تصویرِ‌نما
                        except Exception:
                            pass
                        messagebox.showinfo(
                            "رندر دوباره از آرشیو",
                            "نمودار از آرشیو ساخته شد:\n" + str(out),
                            parent=win)
                    else:
                        messagebox.showerror(
                            "رندر دوباره از آرشیو",
                            "خواندن/رندر آرشیو ناموفق بود.", parent=win)
                except Exception:
                    pass

            threading.Thread(target=_w, daemon=True,
                             name="archive-render").start()

        tk.Button(win, text="⬇ خروجی کامل رخدادهای بازی (ZIP — همین لحظه)",
                  font=("Segoe UI", 9, "bold"), bg="#14405e", fg="#8ecdf7",
                  relief="flat", cursor="hand2", activebackground="#14405e",
                  activeforeground="#ffffff",
                  command=_archive_export_now).pack(fill="x", padx=20,
                                                    pady=(4, 0), ipady=3)
        tk.Button(win, text="⟳ رندر دوبارهٔ نمودار از فایل آرشیو (ZIP/JSON)",
                  font=("Segoe UI", 9, "bold"), bg="#14405e", fg="#8ecdf7",
                  relief="flat", cursor="hand2", activebackground="#14405e",
                  activeforeground="#ffffff",
                  command=_archive_render_pick).pack(fill="x", padx=20,
                                                     pady=(4, 0), ipady=3)

        def _save():
            new_s = dict(self.snap_engine.s)
            for key in TV_SNAP_KEYS:
                new_s[f"{key}_enabled"] = bool(v[f"{key}_enabled"].get())
                new_s[f"{key}_minute"] = snap_clamp_minute(
                    key, v[f"{key}_minute"].get())
            new_s["show_seconds"] = snap_clamp_seconds(v["show_seconds"].get())
            new_s["end_seconds"] = snap_clamp_seconds(v["end_seconds"].get())
            new_s["end_enabled"] = bool(v["end_enabled"].get())
            new_s["permanent_save"] = bool(v["permanent_save"].get())
            new_s["timestamp"] = bool(v["timestamp"].get())
            self.snap_engine.s = new_s
            snap_save_settings(self._script_dir, new_s)
            # نسخهٔ ۱۰٫۱۵ — پنجرهٔ پیش‌ساخته ممکن است با تنظیمات جدید (دقیقهٔ
            # هدف/مدت نمایش) دیگر معتبر نباشد → باطل می‌شود
            for _k in self.snap_engine.mid:
                self.snap_engine.mid[_k]["pre"] = False
            for _k in self.snap_engine.end:
                self.snap_engine.end[_k]["pre"] = False
            try:
                self._discard_snapshot_preload()
            except Exception:
                pass
            self._tv_dirty = True       # مُهر تاریخ/زمان ممکن است عوض شود
            try:
                win.destroy()
            except Exception:
                pass

        def _cancel():
            try:
                win.destroy()
            except Exception:
                pass

        btns = tk.Frame(win, bg="#0d1420")
        btns.pack(fill="x", padx=20, pady=(10, 14))
        tk.Button(btns, text="✓ ذخیره", font=("Segoe UI", 10, "bold"),
                  bg="#1a6b4a", fg="#ffffff", relief="flat", cursor="hand2",
                  activebackground="#1a6b4a", activeforeground="#ffffff",
                  command=_save).pack(side="right", padx=(8, 0), ipadx=14)
        tk.Button(btns, text="انصراف", font=("Segoe UI", 10),
                  bg="#415a77", fg="#ffffff", relief="flat", cursor="hand2",
                  activebackground="#415a77", activeforeground="#ffffff",
                  command=_cancel).pack(side="right", ipadx=10)
        win.bind("<Escape>", lambda _e: _cancel())
        win.grab_set()
        win.lift()
        win.focus_force()


    @staticmethod
    def _gaussian_smooth(vals: List[float], sigma_samples: float) -> List[float]:
        """نسخه ۲: Gaussian smoothing واقعی (نه میانگین متحرک) — فقط لایه نمایش.
        ورودی sigma بر حسب «نمونه» است و بالادست از GAUSSIAN_SIGMA (ثانیه بازی)
        بر اساس فاصله موثر نمونه‌ها محاسبه می‌شود؛ در نتیجه رفتار smoothing
        مستقل از نرخ نمونه‌برداری/دانمپلینگ، همیشه یکسان است.
        لبه‌ها با حالت edge-padding حفظ می‌شوند (بدون افت/بیاس ابتدای سری).
        RAW MOMENTUM دست‌نخورده می‌ماند.
        """
        return _gauss_smooth_impl(vals, sigma_samples)

    def _display_value(self, raw: float) -> float:
        """Normalizing فقط در Presentation Layer — Raw Momentum overwrite نمی‌شود"""
        mode = self.config.DISPLAY_NORMALIZATION
        rng = self.config.DISPLAY_RANGE
        if mode == "raw":
            return raw
        if mode == "peak":
            peak = max(rng * 0.5, self._display_peak)
            return (raw / peak) * rng
        # fixed (پیش‌فرض): soft-clipping پایدار در بازه ±DISPLAY_RANGE
        return rng * math.tanh(raw / max(1.0, self.config.DISPLAY_SOFT_SCALE))

    def _ui_post(self, fn, *args):
        """جایگزین امن self.after(0, ...) برای فراخوانی‌های کراس‌ترد:
          * بعد از شروع بستن (_closing) هیچ callback تازه‌ای صف نمی‌شود؛
          * خود callback هم روی UI-Thread اول «_closing» را چک می‌کند و
            TclError (ویجت نابودشده) را بی‌صدا می‌گذارد — دیگر خطای
            «invalid command name» و فریزِ بستن برنامه رخ نمی‌دهد.
        نسخهٔ ۱۰٫۲۰ — بند ۱۲ کاربر: callback های مرتبط با Snapshot
        (نمایش / پیش‌بارگذاری / پنهان‌سازی) با Name / Scheduled /
        Executed / Latency / Duration لاگ می‌شوند (فقط وقتی
        TV_SNAP_SHOW_DEBUG) — تأخیر صف after در هر dispatch دیده می‌شود.
        v10.28 — خروجی bool + گزارش شکست صف/اجرا + fail-event برای Show
        (پورت v1.3 از 2017 — ریشهٔ «۴۳/۸۵ نمایش داده نشد و دیگر تلاش نشد»:
        قبلاً شکست after/callback کاملاً بی‌صدا بلعیده می‌شد)."""
        _nm = getattr(fn, "__name__", "callback")
        _is_show = _nm in ("_show_snapshot_overlay", "_show_snapshot_overlay_gpu")
        _is_snap = _is_show or _nm in ("_prepare_snapshot_overlay",
                                       "_hide_snapshot_overlay")
        _log_cb = bool(TV_SNAP_SHOW_DEBUG) and _is_snap
        # v10.28 — مبدأ زمانی برای لاگ EXECUTED همیشه برای Show فعال است
        _sched = time.perf_counter() if (_log_cb or _is_show) else 0.0
        # v10.28 — کلید Snapshot برای رویداد fail/show (آخرین آرگومان dispatch)
        _ev_key = args[-1] if (_is_show and args) else None

        def _report_fail(reason: str):
            try:
                _now = time.time()
                _last = self._ui_fail_last.get(_nm, 0.0)
                if _now - _last < self._UI_FAIL_LOG_MIN_SEC:
                    return
                self._ui_fail_last[_nm] = _now
                clog(f"[UI CALLBACK FAIL] {_nm}: {reason}")
                _snap_stage_write(f"[UI] callback '{_nm}' FAILED: {reason}")
            except Exception:
                pass

        def _safe():
            if getattr(self, "_closing", False):
                return
            _t_exec = time.perf_counter()
            try:
                fn(*args)
                # v10.28 — مرحلهٔ EXECUTED برای Show (لاگ همیشه-فعل)
                if _is_show:
                    try:
                        self._snap_show_stage(
                            _ev_key, "SHOW UI CALLBACK EXECUTED",
                            extra=(f"latency={(_t_exec - _sched) * 1000.0:.1f}ms"
                                   if _sched else "name=" + _nm))
                    except Exception:
                        pass
            except (tk.TclError if tk is not None else type(None)) as _te:
                if not getattr(self, "_closing", False):
                    _report_fail(f"TclError: {_te}")
                if _is_show:
                    self._snap_show_event(
                        "fail" if not (_ev_key == "end") else "fail_end",
                        _ev_key if _ev_key != "end"
                        else getattr(self, "_snap_end_dispatch_lvl", "end90"),
                        f"ui-callback TclError: {_te}")
            except Exception as _ex:
                _report_fail(f"{type(_ex).__name__}: {_ex}")
                if _is_show:
                    self._snap_show_event(
                        "fail" if not (_ev_key == "end") else "fail_end",
                        _ev_key if _ev_key != "end"
                        else getattr(self, "_snap_end_dispatch_lvl", "end90"),
                        f"ui-callback {type(_ex).__name__}: {_ex}")
            finally:
                if _log_cb:
                    try:
                        _dur = (time.perf_counter() - _t_exec) * 1000.0
                        _lat = (_t_exec - _sched) * 1000.0
                        print(f"[UI CALLBACK] Name: {_nm} "
                              f"(worker→UI after(0)) | "
                              f"Scheduled: T+0.0 | "
                              f"Executed: T+{_lat:.1f} ms | "
                              f"Latency: {_lat:.2f} ms | "
                              f"Duration: {_dur:.3f} ms | "
                              f"Thread: {_snap_thread_tag()}",
                              flush=True)
                    except Exception:
                        pass
        try:
            if getattr(self, "_closing", False):
                return False
            self.after(0, _safe)
            return True
        except Exception as ex:
            # v10.28 — شکست Scheduling هرگز بی‌صدا نمی‌ماند (رفع «کوری» مسیر)
            _report_fail(f"after(0) scheduling failed: "
                         f"{type(ex).__name__}: {ex}")
            return False

