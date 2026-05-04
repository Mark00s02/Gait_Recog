"""Main application window for the Gait Recognition System."""
import os
import sys
import tkinter as tk
from tkinter import messagebox

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gui.theme import COLORS, FONTS, NAV_ITEMS
from gui.dashboard_view import DashboardView
from gui.enroll_view    import EnrollView
from gui.recognize_view import RecognizeView
from gui.log_view       import LogView
from gui.database_view  import DatabaseView
from gui.settings_view  import SettingsView
from src.database       import GaitDatabase
from src.recognizer     import GaitRecognizer


class GaitRecognitionApp(tk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, bg=COLORS["bg"])
        self.root = root
        self.pack(fill=tk.BOTH, expand=True)

        root.title("Gait Recognition System")
        root.geometry("1340x860")
        root.minsize(1080, 700)
        root.configure(bg=COLORS["bg"])
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            icon_path = os.path.join(ROOT, "assets", "icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass

        db_path   = os.path.join(ROOT, "data", "gait.db")
        model_dir = os.path.join(ROOT, "models")
        self.db         = GaitDatabase(db_path)
        self.recognizer = GaitRecognizer(model_dir)

        self._current_view_name = None
        self._nav_items: dict = {}
        self._views: dict = {}

        self._build_layout()
        self._build_views()
        self._navigate("dashboard")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Header ──
        header = tk.Frame(self, bg=COLORS["surface"], height=58)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        logo_box = tk.Frame(header, bg=COLORS["accent_dark"], width=58, height=58)
        logo_box.pack(side=tk.LEFT)
        logo_box.pack_propagate(False)
        tk.Label(
            logo_box, text="👣", font=("Segoe UI", 22),
            bg=COLORS["accent_dark"], fg=COLORS["accent_light"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        title_block = tk.Frame(header, bg=COLORS["surface"])
        title_block.pack(side=tk.LEFT, padx=16, fill=tk.Y)
        tk.Label(
            title_block, text="Gait Recognition",
            font=FONTS["heading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w", pady=(10, 0))
        tk.Label(
            title_block, text="Identity through motion",
            font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"]
        ).pack(anchor="w")

        # Thin separator line below header
        tk.Frame(header, bg=COLORS["border"], width=1).pack(side=tk.RIGHT, fill=tk.Y)

        self._header_status = tk.Label(
            header, text="", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"]
        )
        self._header_status.pack(side=tk.RIGHT, padx=20)

        # ── Body row ──
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # ── Sidebar ──
        sidebar = tk.Frame(body, bg=COLORS["sidebar_bg"], width=210)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # Right border of sidebar
        tk.Frame(body, bg=COLORS["border"], width=1).pack(side=tk.LEFT, fill=tk.Y)

        tk.Frame(sidebar, bg=COLORS["sidebar_bg"], height=16).pack()

        tk.Label(
            sidebar, text="NAVIGATION",
            font=FONTS["caption"], bg=COLORS["sidebar_bg"], fg=COLORS["text_muted"]
        ).pack(anchor="w", padx=18, pady=(0, 6))

        for key, label, icon in NAV_ITEMS:
            item = self._make_nav_item(sidebar, key, icon, label)
            self._nav_items[key] = item

        # Version at bottom
        tk.Label(
            sidebar, text="v1.1.0",
            font=FONTS["caption"], bg=COLORS["sidebar_bg"], fg=COLORS["text_muted"]
        ).pack(side=tk.BOTTOM, pady=12)

        # ── Content area ──
        self._content = tk.Frame(body, bg=COLORS["bg"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _make_nav_item(self, parent, key: str, icon: str, label: str) -> dict:
        row = tk.Frame(parent, bg=COLORS["sidebar_bg"], height=40, cursor="hand2")
        row.pack(fill=tk.X, padx=8, pady=1)
        row.pack_propagate(False)

        bar = tk.Frame(row, bg=COLORS["sidebar_bg"], width=3)
        bar.pack(side=tk.LEFT, fill=tk.Y)

        lbl = tk.Label(
            row, text=f"  {icon}   {label}",
            font=FONTS["nav"], bg=COLORS["sidebar_bg"], fg=COLORS["text_muted"],
            anchor="w", padx=8
        )
        lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def on_click(_):
            self._navigate(key)

        def on_enter(_):
            if self._current_view_name != key:
                row.config(bg=COLORS["surface2"])
                lbl.config(bg=COLORS["surface2"])

        def on_leave(_):
            if self._current_view_name != key:
                row.config(bg=COLORS["sidebar_bg"])
                lbl.config(bg=COLORS["sidebar_bg"])

        for w in (row, lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)

        return {"row": row, "bar": bar, "lbl": lbl}

    def _set_nav_active(self, key: str):
        for k, item in self._nav_items.items():
            active = k == key
            if active:
                item["row"].config(bg=COLORS["nav_active_bg"])
                item["bar"].config(bg=COLORS["nav_active_bar"])
                item["lbl"].config(bg=COLORS["nav_active_bg"], fg=COLORS["accent_light"])
            else:
                item["row"].config(bg=COLORS["sidebar_bg"])
                item["bar"].config(bg=COLORS["sidebar_bg"])
                item["lbl"].config(bg=COLORS["sidebar_bg"], fg=COLORS["text_muted"])

    # ── Views ─────────────────────────────────────────────────────────────────

    def _build_views(self):
        shared = dict(db=self.db, recognizer=self.recognizer)
        self._views["dashboard"] = DashboardView(self._content, **shared)
        self._views["enroll"]    = EnrollView(
            self._content, **shared, on_model_updated=self._on_model_updated
        )
        self._views["recognize"] = RecognizeView(self._content, **shared)
        self._views["log"]       = LogView(self._content, **shared)
        self._views["database"]  = DatabaseView(
            self._content, **shared, on_model_updated=self._on_model_updated
        )
        self._views["settings"]  = SettingsView(self._content, **shared)

    def _navigate(self, key: str):
        if key == self._current_view_name:
            return

        if self._current_view_name and self._current_view_name in self._views:
            view = self._views[self._current_view_name]
            if hasattr(view, "on_hide"):
                view.on_hide()
            view.pack_forget()

        self._current_view_name = key
        self._set_nav_active(key)

        view = self._views[key]
        view.pack(fill=tk.BOTH, expand=True)
        if hasattr(view, "on_show"):
            view.on_show()

        self._update_header_status()

    def _on_model_updated(self):
        self._update_header_status()
        if self._current_view_name == "dashboard":
            self._views["dashboard"].refresh()

    def _update_header_status(self):
        stats = self.db.get_stats()
        if self.recognizer.is_trained:
            acc = self.recognizer.cv_accuracy
            acc_str = f"  ·  CV {acc*100:.0f}%" if acc > 0 else ""
            status = (
                f"Model ready  ·  {stats['users']} users  ·  "
                f"{stats['samples']} samples{acc_str}  ·  "
                f"{stats['recognitions']} events"
            )
            color = COLORS["success_light"]
        else:
            status = f"{stats['users']} users enrolled  ·  Model not trained"
            color  = COLORS["warning_light"]
        self._header_status.config(text=status, fg=color)

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        for key in ("enroll", "recognize"):
            if key in self._views:
                view = self._views[key]
                if hasattr(view, "on_hide"):
                    try:
                        view.on_hide()
                    except Exception:
                        pass
        self.root.destroy()
