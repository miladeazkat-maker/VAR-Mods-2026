class PassThreatEngine:
    @staticmethod
    def calculate_pass_threat(
        receiver_pos: Tuple[float, float],
        defenders: List[Dict],
        att_dir: int,
        pass_type: str
    ) -> int:
        target_goal_x = PitchConfig.HALF_LENGTH * att_dir
        rx, rz = receiver_pos

        dist_to_goal = math.hypot(rx - target_goal_x, rz)
        goal_angle = GeometryEngine.goal_view_angle(rx, rz, target_goal_x)

        opp_gk = None
        for d in defenders:
            if d["seat"] in (1, 12):
                opp_gk = d
                break

        # مدافعان روبروی گیرنده (بین گیرنده و خط دروازه)
        outfield_defs_ahead = 0
        for d in defenders:
            if opp_gk and d["seat"] == opp_gk["seat"]:
                continue
            d_x_att = d["x"] * att_dir
            r_x_att = rx * att_dir
            if d_x_att > r_x_att and abs(d["z"] - rz) <= (abs(target_goal_x - rx) * 0.45 + 5.0):
                outfield_defs_ahead += 1

        rec_def_dists = sorted([GeometryEngine.dist_2d((rx, rz), (d["x"], d["z"])) for d in defenders]) if defenders else [25.0]
        near_def_dist = rec_def_dists[0]

        # شرط دروازه خالی (Open Goal) -> تهدید ۱۰۰
        is_open_goal = False
        if dist_to_goal <= 16.5 and abs(rz) <= 12.0:
            if outfield_defs_ahead == 0:
                if opp_gk:
                    gk_dist_to_goal = math.hypot(opp_gk["x"] - target_goal_x, opp_gk["z"])
                    gk_x_att = opp_gk["x"] * att_dir
                    r_x_att = rx * att_dir
                    if r_x_att > gk_x_att or gk_dist_to_goal > (dist_to_goal + 4.0) or abs(opp_gk["z"]) > 4.5:
                        is_open_goal = True
                else:
                    is_open_goal = True

        if is_open_goal:
            return 100

        # موقعیت تک به تک مستقیم
        if outfield_defs_ahead == 0 and dist_to_goal <= 22.0 and abs(rz) <= 14.0:
            base_1v1 = 90.0 + (22.0 - dist_to_goal) * 0.4
            if near_def_dist >= 3.0: base_1v1 += 5.0
            return int(min(98, max(88, base_1v1)))

        norm_dist = max(0.0, min(1.0, dist_to_goal / PitchConfig.FIELD_LENGTH))
        proximity_score = ((1.0 - norm_dist) ** 1.8) * 58.0
        angle_score = min(22.0, (goal_angle / 0.80) * 22.0)

        if outfield_defs_ahead == 0: def_ahead_penalty = +15.0
        elif outfield_defs_ahead == 1: def_ahead_penalty = +8.0
        elif outfield_defs_ahead == 2: def_ahead_penalty = 0.0
        elif outfield_defs_ahead == 3: def_ahead_penalty = -10.0
        else: def_ahead_penalty = -22.0

        space_bonus = min(12.0, (near_def_dist / 4.0) * 12.0)
        if near_def_dist < 1.2: space_bonus -= 8.0

        tactical_bonus = 0.0
        if pass_type == "کات‌بک": tactical_bonus = 18.0
        elif pass_type in ("پاس در عمق بین مدافعان", "پاس پشت مدافعان"): tactical_bonus = 15.0
        elif pass_type in ("سانتر زمینی", "سانتر هوایی", "پاس عمقی"): tactical_bonus = 12.0

        raw_threat = proximity_score + angle_score + def_ahead_penalty + space_bonus + tactical_bonus
        if dist_to_goal > 60.0: raw_threat = min(raw_threat, 18.0)

        return int(max(2.0, min(99.0, raw_threat)))

# محدود کردن Threat به بازه 2 تا 99 در تابع بالا حفظ شده است.

# =====================================================================
# ۱۴. طبقه‌بندی هوشمند پاس (PassClassifierEngine — کالیبره، دست‌نخورده)
# =====================================================================
class PassClassifierEngine:
    @staticmethod
    def classify(features: Dict) -> Tuple[str, float, List[str]]:
        scores: Dict[str, float] = {}

        dist = features["dist"]
        fwd = features["fwd"]
        lat = features["lat"]
        max_h = features["max_h"]
        angle = features["angle_deg"]

        s_x = features["start_x"]
        s_z = features["start_z"]
        e_x = features["end_x"]
        e_z = features["end_z"]
        att_dir = features["att_dir"]

        start_x_att = s_x * att_dir
        end_x_att = e_x * att_dir

        receiver_target_err = features["receiver_target_err"]
        receiver_fwd_run = features["receiver_fwd_run"]
        running_to_space = features["running_to_space"]

        is_split_corridor = features["is_split_corridor"]
        behind_def_line = features["behind_def_line"]
        pressure_relief = features["pressure_relief"]

        # -------------------------------------------------------------
        # ۱. سانتر (Cross):
        # شرط قطعی: فقط در زمین حریف (start_x_att > 0)
        # مختصات مبدا: |Z| > 20.1 و |X| > 29.0
        # جهت ارسال: به سمت دروازه حریف و رو به عمق/محوطه
        # بدون بررسی سرعت! تفکیک زمینی و هوایی بر اساس ارتفاع
        # -------------------------------------------------------------
        is_cross_origin = (
            start_x_att > 0 and
            abs(s_x) > PitchConfig.CROSS_LONGITUDINAL_THRESHOLD and
            abs(s_z) > PitchConfig.CROSS_LATERAL_THRESHOLD
        )
        is_moving_towards_goal = (end_x_att > start_x_att) or (abs(e_z) < abs(s_z) and end_x_att >= 28.0)
        is_cross_geo = is_cross_origin and is_moving_towards_goal

        if is_cross_geo:
            if max_h >= PitchConfig.HEIGHT_AERIAL_MIN:
                scores["سانتر هوایی"] = 96.0
            elif max_h <= PitchConfig.HEIGHT_GROUND_MAX:
                scores["سانتر زمینی"] = 96.0
            else:
                scores["سانتر هوایی"] = 90.0

        # -------------------------------------------------------------
        # ۲. کات‌بک (Cut-back):
        # شرط قطعی: فقط در زمین حریف (start_x_att > 0)
        # مختصات مبدا: |X| > 35.0
        # ارتفاع: کمتر از 1.8 متر
        # طولی: X توپ به صفر نزدیک شود (حرکت رو به عقب نسبت به دروازه حریف)
        # بدون بررسی سرعت!
        # -------------------------------------------------------------
        is_cutback_origin = (start_x_att > 0 and abs(s_x) > PitchConfig.CUTBACK_ORIGIN_X_THRESHOLD)
        is_x_towards_zero = (abs(e_x) < abs(s_x)) and (fwd <= 0.5)
        is_cutback_height = (max_h < PitchConfig.CUTBACK_MAX_HEIGHT)

        if is_cutback_origin and is_x_towards_zero and is_cutback_height:
            scores["کات‌بک"] = 98.0

        # -------------------------------------------------------------
        # ۳. پاس خروج از فشار (Pressure Exit):
        # فقط در زمین خودی (start_x_att < 0) و نه در زمین حریف
        # -------------------------------------------------------------
        is_in_own_half = (start_x_att < 0.0)
        if is_in_own_half and features["passer_under_pressure"] and pressure_relief >= 2.5:
            scores["پاس خروج از فشار"] = 82.0 + pressure_relief * 3.0

        # -------------------------------------------------------------
        # ۴. پاس پشت مدافعان (Over-the-Top):
        # ارتفاع بالا (شبیه چیپ)، فرود پشت سر مدافعان
        # -------------------------------------------------------------
        is_behind_defense = behind_def_line or (end_x_att > features["def_line_x_att"])
        if max_h >= 1.55 and is_behind_defense and fwd >= 6.0:
            scores["پاس پشت مدافعان"] = 88.0 + max_h * 4.0

        # -------------------------------------------------------------
        # ۵. پاس در عمق بین مدافعان
        # -------------------------------------------------------------
        if fwd >= 7.0 and is_split_corridor and (behind_def_line or receiver_fwd_run >= 3.0):
            scores["پاس در عمق بین مدافعان"] = 87.0 + fwd * 1.2

        # -------------------------------------------------------------
        # ۶. پاس شکاف‌دهنده
        # -------------------------------------------------------------
        if fwd >= 4.5 and is_split_corridor and "پاس در عمق بین مدافعان" not in scores:
            scores["پاس شکاف‌دهنده"] = 78.0 + fwd * 1.0

        # -------------------------------------------------------------
        # ۷. پاس عمقی (Through Ball):
        # مقصد توپ جلوتر از بازیکن باشد و مستقیم به پای بازیکن ارسال نشود
        # -------------------------------------------------------------
        ball_lead_dist = (e_x - features["receiver_start_x"]) * att_dir
        is_lead_pass = (ball_lead_dist >= 3.5 and receiver_target_err >= 3.0)
        if fwd >= 8.0 and is_lead_pass and (running_to_space or receiver_fwd_run >= 2.5):
            scores["پاس عمقی"] = 79.0 + fwd * 1.1

        # -------------------------------------------------------------
        # ۸. تعویض جناح (Switch of Play)
        # -------------------------------------------------------------
        crosses_center_z = (s_z * e_z < 0) and (abs(s_z) >= 12.0 or abs(e_z) >= 12.0)
        if lat >= 26.0 and dist >= 26.0 and crosses_center_z:
            scores["تعویض جناح"] = 84.0 + lat * 0.5

        # -------------------------------------------------------------
        # ۹. پاس بین خطوط
        # -------------------------------------------------------------
        if 4.0 <= fwd <= 20.0 and features["receiver_between_lines"] and not behind_def_line:
            scores["پاس بین خطوط"] = 74.0 + fwd * 0.8

        # ۱۰. چیپ
        if max_h >= 1.50 and dist <= 20.0 and (max_h / max(1.0, dist)) >= 0.09:
            scores["چیپ"] = 70.0 + max_h * 5.0

        # ۱۱. پاس به فضا
        if receiver_target_err >= 4.0 and running_to_space:
            scores["پاس به فضا"] = 69.0 + receiver_target_err * 2.0

        # ۱۲. انواع عمومی
        if dist >= 30.0: scores["پاس بلند"] = 62.0 + dist * 0.5
        if max_h >= PitchConfig.HEIGHT_AERIAL_MIN and dist >= 14.0: scores["پاس هوایی"] = 60.0 + max_h * 4.0
        if fwd <= -3.0: scores["پاس رو به عقب"] = 55.0 + abs(fwd) * 2.0
        if lat >= 10.0 and abs(fwd) <= 5.0: scores["پاس عرضی"] = 52.0 + lat * 1.5
        if fwd >= 4.5 and lat >= 7.0 and 25.0 <= angle <= 68.0: scores["پاس مورب"] = 50.0 + fwd
        if fwd >= 4.0: scores["پاس رو به جلو"] = 48.0 + fwd * 1.5
        if dist <= 14.0 and max_h <= PitchConfig.HEIGHT_GROUND_MAX + 0.3: scores["پاس کوتاه"] = 56.0 + (14.0 - dist) * 1.5

        # ماتریس تقدم
        priority = [
            "کات‌بک",
            "سانتر هوایی",
            "سانتر زمینی",
            "پاس پشت مدافعان",
            "پاس در عمق بین مدافعان",
            "تعویض جناح",
            "پاس شکاف‌دهنده",
            "پاس عمقی",
            "پاس خروج از فشار",
            "پاس بین خطوط",
            "چیپ",
            "پاس به فضا",
            "پاس بلند",
            "پاس هوایی",
            "پاس مورب",
            "پاس رو به عقب",
            "پاس عرضی",
            "پاس رو به جلو",
            "پاس کوتاه"
        ]

        valid_candidates = {k: v for k, v in scores.items() if v > 0.0}
        if not valid_candidates:
            if dist >= 28.0: final_type = "پاس بلند"
            elif fwd <= -3.0: final_type = "پاس رو به عقب"
            elif lat >= 10.0: final_type = "پاس عرضی"
            elif fwd >= 4.0: final_type = "پاس رو به جلو"
            elif lat >= 6.0: final_type = "پاس مورب"
            else: final_type = "پاس کوتاه"
            confidence = 0.60
        else:
            sorted_candidates = sorted(valid_candidates.items(), key=lambda x: x[1], reverse=True)
            top_type, top_score = sorted_candidates[0]

            for p_type in priority:
                if p_type in valid_candidates and valid_candidates[p_type] >= (top_score - 8.0):
                    top_type = p_type
                    top_score = valid_candidates[p_type]
                    break

            final_type = top_type
            second_score = sorted_candidates[1][1] if len(sorted_candidates) > 1 else 0.0
            confidence = min(0.98, max(0.55, 0.60 + (top_score - second_score) * 0.015))

        tags = []
        if max_h >= PitchConfig.HEIGHT_AERIAL_MIN: tags.append("هوایی")
        if fwd >= 6.0: tags.append("رو به جلو")
        if is_behind_defense: tags.append("پشت دفاع")
        if running_to_space: tags.append("به فضا")

        return final_type, confidence, tags

# =====================================================================
# ۱۵. Pass Engine (موتور تولید رویداد پاس — استخراج‌شده از نسخه کالیبره)
# ---------------------------------------------------------------------
# شروع/پایان پاس از Frame Buffer، تشخیص Pass Type، موفق/ناموفق،
# و محاسبه threat_score توسط PassThreatEngine. خروجی: PassEventData کامل.
# Counter فقط Trigger شروع است؛ هیچ‌جا نوع پاس حدس زده نمی‌شود.
# =====================================================================
class PassEngine:
    def __init__(self):
        self.state = "IDLE"  # IDLE | IN_FLIGHT
        self.cur_pass_team = "Home"
        self.cur_pass_start_ball: Optional[Tuple[float, float, float]] = None
        self.cur_pass_start_time = 0.0      # wall (زیرثانیه — برای فیزیک پرواز/polling)
        self.cur_pass_match_time = 0.0      # زمان بازی
        self.cur_pass_max_h = 0.0
        self.cur_passer: Optional[Dict] = None
        self.cur_receiver_start: Optional[Dict] = None

    def reset(self):
        self.state = "IDLE"
        self.cur_pass_start_ball = None
        self.cur_passer = None
        self.cur_receiver_start = None
        self.cur_pass_max_h = 0.0

    def abort(self):
        """در توقف بازی، پرواز جاری بدون تولید رخداد رها می‌شود"""
        self.state = "IDLE"

    def on_counter_increment(self, ball: Tuple[float, float, float], wall_now: float,
                             match_time: float, team: str, players: List[Dict]):
        """Counter فقط Trigger شروع فرآیند تشخیص است"""
        if self.state == "IN_FLIGHT":
            return  # پاس جاری هنوز در جریان است
        self.state = "IN_FLIGHT"
        self.cur_pass_start_ball = (ball[0], ball[1], ball[2])
        self.cur_pass_start_time = wall_now
        self.cur_pass_match_time = match_time
        self.cur_pass_max_h = ball[2]
        self.cur_pass_team = team

        attackers = [p for p in players if p["team"] == team]
        self.cur_passer, _ = closest_player(ball[0], ball[1], attackers)

        other_attackers = [p for p in attackers if p["seat"] != (self.cur_passer["seat"] if self.cur_passer else -1)]
        self.cur_receiver_start, _ = closest_player(ball[0], ball[1], other_attackers)

    def generate_event(self, ball: Tuple[float, float, float], match_time: float,
                       players: List[Dict], team1_attack_dir: int,
                       possession_provider=None) -> Optional[PassEventData]:
        """به‌روزرسانی پرواز پاس از Frame Buffer و تولید PassEventData در پایان"""
        if self.state != "IN_FLIGHT":
            return None

        bx, bz, by = ball
        if by > self.cur_pass_max_h:
            self.cur_pass_max_h = by

        flight_t = max(0.05, time.time() - self.cur_pass_start_time)
        dist_traveled = math.hypot(bx - self.cur_pass_start_ball[0], bz - self.cur_pass_start_ball[1])

        closest_p, min_d = closest_player(bx, bz, players)

        is_received = (min_d <= 1.85 and dist_traveled >= 2.0 and flight_t >= 0.12)
        is_timeout = (flight_t >= 3.2)

        if not (is_received or is_timeout):
            return None

        self.state = "IDLE"
        passing_team = self.cur_pass_team
        att_dir = team1_attack_dir if passing_team == "Home" else -team1_attack_dir

        attackers = [p for p in players if p["team"] == passing_team]
        defenders = [p for p in players if p["team"] != passing_team]

        s_x, s_z, s_y = self.cur_pass_start_ball
        e_x, e_z, e_y = bx, bz, by

        receiver_end_player, _ = closest_player(e_x, e_z, attackers)
        r_end_x = receiver_end_player["x"] if receiver_end_player else e_x
        r_end_z = receiver_end_player["z"] if receiver_end_player else e_z

        r_start_x = self.cur_receiver_start["x"] if self.cur_receiver_start else s_x
        r_start_z = self.cur_receiver_start["z"] if self.cur_receiver_start else s_z

        seg_start = (s_x, s_z)
        seg_end = (e_x, e_z)
        left_def = 0
        right_def = 0

        for d in defenders:
            d_pt = (d["x"], d["z"])
            dist_seg, t_prog, side = GeometryEngine.point_to_segment_distance(d_pt, seg_start, seg_end)
            if dist_seg <= 3.5 and 0.15 <= t_prog <= 0.85:
                if side > 0: left_def += 1
                elif side < 0: right_def += 1

        is_split = (left_def >= 1 and right_def >= 1)

        defs_x_att = sorted([d["x"] * att_dir for d in defenders]) if defenders else [30.0]
        def_line_x_att = defs_x_att[-2] if len(defs_x_att) >= 2 else 36.0

        rec_disp = math.hypot(r_end_x - r_start_x, r_end_z - r_start_z)
        rec_fwd_run = (r_end_x - r_start_x) * att_dir
        rec_target_err = math.hypot(e_x - r_start_x, e_z - r_start_z)

        run_vx = r_end_x - r_start_x
        run_vz = r_end_z - r_start_z
        dot_run = (run_vx * (e_x - r_start_x) + run_vz * (e_z - r_start_z))
        running_to_space = (dot_run > 0.5 and rec_disp >= 2.5)

        passer_x = self.cur_passer["x"] if self.cur_passer else s_x
        passer_z = self.cur_passer["z"] if self.cur_passer else s_z

        p_near = min([GeometryEngine.dist_2d((passer_x, passer_z), (d["x"], d["z"])) for d in defenders]) if defenders else 10.0
        r_near = min([GeometryEngine.dist_2d((r_end_x, r_end_z), (d["x"], d["z"])) for d in defenders]) if defenders else 10.0

        features = {
            "dist": dist_traveled,
            "fwd": (e_x - s_x) * att_dir,
            "lat": abs(e_z - s_z),
            "max_h": self.cur_pass_max_h,
            "angle_deg": math.degrees(math.atan2(abs(e_z - s_z), max(0.001, abs((e_x - s_x) * att_dir)))),
            "start_x": s_x,
            "start_z": s_z,
            "end_x": e_x,
            "end_z": e_z,
            "att_dir": att_dir,
            "receiver_start_x": r_start_x,
            "receiver_start_z": r_start_z,
            "receiver_target_err": rec_target_err,
            "receiver_fwd_run": rec_fwd_run,
            "running_to_space": running_to_space,
            "is_split_corridor": is_split,
            "behind_def_line": (e_x * att_dir) > def_line_x_att,
            "def_line_x_att": def_line_x_att,
            "receiver_between_lines": (17.5 <= (r_end_x * att_dir) <= def_line_x_att),
            "passer_under_pressure": (p_near <= 2.2),
            "pressure_relief": (r_near - p_near)
        }

        p_type, conf, tags = PassClassifierEngine.classify(features)

        # Threat Score فعلی — منبع امتیاز Pass برای Momentum (بدون تغییر مفهومی)
        threat = PassThreatEngine.calculate_pass_threat(
            receiver_pos=(r_end_x, r_end_z),
            defenders=defenders,
            att_dir=att_dir,
            pass_type=p_type
        )

        new_poss = possession_provider() if possession_provider else None
        is_success = (new_poss == passing_team) if new_poss else is_received

        event_data = PassEventData(
            event_id=0,  # در لحظه ثبت توسط EventDetectionEngine تخصیص می‌یابد
            match_time=self.cur_pass_match_time,
            team=passing_team,
            passer_seat=self.cur_passer["seat"] if self.cur_passer else None,
            receiver_seat=receiver_end_player["seat"] if receiver_end_player else None,
            pass_type=p_type,
            confidence=conf,
            threat_score=threat,
            is_success=is_success,
            start_ball=(s_x, s_z, s_y),
            end_ball=(e_x, e_z, e_y),
            passer_pos=(passer_x, passer_z),
            receiver_start=(r_start_x, r_start_z),
            receiver_end=(r_end_x, r_end_z),
            distance=dist_traveled,
            forward_progress=features["fwd"],
            lateral_progress=features["lat"],
            max_height=self.cur_pass_max_h,
            flight_time=flight_t,
            tags=tags
        )
        return event_data

