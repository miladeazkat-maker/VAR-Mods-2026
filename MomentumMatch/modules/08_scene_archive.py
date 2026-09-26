def _scene_rgba8(a) -> Optional["np.ndarray"]:
    """آرایهٔ تصویر (float 0..1 یا uint8، RGB/RGBA) → RGBA uint8 پیوسته."""
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
    """رنگ hex/نام → (r, g, b) در 0..1 (همان تفسیر matplotlib)."""
    try:
        from matplotlib import colors as _mc
        r, g, b = _mc.to_rgb(color)
        return (float(r), float(g), float(b))
    except Exception:
        return (1.0, 1.0, 1.0)


def _scene_quad_verts(rect) -> "np.ndarray":
    """چهارگوش برای آیتم تکستچر (۲ مثلث؛ a_d=0). rect=(x0,y0,x1,y1) پنل."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    return np.array([[x0, y0, 0.0], [x0, y1, 0.0], [x1, y0, 0.0],
                     [x1, y0, 0.0], [x0, y1, 0.0], [x1, y1, 0.0]],
                    dtype=np.float32)


def _scene_fill_tri_verts(xs, ys, zero_y: float, pad: float,
                          sign: int) -> "np.ndarray":
    """نسخهٔ ۱۰٫۲۴ — fill بین منحنی و خط صفر به‌صورت مثلث‌های GPU (بند
    «Fill Area» گزارش کاربر): هر ستون = ۲ مثلث؛ a_d هر رأس = فاصلهٔ
    علامت‌دار تا «مرز واقعی منحنی» (بیرون مثبت / داخل منفی) تا Fragment
    Shader لبهٔ fill را با smoothstep نرم کند (بدون تغییر شکل داده).
    xs/ys: خروجی _tv_split_sign_segments (عبور از صفر درون‌یابی‌شده)."""
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    n = len(xs)
    if n < 2:
        return np.zeros((0, 3), dtype=np.float32)
    depths = np.abs(ys - float(zero_y))
    out = -1.0 if sign > 0 else 1.0        # جهت «بیرون» (دور از خط صفر)
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
    """باند عمودی مات (خط گل/خط عمودی) — دو نیمهٔ مستقل تا فاصلهٔ علامت‌دار
    داخل هر نیمه خطی بماند (مرز = فاصلهٔ half_w از مرکز)."""
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
    """باند افقی مات (خط صفر) — دو نیمهٔ بالا/پایین مثل _scene_vband_verts."""
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
    """دیسک (فقط fallback نبودن آیکون توپ) — بادبزن مثلثی با مرز AA."""
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
    """نسخهٔ ۱۰٫۲۶ — نرمی لبهٔ fill در مسیر GPU (پیکسل سطح)؛ هم‌ارزِ استروک
    feather مسیر matplotlib تا اورلی زنده و اسنپ‌شات «یک ظاهر» داشته باشند.
    env: TV_GPU_FILL_FEATHER (۰ = لبهٔ تیز قبلی)."""
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
    """نسخهٔ ۱۰٫۲۴ — ساخت «صحنهٔ برداری» نمودار TV در ترد Worker (خالص —
    بدون Tk/GL/matplotlib-draw). خروجی برای GPUOverlayRenderer.upload_scene:
      items: فهرست مرتبِ رسم (عین zorder قبلی) از دو نوع:
        {"kind": "tex",  rgba, size, rect, clip}   — عناصر تصویری نرم
        {"kind": "edge", verts(x,y,d), color4, clip, mode} — عناصر برداری AA
      view: (dx, dy, k) | place: {dx,dy,travel} | clip: مستطیل برش پنل
    شکل منحنی از _tv_curve_core می‌آید — «مو‌به‌مو» همان مسیر matplotlib."""
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
        pad = 1.25 / max(1e-4, k)           # حاشیهٔ AA ≈ ۱٫۲۵px سطح
        items: List[Dict[str, Any]] = []
        n_verts = 0

        # --- ۰) پس‌زمینهٔ پنل (zorder 0 — بدون برش مثل imshow قبلی) ---
        bg8 = _scene_rgba8(core["arr"])
        items.append({"kind": "tex", "rgba": bg8,
                      "size": (int(bg8.shape[1]), int(bg8.shape[0])),
                      "rect": (0.0, 0.0, W, H), "clip": False,
                      "verts": _scene_quad_verts((0.0, 0.0, W, H))})

        if core["pos_segs"] is not None:
            # --- ۱) درخشش نئون (zorder 2 — ریاضی مشترک با مسیر matplotlib) ---
            for rgba_f, _c in _tv_glow_layers(
                    core["pos_segs"], core["neg_segs"], core["W"], core["H"],
                    home_color, away_color, rect_h, zero_y,
                    near_px=core["near_px"], far_px=core["far_px"]):
                g8 = _scene_rgba8(rgba_f)
                items.append({"kind": "tex", "rgba": g8,
                              "size": (int(g8.shape[1]), int(g8.shape[0])),
                              "rect": (0.0, 0.0, W, H), "clip": True,
                              "verts": _scene_quad_verts((0.0, 0.0, W, H))})

            # --- ۲) fill دو تیم (zorder 3 — لبهٔ AA واقعی؛ بند Fill Area) ---
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

        # --- ۳) درخشش مارکرهای گل (zorder 5 — قبل از خط صفر مثل قبل) ---
        markers = core["markers"]
        rc_markers = core.get("rc_markers") or []   # نسخهٔ ۱۰٫۲۷ — کارت قرمز
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

        # --- ۴) خط صفر + خطوط عمودی (zorder 6 — مات با لبهٔ AA) ---
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

        # --- ۵) خط گل (پوستهٔ تیره zorder 8 + هستهٔ سفید zorder 9) ---
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
            # --- ۶) آیکون توپ (zorder 11) ---
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

        # --- ۶٫۵) نسخهٔ ۱۰٫۲۷ — مارکر کارت قرمز (عین گل؛ آیکون کارت به‌جای توپ) ---
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
            # آیکون کارت (zorder 11 — هم‌تراز توپ)
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

        # --- ۷) لوگو/پرچم (zorder 12 — بدون برش مثل قبل) ---
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

        # --- ۸) مُهر تاریخ/ساعت (zorder 20 — بیت‌مپ ثابت یک‌بارمصرف) ---
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
# ۲۵٫۷ — آرشیو کامل رخدادهای بازی (نسخهٔ ۱۰٫۲۴ — درخواست کاربر)
# ---------------------------------------------------------------------
# «قابلیت گرفتن خروجی کامل از رخدادهای بازی به‌صورت یک فایل (یا ZIP) +
#  خواندن همان فایل توسط کد و تبدیل آن به نمودار.»
#
#   خروجی (خودکار در پایان هر بازی + دکمهٔ دستی):
#     Momentum_Archives/match_YYYY-MM-DD_HH-MM.zip
#       ├─ match_data.json      ← کل تاریخچهٔ Momentum + مارکرهای گل +
#       │                          تیم‌ها/رنگ‌ها/تنظیمات/مقیاس/زمان‌ها
#       ├─ flag_home.png        ← لوگوی میزبان (برای بازسازی دقیق)
#       ├─ flag_away.png        ← لوگوی مهمان
#       ├─ snapshot_final.png   ← آخرین رندر نمودار (اگر در دسترس باشد)
#       └─ readme.txt           ← راهنما + دستور رندر دوباره
#
#   ورودی/بازپخش:
#     render_archive_chart(path)  →  خواندن ZIP → موتور شبه → رندر PNG
#     CLI:  python finalmomentum.py --render-archive <file.zip>
#     UI:   دکمهٔ «رندر دوبارهٔ نمودار از آرشیو» در تنظیمات اسنپ‌شات
# =====================================================================

MOMENTUM_ARCHIVE_DIRNAME = "Momentum_Archives"
MOMENTUM_ARCHIVE_FORMAT = "momentum-match-archive"
MOMENTUM_ARCHIVE_VERSION = 1


def _archive_json_safe(v):
    """تبدیل مقدار به JSON-safe: NaN/Inf → None (خواندن دوباره → NaN)."""
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
    """اسنپ‌شات اتمیکِ «همهٔ رخدادهای بازی» به‌صورت dict سازگار با JSON.
    هیچ داده‌ای خلاصه/فیلتر نمی‌شود — تاریخچهٔ کامل نمونه‌به‌نمونه."""
    with momentum._lock:
        hist = [dict(h) for h in momentum.history]
        markers = [dict(m) for m in momentum.hook_goal_markers]
        # نسخهٔ ۱۰٫۲۷ — مارکرهای کارت قرمز (getattr: سازگاری با موتورهای شبه)
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
    """نوشتن ZIP آرشیو (match_data.json + فایل‌های جانبی). خروجی: مسیر یا None."""
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
    """خروجی کامل رخدادهای بازی → ZIP در Momentum_Archives (یا out_dir).
    flag_images: {"home": arr, "away": arr} — آرایهٔ float/uint8 PNG-مانند.
    snapshot_img: PIL.Image آخرین رندر (اختیاری). خروجی: مسیر ZIP یا None."""
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
            "FL_2026 — Live Match Momentum — آرشیو کامل رخدادهای بازی\n"
            "=========================================================\n\n"
            "match_data.json   : کل تاریخچهٔ Momentum (نمونه‌به‌نمونه) + گل‌ها\n"
            "                    + تیم‌ها/رنگ‌ها/تنظیمات — منبع حقیقت.\n"
            "flag_home/away.png: لوگوی تیم‌ها (برای بازسازی دقیق نمودار).\n"
            "snapshot_final.png: آخرین رندر نمودار در لحظهٔ آرشیو (اختیاری).\n\n"
            "رندر دوبارهٔ نمودار از همین فایل:\n"
            "  python finalmomentum.py --render-archive <این فایل>.zip\n"
            "یا از داخل برنامه: ⚙ تنظیمات اسنپ‌شات ← «رندر دوبارهٔ نمودار از\n"
            "آرشیو». فایل JSON استاندارد است؛ ابزارهای تحلیل دیگر هم می‌توانند\n"
            "مستقیم بخوانندش (nan = شکاف نیمه/توقف).\n")
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
    """آرایهٔ uint8 (H,W,3|4) → بایت‌های PNG (برای جاسازی در ZIP)."""
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
    """cfg حداقلی برای رندر دوباره از آرشیو (فقط دو فیلد مؤثر در شکل)."""

    def __init__(self, data: Dict[str, Any]):
        eng = (data or {}).get("engine", {}) or {}
        self.DISPLAY_SOFT_SCALE = float(eng.get("display_soft_scale", 120.0))
        self.HISTORY_SAMPLE_INTERVAL = float(
            eng.get("history_sample_interval", 1.0))


class _ArchiveEngine:
    """موتور شبه برای render_tv_snapshot از دادهٔ آرشیو — همان سه عضوی که
    مسیر رسم می‌خواند: history / hook_goal_markers / _lock."""

    def __init__(self, data: Dict[str, Any]):
        import threading as _th
        self._lock = _th.Lock()
        hist = []
        for h in (data.get("history") or []):
            try:
                row = dict(h)
                for kk in ("game_time", "disp_time", "home", "away", "net"):
                    if kk in row and row[kk] is None:
                        row[kk] = float("nan")     # None → NaN (شکاف واقعی)
                hist.append(row)
            except Exception:
                continue
        self.history = hist
        self.hook_goal_markers = list(data.get("goal_markers") or [])
        # نسخهٔ ۱۰٫۲۷ — مارکرهای کارت قرمز (آرشیوهای قدیمی: خالی)
        self.red_card_markers = list(data.get("red_card_markers") or [])


def load_match_archive(archive_path: str) -> Optional[Dict[str, Any]]:
    """خواندن آرشیو (ZIP یا JSON خام) → {"data": match_data, "flags": {...}}.
    پرچم‌ها از PNGهای داخل ZIP به آرایهٔ RGBA uint8 تبدیل می‌شوند."""
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
            # فایل بدون مُهر فرمت — اگر history داشت بپذیر (سازگاری رو به جلو)
            if "history" not in data:
                return None
        return {"data": data, "flags": flags}
    except Exception:
        return None


def render_archive_chart(archive_path: str,
                         out_path: Optional[str] = None) -> Optional[str]:
    """«کد بتواند فایل موردنظر را بخواند و به نمودار تبدیل کند» (کاربر):
    آرشیو ZIP/JSON → موتور شبه → رندر کامل همان خط تولید نمودار TV → PNG.
    خروجی: مسیر PNG ساخته‌شده یا None."""
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
    """ماشین حالتِ اسنپ‌شات (خالص — بدون بازی/UI، کاملاً قابل تست):
      * میان‌بازی: کپچر در «دقیقهٔ هدف − ۱» و نمایش در «دقیقهٔ هدف»؛
        اگر ساعت از دقیقهٔ هدف رد شود و هنوز کپچری نبود → کپچر+نمایش فوری؛
      * پایان بازی: توقف پیوسته ≥۱۲s در >۹۰′ و >۱۲۰′ (سطح‌های مستقل)؛
        اگر بعد از اولین نمایش بازی از سر گرفته شود (جشن گل در ۹۰+)،
        یک‌بار مجدداً مسلح می‌شود تا سوت واقعی پایان هم نمایش بگیرد
        (حداکثر ۲ نمایش در هر سطح + خنک‌کنندهٔ ۴۵ ثانیه)؛
      * ثبت ساعتِ «شروع بازی» برای مُهر تاریخ/زمان."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None):
        self.s: Dict[str, Any] = dict(TV_SNAP_DEFAULTS
                                      if settings is None else settings)
        self.match_start_wall: Optional[float] = None
        self._reset_state()

    # --- وضعیت داخلی ---
    @staticmethod
    def _new_mid_state() -> Dict[str, Any]:
        """v10.28 (پورت v1.3 از 2017) — چرخهٔ عمر تراکنشی هر کلید میان‌بازی:
        show_state: None → "requested" (action صادر شد، در انتظار تأیید)
                          → "visible" (تأیید شد — consumed)
                          → "failed" (شکست/مهلت گذشت — منتظر تلاش مجدد)
                          → "abandoned" (سقف تلاش‌ها — رها شد)
        مصرف نهایی (shown=True) فقط با confirm_shown انجام می‌شود."""
        return {"cap": False, "shown": False, "pre": False,
                "show_state": None, "show_req_wall": None,
                "retries": 0, "retry_after_wall": None,
                "last_fail": ""}

    @staticmethod
    def _new_end_state() -> Dict[str, Any]:
        # v10.28 — pend: ساعت wall صدور show_end که هنوز تأیید نشده؛
        # fails: تعداد شکست‌های پردازش‌شدهٔ این سطح (سقف TV_SNAP_END_FAIL_MAX)
        return {"stop_since": None, "shows": 0,
                "rearm_used": False, "last_show_wall": None,
                "pre": False,          # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری انجام شد
                "pend": None, "fails": 0}

    def _reset_state(self):
        # نسخهٔ ۱۰٫۱۵ — "pre" = پیش‌بارگذاری (رندر + پنجرهٔ زیرِ صفحه) انجام شد
        self.mid = {k: self._new_mid_state() for k in TV_SNAP_KEYS}
        self.end = {"end90": self._new_end_state(),
                    "end120": self._new_end_state()}

    def reset_match(self, now_wall: Optional[float] = None):
        """شروع دست جدید — همهٔ وضعیت‌ها صفر (تایمر به ۰۰:۰۰ ریست شده)."""
        self._reset_state()
        self.match_start_wall = None

    def reset_preload_flags(self):
        """نسخهٔ ۱۰٫۱۶ — با تغییر پیچ‌های نمایش (نرمی لبه/نئون)، پیش‌بارگذاری‌های
        «مصرف‌شده ولی هنوز نمایش‌داده‌نشده» دوباره مسلح می‌شوند تا رندر با
        تنظیمات جدید از نو ساخته شود (نمایش‌های انجام‌شده دست‌نخورده)."""
        for st in self.mid.values():
            if not st["shown"]:
                st["pre"] = False
        for st in self.end.values():
            if st["shows"] < 2:
                st["pre"] = False

    def target_minute(self, key: str) -> int:
        return snap_clamp_minute(key, self.s.get(f"{key}_minute"))

    # =============================================================
    # v10.28 — API تراکنشی نمایش (پورت v1.3 از نسخهٔ 2017؛ خالص — فقط از
    # ترد Worker صدا زده شود؛ رویدادهای confirm/fail از سمت UI از طریق
    # صف رویداد App به همین‌جا می‌رسند — بخش _snap_drain_show_events)
    # =============================================================
    def confirm_shown(self, key: str) -> bool:
        """تأیید رسیدن Snapshot به SHOWING (پذیرش renderer.show) — فقط در همین
        حالت مصرف نهایی انجام می‌شود؛ خروجی False یعنی تأیید بی‌ربط/دیرهنگام."""
        st = self.mid.get(key)
        if not st or st.get("show_state") != "requested":
            return False
        st["show_state"] = "visible"
        st["shown"] = True
        st["retry_after_wall"] = None
        return True

    def fail_show(self, key: str, now_wall: Optional[float] = None,
                  reason: str = "") -> bool:
        """شکست dispatch/UI برای این کلید → مسلح‌سازی مجدد برای تلاش بعدی
        (پس از TV_SNAP_SHOW_RETRY_BACKOFF_SEC) — نمایش هنوز مصرف نشده."""
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
        """شمارهٔ تلاش جاری (۱ = اولین show؛ n>1 = تلاش مجدد)."""
        st = self.mid.get(key)
        if not st:
            return 0
        return int(st.get("retries", 0)) + (1 if st.get("show_state")
                                             in ("requested", "failed") else 0)

    def confirm_show_end(self) -> bool:
        """تأیید نمایش پایان (کلید App «end») — pend هر دو سطح پاک می‌شود
        (در هر لحظه حداکثر یک show_end در پرواز است)."""
        hit = False
        for lvl in ("end90", "end120"):
            st = self.end.get(lvl)
            if st is not None and st.get("pend") is not None:
                st["pend"] = None
                hit = True
        return hit

    def fail_show_end(self, lvl: str, now_wall: Optional[float] = None,
                      reason: str = "") -> bool:
        """شکست نمایش پایان → «shows» پس گرفته می‌شود و ماشین حالت توقف
        (تأیید ۱۲ ثانیه‌ای + Cooldown) دوباره مسلح می‌شود تا نمایش پایانی
        بدون ری‌استارت بازی دوباره صادر شود."""
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
        """یک تیکWorker — خروجی: فهرست اقدام‌ها:
             ("capture", key)  → رندر PNG موقت (دقیقهٔ هدف − ۱)
             ("show", key)     → نمایش روی صفحه (دقیقهٔ هدف)
             ("show_end", lvl) → نمایش پایان بازی (end90/end120)"""
        acts: List[Tuple[str, str]] = []
        if total_t is None:
            return acts
        try:
            t = float(total_t)
        except (TypeError, ValueError):
            return acts
        now = float(now_wall) if now_wall is not None else time.time()
        if self.match_start_wall is None:
            self.match_start_wall = now          # ثبت ساعت «شروع» بازی
        try:
            half = int(half_number) if half_number is not None else 1
        except (TypeError, ValueError):
            half = 1

        # ---------- میان‌بازی (نیمهٔ اول / دوم / وقت اضافه) ----------
        # نسخهٔ ۱۰٫۱۵ — «et» در هر دو نیمهٔ وقت اضافه (half ۳/۴) معتبر است؛
        # «۲» برای سازگاری با حالتی که فاز ET به هر دلیل مسلح نشده باشد.
        for key, need_half in (("h1", (1,)), ("h2", (2,)), ("et", (2, 3, 4))):
            if not self.s.get(f"{key}_enabled"):
                continue
            if half not in need_half:
                continue
            st = self.mid[key]
            if st["shown"]:
                continue
            # --- v10.28 — مدیریت چرخهٔ تراکنشی (قبل از هر چیز) ---
            _ss = st.get("show_state")
            if _ss == "requested":
                # مهلت تأیید گذشت؟ (dispatch گم‌شده/UI قفل — ریشهٔ باگ
                # «۴۳/۸۵ در 2026 نمایش داده نشد و دیگر تلاش نشد»)
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
                        # سقف تلاش‌ها — رها می‌شود (shown=True تا چرخه نایستد)
                        st["show_state"] = "abandoned"
                        st["shown"] = True
                        acts.append(("show_abandoned", key))
                    else:
                        st["retries"] = int(st.get("retries", 0)) + 1
                        st["show_state"] = "requested"
                        st["show_req_wall"] = now
                        acts.append(("show", key))     # تلاش مجدد
                # هنوز داخل Backoff → هیچ action جدیدی نه
            tgt_min = self.target_minute(key)
            # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری: در پنجرهٔ ۲ ثانیهٔ «قبل از» لحظهٔ
            # نمایش، رندر + ساخت پنجرهٔ زیرِ صفحه (ورود بدون لگ — کاربر:
            # «خارج از کادر نگه دار تا موقع ورود مجبور به لود نشه»)
            if (not st["pre"]) and \
                    (tgt_min * 60.0 - TV_SNAP_PRELOAD_LEAD_SEC) <= t < tgt_min * 60.0:
                st["pre"] = True
                acts.append(("preload", key))
            if (not st["cap"]) and t >= (tgt_min - 1) * 60.0:
                st["cap"] = True
                acts.append(("capture", key))
            if t >= tgt_min * 60.0 and st.get("show_state") is None:
                if not st["cap"]:            # ساعت از هدف رد شده بود → فوری
                    st["cap"] = True
                    acts.append(("capture", key))
                # v10.28 — فقط «درخواست» ثبت می‌شود؛ مصرف نهایی با تأیید
                st["show_state"] = "requested"
                st["show_req_wall"] = now
                acts.append(("show", key))

        # ---------- پایان بازی (>۹۰′ و >۱۲۰′) ----------
        # سطح ۱۲۰ اول ارزیابی می‌شود؛ اگر نمایش ۱۲۰+ افتاد، سطح ۹۰+ برای
        # «همین توقف» بی‌معنی است و کامل مصرف می‌شود (جلوگیری از نمایش دوبل)
        if self.s.get("end_enabled"):
            for lvl, min_t in (("end120", 120 * 60.0), ("end90", 90 * 60.0)):
                st = self.end[lvl]
                # --- v10.28 — مهلت تأیید show_end قبلی (dispatch گم‌شده) ---
                if st.get("pend") is not None:
                    if now - st["pend"] > TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC \
                            and int(st.get("fails", 0)) < TV_SNAP_END_FAIL_MAX:
                        # پس گرفتن shows + مسلح‌سازی دوبارهٔ ماشین توقف
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
                    st["pre"] = False        # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری باطل
                    # جشن گل در ۹۰+ نمایش را مصرف کرده و بازی ادامه یافت →
                    # برای توقف واقعیِ پایان مجدداً مسلح می‌شود (فقط یک‌بار)
                    if st["shows"] == 1 and not st["rearm_used"]:
                        st["shows"] = 0
                        st["rearm_used"] = True
                    continue
                if st["stop_since"] is None:
                    st["stop_since"] = now
                # نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاریِ پایان: در پنجرهٔ ~۲ ثانیهٔ
                # «قبل از» تأیید توقفِ پایان (سپر رندر در لحظهٔ نمایش)
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
                st["pend"] = now            # v10.28 — در انتظار تأیید
                acts.append(("show_end", lvl))
                if lvl == "end120":
                    # نمایش پایانِ ۱۲۰+ کافی است — سطح ۹۰+ «کامل» مصرف
                    # می‌شود (پورت v1.2.2 از 2017 — جلوگیری از نمایش دوبلِ
                    # سوت پایانی وقت‌اضافه)
                    st90 = self.end["end90"]
                    st90["shows"] = 2
                    st90["last_show_wall"] = now
                    st90["stop_since"] = None
                    if st90.get("pend") is not None:
                        # v10.28 — show90 در پرواز نبود که دوبل شود؛ pend او
                        # هم پاک می‌شود (تأیید دیرهنگام دیگر اثری ندارد)
                        st90["pend"] = None
        return acts


