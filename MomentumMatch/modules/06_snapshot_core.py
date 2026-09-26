def _snap_stage_write(msg: str) -> None:
    """write text line in log text textagetext‌text — never exception withtext text‌textandtext."""
    if not SNAP_STAGE_LOG_ENABLED:
        return
    try:
        path = os.path.join(_MOMENTUM_DATA_DIR,
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

# technical noteandtechnical note technical note/technical note display — technical note: real.png (technical note real ≈ 33technical note width / 32technical note height)
TV_SNAP_OVERLAY_MAX_W_FRAC = 0.33    # never technical note from third width technical note
TV_SNAP_OVERLAY_H_FRAC = 0.32        # height technical note ≈ third height technical note
TV_SNAP_OVERLAY_MARGIN_L_FRAC = 0.03
TV_SNAP_OVERLAY_MARGIN_B_FRAC = 0.02

# --- versiontechnical note 10technical note13 — technical note andtechnical noteandtechnical note/technical noteandtechnical note windowtechnical note technical noteagetechnical note‌technical note (user: chart technical notemust
# technical note‌technical note technical note technical noteandtechnical note from technical note technical note technical note 1 second with ease andtechnical note/technical note technical note‌technical noteandtechnical note —
# technical note in andtechnical note technical note technical noteortechnical note and in technical note/technical note smooth and technical note) ---
TV_SNAP_ANIM_MS = 1000          # technical note technical note technical notefrom andtechnical noteandtechnical note/technical noteandtechnical note (technical note‌second)
# versiontechnical note 10technical note18 — technical note technical note 16→25ms (technical noteandtechnical note 40fps — technical note user: technical note below‌technical note
# technical note technical note with perf_counter technical noteandtechnical note «time real» technical note technical note‌technical noteandtechnical note and 1000ms technical note‌technical note)
TV_SNAP_ANIM_STEP_MS = 25       # technical note frame‌technical note technical note (~40fps)
# --- versiontechnical note 10technical note15 — technical note‌withtechnical note (technical note user: «technical note technical noteand second before from andtechnical noteandtechnical note
# technical noteandtechnical note technical note and technical note from technical notein technical note technical note until technical noteandtechnical note andtechnical noteandtechnical note technical noteandtechnical note to technical noteandtechnical note technical note») ---
# technical note‌technical notein before from momenttechnical note displaytechnical note render + technical note window technical note technical note‌technical noteandtechnical note window completetechnical note
# technical note technical note technical note‌technical note and in momenttechnical note display only technical note andtechnical noteandtechnical note technical note technical note‌technical noteandtechnical note.
TV_SNAP_PRELOAD_LEAD_SEC = 2.0

# --- versiontechnical note 10technical note21 — technical note‌technical note test from Environment Variable technical note technical note technical note‌technical noteandtechnical note
# (unchanged code — for technical note fast test‌technical note A/B/C technical noteandtechnical note same withtechnical note):
#   TV_SNAP_SHOW_DEBUG / TV_SNAP_DEBUG_NO_ANIM /
#   TV_SNAP_DEBUG_ANIM_NO_MOVE / TV_SNAP_DEBUG_ANIM_SINGLE_MOVE /
#   TV_SNAP_SWP_WIN_DEBUG   →  value 1/true/yes/on = active
def _snap_env_flag(name: str, default: bool) -> bool:
    """versiontext 10text21 — read text textwithtext from Environment Variable (optional).
    if text text text withtext default code text‌text (textuntiltext text unchanged)."""
    try:
        v = os.environ.get(name)
        if v is None:
            return default
        return str(v).strip().lower() in ("1", "true", "yes", "on", "y")
    except Exception:
        return default


# --- versiontechnical note 10technical note18 — technical notewithtechnical note momenttechnical note display technical noteagetechnical note‌technical note (technical note 1/2/10/11/12 user) ---
# TV_SNAP_SHOW_DEBUG: log complete path display (only technical noteagetechnical note‌technical note — technical note log technical note
# technical note technical note‌technical noteandtechnical note). in versiontechnical note Release technical note is False technical noteandtechnical note.
# --- versiontechnical note 10technical note24 — technical note complete log‌technical note technical noteandtechnical note (request user) ---
# default «silence technical note»: technical note technical noteandtechnical note [OVERLAY_STATE] / [SNAPSHOT_STATE] /
# [SNAPSHOT PRELOAD] / [SNAPSHOT ANIM ...] print technical note‌technical noteandtechnical note. for technical note‌ortechnical note
# technical noteandtechnical note (only in technical noteandtechnical note technical noteortechnical note) same path beforetechnical note with technical note technical note in technical note is:
#   set TV_SNAP_SHOW_DEBUG=1   →  log‌technical note complete technical note
TV_SNAP_SHOW_DEBUG = _snap_env_flag("TV_SNAP_SHOW_DEBUG", False)
# test 1 (technical note 10): display «without technical note» — Render→technical note‌technical notefromtechnical note→Show→technical note.
# if with technical note technical note technical note withtechnical note technical note Show decrease technical note technical notetotal from Animation is not and
# must technical noteandtechnical note Toplevel/Layered/UpdateLayeredWindow/DWM technical note technical noteandtechnical note.
# versiontechnical note 10technical note21 — same «TEST 1 — ENTRY ANIMATION OFF» user is: Preload →
# READY → Show → window direct in technical note technical note technical note SetWindowPos technical note in
# secondtechnical note first technical note technical note‌technical noteandtechnical note. (if technical note SINGLE_MOVE active withtechnical note technical note firstandtechnical note technical note.)
TV_SNAP_DEBUG_NO_ANIM = _snap_env_flag("TV_SNAP_DEBUG_NO_ANIM", False)
# test 2 (technical note 11): display same window with technical note‌technical note technical note technical noteandtechnical note 256×256 to‌technical note
# PNG real (technical note 256×256 with 2034×978 = detection technical note Surface/Composition)
TV_SNAP_DEBUG_SMALL_BITMAP = False
TV_SNAP_DEBUG_BITMAP_SIZE = 256

# --- versiontechnical note 10technical note20 — test technical note (technical note 10 message new user): technical note «without technical note» ---
# technical note technical note and time‌technical note 40fps «active» is andtechnical note technical note SetWindowPos technical note
# technical note‌technical noteandtechnical note window technical note technical note technical note technical note‌technical note (withtechnical note technical note technical note‌technical note — technical note is).
# technical note:
#   NORMAL          → Stutter   |  NO-MOVE (technical note technical note) → without Stutter
#     ⇒ technical note technical notewithtechnical note deterministic: technical noteandtechnical note technical note HWND / Window Manager / DWM.
#   technical note technical noteand technical note Stutter ⇒ technical note from technical note technical noteandtechnical note‌technical note technical note technical note‌technical noteandtechnical note technical note technical noteandtechnical note
#     Show / DWM composition / GPU (technical note 16 technical note 3).
# (test technical note = TV_SNAP_DEBUG_NO_ANIM in withtechnical note technical note technical noteandtechnical note — display completetechnical note technical note.)
TV_SNAP_DEBUG_ANIM_NO_MOVE = _snap_env_flag("TV_SNAP_DEBUG_ANIM_NO_MOVE", False)

# --- versiontechnical note 10technical note21 — test 3 user: only «technical note» SetWindowPos in momenttechnical note andtechnical noteandtechnical note ---
# Overlay from before Preload technical note → Show → only «technical note» SetWindowPos technical notefromtechnical note‌technical note‌technical note
# to technical note technical note aftertechnical note technical note technical note in secondtechnical note first (without technical note without technical note).
# if technical note technical note technical noteandtechnical note 100-200ms length technical note → technical note technical noteandtechnical note technical noteandtechnical note/
# DWM/composition istechnical note technical note time‌technical note technical note. (firstandtechnical note: NO_ANIM > SINGLE_MOVE)
TV_SNAP_DEBUG_ANIM_SINGLE_MOVE = _snap_env_flag(
    "TV_SNAP_DEBUG_ANIM_SINGLE_MOVE", False)

# --- versiontechnical note 10technical note21 — test 5 user: technical note complete andtechnical noteandtechnical note «technical note» SetWindowPos ---
# old/new x,y + y real after from technical note + HWND + native TID + priority + flags
# + return + GetLastError + before/after (Foreground/Visible/TOPMOST/LAYERED/
# TRANSPARENT/NOACTIVATE). if technical note from threshold technical note technical noteandtechnical note → sampletechnical note technical note
# UI-Thread from technical note technical note register technical note‌technical noteandtechnical note (detection «UI technical note technical noteandtechnical note technical note technical note‌technical note»).
TV_SNAP_SWP_WIN_DEBUG = _snap_env_flag("TV_SNAP_SWP_WIN_DEBUG", True)
TV_SNAP_UI_STACK_ON_SLOW_MS = 30.0

# --- versiontechnical note 10technical note19 — Preload real window (log user: NO PREBUILT WINDOW in
# momenttechnical note Show) ---
# if windowtechnical note technical note‌technical note technical note technical noteandtechnical note technical note again until «technical note momenttechnical note Show» resume
# technical note‌ortechnical note (self-heal) — andtechnical note never in momenttechnical note Show start technical note‌technical noteandtechnical note.
TV_SNAP_PRELOAD_RETRY_MIN_GAP_SEC = 0.5   # technical note distancetechnical note technical noteand technical note self-heal
TV_SNAP_PRELOAD_MIN_REMAIN_SEC = 0.4      # technical note from technical note until Show → technical note new technical note‌technical noteandtechnical note (technical note technical note‌technical note)

# --- versiontechnical note 10technical note22 — Snapshot Window Lifecycle Manager (technical note technical note user) ---
# technical note: «window must before from technical noteortechnical note to display technical note technical note withtechnical note» — technical note in momenttechnical note Show.
# 1) windowtechnical note threshold‌technical note technical note Preload (firstandtechnical note 1): for technical noteortechnical note‌withtechnical note‌technical note (h1/h2/et)
#    technical note technical note Worker after from «technical note − technical note second» if windowtechnical note technical note‌technical note READY
#    technical noteandtechnical note same‌technical note dispatch technical note‌technical noteandtechnical note (if match_time >= preload_start)technical note
#    technical note windowtechnical note 2 second‌technical note technical note‌technical note is not. technical note technical noteandtechnical note technical noteandtechnical note: technical noteandtechnical note
#    technical noteortechnical note‌withtechnical note same PNG technical note «minutetechnical note technical note − 1» is (technical note technical note) → technical note
#    technical noteandtechnical note windowtechnical note technical noteandtechnical note display technical note technical note‌technical note change technical note‌technical note.
#    (display «end» technical note technical note windowtechnical note beforetechnical note technical note technical note: rendertechnical note in momenttechnical note stop
#    technical note technical note‌technical noteandtechnical note and render technical noteandtechnical note = charttechnical note technical note‌data‌technical note = change technical noteandtechnical note.)
TV_SNAP_PRELOAD_WIDE_LEAD_SEC = 10.0

# --- versiontechnical note 10technical note23 — architecture new GPU Overlay (technical note technical note user) ---
# «window technical note‌andtechnical note technical note technical note‌technical note technical note technical note inside GPU (Shader) is.»
#   TV_SNAP_GPU_OVERLAY      → technical noteandtechnical note = path beforetechnical note (Tk Layered) in start
#   TV_SNAP_GPU_VSYNC        → technical note render synchronized with displaytechnical note (without CPU Busy Loop)
#   TV_SNAP_GPU_CLICKTHROUGH → windowtechnical note Overlay input technical noteandtechnical note technical note technical note technical note‌technical note
#   TV_SNAP_GPU_ANIM_DEBUG   → technical noteandtechnical note [OVERLAY ANIM DEBUG] after from technical note technical note
# technical note from Environment Variable technical note technical note technical note‌technical noteandtechnical note (unchanged code).
TV_SNAP_GPU_OVERLAY = _snap_env_flag("TV_SNAP_GPU_OVERLAY", True)
TV_SNAP_GPU_VSYNC = _snap_env_flag("TV_SNAP_GPU_VSYNC", True)
TV_SNAP_GPU_CLICKTHROUGH = _snap_env_flag("TV_SNAP_GPU_CLICKTHROUGH", True)
TV_SNAP_GPU_ANIM_DEBUG = _snap_env_flag("TV_SNAP_GPU_ANIM_DEBUG", False)   # versiontechnical note 10technical note24 — default technical noteandtechnical note (technical note log technical noteandtechnical note)
TV_SNAP_GPU_INIT_WAIT_SEC = 4.0        # technical note technical note for Context GPU in start


class SnapshotState(Enum):
    """versiontext 10text22 — text text cycletext text windowtext Snapshot (specification user):
    EMPTY → PREPARING → READY → SHOWING → VISIBLE → (hidden‌textfromtext) EMPTY.
    with textandtext‌text [SNAPSHOT_STATE] text text log text‌textandtext until text «textandtext» textwithtext."""
    EMPTY = 0
    PREPARING = 1
    READY = 2
    SHOWING = 3
    VISIBLE = 4


def _snap_thread_tag() -> str:
    """text text current for log display textagetext‌text (Main/UI or Worker or Anim)."""
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
    """versiontext 10text20 — text native text current (Win32 GetCurrentThreadId) for
    text log with Process Explorer / ETW (text 8 user). text andtextandtext → 0."""
    if os.name == "nt":
        try:
            import ctypes as _ct
            return int(_ct.windll.kernel32.GetCurrentThreadId())
        except Exception:
            pass
    return 0


def _snap_tid_text() -> str:
    """versiontext 10text20 — «Thread ID: <python> (native <win32>)» for log (text 8)."""
    try:
        py_id = threading.get_ident()
    except Exception:
        py_id = 0
    nat = _snap_native_tid()
    return (f"Thread ID: {py_id}"
            + (f" (native {nat})" if nat else ""))


class SnapShowTrace:
    """versiontext 10text18 — time‌agetext perf_counter path display textagetext‌text (text 1 user):
    text text with «time start/end/text (ms)text text HWNDtext text» register and textdistance
    in Console print text‌textandtext. time‌text ratio to momenttext text text (T+ms) text and
    value text perf_counter text for text print text‌textandtext.
    only for path Snapshot Show — text text text from text istext text‌text."""

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

    # --- technical note moment‌technical note (without technical notefromtechnical note‌technical note technical note) ---
    def step(self, label: str, hwnd=None, size=None, note: str = "") -> float:
        now = time.perf_counter()
        rel = (now - self.t0) * 1000.0
        self._emit(label, rel, None, hwnd, size, note)
        return now

    # --- technical note start/end for technical note technical note technical note ---
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

# untiltechnical note/technical note start withtechnical note — technical noteandtechnical note technical note withtechnical note technical note tex (height ≈ 42px)
TV_TIMESTAMP_Y = 21.0
TV_TIMESTAMP_FONT_PT = 17            # in dpi=100 ≈ 24px — inside technical noteandtechnical note technical note technical note‌technical noteandtechnical note
TV_TIMESTAMP_BG_ALPHA = 0.62


def snap_ease_in_out(p: float) -> float:
    """text ease-in-out text (versiontext 10text13): output 0→1 with text smooth and
    text in text and text and text in textortext — exactly text user for andtextandtext/textandtext
    chart textagetext‌text."""
    p = min(1.0, max(0.0, float(p)))
    if p < 0.5:
        return 4.0 * p * p * p
    q = 2.0 * p - 2.0
    return 1.0 + 0.5 * q * q * q


def snap_clamp_minute(key: str, value) -> int:
    """textandtextfromtext minute to withtext textfrom same section (38..44 / 80..89 / 110..119)."""
    lo, hi = TV_SNAP_RANGES.get(key, (0, 130))
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = TV_SNAP_DEFAULT_MINUTE.get(key, lo)
    return max(lo, min(hi, v))


def snap_clamp_seconds(value, default: float = 20.0) -> int:
    """text display: 5 until 300 secondtext real."""
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError):
        v = int(default)
    return max(5, min(300, v))


