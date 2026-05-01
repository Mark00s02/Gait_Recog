"""Settings view — adjust recognition threshold and check dependencies."""
import tkinter as tk
from tkinter import messagebox
import threading

from gui.theme import COLORS, FONTS
from src.utils import check_dependencies


class SettingsView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self._build()

    def _build(self):
        tk.Label(
            self, text="Settings",
            font=FONTS["title"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", padx=30, pady=(25, 4))

        tk.Label(
            self, text="Configure recognition parameters and view system information.",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]
        ).pack(anchor="w", padx=30, pady=(0, 20))

        # Recognition settings card
        card = self._card(self, "Recognition Settings")
        card.pack(fill=tk.X, padx=30, pady=(0, 16))

        # Confidence threshold
        thresh_row = tk.Frame(card, bg=COLORS["surface"])
        thresh_row.pack(fill=tk.X, padx=20, pady=(10, 14))

        tk.Label(
            thresh_row, text="Confidence Threshold",
            font=FONTS["body_bold"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w")
        tk.Label(
            thresh_row,
            text="Minimum confidence required to identify a person.\n"
                 "Lower = more permissive, Higher = more strict (fewer false IDs).",
            font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_dim"],
            justify=tk.LEFT
        ).pack(anchor="w", pady=(2, 8))

        slider_row = tk.Frame(thresh_row, bg=COLORS["surface"])
        slider_row.pack(fill=tk.X)

        self._threshold_var = tk.DoubleVar(value=self.recognizer.confidence_threshold)
        self._thresh_label = tk.Label(
            slider_row, font=FONTS["body_bold"],
            bg=COLORS["surface"], fg=COLORS["accent_light"],
            text=f"{self.recognizer.confidence_threshold*100:.0f}%", width=5
        )
        self._thresh_label.pack(side=tk.RIGHT)

        scale = tk.Scale(
            slider_row, variable=self._threshold_var,
            from_=0.30, to=0.95, resolution=0.01, orient=tk.HORIZONTAL,
            bg=COLORS["surface"], fg=COLORS["text"], highlightbackground=COLORS["surface"],
            troughcolor=COLORS["surface2"], activebackground=COLORS["accent"],
            command=self._on_threshold_change, showvalue=False,
            length=400
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._btn_apply_thresh = tk.Button(
            thresh_row, text="Apply",
            command=self._apply_threshold,
            font=FONTS["body_bold"], bg=COLORS["accent"], fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0, padx=16, pady=5
        )
        self._btn_apply_thresh.pack(anchor="e", pady=(8, 0))

        # Model info card
        model_card = self._card(self, "Model Information")
        model_card.pack(fill=tk.X, padx=30, pady=(0, 16))

        self._model_info_frame = tk.Frame(model_card, bg=COLORS["surface"])
        self._model_info_frame.pack(fill=tk.X, padx=20, pady=(10, 14))
        self._refresh_model_info()

        tk.Button(
            model_card, text="Reset Model (delete trained data)",
            command=self._reset_model,
            font=FONTS["small"], bg=COLORS["error"], fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0, padx=12, pady=5
        ).pack(anchor="w", padx=20, pady=(0, 14))

        # Dependencies card
        dep_card = self._card(self, "System Dependencies")
        dep_card.pack(fill=tk.X, padx=30, pady=(0, 16))

        self._dep_frame = tk.Frame(dep_card, bg=COLORS["surface"])
        self._dep_frame.pack(fill=tk.X, padx=20, pady=(10, 14))

        tk.Button(
            dep_card, text="Check Dependencies",
            command=self._check_deps,
            font=FONTS["body_bold"], bg=COLORS["surface2"], fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0, padx=12, pady=6
        ).pack(anchor="w", padx=20, pady=(0, 14))

        self._check_deps()

    def _card(self, parent, title: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLORS["surface"], relief=tk.FLAT)
        tk.Label(
            frame, text=title,
            font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w", padx=20, pady=(14, 0))
        tk.Frame(frame, bg=COLORS["surface2"], height=1).pack(fill=tk.X, padx=20, pady=(6, 0))
        return frame

    def _on_threshold_change(self, val):
        self._thresh_label.config(text=f"{float(val)*100:.0f}%")

    def _apply_threshold(self):
        val = self._threshold_var.get()
        self.recognizer.set_threshold(val)
        messagebox.showinfo(
            "Threshold Updated",
            f"Confidence threshold set to {val*100:.0f}%."
        )

    def _refresh_model_info(self):
        for w in self._model_info_frame.winfo_children():
            w.destroy()

        items = [
            ("Status:", "Trained ✓" if self.recognizer.is_trained else "Not trained",
             COLORS["success_light"] if self.recognizer.is_trained else COLORS["warning_light"]),
            ("Users:",   str(self.recognizer.n_classes), COLORS["text"]),
            ("CV Accuracy:", (
                f"{self.recognizer.cv_accuracy*100:.1f}%"
                if self.recognizer.cv_accuracy > 0 else "—"
            ), COLORS["text"]),
            ("Threshold:", f"{self.recognizer.confidence_threshold*100:.0f}%", COLORS["text"]),
        ]
        for label, value, color in items:
            row = tk.Frame(self._model_info_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=2)
            tk.Label(
                row, text=label, font=FONTS["body"],
                bg=COLORS["surface"], fg=COLORS["text_dim"], width=18, anchor="w"
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=value, font=FONTS["body_bold"],
                bg=COLORS["surface"], fg=color, anchor="w"
            ).pack(side=tk.LEFT)

    def _reset_model(self):
        if messagebox.askyesno(
            "Reset Model",
            "Delete the trained model?\n"
            "Enrolled user data will NOT be deleted — you can retrain later.",
            icon="warning"
        ):
            self.recognizer.reset()
            self._refresh_model_info()
            messagebox.showinfo("Done", "Model has been reset.")

    def _check_deps(self):
        for w in self._dep_frame.winfo_children():
            w.destroy()

        deps = check_dependencies()
        for pkg, ver in deps.items():
            row = tk.Frame(self._dep_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=2)

            ok = ver is not None
            icon = "✓" if ok else "✗"
            color = COLORS["success_light"] if ok else COLORS["error_light"]

            tk.Label(
                row, text=f"{icon}  {pkg}", font=FONTS["body"],
                bg=COLORS["surface"], fg=color, width=20, anchor="w"
            ).pack(side=tk.LEFT)
            tk.Label(
                row, text=ver if ver else "NOT INSTALLED", font=FONTS["mono"],
                bg=COLORS["surface"], fg=COLORS["text_dim"] if ok else COLORS["error_light"],
                anchor="w"
            ).pack(side=tk.LEFT)

    def on_show(self):
        self._refresh_model_info()
        self._threshold_var.set(self.recognizer.confidence_threshold)
        self._thresh_label.config(text=f"{self.recognizer.confidence_threshold*100:.0f}%")

    def on_hide(self):
        pass
