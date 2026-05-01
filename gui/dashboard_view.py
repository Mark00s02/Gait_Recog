"""Dashboard overview view."""
import tkinter as tk
from gui.theme import COLORS, FONTS


class DashboardView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self._build()

    def _build(self):
        # Title
        tk.Label(
            self, text="Dashboard", font=FONTS["title"],
            bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", padx=30, pady=(25, 5))

        tk.Label(
            self, text="Gait Recognition System Overview",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]
        ).pack(anchor="w", padx=30, pady=(0, 20))

        # Stats cards row
        cards_frame = tk.Frame(self, bg=COLORS["bg"])
        cards_frame.pack(fill=tk.X, padx=30, pady=(0, 20))

        self._stat_cards = {}
        card_defs = [
            ("users",        "Enrolled Users",    COLORS["accent_light"]),
            ("samples",      "Gait Samples",      COLORS["success_light"]),
            ("recognitions", "Recognitions Run",  COLORS["warning_light"]),
            ("model",        "Model Status",      COLORS["text_dim"]),
        ]
        for key, label, color in card_defs:
            card = self._make_stat_card(cards_frame, label, "—", color)
            card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=6)
            self._stat_cards[key] = card

        # How-to guide
        guide_frame = tk.Frame(self, bg=COLORS["surface"], bd=0, relief=tk.FLAT)
        guide_frame.pack(fill=tk.X, padx=30, pady=(0, 20))

        tk.Label(
            guide_frame, text="Quick Start Guide",
            font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w", padx=20, pady=(15, 8))

        steps = [
            ("1", "Enroll Users",
             "Go to  Enroll User  and record each person's walking pattern.\n"
             "Walk sideways or diagonally in front of the camera for 6–8 seconds.\n"
             "Add at least 3 recordings per person for best accuracy."),
            ("2", "Train the Model",
             "After enrolling at least 2 users, click  Train Model  in the Enroll view.\n"
             "The system will learn each person's unique gait signature."),
            ("3", "Recognize",
             "Open  Recognize  and let the system identify who is walking.\n"
             "Results appear in real-time with a confidence score."),
        ]
        for num, title, desc in steps:
            row = tk.Frame(guide_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, padx=20, pady=6)

            num_lbl = tk.Label(
                row, text=num, font=FONTS["heading"],
                bg=COLORS["accent_dark"], fg=COLORS["accent_light"],
                width=3, relief=tk.FLAT
            )
            num_lbl.pack(side=tk.LEFT, padx=(0, 12))

            text_frame = tk.Frame(row, bg=COLORS["surface"])
            text_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(
                text_frame, text=title, font=FONTS["body_bold"],
                bg=COLORS["surface"], fg=COLORS["text"], anchor="w"
            ).pack(fill=tk.X)
            tk.Label(
                text_frame, text=desc, font=FONTS["small"],
                bg=COLORS["surface"], fg=COLORS["text_dim"],
                anchor="w", justify=tk.LEFT, wraplength=700
            ).pack(fill=tk.X)

        guide_frame.pack_configure(pady=(0, 20))
        tk.Frame(guide_frame, bg=COLORS["surface"], height=12).pack()

        # Recent recognitions
        rec_frame = tk.Frame(self, bg=COLORS["surface"])
        rec_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 25))

        tk.Label(
            rec_frame, text="Recent Recognitions",
            font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w", padx=20, pady=(15, 5))

        self._rec_list = tk.Frame(rec_frame, bg=COLORS["surface"])
        self._rec_list.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        self._no_rec_label = tk.Label(
            self._rec_list, text="No recognitions yet — run the Recognize view to see results here.",
            font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_muted"]
        )
        self._no_rec_label.pack(pady=20)

    def _make_stat_card(self, parent, label, value, accent_color):
        frame = tk.Frame(parent, bg=COLORS["surface"], relief=tk.FLAT, bd=0)

        tk.Label(
            frame, text=label, font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"]
        ).pack(anchor="w", padx=16, pady=(14, 2))

        val_label = tk.Label(
            frame, text=value, font=FONTS["big_num"],
            bg=COLORS["surface"], fg=accent_color
        )
        val_label.pack(anchor="w", padx=16, pady=(0, 14))
        frame._value_label = val_label
        frame._accent_color = accent_color
        return frame

    def refresh(self):
        """Refresh stats and recent recognitions."""
        stats = self.db.get_stats()

        self._stat_cards["users"]._value_label.config(text=str(stats["users"]))
        self._stat_cards["samples"]._value_label.config(text=str(stats["samples"]))
        self._stat_cards["recognitions"]._value_label.config(text=str(stats["recognitions"]))

        if self.recognizer.is_trained:
            acc = self.recognizer.cv_accuracy
            model_text = f"Trained ({self.recognizer.n_classes} users)"
            if acc > 0:
                model_text = f"✓ Trained\n{acc*100:.0f}% CV acc"
            self._stat_cards["model"]._value_label.config(
                text=model_text, fg=COLORS["success_light"],
                font=("Helvetica", 16, "bold")
            )
        else:
            self._stat_cards["model"]._value_label.config(
                text="Not trained", fg=COLORS["warning_light"],
                font=FONTS["heading"]
            )

        # Recent recognitions
        for w in self._rec_list.winfo_children():
            w.destroy()

        recs = self.db.get_recent_recognitions(10)
        if not recs:
            tk.Label(
                self._rec_list,
                text="No recognitions yet — run the Recognize view to see results here.",
                font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_muted"]
            ).pack(pady=20)
            return

        header = tk.Frame(self._rec_list, bg=COLORS["surface2"])
        header.pack(fill=tk.X, pady=(0, 2))
        for col, w in [("Time", 80), ("Identified As", 200), ("Confidence", 100)]:
            tk.Label(
                header, text=col, font=FONTS["body_bold"],
                bg=COLORS["surface2"], fg=COLORS["text_dim"], width=w // 8, anchor="w"
            ).pack(side=tk.LEFT, padx=8, pady=4)

        for name, conf, time_str in recs:
            row = tk.Frame(self._rec_list, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=1)
            color = COLORS["success_light"] if name != "Unknown" else COLORS["text_muted"]
            for text, w in [(time_str, 80), (name, 200), (f"{conf*100:.0f}%", 100)]:
                tk.Label(
                    row, text=text, font=FONTS["body"],
                    bg=COLORS["surface"], fg=color if text == name else COLORS["text_dim"],
                    width=w // 8, anchor="w"
                ).pack(side=tk.LEFT, padx=8, pady=3)
