class PitchConfig:
    FIELD_LENGTH = 105.0
    FIELD_WIDTH = 68.0
    HALF_LENGTH = FIELD_LENGTH / 2.0   # 52.5m
    HALF_WIDTH = FIELD_WIDTH / 2.0     # 34.0m

    GOAL_HALF_WIDTH = 3.66             # Z = +/- 3.66m
    GOAL_HEIGHT = 2.44                 # Y = 2.44m
    POST_RADIUS = 0.12                 # radius physical post
    BALL_RADIUS = 0.11                 # radius ball
    POST_COLLISION_RADIUS = 0.32       # threshold detection technical noteandtechnical note with post (calibrated Shot Engine)

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

    # threshold‌technical note technical note andtechnical note cross and technical note‌technical note (calibrated Pass Engine)
    CROSS_LATERAL_THRESHOLD = 20.1      # technical noteintechnical note Z must technical note from 20.1 withtechnical note
    CROSS_LONGITUDINAL_THRESHOLD = 29.0 # technical noteintechnical note X must technical note from 29 withtechnical note
    CUTBACK_ORIGIN_X_THRESHOLD = 35.0   # technical noteintechnical note X technical note must technical note from 35 withtechnical note
    CUTBACK_MAX_HEIGHT = 1.80           # technical note height technical note‌technical note

    HEIGHT_GROUND_MAX = 0.70            # boundary cross/pass pitchtechnical note
    HEIGHT_AERIAL_MIN = 1.60            # boundary cross/pass technical noteandtechnical note

# =====================================================================
# 4. technical note technical note shot (ShotConfig — calibrated‌technical note unchanged)
# =====================================================================
class ShotConfig:
    MAX_TRACK_TIME = 3.0               # technical note time technical note technical noteandfrom shot to second
    WORLD_TO_METER_SCALE = 1.0         # technical noteortechnical note coordinates to technical note
    MIN_VALID_SHOT_SPEED = 18.0        # technical note technical note shot valid (km/h)
    MAX_PLAUSIBLE_SPEED = 185.0        # technical note technical note physical shot (km/h)

    HEADER_HEIGHT_MIN = 1.45           # technical note height start for check technical noteto technical note
    HEADER_HEIGHT_OPTIMAL = 1.65       # height istechnical note for technical noteto technical note
    VOLLEY_HEIGHT_MIN = 0.45           # technical note height andtechnical note
    VOLLEY_HEIGHT_MAX = 1.40           # technical note height andtechnical note

    GK_MAX_REACH_HEIGHT = 2.70         # technical note height technical note inandfromtechnical note‌withtechnical note for technical note
    OUTFIELD_MAX_REACH_HEIGHT = 2.20   # technical note height technical note technical note for technical noteandtechnical note

    STATIONARY_RADIUS = 0.22           # radius technical note technical note for ball technical note
    STATIONARY_DURATION_MIN = 0.75     # technical note time technical noteandtechnical note for technical notewithtechnical note technical note (second)

    # --- versiontechnical note 10technical note14 — layertechnical note Trigger → Contact/Shooter → Tracking → Registration ---
    # (specification user: «1 increment counter = 1 technical note shot» + technical noteandtechnical note technical note technical note
    #  frame/time withtechnical note technical note untiltechnical note‌technical noteandtechnical note technical noteanduntiltechnical note technical noteandtechnical note)
    SHOT_CONTACT_SCOPE = 26            # technical noteandtechnical note immediate momenttechnical note technical noteto (frame — calibrated tool independent)
    SHOT_PENDING_SCOPE = 120           # technical noteandtechnical note technical note in technical note‌technical note aftertechnical note (buffer 320 frametechnical note)
    SHOT_RECOVERY_MAX_FRAMES = 260     # windowtechnical note technical noteandtechnical note technical note technical note frame (technical note with buffer 320)
    SHOT_RECOVERY_MAX_MATCH_SEC = 6.0  # windowtechnical note technical noteandtechnical note technical note technical note time withtechnical note
    SHOT_FINALIZED_KEEP = 64           # technical note technical note technical note technical note register‌technical note (Dedup)

    CORRIDOR_BASE_WIDTH = 1.8          # width technical note in technical note technical noteto
    CURVE_MIN_TRAJECTORY_LEN = 4.5     # technical note length path for check technical note ball
    CURVE_RATIO_THRESHOLD = 0.052      # threshold detection shot technical note‌technical note

