# -*- coding: utf-8 -*-
# =============================================================================
#  BroadcastRenderer.py — موتور گرافیک برودکاستی GPU  (فقط لایه‌ی نمایش/انیمیشن)
#  PES2017 HeatMap — Broadcast Graphics Engine — ModernGL / OpenGL 3.3 Core
# =============================================================================
#  قانون طلایی پروژه:
#    این موتور «هیچ» هیت‌مپی تولید نمی‌کند. ورودی آن عیناً خروجی موتور موجود است:
#        heat_rgba      = density_to_heat_rgba(...)      ← EXACT SAME HEATMAP
#        pitch_plate    = build_flat_pitch_texture(None) ← چمن+خطوط+دروازه تخت (دست‌نخورده)
#    CPU فقط: داده، تایم‌لاین، ورودی، بارگذاری Asset (همه «یک‌بار» هنگام ساخت صحنه)
#    GPU: تمام رندر — پرسپکتیو، Blur، Glow، شیشه، ذرات، سوییپ، ترکیب لایه‌ها
#    لذا در حلقه‌ی فریم حتی یک خط Pillow اجرا نمی‌شود.
#
#  ┌── قرارداد مختصات (COORDINATE CONTRACT) — تنها مرجع تبدیل مختصات در کل پروژه ──┐
#  │ (1) PES world:  x∈[-55,55] طولی چپ→راست | z∈[-37,37] عرضی؛ z_min=-37 = لبه دور  │
#  │ (2) انباشت (Provider — بدون تغییر):                                             │
#  │        gx=(x+55)/110*(GRID_W-1) → ستون i    |  gy=(z+37)/74*(GRID_H-1) → سطر j  │
#  │        پس سطر 0 گرید = z_min                                                    │
#  │ (3) density_to_heat_rgba (Provider — بدون تغییر): PIL RGBA؛ سطرِ بالای تصویر     │
#  │     = z_min و ستون چپ = x_min — عین همان چیزی که نمای دوبعدی زنده نشان می‌دهد    │
#  │ (4) آپلود تکسچر Heat: عیناً بدون flip → در GL سطر اول حافظه = v=0 = z_min        │
#  │ (5) شیدر زمین:  پلیت: u=(x-TEX_X_MIN)/(TEX_X_MAX-TEX_X_MIN)                    │
#  │                v=(z-TEX_Z_MIN)/(TEX_Z_MAX-TEX_Z_MIN)                            │
#  │     Heat: u=(x+55)/110 ، v=(z+37)/74  → بازه موتور؛ عین نمای دوبعدی زنده        │
#  │     (نگاشت خطی uv پلتفرم→موتور داخل شیدر — بدون هیچ flip)                       │
#  │ (6) هاوموگرافی UV→صفحه: (0,0)→PFL دور-چپ | (1,0)→PFR دور-راست                   │
#  │     (1,1)→PNR نزدیک-راست | (0,1)→PNL نزدیک-چپ                                    │
#  │     ⇒ لبه‌ی دورِ صفحه = z_min = بالای تصویر — دقیقاً مثل نمای دوبعدی زنده          │
#  │ (7) اسپرایت‌ها (عکس/لوگو/متن/اورلی): آپلود با «یک» flip مستند → v=1 = بالای تصویر؛│
#  │     پیکسل (px,py) تصویر دقیقاً روی (px,py) صفحه می‌نشیند                          │
#  │ (8) هیچ ماژول دیگری حق flip/scale/mirror مستقل ندارد — فقط همین قرارداد          │
#  └──────────────────────────────────────────────────────────────────────────────┘
# =============================================================================

import math
import os
import sys
import time
import ctypes
import threading

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ---------------------------------------------------------------------
# [SUITE v2.1.4] CRASH-PROOF STDOUT/STDERR — must run before ANY print.
# Same field bug as HeatMapMod: with the stream on a FILE/PIPE (bridge
# child log, redirected run) Python uses the legacy ANSI 'charmap'
# codec, and one Persian/Arabic log line (ENGINE banners carry dynamic
# fail reasons) raises UnicodeEncodeError inside the render thread.
# 1) console -> UTF-8 codepage, 2) streams -> utf-8 + errors='replace',
# 3) wrapper so a failing write degrades instead of raising.
# ---------------------------------------------------------------------
class _CrashProofStream:
    """write()/flush() can never raise; every other attribute is delegated."""

    def __init__(self, stream):
        self._s = stream

    def write(self, s):
        try:
            return self._s.write(s)
        except Exception:
            try:
                return self._s.write(
                    str(s).encode("ascii", "replace").decode("ascii"))
            except Exception:
                try:
                    return len(s)
                except Exception:
                    return 0

    def flush(self):
        try:
            self._s.flush()
        except Exception:
            pass

    def __getattr__(self, attr):
        return getattr(self._s, attr)


def _suite_harden_stdio():
    if sys.platform == "win32":
        try:
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for _st in (sys.stdout, sys.stderr):
        if _st is None:
            continue                                  # pythonw / detached
        try:
            if hasattr(_st, "reconfigure"):
                _st.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stdout is not None and not isinstance(sys.stdout, _CrashProofStream):
        sys.stdout = _CrashProofStream(sys.stdout)
    if sys.stderr is not None and not isinstance(sys.stderr, _CrashProofStream):
        sys.stderr = _CrashProofStream(sys.stderr)


_suite_harden_stdio()

# ---------------------------------------------------------------- ابعاد خروجی
RENDER_W, RENDER_H = 1774, 887          # عین رندر ثابت قبلی (اندازه‌گیری از مرجع)
FPS = 60.0

# --------------------------------------------------- هندسه سکوی چمن (مرجع)
PFL = (255.0, 288.0)     # دور-چپ
PFR = (1531.0, 288.0)    # دور-راست
PNR = (1723.0, 783.0)    # نزدیک-راست
PNL = (53.0, 783.0)      # نزدیک-چپ

# --------------------------------------------------- رنگ‌ها (عین ثابت‌های Provider)
BG_BASE_TOP  = (2, 24, 62)
BG_BASE_BOT  = (0, 12, 34)
BG_GLOW_COL  = (16, 78, 158)
FRAME_COL    = (134, 174, 222)
PANEL_TOP    = (15, 52, 100)
PANEL_BOT    = (6, 34, 78)
PANEL_EDGE_T = (108, 152, 214)
PANEL_EDGE_B = (208, 224, 246)
BAR_COL_L    = (7, 66, 168)
BAR_COL_R    = (10, 84, 196)
RING_COL     = (150, 192, 235)
TXT_WHITE    = (246, 250, 255)

# --------------------------------------------------- چیدمان هدر (عین render_broadcast_heatmap)
CIRCLE_C   = (202.0, 192.0)
CIRCLE_R   = 127
BAR_X0, BAR_Y0, BAR_Y1 = 312, 127, 182
BAR_SLANT  = 22
NAME_X, NAME_Y = 385, 154
LOGO_BOX   = (330, 205, 78, 72)                 # بازیکن/تیم
LOGO_BOX_ALL = ((330, 205, 72, 66), (418, 205, 72, 66))   # نمای همه
# [PT v2.3.0] چیپ SHIRT/AGE — سمت راست لوگوی باشگاه (لوگو تا x=408)، هم‌تراز آن
META_X0, META_Y0, META_H = 442, 205, 72
TITLE_PANEL = (373, 6, 1070, 100)               # x0,y0,w,h
FRAME_RECT  = (22.0, 22.0, RENDER_W - 44.0, RENDER_H - 44.0)
FRAME_R     = 42.0

# فونت‌های جایگزین لینوکسی (روی ویندوز لیست Segoe از Provider استفاده می‌شود)
_LINUX_FONTS_BOLD = [
    "/usr/share/fonts/truetype/english/Carlito-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_LINUX_FONTS_REG = [
    "/usr/share/fonts/truetype/english/Carlito-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

# ---------------------------------------------------------------- easing ها
def clamp01(t):
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)

def seg(f, a, b):
    """پیشرفت 0..1 در بازه فریم [a,b]"""
    if b <= a:
        return 1.0
    return clamp01((f - a) / (b - a))

def out_cubic(t):   t = clamp01(t); return 1.0 - (1.0 - t) ** 3
def out_quint(t):   t = clamp01(t); return 1.0 - (1.0 - t) ** 5
def in_cubic(t):    t = clamp01(t); return t ** 3
def in_quart(t):    t = clamp01(t); return t ** 4
def in_out_cubic(t):
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1.0 - (-2 * t + 2) ** 3 / 2.0

def out_back(t, k=1.35):
    """پاپ ظریف برودکاستی (بدون بانس کارتونی)"""
    t = clamp01(t)
    t -= 1.0
    return 1.0 + (k + 1.0) * t ** 3 + k * t ** 2

def heat_staged(t):
    """پیشروی پله‌ای ورود Heatmap: 0→10→35→70→100 درصد (بند ۱۳ دستور)"""
    t = clamp01(t)
    pts = ((0.00, 0.00), (0.14, 0.10), (0.42, 0.35), (0.72, 0.70), (1.00, 1.00))
    for i in range(len(pts) - 1):
        t0, v0 = pts[i]
        t1, v1 = pts[i + 1]
        if t0 <= t <= t1:
            f = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
            f = f * f * (3.0 - 2.0 * f)          # smoothstep
            return v0 + (v1 - v0) * f
    return 1.0

# ---------------------------------------------------------------- هاوموگرافی
def solve_homography(src, dst):
    """هاوموگرافی 3x3 که src→dst را نگاشت می‌کند (هر دو 4 نقطه).
       عین همان تبدیلی است که Provider با _find_coeffs برای PIL انجام می‌دهد؛
       اینجا معکوسِ رو به جلو برای شیدر ساخته می‌شود (بدون تغییر شکل هندسی)."""
    A = []
    B = []
    for (x, y), (X, Y) in zip(src, dst):
        A.append([x, y, 1, 0, 0, 0, -X * x, -X * y]); B.append(X)
        A.append([0, 0, 0, x, y, 1, -Y * x, -Y * y]); B.append(Y)
    A = np.array(A, dtype=np.float64)
    B = np.array(B, dtype=np.float64)
    h = np.linalg.solve(A, B)
    H = np.array([[h[0], h[1], h[2]],
                  [h[3], h[4], h[5]],
                  [h[6], h[7], 1.0]], dtype=np.float64)
    return H

def stage_scale_matrix(s, cx, cy):
    """ماتریس مقیاس حول مرکز (برای ورود Stage از 0.94→1.00)"""
    T1 = np.array([[1, 0, -cx], [0, 1, -cy], [0, 0, 1]], dtype=np.float64)
    S  = np.array([[s, 0, 0], [0, s, 0], [0, 0, 1]], dtype=np.float64)
    T2 = np.array([[1, 0, cx], [0, 1, cy], [0, 0, 1]], dtype=np.float64)
    return T2 @ S @ T1

# ================================================================
#  شیدرها — GLSL 330 Core
# ================================================================
_VS_QUAD = """
#version 330
in vec2 in_pos;          /* 0..1 */
in vec2 in_uv;           /* v=1 بالای تصویر (اسپرایت‌ها — قرارداد بند ۷) */
uniform vec2 uRes;
uniform vec4 uRect;      /* x,y,w,h پیکسل */
uniform vec2 uPivot;
uniform float uRot;
out vec2 v_uv;
out vec2 v_px;
void main(){
    vec2 w = uRect.xy + in_pos * uRect.zw;
    if (abs(uRot) > 1e-6){
        vec2 d = w - uPivot;
        float c = cos(uRot), s = sin(uRot);
        w = uPivot + vec2(d.x*c - d.y*s, d.x*s + d.y*c);
    }
    v_uv = in_uv;
    v_px = w;
    gl_Position = vec4(w.x / uRes.x * 2.0 - 1.0, 1.0 - w.y / uRes.y * 2.0, 0.0, 1.0);
}
"""

