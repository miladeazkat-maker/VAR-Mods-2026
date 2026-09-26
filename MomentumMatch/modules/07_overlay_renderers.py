class GPUOverlayRenderer:
    """نسخهٔ ۱۰٫۲۳ — Renderer واقعی Game Overlay (گزینهٔ ۲ گزارش کاربر:
    OpenGL Overlay با ModernGL + GLFW — ساده‌تر و قابل‌اتکا در پایتون).

    State (مشخصات کاربر):
      HIDDEN → READY → ANIMATING(ورود) → VISIBLE → ANIMATING(خروج) → HIDDEN

    Thread Model (گزارش کاربر):
      Main/UI Thread ── queue.put ──► GPU Render Thread (GLFW+ModernGL)
      * Show/Hide فقط پیام است؛ هیچ فراخوانی گرافیکی/ویندوزی از UI.
      * ترد رندر «مالک» پنجره/Context است؛ با vsync همگام و در بیکاری
        منتظر پیام (هیچ CPU Busy Loop؛ اولویت ترد هم دستکاری نمی‌شود)."""

    ST_HIDDEN = "HIDDEN"
    ST_READY = "READY"
    ST_VISIBLE = "VISIBLE"
    ST_ANIM = "ANIMATING"

    # v2.0.1 — the GPU renderer supports the v10.24 vector scene path
    supports_scene = True

    def __init__(self, surf_x, surf_y, surf_w, surf_h,
                 click_through=True, vsync=True, anim_debug=True):
        self.surf = (int(surf_x), int(surf_y), int(surf_w), int(surf_h))
        self._ct = bool(click_through)
        self._vsync = bool(vsync)
        self._adebug = bool(anim_debug)
        self._q = _queue.Queue()
        self._lock = threading.Lock()
        self._state = self.ST_HIDDEN
        self._tex_key = None
        self._ready_ev = threading.Event()
        self._init_error = None
        self._init_info = {}
        self._stop = False
        self._anim = None
        self._visible_img = False
        # v10.29 (پورت v1.2.2 از 2017) — پنجرهٔ اورلی فقط هنگام نمایش
        # واقعی دیده می‌شود (نه از INIT) + hide رهاشده دیگر گم نمی‌شود
        self._win_visible = False
        self._hide_pending = False
        self._anim_stats = {}
        # refs ترد رندر (فقط در همان ترد لمس می‌شوند)
        self._glfw = self._mg = self._win = self._ctx = None
        self._prog = self._vao = self._tex = None
        # نسخهٔ ۱۰٫۲۴ — حالت «رندر برداری»: آیتم‌های تجزیه‌شدهٔ scene (GL objects)
        self._scene = None
        self._sprog_edge = self._sprog_tex = None
        self._cur_travel = 0.0
        self._thread = threading.Thread(target=self._run,
                                        name="gpu-overlay", daemon=True)
        self._thread.start()

    # ---------- API امن از هر ترد (همه غیرمسدود — فقط پیام) ----------
    def wait_init(self, timeout: float = 4.0) -> bool:
        self._ready_ev.wait(timeout)
        return self._init_error is None

    def init_error(self) -> Optional[str]:
        return self._init_error

    def init_info(self) -> dict:
        return dict(self._init_info)

    def state(self) -> str:
        with self._lock:
            return self._state

    def texture_key(self) -> Optional[str]:
        with self._lock:
            return self._tex_key

    def is_alive(self) -> bool:
        return bool(self._thread.is_alive() and self._init_error is None)

    def last_anim_stats(self) -> dict:
        with self._lock:
            return dict(self._anim_stats)

    def _set_state(self, st: str) -> None:
        with self._lock:
            self._state = st

    def _put(self, cmd) -> None:
        try:
            self._q.put_nowait(cmd)
        except Exception:
            pass

    def upload_png_rgba(self, raw, w, h, dx, dy, travel, key,
                        keep_state: bool = False) -> None:
        """آپلود/تعویض Texture از UI-Thread (Preload / retune) — فقط پیام."""
        self._put(("upload", bytes(raw), int(w), int(h), int(dx), int(dy),
                   int(travel), key, bool(keep_state)))

    def upload_scene(self, scene, key=None, keep_state: bool = False) -> None:
        """نسخهٔ ۱۰٫۲۴ — آپلود «صحنهٔ برداری» (رندر خط/fill با AA واقعی روی GPU):
        scene دیکشنری خالصِ ساخته‌شده در ترد Worker است (build_gpu_graph_scene)
        — ترد رندر آن را به Vertex Buffer/Texture/Draw-call تبدیل می‌کند.
        انیمیشن/Show/Hide عیناً مثل مسیر تکستچر قبلی است (حرکت فقط Shader)."""
        self._put(("scene", scene, key, bool(keep_state)))

    def show(self, dur_ms: int = TV_SNAP_ANIM_MS, key=None) -> float:
        """Show — «نمایش یک آبجکت آماده»: فقط یک queue.put (زیر ~۰٫۱ms)."""
        t = time.perf_counter()
        self._put(("show", float(max(0.0, dur_ms)) / 1000.0, t, key))
        return t

    def hide(self, dur_ms: int = TV_SNAP_ANIM_MS) -> None:
        """خروج انیمیشنی (Shader) — باز هم فقط پیام."""
        self._put(("hide", float(max(0.0, dur_ms)) / 1000.0,
                   time.perf_counter()))

    def hide_now(self) -> None:
        """شفاف‌شدن فوری (بدون انیمیشن) — یک پیام."""
        self._put(("hide_now", time.perf_counter()))

    def shutdown(self, timeout: float = 1.5) -> None:
        try:
            self._put(("stop",))
            self._thread.join(timeout=timeout)
        except Exception:
            pass

    # ---------------- GPU Render Thread ----------------
    def _log_block(self, title: str, lines) -> None:
        if not TV_SNAP_SHOW_DEBUG:
            return
        try:
            print("=" * 60, flush=True)
            print(title, flush=True)
            print("=" * 60, flush=True)
            for ln in lines:
                print(ln, flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass

    def _apply_win32_styles(self, hwnd) -> str:
        """یک‌بار در شروع — Topmost + click-through. در طول انیمیشن «هیچ»
        فراخوانی ویندوزی انجام نمی‌شود (حرکت فقط uniform روی GPU است)."""
        if sys.platform != "win32" or not hwnd:
            return "n/a (non-Windows)"
        try:
            user32 = ctypes.windll.user32
            GWL_EXSTYLE = -20
            try:
                old = int(user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)) \
                    & 0xFFFFFFFF
            except Exception:
                old = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE)) \
                    & 0xFFFFFFFF
            WS_EX_LAYERED = 0x00080000
            WS_EX_TRANSPARENT = 0x00000020
            WS_EX_NOACTIVATE = 0x08000000
            WS_EX_TOOLWINDOW = 0x00000080
            new = old | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            if self._ct:
                new |= WS_EX_LAYERED | WS_EX_TRANSPARENT
            try:
                user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, new)
            except Exception:
                user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new)
            if self._ct:
                try:
                    user32.SetLayeredWindowAttributes(hwnd, 0, 255, 0x2)
                except Exception:
                    pass
            user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0,
                                0x0001 | 0x0002 | 0x0010)  # TOPMOST یک‌بار
            return (f"0x{old:08X} → 0x{new:08X} "
                    + ("LAYERED|TRANSPARENT|NOACTIVATE|TOOLWINDOW"
                       if self._ct else "NOACTIVATE|TOOLWINDOW")
                    + " | TOPMOST (asserted once at init)")
        except Exception as ex:
            return f"failed: {type(ex).__name__}: {ex}"

    def _run(self):
        try:
            try:
                import glfw as _glfw
                import moderngl as _mg
            except Exception as ex:
                self._init_error = (f"package import failed: "
                                    f"{type(ex).__name__}: {ex} — اجرا کنید: "
                                    "pip install moderngl glfw")
                self._ready_ev.set()
                return
            self._mg = _mg
            if not _glfw.init():
                self._init_error = "glfw.init() failed"
                self._ready_ev.set()
                return
            self._glfw = _glfw
            sx, sy, sw_, sh_ = self.surf
            _glfw.window_hint(_glfw.VISIBLE, False)
            _glfw.window_hint(_glfw.DECORATED, False)
            _glfw.window_hint(_glfw.RESIZABLE, False)
            _glfw.window_hint(_glfw.FOCUS_ON_SHOW, False)
            _glfw.window_hint(_glfw.FLOATING, True)
            _glfw.window_hint(_glfw.TRANSPARENT_FRAMEBUFFER, True)
            _glfw.window_hint(_glfw.DOUBLEBUFFER, True)
            # نسخهٔ ۱۰٫۲۴ — MSAA برای لبه‌های سختِ عناصر مات (خط صفر/گل)؛
            # لبهٔ منحنی/fill خودش AA تحلیلی در Fragment Shader دارد. اگر
            # پیکسل‌فرمت MSAA+شفاف روی این سیستم ساخته نشد → بدون MSAA.
            _glfw.window_hint(_glfw.SAMPLES, 4)
            win = _glfw.create_window(sw_, sh_, "momentum-gpu-overlay",
                                      None, None)
            if not win:
                _glfw.window_hint(_glfw.SAMPLES, 0)
                win = _glfw.create_window(sw_, sh_, "momentum-gpu-overlay",
                                          None, None)
            if not win:
                self._init_error = ("glfw.create_window failed — پنجرهٔ "
                                    "شفاف ساخته نشد (DWM/driver?)")
                self._ready_ev.set()
                _glfw.terminate()
                return
            self._win = win
            _glfw.set_window_pos(win, sx, sy)
            _glfw.make_context_current(win)
            _glfw.swap_interval(1 if self._vsync else 0)
            ctx = _mg.create_context()
            self._ctx = ctx
            try:
                ctx.disable(_mg.DEPTH_TEST)
            except Exception:
                pass
            # نسخهٔ ۱۰٫۲۴ — ترکیب premultiplied-alpha برای رندر برداری چندلایه
            try:
                ctx.enable(_mg.BLEND)
                ctx.blend_func = (_mg.ONE, _mg.ONE_MINUS_SRC_ALPHA)
            except Exception:
                pass
            prog = ctx.program(vertex_shader=_OVERLAY_VERT_SRC,
                               fragment_shader=_OVERLAY_FRAG_SRC)
            quad = np.array([0.0, 0.0,
                             float(sw_), 0.0,
                             0.0, float(sh_),
                             float(sw_), float(sh_)], dtype="f4")
            vbo = ctx.buffer(quad.tobytes())
            vao = ctx.vertex_array(prog, [(vbo, "2f", "a_px")])
            prog["u_surf"].value = (float(sw_), float(sh_))
            self._prog = prog
            self._vao = vao
            # یک فریم کاملاً شفاف قبل از نمایان‌شدن (بدون فلش)
            ctx.clear(0.0, 0.0, 0.0, 0.0)
            _glfw.swap_buffers(win)
            # v10.29 (پورت v1.2.2 از 2017) — رفع «نمودار تا ابد در گوشهٔ
            # تصویر ماند»: پنجره در INIT دیگر نمایش داده نمی‌شود. سیاست
            # جدید: پنجره فقط با فرمان واقعی «show» نمایان می‌شود
            # (_win_show) و بعد از پایان انیمیشن خروج (یا hide_now) در
            # سطح خود ویندوز مخفی می‌شود (_win_hide) — خروج نمودار از
            # صفحه دیگر ONLY به ارائهٔ فریم شفاف از ترد رندر وابسته
            # نیست؛ اگر hide گم/رها شود یا ترد رندر کند شود، خودِ پنجره
            # از صفحه خارج می‌شود.
            self._win_visible = False
            try:
                styles = self._apply_win32_styles(_glfw.get_win32_window(win))
            except Exception as ex:
                styles = f"failed: {ex}"
            try:
                transp = bool(_glfw.get_window_attrib(
                    win, _glfw.TRANSPARENT_FRAMEBUFFER))
            except Exception:
                transp = False
            try:
                gl_ver = str(ctx.info.get("GL_VERSION", "?"))
                gpu_name = str(ctx.info.get("GL_RENDERER", "?"))
            except Exception:
                gl_ver, gpu_name = "?", "?"
            try:
                _msaa_txt = str(ctx.info.get("GL_SAMPLES", "?"))
            except Exception:
                _msaa_txt = "?"
            self._init_info = {"gl": gl_ver, "gpu": gpu_name,
                               "surface": self.surf, "transparent": transp,
                               "clickthrough": self._ct,
                               "vsync": self._vsync, "styles": styles,
                               "msaa": _msaa_txt}
            self._ready_ev.set()
            self._log_block(
                "[OVERLAY_STATE] INIT OK (GPU Overlay Renderer)", [
                    "Mode: GPU SHADER ANIMATION — the window NEVER moves",
                    f"Context: {gl_ver} | {gpu_name}",
                    f"Surface (fixed): {sw_}x{sh_} px @ ({sx},{sy})",
                    f"Transparent framebuffer: {'OK' if transp else 'NO(!)'}"
                    f" | Click-through: {'ON' if self._ct else 'OFF'}"
                    f" | VSync: {'ON' if self._vsync else 'OFF'}",
                    f"Win32 styles (once at init): {styles}",
                    "Pipeline: vector scene / texture → fragment shader "
                    "(premultiplied) → DWM",
                    "Commands: upload / scene / show / hide — Show = "
                    "queue.put only",
                ])
            # ---------------- حلقهٔ اصلی رندر ----------------
            while not self._stop:
                if self._anim is not None:
                    _glfw.poll_events()
                    self._drain()
                    if self._stop:
                        break
                    if self._anim is None:
                        continue          # انیمیشن همین حالا تمام/لغو شد
                    self._frame()
                else:
                    # --- IDLE — هیچ CPU Busy Loop: انتظار پیام ---
                    try:
                        cmd = self._q.get(timeout=0.25)
                    except Exception:
                        cmd = None
                    if cmd is None:
                        _glfw.poll_events()
                        continue
                    self._handle(cmd)
                    if self._stop:
                        break
        except Exception as ex:
            self._init_error = f"{type(ex).__name__}: {ex}"
            self._ready_ev.set()
            self._log_block("[OVERLAY_STATE] RENDER THREAD ERROR", [
                self._init_error,
                "GPU overlay disabled — restart uses legacy Tk path.",
            ])
        finally:
            try:
                self._scene_release()
            except Exception:
                pass
            try:
                if self._tex is not None:
                    self._tex.release()
                    self._tex = None
            except Exception:
                pass
            try:
                if self._win is not None and self._glfw is not None:
                    self._glfw.destroy_window(self._win)
            except Exception:
                pass
            try:
                if self._glfw is not None:
                    self._glfw.terminate()
            except Exception:
                pass

    def _win_show(self) -> None:
        """v10.29 (پورت v1.2.2 از 2017) — نمایان‌کردن پنجرهٔ اورلی
        (فقط از ترد رندر). فقط همزمان با شروع واقعی انیمیشن ورود
        صدا زده می‌شود — بین نمایش‌ها هیچ پنجره‌ای روی بازی نیست."""
        if self._win_visible:
            return
        try:
            self._glfw.show_window(self._win)
            self._win_visible = True
        except Exception:
            pass

    def _win_hide(self) -> None:
        """v10.29 (پورت v1.2.2 از 2017) — مخفی‌کردن پنجرهٔ اورلی در
        «سطح خود ویندوز» (فقط از ترد رندر). بعد از آخرین فریم شفافِ
        انیمیشن خروج (یا hide_now) صدا زده می‌شود — حتی اگر ارائهٔ
        فریم شفاف به هر دلیلی ناموفق باشد، خودِ پنجره از صفحه خارج
        می‌شود؛ دیگر هیچ نموداری «تا ابد» در گوشهٔ تصویر نمی‌ماند."""
        if not self._win_visible:
            return
        try:
            self._glfw.hide_window(self._win)
        except Exception:
            pass
        self._win_visible = False

    def _drain(self) -> None:
        try:
            while True:
                cmd = self._q.get_nowait()
                self._handle(cmd)
                if self._stop:
                    return
        except _queue.Empty:
            pass

    def _frame(self) -> None:
        a = self._anim
        if a is None:
            return
        now = time.perf_counter()
        p = (now - a["start"]) / max(1e-6, a["dur"])
        if p >= 1.0:
            p = 1.0
        self._ctx.clear(0.0, 0.0, 0.0, 0.0)
        if self._scene is not None:
            # نسخهٔ ۱۰٫۲۴ — رندر برداری: همهٔ عناصر با همان transform shader
            self._draw_scene_frame(p, a["dir"])
        else:
            self._prog["u_progress"].value = p
            self._prog["u_dir"].value = a["dir"]
            if self._tex is not None:
                self._tex.use(0)
            self._vao.render(self._mg.TRIANGLE_STRIP, vertices=4)
        self._glfw.swap_buffers(self._win)
        a["frames"] += 1
        cpu_ms = (time.perf_counter() - now) * 1000.0
        a["cpu_sum"] += cpu_ms
        a["cpu_max"] = max(a["cpu_max"], cpu_ms)
        if p >= 1.0:
            self._anim_end(a)

    def _draw_scene_frame(self, progress: float, direction: float) -> None:
        """نسخهٔ ۱۰٫۲۴ — یک فریم کامل از صحنهٔ برداری (بدون هیچ آپلود مجدد):
        ترتیب آیتم‌ها = ترتیب zorder قبلی (bg → glow → fill → marker-glow
        → خط صفر/عمودی → خط گل → توپ → پرچم → مُهر). CPU در هر فریم فقط
        uniform می‌فرستد — هیچ Vertex/Texture بازسازی‌شونده‌ای انجام نمی‌شود."""
        edge, tex = self._sprog_edge, self._sprog_tex
        for prog in (edge, tex):
            if prog is None:
                continue
            prog["u_progress"].value = float(progress)
            prog["u_dir"].value = float(direction)
        mg = self._mg
        for it in self._scene:
            try:
                if it["prog"] == "edge":
                    edge["u_color"].value = it["color4"]
                    edge["u_clip_on"].value = 1.0 if it["clip"] else 0.0
                    edge["u_feather"].value = float(it.get("feather", 0.0))
                    it["vao"].render(it["mode"])
                else:
                    it["tex"].use(0)
                    tex["u_tex"].value = 0
                    tex["u_rect"].value = it["rect"]
                    tex["u_clip_on"].value = 1.0 if it["clip"] else 0.0
                    it["vao"].render(it["mode"])
            except Exception:
                continue

    def _scene_release(self) -> None:
        """آزادسازی منابع GL صحنهٔ فعلی (فقط در ترد رندر)."""
        items = self._scene
        self._scene = None
        if not items:
            return
        for it in items:
            try:
                if it.get("vao") is not None:
                    it["vao"].release()
            except Exception:
                pass
            try:
                if it.get("vbo") is not None:
                    it["vbo"].release()
            except Exception:
                pass
            try:
                if it.get("tex") is not None:
                    it["tex"].release()
            except Exception:
                pass

    def _scene_load(self, scene, key, keep_state: bool) -> None:
        """نسخهٔ ۱۰٫۲۴ — تبدیل scene → منابع GL (یک‌بار در Preload):
        Vertex Buffer هر آیتم + Textureها + سه برنامهٔ Shader. بعد از این،
        هر فریم فقط uniform عوض می‌کند (صفر کارِ ساخت در لحظهٔ Show)."""
        t0 = time.perf_counter()
        try:
            ctx = self._ctx
            mg = self._mg
            sw_, sh_ = self.surf[2], self.surf[3]
            if self._sprog_edge is None:
                self._sprog_edge = ctx.program(
                    vertex_shader=_SCENE_VERT_SRC,
                    fragment_shader=_SCENE_EDGE_FRAG_SRC)
            if self._sprog_tex is None:
                self._sprog_tex = ctx.program(
                    vertex_shader=_SCENE_VERT_SRC,
                    fragment_shader=_SCENE_TEX_FRAG_SRC)
            view = tuple(float(v) for v in scene["view"])
            travel = float(scene["place"]["travel"])
            clip = tuple(float(v) for v in scene["clip"])
            parsed = []
            for it in (scene.get("items") or []):
                kind = it.get("kind")
                verts = np.ascontiguousarray(it["verts"], dtype="f4")
                vbo = ctx.buffer(verts.tobytes())
                if kind == "tex":
                    rgba = it["rgba"]
                    tex = ctx.texture((int(it["size"][0]),
                                       int(it["size"][1])), 4, rgba.tobytes())
                    tex.filter = (mg.LINEAR, mg.LINEAR)
                    tex.repeat_x = tex.repeat_y = False
                    vao = ctx.vertex_array(self._sprog_tex,
                                           [(vbo, "2f 1f", "a_px", "a_d")])
                    parsed.append({"prog": "tex", "vao": vao, "vbo": vbo,
                                   "tex": tex, "rect": it["rect"],
                                   "clip": bool(it.get("clip")),
                                   "mode": mg.TRIANGLES,
                                   "count": int(len(verts))})
                else:  # "edge" — نوار/باند با لبهٔ AA تحلیلی
                    vao = ctx.vertex_array(self._sprog_edge,
                                           [(vbo, "2f 1f", "a_px", "a_d")])
                    parsed.append({"prog": "edge", "vao": vao, "vbo": vbo,
                                   "tex": None,
                                   "color4": tuple(float(c) for c in
                                                   it["color4"]),
                                   "clip": bool(it.get("clip")),
                                   "mode": (mg.TRIANGLE_FAN
                                            if it.get("mode") == "fan"
                                            else mg.TRIANGLES),
                                   "count": int(len(verts))})
            self._scene_release()
            self._scene = parsed
            self._cur_travel = travel
            for prog in (self._sprog_edge, self._sprog_tex):
                prog["u_surf"].value = (float(sw_), float(sh_))
                prog["u_view"].value = view
                prog["u_travel"].value = travel
                prog["u_clip"].value = clip
            with self._lock:
                self._tex_key = key
            up_ms = (time.perf_counter() - t0) * 1000.0
            if TV_SNAP_SHOW_DEBUG:
                sx, sy, sw2, sh2 = self.surf
                self._log_block(
                    "[OVERLAY_STATE] VECTOR SCENE LOADED (GPU)", [
                        f"Items: {len(parsed)} | verts: "
                        f"{sum(p['count'] for p in parsed)} | "
                        f"GL build: {up_ms:.2f} ms | key={key}",
                        f"Placement: img @({view[0]:.0f},{view[1]:.0f}) "
                        f"scale k={view[2]:.4f} inside fixed surface "
                        f"{sw2}x{sh2} @({sx},{sy}) | travel={travel:.0f}px",
                        "State → READY (scene prepared; screen still clear)",
                    ])
            if self._anim is None:
                if self._visible_img and keep_state:
                    # re-blit فوری (retune در جریان نمایش) — همان مکان
                    self._ctx.clear(0.0, 0.0, 0.0, 0.0)
                    self._draw_scene_frame(1.0, 1.0)
                    self._glfw.swap_buffers(self._win)
                elif self._visible_img:
                    self._ctx.clear(0.0, 0.0, 0.0, 0.0)
                    self._draw_scene_frame(1.0, 1.0)
                    self._glfw.swap_buffers(self._win)
                else:
                    self._set_state(self.ST_READY if key else self.ST_HIDDEN)
        except Exception as ex:
            self._log_block("[OVERLAY_STATE] VECTOR SCENE LOAD FAILED", [
                f"key={key} | {type(ex).__name__}: {ex}",
            ])

    def _anim_end(self, a) -> None:
        total_ms = (time.perf_counter() - a["start"]) * 1000.0
        fps = a["frames"] / max(1e-6, total_ms / 1000.0)
        entering = a["dir"] > 0
        self._set_state(self.ST_VISIBLE if entering else self.ST_HIDDEN)
        self._visible_img = bool(entering)
        self._anim = None
        if not entering:
            # v10.29 (پورت v1.2.2 از 2017) — پایان انیمیشن خروج: آخرین
            # فریم (کاملاً شفاف) همین حالا ارائه شده است — پنجره در سطح
            # خود ویندوز مخفی می‌شود؛ حتی اگر ارائهٔ فریم بعدی به هر
            # دلیلی ناموفق باشد، نمودار از صفحه خارج شده است.
            self._win_hide()
        elif self._hide_pending:
            # v10.29 — hide در جریان انیمیشن ورود رسیده بود و (در نسخهٔ
            # قبلی) کاملاً drop می‌شد؛ اگر زنجیرهٔ after طرف UI هم گم
            # می‌شد، نمودار تا ابد روی صفحه می‌ماند. حالا همین‌جا
            # انیمیشن خروج با همان سبک/مدت شروع می‌شود (خروج نرم حفظ
            # می‌شود) و پایانش _win_hide را هم در بر دارد.
            self._hide_pending = False
            self._anim = {"start": time.perf_counter(),
                          "dur": max(1e-3, TV_SNAP_ANIM_MS / 1000.0),
                          "dir": -1.0, "frames": 0, "cpu_sum": 0.0,
                          "cpu_max": 0.0, "key": a.get("key")}
            self._set_state(self.ST_ANIM)
        tag = "ENTRY" if entering else "EXIT"
        try:
            with self._lock:
                self._anim_stats = {
                    "tag": tag, "key": a.get("key"),
                    "frames": a["frames"], "total_ms": total_ms,
                    "fps": fps,
                    "cpu_avg_ms": a["cpu_sum"] / max(1, a["frames"]),
                    "cpu_max_ms": a["cpu_max"], "swp_calls": 0,
                    "window_moved": False}
        except Exception:
            pass
        if TV_SNAP_SHOW_DEBUG and self._adebug:
            self._log_block(f"[OVERLAY ANIM DEBUG] {tag} (GPU shader)", [
                f"key: {a.get('key')}",
                f"Duration: {total_ms:.1f} ms (target "
                f"{a['dur'] * 1000.0:.0f}) | Frames: {a['frames']} "
                f"| ≈{fps:.1f} fps (paced by vsync)",
                f"CPU frame time: avg "
                f"{a['cpu_sum'] / max(1, a['frames']):.3f} ms "
                f"| max {a['cpu_max']:.3f} ms",
                "SetWindowPos calls in this animation: 0",
                "Window moved: NO — fixed surface; motion is GPU shader only",
            ])

    def _handle(self, cmd) -> None:
        kind = cmd[0]
        if kind == "upload":
            (_, raw, w, h, dx, dy, travel, key, keep_state) = cmd
            t0 = time.perf_counter()
            try:
                # نسخهٔ ۱۰٫۲۴ — بیت‌مپ جایگزین scene می‌شود (مسیرهای دو مسیره)
                self._scene_release()
                if self._tex is not None:
                    self._tex.release()
                    self._tex = None
                tex = self._ctx.texture((w, h), 4, raw)
                tex.filter = (self._mg.LINEAR, self._mg.LINEAR)
                tex.repeat_x = tex.repeat_y = False
                tex.use(0)
                self._tex = tex
                self._cur_travel = float(travel)
                self._prog["u_tex"].value = 0
                self._prog["u_tex_size"].value = (float(w), float(h))
                self._prog["u_img"].value = (float(dx), float(dy))
                self._prog["u_travel"].value = float(travel)
                with self._lock:
                    self._tex_key = key
                up_ms = (time.perf_counter() - t0) * 1000.0
                sx, sy, sw_, sh_ = self.surf
                if TV_SNAP_SHOW_DEBUG:
                    self._log_block(
                        "[OVERLAY_STATE] TEXTURE UPLOADED (GPU)", [
                            f"Size: {w}x{h} px | upload: {up_ms:.2f} ms "
                            f"| key={key}",
                            f"Placement: img @({dx},{dy}) inside fixed "
                            f"surface {sw_}x{sh_} @({sx},{sy}) "
                            f"| travel={travel}px",
                            "State → READY (texture prepared; screen "
                            "still clear)",
                        ])
                if self._anim is None:
                    if self._visible_img:
                        # re-blit فوری (retune در جریان نمایش) — همان مکان
                        self._prog["u_progress"].value = 1.0
                        self._prog["u_dir"].value = 1.0
                        self._ctx.clear(0.0, 0.0, 0.0, 0.0)
                        tex.use(0)
                        self._vao.render(self._mg.TRIANGLE_STRIP,
                                         vertices=4)
                        self._glfw.swap_buffers(self._win)
                    else:
                        self._set_state(self.ST_READY if key
                                        else self.ST_HIDDEN)
            except Exception as ex:
                self._log_block("[OVERLAY_STATE] TEXTURE UPLOAD FAILED", [
                    f"key={key} | {type(ex).__name__}: {ex}",
                ])
        elif kind == "scene":
            # نسخهٔ ۱۰٫۲۴ — صحنهٔ برداری (build_gpu_graph_scene در ترد Worker)
            (_, _scene_data, key, keep_state) = cmd
            try:
                if self._tex is not None:
                    self._tex.release()
                    self._tex = None
            except Exception:
                pass
            self._scene_load(_scene_data, key, bool(keep_state))
        elif kind == "show":
            (_, dur, put_t, key) = cmd
            if self._tex is None and self._scene is None:
                self._log_block("[OVERLAY_STATE] SHOW IGNORED (no texture)",
                                [f"key={key} — upload must happen first"])
                return
            lat_ms = (time.perf_counter() - put_t) * 1000.0
            # v10.29 (پورت v1.2.2 از 2017) — پنجره فقط در لحظهٔ Show
            # واقعی نمایان می‌شود؛ show تازه هر hide معلقی را هم باطل
            # می‌کند (باگ «نمودار تا ابد ماند» — خروج تضمینی).
            self._win_show()
            self._hide_pending = False
            self._anim = {"start": time.perf_counter(),
                          "dur": max(1e-3, dur), "dir": 1.0,
                          "frames": 0, "cpu_sum": 0.0, "cpu_max": 0.0,
                          "key": key}
            self._set_state(self.ST_ANIM)
            if TV_SNAP_SHOW_DEBUG:
                travel = float(getattr(self, "_cur_travel", 0.0))
                self._log_block(
                    "[OVERLAY_STATE] SHOW — entry animation (GPU)", [
                        f"time={time.time():.2f} | key={key} | "
                        f"queue→render latency: {lat_ms:.3f} ms",
                        f"Duration: {dur * 1000.0:.0f} ms | travel: "
                        f"{travel:.0f}px (below-screen → final) | "
                        "Window: FIXED (no movement)",
                    ])
        elif kind == "hide":
            (_, dur, put_t) = cmd
            if self._anim is not None:
                # v10.29 — قبلاً اینجا hide «کاملاً رها» می‌شد؛ اگر زنجیرهٔ
                # after طرف UI هم گم می‌شد، نمودار برای همیشه روی صفحه
                # می‌ماند (ریشهٔ باگ «نمودار 116 نمایش داده شد و تمام
                # نشد»). حالا ثبت می‌شود و بلافاصله پس از پایان انیمیشن
                # جاری، خروج نرم اجرا می‌شود (_anim_end → _hide_pending).
                self._hide_pending = True
                return
            if ((self._tex is None and self._scene is None)
                    or not self._visible_img):
                self._set_state(self.ST_HIDDEN)
                return
            self._anim = {"start": time.perf_counter(),
                          "dur": max(1e-3, dur), "dir": -1.0,
                          "frames": 0, "cpu_sum": 0.0, "cpu_max": 0.0,
                          "key": self._tex_key}
            self._set_state(self.ST_ANIM)
            if TV_SNAP_SHOW_DEBUG:
                self._log_block(
                    "[OVERLAY_STATE] HIDE — exit animation (GPU)", [
                        f"time={time.time():.2f} | key={self._tex_key} | "
                        f"queue→render latency: "
                        f"{(time.perf_counter() - put_t) * 1000.0:.3f} ms",
                        f"Duration: {dur * 1000.0:.0f} ms "
                        "(final → below-screen) | Window: FIXED",
                    ])
        elif kind == "hide_now":
            self._anim = None
            self._hide_pending = False   # v10.29 — پاک‌سازی hide معلق
            was = self._visible_img
            self._visible_img = False
            self._set_state(self.ST_HIDDEN)
            if was and (self._tex is not None or self._scene is not None) \
                    and self._glfw is not None:
                # یک فریم کاملاً شفاف ارائه کن
                try:
                    self._ctx.clear(0.0, 0.0, 0.0, 0.0)
                    self._glfw.swap_buffers(self._win)
                except Exception:
                    pass
                if TV_SNAP_SHOW_DEBUG:
                    self._log_block("[OVERLAY_STATE] HIDDEN (hide_now — GPU)",
                                    ["Transparent frame presented — "
                                     "screen fully clear"])
            # v10.29 (پورت v1.2.2 از 2017) — پنجره در هر حالت در سطح خود
            # ویندوز مخفی می‌شود (حتی بدون محتوا) — تضمین ساختاری خروج
            # همهٔ نمودارها بعد از زمان مشخص‌شده.
            self._win_hide()
        elif kind == "stop":
            self._stop = True


