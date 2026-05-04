"""Real-time gait recognition view with live confidence chart and profile photo."""
import io
import tkinter as tk
from tkinter import messagebox
from collections import deque

from gui.theme import COLORS, FONTS, make_btn
from src.utils import open_camera, frame_to_photoimage, placeholder_frame
from src.pose_estimator import PoseEstimator
from src.feature_extractor import GaitFeatureExtractor, FEATURE_SIZE

BUFFER_FRAMES = 90
INFER_EVERY   = 20
DISPLAY_FPS   = 30


class RecognizeView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db         = db
        self.recognizer = recognizer

        self._cap      = None
        self._pose     = None
        self._extractor = GaitFeatureExtractor()
        self._running  = False
        self._after_id = None
        self._frame_idx = 0

        self._landmark_buf: deque = deque(maxlen=BUFFER_FRAMES)
        self._result_name  = "—"
        self._result_conf  = 0.0
        self._all_probs: dict = {}
        self._photo_cache: dict = {}   # name -> PhotoImage
        self._session_counts: dict = {}

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left: camera ──
        left = tk.Frame(self, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(24, 10), pady=24)

        tk.Label(left, text="Live Recognition", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        cam_wrap = tk.Frame(left, bg=COLORS["border"])
        cam_wrap.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Label(cam_wrap, bg="#050a18", relief=tk.FLAT)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._status_bar = tk.Label(
            left, text="Camera not started", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"], anchor="w", padx=10, pady=5
        )
        self._status_bar.pack(fill=tk.X, pady=(6, 0))

        # ── Right: results ──
        right = tk.Frame(self, bg=COLORS["bg"], width=310)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 24), pady=24)
        right.pack_propagate(False)

        # ── Result card ──
        res_outer = tk.Frame(right, bg=COLORS["border"])
        res_outer.pack(fill=tk.X)
        res_card = tk.Frame(res_outer, bg=COLORS["surface"])
        res_card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Frame(res_card, bg=COLORS["accent"], height=3).pack(fill=tk.X)

        # Photo + name row
        id_row = tk.Frame(res_card, bg=COLORS["surface"])
        id_row.pack(fill=tk.X, padx=14, pady=(14, 6))

        # Profile photo placeholder (80x80)
        photo_border = tk.Frame(id_row, bg=COLORS["border"], width=82, height=82)
        photo_border.pack(side=tk.LEFT, padx=(0, 12))
        photo_border.pack_propagate(False)
        self._photo_lbl = tk.Label(photo_border, bg=COLORS["surface2"],
                                   text="?", font=FONTS["heading"], fg=COLORS["text_muted"])
        self._photo_lbl.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        name_col = tk.Frame(id_row, bg=COLORS["surface"])
        name_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(name_col, text="Identified As", font=FONTS["small"],
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w")
        self._name_label = tk.Label(name_col, text="—",
                                    font=("Segoe UI", 20, "bold") if True else FONTS["heading"],
                                    bg=COLORS["surface"], fg=COLORS["accent_light"],
                                    wraplength=180, justify=tk.LEFT)
        self._name_label.pack(anchor="w", pady=(2, 0))
        self._conf_label = tk.Label(name_col, text="Confidence: —",
                                    font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"])
        self._conf_label.pack(anchor="w")

        # Main confidence bar
        bar_bg = tk.Frame(res_card, bg=COLORS["surface2"], height=10)
        bar_bg.pack(fill=tk.X, padx=14, pady=(0, 14))
        self._conf_bar = tk.Frame(bar_bg, bg=COLORS["accent"], height=10)
        self._conf_bar.place(x=0, y=0, relheight=1, relwidth=0)

        # ── Per-user confidence chart ──
        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=(14, 0))
        chart_hdr = tk.Frame(right, bg=COLORS["bg"])
        chart_hdr.pack(fill=tk.X, pady=(10, 6))
        tk.Label(chart_hdr, text="Per-User Confidence", font=FONTS["subheading"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(side=tk.LEFT)

        self._chart_outer = tk.Frame(right, bg=COLORS["border"])
        self._chart_outer.pack(fill=tk.X)
        self._prob_frame = tk.Frame(self._chart_outer, bg=COLORS["surface"])
        self._prob_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Session stats
        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=(14, 0))
        tk.Label(right, text="Session Stats", font=FONTS["subheading"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(10, 6))

        self._session_outer = tk.Frame(right, bg=COLORS["border"])
        self._session_outer.pack(fill=tk.X)
        self._session_frame = tk.Frame(self._session_outer, bg=COLORS["surface"])
        self._session_frame.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self._session_placeholder = tk.Label(
            self._session_frame, text="Start camera to begin tracking.",
            font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self._session_placeholder.pack(padx=12, pady=10)

        # Warning (no model)
        self._no_model_label = tk.Label(
            right,
            text="⚠  Model not trained.\nGo to Enroll User, add people,\nthen click Train Model.",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["warning_light"],
            justify=tk.LEFT
        )

        # Controls
        tk.Frame(right, bg=COLORS["bg"], height=10).pack()
        self._btn_start = make_btn(right, "▶  Start Camera", self._start_camera,
                                   COLORS["accent"], COLORS["accent_hover"])
        self._btn_start.pack(fill=tk.X, pady=(0, 6))

        self._btn_stop_cam = make_btn(right, "⏹  Stop Camera", self._stop_camera,
                                      COLORS["surface2"], COLORS["surface3"])
        self._btn_stop_cam.pack(fill=tk.X)
        self._btn_stop_cam.config(state=tk.DISABLED)

        self._buf_label = tk.Label(right, text="", font=FONTS["small"],
                                   bg=COLORS["bg"], fg=COLORS["text_muted"])
        self._buf_label.pack(anchor="w", pady=(6, 0))

        self._update_model_warning()

    # ── Camera control ────────────────────────────────────────────────────────

    def _start_camera(self):
        if self._running:
            return
        try:
            self._pose = PoseEstimator()
        except ImportError as e:
            messagebox.showerror("Missing Dependency", str(e))
            return
        cap = open_camera(0)
        if cap is None:
            self._set_status("⚠  Camera not found.", COLORS["error_light"])
            return
        self._cap = cap
        self._running = True
        self._landmark_buf.clear()
        self._frame_idx = 0
        self._session_counts = {}
        self._btn_start.config(state=tk.DISABLED)
        self._btn_stop_cam.config(state=tk.NORMAL)
        self._set_status("Running — walk across the frame.", COLORS["success_light"])
        self._update_model_warning()
        self._loop()

    def _stop_camera(self):
        self._running = False
        if self._after_id:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._cap:
            self._cap.release()
            self._cap = None
        if self._pose:
            self._pose.close()
            self._pose = None
        self._btn_start.config(state=tk.NORMAL)
        self._btn_stop_cam.config(state=tk.DISABLED)
        self._set_status("Camera stopped.", COLORS["text_dim"])
        self._landmark_buf.clear()
        photo = frame_to_photoimage(placeholder_frame(640, 440, "Camera stopped"), 640, 440)
        self._canvas.configure(image=photo)
        self._canvas.image = photo

    def _loop(self):
        if not self._running:
            return
        ret, frame = self._cap.read()
        if ret:
            frame = self._process_frame(frame)
            photo = frame_to_photoimage(frame, 640, 440)
            self._canvas.configure(image=photo)
            self._canvas.image = photo
        self._after_id = self.after(1000 // DISPLAY_FPS, self._loop)

    def _process_frame(self, frame):
        self._frame_idx += 1
        annotated, landmarks = self._pose.process_frame(frame)

        if landmarks is not None:
            self._landmark_buf.append(landmarks)

        buf_len = len(self._landmark_buf)
        self._buf_label.config(text=f"Buffer: {buf_len}/{BUFFER_FRAMES} frames")

        if (self._frame_idx % INFER_EVERY == 0
                and buf_len >= GaitFeatureExtractor.MIN_FRAMES
                and self.recognizer.is_trained):
            feats = self._extractor.extract(list(self._landmark_buf))
            if feats is not None:
                name, conf = self.recognizer.predict(feats)
                self._all_probs    = self.recognizer.get_all_probabilities(feats)
                self._result_name  = name
                self._result_conf  = conf
                self._update_result_ui(name, conf)
                self.db.log_recognition(name, conf)
                if name != "Unknown":
                    self._session_counts[name] = self._session_counts.get(name, 0) + 1
                self._update_session_ui()

        if self._result_name != "—":
            self._pose.draw_confidence_overlay(annotated, self._result_name, self._result_conf)

        return annotated

    # ── Result UI ─────────────────────────────────────────────────────────────

    def _update_result_ui(self, name: str, conf: float):
        is_known = name not in ("Unknown", "—")
        color = COLORS["success_light"] if is_known else COLORS["text_muted"]

        self._name_label.config(text=name, fg=color)
        self._conf_label.config(text=f"Confidence:  {conf*100:.1f}%")
        self._conf_bar.place_configure(relwidth=min(conf, 1.0))

        # Update profile photo
        if is_known:
            self._show_result_photo(name)
        else:
            self._photo_lbl.config(image="", text="?", bg=COLORS["surface2"])

        # Per-user confidence chart
        for w in self._prob_frame.winfo_children():
            w.destroy()

        for uname, prob in list(self._all_probs.items())[:7]:
            highlight = uname == name and is_known
            row = tk.Frame(self._prob_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, padx=10, pady=3)

            lbl_color = COLORS["accent_light"] if highlight else COLORS["text_dim"]
            lbl_font  = FONTS["body_bold"] if highlight else FONTS["body"]

            tk.Label(row, text=uname, font=lbl_font,
                     bg=COLORS["surface"], fg=lbl_color,
                     width=13, anchor="w").pack(side=tk.LEFT)

            bar_wrap = tk.Frame(row, bg=COLORS["surface2"], height=12, width=100)
            bar_wrap.pack(side=tk.LEFT, padx=(6, 6))
            bar_wrap.pack_propagate(False)
            bar_fill = tk.Frame(bar_wrap,
                                bg=COLORS["accent"] if highlight else COLORS["surface3"],
                                height=12)
            bar_fill.place(x=0, y=0, relheight=1, relwidth=min(prob, 1.0))

            tk.Label(row, text=f"{prob*100:.0f}%", font=FONTS["small"],
                     bg=COLORS["surface"], fg=lbl_color, width=5, anchor="e"
                     ).pack(side=tk.LEFT)

    def _show_result_photo(self, name: str):
        if name in self._photo_cache:
            photo = self._photo_cache[name]
            if photo:
                self._photo_lbl.config(image=photo, text="", bg=COLORS["surface2"])
            return
        uid = self.db.get_user_id_by_name(name)
        if uid is None:
            self._photo_cache[name] = None
            return
        photo_bytes = self.db.get_user_photo(uid)
        if not photo_bytes:
            self._photo_cache[name] = None
            self._photo_lbl.config(image="", text=name[0].upper(), bg=COLORS["accent_dark"],
                                   fg=COLORS["accent_light"])
            return
        try:
            from PIL import Image, ImageTk
            img   = Image.open(io.BytesIO(photo_bytes)).resize((80, 80), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._photo_cache[name] = photo
            self._photo_lbl.config(image=photo, text="", bg=COLORS["surface2"])
            self._photo_lbl.image = photo
        except Exception:
            self._photo_cache[name] = None

    def _update_session_ui(self):
        for w in self._session_frame.winfo_children():
            w.destroy()
        if not self._session_counts:
            tk.Label(self._session_frame, text="No identifications yet.",
                     font=FONTS["small"], bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(padx=12, pady=10)
            return
        sorted_counts = sorted(self._session_counts.items(), key=lambda x: -x[1])
        for uname, count in sorted_counts[:5]:
            row = tk.Frame(self._session_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, padx=10, pady=3)
            tk.Label(row, text=uname, font=FONTS["body_bold"],
                     bg=COLORS["surface"], fg=COLORS["text"],
                     width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=f"{count}×", font=FONTS["small"],
                     bg=COLORS["surface"], fg=COLORS["accent_light"],
                     anchor="e").pack(side=tk.RIGHT, padx=8)

    def _update_model_warning(self):
        if self.recognizer.is_trained:
            self._no_model_label.pack_forget()
        else:
            self._no_model_label.pack(anchor="w", pady=(14, 0))

    def _set_status(self, msg: str, color: str = COLORS["text_dim"]):
        self._status_bar.config(text=f"  {msg}", fg=color)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self._update_model_warning()
        self._photo_cache.clear()

    def on_hide(self):
        self._stop_camera()