# =====================================================================
# ۱۶. موتور تهدید شوت (ShotThreatEngine — کالیبره، دست‌نخورده)
# ---------------------------------------------------------------------
# تفکیک کامل: موقعیت خام (Pre-Shot Opportunity Value) در برابر
# تحقق نهایی (Final Threat = Event / Momentum Impact)
# =====================================================================
class ShotThreatEngine:
    @staticmethod
    def calculate_pre_shot_threat(
        dist_to_goal: float,
        goal_angle_rad: float,
        corridor_defs: int,
        obstruction_ratio: float,
        nearest_def_dist: float,
        opp_gk: Optional[Dict],
        target_goal_x: float,
        shooter_z: float,
        is_inside_box: bool,
        is_1v1: bool
    ) -> int:
        """محاسبه ارزش ذاتی موقعیت شوت قبل از ضربه (Pre-shot Opportunity Value)"""
        norm_dist = max(0.0, min(1.0, dist_to_goal / 48.0))
        # اثر غیرخطی فاصله تا دروازه
        proximity_score = ((1.0 - norm_dist) ** 2.0) * 52.0

        # اثر زاویه دهانه دروازه
        angle_deg = math.degrees(goal_angle_rad)
        angle_score = min(24.0, (angle_deg / 34.0) * 24.0)

        # جریمه مدافعان بر اساس انسداد مخروط شلیک
        def_penalty = -(obstruction_ratio * 26.0)
        if corridor_defs == 0: def_penalty += 8.0

        # فشار نزدیک‌ترین مدافع
        if nearest_def_dist < 1.0: space_bonus = -12.0
        elif nearest_def_dist < 2.0: space_bonus = -5.0
        elif nearest_def_dist >= 4.0: space_bonus = +8.0
        else: space_bonus = +2.0

        # فاکتور دروازه‌بان (زاویه و فاصله از خط)
        gk_bonus = 0.0
        is_open_goal = False
        if opp_gk:
            gk_x, gk_z = opp_gk["x"], opp_gk["z"]
            gk_off_line = abs(gk_x - target_goal_x)
            gk_lat_offset = abs(gk_z)

            if gk_off_line > 4.5 or gk_lat_offset > 3.8:
                gk_bonus += 12.0 # دروازه‌بان از چارچوب خارج است

            # بررسی حالت دروازه خالی (Open Goal)
            if dist_to_goal <= 16.5 and corridor_defs == 0:
                if gk_off_line > 5.0 or gk_lat_offset > 4.2 or (abs(sx_from_gk := abs(opp_gk["x"] - target_goal_x)) < dist_to_goal - 2.0):
                    is_open_goal = True
        else:
            if dist_to_goal <= 16.5 and corridor_defs == 0: is_open_goal = True

        if is_open_goal:
            return 98

        if is_1v1:
            base_1v1 = 86.0 + max(0.0, (18.0 - dist_to_goal) * 0.5)
            if nearest_def_dist >= 3.0: base_1v1 += 5.0
            return int(min(97, max(85, base_1v1)))

        box_bonus = 6.0 if is_inside_box else -6.0
        raw_pre = proximity_score + angle_score + def_penalty + space_bonus + gk_bonus + box_bonus

        return int(max(5.0, min(95.0, raw_pre)))

    @staticmethod
    def calculate_final_threat(
        pre_shot_threat: int,
        outcome: str,
        is_on_target: bool,
        woodwork_dist: float,
        speed_kmh: Optional[float],
        block_dist: float
    ) -> int:
        """محاسبه تهدید نهایی پس از مشخص شدن فرجام شوت"""
        # گل = ۱۰۰ قطعی
        if "گل" in outcome:
            return 100

        # برخورد به تیرک
        if "تیرک" in outcome:
            speed_factor = min(4.0, (speed_kmh / 30.0)) if speed_kmh else 2.0
            if "بازگشت به زمین" in outcome:
                return int(min(98, 93.0 + speed_factor))
            else:
                return int(min(94, 88.0 + speed_factor))

        speed_mod = 0.0
        if speed_kmh and speed_kmh >= 75.0:
            speed_mod = min(8.0, (speed_kmh - 75.0) * 0.15)

        # مهار یا بلوک
        if "مهار توسط دروازه‌بان" in outcome:
            if is_on_target:
                # مهار در فاصله نزدیک به خط ارزش فوق‌العاده‌ای دارد
                close_boost = max(10.0, (22.0 - block_dist) * 1.0)
                return int(max(65, min(94, pre_shot_threat * 0.75 + close_boost + speed_mod)))
            return int(max(30, min(65, pre_shot_threat * 0.6)))

        if "بلوک توسط مدافع" in outcome:
            if is_on_target:
                if block_dist <= 3.0: return 95 # نجات از روی خط
                return int(max(55, min(88, pre_shot_threat * 0.70 + speed_mod)))
            return int(max(25, min(60, pre_shot_threat * 0.5)))

        # خارج از چارچوب
        if "خارج از چارچوب" in outcome:
            if woodwork_dist <= 0.8: # مماس با تیرک
                return int(max(40, min(75, pre_shot_threat * 0.85)))
            elif woodwork_dist <= 2.2:
                return int(max(20, min(50, pre_shot_threat * 0.50)))
            else:
                return int(max(5, min(30, pre_shot_threat * 0.25)))

        return pre_shot_threat

# =====================================================================
# ۱۷. طبقه‌بندی هوشمند شوت (ShotClassifierEngine — کالیبره، دست‌نخورده)
# =====================================================================
class ShotClassifierEngine:
    @staticmethod
    def classify(features: Dict) -> Tuple[str, float, List[str], Dict[str, float]]:
        scores: Dict[str, float] = {}

        dist = features["dist_to_goal"]
        angle_deg = features["goal_angle_deg"]
        s_z = features["shooter_z"]
        init_h = features["initial_height"]
        max_h = features["max_height"]
        curve_ratio = features["curve_ratio"]
        in_box = features["is_inside_box"]
        is_1v1 = features["is_1v1"]
        is_rebound = features["is_rebound"]
        stationary_time = features["stationary_duration"]
        is_pen_spot = features["is_penalty_spot"]
        other_players_clear = features["other_players_clear_of_box"]
        prior_aerial = features["prior_ball_aerial"]
        ball_descending = features["ball_descending"]
        control_time = features["shooter_control_time"]

        # ۱. پنالتی: شرایط سخت‌گیرانه آرایش زمین
        if is_pen_spot and in_box and stationary_time >= ShotConfig.STATIONARY_DURATION_MIN and other_players_clear:
            scores["پنالتی"] = 96.0

        # ۲. شوت روی ریباند
        if is_rebound:
            scores["شوت روی ریباند"] = 92.0

        # ۳. ضربه آزاد مستقیم
        if stationary_time >= ShotConfig.STATIONARY_DURATION_MIN and not is_pen_spot and dist >= 16.0:
            scores["ضربه آزاد"] = 85.0 + min(10.0, stationary_time * 2.0)

        # ۴. ضربه سر: احتمالاتی بر پایه شواهد فیزیکی
        if init_h >= ShotConfig.HEADER_HEIGHT_MIN and prior_aerial:
            header_evidence = (init_h - ShotConfig.HEADER_HEIGHT_MIN) / 0.6
            scores["ضربه سر"] = 75.0 + min(18.0, header_evidence * 18.0)
            if ball_descending: scores["ضربه سر"] += 6.0

        # ۵. والی
        if (ShotConfig.VOLLEY_HEIGHT_MIN <= init_h < ShotConfig.VOLLEY_HEIGHT_MAX) and prior_aerial and control_time <= 0.40:
            scores["والی"] = 80.0 + (init_h * 5.0)

        # ۶. شوت‌های کات‌دار
        if curve_ratio >= ShotConfig.CURVE_RATIO_THRESHOLD:
            target_name = "شوت کات‌دار درون محوطه" if in_box else "شوت کات‌دار بیرون محوطه"
            scores[target_name] = 84.0 + min(14.0, curve_ratio * 120.0)

        # ۷. شوت چیپ
        if 1.30 <= max_h <= 3.80 and (max_h / max(4.0, dist)) >= 0.08 and dist <= 22.0 and not prior_aerial:
            scores["شوت چیپ"] = 83.0

        # ۸. تک‌به‌تک
        if is_1v1:
            scores["شوت تک‌به‌تک"] = 86.0

        # ۹. شوت از زاویه بسته
        if angle_deg <= PitchConfig.TIGHT_ANGLE_DEG and abs(s_z) >= PitchConfig.WIDE_ZONE_Z:
            scores["شوت از زاویه بسته"] = 80.0

        # ۱۰. شوت نزدیک
        if dist <= PitchConfig.CLOSE_SHOT_DIST_MAX:
            scores["شوت نزدیک"] = 78.0 + (PitchConfig.CLOSE_SHOT_DIST_MAX - dist) * 1.5

        # ۱۱. شوت از راه دور
        if dist >= PitchConfig.LONG_SHOT_DIST_MIN and not in_box:
            scores["شوت از راه دور"] = 76.0 + min(15.0, (dist - 21.0) * 0.8)

        # ۱۲. عمومی
        if abs(s_z) <= PitchConfig.CENTER_ZONE_Z and angle_deg >= 20.0: scores["شوت از مرکز"] = 70.0
        if abs(s_z) >= PitchConfig.WIDE_ZONE_Z: scores["شوت از جناح"] = 69.0
        if in_box: scores["شوت داخل محوطه"] = 68.0

        # انتخاب بهترین کاندیدا
        priority_order = [
            "پنالتی", "شوت روی ریباند", "ضربه آزاد", "شوت کات‌دار درون محوطه",
            "شوت کات‌دار بیرون محوطه", "شوت چیپ", "والی", "ضربه سر",
            "شوت تک‌به‌تک", "شوت از زاویه بسته", "شوت نزدیک", "شوت از راه دور",
            "شوت از مرکز", "شوت از جناح", "شوت داخل محوطه"
        ]

        valid_cands = {k: v for k, v in scores.items() if v > 0.0}
        if not valid_cands:
            final_type = "شوت داخل محوطه" if in_box else "شوت از راه دور"
            confidence = 0.55
        else:
            sorted_cands = sorted(valid_cands.items(), key=lambda x: x[1], reverse=True)
            top_type, top_score = sorted_cands[0]
            # Tie-break هوشمند با اولویت تاکتیکی
            for p_type in priority_order:
                if p_type in valid_cands and valid_cands[p_type] >= (top_score - 4.5):
                    top_type = p_type
                    top_score = valid_cands[p_type]
                    break
            final_type = top_type
            second_score = sorted_cands[1][1] if len(sorted_cands) > 1 else 0.0
            margin = top_score - second_score
            confidence = min(0.95, max(0.55, 0.65 + margin * 0.02))

            # محدودیت اعتماد به دلیل عدم دسترسی به اسکلت بازیکن
            if final_type in ("ضربه سر", "والی"):
                confidence = min(0.85, confidence)

        tags = ["داخل محوطه" if in_box else "بیرون محوطه"]
        if is_1v1: tags.append("تک‌به‌تک")
        if curve_ratio >= ShotConfig.CURVE_RATIO_THRESHOLD: tags.append("کات‌دار")
        if dist <= PitchConfig.CLOSE_SHOT_DIST_MAX: tags.append("برد نزدیک")
        if dist >= PitchConfig.LONG_SHOT_DIST_MIN: tags.append("راه دور")
        if init_h >= ShotConfig.HEADER_HEIGHT_MIN: tags.append("هوایی")

        return final_type, confidence, tags, valid_cands

