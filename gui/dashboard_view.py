"""Dashboard — system overview, stats, and recent activity."""
import tkinter as tk
from gui.theme import COLORS, FONTS, make_btn


class DashboardView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Scrollable canvas wrapper
        canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        vsb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                           bg=COLORS["surface2"], troughcolor=COLORS["surface"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_frame = tk.Frame(canvas, bg=COLORS["bg"])
        self._scroll_win = canvas.create_window((0, 0), window=self._scroll_frame, anchor="nw")
        self._scroll_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._scroll_win, width=e.width))

        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._inner = self._scroll_frame
        self._build_content()

    def _build_content(self):
        p = self._inner

        # Page header
        hdr = tk.Frame(p, bg=COLORS["bg"])
        hdr.pack(fill=tk.X, padx=30, pady=(28, 0))
        tk.Label(hdr, text="Dashboard", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(side=tk.LEFT, anchor="w")

        # Stat cards
        cards_row = tk.Frame(p, bg=COLORS["bg"])
        cards_row.pack(fill=tk.X, padx=30, pady=(20, 0))

        card_defs = [
            ("users",        "Enrolled Users",   "—", COLORS["accent_light"],   COLORS["accent"]),
            ("samples",      "Gait Samples",     "—", COLORS["success_light"],  COLORS["success"]),
            ("recognitions", "Total Events",     "—", COLORS["warning_light"],  COLORS["warning"]),
            ("model",        "Model Status",     "—", COLORS["text_dim"],       COLORS["surface3"]),
        ]
        self._stat_cards = {}
        for key, label, val, color, bar_color in card_defs:
            card = self._stat_card(cards_row, label, val, color, bar_color)
            card.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 10))
            self._stat_cards[key] = card

        # Two-column layout below stats
        cols = tk.Frame(p, bg=COLORS["bg"])
        cols.pack(fill=tk.BOTH, expand=True, padx=30, pady=(20, 0))

        # Left column: quick-start guide
        left = tk.Frame(cols, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        guide_outer = tk.Frame(left, bg=COLORS["border"])
        guide_outer.pack(fill=tk.X)
        guide_card = tk.Frame(guide_outer, bg=COLORS["surface"])
        guide_card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Frame(guide_card, bg=COLORS["accent"], height=3).pack(fill=tk.X)

        tk.Label(guide_card, text="Quick Start", font=FONTS["subheading"],
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(anchor="w", padx=18, pady=(14, 4))
        tk.Frame(guide_card, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=18, pady=(0, 8))

        steps = [
            ("1", "Enroll Users",
             "Go to Enroll User and record each person walking.\n"
             "Aim for at least 3 recordings per person."),
            ("2", "Train the Model",
             "After enrolling 2+ users, click Train Model.\n"
             "The system learns each person's unique gait signature."),
            ("3", "Recognize",
             "Open Recognize and walk in front of the camera.\n"
             "Results and confidence appear in real time."),
        ]
        for num, title, desc in steps:
            row = tk.Frame(guide_card, bg=COLORS["surface"])
            row.pack(fill=tk.X, padx=18, pady=6)

            badge = tk.Frame(row, bg=COLORS["accent_dark"], width=32, height=32)
            badge.pack(side=tk.LEFT, padx=(0, 12))
            badge.pack_propagate(False)
            tk.Label(badge, text=num, font=FONTS["body_bold"],
                     bg=COLORS["accent_dark"], fg=COLORS["accent_light"]).place(relx=.5, rely=.5, anchor="center")

            text_col = tk.Frame(row, bg=COLORS["surface"])
            text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            tk.Label(text_col, text=title, font=FONTS["body_bold"],
                     bg=COLORS["surface"], fg=COLORS["text"], anchor="w").pack(fill=tk.X)
            tk.Label(text_col, text=desc, font=FONTS["small"],
                     bg=COLORS["surface"], fg=COLORS["text_dim"],
                     anchor="w", justify=tk.LEFT, wraplength=380).pack(fill=tk.X)

        tk.Frame(guide_card, height=12, bg=COLORS["surface"]).pack()

        # Right column: recent activity
        right = tk.Frame(cols, bg=COLORS["bg"], width=340)
        right.pack(side=tk.RIGHT, fill=tk.BOTH)
        right.pack_propagate(False)

        rec_outer = tk.Frame(right, bg=COLORS["border"])
        rec_outer.pack(fill=tk.BOTH, expand=True)
        rec_card = tk.Frame(rec_outer, bg=COLORS["surface"])
        rec_card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Frame(rec_card, bg=COLORS["success"], height=3).pack(fill=tk.X)

        rec_hdr = tk.Frame(rec_card, bg=COLORS["surface"])
        rec_hdr.pack(fill=tk.X, padx=18, pady=(14, 4))
        tk.Label(rec_hdr, text="Recent Activity", font=FONTS["subheading"],
                 bg=COLORS["surface"], fg=COLORS["text"]).pack(side=tk.LEFT, anchor="w")

        tk.Frame(rec_card, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=18, pady=(0, 0))

        self._rec_frame = tk.Frame(rec_card, bg=COLORS["surface"])
        self._rec_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=(8, 14))

        tk.Frame(p, height=24, bg=COLORS["bg"]).pack()

    def _stat_card(self, parent, label, value, color, bar_color):
        outer = tk.Frame(parent, bg=COLORS["border"])
        card  = tk.Frame(outer, bg=COLORS["surface"])
        card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        tk.Frame(card, bg=bar_color, height=3).pack(fill=tk.X)
        tk.Label(card, text=label, font=FONTS["small"],
                 bg=COLORS["surface"], fg=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(12, 2))
        val_lbl = tk.Label(card, text=value, font=FONTS["big_num"],
                           bg=COLORS["surface"], fg=color)
        val_lbl.pack(anchor="w", padx=16, pady=(0, 14))
        outer._val = val_lbl
        outer._color = color
        return outer

    # ── Refresh ───────────────────────────────────────────────────────────────

    def refresh(self):
        stats = self.db.get_stats()
        self._stat_cards["users"]._val.config(text=str(stats["users"]))
        self._stat_cards["samples"]._val.config(text=str(stats["samples"]))
        self._stat_cards["recognitions"]._val.config(text=str(stats["recognitions"]))

        if self.recognizer.is_trained:
            acc = self.recognizer.cv_accuracy
            txt = f"Trained"
            if acc > 0:
                txt = f"Trained\n{acc*100:.0f}% CV"
            self._stat_cards["model"]._val.config(
                text=txt, fg=COLORS["success_light"], font=FONTS["heading"]
            )
        else:
            self._stat_cards["model"]._val.config(
                text="Not\ntrained", fg=COLORS["warning_light"], font=FONTS["heading"]
            )

        # Recent activity list
        for w in self._rec_frame.winfo_children():
            w.destroy()

        recs = self.db.get_recent_recognitions(12)
        if not recs:
            tk.Label(
                self._rec_frame,
                text="No activity yet.\nRun Recognize to see results here.",
                font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_muted"],
                justify=tk.CENTER
            ).pack(pady=20)
            return

        # Column headers
        hdr = tk.Frame(self._rec_frame, bg=COLORS["surface2"])
        hdr.pack(fill=tk.X, pady=(0, 4))
        for col, width, anchor in [("Time", 9, "w"), ("Person", 16, "w"), ("Conf.", 6, "e")]:
            tk.Label(hdr, text=col, font=FONTS["caption"],
                     bg=COLORS["surface2"], fg=COLORS["text_muted"],
                     width=width, anchor=anchor).pack(side=tk.LEFT, padx=6, pady=5)

        for name, conf, time_str in recs:
            is_id = name != "Unknown"
            row = tk.Frame(self._rec_frame, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=1)
            dot_color = COLORS["success_light"] if is_id else COLORS["text_muted"]
            name_color = COLORS["text"] if is_id else COLORS["text_muted"]

            tk.Label(row, text=time_str, font=FONTS["mono"],
                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                     width=9, anchor="w").pack(side=tk.LEFT, padx=(6, 0), pady=4)
            tk.Label(row, text=name, font=FONTS["body_bold"],
                     bg=COLORS["surface"], fg=name_color,
                     width=16, anchor="w").pack(side=tk.LEFT, padx=(4, 0))
            tk.Label(row, text=f"{conf*100:.0f}%", font=FONTS["small"],
                     bg=COLORS["surface"], fg=dot_color,
                     width=6, anchor="e").pack(side=tk.LEFT, padx=(0, 6))

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self.refresh()

    def on_hide(self):
        pass
