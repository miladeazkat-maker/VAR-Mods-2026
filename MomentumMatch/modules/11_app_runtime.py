    def _graph_loop(self):
        if not self.is_monitoring or getattr(self, "_closing", False):
            return
        # versiontechnical note 10technical note12 — render livetechnical note technical note TV (when technical note technical note technical note‌technical noteandtechnical note only with change andtechnical note)
        try:
            self._refresh_tv_chart()
        except Exception as ex:
            clog(f"[TVGraph] {ex}")
        # version 2: Live Update chain‌technical note possession (same Row technical note technical note‌technical noteandtechnical note)
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

        heads = {"id": "#", "time": "time", "team": "team", "type": "textandtext text", "rel": "textwithtext",
                 "conf": "text", "raw": "Raw Score", "impact": "Momentum Impact",
                 "pos": "coordinates (X, Z)", "related": "andtext to ID", "tags": "textortext and specification"}
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
            t_str = "Home" if ev.team == "Home" else "Away"
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
            f"textandtext text: {ev.event_type}",
            f"team: {'Home' if ev.team == 'Home' else 'Away'}",
            f"match time: {m:02d}:{s:02d}",
            f"Reliability: {ev.reliability.value}",
            f"Confidence: {int(ev.confidence * 100)}%",
        ]
        if imp:
            # version 2: for Goal Pulse from technical note passtechnical note technical note istechnical note technical note‌technical noteandtechnical note (technical note decay technical note)
            if imp.is_goal_pulse:
                f = self.momentum.goal_response_factor(imp, cur_t)
                phase = self.momentum.goal_pulse_phase(imp, cur_t)
                gm, gs = divmod(int(imp.goal_time), 60)
                pm, ps = divmod(int(imp.peak_time), 60)
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Goal Pulse: {phase} | factor text: {f:.3f}",
                    f"Goal Time: {gm:02d}:{gs:02d} → Peak Time: {pm:02d}:{ps:02d}",
                    f"Contribution moment‌text: {imp.final_impact * f:+.2f}",
                ]
            else:
                decay = self.momentum.decay_factor(max(0.0, cur_t - imp.match_time))
                lines += [
                    f"Raw Score: {imp.raw_threat:.1f}",
                    f"Base Weight: {imp.base_weight:.1f}",
                    f"Momentum Impact: {imp.final_impact:+.2f}",
                    f"Decay text: {decay:.3f}",
                    f"Contribution moment‌text: {imp.final_impact * decay:+.2f}",
                ]
            if imp.note:
                lines.append(f"textis score: {imp.note}")
        else:
            lines.append("Momentum Impact: -- (without score)")
        if ev.related_event_ids:
            lines.append(f"textandtextdatatext andtext: {', '.join(map(str, ev.related_event_ids))}")
        if ev.metadata:
            md_str = ", ".join(f"{k}={v}" for k, v in ev.metadata.items())
            lines.append(f"textuntiltextuntil: {md_str}")
        lines.append(f"text‌text: {', '.join(ev.tags)}")
        messagebox.showinfo(f"textortext text #{ev.event_id}", "\n".join(lines))


    def build_sequences_tab(self, parent):
        seq_cols = ("id", "team", "dur", "prog", "passes", "shots", "chances", "f3rd", "box", "status")
        self.tree_seq = ttk.Treeview(parent, columns=seq_cols, show="headings", height=16)
        heads = {"id": "Seq #", "team": "team", "dur": "text (s)", "prog": "textandtext (m)",
                 "passes": "count pass", "shots": "count shot", "chances": "text",
                 "f3rd": "andtextandtext to third", "box": "andtextandtext to textandtext", "status": "andtext"}
        widths = {"id": 55, "team": 70, "dur": 75, "prog": 85, "passes": 85, "shots": 85,
                  "chances": 65, "f3rd": 105, "box": 105, "status": 170}
        for c in seq_cols:
            self.tree_seq.heading(c, text=heads[c])
            self.tree_seq.column(c, width=widths[c], anchor="center")
        # color technical note for chain‌technical note active (Live)
        self.tree_seq.tag_configure("active", foreground="#00f5d4")
        self.tree_seq.tag_configure("ended", foreground="#c8d3e0")
        self.tree_seq.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(parent, orient="vertical", command=self.tree_seq.yview)
        sb.pack(side="right", fill="y")
        self.tree_seq.configure(yscrollcommand=sb.set)


    def update_ui_sequences(self, seqs: List[PossessionSequence]):
        """
        version 2 — Live Update real:
        text Sequence only text withtext Row text‌text (insert) and until match end «same Row»
        with tree.item(values=...) to‌textandtext text‌textandtext text text text text
        text‌textandtext. chaintext active text display data text‌textandtext and text from text text text
        (duration / ending_reason) in same Row register text‌text.
        """
        for s in seqs:
            t_str = "Home" if s.team == "Home" else "Away"
            if s.is_active:
                status = "active ⏳"
                tag = "active"
            else:
                status = s.ending_reason or "end"
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

        # --- card latest pass ---
        card_pass = tk.LabelFrame(wrap, text="  text text latest pass  ",
                                  font=("Segoe UI", 10, "bold"), fg="#00f5d4", bg="#111722", padx=10, pady=5)
        card_pass.pack(fill="x", padx=10, pady=(8, 3))

        r1 = tk.Frame(card_pass, bg="#111722")
        r1.pack(fill="x")
        self.lbl_card_title = tk.Label(r1, text="textandtext pass: in text start withtext...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#111722")
        self.lbl_card_title.pack(side="left")
        self.lbl_card_threat = tk.Label(r1, text="Threat Score: --", font=("Segoe UI", 12, "bold"), fg="#ff70a6", bg="#111722")
        self.lbl_card_threat.pack(side="right", padx=10)
        self.lbl_card_outcome = tk.Label(r1, text="", font=("Segoe UI", 11, "bold"), bg="#111722")
        self.lbl_card_outcome.pack(side="right")

        r2 = tk.Frame(card_pass, bg="#182030", padx=8, pady=4)
        r2.pack(fill="x", pady=3)
        self.lbl_players = tk.Label(r2, text="text: -- ➔ text: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#182030")
        self.lbl_players.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_flight_time = tk.Label(r2, text="time pass: -- second", font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#182030")
        self.lbl_flight_time.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_confidence = tk.Label(r2, text="text text: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#182030")
        self.lbl_confidence.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_tags = tk.Label(r2, text="andtext‌text: --", font=("Segoe UI", 9), fg="#f4a261", bg="#182030")
        self.lbl_tags.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_metrics = tk.Label(r2, text="length: -- | textandtext lengthtext X: -- | textandtext widthtext Z: -- | textandtext height Y: --",
                                    font=("Segoe UI", 8), fg="#94a3b8", bg="#182030")
        self.lbl_metrics.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- card latest shot ---
        card_shot = tk.LabelFrame(wrap, text="  text text‌text latest shot  ",
                                  font=("Segoe UI", 10, "bold"), fg="#ff3366", bg="#0f1422", padx=10, pady=5)
        card_shot.pack(fill="x", padx=10, pady=3)

        s1 = tk.Frame(card_shot, bg="#0f1422")
        s1.pack(fill="x")
        self.lbl_shot_title = tk.Label(s1, text="textandtext shot: in text register text shot...",
                                       font=("Segoe UI", 12, "bold"), fg="#ffd166", bg="#0f1422")
        self.lbl_shot_title.pack(side="left")
        self.lbl_shot_threats = tk.Label(s1, text="Pre Threat: -- | Final Threat: --", font=("Segoe UI", 12, "bold"), fg="#ff0055", bg="#0f1422")
        self.lbl_shot_threats.pack(side="right", padx=10)
        self.lbl_shot_outcome = tk.Label(s1, text="result: --", font=("Segoe UI", 11, "bold"), fg="#00f5d4", bg="#0f1422")
        self.lbl_shot_outcome.pack(side="right", padx=15)

        s2 = tk.Frame(card_shot, bg="#172033", padx=8, pady=4)
        s2.pack(fill="x", pady=3)
        self.lbl_shooter = tk.Label(s2, text="text: --", font=("Segoe UI", 9, "bold"), fg="#ffffff", bg="#172033")
        self.lbl_shooter.grid(row=0, column=0, sticky="w", padx=6, pady=1)
        self.lbl_speed = tk.Label(s2, text="text text ball: -- km/h", font=("Segoe UI", 9, "bold"), fg="#f72585", bg="#172033")
        self.lbl_speed.grid(row=0, column=1, sticky="w", padx=6, pady=1)
        self.lbl_ontarget = tk.Label(s2, text="andtext textandtext: --", font=("Segoe UI", 9, "bold"), fg="#4cc9f0", bg="#172033")
        self.lbl_ontarget.grid(row=0, column=2, sticky="w", padx=6, pady=1)
        self.lbl_shot_conf = tk.Label(s2, text="text: --", font=("Segoe UI", 9), fg="#a8dadc", bg="#172033")
        self.lbl_shot_conf.grid(row=0, column=3, sticky="w", padx=6, pady=1)
        self.lbl_shot_geom = tk.Label(s2, text="distance shot: -- | textandtext text: -- | distance with post: -- | textandtext height: --",
                                      font=("Segoe UI", 8), fg="#94a3b8", bg="#172033")
        self.lbl_shot_geom.grid(row=1, column=0, columnspan=4, sticky="w", padx=6, pady=1)

        # --- technical notefirst untiltechnical note pass and shot ---
        tables = tk.Frame(wrap, bg="#090c12")
        tables.pack(fill="both", expand=True, padx=10, pady=6)

        left = tk.LabelFrame(tables, text="  📋 untiltext pass‌text (text‌totaltext = textortext)  ",
                             font=("Segoe UI", 9, "bold"), fg="#00f5d4", bg="#090c12")
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        pcols = ("id", "time", "team", "type", "threat", "conf", "passer", "receiver", "dist", "status")
        self.tree_pass = ttk.Treeview(left, columns=pcols, show="headings", height=9)
        pheads = {"id": "#", "time": "time", "team": "team", "type": "textandtext pass", "threat": "Threat",
                  "conf": "text", "passer": "text", "receiver": "text", "dist": "length (m)", "status": "result"}
        for c in pcols:
            self.tree_pass.heading(c, text=pheads[c])
            self.tree_pass.column(c, width=78, anchor="center" if c != "type" else "w")
        self.tree_pass.pack(side="left", fill="both", expand=True)
        sb1 = ttk.Scrollbar(left, orient="vertical", command=self.tree_pass.yview)
        sb1.pack(side="right", fill="y")
        self.tree_pass.configure(yscrollcommand=sb1.set)
        self.tree_pass.bind("<Double-1>", self.on_pass_double_click)

        right = tk.LabelFrame(tables, text="  🎯 untiltext shot‌text (text‌totaltext = textortext)  ",
                              font=("Segoe UI", 9, "bold"), fg="#ff3366", bg="#090c12")
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        scols = ("id", "time", "team", "type", "pre", "final", "outcome", "speed", "dist", "conf")
        self.tree_shot = ttk.Treeview(right, columns=scols, show="headings", height=9)
        sheads = {"id": "#", "time": "time", "team": "team", "type": "textandtext shot", "pre": "Pre Thr",
                  "final": "Final Thr", "outcome": "result", "speed": "text", "dist": "distance", "conf": "text"}
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
        team_str = "Home" if ev.team == "Home" else "Away"
        out_txt = "successful ✅" if ev.is_success else "failed / text ❌"
        out_col = "#2ecc71" if ev.is_success else "#e63946"

        self.lbl_card_title.config(text=f"textandtext pass: {ev.pass_type} ({team_str})")
        self.lbl_card_threat.config(text=f"Threat Score: {ev.threat_score}/100")
        self.lbl_card_outcome.config(text=out_txt, fg=out_col)

        p_str = f"text {ev.passer_seat}" if ev.passer_seat else "nametext"
        r_str = f"text {ev.receiver_seat}" if ev.receiver_seat else "nametext"
        self.lbl_players.config(text=f"text: {p_str} ➔ text: {r_str}")
        self.lbl_flight_time.config(text=f"time textandfrom ball: {ev.flight_time:.2f} second")
        self.lbl_confidence.config(text=f"text text: {int(ev.confidence * 100)}%")
        self.lbl_tags.config(text=f"andtext‌text: {', '.join(ev.tags) if ev.tags else 'text'}")
        self.lbl_metrics.config(
            text=(f"length: {ev.distance:.1f}m | textandtext lengthtext X: {ev.forward_progress:+.1f}m | "
                  f"textandtext widthtext Z: {ev.lateral_progress:.1f}m | textandtext height Y: {ev.max_height:.2f}m")
        )

        m, s = divmod(int(ev.match_time), 60)
        self.tree_pass.insert("", 0, values=(
            ev.event_id, f"{m:02d}:{s:02d}", team_str, ev.pass_type,
            f"{ev.threat_score}", f"{int(ev.confidence * 100)}%",
            p_str, r_str, f"{ev.distance:.1f}",
            "successful" if ev.is_success else "failed"
        ))


    def update_shot_card(self, ev: ShotEventData):
        self.runtime.set_shot(ev)
        self._ui_shot_list.append(ev)
        team_str = "Home" if ev.team == "Home" else "Away"

        self.lbl_shot_title.config(text=f"textandtext shot: {ev.primary_type} ({team_str})")
        self.lbl_shot_threats.config(text=f"Pre Thr: {ev.pre_shot_threat} | Final Thr: {ev.final_threat}")

        outcome_color = "#00f5d4"
        if "text" in ev.outcome: outcome_color = "#2ecc71"
        elif "post" in ev.outcome: outcome_color = "#fca311"
        elif "text" in ev.outcome: outcome_color = "#e63946"
        self.lbl_shot_outcome.config(text=f"result: {ev.outcome}", fg=outcome_color)
        self.lbl_shooter.config(text=f"text: text {ev.shooter_seat} ({team_str})")

        sp_txt = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "-- (text textto)"
        self.lbl_speed.config(text=f"text text ball: {sp_txt}")
        self.lbl_ontarget.config(
            text=f"andtext: {'in textandtext ✅' if ev.is_on_target else 'text textandtext ❌'}",
            fg="#2ecc71" if ev.is_on_target else "#e63946"
        )
        self.lbl_shot_conf.config(text=f"text: {int(ev.confidence * 100)}%")
        sign_desc = "inside" if ev.woodwork_distance < 0 else "text"
        self.lbl_shot_geom.config(
            text=(f"distance: {ev.distance_to_goal:.1f}m | textandtext: {ev.goal_angle_deg:.1f}° | "
                  f"post: {ev.woodwork_distance:+.2f}m ({sign_desc}) | textandtext height: {ev.max_height:.2f}m | "
                  f"text text: {ev.defenders_in_corridor}")
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
            f"pass number: {ev.event_id}\n"
            f"match time: {m:02d}:{s:02d}\n"
            f"text textandfrom ball: {ev.flight_time:.2f} second\n"
            f"team: {ev.team}\n"
            f"text: text {ev.passer_seat} ➔ text: text {ev.receiver_seat}\n\n"
            f"textandtext pass: {ev.pass_type}\n"
            f"text text (Threat): {ev.threat_score}/100\n"
            f"text text: {int(ev.confidence * 100)}%\n\n"
            f"textdecrease pass: {ev.distance:.1f} m\n"
            f"textandtext lengthtext X: {ev.forward_progress:+.1f} m\n"
            f"textto‌text widthtext Z: {ev.lateral_progress:.1f} m\n"
            f"textandtext height Y: {ev.max_height:.2f} m\n"
            f"result pass: {'successful ✅' if ev.is_success else 'text text / failed ❌'}\n\n"
            f"text pass: ({ev.start_ball[0]:.1f}, {ev.start_ball[1]:.1f}) ➔ text: ({ev.end_ball[0]:.1f}, {ev.end_ball[1]:.1f})"
        )
        messagebox.showinfo(f"specification complete pass #{ev.event_id}", msg)


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
        sign_str = "inside textandtext" if ev.woodwork_distance < 0 else "text textandtext"
        sp_str = f"{ev.max_speed_kmh:.1f} km/h" if ev.speed_valid else "nametext / text textto"
        msg = (
            f"🎯 shot number: {ev.event_id}\n"
            f"match time: {m:02d}:{s:02d}\n"
            f"team: {ev.team} (text {ev.shooter_seat})\n"
            f"textandtext shot: {ev.primary_type}\n"
            f"andtext‌text: {', '.join(ev.tags)}\n\n"
            f"🚀 text textto: {sp_str}\n"
            f"🎯 textandtext: {'in textandtext ✅' if ev.is_on_target else 'text from textandtext ❌'}\n"
            f"📏 distance with post: {ev.woodwork_distance:+.2f}m ({sign_str})\n"
            f"📊 result text: {ev.outcome}\n\n"
            f"🔥 Pre-Shot Threat (Opportunity Value): {ev.pre_shot_threat}/100\n"
            f"⚡ Final Threat (Momentum Impact): {ev.final_threat}/100\n"
            f"🛡️ text (Confidence): {int(ev.confidence * 100)}%\n\n"
            f"distance until inandfromtext: {ev.distance_to_goal:.1f}m | textandtext: {ev.goal_angle_deg:.1f}°\n"
            f"text text: {ev.defenders_in_corridor} | nearest text: {ev.nearest_defender_dist:.1f}m\n"
            f"text ball: {ev.curve_ratio * 100:.1f}% ({ev.curve_dir})\n"
        )
        if ev.candidate_scores:
            msg += "\nscore text:\n"
            for cand, sc in sorted(ev.candidate_scores.items(), key=lambda x: x[1], reverse=True)[:8]:
                msg += f"  - {cand}: {sc:.1f}\n"
        messagebox.showinfo(f"specification complete shot #{ev.event_id}", msg)


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
        # version 4: andtechnical note goal hook in technical note technical notewithtechnical note
        self.lbl_goal_hook_dbg = tk.Label(info, text="Goal Hook: -- | H: - A: -",
                                          font=("Consolas", 9, "bold"), fg="#a8dadc", bg="#0d111a")
        self.lbl_goal_hook_dbg.grid(row=1, column=3, sticky="w", padx=8, pady=(3, 0))

        table_wrap = tk.Frame(parent, bg="#090c12")
        table_wrap.pack(fill="both", expand=True, padx=10, pady=6)
        tk.Label(table_wrap, text="textandtext textandtext — for text text: chain Raw Threat → Base Weight → Reliability/Confidence → Final Impact → Decay → Contribution text | textandtext Goal: time text → time textandtext text (textfrom)",
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

        # --- version 2: technical note technical notewithtechnical note chain shot (Counter → Trigger → Tracking → Event → Bus) ---
        chain_wrap = tk.LabelFrame(table_wrap, text="  🔗 chain shot — Shot Counter → Engine → Event → Momentum (newtext withtext)  ",
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

        # section Debug information time
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

        # version 4: andtechnical note goal hook in technical note technical notewithtechnical note
        gh = self._goal_hook_status
        if gh["hooked"]:
            if gh["captured"]:
                dbg_txt = (f"Goal Hook: ACTIVE ✅ | H: {gh['home'] if gh['home'] is not None else '-'} "
                           f"A: {gh['away'] if gh['away'] is not None else '-'} | rcx=0x{gh['rcx']:X}"
                           if gh["rcx"] else "Goal Hook: ACTIVE ✅ | waiting write...")
                dbg_color = "#00f5d4"
            else:
                dbg_txt = "Goal Hook: INSTALLED ⏳ (in text firsttext write structure text)"
                dbg_color = "#ffd166"
            if gh["secondary"]:
                dbg_txt += " | away-write hook: YES"
        else:
            dbg_txt = "Goal Hook: INACTIVE ⚠ (register text disabled)"
            dbg_color = "#fca311"
        self.lbl_goal_hook_dbg.config(text=dbg_txt, fg=dbg_color)

        # technical noteandtechnical note Impact technical note (latest 200 technical noteandtechnical note for technical noteandtechnical note) — version 2 with technical noteandtechnical note‌technical note Linked/Goal
        with self.momentum._lock:
            impacts = list(self.momentum.impacts[-200:])
        self.tree_debug.delete(*self.tree_debug.get_children())
        for imp in impacts:
            if imp.is_goal_pulse:
                # Goal Pulse: technical noteandtechnical note from technical note passtechnical note technical note (technical note decay technical note technical note)
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

        # --- version 2: render chain shot (newtechnical note withtechnical note) ---
        try:
            lines = []
            for e in list(self.shot_debug_log)[-60:]:
                w = time.strftime("%H:%M:%S", time.localtime(e["wall"]))
                extras = ", ".join(f"{k}={v}" for k, v in e.items() if k not in ("wall", "stage"))
                lines.append(f"{w} | {e['stage']:<28} | {extras}")
            self.txt_shot_chain.config(state="normal")
            self.txt_shot_chain.delete("1.0", "end")
            body = "\n".join(reversed(lines))
            # versiontechnical note 10technical note14 — line technical note chaintechnical note shot always in withtechnical note technical noteandtechnical note technical notewithtechnical note
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
                    messagebox.showerror("Error", msg)
                except Exception:
                    pass
            clog(f"[Momentum] attach failed: {msg}")
            return
        self._begin_monitoring(msg, manual=True)

    def update_field_geometry(self, players: List[Dict]):
        # versiontechnical note 10technical note18 — guard TclError: after from technical note technical notenametechnical note callbacktechnical note
        # withtechnical note‌technical note technical notemust Errortechnical note «invalid command name» technical note
        try:
            self._update_field_geometry_impl(players)
        except tk.TclError:
            pass


    def _update_field_geometry_impl(self, players: List[Dict]):
        gk1 = next((p for p in players if p["seat"] == 1), None)
        gk12 = next((p for p in players if p["seat"] == 12), None)
        if gk1 and gk12:
            if gk1["x"] < gk12["x"]:
                self.team1_side_name = "text text (text ➔ textis)"
                self.team2_side_name = "text textis (text ⬅ text)"
                self.team1_attack_dir = 1
                info = "pitch: Home in text (text ➔) | Away in textis (text ⬅)"
            else:
                self.team1_side_name = "text textis (text ⬅ text)"
                self.team2_side_name = "text text (text ➔ textis)"
                self.team1_attack_dir = -1
                info = "pitch: Home in textis (text ⬅) | Away in text (text ➔)"
            self.lbl_field_info.config(text=info)
            self.geometry_ready = True

    def update_time_status(self, m_state: str, g_min: Optional[int], g_sec: Optional[int], total_t: float):
        """to‌textandtext card Match Time and andtext withtext (from Worker)
        versiontext 10text18 — guard TclError for text text textnametext."""
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
            self.lbl_status.config(text="andtext: match live 🟢", fg="#2ecc71")
        else:
            self.lbl_status.config(text="andtext: PAUSED / REPLAY / STOPPED ⏸", fg="#e63946")


    def _init_pipeline_health(self):
        """text‌text/counter‌text layertext detectiontext (version 10text4)"""
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
        version 10text4 — text text Worker (lightweight): to‌textandtext textortext‌text + in time duetext
        write text line Heartbeat complete + Warningtext STALE. text‌andtext exception withtext
        text‌text and text textortext original‌text text change text‌text (only text + re-arm).
        """
        try:
            dbg = getattr(self, "dbg", None)
            if dbg is None or not getattr(dbg, "enabled", False):
                return
            gc = self._gate_counts
            gc["loop"] += 1

            # --- technical noteortechnical note possession + technical note address capture (technical notewithtechnical note change address technical note withtechnical note‌technical note) ---
            poss_ok = poss in ("Home", "Away")
            if poss_ok:
                self._poss_last_ok_wall = now_wall
            cap = getattr(self.engine.poss_hooker, "captured_address", None)
            if cap != self._poss_cap_seen:
                if self._poss_cap_seen is not None and cap is not None:
                    dbg.event("POSS_CAPTURE_CHANGED",
                              old=fmt_ptr(self._poss_cap_seen), new=fmt_ptr(cap),
                              note="address capture possession textandtext text (withtext new structure fresh)")
                self._poss_cap_seen = cap

            # --- technical note currently technical note technical note (for watchdog technical notememory‌technical note) ---
            time_adv = (total_t is not None and self._wd_last_total_t is not None
                        and float(total_t) > float(self._wd_last_total_t))
            self._wd_last_total_t = total_t

            # --- Watchdog re-arm possession (before from technical note‌technical note technical noteandtechnical note always live) ---
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
                              note="capture possession again armed text — firsttext run instruction possession address fresh text text‌text")

            # --- technical noteortechnical note players ---
            if players:
                self._players_last_ok_wall = now_wall

            # --- technical noteortechnical note changetechnical note counter‌technical note (for technical notefromtechnical note‌technical note technical note) ---
            if pass_cnt != self._pass_last_val:
                self._pass_last_val = pass_cnt
                if pass_cnt is not None:
                    self._pass_last_chg_wall = now_wall
            if shot_cnt != self._shot_last_val:
                self._shot_last_val = shot_cnt
                if shot_cnt is not None:
                    self._shot_last_chg_wall = now_wall

            # --- Heartbeat (threshold‌technical note) ---
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

            # --- Warningtechnical note STALE (before from line HB) ---
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
            # reset counter‌technical note windowtechnical note Heartbeat
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
                # agetechnical note technical note Poll (wall — only performance)
                now_wall = time.time()
                if self._last_wall is not None:
                    dt_ms = (now_wall - self._last_wall) * 1000.0
                    self._poll_ema = (self._poll_ema * 0.9 + dt_ms * 0.1) if self._poll_ema else dt_ms
                self._last_wall = now_wall

                # request reset (button user) — in technical note technical note in Worker run technical note‌technical noteandtechnical note
                if self._reset_requested:
                    self._reset_requested = False
                    self._perform_reset()
                    continue

                # ---------- 1. Read Game State ----------
                m_state = self.engine.read_match_state()

                # ---------- 2. Read Game Clock (source andtechnical note time) ----------
                total_t, g_min, g_sec = self.engine.read_game_clock()

                # ---------- 2.0 technical noteortechnical note process (versiontechnical note 10technical note7) ----------
                # read failed technical noteandtechnical note ⇒ process technical note/technical note technical note connection automatic
                # technical note from ENGINE_DEAD_STREAK_LIMIT technical note (~3 second) technical note and retry technical note‌technical note.
                if self.engine.link_alive():
                    self._engine_dead_streak = 0
                else:
                    self._engine_dead_streak += 1

                # ---------- 1.1 cycletechnical note capture possession (versiontechnical note 10technical note18) ----------
                # connectiontechnical note «andtechnical note withtechnical note»: untiltechnical note-technical note technical note technical note‌technical note with firsttechnical note
                # PLAYING cycletechnical note technical note address technical notefrom technical note‌technical noteandtechnical note (hook → confirmation value 2
                # → technical note hook). if capture/hook from before active istechnical note technical note
                # technical note‌technical note (technical note‌withtechnical note technical note).
                if (m_state == "PLAYING"
                        and not self._poss_first_playing_seen
                        and self.engine.poss_hooker.captured_address is None
                        and not self.engine.poss_hooker.is_hooked):
                    self._poss_first_playing_seen = True
                    self._possession_begin_capture_cycle("first-playing")

                # ---------- 2.05 start technical note new (versiontechnical note 10technical note7) ----------
                # «untiltechnical note technical note technical note and after start to rise technical note» = start technical note new
                # (technical note withtechnical note beforetechnical note technical note technical note withtechnical note technical note technical note) ⇒ technical noteandtechnical notefromtechnical note fast hook‌technical note
                self._timer_rebirth_tick(total_t, now_wall)

                # ---------- 2.05-technical note v10.28 — technical note technical notefrom/technical note before from technical noteagetechnical note‌technical note ----------
                # (technical noteandtechnical note v1.3 from versiontechnical note 2017 — technical note withtechnical note technical note «chart in minutetechnical note
                # target (43/85) display data technical note only technical note from match end technical note»):
                # beforetechnical note technical note technical notefrom (technical note decrease time / Watchdog withtechnical note new /
                # confirmation HT and ET) after from technical note‌technical note ball/players/geometry and technical note
                # PLAYING run technical note‌technical note if technical note‌technical note data technical note Worker technical note technical note‌technical note
                # (technical note players=None in connection andtechnical note withtechnical note)technical note half_number for
                # always 1 technical note‌technical note and display minutetechnical note target technical note second (h2/et) never
                # technical notein technical note‌technical note — technical note‌technical note Errortechnical note. technical note:
                #   1) technical noteortechnical note‌technical note technical note (seen_max / max_half2) technical note‌technical note to‌technical noteandtechnical note
                #      technical note‌technical noteandtechnical note (independent from technical note‌technical note data)technical note
                #   2) technical note decrease time technical note‌technical note technical noteandtechnical note technical note‌technical noteandtechnical note (technical note when datatechnical note
                #      ball/player technical note is — technical note technical note only in PLAYING)technical note
                #   3) Watchdog withtechnical note new and confirmation HT/ET with same technical note beforetechnical note
                #      «only in PLAYING» technical note technical note‌technical noteandtechnical note (technical note user technical note technical note).
                # result: technical note _snapshot_tick value half_number always from
                # source andtechnical note fresh is — technical note when datatechnical note pitch technical note is.
                if total_t is not None:
                    if total_t > self._match_seen_max_t:
                        self._match_seen_max_t = total_t
                    # versiontechnical note 10technical note7: technical note game clocktechnical note technical note second — for detection extra time
                    # (second half + technical note > 90 minute ⇒ image Extra_Match_Moment)
                    if (self.half_number >= 2
                            and float(total_t) > self._tv_max_half2_t):
                        self._tv_max_half2_t = float(total_t)
                    # (v10.28 — technical note‌technical note decrease time from after from technical note‌technical note data to
                    #  technical note‌technical note technical note technical note until technical note technical notefrom technical note technical note‌technical note technical noteagetechnical note technical note
                    #  technical note technical note technical note only technical note resume PLAYING)
                    _prev_t_core = self.runtime.get_core()["current_match_time"]
                    if (self.runtime.connected
                            and should_flag_time_drop(
                                _prev_t_core, total_t,
                                self.config.MATCH_RESTART_DELTA)):
                        self._flag_time_drop(_prev_t_core, total_t)
                if m_state == "PLAYING" and total_t is not None:
                    # ---------- 7.4 Watchdog withtechnical note new (version 10technical note3) ----------
                    # «technical note technical note untiltechnical note» in technical noteortechnical note PLAYING technical note technical noteandtechnical note start Match new
                    # is — independent from technical note decrease time. if matchtechnical note current andtechnical note technical noteand
                    # technical note withtechnical note (technical note from windowtechnical note start + technical noteuntil) and technical note PLAYING with
                    # untiltechnical note ≈ technical note technical note matchtechnical note beforetechnical note technical note technical note is:
                    #   90:xx → 0:00 = withtechnical note new   |   6:xx → 0:00 = withtechnical note new
                    #   (45:xx → 45:00 = start second half — to watchdog technical note‌technical noteandtechnical note
                    #    because 2700 from windowtechnical note NEW_GAME_MAX_START outside is)
                    # match endtechnical note first technical noteandtechnical note (90:00 → STOP) never technical note technical note‌technical note
                    # reset only with «PLAYING + untiltechnical note ≈ technical note» run technical note‌technical noteandtechnical note.
                    if is_new_match_watchdog(self._match_seen_max_t, total_t,
                                             self.config.NEW_GAME_MAX_START,
                                             self.config.MATCH_RESTART_DELTA):
                        clog(f"[MatchLifecycle] NEW_MATCH (watchdog): PLAYING + "
                              f"untiltext {_fmt_clock(total_t)} currentlytext text matchtext current until "
                              f"{_fmt_clock(self._match_seen_max_t)} text text textandtext — "
                              "reset complete matchtext beforetext (chart/textandtextdatatext/text/counter‌text)")
                        _d = getattr(self, "dbg", None)
                        if _d:
                            _d.event("NEW_MATCH_WATCHDOG", t=round(float(total_t), 1),
                                     seen_max=round(float(self._match_seen_max_t), 1),
                                     path="watchdog")
                        self._perform_reset(momentum_start_t=total_t)
                        continue

                    # ---------- 7.5 technical note‌technical note technical note from decrease time (version 10technical note3 — State Machine) ----------
                    # only technical note resume PLAYING inwithtechnical note decrease technical note time technical note technical note‌technical note.
                    # technical note with classify_resume_after_drop (technical noteandtechnical note technical note 7technical note6) technical note technical note‌technical noteandtechnical note:
                    #   1) NEW_MATCH: untiltechnical note ≈ technical note — technical noteandtechnical note‌technical note technical note technical note technical note HT
                    #      (90:xx → 0:00 and 6:xx → 0:00 never HT is nottechnical note)
                    #   2) HT: only with rule technical note —
                    #      half == 1 AND prev_end >= 45*60 AND current technical noteandtechnical note 45:00
                    #      (if previous_time < 45:00 withtechnical note technical note with technical note timetechnical note HT technical notemenutechnical note)
                    #   3) KEPT: technical note technical note‌technical note (match end/technical note technical note) → chart technical note technical note‌technical noteandtechnical note
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
                            # HT real: Half 1 End → HT Gap → Half 2 Start (from 45:00)
                            self._ht_pending = False
                            self.half_number = 2
                            self._match_phase = MatchPhase.HALF_2
                            self.momentum.set_phase_label(MatchPhase.HALF_2.value)
                            self.momentum.set_half_break(self.config.HT_GAP_DISPLAY_SECONDS, total_t)
                            self._tv_dirty = True           # versiontechnical note 10technical note12 — render immediate gap HT technical noteandtechnical note technical note TV
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_HT", half1_end=round(float(self._ht_prev_end_t), 1),
                                         half2_start=round(float(total_t), 1))
                            clog(f"[MatchLifecycle] HT confirmation text: first half until "
                                  f"{_fmt_clock(self._ht_prev_end_t)} withtext text (≥ 45:00) — "
                                  f"second half from {_fmt_clock(total_t)}text gap HT intext text")
                            self._shot_debug_push("HALF_TIME_BREAK", team="--",
                                                  half1_end=self._ht_prev_end_t,
                                                  half2_start=total_t,
                                                  note=f"chart text text — gap HT ({int(self.config.HT_GAP_DISPLAY_SECONDS / 60)} minute) intext text sampling from firsttext secondtext second half from text text text‌textandtext (version 5)")
                            self._ui_post(lambda: self.lbl_status.config(
                                text="andtext: second half — chart text text (gap HT) 🟢", fg="#2ecc71"))
                        elif _verdict in ("ET1", "ET2"):
                            # --- versiontechnical note 10technical note15 — start extra time (technical note technical note/technical note technical note technical noteandtechnical note reset):
                            # reset untiltechnical note from withtechnical note 90/105 technical noteandtechnical note 90/105 + Playing + untiltechnical note technical note
                            _et_phase = MatchPhase.ET1 if _verdict == "ET1" else MatchPhase.ET2
                            _et_bound = 90.0 if _verdict == "ET1" else 105.0
                            _et_name = ("text first extra time" if _verdict == "ET1"
                                        else "text second extra time")
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
                            clog(f"[MatchLifecycle] {_verdict} confirmation text (text "
                                 f"{'text' if _verdict == 'ET1' else 'text'}): untiltext from "
                                 f"{_fmt_clock(self._ht_prev_end_t)} (withtext {_et_bound:.0f}:00) "
                                 f"textandtext {_fmt_clock(total_t)} reset text and withtext Playing with "
                                 f"untiltext currently text — start {_et_name}text gap displaytext intext text")
                            self._shot_debug_push(
                                f"{_verdict}_BREAK", team="--",
                                prev_end=self._ht_prev_end_t,
                                et_start=total_t,
                                note=(f"reset untiltext textandtext {_et_bound:.0f}:00 from withtext text + "
                                      f"Playing + untiltext text — start {_et_name}"))
                            self._ui_post(lambda v=_verdict: self.lbl_status.config(
                                text=("andtext: extra time — text first 🟢" if v == "ET1"
                                      else "andtext: extra time — text second 🟢"),
                                fg="#2ecc71"))
                        elif _verdict == "NEW_MATCH":
                            # untiltechnical note from technical note start technical note → withtechnical note new (technical note reset automatic technical notefrom)
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("NEW_MATCH_VERDICT", t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         path="time_drop")
                            clog(f"[MatchLifecycle] NEW_MATCH: PLAYING + untiltext "
                                  f"{_fmt_clock(total_t)} (withtext beforetext until "
                                  f"{_fmt_clock(self._ht_prev_end_t)}) — reset complete matchtext beforetext")
                            self._perform_reset(momentum_start_t=total_t)
                            continue
                        else:
                            # technical note HT and technical note withtechnical note new (technical note technical note technical note/match end) → technical note chart
                            self._ht_pending = False
                            _d = getattr(self, "dbg", None)
                            if _d:
                                _d.event("LIFECYCLE_KEPT", resume_t=round(float(total_t), 1),
                                         prev_end=round(float(self._ht_prev_end_t), 1),
                                         note="chart text text (match end/withtext without reset)")
                            if self.half_number == 2:
                                self._match_phase = MatchPhase.FULL_TIME
                                self.momentum.set_phase_label(MatchPhase.FULL_TIME.value)
                            elif self._match_phase == MatchPhase.HALFTIME:
                                self._match_phase = MatchPhase.HALF_1
                                self.momentum.set_phase_label(MatchPhase.HALF_1.value)
                            # (technical notefromtechnical note ET1/ET2 in technical note KEPT technical note technical note‌technical noteandtechnical note — versiontechnical note 10technical note15)
                            # version 5: technical noteandtechnical note technical note — sampling never technical notemust for technical note
                            # match technical note if technical note technical note latest sampletechnical note technical note withtechnical note
                            # with gap displaytechnical note technical noteandtechnical note from technical note technical note technical note‌technical noteandtechnical note
                            try:
                                self.momentum.resync_clock(total_t)
                            except Exception:
                                pass
                            self._shot_debug_push("TIME_DROP_KEPT", team="--",
                                                  prev_end=self._ht_prev_end_t,
                                                  resume_t=total_t,
                                                  note="chart text text (match end/withtext without reset) — sampling text active text (version 5)")

                # ---------- 2.06 technical noteagetechnical note‌technical note chart TV (versiontechnical note 10technical note11) ----------
                # technical note in «minutetechnical note target − 1»technical note display in «minutetechnical note target» and detection
                # match end (>90′/>120′ stop ≥12s) — must before from technical note‌technical note
                # early-continue run technical noteandtechnical note until in STOP/Pause technical note live technical note.
                self._snapshot_tick(total_t, m_state, now_wall)

                # ---------- 2.06-technical note v2.0.5 — crest banner + ball-link ----------
                # * technical note technical note team‌technical note (minutetechnical note firsttechnical note 5 second) — technical note technical note
                #   linetechnical note data + path displaytechnical note technical note technical noteandtechnical note technical note charttechnical note.
                # * technical note technical noteandtechnical note‌technical note hooktechnical note ball (~2 second) — if tool technical note
                #   (technical noteandtechnical note GLT / crash-recovery) hooktechnical note shared technical note withtechnical noteandtechnical note technical note
                #   withtechnical note automatic re-adopt/reinstall technical note‌technical noteandtechnical note.
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

                # ---------- 2.1 Goal Hook Poll (version 10) — before from technical note technical note‌technical note ----------
                # countertechnical note technical note in memory to ball/players/technical note technical note andtechnical note‌technical note technical note
                # Poll must technical note in menu/Replay/technical note technical note resume technical note withtechnical note.
                # (in version 9 Poll technical note technical noteand early-continue technical noteandtechnical note and with technical note datatechnical note pitch
                #  completetechnical note technical notestop technical note‌technical note — technical note A technical note in technical notein version 10)
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

                # ---------- 2.15 versiontechnical note 10technical note27 — red card (countertechnical note pointertechnical note) ----------
                # technical note technical note: to ball/technical note andtechnical note is nottechnical note technical note for «assignment team»
                # to technical note players technical note frame technical noteortechnical note technical note (technical note z≈40).
                # technical note in STOP/technical note card resume technical note (player‌technical note technical noteandtechnical note technical note‌technical noteandtechnical note).
                try:
                    self._poll_red_card(
                        gh_pick_poll_time(total_t,
                                          self.runtime.get_core().get("current_match_time")),
                        players)
                except Exception as _rc_ex:
                    clog(f"[RedCardPoll] poll error: "
                         f"{type(_rc_ex).__name__}: {_rc_ex}")

                # ---------- 6.0 technical note line technical noteandtechnical note data (version 10technical note4) ----------
                # Heartbeat + Watchdog possession «before from technical note technical note‌technical note» run technical note‌technical noteandtechnical note
                # until technical note when technical note‌technical note technical note technical note technical note‌technical note log technical note technical note codetechnical note layer
                # technical note is (playerstechnical note possessiontechnical note counter‌technical note) and possession technical noteandtechnical note technical noteandtechnical note.
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

                # (v10.28 — technical note‌technical note decrease time to technical note 2.05-technical note technical note technical note — before from
                #  technical note‌technical note datatechnical note until technical note technical notefrom technical note technical note‌technical note technical noteagetechnical note technical note)

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
                self._frame_seq += 1   # versiontechnical note 10technical note14 — countertechnical note technical note frame
                self.runtime.update_core(m_state, total_t, g_min, g_sec, poss, self._poll_ema)
                self._ui_post(self.update_time_status, m_state, g_min, g_sec, total_t)

                # ---------- 7.1 Goal Hook — to technical note 2technical note1 technical note technical note (version 10) ----------
                # Poll technical note technical note before from technical note‌technical note ball/players/geometry run technical note‌technical noteandtechnical note
                # technical note path register technical note technical note technical note early-continuetechnical note hidden is not.

                # ---------- 7.2 technical note‌technical note technical noteandfrom shot technical note in STOP/Pause (version 3) ----------
                # if shot currently technical note‌technical note istechnical note technical note technical note (with burst technical note ~15ms)
                # before from technical note PLAYING run technical note‌technical noteandtechnical note until technical noteandfrom in stop‌technical note technical noteanduntiltechnical note
                # (technical noteandtechnical note ball/technical note technical note) technical note technical noteandtechnical note timeout technical noteandtechnical note technical noteandtechnical note technical noteandtechnical note technical note‌technical note.
                # versiontechnical note 10technical note14 — technical notefromtechnical note technical note technical note technical note in stop‌technical note live technical note‌technical note
                # (buffer in STOP technical note technical note technical note‌technical noteandtechnical note technical noteandtechnical note frame‌technical noteandtechnical note technical note technical note‌technical note)
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                shot_data_early = self._step_shot_tracking(burst=6)
                if shot_data_early:
                    self._register_shot_data(shot_data_early)

                # Pause / Replay / Stop → time withtechnical note technical note istechnical note Momentum technical note technical notemust decay technical note
                if m_state != "PLAYING":
                    self.pass_engine.abort()
                    self._gate_counts["not_playing"] += 1
                    continue

                # (v10.28 — Watchdog withtechnical note new (7.4) and technical note‌technical note technical note from decrease time
                #  (7.5) to technical note 2.05-technical note technical note technical note — before from _snapshot_tick and
                #  technical note‌technical note datatechnical note technical note only in PLAYING technical note technical note is)

                # ---------- 8.0 technical note Context possession (10technical note14 — «before from» technical note shot) ----------
                # order correct specification user:
                #   Read Possession → Read Shot Counter → Read Ball/Players
                #   → Determine valid possession context
                #   → Detect Shot Counter increment → Assign shot team → ...
                # technical note Context possession must «before from» check technical note shot valid technical noteandtechnical note until
                # never «current_possession=None/stale ⇒ technical note technical note» technical note technical note.
                prev_poss_ctx = self.current_possession   # versiontechnical note 10technical note14 — Context beforetechnical note
                if poss and self.current_possession is None:
                    # technical note technical note possession — technical notefrom chain without technical note technical noteandistechnical note
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
                    # technical note technical note baseline countertechnical note «pass» for team active new
                    self.pass_counters[poss] = pass_cnt

                active_team = self.current_possession

                # ---------- 8.1 Shot Counter Trigger (10technical note14 — technical note technical note) ----------
                # counter shot «global» is (technical note technical noteand team). baseline only technical note technical note is
                # and with change possession never withtechnical noteandtechnical note technical note‌technical noteandtechnical note (withtechnical note version 2).
                # versiontechnical note 10technical note14: technical note increment = 1 technical note in technical note ShotEngine — technical note technical note
                # technical note technical note‌technical noteandtechnical note team shot with fallback user technical note and in jumptechnical note «simultaneoustechnical note»
                # possessiontechnical note Context beforetechnical note technical note technical note‌technical noteandtechnical note (team incorrect technical notemenutechnical note).
                cnt_before_dbg = self.shot_counter_baseline
                new_baseline, trig_event = self._shot_trigger_decision(
                    self.shot_counter_baseline, shot_cnt
                )
                self.shot_counter_baseline = new_baseline
                if trig_event == "TRIGGER":
                    # --- technical note team shot (fallback specification user) ---
                    possession_for_shot = self.current_possession
                    if possession_for_shot is None and poss is not None:
                        possession_for_shot = poss
                    # jumptechnical note simultaneous possession and counter ⇒ Context «beforetechnical note» technical note is
                    # (after from shot technical noteandtechnical note possession technical noteandtechnical note technical note‌technical noteandtechnical note if same moment in
                    #  data technical note technical note shot technical notemust to team incorrect ratio data technical noteandtechnical note)
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
                                          note="team shot from Context possession (with fallback) text text")
                elif trig_event == "RESET":
                    _d = getattr(self, "dbg", None)
                    if _d:
                        _d.event("SHOT_COUNTER_RESET", before=cnt_before_dbg, after=shot_cnt,
                                 note="counter shot reset text (second half/restart)")
                    self._shot_debug_push("COUNTER_RESET", team="--",
                                          counter_before=cnt_before_dbg,
                                          counter_after=shot_cnt,
                                          trigger_match_time=total_t,
                                          note="counter shot reset text (second half/restart)")
                    # versiontechnical note 10technical note14 — technical note technical note beforetechnical note technical note‌technical note only with technical note technical note technical note‌technical noteandtechnical note
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
                        # Counter only Trigger is — PassDetector real start technical note‌technical noteandtechnical note
                        self._gate_counts["pass_trig"] += 1
                        self.pass_engine.on_counter_increment(ball, now_wall, total_t, active_team, players)

                pass_data = self.pass_engine.generate_event(
                    ball, total_t, players, self.team1_attack_dir,
                    possession_provider=self.engine.read_possession
                )

                # ---------- 10. Shot Engine — technical note technical note + technical note‌technical note (10technical note14) ----------
                # technical notefromtechnical note technical note technical note technical note shot (1 increment counter = 1 technical note)technical note
                # independent from technical note original (technical note‌technical note) and without technical note‌technical note frame‌technical note.
                self.shot_engine.process(self.engine, list(self.frame_buffer),
                                         now_wall, total_t, self._frame_seq)
                # technical note‌technical note technical noteandfrom with burst technical note (~15ms × 6 ≈ technical note technical note tool independent)
                shot_data = self._step_shot_tracking(burst=6)
                if shot_data:
                    # versiontechnical note 10technical note14 — technical note withtechnical note technical note‌technical note register: output technical note technical note path
                    # technical note must technical note register technical noteandtechnical note (beforetechnical note only path 7.2 register technical note‌technical note)
                    self._register_shot_data(shot_data)

                # ---------- 11-12. Process Event Engine + Register new Events ----------
                if pass_data:
                    self.event_engine.register_pass_event(pass_data)
                    self._ui_post(self.update_pass_card, pass_data)
                self.event_engine.process_frame(self.frame_buffer, frame, self.team1_attack_dir)

                # ---------- 13-15. Events→Impacts (via Bus) + Momentum with MATCH TIME ----------
                self.momentum.update(total_t)

                # ---------- 16. Schedule UI refresh ----------
                # (Event Timeline — technical note technical note new technical notedistance)
                if len(self.event_engine.events) > self._last_ev_count:
                    new_evs = self.event_engine.events[self._last_ev_count:]
                    self._last_ev_count = len(self.event_engine.events)
                    self._ui_post(self.update_ui_events, new_evs)

                # (Possession Sequences — Live Update from _graph_loop technical note technical note‌technical noteandtechnical note
                #  technical note only technical note for technical notewithtechnical note to‌technical noteandtechnical note technical note‌technical note)
                if len(self.momentum.impacts) > self._last_imp_count:
                    self._last_imp_count = len(self.momentum.impacts)

                self._ui_post(self.update_possession_cards)
                self._ui_post(self._update_goal_hook_label)

            except Exception as ex:
                clog(f"[Worker Error] Unhandled exception: {ex}")
                # version 10technical note4: Errortechnical note technical noteandtechnical note Worker in log file technical note register technical note‌technical noteandtechnical note
                # (if technical note technical note technical note technical notecodetechnical note only technical note‌technical note technical note before from Error Poll technical note‌technical noteandtechnical note register technical note‌technical note)
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
        versiontext 10text27 — read countertext red card (pointer 3 leveltext — without hook) and
        assignment team with text player text:
            [base+0x36F3F88] +0x350 +0x4E0 → u8
        text «increment» = 1 red card. teamtext card in momenttext textandtext textandtext is nottext
        code text second player‌text text text text text‌text — player text in
        z≈40 (outside line lengthtext) text‌text text text teamtext textandtext card for same
        team register text‌textandtext. time text = momenttext textandtext (issued_t — frozentext)text
        text momenttext detection. text‌text beforetext (seat) from text text text‌textandtext.
        """
        d = self._rc_diag
        try:
            raw = self.engine.read_red_card_counter()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[RedCardPoll] Errortext read counter: "
                      f"{type(ex).__name__}: {ex}")
            return
        if raw is None:
            d["n_none"] += 1
            return
        d["n_ok"] += 1
        st = self._rc_state

        # --- 1) BASELINE — firsttechnical note read valid ---
        if st["baseline"] is None:
            st["baseline"] = int(raw)
            clog(f"[RedCardPoll] BASELINE countertext red card = {raw} "
                  "(firsttext read valid — card‌text before from connection withtextfromtext "
                  "text‌textandtext)")
            return

        # --- 2) increment → card new (technical note) in technical note assignment team ---
        if raw > st["baseline"]:
            n_new = int(raw) - st["baseline"]
            if n_new > RC_MAX_JUMP:
                clog(f"[RedCardPoll] ⚠ jump text counter "
                      f"({st['baseline']} → {raw}) — rebaseline without register card")
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
            clog(f"[RedCardPoll] 🟥 red card textin text "
                  f"({int(raw) - n_new} → {raw}) in {_fmt_clock(match_t)} — "
                  f"in text text team (text z≈{RC_Z_TARGET:.0f})")

        # --- 3) decrease → technical note (baseline technical note)technical note reset only in windowtechnical note withtechnical note new ---
        elif raw < st["baseline"]:
            _mt = None
            try:
                _mt = float(match_t) if match_t is not None else None
            except (TypeError, ValueError):
                _mt = None
            if _mt is not None and _mt <= float(self.config.NEW_GAME_MAX_START):
                clog(f"[RedCardPoll] RESET countertext red card: "
                      f"{st['baseline']} → {raw} (withtext new)")
                st["baseline"] = int(raw)
                st["pending"].clear()
                st["exiles"].clear()
            else:
                clog(f"[RedCardPoll] ⏳ decrease text counter "
                      f"({st['baseline']} → {raw}) text text text")

        # --- 4) technical note player‌technical note: assignment team + to‌technical noteandtechnical note technical note ---
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

        # technical note without cardtechnical note in technical note technical note register technical noteandtechnical note — cardtechnical note aftertechnical note technical note‌technical note
        # technical note from technical note technical note technical note‌technical note (technical note legacy again assignment technical note‌technical noteandtechnical note)
        st["exiles"].update(now_exiles.keys())

        # --- 5) technical note assignment (time withtechnical note) + limit wall technical noteandtechnical note technical note ---
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
                clog(f"[RedCardPoll] ⌛ text text team card (textintext in "
                      f"{_fmt_clock(pd['issued_t'])}) to end text — "
                      "text register text")

    def _register_hook_red_card(self, team: str, pd: Dict[str, Any],
                                player: Optional[Dict] = None):
        """
        versiontext 10text27 — register text red card textandtext chart (text text: line textandtext +
        icon card to‌text ball). time text = momenttext textandtext card (issued_t —
        frozentext text increment counter)text text momenttext detection team. without text
        textandtextandtext / Event Bus — only text (text versiontext 2017).
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
            clog(f"[RedCard→Graph] text red card {team} registered | "
                  f"textandtext={_fmt_clock(pd.get('issued_t', 0.0))} | "
                  f"detection from player seat={_seat} in z≈{RC_Z_TARGET:.0f} | "
                  f"text active={self.momentum.red_card_marker_count()}")
            self._shot_debug_push(
                "RED_CARD_REGISTERED", team=team,
                match_time=pd.get("issued_t", 0.0),
                half=int(pd.get("issued_half", 1) or 1),
                seat=_seat, z_target=RC_Z_TARGET,
                note="countertext pointertext + assignment z=40 (v10.27)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("RED_CARD_REGISTERED", team=team,
                         t=round(float(pd.get("issued_t", 0.0)), 1),
                         seat=_seat)
        except Exception as ex:
            clog(f"[RedCard] Errortext register text: {ex}")

    def _poll_goal_hook(self, match_t: float):
        """
        version 10 — read textand countertext text ([rcx+0x158] Home / [rcx+0x15C] Away)
        and register text increment to‌textandtext text textandtext Event Bus.

        text text with version‌text before text is (counter_event / Sticky
        First-Capture / limit jump MAX_GOAL_JUMP)text only layertext log
        [GoalHookPoll] text text until «text» path failure in Console text textandtext:
          - hook active is not / still capture text / Errortext read
          - change RAW counter‌text (withtext or below)
          - BASELINE / RESET / textandtext structure (rcx)
          - heartbeat andtext text 5 second
        textandtext to Replay: counter in text text jump text‌text only «increment» text is.
        connection shot ← text with MATCH TIME.
        """
        d = self._gh_diag
        try:
            st = self.engine.read_goal_counters()
        except Exception as ex:
            d["n_err"] += 1
            if d["n_err"] == 1:
                clog(f"[GoalHookPoll] Errortext read counter: {type(ex).__name__}: {ex}")
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
        # [GoalHookPoll] — layertechnical note technical note‌technical note (version 10)
        # ---------------------------------------------------------
        if not st.get("hooked"):
            d["n_nohook"] += 1
            if not d["notified_no_hook"]:
                d["notified_no_hook"] = True
                clog("[GoalHookPoll] goal hook active is not — register text disabled "
                      "(resulttext install hook in Console above text check text)")
            return
        d["notified_no_hook"] = False

        if not st.get("captured"):
            d["n_wait"] += 1
            if d["last_captured"] is not False:
                clog("[GoalHookPoll] captured=False — in text firsttext write structure text "
                      "(slot text istext with firsttext to‌textandtext text text in textandtext withtext capture text‌textandtext)")
            d["last_captured"] = False
            return
        if d["last_captured"] is not True:
            clog(f"[GoalHookPoll] capture text text ✅ rcx={(st.get('rcx') or 0):#x} "
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
            clog(f"[GoalHookPoll] ⚠ structure text textandtext text: rcx {d['last_rcx']:#x} → {(_rcx or 0):#x} "
                  f"(counter‌text from structure new textandtext text‌textandtext)")
            _d = getattr(self, "dbg", None)
            if _d:
                _d.event("GOAL_RCX_CHANGED", old=fmt_ptr(d["last_rcx"]), new=fmt_ptr(_rcx),
                         note="structure text match in memory textto‌text text")
        d["last_rcx"] = _rcx

        _h, _a = st.get("home"), st.get("away")
        if _h != d["last_home"] or _a != d["last_away"]:
            clog(f"[GoalHookPoll] RAW Home: {d['last_home']} → {_h} | "
                  f"Away: {d['last_away']} → {_a} | t={_fmt_clock(match_t)}")
        d["last_home"], d["last_away"] = _h, _a

        # ---------------------------------------------------------
        # technical note (technical note unchanged — version 4/6/9)
        # ---------------------------------------------------------
        # ⚫ technical note original «technical note technical note register technical note‌technical noteandtechnical note» (version 10):
        #   poll() totaltechnical note technical note «home/away» technical noteandtechnical note technical note‌technical note technical note technical note
        #   st.get(team) with «Home/Away» technical note technical noteandtechnical note technical note‌technical note → always None →
        #   counter_event(None, None) → WAIT technical note → technical note technical note never register
        #   technical note‌technical note (from version 5 until 9!). technical note UI from st.get("home") technical note‌technical noteandtechnical note
        #   for technical note number technical noteandtechnical note technical note correct technical noteandtechnical note andtechnical note technical note always WAIT technical noteandtechnical note.
        #   technical note: st.get(team.lower())
        for team in ("Home", "Away"):
            new_v = st.get(team.lower())
            old_v = self.goal_counters[team]
            decision, n_goals = GoalHooker.counter_event(old_v, new_v)
            if decision == "BASELINE":
                # --- version 10technical note3: First-Capture Goal -------------------------
                # firsttechnical note Capture successful Goal Hook possible is «same momenttechnical note technical note first
                # match» withtechnical note (Capture in firsttechnical note run instruction technical note technical note technical note‌technical noteandtechnical note).
                # in technical note beforetechnical note technical note firsttechnical note read technical note BASELINE technical note‌technical note and technical note
                # first for always technical note technical note‌technical note. technical noteandtechnical note: if countertechnical note technical note team in
                # firsttechnical note read valid > 0 withtechnical note technical note «technical note technical note» from baseline
                # technical note start match is and same moment to‌technical noteandtechnical note technical note real register
                # technical note‌technical noteandtechnical note (technical note + Goal Event + technical note). technical note baseline internal
                # same value technical note‌technical noteandtechnical note and technical noteandtechnical note technical note Counter Tracking (1→2 = technical note
                # new) without technical noteandwithtechnical note register‌technical note resume technical note‌ortechnical note. technical note technical note only for
                # firsttechnical note Capture technical note team is and after from reset_capture (withtechnical note new)
                # again armed technical note‌technical noteandtechnical note.
                if self._gh_fc_pending.get(team):
                    self._gh_fc_pending[team] = False
                    self._register_first_hook_goal(team, new_v, match_t)
                self.goal_counters[team] = new_v
                if not d["baselined"].get(team):
                    d["baselined"][team] = True
                    clog(f"[GoalHookPoll] BASELINE {team}={new_v} "
                          "(firsttext read valid — text text text text‌textandtext)")
                self._shot_debug_push("GOAL_COUNTER_BASELINE", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="firsttext read valid countertext text")
            elif decision == "GOAL":
                self.goal_counters[team] = new_v
                clog(f"[GoalHook] change countertext text {team}: {old_v} → {new_v} "
                      f"({n_goals} text new) in {_fmt_clock(match_t)}")
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
                clog(f"[GoalHookPoll] RESET countertext {team}: {old_v} → {new_v} "
                      "(withtext new / resync)")
                self._shot_debug_push("GOAL_COUNTER_RESET", team=team,
                                      counter=new_v, match_time=match_t,
                                      note="countertext text reset text (withtext new)")

        # ---------------------------------------------------------
        # heartbeat andtechnical note — technical note 5 second
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
        version 9 — register text text from change countertext hook:
          1) text direct textandtext chart (path independent from Event Bus) — first from text
          2) versiontext 10text12 — render immediate text TV with text dirty (text Live text text)text
          3) text "Goal ⚽" textandtext Event Bus → text delaytext textandtextandtext + text shottext
          4) textwithtext chain + log Console.
        """
        try:
            # 1) register deterministic Marker
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

            # 2) versiontechnical note 10technical note12 — request render immediate technical note TV (without technical note Live)
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
            clog(f"[GoalHook] text {team} in {_fmt_clock(match_t)} registered — "
                  f"text textandtext chart + text textandtextandtext (text active: "
                  f"{self.momentum.hook_goal_marker_count()})")
        except Exception as ex:
            clog(f"[Goal Register] {ex}")

    def _register_first_hook_goal(self, team: str, value: Optional[int], match_t: float) -> int:
        """
        version 10text3 — First-Capture Goal (untiltext independent and text).

        text: Goal Hook only when text‌textandtext RCX text Capture text text instruction
        countertext text text text‌withtext run text withtext textfortext firsttext run Hook
        possible is exactly momenttext «text first match» withtext. in text text Capture
        text text‌textandtext text text beforetext text text text BASELINE in text text‌text and
        text first from text text‌text.

        text text (only for firsttext Capture successful text team in text withtext):
            Goal Hook still Capture text
                ↓ firsttext read valid instruction Goal (RCX Capture text)
            value text Home/Away textandtext textandtext
                ↓
            value = 0  → text text only baseline firsttext (0,0)
            value = 1  → same moment text Goal real for same team register textandtext:
                          text text textandtext chart + Goal Event + Goal Momentum Pulse
            value > 1  → «text text» from baseline text check and register text‌textandtext
                          (with limit text MAX_GOAL_JUMP — text textandtext and text 0→1 is)
                ↓
            baseline internal = value
                ↓
            from text to after textandtext text Counter Tracking:
              1 → 2 = text text new    2 → 3 = text text new    ...
            (for text textand team independenttext text textandwithtext register‌text text text‌text because
             same increment 0→value only text‌withtext and in text untiltext register text‌textandtext)

        after from reset_capture() in withtext newtext text text again armed text‌textandtext
        (_gh_fc_pending in _perform_reset to True text‌text).

        output: count text‌text register‌text in text textandtext.
        """
        if value is None or value <= 0:
            # technical note technical noteand technical note (or read invalid) → technical note technical note register technical noteandtechnical note
            # Capture only baseline firsttechnical note is
            clog(f"[GoalHook] First-Capture {team}={value} — without text "
                  "Capture to‌textandtext baseline firsttext registered")
            return 0
        n = min(int(value), GoalHooker.MAX_GOAL_JUMP)
        clog(f"[GoalHook] First-Capture Goal {team}: 0 → {value} in {_fmt_clock(match_t)} — "
              f"text first match same momenttext Capture register text‌textandtext "
              f"(text textandtext chart + Goal Event + Goal Momentum Pulse)")
        _d = getattr(self, "dbg", None)
        if _d:
            _d.event("GOAL_FIRST_CAPTURE", team=team, value=value, registered=n,
                     t=(round(float(match_t), 1) if match_t is not None else None))
        for _ in range(n):
            self._register_hook_goal(team, match_t)
        if int(value) > GoalHooker.MAX_GOAL_JUMP:
            clog(f"[GoalHook] ⚠ value firsttext {team}={value} from limit text "
                  f"{GoalHooker.MAX_GOAL_JUMP} text — {n} text registered and "
                  f"{int(value) - n} text withtext‌text text text text (log text check text)")
        return n

    def _update_goal_hook_label(self):
        """text andtext goal hook textandtext textandtext pitch (only in change text text text‌textandtext)"""
        gh = self._goal_hook_status
        if not gh["hooked"]:
            txt = "Goal Hook: INACTIVE ⚠ "
            color = "#fca311"
        elif not gh["captured"]:
            txt = "Goal Hook: INSTALLED ⏳ (text write) "
            color = "#ffd166"
        else:
            txt = (f"Goal Hook: ACTIVE ✅ H:{gh['home'] if gh['home'] is not None else '-'}"
                   f" A:{gh['away'] if gh['away'] is not None else '-'} "
                   f"text‌text: {gh.get('events', 0)} ")
            color = "#00f5d4"
        if txt != self._goal_hook_label_txt:
            self._goal_hook_label_txt = txt
            self.lbl_goal_hook.config(text=txt, fg=color)


    def update_possession_cards(self):
        poss = self.runtime.get_core()["current_possession"]
        if poss == "Home":
            self.card_home.config(bg="#1a3828")
            self.lbl_home_team.config(bg="#1a3828")
            self.lbl_home_status.config(text=f"possession: text ⚽ ({self.team1_side_name})", fg="#00f5d4", bg="#1a3828")
            self.card_away.config(bg="#131a28")
            self.lbl_away_team.config(bg="#131a28")
            self.lbl_away_status.config(text="possession: text", fg="#94a3b8", bg="#131a28")
        elif poss == "Away":
            self.card_away.config(bg="#3d1d2b")
            self.lbl_away_team.config(bg="#3d1d2b")
            self.lbl_away_status.config(text=f"possession: text ⚽ ({self.team2_side_name})", fg="#f38ba8", bg="#3d1d2b")
            self.card_home.config(bg="#131a28")
            self.lbl_home_team.config(bg="#131a28")
            self.lbl_home_status.config(text="possession: text", fg="#94a3b8", bg="#131a28")


    def _team_tick(self):
        """text independent textortext textandtext/color team‌text (text‌text to buttontext connection original).
        versiontext 10text6 — exactly text textortext user:
          * until andtext‌text: text 1 second text connection (TEAM_TRACKER_INTERVAL_MS)text
          * after from andtext‌text: from same moment to after read «text‌untiltext» text‌text —
            text 50ms (TEAM_LIVE_INTERVAL_MS) text text realtime_loop tool originaltext
          * in text text color chart text from leagues_data.json + byte istext numbertext
            color text text‌textandtext (in textandtext changetext chart and text‌text to‌textandtext text‌textandtext).
        versiontext 10text7 — firstandtext 1 in start text new: text _team_rehook_pending
        (text‌text in _on_new_hand_detected) ⇒ text text 50ms aftertext textdistance
        text‌text text again text‌textandtext (detection Home/Away first from text)."""
        urgent = bool(getattr(self, "_team_rehook_pending", False))
        self._team_rehook_pending = False
        snap: Dict[str, Any] = {}
        try:
            snap = self.team_tracker.poll()
            self._apply_team_identity(snap)
            self._apply_team_colors(snap)
            if urgent:
                try:
                    self.dbg.event("TEAM_REHOOK", note="read immediate text‌text in "
                                                   "start text new (firstandtext 1)",
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
            # technical note‌untiltechnical note after from connection / technical note technical note 1 second until connection
            interval = (TEAM_LIVE_INTERVAL_MS if snap.get("connected")
                        else TEAM_TRACKER_INTERVAL_MS)
            self.after(interval, self._team_tick)

    def _apply_team_identity(self, snap: Dict[str, Any]):
        """Renders the logos in the home/away slots (GUI build). If no valid
        team selection has been seen yet (state 100) or the team image is
        not in Football_Database, the slot keeps its «Home»/«Away»
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
        for side, slot, fallback in (("home", self.lbl_home_logo, "Home"),
                                     ("away", self.lbl_away_logo, "Away")):
            ident = snap.get(side)
            path = self.team_tracker.logo_path_for(ident)
            if path == self._team_logo_path[side]:
                continue   # unchanged — technical note technical note image tool original
            photo = None
            if path:
                try:
                    img = Image.open(path)
                    img.thumbnail(TEAM_LOGO_SLOT_PX, Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)
                except Exception:
                    photo = None
            if photo is not None:
                self._team_logo_photo[side] = photo       # prevent from Garbage Collection
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
        """text color text team (textandtext 1..6 section 26-text) and text text:
          * self._chart_colors ⇒ in render aftertext chart (text 100ms) text text‌textandtext
          * text‌text text team name: text text (color text) or currentlytext textandtext
            colortext textand text (color original + color textandtext)text
          * changetext in momentum_debug_log.txt text register text‌textandtext (TEAM_COLOR)."""
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
            return   # unchanged — render technical note technical notefromtechnical note is not
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
        """text color text text team (rule 4):
          * text text: text text — color text‌text chart (text text)text
          * text textandtext (rule 2/3): textand text — color original (text text)
            + color textandtext text code text text (text text)."""
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
        """layer textwithtext chain shot — Worker/ShotEngine → UI (Thread-safe via deque)"""
        try:
            self.shot_debug_log.append({"wall": time.time(), "stage": stage, **kw})
        except Exception:
            pass

    @staticmethod
    def _shot_trigger_decision(prev_baseline: Optional[int], shot_cnt: Optional[int]):
        """
        text text shot from countertext «global» — exactly text tool independent user:
          * baseline None        → register baseline (without text)
          * shot_cnt < baseline  → RESET (second half/restarttext without text)
          * shot_cnt > baseline  → TRIGGER (jump = text or text shot new)
          * text / None         → unchanged
        output: (baseline newtext text) text text ∈ {None, 'BASELINE', 'RESET', 'TRIGGER'}
        text totaltext: text untiltext to possession text text possession never baseline text
        withtextandtext text‌text — text complete withtext text‌text text in version 2.
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
        text or text text textandtext from text‌text textandfrom shot.
        burst > 0: until burst text with distancetext ~12ms run text‌textandtext (text‌textfromtext text
        text ~15ms tool independent) — only when text‌text active istext in textandtext
        text text text‌second text stall text‌textandtext and because decay text text MATCH
        TIME istext textortext textandtextandtext text‌text text text text text‌text.
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
        """register ShotEventData textandtext Event Bus + chaintext [SHOT] + card UI
        versiontext 10text14 — Dedup «only» with text text (1 increment counter = 1 register):
          * text text 10text12 (team/text/text/1 second) text text — textand shot realtext
            text‌text (text textwithtext) text text text‌textandtext
          * path complete text text‌textandtext:
            ShotEventData → register_shot_event() → Momentum Impact → Threat
            → UI Shot List — text text with log [SHOT] and countertext text."""
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
                                          note="same text counter beforetext registeredtext — register second text text")
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
            # --- Momentum Impact (technical note path complete specification user) ---
            imp = self.momentum.get_impact(shot_data.event_id)
            if imp is not None:
                self.shot_engine._stat("threats_created")
                self._shot_debug_push("THREAT_CREATED", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      momentum_impact=f"{imp.final_impact:+.1f}",
                                      note="Impact textandtextandtext for shot text text")
            else:
                self._shot_debug_push("THREAT_MISSING", team=shot_data.team,
                                      shot_event_id=shot_data.event_id,
                                      candidate_id=cand_id,
                                      note="Impact textdecrease text (check textandtext)")
            # --- UI Shot List ---
            self._ui_post(self.update_shot_card, shot_data)
            self.shot_engine._stat("ui_added")
            self._shot_debug_push("UI_ADDED", team=shot_data.team,
                                  shot_event_id=shot_data.event_id,
                                  candidate_id=cand_id,
                                  note="shot to text UI text text")
        except Exception as ex:
            clog(f"[Shot Register] {ex}")

    def _timer_rebirth_tick(self, total_t: Optional[float], now_wall: float):
        """
        textortext text user: «when untiltext withtext to text text text text and second/minute
        text start to rise text text start text new — text withtext beforetext text
        text withtext text text. code must text fast detection text and hook‌text text in text
        from second text and again hook text.»

        text text lightweight (text text Worker ~15ms ⇒ delay detection < 50ms):
          * untiltext ≤ TRB_ZERO_T  ⇒ armed (untiltext text text text)
          * armed and untiltext > TRB_RISE_T ⇒ start to rise ⇒ FIRE + Disarm
        text second from 45:00 start text‌textandtext (minute‌text 45 text text) ⇒ never FIRE
        text‌textandtext text‌text shared with Watchdog 10text3 from reset textandtext prevent
        text‌text (text textand path _last_auto_reset_wall text to‌textandtext text‌text).
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
                             note="untiltext text text text — text start to rise")
                # --- versiontechnical note 10technical note18 — specification user: «to technical note technical note untiltechnical note technical note
                # technical note hook new technical note technical note until address new technical note technical note» — cycletechnical note technical note
                # address possession exactly in momenttechnical note technical note technical notefrom technical note‌technical noteandtechnical note (before from technical note
                # line technical note unchanged is)technical note firsttechnical note capture technical note value 2
                # confirmation and hook technical note technical note‌technical noteandtechnical note.
                self._possession_begin_capture_cycle("timer-zero")
            return
        if self._trb_armed and t > TRB_RISE_T:
            self._trb_armed = False
            if ((now_wall - self._trb_last_fire_wall) < TRB_COOLDOWN_SEC
                    or (now_wall - getattr(self, "_last_auto_reset_wall", 0.0))
                    < TRB_COOLDOWN_SEC):
                return    # Watchdog/reset automatictechnical note technical note technical note — again‌technical note technical notemenutechnical note
            self._trb_last_fire_wall = now_wall
            self._on_new_hand_detected(t)

    def _possession_begin_capture_cycle(self, reason: str) -> None:
        """versiontext 10text18 — textfrom cycletext text address possession from side App:
        momenttext text untiltext (start withtext new) or firsttext PLAYING after from connection
        andtext withtext. only text line textanduntiltext [PossHook] — without log text text."""
        try:
            rep = self.engine.poss_begin_capture_cycle()
            print(f"[PossHook] cycletext capture possession textfrom text ({reason}): {rep}",
                  flush=True)
        except Exception as ex:
            print(f"[PossHook] {reason}: {type(ex).__name__}: {ex}",
                  flush=True)

    def _on_new_hand_detected(self, t: float):
        """
        text start text new — to order firstandtext usertext in text from second:
          1) hook detection Home/Away: read immediate text‌text (firstandtext first —
             player possible is fast ball text from text text)text
          2) textistext‌text/install text text 4 hook (ball/time/text/possession) + re-arm
             capture text and possession (address‌text beforetext text textandtext text‌text)text
          3) reset complete match (chart/textandtextdatatext/text/counter‌text) —
             same path _perform_reset text State Machine 10text3 istext text‌text.
        """
        _d = getattr(self, "dbg", None)
        clog(f"[NewHand] ⚡ start text new detection data text: untiltext {_fmt_clock(t)} "
              "— textandtextfromtext fast hook‌text (firstandtext: detection Home/Away)")
        # --- firstandtechnical note 1: detection Home/Away (technical note aftertechnical note 50ms technical noteortechnical note technical noteandtechnical note technical note‌technical noteandtechnical note)
        self._team_rehook_pending = True
        # --- 2/3: technical noteandtechnical notefromtechnical note hook‌technical note + reset complete ---
        rep: Dict[str, str] = {}
        try:
            rep = self.engine.verify_and_repair_hooks()
        except Exception as ex:
            rep = {"error": f"{type(ex).__name__}: {ex}"}
        if _d:
            _d.event("NEW_HAND_DETECTED", t=round(float(t), 2), hooks=str(rep),
                     note="untiltext text→risetext hook‌text textandtextfromtext + match reset text")
        self._perform_reset(momentum_start_t=float(t))
        self._ui_post(lambda: self.lbl_status.config(
            text="andtext: start text new — hook‌text textandtextfromtext text 🔄", fg="#00b4d8"))

    def _flag_time_drop(self, prev_t: float, new_t: float):
        """
        version 3 — decrease text time withtext «only text text‌textandtext»text text reset automatictext
        text text text‌textandtext (chart match end must text textandtext).
        text text text resume PLAYING in section 7.5 text text‌textandtext:
        HT (second half) / withtext new (from text) / text chart.
        version 10text3 — if text‌text‌text HT (first half ≥ 45:00 text text) text
        withtext State Machine to HALFTIME text‌textandtext (in text resume)text
        confirmation text text with rule text classify_resume_after_drop is.
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
                self.momentum.set_phase_label(MatchPhase.HALFTIME.value)  # 10technical note15
            except Exception:
                pass
        if self.half_number == 1 and prev_t >= self.config.HT_MIN_FIRST_HALF_PLAYED:
            status_txt = "andtext: text end first half — in text resume withtext 🟠"
        else:
            status_txt = "andtext: decrease time withtext — chart text text (match end/withtext newtext) 🟠"
        self._shot_debug_push("TIME_DROP_FLAGGED", team="--",
                              prev_time=prev_t, new_time=new_t,
                              half_number=self.half_number)
        self._ui_post(lambda: self.lbl_status.config(text=status_txt, fg="#fca311"))

    def request_reset(self, *args, **kwargs):
        """Original button behaviour: queue a reset + status hint."""
        self._reset_requested = True
        try:
            self.lbl_status.config(text="andtext: request reset registered...", fg="#fca311")
        except Exception:
            pass


    def _perform_reset(self, momentum_start_t: Optional[float] = None):
        """events / sequences / momentum history / counters / frame buffer / time state / graph"""
        # --- versiontechnical note 10technical note11 — «savetechnical note technical note charttechnical note»: latest chart withtechnical note beforetechnical note
        # must before from technical note‌technical note untiltechnical note register technical noteandtechnical note (untiltechnical note to 00:00 reset technical note =
        # start technical note new). technical note technical note technical note technical noteagetechnical note‌technical note for withtechnical note new technical note technical note‌technical noteandtechnical note.
        try:
            self._snapshot_finalize_previous_match()
        except Exception:
            pass
        try:
            self.snap_engine.reset_match(time.time())
            self._snap_capture_cache = {}
            # versiontechnical note 10technical note21 — test 6: technical noteorder cycletechnical note technical note for withtechnical note new from technical noteand
            # (countertechnical note seq global technical note‌technical note — number‌technical note technical note Snapshot #42 resume technical note)
            self._snap_life = {}
            # v10.28 — cleanup andtechnical note technical note display for withtechnical note new
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
        # versiontechnical note 10technical note15 — window‌technical note technical noteagetechnical note‌technical note (live + technical note‌technical note) with reset match
        # technical note‌technical notewithtechnical note technical note‌technical noteandtechnical note
        # versiontechnical note 10technical note19 — from Worker direct to UI technical note‌technical noteandtechnical note (technical note Tk technical note‌technical note)
        try:
            self._ui_post(self._hide_snapshot_overlay)
        except Exception:
            pass
        # versiontechnical note 10technical note22 — [SNAPSHOT_STATE] reset match → EMPTY
        try:
            self._snap_state_event("MATCH RESET", SnapshotState.EMPTY,
                                   key=None, extra="match reset")
        except Exception:
            pass
        # technical note technical noteandtechnical note current without technical note technical note new
        self.pass_engine.reset()
        # versiontechnical note 10technical note14 — technical note chaintechnical note shot «technical note from» reset must register/display data technical noteandtechnical note
        # (technical noteortechnical note technical note: Counter increments = Candidates ≈ Registered Events)
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
        # version 3: baseline global counter shot (exactly technical note tool independent user)
        self.shot_counter_baseline: Optional[int] = None
        # version 4: baseline counter‌technical note technical note (with reset match again baseline technical note‌technical noteandtechnical note)
        self.goal_counters = {"Home": None, "Away": None}
        # version 6: freetechnical notefromtechnical note slot capture → firsttechnical note technical noteandtechnical noteuntiltechnical note technical note withtechnical note newtechnical note
        # structure technical note fresh technical note capture technical note‌technical note (technical noteandtechnical note‌technical note withtechnical note‌technical note aftertechnical note)
        try:
            self.engine.goal_hooker.reset_capture(self.engine.h_process)
        except Exception:
            pass
        # version 10technical note4: re-arm capture «possession» — same technical noteandtechnical note self-heal goal hook.
        # withtechnical note in withtechnical note new structure technical note/possession technical note technical noteto‌technical note technical note‌technical note capture legacy
        # address technical note technical note technical note‌technical noteandtechnical note → technical notedatatechnical note from withtechnical note second to after technical note technical note‌technical note.
        # versiontechnical note 10technical note18 — re-arm smart: if address «technical note withtechnical note» technical note second past
        # confirmation technical note withtechnical note technical note technical note‌technical noteandtechnical note (start withtechnical note without deterministic possessiontechnical note technical note
        # «chart in technical note technical note technical note technical note‌technical note»)
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
                     note="reset complete match — capture text and possession again armed text")
        self.current_possession = None
        # versiontechnical note 10technical note14 — cleanup Dedup register shot for matchtechnical note new
        self._registered_shot_ids.clear()
        self._registered_shot_order.clear()
        self._last_ev_count = 0
        self._last_seq_count = 0
        self._last_imp_count = 0
        self._ui_pass_list.clear()
        self._ui_shot_list.clear()
        # version 2: reset andtechnical note technical note / HT and technical note‌technical note livetechnical note Sequences
        self.half_number = 1
        self._ht_pending = False
        self._ht_prev_end_t = 0.0
        # --- version 10technical note3: Match Lifecycle — start technical note from HALF_1 ---
        # (HALF_1 → HT → HALF_2 → FULL_TIME | untiltechnical note≈technical note+PLAYING → NEW_MATCH → HALF_1)
        self._match_phase = MatchPhase.HALF_1
        try:
            self.momentum.set_phase_label(MatchPhase.HALF_1.value)   # versiontechnical note 10technical note15
        except Exception:
            pass
        self._match_seen_max_t = float(cur_t)
        # --- version 10technical note3: First-Capture Goal for withtechnical note new again armed technical note‌technical noteandtechnical note ---
        # reset_capture withtechnical note slottechnical note technical note technical note technical note firsttechnical note technical noteandtechnical noteuntiltechnical note technical note withtechnical note new
        # again Capture technical note‌technical note and if same moment technical note first technical noteandtechnical note
        # _register_first_hook_goal technical note technical note register technical note‌technical note (technical note technical noteand team independent).
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
        # --- versiontechnical note 10technical note27 — reset red card: baseline/in technical note‌technical note/technical note
        # technical note technical note‌technical noteandtechnical note (coordinates players in withtechnical note new again technical note technical note‌technical noteandtechnical note —
        # seattechnical note technical noteandtechnical note technical note‌technical noteandtechnical note)technical note technical note with momentum.reset technical note technical note‌technical note.
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
        # --- versiontechnical note 10technical note7: technical note‌technical note shared reset‌technical note automatic + technical note technical note TV ---
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
        self.lbl_card_title.config(text="textandtext pass: in text start withtext...")
        self.lbl_card_threat.config(text="Threat Score: --")
        self.lbl_card_outcome.config(text="")
        self.lbl_shot_title.config(text="textandtext shot: in text register text shot...")
        self.lbl_shot_threats.config(text="Pre Threat: -- | Final Threat: --")
        self.lbl_shot_outcome.config(text="result: --")
        # versiontechnical note 10technical note12 — technical note Live technical note technical note only render technical note technical note TV technical notefromtechnical note is
        self._tv_dirty = True
        self.lbl_status.config(text="andtext: reset complete text — in text withtext 🟠", fg="#fca311")


    def on_close(self):
        # versiontechnical note 10technical note18 — technical noteandtechnical note technical note technical note (technical note frozen and Errortechnical note TclError technical note technical noteandtechnical note):
        #   1) technical note _closing above from technical note — technical note callback technical note‌technical note technical note technical note technical note‌technical noteandtechnical note
        #   2) stop technical note‌technical note (Worker/connection automatic/team‌technical note/technical note)
        #   3) technical note technical noteanduntiltechnical note for end Worker (technical noteandtechnical note after() simultaneous with destroy)
        #   4) technical note window‌technical note technical noteagetechnical note‌technical note/technical noteandtechnical note and hook‌technical note technical note destroy
        self._closing = True
        self.is_monitoring = False
        # versiontechnical note 10technical note7 — stop technical note connection automatic
        self._auto_connect_running = False
        # version 10technical note5 — stop technical note independent team‌technical note and technical note technical note read-only technical note
        self._team_loop_running = False
        # versiontechnical note 10technical note16 — stop technical note technical note technical noteagetechnical note‌technical note
        try:
            self._snap_anim_gen += 1
            self._snap_anim_alive = False
        except Exception:
            pass
        # versiontechnical note 10technical note18 — technical note technical noteanduntiltechnical note for end Worker (technical note ~2 technical note technical note)
        _wt = getattr(self, "_worker_thread", None)
        if _wt is not None:
            try:
                if _wt.is_alive():
                    _wt.join(timeout=1.5)
            except Exception:
                pass
        # versiontechnical note 10technical note18 — technical noteand «technical note» untiltechnical note after withtechnical note‌technical note until technical note callback
        # after from destroy run technical noteandtechnical note (technical note Errortechnical note «invalid command name»)
        try:
            _ids = self.tk.splitlist(self.tk.call("after", "info"))
            for _aid in _ids:
                try:
                    self.after_cancel(_aid)
                except Exception:
                    pass
        except Exception:
            pass
        # versiontechnical note 10technical note11 — technical note windowtechnical note technical noteagetechnical note‌technical note and technical noteandtechnical note technical note
        try:
            self._hide_snapshot_overlay()
        except Exception:
            pass
        # versiontechnical note 10technical note23 — technical noteandtechnical note technical note Renderer GPU (technical note + Context + GLFW)
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
# technical note andtechnical noteandtechnical note technical notenametechnical note
# =====================================================================
# =====================================================================
# 27. test technical notewithtechnical note End-to-End (version 2 — technical note 21)
# ---------------------------------------------------------------------
# without technical noteortechnical note to withtechnical note realtechnical note technical noteortechnical note technical noteandtechnical note technical noteandtechnical note istechnical note to technical noteandtechnical noteandtechnical note
# Momentum technical note technical note‌technical noteandtechnical note and technical noteuntiltechnical note technical note asserts technical note‌technical note:
#   ✔ technical notedatatechnical note Home to withtechnical note / Away to below
#   ✔ decay technical note technical note technical note (only Match Time)
#   ✔ Goal Marker exactly technical noteandtechnical note t_goal and Goal Peak with delay GOAL_PEAK_DELAY
#   ✔ technical note technical noteandwithtechnical note technical note Chance + Shot technical note‌technical note (SHOT_LINKED_CHANCE_RATIO)
#   ✔ chart never to‌technical noteandtechnical note technical note technical note technical noteandtechnical note technical note‌technical note
#   ✔ Gaussian smoothing real (layer display)
#   ✔ Pause (time technical note) → without sample/decay new
#   ✔ gap HT (sample‌technical note NaN + offset second half)
# run:  python FL_2026_Live_Match_Momentum_v9.py --selftest
# =====================================================================