# =====================================================================
# ۱۸. Shot Engine (موتور تولید رویداد شوت — استخراج‌شده از نسخه کالیبره)
# ---------------------------------------------------------------------
# تشخیص لحظه ضربه (جهش بردار سرعت)، ره‌گیری state-based و غیرمسدودکننده
# پرواز تا خط دروازه، ارزیابی صفحه گل، تیرک، مهار/بلوک و خروجی
# ShotEventData کامل با pre_shot_threat و final_threat.
# ره‌گیری به‌صورت State Machine اجرا می‌شود تا Worker اصلی بلاک نشود و
# هم‌زمان Possession / Pass / Zone / Pressure / Time / Momentum از دست نرود.
# =====================================================================
class ShotEngine:
    """
    نسخهٔ ۱۰٫۱۴ — موتور شوت با «صف کاندیدهای شوت»:
      * ۱ افزایش Shot Counter = ۱ کاندید شوت — همیشه صف می‌شود؛ هیچ تریگری
        بی‌دلیل Drop نمی‌شود (حتی اگر موتور در حال TRACKING/PENDING باشد)؛
      * پردازش کاندیدها به ترتیب، مستقل از حلقهٔ اصلی (غیربلاک‌کننده)؛
      * ریکاوری لحظهٔ ضربه/شوت‌زننده بر پایهٔ Frame Buffer و زمان بازی
        (نه تایم‌اوت کوتاه دیواری)؛
      * Dedup فقط با شناسهٔ کاندید (counter + نسل) — دو شوت واقعیِ
        پشت‌سرهم هرگز Duplicate حساب نمی‌شوند؛
      * آمار کامل زنجیره (stats) — قابل مشاهده در دیباگ و پایان مسابقه.
    """
    def __init__(self):
        self.last_shot_counter: Optional[int] = None
        self.previous_shot_ctx: Optional[PreviousShotContext] = None
        self.state = "IDLE"  # IDLE | TRACKING
        self._trk: Optional[Dict[str, Any]] = None
        # --- نسخهٔ ۱۰٫۱۴: صف کاندیدهای شوت (جایگزین Pending تکی) ---
        self._queue: deque = deque()
        self._active: Optional[Dict[str, Any]] = None  # کاندیدِ سرِ صف در حال تلاش
        self._gen: int = 0                             # نسل شمارنده (ریست شمارنده ⇒ نسل جدید)
        self._finalized_ids: set = set()
        self._finalized_order: deque = deque(maxlen=64)
        self._auto_seq: int = 0                        # شناسهٔ خودکار برای مسیر سازگاری
        # --- آمار زنجیرهٔ شوت (مشخصات ۱۰٫۱۴) ---
        self.stats: Dict[str, int] = {
            "counter_increments": 0, "triggers": 0, "contact_found": 0,
            "shooter_found": 0, "tracking_started": 0, "tracking_finalized": 0,
            "events_registered": 0, "threats_created": 0, "ui_added": 0,
            "pending": 0, "pending_dropped": 0, "duplicates": 0,
        }
        # --- کانال دیباگ زنجیره شوت ---
        self.debug_sink = None   # callable(dict) — توسط MomentumApp تنظیم می‌شود

    def _dbg(self, stage: str, **kw):
        """ثبت مراحل زنجیره شوت برای Tab دیباگ (در صورت اتصال sink)"""
        if self.debug_sink:
            try:
                self.debug_sink(stage, **kw)
            except Exception:
                pass

    def _stat(self, key: str):
        """افزایش ایمن شمارندهٔ آماری زنجیرهٔ شوت"""
        try:
            self.stats[key] = self.stats.get(key, 0) + 1
        except Exception:
            pass

    def reset(self):
        self.state = "IDLE"
        self._trk = None
        self.previous_shot_ctx = None
        self._queue.clear()
        self._active = None
        self._gen += 1                     # شناسه‌های مسابقهٔ جدید هرگز قدیمی‌ها را تکرار نمی‌کنند
        self._finalized_ids.clear()
        self._finalized_order.clear()
        for _k in self.stats:
            self.stats[_k] = 0

    def set_counter_baseline(self, cnt: Optional[int]):
        self.last_shot_counter = cnt

    # -------------------------------------------------------------
    # صف کاندیدهای شوت (۱۰٫۱۴) — Push همیشه، Drop فقط با دلیلِ لاگ‌شده
    # -------------------------------------------------------------
    def push_trigger(self, counter_value: Optional[int], team: Optional[str],
                     alternates: List[Optional[str]], match_time: Optional[float],
                     wall_now: float, frame_seq: int = 0,
                     team1_attack_dir: int = 1) -> Optional[str]:
        """
        ۱ افزایش Shot Counter = ۱ کاندید شوت در صف.
          * counter_value → شناسهٔ یکتای کاندید: «نسل:مقدار شمارنده»؛
          * team → تیمِ تعیین‌شده از Context مالکیت (با fallback کاربر)؛
          * alternates → کاندیدهای جایگزین تیم (Context قبلی در جهشِ همزمان
            مالکیت، poss خام و ...) — در رزولوشن به ترتیب امتحان می‌شوند؛
          * Dedup فقط با شناسهٔ کاندید — نه زمان، نه هندسه.
        خروجی: شناسهٔ کاندید (یا None در صورت Duplicate بودن).
        """
        self._stat("triggers")
        if counter_value is None:
            self._auto_seq += 1
            candidate_id = f"{self._gen}:auto-{self._auto_seq}"
        else:
            candidate_id = f"{self._gen}:{int(counter_value)}"
        if candidate_id in self._finalized_ids \
                or (self._active and self._active.get("candidate_id") == candidate_id) \
                or any(q.get("candidate_id") == candidate_id for q in self._queue):
            self._stat("duplicates")
            self._dbg("DUP_SUPPRESSED", engine_state=self.state, team=team,
                      candidate_id=candidate_id, counter=counter_value,
                      note="همان رویداد شمارنده قبلاً صف/ثابت شده است")
            return None
        cand = {
            "candidate_id": candidate_id, "counter": counter_value,
            "team": team,
            "alternates": [t for t in (alternates or []) if t],
            "match_time": match_time, "trigger_wall": wall_now,
            "frame_seq": int(frame_seq), "attempts": 0,
            "t1_dir": int(team1_attack_dir),
        }
        if cand["team"] and cand["team"] not in cand["alternates"]:
            cand["alternates"].insert(0, cand["team"])
        self._queue.append(cand)
        self._dbg("TRIGGER_QUEUED", engine_state=self.state, team=team,
                  candidate_id=candidate_id, counter=counter_value,
                  queue_len=len(self._queue),
                  note="۱ افزایش شمارنده = ۱ کاندید شوت (در صف پردازش)")
        return candidate_id

    def on_counter_reset(self, reason: str = "counter_reset") -> int:
        """
        بازنشانی Shot Counter (نیمه دوم/ری‌استارت): کاندیدهای صف‌شدهٔ قبلی
        کهنه‌اند (تعلق به نسلِ قبل) — فقط با دلیلِ لاگ‌شده حذف می‌شوند و
        نسل += ۱ تا شناسه‌های آینده برخورد نکنند.
        """
        dropped = 0
        while self._queue:
            q = self._queue.popleft()
            self._stat("pending_dropped")
            self._dbg("PENDING_DROPPED", engine_state=self.state, team=q.get("team"),
                      candidate_id=q.get("candidate_id"), reason=reason,
                      note="بازنشانی شمارنده — کاندیدِ نسلِ قبلی حذف شد")
            dropped += 1
        if self._active is not None and self.state != "TRACKING":
            self._stat("pending_dropped")
            self._dbg("PENDING_DROPPED", engine_state=self.state,
                      team=self._active.get("team"),
                      candidate_id=self._active.get("candidate_id"), reason=reason,
                      note="بازنشانی شمارنده — کاندیدِ در حال تلاش حذف شد")
            self._active = None
            dropped += 1
        self._gen += 1
        return dropped

    def _mark_finalized(self, candidate_id: Optional[str]):
        """ثبت شناسهٔ کاندید به‌عنوان نهایی‌شده (هر کاندید فقط یک بار)"""
        if candidate_id is None:
            return
        self._finalized_ids.add(candidate_id)
        self._finalized_order.append(candidate_id)
        while len(self._finalized_order) > ShotConfig.SHOT_FINALIZED_KEEP:
            _old = self._finalized_order.popleft()
            self._finalized_ids.discard(_old)

    # -------------------------------------------------------------
    # شروع ره‌گیری (بدنه مشترک process / شیم سازگاری on_counter_increment)
    # -------------------------------------------------------------
    @staticmethod
    def _seed_from_buffer(buffer_list: List[SnapshotFrame], shot_frame: SnapshotFrame,
                          cap: int = 20) -> Tuple[List, List, List]:
        """
        نسخهٔ ۱۰٫۱۴ — فریم‌های «پس از» لحظهٔ ضربه در بافر → سربارگذاری مسیر پرواز.
        برای رزولوشن‌های دیرهنگام (Pending)، ابتدای پرواز توپ از دست نمی‌رود؛
        سرعت‌ها با همان فرمول update_tracking فیلتر می‌شوند.
        """
        idx = None
        for i in range(len(buffer_list) - 1, -1, -1):
            if buffer_list[i] is shot_frame:
                idx = i
                break
        if idx is None:
            return [], [], []
        balls: List = []
        ts: List = []
        spd: List = []
        prev_b, prev_t = shot_frame.ball, shot_frame.timestamp
        for f in buffer_list[idx + 1: idx + 1 + cap]:
            dt = max(0.005, f.timestamp - prev_t)
            d3 = GeometryEngine.dist_3d(f.ball, prev_b)
            v = (d3 / dt) * 3.6
            if ShotConfig.MIN_VALID_SHOT_SPEED <= v <= ShotConfig.MAX_PLAUSIBLE_SPEED:
                spd.append(v)
            balls.append(f.ball)
            ts.append(f.timestamp)
            prev_b, prev_t = f.ball, f.timestamp
        return balls, ts, spd

    def _start_tracking(self, engine, team: str, att_dir: int,
                        shot_frame: SnapshotFrame, shooter: Dict,
                        buffer_list: List[SnapshotFrame], wall_now: float,
                        candidate: Optional[Dict[str, Any]] = None) -> None:
        self.state = "TRACKING"
        seed_balls, seed_ts, seed_spd = self._seed_from_buffer(buffer_list, shot_frame)
        cand_id = (candidate or {}).get("candidate_id")
        self._trk = {
            "team": team,
            "att_dir": att_dir,
            "target_goal_x": PitchConfig.HALF_LENGTH * att_dir,
            "shot_frame": shot_frame,
            "shooter": shooter,
            "buffer_list": buffer_list,
            "trajectory": [shot_frame.ball] + seed_balls,
            "time_stamps": [shot_frame.timestamp] + seed_ts,
            "speeds": list(seed_spd),
            "max_h": max([shot_frame.ball[2]] + [b[2] for b in seed_balls]),
            "hit_woodwork": False,
            "woodwork_name": "",
            "woodwork_rebound": False,
            "is_goal": False,
            "intercepted": False,
            "intercept_player": None,
            "block_dist": 0.0,
            "goal_line_point": None,
            "tracking_start": time.time(),
            "opp_gk_seat": 12 if team == "Home" else 1,
            "now_t": wall_now,
            "candidate_id": cand_id,
        }
        self._stat("tracking_started")
        self._dbg("TRACKING_STARTED", engine_state=self.state,
                  team=team, shooter_seat=shooter.get("seat"),
                  shot_match_time=shot_frame.match_time,
                  candidate_id=cand_id, seeded_frames=len(seed_balls))

    # -------------------------------------------------------------
    # ریکاوری لحظه دقیق ضربه و شوت‌زننده بر پایه جهش بردار سرعت
    # -------------------------------------------------------------
    @staticmethod
    def find_true_contact_and_shooter(
        buffer_list: List[SnapshotFrame],
        team: str,
        att_dir: int,
        scope_frames: int = 26
    ) -> Tuple[Optional[SnapshotFrame], Optional[Dict]]:
        if len(buffer_list) < 5: return None, None
        scope = min(scope_frames, len(buffer_list) - 1)
        search_scope = buffer_list[-scope:-3] if len(buffer_list) >= scope else buffer_list[:-1]

        best_frame = None
        best_shooter = None
        max_contact_score = -999.0

        for idx in range(1, len(search_scope)):
            f_prev = search_scope[idx - 1]
            f_cur = search_scope[idx]

            dt = max(0.005, f_cur.timestamp - f_prev.timestamp)
            vx = (f_cur.ball[0] - f_prev.ball[0]) / dt
            vz = (f_cur.ball[1] - f_prev.ball[1]) / dt
            vy = (f_cur.ball[2] - f_prev.ball[2]) / dt
            speed = math.sqrt(vx*vx + vz*vz + vy*vy)
            fwd_speed = vx * att_dir

            attackers = [p for p in f_cur.players if p["team"] == team]
            for cand in attackers:
                d_cand = GeometryEngine.dist_2d((cand["x"], cand["z"]), (f_cur.ball[0], f_cur.ball[1]))
                if d_cand <= 2.2:
                    # امتیاز تطابق بردار خروج توپ و حضور بازیکن
                    score = (1.0 / (d_cand + 0.35)) * 40.0 + fwd_speed * 1.5 + (speed * 0.8)
                    if score > max_contact_score:
                        max_contact_score = score
                        best_frame = f_cur
                        best_shooter = cand

        return best_frame, best_shooter

    def on_counter_increment(self, engine, buffer_list: List[SnapshotFrame],
                             wall_now: float, team: str, att_dir: int) -> bool:
        """
        شیم سازگاری (۱۰٫۱۴) — مسیر قدیمی «تریگر فوری»: کاندید می‌سازد و
        همان تیک پردازش می‌کند. مسیر اصلی Worker: push_trigger + process.
        خروجی: True اگر ره‌گیری آغاز شد (قرارداد قدیمی حفظ شده).
        """
        self.push_trigger(None, team, [team], None, wall_now, 0, att_dir)
        return self.process(engine, buffer_list, wall_now, None, 0)

    # -------------------------------------------------------------
    # پردازش صف کاندیدها (۱۰٫۱۴) — هر تیک؛ غیربلاک‌کننده؛ ریکاوری فریم‌محور
    # -------------------------------------------------------------
    def process(self, engine, buffer_list: List[SnapshotFrame], wall_now: float,
                match_time: Optional[float] = None, frame_seq: int = 0) -> bool:
        """
        اگر ره‌گیری فعالی در جریان نیست، سرِ صف را برای «یافتن لحظهٔ ضربه +
        شوت‌زننده» تلاش می‌کند:
          * کاندیدهای تیم به ترتیب (تیم اصلی → Context قبلی → poss خام →
            در نبودِ هر کاندیدی: هر دو تیم) امتحان می‌شوند؛
          * جستجوی اول در پنجرهٔ کالیبره (۲۶ فریم) و تلاش‌های بعدی عمیق‌تر
            (۱۲۰ فریم) داخل Frame Buffer؛
          * Drop فقط پس از عبور «پنجرهٔ ریکاوری واقعی» (فریم/زمان بازی) و
            همیشه با دلیلِ لاگ‌شده — هیچ تریگری بی‌صدا حذف نمی‌شود.
        خروجی: True اگر ره‌گیری آغاز شد.
        """
        if self.state == "TRACKING":
            return False
        if self._active is None:
            if not self._queue:
                return False
            self._active = self._queue.popleft()
            self._dbg("CONTACT_SEARCH", engine_state=self.state,
                      team=self._active.get("team"),
                      candidate_id=self._active.get("candidate_id"),
                      buffer_len=len(buffer_list),
                      note="جستجوی عقب‌روی لحظهٔ ضربه در Frame Buffer")
        cand = self._active

        # --- پنجرهٔ ریکاوری واقعی (فریم / زمان بازی — نه تایم‌اوت کوتاه دیواری) ---
        frames_since = max(0, int(frame_seq) - int(cand.get("frame_seq", 0)))
        mt_since = None
        if match_time is not None and cand.get("match_time") is not None:
            mt_since = max(0.0, float(match_time) - float(cand["match_time"]))
        if (frames_since > ShotConfig.SHOT_RECOVERY_MAX_FRAMES
                or (mt_since is not None
                    and mt_since > ShotConfig.SHOT_RECOVERY_MAX_MATCH_SEC)):
            self._stat("pending_dropped")
            self._dbg("PENDING_DROPPED", engine_state=self.state,
                      team=cand.get("team"),
                      candidate_id=cand.get("candidate_id"),
                      frames_since=frames_since,
                      match_time_since=(round(mt_since, 2) if mt_since is not None else None),
                      attempts=cand.get("attempts", 0),
                      note="عبور از پنجرهٔ ریکاوری — لحظهٔ ضربه قابل بازیابی نبود")
            self._active = None
            return False

        # --- تلاش رزولوشن با کاندیدهای تیم به ترتیب ---
        cand["attempts"] = cand.get("attempts", 0) + 1
        teams_to_try: List[str] = []
        for t in ([cand.get("team")] + list(cand.get("alternates") or [])):
            if t and t not in teams_to_try:
                teams_to_try.append(t)
        if not teams_to_try:
            # Context مالکیت هیچ کاندیدی نداد → خودِ جستجوی تماس تیم را
            # تعیین می‌کند (فقط بازیکنان تیمِ شوت‌زننده کنار توپ هستند)
            teams_to_try = ["Home", "Away"]

        scope = (ShotConfig.SHOT_CONTACT_SCOPE if cand["attempts"] <= 1
                 else ShotConfig.SHOT_PENDING_SCOPE)
        for team in teams_to_try:
            t1_dir = cand.get("t1_dir", 1)
            att_dir = t1_dir if team == "Home" else -t1_dir
            shot_frame, shooter = self.find_true_contact_and_shooter(
                buffer_list, team, att_dir, scope_frames=scope)
            if not shot_frame or not shooter:
                continue
            self._stat("contact_found")
            self._stat("shooter_found")
            # فیلتر قطعی شوت: فقط و فقط در نیمه حریف (کالیبره ابزار مستقل)
            shooter_x_att = shooter["x"] * att_dir
            ball_x_att = shot_frame.ball[0] * att_dir
            if shooter_x_att <= 0.0 or ball_x_att <= 0.0:
                self._dbg("TRIGGER_FILTER_REJECT", engine_state=self.state, team=team,
                          candidate_id=cand.get("candidate_id"),
                          note="ضربه در نیمهٔ خودی برای این کاندید تیم — تیم بعدی")
                continue
            self._active = None
            self._dbg("CONTACT_FOUND", engine_state=self.state, team=team,
                      candidate_id=cand.get("candidate_id"),
                      shot_match_time=shot_frame.match_time,
                      attempts=cand["attempts"],
                      note="فریم لحظهٔ ضربه در بافر یافت شد")
            self._dbg("SHOOTER_FOUND", engine_state=self.state, team=team,
                      candidate_id=cand.get("candidate_id"),
                      shooter_seat=shooter.get("seat"),
                      attempts=cand["attempts"],
                      note="شوت‌زننده تأیید شد")
            if cand["attempts"] > 1:
                self._dbg("PENDING_RESOLVED", engine_state=self.state, team=team,
                          candidate_id=cand.get("candidate_id"),
                          attempts=cand["attempts"],
                          note="لحظهٔ ضربه در تلاش‌های بعدی بازیابی شد")
            self._start_tracking(engine, team, att_dir, shot_frame, shooter,
                                 buffer_list, wall_now, cand)
            return True

        if cand["attempts"] <= 1:
            self._stat("pending")
            self._dbg("PENDING", engine_state=self.state, team=cand.get("team"),
                      candidate_id=cand.get("candidate_id"),
                      note="لحظهٔ ضربه فوراً یافت نشد — ریکاوری در فریم‌های بعدی")
        elif cand["attempts"] % 20 == 0:
            self._dbg("CONTACT_NOT_FOUND", engine_state=self.state,
                      team=cand.get("team"),
                      candidate_id=cand.get("candidate_id"),
                      attempts=cand["attempts"],
                      note="هنوز بدون نتیجه — جستجو ادامه دارد")
        return False

    def try_pending(self, engine, buffer_list: List[SnapshotFrame], wall_now: float) -> bool:
        """شیم سازگاری (۱۰٫۱۴) — معادل process بدون زمان بازی."""
        return self.process(engine, buffer_list, wall_now, None, 0)

    def update_tracking(self, engine) -> Optional[ShotEventData]:
        """
        یک گام از ره‌گیری پرواز (state-based/non-blocking) — در هر Poll یک تکرار
        از حلقه اصلی نسخه کالیبره اجرا می‌شود؛ منطق و آستانه‌ها دست‌نخورده‌اند.
        """
        if self.state != "TRACKING" or not self._trk:
            return None
        trk = self._trk

        # Timeout نسخه کالیبره (wall clock — فقط برای timeout/performance)
        if (time.time() - trk["tracking_start"]) >= ShotConfig.MAX_TRACK_TIME:
            return self._finalize()

        b_cur = engine.read_ball()
        if not b_cur:
            return None

        cur_t = time.time()
        trajectory: List[Tuple[float, float, float]] = trk["trajectory"]
        time_stamps: List[float] = trk["time_stamps"]
        att_dir = trk["att_dir"]
        team = trk["team"]

        dt = cur_t - time_stamps[-1]
        if dt > 0.005:
            d_3d = GeometryEngine.dist_3d(b_cur, trajectory[-1])
            inst_spd = (d_3d / dt) * 3.6
            if ShotConfig.MIN_VALID_SHOT_SPEED <= inst_spd <= ShotConfig.MAX_PLAUSIBLE_SPEED:
                trk["speeds"].append(inst_spd)

        trajectory.append(b_cur)
        time_stamps.append(cur_t)
        if b_cur[2] > trk["max_h"]: trk["max_h"] = b_cur[2]

        # --- نسخهٔ ۱۰٫۱۴: لاگ کنترل‌شدهٔ پیشرفت ره‌گیری (هر ۲۵ نقطه) ---
        if len(trajectory) % 25 == 0:
            self._dbg("TRACKING_UPDATED", engine_state=self.state,
                      team=trk["team"],
                      candidate_id=trk.get("candidate_id"),
                      points=len(trajectory),
                      note="ره‌گیری پرواز در جریان است")

        # الف: بررسی برخورد و انحراف با تیرک‌ها
        if not trk["hit_woodwork"] and abs(b_cur[0] - trk["target_goal_x"]) <= (PitchConfig.POST_COLLISION_RADIUS + 0.3):
            p_prev = trajectory[-2]
            vx_att = (b_cur[0] - p_prev[0]) * att_dir
            # بررسی نزدیکی به تیرهای عمودی یا افقی
            d_post_l = math.hypot(b_cur[1] - (-PitchConfig.GOAL_HALF_WIDTH), max(0.0, b_cur[2] - PitchConfig.GOAL_HEIGHT/2))
            d_post_r = math.hypot(b_cur[1] - PitchConfig.GOAL_HALF_WIDTH, max(0.0, b_cur[2] - PitchConfig.GOAL_HEIGHT/2))
            d_bar = abs(b_cur[2] - PitchConfig.GOAL_HEIGHT)

            if min(d_post_l, d_post_r, d_bar) <= PitchConfig.POST_COLLISION_RADIUS:
                trk["hit_woodwork"] = True
                trk["woodwork_name"] = "تیر افقی" if d_bar < min(d_post_l, d_post_r) else "تیر عمودی"
                if vx_att < -0.2: trk["woodwork_rebound"] = True

        # ب: بررسی مهار یا بلوک واقعی با فیلتر ارتفاع پرش
        cur_players = engine.read_players()
        opponents = [p for p in cur_players if p["team"] != team]
        closest_opp = None
        min_opp_d = 999.0
        for op in opponents:
            d_op = GeometryEngine.dist_2d((op["x"], op["z"]), (b_cur[0], b_cur[1]))
            if d_op < min_opp_d:
                min_opp_d = d_op
                closest_opp = op

        if len(trajectory) >= 6 and closest_opp and min_opp_d <= 1.05:
            is_gk = (closest_opp["seat"] == trk["opp_gk_seat"])
            reach_limit = ShotConfig.GK_MAX_REACH_HEIGHT if is_gk else ShotConfig.OUTFIELD_MAX_REACH_HEIGHT

            # توپ نباید از بالای سقف دسترس بازیکن رد شود
            if b_cur[2] <= reach_limit:
                vx_now = (b_cur[0] - trajectory[-3][0]) * att_dir
                # افت سرعت شدید یا برگشت توپ به سمت عقب
                if vx_now < 0.25:
                    trk["intercepted"] = True
                    trk["intercept_player"] = closest_opp
                    trk["block_dist"] = abs(trk["target_goal_x"] - b_cur[0])
                    return self._finalize()

        # ج: قطع فوری به محض عبور از صفحه خط ۵۲.۵ متر
        cur_x_att = b_cur[0] * att_dir
        prev_x_att = trajectory[-2][0] * att_dir
        if cur_x_att >= PitchConfig.HALF_LENGTH:
            # درون‌یابی دقیق نقطه برخورد با صفحه خط دروازه
            span = cur_x_att - prev_x_att
            t_ratio = (PitchConfig.HALF_LENGTH - prev_x_att) / span if abs(span) > 1e-4 else 1.0
            t_ratio = max(0.0, min(1.0, t_ratio))

            cross_z = trajectory[-2][1] + t_ratio * (b_cur[1] - trajectory[-2][1])
            cross_y = max(0.0, trajectory[-2][2] + t_ratio * (b_cur[2] - trajectory[-2][2]))
            trk["goal_line_point"] = (trk["target_goal_x"], cross_z, cross_y)

            # --- نسخه ۴: ثبت گل از «مسیر توپ + چارچوب دروازه» کاملاً کنار گذاشته شد ---
            # عبور از صفحهٔ دروازه فقط برای ارزیابی is_on_target / فاصله تیرک /
            # متن اولیه Outcome استفاده می‌شود. تعیین نهایی «گل» تنها توسط
            # GoalHooker (شمارندهٔ حافظه: [rcx+0x158] / [rcx+0x15C]) انجام می‌شود
            # و پس از تأیید هوک، رخداد شوتِ لینک‌شده به‌صورت بازگشتی به «گل»
            # ارتقا می‌یابد (register_goal_event + سیاست GOAL_LINKED_SHOT_RATIO).
            return self._finalize()

        return None

    # -------------------------------------------------------------
    # ارزیابی نهایی شوت (پورت کامل بلوک ارزیابی نسخه کالیبره)
    # -------------------------------------------------------------
    def _finalize(self) -> Optional[ShotEventData]:
        trk = self._trk
        self.state = "IDLE"
        self._trk = None
        if not trk:
            return None
        # --- نسخهٔ ۱۰٫۱۴: شناسهٔ کاندید نهایی می‌شود (هر کاندید فقط یک بار) ---
        _cand_id = trk.get("candidate_id")
        self._mark_finalized(_cand_id)
        self._stat("tracking_finalized")
        self._dbg("TRACKING_FINALIZED", engine_state=self.state,
                  team=trk.get("team"), candidate_id=_cand_id,
                  note="ارزیابی نهایی شوت آغاز شد")

        trajectory = trk["trajectory"]
        speeds = trk["speeds"]
        buffer_list = trk["buffer_list"]
        team = trk["team"]
        att_dir = trk["att_dir"]
        shooter = trk["shooter"]
        shot_frame = trk["shot_frame"]
        opp_gk_seat = trk["opp_gk_seat"]
        now_t = trk["now_t"]
        target_goal_x = trk["target_goal_x"]
        is_goal = trk["is_goal"]
        hit_woodwork = trk["hit_woodwork"]
        woodwork_name = trk["woodwork_name"]
        woodwork_rebound = trk["woodwork_rebound"]
        intercepted = trk["intercepted"]
        intercept_player = trk["intercept_player"]
        block_dist = trk["block_dist"]
        goal_line_point = trk["goal_line_point"]

        # ارزیابی سرعت واقعی
        if speeds:
            sorted_spd = sorted(speeds)
            max_speed = sorted_spd[int(len(sorted_spd) * 0.85)]
            speed_valid = True
        else:
            max_speed = None
            speed_valid = False

        # ارزیابی صفحه هدف
        eval_p = goal_line_point if goal_line_point else trajectory[-1]
        signed_woodwork_dist, is_on_target = GeometryEngine.calculate_signed_woodwork_distance(eval_p[1], eval_p[2])

        # تعیین قطعی فرجام شوت (Outcome)
        if is_goal:
            is_on_target = True
            outcome = f"گل با برخورد به {woodwork_name} ⚽💥" if hit_woodwork else "گل قطعی ⚽"
        elif hit_woodwork:
            is_on_target = True
            outcome = f"برخورد به {woodwork_name} و بازگشت به زمین 💥" if woodwork_rebound else f"برخورد به {woodwork_name} و خروج از زمین 💥"
        elif intercepted and intercept_player:
            is_gk = (intercept_player["seat"] == opp_gk_seat)
            actor = "دروازه‌بان" if is_gk else "مدافع"
            outcome = f"مهار توسط {actor} (در چارچوب) 🧤" if is_on_target else f"دفع توسط {actor} (خارج چارچوب)"
        else:
            if is_on_target:
                outcome = "در چارچوب (مهار / توقف)"
            else:
                if signed_woodwork_dist <= 0.8: outcome = "خارج از چارچوب (اختلاف بسیار کم / مماس)"
                elif signed_woodwork_dist <= 2.2: outcome = "خارج از چارچوب (اختلاف متوسط)"
                else: outcome = "خارج از چارچوب (اختلاف زیاد)"

        # استخراج متغیرهای تاکتیکی و هندسی
        dist_to_goal = math.hypot(shooter["x"] - target_goal_x, shooter["z"])
        goal_ang_rad = GeometryEngine.goal_view_angle(shooter["x"], shooter["z"], target_goal_x)
        goal_ang_deg = math.degrees(goal_ang_rad)

        defenders = [p for p in shot_frame.players if p["team"] != team]
        opp_gk = next((p for p in defenders if p["seat"] == opp_gk_seat), None)

        corridor_defs, obstruction_ratio = GeometryEngine.calculate_dynamic_corridor_obstruction(
            (shooter["x"], shooter["z"]), target_goal_x, defenders, opp_gk
        )

        rec_def_dists = sorted([GeometryEngine.dist_2d((shooter["x"], shooter["z"]), (d["x"], d["z"])) for d in defenders]) if defenders else [25.0]
        near_def_dist = rec_def_dists[0]

        # بررسی تک‌به‌تک بر پایه مخروط باز و گلر
        is_1v1 = (corridor_defs == 0 and obstruction_ratio <= 0.08 and dist_to_goal <= 22.0 and near_def_dist >= 2.4)
        is_inside_box = ((shooter["x"] * att_dir) >= PitchConfig.PENALTY_BOX_X and abs(shooter["z"]) <= PitchConfig.PENALTY_BOX_HALF_Z)

        # بررسی مدت سکون توپ برای پنالتی و ضربه آزاد
        stationary_duration = 0.0
        if len(buffer_list) >= 15:
            sub_buf = [f.ball for f in list(buffer_list)[-45:]]
            ref_b = sub_buf[0]
            if all(GeometryEngine.dist_2d((b[0], b[1]), (ref_b[0], ref_b[1])) <= ShotConfig.STATIONARY_RADIUS for b in sub_buf):
                stationary_duration = len(sub_buf) * 0.015

        # بررسی پنالتی دقیق
        pen_spot_x = PitchConfig.PENALTY_SPOT_X_ATT * att_dir
        is_pen_spot = (abs(shooter["x"] - pen_spot_x) <= 1.8 and abs(shooter["z"]) <= 1.4 and dist_to_goal <= 12.5)
        other_players_clear = all(
            GeometryEngine.dist_2d((p["x"], p["z"]), (pen_spot_x, 0.0)) >= 8.5
            for p in shot_frame.players if p["seat"] not in (shooter["seat"], opp_gk_seat)
        )

        # بررسی ریباند واقعی با شواهد هندسی
        is_rebound = False
        if self.previous_shot_ctx:
            dt_prev = now_t - self.previous_shot_ctx.timestamp
            if dt_prev <= 4.2 and self.previous_shot_ctx.team == team:
                dist_from_prev_end = GeometryEngine.dist_2d((shooter["x"], shooter["z"]), (self.previous_shot_ctx.end_position[0], self.previous_shot_ctx.end_position[1]))
                if dist_from_prev_end <= 15.0 and ("مهار" in self.previous_shot_ctx.outcome or "بلوک" in self.previous_shot_ctx.outcome or "تیرک" in self.previous_shot_ctx.outcome):
                    is_rebound = True

        # ثبت شوت فعلی به عنوان کانتکست قبلی
        self.previous_shot_ctx = PreviousShotContext(
            timestamp=now_t,
            end_position=eval_p,
            team=team,
            outcome=outcome,
            target_goal_x=target_goal_x
        )

        # محاسبه کات توپ
        curve_ratio, curve_dir = GeometryEngine.calculate_curve(trajectory)

        # وضعیت پرواز قبلی برای تشخیص سر و والی
        prior_aerial = any(f.ball[2] >= 1.35 for f in buffer_list[-20:-5]) if len(buffer_list) >= 20 else False
        ball_descending = (len(trajectory) >= 3 and trajectory[0][2] > trajectory[2][2])

        features = {
            "dist_to_goal": dist_to_goal,
            "goal_angle_deg": goal_ang_deg,
            "shooter_z": shooter["z"],
            "initial_height": shot_frame.ball[2],
            "max_height": trk["max_h"],
            "curve_ratio": curve_ratio,
            "is_inside_box": is_inside_box,
            "is_1v1": is_1v1,
            "is_rebound": is_rebound,
            "stationary_duration": stationary_duration,
            "is_penalty_spot": is_pen_spot,
            "other_players_clear_of_box": other_players_clear,
            "prior_ball_aerial": prior_aerial,
            "ball_descending": ball_descending,
            "shooter_control_time": 0.25
        }

        primary_type, confidence, tags, cand_scores = ShotClassifierEngine.classify(features)

        # محاسبه تفکیک‌شده تهدید (Pre = Opportunity Value | Final = Momentum Impact)
        pre_threat = ShotThreatEngine.calculate_pre_shot_threat(
            dist_to_goal=dist_to_goal,
            goal_angle_rad=goal_ang_rad,
            corridor_defs=corridor_defs,
            obstruction_ratio=obstruction_ratio,
            nearest_def_dist=near_def_dist,
            opp_gk=opp_gk,
            target_goal_x=target_goal_x,
            shooter_z=shooter["z"],
            is_inside_box=is_inside_box,
            is_1v1=is_1v1
        )

        final_threat = ShotThreatEngine.calculate_final_threat(
            pre_shot_threat=pre_threat,
            outcome=outcome,
            is_on_target=is_on_target,
            woodwork_dist=signed_woodwork_dist,
            speed_kmh=max_speed,
            block_dist=block_dist
        )

        gk_d = GeometryEngine.dist_2d((opp_gk["x"], opp_gk["z"]), (target_goal_x, 0.0)) if opp_gk else 0.0

        shot_data = ShotEventData(
            event_id=0,  # در لحظه ثبت توسط EventDetectionEngine تخصیص می‌یابد
            match_time=shot_frame.match_time,
            team=team,
            shooter_seat=shooter["seat"],
            primary_type=primary_type,
            confidence=confidence,
            pre_shot_threat=pre_threat,
            final_threat=final_threat,
            max_speed_kmh=max_speed,
            speed_valid=speed_valid,
            initial_height=shot_frame.ball[2],
            max_height=trk["max_h"],
            curve_ratio=curve_ratio,
            curve_dir=curve_dir,
            is_on_target=is_on_target,
            outcome=outcome,
            woodwork_distance=signed_woodwork_dist,
            block_distance=block_dist,
            shooter_pos=(shooter["x"], shooter["z"]),
            contact_ball=trajectory[0],
            goal_line_intersection=eval_p,
            distance_to_goal=dist_to_goal,
            goal_angle_deg=goal_ang_deg,
            defenders_in_corridor=corridor_defs,
            nearest_defender_dist=near_def_dist,
            gk_dist_to_goal=gk_d,
            is_inside_box=is_inside_box,
            is_1v1=is_1v1,
            # نسخه ۳: ثبت صریح پرچم گل روی مدل داده
            is_goal=is_goal,
            # نسخهٔ ۱۰٫۱۴: شناسهٔ کاندید شمارنده (مبنای Dedup ثبت نهایی)
            candidate_id=_cand_id,
            tags=tags,
            candidate_scores=cand_scores
        )
        # --- نسخه ۲: ثبت مرحله نهایی زنجیره شوت (Event ساخته شد) ---
        self._dbg(
            "SHOT_EVENT_CREATED",
            engine_state=self.state,
            team=team,
            shot_event_id=0,          # پس از register_shot_event توسط Worker تکمیل می‌شود
            candidate_id=_cand_id,
            shot_match_time=shot_data.match_time,
            outcome=outcome,
            pre_threat=pre_threat,
            final_threat=final_threat,
            is_goal=is_goal,
            is_on_target=is_on_target,
            primary_type=primary_type
        )
        return shot_data

