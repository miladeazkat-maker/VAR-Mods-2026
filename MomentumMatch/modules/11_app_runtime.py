    def _graph_loop(self):
        if not self.is_monitoring or getattr(self, "_closing", False):
            return
        # نسخهٔ ۱۰٫۱۲ — رندر زندهٔ تب TV (وقتی تب دیده می‌شود؛ فقط با تغییر وضعیت)
        try:
            self._refresh_tv_chart()
        except Exception as ex:
            clog(f"[TVGraph] {ex}")
        # نسخه ۲: Live Update زنجیره‌های مالکیت (همان Row آپدیت می‌شود)
        try:
            self.update_ui_sequences(list(self.event_engine.sequences))
        except Exception as ex:
            clog(f"[Seq] {ex}")
        try:
            self.after(self.GRAPH_REFRESH_MS, self._graph_loop)
        except Exception:
            pass


    def build_events_tab(self, parent):
        cols = ("id", "time", "team", "type", "rel", "conf", "raw", "impact", "pos", "related", "tags")
        self.tree_ev = ttk.Treeview(parent, columns=cols, show="headings", height=16)

        heads = {"id": "#", "time": "زمان", "team": "تیم", "type": "نوع رخداد", "rel": "اعتبار",
                 "conf": "اطمینان", "raw": "Raw Score", "impact": "Momentum Impact",
                 "pos": "مختصات (X, Z)", "related": "وابسته به ID", "tags": "جزئیات و مشخصات"}
        widths = {"id": 40, "time": 58, "team": 68, "type": 190, "rel": 82, "conf": 60,
                  "raw": 78, "impact": 95, "pos": 100, "related": 80, "tags": 330}
        anchors = {"type": "w", "tags": "w"}
        for c in cols:
            self.tree_ev.heading(c, text=heads[c])
            self.tree_ev.column(c, width=widths[c], anchor=anchors.get(c, "center"))

        self.tree_ev.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_ev.yview)
        sb.pack(side="right", fill="y")
        self.tree_ev.configure(yscrollcommand=sb.set)
        self.tree_ev.bind("<Double-1>", self.on_event_double_click)


    def update_ui_events(self, events: List[GameEvent]):
        for ev in events:
            t_str = "میزبان" if ev.team == "Home" else "میهمان"
            m, s = divmod(int(ev.match_time), 60)
            p_str = f"{ev.position[0]:.1f}, {ev.position[1]:.1f}"
            r_str = ", ".join(map(str, ev.related_event_ids)) if ev.related_event_ids else "--"

            imp = self.momentum.get_impact(ev.event_id)
            raw_s = f"{imp.raw_threat:.0f}" if imp else "--"
            imp_s = f"{imp.final_impact:+.1f}" if imp else "--"

            self.tree_ev.insert("", 0, values=(
                ev.event_id, f"{m:02d}:{s:02d}", t_str, ev.event_type,
                ev.reliability.value, f"{int(ev.confidence * 100)}%",
                raw_s, imp_s, p_str, r_str, ", ".join(ev.tags)
            ))


    def on_event_double_click(self, _event):
        item = self.tree_ev.focus()
        if not item:
            return
        vals = self.tree_ev.item(item, "values")
        try:
            ev_id = int(vals[0])
        except (ValueError, IndexError):
            return
        ev = self.event_engine.get_event(ev_id)
        if not ev:
            return
        imp = self.momentum.get_impact(ev_id)
        core = self.runtime.get_core()
        cur_t = core["current_match_time"]

        m, s = divmod(int(ev.match_time), 60)
        lines = [
            f"نوع رخداد: {ev.event_type}",
            f"تیم: {'میزبان' if ev.team == 'Home' else 'میهمان'}",
            f"زمان مسابقه: {m:02d}:{s:02d}",
            f"Reliability: {ev.reliability.value}",
            f"Confidence: {int(ev.confidence * 100)}%",
        ]
        if imp:
            # نسخه ۲: برای Goal Pulse از منحنی پاسخ گل استفاده می‌شود (نه decay ساده)
            if imp.is_goal_pulse:
                f = self.momentum.goal_response_factor(imp, cur_t)
                phase = self.momentum.goal_pulse_phase(imp, cur_t)
                gm, gs = divmod(int(imp.goal_time), 60)
                pm, ps = divmod(int(imp.peak_time), 60)
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Goal Pulse: {phase} | factor فعلی: {f:.3f}",
                    f"Goal Time: {gm:02d}:{gs:02d} → Peak Time: {pm:02d}:{ps:02d}",
                    f"Contribution لحظه‌ای: {imp.final_impact * f:+.2f}",
                ]
            else:
                decay = self.momentum.decay_factor(max(0.0, cur_t - imp.match_time))
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Decay فعلی: {decay:.3f}",
                    f"Contribution لحظه‌ای: {imp.final_impact * decay:+.2f}",
                ]
            if imp.note:
                lines.append(f"سیاست امتیاز: {imp.note}")
        else:
            lines.append("Momentum Impact: -- (بدون امتیاز)")
        if ev.related_event_ids:
            lines.append(f"رویدادهای وابسته: {', '.join(map(str, ev.related_event_ids))}")
        if ev.metadata:
            md_str = ", ".join(f"{k}={v}" for k, v in ev.metadata.items())
            lines.append(f"متادیتا: {md_str}")
        lines.append(f"تگ‌ها: {', '.join(ev.tags)}")
        messagebox.showinfo(f"جزئیات رخداد #{ev.event_id}", "\n".join(lines))


    def build_sequences_tab(self, parent):
        seq_cols = ("id", "team", "dur", "prog", "passes", "shots", "chances", "f3rd", "box", "status")
        self.tree_seq = ttk.Treeview(parent, columns=seq_cols, show="headings", height=16)
        heads = {"id": "Seq #", "team": "تیم", "dur": "مدت (s)", "prog": "پیشروی (m)",
                 "passes": "تعداد پاس", "shots": "تعداد شوت", "chances": "فرصت",
                 "f3rd": "ورود به یک‌سوم", "box": "ورود به محوطه", "status": "وضعیت"}
        widths = {"id": 55, "team": 70, "dur": 75, "prog": 85, "passes": 85, "shots": 85,
                  "chances": 65, "f3rd": 105, "box": 105, "status": 170}
        for c in seq_cols:
            self.tree_seq.heading(c, text=heads[c])
            self.tree_seq.column(c, width=widths[c], anchor="center")
        # رنگ سبز برای زنجیره‌های فعال (Live)
        self.tree_seq.tag_configure("active", foreground="#00f5d4")
        self.tree_seq.tag_configure("ended", foreground="#c8d3e0")
        self.tree_seq.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_seq.yview)
        sb.pack(side="right", fill="y")
        self.tree_seq.configure(yscrollcommand=sb.set)


    def update_ui_sequences(self, seqs: List[PossessionSequence]):
        """
        نسخه ۲ — Live Update واقعی:
        هر Sequence فقط یک بار Row می‌گیرد (insert) و تا پایان بازی «همان Row»
        با tree.item(values=...) به‌روزرسانی می‌شود؛ هیچ ردیف تکراری ساخته
        نمی‌شود. زنجیرهٔ فعال سبز نمایش داده می‌شود و پس از بستن، مقادیر نهایی
        (duration / ending_reason) در همان Row ثبت می‌ماند.
        """
        for s in seqs:
            t_str = "میزبان" if s.team == "Home" else "میهمان"
            if s.is_active:
                status = "فعال ⏳"
                tag = "active"
            else:
                status = s.ending_reason or "پایان"
                tag = "ended"
            vals = (
                s.seq_id, t_str, f"{s.duration:.1f}s", f"{s.territorial_gain:+.1f}m",
                s.pass_count, s.shot_count, s.chances_created,
                s.final_third_entries, s.box_entries, status
            )
            item = self._seq_row_items.get(s.seq_id)
            if item is None:
                item = self.tree_seq.insert("", 0, values=vals, tags=(tag,))
                self._seq_row_items[s.seq_id] = item
            else:
                if self._seq_last_values.get(s.seq_id) != vals:
                    self.tree_seq.item(item, values=vals, tags=(tag,))
            self._seq_last_values[s.seq_id] = vals


    def build_details_tab(self, parent):
        wrap = tk.Frame(parent, bg="#090c12")
        wrap.pack(fill="both", expand=True)

        # --- کارت آخرین پاس ---
        card_pass = tk.LabelFrame(wrap, text="  آنالیز دقیق آخرین پاس  ",
                                  font=("Segoe UI", 10, "bold"), fg="#00f5d4", bg="#111722", padx=10, pady=5)
        card_pass.pack(fill="x", padx=10, pady=(8, 3))

        r1 = tk.Frame(card_pass, bg="#111722")
        r1.pack(fill="x")
        self.lbl_card_title = tk.Label(r1, text="نوع پاس: در انتظار شروع بازی...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#111722")
        self.lbl_card_title.pack(side="left")
        self.lbl_card_threat = tk.Label(r1, text="Threat Score: --", font=("Segoe UI", 12, "bold"), fg="#ff70a6", bg="#111722")
        self.lbl_card_threat.pack(side="right", padx=10)
        self.lbl_card_outcome = tk.Label(r1, text="", font=("Segoe UI", 11, "bold"), bg="#111722")
        self.lbl_card_outcome.pack(side="right")

        r2 = tk.Frame(card_pass, bg="#182030", padx=8, pady=4)
        r2.pack(fill="x", pady=3)
        self.lbl_players = tk.Label(r2, text="فرستنده: -- ➔ گیرنده: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#182030")
        self.lbl_players.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_flight_time = tk.Label(r2, text="زمان پاس: -- ثانیه", font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#182030")
        self.lbl_flight_time.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_confidence = tk.Label(r2, text="ضریب اطمینان: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#182030")
        self.lbl_confidence.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_tags = tk.Label(r2, text="ویژگی‌ها: --", font=("Segoe UI", 9), fg="#f4a261", bg="#182030")
        self.lbl_tags.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_metrics = tk.Label(r2, text="طول: -- | پیشروی طولی X: -- | پیشروی عرضی Z: -- | اوج ارتفاع Y: --",
                                    font=("Segoe UI", 8), fg="#94a3b8", bg="#182030")
        self.lbl_metrics.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- کارت آخرین شوت ---
        card_shot = tk.LabelFrame(wrap, text="  آنالیز تفکیک‌شده آخرین شوت  ",
                                  font=("Segoe UI", 10, "bold"), fg="#ff3366", bg="#0f1422", padx=10, pady=5)
        card_shot.pack(fill="x", padx=10, pady=3)

        s1 = tk.Frame(card_shot, bg="#0f1422")
        s1.pack(fill="x")
        self.lbl_shot_title = tk.Label(s1, text="نوع شوت: در انتظار ثبت نخستین شوت...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#0f1422")
        self.lbl_shot_title.pack(side="left")
        self.lbl_shot_threats = tk.Label(s1, text="Pre Threat: -- | Final Threat: --", font=("Segoe UI", 12, "bold"), fg="#ff0055", bg="#0f1422")
        self.lbl_shot_threats.pack(side="right", padx=10)
        self.lbl_shot_outcome = tk.Label(s1, text="نتیجه: --", font=("Segoe UI", 11, "bold"), fg="#00f5d4", bg="#0f1422")
        self.lbl_shot_outcome.pack(side="right", padx=15)

        s2 = tk.Frame(card_shot, bg="#172033", padx=8, pady=4)
        s2.pack(fill="x", pady=3)
        self.lbl_shooter = tk.Label(s2, text="زننده: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#172033")
        self.lbl_shooter.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_speed = tk.Label(s2, text="حداکثر سرعت توپ: -- km/h", font=("Segoe UI", 9, "bold"), fg="#f72585", bg="#172033")
        self.lbl_speed.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_ontarget = tk.Label(s2, text="وضعیت چارچوب: --", font=("Segoe UI", 9, "bold"), fg="#4cc9f0", bg="#172033")
        self.lbl_ontarget.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_shot_conf = tk.Label(s2, text="اطمینان: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#172033")
        self.lbl_shot_conf.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_shot_geom = tk.Label(s2, text="فاصله شوت: -- | زاویه دید: -- | فاصله با تیرک: -- | اوج ارتفاع: --",
                                      font=("Segoe UI", 8), fg="#94a3b8", bg="#172033")
        self.lbl_shot_geom.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- جداول تاریخچه پاس و شوت ---
        tables = tk.Frame(wrap, bg="#090c12")
        tables.pack(fill="both", expand=True, padx=10, pady=6)

        left = tk.LabelFrame(tables, text="  📋 تاریخچه پاس‌ها (دابل‌کلیک = جزئیات)  ",
                             font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#090c12")
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        pcols = ("id", "time", "team", "type", "threat", "conf", "passer", "receiver", "dist", "status")
        self.tree_pass = ttk.Treeview(left, columns=pcols, show="headings", height=9)
        pheads = {"id": "#", "time": "زمان", "team": "تیم", "type": "نوع پاس", "threat": "Threat",
                  "conf": "اطمینان", "passer": "فرستنده", "receiver": "گیرنده", "dist": "طول (m)", "status": "نتیجه"}
        for c in pcols:
            self.tree_pass.heading(c, text=pheads[c])
            self.tree_pass.column(c, width=78, anchor="center" if c != "type" else "w")
        self.tree_pass.pack(side="left", fill="both", expand=True)
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.tree_pass.yview)
        sb1.pack(side="right", fill="y")
        self.tree_pass.configure(yscrollcommand=sb1.set)
        self.tree_pass.bind("<Double-1>", self.on_pass_double_click)

        right = tk.LabelFrame(tables, text="  🎯 تاریخچه شوت‌ها (دابل‌کلیک = جزئیات)  ",
                              font=("Segoe UI", 9, "bold"), fg="#ff3366", bg="#090c12")
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        scols = ("id", "time", "team", "type", "pre", "final", "outcome", "speed", "dist", "conf")
        self.tree_shot = ttk.Treeview(right, columns=scols, show="headings", height=9)
        sheads = {"id": "#", "time": "زمان", "team": "تیم", "type": "نوع شوت", "pre": "Pre Thr",
                  "final": "Final Thr", "outcome": "نتیجه", "speed": "سرعت", "dist": "فاصله", "conf": "اطمینان"}
        for c in scols:
            self.tree_shot.heading(c, text=sheads[c])
            self.tree_shot.column(c, width=78, anchor="center" if c not in ("type", "outcome") else "w")
        self.tree_shot.pack(side="left", fill="both", expand=True)
        sb2 = ttk.Scrollbar(right, orient="vertical", command=self.tree_shot.yview)
        sb2.pack(side="right", fill="y")
        self.tree_shot.configure(yscrollcommand=sb2.set)
        self.tree_shot.bind("<Double-1>", self.on_shot_double_click)


    def update_pass_card(self, ev: PassEventData):
        self.runtime.set_pass(ev)
        self._ui_pass_list.append(ev)
        team_str = "میزبان" if ev.team == "Home" else "میهمان"
        out_txt = "موفق ✅" if ev.is_success else "ناموفق / قطع ❌"
        out_col = "#2ecc71" if ev.is_success else "#e63946"

        self.lbl_card_title.config(text=f"نوع پاس: {ev.pass_type} ({team_str})")
        self.lbl_card_threat.config(text=f"Threat Score: {ev.threat_score}/100")
        self.lbl_card_outcome.config(text=out_txt, fg=out_col)

        p_str = f"صندلی {ev.passer_seat}" if ev.passer_seat else "نامشخص"
        r_str = f"صندلی {ev.receiver_seat}" if ev.receiver_seat else "نامشخص"
        self.lbl_players.config(text=f"فرستنده: {p_str} ➔ گیرنده: {r_str}")
        self.lbl_flight_time.config(text=f"زمان پرواز توپ: {ev.flight_time:.2f} ثانیه")
        self.lbl_confidence.config(text=f"ضریب اطمینان: {int(ev.confidence * 100)}%")
        self.lbl_tags.config(text=f"ویژگی‌ها: {', '.join(ev.tags) if ev.tags else 'عادی'}")
        self.lbl_metrics.config(
            text=(f"طول: {ev.distance:.1f}m | پیشروی طولی X: {ev.forward_progress:+.1f}m | "
                  f"پیشروی عرضی Z: {ev.lateral_progress:.1f}m | اوج ارتفاع Y: {ev.max_height:.2f}m")
        )

        m, s = divmod(int(ev.match_time), 60)
        self.tree_pass.insert("", 0, values=(
            ev.event_id, f"{m:02d}:{s:02d}", team_str, ev.pass_type,
            f"{ev.threat_score}", f"{int(ev.confidence * 100)}%",
            p_str, r_str, f"{ev.distance:.1f}",
            "موفق" if ev.is_success else "ناموفق"
        ))


    def update_shot_card(self, ev: ShotEventData):
        self.runtime.set_shot(ev)
        self._ui_shot_list.append(ev)
        team_str = "میزبان" if ev.team == "Home" else "میهمان"

        self.lbl_shot_title.config(text=f"نوع شوت: {ev.primary_type} ({team_str})")
        self.lbl_shot_threats.config(text=f"Pre Thr: {ev.pre_shot_threat} | Final Thr: {ev.final_threat}")

        outcome_color = "#00f5d4"
        if "گل" in ev.outcome: outcome_color = "#2ecc71"
        elif "تیرک" in ev.outcome: outcome_color = "#fca311"
        elif "خارج" in ev.outcome: outcome_color = "#e63946"
        self.lbl_shot_outcome.config(text=f"نتیجه: {ev.outcome}", fg=outcome_color)
        self.lbl_shooter.config(text=f"زننده: صندلی {ev.shooter_seat} ({team_str})")

        sp_txt = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "-- (غیرقابل محاسبه)"
        self.lbl_speed.config(text=f"حداکثر سرعت توپ: {sp_txt}")
        self.lbl_ontarget.config(
            text=f"وضعیت: {'در چارچوب ✅' if ev.is_on_target else 'خارج چارچوب ❌'}",
            fg="#2ecc71" if ev.is_on_target else "#e63946"
        )
        self.lbl_shot_conf.config(text=f"اطمینان: {int(ev.confidence * 100)}%")
        sign_desc = "داخل" if ev.woodwork_distance < 0 else "خارج"
        self.lbl_shot_geom.config(
            text=(f"فاصله: {ev.distance_to_goal:.1f}m | زاویه: {ev.goal_angle_deg:.1f}° | "
                  f"تیرک: {ev.woodwork_distance:+.2f}m ({sign_desc}) | اوج ارتفاع: {ev.max_height:.2f}m | "
                  f"مدافعان دالان: {ev.defenders_in_corridor}")
        )

        m, s = divmod(int(ev.match_time), 60)
        self.tree_shot.insert("", 0, values=(
            ev.event_id, f"{m:02d}:{s:02d}", team_str, ev.primary_type,
            f"{ev.pre_shot_threat}", f"{ev.final_threat}", ev.outcome,
            sp_txt, f"{ev.distance_to_goal:.1f}m", f"{int(ev.confidence * 100)}%"
        ))


    def on_pass_double_click(self, _event):
        item = self.tree_pass.focus()
        if not item: return
        try:
            pid = int(self.tree_pass.item(item, "values")[0])
        except (ValueError, IndexError):
            return
        ev = next((p for p in self._ui_pass_list if p.event_id == pid), None)
        if not ev: return
        m, s = divmod(int(ev.match_time), 60)
        msg = (
            f"پاس شماره: {ev.event_id}\n"
            f"زمان مسابقه: {m:02d}:{s:02d}\n"
            f"مدت پرواز توپ: {ev.flight_time:.2f} ثانیه\n"
            f"تیم: {ev.team}\n"
            f"فرستنده: صندلی {ev.passer_seat} ➔ گیرنده: صندلی {ev.receiver_seat}\n\n"
            f"نوع پاس: {ev.pass_type}\n"
            f"شاخص تهدید (Threat): {ev.threat_score}/100\n"
            f"ضریب اطمینان: {int(ev.confidence * 100)}%\n\n"
            f"مسافت پاس: {ev.distance:.1f} m\n"
            f"پیشروی طولی X: {ev.forward_progress:+.1f} m\n"
            f"جابه‌جایی عرضی Z: {ev.lateral_progress:.1f} m\n"
            f"اوج ارتفاع Y: {ev.max_height:.2f} m\n"
            f"نتیجه پاس: {'موفق ✅' if ev.is_success else 'قطع شده / ناموفق ❌'}\n\n"
            f"مبدا پاس: ({ev.start_ball[0]:.1f}, {ev.start_ball[1]:.1f}) ➔ مقصد: ({ev.end_ball[0]:.1f}, {ev.end_ball[1]:.1f})"
        )
        messagebox.showinfo(f"مشخصات کامل پاس #{ev.event_id}", msg)


    def on_shot_double_click(self, _event):
        item = self.tree_shot.focus()
        if not item: return
        try:
            sid = int(self.tree_shot.item(item, "values")[0])
        except (ValueError, IndexError):
            return
        ev = next((x for x in self._ui_shot_list if x.event_id == sid), None)
        if not ev: return
        m, s = divmod(int(ev.match_time), 60)
        sign_str = "داخل چارچوب" if ev.woodwork_distance < 0 else "خارج چارچوب"
        sp_str = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "نامشخص / غیرقابل محاسبه"
        msg = (
            f"🎯 شوت شماره: {ev.event_id}\n"
            f"زمان مسابقه: {m:02d}:{s:02d}\n"
            f"تیم: {ev.team} (صندلی {ev.shooter_seat})\n"
            f"نوع شوت: {ev.primary_type}\n"
            f"ویژگی‌ها: {', '.join(ev.tags)}\n\n"
            f"🚀 سرعت ضربه: {sp_str}\n"
            f"🎯 چارچوب: {'در چارچوب ✅' if ev.is_on_target else 'خارج از چارچوب ❌'}\n"
            f"📏 فاصله با تیرک: {ev.woodwork_distance:+.2f}m ({sign_str})\n"
            f"📊 نتیجه نهایی: {ev.outcome}\n\n"
            f"🔥 Pre-Shot Threat (Opportunity Value): {ev.pre_shot_threat}/100\n"
            f"⚡ Final Threat (Momentum Impact): {ev.final_threat}/100\n"
            f"🛡️ اطمینان (Confidence): {int(ev.confidence * 100)}%\n\n"
            f"فاصله تا دروازه: {ev.distance_to_goal:.1f}m | زاویه: {ev.goal_angle_deg:.1f}°\n"
            f"مدافعان دالان: {ev.defenders_in_corridor} | نزدیک‌ترین مدافع: {ev.nearest_defender_dist:.1f}m\n"
            f"کات توپ: {ev.curve_ratio * 100:.1f}% ({ev.curve_dir})\n"
        )
        if ev.candidate_scores:
            msg += "\nامتیاز کاندیداها:\n"
            for cand, sc in sorted(ev.candidate_scores.items(), key=lambda x: x[1], reverse=True)[:8]:
                msg += f"  - {cand}: {sc:.1f}\n"
        messagebox.showinfo(f"مشخصات کامل شوت #{ev.event_id}", msg)


    def build_debug_tab(self, parent):
        info = tk.Frame(parent, bg="#0d111a", padx=10, pady=6)
        info.pack(fill="x")

        self.lbl_time_hook = tk.Label(info, text="Time Hook: --", font=("Consolas", 9, "bold"), fg="#00f5d4", bg="#0d111a")
        self.lbl_time_hook.grid(row=0, column=0, sticky="w", padx=8)
        self.lbl_gmin = tk.Label(info, text="Game Minute: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_gmin.grid(row=0, column=1, sticky="w", padx=8)
        self.lbl_gsec = tk.Label(info, text="Game Second: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_gsec.grid(row=0, column=2, sticky="w", padx=8)
        self.lbl_total_t = tk.Label(info, text="Total Match Time: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_total_t.grid(row=0, column=3, sticky="w", padx=8)
        self.lbl_last_upd = tk.Label(info, text="Last Time Update: --", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_last_upd.grid(row=0, column=4, sticky="w", padx=8)
        self.lbl_poll = tk.Label(info, text="Poll Rate: --", font=("Consolas", 9), fg="#ffd166", bg="#0d111a")
        self.lbl_poll.grid(row=1, column=0, sticky="w", padx=8, pady=(3, 0))
        self.lbl_decay_info = tk.Label(info, text="Half-Life: -- s (Game Time)", font=("Consolas", 9), fg="#ffd166", bg="#0d111a")
        self.lbl_decay_info.grid(row=1, column=1, sticky="w", padx=8, pady=(3, 0))
        self.lbl_impact_count = tk.Label(info, text="Impacts: 0", font=("Consolas", 9), fg="#a8dadc", bg="#0d111a")
        self.lbl_impact_count.grid(row=1, column=2, sticky="w", padx=8, pady=(3, 0))
        # نسخه ۴: وضعیت هوک گل در پنل دیباگ
        self.lbl_goal_hook_dbg = tk.Label(info, text="Goal Hook: -- | H: - A: -",
                                          font=("Consolas", 9, "bold"), fg="#a8dadc", bg="#0d111a")
        self.lbl_goal_hook_dbg.grid(row=1, column=3, sticky="w", padx=8, pady=(3, 0))

        table_wrap = tk.Frame(parent, bg="#090c12")
        table_wrap.pack(fill="both", expand=True, padx=10, pady=6)
        tk.Label(table_wrap, text="جدول کالیبراسیون — برای هر رخداد: زنجیره Raw Threat → Base Weight → Reliability/Confidence → Final Impact → Decay → Contribution فعلی | ستون Goal: زمان گل → زمان اوج پالس (فاز)",
                 font=("Segoe UI", 8), fg="#7f8fa6", bg="#090c12").pack(anchor="w", pady=(0, 3))

        dcols = ("id", "time", "team", "event", "raw", "base", "rel", "conf", "final", "decay", "contrib", "linked", "goal")
        self.tree_debug = ttk.Treeview(table_wrap, columns=dcols, show="headings", height=13)
        dheads = {"id": "ID", "time": "Game Time", "team": "Team", "event": "Event", "raw": "Raw Threat",
                  "base": "Base Weight", "rel": "Reliability", "conf": "Conf",
                  "final": "Final Impact", "decay": "Decay", "contrib": "Current Contribution",
                  "linked": "Linked Event ID", "goal": "Goal Time → Peak (Pulse)"}
        dwidths = {"id": 45, "time": 62, "team": 58, "event": 165, "raw": 75, "base": 80,
                   "rel": 78, "conf": 50, "final": 85, "decay": 65, "contrib": 125,
                   "linked": 90, "goal": 170}
        for c in dcols:
            self.tree_debug.heading(c, text=dheads[c])
            self.tree_debug.column(c, width=dwidths[c], anchor="center" if c not in ("event", "goal") else "w")
        self.tree_debug.pack(side="top", fill="both", expand=True)
        sb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree_debug.yview)
        sb.pack(side="right", fill="y")
        self.tree_debug.configure(yscrollcommand=sb.set)

        # --- نسخه ۲: پنل دیباگ زنجیره شوت (Counter → Trigger → Tracking → Event → Bus) ---
        chain_wrap = tk.LabelFrame(table_wrap, text="  🔗 زنجیره شوت — Shot Counter → Engine → Event → Momentum (جدیدترین بالا)  ",
                                   font=("Segoe UI", 8, "bold"), fg="#ff70a6", bg="#090c12")
        chain_wrap.pack(side="bottom", fill="x", pady=(5, 0))
        self.txt_shot_chain = tk.Text(chain_wrap, height=8, bg="#0b0f18", fg="#c8d3e0",
                                      font=("Consolas", 7), state="disabled", wrap="none")
        self.txt_shot_chain.pack(fill="both", expand=True, padx=4, pady=3)


    def refresh_debug_table(self):
        if not self.is_monitoring:
            return
        core = self.runtime.get_core()
        cur_t = core["current_match_time"]

        # بخش Debug اطلاعات زمان
        hooked = self.engine.time_hooker.is_hooked and core["time_source"] == "HOOK"
        self.lbl_time_hook.config(text=f"Time Hook: {'ACTIVE ✅' if hooked else 'INACTIVE (FALLBACK) ⚠'}",
                                  fg="#00f5d4" if hooked else "#fca311")
        self.lbl_gmin.config(text=f"Game Minute: {core['game_minute'] if core['game_minute'] is not None else '--'}")
        self.lbl_gsec.config(text=f"Game Second: {core['game_second'] if core['game_second'] is not None else '--'}")
        tm, ts = divmod(int(cur_t), 60)
        self.lbl_total_t.config(text=f"Total Match Time: {cur_t:.2f}s ({tm:02d}:{ts:02d})")
        if core["last_time_change_wall"] > 0:
            ago = time.time() - core["last_time_change_wall"]
            self.lbl_last_upd.config(text=f"Last Time Update: {ago:.1f}s ago")
        self.lbl_poll.config(text=f"Poll Rate: {core['poll_rate_ms']:.1f} ms")
        self.lbl_decay_info.config(text=f"Half-Life: {self.config.MOMENTUM_HALF_LIFE:.0f}s (Game Time)")
        self.lbl_impact_count.config(text=f"Impacts: {len(self.momentum.impacts)}")

        # نسخه ۴: وضعیت هوک گل در تب دیباگ
        gh = self._goal_hook_status
        if gh["hooked"]:
            if gh["captured"]:
                dbg_txt = (f"Goal Hook: ACTIVE ✅ | H: {gh['home'] if gh['home'] is not None else '-'} "
                           f"A: {gh['away'] if gh['away'] is not None else '-'} | rcx=0x{gh['rcx']:X}"
                           if gh["rcx"] else "Goal Hook: ACTIVE ✅ | waiting write...")
                dbg_color = "#00f5d4"
            else:
                dbg_txt = "Goal Hook: INSTALLED ⏳ (در انتظار اولین write ساختار آمار)"
                dbg_color = "#ffd166"
            if gh["secondary"]:
                dbg_txt += " | away-write hook: YES"
        else:
            dbg_txt = "Goal Hook: INACTIVE ⚠ (ثبت گل غیرفعال)"
            dbg_color = "#fca311"
        self.lbl_goal_hook_dbg.config(text=dbg_txt, fg=dbg_color)

        # جدول Impact ها (آخرین ۲۰۰ رکورد برای کالیبراسیون) — نسخه ۲ با ستون‌های Linked/Goal
        with self.momentum._lock:
            impacts = list(self.momentum.impacts[-200:])
        self.tree_debug.delete(*self.tree_debug.get_children())
        for imp in impacts:
            if imp.is_goal_pulse:
                # Goal Pulse: فاکتور از منحنی پاسخ گل (نه decay نمایی ساده)
                factor = self.momentum.goal_response_factor(imp, cur_t)
                phase = self.momentum.goal_pulse_phase(imp, cur_t)
                contrib = imp.final_impact * factor
                goal_str = f"{_fmt_clock(imp.goal_time)} → {_fmt_clock(imp.peak_time)} ({phase})"
            else:
                factor = self.momentum.decay_factor(max(0.0, cur_t - imp.match_time))
                contrib = imp.final_impact * factor
                goal_str = "--"
            m, s = divmod(int(imp.match_time), 60)
            team_str = "Home" if imp.team == "Home" else "Away"
            linked_str = ", ".join(str(i) for i in imp.linked_ids) if imp.linked_ids else "--"
            self.tree_debug.insert("", 0, values=(
                imp.source_event_id, f"{m:02d}:{s:02d}", team_str, imp.event_type,
                f"{imp.raw_threat:.0f}", f"{imp.base_weight:.1f}", imp.reliability,
                f"{int(imp.confidence * 100)}%", f"{imp.final_impact:+.2f}",
                f"{factor:.3f}", f"{contrib:+.2f}", linked_str, goal_str
            ))

        # --- نسخه ۲: رندر زنجیره شوت (جدیدترین بالا) ---
        try:
            lines = []
            for e in list(self.shot_debug_log)[-60:]:
                w = time.strftime("%H:%M:%S", time.localtime(e["wall"]))
                extras = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("wall", "stage"))
                lines.append(f"{w} | {e['stage']:<28} | {extras}")
            self.txt_shot_chain.config(state="normal")
            self.txt_shot_chain.delete("1.0", "end")
            body = "\n".join(reversed(lines))
            # نسخهٔ ۱۰٫۱۴ — خط آمار زنجیرهٔ شوت همیشه در بالای جدول دیباگ
            try:
                _st = self.shot_engine.stats
                stats_txt = ("[SHOT STATS] " + " | ".join(f"{k}={v}" for k, v in _st.items()))
            except Exception:
                stats_txt = "[SHOT STATS] --"
            self.txt_shot_chain.insert("1.0", stats_txt + ("\n" + body if body else ""))
            self.txt_shot_chain.config(state="disabled")
        except Exception:
            pass
        try:
            self.after(self.DEBUG_REFRESH_MS, self.refresh_debug_table)
        except Exception:
            pass


    def start_monitoring(self, *args, **kwargs):
        """Manual attach (header button). v2.1.0 — the GUI build shows the
        original error dialog on failure; the headless build logs instead."""
        ok, msg = self.engine.initialize()
        if not ok:
            if getattr(self, "_gui_active", False):
                try:
                    messagebox.showerror("خطا", msg)
                except Exception:
                    pass
            clog(f"[Momentum] attach failed: {msg}")
            return
        self._begin_monitoring(msg, manual=True)

    def update_field_geometry(self, players: List[Dict]):
        # نسخهٔ ۱۰٫۱۸ — محافظ TclError: بعد از بستن برنامه، callbackهای
        # باقی‌مانده نباید خطای «invalid command name» بدهند
        try:
            self._update_field_geometry_impl(players)
        except tk.TclError:
            pass


    def _update_field_geometry_impl(self, players: List[Dict]):
        gk1 = next((p for p in players if p["seat"] == 1), None)
        gk12 = next((p for p in players if p["seat"] == 12), None)
        if gk1 and gk12:
            if gk1["x"] < gk12["x"]:
                self.team1_side_name = "نیمه چپ (حمله ➔ راست)"
                self.team2_side_name = "نیمه راست (حمله ⬅ چپ)"
                self.team1_attack_dir = 1
                info = "زمین: Home در چپ (حمله ➔) | Away در راست (حمله ⬅)"
            else:
                self.team1_side_name = "نیمه راست (حمله ⬅ چپ)"
                self.team2_side_name = "نیمه چپ (حمله ➔ راست)"
                self.team1_attack_dir = -1
                info = "زمین: Home در راست (حمله ⬅) | Away در چپ (حمله ➔)"
            self.lbl_field_info.config(text=info)
            self.geometry_ready = True

    def update_time_status(self, m_state: str, g_min: Optional[int], g_sec: Optional[int], total_t: float):
        """به‌روزرسانی کارت Match Time و وضعیت بازی (از Worker)
        نسخهٔ ۱۰٫۱۸ — محافظ TclError برای بستن امن برنامه."""
        try:
            self._update_time_status_impl(m_state, g_min, g_sec, total_t)
        except tk.TclError:
            pass


    def _update_time_status_impl(self, m_state: str, g_min: Optional[int], g_sec: Optional[int], total_t: float):
        m, s = divmod(int(total_t), 60)
        self.lbl_match_time.config(text=f"{m:02d}:{s:02d}")
        src = "HOOK ✅ (RSI)" if g_min is not None else "FALLBACK ⚠"
        self.lbl_clock_src.config(text=f"Game Clock: {src}")
        if m_state == "PLAYING":
            self.lbl_status.config(text="وضعیت: مسابقه زنده 🟢", fg="#2ecc71")
        else:
            self.lbl_status.config(text="وضعیت: PAUSED / REPLAY / STOPPED ⏸", fg="#e63946")


    def _init_pipeline_health(self):
        """حالت‌ها/شمارنده‌های لایهٔ تشخیصی (نسخه ۱۰٫۴)"""
        self._gate_counts = {"loop": 0, "ball_players": 0, "geometry": 0,
                             "not_playing": 0, "pass_trig": 0, "shot_trig": 0}
        self._poss_last_ok_wall: Optional[float] = None
        self._poss_last_rearm_wall: Optional[float] = None
        self._players_last_ok_wall: Optional[float] = None
        self._wd_last_total_t: Optional[float] = None
        self._pass_last_chg_wall: Optional[float] = None
        self._pass_last_val: Optional[int] = None
        self._shot_last_chg_wall: Optional[float] = None
        self._shot_last_val: Optional[int] = None
        self._poss_cap_seen: Optional[int] = None

    def _pipeline_health_tick(self, m_state: str, total_t: Optional[float],
                              poss: Optional[str], ball, players,
                              pass_cnt: Optional[int], shot_cnt: Optional[int],
                              now_wall: float, clk_hook: bool):
        """
        نسخه ۱۰٫۴ — هر تیک Worker (سبک): به‌روزرسانی ردیاب‌ها + در زمان due،
        نوشتن یک خط Heartbeat کامل + هشدارهای STALE. هیچ‌وقت exception بالا
        نمی‌دهد و هیچ جریان اصلی‌ای را تغییر نمی‌دهد (فقط مشاهده + re-arm).
        """
        try:
            dbg = getattr(self, "dbg", None)
            if dbg is None or not getattr(dbg, "enabled", False):
                return
            gc = self._gate_counts
            gc["loop"] += 1

            # --- ردیابی مالکیت + دیف آدرس capture (اثبات تغییر آدرس بین بازی‌ها) ---
            poss_ok = poss in ("Home", "Away")
            if poss_ok:
                self._poss_last_ok_wall = now_wall
            cap = getattr(self.engine.poss_hooker, "captured_address", None)
            if cap != self._poss_cap_seen:
                if self._poss_cap_seen is not None and cap is not None:
                    dbg.event("POSS_CAPTURE_CHANGED",
                              old=fmt_ptr(self._poss_cap_seen), new=fmt_ptr(cap),
                              note="آدرس capture مالکیت عوض شد (بازی جدید ساختار تازه)")
                self._poss_cap_seen = cap

            # --- ساعت در حال پیش رفت؟ (برای watchdog محافظه‌کار) ---
            time_adv = (total_t is not None and self._wd_last_total_t is not None
                        and float(total_t) > float(self._wd_last_total_t))
            self._wd_last_total_t = total_t

            # --- Watchdog re-arm مالکیت (قبل از گیت‌ها؛ خودترمیم همیشه زنده) ---
            if not poss_ok and m_state == "PLAYING":
                stale = freeze_seconds(self._poss_last_ok_wall, now_wall)
                thr_ok = (self._poss_last_rearm_wall is None
                          or (now_wall - self._poss_last_rearm_wall) >= POSS_REARM_THROTTLE_SEC)
                if possession_rearm_needed(poss_ok, m_state, time_adv, stale, thr_ok):
                    old_cap = cap
                    try:
                        self.engine.reset_possession_capture()
                    except Exception:
                        pass
                    self._poss_last_rearm_wall = now_wall
                    dbg.event("POSS_REARM", old_cap=fmt_ptr(old_cap),
                              stale_s=round(stale, 1),
                              t=(round(float(total_t), 1) if total_t is not None else None),
                              note="capture مالکیت دوباره مسلح شد — اولین اجرای دستور مالکیت آدرس تازه را می‌گیرد")

            # --- ردیابی بازیکنان ---
            if players:
                self._players_last_ok_wall = now_wall

            # --- ردیابی تغییرات شمارنده‌ها (برای اندازه‌گیری انجماد) ---
            if pass_cnt != self._pass_last_val:
                self._pass_last_val = pass_cnt
                if pass_cnt is not None:
                    self._pass_last_chg_wall = now_wall
            if shot_cnt != self._shot_last_val:
                self._shot_last_val = shot_cnt
                if shot_cnt is not None:
                    self._shot_last_chg_wall = now_wall

            # --- Heartbeat (آستانه‌دار) ---
            if not dbg.heartbeat_due(now_wall):
                return
            try:
                diag = self.engine.debug_diagnostics()
            except Exception:
                diag = {}
            gh = getattr(self, "_goal_hook_status", None) or {}
            frz_poss = freeze_seconds(self._poss_last_ok_wall, now_wall)
            frz_players = freeze_seconds(self._players_last_ok_wall, now_wall)
            frz_pass = freeze_seconds(self._pass_last_chg_wall, now_wall)
            frz_shot = freeze_seconds(self._shot_last_chg_wall, now_wall)

            # --- هشدارهای STALE (قبل از خط HB) ---
            if m_state == "PLAYING" and not poss_ok and frz_poss >= POSS_REARM_STALE_SEC:
                dbg.warn("Pipeline",
                         f"poss invalid for {frz_poss:.0f}s while PLAYING "
                         f"(cap={fmt_ptr(cap)}) — possession dead?")
            if m_state == "PLAYING" and not players and frz_players >= POSS_REARM_STALE_SEC:
                dbg.warn("Pipeline",
                         f"players=0 for {frz_players:.0f}s while PLAYING — "
                         f"PLAYERS_ARRAY dead/moved? (seat0={fmt_ptr(diag.get('seat0'))})")
            if should_warn_frozen_counter(frz_pass, m_state):
                dbg.warn("Pipeline",
                         f"pass_cnt frozen {frz_pass:.0f}s while PLAYING "
                         f"(val={self._pass_last_val}, ptr={fmt_ptr(diag.get('pass_ptr'))}) — STALE?")
            if should_warn_frozen_counter(frz_shot, m_state):
                dbg.warn("Pipeline",
                         f"shot_cnt frozen {frz_shot:.0f}s while PLAYING "
                         f"(val={self._shot_last_val}, ptr={fmt_ptr(diag.get('shot_ptr'))}) — STALE?")

            n_p = len(players) if players else 0
            dbg.event("HB",
                      st=m_state,
                      t=(round(float(total_t), 1) if total_t is not None else None),
                      clk=("HOOK" if clk_hook else "FB"),
                      poss=(poss if poss else "-"),
                      cap=fmt_ptr(cap),
                      ball=("OK" if ball else "NONE"),
                      nP=n_p,
                      **{"pass": pass_cnt, "shot": shot_cnt},
                      pPtr=fmt_ptr(diag.get("pass_ptr")), pCnt=diag.get("pass_cnt"),
                      sPtr=fmt_ptr(diag.get("shot_ptr")), sCnt=diag.get("shot_cnt"),
                      seat0=fmt_ptr(diag.get("seat0")),
                      stateRaw=diag.get("state_raw"),
                      ghCap=("Y" if gh.get("captured") else "N"),
                      ghRcx=fmt_ptr(gh.get("rcx")),
                      ghH=gh.get("home"), ghA=gh.get("away"),
                      gates=(f"loop:{gc['loop']} bp:{gc['ball_players']} "
                             f"geo:{gc['geometry']} np:{gc['not_playing']} "
                             f"pTrig:{gc['pass_trig']} sTrig:{gc['shot_trig']}"),
                      frz=(f"poss:{frz_poss:.0f} play:{frz_players:.0f} "
                           f"pass:{frz_pass:.0f} shot:{frz_shot:.0f}"))
            # ریست شمارنده‌های پنجرهٔ Heartbeat
            gc["loop"] = 0
            gc["ball_players"] = 0
            gc["geometry"] = 0
            gc["not_playing"] = 0
            gc["pass_trig"] = 0
            gc["shot_trig"] = 0
        except Exception:
            pass

    def worker_loop(self):
        while self.is_monitoring:
            time.sleep(self.POLL_INTERVAL)
            try:
                # سنجش نرخ Poll (wall — فقط performance)
                now_wall = time.time()
                if self._last_wall is not None:
                    dt_ms = (now_wall - self._last_wall) * 1000.0
                    self._poll_ema = (self._poll_ema * 0.9 + dt_ms * 0.1) if self._poll_ema else dt_ms
                self._last_wall = now_wall

                # درخواست ریست (دکمه کاربر) — در نخستین فرصت در Worker اجرا می‌شود
                if self._reset_requested:
                    self._reset_requested = False
                    self._perform_reset()
                    continue

                # ---------- 1. Read Game State ----------
                m_state = self.engine.read_match_state()

                # ---------- 2. Read Game Clock (منبع واحد زمان) ----------
                total_t, g_min, g_sec = self.engine.read_game_clock()

                # ---------- 2.0 حیات پروسه (نسخهٔ ۱۰٫۷) ----------
                # خواندن ناموفق پیوسته ⇒ پروسه بسته/هندل مرده؛ اتصال خودکار
                # پس از ENGINE_DEAD_STREAK_LIMIT تیک (~۳ ثانیه) قطع و retry می‌کند.
                if self.engine.link_alive():
                    self._engine_dead_streak = 0
                else:
                    self._engine_dead_streak += 1

                # ---------- 1.1 چرخهٔ capture مالکیت (نسخهٔ ۱۰٫۱۸) ----------
                # اتصالِ «وسط بازی»: تایمر-صفر را ندیده‌ایم؛ با اولین
                # PLAYING چرخهٔ شکار آدرس آغاز می‌شود (هوک → تأیید مقدار ۲
                # → برداشتن هوک). اگر capture/هوک از قبل فعال است، کاری
                # نمی‌کند (یک‌بار مصرف).
                if (m_state == "PLAYING"
                        and not self._poss_first_playing_seen
                        and self.engine.poss_hooker.captured_address is None
                        and not self.engine.poss_hooker.is_hooked):
                    self._poss_first_playing_seen = True
                    self._possession_begin_capture_cycle("first-playing")

                # ---------- 2.05 شروع دست جدید (نسخهٔ ۱۰٫۷) ----------
                # «تایمر صفر شد و بعد شروع به بالا رفتن کرد» = شروع دست جدید
                # (چه بازی قبلی تمام شده باشد چه نشده) ⇒ نوسازی سریع هوک‌ها
                self._timer_rebirth_tick(total_t, now_wall)

                # ---------- 2.05-پ v10.28 — تثبییت فاز/نیمه قبل از اسنپ‌شات ----------
                # (پورت v1.3 از نسخهٔ 2017 — ریشهٔ باگ میدانی «نمودار در دقیقهٔ
                # هدف (۴۳/۸۵) نمایش داده نشد؛ فقط پس از پایان بازی آمد»):
                # قبلاً ماشین فاز (علامتِ افت زمان / Watchdog بازی جدید /
                # تأیید HT و ET) بعد از گیت‌های ball/players/geometry و گیت
                # PLAYING اجرا می‌شد؛ اگر گیت‌های داده حلقهٔ Worker را می‌کشتند
                # (مثلاً players=None در اتصال وسط بازی)، half_number برای
                # همیشه ۱ می‌ماند و نمایش دقیقهٔ هدف نیمهٔ دوم (h2/et) هرگز
                # صادر نمی‌شد — بی‌هیچ خطایی. حالا:
                #   ۱) ردیاب‌های ساعت (seen_max / max_half2) همین‌جا به‌روز
                #      می‌شوند (مستقل از گیت‌های داده)؛
                #   ۲) علامت افت زمان همین‌جا خورده می‌شود (حتی وقتی دادهٔ
                #      توپ/بازیکن قطع است — تصمیم همچنان فقط در PLAYING)؛
                #   ۳) Watchdog بازی جدید و تأیید HT/ET با همان شرط قبلی
                #      «فقط در PLAYING» مصرف می‌شوند (شرط کاربر حفظ شد).
                # نتیجه: هنگام _snapshot_tick مقدار half_number همیشه از
                # منبع واحدِ تازه است — حتی وقتی دادهٔ زمین قطع است.
                if total_t is not None:
                    if total_t > self._match_seen_max_t:
                        self._match_seen_max_t = total_t
                    # نسخهٔ ۱۰٫۷: بیشینهٔ ساعت بازیِ نیمهٔ دوم — برای تشخیص وقت اضافه
                    # (نیمه دوم + ساعت > ۹۰ دقیقه ⇒ تصویر Extra_Match_Moment)
                    if (self.half_number >= 2
                            and float(total_t) > self._tv_max_half2_t):
                        self._tv_max_half2_t = float(total_t)
                    # (v10.28 — علامت‌گذاری افت زمان از بعد از گیت‌های داده به
                    #  این‌جا منتقل شد تا ماشین فاز پشت گیت‌ها گرسنه نماند؛
                    #  تصمیم نهایی همچنان فقط هنگام از سرگیری PLAYING)
                    _prev_t_core = self.runtime.get_core()["current_match_time"]
                    if (self.runtime.connected
                            and should_flag_time_drop(
                                _prev_t_core, total_t,
                                self.config.MATCH_RESTART_DELTA)):
                        self._flag_time_drop(_prev_t_core, total_t)
                if m_state == "PLAYING" and total_t is not None:
                    # ---------- 7.4 Watchdog بازی جدید (نسخه ۱۰٫۳) ----------
                    # «صفر شدن تایمر» در جریان PLAYING نشانهٔ قوی شروع Match جدید
                    # است — مستقل از فلگ افت زمان. اگر مسابقهٔ جاری واقعاً جلو
                    # رفته باشد (بیش از پنجرهٔ شروع + دلتا) و حالا PLAYING با
                    # تایمر ≈ صفر برسیم، مسابقهٔ قبلی تمام شده است:
                    #   90:xx → 0:00 = بازی جدید   |   6:xx → 0:00 = بازی جدید
                    #   (45:xx → 45:00 = شروع نیمه دوم — به watchdog نمی‌خورد
                    #    چون 2700 از پنجرهٔ NEW_GAME_MAX_START بیرون است)
                    # پایان مسابقهٔ اول خودش (90:00 → STOP) هرگز اینجا نمی‌آید؛
                    # ریست فقط با «PLAYING + تایمر ≈ صفر» اجرا می‌شود.
                    if is_new_match_watchdog(self._match_seen_max_t, total_t,
                                             self.config.NEW_GAME_MAX_START,
                                             self.config.MATCH_RESTART_DELTA):
                        clog(f"[MatchLifecycle] NEW_MATCH (watchdog): PLAYING + "
                              f"تایمر {_fmt_clock(total_t)} در حالی که مسابقهٔ جاری تا "
                              f"{_fmt_clock(self._match_seen_max_t)} دیده شده بود — "
                              "ریست کامل مسابقهٔ قبلی (نمودار/رویدادها/مارکرها/شمارنده‌ها)")
                        _d = getattr(self, "dbg", None)
                        if _d:
                            _d.event("NEW_MATCH_WATCHDOG", t=round(float(total_t), 1),
                                     seen_max=round(float(self._match_seen_max_t), 1),
                                     path="watchdog")
                        self._perform_reset(momentum_start_t=total_t)
                        continue

                    # ---------- 7.5 تصمیم‌گیری پس از افت زمان (نسخه ۱۰٫۳ — State Machine) ----------
                    # فقط هنگام از سرگیری PLAYING دربارهٔ افت بزرگ زمان تصمیم می‌گیریم.
                    # تصمیم با classify_resume_after_drop (توابع خالص ۷٫۶) گرفته می‌شود:
                    #   ۱) NEW_MATCH: تایمر ≈ صفر — قوی‌ترین سیگنال؛ مقدم بر HT
                    #      (90:xx → 0:00 و 6:xx → 0:00 هرگز HT نیستند)
                    #   ۲) HT: فقط با قانون سخت —
                    #      half == 1 AND prev_end >= 45*60 AND current حوالی 45:00
                    #      (اگر previous_time < 45:00 باشد، حتی با کاهش زمان، HT ممنوع)
                    #   ۳) KEPT: بقیهٔ حالت‌ها (پایان مسابقه/صفحهٔ آمار) → نمودار حفظ می‌شود
                    if self._ht_pending:
                        _verdict = classify_resume_after_drop(
                            self._ht_prev_end_t, total_t, self.half_number,
                            ht_hard_min=self.config.HT_HARD_MIN_FIRST_HALF,
                            ht_resume_lower_slack=self.config.HT_RESUME_LOWER_SLACK,
                            ht_resume_tolerance=self.config.HT_RESUME_TOLERANCE,
                            new_game_max_start=self.config.NEW_GAME_MAX_START,
                            et_reset_tolerance=getattr(self.config, "ET_RESET_TOLERANCE",
                                                       720.0),
                        )
                        if _verdict == "HT":
                            # HT واقعی: Half 1 End → HT Gap → Half 2 Start (از 45:00)
                            self._ht_pending = False
                            self.half_number = 2
                            self._match_phase = MatchPhase.HALF_2
                            self.momentum.set_phase_label(MatchPhase.HALF_2.value)
                            self.momentum.set_half_break(self.config.HT_GAP_DISPLAY_SECONDS, total_t)
                            self._tv_dirty = True           # نسخهٔ ۱۰٫۱۲ — رندر فوری شکاف HT روی تب TV
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_HT", half1_end=round(float(self._ht_prev_end_t), 1),
                                         half2_start=round(float(total_t), 1))
                            clog(f"[MatchLifecycle] HT تأیید شد: نیمه اول تا "
                                  f"{_fmt_clock(self._ht_prev_end_t)} بازی شده (≥ 45:00) — "
                                  f"نیمه دوم از {_fmt_clock(total_t)}؛ شکاف HT درج شد")
                            self._shot_debug_push("HALF_TIME_BREAK", team="--",
                                                  half1_end=self._ht_prev_end_t,
                                                  half2_start=total_t,
                                                  note=f"نمودار حفظ شد — شکاف HT ({int(self.config.HT_GAP_DISPLAY_SECONDS / 60)} دقیقه) درج شد؛ نمونه‌برداری از اولین ثانیهٔ نیمه دوم از سر گرفته می‌شود (نسخه ۵)")
                            self._ui_post(lambda: self.lbl_status.config(
                                text="وضعیت: نیمه دوم — نمودار حفظ شد (شکاف HT) 🟢", fg="#2ecc71"))
                        elif _verdict in ("ET1", "ET2"):
                            # --- نسخهٔ ۱۰٫۱۵ — شروع وقت اضافه (بندهای ج/د چهار نوع ریست):
                            # ریست تایمر از بالای ۹۰/۱۰۵ روی ۹۰/۱۰۵ + Playing + تایمرِ رشد
                            _et_phase = MatchPhase.ET1 if _verdict == "ET1" else MatchPhase.ET2
                            _et_bound = 90.0 if _verdict == "ET1" else 105.0
                            _et_name = ("نیمهٔ اول وقت اضافه" if _verdict == "ET1"
                                        else "نیمهٔ دوم وقت اضافه")
                            self._ht_pending = False
                            self.half_number = 3 if _verdict == "ET1" else 4
                            self._match_phase = _et_phase
                            self.momentum.set_phase_label(_et_phase.value)
                            self.momentum.set_half_break(
                                self.config.HT_GAP_DISPLAY_SECONDS, total_t)
                            self._tv_dirty = True
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_ET", kind=_verdict,
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         et_start=round(float(total_t), 1))
                            clog(f"[MatchLifecycle] {_verdict} تأیید شد (بند "
                                 f"{'ج' if _verdict == 'ET1' else 'د'}): تایمر از "
                                 f"{_fmt_clock(self._ht_prev_end_t)} (بالای {_et_bound:.0f}:۰۰) "
                                 f"روی {_fmt_clock(total_t)} ریست شده و بازی Playing با "
                                 f"تایمرِ در حال رشد — شروع {_et_name}؛ شکاف نمایشی درج شد")
                            self._shot_debug_push(
                                f"{_verdict}_BREAK", team="--",
                                prev_end=self._ht_prev_end_t,
                                et_start=total_t,
                                note=(f"ریست تایمر روی {_et_bound:.0f}:۰۰ از بالای آن + "
                                      f"Playing + تایمر رشد — شروع {_et_name}"))
                            self._ui_post(lambda v=_verdict: self.lbl_status.config(
                                text=("وضعیت: وقت اضافه — نیمهٔ اول 🟢" if v == "ET1"
                                      else "وضعیت: وقت اضافه — نیمهٔ دوم 🟢"),
                                fg="#2ecc71"))
                        elif _verdict == "NEW_MATCH":
                            # تایمر از صفر شروع شده → بازی جدید (تنها ریست خودکار مجاز)
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("NEW_MATCH_VERDICT", t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         path="time_drop")
                            clog(f"[MatchLifecycle] NEW_MATCH: PLAYING + تایمر "
                                  f"{_fmt_clock(total_t)} (بازی قبلی تا "
                                  f"{_fmt_clock(self._ht_prev_end_t)}) — ریست کامل مسابقهٔ قبلی")
                            self._perform_reset(momentum_start_t=total_t)
                            continue
                        else:
                            # نه HT و نه بازی جدید (مثلاً صفحهٔ آمار/پایان مسابقه) → حفظ نمودار
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_KEPT", resume_t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         note="نمودار حفظ شد (پایان مسابقه/بازگشت بدون ریست)")
                            if self.half_number == 2:
                                self._match_phase = MatchPhase.FULL_TIME
                                self.momentum.set_phase_label(MatchPhase.FULL_TIME.value)
                            elif self._match_phase == MatchPhase.HALFTIME:
                                self._match_phase = MatchPhase.HALF_1
                                self.momentum.set_phase_label(MatchPhase.HALF_1.value)
                            # (فازهای ET1/ET2 در شاخهٔ KEPT حفظ می‌شوند — نسخهٔ ۱۰٫۱۵)
                            # نسخه ۵: تور ایمنی — نمونه‌برداری هرگز نباید برای بقیهٔ
                            # مسابقه بمیرد؛ اگر ساعت پشتِ آخرین نمونهٔ ما باشد،
                            # با شکاف نمایشی کوچکی از سر گرفته می‌شود
                            try:
                                self.momentum.resync_clock(total_t)
                            except Exception:
                                pass
                            self._shot_debug_push("TIME_DROP_KEPT", team="--",
                                                  prev_end=self._ht_prev_end_t,
                                                  resume_t=total_t,
                                                  note="نمودار حفظ شد (پایان مسابقه/بازگشت بدون ریست) — نمونه‌برداری مجدداً فعال شد (نسخه ۵)")

                # ---------- 2.06 اسنپ‌شات نمودار TV (نسخهٔ ۱۰٫۱۱) ----------
                # کپچر در «دقیقهٔ هدف − ۱»، نمایش در «دقیقهٔ هدف» و تشخیص
                # پایان بازی (>۹۰′/>۱۲۰′ توقف ≥۱۲s) — باید قبل از گیت‌های
                # early-continue اجرا شود تا در STOP/Pause هم زنده بماند.
                self._snapshot_tick(total_t, m_state, now_wall)

                # ---------- 2.06-پ v2.0.5 — crest banner + ball-link ----------
                # * بنرِ نشانِ تیم‌ها (دقیقهٔ اول، ۵ ثانیه) — علامتِ سلامتِ
                #   خطِ داده + مسیر نمایش؛ عیناً روی مستطیلِ نمودارها.
                # * چکِ دوره‌ایِ هوکِ توپ (~۲ ثانیه) — اگر ابزار دیگری
                #   (خروج GLT / crash-recovery) هوکِ مشترک را بازنویسی کرده
                #   باشد، خودکار re-adopt/reinstall می‌شود.
                try:
                    self._crest_banner_tick(total_t, m_state)
                except Exception as _e:
                    try:
                        print(f"[CREST BANNER] tick error: "
                              f"{type(_e).__name__}: {_e}", flush=True)
                    except Exception:
                        pass
                if now_wall - self._ball_link_last_check >= 2.0:
                    self._ball_link_last_check = now_wall
                    try:
                        self._ball_link_verify(m_state)
                    except Exception:
                        pass

                # ---------- 2.1 Goal Hook Poll (نسخه ۱۰) — قبل از همهٔ گیت‌ها ----------
                # شمارندهٔ گل در حافظه به توپ/بازیکنان/هندسه هیچ وابستگی‌ای ندارد؛
                # Poll باید حتی در منو/Replay/جشن گل ادامه داشته باشد.
                # (در نسخه ۹ Poll پشت دو early-continue بود و با قطع دادهٔ زمین
                #  کاملاً متوقف می‌شد — عیب A مستند در هدر نسخه ۱۰)
                self._poll_goal_hook(
                    gh_pick_poll_time(total_t,
                                      self.runtime.get_core().get("current_match_time"))
                )

                # ---------- 3-6. Possession / Ball / Players / Counters ----------
                poss = self.engine.read_possession()
                ball = self.engine.read_ball()
                players = self.engine.read_players()
                pass_cnt = self.engine.read_pass_counter()
                shot_cnt = self.engine.read_shot_counter()

                # v2.0.6 — ball-feed freshness bookkeeping (evidence line for
                # 'charts visible but empty': a STALE feed means the shared
                # hook's data buffer is not being written anymore)
                try:
                    if ball is not None and ball != self._ball_feed_last:
                        self._ball_feed_last = ball
                        self._ball_feed_change_t = now_wall
                except Exception:
                    pass

                # ---------- 2.15 نسخهٔ ۱۰٫۲۷ — کارت قرمز (شمارندهٔ پوینتری) ----------
                # مثل گل: به توپ/هندسه وابسته نیست؛ اما برای «انتساب تیم»
                # به لیست بازیکنان همین فریم نیاز دارد (تماشای z≈40).
                # حتی در STOP/جشن کارت ادامه دارد (بازیکن‌ها خوانده می‌شوند).
                try:
                    self._poll_red_card(
                        gh_pick_poll_time(total_t,
                                          self.runtime.get_core().get("current_match_time")),
                        players)
                except Exception as _rc_ex:
                    clog(f"[RedCardPoll] poll error: "
                         f"{type(_rc_ex).__name__}: {_rc_ex}")

                # ---------- 6.0 سلامت خط لولهٔ داده (نسخه ۱۰٫۴) ----------
                # Heartbeat + Watchdog مالکیت «قبل از همهٔ گیت‌ها» اجرا می‌شوند
                # تا حتی وقتی گیت‌ها حلقه را می‌کشند، لاگ نشان دهد کدام لایه
                # مرده است (players؟ possession؟ شمارنده‌ها؟) و مالکیت خودترمیم شود.
                self._pipeline_health_tick(m_state, total_t, poss, ball, players,
                                           pass_cnt, shot_cnt, now_wall,
                                           clk_hook=(g_min is not None))

                if not ball or not players:
                    self._gate_counts["ball_players"] += 1
                    # v2.0.7 — visible evidence for "charts visible but
                    # empty": this gate silently skips the WHOLE event
                    # pipeline (shots/passes/momentum history) while the
                    # goal/time/red-card polls (before the gate) keep
                    # working — exactly the field symptom. Say WHICH layer
                    # is dead and for how long, every 5 s.
                    if now_wall - getattr(self, "_gate_diag_last", 0.0) >= 5.0:
                        if not getattr(self, "_gate_blocked_since", 0.0):
                            self._gate_blocked_since = now_wall
                        self._gate_diag_last = now_wall
                        _ball_txt = ("None" if ball is None else
                                     f"({ball[0]:.1f},{ball[1]:.1f},{ball[2]:.1f})"
                                     if len(ball) >= 3 else repr(ball))
                        print(f"[DATA GATE] BLOCKED for "
                              f"{now_wall - self._gate_blocked_since:.0f}s — "
                              f"ball={_ball_txt} "
                              f"(buffer=0x{int(self.engine.ball_data_addr or 0):X}) "
                              f"players={len(players) if players else 0}/22 "
                              f"poss={poss} m_state={m_state} "
                              f"skipped_ticks="
                              f"{self._gate_counts['ball_players']}",
                              flush=True)
                    continue
                if getattr(self, "_gate_blocked_since", 0.0):
                    print(f"[DATA GATE] RECOVERED after "
                          f"{now_wall - self._gate_blocked_since:.0f}s — "
                          f"ball={tuple(round(v, 1) for v in ball)} "
                          f"players={len(players)} (event pipeline resumes)",
                          flush=True)
                    self._gate_blocked_since = 0.0
                    self._gate_diag_last = 0.0

                self._ui_post(self.update_field_geometry, players)
                if not self.geometry_ready:
                    self._gate_counts["geometry"] += 1
                    continue

                # (v10.28 — علامت‌گذاری افت زمان به بند 2.05-پ منتقل شد — قبل از
                #  گیت‌های داده؛ تا ماشین فاز پشت گیت‌ها گرسنه نماند)

                # ---------- 7. Build SnapshotFrame ----------
                frame = SnapshotFrame(
                    timestamp=now_wall,
                    match_time=total_t,
                    ball=ball,
                    players=players,
                    possession=poss,
                    shot_counter=shot_cnt,
                    pass_counter=pass_cnt
                )
                self.frame_buffer.append(frame)
                self._frame_seq += 1   # نسخهٔ ۱۰٫۱۴ — شمارندهٔ مطلق فریم
                self.runtime.update_core(m_state, total_t, g_min, g_sec, poss, self._poll_ema)
                self._ui_post(self.update_time_status, m_state, g_min, g_sec, total_t)

                # ---------- 7.1 Goal Hook — به گام ۲٫۱ منتقل شد (نسخه ۱۰) ----------
                # Poll گل حالا قبل از گیت‌های ball/players/geometry اجرا می‌شود؛
                # هیچ مسیر ثبت گلی دیگر پشت early-continueها پنهان نیست.

                # ---------- 7.2 ره‌گیری پرواز شوت حتی در STOP/Pause (نسخه ۳) ----------
                # اگر شوت در حال ره‌گیری است، یک گام (با burst فشرده ~15ms)
                # قبل از گیت PLAYING اجرا می‌شود تا پرواز در توقف‌های کوتاه
                # (خروج توپ/جشن گل) قطع نشود؛ timeout دیواری خودش محدود می‌کند.
                # نسخهٔ ۱۰٫۱۴ — پردازش صف کاندیدها هم در توقف‌ها زنده می‌ماند
                # (بافر در STOP هم تغذیه می‌شود؛ ریکاوری فریم‌محور کار می‌کند)
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                shot_data_early = self._step_shot_tracking(burst=6)
                if shot_data_early:
                    self._register_shot_data(shot_data_early)

                # Pause / Replay / Stop → زمان بازی ثابت است؛ Momentum هم نباید decay کند
                if m_state != "PLAYING":
                    self.pass_engine.abort()
                    self._gate_counts["not_playing"] += 1
                    continue

                # (v10.28 — Watchdog بازی جدید (۷.۴) و تصمیم‌گیری پس از افت زمان
                #  (۷.۵) به بند 2.05-پ منتقل شدند — قبل از _snapshot_tick و
                #  گیت‌های داده؛ مصرف فقط در PLAYING حفظ شده است)

                # ---------- 8.0 تعیین Context مالکیت (۱۰٫۱۴ — «قبل از» تریگر شوت) ----------
                # ترتیب صحیح مشخصات کاربر:
                #   Read Possession → Read Shot Counter → Read Ball/Players
                #   → Determine valid possession context
                #   → Detect Shot Counter increment → Assign shot team → ...
                # یعنی Context مالکیت باید «قبل از» بررسی تریگر شوت معتبر شود تا
                # هرگز «current_possession=None/stale ⇒ تریگر گم» رخ ندهد.
                prev_poss_ctx = self.current_possession   # نسخهٔ ۱۰٫۱۴ — Context قبلی
                if poss and self.current_possession is None:
                    # نخستین شناسایی مالکیت — آغاز زنجیره بدون رخداد ناخواسته
                    self.current_possession = poss
                    att_dir = self.team1_attack_dir if poss == "Home" else -self.team1_attack_dir
                    self.event_engine.handle_possession_change(
                        new_team=poss, match_time=total_t,
                        start_x_att=ball[0] * att_dir, timestamp=now_wall, ball_pos=ball
                    )
                    self.pass_counters[poss] = pass_cnt
                elif poss and poss != self.current_possession:
                    self.current_possession = poss
                    att_dir = self.team1_attack_dir if poss == "Home" else -self.team1_attack_dir
                    self.event_engine.handle_possession_change(
                        new_team=poss, match_time=total_t,
                        start_x_att=ball[0] * att_dir, timestamp=now_wall, ball_pos=ball
                    )
                    # تنظیم مجدد baseline شمارندهٔ «پاس» برای تیم فعال جدید
                    self.pass_counters[poss] = pass_cnt

                active_team = self.current_possession

                # ---------- 8.1 Shot Counter Trigger (۱۰٫۱۴ — صف کاندیدها) ----------
                # شمارنده شوت «سراسری» است (هر دو تیم). baseline فقط یک متغیر است
                # و با تغییر مالکیت هرگز بازنویسی نمی‌شود (باگ نسخه ۲).
                # نسخهٔ ۱۰٫۱۴: هر افزایش = ۱ کاندید در صف ShotEngine — هیچ تریگری
                # گم نمی‌شود؛ تیم شوت با fallback کاربر تعیین و در جهشِ «همزمانِ»
                # مالکیت، Context قبلی حفظ می‌شود (تیم اشتباه ممنوع).
                cnt_before_dbg = self.shot_counter_baseline
                new_baseline, trig_event = self._shot_trigger_decision(
                    self.shot_counter_baseline, shot_cnt
                )
                self.shot_counter_baseline = new_baseline
                if trig_event == "TRIGGER":
                    # --- تعیین تیم شوت (fallback مشخصات کاربر) ---
                    possession_for_shot = self.current_possession
                    if possession_for_shot is None and poss is not None:
                        possession_for_shot = poss
                    # جهشِ همزمان مالکیت و شمارنده ⇒ Context «قبلی» مقدم است
                    # (بعد از شوت معمولاً مالکیت عوض می‌شود؛ اگر همان لحظه در
                    #  داده دیده شد، شوت نباید به تیم اشتباه نسبت داده شود)
                    flip_same_tick = (prev_poss_ctx is not None
                                      and possession_for_shot is not None
                                      and prev_poss_ctx != possession_for_shot)
                    primary_team = prev_poss_ctx if flip_same_tick else possession_for_shot
                    team_candidates: List[str] = []
                    for _t in (primary_team, prev_poss_ctx, possession_for_shot, poss):
                        if _t and _t not in team_candidates:
                            team_candidates.append(_t)
                    self.shot_engine.stats["counter_increments"] += 1
                    self._gate_counts["shot_trig"] += 1
                    self.shot_engine.push_trigger(
                        counter_value=shot_cnt, team=primary_team,
                        alternates=team_candidates, match_time=total_t,
                        wall_now=now_wall, frame_seq=self._frame_seq,
                        team1_attack_dir=self.team1_attack_dir
                    )
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_TRIGGER", before=cnt_before_dbg, after=shot_cnt,
                                 t=(round(float(total_t), 1) if total_t is not None else None),
                                 poss=primary_team)
                    self._shot_debug_push("COUNTER_INCREMENT", team=primary_team or "--",
                                          counter_before=cnt_before_dbg, counter_after=shot_cnt,
                                          trigger_match_time=total_t,
                                          shot_engine_state=self.shot_engine.state)
                    self._shot_debug_push("TRIGGER_TEAM", team=primary_team or "--",
                                          candidates=",".join(team_candidates) or "Home,Away",
                                          flip_same_tick=flip_same_tick,
                                          trigger_match_time=total_t,
                                          note="تیم شوت از Context مالکیت (با fallback) تعیین شد")
                elif trig_event == "RESET":
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_COUNTER_RESET", before=cnt_before_dbg, after=shot_cnt,
                                 note="شمارنده شوت ریست شد (نیمه دوم/ری‌استارت)")
                    self._shot_debug_push("COUNTER_RESET", team="--",
                                          counter_before=cnt_before_dbg,
                                          counter_after=shot_cnt,
                                          trigger_match_time=total_t,
                                          note="شمارنده شوت ریست شد (نیمه دوم/ری‌استارت)")
                    # نسخهٔ ۱۰٫۱۴ — کاندیدهای نسلِ قبلی کهنه‌اند؛ فقط با دلیل حذف می‌شوند
                    self.shot_engine.on_counter_reset(reason="shot_counter_reset")
                elif trig_event == "BASELINE":
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_BASELINE", val=shot_cnt)

                # ---------- 9. Update Pass Engine ----------
                if active_team:
                    if self.pass_counters[active_team] is None:
                        self.pass_counters[active_team] = pass_cnt
                    elif pass_cnt is not None and pass_cnt > self.pass_counters[active_team]:
                        self.pass_counters[active_team] = pass_cnt
                        # Counter فقط Trigger است — PassDetector واقعی شروع می‌شود
                        self._gate_counts["pass_trig"] += 1
                        self.pass_engine.on_counter_increment(ball, now_wall, total_t, active_team, players)

                pass_data = self.pass_engine.generate_event(
                    ball, total_t, players, self.team1_attack_dir,
                    possession_provider=self.engine.read_possession
                )

                # ---------- 10. Shot Engine — صف کاندیدها + ره‌گیری (۱۰٫۱۴) ----------
                # پردازش سرِ صف کاندیدهای شوت (۱ افزایش شمارنده = ۱ کاندید)؛
                # مستقل از حلقهٔ اصلی (غیربلاک‌کننده) و بدون گم‌شدن فریم‌ها.
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                # ره‌گیری پرواز با burst فشرده (~15ms × 6 ≈ مطابق حلقهٔ ابزار مستقل)
                shot_data = self._step_shot_tracking(burst=6)
                if shot_data:
                    # نسخهٔ ۱۰٫۱۴ — رفع باگ گم‌شدن ثبت: خروجی نهاییِ این مسیر
                    # هم باید حتماً register شود (قبلاً فقط مسیر 7.2 ثبت می‌کرد)
                    self._register_shot_data(shot_data)

                # ---------- 11-12. Process Event Engine + Register new Events ----------
                if pass_data:
                    self.event_engine.register_pass_event(pass_data)
                    self._ui_post(self.update_pass_card, pass_data)
                self.event_engine.process_frame(self.frame_buffer, frame, self.team1_attack_dir)

                # ---------- 13-15. Events→Impacts (via Bus) + Momentum با MATCH TIME ----------
                self.momentum.update(total_t)

                # ---------- 16. Schedule UI refresh ----------
                # (Event Timeline — هر رخداد جدید بلافاصله)
                if len(self.event_engine.events) > self._last_ev_count:
                    new_evs = self.event_engine.events[self._last_ev_count:]
                    self._last_ev_count = len(self.event_engine.events)
                    self._ui_post(self.update_ui_events, new_evs)

                # (Possession Sequences — Live Update از _graph_loop انجام می‌شود؛
                #  اینجا فقط شمارش برای دیباگ به‌روز می‌ماند)
                if len(self.momentum.impacts) > self._last_imp_count:
                    self._last_imp_count = len(self.momentum.impacts)

                self._ui_post(self.update_possession_cards)
                self._ui_post(self._update_goal_hook_label)

            except Exception as ex:
                clog(f"[Worker Error] Unhandled exception: {ex}")
                # نسخه ۱۰٫۴: خطای تکرارشوندهٔ Worker در لاگ فایل هم ثبت می‌شود
                # (اگر حلقه هر تیک بترکد، فقط گل‌ها که قبل از خطا Poll می‌شوند ثبت می‌مانند)
                _d = getattr(self, "dbg", None)
                if _d:
                    try:
                        _d.error("WORKER-ERROR",
                                 f"{type(ex).__name__}: {ex} | " +
                                 traceback.format_exc(limit=4).replace("\n", " | "))
                    except Exception:
                        pass

    def _poll_red_card(self, match_t: float,
                       players: Optional[List[Dict]] = None):
        """
        نسخهٔ ۱۰٫۲۷ — خواندن شمارندهٔ کارت قرمز (پوینتر ۳ سطحی — بدون هوک) و
        انتساب تیم با تماشای بازیکن اخراجی:
            [base+0x36F3F88] +0x350 +0x4E0 → u8
        هر «افزایش» = ۱ کارت قرمز. تیمِ کارت در لحظهٔ صدور معلوم نیست؛
        کد چند ثانیه بازیکن‌ها را زیر نظر می‌گیرد — بازیکن اخراجی در
        z≈40 (بیرون خط طولی) می‌نشیند؛ مال هر تیمی بود، کارت برای همان
        تیم ثبت می‌شود. زمان مارکر = لحظهٔ صدور (issued_t — فریزشده)،
        نه لحظهٔ تشخیص. اخراجی‌های قبلی (seat) از کاندیدها حذف می‌شوند.
        """
        d = self._rc_diag
        try:
            raw = self.engine.read_red_card_counter()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[RedCardPoll] خطای خواندن شمارنده: "
                      f"{type(ex).__name__}: {ex}")
            return
        if raw is None:
            d["n_none"] += 1
            return
        d["n_ok"] += 1
        st = self._rc_state

        # --- ۱) BASELINE — اولین خواندن معتبر ---
        if st["baseline"] is None:
            st["baseline"] = int(raw)
            clog(f"[RedCardPoll] BASELINE شمارندهٔ کارت قرمز = {raw} "
                  "(اولین خواندن معتبر — کارت‌های قبل از اتصال بازسازی "
                  "نمی‌شوند)")
            return

        # --- ۲) افزایش → کارت جدید (های) در انتظار انتساب تیم ---
        if raw > st["baseline"]:
            n_new = int(raw) - st["baseline"]
            if n_new > RC_MAX_JUMP:
                clog(f"[RedCardPoll] ⚠ جهش غیرعادی شمارنده "
                      f"({st['baseline']} → {raw}) — ری‌بیس‌لاین بدون ثبت کارت")
                st["baseline"] = int(raw)
                return
            try:
                with self.momentum._lock:
                    _disp = float(match_t) + float(self.momentum.display_offset)
            except Exception:
                _disp = float(match_t)
            _half = int(self.half_number)
            for _ in range(n_new):
                st["pending"].append({
                    "issued_t": float(match_t),
                    "issued_disp": _disp,
                    "issued_half": _half,
                    "wall": time.time(),
                    "exclude": set(st["exiles"]),
                    "tried": set(),
                })
            st["baseline"] = int(raw)
            d["n_cards"] += n_new
            clog(f"[RedCardPoll] 🟥 کارت قرمز صادر شد "
                  f"({int(raw) - n_new} → {raw}) در {_fmt_clock(match_t)} — "
                  f"در انتظار تعیین تیم (تماشای z≈{RC_Z_TARGET:.0f})")

        # --- ۳) افت → گذرا (baseline حفظ)؛ ریست فقط در پنجرهٔ بازی جدید ---
        elif raw < st["baseline"]:
            _mt = None
            try:
                _mt = float(match_t) if match_t is not None else None
            except (TypeError, ValueError):
                _mt = None
            if _mt is not None and _mt <= float(self.config.NEW_GAME_MAX_START):
                clog(f"[RedCardPoll] RESET شمارندهٔ کارت قرمز: "
                      f"{st['baseline']} → {raw} (بازی جدید)")
                st["baseline"] = int(raw)
                st["pending"].clear()
                st["exiles"].clear()
            else:
                clog(f"[RedCardPoll] ⏳ افت گذرای شمارنده "
                      f"({st['baseline']} → {raw}) نادیده گرفته شد")

        # --- ۴) تماشای بازیکن‌ها: انتساب تیم + به‌روزرسانی تبعیدشدگان ---
        now_exiles: Dict[int, Dict] = {}
        if players:
            for p in players:
                try:
                    _z = float(p.get("z", float("nan")))
                    _seat = int(p.get("seat", -1))
                except (TypeError, ValueError):
                    continue
                if abs(_z - RC_Z_TARGET) <= RC_Z_TOL:
                    now_exiles[_seat] = p

        for pd in list(st["pending"]):
            cands = [p for seat, p in sorted(now_exiles.items())
                     if seat not in pd["exclude"]
                     and seat not in pd["tried"]]
            if not cands:
                continue
            p = cands[0]
            try:
                _seat = int(p.get("seat", -1))
            except (TypeError, ValueError):
                _seat = -1
            pd["tried"].add(_seat)
            team = str(p.get("team", "Home"))
            if team not in ("Home", "Away"):
                team = "Home"
            self._register_hook_red_card(team, pd, p)
            st["pending"].remove(pd)
            st["exiles"].add(_seat)
            d["n_attr"] += 1

        # تبعیدشدگانِ بدون کارتِ در انتظار هم ثبت شوند — کارتِ بعدی آن‌ها
        # را از کاندیدها حذف می‌کند (اخراجی قدیمی دوباره انتساب نمی‌شود)
        st["exiles"].update(now_exiles.keys())

        # --- ۵) مهلت انتساب (زمان بازی) + سقف wall تور ایمنی ---
        try:
            _mt_now = float(match_t) if match_t is not None else None
        except (TypeError, ValueError):
            _mt_now = None
        _now_wall = time.time()
        for pd in list(st["pending"]):
            _expired = False
            if (_mt_now is not None
                    and (_mt_now - pd["issued_t"]) > RC_WATCH_WINDOW_S):
                _expired = True
            if (_now_wall - pd["wall"]) > RC_WATCH_WALL_CAP_S:
                _expired = True
            if _expired:
                st["pending"].remove(pd)
                d["n_timeout"] += 1
                clog(f"[RedCardPoll] ⌛ مهلت تعیین تیم کارت (صادرشده در "
                      f"{_fmt_clock(pd['issued_t'])}) به پایان رسید — "
                      "مارکر ثبت نشد")

    def _register_hook_red_card(self, team: str, pd: Dict[str, Any],
                                player: Optional[Dict] = None):
        """
        نسخهٔ ۱۰٫۲۷ — ثبت مارکر کارت قرمز روی نمودار (عین گل: خط عمودی +
        آیکون کارت به‌جای توپ). زمان مارکر = لحظهٔ صدور کارت (issued_t —
        فریزشده هنگام افزایش شمارنده)، نه لحظهٔ تشخیص تیم. بدون پالس
        مومنتوم / Event Bus — فقط مارکر (عین نسخهٔ 2017).
        """
        try:
            self.momentum.add_hook_red_card_marker(
                team,
                float(pd.get("issued_t", 0.0)),
                int(pd.get("issued_half", 1) or 1),
                disp_time=pd.get("issued_disp"),
            )
            self._tv_dirty = True
            try:
                _seat = int(player.get("seat")) if player else None
            except Exception:
                _seat = None
            clog(f"[RedCard→Graph] مارکر کارت قرمز {team} ثبت شد | "
                  f"صدور={_fmt_clock(pd.get('issued_t', 0.0))} | "
                  f"تشخیص از بازیکن seat={_seat} در z≈{RC_Z_TARGET:.0f} | "
                  f"مارکرهای فعال={self.momentum.red_card_marker_count()}")
            self._shot_debug_push(
                "RED_CARD_REGISTERED", team=team,
                match_time=pd.get("issued_t", 0.0),
                half=int(pd.get("issued_half", 1) or 1),
                seat=_seat, z_target=RC_Z_TARGET,
                note="شمارندهٔ پوینتری + انتساب z=40 (v10.27)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("RED_CARD_REGISTERED", team=team,
                         t=round(float(pd.get("issued_t", 0.0)), 1),
                         seat=_seat)
        except Exception as ex:
            clog(f"[RedCard] خطای ثبت مارکر: {ex}")

    def _poll_goal_hook(self, match_t: float):
        """
        نسخه ۱۰ — خواندن دو شمارندهٔ گل ([rcx+0x158] Home / [rcx+0x15C] Away)
        و ثبت هر افزایش به‌عنوان گل روی Event Bus.

        منطق تصمیم با نسخه‌های قبل یکسان است (counter_event / Sticky
        First-Capture / سقف جهش MAX_GOAL_JUMP)؛ فقط لایهٔ لاگ
        [GoalHookPoll] اضافه شده تا «هر» مسیر شکست در Console دیده شود:
          - هوک فعال نیست / هنوز capture نشده / خطای خواندن
          - تغییر RAW شمارنده‌ها (بالا یا پایین)
          - BASELINE / RESET / تعویض ساختار (rcx)
          - تپش وضعیت هر ۵ ثانیه
        مقاوم به Replay: شمارنده در پخش مجدد جهش نمی‌زند؛ فقط «افزایش» گل است.
        اتصال شوت ← گل با MATCH TIME.
        """
        d = self._gh_diag
        try:
            st = self.engine.read_goal_counters()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[GoalHookPoll] خطای خواندن شمارنده: {type(ex).__name__}: {ex}")
            return
        if not st:
            d["n_err"] += 1
            return

        prev_status = self._goal_hook_status
        events_before = prev_status.get("events", 0)
        self._goal_hook_status = {
            "hooked": bool(st.get("hooked")),
            "captured": bool(st.get("captured")),
            "secondary": bool(st.get("secondary")),
            "rcx": st.get("rcx"),
            "home": st.get("home"),
            "away": st.get("away"),
            "events": events_before
        }

        # ---------------------------------------------------------
        # [GoalHookPoll] — لایهٔ مشاهده‌پذیری (نسخه ۱۰)
        # ---------------------------------------------------------
        if not st.get("hooked"):
            d["n_nohook"] += 1
            if not d["notified_no_hook"]:
                d["notified_no_hook"] = True
                clog("[GoalHookPoll] هوک گل فعال نیست — ثبت گل غیرفعال "
                      "(نتیجهٔ نصب هوک در Console بالاتر را بررسی کنید)")
            return
        d["notified_no_hook"] = False

        if not st.get("captured"):
            d["n_wait"] += 1
            if d["last_captured"] is not False:
                clog("[GoalHookPoll] captured=False — در انتظار اولین write ساختار آمار "
                      "(slot صفر است؛ با اولین به‌روزرسانی آمار گل در خود بازی capture می‌شود)")
            d["last_captured"] = False
            return
        if d["last_captured"] is not True:
            clog(f"[GoalHookPoll] capture انجام شد ✅ rcx={(st.get('rcx') or 0):#x} "
                  f"home={st.get('home')} away={st.get('away')}")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_CAPTURE", rcx=fmt_ptr(st.get("rcx")),
                         home=st.get("home"), away=st.get("away"),
                         t=(round(float(match_t), 1) if match_t is not None else None))
        d["last_captured"] = True
        d["n_ok"] += 1

        _rcx = st.get("rcx")
        if d["last_rcx"] is not None and _rcx != d["last_rcx"]:
            clog(f"[GoalHookPoll] ⚠ ساختار آمار عوض شد: rcx {d['last_rcx']:#x} → {(_rcx or 0):#x} "
                  f"(شمارنده‌ها از ساختار جدید خوانده می‌شوند)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_RCX_CHANGED", old=fmt_ptr(d["last_rcx"]), new=fmt_ptr(_rcx),
                         note="ساختار آمار مسابقه در حافظه جابه‌جا شده")
        d["last_rcx"] = _rcx

        _h, _a = st.get("home"), st.get("away")
        if _h != d["last_home"] or _a != d["last_away"]:
            clog(f"[GoalHookPoll] RAW Home: {d['last_home']} → {_h} | "
                  f"Away: {d['last_away']} → {_a} | t={_fmt_clock(match_t)}")
        d["last_home"], d["last_away"] = _h, _a

        # ---------------------------------------------------------
        # تصمیم (منطق دست‌نخورده — نسخه ۴/۶/۹)
        # ---------------------------------------------------------
        # ⚫ ریشهٔ اصلی «هیچ گلی ثبت نمی‌شود» (نسخه ۱۰):
        #   poll() کلیدها را «home/away» کوچک برمی‌گرداند، اما اینجا
        #   st.get(team) با «Home/Away» بزرگ خوانده می‌شد → همیشه None →
        #   counter_event(None, None) → WAIT ابدی → هیچ گلی هرگز ثبت
        #   نمی‌شد (از نسخه ۵ تا ۹!). برچسب UI از st.get("home") می‌خواند،
        #   برای همین عدد گوشهٔ صفحه درست بود ولی تصمیم همیشه WAIT بود.
        #   اصلاح: st.get(team.lower())
        for team in ("Home", "Away"):
            new_v = st.get(team.lower())
            old_v = self.goal_counters[team]
            decision, n_goals = GoalHooker.counter_event(old_v, new_v)
            if decision == "BASELINE":
                # --- نسخه ۱۰٫۳: First-Capture Goal -------------------------
                # اولین Capture موفق Goal Hook ممکن است «همان لحظهٔ گل اول
                # مسابقه» باشد (Capture در اولین اجرای دستور گل انجام می‌شود).
                # در منطق قبلی این اولین خواندن صرفاً BASELINE می‌شد و گلِ
                # اول برای همیشه گم می‌شد. اکنون: اگر شمارندهٔ یک تیم در
                # اولین خواندن معتبر > 0 باشد، این «اختلاف منطقی» از baseline
                # صفرِ شروع مسابقه است و همان لحظه به‌عنوان گل واقعی ثبت
                # می‌شود (مارکر + Goal Event + پالس). سپس baseline داخلی
                # همان مقدار می‌شود و روال عادی Counter Tracking (1→2 = گل
                # جدید) بدون دوبار ثبت‌شدن ادامه می‌یابد. این منطق فقط برای
                # اولین Capture هر تیم است و بعد از reset_capture (بازی جدید)
                # دوباره مسلح می‌شود.
                if self._gh_fc_pending.get(team):
                    self._gh_fc_pending[team] = False
                    self._register_first_hook_goal(team, new_v, match_t)
                self.goal_counters[team] = new_v
                if not d["baselined"].get(team):
                    d["baselined"][team] = True
                    clog(f"[GoalHookPoll] BASELINE {team}={new_v} "
                          "(اولین خواندن معتبر — مبدأ؛ گل حساب نمی‌شود)")
                self._shot_debug_push("GOAL_COUNTER_BASELINE", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="اولین خواندن معتبر شمارندهٔ گل")
            elif decision == "GOAL":
                self.goal_counters[team] = new_v
                clog(f"[GoalHook] تغییر شمارندهٔ گل {team}: {old_v} → {new_v} "
                      f"({n_goals} گل جدید) در {_fmt_clock(match_t)}")
                _d = getattr(self, "dbg", None)
                if _d:
                    _d.event("GOAL_COUNTER", team=team, old=old_v, new=new_v,
                             n=n_goals, decision=decision,
                             t=(round(float(match_t), 1) if match_t is not None else None))
                for _ in range(n_goals):
                    self._register_hook_goal(team, match_t)
            elif decision == "RESET":
                self.goal_counters[team] = new_v
                d["baselined"][team] = False
                clog(f"[GoalHookPoll] RESET شمارندهٔ {team}: {old_v} → {new_v} "
                      "(بازی جدید / ری‌سنک)")
                self._shot_debug_push("GOAL_COUNTER_RESET", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="شمارندهٔ گل ریست شد (بازی جدید)")

        # ---------------------------------------------------------
        # تپش وضعیت — هر ۵ ثانیه
        # ---------------------------------------------------------
        now_wall = time.time()
        if gh_due_heartbeat(now_wall, d["last_hb"]):
            d["last_hb"] = now_wall
            clog(f"[GoalHookPoll] ❤ hooked=✓ captured=✓ rcx={(_rcx or 0):#x} "
                  f"H={_h} A={_a} | "
                  f"baseline=(H:{self.goal_counters['Home']}, A:{self.goal_counters['Away']}) | "
                  f"polls ok={d['n_ok']} wait={d['n_wait']} err={d['n_err']} nohook={d['n_nohook']}")

    def _register_hook_goal(self, team: str, match_t: float):
        """
        نسخه ۹ — ثبت یک گل از تغییر شمارندهٔ هوک:
          ۱) مارکر مستقیم روی نمودار (مسیر مستقل از Event Bus) — اول از همه؛
          ۲) نسخهٔ ۱۰٫۱۲ — رندر فوری تب TV با فلگ dirty (تب Live حذف شد)؛
          ۳) انتشار "Goal ⚽" روی Event Bus → پالس تأخیری مومنتوم + لینک شوت؛
          ۴) دیباگ زنجیره + لاگ Console.
        """
        try:
            # 1) ثبت قطعی Marker
            self.momentum.add_hook_goal_marker(
                team,
                match_t,
                self.half_number
            )

            clog(
                "[GoalHook→Graph] "
                f"marker appended | team={team} | "
                f"match_t={match_t:.3f} | "
                f"total_markers={self.momentum.hook_goal_marker_count()}"
            )

            # 2) نسخهٔ ۱۰٫۱۲ — درخواست رندر فوری تب TV (بدون تب Live)
            self._tv_dirty = True

        except Exception as ex:
            clog(f"[GoalHook] marker/render scheduling error: {ex}")
        try:
            ev = self.event_engine.register_goal_event(team, match_t, source="memory-hook")
            gh = dict(self._goal_hook_status)
            gh["events"] = gh.get("events", 0) + 1
            self._goal_hook_status = gh
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_REGISTERED", team=team,
                         t=(round(float(match_t), 1) if match_t is not None else None),
                         half=self.half_number,
                         goal_event_id=(ev.event_id if ev else "--"))
            self._shot_debug_push("GOAL_REGISTERED_HOOK", team=team,
                                  goal_event_id=ev.event_id,
                                  goal_match_time=match_t,
                                  half=self.half_number,
                                  chart_marker=True,
                                  linked_shot=(ev.related_event_ids[0] if ev.related_event_ids else "--"),
                                  source="memory-hook [rcx+0x158/0x15C]")
            clog(f"[GoalHook] گل {team} در {_fmt_clock(match_t)} ثبت شد — "
                  f"مارکر روی نمودار + پالس مومنتوم (مارکرهای فعال: "
                  f"{self.momentum.hook_goal_marker_count()})")
        except Exception as ex:
            clog(f"[Goal Register] {ex}")

    def _register_first_hook_goal(self, team: str, value: Optional[int], match_t: float) -> int:
        """
        نسخه ۱۰٫۳ — First-Capture Goal (تابع مستقل و صریح).

        مسئله: Goal Hook فقط وقتی می‌تواند RCX را Capture کند که دستور
        شمارندهٔ گل حداقل یک‌بار اجرا شده باشد؛ بنابراین اولین اجرای Hook
        ممکن است دقیقاً لحظهٔ «گل اول مسابقه» باشد. در این حالت Capture
        انجام می‌شود اما منطق قبلی آن را صرفاً BASELINE در نظر می‌گرفت و
        گل اول از دست می‌رفت.

        منطق دقیق (فقط برای اولین Capture موفق هر تیم در یک بازی):
            Goal Hook هنوز Capture نشده
                ↓ اولین خواندن معتبر دستور Goal (RCX Capture شد)
            مقدار فعلی Home/Away خوانده شود
                ↓
            value = 0  → هیچ گلی؛ فقط baseline اولیه (0,0)
            value = 1  → همان لحظه یک Goal واقعی برای همان تیم ثبت شود:
                          مارکر گل روی نمودار + Goal Event + Goal Momentum Pulse
            value > 1  → «اختلاف منطقی» از baseline صفر بررسی و ثبت می‌شود
                          (با سقف ایمنی MAX_GOAL_JUMP — حالت معمول و مهم 0→1 است)
                ↓
            baseline داخلی = value
                ↓
            از اینجا به بعد روال عادی Counter Tracking:
              1 → 2 = یک گل جدید    2 → 3 = یک گل جدید    ...
            (برای هر دو تیم مستقل؛ هیچ دوبار ثبت‌شدنی رخ نمی‌دهد چون
             همان افزایش 0→value فقط یک‌بار و در همین تابع ثبت می‌شود)

        بعد از reset_capture() در بازی جدید، همین منطق دوباره مسلح می‌شود
        (_gh_fc_pending در _perform_reset به True برمی‌گردد).

        خروجی: تعداد گل‌های ثبت‌شده در همین فراخوانی.
        """
        if value is None or value <= 0:
            # هر دو صفر (یا خواندن نامعتبر) → هیچ گلی ثبت نشود؛
            # Capture فقط baseline اولیه است
            clog(f"[GoalHook] First-Capture {team}={value} — بدون گل؛ "
                  "Capture به‌عنوان baseline اولیه ثبت شد")
            return 0
        n = min(int(value), GoalHooker.MAX_GOAL_JUMP)
        clog(f"[GoalHook] First-Capture Goal {team}: 0 → {value} در {_fmt_clock(match_t)} — "
              f"گل اول مسابقه همان لحظهٔ Capture ثبت می‌شود "
              f"(مارکر روی نمودار + Goal Event + Goal Momentum Pulse)")
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("GOAL_FIRST_CAPTURE", team=team, value=value, registered=n,
                     t=(round(float(match_t), 1) if match_t is not None else None))
        for _ in range(n):
            self._register_hook_goal(team, match_t)
        if int(value) > GoalHooker.MAX_GOAL_JUMP:
            clog(f"[GoalHook] ⚠ مقدار اولیهٔ {team}={value} از سقف ایمنی "
                  f"{GoalHooker.MAX_GOAL_JUMP} گذشت — {n} گل ثبت شد و "
                  f"{int(value) - n} گلِ باقی‌مانده نادیده گرفته شد (لاگ را بررسی کنید)")
        return n

    def _update_goal_hook_label(self):
        """برچسب وضعیت هوک گل روی نوار زمین (فقط در تغییر متن آپدیت می‌شود)"""
        gh = self._goal_hook_status
        if not gh["hooked"]:
            txt = "Goal Hook: INACTIVE ⚠ "
            color = "#fca311"
        elif not gh["captured"]:
            txt = "Goal Hook: INSTALLED ⏳ (انتظار write) "
            color = "#ffd166"
        else:
            txt = (f"Goal Hook: ACTIVE ✅ H:{gh['home'] if gh['home'] is not None else '-'}"
                   f" A:{gh['away'] if gh['away'] is not None else '-'} "
                   f"گل‌ها: {gh.get('events', 0)} ")
            color = "#00f5d4"
        if txt != self._goal_hook_label_txt:
            self._goal_hook_label_txt = txt
            self.lbl_goal_hook.config(text=txt, fg=color)


    def update_possession_cards(self):
        poss = self.runtime.get_core()["current_possession"]
        if poss == "Home":
            self.card_home.config(bg="#1a3828")
            self.lbl_home_team.config(bg="#1a3828")
            self.lbl_home_status.config(text=f"مالکیت: دارد ⚽ ({self.team1_side_name})", fg="#00f5d4", bg="#1a3828")
            self.card_away.config(bg="#131a28")
            self.lbl_away_team.config(bg="#131a28")
            self.lbl_away_status.config(text="مالکیت: ندارد", fg="#94a3b8", bg="#131a28")
        elif poss == "Away":
            self.card_away.config(bg="#3d1d2b")
            self.lbl_away_team.config(bg="#3d1d2b")
            self.lbl_away_status.config(text=f"مالکیت: دارد ⚽ ({self.team2_side_name})", fg="#f38ba8", bg="#3d1d2b")
            self.card_home.config(bg="#131a28")
            self.lbl_home_team.config(bg="#131a28")
            self.lbl_home_status.config(text="مالکیت: ندارد", fg="#94a3b8", bg="#131a28")


    def _team_tick(self):
        """تیک مستقل ردیاب هویت/رنگ تیم‌ها (بی‌ربط به دکمهٔ اتصال اصلی).
        نسخهٔ ۱۰٫۶ — دقیقاً طبق نیاز کاربر:
          * تا وصل‌شدن: هر ۱ ثانیه تلاش اتصال (TEAM_TRACKER_INTERVAL_MS)؛
          * بعد از وصل‌شدن: از همان لحظه به بعد خواندن «ریل‌تایم» اسلات‌ها —
            هر ۵۰ms (TEAM_LIVE_INTERVAL_MS) مثل حلقهٔ realtime_loop ابزار اصلی؛
          * در هر تیک، رنگ نمودار هم از leagues_data.json + بایت استاتیک شمارهٔ
            رنگ حل می‌شود (در صورت تغییر، نمودار و دایره‌ها به‌روز می‌شوند).
        نسخهٔ ۱۰٫۷ — اولویت ۱ در شروع دست جدید: پرچم _team_rehook_pending
        (ست‌شده در _on_new_hand_detected) ⇒ همین تیکِ ۵۰ms بعدی بلافاصله
        اسلات‌ها را دوباره می‌خواند (تشخیص میزبان/مهمان اول از همه)."""
        urgent = bool(getattr(self, "_team_rehook_pending", False))
        self._team_rehook_pending = False
        snap: Dict[str, Any] = {}
        try:
            snap = self.team_tracker.poll()
            self._apply_team_identity(snap)
            self._apply_team_colors(snap)
            if urgent:
                try:
                    self.dbg.event("TEAM_REHOOK", note="خواندن فوری اسلات‌ها در "
                                                   "شروع دست جدید (اولویت ۱)",
                                   home=str(snap.get("home")),
                                   away=str(snap.get("away")),
                                   menu=str(snap.get("menu")))
                except Exception:
                    pass
        except Exception as e:
            try:
                self.dbg.error("TEAM", f"tick error: {e}")
            except Exception:
                pass
        if self._team_loop_running:
            # ریل‌تایم بعد از اتصال / تلاش هر ۱ ثانیه تا اتصال
            interval = (TEAM_LIVE_INTERVAL_MS if snap.get("connected")
                        else TEAM_TRACKER_INTERVAL_MS)
            self.after(interval, self._team_tick)

    def _apply_team_identity(self, snap: Dict[str, Any]):
        """Renders the logos in the home/away slots (GUI build). If no valid
        team selection has been seen yet (state 100) or the team image is
        not in Football_Database, the slot keeps its «میزبان»/«مهمان»
        fallback text. v2.0.6 — identity changes are printed to stdout so
        backend_log.txt shows exactly WHEN the crests became known."""
        for side in ("home", "away"):
            ident = snap.get(side)
            if ident != self._team_ident_last.get(side):
                self._team_ident_last[side] = ident
                self._tv_dirty = True
                try:
                    print(f"[TEAM IDENT] {side} = {ident}", flush=True)
                except Exception:
                    pass
        if ImageTk is None:
            return
        for side, slot, fallback in (("home", self.lbl_home_logo, "میزبان"),
                                     ("away", self.lbl_away_logo, "مهمان")):
            ident = snap.get(side)
            path = self.team_tracker.logo_path_for(ident)
            if path == self._team_logo_path[side]:
                continue   # بدون تغییر — مثل کش تصویر ابزار اصلی
            photo = None
            if path:
                try:
                    img = Image.open(path)
                    img.thumbnail(TEAM_LOGO_SLOT_PX, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                except Exception:
                    photo = None
            if photo is not None:
                self._team_logo_photo[side] = photo       # جلوگیری از Garbage Collection
                self._team_logo_path[side] = path
                slot.config(image=photo, text="",
                            width=TEAM_LOGO_SLOT_PX[0], height=TEAM_LOGO_SLOT_PX[1])
                try:
                    self.dbg.event("TEAM_LOGO", side=side, ident=str(ident))
                except Exception:
                    pass
            else:
                self._team_logo_photo[side] = None
                self._team_logo_path[side] = None
                slot.config(image="", text=fallback,
                            width=TEAM_LOGO_SLOT_TEXT_W, height=TEAM_LOGO_SLOT_TEXT_H)

    def _apply_team_colors(self, snap: Dict[str, Any]):
        """حل رنگ هر تیم (قوانین ۱..۶ بخش ۲۶-ب) و اعمال آن:
          * self._chart_colors ⇒ در رندر بعدی نمودار (هر ۱۰۰ms) اعمال می‌شود؛
          * دایره‌های کنار نام تیم: یک دایره (رنگ انتخابی) یا در حالت تعویض
            رنگ، دو دایره (رنگ اصلی + رنگ تعویضی)؛
          * تغییرات در momentum_debug_log.txt هم ثبت می‌شود (TEAM_COLOR)."""
        try:
            idx = snap.get("color_idx") or {}
            dec = self.team_colors.resolve(snap.get("home"), idx.get("home"),
                                           snap.get("away"), idx.get("away"))
        except Exception as ex:
            try:
                self.dbg.error("TEAMCOLOR", f"resolve error: {ex}")
            except Exception:
                pass
            return
        sig = (dec["home"]["final"], dec["home"]["original"],
               dec["away"]["final"], dec["away"]["original"])
        if sig == self._team_color_sig:
            return   # بدون تغییر — رندر مجدد لازم نیست
        self._team_color_sig = sig
        for side in ("home", "away"):
            ch = dec[side]
            self._team_color_state[side] = ch
            self._chart_colors[side] = _rgb_to_hex(ch["final"])
        self._refresh_color_dots()
        try:
            self.dbg.event("TEAM_COLOR",
                           home=_rgb_to_hex(dec["home"]["final"]),
                           away=_rgb_to_hex(dec["away"]["final"]),
                           home_replaced=str(dec["home"]["replaced"]),
                           away_replaced=str(dec["away"]["replaced"]),
                           home_ident=str(snap.get("home")),
                           away_ident=str(snap.get("away")),
                           color_idx=str(snap.get("color_idx")))
        except Exception:
            pass

    def _refresh_color_dots(self):
        """دایرهٔ رنگ کنار هر تیم (قانون ۴):
          * حالت عادی: یک دایره — رنگ انتخاب‌شدهٔ نمودار (حاشیهٔ طلایی)؛
          * حالت تعویض (قانون ۲/۳): دو دایره — رنگ اصلی (حاشیهٔ خاکستری)
            + رنگ تعویضی که کد انتخاب کرده (حاشیهٔ طلایی)."""
        for side, canvas in (("home", getattr(self, "cvs_home_colors", None)),
                             ("away", getattr(self, "cvs_away_colors", None))):
            if canvas is None:
                continue
            try:
                st = self._team_color_state[side]
                canvas.delete("all")
                d = TEAM_COLOR_DOT_PX
                y = max(1, (TEAM_COLOR_DOT_H - d) // 2)
                x = 1
                if st.get("replaced") and st.get("original"):
                    canvas.config(width=(d + 6) * 2 + 2)
                    canvas.create_oval(x, y, x + d, y + d,
                                       fill=_rgb_to_hex(st["original"]),
                                       outline="#7f8fa6", width=1)
                    x += d + 6
                else:
                    canvas.config(width=d + 2)
                canvas.create_oval(x, y, x + d, y + d,
                                   fill=_rgb_to_hex(st["final"]),
                                   outline="#ffd166", width=2)
            except Exception:
                pass


    def _shot_debug_push(self, stage: str, **kw):
        """لایه دیباگ زنجیره شوت — Worker/ShotEngine → UI (Thread-safe via deque)"""
        try:
            self.shot_debug_log.append({"wall": time.time(), "stage": stage, **kw})
        except Exception:
            pass

    @staticmethod
    def _shot_trigger_decision(prev_baseline: Optional[int], shot_cnt: Optional[int]):
        """
        تصمیم تریگر شوت از شمارندهٔ «سراسری» — دقیقاً منطق ابزار مستقل کاربر:
          * baseline None        → ثبت baseline (بدون تریگر)
          * shot_cnt < baseline  → RESET (نیمه دوم/ری‌استارت؛ بدون تریگر)
          * shot_cnt > baseline  → TRIGGER (جهش = یک یا چند شوت جدید)
          * برابر / None         → بدون تغییر
        خروجی: (baseline جدید، رخداد) که رخداد ∈ {None, 'BASELINE', 'RESET', 'TRIGGER'}
        نکتهٔ کلیدی: این تابع به مالکیت کاری ندارد؛ مالکیت هرگز baseline را
        بازنویسی نمی‌کند — رفع کامل باگ بلعیده‌شدن تریگر در نسخه ۲.
        """
        if shot_cnt is None:
            return prev_baseline, None
        if prev_baseline is None:
            return shot_cnt, "BASELINE"
        if shot_cnt < prev_baseline:
            return shot_cnt, "RESET"
        if shot_cnt > prev_baseline:
            return shot_cnt, "TRIGGER"
        return prev_baseline, None

    def _step_shot_tracking(self, burst: int = 0) -> Optional[ShotEventData]:
        """
        یک یا چند گام محدود از ره‌گیری پرواز شوت.
        burst > 0: تا burst گام با فاصلهٔ ~12ms اجرا می‌شود (شبیه‌سازی حلقهٔ
        فشردهٔ ~15ms ابزار مستقل) — فقط وقتی ره‌گیری فعال است؛ در مجموع
        چند صد میلی‌ثانیه بیشتر stall نمی‌شود و چون decay بر پایهٔ MATCH
        TIME است، ریاضی مومنتوم ذره‌ای تحت تأثیر قرار نمی‌گیرد.
        """
        if self.shot_engine.state != "TRACKING":
            return None
        shot_data = None
        steps = max(1, int(burst))
        for _ in range(steps):
            shot_data = self.shot_engine.update_tracking(self.engine)
            if shot_data is not None:
                break
            time.sleep(0.012)
        return shot_data

    def _register_shot_data(self, shot_data: ShotEventData):
        """ثبت ShotEventData روی Event Bus + زنجیرهٔ [SHOT] + کارت UI
        نسخهٔ ۱۰٫۱۴ — Dedup «فقط» با شناسهٔ کاندید (۱ افزایش شمارنده = ۱ ثبت):
          * گارد هندسی ۱۰٫۱۲ (تیم/زننده/مکان/۱ ثانیه) حذف شد — دو شوت واقعیِ
            پشت‌سرهم (مثلاً ریباند) دیگر حذف نمی‌شوند؛
          * مسیر کامل تضمین می‌شود:
            ShotEventData → register_shot_event() → Momentum Impact → Threat
            → UI Shot List — هر مرحله با لاگ [SHOT] و شمارندهٔ آماری."""
        try:
            cand_id = getattr(shot_data, "candidate_id", None)
            if cand_id is not None:
                if cand_id in self._registered_shot_ids:
                    self.shot_engine._stat("duplicates")
                    self._shot_debug_push("DUP_SUPPRESSED", team=shot_data.team,
                                          candidate_id=cand_id,
                                          shot_match_time=shot_data.match_time,
                                          shooter_seat=shot_data.shooter_seat,
                                          outcome=shot_data.outcome,
                                          note="همان کاندید شمارنده قبلاً ثبت شده — ثبت دوم حذف شد")
                    return
                self._registered_shot_ids.add(cand_id)
                self._registered_shot_order.append(cand_id)
                while len(self._registered_shot_order) > ShotConfig.SHOT_FINALIZED_KEEP:
                    _old = self._registered_shot_order.popleft()
                    self._registered_shot_ids.discard(_old)
            self.event_engine.register_shot_event(shot_data)
            self.shot_engine._stat("events_registered")
            self._shot_debug_push("SHOT_REGISTERED", team=shot_data.team,
                                  shot_event_id=shot_data.event_id,
                                  candidate_id=cand_id,
                                  shot_match_time=shot_data.match_time,
                                  shooter_seat=shot_data.shooter_seat,
                                  shot_type=shot_data.primary_type,
                                  outcome=shot_data.outcome,
                                  pre_threat=shot_data.pre_shot_threat,
                                  final_threat=shot_data.final_threat,
                                  shot_engine_state=self.shot_engine.state)
            # --- Momentum Impact (تضمین مسیر کامل مشخصات کاربر) ---
            imp = self.momentum.get_impact(shot_data.event_id)
            if imp is not None:
                self.shot_engine._stat("threats_created")
                self._shot_debug_push("THREAT_CREATED", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      momentum_impact=f"{imp.final_impact:+.1f}",
                                      note="Impact مومنتوم برای شوت ساخته شد")
            else:
                self._shot_debug_push("THREAT_MISSING", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      note="Impact یافت نشد (بررسی شود)")
            # --- UI Shot List ---
            self._ui_post(self.update_shot_card, shot_data)
            self.shot_engine._stat("ui_added")
            self._shot_debug_push("UI_ADDED", team=shot_data.team,
                                  shot_event_id=shot_data.event_id,
                                  candidate_id=cand_id,
                                  note="شوت به لیست UI اضافه شد")
        except Exception as ex:
            clog(f"[Shot Register] {ex}")

    def _timer_rebirth_tick(self, total_t: Optional[float], now_wall: float):
        """
        نیاز صریح کاربر: «وقتی تایمر بازی به هر دلیلی صفر شد و ثانیه/دقیقه
        شمار شروع به بالا رفتن کردند یعنی شروع دست جدید — چه بازی قبلی تمام
        شده باشد چه نشده. کد باید خیلی سریع تشخیص بدهد و هوک‌ها را در کسری
        از ثانیه حذف و دوباره هوک کند.»

        ماشین حالت سبک (هر تیک Worker ~۱۵ms ⇒ تأخیر تشخیص < ۵۰ms):
          * تایمر ≤ TRB_ZERO_T  ⇒ مسلح (تایمر صفر دیده شد)
          * مسلح و تایمر > TRB_RISE_T ⇒ شروع به بالا رفتن ⇒ FIRE + Disarm
        نیمهٔ دوم از ۴۵:۰۰ شروع می‌شود (دقیقه‌شمار ۴۵ نه صفر) ⇒ هرگز FIRE
        نمی‌شود؛ خنک‌کنندهٔ مشترک با Watchdog ۱۰٫۳ از ریست دوبله جلوگیری
        می‌کند (هر دو مسیر _last_auto_reset_wall را به‌روز می‌کنند).
        """
        if total_t is None:
            return
        try:
            t = float(total_t)
        except (TypeError, ValueError):
            return
        if t <= TRB_ZERO_T:
            if not self._trb_armed:
                self._trb_armed = True
                _d = getattr(self, "dbg", None)
                if _d:
                    _d.event("TIMER_ZERO_ARMED", t=round(t, 2),
                             note="تایمر صفر دیده شد — انتظار شروع به بالا رفتن")
                # --- نسخهٔ ۱۰٫۱۸ — مشخصات کاربر: «به محض اینکه تایمر صفر
                # شد، هوک جدید انجام بشه تا آدرس جدید کشف بشه» — چرخهٔ شکار
                # آدرس مالکیت دقیقاً در لحظهٔ صفر آغاز می‌شود (قبل از آن
                # خط اسمبلی دست‌نخورده است)؛ اولین capture دارای مقدار ۲
                # تأیید و هوک برداشته می‌شود.
                self._possession_begin_capture_cycle("timer-zero")
            return
        if self._trb_armed and t > TRB_RISE_T:
            self._trb_armed = False
            if ((now_wall - self._trb_last_fire_wall) < TRB_COOLDOWN_SEC
                    or (now_wall - getattr(self, "_last_auto_reset_wall", 0.0))
                    < TRB_COOLDOWN_SEC):
                return    # Watchdog/ریست خودکارِ همین حال — دوباره‌کاری ممنوع
            self._trb_last_fire_wall = now_wall
            self._on_new_hand_detected(t)

    def _possession_begin_capture_cycle(self, reason: str) -> None:
        """نسخهٔ ۱۰٫۱۸ — آغاز چرخهٔ شکار آدرس مالکیت از سمت App:
        لحظهٔ صفر تایمر (شروع بازی جدید) یا اولین PLAYING بعد از اتصال
        وسط بازی. فقط چند خط کوتاه [PossHook] — بدون لاگ اضافهٔ دیگر."""
        try:
            rep = self.engine.poss_begin_capture_cycle()
            print(f"[PossHook] چرخهٔ capture مالکیت آغاز شد ({reason}): {rep}",
                  flush=True)
        except Exception as ex:
            print(f"[PossHook] {reason}: {type(ex).__name__}: {ex}",
                  flush=True)

    def _on_new_hand_detected(self, t: float):
        """
        اقدامات شروع دست جدید — به ترتیب اولویت کاربر، در کسری از ثانیه:
          ۱) هوک تشخیص میزبان/مهمان: خواندن فوری اسلات‌ها (اولویت اول —
             بازیکن ممکن است سریع توپ را از دست بدهد)؛
          ۲) راستی‌آزمایی/نصب مجدد هر ۴ هوک (توپ/زمان/گل/مالکیت) + re-arm
             capture گل و مالکیت (آدرس‌های قبلی احتمالاً تعویض شده‌اند)؛
          ۳) ریست کامل مسابقه (نمودار/رویدادها/مارکرها/شمارنده‌ها) —
             همان مسیر _perform_reset که State Machine ۱۰٫۳ استفاده می‌کند.
        """
        _d = getattr(self, "dbg", None)
        clog(f"[NewHand] ⚡ شروع دست جدید تشخیص داده شد: تایمر {_fmt_clock(t)} "
              "— نوسازی سریع هوک‌ها (اولویت: تشخیص میزبان/مهمان)")
        # --- اولویت ۱: تشخیص میزبان/مهمان (تیک بعدیِ ۵۰ms ردیاب فوراً می‌خواند)
        self._team_rehook_pending = True
        # --- ۲/۳: نوسازی هوک‌ها + ریست کامل ---
        rep: Dict[str, str] = {}
        try:
            rep = self.engine.verify_and_repair_hooks()
        except Exception as ex:
            rep = {"error": f"{type(ex).__name__}: {ex}"}
        if _d:
            _d.event("NEW_HAND_DETECTED", t=round(float(t), 2), hooks=str(rep),
                     note="تایمر صفر→بالا رفتن؛ هوک‌ها نوسازی + مسابقه ریست شد")
        self._perform_reset(momentum_start_t=float(t))
        self._ui_post(lambda: self.lbl_status.config(
            text="وضعیت: شروع دست جدید — هوک‌ها نوسازی شدند 🔄", fg="#00b4d8"))

    def _flag_time_drop(self, prev_t: float, new_t: float):
        """
        نسخه ۳ — افت بزرگ زمان بازی «فقط علامت می‌خورد»، هیچ ریست خودکاری
        اینجا انجام نمی‌شود (نمودار پایان مسابقه باید حفظ شود).
        تصمیم نهایی هنگام از سرگیری PLAYING در بخش 7.5 گرفته می‌شود:
        HT (نیمه دوم) / بازی جدید (از صفر) / حفظ نمودار.
        نسخه ۱۰٫۳ — اگر پیش‌شرط‌های HT (نیمه اول ≥ 45:00 دیده شده) برقرار
        باشد، State Machine به HALFTIME می‌رود (در انتظار از سرگیری)؛
        تأیید نهایی همچنان با قانون سخت classify_resume_after_drop است.
        """
        self._ht_pending = True
        self._ht_prev_end_t = prev_t
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("TIME_DROP_FLAGGED",
                     prev=(round(float(prev_t), 1) if prev_t is not None else None),
                     new=(round(float(new_t), 1) if new_t is not None else None),
                     half=self.half_number)
        if self.half_number == 1 and prev_t >= self.config.HT_HARD_MIN_FIRST_HALF:
            self._match_phase = MatchPhase.HALFTIME
            try:
                self.momentum.set_phase_label(MatchPhase.HALFTIME.value)  # ۱۰٫۱۵
            except Exception:
                pass
        if self.half_number == 1 and prev_t >= self.config.HT_MIN_FIRST_HALF_PLAYED:
            status_txt = "وضعیت: احتمال پایان نیمه اول — در انتظار از سرگیری بازی 🟠"
        else:
            status_txt = "وضعیت: افت زمان بازی — نمودار حفظ شد (پایان مسابقه/بازی جدید؟) 🟠"
        self._shot_debug_push("TIME_DROP_FLAGGED", team="--",
                              prev_time=prev_t, new_time=new_t,
                              half_number=self.half_number)
        self._ui_post(lambda: self.lbl_status.config(text=status_txt, fg="#fca311"))

    def request_reset(self, *args, **kwargs):
        """Original button behaviour: queue a reset + status hint."""
        self._reset_requested = True
        try:
            self.lbl_status.config(text="وضعیت: درخواست ریست ثبت شد...", fg="#fca311")
        except Exception:
            pass


    def _perform_reset(self, momentum_start_t: Optional[float] = None):
        """events / sequences / momentum history / counters / frame buffer / time state / graph"""
        # --- نسخهٔ ۱۰٫۱۱ — «ذخیرهٔ دائمی نمودارها»: آخرین نمودار بازی قبلی
        # باید قبل از پاک‌شدن تاریخچه ثبت شود (تایمر به ۰۰:۰۰ ریست شده =
        # شروع دست جدید). سپس ماشین حالت اسنپ‌شات برای بازی جدید صفر می‌شود.
        try:
            self._snapshot_finalize_previous_match()
        except Exception:
            pass
        try:
            self.snap_engine.reset_match(time.time())
            self._snap_capture_cache = {}
            # نسخهٔ ۱۰٫۲۱ — تست ۶: دفترترتیب چرخهٔ عمر برای بازی جدید از نو
            # (شمارندهٔ seq سراسری می‌ماند — شماره‌ها مثل Snapshot #42 ادامه دارند)
            self._snap_life = {}
            # v10.28 — پاک‌سازی وضعیت تراکنشی نمایش برای بازی جدید
            self._snap_end_dispatch_lvl = None
            self._snap_half_block_noted = set()
            self._snap_abandon_noted = set()
            try:
                with self._snap_show_lock:
                    self._snap_show_events.clear()
            except Exception:
                pass
        except Exception:
            pass
        # v2.0.5 — new match: the crest signal banner may fire again
        try:
            self._crest_banner_reset()
        except Exception:
            pass
        # نسخهٔ ۱۰٫۱۵ — پنجره‌های اسنپ‌شات (زنده + پیش‌ساخته) با ریست مسابقه
        # بی‌اعتبار می‌شوند
        # نسخهٔ ۱۰٫۱۹ — از Worker مستقیم به UI نمی‌رویم (حذف Tk کراس‌ترد)
        try:
            self._ui_post(self._hide_snapshot_overlay)
        except Exception:
            pass
        # نسخهٔ ۱۰٫۲۲ — [SNAPSHOT_STATE] ریست مسابقه → EMPTY
        try:
            self._snap_state_event("MATCH RESET", SnapshotState.EMPTY,
                                   key=None, extra="match reset")
        except Exception:
            pass
        # بستن اپیزود جاری بدون انتشار رخداد جدید
        self.pass_engine.reset()
        # نسخهٔ ۱۰٫۱۴ — آمار زنجیرهٔ شوت «پیش از» ریست باید ثبت/نمایش داده شود
        # (معیار پذیرش: Counter increments = Candidates ≈ Registered Events)
        try:
            _ss = dict(self.shot_engine.stats)
            if any(_ss.values()):
                self._shot_debug_push("MATCH_SHOT_STATS", team="--", **_ss)
        except Exception:
            pass
        self.shot_engine.reset()
        self.event_engine.reset()
        cur_t = momentum_start_t if momentum_start_t is not None else self.runtime.get_core()["current_match_time"]
        self.momentum.reset(cur_t)
        self.frame_buffer.clear()
        self.pass_counters = {"Home": None, "Away": None}
        # نسخه ۳: baseline سراسری شمارنده شوت (دقیقاً مثل ابزار مستقل کاربر)
        self.shot_counter_baseline: Optional[int] = None
        # نسخه ۴: baseline شمارنده‌های گل (با ریست مسابقه دوباره baseline می‌شوند)
        self.goal_counters = {"Home": None, "Away": None}
        # نسخه ۶: آزادسازی slot capture → اولین نوشتارِ گلِ بازیِ جدید،
        # ساختار آمارِ تازه را capture می‌کند (خود‌ترمیمی بازی‌های بعدی)
        try:
            self.engine.goal_hooker.reset_capture(self.engine.h_process)
        except Exception:
            pass
        # نسخه ۱۰٫۴: re-arm capture «مالکیت» — همان الگوی self-heal هوک گل.
        # بازی در بازی جدید ساختار آمار/مالکیت را جابه‌جا می‌کند؛ capture قدیمی
        # آدرس مرده را می‌خواند → رخدادها از بازی دوم به بعد قطع می‌شد.
        # نسخهٔ ۱۰٫۱۸ — re-arm هوشمند: اگر آدرس «همین بازی» چند ثانیه past
        # تأیید شده باشد، حفظ می‌شود (شروع بازی بدون قطعی مالکیت؛ رفع
        # «نمودار در دقایق ابتدایی رسم نمی‌شد»)
        _poss_cap_before = None
        try:
            _poss_cap_before = getattr(self.engine.poss_hooker, "captured_address", None)
            self.engine.rearm_possession_capture()
        except Exception:
            pass
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("MATCH_RESET",
                     t=(round(float(cur_t), 1) if cur_t is not None else None),
                     poss_cap_before=fmt_ptr(_poss_cap_before),
                     gh_rcx_before=fmt_ptr((self._goal_hook_status or {}).get("rcx")),
                     note="ریست کامل مسابقه — capture گل و مالکیت دوباره مسلح شد")
        self.current_possession = None
        # نسخهٔ ۱۰٫۱۴ — پاک‌سازی Dedup ثبت شوت برای مسابقهٔ جدید
        self._registered_shot_ids.clear()
        self._registered_shot_order.clear()
        self._last_ev_count = 0
        self._last_seq_count = 0
        self._last_imp_count = 0
        self._ui_pass_list.clear()
        self._ui_shot_list.clear()
        # نسخه ۲: ریست وضعیت نیمه / HT و ردیف‌های زندهٔ Sequences
        self.half_number = 1
        self._ht_pending = False
        self._ht_prev_end_t = 0.0
        # --- نسخه ۱۰٫۳: Match Lifecycle — شروع تمیز از HALF_1 ---
        # (HALF_1 → HT → HALF_2 → FULL_TIME | تایمر≈صفر+PLAYING → NEW_MATCH → HALF_1)
        self._match_phase = MatchPhase.HALF_1
        try:
            self.momentum.set_phase_label(MatchPhase.HALF_1.value)   # نسخهٔ ۱۰٫۱۵
        except Exception:
            pass
        self._match_seen_max_t = float(cur_t)
        # --- نسخه ۱۰٫۳: First-Capture Goal برای بازی جدید دوباره مسلح می‌شود ---
        # reset_capture بالا slotها را صفر کرد؛ اولین نوشتارِ گلِ بازیِ جدید
        # دوباره Capture می‌کند و اگر همان لحظه گل اول بود،
        # _register_first_hook_goal آن را ثبت می‌کند (هر دو تیم مستقل).
        self._gh_fc_pending = {"Home": True, "Away": True}
        _d = self._gh_diag
        _d["last_captured"] = None
        _d["last_rcx"] = None
        _d["last_home"] = None
        _d["last_away"] = None
        _d["baselined"] = {"Home": False, "Away": False}
        self._goal_hook_status = {"hooked": False, "captured": False,
                                  "secondary": False, "rcx": None,
                                  "home": None, "away": None, "events": 0}
        # --- نسخهٔ ۱۰٫۲۷ — ریست کارت قرمز: baseline/در انتظار‌ها/تبعیدشدگان
        # پاک می‌شوند (مختصات بازیکنان در بازی جدید دوباره کپچر می‌شود —
        # seatها عوض می‌شوند)؛ مارکرها با momentum.reset پاک شده‌اند.
        self._rc_state = {"baseline": None, "pending": [], "exiles": set()}
        _rc_diag = getattr(self, "_rc_diag", None)
        if isinstance(_rc_diag, dict):
            _rc_diag["n_cards"] = 0
            _rc_diag["n_attr"] = 0
            _rc_diag["n_timeout"] = 0
        self._seq_row_items.clear()
        self._seq_last_values.clear()
        self.runtime.reset()
        self.runtime.connected = True
        # --- نسخهٔ ۱۰٫۷: خنک‌کنندهٔ مشترک ریست‌های خودکار + حالت تب TV ---
        self._last_auto_reset_wall = time.time()
        self._trb_armed = False
        self._tv_dirty = True
        self._tv_max_half2_t = 0.0
        self._ui_post(self._clear_ui_lists)

    def _clear_ui_lists(self):
        self.tree_ev.delete(*self.tree_ev.get_children())
        self.tree_seq.delete(*self.tree_seq.get_children())
        self.tree_pass.delete(*self.tree_pass.get_children())
        self.tree_shot.delete(*self.tree_shot.get_children())
        self.tree_debug.delete(*self.tree_debug.get_children())
        self._seq_row_items.clear()
        self._seq_last_values.clear()
        self.lbl_card_title.config(text="نوع پاس: در انتظار شروع بازی...")
        self.lbl_card_threat.config(text="Threat Score: --")
        self.lbl_card_outcome.config(text="")
        self.lbl_shot_title.config(text="نوع شوت: در انتظار ثبت نخستین شوت...")
        self.lbl_shot_threats.config(text="Pre Threat: -- | Final Threat: --")
        self.lbl_shot_outcome.config(text="نتیجه: --")
        # نسخهٔ ۱۰٫۱۲ — تب Live حذف شد؛ فقط رندر مجدد تب TV لازم است
        self._tv_dirty = True
        self.lbl_status.config(text="وضعیت: ریست کامل شد — در انتظار بازی 🟠", fg="#fca311")


    def on_close(self):
        # نسخهٔ ۱۰٫۱۸ — توالی بستن امن (رفع فریز و خطاهای TclError هنگام خروج):
        #   ۱) پرچم _closing بالاتر از همه — هر callback صف‌شده نادیده گرفته می‌شود
        #   ۲) توقف حلقه‌ها (Worker/اتصال خودکار/تیم‌ها/انیمیشن)
        #   ۳) صبر کوتاه برای پایان Worker (نبودِ after() همزمان با destroy)
        #   ۴) بستن پنجره‌های اسنپ‌شات/مودال و هوک‌ها، سپس destroy
        self._closing = True
        self.is_monitoring = False
        # نسخهٔ ۱۰٫۷ — توقف حلقهٔ اتصال خودکار
        self._auto_connect_running = False
        # نسخه ۱۰٫۵ — توقف حلقهٔ مستقل تیم‌ها و بستن هندل read-only آن
        self._team_loop_running = False
        # نسخهٔ ۱۰٫۱۶ — توقف ترد انیمیشن اسنپ‌شات
        try:
            self._snap_anim_gen += 1
            self._snap_anim_alive = False
        except Exception:
            pass
        # نسخهٔ ۱۰٫۱۸ — انتظار کوتاه برای پایان Worker (حداکثر ~۲ تیک حلقه)
        _wt = getattr(self, "_worker_thread", None)
        if _wt is not None:
            try:
                if _wt.is_alive():
                    _wt.join(timeout=1.5)
            except Exception:
                pass
        # نسخهٔ ۱۰٫۱۸ — لغو «همهٔ» تایمرهای after باقی‌مانده تا هیچ callback
        # بعد از destroy اجرا نشود (رفع خطاهای «invalid command name»)
        try:
            _ids = self.tk.splitlist(self.tk.call("after", "info"))
            for _aid in _ids:
                try:
                    self.after_cancel(_aid)
                except Exception:
                    pass
        except Exception:
            pass
        # نسخهٔ ۱۰٫۱۱ — بستن پنجرهٔ اسنپ‌شات و مودال تنظیمات
        try:
            self._hide_snapshot_overlay()
        except Exception:
            pass
        # نسخهٔ ۱۰٫۲۳ — خاموشی تمیز Renderer GPU (ترد + Context + GLFW)
        try:
            _gpu = getattr(self, "_snap_gpu", None)
            if _gpu is not None:
                _gpu.shutdown(timeout=1.5)
                self._snap_gpu = None
        except Exception:
            pass
        _dlg = getattr(self, "_snap_dlg", None)
        if _dlg is not None:
            try:
                _dlg.destroy()
            except Exception:
                pass
        try:
            self.team_tracker.close()
        except Exception:
            pass
        try:
            self.engine.cleanup()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass

    def _save_shown_chart_copy(self, key, path=""):
        """NEW SETTING — "permanently save the charts": when
        ModsConfig.json -> mods -> Match Momentum -> mm_save_shown_charts is
        true, EVERY chart prepared for display (h1/h2/et target minutes and
        the end-of-match charts) is copied into Momentum_Saves/ with a
        per-match descriptive name (match start stamp + team ids + key).
        Runs on the Worker thread right after the show request is queued, so
        the file exists even if the on-screen show later fails and retries
        (same target name => overwritten, never duplicated per key).
        The existing permanent_save behaviour (last chart of the match) is
        unchanged and independent."""
        try:
            if not self.snap_engine.s.get("save_shown_charts"):
                return
            p = path
            if not p or not os.path.isfile(p):
                p = self._snapshot_tmp_path(key)
            img = self._snap_capture_cache.get(key)
            if not os.path.isfile(p) and img is not None:
                try:
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    img.save(p, format="PNG")
                except Exception:
                    return
            if not os.path.isfile(p):
                return
            save_dir = os.path.join(self._script_dir, TV_SNAP_SAVE_DIRNAME)
            os.makedirs(save_dir, exist_ok=True)
            w = self.snap_engine.match_start_wall
            stamp = (time.strftime("%Y-%m-%d_%H-%M", time.localtime(w)) if w
                     else time.strftime("%Y-%m-%d_%H-%M"))
            names = {}
            for side in ("home", "away"):
                ident = self._team_ident_last.get(side)
                names[side] = _pt_team_label(ident, side)   # [PT v2.3.0]
            key_norm = {"h1": "H1", "h2": "H2", "et": "ET", "end": "END",
                        "end90": "END90", "end120": "END120"}.get(
                            str(key), str(key).upper())
            base = (f"momentum_{stamp}_{names['home']}_vs_{names['away']}"
                    f"_{key_norm}")
            dst = os.path.join(save_dir, base + ".png")
            with open(p, "rb") as _fsrc:
                _data = _fsrc.read()
            with open(dst, "wb") as _fdst:
                _fdst.write(_data)
            clog(f"[Momentum] chart saved permanently: "
                 f"{os.path.basename(dst)}")
        except Exception:
            pass

# =====================================================================
# نقطه ورود برنامه
# =====================================================================
# =====================================================================
# ۲۷. تست اجباری End-to-End (نسخه ۲ — بند ۲۱)
# ---------------------------------------------------------------------
# بدون نیاز به بازی واقعی؛ جریان رویداد مصنوعی استاندارد به موتور
# Momentum تزریق می‌شود و رفتار زیر asserts می‌گردد:
#   ✔ رخدادهای Home به بالا / Away به پایین
#   ✔ decay نمایی هر رخداد (فقط Match Time)
#   ✔ Goal Marker دقیقاً روی t_goal و Goal Peak با تأخیر GOAL_PEAK_DELAY
#   ✔ کنترل دوبار شماری Chance + Shot لینک‌شده (SHOT_LINKED_CHANCE_RATIO)
#   ✔ نمودار هرگز به‌صورت تصادفی علامت عوض نمی‌کند
#   ✔ Gaussian smoothing واقعی (لایه نمایش)
#   ✔ Pause (زمان ثابت) → بدون نمونه/decay جدید
#   ✔ شکاف HT (نمونه‌های NaN + offset نیمه دوم)
# اجرا:  python FL_2026_Live_Match_Momentum_v9.py --selftest
# =====================================================================
