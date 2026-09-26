def _scene_rgba8(a) -> Optional["np.ndarray"]:
    """text textandtext (float 0..1 or uint8text RGB/RGBA) → RGBA uint8 textandtext."""
    a = np.asarray(a)
    if a.ndim == 2:
        a = np.dstack([a] * 3 + [np.ones_like(a)])
    elif a.shape[2] == 3:
        al = np.ones(a.shape[:2], dtype=a.dtype)
        a = np.dstack([a, al])
    if a.dtype != np.uint8:
        a = np.asarray(a, dtype=float)
        if a.size and float(a.max()) <= 1.0 + 1e-6:
            a = a * 255.0 + 0.5
        a = np.clip(a, 0, 255)
        a = a.astype(np.uint8)
    return np.ascontiguousarray(a)


def _scene_hex_rgb01(color) -> Tuple[float, float, float]:
    """color hex/text → (r, g, b) in 0..1 (same text matplotlib)."""
    try:
        from matplotlib import colors as _mc
        r, g, b = _mc.to_rgb(color)
        return (float(r), float(g), float(b))
    except Exception:
        return (1.0, 1.0, 1.0)


def _scene_quad_verts(rect) -> "np.ndarray":
    """textandtext for text text (2 text a_d=0). rect=(x0,y0,x1,y1) text."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    return np.array([[x0, y0, 0.0], [x0, y1, 0.0], [x1, y0, 0.0],
                     [x1, y0, 0.0], [x0, y1, 0.0], [x1, y1, 0.0]],
                    dtype=np.float32)


def _scene_fill_tri_verts(xs, ys, zero_y: float, pad: float,
                          sign: int) -> "np.ndarray":
    """versiontext 10text24 — fill text text and line text to‌textandtext text‌text GPU (text
    «Fill Area» text user): text textandtext = 2 text a_d text text = distancetext
    text‌text until «boundary real text» (outside textregister / inside text) until Fragment
    Shader texttotext fill text with smoothstep smooth text (unchanged texttotal data).
    xs/ys: output _tv_split_sign_segments (textandtext from text inandtext‌ortext‌text)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    n = len(xs)
    if n < 2:
        return np.zeros((0, 3), dtype=np.float32)
    depths = np.abs(ys - float(zero_y))
    out = -1.0 if sign > 0 else 1.0        # technical note «outside» (technical noteandtechnical note from line technical note)
    top_y = ys + out * pad
    m = n - 1
    v = np.empty((m, 6, 3), dtype=np.float32)
    v[:, 0] = np.stack([xs[:-1], top_y[:-1], np.full(m, pad)], axis=1)
    v[:, 1] = np.stack([xs[:-1], np.full(m, float(zero_y)), -depths[:-1]],
                       axis=1)
    v[:, 2] = np.stack([xs[1:], top_y[1:], np.full(m, pad)], axis=1)
    v[:, 3] = v[:, 2]
    v[:, 4] = v[:, 1]
    v[:, 5] = np.stack([xs[1:], np.full(m, float(zero_y)), -depths[1:]],
                       axis=1)
    return np.ascontiguousarray(v.reshape(-1, 3))


def _scene_vband_verts(x: float, y0: float, y1: float, half_w: float,
                       pad: float) -> "np.ndarray":
    """withtext textandtext text (line text/line textandtext) — textand text independent until distancetext text‌text
    inside text text linetext text (boundary = distancetext half_w from text)."""
    xl, xr = float(x) - (half_w + pad), float(x) + (half_w + pad)
    cx = float(x)
    left = np.array([[xl, y0, pad], [cx, y0, -half_w], [xl, y1, pad],
                     [cx, y0, -half_w], [cx, y1, -half_w], [xl, y1, pad]],
                    dtype=np.float32)
    right = np.array([[cx, y0, -half_w], [xr, y0, pad], [cx, y1, -half_w],
                      [xr, y0, pad], [xr, y1, pad], [cx, y1, -half_w]],
                     dtype=np.float32)
    return np.concatenate([left, right], axis=0)


def _scene_hband_verts(y: float, x0: float, x1: float, half_w: float,
                       pad: float) -> "np.ndarray":
    """withtext text text (line text) — textand text withtext/below text _scene_vband_verts."""
    yt, yb = float(y) - (half_w + pad), float(y) + (half_w + pad)
    cy = float(y)
    top = np.array([[x0, yt, pad], [x0, cy, -half_w], [x1, yt, pad],
                    [x0, cy, -half_w], [x1, cy, -half_w], [x1, yt, pad]],
                   dtype=np.float32)
    bot = np.array([[x0, cy, -half_w], [x0, yb, pad], [x1, cy, -half_w],
                    [x0, yb, pad], [x1, yb, pad], [x1, cy, -half_w]],
                   dtype=np.float32)
    return np.concatenate([top, bot], axis=0)


def _scene_disc_verts(cx: float, cy: float, r: float, pad: float,
                      segments: int = 24) -> "np.ndarray":
    """text (only fallback textandtext icon ball) — withtext text with boundary AA."""
    cx, cy, r = float(cx), float(cy), float(r)
    ang = np.linspace(0.0, 2.0 * math.pi, max(8, int(segments)) + 1)
    rx, ry = cx + (r + pad) * np.cos(ang), cy + (r + pad) * np.sin(ang)
    n = len(ang) - 1
    v = np.empty((n, 3, 3), dtype=np.float32)
    v[:, 0] = [cx, cy, -r]
    v[:, 1] = np.stack([rx[:-1], ry[:-1], np.full(n, pad)], axis=1)
    v[:, 2] = np.stack([rx[1:], ry[1:], np.full(n, pad)], axis=1)
    return np.ascontiguousarray(v.reshape(-1, 3))


def _gpu_fill_feather_px() -> float:
    """versiontext 10text26 — smoothing texttotext fill in path GPU (text level)text text‌text istextandtext
    feather path matplotlib until textandtext live and textagetext‌text «text text» text withtext.
    env: TV_GPU_FILL_FEATHER (0 = texttotext text beforetext)."""
    try:
        v = float(os.environ.get("TV_GPU_FILL_FEATHER",
                                 TV_GPU_FILL_FEATHER_PX) or 0.0)
    except Exception:
        v = float(TV_GPU_FILL_FEATHER_PX)
    return max(0.0, min(3.0, v))