# =====================================================================
# ۱۹. تحلیل ساختار دفاعی (DefensiveStructureEngine)
# =====================================================================
class DefensiveStructureEngine:
    @staticmethod
    def analyze_structure(players: List[Dict], att_team: str, att_dir: int) -> Dict[str, Any]:
        defenders = [p for p in players if p["team"] != att_team]
        opp_gk_seat = 12 if att_team == "Home" else 1
        outfield_defs = [d for d in defenders if d["seat"] != opp_gk_seat]
        if not outfield_defs:
            return {"def_line_x_att": 35.0, "is_high_line": False, "is_deep_block": False, "def_area_sqm": 400.0}

        # مرتب‌سازی طولی مدافعان در جهت حمله حریف
        sorted_x_att = sorted([d["x"] * att_dir for d in outfield_defs])
        # خط آفساید معمولاً با موقعیت دومین مدافع عمیق مشخص می‌شود
        def_line_x_att = sorted_x_att[-2] if len(sorted_x_att) >= 2 else sorted_x_att[-1]

        z_coords = [d["z"] for d in outfield_defs]
        width = max(z_coords) - min(z_coords) if z_coords else 30.0
        length = (sorted_x_att[-1] - sorted_x_att[0]) if len(sorted_x_att) >= 2 else 15.0

        # در مختصات حمله، خط دفاع بالا یعنی مدافعان به سمت میانه زمین جلو کشیده‌اند
        is_high_line = (def_line_x_att <= 22.0)
        is_deep_block = (def_line_x_att >= 36.0)

        return {
            "def_line_x_att": def_line_x_att,
            "is_high_line": is_high_line,
            "is_deep_block": is_deep_block,
            "def_area_sqm": length * width
        }

