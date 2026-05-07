"""
plot_tab.py — Signal Comparison tab mixed into App.

PlotTabMixin provides _build_plot_tab() and all signal-plot event handlers.
It is mixed into App so all methods share self with the rest of the window.
"""

import bisect
import tkinter as tk
from tkinter import ttk, messagebox

from blf_visualizer.theme import (
    DARK_BG, PANEL_BG, TEXT_FG, MUTED,
    ACCENT, ACCENT2, ACCENT3,
    PLOT_COLORS_A, PLOT_COLORS_B, CURSOR_COLOR,
)


class PlotTabMixin:
    """
    Signal Comparison tab.  Requires the host class to expose:
      self.slot_a / self.slot_b   — RecordingSlot
      self._nb                    — ttk.Notebook
      self._redraw_canvas()       — lightweight canvas refresh
    """

    # ── Tab construction ──────────────────────────────────────────────────

    def _build_plot_tab(self):
        outer = ttk.Frame(self._nb)
        self._nb.add(outer, text="📈  Signal Comparison")

        # Left control panel
        left = tk.Frame(outer, bg=PANEL_BG, width=310)
        left.pack(side="left", fill="y", padx=(6, 0), pady=6)
        left.pack_propagate(False)

        tk.Label(left, text="  Signal Comparison", bg=PANEL_BG, fg=ACCENT,
                 font=("Consolas", 11, "bold")).pack(fill="x", pady=(10, 4))

        # Scrollable control inner frame
        ctrl_canvas = tk.Canvas(left, bg=PANEL_BG, highlightthickness=0)
        ctrl_scroll = ttk.Scrollbar(left, orient="vertical",
                                    command=ctrl_canvas.yview)
        ctrl_canvas.configure(yscrollcommand=ctrl_scroll.set)
        ctrl_scroll.pack(side="right", fill="y")
        ctrl_canvas.pack(side="left", fill="both", expand=True)

        ctrl_inner = tk.Frame(ctrl_canvas, bg=PANEL_BG)
        ctrl_win   = ctrl_canvas.create_window((0, 0), window=ctrl_inner,
                                               anchor="nw")

        def _on_resize(event=None):
            ctrl_canvas.configure(scrollregion=ctrl_canvas.bbox("all"))
            ctrl_canvas.itemconfig(ctrl_win, width=ctrl_canvas.winfo_width())

        ctrl_inner.bind("<Configure>", _on_resize)
        ctrl_canvas.bind("<Configure>", lambda e: ctrl_canvas.itemconfig(
            ctrl_win, width=e.width))

        self.slot_a.build_plot_controls(ctrl_inner)
        tk.Frame(ctrl_inner, bg=MUTED, height=1).pack(fill="x", padx=8, pady=6)
        self.slot_b.build_plot_controls(ctrl_inner)
        tk.Frame(ctrl_inner, bg=MUTED, height=1).pack(fill="x", padx=8, pady=6)

        # Chart options
        optf = tk.LabelFrame(ctrl_inner, text=" Chart Options ",
                             bg=PANEL_BG, fg=ACCENT2,
                             font=("Consolas", 8, "bold"),
                             bd=1, relief="solid", padx=8, pady=8)
        optf.pack(fill="x", padx=6, pady=(0, 4))

        tk.Label(optf, text="Mode:", bg=PANEL_BG, fg=TEXT_FG,
                 width=8, anchor="w", font=("Consolas", 9)).grid(
                     row=0, column=0, sticky="w")
        self._plot_mode_var = tk.StringVar(value="Stacked")
        ttk.Combobox(optf, textvariable=self._plot_mode_var,
                     values=["Stacked", "Overlay"],
                     state="readonly", width=10).grid(row=0, column=1, sticky="w")

        tk.Label(optf, text="Style:", bg=PANEL_BG, fg=TEXT_FG,
                 width=8, anchor="w", font=("Consolas", 9)).grid(
                     row=1, column=0, sticky="w", pady=(4, 0))
        self._plot_style_var = tk.StringVar(value="Line")
        ttk.Combobox(optf, textvariable=self._plot_style_var,
                     values=["Line", "Step", "Scatter"],
                     state="readonly", width=10).grid(
                         row=1, column=1, sticky="w", pady=(4, 0))

        self._plot_grid_var = tk.BooleanVar(value=True)
        tk.Checkbutton(optf, text="Grid", variable=self._plot_grid_var,
                       bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                       activebackground=PANEL_BG, activeforeground=TEXT_FG,
                       font=("Consolas", 9)).grid(
                           row=2, column=0, columnspan=2, sticky="w",
                           pady=(4, 0))

        self._plot_legend_var = tk.BooleanVar(value=True)
        tk.Checkbutton(optf, text="Legend", variable=self._plot_legend_var,
                       bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                       activebackground=PANEL_BG, activeforeground=TEXT_FG,
                       font=("Consolas", 9)).grid(
                           row=3, column=0, columnspan=2, sticky="w")

        ttk.Button(ctrl_inner, text="▶  Plot",
                   command=self._do_plot).pack(
                       fill="x", padx=6, pady=(6, 8), ipady=6)

        # Right: matplotlib canvas + scrubber
        right = tk.Frame(outer, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)

        self._canvas_holder = tk.Frame(right, bg=DARK_BG)
        self._canvas_holder.pack(fill="both", expand=True, padx=6, pady=6)

        # Time scrubber
        self._scrub_holder = tk.Frame(right, bg=PANEL_BG, pady=4, padx=8)

        tk.Label(self._scrub_holder, text="⏱ Time Cursor:",
                 bg=PANEL_BG, fg=ACCENT2,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=(0, 6))
        self._scrub_var = tk.DoubleVar(value=0.0)
        self._scrub_slider = tk.Scale(
            self._scrub_holder, variable=self._scrub_var,
            from_=0.0, to=1.0, orient="horizontal", resolution=0.001,
            bg=PANEL_BG, fg=TEXT_FG, troughcolor=DARK_BG,
            highlightthickness=0, sliderrelief="flat", bd=0,
            showvalue=False, command=self._on_scrub)
        self._scrub_slider.pack(side="left", fill="x", expand=True,
                                padx=(0, 8))
        self._scrub_time_lbl = tk.Label(
            self._scrub_holder, text="0.000 s",
            bg=PANEL_BG, fg=ACCENT3, font=("Consolas", 9), width=12)
        self._scrub_time_lbl.pack(side="left")

        tk.Frame(self._scrub_holder, bg=MUTED, width=1,
                 height=22).pack(side="left", padx=(12, 12))

        tk.Label(self._scrub_holder, text="Jump to (s):",
                 bg=PANEL_BG, fg=ACCENT2,
                 font=("Consolas", 9, "bold")).pack(side="left", padx=(0, 4))
        self._jump_tc_var = tk.StringVar()
        jump_entry = tk.Entry(
            self._scrub_holder, textvariable=self._jump_tc_var,
            width=10, bg=DARK_BG, fg=TEXT_FG,
            insertbackground=TEXT_FG, relief="flat", bd=4,
            font=("Consolas", 9))
        jump_entry.pack(side="left", padx=(0, 4))
        jump_entry.bind("<Return>",   lambda e: self._jump_to_tc())
        jump_entry.bind("<KP_Enter>", lambda e: self._jump_to_tc())
        ttk.Button(self._scrub_holder, text="⏭ Go",
                   command=self._jump_to_tc).pack(side="left")

    # ── Rendering ─────────────────────────────────────────────────────────

    def _do_plot(self):
        try:
            import matplotlib
            matplotlib.use("TkAgg")
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_tkagg import (
                FigureCanvasTkAgg, NavigationToolbar2Tk)
            from matplotlib.ticker import FuncFormatter
        except ImportError:
            messagebox.showwarning("matplotlib missing",
                "Install matplotlib:\n\n    pip install matplotlib")
            return

        mode    = self._plot_mode_var.get()
        style   = self._plot_style_var.get()
        do_grid = self._plot_grid_var.get()
        do_leg  = self._plot_legend_var.get()
        has_a   = bool(self.slot_a.plot_series)
        has_b   = bool(self.slot_b.plot_series)

        if not has_a and not has_b:
            messagebox.showinfo("No signals",
                "Add at least one signal to Recording A or B first.")
            return

        if has_a and not self._validate_slot(self.slot_a): return
        if has_b and not self._validate_slot(self.slot_b): return

        # Clear previous state
        for w in self._canvas_holder.winfo_children():
            w.destroy()
        self._vlines = []
        self._tooltip_annots.clear()
        self._ax_tag_map.clear()
        self._fig = self._ax_a = self._ax_b = None
        for slot in (self.slot_a, self.slot_b):
            slot.ref_artist = slot.ref_ax = None

        fig = Figure(figsize=(10, 6), dpi=96, facecolor=DARK_BG)
        fmt = FuncFormatter(lambda v, _: f"{v:.3f}")

        if mode == "Stacked" and has_a and has_b:
            ax_a = fig.add_subplot(211)
            ax_b = fig.add_subplot(212, sharex=ax_a)
            axes_map = [(self.slot_a, ax_a, PLOT_COLORS_A, "A"),
                        (self.slot_b, ax_b, PLOT_COLORS_B, "B")]
            self._ax_a, self._ax_b = ax_a, ax_b
        else:
            ax = fig.add_subplot(111)
            axes_map = []
            if has_a: axes_map.append((self.slot_a, ax, PLOT_COLORS_A, "A"))
            if has_b: axes_map.append((self.slot_b, ax, PLOT_COLORS_B, "B"))
            self._ax_a, self._ax_b = ax, None

        all_ts = []

        for slot, ax, colors, tag in axes_map:
            self._ax_tag_map[ax] = tag
            ax.set_facecolor(PANEL_BG)
            ax.tick_params(colors=MUTED)
            for sp in ax.spines.values():
                sp.set_edgecolor(MUTED)
            if do_grid:
                ax.grid(True, color=MUTED, alpha=0.22, linestyle="--")
            ax.xaxis.set_major_formatter(fmt)
            ax.yaxis.set_major_formatter(fmt)

            if mode == "Stacked" and has_a and has_b:
                ax.set_title(f"Recording {tag}", color=colors[0],
                             fontsize=9, loc="left", pad=4,
                             fontfamily="monospace")

            x_choice  = slot.x_var.get()
            x_is_time = x_choice == "Elapsed Time (s)"
            if not x_is_time:
                x_ts_data, x_val_data = slot.cache.series[x_choice]
                x_label = slot.cache.labels.get(x_choice, x_choice)
            else:
                x_ts_data = x_val_data = None
                x_label = "Elapsed Time (s)"

            for idx, full_name in enumerate(slot.plot_series):
                color        = colors[idx % len(colors)]
                y_ts, y_vals = slot.cache.series[full_name]
                lbl          = slot.cache.labels.get(full_name, full_name)
                legend_lbl   = f"[{tag}] {lbl}"
                xs = y_ts if x_is_time else self._interp(
                    y_ts, x_ts_data, x_val_data)
                if x_is_time and y_ts:
                    all_ts.extend([y_ts[0], y_ts[-1]])

                kw = dict(color=color, linewidth=1.4, label=legend_lbl)
                if style == "Line":       ax.plot(xs, y_vals, **kw)
                elif style == "Step":     ax.step(xs, y_vals, where="post", **kw)
                elif style == "Scatter":  ax.scatter(xs, y_vals, color=color,
                                                     s=8, label=legend_lbl)

            ax.set_xlabel(x_label, color=MUTED, fontsize=8)
            ax.set_ylabel(
                slot.cache.labels.get(slot.plot_series[0], slot.plot_series[0])
                if len(slot.plot_series) == 1 else "Value",
                color=TEXT_FG, fontsize=8)
            if do_leg:
                ax.legend(facecolor=PANEL_BG, edgecolor=MUTED,
                          labelcolor=TEXT_FG, fontsize=7)

            # Reference line (hidden until toggled)
            try:   ref_y = float(slot.ref_value_var.get())
            except (ValueError, TypeError): ref_y = 0.0
            ref_art = ax.axhline(y=ref_y, color="#ff0000", linewidth=1.4,
                                 linestyle="-", alpha=1.0, zorder=9)
            ref_art.set_visible(False)
            slot.ref_artist, slot.ref_ax = ref_art, ax

            # Hover annotation (one per axis)
            if ax not in self._tooltip_annots:
                annot = ax.annotate(
                    "", xy=(0, 0), xytext=(14, 14),
                    textcoords="offset points",
                    bbox=dict(boxstyle="round,pad=0.45", facecolor="#1e1e2e",
                              edgecolor=MUTED, alpha=0.92, linewidth=0.8),
                    fontsize=8, color=TEXT_FG,
                    fontfamily="monospace", zorder=20)
                annot.set_visible(False)
                self._tooltip_annots[ax] = annot

        fig.tight_layout(pad=1.6, h_pad=2.0)

        canvas = FigureCanvasTkAgg(fig, master=self._canvas_holder)
        canvas.draw()
        self._fig, self._plot_canvas_ref = fig, canvas
        canvas.mpl_connect("motion_notify_event", self._on_mouse_move)
        canvas.mpl_connect("axes_leave_event",    self._on_axes_leave)

        tb_frame = tk.Frame(self._canvas_holder, bg=PANEL_BG)
        tb_frame.pack(side="bottom", fill="x")
        toolbar = NavigationToolbar2Tk(canvas, tb_frame)
        toolbar.config(bg=PANEL_BG)
        for child in toolbar.winfo_children():
            try: child.config(bg=PANEL_BG, fg=TEXT_FG)
            except Exception: pass
        toolbar.update()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        if all_ts:
            t_min, t_max = min(all_ts), max(all_ts)
            self._scrub_slider.config(
                from_=t_min, to=t_max,
                resolution=max(0.001, (t_max - t_min) / 10_000))
            self._scrub_var.set(t_min)
            self._scrub_time_lbl.config(text=f"{t_min:.3f} s")
            self._scrub_holder.pack(side="bottom", fill="x")
        else:
            self._scrub_holder.pack_forget()

    # ── Helpers ───────────────────────────────────────────────────────────

    def _validate_slot(self, slot) -> bool:
        missing = [s for s in slot.plot_series if s not in slot.cache.series]
        if missing:
            messagebox.showerror(
                f"Recording {slot.label} — Missing Signals",
                "No data for:\n" + "\n".join(f"  • {s}" for s in missing) +
                "\n\nLoad a matching DBC + BLF file first.")
            return False
        x = slot.x_var.get()
        if x != "Elapsed Time (s)" and x not in slot.cache.series:
            messagebox.showerror(
                f"Recording {slot.label} — X Axis",
                f"Signal '{x}' has no data in cache.")
            return False
        return True

    @staticmethod
    def _interp(y_ts, x_ts, x_vals) -> list:
        """Linearly interpolate *x_vals* at each timestamp in *y_ts*."""
        out = []
        for t in y_ts:
            i = bisect.bisect_left(x_ts, t)
            if i == 0:               out.append(x_vals[0])
            elif i >= len(x_ts):     out.append(x_vals[-1])
            else:
                t0, t1 = x_ts[i-1], x_ts[i]
                v0, v1 = x_vals[i-1], x_vals[i]
                frac = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
                out.append(v0 + frac * (v1 - v0))
        return out

    # ── Mouse / tooltip events ────────────────────────────────────────────

    def _on_mouse_move(self, event):
        if event.inaxes is None or event.inaxes not in self._tooltip_annots:
            return
        ax = event.inaxes
        annot = self._tooltip_annots[ax]
        x, y  = event.xdata, event.ydata
        if x is None or y is None:
            annot.set_visible(False)
            self._redraw_canvas()
            return

        tag = self._ax_tag_map.get(ax, "")
        annot.set_text(f"{'['+tag+']  ' if tag else ''}x = {x:.4f}\n"
                       f"{'     '}y = {y:.4f}")
        annot.xy = (x, y)

        ax_x0, ax_x1 = ax.get_xlim()
        ax_y0, ax_y1 = ax.get_ylim()
        x_frac = (x - ax_x0) / (ax_x1 - ax_x0) if ax_x1 != ax_x0 else 0.5
        y_frac = (y - ax_y0) / (ax_y1 - ax_y0) if ax_y1 != ax_y0 else 0.5
        annot.set_position((-90 if x_frac > 0.75 else 14,
                             -42 if y_frac > 0.80 else 14))
        annot.set_visible(True)
        for other_ax, other in self._tooltip_annots.items():
            if other_ax is not ax:
                other.set_visible(False)
        self._redraw_canvas()

    def _on_axes_leave(self, event):
        ax = event.inaxes
        if ax and ax in self._tooltip_annots:
            self._tooltip_annots[ax].set_visible(False)
            self._redraw_canvas()

    # ── Time scrubber ─────────────────────────────────────────────────────

    def _on_scrub(self, val):
        t = float(val)
        self._scrub_time_lbl.config(text=f"{t:.3f} s")
        self._update_plot_cursor(t)

    def _jump_to_tc(self):
        raw = self._jump_tc_var.get().strip()
        if not raw: return
        try:
            t = float(raw)
        except ValueError:
            messagebox.showwarning("Jump to TC",
                f"Invalid value: '{raw}'  (enter seconds, e.g. 12.5)")
            return
        lo = float(self._scrub_slider.cget("from"))
        hi = float(self._scrub_slider.cget("to"))
        t  = max(lo, min(hi, t))
        self._scrub_var.set(t)
        self._scrub_time_lbl.config(text=f"{t:.3f} s")
        self._update_plot_cursor(t)

    def _update_plot_cursor(self, t: float):
        """Redraw the red dashed time cursor across all active axes."""
        if self._plot_canvas_ref is None:
            return
        for vl in self._vlines:
            try: vl.remove()
            except Exception: pass
        self._vlines = []
        for ax in (self._ax_a, self._ax_b):
            if ax is not None:
                self._vlines.append(ax.axvline(
                    x=t, color=CURSOR_COLOR, linewidth=1.5,
                    linestyle="--", alpha=0.85, zorder=10))
        self._redraw_canvas()