# =====================================================================
# 25.5b — v2.0.1 WIN32 FALLBACK OVERLAY (no moderngl / glfw / Tk needed)
# ---------------------------------------------------------------------
# This headless build has exactly one display path: GPUOverlayRenderer.
# If it cannot boot (moderngl/glfw missing, GL context refused, no
# transparent framebuffer), the legacy Tk path dead-ends silently in a
# GUI-less build and NO chart is ever displayed — the reported
# "transparent window never appears" bug. This renderer is the safety
# net: a pure-ctypes Win32 layered window that presents the same chart
# bitmap with the same slide animation. Zero optional dependencies,
# Windows-only (like the whole project).
#
# It duck-types GPUOverlayRenderer, so the whole show pipeline
# (preload -> upload -> show -> hide) runs unchanged: _gpu_overlay_boot
# falls back to this class and the _show/_hide_snapshot_overlay_gpu
# methods keep working verbatim.
# =====================================================================
class Win32OverlayRenderer:
    """v2.0.1 — GDI layered-window overlay (UpdateLayeredWindow).

    State machine identical to GPUOverlayRenderer:
      HIDDEN -> READY -> ANIMATING(entry) -> VISIBLE -> ANIMATING(exit) -> HIDDEN

    Thread model identical: commands are queue.put only; the renderer
    thread owns the HWND and does all window/GDI work. The window is
    visible ONLY during a real show cycle (v10.29 policy)."""

    ST_HIDDEN = "HIDDEN"
    ST_READY = "READY"
    ST_VISIBLE = "VISIBLE"
    ST_ANIM = "ANIMATING"

    # vector scenes are a GPU-only feature (GL AA shaders); the fallback
    # rejects them and the pipeline transparently falls back to the bitmap
    supports_scene = False

    _CLASS_NAME = "MomentumWin32Overlay"

    def __init__(self, surf_x, surf_y, surf_w, surf_h,
                 click_through=True, vsync=True, anim_debug=True):
        self.surf = (int(surf_x), int(surf_y), int(surf_w), int(surf_h))
        self._ct = bool(click_through)
        self._adebug = bool(anim_debug)
        self._q = _queue.Queue()
        self._lock = threading.Lock()
        self._state = self.ST_HIDDEN
        self._tex_key = None
        self._ready_ev = threading.Event()
        self._init_error = None
        self._init_info = {}
        self._stop = False
        self._anim = None
        self._visible_img = False
        self._win_visible = False
        self._hide_pending = False
        self._anim_stats = {}
        # render-thread-owned resources (touched only inside _run)
        self._hwnd = None
        self._hdc_mem = None
        self._hbmp = None
        self._hbmp_old = None
        self._bmp_w = self._bmp_h = 0
        self._cur_bgra = None
        # image placement in screen coordinates (set by upload)
        self._img_w = self._img_h = 0
        self._img_x = self._img_y = 0
        self._travel = 0
        self._wndproc_ref = None
        self._thread = threading.Thread(target=self._run,
                                        name="win32-overlay", daemon=True)
        self._thread.start()

    # ---------- thread-safe API (non-blocking, messages only) ----------
    def wait_init(self, timeout: float = 4.0) -> bool:
        self._ready_ev.wait(timeout)
        return self._init_error is None

    def init_error(self) -> Optional[str]:
        return self._init_error

    def init_info(self) -> dict:
        return dict(self._init_info)

    def state(self) -> str:
        with self._lock:
            return self._state

    def texture_key(self) -> Optional[str]:
        with self._lock:
            return self._tex_key

    def is_alive(self) -> bool:
        return bool(self._thread.is_alive() and self._init_error is None)

    def last_anim_stats(self) -> dict:
        with self._lock:
            return dict(self._anim_stats)

    def _set_state(self, st: str) -> None:
        with self._lock:
            self._state = st

    def _put(self, cmd) -> None:
        try:
            self._q.put_nowait(cmd)
        except Exception:
            pass

    def upload_png_rgba(self, raw, w, h, dx, dy, travel, key,
                        keep_state: bool = False) -> None:
        """Upload/replace the chart bitmap (preload / retune) — message."""
        self._put(("upload", bytes(raw), int(w), int(h), int(dx), int(dy),
                   int(travel), key, bool(keep_state)))

    def upload_scene(self, scene, key=None, keep_state: bool = False) -> None:
        """Vector scenes are GPU-only — the pipeline catches this and uses
        the bitmap path instead."""
        raise RuntimeError("vector scene unsupported by Win32 fallback — "
                           "use the bitmap path")

    def show(self, dur_ms: int = TV_SNAP_ANIM_MS, key=None) -> float:
        t = time.perf_counter()
        self._put(("show", float(max(0.0, dur_ms)) / 1000.0, t, key))
        return t

    def hide(self, dur_ms: int = TV_SNAP_ANIM_MS) -> None:
        self._put(("hide", float(max(0.0, dur_ms)) / 1000.0,
                   time.perf_counter()))

    def hide_now(self) -> None:
        self._put(("hide_now", time.perf_counter()))

    def shutdown(self, timeout: float = 1.0) -> None:
        self._put(("stop",))
        try:
            self._thread.join(max(0.05, timeout))
        except Exception:
            pass

    # ---------------- renderer thread ----------------
    def _log_block(self, title: str, lines) -> None:
        if not TV_SNAP_SHOW_DEBUG:
            return
        try:
            print("=" * 60, flush=True)
            print(title, flush=True)
            print("=" * 60, flush=True)
            for ln in lines:
                print(ln, flush=True)
            print("=" * 60, flush=True)
        except Exception:
            pass

    def _run(self):
        try:
            if sys.platform != "win32":
                self._init_error = "win32-only renderer (non-Windows)"
                self._ready_ev.set()
                return
            self._boot_window()
            self._ready_ev.set()
            self._log_block(
                "[OVERLAY_STATE] INIT OK (Win32 Fallback Overlay)", [
                    "Mode: GDI LAYERED WINDOW — UpdateLayeredWindow",
                    f"Surface (fixed): {self.surf[2]}x{self.surf[3]} px "
                    f"@ ({self.surf[0]},{self.surf[1]})",
                    f"Click-through: {'ON' if self._ct else 'OFF'}",
                    "Pipeline: RGBA bitmap -> premultiplied BGRA DIB -> "
                    "UpdateLayeredWindow -> DWM",
                    "Commands: upload / show / hide / hide_now",
                ])
            while not self._stop:
                if self._anim is not None:
                    self._pump_messages()
                    self._drain()
                    if self._stop:
                        break
                    if self._anim is None:
                        continue
                    self._anim_step()
                else:
                    self._pump_wait(0.25)
                    self._drain()
        except Exception as ex:
            self._init_error = f"{type(ex).__name__}: {ex}"
            self._ready_ev.set()
            self._log_block("[OVERLAY_STATE] RENDER THREAD ERROR (Win32)", [
                self._init_error,
            ])
        finally:
            try:
                self._destroy_window()
            except Exception:
                pass

    def _drain(self) -> None:
        try:
            while True:
                cmd = self._q.get_nowait()
                self._handle(cmd)
                if self._stop:
                    return
        except _queue.Empty:
            pass

    def _handle(self, cmd) -> None:
        kind = cmd[0]
        if kind == "upload":
            (_, raw, w, h, dx, dy, travel, key, keep_state) = cmd
            self._handle_upload(raw, w, h, dx, dy, travel, key, keep_state)
        elif kind == "show":
            (_, dur, put_t, key) = cmd
            if self._cur_bgra is None:
                self._log_block("[OVERLAY_STATE] SHOW IGNORED (no bitmap)",
                                [f"key={key} — upload must happen first"])
                return
            lat_ms = (time.perf_counter() - put_t) * 1000.0
            # park below the screen BEFORE the window becomes visible —
            # no flash at the final position
            self._move_window(self._img_y + self._travel)
            self._win_show()
            self._hide_pending = False
            self._anim = {"start": time.perf_counter(),
                          "dur": max(1e-3, dur), "dir": 1.0, "frames": 0,
                          "key": key,
                          "y_start": self._img_y + self._travel,
                          "y_end": self._img_y}
            self._set_state(self.ST_ANIM)
            if TV_SNAP_SHOW_DEBUG:
                self._log_block(
                    "[OVERLAY_STATE] SHOW — entry animation (Win32)", [
                        f"time={time.time():.2f} | key={key} | "
                        f"queue->window latency: {lat_ms:.3f} ms",
                        f"Duration: {dur * 1000.0:.0f} ms | travel: "
                        f"{self._travel}px (below-screen -> final)",
                    ])
        elif kind == "hide":
            (_, dur, put_t) = cmd
            if self._anim is not None:
                self._hide_pending = True
                return
            if not self._visible_img:
                self._win_hide()
                self._set_state(self.ST_HIDDEN)
                return
            self._anim = {"start": time.perf_counter(),
                          "dur": max(1e-3, dur), "dir": -1.0, "frames": 0,
                          "key": self._tex_key,
                          "y_start": self._img_y,
                          "y_end": self._img_y + self._travel}
            self._set_state(self.ST_ANIM)
        elif kind == "hide_now":
            self._anim = None
            self._hide_pending = False
            self._visible_img = False
            self._win_hide()
            self._set_state(self.ST_HIDDEN)
        elif kind == "stop":
            self._stop = True

    def _anim_step(self) -> None:
        a = self._anim
        if a is None:
            return
        p = (time.perf_counter() - a["start"]) / max(1e-6, a["dur"])
        if p >= 1.0:
            p = 1.0
        eased = p * p * (3.0 - 2.0 * p)     # smoothstep, like the shader
        y = a["y_start"] + (a["y_end"] - a["y_start"]) * eased
        self._move_window(int(y))
        a["frames"] += 1
        if p >= 1.0:
            self._anim_end(a)
        else:
            time.sleep(0.015)               # ~60 fps pacing

    def _anim_end(self, a) -> None:
        total_ms = (time.perf_counter() - a["start"]) * 1000.0
        entering = a["dir"] > 0
        self._anim = None
        if entering:
            self._visible_img = True
            self._set_state(self.ST_VISIBLE)
        else:
            self._visible_img = False
            self._win_hide()
            self._set_state(self.ST_HIDDEN)
        if not entering and self._hide_pending:
            pass                            # already hidden — state cleared
        try:
            with self._lock:
                self._anim_stats = {
                    "tag": "ENTRY" if entering else "EXIT",
                    "key": a.get("key"), "frames": a["frames"],
                    "total_ms": total_ms, "fps": a["frames"]
                    / max(1e-6, total_ms / 1000.0),
                    "window_moved": True}
        except Exception:
            pass
        if TV_SNAP_SHOW_DEBUG and self._adebug:
            self._log_block(
                f"[OVERLAY ANIM DEBUG] "
                f"{'ENTRY' if entering else 'EXIT'} (Win32)", [
                    f"key: {a.get('key')}",
                    f"Duration: {total_ms:.1f} ms | Frames: {a['frames']}",
                ])

    # ---------------- win32 plumbing ----------------
    def _boot_window(self):
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        kernel32 = ctypes.windll.kernel32
        self._user32, self._gdi32, self._kernel32 = user32, gdi32, kernel32

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, wintypes.HWND,
                                     wintypes.UINT, wintypes.WPARAM,
                                     wintypes.LPARAM)

        def _wproc(hwnd, msg, wparam, lparam):
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_ref = WNDPROC(_wproc)     # keep reference (no GC)

        hinst = kernel32.GetModuleHandleW(None)
        wndclass = wintypes.WNDCLASSW()
        wndclass.lpfnWndProc = self._wndproc_ref
        wndclass.hInstance = hinst
        wndclass.hCursor = user32.LoadCursorW(None, 32512)  # IDC_ARROW
        wndclass.lpszClassName = self._CLASS_NAME
        if not user32.RegisterClassW(ctypes.byref(wndclass)):
            # already registered from a previous boot — fine
            err = kernel32.GetLastError()
            if err != 1410:                     # ERROR_CLASS_ALREADY_EXISTS
                raise OSError(f"RegisterClassW failed (err={err})")

        WS_POPUP = 0x80000000
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        WS_EX_NOACTIVATE = 0x08000000
        WS_EX_TOOLWINDOW = 0x00000080
        ex = (WS_EX_LAYERED | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        if self._ct:
            ex |= WS_EX_TRANSPARENT
        hwnd = user32.CreateWindowExW(ex, self._CLASS_NAME, "", WS_POPUP,
                                      0, 0, 100, 100, None, None, hinst,
                                      None)
        if not hwnd:
            raise OSError(f"CreateWindowExW failed "
                          f"(err={kernel32.GetLastError()})")
        self._hwnd = hwnd
        # topmost once at init (same policy as the GPU overlay styles)
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        user32.ShowWindow(hwnd, 0)              # SW_HIDE
        self._win_visible = False

        hdc_screen = user32.GetDC(None)
        self._hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        user32.ReleaseDC(None, hdc_screen)

        self._init_info = {
            "gl": "GDI (UpdateLayeredWindow)", "gpu": "DWM compositor",
            "surface": self.surf, "transparent": True,
            "clickthrough": self._ct, "vsync": False,
            "styles": "LAYERED|NOACTIVATE|TOOLWINDOW"
                      + ("|TRANSPARENT" if self._ct else "")
                      + " | TOPMOST (once at init)",
            "msaa": "n/a"}

    def _destroy_window(self):
        try:
            if self._hbmp and self._gdi32:
                self._gdi32.DeleteObject(self._hbmp)
                self._hbmp = None
            if self._hdc_mem and self._gdi32:
                self._gdi32.DeleteDC(self._hdc_mem)
                self._hdc_mem = None
            if self._hwnd and self._user32:
                self._user32.DestroyWindow(self._hwnd)
                self._user32.UnregisterClassW(self._CLASS_NAME, None)
                self._hwnd = None
        except Exception:
            pass

    def _win_show(self) -> None:
        if self._win_visible or not self._hwnd:
            return
        try:
            self._user32.ShowWindow(self._hwnd, 5)  # SW_SHOW
            self._win_visible = True
        except Exception:
            pass

    def _win_hide(self) -> None:
        if not self._win_visible or not self._hwnd:
            return
        try:
            self._user32.ShowWindow(self._hwnd, 0)  # SW_HIDE
        except Exception:
            pass
        self._win_visible = False

    def _move_window(self, y: int) -> None:
        if not self._hwnd:
            return
        try:
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            SWP_NOACTIVATE = 0x0010
            self._user32.SetWindowPos(self._hwnd, None, self._img_x,
                                      int(y), 0, 0,
                                      SWP_NOSIZE | SWP_NOZORDER
                                      | SWP_NOACTIVATE)
        except Exception:
            pass

    def _handle_upload(self, raw, w, h, dx, dy, travel, key,
                       keep_state) -> None:
        t0 = time.perf_counter()
        bgra = self._rgba_to_premultiplied_bgra(raw, w, h)
        if bgra is None:
            self._log_block("[OVERLAY_STATE] UPLOAD FAILED (Win32)", [
                f"key={key} | {w}x{h} — RGBA conversion failed"])
            return
        sx, sy, _, _ = self.surf
        self._img_w, self._img_h = int(w), int(h)
        self._img_x = sx + int(dx)
        self._img_y = sy + int(dy)
        self._travel = max(1, int(travel))
        self._cur_bgra = bgra
        with self._lock:
            self._tex_key = key
        self._update_layered()
        up_ms = (time.perf_counter() - t0) * 1000.0
        if self._anim is None:
            if self._visible_img and self._win_visible:
                # live re-blit (retune during show) — bitmap already swapped
                pass
            else:
                self._set_state(self.ST_READY if key else self.ST_HIDDEN)
        if TV_SNAP_SHOW_DEBUG:
            self._log_block("[OVERLAY_STATE] TEXTURE UPLOADED (Win32)", [
                f"Size: {w}x{h} px | upload+blit: {up_ms:.2f} ms | key={key}",
                f"Placement: final @({self._img_x},{self._img_y}) | "
                f"travel={self._travel}px | State -> READY",
            ])

    @staticmethod
    def _rgba_to_premultiplied_bgra(raw, w, h):
        """Straight RGBA bytes -> premultiplied BGRA bytes (DWM needs
        premultiplied alpha with AC_SRC_ALPHA)."""
        try:
            arr = np.frombuffer(bytes(raw), dtype=np.uint8)
            if arr.size != int(w) * int(h) * 4:
                return None
            arr = arr.reshape(int(h), int(w), 4)
            a = arr[:, :, 3:4].astype(np.uint16)
            rgb = (arr[:, :, :3].astype(np.uint16) * a + 127) // 255
            out = np.empty((int(h), int(w), 4), dtype=np.uint8)
            out[:, :, 0] = rgb[:, :, 2]         # B
            out[:, :, 1] = rgb[:, :, 1]         # G
            out[:, :, 2] = rgb[:, :, 0]         # R
            out[:, :, 3] = arr[:, :, 3]         # A
            return out.tobytes()
        except Exception:
            return None

    def _update_layered(self) -> None:
        """(Re)create the DIB for the current bitmap and push it to the
        layered window at the final position (window is hidden at upload
        time; during a live re-blit the position stays untouched)."""
        user32, gdi32 = self._user32, self._gdi32
        w, h = self._img_w, self._img_h
        if not self._hwnd or not self._hdc_mem or w <= 0 or h <= 0:
            return

        class BMIH(ctypes.Structure):
            _fields_ = [("biSize", wintypes.DWORD),
                        ("biWidth", wintypes.LONG),
                        ("biHeight", wintypes.LONG),
                        ("biPlanes", wintypes.WORD),
                        ("biBitCount", wintypes.WORD),
                        ("biCompression", wintypes.DWORD),
                        ("biSizeImage", wintypes.DWORD),
                        ("biXPelsPerMeter", wintypes.LONG),
                        ("biYPelsPerMeter", wintypes.LONG),
                        ("biClrUsed", wintypes.DWORD),
                        ("biClrImportant", wintypes.DWORD)]

        bmi = BMIH()
        bmi.biSize = ctypes.sizeof(BMIH)
        bmi.biWidth = w
        bmi.biHeight = -h                       # top-down
        bmi.biPlanes = 1
        bmi.biBitCount = 32
        bmi.biCompression = 0                   # BI_RGB

        bits = ctypes.c_void_p()
        hdc_screen = user32.GetDC(None)
        try:
            hbmp = gdi32.CreateDIBSection(hdc_screen, ctypes.byref(bmi),
                                          0, ctypes.byref(bits), None, 0)
        finally:
            user32.ReleaseDC(None, hdc_screen)
        if not hbmp or not bits:
            raise OSError("CreateDIBSection failed")
        old_bmp = gdi32.SelectObject(self._hdc_mem, hbmp)
        if self._hbmp and self._hbmp != hbmp:
            try:
                gdi32.DeleteObject(self._hbmp)
            except Exception:
                pass
        self._hbmp = hbmp
        self._hbmp_old = old_bmp
        ctypes.memmove(bits, self._cur_bgra, w * h * 4)

        class PT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class SZ(ctypes.Structure):
            _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]

        class BLEND(ctypes.Structure):
            _fields_ = [("BlendOp", wintypes.BYTE),
                        ("BlendFlags", wintypes.BYTE),
                        ("SourceConstantAlpha", wintypes.BYTE),
                        ("AlphaFormat", wintypes.BYTE)]

        pt_dst = PT(self._img_x, self._img_y)
        pt_src = PT(0, 0)
        size = SZ(w, h)
        blend = BLEND(0, 0, 255, 1)             # AC_SRC_OVER, AC_SRC_ALPHA
        ULW_ALPHA = 0x02
        hdc_screen = user32.GetDC(None)
        try:
            ok = user32.UpdateLayeredWindow(
                self._hwnd, hdc_screen, ctypes.byref(pt_dst),
                ctypes.byref(size), self._hdc_mem, ctypes.byref(pt_src),
                0, ctypes.byref(blend), ULW_ALPHA)
        finally:
            user32.ReleaseDC(None, hdc_screen)
        if not ok:
            err = self._kernel32.GetLastError()
            self._log_block("[OVERLAY_STATE] UpdateLayeredWindow FAILED", [
                f"err={err} | size {w}x{h} @ ({self._img_x},{self._img_y})"])

    def _pump_messages(self) -> None:
        try:
            msg = wintypes.MSG()
            PM_REMOVE = 0x0001
            while self._user32.PeekMessageW(ctypes.byref(msg), None, 0, 0,
                                            PM_REMOVE):
                self._user32.TranslateMessage(ctypes.byref(msg))
                self._user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass

    def _pump_wait(self, timeout_s: float) -> None:
        """Idle wait: message-aware, no busy loop."""
        try:
            QS_ALLINPUT = 0x04FF
            MWMO_INPUTAVAILABLE = 0x0004
            self._user32.MsgWaitForMultipleObjectsEx(
                0, None, int(timeout_s * 1000), QS_ALLINPUT,
                MWMO_INPUTAVAILABLE)
        except Exception:
            time.sleep(min(0.25, timeout_s))
        self._pump_messages()