# --- نسخهٔ ۱۰٫۲۲ — Figure/Canvas «ماندگار» رندر Snapshot (اولویت ۴ کاربر):
# به‌جای ساخت Figure/axes/آرتیست از صفر در هر رندر (~۵۸۰ms)، همان Figure
# دائمی reuse می‌شود؛ draw_tv_momentum خودش ax.clear() می‌کند → خروجی
# پیکسل‌به‌پیکسل مثل قبل است و فقط هزینهٔ ساخت آبجکت‌ها حذف می‌شود.
# قفل: رندر از ترد Worker (capture/preload/end) و ترد snap-retune (ریل‌تایم
# پیچ‌ها) فراخوانی می‌شود — هم‌پوشانی نادر با نوبت‌بندی Lock حل می‌شود.
_SNAP_RENDER_CACHE: Dict[str, Any] = {"fig": None, "canvas": None,
                                      "key": None, "lock": threading.Lock()}


def render_tv_snapshot(momentum, cfg, disp_value, bg_kind: str,
                       home_color: str, away_color: str,
                       home_flag_arr, away_flag_arr,
                       timestamp_text: Optional[str] = None,
                       out_path: Optional[str] = None,
                       transparent: bool = True):
    """رندر آفلاین نمودار TV روی بوم Agg مستقل (بدون دست‌زدن به تب):
    خروجی PIL.Image (RGBA). با transparent=True پس‌زمینهٔ شفاف می‌ماند —
    کانال آلفای تصویر اصلی حفظ می‌شود تا هنگام نمایش روی بازی، تصویر
    بازی از زیرش دیده شود. ابعاد خروجی دقیقاً برابر تصویر پس‌زمینه است
    (half/full: 1608×978 — extra: 2034×978).
    نسخهٔ ۱۰٫۲۲ — Figure/Canvas ماندگار: Figure فقط یک‌بار برای هر
    (W,H,dpi) ساخته می‌شود و در رندرهای بعدی reuse می‌شود (ax.clear()
    داخل draw_tv_momentum محتوای قبلی را کامل پاک می‌کند → خروجی
    بدون تغییر؛ این عملیات هرگز در مسیر Show نیست — فقط Worker)."""
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    bg = tv_load_background(bg_kind)
    if bg is None:
        return None
    W, H = int(bg["W"]), int(bg["H"])
    dpi = 100.0
    # نسخهٔ ۱۰٫۲۵ — ابرنمونه‌گیری رندر اسنپ‌شات: بوم SS برابر بزرگ‌تر رسم
    # می‌شود و آخر کار با میانگین Box به اندازهٔ طراحی فرود می‌آید. همهٔ
    # اندازه‌ها (خط‌ها/متن/توپ/لوگو) بر حسب «پیکسل طراحی» تعریف شده‌اند و
    # با dpi مقیاس می‌شوند ⇒ بعد از فرود، دقیقاً همان اندازهٔ قبل.
    # رندر در ترد Worker و ~۱ دقیقه قبل از نمایش انجام می‌شود ⇒ هزینهٔ
    # محاسباتی هرگز در مسیر Show نیست.
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
    # نسخهٔ ۱۰٫۲۵ — فرود ابرنمونه‌ها: میانگین Box (AA واقعی، بدون رینگ لبه)
    if ss > 1 and buf.shape[0] >= H and buf.shape[1] >= W:
        try:
            from PIL import Image as _ImgSS
            _im_ss = _ImgSS.fromarray(buf)
            _im_ss = _im_ss.resize((W, H), _ImgSS.Resampling.BOX)
            buf = np.asarray(_im_ss).copy()
        except Exception:
            pass
    # نرمال‌سازی ابعاد: محاسبهٔ float اندازهٔ بوم را ۱px کوچک‌تر می‌کند
    # (16.08×100 → 1607) — با پد شفاف دقیقاً به ابعاد تصویر پس‌زمینه می‌رسیم
    if buf.shape[0] != H or buf.shape[1] != W:
        fixed = np.zeros((H, W, 4), dtype=np.uint8)
        hh = min(H, buf.shape[0])
        ww = min(W, buf.shape[1])
        fixed[:hh, :ww] = buf[:hh, :ww]
        buf = fixed
    # نسخهٔ ۱۰٫۱۸ — پارامتر mode حذف شد (DeprecationWarning Pillow 13):
    # fromarray از شکل آرایه (H,W,4) خودش RGBA را تشخیص می‌دهد
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
    """آماده‌سازی آرایهٔ BGRA با آلفای پیش‌ضرب‌شده برای UpdateLayeredWindow."""
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
    """نمایش پنجرهٔ Tk با آلفای پیکسلی واقعی روی ویندوز (UpdateLayeredWindow):
    پنجره topmost، کلیک‌گذر (WS_EX_TRANSPARENT) و بدون گرفتن فوکوس
    (WS_EX_NOACTIVATE) — مناسب افتادن روی تصویر بازی.
    نسخهٔ ۱۰٫۱۶ — arr آرایهٔ BGRA پیش‌ضرب‌شدهٔ آماده (از ترد Worker) است؛
    در این حالت هیچ پردازش پیکسلی در UI-Thread انجام نمی‌شود.
    نسخهٔ ۱۰٫۱۸ — trace (SnapShowTrace): زیرمرحله‌های حساس (Premultiply،
    CreateDIBSection، Upload به UpdateLayeredWindow) جداگانه زمان‌گیری
    می‌شوند تا مظنون اصلی لگ (ULW/DWM) دقیقاً مشخص شود (بند ۶ کاربر).
    در نبود ویندوز/خطا → False (فراخوان fallback ساده می‌کند)."""
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
    """جابه‌جایی پنجرهٔ لایه‌ای «بدون» بازپخش بیت‌مپ (SetWindowPos) — نسخهٔ
    ۱۰٫۱۳: حرکت روان انیمیشن ورود/خروج با هزینهٔ کم در هر فریم.
    نسخهٔ ۱۰٫۱۸ (بند ۷ کاربر): در هر فریم فقط Position عوض می‌شود —
    HWND_TOPMOST و SWP_SHOWWINDOW حذف شدند (Topmost یک‌بار در لحظهٔ ساخت
    تنظیم می‌شود و Show هم یک‌بار انجام شده است؛ تغییر Z-order/Show-state
    در هر فریم، بار سنگین Window Management و DWM می‌سازد).
    در نبود ویندوز/خطا → False (فراخوان fallback با geometry تضمین می‌شود).
    نسخهٔ ۱۰٫۲۰ (بند ۶ کاربر): مدت + پرچم‌های واقعی در تلمتری _SWP_LAST."""
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
        _t0 = time.perf_counter()              # نسخهٔ ۱۰٫۲۰ — بند ۶
        _ok = bool(user32.SetWindowPos(hwnd, 0, int(x), int(y),
                                       0, 0, _fl))
        try:                                   # تلمتری — بدون لاگ اسپم
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
    """نسخهٔ ۱۰٫۱۶ — hwnd خام پنجرهٔ Tk (یک‌بار در UI-Thread حل می‌شود تا
    ترد انیمیشن بدون هیچ فراخوانی Tk کار کند)."""
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


