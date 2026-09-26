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

        # technical note technical noteandtechnical noteandtechnical note technical note (technical note technical note and line inandfromtechnical note)
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

        # technical note inandfromtechnical note empty (Open Goal) -> technical note 100
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

        # position technical note to technical note direct
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
        if pass_type == "text‌text": tactical_bonus = 18.0
        elif pass_type in ("pass in text text text", "pass text text"): tactical_bonus = 15.0
        elif pass_type in ("cross pitchtext", "cross textandtext", "pass text"): tactical_bonus = 12.0

        raw_threat = proximity_score + angle_score + def_ahead_penalty + space_bonus + tactical_bonus
        if dist_to_goal > 60.0: raw_threat = min(raw_threat, 18.0)

        return int(max(2.0, min(99.0, raw_threat)))

# technical noteandtechnical note technical note Threat to withtechnical note 2 until 99 in untiltechnical note withtechnical note technical note technical note is.

# =====================================================================
# 14. technical note‌technical note smart pass (PassClassifierEngine — calibratedtechnical note unchanged)
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
        # 1. cross (Cross):
        # technical note deterministic: only in pitch technical note (start_x_att > 0)
        # coordinates technical note: |Z| > 20.1 and |X| > 29.0
        # technical note technical note: to side inandfromtechnical note technical note and technical noteand to technical note/technical noteandtechnical note
        # without check technical note! technical note pitchtechnical note and technical noteandtechnical note technical note technical note height
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
                scores["cross textandtext"] = 96.0
            elif max_h <= PitchConfig.HEIGHT_GROUND_MAX:
                scores["cross pitchtext"] = 96.0
            else:
                scores["cross textandtext"] = 90.0

        # -------------------------------------------------------------
        # 2. technical note‌technical note (Cut-back):
        # technical note deterministic: only in pitch technical note (start_x_att > 0)
        # coordinates technical note: |X| > 35.0
        # height: technical note from 1.8 technical note
        # lengthtechnical note: X ball to technical note technical note technical noteandtechnical note (technical note technical noteand to technical note ratio to inandfromtechnical note technical note)
        # without check technical note!
        # -------------------------------------------------------------
        is_cutback_origin = (start_x_att > 0 and abs(s_x) > PitchConfig.CUTBACK_ORIGIN_X_THRESHOLD)
        is_x_towards_zero = (abs(e_x) < abs(s_x)) and (fwd <= 0.5)
        is_cutback_height = (max_h < PitchConfig.CUTBACK_MAX_HEIGHT)

        if is_cutback_origin and is_x_towards_zero and is_cutback_height:
            scores["text‌text"] = 98.0

        # -------------------------------------------------------------
        # 3. pass technical noteandtechnical note from pressure (Pressure Exit):
        # only in pitch technical noteandtechnical note (start_x_att < 0) and technical note in pitch technical note
        # -------------------------------------------------------------
        is_in_own_half = (start_x_att < 0.0)
        if is_in_own_half and features["passer_under_pressure"] and pressure_relief >= 2.5:
            scores["pass textandtext from pressure"] = 82.0 + pressure_relief * 3.0

        # -------------------------------------------------------------
        # 4. pass technical note technical note (Over-the-Top):
        # height withtechnical note (technical note technical note)technical note technical noteandtechnical note technical note technical note technical note
        # -------------------------------------------------------------
        is_behind_defense = behind_def_line or (end_x_att > features["def_line_x_att"])
        if max_h >= 1.55 and is_behind_defense and fwd >= 6.0:
            scores["pass text text"] = 88.0 + max_h * 4.0

        # -------------------------------------------------------------
        # 5. pass in technical note technical note technical note
        # -------------------------------------------------------------
        if fwd >= 7.0 and is_split_corridor and (behind_def_line or receiver_fwd_run >= 3.0):
            scores["pass in text text text"] = 87.0 + fwd * 1.2

        # -------------------------------------------------------------
        # 6. pass gap‌technical note
        # -------------------------------------------------------------
        if fwd >= 4.5 and is_split_corridor and "pass in text text text" not in scores:
            scores["pass gap‌text"] = 78.0 + fwd * 1.0

        # -------------------------------------------------------------
        # 7. pass technical note (Through Ball):
        # technical note ball technical noteandtechnical note from player withtechnical note and direct to technical note player technical note technical noteandtechnical note
        # -------------------------------------------------------------
        ball_lead_dist = (e_x - features["receiver_start_x"]) * att_dir
        is_lead_pass = (ball_lead_dist >= 3.5 and receiver_target_err >= 3.0)
        if fwd >= 8.0 and is_lead_pass and (running_to_space or receiver_fwd_run >= 2.5):
            scores["pass text"] = 79.0 + fwd * 1.1

        # -------------------------------------------------------------
        # 8. technical noteandtechnical note technical note (Switch of Play)
        # -------------------------------------------------------------
        crosses_center_z = (s_z * e_z < 0) and (abs(s_z) >= 12.0 or abs(e_z) >= 12.0)
        if lat >= 26.0 and dist >= 26.0 and crosses_center_z:
            scores["textandtext text"] = 84.0 + lat * 0.5

        # -------------------------------------------------------------
        # 9. pass technical note lineandtechnical note
        # -------------------------------------------------------------
        if 4.0 <= fwd <= 20.0 and features["receiver_between_lines"] and not behind_def_line:
            scores["pass text lineandtext"] = 74.0 + fwd * 0.8

        # 10. technical note
        if max_h >= 1.50 and dist <= 20.0 and (max_h / max(1.0, dist)) >= 0.09:
            scores["text"] = 70.0 + max_h * 5.0

        # 11. pass to technical note
        if receiver_target_err >= 4.0 and running_to_space:
            scores["pass to text"] = 69.0 + receiver_target_err * 2.0

        # 12. technical noteandtechnical note technical noteandtechnical note
        if dist >= 30.0: scores["pass text"] = 62.0 + dist * 0.5
        if max_h >= PitchConfig.HEIGHT_AERIAL_MIN and dist >= 14.0: scores["pass textandtext"] = 60.0 + max_h * 4.0
        if fwd <= -3.0: scores["pass textand to text"] = 55.0 + abs(fwd) * 2.0
        if lat >= 10.0 and abs(fwd) <= 5.0: scores["pass widthtext"] = 52.0 + lat * 1.5
        if fwd >= 4.5 and lat >= 7.0 and 25.0 <= angle <= 68.0: scores["pass textandtext"] = 50.0 + fwd
        if fwd >= 4.0: scores["pass textand to textand"] = 48.0 + fwd * 1.5
        if dist <= 14.0 and max_h <= PitchConfig.HEIGHT_GROUND_MAX + 0.3: scores["pass textanduntiltext"] = 56.0 + (14.0 - dist) * 1.5

        # technical note technical note
        priority = [
            "text‌text",
            "cross textandtext",
            "cross pitchtext",
            "pass text text",
            "pass in text text text",
            "textandtext text",
            "pass gap‌text",
            "pass text",
            "pass textandtext from pressure",
            "pass text lineandtext",
            "text",
            "pass to text",
            "pass text",
            "pass textandtext",
            "pass textandtext",
            "pass textand to text",
            "pass widthtext",
            "pass textand to textand",
            "pass textanduntiltext"
        ]

        valid_candidates = {k: v for k, v in scores.items() if v > 0.0}
        if not valid_candidates:
            if dist >= 28.0: final_type = "pass text"
            elif fwd <= -3.0: final_type = "pass textand to text"
            elif lat >= 10.0: final_type = "pass widthtext"
            elif fwd >= 4.0: final_type = "pass textand to textand"
            elif lat >= 6.0: final_type = "pass textandtext"
            else: final_type = "pass textanduntiltext"
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
        if max_h >= PitchConfig.HEIGHT_AERIAL_MIN: tags.append("textandtext")
        if fwd >= 6.0: tags.append("textand to textand")
        if is_behind_defense: tags.append("text text")
        if running_to_space: tags.append("to text")

        return final_type, confidence, tags

