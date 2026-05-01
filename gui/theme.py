"""Shared color palette and font definitions for the GUI."""

COLORS = {
    "bg":             "#0f172a",
    "surface":        "#1e293b",
    "surface2":       "#334155",
    "surface3":       "#475569",
    "accent":         "#7c3aed",
    "accent_hover":   "#8b5cf6",
    "accent_dark":    "#4c1d95",
    "accent_light":   "#a78bfa",
    "success":        "#059669",
    "success_light":  "#34d399",
    "warning":        "#d97706",
    "warning_light":  "#fbbf24",
    "error":          "#dc2626",
    "error_light":    "#f87171",
    "text":           "#f1f5f9",
    "text_dim":       "#94a3b8",
    "text_muted":     "#64748b",
    "border":         "#334155",
    "highlight":      "#1e3a5f",
}

FONTS = {
    "title":     ("Helvetica", 22, "bold"),
    "heading":   ("Helvetica", 15, "bold"),
    "subheading":("Helvetica", 12, "bold"),
    "body":      ("Helvetica", 11),
    "body_bold": ("Helvetica", 11, "bold"),
    "small":     ("Helvetica", 9),
    "mono":      ("Courier", 10),
    "mono_bold": ("Courier", 10, "bold"),
    "nav":       ("Helvetica", 12, "bold"),
    "big_num":   ("Helvetica", 32, "bold"),
}

NAV_ITEMS = [
    ("dashboard",  "  Dashboard",   "🏠"),
    ("enroll",     "  Enroll User", "➕"),
    ("recognize",  "  Recognize",   "🔍"),
    ("database",   "  Database",    "🗄"),
    ("settings",   "  Settings",    "⚙"),
]
