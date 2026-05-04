"""Enroll new users — record gait samples and capture a profile photo."""
import io
import tkinter as tk
from tkinter import messagebox
import threading

from gui.theme import COLORS, FONTS, make_btn
from src.utils import open_camera, frame_to_photoimage, placeholder_frame, draw_recording_indicator
from src.pose_estimator import PoseEstimator
from src.feature_extractor import GaitFeatureExtractor

RECORD_SECONDS = 8
FPS_TARGET     = 30
RECORD_FRAMES  = RECORD_SECONDS * FPS_TARGET
PHOTO_SIZE     = 200   # stored photo dimension


class EnrollView(tk.Frame):
    def __init__(self, parent, db, recognizer, on_model_updated=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self.on_model_updated = on_model_updated

        self._cap          = None
        self._pose         = None
        self._extractor    = GaitFeatureExtractor()
        self._running      = False
        self._recording    = False
        self._frame_count  = 0
        self._landmark_buf = []
        self._after_id     = None
        self._train_thread = None
        self._last_frame   = None   # BGR frame cache for photo capture
        self._photo_img    = None   # tk PhotoImage ref

        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Left: camera preview ──
        left = tk.Frame(self, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(24, 10), pady=24)

        tk.Label(left, text="Camera Preview", font=FONTS["small"],
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(anchor="w", pady=(0, 4))

        cam_wrap = tk.Frame(left, bg=COLORS["border"])
        cam_wrap.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Label(cam_wrap, bg="#050a18", relief=tk.FLAT)
        self._canvas.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._status_bar = tk.Label(
            left, text="Camera not started", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"], anchor="w", padx=10, pady=5
        )
        self._status_bar.pack(fill=tk.X, pady=(6, 0))

        # ── Right: controls ──
        right = tk.Frame(self, bg=COLORS["bg"], width=320)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 24), pady=24)
        right.pack_propagate(False)

        tk.Label(right, text="Enroll New User", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 4))
        tk.Label(right, text="Add a person to the recognition database\nby recording their walking pattern.",
                 font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"],
                 justify=tk.LEFT).pack(anchor="w", pady=(0, 18))

        # Name input
        tk.Label(right, text="Full Name", font=FONTS["body_bold"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        self._name_var = tk.StringVar()
        name_entry = tk.Entry(
            right, textvariable=self._name_var,
            font=FONTS["body"], bg=COLORS["surface2"], fg=COLORS["text"],
            insertbackground=COLORS["text"], relief=tk.FLAT, bd=8
        )
        name_entry.pack(fill=tk.X, pady=(4, 14))

        # Photo preview + capture
        photo_row = tk.Frame(right, bg=COLORS["bg"])
        photo_row.pack(fill=tk.X, pady=(0, 14))

        photo_border = tk.Frame(photo_row, bg=COLORS["border"], width=82, height=82)
        photo_border.pack(side=tk.LEFT)
        photo_border.pack_propagate(False)
        self._photo_lbl = tk.Label(photo_border, bg=COLORS["surface2"], text="📷",
                                   font=("Segoe UI", 22), fg=COLORS["text_muted"])
        self._photo_lbl.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        photo_info = tk.Frame(photo_row, bg=COLORS["bg"])
        photo_info.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(12, 0))
        tk.Label(photo_info, text="Profile Photo", font=FONTS["body_bold"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(photo_info, text="Auto-captured when recording\nfinishes. Click below to retake.",
                 font=FONTS["small"], bg=COLORS["bg"], fg=COLORS["text_muted"],
                 justify=tk.LEFT).pack(anchor="w")
        self._btn_photo = make_btn(photo_info, "  Capture Now", self._capture_photo,
                                   COLORS["surface2"], COLORS["surface3"], pady=5, padx=10)
        self._btn_photo.pack(anchor="w", pady=(6, 0))
        self._btn_photo.config(state=tk.DISABLED)

        # Tip box
        tip = tk.Frame(right, bg=COLORS["surface2"])
        tip.pack(fill=tk.X, pady=(0, 14))
        tk.Frame(tip, bg=COLORS["accent"], height=3).pack(fill=tk.X)
        tk.Label(
            tip,
            text="💡  Walk sideways or diagonally across the camera.\n"
                 "    Recording lasts 8 seconds. Aim for 3+ samples per person.",
            font=FONTS["small"], bg=COLORS["surface2"], fg=COLORS["text_dim"],
            justify=tk.LEFT
        ).pack(padx=12, pady=10, anchor="w")

        # Progress bar
        self._prog_wrap = tk.Frame(right, bg=COLORS["surface2"], height=10)
        self._prog_wrap.pack(fill=tk.X, pady=(0, 4))
        self._prog_wrap.pack_propagate(False)
        self._prog_fill = tk.Frame(self._prog_wrap, bg=COLORS["accent"], height=10)
        self._prog_fill.place(x=0, y=0, relheight=1, width=0)
        self._prog_label = tk.Label(right, text="", font=FONTS["small"],
                                    bg=COLORS["bg"], fg=COLORS["text_dim"])
        self._prog_label.pack(anchor="w", pady=(0, 12))

        # Action buttons
        self._btn_start_cam = make_btn(right, "▶  Start Camera", self._start_camera,
                                       COLORS["surface2"], COLORS["surface3"])
        self._btn_start_cam.pack(fill=tk.X, pady=(0, 6))

        self._btn_record = make_btn(right, "⏺  Record Gait Sample", self._start_recording,
                                    COLORS["accent"], COLORS["accent_hover"])
        self._btn_record.pack(fill=tk.X, pady=(0, 6))
        self._btn_record.config(state=tk.DISABLED)

        self._btn_stop = make_btn(right, "⏹  Stop Recording", self._stop_recording,
                                  COLORS["warning"], "#b45309")
        self._btn_stop.pack(fill=tk.X, pady=(0, 6))
        self._btn_stop.config(state=tk.DISABLED)

        self._btn_train = make_btn(right, "🧠  Train Model", self._train_model,
                                   COLORS["success"], "#047857")
        self._btn_train.pack(fill=tk.X, pady=(0, 0))

        # Samples list
        tk.Frame(right, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=(18, 10))
        tk.Label(right, text="Enrolled Samples", font=FONTS["subheading"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w", pady=(0, 6))

        self._samples_wrap = tk.Frame(right, bg=COLORS["border"])
        self._samples_wrap.pack(fill=tk.BOTH, expand=True)
        self._samples_inner = tk.Frame(self._samples_wrap, bg=COLORS["surface"])
        self._samples_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        self._refresh_samples()

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
            self._set_status("⚠  Could not open camera.", COLORS["error_light"])
            return
        self._cap = cap
        self._running = True
        self._btn_start_cam.config(state=tk.DISABLED)
        self._btn_record.config(state=tk.NORMAL)
        self._btn_photo.config(state=tk.NORMAL)
        self._set_status("Camera active — enter a name and press Record.", COLORS["success_light"])
        self._loop()

    def _loop(self):
        if not self._running:
            return
        ret, frame = self._cap.read()
        if ret:
            self._last_frame = frame.copy()
            frame = self._process_frame(frame)
            photo = frame_to_photoimage(frame, 640, 440)
            self._canvas.configure(image=photo)
            self._canvas.image = photo
        self._after_id = self.after(33, self._loop)

    def _process_frame(self, frame):
        if self._pose is None:
            return frame
        annotated, landmarks = self._pose.process_frame(frame)

        if self._recording:
            self._frame_count += 1
            elapsed  = self._frame_count / FPS_TARGET
            progress = min(elapsed / RECORD_SECONDS, 1.0)

            total_w = self._prog_wrap.winfo_width()
            self._prog_fill.place_configure(width=int(total_w * progress))
            self._prog_label.config(text=f"Recording: {elapsed:.1f} / {RECORD_SECONDS}s")

            if landmarks is not None:
                self._landmark_buf.append(landmarks)

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
        self._recording    = True
        self._frame_count  = 0
        self._landmark_buf = []
        self._btn_record.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.NORMAL)
        self._set_status("Recording…  Walk across the frame!", COLORS["warning_light"])

    def _stop_recording(self):
        if self._recording:
            self._finish_recording()

    def _finish_recording(self):
        self._recording = False
        self._btn_stop.config(state=tk.DISABLED)
        self._btn_record.config(state=tk.NORMAL)
        self._prog_fill.place_configure(width=0)
        self._prog_label.config(text="")

        name      = self._name_var.get().strip()
        landmarks = list(self._landmark_buf)
        self._landmark_buf = []

        if len(landmarks) < GaitFeatureExtractor.MIN_FRAMES:
            self._set_status(
                f"⚠  Too few frames ({len(landmarks)}). Walk more slowly or for longer.",
                COLORS["error_light"]
            )
            return

        features = self._extractor.extract(landmarks)
        if features is None:
            self._set_status("⚠  Could not extract features. Try again.", COLORS["error_light"])
            return

        user_id = self.db.get_or_create_user(name)
        self.db.add_sample(user_id, features)

        # Auto-capture photo if user has none yet
        if self.db.get_user_photo(user_id) is None and self._last_frame is not None:
            self._save_photo(user_id, self._last_frame)

        n = self.db.get_user_sample_count(user_id)
        self._set_status(
            f"✓  Sample saved for '{name}'  ({n} sample{'s' if n != 1 else ''} total).",
            COLORS["success_light"]
        )
        self._refresh_samples()

    # ── Photo capture ─────────────────────────────────────────────────────────

    def _capture_photo(self):
        """Manually capture the current camera frame as profile photo."""
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("Name Required", "Enter a name first.")
            return
        if self._last_frame is None:
            return
        user_id = self.db.get_or_create_user(name)
        self._save_photo(user_id, self._last_frame)
        self._set_status(f"📷  Profile photo updated for '{name}'.", COLORS["accent_light"])

    def _save_photo(self, user_id: int, bgr_frame):
        try:
            import cv2
            from PIL import Image
            rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb).resize((PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            self.db.set_user_photo(user_id, buf.getvalue())
            self._show_photo_preview(buf.getvalue())
        except Exception:
            pass

    def _show_photo_preview(self, photo_bytes: bytes):
        try:
            from PIL import Image, ImageTk
            img   = Image.open(io.BytesIO(photo_bytes)).resize((80, 80), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._photo_lbl.config(image=photo, text="", bg=COLORS["surface2"])
            self._photo_lbl.image = photo
            self._photo_img = photo
        except Exception:
            pass

    # ── Training ──────────────────────────────────────────────────────────────

    def _train_model(self):
        if self._train_thread and self._train_thread.is_alive():
            return
        all_features, labels, label_names = self.db.get_all_samples()
        if not all_features:
            messagebox.showinfo("No Data", "No gait samples found. Enroll users first.")
            return
        self._btn_train.config(state=tk.DISABLED, text="⏳  Training…")
        self._set_status("Training model — please wait…", COLORS["text_dim"])

        def do_train():
            ok, msg = self.recognizer.train(all_features, labels, label_names)
            self.after(0, lambda: self._on_train_done(ok, msg))

        self._train_thread = threading.Thread(target=do_train, daemon=True)
        self._train_thread.start()

    def _on_train_done(self, ok: bool, msg: str):
        self._btn_train.config(state=tk.NORMAL, text="🧠  Train Model")
        color = COLORS["success_light"] if ok else COLORS["error_light"]
        self._set_status(("✓  " if ok else "⚠  ") + msg, color)
        if ok and self.on_model_updated:
            self.on_model_updated()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, color: str = COLORS["text_dim"]):
        self._status_bar.config(text=f"  {msg}", fg=color)

    def _refresh_samples(self):
        for w in self._samples_inner.winfo_children():
            w.destroy()

        users = self.db.get_all_users()
        if not users:
            tk.Label(self._samples_inner, text="No samples yet.",
                     font=FONTS["small"], bg=COLORS["surface"],
                     fg=COLORS["text_muted"]).pack(pady=14)
            return

        for uid, name, count, _ in users:
            row = tk.Frame(self._samples_inner, bg=COLORS["surface2"])
            row.pack(fill=tk.X, padx=6, pady=2)

            # Tiny photo thumbnail
            thumb_bytes = self.db.get_user_photo(uid)
            if thumb_bytes:
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(io.BytesIO(thumb_bytes)).resize((32, 32), Image.LANCZOS)
                    tkimg = ImageTk.PhotoImage(img)
                    lbl = tk.Label(row, image=tkimg, bg=COLORS["surface2"])
                    lbl.image = tkimg
                    lbl.pack(side=tk.LEFT, padx=(6, 0), pady=4)
                except Exception:
                    tk.Frame(row, bg=COLORS["surface3"], width=32, height=32).pack(
                        side=tk.LEFT, padx=(6, 0), pady=4)
            else:
                tk.Frame(row, bg=COLORS["surface3"], width=32, height=32).pack(
                    side=tk.LEFT, padx=(6, 0), pady=4)

            tk.Label(row, text=name, font=FONTS["body_bold"],
                     bg=COLORS["surface2"], fg=COLORS["text"]).pack(side=tk.LEFT, padx=8, pady=6)
            color = COLORS["success_light"] if count >= 3 else COLORS["warning_light"]
            tk.Label(row, text=f"{count} sample{'s' if count != 1 else ''}",
                     font=FONTS["small"], bg=COLORS["surface2"], fg=color
                     ).pack(side=tk.RIGHT, padx=8)

        # Load current user's photo preview if they exist
        name = self._name_var.get().strip()
        if name:
            uid = self.db.get_user_id_by_name(name)
            if uid:
                pb = self.db.get_user_photo(uid)
                if pb:
                    self._show_photo_preview(pb)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self._refresh_samples()

    def on_hide(self):
        self._running   = False
        self._recording = False
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
        self._btn_start_cam.config(state=tk.NORMAL)
        self._btn_record.config(state=tk.DISABLED)
        self._btn_stop.config(state=tk.DISABLED)
        self._btn_photo.config(state=tk.DISABLED)
        self._set_status("Camera not started")
        photo = frame_to_photoimage(placeholder_frame(640, 440, "Camera stopped"), 640, 440)
        self._canvas.configure(image=photo)
        self._canvas.image = photo
