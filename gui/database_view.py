"""Database view — browse users, delete records, and view per-user analytics."""
import io
import tkinter as tk
from tkinter import messagebox, ttk

from gui.theme import COLORS, FONTS, make_btn


class DatabaseView(tk.Frame):
    def __init__(self, parent, db, recognizer, on_model_updated=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self.on_model_updated = on_model_updated
        self._selected_uid  = None
        self._selected_name = None
        self._photo_ref     = None
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Page header
        hdr = tk.Frame(self, bg=COLORS["bg"])
        hdr.pack(fill=tk.X, padx=30, pady=(24, 0))
        tk.Label(hdr, text="User Database", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(hdr, text="Manage enrolled users, gait samples, and view per-user analytics.",
                 font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(2, 0))

        # Toolbar
        tb = tk.Frame(self, bg=COLORS["bg"])
        tb.pack(fill=tk.X, padx=30, pady=(14, 8))

        make_btn(tb, "  Refresh",          self.refresh,         COLORS["surface2"], COLORS["surface3"]).pack(side=tk.LEFT, padx=(0, 8))
        self._btn_del_samples = make_btn(tb, "  Clear Samples",  self._delete_samples, COLORS["warning"], "#b45309")
        self._btn_del_samples.pack(side=tk.LEFT, padx=(0, 8))
        self._btn_del_samples.config(state=tk.DISABLED)

        self._btn_del_user = make_btn(tb, "  Delete User",       self._delete_user,    COLORS["error"], "#b91c1c")
        self._btn_del_user.pack(side=tk.LEFT, padx=(0, 8))
        self._btn_del_user.config(state=tk.DISABLED)

        make_btn(tb, "🧠  Retrain Model",  self._retrain,        COLORS["accent"], COLORS["accent_hover"]).pack(side=tk.RIGHT)

        # Body: table left + analytics right
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))

        # ── Table ──
        table_outer = tk.Frame(body, bg=COLORS["border"])
        table_outer.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        table_inner = tk.Frame(table_outer, bg=COLORS["surface"])
        table_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure("DB.Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=34,
            fieldbackground=COLORS["surface"],
            borderwidth=0,
            font=FONTS["body"],
        )
        style.configure("DB.Treeview.Heading",
            background=COLORS["surface2"],
            foreground=COLORS["text_dim"],
            font=FONTS["body_bold"],
            relief="flat",
            borderwidth=0,
            padding=(8, 8),
        )
        style.map("DB.Treeview",
            background=[("selected", COLORS["accent_dark"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure("DB.Vertical.TScrollbar",
            background=COLORS["surface2"],
            troughcolor=COLORS["surface"],
            borderwidth=0,
            arrowcolor=COLORS["text_muted"],
        )

        cols = ("name", "samples", "created")
        self._tree = ttk.Treeview(table_inner, columns=cols, show="headings",
                                   style="DB.Treeview", selectmode="browse")
        self._tree.heading("name",    text="Name",          anchor="w")
        self._tree.heading("samples", text="Samples",       anchor="center")
        self._tree.heading("created", text="Date Enrolled", anchor="w")
        self._tree.column("name",    width=240, anchor="w",      minwidth=120)
        self._tree.column("samples", width=100, anchor="center",  minwidth=60)
        self._tree.column("created", width=180, anchor="w",      minwidth=120)
        self._tree.tag_configure("good",  foreground=COLORS["success_light"])
        self._tree.tag_configure("warn",  foreground=COLORS["warning_light"])
        self._tree.tag_configure("err",   foreground=COLORS["error_light"])

        vsb = ttk.Scrollbar(table_inner, orient="vertical", command=self._tree.yview,
                            style="DB.Vertical.TScrollbar")
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # ── Analytics panel ──
        self._analytics_outer = tk.Frame(body, bg=COLORS["border"], width=262)
        self._analytics_outer.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        self._analytics_outer.pack_propagate(False)
        self._analytics_card = tk.Frame(self._analytics_outer, bg=COLORS["surface"])
        self._analytics_card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        tk.Frame(self._analytics_card, bg=COLORS["accent"], height=3).pack(fill=tk.X)
        tk.Label(self._analytics_card, text="User Analytics",
                 font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text"]
                 ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Frame(self._analytics_card, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=16, pady=(0, 10))

        self._analytics_content = tk.Frame(self._analytics_card, bg=COLORS["surface"])
        self._analytics_content.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

        self._analytics_placeholder = tk.Label(
            self._analytics_content,
            text="Select a user\nto view their analytics.",
            font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_muted"],
            justify=tk.CENTER
        )
        self._analytics_placeholder.pack(pady=30)

        # Status bar
        self._status_lbl = tk.Label(self, text="", font=FONTS["small"],
                                    bg=COLORS["bg"], fg=COLORS["text_muted"])
        self._status_lbl.pack(anchor="w", padx=30, pady=(0, 8))

        self.refresh()

    # ── Refresh / populate ────────────────────────────────────────────────────

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._selected_uid  = None
        self._selected_name = None
        self._btn_del_user.config(state=tk.DISABLED)
        self._btn_del_samples.config(state=tk.DISABLED)
        self._clear_analytics()

        for uid, name, count, created in self.db.get_all_users():
            tag = "good" if count >= 3 else ("warn" if count >= 1 else "err")
            self._tree.insert("", "end", iid=str(uid),
                              values=(name, count, created or "—"), tags=(tag,))

        stats = self.db.get_stats()
        model_str = (
            f"  ·  Model: trained ({self.recognizer.n_classes} users)"
            if self.recognizer.is_trained else "  ·  Model: not trained"
        )
        self._status_lbl.config(
            text=f"  {stats['users']} users  ·  {stats['samples']} samples{model_str}"
        )

    def _on_select(self, event):
        sel = self._tree.selection()
        if sel:
            self._selected_uid  = int(sel[0])
            row = self._tree.item(sel[0])
            self._selected_name = row["values"][0]
            self._btn_del_user.config(state=tk.NORMAL)
            self._btn_del_samples.config(state=tk.NORMAL)
            self._show_analytics(self._selected_uid, self._selected_name)
        else:
            self._selected_uid  = None
            self._selected_name = None
            self._btn_del_user.config(state=tk.DISABLED)
            self._btn_del_samples.config(state=tk.DISABLED)
            self._clear_analytics()

    # ── Analytics panel ───────────────────────────────────────────────────────

    def _clear_analytics(self):
        for w in self._analytics_content.winfo_children():
            w.destroy()
        self._analytics_placeholder = tk.Label(
            self._analytics_content,
            text="Select a user\nto view their analytics.",
            font=FONTS["body"], bg=COLORS["surface"], fg=COLORS["text_muted"],
            justify=tk.CENTER
        )
        self._analytics_placeholder.pack(pady=30)

    def _show_analytics(self, uid: int, name: str):
        for w in self._analytics_content.winfo_children():
            w.destroy()

        # Profile photo
        photo_bytes = self.db.get_user_photo(uid)
        photo_border = tk.Frame(self._analytics_content, bg=COLORS["border"],
                                width=100, height=100)
        photo_border.pack(pady=(4, 12))
        photo_border.pack_propagate(False)

        if photo_bytes:
            try:
                from PIL import Image, ImageTk
                img  = Image.open(io.BytesIO(photo_bytes)).resize((98, 98), Image.LANCZOS)
                tkimg = ImageTk.PhotoImage(img)
                lbl = tk.Label(photo_border, image=tkimg, bg=COLORS["surface2"])
                lbl.image = tkimg
                lbl.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
                self._photo_ref = tkimg
            except Exception:
                tk.Label(photo_border, text=name[0].upper(), font=FONTS["title"],
                         bg=COLORS["accent_dark"], fg=COLORS["accent_light"]).pack(
                    fill=tk.BOTH, expand=True, padx=1, pady=1)
        else:
            tk.Label(photo_border, text=name[0].upper() if name else "?",
                     font=FONTS["title"],
                     bg=COLORS["accent_dark"], fg=COLORS["accent_light"]).pack(
                fill=tk.BOTH, expand=True, padx=1, pady=1)

        # Name
        tk.Label(self._analytics_content, text=name, font=FONTS["body_bold"],
                 bg=COLORS["surface"], fg=COLORS["text"]).pack()

        # Stats from recognition log
        analytics = self.db.get_user_analytics(name)
        sample_count = self.db.get_user_sample_count(uid)

        tk.Frame(self._analytics_content, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=10)

        stats = [
            ("Gait Samples",    str(sample_count)),
            ("Total Recognized", str(analytics["total_recognitions"])),
            ("Avg Confidence",  f"{analytics['avg_confidence']*100:.0f}%"
             if analytics["avg_confidence"] else "—"),
            ("Last Seen",       analytics["last_seen"]),
        ]
        for label, value in stats:
            row = tk.Frame(self._analytics_content, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=FONTS["small"],
                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                     anchor="w", width=16).pack(side=tk.LEFT)
            tk.Label(row, text=value, font=FONTS["body_bold"],
                     bg=COLORS["surface"], fg=COLORS["text"],
                     anchor="e").pack(side=tk.RIGHT)

        # Status tag
        sample_color = COLORS["success_light"] if sample_count >= 3 else COLORS["warning_light"]
        sample_msg   = "Good sample count" if sample_count >= 3 else "Add more samples"
        tk.Frame(self._analytics_content, bg=COLORS["border"], height=1).pack(fill=tk.X, pady=10)
        tk.Label(self._analytics_content, text=sample_msg, font=FONTS["small"],
                 bg=COLORS["surface"], fg=sample_color).pack(anchor="w")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _delete_user(self):
        if self._selected_uid is None:
            return
        name = self._selected_name or "this user"
        if messagebox.askyesno(
            "Delete User",
            f"Delete '{name}' and all their gait samples?\nThis cannot be undone.",
            icon="warning"
        ):
            self.db.delete_user(self._selected_uid)
            self._selected_uid  = None
            self._selected_name = None
            self.refresh()
            if self.on_model_updated:
                self.on_model_updated()

    def _delete_samples(self):
        if self._selected_uid is None:
            return
        name = self._selected_name or "this user"
        if messagebox.askyesno(
            "Clear Samples",
            f"Delete all gait samples for '{name}'?\nThe user account will remain.",
            icon="warning"
        ):
            self.db.delete_user_samples(self._selected_uid)
            self.refresh()

    def _retrain(self):
        all_features, labels, label_names = self.db.get_all_samples()
        if not all_features:
            messagebox.showinfo("No Data", "No samples to train on.")
            return
        ok, msg = self.recognizer.train(all_features, labels, label_names)
        messagebox.showinfo("Training Result", msg)
        self.refresh()
        if ok and self.on_model_updated:
            self.on_model_updated()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self.refresh()

    def on_hide(self):
        pass