# --- اسپرایت عمومی (عکس/لوگو/متن/اورلی): زنجیره بلور A/B + آلفا + سوییپ روی متن
_FS_SPRITE = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform sampler2D uTexA;
uniform sampler2D uTexB;
uniform float uMix;
uniform float uAlpha;
uniform float uSweepX;
uniform float uSweepW;
uniform float uSweepAmt;
void main(){
    vec4 a = texture(uTexA, v_uv);
    vec4 b = texture(uTexB, v_uv);
    vec4 c = mix(a, b, clamp(uMix, 0.0, 1.0));
    float aa = c.a * uAlpha;
    vec3 rgb = c.rgb;
    if (uSweepAmt > 0.0005){
        float d = (v_uv.x - uSweepX) / max(uSweepW, 1e-4);
        float band = exp(-d * d);
        rgb += vec3(0.75, 0.85, 1.0) * band * uSweepAmt * c.a;
    }
    f_color = vec4(rgb * aa, aa);   /* premultiplied */
}
"""

# --- زمین: پلیت (چمن+خطوط+دروازه) + Heat دقیق + Glow + ورود Heat (بند ۱۳)
_VS_PITCH = """
#version 330
in vec2 in_uv;           /* u=x_frac  v=z_frac — قرارداد بند ۵/۶ */
uniform vec2 uRes;
uniform mat3 uH;         /* uv → پیکسل صفحه */
out vec2 v_uv;
void main(){
    v_uv = in_uv;
    vec3 p = uH * vec3(in_uv, 1.0);
    float w = max(p.z, 1e-5);
    float sx = p.x / w, sy = p.y / w;
    float ndc_x = sx / uRes.x * 2.0 - 1.0;
    float ndc_y = 1.0 - sy / uRes.y * 2.0;
    gl_Position = vec4(ndc_x * w, ndc_y * w, 0.0, w);   /* پرسپکتیو-کوریکت */
}
"""

_FS_PITCH = """
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D uPlateA;   /* تکسچر چمن دقیق (بدون تغییر) */
uniform sampler2D uPlateB;   /* سطح بلور زنجیره */
uniform sampler2D uHeatA;    /* Heat عیناً همان خروجی برنامه (premult) */
uniform sampler2D uHeatB;
uniform sampler2D uGlow;     /* Heat بلورشده برای Glow */
uniform float uPlateMix;
uniform float uHeatMix;
uniform float uHeatScale;    /* 1.03 → 1.00 هنگام ورود */
uniform vec2 uHeatU;         /* نگاشت uv پلتفرم → uv موتور برای Heat (بند ۵ قرارداد) */
uniform vec2 uHeatV;
uniform float uHasHeat;
uniform float uHeatA_amt;    /* شفافیت نهایی Heat */
uniform float uGlowAmt;      /* درخشش ثابت (بدون ضربان) */
uniform float uAlpha;        /* ورود Stage */
void main(){
    vec4 plate = mix(texture(uPlateA, v_uv), texture(uPlateB, v_uv), clamp(uPlateMix, 0.0, 1.0));
    vec3 col = plate.rgb;
    float a = plate.a;
    if (uHasHeat > 0.5){
        /* uv تکسچر Heat = مختصات موتور PES — دقیقاً مثل نمای دوبعدی زنده.
           (پلیت بازه سکو ±56.1/±35.9 دارد ولی Heat روی بازه موتور ±55/±37 است؛
            نگاشت خطی زیر همان جای‌گذاری نمای زنده را بازتولید می‌کند) */
        vec2 puv = (v_uv - 0.5) / max(uHeatScale, 0.05) + 0.5;   /* مقیاس ظریف 1.03→1.00 */
        vec2 cuv = vec2(uHeatU.x * puv.x + uHeatU.y,
                        uHeatV.x * puv.y + uHeatV.y);
        vec4 h = mix(texture(uHeatA, cuv), texture(uHeatB, cuv), clamp(uHeatMix, 0.0, 1.0));
        float ha = h.a * uHeatA_amt;
        /* Heat روی پلیت — مثل نمای زنده (source-over) */
        col = h.rgb * uHeatA_amt + col * (1.0 - ha);
        a   = max(a, ha * plate.a + ha * (1.0 - plate.a));
        /* Glow ثابت — فقط نور اضافه، محتوای Heat دست‌نخورده (بند ۱۵) */
        vec3 g = texture(uGlow, cuv).rgb;
        col += g * uGlowAmt;
    }
    f_color = vec4(col * a * uAlpha, a * uAlpha);
}
"""

# --- نوار اسم: گرادیان + پخ برش + رشد عرض + نور لبه + خط زیر (بند ۱۱)
_FS_BAR = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform vec2 uRes;
uniform vec4 uRect;        /* x0,y0,w_full,h(=63) */
uniform float uBarW;       /* عرض فعلی نوار */
uniform float uSlant;
uniform float uAlpha;
uniform float uLightX;     /* موقعیت نور لبه (local px) */
uniform float uLightAmt;
uniform vec3 uColL;
uniform vec3 uColR;
void main(){
    float lx = v_uv.x * uRect.z;                /* v_uv همیشه مصرف می‌شود (ضد حذف کامپایلر) */
    float ly = (1.0 - v_uv.y) * uRect.w;
    float barH = 55.0;
    vec3 rgb = vec3(0.0);
    float a = 0.0;
    if (ly < barH){
        float edge = uBarW - uSlant * (ly / barH);
        float m = 1.0 - smoothstep(edge - 1.0, edge + 1.0, lx);
        if (m > 0.002){
            float t = clamp(lx / max(uBarW, 1.0), 0.0, 1.0);
            vec3 c = mix(uColL, uColR, t);
            float shade = 1.0 - 0.18 * smoothstep(0.0, barH, ly);   /* عمق عمودی ظریف */
            c *= shade;
            rgb += c * m;
            a = m;
        }
        if (uLightAmt > 0.003){
            float d = (lx - uLightX) / 16.0;
            float band = exp(-d * d);
            rgb += vec3(0.65, 0.82, 1.0) * band * uLightAmt * step(lx, edge) * a;
        }
    } else {
        /* خط زیر نوار — عین رندر ثابت: y 187..190 آلفا 60+150*g */
        float u = clamp((ly - 60.0) / 3.0, 0.0, 1.0);
        float band = 1.0 - smoothstep(0.0, 1.0, u);
        float g = exp(-pow((lx - 160.0) / 420.0, 2.0));
        float aa = (60.0 + 150.0 * g) / 255.0 * band;
        rgb += vec3(110.0, 158.0, 225.0) / 255.0 * aa;
        a = max(a, aa);
    }
    f_color = vec4(rgb * a * uAlpha, a * uAlpha);
}
"""

# --- پنل عنوان ذوزنقه‌ای (عین هندسه رندر ثابت)
_FS_TITLE_PANEL = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform vec4 uRect;        /* (373,6,1070,100) با مقیاس Stage */
uniform float uAlpha;
uniform float uGlobalX0;   /* 373 — برای گاوسی مرکز-روشن */
void main(){
    float w = uRect.z, h = uRect.w;
    float px = v_uv.x * w;
    float t  = v_uv.y;                 /* 0 بالا */
    float py = t * h;
    float slant = 35.0;
    float xl = slant * (1.0 - t);          /* مرز چپ */
    float xr = (w - 35.0) + slant * t;     /* مرز راست */
    float m = step(xl, px) * step(px, xr);
    if (m < 0.5){ discard; }
    vec3 c = mix(vec3(15.0,52.0,100.0), vec3(6.0,34.0,78.0), t) / 255.0;
    /* برش‌های مورب ظریف داخل پنل */
    float c1l = 127.0 + 60.0 * t, c1r = 267.0 + 60.0 * t;
    if (px > c1l && px < c1r) c += vec3(0.027);
    float c2l = 759.0 + 48.0 * t, c2r = 879.0 + 48.0 * t;
    if (px > c2l && px < c2r) c *= (1.0 - 0.063);
    vec3 rgb = c;
    float a = 1.0;
    /* خط لبه بالا/پایین با مرکز-روشن گاوسی — عین رندر ثابت */
    float gx = uGlobalX0 + px;
    if (py < 3.0){
        float f1 = exp(-pow((gx + 2.0 - 887.0) / 470.0, 2.0));
        rgb = vec3(108.0,152.0,214.0)/255.0;
        a = (30.0 + 200.0 * f1) / 255.0;
    }
    if (py > h - 4.5){
        float f2 = exp(-pow((gx + 2.0 - 887.0) / 620.0, 2.0));
        rgb = vec3(208.0,224.0,246.0)/255.0;
        a = max(a, (50.0 + 205.0 * f2) / 255.0);
    }
    f_color = vec4(rgb * a * uAlpha, a * uAlpha);
}
"""

# --- پس‌زمینه: گرادیان + هاله مرکز-بالا با حرکت بسیار آهسته (Live TV feel)
_FS_BG = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform vec2 uRes;
uniform float uT;
uniform float uAlpha;
void main(){
    float t = 1.0 - v_uv.y;                    /* گرادیان از uv (بالای کواد = روشن‌تر) */
    vec3 base = mix(vec3(2.0,24.0,62.0), vec3(0.0,12.0,34.0), t) / 255.0;
    vec2 cc = vec2(uRes.x * 0.5 + sin(uT * 0.045) * 26.0,
                   uRes.y * 0.24 + cos(uT * 0.038) * 16.0);
    vec2 dd = (v_px - cc) / vec2(uRes.x * 0.42, uRes.y * 0.42);
    float dist = length(dd);
    float g = pow(max(1.0 - dist, 0.0), 1.6);
    vec3 col = mix(base, vec3(16.0,78.0,158.0) / 255.0, g * 0.95);
    f_color = vec4(col * uAlpha, uAlpha);
}
"""