# =====================================================================
# ۲۵٫۶ — رندر برداری GPU برای نمودار (نسخهٔ ۱۰٫۲۴ — درخواست کاربر)
# ---------------------------------------------------------------------
# «نمودار قبل از رسیدن به GPU تبدیل به Bitmap می‌شود؛ در نتیجه Shader
#  نمی‌تواند Anti-Aliasing واقعی روی منحنی انجام دهد.» (گزارش کاربر)
#
# پاسخ معماری — Pipeline جدید:
#   Momentum Data ──► _tv_curve_core (همان ریاضی قبلی — بدون تغییر شکل)
#        ──► Vertex Buffer (پنل px) ──► GPU Draw ──► Fragment Shader AA
#        ──► GPU Surface ──► Overlay (انیمیشن Shader — عین ۱۰٫۲۳)
#
#   * خط/fill: هر ناحیه با «فاصلهٔ علامت‌دار تا مرز» (v_d) ساخته می‌شود؛
#     Fragment Shader آلفای لبه را با smoothstep حساب می‌کند (AA واقعی،
#     مستقل از رزولوشن، بدون Supersampling).
#   * عناصر نرم (پس‌زمینه، درخشش بلورشده، پرچم، توپ، مُهر) طبیعتاً تصویرند
#     و مثل قبل Texture می‌مانند (درخشش خودِ بلور گاوسی است — دندانه ندارد).
#   * Matplotlib از مسیر «نمایش» حذف می‌شود؛ فقط تولید تصویر ثابت
#     (ذخیرهٔ دائمی/تب اصلی) باقی می‌ماند.
#   * هر دو مسیر از یک ریاضی مشترک (_tv_curve_core) تغذیه می‌شوند تا شکل
#     نمودار «مو‌به‌مو» همان قبلی باشد (تغییر شکل ممنوع — شرط کاربر).
# =====================================================================

