def _snap_stage_write(msg: str) -> None:
    """نوشتن یک خط در لاگ مراحل اسنپ‌شات — هرگز exception بالا نمی‌آورد."""
    if not SNAP_STAGE_LOG_ENABLED:
        return
    try:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            SNAP_STAGE_LOG_FILENAME)
        try:
            if (os.path.exists(path)
                    and os.path.getsize(path) > SNAP_STAGE_LOG_MAX_BYTES):
                try:
                    if os.path.exists(path + ".1"):
                        os.remove(path + ".1")
                    os.rename(path, path + ".1")
                except Exception:
                    pass
        except Exception:
            pass
        line = (time.strftime("%Y-%m-%d %H:%M:%S")
                + " [SNAPSHOT] " + msg.rstrip() + "\n")
        with open(path, "a", encoding="utf-8", errors="replace") as fh:
            fh.write(line)
    except Exception:
        pass

# فرمول سایز/محل نمایش — مرجع: real.png (پخش واقعی ≈ ۳۳٪ عرض / ۳۲٪ ارتفاع)
TV_SNAP_OVERLAY_MAX_W_FRAC = 0.33    # هرگز بیش از یک‌سوم عرض صفحه
TV_SNAP_OVERLAY_H_FRAC = 0.32        # ارتفاع هدف ≈ یک‌سوم ارتفاع صفحه
TV_SNAP_OVERLAY_MARGIN_L_FRAC = 0.03
TV_SNAP_OVERLAY_MARGIN_B_FRAC = 0.02

# --- نسخهٔ ۱۰٫۱۳ — انیمیشن ورود/خروج پنجرهٔ اسنپ‌شات (کاربر: نمودار نباید
# یک‌دفعه ظاهر شود؛ از زیر صفحه طی ۱ ثانیه با ease وارد/خارج می‌شود —
# سرعت در وسط حرکت زیاد و در ابتدا/انتها نرم و آرام) ---
TV_SNAP_ANIM_MS = 1000          # مدت هر فاز ورود/خروج (میلی‌ثانیه)
# نسخهٔ ۱۰٫۱۸ — گام انیمیشن ۱۶→۲۵ms (حدود ۴۰fps — شرط کاربر: نرخ پایین‌تر،
# مدت انیمیشن با perf_counter روی «زمان واقعی» کنترل می‌شود و ۱۰۰۰ms می‌ماند)
TV_SNAP_ANIM_STEP_MS = 25       # گام فریم‌های انیمیشن (~۴۰fps)
# --- نسخهٔ ۱۰٫۱۵ — پیش‌بارگذاری (شرط کاربر: «یکی دو ثانیه قبل از ورود،
# لودش کن و خارج از کادر نگه دار تا موقع ورود مجبور به لود نشه») ---
# این‌قدر قبل از لحظهٔ نمایش، رندر + ساخت پنجره انجام می‌شود؛ پنجره کاملاً
# زیرِ صفحه می‌ماند و در لحظهٔ نمایش فقط انیمیشن ورود اجرا می‌شود.
TV_SNAP_PRELOAD_LEAD_SEC = 2.0

# --- نسخهٔ ۱۰٫۲۱ — فلگ‌های تست از Environment Variable هم ست می‌شوند
# (بدون تغییر کد — برای اجرای سریع تست‌های A/B/C روی همان بازی):
#   TV_SNAP_SHOW_DEBUG / TV_SNAP_DEBUG_NO_ANIM /
#   TV_SNAP_DEBUG_ANIM_NO_MOVE / TV_SNAP_DEBUG_ANIM_SINGLE_MOVE /
#   TV_SNAP_SWP_WIN_DEBUG   →  مقدار 1/true/yes/on = فعال
def _snap_env_flag(name: str, default: bool) -> bool:
    """نسخهٔ ۱۰٫۲۱ — خواندن فلگ دیباگ از Environment Variable (اختیاری).
    اگر متغیر ست نشده باشد، پیش‌فرض کد برمی‌گردد (رفتار عادی دست‌نخورده)."""
    try:
        v = os.environ.get(name)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "on", "y")
    except Exception:
        return default


