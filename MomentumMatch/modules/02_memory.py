class PitchConfig:
    FIELD_LENGTH = 105.0
    FIELD_WIDTH = 68.0
    HALF_LENGTH = FIELD_LENGTH / 2.0   # 52.5m
    HALF_WIDTH = FIELD_WIDTH / 2.0     # 34.0m

    GOAL_HALF_WIDTH = 3.66             # Z = +/- 3.66m
    GOAL_HEIGHT = 2.44                 # Y = 2.44m
    POST_RADIUS = 0.12                 # شعاع فیزیکی تیرک
    BALL_RADIUS = 0.11                 # شعاع توپ
    POST_COLLISION_RADIUS = 0.32       # آستانه تشخیص برخورد با تیرک (کالیبره Shot Engine)

    PENALTY_BOX_X = HALF_LENGTH - 16.5 # 36.0m
    PENALTY_BOX_HALF_Z = 20.16
    PENALTY_SPOT_X_ATT = HALF_LENGTH - 11.0 # 41.5m

    FINAL_THIRD_X = 17.5
    ZONE_14_X_MIN = 25.0
    ZONE_14_X_MAX = 36.0
    ZONE_14_HALF_Z = 12.0

    LONG_SHOT_DIST_MIN = 21.0
    CLOSE_SHOT_DIST_MAX = 9.5
    WIDE_ZONE_Z = 15.5
    CENTER_ZONE_Z = 8.5
    TIGHT_ANGLE_DEG = 17.0

    # آستانه‌های هندسی ویژه سانتر و کات‌بک (کالیبره Pass Engine)
    CROSS_LATERAL_THRESHOLD = 20.1      # قدرمطلق Z باید بیشتر از 20.1 باشد
    CROSS_LONGITUDINAL_THRESHOLD = 29.0 # قدرمطلق X باید بیشتر از 29 باشد
    CUTBACK_ORIGIN_X_THRESHOLD = 35.0   # قدرمطلق X مبدا باید بیشتر از 35 باشد
    CUTBACK_MAX_HEIGHT = 1.80           # حداکثر ارتفاع کات‌بک

    HEIGHT_GROUND_MAX = 0.70            # مرز سانتر/پاس زمینی
    HEIGHT_AERIAL_MIN = 1.60            # مرز سانتر/پاس هوایی

# =====================================================================
# ۴. پیکربندی فیزیک شوت (ShotConfig — کالیبره‌شده، دست‌نخورده)
# =====================================================================
class ShotConfig:
    MAX_TRACK_TIME = 3.0               # حداکثر زمان تعقیب پرواز شوت به ثانیه
    WORLD_TO_METER_SCALE = 1.0         # مقیاس مختصات به متر
    MIN_VALID_SHOT_SPEED = 18.0        # حداقل سرعت شوت معتبر (km/h)
    MAX_PLAUSIBLE_SPEED = 185.0        # حداکثر سرعت فیزیکی شوت (km/h)

    HEADER_HEIGHT_MIN = 1.45           # حداقل ارتفاع شروع برای بررسی ضربه سر
    HEADER_HEIGHT_OPTIMAL = 1.65       # ارتفاع استاندارد برای ضربه سر
    VOLLEY_HEIGHT_MIN = 0.45           # حداقل ارتفاع والی
    VOLLEY_HEIGHT_MAX = 1.40           # حداکثر ارتفاع والی

    GK_MAX_REACH_HEIGHT = 2.70         # حداکثر ارتفاع پرش دروازه‌بان برای مهار
    OUTFIELD_MAX_REACH_HEIGHT = 2.20   # حداکثر ارتفاع دسترسی مدافع برای بلوک

    STATIONARY_RADIUS = 0.22           # شعاع حداکثر حرکت برای توپ ساکن
    STATIONARY_DURATION_MIN = 0.75     # حداقل زمان سکون برای ضربات ایستگاهی (ثانیه)

    # --- نسخهٔ ۱۰٫۱۴ — لایهٔ Trigger → Contact/Shooter → Tracking → Registration ---
    # (مشخصات کاربر: «۱ افزایش شمارنده = ۱ کاندید شوت» + ریکاوری بر پایهٔ
    #  فریم/زمان بازی، نه تایم‌اوت کوتاه دیواری)
    SHOT_CONTACT_SCOPE = 26            # جستجوی فوری لحظهٔ ضربه (فریم — کالیبره ابزار مستقل)
    SHOT_PENDING_SCOPE = 120           # جستجوی عمیق در تلاش‌های بعدی (بافر ۳۲۰ فریمی)
    SHOT_RECOVERY_MAX_FRAMES = 260     # پنجرهٔ ریکاوری بر پایهٔ فریم (هماهنگ با بافر ۳۲۰)
    SHOT_RECOVERY_MAX_MATCH_SEC = 6.0  # پنجرهٔ ریکاوری بر پایهٔ زمان بازی
    SHOT_FINALIZED_KEEP = 64           # سقف نگهداری شناسهٔ کاندیدهای ثبت‌شده (Dedup)

    CORRIDOR_BASE_WIDTH = 1.8          # عرض دالان در مبدا ضربه
    CURVE_MIN_TRAJECTORY_LEN = 4.5     # حداقل طول مسیر برای بررسی کات توپ
    CURVE_RATIO_THRESHOLD = 0.052      # آستانه تشخیص شوت کات‌دار

# =====================================================================
# ۵. پیکربندی مرکزی امتیازدهی Momentum (بدون Magic Number در منطق)
# =====================================================================
class MomentumScoringConfig:
    # --- Pass: threat_score پاس منبع امتیاز است ---
    PASS_SUCCESS_MULTIPLIER = 1.00
    PASS_FAILURE_MULTIPLIER = 0.20

    # --- Chance ---
    CHANCE_WEIGHT = 35.0
    BIG_CHANCE_WEIGHT = 75.0

    # --- Shot: مبنای اصلی final_threat است؛ pre_shot_threat فقط ذخیره می‌شود ---
    # نسخهٔ ۱۰٫۱۲ (درخواست کاربر): «شوت‌ها نقش مهمی در مومنتوم دارند؛ بجز
    # شوت‌های منجر به گل، بقیه باید امتیاز مهمی داشته باشند» —
    #   * SHOT_APPLY_CONFIDENCE = False → امتیاز مومنتوم شوت دقیقاً برابر
    #     Final Threat ابزار مستقل است (ضریب اطمینان ۰٫۵۵-۰٫۹۵ دیگر آن را
    #     تا ۴۵٪ کم نمی‌کند — علت اصلی «امتیاز خیلی کمتر از ابزار شوت»)؛
    #   * SHOT_MIN_IMPACT = کف معنادار برای شوت‌های «نه گل» (حتی شوت دور
    #     از چارچوب هم سهم قابل‌مشاهده دارد)؛
    #   * شوت گل‌شده همچنان × GOAL_LINKED_SHOT_RATIO می‌شود تا گل هرگز دو
    #     بار حساب نشود (استثنای صریح کاربر).
    SHOT_WEIGHT = 1.00                 # ضریب اعمالی روی final_threat
    SHOT_APPLY_CONFIDENCE = False      # شوت: ضریب اطمینان طبقه‌بند اعمال نشود
    SHOT_MIN_IMPACT = 45.0             # کف امتیاز مومنتوم شوت‌های غیرگل
    GOAL_LINKED_SHOT_RATIO = 0.30      # سهم شوتِ گل‌شده (جلوگیری از دو بار حساب شدن با Goal)
    PENALTY_SHOT_LINKED_RATIO = 0.40   # سهم شوتی که نوع آن «پنالتی» تشخیص داده شده
    SHOT_LINKED_CHANCE_RATIO = 0.30    # کاهش سهم Chance در صورت لینک به Shot
    # پنجرهٔ تشخیص «شوت تکراری» — نسخهٔ ۱۰٫۱۴: منسوخ؛ Dedup فقط با شناسهٔ
    # کاندید انجام می‌شود (candidate_id) و این دو ثابت دیگر استفاده نمی‌شوند
    SHOT_DUP_MATCH_WINDOW = 1.0
    SHOT_DUP_POS_RADIUS = 2.5

    # --- Goal (پاسخ تأخیری گل — Goal Response / Goal Pulse) ---
    GOAL_WEIGHT = 100.0
    # فاصلهٔ اوج پاسخ گل از لحظهٔ گل — فقط بر حسب ثانیهٔ بازی (Game Time)
    GOAL_PEAK_DELAY = 5.0
    # طول فلات اوج (پهنا) پاسخ گل پیش از شروع decay نمایی — ثانیهٔ بازی
    GOAL_RESPONSE_WIDTH = 4.0

    # --- Penalty ---
    PENALTY_WEIGHT = 20.0              # وزن خود رخداد Penalty Kick
    PENALTY_GOAL_WEIGHT = 60.0         # وزن Penalty Goal بدون گل ثبت‌شده موازی
    PENALTY_GOAL_DELTA_WEIGHT = 15.0   # وزن Penalty Goal وقتی Goal همین رخداد قبلا ثبت شده
    PENALTY_GOAL_DEDUP_WINDOW = 5.0    # پنجره زمانی (ثانیه بازی) تشخیص Goal موازی
    PENALTY_MISS_WEIGHT = 25.0
    PENALTY_MISS_NEGATIVE = True       # پنالتی از دست رفته = momentum منفی برای زننده
    PENALTY_KICK_LINKED_RATIO = 0.25   # کاهش وزن Penalty Kick پس از ثبت Penalty Goal/Miss

    # --- Pressure Episode ---
    PRESSURE_BASE_WEIGHT = 6.0
    PRESSURE_DURATION_FACTOR = 0.8
    PRESSURE_INTENSITY_FACTOR = 2.5
    PRESSURE_MAX_WEIGHT = 18.0
    PRESSURE_MIN_DURATION = 4.0        # حداقل طول اپیزود فشار (ثانیه بازی)
    PRESSURE_MIN_AVG = 1.2             # حداقل میانگین تعداد فشاردهنده
    PRESSURE_RADIUS = 3.0              # شعاع فشار حول حامل توپ
    PRESSURE_CARRIER_RADIUS = 2.5      # شعاع تشخیص حامل توپ
    PRESSURE_RELIEF_TIME = 2.0         # زمان رفع فشار برای بستن اپیزود

    # --- Transition / Counterattack / Line Break ---
    TRANSITION_WEIGHT = 8.0
    COUNTERATTACK_WEIGHT = 18.0
    COUNTERATTACK_WINDOW = 8.0         # حداکثر زمان رسیدن به یک‌سوم برای ضدحمله
    TRANSITION_WINDOW = 10.0           # حداکثر زمان عبور به نیمه هجومی برای انتقال
    LINE_BREAK_WEIGHT = 12.0
    LINE_BREAK_COOLDOWN = 8.0

    # --- Zone Entries ---
    FINAL_THIRD_ENTRY_WEIGHT = 3.0
    BOX_ENTRY_WEIGHT = 6.0
    ZONE_EVENT_COOLDOWN = 12.0         # جلوگیری از اشباع نمودار با ورودهای مکرر
    CORNER_WEIGHT = 8.0
    CORNER_COOLDOWN = 25.0
    GOAL_KICK_WEIGHT = 2.0
    GOAL_KICK_COOLDOWN = 25.0

    # --- Possession Change (بیشتر برای زنجیره رویدادهاست نه امتیاز) ---
    POSSESSION_CHANGE_WEIGHT = 0.0

    # --- Reliability / Confidence ---
    CERTAIN_MULTIPLIER = 1.00
    PROBABLE_MULTIPLIER = 0.85
    INFERRED_MULTIPLIER = 0.65
    APPLY_CONFIDENCE = True            # ضرب نهایی در confidence رویداد

    # --- Decay (بر اساس GAME TIME) ---
    MOMENTUM_HALF_LIFE = 180.0         # نیم‌عمر = ۳ دقیقه زمان مسابقه

    # --- Presentation / Normalization (فقط لایه نمایش) ---
    DISPLAY_RANGE = 100.0
    DISPLAY_NORMALIZATION = "fixed"    # fixed | peak | raw
    DISPLAY_SOFT_SCALE = 120.0         # مقیاس soft-clip در حالت fixed
    # Gaussian smoothing واقعی (نه میانگین متحرک) — فقط روی لایه نمایش؛
    # مقدار بر حسب ثانیهٔ زمان بازی است و مستقل از نرخ نمونه‌برداری اعمال می‌شود.
    # نسخه ۴: 16.0s — نوک قله‌ها مثل «نمودار زنگوله‌ای» نرم و گرد می‌شود؛
    # ریز‌نوسان‌ها در موج پیوسته حل می‌شوند؛ RAW دست‌نخورده می‌ماند
    # نسخهٔ ۱۰٫۲۷: 16.0 → 20.0 — همان تنظیم «زنگوله‌ای» نسخهٔ 2017؛
    # قله‌ها/دره‌ها نرم‌تر و پهن‌تر می‌شوند (RAW همچنان دست‌نخورده)
    GAUSSIAN_SIGMA = 20.0     # v10.27 — ۱۶→۲۰ (هموارسازی موتور — منحنی نرم‌تر)

    # --- History Sampling ---
    HISTORY_SAMPLE_INTERVAL = 0.10     # هر 0.1 ثانیه زمان بازی یک نمونه

    # --- نسخه ۱۰٫۲: چسباندن شکاف توقف‌ها (حذف قطعهٔ افقی بعد از گل) ---
    # اگر بین دو نمونهٔ متوالی، ساعت بازی بیش از این مقدار پرش کند
    # (توقف جشن گل/Replay با ساعتِ در حال حرکت)، بازهٔ مرده از محور
    # «نمایش» حذف می‌شود: نمونهٔ بعدی دقیقاً یک interval بعد از آخرین
    # نمونهٔ واقعی می‌نشیند (دو قسمت نمودار به هم می‌چسبند) و درزِ محل
    # اتصال با یک پاره‌خط مستقیم صاف می‌شود. تولید خودِ منحنی تغییر
    # نمی‌کند (رسم = نسخهٔ قبلی).
    MOMENTUM_GLUE_GAP = 4.0            # آستانهٔ تشخیص شکاف توقف (ثانیهٔ زمان بازی)

    # --- نسخه ۱۰٫۲: آیکون توپ گل (tex/ball_icon.png کنار کد) ---
    BALL_ICON_SIZE_PT = 22.0           # قطر نمایشی آیکون توپ روی نمودار (Point)

    # --- Match Restart Detection ---
    MATCH_RESTART_DELTA = 5.0          # افت ناگهانی زمان بازی = ری‌استارت مسابقه

    # --- تشخیص HT / بازی جدید (نسخه ۳) ---
    # نمودار در پایان نیمه اول و «پایان کل مسابقه» هرگز خودکار پاک نمی‌شود؛
    # فقط شروع «بازی جدید» (تایمر از صفر + PLAYING) یا دکمهٔ «ریست مسابقه»
    # ریست کامل انجام می‌دهد. بین دو نیمه شکاف نمایشی با دو خط سرتاسری
    # و برچسب HT روی محور X درج می‌شود.
    # نسخه ۴: عرض شکاف یک‌سوم نسخه ۳ → 300 ثانیه (۵ دقیقه از کل مسابقه)
    HT_GAP_DISPLAY_SECONDS = 300.0     # نسخه ۴: عرض شکاف = ۵ دقیقه (یک‌سوم ۹۰۰ ثانیهٔ قبلی)
    HT_MIN_FIRST_HALF_PLAYED = 1500.0  # حداقل زمان بازی‌شدهٔ نیمه اول برای تشخیص HT
    HT_RESUME_TOLERANCE = 600.0        # از سرگیری نزدیک به پایان نیمه اول = HT (نه بازی جدید)
    NEW_GAME_MAX_START = 180.0         # از سرگیری زیر این مقدار = بازی جدید (تایمر از صفر)

    # --- نسخه ۱۰٫۳: قانون سخت HT (Match Lifecycle State Machine) ---
    # تصمیم نهایی HT دیگر فقط به تولرانس متکی نیست؛ این قانون سخت همیشه
    # داخل Logic اعمال می‌شود:
    #   HT فقط وقتی معتبر است که «نیمه اول واقعاً تمام شده باشد»:
    #     previous_match_time >= 45*60 (2700s)
    #     AND current_match_time حوالی 45:00 (پنجرهٔ [2700-slack، 2700+tolerance])
    #     AND current_state == PLAYING
    #   تایمر ≈ صفر (NEW_GAME_MAX_START) همیشه «بازی جدید» است، هرگز HT —
    #   حتی اگر بازی قبلی روی هر دقیقه‌ای متوقف شده باشد (نشانهٔ قوی).
    HT_HARD_MIN_FIRST_HALF = 2700.0    # 45*60 — حداقل زمان دیده‌شدهٔ نیمه اول برای HT واقعی
    HT_RESUME_LOWER_SLACK = 30.0       # از سرگیری باید «حوالی 45:00» باشد (نه وسط بازی)

    # --- نسخهٔ ۱۰٫۱۵ — وقت اضافه (بندهای ج/د چهار نوع ریست کاربر) ---
    # پنجرهٔ «حوالی ۹۰:۰۰ / ۱۰۵:۰۰» برای شروع ET1/ET2 بعد از ریست تایمر:
    # اولین نمونهٔ زندهٔ ET ممکن است کمی بعد از مرز فرود بیاید (تأخیر خط لوله
    # یا بازیِ ادامه‌یافته در سکوت ما) — ۱۲ دقیقه پنجرهٔ کافی و ایمن است.
    ET_RESET_TOLERANCE = 720.0