def build_gpu_graph_scene(momentum, cfg, bg_kind: str,
                          home_color: str, away_color: str,
                          home_flag_arr=None, away_flag_arr=None,
                          timestamp_text=None,
                          screen=None) -> Optional[Dict[str, Any]]:
    """versiontext 10text24 — text «scenetext text» chart TV in text Worker (text —
    without Tk/GL/matplotlib-draw). output for GPUOverlayRenderer.upload_scene:
      items: list text text (text zorder beforetext) from textand textandtext:
        {"kind": "tex",  rgba, size, rect, clip}   — text textandtext smooth
        {"kind": "edge", verts(x,y,d), color4, clip, mode} — text text AA
      view: (dx, dy, k) | place: {dx,dy,travel} | clip: text text text
    texttotal text from _tv_curve_core text‌text — «textand‌to‌textand» same path matplotlib."""
    try:
        bg = tv_load_background(bg_kind)
        core = _tv_curve_core(momentum, cfg, bg, bg_kind)
        if core is None:
            return None
        W, H = float(core["W"]), float(core["H"])
        l, r, t, b = core["l"], core["r"], core["t"], core["b"]
        zero_y = float(core["zero_y"])
        rect_h = float(core["rect_h"])
        axis_scale = float(core["axis_scale"])
        sw, sh = (screen if screen is not None else (1920, 1080))
        x_final, y_final, w_d, h_d = snap_overlay_geometry(int(W), int(H),
                                                           int(sw), int(sh))
        surf = _gpu_surface_geo(int(sw), int(sh))
        place = _gpu_image_placement(int(sw), int(sh), x_final, y_final,
                                     surf[0], surf[1])
        k = float(w_d) / max(1.0, W)
        pad = 1.25 / max(1e-4, k)           # technical note AA ≈ 1technical note25px level
        items: List[Dict[str, Any]] = []
        n_verts = 0

        # --- 0) technical note‌pitchtechnical note technical note (zorder 0 — without technical note technical note imshow beforetechnical note) ---
        bg8 = _scene_rgba8(core["arr"])
        items.append({"kind": "tex", "rgba": bg8,
                      "size": (int(bg8.shape[1]), int(bg8.shape[0])),
                      "rect": (0.0, 0.0, W, H), "clip": False,
                      "verts": _scene_quad_verts((0.0, 0.0, W, H))})

        if core["pos_segs"] is not None:
            # --- 1) intechnical note technical noteandtechnical note (zorder 2 — technical noteortechnical note shared with path matplotlib) ---
            for rgba_f, _c in _tv_glow_layers(
                    core["pos_segs"], core["neg_segs"], core["W"], core["H"],
                    home_color, away_color, rect_h, zero_y,
                    near_px=core["near_px"], far_px=core["far_px"]):
                g8 = _scene_rgba8(rgba_f)
                items.append({"kind": "tex", "rgba": g8,
                              "size": (int(g8.shape[1]), int(g8.shape[0])),
                              "rect": (0.0, 0.0, W, H), "clip": True,
                              "verts": _scene_quad_verts((0.0, 0.0, W, H))})

            # --- 2) fill technical noteand team (zorder 3 — technical notetotechnical note AA realtechnical note technical note Fill Area) ---
            for segs, color, alpha in (
                    (core["pos_segs"], home_color, TV_FILL_ALPHA_HOME),
                    (core["neg_segs"], away_color, TV_FILL_ALPHA_AWAY)):
                if not segs:
                    continue
                chunks = []
                for (xs, ys) in segs:
                    tri = _scene_fill_tri_verts(xs, ys, zero_y, pad,
                                                +1 if ys[0] <= zero_y else -1)
                    if len(tri):
                        chunks.append(tri)
                if not chunks:
                    continue
                verts = np.concatenate(chunks, axis=0)
                cr, cg, cb = _scene_hex_rgb01(color)
                items.append({"kind": "edge", "verts": verts,
                              "color4": (cr, cg, cb, float(alpha)),
                              "feather": _gpu_fill_feather_px(),
                              "clip": True, "mode": "tris"})
                n_verts += int(len(verts))

        # --- 3) intechnical note technical note technical note (zorder 5 — before from line technical note technical note before) ---
        markers = core["markers"]
        rc_markers = core.get("rc_markers") or []   # versiontechnical note 10technical note27 — red card
        bands = core["bands"]
        ball_d = TV_BALL_FRAC * rect_h
        ball_r = ball_d / 2.0
        ball_val = float(axis_scale) - float(TV_BALL_GAP)
        ball_home_y = zero_y - (ball_val / axis_scale) * (zero_y - t)
        ball_away_y = zero_y + (ball_val / axis_scale) * (b - zero_y)
        core_lw = max(2.0, TV_GLINE_FRAC * rect_h)
        shell_lw = max(3.0, TV_GLINE_SHELL_FRAC * rect_h)
        _ball_icon_ref = load_ball_icon()
        ball8 = _scene_rgba8(_ball_icon_ref) if _ball_icon_ref is not None \
            else None
        mk_geo = []
        for gi, mk in enumerate(markers):
            mmin = tv_marker_minute(mk)
            if mmin is None:
                continue
            _mk_band = tv_band_for_time(bands, mk.get("game_time", None),
                                        mk.get("disp_time", None))
            gx = tv_minute_to_x(bg_kind, core["geom"], mmin, _mk_band)
            team = str(mk.get("team", "Home"))
            if team == "Home":
                byc = ball_home_y
                y0g, y1g = byc + ball_r * 0.9, zero_y
            else:
                byc = ball_away_y
                y0g, y1g = byc - ball_r * 0.9, zero_y
            if abs(y1g - y0g) < 2.0:
                y1g = y0g + (2.0 if team == "Home" else -2.0)
            mk_geo.append((gi, gx, y0g, y1g, byc))
            calc = _tv_marker_glow_calc(gx, y0g, y1g, byc, ball_r, rect_h)
            if calc is not None:
                m8 = _scene_rgba8(calc["rgba"])
                rect = (calc["x0"], calc["y0"], calc["x1"], calc["y1"])
                items.append({"kind": "tex", "rgba": m8,
                              "size": (int(m8.shape[1]), int(m8.shape[0])),
                              "rect": rect, "clip": True,
                              "verts": _scene_quad_verts(rect)})

        # --- 4) line technical note + lineandtechnical note technical noteandtechnical note (zorder 6 — technical note with technical notetotechnical note AA) ---
        zlw = max(2.0, TV_ZERO_LINE_LW_FRAC * rect_h)
        items.append({"kind": "edge",
                      "verts": _scene_hband_verts(zero_y, l, r, zlw / 2.0,
                                                  pad),
                      "color4": (0.949, 0.949, 0.949, 1.0),
                      "clip": True, "mode": "tris"})
        n_verts += 12
        vlw = max(2.0, TV_VLINE_LW_FRAC * rect_h)
        for vx in _tv_internal_verticals(bg_kind, core["geom"]):
            items.append({"kind": "edge",
                          "verts": _scene_vband_verts(vx, t, b, vlw / 2.0,
                                                      pad),
                          "color4": (0.910, 0.910, 0.910, 1.0),
                          "clip": True, "mode": "tris"})
            n_verts += 12

        # --- 5) line technical note (shelltechnical note technical note zorder 8 + technical note technical note zorder 9) ---
        for (gi, gx, y0g, y1g, byc) in mk_geo:
            items.append({"kind": "edge",
                          "verts": _scene_vband_verts(gx, y0g, y1g,
                                                      shell_lw / 2.0, pad),
                          "color4": (0.063, 0.082, 0.122, 0.9),
                          "clip": True, "mode": "tris"})
            items.append({"kind": "edge",
                          "verts": _scene_vband_verts(gx, y0g, y1g,
                                                      core_lw / 2.0, pad),
                          "color4": (1.0, 1.0, 1.0, 1.0),
                          "clip": True, "mode": "tris"})
            n_verts += 24
            # --- 6) icon ball (zorder 11) ---
            _hd = ball_d / 2.0
            brect = (gx - _hd, byc - _hd, gx + _hd, byc + _hd)
            if ball8 is not None:
                items.append({"kind": "tex", "rgba": ball8,
                              "size": (int(ball8.shape[1]),
                                       int(ball8.shape[0])),
                              "rect": brect, "clip": True,
                              "verts": _scene_quad_verts(brect)})
            else:
                items.append({"kind": "edge",
                              "verts": _scene_disc_verts(gx, byc,
                                                         ball_r * 0.55, pad),
                              "color4": (1.0, 1.0, 1.0, 1.0),
                              "clip": True, "mode": "fan"})
                n_verts += len(_scene_disc_verts(gx, byc, ball_r * 0.55, pad))

        # --- 6technical note5) versiontechnical note 10technical note27 — technical note red card (technical note technical note icon card to‌technical note ball) ---
        rc_w = TV_RC_W_FRAC * rect_h
        rc_h = TV_RC_H_FRAC * rect_h
        rc8 = _scene_rgba8(build_red_card_icon())
        for ci, mk in enumerate(rc_markers):
            mmin = tv_marker_minute(mk)
            if mmin is None:
                continue
            _mk_band = tv_band_for_time(bands, mk.get("game_time", None),
                                        mk.get("disp_time", None))
            gx = tv_minute_to_x(bg_kind, core["geom"], mmin, _mk_band)
            team = str(mk.get("team", "Home"))
            cyc = ball_home_y if team == "Home" else ball_away_y
            if team == "Home":
                y0g, y1g = cyc + rc_h * 0.45, zero_y
            else:
                y0g, y1g = cyc - rc_h * 0.45, zero_y
            if abs(y1g - y0g) < 2.0:
                y1g = y0g + (2.0 if team == "Home" else -2.0)
            calc = _tv_marker_glow_calc(gx, y0g, y1g, cyc,
                                        rc_h / 2.0, rect_h)
            if calc is not None:
                m8 = _scene_rgba8(calc["rgba"])
                rect = (calc["x0"], calc["y0"], calc["x1"], calc["y1"])
                items.append({"kind": "tex", "rgba": m8,
                              "size": (int(m8.shape[1]), int(m8.shape[0])),
                              "rect": rect, "clip": True,
                              "verts": _scene_quad_verts(rect)})
            items.append({"kind": "edge",
                          "verts": _scene_vband_verts(gx, y0g, y1g,
                                                      shell_lw / 2.0, pad),
                          "color4": (0.063, 0.082, 0.122, 0.9),
                          "clip": True, "mode": "tris"})
            items.append({"kind": "edge",
                          "verts": _scene_vband_verts(gx, y0g, y1g,
                                                      core_lw / 2.0, pad),
                          "color4": (1.0, 1.0, 1.0, 1.0),
                          "clip": True, "mode": "tris"})
            n_verts += 24
            # icon card (zorder 11 — aligned ball)
            _hw, _hh = rc_w / 2.0, rc_h / 2.0
            crect = (gx - _hw, cyc - _hh, gx + _hw, cyc + _hh)
            if rc8 is not None:
                items.append({"kind": "tex", "rgba": rc8,
                              "size": (int(rc8.shape[1]),
                                       int(rc8.shape[0])),
                              "rect": crect, "clip": True,
                              "verts": _scene_quad_verts(crect)})
            else:
                items.append({"kind": "edge",
                              "verts": _scene_quad_verts(crect),
                              "color4": (0.941, 0.008, 0.071, 1.0),
                              "clip": True, "mode": "tris"})
                n_verts += 6

        # --- 7) logo/technical note (zorder 12 — without technical note technical note before) ---
        for side, farr, cy_frac in (("home", home_flag_arr,
                                     TV_FLAG_HOME_CY_FRAC),
                                    ("away", away_flag_arr,
                                     TV_FLAG_AWAY_CY_FRAC)):
            if farr is None:
                continue
            try:
                fh, fw = farr.shape[:2]
                _sc = float(TV_FLAG_TARGET_W) / float(max(1, max(fh, fw)))
                w_data = float(fw) * _sc
                h_data = float(fh) * _sc
                cxp = l * TV_FLAG_CX_FRAC
                cyp = t + cy_frac * rect_h
                frect = (cxp - w_data / 2.0, cyp - h_data / 2.0,
                         cxp + w_data / 2.0, cyp + h_data / 2.0)
                f8 = _scene_rgba8(farr)
                items.append({"kind": "tex", "rgba": f8,
                              "size": (int(f8.shape[1]), int(f8.shape[0])),
                              "rect": frect, "clip": False,
                              "verts": _scene_quad_verts(frect)})
            except Exception:
                continue

        # --- 8) technical note untiltechnical note/technical note (zorder 20 — technical note‌technical note technical note technical note‌withtechnical note) ---
        if timestamp_text:
            bmp = _tv_timestamp_bitmap(timestamp_text)
            if bmp is not None:
                bw, bh = float(bmp.shape[1]), float(bmp.shape[0])
                trect = (W * 0.5 - bw / 2.0, TV_TIMESTAMP_Y - bh / 2.0,
                         W * 0.5 + bw / 2.0, TV_TIMESTAMP_Y + bh / 2.0)
                items.append({"kind": "tex", "rgba": bmp,
                              "size": (int(bw), int(bh)),
                              "rect": trect, "clip": False,
                              "verts": _scene_quad_verts(trect)})

        return {"version": 1, "mode": "vector",
                "W": int(W), "H": int(H), "k": float(k),
                "img": (int(x_final), int(y_final), int(w_d), int(h_d)),
                "surf": surf, "place": place,
                "view": (float(place["dx"]), float(place["dy"]), float(k)),
                "clip": (float(l), float(t), float(r), float(b)),
                "items": items, "n_verts": n_verts,
                "n_items": len(items)}
    except Exception:
        return None