# --- نسخهٔ ۱۰٫۱۸ — دیباگ لحظهٔ نمایش اسنپ‌شات (بندهای ۱/۲/۱۰/۱۱/۱۲ کاربر) ---
# TV_SNAP_SHOW_DEBUG: لاگ کامل مسیر نمایش (فقط اسنپ‌شات — هیچ لاگ دیگری
# اضافه نمی‌شود). در نسخهٔ Release کافی است False شود.
# --- نسخهٔ ۱۰٫۲۴ — حذف کامل لاگ‌های کنسول (درخواست کاربر) ---
# پیش‌فرض «سکوت مطلق»: هیچ بلوک [OVERLAY_STATE] / [SNAPSHOT_STATE] /
# [SNAPSHOT PRELOAD] / [SNAPSHOT ANIM ...] چاپ نمی‌شود. برای عیب‌یابی
# موقت (فقط در صورت نیاز) همان مسیر قبلی با متغیر محیطی در دسترس است:
#   set TV_SNAP_SHOW_DEBUG=1   →  لاگ‌های کامل برگردند
TV_SNAP_SHOW_DEBUG = _snap_env_flag("TV_SNAP_SHOW_DEBUG", False)
# تست ۱ (بند ۱۰): نمایش «بدون انیمیشن» — Render→آماده‌سازی→Show→ثابت.
# اگر با این حالت هم بازی هنگام Show افت داشت، مشکل از Animation نیست و
# باید روی Toplevel/Layered/UpdateLayeredWindow/DWM تمرکز شود.
# نسخهٔ ۱۰٫۲۱ — همان «TEST 1 — ENTRY ANIMATION OFF» کاربر است: Preload →
# READY → Show → پنجره مستقیم در مکان نهایی؛ هیچ SetWindowPos متحرکی در
# ثانیهٔ اول انجام نمی‌شود. (اگر هم SINGLE_MOVE فعال باشد، این اولویت دارد.)
TV_SNAP_DEBUG_NO_ANIM = _snap_env_flag("TV_SNAP_DEBUG_NO_ANIM", False)
# تست ۲ (بند ۱۱): نمایش همان پنجره با بیت‌مپ آزمایشی کوچک 256×256 به‌جای
# PNG واقعی (مقایسهٔ 256×256 با 2034×978 = تشخیص هزینهٔ Surface/Composition)
TV_SNAP_DEBUG_SMALL_BITMAP = False
TV_SNAP_DEBUG_BITMAP_SIZE = 256

# --- نسخهٔ ۱۰٫۲۰ — تست ب (بند ۱۰ پیام جدید کاربر): انیمیشن «بدون حرکت» ---
# ترد انیمیشن و زمان‌بندی ۴۰fps «فعال» است ولی هیچ SetWindowPos انجام
# نمی‌شود؛ پنجره ثابت زیر صفحه می‌ماند (بالا هم نمی‌آید — طبیعی است).
# تفسیر:
#   NORMAL          → Stutter   |  NO-MOVE (این فلگ) → بدون Stutter
#     ⇒ عامل تقریباً قطعی: خودِ حرکت HWND / Window Manager / DWM.
#   هر دو حالت Stutter ⇒ انیمیشن از لیست مظنون‌ها خارج می‌شود؛ تمرکز روی
#     Show / DWM composition / GPU (بند ۱۶ حالت ۳).
# (تست الف = TV_SNAP_DEBUG_NO_ANIM در بالای همین بلوک — نمایش کاملاً ثابت.)
TV_SNAP_DEBUG_ANIM_NO_MOVE = _snap_env_flag("TV_SNAP_DEBUG_ANIM_NO_MOVE", False)

# --- نسخهٔ ۱۰٫۲۱ — تست ۳ کاربر: فقط «یک» SetWindowPos در لحظهٔ ورود ---
# Overlay از قبل Preload شده → Show → فقط «یک» SetWindowPos اندازه‌گیری‌شده
# به مکان نهایی؛ بعدش هیچ حرکتی در ثانیهٔ اول (بدون انیمیشن، بدون ترد).
# اگر همین یک فراخوانی 100-200ms طول بکشد → هزینهٔ خودِ فراخوانی/
# DWM/composition است، نه زمان‌بندی انیمیشن. (اولویت: NO_ANIM > SINGLE_MOVE)
TV_SNAP_DEBUG_ANIM_SINGLE_MOVE = _snap_env_flag(
    "TV_SNAP_DEBUG_ANIM_SINGLE_MOVE", False)