# نسخهٔ ۱۰٫۲۰ — تلمتری آخرین فراخوانی SetWindowPos حرکتی (بند ۶ کاربر):
# win32_move_hwnd / win32_move_window مدت (perf_counter) + پرچم‌های واقعی +
# نتیجه را این‌جا می‌نویسند؛ ترد انیمیشن بعد از هر فریم آن را می‌خواند و در
# بلوک [SNAPSHOT ANIMATION DEBUG] ثبت می‌کند. بدون لاگ مستقیم (بدون اسپم)؛
# تغییر امضای توابع هم لازم نشد.
_SWP_LAST = {"hwnd": None, "x": 0, "y": 0, "flags": 0, "dur_ms": 0.0,
             "ok": False, "src": "-"}


def _swp_flags_text(flags: int) -> str:
    """نسخهٔ ۱۰٫۲۰ — رشتهٔ خوانا برای پرچم‌های SetWindowPos (بند ۷ کاربر)."""
    names = ((0x0001, "NOSIZE"), (0x0002, "NOMOVE"), (0x0004, "NOZORDER"),
             (0x0008, "NOREDRAW"), (0x0010, "NOACTIVATE"),
             (0x0020, "DRAWFRAME"), (0x0040, "FRAMECHANGED"),
             (0x0080, "SHOWWINDOW"), (0x0100, "HIDEWINDOW"),
             (0x0200, "NOCOPYBITS"), (0x4000, "ASYNCWINDOWPOS"))
    on = [nm for bit, nm in names if flags & bit]
    return f"0x{int(flags):04X} (" + "|".join(on) + ")" if on \
        else f"0x{int(flags):04X}"


