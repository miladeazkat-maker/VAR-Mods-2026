class GeometryEngine:
    @staticmethod
    def dist_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

    @staticmethod
    def dist_3d(p1: Tuple[float, float, float], p2: Tuple[float, float, float]) -> float:
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2 + (p1[2] - p2[2])**2)

    @staticmethod
    def point_to_segment_2d(pt: Tuple[float, float], a: Tuple[float, float], b: Tuple[float, float]) -> Tuple[float, float]:
        vx, vz = b[0] - a[0], b[1] - a[1]
        l_sq = vx*vx + vz*vz
        if l_sq < 1e-6: return GeometryEngine.dist_2d(pt, a), 0.0
        t = max(0.0, min(1.0, ((pt[0] - a[0])*vx + (pt[1] - a[1])*vz) / l_sq))
        proj = (a[0] + t*vx, a[1] + t*vz)
        return GeometryEngine.dist_2d(pt, proj), t

    @staticmethod
    def point_to_segment_distance(pt: Tuple[float, float], seg_start: Tuple[float, float], seg_end: Tuple[float, float]) -> Tuple[float, float, float]:
        """نسخه دارای علامت سمت (برای تشخیص پاس شکاف‌دهنده Pass Engine)"""
        vx = seg_end[0] - seg_start[0]
        vz = seg_end[1] - seg_start[1]
        length_sq = vx * vx + vz * vz
        if length_sq < 1e-6:
            return GeometryEngine.dist_2d(pt, seg_start), 0.0, 0.0

        wx = pt[0] - seg_start[0]
        wz = pt[1] - seg_start[1]
        t = max(0.0, min(1.0, (wx * vx + wz * vz) / length_sq))
        proj_x = seg_start[0] + t * vx
        proj_z = seg_start[1] + t * vz
        dist = math.hypot(pt[0] - proj_x, pt[1] - proj_z)

        cross = vx * wz - vz * wx
        side = 1.0 if cross > 0 else (-1.0 if cross < 0 else 0.0)
        return dist, t, side

    @staticmethod
    def goal_view_angle(pos_x: float, pos_z: float, goal_x: float) -> float:
        p1 = (goal_x, -PitchConfig.GOAL_HALF_WIDTH)
        p2 = (goal_x, PitchConfig.GOAL_HALF_WIDTH)
        v1x, v1z = p1[0] - pos_x, p1[1] - pos_z
        v2x, v2z = p2[0] - pos_x, p2[1] - pos_z
        d1 = math.hypot(v1x, v1z)
        d2 = math.hypot(v2x, v2z)
        if d1 < 1e-4 or d2 < 1e-4: return math.pi
        dot = (v1x * v2x + v1z * v2z) / (d1 * d2)
        dot = max(-1.0, min(1.0, dot))
        return math.acos(dot)

    @staticmethod
    def calculate_dynamic_corridor_obstruction(
        shooter_pos: Tuple[float, float],
        target_goal_x: float,
        defenders: List[Dict],
        opp_gk: Optional[Dict]
    ) -> Tuple[int, float]:
        """
        بررسی مخروط شلیک داینامیک: عرض مخروط از Shooter به تیرک‌های دروازه گسترش می‌یابد.
        (مشترک بین Shot Engine و Opportunity Engine — عرض پایه = ShotConfig.CORRIDOR_BASE_WIDTH)
        خروجی: (تعداد مدافعان مسدودکننده، زاویه انسداد)
        """
        sx, sz = shooter_pos
        angle_total = GeometryEngine.goal_view_angle(sx, sz, target_goal_x)
        if angle_total < 1e-4: return 0, 0.0

        blocked_angle_sum = 0.0
        defs_in_corridor = 0

        for d in defenders:
            if opp_gk and d["seat"] == opp_gk["seat"]:
                continue
            dx, dz = d["x"], d["z"]
            dist_to_shooter = GeometryEngine.dist_2d((sx, sz), (dx, dz))
            dist_to_goal = math.hypot(dx - target_goal_x, dz)

            # مدافع باید جلوتر از شوت‌زننده و به سمت دروازه باشد
            dist_to_path, t_prog = GeometryEngine.point_to_segment_2d((dx, dz), (sx, sz), (target_goal_x, 0.0))
            if 0.05 <= t_prog <= 0.95:
                dynamic_corridor_w = ShotConfig.CORRIDOR_BASE_WIDTH * (1.0 - t_prog) + (PitchConfig.GOAL_HALF_WIDTH * 2.0) * t_prog
                if dist_to_path <= (dynamic_corridor_w / 2.0):
                    defs_in_corridor += 1
                    # محاسبه سهم انسداد زاویه‌ای بر حسب رادیان
                    angular_width = 2.0 * math.atan2(0.5, max(0.8, dist_to_shooter))
                    blocked_angle_sum += angular_width

        obstruction_ratio = min(1.0, blocked_angle_sum / angle_total)
        return defs_in_corridor, obstruction_ratio

    @staticmethod
    def calculate_signed_woodwork_distance(z: float, y: float) -> Tuple[float, bool]:
        """
        محاسبه فاصله با تیرک در صفحه دروازه:
        - داخل چارچوب: مقدار منفی (فاصله تا نزدیک‌ترین تیرک یا تیر افقی)
        - خارج چارچوب: مقدار مثبت (فاصله تا دهانه دروازه)
        """
        in_z = abs(z) <= PitchConfig.GOAL_HALF_WIDTH
        in_y = (0.0 <= y <= PitchConfig.GOAL_HEIGHT)
        is_on_target = in_z and in_y

        if is_on_target:
            dist_left = abs(z - (-PitchConfig.GOAL_HALF_WIDTH))
            dist_right = abs(PitchConfig.GOAL_HALF_WIDTH - z)
            dist_cross = abs(PitchConfig.GOAL_HEIGHT - y)
            return -round(min(dist_left, dist_right, dist_cross), 2), True
        else:
            dz = max(0.0, abs(z) - PitchConfig.GOAL_HALF_WIDTH)
            dy = max(0.0, y - PitchConfig.GOAL_HEIGHT) if y > PitchConfig.GOAL_HEIGHT else (abs(y) if y < 0 else 0.0)
            return +round(math.hypot(dz, dy), 2), False

    @staticmethod
    def calculate_curve(trajectory: List[Tuple[float, float, float]]) -> Tuple[float, str]:
        """محاسبه کات توپ با فیلتر نویز و تعیین جهت قطعی انحراف"""
        if len(trajectory) < 6: return 0.0, "مستقیم"
        p_start = trajectory[0]
        p_end = trajectory[-1]
        tot_dist = GeometryEngine.dist_2d((p_start[0], p_start[1]), (p_end[0], p_end[1]))
        if tot_dist < ShotConfig.CURVE_MIN_TRAJECTORY_LEN: return 0.0, "مستقیم"

        vx = p_end[0] - p_start[0]
        vz = p_end[1] - p_start[1]
        deviations = []
        signed_devs = []

        for pt in trajectory[1:-1]:
            dist, _ = GeometryEngine.point_to_segment_2d((pt[0], pt[1]), (p_start[0], p_start[1]), (p_end[0], p_end[1]))
            cross = vx * (pt[1] - p_start[1]) - vz * (pt[0] - p_start[0])
            deviations.append(dist)
            signed_devs.append(cross)

        # اعمال میانگین میانه برای حذف نویز تک‌فریم
        sorted_devs = sorted(deviations)
        robust_max_dev = sorted_devs[int(len(sorted_devs) * 0.85)]
        ratio = robust_max_dev / tot_dist

        if ratio < ShotConfig.CURVE_RATIO_THRESHOLD:
            return 0.0, "مستقیم"

        sum_sign = sum(signed_devs)
        direction = "کات به راست" if sum_sign > 0 else "کات به چپ"
        return ratio, direction