# =====================================================================
# 5. technical note technical note scoretechnical note Momentum (without Magic Number in technical note)
# =====================================================================
class MomentumScoringConfig:
    # --- Pass: threat_score pass source score is ---
    PASS_SUCCESS_MULTIPLIER = 1.00
    PASS_FAILURE_MULTIPLIER = 0.20

    # --- Chance ---
    CHANCE_WEIGHT = 35.0
    BIG_CHANCE_WEIGHT = 75.0

    # --- Shot: technical note original final_threat istechnical note pre_shot_threat only save technical note‌technical noteandtechnical note ---
    # versiontechnical note 10technical note12 (request user): «shot‌technical note technical note technical note in technical noteandtechnical noteandtechnical note technical note technical note
    # shot‌technical note technical note to technical note technical note must score technical note technical note withtechnical note» —
    #   * SHOT_APPLY_CONFIDENCE = False → score technical noteandtechnical noteandtechnical note shot exactly technical note
    #     Final Threat tool independent is (technical note technical note 0technical note55-0technical note95 technical note technical note technical note
    #     until 45technical note technical note technical note‌technical note — technical note original «score technical note technical note from tool shot»)technical note
    #   * SHOT_MIN_IMPACT = technical note technical note for shot‌technical note «technical note technical note» (technical note shot technical noteandtechnical note
    #     from technical noteandtechnical note technical note technical note technical note‌technical note technical note)technical note
    #   * shot technical note‌technical note technical note × GOAL_LINKED_SHOT_RATIO technical note‌technical noteandtechnical note until technical note never technical noteand
    #     withtechnical note technical note technical noteandtechnical note (istechnical note technical note user).
    SHOT_WEIGHT = 1.00                 # technical note technical note technical noteandtechnical note final_threat
    SHOT_APPLY_CONFIDENCE = False      # shot: technical note technical note technical note‌technical note technical note technical noteandtechnical note
    SHOT_MIN_IMPACT = 45.0             # technical note score technical noteandtechnical noteandtechnical note shot‌technical note technical note
    GOAL_LINKED_SHOT_RATIO = 0.30      # technical note shottechnical note technical note‌technical note (technical noteandtechnical note from technical noteand withtechnical note technical note technical note with Goal)
    PENALTY_SHOT_LINKED_RATIO = 0.40   # technical note shottechnical note technical note technical noteandtechnical note technical note «penalty» detection data technical note
    SHOT_LINKED_CHANCE_RATIO = 0.30    # technical note technical note Chance in technical noteandtechnical note technical note to Shot
    # windowtechnical note detection «shot technical note» — versiontechnical note 10technical note14: technical noteandtechnical note Dedup only with technical note
    # technical note technical note technical note‌technical noteandtechnical note (candidate_id) and technical note technical noteand technical note technical note istechnical note technical note‌technical noteandtechnical note
    SHOT_DUP_MATCH_WINDOW = 1.0
    SHOT_DUP_POS_RADIUS = 2.5

    # --- Goal (passtechnical note delaytechnical note technical note — Goal Response / Goal Pulse) ---
    GOAL_WEIGHT = 100.0
    # distancetechnical note technical noteandtechnical note passtechnical note technical note from momenttechnical note technical note — only technical note technical note secondtechnical note withtechnical note (Game Time)
    GOAL_PEAK_DELAY = 5.0
    # length technical note technical noteandtechnical note (technical note) passtechnical note technical note technical note from start decay technical note — secondtechnical note withtechnical note
    GOAL_RESPONSE_WIDTH = 4.0

    # --- Penalty ---
    PENALTY_WEIGHT = 20.0              # weight technical noteandtechnical note technical note Penalty Kick
    PENALTY_GOAL_WEIGHT = 60.0         # weight Penalty Goal without technical note register‌technical note technical noteandfromtechnical note
    PENALTY_GOAL_DELTA_WEIGHT = 15.0   # weight Penalty Goal when Goal technical note technical note beforetechnical note registeredtechnical note
    PENALTY_GOAL_DEDUP_WINDOW = 5.0    # window timetechnical note (second withtechnical note) detection Goal technical noteandfromtechnical note
    PENALTY_MISS_WEIGHT = 25.0
    PENALTY_MISS_NEGATIVE = True       # penalty from technical note technical note = momentum technical note for technical note
    PENALTY_KICK_LINKED_RATIO = 0.25   # technical note weight Penalty Kick technical note from register Penalty Goal/Miss

    # --- Pressure Episode ---
    PRESSURE_BASE_WEIGHT = 6.0
    PRESSURE_DURATION_FACTOR = 0.8
    PRESSURE_INTENSITY_FACTOR = 2.5
    PRESSURE_MAX_WEIGHT = 18.0
    PRESSURE_MIN_DURATION = 4.0        # technical note length technical noteandtechnical note pressure (second withtechnical note)
    PRESSURE_MIN_AVG = 1.2             # technical note technical noteortechnical note count pressuretechnical note
    PRESSURE_RADIUS = 3.0              # radius pressure technical noteandtechnical note technical note ball
    PRESSURE_CARRIER_RADIUS = 2.5      # radius detection technical note ball
    PRESSURE_RELIEF_TIME = 2.0         # time technical note pressure for technical note technical noteandtechnical note

    # --- Transition / Counterattack / Line Break ---
    TRANSITION_WEIGHT = 8.0
    COUNTERATTACK_WEIGHT = 18.0
    COUNTERATTACK_WINDOW = 8.0         # technical note time technical note to third for counterattack
    TRANSITION_WINDOW = 10.0           # technical note time technical noteandtechnical note to technical note technical noteandtechnical note for transition
    LINE_BREAK_WEIGHT = 12.0
    LINE_BREAK_COOLDOWN = 8.0

    # --- Zone Entries ---
    FINAL_THIRD_ENTRY_WEIGHT = 3.0
    BOX_ENTRY_WEIGHT = 6.0
    ZONE_EVENT_COOLDOWN = 12.0         # technical noteandtechnical note from technical notewithtechnical note chart with andtechnical noteandtechnical note technical note
    CORNER_WEIGHT = 8.0
    CORNER_COOLDOWN = 25.0
    GOAL_KICK_WEIGHT = 2.0
    GOAL_KICK_COOLDOWN = 25.0

    # --- Possession Change (technical note for chain technical noteandtechnical notedatais technical note score) ---
    POSSESSION_CHANGE_WEIGHT = 0.0

    # --- Reliability / Confidence ---
    CERTAIN_MULTIPLIER = 1.00
    PROBABLE_MULTIPLIER = 0.85
    INFERRED_MULTIPLIER = 0.65
    APPLY_CONFIDENCE = True            # technical note technical note in confidence technical noteandtechnical note

    # --- Decay (technical note technical note GAME TIME) ---
    MOMENTUM_HALF_LIFE = 180.0         # technical note‌technical note = 3 minute match time

    # --- Presentation / Normalization (only layer display) ---
    DISPLAY_RANGE = 100.0
    DISPLAY_NORMALIZATION = "fixed"    # fixed | peak | raw
    DISPLAY_SOFT_SCALE = 120.0         # technical noteortechnical note soft-clip currentlytechnical note fixed
    # Gaussian smoothing real (technical note technical noteortechnical note technical note) — only technical noteandtechnical note layer displaytechnical note
    # value technical note technical note secondtechnical note time withtechnical note is and independent from technical note sampling technical note technical note‌technical noteandtechnical note.
    # version 4: 16.0s — technical noteandtechnical note peak‌technical note technical note «chart bell-shaped» smooth and technical note technical note‌technical noteandtechnical note
    # technical note‌technical noteandtechnical note‌technical note in technical noteandtechnical note technical noteandtechnical note technical note technical note‌technical noteandtechnical note RAW unchanged technical note‌technical note
    # versiontechnical note 10technical note27: 16.0 → 20.0 — same technical note «bell-shaped» versiontechnical note 2017technical note
    # peak‌technical note/valley‌technical note smooth‌technical note and technical note‌technical note technical note‌technical noteandtechnical note (RAW technical note unchanged)
    GAUSSIAN_SIGMA = 20.0     # v10.27 — 16→20 (technical noteandtechnical notefromtechnical note technical noteandtechnical noteandtechnical note — technical note smooth‌technical note)

    # --- History Sampling ---
    HISTORY_SAMPLE_INTERVAL = 0.10     # technical note 0.1 second time withtechnical note technical note sample

    # --- version 10technical note2: technical notewithtechnical note gap stop‌technical note (technical note technical note technical note after from technical note) ---
    # if technical note technical noteand sampletechnical note technical noteandtechnical note game clock technical note from technical note value technical note technical note
    # (stop technical note technical note/Replay with technical note currently technical note)technical note withtechnical note technical note from technical noteandtechnical note
    # «display» technical note technical note‌technical noteandtechnical note: sampletechnical note aftertechnical note exactly technical note interval after from latest
    # sampletechnical note real technical note‌technical note (technical noteand technical noteside chart to technical note technical note‌technical note) and intechnical note technical note
    # technical note with technical note technical note‌line direct technical note technical note‌technical noteandtechnical note. technical noteandtechnical note technical noteandtechnical note technical note change
    # technical note‌technical note (technical note = versiontechnical note beforetechnical note).
    MOMENTUM_GLUE_GAP = 4.0            # thresholdtechnical note detection gap stop (secondtechnical note time withtechnical note)

    # --- version 10technical note2: icon ball technical note (tex/ball_icon.png technical note code) ---
    BALL_ICON_SIZE_PT = 22.0           # technical note displaytechnical note icon ball technical noteandtechnical note chart (Point)

    # --- Match Restart Detection ---
    MATCH_RESTART_DELTA = 5.0          # decrease technical note time withtechnical note = restart technical note

    # --- detection HT / new match (version 3) ---
    # chart in end first half and «end total technical note» never automatic technical note technical note‌technical noteandtechnical note
    # only start «new match» (untiltechnical note from technical note + PLAYING) or buttontechnical note «reset technical note»
    # reset complete technical note technical note‌technical note. technical note technical noteand technical note gap displaytechnical note with technical noteand line technical noteuntiltechnical note
    # and technical note HT technical noteandtechnical note technical noteandtechnical note X intechnical note technical note‌technical noteandtechnical note.
    # version 4: width gap third version 3 → 300 second (5 minute from total technical note)
    HT_GAP_DISPLAY_SECONDS = 300.0     # version 4: width gap = 5 minute (third 900 secondtechnical note beforetechnical note)
    HT_MIN_FIRST_HALF_PLAYED = 1500.0  # technical note time withtechnical note‌technical note first half for detection HT
    HT_RESUME_TOLERANCE = 600.0        # resume technical note to end first half = HT (technical note new match)
    NEW_GAME_MAX_START = 180.0         # resume technical note technical note value = new match (untiltechnical note from technical note)

    # --- version 10technical note3: rule technical note HT (Match Lifecycle State Machine) ---
    # technical note technical note HT technical note only to technical noteandtechnical note technical note is nottechnical note technical note rule technical note always
    # inside Logic technical note technical note‌technical noteandtechnical note:
    #   HT only when valid is technical note «first half andtechnical note technical note technical note withtechnical note»:
    #     previous_match_time >= 45*60 (2700s)
    #     AND current_match_time technical noteandtechnical note 45:00 (windowtechnical note [2700-slacktechnical note 2700+tolerance])
    #     AND current_state == PLAYING
    #   untiltechnical note ≈ technical note (NEW_GAME_MAX_START) always «new match» istechnical note never HT —
    #   technical note if withtechnical note beforetechnical note technical noteandtechnical note technical note minute‌technical note technical notestop technical note withtechnical note (technical note technical noteandtechnical note).
    HT_HARD_MIN_FIRST_HALF = 2700.0    # 45*60 — technical note time technical note‌technical note first half for HT real
    HT_RESUME_LOWER_SLACK = 30.0       # resume must «technical noteandtechnical note 45:00» withtechnical note (technical note andtechnical note withtechnical note)

    # --- versiontechnical note 10technical note15 — extra time (technical note technical note/technical note technical note technical noteandtechnical note reset user) ---
    # windowtechnical note «technical noteandtechnical note 90:00 / 105:00» for start ET1/ET2 after from reset untiltechnical note:
    # firsttechnical note sampletechnical note livetechnical note ET possible is technical note after from boundary technical noteandtechnical note technical noteortechnical note (delay line technical noteandtechnical note
    # or withtechnical note resume‌technical notedecreasetechnical note in silence technical note) — 12 minute windowtechnical note technical note and technical note is.
    ET_RESET_TOLERANCE = 720.0