# --- نسخهٔ ۱۰٫۲۱ — تست ۵ کاربر: تلمتری کامل ویندوزی هر SetWindowPos ---
# user32 با use_last_error=True تا GetLastError پس از فراخوانی دقیق باشد
# (ctypes آن را ذخیره می‌کند و ctypes.get_last_error() برمی‌گرداند).
_U32_LE = None
if os.name == "nt":
    try:
        _U32_LE = ctypes.WinDLL("user32", use_last_error=True)
    except Exception:
        _U32_LE = None

# آخرین رکورد تلمتری _win32_swp_debug (ترد انیمیشن بعد از هر حرکت آن را
# کپی می‌کند و در بلوک [SNAPSHOT ANIMATION DEBUG] چاپ می‌شود).
_SWP_LAST_EXTRA = {}

_EX_BITS = ((0x00000008, "TOPMOST"), (0x00080000, "LAYERED"),
            (0x00000020, "TRANSPARENT"), (0x08000000, "NOACTIVATE"))


def _snap_exstyle_text(ex) -> str:
    """نسخهٔ ۱۰٫۲۱ — متن خوانای بیت‌های ex-style (تست ۵ کاربر)."""
    try:
        if ex is None:
            return "?"
        on = [nm for bit, nm in _EX_BITS if int(ex) & bit]
        return "|".join(on) if on else "none"
    except Exception:
        return "?"


