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
            pt=PT)   # [PT v2.3.0] color‌technical note from PT/teams_players_PES2021.txt

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
            pt=PT)   # [PT v2.3.0] Team ID from chaintechnical note new + logo from Asset.zip
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
            self._refresh_color_dots()   # technical note firsttechnical note technical note‌technical note color (technical note technical note/technical note)
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
                self.btn_connect.config(state="disabled", text="text text ✅", bg="#2a9d8f")
                self.btn_reset.config(state="normal")
            except Exception:
                pass
            if "Warning" in msg:
                try:
                    self.lbl_status.config(text="andtext: text (with Warning hook‌text) ⚠", fg="#fca311")
                except Exception:
                    pass
            else:
                try:
                    self.lbl_status.config(text="andtext: text — in text withtext 🟢", fg="#2ecc71")
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
                        self.btn_connect.config(state="normal", text="text to textandtext withtext",
                                                bg="#00b4d8")
                        self.lbl_status.config(text="andtext: textandtext withtext text text — "
                                                    "text text automatic ⏳", fg="#fca311")
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

        # card Match Time (live)
        time_card = tk.Frame(header, bg="#0d1a26", highlightbackground="#00b4d8", highlightthickness=1, padx=12, pady=3)
        time_card.pack(side="left", padx=25)
        tk.Label(time_card, text="MATCH TIME", font=("Segoe UI", 7, "bold"), fg="#7f8fa6", bg="#0d1a26").pack()
        self.lbl_match_time = tk.Label(time_card, text="00:00", font=("Consolas", 17, "bold"), fg="#00f5d4", bg="#0d1a26")
        self.lbl_match_time.pack()
        self.lbl_clock_src = tk.Label(time_card, text="Game Clock: --", font=("Segoe UI", 7), fg="#ffd166", bg="#0d1a26")
        self.lbl_clock_src.pack()

        self.lbl_status = tk.Label(header, text="andtext: in text text",
                                   font=("Segoe UI", 9, "bold"), fg="#fca311", bg="#111622")
        self.lbl_status.pack(side="right", padx=12)

        self.btn_connect = tk.Button(header, text="text to textandtext withtext", font=("Segoe UI", 9, "bold"),
                                     bg="#00b4d8", fg="#ffffff", relief="flat", padx=16, pady=4,
                                     cursor="hand2", command=self.start_monitoring)
        self.btn_connect.pack(side="right")

        self.btn_reset = tk.Button(header, text="reset text", font=("Segoe UI", 9, "bold"),
                                   bg="#415a77", fg="#ffffff", relief="flat", padx=14, pady=4,
                                   cursor="hand2", state="disabled", command=self.request_reset)
        self.btn_reset.pack(side="right", padx=6)

        # ---------------- Field Bar ----------------
        field_bar = tk.Frame(self, bg="#151d2c", padx=15, pady=4)
        field_bar.pack(fill="x")
        self.lbl_field_info = tk.Label(field_bar, text="text pitch: in text text text...",
                                       font=("Segoe UI", 9), fg="#ffd166", bg="#151d2c")
        self.lbl_field_info.pack(side="left")
        # version 4: andtechnical note livetechnical note goal hook (side technical noteis technical noteandtechnical note pitch)
        self.lbl_goal_hook = tk.Label(field_bar, text="Goal Hook: -- ",
                                      font=("Consolas", 9, "bold"), fg="#7f8fa6", bg="#151d2c")
        self.lbl_goal_hook.pack(side="right")

        # ---------------- Possession Cards ----------------
        poss_box = tk.Frame(self, bg="#090c12", padx=15, pady=5)
        poss_box.pack(fill="x")

        self.card_home = tk.Frame(poss_box, bg="#131a28", relief="groove", bd=2, padx=12, pady=5)
        self.card_home.pack(side="left", fill="both", expand=True, padx=(0, 5))
        # version 10technical note5 — technical note logo/technical note Home (default: «Home» until logo technical noteandtechnical note technical noteandtechnical note)
        self.lbl_home_logo = tk.Label(self.card_home, text="Home", font=("Segoe UI", 10, "bold"),
                                      fg="#6b7a90", bg="#0d1117", bd=1, relief="groove",
                                      width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)
        self.lbl_home_logo.pack(side="left", padx=(0, 10), pady=2, fill="y")
        home_txt = tk.Frame(self.card_home, bg="#131a28")
        home_txt.pack(side="left", fill="both", expand=True)
        # versiontechnical note 10technical note6 — technical note technical note: [team name] [technical note‌technical note color chart]
        home_name_row = tk.Frame(home_txt, bg="#131a28")
        home_name_row.pack(fill="x")
        self.lbl_home_team = tk.Label(home_name_row, text="Home (Home / text 1-11)", font=("Segoe UI", 10, "bold"), fg="#a6e3a1", bg="#131a28")
        self.lbl_home_team.pack(side="left")
        self.cvs_home_colors = tk.Canvas(home_name_row, width=TEAM_COLOR_DOT_H, height=TEAM_COLOR_DOT_H,
                                         bg="#131a28", highlightthickness=0)
        self.cvs_home_colors.pack(side="left", padx=(7, 0))
        self.lbl_home_status = tk.Label(home_txt, text="possession: text", font=("Segoe UI", 8), fg="#94a3b8", bg="#131a28")
        self.lbl_home_status.pack(anchor="w")

        self.card_away = tk.Frame(poss_box, bg="#131a28", relief="groove", bd=2, padx=12, pady=5)
        self.card_away.pack(side="right", fill="both", expand=True, padx=(5, 0))
        # version 10technical note5 — technical note logo/technical note Away (default: «Away» until logo technical noteandtechnical note technical noteandtechnical note)
        self.lbl_away_logo = tk.Label(self.card_away, text="Away", font=("Segoe UI", 10, "bold"),
                                      fg="#6b7a90", bg="#0d1117", bd=1, relief="groove",
                                      width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)
        self.lbl_away_logo.pack(side="right", padx=(10, 0), pady=2, fill="y")
        away_txt = tk.Frame(self.card_away, bg="#131a28")
        away_txt.pack(side="right", fill="both", expand=True)
        # versiontechnical note 10technical note6 — technical note technical note: [team name] [technical note‌technical note color chart]
        away_name_row = tk.Frame(away_txt, bg="#131a28")
        away_name_row.pack(fill="x")
        self.lbl_away_team = tk.Label(away_name_row, text="Away (Away / text 12-22)", font=("Segoe UI", 10, "bold"), fg="#f38ba8", bg="#131a28")
        self.lbl_away_team.pack(side="left")
        self.cvs_away_colors = tk.Canvas(away_name_row, width=TEAM_COLOR_DOT_H, height=TEAM_COLOR_DOT_H,
                                         bg="#131a28", highlightthickness=0)
        self.cvs_away_colors.pack(side="left", padx=(7, 0))
        self.lbl_away_status = tk.Label(away_txt, text="possession: text", font=("Segoe UI", 8), fg="#94a3b8", bg="#131a28")
        self.lbl_away_status.pack(anchor="w")

        # ---------------- Tabs ----------------
        tabs_frame = tk.Frame(self, bg="#090c12")
        tabs_frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.tab_control = ttk.Notebook(tabs_frame)
        # versiontechnical note 10technical note12 — technical note «Live Match Momentum» technical note technical note (request user)technical note
        # technical note TV Momentum complete technical note technical note and technical note first is.
        # versiontechnical note 10technical note9 — technical note‌pitchtechnical note technical note TV: technical note technical note (technical noteandtechnical note technical noteandtechnical note/letterbox technical note technical note)
        self.tab_tv = tk.Frame(self.tab_control, bg="#000000")
        self.tab_events = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_seq = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_details = tk.Frame(self.tab_control, bg="#090c12")
        self.tab_debug = tk.Frame(self.tab_control, bg="#090c12")

        # versiontechnical note 10technical note7 — technical note chart technical noteandtechnical note technical noteandtechnical note technical note (Half/Full/Extra)
        self.tab_control.add(self.tab_tv, text="  📺 TV Match Momentum  ")
        self.tab_control.add(self.tab_events, text="  📋 Event Timeline  ")
        self.tab_control.add(self.tab_seq, text="  📊 Possession Sequences  ")
        self.tab_control.add(self.tab_details, text="  🎯 Event / Threat Details  ")
        self.tab_control.add(self.tab_debug, text="  🧪 Momentum Debug  ")
        self.tab_control.pack(fill="both", expand=True)
        # render TV only when technical note technical note technical note‌technical noteandtechnical note + render immediate technical note technical noteandtechnical note
        self.tab_control.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.build_tv_tab(self.tab_tv)
        self.build_events_tab(self.tab_events)
        self.build_sequences_tab(self.tab_seq)
        self.build_details_tab(self.tab_details)
        self.build_debug_tab(self.tab_debug)


    def _detect_goal_glyph(self):
        """check andtextandtext text ⚽ (U+26BD) in textandtext default matplotlibtext
        in textandtext text text text istext (text text with text text) istext text‌textandtext."""
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
        """text TV: only and only chart textandtext textandtext — without text text/text/numbertext.
        versiontext 10text10 — Figure text text is not: text‌pitchtext text text (#000000)
        textandtext textandtext Figure/textandtext/andtext textandtext text text‌textandtext (text «text» text‌text).
        versiontext 10text11 — icon text‌text ⚙ withtext text: textandtext text textagetext‌text
        (time‌text display textandtext text withtext + text + savetext text + untiltext/time)."""
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
        tk.Label(bar, text="text textagetext‌text",
                 font=("Segoe UI", 8), fg="#22304d", bg="#000000").pack(side="right")

        # --- versiontechnical note 10technical note16 — tool technical noteandtechnical note technical note technical note (technical note user — aftertechnical note technical note technical note‌technical noteandtechnical note) ---
        # technical note) smoothing technical notetotechnical note chart (number → technical noteandtechnical note technical note technical noteto)
        # technical note) technical noteand technical note smoothing/technical note technical noteandtechnical note technical noteandtechnical note technical note‌technical note
        bar2 = tk.Frame(parent, bg="#000000", height=30)
        bar2.pack(fill="x", side="bottom")   # before from canvas — chart andtechnical note technical note‌technical note
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
            # versiontechnical note 10technical note17 — «technical note‌untiltechnical note»: untiltechnical note in technical note 220ms after from technical note
            # charttechnical note technical note‌technical note (technical note and PNG technical noteandtechnical note withtechnical note) with value fresh render technical note‌technical noteandtechnical note
            e.bind("<KeyRelease>", self._tune_key_live)
            return e

        tk.Label(bar2, text="tool textandtext (in text aftertext text text‌textandtext):",
                 font=("Segoe UI", 8), fg="#55627a",
                 bg="#000000").pack(side="right", padx=(6, 10))
        _tune_lbl("smoothing textto (px):")
        _tune_ent(self._tv_edge_var)
        _tune_lbl("smoothing textandtext (×):")
        _tune_ent(self._tv_glow_soft_var)
        _tune_lbl("text textandtext (×):")
        _tune_ent(self._tv_glow_int_var)
        tk.Button(bar2, text="text", font=("Segoe UI", 8, "bold"),
                  bg="#1a2336", fg="#00f5d4", relief="flat", cursor="hand2",
                  activebackground="#1a2336", activeforeground="#ffffff",
                  command=self._apply_tv_tuning).pack(side="right", padx=(2, 8))
        tk.Button(bar2, text="default (0 / 1 / 1)", font=("Segoe UI", 8),
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
        """text text text TV — without text text text (text‌pitchtext text text).
        versiontext 10text10 — after from clear() color‌text again textuntiltext text text‌textandtext
        (clear() color textandtext text to default text‌text)."""
        self.tv_ax.clear()
        self.tv_ax.set_facecolor("#000000")
        self.tv_ax.axis("off")
        _fig = getattr(self.tv_ax, "figure", None)
        if _fig is not None:
            _fig.patch.set_facecolor("#000000")
            _fig.patch.set_alpha(1.0)


    def _apply_tv_tuning(self):
        """text 3 message user — textvalleytext textandtext text chart:
          * «smoothing textto (px)» → TV_EDGE_SMOOTH_PX (textandtext text textto + totaltext texttotal)
          * «smoothing textandtext (×)» → TV_GLOW_SOFTNESS_MUL (text textandtext intext)
          * «text textandtext (×)» → TV_GLOW_INTENSITY_MUL (text textandtext intext)
        versiontext 10text17 — «text‌untiltext textandtext charttext text‌text» (text freshtext user:
        text only charttext new!):
          * text untiltext in textvalleytext textandtext text text text with delay 220ms text text‌text
          * text livetext TV textandtext with same datatext text‌text again render text‌textandtext
            (force from text stale-visible textandtext text‌text)text
          * if PNG textagetext‌text text text textandtext text withtext istext same window
            in text textandtext with text fresh re-blit text‌textandtext (without text text
            and without reset text text)text
          * text/text‌withtext for PNGtext aftertext text withtext/withtextarmed text‌textandtext.
        (text text textandtext‌text and in text aftertext textcode text‌textandtext.)"""
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
        # versiontechnical note 10technical note17 — technical note technical note «independent» is until technical note Error technical note technical note technical note technical note
        try:
            self._snap_capture_cache.clear()          # PNGtechnical note with technical note fresh
        except Exception as ex:
            clog(f"[TVTune] cache: {type(ex).__name__}: {ex}")
        try:
            self.snap_engine.reset_preload_flags()    # technical note‌withtechnical note again armed
        except Exception as ex:
            clog(f"[TVTune] preflags: {type(ex).__name__}: {ex}")
        try:
            self._discard_snapshot_preload()          # windowtechnical note technical note‌technical note technical note
        except Exception as ex:
            clog(f"[TVTune] prediscard: {type(ex).__name__}: {ex}")
        try:
            self._tv_dirty = True
            self._refresh_tv_chart(force=True)        # technical note technical note‌technical note — immediate
        except Exception as ex:
            clog(f"[TVTune] tab: {type(ex).__name__}: {ex}")
        try:
            self._retune_live_overlay()               # PNGtechnical note currently display — immediate
        except Exception as ex:
            clog(f"[TVTune] overlay: {type(ex).__name__}: {ex}")


    def _tune_key_live(self, _event=None):
        """versiontext 10text17 — text «text‌untiltext» text untiltext: text totaltext untiltext
        220ms text from textand textandtext text‌text after from text textanduntiltext value text and
        charttext text‌text same moment fresh text‌textandtext (without textortext to Enter)."""
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
        """versiontext 10text17 — if windowtext textagetext‌text text text textandtext text withtext istext
        same charttext «currently display» with text‌text freshtext in same text and without
        text text again render and re-blit text‌textandtext (text‌untiltext real —
        render agetext in text Worker is and UI text text text‌text).
        versiontext 10text23 — path GPU: same «re-blit» — texture in text textandtext
        text‌textandtext (without text windowtext without text display)."""
        if getattr(self, "_snap_gpu", None) is not None:
            st = getattr(self, "_snap_overlay_state", None)
            if st is None or not st.get("gpu"):
                return
            if getattr(self, "_snap_retune_busy", False):
                return
            self._snap_retune_busy = True

            def _worker_gpu():
                try:
                    # versiontechnical note 10technical note24 — first path technical note (fast — without matplotlib)
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
            return                                    # technical note in technical noteortechnical note is — technical note is
        try:
            cur_y = int(win.winfo_rooty())
        except Exception:
            cur_y = int(st.get("y_final", 0))
        if cur_y > int(self.winfo_screenheight()):
            cur_y = int(st.get("y_final", cur_y))     # technical note technical note — technical note technical note
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
        """versiontext 10text17 — text text‌text fresh textandtext «same» windowtext livetext
        textagetext‌text in same text (without text windowtext new/without reset text).
        windowtext layer‌text → text UpdateLayeredWindowtext windowtext textandtext → textandtext‌text
        textandtext Label."""
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
                        ph = ImageTk.PhotoImage(disp)   # for fallback/path technical notelayer‌technical note
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
        """withtext text‌text textandtext to default (0 / 1 / 1)."""
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
                self._tv_dirty = True     # render immediate technical note technical noteandtechnical note
        except Exception:
            pass


    def _tv_bg_kind_for_state(self) -> str:
        """text textandtext text‌pitchtext text text textfrom text:
        first half → Half | second half → Full | extra time → Extra
        versiontext 10text13 — text user: charttext section aftertext only when «textandtext» text‌textandtext
        text section aftertext andtext start text withtext (withtext Playing + untiltext from boundary text):
          * Full: second half + untiltext text‌text in textortext withtext from 45:00 text
            text withtext (until before from text chart text first textandtext text text‌text)text
          * Extra: restarttext 90 in untiltext‌text «confirmation» text withtext — untiltext to
            90:00 reset text and aftertext in textortext PLAYING from 90:00 text text is.
            andtext text‌text text text second (text withtext 95 minute) and resettext without
            resumetext withtext text chart ET text textandtext text‌text (text withtext)."""
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
        """text‌textfromtext text logo/text text team (istextandtext text textandtext‌text) — only
        when path textandtext textandtext text again textfromtext text‌textandtext."""
        for side in ("home", "away"):
            path = self.team_tracker.logo_path_for(self._team_ident_last.get(side))
            sig = path
            if sig != self._tv_flag_sig[side]:
                self._tv_flag_sig[side] = sig
                self._tv_flag_arr[side] = tv_process_flag(path) if path else None
                self._tv_dirty = True

    def _tv_signature(self, bg_kind: str) -> tuple:
        """text andtext for render text in textandtext change (text ~10fps).
        versiontext 10text13 — text untiltext text textand render text is not (only file text)."""
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
        """render livetext text TV — only when text text text‌textandtext and andtext textandtext text is.
        versiontext 10text13 — text request usertext untiltext/text only textandtext «file text»
        textandtext text‌textandtext text textandtext chart display data‌text textandtext text withtext and text text.
        versiontext 10text17 — force=True text «text text render text»: from text
        _tv_visible textandtext text‌text (if text to text text stale withtext
        «text text‌text» text textwithtext text text‌textandtext only canvas must withtext)."""
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
        """text untiltext/text «start» withtext from text text (if text active withtext)."""
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
        """versiontext 10text24 — text scenetext text GPU in text Worker (text — without
        Tk/GL). from same color/text/bg_kind path text istext text‌text texttotal text
        from _tv_curve_core — textand‌to‌textand same path matplotlib. output None =
        text failed (textandtext to path text‌text beforetext text‌text)."""
        return build_gpu_graph_scene(
            self.momentum, self.config, self._tv_bg_kind_for_state(),
            self._chart_colors["home"], self._chart_colors["away"],
            self._tv_flag_arr["home"], self._tv_flag_arr["away"],
            timestamp_text=timestamp_text, screen=self._snap_screen)

    def _snapshot_render_current(self, out_path: Optional[str] = None,
                                 with_timestamp: bool = False):
        """render text andtext text chart TV (with text text) — same texttotaltext text
        text text‌text. output: PIL.Image or None. (from Worker textandtext text‌textandtext
        Figure independent text and with text original textinside text.)
        versiontext 10text13 — text untiltext/text «only» for file savetext text textandtext
        text‌textandtext (with_timestamp=True)text charttext text textandtext text withtext text‌text
        never text text."""
        return render_tv_snapshot(
            self.momentum, self.config, self._display_value,
            self._tv_bg_kind_for_state(),
            self._chart_colors["home"], self._chart_colors["away"],
            self._tv_flag_arr["home"], self._tv_flag_arr["away"],
            timestamp_text=(self._snapshot_timestamp_text()
                            if with_timestamp else None),
            out_path=out_path, transparent=True)

    def _snap_life_mark(self, key, stage: str, note: str = "") -> None:
        """register text text from cycletext text Snapshot in textorder — text for text
        text (Worker/Main-UI/Anim) and text totaltext (h1/h2/et/end)."""
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
        """print untiltext‌text complete cycletext text Snapshot (textandtext [SNAPSHOT SEQ #N])
        + RACE CHECK: distancetext PRELOAD COMPLETE until SHOW or text text Race."""
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
        """versiontext 10text21 — test 6: text Show before from PRELOAD COMPLETE text text
        text text «latest text register‌text»text text stop text + text text log
        text‌textandtext (text E user). only detection — text change textuntiltext.
        versiontext 10text24 — only with TV_SNAP_SHOW_DEBUG."""
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
        """register text text text text + print textandtext [SNAPSHOT_STATE].
        only_from: if data textandtext only when «text beforetext» text from text‌textis
        event register text‌textandtext (textandtext from log text‌text in pathtext
        text text hidetext momenttext Show).
        text for text text (Worker/Main-UI) — only text text + print."""
        try:
            prev = getattr(self, "_snap_state", SnapshotState.EMPTY)
            if only_from is not None and prev not in only_from:
                return
            self._snap_state = state
            if key is not None:
                self._snap_state_key = key
            self._snap_state_since = time.perf_counter()
            if state == SnapshotState.PREPARING:
                # technical note technical notefromtechnical note‌technical note prepare= (only start PRELOAD reset technical note‌technical noteandtechnical note
                # until event technical note technical note technical note technical notefromtechnical note «prepare» technical note broken technical note)
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
        """log always-text text text from cycletext display (file textandtext
        momentum_2026_snapshot.log text text — text mlog versiontext 2017text
        text print textandtext text). text‌text in textandtext text without text textwithtext."""
        try:
            if key in (None, ""):
                key = "?"
            msg = f"[{key}] {stage}" + (f" | {extra}" if extra else "")
            self._snap_life_mark(key, stage, note=extra)
            _snap_stage_write(msg)
        except Exception:
            pass

    def _snap_show_event(self, kind: str, key, reason: str = "") -> None:
        """register textandtext cycletext text from «text text» (Worker/UI/text):
        ("confirm", key)         → display to SHOWING text — text textfrom
        ("confirm_end", lvl)     → show_end to SHOWING text
        ("fail", key, reason)    → text dispatch/UI — armed‌textfromtext text
        ("fail_end", lvl, reason)→ text show_end — text text shows"""
        try:
            with self._snap_show_lock:
                self._snap_show_events.append((kind, key, reason))
        except Exception:
            pass

    def _snap_drain_show_events(self) -> None:
        """text textandtextdatatext confirm/fail textandtext textandtextandtext — only in text Workertext
        in text text _snapshot_tick (textandtextandtext text/text‌text text‌text)."""
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
        """text text text textagetext‌text — text text Worker (text text from PLAYING).
        versiontext 10text15 — «preload/preload_end»: 1-2 second before from momenttext displaytext
        render + text windowtext text text text text‌textandtext until andtextandtext without text withtext.
        versiontext 10text18 — tool text (text 1/2/4 user): total path Worker
        (Render/Resize/Premultiply/Cached-check) with perf_counter register text‌textandtext
        in momenttext Show text Render/Resize/I/O hiddentext text text‌textandtext — if text
        text textandtext with [SNAPSHOT WARNING] text register text‌textandtext.
        v10.28 — cycletext text (textandtext v1.3 from 2017): textandtextdatatext confirm/fail
        first drain text‌textandtext textandtext («show», key) text totaltext text text text‌text
        (text = confirmation SHOWING). if dispatch/UI text textandtext text
        TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC pass textandtext and same totaltext automatic Retry
        text‌textandtext — without restart withtext."""
        self._snap_drain_show_events()
        # --- v10.28 — technical note‌withtechnical note «technical noteandtechnical note technical noteandtechnical note technical note»: if technical note from technical note technical note
        # andtechnical note half still to value technical notefromtechnical note technical note technical note‌withtechnical note log technical note‌technical noteandtechnical note until in technical noteandtechnical note
        # technical note technical noteandtechnical note technical noteandtechnical note technical notetotal from technical note technical notefrom is technical note path Show.
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
                    # v10.28 — technical note technical note‌technical note technical note technical note display technical note technical note‌technical noteandtechnical note (technical note‌withtechnical note log)
                    if key not in self._snap_abandon_noted:
                        self._snap_abandon_noted.add(key)
                        self._snap_show_stage(
                            key, "SHOW ABANDONED (max retries reached)",
                            extra=(f"max={TV_SNAP_SHOW_MAX_RETRIES} "
                                   f"last_fail="
                                   f"{self.snap_engine.mid.get(key, {}).get('last_fail', '')}"))
                elif kind == "capture":
                    # versiontechnical note 10technical note21 — test 6: start cycletechnical note technical note technical note Snapshot
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
                    # versiontechnical note 10technical note15 — technical note‌withtechnical note technical noteortechnical note‌withtechnical note
                    # versiontechnical note 10technical note19 — path technical note dispatch (act + self-heal
                    # retry technical note technical noteand from technical note technical note technical note‌technical noteandtechnical note)
                    # versiontechnical note 10technical note21 — test 6: technical note PRELOAD REQUESTED
                    self._snap_life_mark(key, "PRELOAD REQUESTED (engine act)")
                    self._snapshot_preload_dispatch(key, "PRELOAD DEBUG",
                                                    at_end=False)
                elif kind == "preload_end":
                    # versiontechnical note 10technical note15 — technical note‌withtechnical note display end (~2 second before
                    # from confirmation stoptechnical note end)
                    self._snap_life_mark("end", "PRELOAD REQUESTED (engine act)")
                    self._snapshot_preload_dispatch("end", "PRELOAD-END DEBUG",
                                                    at_end=True)
                elif kind == "show":
                    # versiontechnical note 10technical note18 — momenttechnical note display: only «windowtechnical note technical note» technical noteto‌technical note
                    # technical note‌technical noteandtechnical note technical note technical note agetechnical note technical note‌technical note must with log technical note technical note technical noteandtechnical note
                    # versiontechnical note 10technical note21 — test 6: SHOW REQUESTED (from Worker)
                    self._snap_life_mark(key, "SHOW REQUESTED (engine act)")
                    tr = SnapShowTrace("SHOW DEBUG", TV_SNAP_SHOW_DEBUG)
                    tr.step("Show request received")
                    t0 = tr.begin()
                    img = self._snap_capture_cache.get(key)
                    tr.end("Cached image check", t0,
                           note=("hit" if img is not None else "MISS"))
                    # versiontechnical note 10technical note19 — only andtechnical note «ready» technical note technical note technical note‌technical noteandtechnical note
                    pre_ready = (getattr(self, "_snap_pre", None) is not None
                                 and self._snap_pre.get("key") == key
                                 and self._snap_pre.get("state") == "ready")
                    if img is None:
                        # technical note 4 user — render agetechnical note never technical notemust hidden withtechnical note
                        # (versiontechnical note 10technical note24 — only with TV_SNAP_SHOW_DEBUG)
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
                        # windowtechnical note technical note‌technical note same totaltechnical note live is → technical note technical note‌technical notefromtechnical note
                        # technical note in momenttechnical note Show technical notefromtechnical note is not (technical note 3 user)
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
                    # v10.28 — REQUESTED + QUEUED with number technical note if technical note
                    # after technical note technical noteandtechnical note technical notedistance fail → technical note technical note automatic
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
                    # versiontechnical note 10technical note21 — test 6: SHOW REQUESTED (match end)
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
                    # v10.28 — level in technical noteandfrom register technical note‌technical noteandtechnical note until fail_end technical note codetechnical note
                    # level technical note withtechnical notearmed technical note (end90/end120)
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
                # v10.28 — technical note technical noteandtechnical note technical notefromtechnical note action in Worker technical note fail technical note‌technical noteandtechnical note
                if kind == "show" and key in ("h1", "h2", "et"):
                    self._snap_show_event(
                        "fail", key,
                        f"worker-act-error: {type(ex).__name__}: {ex}")
                elif kind == "show_end":
                    self._snap_show_event(
                        "fail_end", self._snap_end_dispatch_lvl or key,
                        f"worker-act-error: {type(ex).__name__}: {ex}")
        # versiontechnical note 10technical note19 — self-heal technical note‌withtechnical note: if windowtechnical note technical note‌technical note technical note
        # technical noteandtechnical note until «before» from momenttechnical note display again technical note technical note‌technical noteandtechnical note (technical noteandtechnical note technical note)
        self._snapshot_preload_selfheal(total_t, now_wall)

    def _snapshot_preload_dispatch(self, key, trace_title, at_end: bool,
                                   reason: str = ""):
        """path text Preload window (act «preload/preload_end» textandtextandtext and
        self-heal retry text textand from text‌text text‌textandtext) — from text Worker:
          1) textandtext from text (or render if textandtext — same text beforetext)
          2) LANCZOS resize + text‌text text (text from UI-Thread)
          3) dispatch text window to UI-Thread (text text)
        text text agetext «before» from momenttext Show text text‌textandtext in momenttext Show
        only show/position/animation withtext text‌text (text 3/4 user).
        reason: if retry self-heal withtext text in log text‌text."""
        try:
            if getattr(self, "_closing", False):
                return
            # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] PRELOAD START (EMPTY → PREPARING)
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
            # --- versiontechnical note 10technical note24 — path technical note GPU: scene in Worker technical note technical note‌technical noteandtechnical note
            # (technical note from momenttechnical note Show)technical note LANCZOS/premultiply/matplotlib-draw from
            # path display technical note technical note‌technical noteandtechnical note. technical note → path technical note‌technical note beforetechnical note.
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
            # versiontechnical note 10technical note21 — test 6: PRELOAD DISPATCHED → technical note UI + register time
            # technical note (for detection «technical note technical note from 1s technical note technical note» in self-heal)
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
        """check text windowtext text‌text from text Worker (without text textandtext Tk):
        andtext text «ready» + same totaltext + window textandtextandtext."""
        pre = getattr(self, "_snap_pre", None)
        # versiontechnical note 10technical note23 — architecture GPU: prebuilt without windowtechnical note Tk technical note valid is
        return bool(pre is not None
                    and pre.get("key") == key
                    and pre.get("state") == "ready"
                    and (pre.get("win") is not None
                         or pre.get("gpu") is True))

    def _snap_pre_fail_reason_text(self, key) -> str:
        """latest text text Preload for totaltext (for log self-heal/Show)."""
        f = getattr(self, "_snap_pre_fail", None)
        if f and f.get("key") in (None, key) and f.get("reason"):
            return f"previous attempt failed — {f.get('reason')}"
        return "previous attempt did not produce a ready window"

    @staticmethod
    def _preload_not_ready_print(reason: str) -> None:
        """textandtext log «NOT READY» with text text (text 7 user).
        versiontext 10text24 — only with TV_SNAP_SHOW_DEBUG print text‌textandtext (text log textandtext)."""
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
        """versiontext 10text19 — text automatic Preload (text user: «if Window must
        Rebuild textandtext text text must before from time Show aftertext text textandtext»):
          * if windowtext text‌text totaltext text is not (text UI text textandtext/
            text text text/window textandtext text)text again dispatch text‌textandtext —
            with textandtext text and only until TV_SNAP_PRELOAD_MIN_REMAIN_SEC
            before from momenttext display (text in momenttext Show text text text)text
          * time‌text/text textandtextandtext unchanged is — text path only «text‌text»
            idempotent is and when window text is text text‌text.
        versiontext 10text21 — test 6 (Race real user: «PRELOAD UI CALLBACK never
        before from Show text text»):
          1) text text «text pre text text withtext» textfromtext is not — if text Worker from
             windowtext preload text withtext (text pre never text text)text text‌text
             backfill text‌textandtext (text in reason log text‌textandtext)text
          2) if text text text from 1.0s without text text withtext (UI-Thread
             textandtext/text‌text text‌text)text for «same totaltext» again dispatch
             text‌textandtext (supersede — text legacy textandtext text withtext text‌text).
        versiontext 10text22 — Snapshot Window Lifecycle Manager (firstandtext 1/2
        text text user): windowtext «threshold‌text text» — for textortext‌withtext‌text
        dispatch from «text − TV_SNAP_PRELOAD_WIDE_LEAD_SEC (10s)» withtext
        text‌textandtext (if match_time >= preload_start — specification user):
        text windowtext 2 second‌text text‌text is nottext text if UI/Worker in
        windowtext withtext text text text‌text text‌textandtext 0text5s text second
        text text. text textandtext textandtext: textandtext textortext‌withtext same PNG text
        T-60s is (text text) → text textandtext window textandtext display text
        change text‌text. display «end» text windowtext withtext beforetext text
        text (rendertext to momenttext stop andtext is)."""
        try:
            if getattr(self, "_closing", False):
                return
            eng = self.snap_engine
            now = float(now_wall) if now_wall is not None else time.time()
            try:
                t = float(total_t) if total_t is not None else None
            except (TypeError, ValueError):
                t = None
            # versiontechnical note 10technical note21 — «currently technical note» technical note technical note technical note is not: if technical note technical note
            # from 1.0s without technical note technical note for same totaltechnical note again dispatch technical note‌technical noteandtechnical note
            in_flight = (getattr(self, "_snap_pre_build_gen", 0)
                         > getattr(self, "_snap_pre_built_gen", 0))
            pending_key = getattr(self, "_snap_pre_pending_key", None)

            def _in_flight_block(key) -> Optional[str]:
                """if text text textandtext dispatchtext text totaltext text text text text
                text‌text (None = textfromtext dispatch)."""
                if not in_flight:
                    return None
                if pending_key != key:
                    return "another key's build is in flight"
                dw = self._snap_pre_dispatch_wall.get(key, 0.0)
                if (now - dw) < 1.0:
                    return "queued build still fresh (<1.0s)"
                return None          # technical note → technical notefromtechnical note re-dispatch (supersede)

            # ---------- technical noteortechnical note‌withtechnical note ----------
            for key in TV_SNAP_KEYS:
                st = eng.mid.get(key)
                # versiontechnical note 10technical note21 — technical note pre technical note technical note is not (technical note technical note from windowtechnical note
                # 2 second‌technical note technical note must backfill technical noteandtechnical note)
                if st is None or st.get("shown"):
                    continue
                if t is None:
                    continue
                tgt = eng.target_minute(key) * 60.0
                # versiontechnical note 10technical note22 — windowtechnical note threshold‌technical note technical note (firstandtechnical note 1 user):
                # if match_time >= preload_start → technical note technical note after from threshold
                # technical note dispatch technical note (technical note only windowtechnical note 2 second‌technical note technical note‌technical note).
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
            # ---------- match end ----------
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
        """versiontext 10text24 — output complete textdatatext withtext (ZIP) from andtext text.
        from text Worker textandtext text‌textandtext (match end/buttontext text) — text Tk.
        output: path ZIP or None."""
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
        """«savetext text charttext» — latest chart withtext beforetext correct before from
        text‌text untiltext (untiltext to 00:00 reset text = start text new) in
        Momentum_Saves with text textandtext textandtext save text‌textandtext. (from Worker)
        versiontext 10text13 — only text file text text untiltext/text text (user:
        charttext text textandtext text withtext text‌text textmust text text withtext).
        versiontext 10text24 — archive complete textdatatext (ZIP) «always» before from text text
        textandtext text‌textandtext (independent from permanent_save — request text user)."""
        s = self.snap_engine.s
        with self.momentum._lock:
            n_hist = len(self.momentum.history)
        if n_hist < 2 or self._match_seen_max_t < TV_SNAP_MIN_HIST_SEC:
            return    # withtechnical note still datatechnical note technical note technical note
        # --- versiontechnical note 10technical note24 — archive complete technical notedatatechnical note (automatic — always) ---
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
        """versiontext 10text15 — textandtext windowtext «text‌text» textagetext‌text (text text).
        versiontext 10text22 — if windowtext text‌text «text» textandtext text text
        (retune/hide/reset)text text text to EMPTY text‌text and log text‌textandtext
        (self-heal text 10text22 until before from Show again text‌textfromtext)."""
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
            # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] windowtechnical note technical note technical noteandtechnical note technical note technical note
            self._snap_state_event(
                "PREBUILT DISCARDED", SnapshotState.EMPTY, key=None,
                extra="prebuilt window discarded (retune/hide/reset)",
                only_from=(SnapshotState.READY,))

    def _hide_snapshot_overlay(self, expect_win=None):
        """hidden‌textfromtext chart textandtext text.
        versiontext 10text17 — expect_win: if data textandtext only when windowtext text
        «same» window is textandtext/textand text‌textandtext hidetext text text chart
        beforetext (text after(0,hide) text textandtext legacy) text text‌textandtext
        windowtext chart fresh text textandtext or text text textand text.
        versiontext 10text23 — path GPU: window‌text for textandtext text is nottext untiltext
        textand and level in same frame text text‌textandtext (hide_now — text message)."""
        # v10.29 — hidden‌technical notefromtechnical note technical note technical note → technical note‌technical note watchdog technical note display technical note
        # withtechnical note technical note‌technical noteandtechnical note (pathtechnical note GPU and Tk technical note technical noteand from technical note‌technical note technical note‌technical note)
        self._snap_overlay_deadline_wall = None
        if getattr(self, "_snap_gpu", None) is not None:
            return self._hide_snapshot_overlay_gpu(expect_win)
        win = getattr(self, "_snap_overlay", None)
        if expect_win is not None and win is not expect_win:
            return                      # window technical noteandtechnical note technical note — technical note to technical note new technical note‌technical note
        # versiontechnical note 10technical note13 — technical noteand untiltechnical note technical note in technical noteortechnical note before from technical noteandtechnical note window
        for aid in list(getattr(self, "_snap_overlay_after", []) or []):
            try:
                self.after_cancel(aid)
            except Exception:
                pass
        self._snap_overlay_after = []
        # versiontechnical note 10technical note16 — technical noteand technical note technical note (technical note new + technical note stoptechnical note technical note daemon is
        # and with technical note new in same frame aftertechnical note technical note technical note‌technical noteandtechnical note — without join technical noteandtechnical note)
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
            # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] hidden‌technical notefromtechnical note real → EMPTY
            # (only when overlay «technical note‌technical note/currently display» technical noteandtechnical note — hidetechnical note
            # momenttechnical note Show technical note windowtechnical note beforetechnical note technical note log technical note‌technical note technical note‌technical notefromtechnical note)
            self._snap_state_event(
                "HIDDEN", SnapshotState.EMPTY, key=None,
                extra="overlay window destroyed",
                only_from=(SnapshotState.VISIBLE, SnapshotState.SHOWING))
        # versiontechnical note 10technical note15 — technical note‌technical note technical note with hidden‌technical notefromtechnical note live withtechnical note technical note‌technical noteandtechnical note
        self._discard_snapshot_preload()

    def _gpu_overlay_boot(self):
        """text‌textfromtext Renderer GPU — only «text‌withtext in start». text GPU/legacy
        never in momenttext Show text text‌textandtext (text text text display text
        text‌textandtext). text → log text + path beforetext (10text22) for «text text»."""
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
                    print("for active‌textfromtext architecture GPU text text: "
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
        """PIL RGBA text (output LANCZOS Worker) → (bytes, w, h) for GPU
        Texture. text text same textandtext beforetext is — text changetext text."""
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
        """versiontext 10text23 — Preload textandtext architecture GPU:
        text windowtext Tk text text‌textandtext text‌text text Worker (LANCZOS) text GPU
        Texture textandtext text‌textandtext (only message to text render — text text ms) and State
        to READY text‌textandtext. text log‌text cycletext text ([SNAPSHOT_STATE]/[SNAPSHOT
        PRELOAD]/textorder) with same text beforetext text text‌text.
        versiontext 10text24 — if scene text from Worker text withtext to‌text text‌text
        «scenetext text» textandtext text‌textandtext (render line/fill with AA real textandtext GPU) —
        matplotlib text text text in path display text."""
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
            # --- versiontechnical note 10technical note24 — path technical note: technical note technical note‌technical note technical notefromtechnical note is not ---
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
                    self._snap_pre_photo = None          # technical noteandtechnical note from GC technical notefromtechnical note is not
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
                    scene = None            # decrease to path technical note‌technical note beforetechnical note
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
            self._snap_pre_photo = disp          # technical noteandtechnical note from GC
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
        """versiontext 10text23 — Show textandtext architecture GPU (text user):
          Show = renderer.show()  ←  only text queue.put (text ~0text1ms)
        in text moment text Toplevel/PhotoImage/UpdateLayeredWindow/
        SetWindowPos/Image.open/Render text text‌textandtext. andtextandtext/text/textandtext
        completetext inside GPU with Shader is and window text text‌text. cycletext text
        ([SNAPSHOT_STATE] + text end) with same text beforetext text text."""
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
            # technical note‌technical note «before from» hide technical note technical note‌technical noteandtechnical note (hide technical note technical note withtechnical note technical note‌technical note)
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
            # --- technical note Prebuilt GPU (without technical note technical note agetechnical note) ---
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
                # --- path technical note (never in technical noteortechnical note technical note technical notemust technical note technical note) ---
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
                # technical note technical note‌technical note in momenttechnical note Show (agetechnical note — only technical note)
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
            # --- Show (only technical note message — technical note ~0technical note1ms) ---
            anim_ms = 0 if TV_SNAP_DEBUG_NO_ANIM else int(TV_SNAP_ANIM_MS)
            # v10.29 — technical note‌technical note technical noteandtechnical note: technical note technical note‌technical note + technical note + technical note
            # technical note from technical note watchdog UI hidden‌technical notefromtechnical note technical notewithtechnical note technical note‌technical note (technical note end
            # technical note display‌technical note — technical note «chart 116 until technical note technical note»)technical note technical note technical note technical note
            # before from gpu.show is until technical note in technical noteandtechnical note Errortechnical note aftertechnical note technical note‌technical note
            # active technical note and watchdog cleanup technical note.
            self._snap_overlay_deadline_wall = (
                time.time() + float(seconds) + TV_SNAP_ANIM_MS / 1000.0
                + TV_SNAP_OVERDUE_GRACE_SEC)
            t_show = gpu.show(anim_ms, key=key)
            show_ms = (time.perf_counter() - t_show) * 1000.0
            # v10.28 — SHOWING: technical note renderer.show == technical note technical note technical note
            # from technical note‌technical note to after totaltechnical note in technical noteandtechnical noteandtechnical note consumed technical note‌technical noteandtechnical note (confirmation in
            # technical note aftertechnical note Worker from technical note technical noteandtechnical note technical note technical note‌technical noteandtechnical note).
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
                    return              # technical note new technical note — technical note technical note
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
                # technical note end (layertechnical note 3): technical note if technical noteandtechnical note smooth technical note technical note
                _sched(max(1, int((float(seconds)
                                   + TV_SNAP_ANIM_MS / 1000.0 + 1.2)
                                  * 1000.0)), _gpu_hide_this)

            def _entry_watchdog():
                # layertechnical note 2 — if chaintechnical note after technical note technical note technical noteandtechnical note
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
        """versiontext 10text23 — hidden‌textfromtext textandtext GPU:
          * untiltext after cycle textand and text text bump text‌textandtext
          * hide_now = text message → text render in same frame text text‌text
          * [SNAPSHOT_STATE] HIDDEN only if overlay andtext withtextis."""
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
        """v10.29 (textandtext v1.2.2 from 2017) — text «end display text
        charttext»: text 2 second in UI-Thread text text‌textandtext if charttext
        after from text «text text‌text + text + text» still textandtext text
        withtext (text total chaintext textandtext text‌layer text text withtext)text hidden‌textfromtext
        textwithtext idempotent text text‌textandtext: untiltext textand + window in level textandtext
        andtextandtext text (GPU) / textandtext (Tk). text withtext text «chart minutetext
        116 display data text and text text text and for always in textandtext textandtext
        text». text text in display text never text text text‌text — only
        when active text‌textandtext text text layer‌text text text textandtext withtext."""
        try:
            if getattr(self, "_closing", False):
                return          # technical note technical note — chaintechnical note withtechnical notetime‌technical note technical note‌technical note
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
        """versiontext 10text24 — re-blit text (text‌untiltext text‌text): scene fresh in
        same text/text display beforetext (keep_state) — without text text without
        matplotlibtext without text‌text."""
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
        """versiontext 10text23 — text UpdateLayeredWindowtext «same window» in architecture
        GPU: texture in same text textandtext text‌textandtext text text/andtext reset
        text‌textandtext (keep_state=True)."""
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
        """text windowtext text textagetext‌text «completetext text text» (shared text
        text‌withtext and path immediate — output: dict andtext window).
        versiontext 10text21 — test 6: if key data textandtext text WINDOW CREATED /
        PHOTOIMAGE READY / LAYERED READY in textorder cycletext text register
        text‌textandtext (text textuntiltext textand‌to‌textand beforetext is).
        versiontext 10text16 — if prepared=(disp, arr, geo) from text Worker text
        withtext text text agetext text‌text text text‌textandtext (only text window + text
        blit text)text andtext text before text resize/premultiply text‌textandtext.
        versiontext 10text17 — «textwithtextagetext» withtext Worker: if arr/disp/geo with
        text textandtext (dtype/shape/textfromtext)text withtext textandtext text text‌textandtext and
        path text text (10text15) text text‌textandtext — window text‌text with
        text‌text broken text text‌textandtext.
        versiontext 10text18 — text text UI (Toplevel/PhotoImage/update_idletasks/
        UpdateLayeredWindow) with trace time‌text text‌textandtext (text 5 user)text
        TV_SNAP_DEBUG_SMALL_BITMAP=True → text‌text text 256×256 (text 11).
        versiontext 10text19 — PhotoImage and Label text time‌text text‌textandtext
        (text text 10text user)text in Errortext windowtext text‌text textandtext and Error
        withtext textuntiltext text‌textandtext (without text windowtext text text)."""
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
                if not _ok:                 # withtechnical note broken → path technical note technical note
                    if trace is not None:
                        trace.step("Worker payload validation",
                                   note="INVALID — local fallback prepare")
                    prepared = None
                    disp, arr = None, None
            if prepared is None or disp is None:
                t0 = trace.begin() if trace is not None else 0.0
                x, y_final, w, h = snap_overlay_geometry(
                    img.width, img.height, sw, sh)
                disp = img.resize((w, h), Image.Resampling.LANCZOS)  # ratio technical note
                arr = None
                if trace is not None:
                    trace.end("Local resize (UI fallback — LANCZOS)", t0,
                              size=(w, h))
            if TV_SNAP_DEBUG_SMALL_BITMAP:
                # --- technical note 11 user — test level technical noteandtechnical note: 256×256 to‌technical note PNG real ---
                sz = max(32, int(TV_SNAP_DEBUG_BITMAP_SIZE))
                disp = Image.new("RGBA", (sz, sz), (0, 200, 255, 170))
                arr = _premultiply_rgba(disp)
                x, y_final, w, h = snap_overlay_geometry(sz, sz, sw, sh)
                if trace is not None:
                    trace.step("DEBUG SMALL-BITMAP TEST ACTIVE",
                               size=(sz, sz),
                               note=f"{sz}x{sz} instead of real snapshot")
            y_start = sh + 4                   # completetechnical note technical note technical note

            t_tk = trace.begin() if trace is not None else 0.0
            win = tk.Toplevel(self)
            if trace is not None:
                trace.end("Toplevel creation", t_tk)
            t_cfg = trace.begin() if trace is not None else 0.0
            win.overrideredirect(True)
            win.attributes("-topmost", True)   # Topmost only technical note‌technical note — technical note‌withtechnical note
            win.configure(bg="#000000")
            win.geometry(f"{w}x{h}+{x}+{y_start}")
            if trace is not None:
                trace.end("Window configuration (geometry/topmost)", t_cfg,
                          size=(w, h))
            if key is not None:
                self._snap_life_mark(key, "WINDOW CREATED (Toplevel+config)")
            photo, lbl = None, None
            if ImageTk is not None:
                # versiontechnical note 10technical note19 — time‌technical note technical note (technical note technical note 10technical note user)
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
                    "built_wall": time.perf_counter()}   # versiontechnical note 10technical note18
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
        """text‌withtext (UI-Thread): render/textandtext text + text windowtext text
        text 1-2 second before from momenttext displaytext andtextandtext aftertext only text is and
        text textandtext/rendertext in momenttext andtextandtext text text‌textandtext.
        versiontext 10text16 — resize + text‌text text beforetext in text Worker text text
        (prepared)text text‌text only window text text‌textandtext.
        versiontext 10text18 — totaltext window register text‌textandtext until in momenttext Show only «windowtext
        same totaltext» text textandtext + trace complete text UI.
        versiontext 10text19 (text 5/7/10 user):
          * andtext text «ready» only when register text‌textandtext text window «usable»
            withtext (Layered+arr+HWND in andtextandtext / PhotoImage in path text)text
          * textandtext [SNAPSHOT PRELOAD] PRELOAD COMPLETE with Window/HWND/Size/
            text text UI print text‌textandtext in text: NOT READY + Reason text
          * build_gen: if dispatch newtext in text istext text text withtext text‌textandtext.
        versiontext 10text23 — if architecture GPU active withtext total text path to
        _prepare_snapshot_overlay_gpu text‌textandtext (text windowtext Tk text
        text‌textandtext only GPU Texture textandtext text‌textandtext).
        versiontext 10text24 — scene text (in textandtext andtextandtext) to path GPU pass text‌textandtext."""
        if getattr(self, "_snap_gpu", None) is not None:
            return self._prepare_snapshot_overlay_gpu(
                img, path, at_end, prepared=prepared, trace=trace,
                key_tag=key_tag, build_gen=build_gen, scene=scene)
        try:
            if (build_gen is not None
                    and build_gen != getattr(self, "_snap_pre_build_gen",
                                             build_gen)):
                # technical note dispatch newtechnical note technical note — technical note technical note technical note is (superseded)
                # versiontechnical note 10technical note21 — test 6: in technical noteorder technical note register technical note‌technical noteandtechnical note
                self._snap_life_mark(key_tag,
                                     "PRELOAD SUPERSEDED (newer dispatch)")
                if trace is not None:
                    trace.step("Preload attempt superseded (newer dispatch)")
                    trace.finish()
                return
            # versiontechnical note 10technical note21 — test 6: callback UI andtechnical note technical note technical note
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
            st["key"] = key_tag                        # versiontechnical note 10technical note18
            st["at_end"] = bool(at_end)
            # --- versiontechnical note 10technical note19 — technical note technical note + technical note istechnical note ---
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
            st["state"] = "ready"                  # versiontechnical note 10technical note19
            st["built_wall"] = time.perf_counter()
            self._snap_pre_photo = st["photo"]     # technical noteandtechnical note from GC
            self._snap_pre = st
            # versiontechnical note 10technical note21 — test 6: PRELOAD COMPLETE / WINDOW READY + technical note
            # cycletechnical note technical note (until technical note moment) — technical note technical note with SHOW aftertechnical note
            self._snap_life_mark(key_tag, "PRELOAD COMPLETE (WINDOW READY)",
                                 note=f"UI build {ui_ms:.1f} ms")
            self._snap_life_dump(key_tag, "PRELOAD COMPLETE")
            # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] READY (PREPARING → READY)
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
                # --- technical note 10technical note user — technical noteandtechnical note end complete Preload ---
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
        """versiontext 10text16 — text andtextandtext/textandtext in «text text» (text text andtextandtext —
        text user: text to text text text):
          * text frame with time‌text text perf_counter textto text‌textandtext (if UI
            or text momentarily text textandtext frame aftertext exactly textandtext text
            time‌correct text‌text — text never text text‌text)text
          * text with SetWindowPos text (win32_move_hwnd) without text textandtext
            Tk — text textandtext UI-Thread text textandtext text impact text
          * textand with text (gen) — hide/windowtext new textdistance text beforetext text text‌text.
        versiontext 10text17 — «text textandtext» (text «PNG text withtext textortext»):
          * successfultext text SetWindowPos agetext text‌textandtext firsttext text → text
            «fail» in box textandtext text‌textandtext
          * text «text» textandtext Tk text (text after) — because text‌text
            aftertext text‌text textandtext text text‌text Tcl text text (textandtext textwithtext:
            after(0) from text never textfromtext text‌text = same text real
            «withtext textortext PNG»)text text in box text‌text and «text»
            UI-Thread (layertext 1-text) text text until 40ms after text‌textandtext and textandtext
            fallback (text after) text text text‌text.
        versiontext 10text18 (text 8/9 user):
          * SetThreadPriority(...,2) text text — text text «text» istext
            Game > Overlay from text firstandtext text (text 8)text
          * text with perf_counter textandtext time real text text‌textandtext (1000ms
            text — text 60→40fps text text textandtext text‌text)text
          * start/end/text/count frame and FPS text in trace register text‌textandtext.
        versiontext 10text20 (text 4/5/8 message new user) — tool text text frame:
          * «text» frame‌text register text‌textandtext: number / elapsed / text text /
            y real (GetWindowRect — detection text‌text DWM) / text and
            text real SetWindowPos (from text _SWP_LAST) / interval
            real from frame before / text real sleeptext
          * textandtext [SNAPSHOT ANIMATION DEBUG] «after from end text» text‌text
            print text‌textandtext until textandtext log‌text textandtext time‌text frame impact text
          * text: textortext/text/text interval and SetWindowPos (with
            numbertext frame) + text Stalltext (interval > 2× text)text
          * TV_SNAP_DEBUG_ANIM_NO_MOVE (test text): text and time‌text 40fps
            active text‌text andtext text SetWindowPos text text‌textandtext
          * text text «text» textandtext Tk text (only win32 + print)."""
        import threading as _th
        dur = max(0.05, TV_SNAP_ANIM_MS / 1000.0)
        step = max(0.008, TV_SNAP_ANIM_STEP_MS / 1000.0)
        no_move = bool(TV_SNAP_DEBUG_ANIM_NO_MOVE)

        def _dump(recs, note: str, total_ms: float) -> None:
            """versiontext 10text20 — print textandtext [SNAPSHOT ANIMATION DEBUG] (text 4).
            versiontext 10text24 — only with TV_SNAP_SHOW_DEBUG (text log textandtext)."""
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
                    # --- versiontechnical note 10technical note21 — test 5: technical note complete andtechnical noteandtechnical note frame ---
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
                # --- versiontechnical note 10technical note21 — technical note test 4/5 ---
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
            recs = []                 # versiontechnical note 10technical note20 — technical noteandtechnical note technical note frame
            prev_it = None            # momenttechnical note start frame before (interval)
            t0 = time.perf_counter()
            try:
                # --- versiontechnical note 10technical note18 — technical note 8 user: firstandtechnical note technical note technical note technical note
                # technical note‌technical noteandtechnical note (SetThreadPriority technical note technical note). technical note Overlay must
                # completetechnical note Non-Intrusive withtechnical note: Game > Overlay.
                if trace is not None:
                    trace.step("Animation thread started (priority: normal)",
                               hwnd=hwnd,
                               note=("Phase: " + anim_tag + " | "
                                     + _snap_tid_text()))
                nxt = t0
                while True:
                    if self._snap_anim_gen != gen:
                        box["result"] = "cancel"   # technical noteand technical note
                        if trace is not None:
                            trace.step("Animation cancelled (generation)")
                        _dump(recs, "CANCELLED (generation superseded)",
                              (time.perf_counter() - t0) * 1000.0)
                        return
                    it = time.perf_counter()
                    p = (it - t0) / dur
                    if p >= 1.0:
                        # --- technical note technical note (versiontechnical note 10technical note20: register technical note from frame‌technical note) ---
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
                    # --- versiontechnical note 10technical note20 — technical note 6: technical note technical note technical note frame from technical note
                    if no_move:
                        ok = True
                        swp_ms, fl, skipped = 0.0, 0, True
                        wrec = None
                    else:
                        ok = bool(win32_move_hwnd(hwnd, x, ty))
                        swp_ms = float(_SWP_LAST.get("dur_ms", 0.0))
                        fl = int(_SWP_LAST.get("flags", 0))
                        skipped = False
                        # versiontechnical note 10technical note21 — test 5: technical noteandtechnical note complete andtechnical noteandtechnical note technical note frame
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
                        box["result"] = "fail"     # technical noteto‌technical note technical note technical note
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
                        _s0 = time.perf_counter()   # technical note 4: technical note real sleep
                        time.sleep(dly)
                        recs[-1]["sleep_ms"] = \
                            (time.perf_counter() - _s0) * 1000.0
                    else:
                        nxt = time.perf_counter()   # technical note decreasetechnical note — withtechnical note
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
        """display chart textandtext text (must from UI-Thread text text textandtext):
        text/text from textandtext snap_overlay_geometry (below-text until 8Ktext
        ratio text exactly text text‌textandtext — text text text).
        versiontext 10text13 — chart text‌text text «text‌textandtext»: from text text text
        1 second with ease-in-out andtext text‌textandtext to text text‌text text‌text and
        with same lightweight to text text text‌text and after text text‌textandtext.
        versiontext 10text15 — windowtext text‌text (1-2 second beforetext text text) text
        text‌textandtext andtextandtext without text text textandtext text text‌textandtext.
        versiontext 10text16 — textandtext text text from UI-Thread text text: textandtext andtextandtext layer‌text
        text in «text text» with SetWindowPos text text text‌textandtext in
        text‌text text same text after beforetext (fallback) text text‌text.
        versiontext 10text17 — «text layertext text textandtext» (user: PNG text withtext textortext!):
          layer 1) text text only win32 — text in box text‌text (without text
                  textandtext Tktext aftertext text‌text in text text‌text Tcl never
                  textfromtext text‌textandtext — text realtext «withtext textortext»)text text
                  UI-Thread text text until 40ms after text‌textandtext: "ok" → end
                  text "fail" → textandtext text after text‌text text text
                  text‌text (fallback complete until geometry)text
          layer 2) «andtext‌text andtextandtext» after from text+600ms: if window still
                  to text text text (text text/text‌text text text/after
                  text text)text UI textandtext window text to text text text‌text and
                  cycletext text/textandtext text complete text‌text
          layer 3) «text end»: after from text display+text+text
                  hidden‌textfromtext textwithtext idempotent — text‌text text text‌text.
        + andtext complete window in _snap_overlay_state text text text‌textandtext until
          «text text‌untiltext text‌text» textandtext same window text in text re-blit text.
        versiontext 10text18 — (text 3 user) in momenttext Show «text» text agetext text
        text‌textandtext: windowtext text‌text only must same totaltext withtext in text text
        textandtext text complete in momenttext Show with log text register text‌textandtext. delay text
        aftertext hide windowtext beforetext path text/text and start/end text
        text in trace register text‌textandtext. TV_SNAP_DEBUG_NO_ANIM (text 10) =
        display without text (text direct) for text text text.
        versiontext 10text23 — if architecture GPU active withtext total text path to
        _show_snapshot_overlay_gpu text‌textandtext: Show only text queue.put is
        (text ~0text1ms) and text completetext inside GPU (Shader) text text‌textandtext —
        text SetWindowPos/Toplevel/PhotoImage in path is not."""
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
            # versiontechnical note 10technical note20 — technical note 8: technical note technical note current and Main/UI in momenttechnical note Show
            if trace is not None:
                try:
                    _mt = threading.main_thread()
                    trace.step("Thread IDs (current | Main/UI)",
                               note=(f"current: {_snap_tid_text()} | "
                                      f"Main/UI: {_mt.ident}"))
                except Exception:
                    pass
                # versiontechnical note 10technical note20 — technical note 9/10: technical note technical note in log (technical note test‌technical note)
                # versiontechnical note 10technical note21 — test 3 (SINGLE-MOVE) technical note to list technical note‌technical note technical note technical note
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
            # versiontechnical note 10technical note21 — test 6: SHOW (UI) in technical noteorder cycletechnical note technical note
            self._snap_life_mark(key if key is not None
                                 else ("end" if at_end else "?"),
                                 "SHOW (UI callback)")
            # versiontechnical note 10technical note15 — technical note‌technical note «before from» hide technical note technical note‌technical noteandtechnical note (hide in
            # end technical note technical noteandtechnical note preload technical note technical note withtechnical note technical note‌technical note) until technical note technical noteandtechnical note
            pre = getattr(self, "_snap_pre", None)
            self._snap_pre = None
            t_hide = trace.begin() if trace is not None else 0.0
            self._hide_snapshot_overlay()
            if trace is not None:
                trace.end("Hide previous overlay", t_hide)
            # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] SHOW (READY → SHOWING)
            self._snap_state_event(
                "SHOW", SnapshotState.SHOWING, key=key,
                extra=((f"latency={_lat_ms:.1f}ms")
                       if _lat_ms is not None else "latency=?"))
            st = None
            # versiontechnical note 10technical note18 — only windowtechnical note technical note‌technical note «same totaltechnical note» technical note technical note‌technical noteandtechnical note
            # versiontechnical note 10technical note19 — technical note complete technical note (technical note 12 user): window must
            # «technical note» istechnical note withtechnical note technical note technical note with technical note technical note log technical note‌technical noteandtechnical note.
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
                st = pre                              # windowtechnical note technical note‌technical note — technical note andtechnical noteandtechnical note
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
                # versiontechnical note 10technical note21 — test 6: windowtechnical note technical note‌technical note technical note technical note — technical note
                # cycletechnical note technical note with RACE CHECK (must gap technical noteregistertechnical note ~2s withtechnical note)
                self._snap_life_mark(key, "PREBUILT ACCEPTED AT SHOW")
                self._snap_life_dump(key, "SHOW — prebuilt accepted (no race)")
            else:
                # --- versiontechnical note 10technical note19 — technical note technical note + path technical note (technical note 7/8 user) ---
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
                # versiontechnical note 10technical note21 — test 6: before from technical note technical note technical note technical note Race from technical noteandtechnical note
                # technical noteorder cycletechnical note technical note log technical note‌technical noteandtechnical note (technical note E user)
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
                # windowtechnical note technical noteteamtechnical note technical noteusable technical noteandtechnical note technical note‌technical noteandtechnical note (without technical note)
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
            self._snap_overlay_photo = st["photo"]    # technical noteandtechnical note from GC
            self._snap_overlay_state = st             # versiontechnical note 10technical note17
            self._snap_overlay_after = []
            self._snap_anim_alive = True
            # v10.29 — technical note‌technical note technical noteandtechnical note (path Tk/Legacy) — same technical noteandtechnical note GPU
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
                """y real window — first from textandtext andtextandtext (GetWindowRect)text after Tk."""
                yy = win32_window_y(st.get("hwnd")) if st.get("hwnd") else None
                if yy is not None:
                    return int(yy)
                try:
                    return int(win.winfo_rooty())
                except Exception:
                    return None

            _cb_seq = [0]

            def _schedule(delay_ms: int, fn) -> None:
                """versiontext 10text20 — text 12 user: text callback text with
                textagetext‌text textandtext Main/UI (chaintext poll text watchdogtext
                andtextandtext/textandtext/hidden‌textfromtext) with Name / Scheduled / Executed /
                Latency / Duration log text‌textandtext until textinside text‌text with
                text exactly text textandtext. time‌text ratio to start trace
                (momenttext dispatch Show) text — same line‌time text
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
                """path fallback (textandtextandtext/without hwnd/text text): same
                text after versiontext 10text13 — textandtext UI-Thread with chaintext complete
                fallback (win32 → win32 → geometry) — always text text‌text.
                versiontext 10text18 — time‌text with perf_counter (text 9 user)."""
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

            # --- versiontechnical note 10technical note17 — layertechnical note 1: technical note + box + technical note UI-Thread ---
            # technical note only technical note technical note in box technical note‌technical noteandtechnical note (without technical note technical noteandtechnical note Tk —
            # aftertechnical note technical note‌technical note in technical note technical note‌technical note Tcl never technical notefromtechnical note technical note‌technical noteandtechnical note!).
            # technical note (UI-Thread) until 40ms after technical note technical note technical note‌technical noteandtechnical note:
            #   "ok"   → end technical note (done)technical note
            #   "fail" → technical noteandtechnical note technical note after technical note‌technical note technical note technical note technical note‌technical note
            #   technical note    → until technical note‌technical note technical note after technical noteandtechnical note technical note + done.

            def _run_anim(y0: int, y1: int, done, anim_trace=None,
                          anim_tag: str = "ENTRY") -> None:
                hwnd = st.get("hwnd") if layered else None
                if os.name == "nt" and hwnd:
                    box = {"result": None}
                    self._spawn_snap_anim_thread(
                        self._snap_anim_gen, hwnd, x, y0, y1, box,
                        trace=anim_trace, anim_tag=anim_tag)
                    # versiontechnical note 10technical note20 — technical note 8: technical note technical note technical note in same momenttechnical note
                    # spawn (correlation with technical noteandtechnical note ANIMATION DEBUG)
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
                            # versiontechnical note 10technical note20 — technical note 11: end technical note from technical note
                            # UI-Thread (distance until "Animation end" = untiltechnical note
                            # technical note 40ms or technical note UI-Thread — number detectiontechnical note)
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
                            # technical note technical note technical note technical note (technical note/technical note) — technical noteandtechnical note technical note
                            # (versiontechnical note 10technical note20: in test technical note technical note technical note technical notefrom is not)
                            if not TV_SNAP_DEBUG_ANIM_NO_MOVE:
                                _move(int(round(y1)))
                            done()
                            return
                        _schedule(40, _poll)

                    _schedule(40, _poll)
                else:
                    _anim_afterloop(y0, y1, done)

            # --- versiontechnical note 10technical note17 — cycletechnical note technical note with «technical note technical note‌layer» ---
            life = {"entry_done": False}

            def _hide_this():
                self._hide_snapshot_overlay(expect_win=win)

            def _begin_exit():
                """end text → textandtext with same lightweight (versiontext 10text13text text untiltext
                text text — text‌text 10text17 textandtext text textandtext).
                versiontext 10text18 — textandtext text trace independent text (text andtextandtext/textandtext:
                user — «text textandtext textandtext text text text‌textandtext»)."""
                if not win.winfo_exists():
                    return
                if TV_SNAP_DEBUG_NO_ANIM:
                    _move(int(round(y_start)))
                    _hide_this()
                    return
                exit_tr = SnapShowTrace("EXIT DEBUG", TV_SNAP_SHOW_DEBUG)
                exit_tr.step("Exit animation start")   # versiontechnical note 10technical note20 — technical note 11
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
                # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] VISIBLE (SHOWING → VISIBLE)
                self._snap_state_event(
                    "VISIBLE", SnapshotState.VISIBLE, key=key,
                    extra=("entry=%.0fms"
                           % ((time.perf_counter()
                               - self._snap_state_since) * 1000.0)))
                # end andtechnical noteandtechnical note → technical note to technical note technical note‌technical note → technical noteandtechnical note with same lightweight
                _schedule(max(1, int(float(seconds) * 1000.0)), _begin_exit)
                # layertechnical note 3 — technical note end: technical note if technical noteandtechnical note smooth technical note technical note
                # after from (technical note + technical note + technical note) hidden‌technical notefromtechnical note technical notewithtechnical note
                _schedule(max(1, int((float(seconds)
                                      + TV_SNAP_ANIM_MS / 1000.0 + 1.2)
                                     * 1000.0)), _hide_this)

            def _entry_watchdog():
                """layertext 2 — if andtextandtext complete text textandtext UI textandtext text text text
                text‌text: window textandtext to text text text‌textandtext and cycle resume
                text‌ortext. (text text / text text‌text / aftertext text —
                text‌codetext text text‌textandtext textandtext text‌text chart text text.)"""
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
                    # versiontechnical note 10technical note20 — test technical note: technical note technical note technical notefrom is nottechnical note only cycletechnical note
                    # technical note complete technical noteandtechnical note (window technical note technical note technical note technical note‌technical note)
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
            # v10.28 — SHOWING (path Tk/Legacy): window technical note/technical note technical note and
            # andtechnical noteandtechnical note in technical note technical note start technical note‌technical noteandtechnical note (technical note technical note technical note: technical note/technical note/
            # SINGLE-MOVE) — technical note technical note technical note.
            _ck_tk = key if key is not None else ("end" if at_end else "?")
            if at_end or _ck_tk == "end":
                self._snap_show_event("confirm_end", _ck_tk)
            else:
                self._snap_show_event("confirm", _ck_tk)
            self._snap_show_stage(
                _ck_tk, "SHOWING (Tk window accepted — entry starting)")
            if TV_SNAP_DEBUG_NO_ANIM:
                # --- technical note 10 user — test without technical note: Show → technical note ---
                # (versiontechnical note 10technical note21 = TEST 1 — ENTRY ANIMATION OFFtechnical note technical note same technical note
                # SetWindowPostechnical note technical note direct technical note register technical note‌technical noteandtechnical note — technical note test 1)
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
                # --- versiontechnical note 10technical note21 — test 3 user: only «technical note» SetWindowPos in
                # momenttechnical note andtechnical noteandtechnical note + technical noteandtechnical note technical notefromtechnical note‌technical note complete [SNAPSHOT SINGLE-MOVE
                # TEST]technical note without technical note/technical note/technical note technical note technical note in secondtechnical note first.
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
        """versiontext 10text21 — test 3 user: «only text SetWindowPos in momenttext andtextandtext».
        window from before Preload text and text text istext Show text text text‌text
        only «same text» textto‌text to text text text and with Performance
        Counter textfromtext‌text text‌textandtext (aftertext text text text text‌textandtext).
        text detectiontext text: text textandtext «textandtext UI-Thread» is (text‌text with
        text window) — text text message text‌text in text is nottext if text text
        ~100-200ms length text text inside textandtext textandtext/DWM/composition
        istext text time‌text text or text UI."""
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
                # path technical note complete (test 5): before/after + GetLastError + technical note
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
        win.title("⚙ text textagetext‌text chart TV")
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

        def _spin_row(parent, label, var, lo, hi, unit="minute", enabled_var=None):
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

        _title("time‌text display in text withtext (textagetext text minute before text text‌textandtext)")
        _spin_row(win, "text first", v["h1_minute"],
                  *TV_SNAP_RANGES["h1"], enabled_var=v["h1_enabled"])
        _spin_row(win, "text second", v["h2_minute"],
                  *TV_SNAP_RANGES["h2"], enabled_var=v["h2_enabled"])
        _spin_row(win, "andtext‌text text", v["et_minute"],
                  *TV_SNAP_RANGES["et"], enabled_var=v["et_enabled"])

        def _restore_defaults():
            for key in TV_SNAP_KEYS:
                v[f"{key}_minute"].set(str(TV_SNAP_DEFAULT_MINUTE[key]))
                v[f"{key}_enabled"].set(True)
            v["show_seconds"].set("20")
            v["end_seconds"].set("20")
            v["end_enabled"].set(True)

        tk.Button(win, text="↺ withtext to default (43 / 85 / 116)",
                  font=("Segoe UI", 9, "bold"), bg="#1a2336", fg="#00b4d8",
                  relief="flat", cursor="hand2", activebackground="#1a2336",
                  activeforeground="#ffffff",
                  command=_restore_defaults).pack(fill="x", padx=20, pady=(6, 0))

        _title("display and save")
        row_secs = tk.Frame(win, bg="#0d1420")
        row_secs.pack(fill="x", padx=20, pady=3)
        tk.Label(row_secs, text="text display textandtext text (secondtext real)",
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
        tk.Checkbutton(row_end, text="display in match end (end 90+ and 120+)",
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
        tk.Label(row_end, text="second", font=("Segoe UI", 9), fg="#7f8fa6",
                 bg="#0d1420").pack(side="left", padx=(4, 0))

        tk.Checkbutton(win, text="savetext text charttext (latest chart text withtext in foldertext Momentum_Saves)",
                       variable=v["permanent_save"], font=("Segoe UI", 10),
                       fg="#e6edf5", bg="#0d1420", activebackground="#0d1420",
                       selectcolor="#101a2c", anchor="e",
                       justify="right").pack(fill="x", padx=20, pady=3)
        tk.Checkbutton(win, text="register untiltext and time start withtext (withtext chart)",
                       variable=v["timestamp"], font=("Segoe UI", 10),
                       fg="#e6edf5", bg="#0d1420", activebackground="#0d1420",
                       selectcolor="#101a2c", anchor="e",
                       justify="right").pack(fill="x", padx=20, pady=3)

        # --- versiontechnical note 10technical note24 — archive complete technical notedatatechnical note withtechnical note (output/input) ---
        _title("archive textdatatext withtext (output ZIP + render again)")

        def _archive_export_now():
            def _w():
                p = self._export_match_archive()
                self.after(0, lambda: _done(p))

            def _done(p):
                try:
                    if p:
                        messagebox.showinfo(
                            "archive textdatatext withtext",
                            "archive complete text text:\n" + str(p), parent=win)
                    else:
                        messagebox.showerror(
                            "archive textdatatext withtext",
                            "text archive failed textandtext "
                            "(datatext withtext text in text is nottext)", parent=win)
                except Exception:
                    pass

            threading.Thread(target=_w, daemon=True,
                             name="archive-export").start()

        def _archive_render_pick():
            try:
                from tkinter import filedialog as _fd
                p = _fd.askopenfilename(
                    parent=win, title="text file archive (ZIP or JSON)",
                    filetypes=[("archive Momentum", "*.zip *.json"),
                               ("text file‌text", "*.*")])
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
                                os.startfile(out)   # withtechnical note technical note in technical noteandtechnical note‌technical note
                        except Exception:
                            pass
                        messagebox.showinfo(
                            "render again from archive",
                            "chart from archive text text:\n" + str(out),
                            parent=win)
                    else:
                        messagebox.showerror(
                            "render again from archive",
                            "read/render archive failed textandtext.", parent=win)
                except Exception:
                    pass

            threading.Thread(target=_w, daemon=True,
                             name="archive-render").start()

        tk.Button(win, text="⬇ output complete textdatatext withtext (ZIP — text moment)",
                  font=("Segoe UI", 9, "bold"), bg="#14405e", fg="#8ecdf7",
                  relief="flat", cursor="hand2", activebackground="#14405e",
                  activeforeground="#ffffff",
                  command=_archive_export_now).pack(fill="x", padx=20,
                                                    pady=(4, 0), ipady=3)
        tk.Button(win, text="⟳ render againtext chart from file archive (ZIP/JSON)",
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
            # versiontechnical note 10technical note15 — windowtechnical note technical note‌technical note possible is with technical note new (minutetechnical note
            # technical note/technical note display) technical note valid technical notewithtechnical note → withtechnical note technical note‌technical noteandtechnical note
            for _k in self.snap_engine.mid:
                self.snap_engine.mid[_k]["pre"] = False
            for _k in self.snap_engine.end:
                self.snap_engine.end[_k]["pre"] = False
            try:
                self._discard_snapshot_preload()
            except Exception:
                pass
            self._tv_dirty = True       # technical note untiltechnical note/time possible is technical noteandtechnical note technical noteandtechnical note
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
        tk.Button(btns, text="✓ save", font=("Segoe UI", 10, "bold"),
                  bg="#1a6b4a", fg="#ffffff", relief="flat", cursor="hand2",
                  activebackground="#1a6b4a", activeforeground="#ffffff",
                  command=_save).pack(side="right", padx=(8, 0), ipadx=14)
        tk.Button(btns, text="text", font=("Segoe UI", 10),
                  bg="#415a77", fg="#ffffff", relief="flat", cursor="hand2",
                  activebackground="#415a77", activeforeground="#ffffff",
                  command=_cancel).pack(side="right", ipadx=10)
        win.bind("<Escape>", lambda _e: _cancel())
        win.grab_set()
        win.lift()
        win.focus_force()


    @staticmethod
    def _gaussian_smooth(vals: List[float], sigma_samples: float) -> List[float]:
        """version 2: Gaussian smoothing real (text textortext text) — only layer display.
        input sigma text text «sample» is and withtext from GAUSSIAN_SIGMA (second withtext)
        text text distance textandtext sample‌text textto text‌textandtext in text textuntiltext smoothing
        independent from text sampling/text always text is.
        textto‌text with text edge-padding text text‌textandtext (without decrease/textortext text text).
        RAW MOMENTUM unchanged text‌text.
        """
        return _gauss_smooth_impl(vals, sigma_samples)

    def _display_value(self, raw: float) -> float:
        """Normalizing only in Presentation Layer — Raw Momentum overwrite text‌textandtext"""
        mode = self.config.DISPLAY_NORMALIZATION
        rng = self.config.DISPLAY_RANGE
        if mode == "raw":
            return raw
        if mode == "peak":
            peak = max(rng * 0.5, self._display_peak)
            return (raw / peak) * rng
        # fixed (default): soft-clipping technical note in withtechnical note ±DISPLAY_RANGE
        return rng * math.tanh(raw / max(1.0, self.config.DISPLAY_SOFT_SCALE))

    def _ui_post(self, fn, *args):
        """fallback text self.after(0, ...) for textandtext‌text text‌text:
          * after from start text (_closing) text callback fresh‌text text text‌textandtext
          * textandtext callback text textandtext UI-Thread first «_closing» text text text‌text and
            TclError (andtext textandtext) text text‌text text‌text — text Errortext
            «invalid command name» and frozentext text text text text‌text.
        versiontext 10text20 — text 12 user: callback text text with Snapshot
        (display / text‌withtext / hidden‌textfromtext) with Name / Scheduled /
        Executed / Latency / Duration log text‌textandtext (only when
        TV_SNAP_SHOW_DEBUG) — delay text after in text dispatch text text‌textandtext.
        v10.28 — output bool + text text text/text + fail-event for Show
        (textandtext v1.3 from 2017 — text «43/85 display data text and text text text»:
        beforetext text after/callback completetext text‌text text text‌text)."""
        _nm = getattr(fn, "__name__", "callback")
        _is_show = _nm in ("_show_snapshot_overlay", "_show_snapshot_overlay_gpu")
        _is_snap = _is_show or _nm in ("_prepare_snapshot_overlay",
                                       "_hide_snapshot_overlay")
        _log_cb = bool(TV_SNAP_SHOW_DEBUG) and _is_snap
        # v10.28 — technical note timetechnical note for log EXECUTED always for Show active is
        _sched = time.perf_counter() if (_log_cb or _is_show) else 0.0
        # v10.28 — totaltechnical note Snapshot for technical noteandtechnical note fail/show (latest technical noteandtechnical note dispatch)
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
                # v10.28 — technical note EXECUTED for Show (log always-technical note)
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
            # v10.28 — technical note Scheduling never technical note‌technical note technical note‌technical note (technical note «technical noteandtechnical note» path)
            _report_fail(f"after(0) scheduling failed: "
                         f"{type(ex).__name__}: {ex}")
            return False

    def _graph_loop(self):
        if not self.is_monitoring or getattr(self, "_closing", False):
            return
        # versiontechnical note 10technical note12 — render livetechnical note technical note TV (when technical note technical note technical note‌technical noteandtechnical note only with change andtechnical note)
        try:
            self._refresh_tv_chart()
        except Exception as ex:
            clog(f"[TVGraph] {ex}")
        # version 2: Live Update chain‌technical note possession (same Row technical note technical note‌technical noteandtechnical note)
        try:
            self.update_ui_sequences(list(self.event_engine.sequences))
        except Exception as ex:
            clog(f"[Seq] {ex}")
        try:
            self.after(self.GRAPH_REFRESH_MS, self._graph_loop)
        except Exception:
            pass


    def build_events_tab(self, parent):
        cols = ("id", "time", "team", "type", "rel", "conf", "raw", "impact", "pos", "related", "tags")
        self.tree_ev = ttk.Treeview(parent, columns=cols, show="headings", height=16)

        heads = {"id": "#", "time": "time", "team": "team", "type": "textandtext text", "rel": "textwithtext",
                 "conf": "text", "raw": "Raw Score", "impact": "Momentum Impact",
                 "pos": "coordinates (X, Z)", "related": "andtext to ID", "tags": "textortext and specification"}
        widths = {"id": 40, "time": 58, "team": 68, "type": 190, "rel": 82, "conf": 60,
                  "raw": 78, "impact": 95, "pos": 100, "related": 80, "tags": 330}
        anchors = {"type": "w", "tags": "w"}
        for c in cols:
            self.tree_ev.heading(c, text=heads[c])
            self.tree_ev.column(c, width=widths[c], anchor=anchors.get(c, "center"))

        self.tree_ev.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_ev.yview)
        sb.pack(side="right", fill="y")
        self.tree_ev.configure(yscrollcommand=sb.set)
        self.tree_ev.bind("<Double-1>", self.on_event_double_click)


    def update_ui_events(self, events: List[GameEvent]):
        for ev in events:
            t_str = "Home" if ev.team == "Home" else "Away"
            m, s = divmod(int(ev.match_time), 60)
            p_str = f"{ev.position[0]:.1f}, {ev.position[1]:.1f}"
            r_str = ", ".join(map(str, ev.related_event_ids)) if ev.related_event_ids else "--"

            imp = self.momentum.get_impact(ev.event_id)
            raw_s = f"{imp.raw_threat:.0f}" if imp else "--"
            imp_s = f"{imp.final_impact:+.1f}" if imp else "--"

            self.tree_ev.insert("", 0, values=(
                ev.event_id, f"{m:02d}:{s:02d}", t_str, ev.event_type,
                ev.reliability.value, f"{int(ev.confidence * 100)}%",
                raw_s, imp_s, p_str, r_str, ", ".join(ev.tags)
            ))


    def on_event_double_click(self, _event):
        item = self.tree_ev.focus()
        if not item:
            return
        vals = self.tree_ev.item(item, "values")
        try:
            ev_id = int(vals[0])
        except (ValueError, IndexError):
            return
        ev = self.event_engine.get_event(ev_id)
        if not ev:
            return
        imp = self.momentum.get_impact(ev_id)
        core = self.runtime.get_core()
        cur_t = core["current_match_time"]

        m, s = divmod(int(ev.match_time), 60)
        lines = [
            f"textandtext text: {ev.event_type}",
            f"team: {'Home' if ev.team == 'Home' else 'Away'}",
            f"match time: {m:02d}:{s:02d}",
            f"Reliability: {ev.reliability.value}",
            f"Confidence: {int(ev.confidence * 100)}%",
        ]
        if imp:
            # version 2: for Goal Pulse from technical note passtechnical note technical note istechnical note technical note‌technical noteandtechnical note (technical note decay technical note)
            if imp.is_goal_pulse:
                f = self.momentum.goal_response_factor(imp, cur_t)
                phase = self.momentum.goal_pulse_phase(imp, cur_t)
                gm, gs = divmod(int(imp.goal_time), 60)
                pm, ps = divmod(int(imp.peak_time), 60)
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Goal Pulse: {phase} | factor text: {f:.3f}",
                    f"Goal Time: {gm:02d}:{gs:02d} → Peak Time: {pm:02d}:{ps:02d}",
                    f"Contribution moment‌text: {imp.final_impact * f:+.2f}",
                ]
            else:
                decay = self.momentum.decay_factor(max(0.0, cur_t - imp.match_time))
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Decay text: {decay:.3f}",
                    f"Contribution moment‌text: {imp.final_impact * decay:+.2f}",
                ]
            if imp.note:
                lines.append(f"textis score: {imp.note}")
        else:
            lines.append("Momentum Impact: -- (without score)")
        if ev.related_event_ids:
            lines.append(f"textandtextdatatext andtext: {', '.join(map(str, ev.related_event_ids))}")
        if ev.metadata:
            md_str = ", ".join(f"{k}={v}" for k, v in ev.metadata.items())
            lines.append(f"textuntiltextuntil: {md_str}")
        lines.append(f"text‌text: {', '.join(ev.tags)}")
        messagebox.showinfo(f"textortext text #{ev.event_id}", "\n".join(lines))


    def build_sequences_tab(self, parent):
        seq_cols = ("id", "team", "dur", "prog", "passes", "shots", "chances", "f3rd", "box", "status")
        self.tree_seq = ttk.Treeview(parent, columns=seq_cols, show="headings", height=16)
        heads = {"id": "Seq #", "team": "team", "dur": "text (s)", "prog": "textandtext (m)",
                 "passes": "count pass", "shots": "count shot", "chances": "text",
                 "f3rd": "andtextandtext to third", "box": "andtextandtext to textandtext", "status": "andtext"}
        widths = {"id": 55, "team": 70, "dur": 75, "prog": 85, "passes": 85, "shots": 85,
                  "chances": 65, "f3rd": 105, "box": 105, "status": 170}
        for c in seq_cols:
            self.tree_seq.heading(c, text=heads[c])
            self.tree_seq.column(c, width=widths[c], anchor="center")
        # color technical note for chain‌technical note active (Live)
        self.tree_seq.tag_configure("active", foreground="#00f5d4")
        self.tree_seq.tag_configure("ended", foreground="#c8d3e0")
        self.tree_seq.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_seq.yview)
        sb.pack(side="right", fill="y")
        self.tree_seq.configure(yscrollcommand=sb.set)


    def update_ui_sequences(self, seqs: List[PossessionSequence]):
        """
        version 2 — Live Update real:
        text Sequence only text withtext Row text‌text (insert) and until match end «same Row»
        with tree.item(values=...) to‌textandtext text‌textandtext text text text text
        text‌textandtext. chaintext active text display data text‌textandtext and text from text text text
        (duration / ending_reason) in same Row register text‌text.
        """
        for s in seqs:
            t_str = "Home" if s.team == "Home" else "Away"
            if s.is_active:
                status = "active ⏳"
                tag = "active"
            else:
                status = s.ending_reason or "end"
                tag = "ended"
            vals = (
                s.seq_id, t_str, f"{s.duration:.1f}s", f"{s.territorial_gain:+.1f}m",
                s.pass_count, s.shot_count, s.chances_created,
                s.final_third_entries, s.box_entries, status
            )
            item = self._seq_row_items.get(s.seq_id)
            if item is None:
                item = self.tree_seq.insert("", 0, values=vals, tags=(tag,))
                self._seq_row_items[s.seq_id] = item
            else:
                if self._seq_last_values.get(s.seq_id) != vals:
                    self.tree_seq.item(item, values=vals, tags=(tag,))
            self._seq_last_values[s.seq_id] = vals


    def build_details_tab(self, parent):
        wrap = tk.Frame(parent, bg="#090c12")
        wrap.pack(fill="both", expand=True)

        # --- card latest pass ---
        card_pass = tk.LabelFrame(wrap, text="  text text latest pass  ",
                                  font=("Segoe UI", 10, "bold"), fg="#00f5d4", bg="#111722", padx=10, pady=5)
        card_pass.pack(fill="x", padx=10, pady=(8, 3))

        r1 = tk.Frame(card_pass, bg="#111722")
        r1.pack(fill="x")
        self.lbl_card_title = tk.Label(r1, text="textandtext pass: in text start withtext...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#111722")
        self.lbl_card_title.pack(side="left")
        self.lbl_card_threat = tk.Label(r1, text="Threat Score: --", font=("Segoe UI", 12, "bold"), fg="#ff70a6", bg="#111722")
        self.lbl_card_threat.pack(side="right", padx=10)
        self.lbl_card_outcome = tk.Label(r1, text="", font=("Segoe UI", 11, "bold"), bg="#111722")
        self.lbl_card_outcome.pack(side="right")

        r2 = tk.Frame(card_pass, bg="#182030", padx=8, pady=4)
        r2.pack(fill="x", pady=3)
        self.lbl_players = tk.Label(r2, text="text: -- ➔ text: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#182030")
        self.lbl_players.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_flight_time = tk.Label(r2, text="time pass: -- second", font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#182030")
        self.lbl_flight_time.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_confidence = tk.Label(r2, text="text text: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#182030")
        self.lbl_confidence.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_tags = tk.Label(r2, text="andtext‌text: --", font=("Segoe UI", 9), fg="#f4a261", bg="#182030")
        self.lbl_tags.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_metrics = tk.Label(r2, text="length: -- | textandtext lengthtext X: -- | textandtext widthtext Z: -- | textandtext height Y: --",
                                    font=("Segoe UI", 8), fg="#94a3b8", bg="#182030")
        self.lbl_metrics.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- card latest shot ---
        card_shot = tk.LabelFrame(wrap, text="  text text‌text latest shot  ",
                                  font=("Segoe UI", 10, "bold"), fg="#ff3366", bg="#0f1422", padx=10, pady=5)
        card_shot.pack(fill="x", padx=10, pady=3)

        s1 = tk.Frame(card_shot, bg="#0f1422")
        s1.pack(fill="x")
        self.lbl_shot_title = tk.Label(s1, text="textandtext shot: in text register text shot...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#0f1422")
        self.lbl_shot_title.pack(side="left")
        self.lbl_shot_threats = tk.Label(s1, text="Pre Threat: -- | Final Threat: --", font=("Segoe UI", 12, "bold"), fg="#ff0055", bg="#0f1422")
        self.lbl_shot_threats.pack(side="right", padx=10)
        self.lbl_shot_outcome = tk.Label(s1, text="result: --", font=("Segoe UI", 11, "bold"), fg="#00f5d4", bg="#0f1422")
        self.lbl_shot_outcome.pack(side="right", padx=15)

        s2 = tk.Frame(card_shot, bg="#172033", padx=8, pady=4)
        s2.pack(fill="x", pady=3)
        self.lbl_shooter = tk.Label(s2, text="text: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#172033")
        self.lbl_shooter.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_speed = tk.Label(s2, text="text text ball: -- km/h", font=("Segoe UI", 9, "bold"), fg="#f72585", bg="#172033")
        self.lbl_speed.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_ontarget = tk.Label(s2, text="andtext textandtext: --", font=("Segoe UI", 9, "bold"), fg="#4cc9f0", bg="#172033")
        self.lbl_ontarget.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_shot_conf = tk.Label(s2, text="text: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#172033")
        self.lbl_shot_conf.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_shot_geom = tk.Label(s2, text="distance shot: -- | textandtext text: -- | distance with post: -- | textandtext height: --",
                                      font=("Segoe UI", 8), fg="#94a3b8", bg="#172033")
        self.lbl_shot_geom.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- technical notefirst untiltechnical note pass and shot ---
        tables = tk.Frame(wrap, bg="#090c12")
        tables.pack(fill="both", expand=True, padx=10, pady=6)

        left = tk.LabelFrame(tables, text="  📋 untiltext pass‌text (text‌totaltext = textortext)  ",
                             font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#090c12")
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        pcols = ("id", "time", "team", "type", "threat", "conf", "passer", "receiver", "dist", "status")
        self.tree_pass = ttk.Treeview(left, columns=pcols, show="headings", height=9)
        pheads = {"id": "#", "time": "time", "team": "team", "type": "textandtext pass", "threat": "Threat",
                  "conf": "text", "passer": "text", "receiver": "text", "dist": "length (m)", "status": "result"}
        for c in pcols:
            self.tree_pass.heading(c, text=pheads[c])
            self.tree_pass.column(c, width=78, anchor="center" if c != "type" else "w")
        self.tree_pass.pack(side="left", fill="both", expand=True)
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.tree_pass.yview)
        sb1.pack(side="right", fill="y")
        self.tree_pass.configure(yscrollcommand=sb1.set)
        self.tree_pass.bind("<Double-1>", self.on_pass_double_click)

        right = tk.LabelFrame(tables, text="  🎯 untiltext shot‌text (text‌totaltext = textortext)  ",
                              font=("Segoe UI", 9, "bold"), fg="#ff3366", bg="#090c12")
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        scols = ("id", "time", "team", "type", "pre", "final", "outcome", "speed", "dist", "conf")
        self.tree_shot = ttk.Treeview(right, columns=scols, show="headings", height=9)
        sheads = {"id": "#", "time": "time", "team": "team", "type": "textandtext shot", "pre": "Pre Thr",
                  "final": "Final Thr", "outcome": "result", "speed": "text", "dist": "distance", "conf": "text"}
        for c in scols:
            self.tree_shot.heading(c, text=sheads[c])
            self.tree_shot.column(c, width=78, anchor="center" if c not in ("type", "outcome") else "w")
        self.tree_shot.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(right, orient="vertical", command=self.tree_shot.yview)
        sb2.pack(side="right", fill="y")
        self.tree_shot.configure(yscrollcommand=sb2.set)
        self.tree_shot.bind("<Double-1>", self.on_shot_double_click)


    def update_pass_card(self, ev: PassEventData):
        self.runtime.set_pass(ev)
        self._ui_pass_list.append(ev)
        team_str = "Home" if ev.team == "Home" else "Away"
        out_txt = "successful ✅" if ev.is_success else "failed / text ❌"
        out_col = "#2ecc71" if ev.is_success else "#e63946"

        self.lbl_card_title.config(text=f"textandtext pass: {ev.pass_type} ({team_str})")
        self.lbl_card_threat.config(text=f"Threat Score: {ev.threat_score}/100")
        self.lbl_card_outcome.config(text=out_txt, fg=out_col)

        p_str = f"text {ev.passer_seat}" if ev.passer_seat else "nametext"
        r_str = f"text {ev.receiver_seat}" if ev.receiver_seat else "nametext"
        self.lbl_players.config(text=f"text: {p_str} ➔ text: {r_str}")
        self.lbl_flight_time.config(text=f"time textandfrom ball: {ev.flight_time:.2f} second")
        self.lbl_confidence.config(text=f"text text: {int(ev.confidence * 100)}%")
        self.lbl_tags.config(text=f"andtext‌text: {', '.join(ev.tags) if ev.tags else 'text'}")
        self.lbl_metrics.config(
            text=(f"length: {ev.distance:.1f}m | textandtext lengthtext X: {ev.forward_progress:+.1f}m | "
                  f"textandtext widthtext Z: {ev.lateral_progress:.1f}m | textandtext height Y: {ev.max_height:.2f}m")
        )

        m, s = divmod(int(ev.match_time), 60)
        self.tree_pass.insert("", 0, values=(
            ev.event_id, f"{m:02d}:{s:02d}", team_str, ev.pass_type,
            f"{ev.threat_score}", f"{int(ev.confidence * 100)}%",
            p_str, r_str, f"{ev.distance:.1f}",
            "successful" if ev.is_success else "failed"
        ))


    def update_shot_card(self, ev: ShotEventData):
        self.runtime.set_shot(ev)
        self._ui_shot_list.append(ev)
        team_str = "Home" if ev.team == "Home" else "Away"

        self.lbl_shot_title.config(text=f"textandtext shot: {ev.primary_type} ({team_str})")
        self.lbl_shot_threats.config(text=f"Pre Thr: {ev.pre_shot_threat} | Final Thr: {ev.final_threat}")

        outcome_color = "#00f5d4"
        if "text" in ev.outcome: outcome_color = "#2ecc71"
        elif "post" in ev.outcome: outcome_color = "#fca311"
        elif "text" in ev.outcome: outcome_color = "#e63946"
        self.lbl_shot_outcome.config(text=f"result: {ev.outcome}", fg=outcome_color)
        self.lbl_shooter.config(text=f"text: text {ev.shooter_seat} ({team_str})")

        sp_txt = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "-- (text textto)"
        self.lbl_speed.config(text=f"text text ball: {sp_txt}")
        self.lbl_ontarget.config(
            text=f"andtext: {'in textandtext ✅' if ev.is_on_target else 'text textandtext ❌'}",
            fg="#2ecc71" if ev.is_on_target else "#e63946"
        )
        self.lbl_shot_conf.config(text=f"text: {int(ev.confidence * 100)}%")
        sign_desc = "inside" if ev.woodwork_distance < 0 else "text"
        self.lbl_shot_geom.config(
            text=(f"distance: {ev.distance_to_goal:.1f}m | textandtext: {ev.goal_angle_deg:.1f}° | "
                  f"post: {ev.woodwork_distance:+.2f}m ({sign_desc}) | textandtext height: {ev.max_height:.2f}m | "
                  f"text text: {ev.defenders_in_corridor}")
        )

        m, s = divmod(int(ev.match_time), 60)
        self.tree_shot.insert("", 0, values=(
            ev.event_id, f"{m:02d}:{s:02d}", team_str, ev.primary_type,
            f"{ev.pre_shot_threat}", f"{ev.final_threat}", ev.outcome,
            sp_txt, f"{ev.distance_to_goal:.1f}m", f"{int(ev.confidence * 100)}%"
        ))


    def on_pass_double_click(self, _event):
        item = self.tree_pass.focus()
        if not item: return
        try:
            pid = int(self.tree_pass.item(item, "values")[0])
        except (ValueError, IndexError):
            return
        ev = next((p for p in self._ui_pass_list if p.event_id == pid), None)
        if not ev: return
        m, s = divmod(int(ev.match_time), 60)
        msg = (
            f"pass number: {ev.event_id}\n"
            f"match time: {m:02d}:{s:02d}\n"
            f"text textandfrom ball: {ev.flight_time:.2f} second\n"
            f"team: {ev.team}\n"
            f"text: text {ev.passer_seat} ➔ text: text {ev.receiver_seat}\n\n"
            f"textandtext pass: {ev.pass_type}\n"
            f"text text (Threat): {ev.threat_score}/100\n"
            f"text text: {int(ev.confidence * 100)}%\n\n"
            f"textdecrease pass: {ev.distance:.1f} m\n"
            f"textandtext lengthtext X: {ev.forward_progress:+.1f} m\n"
            f"textto‌text widthtext Z: {ev.lateral_progress:.1f} m\n"
            f"textandtext height Y: {ev.max_height:.2f} m\n"
            f"result pass: {'successful ✅' if ev.is_success else 'text text / failed ❌'}\n\n"
            f"text pass: ({ev.start_ball[0]:.1f}, {ev.start_ball[1]:.1f}) ➔ text: ({ev.end_ball[0]:.1f}, {ev.end_ball[1]:.1f})"
        )
        messagebox.showinfo(f"specification complete pass #{ev.event_id}", msg)


    def on_shot_double_click(self, _event):
        item = self.tree_shot.focus()
        if not item: return
        try:
            sid = int(self.tree_shot.item(item, "values")[0])
        except (ValueError, IndexError):
            return
        ev = next((x for x in self._ui_shot_list if x.event_id == sid), None)
        if not ev: return
        m, s = divmod(int(ev.match_time), 60)
        sign_str = "inside textandtext" if ev.woodwork_distance < 0 else "text textandtext"
        sp_str = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "nametext / text textto"
        msg = (
            f"🎯 shot number: {ev.event_id}\n"
            f"match time: {m:02d}:{s:02d}\n"
            f"team: {ev.team} (text {ev.shooter_seat})\n"
            f"textandtext shot: {ev.primary_type}\n"
            f"andtext‌text: {', '.join(ev.tags)}\n\n"
            f"🚀 text textto: {sp_str}\n"
            f"🎯 textandtext: {'in textandtext ✅' if ev.is_on_target else 'text from textandtext ❌'}\n"
            f"📏 distance with post: {ev.woodwork_distance:+.2f}m ({sign_str})\n"
            f"📊 result text: {ev.outcome}\n\n"
            f"🔥 Pre-Shot Threat (Opportunity Value): {ev.pre_shot_threat}/100\n"
            f"⚡ Final Threat (Momentum Impact): {ev.final_threat}/100\n"
            f"🛡️ text (Confidence): {int(ev.confidence * 100)}%\n\n"
            f"distance until inandfromtext: {ev.distance_to_goal:.1f}m | textandtext: {ev.goal_angle_deg:.1f}°\n"
            f"text text: {ev.defenders_in_corridor} | nearest text: {ev.nearest_defender_dist:.1f}m\n"
            f"text ball: {ev.curve_ratio * 100:.1f}% ({ev.curve_dir})\n"
        )
        if ev.candidate_scores:
            msg += "\nscore text:\n"
            for cand, sc in sorted(ev.candidate_scores.items(), key=lambda x: x[1], reverse=True)[:8]:
                msg += f"  - {cand}: {sc:.1f}\n"
        messagebox.showinfo(f"specification complete shot #{ev.event_id}", msg)


    def build_debug_tab(self, parent):
        info = tk.Frame(parent, bg="#0d111a", padx=10, pady=6)
        info.pack(fill="x")

        self.lbl_time_hook = tk.Label(info, text="Time Hook: --", font=("Consolas", 9, "bold"), fg="#00f5d4", bg="#0d111a")
        self.lbl_time_hook.grid(row=0, column=0, sticky="w", padx=8)
        self.lbl_gmin = tk.Label(info, text="Game Minute: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_gmin.grid(row=0, column=1, sticky="w", padx=8)
        self.lbl_gsec = tk.Label(info, text="Game Second: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_gsec.grid(row=0, column=2, sticky="w", padx=8)
        self.lbl_total_t = tk.Label(info, text="Total Match Time: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_total_t.grid(row=0, column=3, sticky="w", padx=8)
        self.lbl_last_upd = tk.Label(info, text="Last Time Update: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_last_upd.grid(row=0, column=4, sticky="w", padx=8)
        self.lbl_poll = tk.Label(info, text="Poll Rate: --", font=("Consolas", 9), fg="#ffd166", bg="#0d111a")
        self.lbl_poll.grid(row=1, column=0, sticky="w", padx=8, pady=(3, 0))
        self.lbl_decay_info = tk.Label(info, text="Half-Life: -- s (Game Time)", font=("Consolas", 9), fg="#ffd166", bg="#0d111a")
        self.lbl_decay_info.grid(row=1, column=1, sticky="w", padx=8, pady=(3, 0))
        self.lbl_impact_count = tk.Label(info, text="Impacts: 0", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_impact_count.grid(row=1, column=2, sticky="w", padx=8, pady=(3, 0))
        # version 4: andtechnical note goal hook in technical note technical notewithtechnical note
        self.lbl_goal_hook_dbg = tk.Label(info, text="Goal Hook: -- | H: - A: -",
                                          font=("Consolas", 9, "bold"), fg="#a8dadc", bg="#0d111a")
        self.lbl_goal_hook_dbg.grid(row=1, column=3, sticky="w", padx=8, pady=(3, 0))

        table_wrap = tk.Frame(parent, bg="#090c12")
        table_wrap.pack(fill="both", expand=True, padx=10, pady=6)
        tk.Label(table_wrap, text="textandtext textandtext — for text text: chain Raw Threat → Base Weight → Reliability/Confidence → Final Impact → Decay → Contribution text | textandtext Goal: time text → time textandtext text (textfrom)",
                 font=("Segoe UI", 8), fg="#7f8fa6", bg="#090c12").pack(anchor="w", pady=(0, 3))

        dcols = ("id", "time", "team", "event", "raw", "base", "rel", "conf", "final", "decay", "contrib", "linked", "goal")
        self.tree_debug = ttk.Treeview(table_wrap, columns=dcols, show="headings", height=13)
        dheads = {"id": "ID", "time": "Game Time", "team": "Team", "event": "Event", "raw": "Raw Threat",
                  "base": "Base Weight", "rel": "Reliability", "conf": "Conf",
                  "final": "Final Impact", "decay": "Decay", "contrib": "Current Contribution",
                  "linked": "Linked Event ID", "goal": "Goal Time → Peak (Pulse)"}
        dwidths = {"id": 45, "time": 62, "team": 58, "event": 165, "raw": 75, "base": 80,
                   "rel": 78, "conf": 50, "final": 85, "decay": 65, "contrib": 125,
                   "linked": 90, "goal": 170}
        for c in dcols:
            self.tree_debug.heading(c, text=dheads[c])
            self.tree_debug.column(c, width=dwidths[c], anchor="center" if c not in ("event", "goal") else "w")
        self.tree_debug.pack(side="top", fill="both", expand=True)
        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_debug.yview)
        sb.pack(side="right", fill="y")
        self.tree_debug.configure(yscrollcommand=sb.set)

        # --- version 2: technical note technical notewithtechnical note chain shot (Counter → Trigger → Tracking → Event → Bus) ---
        chain_wrap = tk.LabelFrame(table_wrap, text="  🔗 chain shot — Shot Counter → Engine → Event → Momentum (newtext withtext)  ",
                                   font=("Segoe UI", 8, "bold"), fg="#ff70a6", bg="#090c12")
        chain_wrap.pack(side="bottom", fill="x", pady=(5, 0))
        self.txt_shot_chain = tk.Text(chain_wrap, height=8, bg="#0b0f18", fg="#c8d3e0",
                                      font=("Consolas", 7), state="disabled", wrap="none")
        self.txt_shot_chain.pack(fill="both", expand=True, padx=4, pady=3)


    def refresh_debug_table(self):
        if not self.is_monitoring:
            return
        core = self.runtime.get_core()
        cur_t = core["current_match_time"]

        # section Debug information time
        hooked = self.engine.time_hooker.is_hooked and core["time_source"] == "HOOK"
        self.lbl_time_hook.config(text=f"Time Hook: {'ACTIVE ✅' if hooked else 'INACTIVE (FALLBACK) ⚠'}",
                                  fg="#00f5d4" if hooked else "#fca311")
        self.lbl_gmin.config(text=f"Game Minute: {core['game_minute'] if core['game_minute'] is not None else '--'}")
        self.lbl_gsec.config(text=f"Game Second: {core['game_second'] if core['game_second'] is not None else '--'}")
        tm, ts = divmod(int(cur_t), 60)
        self.lbl_total_t.config(text=f"Total Match Time: {cur_t:.2f}s ({tm:02d}:{ts:02d})")
        if core["last_time_change_wall"] > 0:
            ago = time.time() - core["last_time_change_wall"]
            self.lbl_last_upd.config(text=f"Last Time Update: {ago:.1f}s ago")
        self.lbl_poll.config(text=f"Poll Rate: {core['poll_rate_ms']:.1f} ms")
        self.lbl_decay_info.config(text=f"Half-Life: {self.config.MOMENTUM_HALF_LIFE:.0f}s (Game Time)")
        self.lbl_impact_count.config(text=f"Impacts: {len(self.momentum.impacts)}")

        # version 4: andtechnical note goal hook in technical note technical notewithtechnical note
        gh = self._goal_hook_status
        if gh["hooked"]:
            if gh["captured"]:
                dbg_txt = (f"Goal Hook: ACTIVE ✅ | H: {gh['home'] if gh['home'] is not None else '-'} "
                           f"A: {gh['away'] if gh['away'] is not None else '-'} | rcx=0x{gh['rcx']:X}"
                           if gh["rcx"] else "Goal Hook: ACTIVE ✅ | waiting write...")
                dbg_color = "#00f5d4"
            else:
                dbg_txt = "Goal Hook: INSTALLED ⏳ (in text firsttext write structure text)"
                dbg_color = "#ffd166"
            if gh["secondary"]:
                dbg_txt += " | away-write hook: YES"
        else:
            dbg_txt = "Goal Hook: INACTIVE ⚠ (register text disabled)"
            dbg_color = "#fca311"
        self.lbl_goal_hook_dbg.config(text=dbg_txt, fg=dbg_color)

        # technical noteandtechnical note Impact technical note (latest 200 technical noteandtechnical note for technical noteandtechnical note) — version 2 with technical noteandtechnical note‌technical note Linked/Goal
        with self.momentum._lock:
            impacts = list(self.momentum.impacts[-200:])
        self.tree_debug.delete(*self.tree_debug.get_children())
        for imp in impacts:
            if imp.is_goal_pulse:
                # Goal Pulse: technical noteandtechnical note from technical note passtechnical note technical note (technical note decay technical note technical note)
                factor = self.momentum.goal_response_factor(imp, cur_t)
                phase = self.momentum.goal_pulse_phase(imp, cur_t)
                contrib = imp.final_impact * factor
                goal_str = f"{_fmt_clock(imp.goal_time)} → {_fmt_clock(imp.peak_time)} ({phase})"
            else:
                factor = self.momentum.decay_factor(max(0.0, cur_t - imp.match_time))
                contrib = imp.final_impact * factor
                goal_str = "--"
            m, s = divmod(int(imp.match_time), 60)
            team_str = "Home" if imp.team == "Home" else "Away"
            linked_str = ", ".join(str(i) for i in imp.linked_ids) if imp.linked_ids else "--"
            self.tree_debug.insert("", 0, values=(
                imp.source_event_id, f"{m:02d}:{s:02d}", team_str, imp.event_type,
                f"{imp.raw_threat:.0f}", f"{imp.base_weight:.1f}", imp.reliability,
                f"{int(imp.confidence * 100)}%", f"{imp.final_impact:+.2f}",
                f"{factor:.3f}", f"{contrib:+.2f}", linked_str, goal_str
            ))

        # --- version 2: render chain shot (newtechnical note withtechnical note) ---
        try:
            lines = []
            for e in list(self.shot_debug_log)[-60:]:
                w = time.strftime("%H:%M:%S", time.localtime(e["wall"]))
                extras = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("wall", "stage"))
                lines.append(f"{w} | {e['stage']:<28} | {extras}")
            self.txt_shot_chain.config(state="normal")
            self.txt_shot_chain.delete("1.0", "end")
            body = "\n".join(reversed(lines))
            # versiontechnical note 10technical note14 — line technical note chaintechnical note shot always in withtechnical note technical noteandtechnical note technical notewithtechnical note
            try:
                _st = self.shot_engine.stats
                stats_txt = ("[SHOT STATS] " + " | ".join(f"{k}={v}" for k, v in _st.items()))
            except Exception:
                stats_txt = "[SHOT STATS] --"
            self.txt_shot_chain.insert("1.0", stats_txt + ("\n" + body if body else ""))
            self.txt_shot_chain.config(state="disabled")
        except Exception:
            pass
        try:
            self.after(self.DEBUG_REFRESH_MS, self.refresh_debug_table)
        except Exception:
            pass


    def start_monitoring(self, *args, **kwargs):
        """Manual attach (header button). v2.1.0 — the GUI build shows the
        original error dialog on failure; the headless build logs instead."""
        ok, msg = self.engine.initialize()
        if not ok:
            if getattr(self, "_gui_active", False):
                try:
                    messagebox.showerror("Error", msg)
                except Exception:
                    pass
            clog(f"[Momentum] attach failed: {msg}")
            return
        self._begin_monitoring(msg, manual=True)

    def update_field_geometry(self, players: List[Dict]):
        # versiontechnical note 10technical note18 — guard TclError: after from technical note technical notenametechnical note callbacktechnical note
        # withtechnical note‌technical note technical notemust Errortechnical note «invalid command name» technical note
        try:
            self._update_field_geometry_impl(players)
        except tk.TclError:
            pass


    def _update_field_geometry_impl(self, players: List[Dict]):
        gk1 = next((p for p in players if p["seat"] == 1), None)
        gk12 = next((p for p in players if p["seat"] == 12), None)
        if gk1 and gk12:
            if gk1["x"] < gk12["x"]:
                self.team1_side_name = "text text (text ➔ textis)"
                self.team2_side_name = "text textis (text ⬅ text)"
                self.team1_attack_dir = 1
                info = "pitch: Home in text (text ➔) | Away in textis (text ⬅)"
            else:
                self.team1_side_name = "text textis (text ⬅ text)"
                self.team2_side_name = "text text (text ➔ textis)"
                self.team1_attack_dir = -1
                info = "pitch: Home in textis (text ⬅) | Away in text (text ➔)"
            self.lbl_field_info.config(text=info)
            self.geometry_ready = True

    def update_time_status(self, m_state: str, g_min: Optional[int], g_sec: Optional[int], total_t: float):
        """to‌textandtext card Match Time and andtext withtext (from Worker)
        versiontext 10text18 — guard TclError for text text textnametext."""
        try:
            self._update_time_status_impl(m_state, g_min, g_sec, total_t)
        except tk.TclError:
            pass


    def _update_time_status_impl(self, m_state: str, g_min: Optional[int], g_sec: Optional[int], total_t: float):
        m, s = divmod(int(total_t), 60)
        self.lbl_match_time.config(text=f"{m:02d}:{s:02d}")
        src = "HOOK ✅ (RSI)" if g_min is not None else "FALLBACK ⚠"
        self.lbl_clock_src.config(text=f"Game Clock: {src}")
        if m_state == "PLAYING":
            self.lbl_status.config(text="andtext: match live 🟢", fg="#2ecc71")
        else:
            self.lbl_status.config(text="andtext: PAUSED / REPLAY / STOPPED ⏸", fg="#e63946")


    def _init_pipeline_health(self):
        """text‌text/counter‌text layertext detectiontext (version 10text4)"""
        self._gate_counts = {"loop": 0, "ball_players": 0, "geometry": 0,
                             "not_playing": 0, "pass_trig": 0, "shot_trig": 0}
        self._poss_last_ok_wall: Optional[float] = None
        self._poss_last_rearm_wall: Optional[float] = None
        self._players_last_ok_wall: Optional[float] = None
        self._wd_last_total_t: Optional[float] = None
        self._pass_last_chg_wall: Optional[float] = None
        self._pass_last_val: Optional[int] = None
        self._shot_last_chg_wall: Optional[float] = None
        self._shot_last_val: Optional[int] = None
        self._poss_cap_seen: Optional[int] = None

    def _pipeline_health_tick(self, m_state: str, total_t: Optional[float],
                              poss: Optional[str], ball, players,
                              pass_cnt: Optional[int], shot_cnt: Optional[int],
                              now_wall: float, clk_hook: bool):
        """
        version 10text4 — text text Worker (lightweight): to‌textandtext textortext‌text + in time duetext
        write text line Heartbeat complete + Warningtext STALE. text‌andtext exception withtext
        text‌text and text textortext original‌text text change text‌text (only text + re-arm).
        """
        try:
            dbg = getattr(self, "dbg", None)
            if dbg is None or not getattr(dbg, "enabled", False):
                return
            gc = self._gate_counts
            gc["loop"] += 1

            # --- technical noteortechnical note possession + technical note address capture (technical notewithtechnical note change address technical note withtechnical note‌technical note) ---
            poss_ok = poss in ("Home", "Away")
            if poss_ok:
                self._poss_last_ok_wall = now_wall
            cap = getattr(self.engine.poss_hooker, "captured_address", None)
            if cap != self._poss_cap_seen:
                if self._poss_cap_seen is not None and cap is not None:
                    dbg.event("POSS_CAPTURE_CHANGED",
                              old=fmt_ptr(self._poss_cap_seen), new=fmt_ptr(cap),
                              note="address capture possession textandtext text (withtext new structure fresh)")
                self._poss_cap_seen = cap

            # --- technical note currently technical note technical note (for watchdog technical notememory‌technical note) ---
            time_adv = (total_t is not None and self._wd_last_total_t is not None
                        and float(total_t) > float(self._wd_last_total_t))
            self._wd_last_total_t = total_t

            # --- Watchdog re-arm possession (before from technical note‌technical note technical noteandtechnical note always live) ---
            if not poss_ok and m_state == "PLAYING":
                stale = freeze_seconds(self._poss_last_ok_wall, now_wall)
                thr_ok = (self._poss_last_rearm_wall is None
                          or (now_wall - self._poss_last_rearm_wall) >= POSS_REARM_THROTTLE_SEC)
                if possession_rearm_needed(poss_ok, m_state, time_adv, stale, thr_ok):
                    old_cap = cap
                    try:
                        self.engine.reset_possession_capture()
                    except Exception:
                        pass
                    self._poss_last_rearm_wall = now_wall
                    dbg.event("POSS_REARM", old_cap=fmt_ptr(old_cap),
                              stale_s=round(stale, 1),
                              t=(round(float(total_t), 1) if total_t is not None else None),
                              note="capture possession again armed text — firsttext run instruction possession address fresh text text‌text")

            # --- technical noteortechnical note players ---
            if players:
                self._players_last_ok_wall = now_wall

            # --- technical noteortechnical note changetechnical note counter‌technical note (for technical notefromtechnical note‌technical note technical note) ---
            if pass_cnt != self._pass_last_val:
                self._pass_last_val = pass_cnt
                if pass_cnt is not None:
                    self._pass_last_chg_wall = now_wall
            if shot_cnt != self._shot_last_val:
                self._shot_last_val = shot_cnt
                if shot_cnt is not None:
                    self._shot_last_chg_wall = now_wall

            # --- Heartbeat (threshold‌technical note) ---
            if not dbg.heartbeat_due(now_wall):
                return
            try:
                diag = self.engine.debug_diagnostics()
            except Exception:
                diag = {}
            gh = getattr(self, "_goal_hook_status", None) or {}
            frz_poss = freeze_seconds(self._poss_last_ok_wall, now_wall)
            frz_players = freeze_seconds(self._players_last_ok_wall, now_wall)
            frz_pass = freeze_seconds(self._pass_last_chg_wall, now_wall)
            frz_shot = freeze_seconds(self._shot_last_chg_wall, now_wall)

            # --- Warningtechnical note STALE (before from line HB) ---
            if m_state == "PLAYING" and not poss_ok and frz_poss >= POSS_REARM_STALE_SEC:
                dbg.warn("Pipeline",
                         f"poss invalid for {frz_poss:.0f}s while PLAYING "
                         f"(cap={fmt_ptr(cap)}) — possession dead?")
            if m_state == "PLAYING" and not players and frz_players >= POSS_REARM_STALE_SEC:
                dbg.warn("Pipeline",
                         f"players=0 for {frz_players:.0f}s while PLAYING — "
                         f"PLAYERS_ARRAY dead/moved? (seat0={fmt_ptr(diag.get('seat0'))})")
            if should_warn_frozen_counter(frz_pass, m_state):
                dbg.warn("Pipeline",
                         f"pass_cnt frozen {frz_pass:.0f}s while PLAYING "
                         f"(val={self._pass_last_val}, ptr={fmt_ptr(diag.get('pass_ptr'))}) — STALE?")
            if should_warn_frozen_counter(frz_shot, m_state):
                dbg.warn("Pipeline",
                         f"shot_cnt frozen {frz_shot:.0f}s while PLAYING "
                         f"(val={self._shot_last_val}, ptr={fmt_ptr(diag.get('shot_ptr'))}) — STALE?")

            n_p = len(players) if players else 0
            dbg.event("HB",
                      st=m_state,
                      t=(round(float(total_t), 1) if total_t is not None else None),
                      clk=("HOOK" if clk_hook else "FB"),
                      poss=(poss if poss else "-"),
                      cap=fmt_ptr(cap),
                      ball=("OK" if ball else "NONE"),
                      nP=n_p,
                      **{"pass": pass_cnt, "shot": shot_cnt},
                      pPtr=fmt_ptr(diag.get("pass_ptr")), pCnt=diag.get("pass_cnt"),
                      sPtr=fmt_ptr(diag.get("shot_ptr")), sCnt=diag.get("shot_cnt"),
                      seat0=fmt_ptr(diag.get("seat0")),
                      stateRaw=diag.get("state_raw"),
                      ghCap=("Y" if gh.get("captured") else "N"),
                      ghRcx=fmt_ptr(gh.get("rcx")),
                      ghH=gh.get("home"), ghA=gh.get("away"),
                      gates=(f"loop:{gc['loop']} bp:{gc['ball_players']} "
                             f"geo:{gc['geometry']} np:{gc['not_playing']} "
                             f"pTrig:{gc['pass_trig']} sTrig:{gc['shot_trig']}"),
                      frz=(f"poss:{frz_poss:.0f} play:{frz_players:.0f} "
                           f"pass:{frz_pass:.0f} shot:{frz_shot:.0f}"))
            # reset counter‌technical note windowtechnical note Heartbeat
            gc["loop"] = 0
            gc["ball_players"] = 0
            gc["geometry"] = 0
            gc["not_playing"] = 0
            gc["pass_trig"] = 0
            gc["shot_trig"] = 0
        except Exception:
            pass

    def worker_loop(self):
        while self.is_monitoring:
            time.sleep(self.POLL_INTERVAL)
            try:
                # agetechnical note technical note Poll (wall — only performance)
                now_wall = time.time()
                if self._last_wall is not None:
                    dt_ms = (now_wall - self._last_wall) * 1000.0
                    self._poll_ema = (self._poll_ema * 0.9 + dt_ms * 0.1) if self._poll_ema else dt_ms
                self._last_wall = now_wall

                # request reset (button user) — in technical note technical note in Worker run technical note‌technical noteandtechnical note
                if self._reset_requested:
                    self._reset_requested = False
                    self._perform_reset()
                    continue

                # ---------- 1. Read Game State ----------
                m_state = self.engine.read_match_state()

                # ---------- 2. Read Game Clock (source andtechnical note time) ----------
                total_t, g_min, g_sec = self.engine.read_game_clock()

                # ---------- 2.0 technical noteortechnical note process (versiontechnical note 10technical note7) ----------
                # read failed technical noteandtechnical note ⇒ process technical note/technical note technical note connection automatic
                # technical note from ENGINE_DEAD_STREAK_LIMIT technical note (~3 second) technical note and retry technical note‌technical note.
                if self.engine.link_alive():
                    self._engine_dead_streak = 0
                else:
                    self._engine_dead_streak += 1

                # ---------- 1.1 cycletechnical note capture possession (versiontechnical note 10technical note18) ----------
                # connectiontechnical note «andtechnical note withtechnical note»: untiltechnical note-technical note technical note technical note‌technical note with firsttechnical note
                # PLAYING cycletechnical note technical note address technical notefrom technical note‌technical noteandtechnical note (hook → confirmation value 2
                # → technical note hook). if capture/hook from before active istechnical note technical note
                # technical note‌technical note (technical note‌withtechnical note technical note).
                if (m_state == "PLAYING"
                        and not self._poss_first_playing_seen
                        and self.engine.poss_hooker.captured_address is None
                        and not self.engine.poss_hooker.is_hooked):
                    self._poss_first_playing_seen = True
                    self._possession_begin_capture_cycle("first-playing")

                # ---------- 2.05 start technical note new (versiontechnical note 10technical note7) ----------
                # «untiltechnical note technical note technical note and after start to rise technical note» = start technical note new
                # (technical note withtechnical note beforetechnical note technical note technical note withtechnical note technical note technical note) ⇒ technical noteandtechnical notefromtechnical note fast hook‌technical note
                self._timer_rebirth_tick(total_t, now_wall)

                # ---------- 2.05-technical note v10.28 — technical note technical notefrom/technical note before from technical noteagetechnical note‌technical note ----------
                # (technical noteandtechnical note v1.3 from versiontechnical note 2017 — technical note withtechnical note technical note «chart in minutetechnical note
                # target (43/85) display data technical note only technical note from match end technical note»):
                # beforetechnical note technical note technical notefrom (technical note decrease time / Watchdog withtechnical note new /
                # confirmation HT and ET) after from technical note‌technical note ball/players/geometry and technical note
                # PLAYING run technical note‌technical note if technical note‌technical note data technical note Worker technical note technical note‌technical note
                # (technical note players=None in connection andtechnical note withtechnical note)technical note half_number for
                # always 1 technical note‌technical note and display minutetechnical note target technical note second (h2/et) never
                # technical notein technical note‌technical note — technical note‌technical note Errortechnical note. technical note:
                #   1) technical noteortechnical note‌technical note technical note (seen_max / max_half2) technical note‌technical note to‌technical noteandtechnical note
                #      technical note‌technical noteandtechnical note (independent from technical note‌technical note data)technical note
                #   2) technical note decrease time technical note‌technical note technical noteandtechnical note technical note‌technical noteandtechnical note (technical note when datatechnical note
                #      ball/player technical note is — technical note technical note only in PLAYING)technical note
                #   3) Watchdog withtechnical note new and confirmation HT/ET with same technical note beforetechnical note
                #      «only in PLAYING» technical note technical note‌technical noteandtechnical note (technical note user technical note technical note).
                # result: technical note _snapshot_tick value half_number always from
                # source andtechnical note fresh is — technical note when datatechnical note pitch technical note is.
                if total_t is not None:
                    if total_t > self._match_seen_max_t:
                        self._match_seen_max_t = total_t
                    # versiontechnical note 10technical note7: technical note game clocktechnical note technical note second — for detection extra time
                    # (second half + technical note > 90 minute ⇒ image Extra_Match_Moment)
                    if (self.half_number >= 2
                            and float(total_t) > self._tv_max_half2_t):
                        self._tv_max_half2_t = float(total_t)
                    # (v10.28 — technical note‌technical note decrease time from after from technical note‌technical note data to
                    #  technical note‌technical note technical note technical note until technical note technical notefrom technical note technical note‌technical note technical noteagetechnical note technical note
                    #  technical note technical note technical note only technical note resume PLAYING)
                    _prev_t_core = self.runtime.get_core()["current_match_time"]
                    if (self.runtime.connected
                            and should_flag_time_drop(
                                _prev_t_core, total_t,
                                self.config.MATCH_RESTART_DELTA)):
                        self._flag_time_drop(_prev_t_core, total_t)
                if m_state == "PLAYING" and total_t is not None:
                    # ---------- 7.4 Watchdog withtechnical note new (version 10technical note3) ----------
                    # «technical note technical note untiltechnical note» in technical noteortechnical note PLAYING technical note technical noteandtechnical note start Match new
                    # is — independent from technical note decrease time. if matchtechnical note current andtechnical note technical noteand
                    # technical note withtechnical note (technical note from windowtechnical note start + technical noteuntil) and technical note PLAYING with
                    # untiltechnical note ≈ technical note technical note matchtechnical note beforetechnical note technical note technical note is:
                    #   90:xx → 0:00 = withtechnical note new   |   6:xx → 0:00 = withtechnical note new
                    #   (45:xx → 45:00 = start second half — to watchdog technical note‌technical noteandtechnical note
                    #    because 2700 from windowtechnical note NEW_GAME_MAX_START outside is)
                    # match endtechnical note first technical noteandtechnical note (90:00 → STOP) never technical note technical note‌technical note
                    # reset only with «PLAYING + untiltechnical note ≈ technical note» run technical note‌technical noteandtechnical note.
                    if is_new_match_watchdog(self._match_seen_max_t, total_t,
                                             self.config.NEW_GAME_MAX_START,
                                             self.config.MATCH_RESTART_DELTA):
                        clog(f"[MatchLifecycle] NEW_MATCH (watchdog): PLAYING + "
                              f"untiltext {_fmt_clock(total_t)} currentlytext text matchtext current until "
                              f"{_fmt_clock(self._match_seen_max_t)} text text textandtext — "
                              "reset complete matchtext beforetext (chart/textandtextdatatext/text/counter‌text)")
                        _d = getattr(self, "dbg", None)
                        if _d:
                            _d.event("NEW_MATCH_WATCHDOG", t=round(float(total_t), 1),
                                     seen_max=round(float(self._match_seen_max_t), 1),
                                     path="watchdog")
                        self._perform_reset(momentum_start_t=total_t)
                        continue

                    # ---------- 7.5 technical note‌technical note technical note from decrease time (version 10technical note3 — State Machine) ----------
                    # only technical note resume PLAYING inwithtechnical note decrease technical note time technical note technical note‌technical note.
                    # technical note with classify_resume_after_drop (technical noteandtechnical note technical note 7technical note6) technical note technical note‌technical noteandtechnical note:
                    #   1) NEW_MATCH: untiltechnical note ≈ technical note — technical noteandtechnical note‌technical note technical note technical note technical note HT
                    #      (90:xx → 0:00 and 6:xx → 0:00 never HT is nottechnical note)
                    #   2) HT: only with rule technical note —
                    #      half == 1 AND prev_end >= 45*60 AND current technical noteandtechnical note 45:00
                    #      (if previous_time < 45:00 withtechnical note technical note with technical note timetechnical note HT technical notemenutechnical note)
                    #   3) KEPT: technical note technical note‌technical note (match end/technical note technical note) → chart technical note technical note‌technical noteandtechnical note
                    if self._ht_pending:
                        _verdict = classify_resume_after_drop(
                            self._ht_prev_end_t, total_t, self.half_number,
                            ht_hard_min=self.config.HT_HARD_MIN_FIRST_HALF,
                            ht_resume_lower_slack=self.config.HT_RESUME_LOWER_SLACK,
                            ht_resume_tolerance=self.config.HT_RESUME_TOLERANCE,
                            new_game_max_start=self.config.NEW_GAME_MAX_START,
                            et_reset_tolerance=getattr(self.config, "ET_RESET_TOLERANCE",
                                                       720.0),
                        )
                        if _verdict == "HT":
                            # HT real: Half 1 End → HT Gap → Half 2 Start (from 45:00)
                            self._ht_pending = False
                            self.half_number = 2
                            self._match_phase = MatchPhase.HALF_2
                            self.momentum.set_phase_label(MatchPhase.HALF_2.value)
                            self.momentum.set_half_break(self.config.HT_GAP_DISPLAY_SECONDS, total_t)
                            self._tv_dirty = True           # versiontechnical note 10technical note12 — render immediate gap HT technical noteandtechnical note technical note TV
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_HT", half1_end=round(float(self._ht_prev_end_t), 1),
                                         half2_start=round(float(total_t), 1))
                            clog(f"[MatchLifecycle] HT confirmation text: first half until "
                                  f"{_fmt_clock(self._ht_prev_end_t)} withtext text (≥ 45:00) — "
                                  f"second half from {_fmt_clock(total_t)}text gap HT intext text")
                            self._shot_debug_push("HALF_TIME_BREAK", team="--",
                                                  half1_end=self._ht_prev_end_t,
                                                  half2_start=total_t,
                                                  note=f"chart text text — gap HT ({int(self.config.HT_GAP_DISPLAY_SECONDS / 60)} minute) intext text sampling from firsttext secondtext second half from text text text‌textandtext (version 5)")
                            self._ui_post(lambda: self.lbl_status.config(
                                text="andtext: second half — chart text text (gap HT) 🟢", fg="#2ecc71"))
                        elif _verdict in ("ET1", "ET2"):
                            # --- versiontechnical note 10technical note15 — start extra time (technical note technical note/technical note technical note technical noteandtechnical note reset):
                            # reset untiltechnical note from withtechnical note 90/105 technical noteandtechnical note 90/105 + Playing + untiltechnical note technical note
                            _et_phase = MatchPhase.ET1 if _verdict == "ET1" else MatchPhase.ET2
                            _et_bound = 90.0 if _verdict == "ET1" else 105.0
                            _et_name = ("text first extra time" if _verdict == "ET1"
                                        else "text second extra time")
                            self._ht_pending = False
                            self.half_number = 3 if _verdict == "ET1" else 4
                            self._match_phase = _et_phase
                            self.momentum.set_phase_label(_et_phase.value)
                            self.momentum.set_half_break(
                                self.config.HT_GAP_DISPLAY_SECONDS, total_t)
                            self._tv_dirty = True
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_ET", kind=_verdict,
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         et_start=round(float(total_t), 1))
                            clog(f"[MatchLifecycle] {_verdict} confirmation text (text "
                                 f"{'text' if _verdict == 'ET1' else 'text'}): untiltext from "
                                 f"{_fmt_clock(self._ht_prev_end_t)} (withtext {_et_bound:.0f}:00) "
                                 f"textandtext {_fmt_clock(total_t)} reset text and withtext Playing with "
                                 f"untiltext currently text — start {_et_name}text gap displaytext intext text")
                            self._shot_debug_push(
                                f"{_verdict}_BREAK", team="--",
                                prev_end=self._ht_prev_end_t,
                                et_start=total_t,
                                note=(f"reset untiltext textandtext {_et_bound:.0f}:00 from withtext text + "
                                      f"Playing + untiltext text — start {_et_name}"))
                            self._ui_post(lambda v=_verdict: self.lbl_status.config(
                                text=("andtext: extra time — text first 🟢" if v == "ET1"
                                      else "andtext: extra time — text second 🟢"),
                                fg="#2ecc71"))
                        elif _verdict == "NEW_MATCH":
                            # untiltechnical note from technical note start technical note → withtechnical note new (technical note reset automatic technical notefrom)
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("NEW_MATCH_VERDICT", t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         path="time_drop")
                            clog(f"[MatchLifecycle] NEW_MATCH: PLAYING + untiltext "
                                  f"{_fmt_clock(total_t)} (withtext beforetext until "
                                  f"{_fmt_clock(self._ht_prev_end_t)}) — reset complete matchtext beforetext")
                            self._perform_reset(momentum_start_t=total_t)
                            continue
                        else:
                            # technical note HT and technical note withtechnical note new (technical note technical note technical note/match end) → technical note chart
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_KEPT", resume_t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         note="chart text text (match end/withtext without reset)")
                            if self.half_number == 2:
                                self._match_phase = MatchPhase.FULL_TIME
                                self.momentum.set_phase_label(MatchPhase.FULL_TIME.value)
                            elif self._match_phase == MatchPhase.HALFTIME:
                                self._match_phase = MatchPhase.HALF_1
                                self.momentum.set_phase_label(MatchPhase.HALF_1.value)
                            # (technical notefromtechnical note ET1/ET2 in technical note KEPT technical note technical note‌technical noteandtechnical note — versiontechnical note 10technical note15)
                            # version 5: technical noteandtechnical note technical note — sampling never technical notemust for technical note
                            # match technical note if technical note technical note latest sampletechnical note technical note withtechnical note
                            # with gap displaytechnical note technical noteandtechnical note from technical note technical note technical note‌technical noteandtechnical note
                            try:
                                self.momentum.resync_clock(total_t)
                            except Exception:
                                pass
                            self._shot_debug_push("TIME_DROP_KEPT", team="--",
                                                  prev_end=self._ht_prev_end_t,
                                                  resume_t=total_t,
                                                  note="chart text text (match end/withtext without reset) — sampling text active text (version 5)")

                # ---------- 2.06 technical noteagetechnical note‌technical note chart TV (versiontechnical note 10technical note11) ----------
                # technical note in «minutetechnical note target − 1»technical note display in «minutetechnical note target» and detection
                # match end (>90′/>120′ stop ≥12s) — must before from technical note‌technical note
                # early-continue run technical noteandtechnical note until in STOP/Pause technical note live technical note.
                self._snapshot_tick(total_t, m_state, now_wall)

                # ---------- 2.06-technical note v2.0.5 — crest banner + ball-link ----------
                # * technical note technical note team‌technical note (minutetechnical note firsttechnical note 5 second) — technical note technical note
                #   linetechnical note data + path displaytechnical note technical note technical noteandtechnical note technical note charttechnical note.
                # * technical note technical noteandtechnical note‌technical note hooktechnical note ball (~2 second) — if tool technical note
                #   (technical noteandtechnical note GLT / crash-recovery) hooktechnical note shared technical note withtechnical noteandtechnical note technical note
                #   withtechnical note automatic re-adopt/reinstall technical note‌technical noteandtechnical note.
                try:
                    self._crest_banner_tick(total_t, m_state)
                except Exception as _e:
                    try:
                        print(f"[CREST BANNER] tick error: "
                              f"{type(_e).__name__}: {_e}", flush=True)
                    except Exception:
                        pass
                if now_wall - self._ball_link_last_check >= 2.0:
                    self._ball_link_last_check = now_wall
                    try:
                        self._ball_link_verify(m_state)
                    except Exception:
                        pass

                # ---------- 2.1 Goal Hook Poll (version 10) — before from technical note technical note‌technical note ----------
                # countertechnical note technical note in memory to ball/players/technical note technical note andtechnical note‌technical note technical note
                # Poll must technical note in menu/Replay/technical note technical note resume technical note withtechnical note.
                # (in version 9 Poll technical note technical noteand early-continue technical noteandtechnical note and with technical note datatechnical note pitch
                #  completetechnical note technical notestop technical note‌technical note — technical note A technical note in technical notein version 10)
                self._poll_goal_hook(
                    gh_pick_poll_time(total_t,
                                      self.runtime.get_core().get("current_match_time"))
                )

                # ---------- 3-6. Possession / Ball / Players / Counters ----------
                poss = self.engine.read_possession()
                ball = self.engine.read_ball()
                players = self.engine.read_players()
                pass_cnt = self.engine.read_pass_counter()
                shot_cnt = self.engine.read_shot_counter()

                # v2.0.6 — ball-feed freshness bookkeeping (evidence line for
                # 'charts visible but empty': a STALE feed means the shared
                # hook's data buffer is not being written anymore)
                try:
                    if ball is not None and ball != self._ball_feed_last:
                        self._ball_feed_last = ball
                        self._ball_feed_change_t = now_wall
                except Exception:
                    pass

                # ---------- 2.15 versiontechnical note 10technical note27 — red card (countertechnical note pointertechnical note) ----------
                # technical note technical note: to ball/technical note andtechnical note is nottechnical note technical note for «assignment team»
                # to technical note players technical note frame technical noteortechnical note technical note (technical note z≈40).
                # technical note in STOP/technical note card resume technical note (player‌technical note technical noteandtechnical note technical note‌technical noteandtechnical note).
                try:
                    self._poll_red_card(
                        gh_pick_poll_time(total_t,
                                          self.runtime.get_core().get("current_match_time")),
                        players)
                except Exception as _rc_ex:
                    clog(f"[RedCardPoll] poll error: "
                         f"{type(_rc_ex).__name__}: {_rc_ex}")

                # ---------- 6.0 technical note line technical noteandtechnical note data (version 10technical note4) ----------
                # Heartbeat + Watchdog possession «before from technical note technical note‌technical note» run technical note‌technical noteandtechnical note
                # until technical note when technical note‌technical note technical note technical note technical note‌technical note log technical note technical note codetechnical note layer
                # technical note is (playerstechnical note possessiontechnical note counter‌technical note) and possession technical noteandtechnical note technical noteandtechnical note.
                self._pipeline_health_tick(m_state, total_t, poss, ball, players,
                                           pass_cnt, shot_cnt, now_wall,
                                           clk_hook=(g_min is not None))

                if not ball or not players:
                    self._gate_counts["ball_players"] += 1
                    # v2.0.7 — visible evidence for "charts visible but
                    # empty": this gate silently skips the WHOLE event
                    # pipeline (shots/passes/momentum history) while the
                    # goal/time/red-card polls (before the gate) keep
                    # working — exactly the field symptom. Say WHICH layer
                    # is dead and for how long, every 5 s.
                    if now_wall - getattr(self, "_gate_diag_last", 0.0) >= 5.0:
                        if not getattr(self, "_gate_blocked_since", 0.0):
                            self._gate_blocked_since = now_wall
                        self._gate_diag_last = now_wall
                        _ball_txt = ("None" if ball is None else
                                     f"({ball[0]:.1f},{ball[1]:.1f},{ball[2]:.1f})"
                                     if len(ball) >= 3 else repr(ball))
                        print(f"[DATA GATE] BLOCKED for "
                              f"{now_wall - self._gate_blocked_since:.0f}s — "
                              f"ball={_ball_txt} "
                              f"(buffer=0x{int(self.engine.ball_data_addr or 0):X}) "
                              f"players={len(players) if players else 0}/22 "
                              f"poss={poss} m_state={m_state} "
                              f"skipped_ticks="
                              f"{self._gate_counts['ball_players']}",
                              flush=True)
                    continue
                if getattr(self, "_gate_blocked_since", 0.0):
                    print(f"[DATA GATE] RECOVERED after "
                          f"{now_wall - self._gate_blocked_since:.0f}s — "
                          f"ball={tuple(round(v, 1) for v in ball)} "
                          f"players={len(players)} (event pipeline resumes)",
                          flush=True)
                    self._gate_blocked_since = 0.0
                    self._gate_diag_last = 0.0

                self._ui_post(self.update_field_geometry, players)
                if not self.geometry_ready:
                    self._gate_counts["geometry"] += 1
                    continue

                # (v10.28 — technical note‌technical note decrease time to technical note 2.05-technical note technical note technical note — before from
                #  technical note‌technical note datatechnical note until technical note technical notefrom technical note technical note‌technical note technical noteagetechnical note technical note)

                # ---------- 7. Build SnapshotFrame ----------
                frame = SnapshotFrame(
                    timestamp=now_wall,
                    match_time=total_t,
                    ball=ball,
                    players=players,
                    possession=poss,
                    shot_counter=shot_cnt,
                    pass_counter=pass_cnt
                )
                self.frame_buffer.append(frame)
                self._frame_seq += 1   # versiontechnical note 10technical note14 — countertechnical note technical note frame
                self.runtime.update_core(m_state, total_t, g_min, g_sec, poss, self._poll_ema)
                self._ui_post(self.update_time_status, m_state, g_min, g_sec, total_t)

                # ---------- 7.1 Goal Hook — to technical note 2technical note1 technical note technical note (version 10) ----------
                # Poll technical note technical note before from technical note‌technical note ball/players/geometry run technical note‌technical noteandtechnical note
                # technical note path register technical note technical note technical note early-continuetechnical note hidden is not.

                # ---------- 7.2 technical note‌technical note technical noteandfrom shot technical note in STOP/Pause (version 3) ----------
                # if shot currently technical note‌technical note istechnical note technical note technical note (with burst technical note ~15ms)
                # before from technical note PLAYING run technical note‌technical noteandtechnical note until technical noteandfrom in stop‌technical note technical noteanduntiltechnical note
                # (technical noteandtechnical note ball/technical note technical note) technical note technical noteandtechnical note timeout technical noteandtechnical note technical noteandtechnical note technical noteandtechnical note technical note‌technical note.
                # versiontechnical note 10technical note14 — technical notefromtechnical note technical note technical note technical note in stop‌technical note live technical note‌technical note
                # (buffer in STOP technical note technical note technical note‌technical noteandtechnical note technical noteandtechnical note frame‌technical noteandtechnical note technical note technical note‌technical note)
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                shot_data_early = self._step_shot_tracking(burst=6)
                if shot_data_early:
                    self._register_shot_data(shot_data_early)

                # Pause / Replay / Stop → time withtechnical note technical note istechnical note Momentum technical note technical notemust decay technical note
                if m_state != "PLAYING":
                    self.pass_engine.abort()
                    self._gate_counts["not_playing"] += 1
                    continue

                # (v10.28 — Watchdog withtechnical note new (7.4) and technical note‌technical note technical note from decrease time
                #  (7.5) to technical note 2.05-technical note technical note technical note — before from _snapshot_tick and
                #  technical note‌technical note datatechnical note technical note only in PLAYING technical note technical note is)

                # ---------- 8.0 technical note Context possession (10technical note14 — «before from» technical note shot) ----------
                # order correct specification user:
                #   Read Possession → Read Shot Counter → Read Ball/Players
                #   → Determine valid possession context
                #   → Detect Shot Counter increment → Assign shot team → ...
                # technical note Context possession must «before from» check technical note shot valid technical noteandtechnical note until
                # never «current_possession=None/stale ⇒ technical note technical note» technical note technical note.
                prev_poss_ctx = self.current_possession   # versiontechnical note 10technical note14 — Context beforetechnical note
                if poss and self.current_possession is None:
                    # technical note technical note possession — technical notefrom chain without technical note technical noteandistechnical note
                    self.current_possession = poss
                    att_dir = self.team1_attack_dir if poss == "Home" else -self.team1_attack_dir
                    self.event_engine.handle_possession_change(
                        new_team=poss, match_time=total_t,
                        start_x_att=ball[0] * att_dir, timestamp=now_wall, ball_pos=ball
                    )
                    self.pass_counters[poss] = pass_cnt
                elif poss and poss != self.current_possession:
                    self.current_possession = poss
                    att_dir = self.team1_attack_dir if poss == "Home" else -self.team1_attack_dir
                    self.event_engine.handle_possession_change(
                        new_team=poss, match_time=total_t,
                        start_x_att=ball[0] * att_dir, timestamp=now_wall, ball_pos=ball
                    )
                    # technical note technical note baseline countertechnical note «pass» for team active new
                    self.pass_counters[poss] = pass_cnt

                active_team = self.current_possession

                # ---------- 8.1 Shot Counter Trigger (10technical note14 — technical note technical note) ----------
                # counter shot «global» is (technical note technical noteand team). baseline only technical note technical note is
                # and with change possession never withtechnical noteandtechnical note technical note‌technical noteandtechnical note (withtechnical note version 2).
                # versiontechnical note 10technical note14: technical note increment = 1 technical note in technical note ShotEngine — technical note technical note
                # technical note technical note‌technical noteandtechnical note team shot with fallback user technical note and in jumptechnical note «simultaneoustechnical note»
                # possessiontechnical note Context beforetechnical note technical note technical note‌technical noteandtechnical note (team incorrect technical notemenutechnical note).
                cnt_before_dbg = self.shot_counter_baseline
                new_baseline, trig_event = self._shot_trigger_decision(
                    self.shot_counter_baseline, shot_cnt
                )
                self.shot_counter_baseline = new_baseline
                if trig_event == "TRIGGER":
                    # --- technical note team shot (fallback specification user) ---
                    possession_for_shot = self.current_possession
                    if possession_for_shot is None and poss is not None:
                        possession_for_shot = poss
                    # jumptechnical note simultaneous possession and counter ⇒ Context «beforetechnical note» technical note is
                    # (after from shot technical noteandtechnical note possession technical noteandtechnical note technical note‌technical noteandtechnical note if same moment in
                    #  data technical note technical note shot technical notemust to team incorrect ratio data technical noteandtechnical note)
                    flip_same_tick = (prev_poss_ctx is not None
                                      and possession_for_shot is not None
                                      and prev_poss_ctx != possession_for_shot)
                    primary_team = prev_poss_ctx if flip_same_tick else possession_for_shot
                    team_candidates: List[str] = []
                    for _t in (primary_team, prev_poss_ctx, possession_for_shot, poss):
                        if _t and _t not in team_candidates:
                            team_candidates.append(_t)
                    self.shot_engine.stats["counter_increments"] += 1
                    self._gate_counts["shot_trig"] += 1
                    self.shot_engine.push_trigger(
                        counter_value=shot_cnt, team=primary_team,
                        alternates=team_candidates, match_time=total_t,
                        wall_now=now_wall, frame_seq=self._frame_seq,
                        team1_attack_dir=self.team1_attack_dir
                    )
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_TRIGGER", before=cnt_before_dbg, after=shot_cnt,
                                 t=(round(float(total_t), 1) if total_t is not None else None),
                                 poss=primary_team)
                    self._shot_debug_push("COUNTER_INCREMENT", team=primary_team or "--",
                                          counter_before=cnt_before_dbg, counter_after=shot_cnt,
                                          trigger_match_time=total_t,
                                          shot_engine_state=self.shot_engine.state)
                    self._shot_debug_push("TRIGGER_TEAM", team=primary_team or "--",
                                          candidates=",".join(team_candidates) or "Home,Away",
                                          flip_same_tick=flip_same_tick,
                                          trigger_match_time=total_t,
                                          note="team shot from Context possession (with fallback) text text")
                elif trig_event == "RESET":
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_COUNTER_RESET", before=cnt_before_dbg, after=shot_cnt,
                                 note="counter shot reset text (second half/restart)")
                    self._shot_debug_push("COUNTER_RESET", team="--",
                                          counter_before=cnt_before_dbg,
                                          counter_after=shot_cnt,
                                          trigger_match_time=total_t,
                                          note="counter shot reset text (second half/restart)")
                    # versiontechnical note 10technical note14 — technical note technical note beforetechnical note technical note‌technical note only with technical note technical note technical note‌technical noteandtechnical note
                    self.shot_engine.on_counter_reset(reason="shot_counter_reset")
                elif trig_event == "BASELINE":
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_BASELINE", val=shot_cnt)

                # ---------- 9. Update Pass Engine ----------
                if active_team:
                    if self.pass_counters[active_team] is None:
                        self.pass_counters[active_team] = pass_cnt
                    elif pass_cnt is not None and pass_cnt > self.pass_counters[active_team]:
                        self.pass_counters[active_team] = pass_cnt
                        # Counter only Trigger is — PassDetector real start technical note‌technical noteandtechnical note
                        self._gate_counts["pass_trig"] += 1
                        self.pass_engine.on_counter_increment(ball, now_wall, total_t, active_team, players)

                pass_data = self.pass_engine.generate_event(
                    ball, total_t, players, self.team1_attack_dir,
                    possession_provider=self.engine.read_possession
                )

                # ---------- 10. Shot Engine — technical note technical note + technical note‌technical note (10technical note14) ----------
                # technical notefromtechnical note technical note technical note technical note shot (1 increment counter = 1 technical note)technical note
                # independent from technical note original (technical note‌technical note) and without technical note‌technical note frame‌technical note.
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                # technical note‌technical note technical noteandfrom with burst technical note (~15ms × 6 ≈ technical note technical note tool independent)
                shot_data = self._step_shot_tracking(burst=6)
                if shot_data:
                    # versiontechnical note 10technical note14 — technical note withtechnical note technical note‌technical note register: output technical note technical note path
                    # technical note must technical note register technical noteandtechnical note (beforetechnical note only path 7.2 register technical note‌technical note)
                    self._register_shot_data(shot_data)

                # ---------- 11-12. Process Event Engine + Register new Events ----------
                if pass_data:
                    self.event_engine.register_pass_event(pass_data)
                    self._ui_post(self.update_pass_card, pass_data)
                self.event_engine.process_frame(self.frame_buffer, frame, self.team1_attack_dir)

                # ---------- 13-15. Events→Impacts (via Bus) + Momentum with MATCH TIME ----------
                self.momentum.update(total_t)

                # ---------- 16. Schedule UI refresh ----------
                # (Event Timeline — technical note technical note new technical notedistance)
                if len(self.event_engine.events) > self._last_ev_count:
                    new_evs = self.event_engine.events[self._last_ev_count:]
                    self._last_ev_count = len(self.event_engine.events)
                    self._ui_post(self.update_ui_events, new_evs)

                # (Possession Sequences — Live Update from _graph_loop technical note technical note‌technical noteandtechnical note
                #  technical note only technical note for technical notewithtechnical note to‌technical noteandtechnical note technical note‌technical note)
                if len(self.momentum.impacts) > self._last_imp_count:
                    self._last_imp_count = len(self.momentum.impacts)

                self._ui_post(self.update_possession_cards)
                self._ui_post(self._update_goal_hook_label)

            except Exception as ex:
                clog(f"[Worker Error] Unhandled exception: {ex}")
                # version 10technical note4: Errortechnical note technical noteandtechnical note Worker in log file technical note register technical note‌technical noteandtechnical note
                # (if technical note technical note technical note technical notecodetechnical note only technical note‌technical note technical note before from Error Poll technical note‌technical noteandtechnical note register technical note‌technical note)
                _d = getattr(self, "dbg", None)
                if _d:
                    try:
                        _d.error("WORKER-ERROR",
                                 f"{type(ex).__name__}: {ex} | " +
                                 traceback.format_exc(limit=4).replace("\n", " | "))
                    except Exception:
                        pass

    def _poll_red_card(self, match_t: float,
                       players: Optional[List[Dict]] = None):
        """
        versiontext 10text27 — read countertext red card (pointer 3 leveltext — without hook) and
        assignment team with text player text:
            [base+0x36F3F88] +0x350 +0x4E0 → u8
        text «increment» = 1 red card. teamtext card in momenttext textandtext textandtext is nottext
        code text second player‌text text text text text‌text — player text in
        z≈40 (outside line lengthtext) text‌text text text teamtext textandtext card for same
        team register text‌textandtext. time text = momenttext textandtext (issued_t — frozentext)text
        text momenttext detection. text‌text beforetext (seat) from text text text‌textandtext.
        """
        d = self._rc_diag
        try:
            raw = self.engine.read_red_card_counter()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[RedCardPoll] Errortext read counter: "
                      f"{type(ex).__name__}: {ex}")
            return
        if raw is None:
            d["n_none"] += 1
            return
        d["n_ok"] += 1
        st = self._rc_state

        # --- 1) BASELINE — firsttechnical note read valid ---
        if st["baseline"] is None:
            st["baseline"] = int(raw)
            clog(f"[RedCardPoll] BASELINE countertext red card = {raw} "
                  "(firsttext read valid — card‌text before from connection withtextfromtext "
                  "text‌textandtext)")
            return

        # --- 2) increment → card new (technical note) in technical note assignment team ---
        if raw > st["baseline"]:
            n_new = int(raw) - st["baseline"]
            if n_new > RC_MAX_JUMP:
                clog(f"[RedCardPoll] ⚠ jump text counter "
                      f"({st['baseline']} → {raw}) — rebaseline without register card")
                st["baseline"] = int(raw)
                return
            try:
                with self.momentum._lock:
                    _disp = float(match_t) + float(self.momentum.display_offset)
            except Exception:
                _disp = float(match_t)
            _half = int(self.half_number)
            for _ in range(n_new):
                st["pending"].append({
                    "issued_t": float(match_t),
                    "issued_disp": _disp,
                    "issued_half": _half,
                    "wall": time.time(),
                    "exclude": set(st["exiles"]),
                    "tried": set(),
                })
            st["baseline"] = int(raw)
            d["n_cards"] += n_new
            clog(f"[RedCardPoll] 🟥 red card textin text "
                  f"({int(raw) - n_new} → {raw}) in {_fmt_clock(match_t)} — "
                  f"in text text team (text z≈{RC_Z_TARGET:.0f})")

        # --- 3) decrease → technical note (baseline technical note)technical note reset only in windowtechnical note withtechnical note new ---
        elif raw < st["baseline"]:
            _mt = None
            try:
                _mt = float(match_t) if match_t is not None else None
            except (TypeError, ValueError):
                _mt = None
            if _mt is not None and _mt <= float(self.config.NEW_GAME_MAX_START):
                clog(f"[RedCardPoll] RESET countertext red card: "
                      f"{st['baseline']} → {raw} (withtext new)")
                st["baseline"] = int(raw)
                st["pending"].clear()
                st["exiles"].clear()
            else:
                clog(f"[RedCardPoll] ⏳ decrease text counter "
                      f"({st['baseline']} → {raw}) text text text")

        # --- 4) technical note player‌technical note: assignment team + to‌technical noteandtechnical note technical note ---
        now_exiles: Dict[int, Dict] = {}
        if players:
            for p in players:
                try:
                    _z = float(p.get("z", float("nan")))
                    _seat = int(p.get("seat", -1))
                except (TypeError, ValueError):
                    continue
                if abs(_z - RC_Z_TARGET) <= RC_Z_TOL:
                    now_exiles[_seat] = p

        for pd in list(st["pending"]):
            cands = [p for seat, p in sorted(now_exiles.items())
                     if seat not in pd["exclude"]
                     and seat not in pd["tried"]]
            if not cands:
                continue
            p = cands[0]
            try:
                _seat = int(p.get("seat", -1))
            except (TypeError, ValueError):
                _seat = -1
            pd["tried"].add(_seat)
            team = str(p.get("team", "Home"))
            if team not in ("Home", "Away"):
                team = "Home"
            self._register_hook_red_card(team, pd, p)
            st["pending"].remove(pd)
            st["exiles"].add(_seat)
            d["n_attr"] += 1

        # technical note without cardtechnical note in technical note technical note register technical noteandtechnical note — cardtechnical note aftertechnical note technical note‌technical note
        # technical note from technical note technical note technical note‌technical note (technical note legacy again assignment technical note‌technical noteandtechnical note)
        st["exiles"].update(now_exiles.keys())

        # --- 5) technical note assignment (time withtechnical note) + limit wall technical noteandtechnical note technical note ---
        try:
            _mt_now = float(match_t) if match_t is not None else None
        except (TypeError, ValueError):
            _mt_now = None
        _now_wall = time.time()
        for pd in list(st["pending"]):
            _expired = False
            if (_mt_now is not None
                    and (_mt_now - pd["issued_t"]) > RC_WATCH_WINDOW_S):
                _expired = True
            if (_now_wall - pd["wall"]) > RC_WATCH_WALL_CAP_S:
                _expired = True
            if _expired:
                st["pending"].remove(pd)
                d["n_timeout"] += 1
                clog(f"[RedCardPoll] ⌛ text text team card (textintext in "
                      f"{_fmt_clock(pd['issued_t'])}) to end text — "
                      "text register text")

    def _register_hook_red_card(self, team: str, pd: Dict[str, Any],
                                player: Optional[Dict] = None):
        """
        versiontext 10text27 — register text red card textandtext chart (text text: line textandtext +
        icon card to‌text ball). time text = momenttext textandtext card (issued_t —
        frozentext text increment counter)text text momenttext detection team. without text
        textandtextandtext / Event Bus — only text (text versiontext 2017).
        """
        try:
            self.momentum.add_hook_red_card_marker(
                team,
                float(pd.get("issued_t", 0.0)),
                int(pd.get("issued_half", 1) or 1),
                disp_time=pd.get("issued_disp"),
            )
            self._tv_dirty = True
            try:
                _seat = int(player.get("seat")) if player else None
            except Exception:
                _seat = None
            clog(f"[RedCard→Graph] text red card {team} registered | "
                  f"textandtext={_fmt_clock(pd.get('issued_t', 0.0))} | "
                  f"detection from player seat={_seat} in z≈{RC_Z_TARGET:.0f} | "
                  f"text active={self.momentum.red_card_marker_count()}")
            self._shot_debug_push(
                "RED_CARD_REGISTERED", team=team,
                match_time=pd.get("issued_t", 0.0),
                half=int(pd.get("issued_half", 1) or 1),
                seat=_seat, z_target=RC_Z_TARGET,
                note="countertext pointertext + assignment z=40 (v10.27)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("RED_CARD_REGISTERED", team=team,
                         t=round(float(pd.get("issued_t", 0.0)), 1),
                         seat=_seat)
        except Exception as ex:
            clog(f"[RedCard] Errortext register text: {ex}")

    def _poll_goal_hook(self, match_t: float):
        """
        version 10 — read textand countertext text ([rcx+0x158] Home / [rcx+0x15C] Away)
        and register text increment to‌textandtext text textandtext Event Bus.

        text text with version‌text before text is (counter_event / Sticky
        First-Capture / limit jump MAX_GOAL_JUMP)text only layertext log
        [GoalHookPoll] text text until «text» path failure in Console text textandtext:
          - hook active is not / still capture text / Errortext read
          - change RAW counter‌text (withtext or below)
          - BASELINE / RESET / textandtext structure (rcx)
          - heartbeat andtext text 5 second
        textandtext to Replay: counter in text text jump text‌text only «increment» text is.
        connection shot ← text with MATCH TIME.
        """
        d = self._gh_diag
        try:
            st = self.engine.read_goal_counters()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[GoalHookPoll] Errortext read counter: {type(ex).__name__}: {ex}")
            return
        if not st:
            d["n_err"] += 1
            return

        prev_status = self._goal_hook_status
        events_before = prev_status.get("events", 0)
        self._goal_hook_status = {
            "hooked": bool(st.get("hooked")),
            "captured": bool(st.get("captured")),
            "secondary": bool(st.get("secondary")),
            "rcx": st.get("rcx"),
            "home": st.get("home"),
            "away": st.get("away"),
            "events": events_before
        }

        # ---------------------------------------------------------
        # [GoalHookPoll] — layertechnical note technical note‌technical note (version 10)
        # ---------------------------------------------------------
        if not st.get("hooked"):
            d["n_nohook"] += 1
            if not d["notified_no_hook"]:
                d["notified_no_hook"] = True
                clog("[GoalHookPoll] goal hook active is not — register text disabled "
                      "(resulttext install hook in Console above text check text)")
            return
        d["notified_no_hook"] = False

        if not st.get("captured"):
            d["n_wait"] += 1
            if d["last_captured"] is not False:
                clog("[GoalHookPoll] captured=False — in text firsttext write structure text "
                      "(slot text istext with firsttext to‌textandtext text text in textandtext withtext capture text‌textandtext)")
            d["last_captured"] = False
            return
        if d["last_captured"] is not True:
            clog(f"[GoalHookPoll] capture text text ✅ rcx={(st.get('rcx') or 0):#x} "
                  f"home={st.get('home')} away={st.get('away')}")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_CAPTURE", rcx=fmt_ptr(st.get("rcx")),
                         home=st.get("home"), away=st.get("away"),
                         t=(round(float(match_t), 1) if match_t is not None else None))
        d["last_captured"] = True
        d["n_ok"] += 1

        _rcx = st.get("rcx")
        if d["last_rcx"] is not None and _rcx != d["last_rcx"]:
            clog(f"[GoalHookPoll] ⚠ structure text textandtext text: rcx {d['last_rcx']:#x} → {(_rcx or 0):#x} "
                  f"(counter‌text from structure new textandtext text‌textandtext)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_RCX_CHANGED", old=fmt_ptr(d["last_rcx"]), new=fmt_ptr(_rcx),
                         note="structure text match in memory textto‌text text")
        d["last_rcx"] = _rcx

        _h, _a = st.get("home"), st.get("away")
        if _h != d["last_home"] or _a != d["last_away"]:
            clog(f"[GoalHookPoll] RAW Home: {d['last_home']} → {_h} | "
                  f"Away: {d['last_away']} → {_a} | t={_fmt_clock(match_t)}")
        d["last_home"], d["last_away"] = _h, _a

        # ---------------------------------------------------------
        # technical note (technical note unchanged — version 4/6/9)
        # ---------------------------------------------------------
        # ⚫ technical note original «technical note technical note register technical note‌technical noteandtechnical note» (version 10):
        #   poll() totaltechnical note technical note «home/away» technical noteandtechnical note technical note‌technical note technical note technical note
        #   st.get(team) with «Home/Away» technical note technical noteandtechnical note technical note‌technical note → always None →
        #   counter_event(None, None) → WAIT technical note → technical note technical note never register
        #   technical note‌technical note (from version 5 until 9!). technical note UI from st.get("home") technical note‌technical noteandtechnical note
        #   for technical note number technical noteandtechnical note technical note correct technical noteandtechnical note andtechnical note technical note always WAIT technical noteandtechnical note.
        #   technical note: st.get(team.lower())
        for team in ("Home", "Away"):
            new_v = st.get(team.lower())
            old_v = self.goal_counters[team]
            decision, n_goals = GoalHooker.counter_event(old_v, new_v)
            if decision == "BASELINE":
                # --- version 10technical note3: First-Capture Goal -------------------------
                # firsttechnical note Capture successful Goal Hook possible is «same momenttechnical note technical note first
                # match» withtechnical note (Capture in firsttechnical note run instruction technical note technical note technical note‌technical noteandtechnical note).
                # in technical note beforetechnical note technical note firsttechnical note read technical note BASELINE technical note‌technical note and technical note
                # first for always technical note technical note‌technical note. technical noteandtechnical note: if countertechnical note technical note team in
                # firsttechnical note read valid > 0 withtechnical note technical note «technical note technical note» from baseline
                # technical note start match is and same moment to‌technical noteandtechnical note technical note real register
                # technical note‌technical noteandtechnical note (technical note + Goal Event + technical note). technical note baseline internal
                # same value technical note‌technical noteandtechnical note and technical noteandtechnical note technical note Counter Tracking (1→2 = technical note
                # new) without technical noteandwithtechnical note register‌technical note resume technical note‌ortechnical note. technical note technical note only for
                # firsttechnical note Capture technical note team is and after from reset_capture (withtechnical note new)
                # again armed technical note‌technical noteandtechnical note.
                if self._gh_fc_pending.get(team):
                    self._gh_fc_pending[team] = False
                    self._register_first_hook_goal(team, new_v, match_t)
                self.goal_counters[team] = new_v
                if not d["baselined"].get(team):
                    d["baselined"][team] = True
                    clog(f"[GoalHookPoll] BASELINE {team}={new_v} "
                          "(firsttext read valid — text text text text‌textandtext)")
                self._shot_debug_push("GOAL_COUNTER_BASELINE", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="firsttext read valid countertext text")
            elif decision == "GOAL":
                self.goal_counters[team] = new_v
                clog(f"[GoalHook] change countertext text {team}: {old_v} → {new_v} "
                      f"({n_goals} text new) in {_fmt_clock(match_t)}")
                _d = getattr(self, "dbg", None)
                if _d:
                    _d.event("GOAL_COUNTER", team=team, old=old_v, new=new_v,
                             n=n_goals, decision=decision,
                             t=(round(float(match_t), 1) if match_t is not None else None))
                for _ in range(n_goals):
                    self._register_hook_goal(team, match_t)
            elif decision == "RESET":
                self.goal_counters[team] = new_v
                d["baselined"][team] = False
                clog(f"[GoalHookPoll] RESET countertext {team}: {old_v} → {new_v} "
                      "(withtext new / resync)")
                self._shot_debug_push("GOAL_COUNTER_RESET", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="countertext text reset text (withtext new)")

        # ---------------------------------------------------------
        # heartbeat andtechnical note — technical note 5 second
        # ---------------------------------------------------------
        now_wall = time.time()
        if gh_due_heartbeat(now_wall, d["last_hb"]):
            d["last_hb"] = now_wall
            clog(f"[GoalHookPoll] ❤ hooked=✓ captured=✓ rcx={(_rcx or 0):#x} "
                  f"H={_h} A={_a} | "
                  f"baseline=(H:{self.goal_counters['Home']}, A:{self.goal_counters['Away']}) | "
                  f"polls ok={d['n_ok']} wait={d['n_wait']} err={d['n_err']} nohook={d['n_nohook']}")

    def _register_hook_goal(self, team: str, match_t: float):
        """
        version 9 — register text text from change countertext hook:
          1) text direct textandtext chart (path independent from Event Bus) — first from text
          2) versiontext 10text12 — render immediate text TV with text dirty (text Live text text)text
          3) text "Goal ⚽" textandtext Event Bus → text delaytext textandtextandtext + text shottext
          4) textwithtext chain + log Console.
        """
        try:
            # 1) register deterministic Marker
            self.momentum.add_hook_goal_marker(
                team,
                match_t,
                self.half_number
            )

            clog(
                "[GoalHook→Graph] "
                f"marker appended | team={team} | "
                f"match_t={match_t:.3f} | "
                f"total_markers={self.momentum.hook_goal_marker_count()}"
            )

            # 2) versiontechnical note 10technical note12 — request render immediate technical note TV (without technical note Live)
            self._tv_dirty = True

        except Exception as ex:
            clog(f"[GoalHook] marker/render scheduling error: {ex}")
        try:
            ev = self.event_engine.register_goal_event(team, match_t, source="memory-hook")
            gh = dict(self._goal_hook_status)
            gh["events"] = gh.get("events", 0) + 1
            self._goal_hook_status = gh
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_REGISTERED", team=team,
                         t=(round(float(match_t), 1) if match_t is not None else None),
                         half=self.half_number,
                         goal_event_id=(ev.event_id if ev else "--"))
            self._shot_debug_push("GOAL_REGISTERED_HOOK", team=team,
                                  goal_event_id=ev.event_id,
                                  goal_match_time=match_t,
                                  half=self.half_number,
                                  chart_marker=True,
                                  linked_shot=(ev.related_event_ids[0] if ev.related_event_ids else "--"),
                                  source="memory-hook [rcx+0x158/0x15C]")
            clog(f"[GoalHook] text {team} in {_fmt_clock(match_t)} registered — "
                  f"text textandtext chart + text textandtextandtext (text active: "
                  f"{self.momentum.hook_goal_marker_count()})")
        except Exception as ex:
            clog(f"[Goal Register] {ex}")

    def _register_first_hook_goal(self, team: str, value: Optional[int], match_t: float) -> int:
        """
        version 10text3 — First-Capture Goal (untiltext independent and text).

        text: Goal Hook only when text‌textandtext RCX text Capture text text instruction
        countertext text text text‌withtext run text withtext textfortext firsttext run Hook
        possible is exactly momenttext «text first match» withtext. in text text Capture
        text text‌textandtext text text beforetext text text text BASELINE in text text‌text and
        text first from text text‌text.

        text text (only for firsttext Capture successful text team in text withtext):
            Goal Hook still Capture text
                ↓ firsttext read valid instruction Goal (RCX Capture text)
            value text Home/Away textandtext textandtext
                ↓
            value = 0  → text text only baseline firsttext (0,0)
            value = 1  → same moment text Goal real for same team register textandtext:
                          text text textandtext chart + Goal Event + Goal Momentum Pulse
            value > 1  → «text text» from baseline text check and register text‌textandtext
                          (with limit text MAX_GOAL_JUMP — text textandtext and text 0→1 is)
                ↓
            baseline internal = value
                ↓
            from text to after textandtext text Counter Tracking:
              1 → 2 = text text new    2 → 3 = text text new    ...
            (for text textand team independenttext text textandwithtext register‌text text text‌text because
             same increment 0→value only text‌withtext and in text untiltext register text‌textandtext)

        after from reset_capture() in withtext newtext text text again armed text‌textandtext
        (_gh_fc_pending in _perform_reset to True text‌text).

        output: count text‌text register‌text in text textandtext.
        """
        if value is None or value <= 0:
            # technical note technical noteand technical note (or read invalid) → technical note technical note register technical noteandtechnical note
            # Capture only baseline firsttechnical note is
            clog(f"[GoalHook] First-Capture {team}={value} — without text "
                  "Capture to‌textandtext baseline firsttext registered")
            return 0
        n = min(int(value), GoalHooker.MAX_GOAL_JUMP)
        clog(f"[GoalHook] First-Capture Goal {team}: 0 → {value} in {_fmt_clock(match_t)} — "
              f"text first match same momenttext Capture register text‌textandtext "
              f"(text textandtext chart + Goal Event + Goal Momentum Pulse)")
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("GOAL_FIRST_CAPTURE", team=team, value=value, registered=n,
                     t=(round(float(match_t), 1) if match_t is not None else None))
        for _ in range(n):
            self._register_hook_goal(team, match_t)
        if int(value) > GoalHooker.MAX_GOAL_JUMP:
            clog(f"[GoalHook] ⚠ value firsttext {team}={value} from limit text "
                  f"{GoalHooker.MAX_GOAL_JUMP} text — {n} text registered and "
                  f"{int(value) - n} text withtext‌text text text text (log text check text)")
        return n

    def _update_goal_hook_label(self):
        """text andtext goal hook textandtext textandtext pitch (only in change text text text‌textandtext)"""
        gh = self._goal_hook_status
        if not gh["hooked"]:
            txt = "Goal Hook: INACTIVE ⚠ "
            color = "#fca311"
        elif not gh["captured"]:
            txt = "Goal Hook: INSTALLED ⏳ (text write) "
            color = "#ffd166"
        else:
            txt = (f"Goal Hook: ACTIVE ✅ H:{gh['home'] if gh['home'] is not None else '-'}"
                   f" A:{gh['away'] if gh['away'] is not None else '-'} "
                   f"text‌text: {gh.get('events', 0)} ")
            color = "#00f5d4"
        if txt != self._goal_hook_label_txt:
            self._goal_hook_label_txt = txt
            self.lbl_goal_hook.config(text=txt, fg=color)


    def update_possession_cards(self):
        poss = self.runtime.get_core()["current_possession"]
        if poss == "Home":
            self.card_home.config(bg="#1a3828")
            self.lbl_home_team.config(bg="#1a3828")
            self.lbl_home_status.config(text=f"possession: text ⚽ ({self.team1_side_name})", fg="#00f5d4", bg="#1a3828")
            self.card_away.config(bg="#131a28")
            self.lbl_away_team.config(bg="#131a28")
            self.lbl_away_status.config(text="possession: text", fg="#94a3b8", bg="#131a28")
        elif poss == "Away":
            self.card_away.config(bg="#3d1d2b")
            self.lbl_away_team.config(bg="#3d1d2b")
            self.lbl_away_status.config(text=f"possession: text ⚽ ({self.team2_side_name})", fg="#f38ba8", bg="#3d1d2b")
            self.card_home.config(bg="#131a28")
            self.lbl_home_team.config(bg="#131a28")
            self.lbl_home_status.config(text="possession: text", fg="#94a3b8", bg="#131a28")


    def _team_tick(self):
        """text independent textortext textandtext/color team‌text (text‌text to buttontext connection original).
        versiontext 10text6 — exactly text textortext user:
          * until andtext‌text: text 1 second text connection (TEAM_TRACKER_INTERVAL_MS)text
          * after from andtext‌text: from same moment to after read «text‌untiltext» text‌text —
            text 50ms (TEAM_LIVE_INTERVAL_MS) text text realtime_loop tool originaltext
          * in text text color chart text from leagues_data.json + byte istext numbertext
            color text text‌textandtext (in textandtext changetext chart and text‌text to‌textandtext text‌textandtext).
        versiontext 10text7 — firstandtext 1 in start text new: text _team_rehook_pending
        (text‌text in _on_new_hand_detected) ⇒ text text 50ms aftertext textdistance
        text‌text text again text‌textandtext (detection Home/Away first from text)."""
        urgent = bool(getattr(self, "_team_rehook_pending", False))
        self._team_rehook_pending = False
        snap: Dict[str, Any] = {}
        try:
            snap = self.team_tracker.poll()
            self._apply_team_identity(snap)
            self._apply_team_colors(snap)
            if urgent:
                try:
                    self.dbg.event("TEAM_REHOOK", note="read immediate text‌text in "
                                                   "start text new (firstandtext 1)",
                                   home=str(snap.get("home")),
                                   away=str(snap.get("away")),
                                   menu=str(snap.get("menu")))
                except Exception:
                    pass
        except Exception as e:
            try:
                self.dbg.error("TEAM", f"tick error: {e}")
            except Exception:
                pass
        if self._team_loop_running:
            # technical note‌untiltechnical note after from connection / technical note technical note 1 second until connection
            interval = (TEAM_LIVE_INTERVAL_MS if snap.get("connected")
                        else TEAM_TRACKER_INTERVAL_MS)
            self.after(interval, self._team_tick)

    def _apply_team_identity(self, snap: Dict[str, Any]):
        """Renders the logos in the home/away slots (GUI build). If no valid
        team selection has been seen yet (state 100) or the team image is
        not in Football_Database, the slot keeps its «Home»/«Away»
        fallback text. v2.0.6 — identity changes are printed to stdout so
        backend_log.txt shows exactly WHEN the crests became known."""
        for side in ("home", "away"):
            ident = snap.get(side)
            if ident != self._team_ident_last.get(side):
                self._team_ident_last[side] = ident
                self._tv_dirty = True
                try:
                    print(f"[TEAM IDENT] {side} = {ident}", flush=True)
                except Exception:
                    pass
        if ImageTk is None:
            return
        for side, slot, fallback in (("home", self.lbl_home_logo, "Home"),
                                     ("away", self.lbl_away_logo, "Away")):
            ident = snap.get(side)
            path = self.team_tracker.logo_path_for(ident)
            if path == self._team_logo_path[side]:
                continue   # unchanged — technical note technical note image tool original
            photo = None
            if path:
                try:
                    img = Image.open(path)
                    img.thumbnail(TEAM_LOGO_SLOT_PX, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                except Exception:
                    photo = None
            if photo is not None:
                self._team_logo_photo[side] = photo       # prevent from Garbage Collection
                self._team_logo_path[side] = path
                slot.config(image=photo, text="",
                            width=TEAM_LOGO_SLOT_PX[0], height=TEAM_LOGO_SLOT_PX[1])
                try:
                    self.dbg.event("TEAM_LOGO", side=side, ident=str(ident))
                except Exception:
                    pass
            else:
                self._team_logo_photo[side] = None
                self._team_logo_path[side] = None
                slot.config(image="", text=fallback,
                            width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)

    def _apply_team_colors(self, snap: Dict[str, Any]):
        """text color text team (textandtext 1..6 section 26-text) and text text:
          * self._chart_colors ⇒ in render aftertext chart (text 100ms) text text‌textandtext
          * text‌text text team name: text text (color text) or currentlytext textandtext
            colortext textand text (color original + color textandtext)text
          * changetext in momentum_debug_log.txt text register text‌textandtext (TEAM_COLOR)."""
        try:
            idx = snap.get("color_idx") or {}
            dec = self.team_colors.resolve(snap.get("home"), idx.get("home"),
                                           snap.get("away"), idx.get("away"))
        except Exception as ex:
            try:
                self.dbg.error("TEAMCOLOR", f"resolve error: {ex}")
            except Exception:
                pass
            return
        sig = (dec["home"]["final"], dec["home"]["original"],
               dec["away"]["final"], dec["away"]["original"])
        if sig == self._team_color_sig:
            return   # unchanged — render technical note technical notefromtechnical note is not
        self._team_color_sig = sig
        for side in ("home", "away"):
            ch = dec[side]
            self._team_color_state[side] = ch
            self._chart_colors[side] = _rgb_to_hex(ch["final"])
        self._refresh_color_dots()
        try:
            self.dbg.event("TEAM_COLOR",
                           home=_rgb_to_hex(dec["home"]["final"]),
                           away=_rgb_to_hex(dec["away"]["final"]),
                           home_replaced=str(dec["home"]["replaced"]),
                           away_replaced=str(dec["away"]["replaced"]),
                           home_ident=str(snap.get("home")),
                           away_ident=str(snap.get("away")),
                           color_idx=str(snap.get("color_idx")))
        except Exception:
            pass

    def _refresh_color_dots(self):
        """text color text text team (rule 4):
          * text text: text text — color text‌text chart (text text)text
          * text textandtext (rule 2/3): textand text — color original (text text)
            + color textandtext text code text text (text text)."""
        for side, canvas in (("home", getattr(self, "cvs_home_colors", None)),
                             ("away", getattr(self, "cvs_away_colors", None))):
            if canvas is None:
                continue
            try:
                st = self._team_color_state[side]
                canvas.delete("all")
                d = TEAM_COLOR_DOT_PX
                y = max(1, (TEAM_COLOR_DOT_H - d) // 2)
                x = 1
                if st.get("replaced") and st.get("original"):
                    canvas.config(width=(d + 6) * 2 + 2)
                    canvas.create_oval(x, y, x + d, y + d,
                                       fill=_rgb_to_hex(st["original"]),
                                       outline="#7f8fa6", width=1)
                    x += d + 6
                else:
                    canvas.config(width=d + 2)
                canvas.create_oval(x, y, x + d, y + d,
                                   fill=_rgb_to_hex(st["final"]),
                                   outline="#ffd166", width=2)
            except Exception:
                pass


    def _shot_debug_push(self, stage: str, **kw):
        """layer textwithtext chain shot — Worker/ShotEngine → UI (Thread-safe via deque)"""
        try:
            self.shot_debug_log.append({"wall": time.time(), "stage": stage, **kw})
        except Exception:
            pass

    @staticmethod
    def _shot_trigger_decision(prev_baseline: Optional[int], shot_cnt: Optional[int]):
        """
        text text shot from countertext «global» — exactly text tool independent user:
          * baseline None        → register baseline (without text)
          * shot_cnt < baseline  → RESET (second half/restarttext without text)
          * shot_cnt > baseline  → TRIGGER (jump = text or text shot new)
          * text / None         → unchanged
        output: (baseline newtext text) text text ∈ {None, 'BASELINE', 'RESET', 'TRIGGER'}
        text totaltext: text untiltext to possession text text possession never baseline text
        withtextandtext text‌text — text complete withtext text‌text text in version 2.
        """
        if shot_cnt is None:
            return prev_baseline, None
        if prev_baseline is None:
            return shot_cnt, "BASELINE"
        if shot_cnt < prev_baseline:
            return shot_cnt, "RESET"
        if shot_cnt > prev_baseline:
            return shot_cnt, "TRIGGER"
        return prev_baseline, None

    def _step_shot_tracking(self, burst: int = 0) -> Optional[ShotEventData]:
        """
        text or text text textandtext from text‌text textandfrom shot.
        burst > 0: until burst text with distancetext ~12ms run text‌textandtext (text‌textfromtext text
        text ~15ms tool independent) — only when text‌text active istext in textandtext
        text text text‌second text stall text‌textandtext and because decay text text MATCH
        TIME istext textortext textandtextandtext text‌text text text text text‌text.
        """
        if self.shot_engine.state != "TRACKING":
            return None
        shot_data = None
        steps = max(1, int(burst))
        for _ in range(steps):
            shot_data = self.shot_engine.update_tracking(self.engine)
            if shot_data is not None:
                break
            time.sleep(0.012)
        return shot_data

    def _register_shot_data(self, shot_data: ShotEventData):
        """register ShotEventData textandtext Event Bus + chaintext [SHOT] + card UI
        versiontext 10text14 — Dedup «only» with text text (1 increment counter = 1 register):
          * text text 10text12 (team/text/text/1 second) text text — textand shot realtext
            text‌text (text textwithtext) text text text‌textandtext
          * path complete text text‌textandtext:
            ShotEventData → register_shot_event() → Momentum Impact → Threat
            → UI Shot List — text text with log [SHOT] and countertext text."""
        try:
            cand_id = getattr(shot_data, "candidate_id", None)
            if cand_id is not None:
                if cand_id in self._registered_shot_ids:
                    self.shot_engine._stat("duplicates")
                    self._shot_debug_push("DUP_SUPPRESSED", team=shot_data.team,
                                          candidate_id=cand_id,
                                          shot_match_time=shot_data.match_time,
                                          shooter_seat=shot_data.shooter_seat,
                                          outcome=shot_data.outcome,
                                          note="same text counter beforetext registeredtext — register second text text")
                    return
                self._registered_shot_ids.add(cand_id)
                self._registered_shot_order.append(cand_id)
                while len(self._registered_shot_order) > ShotConfig.SHOT_FINALIZED_KEEP:
                    _old = self._registered_shot_order.popleft()
                    self._registered_shot_ids.discard(_old)
            self.event_engine.register_shot_event(shot_data)
            self.shot_engine._stat("events_registered")
            self._shot_debug_push("SHOT_REGISTERED", team=shot_data.team,
                                  shot_event_id=shot_data.event_id,
                                  candidate_id=cand_id,
                                  shot_match_time=shot_data.match_time,
                                  shooter_seat=shot_data.shooter_seat,
                                  shot_type=shot_data.primary_type,
                                  outcome=shot_data.outcome,
                                  pre_threat=shot_data.pre_shot_threat,
                                  final_threat=shot_data.final_threat,
                                  shot_engine_state=self.shot_engine.state)
            # --- Momentum Impact (technical note path complete specification user) ---
            imp = self.momentum.get_impact(shot_data.event_id)
            if imp is not None:
                self.shot_engine._stat("threats_created")
                self._shot_debug_push("THREAT_CREATED", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      momentum_impact=f"{imp.final_impact:+.1f}",
                                      note="Impact textandtextandtext for shot text text")
            else:
                self._shot_debug_push("THREAT_MISSING", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      note="Impact textdecrease text (check textandtext)")
            # --- UI Shot List ---
            self._ui_post(self.update_shot_card, shot_data)
            self.shot_engine._stat("ui_added")
            self._shot_debug_push("UI_ADDED", team=shot_data.team,
                                  shot_event_id=shot_data.event_id,
                                  candidate_id=cand_id,
                                  note="shot to text UI text text")
        except Exception as ex:
            clog(f"[Shot Register] {ex}")

    def _timer_rebirth_tick(self, total_t: Optional[float], now_wall: float):
        """
        textortext text user: «when untiltext withtext to text text text text and second/minute
        text start to rise text text start text new — text withtext beforetext text
        text withtext text text. code must text fast detection text and hook‌text text in text
        from second text and again hook text.»

        text text lightweight (text text Worker ~15ms ⇒ delay detection < 50ms):
          * untiltext ≤ TRB_ZERO_T  ⇒ armed (untiltext text text text)
          * armed and untiltext > TRB_RISE_T ⇒ start to rise ⇒ FIRE + Disarm
        text second from 45:00 start text‌textandtext (minute‌text 45 text text) ⇒ never FIRE
        text‌textandtext text‌text shared with Watchdog 10text3 from reset textandtext prevent
        text‌text (text textand path _last_auto_reset_wall text to‌textandtext text‌text).
        """
        if total_t is None:
            return
        try:
            t = float(total_t)
        except (TypeError, ValueError):
            return
        if t <= TRB_ZERO_T:
            if not self._trb_armed:
                self._trb_armed = True
                _d = getattr(self, "dbg", None)
                if _d:
                    _d.event("TIMER_ZERO_ARMED", t=round(t, 2),
                             note="untiltext text text text — text start to rise")
                # --- versiontechnical note 10technical note18 — specification user: «to technical note technical note untiltechnical note technical note
                # technical note hook new technical note technical note until address new technical note technical note» — cycletechnical note technical note
                # address possession exactly in momenttechnical note technical note technical notefrom technical note‌technical noteandtechnical note (before from technical note
                # line technical note unchanged is)technical note firsttechnical note capture technical note value 2
                # confirmation and hook technical note technical note‌technical noteandtechnical note.
                self._possession_begin_capture_cycle("timer-zero")
            return
        if self._trb_armed and t > TRB_RISE_T:
            self._trb_armed = False
            if ((now_wall - self._trb_last_fire_wall) < TRB_COOLDOWN_SEC
                    or (now_wall - getattr(self, "_last_auto_reset_wall", 0.0))
                    < TRB_COOLDOWN_SEC):
                return    # Watchdog/reset automatictechnical note technical note technical note — again‌technical note technical notemenutechnical note
            self._trb_last_fire_wall = now_wall
            self._on_new_hand_detected(t)

    def _possession_begin_capture_cycle(self, reason: str) -> None:
        """versiontext 10text18 — textfrom cycletext text address possession from side App:
        momenttext text untiltext (start withtext new) or firsttext PLAYING after from connection
        andtext withtext. only text line textanduntiltext [PossHook] — without log text text."""
        try:
            rep = self.engine.poss_begin_capture_cycle()
            print(f"[PossHook] cycletext capture possession textfrom text ({reason}): {rep}",
                  flush=True)
        except Exception as ex:
            print(f"[PossHook] {reason}: {type(ex).__name__}: {ex}",
                  flush=True)

    def _on_new_hand_detected(self, t: float):
        """
        text start text new — to order firstandtext usertext in text from second:
          1) hook detection Home/Away: read immediate text‌text (firstandtext first —
             player possible is fast ball text from text text)text
          2) textistext‌text/install text text 4 hook (ball/time/text/possession) + re-arm
             capture text and possession (address‌text beforetext text textandtext text‌text)text
          3) reset complete match (chart/textandtextdatatext/text/counter‌text) —
             same path _perform_reset text State Machine 10text3 istext text‌text.
        """
        _d = getattr(self, "dbg", None)
        clog(f"[NewHand] ⚡ start text new detection data text: untiltext {_fmt_clock(t)} "
              "— textandtextfromtext fast hook‌text (firstandtext: detection Home/Away)")
        # --- firstandtechnical note 1: detection Home/Away (technical note aftertechnical note 50ms technical noteortechnical note technical noteandtechnical note technical note‌technical noteandtechnical note)
        self._team_rehook_pending = True
        # --- 2/3: technical noteandtechnical notefromtechnical note hook‌technical note + reset complete ---
        rep: Dict[str, str] = {}
        try:
            rep = self.engine.verify_and_repair_hooks()
        except Exception as ex:
            rep = {"error": f"{type(ex).__name__}: {ex}"}
        if _d:
            _d.event("NEW_HAND_DETECTED", t=round(float(t), 2), hooks=str(rep),
                     note="untiltext text→risetext hook‌text textandtextfromtext + match reset text")
        self._perform_reset(momentum_start_t=float(t))
        self._ui_post(lambda: self.lbl_status.config(
            text="andtext: start text new — hook‌text textandtextfromtext text 🔄", fg="#00b4d8"))

    def _flag_time_drop(self, prev_t: float, new_t: float):
        """
        version 3 — decrease text time withtext «only text text‌textandtext»text text reset automatictext
        text text text‌textandtext (chart match end must text textandtext).
        text text text resume PLAYING in section 7.5 text text‌textandtext:
        HT (second half) / withtext new (from text) / text chart.
        version 10text3 — if text‌text‌text HT (first half ≥ 45:00 text text) text
        withtext State Machine to HALFTIME text‌textandtext (in text resume)text
        confirmation text text with rule text classify_resume_after_drop is.
        """
        self._ht_pending = True
        self._ht_prev_end_t = prev_t
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("TIME_DROP_FLAGGED",
                     prev=(round(float(prev_t), 1) if prev_t is not None else None),
                     new=(round(float(new_t), 1) if new_t is not None else None),
                     half=self.half_number)
        if self.half_number == 1 and prev_t >= self.config.HT_HARD_MIN_FIRST_HALF:
            self._match_phase = MatchPhase.HALFTIME
            try:
                self.momentum.set_phase_label(MatchPhase.HALFTIME.value)  # 10technical note15
            except Exception:
                pass
        if self.half_number == 1 and prev_t >= self.config.HT_MIN_FIRST_HALF_PLAYED:
            status_txt = "andtext: text end first half — in text resume withtext 🟠"
        else:
            status_txt = "andtext: decrease time withtext — chart text text (match end/withtext newtext) 🟠"
        self._shot_debug_push("TIME_DROP_FLAGGED", team="--",
                              prev_time=prev_t, new_time=new_t,
                              half_number=self.half_number)
        self._ui_post(lambda: self.lbl_status.config(text=status_txt, fg="#fca311"))

    def request_reset(self, *args, **kwargs):
        """Original button behaviour: queue a reset + status hint."""
        self._reset_requested = True
        try:
            self.lbl_status.config(text="andtext: request reset registered...", fg="#fca311")
        except Exception:
            pass


    def _perform_reset(self, momentum_start_t: Optional[float] = None):
        """events / sequences / momentum history / counters / frame buffer / time state / graph"""
        # --- versiontechnical note 10technical note11 — «savetechnical note technical note charttechnical note»: latest chart withtechnical note beforetechnical note
        # must before from technical note‌technical note untiltechnical note register technical noteandtechnical note (untiltechnical note to 00:00 reset technical note =
        # start technical note new). technical note technical note technical note technical noteagetechnical note‌technical note for withtechnical note new technical note technical note‌technical noteandtechnical note.
        try:
            self._snapshot_finalize_previous_match()
        except Exception:
            pass
        try:
            self.snap_engine.reset_match(time.time())
            self._snap_capture_cache = {}
            # versiontechnical note 10technical note21 — test 6: technical noteorder cycletechnical note technical note for withtechnical note new from technical noteand
            # (countertechnical note seq global technical note‌technical note — number‌technical note technical note Snapshot #42 resume technical note)
            self._snap_life = {}
            # v10.28 — cleanup andtechnical note technical note display for withtechnical note new
            self._snap_end_dispatch_lvl = None
            self._snap_half_block_noted = set()
            self._snap_abandon_noted = set()
            try:
                with self._snap_show_lock:
                    self._snap_show_events.clear()
            except Exception:
                pass
        except Exception:
            pass
        # v2.0.5 — new match: the crest signal banner may fire again
        try:
            self._crest_banner_reset()
        except Exception:
            pass
        # versiontechnical note 10technical note15 — window‌technical note technical noteagetechnical note‌technical note (live + technical note‌technical note) with reset match
        # technical note‌technical notewithtechnical note technical note‌technical noteandtechnical note
        # versiontechnical note 10technical note19 — from Worker direct to UI technical note‌technical noteandtechnical note (technical note Tk technical note‌technical note)
        try:
            self._ui_post(self._hide_snapshot_overlay)
        except Exception:
            pass
        # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] reset match → EMPTY
        try:
            self._snap_state_event("MATCH RESET", SnapshotState.EMPTY,
                                   key=None, extra="match reset")
        except Exception:
            pass
        # technical note technical noteandtechnical note current without technical note technical note new
        self.pass_engine.reset()
        # versiontechnical note 10technical note14 — technical note chaintechnical note shot «technical note from» reset must register/display data technical noteandtechnical note
        # (technical noteortechnical note technical note: Counter increments = Candidates ≈ Registered Events)
        try:
            _ss = dict(self.shot_engine.stats)
            if any(_ss.values()):
                self._shot_debug_push("MATCH_SHOT_STATS", team="--", **_ss)
        except Exception:
            pass
        self.shot_engine.reset()
        self.event_engine.reset()
        cur_t = momentum_start_t if momentum_start_t is not None else self.runtime.get_core()["current_match_time"]
        self.momentum.reset(cur_t)
        self.frame_buffer.clear()
        self.pass_counters = {"Home": None, "Away": None}
        # version 3: baseline global counter shot (exactly technical note tool independent user)
        self.shot_counter_baseline: Optional[int] = None
        # version 4: baseline counter‌technical note technical note (with reset match again baseline technical note‌technical noteandtechnical note)
        self.goal_counters = {"Home": None, "Away": None}
        # version 6: freetechnical notefromtechnical note slot capture → firsttechnical note technical noteandtechnical noteuntiltechnical note technical note withtechnical note newtechnical note
        # structure technical note fresh technical note capture technical note‌technical note (technical noteandtechnical note‌technical note withtechnical note‌technical note aftertechnical note)
        try:
            self.engine.goal_hooker.reset_capture(self.engine.h_process)
        except Exception:
            pass
        # version 10technical note4: re-arm capture «possession» — same technical noteandtechnical note self-heal goal hook.
        # withtechnical note in withtechnical note new structure technical note/possession technical note technical noteto‌technical note technical note‌technical note capture legacy
        # address technical note technical note technical note‌technical noteandtechnical note → technical notedatatechnical note from withtechnical note second to after technical note technical note‌technical note.
        # versiontechnical note 10technical note18 — re-arm smart: if address «technical note withtechnical note» technical note second past
        # confirmation technical note withtechnical note technical note technical note‌technical noteandtechnical note (start withtechnical note without deterministic possessiontechnical note technical note
        # «chart in technical note technical note technical note technical note‌technical note»)
        _poss_cap_before = None
        try:
            _poss_cap_before = getattr(self.engine.poss_hooker, "captured_address", None)
            self.engine.rearm_possession_capture()
        except Exception:
            pass
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("MATCH_RESET",
                     t=(round(float(cur_t), 1) if cur_t is not None else None),
                     poss_cap_before=fmt_ptr(_poss_cap_before),
                     gh_rcx_before=fmt_ptr((self._goal_hook_status or {}).get("rcx")),
                     note="reset complete match — capture text and possession again armed text")
        self.current_possession = None
        # versiontechnical note 10technical note14 — cleanup Dedup register shot for matchtechnical note new
        self._registered_shot_ids.clear()
        self._registered_shot_order.clear()
        self._last_ev_count = 0
        self._last_seq_count = 0
        self._last_imp_count = 0
        self._ui_pass_list.clear()
        self._ui_shot_list.clear()
        # version 2: reset andtechnical note technical note / HT and technical note‌technical note livetechnical note Sequences
        self.half_number = 1
        self._ht_pending = False
        self._ht_prev_end_t = 0.0
        # --- version 10technical note3: Match Lifecycle — start technical note from HALF_1 ---
        # (HALF_1 → HT → HALF_2 → FULL_TIME | untiltechnical note≈technical note+PLAYING → NEW_MATCH → HALF_1)
        self._match_phase = MatchPhase.HALF_1
        try:
            self.momentum.set_phase_label(MatchPhase.HALF_1.value)   # versiontechnical note 10technical note15
        except Exception:
            pass
        self._match_seen_max_t = float(cur_t)
        # --- version 10technical note3: First-Capture Goal for withtechnical note new again armed technical note‌technical noteandtechnical note ---
        # reset_capture withtechnical note slottechnical note technical note technical note technical note firsttechnical note technical noteandtechnical noteuntiltechnical note technical note withtechnical note new
        # again Capture technical note‌technical note and if same moment technical note first technical noteandtechnical note
        # _register_first_hook_goal technical note technical note register technical note‌technical note (technical note technical noteand team independent).
        self._gh_fc_pending = {"Home": True, "Away": True}
        _d = self._gh_diag
        _d["last_captured"] = None
        _d["last_rcx"] = None
        _d["last_home"] = None
        _d["last_away"] = None
        _d["baselined"] = {"Home": False, "Away": False}
        self._goal_hook_status = {"hooked": False, "captured": False,
                                  "secondary": False, "rcx": None,
                                  "home": None, "away": None, "events": 0}
        # --- versiontechnical note 10technical note27 — reset red card: baseline/in technical note‌technical note/technical note
        # technical note technical note‌technical noteandtechnical note (coordinates players in withtechnical note new again technical note technical note‌technical noteandtechnical note —
        # seattechnical note technical noteandtechnical note technical note‌technical noteandtechnical note)technical note technical note with momentum.reset technical note technical note‌technical note.
        self._rc_state = {"baseline": None, "pending": [], "exiles": set()}
        _rc_diag = getattr(self, "_rc_diag", None)
        if isinstance(_rc_diag, dict):
            _rc_diag["n_cards"] = 0
            _rc_diag["n_attr"] = 0
            _rc_diag["n_timeout"] = 0
        self._seq_row_items.clear()
        self._seq_last_values.clear()
        self.runtime.reset()
        self.runtime.connected = True
        # --- versiontechnical note 10technical note7: technical note‌technical note shared reset‌technical note automatic + technical note technical note TV ---
        self._last_auto_reset_wall = time.time()
        self._trb_armed = False
        self._tv_dirty = True
        self._tv_max_half2_t = 0.0
        self._ui_post(self._clear_ui_lists)

    def _clear_ui_lists(self):
        self.tree_ev.delete(*self.tree_ev.get_children())
        self.tree_seq.delete(*self.tree_seq.get_children())
        self.tree_pass.delete(*self.tree_pass.get_children())
        self.tree_shot.delete(*self.tree_shot.get_children())
        self.tree_debug.delete(*self.tree_debug.get_children())
        self._seq_row_items.clear()
        self._seq_last_values.clear()
        self.lbl_card_title.config(text="textandtext pass: in text start withtext...")
        self.lbl_card_threat.config(text="Threat Score: --")
        self.lbl_card_outcome.config(text="")
        self.lbl_shot_title.config(text="textandtext shot: in text register text shot...")
        self.lbl_shot_threats.config(text="Pre Threat: -- | Final Threat: --")
        self.lbl_shot_outcome.config(text="result: --")
        # versiontechnical note 10technical note12 — technical note Live technical note technical note only render technical note technical note TV technical notefromtechnical note is
        self._tv_dirty = True
        self.lbl_status.config(text="andtext: reset complete text — in text withtext 🟠", fg="#fca311")


    def on_close(self):
        # versiontechnical note 10technical note18 — technical noteandtechnical note technical note technical note (technical note frozen and Errortechnical note TclError technical note technical noteandtechnical note):
        #   1) technical note _closing above from technical note — technical note callback technical note‌technical note technical note technical note technical note‌technical noteandtechnical note
        #   2) stop technical note‌technical note (Worker/connection automatic/team‌technical note/technical note)
        #   3) technical note technical noteanduntiltechnical note for end Worker (technical noteandtechnical note after() simultaneous with destroy)
        #   4) technical note window‌technical note technical noteagetechnical note‌technical note/technical noteandtechnical note and hook‌technical note technical note destroy
        self._closing = True
        self.is_monitoring = False
        # versiontechnical note 10technical note7 — stop technical note connection automatic
        self._auto_connect_running = False
        # version 10technical note5 — stop technical note independent team‌technical note and technical note technical note read-only technical note
        self._team_loop_running = False
        # versiontechnical note 10technical note16 — stop technical note technical note technical noteagetechnical note‌technical note
        try:
            self._snap_anim_gen += 1
            self._snap_anim_alive = False
        except Exception:
            pass
        # versiontechnical note 10technical note18 — technical note technical noteanduntiltechnical note for end Worker (technical note ~2 technical note technical note)
        _wt = getattr(self, "_worker_thread", None)
        if _wt is not None:
            try:
                if _wt.is_alive():
                    _wt.join(timeout=1.5)
            except Exception:
                pass
        # versiontechnical note 10technical note18 — technical noteand «technical note» untiltechnical note after withtechnical note‌technical note until technical note callback
        # after from destroy run technical noteandtechnical note (technical note Errortechnical note «invalid command name»)
        try:
            _ids = self.tk.splitlist(self.tk.call("after", "info"))
            for _aid in _ids:
                try:
                    self.after_cancel(_aid)
                except Exception:
                    pass
        except Exception:
            pass
        # versiontechnical note 10technical note11 — technical note windowtechnical note technical noteagetechnical note‌technical note and technical noteandtechnical note technical note
        try:
            self._hide_snapshot_overlay()
        except Exception:
            pass
        # versiontechnical note 10technical note23 — technical noteandtechnical note technical note Renderer GPU (technical note + Context + GLFW)
        try:
            _gpu = getattr(self, "_snap_gpu", None)
            if _gpu is not None:
                _gpu.shutdown(timeout=1.5)
                self._snap_gpu = None
        except Exception:
            pass
        _dlg = getattr(self, "_snap_dlg", None)
        if _dlg is not None:
            try:
                _dlg.destroy()
            except Exception:
                pass
        try:
            self.team_tracker.close()
        except Exception:
            pass
        try:
            self.engine.cleanup()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _save_shown_chart_copy(self, key, path=""):
        """NEW SETTING — "permanently save the charts": when
        ModsConfig.json -> mods -> Match Momentum -> mm_save_shown_charts is
        true, EVERY chart prepared for display (h1/h2/et target minutes and
        the end-of-match charts) is copied into Momentum_Saves/ with a
        per-match descriptive name (match start stamp + team ids + key).
        Runs on the Worker thread right after the show request is queued, so
        the file exists even if the on-screen show later fails and retries
        (same target name => overwritten, never duplicated per key).
        The existing permanent_save behaviour (last chart of the match) is
        unchanged and independent."""
        try:
            if not self.snap_engine.s.get("save_shown_charts"):
                return
            p = path
            if not p or not os.path.isfile(p):
                p = self._snapshot_tmp_path(key)
            img = self._snap_capture_cache.get(key)
            if not os.path.isfile(p) and img is not None:
                try:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    img.save(p, format="PNG")
                except Exception:
                    return
            if not os.path.isfile(p):
                return
            save_dir = os.path.join(self._script_dir, TV_SNAP_SAVE_DIRNAME)
            os.makedirs(save_dir, exist_ok=True)
            w = self.snap_engine.match_start_wall
            stamp = (time.strftime("%Y-%m-%d_%H-%M", time.localtime(w)) if w
                     else time.strftime("%Y-%m-%d_%H-%M"))
            names = {}
            for side in ("home", "away"):
                ident = self._team_ident_last.get(side)
                names[side] = _pt_team_label(ident, side)   # [PT v2.3.0]
            key_norm = {"h1": "H1", "h2": "H2", "et": "ET", "end": "END",
                        "end90": "END90", "end120": "END120"}.get(
                            str(key), str(key).upper())
            base = (f"momentum_{stamp}_{names['home']}_vs_{names['away']}"
                    f"_{key_norm}")
            dst = os.path.join(save_dir, base + ".png")
            with open(p, "rb") as _fsrc:
                _data = _fsrc.read()
            with open(dst, "wb") as _fdst:
                _fdst.write(_data)
            clog(f"[Momentum] chart saved permanently: "
                 f"{os.path.basename(dst)}")
        except Exception:
            pass

# =====================================================================
# technical note andtechnical noteandtechnical note technical notenametechnical note
# =====================================================================
# =====================================================================
# 27. test technical notewithtechnical note End-to-End (version 2 — technical note 21)
# ---------------------------------------------------------------------
# without technical noteortechnical note to withtechnical note realtechnical note technical noteortechnical note technical noteandtechnical note technical noteandtechnical note istechnical note to technical noteandtechnical noteandtechnical note
# Momentum technical note technical note‌technical noteandtechnical note and technical noteuntiltechnical note technical note asserts technical note‌technical note:
#   ✔ technical notedatatechnical note Home to withtechnical note / Away to below
#   ✔ decay technical note technical note technical note (only Match Time)
#   ✔ Goal Marker exactly technical noteandtechnical note t_goal and Goal Peak with delay GOAL_PEAK_DELAY
#   ✔ technical note technical noteandwithtechnical note technical note Chance + Shot technical note‌technical note (SHOT_LINKED_CHANCE_RATIO)
#   ✔ chart never to‌technical noteandtechnical note technical note technical note technical noteandtechnical note technical note‌technical note
#   ✔ Gaussian smoothing real (layer display)
#   ✔ Pause (time technical note) → without sample/decay new
#   ✔ gap HT (sample‌technical note NaN + offset second half)
# run:  python FL_2026_Live_Match_Momentum_v9.py --selftest
# =====================================================================
