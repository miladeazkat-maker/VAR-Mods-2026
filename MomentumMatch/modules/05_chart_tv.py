def _fmt_clock(sec: float) -> str:
    m, s = divmod(int(round(max(0.0, sec))), 60)
    return f"{m:02d}:{s:02d}"


def gaussian_smooth(vals: List[float], sigma_samples: float) -> List[float]:
    """Gaussian smoothing real — for text selftest in level textandtext"""
    return _gauss_smooth_impl(vals, sigma_samples)


def _gauss_smooth_impl(vals: List[float], sigma_samples: float) -> List[float]:
    """
    version 3 — Gaussian smoothing text‌text‌text (NaN-aware):
    sample‌text NaN (watchdog‌text gap HT) to‌textandtext text text text‌text and text
    text textandtext to‌textandtext independent textandtext text‌textandtext in text:
      * NaN in text text «text» text‌textandtext (textuntiltext beforetext: textandtext to radius text)
      * text text text until texttotext gap completetext textandtext and textandtext is and textandtext gap text text‌text
    """
    n = len(vals)
    s = float(sigma_samples)
    if s <= 0.3 or n < 5:
        return list(vals)
    arr = np.asarray(vals, dtype=float)
    nan_mask = np.isnan(arr)
    if not nan_mask.any():
        return _smooth_segment(arr, s).tolist()
    out = arr.copy()
    # technical note technical note technical note‌technical note technical noteandtechnical note non-NaN
    idx = np.where(~nan_mask)[0]
    if idx.size == 0:
        return list(vals)
    splits = np.where(np.diff(idx) > 1)[0]
    seg_starts = np.concatenate(([idx[0]], np.atleast_1d(idx[splits + 1])))
    seg_ends = np.concatenate((np.atleast_1d(idx[splits]), [idx[-1]]))
    for a, b in zip(seg_starts, seg_ends):
        out[a:b + 1] = _smooth_segment(arr[a:b + 1], s)
    return out.tolist()


def _smooth_segment(seg: "np.ndarray", s: float) -> "np.ndarray":
    """textandtextfromtext textandtext text text textandtext (without NaN) — edge-padding for text textto‌text"""
    m = len(seg)
    if m < 5:
        return seg.copy()
    radius = max(1, min(int(math.ceil(3.0 * s)), 500))
    if radius >= m:
        radius = max(1, m - 1)
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-(x * x) / (2.0 * s * s))
    kernel /= kernel.sum()
    padded = np.pad(seg, radius, mode="edge")
    return np.convolve(padded, kernel, mode="valid")


# =====================================================================
# version 10technical note2 — withtechnical note icon ball technical note from tex/ball_icon.png (technical note code)
# ---------------------------------------------------------------------
# * if file technical noteandtechnical noteandtechnical note withtechnical note → draw_momentum_chart to‌technical note technical note technical note
#   technical note technical noteandtechnical note technical note with technical note cfg.BALL_ICON_SIZE_PT technical note technical note‌technical note.
# * if file technical noteandtechnical note/broken technical noteandtechnical note → technical note technical note default (fallback deterministic).
# * technical note technical note technical note‌technical noteandtechnical note until only technical note withtechnical note from technical note technical noteandtechnical note technical noteandtechnical note.
# =====================================================================
_ball_icon_cache = {"tried": False, "arr": None}


def load_ball_icon():
    """
    text textandtext icon ball (tex/ball_icon.png text file code) or None.
    output always for render text is: None text fallback to text.
    """
    if _ball_icon_cache["tried"]:
        return _ball_icon_cache["arr"]
    _ball_icon_cache["tried"] = True
    try:
        path = os.path.join(_MOMENTUM_DATA_DIR,
                            "tex", "ball_icon.png")
        if os.path.exists(path):
            import matplotlib.image as _mpimg
            arr = _mpimg.imread(path)
            if getattr(arr, "ndim", 0) == 3 and arr.shape[0] > 0 and arr.shape[1] > 0:
                _ball_icon_cache["arr"] = arr
                clog(f"[BallIcon] icon ball withtext text: {path} "
                      f"({arr.shape[1]}×{arr.shape[0]})")
            else:
                clog(f"[BallIcon] text textandtext usable is not: {path}")
        else:
            clog(f"[BallIcon] file icon text text: {path} — "
                  f"from text text default istext text‌textandtext")
    except Exception as ex:
        clog(f"[BallIcon] Errortext withtext icon: {type(ex).__name__}: {ex}")
    return _ball_icon_cache["arr"]


_red_card_icon_cache = {"arr": None}

RED_CARD_ASPECT_W_H = 0.628            # 27/43 — technical note sampletechnical note user
RED_CARD_FILL_TOP = (250, 49, 60)      # #FA313C — technical notetotechnical note withtechnical note
RED_CARD_FILL_BOTTOM = (234, 1, 11)    # #EA010B — technical notetotechnical note below


def build_red_card_icon():
    """
    versiontext 10text27 — icon red card to‌textandtext text RGBA float 0..1 — text
    in code with PIL (textsample‌text ×4 + textandtext LANCZOS for texttotext smoothtext text
    versiontext 2017). None if PIL in text textwithtext (rendertext to text text
    Matplotlib fallback text‌text).
    """
    if _red_card_icon_cache["arr"] is not None:
        return _red_card_icon_cache["arr"]
    if Image is None:
        return None
    try:
        from PIL import ImageDraw as _IDraw
        from PIL import ImageFilter as _IFilter

        w, h = 66, 105                    # ratio 0.629 ≈ sample (27×43)
        ss = 4                            # technical notesample‌technical note
        W, H = w * ss, h * ss
        pad = 3 * ss                      # technical note for technical note
        radius = max(2, int(round(W * (2.5 / 27.0))))

        canvas = Image.new("RGBA", (W + 2 * pad, H + 2 * pad),
                           (0, 0, 0, 0))

        # --- technical note smooth technical note (technical noteto‌technical note ~1px below + technical noteandtechnical note) ---
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        _sdr = _IDraw.Draw(shadow)
        _sdr.rounded_rectangle(
            [pad + ss, pad + ss, pad + W - 1 + ss, pad + H - 1 + ss],
            radius=radius, fill=(10, 14, 22, 118))
        shadow = shadow.filter(_IFilter.GaussianBlur(radius=2 * ss))
        canvas.alpha_composite(shadow)

        # --- technical note card: technical noteortechnical note technical noteandtechnical note + technical note technical noteandtechnical note technical note ---
        grad_line = Image.new("RGBA", (1, H))
        for y in range(H):
            f = y / max(1, H - 1)
            grad_line.putpixel(
                (0, y),
                (int(RED_CARD_FILL_TOP[0]
                     + (RED_CARD_FILL_BOTTOM[0] - RED_CARD_FILL_TOP[0]) * f),
                 int(RED_CARD_FILL_TOP[1]
                     + (RED_CARD_FILL_BOTTOM[1] - RED_CARD_FILL_TOP[1]) * f),
                 int(RED_CARD_FILL_TOP[2]
                     + (RED_CARD_FILL_BOTTOM[2] - RED_CARD_FILL_TOP[2]) * f),
                 255))
        grad = grad_line.resize((W, H))
        mask = Image.new("L", (W, H), 0)
        _IDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1],
                                            radius=radius, fill=255)
        canvas.paste(grad, (pad, pad), mask)

        # --- technical noteandtechnical note technical notesample → technical note float 0..1 ---
        try:
            _lanczos = Image.Resampling.LANCZOS
        except AttributeError:
            _lanczos = Image.LANCZOS
        icon = canvas.resize((w, h), _lanczos)
        arr = np.asarray(icon.convert("RGBA")).astype(float) / 255.0
        _red_card_icon_cache["arr"] = arr
        clog(f"[RedCardIcon] icon red card text text ({w}×{h})")
        return arr
    except Exception as ex:
        clog(f"[RedCardIcon] Errortext text icon: {type(ex).__name__}: {ex}")
        return None


def draw_momentum_chart(ax, momentum: "MomentumEngine", cfg: "MomentumScoringConfig",
                        disp_value, goal_glyph_ok: bool = True,
                        home_color: str = '#e63946', away_color: str = '#f5f5f5'):
    """
    render complete chart textandtext ax — text in App and text in selftest (headless).
    version 9 — text text: Memory Goal Counter → add_hook_goal_marker()
      → textandtext Schedule Render → draw_momentum_chart() → line + ball
      * Goal Marker «line textandtext + icon ball» only and only from hook_goal_markers
        text text‌textandtext (source deterministic: Memory Goal Counter → Goal Marker → Chart).
        for text text hook_goal_markers exactly text text text text‌textandtext and text
        Dedup text text‌text text text‌textandtext — text if textand text text text withtext or
        from text team withtext.
      * version 9 (text): in text untiltext text return textandtext andtextandtext text —
        textandtext len(hist) < 2 only message «Waiting for match start...» text‌text
        layer‌text andtext to history (text/HT/text/Legend) with text text
        len(hist) >= 2 text text‌textandtext until section Goal Marker «always» text textandtext.
      * Goal Impact / Event Bus / Shot / history / dedup text text in
        text text text (path text completetext independent:
        Counter → Goal Event → Goal Impact → Momentum Pulse).
      * disp_time text text same value frozentext text register in
        add_hook_goal_marker istext order text = order register (without sort).
      * Home: icon withtext/line text to side below until line text | Away: textimagetext
        line from line andtext text text‌textandtext and text text textandtext chart textandtext text‌textandtext
      * gap HT: textand line textandtext textuntiltext + text HT + gap‌text text resync
      * text Artist text with gid deterministic text text‌textandtext (goal_line_{i}_shell /
        goal_line_{i}_core / goal_ball_{i}) until Self-Test textandtext assert
        text: len(hook_goal_markers) == number_of_goal_icons
                              == number_of_goal_marker_lines
      * specification deterministic text text (v9): clip_on=False for text Artisttext
        zorder 100 (shell) / 101 (core) / 102 (ball)text ball text
        marker="o" textplotlib is — text andtext to textandtext/text text and
        goal_glyph_ok in Goal Marker text‌text is.
      * log‌text text chain: [GraphGoalRender] after from Snapshot and
        [GoalMarkerRender] before from text text — for detection text text failure
        (Hook → Engine → Snapshot → Render → Matplotlib)
    """
    with momentum._lock:
        hist = list(momentum.history)
        display_offset = momentum.display_offset
        ht_break = momentum.ht_break
        extra_breaks = list(momentum.extra_breaks)
        hook_markers = [dict(m) for m in momentum.hook_goal_markers]
        # versiontechnical note 10technical note27 — technical note red card (getattr: technical notefromtechnical note with technical noteandtechnical noteandtechnical note technical noteto)
        rc_markers = [dict(m) for m in
                      (getattr(momentum, "red_card_markers", None) or [])]

    # version 8 — Snapshot technical note technical note technical note from technical note to after only and only from
    # hook_markers istechnical note technical note‌technical noteandtechnical note (technical note technical note direct to
    # momentum.hook_goal_markers in resumetechnical note untiltechnical note andtechnical noteandtechnical note technical note).
    clog(
        "[GraphGoalRender] "
        f"hook_markers={len(hook_markers)} | "
        f"points={[(m.get('team'), m.get('game_time'), m.get('disp_time')) for m in hook_markers]}"
    )

    panel_bg = '#111a2b'
    grid = '#2e384d'
    rng = cfg.DISPLAY_RANGE
    ax.clear()
    ax.set_facecolor(panel_bg)
    ax.tick_params(colors='#94a3b8', labelsize=8)
    for sp in ('bottom', 'top', 'right', 'left'):
        ax.spines[sp].set_color(grid)
    ax.set_xlabel("match time (Game Clock)", color='#94a3b8', fontsize=8)
    ax.set_ylabel("Net Momentum\n(Home ↑ / Away ↓)", color='#ffd166', fontsize=8)
    # version 3: technical note withtechnical note/below for icon ball technical note‌technical note — version 4: technical note technical note‌technical note (icon 13)
    ax.set_ylim(-rng - 18, rng + 27)
    ax.axhline(0, color='#7f8fa6', linewidth=1.0, alpha=0.8)
    ax.grid(True, linestyle='--', alpha=0.22, color=grid)

    if len(hist) < 2:
        ax.text(
            0.5,
            0.5,
            "Waiting for match start...",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color="#54607a",
            fontsize=11
        )

        # technical note:
        # technical note RETURN technical notemenutechnical note is.
        #
        # Goal Marker independent from history is and below‌technical note
        # must technical note Render technical noteandtechnical note.

    # --- version 9: technical note/HT only with history technical note — without technical note return ---
    # (beforetechnical note technical note with return technical noteandtechnical note total untiltechnical note technical note technical note‌technical note technical noteandtechnical note only technical note
    #  layer‌technical note andtechnical note to history technical note technical note‌technical noteandtechnical note until Goal Marker technical note below‌technical note
    #  is «always» technical note technical noteandtechnical note — technical note with technical note or technical note sample)
    t_axis = None
    t_end = 0.0
    if len(hist) >= 2:
        # --- downsampling for technical note (RAW sourcetechnical note only distance‌technical note) ---
        step = max(1, len(hist) // 3000)
        samples = hist[::step]
        if samples[-1] is not hist[-1]:
            samples.append(hist[-1])

        t_axis = [s.get("disp_time", s["game_time"]) for s in samples]
        net_disp = [disp_value(s["net"]) for s in samples]

        # --- Gaussian smoothing real (technical note technical noteortechnical note technical note) — only layer display ---
        # version 3: sigma technical note‌technical note (GAUSSIAN_SIGMA=7s) → technical note technical noteandtechnical note technical note without technical note
        # technical noteandtechnical notefromtechnical note technical note‌technical note‌technical note is → NaNtechnical note gap HT technical note technical note‌technical noteandtechnical note and technical note technical note‌technical note
        dts = [(b["game_time"] - a["game_time"]) for a, b in zip(samples, samples[1:])
               if b["game_time"] > a["game_time"]]
        eff_dt = (sum(dts) / len(dts)) if dts else cfg.HISTORY_SAMPLE_INTERVAL
        sigma_samples = cfg.GAUSSIAN_SIGMA / max(0.02, eff_dt)
        net_disp = _gauss_smooth_impl(net_disp, sigma_samples)

        # --- Net Area technical note‌technical note: Home withtechnical note | Away below ---
        # versiontechnical note 10technical note6 — color technical note team from leagues_data.json + byte istechnical note numbertechnical note color
        # technical noteandtechnical note technical note‌technical noteandtechnical note (default: technical note/technical note always‌beforetechnical note)technical note technical notetotal chart changetechnical note technical note.
        ax.fill_between(t_axis, net_disp, 0, where=[(v >= 0) for v in net_disp],
                        interpolate=True, color=home_color, alpha=0.80, label='Home (Home)')
        ax.fill_between(t_axis, net_disp, 0, where=[(v < 0) for v in net_disp],
                        interpolate=True, color=away_color, alpha=0.90, label='Away (Away)')
        # version 3: technical note technical note‌technical note with technical note/intechnical note technical note → technical note «technical note line technical note»
        ax.plot(t_axis, net_disp, color='#ffd166', linewidth=2.0, alpha=0.95,
                solid_capstyle='round', solid_joinstyle='round', antialiased=True)

        # --- gap HT: technical noteand line technical noteandtechnical note technical noteuntiltechnical note + technical note HT (version 3) ---
        # version 5: gap‌technical note technical note resync_clock technical note with technical noteand line technical noteuntiltechnical note (without technical note)
        if ht_break:
            g1, g2 = ht_break
            for gb in (g1, g2):
                ax.axvline(gb, color='#8fa3c8', linewidth=1.3, alpha=0.9, zorder=4)
            ax.text((g1 + g2) / 2.0, 0, "HT", ha='center', va='center',
                    color='#ffd166', fontsize=11, fontweight='bold', alpha=0.95,
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='#0d1420',
                              edgecolor='#8fa3c8', alpha=0.95))
        for (b1, b2) in extra_breaks:
            for gb in (b1, b2):
                ax.axvline(gb, color='#8fa3c8', linewidth=1.1, alpha=0.55, zorder=4)
        t_end = t_axis[-1]

    # ================================================================
    # GOAL MARKER — SINGLE SOURCE OF TRUTH
    # ================================================================
    # only and only:
    # MomentumEngine.hook_goal_markers
    #
    # technical note technical note = exactly technical note line + technical note ball
    # technical note Dedup
    # technical note Event Impact
    # technical note Shot
    # technical note History technical note
    # ================================================================

    goal_points = []

    for mk in hook_markers:
        try:
            gx = float(mk["disp_time"])
            team = str(mk.get("team", "Home"))

            if not math.isfinite(gx):
                continue

            goal_points.append((gx, team))

        except Exception as ex:
            clog(f"[GoalMarker] invalid marker ignored: {ex}")

    y_top = rng + 16.0
    y_bot = -rng - 12.0

    # version 10technical note2 — icon ball technical note withtechnical note in technical note render withtechnical note technical note‌technical noteandtechnical note (technical note internal)
    _ball_icon_ref = load_ball_icon()

    clog(
        "[GoalMarkerRender] "
        f"count={len(goal_points)} | "
        f"points={goal_points}"
    )

    for gi, (gx, team) in enumerate(goal_points):

        y_goal = y_top if team == "Home" else y_bot

        # ------------------------------------------------------------
        # line technical noteandtechnical note — shell
        # ------------------------------------------------------------
        shell = ax.plot(
            [gx, gx],
            [y_goal, 0.0],
            color="#0d1420",
            linewidth=5.0,
            alpha=1.0,
            zorder=100,
            solid_capstyle="butt",
            clip_on=False
        )[0]

        # ------------------------------------------------------------
        # line technical noteandtechnical note — core
        # ------------------------------------------------------------
        core = ax.plot(
            [gx, gx],
            [y_goal, 0.0],
            color="#ffffff",
            linewidth=2.5,
            alpha=1.0,
            zorder=101,
            solid_capstyle="butt",
            clip_on=False
        )[0]

        # ------------------------------------------------------------
        # ball — version 10technical note2: icon PNG (tex/ball_icon.png technical note code)
        # if file icon technical noteandtechnical noteandtechnical note withtechnical note technical noteandtechnical note with technical note cfg.BALL_ICON_SIZE_PT
        # (technical note‌technical note from technical note beforetechnical note) technical note technical note‌technical noteandtechnical note in technical note technical note technical noteandtechnical note technical note
        # Matplotlib (deterministic and independent from technical noteandtechnical note) with technical note technical note technical note‌technical note (17).
        # for technical note technical note Self-Testtechnical note currentlytechnical note icon technical note technical note Line2D technical note
        # with same gid «goal_ball_{i}» register technical note‌technical noteandtechnical note (technical note‌technical note position/technical note)technical note
        # and technical noteandtechnical note icon with gid «goal_ballimg_{i}» technical note technical note‌technical noteandtechnical note.
        # ------------------------------------------------------------
        if _ball_icon_ref is not None:
            ball = ax.plot(
                [gx],
                [y_goal],
                marker="o",
                markersize=15.0,
                markerfacecolor="none",
                markeredgecolor="none",
                alpha=0.0,
                linestyle="None",
                zorder=102,
                clip_on=False
            )[0]

            _ih = int(_ball_icon_ref.shape[0])
            _iw = int(_ball_icon_ref.shape[1])
            _fig_dpi = float(ax.figure.dpi) if (ax.figure is not None and ax.figure.dpi) else 100.0
            # technical note technical note technical noteandtechnical note Point → zoom technical note technical note technical notefromtechnical note technical noteandtechnical note:
            #   technical notefromtechnical note displaytechnical note (px output) = px technical noteandtechnical note × zoom  and  px = pt × dpi / 72
            _zoom = (cfg.BALL_ICON_SIZE_PT / 72.0) * _fig_dpi / float(max(_iw, _ih))
            _img = OffsetImage(_ball_icon_ref, zoom=_zoom,
                               resample=True, interpolation="bilinear")
            _abox = AnnotationBbox(
                _img, (gx, y_goal),
                frameon=False,
                annotation_clip=False,
                zorder=103
            )
            ax.add_artist(_abox)
            _abox.set_gid(f"goal_ballimg_{gi}")
        else:
            # technical note technical note from glyph technical noteandtechnical note istechnical note technical note.
            # technical note‌technical note Matplotlib deterministic and independent from technical noteandtechnical note is.
            ball = ax.plot(
                [gx],
                [y_goal],
                marker="o",
                markersize=17.0,
                markerfacecolor="#ffffff",
                markeredgecolor="#0d1420",
                markeredgewidth=2.0,
                linestyle="None",
                zorder=102,
                clip_on=False
            )[0]

        # ------------------------------------------------------------
        # GID for test
        # ------------------------------------------------------------
        shell.set_gid(f"goal_line_{gi}_shell")
        core.set_gid(f"goal_line_{gi}_core")
        ball.set_gid(f"goal_ball_{gi}")

    # ================================================================
    # versiontechnical note 10technical note27 — RED CARD MARKER (technical note GOAL MARKER — icon card to‌technical note ball)
    # ================================================================
    # only and only: MomentumEngine.red_card_markers
    # technical note technical note = exactly technical note line (shell + core) + technical note icon red card.
    # gid technical note: rc_line_{i}_shell / rc_line_{i}_core / rc_card_{i} (technical note‌technical note)
    # and rc_cardimg_{i} (icon) — same technical note test‌technical note technical note (technical note 2017).
    # ================================================================
    rc_points = []
    for mk in rc_markers:
        try:
            gx = float(mk["disp_time"])
            team = str(mk.get("team", "Home"))
            if not math.isfinite(gx):
                continue
            rc_points.append((gx, team))
        except Exception as ex:
            clog(f"[RedCardMarker] invalid marker ignored: {ex}")

    _rc_icon_ref = build_red_card_icon()
    for ci, (gx, team) in enumerate(rc_points):
        y_rc = y_top if team == "Home" else y_bot

        # ------------------------------------------------------------
        # line technical noteandtechnical note — shell + core (technical note technical note)
        # ------------------------------------------------------------
        rc_sh = ax.plot([gx, gx], [y_rc, 0.0], color="#0d1420",
                        linewidth=5.0, alpha=1.0, zorder=100,
                        solid_capstyle="butt", clip_on=False)[0]
        rc_co = ax.plot([gx, gx], [y_rc, 0.0], color="#ffffff",
                        linewidth=2.5, alpha=1.0, zorder=101,
                        solid_capstyle="butt", clip_on=False)[0]

        # ------------------------------------------------------------
        # icon red card — technical notefromtechnical note technical note‌technical note from ratio‌technical note sampletechnical note user:
        # height ≈ 1.05 × technical note icon balltechnical note width from ratio technical note 0.628.
        # if PIL technical noteandtechnical note → technical note technical note Matplotlib (deterministic and independent from technical noteandtechnical note).
        # ------------------------------------------------------------
        if _rc_icon_ref is not None:
            rc_anchor = ax.plot([gx], [y_rc], marker="o", markersize=15.0,
                                markerfacecolor="none",
                                markeredgecolor="none", alpha=0.0,
                                linestyle="None", zorder=102,
                                clip_on=False)[0]
            _ih = int(_rc_icon_ref.shape[0])
            _iw = int(_rc_icon_ref.shape[1])
            _fig_dpi = (float(ax.figure.dpi)
                        if (ax.figure is not None and ax.figure.dpi)
                        else 100.0)
            # height displaytechnical note (Point): ratiotechnical note card‌to‌ball technical note sample (≈1.05×)
            _h_pt = float(getattr(cfg, "BALL_ICON_SIZE_PT", 22.0)) \
                * (TV_RC_H_FRAC / TV_BALL_FRAC)
            _zoom = (_h_pt / 72.0) * _fig_dpi / float(max(1, _ih))
            _rimg = OffsetImage(_rc_icon_ref, zoom=_zoom,
                                resample=True, interpolation="bilinear")
            _rabox = AnnotationBbox(
                _rimg, (gx, y_rc),
                frameon=False, annotation_clip=False, zorder=103)
            ax.add_artist(_rabox)
            _rabox.set_gid(f"rc_cardimg_{ci}")
        else:
            rc_anchor = ax.plot([gx], [y_rc], marker="s", markersize=15.0,
                                markerfacecolor="#F00212",
                                markeredgecolor="#0d1420",
                                markeredgewidth=2.0, linestyle="None",
                                zorder=102, clip_on=False)[0]

        rc_sh.set_gid(f"rc_line_{ci}_shell")
        rc_co.set_gid(f"rc_line_{ci}_core")
        rc_anchor.set_gid(f"rc_card_{ci}")

    # ---------------------------------------------------------------
    # technical noteandtechnical note X technical note must Goal technical note technical noteandtechnical note technical note
    # ---------------------------------------------------------------
    if goal_points:
        max_goal_x = max(gx for gx, _ in goal_points)

        if len(hist) >= 2:
            try:
                current_x = max(
                    float(t_axis[-1]),
                    float(hist[-1].get("disp_time", hist[-1]["game_time"]))
                )
            except Exception:
                current_x = 0.0
        else:
            current_x = 0.0

        x_right = max(
            60.0,
            current_x + 45.0,
            max_goal_x + 25.0
        )

        ax.set_xlim(0.0, x_right)

    # --- withtechnical note technical noteandtechnical note X (version 9 — only with history technical note) ---
    # technical noteandtechnical note technical note‌technical note technical noteandtechnical note technical noteandtechnical note Goal Marker withtechnical note technical note technical note istechnical note technical note only
    # technical noteandtechnical note technical note technical note technical note‌technical noteandtechnical note and technical note technical note‌technical note technical noteandtechnical note technical note technical noteandtechnical note‌technical note technical noteandtechnical note
    # (max with side technical noteis technical note technical noteandtechnical note)
    if len(hist) >= 2:
        x_right = max(60.0, t_end + 45.0, ax.get_xlim()[1])
        ax.set_xlim(max(0.0, t_axis[0]), x_right)

    # --- technical note‌technical note 15 minute‌technical note Game Clock (version 3: technical note real match time) ---
    # time‌technical note first half without offsettechnical note time‌technical note second half with offset → technical note 60'
    # correct after from gap HT technical note‌decreasetechnical note and technical note technical note inside gap technical note technical note‌technical note
    # (version 9: only with history technical note — without returntechnical note technical note technical note)
    if len(hist) >= 2:
        total_clock = hist[-1]["game_time"] + display_offset
        ticks, labels = [], []
        cm = 0
        while cm * 60 <= total_clock + 60:
            t_real = cm * 60
            if ht_break and t_real > ht_break[0]:
                disp = t_real + display_offset
            else:
                disp = t_real
            if disp <= t_end + 45.0:
                ticks.append(disp)
                labels.append(f"{cm}'")
            cm += 15
        if ticks:
            ax.set_xticks(ticks)
            ax.set_xticklabels(labels)

    # --- Legend: Home / Away / Goal (line technical note + icon ball) ---
    # (version 9: only with history technical note — technical note technical note empty without Legend technical note‌technical note)
    if len(hist) >= 2:
        handles = [
            Patch(facecolor=home_color, alpha=0.80, label='Home (Home)'),
            Patch(facecolor=away_color, alpha=0.90, label='Away (Away)'),
        ]
        if goal_points:
            handles.append(Line2D([0], [0], color='#ffffff', linewidth=1.9,
                                  marker='o', markersize=9,
                                  mfc='#ffffff', mec='#0d1420', mew=1.3,
                                  label='Goal'))
        ax.legend(handles=handles, facecolor='#111722', edgecolor='#2e384d',
                  labelcolor='#ffffff', fontsize=7, loc='upper left')


