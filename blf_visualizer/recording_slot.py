"""
recording_slot.py — Self-contained state + widgets for one BLF recording.

RecordingSlot manages file loading, DBC import, message filtering,
the Treeview display, signal combo boxes, and CSV export for one slot (A or B).
"""

import os
import csv
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from blf_visualizer.blf_parser   import BLFParser
from blf_visualizer.dbc_parser   import DBCParser
from blf_visualizer.signal_cache import SignalCache
from blf_visualizer.theme import (
    DARK_BG, PANEL_BG, TEXT_FG, MUTED, ACCENT3, SEL_BG,
    ROW_ODD, ROW_EVEN, ERROR_CLR, FD_CLR,
    COLS, COL_LABELS, COL_WIDTH,
)


class RecordingSlot:
    """
    All state and widgets for one BLF recording.

    Parameters
    ----------
    label : str
        "A" or "B"
    accent : str
        Hex colour that visually distinguishes this slot.
    app : tk.Tk
        Reference to the main App window (for threading callbacks
        and the shared progress bar).
    """

    def __init__(self, label: str, accent: str, app):
        self.label  = label
        self.accent = accent
        self.app    = app

        # Data
        self.all_messages: list = []
        self.filtered:     list = []
        self.sort_col: str  = "idx"
        self.sort_rev: bool = False
        self.filepath: str  = ""
        self.dbc:      DBCParser | None = None
        self.cache     = SignalCache()
        self.plot_series: list = []   # full signal names selected for Y axis

        # Tkinter variables — assigned during widget construction
        self.filter_var:    tk.StringVar | None = None
        self.status_var:    tk.StringVar | None = None
        self.dbc_label_var: tk.StringVar | None = None

        # Reference-line controls (set in build_plot_controls)
        self.ref_enabled_var: tk.BooleanVar | None = None
        self.ref_value_var:   tk.StringVar  | None = None

        # Matplotlib artists — assigned by PlotTab after rendering
        self.ref_artist = None
        self.ref_ax     = None

        # Widgets
        self.tree:       ttk.Treeview | None = None
        self.x_var:      tk.StringVar | None = None
        self.x_combo:    ttk.Combobox | None = None
        self.y_pick_var: tk.StringVar | None = None
        self.y_pick:     ttk.Combobox | None = None
        self.y_listbox:  tk.Listbox   | None = None

    # ── Widget builders ───────────────────────────────────────────────────

    def build_messages_pane(self, parent: tk.Widget):
        """Build the header toolbar + sortable Treeview inside *parent*."""
        hdr = tk.Frame(parent, bg=PANEL_BG, pady=5, padx=8)
        hdr.pack(fill="x")

        tk.Label(hdr, text=f" {self.label} ", bg=self.accent,
                 fg="#fff", font=("Consolas", 10, "bold"),
                 padx=4).pack(side="left", padx=(0, 8))

        ttk.Button(hdr, text="📂 Open BLF",
                   command=self._open_dialog).pack(side="left", padx=(0, 4))
        ttk.Button(hdr, text="📐 Import DBC",
                   command=self._import_dbc).pack(side="left", padx=(0, 12))
        ttk.Button(hdr, text="💾 Export CSV",
                   command=self._export_csv).pack(side="left", padx=(0, 12))

        tk.Label(hdr, text="Filter:", bg=PANEL_BG, fg=TEXT_FG,
                 font=("Consolas", 9)).pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._apply_filter())
        tk.Entry(hdr, textvariable=self.filter_var, width=24,
                 bg=DARK_BG, fg=TEXT_FG, insertbackground=TEXT_FG,
                 relief="flat", bd=4,
                 font=("Consolas", 9)).pack(side="left", padx=6)

        self.dbc_label_var = tk.StringVar(value="No DBC")
        tk.Label(hdr, textvariable=self.dbc_label_var, bg=PANEL_BG,
                 fg=ACCENT3, font=("Consolas", 8)).pack(side="left", padx=(8, 0))

        self.status_var = tk.StringVar(value="No file loaded")
        tk.Label(hdr, textvariable=self.status_var, bg=PANEL_BG,
                 fg=MUTED, font=("Consolas", 8)).pack(side="right")

        tf = tk.Frame(parent, bg=DARK_BG)
        tf.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(tf, columns=COLS, show="headings",
                                  selectmode="browse")
        for col in COLS:
            self.tree.heading(col, text=COL_LABELS[col],
                              command=lambda c=col: self._sort(c))
            anc = "e" if col in ("idx", "dlc") else "w"
            self.tree.column(col, width=COL_WIDTH[col], anchor=anc,
                             minwidth=30, stretch=(col == "decoded"))

        vsb = ttk.Scrollbar(tf, orient="vertical",   command=self.tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.tag_configure("odd",   background=ROW_ODD)
        self.tree.tag_configure("even",  background=ROW_EVEN)
        self.tree.tag_configure("error", foreground=ERROR_CLR)
        self.tree.tag_configure("fd",    foreground=FD_CLR)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        tf.rowconfigure(0, weight=1)
        tf.columnconfigure(0, weight=1)

    def build_plot_controls(self, parent: tk.Widget):
        """Build X / Y signal-selection controls inside *parent*."""
        tk.Label(parent, text=f"  Recording {self.label}", bg=PANEL_BG,
                 fg=self.accent, font=("Consolas", 10, "bold")).pack(
                     fill="x", pady=(8, 4), padx=6)

        # X axis
        xf = tk.LabelFrame(parent, text=f" X Axis ({self.label}) ",
                           bg=PANEL_BG, fg=self.accent,
                           font=("Consolas", 8, "bold"), bd=1, relief="solid",
                           padx=5, pady=6)
        xf.pack(fill="x", padx=6, pady=(0, 3))
        self.x_var = tk.StringVar(value="Elapsed Time (s)")
        self.x_combo = ttk.Combobox(xf, textvariable=self.x_var,
                                    state="readonly", width=26)
        self.x_combo["values"] = ["Elapsed Time (s)"]
        self.x_combo.pack(fill="x")

        # Y series
        yf = tk.LabelFrame(parent, text=f" Y Series ({self.label}) ",
                           bg=PANEL_BG, fg=self.accent,
                           font=("Consolas", 8, "bold"), bd=1, relief="solid",
                           padx=5, pady=6)
        yf.pack(fill="both", expand=True, padx=6, pady=(0, 3))

        add_row = tk.Frame(yf, bg=PANEL_BG)
        add_row.pack(fill="x", pady=(0, 4))
        self.y_pick_var = tk.StringVar()
        self.y_pick = ttk.Combobox(add_row, textvariable=self.y_pick_var,
                                    state="readonly", width=22)
        self.y_pick["values"] = []
        self.y_pick.pack(side="left", fill="x", expand=True)
        ttk.Button(add_row, text="＋", width=3,
                   command=self._add_y_series).pack(side="left", padx=(3, 0))

        self.y_listbox = tk.Listbox(yf, bg=DARK_BG, fg=self.accent,
                                     selectbackground=SEL_BG,
                                     font=("Consolas", 8), height=5,
                                     relief="flat", bd=0, activestyle="none")
        self.y_listbox.pack(fill="both", expand=True)
        ttk.Button(yf, text="✕ Remove",
                   command=self._remove_y_series).pack(fill="x", pady=(4, 0))

        # Reference line
        rf = tk.LabelFrame(parent, text=f" Reference Line ({self.label}) ",
                           bg=PANEL_BG, fg=self.accent,
                           font=("Consolas", 8, "bold"), bd=1, relief="solid",
                           padx=5, pady=6)
        rf.pack(fill="x", padx=6, pady=(0, 3))

        self.ref_enabled_var = tk.BooleanVar(value=False)
        tk.Checkbutton(rf, text="Show", variable=self.ref_enabled_var,
                       bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                       activebackground=PANEL_BG, activeforeground=TEXT_FG,
                       font=("Consolas", 8),
                       command=self._toggle_ref).pack(anchor="w")

        ref_row = tk.Frame(rf, bg=PANEL_BG)
        ref_row.pack(fill="x", pady=(3, 0))
        tk.Label(ref_row, text="Y =", bg=PANEL_BG, fg=MUTED,
                 font=("Consolas", 8)).pack(side="left")
        self.ref_value_var = tk.StringVar(value="0")
        ref_entry = tk.Entry(ref_row, textvariable=self.ref_value_var,
                             bg=DARK_BG, fg=TEXT_FG, insertbackground=TEXT_FG,
                             relief="flat", bd=3, font=("Consolas", 9))
        ref_entry.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ref_entry.bind("<Return>",   lambda e: self._update_ref())
        ref_entry.bind("<KP_Enter>", lambda e: self._update_ref())

    # ── Reference line ────────────────────────────────────────────────────

    def _toggle_ref(self):
        if self.ref_ax is None:
            return
        if self.ref_enabled_var.get():
            self._update_ref()
        else:
            if self.ref_artist is not None:
                self.ref_artist.set_visible(False)
            self.app._redraw_canvas()

    def _update_ref(self):
        if self.ref_ax is None:
            return
        try:
            v = float(self.ref_value_var.get())
        except ValueError:
            return
        if self.ref_artist is not None:
            try:
                self.ref_artist.remove()
            except Exception:
                pass
        self.ref_artist = self.ref_ax.axhline(
            y=v, color="#ff0000", linewidth=1.4,
            linestyle="-", alpha=1.0, zorder=9)
        self.ref_artist.set_visible(self.ref_enabled_var.get())
        self.app._redraw_canvas()

    # ── File loading ──────────────────────────────────────────────────────

    def _open_dialog(self):
        path = filedialog.askopenfilename(
            title=f"Open BLF File — Recording {self.label}",
            filetypes=[("BLF files", "*.blf"), ("All files", "*.*")])
        if path:
            self.load_file(path)

    def load_file(self, path: str):
        """Start a background thread to load *path*."""
        self.filepath = path
        self.status_var.set(f"Loading {os.path.basename(path)} …")
        self.app.update_idletasks()
        self.app.show_progress(True)

        def _worker():
            try:
                parser = BLFParser(path)
                msgs   = parser.parse(progress_cb=self.app.set_progress)
                self.app.after(0, lambda: self._on_loaded(msgs, parser.stats, path))
            except Exception as exc:
                self.app.after(0, lambda: messagebox.showerror(
                    f"Parse Error — Recording {self.label}", str(exc)))
                self.app.after(0, lambda: self.app.show_progress(False))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_loaded(self, msgs: list, stats: dict, path: str):
        self.all_messages = msgs
        self.app.show_progress(False)
        self.filter_var.set("")
        self._apply_filter()
        dur = stats.get("duration", 0)
        self.status_var.set(
            f"✔  {os.path.basename(path)}  —  {len(msgs):,} msgs  |  {dur:.2f} s")
        if self.dbc:
            self._rebuild_cache()

    # ── DBC ───────────────────────────────────────────────────────────────

    def _import_dbc(self):
        path = filedialog.askopenfilename(
            title=f"Import DBC — Recording {self.label}",
            filetypes=[("DBC files", "*.dbc"), ("All files", "*.*")])
        if not path:
            return
        try:
            dbc    = DBCParser()
            dbc.parse_file(path)
            n_msgs = len(dbc.messages)
            n_sigs = sum(len(m.signals) for m in dbc.messages.values())
            if n_msgs == 0:
                messagebox.showwarning("DBC", "No message definitions found.")
                return
            self.dbc = dbc
            self.dbc_label_var.set(
                f"📐 {os.path.basename(path)} ({n_msgs}m/{n_sigs}s)")
            if self.all_messages:
                self._rebuild_cache()
            else:
                self.status_var.set("DBC loaded — open a BLF file to decode")
        except Exception as exc:
            messagebox.showerror("DBC Error", str(exc))

    def _rebuild_cache(self):
        self.status_var.set("Building signal cache…")
        self.app.show_progress(True)

        def _worker():
            self.cache.build(self.all_messages, self.dbc,
                             progress_cb=self.app.set_progress)
            self.app.after(0, self._on_cache_ready)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_cache_ready(self):
        self.app.show_progress(False)
        self._apply_filter()
        self._refresh_signal_combos()
        self.status_var.set(
            f"DBC ready — {len(self.cache.series)} signal series decoded")

    def _refresh_signal_combos(self):
        if self.x_combo is None:
            return
        sigs   = self.cache.available
        x_opts = ["Elapsed Time (s)"] + sigs
        self.x_combo["values"] = x_opts
        if self.x_var.get() not in x_opts:
            self.x_var.set("Elapsed Time (s)")
        self.y_pick["values"] = sigs

    def _add_y_series(self):
        sig = self.y_pick_var.get()
        if sig and sig not in self.plot_series:
            self.plot_series.append(sig)
            self.y_listbox.insert("end", sig)

    def _remove_y_series(self):
        sel = self.y_listbox.curselection()
        if sel:
            self.plot_series.pop(sel[0])
            self.y_listbox.delete(sel[0])

    # ── Filter + Treeview ─────────────────────────────────────────────────

    def _apply_filter(self):
        q = self.filter_var.get().strip().lower()
        result = []
        for m in self.all_messages:
            if q:
                hay = (f"{m.arb_id:08X} {m.data_str} "
                       f"{m.timestamp_str} {m.channel}").lower()
                if q not in hay:
                    continue
            result.append(m)
        self.filtered = result
        self._populate_tree(result)

    def _populate_tree(self, msgs: list):
        self.tree.delete(*self.tree.get_children())
        for i, m in enumerate(msgs):
            tags = ["odd" if i % 2 else "even"]
            if m.is_error: tags.append("error")
            if m.is_fd:    tags.append("fd")

            id_str = (f"{m.arb_id:08X}" if m.is_extended
                      else f"{m.arb_id:04X}")

            decoded_str = ""
            if self.dbc and not m.is_error:
                dbc_msg = self.dbc.messages.get(m.arb_id)
                if dbc_msg:
                    parts = []
                    for sname, sig in dbc_msg.signals.items():
                        try:
                            raw  = sig._extract_bits(m.data)
                            phys = sig.decode(m.data)
                            unit = f" {sig.unit}" if sig.unit else ""
                            if sig.values:
                                lbl = sig.values.get(int(raw), "")
                                parts.append(
                                    f"{sname}={lbl or f'{phys:.4g}'}{unit}")
                            else:
                                parts.append(f"{sname}={phys:.4g}{unit}")
                        except Exception:
                            pass
                    decoded_str = "  |  ".join(parts)

            self.tree.insert("", "end", iid=str(i), tags=tags, values=(
                i + 1, m.timestamp_str, m.channel, id_str,
                m.dlc, m.data_str, decoded_str))

    def _sort(self, col: str):
        self.sort_rev = (not self.sort_rev if self.sort_col == col else False)
        self.sort_col = col
        key_fn = {
            "idx":       lambda m: 0,
            "timestamp": lambda m: m.timestamp,
            "channel":   lambda m: m.channel,
            "id":        lambda m: m.arb_id,
            "dlc":       lambda m: m.dlc,
            "data":      lambda m: m.data_str,
            "decoded":   lambda m: m.arb_id,
        }.get(col, lambda m: 0)
        self.filtered.sort(key=key_fn, reverse=self.sort_rev)
        self._populate_tree(self.filtered)
        arrow = " ▼" if self.sort_rev else " ▲"
        for c in COLS:
            self.tree.heading(
                c, text=COL_LABELS[c] + (arrow if c == col else ""))

    # ── CSV export ────────────────────────────────────────────────────────

    def _export_csv(self):
        if not self.filtered:
            messagebox.showinfo("Export", "No messages to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            title=f"Export Recording {self.label} as CSV")
        if not path:
            return

        sig_names: list = []
        if self.dbc:
            seen: set = set()
            for m in self.filtered:
                dbc_msg = self.dbc.messages.get(m.arb_id)
                if dbc_msg:
                    for sn in dbc_msg.signals:
                        if sn not in seen:
                            seen.add(sn)
                            sig_names.append(sn)

        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            header = ["#", "Timestamp(s)", "Channel", "ArbID_hex",
                      "ArbID_dec", "IsExtended", "IsFD", "IsError",
                      "DLC", "Data_hex"]
            if self.dbc:
                header.append("MsgName")
            header.extend(sig_names)
            w.writerow(header)

            for i, m in enumerate(self.filtered, 1):
                row = [i, m.timestamp_str, m.channel,
                       f"{m.arb_id:X}", m.arb_id,
                       int(m.is_extended), int(m.is_fd), int(m.is_error),
                       m.dlc, m.data_str]
                if self.dbc:
                    dbc_msg = self.dbc.messages.get(m.arb_id)
                    row.append(dbc_msg.name if dbc_msg else "")
                    dec = (self.dbc.decode_message(m.arb_id, m.data)
                           if not m.is_error else {})
                    row.extend(dec.get(sn, "") for sn in sig_names)
                w.writerow(row)

        messagebox.showinfo("Export",
            f"Exported {len(self.filtered):,} rows to:\n{path}")