# --- نسخهٔ ۱۰٫۲۱ — تست ۵ کاربر: تلمتری کامل ویندوزی «هر» SetWindowPos ---
# old/new x,y + y واقعی بعد از حرکت + HWND + native TID + priority + flags
# + return + GetLastError + قبل/بعد (Foreground/Visible/TOPMOST/LAYERED/
# TRANSPARENT/NOACTIVATE). اگر مدت از آستانه بیشتر شود → نمونهٔ پشتهٔ
# UI-Thread از ترد انیمیشن ثبت می‌شود (تشخیص «UI هنگام بلوک چه می‌کرد؟»).
TV_SNAP_SWP_WIN_DEBUG = _snap_env_flag("TV_SNAP_SWP_WIN_DEBUG", True)
TV_SNAP_UI_STACK_ON_SLOW_MS = 30.0

# --- نسخهٔ ۱۰٫۱۹ — Preload واقعی پنجره (لاگ کاربر: NO PREBUILT WINDOW در
# لحظهٔ Show) ---
# اگر پنجرهٔ پیش‌ساخته آماده نبود، ساخت دوباره تا «نزدیک لحظهٔ Show» ادامه
# می‌یابد (self-heal) — ولی هرگز در لحظهٔ Show شروع نمی‌شود.
TV_SNAP_PRELOAD_RETRY_MIN_GAP_SEC = 0.5   # حداقل فاصلهٔ دو تلاش self-heal
TV_SNAP_PRELOAD_MIN_REMAIN_SEC = 0.4      # کمتر از این تا Show → تلاش جدید نمی‌شود (دیگر نمی‌رسد)

# --- نسخهٔ ۱۰٫۲۲ — Snapshot Window Lifecycle Manager (گزارش فنی کاربر) ---
# هدف: «پنجره باید قبل از نیاز به نمایش ساخته شده باشد» — نه در لحظهٔ Show.
# ۱) پنجرهٔ آستانه‌ای پهن Preload (اولویت ۱): برای میان‌بازی‌ها (h1/h2/et)
#    هر تیک Worker بعد از «هدف − این ثانیه» اگر پنجرهٔ پیش‌ساخته READY
#    نبود، همان‌جا dispatch می‌شود (if match_time >= preload_start)؛
#    دیگر پنجرهٔ ۲ ثانیه‌ای تک‌شانس نیست. امن بودن محتوا: تصویرِ
#    میان‌بازی همان PNG کپچرشدهٔ «دقیقهٔ هدف − ۱» است (کش ثابت) → ساخت
#    زودترِ پنجره، محتوای نمایش را ذره‌ای تغییر نمی‌دهد.
#    (نمایش «پایان» عمداً همین پنجرهٔ قبلی را دارد: رندرش در لحظهٔ توقف
#    انجام می‌شود و رندر زودتر = نمودارِ کم‌داده‌تر = تغییر محتوا.)
TV_SNAP_PRELOAD_WIDE_LEAD_SEC = 10.0

# --- نسخهٔ ۱۰٫۲۳ — معماری جدید GPU Overlay (گزارش فنی کاربر) ---
# «پنجره هیچ‌وقت حرکت نمی‌کند؛ تمام انیمیشن داخل GPU (Shader) است.»
#   TV_SNAP_GPU_OVERLAY      → خاموشی = مسیر قبلی (Tk Layered) در شروع
#   TV_SNAP_GPU_VSYNC        → حلقهٔ رندر همگام با نمایشگر (بدون CPU Busy Loop)
#   TV_SNAP_GPU_CLICKTHROUGH → پنجرهٔ Overlay ورودی موس را رد می‌کند
#   TV_SNAP_GPU_ANIM_DEBUG   → بلوک [OVERLAY ANIM DEBUG] بعد از هر انیمیشن
# همه از Environment Variable هم ست می‌شوند (بدون تغییر کد).
TV_SNAP_GPU_OVERLAY = _snap_env_flag("TV_SNAP_GPU_OVERLAY", True)
TV_SNAP_GPU_VSYNC = _snap_env_flag("TV_SNAP_GPU_VSYNC", True)
TV_SNAP_GPU_CLICKTHROUGH = _snap_env_flag("TV_SNAP_GPU_CLICKTHROUGH", True)
TV_SNAP_GPU_ANIM_DEBUG = _snap_env_flag("TV_SNAP_GPU_ANIM_DEBUG", False)   # نسخهٔ ۱۰٫۲۴ — پیش‌فرض خاموش (حذف لاگ کنسول)
TV_SNAP_GPU_INIT_WAIT_SEC = 4.0        # حداکثر انتظار برای Context GPU در شروع


