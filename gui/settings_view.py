"""Settings view — recognition threshold, model info, dependencies, data export."""
import tkinter as tk
from tkinter import messagebox, filedialog
import threading

from gui.theme import COLORS, FONTS, make_btn, make_card
from src.utils import check_dependencies


class SettingsView(tk.Frame):
    def __init__(self, parent, db, recognizer, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self._build()

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build(self):
        # Scrollable area
        canvas = tk.Canvas(self, bg=COLORS["bg"], highlightthickness=0)
        vsb = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                           bg=COLORS["surface2"], troughcolor=COLORS["surface"])
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        frame = tk.Frame(canvas, bg=COLORS["bg"])
        win   = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))

        def _scroll(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _scroll)

        self._frame = frame
        self._build_content()

    def _build_content(self):
        p = self._frame

        # Page header
        hdr = tk.Frame(p, bg=COLORS["bg"])
        hdr.pack(fill=tk.X, padx=30, pady=(24, 0))
        tk.Label(hdr, text="Settings", font=FONTS["title"],
                 bg=COLORS["bg"], fg=COLORS["text"]).pack(anchor="w")
        tk.Label(hdr, text="Configure recognition parameters, model options, and system tools.",
                 font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(2, 0))

        # Two-column layout
        cols = tk.Frame(p, bg=COLORS["bg"])
        cols.pack(fill=tk.BOTH, expand=True, padx=30, pady=(20, 0))

        left  = tk.Frame(cols, bg=COLORS["bg"])
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        right = tk.Frame(cols, bg=COLORS["bg"], width=320)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        # ── Left: threshold + model info ──
        self._build_threshold(left)
        tk.Frame(left, height=14, bg=COLORS["bg"]).pack()
        self._build_model_info(left)
        tk.Frame(left, height=14, bg=COLORS["bg"]).pack()
        self._build_data_tools(left)

        # ── Right: dependencies ──
        self._build_dependencies(right)

        tk.Frame(p, height=28, bg=COLORS["bg"]).pack()

    # ── Threshold card ────────────────────────────────────────────────────────

    def _build_threshold(self, parent):
        outer, inner = make_card(parent, "Recognition Threshold", COLORS["accent"])
        outer.pack(fill=tk.X)

        tk.Label(inner,
                 text="Minimum confidence required to identify a person.\n"
                      "Lower = more permissive.  Higher = fewer false identifications.",
                 font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_dim"],
                 justify=tk.LEFT).pack(anchor="w", pady=(0, 10))

        slider_row = tk.Frame(inner, bg=COLORS["surface"])
        slider_row.pack(fill=tk.X)

        self._threshold_var = tk.DoubleVar(value=self.recognizer.confidence_threshold)
        self._thresh_lbl = tk.Label(slider_row, font=FONTS["med_num"],
                                    bg=COLORS["surface"], fg=COLORS["accent_light"],
                                    text=f"{self.recognizer.confidence_threshold*100:.0f}%",
                                    width=5)
        self._thresh_lbl.pack(side=tk.RIGHT)

        scale = tk.Scale(
            slider_row, variable=self._threshold_var,
            from_=0.30, to=0.95, resolution=0.01, orient=tk.HORIZONTAL,
            bg=COLORS["surface"], fg=COLORS["text"], highlightbackground=COLORS["surface"],
            troughcolor=COLORS["surface2"], activebackground=COLORS["accent"],
            command=self._on_thresh_change, showvalue=False, length=340
        )
        scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        make_btn(inner, "Apply Threshold", self._apply_threshold,
                 COLORS["accent"], COLORS["accent_hover"], pady=7, padx=16
                 ).pack(anchor="e", pady=(10, 0))

    # ── Model info card ───────────────────────────────────────────────────────

    def _build_model_info(self, parent):
        outer, inner = make_card(parent, "Model Information", COLORS["success"])
        outer.pack(fill=tk.X)

        self._model_info_inner = inner
        self._refresh_model_info()

        make_btn(inner, "Reset Model (delete trained data)", self._reset_model,
                 COLORS["error"], "#b91c1c", pady=6, padx=12
                 ).pack(anchor="w", pady=(12, 0))

    def _refresh_model_info(self):
        for w in self._model_info_inner.winfo_children():
            w.destroy()

        items = [
            ("Status:",        "Trained ✓"  if self.recognizer.is_trained else "Not trained",
             COLORS["success_light"] if self.recognizer.is_trained else COLORS["warning_light"]),
            ("Users:",         str(self.recognizer.n_classes),      COLORS["text"]),
            ("CV Accuracy:",   (f"{self.recognizer.cv_accuracy*100:.1f}%"
                                if self.recognizer.cv_accuracy > 0 else "—"),  COLORS["text"]),
            ("Threshold:",     f"{self.recognizer.confidence_threshold*100:.0f}%", COLORS["text"]),
        ]
        for label, value, color in items:
            row = tk.Frame(self._model_info_inner, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=label, font=FONTS["body"],
                     bg=COLORS["surface"], fg=COLORS["text_muted"],
                     width=16, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, font=FONTS["body_bold"],
                     bg=COLORS["surface"], fg=color, anchor="w").pack(side=tk.LEFT)

    # ── Data tools card ───────────────────────────────────────────────────────

    def _build_data_tools(self, parent):
        outer, inner = make_card(parent, "Data Tools", COLORS["warning"])
        outer.pack(fill=tk.X)

        tk.Label(inner, text="Export the recognition log or all enrolled user data.",
                 font=FONTS["small"], bg=COLORS["surface"], fg=COLORS["text_dim"]).pack(anchor="w", pady=(0, 10))

        row = tk.Frame(inner, bg=COLORS["surface"])
        row.pack(fill=tk.X)
        make_btn(row, "Export Recognition Log (CSV)", self._export_log,
                 COLORS["surface2"], COLORS["surface3"], pady=7, padx=12
                 ).pack(side=tk.LEFT, padx=(0, 8))

    def _export_log(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile="gait_recognition_log.csv",
            title="Export Recognition Log",
        )
        if path:
            try:
                self.db.export_log_csv(path)
                messagebox.showinfo("Export Complete", f"Log saved to:\n{path}")
            except Exception as exc:
                messagebox.showerror("Export Failed", str(exc))

    # ── Dependencies card ─────────────────────────────────────────────────────

    def _build_dependencies(self, parent):
        outer, inner = make_card(parent, "System Dependencies", COLORS["surface3"])
        outer.pack(fill=tk.X)

        self._dep_inner = inner
        make_btn(inner, "Check Dependencies", self._check_deps,
                 COLORS["surface2"], COLORS["surface3"], pady=7, padx=12
                 ).pack(anchor="w", pady=(0, 10))
        self._check_deps()

    def _check_deps(self):
        for w in self._dep_inner.winfo_children():
            if isinstance(w, tk.Frame):
                w.destroy()

        deps = check_dependencies()
        for pkg, ver in deps.items():
            ok    = ver is not None
            row   = tk.Frame(self._dep_inner, bg=COLORS["surface"])
            row.pack(fill=tk.X, pady=2)
            icon  = "✓" if ok else "✗"
            color = COLORS["success_light"] if ok else COLORS["error_light"]
            tk.Label(row, text=f"{icon}  {pkg}", font=FONTS["body"],
                     bg=COLORS["surface"], fg=color, width=18, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=ver or "NOT INSTALLED", font=FONTS["mono"],
                     bg=COLORS["surface"],
                     fg=COLORS["text_dim"] if ok else COLORS["error_light"],
                     anchor="w").pack(side=tk.LEFT)

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_thresh_change(self, val):
        self._thresh_lbl.config(text=f"{float(val)*100:.0f}%")

    def _apply_threshold(self):
        val = self._threshold_var.get()
        self.recognizer.set_threshold(val)
        messagebox.showinfo("Updated", f"Confidence threshold set to {val*100:.0f}%.")

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

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_show(self):
        self._refresh_model_info()
        self._threshold_var.set(self.recognizer.confidence_threshold)
        self._thresh_lbl.config(text=f"{self.recognizer.confidence_threshold*100:.0f}%")

    def on_hide(self):
        pass