# =====================================================================
# ۶. هوک مالکیت توپ (PossessionHooker — نسخه واحد)
# =====================================================================
# نسخهٔ ۱۰٫۱۸ — چرخهٔ حیات جدید هوک مالکیت (مشخصات صریح کاربر):
#   * هوک «فقط» در فاز شکار آدرس نصب است: به محض صفر شدن تایمر (شروع
#     بازی جدید) نصب می‌شود؛ قبل از آن خط اسمبلی دست‌نخورده می‌ماند؛
#   * اولین آدرس Capture‌شده‌ای که «مقدار ۲» (میزبان) در آن باشد، آدرس
#     تشخیص میزبان/مهمان است؛ آدرس‌های بدون مقدار ۲ رد و اسلات صفر می‌شود؛
#   * بعد از تأیید، هوک «برداشته» می‌شود و همان آدرس تا پایان مسابقه
#     خوانده می‌شود (هوک نصب‌مانده دیگر ساختار را جابه‌جا نمی‌کند و
#     capture‌های گذرا/غلط نمی‌سازد)؛
#   * هر بار تایمر صفر شد، چرخهٔ شکار دوباره آغاز می‌شود.
# =====================================================================
POSS_CAPTURE_LOG = False     # نسخهٔ ۱۰٫۲۴ — پیش‌فرض خاموش (حذف لاگ کنسول؛ برای عیب‌یابی True شود)


def _poss_capture_log(msg: str):
    if POSS_CAPTURE_LOG:
        try:
            print(f"[PossHook] {msg}", flush=True)
        except Exception:
            pass


class PossessionHooker:
    ORIG_BYTES = b'\xC7\x47\x58\x02\x00\x00\x00' # mov [rdi+58h], 2

    def __init__(self):
        self.cave_address = None
        self.target_address = None
        self.captured_address = None
        self.captured_wall = None        # نسخهٔ ۱۰٫۱۸ — لحظهٔ تأیید capture
        self.is_hooked = False

    def hook(self, h_process, base_addr: int):
        if self.is_hooked:               # نسخهٔ ۱۰٫۱۸ — نصب دوباره ممنوع
            return
        self.target_address = base_addr + 0x9DFA86
        self.cave_address = allocate_near_target(h_process, self.target_address)
        if not self.cave_address:
            raise Exception("خطا در تخصیص حافظه برای هوک مالکیت.")

        cave_code_start = self.cave_address + 0x20
        return_addr = self.target_address + 7

        rel_jmp_back = return_addr - (cave_code_start + 0x27)
        rel_jmp_to_cave = cave_code_start - (self.target_address + 5)

        cave_bytes = bytearray([
            0xC7, 0x47, 0x58, 0x02, 0x00, 0x00, 0x00,
            0x50,
            0x9C,
            0x48, 0x8B, 0x05, 0xD0, 0xFF, 0xFF, 0xFF,
            0x48, 0x85, 0xC0,
            0x75, 0x0B,
            0x48, 0x8D, 0x47, 0x58,
            0x48, 0x89, 0x05, 0xC0, 0xFF, 0xFF, 0xFF,
            0x9D,
            0x58,
            0xE9
        ]) + struct.pack("<i", rel_jmp_back)

        safe_write(h_process, self.cave_address, b'\x00' * 8)
        safe_write(h_process, cave_code_start, bytes(cave_bytes))
        patch = b'\xE9' + struct.pack("<i", rel_jmp_to_cave) + b'\x90\x90'
        if safe_write(h_process, self.target_address, patch):
            self.is_hooked = True

    def unhook(self, h_process):
        if self.is_hooked and self.target_address and h_process:
            safe_write(h_process, self.target_address, self.ORIG_BYTES)
            self.is_hooked = False

    def reset_capture(self, h_process=None):
        """
        نسخه ۱۰٫۴ — re-arm اسلات چسبان Capture مالکیت (الگوی reset_capture هوک گل).

        مسئله: این هوک آدرس rdi+0x58 را فقط «یک‌بار» (اولین اجرای دستور بعد
        از اتصال) در اسلات داخل بازی می‌نویسد و سمت پایتون هم همان را برای
        همیشه cache می‌کند. در بارگذاری «بازی جدید»، بازی ساختار آمار/مالکیت
        را در آدرس تازه می‌سازد؛ Capture قدیمی به آدرس مرده می‌خواند →
        مالکیت None/منجمد → بدون تغییر مالکیت، هیچ پاس/شوت/رخدادی ثبت
        نمی‌شود (علامت گزارش‌شدهٔ «از بازی دوم به بعد فقط گل‌ها»).

        این متد اسلات داخل بازی را صفر می‌کند (تا دستور مالکیت در اولین اجرای
        بعدی دوباره Capture کند) و کش سمت پایتون را پاک می‌کند. صدا زدن با
        h_process=None فقط کش پایتون را پاک می‌کند (امن برای تست).
        """
        try:
            if h_process and self.cave_address:
                safe_write(h_process, self.cave_address, b'\x00' * 8)
        except Exception:
            pass
        self.captured_address = None

    def read_possession_byte(self, h_process) -> Optional[str]:
        if not self.cave_address:
            return None
        if not self.captured_address:
            buf = ctypes.c_uint64(0)
            kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(self.cave_address), ctypes.byref(buf), 8, None)
            if buf.value == 0:
                return None
            # --- نسخهٔ ۱۰٫۱۸ — اعتبارسنجی کاربر: فقط آدرسی که در لحظهٔ
            # capture «مقدار ۲» (میزبان) در آن است پذیرفته می‌شود؛ بقیه
            # رد و اسلات صفر می‌شود تا نوشتار بعدی دوباره Capture کند.
            candidate = buf.value
            val = ctypes.c_uint8(0)
            kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(candidate), ctypes.byref(val), 1, None)
            if val.value != 2:
                _poss_capture_log(
                    f"capture رد شد (val={val.value}) addr=0x{candidate:X} "
                    "— اسلات صفر شد؛ انتظار نوشتار بعدی")
                self.reset_capture(h_process)
                return None
            self.captured_address = candidate
            self.captured_wall = time.time()
            _poss_capture_log(
                f"آدرس میزبان/مهمان تأیید شد: 0x{candidate:X} (مقدار ۲ = میزبان) "
                "— هوک برداشته می‌شود؛ تا پایان مسابقه همین آدرس خوانده می‌شود")
            # کاربر: بعد از تشخیص، هوک حذف شود — خط اسمبلی به حالت اصلی
            # برمی‌گردد و فقط خواندنِ همان آدرس ادامه دارد.
            self.unhook(h_process)

        val = ctypes.c_uint8(0)
        kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(self.captured_address), ctypes.byref(val), 1, None)
        if val.value == 2: return "Home"
        if val.value == 1: return "Away"
        return None

# =====================================================================
# ۷. هوک جدید زمان مسابقه (TimeHooker)
# ---------------------------------------------------------------------
# دستور بازی:  FL_2026.exe+20F1CDA - 89 86 40010000 - mov [rsi+00000140],eax
#   Seconds = [rsi+0x140]   (همان جایی که eax نوشته می‌شود)
#   Minutes = [rsi+0x13C]   (دقیقا ۴ بایت قبل)
# Cave: اجرای دستور اصلی + capture RSI در یک memory slot داخلی
# =====================================================================
class TimeHooker:
    HOOK_OFFSET = 0x20F1CDA
    ORIG_BYTES = b'\x89\x86\x40\x01\x00\x00'   # mov [rsi+00000140],eax
    MINUTES_OFFSET = 0x13C
    SECONDS_OFFSET = 0x140

    def __init__(self):
        self.cave_address = None
        self.target_address = None
        self.data_address = None      # slot نگهداری RSI اسنپ‌شده
        self.is_hooked = False
        self.last_valid_wall = 0.0    # آخرین باری که زمان معتبر خوانده شد (فقط دیباگ)
        # [suite v2.1.5] bridge-managed time hook: the bytes belong to the
        # bridge, this object only READS the shared RSI slot and releases
        # its reference on unhook. Never writes game bytes in this mode.
        self.via_bridge = False
        self._bridge_cli = None

    def hook(self, h_process, base_addr: int):
        self.target_address = base_addr + self.HOOK_OFFSET

        # راستی‌آزمایی امضای دستور اصلی قبل از هرگونه نوشتن
        curr = safe_read(h_process, self.target_address, len(self.ORIG_BYTES))
        if curr is None:
            raise Exception("خواندن حافظه Time Hook ممکن نشد.")
        if curr == self.ORIG_BYTES:
            pass  # حالت عادی
        elif curr[0] == 0xE9:
            raise Exception("Time Hook قبلا نصب شده است (اجرای قبلی Restore نشده). بازی را ری‌استارت کنید.")
        else:
            raise Exception(
                "امضای دستور زمان مطابقت ندارد: " + curr.hex().upper() +
                " (آفست 0x20F1CDA نیاز به بازبینی دارد)"
            )

        self.cave_address = allocate_near_target(h_process, self.target_address, 128)
        if not self.cave_address:
            raise Exception("خطا در تخصیص حافظه برای Time Hook.")

        self.data_address = self.cave_address + 0x40   # slot 8 بایتی RSI
        code_start = self.cave_address + 0x20

        # ---------- Cave ----------
        # mov [rsi+0x140], eax      ; دستور اصلی بازی       (6)
        # push rax                  ;                        (1)
        # pushfq                    ;                        (1)
        # mov rax, rsi              ;                        (3)
        # mov [data_addr], rax      ; capture RSI           (10)
        # popfq                     ;                        (1)
        # pop rax                   ;                        (1)
        # jmp rel32 -> target+6                              (5)
        rel_jmp_back = (self.target_address + 6) - (code_start + 28)

        cave = bytearray([
            0x89, 0x86, 0x40, 0x01, 0x00, 0x00,       # mov [rsi+140],eax
            0x50,                                     # push rax
            0x9C,                                     # pushfq
            0x48, 0x89, 0xF0,                         # mov rax, rsi
            0x48, 0xA3                                # mov [qword], rax
        ]) + struct.pack('<Q', self.data_address)
        cave += bytearray([0x9D, 0x58, 0xE9])         # popfq, pop rax, jmp
        cave += struct.pack('<i', rel_jmp_back)

        if not safe_write(h_process, self.cave_address, b'\x00' * 8):
            raise Exception("پاک‌سازی slot زمان ناموفق بود.")
        if not safe_write(h_process, code_start, bytes(cave)):
            raise Exception("نوشتن کد Time Hook در Cave ناموفق بود.")

        patch = b'\xE9' + struct.pack('<i', code_start - (self.target_address + 5)) + b'\x90'
        if safe_write(h_process, self.target_address, patch):
            self.is_hooked = True
        else:
            raise Exception("نصب Patch Time Hook روی بازی ناموفق بود.")

    def unhook(self, h_process):
        # [suite v2.1.5] bridge-managed hook: the site bytes belong to the
        # bridge — only drop OUR reference (hook_release). Restoring bytes
        # here would kill the shared feed the Heat Map mod still reads.
        if getattr(self, "via_bridge", False):
            cli = getattr(self, "_bridge_cli", None)
            if cli is not None:
                try:
                    cli.hook_release(self.HOOK_OFFSET)
                except Exception:
                    pass
            self.is_hooked = False
            return
        if self.is_hooked and self.target_address and h_process:
            safe_write(h_process, self.target_address, self.ORIG_BYTES)
        self.is_hooked = False

    @staticmethod
    def compute_total_seconds(minutes: int, seconds: int) -> float:
        """
        تولید پایدار total_match_seconds:
        - اگر ثانیه به‌صورت ثانیه‌شماری معمولی (0..59) باشد -> minutes*60 + seconds
        - اگر بازی ثانیه را به‌صورت شمارنده/کل ثانیه ذخیره کرده باشد (> 59) -> خودِ آن مقدار
        """
        if seconds <= 59:
            return float(minutes * 60 + seconds)
        return float(seconds)

    def read_time_registers(self, h_process) -> Optional[Tuple[int, int]]:
        """خواندن (Minutes, Seconds) از ساختار زمان بازی از طریق RSI اسنپ‌شده"""
        if not self.is_hooked or not self.data_address:
            return None
        raw = safe_read(h_process, self.data_address, 8)
        if not raw:
            return None
        rsi_val = struct.unpack('<Q', raw)[0]
        if not rsi_val or rsi_val < 0x10000:
            return None  # هنوز capture نشده

        raw_m = safe_read(h_process, rsi_val + self.MINUTES_OFFSET, 4)
        raw_s = safe_read(h_process, rsi_val + self.SECONDS_OFFSET, 4)
        if not raw_m or not raw_s:
            return None

        minutes = struct.unpack('<I', raw_m)[0]
        seconds = struct.unpack('<I', raw_s)[0]

        # گاردهای عقلایی بودن مقادیر
        if minutes > 300 or seconds > 10800:
            return None

        self.last_valid_wall = time.time()
        return minutes, seconds