def _snap_ui_stack_sample(max_frames: int = 10) -> str:
    """نسخهٔ ۱۰٫۲۱ — نمونهٔ پشتهٔ Python ترد Main/UI از ترد دیگر
    (sys._current_frames) — وقتی SetWindowPos ترد انیمیشن بلوک می‌شود،
    این نمونه نشان می‌دهد UI-Thread دقیقاً چه کدی اجرا می‌کرده
    (پاسخ سؤال D کاربر: چرا ورود 150ms و خروج 1ms؟)."""
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
    """نسخهٔ ۱۰٫۲۱ — تست ۵ کاربر: «همان» SetWindowPos حرکتی (flags ثابت
    0x0015 = NOSIZE|NOZORDER|NOACTIVATE) را با تلمتری کامل ویندوزی اجرا
    می‌کند و رکورد را در _SWP_LAST_EXTRA می‌گذارد و برمی‌گرداند:
      * old x/y (GetWindowRect قبل) / مکان درخواستی / y واقعی بعد از حرکت
      * HWND + native Thread ID + Thread priority
      * flags + return value + GetLastError
      * قبل و بعد: GetForegroundWindow / IsWindowVisible / بیت‌های
        WS_EX_TOPMOST | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE
      * اگر مدت > TV_SNAP_UI_STACK_ON_SLOW_MS → نمونهٔ پشتهٔ UI-Thread
    فقط وقتی TV_SNAP_SWP_WIN_DEBUG فعال است؛ در نبود ویندوز/خطا → None
    (فراخوان به مسیر سادهٔ قبلی برمی‌گردد — رفتار عادی دست‌نخورده)."""
    if os.name != "nt" or not hwnd or not TV_SNAP_SWP_WIN_DEBUG:
        return None
    try:
        from ctypes import wintypes as _wt
        u = _U32_LE if _U32_LE is not None else ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        hwnd = int(hwnd)
        GWL_EXSTYLE = -20
        ex_mask = 0x00000008 | 0x00080000 | 0x00000020 | 0x08000000
        # --- وضعیت «قبل» (خطا → None/صفر — هیچ‌کدام مسیر حرکت را عوض
        # نمی‌کنند؛ SetWindowPos خودش همیشه اجرا می‌شود) ---
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
        # --- خودِ فراخوانی (اگر خودش خطا دهد → None تا مسیر ساده ادامه دهد) ---
        try:
            t0 = time.perf_counter()
            ok = bool(u.SetWindowPos(hwnd, 0, int(x), int(y), 0, 0, flags))
            err = int(ctypes.get_last_error()) if _U32_LE is not None else -1
            dur = (time.perf_counter() - t0) * 1000.0
        except Exception:
            return None
        # --- وضعیت «بعد» ---
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
    """نسخهٔ ۱۰٫۲۱ — فهرست فریم‌های کند SetWindowPos (خلاصهٔ تست ۵)."""
    try:
        items = [(int(r.get("no", 0)), float(r.get("swp_ms", 0.0)))
                 for r in recs if not r.get("skipped")]
        slow = [f"#{no:02d}={d:.1f}ms" for no, d in items if d > thr_ms]
        return ", ".join(slow)
    except Exception:
        return ""