# =====================================================================
# 25technical note — render «TV Momentum»: chart technical noteandtechnical noteandtechnical note technical noteandtechnical note technical noteandtechnical note technical note (versiontechnical note 10technical note7)
# ---------------------------------------------------------------------
# * technical note‌pitchtechnical note: technical noteandtechnical note PNG foldertechnical note tex technical note technical note:
#     first half  → Half_Match_Moment.png   |  second half → Full_Match_Moment.png
#     extra time → Extra_Match_Moment.png
# * technical note technical noteandtechnical note (technical note charttechnical note line technical note lineandtechnical note technical noteandtechnical note HT/FT/ET) «from technical noteandtechnical note
#   technical noteandtechnical note» detection data technical note‌technical noteandtechnical note (technical note technical note technical notecodetechnical note ‎#3a3a3a + lineandtechnical note technical note)technical note
#   if detection failed technical noteandtechnical note technical note technical notefromtechnical note‌technical note‌technical note from technical note file‌technical note to‌technical noteandtechnical note
#   fallback istechnical note technical note‌technical noteandtechnical note.
# * technical noteandtechnical note technical note (exactly technical note specification user):
#     - chart from same first with technical notefromtechnical note complete technical note technical note‌technical noteandtechnical note (technical note technical note‌technical noteandtechnical note)
#     - technical noteandtechnical note technical noteandtechnical note ‎-120..+120‎ — without technical note number/technical note/technical note/technical note
#     - line technical note technical noteortechnical note technical note = line technical note
#     - line technical note and lineandtechnical note technical noteandtechnical note technical noteandtechnical note «technical noteand technical note‌technical noteandtechnical note» (after from fill again
#       technical noteandtechnical note technical note‌technical note technical note technical note‌technical noteandtechnical note) — layertechnical note technical noteandtechnical note chart 100technical note technical note is
#     - color fill = color chart technical noteandtechnical note istechnical noteandtechnical note technical note in technical note technical note technical note technical note
#     - intechnical note technical noteandtechnical note technical note technical noteandtechnical note technical notetotechnical note fill
#     - technical note technical note technical noteand technical note technical note — technical noteand technical note from technical note line technical note to technical note technical note‌technical note
#     - technical note technical note = line technical noteandtechnical note withtechnical note + ball (technical notefromtechnical note‌technical note technical note sampletechnical note user)
#     - logo/technical note team‌technical note: technical note technical note technical note — Home withtechnical note / Away belowtechnical note
#       with istechnical noteandtechnical note technical note technical noteandtechnical note‌technical note technical note technical noteandtechnical note sample
# =====================================================================
TV_BG_DIRNAME = "tex"                                   # technical note technical note
TV_BG_FILES = {
    "half":  "Half_Match_Moment.png",
    "full":  "Full_Match_Moment.png",
    "extra": "Extra_Match_Moment.png",
}
# ------------------------------------------------------------------
# versiontechnical note 10technical note8 — technical noteandtechnical note technical noteandtechnical note technical note from technical noteandtechnical note «technical note‌technical note technical noteandtechnical note technical noteandtechnical note»
#   HT = minutetechnical note 45 | FT = minutetechnical note 90 | ET = minutetechnical note 105
#   first half : technical note‌technical note 0 technical note 15 technical note 30 technical note 45(HT)
#   second half : technical note‌technical note 0 technical note 15 technical note 30 technical note 45(HT) technical note 60 technical note 75 technical note 90
#   extra time: technical note‌technical note 0 technical note 15 technical note 30 technical note 45(HT) technical note 60 technical note 75 technical note 90(FT) technical note 105(ET) technical note 120
# count technical note detection‌data‌technical note ← minutetechnical note technical note technical note minute→technical note linetechnical note technical note‌technical note.
# ------------------------------------------------------------------
TV_TICK_MINUTES_BY_COUNT = {
    4: (0.0, 15.0, 30.0, 45.0),
    7: (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0),
    9: (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0),
}
# position technical note‌technical note technical noteandtechnical note file‌technical note original (technical note technical noteandtechnical note technical note) — only fallback
TV_FALLBACK_TICKS = {
    "half":  (220.0, 647.0, 1073.0, 1500.0),
    "full":  (220.0, 434.0, 647.0, 860.0, 1073.0, 1286.0, 1500.0),
    "extra": (220.0, 434.0, 647.0, 860.0, 1073.0, 1286.0, 1500.0, 1713.0, 1926.0),
}
TV_FALLBACK_BASE_W = {"half": 1608, "full": 1608, "extra": 2034}
TV_FALLBACK_GEOM = {
    "half":  {"rect": (211, 1510, 189, 755), "zero_y": 486, "verticals": [],
              "anchors_x": [], "W": 1608},
    "full":  {"rect": (211, 1510, 189, 755), "zero_y": 486, "verticals": [],
              "anchors_x": [], "W": 1608},
    "extra": {"rect": (211, 1936, 189, 755), "zero_y": 486, "verticals": [],
              "anchors_x": [], "W": 2034},
}
TV_Y_RANGE = 150.0            # technical noteandtechnical note technical noteandtechnical note technical note ‎-150..+150‎ (without number technical noteandtechnical note technical noteandtechnical note)
# --- versiontechnical note 10technical note16 — technical noteortechnical note technical noteandtechnical note «technical noteandor» (technical note new user) ---
# technical note technical noteandtechnical note = 50 andtechnical note above from «technical note technical noteintechnical note height technical note technical noteand chart» (withtechnical note+
# below with technical note) and never technical note from 150 is not:
#   technical noteortechnical note = max(150 technical note technical note |height chart| + 50)
# technical note user: technical noteandtechnical note 120 → technical noteandtechnical note ‎±170‎technical note if ‎(technical noteandtechnical note+50)<150‎ technical note → same ‎±150‎.
TV_SCALE_MARGIN = 50.0        # distancetechnical note technical note technical noteandtechnical note from technical note chart
TV_SCALE_MIN = 150.0          # technical note technical notefrom technical noteortechnical note (= TV_Y_RANGE)
# icon ball always «30 andtechnical note below‌technical note from technical note technical noteortechnical note» is (technical note user 10technical note16):
# ball = technical noteortechnical note − 30 → technical note ball‌technical note in «technical note height»technical note if technical noteortechnical note aftertechnical note technical noteandtechnical note technical noteandtechnical note
# ball‌technical note technical note with technical note technical noteto‌technical note technical note‌technical noteandtechnical note. with technical noteortechnical note technical note 150 → ball technical noteandtechnical note 120
# (same TV_BALL_VALUE versiontechnical note before — only technical note technical note technical noteortechnical note technical note is).
TV_BALL_GAP = 30.0
# --- technical note technical note‌technical note (technical noteandtechnical note technical noteanduntiltechnical note technical note technical notetotechnical note below technical note) ---
TV_TICK_BAND_OFF = 4          # start technical note: b + 4 technical note
TV_TICK_BAND_H = 30           # height technical noteandtechnical note technical note technical note
TV_TICK_MIN_ROWS = 12         # technical note technical note technical note in technical noteandtechnical note technical note
# --- technical notefromtechnical note‌technical note technical note technical note (technical note from technical noteandtechnical note sampletechnical note user technical notefromtechnical note‌technical note technical note) ---
TV_BALL_FRAC = 0.061          # technical note ball ÷ height technical note  (≈ 34px in 560px — technical note sample)
TV_BALL_EDGE_FRAC = 0.079     # (technical noteandtechnical note — versiontechnical note 10technical note15) distancetechnical note beforetechnical note ball from technical noteto
# versiontechnical note 10technical note15 — height icon ball technical noteandtechnical note ‎±120‎ — versiontechnical note 10technical note16: value technical note
# «technical noteortechnical note − 30» is (TV_BALL_GAP)technical note technical note technical note only technical note technical note technical noteortechnical note technical note
# (150) technical note technical note technical note‌technical note and for technical notefromtechnical note test‌technical note technical note technical note technical note is.
TV_BALL_VALUE = 120.0
TV_GLINE_FRAC = 0.0054        # technical note line technical note ÷ height technical note (≈ 3px — technical note sample)
TV_GLINE_SHELL_FRAC = 0.0089  # shelltechnical note technical note technical note line technical note (≈ 5px — technical noteandtechnical note technical noteandtechnical note fill technical noteandtechnical note)
# --- versiontechnical note 10technical note27 — technical notefromtechnical note‌technical note technical note red card (technical note versiontechnical note 2017 / technical noteandtechnical note user) ---
TV_RC_W_FRAC = 0.040          # width red card ÷ height technical note (≈ 0.66 × technical note ball)
TV_RC_H_FRAC = 0.064          # height red card ÷ height technical note (≈ 1.05 × technical note ball)
# --- versiontechnical note 10technical note27 — technical note assignment team red card (technical note player technical note) ---
RC_Z_TARGET = 40.0            # coordinates z player technical note (outside line lengthtechnical note 68m)
RC_Z_TOL = 5.0                # tolerance detection z≈40 (players pitch |z|≤34)
RC_WATCH_WINDOW_S = 30.0      # windowtechnical note technical note (secondtechnical note time withtechnical note) for technical note team
RC_WATCH_WALL_CAP_S = 300.0   # technical note wall technical noteandtechnical note technical note (stop lengthtechnical note/technical note technical note)
RC_MAX_JUMP = 5               # jump technical notefrom counter in technical note Poll (technical note = rebaseline)
# --- logo/technical note (technical note technical note technical note — technical notefromtechnical note‌technical note technical note technical noteandtechnical note sample) ---
TV_FLAG_TARGET_W = 110        # technical note‌technical note technical note technical note logo+istechnical noteandtechnical note (≈ 109px in sample)
TV_FLAG_CONTENT_W = 100       # width technical noteandtechnical note colortechnical note technical note from technical note (technical noteandtechnical note technical note ≈ 135px)
TV_FLAG_CONTENT_MAX_H = 118   # technical note height technical noteandtechnical note colortechnical note
TV_FLAG_STROKE_PX = 3         # istechnical noteandtechnical note technical note technical note technical notefromtechnical note (≈ 3px in sample)
TV_FLAG_GAP_PX = 2            # distancetechnical note istechnical noteandtechnical note from technical noteside colortechnical note (technical note sample)
TV_FLAG_CX_FRAC = 0.663       # x technical note logo ÷ x technical notetotechnical note technical note technical note (≈ 142px — technical note technical noteandtechnical note)
TV_FLAG_HOME_CY_FRAC = 0.229  # y technical note logotechnical note Home from withtechnical note technical note (technical note sample)
TV_FLAG_AWAY_CY_FRAC = 0.779  # y technical note logotechnical note Away from withtechnical note technical note (technical note sample)
# --- technical note ---
TV_ZERO_LINE_LW_FRAC = 0.0075   # technical note line technical note withtechnical note‌technical note ÷ height technical note
TV_VLINE_LW_FRAC = 0.0060       # technical note lineandtechnical note technical noteandtechnical note withtechnical note‌technical note (HT/FT/ET)
TV_FILL_ALPHA_HOME = 0.80       # technical note chart original
TV_FILL_ALPHA_AWAY = 0.90
# --- technical note: technical noteandtechnical notefromtechnical note displaytechnical note + technical note technical note (versiontechnical note 10technical note8) ---
TV_SMOOTH_SIGMA_SEC = 55.0    # technical note technical noteandtechnical note layertechnical note display TV (secondtechnical note time withtechnical note)
                              # v10.27 — 35→55 (same technical note «bell-shaped» versiontechnical note
                              # 2017 — peak‌technical note/valley‌technical note technical note‌technical note and smooth‌technical note technical note‌technical noteandtechnical note
                              # technical note‌technical note technical note technical noteandtechnical note technical notetotal totaltechnical note technical note technical note‌technical noteandtechnical note)