# =====================================================================
# ۷.۵ هوک ثبت گل از حافظه (GoalHooker — نسخه ۶ — Sticky First-Capture)
# ---------------------------------------------------------------------
# دستور بازی (گل میزبان):
#   FL_2026.exe+19ECBE2 - 44 89 89 58010000 - mov [rcx+00000158],r9d
# شمارندهٔ گل میهمان: «دقیقاً ۴ بایت جلوتر» از محل شمارندهٔ میزبان
#   → byte [rcx+0x15C]
# هر دو «متغیر یک‌بایتی» هستند (شمارندهٔ گل هر تیم؛ مقادیر 0,1,2,...)
#
# مکانیزم (نسخه ۶ — رفع باگ «فقط یک گل ثبت می‌شد»):
#   Cave دستور اصلی را عیناً اجرا می‌کند + RCX (پایهٔ ساختار آمار مسابقه)
#   را «فقط یک‌بار» — در اولین اجرای دستور بعد از اتصال (وقتی slot هنوز
#   صفر است) — در slot ذخیره می‌کند و دیگر هرگز بازنویسی نمی‌کند:
#       cmp qword [slot], 0  /  jne skip  /  mov [slot], rax  /  skip:
#   دلیل: بازی همین دستور را برای ساختارهای آمار دیگر (صفحات آمار،
#   پخش مجدد، ساختارهای موقت) هم اجرا می‌کند؛ در نسخه‌های قبل هر اجرا
#   slot را بازنویسی می‌کرد و بعد از اولین گل، slot با یک RCX بیگانه
#   خراب می‌شد → دیگر هیچ گلی ثبت نمی‌شد. اکنون شمارنده‌ها برای
#   «همهٔ گل‌های بعدی هر دو تیم» همیشه از همان ساختار درست خوانده
#   می‌شوند. Worker دو بایت شمارنده را Poll می‌کند:
#       Home = byte [rcx+0x158]   |   Away = byte [rcx+0x15C]
#   هر «افزایش» شمارنده = یک گل (نه اجرای دستور!). در پخش مجدد گل،
#   شمارنده جهش نمی‌زند؛ بنابراین گل هرگز دوبار ثبت نمی‌شود.
#
# هوک دوم (اختیاری و خودکار): اگر ۷ بایت بعد از هوک میزبان دقیقاً
#   «mov [rcx+0000015C],r9d» باشد (نوشتن شمارندهٔ میهمان بلافاصله بعد از
#   میزبان)، آن دستور هم هوک می‌شود تا RCX حتی قبل از اولین گل میزبان
#   (مثلاً وقتی میهمان اولین گل را می‌زند) capture شده باشد.
#
# اتصال مجدد (Adopt): اگر هوک نسخهٔ ۶ قبلاً در بازی نصب باشد، به‌جای
#   خطا پذیرفته می‌شود و slot صفر می‌شود تا capture تازهٔ این جلسه
#   انجام شود (هوک فقط در اولین اتصال «انجام» می‌شود؛ اتصال‌های بعدی
#   فقط از نصب موجود استفاده می‌کنند).
# =====================================================================
class GoalHooker:
    HOOK_OFFSET = 0x19ECBE2
    ORIG_BYTES = b'\x44\x89\x89\x58\x01\x00\x00'            # mov [rcx+158h],r9d
    AWAY_EXPECTED_BYTES = b'\x44\x89\x89\x5C\x01\x00\x00'   # mov [rcx+15Ch],r9d
    HOME_COUNTER_OFFSET = 0x158
    AWAY_COUNTER_OFFSET = 0x15C      # دقیقاً ۴ بایت جلوتر (مشخصات کاربر)
    MAX_COUNTER_VALUE = 20           # گارد عقلایی بودن بایت شمارنده
    MAX_GOAL_JUMP = 3                # سقف ایمنی برای جهش چندگانه در یک Poll
    # --- نسخه ۶: چیدمان Cave با capture یک‌بارمصرف ---
    CAVE_ALLOC_SIZE = 128            # حجم تخصیص Cave (کد + slot)
    CODE_OFFSET = 0x20               # شروع کد در Cave
    DATA_SLOT_OFFSET = 0x60          # slot ۸ بایتی RCX (بعد از کدِ ۴۱ بایتی)
    CAVE_CODE_SIZE = 41              # طول دقیق کد تولیدی (_build_capture_code)

    def __init__(self):
        self.cave_address = None
        self.data_home = None          # slot 8 بایتی RCX (فقط اولین capture نوشته می‌شود — نسخه ۶)
        self.target_address = None
        # --- هوک دوم (میهمان) ---
        self.away_installed = False
        self.away_target_address = None
        self.away_cave_address = None
        self.away_data = None
        self.is_hooked = False
        self.adopted = False           # نسخه ۶: اتصال به نصب موجود (بدون نصب مجدد)

    # -------------------------------------------------------------
    @staticmethod
    def counter_event(prev: Optional[int], new: Optional[int]) -> Tuple[str, int]:
        """
        تصمیم خالص از روی دو خواندن متوالی شمارنده (قابل تست بدون بازی):
          prev=None , new=None → ("WAIT", 0)      هنوز چیزی capture نشده
          prev=None , new=v    → ("BASELINE", 0)  اولین خواندن معتبر
          new > prev           → ("GOAL", n)      n گل جدید (سقف MAX_GOAL_JUMP)
          new < prev           → ("RESET", 0)     شروع بازی جدید / ری‌سنک
          برابر                → ("NOCHANGE", 0)
        """
        if new is None:
            return ("WAIT", 0) if prev is None else ("NOCHANGE", 0)
        if prev is None:
            return ("BASELINE", 0)
        if new > prev:
            return ("GOAL", min(new - prev, GoalHooker.MAX_GOAL_JUMP))
        if new < prev:
            return ("RESET", 0)
        return ("NOCHANGE", 0)

    # -------------------------------------------------------------
    def _install_cave(self, h_process, target: int, orig: bytes) -> Tuple[Optional[int], Optional[int]]:
        """نصب یک Cave الگو-TimeHooker روی target: اجرای دستور اصلی + capture یک‌بارمصرف RCX"""
        cave_address = allocate_near_target(h_process, target, self.CAVE_ALLOC_SIZE)
        if not cave_address:
            return None, None
        data_address = cave_address + self.DATA_SLOT_OFFSET   # slot 8 بایتی RCX (بعد از کد)
        code_start = cave_address + self.CODE_OFFSET

        # ---------- Cave (نسخه ۶ — Sticky First-Capture) ----------
        # mov [rcx+disp32], r9d        ; دستور اصلی بازی            (7)
        # push rax                     ;                             (1)
        # push rcx                     ;                             (1)
        # pushfq                       ;                             (1)
        # mov rax, rcx                 ;                             (3)
        # cmp qword [slot],0           ; slot صفر است؟               (8)
        # jne skip                     ; نه → capture قبلاً انجام شده  (2)
        # mov [slot], rax              ; بله → فقط همین‌بار capture   (10)
        # skip:
        # popfq                        ;                             (1)
        # pop rcx                      ;                             (1)
        # pop rax                      ;                             (1)
        # jmp rel32 → target+7         ;                             (5)
        # مجموع = 41 بایت (CAVE_CODE_SIZE)
        code = self._build_capture_code(orig, data_address, target, code_start)

        # slot صفر → اولین اجرای دستور بعد از اتصال capture می‌شود
        if not safe_write(h_process, cave_address, b'\x00' * self.CAVE_ALLOC_SIZE):
            return None, None
        if not safe_write(h_process, code_start, code):
            return None, None

        patch = b'\xE9' + struct.pack('<i', code_start - (target + 5)) + b'\x90\x90'
        if not safe_write(h_process, target, patch):
            return None, None
        return cave_address, data_address

    # -------------------------------------------------------------
    @staticmethod
    def _build_capture_code(orig: bytes, slot: int, target: int,
                            code_start: int) -> bytes:
        """
        نسخه ۶ — تولید بایت‌کد Cave با capture «یک‌بارمصرف»:
        RCX فقط وقتی در slot نوشته می‌شود که slot هنوز صفر باشد
        (اولین اجرای دستور بعد از اتصال). در اجراهای بعدی شرط jne
        مسیر store را رد می‌کند → slot هرگز با RCX بیگانه بازنویسی
        نمی‌شود → شمارنده‌های هر دو تیم تا آخر مسابقه از ساختار درست
        خوانده می‌شوند. (خالص و قابل تست بدون بازی)
        """
        code = bytearray(orig)                                  # (7)
        code += bytes([0x50, 0x51, 0x9C])                       # push rax, push rcx, pushfq
        code += bytes([0x48, 0x89, 0xC8])                       # mov rax, rcx
        cmp_pos = len(code)                                     # 13
        code += bytes([0x48, 0x83, 0x3D, 0, 0, 0, 0, 0])        # cmp qword [rip+disp32], 0
        jne_pos = len(code)                                     # 21
        code += bytes([0x75, 0x00])                             # jne rel8 → skip
        code += bytes([0x48, 0xA3]) + struct.pack('<Q', slot)   # mov [slot], rax (فقط اولین‌بار)
        pop_pos = len(code)                                     # 33 → skip:
        code += bytes([0x9D, 0x59, 0x58])                       # popfq, pop rcx, pop rax
        code += bytes([0xE9])                                   # jmp rel32
        # rel32 نسبت به انتهای دستور jmp: انتهای فعلی + ۴ بایت rel32
        code += struct.pack('<i', (target + 7) - (code_start + len(code) + 4))
        # --- fixups ---
        # disp32 مقایسه rip-relative: از انتهای دستور cmp سنجیده می‌شود
        struct.pack_into('<i', code, cmp_pos + 3, slot - (code_start + cmp_pos + 8))
        # rel8 پرش jne روی دستور store ده‌بایتی
        code[jne_pos + 1] = (pop_pos - (jne_pos + 2)) & 0xFF
        if len(code) != GoalHooker.CAVE_CODE_SIZE:
            raise Exception(f"طول کد Cave نامعتبر: {len(code)}")
        return bytes(code)

    # -------------------------------------------------------------
    @staticmethod
    def _parse_existing_cave_code(code: bytes, orig: bytes) -> Optional[int]:
        """
        نسخه ۶ — تشخیص Cave «نسخهٔ ۶» نصب‌شده از جلسهٔ قبلی و استخراج
        آدرس slot از دستور mov [abs64], rax. اگر بایت‌ها الگوی نسخهٔ ۶
        نباشد (مثلاً Cave قدیمی نسخهٔ ۴/۵ که capture همیشگی دارد) None
        برمی‌گردد تا اتصال مجدد با آن مجاز نشود (باید بازی ری‌استارت شود).
        """
        if len(code) < GoalHooker.CAVE_CODE_SIZE:
            return None
        if code[0:len(orig)] != orig:
            return None
        if (bytes(code[7:10]) == b'\x50\x51\x9C'              # push rax, push rcx, pushfq
                and bytes(code[10:13]) == b'\x48\x89\xC8'     # mov rax, rcx
                and bytes(code[13:16]) == b'\x48\x83\x3D'     # cmp qword [rip+disp32], 0
                and code[21] == 0x75                          # jne (skip store)
                and bytes(code[23:25]) == b'\x48\xA3'):       # mov [abs64], rax
            return struct.unpack('<Q', code[25:33])[0]
        return None

    # -------------------------------------------------------------
    def hook(self, h_process, base_addr: int):
        self.target_address = base_addr + self.HOOK_OFFSET

        # راستی‌آزمایی امضای دستور اصلی قبل از هرگونه نوشتن
        curr = safe_read(h_process, self.target_address, len(self.ORIG_BYTES))
        if curr is None:
            raise Exception("خواندن حافظه Goal Hook ممکن نشد.")
        if curr == self.ORIG_BYTES:
            # --- حالت عادی: نصب تازه Cave (تنها بار «انجام شدن» هوک) ---
            self.cave_address, self.data_home = self._install_cave(
                h_process, self.target_address, self.ORIG_BYTES)
            if not self.cave_address:
                raise Exception("خطا در تخصیص حافظه برای Goal Hook (میزبان).")
        elif curr[0] == 0xE9:
            # --- نسخه ۶: Adopt — هوک نسخهٔ ۶ قبلاً نصب شده (جلسهٔ قبل
            # Restore نشده). به‌جای خطا، نصب موجود پذیرفته می‌شود؛
            # slot هم صفر می‌شود تا capture تازهٔ «این اتصال» انجام شود
            # (رفتار «هوک فقط در دفعهٔ اولِ اتصال» حفظ می‌ماند).
            rel = struct.unpack('<i', curr[1:5])[0]
            code_start = self.target_address + 5 + rel
            existing = safe_read(h_process, code_start, self.CAVE_CODE_SIZE)
            slot = self._parse_existing_cave_code(existing, self.ORIG_BYTES) if existing else None
            if slot is None:
                raise Exception(
                    "Goal Hook قدیمی (نسخهٔ ۴/۵) در بازی نصب است و قابل Adopt نیست؛ "
                    "برای فعال‌شدن capture یک‌بارمصرف نسخهٔ ۶، بازی را یک‌بار ری‌استارت کنید.")
            self.cave_address = code_start - self.CODE_OFFSET
            self.data_home = slot
            self.adopted = True
            safe_write(h_process, self.data_home, b'\x00' * 8)   # capture تازه این جلسه
            clog(f"[GoalHook] نصب موجود Adopt شد (slot={slot:#x}) — slot صفر شد "
                  f"تا اولین نوشتار گل این جلسه capture شود")
        else:
            raise Exception(
                "امضای دستور گل میزبان مطابقت ندارد: " + curr.hex().upper() +
                " (آفست 0x19ECBE2 نیاز به بازبینی دارد)"
            )

        # --- هوک دوم (میهمان): فقط اگر امضا دقیقاً ۷ بایت بعد باشد ---
        try:
            nxt = safe_read(h_process, self.target_address + 7, len(self.AWAY_EXPECTED_BYTES))
            if nxt == self.AWAY_EXPECTED_BYTES:
                a_cave, a_data = self._install_cave(
                    h_process, self.target_address + 7, self.AWAY_EXPECTED_BYTES)
                if a_cave:
                    self.away_installed = True
                    self.away_target_address = self.target_address + 7
                    self.away_cave_address = a_cave
                    self.away_data = a_data
            elif nxt and nxt[0] == 0xE9:
                # Adopt هوک میهمانِ نسخهٔ ۶ از جلسهٔ قبلی
                rel = struct.unpack('<i', nxt[1:5])[0]
                a_code_start = (self.target_address + 7) + 5 + rel
                a_existing = safe_read(h_process, a_code_start, self.CAVE_CODE_SIZE)
                a_slot = self._parse_existing_cave_code(a_existing, self.AWAY_EXPECTED_BYTES) if a_existing else None
                if a_slot is not None:
                    self.away_installed = True
                    self.away_target_address = self.target_address + 7
                    self.away_cave_address = a_code_start - self.CODE_OFFSET
                    self.away_data = a_slot
                    safe_write(h_process, self.away_data, b'\x00' * 8)
                    clog(f"[GoalHook] هوک میهمان موجود Adopt شد (slot={a_slot:#x})")
        except Exception:
            self.away_installed = False   # غیرحیاتی — Poll از طریق slot میزبان کار می‌کند

        self.is_hooked = True

    def unhook(self, h_process):
        if h_process and self.target_address:
            try:
                safe_write(h_process, self.target_address, self.ORIG_BYTES)
            except Exception:
                pass
        if h_process and self.away_installed and self.away_target_address:
            try:
                safe_write(h_process, self.away_target_address, self.AWAY_EXPECTED_BYTES)
            except Exception:
                pass
        self.is_hooked = False
        self.away_installed = False

    # -------------------------------------------------------------
    def reset_capture(self, h_process):
        """
        نسخه ۶ — صفر کردن slotهای capture برای «اجازهٔ capture مجدد».
        فقط مسیر «ریست مسابقه / بازی جدید» این متد را صدا می‌زند تا
        اولین نوشتارِ گلِ بازیِ جدید، ساختار تازه را capture کند.
        در جریان عادی مسابقه هرگز فراخوانی نمی‌شود (capture فقط
        اولین‌بار بعد از اتصال انجام می‌شود).
        """
        try:
            if h_process and self.data_home:
                safe_write(h_process, self.data_home, b'\x00' * 8)
            if h_process and self.away_data:
                safe_write(h_process, self.away_data, b'\x00' * 8)
        except Exception:
            pass

    # -------------------------------------------------------------
    def _read_rcx_slot(self, h_process, slot: Optional[int]) -> Optional[int]:
        if not slot:
            return None
        raw = safe_read(h_process, slot, 8)
        if not raw:
            return None
        val = struct.unpack('<Q', raw)[0]
        if not val or val < 0x10000:
            return None
        return val

    def poll(self, h_process) -> Dict[str, Any]:
        """
        خواندن وضعیت هوک + دو شمارندهٔ گل از ساختار آمار.
        خروجی: {"hooked", "captured", "secondary", "rcx", "home", "away"}
        home/away یا int (0..MAX_COUNTER_VALUE) یا None هستند.
        """
        out = {"hooked": self.is_hooked, "captured": False, "secondary": self.away_installed,
               "rcx": None, "home": None, "away": None}
        if not self.is_hooked or not h_process:
            return out

        rcx = self._read_rcx_slot(h_process, self.data_home)
        if rcx is None:
            rcx = self._read_rcx_slot(h_process, self.away_data)
        if rcx is None:
            return out   # هنوز هیچ نوشتاری اجرا نشده

        out["captured"] = True
        out["rcx"] = rcx

        raw_h = safe_read(h_process, rcx + self.HOME_COUNTER_OFFSET, 1)
        raw_a = safe_read(h_process, rcx + self.AWAY_COUNTER_OFFSET, 1)
        if raw_h:
            v = struct.unpack('<B', raw_h)[0]
            if v <= self.MAX_COUNTER_VALUE:
                out["home"] = v
        if raw_a:
            v = struct.unpack('<B', raw_a)[0]
            if v <= self.MAX_COUNTER_VALUE:
                out["away"] = v
        return out