# =====================================================================
# ۲۰. تشخیص موقعیت‌های گل (OpportunityEngine — Chance و Big Chance)
# =====================================================================
class OpportunityEngine:
    def __init__(self):
        self.last_chance_time = 0.0
        self.last_chance_id: Optional[int] = None

    def evaluate(
        self,
        frame: SnapshotFrame,
        att_team: str,
        att_dir: int,
        emit,
        id_gen
    ):
        now_t = frame.timestamp
        if (now_t - self.last_chance_time) < 3.2:
            return

        target_goal_x = PitchConfig.HALF_LENGTH * att_dir
        attackers = [p for p in frame.players if p["team"] == att_team]
        defenders = [p for p in frame.players if p["team"] != att_team]
        opp_gk_seat = 12 if att_team == "Home" else 1
        opp_gk = next((p for p in defenders if p["seat"] == opp_gk_seat), None)

        bx, bz, _ = frame.ball
        carrier = min(attackers, key=lambda p: GeometryEngine.dist_2d((p["x"], p["z"]), (bx, bz))) if attackers else None
        if not carrier or GeometryEngine.dist_2d((carrier["x"], carrier["z"]), (bx, bz)) > 2.5:
            return

        cx, cz = carrier["x"], carrier["z"]
        dist_to_goal = math.hypot(cx - target_goal_x, cz)
        if dist_to_goal > 24.0 or (cx * att_dir) <= 0.0:
            return

        corridor_defs, obstruction_ratio = GeometryEngine.calculate_dynamic_corridor_obstruction(
            (cx, cz), target_goal_x, defenders, opp_gk
        )
        near_def_dist = min([GeometryEngine.dist_2d((cx, cz), (d["x"], d["z"])) for d in defenders]) if defenders else 20.0
        goal_ang = math.degrees(GeometryEngine.goal_view_angle(cx, cz, target_goal_x))

        is_inside_box = ((cx * att_dir) >= PitchConfig.PENALTY_BOX_X and abs(cz) <= PitchConfig.PENALTY_BOX_HALF_Z)
        is_1v1 = (corridor_defs == 0 and obstruction_ratio <= 0.10 and dist_to_goal <= 20.0 and near_def_dist >= 2.2)

        is_big_chance = (is_1v1 or (is_inside_box and dist_to_goal <= 12.0 and corridor_defs <= 1))
        is_chance = (dist_to_goal <= 20.0 and goal_ang >= 20.0 and corridor_defs <= 2)

        if is_big_chance or is_chance:
            self.last_chance_time = now_t
            ev_id = id_gen()
            self.last_chance_id = ev_id
            emit(GameEvent(
                event_id=ev_id,
                event_type="Big Chance" if is_big_chance else "Chance",
                team=att_team,
                timestamp=frame.timestamp,
                match_time=frame.match_time,
                reliability=EventReliability.INFERRED,
                confidence=0.88 if is_big_chance else 0.80,
                position=frame.ball,
                tags=["موقعیت طلایی" if is_big_chance else "موقعیت خطرناک", f"{dist_to_goal:.1f}m"]
            ))

# =====================================================================
# ۲۱. رخدادنگار مستقل پنالتی (PenaltyDetector — مستقل از شمارنده شوت)
# =====================================================================
class PenaltyDetector:
    """تشخیص موقعیت و شلیک ضربه پنالتی بر پایه شواهد نقطه و فیزیک"""
    def __init__(self):
        self.state = "IDLE"
        self.stationary_start = 0.0
        self.target_goal_x = 0.0
        self.att_team = ""
        self.penalty_id: Optional[int] = None

    def reset(self):
        self.state = "IDLE"
        self.penalty_id = None

    def update(
        self,
        frame_buffer: deque,
        current_frame: SnapshotFrame,
        team1_att_dir: int,
        emit,
        id_gen
    ):
        bx, bz, by = current_frame.ball
        dist_spot_r = math.hypot(bx - PitchConfig.PENALTY_SPOT_X_ATT, bz)
        dist_spot_l = math.hypot(bx - (-PitchConfig.PENALTY_SPOT_X_ATT), bz)

        is_near_spot = False
        target_goal_x = 0.0
        att_team = ""

        if dist_spot_r <= 1.8:
            is_near_spot = True
            target_goal_x = PitchConfig.HALF_LENGTH
            att_team = "Home" if team1_att_dir == 1 else "Away"
        elif dist_spot_l <= 1.8:
            is_near_spot = True
            target_goal_x = -PitchConfig.HALF_LENGTH
            att_team = "Away" if team1_att_dir == 1 else "Home"

        if self.state == "IDLE":
            if is_near_spot and by <= 0.35:
                self.state = "WAITING_KICK"
                self.stationary_start = current_frame.timestamp
                self.target_goal_x = target_goal_x
                self.att_team = att_team

        elif self.state == "WAITING_KICK":
            # بررسی خروج ناگهانی از نقطه با سرعت بالا
            if len(frame_buffer) >= 2:
                prev_f = frame_buffer[-2]
                dt = max(0.005, current_frame.timestamp - prev_f.timestamp)
                v_ball = GeometryEngine.dist_3d(current_frame.ball, prev_f.ball) / dt
                vx_att = (current_frame.ball[0] - prev_f.ball[0]) * (1 if self.target_goal_x > 0 else -1)

                if v_ball >= 7.0 and vx_att > 0.3:
                    self.penalty_id = id_gen()
                    self.state = "RESOLVING"
                    emit(GameEvent(
                        event_id=self.penalty_id,
                        event_type="Penalty Kick",
                        team=self.att_team,
                        timestamp=current_frame.timestamp,
                        match_time=current_frame.match_time,
                        reliability=EventReliability.PROBABLE,
                        confidence=0.90,
                        position=current_frame.ball,
                        tags=["ضربه پنالتی"]
                    ))

        elif self.state == "RESOLVING":
            # بررسی گل شدن پنالتی
            reached_line = (self.target_goal_x > 0 and bx >= PitchConfig.HALF_LENGTH) or (self.target_goal_x < 0 and bx <= -PitchConfig.HALF_LENGTH)
            if reached_line:
                is_goal = (abs(bz) <= PitchConfig.GOAL_HALF_WIDTH and by <= PitchConfig.GOAL_HEIGHT)
                emit(GameEvent(
                    event_id=id_gen(),
                    event_type="Penalty Goal" if is_goal else "Penalty Miss",
                    team=self.att_team,
                    timestamp=current_frame.timestamp,
                    match_time=current_frame.match_time,
                    reliability=EventReliability.PROBABLE,
                    confidence=0.94,
                    position=current_frame.ball,
                    related_event_ids=[self.penalty_id] if self.penalty_id else [],
                    tags=["گل پنالتی ⚽" if is_goal else "پنالتی از دست رفته ❌"]
                ))
                self.state = "IDLE"
            elif (current_frame.timestamp - self.stationary_start) > 4.0:
                self.state = "IDLE"

# =====================================================================
# ۲۲. آشکارساز اپیزود فشار (PressureEpisodeDetector)
# ---------------------------------------------------------------------
# Pressure Episode: فشار تدریجی بر حامل توپ؛ impact ملایم و تدریجی با
# duration / avg_pressure / max_pressure
# =====================================================================
class PressureEpisodeDetector:
    def __init__(self, cfg: MomentumScoringConfig):
        self.cfg = cfg
        self.active = False
        self.start_mt = 0.0
        self.sum_pressure = 0.0
        self.max_pressure = 0
        self.sample_count = 0
        self.relief_since: Optional[float] = None
        self.last_mt = 0.0

    def reset(self):
        self.active = False
        self.sum_pressure = 0.0
        self.max_pressure = 0
        self.sample_count = 0
        self.relief_since = None

    def _collect(self, end_mt: float) -> Dict[str, float]:
        duration = max(0.0, end_mt - self.start_mt)
        avg = (self.sum_pressure / self.sample_count) if self.sample_count else 0.0
        stats = {"duration": duration, "avg_pressure": avg, "max_pressure": float(self.max_pressure)}
        self.reset()
        return stats

    def update(self, frame: SnapshotFrame, att_team: Optional[str], att_dir: int) -> Optional[Dict[str, float]]:
        self.last_mt = frame.match_time
        if not att_team:
            return None

        attackers = [p for p in frame.players if p["team"] == att_team]
        defenders = [p for p in frame.players if p["team"] != att_team]
        bx, bz, _ = frame.ball

        carrier, carrier_dist = closest_player(bx, bz, attackers)
        pressure = 0
        if carrier and carrier_dist <= self.cfg.PRESSURE_CARRIER_RADIUS:
            for d in defenders:
                if GeometryEngine.dist_2d((d["x"], d["z"]), (carrier["x"], carrier["z"])) <= self.cfg.PRESSURE_RADIUS:
                    pressure += 1

        finished = None
        if pressure > 0:
            if not self.active:
                self.active = True
                self.start_mt = frame.match_time
                self.sum_pressure = 0.0
                self.max_pressure = 0
                self.sample_count = 0
                self.relief_since = None
            self.sum_pressure += pressure
            self.sample_count += 1
            if pressure > self.max_pressure:
                self.max_pressure = pressure
            self.relief_since = None
        elif self.active:
            if self.relief_since is None:
                self.relief_since = frame.match_time
            elif (frame.match_time - self.relief_since) >= self.cfg.PRESSURE_RELIEF_TIME:
                finished = self._collect(frame.match_time)
        return finished

    def force_finish(self, end_mt: float) -> Optional[Dict[str, float]]:
        """بستن اپیزود در تغییر مالکیت"""
        if not self.active:
            return None
        return self._collect(end_mt if end_mt is not None else self.last_mt)

# =====================================================================
# ۲۳. موتور گذارها (TransitionEngine — Counterattack / Attacking Transition)
# =====================================================================
class TransitionEngine:
    def __init__(self):
        self.flagged: Dict[int, set] = {}

    def reset(self):
        self.flagged.clear()

    def update(self, seq: PossessionSequence, frame: SnapshotFrame, att_dir: int,
               cfg: MomentumScoringConfig, emit, id_gen):
        flags = self.flagged.setdefault(seq.seq_id, set())
        elapsed = frame.match_time - seq.start_time
        bx_att = frame.ball[0] * att_dir

        # ضدحمله: شروع از زمین خودی، رسیدن سریع به یک‌سوم هجومی با پاس‌های محدود
        if "counter" not in flags:
            if (elapsed <= cfg.COUNTERATTACK_WINDOW and bx_att >= PitchConfig.FINAL_THIRD_X
                    and seq.pass_count <= 3 and seq.start_ball_x <= 10.0):
                flags.add("counter")
                flags.add("transition")
                emit(GameEvent(
                    event_id=id_gen(),
                    event_type="Counterattack",
                    team=seq.team,
                    timestamp=frame.timestamp,
                    match_time=frame.match_time,
                    reliability=EventReliability.PROBABLE,
                    confidence=0.80,
                    position=frame.ball,
                    tags=["ضدحمله", f"{elapsed:.1f}s"]
                ))
                return

        # انتقال هجومی عادی (وزن کمتر از ضدحمله)
        if "transition" not in flags:
            if elapsed <= cfg.TRANSITION_WINDOW and bx_att >= 0.0 and seq.start_ball_x < 0.0:
                flags.add("transition")
                emit(GameEvent(
                    event_id=id_gen(),
                    event_type="Attacking Transition",
                    team=seq.team,
                    timestamp=frame.timestamp,
                    match_time=frame.match_time,
                    reliability=EventReliability.INFERRED,
                    confidence=0.70,
                    position=frame.ball,
                    tags=["انتقال هجومی", f"{elapsed:.1f}s"]
                ))

