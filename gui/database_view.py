"""Database management view — browse, delete, and manage enrolled users."""
import tkinter as tk
from tkinter import messagebox, ttk

from gui.theme import COLORS, FONTS


class DatabaseView(tk.Frame):
    def __init__(self, parent, db, recognizer, on_model_updated=None, **kwargs):
        super().__init__(parent, bg=COLORS["bg"], **kwargs)
        self.db = db
        self.recognizer = recognizer
        self.on_model_updated = on_model_updated
        self._selected_user_id = None
        self._build()

    def _build(self):
        tk.Label(
            self, text="User Database",
            font=FONTS["title"], bg=COLORS["bg"], fg=COLORS["text"]
        ).pack(anchor="w", padx=30, pady=(25, 4))

        tk.Label(
            self, text="Manage enrolled users and their gait samples.",
            font=FONTS["body"], bg=COLORS["bg"], fg=COLORS["text_dim"]
        ).pack(anchor="w", padx=30, pady=(0, 16))

        # Toolbar
        toolbar = tk.Frame(self, bg=COLORS["bg"])
        toolbar.pack(fill=tk.X, padx=30, pady=(0, 10))

        self._btn_refresh = self._btn(toolbar, "🔄  Refresh", self.refresh, COLORS["surface2"])
        self._btn_refresh.pack(side=tk.LEFT, padx=(0, 8))

        self._btn_delete_samples = self._btn(
            toolbar, "🗑  Clear Samples (keep user)", self._delete_samples, COLORS["warning"]
        )
        self._btn_delete_samples.pack(side=tk.LEFT, padx=(0, 8))
        self._btn_delete_samples.config(state=tk.DISABLED)

        self._btn_delete_user = self._btn(
            toolbar, "✖  Delete User", self._delete_user, COLORS["error"]
        )
        self._btn_delete_user.pack(side=tk.LEFT, padx=(0, 8))
        self._btn_delete_user.config(state=tk.DISABLED)

        self._btn_retrain = self._btn(
            toolbar, "🧠  Retrain Model", self._retrain, COLORS["accent"]
        )
        self._btn_retrain.pack(side=tk.RIGHT)

        # Table
        table_frame = tk.Frame(self, bg=COLORS["surface"])
        table_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Gait.Treeview",
            background=COLORS["surface"],
            foreground=COLORS["text"],
            rowheight=30,
            fieldbackground=COLORS["surface"],
            borderwidth=0,
            font=FONTS["body"],
        )
        style.configure("Gait.Treeview.Heading",
            background=COLORS["surface2"],
            foreground=COLORS["text_dim"],
            font=FONTS["body_bold"],
            relief="flat",
            borderwidth=0,
        )
        style.map("Gait.Treeview",
            background=[("selected", COLORS["accent_dark"])],
            foreground=[("selected", COLORS["text"])],
        )

        cols = ("name", "samples", "created")
        self._tree = ttk.Treeview(
            table_frame, columns=cols, show="headings",
            style="Gait.Treeview", selectmode="browse"
        )
        self._tree.heading("name",    text="Name",         anchor="w")
        self._tree.heading("samples", text="Samples",      anchor="center")
        self._tree.heading("created", text="Date Enrolled",anchor="w")
        self._tree.column("name",    width=250, anchor="w")
        self._tree.column("samples", width=100, anchor="center")
        self._tree.column("created", width=180, anchor="w")

        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.tag_configure("good",  foreground=COLORS["success_light"])
        self._tree.tag_configure("warn",  foreground=COLORS["warning_light"])
        self._tree.tag_configure("error", foreground=COLORS["error_light"])

        # Status label
        self._status = tk.Label(
            self, text="", font=FONTS["small"],
            bg=COLORS["bg"], fg=COLORS["text_dim"]
        )
        self._status.pack(anchor="w", padx=30, pady=(0, 8))

        self.refresh()

    def _btn(self, parent, text, cmd, bg):
        return tk.Button(
            parent, text=text, command=cmd,
            font=FONTS["body_bold"], bg=bg, fg=COLORS["text"],
            relief=tk.FLAT, cursor="hand2", bd=0,
            activebackground=COLORS["surface3"], activeforeground=COLORS["text"],
            padx=12, pady=6
        )

    def refresh(self):
        for row in self._tree.get_children():
            self._tree.delete(row)
        self._selected_user_id = None
        self._btn_delete_user.config(state=tk.DISABLED)
        self._btn_delete_samples.config(state=tk.DISABLED)

        users = self.db.get_all_users()
        for uid, name, count, created in users:
            tag = "good" if count >= 3 else ("warn" if count >= 1 else "error")
            self._tree.insert(
                "", "end",
                iid=str(uid),
                values=(name, count, created or "—"),
                tags=(tag,)
            )

        stats = self.db.get_stats()
        model_info = (
            f"  |  Model: trained ({self.recognizer.n_classes} users)"
            if self.recognizer.is_trained else "  |  Model: not trained"
        )
        self._status.config(
            text=f"Total users: {stats['users']}  |  Total samples: {stats['samples']}{model_info}"
        )

    def _on_select(self, event):
        sel = self._tree.selection()
        if sel:
            self._selected_user_id = int(sel[0])
            self._btn_delete_user.config(state=tk.NORMAL)
            self._btn_delete_samples.config(state=tk.NORMAL)
        else:
            self._selected_user_id = None
            self._btn_delete_user.config(state=tk.DISABLED)
            self._btn_delete_samples.config(state=tk.DISABLED)

    def _delete_user(self):
        if self._selected_user_id is None:
            return
        row = self._tree.item(str(self._selected_user_id))
        name = row["values"][0]
        if messagebox.askyesno(
            "Confirm Delete",
            f"Delete user '{name}' and ALL their gait samples?\nThis cannot be undone.",
            icon="warning"
        ):
            self.db.delete_user(self._selected_user_id)
            self._selected_user_id = None
            self.refresh()
            if self.on_model_updated:
                self.on_model_updated()

    def _delete_samples(self):
        if self._selected_user_id is None:
            return
        row = self._tree.item(str(self._selected_user_id))
        name = row["values"][0]
        if messagebox.askyesno(
            "Confirm Clear",
            f"Delete all gait samples for '{name}'?\nThe user account will remain.",
            icon="warning"
        ):
            self.db.delete_user_samples(self._selected_user_id)
            self.refresh()

    def _retrain(self):
        all_features, labels, label_names = self.db.get_all_samples()
        if not all_features:
            messagebox.showinfo("No Data", "No samples to train on.")
            return
        ok, msg = self.recognizer.train(all_features, labels, label_names)
        icon = "info" if ok else "warning"
        messagebox.showinfo("Training Result", msg)
        self.refresh()
        if ok and self.on_model_updated:
            self.on_model_updated()

    def on_show(self):
        self.refresh()

    def on_hide(self):
        pass