# =====================================================================
# ۷٫۵ — توابع خالص کمکی لایهٔ Detection (نسخه ۱۰ — قابل تست بدون بازی)
# =====================================================================
GH_HEARTBEAT_INTERVAL = 5.0   # ثانیه — تپش [GoalHookPoll]


def gh_due_heartbeat(now: float, last: Optional[float],
                     interval: float = GH_HEARTBEAT_INTERVAL) -> bool:
    """آیا وقت لاگ تپش [GoalHookPoll] رسیده؟ (اولین فراخوانی همیشه بله)"""
    if last is None:
        return True
    return (now - last) >= interval


def gh_pick_poll_time(total_t: Optional[float],
                      core_t: Optional[float]) -> float:
    """
    انتخاب زمان مسابقه برای Poll گل (نسخه ۱۰):
      کلید ساعت این لحظه اگر معتبر (> 0)؛ وگرنه آخرین زمان معتبر core؛
      وگرنه ۰. Poll گل نباید به‌خاطر ساعتِ موقتاً خراب از دست برود.
    """
    if total_t is not None and total_t > 0:
        return float(total_t)
    if core_t is not None and core_t > 0:
        return float(core_t)
    return 0.0


# =====================================================================
# ۷٫۶ — نسخه ۱۰٫۳: Match Lifecycle State Machine (توابع خالص — قابل تست بدون بازی)
# ---------------------------------------------------------------------
# چرخهٔ کامل:  HALF_1 → (HT واقعی) → HALF_2 → (پایان) → FULL_TIME
#             هر جای مسیر: تایمر ≈ صفر + PLAYING → NEW_MATCH (ریست کامل)
# اصل سخت: HT فقط وقتی معتبر است که «نیمه اول واقعاً تمام شده باشد»؛
# یعنی قبلاً زمان معتبر ≥ 45:00 دیده شده باشد. صرفِ «کاهش زمان» هرگز HT
# نیست (مثال‌های نقض: 90:00→00:00، 03:00→02:59، 06:00→…) و دقیقه ۶ هر
# بازی نباید تحت هیچ شرایطی HT تولید کند.
# =====================================================================
class MatchPhase(Enum):
    HALF_1 = "HALF_1"
    HALFTIME = "HALFTIME"      # افت زمان بعد از نیمه اول دیده شد — در انتظار از سرگیری
    HALF_2 = "HALF_2"
    # --- نسخهٔ ۱۰٫۱۵ — وقت اضافه (چهار نوع ریست کاربر؛ بندهای ج و د) ---
    # ET1: ریست تایمر از بالای ۹۰:۰۰ به ۹۰:۰۰ + Playing + تایمرِ در حال رشد
    # ET2: ریست تایمر از بالای ۱۰۵:۰۰ به ۱۰۵:۰۰ + Playing + تایمرِ در حال رشد
    ET1 = "ET1"
    ET2 = "ET2"
    FULL_TIME = "FULL_TIME"    # مسابقه تمام شد — نمودار حفظ می‌شود (پاک نمی‌شود)
    NEW_MATCH = "NEW_MATCH"    # گذرا — بعد از ریست کامل به HALF_1 برمی‌گردد


def should_flag_time_drop(prev_t: Optional[float], current_t: float,
                          min_delta: float) -> bool:
    """
    نسخه ۱۰٫۳ — آیا افت بزرگ زمان بازی باید «علامت» بخورد؟
    فقط علامت؛ هیچ تصمیمی اینجا گرفته نمی‌شود (تصمیم نهایی هنگام
    از سرگیری PLAYING با classify_resume_after_drop گرفته می‌شود).
    """
    if prev_t is None or prev_t <= 0:
        return False
    return (prev_t - current_t) > min_delta