class SnapshotState(Enum):
    """نسخهٔ ۱۰٫۲۲ — ماشین حالت چرخهٔ عمر پنجرهٔ Snapshot (مشخصات کاربر):
    EMPTY → PREPARING → READY → SHOWING → VISIBLE → (پنهان‌سازی) EMPTY.
    با بلوک‌های [SNAPSHOT_STATE] هر گذر لاگ می‌شود تا دیگر «کور» نباشیم."""
    EMPTY = 0
    PREPARING = 1
    READY = 2
    SHOWING = 3
    VISIBLE = 4


def _snap_thread_tag() -> str:
    """برچسب تردِ جاری برای لاگ نمایش اسنپ‌شات (Main/UI یا Worker یا Anim)."""
    try:
        name = threading.current_thread().name
    except Exception:
        return "?"
    if name == "MainThread":
        return "Main/UI"
    if name == "snap-anim":
        return "Anim"
    if name == "app-worker":
        return "Worker"
    return name


def _snap_native_tid() -> int:
    """نسخهٔ ۱۰٫۲۰ — شناسهٔ native ترد جاری (Win32 GetCurrentThreadId) برای
    همبستگی لاگ با Process Explorer / ETW (بند ۸ کاربر). غیر ویندوز → 0."""
    if os.name == "nt":
        try:
            import ctypes as _ct
            return int(_ct.windll.kernel32.GetCurrentThreadId())
        except Exception:
            pass
    return 0


def _snap_tid_text() -> str:
    """نسخهٔ ۱۰٫۲۰ — «Thread ID: <python> (native <win32>)» برای لاگ (بند ۸)."""
    try:
        py_id = threading.get_ident()
    except Exception:
        py_id = 0
    nat = _snap_native_tid()
    return (f"Thread ID: {py_id}"
            + (f" (native {nat})" if nat else ""))


