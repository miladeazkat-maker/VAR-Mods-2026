def run_selftest(render_png: bool = True) -> int:
    print("=" * 74)
    print(" FL_2026 Live Match Momentum v9 — End-to-End Self Test")
    print("=" * 74)

    import matplotlib
    try:
        matplotlib.use("Agg")   # headless — بدون نیاز به نمایشگر
    except Exception:
        pass
    import matplotlib.pyplot as plt

    cfg = MomentumScoringConfig()
    mom = MomentumEngine(cfg)
    failures: List[str] = []
    total = 0

    def check(name: str, cond: bool, detail: str = ""):
        nonlocal total
        total += 1
        mark = "[PASS]" if cond else "[FAIL]"
        print(f"  {mark} {name}" + (f"  | {detail}" if detail else ""))
        if not cond:
            failures.append(name)

    def make_ev(eid, etype, team, mt, md=None, rel=EventReliability.CERTAIN, conf=1.0, related=None):
        return GameEvent(
            event_id=eid, event_type=etype, team=team,
            timestamp=time.time(), match_time=mt,
            reliability=rel, confidence=conf,
            position=(0.0, 0.0, 0.0),
            related_event_ids=list(related or []),
            metadata=dict(md or {}),
            tags=["selftest"]
        )

    # ---------- جریان مصنوعی استاندارد (بند ۲۱) ----------
    stream = [
        (0.0,    "Pass", "Home", {"threat_score": 20.0, "is_success": True}),
        (60.0,   "Chance", "Home", {}),
        (120.0,  "Chance", "Away", {}),
        (300.0,  "Shot", "Home", {"final_threat": 60.0}),
        (600.0,  "Shot", "Away", {"final_threat": 70.0}),
        (1200.0, "Goal", "Home", {}),
        (1800.0, "Goal", "Away", {}),
        (2400.0, "Big Chance", "Home", {}),
    ]
    next_id = 1
    pending = {}
    for mt, et, team, md in stream:
        pending[mt] = make_ev(next_id, et, team, mt, md)
        next_id += 1

    # شبیه‌سازی Game Clock: 0 تا 46:00 با گام 0.5s — رویداد دقیقاً در زمان خودش
    # نسخه ۷: رخداد Goal دقیقاً مثل زنجیرهٔ واقعی _register_hook_goal ثبت
    # می‌شود: اول مارکر مستقیم هوک (disp_time در همان لحظه فریز) و بعد
    # انتشار روی Event Bus → Impact پالس. دو مسیر مستقل می‌مانند.
    def _fire_goal_like_hook(ev, mt):
        mom.add_hook_goal_marker(ev.team, mt, 1)   # (۱) مارکر مستقیم — اول
        mom.on_event(ev)                            # (۲) Event Bus → Impact پالس

    t = 0.0
    T_END = 2760.0
    while t <= T_END:
        for mt in [m for m in pending if m <= t]:
            _ev = pending.pop(mt)
            if _ev.event_type == "Goal":
                _fire_goal_like_hook(_ev, mt)
            else:
                mom.on_event(_ev)
        mom.update(t)
        t += 0.5
    for mt in pending:                      # هر رویداد باقی‌مانده (نباید رخ دهد)
        mom.on_event(pending[mt])
    mom.update(T_END)

    hist = [s for s in mom.history if s["net"] == s["net"]]

    def val_at(tm: float, key: str) -> float:
        best = min(hist, key=lambda s: abs(s["game_time"] - tm))
        return best[key]

    print("\n--- ۱) جهت رخدادها: Home بالا / Away پایین ---")
    check("Home events → Net > 0", val_at(310.0, "net") > 0,
          f"net(05:10)={val_at(310.0, 'net'):+.1f}")
    check("Away Shot → Away انرژی می‌گیرد", val_at(610.0, "away") > val_at(300.0, "away"),
          f"away(10:10)={val_at(610.0, 'away'):+.1f} > away(05:00)={val_at(300.0, 'away'):+.1f}")
    check("Away events → Net رو به پایین", val_at(615.0, "net") < val_at(305.0, "net"),
          f"net(10:15)={val_at(615.0, 'net'):+.1f} < net(05:05)={val_at(305.0, 'net'):+.1f}")

    print("\n--- ۲) Decay نمایی (فقط Match Time) ---")
    check("decay: Net(19:50) < Net(05:10)", val_at(1190.0, "net") < val_at(310.0, "net"),
          f"{val_at(1190.0, 'net'):+.1f} < {val_at(310.0, 'net'):+.1f}")
    half = cfg.MOMENTUM_HALF_LIFE
    v0 = val_at(305.0, "home")
    v1 = val_at(305.0 + half, "home")
    check(f"نیم‌عمر {half:.0f}s → سهم حدوداً نصف", v1 < v0 * 0.75, f"home(05:05)={v0:.1f} → home(+HL)={v1:.1f}")

    print("\n--- ۳) Goal Marker / Goal Delayed Pulse ---")
    g_imp = next((i for i in mom.impacts if i.event_type == "Goal" and i.team == "Home"), None)
    check("Goal Home → Impact با pulse", g_imp is not None and g_imp.is_goal_pulse)
    if g_imp:
        check("Goal Marker روی 20:00 دقیق", abs(g_imp.goal_time - 1200.0) < 1e-9,
              f"goal_time={_fmt_clock(g_imp.goal_time)}")
        check("Goal Peak روی 20:05 (DELAY=5s بازی)", abs(g_imp.peak_time - 1205.0) < 1e-9,
              f"peak_time={_fmt_clock(g_imp.peak_time)}")
        f0 = mom.goal_response_factor(g_imp, 1199.0)
        f_mid = mom.goal_response_factor(g_imp, 1202.5)
        f_peak = mom.goal_response_factor(g_imp, 1205.0)
        f_hold = mom.goal_response_factor(g_imp, 1205.0 + cfg.GOAL_RESPONSE_WIDTH - 0.1)
        f_dec = mom.goal_response_factor(g_imp, 1205.0 + cfg.GOAL_RESPONSE_WIDTH + 60.0)
        check("پاسخ گل قبل از t_goal = 0", f0 == 0.0)
        check("پاسخ گل میانهٔ راه ≈ 0.5 (raised-cosine)", abs(f_mid - 0.5) < 0.02, f"f={f_mid:.3f}")
        check("پاسخ گل در اوج = 1.0", abs(f_peak - 1.0) < 1e-9)
        check("فلات اوج تا peak+WIDTH", abs(f_hold - 1.0) < 1e-9)
        check("پس از فلات → decay نمایی", 0.0 < f_dec < 1.0, f"f(+60s)={f_dec:.3f}")
        check("اوج پاسخ → Net بالا می‌رود", val_at(1206.0, "net") > val_at(1199.0, "net"),
              f"net(20:06)={val_at(1206.0, 'net'):+.1f} > net(19:59)={val_at(1199.0, 'net'):+.1f}")
        phase_peak = mom.goal_pulse_phase(g_imp, 1206.0)
        phase_done = mom.goal_pulse_phase(g_imp, 1199.0)
        check("فازهای pulse درست", phase_done == "WAITING" and phase_peak == "PEAK/ACTIVE",
              f"19:59→{phase_done} | 20:06→{phase_peak}")
    ga_imp = next((i for i in mom.impacts if i.event_type == "Goal" and i.team == "Away"), None)
    check("Goal Away → Peak روی 30:05", ga_imp is not None and abs(ga_imp.peak_time - 1805.0) < 1e-9)
    check("Marker روی t_goal است نه peak", g_imp is not None and g_imp.goal_time < g_imp.peak_time)

    print("\n--- ۴) سلامت سری: بدون تغییر علامت تصادفی ---")
    ok_nonneg = all(s["home"] >= -1e-9 and s["away"] >= -1e-9 for s in hist)
    ok_sum = all(abs(s["net"] - (s["home"] - s["away"])) < 1e-9 for s in hist)
    ok_mono = all(b["game_time"] >= a["game_time"] for a, b in zip(hist, hist[1:]))
    check("home/away هرگز منفی نمی‌شوند", ok_nonneg)
    check("net ≡ home − away (دقیقاً)", ok_sum)
    check("Game Time صعودی", ok_mono)
    # پرش مجاز فقط در لحظهٔ تزریق رخداد لحظه‌ای یا پنجرهٔ رشد پاسخ گل؛
    # در بقیهٔ نمونه‌ها منحنی باید کاملاً نرم باشد (فقط decay نمایی)
    instant_times = [imp.match_time for imp in mom.impacts if not imp.is_goal_pulse]
    goal_windows = [(imp.goal_time, imp.peak_time + cfg.GOAL_RESPONSE_WIDTH + 1.0)
                    for imp in mom.impacts if imp.is_goal_pulse]

    def _in_jump_zone(tm: float) -> bool:
        if any(abs(tm - it) < 1.5 for it in instant_times):
            return True
        return any(g0 - 0.5 <= tm <= g1 for g0, g1 in goal_windows)

    max_allowed = cfg.GOAL_WEIGHT + cfg.BIG_CHANCE_WEIGHT + 10.0
    steps = [(abs(b["net"] - a["net"]), b["game_time"]) for a, b in zip(hist, hist[1:])]
    outside = [d for d, tm in steps if not _in_jump_zone(tm)]
    check("خارج از رخدادها منحنی نرم است (Δ≤2.0/نمونه)", max(outside, default=0.0) <= 2.0,
          f"max outside={max(outside, default=0.0):.3f}")
    check("هیچ پرشی بزرگ‌تر از بیشینهٔ رخداد مجاز نیست",
          all(d <= max_allowed for d, _ in steps),
          f"max step={max((d for d, _ in steps), default=0.0):.1f} ≤ {max_allowed:.0f}")

    print("\n--- ۵) ضد دوبار شماری Chance + Shot لینک‌شده ---")
    ch = make_ev(next_id, "Chance", "Home", 2100.0, {})
    next_id += 1
    mom.on_event(ch)
    sh = make_ev(next_id, "Shot", "Home", 2101.5, {"final_threat": 50.0}, related=[ch.event_id])
    next_id += 1
    mom.on_event(sh)
    ch_imp = mom.get_impact(ch.event_id)
    sh_imp = mom.get_impact(sh.event_id)
    expected_ch = cfg.CHANCE_WEIGHT * cfg.SHOT_LINKED_CHANCE_RATIO * cfg.CERTAIN_MULTIPLIER * 1.0
    check("Chance لینک‌شده کاپ شد (×0.30)", ch_imp is not None and abs(ch_imp.final_impact - expected_ch) < 0.01,
          f"final={ch_imp.final_impact:.2f} ≈ {expected_ch:.2f}")
    check("Shot لینک‌شده کاپ نشد", sh_imp is not None and abs(sh_imp.final_impact - 50.0) < 0.01,
          f"final={sh_imp.final_impact:.2f} = 50.0")
    check("لینک با MATCH TIME (Δt=1.5s ≤ 3.0s)", 0.0 <= sh.match_time - ch.match_time <= 3.0,
          f"Δt={sh.match_time - ch.match_time:.1f}s")

    print("\n--- ۶) Gaussian smoothing واقعی (لایه نمایش) ---")
    sg = gaussian_smooth([0, 0, 0, 0, 9.0, 0, 0, 0, 0], 1.0)
    check("طول سری حفظ می‌شود", len(sg) == 9)
    check("اوج کاهش می‌یابد (نه spike)", 3.0 < max(sg) < 9.0, f"peak={max(sg):.2f}")
    check("جمع سری تقریباً حفظ می‌شود", abs(sum(sg) - 9.0) < 0.6, f"sum={sum(sg):.2f}")

    print("\n--- ۷) Pause (Match Time ثابت → هیچ چیز جلو نمی‌رود) ---")
    n_before = len(mom.history)
    mom.update(T_END); mom.update(T_END); mom.update(T_END)
    check("زمان ثابت → نمونه جدید ثبت نمی‌شود", len(mom.history) == n_before,
          f"len={len(mom.history)} (قبل: {n_before})")

    print("\n--- ۸) شکاف HT (حفظ نمودار بین دو نیمه) ---")
    h1_last_disp = mom.history[-1]["disp_time"]
    mom.set_half_break(cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
    guards = sum(1 for s in mom.history if s["net"] != s["net"])
    check("دو نگهبان NaN در شکاف HT", guards == 2, f"guards={guards}")
    check("عرض شکاف = HT_GAP_DISPLAY_SECONDS",
          mom.ht_break is not None and abs((mom.ht_break[1] - mom.ht_break[0]) - cfg.HT_GAP_DISPLAY_SECONDS) < 1e-9)
    # --- نسخه ۵ (رفع باگ ۲): بازی ساعت را برای نیمه دوم به 45:00 برمی‌گرداند؛
    # نخستین ثانیه‌های نیمه دوم (2700..2760 — عقب‌تر از پایان ثبت‌شدهٔ نیمه اول
    # که T_END=2760 است) باید بلافاصله نمونه بگیرند، نه اینکه نمودار خالی بماند
    n_before_h2 = len(mom.history)
    mom.update(2700.5)   # نخستین نمونهٔ نیمه دوم — هنوز عقب‌تر از T_END نیمه اول
    check("نسخه ۵: نمونه‌برداری نیمه دوم بلافاصله بعد از خط راست HT از سر می‌گیرد",
          len(mom.history) == n_before_h2 + 1,
          f"Δ={len(mom.history) - n_before_h2} (انتظار: +1) | _last_t={mom._last_t:.1f}")
    _s2 = mom.history[-1]
    check("نسخه ۵: اولین نمونهٔ نیمه دوم درست بعد از شکاف است (نه داخل آن)",
          _s2["disp_time"] >= mom.ht_break[1] - 1e-6,
          f"disp={_s2['disp_time']:.1f} ≥ ht_end={mom.ht_break[1]:.1f}")
    mom.update(2820.0)   # نیمه دوم جلو می‌رود (45:00 resumed → 47:00)
    last = mom.history[-1]
    off = mom.display_offset
    check("offset نیمه دوم اعمال شد", abs(last["disp_time"] - (2820.0 + off)) < 1e-9 and off > 0,
          f"offset={off:+.1f}s")
    check("نمونه نیمه دوم بعد از شکاف است", last["disp_time"] >= h1_last_disp + cfg.HT_GAP_DISPLAY_SECONDS - 1e-9,
          f"disp={last['disp_time']:.1f} ≥ {h1_last_disp + cfg.HT_GAP_DISPLAY_SECONDS:.1f}")

    print("\n--- ۹) رندر نمودار (Net-only آینه‌ای + Goal Marker نسخه ۴ + HT) ---")
    ax_ref = {"ax": None}
    if render_png:
        try:
            def fixed_disp(raw):
                if raw != raw:
                    return float('nan')
                return cfg.DISPLAY_RANGE * math.tanh(raw / max(1.0, cfg.DISPLAY_SOFT_SCALE))
            fig = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
            ax = fig.add_subplot(111)
            draw_momentum_chart(ax, mom, cfg, fixed_disp, goal_glyph_ok=True)
            out_png = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "momentum_v10_selftest.png")
            os.makedirs(os.path.dirname(out_png), exist_ok=True)
            fig.savefig(out_png, facecolor=fig.get_facecolor())
            check("رندر headless و ذخیره PNG", os.path.exists(out_png), out_png)
            ax_ref["ax"] = ax
            plt.close(fig)
        except Exception as ex:
            check("رندر headless و ذخیره PNG", False, f"exception: {ex}")

    # --- بررسی Artistهای رندر (نسخه ۷ — مبتنی بر gid قطعی مارکرها) ---
    if ax_ref["ax"] is not None:
        ax = ax_ref["ax"]
        # ۱) خطوط عمودی گل: فقط Artistهای تگ‌شدهٔ مارکر گل (xdata ثابت،
        #    ydata از 0 (خط صفر) تا بیرون — بدون عبور از صفر)
        goal_verts = [ln for ln in ax.lines
                      if (ln.get_gid() or "").startswith("goal_line_")]
        # هر مارکر دو Artist خط دارد: پوستهٔ تیره + مغز سفید
        check("هر گل یک خط عمودی دارد (پوسته + مغز)",
              len(goal_verts) == 2 * len(mom.hook_goal_markers),
              f"verts={len(goal_verts)}")
        ok_no_cross = all(min(ln.get_ydata()) >= 0.0 or max(ln.get_ydata()) <= 0.0
                          for ln in goal_verts)
        check("خط گل از خط صفر عبور نمی‌کند", ok_no_cross)
        # ۲) آیکون توپ: مارکر دایره‌ای تک‌نقطه‌ای برای هر مارکر هوک
        ball_icons = [ln for ln in ax.lines
                      if (ln.get_gid() or "").startswith("goal_ball_")]
        check("آیکون توپ (تکیه‌گاه Line2D) برای هر گل رسم شده",
              len(ball_icons) == len(mom.hook_goal_markers),
              f"icons={len(ball_icons)}")
        # ۲٫۱) نسخه ۱۰٫۲ — آیکون PNG توپ (اگر tex/ball_icon.png موجود باشد)
        if load_ball_icon() is not None:
            _img_icons = [a for a in ax.artists
                          if (a.get_gid() or "").startswith("goal_ballimg_")]
            check("آیکون PNG توپ (goal_ballimg_) برای هر گل رسم شده",
                  len(_img_icons) == len(mom.hook_goal_markers),
                  f"img_icons={len(_img_icons)}")
        else:
            check("آیکون PNG توپ موجود نیست → fallback دایره فعال",
                  all(ln.get_marker() == "o" for ln in ball_icons),
                  f"circle_markers={len(ball_icons)}")
        # ۳) Render Assert نسخه ۷ — قطعی:
        #    len(hook_goal_markers) == number_of_goal_icons
        #                            == number_of_goal_marker_lines
        _n_mk = len(mom.hook_goal_markers)
        _n_lines = len({(ln.get_gid() or "").split("_")[2] for ln in goal_verts})
        check("Render Assert: len(hook_goal_markers) == goal_icons == goal_marker_lines",
              _n_mk == len(ball_icons) == _n_lines,
              f"markers={_n_mk}, icons={len(ball_icons)}, lines={_n_lines}")
        home_above = any(ln.get_ydata()[0] > 0 for ln in ball_icons)
        away_below = any(ln.get_ydata()[0] < 0 for ln in ball_icons)
        check("Home آیکون بالا / Away آیکون پایین", home_above and away_below,
              f"above={home_above}, below={away_below}")
        # ۳) هیچ متنی از گل روی نمودار نوشته نشده (فقط HT مجاز است)
        no_goal_text = all("Goal" not in t.get_text() and "گل" not in t.get_text()
                           for t in ax.texts)
        check("بدون متن اضافهٔ گل روی نمودار", no_goal_text,
              f"texts={[t.get_text() for t in ax.texts]}")
        # ۴) دو خط سرتاسری مرز HT
        def _is_vert_line(ln):
            xd, yd = list(ln.get_xdata()), list(ln.get_ydata())
            return len(xd) == 2 and xd[0] == xd[1]
        ht_lines = [ln for ln in ax.lines if _is_vert_line(ln)
                    and list(ln.get_ydata()) == [0.0, 1.0]]
        check("دو خط عمودی سرتاسری مرز HT", len(ht_lines) == 2, f"ht_lines={len(ht_lines)}")
        if mom.ht_break:
            gxs = sorted(ln.get_xdata()[0] for ln in ht_lines)
            check("موقعیت خطوط HT = ابتدا/انتهای شکاف",
                  abs(gxs[0] - mom.ht_break[0]) < 1.0 and abs(gxs[1] - mom.ht_break[1]) < 1.0,
                  f"lines={[f'{v:.0f}' for v in gxs]} | break={mom.ht_break}")
        # ۵) نسخه ۴: عرض شکاف روی محور = ۵ دقیقه (۳۰۰ ثانیه — یک‌سوم ۹۰۰ قبلی)
        check("عرض شکاف HT روی محور = 300s (۵ دقیقه — یک‌سوم نسخه ۳)",
              mom.ht_break is not None
              and abs((mom.ht_break[1] - mom.ht_break[0]) - cfg.HT_GAP_DISPLAY_SECONDS) < 1e-9
              and abs(cfg.HT_GAP_DISPLAY_SECONDS - 300.0) < 1e-9,
              f"gap={mom.ht_break[1] - mom.ht_break[0]:.0f}s")

    # -------------------------------------------------------------
    # نسخه ۷ — ۹٫۵) زنجیرهٔ قطعی Counter → Hook Marker → Chart:
    #   هر افزایش شمارندهٔ گل (برای هر تیم) باید دقیقاً یک مارکر جدید
    #   بسازد و روی نمودار دقیقاً یک آیکون + یک خط عمودی بگیرد.
    #   هیچ Dedup بین گل‌ها انجام نمی‌شود — حتی دو گل نزدیک هم از یک تیم.
    #   Goal Impact فقط برای Momentum Pulse است و در رسم مارکر نقشی ندارد.
    # -------------------------------------------------------------
    print("\n--- ۹٫۵) نسخه ۷: زنجیرهٔ Counter increment → Hook Marker → Chart ---")

    def _disp5(raw):
        if raw != raw:
            return float('nan')
        return cfg.DISPLAY_RANGE * math.tanh(raw / max(1.0, cfg.DISPLAY_SOFT_SCALE))

    def _render_counts(axx):
        """شمارش قطعی از روی gid: خطوط منطقی گل (هر مارکر = پوسته+مغز) و آیکون‌ها"""
        _lgids = sorted((ln.get_gid() or "") for ln in axx.lines
                        if (ln.get_gid() or "").startswith("goal_line_"))
        _lines = sorted({g.split("_")[2] for g in _lgids})
        _icons = [ln for ln in axx.lines
                  if (ln.get_gid() or "").startswith("goal_ball_")]
        return _lgids, _lines, _icons

    _chain_id = 5000
    try:
        mom2 = MomentumEngine(cfg)
        _t = 0.0
        while _t <= 130.0:
            mom2.update(_t)
            _t += 0.5

        # شبیه‌سازی دقیق _poll_goal_hook + _register_hook_goal (ترتیب حفظ
        # شده: اول add_hook_goal_marker و بعد register_goal_event روی Bus)
        _cnt = {"Home": None, "Away": None}
        _chain_events = []

        def _hook_poll(team, new_v, t, bus_ok=True):
            nonlocal _chain_id
            _dec, _n = GoalHooker.counter_event(_cnt[team], new_v)
            _registered = 0
            if _dec == "GOAL":
                for _ in range(_n):
                    mom2.add_hook_goal_marker(team, t, 1)     # (۱) مارکر مستقیم — اول
                    if bus_ok:                                 # (۲) Event Bus → Impact پالس
                        _chain_id += 1
                        _ev = make_ev(_chain_id, "Goal", team, t)
                        _chain_events.append(_ev)
                        mom2.on_event(_ev)
                    _registered += 1
            _cnt[team] = new_v        # BASELINE/RESET/NOCHANGE فقط آپدیت شمارنده
            return _dec, _registered

        _hook_poll("Home", 0, 5.0)     # BASELINE — اولین خواندن معتبر میزبان
        _hook_poll("Away", 0, 5.0)     # BASELINE — اولین خواندن معتبر میهمان
        check("BASELINE اولین خواندن است — هیچ مارکری نمی‌سازد",
              mom2.hook_goal_marker_count() == 0,
              f"markers={mom2.hook_goal_marker_count()}")
        # --- Counter increment #1 → hook marker #1 ---
        check("Counter increment #1 → hook marker #1",
              _hook_poll("Home", 1, 100.0) == ("GOAL", 1)
              and mom2.hook_goal_marker_count() == 1,
              f"markers={mom2.hook_goal_marker_count()}")
        # --- Counter increment #2 → hook marker #2 ---
        check("Counter increment #2 → hook marker #2",
              _hook_poll("Away", 1, 120.0) == ("GOAL", 1)
              and mom2.hook_goal_marker_count() == 2,
              f"markers={mom2.hook_goal_marker_count()}")
        # --- Counter increment #3 → hook marker #3 (هم‌تیم با #1 و فقط ۶s بعد) ---
        check("Counter increment #3 → hook marker #3 (حتی هم‌تیم و نزدیک)",
              _hook_poll("Home", 2, 126.0) == ("GOAL", 1)
              and mom2.hook_goal_marker_count() == 3,
              f"markers={mom2.hook_goal_marker_count()}")
        _h_imp = mom2.get_impact(_chain_events[0].event_id)
        check("مسیر Bus سالم است: پالس گل با goal_disp_time فریز = goal_time",
              _h_imp is not None and _h_imp.is_goal_pulse
              and abs(_h_imp.goal_disp_time - 100.0) < 1e-9 and _h_imp.goal_half == 1,
              f"disp={_h_imp.goal_disp_time if _h_imp else None}")

        _fig2 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax2 = _fig2.add_subplot(111)
        draw_momentum_chart(_ax2, mom2, cfg, _disp5, goal_glyph_ok=True)
        try:
            _chain_png = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "momentum_v10_hook_chain.png")
            _fig2.savefig(_chain_png, facecolor=_fig2.get_facecolor())
        except Exception:
            pass

        _lgids, _llines, _balls2 = _render_counts(_ax2)
        # Render Assert نسخه ۷ — دقیقاً یک به یک:
        _n_mk2 = mom2.hook_goal_marker_count()
        check("Render Assert: len(hook_goal_markers) == number_of_goal_icons == number_of_goal_marker_lines",
              _n_mk2 == len(_balls2) == len(_llines),
              f"markers={_n_mk2}, icons={len(_balls2)}, lines={len(_llines)}")
        check("هر مارکر دقیقاً پوسته + مغز دارد (بدون Artist اضافه)",
              len(_lgids) == 2 * _n_mk2, f"line_artists={len(_lgids)}")
        _ball_x = sorted(round(list(ln.get_xdata())[0], 1) for ln in _balls2)
        check("هر ۳ گل رسم شدند: 100s و 120s و 126s (بدون Dedup حتی برای دو گل نزدیک هم‌تیم)",
              _ball_x == [100.0, 120.0, 126.0], f"x={_ball_x}")
        _home_balls = [ln for ln in _balls2 if list(ln.get_ydata())[0] > 0]
        _away_balls = [ln for ln in _balls2 if list(ln.get_ydata())[0] < 0]
        check("Home → توپ بالای نمودار (۲ گل) / Away → توپ پایین نمودار (۱ گل)",
              len(_home_balls) == 2 and len(_away_balls) == 1,
              f"home={len(_home_balls)}, away={len(_away_balls)}")

        # --- استقلال دو مسیر: Goal Impact هیچ نقشی در رسم مارکر ندارد ---
        # گل #4 فقط از مسیر Bus (Event + Impact پالس) و «بدون» مارکر هوک
        # ثبت می‌شود → تعداد آیکون/خط مارکر باید بدون تغییر ۳ بماند.
        _chain_id += 1
        mom2.on_event(make_ev(_chain_id, "Goal", "Away", 128.0))
        _n_pulse = sum(1 for imp in mom2.impacts if imp.is_goal_pulse)
        _fig2b = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax2b = _fig2b.add_subplot(111)
        draw_momentum_chart(_ax2b, mom2, cfg, _disp5, goal_glyph_ok=True)
        _lgids_b, _llines_b, _balls2b = _render_counts(_ax2b)
        check("Goal Impact فقط پالس مومنتوم است — آیکون/خط اضافه رسم نمی‌کند",
              len(_balls2b) == 3 and len(_llines_b) == 3
              and mom2.hook_goal_marker_count() == 3,
              f"icons={len(_balls2b)}, lines={len(_llines_b)}, markers={mom2.hook_goal_marker_count()}")
        check("مسیر مستقل Counter → Event → Impact → Pulse سالم است (۴ پالس گل)",
              _n_pulse == 4, f"goal_pulses={_n_pulse}")

        # --- مارکر بدون Event (فرض: خطای Bus) + آفست فریز نیمه دوم ---
        # گل #5 فقط با add_hook_goal_marker ثبت می‌شود (بدون on_event) —
        # باز هم دقیقاً یک مارکر باید رسم شود؛ disp_time فریز لحظهٔ ثبت است.
        mom2.set_half_break(cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
        mom2.add_hook_goal_marker("Away", 2760.0, 2)   # بدون on_event → Bus از کار افتاده
        _t2 = 2700.0
        while _t2 <= 2770.0:
            mom2.update(_t2)
            _t2 += 0.5
        _fig3 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax3 = _fig3.add_subplot(111)
        draw_momentum_chart(_ax3, mom2, cfg, _disp5, goal_glyph_ok=True)
        _lgids_c, _llines_c, _balls3 = _render_counts(_ax3)
        _n_mk3 = mom2.hook_goal_marker_count()
        check("Render Assert پس از گل نیمه دوم: markers == icons == lines",
              _n_mk3 == len(_balls3) == len(_llines_c),
              f"markers={_n_mk3}, icons={len(_balls3)}, lines={len(_llines_c)}")
        _expect = round(2760.0 + mom2.display_offset, 1)
        check("گل نیمه دوم با disp_time فریز درست رسم شد (بعد از خط راست HT)",
              any(abs(round(list(ln.get_xdata())[0], 1) - _expect) < 0.5 for ln in _balls3),
              f"ball_x={[round(list(ln.get_xdata())[0], 1) for ln in _balls3]} | انتظار≈{_expect}")
    except Exception as ex:
        check("زنجیرهٔ Counter → Hook Marker → Chart (۹٫۵)", False, f"exception: {ex}")

    # --- نسخه ۵: تور ایمنی resync_clock (نمودار هرگز نمی‌میرد) ---
    print("\n--- ۹٫۶) نسخه ۵: resync_clock — بازگشت بدون HT/بازی جدید ---")
    try:
        mom3 = MomentumEngine(cfg)
        _t3 = 0.0
        while _t3 <= 600.0:
            mom3.update(_t3)
            _t3 += 0.5
        _n_before3 = len(mom3.history)
        mom3.resync_clock(300.0)   # ساعت عقب‌تر از آخرین نمونه (بازگشت نامشخص)
        check("resync: شکاف اضافی ثبت شد", len(mom3.extra_breaks) == 1
              and sum(1 for s in mom3.history if s["net"] != s["net"]) == 2,
              f"extra={len(mom3.extra_breaks)}")
        _n_guard3 = len(mom3.history)
        mom3.update(301.0)         # بازی از سر گرفته شد → باید فوراً نمونه بگیرد
        check("resync: نمونه‌برداری فوراً از سر می‌گیرد (نمودار نمی‌میرد)",
              len(mom3.history) == _n_guard3 + 1,
              f"Δ={len(mom3.history) - _n_guard3} | _last_t={mom3._last_t:.1f}")
        _last3 = mom3.history[-1]
        check("resync: نمونهٔ جدید بعد از شکاف اضافی است",
              _last3["disp_time"] >= mom3.extra_breaks[-1][1] - 1e-6,
              f"disp={_last3['disp_time']:.1f} ≥ {mom3.extra_breaks[-1][1]:.1f}")
        mom3.resync_clock(900.0)   # ساعت جلوتر → بدون شکاف، فقط نمونه‌برداری فوری
        mom3.update(901.0)
        check("resync: ساعت جلوتر → بدون شکاف اضافی جدید",
              len(mom3.extra_breaks) == 1, f"extra={len(mom3.extra_breaks)}")
    except Exception as ex:
        check("resync_clock (۹٫۶)", False, f"exception: {ex}")

    # -------------------------------------------------------------
    # نسخه ۸ — ۹٫۷) مارکر گل مستقل از history (رفع باگ لایه Render):
    #   در نسخه ۷ اگر len(hist) < 2 بود، draw_momentum_chart زودبرمی‌گشت
    #   و مارکرهای گلِ ثبت‌شده در ابتدای مسابقه هرگز رسم نمی‌شدند.
    #   از نسخه ۸ به بعد: Goal Marker به history وابسته نیست — حتی با
    #   صفر یا یک نمونه، هر آیتم hook_goal_markers دقیقاً یک مارکر
    #   (پوسته + مغز + آیکون توپ) می‌گیرد.
    # -------------------------------------------------------------
    print("\n--- ۹٫۷) نسخه ۸: مارکر گل مستقل از history (len(hist) < 2 نباید مانع مارکر شود) ---")
    try:
        mom4 = MomentumEngine(cfg)
        mom4.update(0.0)                        # حداکثر یک نمونه → len(hist) < 2
        mom4.add_hook_goal_marker("Home", 30.0, 1)
        mom4.add_hook_goal_marker("Away", 45.0, 1)
        check("شرط باگ بازسازی شد: history ناکافی ولی ۲ مارکر هوک ثبت شده",
              len(mom4.history) < 2 and mom4.hook_goal_marker_count() == 2,
              f"hist={len(mom4.history)}, markers={mom4.hook_goal_marker_count()}")

        _fig4 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax4 = _fig4.add_subplot(111)
        draw_momentum_chart(_ax4, mom4, cfg, _disp5, goal_glyph_ok=True)
        _lgids_d, _llines_d, _balls4 = _render_counts(_ax4)
        _n_mk4 = mom4.hook_goal_marker_count()
        check("Render Assert بدون history کافی: markers == icons == lines",
              _n_mk4 == len(_balls4) == len(_llines_d),
              f"markers={_n_mk4}, icons={len(_balls4)}, lines={len(_llines_d)}")
        check("حتی با len(hist)<2 هر مارکر پوسته + مغز دارد",
              len(_lgids_d) == 2 * _n_mk4, f"line_artists={len(_lgids_d)}")
        check("پیام «در انتظار شروع مسابقه...» حفظ شده است",
              any("در انتظار شروع مسابقه" in t.get_text() for t in _ax4.texts),
              f"texts={[t.get_text() for t in _ax4.texts]}")
        _xlim4 = _ax4.get_xlim()
        check("xlim برای پوشش مارکرها گسترش یافت (آخرین گل ۴۵s + ۲۵s)",
              abs(_xlim4[0]) < 1e-9 and _xlim4[1] >= 70.0 - 1e-6,
              f"xlim={_xlim4}")
        _home4 = sum(1 for ln in _balls4 if list(ln.get_ydata())[0] > 0)
        _away4 = sum(1 for ln in _balls4 if list(ln.get_ydata())[0] < 0)
        check("Home بالا / Away پایین — حتی در حالت بدون history کافی",
              _home4 == 1 and _away4 == 1, f"home={_home4}, away={_away4}")

        # حالت مرزی: بدون مارکر و بدون history → رفتار قدیمی (هیچ مارکری)
        mom5 = MomentumEngine(cfg)
        draw_momentum_chart(_ax4, mom5, cfg, _disp5, goal_glyph_ok=True)
        _g_gids5 = [ln.get_gid() for ln in _ax4.lines
                    if (ln.get_gid() or "").startswith("goal_")]
        check("بدون مارکر و بدون history: هیچ آیکون/خط گل رسم نمی‌شود",
              len(_g_gids5) == 0, f"gids={_g_gids5}")
    except Exception as ex:
        check("مارکر گل مستقل از history (۹٫۷)", False, f"exception: {ex}")

    # -------------------------------------------------------------
    # نسخه ۹ — ۹٫۸) رندر فوری بدون هیچ Signal:
    #   * سخت‌ترین حالت: len(hist) == 0 — هیچ منحنی/تیک/Legend ای وجود
    #     ندارد ولی Goal Marker باید دقیقاً از hook_goal_markers رسم شود؛
    #   * ترتیب ثبت = ترتیب رسم (بدون sort/بازآرایی — gid ها به ترتیب
    #     append داده می‌شوند، حتی اگر زمان گل‌ها نامرتب باشد)؛
    #   * مشخصات قطعی رسم: zorder 100/101/102 و clip_on=False.
    # -------------------------------------------------------------
    print("\n--- ۹٫۸) نسخه ۹: رندر فوری بدون Signal — hist=0 + ترتیب ثبت = ترتیب رسم ---")
    try:
        mom6 = MomentumEngine(cfg)
        # هیچ update() ای اجرا نمی‌شود → history پیش‌فرض سازنده (یک نمونه) —
        # یعنی len(hist) < 2: منحنی/تیک/Legend نباید رسم شوند ولی Goal Marker
        # باید دقیقاً از hook_goal_markers رسم شود
        mom6.add_hook_goal_marker("Away", 45.0, 1)   # ثبت اول (زمان جلوتر)
        mom6.add_hook_goal_marker("Home", 30.0, 1)   # ثبت دوم (زمان عقب‌تر — عمداً نامرتب)
        check("شرط سخت بازسازی شد: history ناکافی (<2) ولی ۲ مارکر ثبت شده",
              len(mom6.history) < 2 and mom6.hook_goal_marker_count() == 2,
              f"hist={len(mom6.history)}, markers={mom6.hook_goal_marker_count()}")

        _fig6 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax6 = _fig6.add_subplot(111)
        draw_momentum_chart(_ax6, mom6, cfg, _disp5, goal_glyph_ok=True)
        _lgids_e, _llines_e, _balls6 = _render_counts(_ax6)
        _n_mk6 = mom6.hook_goal_marker_count()
        check("Render Assert با hist=0: markers == icons == lines",
              _n_mk6 == len(_balls6) == len(_llines_e),
              f"markers={_n_mk6}, icons={len(_balls6)}, lines={len(_llines_e)}")

        _b0, _b1 = _balls6[0], _balls6[1]
        _b0x = float(list(_b0.get_xdata())[0]); _b0y = float(list(_b0.get_ydata())[0])
        _b1x = float(list(_b1.get_xdata())[0]); _b1y = float(list(_b1.get_ydata())[0])
        check("ترتیب ثبت = ترتیب رسم: goal_ball_0 = ثبت اول (Away@45 — پایین)",
              _b0.get_gid() == "goal_ball_0" and abs(_b0x - 45.0) < 1e-6 and _b0y < 0,
              f"ball0=({_b0x:.1f},{_b0y:.1f}) gid={_b0.get_gid()}")
        check("goal_ball_1 = ثبت دوم (Home@30 — بالا) بدون sort زمانی",
              _b1.get_gid() == "goal_ball_1" and abs(_b1x - 30.0) < 1e-6 and _b1y > 0,
              f"ball1=({_b1x:.1f},{_b1y:.1f}) gid={_b1.get_gid()}")

        _sh_e = [ln for ln in _ax6.lines if (ln.get_gid() or "") == "goal_line_0_shell"]
        _co_e = [ln for ln in _ax6.lines if (ln.get_gid() or "") == "goal_line_0_core"]
        check("zorder قطعی: shell=100 < core=101 < ball=102",
              bool(_sh_e) and bool(_co_e)
              and _sh_e[0].get_zorder() == 100 and _co_e[0].get_zorder() == 101
              and _b0.get_zorder() == 102,
              f"z={_sh_e[0].get_zorder() if _sh_e else None},"
              f"{_co_e[0].get_zorder() if _co_e else None},{_b0.get_zorder()}")
        check("clip_on=False برای همهٔ Artistهای گل (توپ هیچ‌گاه کلیپ نمی‌شود)",
              all(ln.get_clip_on() is False for ln in (_sh_e[0], _co_e[0], _b0, _b1)),
              f"clip={[ln.get_clip_on() for ln in (_sh_e[0], _co_e[0], _b0, _b1)]}")
        _n_nongoal = len([ln for ln in _ax6.lines
                          if not (ln.get_gid() or "").startswith("goal_")])
        check("با hist=0 هیچ لایهٔ وابسته به history رسم نمی‌شود (فقط خط صفر)",
              _n_nongoal == 1, f"non_goal_lines={_n_nongoal}")
        check("پیام انتظار با hist=0 هم حفظ شده و xlim گل‌ها را پوشش می‌دهد",
              any("در انتظار شروع مسابقه" in t.get_text() for t in _ax6.texts)
              and _ax6.get_xlim()[1] >= 70.0 - 1e-6,
              f"texts={[t.get_text() for t in _ax6.texts]} | xlim={_ax6.get_xlim()}")
    except Exception as ex:
        check("رندر فوری بدون Signal (۹٫۸)", False, f"exception: {ex}")

    print("\n--- ۱۰) نسخه ۴: زنجیرهٔ کامل Shot (Counter → Contact → Tracking) — بدون ثبت هندسی گل ---")

    class _FakeShotEngineIO:
        """شبیه‌ساز GameEngine برای تست ShotEngine بدون بازی واقعی"""
        def __init__(self, traj, players):
            self.traj = list(traj)
            self.i = 0
            self.players = players
        def read_ball(self):
            if self.i >= len(self.traj):
                return self.traj[-1]
            b = self.traj[self.i]
            self.i += 1
            return b
        def read_players(self):
            return self.players

    _players_std = [
        {"seat": 9, "team": "Home", "x": 40.0, "z": 0.0},    # شوت‌زننده
        {"seat": 10, "team": "Home", "x": 36.0, "z": 5.0},
        {"seat": 1, "team": "Away", "x": -50.0, "z": 0.0},   # GK حریف (دور)
        {"seat": 5, "team": "Away", "x": 30.0, "z": 8.0},
    ]
    # --- سناریو ۱: گل (توپ از خط دروازه عبور می‌کند) ---
    _buf = []
    _t0 = time.time()
    for k in range(8):
        _buf.append(SnapshotFrame(
            timestamp=_t0 + k * 0.05, match_time=900.0 + k * 0.05,
            ball=(40.0, 0.0, 0.2), players=_players_std,
            possession="Home", shot_counter=7, pass_counter=30
        ))
    se = ShotEngine()
    traj_goal = [(44.0, 0.0, 0.30), (48.0, 0.0, 0.50), (51.0, 0.0, 0.70),
                 (53.2, 0.0, 0.85), (55.0, 0.0, 0.90), (56.0, 0.0, 0.90)]
    fake_g = _FakeShotEngineIO(traj_goal, _players_std)
    started = se.on_counter_increment(fake_g, list(_buf), time.time(), "Home", 1)
    check("Counter Increment → شروع ره‌گیری", started and se.state == "TRACKING")
    ev_g = None
    for _ in range(12):
        ev_g = se.update_tracking(fake_g)
        if ev_g is not None:
            break
    check("ره‌گیری → ShotEventData نهایی", ev_g is not None)
    if ev_g is not None:
        # --- نسخه ۴: تعیین گل دیگر از مسیر توپ/چارچوب انجام نمی‌شود ---
        check("گل دیگر از هندسه ثبت نمی‌شود (is_goal=False — فقط هوک حافظه)",
              not ev_g.is_goal, f"outcome={ev_g.outcome}")
        check("Outcome میانی خارج از حالت گل است (تا تأیید هوک)",
              "گل" not in ev_g.outcome, f"outcome={ev_g.outcome}")
        check("زمان شوت از فریم تماس (Match Time)", abs(ev_g.match_time - 900.0) < 0.5,
              f"mt={ev_g.match_time:.2f}")
        check("تیم شوت صحیح", ev_g.team == "Home")
    # --- سناریو ۲: مهار (توپ جلوی مدافع می‌ایستد) ---
    _players_save = [
        {"seat": 9, "team": "Home", "x": 40.0, "z": 0.0},
        {"seat": 5, "team": "Away", "x": 46.5, "z": 0.0},    # مدافع سر مسیر
        {"seat": 1, "team": "Away", "x": -50.0, "z": 0.0},
    ]
    _buf2 = []
    for k in range(8):
        _buf2.append(SnapshotFrame(
            timestamp=_t0 + 10.0 + k * 0.05, match_time=1000.0 + k * 0.05,
            ball=(40.0, 0.0, 0.2), players=_players_save,
            possession="Home", shot_counter=8, pass_counter=35
        ))
    se2 = ShotEngine()
    traj_save = [(44.0, 0.0, 0.30), (46.0, 0.0, 0.40), (46.5, 0.0, 0.45),
                 (46.5, 0.0, 0.45), (46.5, 0.0, 0.45), (46.5, 0.0, 0.45)]
    fake_s = _FakeShotEngineIO(traj_save, _players_save)
    se2.on_counter_increment(fake_s, list(_buf2), time.time(), "Home", 1)
    ev_s = None
    for _ in range(12):
        ev_s = se2.update_tracking(fake_s)
        if ev_s is not None:
            break
    check("سناریوی مهار → رخداد بدون گل", ev_s is not None and not ev_s.is_goal
          and ("مهار" in ev_s.outcome or "دفع" in ev_s.outcome),
          f"outcome={ev_s.outcome if ev_s else None}")

    # -------------------------------------------------------------
    # نسخه ۴ — ثبت گل از هوک حافظه: زنجیرهٔ کامل روی Bus واقعی
    # (Shot → register_shot_event → register_goal_event → Momentum)
    # -------------------------------------------------------------
    print("\n--- ۱۰٫۵) نسخه ۴: ثبت گل از هوک حافظه (تنها مسیر گل) ---")
    _ede = EventDetectionEngine(cfg)
    _ede.event_bus.subscribe(mom.on_event)
    if ev_g is not None:
        _shot_ev = _ede.register_shot_event(ev_g)
        _imp_before = mom.get_impact(_shot_ev.event_id)
        _base_before = _imp_before.base_weight if _imp_before else 0.0
        _goal_ev = _ede.register_goal_event("Home", ev_g.match_time + 1.0,
                                            source="memory-hook")
        check("رخداد Goal ⚽ روی Bus منتشر شد",
              any(e.event_type == "Goal ⚽" for e in _ede.events))
        check("گل به آخرین شوت همان تیم لینک شد (پنجرهٔ Match Time)",
              _goal_ev.related_event_ids == [_shot_ev.event_id],
              f"rel={_goal_ev.related_event_ids} | shot={_shot_ev.event_id}")
        check("پرچم is_goal روی رخداد شوت اعمال شد (ارتقای بازگشتی)",
              bool(_shot_ev.metadata.get("is_goal")) and "گل" in str(_shot_ev.metadata.get("outcome", "")))
        _imp_after = mom.get_impact(_shot_ev.event_id)
        check("سهم شوت لینک‌شده به گل تنزیل شد (GOAL_LINKED_SHOT_RATIO)",
              _imp_after is not None
              and abs(_imp_after.base_weight - _base_before * cfg.GOAL_LINKED_SHOT_RATIO) < 1e-6
              and "goal-linked" in (_imp_after.note or ""),
              f"base {_base_before:.2f} → {_imp_after.base_weight if _imp_after else None}")
        _g_imp = mom.get_impact(_goal_ev.event_id)
        check("Impact گل = پالس تأخیری با اوج goal+GOAL_PEAK_DELAY",
              _g_imp is not None and _g_imp.is_goal_pulse
              and abs(_g_imp.peak_time - (_goal_ev.match_time + cfg.GOAL_PEAK_DELAY)) < 1e-9,
              f"peak={_g_imp.peak_time if _g_imp else None}")
        check("وزن پایهٔ گل = GOAL_WEIGHT",
              _g_imp is not None and abs(_g_imp.base_weight - cfg.GOAL_WEIGHT) < 1e-9)

    print("\n--- ۱۱) تصمیم تریگر شمارندهٔ سراسری (رفع باگ بلعیده‌شدن تریگر نسخه ۲) ---")
    _dec = MomentumApp._shot_trigger_decision
    b, e = _dec(None, 5)
    check("اولین خواندن → BASELINE", e == "BASELINE" and b == 5)
    b, e = _dec(5, 5)
    check("بدون تغییر → بدون تریگر", e is None and b == 5)
    b, e = _dec(5, 6)
    check("جهش شمارنده → TRIGGER", e == "TRIGGER" and b == 6)
    b, e = _dec(6, 2)
    check("افت شمارنده → RESET", e == "RESET" and b == 2)
    b, e = _dec(6, None)
    check("خواندن ناموفق → بدون تغییر", e is None and b == 6)
    # سناریوی واقعی بلعیده‌شدن تریگر: شوت → تعویض مالکیت در همان Poll → شمارنده دیر می‌رسد
    # در نسخه ۳ baseline با مالکیت دستکاری نمی‌شود؛ جهش بعدی باید تریگر بدهد
    b1, e1 = _dec(None, 10)              # baseline=10
    b2, e2 = _dec(b1, 10)                # مالکیت عوض شد؛ شمارنده ثابت
    b3, e3 = _dec(b2, 11)                # شمارندهٔ شوت دیر رسید
    check("سناریوی رقابت مالکیت: جهشِ دیرهنگام تریگر می‌دهد",
          e1 == "BASELINE" and e2 is None and e3 == "TRIGGER",
          f"events={e1},{e2},{e3}")

    print("\n--- ۱۱٫۵) نسخه ۴: تصمیم شمارندهٔ گل (GoalHooker.counter_event) ---")
    _gc = GoalHooker.counter_event
    check("None→None → WAIT (هنوز capture نشده)", _gc(None, None) == ("WAIT", 0))
    check("None→2 → BASELINE (اولین خواندن معتبر)", _gc(None, 2) == ("BASELINE", 0))
    check("2→3 → GOAL×1", _gc(2, 3) == ("GOAL", 1))
    check("2→2 → NOCHANGE", _gc(2, 2) == ("NOCHANGE", 0))
    check("3→0 → RESET (بازی جدید، بدون رخداد گل)", _gc(3, 0) == ("RESET", 0))
    check("0→2 → GOAL×2 (دو گل در یک Poll)", _gc(0, 2) == ("GOAL", 2))
    check("سقف ایمنی جهش: 1→9 → حداکثر GOAL×3",
          _gc(1, 9) == ("GOAL", GoalHooker.MAX_GOAL_JUMP))
    check("خواندن ناموفق → NOCHANGE", _gc(2, None) == ("NOCHANGE", 0))

    print("\n--- ۱۱٫۷) نسخه ۶: Cave با Sticky First-Capture (بدون بازی) ---")
    # چیدمان Cave: کد نباید روی slot بیفتد
    check("چیدمان Cave: کد ۴۱ بایتی قبل از slot در 0x60",
          GoalHooker.CODE_OFFSET + GoalHooker.CAVE_CODE_SIZE <= GoalHooker.DATA_SLOT_OFFSET,
          f"0x20+41={GoalHooker.CODE_OFFSET + GoalHooker.CAVE_CODE_SIZE} ≤ 0x{GoalHooker.DATA_SLOT_OFFSET:X}")
    check("slot + 8 بایت داخل تخصیص ۱۲۸ بایتی",
          GoalHooker.DATA_SLOT_OFFSET + 8 <= GoalHooker.CAVE_ALLOC_SIZE)

    # ساخت کد با آدرس‌های فرضی و راستی‌آزمایی فیکس‌آپ‌ها
    # (Cave واقعی با allocate_near_target نزدیک target تخصیص می‌یابد؛
    #  اینجا هم Cave را در فاصلهٔ ۲۵۶MB قرار می‌دهیم تا در بازهٔ rel32 باشد)
    _orig = GoalHooker.ORIG_BYTES
    _target = 0x140000000 + 0x19ECBE2
    _cave = _target + 0x10000000
    _code_start = _cave + GoalHooker.CODE_OFFSET
    _slot = _cave + GoalHooker.DATA_SLOT_OFFSET
    _code = GoalHooker._build_capture_code(_orig, _slot, _target, _code_start)
    check("طول کد Cave = ۴۱ بایت", len(_code) == GoalHooker.CAVE_CODE_SIZE,
          f"len={len(_code)}")
    check("دستور اصلی در ابتدای Cave حفظ شده", bytes(_code[0:7]) == _orig)
    check("push rax/push rcx/pushfq و popfq/pop rcx/pop rax متقارن",
          bytes(_code[7:10]) == b'\x50\x51\x9C' and bytes(_code[33:36]) == b'\x9D\x59\x58')
    # disp32 مقایسه: از انتهای cmp (بایت ۲۱) سنجیده می‌شود
    _disp = struct.unpack('<i', _code[16:20])[0]
    check("disp32 مقایسه به slot اشاره می‌کند", _slot == (_code_start + 21) + _disp,
          f"slot==rip(0x{_code_start + 21:X})+0x{_disp:X}")
    # rel8 پرش jne باید store ده‌بایتی را رد کند (۲۳ → ۳۳)
    check("jne دقیقاً روی store ده‌بایتی می‌پرد",
          _code[21] == 0x75 and _code[22] == (33 - 23) & 0xFF,
          f"jne rel8={_code[22]}")
    # rel32 بازگشت: از انتهای jmp (بایت ۴۱) سنجیده می‌شود
    _rel = struct.unpack('<i', _code[37:41])[0]
    check("jmp به target+7 برمی‌گردد", (_code_start + 41) + _rel == _target + 7,
          f"end+jmp=0x{(_code_start + 41) + _rel:X}")
    # Adopt: پارسر باید همان slot را از کد تولیدی بخواند
    _slot_back = GoalHooker._parse_existing_cave_code(_code, _orig)
    check("پارسر Adopt slot را درست استخراج می‌کند", _slot_back == _slot,
          f"parsed={_slot_back:#x}" if _slot_back else "parsed=None")
    # Cave قدیمی (نسخه ۴/۵ — capture همیشگی) نباید Adopt شود
    _old_cave = bytearray(_orig)
    _old_cave += bytes([0x50, 0x9C, 0x48, 0x89, 0xC8, 0x48, 0xA3]) + struct.pack('<Q', 0xDEAD)
    _old_cave += bytes([0x9D, 0x58, 0xE9]) + struct.pack('<i', 0)
    check("Cave قدیمی نسخهٔ ۴/۵ رد می‌شود (نیاز به ری‌استارت بازی)",
          GoalHooker._parse_existing_cave_code(bytes(_old_cave), _orig) is None)
    check("کد خراب/کوتاه رد می‌شود",
          GoalHooker._parse_existing_cave_code(b'\x90' * 20, _orig) is None)
    # همان پارسر برای هوک میهمان (امضای متفاوت)
    _code_a = GoalHooker._build_capture_code(GoalHooker.AWAY_EXPECTED_BYTES, _slot, _target, _code_start)
    check("پارسر با امضای هوک میهمان هم کار می‌کند",
          GoalHooker._parse_existing_cave_code(_code_a, GoalHooker.AWAY_EXPECTED_BYTES) == _slot)

    print("\n--- ۱۱٫۸) نسخه ۶: سناریوی «گل‌های متعدد» از تغییر شمارنده (بدون بازی) ---")
    # شبیه‌سازی کامل Poll: هر افزایش شمارنده باید یک ثبت جداگانه بدهد
    _seq = [(None, 0), (0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3), (3, 3)]
    _decisions = [GoalHooker.counter_event(p, n)[0] for p, n in _seq]
    check("هر افزایش شمارنده = یک گل جداگانه (۴ گل متوالی ثبت می‌شود)",
          _decisions == ["BASELINE", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE"],
          f"{_decisions}")
    _seq2 = [(None, 0), (0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 1), (1, 2)]
    _dec2 = [GoalHooker.counter_event(p, n)[0] for p, n in _seq2]
    check("ریست موقت شمارنده ثبت گل اشتباه نمی‌سازد و بازی ادامه می‌یابد",
          _dec2 == ["BASELINE", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE", "RESET", "GOAL"],
          f"{_dec2}")

    print("\n--- ۱۱٫۹) نسخه ۱۰: Poll گل مستقل از گیت‌های زمین + تپش [GoalHookPoll] ---")
    # ۱) تپش: اولین فراخوانی همیشه بله؛ داخل بازه خیر؛ بعد از بازه بله
    check("gh_due_heartbeat: اولین فراخوانی (last=None) همیشه due است",
          gh_due_heartbeat(100.0, None) is True)
    check("gh_due_heartbeat: داخل بازهٔ ۵ ثانیه due نیست",
          gh_due_heartbeat(102.0, 100.0) is False
          and gh_due_heartbeat(104.9, 100.0) is False)
    check("gh_due_heartbeat: بعد از گذر بازه due می‌شود",
          gh_due_heartbeat(105.0, 100.0) is True)
    # ۲) انتخاب زمان Poll: ساعت معتبر مقدم؛ وگرنه آخرین زمان core
    check("gh_pick_poll_time: ساعت معتبر این لحظه مقدم است",
          gh_pick_poll_time(45.0, 30.0) == 45.0)
    check("gh_pick_poll_time: ساعت صفر/None → آخرین زمان معتبر core",
          gh_pick_poll_time(0.0, 30.0) == 30.0 and gh_pick_poll_time(None, 30.0) == 30.0)
    check("gh_pick_poll_time: هیچ‌کدام → ۰ (Poll هرگز به‌خاطر ساعت حذف نمی‌شود)",
          gh_pick_poll_time(None, None) == 0.0 and gh_pick_poll_time(0.0, 0.0) == 0.0)
    # ۳) تست ساختاری جایگاه Poll: فراخوانی باید قبل از هر دو early-continue باشد
    _src_all = open(os.path.abspath(__file__), encoding="utf-8").read()
    _i_def = _src_all.find("def worker_loop")
    _i_next = _src_all.find("\n    def ", _i_def + 10)   # اولین متد بعد از worker_loop
    _wl = _src_all[_i_def:_i_next]
    _n_calls = _wl.count("self._poll_goal_hook(")
    _i_call = _wl.find("self._poll_goal_hook(")
    _i_ball_gate = _wl.find("if not ball or not players")
    _i_geom_gate = _wl.find("if not self.geometry_ready")
    check("Poll گل دقیقاً یک فراخوانی در worker_loop دارد (فراخوانی قدیمی حذف شده)",
          _n_calls == 1, f"calls={_n_calls}")
    check("Poll گل قبل از گیت ball/players است (دیگر پشت early-continue پنهان نیست)",
          0 < _i_call < _i_ball_gate,
          f"call={_i_call}, ball_gate={_i_ball_gate}")
    check("Poll گل قبل از گیت geometry_ready است",
          0 < _i_call < _i_geom_gate,
          f"call={_i_call}, geom_gate={_i_geom_gate}")
    check("زمان Poll با gh_pick_poll_time انتخاب می‌شود (fallback زمان core)",
          "gh_pick_poll_time(" in _wl[_i_call:_i_call + 200])
    # ۴) لایهٔ مشاهده‌پذیری: مسیرهای بی‌صدا باید لاگ داشته باشند
    check("هیچ مسیر شکستی در _poll_goal_hook بی‌صدا نیست (لاگ [GoalHookPoll])",
          _src_all.count("[GoalHookPoll]") >= 6,
          f"logs={_src_all.count('[GoalHookPoll]')}")

    print("\n--- ۱۱٫۱۰) نسخه ۱۰: رگرسیون کلیدها — _poll_goal_hook واقعی با fake engine ---")
    # عیب C نسخه ۵ تا ۹: poll() کلید «home/away» کوچک می‌داد و تصمیم
    # «Home/Away» بزرگ می‌خواند → WAIT ابدی. این تست «کل» تابع واقعی را
    # با شکل واقعی خروجی poll() اجرا می‌کند تا این کلاس باگ هرگز برگردد.
    class _FakePollEngine:
        def __init__(self, states):
            self._it = iter(states)
        def read_goal_counters(self):
            return next(self._it)

    # نسخه ۱۰٫۳ — fake app با «متدهای واقعی» _poll_goal_hook و
    # _register_first_hook_goal؛ فقط _register_hook_goal جایگزین می‌شود
    # تا کل زنجیرهٔ تصمیم (شامل First-Capture Goal) واقعاً تست شود.
    class _FakeGHApp:
        _poll_goal_hook = MomentumApp._poll_goal_hook
        _register_first_hook_goal = MomentumApp._register_first_hook_goal
        def __init__(self, states, stub):
            self._gh_diag = {
                "last_hb": None, "notified_no_hook": False, "last_captured": None,
                "last_rcx": None, "last_home": None, "last_away": None,
                "baselined": {"Home": False, "Away": False},
                "n_ok": 0, "n_wait": 0, "n_err": 0, "n_nohook": 0,
            }
            self.goal_counters = {"Home": None, "Away": None}
            self._gh_fc_pending = {"Home": True, "Away": True}
            self._goal_hook_status = {"events": 0}
            self.engine = _FakePollEngine(states)
            self._shot_debug_push = lambda *a, **k: None
            self._register_hook_goal = lambda team, t, _s=stub: _s.append((team, round(t, 1)))

    _reg_stub = []
    _gh_states = [
        {"hooked": True, "captured": False, "secondary": True, "rcx": None, "home": None, "away": None},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 0, "away": 0},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 0, "away": 0},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 1, "away": 0},  # گل!
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 1, "away": 2},  # دو گل میهمان
    ]
    _fake_app = _FakeGHApp(_gh_states, _reg_stub)
    try:
        for _i in range(len(_gh_states)):
            MomentumApp._poll_goal_hook(_fake_app, 600.0 + _i)
        check("کلیدهای poll() خوانده می‌شوند: BASELINE از home=0/away=0 ثبت شد",
              _fake_app.goal_counters["Home"] == 0 and _fake_app.goal_counters["Away"] == 0
              or _fake_app.goal_counters["Home"] == 1,
              f"counters={_fake_app.goal_counters}")
        check("گل میزبان از تغییر RAW (0→1) ثبت شد",
              ("Home", 603.0) in _reg_stub, f"registered={_reg_stub}")
        check("دو گل میهمان پشت‌سرهم ثبت شد (1→2 با MAX_GOAL_JUMP)",
              ("Away", 604.0) in _reg_stub, f"registered={_reg_stub}")
        check("شمارش نهایی: Home=1, Away=2 — دقیقاً برابر RAW",
              _fake_app.goal_counters == {"Home": 1, "Away": 2},
              f"counters={_fake_app.goal_counters}")
        check("شمارش Poll: wait=1 و ok=4 (مسیر WAIT هم دیده می‌شود)",
              _fake_app._gh_diag["n_wait"] == 1 and _fake_app._gh_diag["n_ok"] == 4,
              f"diag=wait:{_fake_app._gh_diag['n_wait']} ok:{_fake_app._gh_diag['n_ok']}")
        # نسخه ۱۰٫۳ — First-Capture در این سناریو (capture روی 0-0) نباید گل ثبت کرده باشد
        check("First-Capture روی 0-0 فقط baseline است (هیچ گل اضافه‌ای ثبت نشد)",
              len(_reg_stub) == 3 and _fake_app._gh_fc_pending == {"Home": False, "Away": False},
              f"registered={_reg_stub} pending={_fake_app._gh_fc_pending}")
    except StopIteration:
        check("توالی fake engine کامل مصرف شد", False, "StopIteration — تعداد Poll کمتر از حالت‌هاست")

    print("\n--- ۱۱٫۱۱) نسخه ۱۰٫۳: First-Capture Goal — گل اول همان لحظهٔ Capture ---")
    # سناریوی کاربر: Goal Hook فقط با اولین اجرای دستور گل Capture می‌کند؛
    # پس اولین Capture ممکن است دقیقاً همزمان با گل اول باشد (Home=1, Away=0).
    # قبلاً: BASELINE → گل اول گم می‌شد. اکنون: همان لحظه گل #1 ثبت می‌شود و
    # baseline داخلی 1 می‌شود؛ سپس 1→2 گل دوم را می‌دهد (بدون دوبار ثبت).
    _fc_states = [
        {"hooked": True, "captured": False, "secondary": True, "rcx": None, "home": None, "away": None},
        # اولین Capture همزمان با گل اول میزبان:
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 1, "away": 0},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 1, "away": 0},
        # گل دوم میزبان — روال عادی Counter Tracking (1→2):
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 2, "away": 0},
    ]
    _fc_stub = []
    _fc_app = _FakeGHApp(_fc_states, _fc_stub)
    try:
        for _i in range(len(_fc_states)):
            MomentumApp._poll_goal_hook(_fc_app, 700.0 + _i)
        check("گل #1 میزبان دقیقاً در لحظهٔ اولین Capture ثبت شد (نه baseline)",
              ("Home", 701.0) in _fc_stub, f"registered={_fc_stub}")
        check("گل #2 میزبان از روال عادی 1→2 ثبت شد",
              ("Home", 703.0) in _fc_stub, f"registered={_fc_stub}")
        check("هیچ دوبار ثبت‌شدنی نیست: دقیقاً ۲ گل برای Home",
              len([r for r in _fc_stub if r[0] == "Home"]) == 2 and len(_fc_stub) == 2,
              f"registered={_fc_stub}")
        check("baseline داخلی بعد از First-Capture همان مقدار RAW است (Home=2)",
              _fc_app.goal_counters == {"Home": 2, "Away": 0},
              f"counters={_fc_app.goal_counters}")
        check("First-Capture فقط یک‌بار مسلح بود (pending بعد از اولین خواندن خاموش شد)",
              _fc_app._gh_fc_pending == {"Home": False, "Away": False},
              f"pending={_fc_app._gh_fc_pending}")
    except StopIteration:
        check("توالی First-Capture کامل مصرف شد", False, "StopIteration")

    # سناریوی معکوس: اولین Capture همزمان با گل اول «میهمان» (Home=0, Away=1)
    _fca_states = [
        {"hooked": True, "captured": False, "secondary": True, "rcx": None, "home": None, "away": None},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22BB, "home": 0, "away": 1},
    ]
    _fca_stub = []
    _fca_app = _FakeGHApp(_fca_states, _fca_stub)
    try:
        for _i in range(len(_fca_states)):
            MomentumApp._poll_goal_hook(_fca_app, 800.0 + _i)
        check("گل #1 میهمان در لحظهٔ Capture ثبت شد (Home=0, Away=1)",
              _fca_stub == [("Away", 801.0)], f"registered={_fca_stub}")
        check("baseline: Home=0 بدون گل، Away=1",
              _fca_app.goal_counters == {"Home": 0, "Away": 1},
              f"counters={_fca_app.goal_counters}")
    except StopIteration:
        check("توالی First-Capture میهمان کامل مصرف شد", False, "StopIteration")

    # سناریوی مقدار اولیه > 1: اختلاف منطقی با سقف MAX_GOAL_JUMP
    _fcc_states = [
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22CC, "home": 2, "away": 0},
    ]
    _fcc_stub = []
    _fcc_app = _FakeGHApp(_fcc_states, _fcc_stub)
    MomentumApp._poll_goal_hook(_fcc_app, 900.0)
    check("مقدار اولیهٔ 2 → هر دو گل (اختلاف منطقی) ثبت شد",
          _fcc_stub == [("Home", 900.0), ("Home", 900.0)],
          f"registered={_fcc_stub}")
    check("baseline بعد از First-Capture چندگانه = مقدار RAW",
          _fcc_app.goal_counters == {"Home": 2, "Away": 0},
          f"counters={_fcc_app.goal_counters}")

    print("\n--- ۱۱٫۱۲) نسخه ۱۰٫۳: Match Lifecycle — قانون سخت HT / بازی جدید / دقیقهٔ ۶ ---")
    # شبیه‌ساز کوچک حلقهٔ تصمیم worker: flag → در اولین PLAYING تصمیم
    def _simulate(seqs, half0=1):
        half = half0
        pending = False
        prev_end = 0.0
        verdicts = []
        prev_t = None
        for t, playing in seqs:
            if should_flag_time_drop(prev_t, t, 5.0):
                pending = True
                prev_end = float(prev_t)
            if playing and pending:
                v = classify_resume_after_drop(prev_end, t, half,
                                               ht_hard_min=2700.0,
                                               ht_resume_lower_slack=30.0,
                                               ht_resume_tolerance=600.0,
                                               new_game_max_start=180.0)
                verdicts.append(v)
                pending = False
                if v == "HT":
                    half = 2
            prev_t = t
        return verdicts, half

    # --- تست اجباری ۱: HT صحیح ---
    _t1 = [(44 * 60 + 58, True), (2700, True), (2734, True), (2734, False),
           (2700, False), (2700, True), (2701, True)]
    _v1, _h1 = _simulate(_t1)
    check("تست ۱ — HT صحیح: دقیقاً یک HT و نیمه دوم از 45:00",
          _v1 == ["HT"] and _h1 == 2, f"verdicts={_v1} half={_h1}")

    # --- تست اجباری ۲: شروع بازی جدید (هیچ HT جدیدی + تصمیم NEW_MATCH) ---
    _t2 = [(5400, False), (0, False), (0, True), (1, True), (2, True), (3, True)]
    _v2, _h2 = _simulate(_t2)
    check("تست ۲ — 90:00→0:00 = NEW_MATCH (هیچ HT ای)",
          _v2 == ["NEW_MATCH"] and not any(v == "HT" for v in _v2),
          f"verdicts={_v2}")
    check("تست ۲ — NEW_MATCH حتی وقتی HT بازی قبل از دست رفته و half هنوز 1 است",
          classify_resume_after_drop(5400.0, 0.0, 1) == "NEW_MATCH")

    # --- تست اجباری ۳: بازی دوم بدون اشتباه HT (0:00..6:00 → 10:00) ---
    _t3 = [(0, True), (60, True), (120, True), (180, True), (240, True),
           (300, True), (360, True), (600, True)]
    _v3, _h3 = _simulate(_t3)
    check("تست ۳ — توالی 0..6:00→10:00: حتی یک HT هم ثبت نشد (HT=0)",
          len(_v3) == 0 and _h3 == 1, f"verdicts={_v3}")
    check("تست ۳ — بازسازی دقیقهٔ ۶: افت کوچک با prev<45:00 هرگز HT نیست",
          classify_resume_after_drop(370.0, 360.0, 1) == "KEPT")
    check("تست ۳ — 03:00→02:59 (ری‌سنک ۱ ثانیه‌ای) اصلاً علامت نمی‌خورد → HT نیست",
          should_flag_time_drop(180.0, 179.0, 5.0) is False)
    check("تست ۳ — جهش عقبرو به پنجرهٔ تایمر≈صفر = NEW_MATCH (نه HT)",
          should_flag_time_drop(180.0, 170.0, 5.0) is True
          and classify_resume_after_drop(180.0, 170.0, 1) == "NEW_MATCH")

    # --- قانون سخت HT: مرزها ---
    check("قانون سخت: prev=45:34، resume=45:00 → HT",
          classify_resume_after_drop(2734.0, 2700.0, 1) == "HT")
    check("قانون سخت: resume=46:20 (داخل تولرانس) → HT",
          classify_resume_after_drop(2780.0, 2780.0, 1) == "HT")
    check("قانون سخت: prev<45:00 (مثلاً 39:00) → هرگز HT",
          classify_resume_after_drop(2340.0, 2700.0, 1) == "KEPT")
    check("قانون سخت: resume وسط بازی (10:00 بعد از 45:40) → HT نیست",
          classify_resume_after_drop(2740.0, 600.0, 1) == "KEPT")
    check("قانون سخت: نیمه دوم (half=2) دیگر هیچ‌وقت HT نمی‌سازد",
          classify_resume_after_drop(5400.0, 2700.0, 2) == "KEPT")
    check("قانون سخت: تایمر≈صفر مقدم بر HT است (90:xx→0:00 با half=1 هم بازی جدید است)",
          classify_resume_after_drop(5400.0, 30.0, 1) == "NEW_MATCH")

    # --- Watchdog بازی جدید (مستقل از فلگ افت زمان) ---
    check("watchdog: مسابقه تا 90:00 دیده شده + PLAYING@0:00 → بازی جدید",
          is_new_match_watchdog(5400.0, 0.0, 180.0, 5.0) is True)
    check("watchdog: مسابقه تا 90:00 + PLAYING@1:40 (پول دیرهنگام) → بازی جدید",
          is_new_match_watchdog(5400.0, 100.0, 180.0, 5.0) is True)
    check("watchdog: شروع عادی مسابقه (تایمر داخل پنجره) → نمی‌زند",
          is_new_match_watchdog(120.0, 100.0, 180.0, 5.0) is False
          and is_new_match_watchdog(183.0, 179.0, 180.0, 5.0) is False)
    check("watchdog: دقیقه ۶ بازی دوم → نمی‌زند",
          is_new_match_watchdog(370.0, 360.0, 180.0, 5.0) is False)

    # --- ساختار: worker_loop واقعاً از State Machine استفاده می‌کند ---
    check("worker_loop از classify_resume_after_drop و watchdog استفاده می‌کند",
          "classify_resume_after_drop(" in _wl and "is_new_match_watchdog(" in _wl)

    # --- ۱۰٫۳ در سطح موتور: ریست بازی جدید همه‌چیز را پاک می‌کند ---
    _mom3 = MomentumEngine(MomentumScoringConfig())
    _mom3.update(120.0)
    _mom3.add_hook_goal_marker("Home", 120.0, 1)
    _mom3.set_half_break(_mom3.cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
    _mom3.reset(0.0)
    check("بازی جدید در سطح موتور: history/marker/HT/offset کاملاً پاک و از 0:00 شروع می‌شود",
          len(_mom3.history) == 1
          and _mom3.hook_goal_marker_count() == 0
          and _mom3.ht_break is None
          and abs(_mom3.display_offset) < 1e-9
          and _mom3.half_number == 1
          and abs(_mom3.history[0]["game_time"]) < 1e-9)

    print("\n--- ۱۱٫۱۳) نسخه ۱۰٫۴: Pipeline Health — re-arm مالکیت / لاگ فایل / هشدار STALE ---")
    # ۱) تصمیم re-arm مالکیت (تابع خالص — Watchdog خودترمیم)
    check("re-arm: poss=None + PLAYING + ساعت جلو + stale کافی + throttle باز → بله",
          possession_rearm_needed(False, "PLAYING", True, 25.0, True) is True)
    check("re-arm: poss معتبر → خیر",
          possession_rearm_needed(True, "PLAYING", True, 999.0, True) is False)
    check("re-arm: غیر PLAYING (Pause/Replay/منو) → خیر",
          possession_rearm_needed(False, "STOP", True, 999.0, True) is False)
    check("re-arm: ساعت مرده (بدون پیشرفت) → خیر",
          possession_rearm_needed(False, "PLAYING", False, 999.0, True) is False)
    check("re-arm: stale ناکافی (زیر آستانه) → خیر",
          possession_rearm_needed(False, "PLAYING", True, 5.0, True) is False)
    check("re-arm: throttle بسته (تلاش اخیر) → خیر",
          possession_rearm_needed(False, "PLAYING", True, 999.0, False) is False)
    # ۲) هشدار شمارندهٔ منجمد (STALE)
    check("STALE: شمارندهٔ پاس 60 ثانیه بدون تغییر در PLAYING → هشدار",
          should_warn_frozen_counter(60.0, "PLAYING") is True)
    check("STALE: در STOP هشدار نمی‌دهیم (انجماد در توقف طبیعی است)",
          should_warn_frozen_counter(600.0, "STOP") is False)
    check("STALE: زیر آستانه → خیر",
          should_warn_frozen_counter(10.0, "PLAYING") is False)
    # ۳) DebugLogger: نوشتن / heartbeat / چرخش فایل
    import tempfile as _tmpmod
    with _tmpmod.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "dbg.txt")
        _d = DebugLogger(_p, enabled=True, heartbeat_sec=0.0, max_bytes=1 << 20)
        _d.event("T", a=1, b="x")
        _d.write("T2", "پیام تست")
        _hb1 = _d.heartbeat_due(100.0)
        _hb2 = _d.heartbeat_due(100.0)
        _d.close()
        _txt = open(_p, encoding="utf-8").read()
        check("DebugLogger: خط رویداد و هدر Session در فایل ثبت شد",
              "[T] a=1 b=x" in _txt and "SESSION" in _txt and "پیام تست" in _txt,
              f"len={len(_txt)}")
        check("DebugLogger: heartbeat با آستانهٔ صفر هر بار due است",
              _hb1 is True and _hb2 is True)
        check("DebugLogger: حالت disabled هیچ فایلی نمی‌سازد",
              not os.path.exists(os.path.join(_td, "off.txt"))
              if not DebugLogger(os.path.join(_td, "off.txt"), enabled=False).enabled else False)
    with _tmpmod.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "dbg2.txt")
        _d = DebugLogger(_p, enabled=True, heartbeat_sec=10.0, max_bytes=400)
        for _i in range(60):
            _d.write("FILL", "x" * 20)
        _d.close()
        check("DebugLogger: چرخش فایل هنگام عبور از max_bytes (نسخهٔ .1 ساخته شد)",
              os.path.exists(_p + ".1"),
              f"main={os.path.getsize(_p) if os.path.exists(_p) else 0}B")
    # ۴) PossessionHooker.reset_capture — پاک‌شدن کش سمت پایتون (بدون h_process هم امن)
    _ph = PossessionHooker()
    _ph.captured_address = 0x12345
    _ph.reset_capture(None)
    check("PossessionHooker.reset_capture: کش captured_address پاک شد",
          _ph.captured_address is None)
    _ph2 = PossessionHooker()
    _ph2.cave_address = 0xBEEF   # h_process=None → فقط کش پایدار پاک می‌شود؛ crash ندارد
    _ph2.captured_address = 0x999
    _ph2.reset_capture(None)
    check("PossessionHooker.reset_capture: با cave_address و h_process=None کرش نمی‌کند",
          _ph2.captured_address is None)
    # ۵) fmt_ptr / freeze_seconds
    check("fmt_ptr: None/0 → '-' و آدرس → hex",
          fmt_ptr(None) == "-" and fmt_ptr(0) == "-" and fmt_ptr(0x1234) == "0x1234")
    check("freeze_seconds: بدون سابقه → -1 و با سابقه → تفاوت",
          freeze_seconds(None, 10.0) == -1.0
          and abs(freeze_seconds(4.0, 10.0) - 6.0) < 1e-9)
    # ۶) ساختار: worker واقعاً health-tick را قبل از گیت‌ها صدا می‌زند و گیت‌شمار دارد
    check("worker_loop نسخه ۱۰٫۴: _pipeline_health_tick قبل از گیت ball/players صدا زده می‌شود",
          _wl.find("_pipeline_health_tick(") != -1
          and _wl.find("_pipeline_health_tick(") < _wl.find('if not ball or not players:'))
    check("worker_loop نسخه ۱۰٫۴: شمارندهٔ گیت ball_players/not_playing/pass_trig/shot_trig موجود است",
          '_gate_counts["ball_players"]' in _wl and '_gate_counts["not_playing"]' in _wl
          and '_gate_counts["pass_trig"]' in _wl and '_gate_counts["shot_trig"]' in _wl)
    import inspect as _inspect
    _pr_src = _inspect.getsource(MomentumApp._perform_reset)
    # نسخهٔ ۱۰٫۱۸ — re-arm مالکیت حالا از مسیر هوشمند rearm_possession_capture
    # می‌گذرد (خودِ آن reset_possession_capture را صدا می‌زند)
    check("perform_reset نسخه ۱۰٫۴: capture مالکیت هم دوباره مسلح می‌شود",
          ("rearm_possession_capture" in _pr_src
           or "reset_possession_capture" in _pr_src)
          and "MATCH_RESET" in _pr_src)

    print("\n--- ۱۲) هموارسازی قطعه‌بندی‌شده (NaN شکاف HT پخش نمی‌شود) ---")
    _series = [0.0, 0.0, 5.0, 0.0, 0.0, float('nan'), float('nan'), 0.0, 0.0, 7.0, 0.0, 0.0]
    _sm = gaussian_smooth(_series, 1.0)
    _nan_idx = [i for i, v in enumerate(_sm) if v != v]
    check("NaN ها فقط در جای خودشان می‌مانند", _nan_idx == [5, 6], f"nan_idx={_nan_idx}")
    check("قطعهٔ اول تا لبهٔ شکاف مقدار متناهی دارد",
          all(_sm[i] == _sm[i] for i in range(5)) and abs(_sm[4]) < 5.0)
    check("قطعهٔ دوم تا لبهٔ شکاف مقدار متناهی دارد",
          all(_sm[i] == _sm[i] for i in range(7, 12)))

    # =============================================================
    print("\n--- ۱۳) نرمی زنگوله‌ای (نسخهٔ ۱۰٫۲۷ — هم‌ارز تنظیم 2017) ---")
    # =============================================================
    check("ثابت‌ها: GAUSSIAN_SIGMA=20 و TV_SMOOTH_SIGMA_SEC=55 (تنظیم 2017)",
          cfg.GAUSSIAN_SIGMA == 20.0 and TV_SMOOTH_SIGMA_SEC == 55.0,
          f"sigma={cfg.GAUSSIAN_SIGMA}, tv_sigma={TV_SMOOTH_SIGMA_SEC}")
    # قلهٔ هموارشدهٔ یک تکانه با سیگمای بزرگ‌تر: اوجِ کمتر + شانهٔ پهن‌تر
    _imp = [0.0] * 200 + [100.0] + [0.0] * 199
    _sm20 = gaussian_smooth(_imp, 40.0)   # 20s / eff_dt=0.5s → 40 نمونه
    _sm16 = gaussian_smooth(_imp, 32.0)   # 16s (مقدار قبلی)
    check("زنگوله‌ای: اوج قله با σ=20s از σ=16s پخش‌تر/کمتر است",
          max(_sm20) < max(_sm16),
          f"peak20={max(_sm20):.4f} < peak16={max(_sm16):.4f}")
    check("زنگوله‌ای: شانهٔ قله با σ=20s پهن‌تر است (d=80 نمونه)",
          _sm20[280] > _sm16[280],
          f"sm20[280]={_sm20[280]:.4f} > sm16[280]={_sm16[280]:.4f}")
    check("زنگوله‌ای: هیچ نمونه‌ای منفی/NaN نمی‌شود",
          all(v == v and v >= 0.0 for v in _sm20))

    # =============================================================
    print("\n--- Test RC: کارت قرمز — پوینتر ۳ سطحی + انتساب z=40 + رندر (نسخهٔ ۱۰٫۲۷) ---")
    # =============================================================
    # سناریوهای منطق با «متدهای REAL» MomentumApp روی هستهٔ واقعی
    # Momentum (فقط engine/دیباگ فیک) — همان سبک تست ۱۱٫۱۰.

    class _FakeRCEngine:
        def __init__(self, value=None):
            self.value = value

        def read_red_card_counter(self):
            return self.value

    class _FakeRCApp:
        """اپ کوچک با متدهای واقعی کارت قرمز روی MomentumEngine واقعی."""
        _poll_red_card = MomentumApp._poll_red_card
        _register_hook_red_card = MomentumApp._register_hook_red_card

        def __init__(self, engine):
            self.engine = engine
            self.momentum = MomentumEngine(MomentumScoringConfig())
            self.config = MomentumScoringConfig()
            self.half_number = 1
            self._tv_dirty = False
            self._rc_state = {"baseline": None, "pending": [],
                              "exiles": set()}
            self._rc_diag = {"n_ok": 0, "n_none": 0, "n_err": 0,
                             "n_cards": 0, "n_attr": 0, "n_timeout": 0}

        def _shot_debug_push(self, *a, **k):
            pass

    # --- RC1: زنجیرهٔ پوینتر ۳ سطحی (حافظهٔ فیک — پچ موقت safe_read) ---
    _g = globals()
    _orig_safe_read = _g["safe_read"]
    _BASE = 0x140000000
    _RC_P1 = 0x250000100
    _RC_P2 = 0x250000200
    _rc_mem = {
        _BASE + GameEngine.RED_CARD_PTR_OFFSET: struct.pack("<Q", _RC_P1),
        _RC_P1 + 0x350: struct.pack("<Q", _RC_P2),
        _RC_P2 + 0x4E0: bytes([0]),
    }

    def _fake_safe_read_rc(hp, addr, size):
        b = _rc_mem.get(int(addr))
        if b is None or len(b) < size:
            return None
        return b[:size]

    _g["safe_read"] = _fake_safe_read_rc
    try:
        engRC = GameEngine()
        engRC.is_ready = True
        engRC.base_addr = _BASE
        engRC.h_process = 0
        check("RC1: خواندن زنجیرهٔ کارت قرمز (base+0x36F3F88→+350→+4E0)",
              engRC.read_red_card_counter() == 0,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P2 + 0x4E0] = bytes([2])
        check("RC1b: افزایش شمارنده ۱ بایتی از زنجیره خوانده می‌شود",
              engRC.read_red_card_counter() == 2,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P2 + 0x4E0] = bytes([255])
        check("RC1c: مقدار ۲۵۵ (سقف u8) معتبر خوانده می‌شود",
              engRC.read_red_card_counter() == 255,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P1 + 0x350] = struct.pack("<Q", 0)
        _rc_mem[_RC_P2 + 0x4E0] = bytes([2])
        check("RC1d: زنجیرهٔ شکسته (پوینتر مرده) → None",
              engRC.read_red_card_counter() is None)
        _rc_mem[_BASE + GameEngine.RED_CARD_PTR_OFFSET] = struct.pack("<Q", 0x10)
        check("RC1e: پوینتر پایهٔ نامعتبر (<0x10000) → None",
              engRC.read_red_card_counter() is None)
        engRC.is_ready = False
        check("RC1f: بدون اتصال (is_ready=False) → None",
              engRC.read_red_card_counter() is None)
        engRC.is_ready = True
    finally:
        _g["safe_read"] = _orig_safe_read

    # --- RC2: baseline + افزایش → pending با زمان/نیمهٔ فریزشده ---
    fake_eng = _FakeRCEngine(2)
    fa = _FakeRCApp(fake_eng)
    fa.momentum.display_offset = 300.0      # شبیه‌سازی آفست نمایشی
    fa._poll_red_card(600.0, [])
    check("RC2: اولین خواندن = BASELINE (بدون کارت)",
          fa._rc_state["baseline"] == 2
          and not fa._rc_state["pending"]
          and fa.momentum.red_card_marker_count() == 0,
          f"baseline={fa._rc_state['baseline']}")
    fake_eng.value = 3
    fa._poll_red_card(610.0, [])
    _pd0 = fa._rc_state["pending"][0] if fa._rc_state["pending"] else {}
    check("RC2b: افزایش 2→3 یک کارت در انتظار انتساب می‌سازد",
          len(fa._rc_state["pending"]) == 1,
          f"pending={len(fa._rc_state['pending'])}")
    check("RC2c: زمان/نیمه/disp لحظهٔ صدور فریز می‌شود",
          _pd0.get("issued_t") == 610.0
          and _pd0.get("issued_disp") == 910.0
          and _pd0.get("issued_half") == 1,
          f"pd={_pd0}")

    # --- RC3: انتساب — بازیکن میزبان به z=40 می‌رود ---
    players = [{"seat": i,
                "team": ("Home" if i <= 11 else "Away"),
                "x": -10.0, "z": 0.0}
               for i in range(1, 23)]
    players[4]["z"] = 40.3                  # بازیکن میزبان اخراج شد
    fa._poll_red_card(618.0, players)
    _mk0 = fa.momentum.get_hook_red_card_markers()
    check("RC3: کارت به تیم میزبان منتسب و مارکر ثبت شد",
          len(_mk0) == 1 and _mk0[0]["team"] == "Home",
          f"markers={_mk0}")
    check("RC3b: زمان مارکر = لحظهٔ صدور (نه لحظهٔ تشخیص)",
          _mk0[0]["game_time"] == 610.0
          and _mk0[0]["disp_time"] == 910.0,
          f"gt={_mk0[0]['game_time']} disp={_mk0[0]['disp_time']}")
    check("RC3c: seat تبعیدی ثبت شد (کاندید کارت بعدی نیست)",
          5 in fa._rc_state["exiles"],
          f"exiles={sorted(fa._rc_state['exiles'])}")
    check("RC3d: pending خالی شد + _tv_dirty برای رندر فوری",
          not fa._rc_state["pending"] and fa._tv_dirty)
    fa.momentum.display_offset = 999.0       # آفست بعد از صدور عوض شد
    check("RC3e: disp_time فریزشده باقی می‌ماند (آفست جدید بی‌اثر)",
          fa.momentum.get_hook_red_card_markers()[0]["disp_time"] == 910.0)

    # --- RC4: کارت دوم — مهمان؛ اخراجی قدیمی کاندید نیست ---
    fake_eng.value = 4
    fa._poll_red_card(1200.0, players)      # فقط اخراجی قدیمی در z=40
    check("RC4: اخراجی قدیمی (seat 5) انتساب نمی‌شود",
          len(fa._rc_state["pending"]) == 1,
          f"pending={len(fa._rc_state['pending'])}")
    players[15]["z"] = 39.8                 # بازیکن مهمان اخراج شد
    fa._poll_red_card(1212.0, players)
    _mk1 = fa.momentum.get_hook_red_card_markers()
    check("RC4b: کارت دوم به مهمان منتسب شد (زمان صدور خودش)",
          len(_mk1) == 2 and _mk1[1]["team"] == "Away"
          and _mk1[1]["game_time"] == 1200.0,
          f"markers={[(m['team'], m['game_time']) for m in _mk1]}")

    # --- RC5: تلورانس z ---
    fa5 = _FakeRCApp(_FakeRCEngine(4))
    fa5._poll_red_card(2000.0, [])          # baseline = 4
    fa5.engine.value = 5
    fa5._poll_red_card(2005.0, [])
    p_bad = [{"seat": 30, "team": "Away", "x": 0.0, "z": 34.5},
             {"seat": 31, "team": "Home", "x": 0.0, "z": 45.6}]
    fa5._poll_red_card(2010.0, p_bad)
    check("RC5: z خارج از تلورانس (34.5 / 45.6) کاندید نیست",
          len(fa5._rc_state["pending"]) == 1,
          f"pending={len(fa5._rc_state['pending'])}")
    p_ok = [{"seat": 32, "team": "Home", "x": 0.0, "z": 36.0}]
    fa5._poll_red_card(2015.0, p_ok)
    check("RC5b: z=36 (مرز تلورانس) کاندید است",
          len(fa5.momentum.get_hook_red_card_markers()) == 1
          and fa5.momentum.get_hook_red_card_markers()[0]["team"] == "Home",
          f"markers={fa5.momentum.get_hook_red_card_markers()}")

    # --- RC6: مهلت انتساب ---
    fa6 = _FakeRCApp(_FakeRCEngine(5))
    fa6._poll_red_card(3000.0, [])          # baseline = 5
    fa6.engine.value = 6
    fa6._poll_red_card(3010.0, [])
    check("RC6: کارت صادرشده در انتظار می‌ماند",
          len(fa6._rc_state["pending"]) == 1)
    fa6._poll_red_card(3010.0 + RC_WATCH_WINDOW_S + 1.0, [])
    check("RC6b: مهلت زمان بازی → کارت بدون مارکر رها شد",
          not fa6._rc_state["pending"]
          and fa6._rc_diag["n_timeout"] == 1
          and fa6.momentum.red_card_marker_count() == 0,
          f"timeout={fa6._rc_diag['n_timeout']}")

    # --- RC7: افت گذرای شمارنده ---
    fa7 = _FakeRCApp(_FakeRCEngine(6))
    fa7._poll_red_card(4000.0, [])          # baseline = 6
    fa7.engine.value = 3                    # افت میانهٔ بازی
    fa7._poll_red_card(4010.0, [])
    check("RC7: افت میانهٔ بازی نادیده گرفته می‌شود (baseline حفظ)",
          fa7._rc_state["baseline"] == 6,
          f"baseline={fa7._rc_state['baseline']}")
    fa7.engine.value = 7
    fa7._poll_red_card(4020.0, [])
    check("RC7b: افزایش بعدی از baseline حفظشده یک کارت می‌سازد",
          len(fa7._rc_state["pending"]) == 1,
          f"pending={len(fa7._rc_state['pending'])}")

    # --- RC8: ریست در پنجرهٔ بازی جدید ---
    fa8 = _FakeRCApp(_FakeRCEngine(7))
    fa8._poll_red_card(5000.0, [])          # baseline = 7
    fa8.engine.value = 0
    fa8._poll_red_card(10.0, [])            # t=10 < NEW_GAME_MAX_START
    check("RC8: افت در پنجرهٔ بازی جدید ریست پذیرفته می‌شود",
          fa8._rc_state["baseline"] == 0,
          f"baseline={fa8._rc_state['baseline']}")

    # --- RC9: جهش غیرعادی ---
    fa9 = _FakeRCApp(_FakeRCEngine(3))
    fa9._poll_red_card(6000.0, [])          # baseline = 3
    fa9.engine.value = 50                   # جهش 47 > RC_MAX_JUMP
    fa9._poll_red_card(6010.0, [])
    check("RC9: جهش > RC_MAX_JUMP ری‌بیس‌لاین بدون ثبت کارت",
          fa9._rc_state["baseline"] == 50
          and not fa9._rc_state["pending"]
          and fa9.momentum.red_card_marker_count() == 0,
          f"baseline={fa9._rc_state['baseline']}")

    # --- RC10: ریست مسابقه مارکرها را پاک می‌کند ---
    faR = _FakeRCApp(_FakeRCEngine(0))
    faR.momentum.add_hook_red_card_marker("Away", 100.0, 1)
    faR.momentum.add_hook_goal_marker("Home", 200.0, 1)
    faR.momentum.reset(0.0)
    check("RC10: momentum.reset مارکرهای کارت و گل را پاک می‌کند",
          faR.momentum.red_card_marker_count() == 0
          and faR.momentum.hook_goal_marker_count() == 0)

    # --- RC11: آیکون کارت (طراحی در کد) ---
    ic = build_red_card_icon()
    check("RC11: آیکون کارت RGBA ساخته می‌شود",
          ic is not None and ic.ndim == 3 and ic.shape[2] == 4,
          f"shape={None if ic is None else ic.shape}")
    if ic is not None:
        _ih, _iw = ic.shape[:2]
        check("RC11b: نسبت ابعاد عین نمونهٔ کاربر (≈0.628)",
              abs(_iw / _ih - RED_CARD_ASPECT_W_H) < 0.02,
              f"{_iw}x{_ih} → {_iw / _ih:.3f}")
        _c = ic[_ih // 2, _iw // 2]
        check("RC11c: مرکز قرمز پررنگ و مات",
              _c[0] > 0.85 and _c[1] < 0.15 and _c[2] < 0.2
              and _c[3] > 0.98,
              f"rgba={_c.round(3)}")
        check("RC11d: گوشه‌ها شفاف (کارت گوشه‌گرد بدون حاشیه)",
              ic[1, 1, 3] < 0.55 and ic[-2, -2, 3] < 0.55,
              f"a_tl={ic[1, 1, 3]:.2f} a_br={ic[-2, -2, 3]:.2f}")
        _top = ic[int(_ih * 0.18), _iw // 2]
        _bot = ic[int(_ih * 0.82), _iw // 2]
        check("RC11e: گرادیان عمودی (بالا روشن‌تر از پایین)",
              _top[0] > _bot[0] + 0.02,
              f"top={_top[0]:.3f} bot={_bot[0]:.3f}")

    # --- RC12-RC14: رندر سه‌مسیره (نمودار اصلی + TV + صحنهٔ GPU) ---
    momTV = MomentumEngine(MomentumScoringConfig())
    for _t in range(0, 2701, 30):
        momTV.history.append({"game_time": float(_t),
                              "disp_time": float(_t),
                              "home": 20.0, "away": -10.0, "net": 30.0,
                              "wall": 1000.0 + _t, "phase": "HALF_2"})
    momTV.add_hook_goal_marker("Home", 1200.0, 1)
    momTV.add_hook_red_card_marker("Away", 1800.0, 1)
    momTV.add_hook_red_card_marker("Home", 2400.0, 1)

    _orig_bg_load = _g["tv_load_background"]
    _arr = np.zeros((978, 1608, 4), dtype=float)
    _arr[..., 3] = 1.0
    _fake_bg = {"arr": _arr,
                "geom": dict(TV_FALLBACK_GEOM["half"]),
                "W": 1608, "H": 978}
    _g["tv_load_background"] = lambda kind: _fake_bg
    try:
        from matplotlib.backends.backend_agg \
            import FigureCanvasAgg as _AggRC
        from matplotlib.figure import Figure as _FigRC

        def _gid_of(a):
            try:
                return str(a.get_gid() or "")
            except Exception:
                return ""

        # --- TV ---
        _fig = _FigRC(figsize=(16.08, 9.78), dpi=100)
        _AggRC(_fig)
        _ax = _fig.add_subplot(111)
        _info = draw_tv_momentum(_ax, momTV, MomentumScoringConfig(),
                                 None, "half")
        _arts = list(_ax.lines) + list(_ax.images) + list(_ax.artists)
        _rc_imgs = [a for a in _arts
                    if _gid_of(a).startswith("tv_rc_cardimg_")]
        _rc_anchors = [a for a in _arts
                       if _gid_of(a).startswith("tv_rc_card_")]
        _rc_cores = [a for a in _arts
                     if _gid_of(a).startswith("tv_rc_line_")
                     and _gid_of(a).endswith("_core")]
        _gl_icons = [a for a in _arts
                     if _gid_of(a).startswith("tv_goal_ballimg_")]
        check("RC12: TV — دو آیکون کارت رندر شد (مهمان + میزبان)",
              len(_rc_imgs) == 2 and len(_rc_anchors) == 2,
              f"icons={len(_rc_imgs)} anchors={len(_rc_anchors)}")
        check("RC12b: TV — دو خط کارت (core) با همان استایل گل",
              len(_rc_cores) == 2, f"cores={len(_rc_cores)}")
        check("RC12c: TV — مارکر گل دست‌نخورده ماند",
              len(_gl_icons) == 1 and _info.get("balls") == 1,
              f"balls={_info.get('balls')}")
        _rc_y = {}
        for a in _rc_imgs:
            _e = a.get_extent()                # (l, r, bottom, top)
            _rc_y[_gid_of(a)] = (_e[2] + _e[3]) / 2.0
        _away_y = next((v for k, v in _rc_y.items()
                        if k.endswith("_0")), None)
        _home_y = next((v for k, v in _rc_y.items()
                        if k.endswith("_1")), None)
        check("RC12d: TV — کارت مهمان زیر خط صفر (y>zero_y=486)",
              _away_y is not None and _away_y > 486.0,
              f"away_y={_away_y}")
        check("RC12e: TV — کارت میزبان بالای خط صفر (y<zero_y=486)",
              _home_y is not None and _home_y < 486.0,
              f"home_y={_home_y}")
        check("RC12f: TV — شمارنده‌های info کارت پر شدند",
              _info.get("rc_cards") == 2 and _info.get("rc_lines") == 2,
              f"rc_cards={_info.get('rc_cards')} "
              f"rc_lines={_info.get('rc_lines')}")

        # --- نمودار اصلی ---
        _fig2 = _FigRC(figsize=(11.5, 5.2), dpi=100)
        _AggRC(_fig2)
        _ax2 = _fig2.add_subplot(111)
        draw_momentum_chart(_ax2, momTV, MomentumScoringConfig(),
                            lambda v: v)
        _arts2 = list(_ax2.lines) + list(_ax2.artists)
        _rc_img2 = [a for a in _arts2
                    if _gid_of(a).startswith("rc_cardimg_")]
        _rc_anchor2 = [a for a in _arts2
                       if _gid_of(a).startswith("rc_card_")]
        _rc_core2 = [a for a in _arts2
                     if _gid_of(a).startswith("rc_line_")
                     and _gid_of(a).endswith("_core")]
        check("RC13: نمودار اصلی — دو آیکون کارت (AnnotationBbox)",
              len(_rc_img2) == 2 and len(_rc_anchor2) == 2,
              f"icons={len(_rc_img2)} anchors={len(_rc_anchor2)}")
        check("RC13b: نمودار اصلی — دو خط کارت",
              len(_rc_core2) == 2, f"cores={len(_rc_core2)}")
        _home_ln = [a for a in _rc_anchor2
                    if _gid_of(a) == "rc_card_1"]
        _away_ln = [a for a in _rc_anchor2
                    if _gid_of(a) == "rc_card_0"]
        check("RC13c: نمودار اصلی — میزبان بالا (y>0) / مهمان پایین (y<0)",
              _home_ln and _away_ln
              and _home_ln[0].get_ydata()[0] > 0
              and _away_ln[0].get_ydata()[0] < 0,
              f"home_y={_home_ln[0].get_ydata()[0] if _home_ln else None} "
              f"away_y={_away_ln[0].get_ydata()[0] if _away_ln else None}")

        # --- صحنهٔ GPU ---
        _scene = build_gpu_graph_scene(momTV, MomentumScoringConfig(),
                                       "half", "#e63946", "#f5f5f5")
        check("RC14: صحنهٔ GPU ساخته می‌شود", isinstance(_scene, dict),
              f"scene={'OK' if isinstance(_scene, dict) else None}")
        if isinstance(_scene, dict):
            _ic_shape = build_red_card_icon().shape[:2]
            _rc_tex = [it for it in _scene["items"]
                       if it.get("kind") == "tex"
                       and tuple(it.get("size", ()))
                       == (int(_ic_shape[1]), int(_ic_shape[0]))]
            check("RC14b: صحنهٔ GPU — دو تکستچر کارت (اندازهٔ آیکون)",
                  len(_rc_tex) == 2,
                  f"rc_tex={len(_rc_tex)}")
            _rc_edges = [it for it in _scene["items"]
                         if it.get("kind") == "edge"
                         and it.get("color4") == (1.0, 1.0, 1.0, 1.0)]
            check("RC14c: صحنهٔ GPU — خط‌های هستهٔ سفید کارت موجود",
                  len(_rc_edges) >= 4,
                  f"white_edges={len(_rc_edges)}")
    finally:
        _g["tv_load_background"] = _orig_bg_load

    # --- RC15: آرشیو ---
    momAR = MomentumEngine(MomentumScoringConfig())
    momAR.history.append({"game_time": 0.0, "disp_time": 0.0,
                          "home": 0.0, "away": 0.0, "net": 0.0,
                          "wall": 1.0, "phase": None})
    momAR.add_hook_red_card_marker("Away", 2520.0, 2,
                                   disp_time=2820.0)
    _data = collect_match_events(momAR)
    check("RC15: آرشیو شامل red_card_markers است",
          len(_data.get("red_card_markers") or []) == 1,
          f"n={len(_data.get('red_card_markers') or [])}")
    check("RC15b: counts.red_card_markers درست است",
          (_data.get("counts") or {}).get("red_card_markers") == 1)
    _arch = _ArchiveEngine(_data)
    check("RC15c: موتور شبهٔ آرشیو مارکرهای کارت را بازمی‌سازد",
          len(_arch.red_card_markers) == 1
          and _arch.red_card_markers[0]["team"] == "Away")
    _arch2 = _ArchiveEngine({"history": momAR.history})   # آرشیو قدیمی
    check("RC15d: آرشیو قدیمی بدون red_card_markers هم سازگار است",
          _arch2.red_card_markers == [])

    # --- RC16: یکپارچگی Worker/Reset (بازرسی سورس — سبک تست ۱۱٫۱۳) ---
    import inspect as _inspect
    _src_wl_rc = _inspect.getsource(MomentumApp.worker_loop)
    _i_pl = _src_wl_rc.find("players = self.engine.read_players()")
    _i_rc = _src_wl_rc.find("self._poll_red_card(")
    check("RC16: worker بعد از خواندن بازیکنان poll کارت را صدا می‌زند",
          0 < _i_pl < _i_rc, f"players@{_i_pl} rc@{_i_rc}")
    _i_gate = _src_wl_rc.find('if not ball or not players:')
    check("RC16b: poll کارت قبل از گیت ball/players اجرا می‌شود",
          0 < _i_rc < _i_gate, f"rc@{_i_rc} gate@{_i_gate}")
    _src_pr_rc = _inspect.getsource(MomentumApp._perform_reset)
    check("RC16c: _perform_reset وضعیت کارت را پاک می‌کند",
          "_rc_state" in _src_pr_rc)
    _src_ms = _inspect.getsource(MomentumApp.read_match_state) \
        if hasattr(MomentumApp, "read_match_state") else ""
    check("RC16d: تشخیص PLAYING/STOP دست‌نخورده (متد قدیمی سر جایش)",
          "MATCH_STATE_OFFSET" in _inspect.getsource(GameEngine.read_match_state)
          and "128" in _inspect.getsource(GameEngine.read_match_state),
          "read_match_state = بایت وضعیت 128/129")

    # --- Test TS: نمایش تراکنشی اسنپ‌شات (v10.28 — پورت v1.3 از 2017) ---
    print("\n--- Test TS: چرخهٔ عمر تراکنشی نمایش (SHOW → confirm/retry) ---")
    _ts_settings = dict(TV_SNAP_DEFAULTS)
    _ts_settings.update({"h1_enabled": True, "h1_minute": 43,
                         "h2_enabled": True, "h2_minute": 85,
                         "et_enabled": False, "et_minute": 116,
                         "end_enabled": True,
                         "show_seconds": 5, "end_seconds": 5,
                         "permanent_save": False, "timestamp": False})
    _ts = TVSnapshotEngine(_ts_settings)
    _ts.reset_match(1000.0)

    # TS1: حالت اولیه — ساختار تراکنشی
    check("TS1: mid state تراکنشی است (show_state/retries/last_fail)",
          all(set(("show_state", "retries", "last_fail",
                   "show_req_wall", "retry_after_wall")) <= set(_ts.mid[k])
              for k in _ts.mid)
          and _ts.mid["h1"]["show_state"] is None
          and _ts.mid["h1"]["shown"] is False)
    check("TS1b: end state با pend/fails شروع می‌شود",
          all(_ts.end[k].get("pend") is None and _ts.end[k].get("fails") == 0
              for k in _ts.end))

    # TS2: رسیدن به دقیقهٔ هدف فقط «درخواست» می‌دهد — مصرف نشده
    _acts = _ts.tick(43 * 60.0, "PLAYING", 1, 1001.0)
    check("TS2: show در دقیقهٔ هدف صادر و «درخواست» ثبت می‌شود",
          ("show", "h1") in _acts
          and _ts.mid["h1"]["show_state"] == "requested"
          and _ts.mid["h1"]["shown"] is False)
    _acts2 = _ts.tick(43 * 60.0 + 5.0, "PLAYING", 1, 1002.0)
    check("TS2b: بدون تأیید، تیک بعدی show تازه نمی‌دهد",
          ("show", "h1") not in _acts2
          and _ts.mid["h1"]["show_state"] == "requested")

    # TS3: مهلت تأیید → failed → تلاش مجدد خودکار پس از Backoff
    _acts3 = _ts.tick(43 * 60.0 + 6.0, "PLAYING", 1,
                      1001.0 + TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0)
    check("TS3a: مهلت تأیید گذشت → failed با علت confirm-timeout",
          ("show", "h1") not in _acts3
          and _ts.mid["h1"]["show_state"] == "failed"
          and _ts.mid["h1"]["last_fail"] == "confirm-timeout")
    _acts3b = _ts.tick(43 * 60.0 + 6.5, "PLAYING", 1,
                       1001.0 + TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0
                       + TV_SNAP_SHOW_RETRY_BACKOFF_SEC + 1.0)
    check("TS3b: پس از Backoff تلاش مجدد صادر می‌شود",
          ("show", "h1") in _acts3b
          and _ts.mid["h1"]["retries"] == 1
          and _ts.mid["h1"]["show_state"] == "requested")

    # TS4: fail_show صریح → Backoff → تلاش مجدد
    check("TS4a: fail_show درخواست را شکست‌خورده می‌کند",
          _ts.fail_show("h1", 2000.0, "test-fail") is True
          and _ts.mid["h1"]["show_state"] == "failed"
          and _ts.mid["h1"]["last_fail"] == "test-fail")
    _acts4 = _ts.tick(43 * 60.0 + 7.0, "PLAYING", 1,
                      2000.0 + TV_SNAP_SHOW_RETRY_BACKOFF_SEC + 1.0)
    check("TS4b: پس از Backoff دوباره show صادر می‌شود",
          ("show", "h1") in _acts4 and _ts.mid["h1"]["retries"] == 2)
    check("TS4c: show_attempt شمارهٔ تلاش را می‌دهد",
          _ts.show_attempt("h1") == 3)

    # TS5: confirm_shown → مصرف نهایی
    check("TS5: confirm_shown کلید را مصرف می‌کند",
          _ts.confirm_shown("h1") is True
          and _ts.mid["h1"]["show_state"] == "visible"
          and _ts.mid["h1"]["shown"] is True)
    check("TS5b: تأیید دوباره بی‌اثر است",
          _ts.confirm_shown("h1") is False)
    check("TS5c: fail پس از مصرف بی‌اثر است",
          _ts.fail_show("h1", 2100.0, "late") is False)

    # TS6: سقف تلاش‌ها → abandoned (چرخهٔ timeout→backoff→retry تا سقف)
    _ts6 = TVSnapshotEngine(dict(_ts_settings))
    _ts6.reset_match(3000.0)
    _ts6.tick(43 * 60.0, "PLAYING", 1, 3001.0)
    _now6 = 3001.0
    _abandoned_seen = False
    for _i6 in range(TV_SNAP_SHOW_MAX_RETRIES * 3 + 6):
        _now6 += (TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC
                  + TV_SNAP_SHOW_RETRY_BACKOFF_SEC + 2.0)
        _a6 = _ts6.tick(43 * 60.0 + 1.0, "PLAYING", 1, _now6)
        if ("show_abandoned", "h1") in _a6:
            _abandoned_seen = True
            break
    check("TS6: سقف Retry → show_abandoned + shown=True (چرخه می‌ایستد)",
          _abandoned_seen
          and _ts6.mid["h1"]["show_state"] == "abandoned"
          and _ts6.mid["h1"]["shown"] is True
          and _ts6.mid["h1"]["retries"] == TV_SNAP_SHOW_MAX_RETRIES)
    _a6b = _ts6.tick(50 * 60.0, "PLAYING", 1, _now6 + 5.0)
    check("TS6b: پس از abandoned دیگر show صادر نمی‌شود",
          ("show", "h1") not in _a6b
          and ("show_abandoned", "h1") not in _a6b)

    # TS7: پایان بازی — pend + confirm_show_end
    _ts7 = TVSnapshotEngine(dict(_ts_settings))
    _ts7.reset_match(4000.0)
    _a7 = []
    _w7 = 4000.0
    _a7 += _ts7.tick(91 * 60.0, "STOP", 2, _w7)
    for _i7 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w7 += 1.0
        _a7 += _ts7.tick(91 * 60.0, "STOP", 2, _w7)
    check("TS7: show_end با pend صادر می‌شود",
          ("show_end", "end90") in _a7
          and _ts7.end["end90"]["pend"] is not None
          and _ts7.end["end90"]["shows"] == 1)
    check("TS7b: confirm_show_end پاک می‌کند",
          _ts7.confirm_show_end() is True
          and _ts7.end["end90"]["pend"] is None)

    # TS8: fail_show_end → پس گرفتن shows + بازمسلح‌سازی
    _ts8 = TVSnapshotEngine(dict(_ts_settings))
    _ts8.reset_match(5000.0)
    _a8 = []
    _w8 = 5000.0
    _a8 += _ts8.tick(91 * 60.0, "STOP", 2, _w8)
    for _i8 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w8 += 1.0
        _a8 += _ts8.tick(91 * 60.0, "STOP", 2, _w8)
    check("TS8: fail_show_end سطح را بازمسلح می‌کند",
          _ts8.fail_show_end("end90", 6000.0, "test") is True
          and _ts8.end["end90"]["shows"] == 0
          and _ts8.end["end90"]["stop_since"] is None
          and _ts8.end["end90"]["fails"] == 1)

    # TS9: نمایش ۱۲۰ سطح ۹۰ را کامل مصرف می‌کند (بدون دوبل)
    _ts9 = TVSnapshotEngine(dict(_ts_settings))
    _ts9.reset_match(7000.0)
    _ts9.end["end90"]["shows"] = 1
    _ts9.end["end90"]["rearm_used"] = True
    _a9 = []
    _w9 = 7000.0
    _a9 += _ts9.tick(121 * 60.0, "STOP", 2, _w9)
    for _i9 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w9 += 1.0
        _a9 += _ts9.tick(121 * 60.0, "STOP", 2, _w9)
    check("TS9: end120 → end90 کامل مصرف (بدون دوبل) + pend پاک",
          ("show_end", "end120") in _a9
          and _ts9.end["end90"]["shows"] == 2
          and _ts9.end["end90"]["pend"] is None
          and _ts9.end["end120"]["pend"] is not None)

    # TS10: مهلت تأیید show_end → پس گرفتن خودکار + صدور مجدد
    _ts10 = TVSnapshotEngine(dict(_ts_settings))
    _ts10.reset_match(8000.0)
    _w10 = 8000.0
    _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    for _i10 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w10 += 1.0
        _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    _w10 += TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0
    _ts10.tick(91 * 60.0, "STOP", 2, _w10)     # مهلت → پس گرفتن خودکار
    check("TS10a: مهلت تأیید show_end → shows پس گرفته می‌شود",
          _ts10.end["end90"]["shows"] == 0
          and _ts10.end["end90"]["fails"] == 1)
    _a10b = []
    for _i10b in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w10 += 1.0
        _a10b += _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    check("TS10b: پس از بازمسلح‌سازی، نمایش پایان دوباره صادر می‌شود",
          ("show_end", "end90") in _a10b)

    # TS11: یکپارچگی ساختاری — پورت کامل سه‌لایه (بازرسی سورس)
    _src_engine_ts = _inspect.getsource(TVSnapshotEngine)
    check("TS11: موتور API تراکنشی دارد (confirm/fail/show_attempt)",
          all(m in _src_engine_ts
              for m in ("def confirm_shown", "def fail_show",
                        "def show_attempt", "def confirm_show_end",
                        "def fail_show_end", "show_abandoned")))
    _src_app_ts = _inspect.getsource(MomentumApp)
    check("TS11b: App صف رویداد + drain + لاگ مرحله دارد",
          all(m in _src_app_ts
              for m in ("_snap_show_events", "_snap_drain_show_events",
                        "_snap_show_stage", "_snap_show_event")))
    _src_uip_ts = _inspect.getsource(MomentumApp._ui_post)
    check("TS11c: _ui_post خروجی bool می‌دهد (صف/اجرا گزارش می‌شود)",
          "return True" in _src_uip_ts and "return False" in _src_uip_ts
          and "_report_fail" in _src_uip_ts)
    _src_gpu_ts = _inspect.getsource(MomentumApp._show_snapshot_overlay_gpu)
    check("TS11d: نقطهٔ تأیید SHOWING در مسیر GPU",
          '_snap_show_event("confirm' in _src_gpu_ts)
    _src_tk_ts = _inspect.getsource(MomentumApp._show_snapshot_overlay)
    check("TS11e: نقطهٔ تأیید SHOWING در مسیر Tk",
          '_snap_show_event("confirm' in _src_tk_ts)

    # TS11f-h: جای درست ماشین فاز در worker_loop (قبل از گیت‌های داده)
    _src_wl_ts = _inspect.getsource(MomentumApp.worker_loop)
    _i_205 = _src_wl_ts.find("2.05-پ")
    _i_snapts = _src_wl_ts.find("self._snapshot_tick(")
    _i_gates = _src_wl_ts.find("if not ball or not players:")
    _i_verdict = _src_wl_ts.find("if self._ht_pending:")
    _i_wd = _src_wl_ts.find("if is_new_match_watchdog(")
    _i_flag = _src_wl_ts.find("should_flag_time_drop(")
    check("TS11f: بند 2.05-پ قبل از _snapshot_tick اجرا می‌شود",
          0 < _i_205 < _i_snapts,
          f"205@{_i_205} snap@{_i_snapts}")
    check("TS11g: تصمیم HT/ET قبل از گیت‌های ball/players (رفع گرسنگی FSM)",
          0 < _i_verdict < _i_gates and 0 < _i_wd < _i_gates
          and 0 < _i_flag < _i_gates,
          f"verdict@{_i_verdict} wd@{_i_wd} flag@{_i_flag} gates@{_i_gates}")
    check("TS11h: هر تصمیم‌گر فقط یک‌بار در worker وجود است",
          _src_wl_ts.count("if self._ht_pending:") == 1
          and _src_wl_ts.count("should_flag_time_drop(") == 1
          and _src_wl_ts.count("if is_new_match_watchdog(") == 1)
    check("TS11i: مصرف تصمیم‌ها فقط در PLAYING (شرط قدیمی حفظ شده)",
          'if m_state == "PLAYING" and total_t is not None:' in _src_wl_ts)

    # TS12: رگرسیون — منطق‌های دیگر دست‌نخورده
    check("TS12a: تشخیص PLAYING/STOP همان متد قدیمی است (بایت 128/129)",
          "MATCH_STATE_OFFSET" in _inspect.getsource(GameEngine.read_match_state)
          and "128" in _inspect.getsource(GameEngine.read_match_state))
    check("TS12b: کارت قرمز سر جایش (پوینتر/زنجیره)",
          GameEngine.RED_CARD_PTR_OFFSET == 0x036F3F88
          and tuple(GameEngine.RED_CARD_CHAIN) == (0x350, 0x4E0))
    check("TS12c: نرمی زنگوله‌ای حفظ شد (σ=20/55)",
          abs(MomentumScoringConfig.GAUSSIAN_SIGMA - 20.0) < 1e-9
          and abs(TV_SMOOTH_SIGMA_SEC - 55.0) < 1e-9)
    check("TS12d: ثابت‌های تراکنشی v10.28 در جای خود هستند",
          TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC == 10.0
          and TV_SNAP_SHOW_RETRY_BACKOFF_SEC == 3.0
          and TV_SNAP_SHOW_MAX_RETRIES == 6
          and TV_SNAP_END_FAIL_MAX == 3)

    # TS13: v10.29 — تضمین پایان نمایش همهٔ نمودارها (پورت v1.2.2 از 2017)
    _src_gpu_cls = _inspect.getsource(GPUOverlayRenderer)
    check("TS13a: رندرر GPU مدیریت سطح-پنجره دارد (_win_show/_win_hide)",
          "def _win_show" in _src_gpu_cls
          and "def _win_hide" in _src_gpu_cls
          and "_win_visible" in _src_gpu_cls
          and "_hide_pending" in _src_gpu_cls)
    check("TS13b: پنجره در INIT دیگر نمایان نمی‌شود (رفع ماندن تا ابد)",
          "_glfw.show_window(win)" not in
          _inspect.getsource(GPUOverlayRenderer._run)
          and "self._win_visible = False" in
          _inspect.getsource(GPUOverlayRenderer._run))
    _src_h29 = _inspect.getsource(GPUOverlayRenderer._handle)
    check("TS13c: show واقعی → _win_show؛ hide_now → _win_hide ساختاری",
          "self._win_show()" in _src_h29
          and "self._win_hide()" in _src_h29
          and "self._hide_pending = False" in _src_h29)
    check("TS13d: hide در جریان انیمیشن رها نمی‌شود (_hide_pending)",
          "self._hide_pending = True" in _src_h29)
    _src_ae29 = _inspect.getsource(GPUOverlayRenderer._anim_end)
    check("TS13e: پایان خروج → پنجره مخفی؛ hide معلق → خروج نرم",
          "self._win_hide()" in _src_ae29
          and "self._hide_pending" in _src_ae29)
    _src_app29 = _inspect.getsource(MomentumApp)
    check("TS13f: App نگهبان مدت نمایش + ضرب‌الاجل دارد",
          "def _snap_overlay_duration_watchdog" in _src_app29
          and "_snap_overlay_deadline_wall" in _src_app29
          and "_snap_overdue_watchdog_fired" in _src_app29)
    _src_shg29 = _inspect.getsource(MomentumApp._show_snapshot_overlay_gpu)
    _src_sht29 = _inspect.getsource(MomentumApp._show_snapshot_overlay)
    check("TS13g: ضرب‌الاجل در هر دو مسیر نمایش (GPU/Tk) ست می‌شود",
          "_snap_overlay_deadline_wall = (" in _src_shg29
          and "_snap_overlay_deadline_wall = (" in _src_sht29
          and "TV_SNAP_OVERDUE_GRACE_SEC" in _src_shg29
          and "TV_SNAP_OVERDUE_GRACE_SEC" in _src_sht29)
    _src_hso29 = _inspect.getsource(MomentumApp._hide_snapshot_overlay)
    check("TS13h: پنهان‌سازی ضرب‌الاجل را باطل می‌کند (هر دو مسیر)",
          "_snap_overlay_deadline_wall = None" in _src_hso29)
    check("TS13i: مهلت نگهبان (8s) و شروع آن در __init__ ثبت شده",
          TV_SNAP_OVERDUE_GRACE_SEC == 8.0
          and "_snap_overlay_duration_watchdog" in
          _inspect.getsource(MomentumApp.__init__))
    check("TS13j: رگرسیون v10.29 — کارت قرمز/PLAYING/نرمی زنگوله‌ای "
          "دست‌نخورده",
          GameEngine.RED_CARD_PTR_OFFSET == 0x036F3F88
          and tuple(GameEngine.RED_CARD_CHAIN) == (0x350, 0x4E0)
          and "MATCH_STATE_OFFSET" in
          _inspect.getsource(GameEngine.read_match_state)
          and abs(MomentumScoringConfig.GAUSSIAN_SIGMA - 20.0) < 1e-9
          and abs(TV_SMOOTH_SIGMA_SEC - 55.0) < 1e-9)

    print("\n" + "=" * 74)
    if failures:
        print(f" نتیجه: {total - len(failures)}/{total} PASS — {len(failures)} FAILURE:")
        for f in failures:
            print(f"   ✗ {f}")
        return 1
    print(f" نتیجه: {total}/{total} PASS ✅ — همهٔ تست‌های End-to-End موفق")
    return 0


# =============================================================================
# Entry point (headless service started by ModBridge.py)
# =============================================================================
def main():
    if not acquire_single_instance():
        clog("[Momentum] another Match Momentum backend is already running.")
        return
    try:
        app = MomentumApp()
    except Exception as ex:
        if _MOM_BASE is _HeadlessTkBase:
            raise
        print(f"[Momentum] GUI window init failed "
              f"({type(ex).__name__}: {ex}) — restarting as pure headless "
              f"backend (set MOM_GUI=0 to silence)", flush=True)
        globals()["_MOM_BASE"] = _HeadlessTkBase
        globals()["MomentumApp"] = type("MomentumApp", (_HeadlessTkBase,),
                                        dict(MomentumApp.__dict__))
        app = MomentumApp()
    try:
        app.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.on_close()


if __name__ == "__main__":
    if "--render-archive" in sys.argv:
        try:
            _idx = sys.argv.index("--render-archive")
            _path = sys.argv[_idx + 1] if len(sys.argv) > _idx + 1 else ""
            if not _path:
                print("usage: python MomentumMod.py --render-archive "
                      "<archive.zip|match_data.json>")
                sys.exit(2)
            _out = render_archive_chart(_path)
            if _out:
                print("CHART RENDERED: " + str(_out))
                sys.exit(0)
            print("RENDER FAILED: " + str(_path))
            sys.exit(1)
        except SystemExit:
            raise
        except Exception as _ex:
            print(f"RENDER ERROR: {type(_ex).__name__}: {_ex}")
            sys.exit(1)
    if "--selftest" in sys.argv:
        sys.exit(run_selftest())
    main()