# =====================================================================
# 15. Pass Engine (technical noteandtechnical noteandtechnical note technical noteandtechnical note technical noteandtechnical note pass — istechnical note‌technical note from version calibrated)
# ---------------------------------------------------------------------
# start/end pass from Frame Buffertechnical note detection Pass Typetechnical note successful/failedtechnical note
# and technical noteto threat_score technical noteandtechnical note PassThreatEngine. output: PassEventData complete.
# Counter only Trigger start istechnical note technical note‌technical note technical noteandtechnical note pass technical note technical note technical note‌technical noteandtechnical note.
# =====================================================================
class PassEngine:
    def __init__(self):
        self.state = "IDLE"  # IDLE | IN_FLIGHT
        self.cur_pass_team = "Home"
        self.cur_pass_start_ball: Optional[Tuple[float, float, float]] = None
        self.cur_pass_start_time = 0.0      # wall (technical notesecond — for technical note technical noteandfrom/polling)
        self.cur_pass_match_time = 0.0      # time withtechnical note
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
        """in stop withtext textandfrom current without textandtext text text text‌textandtext"""
        self.state = "IDLE"

    def on_counter_increment(self, ball: Tuple[float, float, float], wall_now: float,
                             match_time: float, team: str, players: List[Dict]):
        """Counter only Trigger start text detection is"""
        if self.state == "IN_FLIGHT":
            return  # pass current still in technical noteortechnical note is
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
        """to‌textandtext textandfrom pass from Frame Buffer and textandtext PassEventData in end"""
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

        # Threat Score technical note — source score Pass for Momentum (unchanged technical noteandtechnical note)
        threat = PassThreatEngine.calculate_pass_threat(
            receiver_pos=(r_end_x, r_end_z),
            defenders=defenders,
            att_dir=att_dir,
            pass_type=p_type
        )

        new_poss = possession_provider() if possession_provider else None
        is_success = (new_poss == passing_team) if new_poss else is_received

        event_data = PassEventData(
            event_id=0,  # in moment register technical noteandtechnical note EventDetectionEngine technical note technical note‌ortechnical note
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
# 16. technical noteandtechnical noteandtechnical note technical note shot (ShotThreatEngine — calibratedtechnical note unchanged)
# ---------------------------------------------------------------------
# technical note complete: position technical note (Pre-Shot Opportunity Value) in technical note
# technical note technical note (Final Threat = Event / Momentum Impact)
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
        """textto text text position shot before from textto (Pre-shot Opportunity Value)"""
        norm_dist = max(0.0, min(1.0, dist_to_goal / 48.0))
        # impact technical notelinetechnical note distance until inandfromtechnical note
        proximity_score = ((1.0 - norm_dist) ** 2.0) * 52.0

        # impact technical noteandtechnical note technical note inandfromtechnical note
        angle_deg = math.degrees(goal_angle_rad)
        angle_score = min(24.0, (angle_deg / 34.0) * 24.0)

        # technical note technical note technical note technical note technical note technical noteandtechnical note technical note
        def_penalty = -(obstruction_ratio * 26.0)
        if corridor_defs == 0: def_penalty += 8.0

        # pressure nearest technical note
        if nearest_def_dist < 1.0: space_bonus = -12.0
        elif nearest_def_dist < 2.0: space_bonus = -5.0
        elif nearest_def_dist >= 4.0: space_bonus = +8.0
        else: space_bonus = +2.0

        # technical noteandtechnical note inandfromtechnical note‌withtechnical note (technical noteandtechnical note and distance from line)
        gk_bonus = 0.0
        is_open_goal = False
        if opp_gk:
            gk_x, gk_z = opp_gk["x"], opp_gk["z"]
            gk_off_line = abs(gk_x - target_goal_x)
            gk_lat_offset = abs(gk_z)

            if gk_off_line > 4.5 or gk_lat_offset > 3.8:
                gk_bonus += 12.0 # inandfromtechnical note‌withtechnical note from technical noteandtechnical note technical note is

            # check technical note inandfromtechnical note empty (Open Goal)
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
        """textto text text text from text text text shot"""
        # technical note = 100 deterministic
        if "text" in outcome:
            return 100

        # technical noteandtechnical note to post
        if "post" in outcome:
            speed_factor = min(4.0, (speed_kmh / 30.0)) if speed_kmh else 2.0
            if "withtext to pitch" in outcome:
                return int(min(98, 93.0 + speed_factor))
            else:
                return int(min(94, 88.0 + speed_factor))

        speed_mod = 0.0
        if speed_kmh and speed_kmh >= 75.0:
            speed_mod = min(8.0, (speed_kmh - 75.0) * 0.15)

        # technical note or technical noteandtechnical note
        if "text textandtext inandfromtext‌withtext" in outcome:
            if is_on_target:
                # technical note in distance technical note to line technical note technical noteandtechnical note‌technical note‌technical note technical note
                close_boost = max(10.0, (22.0 - block_dist) * 1.0)
                return int(max(65, min(94, pre_shot_threat * 0.75 + close_boost + speed_mod)))
            return int(max(30, min(65, pre_shot_threat * 0.6)))

        if "textandtext textandtext text" in outcome:
            if is_on_target:
                if block_dist <= 3.0: return 95 # technical note from technical noteandtechnical note line
                return int(max(55, min(88, pre_shot_threat * 0.70 + speed_mod)))
            return int(max(25, min(60, pre_shot_threat * 0.5)))

        # technical note from technical noteandtechnical note
        if "text from textandtext" in outcome:
            if woodwork_dist <= 0.8: # technical note with post
                return int(max(40, min(75, pre_shot_threat * 0.85)))
            elif woodwork_dist <= 2.2:
                return int(max(20, min(50, pre_shot_threat * 0.50)))
            else:
                return int(max(5, min(30, pre_shot_threat * 0.25)))

        return pre_shot_threat

# =====================================================================
# 17. technical note‌technical note smart shot (ShotClassifierEngine — calibratedtechnical note unchanged)
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

        # 1. penalty: technical note technical note‌technical note technical note pitch
        if is_pen_spot and in_box and stationary_time >= ShotConfig.STATIONARY_DURATION_MIN and other_players_clear:
            scores["penalty"] = 96.0

        # 2. shot technical noteandtechnical note technical notewithtechnical note
        if is_rebound:
            scores["shot textandtext textwithtext"] = 92.0

        # 3. technical noteto free direct
        if stationary_time >= ShotConfig.STATIONARY_DURATION_MIN and not is_pen_spot and dist >= 16.0:
            scores["textto free"] = 85.0 + min(10.0, stationary_time * 2.0)

        # 4. technical noteto technical note: technical note technical note technical note technical noteandtechnical note physical
        if init_h >= ShotConfig.HEADER_HEIGHT_MIN and prior_aerial:
            header_evidence = (init_h - ShotConfig.HEADER_HEIGHT_MIN) / 0.6
            scores["textto text"] = 75.0 + min(18.0, header_evidence * 18.0)
            if ball_descending: scores["textto text"] += 6.0

        # 5. andtechnical note
        if (ShotConfig.VOLLEY_HEIGHT_MIN <= init_h < ShotConfig.VOLLEY_HEIGHT_MAX) and prior_aerial and control_time <= 0.40:
            scores["andtext"] = 80.0 + (init_h * 5.0)

        # 6. shot‌technical note technical note‌technical note
        if curve_ratio >= ShotConfig.CURVE_RATIO_THRESHOLD:
            target_name = "shot text‌text inandtext textandtext" if in_box else "shot text‌text outside textandtext"
            scores[target_name] = 84.0 + min(14.0, curve_ratio * 120.0)

        # 7. shot technical note
        if 1.30 <= max_h <= 3.80 and (max_h / max(4.0, dist)) >= 0.08 and dist <= 22.0 and not prior_aerial:
            scores["shot text"] = 83.0

        # 8. technical note‌to‌technical note
        if is_1v1:
            scores["shot text‌to‌text"] = 86.0

        # 9. shot from technical noteandtechnical note technical note
        if angle_deg <= PitchConfig.TIGHT_ANGLE_DEG and abs(s_z) >= PitchConfig.WIDE_ZONE_Z:
            scores["shot from textandtext text"] = 80.0

        # 10. shot technical note
        if dist <= PitchConfig.CLOSE_SHOT_DIST_MAX:
            scores["shot text"] = 78.0 + (PitchConfig.CLOSE_SHOT_DIST_MAX - dist) * 1.5

        # 11. shot from technical note technical noteandtechnical note
        if dist >= PitchConfig.LONG_SHOT_DIST_MIN and not in_box:
            scores["shot from text textandtext"] = 76.0 + min(15.0, (dist - 21.0) * 0.8)

        # 12. technical noteandtechnical note
        if abs(s_z) <= PitchConfig.CENTER_ZONE_Z and angle_deg >= 20.0: scores["shot from text"] = 70.0
        if abs(s_z) >= PitchConfig.WIDE_ZONE_Z: scores["shot from text"] = 69.0
        if in_box: scores["shot inside textandtext"] = 68.0

        # technical note totechnical note technical note
        priority_order = [
            "penalty", "shot textandtext textwithtext", "textto free", "shot text‌text inandtext textandtext",
            "shot text‌text outside textandtext", "shot text", "andtext", "textto text",
            "shot text‌to‌text", "shot from textandtext text", "shot text", "shot from text textandtext",
            "shot from text", "shot from text", "shot inside textandtext"
        ]

        valid_cands = {k: v for k, v in scores.items() if v > 0.0}
        if not valid_cands:
            final_type = "shot inside textandtext" if in_box else "shot from text textandtext"
            confidence = 0.55
        else:
            sorted_cands = sorted(valid_cands.items(), key=lambda x: x[1], reverse=True)
            top_type, top_score = sorted_cands[0]
            # Tie-break smart with firstandtechnical note untiltechnical note
            for p_type in priority_order:
                if p_type in valid_cands and valid_cands[p_type] >= (top_score - 4.5):
                    top_type = p_type
                    top_score = valid_cands[p_type]
                    break
            final_type = top_type
            second_score = sorted_cands[1][1] if len(sorted_cands) > 1 else 0.0
            margin = top_score - second_score
            confidence = min(0.95, max(0.55, 0.65 + margin * 0.02))

            # technical noteandtechnical note confidence to technical note technical note technical note to technical notetotaltechnical note player
            if final_type in ("textto text", "andtext"):
                confidence = min(0.85, confidence)

        tags = ["inside textandtext" if in_box else "outside textandtext"]
        if is_1v1: tags.append("text‌to‌text")
        if curve_ratio >= ShotConfig.CURVE_RATIO_THRESHOLD: tags.append("text‌text")
        if dist <= PitchConfig.CLOSE_SHOT_DIST_MAX: tags.append("text text")
        if dist >= PitchConfig.LONG_SHOT_DIST_MIN: tags.append("text textandtext")
        if init_h >= ShotConfig.HEADER_HEIGHT_MIN: tags.append("textandtext")

        return final_type, confidence, tags, valid_cands

# =====================================================================
# 18. Shot Engine (technical noteandtechnical noteandtechnical note technical noteandtechnical note technical noteandtechnical note shot — istechnical note‌technical note from version calibrated)
# ---------------------------------------------------------------------
# detection moment technical noteto (jump technical note technical note)technical note technical note‌technical note state-based and technical noteandtechnical note
# technical noteandfrom until line inandfromtechnical note technical noteortechnical note technical note technical note posttechnical note technical note/technical noteandtechnical note and output
# ShotEventData complete with pre_shot_threat and final_threat.
# technical note‌technical note to‌technical noteandtechnical note State Machine technical note technical note‌technical noteandtechnical note until Worker original technical note technical noteandtechnical note and
# technical note‌time Possession / Pass / Zone / Pressure / Time / Momentum from technical note technical noteandtechnical note.
# =====================================================================
class ShotEngine:
    """
    versiontext 10text14 — textandtextandtext shot with «text text shot»:
      * 1 increment Shot Counter = 1 text shot — always text text‌textandtext text text
        text‌text Drop text‌textandtext (text if textandtextandtext currently TRACKING/PENDING withtext)text
      * textfromtext text to ordertext independent from text original (text‌text)text
      * textandtext momenttext textto/shot‌text text text Frame Buffer and time withtext
        (text untiltext‌textandtext textanduntiltext textandtext)text
      * Dedup only with text text (counter + text) — textand shot realtext
        text‌text never Duplicate text text‌textandtext
      * text complete chain (stats) — text text in textwithtext and match end.
    """
    def __init__(self):
        self.last_shot_counter: Optional[int] = None
        self.previous_shot_ctx: Optional[PreviousShotContext] = None
        self.state = "IDLE"  # IDLE | TRACKING
        self._trk: Optional[Dict[str, Any]] = None
        # --- versiontechnical note 10technical note14: technical note technical note shot (fallback Pending technical note) ---
        self._queue: deque = deque()
        self._active: Optional[Dict[str, Any]] = None  # technical note technical note technical note currently technical note
        self._gen: int = 0                             # technical note counter (reset counter ⇒ technical note new)
        self._finalized_ids: set = set()
        self._finalized_order: deque = deque(maxlen=64)
        self._auto_seq: int = 0                        # technical note automatic for path technical notefromtechnical note
        # --- technical note chaintechnical note shot (specification 10technical note14) ---
        self.stats: Dict[str, int] = {
            "counter_increments": 0, "triggers": 0, "contact_found": 0,
            "shooter_found": 0, "tracking_started": 0, "tracking_finalized": 0,
            "events_registered": 0, "threats_created": 0, "ui_added": 0,
            "pending": 0, "pending_dropped": 0, "duplicates": 0,
        }
        # --- technical note technical notewithtechnical note chain shot ---
        self.debug_sink = None   # callable(dict) — technical noteandtechnical note MomentumApp technical note technical note‌technical noteandtechnical note

    def _dbg(self, stage: str, **kw):
        """register text chain shot for Tab textwithtext (in textandtext text sink)"""
        if self.debug_sink:
            try:
                self.debug_sink(stage, **kw)
            except Exception:
                pass

    def _stat(self, key: str):
        """increment text countertext text chaintext shot"""
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
        self._gen += 1                     # technical note‌technical note technical note new never legacy‌technical note technical note technical note technical note‌technical note
        self._finalized_ids.clear()
        self._finalized_order.clear()
        for _k in self.stats:
            self.stats[_k] = 0

    def set_counter_baseline(self, cnt: Optional[int]):
        self.last_shot_counter = cnt

    # -------------------------------------------------------------
    # technical note technical note shot (10technical note14) — Push alwaystechnical note Drop only with technical note log‌technical note
    # -------------------------------------------------------------
    def push_trigger(self, counter_value: Optional[int], team: Optional[str],
                     alternates: List[Optional[str]], match_time: Optional[float],
                     wall_now: float, frame_seq: int = 0,
                     team1_attack_dir: int = 1) -> Optional[str]:
        """
        1 increment Shot Counter = 1 text shot in text.
          * counter_value → text textuntiltext text: «text:value counter»text
          * team → teamtext text‌text from Context possession (with fallback user)text
          * alternates → text fallback team (Context beforetext in jumptext simultaneous
            possessiontext poss text and ...) — in textandtextandtext to order text text‌textandtext
          * Dedup only with text text — text timetext text text.
        output: text text (or None in textandtext Duplicate textandtext).
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
                      note="same textandtext counter beforetext text/text text is")
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
                  note="1 increment counter = 1 text shot (in text textfromtext)")
        return candidate_id

    def on_counter_reset(self, reason: str = "counter_reset") -> int:
        """
        withtext Shot Counter (second half/restart): text text‌text beforetext
        text‌text (text to text before) — only with text log‌text text text‌textandtext and
        text += 1 until text‌text text textandtext text.
        """
        dropped = 0
        while self._queue:
            q = self._queue.popleft()
            self._stat("pending_dropped")
            self._dbg("PENDING_DROPPED", engine_state=self.state, team=q.get("team"),
                      candidate_id=q.get("candidate_id"), reason=reason,
                      note="withtext counter — text text beforetext text text")
            dropped += 1
        if self._active is not None and self.state != "TRACKING":
            self._stat("pending_dropped")
            self._dbg("PENDING_DROPPED", engine_state=self.state,
                      team=self._active.get("team"),
                      candidate_id=self._active.get("candidate_id"), reason=reason,
                      note="withtext counter — text currently text text text")
            self._active = None
            dropped += 1
        self._gen += 1
        return dropped

    def _mark_finalized(self, candidate_id: Optional[str]):
        """register text text to‌textandtext text‌text (text text only text withtext)"""
        if candidate_id is None:
            return
        self._finalized_ids.add(candidate_id)
        self._finalized_order.append(candidate_id)
        while len(self._finalized_order) > ShotConfig.SHOT_FINALIZED_KEEP:
            _old = self._finalized_order.popleft()
            self._finalized_ids.discard(_old)

    # -------------------------------------------------------------
    # start technical note‌technical note (technical note shared process / technical note technical notefromtechnical note on_counter_increment)
    # -------------------------------------------------------------
    @staticmethod
    def _seed_from_buffer(buffer_list: List[SnapshotFrame], shot_frame: SnapshotFrame,
                          cap: int = 20) -> Tuple[List, List, List]:
        """
        versiontext 10text14 — frame‌text «text from» momenttext textto in buffer → textwithtext path textandfrom.
        for textandtextandtext‌text text (Pending)text text textandfrom ball from text text‌textandtext
        text‌text with same textandtext update_tracking text text‌textandtext.
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
    # technical noteandtechnical note moment technical note technical noteto and shot‌technical note technical note technical note jump technical note technical note
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
                    # score technical note technical note technical noteandtechnical note ball and technical noteandtechnical note player
                    score = (1.0 / (d_cand + 0.35)) * 40.0 + fwd_speed * 1.5 + (speed * 0.8)
                    if score > max_contact_score:
                        max_contact_score = score
                        best_frame = f_cur
                        best_shooter = cand

        return best_frame, best_shooter

    def on_counter_increment(self, engine, buffer_list: List[SnapshotFrame],
                             wall_now: float, team: str, att_dir: int) -> bool:
        """
        text textfromtext (10text14) — path legacy «text immediate»: text text‌textfromtext and
        same text textfromtext text‌text. path original Worker: push_trigger + process.
        output: True if text‌text textfrom text (text legacy text text).
        """
        self.push_trigger(None, team, [team], None, wall_now, 0, att_dir)
        return self.process(engine, buffer_list, wall_now, None, 0)

    # -------------------------------------------------------------
    # technical notefromtechnical note technical note technical note (10technical note14) — technical note technical note technical note‌technical note technical noteandtechnical note frame‌technical noteandtechnical note
    # -------------------------------------------------------------
    def process(self, engine, buffer_list: List[SnapshotFrame], wall_now: float,
                match_time: Optional[float] = None, frame_seq: int = 0) -> bool:
        """
        if text‌text activetext in textortext is nottext text text text for «textdecreasetext momenttext textto +
        shot‌text» text text‌text:
          * text team to order (team original → Context beforetext → poss text →
            in textandtext text text: text textand team) text text‌textandtext
          * textandtext first in windowtext calibrated (26 frame) and text‌text aftertext text‌text
            (120 frame) inside Frame Buffertext
          * Drop only text from textandtext «windowtext textandtext real» (frame/time withtext) and
            always with text log‌text — text text text‌text text text‌textandtext.
        output: True if text‌text textfrom text.
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
                      note="textandtext text‌textandtext momenttext textto in Frame Buffer")
        cand = self._active

        # --- windowtechnical note technical noteandtechnical note real (frame / time withtechnical note — technical note untiltechnical note‌technical noteandtechnical note technical noteanduntiltechnical note technical noteandtechnical note) ---
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
                      note="textandtext from windowtext textandtext — momenttext textto text recovery textandtext")
            self._active = None
            return False

        # --- technical note technical noteandtechnical noteandtechnical note with technical note team to order ---
        cand["attempts"] = cand.get("attempts", 0) + 1
        teams_to_try: List[str] = []
        for t in ([cand.get("team")] + list(cand.get("alternates") or [])):
            if t and t not in teams_to_try:
                teams_to_try.append(t)
        if not teams_to_try:
            # Context possession technical note technical note technical note → technical noteandtechnical note technical noteandtechnical note technical note team technical note
            # technical note technical note‌technical note (only players teamtechnical note shot‌technical note technical note ball technical note)
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
            # technical note deterministic shot: only and only in technical note technical note (calibrated tool independent)
            shooter_x_att = shooter["x"] * att_dir
            ball_x_att = shot_frame.ball[0] * att_dir
            if shooter_x_att <= 0.0 or ball_x_att <= 0.0:
                self._dbg("TRIGGER_FILTER_REJECT", engine_state=self.state, team=team,
                          candidate_id=cand.get("candidate_id"),
                          note="textto in text textandtext for text text team — team aftertext")
                continue
            self._active = None
            self._dbg("CONTACT_FOUND", engine_state=self.state, team=team,
                      candidate_id=cand.get("candidate_id"),
                      shot_match_time=shot_frame.match_time,
                      attempts=cand["attempts"],
                      note="frame momenttext textto in buffer textdecrease text")
            self._dbg("SHOOTER_FOUND", engine_state=self.state, team=team,
                      candidate_id=cand.get("candidate_id"),
                      shooter_seat=shooter.get("seat"),
                      attempts=cand["attempts"],
                      note="shot‌text confirmation text")
            if cand["attempts"] > 1:
                self._dbg("PENDING_RESOLVED", engine_state=self.state, team=team,
                          candidate_id=cand.get("candidate_id"),
                          attempts=cand["attempts"],
                          note="momenttext textto in text‌text aftertext recovery text")
            self._start_tracking(engine, team, att_dir, shot_frame, shooter,
                                 buffer_list, wall_now, cand)
            return True

        if cand["attempts"] <= 1:
            self._stat("pending")
            self._dbg("PENDING", engine_state=self.state, team=cand.get("team"),
                      candidate_id=cand.get("candidate_id"),
                      note="momenttext textto textandtext textdecrease text — textandtext in frame‌text aftertext")
        elif cand["attempts"] % 20 == 0:
            self._dbg("CONTACT_NOT_FOUND", engine_state=self.state,
                      team=cand.get("team"),
                      candidate_id=cand.get("candidate_id"),
                      attempts=cand["attempts"],
                      note="still without text — textand resume text")
        return False

    def try_pending(self, engine, buffer_list: List[SnapshotFrame], wall_now: float) -> bool:
        """text textfromtext (10text14) — text process without time withtext."""
        return self.process(engine, buffer_list, wall_now, None, 0)

    def update_tracking(self, engine) -> Optional[ShotEventData]:
        """
        text text from text‌text textandfrom (state-based/non-blocking) — in text Poll text text
        from text original version calibrated text text‌textandtext text and threshold‌text unchanged‌text.
        """
        if self.state != "TRACKING" or not self._trk:
            return None
        trk = self._trk

        # Timeout version calibrated (wall clock — only for timeout/performance)
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

        # --- versiontechnical note 10technical note14: log technical note‌technical note technical note technical note‌technical note (technical note 25 technical note) ---
        if len(trajectory) % 25 == 0:
            self._dbg("TRACKING_UPDATED", engine_state=self.state,
                      team=trk["team"],
                      candidate_id=trk.get("candidate_id"),
                      points=len(trajectory),
                      note="text‌text textandfrom in textortext is")

        # technical note: check technical noteandtechnical note and technical note with post‌technical note
        if not trk["hit_woodwork"] and abs(b_cur[0] - trk["target_goal_x"]) <= (PitchConfig.POST_COLLISION_RADIUS + 0.3):
            p_prev = trajectory[-2]
            vx_att = (b_cur[0] - p_prev[0]) * att_dir
            # check technical note to technical note technical noteandtechnical note or technical note
            d_post_l = math.hypot(b_cur[1] - (-PitchConfig.GOAL_HALF_WIDTH), max(0.0, b_cur[2] - PitchConfig.GOAL_HEIGHT/2))
            d_post_r = math.hypot(b_cur[1] - PitchConfig.GOAL_HALF_WIDTH, max(0.0, b_cur[2] - PitchConfig.GOAL_HEIGHT/2))
            d_bar = abs(b_cur[2] - PitchConfig.GOAL_HEIGHT)

            if min(d_post_l, d_post_r, d_bar) <= PitchConfig.POST_COLLISION_RADIUS:
                trk["hit_woodwork"] = True
                trk["woodwork_name"] = "text text" if d_bar < min(d_post_l, d_post_r) else "text textandtext"
                if vx_att < -0.2: trk["woodwork_rebound"] = True

        # technical note: check technical note or technical noteandtechnical note real with technical note height technical note
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

            # ball technical notemust from withtechnical note technical note technical note player technical note technical noteandtechnical note
            if b_cur[2] <= reach_limit:
                vx_now = (b_cur[0] - trajectory[-3][0]) * att_dir
                # decrease technical note technical note or technical note ball to side technical note
                if vx_now < 0.25:
                    trk["intercepted"] = True
                    trk["intercept_player"] = closest_opp
                    trk["block_dist"] = abs(trk["target_goal_x"] - b_cur[0])
                    return self._finalize()

        # technical note: technical note immediate to technical note technical noteandtechnical note from technical note line 52.5 technical note
        cur_x_att = b_cur[0] * att_dir
        prev_x_att = trajectory[-2][0] * att_dir
        if cur_x_att >= PitchConfig.HALF_LENGTH:
            # inandtechnical note‌ortechnical note technical note technical note technical noteandtechnical note with technical note line inandfromtechnical note
            span = cur_x_att - prev_x_att
            t_ratio = (PitchConfig.HALF_LENGTH - prev_x_att) / span if abs(span) > 1e-4 else 1.0
            t_ratio = max(0.0, min(1.0, t_ratio))

            cross_z = trajectory[-2][1] + t_ratio * (b_cur[1] - trajectory[-2][1])
            cross_y = max(0.0, trajectory[-2][2] + t_ratio * (b_cur[2] - trajectory[-2][2]))
            trk["goal_line_point"] = (trk["target_goal_x"], cross_z, cross_y)

            # --- version 4: register technical note from «path ball + technical noteandtechnical note inandfromtechnical note» completetechnical note technical note technical note technical note ---
            # technical noteandtechnical note from technical note inandfromtechnical note only for technical noteortechnical note is_on_target / distance post /
            # technical note firsttechnical note Outcome istechnical note technical note‌technical noteandtechnical note. technical note technical note «technical note» technical note technical noteandtechnical note
            # GoalHooker (countertechnical note memory: [rcx+0x158] / [rcx+0x15C]) technical note technical note‌technical noteandtechnical note
            # and technical note from confirmation hooktechnical note technical note shottechnical note technical note‌technical note to‌technical noteandtechnical note withtechnical note to «technical note»
            # technical note technical note‌ortechnical note (register_goal_event + technical noteis GOAL_LINKED_SHOT_RATIO).
            return self._finalize()

        return None

    # -------------------------------------------------------------
    # technical noteortechnical note technical note shot (technical noteandtechnical note complete technical noteandtechnical note technical noteortechnical note version calibrated)
    # -------------------------------------------------------------
    def _finalize(self) -> Optional[ShotEventData]:
        trk = self._trk
        self.state = "IDLE"
        self._trk = None
        if not trk:
            return None
        # --- versiontechnical note 10technical note14: technical note technical note technical note technical note‌technical noteandtechnical note (technical note technical note only technical note withtechnical note) ---
        _cand_id = trk.get("candidate_id")
        self._mark_finalized(_cand_id)
        self._stat("tracking_finalized")
        self._dbg("TRACKING_FINALIZED", engine_state=self.state,
                  team=trk.get("team"), candidate_id=_cand_id,
                  note="textortext text shot textfrom text")

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

        # technical noteortechnical note technical note real
        if speeds:
            sorted_spd = sorted(speeds)
            max_speed = sorted_spd[int(len(sorted_spd) * 0.85)]
            speed_valid = True
        else:
            max_speed = None
            speed_valid = False

        # technical noteortechnical note technical note technical note
        eval_p = goal_line_point if goal_line_point else trajectory[-1]
        signed_woodwork_dist, is_on_target = GeometryEngine.calculate_signed_woodwork_distance(eval_p[1], eval_p[2])

        # technical note deterministic technical note shot (Outcome)
        if is_goal:
            is_on_target = True
            outcome = f"text with textandtext to {woodwork_name} ⚽💥" if hit_woodwork else "text deterministic ⚽"
        elif hit_woodwork:
            is_on_target = True
            outcome = f"textandtext to {woodwork_name} and withtext to pitch 💥" if woodwork_rebound else f"textandtext to {woodwork_name} and textandtext from pitch 💥"
        elif intercepted and intercept_player:
            is_gk = (intercept_player["seat"] == opp_gk_seat)
            actor = "inandfromtext‌withtext" if is_gk else "text"
            outcome = f"text textandtext {actor} (in textandtext) 🧤" if is_on_target else f"text textandtext {actor} (text textandtext)"
        else:
            if is_on_target:
                outcome = "in textandtext (text / stop)"
            else:
                if signed_woodwork_dist <= 0.8: outcome = "text from textandtext (text textortext text / text)"
                elif signed_woodwork_dist <= 2.2: outcome = "text from textandtext (text textandtext)"
                else: outcome = "text from textandtext (text textortext)"

        # istechnical note technical note untiltechnical note and technical note
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

        # check technical note‌to‌technical note technical note technical note technical noteandtechnical note withtechnical note and technical note
        is_1v1 = (corridor_defs == 0 and obstruction_ratio <= 0.08 and dist_to_goal <= 22.0 and near_def_dist >= 2.4)
        is_inside_box = ((shooter["x"] * att_dir) >= PitchConfig.PENALTY_BOX_X and abs(shooter["z"]) <= PitchConfig.PENALTY_BOX_HALF_Z)

        # check technical note technical noteandtechnical note ball for penalty and technical noteto free
        stationary_duration = 0.0
        if len(buffer_list) >= 15:
            sub_buf = [f.ball for f in list(buffer_list)[-45:]]
            ref_b = sub_buf[0]
            if all(GeometryEngine.dist_2d((b[0], b[1]), (ref_b[0], ref_b[1])) <= ShotConfig.STATIONARY_RADIUS for b in sub_buf):
                stationary_duration = len(sub_buf) * 0.015

        # check penalty technical note
        pen_spot_x = PitchConfig.PENALTY_SPOT_X_ATT * att_dir
        is_pen_spot = (abs(shooter["x"] - pen_spot_x) <= 1.8 and abs(shooter["z"]) <= 1.4 and dist_to_goal <= 12.5)
        other_players_clear = all(
            GeometryEngine.dist_2d((p["x"], p["z"]), (pen_spot_x, 0.0)) >= 8.5
            for p in shot_frame.players if p["seat"] not in (shooter["seat"], opp_gk_seat)
        )

        # check technical notewithtechnical note real with technical noteandtechnical note technical note
        is_rebound = False
        if self.previous_shot_ctx:
            dt_prev = now_t - self.previous_shot_ctx.timestamp
            if dt_prev <= 4.2 and self.previous_shot_ctx.team == team:
                dist_from_prev_end = GeometryEngine.dist_2d((shooter["x"], shooter["z"]), (self.previous_shot_ctx.end_position[0], self.previous_shot_ctx.end_position[1]))
                if dist_from_prev_end <= 15.0 and ("text" in self.previous_shot_ctx.outcome or "textandtext" in self.previous_shot_ctx.outcome or "post" in self.previous_shot_ctx.outcome):
                    is_rebound = True

        # register shot technical note to technical noteandtechnical note technical note beforetechnical note
        self.previous_shot_ctx = PreviousShotContext(
            timestamp=now_t,
            end_position=eval_p,
            team=team,
            outcome=outcome,
            target_goal_x=target_goal_x
        )

        # technical noteto technical note ball
        curve_ratio, curve_dir = GeometryEngine.calculate_curve(trajectory)

        # andtechnical note technical noteandfrom beforetechnical note for detection technical note and andtechnical note
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

        # technical noteto technical note‌technical note technical note (Pre = Opportunity Value | Final = Momentum Impact)
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
            event_id=0,  # in moment register technical noteandtechnical note EventDetectionEngine technical note technical note‌ortechnical note
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
            # version 3: register technical note technical note technical note technical noteandtechnical note technical note data
            is_goal=is_goal,
            # versiontechnical note 10technical note14: technical note technical note counter (technical note Dedup register technical note)
            candidate_id=_cand_id,
            tags=tags,
            candidate_scores=cand_scores
        )
        # --- version 2: register technical note technical note chain shot (Event technical note technical note) ---
        self._dbg(
            "SHOT_EVENT_CREATED",
            engine_state=self.state,
            team=team,
            shot_event_id=0,          # technical note from register_shot_event technical noteandtechnical note Worker technical note technical note‌technical noteandtechnical note
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
# 19. technical note structure technical note (DefensiveStructureEngine)
# =====================================================================
class DefensiveStructureEngine:
    @staticmethod
    def analyze_structure(players: List[Dict], att_team: str, att_dir: int) -> Dict[str, Any]:
        defenders = [p for p in players if p["team"] != att_team]
        opp_gk_seat = 12 if att_team == "Home" else 1
        outfield_defs = [d for d in defenders if d["seat"] != opp_gk_seat]
        if not outfield_defs:
            return {"def_line_x_att": 35.0, "is_high_line": False, "is_deep_block": False, "def_area_sqm": 400.0}

        # technical note‌technical notefromtechnical note lengthtechnical note technical note in technical note technical note technical note
        sorted_x_att = sorted([d["x"] * att_dir for d in outfield_defs])
        # line technical note technical noteandtechnical note with position secondtechnical note technical note technical note technical note technical note‌technical noteandtechnical note
        def_line_x_att = sorted_x_att[-2] if len(sorted_x_att) >= 2 else sorted_x_att[-1]

        z_coords = [d["z"] for d in outfield_defs]
        width = max(z_coords) - min(z_coords) if z_coords else 30.0
        length = (sorted_x_att[-1] - sorted_x_att[0]) if len(sorted_x_att) >= 2 else 15.0

        # in coordinates technical note line technical note withtechnical note technical note technical note to side technical noteortechnical note pitch technical noteand technical note‌technical note
        is_high_line = (def_line_x_att <= 22.0)
        is_deep_block = (def_line_x_att >= 36.0)

        return {
            "def_line_x_att": def_line_x_att,
            "is_high_line": is_high_line,
            "is_deep_block": is_deep_block,
            "def_area_sqm": length * width
        }

# =====================================================================
# 20. detection position‌technical note technical note (OpportunityEngine — Chance and Big Chance)
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
                tags=["position text" if is_big_chance else "position linetext", f"{dist_to_goal:.1f}m"]
            ))

# =====================================================================
# 21. technical note independent penalty (PenaltyDetector — independent from counter shot)
# =====================================================================
class PenaltyDetector:
    """detection position and text textto penalty text text textandtext text and text"""
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
            # check technical noteandtechnical note technical note from technical note with technical note withtechnical note
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
                        tags=["textto penalty"]
                    ))

        elif self.state == "RESOLVING":
            # check technical note technical note penalty
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
                    tags=["text penalty ⚽" if is_goal else "penalty from text text ❌"]
                ))
                self.state = "IDLE"
            elif (current_frame.timestamp - self.stationary_start) > 4.0:
                self.state = "IDLE"

# =====================================================================
# 22. technical notefrom technical noteandtechnical note pressure (PressureEpisodeDetector)
# ---------------------------------------------------------------------
# Pressure Episode: pressure technical noteintechnical note technical note technical note balltechnical note impact technical note and technical noteintechnical note with
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
        """text textandtext in change possession"""
        if not self.active:
            return None
        return self._collect(end_mt if end_mt is not None else self.last_mt)

# =====================================================================
# 23. technical noteandtechnical noteandtechnical note technical note (TransitionEngine — Counterattack / Attacking Transition)
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

        # counterattack: start from pitch technical noteandtechnical note technical note fast to third technical noteandtechnical note with pass‌technical note technical noteandtechnical note
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
                    tags=["counterattack", f"{elapsed:.1f}s"]
                ))
                return

        # transition technical noteandtechnical note technical note (weight technical note from counterattack)
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
                    tags=["transition textandtext", f"{elapsed:.1f}s"]
                ))

# =====================================================================
# 24. technical noteandtechnical noteandtechnical note technical note Event Detection Engine (layer technical note register and technical note technical note)
# ---------------------------------------------------------------------
# Pass/Shot only from PassEngine and ShotEngine register technical note‌technical noteandtechnical note technical note technical noteandtechnical noteandtechnical note never
# Pass or Shot technical note from technical note technical note‌technical note technical note‌technical note. technical notedatatechnical note from Event Bus technical note
# technical note‌technical noteandtechnical note until MomentumScoring technical note‌technical note technical note to Impact technical note technical note.
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
        """register in Event Stream + text textandtext Unified Event Bus"""
        self.events.append(event)
        # --- version 2: technical note Event → Sequence (technical note) ---
        # technical note Chance/Big Chance to chain possession current technical note technical note‌technical noteandtechnical note
        # (pass/shot in register_pass_event / register_shot_event technical note technical note‌technical noteandtechnical note)
        if (event.event_type in ("Chance", "Big Chance")
                and self.current_seq and self.current_seq.is_active):
            self.current_seq.chances_created += 1
        self.event_bus.publish(event)

    def _zone_allowed(self, team: str, etype: str, match_time: float, cooldown: Optional[float] = None) -> bool:
        """Cooldown / Deduplication for textdatatext zone-based"""
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
        # technical note technical noteandtechnical note pressure team beforetechnical note (technical note from technical noteandtechnical note chain)
        prev_team = self.current_seq.team if (self.current_seq and self.current_seq.is_active) else None
        ep = self.pressure_detector.force_finish(match_time)
        if ep and prev_team:
            self._emit_pressure_event(ep, prev_team, timestamp, match_time, ball_pos)

        # end chain beforetechnical note
        if self.current_seq and self.current_seq.is_active:
            self.current_seq.end_time = match_time
            self.current_seq.duration = max(0.1, match_time - self.current_seq.start_time)
            self.current_seq.territorial_gain = self.current_seq.max_ball_x - self.current_seq.start_ball_x
            self.current_seq.ending_reason = "from text text possession"
            self.current_seq.is_active = False

        # technical notefrom chain new
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

        # register technical noteandtechnical note transition possession (weight technical noteortechnical note technical note/technical note — technical note for chain technical noteandtechnical notedatatechnical note)
        self._emit(GameEvent(
            event_id=self.generate_id(),
            event_type="Possession Change",
            team=new_team,
            timestamp=timestamp,
            match_time=match_time,
            reliability=EventReliability.CERTAIN,
            confidence=1.0,
            position=ball_pos,
            tags=["change possession", f"team new: {new_team}"]
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
                tags=[f"pressure {stats['duration']:.0f} second‌text",
                      f"textortext pressure {stats['avg_pressure']:.1f}",
                      f"textandtext pressure {stats['max_pressure']:.0f}"]
            ))

    # -------------------------------------------------------------
    def _detect_corner(self, current_frame: SnapshotFrame, att_team: Optional[str], att_dir: int):
        if not att_team:
            return
        bx, bz, _ = current_frame.ball
        # ball in technical noteandtechnical note technical noteandtechnical note technical note side technical note team technical note
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
                    tags=["text (istextwithtext)"]
                ))

    def _detect_goal_kick(self, frame_buffer: deque, current_frame: SnapshotFrame, team1_att_dir: int):
        bx, bz, _ = current_frame.ball
        if abs(bx) < 47.5 or abs(bz) > 9.2:
            return
        # team technical note inandfromtechnical note technical note ball
        if bx < 0:
            defending = "Home" if team1_att_dir == 1 else "Away"
        else:
            defending = "Away" if team1_att_dir == 1 else "Home"
        if current_frame.possession != defending:
            return
        # technical noteandtechnical note technical note ball (technical noteto inandfromtechnical note from technical note technical note)
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
                tags=["textto inandfromtext (istextwithtext)"]
            ))

    # -------------------------------------------------------------
    def process_frame(self, frame_buffer: deque, current_frame: SnapshotFrame, team1_att_dir: int):
        att_team = current_frame.possession
        if not att_team: return
        att_dir = team1_att_dir if att_team == "Home" else -team1_att_dir

        bx, bz, by = current_frame.ball
        bx_att = bx * att_dir

        # to‌technical noteandtechnical note livetechnical note chain possession (version 2 — UI same Row technical note Live technical note technical note‌technical note)
        if self.current_seq and self.current_seq.is_active:
            if bx_att > self.current_seq.max_ball_x:
                self.current_seq.max_ball_x = bx_att
            # technical note and technical noteandtechnical note in technical note frame live to‌technical noteandtechnical note technical note‌technical noteandtechnical note (technical note only technical note technical note)
            self.current_seq.duration = max(0.0, current_frame.match_time - self.current_seq.start_time)
            self.current_seq.territorial_gain = self.current_seq.max_ball_x - self.current_seq.start_ball_x

        # 1. andtechnical noteandtechnical note to technical note (Zone Entries) with cooldown technical note technical notewithtechnical note
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
                    tags=["andtextandtext to third textandtext"]
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
                    tags=["andtextandtext to textandtext text"]
                ))
        self.prev_ball_in_box[att_team] = in_box

        # 2. position‌technical note linetechnical note (Chances)
        self.opportunity_engine.evaluate(current_frame, att_team, att_dir, self._emit, self.generate_id)

        # 3. penalty (independent from counter shot)
        self.penalty_detector.update(frame_buffer, current_frame, team1_att_dir, self._emit, self.generate_id)

        # 4. technical noteandtechnical note pressure
        ep = self.pressure_detector.update(current_frame, att_team, att_dir)
        if ep:
            self._emit_pressure_event(ep, att_team, current_frame.timestamp, current_frame.match_time, current_frame.ball)

        # 5. counterattack / transition technical noteandtechnical note (technical note‌withtechnical note in technical note chain)
        if self.current_seq and self.current_seq.is_active:
            self.transition_engine.update(self.current_seq, current_frame, att_dir, self.cfg, self._emit, self.generate_id)

        # 6. technical note / technical noteto inandfromtechnical note (istechnical notewithtechnical note zone-based)
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
            tags=["successful ✅" if pass_data.is_success else "failed ❌"] + pass_data.tags
        )
        self._emit(ev)

        # technical note line technical note: from technical noteandtechnical note technical note‌technical note Classifier real pass (without withtechnical notefromtechnical note technical note pass)
        if pass_data.is_success and "text text" in pass_data.tags and pass_data.forward_progress >= 6.0:
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
                    tags=["text line text"]
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

        # --- version 2: technical noteandtechnical note Chance → Shot only technical note technical note MATCH TIME ---
        # (Wall Clock after from technical note/stop/technical note technical note technical note technical note‌technical note andtechnical note game clock technical notestop istechnical note
        #  technical notefortechnical note technical note technical noteandtechnical notedatatechnical note only with time withtechnical note valid is.)
        # technical note: 0 <= shot_match_time - chance_match_time <= 3.0
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

        # register technical note technical note from technical noteandtechnical note technical note technical noteandtechnical note without technical note technical note string technical note
        # (Flag is_goal + related_event_ids → technical noteis Contribution technical noteandtechnical note technical noteandwithtechnical note score technical note technical note‌technical note)
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
                tags=["text text", f"text {shot_data.shooter_seat}"]
            ))
        return ev

    # -------------------------------------------------------------
    def register_goal_event(self, team: str, match_time: float,
                            source: str = "memory-hook",
                            shooter_seat: Optional[int] = None) -> GameEvent:
        """
        version 4 — register text «only» from text hook memory (GoalHooker).
        path legacy (textandtext ball from line + textandtext inandfromtext) text text is.
        text:
          1) textandtext to latest shot text team with windowtext MATCH TIME:
             0 <= goal_t - shot_t <= 4.0 (textandfrom ball/text in text withtext is)
             and text withtext text shot to «text» (metadata + tags).
          2) text "Goal ⚽" textandtext Event Bus → MomentumEngine textandtext passtext
             delaytext (Goal Pulse) and Dedup with Penalty Goal text text text‌text.
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
                    if "text" not in str(ev.metadata.get("outcome", "")):
                        ev.metadata["outcome"] = "text deterministic ⚽ (confirmation hook memory)"
                        if "text deterministic ⚽" not in ev.tags:
                            ev.tags.append("text deterministic ⚽ (hook)")
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
            tags=["text text", "hook memory ✅"]
        )
        self._emit(ev)
        return ev