# =====================================================================
# ۲۴. موتور یکپارچه Event Detection Engine (لایه مرکزی ثبت و لینک رخداد)
# ---------------------------------------------------------------------
# Pass/Shot فقط از PassEngine و ShotEngine ثبت می‌شوند؛ این موتور هرگز
# Pass یا Shot را از صفر طبقه‌بندی نمی‌کند. رخدادها از Event Bus منتشر
# می‌شوند تا MomentumScoring آن‌ها را به Impact تبدیل کند.
# =====================================================================
class EventDetectionEngine:
    def __init__(self, config: MomentumScoringConfig):
        self.cfg = config
        self.event_bus = EventBus()
        self.events: List[GameEvent] = []
        self.sequences: List[PossessionSequence] = []
        self.current_seq: Optional[PossessionSequence] = None
        self._next_id = 1

        self.penalty_detector = PenaltyDetector()
        self.opportunity_engine = OpportunityEngine()
        self.pressure_detector = PressureEpisodeDetector(config)
        self.transition_engine = TransitionEngine()

        self.prev_ball_in_f3 = {"Home": False, "Away": False}
        self.prev_ball_in_box = {"Home": False, "Away": False}
        self.zone_last: Dict[str, Dict[str, float]] = {"Home": {}, "Away": {}}

    # -------------------------------------------------------------
    def reset(self):
        self.events.clear()
        self.sequences.clear()
        self.current_seq = None
        self._next_id = 1
        self.penalty_detector.reset()
        self.opportunity_engine = OpportunityEngine()
        self.pressure_detector.reset()
        self.transition_engine.reset()
        self.prev_ball_in_f3 = {"Home": False, "Away": False}
        self.prev_ball_in_box = {"Home": False, "Away": False}
        self.zone_last = {"Home": {}, "Away": {}}

    def generate_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def get_event(self, event_id: int) -> Optional[GameEvent]:
        for ev in reversed(self.events):
            if ev.event_id == event_id:
                return ev
        return None

    def _emit(self, event: GameEvent):
        """ثبت در Event Stream + انتشار روی Unified Event Bus"""
        self.events.append(event)
        # --- نسخه ۲: لینک Event → Sequence (متمرکز) ---
        # هر Chance/Big Chance به زنجیره مالکیت جاری شمارش می‌شود؛
        # (pass/shot در register_pass_event / register_shot_event شمرده می‌شوند)
        if (event.event_type in ("Chance", "Big Chance")
                and self.current_seq and self.current_seq.is_active):
            self.current_seq.chances_created += 1
        self.event_bus.publish(event)

    def _zone_allowed(self, team: str, etype: str, match_time: float, cooldown: Optional[float] = None) -> bool:
        """Cooldown / Deduplication برای رخدادهای zone-based"""
        cd = cooldown if cooldown is not None else self.cfg.ZONE_EVENT_COOLDOWN
        last = self.zone_last[team].get(etype, -1e9)
        if (match_time - last) >= cd:
            self.zone_last[team][etype] = match_time
            return True
        return False

    # -------------------------------------------------------------
    def handle_possession_change(self, new_team: str, match_time: float,
                                 start_x_att: float, timestamp: float,
                                 ball_pos: Tuple[float, float, float]):
        # بستن اپیزود فشار تیم قبلی (پیش از تعویض زنجیره)
        prev_team = self.current_seq.team if (self.current_seq and self.current_seq.is_active) else None
        ep = self.pressure_detector.force_finish(match_time)
        if ep and prev_team:
            self._emit_pressure_event(ep, prev_team, timestamp, match_time, ball_pos)

        # پایان زنجیره قبلی
        if self.current_seq and self.current_seq.is_active:
            self.current_seq.end_time = match_time
            self.current_seq.duration = max(0.1, match_time - self.current_seq.start_time)
            self.current_seq.territorial_gain = self.current_seq.max_ball_x - self.current_seq.start_ball_x
            self.current_seq.ending_reason = "از دست دادن مالکیت"
            self.current_seq.is_active = False

        # آغاز زنجیره جدید
        new_seq = PossessionSequence(
            seq_id=len(self.sequences) + 1,
            team=new_team,
            start_time=match_time,
            end_time=None,
            duration=0.0,
            start_ball_x=start_x_att,
            max_ball_x=start_x_att,
            territorial_gain=0.0,
            pass_count=0,
            shot_count=0,
            final_third_entries=0,
            box_entries=0,
            chances_created=0
        )
        self.sequences.append(new_seq)
        self.current_seq = new_seq

        # ثبت رویداد انتقال مالکیت (وزن بسیار کم/صفر — بیشتر برای زنجیره رویدادها)
        self._emit(GameEvent(
            event_id=self.generate_id(),
            event_type="Possession Change",
            team=new_team,
            timestamp=timestamp,
            match_time=match_time,
            reliability=EventReliability.CERTAIN,
            confidence=1.0,
            position=ball_pos,
            tags=["تغییر مالکیت", f"تیم جدید: {new_team}"]
        ))

    # -------------------------------------------------------------
    def _emit_pressure_event(self, stats: Dict[str, float], team: str,
                             timestamp: float, match_time: float,
                             ball_pos: Tuple[float, float, float]):
        if stats["duration"] >= self.cfg.PRESSURE_MIN_DURATION and stats["avg_pressure"] >= self.cfg.PRESSURE_MIN_AVG:
            self._emit(GameEvent(
                event_id=self.generate_id(),
                event_type="Pressure Episode",
                team=team,
                timestamp=timestamp,
                match_time=match_time,
                reliability=EventReliability.PROBABLE,
                confidence=0.75,
                position=ball_pos,
                metadata={
                    "duration": round(stats["duration"], 1),
                    "avg_pressure": round(stats["avg_pressure"], 2),
                    "max_pressure": stats["max_pressure"]
                },
                tags=[f"فشار {stats['duration']:.0f} ثانیه‌ای",
                      f"میانگین فشار {stats['avg_pressure']:.1f}",
                      f"اوج فشار {stats['max_pressure']:.0f}"]
            ))

    # -------------------------------------------------------------
    def _detect_corner(self, current_frame: SnapshotFrame, att_team: Optional[str], att_dir: int):
        if not att_team:
            return
        bx, bz, _ = current_frame.ball
        # توپ در محدوده قوس کرنر سمت حمله تیم مالک
        if (bx * att_dir) >= 48.0 and abs(bz) >= 29.0:
            if self._zone_allowed(att_team, "Corner", current_frame.match_time, self.cfg.CORNER_COOLDOWN):
                self._emit(GameEvent(
                    event_id=self.generate_id(),
                    event_type="Corner",
                    team=att_team,
                    timestamp=current_frame.timestamp,
                    match_time=current_frame.match_time,
                    reliability=EventReliability.INFERRED,
                    confidence=0.65,
                    position=current_frame.ball,
                    tags=["کرنر (استنباطی)"]
                ))

    def _detect_goal_kick(self, frame_buffer: deque, current_frame: SnapshotFrame, team1_att_dir: int):
        bx, bz, _ = current_frame.ball
        if abs(bx) < 47.5 or abs(bz) > 9.2:
            return
        # تیم مدافع دروازه نزدیک توپ
        if bx < 0:
            defending = "Home" if team1_att_dir == 1 else "Away"
        else:
            defending = "Away" if team1_att_dir == 1 else "Home"
        if current_frame.possession != defending:
            return
        # سکون نسبی توپ (ضربه دروازه از نقطه ثابت)
        if len(frame_buffer) >= 5:
            prev_f = frame_buffer[-4]
            dt = max(0.01, current_frame.timestamp - prev_f.timestamp)
            speed = GeometryEngine.dist_3d(current_frame.ball, prev_f.ball) / dt
            if speed > 2.5:
                return
        if self._zone_allowed(defending, "Goal Kick", current_frame.match_time, self.cfg.GOAL_KICK_COOLDOWN):
            self._emit(GameEvent(
                event_id=self.generate_id(),
                event_type="Goal Kick",
                team=defending,
                timestamp=current_frame.timestamp,
                match_time=current_frame.match_time,
                reliability=EventReliability.INFERRED,
                confidence=0.60,
                position=current_frame.ball,
                tags=["ضربه دروازه (استنباطی)"]
            ))

    # -------------------------------------------------------------
    def process_frame(self, frame_buffer: deque, current_frame: SnapshotFrame, team1_att_dir: int):
        att_team = current_frame.possession
        if not att_team: return
        att_dir = team1_att_dir if att_team == "Home" else -team1_att_dir

        bx, bz, by = current_frame.ball
        bx_att = bx * att_dir

        # به‌روزرسانی زندهٔ زنجیره مالکیت (نسخه ۲ — UI همان Row را Live آپدیت می‌کند)
        if self.current_seq and self.current_seq.is_active:
            if bx_att > self.current_seq.max_ball_x:
                self.current_seq.max_ball_x = bx_att
            # مدت و پیشروی در هر فریم زنده به‌روزرسانی می‌شود (نه فقط هنگام بستن)
            self.current_seq.duration = max(0.0, current_frame.match_time - self.current_seq.start_time)
            self.current_seq.territorial_gain = self.current_seq.max_ball_x - self.current_seq.start_ball_x

        # ۱. ورود به مناطق (Zone Entries) با cooldown ضد اشباع
        in_f3 = (bx_att >= PitchConfig.FINAL_THIRD_X)
        if in_f3 and not self.prev_ball_in_f3[att_team]:
            if self.current_seq: self.current_seq.final_third_entries += 1
            if self._zone_allowed(att_team, "Final Third Entry", current_frame.match_time):
                self._emit(GameEvent(
                    event_id=self.generate_id(),
                    event_type="Final Third Entry",
                    team=att_team,
                    timestamp=current_frame.timestamp,
                    match_time=current_frame.match_time,
                    reliability=EventReliability.CERTAIN,
                    confidence=0.98,
                    position=current_frame.ball,
                    tags=["ورود به یک‌سوم هجومی"]
                ))
        self.prev_ball_in_f3[att_team] = in_f3

        in_box = (bx_att >= PitchConfig.PENALTY_BOX_X and abs(bz) <= PitchConfig.PENALTY_BOX_HALF_Z)
        if in_box and not self.prev_ball_in_box[att_team]:
            if self.current_seq: self.current_seq.box_entries += 1
            if self._zone_allowed(att_team, "Penalty Area Entry", current_frame.match_time):
                self._emit(GameEvent(
                    event_id=self.generate_id(),
                    event_type="Penalty Area Entry",
                    team=att_team,
                    timestamp=current_frame.timestamp,
                    match_time=current_frame.match_time,
                    reliability=EventReliability.CERTAIN,
                    confidence=0.99,
                    position=current_frame.ball,
                    tags=["ورود به محوطه جریمه"]
                ))
        self.prev_ball_in_box[att_team] = in_box

        # ۲. موقعیت‌های خطرناک (Chances)
        self.opportunity_engine.evaluate(current_frame, att_team, att_dir, self._emit, self.generate_id)

        # ۳. پنالتی (مستقل از شمارنده شوت)
        self.penalty_detector.update(frame_buffer, current_frame, team1_att_dir, self._emit, self.generate_id)

        # ۴. اپیزود فشار
        ep = self.pressure_detector.update(current_frame, att_team, att_dir)
        if ep:
            self._emit_pressure_event(ep, att_team, current_frame.timestamp, current_frame.match_time, current_frame.ball)

        # ۵. ضدحمله / انتقال هجومی (یک‌بار در هر زنجیره)
        if self.current_seq and self.current_seq.is_active:
            self.transition_engine.update(self.current_seq, current_frame, att_dir, self.cfg, self._emit, self.generate_id)

        # ۶. کرنر / ضربه دروازه (استنباطی zone-based)
        self._detect_corner(current_frame, att_team, att_dir)
        self._detect_goal_kick(frame_buffer, current_frame, team1_att_dir)

    # -------------------------------------------------------------
    def register_pass_event(self, pass_data: PassEventData) -> GameEvent:
        """PassEngine.generate_event() → EventDetectionEngine.register_pass_event()"""
        if self.current_seq and self.current_seq.is_active:
            self.current_seq.pass_count += 1

        ev_id = self.generate_id()
        pass_data.event_id = ev_id

        ev = GameEvent(
            event_id=ev_id,
            event_type=f"Pass ({pass_data.pass_type})",
            team=pass_data.team,
            timestamp=time.time(),
            match_time=pass_data.match_time,
            reliability=EventReliability.CERTAIN,
            confidence=pass_data.confidence,
            position=pass_data.start_ball,
            metadata={
                "passer": pass_data.passer_seat,
                "receiver": pass_data.receiver_seat,
                "dist": pass_data.distance,
                "flight_t": pass_data.flight_time,
                "threat_score": pass_data.threat_score,
                "is_success": pass_data.is_success,
                "forward_progress": pass_data.forward_progress
            },
            tags=["موفق ✅" if pass_data.is_success else "ناموفق ❌"] + pass_data.tags
        )
        self._emit(ev)

        # شکستن خط دفاعی: از روی تگ‌های Classifier واقعی پاس (بدون بازسازی منطق پاس)
        if pass_data.is_success and "پشت دفاع" in pass_data.tags and pass_data.forward_progress >= 6.0:
            if self._zone_allowed(pass_data.team, "Defensive Line Break", pass_data.match_time, self.cfg.LINE_BREAK_COOLDOWN):
                self._emit(GameEvent(
                    event_id=self.generate_id(),
                    event_type="Defensive Line Break",
                    team=pass_data.team,
                    timestamp=time.time(),
                    match_time=pass_data.match_time,
                    reliability=EventReliability.PROBABLE,
                    confidence=0.82,
                    position=pass_data.end_ball,
                    related_event_ids=[ev_id],
                    metadata={"source_pass": ev_id},
                    tags=["شکست خط دفاعی"]
                ))
        return ev

    # -------------------------------------------------------------
    def register_shot_event(self, shot_data: ShotEventData) -> GameEvent:
        """ShotEngine → EventDetectionEngine.register_shot_event()"""
        if self.current_seq and self.current_seq.is_active:
            self.current_seq.shot_count += 1

        shot_id = self.generate_id()
        shot_data.event_id = shot_id
        rel_ids = []

        # --- نسخه ۲: پیوند Chance → Shot فقط بر اساس MATCH TIME ---
        # (Wall Clock بعد از گل/توقف/پخش مجدد حرکت می‌کند ولی ساعت بازی متوقف است؛
        #  بنابراین رابطه رویدادها فقط با زمان بازی معتبر است.)
        # شرط: 0 <= shot_match_time - chance_match_time <= 3.0
        for ev in reversed(self.events[-10:]):
            if ev.event_type in ("Chance", "Big Chance") and ev.team == shot_data.team:
                dt_match = shot_data.match_time - ev.match_time
                if 0.0 <= dt_match <= 3.0:
                    rel_ids.append(ev.event_id)
                    ev.related_event_ids.append(shot_id)
                    break

        ev = GameEvent(
            event_id=shot_id,
            event_type=f"Shot ({shot_data.primary_type})",
            team=shot_data.team,
            timestamp=time.time(),
            match_time=shot_data.match_time,
            reliability=EventReliability.CERTAIN,
            confidence=shot_data.confidence,
            position=shot_data.contact_ball,
            related_event_ids=rel_ids,
            metadata={
                "shooter": shot_data.shooter_seat,
                "speed": shot_data.max_speed_kmh,
                "dist": shot_data.distance_to_goal,
                "outcome": shot_data.outcome,
                "primary_type": shot_data.primary_type,
                "pre_shot_threat": shot_data.pre_shot_threat,   # Opportunity Value
                "final_threat": shot_data.final_threat,         # Event / Momentum Impact
                "is_goal": shot_data.is_goal,
                "is_on_target": shot_data.is_on_target
            },
            tags=[shot_data.outcome] + shot_data.tags
        )
        self._emit(ev)

        # ثبت صریح گل از روی پرچم بولی بدون تکیه بر رشته متنی
        # (Flag is_goal + related_event_ids → سیاست Contribution جلوی دوبار امتیاز را می‌گیرد)
        if shot_data.is_goal:
            self._emit(GameEvent(
                event_id=self.generate_id(),
                event_type="Goal ⚽",
                team=shot_data.team,
                timestamp=time.time() + 0.05,
                match_time=shot_data.match_time,
                reliability=EventReliability.CERTAIN,
                confidence=1.0,
                position=shot_data.contact_ball,
                related_event_ids=[shot_id],
                metadata={"source_shot": shot_id, "shooter": shot_data.shooter_seat},
                tags=["گل مسابقه", f"صندلی {shot_data.shooter_seat}"]
            ))
        return ev

    # -------------------------------------------------------------
    def register_goal_event(self, team: str, match_time: float,
                            source: str = "memory-hook",
                            shooter_seat: Optional[int] = None) -> GameEvent:
        """
        نسخه ۴ — ثبت گل «فقط» از طریق هوک حافظه (GoalHooker).
        مسیر قدیمی (عبور توپ از خط + چارچوب دروازه) حذف شده است.
        مراحل:
          ۱) پیوند به آخرین شوت همین تیم با پنجرهٔ MATCH TIME:
             0 <= goal_t - shot_t <= 4.0 (پرواز توپ/دفاع در این بازه است)
             و ارتقای بازگشتی رخداد شوت به «گل» (metadata + tags).
          ۲) انتشار "Goal ⚽" روی Event Bus → MomentumEngine خودش پاسخ
             تأخیری (Goal Pulse) و Dedup با Penalty Goal را اعمال می‌کند.
        """
        ev_id = self.generate_id()
        rel_ids: List[int] = []

        for ev in reversed(self.events[-12:]):
            if ev.event_type.startswith("Shot") and ev.team == team:
                dt_match = match_time - ev.match_time
                if 0.0 <= dt_match <= 4.0:
                    rel_ids.append(ev.event_id)
                    ev.related_event_ids.append(ev_id)
                    ev.metadata["is_goal"] = True
                    if "گل" not in str(ev.metadata.get("outcome", "")):
                        ev.metadata["outcome"] = "گل قطعی ⚽ (تأیید هوک حافظه)"
                        if "گل قطعی ⚽" not in ev.tags:
                            ev.tags.append("گل قطعی ⚽ (هوک)")
                    break

        ev = GameEvent(
            event_id=ev_id,
            event_type="Goal ⚽",
            team=team,
            timestamp=time.time(),
            match_time=match_time,
            reliability=EventReliability.CERTAIN,
            confidence=1.0,
            position=(0.0, 0.0, 0.0),
            related_event_ids=rel_ids,
            metadata={
                "source": source,
                "shooter": shooter_seat,
                "link_window": "0..4s (Match Time)",
                "counter": "memory [rcx+0x158]/[rcx+0x15C]"
            },
            tags=["گل مسابقه", "هوک حافظه ✅"]
        )
        self._emit(ev)
        return ev

# =====================================================================
# ۲۵. Momentum Engine (مدل Threat/Event Decay بر پایه Match Time)
# ---------------------------------------------------------------------
# HomeMomentum(t)  = Σ HomeEventImpact_i × decay(t - event_time_i)
# AwayMomentum(t)  = Σ AwayEventImpact_i × decay(t - event_time_i)
# NetMomentum(t)   = HomeMomentum(t) - AwayMomentum(t)
# decay(Δt) = exp(-λ Δt) ،  λ = ln(2) / MOMENTUM_HALF_LIFE
#
# نکته حیاتی: Δt همیشه بر حسب GAME TIME است نه Wall Clock.
# اگر Match Time بین دو فریم تغییر نکند، Momentum نیز تغییری نمی‌کند
# (Pause / Replay / Stop → نمودار ثابت می‌ماند).
# =====================================================================
_LN2 = math.log(2.0)