# =====================================================================
# 25technical note7 — archive complete technical notedatatechnical note withtechnical note (versiontechnical note 10technical note24 — request user)
# ---------------------------------------------------------------------
# «technical note technical note output complete from technical notedatatechnical note withtechnical note to‌technical noteandtechnical note technical note file (or ZIP) +
#  read same file technical noteandtechnical note code and technical note technical note to chart.»
#
#   output (automatic in end technical note withtechnical note + buttontechnical note technical note):
#     Momentum_Archives/match_YYYY-MM-DD_HH-MM.zip
#       ├─ match_data.json      ← total untiltechnical note Momentum + technical note technical note +
#       │                          team‌technical note/color‌technical note/technical note/technical noteortechnical note/time‌technical note
#       ├─ flag_home.png        ← logotechnical note Home (for withtechnical notefromtechnical note technical note)
#       ├─ flag_away.png        ← logotechnical note Away
#       ├─ snapshot_final.png   ← latest render chart (if in technical note withtechnical note)
#       └─ readme.txt           ← technical note + instruction render again
#
#   input/withtechnical note:
#     render_archive_chart(path)  →  read ZIP → technical noteandtechnical noteandtechnical note technical noteto → render PNG
#     CLI:  python finalmomentum.py --render-archive <file.zip>
#     UI:   buttontechnical note «render againtechnical note chart from archive» in technical note technical noteagetechnical note‌technical note
# =====================================================================

MOMENTUM_ARCHIVE_DIRNAME = "Momentum_Archives"
MOMENTUM_ARCHIVE_FORMAT = "momentum-match-archive"
MOMENTUM_ARCHIVE_VERSION = 1


