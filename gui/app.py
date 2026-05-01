"""Main application window for the Gait Recognition System."""
import os
import sys
import tkinter as tk
from tkinter import messagebox

# Ensure src/ is importable
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gui.theme import COLORS, FONTS, NAV_ITEMS
from gui.dashboard_view  import DashboardView
from gui.enroll_view     import EnrollView
from gui.recognize_view  import RecognizeView
from gui.database_view   import DatabaseView
from gui.settings_view   import SettingsView
from src.database        import GaitDatabase
from src.recognizer      import GaitRecognizer


class GaitRecognitionApp(tk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, bg=COLORS["bg"])
        self.root = root
        self.pack(fill=tk.BOTH, expand=True)

        root.title("Gait Recognition System")
        root.geometry("1280x820")
        root.minsize(1000, 680)
        root.configure(bg=COLORS["bg"])
        root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Set window icon if available
        try:
            icon_path = os.path.join(ROOT, "assets", "icon.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass

        # Backend
        db_path = os.path.join(ROOT, "data", "gait.db")
        model_dir = os.path.join(ROOT, "models")
        self.db = GaitDatabase(db_path)
        self.recognizer = GaitRecognizer(model_dir)

        self._current_view_name = None
        self._nav_buttons: dict = {}
        self._views: dict = {}

        self._build_layout()
        self._build_views()
        self._navigate("dashboard")

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # Header
        header = tk.Frame(self, bg=COLORS["surface"], height=56)
        header.pack(fill=tk.X, side=tk.TOP)
        header.pack_propagate(False)

        logo_frame = tk.Frame(header, bg=COLORS["accent_dark"], width=56, height=56)
        logo_frame.pack(side=tk.LEFT)
        logo_frame.pack_propagate(False)
        tk.Label(
            logo_frame, text="👣", font=("Helvetica", 22),
            bg=COLORS["accent_dark"], fg=COLORS["accent_light"]
        ).place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            header, text="Gait Recognition System",
            font=FONTS["heading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(side=tk.LEFT, padx=16)

        self._header_status = tk.Label(
            header, text="", font=FONTS["small"],
            bg=COLORS["surface"], fg=COLORS["text_dim"]
        )
        self._header_status.pack(side=tk.RIGHT, padx=16)

        # Body row: sidebar + content
        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        sidebar = tk.Frame(body, bg=COLORS["surface"], width=200)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        tk.Frame(sidebar, bg=COLORS["surface"], height=10).pack()

        for key, label, icon in NAV_ITEMS:
            btn = self._make_nav_btn(sidebar, icon + label, key)
            btn.pack(fill=tk.X, padx=8, pady=2)
            self._nav_buttons[key] = btn

        # Version label at bottom of sidebar
        tk.Label(
            sidebar, text="v1.0.0",
            font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_muted"]
        ).pack(side=tk.BOTTOM, pady=10)

        # Content area
        self._content = tk.Frame(body, bg=COLORS["bg"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _make_nav_btn(self, parent, label: str, key: str) -> tk.Frame:
        frame = tk.Frame(parent, bg=COLORS["surface"], cursor="hand2", height=40)
        frame.pack_propagate(False)

        lbl = tk.Label(
            frame, text=label, font=FONTS["nav"],
            bg=COLORS["surface"], fg=COLORS["text_dim"],
            anchor="w", padx=12
        )
        lbl.place(relx=0, rely=0, relwidth=1, relheight=1)

        def on_enter(_):
            if self._current_view_name != key:
                frame.config(bg=COLORS["surface2"])
                lbl.config(bg=COLORS["surface2"])

        def on_leave(_):
            if self._current_view_name != key:
                frame.config(bg=COLORS["surface"])
                lbl.config(bg=COLORS["surface"])

        def on_click(_):
            self._navigate(key)

        for widget in (frame, lbl):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

        frame._label = lbl
        return frame

    def _set_nav_active(self, key: str):
        for k, btn in self._nav_buttons.items():
            active = k == key
            bg = COLORS["accent_dark"] if active else COLORS["surface"]
            fg = COLORS["accent_light"] if active else COLORS["text_dim"]
            btn.config(bg=bg)
            btn._label.config(bg=bg, fg=fg)

    # ── Views ─────────────────────────────────────────────────────────────────

    def _build_views(self):
        shared = dict(db=self.db, recognizer=self.recognizer)

        self._views["dashboard"] = DashboardView(
            self._content, **shared
        )
        self._views["enroll"] = EnrollView(
            self._content, **shared,
            on_model_updated=self._on_model_updated
        )
        self._views["recognize"] = RecognizeView(
            self._content, **shared
        )
        self._views["database"] = DatabaseView(
            self._content, **shared,
            on_model_updated=self._on_model_updated
        )
        self._views["settings"] = SettingsView(
            self._content, **shared
        )

    def _navigate(self, key: str):
        if key == self._current_view_name:
            return

        # Hide current
        if self._current_view_name and self._current_view_name in self._views:
            view = self._views[self._current_view_name]
            if hasattr(view, "on_hide"):
                view.on_hide()
            view.pack_forget()

        self._current_view_name = key
        self._set_nav_active(key)

        # Show new
        view = self._views[key]
        view.pack(fill=tk.BOTH, expand=True)
        if hasattr(view, "on_show"):
            view.on_show()

        self._update_header_status()

    def _on_model_updated(self):
        self._update_header_status()
        # Refresh dashboard if visible
        if self._current_view_name == "dashboard":
            self._views["dashboard"].refresh()

    def _update_header_status(self):
        stats = self.db.get_stats()
        if self.recognizer.is_trained:
            status = (
                f"Model ready  •  {stats['users']} users  •  "
                f"{stats['samples']} samples  •  "
                f"CV acc: {self.recognizer.cv_accuracy*100:.0f}%"
            )
            color = COLORS["success_light"]
        else:
            status = (
                f"{stats['users']} users enrolled  •  Model not trained"
            )
            color = COLORS["warning_light"]
        self._header_status.config(text=status, fg=color)

    # ── Close ─────────────────────────────────────────────────────────────────

    def _on_close(self):
        # Make sure camera is released in any active view
        for key in ("enroll", "recognize"):
            if key in self._views:
                view = self._views[key]
                if hasattr(view, "on_hide"):
                    try:
                        view.on_hide()
                    except Exception:
                        pass
        self.root.destroy()