def _anim_flags_policy_text(recs) -> str:
    """نسخهٔ ۱۰٫۲۱ — تست ۴ کاربر: راستی‌آزمایی خودکار پرچم‌ها — همهٔ فریم‌های
    انیمیشن باید دقیقاً 0x0015 (NOSIZE|NOZORDER|NOACTIVATE) باشند؛ هیچ
    HWND_TOPMOST / SWP_SHOWWINDOW / تغییر Z-order / UpdateLayeredWindow /
    opacity / resize / بازسازی پنجره در حلقه مجاز نیست (Topmost/Show فقط
    یک‌بار در ساخت پنجره انجام شده‌اند)."""
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
    """نسخهٔ ۱۰٫۱۶ — جابه‌جایی با hwnd خام و «بدون هیچ فراخوانی Tk»:
    ترد انیمیشن اختصاصی با این تابع، فریم‌ها را مستقل از صف UI اعمال
    می‌کند (رفع لگ ورود اسنپ‌شات — شرط کاربر: سپردن به ترد جدا).
    نسخهٔ ۱۰٫۱۸ (بند ۷ کاربر): فقط حرکت — SWP_NOZORDER | SWP_NOACTIVATE؛
    بدون HWND_TOPMOST و بدون SWP_SHOWWINDOW (Topmost/Show یک‌بار در
    ساخت پنجره انجام شده‌اند؛ «Topmost وضعیت پنجره است، نه عملِ هر فریم»).
    نسخهٔ ۱۰٫۲۰ (بند ۶ کاربر): t0/t1 با perf_counter — مدت + پرچم‌های
    واقعی + نتیجه در تلمتری _SWP_LAST ثبت می‌شود (بند ۷: باید همیشه
    0x0015 = NOSIZE|NOZORDER|NOACTIVATE باشد).
    نسخهٔ ۱۰٫۲۱ (تست ۵ کاربر): وقتی TV_SNAP_SWP_WIN_DEBUG فعال است، همین
    فراخوانی از مسیر _win32_swp_debug می‌رود (همان SetWindowPos با همان
    0x0015 + old/new x,y + وضعیت قبل/بعد + GetLastError + نمونهٔ پشتهٔ
    UI در کندی)؛ رکورد در _SWP_LAST_EXTRA می‌ماند تا ترد انیمیشن آن را
    در بلوک [SNAPSHOT ANIMATION DEBUG] چاپ کند. خودِ فراخوانی و پرچم‌ها
    هیچ تغییری نکرده‌اند."""
    if os.name != "nt" or not hwnd:
        return False
    # --- نسخهٔ ۱۰٫۲۱ — تست ۵: مسیر تلمتری کامل (همان حرکت، دادهٔ بیشتر) ---
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
        _t0 = time.perf_counter()              # بند ۶: قبل از SetWindowPos
        _ok = bool(user32.SetWindowPos(int(hwnd), 0, int(x),
                                       int(y), 0, 0, _fl))
        try:                                   # بند ۶: بعد از SetWindowPos
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
    """نسخهٔ ۱۰٫۱۷ — y واقعی (بالای مستطیل) پنجره از خود ویندوز
    (GetWindowRect) — برای «واچ‌داگ ورود»: تشخیص اینکه پنجره هنوز زیرِ
    صفحه گیر کرده است یا نه. در نبود ویندوز/خطا → None."""
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
# ۲۶. رابط کاربری نهایی (Main Application — Tkinter + Matplotlib)
# ---------------------------------------------------------------------
# Tabها: 📈 Live Match Momentum | 📋 Event Timeline | 📊 Possession Sequences
#        🎯 Event / Threat Details | 🧪 Momentum Debug
# Header: اتصال، وضعیت بازی، Match Time (زنده)، Possession، Home/Away
# =====================================================================
# =====================================================================
# ۲۶ — ردیاب مستقل هویت تیم‌ها: لوگو/پرچم میزبان و مهمان (نسخه ۱۰٫۵)
# ---------------------------------------------------------------------
# منطق عیناً از ابزار مستقل «Team Tracker» کاربر منتقل شده است:
#   * اتصال ۱۰۰٪ مستقل از GameEngine اصلی و دکمهٔ «اتصال به پروسه بازی»؛
#     هندل read-only خودش را باز می‌کند و هیچ نوشتن/هوکی روی پروسهٔ بازی
#     انجام نمی‌دهد (فقط ReadProcessMemory).
#   * از لحظهٔ اجرای برنامه هر ۱ ثانیه تلاش به اتصال می‌کند؛ بعد از اتصال
#     موفق دیگر هیچ تلاش اتصالی انجام نمی‌شود (نسخهٔ ۱۰٫۶: از همان لحظه
#     خواندن اسلات‌ها «ریل‌تایم» می‌شود — هر ۵۰ms مثل حلقهٔ realtime_loop
#     ابزار اصلی؛ اگر پروسه بسته شود، دوباره به حالت «تلاش هر ۱ ثانیه»
#     برمی‌گردد. اسکن سنگین پروسه فقط وقتی انجام می‌شود که یا وصل نیستیم
#     یا خواندن حافظه شکست خورده — نه در هر تیکِ متصل).
#   * [PT v2.3.1] تشخیص تیم فقط وقتی اجرا می‌شود که بایت وضعیت منو
#     (base+0x36F9AE0) = ۹ باشد (قبلاً ۱۰۰ بود) — در «هر دو» مسیرِ PT و
#     قدیمی؛ بقیهٔ وضعیت‌ها یعنی قفل روی آخرین انتخاب معتبر — مثل ابزار اصلی.
#   * نسخهٔ ۱۰٫۶ — رنگ نمودار: دو بایت استاتیک ۱ بیتی شمارهٔ رنگ هر تیم
#     (مطلق: 0x1436F5198 میزبان / 0x1436F51A0 مهمان = base+آفست) در هر تیکِ
#     متصل خوانده می‌شود و TeamColorResolver رنگ fill نمودار را از
#     leagues_data.json (کنار اسکریپت) برمی‌دارد — بخش ۲۶-ب.
# =====================================================================
TEAM_TRACKER_INTERVAL_MS = 1000        # تلاش اتصال (تا وصل‌شدن): هر ۱ ثانیه
TEAM_LIVE_INTERVAL_MS = 50             # بعد از اتصال: خواندن ریل‌تایم اسلات‌ها (مثل ابزار اصلی)
TEAM_PROCESS_ACCESS = 0x0010 | 0x0400  # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION
TEAM_MENU_STATE_OFFSET = 0x036F9AE0    # بایت وضعیت منو (خواندن مستقیم base+آفست — عین بقیهٔ آفست‌های استاتیک)
# [PT v2.3.1] شرط اجرای تشخیص تیم: فقط وقتی بایت منو = ۹ باشد (قبلاً ۱۰۰ بود).
# خواندنِ این بایت با همان _read_u8 انجام می‌شود که بقیهٔ مقادیر پوینتری را می‌خوانند.
TEAM_MENU_DETECT_VALUE = 9
TEAM_DB_DIRNAME = "Football_Database"  # پوشهٔ تصاویر کنار اسکریپت
TEAM_SLOT_COUNT = 37                   # تعداد اسلات‌های هر تیم (مثل ابزار اصلی)
TEAM_SLOT_STRIDE = 112                 # فاصلهٔ اسلات‌ها (بایت)
TEAM_LOGO_SLOT_PX = (96, 96)           # اندازهٔ اسلات لوگو در UI (پیکسل)
TEAM_LOGO_SLOT_TEXT_W = 10             # عرض حالت متنی اسلات (کاراکتر)
TEAM_LOGO_SLOT_TEXT_H = 3              # ارتفاع حالت متنی اسلات (خط)
TEAM_TRACKER_PROC_NAMES = ("FL_2026.exe", "PES2021.exe")
# --- نسخهٔ ۱۰٫۶ — شمارهٔ رنگ نمودار (دو بایت استاتیک ۱ بیتی) ---
# آدرس مطلق داده‌شده توسط کاربر:  1436F5198 / 1436F51A0
# = پایهٔ ماژول 0x140000000 + آفست  ⇒ base + 0x36F5198 / base + 0x36F51A0
TEAM_COLOR_IDX_OFFSET_HOME = 0x036F5198   # شمارهٔ رنگ میزبان (uint8)
TEAM_COLOR_IDX_OFFSET_AWAY = 0x036F51A0   # شمارهٔ رنگ مهمان (uint8)
TEAM_COLOR_JSON_FILENAME = "leagues_data.json"