def _archive_json_safe(v):
    """text value to JSON-safe: NaN/Inf → None (read again → NaN)."""
    try:
        if isinstance(v, float):
            return v if (v == v and -1e308 < v < 1e308) else None
        if isinstance(v, dict):
            return {str(k): _archive_json_safe(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [_archive_json_safe(x) for x in v]
        if v is None or isinstance(v, (str, int, bool)):
            return v
        if isinstance(v, (np.integer,)):
            return int(v)
        if isinstance(v, (np.floating,)):
            return _archive_json_safe(float(v))
        return str(v)
    except Exception:
        return None


def collect_match_events(momentum, snap_engine=None,
                         seen_max_t: float = 0.0,
                         teams: Optional[Dict[str, Any]] = None,
                         colors: Optional[Dict[str, str]] = None,
                         bg_kind: str = "half",
                         settings: Optional[Dict[str, Any]] = None,
                         tuning: Optional[Dict[str, float]] = None,
                         display_cfg=None) -> Dict[str, Any]:
    """textagetext‌text text «text textdatatext withtext» to‌textandtext dict textfromtext with JSON.
    text data‌text text/text text‌textandtext — untiltext complete sample‌to‌sample."""
    with momentum._lock:
        hist = [dict(h) for h in momentum.history]
        markers = [dict(m) for m in momentum.hook_goal_markers]
        # versiontechnical note 10technical note27 — technical note red card (getattr: technical notefromtechnical note with technical noteandtechnical noteandtechnical note technical noteto)
        rc_markers = [dict(m) for m in
                      (getattr(momentum, "red_card_markers", None) or [])]
    start_wall = None
    if snap_engine is not None:
        start_wall = getattr(snap_engine, "match_start_wall", None)
    score = {"home": 0, "away": 0}
    for m in markers:
        team = str(m.get("team", "Home")).strip().lower()
        if team in score:
            score[team] = score.get(team, 0) + 1
    data = {
        "format": MOMENTUM_ARCHIVE_FORMAT,
        "version": MOMENTUM_ARCHIVE_VERSION,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "app_hint": "FL_2026 Live Match Momentum — finalmomentum.py",
        "match": {
            "start_wall": (float(start_wall)
                           if start_wall is not None else None),
            "start_text": (time.strftime("%Y-%m-%d %H:%M",
                                         time.localtime(start_wall))
                           if start_wall else None),
            "seen_max_t": float(seen_max_t or 0.0),
        },
        "teams": _archive_json_safe(teams or {}),
        "score": score,
        "display": {
            "bg_kind": str(bg_kind or "half"),
            "colors": _archive_json_safe(colors or {}),
            "timestamp_enabled": bool((settings or {}).get("timestamp")),
            "tuning": _archive_json_safe(tuning or {}),
        },
        "engine": {
            "display_soft_scale": float(getattr(display_cfg,
                                                "DISPLAY_SOFT_SCALE", 120.0)),
            "history_sample_interval": float(getattr(
                display_cfg, "HISTORY_SAMPLE_INTERVAL", 1.0)),
        },
        "settings": _archive_json_safe(settings or {}),
        "history": _archive_json_safe(hist),
        "goal_markers": _archive_json_safe(markers),
        "red_card_markers": _archive_json_safe(rc_markers),
        "counts": {"history": len(hist), "goal_markers": len(markers),
                   "red_card_markers": len(rc_markers)},
    }
    return data


def write_match_archive_zip(out_path: str, match_data: Dict[str, Any],
                            extra_files: Optional[Dict[str, bytes]] = None,
                            readme_text: str = "") -> Optional[str]:
    """write ZIP archive (match_data.json + file‌text text). output: path or None."""
    try:
        import zipfile
        d = os.path.dirname(os.path.abspath(out_path))
        if d:
            os.makedirs(d, exist_ok=True)
        n = 2
        base = out_path
        while os.path.exists(base):
            root, ext = os.path.splitext(out_path)
            base = f"{root}_{n}{ext or '.zip'}"
            n += 1
        out_path = base
        with zipfile.ZipFile(out_path, "w",
                             compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("match_data.json",
                        json.dumps(_archive_json_safe(match_data),
                                   ensure_ascii=False, indent=1))
            if readme_text:
                zf.writestr("readme.txt", readme_text)
            for name, blob in (extra_files or {}).items():
                if blob:
                    zf.writestr(name, blob)
        return out_path
    except Exception:
        return None


def export_match_archive(momentum, snap_engine=None,
                         seen_max_t: float = 0.0,
                         teams: Optional[Dict[str, Any]] = None,
                         colors: Optional[Dict[str, str]] = None,
                         bg_kind: str = "half",
                         settings: Optional[Dict[str, Any]] = None,
                         tuning: Optional[Dict[str, float]] = None,
                         display_cfg=None,
                         flag_images: Optional[Dict[str, Any]] = None,
                         snapshot_img=None,
                         out_dir: Optional[str] = None) -> Optional[str]:
    """output complete textdatatext withtext → ZIP in Momentum_Archives (or out_dir).
    flag_images: {"home": arr, "away": arr} — text float/uint8 PNG-text.
    snapshot_img: PIL.Image latest render (optional). output: path ZIP or None."""
    try:
        data = collect_match_events(
            momentum, snap_engine=snap_engine, seen_max_t=seen_max_t,
            teams=teams, colors=colors, bg_kind=bg_kind, settings=settings,
            tuning=tuning, display_cfg=display_cfg)
        extra: Dict[str, bytes] = {}
        try:
            if Image is not None and flag_images:
                for side in ("home", "away"):
                    arr = flag_images.get(side)
                    if arr is None:
                        continue
                    a = np.asarray(arr)
                    if a.dtype != np.uint8:
                        a = np.clip(a * (255.0 if float(a.max()) <= 1.0 + 1e-6
                                         else 1.0) + 0.5, 0, 255)
                    a = a.astype(np.uint8)
                    buf = io_bytes_image(a)
                    if buf:
                        extra[f"flag_{side}.png"] = buf
        except Exception:
            pass
        try:
            if snapshot_img is not None and Image is not None:
                from io import BytesIO as _BIO
                b = _BIO()
                snapshot_img.save(b, format="PNG")
                extra["snapshot_final.png"] = b.getvalue()
        except Exception:
            pass
        stamp = (data.get("match", {}) or {}).get("start_text")
        stamp = stamp.replace(":", "-") if stamp else \
            time.strftime("%Y-%m-%d_%H-%M")
        th = (teams or {}).get("home") or {}
        ta = (teams or {}).get("away") or {}
        nh = th.get("label") or "Home"
        na = ta.get("label") or "Away"
        base = f"match_{stamp}_{nh}_vs_{na}".replace(" ", "_")
        readme = (
            "FL_2026 — Live Match Momentum — archive complete textdatatext withtext\n"
            "=========================================================\n\n"
            "match_data.json   : total untiltext Momentum (sample‌to‌sample) + text‌text\n"
            "                    + team‌text/color‌text/text — source text.\n"
            "flag_home/away.png: logotext team‌text (for withtextfromtext text chart).\n"
            "snapshot_final.png: latest render chart in momenttext archive (optional).\n\n"
            "render againtext chart from text file:\n"
            "  python finalmomentum.py --render-archive <text file>.zip\n"
            "or from inside text: ⚙ text textagetext‌text ← «render againtext chart from\n"
            "archive». file JSON istext istext tooltext text text text text‌textandtext\n"
            "direct textandtext (nan = gap text/stop).\n")
        out_dir = out_dir or os.path.join(
            os.path.dirname(os.path.abspath(
                __file__ if "__file__" in globals() else os.getcwd())),
            MOMENTUM_ARCHIVE_DIRNAME)
        return write_match_archive_zip(
            os.path.join(out_dir, base + ".zip"), data, extra_files=extra,
            readme_text=readme)
    except Exception:
        return None


def io_bytes_image(arr_uint8) -> Optional[bytes]:
    """text uint8 (H,W,3|4) → byte‌text PNG (for textfromtext in ZIP)."""
    try:
        if Image is None or arr_uint8 is None:
            return None
        from io import BytesIO as _BIO
        a = np.asarray(arr_uint8)
        im = Image.fromarray(a)
        b = _BIO()
        im.save(b, format="PNG")
        return b.getvalue()
    except Exception:
        return None


class _ArchiveCurveCfg:
    """cfg text for render again from archive (only textand text text in texttotal)."""

    def __init__(self, data: Dict[str, Any]):
        eng = (data or {}).get("engine", {}) or {}
        self.DISPLAY_SOFT_SCALE = float(eng.get("display_soft_scale", 120.0))
        self.HISTORY_SAMPLE_INTERVAL = float(
            eng.get("history_sample_interval", 1.0))


class _ArchiveEngine:
    """textandtextandtext textto for render_tv_snapshot from datatext archive — same text textandtext text
    path text text‌textandtext: history / hook_goal_markers / _lock."""

    def __init__(self, data: Dict[str, Any]):
        import threading as _th
        self._lock = _th.Lock()
        hist = []
        for h in (data.get("history") or []):
            try:
                row = dict(h)
                for kk in ("game_time", "disp_time", "home", "away", "net"):
                    if kk in row and row[kk] is None:
                        row[kk] = float("nan")     # None → NaN (gap real)
                hist.append(row)
            except Exception:
                continue
        self.history = hist
        self.hook_goal_markers = list(data.get("goal_markers") or [])
        # versiontechnical note 10technical note27 — technical note red card (archivetechnical note legacy: empty)
        self.red_card_markers = list(data.get("red_card_markers") or [])


def load_match_archive(archive_path: str) -> Optional[Dict[str, Any]]:
    """read archive (ZIP or JSON text) → {"data": match_data, "flags": {...}}.
    text‌text from PNGtext inside ZIP to text RGBA uint8 text text‌textandtext."""
    try:
        import zipfile
        data = None
        flags = {"home": None, "away": None}
        ap = str(archive_path)
        if ap.lower().endswith(".zip") or zipfile.is_zipfile(ap):
            with zipfile.ZipFile(ap, "r") as zf:
                names = set(zf.namelist())
                if "match_data.json" in names:
                    data = json.loads(
                        zf.read("match_data.json").decode("utf-8"))
                if Image is not None:
                    for side in ("home", "away"):
                        nm = f"flag_{side}.png"
                        if nm in names:
                            try:
                                from io import BytesIO as _BIO
                                im = Image.open(_BIO(zf.read(nm)))
                                flags[side] = np.asarray(
                                    im.convert("RGBA")).copy()
                            except Exception:
                                flags[side] = None
        else:
            with open(ap, "r", encoding="utf-8") as f:
                data = json.load(f)
        if not isinstance(data, dict):
            return None
        if str(data.get("format", "")) != MOMENTUM_ARCHIVE_FORMAT:
            # file without technical note technical note — if history technical note technical note (technical notefromtechnical note technical noteand to technical noteand)
            if "history" not in data:
                return None
        return {"data": data, "flags": flags}
    except Exception:
        return None


def render_archive_chart(archive_path: str,
                         out_path: Optional[str] = None) -> Optional[str]:
    """«code textandtext file textandtext text textandtext and to chart text text» (user):
    archive ZIP/JSON → textandtextandtext textto → render complete same line textandtext chart TV → PNG.
    output: path PNG built or None."""
    try:
        loaded = load_match_archive(archive_path)
        if loaded is None:
            return None
        data, flags = loaded["data"], loaded["flags"]
        eng = _ArchiveEngine(data)
        cfg = _ArchiveCurveCfg(data)
        disp = data.get("display", {}) or {}
        colors = disp.get("colors", {}) or {}
        home_c = colors.get("home") or "#e63946"
        away_c = colors.get("away") or "#f5f5f5"
        bg_kind = disp.get("bg_kind") or "half"
        ts = None
        if disp.get("timestamp_enabled"):
            stw = (data.get("match", {}) or {}).get("start_wall")
            if stw:
                ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(stw))
        if out_path is None:
            base = os.path.splitext(os.path.abspath(str(archive_path)))[0]
            out_path = base + "_chart.png"
        d = os.path.dirname(out_path)
        if d:
            os.makedirs(d, exist_ok=True)
        img = render_tv_snapshot(eng, cfg, None, str(bg_kind),
                                 home_c, away_c,
                                 flags.get("home"), flags.get("away"),
                                 timestamp_text=ts,
                                 out_path=out_path, transparent=False)
        if img is None:
            return None
        return out_path
    except Exception:
        return None


class TVSnapshotEngine:
    """text text textagetext‌text (text — without withtext/UItext completetext testable):
      * textortext‌withtext: text in «minutetext text − 1» and display in «minutetext text»text
        if text from minutetext text text textandtext and still text textandtext → text+display immediatetext
      * match end: stop textandtext ≥12s in >90′ and >120′ (level‌text independent)text
        if after from firsttext display withtext from text text textandtext (text text in 90+)text
        text‌withtext text armed text‌textandtext until textandtext real end text display text
        (text 2 display in text level + text‌text 45 second)text
      * register text «start withtext» for text untiltext/time."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.s: Dict[str, Any] = dict(TV_SNAP_DEFAULTS
                                      if settings is None else settings)
        self.match_start_wall: Optional[float] = None
        self._reset_state()

    # --- andtechnical note internal ---
    @staticmethod
    def _new_mid_state() -> Dict[str, Any]:
        """v10.28 (textandtext v1.3 from 2017) — cycletext text text text totaltext textortext‌withtext:
        show_state: None → "requested" (action textin text in text confirmation)
                          → "visible" (confirmation text — consumed)
                          → "failed" (text/text text — text text text)
                          → "abandoned" (text text‌text — text text)
        text text (shown=True) only with confirm_shown text text‌textandtext."""
        return {"cap": False, "shown": False, "pre": False,
                "show_state": None, "show_req_wall": None,
                "retries": 0, "retry_after_wall": None,
                "last_fail": ""}

    @staticmethod
    def _new_end_state() -> Dict[str, Any]:
        # v10.28 — pend: technical note wall technical noteandtechnical note show_end technical note still confirmation technical note
        # fails: count technical note‌technical note technical notefromtechnical note‌technical note technical note level (technical note TV_SNAP_END_FAIL_MAX)
        return {"stop_since": None, "shows": 0,
                "rearm_used": False, "last_show_wall": None,
                "pre": False,          # versiontechnical note 10technical note15 — technical note‌withtechnical note technical note technical note
                "pend": None, "fails": 0}

    def _reset_state(self):
        # versiontechnical note 10technical note15 — "pre" = technical note‌withtechnical note (render + windowtechnical note technical note technical note) technical note technical note
        self.mid = {k: self._new_mid_state() for k in TV_SNAP_KEYS}
        self.end = {"end90": self._new_end_state(),
                    "end120": self._new_end_state()}

    def reset_match(self, now_wall: Optional[float] = None):
        """start text new — text andtext‌text text (untiltext to 00:00 reset text)."""
        self._reset_state()
        self.match_start_wall = None

    def reset_preload_flags(self):
        """versiontext 10text16 — with change text‌text display (smoothing textto/textandtext)text text‌withtext‌text
        «text‌text andtext still display‌data‌text» again armed text‌textandtext until render with
        text new from textand text textandtext (display‌text text‌text unchanged)."""
        for st in self.mid.values():
            if not st["shown"]:
                st["pre"] = False
        for st in self.end.values():
            if st["shows"] < 2:
                st["pre"] = False

    def target_minute(self, key: str) -> int:
        return snap_clamp_minute(key, self.s.get(f"{key}_minute"))

    # =============================================================
    # v10.28 — API technical note display (technical noteandtechnical note v1.3 from versiontechnical note 2017technical note technical note — only from
    # technical note Worker technical note technical note technical noteandtechnical note technical noteandtechnical notedatatechnical note confirm/fail from side UI from technical note
    # technical note technical noteandtechnical note App to technical note‌technical note technical note‌technical noteagetechnical note — section _snap_drain_show_events)
    # =============================================================
    def confirm_shown(self, key: str) -> bool:
        """confirmation text Snapshot to SHOWING (text renderer.show) — only in text
        text text text text text‌textandtext output False text confirmation text‌text/text."""
        st = self.mid.get(key)
        if not st or st.get("show_state") != "requested":
            return False
        st["show_state"] = "visible"
        st["shown"] = True
        st["retry_after_wall"] = None
        return True

    def fail_show(self, key: str, now_wall: Optional[float] = None,
                  reason: str = "") -> bool:
        """text dispatch/UI for text totaltext → armed‌textfromtext text for text aftertext
        (text from TV_SNAP_SHOW_RETRY_BACKOFF_SEC) — display still text text."""
        st = self.mid.get(key)
        if not st or st.get("show_state") != "requested":
            return False
        now = float(now_wall) if now_wall is not None else time.time()
        st["show_state"] = "failed"
        st["retry_after_wall"] = now + TV_SNAP_SHOW_RETRY_BACKOFF_SEC
        if reason:
            st["last_fail"] = str(reason)[:120]
        return True

    def show_attempt(self, key: str) -> int:
        """numbertext text current (1 = firsttext showtext n>1 = text text)."""
        st = self.mid.get(key)
        if not st:
            return 0
        return int(st.get("retries", 0)) + (1 if st.get("show_state")
                                             in ("requested", "failed") else 0)

    def confirm_show_end(self) -> bool:
        """confirmation display end (totaltext App «end») — pend text textand level text text‌textandtext
        (in text moment text text show_end in textandfrom is)."""
        hit = False
        for lvl in ("end90", "end120"):
            st = self.end.get(lvl)
            if st is not None and st.get("pend") is not None:
                st["pend"] = None
                hit = True
        return hit

    def fail_show_end(self, lvl: str, now_wall: Optional[float] = None,
                      reason: str = "") -> bool:
        """text display end → «shows» text text text‌textandtext and text text stop
        (confirmation 12 second‌text + Cooldown) again armed text‌textandtext until display endtext
        without restart withtext again textin textandtext."""
        st = self.end.get(lvl)
        if not st or st.get("pend") is None:
            return False
        st["pend"] = None
        st["shows"] = max(0, int(st.get("shows", 0)) - 1)
        st["stop_since"] = None
        st["last_show_wall"] = None
        st["fails"] = int(st.get("fails", 0)) + 1
        if reason:
            st["last_fail"] = str(reason)[:120]
        return True

    def tick(self, total_t, m_state, half_number, now_wall) -> List[Tuple[str, str]]:
        """text textWorker — output: list text‌text:
             ("capture", key)  → render PNG textandtext (minutetext text − 1)
             ("show", key)     → display textandtext text (minutetext text)
             ("show_end", lvl) → display match end (end90/end120)"""
        acts: List[Tuple[str, str]] = []
        if total_t is None:
            return acts
        try:
            t = float(total_t)
        except (TypeError, ValueError):
            return acts
        now = float(now_wall) if now_wall is not None else time.time()
        if self.match_start_wall is None:
            self.match_start_wall = now          # register technical note «start» withtechnical note
        try:
            half = int(half_number) if half_number is not None else 1
        except (TypeError, ValueError):
            half = 1

        # ---------- technical noteortechnical note‌withtechnical note (technical note first / second / extra time) ----------
        # versiontechnical note 10technical note15 — «et» in technical note technical noteand technical note extra time (half 3/4) valid istechnical note
        # «2» for technical notefromtechnical note with technical note technical note technical notefrom ET to technical note technical note armed technical note withtechnical note.
        for key, need_half in (("h1", (1,)), ("h2", (2,)), ("et", (2, 3, 4))):
            if not self.s.get(f"{key}_enabled"):
                continue
            if half not in need_half:
                continue
            st = self.mid[key]
            if st["shown"]:
                continue
            # --- v10.28 — technical note cycletechnical note technical note (before from technical note technical note) ---
            _ss = st.get("show_state")
            if _ss == "requested":
                # technical note confirmation technical note (dispatch technical note‌technical note/UI technical note — technical note withtechnical note
                # «43/85 in 2026 display data technical note and technical note technical note technical note»)
                if (st.get("show_req_wall") is not None
                        and now - st["show_req_wall"]
                        > TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC):
                    st["show_state"] = "failed"
                    st["last_fail"] = "confirm-timeout"
                    st["retry_after_wall"] = now + TV_SNAP_SHOW_RETRY_BACKOFF_SEC
                    _ss = "failed"
            if _ss == "failed":
                if now >= (st.get("retry_after_wall") or 0.0):
                    if int(st.get("retries", 0)) >= TV_SNAP_SHOW_MAX_RETRIES:
                        # technical note technical note‌technical note — technical note technical note‌technical noteandtechnical note (shown=True until cycle technical note)
                        st["show_state"] = "abandoned"
                        st["shown"] = True
                        acts.append(("show_abandoned", key))
                    else:
                        st["retries"] = int(st.get("retries", 0)) + 1
                        st["show_state"] = "requested"
                        st["show_req_wall"] = now
                        acts.append(("show", key))     # technical note technical note
                # still inside Backoff → technical note action newtechnical note technical note
            tgt_min = self.target_minute(key)
            # versiontechnical note 10technical note15 — technical note‌withtechnical note: in windowtechnical note 2 secondtechnical note «before from» momenttechnical note
            # displaytechnical note render + technical note windowtechnical note technical note technical note (andtechnical noteandtechnical note without technical note — user:
            # «technical note from technical notein technical note technical note until technical noteandtechnical note andtechnical noteandtechnical note technical noteandtechnical note to technical noteandtechnical note technical note»)
            if (not st["pre"]) and \
                    (tgt_min * 60.0 - TV_SNAP_PRELOAD_LEAD_SEC) <= t < tgt_min * 60.0:
                st["pre"] = True
                acts.append(("preload", key))
            if (not st["cap"]) and t >= (tgt_min - 1) * 60.0:
                st["cap"] = True
                acts.append(("capture", key))
            if t >= tgt_min * 60.0 and st.get("show_state") is None:
                if not st["cap"]:            # technical note from technical note technical note technical note technical noteandtechnical note → immediate
                    st["cap"] = True
                    acts.append(("capture", key))
                # v10.28 — only «request» register technical note‌technical noteandtechnical note technical note technical note with confirmation
                st["show_state"] = "requested"
                st["show_req_wall"] = now
                acts.append(("show", key))

        # ---------- match end (>90′ and >120′) ----------
        # level 120 first technical noteortechnical note technical note‌technical noteandtechnical note if display 120+ decreasetechnical note level 90+ for
        # «technical note stop» technical note‌technical note is and complete technical note technical note‌technical noteandtechnical note (technical noteandtechnical note from display technical noteandtechnical note)
        if self.s.get("end_enabled"):
            for lvl, min_t in (("end120", 120 * 60.0), ("end90", 90 * 60.0)):
                st = self.end[lvl]
                # --- v10.28 — technical note confirmation show_end beforetechnical note (dispatch technical note‌technical note) ---
                if st.get("pend") is not None:
                    if now - st["pend"] > TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC \
                            and int(st.get("fails", 0)) < TV_SNAP_END_FAIL_MAX:
                        # technical note technical note shows + armed‌technical notefromtechnical note againtechnical note technical note stop
                        st["pend"] = None
                        st["shows"] = max(0, int(st.get("shows", 0)) - 1)
                        st["stop_since"] = None
                        st["last_show_wall"] = None
                        st["fails"] = int(st.get("fails", 0)) + 1
                        st["last_fail"] = "confirm-timeout"
                if st["shows"] >= 2:
                    continue
                if t < min_t:
                    continue
                if str(m_state) == "PLAYING":
                    st["stop_since"] = None
                    st["pre"] = False        # versiontechnical note 10technical note15 — technical note‌withtechnical note withtechnical note
                    # technical note technical note in 90+ display technical note technical note technical note and withtechnical note resume technical notedecrease →
                    # for stop realtechnical note end technical note armed technical note‌technical noteandtechnical note (only technical note‌withtechnical note)
                    if st["shows"] == 1 and not st["rearm_used"]:
                        st["shows"] = 0
                        st["rearm_used"] = True
                    continue
                if st["stop_since"] is None:
                    st["stop_since"] = now
                # versiontechnical note 10technical note15 — technical note‌withtechnical note end: in windowtechnical note ~2 secondtechnical note
                # «before from» confirmation stoptechnical note end (technical note render in momenttechnical note display)
                _elapsed = now - st["stop_since"]
                if (not st["pre"]) and \
                        (TV_SNAP_END_STOP_CONFIRM_SEC
                         - TV_SNAP_PRELOAD_LEAD_SEC) <= _elapsed \
                        < TV_SNAP_END_STOP_CONFIRM_SEC:
                    st["pre"] = True
                    acts.append(("preload_end", lvl))
                if now - st["stop_since"] < TV_SNAP_END_STOP_CONFIRM_SEC:
                    continue
                if (st["last_show_wall"] is not None
                        and now - st["last_show_wall"] < TV_SNAP_END_RESHOW_COOLDOWN_SEC):
                    continue
                st["shows"] += 1
                st["stop_since"] = None
                st["last_show_wall"] = now
                st["pend"] = now            # v10.28 — in technical note confirmation
                acts.append(("show_end", lvl))
                if lvl == "end120":
                    # display endtechnical note 120+ technical note is — level 90+ «complete» technical note
                    # technical note‌technical noteandtechnical note (technical noteandtechnical note v1.2.2 from 2017 — technical noteandtechnical note from display technical noteandtechnical note
                    # technical noteandtechnical note endtechnical note andtechnical note‌technical note)
                    st90 = self.end["end90"]
                    st90["shows"] = 2
                    st90["last_show_wall"] = now
                    st90["stop_since"] = None
                    if st90.get("pend") is not None:
                        # v10.28 — show90 in technical noteandfrom technical noteandtechnical note technical note technical noteandtechnical note technical noteandtechnical note pend technical noteand
                        # technical note technical note technical note‌technical noteandtechnical note (confirmation technical note technical note impacttechnical note technical note)
                        st90["pend"] = None
        return acts


# --- versiontechnical note 10technical note22 — Figure/Canvas «technical note» render Snapshot (firstandtechnical note 4 user):
# to‌technical note technical note Figure/axes/technical note from technical note in technical note render (~580ms)technical note same Figure
# technical note reuse technical note‌technical noteandtechnical note draw_tv_momentum technical noteandtechnical note ax.clear() technical note‌technical note → output
# technical note‌to‌technical note technical note before is and only technical note technical note technical note‌technical note technical note technical note‌technical noteandtechnical note.
# technical note: render from technical note Worker (capture/preload/end) and technical note snap-retune (technical note‌untiltechnical note
# technical note‌technical note) technical noteandtechnical note technical note‌technical noteandtechnical note — technical note‌technical noteandtechnical note technical notein with technical noteandtechnical note‌technical note Lock technical note technical note‌technical noteandtechnical note.
_SNAP_RENDER_CACHE: Dict[str, Any] = {"fig": None, "canvas": None,
                                      "key": None, "lock": threading.Lock()}


def render_tv_snapshot(momentum, cfg, disp_value, bg_kind: str,
                       home_color: str, away_color: str,
                       home_flag_arr, away_flag_arr,
                       timestamp_text: Optional[str] = None,
                       out_path: Optional[str] = None,
                       transparent: bool = True):
    """render text chart TV textandtext textandtext Agg independent (without text‌text to text):
    output PIL.Image (RGBA). with transparent=True text‌pitchtext text text‌text —
    text text textandtext original text text‌textandtext until text display textandtext withtext textandtext
    withtext from text text textandtext. text output exactly text textandtext text‌pitchtext is
    (half/full: 1608×978 — extra: 2034×978).
    versiontext 10text22 — Figure/Canvas text: Figure only text‌withtext for text
    (W,H,dpi) text text‌textandtext and in rendertext aftertext reuse text‌textandtext (ax.clear()
    inside draw_tv_momentum textandtext beforetext text complete text text‌text → output
    unchangedtext text textortext never in path Show is not — only Worker)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    bg = tv_load_background(bg_kind)
    if bg is None:
        return None
    W, H = int(bg["W"]), int(bg["H"])
    dpi = 100.0
    # versiontechnical note 10technical note25 — technical notesample‌technical note render technical noteagetechnical note‌technical note: technical noteandtechnical note SS technical note technical note‌technical note technical note
    # technical note‌technical noteandtechnical note and technical note technical note with technical noteortechnical note Box to technical notefromtechnical note technical note technical noteandtechnical note technical note‌technical note. technical note
    # technical notefromtechnical note‌technical note (line‌technical note/technical note/ball/logo) technical note technical note «technical note technical note» technical note technical note‌technical note and
    # with dpi technical noteortechnical note technical note‌technical noteandtechnical note ⇒ after from technical noteandtechnical note exactly same technical notefromtechnical note before.
    # render in technical note Worker and ~1 minute before from display technical note technical note‌technical noteandtechnical note ⇒ technical note
    # technical notewithtechnical note never in path Show is not.
    ss = max(1, int(TV_SNAPSHOT_SS))
    with _SNAP_RENDER_CACHE["lock"]:
        fkey = (W, H, round(dpi, 3), ss)
        if (_SNAP_RENDER_CACHE["fig"] is None
                or _SNAP_RENDER_CACHE["key"] != fkey):
            fig = Figure(figsize=(W / dpi, H / dpi), dpi=dpi * ss)
            canvas = FigureCanvasAgg(fig)
            _SNAP_RENDER_CACHE["fig"] = fig
            _SNAP_RENDER_CACHE["canvas"] = canvas
            _SNAP_RENDER_CACHE["key"] = fkey
        fig = _SNAP_RENDER_CACHE["fig"]
        canvas = _SNAP_RENDER_CACHE["canvas"]
        ax = fig.axes[0] if fig.axes else fig.add_subplot(111)
        draw_tv_momentum(ax, momentum, cfg, disp_value, bg_kind,
                         home_color=home_color, away_color=away_color,
                         home_flag_arr=home_flag_arr,
                         away_flag_arr=away_flag_arr,
                         transparent_bg=bool(transparent),
                         timestamp_text=timestamp_text)
        canvas.draw()
        buf = np.asarray(canvas.buffer_rgba()).copy()
    # versiontechnical note 10technical note25 — technical noteandtechnical note technical notesample‌technical note: technical noteortechnical note Box (AA realtechnical note without technical note technical noteto)
    if ss > 1 and buf.shape[0] >= H and buf.shape[1] >= W:
        try:
            from PIL import Image as _ImgSS
            _im_ss = _ImgSS.fromarray(buf)
            _im_ss = _im_ss.resize((W, H), _ImgSS.Resampling.BOX)
            buf = np.asarray(_im_ss).copy()
        except Exception:
            pass
    # smoothtechnical note‌technical notefromtechnical note technical note: technical notetotechnical note float technical notefromtechnical note technical noteandtechnical note technical note 1px technical noteandtechnical note‌technical note technical note‌technical note
    # (16.08×100 → 1607) — with technical note technical note exactly to technical note technical noteandtechnical note technical note‌pitchtechnical note technical note‌technical note
    if buf.shape[0] != H or buf.shape[1] != W:
        fixed = np.zeros((H, W, 4), dtype=np.uint8)
        hh = min(H, buf.shape[0])
        ww = min(W, buf.shape[1])
        fixed[:hh, :ww] = buf[:hh, :ww]
        buf = fixed
    # versiontechnical note 10technical note18 — technical note mode technical note technical note (DeprecationWarning Pillow 13):
    # fromarray from technical notetotal technical note (H,W,4) technical noteandtechnical note RGBA technical note detection technical note‌technical note
    img = Image.fromarray(buf) if Image is not None else None
    if img is not None and out_path:
        try:
            d = os.path.dirname(os.path.abspath(out_path))
            if d:
                os.makedirs(d, exist_ok=True)
            img.save(out_path)
        except Exception:
            return None
    return img


def _premultiply_rgba(img):
    """text‌textfromtext text BGRA with text text‌text‌text for UpdateLayeredWindow."""
    arr = np.array(img.convert("RGBA"), dtype=np.uint8)
    a = arr[:, :, 3:4].astype(np.uint32)
    rgb = (arr[:, :, :3].astype(np.uint32) * a + 127) // 255
    out = np.empty(arr.shape, dtype=np.uint8)
    out[:, :, 0] = rgb[:, :, 2]        # B
    out[:, :, 1] = rgb[:, :, 1]        # G
    out[:, :, 2] = rgb[:, :, 0]        # R
    out[:, :, 3] = arr[:, :, 3]        # A
    return np.ascontiguousarray(out)


def win32_show_layered(win, pil_img, x: int, y: int, w: int, h: int,
                       arr=None, trace=None) -> bool:
    """display windowtext Tk with text text real textandtext andtextandtext (UpdateLayeredWindow):
    window topmosttext totaltext‌text (WS_EX_TRANSPARENT) and without text textandtextandtext
    (WS_EX_NOACTIVATE) — text decreasetext textandtext textandtext withtext.
    versiontext 10text16 — arr text BGRA text‌text‌text text (from text Worker) istext
    in text text text textfromtext text in UI-Thread text text‌textandtext.
    versiontext 10text18 — trace (SnapShowTrace): text‌text text (Premultiplytext
    CreateDIBSectiontext Upload to UpdateLayeredWindow) text time‌text
    text‌textandtext until textandtext original text (ULW/DWM) exactly text textandtext (text 6 user).
    in textandtext andtextandtext/Error → False (textandtext fallback text text‌text)."""
    if os.name != "nt" or Image is None:
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32

        try:
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        except Exception:
            hwnd = win.winfo_id()
        if not hwnd:
            return False
        if trace is not None:
            trace.step("Layered: ex-style set", hwnd=hwnd, size=(w, h))

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_NOACTIVATE = 0x08000000
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                              style | WS_EX_LAYERED | WS_EX_TRANSPARENT |
                              WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)

        t_pre = trace.begin() if trace is not None else 0.0
        if arr is None:
            arr = _premultiply_rgba(pil_img)
        if trace is not None:
            trace.end("Layered: Premultiply RGBA", t_pre, hwnd=hwnd,
                      size=(w, h),
                      note=("UI fallback (worker arr missing!)"
                            if pil_img is not None else "worker-ready"))

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                        ("bmiColors", wintypes.DWORD * 3)]

        class BLENDFUNCTION(ctypes.Structure):
            _fields_ = [("BlendOp", ctypes.c_byte),
                        ("BlendFlags", ctypes.c_byte),
                        ("SourceConstantAlpha", ctypes.c_byte),
                        ("AlphaFormat", ctypes.c_byte)]

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class SIZE(ctypes.Structure):
            _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

        BI_RGB = 0
        DIB_RGB_COLORS = 0
        ULW_ALPHA = 2
        AC_SRC_OVER = 0
        AC_SRC_ALPHA = 1

        hdc_screen = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        bi = BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = w
        bi.bmiHeader.biHeight = -h          # top-down
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = BI_RGB
        t_dib = trace.begin() if trace is not None else 0.0
        ptr = ctypes.c_void_p()
        dib = gdi32.CreateDIBSection(hdc_mem, ctypes.byref(bi),
                                     DIB_RGB_COLORS, ctypes.byref(ptr),
                                     None, 0)
        if trace is not None:
            trace.end("Layered: CreateDIBSection", t_dib, hwnd=hwnd,
                      size=(w, h))
        if not dib or not ptr:
            gdi32.DeleteDC(hdc_mem)
            user32.ReleaseDC(0, hdc_screen)
            return False
        old = gdi32.SelectObject(hdc_mem, dib)
        t_up = trace.begin() if trace is not None else 0.0
        ctypes.memmove(ptr, arr.ctypes.data, arr.nbytes)
        blend = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        pt_dst = POINT(x, y)
        pt_src = POINT(0, 0)
        size = SIZE(w, h)
        ok = user32.UpdateLayeredWindow(hwnd, hdc_screen,
                                        ctypes.byref(pt_dst),
                                        ctypes.byref(size),
                                        hdc_mem, ctypes.byref(pt_src),
                                        0, ctypes.byref(blend), ULW_ALPHA)
        if trace is not None:
            trace.end("Layered: UpdateLayeredWindow (upload)", t_up,
                      hwnd=hwnd, size=(w, h),
                      note=("OK" if ok else "FAILED"))
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(dib)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, hdc_screen)
        return bool(ok)
    except Exception:
        return False