TV_BIN_STEP_PX = 1.5          # technical noteortechnical note‌technical note inside technical noteandtechnical note‌technical note 1technical note5 technical note (technical note technical note)
# --- versiontechnical note 10technical note26 — «technical note technical note» (resumetechnical note technical notetotechnical note technical note — technical note technical note user:
#     snap_h1 / preview_v10_18_userzoom / preview_v10_18_stroke). technical note
#     «technical note‌technical note»technical note withtechnical note‌technical note technical note technical note: inandtechnical note‌ortechnical note «linetechnical note» technical note technical note‌technical note ~0technical note9pxtechnical note
#     technical note technical note in technical note technical note technical note technical noteandtechnical note technical note‌technical note ⇒ technical noteandtechnical note technical noteortechnical note technical note ⇒
#     technical note‌technical note totalandtechnical note‌technical note in technical noteandtechnical note (5-8×). intechnical note (only render — technical note unchanged):
#     1) _tv_uniform_resample_c1: inandtechnical note‌ortechnical note «technical note technical noteandtechnical noteandtechnical noteandtechnical note» (PCHIP /
#        Fritsch–Carlson) technical noteandtechnical note same technical note 0technical note5px — from technical note technical note‌technical note technical note‌technical note
#        (height peak/valley technical note before)technical note technical noteandtechnical noteandtechnical noteandtechnical note (technical note technical noteandtechnical note)technical note technical note technical noteandtechnical note ⇒
#        technical note‌technical note technical noteandtechnical note and technical note. change technical notetotal ratio to linetechnical note: technical noteortechnical note 0technical note15pxtechnical note
#        p99 0technical note7px — technical note in technical note technical note count peak‌technical note and technical noteandtechnical note from technical note technical note before.
#     2) feather stroke: istechnical noteandtechnical note technical note‌technical note technical note‌color (1technical note6pxtechnical note technical note 0technical note4) technical noteandtechnical note boundary
#        fill in path matplotlib ⇒ technical note technical note technical noteto ~2x technical note‌technical note and technical note
#        (technical note technical note snap_h1technical note peak-gradient technical noteto 68→45). env:
#        TV_EDGE_FEATHER_LW / TV_EDGE_FEATHER_ALPHA (0=technical noteandtechnical note).
#     3) path GPU (technical noteandtechnical note live): uniform new u_feather in technical notein technical noteto — only
#        technical note‌technical note fill smoothing 1px technical note‌technical note (line‌technical note/ball/technical note technical note technical note‌technical note).
#        env: TV_GPU_FILL_FEATHER (0=technical noteuntiltechnical note beforetechnical note).
# --- versiontechnical note 10technical note25 — «technical notetotechnical note technical note» (user: technical notetotechnical note chart completetechnical note technical note and technical note
#     without to‌technical note‌technical note technical note totaltechnical note) — technical note technical note‌technical note technical note technical note: output binningtechnical note
#     technical noteandtechnical note‌technical note «technical note‌distance» with technical note technical note technical note‌technical note and technical note‌technical note fill technical note
#     technical note‌technical note technical note technical note technical note‌technical notefromtechnical note AA technical noteandtechnical note Agg (‎~1px‎) technical note technical note technical note‌technical noteandtechnical note.
#     intechnical note technical noteand layer‌technical note (only layertechnical note display — technical noteandtechnical note technical noteandtechnical noteandtechnical note unchanged):
#     1) withtechnical notesampling technical note technical noteandtechnical note technical note technical note «technical noteandtechnical note» technical note (0technical note5px)
#     2) technical noteandtechnical note technical note technical note (0technical note6px) only for technical note technical noteandtechnical note withtechnical note‌technical note —
#        width andtechnical note‌technical note chart ≥ ~10px ⇒ decrease height peak < 0technical note2technical note (technical note technical note before)
#     3) render technical noteagetechnical note‌technical note with technical notesample‌technical note TV_SNAPSHOT_SS× and technical noteortechnical note Box —
#        AA real technical noteandtechnical note technical note technical noteto‌technical note (fill/technical noteand/line technical note/technical note/logo) unchanged technical notetotal
TV_CURVE_GRID_STEP_PX = 0.5     # technical note technical note technical noteandtechnical note output technical note (technical note)
TV_EDGE_MICRO_SIGMA_PX = 0.8    # technical note technical noteandtechnical note technical note technical noteto (technical note technical note)
TV_SNAPSHOT_SS = 2              # technical note technical notesample‌technical note render technical noteagetechnical note‌technical note (1 = technical noteandtechnical note)
# --- versiontechnical note 10technical note26 — technical notetotechnical note technical note (feather) — technical note technical note technical note user (snap_h1) ---
# istechnical noteandtechnical note technical note‌technical note technical note‌color technical noteandtechnical note «technical noteandtechnical note boundary fill» → technical note technical note technical noteto from ~1px
# to ~1technical note6-2px technical note technical note‌technical noteandtechnical note technical note‌technical note technical note in technical noteandtechnical note technical note technical note technical note‌technical noteandtechnical note (technical note
# technical note). technical note technical note technical noteandtechnical note technical note/technical notetotal data technical note — only «rendertechnical note» technical noteto.
# TV_EDGE_FEATHER=0 (env) → technical noteandtechnical note (technical noteuntiltechnical note 10technical note25).
TV_EDGE_FEATHER_LW_PX = 1.6     # technical note istechnical noteandtechnical note feather (technical note technical note)
TV_EDGE_FEATHER_ALPHA = 0.40    # technical note istechnical noteandtechnical note feather
# path GPU (technical noteandtechnical note live): technical note‌technical note same smoothing for fill technical note — technical note‌widthtechnical note
# smoothstep technical noteto (technical note level). 0 = technical noteuntiltechnical note beforetechnical note (technical notetotechnical note technical note 1px).
TV_GPU_FILL_FEATHER_PX = 1.0
# (versiontechnical note 10technical note10 — line technical notetotechnical note technical note technical note: technical noteand line technical note technical note line technical note to color team‌technical note
#  technical note user technical note technical note same rim technical notetotechnical note fill technical noteandtechnical note — technical note technical note)
# --- intechnical note technical noteandtechnical note smooth (technical noteandtechnical note technical noteandtechnical note real — technical noteandtechnical note completetechnical note smooth from line to outside) ---
TV_GLOW_CORE_PX = 4.0                       # technical note line technical note intechnical note
# versiontechnical note 10technical note10 — technical note technical note with same smoothing (technical note technical note = smoothing sametechnical note
# only technical note technical noteandtechnical note ~1technical note6 technical note technical note until intechnical note technical note technical note technical noteandtechnical note)
TV_GLOW_LAYERS = ((3.0, 0.48), (10.0, 0.21))  # (technical note technical noteandtechnical note technical note technical noteandtechnical note)
# --- versiontechnical note 10technical note16 — technical note‌technical note technical noteandtechnical note user (technical note charttechnical note aftertechnical note technical notecode technical note‌technical noteandtechnical note) ---
TV_GLOW_SOFTNESS_MUL = 1.0     # technical note «smoothing» technical noteandtechnical note — in technical note technical noteandtechnical note technical note technical note‌technical noteandtechnical note
TV_GLOW_INTENSITY_MUL = 1.0    # technical note «technical note» technical noteandtechnical note — in technical note technical noteandtechnical note technical note technical note‌technical noteandtechnical note
TV_EDGE_SMOOTH_PX = 0.0        # technical noteandtechnical notefromtechnical note technical note «technical notetotechnical note» chart (technical noteandtechnical note technical note)
# versiontechnical note 10technical note17 — technical note technical noteto‌technical note technical notefrom technical noteandtechnical notefrom technical noteto (technical note): with totaltechnical note smooth tanhtechnical note
# technical note technical noteandtechnical note technical note from technical note value from value original‌technical note technical noteandtechnical note technical note‌technical noteandtechnical note ⇒ technical note‌technical note
# technical noteto technical note technical note‌technical noteandtechnical note andtechnical note «technical notetotal totaltechnical note» (peak‌technical note/valley‌technical note/height‌technical note) unchanged technical note‌technical note
# (technical note user: «smooth technical note technical noteto technical notemust technical notetotal totaltechnical note chart technical note to technical note technical note»).
TV_EDGE_SMOOTH_MAX_SHIFT_PX = 10.0
# --- versiontechnical note 10technical note9 — intechnical note technical note smoothtechnical note «ball + line technical noteandtechnical note technical note» ---
TV_MARKER_GLOW_LAYERS = ((2.5, 0.38), (9.0, 0.18))  # (technical note technical noteandtechnical note technical note technical noteandtechnical note) — technical note
# --- versiontechnical note 10technical note9 — «minute‌technical note shared» (extra time‌technical note technical note section) ---
# firsttechnical note technical note from technical note minute‌technical note in technical note boundary = extra timetechnical note section beforetechnical note (before from line boundary
# technical note technical note‌technical noteandtechnical note)technical note with restart untiltechnical note technical note from technical noteandtechnical note line boundary resume technical note‌ortechnical note.
TV_STOP_BOUNDS = (45.0, 90.0, 105.0, 120.0)   # boundary section‌technical note: HT / FT / ET / end
TV_STOP_WINDOW = {45.0: 5.0, 90.0: 7.0, 105.0: 7.0, 120.0: 7.0}
#                        ↑ windowtechnical note minute‌technical note shared (user: 45-50 and 90-97)
TV_STOP_SQUEEZE_FRAC = 0.10    # technical note withtechnical note technical note = technical note technical note × distancetechnical note technical note‌technical note (px/min)
TV_STOP_BAND_CAP_MIN = 8.0     # technical note minute‌technical note technical note‌technical note in technical note (technical note withtechnical note technical notereal)
TV_RESTART_GAP_SEC = 4.0       # technical note gap time real for «technical noteandtechnical note technical noteandtechnical note» (restart untiltechnical note)
# --- versiontechnical note 10technical note10 — detection restart technical note technical note user: «code first technical note technical note technical note technical noteor
# withtechnical note to minutetechnical note 45 or 90 reset technical note» technical note untiltechnical note from boundary technical note technical note number technical note‌technical note
# technical note and after from technical note stop again from technical noteandtechnical note boundary start to technical note technical note until before from
# technical note technical noteandtechnical note minute‌technical note shared technical noteand extra timetechnical note section beforetechnical note‌technical note.
TV_RESTART_LAND_EPS = 0.25     # technical noteandtechnical note restart: until 15 second after from minutetechnical note boundary
TV_RESTART_LAND_BELOW = 0.05   # technical noteandtechnical note restart: until 3 second before from minutetechnical note boundary
TV_RESTART_EDGE_EPS = 0.15     # «end andtechnical note technical note technical noteandtechnical note boundary»: beforetechnical note until 9 second before from boundary
TV_RESTART_BACKJUMP_MIN = 0.5  # jump technical noteandtechnical note technical note technical note (≥30s) = stop/technical note technical note without gap sample
TV_RESTART_EDGE_GAP_SEC = 30.0 # technical note gap for «end andtechnical note technical note technical noteandtechnical note boundary» (technical note real —
                               #  istechnical note technical noteanduntiltechnical note sampling technical notemust restart technical note technical notefromtechnical note)
# --- versiontechnical note 10technical note12 — «technical note technical note» (technical note line technical note technical note second half) ---
# technical note: line technical noteandtechnical note data in technical note HT technical note minute technical note technical note‌technical note if firsttechnical note sampletechnical note
# livetechnical note second half technical note technical noteandtechnical note technical noteortechnical note (technical note 46'-49')technical note technical noteandtechnical note technical note‌technical note ±15 second
# technical note technical note‌technical note ⇒ technical note sample‌technical note second half in technical noteandtechnical note withtechnical note technical note line HT technical note technical note‌technical note
# (user: «technical note register technical note‌technical note») and in technical noteandtechnical note from windowtechnical note 45-50 technical note line technical note technical note
# technical note‌technical note. technical noteandtechnical note «silence ≥180 secondtechnical note real» or «gap displaytechnical note watchdog ≥30 second»
# = technical note technical note technical noteandtechnical note until technical note windowtechnical note shared technical note and technical note jump technical noteand to technical noteand
# disabled technical note‌technical noteandtechnical note. (technical note technical note/Replay with silence 30-120 second never threshold technical note technical note
# technical note‌technical note ⇒ restart technical note technical note.)
TV_BREAK_WALL_SEC = 180.0      # silence real (Wall) technical note technical noteand sampletechnical note technical noteandtechnical note = technical note technical note
TV_RESTART_DISP_BREAK_SEC = 30.0  # gap disp_time watchdog‌technical note (HT/resync) = technical note technical note

# --- versiontechnical note 10technical note15 — technical note technical noteandtechnical note reset + technical note technical notefrom Lifecycle ---
# section‌technical note «after from» technical note boundary — for technical noteandtechnical note without droptechnical note untiltechnical note after from technical note technical note
# (momenttechnical note reset technical noteandtechnical note line technical noteandtechnical note technical note technical note). technical note phase sample must with section aftertechnical note
# technical notefromtechnical note withtechnical note andtechnical note andtechnical note technical note andtechnical note andtechnical note technical noteintechnical note same sectiontechnical note technical note‌istechnical note
# technical note‌technical notefromtechnical note (technical note user: reset = drop untiltechnical note technical noteandtechnical note boundarytechnical note technical note technical noteandtechnical note from technical note).
TV_PHASE_AFTER_RESTART = {
    45.0: ("HALF_2", "ET1", "ET2"),     # after from HT: second half/extra time
    90.0: ("ET1", "ET2"),               # after from FT: extra time
    105.0: ("ET2",),                    # after from technical note ET: second half extra time
}


def tv_phase_allows_restart(bound: float, phase) -> bool:
    """versiontext 10text15 — textor textfrom Lifecycle with «start sectiontext after from boundary» textfromtext istext
    only for textandtext without droptext untiltext after from text text to text text‌textandtext.
    phase=None / text (untiltext legacy and test‌text) → True (textuntiltext beforetext)."""
    if phase is None:
        return True
    try:
        allowed = TV_PHASE_AFTER_RESTART.get(float(bound))
    except (TypeError, ValueError):
        return True
    if allowed is None:
        return True
    try:
        return str(phase) in allowed
    except Exception:
        return True

_tv_bg_cache: Dict[str, Dict[str, Any]] = {}     # kind → {"mtime","arr","geom"}
_tv_flag_cache: Dict[str, Tuple[Any, Any]] = {}  # path → (mtime, arr|None)


def _tv_bg_path(kind: str) -> str:
    return os.path.join(_MOMENTUM_DATA_DIR,
                        TV_BG_DIRNAME, TV_BG_FILES.get(kind, TV_BG_FILES["half"]))


def _tv_group_idx(idx: "np.ndarray") -> List[Tuple[int, int]]:
    """text‌text text‌text textandtext → [(start, end)]"""
    if idx is None or len(idx) == 0:
        return []
    out = []
    s = p = int(idx[0])
    for v in idx[1:]:
        v = int(v)
        if v == p + 1:
            p = v
        else:
            out.append((s, p))
            s = p = v
    out.append((s, p))
    return out