# --- [PT v2.3.0] NEW POINTER SPECS (user spec — Cheat Engine hex notation) ---
# شناسهٔ تیم میزبان/مهمان (روش جدید — جایگزین زنجیره‌های league/slots):
#   پایه = "FL_2026.exe"+0x03705E20 → deref → +0x98 → deref → +0x228
#   [پایانی] (۴ بایت) = Team ID میزبان ؛ [پایانی+4] (۴ بایت) = Team ID مهمان
# نام/رنگ تیم از PT/teams_players_PES2021.txt ؛ لوگو/پرچم از PT/Asset.zip
# (Teams/{id}.png) — همان منبع دادهٔ Heat Map (پوشهٔ PT کنار MyMods.py).
TEAM_ID_PTR_OFFSET = 0x03705E20
TEAM_ID_CHAIN      = (0x98, 0x228)
# بازیکن جاری (رزرو برای مصرف آینده): "FL_2026.exe"+0x036F4270 → deref →
# +0x74 ⇒ ۱ بایت = Slot بازیکن در لیست تیمش
PLAYER_SLOT_PTR_OFFSET = 0x036F4270
PLAYER_SLOT_CHAIN      = (0x74,)
# نسخهٔ ۱۰٫۹ — فایل جیسون داخل پوشهٔ Football_Database کنار اسکریپت است؛
# اگر آنجا نبود، مسیر قدیمی (کنار اسکریپت) هم بررسی می‌شود (سازگاری).
TEAM_COLOR_DOT_PX = 13                 # قطر دایرهٔ رنگ کنار نام تیم (پیکسل)
TEAM_COLOR_DOT_H = 17                  # ارتفاع ناحیهٔ دایره‌ها (پیکسل)