# =====================================================================
# 6. hook possession (PossessionHooker — version andtechnical note)
# =====================================================================
# versiontechnical note 10technical note18 — cycletechnical note technical noteortechnical note new hook possession (specification technical note user):
#   * hook «only» in technical notefrom technical note address technical note is: to technical note technical note technical note untiltechnical note (start
#     new match) technical note technical note‌technical noteandtechnical note before from technical note line technical note unchanged technical note‌technical note
#   * firsttechnical note address Capture‌technical note‌technical note technical note «value 2» (Home) in technical note withtechnical note address
#     detection Home/Away istechnical note address‌technical note without value 2 technical note and technical note technical note technical note‌technical noteandtechnical note
#   * after from confirmationtechnical note hook «technical note» technical note‌technical noteandtechnical note and same address until match end
#     technical noteandtechnical note technical note‌technical noteandtechnical note (hook technical note‌technical note technical note structure technical note technical noteto‌technical note technical note‌technical note and
#     capture‌technical note technical note/technical note technical note‌technical notefromtechnical note)technical note
#   * technical note withtechnical note untiltechnical note technical note technical note cycletechnical note technical note again technical notefrom technical note‌technical noteandtechnical note.
# =====================================================================
POSS_CAPTURE_LOG = False     # versiontechnical note 10technical note24 — default technical noteandtechnical note (technical note log technical noteandtechnical note for technical note‌ortechnical note True technical noteandtechnical note)


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
        self.captured_wall = None        # versiontechnical note 10technical note18 — momenttechnical note confirmation capture
        self.is_hooked = False

    def hook(self, h_process, base_addr: int):
        if self.is_hooked:               # versiontechnical note 10technical note18 — technical note again technical notemenutechnical note
            return
        self.target_address = base_addr + 0x9DFA86
        self.cave_address = allocate_near_target(h_process, self.target_address)
        if not self.cave_address:
            raise Exception("Error in text memory for hook possession.")

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
        version 10text4 — re-arm text textwithtext Capture possession (textandtext reset_capture goal hook).

        text: text hook address rdi+0x58 text only «text‌withtext» (firsttext text instruction after
        from text) in text inside withtext text‌textandtext and side textandtext text same text for
        always cache text‌text. in withtext «new match»text withtext structure text/possession
        text in address fresh text‌textfromtext Capture legacy to address text text‌textandtext →
        possession None/frozen → unchanged possessiontext text pass/shot/text register
        text‌textandtext (text text‌text «from withtext second to after only text‌text»).

        text text text inside withtext text text text‌text (until instruction possession in firsttext text
        aftertext again Capture text) and text side textandtext text text text‌text. text text with
        h_process=None only text textandtext text text text‌text (text for test).
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
            # --- versiontechnical note 10technical note18 — technical notewithtechnical noteagetechnical note user: only addresstechnical note technical note in momenttechnical note
            # capture «value 2» (Home) in technical note is technical note technical note‌technical noteandtechnical note technical note
            # technical note and technical note technical note technical note‌technical noteandtechnical note until technical noteandtechnical noteuntiltechnical note aftertechnical note again Capture technical note.
            candidate = buf.value
            val = ctypes.c_uint8(0)
            kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(candidate), ctypes.byref(val), 1, None)
            if val.value != 2:
                _poss_capture_log(
                    f"capture text text (val={val.value}) addr=0x{candidate:X} "
                    "— text text text text textandtextuntiltext aftertext")
                self.reset_capture(h_process)
                return None
            self.captured_address = candidate
            self.captured_wall = time.time()
            _poss_capture_log(
                f"address Home/Away confirmation text: 0x{candidate:X} (value 2 = Home) "
                "— hook text text‌textandtext until match end text address textandtext text‌textandtext")
            # user: after from detectiontechnical note hook technical note technical noteandtechnical note — line technical note to technical note original
            # technical note‌technical note and only readtechnical note same address resume technical note.
            self.unhook(h_process)

        val = ctypes.c_uint8(0)
        kernel32.ReadProcessMemory(h_process, ctypes.c_void_p(self.captured_address), ctypes.byref(val), 1, None)
        if val.value == 2: return "Home"
        if val.value == 1: return "Away"
        return None