# =====================================================================
# ۱۰. ساختارهای داده مدل رخداد (ادغام هر سه فایل)
# =====================================================================
class EventReliability(Enum):
    CERTAIN = "CERTAIN"      # قطعی از هوک حافظه یا مرز صریح
    PROBABLE = "PROBABLE"    # بسیار محتمل بر پایه شواهد مکانی/زمانی
    INFERRED = "INFERRED"    # استنتاجی و تحلیلی

@dataclass
class SnapshotFrame:
    timestamp: float                       # Wall Clock (فقط برای polling/performance)
    match_time: float                      # زمان بازی (منبع اصلی Momentum)
    ball: Tuple[float, float, float]
    players: List[Dict]
    possession: Optional[str]
    shot_counter: Optional[int]
    pass_counter: Optional[int]

@dataclass
class GameEvent:
    event_id: int
    event_type: str
    team: str
    timestamp: float
    match_time: float
    reliability: EventReliability
    confidence: float
    position: Tuple[float, float, float]
    related_event_ids: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

@dataclass
class PassEventData:
    """مدل کامل پاس (کالیبره Pass Engine) — threat_score منبع امتیاز Momentum"""
    event_id: int
    match_time: float
    team: str
    passer_seat: Optional[int]
    receiver_seat: Optional[int]
    pass_type: str
    confidence: float
    threat_score: int
    is_success: bool
    start_ball: Tuple[float, float, float]
    end_ball: Tuple[float, float, float]
    passer_pos: Tuple[float, float]
    receiver_start: Tuple[float, float]
    receiver_end: Tuple[float, float]
    distance: float
    forward_progress: float
    lateral_progress: float
    max_height: float
    flight_time: float
    tags: List[str] = field(default_factory=list)