# =====================================================================
# 25. Momentum Engine (technical note Threat/Event Decay technical note technical note Match Time)
# ---------------------------------------------------------------------
# HomeMomentum(t)  = Σ HomeEventImpact_i × decay(t - event_time_i)
# AwayMomentum(t)  = Σ AwayEventImpact_i × decay(t - event_time_i)
# NetMomentum(t)   = HomeMomentum(t) - AwayMomentum(t)
# decay(Δt) = exp(-λ Δt) technical note  λ = ln(2) / MOMENTUM_HALF_LIFE
#
# technical note technical noteortechnical note: Δt always technical note technical note GAME TIME is technical note Wall Clock.
# if Match Time technical note technical noteand frame change technical note Momentum technical note changetechnical note technical note‌technical note
# (Pause / Replay / Stop → chart technical note technical note‌technical note).
# =====================================================================
_LN2 = math.log(2.0)

class MomentumEngine:
    def __init__(self, config: MomentumScoringConfig):
        self.cfg = config
        self.impacts: List[EventImpact] = []
        self._impact_index: Dict[int, EventImpact] = {}
        # momentum_history structure istechnical note:
        # {"game_time" (time technical note withtechnical note), "disp_time" (time displaytechnical note with gap HT), "home","away","net"}
        self.history: List[Dict[str, float]] = [
            {"game_time": 0.0, "disp_time": 0.0, "home": 0.0, "away": 0.0, "net": 0.0,
             "phase": None}
        ]
        self._lock = threading.RLock()
        self._last_t = 0.0
        self._last_sample_t = -1.0
        # --- version 2: gap displaytechnical note technical note technical noteand technical note (HT Gap) ---
        # display_offset = technical noteuntiltechnical note technical note technical note to time withtechnical note second half for display
        # technical note technical note‌technical noteandtechnical note until technical note technical noteand technical note technical note empty technical noteandtechnical note with technical note HT technical note technical noteandtechnical note.
        self.display_offset: float = 0.0
        # (disp_start, disp_end) gap HT for render — None until before from HT
        self.ht_break: Optional[Tuple[float, float]] = None
        # --- version 5 ---
        # technical note current from technical note technical noteandtechnical noteandtechnical note (for technical note technical note technical noteandtechnical note technical note/technical note technical note‌technical note)
        self.half_number: int = 1
        # technical note direct technical note from hook memory (path independent from Event Bus) —
        # technical note technical note: {team, game_time, disp_time (frozen), half, wall}
        self.hook_goal_markers: List[Dict[str, float]] = []
        # --- versiontechnical note 10technical note27 — technical note direct red card (same technical noteandtechnical note technical note) ---
        # technical note technical note: {team, game_time (=momenttechnical note technical noteandtechnical note), disp_time (frozen), half, wall}
        self.red_card_markers: List[Dict[str, float]] = []
        # gap‌technical note displaytechnical note technical note (technical noteandtechnical note technical note resync_clock) — without technical note HT
        self.extra_breaks: List[Tuple[float, float]] = []
        # --- version 10technical note2: intechnical note technical notewithtechnical note gap stop (for technical note‌technical notefromtechnical note with line technical note) ---
        # {"a": technical note latest sampletechnical note before from stop, "b": technical note firsttechnical note sampletechnical note after from technical note}
        self._glue_smooth: Optional[Dict[str, int]] = None
        # --- versiontechnical note 10technical note15 — technical note technical notefrom Lifecycle technical noteandtechnical note sample‌technical note untiltechnical note ---
        # Worker technical notefrom current (HALF_1/HALF_2/ET1/ET2/…) technical note technical note technical note‌technical noteandtechnical note and technical note
        # sampletechnical note new (update/set_half_break/resync/reset) technical note technical note technical note technical note‌technical note.
        # technical note: technical note technical notefromtechnical note technical noteandtechnical note «without drop» restart in _tv_timeline.
        self.phase_label: Optional[str] = None

    def set_phase_label(self, label: Optional[str]):
        """text text textfrom current (from Worker — with change _match_phase synchronized text‌textandtext)."""
        try:
            self.phase_label = (str(label) if label is not None else None)
        except Exception:
            self.phase_label = None

    # -------------------------------------------------------------
    # technical note technical noteandtechnical note Unified Event Bus
    # -------------------------------------------------------------
    def on_event(self, event: GameEvent):
        with self._lock:
            impact = self._score_event(event)
            if impact is not None:
                self.impacts.append(impact)
                self._impact_index[impact.source_event_id] = impact
            # technical noteis Contribution / Deduplication technical note from receive technical noteandtechnical notedatatechnical note andtechnical note
            self._apply_post_links(event)

    def get_impact(self, source_event_id: int) -> Optional[EventImpact]:
        with self._lock:
            return self._impact_index.get(source_event_id)

    # -------------------------------------------------------------
    # technical note Event → EventImpact (technical note weight‌technical note from MomentumScoringConfig)
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
        # versiontechnical note 10technical note12 — apply_conf: for shot‌technical note technical note‌technical noteandtechnical note ApplyConfidence global
        # technical note technical noteand technical note (SHOT_APPLY_CONFIDENCE=False → score shot = Final Threat).
        _apply_conf = self.cfg.APPLY_CONFIDENCE if apply_conf is None else bool(apply_conf)
        conf = event.confidence if _apply_conf else 1.0
        final = base_weight * rel_mult * conf * sign
        # version 5: position displaytechnical note technical note technical note in momenttechnical note register frozen technical note‌technical noteandtechnical note
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

        # ---- Shot: base = final_threat (pre_shot_threat only save technical note‌technical noteandtechnical note) ----
        # versiontechnical note 10technical note12 — technical noteis new score shot (request user):
        #   * without technical note technical note → score technical noteandtechnical noteandtechnical note = Final Threat tool independenttechnical note
        #   * shot‌technical note technical note technical note technical note (SHOT_MIN_IMPACT) technical note — technical note shottechnical note
        #     technical noteandtechnical note from technical noteandtechnical note technical note technical noteandtechnical note in technical noteandtechnical noteandtechnical note technical note
        #   * shot technical note‌technical note (istechnical note user) × GOAL_LINKED_SHOT_RATIO technical note‌technical noteandtechnical note because
        #     score original technical note Goal (technical note 100) technical note‌technical note — without numbertechnical note technical noteandtechnical note.
        if t.startswith("Shot"):
            final_threat = float(md.get("final_threat", 0) or 0)
            base = final_threat * cfg.SHOT_WEIGHT
            note = ""
            # shottechnical note technical note‌technical note technical note technical note‌technical notedecreasetechnical note technical note‌technical note because Goal Event score original technical note technical note‌technical note
            if md.get("is_goal"):
                base *= cfg.GOAL_LINKED_SHOT_RATIO
                note = "goal-linked"
            else:
                # shot penalty with Penalty Goal/Miss technical note technical note‌technical noteandtechnical note
                if md.get("primary_type") == "penalty":
                    base *= cfg.PENALTY_SHOT_LINKED_RATIO
                    note = "penalty"
                # technical note technical note — shot‌technical note technical note never technical note technical note‌technical note
                if base < cfg.SHOT_MIN_IMPACT:
                    base = float(cfg.SHOT_MIN_IMPACT)
                    note = (note + "+min-floor" if note else "min-floor")
            return self._make_impact(ev, raw_threat=final_threat, base_weight=base,
                                     note=note or "final-threat",
                                     apply_conf=cfg.SHOT_APPLY_CONFIDENCE)

        # ---- Goal: passtechnical note delaytechnical note (Goal Response / Goal Pulse — version 2) ----
        # technical note technical note spike moment‌technical note is nottechnical note Contribution technical note technical note passtechnical note technical note:
        #   t < t_goal                     → 0
        #   t_goal ≤ t < t_goal + DELAY    → increment smooth (raised-cosine)
        #   until t_goal + DELAY + WIDTH      → technical note technical noteandtechnical note (value complete)
        #   technical note from technical note                       → decay technical note with same technical note‌technical note technical noteandtechnical noteandtechnical note
        # total technical note untiltechnical note technical note from MATCH TIME istechnical note in Pause automatic frozen technical note‌technical noteandtechnical note
        # and technical note technical note technical note (Wall Clock) technical noteandtechnical note technical note‌technical noteandtechnical note.
        # technical noteandtechnical note: technical note technical note — «Goal Kick» technical notemust to‌technical noteandtechnical note technical note score technical note
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
            # Dedup: if Goal technical note technical note beforetechnical note registeredtechnical note only technical noteuntiltechnical note technical note penalty technical note technical noteandtechnical note
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
            # Penalty Goal independent (without Goal technical noteandfromtechnical note) → technical noteandtechnical note passtechnical note technical note technical note technical note technical note‌technical note
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

        # ---- Pressure Episode: impact technical note and technical noteintechnical note ----
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

        # ---- Possession Change: without impact technical note (for chain technical noteandtechnical notedatatechnical note) ----
        if t == "Possession Change":
            if cfg.POSSESSION_CHANGE_WEIGHT <= 0:
                return None
            return self._make_impact(ev, raw_threat=cfg.POSSESSION_CHANGE_WEIGHT, base_weight=cfg.POSSESSION_CHANGE_WEIGHT)

        return None

    # -------------------------------------------------------------
    # technical noteis Contribution / Deduplication (technical noteandtechnical note from Double Counting)
    # -------------------------------------------------------------
    def _apply_post_links(self, ev: GameEvent):
        cfg = self.cfg
        # Shot → Chance technical note‌technical note technical note technical note‌technical notedecreasetechnical note technical note‌technical note
        if ev.event_type.startswith("Shot") and ev.related_event_ids:
            for rid in ev.related_event_ids:
                imp = self._impact_index.get(rid)
                if imp and imp.event_type in ("Chance", "Big Chance"):
                    imp.base_weight *= cfg.SHOT_LINKED_CHANCE_RATIO
                    imp.final_impact *= cfg.SHOT_LINKED_CHANCE_RATIO
                    imp.note = "capped (linked→shot)"
        # Penalty Goal / Penalty Miss → technical noteandtechnical note Penalty Kick technical note technical note‌technical notedecreasetechnical note technical note‌technical note
        if ev.event_type in ("Penalty Goal", "Penalty Miss") and ev.related_event_ids:
            for rid in ev.related_event_ids:
                imp = self._impact_index.get(rid)
                if imp and imp.event_type == "Penalty Kick":
                    imp.base_weight *= cfg.PENALTY_KICK_LINKED_RATIO
                    imp.final_impact *= cfg.PENALTY_KICK_LINKED_RATIO
                    imp.note = "linked→penalty-result"
        # --- version 2: Dedup technical noteandtechnical note — Goal technical noteandfromtechnical note technical note «after from» Penalty Goal independent
        # technical note‌technical note Penalty Goal beforetechnical note (technical note pulse complete technical note) to technical noteuntil technical note technical note‌technical noteandtechnical note
        # until technical note never technical noteand withtechnical note (and with technical noteand pulse) technical note technical noteandtechnical note.
        if ev.event_type.startswith("Goal") and "Kick" not in ev.event_type:
            # --- version 4: technical note confirmationtechnical note hook → shot technical note‌technical note technical note technical note‌technical notedecreasetechnical note
            # technical note‌technical note (GOAL_LINKED_SHOT_RATIO) until technical note never technical noteand withtechnical note score technical note
            # exactly same technical noteistechnical note technical note for is_goal in momenttechnical note register shot technical note technical note‌technical note.
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
                    imp.is_goal_pulse = False      # pulse original technical note Goal technical note technical note‌technical note
                    imp.goal_time = 0.0
                    imp.peak_time = 0.0
                    imp.parallel_goal_dedup = True
                    imp.note = "delta (parallel Goal arrived later)"

    # -------------------------------------------------------------
    # Decay and passtechnical note technical note (only technical note technical note Match Time)
    # -------------------------------------------------------------
    def decay_factor(self, dt: float) -> float:
        if dt <= 0:
            return 1.0
        return math.exp(-_LN2 * dt / max(1e-6, self.cfg.MOMENTUM_HALF_LIFE))

    def goal_response_factor(self, imp: EventImpact, t: float) -> float:
        """
        text passtext text (Goal Pulse) — untiltext text from time withtext:
          t < t_goal                    → 0.0
          t_goal ≤ t < peak_time        → raised-cosine from 0 until 1
          peak_time ≤ t < peak+W        → 1.0 (text textandtext)
          t ≥ peak+W                    → decay text with text‌text textandtextandtext
        text textortext (scenariotext Pause after from text):
          if game clock textstop text t text is and output text untiltext text text
          text‌text text textwithtext for textand text time andtextandtext text and never from
          Wall Clock for textand text textandtext X istext text‌textandtext. when withtext from
          45:12 to 45:17 text textandtext textandtextto‌textandtext in same Match Time text text‌textandtext.
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
        """textfrom text passtext text for textandtext textwithtext"""
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
                # passtechnical note delaytechnical note technical note: technical note before from t_goaltechnical note technical noteandtechnical note in peak_time
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
        in text text withtext text text‌textandtext. if Match Time textand text withtext
        (Pause/Replay/Stop) text sample and decay newtext register text‌textandtext.

        version 10text2 — textwithtext gap stop‌text (text text text after from text):
        if text textand sampletext textandtext game clock text from MOMENTUM_GLUE_GAP text
        text (stop text text/Replay with text currently text)text to‌text register text
        sampletext textandtext in text gap (text textandtext chart «text‌line text» text‌text)text
        only text display to‌textfromtext same withtext text text text‌textandtext sampletext
        aftertext exactly text interval after from latest sampletext real text‌text and
        textand textside chart unchanged texttotaltext text to text text‌text. intext text
        text text to‌text text firsttext sampletext aftertext with text text‌line direct text
        text‌textandtext (_apply_glue_smoothing_locked). gap‌text text‌text
        withtext text (HT / resync textand) watchdog NaN text and never textwithtext
        text‌textandtext.
        """
        with self._lock:
            if current_match_time <= self._last_t:
                self._last_t = current_match_time
                return
            # --- version 10technical note2: detection gap stop (only when latest sample real is) ---
            glue_anchor = -1
            if self._last_sample_t >= 0.0 and self.history:
                _last_hist = self.history[-1]
                _is_nan_guard = _last_hist["net"] != _last_hist["net"]
                _gap = float(current_match_time) - float(self._last_sample_t)
                if (not _is_nan_guard) and _gap > self.cfg.MOMENTUM_GLUE_GAP:
                    # withtechnical note technical note stop from technical noteandtechnical note display technical note technical note‌technical noteandtechnical note: technical note display
                    # technical noteandtechnical note technical note technical note‌technical noteandtechnical note technical note sampletechnical note aftertechnical note technical notedistance after from latest
                    # sampletechnical note real technical note (technical noteand technical noteside technical note‌technical note). technical noteandtechnical note: assignment
                    # «technical note» is technical note incrementtechnical note — last_disp technical noteandtechnical note technical note technical note
                    # technical note beforetechnical note (HT and intechnical note technical note) is and technical noteandtechnical note technical note
                    # exactly only technical note withtechnical note technical note technical note technical note technical note‌technical note.
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
                    "wall": time.time(),   # versiontechnical note 10technical note12 — silence real = technical note technical note
                    "phase": self.phase_label   # versiontechnical note 10technical note15 — technical note technical notefrom Lifecycle
                })
                self._last_sample_t = current_match_time
                if glue_anchor >= 0:
                    # intechnical note technical notewithtechnical note — with firsttechnical note sampletechnical note aftertechnical note with line technical note technical note technical note‌technical noteandtechnical note
                    self._glue_smooth = {"a": glue_anchor, "b": len(self.history) - 1}
                self._apply_glue_smoothing_locked()
            self._last_t = current_match_time

    def _apply_glue_smoothing_locked(self):
        """
        version 10text2 — text text text text textwithtext with text line text.
        after from textwithtext textand textside charttext to‌text text firsttext sampletext after from
        intext textand sampletext text text textandtext text‌line directtext «sampletext before from stop
        ← sampletext after from intext» withtextandtext text‌textandtext until text textandtext text in text
        intext text textandtext. only text textand sampletext intext text text‌textandtext and text
        sample‌text (and time‌text) unchanged text‌text.
        """
        js = self._glue_smooth
        if js is None:
            return
        a, b = int(js["a"]), int(js["b"])
        if (b + 1) >= len(self.history):
            return                        # still sampletechnical note aftertechnical note technical note — pending technical note‌technical note
        self._glue_smooth = None          # technical note‌withtechnical note
        if a < 1:
            return                        # technical note before from intechnical note andtechnical noteandtechnical note technical note
        L = self.history[a - 1]
        A = self.history[a]
        B = self.history[b]
        R = self.history[b + 1]
        vals = (L["net"], A["net"], B["net"], R["net"])
        if any(v != v for v in vals):     # watchdog NaN (gap HT) → technical note technical note
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
        version 2 — register transition text textand text (Half-Time):
        chart text text‌textandtext only text gap displaytext textandtext (text HT) text latest
        sampletext first half and sample‌text second half intext text‌textandtext.
        textand sampletext NaN to‌textandtext watchdog intext text‌textandtext until line/text chart textandtext
        gap «text» text. from text text to time withtext sample‌text new offset text
        text‌textandtext. text textortext text text Wall Clock is not.
        resume_game_t: firsttext time withtext second half (text 45:00=2700s) — if
        text from latest time first half withtext (andtext textto‌text)text offset text text
        same text textto text‌textandtext until sample‌text second half never andtext gap textandtext.

        version 5 — text withtext «chart text second half text text‌text»:
        withtext text text for start second half to 45:00 text‌text in versiontext 4
        _last_t textandtext text register‌text first half (text 45:00+text) withtext
        text‌text and update() until textandtext game clock from text text text sample‌text
        register text‌text → text second half textandtext chart empty text‌text.
        textandtext text internal textandtextandtext to base_t (text resume) text text‌textandtext and
        _last_sample_t text text interval text‌text text text‌textandtext until «firsttext
        secondtext second half» textdistance (correct after from line side textis gap) text textandtext.
        """
        with self._lock:
            last = self.history[-1] if self.history else None
            last_disp = float(last["disp_time"]) if last else 0.0
            last_game = float(last["game_time"]) if last else 0.0
            gap = max(10.0, float(gap_seconds))
            base_t = self._last_t
            if resume_game_t is not None:
                base_t = min(self._last_t, float(resume_game_t))
            # sample‌technical note watchdog NaN — technical note technical note chart in gap HT
            _now_wall = time.time()
            self.history.append({"game_time": last_game, "disp_time": last_disp,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            self.history.append({"game_time": base_t, "disp_time": last_disp + gap,
                                 "home": float('nan'), "away": float('nan'), "net": float('nan'),
                                 "wall": _now_wall, "phase": self.phase_label})
            # resume second half: time displaytechnical note = time withtechnical note + offset
            self.display_offset = (last_disp + gap) - base_t
            self.ht_break = (last_disp, last_disp + gap)
            # --- version 5 (technical note technical note withtechnical note 2) ---
            self._last_t = base_t
            self._last_sample_t = base_t - max(0.05, self.cfg.HISTORY_SAMPLE_INTERVAL) - 1e-6
            self.half_number = 2

    # -------------------------------------------------------------
    # version 5 — technical note direct technical note from hook memory (path independent from Event Bus)
    # -------------------------------------------------------------
    def add_hook_goal_marker(self, team: str, game_time: float, half: int = 0):
        """
        register direct text text text textandtext chart — to‌text change countertext text text team.
        position displaytext (disp_time) in same moment with display_offset current frozen
        text‌textandtext in text text if aftertext text change text text text text text‌text.
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
    # versiontechnical note 10technical note27 — technical note direct red card (same technical noteandtechnical note technical note — technical note 2017)
    # -------------------------------------------------------------
    def add_hook_red_card_marker(self, team: str, game_time: float,
                                 half: int = 0,
                                 disp_time: Optional[float] = None):
        """
        register direct text text red card — text text text with text textandtext text
        disp_time text‌textandtext «momenttext textandtext» withtext: assignment team card text second
        after from textandtext (text player text in z=40) text text‌textandtext text
        text must textandtext momenttext textandtext text text momenttext detection.
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
    # version 5 — technical noteandtechnical note technical note: withtechnical note technical note without detection HT/new match
    # -------------------------------------------------------------
    def resync_clock(self, resume_t: float, gap_seconds: float = 90.0):
        """
        when withtext from text stop text from text text text‌textandtext text text HT detection data
        text and text new matchtext game clock text‌textandtext «text‌text from latest sampletext»
        text withtext. in versiontext 4 update() in text text until text text to text beforetext
        text sample‌text register text‌text and chart text for text text text‌text.
        text text sampling text textandtext from text text‌text:
          * text textandtext text text → only sampling immediate (without gap)
          * text text‌text text text → text NaN + gap displaytext textandtext + text new
            (chart beforetext text and display resumetext withtext in resumetext textandtext intext text‌textandtext)
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
            # --- version 5 ---
            self.half_number = 1
            self.hook_goal_markers.clear()
            self.red_card_markers.clear()   # versiontechnical note 10technical note27 — technical note red card
            self.extra_breaks.clear()


# =====================================================================
# 25.1 render chart Momentum (shared technical note App and Self-Test — version 2)
# ---------------------------------------------------------------------
# chart original only technical note technical note technical noteandtechnical note is (without lineandtechnical note technical note Home/Away):
#   ✔ Net Area technical note‌technical note: Net>0 → technical note/withtechnical note (Home) | Net<0 → technical note/below (Away)
#   ✔ line Zero
#   ✔ Goal Marker: line technical noteandtechnical note + ⚽ exactly technical noteandtechnical note t_goal (technical note peak)
#   ✔ gap HT technical note technical noteand technical note (sample‌technical note NaN) + technical note HT
#   ✔ Gaussian smoothing real only technical noteandtechnical note layer display — RAW unchanged
# technical noteandtechnical note X always Game Clock is (never Wall Clock).
# =====================================================================
