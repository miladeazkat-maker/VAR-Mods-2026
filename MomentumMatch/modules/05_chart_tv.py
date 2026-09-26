def _fmt_clock(sec: float) -> str:
    m, s = divmod(int(round(max(0.0, sec))), 60)
    return f"{m:02d}:{s:02d}"


def gaussian_smooth(vals: List[float], sigma_samples: float) -> List[float]:
    """Gaussian smoothing واقعی — برای دسترسی selftest در سطح ماژول"""
    return _gauss_smooth_impl(vals, sigma_samples)


def _gauss_smooth_impl(vals: List[float], sigma_samples: float) -> List[float]:
    """
    نسخه ۳ — Gaussian smoothing قطعه‌بندی‌شده (NaN-aware):
    نمونه‌های NaN (نگهبان‌های شکاف HT) به‌عنوان جداکننده عمل می‌کنند و هر
    قطعهٔ پیوسته به‌صورت مستقل هموار می‌شود؛ در نتیجه:
      * NaN در سراسر سری «پخش» نمی‌شود (رفتار قبلی: آلودگی به شعاع کرنل)
      * منحنی هر نیمه تا لبهٔ شکاف کاملاً هموار و پیوسته است و روی شکاف پل نمی‌زند
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
    # پیدا کردن قطعه‌های پیوستهٔ non-NaN
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
    """هموارسازی گاوسی یک قطعهٔ پیوسته (بدون NaN) — edge-padding برای حفظ لبه‌ها"""
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
# نسخه ۱۰٫۲ — بارگذاری آیکون توپ گل از tex/ball_icon.png (کنار کد)
# ---------------------------------------------------------------------
# * اگر فایل موجود باشد → draw_momentum_chart به‌جای دایرهٔ سفید،
#   همین تصویر را با قطر cfg.BALL_ICON_SIZE_PT رسم می‌کند.
# * اگر فایل نبود/خراب بود → دایرهٔ سفید پیش‌فرض (fallback قطعی).
# * نتیجه کش می‌شود تا فقط یک بار از دیسک خوانده شود.
# =====================================================================
_ball_icon_cache = {"tried": False, "arr": None}


def load_ball_icon():
    """
    آرایهٔ تصویر آیکون توپ (tex/ball_icon.png کنار فایل کد) یا None.
    خروجی همیشه برای رندر امن است: None یعنی fallback به دایره.
    """
    if _ball_icon_cache["tried"]:
        return _ball_icon_cache["arr"]
    _ball_icon_cache["tried"] = True
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "tex", "ball_icon.png")
        if os.path.exists(path):
            import matplotlib.image as _mpimg
            arr = _mpimg.imread(path)
            if getattr(arr, "ndim", 0) == 3 and arr.shape[0] > 0 and arr.shape[1] > 0:
                _ball_icon_cache["arr"] = arr
                clog(f"[BallIcon] آیکون توپ بارگذاری شد: {path} "
                      f"({arr.shape[1]}×{arr.shape[0]})")
            else:
                clog(f"[BallIcon] فرمت تصویر قابل استفاده نیست: {path}")
        else:
            clog(f"[BallIcon] فایل آیکون پیدا نشد: {path} — "
                  f"از دایرهٔ سفید پیش‌فرض استفاده می‌شود")
    except Exception as ex:
        clog(f"[BallIcon] خطای بارگذاری آیکون: {type(ex).__name__}: {ex}")
    return _ball_icon_cache["arr"]


_red_card_icon_cache = {"arr": None}

RED_CARD_ASPECT_W_H = 0.628            # 27/43 — عین نمونهٔ کاربر
RED_CARD_FILL_TOP = (250, 49, 60)      # #FA313C — لبهٔ بالا
RED_CARD_FILL_BOTTOM = (234, 1, 11)    # #EA010B — لبهٔ پایین


def build_red_card_icon():
    """
    نسخهٔ ۱۰٫۲۷ — آیکون کارت قرمز به‌صورت آرایهٔ RGBA float 0..1 — طراحی
    در کد با PIL (ابرنمونه‌گیری ×۴ + فرود LANCZOS برای لبهٔ نرم؛ عین
    نسخهٔ 2017). None اگر PIL در دسترس نباشد (رندرها به مربع قرمز
    Matplotlib fallback می‌کنند).
    """
    if _red_card_icon_cache["arr"] is not None:
        return _red_card_icon_cache["arr"]
    if Image is None:
        return None
    try:
        from PIL import ImageDraw as _IDraw
        from PIL import ImageFilter as _IFilter

        w, h = 66, 105                    # نسبت 0.629 ≈ نمونه (27×43)
        ss = 4                            # ابرنمونه‌گیری
        W, H = w * ss, h * ss
        pad = 3 * ss                      # حاشیه برای سایه
        radius = max(2, int(round(W * (2.5 / 27.0))))

        canvas = Image.new("RGBA", (W + 2 * pad, H + 2 * pad),
                           (0, 0, 0, 0))

        # --- سایهٔ نرم تیره (جابه‌جایی ~1px پایین + بلور) ---
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        _sdr = _IDraw.Draw(shadow)
        _sdr.rounded_rectangle(
            [pad + ss, pad + ss, pad + W - 1 + ss, pad + H - 1 + ss],
            radius=radius, fill=(10, 14, 22, 118))
        shadow = shadow.filter(_IFilter.GaussianBlur(radius=2 * ss))
        canvas.alpha_composite(shadow)

        # --- بدنهٔ کارت: گرادیان عمودی + ماسک گوشهٔ گرد ---
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

        # --- فرود ابرنمونه → آرایهٔ float 0..1 ---
        try:
            _lanczos = Image.Resampling.LANCZOS
        except AttributeError:
            _lanczos = Image.LANCZOS
        icon = canvas.resize((w, h), _lanczos)
        arr = np.asarray(icon.convert("RGBA")).astype(float) / 255.0
        _red_card_icon_cache["arr"] = arr
        clog(f"[RedCardIcon] آیکون کارت قرمز ساخته شد ({w}×{h})")
        return arr
    except Exception as ex:
        clog(f"[RedCardIcon] خطای ساخت آیکون: {type(ex).__name__}: {ex}")
        return None


def draw_momentum_chart(ax, momentum: "MomentumEngine", cfg: "MomentumScoringConfig",
                        disp_value, goal_glyph_ok: bool = True,
                        home_color: str = '#e63946', away_color: str = '#f5f5f5'):
    """
    رندر کامل نمودار روی ax — هم در App و هم در selftest (headless).
    نسخه ۹ — اصل ساده: Memory Goal Counter → add_hook_goal_marker()
      → فوراً Schedule Render → draw_momentum_chart() → خط + توپ
      * Goal Marker «خط عمودی + آیکون توپ» فقط و فقط از hook_goal_markers
        ساخته می‌شود (منبع قطعی: Memory Goal Counter → Goal Marker → Chart).
        برای هر آیتم hook_goal_markers دقیقاً یک مارکر رسم می‌شود و هیچ
        Dedup بین گل‌ها انجام نمی‌شود — حتی اگر دو گل نزدیک هم باشند یا
        از یک تیم باشند.
      * نسخه ۹ (مهم): در این تابع هیچ return زودهنگامی وجود ندارد —
        بلوک len(hist) < 2 فقط پیام «در انتظار شروع مسابقه...» می‌گذارد؛
        لایه‌های وابسته به history (منحنی/HT/تیک/Legend) با گارد محلی
        len(hist) >= 2 رد می‌شوند تا بخش Goal Marker «همیشه» اجرا شود.
      * Goal Impact / Event Bus / Shot / history / dedup هیچ نقشی در
        رسم مارکر ندارند (مسیر پالس کاملاً مستقل:
        Counter → Goal Event → Goal Impact → Momentum Pulse).
      * disp_time هر مارکر همان مقدار فریزشده هنگام ثبت در
        add_hook_goal_marker است؛ ترتیب رسم = ترتیب ثبت (بدون sort).
      * Home: آیکون بالا/خط سفید به سمت پایین تا خط صفر | Away: برعکس؛
        خط از خط وسط رد نمی‌شود و هیچ متنی روی نمودار نوشته نمی‌شود
      * شکاف HT: دو خط عمودی سرتاسری + برچسب HT + شکاف‌های اضافی resync
      * هر Artist مارکر با gid قطعی تگ می‌شود (goal_line_{i}_shell /
        goal_line_{i}_core / goal_ball_{i}) تا Self-Test بتواند assert
        کند: len(hook_goal_markers) == number_of_goal_icons
                              == number_of_goal_marker_lines
      * مشخصات قطعی رسم مارکر (v9): clip_on=False برای همهٔ Artistها،
        zorder 100 (shell) / 101 (core) / 102 (ball)؛ توپ عمداً
        marker="o" ماتplotlib است — هیچ وابستگی به فونت/گلیف ندارد و
        goal_glyph_ok در Goal Marker بی‌تأثیر است.
      * لاگ‌های تفکیکی زنجیره: [GraphGoalRender] بعد از Snapshot و
        [GoalMarkerRender] قبل از حلقهٔ رسم — برای تشخیص دقیق محل خرابی
        (Hook → Engine → Snapshot → Render → Matplotlib)
    """
    with momentum._lock:
        hist = list(momentum.history)
        display_offset = momentum.display_offset
        ht_break = momentum.ht_break
        extra_breaks = list(momentum.extra_breaks)
        hook_markers = [dict(m) for m in momentum.hook_goal_markers]
        # نسخهٔ ۱۰٫۲۷ — مارکرهای کارت قرمز (getattr: سازگاری با موتورهای شبه)
        rc_markers = [dict(m) for m in
                      (getattr(momentum, "red_card_markers", None) or [])]

    # نسخه ۸ — Snapshot اتمیک گرفته شد؛ از اینجا به بعد فقط و فقط از
    # hook_markers استفاده می‌شود (هیچ دسترسی مستقیم به
    # momentum.hook_goal_markers در ادامهٔ تابع وجود ندارد).
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
    ax.set_xlabel("زمان مسابقه (Game Clock)", color='#94a3b8', fontsize=8)
    ax.set_ylabel("Net Momentum\n(Home ↑ / Away ↓)", color='#ffd166', fontsize=8)
    # نسخه ۳: حاشیه بالا/پایین برای آیکون توپ گل‌ها — نسخه ۴: کمی بزرگ‌تر (آیکون ۱۳)
    ax.set_ylim(-rng - 18, rng + 27)
    ax.axhline(0, color='#7f8fa6', linewidth=1.0, alpha=0.8)
    ax.grid(True, linestyle='--', alpha=0.22, color=grid)

    if len(hist) < 2:
        ax.text(
            0.5,
            0.5,
            "در انتظار شروع مسابقه...",
            transform=ax.transAxes,
            ha="center",
            va="center",
            color="#54607a",
            fontsize=11
        )

        # مهم:
        # اینجا RETURN ممنوع است.
        #
        # Goal Marker مستقل از history است و پایین‌تر
        # باید حتماً Render شود.

    # --- نسخه ۹: منحنی/HT فقط با history کافی — بدون هیچ return ---
    # (قبلاً اینجا با return زودهنگام کل تابع رد می‌شد؛ اکنون فقط این
    #  لایه‌های وابسته به history گارد می‌شوند تا Goal Marker که پایین‌تر
    #  است «همیشه» اجرا شود — حتی با صفر یا یک نمونه)
    t_axis = None
    t_end = 0.0
    if len(hist) >= 2:
        # --- downsampling برای عملکرد (RAW منبع، فقط فاصله‌گذاری) ---
        step = max(1, len(hist) // 3000)
        samples = hist[::step]
        if samples[-1] is not hist[-1]:
            samples.append(hist[-1])

        t_axis = [s.get("disp_time", s["game_time"]) for s in samples]
        net_disp = [disp_value(s["net"]) for s in samples]

        # --- Gaussian smoothing واقعی (نه میانگین متحرک) — فقط لایه نمایش ---
        # نسخه ۳: sigma بزرگ‌تر (GAUSSIAN_SIGMA=7s) → منحنی پیوستهٔ خمیده بدون دندانه؛
        # هموارسازی قطعه‌بندی‌شده است → NaNهای شکاف HT پخش نمی‌شوند و پل نمی‌زنند
        dts = [(b["game_time"] - a["game_time"]) for a, b in zip(samples, samples[1:])
               if b["game_time"] > a["game_time"]]
        eff_dt = (sum(dts) / len(dts)) if dts else cfg.HISTORY_SAMPLE_INTERVAL
        sigma_samples = cfg.GAUSSIAN_SIGMA / max(0.02, eff_dt)
        net_disp = _gauss_smooth_impl(net_disp, sigma_samples)

        # --- Net Area آینه‌ای: Home بالا | Away پایین ---
        # نسخهٔ ۱۰٫۶ — رنگ هر تیم از leagues_data.json + بایت استاتیک شمارهٔ رنگ
        # خوانده می‌شود (پیش‌فرض: قرمز/سفیدِ همیشه‌قبلی)؛ شکل نمودار تغییری نکرده.
        ax.fill_between(t_axis, net_disp, 0, where=[(v >= 0) for v in net_disp],
                        interpolate=True, color=home_color, alpha=0.80, label='میزبان (Home)')
        ax.fill_between(t_axis, net_disp, 0, where=[(v < 0) for v in net_disp],
                        interpolate=True, color=away_color, alpha=0.90, label='میهمان (Away)')
        # نسخه ۳: منحنی ضخیم‌تر با اتصال/درز گرد → حس «یک خط ممتد»
        ax.plot(t_axis, net_disp, color='#ffd166', linewidth=2.0, alpha=0.95,
                solid_capstyle='round', solid_joinstyle='round', antialiased=True)

        # --- شکاف HT: دو خط عمودی سرتاسری + برچسب HT (نسخه ۳) ---
        # نسخه ۵: شکاف‌های اضافی resync_clock هم با دو خط سرتاسری (بدون برچسب)
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
    # فقط و فقط:
    # MomentumEngine.hook_goal_markers
    #
    # هر آیتم = دقیقاً یک خط + یک توپ
    # هیچ Dedup
    # هیچ Event Impact
    # هیچ Shot
    # هیچ History شرطی
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

    # نسخه ۱۰٫۲ — آیکون توپ یک بار در هر رندر بارگذاری می‌شود (کش داخلی)
    _ball_icon_ref = load_ball_icon()

    clog(
        "[GoalMarkerRender] "
        f"count={len(goal_points)} | "
        f"points={goal_points}"
    )

    for gi, (gx, team) in enumerate(goal_points):

        y_goal = y_top if team == "Home" else y_bot

        # ------------------------------------------------------------
        # خط عمودی — shell
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
        # خط عمودی — core
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
        # توپ — نسخه ۱۰٫۲: آیکون PNG (tex/ball_icon.png کنار کد)
        # اگر فایل آیکون موجود باشد، تصویر با قطر cfg.BALL_ICON_SIZE_PT
        # (بزرگ‌تر از دایرهٔ قبلی) رسم می‌شود؛ در غیر این صورت دایرهٔ
        # Matplotlib (قطعی و مستقل از فونت) با سایز کمی بزرگ‌تر (۱۷).
        # برای حفظ قرارداد Self-Test، در حالت آیکون هم یک Line2D نامرئی
        # با همان gid «goal_ball_{i}» ثبت می‌شود (تکیه‌گاه موقعیت/شمارش)،
        # و خود آیکون با gid «goal_ballimg_{i}» اضافه می‌شود.
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
            # تبدیل قطر مطلوب Point → zoom مناسب هر اندازه تصویر:
            #   اندازهٔ نمایشی (px خروجی) = px تصویر × zoom  و  px = pt × dpi / 72
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
            # فعلاً عمداً از glyph فونت استفاده نکن.
            # دایره‌ی Matplotlib قطعی و مستقل از فونت است.
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
        # GID برای تست
        # ------------------------------------------------------------
        shell.set_gid(f"goal_line_{gi}_shell")
        core.set_gid(f"goal_line_{gi}_core")
        ball.set_gid(f"goal_ball_{gi}")

    # ================================================================
    # نسخهٔ ۱۰٫۲۷ — RED CARD MARKER (عین GOAL MARKER — آیکون کارت به‌جای توپ)
    # ================================================================
    # فقط و فقط: MomentumEngine.red_card_markers
    # هر آیتم = دقیقاً یک خط (shell + core) + یک آیکون کارت قرمز.
    # gid ها: rc_line_{i}_shell / rc_line_{i}_core / rc_card_{i} (تکیه‌گاه)
    # و rc_cardimg_{i} (آیکون) — همان قرارداد تست‌پذیری گلی (عین 2017).
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
        # خط عمودی — shell + core (عین گل)
        # ------------------------------------------------------------
        rc_sh = ax.plot([gx, gx], [y_rc, 0.0], color="#0d1420",
                        linewidth=5.0, alpha=1.0, zorder=100,
                        solid_capstyle="butt", clip_on=False)[0]
        rc_co = ax.plot([gx, gx], [y_rc, 0.0], color="#ffffff",
                        linewidth=2.5, alpha=1.0, zorder=101,
                        solid_capstyle="butt", clip_on=False)[0]

        # ------------------------------------------------------------
        # آیکون کارت قرمز — اندازهٔ نقطه‌ای از نسبت‌های نمونهٔ کاربر:
        # ارتفاع ≈ 1.05 × قطر آیکون توپ، عرض از نسبت ابعاد 0.628.
        # اگر PIL نبود → مربع قرمز Matplotlib (قطعی و مستقل از فونت).
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
            # ارتفاع نمایشی (Point): نسبتِ کارت‌به‌توپ عین نمونه (≈1.05×)
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
    # محور X حتماً باید Goal را پوشش بدهد
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

    # --- بازه محور X (نسخه ۹ — فقط با history کافی) ---
    # پوشش گل‌ها توسط بلوک Goal Marker بالا انجام شده است؛ اینجا فقط
    # پوشش منحنی تضمین می‌شود و تضمین می‌کنیم پوشش گل کوچک‌تر نشود
    # (max با سمت راست فعلی محور)
    if len(hist) >= 2:
        x_right = max(60.0, t_end + 45.0, ax.get_xlim()[1])
        ax.set_xlim(max(0.0, t_axis[0]), x_right)

    # --- تیک‌های ۱۵ دقیقه‌ای Game Clock (نسخه ۳: نگاشت واقعی زمان مسابقه) ---
    # زمان‌های نیمه اول بدون offset؛ زمان‌های نیمه دوم با offset → تیک 60'
    # درست بعد از شکاف HT می‌افتد و هیچ تیکی داخل شکاف قرار نمی‌گیرد
    # (نسخه ۹: فقط با history کافی — بدون return، گارد محلی)
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

    # --- Legend: میزبان / میهمان / Goal (خط سفید + آیکون توپ) ---
    # (نسخه ۹: فقط با history کافی — حالت انتظار خالی بدون Legend می‌ماند)
    if len(hist) >= 2:
        handles = [
            Patch(facecolor=home_color, alpha=0.80, label='میزبان (Home)'),
            Patch(facecolor=away_color, alpha=0.90, label='میهمان (Away)'),
        ]
        if goal_points:
            handles.append(Line2D([0], [0], color='#ffffff', linewidth=1.9,
                                  marker='o', markersize=9,
                                  mfc='#ffffff', mec='#0d1420', mew=1.3,
                                  label='Goal'))
        ax.legend(handles=handles, facecolor='#111722', edgecolor='#2e384d',
                  labelcolor='#ffffff', fontsize=7, loc='upper left')


# =====================================================================
# ۲۵٫ب — رندر «TV Momentum»: نمودار مومنتوم روی تصویر پنل (نسخهٔ ۱۰٫۷)
# ---------------------------------------------------------------------
# * پس‌زمینه: تصاویر PNG پوشهٔ tex کنار اسکریپت:
#     نیمه اول  → Half_Match_Moment.png   |  نیمه دوم → Full_Match_Moment.png
#     وقت اضافه → Extra_Match_Moment.png
# * هندسهٔ تصویر (مستطیل نمودار، خط صفر، خطوط عمودی HT/FT/ET) «از خود
#   تصویر» تشخیص داده می‌شود (ناحیهٔ خاکستری یکدست ‎#3a3a3a + خطوط سفید)؛
#   اگر تشخیص ناموفق بود، مقادیر اندازه‌گیری‌شده از همین فایل‌ها به‌عنوان
#   fallback استفاده می‌شود.
# * قواعد رسم (دقیقاً طبق مشخصات کاربر):
#     - نمودار از همان اول با اندازهٔ کامل رسم می‌شود (جمع نمی‌شود)
#     - محور عمودی ‎-120..+120‎ — بدون هیچ عدد/تیک/لجند/متن
#     - خط افقی میانهٔ مستطیل = خط صفر
#     - خط صفر و خطوط عمودی تصویر «محو نمی‌شوند» (بعد از fill دوباره
#       روی آن‌ها کشیده می‌شود) — لایهٔ خود نمودار ۱۰۰٪ شفاف است
#     - رنگ fill = رنگ نمودار خودمان؛ استروک زرد در این تب حذف شده
#     - درخشش نئونی ضعیف دور لبهٔ fill
#     - گپ بین دو نیمه حذف — دو نیمه از محل خط مرکز به هم می‌چسبند
#     - مارکر گل = خط عمودی باریک + توپ (اندازه‌ها عین نمونهٔ کاربر)
#     - لوگو/پرچم تیم‌ها: ناحیهٔ مشکی چپ — میزبان بالا / مهمان پایین،
#       با استروک سفید گوشه‌گرد مثل تصویر نمونه
# =====================================================================
TV_BG_DIRNAME = "tex"                                   # کنار اسکریپت
TV_BG_FILES = {
    "half":  "Half_Match_Moment.png",
    "full":  "Full_Match_Moment.png",
    "extra": "Extra_Match_Moment.png",
}
# ------------------------------------------------------------------
# نسخهٔ ۱۰٫۸ — کالیبراسیون محور افقی از روی «تیک‌های خود تصویر»
#   HT = دقیقهٔ ۴۵ | FT = دقیقهٔ ۹۰ | ET = دقیقهٔ ۱۰۵
#   نیمه اول : تیک‌های ۰ ، ۱۵ ، ۳۰ ، ۴۵(HT)
#   نیمه دوم : تیک‌های ۰ ، ۱۵ ، ۳۰ ، ۴۵(HT) ، ۶۰ ، ۷۵ ، ۹۰
#   وقت اضافه: تیک‌های ۰ ، ۱۵ ، ۳۰ ، ۴۵(HT) ، ۶۰ ، ۷۵ ، ۹۰(FT) ، ۱۰۵(ET) ، ۱۲۰
# تعداد تیکِ تشخیص‌داده‌شده ← دقیقهٔ لنگرها؛ نگاشت دقیقه→پیکسل خطیِ تکه‌تکه.
# ------------------------------------------------------------------
TV_TICK_MINUTES_BY_COUNT = {
    4: (0.0, 15.0, 30.0, 45.0),
    7: (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0),
    9: (0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0, 105.0, 120.0),
}
# موقعیت تیک‌ها روی فایل‌های اصلی (پیکسل تصویر مبنا) — فقط fallback
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
TV_Y_RANGE = 150.0            # محور عمودی پایه ‎-150..+150‎ (بدون عدد روی محور)
# --- نسخهٔ ۱۰٫۱۶ — مقیاس عمودی «پویا» (شرط جدید کاربر) ---
# سقف محور = ۵۰ واحد بالاتر از «بیشینهٔ قدرمطلق ارتفاع هر دو نمودار» (بالا+
# پایین با هم) و هرگز کمتر از ۱۵۰ نیست:
#   مقیاس = max(150 ، بیشینهٔ |ارتفاع نمودار| + 50)
# مثال کاربر: اوج ۱۲۰ → محور ‎±۱۷۰‎؛ اگر ‎(اوج+۵۰)<۱۵۰‎ شد → همان ‎±۱۵۰‎.
TV_SCALE_MARGIN = 50.0        # فاصلهٔ سقف محور از بیشینهٔ نمودار
TV_SCALE_MIN = 150.0          # حداقل مجاز مقیاس (= TV_Y_RANGE)
# آیکون توپ همیشه «۳۰ واحد پایین‌تر از سقف مقیاس» است (شرط کاربر ۱۰٫۱۶):
# توپ = مقیاس − ۳۰ → همهٔ توپ‌ها در «یک ارتفاع»؛ اگر مقیاس بعداً عوض شود
# توپ‌ها همگی با هم جابه‌جا می‌شوند. با مقیاس حداقل ۱۵۰ → توپ روی ۱۲۰
# (همان TV_BALL_VALUE نسخهٔ قبل — فقط حالت خاصِ مقیاس حداقل است).
TV_BALL_GAP = 30.0
# --- هندسهٔ تیک‌ها (نوار کوتاه زیر لبهٔ پایین مستطیل) ---
TV_TICK_BAND_OFF = 4          # شروع اسکن: b + 4 پیکسل
TV_TICK_BAND_H = 30           # ارتفاع نوار اسکن تیک
TV_TICK_MIN_ROWS = 12         # حداقل پیکسل سفید در ستونِ تیک
# --- اندازه‌های مارکر گل (عیناً از تصویر نمونهٔ کاربر اندازه‌گیری شد) ---
TV_BALL_FRAC = 0.061          # قطر توپ ÷ ارتفاع مستطیل  (≈ 34px در 560px — عین نمونه)
TV_BALL_EDGE_FRAC = 0.079     # (منسوخ — نسخهٔ ۱۰٫۱۵) فاصلهٔ قبلی توپ از لبه
# نسخهٔ ۱۰٫۱۵ — ارتفاع آیکون توپ روی ‎±120‎ — نسخهٔ ۱۰٫۱۶: مقدار مؤثر
# «مقیاس − ۳۰» است (TV_BALL_GAP)؛ این ثابت فقط حالت خاصِ مقیاس حداقل
# (۱۵۰) را نشان می‌دهد و برای سازگاری تست‌ها نگه داشته شده است.
TV_BALL_VALUE = 120.0
TV_GLINE_FRAC = 0.0054        # ضخامت خط گل ÷ ارتفاع مستطیل (≈ 3px — عین نمونه)
TV_GLINE_SHELL_FRAC = 0.0089  # پوستهٔ تیرهٔ زیر خط سفید (≈ 5px — خوانایی روی fill روشن)
# --- نسخهٔ ۱۰٫۲۷ — اندازه‌های مارکر کارت قرمز (عین نسخهٔ 2017 / تصویر کاربر) ---
TV_RC_W_FRAC = 0.040          # عرض کارت قرمز ÷ ارتفاع مستطیل (≈ 0.66 × قطر توپ)
TV_RC_H_FRAC = 0.064          # ارتفاع کارت قرمز ÷ ارتفاع مستطیل (≈ 1.05 × قطر توپ)
# --- نسخهٔ ۱۰٫۲۷ — منطق انتساب تیم کارت قرمز (تماشای بازیکن اخراجی) ---
RC_Z_TARGET = 40.0            # مختصات z بازیکن اخراجی (بیرون خط طولی ۶۸m)
RC_Z_TOL = 5.0                # تلورانس تشخیص z≈40 (بازیکنان زمین |z|≤34)
RC_WATCH_WINDOW_S = 30.0      # پنجرهٔ تماشا (ثانیهٔ زمان بازی) برای تعیین تیم
RC_WATCH_WALL_CAP_S = 300.0   # سقف wall تور ایمنی (توقف طولانی/ساعت گیرکرده)
RC_MAX_JUMP = 5               # جهش مجاز شمارنده در یک Poll (بیشتر = ری‌بیس‌لاین)
# --- لوگو/پرچم (ناحیهٔ مشکی چپ — اندازه‌ها عین تصویر نمونه) ---
TV_FLAG_TARGET_W = 110        # بزرگ‌ترین بُعد نهایی لوگو+استروک (≈ 109px در نمونه)
TV_FLAG_CONTENT_W = 100       # عرض محتوای رنگی پس از برش (نوار مشکی ≈ 135px)
TV_FLAG_CONTENT_MAX_H = 118   # سقف ارتفاع محتوای رنگی
TV_FLAG_STROKE_PX = 3         # استروک سفید خیلی نازک (≈ 3px در نمونه)
TV_FLAG_GAP_PX = 2            # فاصلهٔ استروک از قسمت رنگی (مثل نمونه)
TV_FLAG_CX_FRAC = 0.663       # x مرکز لوگو ÷ x لبهٔ چپ مستطیل (≈ 142px — مرکز نوار)
TV_FLAG_HOME_CY_FRAC = 0.229  # y مرکز لوگوی میزبان از بالای مستطیل (عین نمونه)
TV_FLAG_AWAY_CY_FRAC = 0.779  # y مرکز لوگوی مهمان از بالای مستطیل (عین نمونه)
# --- ظاهر ---
TV_ZERO_LINE_LW_FRAC = 0.0075   # ضخامت خط صفر بازکشیده‌شده ÷ ارتفاع مستطیل
TV_VLINE_LW_FRAC = 0.0060       # ضخامت خطوط عمودی بازکشیده‌شده (HT/FT/ET)
TV_FILL_ALPHA_HOME = 0.80       # عین نمودار اصلی
TV_FILL_ALPHA_AWAY = 0.90
# --- منحنی: هموارسازی نمایشی + حذف دندانه (نسخهٔ ۱۰٫۸) ---
TV_SMOOTH_SIGMA_SEC = 55.0    # سیگمای گاوسیِ لایهٔ نمایش TV (ثانیهٔ زمان بازی)
                              # v10.27 — ۳۵→۵۵ (همان تنظیم «زنگوله‌ای» نسخهٔ
                              # 2017 — قله‌ها/دره‌ها پهن‌تر و نرم‌تر می‌شوند؛
                              # شکستگی‌های جزئی محو؛ شکل کلی حفظ می‌شود)
TV_BIN_STEP_PX = 1.5          # میانگین‌گیری داخل ستون‌های ۱٫۵ پیکسلی (ضد دندانه)
# --- نسخهٔ ۱۰٫۲۶ — «پلهٔ نامرئی» (ادامهٔ لبهٔ ابریشمی — مرجع صافی کاربر:
#     snap_h1 / preview_v10_18_userzoom / preview_v10_18_stroke). ریشهٔ
#     «پله‌پله»ی باقی‌مانده پیدا شد: درون‌یابی «خطی» بین گره‌های ~۰٫۹px،
#     شیب را در هر گره ناگهانی عوض می‌کند ⇒ اسکالوپینگِ مقیاس پیکسل ⇒
#     پله‌های کلوخه‌ای در زوم (۵-۸×). درمان (فقط رندر — فرم دست‌نخورده):
#     ۱) _tv_uniform_resample_c1: درون‌یابی «مکعبی مونوتون» (PCHIP /
#        Fritsch–Carlson) روی همان شبکهٔ ۰٫۵px — از همهٔ گره‌ها می‌گذرد
#        (ارتفاع قله/دره عین قبل)، مونوتون (صفر فراجوش)، شیب پیوسته ⇒
#        پله‌ها یکنواخت و مخملی. تغییر شکل نسبت به خطی: میانگین ۰٫۱۵px،
#        p99 ۰٫۷px — نامرئی در نگاه عادی؛ تعداد قله‌ها و عبور از صفر عین قبل.
#     ۲) feather stroke: استروک نیمه‌شفاف هم‌رنگ (۱٫۶px، آلفا ۰٫۴) روی مرز
#        fill در مسیر matplotlib ⇒ گذار آلفای لبه ~۲x پهن‌تر و مخملی
#        (عین مرجع snap_h1؛ peak-gradient لبه ۶۸→۴۵). env:
#        TV_EDGE_FEATHER_LW / TV_EDGE_FEATHER_ALPHA (۰=خاموش).
#     ۳) مسیر GPU (اورلی زنده): uniform جدید u_feather در شیدر لبه — فقط
#        آیتم‌های fill نرمی ۱px می‌گیرند (خط‌ها/توپ/پرچم تیز می‌مانند).
#        env: TV_GPU_FILL_FEATHER (۰=رفتار قبلی).
# --- نسخهٔ ۱۰٫۲۵ — «لبهٔ ابریشمی» (کاربر: لبهٔ نمودار کاملاً صاف و صیقلی،
#     بدون به‌هم‌ریختن فرم کلی) — ریشهٔ دندانه‌ها پیدا شد: خروجی binning،
#     ستون‌های «ناهم‌فاصله» با مرکزهای لرزان می‌دهد و پلی‌لاین fill بین
#     آن‌ها پلهٔ پیکسلی می‌سازد؛ AA معمولی Agg (‎~۱px‎) آن را نمی‌پوشاند.
#     درمان دو لایه‌ای (فقط لایهٔ نمایش — فرمول مومنتوم دست‌نخورده):
#     ۱) بازنمونه‌برداری منحنی روی شبکهٔ افقی «یکنواختِ» ریز (۰٫۵px)
#     ۲) گاوسیِ زیرپیکسلیِ ثابت (۰٫۶px) فقط برای ارتعاش ستونیِ باقی‌مانده —
#        عرض ویژگی‌های نمودار ≥ ~۱۰px ⇒ افت ارتفاع قله < ۰٫۲٪ (فرم عین قبل)
#     ۳) رندر اسنپ‌شات با ابرنمونه‌گیری TV_SNAPSHOT_SS× و میانگین Box —
#        AA واقعی روی همهٔ لبه‌ها (fill/گلو/خط گل/متن/لوگو) بدون تغییر شکل
TV_CURVE_GRID_STEP_PX = 0.5     # گام شبکهٔ یکنواخت خروجی منحنی (پیکسل)
TV_EDGE_MICRO_SIGMA_PX = 0.8    # سیگمای گاوسی زیرپیکسلی لبه (پیکسل طراحی)
TV_SNAPSHOT_SS = 2              # ضریب ابرنمونه‌گیری رندر اسنپ‌شات (۱ = خاموش)
# --- نسخهٔ ۱۰٫۲۶ — لبهٔ مخملی (feather) — عین مرجع صافی کاربر (snap_h1) ---
# استروکِ نیمه‌شفافِ هم‌رنگ روی «خودِ مرز fill» → گذار آلفای لبه از ~۱px
# به ~۱٫۶-۲px پهن می‌شود؛ پله‌های رستری در زوم مخملی دیده می‌شوند (عین
# مرجع). هیچ تأثیری روی هندسه/شکل داده ندارد — فقط «رندرِ» لبه.
# TV_EDGE_FEATHER=0 (env) → خاموش (رفتار ۱۰٫۲۵).
TV_EDGE_FEATHER_LW_PX = 1.6     # ضخامت استروک feather (پیکسل طراحی)
TV_EDGE_FEATHER_ALPHA = 0.40    # آلفای استروک feather
# مسیر GPU (اورلی زنده): هم‌ارزِ همان نرمی برای fill برداری — نیم‌عرضِ
# smoothstep لبه (پیکسل سطح). ۰ = رفتار قبلی (لبهٔ تیز ۱px).
TV_GPU_FILL_FEATHER_PX = 1.0
# (نسخهٔ ۱۰٫۱۰ — خط لبهٔ حذف شد: دو خط افقیِ نزدیک خط صفر به رنگ تیم‌ها
#  که کاربر گزارش کرد همان rim لبهٔ fill بود — حذف شد)
# --- درخشش نئون نرم (بلور گاوسیِ واقعی — محوشدگی کاملاً نرم از خط به بیرون) ---
TV_GLOW_CORE_PX = 4.0                       # ضخامت خط مبدأ درخشش
# نسخهٔ ۱۰٫۱۰ — شدت بیشتر با همان نرمی (سیگماها ثابت = نرمی همان؛
# فقط آلفای اوج ~۱٫۶ برابر شد تا درخشش بیشتر دیده شود)
TV_GLOW_LAYERS = ((3.0, 0.48), (10.0, 0.21))  # (سیگمای بلور، آلفای اوج)
# --- نسخهٔ ۱۰٫۱۶ — پیچ‌های موقتِ کاربر (کنار نمودار؛ بعداً هاردکد می‌شوند) ---
TV_GLOW_SOFTNESS_MUL = 1.0     # ضریب «نرمی» نئون — در سیگمای بلور ضرب می‌شود
TV_GLOW_INTENSITY_MUL = 1.0    # ضریب «شدت» نئون — در آلفای اوج ضرب می‌شود
TV_EDGE_SMOOTH_PX = 0.0        # هموارسازی اضافهٔ «لبهٔ» نمودار (گاوسی، پیکسل)
# نسخهٔ ۱۰٫۱۷ — سقف جابه‌جایی مجاز هموارساز لبه (پیکسل): با کلمپ نرم tanh،
# هیچ ستونی بیش از این مقدار از مقدار اصلی‌اش دور نمی‌شود ⇒ دندانه‌های
# لبه صاف می‌شوند ولی «شکل کلی» (قله‌ها/دره‌ها/ارتفاع‌ها) دست‌نخورده می‌ماند
# (شرط کاربر: «نرم کردن لبه نباید شکل کلی نمودار را به هم بریزد»).
TV_EDGE_SMOOTH_MAX_SHIFT_PX = 10.0
# --- نسخهٔ ۱۰٫۹ — درخشش سفید نرمِ «توپ + خط عمودی گل» ---
TV_MARKER_GLOW_LAYERS = ((2.5, 0.38), (9.0, 0.18))  # (سیگمای بلور، آلفای اوج) — سفید
# --- نسخهٔ ۱۰٫۹ — «دقیقه‌های مشترک» (وقت اضافه‌شدهٔ هر بخش) ---
# اولین گذر از این دقیقه‌ها در هر مرز = وقت اضافهٔ بخش قبلی (قبل از خط مرز
# فشرده می‌شود)؛ با ری‌استارت تایمر، رسم از خودِ خط مرز ادامه می‌یابد.
TV_STOP_BOUNDS = (45.0, 90.0, 105.0, 120.0)   # مرز بخش‌ها: HT / FT / ET / پایان
TV_STOP_WINDOW = {45.0: 5.0, 90.0: 7.0, 105.0: 7.0, 120.0: 7.0}
#                        ↑ پنجرهٔ دقیقه‌های مشترک (کاربر: ۴۵-۵۰ و ۹۰-۹۷)
TV_STOP_SQUEEZE_FRAC = 0.10    # ضخامت باند فشردن = این کسر × فاصلهٔ تیک‌ها (px/min)
TV_STOP_BAND_CAP_MIN = 8.0     # سقف دقیقه‌های فشرده‌شده در نگاشت (ضد باند غیرواقعی)
TV_RESTART_GAP_SEC = 4.0       # حداقل شکاف زمان واقعی برای «تعویض دوره» (ری‌استارت تایمر)
# --- نسخهٔ ۱۰٫۱۰ — تشخیص ری‌استارت طبق شرط کاربر: «کد اول چک کند که آیا
# بازی به دقیقهٔ ۴۵ یا ۹۰ ریست شده؟» یعنی تایمر از مرز رد شده، عدد بزرگ‌تر
# دیده و بعد از یک توقف دوباره از خودِ مرز شروع به شمارش کرده؛ تا قبل از
# این رویداد، دقیقه‌های مشترک جزو وقت اضافهٔ بخش قبلی‌اند.
TV_RESTART_LAND_EPS = 0.25     # فرود ری‌استارت: تا ۱۵ ثانیه بعد از دقیقهٔ مرز
TV_RESTART_LAND_BELOW = 0.05   # فرود ری‌استارت: تا ۳ ثانیه قبل از دقیقهٔ مرز
TV_RESTART_EDGE_EPS = 0.15     # «پایان وقت عادی روی مرز»: قبلاً تا ۹ ثانیه قبل از مرز
TV_RESTART_BACKJUMP_MIN = 0.5  # جهش عقبروی بزرگ ساعت (≥۳۰s) = توقف/بریک حتی بدون شکاف نمونه
TV_RESTART_EDGE_GAP_SEC = 30.0 # حداقل شکاف برای «پایان وقت عادی روی مرز» (بریک واقعی —
                               #  استال کوتاه نمونه‌برداری نباید ری‌استارت کاذب بسازد)
# --- نسخهٔ ۱۰٫۱۲ — «بریک بزرگ» (رفع خط صاف ابتدای نیمه دوم) ---
# علامت: خط لولهٔ داده در برک HT چند دقیقه ساکت می‌ماند؛ اگر اولین نمونهٔ
# زندهٔ نیمه دوم دیر فرود بیاید (مثلاً ۴۶'-۴۹')، فرودِ سخت‌گیرانهٔ ±۱۵ ثانیه
# رد می‌شد ⇒ همهٔ نمونه‌های نیمه دوم در نوار باریکِ کنار خط HT فشرده می‌شدند
# (کاربر: «هیچی ثبت نمی‌شه») و در خروج از پنجرهٔ ۴۵-۵۰ یک خط صاف کشیده
# می‌شد. اکنون «سکوت ≥۱۸۰ ثانیهٔ واقعی» یا «شکاف نمایشی نگهبان ≥۳۰ ثانیه»
# = بریک بزرگ؛ فرود تا انتهای پنجرهٔ مشترک پذیرفته و گارد جهش رو به جلو
# غیرفعال می‌شود. (جشن گل/Replay با سکوت ۳۰-۱۲۰ ثانیه هرگز آستانه را رد
# نمی‌کند ⇒ ری‌استارت کاذب ندارد.)
TV_BREAK_WALL_SEC = 180.0      # سکوت واقعی (Wall) بین دو نمونهٔ متوالی = بریک بزرگ
TV_RESTART_DISP_BREAK_SEC = 30.0  # شکاف disp_time نگهبان‌ها (HT/resync) = بریک بزرگ

# --- نسخهٔ ۱۰٫۱۵ — چهار نوع ریست + گیتِ فاز Lifecycle ---
# بخش‌های «بعد از» هر مرز — برای فرودهای بدون سقوطِ تایمر بعد از بریک بزرگ
# (لحظهٔ ریست توسط خط لوله دیده نشده). مُهر phase نمونه باید با بخش بعدی
# سازگار باشد؛ وگرنه وقفهٔ بلندِ وسط وقت هدررفتهٔ همان بخش، ری‌استار
# نمی‌سازد (شرط کاربر: ریست = سقوط تایمر روی مرز، نه صعود از آن).
TV_PHASE_AFTER_RESTART = {
    45.0: ("HALF_2", "ET1", "ET2"),     # بعد از HT: نیمه دوم/وقت اضافه
    90.0: ("ET1", "ET2"),               # بعد از FT: وقت اضافه
    105.0: ("ET2",),                    # بعد از برک ET: نیمه دوم وقت اضافه
}


def tv_phase_allows_restart(bound: float, phase) -> bool:
    """نسخهٔ ۱۰٫۱۵ — آیا فاز Lifecycle با «شروع بخشِ بعد از مرز» سازگار است؟
    فقط برای فرودهای بدون سقوطِ تایمر بعد از بریک بزرگ به کار می‌رود.
    phase=None / نامشخص (تاریخچهٔ قدیمی و تست‌ها) → True (رفتار قبلی)."""
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
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        TV_BG_DIRNAME, TV_BG_FILES.get(kind, TV_BG_FILES["half"]))


def _tv_group_idx(idx: "np.ndarray") -> List[Tuple[int, int]]:
    """بسته‌بندی ایندکس‌های متوالی → [(start, end)]"""
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
    تشخیص خودکار هندسه از خود تصویر:
      * مستطیل نمودار = ناحیهٔ یکدست خاکستری ‎(58,58,58)‎
      * خط صفر = سفیدِ سرتاسری در میانهٔ عمودی مستطیل
      * خطوط عمودی = ستون‌های سفیدِ سرتاسری داخل مستطیل (HT/FT/ET)
    خروجی: {"rect": (l,r,t,b), "zero_y": int, "verticals": [x,...]}
    """
    H, W = arr.shape[:2]
    rgb = np.asarray(arr[..., :3], dtype=float)
    if rgb.size and float(rgb.max()) <= 1.001:
        rgb = rgb * 255.0          # ورودی 0..1 (خروجی tv_load_background) هم پذیرفته می‌شود
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

    # --- خط صفر: سفید سرتاسری بین t و b (نزدیک‌ترین به میانه) ---
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

    # --- خطوط عمودی داخل مستطیل (تصاویر فعلی خط داخلی ندارند؛ فقط سازگاری) ---
    segv = white[t + 10:b - 10, l + 10:r - 10]
    wcols = np.where(segv.mean(axis=0) > 0.80)[0]
    verticals = []
    for g0, g1 in _tv_group_idx(wcols):
        verticals.append(l + 10 + (g0 + g1) // 2)
    # لبه‌های مستطیل از لیست خطوط داخلی حذف شوند
    verticals = [x for x in verticals if l + 14 < x < r - 14]

    # --- نسخهٔ ۱۰٫۸ — تیک‌های محور افقی (نوار کوتاه زیر لبهٔ پایین مستطیل) ---
    # این تیک‌ها لنگرهای کالیبراسیون‌اند: ۴ تیک = ۰/۱۵/۳۰/۴۵(HT)
    # ۷ تیک = ۰..۹۰ | ۹ تیک = ۰..۱۲۰ (با FT=۹۰ و ET=۱۰۵)
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
        # اعتبارسنجی: تعداد باید ۴/۷/۹ باشد؛ تیک اول نزدیک لبهٔ چپ و
        # تیک آخر نزدیک لبهٔ راست (روی فایل‌های اصلی ≈ ۶ پیکسل داخل‌تر)
        ok = len(anchors) in TV_TICK_MINUTES_BY_COUNT
        if ok and len(anchors) >= 2:
            ok = (l + 2 <= anchors[0] <= l + 60) and (r - 60 <= anchors[-1] <= r + 2)
            # فاصلهٔ تیک‌ها باید تقریباً یکنواخت باشد (بدون پرش غیرمنطقی)
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
    بارگذاری کش‌شدهٔ تصویر پس‌زمینه + هندسهٔ تشخیصی.
    خروجی: {"arr": float RGBA (H,W,4) 0..1, "geom": dict, "W": int, "H": int}
    فایل نبود/خراب بود ⇒ None (تب خالی و امن می‌ماند).
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
            # مقیاس fallback در صورت تفاوت ابعاد فایل
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
            clog(f"[TVBg] خطای بارگذاری {path}: {type(ex).__name__}: {ex}")
        except Exception:
            pass
        # v2.1.0 — unreadable file: built-in fallback (charts stay alive)
        return tv_fallback_background_cached(kind)
        return None


def _tv_anchor_map(kind: str, geom: Dict[str, Any]):
    """لنگرهای افقی (px) + دقیقهٔ آن‌ها برای پنل — با fallback اندازه‌گیری‌شده."""
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
    نگاشت «دقیقهٔ مسابقه» → پیکسل افقی تصویر (نسخهٔ ۱۰٫۸ — کالیبره با تیک‌ها).
    لنگرها = تیک‌های تشخیص‌داده‌شدهٔ خود تصویر:
      half  (۴ تیک) : ۰/۱۵/۳۰/۴۵(HT)     ← HT دقیقاً روی تیک آخرِ راست
      full  (۷ تیک) : ۰/۱۵/۳۰/۴۵(HT)/۶۰/۷۵/۹۰
      extra (۹ تیک) : ۰..۹۰(FT)/۱۰۵(ET)/۱۲۰
    HT=۴۵ ، FT=۹۰ ، ET=۱۰۵ — نگاشت خطیِ تکه‌تکه بین تیک‌های مجاور؛
    فراتر از آخرین لنگر (وقت‌های تلف‌شده) ادامهٔ خطی با شیب همان قطعه.
    اگر تصویر تیک معتبری نداشت، تیک‌های اندازه‌گیری‌شدهٔ همان پنل با مقیاس
    عرض تصویر استفاده می‌شود.

    نسخهٔ ۱۰٫۹ — «دقیقه‌های مشترک»: اگر band داده شود ({"bound","s"})،
    دقیقه‌های وقت اضافه‌شدهٔ بخش قبلی به‌جای ادامهٔ خطی، در باند باریکی
    «سمت چپِ» خط مرز فشرده می‌شوند (نزدیک‌ترین نمونه ≈ ۱px قبل از خط) —
    یعنی وقت اضافهٔ نیمهٔ اول قبل از HT می‌نشیند، نه بعد از آن.
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
        # فراتر از آخرین لنگر → ادامهٔ خطی با شیب آخرین قطعه
        i = len(ms) - 1
        rate = (anchors[i] - anchors[i - 1]) / max(1e-9, (ms[i] - ms[i - 1]))
        return anchors[i] + (minute_ - ms[i]) * rate

    if band is not None:
        try:
            bnd = float(band.get("bound", 0.0))
            s_tot = float(band.get("s", 0.0))
        except (TypeError, ValueError):
            return _map_raw(minute)
        # شیب محلی دورِ مرز (برای ضخامت باند متناسب با مقیاس همان ناحیه)
        rate = (anchors[-1] - anchors[0]) / max(1e-9, (ms[-1] - ms[0]))
        for i in range(1, len(ms)):
            if ms[i - 1] <= bnd <= ms[i]:
                rate = (anchors[i] - anchors[i - 1]) / max(1e-9, (ms[i] - ms[i - 1]))
                break
        delta = max(0.4, TV_STOP_SQUEEZE_FRAC * rate)      # px به ازای هر دقیقه
        s_eff = min(max(0.0, s_tot), TV_STOP_BAND_CAP_MIN)
        x_bound = _map_raw(bnd)
        x_off = min(max(minute - bnd, 0.0), s_eff)         # 0..s_eff دقیقه داخل باند
        return x_bound - 1.0 - (s_eff - x_off) * delta

    return _map_raw(minute)


def _tv_timeline(hist: List[Dict[str, float]], restarts_out: Optional[Dict[float, bool]] = None):
    """
    نسخهٔ ۱۰٫۹ — گام مشترک محور زمانی TV (خالص و قابل‌تست).
    خروجی: (minutes, bands, band_idx)
      * minutes : دقیقهٔ بازی هر نمونه (NaN = نگهبان/نامعتبر — در رسم رد می‌شود)
      * bands   : لیست وقت‌های اضافه‌شدهٔ شناسایی‌شده:
                  {"bound": مرز (۴۵/۹۰/۱۰۵/۱۲۰), "gt0","gt1": بازهٔ game_time,
                   "s": طول وقت اضافه به دقیقه}
      * band_idx: ایندکس باند هر نمونه (-1 = عادی؛ ممکن است به باندِ دورریز
                  اشاره کند — سمت مصرف با گارد بررسی شود)

    منطق «دقیقه‌های مشترک» (۴۵-۵۰ / ۹۰-۹۷ / …) — نسخهٔ ۱۰٫۱۰ (شرط کاربر):
      * کد «اول» چک می‌کند که آیا بازی به دقیقهٔ ۴۵ یا ۹۰ ریست شده یا نه؛
        ری‌استارت یعنی: تایمر از دقیقهٔ مرز (۴۵:۰۰) رد شده و به عددی
        بزرگ‌تر رسیده و بعد از یک توقف، دوباره از خودِ ۴۵:۰۰ شروع به
        شمارش کرده است؛
      * تا وقتی این رویداد ثبت نشده، اتفاق‌های این پنجره (مثل گل دقیقهٔ ۴۶
        یا ۹۵) جزو «وقت اضافهٔ بخش قبلی» است (مثال کاربر: گل دقیقهٔ ۹۵
        بدون ری‌استارتِ ثبت‌شدهٔ ۹۰ = گل نیمهٔ دوم؛ بعد از ثبت ری‌استارت ۹۰
        = گل وقت اضافهٔ اول)؛
      * به محض «تأیید» ری‌استارت، بخش بعدی از خودِ خط مرز شروع به رسم
        می‌شود؛
      * توقف = شکاف زمان واقعی بین نمونه‌ها (نگهبان‌های NaN حداقل ۱۰ ثانیه
        شکاف دارند) «یا» جهش عقبروی بزرگ ساعت (ساعتِ فریز در بریک)؛
      * جهش‌های کوچک عقبرو (resync وسط بازی، بدون توقف) ⇒ کلمپ مونوتونیک.

    نسخهٔ ۱۰٫۱۳ — «تأیید ری‌استارت» (شرط کاربر):
      فرود روی مرز فقط «نامزدِ» ری‌استارت است؛ ثبت نهایی وقتی است که یک
      نمونهٔ واقعی (غیرنگهبان = بازی PLAYING و ساعت جلو رفته) با دقیقهٔ
      «بیشتر از خودِ مرز» برسد — یعنی بازی Playing شده و تایمر از مرز
      (۴۵/۹۰/۱۰۵) بیشتر شده باشد. تا قبل از تأیید، اتفاق‌های پنجرهٔ مشترک
      جزو وقت اضافهٔ بخش قبلی می‌مانند (مثال کاربر: ریست تایمر به ۹۰ در
      حالی که بازی هنوز به وقت اضافه نرفته ⇒ نمودار ET فراخوانی نمی‌شود).

    نسخهٔ ۱۰٫۱۵ — «چهار نوع ریست» (شرط صریح کاربر — رفع باگ فعال‌شدن ET
    به‌محض عبور از دقیقهٔ ۹۰ و ثبتِ گلِ وقت هدررفتهٔ نیمهٔ اول برای نیمهٔ دوم):
      ریست یعنی «ساعت بازی واقعاً سقوط کرده و روی مرز نشسته باشد»:
        الف) ریست به ۰۰:۰۰            → بازی جدید (Lifecycle — خارج از این تابع)
        ب) ریست به ۴۵:۰۰              → شروع نیمهٔ دوم
        ج) ریست به ۹۰:۰۰ از بالای ۹۰   → شروع نیمهٔ اول وقت اضافه
        د) ریست به ۱۰۵:۰۰ از بالای ۱۰۵ → شروع نیمهٔ دوم وقت اضافه
      و هر چهار نوع فقط وقتی «شروع یک بخش جدید»اند که بازی Playing شود و
      تایمر شروع به بالا رفتن کند (گام تأیید ۱۰٫۱۳ — تغییری نکرده است).
      پیامدها:
        * عبورِ صعودیِ تایمر از ۹۰:۰۰ (وقت هدررفتهٔ نیمهٔ دوم) هرگز ریست
          نیست — «سقوط به مرز» (m < prev_m) شرط اصلی است؛ استالِ چندثانیه‌ای
          کنار مرز (اعلان وقت اضافه/ضربه آزاد) دیگر ری‌استارت نمی‌سازد؛
        * برای ۹۰/۱۰۵ «بالاتر بودن قبلی از مرز» الزامی است (بند ج/د)؛
        * فرودِ بدون سقوط بعد از یک بریک بزرگ (خط لوله در لحظهٔ ریست مرده
          بوده — مثلاً اولین نمونهٔ نیمه دوم در ۴۸') فقط وقتی پذیرفته
          می‌شود که فاز Lifecycle (مُهر phase نمونه) بخش بعدی را تأیید کند؛
        * تا قبل از ریستِ تأییدشده، هر رویداد/نمونهٔ «وقت هدررفته» (بعد از
          دقیقهٔ نهایی هر بخش) جزو همان بخش است — نه بخش بعدی.
    """
    minutes: List[float] = []
    band_idx: List[int] = []
    bands: List[Dict[str, float]] = []
    cur: Optional[Dict[str, float]] = None
    bound_i = 0
    prev_m: Optional[float] = None
    prev_d: Optional[float] = None
    prev_gt: Optional[float] = None
    prev_w: Optional[float] = None      # نسخهٔ ۱۰٫۱۲ — wall نمونهٔ قبلی (بریک بزرگ)
    clamp_m: Optional[float] = None       # کلمپ مونوتونیک (فقط نمونه‌های واقعی)
    # نسخهٔ ۱۰٫۱۰ — وضعیت هر مرز: آیا تایمر از مرز رد شده (عدد بزرگ‌تر دیده)
    # و آیا ری‌استارتِ آن مرز ثبت شده است؟
    above = {B: False for B in TV_STOP_BOUNDS[:3]}
    restarted = {B: False for B in TV_STOP_BOUNDS[:3]}
    # نسخهٔ ۱۰٫۱۳ — نامزدهای ری‌استارت (فرود روی مرز) که هنوز «تأیید» نشده‌اند:
    #   B → {"d": disp لحظهٔ فرود، "up_to_m": آخرین دقیقهٔ قبل از فرود،
    #        "up_to_gt": آخرین game_time قبل از فرود}
    pending = {}

    def _finalize(c: Dict[str, float], up_to_m: float, d_restart=None) -> None:
        c["s"] = max(float(c.get("s", 0.0)), max(0.0, up_to_m - float(c["bound"])))
        if d_restart is not None and math.isfinite(float(d_restart)):
            c["d1"] = float(d_restart)     # لحظهٔ نمایشی ری‌استارت تایمر
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
        # نسخهٔ ۱۰٫۱۲ — زمان واقعی (Wall) نمونه برای آشکارسازی «بریک بزرگ»
        try:
            w = float(s.get("wall")) if s.get("wall") is not None else None
            if w is not None and not math.isfinite(w):
                w = None
        except (TypeError, ValueError):
            w = None
        m = gt / 60.0
        is_guard = (net != net)

        # --- ۱) تشخیص ری‌استارت تایمر — نسخهٔ ۱۰٫۱۵ (چهار نوع ریست کاربر) ---
        # ریست = «سقوط واقعی ساعت روی مرز» + توقف؛ نه استالِ صعودی کنار مرز.
        # جزئیات کامل در docstring بالا (بندهای الف تا د).
        if prev_m is not None:
            # شرط اصلی ریست (نسخهٔ ۱۰٫۱۵): سقوط واقعی تایمر به مرز
            is_drop = m < prev_m - 1e-9
            back_ok = math.isfinite(d) and \
                (prev_m - m) >= TV_RESTART_BACKJUMP_MIN
            # --- نسخهٔ ۱۰٫۱۲ — «بریک بزرگ»: سکوت واقعی ≥۳ دقیقه (خط لولهٔ
            # داده در برک HT ساکت است و اولین نمونهٔ نیمه دوم ممکن است دیر
            # فرود بیاید) یا شکاف نمایشی نگهبان‌ها (HT/resync). در این حالت
            # فرود تا انتهای پنجرهٔ مشترک پذیرفته می‌شود و جهش رو به جلوی
            # اولین نمونهٔ بریک (تأخیر خط لوله) ری‌استارت را رد نمی‌کند.
            wall_gap_ok = (prev_w is not None and w is not None
                           and (w - prev_w) >= TV_BREAK_WALL_SEC)
            try:
                disp_gap_ok = (math.isfinite(d) and prev_d is not None
                               and math.isfinite(prev_d)
                               and (d - prev_d) >= TV_RESTART_DISP_BREAK_SEC)
            except TypeError:
                disp_gap_ok = False
            big_break = bool(wall_gap_ok or disp_gap_ok)
            # توقف کوتاه واقعی (≥۴ ثانیه سکوت wall) برای مسیر «سقوط به مرز»
            wall_stop_ok = (prev_w is not None and w is not None
                            and (w - prev_w) >= TV_RESTART_GAP_SEC)
            for B in TV_STOP_BOUNDS[:3]:        # ۴۵ / ۹۰ / ۱۰۵
                if restarted.get(B):
                    continue
                from_above = above.get(B, False) and prev_m > B + 1e-9
                # «لبهٔ مرز» فقط برای ۴۵ (HT بدون وقت هدررفته — بند ب)؛
                # برای ۹۰/۱۰۵ حذف شد: عبور عادی تایمر از مرز در وقت هدررفتهٔ
                # نیمهٔ جاری نباید ری‌استارت بسازد (بندهای ج/د کاربر)
                from_edge = (B == 45.0) and \
                    ((B - TV_RESTART_EDGE_EPS) <= prev_m <= (B + 1e-9))
                if not (from_above or from_edge):
                    continue
                if big_break:
                    # فرود آزاد در کل پنجرهٔ مشترک (نمونهٔ اولِ بعد از بریک)
                    if not ((B - TV_RESTART_LAND_BELOW) <= m
                            <= (B + TV_STOP_WINDOW[B])):
                        continue
                    # نسخهٔ ۱۰٫۱۵ — فرودِ «بدون سقوط» بعد از بریک بزرگ (خط
                    # لوله در لحظهٔ ریست مرده بوده) فقط وقتی معتبر است که
                    # فاز Lifecycle هم بخش بعدی را تأیید کند؛ وگرنه وقفهٔ
                    # بلندِ وسط وقت هدررفته (همچنان در همان بخش) ری‌استار
                    # نمی‌سازد. (تاریخچهٔ بدون مُهر phase = رفتار قبلی)
                    if from_above and not is_drop and \
                            not tv_phase_allows_restart(B, s.get("phase")):
                        continue
                else:
                    if not ((B - TV_RESTART_LAND_BELOW) <= m
                            <= (B + TV_RESTART_LAND_EPS)):
                        continue
                    if m > prev_m + TV_RESTART_LAND_EPS:
                        continue                 # جهش رو به جلو ≠ ری‌استارت
                    if from_above and not is_drop:
                        # نسخهٔ ۱۰٫۱۵ — شرط کاربر: بالای مرز بودن به‌تنهایی
                        # کافی نیست؛ تایمر باید واقعاً «سقوط» کرده باشد.
                        # استال صعودی کنار مرز (اعلان وقت اضافه و…) هرگز
                        # ری‌استارت نیست — ریشهٔ باگ ET در عبور از ۹۰ و ثبت
                        # گل وقت هدررفته برای بخش بعدی.
                        continue
                    if from_edge:
                        # پایان عادی روی مرز (HT بدون وقت هدررفته): فقط با
                        # بریک واقعی (شکاف ≥۳۰s — نه استال نمونه‌برداری)
                        gap_ok = (prev_d is not None and math.isfinite(prev_d)
                                  and math.isfinite(d)
                                  and (d - prev_d) >= TV_RESTART_EDGE_GAP_SEC)
                        if not (gap_ok or back_ok):
                            continue
                    else:
                        # سقوط واقعی به مرز + توقف (شکاف ≥۴s / سکوت wall /
                        # جهش عقبروی ساعت — حالت ساعتِ فریز در بریک)
                        gap_ok = (prev_d is not None and math.isfinite(prev_d)
                                  and math.isfinite(d)
                                  and (d - prev_d) >= TV_RESTART_GAP_SEC)
                        if not (gap_ok or back_ok or wall_stop_ok):
                            continue
                # --- نسخهٔ ۱۰٫۱۳ — فرود فقط «نامزد» است؛ ثبت نهایی بعد از
                # تأیید شرط کاربر انجام می‌شود (Playing + تایمر > مرز).
                # up_to_m/up_to_gt = آخرین وضعیت قبل از فرود (برای تکمیل باند).
                pending[B] = {"d": d, "up_to_m": prev_m, "up_to_gt": prev_gt}
                # لنگر ریست تایمر: کلمپ مونوتونیکِ «قبل از مرز» از همین لحظه
                # بی‌اعتبار است (نمونه‌های روی مرز = شروع شمارش جدید؛ رفتار
                # ثبت-در-فرودِ نسخه‌های قبل حفظ می‌شود)
                clamp_m = None
                break

        # --- ۱-آ) تأیید ری‌استارت نامزد (نسخهٔ ۱۰٫۱۳ — شرط کاربر) ---
        # نمونهٔ واقعی (غیرنگهبان) یعنی بازی PLAYING است و ساعت جلو رفته؛
        # «Playing + تایمر از مرز بیشتر» = بخش بعدی واقعاً شروع شده است.
        if pending and not is_guard:
            for B in TV_STOP_BOUNDS[:3]:
                pd = pending.get(B)
                if pd is None or restarted.get(B):
                    continue
                if m <= B + 1e-9:
                    continue                    # تایمر هنوز از مرز نگذشته
                if cur is not None:
                    _finalize(cur, pd["up_to_m"], d_restart=pd["d"])
                    cur = None
                elif bands and bands[-1]["bound"] == B:
                    # باندِ بسته‌شده با «فرار از پنجره» — تا لحظهٔ فرود تکمیل شود
                    bands[-1]["gt1"] = pd["up_to_gt"] \
                        if pd["up_to_gt"] is not None else bands[-1]["gt1"]
                    bands[-1]["s"] = max(float(bands[-1]["s"]),
                                         max(0.0, float(pd["up_to_m"]) - B))
                    if math.isfinite(pd["d"]):
                        bands[-1]["d1"] = float(pd["d"])
                bound_i = max(bound_i, min(TV_STOP_BOUNDS.index(B) + 1,
                                           len(TV_STOP_BOUNDS) - 1))
                restarted[B] = True              # تأیید شد — ری‌استارت ثبت شد
                above[B] = False
                clamp_m = None                   # کلمپ در مرز جدید ریست می‌شود
                del pending[B]

        # --- ۱-ب) ثبت «تایمر از مرز رد شده» (عدد بزرگ‌تر از مرز دیده شد) ---
        for B in TV_STOP_BOUNDS[:3]:
            if not above.get(B, False) and m > B + 1e-9:
                above[B] = True

        # --- ۲) فرار از پنجرهٔ دقیقه‌های مشترک → مرز بعدی ---
        while (bound_i < len(TV_STOP_BOUNDS) - 1
               and m > TV_STOP_BOUNDS[bound_i] + TV_STOP_WINDOW[TV_STOP_BOUNDS[bound_i]]):
            if cur is not None:
                _finalize(cur, m)
                cur = None
            bound_i += 1

        # --- ۳) باز/امتداد باند وقت اضافهٔ بخش فعلی ---
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
            bi = len(bands)          # اندیس باندِ در حال باز پس از نهایی‌شدن

        # --- ۴) خروجی دقیقه (کلمپ مونوتونیک فقط برای نمونه‌های واقعی) ---
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
    نسخهٔ ۱۰٫۹ — محور «دقیقهٔ مسابقه» برای هر نمونهٔ history بر پایهٔ
    game_time خام (ساعت بازی). چون لنگرهای تصویر دقیقهٔ مطلق مسابقه‌اند
    (HT=۴۵ ، FT=۹۰ ، ET=۱۰۵)، شکاف HT به‌طور طبیعی روی خط HT می‌نشیند و
    دو نیمه دقیقاً از محل HT به هم می‌چسبند (کالیبراسیون دوباره هنگام
    عوض‌شدن تصویر خودکار است).
      * نمونه‌های NaN نگهبان → NaN (در رسم رد می‌شوند)
      * ری‌استارت تایمر (۴۵→۴۵ / ۹۰→۹۰ / ۱۰۵→۱۰۵ پس از شکاف دوره) →
        دقیقه‌های بخش جدید از خودِ مرز ادامه می‌یابد (کلمپِ بین‌بخشی حذف شد)
      * جهش‌های عقبرؤ ساعت (resync وسط بازی) → کلمپ مونوتونیک
    """
    return _tv_timeline(hist)[0]


def tv_stop_bands(hist: List[Dict[str, float]]) -> List[Dict[str, float]]:
    """نسخهٔ ۱۰٫۹ — فهرست «وقت‌های اضافه‌شده» (دقیقه‌های مشترک) هر بخش.
    خروجی: [{"bound": ۴۵/۹۰/۱۰۵/۱۲۰, "gt0","gt1": بازهٔ game_time, "s": طول}]"""
    return _tv_timeline(hist)[1]


def tv_restart_flags(hist: List[Dict[str, float]]) -> Dict[float, bool]:
    """نسخهٔ ۱۰٫۱۳ — کدام مرزها ری‌استارتِ «تأییدشده» دارند (۴۵/۹۰/۱۰۵).
    تأیید = فرود روی مرز + بعدش یک نمونهٔ واقعی (PLAYING، ساعت صعودی) با
    دقیقهٔ بیشتر از خودِ مرز دیده شده باشد (شرط کاربر برای «شروع واقعی
    بخش بعدی»). فرودِ بدون تأیید (مثلاً ریست تایمر به ۹۰ وقتی بازی ادامه
    نیافته) اینجا False است و نمودار بخش بعدی فراخوانی نمی‌شود."""
    out: Dict[float, bool] = {}
    try:
        _tv_timeline(hist, restarts_out=out)
    except Exception:
        pass
    return out


def tv_band_for_time(bands: List[Dict[str, float]], gt: float,
                     disp: Optional[float] = None) -> Optional[Dict[str, float]]:
    """باندِ وقت اضافه‌ای که این game_time داخل آن افت می‌کند (None = عادی).
    نسخهٔ ۱۰٫۹ — دقیقه‌های مشترک دو بار دیده می‌شوند؛ مرز تشخیص «گذر اول/دوم»
    disp_time است (لحظهٔ ری‌استارت تایمر در باند ذخیره می‌شود): اگر نمونه/
    مارکر بعد از ری‌استارت باشد، دیگر داخل باندِ وقت اضافهٔ بخش قبل نیست."""
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
            continue                          # گذر دوم (بعد از ری‌استارت) → عادی
        return b
    return None


def tv_marker_minute(mk: Dict[str, Any]) -> Optional[float]:
    """دقیقهٔ مسابقهٔ یک مارکر گل — بر پایهٔ game_time خام (همان محور تیک‌ها)."""
    try:
        gt = float(mk.get("game_time", float("nan")))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(gt):
        return None
    return gt / 60.0


def _tv_internal_verticals(kind: str, geom: Dict[str, Any]) -> List[float]:
    """
    خطوط عمودی سرتاسری که باید «روی fill» بازکشیده شوند (مثل تصویر نمونه —
    فقط خطوط نام‌دار HT/FT/ET، نه تیک‌های ۱۵ دقیقه‌ای):
      پنل full : خط HT (۴۵′)
      پنل extra: خطوط HT (۴۵′) + FT (۹۰′) + ET (۱۰۵′)
      پنل half : HT روی لبهٔ راست است → هیچ
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
    آماده‌سازی لوگو/پرچم برای تب TV (نسخهٔ ۱۰٫۸ — عین تصویر نمونه):
      * برش به «قسمت رنگی» فایل (حذف حاشیهٔ شفاف) — استروک دور محتوای رنگی
        احاطه می‌شود، نه دور کل عکس
      * استروک سفید خیلی نازک (≈۳px) با فاصلهٔ کم (≈۲px) از محتوا — مثل نمونه
      * سقف اندازه: لوگو+استروک هرگز بزرگ‌تر از فضای مشکی نمی‌شود
    خروجی آرایهٔ RGBA float 0..1 — کش بر اساس (path, mtime).
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
        # --- برش به محتوای رنگی (پیکسل‌های با آلفای معنادار) ---
        a_arr = np.asarray(im)[:, :, 3]
        ys, xs = np.where(a_arr >= 8)
        if len(ys) == 0:
            _tv_flag_cache[path] = (mt, None)
            return None
        im = im.crop((int(xs.min()), int(ys.min()),
                      int(xs.max()) + 1, int(ys.max()) + 1))
        # --- مقیاس محتوا (۲ برابر برای استروک نرم و گوشه‌های تمیز) ---
        ss = 2
        w, h = im.size
        scale = min(TV_FLAG_CONTENT_W * ss / max(1, w),
                    TV_FLAG_CONTENT_MAX_H * ss / max(1, h))
        nw, nh = max(2, int(round(w * scale))), max(2, int(round(h * scale)))
        im = im.resize((nw, nh), Image.Resampling.LANCZOS)
        alpha = im.getchannel("A")

        # --- استروک حلقوی با فاصله: دیلیت دقیق ماسک آلفا (با نگه‌داشتن حاشیه) ---
        k_gap = max(1, TV_FLAG_GAP_PX * ss)
        k_out = max(k_gap + 1, (TV_FLAG_GAP_PX + TV_FLAG_STROKE_PX) * ss)

        def _dilate(mask, k):
            # MaxFilter دقیق؛ خروجی = اندازهٔ محتوا + ۲k (حاشیهٔ دیلیت حفظ می‌شود)
            w0, h0 = mask.size
            pad = k + 2
            big = Image.new("L", (w0 + 2 * pad, h0 + 2 * pad), 0)
            big.paste(mask, (pad, pad))
            d = big.filter(_ImageFilter.MaxFilter(2 * k + 1))
            a0 = pad - k
            return d.crop((a0, a0, a0 + w0 + 2 * k, a0 + h0 + 2 * k))

        d_out = _dilate(alpha, k_out)              # = بوم نهایی (nw+2m × nh+2m)
        d_gap = _dilate(alpha, k_gap)              # کوچک‌تر — هم‌مرکز می‌شود
        d_gap_pad = Image.new("L", d_out.size, 0)
        d_gap_pad.paste(d_gap, (k_out - k_gap, k_out - k_gap))
        ring = _ImageChops.subtract(d_out, d_gap_pad)
        ring = ring.filter(_ImageFilter.GaussianBlur(1.2))   # لبه/گوشهٔ نرم
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
        clog(f"[TVFlag] خطای پردازش {path}: {type(ex).__name__}: {ex}")
        out = None
    _tv_flag_cache[path] = (mt, out)
    return out


# --- کمک‌کارهای نسخهٔ ۱۰٫۸ (خالص و قابل‌تست بدون بازی) ---

def _tv_lighten(color, f: float = 0.35):
    """(نسخهٔ ۱۰٫۱۰ — خط لبهٔ fill حذف شد؛ تابع فقط برای سازگاری نگه داشته شده.)"""
    try:
        from matplotlib import colors as _mcolors
        r, g, b = _mcolors.to_rgb(color)
    except Exception:
        r, g, b = 1.0, 1.0, 1.0
    return (r + (1.0 - r) * f, g + (1.0 - g) * f, b + (1.0 - b) * f)


def _tv_split_sign_segments(px: "np.ndarray", py: "np.ndarray", zero_y: float):
    """
    شکستن منحنی به پاره‌های مثبت/منفی نسبت به خط صفر — نقطهٔ عبور از صفر
    با درون‌یابی به هر دو پاره اضافه می‌شود (fill/گلو/لبه بدون پرش).
    خروجی: (pos_segs, neg_segs) — هر پاره = (xs, ys) آرایهٔ numpy.
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
    میانگین‌گیری نمونه‌ها داخل هر ستون پیکسلی (عرض step) — حذف ارتعاش
    زیرپیکسلیِ لبهٔ fill («دندانه»). خروجی (bx, by) با طول ≤ عرض مستطیل/step.
    """
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    if len(px) < 8:
        return px, py
    bi = np.floor(px / max(0.2, float(step))).astype(np.int64)
    b0 = int(bi.min())
    nb = int(bi.max()) - b0 + 1
    if nb >= len(px):            # تراکم پایین — میانگین‌گیری بی‌فایده
        return px, py
    cnt = np.bincount(bi - b0, minlength=nb).astype(float)
    sx = np.bincount(bi - b0, weights=px, minlength=nb)
    sy = np.bincount(bi - b0, weights=py, minlength=nb)
    m = cnt > 0
    return sx[m] / cnt[m], sy[m] / cnt[m]


def _tv_extra_edge_smooth(by: "np.ndarray", sigma_samples: float,
                          max_shift: float = None) -> "np.ndarray":
    """نسخهٔ ۱۰٫۱۶ — هموارسازی اضافهٔ «لبهٔ» نمودار (بند ۳-الف شرط کاربر):
    گاوسیِ تک‌بعدی روی ارتفاع ستون‌های پس از binning؛ سیگما بر حسب «نمونه»
    (هر نمونه ≈ TV_BIN_STEP_PX پیکسل). ورودی کاربر از کادر متنی موقت
    کنار نمودار می‌آید (TV_EDGE_SMOOTH_PX بر حسب پیکسل)؛ عدد نهایی بعداً
    هاردکد خواهد شد. این لایه فقط نمایشی است — فرمول مومنتوم دست‌نخورده.
    نسخهٔ ۱۰٫۱۷ — «حفظ شکل» (شرط کاربر: نرمی فقط برای لبه است، نه تغییر
    شکل نمودار): گاوسیِ خام قله‌ها را گرد و ارتفاع‌ها را جابه‌جا می‌کند؛
    این‌جا خروجی گاوسی با «کلمپ نرم tanh» به مقدار اصلی محدود می‌شود:
        delta = lim · tanh((smooth − original) / lim)
    یعنی جابه‌جایی‌های کوچک (دندانه‌های زیرپیکسلی) کاملاً اعمال می‌شوند
    (لبه صاف می‌شود) ولی هیچ ستونی بیش از lim (≈TV_EDGE_SMOOTH_MAX_SHIFT_PX
    پیکسل) از مقدار اصلی دور نمی‌شود ⇒ قله‌ها/دره‌ها و شکل کلی سر جایشان
    می‌مانند. max_shift=None → رفتار قدیمی (بدون کلمپ؛ برای تست‌ها)."""
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
    """نسخهٔ ۱۰٫۲۵ — بازنمونه‌برداری منحنی روی شبکهٔ افقی «یکنواخت».
    خروجی binning، ستون‌هایی با مرکزهای ناهم‌فاصله می‌دهد (مرکز = میانگین x
    نمونه‌های همان ستون)؛ پلی‌لاین بین این مرکزها، لبهٔ fill را پله‌پله
    می‌کند. این‌جا منحنی با درون‌یابی خطی روی شبکهٔ ثابت step پیکسلی
    نمونه‌برداری می‌شود ⇒ فاصلهٔ نقاط همیشه یکنواخت، لبهٔ پیوسته.
    مقدارها از «همان» منحنی binning می‌آیند ⇒ هیچ قله/دره‌ای جابه‌جا
    یا حذف نمی‌شود (فقط بازچینش نقطه‌ها روی x یکنواخت)."""
    try:
        bx = np.asarray(bx, dtype=float)
        by = np.asarray(by, dtype=float)
    except Exception:
        return bx, by
    if bx.size < 8 or bx.size != by.size:
        return bx, by
    step = max(0.1, float(step))
    try:
        # xp برای np.interp باید اکیداً صعودی باشد — نسخهٔ اول هر تکرار
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
    """نسخهٔ ۱۰٫۲۶ — شیب‌های هermite مونوتون (Fritsch–Carlson) برای PCHIP.
    خروجی: شیب (dy/dx) در هر گره؛ تضمین: هیچ فراجوشی (overshoot) بین دو
    گرهٔ مجاور ایجاد نمی‌شود ⇒ شکل داده (قله/دره/پلهٔ واقعی) عیناً حفظ
    می‌شود — فقط شیب بین گره‌ها «پیوسته» می‌شود."""
    h = np.diff(bx)
    d = np.diff(by) / h
    m = np.zeros_like(by)
    m[0], m[-1] = d[0], d[-1]
    for i in range(1, len(by) - 1):
        if d[i - 1] * d[i] <= 0.0:
            m[i] = 0.0                     # اکسترمم محلی — شیب صفر
        else:
            w1 = 2.0 * h[i] + h[i - 1]
            w2 = h[i] + 2.0 * h[i - 1]
            m[i] = (w1 + w2) / (w1 / d[i - 1] + w2 / d[i])
    return m


def _tv_pchip_eval(bx: "np.ndarray", by: "np.ndarray",
                   gx: "np.ndarray") -> "np.ndarray":
    """ارزیابی چندجمله‌ای هرمیت مکعبی روی شبکهٔ gx (bx صعودی فرض می‌شود)."""
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
    """نسخهٔ ۱۰٫۲۶ — بازنمونه‌برداری «مکعبی مونوتون» روی شبکهٔ یکنواخت.
    ریشهٔ واقعی «پله‌پله»: نسخهٔ خطی (np.interp) بین گره‌های ~۰٫۹ پیکسلی،
    شیب را در «هر گره» ناگهانی عوض می‌کند ⇒ اسکالوپینگِ مقیاس پیکسل ⇒
    پله‌های نامنظم و کلوخه‌ای در زوم. درون‌یابی PCHIP: از «همهٔ» گره‌ها
    می‌گذرد (ارتفاع قله/دره عین قبل)، مونوتون است (هیچ فراجوششی ندارد)،
    و شیب بین گره‌ها پیوسته است ⇒ لبهٔ رستری یکنواخت و ابریشمی می‌شود.
    تغییر شکل نسبت به نسخهٔ خطی ≤ دامنهٔ اسکالوپ (~۰٫۳px) — نامرئی."""
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
    """نسخهٔ ۱۰٫۲۵ — گاوسیِ «زیرپیکسلی» روی ارتفاع ستون‌های شبکهٔ یکنواخت.
    فقط ارتعاش ستونیِ مقیاس ~۱ پیکسل حذف می‌شود؛ چون سیگما (‎۰٫۶px‎) ده‌ها
    بار کوچک‌تر از عرض ویژگی‌های نمودار (قله/دره ≥ ~۱۰px) است، افت ارتفاع
    قله‌ها < ۰٫۲٪ و جابه‌جایی صفر است — فرم کلی نمودار عین قبل می‌ماند.
    (خنثی بودن روی شکل با تست «انحراف هندسه» هم verify می‌شود.)"""
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


# --- نسخهٔ ۱۰٫۱۵ — حذف «هالهٔ افقی» کنار خط صفر (شرط کاربر) ---
# وقتی منحنی برای مدتی چسبیده به خط صفر حرکت می‌کند، درخشش نئونِ همان قسمت
# یک نوار افقیِ کشیده و اضافه روی خط صفر می‌سازد (کاربر: «هالهٔ رنگ میزبان
# در وسط نمودار»). درمان: وزن هر ستون = فاصلهٔ منحنی تا خط صفر در همان
# ستون؛ نزدیکِ صفر → درخشش حذف، دور از صفر → درخشش کامل.
TV_GLOW_ZERO_NEAR_PX = 5.0     # (پیش‌فرض سازگاری — مسیر رندر از آستانهٔ «واحدی» استفاده می‌کند)
TV_GLOW_ZERO_FAR_PX = 30.0     # فاصلهٔ بیشتر از این → درخشش کامل
TV_GLOW_ZERO_SPREAD_PX = 24.0  # شعاع گسترش افقی فاصله (عبورهای تند از صفر حفظ شوند)
# --- نسخهٔ ۱۰٫۱۶ — ریشهٔ واقعی «هاله» پیدا شد ---
# آستانهٔ قدیمی (۵ تا ۳۰ پیکسل ≈ ۳ تا ۱۶ واحد) هرگز درخششِ منحنی‌های
# ۱۰-۲۰ واحدی (۲۰-۴۰ پیکسلی) را نمی‌کشت — همان نوار افقیِ رنگی کنار خط
# صفر که کاربر دوباره گزارش کرد. آستانهٔ جدید بر حسب «واحد ارتفاع نمودار»
# است (نه پیکسل) تا با مقیاس پویا هم درست بماند:
TV_GLOW_ZERO_NEAR_VAL = 18.0   # نزدیک‌تر از ۱۸ واحد → بدون درخشش (هاله حذف)
TV_GLOW_ZERO_FAR_VAL = 42.0    # دورتر از ۴۲ واحد → درخشش کامل


def _tv_zero_fade_weight(segs, hw: int, sc: float, zero_y: float,
                         gs: float, near_px: float = None,
                         far_px: float = None) -> "np.ndarray":
    """وزن ۰..۱ هر ستون تصویر برای میرایی درخششِ چسبیده به خط صفر.
    فاصلهٔ منحنی تا خط صفر per-column محاسبه، افقی گسترش (max-filter) و
    نرم می‌شود تا عبورهای تند از صفر (که فاصله در یک ستون صفر است) درخشش
    خود را از دست ندهند؛ فقط قسمت‌های «چسبیده به صفر» بی‌هاله می‌شوند.
    نسخهٔ ۱۰٫۱۶ — near_px/far_px اختیاری: مسیر رندر واقعی آستانه را بر
    حسب «واحد ارتفاع نمودار» (TV_GLOW_ZERO_NEAR/FAR_VAL ÷ مقیاس پویا)
    می‌فرستد؛ بدون آرگومان = ثابت‌های قدیمی پیکسلی (سازگاری تست‌ها)."""
    INF = 1e9
    d = np.full(int(hw), INF, dtype=float)
    for (xs, ys) in (segs or []):
        if xs is None or len(xs) < 1:
            continue
        xs_f = np.asarray(xs, dtype=float)
        ys_f = np.asarray(ys, dtype=float)
        # متراکم‌سازی: فاصلهٔ تا صفر باید «در تمام ستون‌های بین نقاط» هم
        # درست باشد (نه فقط در نقاط خود منحنی) — در غیر این صورت با ورودی
        # کم‌تراکم، هالهٔ بین دو نقطه زنده می‌ماند
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
    d = np.minimum(d, TV_GLOW_ZERO_FAR_PX * gs * sc * 4.0)   # سقف برای گسترش
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
    try:                                   # لبه‌های وزن نرم شود
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
    """نسخهٔ ۱۰٫۲۴ — بدنهٔ محاسباتیِ درخشش نئون (بدون ax/matplotlib):
    ماسک خط منحنی با «بلور گاوسی واقعی» در نیم‌وضوح + میرایی ستونی کنار
    خط صفر — خروجی: [(rgba_float، رنگ)، ...] به ترتیب میزبان/مهمان.
    هم _tv_draw_glow (مسیر matplotlib) و هم scene-builder GPU از همین
    استفاده می‌کنند تا درخشش در هر دو مسیر «مو‌به‌مو» یکی باشد.
    (ریاضی عیناً از _tv_draw_glow نسخهٔ ۱۰٫۱۶ کپی شده است.)"""
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
        return layers                  # شدت صفر — کاربر درخشش را خاموش کرده
    hw, hh = max(2, int(W) // 2), max(2, int(H) // 2)
    sc = hw / float(W)                      # مقیاس نیم‌وضوح
    gs = rect_h / 560.0                     # مقیاس با ارتفاع مستطیل
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
            sig = max(0.6, sig_base * gs * sc * soft_mul)   # ۱۰٫۱۶ — نرمی
            bl = np.asarray(mask.filter(_IFilter.GaussianBlur(sig)),
                            dtype=float) / 255.0
            acc += bl * (float(peak) * inten_mul)           # ۱۰٫۱۶ — شدت
        np.clip(acc, 0.0, 1.0, out=acc)
        # --- نسخهٔ ۱۰٫۱۵/۱۰٫۱۶ — میرایی هالهٔ کنار خط صفر (per-column) ---
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
    درخشش نئون نرم (نسخهٔ ۱۰٫۸): ماسک خط منحنی با «بلور گاوسی واقعی» —
    روشنایی از خط به بیرون به‌صورت کاملاً نرم محو می‌شود (بدون پله).
    ماسک در نیم‌وضوح ساخته می‌شود (بلور کم‌بسامد است) → سریع و صاف.
    نسخهٔ ۱۰٫۱۵ — درخششِ هر رنگ در ستون‌هایی که منحنی همان رنگ چسبیده به
    خط صفر است میرا می‌شود (حذف هالهٔ افقی اضافه — شرط کاربر).
    نسخهٔ ۱۰٫۱۶ — پیچ‌های موقت کاربر: TV_GLOW_SOFTNESS_MUL (سیگمای بلور)
    و TV_GLOW_INTENSITY_MUL (آلفای اوج)؛ شدت صفر → درخشش اصلاً رسم
    نمی‌شود. near_px/far_px → آستانهٔ «واحدی» حذف هاله (بند ۴).
    نسخهٔ ۱۰٫۲۴ — ریاضی به _tv_glow_layers منتقل شد (مشترک با مسیر GPU)؛
    خروجی این تابع پیکسل‌به‌پیکسل مثل قبل است.
    خروجی: تعداد لایه‌های درخشش رسم‌شده.
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
    """نسخهٔ ۱۰٫۲۴ — محاسبهٔ درخشش سفید دور «خط عمودی گل + آیکون توپ»
    (بدون ax): ماسک محلی + بلور گاوسی در دو لایه — خروجی rgba نیمه‌باز +
    مختصات دقیقش در فضای پنل (x0, y0, x1, y1) برای imshow یا Quad GPU.
    (ریاضی عیناً از _tv_draw_marker_glow نسخهٔ ۱۰٫۹.)"""
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
    rgba[..., 0] = rgba[..., 1] = rgba[..., 2] = 1.0     # سفید
    rgba[..., 3] = acc
    return {"rgba": rgba, "x0": float(x0), "y0": float(y0),
            "x1": float(x1), "y1": float(y1)}


def _tv_draw_marker_glow(ax, gx: float, y_line0: float, y_line1: float,
                         ball_cy: float, ball_r: float, clip,
                         rect_h: float, gid: str) -> int:
    """
    نسخهٔ ۱۰٫۹ — درخشش نرمِ سفید دور «خط عمودی گل + آیکون توپ».
    ماسک محلی (خط + دایرهٔ توپ) با بلور گاوسی واقعی در دو لایه — هالهٔ
    سفید کاملاً نرم که از خط به بیرون محو می‌شود (بدون پله). لایه زیر
    خط صفر (zorder ۵ < ۶) است تا خط صفر/راهنماها هیچ‌گاه مات نشوند.
    نسخهٔ ۱۰٫۲۴ — ریاضی به _tv_marker_glow_calc منتقل شد (مشترک با GPU)؛
    خروجی پیکسل‌به‌پیکسل مثل قبل است.
    خروجی: ۱ اگر رسم شد وگرنه ۰.
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
    """نسخهٔ ۱۰٫۲۴ — رندر «یک‌جا»ی مُهر تاریخ/ساعت (قرص + متن) به بیت‌مپ
    RGBA برش‌خورده — تولید تصویر ثابت (خارج از مسیر نمایش زنده). خروجی برای
    Quad تکستچر GPU؛ مرکز بیت‌مپ = مرکز قرص (مثل ax.text با ha/va=center).
    فونت/اندازه/پد عیناً همان پارامترهای درون‌نموداری است (dpi=100)."""
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
    """نسخهٔ ۱۰٫۲۴ — پایهٔ «مشترک» ریاضیِ منحنی TV (بدون هیچ matplotlib).
    هم draw_tv_momentum (مسیر تب/رندر PNG) و هم scene-builder رندر برداری GPU
    از «همین» تابع استفاده می‌کنند تا شکل منحنی در هر دو مسیر مو‌به‌مو یکی
    باشد (شرط کاربر: تغییر شکل نمودار ممنوع — فقط رندر برداری با AA واقعی).
    خروجی: dict شامل هندسهٔ پنل + مختصات منحنی (bx/by) + پاره‌های مثبت/منفی +
    مقیاس پویا + آستانه‌های درخشش؛ یا None وقتی پس‌زمینه در دسترس نیست."""
    if bg is None:
        return None
    arr, geom = bg["arr"], bg["geom"]
    H, W = bg["H"], bg["W"]
    l, r, t, b = geom["rect"]
    zero_y = geom["zero_y"]
    rect_h = max(1.0, float(b - t))

    # --- snapshot اتمیک ---
    with momentum._lock:
        hist = list(momentum.history)
        markers = [dict(m) for m in momentum.hook_goal_markers]
        # نسخهٔ ۱۰٫۲۷ — مارکرهای کارت قرمز (getattr: سازگاری با موتورهای شبه)
        rc_markers = [dict(m) for m in
                      (getattr(momentum, "red_card_markers", None) or [])]

    # --- نسخهٔ ۱۰٫۱۶ — مقیاس عمودی «پویا» — پیش‌فرض: حداقل (±150) ---
    axis_scale = float(TV_SCALE_MIN)
    bx = by = None
    pos_segs = neg_segs = None
    near_px = far_px = None
    bands = []

    if len(hist) >= 2:
        # نسخهٔ ۱۰٫۹ — تایم‌لاین restart-aware: دقیقه‌ها + باندهای «دقیقه‌های مشترک»
        minutes_all, bands, band_of = _tv_timeline(hist)
        step = max(1, len(hist) // 3000)
        idxs = list(range(0, len(hist), step))
        if idxs[-1] != len(hist) - 1:
            idxs.append(len(hist) - 1)
        smin, sval, sgame, sband = [], [], [], []
        for i in idxs:
            m = minutes_all[i]
            if m != m:
                continue               # نگهبان NaN — رد
            smin.append(float(m))
            try:
                sgame.append(float(hist[i].get("game_time", 0.0)))
            except (TypeError, ValueError):
                sgame.append(0.0)
            sval.append(float(hist[i]["net"]))   # نسخهٔ ۱۰٫۱۵ — مقدار خام
            _bi = band_of[i]
            sband.append(bands[_bi] if 0 <= _bi < len(bands) else None)

        if len(smin) >= 2:
            # --- نسخهٔ ۱۰٫۱۶ — مقیاس عمودی «پویا» (شرط کاربر — بند ۱) ---
            soft = max(1.0, float(getattr(cfg, "DISPLAY_SOFT_SCALE", 120.0)))
            vals = np.asarray(
                [TV_Y_RANGE * math.tanh(float(v) / soft) for v in sval],
                dtype=float)
            mins = np.asarray(smin, dtype=float)

            # --- هموارسازی گاوسی نمایشی (صاف‌تر از نمودار اصلی — خواستهٔ کاربر) ---
            gt_arr = np.asarray(sgame, dtype=float)
            dts = np.diff(gt_arr)
            dts = dts[dts > 0]
            eff_dt = float(np.median(dts)) if len(dts) else \
                float(getattr(cfg, "HISTORY_SAMPLE_INTERVAL", 1.0))
            sigma_samples = TV_SMOOTH_SIGMA_SEC / max(0.02, eff_dt)
            sm = np.asarray(_gauss_smooth_impl(vals.tolist(), sigma_samples),
                            dtype=float)

            # --- نسخهٔ ۱۰٫۱۶ — محاسبهٔ مقیاس پویا ---
            data_peak = float(np.max(np.abs(vals))) if vals.size else 0.0
            axis_scale = max(float(TV_SCALE_MIN),
                             data_peak + float(TV_SCALE_MARGIN))

            px = np.asarray([tv_minute_to_x(bg_kind, geom, m, bnd)
                             for m, bnd in zip(mins, sband)], dtype=float)
            span = np.where(sm >= 0, zero_y - t, b - zero_y)
            py = zero_y - (sm / axis_scale) * span

            # --- نسخهٔ ۱۰٫۲۵ — «شبکهٔ یکنواخت از مبدأ»: منحنیِ هموارشدهٔ
            # گاوسی (σ=۳۵ثانیه ≈ ۱۸٫۶px) از قبل در مقیاس زیرپیکسلی صاف است؛
            # مستقیم روی شبکهٔ ثابت ۰٫۵px بازنمونه می‌شود — بدون عبور از
            # binningِ ۱٫۵px (مرکزهای لرزان ستونی = مبدأ دندانه). درون‌یابی
            # خطی بین نمونه‌های اصلی = همان پلی‌لاین قبلی، فقط با x یکنواخت؛
            # بعد گاوسی میکرون (۰٫۸px) فقط برای لبهٔ ابریشمی — قله/دره و
            # شکل کلی (ویژگی‌های ≥ ~۱۸px) دست‌نخورده می‌مانند.
            bx, by = _tv_uniform_resample_c1(px, py, TV_CURVE_GRID_STEP_PX)
            by = _tv_micro_edge_smooth(by, TV_EDGE_MICRO_SIGMA_PX,
                                       TV_CURVE_GRID_STEP_PX)
            # --- نسخهٔ ۱۰٫۱۷ — کلمپ نرم (فقط وقتی کاربر عدد داده باشد) ---
            if TV_EDGE_SMOOTH_PX > 0.0:
                by = _tv_extra_edge_smooth(
                    by,
                    TV_EDGE_SMOOTH_PX / max(0.2, float(TV_CURVE_GRID_STEP_PX)),
                    max_shift=TV_EDGE_SMOOTH_MAX_SHIFT_PX
                    / max(0.2, float(TV_CURVE_GRID_STEP_PX)))

            if len(bx) >= 2:
                pos_segs, neg_segs = _tv_split_sign_segments(bx, by, zero_y)
                # نسخهٔ ۱۰٫۱۶ — آستانهٔ حذف هاله بر حسب «واحد ارتفاع نمودار»
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
    رندر کامل تب TV روی ax (پیکسل‌محور) — نسخهٔ ۱۰٫۹:
      * محور X کالیبره با تیک‌های خود تصویر (HT=۴۵′ ، FT=۹۰′ ، ET=۱۰۵′) —
        محور بر حسب «دقیقهٔ مطلق مسابقه» است؛ عوض‌شدن پنل = کالیبره دوباره
        خودکار و منحنی دقیقاً از خط HT ادامه می‌یابد
      * «دقیقه‌های مشترک» (۴۵-۵۰/۹۰-۹۷): اولین گذر = وقت اضافهٔ بخش قبلی →
        قبل از خط مرز فشرده می‌شود؛ با ری‌استارت تایمر، رسم از خودِ مرز
      * نسبت ابعاد تصویر حفظ می‌شود (aspect equal — هیچ کشیدگی ندارد)
      * محور Y ‎-150..+150‎ (بدون عدد) — صفر = خط مرکزی تصویر
      * درخشش نئون نرم (بلور گاوسی) زیر fill + خط لبهٔ نازک روشن
      * خط گل: از توپ تا خط صفر — «روی» fill، با درخشش سفید نرم و بدون
        عبور از خط صفر
      * خطوط عمودی HT/FT/ET (لنگرهای داخلی) روی fill بازکشیده می‌شوند
      * لوگو: برش به قسمت رنگی + استروک نازک — داخل فضای مشکی، بدون
        به‌هم‌ریختن نسبت ابعاد
    نسخهٔ ۱۰٫۱۱:
      * transparent_bg=True → پس‌زمینهٔ Figure/محور شفاف می‌ماند (کانال
        آلفای تصویر اصلی حفظ می‌شود) — برای خروجی PNG اسنپ‌شات که باید
        روی تصویر بازی بیفتد و بازی از زیرش دیده شود؛
      * timestamp_text → تاریخ/ساعت شروع بازی (از ساعت سیستم) در نوار
        بالای پنل (شفاف) با قرصِ نیمه‌شفاف تیره نوشته می‌شود.
    """
    info = {"fills": 0, "glow": 0, "goal_lines": 0, "balls": 0,
            "flags": 0, "zero_line": 0, "vlines": 0, "texts": 0,
            "bg": None, "px": 0, "bins": 0, "marker_glows": 0,
            "rc_lines": 0, "rc_cards": 0,
            "axis_scale": float(TV_SCALE_MIN)}

    bg = tv_load_background(bg_kind)
    ax.clear()
    # نسخهٔ ۱۰٫۱۱ — transparent_bg: خروجی اسنپ‌شات (کانال آلفا حفظ می‌شود)
    # در حالت عادی: پس‌زمینهٔ مشکی خالص (رفع «شفید» دیده‌شدن — نسخهٔ ۱۰٫۱۰)
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
    ax.set_ylim(H, 0)              # محور Y رو به پایین = مختصات پیکسلی طبیعی
    ax.set_position([0, 0, 1, 1])
    # نسخهٔ ۱۰٫۹ — نسبت ابعاد تصویر حفظ می‌شود: باکس محور داخل کادر با
    # نسبت ابعاد خود تصویر جا می‌گیرد (letterbox) — هیچ کشیدگی از هیچ طرف؛
    # فضای اضافی دور تصویر، پس‌زمینهٔ مشکی تب دیده می‌شود.
    ax.set_aspect("equal", adjustable="box")
    ax.set_anchor("C")
    ax.axis("off")

    ax.imshow(arr, extent=(0, W, H, 0), interpolation="bilinear",
              zorder=0)
    info["bg"] = bg_kind

    # --- نسخهٔ ۱۰٫۱۱ — تاریخ/ساعت شروع بازی: نوار بالای پنل (شفاف) ---
    # tex بالای پنل ~۴۲px نوار شفاف دارد؛ متن با قرص نیمه‌شفاف تیره
    # نوشته می‌شود تا روی هر پس‌زمینه‌ای از بازی خوانا بماند.
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

    # مسیر برش به مستطیل نمودار — fill/گلو/خط گل هرگز بیرون نزنند
    from matplotlib.patches import Rectangle as _Rect
    clip = _Rect((l, t), (r - l), (b - t), transform=ax.transData)
    clip.set_visible(False)
    ax.add_patch(clip)

    # --- نسخهٔ ۱۰٫۲۴ — پایهٔ مشترک ریاضی منحنی (snapshot اتمیک داخل core؛
    # همان توابع و همان ترتیب — خروجی مو‌به‌مو مثل قبل) ---
    core = _tv_curve_core(momentum, cfg, bg, bg_kind)
    markers = core["markers"]
    bands = core["bands"]          # نسخهٔ ۱۰٫۲۴ — باندهای دقیقه‌های مشترک
    rc_markers = core.get("rc_markers") or []   # نسخهٔ ۱۰٫۲۷ — کارت قرمز
    axis_scale = core["axis_scale"]
    info["axis_scale"] = float(axis_scale)

    bx, by = core["bx"], core["by"]
    if core["pos_segs"] is not None:
        pos_segs, neg_segs = core["pos_segs"], core["neg_segs"]

        # --- درخشش نئون نرم (زیر fill) ---
        # نسخهٔ ۱۰٫۱۶ — آستانهٔ حذف هاله بر حسب «واحد ارتفاع نمودار»
        # (نزدیک‌تر از ۱۸ واحد → بدون درخشش؛ دورتر از ۴۲ → کامل)
        # تا با مقیاس پویا هم هالهٔ وسط نمودار واقعاً حذف شود.
        info["glow"] = _tv_draw_glow(ax, pos_segs, neg_segs, W, H,
                                     clip, home_color, away_color,
                                     rect_h, float(zero_y),
                                     near_px=core["near_px"],
                                     far_px=core["far_px"])

        # --- fill دو تیم (رنگ خودمان — بدون استروک زرد) ---
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
        # --- نسخهٔ ۱۰٫۲۶ — پرِ لبهٔ مخملی (feather) — عین مرجع کاربر ---
        # استروک هم‌رنگِ نیمه‌شفاف روی مرز fill؛ گذار آلفا را پهن و مخملی
        # می‌کند (پله‌های رستری در زوم نرم دیده می‌شوند). بدون تغییر شکل.
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
        # (نسخهٔ ۱۰٫۱۰ — خط لبهٔ رنگی حذف شد: دو خط افقیِ نزدیک خط صفر
        #  به رنگ میزبان/مهمان که کاربر دید، rim لبهٔ fill بود)

    # --- خط صفر + خطوط عمودی HT/FT/ET — «هرگز محو نمی‌شوند» (روی fill) ---
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

    # --- مارکر گل: خط عمود از توپ «تا خط صفر» (روی fill — بدون عبور از صفر) ---
    ball_d = TV_BALL_FRAC * rect_h
    ball_r = ball_d / 2.0
    # نسخهٔ ۱۰٫۱۶ — ارتفاع توپ = «مقیاس − ۳۰» (شرط جدید کاربر — بند ۲):
    # همهٔ توپ‌ها در «یک ارتفاع» مشترک می‌نشینند و اگر مقیاس پویا بعداً
    # بزرگ‌تر شود، توپ‌ها همگی با هم ۳۰ واحد پایین‌تر از سقف جدید می‌روند.
    # با مقیاس حداقل ۱۵۰ → توپ روی ±120 (رفتار نسخهٔ ۱۰٫۱۵ حفظ می‌شود).
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
        # نسخهٔ ۱۰٫۹ — گلِ داخل «وقت اضافه‌شدهٔ بخش قبل» (مثلاً ۴۵+۲ نیمهٔ اول)
        # قبل از خط مرز فشرده می‌شود؛ گلِ بعد از ری‌استارت تایمر سر جایش
        # (تمایز گذر اول/دوم دقیقه‌های مشترک با disp_time انجام می‌شود)
        _mk_band = tv_band_for_time(bands, mk.get("game_time", None),
                                    mk.get("disp_time", None))
        gx = tv_minute_to_x(bg_kind, geom, mmin, _mk_band)
        team = str(mk.get("team", "Home"))
        if team == "Home":
            byc = ball_home_y                     # ارتفاع ‎+120‎ — بالای منحنی
            y0, y1 = byc + ball_r * 0.9, float(zero_y)   # تا خط صفر — نه بیشتر
        else:
            byc = ball_away_y                     # ارتفاع ‎−120‎ — زیر منحنی
            y0, y1 = byc - ball_r * 0.9, float(zero_y)
        if abs(y1 - y0) < 2.0:
            y1 = y0 + (2.0 if team == "Home" else -2.0)
        # --- نسخهٔ ۱۰٫۹ — درخشش سفید نرم دور خط + توپ (زیر خط صفر) ---
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
            # نسخهٔ ۱۰٫۸ — imshow با extent داده‌ای: قطر توپ دقیقاً ball_d
            # پیکسلِ تصویر اصلی (مستقل از dpi/نقطه/بوم — عین تصویر نمونه)
            _hd = ball_d / 2.0
            _img = ax.imshow(_ball_icon_ref,
                             extent=(gx - _hd, gx + _hd,
                                     byc + _hd, byc - _hd),   # نسخهٔ Y معکوس — ردیف ۰ = بالا
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

    # --- نسخهٔ ۱۰٫۲۷ — مارکر کارت قرمز: عین گل، فقط آیکون کارت به‌جای توپ ---
    # (اندازه‌ها از تصویر نمونهٔ کاربر: عرض ≈ 0.66×قطر توپ، ارتفاع ≈ 1.05×)
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
        # خط از لبهٔ کارت تا خط صفر — مثل گل: بدون عبور از صفر
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

    # --- لوگو/پرچم: ناحیهٔ مشکی چپ — میزبان بالا / مهمان پایین ---
    # (نسخهٔ ۱۰٫۹ — imshow با extent داده‌ای: «بزرگ‌ترین بُعد» دقیقاً
    #  TV_FLAG_TARGET_W پیکسلِ تصویر اصلی و عرض/ارتفاع کاملاً متناسب با
    #  آرایهٔ تصویر — نسبت ابعاد هرگز به هم نمی‌ریزد؛ عین نمونه)
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
            clog(f"[TVFlag] رندر لوگو {side} ناموفق: {ex}")

    info["texts"] = len(getattr(ax, "texts", []))
    return info


# =====================================================================
# ۲۵-ب — اسنپ‌شات نمودار TV روی صفحهٔ بازی (نسخهٔ ۱۰٫۱۱ — درخواست کاربر)
# ---------------------------------------------------------------------
# چرخهٔ کامل:
#   دقیقهٔ هدف − ۱  →  رندر آفلاین نمودار TV با پس‌زمینهٔ شفاف (کانال آلفای
#                     تصویر اصلی حفظ می‌شود) → PNG موقت در tv_snapshot_tmp
#   دقیقهٔ هدف      →  نمایش روی صفحهٔ کاربر (پایین-چپ) به مدت تنظیم‌شده
#                     (پیش‌فرض ۲۰ ثانیهٔ واقعی) — دقیقاً همان شکل، همراه گل‌ها
#   پایان بازی      →  توقف ≥۱۲ ثانیه در زمان >۹۰′ و >۱۲۰′ → نمایش آخرین نمودار
#   ریست تایمر به ۰۰:۰۰ (دست جدید) → «ذخیرهٔ دائمی» آخرین نمودار بازی قبلی
#                     در Momentum_Saves با نام مخصوص خودش
# تنظیمات (چرخ‌دندهٔ تب TV): در tv_snapshot_settings.json کنار اسکریپت
# ذخیره می‌شود و در اجراهای بعدی خودکار بازیابی می‌شود.
# =====================================================================
TV_SNAP_TMP_DIRNAME = "tv_snapshot_tmp"            # PNG موقت اسنپ‌شات‌ها
TV_SNAP_SAVE_DIRNAME = "Momentum_Saves"            # ذخیرهٔ دائمی آخرین نمودارها
TV_SNAP_SETTINGS_FILENAME = "tv_snapshot_settings.json"

TV_SNAP_KEYS = ("h1", "h2", "et")
# بازهٔ مجاز انتخاب دقیقه برای هر بخش (درخواست صریح کاربر)
TV_SNAP_RANGES = {"h1": (38, 44), "h2": (80, 89), "et": (110, 119)}
TV_SNAP_DEFAULT_MINUTE = {"h1": 43, "h2": 85, "et": 116}   # «پیش‌فرض»

TV_SNAP_DEFAULTS = {
    "h1_enabled": True,  "h1_minute": 43,
    "h2_enabled": True,  "h2_minute": 85,
    "et_enabled": True,  "et_minute": 116,
    "show_seconds": 10,                  # ثانیهٔ واقعی (نه ثانیهٔ بازی)
    "end_enabled": True, "end_seconds": 20,
    "permanent_save": False,
    "timestamp": False,
}

# پایان بازی: توقفِ پیوستهٔ بازی حداقل این‌قدر ثانیه ادامه یابد تا «پایان»
# تلقی شود (تشخیص جشن گل از سوت پایان؛ جشن کوتاه‌تر از این است)
TV_SNAP_END_STOP_CONFIRM_SEC = 12.0
TV_SNAP_END_RESHOW_COOLDOWN_SEC = 45.0
TV_SNAP_MIN_HIST_SEC = 90.0      # بازی با کمتر از این زمان ذخیرهٔ دائمی نمی‌شود

# --- v10.28 — چرخهٔ عمر تراکنشی نمایش (پورت v1.3 از نسخهٔ 2017؛ رفع باگ
# «نمودار در دقیقهٔ هدف (۴۳/۸۵) نمایش داده نشد و فقط پس از پایان بازی آمد») —
# قبلاً st["shown"]=True صرفاً با «تولید» action ست می‌شد؛ اگر dispatch/UI
# گم می‌شد، همان نمایش برای همیشه از دست می‌رفت. حالا مصرف نهایی فقط با
# تأیید (confirm) پس از پذیرش Show انجام می‌شود و شکست/مهلت‌گذشتِ تأیید →
# تلاش مجدد خودکار بدون ری‌استارت بازی. ---
TV_SNAP_SHOW_CONFIRM_TIMEOUT_SEC = 10.0   # مهلت رسیدن تأیید SHOWING (wall)
TV_SNAP_SHOW_RETRY_BACKOFF_SEC = 3.0      # فاصلهٔ تلاش مجدد پس از شکست
TV_SNAP_SHOW_MAX_RETRIES = 6              # حداکثر تلاش مجدد هر کلید میان‌بازی
TV_SNAP_END_FAIL_MAX = 3                  # حداکثر شکست ثبت‌شدهٔ هر سطح پایان

# --- v10.29 (پورت v1.2.2 از 2017) — تضمین «پایان نمایش همهٔ نمودارها»
# (رفع باگ میدانی «نمودار دقیقهٔ 116 نمایش داده شد و دیگر تمام نشد و
# برای همیشه در گوشهٔ تصویر ماند»):
#  ۱) پنجرهٔ اورلی GPU فقط در لحظهٔ Show واقعی نمایان و بعد از انیمیشن
#     خروج (یا hide_now) در «سطح خود ویندوز» مخفی می‌شود — حذف از صفحه
#     دیگر فقط به ارائهٔ فریم شفاف از ترد رندر وابسته نیست؛
#  ۲) فرمان hide در جریان انیمیشن رها (drop) نمی‌شود؛
#  ۳) نگهبان مدت نمایش در UI بعد از (مدت تنظیم‌شده + انیمیشن + این
#     مهلت) پنهان‌سازی اجباری idempotent اجرا می‌کند. ---
TV_SNAP_OVERDUE_GRACE_SEC = 8.0        # مهلت اضافهٔ نگهبان مدت نمایش (wall)

# --- v10.28 — لاگ همیشه-فعلِ «مراحل نمایش اسنپ‌شات» (عین mlog نسخهٔ 2017):
# فایل کوچک momentum_2026_snapshot.log کنار اسکریپت — فقط چند خط به
# ازای هر نمایش (REQUESTED/QUEUED/EXECUTED/SHOWING/CONFIRMED/FAILED/...).
# هدف: در آزمون میدانی معلوم شود هر نمایش دقیقاً تا کدام مرحله رسیده.
# هیچ چاپ کنسولی ندارد (سیاست v10.24 حفظ شد) و با یک فلگ خاموش می‌شود. ---
SNAP_STAGE_LOG_ENABLED = True
SNAP_STAGE_LOG_MAX_BYTES = 512 * 1024
SNAP_STAGE_LOG_FILENAME = "momentum_2026_snapshot.log"