@dataclass
class PreviousShotContext:
    timestamp: float
    end_position: Tuple[float, float, float]
    team: str
    outcome: str
    target_goal_x: float

@dataclass
class ShotEventData:
    """مدل کامل شوت (کالیبره Shot Engine) — pre_shot_threat و final_threat تفکیک‌شده"""
    event_id: int
    match_time: float
    team: str
    shooter_seat: Optional[int]
    primary_type: str
    confidence: float
    pre_shot_threat: int
    final_threat: int

    max_speed_kmh: Optional[float]
    speed_valid: bool
    initial_height: float
    max_height: float
    curve_ratio: float
    curve_dir: str

    is_on_target: bool
    outcome: str
    woodwork_distance: float
    block_distance: float

    shooter_pos: Tuple[float, float]
    contact_ball: Tuple[float, float, float]
    goal_line_intersection: Tuple[float, float, float]

    distance_to_goal: float
    goal_angle_deg: float
    defenders_in_corridor: int
    nearest_defender_dist: float
    gk_dist_to_goal: float
    is_inside_box: bool
    is_1v1: bool
    # --- نسخه ۳ (رفع باگ بحرانی): پرچم گل روی مدل داده —
    # register_shot_event به shot_data.is_goal دسترسی دارد؛ نبودِ این فیلد
    # در نسخه ۲ باعث AttributeError و «حذف بی‌صدای همهٔ شوت‌ها» می‌شد
    is_goal: bool = False
    # --- نسخهٔ ۱۰٫۱۴ — شناسهٔ یکتای کاندید شوت (= مقدار شمارنده + نسل)؛
    # مبنای Dedup: «همان کاندید فقط یک بار ثبت می‌شود» — شوت‌های واقعیِ
    # پشت‌سرهم هرگز با این گارد حذف نمی‌شوند
    candidate_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    candidate_scores: Dict[str, float] = field(default_factory=dict)

@dataclass
class PossessionSequence:
    seq_id: int
    team: str
    start_time: float
    end_time: Optional[float]
    duration: float
    start_ball_x: float
    max_ball_x: float
    territorial_gain: float
    pass_count: int
    shot_count: int
    final_third_entries: int
    box_entries: int
    chances_created: int
    ending_reason: str = "Active"
    is_active: bool = True

@dataclass
class EventImpact:
    """
    رکورد مرکزی امتیاز Momentum برای هر Event
    (score خام و sign جدا نگه داشته می‌شوند)
    """
    source_event_id: int
    event_type: str
    team: str
    match_time: float
    raw_threat: float            # ورودی خام (threat_score پاس / final_threat شوت / وزن رخداد)
    base_weight: float           # پس از multiplierهای نوع رویداد (قبل از reliability/confidence)
    reliability: str
    confidence: float
    reliability_multiplier: float
    sign: int                    # +1 عادی / -1 برای Penalty Miss (مدل داخلی جدا نگه داشته می‌شود)
    final_impact: float          # base_weight × rel_mult × confidence × sign  (امضادار)
    note: str = ""
    # --- Goal Pulse (نسخه ۲) ---
    # گل به‌جای spike لحظه‌ای، پاسخ تأخیری دارد: اوج در goal_time + GOAL_PEAK_DELAY
    is_goal_pulse: bool = False
    goal_time: float = 0.0       # t_goal (ثانیه بازی) — مارکر گل دقیقاً اینجاست
    peak_time: float = 0.0       # t_goal + GOAL_PEAK_DELAY (ثانیه بازی)
    # --- نسخه ۵: نیمهٔ گل + موقعیت نمایشی فریزشدهٔ مارکر ---
    # goal_disp_time در لحظهٔ ثبت با display_offset جاری محاسبه و فریز
    # می‌شود؛ حتی اگر بعداً آفست نمایش تغییر کند، مارکر دقیقاً روی
    # موقعیت درست خودش می‌ماند (رفع جابه‌جایی مارکر گل نیمه دوم نسخه ۴)
    goal_half: int = 1
    goal_disp_time: float = -1.0
    # --- Debug / Dedup ---
    linked_ids: List[int] = field(default_factory=list)   # related_event_ids هنگام امتیازدهی
    parallel_goal_dedup: bool = False                     # Penalty Goal که به Goal موازی تنزیل یافته