def snap_load_settings(script_dir: str) -> Dict[str, Any]:
    """read text save‌text (file text text) + text with default‌text
    and textandtextfromtext text — file broken/text = default‌text."""
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
    """savetext text (JSON text text — until text after textortext to text textwithtext)."""
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
    """textandtext text/text display (until 8K — ratio text never to text text‌text):
         w = min(0.33×sw text 0.32×sh×ratio)   h = w÷ratio
         x = 0.03×sw text y = sh − h − 0.02×sh   (textandtext below-text)
       text textfromtext: real.png (text real ≈ 33text width / 32text height).
       output: (x, y, w, h) to text."""
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
    """versiontext 10text16 — text‌textfromtext agetext text «text from UI-Thread» (text text
    andtextandtext — text user: text to text text):
      1) resize to text text (LANCZOS)
      2) text‌text text → text BGRA text UpdateLayeredWindow
    output: (disp, arr, (x, y_final, w, h)) — in Error (None, None, None).
    untiltext text is (without Tk) and from text Worker textandtext text‌textandtext."""
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
# 25technical note5 — GPU OVERLAY RENDERER (versiontechnical note 10technical note23 — architecture Game Overlay real)
# ---------------------------------------------------------------------
# technical note technical note user: «windowtechnical note Overlay must only technical note‌withtechnical note technical note technical noteandtechnical note technical note‌andtechnical note
# technical note technical note and technical note technical note inside GPU technical note technical noteandtechnical note.»
#
#   Python Logic ──► GPU Texture (PNG technical note Worker — same LANCZOS)
#        ──► Fragment Shader (technical note + ease-in-out + premultiply technical note)
#        ──► OpenGL Swapchain technical noteandtechnical note windowtechnical note «technical note» technical note (GLFW)
#        ──► DWM ──► DirectX withtechnical note
#
#   * window technical note‌andtechnical note technical note/resize/show-hide technical note‌technical noteandtechnical note «technical note» technical note technical noteandtechnical note
#     completetechnical note technical note (technical note technical note) — DWM technical note technical note‌andtechnical note intechnical note technical note HWND is not.
#   * Show/Hide only queue.put is (technical note ~0technical note1ms) — technical note technical noteandtechnical note andtechnical noteandtechnical note.
#   * technical note: CPU only progress=(now-start)/dur technical note‌technical note interpolation
#     and technical note ease inside Shader is. in length technical note «technical note» SetWindowPos.
#   * technical note render with vsync synchronized istechnical note without technical note technical noteandtechnical note technical note message technical note
#     technical note‌technical note (technical note CPU Busy Loop). firstandtechnical note technical note technical note technical note‌technical noteandtechnical note
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
layout(location = 0) in vec2 a_px;          // coordinates text level (text withtext-text)
uniform vec2 u_surf;                        // textfromtext level (text)
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
uniform vec2  u_tex_size;                   // textfromtext textandtext (text)
uniform vec2  u_img;                        // text «text» textandtext withtext-text textandtext textandtext level
uniform float u_travel;                     // distancetext textandtext text (text)
uniform float u_progress;                   // 0..1 — CPU only time text‌text
uniform float u_dir;                        // +1 andtextandtext (withtext) | -1 textandtext (below)
out vec4 frag;
float ease_in_out(float p) {                // text snap_ease_in_out (10text13)
    p = clamp(p, 0.0, 1.0);
    if (p < 0.5) return 4.0 * p * p * p;
    float q = 2.0 * p - 2.0;
    return 1.0 + 0.5 * q * q * q;
}
void main() {
    float e = ease_in_out(u_progress);
    float t = (u_dir > 0.0) ? (1.0 - e) : e;   // 1 = completetext text text | 0 = text text
    vec2 origin = u_img + vec2(0.0, t * u_travel);
    vec2 p = v_px - origin;
    if (p.x < 0.0 || p.y < 0.0 || p.x >= u_tex_size.x || p.y >= u_tex_size.y) {
        frag = vec4(0.0);                   // outside textandtext = completetext text
        return;
    }
    vec4 c = texture(u_tex, (p + vec2(0.5)) / u_tex_size);  // text text — without untiltext
    frag = vec4(c.rgb * c.a, c.a);          // premultiplied alpha for DWM
}
"""


def _gpu_surface_geo(sw: int, sh: int) -> Tuple[int, int, int, int]:
    """level «text» Overlay — total path text text text for «text» textfromtext
    Snapshot textandtext text‌text. sectiontext text texttotext text to‌textandtext text outside textandtext
    is — exactly text when text windowtext real text text text text‌text text text
    andtextandtext/textandtext text‌to‌text sametext path beforetext is (window text text‌text)."""
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
    """text textandtext «inside level text» + distancetext text (texttotext text — agetext is not)."""
    return {"dx": int(x) - int(surf_x), "dy": int(y_final) - int(surf_top),
            "travel": max(1, int(sh) + 4 - int(y_final))}