def win32_move_window(win, x: int, y: int) -> bool:
    """textto‌text windowtext layer‌text «without» withtext text‌text (SetWindowPos) — versiontext
    10text13: text textandtext text andtextandtext/textandtext with text text in text frame.
    versiontext 10text18 (text 7 user): in text frame only Position textandtext text‌textandtext —
    HWND_TOPMOST and SWP_SHOWWINDOW text text (Topmost text‌withtext in momenttext text
    text text‌textandtext and Show text text‌withtext text text istext change Z-order/Show-state
    in text frametext withtext agetext Window Management and DWM text‌textfromtext).
    in textandtext andtextandtext/Error → False (textandtext fallback with geometry text text‌textandtext).
    versiontext 10text20 (text 6 user): text + text‌text real in text _SWP_LAST."""
    if os.name != "nt":
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        except Exception:
            hwnd = win.winfo_id()
        if not hwnd:
            return False
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        _fl = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        _t0 = time.perf_counter()              # versiontechnical note 10technical note20 — technical note 6
        _ok = bool(user32.SetWindowPos(hwnd, 0, int(x), int(y),
                                       0, 0, _fl))
        try:                                   # technical note — without log technical note
            _SWP_LAST.update(hwnd=int(hwnd), x=int(x), y=int(y),
                             flags=_fl, src="move_window",
                             dur_ms=(time.perf_counter() - _t0) * 1000.0,
                             ok=_ok)
        except Exception:
            pass
        return _ok
    except Exception:
        return False