def classify_resume_after_drop(prev_end_t: float, current_t: float,
                               half_number: int, *,
                               ht_hard_min: float = 2700.0,
                               ht_resume_lower_slack: float = 30.0,
                               ht_resume_tolerance: float = 600.0,
                               new_game_max_start: float = 180.0,
                               et_reset_tolerance: float = 720.0) -> str:
    """
    نسخه ۱۰٫۳ — تصمیم قطعی پس از از سرگیری PLAYING (بعد از یک افت بزرگ زمان).
    خروجی: "HT" | "NEW_MATCH" | "ET1" | "ET2" | "KEPT"

    قانون ۱ — بازی جدید (قوی‌ترین سیگنال؛ مقدم بر همه):
        current ≈ 0  →  NEW_MATCH
        (90:xx → 0:00 و 6:xx → 0:00 هرگز HT نیستند؛ بازی جدید ممکن است
         بعد از توقف روی «هر دقیقه‌ای» شروع شود)

    قانون ۲ — HT (قانون سخت، صریح داخل Logic — نه صرفاً تولرانس):
        half == 1
        AND previous valid game time >= 45*60   (نیمه اول واقعاً تمام شده)
        AND current حوالی 45:00 باشد:
             (ht_hard_min - lower_slack) <= current <= (ht_hard_min + tolerance)
        (45:xx/46:xx → 45:00 = شروع نیمه دوم همان بازی)

    قانون ۲-ج — شروع وقت اضافه (نسخهٔ ۱۰٫۱۵ — بند ج چهار نوع ریست کاربر):
        half == 2
        AND previous time بالاتر از ۹۰:۰۰ دیده شده (وقت هدررفتهٔ نیمهٔ دوم)
        AND current حوالی ۹۰:۰۰ (سقوط تایمر روی ۹۰:۰۰):
             (90*60 - slack) <= current <= (90*60 + et_reset_tolerance)
        ⇒ ET1 (نیمهٔ اول وقت اضافه)

    قانون ۲-د — شروع نیمهٔ دوم وقت اضافه (بند د):
        half == 3
        AND previous time بالاتر از ۱۰۵:۰۰ دیده شده (وقت هدررفتهٔ ET1)
        AND current حوالی ۱۰۵:۰۰  ⇒  ET2

    قانون ۳ — بقیهٔ حالت‌ها (پایان مسابقه/صفحهٔ آمار/ری‌سنک):
        KEPT → نمودار حفظ می‌شود؛ هیچ HT و هیچ ریستی ساخته نمی‌شود
        (6:00 تحت هیچ شرایطی HT تولید نمی‌کند چون prev_end < 2700 است)
    """
    # ۱) بازی جدید — تایمر ≈ صفر
    if current_t <= new_game_max_start:
        return "NEW_MATCH"
    # ۲-د) شروع نیمهٔ دوم وقت اضافه — ریست ۱۰۵ از بالای ۱۰۵ (نسخهٔ ۱۰٫۱۵)
    if (half_number == 3
            and prev_end_t > 105.0 * 60.0
            and (105.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 105.0 * 60.0 + et_reset_tolerance):
        return "ET2"
    # ۲-ج) شروع وقت اضافه — ریست ۹۰ از بالای ۹۰ (نسخهٔ ۱۰٫۱۵)
    if (half_number == 2
            and prev_end_t > 90.0 * 60.0
            and (90.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 90.0 * 60.0 + et_reset_tolerance):
        return "ET1"
    # ۲) HT — قانون سخت
    if (half_number == 1
            and prev_end_t >= ht_hard_min
            and (ht_hard_min - ht_resume_lower_slack) <= current_t
            and current_t <= ht_hard_min + ht_resume_tolerance):
        return "HT"
    # ۳) حفظ نمودار
    return "KEPT"


def is_new_match_watchdog(seen_max_t: float, current_t: float,
                          new_game_max_start: float,
                          min_delta: float) -> bool:
    """
    نسخه ۱۰٫۳ — Watchdog مستقل بازی جدید (بدون نیاز به فلگ افت زمان).
    وقتی در جریان PLAYING تایمر ≈ صفر است اما مسابقهٔ جاری واقعاً جلو
    رفته (بیش از پنجرهٔ شروع + دلتا)، یعنی مسابقهٔ قبلی تمام و بازیِ
    جدید شروع شده — حتی اگر به‌هر دلیلی «افت زمان» علامت نخورده باشد
    (مثلاً core در منوها از قبل به صفر به‌روز شده باشد).
    """
    if current_t > new_game_max_start:
        return False
    return seen_max_t > (max(new_game_max_start, current_t) + min_delta)


# =====================================================================
# ۷٫۷ — نسخه ۱۰٫۴: لاگ تشخیصی فایل txt + سلامت خط لولهٔ داده (Pipeline Health)
# ---------------------------------------------------------------------
# هدف: وقتی بعد از شروع «بازی دوم» فقط گل‌ها ثبت می‌شوند و پاس/شوت/رخداد
# قطع می‌شود، این بخش نشان می‌دهد دقیقاً کدام لایهٔ داده مرده است.
#   * DebugLogger — فایل txt کنار اسکریپت (thread-safe؛ هرگز exception
#     بالا نمی‌دهد) با هدر Session، رویدادهای فوری و Heartbeat آستانه‌دار.
#   * توابع خالص تصمیم (قابل تست بدون بازی): possession_rearm_needed،
#     freeze_seconds، should_warn_frozen_counter، fmt_ptr.
# قواعد خواندن لاگ (راهنمای سریع):
#   HB st=... t=... poss=... nP=... pass=... shot=... | ptr ... | gates ...
#     - gates bp>0 در همهٔ خط‌ها  → گیت ball/players حلقه را می‌کشد
#     - poss=- و cap=- همیشگی    → capture مالکیت مرده (POSS_REARM می‌بینیم؟)
#     - pass/shot ثابت + pPtr/sPtr ثابت بین دو بازی → پوینتر منجمد (STALE؟)
#     - ghRcx بین دو بازی فرق کند → اثبات جابه‌جایی ساختار آمار در بازی جدید
# =====================================================================
DEBUG_LOG_FILENAME = "momentum_debug_log.txt"
DEBUG_LOG_HEARTBEAT_SEC = 5.0
DEBUG_LOG_MAX_BYTES = 4 * 1024 * 1024
POSS_REARM_STALE_SEC = 20.0      # مالکیت نامعتبرِ پایدار در جریان PLAYING → re-arm
POSS_REARM_THROTTLE_SEC = 60.0   # حداقل فاصلهٔ دو re-arm خودکار
COUNTER_FROZEN_WARN_SEC = 45.0   # شمارندهٔ پاس/شوت بدون تغییر در جریان PLAYING → STALE؟


class DebugLogger:
    """
    نسخه ۱۰٫۴ — لاگ متنی ساده و مقاوم برای تشخیص زنده‌بودن لایه‌های داده.
      * append با هدر Session (هر اجرای برنامه یک بلاک جدید)
      * write/event همیشه فوری؛ heartbeat با آستانهٔ زمانی (throttle)
      * چرخش ساده: عبور از max_bytes → فایل به path+".1" منتقل می‌شود
      * هیچ‌وقت exception بالا نمی‌دهد (لاگ نباید برنامه را بکشد)
    """

    def __init__(self, path: str, enabled: bool = DEBUG_LOG_ENABLED,
                 heartbeat_sec: float = DEBUG_LOG_HEARTBEAT_SEC,
                 max_bytes: int = DEBUG_LOG_MAX_BYTES):
        self.enabled = bool(enabled)
        self.path = path
        self.heartbeat_sec = float(heartbeat_sec)
        self.max_bytes = int(max_bytes)
        self._lock = threading.Lock()
        self._last_hb_wall: Optional[float] = None
        self._fh = None
        if self.enabled:
            try:
                self._open("a")
                self.write("SESSION", f"v10.6 | python={sys.version.split()[0]} | log={path}")
            except Exception:
                self._fh = None

    def _open(self, mode: str):
        self._fh = open(self.path, mode, encoding="utf-8", errors="replace")

    def _rotate_if_needed(self):
        try:
            if self._fh and self._fh.tell() > self.max_bytes:
                self._fh.close()
                self._fh = None
                try:
                    if os.path.exists(self.path + ".1"):
                        os.remove(self.path + ".1")
                    os.rename(self.path, self.path + ".1")
                except Exception:
                    pass
                self._open("a")
        except Exception:
            pass

    @staticmethod
    def _stamp() -> str:
        return time.strftime("%Y-%m-%d %H:%M:%S")

    def write(self, tag: str, msg: str = "", level: str = "INFO"):
        if not self.enabled:
            return
        line = f"{self._stamp()} [{level}] [{tag}] {msg}".rstrip() + "\n"
        try:
            with self._lock:
                if self._fh is None:
                    self._open("a")
                self._fh.write(line)
                self._fh.flush()
                self._rotate_if_needed()
        except Exception:
            pass

    def event(self, tag: str, **kv):
        parts = []
        for k, v in kv.items():
            parts.append(f"{k}={v}")
        self.write(tag, " ".join(parts))

    def warn(self, tag: str, msg: str = ""):
        self.write(tag, msg, level="WARN")

    def error(self, tag: str, msg: str = ""):
        self.write(tag, msg, level="ERROR")

    def heartbeat_due(self, now_wall: Optional[float] = None) -> bool:
        """آیا وقت نوشتن Heartbeat رسیده؟ (آستانه‌دار؛ فراخوانی سبک هر تیک)"""
        if not self.enabled:
            return False
        now_wall = time.time() if now_wall is None else now_wall
        if self._last_hb_wall is None or (now_wall - self._last_hb_wall) >= self.heartbeat_sec:
            self._last_hb_wall = now_wall
            return True
        return False

    def close(self):
        try:
            with self._lock:
                if self._fh:
                    self._fh.close()
                    self._fh = None
        except Exception:
            pass


def fmt_ptr(v: Optional[int]) -> str:
    """آدرس حافظه به hex برای لاگ؛ None/صفر → '-' (قابل تست بدون بازی)"""
    if not v:
        return "-"
    try:
        return f"{int(v):#x}"
    except Exception:
        return "-"


def freeze_seconds(last_change_wall: Optional[float], now_wall: float) -> float:
    """چند ثانیه از آخرین «تغییر معتبر» گذشته؟ (بدون سابقه → -1)"""
    if last_change_wall is None:
        return -1.0
    try:
        return max(0.0, float(now_wall) - float(last_change_wall))
    except Exception:
        return -1.0


def possession_rearm_needed(poss_valid: bool, m_state: str, time_advancing: bool,
                            stale_sec: float, throttle_ok: bool) -> bool:
    """
    نسخه ۱۰٫۴ — تصمیم re-arm خودکار capture مالکیت (تابع خالص):
      فقط وقتی: مالکیت نامعتبر + بازی واقعاً در جریان است (PLAYING و ساعت
      در حال پیش رفت) + مدت نامعتبری از آستانه گذشت + throttle باز باشد.
      عمداً محافظه‌کار: هیچ re-arm ای در Pause/Replay/منو یا با ساعت مرده.
    """
    if poss_valid:
        return False
    if m_state != "PLAYING" or not time_advancing:
        return False
    if stale_sec < POSS_REARM_STALE_SEC:
        return False
    return bool(throttle_ok)


def should_warn_frozen_counter(freeze_sec: float, m_state: str,
                               warn_after: float = COUNTER_FROZEN_WARN_SEC) -> bool:
    """
    نسخه ۱۰٫۴ — شمارندهٔ پاس/شوت در جریان PLAYING مدت‌ها بدون تغییر مانده؟
    (در Pause/Replay انجماد طبیعی است و نباید هشدار بدهد)
    """
    if m_state != "PLAYING":
        return False
    return freeze_sec >= warn_after


# =====================================================================
# ۸. موتور استخراج داده‌های بازی (GameEngine — نسخه یکپارچه هر سه فایل)
# =====================================================================
class BridgeHookClient:
    """
    v2.0.6 — client for the ModBridge HOOK BROKER (localhost JSON-line TCP).

    ARCHITECTURE (user request): mods must NOT hook or reset game bytes
    themselves anymore. The bridge is the single owner of hook bytes:

      * hook_request  -> bridge installs the hook ONCE (or points us at the
                         EXISTING shared hook's data buffer — no second hook)
      * hook_status   -> cheap liveness check (no log noise on the bridge)
      * hook_release  -> we no longer need the feed; the bridge restores the
                         original bytes only when the LAST consumer leaves

    The channel is a long-lived connection: if this process dies, the bridge
    sees the dropped socket and releases our references automatically, so a
    shared hook is never destroyed while somebody still needs it.

    Discovery: MODBRIDGE_IPC_PORT / MODBRIDGE_IPC_TOKEN environment variables
    (set by the bridge at spawn time), else <PES MODS>/bridge_ipc.json
    (written by the bridge for manually-started mods).
    Pure stdlib; every call is silent + fail-safe (returns None on any error,
    reason in last_error) so the engine can fall back to the legacy local
    path when the bridge is not running at all.
    """
    MOD_NAME = "Match Momentum"

    def __init__(self, mod_name: str = MOD_NAME,
                 port: Optional[int] = None, token: Optional[str] = None,
                 ipc_file: Optional[str] = None):
        self.mod_name = mod_name
        self.last_error = "not-configured"
        # RLock: _rpc holds it while _connect() runs and _connect itself
        # sends the hello request through _rpc (re-entrant).
        self._lock = threading.RLock()
        self._sock = None
        self._buf = b""
        self._req_id = 0
        self._rpc_timeout = 6.0
        # --- discovery: env first, then the bridge_ipc.json file ---
        if port is None:
            try:
                port = int(os.environ.get("MODBRIDGE_IPC_PORT", "") or 0) or None
            except Exception:
                port = None
        if token is None:
            token = os.environ.get("MODBRIDGE_IPC_TOKEN") or None
        self._token = token
        self._port = port
        self._ipc_file = ipc_file or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bridge_ipc.json")
        if self._port is None and self._token is None:
            try:
                with open(self._ipc_file, "r", encoding="utf-8") as f:
                    d = json.load(f)
                self._port = int(d.get("port") or 0) or None
                self._token = str(d.get("token") or "") or None
            except Exception:
                pass

    # -------------------------------------------------------------
    def available(self) -> bool:
        """True when broker coordinates were found (env or ipc file)."""
        return bool(self._port and self._token)

    def _refresh_from_file(self) -> bool:
        """Re-read the ipc file — a RESTARTED bridge writes fresh
        coordinates (new port/token); the file is the newest truth."""
        try:
            with open(self._ipc_file, "r", encoding="utf-8") as f:
                d = json.load(f)
            port = int(d.get("port") or 0) or None
            token = str(d.get("token") or "") or None
            if port and token:
                self._port, self._token = port, token
                return True
        except Exception:
            pass
        return False

    def _try_handshake(self) -> bool:
        """Open the socket if needed and send hello on it."""
        if self._sock is None:
            try:
                s = socket.create_connection(("127.0.0.1", int(self._port)),
                                             timeout=self._rpc_timeout)
                s.settimeout(self._rpc_timeout)
            except Exception as e:
                self.last_error = f"connect-failed:{e.__class__.__name__}"
                return False
            self._sock = s
            self._buf = b""
        try:
            hello = {"id": 0, "cmd": "hello", "mod": self.mod_name,
                     "token": self._token}
            self._sock.sendall((json.dumps(hello) + "\n").encode("utf-8"))
            while b"\n" not in self._buf:
                chunk = self._sock.recv(4096)
                if not chunk:
                    raise ConnectionError("closed")
                self._buf += chunk
            line, self._buf = self._buf.split(b"\n", 1)
            resp = json.loads(line.decode("utf-8"))
            if not resp.get("ok"):
                self.last_error = resp.get("error") or "hello-refused"
                return False
            return True
        except Exception as e:
            self.last_error = f"hello:{e.__class__.__name__}"
            self._close_sock()
            return False

    def _connect(self) -> bool:
        if not self.available():
            self.last_error = "not-configured"
            return False
        if self._try_handshake():
            return True
        # a restarted bridge issues NEW credentials; the ipc file always
        # carries the coordinates of the broker that is live RIGHT NOW —
        # refresh once and retry, then give up (caller falls back)
        if self._refresh_from_file() and self._try_handshake():
            return True
        self._close_sock()
        return False

    def _close_sock(self):
        try:
            if self._sock is not None:
                self._sock.close()
        except Exception:
            pass
        self._sock = None
        self._buf = b""

    def close(self):
        with self._lock:
            self._close_sock()

    # -------------------------------------------------------------
    def _rpc(self, cmd: str, _noreconnect: bool = False,
             **fields) -> Optional[dict]:
        """One request -> one response dict (or None). Reconnects once on a
        dropped pipe — the broker keeps our hook refs while we are away."""
        with self._lock:
            for attempt in (0, 1):
                if self._sock is None:
                    if _noreconnect or not self._connect():
                        return None
                self._req_id += 1
                rid = self._req_id
                req = {"id": rid, "cmd": cmd}
                req.update({k: v for k, v in fields.items()
                            if not k.startswith("_")})
                try:
                    self._sock.sendall(
                        (json.dumps(req) + "\n").encode("utf-8"))
                    while b"\n" not in self._buf:
                        chunk = self._sock.recv(4096)
                        if not chunk:
                            raise ConnectionError("closed")
                        self._buf += chunk
                    line, self._buf = self._buf.split(b"\n", 1)
                    resp = json.loads(line.decode("utf-8"))
                    if int(resp.get("id", -1)) != rid:
                        raise ValueError("response id mismatch")
                    return resp
                except Exception as e:
                    self.last_error = f"{cmd}:{e.__class__.__name__}"
                    self._close_sock()
                    if _noreconnect or attempt == 1:
                        return None
            return None

    # -------------------------------------------------------------
    # public API — every method returns None/False on ANY failure and
    # explains itself through last_error (never raises).
    # -------------------------------------------------------------
    def hook_request(self, site_rva: int, orig_bytes: bytes,
                     nop: int = 2, kind: str = "xmm0") -> Optional[int]:
        """Ask the bridge to hook site_rva (or SHARE its existing hook).
        kind selects the capture cave layout ("xmm0" ball feed, "rsi"
        time feed — byte-identical to the local TimeHooker cave so the
        bridge can adopt/share it with the Heat Map mod). Returns the
        absolute data-buffer address to read, or None."""
        resp = self._rpc("hook_request", site_rva=int(site_rva),
                         orig_hex=bytes(orig_bytes).hex(), nop=int(nop),
                         kind=str(kind or "xmm0"))
        if not resp or not resp.get("ok"):
            if resp:
                self.last_error = f"hook_request:{resp.get('error', 'refused')}"
            return None
        try:
            return int(resp.get("buffer"))
        except Exception:
            self.last_error = "hook_request:bad-buffer"
            return None

    def hook_status(self, site_rva: int) -> Optional[dict]:
        resp = self._rpc("hook_status", site_rva=int(site_rva))
        if not resp or not resp.get("ok"):
            if resp:
                self.last_error = f"hook_status:{resp.get('error', 'refused')}"
            return None
        return resp

    def hook_release(self, site_rva: int) -> bool:
        resp = self._rpc("hook_release", site_rva=int(site_rva))
        if not resp or not resp.get("ok"):
            if resp:
                self.last_error = f"hook_release:{resp.get('error', 'refused')}"
            return False
        return True

    def hook_reset_request(self, site_rva: int, orig_bytes: bytes,
                           nop: int = 2, kind: str = "xmm0") -> Optional[int]:
        """v2.0.7 — the feed looks DEAD (frozen buffer): ask the bridge to
        restore the original bytes, drop the old record and REBUILD the
        hook. Returns the (possibly new) buffer address, or None."""
        resp = self._rpc("hook_reset_request", site_rva=int(site_rva),
                         orig_hex=bytes(orig_bytes).hex(), nop=int(nop),
                         kind=str(kind or "xmm0"))
        if not resp or not resp.get("ok"):
            if resp:
                self.last_error = f"hook_reset:{resp.get('error', 'refused')}"
            return None
        try:
            return int(resp.get("buffer"))
        except Exception:
            self.last_error = "hook_reset:bad-buffer"
            return None

    def ping(self) -> Optional[dict]:
        return self._rpc("ping")

    def game_status(self) -> Optional[dict]:
        """[suite v2.1.5] — is FL_2026.exe running? PROCESS DETECTION IS
        THE BRIDGE'S JOB (user architecture): the bridge polls the game
        every 2 s, so a backend opened BEFORE the game simply asks and
        waits instead of trusting its own one-shot process scan. Returns
        {running, pid, base, name} or None when the bridge is unreachable
        at all (standalone run — the caller may use the legacy local scan)."""
        resp = self._rpc("game_status")
        if not resp or not resp.get("ok"):
            if resp:
                self.last_error = f"game_status:{resp.get('error', 'refused')}"
            return None
        return resp

# =====================================================================
# ۸. موتور استخراج داده‌های بازی (GameEngine — نسخه یکپارچه هر سه فایل)
# =====================================================================
class GameEngine:
    BALL_HOOK_OFFSET = 0x176A3A2
    BALL_ORIG_BYTES = b'\x0F\x29\x80\x50\x04\x00\x00'
    PLAYERS_ARRAY_OFFSET = 0x036F3FC0
    PASS_COUNT_OFFSET = 0x036F4270
    SHOT_COUNT_PTR_OFFSET = 0x036F4238
    SHOT_COUNT_FIRST_OFFSET = 0x3C
    MATCH_STATE_OFFSET = 0x372D148
    MATCH_TIME_OFFSET = 0x0372D114
    # --- نسخهٔ ۱۰٫۲۷ — کارت قرمز (پوینتر ۳ سطحی — بدون هوک) ---
    # زنجیرهٔ Cheat Engine کاربر:
    #   آدرس پایه: "FL_2026.exe"+036F3F88 / آفست اول: 350 / آفست دوم: 4E0
    RED_CARD_PTR_OFFSET = 0x036F3F88
    RED_CARD_CHAIN = (0x350, 0x4E0)
    RED_CARD_COUNTER_MAX = 1000        # گارد ارزش (آدرس مرده → عبث)

    def __init__(self):
        self.h_process = None
        self.pid = None
        self.base_addr = None
        self.ball_hook_addr = 0
        self.ball_cave_addr = 0
        self.ball_data_addr = 0
        # v2.0.1 — True when the live E9 at the ball site belongs to ANOTHER
        # owner (bridge-style cave we adopted); then we must never restore
        # the site bytes on cleanup (the owner manages its own lifecycle).
        self.ball_hook_adopted = False
        # v2.0.6 — True when the ball hook is OWNED BY THE BRIDGE (we asked
        # the HookBroker for it). The site bytes are then never touched by
        # this process at all: install / share / restore is all the
        # bridge's decision (user architecture change).
        self.ball_hook_via_bridge = False
        self.bridge_client = BridgeHookClient("Match Momentum")
        # [suite v2.1.5] the SHARED time site is bridge-managed too (the
        # Heat Map mod reads the same RSI slot) — see initialize().
        self.time_hook_via_bridge = False
        self.poss_hooker = PossessionHooker()
        self.time_hooker = TimeHooker()
        # نسخه ۴: هوک ثبت گل از حافظه (جایگزین تشخیص هندسی مسیر توپ/دروازه)
        self.goal_hooker = GoalHooker()
        self.is_ready = False

    def initialize(self) -> Tuple[bool, str]:
        proc_name = None
        # [suite v2.1.5] — PROCESS DETECTION IS THE BRIDGE'S JOB: when the
        # bridge answers, it is the ONLY authority on FL_2026.exe (it polls
        # the game every 2 s, so a backend opened BEFORE the game still
        # learns the moment the game appears — the local toolhelp scan of
        # THIS process could not be trusted for that timing). A bridge that
        # answers is obeyed: running -> attach with the pid + base it hands
        # us; not running -> report and let the next auto-connect tick
        # retry (no local scan). Only when the bridge does NOT answer at
        # all (standalone run) is the legacy local scan used.
        _cli = self.bridge_client
        _gstate, _gdata = (self._game_via_bridge(_cli)
                           if (_cli is not None and _cli.available())
                           else ("unreachable", None))
        if _gstate == "running":
            proc_name, self.pid, self.base_addr = _gdata
        elif _gstate == "idle":
            # the bridge answered: the game is NOT running — detection is
            # the bridge's job, so do NOT scan locally; retry on the next
            # auto-connect tick
            return False, "بازی باز نیست! ابتدا بازی را اجرا کنید."
        else:
            for pname in ["FL_2026.exe", "PES2021.exe"]:
                self.pid = get_pid_by_name(pname)
                if self.pid:
                    proc_name = pname
                    break

            if not self.pid:
                return False, "بازی باز نیست! ابتدا بازی را اجرا کنید."

        self.h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.h_process:
            return False, "دسترسی سیستمی به پروسه مسدود است (Run as Admin)."

        self.base_addr = get_module_base(self.pid, proc_name)
        if not self.base_addr:
            return False, "ماژول بازی یافت نشد."

        base = int(self.base_addr)
        warnings = []

        # نسخهٔ ۱۰٫۱۸ — اتصال تازه = چرخهٔ capture مالکیتِ تازه (وضعیت
        # اتصال قبلی — آدرس/کِیو هوک پروسهٔ قبلی — کاملاً پاک می‌شود)
        self.poss_hooker = PossessionHooker()

        # --- هوک مالکیت (نسخهٔ ۱۰٫۱۸ — مشخصات صریح کاربر): دیگر «در لحظهٔ
        # اتصال» نصب نمی‌شود! خط اسمبلی مالکیت باید تا «لحظهٔ صفر تایمر»
        # دست‌نخورده بماند؛ در آن لحظه چرخهٔ شکار آدرس آغاز می‌شود (نصب هوک
        # → اولین captureِ دارای مقدار ۲ → برداشتن هوک → خواندن همان آدرس
        # تا پایان مسابقه). برای اتصالِ وسطِ بازی، اولین تیک PLAYING چرخه
        # را آغاز می‌کند (worker_loop → _possession_begin_capture_cycle).

        # --- هوک توپ ---
        # v2.0.6 — معمارِ جدید کاربر: نصب/ریستِ بایت‌ها فقط کار ModBridge است.
        # اول از HookBroker درخواست می‌کنیم؛ پل یا هوکِ موجود را «مشترک»
        # به ما می‌دهد (آدرس بافرش) یا یک‌بار هوک می‌زند. خودِ این پروسه دیگر
        # هیچ بایتِ هوکی نمی‌نویسد تا وقتی پل در دسترس نباشد (اجرای دستی).
        self.ball_hook_adopted = False
        self.ball_hook_via_bridge = False
        self.ball_hook_addr = base + self.BALL_HOOK_OFFSET
        self.ball_cave_addr = 0
        self.ball_data_addr = 0
        _cli = self.bridge_client
        _bridge_up = (_cli is not None and _cli.available())
        if _bridge_up:
            _buf = self._ball_hook_via_broker(_cli)
            if _buf:
                self.ball_data_addr = int(_buf)
                self.ball_hook_adopted = True      # bytes are NOT ours — ever
                self.ball_hook_via_bridge = True
                print(f"[BALL HOOK] via ModBridge broker — shared data "
                      f"buffer 0x{self.ball_data_addr:X} (site bytes owned "
                      f"by the bridge)", flush=True)
            else:
                # [suite v2.1.5] — the bridge owns the bytes: a refused
                # request must NEVER fall back to a local hook (a second
                # hook on a shared site is exactly what disturbs the other
                # mod's feed). The 2 s link watchdog retries through the
                # bridge until it is granted.
                _err = getattr(_cli, "last_error", "")
                warnings.append(f"Ball Hook: bridge refused ({_err}) — will retry via the bridge")
                print(f"[BALL HOOK] broker request failed ({_err}) — "
                      "NO local fallback (bytes owned by the bridge; the "
                      "link watchdog retries)", flush=True)
        if not self.ball_hook_via_bridge and not _bridge_up:
            curr_b = safe_read(self.h_process, self.ball_hook_addr, 7)
            if curr_b and curr_b[0] == 0xE9:
                rel = struct.unpack('<i', curr_b[1:5])[0]
                self.ball_cave_addr = self.ball_hook_addr + 5 + rel
                self.ball_data_addr = self._resolve_ball_data_from_cave(
                    self.ball_cave_addr)
                if self.ball_data_addr:
                    self.ball_hook_adopted = True
                else:
                    # کِیو ناشناخته است — با هوک خودمان جایگزین می‌شود (شکل پچ
                    # یکسان است و بایت‌های اصلی در کِیو اجرا می‌شوند — امن)
                    if not self._install_ball_hook(base):
                        self._partial_cleanup()
                        return False, "خطا در نصب هوک توپ."
            else:
                if not self._install_ball_hook(base):
                    self._partial_cleanup()
                    return False, "خطا در نصب هوک توپ."

        # --- هوک جدید زمان مسابقه (TimeHooker) ---
        # [suite v2.1.5] — THE SHARED TIME SITE (0x20F1CDA) IS ALSO THE HEAT
        # MAP'S TIME SITE: two independent local hooks on this one site are
        # exactly what "disturbed the time" when both mods ran (the second
        # install either refused with 'already installed' or orphaned the
        # first cave). With the bridge up, BOTH mods request the SAME
        # kind="rsi" hook and the bridge answers with ONE shared RSI slot;
        # a refusal never falls back to local bytes (watchdog retries).
        _time_bridged = False
        if _bridge_up:
            _tbuf = self._time_hook_via_broker(_cli)
            if _tbuf:
                _th = self.time_hooker
                _th.via_bridge = True
                _th._bridge_cli = _cli
                _th.target_address = int(self.base_addr) + TimeHooker.HOOK_OFFSET
                _th.cave_address = 0
                _th.data_address = int(_tbuf)
                _th.is_hooked = True
                self.time_hook_via_bridge = True
                _time_bridged = True
                print(f"[TIME HOOK] via ModBridge broker — shared RSI slot "
                      f"0x{int(_tbuf):X} (ONE hook feeds Match Momentum + "
                      "Heat Map)", flush=True)
            else:
                _terr = getattr(_cli, "last_error", "")
                warnings.append(f"Time Hook: bridge refused ({_terr}) — will retry via the bridge")
                print(f"[TIME HOOK] broker request failed ({_terr}) — "
                      "NO local fallback (bytes owned by the bridge; the "
                      "link watchdog retries)", flush=True)
        if not _time_bridged and not _bridge_up:
            try:
                self.time_hooker.hook(self.h_process, self.base_addr)
            except Exception as e:
                # نصب نشد -> خطای واضح گزارش می‌شود و به زمان جایگزین (MATCH_TIME_OFFSET) سقوط می‌کنیم
                warnings.append(f"Time Hook: {e} (از زمان جایگزین استفاده می‌شود)")

        # --- هوک ثبت گل (GoalHooker — نسخه ۴) ---
        # غیرحیاتی: اگر امضا مطابقت نکرد فقط هشدار داده می‌شود؛ در این حالت
        # هیچ مسیر جایگزینی برای ثبت گل وجود ندارد (مسیر هندسی حذف شده است)
        try:
            self.goal_hooker.hook(self.h_process, self.base_addr)
        except Exception as e:
            warnings.append(f"Goal Hook: {e} (ثبت گل غیرفعال)")

        self.is_ready = True
        msg = "اتصال و هوک‌ها برقرار شدند."
        if warnings:
            msg += " | هشدار: " + " | ".join(warnings)
        return True, msg

    def _game_via_bridge(self, cli):
        """[suite v2.1.5] — ask the bridge whether FL_2026.exe is running.
        Returns ("running", (name, pid, base)) when the bridge says the
        game is up, ("idle", None) when the bridge answers but the game is
        not running (the caller MUST NOT scan locally — detection is the
        bridge's job), ("unreachable", None) when no bridge answers at all
        (standalone run — the caller may use the legacy local scan)."""
        try:
            st = cli.game_status()
        except Exception:
            return "unreachable", None
        if st is None:
            return "unreachable", None
        if not st.get("running"):
            return "idle", None
        try:
            pid = int(st.get("pid") or 0)
            base = int(str(st.get("base") or "0"), 16)
        except Exception:
            return "unreachable", None
        if not pid or not base:
            return "unreachable", None
        return "running", (str(st.get("name") or "FL_2026.exe"), pid, base)

    def _time_hook_via_broker(self, cli) -> Optional[int]:
        """[suite v2.1.5] — ask the HookBroker for the SHARED time hook
        (kind="rsi", byte-identical to the local TimeHooker cave so the
        same site feeds both mods from one slot). While the bridge is
        reachable but its game link is not up yet, keep WAITING instead of
        racing it with a local hook. Returns the shared RSI-slot address
        or None — the caller must NEVER write hook bytes itself."""
        deadline = time.time() + 20.0
        while True:
            buf = cli.hook_request(TimeHooker.HOOK_OFFSET,
                                   TimeHooker.ORIG_BYTES, 1, kind="rsi")
            if buf:
                return int(buf)
            err = str(getattr(cli, "last_error", ""))
            # bridge reachable, but not connected to the game yet -> wait
            if "not connected" in err and time.time() < deadline:
                time.sleep(2.0)
                continue
            return None

    def _ball_hook_via_broker(self, cli) -> Optional[int]:
        """v2.0.6 — ask the HookBroker for the shared ball hook (user
        architecture: the bridge owns all hook bytes). While the bridge is
        reachable but its game link is not up yet, keep WAITING instead of
        racing it with a local hook. Returns the data-buffer address or
        None (caller falls back to the legacy local path)."""
        deadline = time.time() + 20.0
        while True:
            buf = cli.hook_request(self.BALL_HOOK_OFFSET,
                                   self.BALL_ORIG_BYTES, 2)
            if buf:
                return int(buf)
            err = str(getattr(cli, "last_error", ""))
            # bridge reachable, but not connected to the game yet -> wait
            if "not connected" in err and time.time() < deadline:
                time.sleep(2.0)
                continue
            return None

    def _resolve_ball_data_from_cave(self, cave_addr: int) -> int:
        """v2.0.1 — تعارض هوک توپ: از روی اولین دستور کِیو موجود، آدرس بافر
        داده‌ای که XMM0 گرفتارشده در آن نوشته می‌شود پیدا می‌شود:
          کِیو ModBridge : 0F 11 05 rel32 (movups [buf], xmm0) → buf = cave+7+rel32
          کِیو momentum : کِیو با بایت‌های اصلی movaps شروع می‌شود → داده = cave+64
        خروجی 0 = امضای ناشناخته."""
        try:
            code = safe_read(self.h_process, cave_addr, 40)
        except Exception:
            return 0
        if not code:
            return 0
        code = bytes(code)
        try:
            if code[0:3] == b'\x0F\x11\x05':
                rel = struct.unpack('<i', code[3:7])[0]
                return cave_addr + 7 + rel
            if code[0:7] == self.BALL_ORIG_BYTES:
                return cave_addr + 64
        except Exception:
            pass
        return 0

    def verify_ball_link(self) -> str:
        """v2.0.5 — چکِ سبکِ دوره‌ایِ زنده‌بودنِ خطِ دادهٔ توپ (۲ ثانیه یک‌بار):
        کاربر پرسید «هوک هنوز وصل است؟ نمودار خالی چرا؟». علتِ واقعیِ
        «نمودارِ خالی/منجمد» در میدان: هوکِ مشترکِ سایت توپ توسط ابزار
        دیگری (restore خروج GLT / crash-recovery بازیابیِ mem_backup)
        بازنویسی می‌شود؛ این چک وضعیت را گزارش و در صورت نیاز ترمیم می‌کند.
        v2.0.6 — وقتی هوک از پل (HookBroker) گرفته شده، بایت‌ها اصلاً مالِ
        ما نیستند؛ فقط از طریق پل وضعیت را چک می‌کنیم و در صورت نیاز
        «درخواست» را تکرار می‌کنیم (نصب/اشتراک/بازگردانی همه تصمیمِ پل است).
        خروجی یکی از:
          ok / re-adopt / reinstall / unknown-cave / install-fail /
          signature-mismatch / read-fail   (مسیر محلی)
          ok / re-adopt(bridge) / reinstalled(bridge) / install-fail(bridge)
          / bridge-lost                    (مسیر پل)
        هزینه: خواندنِ ۷ بایتِ ریموت هر ~۲ ثانیه — ناچیز."""
        if not (self.h_process and self.base_addr and self.ball_hook_addr):
            return "not-connected"
        base = int(self.base_addr)
        # --- v2.0.6 / v2.1.5 — bridge-managed hook: never touch bytes
        # ourselves. The branch now covers the NOT-YET-GRANTED case too
        # (a hook refused at initialize is re-requested here every ~2 s
        # until the bridge grants it — still zero local bytes).
        if getattr(self, "ball_hook_via_bridge", False):
            cli = self.bridge_client
            if cli is None or not cli.available():
                return "bridge-lost"
        cli = getattr(self, "bridge_client", None)
        if cli is not None and cli.available():
            st = cli.hook_status(self.BALL_HOOK_OFFSET)
            if st is None:
                return "bridge-lost"
            if st.get("hooked"):
                try:
                    buf = int(st.get("buffer") or 0)
                except Exception:
                    buf = 0
                if buf and buf != self.ball_data_addr:
                    self.ball_data_addr = buf      # bridge re-created/adopted it
                    self.ball_hook_adopted = True
                    self.ball_hook_via_bridge = True
                    return "re-adopt(bridge)"
                if buf and not self.ball_hook_via_bridge:
                    # granted since initialize (was refused) — first adopt
                    self.ball_data_addr = buf
                    self.ball_hook_adopted = True
                    self.ball_hook_via_bridge = True
                    return "re-adopt(bridge)"
                return "ok"
            buf = cli.hook_request(self.BALL_HOOK_OFFSET,
                                   self.BALL_ORIG_BYTES, 2)
            if buf:
                self.ball_data_addr = int(buf)
                self.ball_hook_adopted = True
                self.ball_hook_via_bridge = True
                return "reinstalled(bridge)"
            return "install-fail(bridge)"
        try:
            curr = safe_read(self.h_process, base + self.BALL_HOOK_OFFSET, 7)
        except Exception:
            return "read-fail"
        if curr is None:
            return "read-fail"
        if curr[0] == 0xE9:
            try:
                rel = struct.unpack('<i', curr[1:5])[0]
                cave = (base + self.BALL_HOOK_OFFSET + 5 + rel)
            except Exception:
                return "read-fail"
            if cave == self.ball_cave_addr:
                return "ok"
            data = self._resolve_ball_data_from_cave(cave)
            if data:
                self.ball_cave_addr = cave
                self.ball_data_addr = data
                self.ball_hook_adopted = True
                return "re-adopt"
            return "unknown-cave"
        if bytes(curr) == self.BALL_ORIG_BYTES:
            return "reinstall" if self._install_ball_hook(base) else "install-fail"
        return "signature-mismatch"

    def reset_ball_hook_via_bridge(self) -> Optional[int]:
        """v2.0.7 — the ARBITRATED self-heal: the ball feed is frozen, so
        ask the bridge to restore the site bytes, drop the old record and
        rebuild the hook; adopt whatever buffer the bridge hands back.
        This process still never writes hook bytes itself (user's
        architecture: requests only, the bridge decides and executes).
        Returns the new buffer address or None (not bridge-managed /
        bridge unreachable / refused)."""
        if not getattr(self, "ball_hook_via_bridge", False):
            return None
        cli = self.bridge_client
        if cli is None or not cli.available():
            return None
        buf = cli.hook_reset_request(self.BALL_HOOK_OFFSET,
                                     self.BALL_ORIG_BYTES, 2)
        if buf:
            self.ball_data_addr = int(buf)
        return buf

    def _ball_site_is_ours(self) -> bool:
        """v2.0.1 — True فقط وقتی E9 فعلیِ سایت توپ به کِیو خودِ ما اشاره
        می‌کند؛ در آن حالت و فقط در آن حالت اجازهٔ restore بایت‌های اصلی
        را داریم (هوک مالک دیگری هرگز خراب نمی‌شود).
        v2.0.6 — وقتی هوک از پل گرفته شده، بایت‌ها هرگز مالِ ما نیستند."""
        try:
            if getattr(self, "ball_hook_via_bridge", False):
                return False          # bytes belong to the bridge — never ours
            if not (self.ball_hook_addr and self.h_process
                    and self.ball_cave_addr):
                return False
            curr = safe_read(self.h_process, self.ball_hook_addr, 7)
            if not curr or curr[0] != 0xE9:
                return False          # سایت از قبل اصلی است — کاری نیست
            if self.ball_hook_adopted:
                return False          # کِیو مال ما نیست (پذیرفته‌شده)
            rel = struct.unpack('<i', bytes(curr[1:5]))[0]
            return (self.ball_hook_addr + 5 + rel) == self.ball_cave_addr
        except Exception:
            return False

    def _install_ball_hook(self, base: int) -> bool:
        """
        نسخهٔ ۱۰٫۷ — نصب هوک توپ (استخراج‌شده از initialize؛ رفتار عین قبل).
        در initialize و در verify_and_repair_hooks (نوسازی شروع دست جدید)
        استفاده می‌شود. True = نصب موفق. (v2.0.1 — پرچم adopted همیشه ریست
        می‌شود چون از این لحظه کِیو مال خودِ ماست.)
        """
        self.ball_hook_adopted = False
        self.ball_hook_addr = base + self.BALL_HOOK_OFFSET
        self.ball_cave_addr = allocate_near_target(self.h_process, self.ball_hook_addr, 128)
        if not self.ball_cave_addr:
            return False
        self.ball_data_addr = self.ball_cave_addr + 64

        cave_b = bytearray(self.BALL_ORIG_BYTES)
        cave_b.append(0x53)
        cave_b.extend(b'\x48\xBB')
        cave_b.extend(struct.pack('<Q', self.ball_data_addr))
        cave_b.extend(b'\x0F\x11\x03')
        cave_b.append(0x5B)
        cave_b.extend(b'\xFF\x25\x00\x00\x00\x00')
        cave_b.extend(struct.pack('<Q', self.ball_hook_addr + 7))

        safe_write(self.h_process, self.ball_cave_addr, bytes(cave_b))
        rel_jmp = self.ball_cave_addr - (self.ball_hook_addr + 5)
        patch = b'\xE9' + struct.pack('<i', rel_jmp) + b'\x90\x90'
        return bool(safe_write(self.h_process, self.ball_hook_addr, patch))

    def link_alive(self) -> bool:
        """
        نسخهٔ ۱۰٫۷ — کنترل سبک حیات پروسه: خواندن ۱ بایتی از ناحیهٔ وضعیت.
        None ⇒ پروسه بسته/هندل مرده است (برای اتصال مجدد خودکار).
        """
        try:
            if not self.h_process or not self.base_addr:
                return False
            return safe_read(self.h_process,
                             int(self.base_addr) + self.MATCH_STATE_OFFSET, 1) is not None
        except Exception:
            return False

    def verify_and_repair_hooks(self) -> Dict[str, str]:
        """
        نسخهٔ ۱۰٫۷ — نوسازی سریع هوک‌ها در شروع دست جدید (نیاز صریح کاربر:
        «هوک‌های انجام‌شده را در کسری از ثانیه حذف و دوباره هوک کن»).
        برای هر ۴ هوک: امضای بایت هدف راستی‌آزمایی می‌شود؛ اگر بازی restore
        کرده بود، دوباره نصب می‌شود؛ اگر همین حال نصب است، تثبیت می‌شود.
        در انتها capture گل و مالکیت re-arm می‌شود تا اولین نوشتارِ بازیِ
        جدید ساختار تازه را capture کند.
        خروجی: گزارش وضعیت هر هوک (برای لاگ).
        """
        rep = {"ball": "skip", "time": "skip", "goal": "skip", "poss": "skip"}
        if not self.h_process or not self.base_addr:
            return {**rep, "_": "not-connected"}
        base = int(self.base_addr)

        # [suite v2.1.5] — bridge available = the bridge owns the shared
        # bytes: ball and time are status/re-request/reset THROUGH the
        # bridge; no local byte write can happen in this mode (a local
        # reinstall over a hook the bridge or the Heat Map mod owns is
        # exactly what disturbed the shared feeds).
        _bcli = getattr(self, "bridge_client", None)
        _bridge_up = (_bcli is not None and _bcli.available())

        # --- توپ: امضا E9 = هوک زندهٔ خودمان یا دیگری (پارس کِیو + پذیرش
        # بافر — v2.0.1) | ORIG = نصب مجدد ---
        if _bridge_up or getattr(self, "ball_hook_via_bridge", False):
            rep["ball"] = self.verify_ball_link()
        else:
            try:
                curr = safe_read(self.h_process, base + self.BALL_HOOK_OFFSET, 7)
                if curr is None:
                    rep["ball"] = "read-fail"
                elif curr[0] == 0xE9:
                    rel = struct.unpack('<i', curr[1:5])[0]
                    self.ball_hook_addr = base + self.BALL_HOOK_OFFSET
                    cave = self.ball_hook_addr + 5 + rel
                    data = self._resolve_ball_data_from_cave(cave)
                    if data:
                        # مالکیت: فقط وقتی کِیو همان کِیو نصب‌شدهٔ خودمان است و
                        # قبلاً پذیرفته‌نشده، هوک «مال ما» محسوب می‌شود
                        was_ours = (cave == self.ball_cave_addr
                                    and not self.ball_hook_adopted)
                        self.ball_cave_addr = cave
                        self.ball_data_addr = data
                        self.ball_hook_adopted = not was_ours
                        rep["ball"] = "ok(already)"
                    else:
                        rep["ball"] = ("reinstalled"
                                       if self._install_ball_hook(base)
                                       else "install-fail")
                elif bytes(curr) == self.BALL_ORIG_BYTES:
                    rep["ball"] = "reinstalled" if self._install_ball_hook(base) else "install-fail"
                else:
                    rep["ball"] = "signature-mismatch"
            except Exception as ex:
                rep["ball"] = f"error:{type(ex).__name__}"

        # --- زمان: ORIG ⇒ نصب مجدد | E9 ⇒ نصب مانده (خوب) ---
        if _bridge_up or getattr(self.time_hooker, "via_bridge", False):
            rep["time"] = self._bridge_verify_time_hook()
        else:
            try:
                t_t = base + TimeHooker.HOOK_OFFSET
                curr = safe_read(self.h_process, t_t, len(TimeHooker.ORIG_BYTES))
                if curr is None:
                    rep["time"] = "read-fail"
                elif bytes(curr) == TimeHooker.ORIG_BYTES:
                    try:
                        self.time_hooker.hook(self.h_process, self.base_addr)
                        rep["time"] = "reinstalled"
                    except Exception as ex:
                        rep["time"] = f"install-fail:{type(ex).__name__}"
                elif curr[0] == 0xE9:
                    rep["time"] = "ok(already)"
                else:
                    rep["time"] = "signature-mismatch"
            except Exception as ex:
                rep["time"] = f"error:{type(ex).__name__}"

        # --- گل: hook() خودش نصب‌مجدد/Adopt را هندل می‌کند + slot صفر می‌شود ---
        try:
            self.goal_hooker.hook(self.h_process, self.base_addr)
            rep["goal"] = "ok" if self.goal_hooker.is_hooked else "inactive"
        except Exception as ex:
            rep["goal"] = f"error:{type(ex).__name__}"

        # --- مالکیت (نسخهٔ ۱۰٫۱۸ — مدل «شکار آدرس»): اگر آدرس معتبر همین
        # دست قبلاً تأیید شده، دست نمی‌خوریم؛ وگرنه هوک شکار + اسلات خالی
        try:
            if self.poss_hooker.captured_address:
                rep["poss"] = "captured(already)"
            elif not self.poss_hooker.is_hooked:
                self.poss_hooker.hook(self.h_process, self.base_addr)
                self.reset_possession_capture()
                rep["poss"] = "hunting(hook-installed)"
            else:
                self.reset_possession_capture()
                rep["poss"] = "hunting(capture-cleared)"
        except Exception as ex:
            rep["poss"] = f"error:{type(ex).__name__}"

        # --- re-arm capture گل (اولین نوشتارِ گلِ دستِ جدید دوباره capture کند) ---
        try:
            self.goal_hooker.reset_capture(self.h_process)
        except Exception:
            pass
        return rep

    def _bridge_verify_time_hook(self) -> str:
        """[suite v2.1.5] — bridge-side time-hook liveness/repair. NEVER
        writes bytes itself: hook_status -> (re)request -> reset_request,
        exactly like the ball link watchdog. Covers the not-yet-granted
        case too (a hook refused at initialize is retried at every new
        half / watchdog tick until the bridge grants it)."""
        cli = getattr(self, "bridge_client", None)
        if cli is None or not cli.available():
            return "bridge-lost"
        try:
            st = cli.hook_status(TimeHooker.HOOK_OFFSET)
            if st is None:
                return "bridge-lost"
            if st.get("hooked"):
                try:
                    buf = int(st.get("buffer") or 0)
                except Exception:
                    buf = 0
                if not buf:
                    return "ok(bridge)"
                if buf != self.time_hooker.data_address:
                    self.time_hooker.data_address = buf
                    self.time_hooker.target_address = (
                        int(self.base_addr) + TimeHooker.HOOK_OFFSET)
                    self.time_hooker.is_hooked = True
                    self.time_hooker.via_bridge = True
                    self.time_hooker._bridge_cli = cli
                    self.time_hook_via_bridge = True
                    return "re-adopt(bridge)"
                return "ok(bridge)"
            buf = cli.hook_reset_request(TimeHooker.HOOK_OFFSET,
                                         TimeHooker.ORIG_BYTES, 1, kind="rsi")
            if buf:
                self.time_hooker.via_bridge = True
                self.time_hooker._bridge_cli = cli
                self.time_hooker.target_address = (
                    int(self.base_addr) + TimeHooker.HOOK_OFFSET)
                self.time_hooker.cave_address = 0
                self.time_hooker.data_address = int(buf)
                self.time_hooker.is_hooked = True
                self.time_hook_via_bridge = True
                return "reinstalled(bridge)"
            return "install-fail(bridge)"
        except Exception as ex:
            return f"error:{type(ex).__name__}"

    def _partial_cleanup(self):
        """پاک‌سازی init ناقص در صورت خطا"""
        try:
            if self.poss_hooker and self.h_process:
                self.poss_hooker.unhook(self.h_process)
        except Exception:
            pass
        try:
            if self.time_hooker and self.h_process:
                self.time_hooker.unhook(self.h_process)
        except Exception:
            pass
        try:
            if self.goal_hooker and self.h_process:
                self.goal_hooker.unhook(self.h_process)
        except Exception:
            pass
        try:
            # v2.0.1 — restore فقط وقتی مجاز است که E9 فعلی سایت به کِیو خودِ
            # ما اشاره کند؛ هوک مالک دیگر (ModBridge) هرگز خراب نمی‌شود
            # v2.0.6 — هوکِ پل: فقط مرجع‌مان را پس می‌دهیم (hook_release)؛
            # تصمیمِ بازگردانی بایت‌ها کاملاً با پل است
            if getattr(self, "ball_hook_via_bridge", False):
                if self.bridge_client is not None:
                    self.bridge_client.hook_release(self.BALL_HOOK_OFFSET)
            elif self.ball_hook_addr and self.h_process \
                    and self._ball_site_is_ours():
                safe_write(self.h_process, self.ball_hook_addr, self.BALL_ORIG_BYTES)
        except Exception:
            pass

    def read_possession(self) -> Optional[str]:
        return self.poss_hooker.read_possession_byte(self.h_process)

    def read_ball(self) -> Optional[Tuple[float, float, float]]:
        """
        تبدیل اجباری لایه دریافت:
        Raw Engine: Float0 = طولی, Float1 = ارتفاع, Float2 = عرضی
        Standard App: X = طولی, Z = عرضی, Y = ارتفاع
        """
        if not self.ball_data_addr: return None
        raw = safe_read(self.h_process, self.ball_data_addr, 12)
        if raw:
            raw_x, raw_h, raw_z = struct.unpack('<fff', raw)
            return (raw_x * ShotConfig.WORLD_TO_METER_SCALE,
                    raw_z * ShotConfig.WORLD_TO_METER_SCALE,
                    raw_h * ShotConfig.WORLD_TO_METER_SCALE)
        return None

    def read_match_state(self) -> str:
        raw = safe_read(self.h_process, int(self.base_addr) + self.MATCH_STATE_OFFSET, 1)
        if raw:
            val = struct.unpack('<B', raw)[0]
            return "PLAYING" if val in (128, 129) else "STOP"
        return "STOP"

    def read_match_time(self) -> float:
        """زمان جایگزین (Fallback) — فقط وقتی Time Hook در دسترس نباشد"""
        raw = safe_read(self.h_process, int(self.base_addr) + self.MATCH_TIME_OFFSET, 4)
        if raw:
            return max(0.0, struct.unpack('<f', raw)[0])
        return 0.0

    def read_game_clock(self) -> Tuple[float, Optional[int], Optional[int]]:
        """
        منبع واحد زمان مسابقه:
        ۱) TimeHooker (RSI+0x13C دقیقه / RSI+0x140 ثانیه)  — منبع اصلی
        ۲) MATCH_TIME_OFFSET (float)                        — فقط Fallback
        خروجی: (total_match_seconds, game_minutes, game_seconds)
        """
        regs = self.time_hooker.read_time_registers(self.h_process)
        if regs:
            minutes, seconds = regs
            return TimeHooker.compute_total_seconds(minutes, seconds), minutes, seconds
        return self.read_match_time(), None, None

    def read_pass_counter(self) -> Optional[int]:
        ptr_addr = int(self.base_addr) + self.PASS_COUNT_OFFSET
        raw_p = safe_read(self.h_process, ptr_addr, 8)
        if not raw_p: return None
        p_val = struct.unpack('<Q', raw_p)[0]
        if p_val == 0: return None
        raw_byte = safe_read(self.h_process, p_val + 0xD0, 1)
        if raw_byte:
            return struct.unpack('<B', raw_byte)[0]
        return None

    def read_shot_counter(self) -> Optional[int]:
        ptr_addr = int(self.base_addr) + self.SHOT_COUNT_PTR_OFFSET
        raw_p = safe_read(self.h_process, ptr_addr, 8)
        if not raw_p: return None
        p_val = struct.unpack('<Q', raw_p)[0]
        if p_val == 0 or p_val < 0x10000: return None

        raw_cnt = safe_read(self.h_process, p_val + self.SHOT_COUNT_FIRST_OFFSET, 4)
        if raw_cnt:
            cnt = struct.unpack('<I', raw_cnt)[0]
            if cnt < 500:
                return cnt
        return None

    def read_red_card_counter(self) -> Optional[int]:
        """
        نسخهٔ ۱۰٫۲۷ — شمارندهٔ کارت قرمز (بدون هوک — پوینتر ۳ سطحی ۶۴ بیتی):
            curr  = u64[base + 0x036F3F88]
            curr  = u64[curr + 0x350]
            value = u8 [curr + 0x4E0]
        هر «افزایش» مقدار ۱ بایتی = یک کارت قرمز صادرشده (عین نسخهٔ 2017).
        گارد ارزش: مقدار > RED_CARD_COUNTER_MAX یا پوینتر مرده → None.
        """
        if not self.is_ready:
            return None
        try:
            base = int(self.base_addr)
            raw_p = safe_read(self.h_process,
                              base + self.RED_CARD_PTR_OFFSET, 8)
            if not raw_p:
                return None
            curr = struct.unpack('<Q', raw_p)[0]
            if curr < 0x10000:
                return None
            for i, off in enumerate(self.RED_CARD_CHAIN):
                target = (curr + off) & 0xFFFFFFFFFFFFFFFF
                if i == len(self.RED_CARD_CHAIN) - 1:
                    raw_v = safe_read(self.h_process, target, 1)
                    if not raw_v:
                        return None
                    v = struct.unpack('<B', raw_v)[0]
                    if v > self.RED_CARD_COUNTER_MAX:
                        return None
                    return v
                raw_n = safe_read(self.h_process, target, 8)
                if not raw_n:
                    return None
                curr = struct.unpack('<Q', raw_n)[0]
                if curr < 0x10000:
                    return None
            return None
        except Exception:
            return None

    def read_goal_counters(self) -> Dict[str, Any]:
        """نسخه ۴ — وضعیت هوک گل + شمارنده‌های گل (Home/Away) از حافظه"""
        try:
            return self.goal_hooker.poll(self.h_process)
        except Exception:
            return {"hooked": False, "captured": False, "secondary": False,
                    "rcx": None, "home": None, "away": None}

    def reset_possession_capture(self):
        """
        نسخه ۱۰٫۴ — re-arm اسلات Capture مالکیت برای «بازی جدید».
        همان الگوی self-heal هوک گل: بازی در بازیِ جدید ساختار آمار را
        جابه‌جا می‌کند؛ capture قدیمی آدرس مرده را می‌خواند. بعد از این
        فراخوانی، اولین اجرای دستور مالکیت در بازیِ جدید آدرس تازه را
        Capture می‌کند.
        نسخهٔ ۱۰٫۱۸ — بدون هوکِ نصب‌شده، capture هرگز رخ نمی‌دهد؛ پس اگر
        هوک در حال حاضر نصب نیست (برداشته‌شده بعد از تأیید)، چرخهٔ شکار
        دوباره آغاز می‌شود (نصب هوک + اسلات خالی).
        """
        try:
            self.poss_hooker.reset_capture(self.h_process)
        except Exception:
            pass
        if self.h_process and self.base_addr and not self.poss_hooker.is_hooked:
            try:
                self.poss_hooker.hook(self.h_process, self.base_addr)
            except Exception:
                pass

    def rearm_possession_capture(self, keep_recent_sec: float = 30.0):
        """نسخهٔ ۱۰٫۱۸ — re-arm هوشمند برای «شروع دست جدید»:
        اگر آدرس مالکیت «همین چند ثانیه past» تأیید شده باشد (بعد از
        لحظهٔ صفر تایمر)، به ساختار همین بازی تعلق دارد و نباید پاک شود
        (وگرنه چند ثانیه اول بازی بدون مالکیت = نمودار خالی در دقایق ابتدایی).
        capture قدیمی/کهنه → پاک + چرخهٔ شکار دوباره."""
        ph = self.poss_hooker
        w = getattr(ph, "captured_wall", None)
        if (w is not None and not ph.is_hooked
                and (time.time() - w) <= keep_recent_sec):
            return        # capture تازهٔ همین دست — دست نخور
        self.reset_possession_capture()

    def poss_begin_capture_cycle(self) -> str:
        """نسخهٔ ۱۰٫۱۸ — آغاز چرخهٔ «شکار آدرس» مالکیت (مشخصات کاربر):
        نصب هوک + خالی‌کردن اسلات. در لحظهٔ صفر تایمر (شروع بازی جدید) و
        در اولین تیک PLAYING بعد از اتصالِ وسطِ بازی فراخوانی می‌شود.
        خروجی: گزارش کوتاه برای لاگ."""
        if not self.h_process or not self.base_addr:
            return "not-connected"
        ph = self.poss_hooker
        if ph.is_hooked:
            ph.reset_capture(self.h_process)
            return "hunting(capture-cleared)"
        try:
            ph.hook(self.h_process, self.base_addr)
            ph.reset_capture(self.h_process)
            return "hunting(hook-installed)"
        except Exception as e:
            return f"error:{type(e).__name__}:{e}"

    def debug_diagnostics(self) -> Dict[str, Any]:
        """
        نسخه ۱۰٫۴ — خواندن RAW لایهٔ داده برای لاگ تشخیصی (بدون اثر جانبی).
        همهٔ آدرس‌ها int هستند (لاگ با fmt_ptr به hex می‌رود). هدف: مقایسهٔ
        آدرس‌ها بین «بازی اول» و «بازی دوم» برای اثبات جابه‌جایی ساختارها.
          pass_ptr  → qword [base+PASS_COUNT_OFFSET]   (شمارنده: byte[ptr+0xD0])
          shot_ptr  → qword [base+SHOT_COUNT_PTR_OFFSET] (شمارنده: [ptr+0x3C])
          seat0/seat1 → دو پوینتر اول آرایهٔ بازیکنان
          state_raw → بایت خام وضعیت مسابقه
          poss_cap  → آدرس capture شدهٔ مالکیت (rdi+0x58)
        """
        out: Dict[str, Any] = {
            "pass_ptr": None, "pass_cnt": None, "pass_ptr_alive": None,
            "shot_ptr": None, "shot_cnt": None, "shot_ptr_alive": None,
            "seat0": None, "seat1": None, "players_seat0_alive": None,
            "state_raw": None, "poss_cap": None,
        }
        try:
            base = int(self.base_addr) if self.base_addr else 0
            if not base or not self.h_process:
                return out
            # --- پاس ---
            raw = safe_read(self.h_process, base + self.PASS_COUNT_OFFSET, 8)
            if raw:
                p = struct.unpack('<Q', raw)[0]
                out["pass_ptr"] = p
                if p:
                    b = safe_read(self.h_process, p + 0xD0, 1)
                    if b:
                        out["pass_cnt"] = struct.unpack('<B', b)[0]
                        out["pass_ptr_alive"] = True
                    else:
                        out["pass_ptr_alive"] = False
            # --- شوت ---
            raw = safe_read(self.h_process, base + self.SHOT_COUNT_PTR_OFFSET, 8)
            if raw:
                p = struct.unpack('<Q', raw)[0]
                out["shot_ptr"] = p
                if p and p >= 0x10000:
                    c = safe_read(self.h_process, p + self.SHOT_COUNT_FIRST_OFFSET, 4)
                    if c:
                        out["shot_cnt"] = struct.unpack('<I', c)[0]
                        out["shot_ptr_alive"] = True
                    else:
                        out["shot_ptr_alive"] = False
            # --- آرایهٔ بازیکنان (دو صندلی اول) ---
            raw0 = safe_read(self.h_process, base + self.PLAYERS_ARRAY_OFFSET, 8)
            if raw0:
                p0 = struct.unpack('<Q', raw0)[0]
                out["seat0"] = p0
                if p0:
                    out["players_seat0_alive"] = True
                    b = safe_read(self.h_process, p0 + 0x7D8, 8)
                    if b:
                        out["seat1"] = struct.unpack('<Q', b)[0]
                else:
                    out["players_seat0_alive"] = False
            # --- وضعیت مسابقه (بایت خام) ---
            raw = safe_read(self.h_process, base + self.MATCH_STATE_OFFSET, 1)
            if raw:
                out["state_raw"] = struct.unpack('<B', raw)[0]
            # --- آدرس capture مالکیت ---
            out["poss_cap"] = getattr(self.poss_hooker, "captured_address", None)
        except Exception:
            pass
        return out

    def read_players(self) -> List[Dict]:
        players = []
        base = int(self.base_addr)
        array_base = base + self.PLAYERS_ARRAY_OFFSET

        for i in range(22):
            seat_addr = array_base + (i * 8)
            p1_raw = safe_read(self.h_process, seat_addr, 8)
            if not p1_raw: continue
            p1 = struct.unpack('<Q', p1_raw)[0]
            if not p1: continue

            p2_raw = safe_read(self.h_process, p1 + 0x7D8, 8)
            if not p2_raw: continue
            p2 = struct.unpack('<Q', p2_raw)[0]
            if not p2: continue

            p3_raw = safe_read(self.h_process, p2 + 0xA08, 8)
            if not p3_raw: continue
            p3 = struct.unpack('<Q', p3_raw)[0]
            if not p3: continue

            p4_raw = safe_read(self.h_process, p3 + 0x188, 8)
            if not p4_raw: continue
            p4 = struct.unpack('<Q', p4_raw)[0]
            if not p4: continue

            raw_coords = safe_read(self.h_process, p4 + 0xD0, 12)
            if raw_coords:
                x = struct.unpack('<f', raw_coords[0:4])[0]   # طولی
                z = struct.unpack('<f', raw_coords[8:12])[0]  # عرضی
                players.append({
                    "seat": i + 1,
                    "team": "Home" if i < 11 else "Away",
                    "x": x * ShotConfig.WORLD_TO_METER_SCALE,
                    "z": z * ShotConfig.WORLD_TO_METER_SCALE
                })
        return players

    def cleanup(self):
        """Restore کامل همهٔ هوک‌ها (Ball / Possession / Time / Goal)
        (v2.0.1 — هوک توپ فقط اگر مالِ خودمان باشد restore می‌شود)
        (v2.0.6 — هوکِ پل: هیچ بایتی نوشته نمی‌شود؛ فقط hook_release)"""
        if getattr(self, "ball_hook_via_bridge", False):
            # the bridge owns the site bytes — we only drop our reference
            try:
                if self.bridge_client is not None:
                    self.bridge_client.hook_release(self.BALL_HOOK_OFFSET)
            except Exception:
                pass
        elif self.ball_hook_addr and self.h_process and self._ball_site_is_ours():
            safe_write(self.h_process, self.ball_hook_addr, self.BALL_ORIG_BYTES)
        if self.poss_hooker:
            self.poss_hooker.unhook(self.h_process)
        if self.time_hooker:
            self.time_hooker.unhook(self.h_process)
        if self.goal_hooker:
            self.goal_hooker.unhook(self.h_process)

# =====================================================================
# ۹. محاسبات هندسی یکپارچه (GeometryEngine — ادغام هر سه فایل)
# =====================================================================
