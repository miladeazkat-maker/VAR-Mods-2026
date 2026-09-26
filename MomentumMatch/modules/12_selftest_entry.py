def run_selftest(render_png: bool = True) -> int:
    print("=" * 74)
    print(" FL_2026 Live Match Momentum v9 — End-to-End Self Test")
    print("=" * 74)

    import matplotlib
    try:
        matplotlib.use("Agg")   # headless — without technical noteortechnical note to displaytechnical note
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

    # ---------- technical noteortechnical note technical noteandtechnical note istechnical note (technical note 21) ----------
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

    # technical note‌technical notefromtechnical note Game Clock: 0 until 46:00 with technical note 0.5s — technical noteandtechnical note exactly in time technical noteandtechnical note
    # version 7: technical note Goal exactly technical note chaintechnical note real _register_hook_goal register
    # technical note‌technical noteandtechnical note: first technical note direct hook (disp_time in same moment frozen) and after
    # technical note technical noteandtechnical note Event Bus → Impact technical note. technical noteand path independent technical note‌technical note.
    def _fire_goal_like_hook(ev, mt):
        mom.add_hook_goal_marker(ev.team, mt, 1)   # (1) technical note direct — first
        mom.on_event(ev)                            # (2) Event Bus → Impact technical note

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
    for mt in pending:                      # technical note technical noteandtechnical note withtechnical note‌technical note (technical notemust technical note technical note)
        mom.on_event(pending[mt])
    mom.update(T_END)

    hist = [s for s in mom.history if s["net"] == s["net"]]

    def val_at(tm: float, key: str) -> float:
        best = min(hist, key=lambda s: abs(s["game_time"] - tm))
        return best[key]

    print("\n--- 1) text textdatatext: Home withtext / Away below ---")
    check("Home events → Net > 0", val_at(310.0, "net") > 0,
          f"net(05:10)={val_at(310.0, 'net'):+.1f}")
    check("Away Shot → Away text text‌text", val_at(610.0, "away") > val_at(300.0, "away"),
          f"away(10:10)={val_at(610.0, 'away'):+.1f} > away(05:00)={val_at(300.0, 'away'):+.1f}")
    check("Away events → Net textand to below", val_at(615.0, "net") < val_at(305.0, "net"),
          f"net(10:15)={val_at(615.0, 'net'):+.1f} < net(05:05)={val_at(305.0, 'net'):+.1f}")

    print("\n--- 2) Decay text (only Match Time) ---")
    check("decay: Net(19:50) < Net(05:10)", val_at(1190.0, "net") < val_at(310.0, "net"),
          f"{val_at(1190.0, 'net'):+.1f} < {val_at(310.0, 'net'):+.1f}")
    half = cfg.MOMENTUM_HALF_LIFE
    v0 = val_at(305.0, "home")
    v1 = val_at(305.0 + half, "home")
    check(f"text‌text {half:.0f}s → text textandtext text", v1 < v0 * 0.75, f"home(05:05)={v0:.1f} → home(+HL)={v1:.1f}")

    print("\n--- 3) Goal Marker / Goal Delayed Pulse ---")
    g_imp = next((i for i in mom.impacts if i.event_type == "Goal" and i.team == "Home"), None)
    check("Goal Home → Impact with pulse", g_imp is not None and g_imp.is_goal_pulse)
    if g_imp:
        check("Goal Marker textandtext 20:00 text", abs(g_imp.goal_time - 1200.0) < 1e-9,
              f"goal_time={_fmt_clock(g_imp.goal_time)}")
        check("Goal Peak textandtext 20:05 (DELAY=5s withtext)", abs(g_imp.peak_time - 1205.0) < 1e-9,
              f"peak_time={_fmt_clock(g_imp.peak_time)}")
        f0 = mom.goal_response_factor(g_imp, 1199.0)
        f_mid = mom.goal_response_factor(g_imp, 1202.5)
        f_peak = mom.goal_response_factor(g_imp, 1205.0)
        f_hold = mom.goal_response_factor(g_imp, 1205.0 + cfg.GOAL_RESPONSE_WIDTH - 0.1)
        f_dec = mom.goal_response_factor(g_imp, 1205.0 + cfg.GOAL_RESPONSE_WIDTH + 60.0)
        check("passtext text before from t_goal = 0", f0 == 0.0)
        check("passtext text textortext text ≈ 0.5 (raised-cosine)", abs(f_mid - 0.5) < 0.02, f"f={f_mid:.3f}")
        check("passtext text in textandtext = 1.0", abs(f_peak - 1.0) < 1e-9)
        check("text textandtext until peak+WIDTH", abs(f_hold - 1.0) < 1e-9)
        check("text from text → decay text", 0.0 < f_dec < 1.0, f"f(+60s)={f_dec:.3f}")
        check("textandtext passtext → Net withtext text‌textandtext", val_at(1206.0, "net") > val_at(1199.0, "net"),
              f"net(20:06)={val_at(1206.0, 'net'):+.1f} > net(19:59)={val_at(1199.0, 'net'):+.1f}")
        phase_peak = mom.goal_pulse_phase(g_imp, 1206.0)
        phase_done = mom.goal_pulse_phase(g_imp, 1199.0)
        check("textfromtext pulse correct", phase_done == "WAITING" and phase_peak == "PEAK/ACTIVE",
              f"19:59→{phase_done} | 20:06→{phase_peak}")
    ga_imp = next((i for i in mom.impacts if i.event_type == "Goal" and i.team == "Away"), None)
    check("Goal Away → Peak textandtext 30:05", ga_imp is not None and abs(ga_imp.peak_time - 1805.0) < 1e-9)
    check("Marker textandtext t_goal is text peak", g_imp is not None and g_imp.goal_time < g_imp.peak_time)

    print("\n--- 4) text text: unchanged text text ---")
    ok_nonneg = all(s["home"] >= -1e-9 and s["away"] >= -1e-9 for s in hist)
    ok_sum = all(abs(s["net"] - (s["home"] - s["away"])) < 1e-9 for s in hist)
    ok_mono = all(b["game_time"] >= a["game_time"] for a, b in zip(hist, hist[1:]))
    check("home/away never text text‌textandtext", ok_nonneg)
    check("net ≡ home − away (exactly)", ok_sum)
    check("Game Time textandtext", ok_mono)
    # technical note technical notefrom only in momenttechnical note technical note technical note moment‌technical note or windowtechnical note technical note passtechnical note technical note
    # in technical note sample‌technical note technical note must completetechnical note smooth withtechnical note (only decay technical note)
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
    check("text from textdatatext text smooth is (Δ≤2.0/sample)", max(outside, default=0.0) <= 2.0,
          f"max outside={max(outside, default=0.0):.3f}")
    check("text text text‌text from text text textfrom is not",
          all(d <= max_allowed for d, _ in steps),
          f"max step={max((d for d, _ in steps), default=0.0):.1f} ≤ {max_allowed:.0f}")

    print("\n--- 5) text textandwithtext text Chance + Shot text‌text ---")
    ch = make_ev(next_id, "Chance", "Home", 2100.0, {})
    next_id += 1
    mom.on_event(ch)
    sh = make_ev(next_id, "Shot", "Home", 2101.5, {"final_threat": 50.0}, related=[ch.event_id])
    next_id += 1
    mom.on_event(sh)
    ch_imp = mom.get_impact(ch.event_id)
    sh_imp = mom.get_impact(sh.event_id)
    expected_ch = cfg.CHANCE_WEIGHT * cfg.SHOT_LINKED_CHANCE_RATIO * cfg.CERTAIN_MULTIPLIER * 1.0
    check("Chance text‌text text text (×0.30)", ch_imp is not None and abs(ch_imp.final_impact - expected_ch) < 0.01,
          f"final={ch_imp.final_impact:.2f} ≈ {expected_ch:.2f}")
    check("Shot text‌text text text", sh_imp is not None and abs(sh_imp.final_impact - 50.0) < 0.01,
          f"final={sh_imp.final_impact:.2f} = 50.0")
    check("text with MATCH TIME (Δt=1.5s ≤ 3.0s)", 0.0 <= sh.match_time - ch.match_time <= 3.0,
          f"Δt={sh.match_time - ch.match_time:.1f}s")

    print("\n--- 6) Gaussian smoothing real (layer display) ---")
    sg = gaussian_smooth([0, 0, 0, 0, 9.0, 0, 0, 0, 0], 1.0)
    check("length text text text‌textandtext", len(sg) == 9)
    check("textandtext text text‌ortext (text spike)", 3.0 < max(sg) < 9.0, f"peak={max(sg):.2f}")
    check("text text textwithtext text text‌textandtext", abs(sum(sg) - 9.0) < 0.6, f"sum={sum(sg):.2f}")

    print("\n--- 7) Pause (Match Time text → text text textand text‌textandtext) ---")
    n_before = len(mom.history)
    mom.update(T_END); mom.update(T_END); mom.update(T_END)
    check("time text → sample new register text‌textandtext", len(mom.history) == n_before,
          f"len={len(mom.history)} (before: {n_before})")

    print("\n--- 8) gap HT (text chart text textand text) ---")
    h1_last_disp = mom.history[-1]["disp_time"]
    mom.set_half_break(cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
    guards = sum(1 for s in mom.history if s["net"] != s["net"])
    check("textand watchdog NaN in gap HT", guards == 2, f"guards={guards}")
    check("width gap = HT_GAP_DISPLAY_SECONDS",
          mom.ht_break is not None and abs((mom.ht_break[1] - mom.ht_break[0]) - cfg.HT_GAP_DISPLAY_SECONDS) < 1e-9)
    # --- version 5 (technical note withtechnical note 2): withtechnical note technical note technical note for second half to 45:00 technical note‌technical note
    # technical note second‌technical note second half (2700..2760 — technical note‌technical note from end register‌technical note first half
    # technical note T_END=2760 is) must technical notedistance sample technical note technical note technical note chart empty technical note
    n_before_h2 = len(mom.history)
    mom.update(2700.5)   # technical note sampletechnical note second half — still technical note‌technical note from T_END first half
    check("version 5: sampling second half textdistance after from line textis HT from text text‌text",
          len(mom.history) == n_before_h2 + 1,
          f"Δ={len(mom.history) - n_before_h2} (text: +1) | _last_t={mom._last_t:.1f}")
    _s2 = mom.history[-1]
    check("version 5: firsttext sampletext second half correct after from gap is (text inside text)",
          _s2["disp_time"] >= mom.ht_break[1] - 1e-6,
          f"disp={_s2['disp_time']:.1f} ≥ ht_end={mom.ht_break[1]:.1f}")
    mom.update(2820.0)   # second half technical noteand technical note‌technical noteandtechnical note (45:00 resumed → 47:00)
    last = mom.history[-1]
    off = mom.display_offset
    check("offset second half text text", abs(last["disp_time"] - (2820.0 + off)) < 1e-9 and off > 0,
          f"offset={off:+.1f}s")
    check("sample second half after from gap is", last["disp_time"] >= h1_last_disp + cfg.HT_GAP_DISPLAY_SECONDS - 1e-9,
          f"disp={last['disp_time']:.1f} ≥ {h1_last_disp + cfg.HT_GAP_DISPLAY_SECONDS:.1f}")

    print("\n--- 9) render chart (Net-only text‌text + Goal Marker version 4 + HT) ---")
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
            check("render headless and save PNG", os.path.exists(out_png), out_png)
            ax_ref["ax"] = ax
            plt.close(fig)
        except Exception as ex:
            check("render headless and save PNG", False, f"exception: {ex}")

    # --- check Artisttechnical note render (version 7 — technical note technical note gid deterministic technical note) ---
    if ax_ref["ax"] is not None:
        ax = ax_ref["ax"]
        # 1) lineandtechnical note technical noteandtechnical note technical note: only Artisttechnical note technical note‌technical note technical note technical note (xdata technical note
        #    ydata from 0 (line technical note) until outside — without technical noteandtechnical note from technical note)
        goal_verts = [ln for ln in ax.lines
                      if (ln.get_gid() or "").startswith("goal_line_")]
        # technical note technical note technical noteand Artist line technical note: shelltechnical note technical note + core technical note
        check("text text text line textandtext text (shell + core)",
              len(goal_verts) == 2 * len(mom.hook_goal_markers),
              f"verts={len(goal_verts)}")
        ok_no_cross = all(min(ln.get_ydata()) >= 0.0 or max(ln.get_ydata()) <= 0.0
                          for ln in goal_verts)
        check("line text from line text textandtext text‌text", ok_no_cross)
        # 2) icon ball: technical note technical note‌technical note technical note‌technical note‌technical note for technical note technical note hook
        ball_icons = [ln for ln in ax.lines
                      if (ln.get_gid() or "").startswith("goal_ball_")]
        check("icon ball (text‌text Line2D) for text text text text",
              len(ball_icons) == len(mom.hook_goal_markers),
              f"icons={len(ball_icons)}")
        # 2technical note1) version 10technical note2 — icon PNG ball (if tex/ball_icon.png technical noteandtechnical noteandtechnical note withtechnical note)
        if load_ball_icon() is not None:
            _img_icons = [a for a in ax.artists
                          if (a.get_gid() or "").startswith("goal_ballimg_")]
            check("icon PNG ball (goal_ballimg_) for text text text text",
                  len(_img_icons) == len(mom.hook_goal_markers),
                  f"img_icons={len(_img_icons)}")
        else:
            check("icon PNG ball textandtextandtext is not → fallback text active",
                  all(ln.get_marker() == "o" for ln in ball_icons),
                  f"circle_markers={len(ball_icons)}")
        # 3) Render Assert version 7 — deterministic:
        #    len(hook_goal_markers) == number_of_goal_icons
        #                            == number_of_goal_marker_lines
        _n_mk = len(mom.hook_goal_markers)
        _n_lines = len({(ln.get_gid() or "").split("_")[2] for ln in goal_verts})
        check("Render Assert: len(hook_goal_markers) == goal_icons == goal_marker_lines",
              _n_mk == len(ball_icons) == _n_lines,
              f"markers={_n_mk}, icons={len(ball_icons)}, lines={_n_lines}")
        home_above = any(ln.get_ydata()[0] > 0 for ln in ball_icons)
        away_below = any(ln.get_ydata()[0] < 0 for ln in ball_icons)
        check("Home icon withtext / Away icon below", home_above and away_below,
              f"above={home_above}, below={away_below}")
        # 3) technical note technical note from technical note technical noteandtechnical note chart technical noteandtechnical note technical note (only HT technical notefrom is)
        no_goal_text = all("Goal" not in t.get_text() and "text" not in t.get_text()
                           for t in ax.texts)
        check("without text text text textandtext chart", no_goal_text,
              f"texts={[t.get_text() for t in ax.texts]}")
        # 4) technical noteand line technical noteuntiltechnical note boundary HT
        def _is_vert_line(ln):
            xd, yd = list(ln.get_xdata()), list(ln.get_ydata())
            return len(xd) == 2 and xd[0] == xd[1]
        ht_lines = [ln for ln in ax.lines if _is_vert_line(ln)
                    and list(ln.get_ydata()) == [0.0, 1.0]]
        check("textand line textandtext textuntiltext boundary HT", len(ht_lines) == 2, f"ht_lines={len(ht_lines)}")
        if mom.ht_break:
            gxs = sorted(ln.get_xdata()[0] for ln in ht_lines)
            check("position lineandtext HT = text/text gap",
                  abs(gxs[0] - mom.ht_break[0]) < 1.0 and abs(gxs[1] - mom.ht_break[1]) < 1.0,
                  f"lines={[f'{v:.0f}' for v in gxs]} | break={mom.ht_break}")
        # 5) version 4: width gap technical noteandtechnical note technical noteandtechnical note = 5 minute (300 second — third 900 beforetechnical note)
        check("width gap HT textandtext textandtext = 300s (5 minute — third version 3)",
              mom.ht_break is not None
              and abs((mom.ht_break[1] - mom.ht_break[0]) - cfg.HT_GAP_DISPLAY_SECONDS) < 1e-9
              and abs(cfg.HT_GAP_DISPLAY_SECONDS - 300.0) < 1e-9,
              f"gap={mom.ht_break[1] - mom.ht_break[0]:.0f}s")

    # -------------------------------------------------------------
    # version 7 — 9technical note5) chaintechnical note deterministic Counter → Hook Marker → Chart:
    #   technical note increment countertechnical note technical note (for technical note team) must exactly technical note technical note new
    #   technical notefromtechnical note and technical noteandtechnical note chart exactly technical note icon + technical note line technical noteandtechnical note technical note.
    #   technical note Dedup technical note technical note‌technical note technical note technical note‌technical noteandtechnical note — technical note technical noteand technical note technical note technical note from technical note team.
    #   Goal Impact only for Momentum Pulse is and in technical note technical note technical note technical note.
    # -------------------------------------------------------------
    print("\n--- 9text5) version 7: chaintext Counter increment → Hook Marker → Chart ---")

    def _disp5(raw):
        if raw != raw:
            return float('nan')
        return cfg.DISPLAY_RANGE * math.tanh(raw / max(1.0, cfg.DISPLAY_SOFT_SCALE))

    def _render_counts(axx):
        """text deterministic from textandtext gid: lineandtext text text (text text = shell+core) and icon‌text"""
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

        # technical note‌technical notefromtechnical note technical note _poll_goal_hook + _register_hook_goal (order technical note
        # technical note: first add_hook_goal_marker and after register_goal_event technical noteandtechnical note Bus)
        _cnt = {"Home": None, "Away": None}
        _chain_events = []

        def _hook_poll(team, new_v, t, bus_ok=True):
            nonlocal _chain_id
            _dec, _n = GoalHooker.counter_event(_cnt[team], new_v)
            _registered = 0
            if _dec == "GOAL":
                for _ in range(_n):
                    mom2.add_hook_goal_marker(team, t, 1)     # (1) technical note direct — first
                    if bus_ok:                                 # (2) Event Bus → Impact technical note
                        _chain_id += 1
                        _ev = make_ev(_chain_id, "Goal", team, t)
                        _chain_events.append(_ev)
                        mom2.on_event(_ev)
                    _registered += 1
            _cnt[team] = new_v        # BASELINE/RESET/NOCHANGE only technical note counter
            return _dec, _registered

        _hook_poll("Home", 0, 5.0)     # BASELINE — firsttechnical note read valid Home
        _hook_poll("Away", 0, 5.0)     # BASELINE — firsttechnical note read valid Away
        check("BASELINE firsttext read is — text text text‌textfromtext",
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
        # --- Counter increment #3 → hook marker #3 (technical note‌team with #1 and only 6s after) ---
        check("Counter increment #3 → hook marker #3 (text text‌team and text)",
              _hook_poll("Home", 2, 126.0) == ("GOAL", 1)
              and mom2.hook_goal_marker_count() == 3,
              f"markers={mom2.hook_goal_marker_count()}")
        _h_imp = mom2.get_impact(_chain_events[0].event_id)
        check("path Bus healthy is: text text with goal_disp_time frozen = goal_time",
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
        # Render Assert version 7 — exactly technical note to technical note:
        _n_mk2 = mom2.hook_goal_marker_count()
        check("Render Assert: len(hook_goal_markers) == number_of_goal_icons == number_of_goal_marker_lines",
              _n_mk2 == len(_balls2) == len(_llines),
              f"markers={_n_mk2}, icons={len(_balls2)}, lines={len(_llines)}")
        check("text text exactly shell + core text (without Artist text)",
              len(_lgids) == 2 * _n_mk2, f"line_artists={len(_lgids)}")
        _ball_x = sorted(round(list(ln.get_xdata())[0], 1) for ln in _balls2)
        check("text 3 text text text: 100s and 120s and 126s (without Dedup text for textand text text text‌team)",
              _ball_x == [100.0, 120.0, 126.0], f"x={_ball_x}")
        _home_balls = [ln for ln in _balls2 if list(ln.get_ydata())[0] > 0]
        _away_balls = [ln for ln in _balls2 if list(ln.get_ydata())[0] < 0]
        check("Home → ball withtext chart (2 text) / Away → ball below chart (1 text)",
              len(_home_balls) == 2 and len(_away_balls) == 1,
              f"home={len(_home_balls)}, away={len(_away_balls)}")

        # --- istechnical note technical noteand path: Goal Impact technical note technical note in technical note technical note technical note ---
        # technical note #4 only from path Bus (Event + Impact technical note) and «without» technical note hook
        # register technical note‌technical noteandtechnical note → count icon/line technical note must unchanged 3 technical note.
        _chain_id += 1
        mom2.on_event(make_ev(_chain_id, "Goal", "Away", 128.0))
        _n_pulse = sum(1 for imp in mom2.impacts if imp.is_goal_pulse)
        _fig2b = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax2b = _fig2b.add_subplot(111)
        draw_momentum_chart(_ax2b, mom2, cfg, _disp5, goal_glyph_ok=True)
        _lgids_b, _llines_b, _balls2b = _render_counts(_ax2b)
        check("Goal Impact only text textandtextandtext is — icon/line text text text‌text",
              len(_balls2b) == 3 and len(_llines_b) == 3
              and mom2.hook_goal_marker_count() == 3,
              f"icons={len(_balls2b)}, lines={len(_llines_b)}, markers={mom2.hook_goal_marker_count()}")
        check("path independent Counter → Event → Impact → Pulse healthy is (4 text text)",
              _n_pulse == 4, f"goal_pulses={_n_pulse}")

        # --- technical note without Event (technical note: Errortechnical note Bus) + technical note frozen second half ---
        # technical note #5 only with add_hook_goal_marker register technical note‌technical noteandtechnical note (without on_event) —
        # withtechnical note technical note exactly technical note technical note must technical note technical noteandtechnical note disp_time frozen momenttechnical note register is.
        mom2.set_half_break(cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
        mom2.add_hook_goal_marker("Away", 2760.0, 2)   # without on_event → Bus from technical note decreasetechnical note
        _t2 = 2700.0
        while _t2 <= 2770.0:
            mom2.update(_t2)
            _t2 += 0.5
        _fig3 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax3 = _fig3.add_subplot(111)
        draw_momentum_chart(_ax3, mom2, cfg, _disp5, goal_glyph_ok=True)
        _lgids_c, _llines_c, _balls3 = _render_counts(_ax3)
        _n_mk3 = mom2.hook_goal_marker_count()
        check("Render Assert text from text second half: markers == icons == lines",
              _n_mk3 == len(_balls3) == len(_llines_c),
              f"markers={_n_mk3}, icons={len(_balls3)}, lines={len(_llines_c)}")
        _expect = round(2760.0 + mom2.display_offset, 1)
        check("text second half with disp_time frozen correct text text (after from line textis HT)",
              any(abs(round(list(ln.get_xdata())[0], 1) - _expect) < 0.5 for ln in _balls3),
              f"ball_x={[round(list(ln.get_xdata())[0], 1) for ln in _balls3]} | text≈{_expect}")
    except Exception as ex:
        check("chaintext Counter → Hook Marker → Chart (9text5)", False, f"exception: {ex}")

    # --- version 5: technical noteandtechnical note technical note resync_clock (chart never technical note‌technical note) ---
    print("\n--- 9text6) version 5: resync_clock — withtext without HT/withtext new ---")
    try:
        mom3 = MomentumEngine(cfg)
        _t3 = 0.0
        while _t3 <= 600.0:
            mom3.update(_t3)
            _t3 += 0.5
        _n_before3 = len(mom3.history)
        mom3.resync_clock(300.0)   # technical note technical note‌technical note from latest sample (withtechnical note nametechnical note)
        check("resync: gap text registered", len(mom3.extra_breaks) == 1
              and sum(1 for s in mom3.history if s["net"] != s["net"]) == 2,
              f"extra={len(mom3.extra_breaks)}")
        _n_guard3 = len(mom3.history)
        mom3.update(301.0)         # withtechnical note from technical note technical note technical note → must technical noteandtechnical note sample technical note
        check("resync: sampling textandtext from text text‌text (chart text‌text)",
              len(mom3.history) == _n_guard3 + 1,
              f"Δ={len(mom3.history) - _n_guard3} | _last_t={mom3._last_t:.1f}")
        _last3 = mom3.history[-1]
        check("resync: sampletext new after from gap text is",
              _last3["disp_time"] >= mom3.extra_breaks[-1][1] - 1e-6,
              f"disp={_last3['disp_time']:.1f} ≥ {mom3.extra_breaks[-1][1]:.1f}")
        mom3.resync_clock(900.0)   # technical note technical noteandtechnical note → without gaptechnical note only sampling immediate
        mom3.update(901.0)
        check("resync: text textandtext → without gap text new",
              len(mom3.extra_breaks) == 1, f"extra={len(mom3.extra_breaks)}")
    except Exception as ex:
        check("resync_clock (9text6)", False, f"exception: {ex}")

    # -------------------------------------------------------------
    # version 8 — 9technical note7) technical note technical note independent from history (technical note withtechnical note layer Render):
    #   in version 7 if len(hist) < 2 technical noteandtechnical note draw_momentum_chart technical noteandtechnical note‌technical note
    #   and technical note technical note register‌technical note in technical note match never technical note technical note‌technical note.
    #   from version 8 to after: Goal Marker to history andtechnical note is not — technical note with
    #   technical note or technical note sampletechnical note technical note technical note hook_goal_markers exactly technical note technical note
    #   (shell + core + icon ball) technical note‌technical note.
    # -------------------------------------------------------------
    print("\n--- 9text7) version 8: text text independent from history (len(hist) < 2 textmust text text textandtext) ---")
    try:
        mom4 = MomentumEngine(cfg)
        mom4.update(0.0)                        # technical note technical note sample → len(hist) < 2
        mom4.add_hook_goal_marker("Home", 30.0, 1)
        mom4.add_hook_goal_marker("Away", 45.0, 1)
        check("text withtext withtextfromtext text: history text andtext 2 text hook registeredtext",
              len(mom4.history) < 2 and mom4.hook_goal_marker_count() == 2,
              f"hist={len(mom4.history)}, markers={mom4.hook_goal_marker_count()}")

        _fig4 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax4 = _fig4.add_subplot(111)
        draw_momentum_chart(_ax4, mom4, cfg, _disp5, goal_glyph_ok=True)
        _lgids_d, _llines_d, _balls4 = _render_counts(_ax4)
        _n_mk4 = mom4.hook_goal_marker_count()
        check("Render Assert without history text: markers == icons == lines",
              _n_mk4 == len(_balls4) == len(_llines_d),
              f"markers={_n_mk4}, icons={len(_balls4)}, lines={len(_llines_d)}")
        check("text with len(hist)<2 text text shell + core text",
              len(_lgids_d) == 2 * _n_mk4, f"line_artists={len(_lgids_d)}")
        check("message «Waiting for match start...» text text is",
              any("Waiting for match start" in t.get_text() for t in _ax4.texts),
              f"texts={[t.get_text() for t in _ax4.texts]}")
        _xlim4 = _ax4.get_xlim()
        check("xlim for textandtext text text textdecrease (latest text 45s + 25s)",
              abs(_xlim4[0]) < 1e-9 and _xlim4[1] >= 70.0 - 1e-6,
              f"xlim={_xlim4}")
        _home4 = sum(1 for ln in _balls4 if list(ln.get_ydata())[0] > 0)
        _away4 = sum(1 for ln in _balls4 if list(ln.get_ydata())[0] < 0)
        check("Home withtext / Away below — text currentlytext without history text",
              _home4 == 1 and _away4 == 1, f"home={_home4}, away={_away4}")

        # technical note boundarytechnical note: without technical note and without history → technical noteuntiltechnical note legacy (technical note technical note)
        mom5 = MomentumEngine(cfg)
        draw_momentum_chart(_ax4, mom5, cfg, _disp5, goal_glyph_ok=True)
        _g_gids5 = [ln.get_gid() for ln in _ax4.lines
                    if (ln.get_gid() or "").startswith("goal_")]
        check("without text and without history: text icon/line text text text‌textandtext",
              len(_g_gids5) == 0, f"gids={_g_gids5}")
    except Exception as ex:
        check("text text independent from history (9text7)", False, f"exception: {ex}")

    # -------------------------------------------------------------
    # version 9 — 9technical note8) render immediate without technical note Signal:
    #   * technical note‌technical note technical note: len(hist) == 0 — technical note technical note/technical note/Legend technical note andtechnical noteandtechnical note
    #     technical note andtechnical note Goal Marker must exactly from hook_goal_markers technical note technical noteandtechnical note
    #   * order register = order technical note (without sort/withtechnical note — gid technical note to order
    #     append data technical note‌technical noteandtechnical note technical note if time technical note‌technical note nametechnical note withtechnical note)technical note
    #   * specification deterministic technical note: zorder 100/101/102 and clip_on=False.
    # -------------------------------------------------------------
    print("\n--- 9text8) version 9: render immediate without Signal — hist=0 + order register = order text ---")
    try:
        mom6 = MomentumEngine(cfg)
        # technical note update() technical note run technical note‌technical noteandtechnical note → history default technical notelive (technical note sample) —
        # technical note len(hist) < 2: technical note/technical note/Legend technical notemust technical note technical noteandtechnical note andtechnical note Goal Marker
        # must exactly from hook_goal_markers technical note technical noteandtechnical note
        mom6.add_hook_goal_marker("Away", 45.0, 1)   # register first (time technical noteandtechnical note)
        mom6.add_hook_goal_marker("Home", 30.0, 1)   # register second (time technical note‌technical note — technical note nametechnical note)
        check("text text withtextfromtext text: history text (<2) andtext 2 text registeredtext",
              len(mom6.history) < 2 and mom6.hook_goal_marker_count() == 2,
              f"hist={len(mom6.history)}, markers={mom6.hook_goal_marker_count()}")

        _fig6 = plt.Figure(figsize=(11.5, 5.2), dpi=120, facecolor='#0d1420')
        _ax6 = _fig6.add_subplot(111)
        draw_momentum_chart(_ax6, mom6, cfg, _disp5, goal_glyph_ok=True)
        _lgids_e, _llines_e, _balls6 = _render_counts(_ax6)
        _n_mk6 = mom6.hook_goal_marker_count()
        check("Render Assert with hist=0: markers == icons == lines",
              _n_mk6 == len(_balls6) == len(_llines_e),
              f"markers={_n_mk6}, icons={len(_balls6)}, lines={len(_llines_e)}")

        _b0, _b1 = _balls6[0], _balls6[1]
        _b0x = float(list(_b0.get_xdata())[0]); _b0y = float(list(_b0.get_ydata())[0])
        _b1x = float(list(_b1.get_xdata())[0]); _b1y = float(list(_b1.get_ydata())[0])
        check("order register = order text: goal_ball_0 = register first (Away@45 — below)",
              _b0.get_gid() == "goal_ball_0" and abs(_b0x - 45.0) < 1e-6 and _b0y < 0,
              f"ball0=({_b0x:.1f},{_b0y:.1f}) gid={_b0.get_gid()}")
        check("goal_ball_1 = register second (Home@30 — withtext) without sort timetext",
              _b1.get_gid() == "goal_ball_1" and abs(_b1x - 30.0) < 1e-6 and _b1y > 0,
              f"ball1=({_b1x:.1f},{_b1y:.1f}) gid={_b1.get_gid()}")

        _sh_e = [ln for ln in _ax6.lines if (ln.get_gid() or "") == "goal_line_0_shell"]
        _co_e = [ln for ln in _ax6.lines if (ln.get_gid() or "") == "goal_line_0_core"]
        check("zorder deterministic: shell=100 < core=101 < ball=102",
              bool(_sh_e) and bool(_co_e)
              and _sh_e[0].get_zorder() == 100 and _co_e[0].get_zorder() == 101
              and _b0.get_zorder() == 102,
              f"z={_sh_e[0].get_zorder() if _sh_e else None},"
              f"{_co_e[0].get_zorder() if _co_e else None},{_b0.get_zorder()}")
        check("clip_on=False for text Artisttext text (ball text‌text totaltext text‌textandtext)",
              all(ln.get_clip_on() is False for ln in (_sh_e[0], _co_e[0], _b0, _b1)),
              f"clip={[ln.get_clip_on() for ln in (_sh_e[0], _co_e[0], _b0, _b1)]}")
        _n_nongoal = len([ln for ln in _ax6.lines
                          if not (ln.get_gid() or "").startswith("goal_")])
        check("with hist=0 text layertext andtext to history text text‌textandtext (only line text)",
              _n_nongoal == 1, f"non_goal_lines={_n_nongoal}")
        check("message text with hist=0 text text text and xlim text‌text text textandtext text‌text",
              any("Waiting for match start" in t.get_text() for t in _ax6.texts)
              and _ax6.get_xlim()[1] >= 70.0 - 1e-6,
              f"texts={[t.get_text() for t in _ax6.texts]} | xlim={_ax6.get_xlim()}")
    except Exception as ex:
        check("render immediate without Signal (9text8)", False, f"exception: {ex}")

    print("\n--- 10) version 4: chaintext complete Shot (Counter → Contact → Tracking) — without register text text ---")

    class _FakeShotEngineIO:
        """text‌textfrom GameEngine for test ShotEngine without withtext real"""
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
        {"seat": 9, "team": "Home", "x": 40.0, "z": 0.0},    # shot‌technical note
        {"seat": 10, "team": "Home", "x": 36.0, "z": 5.0},
        {"seat": 1, "team": "Away", "x": -50.0, "z": 0.0},   # GK technical note (technical noteandtechnical note)
        {"seat": 5, "team": "Away", "x": 30.0, "z": 8.0},
    ]
    # --- scenario 1: technical note (ball from line inandfromtechnical note technical noteandtechnical note technical note‌technical note) ---
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
    check("Counter Increment → start text‌text", started and se.state == "TRACKING")
    ev_g = None
    for _ in range(12):
        ev_g = se.update_tracking(fake_g)
        if ev_g is not None:
            break
    check("text‌text → ShotEventData text", ev_g is not None)
    if ev_g is not None:
        # --- version 4: technical note technical note technical note from path ball/technical noteandtechnical note technical note technical note‌technical noteandtechnical note ---
        check("text text from text register text‌textandtext (is_goal=False — only hook memory)",
              not ev_g.is_goal, f"outcome={ev_g.outcome}")
        check("Outcome textortext text from text text is (until confirmation hook)",
              "text" not in ev_g.outcome, f"outcome={ev_g.outcome}")
        check("time shot from frame contact (Match Time)", abs(ev_g.match_time - 900.0) < 0.5,
              f"mt={ev_g.match_time:.2f}")
        check("team shot correct", ev_g.team == "Home")
    # --- scenario 2: technical note (ball technical noteandtechnical note technical note technical note‌technical note) ---
    _players_save = [
        {"seat": 9, "team": "Home", "x": 40.0, "z": 0.0},
        {"seat": 5, "team": "Away", "x": 46.5, "z": 0.0},    # technical note technical note path
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
    check("scenariotext text → text without text", ev_s is not None and not ev_s.is_goal
          and ("text" in ev_s.outcome or "text" in ev_s.outcome),
          f"outcome={ev_s.outcome if ev_s else None}")

    # -------------------------------------------------------------
    # version 4 — register technical note from hook memory: chaintechnical note complete technical noteandtechnical note Bus real
    # (Shot → register_shot_event → register_goal_event → Momentum)
    # -------------------------------------------------------------
    print("\n--- 10text5) version 4: register text from hook memory (text path text) ---")
    _ede = EventDetectionEngine(cfg)
    _ede.event_bus.subscribe(mom.on_event)
    if ev_g is not None:
        _shot_ev = _ede.register_shot_event(ev_g)
        _imp_before = mom.get_impact(_shot_ev.event_id)
        _base_before = _imp_before.base_weight if _imp_before else 0.0
        _goal_ev = _ede.register_goal_event("Home", ev_g.match_time + 1.0,
                                            source="memory-hook")
        check("text Goal ⚽ textandtext Bus text text",
              any(e.event_type == "Goal ⚽" for e in _ede.events))
        check("text to latest shot same team text text (windowtext Match Time)",
              _goal_ev.related_event_ids == [_shot_ev.event_id],
              f"rel={_goal_ev.related_event_ids} | shot={_shot_ev.event_id}")
        check("text is_goal textandtext text shot text text (text withtext)",
              bool(_shot_ev.metadata.get("is_goal")) and "text" in str(_shot_ev.metadata.get("outcome", "")))
        _imp_after = mom.get_impact(_shot_ev.event_id)
        check("text shot text‌text to text text text (GOAL_LINKED_SHOT_RATIO)",
              _imp_after is not None
              and abs(_imp_after.base_weight - _base_before * cfg.GOAL_LINKED_SHOT_RATIO) < 1e-6
              and "goal-linked" in (_imp_after.note or ""),
              f"base {_base_before:.2f} → {_imp_after.base_weight if _imp_after else None}")
        _g_imp = mom.get_impact(_goal_ev.event_id)
        check("Impact text = text delaytext with textandtext goal+GOAL_PEAK_DELAY",
              _g_imp is not None and _g_imp.is_goal_pulse
              and abs(_g_imp.peak_time - (_goal_ev.match_time + cfg.GOAL_PEAK_DELAY)) < 1e-9,
              f"peak={_g_imp.peak_time if _g_imp else None}")
        check("weight text text = GOAL_WEIGHT",
              _g_imp is not None and abs(_g_imp.base_weight - cfg.GOAL_WEIGHT) < 1e-9)

    print("\n--- 11) text text countertext global (text withtext text‌text text version 2) ---")
    _dec = MomentumApp._shot_trigger_decision
    b, e = _dec(None, 5)
    check("firsttext read → BASELINE", e == "BASELINE" and b == 5)
    b, e = _dec(5, 5)
    check("unchanged → without text", e is None and b == 5)
    b, e = _dec(5, 6)
    check("jump counter → TRIGGER", e == "TRIGGER" and b == 6)
    b, e = _dec(6, 2)
    check("decrease counter → RESET", e == "RESET" and b == 2)
    b, e = _dec(6, None)
    check("read failed → unchanged", e is None and b == 6)
    # scenariotechnical note real technical note‌technical note technical note: shot → technical noteandtechnical note possession in same Poll → counter technical note technical note‌technical note
    # in version 3 baseline with possession technical note technical note‌technical noteandtechnical note jump aftertechnical note must technical note technical note
    b1, e1 = _dec(None, 10)              # baseline=10
    b2, e2 = _dec(b1, 10)                # possession technical noteandtechnical note technical note counter technical note
    b3, e3 = _dec(b2, 11)                # countertechnical note shot technical note technical note
    check("scenariotext text possession: jumptext text text text‌text",
          e1 == "BASELINE" and e2 is None and e3 == "TRIGGER",
          f"events={e1},{e2},{e3}")

    print("\n--- 11text5) version 4: text countertext text (GoalHooker.counter_event) ---")
    _gc = GoalHooker.counter_event
    check("None→None → WAIT (still capture text)", _gc(None, None) == ("WAIT", 0))
    check("None→2 → BASELINE (firsttext read valid)", _gc(None, 2) == ("BASELINE", 0))
    check("2→3 → GOAL×1", _gc(2, 3) == ("GOAL", 1))
    check("2→2 → NOCHANGE", _gc(2, 2) == ("NOCHANGE", 0))
    check("3→0 → RESET (withtext newtext without text text)", _gc(3, 0) == ("RESET", 0))
    check("0→2 → GOAL×2 (textand text in text Poll)", _gc(0, 2) == ("GOAL", 2))
    check("limit text jump: 1→9 → text GOAL×3",
          _gc(1, 9) == ("GOAL", GoalHooker.MAX_GOAL_JUMP))
    check("read failed → NOCHANGE", _gc(2, None) == ("NOCHANGE", 0))

    print("\n--- 11text7) version 6: Cave with Sticky First-Capture (without withtext) ---")
    # technical note Cave: code technical notemust technical noteandtechnical note slot technical note
    check("text Cave: code 41 bytetext before from slot in 0x60",
          GoalHooker.CODE_OFFSET + GoalHooker.CAVE_CODE_SIZE <= GoalHooker.DATA_SLOT_OFFSET,
          f"0x20+41={GoalHooker.CODE_OFFSET + GoalHooker.CAVE_CODE_SIZE} ≤ 0x{GoalHooker.DATA_SLOT_OFFSET:X}")
    check("slot + 8 byte inside allocation 128 bytetext",
          GoalHooker.DATA_SLOT_OFFSET + 8 <= GoalHooker.CAVE_ALLOC_SIZE)

    # technical note code with address‌technical note technical note and technical noteistechnical note‌technical note technical note‌technical note‌technical note
    # (Cave real with allocate_near_target technical note target allocation technical note‌ortechnical note
    #  technical note technical note Cave technical note in distancetechnical note 256MB technical note technical note‌technical note until in withtechnical note rel32 withtechnical note)
    _orig = GoalHooker.ORIG_BYTES
    _target = 0x140000000 + 0x19ECBE2
    _cave = _target + 0x10000000
    _code_start = _cave + GoalHooker.CODE_OFFSET
    _slot = _cave + GoalHooker.DATA_SLOT_OFFSET
    _code = GoalHooker._build_capture_code(_orig, _slot, _target, _code_start)
    check("length code Cave = 41 byte", len(_code) == GoalHooker.CAVE_CODE_SIZE,
          f"len={len(_code)}")
    check("instruction original in text Cave text text", bytes(_code[0:7]) == _orig)
    check("push rax/push rcx/pushfq and popfq/pop rcx/pop rax text",
          bytes(_code[7:10]) == b'\x50\x51\x9C' and bytes(_code[33:36]) == b'\x9D\x59\x58')
    # disp32 technical note: from technical note cmp (byte 21) agetechnical note technical note‌technical noteandtechnical note
    _disp = struct.unpack('<i', _code[16:20])[0]
    check("disp32 text to slot text text‌text", _slot == (_code_start + 21) + _disp,
          f"slot==rip(0x{_code_start + 21:X})+0x{_disp:X}")
    # rel8 technical note jne must store technical note‌bytetechnical note technical note technical note technical note (23 → 33)
    check("jne exactly textandtext store text‌bytetext text‌text",
          _code[21] == 0x75 and _code[22] == (33 - 23) & 0xFF,
          f"jne rel8={_code[22]}")
    # rel32 withtechnical note: from technical note jmp (byte 41) agetechnical note technical note‌technical noteandtechnical note
    _rel = struct.unpack('<i', _code[37:41])[0]
    check("jmp to target+7 text‌text", (_code_start + 41) + _rel == _target + 7,
          f"end+jmp=0x{(_code_start + 41) + _rel:X}")
    # Adopt: technical note must same slot technical note from code technical noteandtechnical note technical noteandtechnical note
    _slot_back = GoalHooker._parse_existing_cave_code(_code, _orig)
    check("text Adopt slot text correct istext text‌text", _slot_back == _slot,
          f"parsed={_slot_back:#x}" if _slot_back else "parsed=None")
    # Cave legacy (version 4/5 — capture technical note) technical notemust Adopt technical noteandtechnical note
    _old_cave = bytearray(_orig)
    _old_cave += bytes([0x50, 0x9C, 0x48, 0x89, 0xC8, 0x48, 0xA3]) + struct.pack('<Q', 0xDEAD)
    _old_cave += bytes([0x9D, 0x58, 0xE9]) + struct.pack('<i', 0)
    check("Cave legacy versiontext 4/5 text text‌textandtext (textortext to restart withtext)",
          GoalHooker._parse_existing_cave_code(bytes(_old_cave), _orig) is None)
    check("code broken/textanduntiltext text text‌textandtext",
          GoalHooker._parse_existing_cave_code(b'\x90' * 20, _orig) is None)
    # same technical note for hook Away (technical note technical noteandtechnical note)
    _code_a = GoalHooker._build_capture_code(GoalHooker.AWAY_EXPECTED_BYTES, _slot, _target, _code_start)
    check("text with text hook Away text text text‌text",
          GoalHooker._parse_existing_cave_code(_code_a, GoalHooker.AWAY_EXPECTED_BYTES) == _slot)

    print("\n--- 11text8) version 6: scenariotext «text‌text textnumber» from change counter (without withtext) ---")
    # technical note‌technical notefromtechnical note complete Poll: technical note increment counter must technical note register technical note technical note
    _seq = [(None, 0), (0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 3), (3, 3)]
    _decisions = [GoalHooker.counter_event(p, n)[0] for p, n in _seq]
    check("text increment counter = text text text (4 text textandtext register text‌textandtext)",
          _decisions == ["BASELINE", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE"],
          f"{_decisions}")
    _seq2 = [(None, 0), (0, 0), (0, 1), (1, 1), (1, 2), (2, 2), (2, 1), (1, 2)]
    _dec2 = [GoalHooker.counter_event(p, n)[0] for p, n in _seq2]
    check("reset textandtext counter register text incorrect text‌textfromtext and withtext resume text‌ortext",
          _dec2 == ["BASELINE", "NOCHANGE", "GOAL", "NOCHANGE", "GOAL", "NOCHANGE", "RESET", "GOAL"],
          f"{_dec2}")

    print("\n--- 11text9) version 10: Poll text independent from text‌text pitch + heartbeat [GoalHookPoll] ---")
    # 1) heartbeat: firsttechnical note technical noteandtechnical note always technical note inside withtechnical note technical note after from withtechnical note technical note
    check("gh_due_heartbeat: firsttext textandtext (last=None) always due is",
          gh_due_heartbeat(100.0, None) is True)
    check("gh_due_heartbeat: inside withtext 5 second due is not",
          gh_due_heartbeat(102.0, 100.0) is False
          and gh_due_heartbeat(104.9, 100.0) is False)
    check("gh_due_heartbeat: after from text withtext due text‌textandtext",
          gh_due_heartbeat(105.0, 100.0) is True)
    # 2) technical note time Poll: technical note valid technical note andtechnical note latest time core
    check("gh_pick_poll_time: text valid text moment text is",
          gh_pick_poll_time(45.0, 30.0) == 45.0)
    check("gh_pick_poll_time: text text/None → latest time valid core",
          gh_pick_poll_time(0.0, 30.0) == 30.0 and gh_pick_poll_time(None, 30.0) == 30.0)
    check("gh_pick_poll_time: text‌codetext → 0 (Poll never to‌text text text text‌textandtext)",
          gh_pick_poll_time(None, None) == 0.0 and gh_pick_poll_time(0.0, 0.0) == 0.0)
    # 3) test structuretechnical note technical note Poll: technical noteandtechnical note must before from technical note technical noteand early-continue withtechnical note
    _src_all = open(os.path.abspath(__file__), encoding="utf-8").read()
    _i_def = _src_all.find("def worker_loop")
    _i_next = _src_all.find("\n    def ", _i_def + 10)   # firsttechnical note technical note after from worker_loop
    _wl = _src_all[_i_def:_i_next]
    _n_calls = _wl.count("self._poll_goal_hook(")
    _i_call = _wl.find("self._poll_goal_hook(")
    _i_ball_gate = _wl.find("if not ball or not players")
    _i_geom_gate = _wl.find("if not self.geometry_ready")
    check("Poll text exactly text textandtext in worker_loop text (textandtext legacy text text)",
          _n_calls == 1, f"calls={_n_calls}")
    check("Poll text before from text ball/players is (text text early-continue hidden is not)",
          0 < _i_call < _i_ball_gate,
          f"call={_i_call}, ball_gate={_i_ball_gate}")
    check("Poll text before from text geometry_ready is",
          0 < _i_call < _i_geom_gate,
          f"call={_i_call}, geom_gate={_i_geom_gate}")
    check("time Poll with gh_pick_poll_time text text‌textandtext (fallback time core)",
          "gh_pick_poll_time(" in _wl[_i_call:_i_call + 200])
    # 4) layertechnical note technical note‌technical note: pathtechnical note technical note‌technical note must log technical note withtechnical note
    check("text path failuretext in _poll_goal_hook text‌text is not (log [GoalHookPoll])",
          _src_all.count("[GoalHookPoll]") >= 6,
          f"logs={_src_all.count('[GoalHookPoll]')}")

    print("\n--- 11text10) version 10: textandtext totaltext — _poll_goal_hook real with fake engine ---")
    # technical note C version 5 until 9: poll() totaltechnical note «home/away» technical noteandtechnical note technical note‌technical note and technical note
    # «Home/Away» technical note technical note‌technical noteandtechnical note → WAIT technical note. technical note test «total» untiltechnical note real technical note
    # with technical notetotal real output poll() run technical note‌technical note until technical note totaltechnical note withtechnical note never technical note.
    class _FakePollEngine:
        def __init__(self, states):
            self._it = iter(states)
        def read_goal_counters(self):
            return next(self._it)

    # version 10technical note3 — fake app with «technical note real» _poll_goal_hook and
    # _register_first_hook_goaltechnical note only _register_hook_goal fallback technical note‌technical noteandtechnical note
    # until total chaintechnical note technical note (technical note First-Capture Goal) andtechnical note test technical noteandtechnical note.
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
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 1, "away": 0},  # technical note!
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x1234, "home": 1, "away": 2},  # technical noteand technical note Away
    ]
    _fake_app = _FakeGHApp(_gh_states, _reg_stub)
    try:
        for _i in range(len(_gh_states)):
            MomentumApp._poll_goal_hook(_fake_app, 600.0 + _i)
        check("totaltext poll() textandtext text‌textandtext: BASELINE from home=0/away=0 registered",
              _fake_app.goal_counters["Home"] == 0 and _fake_app.goal_counters["Away"] == 0
              or _fake_app.goal_counters["Home"] == 1,
              f"counters={_fake_app.goal_counters}")
        check("text Home from change RAW (0→1) registered",
              ("Home", 603.0) in _reg_stub, f"registered={_reg_stub}")
        check("textand text Away text‌text registered (1→2 with MAX_GOAL_JUMP)",
              ("Away", 604.0) in _reg_stub, f"registered={_reg_stub}")
        check("text text: Home=1, Away=2 — exactly text RAW",
              _fake_app.goal_counters == {"Home": 1, "Away": 2},
              f"counters={_fake_app.goal_counters}")
        check("text Poll: wait=1 and ok=4 (path WAIT text text text‌textandtext)",
              _fake_app._gh_diag["n_wait"] == 1 and _fake_app._gh_diag["n_ok"] == 4,
              f"diag=wait:{_fake_app._gh_diag['n_wait']} ok:{_fake_app._gh_diag['n_ok']}")
        # version 10technical note3 — First-Capture in technical note scenario (capture technical noteandtechnical note 0-0) technical notemust technical note register technical note withtechnical note
        check("First-Capture textandtext 0-0 only baseline is (text text text‌text register text)",
              len(_reg_stub) == 3 and _fake_app._gh_fc_pending == {"Home": False, "Away": False},
              f"registered={_reg_stub} pending={_fake_app._gh_fc_pending}")
    except StopIteration:
        check("textandtext fake engine complete text text", False, "StopIteration — count Poll text from text‌textis")

    print("\n--- 11text11) version 10text3: First-Capture Goal — text first same momenttext Capture ---")
    # scenariotechnical note user: Goal Hook only with firsttechnical note run instruction technical note Capture technical note‌technical note
    # technical note firsttechnical note Capture possible is exactly simultaneous with technical note first withtechnical note (Home=1, Away=0).
    # beforetechnical note: BASELINE → technical note first technical note technical note‌technical note. technical noteandtechnical note: same moment technical note #1 register technical note‌technical noteandtechnical note and
    # baseline internal 1 technical note‌technical noteandtechnical note technical note 1→2 technical note second technical note technical note‌technical note (without technical noteandwithtechnical note register).
    _fc_states = [
        {"hooked": True, "captured": False, "secondary": True, "rcx": None, "home": None, "away": None},
        # firsttechnical note Capture simultaneous with technical note first Home:
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 1, "away": 0},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 1, "away": 0},
        # technical note second Home — technical noteandtechnical note technical note Counter Tracking (1→2):
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22AA, "home": 2, "away": 0},
    ]
    _fc_stub = []
    _fc_app = _FakeGHApp(_fc_states, _fc_stub)
    try:
        for _i in range(len(_fc_states)):
            MomentumApp._poll_goal_hook(_fc_app, 700.0 + _i)
        check("text #1 Home exactly in momenttext firsttext Capture registered (text baseline)",
              ("Home", 701.0) in _fc_stub, f"registered={_fc_stub}")
        check("text #2 Home from textandtext text 1→2 registered",
              ("Home", 703.0) in _fc_stub, f"registered={_fc_stub}")
        check("text textandwithtext register‌text is not: exactly 2 text for Home",
              len([r for r in _fc_stub if r[0] == "Home"]) == 2 and len(_fc_stub) == 2,
              f"registered={_fc_stub}")
        check("baseline internal after from First-Capture same value RAW is (Home=2)",
              _fc_app.goal_counters == {"Home": 2, "Away": 0},
              f"counters={_fc_app.goal_counters}")
        check("First-Capture only text‌withtext armed textandtext (pending after from firsttext read textandtext text)",
              _fc_app._gh_fc_pending == {"Home": False, "Away": False},
              f"pending={_fc_app._gh_fc_pending}")
    except StopIteration:
        check("textandtext First-Capture complete text text", False, "StopIteration")

    # scenariotechnical note technical noteandtechnical note: firsttechnical note Capture simultaneous with technical note first «Away» (Home=0, Away=1)
    _fca_states = [
        {"hooked": True, "captured": False, "secondary": True, "rcx": None, "home": None, "away": None},
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22BB, "home": 0, "away": 1},
    ]
    _fca_stub = []
    _fca_app = _FakeGHApp(_fca_states, _fca_stub)
    try:
        for _i in range(len(_fca_states)):
            MomentumApp._poll_goal_hook(_fca_app, 800.0 + _i)
        check("text #1 Away in momenttext Capture registered (Home=0, Away=1)",
              _fca_stub == [("Away", 801.0)], f"registered={_fca_stub}")
        check("baseline: Home=0 without text Away=1",
              _fca_app.goal_counters == {"Home": 0, "Away": 1},
              f"counters={_fca_app.goal_counters}")
    except StopIteration:
        check("textandtext First-Capture Away complete text text", False, "StopIteration")

    # scenariotechnical note value firsttechnical note > 1: technical note technical note with limit MAX_GOAL_JUMP
    _fcc_states = [
        {"hooked": True, "captured": True, "secondary": True, "rcx": 0x22CC, "home": 2, "away": 0},
    ]
    _fcc_stub = []
    _fcc_app = _FakeGHApp(_fcc_states, _fcc_stub)
    MomentumApp._poll_goal_hook(_fcc_app, 900.0)
    check("value firsttext 2 → text textand text (text text) registered",
          _fcc_stub == [("Home", 900.0), ("Home", 900.0)],
          f"registered={_fcc_stub}")
    check("baseline after from First-Capture text = value RAW",
          _fcc_app.goal_counters == {"Home": 2, "Away": 0},
          f"counters={_fcc_app.goal_counters}")

    print("\n--- 11text12) version 10text3: Match Lifecycle — rule text HT / withtext new / minutetext 6 ---")
    # technical note‌technical notefrom technical noteandtechnical note technical note technical note worker: flag → in firsttechnical note PLAYING technical note
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

    # --- test technical notewithtechnical note 1: HT correct ---
    _t1 = [(44 * 60 + 58, True), (2700, True), (2734, True), (2734, False),
           (2700, False), (2700, True), (2701, True)]
    _v1, _h1 = _simulate(_t1)
    check("test 1 — HT correct: exactly text HT and second half from 45:00",
          _v1 == ["HT"] and _h1 == 2, f"verdicts={_v1} half={_h1}")

    # --- test technical notewithtechnical note 2: start withtechnical note new (technical note HT newtechnical note + technical note NEW_MATCH) ---
    _t2 = [(5400, False), (0, False), (0, True), (1, True), (2, True), (3, True)]
    _v2, _h2 = _simulate(_t2)
    check("test 2 — 90:00→0:00 = NEW_MATCH (text HT text)",
          _v2 == ["NEW_MATCH"] and not any(v == "HT" for v in _v2),
          f"verdicts={_v2}")
    check("test 2 — NEW_MATCH text when HT withtext before from text text and half still 1 is",
          classify_resume_after_drop(5400.0, 0.0, 1) == "NEW_MATCH")

    # --- test technical notewithtechnical note 3: withtechnical note second without incorrect HT (0:00..6:00 → 10:00) ---
    _t3 = [(0, True), (60, True), (120, True), (180, True), (240, True),
           (300, True), (360, True), (600, True)]
    _v3, _h3 = _simulate(_t3)
    check("test 3 — textandtext 0..6:00→10:00: text text HT text register text (HT=0)",
          len(_v3) == 0 and _h3 == 1, f"verdicts={_v3}")
    check("test 3 — withtextfromtext minutetext 6: decrease textandtext with prev<45:00 never HT is not",
          classify_resume_after_drop(370.0, 360.0, 1) == "KEPT")
    check("test 3 — 03:00→02:59 (resync 1 second‌text) text text text‌textandtext → HT is not",
          should_flag_time_drop(180.0, 179.0, 5.0) is False)
    check("test 3 — jump textand to windowtext untiltext≈text = NEW_MATCH (text HT)",
          should_flag_time_drop(180.0, 170.0, 5.0) is True
          and classify_resume_after_drop(180.0, 170.0, 1) == "NEW_MATCH")

    # --- rule technical note HT: boundarytechnical note ---
    check("rule text: prev=45:34text resume=45:00 → HT",
          classify_resume_after_drop(2734.0, 2700.0, 1) == "HT")
    check("rule text: resume=46:20 (inside textandtext) → HT",
          classify_resume_after_drop(2780.0, 2780.0, 1) == "HT")
    check("rule text: prev<45:00 (text 39:00) → never HT",
          classify_resume_after_drop(2340.0, 2700.0, 1) == "KEPT")
    check("rule text: resume andtext withtext (10:00 after from 45:40) → HT is not",
          classify_resume_after_drop(2740.0, 600.0, 1) == "KEPT")
    check("rule text: second half (half=2) text text‌andtext HT text‌textfromtext",
          classify_resume_after_drop(5400.0, 2700.0, 2) == "KEPT")
    check("rule text: untiltext≈text text text HT is (90:xx→0:00 with half=1 text withtext new is)",
          classify_resume_after_drop(5400.0, 30.0, 1) == "NEW_MATCH")

    # --- Watchdog withtechnical note new (independent from technical note decrease time) ---
    check("watchdog: match until 90:00 text text + PLAYING@0:00 → withtext new",
          is_new_match_watchdog(5400.0, 0.0, 180.0, 5.0) is True)
    check("watchdog: match until 90:00 + PLAYING@1:40 (textandtext text) → withtext new",
          is_new_match_watchdog(5400.0, 100.0, 180.0, 5.0) is True)
    check("watchdog: start text match (untiltext inside window) → text‌text",
          is_new_match_watchdog(120.0, 100.0, 180.0, 5.0) is False
          and is_new_match_watchdog(183.0, 179.0, 180.0, 5.0) is False)
    check("watchdog: minute 6 withtext second → text‌text",
          is_new_match_watchdog(370.0, 360.0, 180.0, 5.0) is False)

    # --- structure: worker_loop andtechnical note from State Machine istechnical note technical note‌technical note ---
    check("worker_loop from classify_resume_after_drop and watchdog istext text‌text",
          "classify_resume_after_drop(" in _wl and "is_new_match_watchdog(" in _wl)

    # --- 10technical note3 in level technical noteandtechnical noteandtechnical note: reset withtechnical note new technical note‌technical note technical note technical note technical note‌technical note ---
    _mom3 = MomentumEngine(MomentumScoringConfig())
    _mom3.update(120.0)
    _mom3.add_hook_goal_marker("Home", 120.0, 1)
    _mom3.set_half_break(_mom3.cfg.HT_GAP_DISPLAY_SECONDS, 2700.0)
    _mom3.reset(0.0)
    check("withtext new in level textandtextandtext: history/marker/HT/offset completetext text and from 0:00 start text‌textandtext",
          len(_mom3.history) == 1
          and _mom3.hook_goal_marker_count() == 0
          and _mom3.ht_break is None
          and abs(_mom3.display_offset) < 1e-9
          and _mom3.half_number == 1
          and abs(_mom3.history[0]["game_time"]) < 1e-9)

    print("\n--- 11text13) version 10text4: Pipeline Health — re-arm possession / log file / Warning STALE ---")
    # 1) technical note re-arm possession (untiltechnical note technical note — Watchdog technical noteandtechnical note)
    check("re-arm: poss=None + PLAYING + text textand + stale text + throttle withtext → text",
          possession_rearm_needed(False, "PLAYING", True, 25.0, True) is True)
    check("re-arm: poss valid → text",
          possession_rearm_needed(True, "PLAYING", True, 999.0, True) is False)
    check("re-arm: text PLAYING (Pause/Replay/menu) → text",
          possession_rearm_needed(False, "STOP", True, 999.0, True) is False)
    check("re-arm: text text (without text) → text",
          possession_rearm_needed(False, "PLAYING", False, 999.0, True) is False)
    check("re-arm: stale text (text threshold) → text",
          possession_rearm_needed(False, "PLAYING", True, 5.0, True) is False)
    check("re-arm: throttle text (text text) → text",
          possession_rearm_needed(False, "PLAYING", True, 999.0, False) is False)
    # 2) Warning countertechnical note frozen (STALE)
    check("STALE: countertext pass 60 second unchanged in PLAYING → Warning",
          should_warn_frozen_counter(60.0, "PLAYING") is True)
    check("STALE: in STOP Warning text‌text (text in stop text is)",
          should_warn_frozen_counter(600.0, "STOP") is False)
    check("STALE: text threshold → text",
          should_warn_frozen_counter(10.0, "PLAYING") is False)
    # 3) DebugLogger: write / heartbeat / technical note file
    import tempfile as _tmpmod
    with _tmpmod.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "dbg.txt")
        _d = DebugLogger(_p, enabled=True, heartbeat_sec=0.0, max_bytes=1 << 20)
        _d.event("T", a=1, b="x")
        _d.write("T2", "message test")
        _hb1 = _d.heartbeat_due(100.0)
        _hb2 = _d.heartbeat_due(100.0)
        _d.close()
        _txt = open(_p, encoding="utf-8").read()
        check("DebugLogger: line textandtext and textin Session in file registered",
              "[T] a=1 b=x" in _txt and "SESSION" in _txt and "message test" in _txt,
              f"len={len(_txt)}")
        check("DebugLogger: heartbeat with thresholdtext text text withtext due is",
              _hb1 is True and _hb2 is True)
        check("DebugLogger: text disabled text filetext text‌textfromtext",
              not os.path.exists(os.path.join(_td, "off.txt"))
              if not DebugLogger(os.path.join(_td, "off.txt"), enabled=False).enabled else False)
    with _tmpmod.TemporaryDirectory() as _td:
        _p = os.path.join(_td, "dbg2.txt")
        _d = DebugLogger(_p, enabled=True, heartbeat_sec=10.0, max_bytes=400)
        for _i in range(60):
            _d.write("FILL", "x" * 20)
        _d.close()
        check("DebugLogger: text file text textandtext from max_bytes (versiontext .1 text text)",
              os.path.exists(_p + ".1"),
              f"main={os.path.getsize(_p) if os.path.exists(_p) else 0}B")
    # 4) PossessionHooker.reset_capture — technical note‌technical note technical note side technical noteandtechnical note (without h_process technical note technical note)
    _ph = PossessionHooker()
    _ph.captured_address = 0x12345
    _ph.reset_capture(None)
    check("PossessionHooker.reset_capture: text captured_address text text",
          _ph.captured_address is None)
    _ph2 = PossessionHooker()
    _ph2.cave_address = 0xBEEF   # h_process=None → only technical note technical note technical note technical note‌technical noteandtechnical note crash technical note
    _ph2.captured_address = 0x999
    _ph2.reset_capture(None)
    check("PossessionHooker.reset_capture: with cave_address and h_process=None text text‌text",
          _ph2.captured_address is None)
    # 5) fmt_ptr / freeze_seconds
    check("fmt_ptr: None/0 → '-' and address → hex",
          fmt_ptr(None) == "-" and fmt_ptr(0) == "-" and fmt_ptr(0x1234) == "0x1234")
    check("freeze_seconds: without text → -1 and with text → textandtext",
          freeze_seconds(None, 10.0) == -1.0
          and abs(freeze_seconds(4.0, 10.0) - 6.0) < 1e-9)
    # 6) structure: worker andtechnical note health-tick technical note before from technical note‌technical note technical note technical note‌technical note and technical note‌technical note technical note
    check("worker_loop version 10text4: _pipeline_health_tick before from text ball/players text text text‌textandtext",
          _wl.find("_pipeline_health_tick(") != -1
          and _wl.find("_pipeline_health_tick(") < _wl.find('if not ball or not players:'))
    check("worker_loop version 10text4: countertext text ball_players/not_playing/pass_trig/shot_trig textandtextandtext is",
          '_gate_counts["ball_players"]' in _wl and '_gate_counts["not_playing"]' in _wl
          and '_gate_counts["pass_trig"]' in _wl and '_gate_counts["shot_trig"]' in _wl)
    import inspect as _inspect
    _pr_src = _inspect.getsource(MomentumApp._perform_reset)
    # versiontechnical note 10technical note18 — re-arm possession technical note from path smart rearm_possession_capture
    # technical note‌technical note (technical noteandtechnical note technical note reset_possession_capture technical note technical note technical note‌technical note)
    check("perform_reset version 10text4: capture possession text again armed text‌textandtext",
          ("rearm_possession_capture" in _pr_src
           or "reset_possession_capture" in _pr_src)
          and "MATCH_RESET" in _pr_src)

    print("\n--- 12) textandtextfromtext text‌text‌text (NaN gap HT text text‌textandtext) ---")
    _series = [0.0, 0.0, 5.0, 0.0, 0.0, float('nan'), float('nan'), 0.0, 0.0, 7.0, 0.0, 0.0]
    _sm = gaussian_smooth(_series, 1.0)
    _nan_idx = [i for i, v in enumerate(_sm) if v != v]
    check("NaN text only in text textandtext text‌text", _nan_idx == [5, 6], f"nan_idx={_nan_idx}")
    check("text first until texttotext gap value text text",
          all(_sm[i] == _sm[i] for i in range(5)) and abs(_sm[4]) < 5.0)
    check("text second until texttotext gap value text text",
          all(_sm[i] == _sm[i] for i in range(7, 12)))

    # =============================================================
    print("\n--- 13) smoothing bell-shaped (versiontext 10text27 — text‌text text 2017) ---")
    # =============================================================
    check("text‌text: GAUSSIAN_SIGMA=20 and TV_SMOOTH_SIGMA_SEC=55 (text 2017)",
          cfg.GAUSSIAN_SIGMA == 20.0 and TV_SMOOTH_SIGMA_SEC == 55.0,
          f"sigma={cfg.GAUSSIAN_SIGMA}, tv_sigma={TV_SMOOTH_SIGMA_SEC}")
    # peaktechnical note technical noteandtechnical note technical note technical note with technical note technical note‌technical note: technical noteandtechnical note technical note + technical note technical note‌technical note
    _imp = [0.0] * 200 + [100.0] + [0.0] * 199
    _sm20 = gaussian_smooth(_imp, 40.0)   # 20s / eff_dt=0.5s → 40 sample
    _sm16 = gaussian_smooth(_imp, 32.0)   # 16s (value beforetechnical note)
    check("bell-shaped: textandtext peak with σ=20s from σ=16s text‌text/text is",
          max(_sm20) < max(_sm16),
          f"peak20={max(_sm20):.4f} < peak16={max(_sm16):.4f}")
    check("bell-shaped: text peak with σ=20s text‌text is (d=80 sample)",
          _sm20[280] > _sm16[280],
          f"sm20[280]={_sm20[280]:.4f} > sm16[280]={_sm16[280]:.4f}")
    check("bell-shaped: text sample‌text text/NaN text‌textandtext",
          all(v == v and v >= 0.0 for v in _sm20))

    # =============================================================
    print("\n--- Test RC: red card — pointer 3 leveltext + assignment z=40 + render (versiontext 10text27) ---")
    # =============================================================
    # scenariotechnical note technical note with «technical note REAL» MomentumApp technical noteandtechnical note technical note real
    # Momentum (only engine/technical notewithtechnical note technical note) — same lightweight test 11technical note10.

    class _FakeRCEngine:
        def __init__(self, value=None):
            self.value = value

        def read_red_card_counter(self):
            return self.value

    class _FakeRCApp:
        """text textandtext with text real red card textandtext MomentumEngine real."""
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

    # --- RC1: chaintechnical note pointer 3 leveltechnical note (memorytechnical note technical note — technical note technical noteandtechnical note safe_read) ---
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
        check("RC1: read chaintext red card (base+0x36F3F88→+350→+4E0)",
              engRC.read_red_card_counter() == 0,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P2 + 0x4E0] = bytes([2])
        check("RC1b: increment counter 1 bytetext from chain textandtext text‌textandtext",
              engRC.read_red_card_counter() == 2,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P2 + 0x4E0] = bytes([255])
        check("RC1c: value 255 (limit u8) valid textandtext text‌textandtext",
              engRC.read_red_card_counter() == 255,
              f"val={engRC.read_red_card_counter()}")
        _rc_mem[_RC_P1 + 0x350] = struct.pack("<Q", 0)
        _rc_mem[_RC_P2 + 0x4E0] = bytes([2])
        check("RC1d: chaintext failuretext (pointer text) → None",
              engRC.read_red_card_counter() is None)
        _rc_mem[_BASE + GameEngine.RED_CARD_PTR_OFFSET] = struct.pack("<Q", 0x10)
        check("RC1e: pointer text invalid (<0x10000) → None",
              engRC.read_red_card_counter() is None)
        engRC.is_ready = False
        check("RC1f: without connection (is_ready=False) → None",
              engRC.read_red_card_counter() is None)
        engRC.is_ready = True
    finally:
        _g["safe_read"] = _orig_safe_read

    # --- RC2: baseline + increment → pending with time/technical note frozentechnical note ---
    fake_eng = _FakeRCEngine(2)
    fa = _FakeRCApp(fake_eng)
    fa.momentum.display_offset = 300.0      # technical note‌technical notefromtechnical note technical note displaytechnical note
    fa._poll_red_card(600.0, [])
    check("RC2: firsttext read = BASELINE (without card)",
          fa._rc_state["baseline"] == 2
          and not fa._rc_state["pending"]
          and fa.momentum.red_card_marker_count() == 0,
          f"baseline={fa._rc_state['baseline']}")
    fake_eng.value = 3
    fa._poll_red_card(610.0, [])
    _pd0 = fa._rc_state["pending"][0] if fa._rc_state["pending"] else {}
    check("RC2b: increment 2→3 text card in text assignment text‌textfromtext",
          len(fa._rc_state["pending"]) == 1,
          f"pending={len(fa._rc_state['pending'])}")
    check("RC2c: time/text/disp momenttext textandtext frozen text‌textandtext",
          _pd0.get("issued_t") == 610.0
          and _pd0.get("issued_disp") == 910.0
          and _pd0.get("issued_half") == 1,
          f"pd={_pd0}")

    # --- RC3: assignment — player Home to z=40 technical note‌technical noteandtechnical note ---
    players = [{"seat": i,
                "team": ("Home" if i <= 11 else "Away"),
                "x": -10.0, "z": 0.0}
               for i in range(1, 23)]
    players[4]["z"] = 40.3                  # player Home technical note technical note
    fa._poll_red_card(618.0, players)
    _mk0 = fa.momentum.get_hook_red_card_markers()
    check("RC3: card to team Home text and text registered",
          len(_mk0) == 1 and _mk0[0]["team"] == "Home",
          f"markers={_mk0}")
    check("RC3b: time text = momenttext textandtext (text momenttext detection)",
          _mk0[0]["game_time"] == 610.0
          and _mk0[0]["disp_time"] == 910.0,
          f"gt={_mk0[0]['game_time']} disp={_mk0[0]['disp_time']}")
    check("RC3c: seat text registered (text card aftertext is not)",
          5 in fa._rc_state["exiles"],
          f"exiles={sorted(fa._rc_state['exiles'])}")
    check("RC3d: pending empty text + _tv_dirty for render immediate",
          not fa._rc_state["pending"] and fa._tv_dirty)
    fa.momentum.display_offset = 999.0       # technical note after from technical noteandtechnical note technical noteandtechnical note technical note
    check("RC3e: disp_time frozentext withtext text‌text (text new text‌impact)",
          fa.momentum.get_hook_red_card_markers()[0]["disp_time"] == 910.0)

    # --- RC4: card second — Awaytechnical note technical note legacy technical note is not ---
    fake_eng.value = 4
    fa._poll_red_card(1200.0, players)      # only technical note legacy in z=40
    check("RC4: text legacy (seat 5) assignment text‌textandtext",
          len(fa._rc_state["pending"]) == 1,
          f"pending={len(fa._rc_state['pending'])}")
    players[15]["z"] = 39.8                 # player Away technical note technical note
    fa._poll_red_card(1212.0, players)
    _mk1 = fa.momentum.get_hook_red_card_markers()
    check("RC4b: card second to Away text text (time textandtext textandtext)",
          len(_mk1) == 2 and _mk1[1]["team"] == "Away"
          and _mk1[1]["game_time"] == 1200.0,
          f"markers={[(m['team'], m['game_time']) for m in _mk1]}")

    # --- RC5: tolerance z ---
    fa5 = _FakeRCApp(_FakeRCEngine(4))
    fa5._poll_red_card(2000.0, [])          # baseline = 4
    fa5.engine.value = 5
    fa5._poll_red_card(2005.0, [])
    p_bad = [{"seat": 30, "team": "Away", "x": 0.0, "z": 34.5},
             {"seat": 31, "team": "Home", "x": 0.0, "z": 45.6}]
    fa5._poll_red_card(2010.0, p_bad)
    check("RC5: z text from tolerance (34.5 / 45.6) text is not",
          len(fa5._rc_state["pending"]) == 1,
          f"pending={len(fa5._rc_state['pending'])}")
    p_ok = [{"seat": 32, "team": "Home", "x": 0.0, "z": 36.0}]
    fa5._poll_red_card(2015.0, p_ok)
    check("RC5b: z=36 (boundary tolerance) text is",
          len(fa5.momentum.get_hook_red_card_markers()) == 1
          and fa5.momentum.get_hook_red_card_markers()[0]["team"] == "Home",
          f"markers={fa5.momentum.get_hook_red_card_markers()}")

    # --- RC6: technical note assignment ---
    fa6 = _FakeRCApp(_FakeRCEngine(5))
    fa6._poll_red_card(3000.0, [])          # baseline = 5
    fa6.engine.value = 6
    fa6._poll_red_card(3010.0, [])
    check("RC6: card textintext in text text‌text",
          len(fa6._rc_state["pending"]) == 1)
    fa6._poll_red_card(3010.0 + RC_WATCH_WINDOW_S + 1.0, [])
    check("RC6b: text time withtext → card without text text text",
          not fa6._rc_state["pending"]
          and fa6._rc_diag["n_timeout"] == 1
          and fa6.momentum.red_card_marker_count() == 0,
          f"timeout={fa6._rc_diag['n_timeout']}")

    # --- RC7: decrease technical note counter ---
    fa7 = _FakeRCApp(_FakeRCEngine(6))
    fa7._poll_red_card(4000.0, [])          # baseline = 6
    fa7.engine.value = 3                    # decrease technical noteortechnical note withtechnical note
    fa7._poll_red_card(4010.0, [])
    check("RC7: decrease textortext withtext text text text‌textandtext (baseline text)",
          fa7._rc_state["baseline"] == 6,
          f"baseline={fa7._rc_state['baseline']}")
    fa7.engine.value = 7
    fa7._poll_red_card(4020.0, [])
    check("RC7b: increment aftertext from baseline text text card text‌textfromtext",
          len(fa7._rc_state["pending"]) == 1,
          f"pending={len(fa7._rc_state['pending'])}")

    # --- RC8: reset in windowtechnical note withtechnical note new ---
    fa8 = _FakeRCApp(_FakeRCEngine(7))
    fa8._poll_red_card(5000.0, [])          # baseline = 7
    fa8.engine.value = 0
    fa8._poll_red_card(10.0, [])            # t=10 < NEW_GAME_MAX_START
    check("RC8: decrease in windowtext withtext new reset text text‌textandtext",
          fa8._rc_state["baseline"] == 0,
          f"baseline={fa8._rc_state['baseline']}")

    # --- RC9: jump technical note ---
    fa9 = _FakeRCApp(_FakeRCEngine(3))
    fa9._poll_red_card(6000.0, [])          # baseline = 3
    fa9.engine.value = 50                   # jump 47 > RC_MAX_JUMP
    fa9._poll_red_card(6010.0, [])
    check("RC9: jump > RC_MAX_JUMP rebaseline without register card",
          fa9._rc_state["baseline"] == 50
          and not fa9._rc_state["pending"]
          and fa9.momentum.red_card_marker_count() == 0,
          f"baseline={fa9._rc_state['baseline']}")

    # --- RC10: reset match technical note technical note technical note technical note‌technical note ---
    faR = _FakeRCApp(_FakeRCEngine(0))
    faR.momentum.add_hook_red_card_marker("Away", 100.0, 1)
    faR.momentum.add_hook_goal_marker("Home", 200.0, 1)
    faR.momentum.reset(0.0)
    check("RC10: momentum.reset text card and text text text text‌text",
          faR.momentum.red_card_marker_count() == 0
          and faR.momentum.hook_goal_marker_count() == 0)

    # --- RC11: icon card (technical note in code) ---
    ic = build_red_card_icon()
    check("RC11: icon card RGBA text text‌textandtext",
          ic is not None and ic.ndim == 3 and ic.shape[2] == 4,
          f"shape={None if ic is None else ic.shape}")
    if ic is not None:
        _ih, _iw = ic.shape[:2]
        check("RC11b: ratio text text sampletext user (≈0.628)",
              abs(_iw / _ih - RED_CARD_ASPECT_W_H) < 0.02,
              f"{_iw}x{_ih} → {_iw / _ih:.3f}")
        _c = ic[_ih // 2, _iw // 2]
        check("RC11c: text text textcolor and text",
              _c[0] > 0.85 and _c[1] < 0.15 and _c[2] < 0.2
              and _c[3] > 0.98,
              f"rgba={_c.round(3)}")
        check("RC11d: textandtext‌text text (card textandtext‌text without text)",
              ic[1, 1, 3] < 0.55 and ic[-2, -2, 3] < 0.55,
              f"a_tl={ic[1, 1, 3]:.2f} a_br={ic[-2, -2, 3]:.2f}")
        _top = ic[int(_ih * 0.18), _iw // 2]
        _bot = ic[int(_ih * 0.82), _iw // 2]
        check("RC11e: textortext textandtext (withtext textandtext‌text from below)",
              _top[0] > _bot[0] + 0.02,
              f"top={_top[0]:.3f} bot={_bot[0]:.3f}")

    # --- RC12-RC14: render technical note‌pathtechnical note (chart original + TV + scenetechnical note GPU) ---
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
        check("RC12: TV — textand icon card render text (Away + Home)",
              len(_rc_imgs) == 2 and len(_rc_anchors) == 2,
              f"icons={len(_rc_imgs)} anchors={len(_rc_anchors)}")
        check("RC12b: TV — textand line card (core) with same istext text",
              len(_rc_cores) == 2, f"cores={len(_rc_cores)}")
        check("RC12c: TV — text text unchanged text",
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
        check("RC12d: TV — card Away text line text (y>zero_y=486)",
              _away_y is not None and _away_y > 486.0,
              f"away_y={_away_y}")
        check("RC12e: TV — card Home withtext line text (y<zero_y=486)",
              _home_y is not None and _home_y < 486.0,
              f"home_y={_home_y}")
        check("RC12f: TV — counter‌text info card text text",
              _info.get("rc_cards") == 2 and _info.get("rc_lines") == 2,
              f"rc_cards={_info.get('rc_cards')} "
              f"rc_lines={_info.get('rc_lines')}")

        # --- chart original ---
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
        check("RC13: chart original — textand icon card (AnnotationBbox)",
              len(_rc_img2) == 2 and len(_rc_anchor2) == 2,
              f"icons={len(_rc_img2)} anchors={len(_rc_anchor2)}")
        check("RC13b: chart original — textand line card",
              len(_rc_core2) == 2, f"cores={len(_rc_core2)}")
        _home_ln = [a for a in _rc_anchor2
                    if _gid_of(a) == "rc_card_1"]
        _away_ln = [a for a in _rc_anchor2
                    if _gid_of(a) == "rc_card_0"]
        check("RC13c: chart original — Home withtext (y>0) / Away below (y<0)",
              _home_ln and _away_ln
              and _home_ln[0].get_ydata()[0] > 0
              and _away_ln[0].get_ydata()[0] < 0,
              f"home_y={_home_ln[0].get_ydata()[0] if _home_ln else None} "
              f"away_y={_away_ln[0].get_ydata()[0] if _away_ln else None}")

        # --- scenetechnical note GPU ---
        _scene = build_gpu_graph_scene(momTV, MomentumScoringConfig(),
                                       "half", "#e63946", "#f5f5f5")
        check("RC14: scenetext GPU text text‌textandtext", isinstance(_scene, dict),
              f"scene={'OK' if isinstance(_scene, dict) else None}")
        if isinstance(_scene, dict):
            _ic_shape = build_red_card_icon().shape[:2]
            _rc_tex = [it for it in _scene["items"]
                       if it.get("kind") == "tex"
                       and tuple(it.get("size", ()))
                       == (int(_ic_shape[1]), int(_ic_shape[0]))]
            check("RC14b: scenetext GPU — textand text card (textfromtext icon)",
                  len(_rc_tex) == 2,
                  f"rc_tex={len(_rc_tex)}")
            _rc_edges = [it for it in _scene["items"]
                         if it.get("kind") == "edge"
                         and it.get("color4") == (1.0, 1.0, 1.0, 1.0)]
            check("RC14c: scenetext GPU — line‌text text text card textandtextandtext",
                  len(_rc_edges) >= 4,
                  f"white_edges={len(_rc_edges)}")
    finally:
        _g["tv_load_background"] = _orig_bg_load

    # --- RC15: archive ---
    momAR = MomentumEngine(MomentumScoringConfig())
    momAR.history.append({"game_time": 0.0, "disp_time": 0.0,
                          "home": 0.0, "away": 0.0, "net": 0.0,
                          "wall": 1.0, "phase": None})
    momAR.add_hook_red_card_marker("Away", 2520.0, 2,
                                   disp_time=2820.0)
    _data = collect_match_events(momAR)
    check("RC15: archive text red_card_markers is",
          len(_data.get("red_card_markers") or []) == 1,
          f"n={len(_data.get('red_card_markers') or [])}")
    check("RC15b: counts.red_card_markers correct is",
          (_data.get("counts") or {}).get("red_card_markers") == 1)
    _arch = _ArchiveEngine(_data)
    check("RC15c: textandtextandtext texttotext archive text card text withtext‌textfromtext",
          len(_arch.red_card_markers) == 1
          and _arch.red_card_markers[0]["team"] == "Away")
    _arch2 = _ArchiveEngine({"history": momAR.history})   # archive legacy
    check("RC15d: archive legacy without red_card_markers text compatible is",
          _arch2.red_card_markers == [])

    # --- RC16: technical note Worker/Reset (withtechnical note technical noteandtechnical note — lightweight test 11technical note13) ---
    import inspect as _inspect
    _src_wl_rc = _inspect.getsource(MomentumApp.worker_loop)
    _i_pl = _src_wl_rc.find("players = self.engine.read_players()")
    _i_rc = _src_wl_rc.find("self._poll_red_card(")
    check("RC16: worker after from read players poll card text text text‌text",
          0 < _i_pl < _i_rc, f"players@{_i_pl} rc@{_i_rc}")
    _i_gate = _src_wl_rc.find('if not ball or not players:')
    check("RC16b: poll card before from text ball/players run text‌textandtext",
          0 < _i_rc < _i_gate, f"rc@{_i_rc} gate@{_i_gate}")
    _src_pr_rc = _inspect.getsource(MomentumApp._perform_reset)
    check("RC16c: _perform_reset andtext card text text text‌text",
          "_rc_state" in _src_pr_rc)
    _src_ms = _inspect.getsource(MomentumApp.read_match_state) \
        if hasattr(MomentumApp, "read_match_state") else ""
    check("RC16d: detection PLAYING/STOP unchanged (text legacy text text)",
          "MATCH_STATE_OFFSET" in _inspect.getsource(GameEngine.read_match_state)
          and "128" in _inspect.getsource(GameEngine.read_match_state),
          "read_match_state = byte andtext 128/129")

    # --- Test TS: display technical note technical noteagetechnical note‌technical note (v10.28 — technical noteandtechnical note v1.3 from 2017) ---
    print("\n--- Test TS: cycletext text text display (SHOW → confirm/retry) ---")
    _ts_settings = dict(TV_SNAP_DEFAULTS)
    _ts_settings.update({"h1_enabled": True, "h1_minute": 43,
                         "h2_enabled": True, "h2_minute": 85,
                         "et_enabled": False, "et_minute": 116,
                         "end_enabled": True,
                         "show_seconds": 5, "end_seconds": 5,
                         "permanent_save": False, "timestamp": False})
    _ts = TVSnapshotEngine(_ts_settings)
    _ts.reset_match(1000.0)

    # TS1: technical note firsttechnical note — structure technical note
    check("TS1: mid state text is (show_state/retries/last_fail)",
          all(set(("show_state", "retries", "last_fail",
                   "show_req_wall", "retry_after_wall")) <= set(_ts.mid[k])
              for k in _ts.mid)
          and _ts.mid["h1"]["show_state"] is None
          and _ts.mid["h1"]["shown"] is False)
    check("TS1b: end state with pend/fails start text‌textandtext",
          all(_ts.end[k].get("pend") is None and _ts.end[k].get("fails") == 0
              for k in _ts.end))

    # TS2: technical note to minutetechnical note target only «request» technical note‌technical note — technical note technical note
    _acts = _ts.tick(43 * 60.0, "PLAYING", 1, 1001.0)
    check("TS2: show in minutetext target textin and «request» register text‌textandtext",
          ("show", "h1") in _acts
          and _ts.mid["h1"]["show_state"] == "requested"
          and _ts.mid["h1"]["shown"] is False)
    _acts2 = _ts.tick(43 * 60.0 + 5.0, "PLAYING", 1, 1002.0)
    check("TS2b: without confirmationtext text aftertext show fresh text‌text",
          ("show", "h1") not in _acts2
          and _ts.mid["h1"]["show_state"] == "requested")

    # TS3: technical note confirmation → failed → technical note technical note automatic technical note from Backoff
    _acts3 = _ts.tick(43 * 60.0 + 6.0, "PLAYING", 1,
                      1001.0 + TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0)
    check("TS3a: text confirmation text → failed with text confirm-timeout",
          ("show", "h1") not in _acts3
          and _ts.mid["h1"]["show_state"] == "failed"
          and _ts.mid["h1"]["last_fail"] == "confirm-timeout")
    _acts3b = _ts.tick(43 * 60.0 + 6.5, "PLAYING", 1,
                       1001.0 + TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0
                       + TV_SNAP_SHOW_RETRY_BACKOFF_SEC + 1.0)
    check("TS3b: text from Backoff text text textin text‌textandtext",
          ("show", "h1") in _acts3b
          and _ts.mid["h1"]["retries"] == 1
          and _ts.mid["h1"]["show_state"] == "requested")

    # TS4: fail_show technical note → Backoff → technical note technical note
    check("TS4a: fail_show request text failure‌textandtext text‌text",
          _ts.fail_show("h1", 2000.0, "test-fail") is True
          and _ts.mid["h1"]["show_state"] == "failed"
          and _ts.mid["h1"]["last_fail"] == "test-fail")
    _acts4 = _ts.tick(43 * 60.0 + 7.0, "PLAYING", 1,
                      2000.0 + TV_SNAP_SHOW_RETRY_BACKOFF_SEC + 1.0)
    check("TS4b: text from Backoff again show textin text‌textandtext",
          ("show", "h1") in _acts4 and _ts.mid["h1"]["retries"] == 2)
    check("TS4c: show_attempt numbertext text text text‌text",
          _ts.show_attempt("h1") == 3)

    # TS5: confirm_shown → technical note technical note
    check("TS5: confirm_shown totaltext text text text‌text",
          _ts.confirm_shown("h1") is True
          and _ts.mid["h1"]["show_state"] == "visible"
          and _ts.mid["h1"]["shown"] is True)
    check("TS5b: confirmation again text‌impact is",
          _ts.confirm_shown("h1") is False)
    check("TS5c: fail text from text text‌impact is",
          _ts.fail_show("h1", 2100.0, "late") is False)

    # TS6: limit technical note‌technical note → abandoned (cycletechnical note timeout→backoff→retry until limit)
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
    check("TS6: limit Retry → show_abandoned + shown=True (cycle text‌text)",
          _abandoned_seen
          and _ts6.mid["h1"]["show_state"] == "abandoned"
          and _ts6.mid["h1"]["shown"] is True
          and _ts6.mid["h1"]["retries"] == TV_SNAP_SHOW_MAX_RETRIES)
    _a6b = _ts6.tick(50 * 60.0, "PLAYING", 1, _now6 + 5.0)
    check("TS6b: text from abandoned text show textin text‌textandtext",
          ("show", "h1") not in _a6b
          and ("show_abandoned", "h1") not in _a6b)

    # TS7: match end — pend + confirm_show_end
    _ts7 = TVSnapshotEngine(dict(_ts_settings))
    _ts7.reset_match(4000.0)
    _a7 = []
    _w7 = 4000.0
    _a7 += _ts7.tick(91 * 60.0, "STOP", 2, _w7)
    for _i7 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w7 += 1.0
        _a7 += _ts7.tick(91 * 60.0, "STOP", 2, _w7)
    check("TS7: show_end with pend textin text‌textandtext",
          ("show_end", "end90") in _a7
          and _ts7.end["end90"]["pend"] is not None
          and _ts7.end["end90"]["shows"] == 1)
    check("TS7b: confirm_show_end text text‌text",
          _ts7.confirm_show_end() is True
          and _ts7.end["end90"]["pend"] is None)

    # TS8: fail_show_end → technical note technical note shows + re-arming
    _ts8 = TVSnapshotEngine(dict(_ts_settings))
    _ts8.reset_match(5000.0)
    _a8 = []
    _w8 = 5000.0
    _a8 += _ts8.tick(91 * 60.0, "STOP", 2, _w8)
    for _i8 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w8 += 1.0
        _a8 += _ts8.tick(91 * 60.0, "STOP", 2, _w8)
    check("TS8: fail_show_end level text withtextarmed text‌text",
          _ts8.fail_show_end("end90", 6000.0, "test") is True
          and _ts8.end["end90"]["shows"] == 0
          and _ts8.end["end90"]["stop_since"] is None
          and _ts8.end["end90"]["fails"] == 1)

    # TS9: display 120 level 90 technical note complete technical note technical note‌technical note (without technical noteandtechnical note)
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
    check("TS9: end120 → end90 complete text (without textandtext) + pend text",
          ("show_end", "end120") in _a9
          and _ts9.end["end90"]["shows"] == 2
          and _ts9.end["end90"]["pend"] is None
          and _ts9.end["end120"]["pend"] is not None)

    # TS10: technical note confirmation show_end → technical note technical note automatic + technical noteandtechnical note technical note
    _ts10 = TVSnapshotEngine(dict(_ts_settings))
    _ts10.reset_match(8000.0)
    _w10 = 8000.0
    _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    for _i10 in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w10 += 1.0
        _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    _w10 += TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC + 1.0
    _ts10.tick(91 * 60.0, "STOP", 2, _w10)     # technical note → technical note technical note automatic
    check("TS10a: text confirmation show_end → shows text text text‌textandtext",
          _ts10.end["end90"]["shows"] == 0
          and _ts10.end["end90"]["fails"] == 1)
    _a10b = []
    for _i10b in range(int(TV_SNAP_END_STOP_CONFIRM_SEC + 3)):
        _w10 += 1.0
        _a10b += _ts10.tick(91 * 60.0, "STOP", 2, _w10)
    check("TS10b: text from re-armingtext display end again textin text‌textandtext",
          ("show_end", "end90") in _a10b)

    # TS11: technical note structuretechnical note — technical noteandtechnical note complete three-layer (withtechnical note technical noteandtechnical note)
    _src_engine_ts = _inspect.getsource(TVSnapshotEngine)
    check("TS11: textandtextandtext API text text (confirm/fail/show_attempt)",
          all(m in _src_engine_ts
              for m in ("def confirm_shown", "def fail_show",
                        "def show_attempt", "def confirm_show_end",
                        "def fail_show_end", "show_abandoned")))
    _src_app_ts = _inspect.getsource(MomentumApp)
    check("TS11b: App text textandtext + drain + log text text",
          all(m in _src_app_ts
              for m in ("_snap_show_events", "_snap_drain_show_events",
                        "_snap_show_stage", "_snap_show_event")))
    _src_uip_ts = _inspect.getsource(MomentumApp._ui_post)
    check("TS11c: _ui_post output bool text‌text (text/run text text‌textandtext)",
          "return True" in _src_uip_ts and "return False" in _src_uip_ts
          and "_report_fail" in _src_uip_ts)
    _src_gpu_ts = _inspect.getsource(MomentumApp._show_snapshot_overlay_gpu)
    check("TS11d: text confirmation SHOWING in path GPU",
          '_snap_show_event("confirm' in _src_gpu_ts)
    _src_tk_ts = _inspect.getsource(MomentumApp._show_snapshot_overlay)
    check("TS11e: text confirmation SHOWING in path Tk",
          '_snap_show_event("confirm' in _src_tk_ts)

    # TS11f-h: technical note correct technical note technical notefrom in worker_loop (before from technical note‌technical note data)
    _src_wl_ts = _inspect.getsource(MomentumApp.worker_loop)
    _i_205 = _src_wl_ts.find("2.05-text")
    _i_snapts = _src_wl_ts.find("self._snapshot_tick(")
    _i_gates = _src_wl_ts.find("if not ball or not players:")
    _i_verdict = _src_wl_ts.find("if self._ht_pending:")
    _i_wd = _src_wl_ts.find("if is_new_match_watchdog(")
    _i_flag = _src_wl_ts.find("should_flag_time_drop(")
    check("TS11f: text 2.05-text before from _snapshot_tick run text‌textandtext",
          0 < _i_205 < _i_snapts,
          f"205@{_i_205} snap@{_i_snapts}")
    check("TS11g: text HT/ET before from text‌text ball/players (text textagetext FSM)",
          0 < _i_verdict < _i_gates and 0 < _i_wd < _i_gates
          and 0 < _i_flag < _i_gates,
          f"verdict@{_i_verdict} wd@{_i_wd} flag@{_i_flag} gates@{_i_gates}")
    check("TS11h: text text‌text only text‌withtext in worker andtextandtext is",
          _src_wl_ts.count("if self._ht_pending:") == 1
          and _src_wl_ts.count("should_flag_time_drop(") == 1
          and _src_wl_ts.count("if is_new_match_watchdog(") == 1)
    check("TS11i: text text‌text only in PLAYING (text legacy text text)",
          'if m_state == "PLAYING" and total_t is not None:' in _src_wl_ts)

    # TS12: technical noteandtechnical note — technical note‌technical note technical note unchanged
    check("TS12a: detection PLAYING/STOP same text legacy is (byte 128/129)",
          "MATCH_STATE_OFFSET" in _inspect.getsource(GameEngine.read_match_state)
          and "128" in _inspect.getsource(GameEngine.read_match_state))
    check("TS12b: red card text text (pointer/chain)",
          GameEngine.RED_CARD_PTR_OFFSET == 0x036F3F88
          and tuple(GameEngine.RED_CARD_CHAIN) == (0x350, 0x4E0))
    check("TS12c: smoothing bell-shaped text text (σ=20/55)",
          abs(MomentumScoringConfig.GAUSSIAN_SIGMA - 20.0) < 1e-9
          and abs(TV_SMOOTH_SIGMA_SEC - 55.0) < 1e-9)
    check("TS12d: text‌text text v10.28 in text textandtext text",
          TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC == 10.0
          and TV_SNAP_SHOW_RETRY_BACKOFF_SEC == 3.0
          and TV_SNAP_SHOW_MAX_RETRIES == 6
          and TV_SNAP_END_FAIL_MAX == 3)

    # TS13: v10.29 — technical note end display technical note charttechnical note (technical noteandtechnical note v1.2.2 from 2017)
    _src_gpu_cls = _inspect.getsource(GPUOverlayRenderer)
    check("TS13a: rendertext GPU Administratortext level-window text (_win_show/_win_hide)",
          "def _win_show" in _src_gpu_cls
          and "def _win_hide" in _src_gpu_cls
          and "_win_visible" in _src_gpu_cls
          and "_hide_pending" in _src_gpu_cls)
    check("TS13b: window in INIT text textortext text‌textandtext (text text until text)",
          "_glfw.show_window(win)" not in
          _inspect.getsource(GPUOverlayRenderer._run)
          and "self._win_visible = False" in
          _inspect.getsource(GPUOverlayRenderer._run))
    _src_h29 = _inspect.getsource(GPUOverlayRenderer._handle)
    check("TS13c: show real → _win_showtext hide_now → _win_hide structuretext",
          "self._win_show()" in _src_h29
          and "self._win_hide()" in _src_h29
          and "self._hide_pending = False" in _src_h29)
    check("TS13d: hide in textortext text text text‌textandtext (_hide_pending)",
          "self._hide_pending = True" in _src_h29)
    _src_ae29 = _inspect.getsource(GPUOverlayRenderer._anim_end)
    check("TS13e: end textandtext → window text hide text → textandtext smooth",
          "self._win_hide()" in _src_ae29
          and "self._hide_pending" in _src_ae29)
    _src_app29 = _inspect.getsource(MomentumApp)
    check("TS13f: App watchdog text display + text‌text text",
          "def _snap_overlay_duration_watchdog" in _src_app29
          and "_snap_overlay_deadline_wall" in _src_app29
          and "_snap_overdue_watchdog_fired" in _src_app29)
    _src_shg29 = _inspect.getsource(MomentumApp._show_snapshot_overlay_gpu)
    _src_sht29 = _inspect.getsource(MomentumApp._show_snapshot_overlay)
    check("TS13g: text‌text in text textand path display (GPU/Tk) text text‌textandtext",
          "_snap_overlay_deadline_wall = (" in _src_shg29
          and "_snap_overlay_deadline_wall = (" in _src_sht29
          and "TV_SNAP_OVERDUE_GRACE_SEC" in _src_shg29
          and "TV_SNAP_OVERDUE_GRACE_SEC" in _src_sht29)
    _src_hso29 = _inspect.getsource(MomentumApp._hide_snapshot_overlay)
    check("TS13h: hidden‌textfromtext text‌text text withtext text‌text (text textand path)",
          "_snap_overlay_deadline_wall = None" in _src_hso29)
    check("TS13i: text watchdog (8s) and start text in __init__ registeredtext",
          TV_SNAP_OVERDUE_GRACE_SEC == 8.0
          and "_snap_overlay_duration_watchdog" in
          _inspect.getsource(MomentumApp.__init__))
    check("TS13j: textandtext v10.29 — red card/PLAYING/smoothing bell-shaped "
          "unchanged",
          GameEngine.RED_CARD_PTR_OFFSET == 0x036F3F88
          and tuple(GameEngine.RED_CARD_CHAIN) == (0x350, 0x4E0)
          and "MATCH_STATE_OFFSET" in
          _inspect.getsource(GameEngine.read_match_state)
          and abs(MomentumScoringConfig.GAUSSIAN_SIGMA - 20.0) < 1e-9
          and abs(TV_SMOOTH_SIGMA_SEC - 55.0) < 1e-9)

    print("\n" + "=" * 74)
    if failures:
        print(f" result: {total - len(failures)}/{total} PASS — {len(failures)} FAILURE:")
        for f in failures:
            print(f"   ✗ {f}")
        return 1
    print(f" result: {total}/{total} PASS ✅ — text test‌text End-to-End successful")
    return 0


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


# =============================================================================
# Entry point (headless service started by ModBridge.py)
# =============================================================================