def win32_hwnd_of(win):
    """versiontext 10text16 — hwnd text windowtext Tk (text‌withtext in UI-Thread text text‌textandtext until
    text text without text textandtext Tk text text)."""
    if os.name != "nt" or win is None:
        return None
    try:
        import ctypes
        user32 = ctypes.windll.user32
        try:
            hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        except Exception:
            hwnd = win.winfo_id()
        return int(hwnd) if hwnd else None
    except Exception:
        return None


# versiontechnical note 10technical note20 — technical note latest technical noteandtechnical note SetWindowPos technical note (technical note 6 user):
# win32_move_hwnd / win32_move_window technical note (perf_counter) + technical note‌technical note real +
# technical note technical note technical note‌technical note technical note‌technical noteandtechnical noteagetechnical note technical note technical note after from technical note frame technical note technical note technical note‌technical noteandtechnical note and in
# technical noteandtechnical note [SNAPSHOT ANIMATION DEBUG] register technical note‌technical note. without log direct (without technical note)technical note
# change technical note technical noteandtechnical note technical note technical notefromtechnical note technical note.
_SWP_LAST = {"hwnd": None, "x": 0, "y": 0, "flags": 0, "dur_ms": 0.0,
             "ok": False, "src": "-"}


def _swp_flags_text(flags: int) -> str:
    """versiontext 10text20 — stringtext textandtext for text‌text SetWindowPos (text 7 user)."""
    names = ((0x0001, "NOSIZE"), (0x0002, "NOMOVE"), (0x0004, "NOZORDER"),
             (0x0008, "NOREDRAW"), (0x0010, "NOACTIVATE"),
             (0x0020, "DRAWFRAME"), (0x0040, "FRAMECHANGED"),
             (0x0080, "SHOWWINDOW"), (0x0100, "HIDEWINDOW"),
             (0x0200, "NOCOPYBITS"), (0x4000, "ASYNCWINDOWPOS"))
    on = [nm for bit, nm in names if flags & bit]
    return f"0x{int(flags):04X} (" + "|".join(on) + ")" if on \
        else f"0x{int(flags):04X}"


