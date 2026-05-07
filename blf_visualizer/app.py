"""
app.py — Main application window.

App composes the three tabs by inheriting from two mixins:
  PlotTabMixin  — Signal Comparison tab
  GpsTabMixin   — GPS Track Map tab
"""

import os
import sys
import tkinter as tk
from tkinter import ttk

from blf_visualizer.theme          import (DARK_BG, PANEL_BG, MUTED,
                                            ACCENT, ACCENT2, apply_style)
from blf_visualizer.recording_slot import RecordingSlot
from blf_visualizer.plot_tab       import PlotTabMixin
from blf_visualizer.gps_tab        import GpsTabMixin


class App(PlotTabMixin, GpsTabMixin, tk.Tk):
    """
    Top-level window.  Run with:

        App().mainloop()
    """

    def __init__(self):
        super().__init__()
        self.title("BLF Visualizer v5.5 — Gusztav Gombas")
        self.geometry("1440x900")
        self.configure(bg=DARK_BG)
        self.option_add("*Font", "Consolas 10")

        # Two recording slots
        self.slot_a = RecordingSlot("A", ACCENT,  self)
        self.slot_b = RecordingSlot("B", ACCENT2, self)

        # Plot state — consumed by PlotTabMixin
        self._fig:             object = None
        self._ax_a:            object = None
        self._ax_b:            object = None
        self._plot_canvas_ref: object = None
        self._vlines:          list   = []
        self._tooltip_annots:  dict   = {}
        self._ax_tag_map:      dict   = {}

        self._build_ui()
        apply_style(self)

        # Optional command-line arguments: file_a.blf  [file_b.blf]
        args = sys.argv[1:]
        if len(args) >= 1 and os.path.isfile(args[0]):
            self.after(200, lambda: self.slot_a.load_file(args[0]))
        if len(args) >= 2 and os.path.isfile(args[1]):
            self.after(400, lambda: self.slot_b.load_file(args[1]))

    # ── Progress bar ──────────────────────────────────────────────────────

    def show_progress(self, visible: bool):
        if visible:
            self._progress.pack(fill="x", padx=8, pady=2)
        else:
            self._progress.pack_forget()

    def set_progress(self, frac: float):
        self._progress["value"] = frac * 100
        self.update_idletasks()

    def _redraw_canvas(self):
        """Lightweight canvas redraw for ref-line / cursor live updates."""
        if self._plot_canvas_ref is not None:
            try:
                self._plot_canvas_ref.draw_idle()
            except Exception:
                pass

    # ── Layout ────────────────────────────────────────────────────────────

    def _build_ui(self):
        mb = tk.Menu(self, bg=PANEL_BG, fg="#cdd6f4",
                     activebackground=ACCENT, activeforeground="#fff",
                     tearoff=False)
        fm = tk.Menu(mb, bg=PANEL_BG, fg="#cdd6f4",
                     activebackground=ACCENT, activeforeground="#fff",
                     tearoff=False)
        fm.add_command(label="Open BLF — Recording A…",
                       command=self.slot_a._open_dialog,
                       accelerator="Ctrl+Shift+A")
        fm.add_command(label="Open BLF — Recording B…",
                       command=self.slot_b._open_dialog,
                       accelerator="Ctrl+Shift+B")
        fm.add_separator()
        fm.add_command(label="Import DBC — Recording A…",
                       command=self.slot_a._import_dbc)
        fm.add_command(label="Import DBC — Recording B…",
                       command=self.slot_b._import_dbc)
        fm.add_separator()
        fm.add_command(label="Export CSV — Recording A…",
                       command=self.slot_a._export_csv)
        fm.add_command(label="Export CSV — Recording B…",
                       command=self.slot_b._export_csv)
        fm.add_separator()
        fm.add_command(label="Quit", command=self.quit,
                       accelerator="Ctrl+Q")
        mb.add_cascade(label="File", menu=fm)
        self.config(menu=mb)
        self.bind("<Control-q>", lambda e: self.quit())

        self._progress = ttk.Progressbar(self, mode="determinate",
                                          maximum=100)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        self._build_messages_tab()
        self._build_plot_tab()    # PlotTabMixin
        self._build_gps_tab()     # GpsTabMixin

    # ── Tab 1: Messages ───────────────────────────────────────────────────

    def _build_messages_tab(self):
        outer = ttk.Frame(self._nb)
        self._nb.add(outer, text="📋  Messages")

        paned = ttk.PanedWindow(outer, orient="vertical")
        paned.pack(fill="both", expand=True)

        frame_a = tk.Frame(paned, bg=DARK_BG,
                           highlightbackground=ACCENT, highlightthickness=1)
        self.slot_a.build_messages_pane(frame_a)
        paned.add(frame_a, weight=1)

        paned.add(tk.Frame(paned, bg=MUTED, height=2), weight=0)

        frame_b = tk.Frame(paned, bg=DARK_BG,
                           highlightbackground=ACCENT2, highlightthickness=1)
        self.slot_b.build_messages_pane(frame_b)
        paned.add(frame_b, weight=1)
