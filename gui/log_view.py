"""Activity Log view — full recognition history and attendance tracker."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from gui.theme import COLORS, FONTS, make_btn


class LogView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self._filter_var = tk.StringVar(value="All")
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Page header
        hdr = tk.Frame(self, bg=COLORS["bg"])
        hdr.pack(fill=tk.X, padx=30, pady=(24, 0))
        tk.Label(hdr, text="Activity Log", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(hdr, text="Full recognition history and attendance records.",
                 font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(2, 0))

        # Stats row
        stats_row = tk.Frame(self, bg=COLORS["bg"])
        stats_row.pack(fill=tk.X, padx=30, pady=(16, 0))
        self._stat_vals = {}
        defs = [
            ("total",     "Total Events",   COLORS["accent_light"]),
            ("rate",      "ID Rate",        COLORS["success_light"]),
            ("most_freq", "Most Frequent",  COLORS["warning_light"]),
            ("avg_conf",  "Avg Confidence", COLORS["text_dim"]),
        ]
        for key, label, color in defs:
            c = self._stat_card(stats_row, label, "—", color)
            c.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=(0, 8))
            self._stat_vals[key] = c._val

        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=30, pady=(16, 8))

        tk.Label(toolbar, text="Filter by person:", font=FONTS["small"],
                 bg=COLORS["bg"], fg=COLORS["text_muted"]).pack(side=tk.LEFT, padx=(0, 6))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Log.TCombobox",
            fieldbackground=COLORS["surface2"],
            background=COLORS["surface2"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["text_dim"],
            borderwidth=0,
        )
        self._filter_menu = ttk.Combobox(
            toolbar, textvariable=self._filter_var,
            state="readonly", width=20, font=FONTS["body"],
            style="Log.TCombobox"
        )
        self._filter_menu.pack(side=tk.LEFT, padx=(0, 14))
        self._filter_menu.bind("<<ComboboxSelected>>", lambda e: self._load_rows())

        make_btn(toolbar, "  Refresh",    self.refresh,      COLORS["surface2"], COLORS["surface3"]).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(toolbar, "  Export CSV", self._export_csv,  COLORS["accent"],   COLORS["accent_hover"]).pack(side=tk.LEFT, padx=(0, 8))
        make_btn(toolbar, "  Clear Log",  self._clear_log,   COLORS["error"],    "#b91c1c").pack(side=tk.RIGHT)

        # Table area
        wrap = tk.Frame(self, bg=COLORS["border"])
        wrap.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 24))
        inner = tk.Frame(wrap, bg=COLORS["surface"])
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        style.configure("Log.Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=34,
            fieldbackground=COLORS["surface"],
            borderwidth=0,
            font=FONTS["body"],
        )
        style.configure("Log.Treeview.Heading",
            background=COLORS["surface2"],
            foreground=COLORS["text_dim"],
            font=FONTS["body_bold"],
            relief="flat",
            borderwidth=0,
            padding=(8, 8),
        )
        style.map("Log.Treeview",
            background=[("selected", COLORS["accent_dark"])],
            foreground=[("selected", COLORS["text"])],
        )
        style.configure("Log.Vertical.TScrollbar",
            background=COLORS["surface2"],
            troughcolor=COLORS["surface"],
            borderwidth=0,
            arrowcolor=COLORS["text_muted"],
        )

        cols = ("datetime", "person", "confidence", "status")
        self._tree = ttk.Treeview(
            inner, columns=cols, show="headings",
            style="Log.Treeview", selectmode="none"
        )
        self._tree.heading("datetime",   text="Date & Time",  anchor="w")
        self._tree.heading("person",     text="Person",       anchor="w")
        self._tree.heading("confidence", text="Confidence",   anchor="center")
        self._tree.heading("status",     text="Status",       anchor="center")
        self._tree.column("datetime",    width=210, anchor="w", minwidth=150)
        self._tree.column("person",      width=240, anchor="w", minwidth=120)
        self._tree.column("confidence",  width=130, anchor="center", minwidth=80)
        self._tree.column("status",      width=140, anchor="center", minwidth=80)
        self._tree.tag_configure("identified", foreground=COLORS["success_light"])
        self._tree.tag_configure("unknown",    foreground=COLORS["text_muted"])

        vsb = ttk.Scrollbar(inner, orient="vertical", command=self._tree.yview,
                            style="Log.Vertical.TScrollbar")
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.refresh()

    def _stat_card(self, parent, label, value, color):
        f = tk.Frame(parent, bg=COLORS["surface2"])
        tk.Frame(f, bg=color, height=3).pack(fill=tk.X)
        tk.Label(f, text=label, font=FONTS["small"],
                 bg=COLORS["surface2"], fg=COLORS["text_muted"]).pack(anchor="w", padx=14, pady=(10, 2))
        val = tk.Label(f, text=value, font=FONTS["med_num"],
                       bg=COLORS["surface2"], fg=color)
        val.pack(anchor="w", padx=14, pady=(0, 12))
        f._val = val
        return f

    # ── Data loading ──────────────────────────────────────────────────────────

    def refresh(self):
        self._update_filter_options()
        self._update_stats()
        self._load_rows()

    def _update_filter_options(self):
        names = ["All"] + self.db.get_unique_log_names()
        current = self._filter_var.get()
        self._filter_menu["values"] = names
        if current not in names:
            self._filter_var.set("All")

    def _update_stats(self):
        s = self.db.get_log_stats()
        self._stat_vals["total"].config(text=str(s["total"]))
        self._stat_vals["rate"].config(text=f"{s['rate']:.0f}%")
        self._stat_vals["most_freq"].config(text=s["most_freq"])
        conf = s["avg_conf"]
        self._stat_vals["avg_conf"].config(text=f"{conf*100:.0f}%" if conf else "—")

    def _load_rows(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        person = self._filter_var.get()
        rows = self.db.get_all_recognitions(
            limit=1000, person=person if person != "All" else None
        )
        for name, conf, dt in rows:
            is_id = name != "Unknown"
            tag = "identified" if is_id else "unknown"
            status = "✓  Identified" if is_id else "?  Unknown"
            self._tree.insert("", "end",
                values=(dt, name, f"{conf*100:.0f}%", status),
                tags=(tag,))

    # ── Actions ───────────────────────────────────────────────────────────────

    def _export_csv(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="gait_recognition_log.csv",
            title="Export Recognition Log",
        )
        if path:
            try:
                self.db.export_log_csv(path)
                messagebox.showinfo("Export Complete", f"Log exported to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Failed", str(exc))

    def _clear_log(self):
        if messagebox.askyesno(
            "Clear Activity Log",
            "Delete the entire recognition history?\nThis cannot be undone.",
            icon="warning",
        ):
            self.db.clear_recognition_log()
            self.refresh()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self.refresh()

    def on_hide(self):
        pass