def team_json_candidates() -> List[str]:
    """مسیرهای کاندید leagues_data.json به ترتیب اولویت (نسخهٔ ۱۰٫۹):
    ۱) Football_Database/leagues_data.json (کنار اسکریپت — مسیر جدید)
    ۲) leagues_data.json کنار اسکریپت (مسیر قدیمی — سازگاری)"""
    base = os.path.dirname(os.path.abspath(__file__))
    return [os.path.join(base, TEAM_DB_DIRNAME, TEAM_COLOR_JSON_FILENAME),
            os.path.join(base, TEAM_COLOR_JSON_FILENAME)]

# --- نسخهٔ ۱۰٫۷ — اتصال خودکار به پروسهٔ بازی (بدون نیاز به کلیک کاربر) ---
AUTO_CONNECT_INTERVAL_MS = 1000        # هر ۱ ثانیه تا دیدن پروسهٔ بازی تلاش کن
AUTO_CONNECT_FIRST_DELAY_MS = 800      # اولین تلاش کمی بعد از ساخت UI
# مرگ پروسه: N تیک پیوستهٔ Worker (~۱۵ms) بدون پاسخ خواندن ⇒ اتصال قطع است
ENGINE_DEAD_STREAK_LIMIT = 200

# --- نسخهٔ ۱۰٫۷ — تشخیص «شروع دست جدید» از تایمر (صفر → بالا رفتن) ---
TRB_ZERO_T = 1.0        # تایمر ≤ ۱ ثانیه ⇒ «صفر شده» (دقیقه‌شمار صفر)
TRB_RISE_T = 2.0        # عبور به بالای ۲ ثانیه ⇒ «شروع به بالا رفتن کرد»
TRB_COOLDOWN_SEC = 20.0 # فاصلهٔ حداقلی دو نوسازی متوالی (ضد ریست دوبله با Watchdog)