def _tv_detect_geometry(arr: "np.ndarray") -> Dict[str, Any]:
    """
    detection automatic text from textandtext textandtext:
      * text chart = text textcodetext text ‎(58,58,58)‎
      * line text = text textuntiltext in textortext textandtext text
      * lineandtext textandtext = textandtext‌text text textuntiltext inside text (HT/FT/ET)
    output: {"rect": (l,r,t,b), "zero_y": int, "verticals": [x,...]}
    """
    H, W = arr.shape[:2]
    rgb = np.asarray(arr[..., :3], dtype=float)
    if rgb.size and float(rgb.max()) <= 1.001:
        rgb = rgb * 255.0          # input 0..1 (output tv_load_background) technical note technical note technical note‌technical noteandtechnical note
    gray = (np.abs(rgb[:, :, 0] - 58) <= 12) & \
           (np.abs(rgb[:, :, 1] - 58) <= 12) & \
           (np.abs(rgb[:, :, 2] - 58) <= 12)
    white = (rgb[:, :, 0] > 195) & (rgb[:, :, 1] > 195) & (rgb[:, :, 2] > 195)

    grow = gray.sum(axis=1)
    gcols = gray.sum(axis=0)
    rows = np.where(grow > 0.30 * W)[0]
    cols = np.where(gcols > 0.30 * H)[0]
    if len(rows) < 40 or len(cols) < 40:
        raise ValueError("gray plot area not found")
    t, b = int(rows[0]), int(rows[-1])
    l, r = int(cols[0]), int(cols[-1])
    if (b - t) < 60 or (r - l) < 60:
        raise ValueError("plot area too small")

    # --- line technical note: technical note technical noteuntiltechnical note technical note t and b (nearest to technical noteortechnical note) ---
    seg = white[t + 6:b - 6, l + 8:r - 8]
    wrows = np.where(seg.mean(axis=1) > 0.85)[0]
    zero_y = None
    if len(wrows):
        groups = _tv_group_idx(wrows)
        mid = (b - t) / 2.0
        g = min(groups, key=lambda gr: abs((gr[0] + gr[1]) / 2.0 - mid))
        zero_y = t + 6 + (g[0] + g[1]) // 2
    if zero_y is None:
        zero_y = (t + b) // 2

    # --- lineandtechnical note technical noteandtechnical note inside technical note (technical noteandtechnical note technical note line internal technical note only technical notefromtechnical note) ---
    segv = white[t + 10:b - 10, l + 10:r - 10]
    wcols = np.where(segv.mean(axis=0) > 0.80)[0]
    verticals = []
    for g0, g1 in _tv_group_idx(wcols):
        verticals.append(l + 10 + (g0 + g1) // 2)
    # technical noteto‌technical note technical note from technical note lineandtechnical note internal technical note technical noteandtechnical note
    verticals = [x for x in verticals if l + 14 < x < r - 14]

    # --- versiontechnical note 10technical note8 — technical note‌technical note technical noteandtechnical note technical note (technical noteandtechnical note technical noteanduntiltechnical note technical note technical notetotechnical note below technical note) ---
    # technical note technical note‌technical note technical note technical noteandtechnical note‌technical note: 4 technical note = 0/15/30/45(HT)
    # 7 technical note = 0..90 | 9 technical note = 0..120 (with FT=90 and ET=105)
    anchors: List[int] = []
    y0b = b + TV_TICK_BAND_OFF
    y1b = min(H, y0b + TV_TICK_BAND_H)
    if y1b - y0b >= TV_TICK_MIN_ROWS:
        band = white[y0b:y1b, :]
        colhits = band.sum(axis=0)
        tcols = np.where(colhits >= TV_TICK_MIN_ROWS)[0]
        for g0, g1 in _tv_group_idx(tcols):
            cx = (g0 + g1) / 2.0
            if (l - 8) <= cx <= (r + 8):
                anchors.append(int(round(cx)))
        # technical notewithtechnical noteagetechnical note: count must 4/7/9 withtechnical note technical note first technical note technical notetotechnical note technical note and
        # technical note technical note technical note technical notetotechnical note technical noteis (technical noteandtechnical note file‌technical note original ≈ 6 technical note inside‌technical note)
        ok = len(anchors) in TV_TICK_MINUTES_BY_COUNT
        if ok and len(anchors) >= 2:
            ok = (l + 2 <= anchors[0] <= l + 60) and (r - 60 <= anchors[-1] <= r + 2)
            # distancetechnical note technical note‌technical note must technical notewithtechnical note technical noteandtechnical note withtechnical note (without technical note technical note)
            gaps = [anchors[i2] - anchors[i2 - 1] for i2 in range(1, len(anchors))]
            if ok and gaps:
                gmed = float(np.median(gaps))
                ok = all(abs(gp - gmed) <= 0.22 * max(1.0, gmed) for gp in gaps)
        if not ok:
            anchors = []
    return {"rect": (l, r, t, b), "zero_y": int(zero_y),
            "verticals": [int(x) for x in verticals],
            "anchors_x": [int(x) for x in anchors], "W": int(W)}


def tv_fallback_background(kind: str) -> Dict[str, Any]:
    """v2.1.0 — BUILT-IN fallback background, used when
    tex/Half|Full|Extra_Match_Moment.png is missing or unreadable.
    A missing texture used to make tv_load_background return None and
    render_tv_snapshot bail out — the charts then NEVER display even
    though every hook and every data layer is healthy (the exact
    "charts completely gone" field report). This draws the documented
    standard geometry (grey 58-panel + full-width white zero line) at
    the documented size, so the chart pipeline stays ALIVE without the
    texture file; the real PNG is used again the moment it is back."""
    fg = dict(TV_FALLBACK_GEOM.get(kind) or TV_FALLBACK_GEOM["half"])
    W, H = 1608, 978
    if kind == "extra":
        W = 2034
    arr = np.zeros((H, W, 4), dtype=float)
    arr[..., 3] = 1.0                                  # opaque black
    l, r, t, b = fg["rect"]
    arr[t:b + 1, l:r + 1, 0:3] = 58.0 / 255.0          # grey chart panel
    zy = max(0, min(H - 1, int(fg["zero_y"])))
    arr[zy, :, 0:3] = 1.0                              # white zero line
    for vx in (fg.get("verticals") or []):
        if t <= int(vx) <= b:
            arr[t:b + 1, int(vx), 0:3] = 1.0           # HT/FT/ET verticals
    return {"mtime": -1.0, "arr": arr, "geom": dict(fg, W=W), "W": W, "H": H,
            "fallback": True}


_TV_FALLBACK_CACHE: Dict[str, Dict[str, Any]] = {}


def tv_fallback_background_cached(kind: str) -> Dict[str, Any]:
    """v2.1.0 — cached fallback + a ONE-TIME clog evidence line per kind."""
    ent = _TV_FALLBACK_CACHE.get(kind)
    if ent is None:
        try:
            clog(f"[TVBg] texture missing/unreadable: {_tv_bg_path(kind)} "
                 "— charts switch to the BUILT-IN fallback background "
                 "(pipeline stays alive); restore the PNG to get the "
                 "real artwork back")
        except Exception:
            pass
        ent = tv_fallback_background(kind)
        _TV_FALLBACK_CACHE[kind] = ent
    return ent


def tv_load_background(kind: str) -> Optional[Dict[str, Any]]:
    """
    withtext text‌text textandtext text‌pitchtext + text detectiontext.
    output: {"arr": float RGBA (H,W,4) 0..1, "geom": dict, "W": int, "H": int}
    file textandtext/broken textandtext ⇒ None (text empty and text text‌text).
    """
    path = _tv_bg_path(kind)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        # v2.1.0 — the file is GONE: keep the chart pipeline alive with the
        # built-in fallback instead of silently killing every chart.
        return tv_fallback_background_cached(kind)
    cached = _tv_bg_cache.get(kind)
    if cached is not None and cached["mtime"] == mtime:
        return cached
    try:
        from PIL import Image as _PILImage
        im = _PILImage.open(path).convert("RGBA")
        arr = np.asarray(im).astype(float) / 255.0
        try:
            geom = _tv_detect_geometry(arr)
        except Exception:
            geom = dict(TV_FALLBACK_GEOM.get(kind) or TV_FALLBACK_GEOM["half"])
            # technical noteortechnical note fallback in technical noteandtechnical note technical noteandtechnical note technical note file
            ih, iw = arr.shape[:2]
            fw = TV_FALLBACK_GEOM[kind]["rect"][1] + 30
            sx, sy = iw / float(fw), ih / 978.0
            l, r, t, b = geom["rect"]
            geom["rect"] = (int(l * sx), int(r * sx), int(t * sy), int(b * sy))
            geom["zero_y"] = int(geom["zero_y"] * sy)
            geom["verticals"] = [int(x * sx) for x in geom["verticals"]]
            geom["anchors_x"] = []
            geom["W"] = int(iw)
        entry = {"mtime": mtime, "arr": arr, "geom": geom,
                 "W": int(arr.shape[1]), "H": int(arr.shape[0])}
        _tv_bg_cache[kind] = entry
        return entry
    except Exception as ex:
        try:
            clog(f"[TVBg] Errortext withtext {path}: {type(ex).__name__}: {ex}")
        except Exception:
            pass
        # v2.1.0 — unreadable file: built-in fallback (charts stay alive)
        return tv_fallback_background_cached(kind)
        return None


def _tv_anchor_map(kind: str, geom: Dict[str, Any]):
    """text text (px) + minutetext text‌text for text — with fallback textfromtext‌text‌text."""
    anchors = [float(x) for x in (geom.get("anchors_x") or [])]
    ms = TV_TICK_MINUTES_BY_COUNT.get(len(anchors))
    if ms is None:
        base = TV_FALLBACK_TICKS.get(kind) or TV_FALLBACK_TICKS["half"]
        w_base = float(TV_FALLBACK_BASE_W.get(kind, 1608))
        w_img = float(geom.get("W") or w_base)
        s = (w_img / w_base) if w_base else 1.0
        anchors = [x * s for x in base]
        ms = TV_TICK_MINUTES_BY_COUNT[len(anchors)]
    return anchors, ms


def tv_minute_to_x(kind: str, geom: Dict[str, Any], minute: float,
                   band: Optional[Dict[str, float]] = None) -> float:
    """
    text «minutetext text» → text text textandtext (versiontext 10text8 — calibrated with text‌text).
    text = text‌text detection‌data‌text textandtext textandtext:
      half  (4 text) : 0/15/30/45(HT)     ← HT exactly textandtext text text textis
      full  (7 text) : 0/15/30/45(HT)/60/75/90
      extra (9 text) : 0..90(FT)/105(ET)/120
    HT=45 text FT=90 text ET=105 — text linetext text‌text text text‌text textandtext
    text from latest text (andtext‌text text‌text) resumetext linetext with text same text.
    if textandtext text validtext text text‌text textfromtext‌text‌text same text with textortext
    width textandtext istext text‌textandtext.

    versiontext 10text9 — «minute‌text shared»: if band data textandtext ({"bound","s"})text
    minute‌text extra time‌text section beforetext to‌text resumetext linetext in withtext withtext
    «side text» line boundary text text‌textandtext (nearest sample ≈ 1px before from line) —
    text extra timetext text first before from HT text‌text text after from text.
    """
    l, r, _t, _b = geom["rect"]
    anchors, ms = _tv_anchor_map(kind, geom)

    def _map_raw(minute_: float) -> float:
        if minute_ <= ms[0]:
            return float(anchors[0])
        for i in range(1, len(ms)):
            if minute_ <= ms[i]:
                u = (minute_ - ms[i - 1]) / max(1e-9, (ms[i] - ms[i - 1]))
                return anchors[i - 1] + u * (anchors[i] - anchors[i - 1])
        # technical note from latest technical note → resumetechnical note linetechnical note with technical note latest technical note
        i = len(ms) - 1
        rate = (anchors[i] - anchors[i - 1]) / max(1e-9, (ms[i] - ms[i - 1]))
        return anchors[i] + (minute_ - ms[i]) * rate

    if band is not None:
        try:
            bnd = float(band.get("bound", 0.0))
            s_tot = float(band.get("s", 0.0))
        except (TypeError, ValueError):
            return _map_raw(minute)
        # technical note technical note technical noteandtechnical note boundary (for technical note withtechnical note technical note with technical noteortechnical note same technical note)
        rate = (anchors[-1] - anchors[0]) / max(1e-9, (ms[-1] - ms[0]))
        for i in range(1, len(ms)):
            if ms[i - 1] <= bnd <= ms[i]:
                rate = (anchors[i] - anchors[i - 1]) / max(1e-9, (ms[i] - ms[i - 1]))
                break
        delta = max(0.4, TV_STOP_SQUEEZE_FRAC * rate)      # px to fromtechnical note technical note minute
        s_eff = min(max(0.0, s_tot), TV_STOP_BAND_CAP_MIN)
        x_bound = _map_raw(bnd)
        x_off = min(max(minute - bnd, 0.0), s_eff)         # 0..s_eff minute inside withtechnical note
        return x_bound - 1.0 - (s_eff - x_off) * delta

    return _map_raw(minute)


def _tv_timeline(hist: List[Dict[str, float]], restarts_out: Optional[Dict[float, bool]] = None):
    """
    versiontext 10text9 — text shared textandtext timetext TV (text and text‌test).
    output: (minutes, bands, band_idx)
      * minutes : minutetext withtext text sample (NaN = watchdog/invalid — in text text text‌textandtext)
      * bands   : text andtext‌text text‌text text‌text:
                  {"bound": boundary (45/90/105/120), "gt0","gt1": withtext game_time,
                   "s": length extra time to minute}
      * band_idx: text withtext text sample (-1 = text possible is to withtext textandtext
                  text text — side text with text check textandtext)

    text «minute‌text shared» (45-50 / 90-97 / …) — versiontext 10text10 (text user):
      * code «first» text text‌text text textor withtext to minutetext 45 or 90 reset text or text
        restart text: untiltext from minutetext boundary (45:00) text text and to numbertext
        text‌text text and after from text stoptext again from textandtext 45:00 start to
        text text istext
      * until when text textandtext register text text‌text text window (text text minutetext 46
        or 95) textand «extra timetext section beforetext» is (text user: text minutetext 95
        without restarttext register‌text 90 = text text secondtext after from register restart 90
        = text extra timetext first)text
      * to text «confirmation» restarttext section aftertext from textandtext line boundary start to text
        text‌textandtext
      * stop = gap time real text sample‌text (watchdog‌text NaN text 10 second
        gap text) «or» jump textandtext text text (text frozen in text)text
      * jump‌text textandtext textand (resync andtext withtext without stop) ⇒ totaltext textandtextandtextandtext.

    versiontext 10text13 — «confirmation restart» (text user):
      textandtext textandtext boundary only «text» restart istext register text when is text text
      sampletext real (textwatchdog = withtext PLAYING and text textand text) with minutetext
      «text from textandtext boundary» text — text withtext Playing text and untiltext from boundary
      (45/90/105) text text withtext. until before from confirmationtext text‌text windowtext shared
      textand extra timetext section beforetext text‌text (text user: reset untiltext to 90 in
      text text withtext still to extra time text ⇒ chart ET textandtext text‌textandtext).

    versiontext 10text15 — «text textandtext reset» (text text user — text withtext active‌text ET
    to‌text textandtext from minutetext 90 and registertext text andtext textintext text first for text second):
      reset text «game clock andtext drop text and textandtext boundary text withtext»:
        text) reset to 00:00            → new match (Lifecycle — text from text untiltext)
        text) reset to 45:00              → start text second
        text) reset to 90:00 from withtext 90   → start text first extra time
        text) reset to 105:00 from withtext 105 → start text second extra time
      and text text textandtext only when «start text section new»text text withtext Playing textandtext and
      untiltext start to rise text (text confirmation 10text13 — changetext text is).
      messagetext:
        * textandtext textandtext untiltext from 90:00 (andtext textintext text second) never reset
          is not — «drop to boundary» (m < prev_m) text original istext istext textsecond‌text
          text boundary (text extra time/textto free) text restart text‌textfromtext
        * for 90/105 «above textandtext beforetext from boundary» text is (text text/text)text
        * textandtext without drop after from text text text (line textandtext in momenttext reset text
          textandtext — text firsttext sampletext second half in 48') only when text
          text‌textandtext text textfrom Lifecycle (text phase sample) section aftertext text confirmation text
        * until before from resettext confirmationtext text textandtext/sampletext «andtext textintext» (after from
          minutetext text text section) textand same section is — text section aftertext.
    """
    minutes: List[float] = []
    band_idx: List[int] = []
    bands: List[Dict[str, float]] = []
    cur: Optional[Dict[str, float]] = None
    bound_i = 0
    prev_m: Optional[float] = None
    prev_d: Optional[float] = None
    prev_gt: Optional[float] = None
    prev_w: Optional[float] = None      # versiontechnical note 10technical note12 — wall sampletechnical note beforetechnical note (technical note technical note)
    clamp_m: Optional[float] = None       # totaltechnical note technical noteandtechnical noteandtechnical noteandtechnical note (only sample‌technical note real)
    # versiontechnical note 10technical note10 — andtechnical note technical note boundary: technical noteor untiltechnical note from boundary technical note technical note (number technical note‌technical note technical note)
    # and technical noteor restarttechnical note technical note boundary registeredtechnical note istechnical note
    above = {B: False for B in TV_STOP_BOUNDS[:3]}
    restarted = {B: False for B in TV_STOP_BOUNDS[:3]}
    # versiontechnical note 10technical note13 — technical note restart (technical noteandtechnical note technical noteandtechnical note boundary) technical note still «confirmation» technical note‌technical note:
    #   B → {"d": disp momenttechnical note technical noteandtechnical note "up_to_m": latest minutetechnical note before from technical noteandtechnical note
    #        "up_to_gt": latest game_time before from technical noteandtechnical note}
    pending = {}

    def _finalize(c: Dict[str, float], up_to_m: float, d_restart=None) -> None:
        c["s"] = max(float(c.get("s", 0.0)), max(0.0, up_to_m - float(c["bound"])))
        if d_restart is not None and math.isfinite(float(d_restart)):
            c["d1"] = float(d_restart)     # momenttechnical note displaytechnical note restart untiltechnical note
        if float(c["s"]) >= 0.05:
            bands.append(c)

    for s in hist:
        net = s.get("net", float("nan"))
        gt_raw = s.get("game_time", None)
        if gt_raw is None:
            minutes.append(float("nan"))
            band_idx.append(-1)
            continue
        try:
            gt = float(gt_raw)
        except (TypeError, ValueError):
            minutes.append(float("nan"))
            band_idx.append(-1)
            continue
        if not math.isfinite(gt):
            minutes.append(float("nan"))
            band_idx.append(-1)
            continue
        try:
            d = float(s.get("disp_time", gt))
        except (TypeError, ValueError):
            d = gt
        # versiontechnical note 10technical note12 — time real (Wall) sample for technical notefromtechnical note «technical note technical note»
        try:
            w = float(s.get("wall")) if s.get("wall") is not None else None
            if w is not None and not math.isfinite(w):
                w = None
        except (TypeError, ValueError):
            w = None
        m = gt / 60.0
        is_guard = (net != net)

        # --- 1) detection restart untiltechnical note — versiontechnical note 10technical note15 (technical note technical noteandtechnical note reset user) ---
        # reset = «drop real technical note technical noteandtechnical note boundary» + stoptechnical note technical note istechnical note technical noteandtechnical note technical note boundary.
        # technical noteortechnical note complete in docstring withtechnical note (technical note technical note until technical note).
        if prev_m is not None:
            # technical note original reset (versiontechnical note 10technical note15): drop real untiltechnical note to boundary
            is_drop = m < prev_m - 1e-9
            back_ok = math.isfinite(d) and \
                (prev_m - m) >= TV_RESTART_BACKJUMP_MIN
            # --- versiontechnical note 10technical note12 — «technical note technical note»: silence real ≥3 minute (line technical noteandtechnical note
            # data in technical note HT technical note is and firsttechnical note sampletechnical note second half possible is technical note
            # technical noteandtechnical note technical noteortechnical note) or gap displaytechnical note watchdog‌technical note (HT/resync). in technical note technical note
            # technical noteandtechnical note until technical note windowtechnical note shared technical note technical note‌technical noteandtechnical note and jump technical noteand to technical noteandtechnical note
            # firsttechnical note sampletechnical note technical note (delay line technical noteandtechnical note) restart technical note technical note technical note‌technical note.
            wall_gap_ok = (prev_w is not None and w is not None
                           and (w - prev_w) >= TV_BREAK_WALL_SEC)
            try:
                disp_gap_ok = (math.isfinite(d) and prev_d is not None
                               and math.isfinite(prev_d)
                               and (d - prev_d) >= TV_RESTART_DISP_BREAK_SEC)
            except TypeError:
                disp_gap_ok = False
            big_break = bool(wall_gap_ok or disp_gap_ok)
            # stop technical noteanduntiltechnical note real (≥4 second silence wall) for path «drop to boundary»
            wall_stop_ok = (prev_w is not None and w is not None
                            and (w - prev_w) >= TV_RESTART_GAP_SEC)
            for B in TV_STOP_BOUNDS[:3]:        # 45 / 90 / 105
                if restarted.get(B):
                    continue
                from_above = above.get(B, False) and prev_m > B + 1e-9
                # «technical notetotechnical note boundary» only for 45 (HT without andtechnical note technical noteintechnical note — technical note technical note)technical note
                # for 90/105 technical note technical note: technical noteandtechnical note technical note untiltechnical note from boundary in andtechnical note technical noteintechnical note
                # technical note current technical notemust restart technical notefromtechnical note (technical note technical note/technical note user)
                from_edge = (B == 45.0) and \
                    ((B - TV_RESTART_EDGE_EPS) <= prev_m <= (B + 1e-9))
                if not (from_above or from_edge):
                    continue
                if big_break:
                    # technical noteandtechnical note free in total windowtechnical note shared (sampletechnical note firsttechnical note after from technical note)
                    if not ((B - TV_RESTART_LAND_BELOW) <= m
                            <= (B + TV_STOP_WINDOW[B])):
                        continue
                    # versiontechnical note 10technical note15 — technical noteandtechnical note «without drop» after from technical note technical note (line
                    # technical noteandtechnical note in momenttechnical note reset technical note technical noteandtechnical note) only when valid is technical note
                    # technical notefrom Lifecycle technical note section aftertechnical note technical note confirmation technical note andtechnical note andtechnical note
                    # technical note andtechnical note andtechnical note technical noteintechnical note (technical note in same section) technical note‌istechnical note
                    # technical note‌technical notefromtechnical note. (untiltechnical note without technical note phase = technical noteuntiltechnical note beforetechnical note)
                    if from_above and not is_drop and \
                            not tv_phase_allows_restart(B, s.get("phase")):
                        continue
                else:
                    if not ((B - TV_RESTART_LAND_BELOW) <= m
                            <= (B + TV_RESTART_LAND_EPS)):
                        continue
                    if m > prev_m + TV_RESTART_LAND_EPS:
                        continue                 # jump technical noteand to technical noteand ≠ restart
                    if from_above and not is_drop:
                        # versiontechnical note 10technical note15 — technical note user: withtechnical note boundary technical noteandtechnical note to‌technical note
                        # technical note is nottechnical note untiltechnical note must andtechnical note «drop» technical note withtechnical note.
                        # istechnical note technical noteandtechnical note technical note boundary (technical note extra time and…) never
                        # restart is not — technical note withtechnical note ET in technical noteandtechnical note from 90 and register
                        # technical note andtechnical note technical noteintechnical note for section aftertechnical note.
                        continue
                    if from_edge:
                        # end technical note technical noteandtechnical note boundary (HT without andtechnical note technical noteintechnical note): only with
                        # technical note real (gap ≥30s — technical note istechnical note sampling)
                        gap_ok = (prev_d is not None and math.isfinite(prev_d)
                                  and math.isfinite(d)
                                  and (d - prev_d) >= TV_RESTART_EDGE_GAP_SEC)
                        if not (gap_ok or back_ok):
                            continue
                    else:
                        # drop real to boundary + stop (gap ≥4s / silence wall /
                        # jump technical noteandtechnical note technical note — technical note technical note frozen in technical note)
                        gap_ok = (prev_d is not None and math.isfinite(prev_d)
                                  and math.isfinite(d)
                                  and (d - prev_d) >= TV_RESTART_GAP_SEC)
                        if not (gap_ok or back_ok or wall_stop_ok):
                            continue
                # --- versiontechnical note 10technical note13 — technical noteandtechnical note only «technical note» istechnical note register technical note after from
                # confirmation technical note user technical note technical note‌technical noteandtechnical note (Playing + untiltechnical note > boundary).
                # up_to_m/up_to_gt = latest andtechnical note before from technical noteandtechnical note (for technical note withtechnical note).
                pending[B] = {"d": d, "up_to_m": prev_m, "up_to_gt": prev_gt}
                # technical note reset untiltechnical note: totaltechnical note technical noteandtechnical noteandtechnical noteandtechnical note «before from boundary» from technical note moment
                # technical note‌technical notewithtechnical note is (sample‌technical note technical noteandtechnical note boundary = start technical note newtechnical note technical noteuntiltechnical note
                # register-in-technical noteandtechnical note version‌technical note before technical note technical note‌technical noteandtechnical note)
                clamp_m = None
                break

        # --- 1-technical note) confirmation restart technical note (versiontechnical note 10technical note13 — technical note user) ---
        # sampletechnical note real (technical notewatchdog) technical note withtechnical note PLAYING is and technical note technical noteand technical note
        # «Playing + untiltechnical note from boundary technical note» = section aftertechnical note andtechnical note start technical note is.
        if pending and not is_guard:
            for B in TV_STOP_BOUNDS[:3]:
                pd = pending.get(B)
                if pd is None or restarted.get(B):
                    continue
                if m <= B + 1e-9:
                    continue                    # untiltechnical note still from boundary technical note
                if cur is not None:
                    _finalize(cur, pd["up_to_m"], d_restart=pd["d"])
                    cur = None
                elif bands and bands[-1]["bound"] == B:
                    # withtechnical note technical note‌technical note with «technical note from window» — until momenttechnical note technical noteandtechnical note technical note technical noteandtechnical note
                    bands[-1]["gt1"] = pd["up_to_gt"] \
                        if pd["up_to_gt"] is not None else bands[-1]["gt1"]
                    bands[-1]["s"] = max(float(bands[-1]["s"]),
                                         max(0.0, float(pd["up_to_m"]) - B))
                    if math.isfinite(pd["d"]):
                        bands[-1]["d1"] = float(pd["d"])
                bound_i = max(bound_i, min(TV_STOP_BOUNDS.index(B) + 1,
                                           len(TV_STOP_BOUNDS) - 1))
                restarted[B] = True              # confirmation technical note — restart registered
                above[B] = False
                clamp_m = None                   # totaltechnical note in boundary new reset technical note‌technical noteandtechnical note
                del pending[B]

        # --- 1-technical note) register «untiltechnical note from boundary technical note technical note» (number technical note‌technical note from boundary technical note technical note) ---
        for B in TV_STOP_BOUNDS[:3]:
            if not above.get(B, False) and m > B + 1e-9:
                above[B] = True

        # --- 2) technical note from windowtechnical note minute‌technical note shared → boundary aftertechnical note ---
        while (bound_i < len(TV_STOP_BOUNDS) - 1
               and m > TV_STOP_BOUNDS[bound_i] + TV_STOP_WINDOW[TV_STOP_BOUNDS[bound_i]]):
            if cur is not None:
                _finalize(cur, m)
                cur = None
            bound_i += 1

        # --- 3) withtechnical note/technical note withtechnical note extra timetechnical note section technical note ---
        bi = -1
        B = TV_STOP_BOUNDS[bound_i]
        if cur is None:
            if m > B and m <= B + TV_STOP_WINDOW[B]:
                cur = {"bound": float(B), "gt0": gt, "gt1": gt, "s": m - B}
        else:
            if m > float(cur["bound"]):
                cur["gt1"] = gt
                cur["s"] = max(float(cur["s"]), m - float(cur["bound"]))
        if cur is not None:
            bi = len(bands)          # technical note withtechnical note currently withtechnical note technical note from technical note‌technical note

        # --- 4) output minute (totaltechnical note technical noteandtechnical noteandtechnical noteandtechnical note only for sample‌technical note real) ---
        if is_guard:
            minutes.append(float("nan"))
        else:
            om = m
            if clamp_m is not None and om < clamp_m:
                om = clamp_m
            clamp_m = om
            minutes.append(om)
        band_idx.append(bi)
        prev_m, prev_d, prev_gt, prev_w = m, d, gt, w

    if cur is not None:
        _finalize(cur, prev_m if prev_m is not None else float(cur["bound"]))
    if restarts_out is not None:
        try:
            restarts_out.update(restarted)
        except Exception:
            pass
    return minutes, bands, band_idx


def tv_build_minutes(hist: List[Dict[str, float]]) -> List[float]:
    """
    versiontext 10text9 — textandtext «minutetext text» for text sampletext history text text
    game_time text (game clock). because text textandtext minutetext text text‌text
    (HT=45 text FT=90 text ET=105)text gap HT to‌textandtext text textandtext line HT text‌text and
    textand text exactly from text HT to text text‌text (textandtext again text
    textandtext‌text textandtext automatic is).
      * sample‌text NaN watchdog → NaN (in text text text‌textandtext)
      * restart untiltext (45→45 / 90→90 / 105→105 text from gap textandtext) →
        minute‌text section new from textandtext boundary resume text‌ortext (totaltext text‌sectiontext text text)
      * jump‌text textandtext text (resync andtext withtext) → totaltext textandtextandtextandtext
    """
    return _tv_timeline(hist)[0]


def tv_stop_bands(hist: List[Dict[str, float]]) -> List[Dict[str, float]]:
    """versiontext 10text9 — list «andtext‌text text‌text» (minute‌text shared) text section.
    output: [{"bound": 45/90/105/120, "gt0","gt1": withtext game_time, "s": length}]"""
    return _tv_timeline(hist)[1]


def tv_restart_flags(hist: List[Dict[str, float]]) -> Dict[float, bool]:
    """versiontext 10text13 — codetext boundarytext restarttext «confirmationtext» text (45/90/105).
    confirmation = textandtext textandtext boundary + aftertext text sampletext real (PLAYINGtext text textandtext) with
    minutetext text from textandtext boundary text text withtext (text user for «start real
    section aftertext»). textandtext without confirmation (text reset untiltext to 90 when withtext resume
    textdecreasetext) text False is and chart section aftertext textandtext text‌textandtext."""
    out: Dict[float, bool] = {}
    try:
        _tv_timeline(hist, restarts_out=out)
    except Exception:
        pass
    return out


def tv_band_for_time(bands: List[Dict[str, float]], gt: float,
                     disp: Optional[float] = None) -> Optional[Dict[str, float]]:
    """withtext extra time‌text text text game_time inside text decrease text‌text (None = text).
    versiontext 10text9 — minute‌text shared textand withtext text text‌textandtext boundary detection «text first/second»
    disp_time is (momenttext restart untiltext in withtext save text‌textandtext): if sample/
    text after from restart withtext text inside withtext extra timetext section before is not."""
    try:
        g = float(gt)
    except (TypeError, ValueError):
        return None
    try:
        dsp = float(disp) if disp is not None else None
    except (TypeError, ValueError):
        dsp = None
    for b in bands or []:
        try:
            if not (float(b["gt0"]) <= g <= float(b["gt1"])):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        d1 = b.get("d1")
        if dsp is not None and d1 is not None and dsp >= float(d1):
            continue                          # technical note second (after from restart) → technical note
        return b
    return None


def tv_marker_minute(mk: Dict[str, Any]) -> Optional[float]:
    """minutetext text text text text — text text game_time text (same textandtext text‌text)."""
    try:
        gt = float(mk.get("game_time", float("nan")))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(gt):
        return None
    return gt / 60.0


def _tv_internal_verticals(kind: str, geom: Dict[str, Any]) -> List[float]:
    """
    lineandtext textandtext textuntiltext text must «textandtext fill» withtext textandtext (text textandtext sample —
    only lineandtext text‌text HT/FT/ETtext text text‌text 15 minute‌text):
      text full : line HT (45′)
      text extra: lineandtext HT (45′) + FT (90′) + ET (105′)
      text half : HT textandtext texttotext textis is → text
    """
    out = []
    l, r, _t, _b = geom["rect"]
    named = {45.0, 90.0, 105.0}
    anchors = [float(x) for x in (geom.get("anchors_x") or [])]
    ms = TV_TICK_MINUTES_BY_COUNT.get(len(anchors))
    if ms is None:
        base = TV_FALLBACK_TICKS.get(kind) or TV_FALLBACK_TICKS["half"]
        w_base = float(TV_FALLBACK_BASE_W.get(kind, 1608))
        w_img = float(geom.get("W") or w_base)
        s = (w_img / w_base) if w_base else 1.0
        anchors = [x * s for x in base]
        ms = TV_TICK_MINUTES_BY_COUNT[len(anchors)]
    for m, x in zip(ms, anchors):
        if m in named and l + 14 < x < r - 14:
            out.append(float(x))
    return out


def tv_process_flag(path: str) -> Optional["np.ndarray"]:
    """
    text‌textfromtext logo/text for text TV (versiontext 10text8 — text textandtext sample):
      * text to «textside colortext» file (text text text) — istextandtext textandtext textandtext colortext
        text text‌textandtext text textandtext total image
      * istextandtext text text textfromtext (≈3px) with distancetext text (≈2px) from textandtext — text sample
      * text textfromtext: logo+istextandtext never text‌text from text text text‌textandtext
    output text RGBA float 0..1 — text text text (path, mtime).
    """
    if Image is None:
        return None
    try:
        mt = os.path.getmtime(path)
    except OSError:
        return None
    cached = _tv_flag_cache.get(path)
    if cached is not None and cached[0] == mt:
        return cached[1]
    out = None
    try:
        from PIL import ImageChops as _ImageChops
        from PIL import ImageFilter as _ImageFilter
        im = Image.open(path).convert("RGBA")
        # --- technical note to technical noteandtechnical note colortechnical note (technical note‌technical note with technical note technical note) ---
        a_arr = np.asarray(im)[:, :, 3]
        ys, xs = np.where(a_arr >= 8)
        if len(ys) == 0:
            _tv_flag_cache[path] = (mt, None)
            return None
        im = im.crop((int(xs.min()), int(ys.min()),
                      int(xs.max()) + 1, int(ys.max()) + 1))
        # --- technical noteortechnical note technical noteandtechnical note (2 technical note for istechnical noteandtechnical note smooth and technical noteandtechnical note‌technical note technical note) ---
        ss = 2
        w, h = im.size
        scale = min(TV_FLAG_CONTENT_W * ss / max(1, w),
                    TV_FLAG_CONTENT_MAX_H * ss / max(1, h))
        nw, nh = max(2, int(round(w * scale))), max(2, int(round(h * scale)))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        alpha = im.getchannel("A")

        # --- istechnical noteandtechnical note technical noteandtechnical note with distance: technical note technical note technical note technical note (with technical note‌technical note technical note) ---
        k_gap = max(1, TV_FLAG_GAP_PX * ss)
        k_out = max(k_gap + 1, (TV_FLAG_GAP_PX + TV_FLAG_STROKE_PX) * ss)

        def _dilate(mask, k):
            # MaxFilter technical note output = technical notefromtechnical note technical noteandtechnical note + 2k (technical note technical note technical note technical note‌technical noteandtechnical note)
            w0, h0 = mask.size
            pad = k + 2
            big = Image.new("L", (w0 + 2 * pad, h0 + 2 * pad), 0)
            big.paste(mask, (pad, pad))
            d = big.filter(_ImageFilter.MaxFilter(2 * k + 1))
            a0 = pad - k
            return d.crop((a0, a0, a0 + w0 + 2 * k, a0 + h0 + 2 * k))

        d_out = _dilate(alpha, k_out)              # = technical noteandtechnical note technical note (nw+2m × nh+2m)
        d_gap = _dilate(alpha, k_gap)              # technical noteandtechnical note‌technical note — technical note‌technical note technical note‌technical noteandtechnical note
        d_gap_pad = Image.new("L", d_out.size, 0)
        d_gap_pad.paste(d_gap, (k_out - k_gap, k_out - k_gap))
        ring = _ImageChops.subtract(d_out, d_gap_pad)
        ring = ring.filter(_ImageFilter.GaussianBlur(1.2))   # technical noteto/technical noteandtechnical note smooth
        m = k_out
        canvas = Image.new("RGBA", (nw + 2 * m, nh + 2 * m), (0, 0, 0, 0))
        white_ring = Image.new("RGBA", ring.size, (255, 255, 255, 255))
        canvas.paste(white_ring, (0, 0), ring)
        canvas.paste(im, (m, m), im)
        canvas = canvas.resize((max(1, canvas.width // ss),
                                max(1, canvas.height // ss)),
                               Image.Resampling.LANCZOS)
        out = np.asarray(canvas).astype(float) / 255.0
    except Exception as ex:
        clog(f"[TVFlag] Errortext textfromtext {path}: {type(ex).__name__}: {ex}")
        out = None
    _tv_flag_cache[path] = (mt, out)
    return out


# --- technical note‌technical note versiontechnical note 10technical note8 (technical note and technical note‌test without withtechnical note) ---

def _tv_lighten(color, f: float = 0.35):
    """(versiontext 10text10 — line texttotext fill text text untiltext only for textfromtext text text text.)"""
    try:
        from matplotlib import colors as _mcolors
        r, g, b = _mcolors.to_rgb(color)
    except Exception:
        r, g, b = 1.0, 1.0, 1.0
    return (r + (1.0 - r) * f, g + (1.0 - g) * f, b + (1.0 - b) * f)


def _tv_split_sign_segments(px: "np.ndarray", py: "np.ndarray", zero_y: float):
    """
    text text to text‌text textregister/text ratio to line text — text textandtext from text
    with inandtext‌ortext to text textand text text text‌textandtext (fill/textand/textto without text).
    output: (pos_segs, neg_segs) — text text = (xs, ys) text numpy.
    """
    pos_segs, neg_segs = [], []
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    if len(px) < 2:
        return pos_segs, neg_segs

    def _flush(sign, xs, ys):
        if len(xs) >= 2:
            (pos_segs if sign > 0 else neg_segs).append(
                (np.asarray(xs, dtype=float), np.asarray(ys, dtype=float)))

    cur = 1 if py[0] <= zero_y else -1
    cx, cy = [float(px[0])], [float(py[0])]
    for i in range(1, len(px)):
        s = 1 if py[i] <= zero_y else -1
        if s == cur:
            cx.append(float(px[i]))
            cy.append(float(py[i]))
        else:
            y0, y1 = cy[-1], float(py[i])
            u = (zero_y - y0) / max(1e-9, y1 - y0)
            xc = cx[-1] + u * (float(px[i]) - cx[-1])
            cx.append(xc)
            cy.append(zero_y)
            _flush(cur, cx, cy)
            cur = s
            cx, cy = [xc, float(px[i])], [zero_y, float(py[i])]
    _flush(cur, cx, cy)
    return pos_segs, neg_segs


def _tv_pixel_bin(px: "np.ndarray", py: "np.ndarray", step: float = 1.5):
    """
    textortext‌text sample‌text inside text textandtext text (width step) — text text
    text texttotext fill («text»). output (bx, by) with length ≤ width text/step.
    """
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    if len(px) < 8:
        return px, py
    bi = np.floor(px / max(0.2, float(step))).astype(np.int64)
    b0 = int(bi.min())
    nb = int(bi.max()) - b0 + 1
    if nb >= len(px):            # technical note below — technical noteortechnical note‌technical note technical note‌technical note
        return px, py
    cnt = np.bincount(bi - b0, minlength=nb).astype(float)
    sx = np.bincount(bi - b0, weights=px, minlength=nb)
    sy = np.bincount(bi - b0, weights=py, minlength=nb)
    m = cnt > 0
    return sx[m] / cnt[m], sy[m] / cnt[m]


def _tv_extra_edge_smooth(by: "np.ndarray", sigma_samples: float,
                          max_shift: float = None) -> "np.ndarray":
    """versiontext 10text16 — textandtextfromtext text «texttotext» chart (text 3-text text user):
    textandtext text‌aftertext textandtext height textandtext‌text text from binningtext text text text «sample»
    (text sample ≈ TV_BIN_STEP_PX text). input user from textin text textandtext
    text chart text‌text (TV_EDGE_SMOOTH_PX text text text)text number text aftertext
    textcode textandtext text. text layer only displaytext is — textandtext textandtextandtext unchanged.
    versiontext 10text17 — «text texttotal» (text user: smoothing only for textto istext text change
    texttotal chart): textandtext text peak‌text text text and height‌text text textto‌text text‌text
    text‌text output textandtext with «totaltext smooth tanh» to value original textandtext text‌textandtext:
        delta = lim · tanh((smooth − original) / lim)
    text textto‌text‌text textandtext (text‌text text) completetext text text‌textandtext
    (textto text text‌textandtext) andtext text textandtext text from lim (≈TV_EDGE_SMOOTH_MAX_SHIFT_PX
    text) from value original textandtext text‌textandtext ⇒ peak‌text/valley‌text and texttotal totaltext text text
    text‌text. max_shift=None → textuntiltext legacy (without totaltext for test‌text)."""
    try:
        by = np.asarray(by, dtype=float)
        sig = float(sigma_samples)
    except Exception:
        return by
    if sig <= 0.05 or by.size < 8:
        return by
    try:
        sm = _gauss_smooth_impl([float(v) for v in by], sig)
        out = np.asarray(sm, dtype=float)
        if out.size != by.size:
            return by
        if max_shift is not None:
            lim = float(max_shift)
            if lim > 0.0:
                delta = lim * np.tanh((out - by) / lim)
                out = by + delta
        return out
    except Exception:
        return by


def _tv_uniform_resample(bx: "np.ndarray", by: "np.ndarray",
                         step: float = 0.5):
    """versiontext 10text25 — withtextsampling text textandtext text text «textandtext».
    output binningtext textandtext‌text with text text‌distance text‌text (text = textortext x
    sample‌text same textandtext)text text‌text text text text texttotext fill text text‌text
    text‌text. text‌text text with inandtext‌ortext linetext textandtext text text step text
    sampling text‌textandtext ⇒ distancetext text always textandtext texttotext textandtext.
    valuetext from «same» text binning text‌text ⇒ text peak/valley‌text textto‌text
    or text text‌textandtext (only withtext text‌text textandtext x textandtext)."""
    try:
        bx = np.asarray(bx, dtype=float)
        by = np.asarray(by, dtype=float)
    except Exception:
        return bx, by
    if bx.size < 8 or bx.size != by.size:
        return bx, by
    step = max(0.1, float(step))
    try:
        # xp for np.interp must technical note technical noteandtechnical note withtechnical note — versiontechnical note first technical note technical note
        keep = np.concatenate(([True], np.diff(bx) > 1e-9))
        bxu, byu = bx[keep], by[keep]
        if bxu.size < 8:
            return bx, by
        x0 = float(np.ceil(bxu[0] / step) * step)
        x1 = float(bxu[-1])
        if not np.isfinite(x0) or not np.isfinite(x1) or x1 - x0 < step * 4.0:
            return bx, by
        gx = np.arange(x0, x1, step)
        if gx.size < 8:
            return bx, by
        gy = np.interp(gx, bxu, byu)
        return gx, gy
    except Exception:
        return bx, by


def _tv_pchip_slopes(bx: "np.ndarray", by: "np.ndarray") -> "np.ndarray":
    """versiontext 10text26 — text‌text textermite textandtextandtextandtext (Fritsch–Carlson) for PCHIP.
    output: text (dy/dx) in text text text: text textandtext (overshoot) text textand
    text textandtext text text‌textandtext ⇒ texttotal data (peak/valley/text real) text text
    text‌textandtext — only text text text‌text «textandtext» text‌textandtext."""
    h = np.diff(bx)
    d = np.diff(by) / h
    m = np.zeros_like(by)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(by) - 1):
        if d[i - 1] * d[i] <= 0.0:
            m[i] = 0.0                     # technical note technical note — technical note technical note
        else:
            w1 = 2.0 * h[i] + h[i - 1]
            w2 = h[i] + 2.0 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def _tv_pchip_eval(bx: "np.ndarray", by: "np.ndarray",
                   gx: "np.ndarray") -> "np.ndarray":
    """textortext text‌text text text textandtext text gx (bx textandtext text text‌textandtext)."""
    h = np.diff(bx)
    m = _tv_pchip_slopes(bx, by)
    idx = np.clip(np.searchsorted(bx, gx, side="right") - 1, 0, len(bx) - 2)
    hx = h[idx]
    t = (gx - bx[idx]) / hx
    t2 = t * t
    t3 = t2 * t
    h00 = 2.0 * t3 - 3.0 * t2 + 1.0
    h10 = t3 - 2.0 * t2 + t
    h01 = -2.0 * t3 + 3.0 * t2
    h11 = t3 - t2
    return (h00 * by[idx] + h10 * hx * m[idx]
            + h01 * by[idx + 1] + h11 * hx * m[idx + 1])


def _tv_uniform_resample_c1(bx: "np.ndarray", by: "np.ndarray",
                            step: float = 0.5):
    """versiontext 10text26 — withtextsampling «text textandtextandtextandtext» textandtext text textandtext.
    text real «text‌text»: versiontext linetext (np.interp) text text‌text ~0text9 text
    text text in «text text» text textandtext text‌text ⇒ textandtext textortext text ⇒
    text‌text text and totalandtext‌text in textandtext. inandtext‌ortext PCHIP: from «text» text‌text
    text‌text (height peak/valley text before)text textandtextandtextandtext is (text textandtext text)text
    and text text text‌text textandtext is ⇒ texttotext text textandtext and text text‌textandtext.
    change texttotal ratio to versiontext linetext ≤ text textandtext (~0text3px) — text."""
    try:
        bx = np.asarray(bx, dtype=float)
        by = np.asarray(by, dtype=float)
    except Exception:
        return bx, by
    if bx.size < 8 or bx.size != by.size:
        return bx, by
    step = max(0.1, float(step))
    try:
        keep = np.concatenate(([True], np.diff(bx) > 1e-9))
        bxu, byu = bx[keep], by[keep]
        if bxu.size < 8:
            return bx, by
        x0 = float(np.ceil(bxu[0] / step) * step)
        x1 = float(bxu[-1])
        if not np.isfinite(x0) or not np.isfinite(x1) or x1 - x0 < step * 4.0:
            return bx, by
        gx = np.arange(x0, x1, step)
        if gx.size < 8:
            return bx, by
        if not (np.all(np.isfinite(bxu)) and np.all(np.isfinite(byu))):
            return _tv_uniform_resample(bx, by, step)
        gy = _tv_pchip_eval(bxu, byu, gx)
        if not np.all(np.isfinite(gy)):
            return _tv_uniform_resample(bx, by, step)
        return gx, gy
    except Exception:
        return _tv_uniform_resample(bx, by, step)


def _tv_micro_edge_smooth(by: "np.ndarray", sigma_px: float,
                          step_px: float) -> "np.ndarray":
    """versiontext 10text25 — textandtext «text» textandtext height textandtext‌text text textandtext.
    only text textandtext textortext ~1 text text text‌textandtext because text (‎0text6px‎) text‌text
    withtext textandtext‌text from width andtext‌text chart (peak/valley ≥ ~10px) istext decrease height
    peak‌text < 0text2text and textto‌text text is — text totaltext chart text before text‌text.
    (text textandtext textandtext texttotal with test «text text» text verify text‌textandtext.)"""
    try:
        by = np.asarray(by, dtype=float)
        s = float(sigma_px) / max(0.05, float(step_px))
    except Exception:
        return by
    if s <= 0.05 or by.size < 8:
        return by
    try:
        return _smooth_segment(by, s)
    except Exception:
        return by


# --- versiontechnical note 10technical note15 — technical note «technical note technical note» technical note line technical note (technical note user) ---
# when technical note for technical note technical note to line technical note technical note technical note‌technical note intechnical note technical noteandtechnical note same technical noteside
# technical note technical noteandtechnical note technical note technical note and technical note technical noteandtechnical note line technical note technical note‌technical notefromtechnical note (user: «technical note color Home
# in andtechnical note chart»). intechnical note: weight technical note technical noteandtechnical note = distancetechnical note technical note until line technical note in same
# technical noteandtechnical note technical note technical note → intechnical note technical note technical noteandtechnical note from technical note → intechnical note complete.
TV_GLOW_ZERO_NEAR_PX = 5.0     # (default technical notefromtechnical note — path render from thresholdtechnical note «andtechnical note» istechnical note technical note‌technical note)
TV_GLOW_ZERO_FAR_PX = 30.0     # distancetechnical note technical note from technical note → intechnical note complete
TV_GLOW_ZERO_SPREAD_PX = 24.0  # radius technical note technical note distance (technical noteandtechnical note technical note from technical note technical note technical noteandtechnical note)
# --- versiontechnical note 10technical note16 — technical note real «technical note» technical note technical note ---
# thresholdtechnical note legacy (5 until 30 technical note ≈ 3 until 16 andtechnical note) never intechnical note technical note‌technical note
# 10-20 andtechnical note (20-40 technical note) technical note technical note‌technical note — same technical noteandtechnical note technical note colortechnical note technical note line
# technical note technical note user again technical note technical note. thresholdtechnical note new technical note technical note «andtechnical note height chart»
# is (technical note technical note) until with technical noteortechnical note technical noteandor technical note correct technical note:
TV_GLOW_ZERO_NEAR_VAL = 18.0   # technical note‌technical note from 18 andtechnical note → without intechnical note (technical note technical note)
TV_GLOW_ZERO_FAR_VAL = 42.0    # technical noteandtechnical note from 42 andtechnical note → intechnical note complete


def _tv_zero_fade_weight(segs, hw: int, sc: float, zero_y: float,
                         gs: float, near_px: float = None,
                         far_px: float = None) -> "np.ndarray":
    """weight 0..1 text textandtext textandtext for text intext text to line text.
    distancetext text until line text per-column texttotext text text (max-filter) and
    smooth text‌textandtext until textandtext text from text (text distance in text textandtext text is) intext
    textandtext text from text text only textside‌text «text to text» text‌text text‌textandtext.
    versiontext 10text16 — near_px/far_px optional: path render real threshold text text
    text «andtext height chart» (TV_GLOW_ZERO_NEAR/FAR_VAL ÷ textortext textandor)
    text‌text without textandtext = text‌text legacy text (textfromtext test‌text)."""
    INF = 1e9
    d = np.full(int(hw), INF, dtype=float)
    for (xs, ys) in (segs or []):
        if xs is None or len(xs) < 1:
            continue
        xs_f = np.asarray(xs, dtype=float)
        ys_f = np.asarray(ys, dtype=float)
        # technical note‌technical notefromtechnical note: distancetechnical note until technical note must «in technical note technical noteandtechnical note‌technical note technical note technical note» technical note
        # correct withtechnical note (technical note only in technical note technical noteandtechnical note technical note) — in technical note technical note technical noteandtechnical note with input
        # technical note‌technical note technical note technical note technical noteand technical note live technical note‌technical note
        if len(xs_f) >= 2:
            n_src = len(xs_f)
            span_cols = max(2.0, float(np.nanmax(np.abs(np.diff(xs_f))) * sc))
            n_dens = int(min(200000, max(n_src, span_cols * 2.0)))
            xd = np.linspace(0, n_src - 1, n_dens)
            xs_f = np.interp(xd, np.arange(n_src), xs_f)
            ys_f = np.interp(xd, np.arange(n_src), ys_f)
        xc = np.floor(xs_f * float(sc)).astype(np.int64)
        dy = np.abs(ys_f - float(zero_y)) * float(sc)
        ok = (xc >= 0) & (xc < int(hw)) & np.isfinite(dy)
        if np.any(ok):
            np.minimum.at(d, xc[ok], dy[ok])
    d = np.minimum(d, TV_GLOW_ZERO_FAR_PX * gs * sc * 4.0)   # technical note for technical note
    k = int(max(0, round(TV_GLOW_ZERO_SPREAD_PX * gs * sc)))
    if k > 0:
        pad = np.pad(d, (k, k), constant_values=INF)
        w = d.shape[0]
        d = np.max(np.stack([pad[i:i + w] for i in range(2 * k + 1)], axis=0),
                   axis=0)
    near = (TV_GLOW_ZERO_NEAR_PX if near_px is None
            else float(near_px)) * gs * sc
    far = (TV_GLOW_ZERO_FAR_PX if far_px is None
           else float(far_px)) * gs * sc
    wgt = np.clip((d - near) / max(1e-6, (far - near)), 0.0, 1.0)
    try:                                   # technical noteto‌technical note weight smooth technical noteandtechnical note
        from PIL import ImageFilter as _IF0
        im1 = Image.new("L", (int(hw), 1), 0)
        im1.putdata((wgt * 255.0).astype(np.uint8).tolist())
        im1 = im1.filter(_IF0.GaussianBlur(max(1.0, 3.0 * gs * sc)))
        wgt = np.asarray(im1, dtype=float).reshape(-1) / 255.0
    except Exception:
        pass
    return wgt


def _tv_glow_layers(pos_segs, neg_segs, W, H, home_color, away_color,
                    rect_h, zero_y: float,
                    near_px: float = None, far_px: float = None) -> list:
    """versiontext 10text24 — text textwithtext intext textandtext (without ax/matplotlib):
    text line text with «textandtext textandtext real» in text‌andtextandtext + text textandtext text
    line text — output: [(rgba_floattext color)text ...] to order Home/Away.
    text _tv_draw_glow (path matplotlib) and text scene-builder GPU from text
    istext text‌text until intext in text textand path «textand‌to‌textand» text withtext.
    (textortext text from _tv_draw_glow versiontext 10text16 text text is.)"""
    from PIL import ImageDraw as _IDraw
    from PIL import ImageFilter as _IFilter
    from matplotlib import colors as _mcolors
    layers = []
    try:
        soft_mul = max(0.05, float(TV_GLOW_SOFTNESS_MUL))
        inten_mul = max(0.0, float(TV_GLOW_INTENSITY_MUL))
    except Exception:
        soft_mul, inten_mul = 1.0, 1.0
    if inten_mul <= 0.001:
        return layers                  # technical note technical note — user intechnical note technical note technical noteandtechnical note technical note
    hw, hh = max(2, int(W) // 2), max(2, int(H) // 2)
    sc = hw / float(W)                      # technical noteortechnical note technical note‌andtechnical noteandtechnical note
    gs = rect_h / 560.0                     # technical noteortechnical note with height technical note
    lw_half = max(1, int(round(TV_GLOW_CORE_PX * gs * sc)))
    for color, segs in ((home_color, pos_segs), (away_color, neg_segs)):
        if not segs:
            continue
        mask = Image.new("L", (hw, hh), 0)
        dr = _IDraw.Draw(mask)
        drew = False
        for (xs, ys) in segs:
            if len(xs) < 2:
                continue
            pts = [(float(x) * sc, float(y) * sc) for x, y in zip(xs, ys)]
            dr.line(pts, fill=255, width=lw_half, joint="curve")
            drew = True
        if not drew:
            continue
        acc = np.zeros((hh, hw), dtype=float)
        for sig_base, peak in TV_GLOW_LAYERS:
            sig = max(0.6, sig_base * gs * sc * soft_mul)   # 10technical note16 — smoothing
            bl = np.asarray(mask.filter(_IFilter.GaussianBlur(sig)),
                            dtype=float) / 255.0
            acc += bl * (float(peak) * inten_mul)           # 10technical note16 — technical note
        np.clip(acc, 0.0, 1.0, out=acc)
        # --- versiontechnical note 10technical note15/10technical note16 — technical note technical note technical note line technical note (per-column) ---
        zw = _tv_zero_fade_weight(segs, hw, sc, zero_y, gs,
                                  near_px=near_px, far_px=far_px)
        acc = acc * zw[None, :]
        rgba = np.zeros((hh, hw, 4), dtype=float)
        try:
            r, g, b = _mcolors.to_rgb(color)
        except Exception:
            r, g, b = 1.0, 1.0, 1.0
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = r, g, b
        rgba[..., 3] = acc
        layers.append((rgba, str(color)))
    return layers


def _tv_draw_glow(ax, pos_segs, neg_segs, W, H, clip,
                  home_color, away_color, rect_h, zero_y: float,
                  near_px: float = None, far_px: float = None) -> int:
    """
    intext textandtext smooth (versiontext 10text8): text line text with «textandtext textandtext real» —
    textandtext from line to outside to‌textandtext completetext smooth textand text‌textandtext (without text).
    text in text‌andtextandtext text text‌textandtext (textandtext text‌text is) → fast and text.
    versiontext 10text15 — intext text color in textandtext‌text text text same color text to
    line text is text text‌textandtext (text text text text — text user).
    versiontext 10text16 — text‌text textandtext user: TV_GLOW_SOFTNESS_MUL (text textandtext)
    and TV_GLOW_INTENSITY_MUL (text textandtext)text text text → intext text text
    text‌textandtext. near_px/far_px → thresholdtext «andtext» text text (text 4).
    versiontext 10text24 — textortext to _tv_glow_layers text text (shared with path GPU)text
    output text untiltext text‌to‌text text before is.
    output: count layer‌text intext text‌text.
    """
    info = 0
    for rgba, _color in _tv_glow_layers(pos_segs, neg_segs, W, H,
                                        home_color, away_color, rect_h,
                                        zero_y, near_px=near_px,
                                        far_px=far_px):
        im = ax.imshow(rgba, extent=(0, W, H, 0), zorder=2,
                       interpolation="bilinear", filternorm=False)
        im.set_clip_path(clip)
        info += 1
    return info


def _tv_marker_glow_calc(gx: float, y_line0: float, y_line1: float,
                         ball_cy: float, ball_r: float,
                         rect_h: float) -> Optional[Dict[str, Any]]:
    """versiontext 10text24 — texttotext intext text textandtext «line textandtext text + icon ball»
    (without ax): text text + textandtext textandtext in textand layer — output rgba text‌withtext +
    coordinates text in text text (x0, y0, x1, y1) for imshow or Quad GPU.
    (textortext text from _tv_draw_marker_glow versiontext 10text9.)"""
    from PIL import ImageDraw as _IDraw
    from PIL import ImageFilter as _IFilter
    gs = rect_h / 560.0
    sig_max = max(sig for sig, _p in TV_MARKER_GLOW_LAYERS) * gs
    pad = ball_r + 4.0 * sig_max + 6.0
    x0 = int(math.floor(gx - pad))
    x1 = int(math.ceil(gx + pad))
    y0 = int(math.floor(min(y_line0, y_line1, ball_cy) - pad))
    y1 = int(math.ceil(max(y_line0, y_line1, ball_cy) + pad))
    w, h = x1 - x0, y1 - y0
    if w < 4 or h < 4:
        return None
    lw = max(2, int(round(TV_GLINE_FRAC * rect_h * 1.7)))
    mask = Image.new("L", (w, h), 0)
    dr = _IDraw.Draw(mask)
    lx = gx - x0
    dr.line([(lx, y_line0 - y0), (lx, y_line1 - y0)], fill=255, width=lw)
    br = max(2.0, ball_r * 0.92)
    cx = gx - x0
    cy = ball_cy - y0
    dr.ellipse([cx - br, cy - br, cx + br, cy + br], fill=255)
    acc = np.zeros((h, w), dtype=float)
    for sig_base, peak in TV_MARKER_GLOW_LAYERS:
        sig = max(0.6, sig_base * gs)
        bl = np.asarray(mask.filter(_IFilter.GaussianBlur(sig)), dtype=float) / 255.0
        acc += bl * float(peak)
    np.clip(acc, 0.0, 1.0, out=acc)
    rgba = np.zeros((h, w, 4), dtype=float)
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = 1.0     # technical note
    rgba[..., 3] = acc
    return {"rgba": rgba, "x0": float(x0), "y0": float(y0),
            "x1": float(x1), "y1": float(y1)}


def _tv_draw_marker_glow(ax, gx: float, y_line0: float, y_line1: float,
                         ball_cy: float, ball_r: float, clip,
                         rect_h: float, gid: str) -> int:
    """
    versiontext 10text9 — intext smoothtext text textandtext «line textandtext text + icon ball».
    text text (line + text ball) with textandtext textandtext real in textand layer — text
    text completetext smooth text from line to outside textand text‌textandtext (without text). layer text
    line text (zorder 5 < 6) is until line text/text text‌text text textandtext.
    versiontext 10text24 — textortext to _tv_marker_glow_calc text text (shared with GPU)text
    output text‌to‌text text before is.
    output: 1 if text text andtext 0.
    """
    calc = _tv_marker_glow_calc(gx, y_line0, y_line1, ball_cy, ball_r,
                                rect_h)
    if calc is None:
        return 0
    rgba = calc["rgba"]
    im = ax.imshow(rgba, extent=(calc["x0"], calc["x1"], calc["y1"],
                                 calc["y0"]), zorder=5,
                   interpolation="bilinear", filternorm=False)
    im.set_clip_path(clip)
    im.set_gid(gid)
    return 1


def _tv_timestamp_bitmap(text: str) -> Optional[np.ndarray]:
    """versiontext 10text24 — render «text‌text»text text untiltext/text (text + text) to text‌text
    RGBA text‌textandtext — textandtext textandtext text (text from path display live). output for
    Quad text GPUtext text text‌text = text text (text ax.text with ha/va=center).
    textandtext/textfromtext/text text same text inandtext‌charttext is (dpi=100)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    try:
        dpi = 100.0
        txt = str(text)
        est_w = max(120, int(len(txt) * TV_TIMESTAMP_FONT_PT * 0.72) + 90)
        est_h = int(TV_TIMESTAMP_FONT_PT * 3.4)
        fig = Figure(figsize=(est_w / dpi, est_h / dpi), dpi=dpi)
        canvas = FigureCanvasAgg(fig)
        ax = fig.add_subplot(111)
        ax.set_position([0, 0, 1, 1])
        ax.axis("off")
        ax.set_xlim(0, est_w)
        ax.set_ylim(est_h, 0)
        fig.patch.set_facecolor("none")
        fig.patch.set_alpha(0.0)
        ax.set_facecolor("none")
        ax.text(est_w * 0.5, est_h * 0.5, txt,
                ha="center", va="center", color="#f5f5f5",
                fontsize=TV_TIMESTAMP_FONT_PT, fontweight="bold",
                family="DejaVu Sans",
                bbox=dict(boxstyle="round,pad=0.35",
                          facecolor="#000000",
                          edgecolor="none",
                          alpha=TV_TIMESTAMP_BG_ALPHA))
        canvas.draw()
        buf = np.asarray(canvas.buffer_rgba()).copy()
        a = buf[:, :, 3]
        ys, xs = np.nonzero(a > 0)
        if xs.size == 0:
            return None
        x0, x1 = int(xs.min()), int(xs.max()) + 1
        y0, y1 = int(ys.min()), int(ys.max()) + 1
        return np.ascontiguousarray(buf[y0:y1, x0:x1])
    except Exception:
        return None


def _tv_curve_core(momentum: "MomentumEngine", cfg: "MomentumScoringConfig",
                   bg: Optional[Dict[str, Any]],
                   bg_kind: str = "half") -> Optional[Dict[str, Any]]:
    """versiontext 10text24 — text «shared» textortext text TV (without text matplotlib).
    text draw_tv_momentum (path text/render PNG) and text scene-builder render text GPU
    from «text» untiltext istext text‌text until texttotal text in text textand path textand‌to‌textand text
    withtext (text user: change texttotal chart textmenutext — only render text with AA real).
    output: dict text text text + coordinates text (bx/by) + text‌text textregister/text +
    textortext textandor + threshold‌text intext or None when text‌pitchtext in text is not."""
    if bg is None:
        return None
    arr, geom = bg["arr"], bg["geom"]
    H, W = bg["H"], bg["W"]
    l, r, t, b = geom["rect"]
    zero_y = geom["zero_y"]
    rect_h = max(1.0, float(b - t))

    # --- snapshot technical note ---
    with momentum._lock:
        hist = list(momentum.history)
        markers = [dict(m) for m in momentum.hook_goal_markers]
        # versiontechnical note 10technical note27 — technical note red card (getattr: technical notefromtechnical note with technical noteandtechnical noteandtechnical note technical noteto)
        rc_markers = [dict(m) for m in
                      (getattr(momentum, "red_card_markers", None) or [])]

    # --- versiontechnical note 10technical note16 — technical noteortechnical note technical noteandtechnical note «technical noteandor» — default: technical note (±150) ---
    axis_scale = float(TV_SCALE_MIN)
    bx = by = None
    pos_segs = neg_segs = None
    near_px = far_px = None
    bands = []

    if len(hist) >= 2:
        # versiontechnical note 10technical note9 — untiltechnical note‌technical note restart-aware: minute‌technical note + withtechnical note «minute‌technical note shared»
        minutes_all, bands, band_of = _tv_timeline(hist)
        step = max(1, len(hist) // 3000)
        idxs = list(range(0, len(hist), step))
        if idxs[-1] != len(hist) - 1:
            idxs.append(len(hist) - 1)
        smin, sval, sgame, sband = [], [], [], []
        for i in idxs:
            m = minutes_all[i]
            if m != m:
                continue               # watchdog NaN — technical note
            smin.append(float(m))
            try:
                sgame.append(float(hist[i].get("game_time", 0.0)))
            except (TypeError, ValueError):
                sgame.append(0.0)
            sval.append(float(hist[i]["net"]))   # versiontechnical note 10technical note15 — value technical note
            _bi = band_of[i]
            sband.append(bands[_bi] if 0 <= _bi < len(bands) else None)

        if len(smin) >= 2:
            # --- versiontechnical note 10technical note16 — technical noteortechnical note technical noteandtechnical note «technical noteandor» (technical note user — technical note 1) ---
            soft = max(1.0, float(getattr(cfg, "DISPLAY_SOFT_SCALE", 120.0)))
            vals = np.asarray(
                [TV_Y_RANGE * math.tanh(float(v) / soft) for v in sval],
                dtype=float)
            mins = np.asarray(smin, dtype=float)

            # --- technical noteandtechnical notefromtechnical note technical noteandtechnical note displaytechnical note (technical note‌technical note from chart original — technical noteandistechnical note user) ---
            gt_arr = np.asarray(sgame, dtype=float)
            dts = np.diff(gt_arr)
            dts = dts[dts > 0]
            eff_dt = float(np.median(dts)) if len(dts) else \
                float(getattr(cfg, "HISTORY_SAMPLE_INTERVAL", 1.0))
            sigma_samples = TV_SMOOTH_SIGMA_SEC / max(0.02, eff_dt)
            sm = np.asarray(_gauss_smooth_impl(vals.tolist(), sigma_samples),
                            dtype=float)

            # --- versiontechnical note 10technical note16 — technical notetotechnical note technical noteortechnical note technical noteandor ---
            data_peak = float(np.max(np.abs(vals))) if vals.size else 0.0
            axis_scale = max(float(TV_SCALE_MIN),
                             data_peak + float(TV_SCALE_MARGIN))

            px = np.asarray([tv_minute_to_x(bg_kind, geom, m, bnd)
                             for m, bnd in zip(mins, sband)], dtype=float)
            span = np.where(sm >= 0, zero_y - t, b - zero_y)
            py = zero_y - (sm / axis_scale) * span

            # --- versiontechnical note 10technical note25 — «technical note technical noteandtechnical note from technical note»: technical note technical noteandtechnical note
            # technical noteandtechnical note (σ=35second ≈ 18technical note6px) from before in technical noteortechnical note technical note technical note istechnical note
            # direct technical noteandtechnical note technical note technical note 0technical note5px withtechnical notesample technical note‌technical noteandtechnical note — without technical noteandtechnical note from
            # binningtechnical note 1technical note5px (technical note technical note technical noteandtechnical note = technical note technical note). inandtechnical note‌ortechnical note
            # linetechnical note technical note sample‌technical note original = same technical note‌technical note beforetechnical note only with x technical noteandtechnical note
            # after technical noteandtechnical note technical noteandtechnical note (0technical note8px) only for technical notetotechnical note technical note — peak/valley and
            # technical notetotal totaltechnical note (andtechnical note‌technical note ≥ ~18px) unchanged technical note‌technical note.
            bx, by = _tv_uniform_resample_c1(px, py, TV_CURVE_GRID_STEP_PX)
            by = _tv_micro_edge_smooth(by, TV_EDGE_MICRO_SIGMA_PX,
                                       TV_CURVE_GRID_STEP_PX)
            # --- versiontechnical note 10technical note17 — totaltechnical note smooth (only when user number data withtechnical note) ---
            if TV_EDGE_SMOOTH_PX > 0.0:
                by = _tv_extra_edge_smooth(
                    by,
                    TV_EDGE_SMOOTH_PX / max(0.2, float(TV_CURVE_GRID_STEP_PX)),
                    max_shift=TV_EDGE_SMOOTH_MAX_SHIFT_PX
                    / max(0.2, float(TV_CURVE_GRID_STEP_PX)))

            if len(bx) >= 2:
                pos_segs, neg_segs = _tv_split_sign_segments(bx, by, zero_y)
                # versiontechnical note 10technical note16 — thresholdtechnical note technical note technical note technical note technical note «andtechnical note height chart»
                span_ref = 0.5 * (float(zero_y - t) + float(b - zero_y))
                near_px = (TV_GLOW_ZERO_NEAR_VAL / axis_scale) * span_ref
                far_px = (TV_GLOW_ZERO_FAR_VAL / axis_scale) * span_ref

    return {"arr": arr, "geom": geom, "W": W, "H": H,
            "l": l, "r": r, "t": t, "b": b,
            "zero_y": zero_y, "rect_h": rect_h,
            "hist": hist, "markers": markers, "bands": bands,
            "rc_markers": rc_markers,
            "axis_scale": float(axis_scale),
            "bx": bx, "by": by,
            "pos_segs": pos_segs, "neg_segs": neg_segs,
            "near_px": near_px, "far_px": far_px}


def draw_tv_momentum(ax, momentum: "MomentumEngine", cfg: "MomentumScoringConfig",
                     disp_value, bg_kind: str,
                     home_color: str = '#e63946', away_color: str = '#f5f5f5',
                     home_flag_arr=None, away_flag_arr=None,
                     transparent_bg: bool = False,
                     timestamp_text: Optional[str] = None) -> Dict[str, Any]:
    """
    render complete text TV textandtext ax (text‌textandtext) — versiontext 10text9:
      * textandtext X calibrated with text‌text textandtext textandtext (HT=45′ text FT=90′ text ET=105′) —
        textandtext text text «minutetext text text» istext textandtext‌text text = calibrated again
        automatic and text exactly from line HT resume text‌ortext
      * «minute‌text shared» (45-50/90-97): firsttext text = extra timetext section beforetext →
        before from line boundary text text‌textandtext with restart untiltext text from textandtext boundary
      * ratio text textandtext text text‌textandtext (aspect equal — text text text)
      * textandtext Y ‎-150..+150‎ (without number) — text = line text textandtext
      * intext textandtext smooth (textandtext textandtext) text fill + line texttotext textfromtext textandtext
      * line text: from ball until line text — «textandtext» filltext with intext text smooth and without
        textandtext from line text
      * lineandtext textandtext HT/FT/ET (text internal) textandtext fill withtext text‌textandtext
      * logo: text to textside colortext + istextandtext textfromtext — inside text text without
        to‌text‌text ratio text
    versiontext 10text11:
      * transparent_bg=True → text‌pitchtext Figure/textandtext text text‌text (text
        text textandtext original text text‌textandtext) — for output PNG textagetext‌text text must
        textandtext textandtext withtext text and withtext from text text textandtext
      * timestamp_text → untiltext/text start withtext (from text text) in textandtext
        withtext text (text) with text text‌text text textandtext text‌textandtext.
    """
    info = {"fills": 0, "glow": 0, "goal_lines": 0, "balls": 0,
            "flags": 0, "zero_line": 0, "vlines": 0, "texts": 0,
            "bg": None, "px": 0, "bins": 0, "marker_glows": 0,
            "rc_lines": 0, "rc_cards": 0,
            "axis_scale": float(TV_SCALE_MIN)}

    bg = tv_load_background(bg_kind)
    ax.clear()
    # versiontechnical note 10technical note11 — transparent_bg: output technical noteagetechnical note‌technical note (technical note technical note technical note technical note‌technical noteandtechnical note)
    # currentlytechnical note technical note: technical note‌pitchtechnical note technical note technical note (technical note «technical note» technical note‌technical note — versiontechnical note 10technical note10)
    ax.set_facecolor("none" if transparent_bg else "#000000")
    fig = getattr(ax, "figure", None)
    if fig is not None:
        fig.patch.set_facecolor("none" if transparent_bg else "#000000")
        fig.patch.set_alpha(0.0 if transparent_bg else 1.0)
    if bg is None:
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        return info

    arr, geom = bg["arr"], bg["geom"]
    H, W = bg["H"], bg["W"]
    l, r, t, b = geom["rect"]
    zero_y = geom["zero_y"]
    rect_h = max(1.0, float(b - t))

    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)              # technical noteandtechnical note Y technical noteand to below = coordinates technical note technical note
    ax.set_position([0, 0, 1, 1])
    # versiontechnical note 10technical note9 — ratio technical note technical noteandtechnical note technical note technical note‌technical noteandtechnical note: withtechnical note technical noteandtechnical note inside technical notein with
    # ratio technical note technical noteandtechnical note technical noteandtechnical note technical note technical note‌technical note (letterbox) — technical note technical note from technical note technical note
    # technical note technical note technical noteandtechnical note technical noteandtechnical note technical note‌pitchtechnical note technical note technical note technical note technical note‌technical noteandtechnical note.
    ax.set_aspect("equal", adjustable="box")
    ax.set_anchor("C")
    ax.axis("off")

    ax.imshow(arr, extent=(0, W, H, 0), interpolation="bilinear",
              zorder=0)
    info["bg"] = bg_kind

    # --- versiontechnical note 10technical note11 — untiltechnical note/technical note start withtechnical note: technical noteandtechnical note withtechnical note technical note (technical note) ---
    # tex withtechnical note technical note ~42px technical noteandtechnical note technical note technical note technical note with technical note technical note‌technical note technical note
    # technical noteandtechnical note technical note‌technical noteandtechnical note until technical noteandtechnical note technical note technical note‌pitchtechnical note‌technical note from withtechnical note technical noteandtechnical note technical note.
    if timestamp_text:
        try:
            ax.text(W * 0.5, TV_TIMESTAMP_Y, str(timestamp_text),
                    ha="center", va="center", color="#f5f5f5",
                    fontsize=TV_TIMESTAMP_FONT_PT, fontweight="bold",
                    family="DejaVu Sans", zorder=20,
                    bbox=dict(boxstyle="round,pad=0.35",
                              facecolor="#000000",
                              edgecolor="none",
                              alpha=TV_TIMESTAMP_BG_ALPHA))
        except Exception as ex:
            clog(f"[TVStamp] {type(ex).__name__}: {ex}")

    # path technical note to technical note chart — fill/technical noteand/line technical note never outside technical note
    from matplotlib.patches import Rectangle as _Rect
    clip = _Rect((l, t), (r - l), (b - t), transform=ax.transData)
    clip.set_visible(False)
    ax.add_patch(clip)

    # --- versiontechnical note 10technical note24 — technical note shared technical noteortechnical note technical note (snapshot technical note inside coretechnical note
    # same technical noteandtechnical note and same order — output technical noteand‌to‌technical noteand technical note before) ---
    core = _tv_curve_core(momentum, cfg, bg, bg_kind)
    markers = core["markers"]
    bands = core["bands"]          # versiontechnical note 10technical note24 — withtechnical note minute‌technical note shared
    rc_markers = core.get("rc_markers") or []   # versiontechnical note 10technical note27 — red card
    axis_scale = core["axis_scale"]
    info["axis_scale"] = float(axis_scale)

    bx, by = core["bx"], core["by"]
    if core["pos_segs"] is not None:
        pos_segs, neg_segs = core["pos_segs"], core["neg_segs"]

        # --- intechnical note technical noteandtechnical note smooth (technical note fill) ---
        # versiontechnical note 10technical note16 — thresholdtechnical note technical note technical note technical note technical note «andtechnical note height chart»
        # (technical note‌technical note from 18 andtechnical note → without intechnical note technical noteandtechnical note from 42 → complete)
        # until with technical noteortechnical note technical noteandor technical note technical note andtechnical note chart andtechnical note technical note technical noteandtechnical note.
        info["glow"] = _tv_draw_glow(ax, pos_segs, neg_segs, W, H,
                                     clip, home_color, away_color,
                                     rect_h, float(zero_y),
                                     near_px=core["near_px"],
                                     far_px=core["far_px"])

        # --- fill technical noteand team (color technical noteandtechnical note — without istechnical noteandtechnical note technical note) ---
        where_pos = by <= zero_y
        where_neg = by > zero_y
        f1 = ax.fill_between(bx, by, zero_y, where=where_pos,
                             interpolate=True, color=home_color,
                             alpha=TV_FILL_ALPHA_HOME,
                             linewidth=0.0, zorder=3)
        f1.set_clip_path(clip)
        f2 = ax.fill_between(bx, by, zero_y, where=where_neg,
                             interpolate=True, color=away_color,
                             alpha=TV_FILL_ALPHA_AWAY,
                             linewidth=0.0, zorder=3)
        f2.set_clip_path(clip)
        info["fills"] += 2
        info["px"] = int(len(bx))
        info["bins"] = int(len(bx))
        # --- versiontechnical note 10technical note26 — technical note technical notetotechnical note technical note (feather) — technical note technical note user ---
        # istechnical noteandtechnical note technical note‌colortechnical note technical note‌technical note technical noteandtechnical note boundary filltechnical note technical note technical note technical note technical note and technical note
        # technical note‌technical note (technical note‌technical note technical note in technical noteandtechnical note smooth technical note technical note‌technical noteandtechnical note). unchanged technical notetotal.
        try:
            _fw = float(os.environ.get("TV_EDGE_FEATHER_LW",
                                       TV_EDGE_FEATHER_LW_PX) or 0.0)
        except Exception:
            _fw = float(TV_EDGE_FEATHER_LW_PX)
        try:
            _fa = float(os.environ.get("TV_EDGE_FEATHER_ALPHA",
                                       TV_EDGE_FEATHER_ALPHA) or 0.0)
        except Exception:
            _fa = float(TV_EDGE_FEATHER_ALPHA)
        if _fw > 0.05 and _fa > 0.01:
            _feather_kinds = (
                ((pos_segs or []), home_color, "pos"),
                ((neg_segs or []), away_color, "neg"),
            )
            _n_feather = 0
            for _segs, _col, _tag in _feather_kinds:
                for _si, (_xs, _ys) in enumerate(_segs):
                    if _xs is None or len(_xs) < 2:
                        continue
                    _ln = ax.plot(_xs, _ys, color=_col, alpha=_fa,
                                  linewidth=_fw, zorder=3.4,
                                  solid_joinstyle="round",
                                  solid_capstyle="round")[0]
                    _ln.set_clip_path(clip)
                    _ln.set_gid(f"tv_edge_feather_{_tag}_{_si}")
                    _n_feather += 1
            info["edge_feathers"] = _n_feather
        # (versiontechnical note 10technical note10 — line technical notetotechnical note colortechnical note technical note technical note: technical noteand line technical note technical note line technical note
        #  to color Home/Away technical note user technical note rim technical notetotechnical note fill technical noteandtechnical note)

    # --- line technical note + lineandtechnical note technical noteandtechnical note HT/FT/ET — «never technical noteand technical note‌technical noteandtechnical note» (technical noteandtechnical note fill) ---
    zlw = max(2.0, TV_ZERO_LINE_LW_FRAC * rect_h)
    zl = ax.plot([l, r], [zero_y, zero_y], color="#f2f2f2",
                 linewidth=zlw, alpha=1.0, zorder=6,
                 solid_capstyle="butt")[0]
    zl.set_clip_path(clip)
    info["zero_line"] = 1
    vlw = max(2.0, TV_VLINE_LW_FRAC * rect_h)
    for vx in _tv_internal_verticals(bg_kind, geom):
        vl = ax.plot([vx, vx], [t, b], color="#e8e8e8",
                     linewidth=vlw, alpha=1.0, zorder=6,
                     solid_capstyle="butt")[0]
        vl.set_clip_path(clip)
        info["vlines"] += 1

    # --- technical note technical note: line technical noteandtechnical note from ball «until line technical note» (technical noteandtechnical note fill — without technical noteandtechnical note from technical note) ---
    ball_d = TV_BALL_FRAC * rect_h
    ball_r = ball_d / 2.0
    # versiontechnical note 10technical note16 — height ball = «technical noteortechnical note − 30» (technical note new user — technical note 2):
    # technical note ball‌technical note in «technical note height» shared technical note‌technical note and if technical noteortechnical note technical noteandor aftertechnical note
    # technical note‌technical note technical noteandtechnical note ball‌technical note technical note with technical note 30 andtechnical note below‌technical note from technical note new technical note‌technical noteandtechnical note.
    # with technical noteortechnical note technical note 150 → ball technical noteandtechnical note ±120 (technical noteuntiltechnical note versiontechnical note 10technical note15 technical note technical note‌technical noteandtechnical note).
    ball_val = float(axis_scale) - float(TV_BALL_GAP)
    ball_home_y = zero_y - (ball_val / axis_scale) * (zero_y - t)
    ball_away_y = zero_y + (ball_val / axis_scale) * (b - zero_y)
    core_lw = max(2.0, TV_GLINE_FRAC * rect_h)
    shell_lw = max(3.0, TV_GLINE_SHELL_FRAC * rect_h)
    _ball_icon_ref = load_ball_icon()

    for gi, mk in enumerate(markers):
        mmin = tv_marker_minute(mk)
        if mmin is None:
            continue
        # versiontechnical note 10technical note9 — technical note inside «extra time‌technical note section before» (technical note 45+2 technical note first)
        # before from line boundary technical note technical note‌technical noteandtechnical note technical note after from restart untiltechnical note technical note technical note
        # (technical note technical note first/second minute‌technical note shared with disp_time technical note technical note‌technical noteandtechnical note)
        _mk_band = tv_band_for_time(bands, mk.get("game_time", None),
                                    mk.get("disp_time", None))
        gx = tv_minute_to_x(bg_kind, geom, mmin, _mk_band)
        team = str(mk.get("team", "Home"))
        if team == "Home":
            byc = ball_home_y                     # height ‎+120‎ — withtechnical note technical note
            y0, y1 = byc + ball_r * 0.9, float(zero_y)   # until line technical note — technical note technical note
        else:
            byc = ball_away_y                     # height ‎−120‎ — technical note technical note
            y0, y1 = byc - ball_r * 0.9, float(zero_y)
        if abs(y1 - y0) < 2.0:
            y1 = y0 + (2.0 if team == "Home" else -2.0)
        # --- versiontechnical note 10technical note9 — intechnical note technical note smooth technical noteandtechnical note line + ball (technical note line technical note) ---
        info["marker_glows"] += _tv_draw_marker_glow(
            ax, gx, y0, y1, float(byc), ball_r, clip, rect_h,
            f"tv_goal_glow_{gi}")
        sh = ax.plot([gx, gx], [y0, y1], color="#10151f", linewidth=shell_lw,
                     alpha=0.9, zorder=8, solid_capstyle="butt")[0]
        sh.set_clip_path(clip)
        co = ax.plot([gx, gx], [y0, y1], color="#ffffff", linewidth=core_lw,
                     alpha=1.0, zorder=9, solid_capstyle="butt")[0]
        co.set_clip_path(clip)
        sh.set_gid(f"tv_goal_line_{gi}_shell")
        co.set_gid(f"tv_goal_line_{gi}_core")
        info["goal_lines"] += 1

        invisible = ax.plot([gx], [byc], marker="o", markersize=2,
                            markerfacecolor="none", markeredgecolor="none",
                            alpha=0.0, linestyle="None", zorder=10)[0]
        invisible.set_gid(f"tv_goal_ball_{gi}")
        if _ball_icon_ref is not None:
            # versiontechnical note 10technical note8 — imshow with extent data‌technical note: technical note ball exactly ball_d
            # technical note technical noteandtechnical note original (independent from dpi/technical note/technical noteandtechnical note — technical note technical noteandtechnical note sample)
            _hd = ball_d / 2.0
            _img = ax.imshow(_ball_icon_ref,
                             extent=(gx - _hd, gx + _hd,
                                     byc + _hd, byc - _hd),   # versiontechnical note Y technical noteandtechnical note — technical note 0 = withtechnical note
                             zorder=11, interpolation="bilinear")
            _img.set_clip_path(clip)
            _img.set_gid(f"tv_goal_ballimg_{gi}")
        else:
            fb = ax.plot([gx], [byc], marker="o", markersize=ball_d * 0.55,
                         markerfacecolor="#ffffff", markeredgecolor="#10151f",
                         markeredgewidth=max(1.5, shell_lw * 0.5),
                         linestyle="None", zorder=11)[0]
            fb.set_clip_path(clip)
            fb.set_gid(f"tv_goal_ballimg_{gi}")
        info["balls"] += 1

    # --- versiontechnical note 10technical note27 — technical note red card: technical note technical note only icon card to‌technical note ball ---
    # (technical notefromtechnical note‌technical note from technical noteandtechnical note sampletechnical note user: width ≈ 0.66×technical note balltechnical note height ≈ 1.05×)
    rc_w = TV_RC_W_FRAC * rect_h
    rc_h = TV_RC_H_FRAC * rect_h
    _rc_icon_ref = build_red_card_icon()
    for ci, mk in enumerate(rc_markers):
        mmin = tv_marker_minute(mk)
        if mmin is None:
            continue
        _mk_band = tv_band_for_time(bands, mk.get("game_time", None),
                                    mk.get("disp_time", None))
        gx = tv_minute_to_x(bg_kind, geom, mmin, _mk_band)
        team = str(mk.get("team", "Home"))
        cyc = ball_home_y if team == "Home" else ball_away_y
        # line from technical notetotechnical note card until line technical note — technical note technical note: without technical noteandtechnical note from technical note
        if team == "Home":
            y0, y1 = cyc + rc_h * 0.45, float(zero_y)
        else:
            y0, y1 = cyc - rc_h * 0.45, float(zero_y)
        if abs(y1 - y0) < 2.0:
            y1 = y0 + (2.0 if team == "Home" else -2.0)
        info["marker_glows"] += _tv_draw_marker_glow(
            ax, gx, y0, y1, float(cyc), rc_h / 2.0, clip, rect_h,
            f"tv_rc_glow_{ci}")
        rsh = ax.plot([gx, gx], [y0, y1], color="#10151f",
                      linewidth=shell_lw, alpha=0.9, zorder=8,
                      solid_capstyle="butt")[0]
        rsh.set_clip_path(clip)
        rco = ax.plot([gx, gx], [y0, y1], color="#ffffff",
                      linewidth=core_lw, alpha=1.0, zorder=9,
                      solid_capstyle="butt")[0]
        rco.set_clip_path(clip)
        rsh.set_gid(f"tv_rc_line_{ci}_shell")
        rco.set_gid(f"tv_rc_line_{ci}_core")
        info["rc_lines"] += 1
        rc_anchor = ax.plot([gx], [cyc], marker="o", markersize=2,
                            markerfacecolor="none", markeredgecolor="none",
                            alpha=0.0, linestyle="None", zorder=10)[0]
        rc_anchor.set_gid(f"tv_rc_card_{ci}")
        if _rc_icon_ref is not None:
            _img = ax.imshow(_rc_icon_ref,
                             extent=(gx - rc_w / 2.0, gx + rc_w / 2.0,
                                     cyc + rc_h / 2.0, cyc - rc_h / 2.0),
                             zorder=11, interpolation="bilinear")
            _img.set_clip_path(clip)
            _img.set_gid(f"tv_rc_cardimg_{ci}")
        else:
            rfb = ax.plot([gx], [cyc], marker="s", markersize=rc_w * 0.7,
                          markerfacecolor="#F00212",
                          markeredgecolor="#10151f",
                          markeredgewidth=max(1.5, shell_lw * 0.5),
                          linestyle="None", zorder=11)[0]
            rfb.set_clip_path(clip)
            rfb.set_gid(f"tv_rc_cardimg_{ci}")
        info["rc_cards"] += 1

    # --- logo/technical note: technical note technical note technical note — Home withtechnical note / Away below ---
    # (versiontechnical note 10technical note9 — imshow with extent data‌technical note: «technical note‌technical note technical note» exactly
    #  TV_FLAG_TARGET_W technical note technical noteandtechnical note original and width/height completetechnical note technical note with
    #  technical note technical noteandtechnical note — ratio technical note never to technical note technical note‌technical note technical note sample)
    for side, farr, cy_frac in (("home", home_flag_arr, TV_FLAG_HOME_CY_FRAC),
                                ("away", away_flag_arr, TV_FLAG_AWAY_CY_FRAC)):
        if farr is None:
            continue
        try:
            fh, fw = farr.shape[:2]
            _sc = float(TV_FLAG_TARGET_W) / float(max(1, max(fh, fw)))
            w_data = float(fw) * _sc
            h_data = float(fh) * _sc
            cxp = l * TV_FLAG_CX_FRAC
            cyp = t + cy_frac * rect_h
            _img = ax.imshow(farr,
                             extent=(cxp - w_data / 2.0, cxp + w_data / 2.0,
                                     cyp + h_data / 2.0, cyp - h_data / 2.0),
                             zorder=12, interpolation="bilinear")
            _img.set_gid(f"tv_flag_{side}")
            info["flags"] += 1
        except Exception as ex:
            clog(f"[TVFlag] render logo {side} failed: {ex}")

    info["texts"] = len(getattr(ax, "texts", []))
    return info


# =====================================================================
# 25-technical note — technical noteagetechnical note‌technical note chart TV technical noteandtechnical note technical note withtechnical note (versiontechnical note 10technical note11 — request user)
# ---------------------------------------------------------------------
# cycletechnical note complete:
#   minutetechnical note technical note − 1  →  render technical note chart TV with technical note‌pitchtechnical note technical note (technical note technical note
#                     technical noteandtechnical note original technical note technical note‌technical noteandtechnical note) → PNG technical noteandtechnical note in tv_snapshot_tmp
#   minutetechnical note technical note      →  display technical noteandtechnical note technical note user (below-technical note) to technical note technical note‌technical note
#                     (default 20 secondtechnical note real) — exactly same technical notetotaltechnical note technical note technical note‌technical note
#   match end      →  stop ≥12 second in time >90′ and >120′ → display latest chart
#   reset untiltechnical note to 00:00 (technical note new) → «savetechnical note technical note» latest chart withtechnical note beforetechnical note
#                     in Momentum_Saves with technical note technical noteandtechnical note technical noteandtechnical note
# technical note (technical note‌technical note technical note TV): in tv_snapshot_settings.json technical note technical note
# save technical note‌technical noteandtechnical note and in technical note aftertechnical note automatic recovery technical note‌technical noteandtechnical note.
# =====================================================================
TV_SNAP_TMP_DIRNAME = "tv_snapshot_tmp"            # PNG technical noteandtechnical note technical noteagetechnical note‌technical note‌technical note
TV_SNAP_SAVE_DIRNAME = "Momentum_Saves"            # savetechnical note technical note latest charttechnical note
TV_SNAP_SETTINGS_FILENAME = "tv_snapshot_settings.json"

TV_SNAP_KEYS = ("h1", "h2", "et")
# withtechnical note technical notefrom technical note minute for technical note section (request technical note user)
TV_SNAP_RANGES = {"h1": (38, 44), "h2": (80, 89), "et": (110, 119)}
TV_SNAP_DEFAULT_MINUTE = {"h1": 43, "h2": 85, "et": 116}   # «default»

TV_SNAP_DEFAULTS = {
    "h1_enabled": True,  "h1_minute": 43,
    "h2_enabled": True,  "h2_minute": 85,
    "et_enabled": True,  "et_minute": 116,
    "show_seconds": 10,                  # secondtechnical note real (technical note secondtechnical note withtechnical note)
    "end_enabled": True, "end_seconds": 20,
    "permanent_save": False,
    "timestamp": False,
}

# match end: stoptechnical note technical noteandtechnical note withtechnical note technical note technical note‌technical notein second resume ortechnical note until «end»
# technical note technical noteandtechnical note (detection technical note technical note from technical noteandtechnical note endtechnical note technical note technical noteanduntiltechnical note‌technical note from technical note is)
TV_SNAP_END_STOP_CONFIRM_SEC = 12.0
TV_SNAP_END_RESHOW_COOLDOWN_SEC = 45.0
TV_SNAP_MIN_HIST_SEC = 90.0      # withtechnical note with technical note from technical note time savetechnical note technical note technical note‌technical noteandtechnical note

# --- v10.28 — cycletechnical note technical note technical note display (technical noteandtechnical note v1.3 from versiontechnical note 2017technical note technical note withtechnical note
# «chart in minutetechnical note technical note (43/85) display data technical note and only technical note from match end technical note») —
# beforetechnical note st["shown"]=True technical note with «technical noteandtechnical note» action technical note technical note‌technical note if dispatch/UI
# technical note technical note‌technical note same display for always from technical note technical note‌technical note. technical note technical note technical note only with
# confirmation (confirm) technical note from technical note Show technical note technical note‌technical noteandtechnical note and technical note/technical note‌technical note confirmation →
# technical note technical note automatic without restart withtechnical note. ---
TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC = 10.0   # technical note technical note confirmation SHOWING (wall)
TV_SNAP_SHOW_RETRY_BACKOFF_SEC = 3.0      # distancetechnical note technical note technical note technical note from technical note
TV_SNAP_SHOW_MAX_RETRIES = 6              # technical note technical note technical note technical note totaltechnical note technical noteortechnical note‌withtechnical note
TV_SNAP_END_FAIL_MAX = 3                  # technical note technical note register‌technical note technical note level end

# --- v10.29 (technical noteandtechnical note v1.2.2 from 2017) — technical note «end display technical note charttechnical note»
# (technical note withtechnical note technical note «chart minutetechnical note 116 display data technical note and technical note technical note technical note and
# for always in technical noteandtechnical note technical noteandtechnical note technical note»):
#  1) windowtechnical note technical noteandtechnical note GPU only in momenttechnical note Show real technical noteortechnical note and after from technical note
#     technical noteandtechnical note (or hide_now) in «level technical noteandtechnical note andtechnical noteandtechnical note» technical note technical note‌technical noteandtechnical note — technical note from technical note
#     technical note only to technical note frame technical note from technical note render andtechnical note is nottechnical note
#  2) technical note hide in technical noteortechnical note technical note technical note (drop) technical note‌technical noteandtechnical note
#  3) watchdog technical note display in UI after from (technical note technical note‌technical note + technical note + technical note
#     technical note) hidden‌technical notefromtechnical note technical notewithtechnical note idempotent technical note technical note‌technical note. ---
TV_SNAP_OVERDUE_GRACE_SEC = 8.0        # technical note technical note watchdog technical note display (wall)

# --- v10.28 — log always-technical note «technical note display technical noteagetechnical note‌technical note» (technical note mlog versiontechnical note 2017):
# file technical noteandtechnical note momentum_2026_snapshot.log technical note technical note — only technical note line to
# fromtechnical note technical note display (REQUESTED/QUEUED/EXECUTED/SHOWING/CONFIRMED/FAILED/...).
# technical note: in technical noteandtechnical note technical note technical noteandtechnical note technical noteandtechnical note technical note display exactly until codetechnical note technical note technical note.
# technical note print technical noteandtechnical note technical note (technical noteis v10.24 technical note technical note) and with technical note technical note technical noteandtechnical note technical note‌technical noteandtechnical note. ---
SNAP_STAGE_LOG_ENABLED = True
SNAP_STAGE_LOG_MAX_BYTES = 512 * 1024
SNAP_STAGE_LOG_FILENAME = "momentum_2026_snapshot.log"