# =====================================================================
# 7. hook new match time (TimeHooker)
# ---------------------------------------------------------------------
# instruction withtechnical note:  FL_2026.exe+20F1CDA - 89 86 40010000 - mov [rsi+00000140],eax
#   Seconds = [rsi+0x140]   (same technical note technical note eax technical noteandtechnical note technical note‌technical noteandtechnical note)
#   Minutes = [rsi+0x13C]   (technical note 4 byte before)
# Cave: technical note instruction original + capture RSI in technical note memory slot internal
# =====================================================================
class TimeHooker:
    HOOK_OFFSET = 0x20F1CDA
    ORIG_BYTES = b'\x89\x86\x40\x01\x00\x00'   # mov [rsi+00000140],eax
    MINUTES_OFFSET = 0x13C
    SECONDS_OFFSET = 0x140

    def __init__(self):
        self.cave_address = None
        self.target_address = None
        self.data_address = None      # slot technical note RSI technical noteagetechnical note‌technical note
        self.is_hooked = False
        self.last_valid_wall = 0.0    # latest withtechnical note technical note time valid technical noteandtechnical note technical note (only technical notewithtechnical note)
        # [suite v2.1.5] bridge-managed time hook: the bytes belong to the
        # bridge, this object only READS the shared RSI slot and releases
        # its reference on unhook. Never writes game bytes in this mode.
        self.via_bridge = False
        self._bridge_cli = None

    def hook(self, h_process, base_addr: int):
        self.target_address = base_addr + self.HOOK_OFFSET

        # technical noteistechnical note‌technical note technical note instruction original before from technical noteandtechnical note write
        curr = safe_read(h_process, self.target_address, len(self.ORIG_BYTES))
        if curr is None:
            raise Exception("read memory Time Hook possible text.")
        if curr == self.ORIG_BYTES:
            pass  # technical note technical note
        elif curr[0] == 0xE9:
            raise Exception("Time Hook beforetext text text is (text beforetext Restore text). withtext text restart text.")
        else:
            raise Exception(
                "text instruction time text text: " + curr.hex().upper() +
                " (text 0x20F1CDA textortext to withtext text)"
            )

        self.cave_address = allocate_near_target(h_process, self.target_address, 128)
        if not self.cave_address:
            raise Exception("Error in text memory for Time Hook.")

        self.data_address = self.cave_address + 0x40   # slot 8 bytetechnical note RSI
        code_start = self.cave_address + 0x20

        # ---------- Cave ----------
        # mov [rsi+0x140], eax      ; instruction original withtechnical note       (6)
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
            raise Exception("cleanup slot time failed textandtext.")
        if not safe_write(h_process, code_start, bytes(cave)):
            raise Exception("write code Time Hook in Cave failed textandtext.")

        patch = b'\xE9' + struct.pack('<i', code_start - (self.target_address + 5)) + b'\x90'
        if safe_write(h_process, self.target_address, patch):
            self.is_hooked = True
        else:
            raise Exception("text Patch Time Hook textandtext withtext failed textandtext.")

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
        textandtext text total_match_seconds:
        - if second to‌textandtext second‌text textandtext (0..59) withtext -> minutes*60 + seconds
        - if withtext second text to‌textandtext counter/total second save text withtext (> 59) -> textandtext text value
        """
        if seconds <= 59:
            return float(minutes * 60 + seconds)
        return float(seconds)

    def read_time_registers(self, h_process) -> Optional[Tuple[int, int]]:
        """read (Minutes, Seconds) from structure time withtext from text RSI textagetext‌text"""
        if not self.is_hooked or not self.data_address:
            return None
        raw = safe_read(h_process, self.data_address, 8)
        if not raw:
            return None
        rsi_val = struct.unpack('<Q', raw)[0]
        if not rsi_val or rsi_val < 0x10000:
            return None  # still capture technical note

        raw_m = safe_read(h_process, rsi_val + self.MINUTES_OFFSET, 4)
        raw_s = safe_read(h_process, rsi_val + self.SECONDS_OFFSET, 4)
        if not raw_m or not raw_s:
            return None

        minutes = struct.unpack('<I', raw_m)[0]
        seconds = struct.unpack('<I', raw_s)[0]

        # technical note technical note technical noteandtechnical note technical note
        if minutes > 300 or seconds > 10800:
            return None

        self.last_valid_wall = time.time()
        return minutes, seconds

# =====================================================================
# 7.5 hook register technical note from memory (GoalHooker — version 6 — Sticky First-Capture)
# ---------------------------------------------------------------------
# instruction withtechnical note (technical note Home):
#   FL_2026.exe+19ECBE2 - 44 89 89 58010000 - mov [rcx+00000158],r9d
# countertechnical note technical note Away: «exactly 4 byte technical noteandtechnical note» from technical note countertechnical note Home
#   → byte [rcx+0x15C]
# technical note technical noteand «technical note technical note‌bytetechnical note» technical note (countertechnical note technical note technical note teamtechnical note technical note 0,1,2,...)
#
# technical note (version 6 — technical note withtechnical note «only technical note technical note register technical note‌technical note»):
#   Cave instruction original technical note technical note technical note technical note‌technical note + RCX (technical note structure technical note technical note)
#   technical note «only technical note‌withtechnical note» — in firsttechnical note technical note instruction after from technical note (when slot still
#   technical note is) — in slot save technical note‌technical note and technical note never withtechnical noteandtechnical note technical note‌technical note:
#       cmp qword [slot], 0  /  jne skip  /  mov [slot], rax  /  skip:
#   technical note: withtechnical note technical note instruction technical note for structuretechnical note technical note technical note (technical note technical note
#   technical note technical note structuretechnical note technical noteandtechnical note) technical note technical note technical note‌technical note in version‌technical note before technical note technical note
#   slot technical note withtechnical noteandtechnical note technical note‌technical note and after from firsttechnical note technical note slot with technical note RCX technical note
#   broken technical note‌technical note → technical note technical note technical note register technical note‌technical note. technical noteandtechnical note counter‌technical note for
#   «technical note technical note‌technical note aftertechnical note technical note technical noteand team» always from same structure correct technical noteandtechnical note
#   technical note‌technical noteandtechnical note. Worker technical noteand byte counter technical note Poll technical note‌technical note:
#       Home = byte [rcx+0x158]   |   Away = byte [rcx+0x15C]
#   technical note «increment» counter = technical note technical note (technical note technical note instruction!). in technical note technical note technical note
#   counter jump technical note‌technical note technical notefortechnical note technical note never technical noteandwithtechnical note register technical note‌technical noteandtechnical note.
#
# hook second (optional and automatic): if 7 byte after from hook Home exactly
#   «mov [rcx+0000015C],r9d» withtechnical note (write countertechnical note Away technical notedistance after from
#   Home)technical note technical note instruction technical note hook technical note‌technical noteandtechnical note until RCX technical note before from firsttechnical note technical note Home
#   (technical note when Away firsttechnical note technical note technical note technical note‌technical note) capture technical note withtechnical note.
#
# technical note technical note (Adopt): if hook versiontechnical note 6 beforetechnical note in withtechnical note technical note withtechnical note to‌technical note
#   Error technical note technical note‌technical noteandtechnical note and slot technical note technical note‌technical noteandtechnical note until capture freshtechnical note technical note technical note
#   technical note technical noteandtechnical note (hook only in firsttechnical note technical note «technical note» technical note‌technical noteandtechnical note technical note‌technical note aftertechnical note
#   only from technical note technical noteandtechnical noteandtechnical note istechnical note technical note‌technical note).
# =====================================================================
class GoalHooker:
    HOOK_OFFSET = 0x19ECBE2
    ORIG_BYTES = b'\x44\x89\x89\x58\x01\x00\x00'            # mov [rcx+158h],r9d
    AWAY_EXPECTED_BYTES = b'\x44\x89\x89\x5C\x01\x00\x00'   # mov [rcx+15Ch],r9d
    HOME_COUNTER_OFFSET = 0x158
    AWAY_COUNTER_OFFSET = 0x15C      # exactly 4 byte technical noteandtechnical note (specification user)
    MAX_COUNTER_VALUE = 20           # technical note technical note technical noteandtechnical note byte counter
    MAX_GOAL_JUMP = 3                # technical note technical note for jump technical note in technical note Poll
    # --- version 6: technical note Cave with capture technical note‌withtechnical note ---
    CAVE_ALLOC_SIZE = 128            # technical note technical note Cave (code + slot)
    CODE_OFFSET = 0x20               # start code in Cave
    DATA_SLOT_OFFSET = 0x60          # slot 8 bytetechnical note RCX (after from codetechnical note 41 bytetechnical note)
    CAVE_CODE_SIZE = 41              # length technical note code technical noteandtechnical note (_build_capture_code)

    def __init__(self):
        self.cave_address = None
        self.data_home = None          # slot 8 bytetechnical note RCX (only firsttechnical note capture technical noteandtechnical note technical note‌technical noteandtechnical note — version 6)
        self.target_address = None
        # --- hook second (Away) ---
        self.away_installed = False
        self.away_target_address = None
        self.away_cave_address = None
        self.away_data = None
        self.is_hooked = False
        self.adopted = False           # version 6: technical note to technical note technical noteandtechnical noteandtechnical note (without technical note technical note)

    # -------------------------------------------------------------
    @staticmethod
    def counter_event(prev: Optional[int], new: Optional[int]) -> Tuple[str, int]:
        """
        text text from textandtext textand read textandtext counter (testable without withtext):
          prev=None , new=None → ("WAIT", 0)      still text capture text
          prev=None , new=v    → ("BASELINE", 0)  firsttext read valid
          new > prev           → ("GOAL", n)      n text new (text MAX_GOAL_JUMP)
          new < prev           → ("RESET", 0)     new match start / resync
          text                → ("NOCHANGE", 0)
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
        """text text Cave textand-TimeHooker textandtext target: text instruction original + capture text‌withtext RCX"""
        cave_address = allocate_near_target(h_process, target, self.CAVE_ALLOC_SIZE)
        if not cave_address:
            return None, None
        data_address = cave_address + self.DATA_SLOT_OFFSET   # slot 8 bytetechnical note RCX (after from code)
        code_start = cave_address + self.CODE_OFFSET

        # ---------- Cave (version 6 — Sticky First-Capture) ----------
        # mov [rcx+disp32], r9d        ; instruction original withtechnical note            (7)
        # push rax                     ;                             (1)
        # push rcx                     ;                             (1)
        # pushfq                       ;                             (1)
        # mov rax, rcx                 ;                             (3)
        # cmp qword [slot],0           ; slot technical note istechnical note               (8)
        # jne skip                     ; technical note → capture beforetechnical note technical note technical note  (2)
        # mov [slot], rax              ; technical note → only technical note‌withtechnical note capture   (10)
        # skip:
        # popfq                        ;                             (1)
        # pop rcx                      ;                             (1)
        # pop rax                      ;                             (1)
        # jmp rel32 → target+7         ;                             (5)
        # technical noteandtechnical note = 41 byte (CAVE_CODE_SIZE)
        code = self._build_capture_code(orig, data_address, target, code_start)

        # slot technical note → firsttechnical note technical note instruction after from technical note capture technical note‌technical noteandtechnical note
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
        version 6 — textandtext byte‌code Cave with capture «text‌withtext»:
        RCX only when in slot textandtext text‌textandtext text slot still text withtext
        (firsttext text instruction after from text). in text aftertext text jne
        path store text text text‌text → slot never with RCX text withtextandtext
        text‌textandtext → counter‌text text textand team until text text from structure correct
        textandtext text‌textandtext. (text and testable without withtext)
        """
        code = bytearray(orig)                                  # (7)
        code += bytes([0x50, 0x51, 0x9C])                       # push rax, push rcx, pushfq
        code += bytes([0x48, 0x89, 0xC8])                       # mov rax, rcx
        cmp_pos = len(code)                                     # 13
        code += bytes([0x48, 0x83, 0x3D, 0, 0, 0, 0, 0])        # cmp qword [rip+disp32], 0
        jne_pos = len(code)                                     # 21
        code += bytes([0x75, 0x00])                             # jne rel8 → skip
        code += bytes([0x48, 0xA3]) + struct.pack('<Q', slot)   # mov [slot], rax (only firsttechnical note‌withtechnical note)
        pop_pos = len(code)                                     # 33 → skip:
        code += bytes([0x9D, 0x59, 0x58])                       # popfq, pop rcx, pop rax
        code += bytes([0xE9])                                   # jmp rel32
        # rel32 ratio to technical note instruction jmp: technical note technical note + 4 byte rel32
        code += struct.pack('<i', (target + 7) - (code_start + len(code) + 4))
        # --- fixups ---
        # disp32 technical note rip-relative: from technical note instruction cmp agetechnical note technical note‌technical noteandtechnical note
        struct.pack_into('<i', code, cmp_pos + 3, slot - (code_start + cmp_pos + 8))
        # rel8 technical note jne technical noteandtechnical note instruction store technical note‌bytetechnical note
        code[jne_pos + 1] = (pop_pos - (jne_pos + 2)) & 0xFF
        if len(code) != GoalHooker.CAVE_CODE_SIZE:
            raise Exception(f"length code Cave invalid: {len(code)}")
        return bytes(code)

    # -------------------------------------------------------------
    @staticmethod
    def _parse_existing_cave_code(code: bytes, orig: bytes) -> Optional[int]:
        """
        version 6 — detection Cave «versiontext 6» text‌text from text beforetext and istext
        address slot from instruction mov [abs64], rax. if byte‌text textandtext versiontext 6
        textwithtext (text Cave legacy versiontext 4/5 text capture text text) None
        text‌text until text text with text textfrom textandtext (must withtext restart textandtext).
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

        # technical noteistechnical note‌technical note technical note instruction original before from technical noteandtechnical note write
        curr = safe_read(h_process, self.target_address, len(self.ORIG_BYTES))
        if curr is None:
            raise Exception("read memory Goal Hook possible text.")
        if curr == self.ORIG_BYTES:
            # --- technical note technical note: technical note fresh Cave (technical note withtechnical note «technical note technical note» hook) ---
            self.cave_address, self.data_home = self._install_cave(
                h_process, self.target_address, self.ORIG_BYTES)
            if not self.cave_address:
                raise Exception("Error in text memory for Goal Hook (Home).")
        elif curr[0] == 0xE9:
            # --- version 6: Adopt — hook versiontechnical note 6 beforetechnical note technical note technical note (technical note before
            # Restore technical note). to‌technical note Errortechnical note technical note technical noteandtechnical noteandtechnical note technical note technical note‌technical noteandtechnical note
            # slot technical note technical note technical note‌technical noteandtechnical note until capture freshtechnical note «technical note technical note» technical note technical noteandtechnical note
            # (technical noteuntiltechnical note «hook only in technical note firsttechnical note technical note» technical note technical note‌technical note).
            rel = struct.unpack('<i', curr[1:5])[0]
            code_start = self.target_address + 5 + rel
            existing = safe_read(h_process, code_start, self.CAVE_CODE_SIZE)
            slot = self._parse_existing_cave_code(existing, self.ORIG_BYTES) if existing else None
            if slot is None:
                raise Exception(
                    "Goal Hook legacy (versiontext 4/5) in withtext text is and text Adopt is nottext "
                    "for active‌text capture text‌withtext versiontext 6text withtext text text‌withtext restart text.")
            self.cave_address = code_start - self.CODE_OFFSET
            self.data_home = slot
            self.adopted = True
            safe_write(h_process, self.data_home, b'\x00' * 8)   # capture fresh technical note technical note
            clog(f"[GoalHook] text textandtextandtext Adopt text (slot={slot:#x}) — slot text text "
                  f"until firsttext textandtextuntiltext text text text capture textandtext")
        else:
            raise Exception(
                "text instruction text Home text text: " + curr.hex().upper() +
                " (text 0x19ECBE2 textortext to withtext text)"
            )

        # --- hook second (Away): only if technical note exactly 7 byte after withtechnical note ---
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
                # Adopt hook Awaytechnical note versiontechnical note 6 from technical note beforetechnical note
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
                    clog(f"[GoalHook] hook Away textandtextandtext Adopt text (slot={a_slot:#x})")
        except Exception:
            self.away_installed = False   # technical noteortechnical note — Poll from technical note slot Home technical note technical note‌technical note

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
        version 6 — text text slottext capture for «textfromtext capture text».
        only path «reset text / new match» text text text text text‌text until
        firsttext textandtextuntiltext text withtext newtext structure fresh text capture text.
        in textortext text text never textandtext text‌textandtext (capture only
        firsttext‌withtext after from text text text‌textandtext).
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
        read andtext hook + textand countertext text from structure text.
        output: {"hooked", "captured", "secondary", "rcx", "home", "away"}
        home/away or int (0..MAX_COUNTER_VALUE) or None text.
        """
        out = {"hooked": self.is_hooked, "captured": False, "secondary": self.away_installed,
               "rcx": None, "home": None, "away": None}
        if not self.is_hooked or not h_process:
            return out

        rcx = self._read_rcx_slot(h_process, self.data_home)
        if rcx is None:
            rcx = self._read_rcx_slot(h_process, self.away_data)
        if rcx is None:
            return out   # still technical note technical noteandtechnical noteuntiltechnical note technical note technical note

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
# 7technical note5 — technical noteandtechnical note technical note technical note layertechnical note Detection (version 10 — testable without withtechnical note)
# =====================================================================
GH_HEARTBEAT_INTERVAL = 5.0   # second — heartbeat [GoalHookPoll]


def gh_due_heartbeat(now: float, last: Optional[float],
                     interval: float = GH_HEARTBEAT_INTERVAL) -> bool:
    """textor andtext log heartbeat [GoalHookPoll] text (firsttext textandtext always text)"""
    if last is None:
        return True
    return (now - last) >= interval


def gh_pick_poll_time(total_t: Optional[float],
                      core_t: Optional[float]) -> float:
    """
    text match time for Poll text (version 10):
      totaltext text text moment if valid (> 0)text andtext latest time valid coretext
      andtext 0. Poll text textmust to‌text text textandtextuntiltext broken from text textandtext.
    """
    if total_t is not None and total_t > 0:
        return float(total_t)
    if core_t is not None and core_t > 0:
        return float(core_t)
    return 0.0


# =====================================================================
# 7technical note6 — version 10technical note3: Match Lifecycle State Machine (technical noteandtechnical note technical note — testable without withtechnical note)
# ---------------------------------------------------------------------
# cycletechnical note complete:  HALF_1 → (HT real) → HALF_2 → (end) → FULL_TIME
#             technical note technical note path: untiltechnical note ≈ technical note + PLAYING → NEW_MATCH (reset complete)
# technical note technical note: HT only when valid is technical note «first half andtechnical note technical note technical note withtechnical note»technical note
# technical note beforetechnical note time valid ≥ 45:00 technical note technical note withtechnical note. technical note «technical note time» never HT
# is not (technical note‌technical note technical note: 90:00→00:00technical note 03:00→02:59technical note 06:00→…) and minute 6 technical note
# withtechnical note technical notemust technical note technical note technical note HT technical noteandtechnical note technical note.
# =====================================================================
class MatchPhase(Enum):
    HALF_1 = "HALF_1"
    HALFTIME = "HALFTIME"      # decrease time after from first half technical note technical note — in technical note resume
    HALF_2 = "HALF_2"
    # --- versiontechnical note 10technical note15 — extra time (technical note technical noteandtechnical note reset usertechnical note technical note technical note and technical note) ---
    # ET1: reset untiltechnical note from withtechnical note 90:00 to 90:00 + Playing + untiltechnical note currently technical note
    # ET2: reset untiltechnical note from withtechnical note 105:00 to 105:00 + Playing + untiltechnical note currently technical note
    ET1 = "ET1"
    ET2 = "ET2"
    FULL_TIME = "FULL_TIME"    # technical note technical note technical note — chart technical note technical note‌technical noteandtechnical note (technical note technical note‌technical noteandtechnical note)
    NEW_MATCH = "NEW_MATCH"    # technical note — after from reset complete to HALF_1 technical note‌technical note


def should_flag_time_drop(prev_t: Optional[float], current_t: float,
                          min_delta: float) -> bool:
    """
    version 10text3 — textor decrease text time withtext must «text» textandtext
    only text text text text text text‌textandtext (text text text
    resume PLAYING with classify_resume_after_drop text text‌textandtext).
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
    version 10text3 — text deterministic text from resume PLAYING (after from text decrease text time).
    output: "HT" | "NEW_MATCH" | "ET1" | "ET2" | "KEPT"

    rule 1 — new match (textandtext‌text text text text text):
        current ≈ 0  →  NEW_MATCH
        (90:xx → 0:00 and 6:xx → 0:00 never HT is nottext new match possible is
         after from stop textandtext «text minute‌text» start textandtext)

    rule 2 — HT (rule text text inside Logic — text text textandtext):
        half == 1
        AND previous valid game time >= 45*60   (first half andtext text text)
        AND current textandtext 45:00 withtext:
             (ht_hard_min - lower_slack) <= current <= (ht_hard_min + tolerance)
        (45:xx/46:xx → 45:00 = start second half same withtext)

    rule 2-text — start extra time (versiontext 10text15 — text text text textandtext reset user):
        half == 2
        AND previous time above from 90:00 text text (andtext textintext text second)
        AND current textandtext 90:00 (drop untiltext textandtext 90:00):
             (90*60 - slack) <= current <= (90*60 + et_reset_tolerance)
        ⇒ ET1 (text first extra time)

    rule 2-text — start text second extra time (text text):
        half == 3
        AND previous time above from 105:00 text text (andtext textintext ET1)
        AND current textandtext 105:00  ⇒  ET2

    rule 3 — text text‌text (match end/text text/resync):
        KEPT → chart text text‌textandtext text HT and text resettext text text‌textandtext
        (6:00 text text text HT textandtext text‌text because prev_end < 2700 is)
    """
    # 1) new match — untiltechnical note ≈ technical note
    if current_t <= new_game_max_start:
        return "NEW_MATCH"
    # 2-technical note) start technical note second extra time — reset 105 from withtechnical note 105 (versiontechnical note 10technical note15)
    if (half_number == 3
            and prev_end_t > 105.0 * 60.0
            and (105.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 105.0 * 60.0 + et_reset_tolerance):
        return "ET2"
    # 2-technical note) start extra time — reset 90 from withtechnical note 90 (versiontechnical note 10technical note15)
    if (half_number == 2
            and prev_end_t > 90.0 * 60.0
            and (90.0 * 60.0 - ht_resume_lower_slack) <= current_t
            and current_t <= 90.0 * 60.0 + et_reset_tolerance):
        return "ET1"
    # 2) HT — rule technical note
    if (half_number == 1
            and prev_end_t >= ht_hard_min
            and (ht_hard_min - ht_resume_lower_slack) <= current_t
            and current_t <= ht_hard_min + ht_resume_tolerance):
        return "HT"
    # 3) technical note chart
    return "KEPT"


def is_new_match_watchdog(seen_max_t: float, current_t: float,
                          new_game_max_start: float,
                          min_delta: float) -> bool:
    """
    version 10text3 — Watchdog independent new match (without textortext to text decrease time).
    when in textortext PLAYING untiltext ≈ text is text text current andtext textand
    text (text from windowtext start + textuntil)text text text beforetext text and withtext
    new start text — text if to‌text text «decrease time» text textandtext withtext
    (text core in menutext from before to text to‌textandtext text withtext).
    """
    if current_t > new_game_max_start:
        return False
    return seen_max_t > (max(new_game_max_start, current_t) + min_delta)


# =====================================================================
# 7technical note7 — version 10technical note4: log detectiontechnical note file txt + technical note line technical noteandtechnical note data (Pipeline Health)
# ---------------------------------------------------------------------
# technical note: when after from start «withtechnical note second» only technical note‌technical note register technical note‌technical noteandtechnical note and pass/shot/technical note
# technical note technical note‌technical noteandtechnical note technical note section technical note technical note‌technical note exactly codetechnical note layertechnical note data technical note is.
#   * DebugLogger — file txt technical note technical note (thread-safetechnical note never exception
#     withtechnical note technical note‌technical note) with technical notein Sessiontechnical note technical noteandtechnical notedatatechnical note immediate and Heartbeat threshold‌technical note.
#   * technical noteandtechnical note technical note technical note (testable without withtechnical note): possession_rearm_neededtechnical note
#     freeze_secondstechnical note should_warn_frozen_countertechnical note fmt_ptr.
# technical noteandtechnical note read log (technical note fast):
#   HB st=... t=... poss=... nP=... pass=... shot=... | ptr ... | gates ...
#     - gates bp>0 in technical note line‌technical note  → technical note ball/players technical note technical note technical note‌technical note
#     - poss=- and cap=- technical note    → capture possession technical note (POSS_REARM technical note‌technical note)
#     - pass/shot technical note + pPtr/sPtr technical note technical note technical noteand withtechnical note → pointer frozen (STALEtechnical note)
#     - ghRcx technical note technical noteand withtechnical note technical note technical note → technical notewithtechnical note technical noteto‌technical note structure technical note in new match
# =====================================================================
DEBUG_LOG_FILENAME = "momentum_debug_log.txt"
DEBUG_LOG_HEARTBEAT_SEC = 5.0
DEBUG_LOG_MAX_BYTES = 4 * 1024 * 1024
POSS_REARM_STALE_SEC = 20.0      # possession invalidtechnical note technical note in technical noteortechnical note PLAYING → re-arm
POSS_REARM_THROTTLE_SEC = 60.0   # technical note distancetechnical note technical noteand re-arm automatic
COUNTER_FROZEN_WARN_SEC = 45.0   # countertechnical note pass/shot unchanged in technical noteortechnical note PLAYING → STALEtechnical note


class DebugLogger:
    """
    version 10text4 — log text text and textandtext for detection live‌textandtext layer‌text data.
      * append with textin Session (text text text text text new)
      * write/event always immediatetext heartbeat with thresholdtext timetext (throttle)
      * text text: textandtext from max_bytes → file to path+".1" text text‌textandtext
      * text‌andtext exception withtext text‌text (log textmust text text text)
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
        """textor andtext write Heartbeat text (threshold‌text textandtext lightweight text text)"""
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
    """address memory to hex for logtext None/text → '-' (testable without withtext)"""
    if not v:
        return "-"
    try:
        return f"{int(v):#x}"
    except Exception:
        return "-"


