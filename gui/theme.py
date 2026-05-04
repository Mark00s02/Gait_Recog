"""Design system: colors, fonts, and UI helper factories."""
import platform
import tkinter as tk

_F    = "Segoe UI"  if platform.system() == "Windows" else "Helvetica"
_MONO = "Consolas"  if platform.system() == "Windows" else "Courier"

COLORS = {
    # Backgrounds
    "bg":             "#070c1a",
    "surface":        "#0d1526",
    "surface2":       "#162035",
    "surface3":       "#1e2d4a",
    "border":         "#1a2744",
    # Accent (purple)
    "accent":         "#7c3aed",
    "accent_hover":   "#8b5cf6",
    "accent_dark":    "#3b0764",
    "accent_light":   "#a78bfa",
    # Semantic
    "success":        "#059669",
    "success_light":  "#10b981",
    "success_bg":     "#022c22",
    "warning":        "#d97706",
    "warning_light":  "#f59e0b",
    "warning_bg":     "#2d1a00",
    "error":          "#dc2626",
    "error_light":    "#ef4444",
    "error_bg":       "#2d0a0a",
    # Text
    "text":           "#f1f5f9",
    "text_dim":       "#94a3b8",
    "text_muted":     "#475569",
    # Sidebar
    "sidebar_bg":     "#060a14",
    "nav_active_bg":  "#130d2e",
    "nav_active_bar": "#7c3aed",
    # Misc
    "highlight":      "#1e3a5f",
    "photo_bg":       "#0d1526",
}

FONTS = {
    "title":      (_F, 22, "bold"),
    "heading":    (_F, 14, "bold"),
    "subheading": (_F, 11, "bold"),
    "body":       (_F, 10),
    "body_bold":  (_F, 10, "bold"),
    "small":      (_F, 9),
    "caption":    (_F, 8),
    "mono":       (_MONO, 10),
    "mono_bold":  (_MONO, 10, "bold"),
    "nav":        (_F, 10, "bold"),
    "big_num":    (_F, 32, "bold"),
    "med_num":    (_F, 18, "bold"),
}

NAV_ITEMS = [
    ("dashboard", "Dashboard",    "⬡"),
    ("enroll",    "Enroll User",  "+"),
    ("recognize", "Recognize",    "◎"),
    ("log",       "Activity Log", "≡"),
    ("database",  "Database",     "⊞"),
    ("settings",  "Settings",     "✦"),
]


def make_card(parent, title: str = None, accent_top: str = None) -> tk.Frame:
    """
    Returns a styled card frame. Caller packs the outer border frame,
    places widgets inside the returned inner content frame.
    Usage:
        outer, inner = make_card(parent, "My Section")
        outer.pack(fill=tk.X, padx=24, pady=6)
        tk.Label(inner, text="hello").pack()
    """
    outer = tk.Frame(parent, bg=COLORS["border"])
    card  = tk.Frame(outer, bg=COLORS["surface"])
    card.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

    if accent_top:
        tk.Frame(card, bg=accent_top, height=3).pack(fill=tk.X)

    if title:
        tk.Label(
            card, text=title,
            font=FONTS["subheading"], bg=COLORS["surface"], fg=COLORS["text"]
        ).pack(anchor="w", padx=18, pady=(14, 0))
        tk.Frame(card, bg=COLORS["border"], height=1).pack(fill=tk.X, padx=18, pady=(8, 0))

    inner = tk.Frame(card, bg=COLORS["surface"])
    inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=12)
    return outer, inner


def make_btn(parent, text: str, cmd, bg: str,
             hover_bg: str = None, fg: str = None,
             pady: int = 9, padx: int = 14) -> tk.Button:
    """Styled button with hover effect."""
    fg = fg or COLORS["text"]
    hover = hover_bg or COLORS["surface3"]
    b = tk.Button(
        parent, text=text, command=cmd,
        font=FONTS["body_bold"], bg=bg, fg=fg,
        relief=tk.FLAT, cursor="hand2", bd=0,
        activebackground=hover, activeforeground=COLORS["text"],
        pady=pady, padx=padx
    )
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b