_SCENE_VERT_SRC = """
#version 330 core
layout(location = 0) in vec2 a_px;      // مختصات در فضای پنل (px تصویر مرجع)
layout(location = 1) in float a_d;      // فاصلهٔ علامت‌دار تا مرز (px پنل؛ منفی = داخل)
uniform vec2  u_surf;                   // اندازهٔ سطح ثابت (px)
uniform vec3  u_view;                   // (dx, dy, k) — نگاشت پنل → سطح
uniform float u_travel;                 // فاصلهٔ عمودی حرکت (px سطح)
uniform float u_progress;               // 0..1 — CPU فقط زمان می‌فرستد
uniform float u_dir;                    // +1 ورود | -1 خروج
out vec2  v_px;
out float v_d;
float ease_in_out(float p) {            // عیناً snap_ease_in_out (۱۰٫۱۳)
    p = clamp(p, 0.0, 1.0);
    if (p < 0.5) return 4.0 * p * p * p;
    float q = 2.0 * p - 2.0;
    return 1.0 + 0.5 * q * q * q;
}
void main() {
    v_px = a_px;
    v_d = a_d;
    float e = ease_in_out(u_progress);
    float t = (u_dir > 0.0) ? (1.0 - e) : e;   // ۱ = زیر صفحه | ۰ = مکان نهایی
    vec2 sp = vec2(u_view.x + a_px.x * u_view.z,
                   u_view.y + a_px.y * u_view.z + t * u_travel);
    float cx = (sp.x / u_surf.x) * 2.0 - 1.0;
    float cy = 1.0 - (sp.y / u_surf.y) * 2.0;
    gl_Position = vec4(cx, cy, 0.0, 1.0);
}
"""