# --- شیشه: SDF مستطیل گرد — پرکردن داخلی | خط لبه + هاله + سوییپ‌ها
_FS_GLASS = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform vec4 uFrame;      /* x,y,w,h */
uniform float uRadius;
uniform float uMode;      /* 0=پرکردن  1=لبه+هاله+سوییپ */
uniform float uAlpha;
uniform float uTopSweep;  /* 0..1 موقعیت نور لبه بالا */
uniform float uTopAmt;
uniform float uSpecPos;   /* موقعیت پیکسلی سوییپ مورب */
uniform float uSpecAmt;
float sdRoundBox(vec2 p, vec2 b, float r){
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}
void main(){
    vec2 ctr = uFrame.xy + uFrame.zw * 0.5;
    float d = sdRoundBox(v_px - ctr, uFrame.zw * 0.5, uRadius);
    vec3 rgb = vec3(0.0);
    float a = 0.0;
    if (uMode < 0.5){
        /* پرکردن شیشه‌ای: سرمه‌ای نیمه‌شفاف با گرادیان عمودی ظریف */
        if (d < 0.0){
            float t = clamp(1.0 - v_uv.y, 0.0, 1.0);
            vec3 c = mix(vec3(10.0, 36.0, 82.0), vec3(4.0, 20.0, 52.0), t);
            a = mix(0.115, 0.145, t);
            rgb = c / 255.0 * 2.2;
        }
    } else {
        /* خط لبه روشن — عین قاب رندر ثابت (عرض ~5px) */
        float line = 1.0 - smoothstep(2.0, 3.2, abs(d));
        float halo = exp(-abs(d) / 9.0) * (1.0 - line);
        rgb += vec3(134.0,174.0,222.0)/255.0 * line;
        a   = max(a, line * 0.95);
        rgb += vec3(120.0,168.0,230.0)/255.0 * halo * 0.85;
        a   = max(a, halo * 0.55);
        /* خط داخلی مویی */
        float hair = 1.0 - smoothstep(0.6, 1.4, abs(d - 14.0));
        rgb += vec3(60.0,105.0,170.0)/255.0 * hair * 0.6;
        a   = max(a, hair * 0.35);
        /* نور باریک روی لبه بالا هنگام ورود + تکرار خیلی آهسته */
        if (uTopAmt > 0.004){
            float tt = (v_px.x - uFrame.x) / uFrame.z;
            float band = exp(-pow((tt - uTopSweep) * uFrame.z / 75.0, 2.0));
            float topEdge = (1.0 - smoothstep(2.0, 4.5, abs(d))) *
                            (1.0 - smoothstep(24.0, 44.0, v_px.y - uFrame.y));
            rgb += vec3(0.80, 0.90, 1.0) * band * topEdge * uTopAmt;
            a = max(a, band * topEdge * uTopAmt * 0.8);
        }
        /* سوییپ مشخصِ مورب — بسیار نرم، دوره‌ای (بند ۷ و ۱۶) */
        if (uSpecAmt > 0.004){
            float s = v_px.x + v_px.y * 0.35;
            float band2 = exp(-pow((s - uSpecPos) / 240.0, 2.0));
            float inside = 1.0 - smoothstep(-6.0, -2.0, d);
            rgb += vec3(0.65, 0.78, 1.0) * band2 * inside * uSpecAmt;
        }
    }
    f_color = vec4(rgb * a * uAlpha, a * uAlpha);
}
"""

# --- ذرات محیطی: ۱۰۰ ذره، کاملاً روی GPU (بند ۶ و ۱۶)
_VS_PART = """
#version 330
in vec3 in_a;    /* x0, y0, speed */
in vec2 in_b;    /* phase, size */
uniform vec2 uRes;
uniform float uT;
uniform float uAlpha;
out float v_a;
void main(){
    float span = uRes.y + 60.0;
    float y = mod(in_a.y - uT * (4.0 + 9.0 * in_a.z), span) - 30.0;
    float x = in_a.x + sin(uT * 0.30 + in_b.x * 6.2831) * 16.0;
    float tw = 0.55 + 0.45 * sin(uT * 1.15 + in_b.x * 12.56);
    v_a = uAlpha * tw;
    gl_PointSize = in_b.y;
    gl_Position = vec4(x / uRes.x * 2.0 - 1.0, 1.0 - y / uRes.y * 2.0, 0.0, 1.0);
}
"""

_FS_PART = """
#version 330
in float v_a;
out vec4 f_color;
void main(){
    float d = length(gl_PointCoord - vec2(0.5));
    float a = smoothstep(0.5, 0.10, d) * v_a;
    f_color = vec4(vec3(0.62, 0.76, 1.0) * a, a);
}
"""

# --- کپی/اسکیل + بلور جداشدنی (برای ساخت زنجیره‌های Blur روی GPU در init)
_FS_COPY = """
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D uTex;
void main(){ f_color = texture(uTex, v_uv); }
"""

_FS_BLUR = """
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D uTex;
uniform vec2 uDir;       /* بردار تاپ در واحد تکسچر */
void main(){
    float w0 = 0.227027, w1 = 0.194594, w2 = 0.121621, w3 = 0.054054, w4 = 0.016216;
    vec4 c = texture(uTex, v_uv) * w0;
    c += texture(uTex, v_uv + uDir * 1.3846) * w1;
    c += texture(uTex, v_uv - uDir * 1.3846) * w1;
    c += texture(uTex, v_uv + uDir * 3.2307) * w2;
    c += texture(uTex, v_uv - uDir * 3.2307) * w2;
    c += texture(uTex, v_uv + uDir * 5.0769) * w3;
    c += texture(uTex, v_uv - uDir * 5.0769) * w3;
    c += texture(uTex, v_uv + uDir * 6.9230) * w4;
    c += texture(uTex, v_uv - uDir * 6.9230) * w4;
    f_color = c;
}
"""

# --- بلیت نهایی به پنجره
_FS_BLIT = """
#version 330
in vec2 v_uv;
out vec4 f_color;
uniform sampler2D uTex;
void main(){ f_color = vec4(texture(uTex, v_uv).rgb, 1.0); }
"""

# ================================================================
#  بخش ۱ — ساخت Asset با Pillow (فقط یک‌بار هنگام ساخت صحنه — هرگز در حلقه فریم)
# ================================================================
def _pick_font(candidates, size):
    for path in list(candidates) + _LINUX_FONTS_BOLD:
        try:
            return ImageFont.truetype(path, int(size))
        except Exception:
            continue
    for path in _LINUX_FONTS_REG:
        try:
            return ImageFont.truetype(path, int(size))
        except Exception:
            continue
    return ImageFont.load_default()

def _tracked_width(draw, text, font, tracking):
    if not text:
        return 0.0
    ws = [draw.textlength(ch, font=font) for ch in text]
    return sum(ws) + tracking * (len(text) - 1)

def make_title_sprite(text, candidates):
    """عنوان HEATMAP — همان منطق fit_font_tracked (سقف 88px / عرض 620 / track 0.16)
       سایه همگام داخل تکسچر پخته می‌شود."""
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    size, font, track = 88, None, 2
    while size > 12:
        font = _pick_font(candidates, size)
        track = max(2, int(round(size * 0.16)))
        try:
            if _tracked_width(tmp, text, font, track) <= 620:
                break
        except Exception:
            break
        size -= 2
    ws = [tmp.textlength(ch, font=font) for ch in text]
    tw = sum(ws) + track * (len(text) - 1)
    pad = 10
    W = int(tw + pad * 2 + 4)
    H = int(size * 1.45 + pad * 2)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cy = H / 2 - pad + 2
    x = pad
    for ch, w in zip(text, ws):     # سایه (2,3) — عین رندر ثابت
        d.text((x + 2, cy + 3), ch, font=font, fill=(0, 10, 30, 150), anchor="lm")
        x += w + track
    x = pad
    for ch, w in zip(text, ws):
        d.text((x, cy), ch, font=font, fill=TXT_WHITE, anchor="lm")
        x += w + track
    return img

def make_name_sprite(text, candidates):
    """اسم بازیکن — fit سقف 48px / عرض 900 (عین رندر ثابت). عرض متن برمی‌گردد."""
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    size, font = 48, None
    while size > 12:
        font = _pick_font(candidates, size)
        try:
            if tmp.textlength(text, font=font) <= 900:
                break
        except Exception:
            break
        size -= 2
    try:
        tw = tmp.textlength(text, font=font)
    except Exception:
        tw = size * len(text) * 0.6
    pad = 12
    W = int(tw + pad * 2)
    H = int(size * 1.5 + pad * 2)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((pad, H / 2 - pad), text, font=font, fill=TXT_WHITE, anchor="lm")
    return img, tw

def make_meta_sprite(header, candidates):
    """[PT v2.3.0] چیپ «شماره پیراهن + سن» کارت بازیکن — داده از
    teams_players_PES2021.txt (Slot پوینتر → شماره/سن). خروجی: (تصویر، عرض)
    یا (None, 0) وقتی داده‌ای نیست یا نمای بازیکن نیست.
    شیشه‌ای ملایم هم‌سبک پنل کارت؛ متن 30px سفید با برچسب خاکستری."""
    if header.get("kind", "all") != "player":
        return None, 0
    shirt = header.get("shirt")
    age = header.get("age")
    if shirt is None and age is None:
        return None, 0
    parts = []
    if shirt is not None:
        parts.append(("SHIRT", str(int(shirt))))
    if age is not None:
        parts.append(("AGE", str(int(age))))
    tmp = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    f_label = _pick_font(candidates, 20)
    f_value = _pick_font(candidates, 34)
    pad_x, gap = 22, 30
    H = 56
    widths = []
    for lbl, val in parts:
        try:
            wl = tmp.textlength(lbl, font=f_label)
            wv = tmp.textlength(val, font=f_value)
        except Exception:
            wl, wv = 60, 60
        widths.append((lbl, val, wl, wv))
    W = int(pad_x * 2 + sum(wl + 8 + wv for _, _, wl, wv in widths)
            + gap * (len(widths) - 1))
    img = Image.new("RGBA", (max(1, W), H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, H - 1], radius=12, fill=(13, 42, 92, 110),
                        outline=(86, 132, 198, 120), width=2)
    x = float(pad_x)
    for i, (lbl, val, wl, wv) in enumerate(widths):
        d.text((x, H / 2 - 11), lbl, font=f_label, fill=(148, 178, 214, 255),
               anchor="lm")
        d.text((x + wl + 8, H / 2 + 1), val, font=f_value, fill=TXT_WHITE,
               anchor="lm")
        x += wl + 8 + wv
        if i < len(widths) - 1:
            d.line([(x + gap / 2 - 1, 14), (x + gap / 2 - 1, H - 14)],
                   fill=(90, 128, 180, 90), width=2)
            x += gap
    return img, W

def make_logo_image(logo_path, box, fallback_key=None):
    """عین منطق _paste_logo — برش bbox + مقیاس؛ خروجی اسپرایت مستقل"""
    x0, y0, max_w, max_h = box
    out = Image.new("RGBA", (int(max_w), int(max_h)), (0, 0, 0, 0))
    if logo_path and os.path.isfile(logo_path):
        try:
            lg = Image.open(logo_path).convert("RGBA")
            bbox = lg.getbbox()
            if bbox:
                lg = lg.crop(bbox)
            s = min(max_w / lg.width, max_h / lg.height, 4.0)
            lg = lg.resize((max(1, int(lg.width * s)), max(1, int(lg.height * s))),
                           Image.Resampling.LANCZOS)
            out.alpha_composite(lg, (int((max_w - lg.width) / 2), int((max_h - lg.height) / 2)))
            return out
        except Exception:
            pass
    # سپر جایگزین — عین رنگ‌های _paste_logo
    dd = ImageDraw.Draw(out)
    cx, cy = max_w / 2.0, max_h / 2.0
    w, h = max_w * 0.88, max_h * 0.96
    shield = [(cx - w/2, cy - h/2), (cx + w/2, cy - h/2), (cx + w/2, cy + h*0.10),
              (cx + w*0.30, cy + h*0.36), (cx, cy + h/2), (cx - w*0.30, cy + h*0.36),
              (cx - w/2, cy + h*0.10)]
    dd.polygon(shield, fill=(238, 244, 250, 255), outline=(255, 255, 255, 255), width=3)
    HOME, AWAY = (7, 3), (7, 15)
    if fallback_key == HOME:
        cols = [(0, 77, 152, 255), (165, 0, 68, 255), (0, 77, 152, 255)]
    elif fallback_key == AWAY:
        cols = [(200, 16, 46, 255), (235, 240, 248, 255), (200, 16, 46, 255)]
    else:
        cols = [(24, 52, 110, 255), (222, 230, 242, 255), (24, 52, 110, 255)]
    for i, col in enumerate(cols):
        sx = cx - w * 0.27 + i * w * 0.19
        dd.polygon([(sx, cy - h*0.32), (sx + w*0.13, cy - h*0.32),
                    (sx + w*0.13, cy + h*0.14), (sx, cy + h*0.14)], fill=col)
    return out

def make_portrait_sprite(header, candidates):
    """دایره بازیکن/تیم — عین _circle_photo (هاله + محتوا + حلقه) به‌صورت اسپرایت مستقل"""
    kind = header.get("kind", "all")
    r = CIRCLE_R
    pad = 34
    S = 2 * (r + pad)
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    cx = cy = r + pad
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10], fill=(70, 130, 220, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(14))
    img.alpha_composite(glow)
    d = ImageDraw.Draw(img)
    photo_path = header.get("photo_path")
    if kind == "player" and photo_path and os.path.isfile(photo_path):
        try:
            im = Image.open(photo_path).convert("RGB")
            w, h = im.size
            s = min(w, h)
            im = im.crop(((w - s)//2, (h - s)//2, (w - s)//2 + s, (h - s)//2 + s))
            im = im.resize((2 * r, 2 * r), resample=Image.Resampling.LANCZOS)
            mask = Image.new("L", (2 * r, 2 * r), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 2 * r - 1, 2 * r - 1], fill=255)
            img.paste(im, (cx - r, cy - r), mask)
        except Exception:
            pass
    elif kind == "player":
        fill = (150, 12, 62, 255) if header.get("team_key") == (7, 3) else (16, 45, 96, 255)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill)
        name = str(header.get("name", ""))
        initials = "".join(w[0] for w in name.split()[:2]).upper() if name else "?"
        f_ini = _pick_font(candidates, int(r * 0.9))
        try:
            iw = d.textlength(initials, font=f_ini)
            d.text((cx - iw / 2, cy - r * 0.62), initials, font=f_ini, fill=(244, 248, 252, 255))
        except Exception:
            pass
    else:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 34, 78, 255))
        if kind == "team":
            lg = make_logo_image(header.get("logo_path"),
                                 (r*0.38, r*0.38, r*1.24, r*1.24), header.get("team_key"))
            img.alpha_composite(lg, (int(cx - r*0.62), int(cy - r*0.62)))
        else:
            lg1 = make_logo_image(header.get("logo_home"),
                                  (r*0.08, r*0.04, r*0.84, r*1.16), (7, 3))
            lg2 = make_logo_image(header.get("logo_away"),
                                  (r*1.08, r*0.04, r*0.84, r*1.16), (7, 15))
            img.alpha_composite(lg1, (int(cx - r*0.92), int(cy - r*0.58)))
            img.alpha_composite(lg2, (int(cx + r*0.08), int(cy - r*0.58)))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=RING_COL, width=7)
    return img

def make_trim_overlay():
    """نوار زیر لبه سکو + دورخط ذوزنقه — عین خطوط 1724-1737 رندر ثابت (یک‌بار پخت)"""
    W, H = RENDER_W, RENDER_H
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    strip_w = int(PNR[0] - PNL[0])
    strip_h = 13
    strip = np.zeros((strip_h, strip_w, 4), dtype=np.uint8)
    st = np.linspace(0.0, 1.0, strip_h).reshape(strip_h, 1)
    strip[:, :, :3] = (206, 238, 198)
    strip[:, :, 3] = (200 * (1 - st)).astype(np.uint8)
    img.alpha_composite(Image.fromarray(strip, mode="RGBA"), (int(PNL[0]), int(PNL[1])))
    d = ImageDraw.Draw(img)
    d.polygon([PFL, PFR, PNR, PNL], outline=(4, 30, 12, 90), width=2)
    return img

def make_ui_overlay():
    """روبان‌های گوشه + پنل کارت بازیکن — عین رندر ثابت (یک‌بار پخت)"""
    W, H = RENDER_W, RENDER_H
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.polygon([(22, 128), (22, 54), (148, 22), (226, 22)], fill=(120, 170, 235, 14))
    d.polygon([(W - 22, 128), (W - 22, 54), (W - 226, 22), (W - 148, 22)], fill=(120, 170, 235, 14))
    d.rounded_rectangle([55, 96, 1085, 278], radius=18, fill=(13, 42, 92, 55),
                        outline=(86, 132, 198, 70), width=2)
    return img

# ================================================================
#  بخش ۲ — آپلود تکسچر (قرارداد flip اینجاست — بندهای ۴ و ۷)
# ================================================================
def upload_sprite(ctx, img):
    """اسپرایت‌های PIL: یک flip مستند → v=1 = بالای تصویر (قرارداد بند ۷)"""
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    arr = np.flipud(arr)                       # تنها flip مسیر اسپرایت — مستند
    tex = ctx.texture((arr.shape[1], arr.shape[0]), 4, arr.tobytes())
    tex.filter = (0x2601, 0x2601)              # GL_LINEAR
    tex.repeat_x = tex.repeat_y = False
    return tex

def upload_heat(ctx, img):
    """تکسچر Heat: عیناً بدون flip → v=0 = سطر اول تصویر = z_min (قرارداد بند ۴)"""
    arr = np.asarray(img.convert("RGBA"), dtype=np.uint8)
    tex = ctx.texture((arr.shape[1], arr.shape[0]), 4, arr.tobytes())
    tex.filter = (0x2601, 0x2601)
    tex.repeat_x = tex.repeat_y = False
    return tex

def premultiply(img):
    """RGBA استریت → premultiplied (برای زنجیره Heat و ترکیب صحیح)"""
    arr = np.asarray(img.convert("RGBA"), dtype=np.float32) / 255.0
    arr[..., :3] *= arr[..., 3:4]
    return Image.fromarray((arr * 255.0 + 0.5).astype(np.uint8), mode="RGBA")

# ================================================================
#  بخش ۳ — موتور GPU
# ================================================================
class _BlurChain:
    """زنجیره بلور پیش‌ساخته روی GPU — در init ساخته می‌شود؛ در فریم فقط mix می‌شود.
       levels[0] = تکسچر اصلیِ دقیق، بقیه سطوح بلورشده در مقیاس نصفه.
       upload_fn: مسیر اسپرایت (flip بند ۷) یا مسیر world (بدون flip بند ۴)"""
    def __init__(self, ctx, prog_copy, prog_blur, quad, img, sigmas, upload_fn=upload_sprite):
        self.ctx = ctx
        self.levels = [upload_fn(ctx, img)]              # سطح ۰ = عین ورودی
        for sc, sig in sigmas:
            w = max(4, int(img.width * sc))
            h = max(4, int(img.height * sc))
            src = self.levels[0]
            small = ctx.texture((w, h), 4)
            small.filter = (0x2601, 0x2601)
            small.repeat_x = small.repeat_y = False
            fbo_s = ctx.framebuffer(small)
            fbo_s.use()
            ctx.viewport = (0, 0, w, h)
            ctx.clear(0.0, 0.0, 0.0, 0.0)
            prog_copy['uTex'].value = 0
            src.use(0)
            prog_copy['uRes'].value = (float(w), float(h))
            prog_copy['uRect'].value = (0.0, 0.0, float(w), float(h))
            prog_copy['uPivot'].value = (0.0, 0.0)
            prog_copy['uRot'].value = 0.0
            quad.render(moderngl.TRIANGLE_STRIP)
            tmp = ctx.texture((w, h), 4)
            tmp.filter = (0x2601, 0x2601)
            tmp.repeat_x = tmp.repeat_y = False
            fbo_a = ctx.framebuffer(small)
            fbo_b = ctx.framebuffer(tmp)
            for axis in (0, 1):                           # دو پاس H و V
                fbo = fbo_a if axis == 0 else fbo_b
                dst = small if axis == 0 else tmp
                srct = tmp if axis == 0 else small
                fbo.use()
                ctx.viewport = (0, 0, w, h)
                prog_blur['uTex'].value = 0
                srct.use(0)
                dx = sig / w if axis == 0 else 0.0
                dy = 0.0 if axis == 0 else sig / h
                prog_blur['uDir'].value = (dx, dy)
                prog_blur['uRes'].value = (float(w), float(h))
                prog_blur['uRect'].value = (0.0, 0.0, float(w), float(h))
                prog_blur['uPivot'].value = (0.0, 0.0)
                prog_blur['uRot'].value = 0.0
                quad.render(moderngl.TRIANGLE_STRIP)
            fbo_b.release()
            fbo_a.release()
            fbo_s.release()
            self.levels.append(small)
            tmp.release()

    def mix_textures(self, blur01):
        """(texA, texB, mix) برای مقدار بلور 0..1"""
        n = len(self.levels)
        L = clamp01(blur01) * (n - 1)
        i = min(int(L), n - 2)
        f = L - i
        return self.levels[i], self.levels[i + 1], f


def _blend_src_over(ctx):
    ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA   # premultiplied

def _blend_add(ctx):
    ctx.blend_func = moderngl.ONE, moderngl.ONE                    # افزودنی (ذرات/گلو)


class Engine:
    """صحنه برودکاست — تمام رندر روی GPU؛ CPU فقط تایم‌لاین و uniform"""

    def __init__(self, ctx, assets, W=RENDER_W, H=RENDER_H, clear_alpha=1.0):
        import moderngl as _mg
        global moderngl
        moderngl = _mg
        self.ctx = ctx
        self.W, self.H = W, H
        # clear_alpha=0.0 → مخصوص Overlay (پنجره شفاف): خارج از قاب گرد شفاف می‌ماند
        self._clear_a = float(clear_alpha)
        header = assets["header"]
        fonts_title = assets.get("fonts", {}).get("title", [])
        fonts_bold = assets.get("fonts", {}).get("bold", [])

        # ---------- برنامه‌ها
        p = ctx.program
        self.p_quad   = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_SPRITE)
        self.p_copy   = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_COPY)
        self.p_blur   = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_BLUR)
        self.p_pitch  = p(vertex_shader=_VS_PITCH, fragment_shader=_FS_PITCH)
        self.p_bar    = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_BAR)
        self.p_tpanel = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_TITLE_PANEL)
        self.p_bg     = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_BG)
        self.p_glass  = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_GLASS)
        self.p_part   = p(vertex_shader=_VS_PART, fragment_shader=_FS_PART)
        self.p_blit   = p(vertex_shader=_VS_QUAD, fragment_shader=_FS_BLIT)

        # ---------- کواد واحد (TL,TR,BL,BR — strip) با uv اسپرایت (v=1 بالا)
        q = np.array([0, 0, 0, 1,   1, 0, 1, 1,   0, 1, 0, 0,   1, 1, 1, 0], dtype='f4')
        self.vb_quad = ctx.buffer(q.tobytes())
        def vao_for(prog):
            return ctx.vertex_array(prog, [(self.vb_quad, '2f 2f', 'in_pos', 'in_uv')])
        self.v_quad = vao_for(self.p_quad)
        self.v_copy = vao_for(self.p_copy)
        self.v_blur = vao_for(self.p_blur)
        self.v_bar = vao_for(self.p_bar)
        self.v_tpanel = vao_for(self.p_tpanel)
        self.v_bg = vao_for(self.p_bg)
        self.v_glass = vao_for(self.p_glass)
        self.v_blit = vao_for(self.p_blit)

        # ---------- کواد زمین: فقط uv = (x_frac, z_frac) — پوزیشن از هاوموگرافی (بند ۶)
        qp = np.array([0, 0,   1, 0,   0, 1,   1, 1], dtype='f4')
        self.vb_pitch = ctx.buffer(qp.tobytes())
        self.v_pitch = ctx.vertex_array(self.p_pitch, [(self.vb_pitch, '2f', 'in_uv')])

        # ---------- هاوموگرافی پایه (عین منطق _find_coeffs Provider — بند ۶)
        self.H0 = solve_homography(
            [(0, 0), (1, 0), (1, 1), (0, 1)], [PFL, PFR, PNR, PNL])

        # ---------- نگاشت uv پلتفرم → uv موتور برای Heat (قرارداد بند ۵)
        #   پلیت چمن بازه سکو (±56.1/±35.9) دارد ولی Heat روی بازه موتور (±55/±37)
        #   ساخته می‌شود؛ این نگاشت خطی جای‌گذاری را عین نمای دوبعدی زنده می‌کند.
        tx0, tx1, tz0, tz1 = assets.get("tex_range", (-56.1, 56.1, -35.9, 35.9))
        self.heat_u = ((tx1 - tx0) / 110.0, (tx0 + 55.0) / 110.0)
        self.heat_v = ((tz1 - tz0) / 74.0, (tz0 + 37.0) / 74.0)

        # ---------- FBO خروجی
        self.tex_out = ctx.texture((W, H), 4)
        self.tex_out.filter = (0x2601, 0x2601)
        self.fbo = ctx.framebuffer(self.tex_out)

        # ---------- تکسچر زمین و Heat (عین Provider — بدون تغییر)
        #   مسیر world: آپلود بدون flip (قرارداد بند ۴/۵)
        plate_img = assets["pitch_plate"]
        self.chain_plate = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                      plate_img, [(0.5, 1.6), (0.5, 4.5)], upload_fn=upload_heat)
        heat_img = assets.get("heat_rgba")
        self.has_heat = heat_img is not None
        self.glow_tex = None
        self.chain_heat = None
        if self.has_heat:
            self.chain_heat = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                         premultiply(heat_img),
                                         [(0.5, 2.0), (0.5, 5.0), (0.5, 10.0)],
                                         upload_fn=upload_heat)
            self.glow_tex = self.chain_heat.levels[-1]

        # ---------- اسپرایت‌های هدر (یک‌بار پخت با Pillow)
        self.spr_title = upload_sprite(ctx, make_title_sprite("HEATMAP", fonts_title))
        name_img, name_w = make_name_sprite(header.get("name") or header.get("text") or "PLAYER",
                                            fonts_bold)
        self.spr_name = upload_sprite(ctx, name_img)
        self.name_w = name_w
        kind = header.get("kind", "all")
        self.kind = kind
        self.spr_portrait = upload_sprite(ctx, make_portrait_sprite(header, fonts_bold))
        if kind in ("player", "team"):
            self.spr_logo = upload_sprite(ctx, make_logo_image(header.get("logo_path"),
                                                               LOGO_BOX, header.get("team_key")))
        else:
            imgs = [make_logo_image(p, b, k) for p, b, k in
                    ((header.get("logo_home"), LOGO_BOX_ALL[0], (7, 3)),
                     (header.get("logo_away"), LOGO_BOX_ALL[1], (7, 15)))]
            merged = Image.new("RGBA", (176, 84), (0, 0, 0, 0))
            merged.alpha_composite(imgs[0], (0, 0))
            merged.alpha_composite(imgs[1], (88, 0))
            self.spr_logo = upload_sprite(ctx, merged)
        self.spr_trim = upload_sprite(ctx, make_trim_overlay())
        self.spr_ui = upload_sprite(ctx, make_ui_overlay())

        # [PT v2.3.0] چیپ SHIRT/AGE کارت بازیکن (فقط وقتی دادهٔ PT هست)
        _meta_img, _meta_w = make_meta_sprite(header, fonts_bold)
        self.meta_w = float(_meta_w)
        self.spr_meta = upload_sprite(ctx, _meta_img) if _meta_img is not None else None

        # زنجیره بلور اسپرایت‌ها (در init روی GPU)
        self.ch_title = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                   make_title_sprite("HEATMAP", fonts_title), [(1.0, 2.5), (1.0, 7.0)])
        self.ch_name = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                  name_img, [(1.0, 2.5), (1.0, 7.0)])
        self.ch_portrait = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                      make_portrait_sprite(header, fonts_bold),
                                      [(1.0, 3.0), (1.0, 8.0)])
        if kind in ("player", "team"):
            _logo_img = make_logo_image(header.get("logo_path"), LOGO_BOX, header.get("team_key"))
        else:
            _lg1 = make_logo_image(header.get("logo_home"), LOGO_BOX_ALL[0], (7, 3))
            _lg2 = make_logo_image(header.get("logo_away"), LOGO_BOX_ALL[1], (7, 15))
            _logo_img = Image.new("RGBA", (176, 84), (0, 0, 0, 0))
            _logo_img.alpha_composite(_lg1, (0, 0))
            _logo_img.alpha_composite(_lg2, (88, 0))
        self.ch_logo = _BlurChain(ctx, self.p_copy, self.p_blur, self.v_copy,
                                  _logo_img, [(1.0, 2.5), (1.0, 6.5)])

        # ---------- عرض هدف نوار اسم (عین فرمول رندر ثابت)
        max_bar_w = 1000 if kind in ("player", "team") else 1150
        self.bar_w = max(150.0, min(float(max_bar_w), (NAME_X - BAR_X0) + name_w + 55.0))

        # ---------- ذرات (۱۰۰ ذره — بند ۶ دستور)
        rng = np.random.default_rng(11)
        N = 100
        pa = np.stack([rng.uniform(0, W, N).astype('f4'),
                       rng.uniform(0, H, N).astype('f4'),
                       rng.uniform(0, 1, N).astype('f4')], axis=1)
        pb = np.stack([rng.uniform(0, 1, N).astype('f4'),
                       rng.uniform(2.0, 4.5, N).astype('f4')], axis=1)
        self.n_particles = N
        self.vb_part = ctx.buffer(np.concatenate([pa, pb], axis=1).tobytes())
        self.v_part = ctx.vertex_array(self.p_part, [(self.vb_part, '3f 2f', 'in_a', 'in_b')])

        # ---------- فاز جاری (برای سوییپ‌های زنده)
        self._t_last = 0.0

    # ------------------------------------------------------------ کمکی‌ها
    def _scaled_rect(self, rect, s, dy=0.0):
        """مقیاس حول مرکز + جابه‌جایی عمودی — برای ورود Stage/عنوان"""
        x, y, w, h = rect
        cx, cy = self.W / 2.0, self.H / 2.0
        nx = cx + (x - cx) * s
        ny = cy + (y - cy) * s + dy
        return (nx, ny, w * s, h * s)

    def _quad(self, prog, vao, rect, texA, texB=None, mixv=0.0, alpha=1.0,
              pivot=None, rot=0.0, sweep=(0.5, 0.25, 0.0)):
        prog['uRes'].value = (float(self.W), float(self.H))
        prog['uRect'].value = tuple(float(v) for v in rect)
        prog['uPivot'].value = pivot if pivot is not None else (rect[0] + rect[2] / 2.0, rect[1] + rect[3] / 2.0)
        prog['uRot'].value = float(rot)
        prog['uTexA'].value = 0
        prog['uTexB'].value = 1
        prog['uMix'].value = float(mixv)
        prog['uAlpha'].value = float(alpha)
        prog['uSweepX'].value = float(sweep[0])
        prog['uSweepW'].value = float(sweep[1])
        prog['uSweepAmt'].value = float(sweep[2])
        if texB is not None:
            texB.use(1)
        texA.use(0)
        vao.render(moderngl.TRIANGLE_STRIP)

    def _sprite(self, chain, rect, blur01, alpha, pivot=None, rot=0.0, sweep=(0.5, 0.25, 0.0)):
        ta, tb, mx = chain.mix_textures(blur01)
        self._quad(self.p_quad, self.v_quad, rect, ta, tb, mx, alpha, pivot, rot, sweep)

    # ------------------------------------------------------------ تایم‌لاین
    def _entrance_params(self, f):
        """کلیدفریم‌های ورود (فریم @60fps) — بند ۵ دستور:
           0→15 قاب | 15→30 عنوان | 25→50 بازیکن | 40→65 اسم | 50→70 لوگو | 60→110 هیت‌مپ"""
        p = {}
        p["bg_a"]        = out_cubic(seg(f, 0, 10))
        p["stage_s"]     = 0.94 + 0.06 * out_cubic(seg(f, 0, 25))
        p["stage_a"]     = out_cubic(seg(f, 2, 25))
        p["plate_blur"]  = 1.0 - out_cubic(seg(f, 4, 26))
        # نور لبه بالا — در ورود پررنگ، بعد هر ~8 ثانیه خیلی ظریف
        if f < 26:
            p["top_sweep"] = seg(f, 3, 24); p["top_amt"] = 0.85 * seg(f, 3, 6) * (1.0 - 0.4 * seg(f, 20, 26))
        else:
            c = ((f - 26) % 480) / 480.0
            p["top_sweep"] = c; p["top_amt"] = 0.16
        # سوییپ مورب شیشه — از فریم ۴۰ به بعد، هر ~۱۳ ثانیه
        p["spec_pos"] = ((f - 40) * 3.0) % (self.W + 700) - 350 if f > 40 else -1e5
        p["spec_amt"] = 0.07 if f > 40 else 0.0
        # عنوان
        p["title_a"]    = out_cubic(seg(f, 15, 32))
        p["title_s"]    = 0.92 + 0.08 * out_cubic(seg(f, 15, 32))
        p["title_dy"]   = -10.0 * (1.0 - out_cubic(seg(f, 15, 32)))
        p["title_blur"] = 1.0 - out_cubic(seg(f, 15, 34))
        if f < 52:
            sx = seg(f, 34, 50); p["title_sweep"] = (sx * 1.4 - 0.2, 0.18, 0.45 * math.sin(math.pi * clamp01(sx)))
        else:
            c = ((f - 52) % 540) / 540.0
            p["title_sweep"] = (c * 1.4 - 0.2, 0.18, 0.13 * math.sin(math.pi * clamp01(c)))
        # ورود عناصر
        p["ui_a"] = p["stage_a"]
        q = out_quint(seg(f, 25, 50))
        p["photo_a"] = q; p["photo_dy"] = 30.0 * (1.0 - q); p["photo_s"] = 1.08 - 0.08 * q
        p["photo_blur"] = 1.0 - out_quint(seg(f, 25, 52))
        p["bar_w01"]  = out_cubic(seg(f, 40, 62))
        p["bar_lx"]   = p["bar_w01"] * self.bar_w
        p["bar_lamt"] = 0.55 * (1.0 - seg(f, 60, 74)) * seg(f, 40, 46)
        q = out_quint(seg(f, 45, 68))
        p["name_dx"]   = -min(240.0, self.name_w * 0.9 + 24.0) * (1.0 - q)
        p["name_a"]    = out_quint(seg(f, 47, 66))
        p["name_blur"] = 1.0 - out_quint(seg(f, 47, 70))
        p["logo_a"]   = out_cubic(seg(f, 50, 68))
        p["logo_s"]   = 0.70 + 0.30 * out_back(seg(f, 50, 70))
        p["logo_rot"] = -3.0 * (1.0 - out_cubic(seg(f, 50, 70)))
        p["logo_blur"] = 1.0 - out_cubic(seg(f, 50, 72))
        # هیت‌مپ — آخر از همه (بند ۱۳)
        p["heat_a"]    = heat_staged(seg(f, 60, 110))
        p["heat_glow"] = out_cubic(seg(f, 64, 112))
        p["heat_scale"] = 1.03 - 0.03 * out_cubic(seg(f, 60, 112))
        p["heat_blur"] = 1.0 - out_cubic(seg(f, 60, 114))
        p["part_a"] = 0.32 * out_cubic(seg(f, 100, 130))
        return p

    def _exit_params(self, k):
        """خروج — تقریباً آینه ورود ولی با ترتیب/ایزینگ متفاوت (بند ۱۷):
           Heat اول → لوگو → اسم → بازیکن → عنوان → قاب → پس‌زمینه"""
        p = {}
        p["bg_a"]        = 1.0 - in_cubic(seg(k, 48, 60))
        p["stage_s"]     = 1.0 - 0.045 * in_cubic(seg(k, 40, 58))
        p["stage_a"]     = 1.0 - in_cubic(seg(k, 40, 58))
        p["plate_blur"]  = in_cubic(seg(k, 40, 58))
        p["top_sweep"] = 1.0 - in_cubic(seg(k, 40, 55)); p["top_amt"] = 0.35 * (1.0 - seg(k, 40, 55))
        p["spec_pos"] = ((k) * 4.0) % (self.W + 700) - 350
        p["spec_amt"] = 0.05 * (1.0 - seg(k, 36, 50))
        p["title_a"]    = 1.0 - in_cubic(seg(k, 30, 46))
        p["title_s"]    = 1.0 - 0.05 * in_cubic(seg(k, 30, 46))
        p["title_dy"]   = -8.0 * in_cubic(seg(k, 30, 46))
        p["title_blur"] = in_cubic(seg(k, 30, 46))
        p["title_sweep"] = (0.5, 0.2, 0.0)
        p["ui_a"] = 1.0 - in_cubic(seg(k, 34, 52))
        p["heat_a"]    = 1.0 - in_quart(seg(k, 0, 14))
        p["heat_glow"] = 1.0 - in_quart(seg(k, 0, 16))
        p["heat_scale"] = 1.0 + 0.012 * in_cubic(seg(k, 0, 16))
        p["heat_blur"] = in_cubic(seg(k, 0, 16))
        q = in_cubic(seg(k, 22, 42))
        p["photo_a"] = 1.0 - q; p["photo_dy"] = 26.0 * q; p["photo_s"] = 1.0 + 0.06 * q
        p["photo_blur"] = q
        p["bar_w01"]  = 1.0 - in_cubic(seg(k, 12, 30))
        p["bar_lx"]   = 0.0; p["bar_lamt"] = 0.0
        q = in_cubic(seg(k, 12, 28))
        p["name_dx"]   = -min(240.0, self.name_w * 0.9 + 24.0) * q
        p["name_a"]    = 1.0 - q
        p["name_blur"] = q
        q = in_cubic(seg(k, 6, 20))
        p["logo_a"]   = 1.0 - q
        p["logo_s"]   = 1.0 - 0.28 * q
        p["logo_rot"] = 3.0 * q
        p["logo_blur"] = q
        p["part_a"] = 0.32 * (1.0 - in_cubic(seg(k, 26, 42)))
        return p

    # ------------------------------------------------------------ رسم صحنه
    def _draw(self, p, t_sec):
        ctx = self.ctx
        self.fbo.use()
        ctx.viewport = (0, 0, self.W, self.H)
        ctx.clear(0.0, 0.0, 0.0, self._clear_a)
        ctx.enable(moderngl.BLEND)
        _blend_src_over(ctx)
        W, H = self.W, self.H

        # 1) پس‌زمینه زنده
        g = self.p_bg
        g['uRes'].value = (float(W), float(H))
        g['uT'].value = float(t_sec)
        g['uAlpha'].value = float(p["bg_a"])
        g['uRect'].value = (0.0, 0.0, float(W), float(H))
        g['uPivot'].value = (0.0, 0.0)
        g['uRot'].value = 0.0
        self.v_bg.render(moderngl.TRIANGLE_STRIP)

        # 2) شیشه — پرکردن داخلی
        fr = self._scaled_rect(FRAME_RECT, p["stage_s"])
        gl = self.p_glass
        gl['uRes'].value = (float(W), float(H))
        gl['uRect'].value = fr
        gl['uPivot'].value = (0.0, 0.0)
        gl['uRot'].value = 0.0
        gl['uFrame'].value = fr
        gl['uRadius'].value = FRAME_R * p["stage_s"]
        gl['uMode'].value = 0.0
        gl['uAlpha'].value = float(p["stage_a"])
        gl['uTopSweep'].value = 0.0; gl['uTopAmt'].value = 0.0
        gl['uSpecPos'].value = 0.0;  gl['uSpecAmt'].value = 0.0
        self.v_glass.render(moderngl.TRIANGLE_STRIP)

        # 3) زمین + Heat (پرسپکتیو GPU — هاوموگرافی با مقیاس Stage)
        S = stage_scale_matrix(p["stage_s"], W / 2.0, H / 2.0)
        Hs = S @ self.H0
        pp = self.p_pitch
        pp['uRes'].value = (float(W), float(H))
        pp['uH'].write(Hs.T.astype('f4').tobytes())   # mat3 ستون-اصلی
        pa_, pb_, pm_ = self.chain_plate.mix_textures(p["plate_blur"])
        pp['uPlateA'].value = 0; pp['uPlateB'].value = 1
        pa_.use(0); pb_.use(1)
        pp['uPlateMix'].value = float(pm_)
        pp['uHeatU'].value = self.heat_u
        pp['uHeatV'].value = self.heat_v
        pp['uAlpha'].value = float(p["stage_a"])
        pp['uHasHeat'].value = 1.0 if self.has_heat else 0.0
        if self.has_heat:
            ha_, hb_, hm_ = self.chain_heat.mix_textures(p["heat_blur"])
            pp['uHeatA'].value = 2; pp['uHeatB'].value = 3
            ha_.use(2); hb_.use(3)
            pp['uHeatMix'].value = float(hm_)
            pp['uHeatScale'].value = float(p["heat_scale"])
            pp['uHeatA_amt'].value = float(p["heat_a"])
            pp['uGlowAmt'].value = 0.55 * float(p["heat_glow"])
            self.glow_tex.use(4)
            pp['uGlow'].value = 4
        self.v_pitch.render(moderngl.TRIANGLE_STRIP)

        # 4) تریم سکو (نوار + دورخط)
        self._sprite(_StaticChain(self.spr_trim),
                     self._scaled_rect((0.0, 0.0, float(W), float(H)), p["stage_s"]),
                     0.0, p["stage_a"])

        # 5) شیشه — خط لبه + نور بالا + سوییپ مورب
        gl['uMode'].value = 1.0
        gl['uTopSweep'].value = float(p["top_sweep"])
        gl['uTopAmt'].value = float(p["top_amt"])
        gl['uSpecPos'].value = float(p["spec_pos"])
        gl['uSpecAmt'].value = float(p["spec_amt"])
        self.v_glass.render(moderngl.TRIANGLE_STRIP)

        # 6) پنل عنوان
        tp = TITLE_PANEL
        tcx, tcy = tp[0] + tp[2] / 2.0, tp[1] + tp[3] / 2.0
        trect = (tcx - tp[2] * p["title_s"] / 2.0, tcy - tp[3] * p["title_s"] / 2.0 + p["title_dy"],
                 tp[2] * p["title_s"], tp[3] * p["title_s"])
        pt = self.p_tpanel
        pt['uRes'].value = (float(W), float(H))
        pt['uRect'].value = trect
        pt['uPivot'].value = (0.0, 0.0)
        pt['uRot'].value = 0.0
        pt['uAlpha'].value = float(p["title_a"])
        pt['uGlobalX0'].value = float(trect[0])
        self.v_tpanel.render(moderngl.TRIANGLE_STRIP)

        # 7) اورلی استاتیک (روبان‌ها + پنل کارت)
        self._sprite(_StaticChain(self.spr_ui),
                     self._scaled_rect((0.0, 0.0, float(W), float(H)), p["stage_s"]),
                     0.0, p["ui_a"])

        # 8) نوار اسم (رشد عرض + نور لبه)
        pb = self.p_bar
        bar_rect = self._scaled_rect((BAR_X0, BAR_Y0, self.bar_w + 120.0, 63.0), p["stage_s"])
        pb['uRes'].value = (float(W), float(H))
        pb['uRect'].value = bar_rect
        pb['uPivot'].value = (0.0, 0.0)
        pb['uRot'].value = 0.0
        pb['uBarW'].value = float(p["bar_w01"] * self.bar_w)
        pb['uSlant'].value = float(BAR_SLANT)
        pb['uAlpha'].value = float(p["stage_a"])
        pb['uLightX'].value = float(p["bar_lx"])
        pb['uLightAmt'].value = float(p["bar_lamt"])
        pb['uColL'].value = tuple(c / 255.0 for c in BAR_COL_L)
        pb['uColR'].value = tuple(c / 255.0 for c in BAR_COL_R)
        self.v_bar.render(moderngl.TRIANGLE_STRIP)

        # 9) اسم — از پشت بازیکن بیرون می‌آید (زیر دایره بازیکن رسم می‌شود — بند ۱۰)
        nimg_h = self.ch_name.levels[0].height
        nrect = ((NAME_X - 12.0 + p["name_dx"]) * p["stage_s"] + (W / 2.0) * (1 - p["stage_s"]),
                 (NAME_Y - (nimg_h / 2.0 - 12.0)) * p["stage_s"] + (H / 2.0) * (1 - p["stage_s"]),
                 self.ch_name.levels[0].width * p["stage_s"], nimg_h * p["stage_s"])
        self._sprite(self.ch_name, nrect, p["name_blur"], p["name_a"])

        # 10) دایره بازیکن/تیم — روی اسم تا ماسک واقعی عمل کند
        pr = CIRCLE_R + 34
        prect0 = (CIRCLE_C[0] - pr, CIRCLE_C[1] - pr, 2 * pr, 2 * pr)
        pcs = (prect0[0] + prect0[2] / 2.0, prect0[1] + prect0[3] / 2.0)
        pw, phh = prect0[2] * p["photo_s"], prect0[3] * p["photo_s"]
        prect = (pcs[0] - pw / 2.0, pcs[1] - phh / 2.0 + p["photo_dy"], pw, phh)
        prect = self._stage_around(prect, p["stage_s"])
        self._sprite(self.ch_portrait, prect, p["photo_blur"], p["photo_a"])

        # 11) لوگوی باشگاه (پاپ ظریف — بند ۱۲)
        lrect = self._stage_around((LOGO_BOX[0], LOGO_BOX[1], LOGO_BOX[2] + 8, LOGO_BOX[3] + 8),
                                   p["stage_s"])
        lpiv = (lrect[0] + lrect[2] / 2.0, lrect[1] + lrect[3] / 2.0)
        ls = p["logo_s"]
        lrect2 = (lpiv[0] - lrect[2] * ls / 2.0, lpiv[1] - lrect[3] * ls / 2.0,
                  lrect[2] * ls, lrect[3] * ls)
        if self.kind == "all":
            lrect2 = (lrect2[0] - 4.0 * ls, lrect2[1] - 4.0 * ls, lrect2[2], lrect2[3])
        self._sprite(self.ch_logo, lrect2, p["logo_blur"], p["logo_a"], pivot=lpiv, rot=math.radians(p["logo_rot"]))

        # 11.5) [PT v2.3.0] چیپ SHIRT/AGE — سمت راست لوگو، زیر نوار اسم؛
        #       ورود/خروج هم‌فاز لوگو (همان آلفا و اسکیل stage)
        if self.spr_meta is not None:
            mrect = self._stage_around((META_X0, META_Y0, self.meta_w, META_H),
                                       p["stage_s"])
            self._sprite(_StaticChain(self.spr_meta), mrect, 0.0, p["logo_a"])

        # 12) عنوان HEATMAP (بند ۸) + سوییپ ظریف نهایی
        tim = self.ch_title.levels[0]
        t_text_y = tim.height / 2.0 - 10.0 + 2.0
        t_cx, t_cy = W / 2.0, 62.0
        tw, th = tim.width * p["title_s"], tim.height * p["title_s"]
        trect2 = (t_cx - tw / 2.0, t_cy - t_text_y * p["title_s"] + p["title_dy"], tw, th)
        self._sprite(self.ch_title, trect2, p["title_blur"], p["title_a"],
                     sweep=p["title_sweep"])

        # 13) ذرات محیطی (افزودنی — GPU instanced points)
        if p["part_a"] > 0.003:
            _blend_add(ctx)
            gp = self.p_part
            gp['uRes'].value = (float(W), float(H))
            gp['uT'].value = float(t_sec)
            gp['uAlpha'].value = float(p["part_a"])
            self.v_part.render(moderngl.POINTS)
            _blend_src_over(ctx)

    def _stage_around(self, rect, s):
        """مقیاس یک rect حول مرکز بوم (هم‌تراز با Stage)"""
        cx, cy = self.W / 2.0, self.H / 2.0
        x, y, w, h = rect
        nx, ny = cx + (x - cx) * s, cy + (y - cy) * s
        return (nx, ny, w * s, h * s)

    # ------------------------------------------------------------ خروجی فریم
    def render_entrance(self, f):
        self._draw(self._entrance_params(f), f / FPS)

    def render_exit(self, k):
        self._draw(self._exit_params(k), 1000.0 + k / FPS)

    def read_frame_rgb(self):
        data = self.fbo.read(components=4)
        arr = np.frombuffer(data, dtype=np.uint8).reshape(self.H, self.W, 4)
        arr = np.flipud(arr)                          # GL سطر ۰ پایین — برای PNG یک flip مستند
        return Image.fromarray(arr[:, :, :3], mode="RGB")

    def render_png(self, f):
        self.render_entrance(f)
        return self.read_frame_rgb()


class _StaticChain:
    """آداپتور اسپرایت استاتیک برای _sprite (بدون زنجیره بلور)"""
    def __init__(self, tex):
        self.tex = tex
    def mix_textures(self, blur01):
        return self.tex, self.tex, 0.0


# ================================================================
#  بخش ۴ — کانتکست، پنجره زنده، API عمومی
# ================================================================
def create_context_offscreen():
    """کانتکست آفلاین (تست/اسکرین‌شات) — نیازی به پنجره ندارد"""
    import moderngl
    return moderngl.create_context(standalone=True)


def create_context_windowed(w, h, title):
    """پنجره GLFW برای پخش زنده روی سیستم کاربر"""
    import glfw
    import moderngl
    if sys.platform.startswith("linux"):
        # برخی توزیع‌های لینوکس: پیش‌بارگذاری GL با RTLD_GLOBAL قبل از ساخت کانتکست
        for _lib in ("libGL.so.1", "libEGL.so.1"):
            try:
                ctypes.CDLL(_lib, mode=ctypes.RTLD_GLOBAL)
            except Exception:
                pass
    if not glfw.init():
        raise RuntimeError("glfw.init failed")
    glfw.window_hint(glfw.VISIBLE, True)
    glfw.window_hint(glfw.RESIZABLE, True)
    win = glfw.create_window(w, h, title, None, None)
    if not win:
        glfw.terminate()
        raise RuntimeError("glfw.create_window failed")
    glfw.make_context_current(win)
    glfw.swap_interval(1)
    ctx = moderngl.create_context()
    return win, ctx, glfw


class _WindowSession:
    """نشست زنده: ورود → حالت Live → خروج انیمیشنی → بستن
       bundle=(win, ctx, glfw) → میزبانی توسط OverlayEngine (بدون init/terminate جدید —
       قانون طلایی GLFW: در کل پروسه فقط یک init در boot موتور اورلی انجام می‌شود)."""

    def __init__(self, assets, events, scale=0.78, bundle=None):
        self.assets = assets
        self.events = events
        w = int(RENDER_W * scale)
        h = int(RENDER_H * scale)
        if bundle is None:
            self.win, self.ctx, self.glfw = create_context_windowed(
                w, h, "PES 2017  |  BROADCAST HEATMAP (GPU)")
            self.owns_glfw = True
        else:
            self.win, self.ctx, self.glfw = bundle
            self.owns_glfw = False
        self.engine = Engine(self.ctx, assets)
        # بلیت تمام‌صفحه (شیدر ساده — فقط uTex و یونیفرم‌های VS)
        q = np.array([0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0], dtype='f4')
        self.vb = self.ctx.buffer(q.tobytes())
        self.p_blit2 = self.ctx.program(vertex_shader=_VS_QUAD, fragment_shader=_FS_BLIT)
        self.vao = self.ctx.vertex_array(self.p_blit2, [(self.vb, '2f 2f', 'in_pos', 'in_uv')])

    def _blit(self):
        ww, wh = self.glfw.get_framebuffer_size(self.win)
        self.glfw.make_context_current(self.win)
        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, ww, wh)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.ctx.disable(moderngl.BLEND)
        self.p_blit2['uRes'].value = (float(ww), float(wh))
        self.p_blit2['uRect'].value = (0.0, 0.0, float(ww), float(wh))
        self.p_blit2['uPivot'].value = (0.0, 0.0)
        self.p_blit2['uRot'].value = 0.0
        self.p_blit2['uTex'].value = 0
        self.engine.tex_out.use(0)
        self.vao.render(moderngl.TRIANGLE_STRIP)

    def run(self):
        glfw = self.glfw
        t0 = time.perf_counter()
        phase = "entrance"
        t_exit0 = None
        saved_hint = ""
        while not glfw.window_should_close(self.win):
            now = time.perf_counter()
            ev = self.events
            if ev["replay"].is_set():
                ev["replay"].clear()
                t0 = now
                phase = "entrance"
                t_exit0 = None
            if ev["close"].is_set():
                ev["close"].clear()
                if phase != "exit":
                    phase = "exit"
                    t_exit0 = now
            if glfw.get_key(self.win, glfw.KEY_ESCAPE) == glfw.PRESS and phase != "exit":
                phase = "exit"
                t_exit0 = now
            if glfw.get_key(self.win, glfw.KEY_R) == glfw.PRESS:
                t0 = now
                phase = "entrance"
                t_exit0 = None
            if glfw.get_key(self.win, glfw.KEY_S) == glfw.PRESS:
                f = (now - t0) * FPS
                img = self.engine.render_png(min(f, 1e9))
                _save_render(img, "live")

            f = (now - t0) * FPS
            if phase == "entrance":
                self.engine.render_entrance(f)          # بعد از ۱۳۰ به Live می‌رسد
            else:
                k = (now - t_exit0) * FPS
                if k >= 62:
                    break
                self.engine.render_exit(k)
            self._blit()
            glfw.swap_buffers(self.win)
            glfw.poll_events()
        glfw.destroy_window(self.win)
        if self.owns_glfw:          # فقط اگر همین نشست مالک کتابخانه بود (مسیر قدیمی)
            glfw.terminate()


def _save_render(img, tag):
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders")
    os.makedirs(out_dir, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(out_dir, f"BROADCAST_{tag}_{ts}.png")
    img.save(path, "PNG")
    return path


# ------------------------------------------------------------ API عمومی
_lock = threading.Lock()
_thread_box = {"th": None, "events": None}

def launch(assets, interactive=True, scale=0.78):
    """فراخوانی از دکمه رندر برنامه اصلی.
       خروجی: دیکشنری رویدادها {ready, failed, replay, close} یا None.
       ready بعد از ساخته‌شدن موفق پنجره/موتور ست می‌شود؛ failed در هر خطای GPU/پنجره.
       اگر پنجره قبلاً باز باشد → Replay در همان پنجره.
       اگر OverlayEngine مقیم زنده باشد → پنجره تعاملی روی ترد همان موتور میزبانی
       می‌شود (بدون glfw.init/terminate جدید — ریشه‌ی باگ Class already exists)."""
    _eng = globals().get("_OVERLAY_ENGINE")
    if interactive and _eng is not None and _eng.is_alive():
        try:
            return _eng.open_manual(assets, scale=scale)
        except Exception:
            pass
    with _lock:
        th = _thread_box["th"]
        if interactive and th is not None and th.is_alive() and _thread_box["events"]:
            _thread_box["events"]["replay"].set()
            return _thread_box["events"]
        events = {"replay": threading.Event(), "close": threading.Event(),
                  "ready": threading.Event(), "failed": threading.Event()}

        def _worker():
            try:
                sess = _WindowSession(assets, events, scale)
                events["ready"].set()
                sess.run()
            except Exception as ex:      # هر خطای GPU/پنجره → برنامه اصلی fallback می‌کند
                events["failed"].set()
                print("[BroadcastRenderer] window failed:", ex, file=sys.stderr)

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        _thread_box["th"] = t
        _thread_box["events"] = events
        return events


def request_close():
    with _lock:
        if _thread_box["events"]:
            _thread_box["events"]["close"].set()


def capture_frames(assets, entrance_frames, exit_frames=None):
    """اسکرین‌شات قطعی فریم‌ها (بدون پنجره) — برای بررسی کنار مرجع (بند ۲۱)"""
    ctx = create_context_offscreen()
    eng = Engine(ctx, assets)
    out = {}
    for f in entrance_frames:
        out[("in", int(f))] = eng.render_png(float(f))
    if exit_frames:
        for k in exit_frames:
            eng.render_exit(float(k))
            out[("out", int(k))] = eng.read_frame_rgb()
    ctx.release()
    return out


# ================================================================
#  بخش ۵ — Second Broadcast Layer: OverlayEngine مقیم
# ================================================================
#  پنجره‌ی برودکاست خودکار روی تصویر بازی — عین معماری اثبات‌شده:
#    • glfw.init فقط «یک‌بار» در boot همین موتور در کل پروسه صدا زده می‌شود.
#      هیچ مسیری در میانه‌ی بازی init/terminate نمی‌زند → باگ
#      «Win32: Failed to register helper window class» ریشه‌کن می‌شود.
#    • پنجره از ابتدا مخفی ساخته می‌شود (شفاف + Topmost + Click-through +
#      NOACTIVATE) و فقط هنگام نمایش واقعی show/hide می‌شود؛ موقعیتش هرگز
#      عوض نمی‌شود — انیمیشن فقط با uniform روی GPU حرکت می‌کند.
#    • Prepare = آپلود تکسچر/ساخت صحنه چند ثانیه «قبل» از لحظه نمایش؛
#      Show = فقط یک queue.put (زیر 0.1ms) → سپس تایم‌لاین ورود روی GPU.
#
#  State:  HIDDEN → PREPARING → READY → SHOWING → VISIBLE → EXITING → HIDDEN
#          (خطای رندر → FAILED → با prepare دوباره → READY → SHOWING)
# BUSY = پنجره تعاملی کلید R روی همین ترد در حال اجراست.

import queue as _queue

_FS_MASK = """
#version 330
in vec2 v_uv;
in vec2 v_px;
out vec4 f_color;
uniform sampler2D uTex;
uniform vec4 uRect;       /* هندسه کواد — کل بوم fit-شده روی صفحه */
uniform vec4 uMaskRect;   /* قاب گرد در مختصات صفحه — بیرونش شفاف می‌شود */
uniform float uRadius;
float sdRoundBox(vec2 p, vec2 b, float r){
    vec2 q = abs(p) - b + r;
    return min(max(q.x, q.y), 0.0) + length(max(q, 0.0)) - r;
}
void main(){
    vec4 c = texture(uTex, v_uv);
    vec2 ctr = uMaskRect.xy + uMaskRect.zw * 0.5;
    float d = sdRoundBox(v_px - ctr, uMaskRect.zw * 0.5, uRadius);
    float cov = 1.0 - clamp(d, 0.0, 1.0);          /* AA یک‌پیکسلی لبه */
    f_color = vec4(c.rgb * cov, c.a * cov);        /* خروجی premultiplied */
}
"""


def _release_gpu_members(obj, skip=("ctx",)):
    """آزادسازی منظم اشیاء GPU یک شیء (برای تعویض صحنه بدون نشت)"""
    if obj is None:
        return
    for _name, _val in list(vars(obj).items()):
        if _name in skip or _val is None:
            continue
        _rel = getattr(_val, "release", None)
        if callable(_rel):
            try:
                _rel()
            except Exception:
                pass
        elif isinstance(_val, (list, tuple)):
            for _v in _val:
                _r2 = getattr(_v, "release", None)
                if callable(_r2):
                    try:
                        _r2()
                    except Exception:
                        pass


class OverlayEngine:
    """موتور اورلی مقیم — ترد رندر مالک انحصاری GLFW/Context در کل پروسه.

       API (همه فقط پیام — غیرمسدود و امن از هر ترد):
         prepare_player_overlay(assets)  → آپلود صحنه (قبل از لحظه نمایش)
         show_player_overlay()           → تایم‌لاین ورود روی GPU
         hide_player_overlay()           → تایم‌لاین خروج لایه‌به‌لایه
         hide_now()                      → شفاف/مخفی فوری
         open_manual(assets, scale)      → پنجره تعاملی R روی همین ترد
         shutdown()                      → فقط هنگام بستن برنامه
    """

    ST_HIDDEN = "HIDDEN"
    ST_PREPARING = "PREPARING"
    ST_READY = "READY"
    ST_SHOWING = "SHOWING"
    ST_VISIBLE = "VISIBLE"
    ST_EXITING = "EXITING"
    ST_FAILED = "FAILED"
    ST_BUSY = "BUSY"
    ST_DEAD = "DEAD"

    _instance = None
    _inst_lock = threading.Lock()

    @classmethod
    def start(cls, width_frac=0.33, height_frac=0.32):
        """فقط یک‌بار در شروع برنامه — non-blocking (ترد جدا + handshake داخلی)."""
        with cls._inst_lock:
            if cls._instance is not None:
                return cls._instance
            eng = cls(width_frac, height_frac)
            globals()["_OVERLAY_ENGINE"] = eng
            cls._instance = eng
            return eng

    def __init__(self, width_frac, height_frac):
        self._wf = float(width_frac)
        self._hf = float(height_frac)
        self._q = _queue.Queue()
        self._lock = threading.Lock()
        self._state = self.ST_DEAD
        self._fail = None              # خطای boot (دائمی)
        self._last_error = None        # خطای رندر/prepare (با prepare بعدی پاک می‌شود)
        self._ready_ev = threading.Event()
        self._init_info = {}
        self._gen = 0
        self._stop = False
        # فقط در ترد رندر لمس می‌شوند:
        self._glfw = None
        self._mg = None
        self._ctx = None
        self._win = None
        self._geo = None               # (ow, oh, ox, oy)
        self._eng = None               # Engine صحنه فعلی
        self._phase = None             # None | "in" | "live" | "out"
        self._t0 = 0.0
        self._p_mask = self._vb_mask = self._vao_mask = None
        self._thread = threading.Thread(target=self._run,
                                        name="auto-overlay-engine", daemon=True)
        self._thread.start()

    # ---------------- API امن از هر ترد ----------------
    def is_alive(self):
        return bool(self._thread.is_alive() and self._ready_ev.is_set()
                    and self._fail is None and not self._stop)

    def state(self):
        with self._lock:
            return self._state

    def fail_reason(self):
        with self._lock:
            return self._fail if self._fail is not None else self._last_error

    def init_info(self):
        with self._lock:
            return dict(self._init_info)

    def wait_init(self, timeout=6.0):
        self._ready_ev.wait(timeout)
        return self._fail is None

    def prepare_player_overlay(self, assets):
        self._gen += 1
        self._put(("prepare", assets, self._gen))

    def show_player_overlay(self):
        self._put(("show",))

    def hide_player_overlay(self):
        self._put(("hide",))

    def hide_now(self):
        self._put(("hide_now",))

    def open_manual(self, assets, scale=0.78):
        ev = {"replay": threading.Event(), "close": threading.Event(),
              "ready": threading.Event(), "failed": threading.Event()}
        self._put(("manual", assets, float(scale), ev))
        return ev

    def shutdown(self, timeout=2.0):
        """فقط هنگام بستن برنامه — تنها نقطه‌ی terminate در کل پروسه."""
        self._stop = True
        self._put(("stop",))
        try:
            self._thread.join(timeout=timeout)
        except Exception:
            pass

    # ---------------- داخلی ----------------
    def _put(self, cmd):
        try:
            self._q.put_nowait(cmd)
        except Exception:
            pass

    def _set_state(self, st):
        with self._lock:
            self._state = st

    def _log_block(self, title, lines):
        try:
            print("=" * 60, flush=True)
            print(title, flush=True)
            for ln in lines:
                print(ln, flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass

    def _apply_win32_styles(self, hwnd):
        """یک‌بار در boot — Topmost + Click-through + NOACTIVATE (عین الگوی اثبات‌شده).
           در طول انیمیشن «هیچ» فراخوانی ویندوزی انجام نمی‌شود."""
        if sys.platform != "win32" or not hwnd:
            return "n/a (non-Windows)"
        try:
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            try:
                old = int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)) & 0xFFFFFFFF
            except Exception:
                old = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE)) & 0xFFFFFFFF
            new = old | WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            try:
                user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new)
            except Exception:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
            try:
                user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)  # LWA_ALPHA
            except Exception:
                pass
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)  # TOPMOST یک‌بار
            return (f"0x{old:08X} → 0x{new:08X} "
                    "LAYERED|TRANSPARENT|NOACTIVATE|TOOLWINDOW | TOPMOST (once at boot)")
        except Exception as ex:
            return f"failed: {type(ex).__name__}: {ex}"

    def _compute_geometry(self):
        """اندازه/موقعیت پنجره — یک‌بار در boot: کسر واقعی از رزولوشن، پایین-چپ Working Area."""
        g = self._glfw
        wx, wy, ww, wh = 0, 0, 0, 0
        mon = None
        try:
            mon = g.get_primary_monitor()
        except Exception:
            pass
        if mon is not None:
            try:
                wa = g.get_monitor_workarea(mon)
                wx, wy, ww, wh = int(wa[0]), int(wa[1]), int(wa[2]), int(wa[3])
            except Exception:
                pass
            if ww <= 0 or wh <= 0:
                try:
                    vm = g.get_video_mode(mon)
                    wx, wy = 0, 0
                    ww, wh = int(vm.size.width), int(vm.size.height)
                except Exception:
                    pass
        if ww <= 0 or wh <= 0:
            wx, wy, ww, wh = 0, 0, 1920, 1080
        ow = max(320, int(round(ww * self._wf)))
        oh = max(200, int(round(wh * self._hf)))
        mx = max(8, int(round(ww * 0.015)))          # حاشیه چپ
        my = max(8, int(round(wh * 0.02)))           # حاشیه پایین (~2%)
        ox = wx + mx
        oy = wy + wh - oh - my
        return (ow, oh, ox, oy), (wx, wy, ww, wh)

    # ---------------- ترد رندر ----------------
    def _run(self):
        if sys.platform.startswith("linux"):
            # برخی توزیع‌های لینوکس: پیش‌بارگذاری GL با RTLD_GLOBAL قبل از ساخت کانتکست
            for _lib in ("libGL.so.1", "libEGL.so.1"):
                try:
                    ctypes.CDLL(_lib, mode=ctypes.RTLD_GLOBAL)
                except Exception:
                    pass
        try:
            import glfw as _glfw
            import moderngl as _mg
        except Exception as ex:
            self._fail = (f"package import failed: {type(ex).__name__}: {ex} "
                          "— اجرا کنید: pip install moderngl glfw")
            self._ready_ev.set()
            print(f"[AUTO_HEATMAP] ENGINE INIT FAILED — {self._fail}", flush=True)
            return
        try:
            if not _glfw.init():                      # تنها init کل پروسه
                self._fail = "glfw.init() failed"
                self._ready_ev.set()
                print("[AUTO_HEATMAP] ENGINE INIT FAILED — glfw.init() failed", flush=True)
                return
            self._glfw = _glfw
            self._mg = _mg
            (ow, oh, ox, oy), wa = self._compute_geometry()
            self._geo = (ow, oh, ox, oy)
            g = _glfw
            g.window_hint(g.VISIBLE, False)           # مخفی — فقط هنگام نمایش واقعی show
            g.window_hint(g.DECORATED, False)
            g.window_hint(g.RESIZABLE, False)
            g.window_hint(g.FOCUS_ON_SHOW, False)     # هیچ‌وقت فوکوس نمی‌گیرد
            g.window_hint(g.FLOATING, True)
            g.window_hint(g.TRANSPARENT_FRAMEBUFFER, True)
            g.window_hint(g.DOUBLEBUFFER, True)
            g.window_hint(g.SAMPLES, 4)
            win = g.create_window(ow, oh, "pes-heatmap-auto-overlay", None, None)
            if not win:
                g.window_hint(g.SAMPLES, 0)
                win = g.create_window(ow, oh, "pes-heatmap-auto-overlay", None, None)
            if not win:
                self._fail = "glfw.create_window failed — پنجره شفاف ساخته نشد (DWM/driver?)"
                self._ready_ev.set()
                g.terminate()
                print(f"[AUTO_HEATMAP] ENGINE INIT FAILED — {self._fail}", flush=True)
                return
            self._win = win
            g.set_window_pos(win, ox, oy)             # تنها بار — پنجره هرگز جابه‌جا نمی‌شود
            g.make_context_current(win)
            g.swap_interval(1)                        # 60FPS VSync — بدون Busy Loop
            ctx = _mg.create_context()
            self._ctx = ctx
            try:
                ctx.disable(_mg.DEPTH_TEST)
            except Exception:
                pass
            ctx.enable(_mg.BLEND)
            ctx.blend_func = (_mg.ONE, _mg.ONE_MINUS_SRC_ALPHA)   # premultiplied
            # فریم کاملاً شفاف زیر پنجره — بدون هیچ فلشی
            ctx.clear(0.0, 0.0, 0.0, 0.0)
            g.swap_buffers(win)
            try:
                styles = self._apply_win32_styles(g.get_win32_window(win))
            except Exception as ex:
                styles = f"failed: {ex}"
            transp = False
            try:
                transp = bool(g.get_window_attrib(win, g.TRANSPARENT_FRAMEBUFFER))
            except Exception:
                pass
            gl_ver = gpu_name = "?"
            try:
                gl_ver = str(ctx.info.get("GL_VERSION", "?"))
                gpu_name = str(ctx.info.get("GL_RENDERER", "?"))
            except Exception:
                pass
            self._init_info = {"gl": gl_ver, "gpu": gpu_name,
                               "surface": (ow, oh, ox, oy), "workarea": wa,
                               "transparent": transp, "styles": styles}
            self._p_mask = ctx.program(vertex_shader=_VS_QUAD, fragment_shader=_FS_MASK)
            qm = np.array([0, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1, 0], dtype='f4')
            self._vb_mask = ctx.buffer(qm.tobytes())
            self._vao_mask = ctx.vertex_array(
                self._p_mask, [(self._vb_mask, '2f 2f', 'in_pos', 'in_uv')])
            self._state = self.ST_HIDDEN
            self._ready_ev.set()
            self._log_block("[AUTO_HEATMAP] ENGINE READY (Second Broadcast Layer)", [
                "Mode: GPU SHADER ANIMATION — the window NEVER moves",
                "Window: HIDDEN at boot — shown ONLY during the auto display",
                f"Context: {gl_ver} | {gpu_name}",
                f"Surface (fixed): {ow}x{oh} px @ ({ox},{oy}) | WorkArea {wa}",
                f"Transparent framebuffer: {'OK' if transp else 'NO(!)'} | "
                f"Click-through: ON | VSync: ON",
                f"Win32 styles: {styles}",
                "Commands: prepare / show / hide — Show = queue.put only",
            ])
        except Exception as ex:
            self._fail = f"{type(ex).__name__}: {ex}"
            self._ready_ev.set()
            print(f"[AUTO_HEATMAP] ENGINE INIT FAILED — {self._fail}", flush=True)
            return
        # ---------------- حلقه اصلی ----------------
        while not self._stop:
            try:
                self._loop_once()
            except Exception as ex:
                # خطای رندر → FAILED؛ ترد زنده می‌ماند (مسیر retry بند ۳۲)
                with self._lock:
                    self._last_error = f"render: {type(ex).__name__}: {ex}"
                self._phase = None
                self._set_state(self.ST_FAILED)
                try:
                    if self._win is not None:
                        self._render_transparent_frame()
                        self._glfw.hide_window(self._win)
                except Exception:
                    pass
                print(f"[AUTO_HEATMAP] ENGINE FAILED — {self._last_error}",
                      flush=True)
        # ---------------- خروج برنامه (تنها terminate) ----------------
        try:
            _release_gpu_members(self._eng)
            self._eng = None
        except Exception:
            pass
        try:
            if self._win is not None:
                self._glfw.destroy_window(self._win)
        except Exception:
            pass
        try:
            self._glfw.terminate()
        except Exception:
            pass

    def _loop_once(self):
        g = self._glfw
        if self._phase is None:
            # --- IDLE — انتظار پیام؛ بدون CPU Busy Loop
            try:
                cmd = self._q.get(timeout=0.25)
            except Exception:
                cmd = None
            g.poll_events()
            if cmd is not None:
                self._handle(cmd)
            return
        # --- فاز فعال (ورود/لایو/خروج) — هر فریم: رویدادها + پیام‌ها + رندر
        g.poll_events()
        if not self._drain() or self._stop:
            return
        if self._phase is None:
            return
        now = time.perf_counter()
        eng = self._eng
        if eng is None:
            self._phase = None
            self._set_state(self.ST_HIDDEN)
            return
        if self._phase == "in":
            f = (now - self._t0) * FPS
            eng.render_entrance(f)
            self._overlay_blit()
            if f >= 130.0:
                self._phase = "live"
                self._set_state(self.ST_VISIBLE)
        elif self._phase == "live":
            f = (now - self._t0) * FPS
            self._render_live(f)
            self._overlay_blit()
        elif self._phase == "out":
            k = (now - self._t0) * FPS
            eng.render_exit(k)
            self._overlay_blit()
            if k >= 62.0:
                self._finish_hide()

    def _drain(self):
        """پردازش همه پیام‌های صفی till اولین deferral — False یعنی پیام مؤخر شد"""
        while True:
            try:
                cmd = self._q.get_nowait()
            except Exception:
                return True
            if self._handle(cmd):
                return False if self._stop else True
            if self._stop:
                return False

    def _handle(self, cmd):
        """True = توقف drain (پیام مؤخر شد یا stop) | None/False = ادامه"""
        kind = cmd[0]
        if kind == "stop":
            self._stop = True
            return True
        if kind == "prepare":
            if self._phase is not None:
                self._q.put(cmd)
                return True                      # مؤخر — تا پایان نمایش فعلی
            _tag, assets, gen = cmd
            self._set_state(self.ST_PREPARING)
            try:
                _release_gpu_members(self._eng)
                self._eng = None
                self._eng = Engine(self._ctx, assets, clear_alpha=0.0)
                with self._lock:
                    self._last_error = None
                self._set_state(self.ST_READY)
                print(f"[AUTO_HEATMAP] ENGINE PREPARED (GPU scene #{gen} ready)",
                      flush=True)
            except Exception as ex:
                self._eng = None
                with self._lock:
                    self._last_error = f"prepare: {type(ex).__name__}: {ex}"
                self._set_state(self.ST_FAILED)
                print(f"[AUTO_HEATMAP] ENGINE PREPARE FAILED — {self._last_error}",
                      flush=True)
            return False
        if kind == "show":
            if self._phase is not None or self._eng is None:
                return False
            # اولین فریم کاملاً آماده زیر پنجره → show → بدون فلش
            self._t0 = time.perf_counter()
            try:
                self._eng.render_entrance(0.0)
                self._overlay_blit()
                self._glfw.show_window(self._win)
            except Exception:
                raise
            self._phase = "in"
            self._set_state(self.ST_SHOWING)
            return False
        if kind == "hide":
            if self._phase in ("in", "live"):
                self._start_exit()
            return False
        if kind == "hide_now":
            self._finish_hide()
            return False
        if kind == "manual":
            if self._phase is not None:
                self._q.put(cmd)
                return True                      # مؤخر — اورلی فعلی تمام شود
            self._run_manual(cmd[1], cmd[2], cmd[3])
            return False
        return False

    def _start_exit(self):
        self._t0 = time.perf_counter()
        self._phase = "out"
        self._set_state(self.ST_EXITING)

    def _finish_hide(self):
        self._phase = None
        try:
            self._render_transparent_frame()
            self._glfw.hide_window(self._win)
        except Exception:
            pass
        self._set_state(self.ST_HIDDEN)

    def _render_transparent_frame(self):
        ctx = self._ctx
        ctx.screen.use()
        ww, wh = self._glfw.get_framebuffer_size(self._win)
        ctx.viewport = (0, 0, ww, wh)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        self._glfw.swap_buffers(self._win)

    def _render_live(self, f):
        """حالت لایو + میکرو-انیمیشن‌های GPU (بند دستور): پارالاکس بازیکن ±1.5px،
           تنفس نوار اسم ±1px، ضربان Glow 0.92→1.00→0.94 — داده هیت‌مپ ثابت است."""
        eng = self._eng
        p = eng._entrance_params(f)
        t = f / FPS
        p["photo_dy"] += 1.5 * math.sin(t * 0.9)
        p["name_dx"] += 1.0 * math.sin(t * 0.7 + 1.0)
        p["heat_glow"] *= 0.96 + 0.04 * math.sin(t * 0.5)
        eng._draw(p, t)

    def _overlay_blit(self):
        """بلیت نهایی به صفحه: fit حفظ نسبت + ماسک SDF گوشه‌گرد (بیرون قاب = شفاف کامل)"""
        eng = self._eng
        if eng is None:
            return
        g, win, ctx = self._glfw, self._win, self._ctx
        ww, wh = g.get_framebuffer_size(win)
        s = min(float(ww) / RENDER_W, float(wh) / RENDER_H)
        fw, fh = RENDER_W * s, RENDER_H * s
        fx, fy = (ww - fw) * 0.5, (wh - fh) * 0.5
        ctx.screen.use()
        ctx.viewport = (0, 0, ww, wh)
        ctx.clear(0.0, 0.0, 0.0, 0.0)
        ctx.enable(moderngl.BLEND)
        _blend_src_over(ctx)
        pm = self._p_mask
        fr = FRAME_RECT
        pad = 3.0 * s                          # نگه‌داشتن نیم‌پیکسل خط لبه
        pm['uRes'].value = (float(ww), float(wh))
        pm['uRect'].value = (fx, fy, fw, fh)   # کواد = کل بوم (uv صحیح)
        pm['uMaskRect'].value = (fx + fr[0] * s - pad, fy + fr[1] * s - pad,
                                 fr[2] * s + 2.0 * pad, fr[3] * s + 2.0 * pad)
        pm['uRadius'].value = (FRAME_R + 3.0) * s
        pm['uTex'].value = 0
        eng.tex_out.use(0)
        self._vao_mask.render(moderngl.TRIANGLE_STRIP)
        g.swap_buffers(win)

    def _run_manual(self, assets, scale, events):
        """پنجره تعاملی کلید R — روی «همین ترد» میزبانی می‌شود؛ بدون init/terminate جدید."""
        g = self._glfw
        w, h = int(RENDER_W * scale), int(RENDER_H * scale)
        sess = None
        try:
            g.window_hint(g.VISIBLE, True)
            g.window_hint(g.DECORATED, True)
            g.window_hint(g.RESIZABLE, True)
            g.window_hint(g.FOCUS_ON_SHOW, True)
            g.window_hint(g.FLOATING, False)
            g.window_hint(g.TRANSPARENT_FRAMEBUFFER, False)
            g.window_hint(g.DOUBLEBUFFER, True)
            g.window_hint(g.SAMPLES, 0)
            win = g.create_window(w, h, "PES 2017  |  BROADCAST HEATMAP (GPU)",
                                  None, None)
            if not win:
                raise RuntimeError("glfw.create_window failed (manual)")
            g.make_context_current(win)
            g.swap_interval(1)
            mctx = self._mg.create_context()
            sess = _WindowSession(assets, events, scale, bundle=(win, mctx, g))
            events["ready"].set()
            self._set_state(self.ST_BUSY)
            sess.run()
            _release_gpu_members(sess.engine)
        except Exception as ex:
            events["failed"].set()
            print("[BroadcastRenderer] manual window failed:", ex, file=sys.stderr)
        finally:
            try:
                if sess is not None:
                    _release_gpu_members(sess.engine)
            except Exception:
                pass
            try:
                g.make_context_current(self._win)   # برگرد به کانتکست اورلی
            except Exception:
                pass
            if self._phase is None:
                self._set_state(self.ST_READY if self._eng is not None
                                else self.ST_HIDDEN)
