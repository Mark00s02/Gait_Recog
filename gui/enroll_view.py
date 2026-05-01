"""Enroll new users by recording their gait pattern."""
import tkinter as tk
from tkinter import messagebox
import threading
import time
from collections import deque

from gui.theme import COLORS, FONTS
from src.utils import open_camera, frame_to_photoimage, placeholder_frame, draw_recording_indicator
from src.pose_estimator import PoseEstimator
from src.feature_extractor import GaitFeatureExtractor

RECORD_SECONDS = 8
FPS_TARGET = 30
RECORD_FRAMES = RECORD_SECONDS * FPS_TARGET


class EnrollView(tk.Frame):
    def __init__(self, parent, db, recognizer, on_model_updated=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self.on_model_updated = on_model_updated

        self._cap = None
        self._pose = None
        self._extractor = GaitFeatureExtractor()
        self._running = False
        self._recording = False
        self._frame_count = 0
        self._record_buffer = []
        self._landmark_buffer = []
        self._after_id = None
        self._train_thread = None

        self._build()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build(self):
        # Left: camera preview
        left = tk.Frame(self, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 10), pady=20)

        tk.Label(
            left, text="Camera Preview",
            font=FONTS["subheading"], bg=COLORS["bg"], fg=COLORS["text_dim"]
        ).pack(anchor="w", pady=(0, 6))

        self._canvas = tk.Label(left, bg="#000000", relief=tk.FLAT)
        self._canvas.pack(fill=tk.BOTH, expand=True)

        self._status_bar = tk.Label(
            left, text="Camera not started", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"], anchor="w", padx=8
        )
        self._status_bar.pack(fill=tk.X, pady=(4, 0))

        # Right: controls
        right = tk.Frame(self, bg=COLORS["bg"], width=310)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 20), pady=20)
        right.pack_propagate(False)

        tk.Label(
            right, text="Enroll New User",
            font=FONTS["title"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(0, 4))

        tk.Label(
            right,
            text="Record a person's gait to add\nthem to the recognition database.",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"],
            justify=tk.LEFT
        ).pack(anchor="w", pady=(0, 18))

        # Name input
        self._field("Name", right)
        self._name_var = tk.StringVar()
        name_entry = tk.Entry(
            right, textvariable=self._name_var,
            font=FONTS["body"], bg=COLORS["surface2"],
            fg=COLORS["text"], insertbackground=COLORS["text"],
            relief=tk.FLAT, bd=6
        )
        name_entry.pack(fill=tk.X, pady=(4, 14))

        # Recording tip
        tip = tk.Frame(right, bg=COLORS["accent_dark"], relief=tk.FLAT)
        tip.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            tip,
            text="💡 Tip: Walk sideways or diagonally across\n"
                 "the camera for best results.\n"
                 "Recording lasts 8 seconds.",
            font=FONTS["small"], bg=COLORS["accent_dark"],
            fg=COLORS["accent_light"], justify=tk.LEFT
        ).pack(padx=10, pady=8)

        # Progress bar
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_frame = tk.Frame(right, bg=COLORS["surface"], height=14, relief=tk.FLAT)
        self._progress_frame.pack(fill=tk.X, pady=(0, 6))
        self._progress_frame.pack_propagate(False)

        self._progress_fill = tk.Frame(self._progress_frame, bg=COLORS["accent"], height=14)
        self._progress_fill.place(x=0, y=0, relheight=1, width=0)

        self._progress_label = tk.Label(
            right, text="", font=FONTS["small"],
            bg=COLORS["bg"], fg=COLORS["text_dim"]
        )
        self._progress_label.pack(anchor="w", pady=(0, 14))

        # Buttons
        self._btn_start_cam = self._btn(right, "▶  Start Camera", self._start_camera, COLORS["surface2"])
        self._btn_start_cam.pack(fill=tk.X, pady=(0, 6))

        self._btn_record = self._btn(right, "⏺  Record Gait Sample", self._start_recording, COLORS["accent"])
        self._btn_record.pack(fill=tk.X, pady=(0, 6))
        self._btn_record.config(state=tk.DISABLED)

        self._btn_stop = self._btn(right, "⏹  Stop Recording", self._stop_recording, COLORS["warning"])
        self._btn_stop.pack(fill=tk.X, pady=(0, 6))
        self._btn_stop.config(state=tk.DISABLED)

        self._btn_train = self._btn(right, "🧠  Train Model", self._train_model, COLORS["success"])
        self._btn_train.pack(fill=tk.X, pady=(0, 6))

        # Samples list
        tk.Label(
            right, text="Recorded Samples",
            font=FONTS["subheading"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(20, 6))

        self._samples_frame = tk.Frame(right, bg=COLORS["surface"], relief=tk.FLAT)
        self._samples_frame.pack(fill=tk.BOTH, expand=True)

        self._no_samples_lbl = tk.Label(
            self._samples_frame,
            text="No samples yet.",
            font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self._no_samples_lbl.pack(pady=12)

        self._refresh_samples_list()

    def _field(self, text, parent):
        tk.Label(
            parent, text=text, font=FONTS["body_bold"],
            bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w")

    def _btn(self, parent, text, cmd, bg):
        b = tk.Button(
            parent, text=text, command=cmd,
            font=FONTS["body_bold"], bg=bg, fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0,
            activebackground=COLORS["surface3"], activeforeground=COLORS["text"],
            pady=8
        )
        return b

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
            self._set_status("⚠  Could not open camera. Check connection.", COLORS["error_light"])
            return

        self._cap = cap
        self._running = True
        self._btn_start_cam.config(state=tk.DISABLED)
        self._btn_record.config(state=tk.NORMAL)
        self._set_status("Camera active — ready to record.", COLORS["success_light"])
        self._loop()

    def _loop(self):
        if not self._running:
            return
        ret, frame = self._cap.read()
        if ret:
            frame = self._process_frame(frame)
            photo = frame_to_photoimage(frame, 640, 440)
            self._canvas.configure(image=photo)
            self._canvas.image = photo
        self._after_id = self.after(33, self._loop)  # ~30 fps

    def _process_frame(self, frame):
        if self._pose is None:
            return frame
        annotated, landmarks = self._pose.process_frame(frame)

        if self._recording:
            self._frame_count += 1
            elapsed = self._frame_count / FPS_TARGET
            progress = min(elapsed / RECORD_SECONDS, 1.0)

            # Update progress bar width
            total_w = self._progress_frame.winfo_width()
            fill_w = int(total_w * progress)
            self._progress_fill.place_configure(width=fill_w)
            self._progress_label.config(text=f"Recording: {elapsed:.1f} / {RECORD_SECONDS}s")

            if landmarks is not None:
                self._landmark_buffer.append(landmarks)

            draw_recording_indicator(annotated, self._frame_count)

            if self._frame_count >= RECORD_FRAMES:
                self._finish_recording()

        return annotated

    # ── Recording control ─────────────────────────────────────────────────────

    def _start_recording(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Name Required", "Please enter a name before recording.")
            return
        if self._recording:
            return

        self._recording = True
        self._frame_count = 0
        self._landmark_buffer = []
        self._btn_record.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.NORMAL)
        self._set_status("Recording…", COLORS["warning_light"])

    def _stop_recording(self):
        if self._recording:
            self._finish_recording()

    def _finish_recording(self):
        self._recording = False
        self._btn_stop.config(state=tk.DISABLED)
        self._btn_record.config(state=tk.NORMAL)

        self._progress_fill.place_configure(width=0)
        self._progress_label.config(text="")

        name = self._name_var.get().strip()
        landmarks = list(self._landmark_buffer)
        self._landmark_buffer = []

        if len(landmarks) < GaitFeatureExtractor.MIN_FRAMES:
            self._set_status(
                f"⚠  Too few frames captured ({len(landmarks)}). Walk more/slower.",
                COLORS["error_light"]
            )
            return

        features = self._extractor.extract(landmarks)
        if features is None:
            self._set_status("⚠  Could not extract features. Try again.", COLORS["error_light"])
            return

        user_id = self.db.get_or_create_user(name)
        self.db.add_sample(user_id, features)

        n = self.db.get_user_sample_count(user_id)
        self._set_status(
            f"✓  Sample saved for '{name}' (total: {n} sample{'s' if n != 1 else ''}).",
            COLORS["success_light"]
        )
        self._refresh_samples_list()

    # ── Training ──────────────────────────────────────────────────────────────

    def _train_model(self):
        if self._train_thread and self._train_thread.is_alive():
            return

        all_features, labels, label_names = self.db.get_all_samples()
        if not all_features:
            messagebox.showinfo("No Data", "No gait samples found. Enroll users first.")
            return

        self._btn_train.config(state=tk.DISABLED, text="⏳ Training…")
        self._set_status("Training model — please wait…", COLORS["text_dim"])

        def do_train():
            ok, msg = self.recognizer.train(all_features, labels, label_names)
            self.after(0, lambda: self._on_train_done(ok, msg))

        self._train_thread = threading.Thread(target=do_train, daemon=True)
        self._train_thread.start()

    def _on_train_done(self, ok: bool, msg: str):
        self._btn_train.config(state=tk.NORMAL, text="🧠  Train Model")
        color = COLORS["success_light"] if ok else COLORS["error_light"]
        icon = "✓" if ok else "⚠"
        self._set_status(f"{icon}  {msg}", color)
        if ok and self.on_model_updated:
            self.on_model_updated()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = COLORS["text_dim"]):
        self._status_bar.config(text=msg, fg=color)

    def _refresh_samples_list(self):
        for w in self._samples_frame.winfo_children():
            w.destroy()

        users = self.db.get_all_users()
        if not users:
            tk.Label(
                self._samples_frame, text="No samples yet.",
                font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"]
            ).pack(pady=12)
            return

        for uid, name, count, created in users:
            row = tk.Frame(self._samples_frame, bg=COLORS["surface2"], relief=tk.FLAT)
            row.pack(fill=tk.X, padx=6, pady=2)
            color = COLORS["success_light"] if count >= 3 else COLORS["warning_light"]
            tk.Label(
                row, text=name, font=FONTS["body_bold"],
                bg=COLORS["surface2"], fg=COLORS["text"]
            ).pack(side=tk.LEFT, padx=8, pady=5)
            tk.Label(
                row, text=f"{count} sample{'s' if count != 1 else ''}",
                font=FONTS["small"], bg=COLORS["surface2"], fg=color
            ).pack(side=tk.RIGHT, padx=8)

    def on_show(self):
        """Called when this view becomes visible."""
        self._refresh_samples_list()

    def on_hide(self):
        """Called when navigating away — release camera."""
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
        self._recording = False
        self._btn_start_cam.config(state=tk.NORMAL)
        self._btn_record.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.DISABLED)
        self._set_status("Camera not started")
        photo = frame_to_photoimage(
            placeholder_frame(640, 440, "Camera stopped"), 640, 440
        )
        self._canvas.configure(image=photo)
        self._canvas.image = photo
