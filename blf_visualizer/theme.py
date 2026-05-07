"""
theme.py — colour palette, table column definitions, and ttk style helper.
Change colours and fonts here; nothing else needs to be touched.
"""

import tkinter as tk
from tkinter import ttk

# ── Colour palette ─────────────────────────────────────────────────────────
DARK_BG   = "#1e1e2e"
PANEL_BG  = "#2a2a3e"
ACCENT    = "#7c6af7"   # Recording A — violet
ACCENT2   = "#48cfad"   # Recording B — teal
ACCENT3   = "#f9c74f"   # amber (time labels, car marker)
TEXT_FG   = "#cdd6f4"
MUTED     = "#6c7086"
ROW_ODD   = "#242436"
ROW_EVEN  = "#1e1e2e"
SEL_BG    = "#45475a"
ERROR_CLR = "#f38ba8"
FD_CLR    = "#a6e3a1"

# ── Per-recording plot palettes ────────────────────────────────────────────
PLOT_COLORS_A = ["#7c6af7", "#cba6f7", "#b4a0f5", "#9370f0",
                 "#a47de8", "#8b5cf6", "#d8b4fe", "#c084fc"]
PLOT_COLORS_B = ["#48cfad", "#a6e3a1", "#94e2d5", "#2dd4bf",
                 "#6ee7b7", "#34d399", "#86efac", "#4ade80"]

CURSOR_COLOR = "#f38ba8"   # red dashed cursor on signal plot

# ── Message table columns ──────────────────────────────────────────────────
COLS = ("idx", "timestamp", "channel", "id", "dlc", "data", "decoded")

COL_LABELS = {
    "idx":       "#",
    "timestamp": "Timestamp (s)",
    "channel":   "Ch",
    "id":        "Arb ID",
    "dlc":       "DLC",
    "data":      "Data (hex)",
    "decoded":   "Decoded Signals",
}

COL_WIDTH = {
    "idx":       50,
    "timestamp": 115,
    "channel":   40,
    "id":        95,
    "dlc":       35,
    "data":      210,
    "decoded":   340,
}


# ── ttk style ──────────────────────────────────────────────────────────────
def apply_style(root: tk.Tk):
    """Apply the dark Catppuccin-inspired ttk theme to *root*."""
    s = ttk.Style(root)
    s.theme_use("clam")
    s.configure(".", background=DARK_BG, foreground=TEXT_FG,
                fieldbackground=PANEL_BG, bordercolor=MUTED,
                troughcolor=PANEL_BG, selectbackground=ACCENT,
                selectforeground=TEXT_FG, font=("Consolas", 10))
    s.configure("Treeview", background=ROW_EVEN, foreground=TEXT_FG,
                fieldbackground=ROW_EVEN, rowheight=22, borderwidth=0)
    s.configure("Treeview.Heading", background=PANEL_BG, foreground=ACCENT,
                relief="flat", font=("Consolas", 10, "bold"))
    s.map("Treeview",
          background=[("selected", SEL_BG)],
          foreground=[("selected", TEXT_FG)])
    s.configure("TNotebook", background=DARK_BG, tabmargins=0)
    s.configure("TNotebook.Tab", background=PANEL_BG, foreground=MUTED,
                padding=[12, 6])
    s.map("TNotebook.Tab",
          background=[("selected", DARK_BG)],
          foreground=[("selected", ACCENT)])
    s.configure("TButton", background=ACCENT, foreground="#fff",
                relief="flat", padding=[8, 4], font=("Consolas", 9, "bold"))
    s.map("TButton", background=[("active", "#9d8fff")])
    s.configure("TLabel",       background=DARK_BG, foreground=TEXT_FG)
    s.configure("TEntry",       fieldbackground=PANEL_BG, foreground=TEXT_FG,
                insertcolor=TEXT_FG, borderwidth=0, relief="flat")
    s.configure("TFrame",       background=DARK_BG)
    s.configure("Panel.TFrame", background=PANEL_BG)
    s.configure("TScrollbar",   background=PANEL_BG, troughcolor=DARK_BG,
                borderwidth=0, arrowsize=12)
    s.configure("TPanedwindow", background=MUTED)
