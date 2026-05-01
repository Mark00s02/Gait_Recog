"""Real-time gait recognition view with sliding-window inference."""
import tkinter as tk
from tkinter import messagebox
from collections import deque

from gui.theme import COLORS, FONTS
from src.utils import open_camera, frame_to_photoimage, placeholder_frame
from src.pose_estimator import PoseEstimator
from src.feature_extractor import GaitFeatureExtractor, FEATURE_SIZE

BUFFER_FRAMES = 90       # 3 s at 30 fps
INFER_EVERY   = 20       # run inference every N frames
DISPLAY_FPS   = 30


class RecognizeView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer

        self._cap = None
        self._pose = None
        self._extractor = GaitFeatureExtractor()

        self._running = False
        self._after_id = None
        self._frame_idx = 0

        self._landmark_buf: deque = deque(maxlen=BUFFER_FRAMES)
        self._result_name = "—"
        self._result_conf = 0.0
        self._all_probs: dict = {}
        self._last_features = None

        self._build()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build(self):
        # Left: camera
        left = tk.Frame(self, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 10), pady=20)

        tk.Label(
            left, text="Live Recognition",
            font=FONTS["title"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(0, 6))

        self._canvas = tk.Label(left, bg="#000000", relief=tk.FLAT)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        # Status bar
        self._status_bar = tk.Label(
            left, text="Camera not started", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"], anchor="w", padx=8
        )
        self._status_bar.pack(fill=tk.X, pady=(4, 0))

        # Right: results panel
        right = tk.Frame(self, bg=COLORS["bg"], width=300)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 20), pady=20)
        right.pack_propagate(False)

        # Result card
        result_card = tk.Frame(right, bg=COLORS["surface"], relief=tk.FLAT)
        result_card.pack(fill=tk.X, pady=(40, 0))

        tk.Label(
            result_card, text="Identified Person",
            font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text_dim"]
        ).pack(anchor="w", padx=16, pady=(14, 2))

        self._name_label = tk.Label(
            result_card, text="—", font=("Helvetica", 28, "bold"),
            bg=COLORS["surface"], fg=COLORS["accent_light"]
        )
        self._name_label.pack(anchor="w", padx=16, pady=(0, 4))

        self._conf_label = tk.Label(
            result_card, text="Confidence: —",
            font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_dim"]
        )
        self._conf_label.pack(anchor="w", padx=16, pady=(0, 6))

        # Confidence bar
        bar_bg = tk.Frame(result_card, bg=COLORS["surface2"], height=12)
        bar_bg.pack(fill=tk.X, padx=16, pady=(0, 14))
        self._conf_bar = tk.Frame(bar_bg, bg=COLORS["accent"], height=12)
        self._conf_bar.place(x=0, y=0, relheight=1, relwidth=0)

        # All-users probability breakdown
        tk.Label(
            right, text="Per-User Confidence",
            font=FONTS["subheading"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(20, 6))

        self._prob_frame = tk.Frame(right, bg=COLORS["surface"])
        self._prob_frame.pack(fill=tk.X)

        self._no_model_label = tk.Label(
            right,
            text="⚠  Model not trained.\nGo to Enroll to add users\nand train the model.",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["warning_light"],
            justify=tk.LEFT
        )
        self._no_model_label.pack(anchor="w", pady=(20, 0))

        # Controls
        self._btn_start = self._btn(right, "▶  Start Camera", self._start_camera, COLORS["accent"])
        self._btn_start.pack(fill=tk.X, pady=(20, 6))

        self._btn_stop_cam = self._btn(right, "⏹  Stop Camera", self._stop_camera, COLORS["surface2"])
        self._btn_stop_cam.pack(fill=tk.X, pady=(0, 6))
        self._btn_stop_cam.config(state=tk.DISABLED)

        # Buffer info
        self._buf_label = tk.Label(
            right, text="", font=FONTS["small"],
            bg=COLORS["bg"], fg=COLORS["text_muted"]
        )
        self._buf_label.pack(anchor="w")

        self._update_model_warning()

    def _btn(self, parent, text, cmd, bg):
        return tk.Button(
            parent, text=text, command=cmd,
            font=FONTS["body_bold"], bg=bg, fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0,
            activebackground=COLORS["surface3"], activeforeground=COLORS["text"],
            pady=8
        )

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
        self._buf_label.config(
            text=f"Buffer: {buf_len}/{BUFFER_FRAMES} frames"
        )

        # Run inference periodically
        if (self._frame_idx % INFER_EVERY == 0
                and buf_len >= GaitFeatureExtractor.MIN_FRAMES
                and self.recognizer.is_trained):
            feats = self._extractor.extract(list(self._landmark_buf))
            if feats is not None:
                name, conf = self.recognizer.predict(feats)
                self._all_probs = self.recognizer.get_all_probabilities(feats)
                self._result_name = name
                self._result_conf = conf
                self._update_result_ui(name, conf)
                self.db.log_recognition(name, conf)

        # Draw result overlay on frame
        if self._result_name != "—":
            self._pose.draw_confidence_overlay(annotated, self._result_name, self._result_conf)

        return annotated

    # ── Result UI ─────────────────────────────────────────────────────────────

    def _update_result_ui(self, name: str, conf: float):
        is_known = name != "Unknown" and name != "—"
        color = COLORS["success_light"] if is_known else COLORS["text_muted"]

        self._name_label.config(text=name, fg=color)
        self._conf_label.config(text=f"Confidence: {conf*100:.1f}%")
        self._conf_bar.place_configure(relwidth=conf)

        # Per-user breakdown
        for w in self._prob_frame.winfo_children():
            w.destroy()

        for uname, prob in list(self._all_probs.items())[:6]:
            row = tk.Frame(self._prob_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, padx=4, pady=2)

            highlight = (uname == name and is_known)
            lbl_color = COLORS["accent_light"] if highlight else COLORS["text_dim"]

            tk.Label(
                row, text=uname, font=FONTS["body_bold"] if highlight else FONTS["body"],
                bg=COLORS["surface"], fg=lbl_color, width=14, anchor="w"
            ).pack(side=tk.LEFT, padx=(8, 4))

            # mini bar
            bar_bg = tk.Frame(row, bg=COLORS["surface2"], height=8, width=80)
            bar_bg.pack(side=tk.LEFT, padx=(0, 6))
            bar_bg.pack_propagate(False)
            bar_fill = tk.Frame(bar_bg, bg=lbl_color, height=8)
            bar_fill.place(x=0, y=0, relheight=1, relwidth=min(prob, 1.0))

            tk.Label(
                row, text=f"{prob*100:.0f}%", font=FONTS["small"],
                bg=COLORS["surface"], fg=lbl_color, width=5
            ).pack(side=tk.LEFT)

    def _update_model_warning(self):
        if self.recognizer.is_trained:
            self._no_model_label.pack_forget()
        else:
            self._no_model_label.pack(anchor="w", pady=(20, 0))

    def _set_status(self, msg: str, color: str = COLORS["text_dim"]):
        self._status_bar.config(text=msg, fg=color)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self._update_model_warning()

    def on_hide(self):
        self._stop_camera()