# =====================================================================
# ۱۱. باس رویداد یکپارچه (Unified Event Bus)
# =====================================================================
class EventBus:
    """Event Stream مشترک: Event Engine منتشر می‌کند، Momentum Engine مصرف"""
    def __init__(self):
        self._subscribers: List[Any] = []
        self._lock = threading.RLock()

    def subscribe(self, callback):
        with self._lock:
            self._subscribers.append(callback)

    def publish(self, event: GameEvent):
        with self._lock:
            subs = list(self._subscribers)
        for cb in subs:
            try:
                cb(event)
            except Exception as ex:
                clog(f"[EventBus] Subscriber error: {ex}")

# =====================================================================
# ۱۲. Data Store داخلی RuntimeState (Worker → RuntimeState → UI snapshot)
# =====================================================================
class RuntimeState:
    def __init__(self):
        self._lock = threading.RLock()
        self.match_state: str = "STOP"
        self.current_match_time: float = 0.0
        self.game_minute: Optional[int] = None
        self.game_second: Optional[int] = None
        self.time_source: str = "FALLBACK"
        self.current_possession: Optional[str] = None
        self.last_time_change_wall: float = 0.0
        self.poll_rate_ms: float = 0.0
        self.connected: bool = False
        self.last_pass: Optional[PassEventData] = None
        self.last_shot: Optional[ShotEventData] = None
        # ارجاع به لیست‌های append-only (خواندن امن از UI بدون کپی سنگین)
        self.events: List[GameEvent] = []
        self.sequences: List[PossessionSequence] = []
        self.momentum_history: List[Dict[str, float]] = []

    def update_core(self, match_state: str, match_time: float,
                    game_minute: Optional[int], game_second: Optional[int],
                    possession: Optional[str], poll_rate_ms: float):
        with self._lock:
            if match_time != self.current_match_time:
                self.last_time_change_wall = time.time()
            self.match_state = match_state
            self.current_match_time = match_time
            self.game_minute = game_minute
            self.game_second = game_second
            self.time_source = "HOOK" if game_minute is not None else "FALLBACK"
            if possession:
                self.current_possession = possession
            self.poll_rate_ms = poll_rate_ms

    def set_pass(self, p: PassEventData):
        with self._lock:
            self.last_pass = p

    def set_shot(self, s: ShotEventData):
        with self._lock:
            self.last_shot = s

    def get_core(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "match_state": self.match_state,
                "current_match_time": self.current_match_time,
                "game_minute": self.game_minute,
                "game_second": self.game_second,
                "time_source": self.time_source,
                "current_possession": self.current_possession,
                "last_time_change_wall": self.last_time_change_wall,
                "poll_rate_ms": self.poll_rate_ms,
            }

    def reset(self):
        with self._lock:
            self.match_state = "STOP"
            self.current_match_time = 0.0
            self.game_minute = None
            self.game_second = None
            self.current_possession = None
            self.last_pass = None
            self.last_shot = None

# =====================================================================
# ۱۳. موتور کالیبره‌شده شاخص تهدید پاس (PassThreatEngine)
# ---------------------------------------------------------------------
# منطق تست‌شده ThreatCalculator فایل Pass Engine — بدون هیچ تغییری.
# این کلاس تنها منبع امتیاز Threat برای رویداد Pass است.
# =====================================================================