class MomentumEngine:
    def __init__(self, config: MomentumScoringConfig):
        self.cfg = config
        self.impacts: List[EventImpact] = []
        self._impact_index: Dict[int, EventImpact] = {}
        # momentum_history ساختار استاندارد:
        # {"game_time" (زمان خام بازی), "disp_time" (زمان نمایشی با شکاف HT), "home","away","net"}
        self.history: List[Dict[str, float]] = [
            {"game_time": 0.0, "disp_time": 0.0, "home": 0.0, "away": 0.0, "net": 0.0,
             "phase": None}
        ]
        self._lock = threading.RLock()
        self._last_t = 0.0
        self._last_sample_t = -1.0
        # --- نسخه ۲: شکاف نمایشی بین دو نیمه (HT Gap) ---
        # display_offset = اختافهٔ ثابتی که به زمان بازیِ نیمه دوم برای نمایش
        # اضافه می‌شود تا بین دو نیمه فضای خالی کوچکی با برچسب HT دیده شود.
        self.display_offset: float = 0.0
        # (disp_start, disp_end) شکاف HT برای رندر — None تا قبل از HT
        self.ht_break: Optional[Tuple[float, float]] = None
        # --- نسخه ۵ ---
        # نیمهٔ جاری از دید موتور (برای مُهر نیمه روی پالس/مارکر گل‌ها)
        self.half_number: int = 1
        # مارکرهای مستقیم گل از هوک حافظه (مسیر مستقل از Event Bus) —
        # هر آیتم: {team, game_time, disp_time (فریز), half, wall}
        self.hook_goal_markers: List[Dict[str, float]] = []
        # --- نسخهٔ ۱۰٫۲۷ — مارکرهای مستقیم کارت قرمز (همان الگوی گل) ---
        # هر آیتم: {team, game_time (=لحظهٔ صدور), disp_time (فریز), half, wall}
        self.red_card_markers: List[Dict[str, float]] = []
        # شکاف‌های نمایشی اضافی (تور ایمنی resync_clock) — بدون برچسب HT
        self.extra_breaks: List[Tuple[float, float]] = []
        # --- نسخه ۱۰٫۲: درزِ چسباندن شکاف توقف (برای صاف‌سازی با خط صاف) ---
        # {"a": ایندکس آخرین نمونهٔ قبل از توقف, "b": ایندکس اولین نمونهٔ بعد از آن}
        self._glue_smooth: Optional[Dict[str, int]] = None
        # --- نسخهٔ ۱۰٫۱۵ — مُهر فاز Lifecycle روی نمونه‌های تاریخچه ---
        # Worker فاز جاری (HALF_1/HALF_2/ET1/ET2/…) را اینجا می‌نویسد و هر
        # نمونهٔ جدید (update/set_half_break/resync/reset) آن را حمل می‌کند.
        # مصرف: گیت فازِ فرودهای «بدون سقوط» ری‌استارت در _tv_timeline.
        self.phase_label: Optional[str] = None

    def set_phase_label(self, label: Optional[str]):
        """تنظیم مُهر فاز جاری (از Worker — با تغییر _match_phase همگام می‌شود)."""
        try:
            self.phase_label = (str(label) if label is not None else None)
        except Exception:
            self.phase_label = None

    # -------------------------------------------------------------
    # اشتراک روی Unified Event Bus
    # -------------------------------------------------------------
    def on_event(self, event: GameEvent):
        with self._lock:
            impact = self._score_event(event)
            if impact is not None:
                self.impacts.append(impact)
                self._impact_index[impact.source_event_id] = impact
            # سیاست Contribution / Deduplication پس از دریافت رویدادهای وابسته
            self._apply_post_links(event)

    def get_impact(self, source_event_id: int) -> Optional[EventImpact]:
        with self._lock:
            return self._impact_index.get(source_event_id)

    # -------------------------------------------------------------
    # نگاشت Event → EventImpact (تمام وزن‌ها از MomentumScoringConfig)
    # -------------------------------------------------------------
    def _reliability_multiplier(self, reliability: EventReliability) -> float:
        if reliability == EventReliability.CERTAIN:
            return self.cfg.CERTAIN_MULTIPLIER
        if reliability == EventReliability.PROBABLE:
            return self.cfg.PROBABLE_MULTIPLIER
        return self.cfg.INFERRED_MULTIPLIER

    def _make_impact(self, event: GameEvent, raw_threat: float, base_weight: float,
                     sign: int = 1, note: str = "", is_goal_pulse: bool = False,
                     goal_time: float = 0.0, peak_time: float = 0.0,
                     apply_conf: Optional[bool] = None) -> EventImpact:
        rel_mult = self._reliability_multiplier(event.reliability)
        # نسخهٔ ۱۰٫۱۲ — apply_conf: برای شوت‌ها می‌تواند ApplyConfidence سراسری
        # را لغو کند (SHOT_APPLY_CONFIDENCE=False → امتیاز شوت = Final Threat).
        _apply_conf = self.cfg.APPLY_CONFIDENCE if apply_conf is None else bool(apply_conf)
        conf = event.confidence if _apply_conf else 1.0
        final = base_weight * rel_mult * conf * sign
        # نسخه ۵: موقعیت نمایشی مارکر گل در لحظهٔ ثبت فریز می‌شود
        goal_disp = -1.0
        if is_goal_pulse:
            with self._lock:
                goal_disp = float(goal_time) + self.display_offset
                goal_half = int(self.half_number)
        else:
            goal_half = 1
        return EventImpact(
            source_event_id=event.event_id,
            event_type=event.event_type,
            team=event.team,
            match_time=event.match_time,
            raw_threat=float(raw_threat),
            base_weight=float(base_weight),
            reliability=event.reliability.value,
            confidence=float(event.confidence),
            reliability_multiplier=rel_mult,
            sign=sign,
            final_impact=final,
            note=note,
            is_goal_pulse=is_goal_pulse,
            goal_time=goal_time,
            peak_time=peak_time,
            goal_half=goal_half,
            goal_disp_time=goal_disp,
            linked_ids=list(event.related_event_ids)
        )

    def _score_event(self, ev: GameEvent) -> Optional[EventImpact]:
        cfg = self.cfg
        t = ev.event_type
        md = ev.metadata

        # ---- Pass: base = threat_score × success/failure multiplier ----
        if t.startswith("Pass"):
            threat = float(md.get("threat_score", 0) or 0)
            is_success = bool(md.get("is_success", True))
            mult = cfg.PASS_SUCCESS_MULTIPLIER if is_success else cfg.PASS_FAILURE_MULTIPLIER
            return self._make_impact(ev, raw_threat=threat, base_weight=threat * mult,
                                     note="success" if is_success else "failure")

        # ---- Shot: base = final_threat (pre_shot_threat فقط ذخیره می‌شود) ----
        # نسخهٔ ۱۰٫۱۲ — سیاست جدید امتیاز شوت (درخواست کاربر):
        #   * بدون ضریب اطمینان → امتیاز مومنتوم = Final Threat ابزار مستقل؛
        #   * شوت‌های غیرگل کف معنادار (SHOT_MIN_IMPACT) دارند — حتی شوتِ
        #     دور از چارچوب نقش مشهود در مومنتوم دارد؛
        #   * شوت گل‌شده (استثنای کاربر) × GOAL_LINKED_SHOT_RATIO می‌شود چون
        #     امتیاز اصلی را Goal (پالس ۱۰۰) می‌دهد — بدون شمارهٔ دوگانه.
        if t.startswith("Shot"):
            final_threat = float(md.get("final_threat", 0) or 0)
            base = final_threat * cfg.SHOT_WEIGHT
            note = ""
            # شوتِ گل‌شده سهم کاهش‌یافته می‌گیرد چون Goal Event امتیاز اصلی را می‌دهد
            if md.get("is_goal"):
                base *= cfg.GOAL_LINKED_SHOT_RATIO
                note = "goal-linked"
            else:
                # شوت پنالتی با Penalty Goal/Miss رقابتی می‌شود
                if md.get("primary_type") == "پنالتی":
                    base *= cfg.PENALTY_SHOT_LINKED_RATIO
                    note = "penalty"
                # کف معنادار — شوت‌های غیرگل هرگز ناچیز نمی‌مانند
                if base < cfg.SHOT_MIN_IMPACT:
                    base = float(cfg.SHOT_MIN_IMPACT)
                    note = (note + "+min-floor" if note else "min-floor")
            return self._make_impact(ev, raw_threat=final_threat, base_weight=base,
                                     note=note or "final-threat",
                                     apply_conf=cfg.SHOT_APPLY_CONFIDENCE)

        # ---- Goal: پاسخ تأخیری (Goal Response / Goal Pulse — نسخه ۲) ----
        # گل دیگر spike لحظه‌ای نیست؛ Contribution آن منحنی پاسخ دارد:
        #   t < t_goal                     → 0
        #   t_goal ≤ t < t_goal + DELAY    → افزایش نرم (raised-cosine)
        #   تا t_goal + DELAY + WIDTH      → فلات اوج (مقدار کامل)
        #   پس از آن                       → decay نمایی با همان نیم‌عمر مومنتوم
        # کل منحنی تابعی خالص از MATCH TIME است؛ در Pause خودکار منجمد می‌شود
        # و هیچ ساعت جعلی (Wall Clock) تولید نمی‌شود.
        # توجه: تطابق دقیق — «Goal Kick» نباید به‌عنوان گل امتیاز بگیرد
        if t.startswith("Goal") and "Kick" not in t:
            return self._make_impact(
                ev, raw_threat=cfg.GOAL_WEIGHT, base_weight=cfg.GOAL_WEIGHT,
                note="goal-pulse (delayed peak)",
                is_goal_pulse=True,
                goal_time=ev.match_time,
                peak_time=ev.match_time + cfg.GOAL_PEAK_DELAY
            )

        # ---- Chance / Big Chance ----
        if t == "Big Chance":
            return self._make_impact(ev, raw_threat=cfg.BIG_CHANCE_WEIGHT, base_weight=cfg.BIG_CHANCE_WEIGHT)
        if t == "Chance":
            return self._make_impact(ev, raw_threat=cfg.CHANCE_WEIGHT, base_weight=cfg.CHANCE_WEIGHT)

        # ---- Penalty ----
        if t == "Penalty Kick":
            return self._make_impact(ev, raw_threat=cfg.PENALTY_WEIGHT, base_weight=cfg.PENALTY_WEIGHT)
        if t == "Penalty Goal":
            # Dedup: اگر Goal همین رخداد قبلا ثبت شده، فقط دلتای خاص پنالتی اعمال شود
            has_parallel_goal = any(
                i.event_type.startswith("Goal") and "Kick" not in i.event_type
                and i.team == ev.team
                and abs(i.match_time - ev.match_time) <= cfg.PENALTY_GOAL_DEDUP_WINDOW
                for i in self.impacts
            )
            if has_parallel_goal:
                w = cfg.PENALTY_GOAL_DELTA_WEIGHT
                return self._make_impact(ev, raw_threat=w, base_weight=w,
                                         note="delta (goal already counted)")
            # Penalty Goal مستقل (بدون Goal موازی) → خودش پاسخ گل را حمل می‌کند
            return self._make_impact(
                ev, raw_threat=cfg.PENALTY_GOAL_WEIGHT, base_weight=cfg.PENALTY_GOAL_WEIGHT,
                note="goal-pulse (penalty, standalone)",
                is_goal_pulse=True,
                goal_time=ev.match_time,
                peak_time=ev.match_time + cfg.GOAL_PEAK_DELAY
            )
        if t == "Penalty Miss":
            sign = -1 if cfg.PENALTY_MISS_NEGATIVE else 1
            return self._make_impact(ev, raw_threat=cfg.PENALTY_MISS_WEIGHT,
                                     base_weight=cfg.PENALTY_MISS_WEIGHT, sign=sign, note="miss")

        # ---- Pressure Episode: impact ملایم و تدریجی ----
        if t == "Pressure Episode":
            duration = float(md.get("duration", 0) or 0)
            avg_p = float(md.get("avg_pressure", 0) or 0)
            max_p = float(md.get("max_pressure", 0) or 0)
            w = (cfg.PRESSURE_BASE_WEIGHT
                 + duration * cfg.PRESSURE_DURATION_FACTOR
                 + avg_p * cfg.PRESSURE_INTENSITY_FACTOR
                 + max_p * 0.3)
            w = min(w, cfg.PRESSURE_MAX_WEIGHT)
            return self._make_impact(ev, raw_threat=w, base_weight=w, note="gradual")

        # ---- Counterattack / Transition / Line Break ----
        if t == "Counterattack":
            return self._make_impact(ev, raw_threat=cfg.COUNTERATTACK_WEIGHT, base_weight=cfg.COUNTERATTACK_WEIGHT)
        if t == "Attacking Transition":
            return self._make_impact(ev, raw_threat=cfg.TRANSITION_WEIGHT, base_weight=cfg.TRANSITION_WEIGHT)
        if t == "Defensive Line Break":
            return self._make_impact(ev, raw_threat=cfg.LINE_BREAK_WEIGHT, base_weight=cfg.LINE_BREAK_WEIGHT)

        # ---- Zone Entries ----
        if t == "Final Third Entry":
            return self._make_impact(ev, raw_threat=cfg.FINAL_THIRD_ENTRY_WEIGHT, base_weight=cfg.FINAL_THIRD_ENTRY_WEIGHT)
        if t == "Penalty Area Entry":
            return self._make_impact(ev, raw_threat=cfg.BOX_ENTRY_WEIGHT, base_weight=cfg.BOX_ENTRY_WEIGHT)
        if t == "Corner":
            return self._make_impact(ev, raw_threat=cfg.CORNER_WEIGHT, base_weight=cfg.CORNER_WEIGHT)
        if t == "Goal Kick":
            return self._make_impact(ev, raw_threat=cfg.GOAL_KICK_WEIGHT, base_weight=cfg.GOAL_KICK_WEIGHT)

        # ---- Possession Change: بدون impact معنادار (برای زنجیره رویدادها) ----
        if t == "Possession Change":
            if cfg.POSSESSION_CHANGE_WEIGHT <= 0:
                return None
            return self._make_impact(ev, raw_threat=cfg.POSSESSION_CHANGE_WEIGHT, base_weight=cfg.POSSESSION_CHANGE_WEIGHT)

        return None

    # -------------------------------------------------------------
    # سیاست Contribution / Deduplication (جلوگیری از Double Counting)
    # -------------------------------------------------------------
    def _apply_post_links(self, ev: GameEvent):
        cfg = self.cfg
        # Shot → Chance لینک‌شده سهم کاهش‌یافته می‌گیرد
        if ev.event_type.startswith("Shot") and ev.related_event_ids:
            for rid in ev.related_event_ids:
                imp = self._impact_index.get(rid)
                if imp and imp.event_type in ("Chance", "Big Chance"):
                    imp.base_weight *= cfg.SHOT_LINKED_CHANCE_RATIO
                    imp.final_impact *= cfg.SHOT_LINKED_CHANCE_RATIO
                    imp.note = "capped (linked→shot)"
        # Penalty Goal / Penalty Miss → خود Penalty Kick سهم کاهش‌یافته می‌گیرد
        if ev.event_type in ("Penalty Goal", "Penalty Miss") and ev.related_event_ids:
            for rid in ev.related_event_ids:
                imp = self._impact_index.get(rid)
                if imp and imp.event_type == "Penalty Kick":
                    imp.base_weight *= cfg.PENALTY_KICK_LINKED_RATIO
                    imp.final_impact *= cfg.PENALTY_KICK_LINKED_RATIO
                    imp.note = "linked→penalty-result"
        # --- نسخه ۲: Dedup دوطرفه — Goal موازی که «بعد از» Penalty Goal مستقل
        # می‌رسد؛ Penalty Goal قبلی (که pulse کامل داشت) به دلتا تنزیل می‌شود
        # تا گل هرگز دو بار (و با دو pulse) شمرده نشود.
        if ev.event_type.startswith("Goal") and "Kick" not in ev.event_type:
            # --- نسخه ۴: گلِ تأییدشدهٔ هوک → شوت لینک‌شده سهم کاهش‌یافته
            # می‌گیرد (GOAL_LINKED_SHOT_RATIO) تا گل هرگز دو بار امتیاز نگیرد؛
            # دقیقاً همان سیاستی که برای is_goal در لحظهٔ ثبت شوت اعمال می‌شد.
            for rid in ev.related_event_ids:
                imp = self._impact_index.get(rid)
                if (imp and imp.event_type.startswith("Shot")
                        and "goal-linked" not in (imp.note or "")):
                    imp.base_weight *= cfg.GOAL_LINKED_SHOT_RATIO
                    imp.final_impact *= cfg.GOAL_LINKED_SHOT_RATIO
                    imp.note = "goal-linked (hook)"
            for imp in self.impacts:
                if (imp.event_type == "Penalty Goal"
                        and imp.team == ev.team
                        and not imp.parallel_goal_dedup
                        and abs(imp.match_time - ev.match_time) <= cfg.PENALTY_GOAL_DEDUP_WINDOW):
                    scale = cfg.PENALTY_GOAL_DELTA_WEIGHT / max(1e-6, cfg.PENALTY_GOAL_WEIGHT)
                    imp.base_weight *= scale
                    imp.final_impact *= scale
                    imp.is_goal_pulse = False      # pulse اصلی را Goal حمل می‌کند
                    imp.goal_time = 0.0
                    imp.peak_time = 0.0
                    imp.parallel_goal_dedup = True
                    imp.note = "delta (parallel Goal arrived later)"

    # -------------------------------------------------------------
    # Decay و پاسخ گل (فقط بر اساس Match Time)
    # -------------------------------------------------------------
    def decay_factor(self, dt: float) -> float:
        if dt <= 0:
            return 1.0
        return math.exp(-_LN2 * dt / max(1e-6, self.cfg.MOMENTUM_HALF_LIFE))

    def goal_response_factor(self, imp: EventImpact, t: float) -> float:
        """
        منحنی پاسخ گل (Goal Pulse) — تابعی خالص از زمان بازی:
          t < t_goal                    → 0.0
          t_goal ≤ t < peak_time        → raised-cosine از 0 تا 1
          peak_time ≤ t < peak+W        → 1.0 (فلات اوج)
          t ≥ peak+W                    → decay نمایی با نیم‌عمر مومنتوم
        نکته حیاتی (سناریوی Pause بعد از گل):
          اگر ساعت بازی متوقف بماند، t ثابت است و خروجی این تابع نیز ثابت
          می‌ماند؛ هیچ اجباری برای جلو بردن زمان وجود ندارد و هرگز از
          Wall Clock برای جلو بردن محور X استفاده نمی‌شود. وقتی بازی از
          45:12 به 45:17 برسد، اوج خودبه‌خود در همان Match Time ظاهر می‌شود.
        """
        dt = t - imp.goal_time
        if dt <= 0:
            return 0.0
        peak_t = imp.peak_time
        if t < peak_t:
            span = max(1e-6, peak_t - imp.goal_time)   # = GOAL_PEAK_DELAY
            u = dt / span
            return 0.5 * (1.0 - math.cos(math.pi * u))
        hold_end = peak_t + self.cfg.GOAL_RESPONSE_WIDTH
        if t < hold_end:
            return 1.0
        return self.decay_factor(t - hold_end)

    def goal_pulse_phase(self, imp: EventImpact, t: float) -> str:
        """فاز فعلی پاسخ گل برای جدول دیباگ"""
        if t < imp.goal_time:
            return "WAITING"
        if t < imp.peak_time:
            return "RISING"
        if t < imp.peak_time + self.cfg.GOAL_RESPONSE_WIDTH:
            return "PEAK/ACTIVE"
        if self.goal_response_factor(imp, t) > 0.01:
            return "DECAYING"
        return "COMPLETED"

    def _compute_unlocked(self, t: float) -> Tuple[float, float, float]:
        home = 0.0
        away = 0.0
        for imp in self.impacts:
            if imp.is_goal_pulse:
                # پاسخ تأخیری گل: صفر قبل از t_goal، اوج در peak_time
                f = self.goal_response_factor(imp, t)
                if f <= 0.0:
                    continue
                v = imp.final_impact * f
            else:
                dt = t - imp.match_time
                if dt < 0:
                    continue
                v = imp.final_impact * self.decay_factor(dt)
            if imp.team == "Home":
                home += v
            else:
                away += v
        return home, away, home - away

    def compute_at(self, t: float) -> Tuple[float, float, float]:
        with self._lock:
            return self._compute_unlocked(t)

    def update(self, current_match_time: float):
        """
        در هر تیک بازی اجرا می‌شود. اگر Match Time جلو نرفته باشد
        (Pause/Replay/Stop) هیچ نمونه و decay جدیدی ثبت نمی‌شود.

        نسخه ۱۰٫۲ — چسباندن شکاف توقف‌ها (حذف قطعهٔ افقی بعد از گل):
        اگر بین دو نمونهٔ متوالی، ساعت بازی بیش از MOMENTUM_GLUE_GAP پرش
        کند (توقف جشن گل/Replay با ساعتِ در حال حرکت)، به‌جای ثبت یک
        نمونهٔ دور در انتهای شکاف (که روی نمودار «پاره‌خط تخت» می‌ساخت)،
        فقط آفستِ نمایش به‌اندازهٔ همان بازهٔ مرده جمع می‌شود؛ نمونهٔ
        بعدی دقیقاً یک interval بعد از آخرین نمونهٔ واقعی می‌نشیند و
        دو قسمت نمودار بدون تغییر شکلِ منحنی به هم می‌چسبند. درزِ محل
        اتصال هم به‌محض رسیدن اولین نمونهٔ بعدی با یک پاره‌خط مستقیم صاف
        می‌شود (_apply_glue_smoothing_locked). شکاف‌های مدیریت‌شدهٔ
        بالا دستی (HT / resync عقبرو) نگهبان NaN دارند و هرگز چسبانده
        نمی‌شوند.
        """
        with self._lock:
            if current_match_time <= self._last_t:
                self._last_t = current_match_time
                return
            # --- نسخه ۱۰٫۲: تشخیص شکاف توقف (فقط وقتی آخرین نمونه واقعی است) ---
            glue_anchor = -1
            if self._last_sample_t >= 0.0 and self.history:
                _last_hist = self.history[-1]
                _is_nan_guard = _last_hist["net"] != _last_hist["net"]
                _gap = float(current_match_time) - float(self._last_sample_t)
                if (not _is_nan_guard) and _gap > self.cfg.MOMENTUM_GLUE_GAP:
                    # بازهٔ مردهٔ توقف از محور نمایش حذف می‌شود: آفست نمایش
                    # طوری تنظیم می‌شود که نمونهٔ بعدی بلافاصله بعد از آخرین
                    # نمونهٔ واقعی بنشیند (دو قسمت می‌چسبند). توجه: انتساب
                    # «مطلق» است نه افزایشی — last_disp خودش حامل همهٔ
                    # تنظیمات قبلی (HT و درزهای پیشین) است و فرمول مطلق
                    # دقیقاً فقط همین بازهٔ مرده را حذف می‌کند.
                    _last_disp = float(_last_hist["disp_time"])
                    self.display_offset = (_last_disp + self.cfg.HISTORY_SAMPLE_INTERVAL
                                           - float(current_match_time))
                    glue_anchor = len(self.history) - 1
            if (current_match_time - self._last_sample_t) >= self.cfg.HISTORY_SAMPLE_INTERVAL:
                home, away, net = self._compute_unlocked(current_match_time)
                self.history.append({
                    "game_time": float(current_match_time),
                    "disp_time": float(current_match_time + self.display_offset),
                    "home": home,
                    "away": away,
                    "net": net,
                    "wall": time.time(),   # نسخهٔ ۱۰٫۱۲ — سکوت واقعی = بریک بزرگ
                    "phase": self.phase_label   # نسخهٔ ۱۰٫۱۵ — مُهر فاز Lifecycle
                })
                self._last_sample_t = current_match_time
                if glue_anchor >= 0:
                    # درزِ چسباندن — با اولین نمونهٔ بعدی، با خط صاف صاف می‌شود
                    self._glue_smooth = {"a": glue_anchor, "b": len(self.history) - 1}
                self._apply_glue_smoothing_locked()
            self._last_t = current_match_time

    def _apply_glue_smoothing_locked(self):
        """
        نسخه ۱۰٫۲ — برطرف کردن شکستگیِ محل چسباندن با یک خط صاف.
        بعد از چسباندن دو قسمت نمودار، به‌محض رسیدن اولین نمونهٔ بعد از
        درز، دو نمونهٔ محل اتصال روی پاره‌خط مستقیمِ «نمونهٔ قبل از توقف
        ← نمونهٔ بعد از درز» بازنویسی می‌شوند تا هیچ زاویهٔ تندی در محل
        درز دیده نشود. فقط همین دو نمونهٔ درز صاف می‌شوند و بقیهٔ
        نمونه‌ها (و زمان‌ها) دست‌نخورده می‌مانند.
        """
        js = self._glue_smooth
        if js is None:
            return
        a, b = int(js["a"]), int(js["b"])
        if (b + 1) >= len(self.history):
            return                        # هنوز نمونهٔ بعدی نرسیده — pending می‌ماند
        self._glue_smooth = None          # یک‌بارمصرف
        if a < 1:
            return                        # لنگرِ قبل از درز وجود ندارد
        L = self.history[a - 1]
        A = self.history[a]
        B = self.history[b]
        R = self.history[b + 1]
        vals = (L["net"], A["net"], B["net"], R["net"])
        if any(v != v for v in vals):     # نگهبان NaN (شکاف HT) → دست نزن
            return
        dL = float(L["disp_time"])
        dR = float(R["disp_time"])
        if dR - dL <= 1e-9:
            return
        for f in ("home", "away", "net"):
            vL = float(L[f])
            vR = float(R[f])
            for s in (A, B):
                u = (float(s["disp_time"]) - dL) / (dR - dL)
                s[f] = vL + u * (vR - vL)

    def set_half_break(self, gap_seconds: float, resume_game_t: Optional[float] = None):
        """
        نسخه ۲ — ثبت انتقال بین دو نیمه (Half-Time):
        نمودار پاک نمی‌شود؛ فقط یک شکاف نمایشی کوچک (برچسب HT) بین آخرین
        نمونهٔ نیمه اول و نمونه‌های نیمه دوم درج می‌شود.
        دو نمونهٔ NaN به‌عنوان نگهبان درج می‌شوند تا خط/ناحیهٔ نمودار روی
        شکاف «پل» نزند. از این پس به زمان بازیِ نمونه‌های جدید offset اضافه
        می‌شود. هیچ عملیاتی بر پایه Wall Clock نیست.
        resume_game_t: اولین زمان بازی نیمه دوم (مثلاً 45:00=2700s) — اگر
        کمتر از آخرین زمان نیمه اول باشد (وقت حتبه‌جبرانی)، offset بر مبنای
        همان نقطه محاسبه می‌شود تا نمونه‌های نیمه دوم هرگز وارد شکاف نشوند.

        نسخه ۵ — رفع باگ «نمودار ابتدای نیمه دوم دیده نمی‌شد»:
        بازی ساعت را برای شروع نیمه دوم به 45:00 برمی‌گرداند؛ در نسخهٔ ۴
        _last_t روی انتهای ثبت‌شدهٔ نیمه اول (مثلاً 45:00+جبرانی) باقی
        می‌ماند و update() تا عبور ساعت بازی از آن نقطه، هیچ نمونه‌ای
        ثبت نمی‌کرد → ابتدای نیمه دوم روی نمودار خالی می‌ماند.
        اکنون ساعت داخلی موتور به base_t (نقطهٔ از سرگیری) برده می‌شود و
        _last_sample_t عمداً یک interval عقب‌تر گذاشته می‌شود تا «اولین
        ثانیهٔ نیمه دوم» بلافاصله (درست بعد از خط سمت راست شکاف) رسم شود.
        """
        with self._lock:
            last = self.history[-1] if self.history else None
            last_disp = float(last["disp_time"]) if last else 0.0
            last_game = float(last["game_time"]) if last else 0.0
            gap = max(10.0, float(gap_seconds))
            base_t = self._last_t
            if resume_game_t is not None:
                base_t = min(self._last_t, float(resume_game_t))
            # نمونه‌های نگهبان NaN — شکست بصری نمودار در شکاف HT
            _now_wall = time.time()
            self.history.append({"game_time": last_game, "disp_time": last_disp,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            self.history.append({"game_time": base_t, "disp_time": last_disp + gap,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            # از سرگیری نیمه دوم: زمان نمایشی = زمان بازی + offset
            self.display_offset = (last_disp + gap) - base_t
            self.ht_break = (last_disp, last_disp + gap)
            # --- نسخه ۵ (قلب فیکس باگ ۲) ---
            self._last_t = base_t
            self._last_sample_t = base_t - max(0.05, self.cfg.HISTORY_SAMPLE_INTERVAL) - 1e-6
            self.half_number = 2

    # -------------------------------------------------------------
    # نسخه ۵ — مارکر مستقیم گل از هوک حافظه (مسیر مستقل از Event Bus)
    # -------------------------------------------------------------
    def add_hook_goal_marker(self, team: str, game_time: float, half: int = 0):
        """
        ثبت مستقیم یک مارکر گل روی نمودار — به‌محض تغییر شمارندهٔ گل هر تیم.
        موقعیت نمایشی (disp_time) در همان لحظه با display_offset جاری فریز
        می‌شود؛ در نتیجه حتی اگر بعداً آفست تغییر کند، مارکر سر جایش می‌ماند.
        """
        with self._lock:
            self.hook_goal_markers.append({
                "team": team,
                "game_time": float(game_time),
                "disp_time": float(game_time) + self.display_offset,
                "half": int(half) if half else int(self.half_number),
                "wall": time.time()
            })

    def get_hook_goal_markers(self) -> List[Dict[str, float]]:
        with self._lock:
            return [dict(m) for m in self.hook_goal_markers]

    def hook_goal_marker_count(self) -> int:
        with self._lock:
            return len(self.hook_goal_markers)

    # -------------------------------------------------------------
    # نسخهٔ ۱۰٫۲۷ — مارکر مستقیم کارت قرمز (همان الگوی گل — عین 2017)
    # -------------------------------------------------------------
    def add_hook_red_card_marker(self, team: str, game_time: float,
                                 half: int = 0,
                                 disp_time: Optional[float] = None):
        """
        ثبت مستقیم یک مارکر کارت قرمز — عین قرارداد گل با این تفاوت که
        disp_time می‌تواند «لحظهٔ صدور» باشد: انتساب تیم کارت چند ثانیه
        بعد از صدور (تماشای بازیکن اخراجی در z=40) انجام می‌شود اما
        مارکر باید روی لحظهٔ صدور بنشیند، نه لحظهٔ تشخیص.
        """
        with self._lock:
            self.red_card_markers.append({
                "team": team,
                "game_time": float(game_time),
                "disp_time": (float(disp_time) if disp_time is not None
                              else float(game_time) + self.display_offset),
                "half": int(half) if half else int(self.half_number),
                "wall": time.time()
            })

    def get_hook_red_card_markers(self) -> List[Dict[str, float]]:
        with self._lock:
            return [dict(m) for m in self.red_card_markers]

    def red_card_marker_count(self) -> int:
        with self._lock:
            return len(self.red_card_markers)

    # -------------------------------------------------------------
    # نسخه ۵ — تور ایمنی: بازگشت ساعت بدون تشخیص HT/بازی جدید
    # -------------------------------------------------------------
    def resync_clock(self, resume_t: float, gap_seconds: float = 90.0):
        """
        وقتی بازی از یک توقف بزرگ از سر گرفته می‌شود اما نه HT تشخیص داده
        شده و نه بازی جدید، ساعت بازی می‌تواند «عقب‌تر از آخرین نمونهٔ»
        ما باشد. در نسخهٔ ۴ update() در این حالت تا رسیدن ساعت به نقطهٔ قبلی
        هیچ نمونه‌ای ثبت نمی‌کرد و نمودار عملاً برای بقیهٔ مسابقه می‌مرد.
        این متد نمونه‌برداری را فوراً از سر می‌گیرد:
          * ساعت جلوتر زده شده → فقط نمونه‌برداری فوری (بدون شکاف)
          * ساعت عقب‌تر زده شده → گارد NaN + شکاف نمایشی کوچک + آفست جدید
            (نمودار قبلی حفظ و نمایش ادامهٔ بازی در ادامهٔ محور درج می‌شود)
        """
        with self._lock:
            resume_t = float(resume_t)
            if resume_t > self._last_t:
                self._last_t = resume_t
                self._last_sample_t = resume_t - max(0.05, self.cfg.HISTORY_SAMPLE_INTERVAL) - 1e-6
                return
            last = self.history[-1] if self.history else None
            if not last:
                self._last_t = resume_t
                self._last_sample_t = resume_t
                return
            last_disp = float(last["disp_time"])
            last_game = float(last["game_time"])
            gap = max(30.0, float(gap_seconds))
            _now_wall = time.time()
            self.history.append({"game_time": last_game, "disp_time": last_disp,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            self.history.append({"game_time": resume_t, "disp_time": last_disp + gap,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            self.display_offset = (last_disp + gap) - resume_t
            self.extra_breaks.append((last_disp, last_disp + gap))
            self._last_t = resume_t
            self._last_sample_t = resume_t - max(0.05, self.cfg.HISTORY_SAMPLE_INTERVAL) - 1e-6

    def reset(self, current_match_time: float = 0.0):
        with self._lock:
            self.impacts.clear()
            self._impact_index.clear()
            self.history.clear()
            self.history.append({"game_time": float(current_match_time), "disp_time": float(current_match_time),
                                 "home": 0.0, "away": 0.0, "net": 0.0, "wall": time.time(),
                                 "phase": self.phase_label})
            self._last_t = float(current_match_time)
            self._last_sample_t = float(current_match_time)
            self.display_offset = 0.0
            self.ht_break = None
            self._glue_smooth = None
            # --- نسخه ۵ ---
            self.half_number = 1
            self.hook_goal_markers.clear()
            self.red_card_markers.clear()   # نسخهٔ ۱۰٫۲۷ — مارکرهای کارت قرمز
            self.extra_breaks.clear()


# =====================================================================
# ۲۵.۱ رندر نمودار Momentum (مشترک بین App و Self-Test — نسخه ۲)
# ---------------------------------------------------------------------
# نمودار اصلی فقط شامل این موارد است (بدون خطوط جداگانه Home/Away):
#   ✔ Net Area آینه‌ای: Net>0 → قرمز/بالا (Home) | Net<0 → سفید/پایین (Away)
#   ✔ خط Zero
#   ✔ Goal Marker: خط عمودی + ⚽ دقیقاً روی t_goal (نه peak)
#   ✔ شکاف HT بین دو نیمه (نمونه‌های NaN) + برچسب HT
#   ✔ Gaussian smoothing واقعی فقط روی لایه نمایش — RAW دست‌نخورده
# محور X همیشه Game Clock است (هرگز Wall Clock).
# =====================================================================