# --- versiontechnical note 10technical note21 — test 5 user: technical note complete andtechnical noteandtechnical note technical note SetWindowPos ---
# user32 with use_last_error=True until GetLastError technical note from technical noteandtechnical note technical note withtechnical note
# (ctypes technical note technical note save technical note‌technical note and ctypes.get_last_error() technical note‌technical note).
_U32_LE = None
if os.name == "nt":
    try:
        _U32_LE = ctypes.WinDLL("user32", use_last_error=True)
    except Exception:
        _U32_LE = None

# latest technical noteandtechnical note technical note _win32_swp_debug (technical note technical note after from technical note technical note technical note technical note
# technical note technical note‌technical note and in technical noteandtechnical note [SNAPSHOT ANIMATION DEBUG] print technical note‌technical noteandtechnical note).
_SWP_LAST_EXTRA = {}

_EX_BITS = ((0x00000008, "TOPMOST"), (0x00080000, "LAYERED"),
            (0x00000020, "TRANSPARENT"), (0x08000000, "NOACTIVATE"))


def _snap_exstyle_text(ex) -> str:
    """versiontext 10text21 — text textandtext text‌text ex-style (test 5 user)."""
    try:
        if ex is None:
            return "?"
        on = [nm for bit, nm in _EX_BITS if int(ex) & bit]
        return "|".join(on) if on else "none"
    except Exception:
        return "?"


def _snap_ui_stack_sample(max_frames: int = 10) -> str:
    """versiontext 10text21 — sampletext text Python text Main/UI from text text
    (sys._current_frames) — when SetWindowPos text text textandtext text‌textandtext
    text sample text text‌text UI-Thread exactly text codetext text text‌text
    (passtext text D user: text andtextandtext 150ms and textandtext 1mstext)."""
    try:
        mt = threading.main_thread()
        fr = sys._current_frames().get(mt.ident)
        out = []
        n = 0
        while fr is not None and n < max_frames:
            out.append(f"{os.path.basename(fr.f_code.co_filename)}:"
                       f"{fr.f_lineno}({fr.f_code.co_name})")
            fr = fr.f_back
            n += 1
        return " <- ".join(out)
    except Exception:
        return ""


def _win32_swp_debug(hwnd, x: int, y: int, src: str = "move_hwnd"):
    """versiontext 10text21 — test 5 user: «same» SetWindowPos text (flags text
    0x0015 = NOSIZE|NOZORDER|NOACTIVATE) text with text complete andtextandtext text
    text‌text and textandtext text in _SWP_LAST_EXTRA text‌text and text‌text:
      * old x/y (GetWindowRect before) / text requesttext / y real after from text
      * HWND + native Thread ID + Thread priority
      * flags + return value + GetLastError
      * before and after: GetForegroundWindow / IsWindowVisible / text‌text
        WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
      * if text > TV_SNAP_UI_STACK_ON_SLOW_MS → sampletext text UI-Thread
    only when TV_SNAP_SWP_WIN_DEBUG active istext in textandtext andtextandtext/Error → None
    (textandtext to path text beforetext text‌text — textuntiltext text unchanged)."""
    if os.name != "nt" or not hwnd or not TV_SNAP_SWP_WIN_DEBUG:
        return None
    try:
        from ctypes import wintypes as _wt
        u = _U32_LE if _U32_LE is not None else ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        hwnd = int(hwnd)
        GWL_EXSTYLE = -20
        ex_mask = 0x00000008 | 0x00080000 | 0x00000020 | 0x08000000
        # --- andtechnical note «before» (Error → None/technical note — technical note‌codetechnical note path technical note technical note technical noteandtechnical note
        # technical note‌technical note SetWindowPos technical noteandtechnical note always technical note technical note‌technical noteandtechnical note) ---
        old = None
        fg0 = vis0 = ex0 = None
        try:
            rc = _wt.RECT()
            if u.GetWindowRect(hwnd, ctypes.byref(rc)):
                old = (int(rc.left), int(rc.top))
            fg0 = int(u.GetForegroundWindow() or 0)
            vis0 = bool(u.IsWindowVisible(hwnd))
            ex0 = int(u.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0) & ex_mask
        except Exception:
            pass
        try:
            prio = int(k32.GetThreadPriority(k32.GetCurrentThread()))
        except Exception:
            prio = None
        flags = 0x0001 | 0x0004 | 0x0010
        # --- technical noteandtechnical note technical noteandtechnical note (if technical noteandtechnical note Error technical note → None until path technical note resume technical note) ---
        try:
            t0 = time.perf_counter()
            ok = bool(u.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, flags))
            err = int(ctypes.get_last_error()) if _U32_LE is not None else -1
            dur = (time.perf_counter() - t0) * 1000.0
        except Exception:
            return None
        # --- andtechnical note «after» ---
        new = None
        fg1 = vis1 = ex1 = None
        try:
            rc2 = _wt.RECT()
            if u.GetWindowRect(hwnd, ctypes.byref(rc2)):
                new = (int(rc2.left), int(rc2.top))
            fg1 = int(u.GetForegroundWindow() or 0)
            vis1 = bool(u.IsWindowVisible(hwnd))
            ex1 = int(u.GetWindowLongW(hwnd, GWL_EXSTYLE) or 0) & ex_mask
        except Exception:
            pass
        rec = {
            "src": src, "hwnd": hwnd,
            "old": old, "new_req": (int(x), int(y)), "new": new,
            "fg0": fg0, "vis0": vis0, "ex0": ex0,
            "fg1": fg1, "vis1": vis1, "ex1": ex1,
            "tid": _snap_native_tid(), "prio": prio,
            "flags": flags, "ok": ok, "err": err, "dur_ms": dur,
            "ui_stack": (_snap_ui_stack_sample()
                         if dur > TV_SNAP_UI_STACK_ON_SLOW_MS else ""),
        }
        try:
            _SWP_LAST_EXTRA.clear()
            _SWP_LAST_EXTRA.update(rec)
        except Exception:
            pass
        return rec
    except Exception:
        return None


def _anim_slow_swp_text(recs, thr_ms: float = 5.0) -> str:
    """versiontext 10text21 — list frame‌text text SetWindowPos (text test 5)."""
    try:
        items = [(int(r.get("no", 0)), float(r.get("swp_ms", 0.0)))
                 for r in recs if not r.get("skipped")]
        slow = [f"#{no:02d}={d:.1f}ms" for no, d in items if d > thr_ms]
        return ", ".join(slow)
    except Exception:
        return ""


def _anim_flags_policy_text(recs) -> str:
    """versiontext 10text21 — test 4 user: textistext‌text automatic text‌text — text frame‌text
    text must exactly 0x0015 (NOSIZE|NOZORDER|NOACTIVATE) withtext text
    HWND_TOPMOST / SWP_SHOWWINDOW / change Z-order / UpdateLayeredWindow /
    opacity / resize / withtextfromtext window in text textfrom is not (Topmost/Show only
    text‌withtext in text window text text‌text)."""
    try:
        if os.name != "nt":
            return "n/a (non-Windows)"
        mov = [r for r in recs if not r.get("skipped")]
        if not mov:
            return "no SetWindowPos frames (TEST-B NO-MOVE)"
        bad = [int(r.get("no", 0)) for r in mov
               if int(r.get("flags", 0)) != 0x0015]
        if not bad:
            return ("OK — all frames 0x0015 (NOSIZE|NOZORDER|NOACTIVATE); "
                    "no TOPMOST/SHOWWINDOW/Z-order/ULW per frame")
        return (f"VIOLATION in frames {bad} — flags other than 0x0015 seen!")
    except Exception:
        return "?"


def win32_move_hwnd(hwnd, x: int, y: int) -> bool:
    """versiontext 10text16 — textto‌text with hwnd text and «without text textandtext Tk»:
    text text text with text untiltext frame‌text text independent from text UI text
    text‌text (text text andtextandtext textagetext‌text — text user: text to text text).
    versiontext 10text18 (text 7 user): only text — SWP_NOZORDER | SWP_NOACTIVATEtext
    without HWND_TOPMOST and without SWP_SHOWWINDOW (Topmost/Show text‌withtext in
    text window text text‌text «Topmost andtext window istext text text text frame»).
    versiontext 10text20 (text 6 user): t0/t1 with perf_counter — text + text‌text
    real + text in text _SWP_LAST register text‌textandtext (text 7: must always
    0x0015 = NOSIZE|NOZORDER|NOACTIVATE withtext).
    versiontext 10text21 (test 5 user): when TV_SNAP_SWP_WIN_DEBUG active istext text
    textandtext from path _win32_swp_debug text‌textandtext (same SetWindowPos with same
    0x0015 + old/new x,y + andtext before/after + GetLastError + sampletext text
    UI in text)text textandtext in _SWP_LAST_EXTRA text‌text until text text text text
    in textandtext [SNAPSHOT ANIMATION DEBUG] print text. textandtext textandtext and text‌text
    text changetext text‌text."""
    if os.name != "nt" or not hwnd:
        return False
    # --- versiontechnical note 10technical note21 — test 5: path technical note complete (same technical note datatechnical note technical note) ---
    _rec = _win32_swp_debug(hwnd, x, y, "move_hwnd")
    if _rec is not None:
        try:
            _SWP_LAST.update(hwnd=int(hwnd), x=int(x), y=int(y),
                             flags=int(_rec.get("flags", 0x0015)),
                             src="move_hwnd",
                             dur_ms=float(_rec.get("dur_ms", 0.0)),
                             ok=bool(_rec.get("ok")))
        except Exception:
            pass
        return bool(_rec.get("ok"))
    try:
        import ctypes
        user32 = ctypes.windll.user32
        SWP_NOSIZE = 0x0001
        SWP_NOZORDER = 0x0004
        SWP_NOACTIVATE = 0x0010
        _fl = SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE
        _t0 = time.perf_counter()              # technical note 6: before from SetWindowPos
        _ok = bool(user32.SetWindowPos(int(hwnd), 0, int(x),
                                       int(y), 0, 0, _fl))
        try:                                   # technical note 6: after from SetWindowPos
            _SWP_LAST.update(hwnd=int(hwnd), x=int(x), y=int(y),
                             flags=_fl, src="move_hwnd",
                             dur_ms=(time.perf_counter() - _t0) * 1000.0,
                             ok=_ok)
        except Exception:
            pass
        return _ok
    except Exception:
        return False