_SCENE_EDGE_FRAG_SRC = """
#version 330 core
in vec2  v_px;
in float v_d;                           // فاصلهٔ علامت‌دار تا مرز (px پنل)
uniform vec4  u_color;                  // rgb + آلفای پایه
uniform vec4  u_clip;                   // (x0, y0, x1, y1) در فضای پنل
uniform float u_clip_on;
uniform vec3  u_view;                   // فقط k لازم است
uniform float u_feather;                // نسخهٔ ۱۰٫۲۶ — نرمی اضافهٔ لبه (px سطح؛ ۰=خاموش)
out vec4 frag;
void main() {
    if (u_clip_on > 0.5) {
        if (v_px.x < u_clip.x || v_px.x > u_clip.z ||
            v_px.y < u_clip.y || v_px.y > u_clip.w) {
            discard;
        }
    }
    float s  = v_d * u_view.z;          // فاصله در px سطح
    float aa = clamp(fwidth(s) * 0.8, 0.4, 1.5);
    aa = max(aa, u_feather);            // feather فقط برای fill (لبهٔ مخملی — عین مرجع کاربر)
    float a  = u_color.a * (1.0 - smoothstep(-aa, aa, s));
    a = clamp(a, 0.0, 1.0);
    frag = vec4(u_color.rgb * a, a);    // premultiplied برای DWM
}
"""

_SCENE_TEX_FRAG_SRC = """
#version 330 core
in vec2  v_px;
in float v_d;
uniform sampler2D u_tex;
uniform vec4  u_rect;                   // (x0, y0, x1, y1) در فضای پنل
uniform vec4  u_clip;
uniform float u_clip_on;
out vec4 frag;
void main() {
    if (u_clip_on > 0.5) {
        if (v_px.x < u_clip.x || v_px.x > u_clip.z ||
            v_px.y < u_clip.y || v_px.y > u_clip.w) {
            discard;
        }
    }
    vec2 uv = (v_px - u_rect.xy) / max(vec2(1e-6), u_rect.zw - u_rect.xy);
    vec4 c = texture(u_tex, clamp(uv, 0.0, 1.0));
    frag = vec4(c.rgb * c.a, c.a);      // premultiplied برای DWM
}
"""