class SnapShowTrace:
    """نسخهٔ ۱۰٫۱۸ — زمان‌سنج perf_counter مسیر نمایش اسنپ‌شات (بند ۱ کاربر):
    هر مرحله با «زمان شروع/پایان/مدت (ms)، ترد، HWND، ابعاد» ثبت و بلافاصله
    در Console چاپ می‌شود. زمان‌ها نسبت به لحظهٔ ساخت تریس (T+ms) هستند و
    مقدار خام perf_counter هم برای همبستگی چاپ می‌شود.
    فقط برای مسیر Snapshot Show — هیچ سیستم دیگری از آن استفاده نمی‌کند."""

    def __init__(self, title: str, enabled: bool = True):
        self.enabled = bool(enabled)
        self.title = title
        self.t0 = time.perf_counter()
        self.steps = []                       # (rel_ms, dur_ms, label)
        if not self.enabled:
            return
        print("=" * 60, flush=True)
        print(f"[SNAPSHOT {title}]", flush=True)
        print("=" * 60, flush=True)
        self.step("Trace start")

    # --- مرحلهٔ لحظه‌ای (بدون اندازه‌گیری مدت) ---
    def step(self, label: str, hwnd=None, size=None, note: str = "") -> float:
        now = time.perf_counter()
        rel = (now - self.t0) * 1000.0
        self._emit(label, rel, None, hwnd, size, note)
        return now

    # --- جفت شروع/پایان برای مراحل دارای مدت ---
    def begin(self) -> float:
        return time.perf_counter()

    def end(self, label: str, t_start: float, hwnd=None, size=None,
            note: str = "") -> float:
        now = time.perf_counter()
        dur = (now - t_start) * 1000.0
        self._emit(label, (now - self.t0) * 1000.0, dur, hwnd, size, note)
        return dur

    def _emit(self, label, rel_ms, dur_ms, hwnd, size, note) -> None:
        self.steps.append((rel_ms, dur_ms, label))
        if not self.enabled:
            return
        raw_t = time.perf_counter()
        txt = (f"[{rel_ms:010.3f} ms] {label}"
               + (f" — {dur_ms:.3f} ms" if dur_ms is not None else "")
               + f" | Thread: {_snap_thread_tag()}"
               + (f" | HWND: 0x{int(hwnd):08X}" if hwnd else "")
               + (f" | Size: {size[0]}x{size[1]}" if size else "")
               + (f" | {note}" if note else "")
               + f" | t={raw_t:.6f}")
        try:
            print(txt, flush=True)
        except Exception:
            pass

    def finish(self) -> None:
        if not self.enabled:
            return
        total = (time.perf_counter() - self.t0) * 1000.0
        try:
            timed = [(d, l) for (_r, d, l) in self.steps if d is not None]
            timed.sort(reverse=True)
            top = " | ".join(f"{l} {d:.2f}ms" for d, l in timed[:6]) or "-"
            print("-" * 60, flush=True)
            print(f"[SNAPSHOT {self.title} END] total {total:.3f} ms | "
                  f"steps: {len(self.steps)}", flush=True)
            print(f"  Slowest: {top}", flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass

# تاریخ/ساعت شروع بازی — نوار شفافِ بالای پنل tex (ارتفاع ≈ ۴۲px)
TV_TIMESTAMP_Y = 21.0
TV_TIMESTAMP_FONT_PT = 17            # در dpi=100 ≈ ۲۴px — داخل نوار جا می‌شود
TV_TIMESTAMP_BG_ALPHA = 0.62


def snap_ease_in_out(p: float) -> float:
    """منحنی ease-in-out مکعبی (نسخهٔ ۱۰٫۱۳): خروجی ۰→۱ با حرکتِ نرم و
    آرام در ابتدا و انتها و تند در میانه — دقیقاً شرط کاربر برای ورود/خروج
    نمودار اسنپ‌شات."""
    p = min(1.0, max(0.0, float(p)))
    if p < 0.5:
        return 4.0 * p * p * p
    q = 2.0 * p - 2.0
    return 1.0 + 0.5 * q * q * q


def snap_clamp_minute(key: str, value) -> int:
    """محدودسازی دقیقه به بازهٔ مجاز همان بخش (۳۸..۴۴ / ۸۰..۸۹ / ۱۱۰..۱۱۹)."""
    lo, hi = TV_SNAP_RANGES.get(key, (0, 130))
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = TV_SNAP_DEFAULT_MINUTE.get(key, lo)
    return max(lo, min(hi, v))


def snap_clamp_seconds(value, default: float = 20.0) -> int:
    """مدت نمایش: ۵ تا ۳۰۰ ثانیهٔ واقعی."""
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = int(default)
    return max(5, min(300, v))


def snap_load_settings(script_dir: str) -> Dict[str, Any]:
    """خواندن تنظیمات ذخیره‌شده (فایل کنار اسکریپت) + ادغام با پیش‌فرض‌ها
    و محدودسازی مقادیر — فایل خراب/ناقص = پیش‌فرض‌ها."""
    s = dict(TV_SNAP_DEFAULTS)
    try:
        path = os.path.join(script_dir, TV_SNAP_SETTINGS_FILENAME)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                for k in TV_SNAP_DEFAULTS:
                    if k in raw:
                        s[k] = raw[k]
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
    return s


def snap_save_settings(script_dir: str, settings: Dict[str, Any]) -> bool:
    """ذخیرهٔ تنظیمات (JSON کنار اسکریپت — تا دفعات بعد نیاز به تکرار نباشد)."""
    try:
        path = os.path.join(script_dir, TV_SNAP_SETTINGS_FILENAME)
        payload = {}
        for k in TV_SNAP_DEFAULTS:
            payload[k] = settings.get(k, TV_SNAP_DEFAULTS[k])
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def snap_overlay_geometry(img_w: int, img_h: int, screen_w: int, screen_h: int
                          ) -> Tuple[int, int, int, int]:
    """فرمول سایز/محل نمایش (تا 8K — نسبت ابعاد هرگز به هم نمی‌ریزد):
         w = min(0.33×sw ، 0.32×sh×نسبت)   h = w÷نسبت
         x = 0.03×sw ، y = sh − h − 0.02×sh   (گوشهٔ پایین-چپ)
       مرجع اندازه: real.png (پخش واقعی ≈ ۳۳٪ عرض / ۳۲٪ ارتفاع).
       خروجی: (x, y, w, h) به پیکسل."""
    try:
        iw, ih = max(1, int(img_w)), max(1, int(img_h))
        sw, sh = max(1, int(screen_w)), max(1, int(screen_h))
    except (TypeError, ValueError):
        return 0, 0, 1, 1
    aspect = float(iw) / float(ih)
    w = min(TV_SNAP_OVERLAY_MAX_W_FRAC * sw,
            TV_SNAP_OVERLAY_H_FRAC * sh * aspect)
    h = w / aspect
    x = int(round(TV_SNAP_OVERLAY_MARGIN_L_FRAC * sw))
    y = int(round(float(sh) - h - TV_SNAP_OVERLAY_MARGIN_B_FRAC * sh))
    return x, max(0, y), max(1, int(round(w))), max(1, int(round(h)))


def snap_prepare_display(img, screen_w: int, screen_h: int):
    """نسخهٔ ۱۰٫۱۶ — آماده‌سازی سنگینِ پیکسلی «خارج از UI-Thread» (رفع لگ
    ورود — شرط کاربر: سپردن به ترد جدا):
      ۱) resize به هندسهٔ نهایی (LANCZOS)
      ۲) پیش‌ضرب آلفا → آرایهٔ BGRA آمادهٔ UpdateLayeredWindow
    خروجی: (disp, arr, (x, y_final, w, h)) — در خطا (None, None, None).
    تابع خالص است (بدون Tk) و از ترد Worker فراخوانی می‌شود."""
    if img is None:
        return None, None, None
    try:
        x, y_final, w, h = snap_overlay_geometry(img.width, img.height,
                                                 screen_w, screen_h)
        disp = img.resize((max(1, int(w)), max(1, int(h))),
                          Image.Resampling.LANCZOS)
        arr = _premultiply_rgba(disp)
        return disp, arr, (int(x), int(y_final), int(w), int(h))
    except Exception:
        return None, None, None


# =====================================================================
# ۲۵٫۵ — GPU OVERLAY RENDERER (نسخهٔ ۱۰٫۲۳ — معماری Game Overlay واقعی)
# ---------------------------------------------------------------------
# گزارش فنی کاربر: «پنجرهٔ Overlay باید فقط یک‌بار ساخته شود، هیچ‌وقت
# حرکت نکند و تمام انیمیشن داخل GPU انجام شود.»
#
#   Python Logic ──► GPU Texture (PNG آمادهٔ Worker — همان LANCZOS)
#        ──► Fragment Shader (حرکت + ease-in-out + premultiply آلفا)
#        ──► OpenGL Swapchain روی پنجرهٔ «ثابت» شفاف (GLFW)
#        ──► DWM ──► DirectX بازی
#
#   * پنجره هیچ‌وقت حرکت/resize/show-hide نمی‌شود؛ «مخفی» یعنی محتوای
#     کاملاً شفاف (آلفای صفر) — DWM دیگر هیچ‌وقت درگیر حرکت HWND نیست.
#   * Show/Hide فقط queue.put است (زیر ~۰٫۱ms) — هیچ فراخوانی ویندوزی.
#   * انیمیشن: CPU فقط progress=(now-start)/dur می‌فرستد؛ interpolation
#     و منحنی ease داخل Shader است. در طول انیمیشن «صفر» SetWindowPos.
#   * ترد رندر با vsync همگام است؛ بدون انیمیشن روی صف پیام منتظر
#     می‌ماند (هیچ CPU Busy Loop). اولویت ترد دستکاری نمی‌شود
#     (Game > Overlay). State: HIDDEN→READY→ANIMATING→VISIBLE.
# =====================================================================
import queue as _queue

# =====================================================================
# v2.0.5 — CREST SIGNAL BANNER (hook/display health indicator)
# ---------------------------------------------------------------------
# User request: during the FIRST MINUTE of a match the two team crests
# appear side-by-side in the bottom-left corner — the EXACT spot where
# the charts show up later — and disappear again after 5 seconds.
#
# Purpose — a visible self-test of the whole chain, because the banner
# is produced by the SAME pipeline as the charts:
#   crests visible        → team identity slots read OK AND the overlay
#                           display path (GPU renderer or the Win32
#                           fallback) works → charts will be drawable.
#   crests never appear   → the display path is dead or the game-data
#                           hooks are not delivering; the charts would
#                           then be empty/absent for the same reason.
# Implementation notes:
#   * the banner is uploaded/shown/hidden through the renderer's
#     thread-safe message queue (same messages as the chart path) from
#     the Worker thread — zero new windows, zero new threads;
#   * geometry = snap_prepare_display / snap_overlay_geometry with the
#     SAME canvas aspect as the charts (11.5 x 5.2 @120dpi), so it
#     occupies exactly the rectangle the charts will use;
#   * it fires ONCE per match (reset clears it), never while a real
#     chart is on screen, and only inside the first-minute window.
# =====================================================================
CREST_BANNER_KEY = "crest_banner"
CREST_BANNER_SECONDS = 5.0          # on-screen duration (user request)
CREST_BANNER_WINDOW_SEC = 60.0      # first-minute window (user request)
CREST_BANNER_MIN_T_SEC = 2.0        # small grace period after kickoff
CREST_BANNER_W_PX = 1380            # chart canvas: 11.5in x 120dpi
CREST_BANNER_H_PX = 624             # chart canvas:  5.2in x 120dpi
_CREST_BANNER_PANEL = (8, 14, 26, 175)     # rounded panel behind crests
_CREST_BANNER_EDGE = (90, 200, 255, 220)   # thin cyan edge (chart accent)
_CREST_BANNER_BOX = 190                   # per-crest square (px @1380x624)
# --- v2.0.7 — ARBITRATED FEED SELF-HEAL thresholds -----------------
# A ball buffer frozen longer than this WHILE PLAYING means the shared
# hook is dead (charts would be empty) -> send hook_reset_request to
# the bridge (restore + rebuild), then adopt the buffer it hands back.
FEED_HEAL_AFTER_SEC = 25.0          # STALE warn at 15 s, heal at 25 s
FEED_HEAL_RETRY_SEC = 60.0          # max one reset attempt per minute
_CREST_BANNER_GAP = 46                    # gap between the two crests


def _load_crest_png(path):
    """Read a crest file as RGBA, or None (missing/corrupt/empty file)."""
    try:
        with Image.open(path) as im:
            return im.convert("RGBA")
    except Exception:
        return None


def _fit_crest(im, box):
    """Fit a crest into a box x box square (LANCZOS, aspect preserved)."""
    try:
        w, h = im.size
        if w < 1 or h < 1:
            return None
        scale = min(box / float(w), box / float(h))
        nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
        return im.resize((nw, nh), Image.Resampling.LANCZOS)
    except Exception:
        return None


def _build_crest_banner_image(path_home, path_away):
    """Compose the two team crests side-by-side on a transparent canvas
    with the chart's exact aspect ratio. Returns a PIL RGBA image or
    None when BOTH crest files are unreadable (single missing crest
    still shows — as an empty slot — so the signal stays interpretable:
    one crest missing = identity file problem, no banner at all =
    pipeline problem)."""
    im_h = _load_crest_png(path_home)
    im_a = _load_crest_png(path_away)
    if im_h is None and im_a is None:
        return None
    W, H = CREST_BANNER_W_PX, CREST_BANNER_H_PX
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    from PIL import ImageDraw as _IDraw
    draw = _IDraw.Draw(canvas)
    box = _CREST_BANNER_BOX
    gap = _CREST_BANNER_GAP
    total = box * 2 + gap
    cx0 = (W - total) // 2
    cy0 = (H - box) // 2
    # rounded translucent panel + thin accent edge (chart-look)
    pad = 28
    draw.rounded_rectangle(
        (cx0 - pad, cy0 - pad, cx0 + total + pad, cy0 + box + pad),
        radius=34, fill=_CREST_BANNER_PANEL, outline=_CREST_BANNER_EDGE,
        width=3)
    # side-by-side crests (missing side = faint empty slot circle)
    for idx, (im, px0) in enumerate(((im_h, cx0), (im_a, cx0 + box + gap))):
        fitted = _fit_crest(im, box) if im is not None else None
        if fitted is not None:
            ox = px0 + (box - fitted.size[0]) // 2
            oy = cy0 + (box - fitted.size[1]) // 2
            canvas.alpha_composite(fitted, (ox, oy))
        else:
            ccx, ccy = px0 + box // 2, cy0 + box // 2
            draw.ellipse((ccx - 70, ccy - 70, ccx + 70, ccy + 70),
                         outline=(150, 165, 185, 120), width=4)
    return canvas


_OVERLAY_VERT_SRC = """
#version 330 core
layout(location = 0) in vec2 a_px;          // مختصات پیکسلی سطح (مبدأ بالا-چپ)
uniform vec2 u_surf;                        // اندازهٔ سطح (پیکسل)
out vec2 v_px;
void main() {
    v_px = a_px;
    float cx = (a_px.x / u_surf.x) * 2.0 - 1.0;
    float cy = 1.0 - (a_px.y / u_surf.y) * 2.0;
    gl_Position = vec4(cx, cy, 0.0, 1.0);
}
"""

_OVERLAY_FRAG_SRC = """
#version 330 core
in vec2 v_px;
uniform sampler2D u_tex;
uniform vec2  u_tex_size;                   // اندازهٔ تصویر (پیکسل)
uniform vec2  u_img;                        // مکان «نهایی» گوشهٔ بالا-چپ تصویر روی سطح
uniform float u_travel;                     // فاصلهٔ عمودی حرکت (پیکسل)
uniform float u_progress;                   // 0..1 — CPU فقط زمان می‌فرستد
uniform float u_dir;                        // +1 ورود (بالا) | -1 خروج (پایین)
out vec4 frag;
float ease_in_out(float p) {                // عیناً snap_ease_in_out (۱۰٫۱۳)
    p = clamp(p, 0.0, 1.0);
    if (p < 0.5) return 4.0 * p * p * p;
    float q = 2.0 * p - 2.0;
    return 1.0 + 0.5 * q * q * q;
}
void main() {
    float e = ease_in_out(u_progress);
    float t = (u_dir > 0.0) ? (1.0 - e) : e;   // ۱ = کاملاً زیر صفحه | ۰ = مکان نهایی
    vec2 origin = u_img + vec2(0.0, t * u_travel);
    vec2 p = v_px - origin;
    if (p.x < 0.0 || p.y < 0.0 || p.x >= u_tex_size.x || p.y >= u_tex_size.y) {
        frag = vec4(0.0);                   // بیرون تصویر = کاملاً شفاف
        return;
    }
    vec4 c = texture(u_tex, (p + vec2(0.5)) / u_tex_size);  // مرکز تکستل — بدون تاری
    frag = vec4(c.rgb * c.a, c.a);          // premultiplied alpha برای DWM
}
"""


def _gpu_surface_geo(sw: int, sh: int) -> Tuple[int, int, int, int]:
    """سطح «ثابت» Overlay — کل مسیر دیدنیِ حرکت را برای «هر» اندازهٔ
    Snapshot پوشش می‌دهد. بخشِ زیرِ لبهٔ صفحه به‌طور طبیعی بیرون مانیتور
    است — دقیقاً مثل وقتی که پنجرهٔ واقعی زیر صفحه حرکت می‌کرد؛ پس ظاهر
    ورود/خروج پیکسل‌به‌پیکسل همانند مسیر قبلی است (پنجره حرکت نمی‌کند)."""
    sw = max(1, int(sw))
    sh = max(1, int(sh))
    x = max(0, int(round(TV_SNAP_OVERLAY_MARGIN_L_FRAC * sw)) - 4)
    top = max(0, int(round(sh - TV_SNAP_OVERLAY_H_FRAC * sh
                           - TV_SNAP_OVERLAY_MARGIN_B_FRAC * sh)) - 8)
    w = max(16, min(sw - x, int(round(TV_SNAP_OVERLAY_MAX_W_FRAC * sw)) + 8))
    h = max(16, sh - top + 8)
    return x, top, w, h


def _gpu_image_placement(sw: int, sh: int, x: int, y_final: int,
                         surf_x: int, surf_top: int) -> Dict[str, int]:
    """محل تصویر «داخل سطح ثابت» + فاصلهٔ حرکت (محاسبهٔ خالص — سنگین نیست)."""
    return {"dx": int(x) - int(surf_x), "dy": int(y_final) - int(surf_top),
            "travel": max(1, int(sh) + 4 - int(y_final))}