def win32_window_y(hwnd) -> Optional[int]:
    """versiontext 10text17 — y real (withtext text) window from textandtext andtextandtext
    (GetWindowRect) — for «andtext‌text andtextandtext»: detection text window still text
    text text text is or text. in textandtext andtextandtext/Error → None."""
    if os.name != "nt" or not hwnd:
        return None
    try:
        import ctypes
        from ctypes import wintypes as _wt
        rc = _wt.RECT()
        if ctypes.windll.user32.GetWindowRect(int(hwnd),
                                              ctypes.byref(rc)):
            return int(rc.top)
    except Exception:
        pass
    return None


# =====================================================================
# 26. technical note usertechnical note technical note (Main Application — Tkinter + Matplotlib)
# ---------------------------------------------------------------------
# Tabtechnical note: 📈 Live Match Momentum | 📋 Event Timeline | 📊 Possession Sequences
#        🎯 Event / Threat Details | 🧪 Momentum Debug
# Header: technical note andtechnical note withtechnical note Match Time (live)technical note Possessiontechnical note Home/Away
# =====================================================================
# =====================================================================
# 26 — technical noteortechnical note independent technical noteandtechnical note team‌technical note: logo/technical note Home and Away (version 10technical note5)
# ---------------------------------------------------------------------
# technical note technical note from tool independent «Team Tracker» user technical note technical note is:
#   * technical note 100technical note independent from GameEngine original and buttontechnical note «technical note to technical noteandtechnical note withtechnical note»technical note
#     technical note read-only technical noteandtechnical note technical note withtechnical note technical note‌technical note and technical note write/hooktechnical note technical noteandtechnical note technical noteandtechnical note withtechnical note
#     technical note technical note‌technical note (only ReadProcessMemory).
#   * from momenttechnical note technical note technical note technical note 1 second technical note to technical note technical note‌technical note after from technical note
#     successful technical note technical note technical note technical note technical note technical note‌technical noteandtechnical note (versiontechnical note 10technical note6: from same moment
#     read technical note‌technical note «technical note‌untiltechnical note» technical note‌technical noteandtechnical note — technical note 50ms technical note technical note realtime_loop
#     tool originaltechnical note if technical noteandtechnical note technical note technical noteandtechnical note again to technical note «technical note technical note 1 second»
#     technical note‌technical note. technical note agetechnical note technical noteandtechnical note only when technical note technical note‌technical noteandtechnical note technical note or andtechnical note is nottechnical note
#     or read memory technical note technical noteandtechnical note — technical note in technical note technical note technical note).
#   * [PT v2.3.1] detection team only when technical note technical note‌technical noteandtechnical note technical note byte andtechnical note menu
#     (base+0x36F9AE0) = 9 withtechnical note (beforetechnical note 100 technical noteandtechnical note) — in «technical note technical noteand» pathtechnical note PT and
#     legacytechnical note technical note andtechnical note‌technical note technical note technical note technical noteandtechnical note latest technical note valid — technical note tool original.
#   * versiontechnical note 10technical note6 — color chart: technical noteand byte istechnical note 1 technical note numbertechnical note color technical note team
#     (technical note: 0x1436F5198 Home / 0x1436F51A0 Away = base+technical note) in technical note technical note
#     technical note technical noteandtechnical note technical note‌technical noteandtechnical note and TeamColorResolver color fill chart technical note from
#     leagues_data.json (technical note technical note) technical note‌technical note — section 26-technical note.
# =====================================================================
TEAM_TRACKER_INTERVAL_MS = 1000        # technical note technical note (until andtechnical note‌technical note): technical note 1 second
TEAM_LIVE_INTERVAL_MS = 50             # after from technical note: read technical note‌untiltechnical note technical note‌technical note (technical note tool original)
TEAM_PROCESS_ACCESS = 0x0010 | 0x0400  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
TEAM_MENU_STATE_OFFSET = 0x036F9AE0    # byte andtechnical note menu (read direct base+technical note — technical note technical note technical note‌technical note istechnical note)
# [PT v2.3.1] technical note technical note detection team: only when byte menu = 9 withtechnical note (beforetechnical note 100 technical noteandtechnical note).
# readtechnical note technical note byte with same _read_u8 technical note technical note‌technical noteandtechnical note technical note technical note technical note pointertechnical note technical note technical note‌technical noteandtechnical note.
TEAM_MENU_DETECT_VALUE = 9
TEAM_DB_DIRNAME = "Football_Database"  # foldertechnical note technical noteandtechnical note technical note technical note
TEAM_SLOT_COUNT = 37                   # count technical note‌technical note technical note team (technical note tool original)
TEAM_SLOT_STRIDE = 112                 # distancetechnical note technical note‌technical note (byte)
TEAM_LOGO_SLOT_PX = (96, 96)           # technical notefromtechnical note technical note logo in UI (technical note)
TEAM_LOGO_SLOT_TEXT_W = 10             # width technical note technical note technical note (technical note)
TEAM_LOGO_SLOT_TEXT_H = 3              # height technical note technical note technical note (line)
TEAM_TRACKER_PROC_NAMES = ("FL_2026.exe", "PES2021.exe")
# --- versiontechnical note 10technical note6 — numbertechnical note color chart (technical noteand byte istechnical note 1 technical note) ---
# address technical note data‌technical note technical noteandtechnical note user:  1436F5198 / 1436F51A0
# = technical note technical noteandtechnical note 0x140000000 + technical note  ⇒ base + 0x36F5198 / base + 0x36F51A0
TEAM_COLOR_IDX_OFFSET_HOME = 0x036F5198   # numbertechnical note color Home (uint8)
TEAM_COLOR_IDX_OFFSET_AWAY = 0x036F51A0   # numbertechnical note color Away (uint8)
TEAM_COLOR_JSON_FILENAME = "leagues_data.json"

# --- [PT v2.3.0] NEW POINTER SPECS (user spec — Cheat Engine hex notation) ---
# technical note team Home/Away (technical noteandtechnical note new — fallback chain‌technical note league/slots):
#   technical note = "FL_2026.exe"+0x03705E20 → deref → +0x98 → deref → +0x228
#   [endtechnical note] (4 byte) = Team ID Home technical note [endtechnical note+4] (4 byte) = Team ID Away
# technical note/color team from PT/teams_players_PES2021.txt technical note logo/technical note from PT/Asset.zip
# (Teams/{id}.png) — same source datatechnical note Heat Map (foldertechnical note PT technical note MyMods.py).
TEAM_ID_PTR_OFFSET = 0x03705E20
TEAM_ID_CHAIN      = (0x98, 0x228)
# player current (technical noteand for technical note technical note): "FL_2026.exe"+0x036F4270 → deref →
# +0x74 ⇒ 1 byte = Slot player in technical note teamtechnical note
PLAYER_SLOT_PTR_OFFSET = 0x036F4270
PLAYER_SLOT_CHAIN      = (0x74,)
# versiontechnical note 10technical note9 — file technical noteandtechnical note inside foldertechnical note Football_Database technical note technical note istechnical note
# if technical note technical noteandtechnical note path legacy (technical note technical note) technical note check technical note‌technical noteandtechnical note (technical notefromtechnical note).
TEAM_COLOR_DOT_PX = 13                 # technical note technical note color technical note team name (technical note)
TEAM_COLOR_DOT_H = 17                  # height technical note technical note‌technical note (technical note)


def team_json_candidates() -> List[str]:
    """pathtext text leagues_data.json to order firstandtext (versiontext 10text9):
    1) Football_Database/leagues_data.json (text text — path new)
    2) leagues_data.json text text (path legacy — textfromtext)"""
    base = _MOMENTUM_DATA_DIR
    return [os.path.join(base, TEAM_DB_DIRNAME, TEAM_COLOR_JSON_FILENAME),
            os.path.join(base, TEAM_COLOR_JSON_FILENAME)]

# --- versiontechnical note 10technical note7 — technical note automatic to technical noteandtechnical note withtechnical note (without technical noteortechnical note to totaltechnical note user) ---
AUTO_CONNECT_INTERVAL_MS = 1000        # technical note 1 second until technical note technical noteandtechnical note withtechnical note technical note technical note
AUTO_CONNECT_FIRST_DELAY_MS = 800      # firsttechnical note technical note technical note after from technical note UI
# technical note technical noteandtechnical note: N technical note technical noteandtechnical note Worker (~15ms) without passtechnical note read ⇒ technical note technical note is
ENGINE_DEAD_STREAK_LIMIT = 200

# --- versiontechnical note 10technical note7 — detection «start technical note new» from untiltechnical note (technical note → rise) ---
TRB_ZERO_T = 1.0        # untiltechnical note ≤ 1 second ⇒ «technical note technical note» (minute‌technical note technical note)
TRB_RISE_T = 2.0        # technical noteandtechnical note to withtechnical note 2 second ⇒ «start to rise technical note»
TRB_COOLDOWN_SEC = 20.0 # distancetechnical note technical note technical noteand technical noteandtechnical notefromtechnical note technical noteandtechnical note (technical note reset technical noteandtechnical note with Watchdog)