def freeze_seconds(last_change_wall: Optional[float], now_wall: float) -> float:
    """text second from latest «change valid» text (without text → -1)"""
    if last_change_wall is None:
        return -1.0
    try:
        return max(0.0, float(now_wall) - float(last_change_wall))
    except Exception:
        return -1.0


def possession_rearm_needed(poss_valid: bool, m_state: str, time_advancing: bool,
                            stale_sec: float, throttle_ok: bool) -> bool:
    """
    version 10text4 — text re-arm automatic capture possession (untiltext text):
      only when: possession invalid + withtext andtext in textortext is (PLAYING and text
      currently text text) + text invalidtext from threshold text + throttle withtext withtext.
      text textmemory‌text: text re-arm text in Pause/Replay/menu or with text text.
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
    version 10text4 — countertext pass/shot in textortext PLAYING text‌text unchanged text
    (in Pause/Replay text text is and textmust Warning text)
    """
    if m_state != "PLAYING":
        return False
    return freeze_sec >= warn_after


# =====================================================================
# 8. technical noteandtechnical noteandtechnical note istechnical note data‌technical note withtechnical note (GameEngine — version technical note technical note technical note file)
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
# 8. technical noteandtechnical noteandtechnical note istechnical note data‌technical note withtechnical note (GameEngine — version technical note technical note technical note file)
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
    # --- versiontechnical note 10technical note27 — red card (pointer 3 leveltechnical note — without hook) ---
    # chaintechnical note Cheat Engine user:
    #   address technical note: "FL_2026.exe"+036F3F88 / technical note first: 350 / technical note second: 4E0
    RED_CARD_PTR_OFFSET = 0x036F3F88
    RED_CARD_CHAIN = (0x350, 0x4E0)
    RED_CARD_COUNTER_MAX = 1000        # technical note technical note (address technical note → technical note)

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
        # version 4: hook register technical note from memory (fallback detection technical note path ball/inandfromtechnical note)
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
            return False, "The game is not running. Start the game first."
        else:
            for pname in ["FL_2026.exe", "PES2021.exe"]:
                self.pid = get_pid_by_name(pname)
                if self.pid:
                    proc_name = pname
                    break

            if not self.pid:
                return False, "The game is not running. Start the game first."

        self.h_process = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, self.pid)
        if not self.h_process:
            return False, "text text to textandtext textandtext is (Run as Admin)."

        self.base_addr = get_module_base(self.pid, proc_name)
        if not self.base_addr:
            return False, "textandtext withtext textdecrease text."

        base = int(self.base_addr)
        warnings = []

        # versiontechnical note 10technical note18 — technical note fresh = cycletechnical note capture possessiontechnical note fresh (andtechnical note
        # technical note beforetechnical note — address/technical noteand hook technical noteandtechnical note beforetechnical note — completetechnical note technical note technical note‌technical noteandtechnical note)
        self.poss_hooker = PossessionHooker()

        # --- hook possession (versiontechnical note 10technical note18 — specification technical note user): technical note «in momenttechnical note
        # technical note» technical note technical note‌technical noteandtechnical note! line technical note possession must until «momenttechnical note technical note untiltechnical note»
        # unchanged technical note in technical note moment cycletechnical note technical note address technical notefrom technical note‌technical noteandtechnical note (technical note hook
        # → firsttechnical note capturetechnical note technical note value 2 → technical note hook → read same address
        # until match end). for technical note andtechnical note withtechnical note firsttechnical note technical note PLAYING cycle
        # technical note technical notefrom technical note‌technical note (worker_loop → _possession_begin_capture_cycle).

        # --- ball hook ---
        # v2.0.6 — technical note new user: technical note/resettechnical note byte‌technical note only technical note ModBridge is.
        # first from HookBroker request technical note‌technical note technical note or hooktechnical note technical noteandtechnical noteandtechnical note technical note «shared»
        # to technical note technical note‌technical note (address buffertechnical note) or technical note‌withtechnical note hook technical note‌technical note. technical noteandtechnical note technical note technical noteandtechnical note technical note
        # technical note bytetechnical note hooktechnical note technical note‌technical noteandtechnical note until when technical note in technical note technical notewithtechnical note (technical note technical note).
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
                    # technical noteand unknown is — with hook technical noteandtechnical note fallback technical note‌technical noteandtechnical note (technical notetotal technical note
                    # technical note is and byte‌technical note original in technical noteand technical note technical note‌technical noteandtechnical note — technical note)
                    if not self._install_ball_hook(base):
                        self._partial_cleanup()
                        return False, "Error in text ball hook."
            else:
                if not self._install_ball_hook(base):
                    self._partial_cleanup()
                    return False, "Error in text ball hook."

        # --- hook new match time (TimeHooker) ---
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
                # technical note technical note -> Errortechnical note andtechnical note technical note technical note‌technical noteandtechnical note and to time fallback (MATCH_TIME_OFFSET) drop technical note‌technical note
                warnings.append(f"Time Hook: {e} (from time fallback istext text‌textandtext)")

        # --- hook register technical note (GoalHooker — version 4) ---
        # technical noteortechnical note: if technical note technical note technical note only Warning data technical note‌technical noteandtechnical note in technical note technical note
        # technical note path fallbacktechnical note for register technical note andtechnical noteandtechnical note technical note (path technical note technical note technical note is)
        try:
            self.goal_hooker.hook(self.h_process, self.base_addr)
        except Exception as e:
            warnings.append(f"Goal Hook: {e} (register text disabled)")

        self.is_ready = True
        msg = "text and hook‌text text text."
        if warnings:
            msg += " | Warning: " + " | ".join(warnings)
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
        """v2.0.1 — text ball hook: from textandtext firsttext instruction textand textandtextandtext address buffer
        data‌text text XMM0 textuntiltext in text textandtext text‌textandtext text text‌textandtext:
          textand ModBridge : 0F 11 05 rel32 (movups [buf], xmm0) → buf = cave+7+rel32
          textand momentum : textand with byte‌text original movaps start text‌textandtext → data = cave+64
        output 0 = text unknown."""
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
        """v2.0.5 — text lightweighttext textandtext‌text live‌textandtext linetext datatext ball (2 second text‌withtext):
        user text «hook still andtext istext chart empty text». text realtext
        «charttext empty/frozen» in text: hooktext sharedtext text ball textandtext tool
        text (restore textandtext GLT / crash-recovery recoverytext mem_backup)
        withtextandtext text‌textandtext text text andtext text text and in textandtext textortext text text‌text.
        v2.0.6 — when hook from text (HookBroker) text text byte‌text text text
        text is nottext only from text text andtext text text text‌text and in textandtext textortext
        «request» text text text‌text (text/text/withtext text text text is).
        output text from:
          ok / re-adopt / reinstall / unknown-cave / install-fail /
          signature-mismatch / read-fail   (path text)
          ok / re-adopt(bridge) / reinstalled(bridge) / install-fail(bridge)
          / bridge-lost                    (path text)
        text: readtext 7 bytetext textandtext text ~2 second — text."""
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
        """v2.0.1 — True only when E9 text text ball to textand textandtext text text
        text‌text in text text and only in text text textfromtext restore byte‌text original
        text text (hook text text never broken text‌textandtext).
        v2.0.6 — when hook from text text text byte‌text never text text is nottext."""
        try:
            if getattr(self, "ball_hook_via_bridge", False):
                return False          # bytes belong to the bridge — never ours
            if not (self.ball_hook_addr and self.h_process
                    and self.ball_cave_addr):
                return False
            curr = safe_read(self.h_process, self.ball_hook_addr, 7)
            if not curr or curr[0] != 0xE9:
                return False          # technical note from before original is — technical note is not
            if self.ball_hook_adopted:
                return False          # technical noteand technical note technical note is not (technical note‌technical note)
            rel = struct.unpack('<i', bytes(curr[1:5]))[0]
            return (self.ball_hook_addr + 5 + rel) == self.ball_cave_addr
        except Exception:
            return False

    def _install_ball_hook(self, base: int) -> bool:
        """
        versiontext 10text7 — text ball hook (istext‌text from initializetext textuntiltext text before).
        in initialize and in verify_and_repair_hooks (textandtextfromtext start text new)
        istext text‌textandtext. True = text successful. (v2.0.1 — text adopted always reset
        text‌textandtext because from text moment textand text textandtext textis.)
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
        versiontext 10text7 — text lightweight textortext textandtext: read 1 bytetext from text andtext.
        None ⇒ textandtext text/text text is (for text text automatic).
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
        versiontext 10text7 — textandtextfromtext fast hook‌text in start text new (textortext text user:
        «hook‌text text‌text text in text from second text and again hook text»).
        for text 4 hook: text byte text textistext‌text text‌textandtext if withtext restore
        text textandtext again text text‌textandtext if text text text istext text text‌textandtext.
        in text capture text and possession re-arm text‌textandtext until firsttext textandtextuntiltext withtext
        new structure fresh text capture text.
        output: text andtext text hook (for log).
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

        # --- ball: technical note E9 = hook livetechnical note technical noteandtechnical note or technical note (technical note technical noteand + technical note
        # buffer — v2.0.1) | ORIG = technical note technical note ---
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
                        # possession: only when technical noteand same technical noteand technical note‌technical note technical noteandtechnical note is and
                        # beforetechnical note technical note‌technical note hook «technical note technical note» technical noteandtechnical note technical note‌technical noteandtechnical note
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

        # --- time: ORIG ⇒ technical note technical note | E9 ⇒ technical note technical note (technical noteandtechnical note) ---
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

        # --- technical note: hook() technical noteandtechnical note technical note‌technical note/Adopt technical note technical note technical note‌technical note + slot technical note technical note‌technical noteandtechnical note ---
        try:
            self.goal_hooker.hook(self.h_process, self.base_addr)
            rep["goal"] = "ok" if self.goal_hooker.is_hooked else "inactive"
        except Exception as ex:
            rep["goal"] = f"error:{type(ex).__name__}"

        # --- possession (versiontechnical note 10technical note18 — technical note «technical note address»): if address valid technical note
        # technical note beforetechnical note confirmation technical note technical note technical note‌technical noteandtechnical note andtechnical note hook technical note + technical note empty
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

        # --- re-arm capture technical note (firsttechnical note technical noteandtechnical noteuntiltechnical note technical note technical note new again capture technical note) ---
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
        """cleanup init text in textandtext Error"""
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
            # v2.0.1 — restore only when technical notefrom is technical note E9 technical note technical note to technical noteand technical noteandtechnical note
            # technical note technical note technical note hook technical note technical note (ModBridge) never broken technical note‌technical noteandtechnical note
            # v2.0.6 — hooktechnical note technical note: only technical note‌technical note technical note technical note technical note‌technical note (hook_release)technical note
            # technical note withtechnical note byte‌technical note completetechnical note with technical note is
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
        text textwithtext layer receive:
        Raw Engine: Float0 = lengthtext, Float1 = height, Float2 = widthtext
        Standard App: X = lengthtext, Z = widthtext, Y = height
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
        """time fallback (Fallback) — only when Time Hook in text textwithtext"""
        raw = safe_read(self.h_process, int(self.base_addr) + self.MATCH_TIME_OFFSET, 4)
        if raw:
            return max(0.0, struct.unpack('<f', raw)[0])
        return 0.0

    def read_game_clock(self) -> Tuple[float, Optional[int], Optional[int]]:
        """
        source andtext match time:
        1) TimeHooker (RSI+0x13C minute / RSI+0x140 second)  — source original
        2) MATCH_TIME_OFFSET (float)                        — only Fallback
        output: (total_match_seconds, game_minutes, game_seconds)
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
        versiontext 10text27 — countertext red card (without hook — pointer 3 leveltext 64 text):
            curr  = u64[base + 0x036F3F88]
            curr  = u64[curr + 0x350]
            value = u8 [curr + 0x4E0]
        text «increment» value 1 bytetext = text red card textintext (text versiontext 2017).
        text text: value > RED_CARD_COUNTER_MAX or pointer text → None.
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
        """version 4 — andtext goal hook + counter‌text text (Home/Away) from memory"""
        try:
            return self.goal_hooker.poll(self.h_process)
        except Exception:
            return {"hooked": False, "captured": False, "secondary": False,
                    "rcx": None, "home": None, "away": None}

    def reset_possession_capture(self):
        """
        version 10text4 — re-arm text Capture possession for «new match».
        same textandtext self-heal goal hook: withtext in withtext new structure text text
        textto‌text text‌text capture legacy address text text text‌textandtext. after from text
        textandtext firsttext text instruction possession in withtext new address fresh text
        Capture text‌text.
        versiontext 10text18 — without hooktext text‌text capture never text text‌text text if
        hook currently text text is not (text‌text after from confirmation)text cycletext text
        again textfrom text‌textandtext (text hook + text empty).
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
        """versiontext 10text18 — re-arm smart for «start text new»:
        if address possession «text text second past» confirmation text withtext (after from
        momenttext text untiltext)text to structure text withtext text text and textmust text textandtext
        (andtext text second first withtext without possession = chart empty in text text).
        capture legacy/text → text + cycletext text again."""
        ph = self.poss_hooker
        w = getattr(ph, "captured_wall", None)
        if (w is not None and not ph.is_hooked
                and (time.time() - w) <= keep_recent_sec):
            return        # capture freshtechnical note technical note technical note — technical note technical noteandtechnical note
        self.reset_possession_capture()

    def poss_begin_capture_cycle(self) -> str:
        """versiontext 10text18 — textfrom cycletext «text address» possession (specification user):
        text hook + empty‌text text. in momenttext text untiltext (new match start) and
        in firsttext text PLAYING after from text andtext withtext textandtext text‌textandtext.
        output: text textanduntiltext for log."""
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
        version 10text4 — read RAW layertext data for log detectiontext (without impact text).
        text address‌text int text (log with fmt_ptr to hex text‌textandtext). text: text
        address‌text text «withtext first» and «withtext second» for textwithtext textto‌text structuretext.
          pass_ptr  → qword [base+PASS_COUNT_OFFSET]   (counter: byte[ptr+0xD0])
          shot_ptr  → qword [base+SHOT_COUNT_PTR_OFFSET] (counter: [ptr+0x3C])
          seat0/seat1 → textand pointer first text players
          state_raw → byte text andtext text
          poss_cap  → address capture text possession (rdi+0x58)
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
            # --- pass ---
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
            # --- shot ---
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
            # --- technical note players (technical noteand technical note first) ---
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
            # --- andtechnical note technical note (byte technical note) ---
            raw = safe_read(self.h_process, base + self.MATCH_STATE_OFFSET, 1)
            if raw:
                out["state_raw"] = struct.unpack('<B', raw)[0]
            # --- address capture possession ---
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
                x = struct.unpack('<f', raw_coords[0:4])[0]   # lengthtechnical note
                z = struct.unpack('<f', raw_coords[8:12])[0]  # widthtechnical note
                players.append({
                    "seat": i + 1,
                    "team": "Home" if i < 11 else "Away",
                    "x": x * ShotConfig.WORLD_TO_METER_SCALE,
                    "z": z * ShotConfig.WORLD_TO_METER_SCALE
                })
        return players

    def cleanup(self):
        """Restore complete text hook‌text (Ball / Possession / Time / Goal)
        (v2.0.1 — ball hook only if text textandtext withtext restore text‌textandtext)
        (v2.0.6 — hooktext text: text bytetext textandtext text‌textandtext only hook_release)"""
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
# 9. technical notewithtechnical note technical note technical note (GeometryEngine — technical note technical note technical note file)
# =====================================================================
