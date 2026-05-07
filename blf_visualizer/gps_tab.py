"""
gps_tab.py — GPS Track Map tab mixed into App.

GpsTabMixin provides _build_gps_tab() and all GPS helpers / playback handlers.
Requires tkintermapview at runtime (graceful warning if missing).
"""

import bisect
import math
import tkinter as tk
from tkinter import ttk, messagebox

from blf_visualizer.theme import (
    DARK_BG, PANEL_BG, TEXT_FG, MUTED,
    ACCENT, ACCENT2, ACCENT3, SEL_BG,
)


class GpsTabMixin:
    """
    GPS Track Map tab.  Requires the host class to expose:
      self.slot_a / self.slot_b  — RecordingSlot
      self._nb                   — ttk.Notebook
    """

    # ── Tab construction ──────────────────────────────────────────────────

    def _build_gps_tab(self):
        outer = ttk.Frame(self._nb)
        self._nb.add(outer, text="🗺  GPS Track")

        # Left control panel
        left = tk.Frame(outer, bg=PANEL_BG, width=280)
        left.pack(side="left", fill="y", padx=(6, 0), pady=6)
        left.pack_propagate(False)

        tk.Label(left, text="  GPS Track Map", bg=PANEL_BG, fg=ACCENT,
                 font=("Consolas", 11, "bold")).pack(fill="x", pady=(10, 6))

        # GPS source
        gps_src_f = tk.LabelFrame(left, text=" GPS Coordinates From ",
                                  bg=PANEL_BG, fg=ACCENT2,
                                  font=("Consolas", 8, "bold"),
                                  bd=1, relief="solid", padx=6, pady=6)
        gps_src_f.pack(fill="x", padx=8, pady=(0, 4))
        self._gps_slot_var = tk.StringVar(value="A")
        for val, lbl in (("A", "Recording A  (DBC 1)"),
                         ("B", "Recording B  (DBC 2)")):
            tk.Radiobutton(gps_src_f, text=lbl,
                           variable=self._gps_slot_var, value=val,
                           bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                           activebackground=PANEL_BG, activeforeground=TEXT_FG,
                           font=("Consolas", 9)).pack(anchor="w")

        # Overlay source
        ov_src_f = tk.LabelFrame(left, text=" Overlay Signals From ",
                                 bg=PANEL_BG, fg=ACCENT2,
                                 font=("Consolas", 8, "bold"),
                                 bd=1, relief="solid", padx=6, pady=6)
        ov_src_f.pack(fill="x", padx=8, pady=(0, 4))
        self._gps_ov_slot_var = tk.StringVar(value="A")
        for val, lbl in (("A", "Recording A  (DBC 1)"),
                         ("B", "Recording B  (DBC 2)")):
            tk.Radiobutton(ov_src_f, text=lbl,
                           variable=self._gps_ov_slot_var, value=val,
                           bg=PANEL_BG, fg=TEXT_FG, selectcolor=DARK_BG,
                           activebackground=PANEL_BG, activeforeground=TEXT_FG,
                           font=("Consolas", 9)).pack(anchor="w")

        # GPS signal selectors (lat / lon)
        sig_f = tk.LabelFrame(left, text=" GPS Signals ", bg=PANEL_BG,
                              fg=ACCENT2, font=("Consolas", 8, "bold"),
                              bd=1, relief="solid", padx=6, pady=6)
        sig_f.pack(fill="x", padx=8, pady=(0, 4))

        self._gps_signal_combos: list = []   # [lat_cb, lon_cb]
        for row, (attr, lbl) in enumerate((("_gps_lat_var", "Latitude"),
                                           ("_gps_lon_var", "Longitude"))):
            tk.Label(sig_f, text=f"{lbl}:", bg=PANEL_BG, fg=MUTED,
                     font=("Consolas", 8), anchor="w").grid(
                         row=row * 2, column=0, sticky="w",
                         pady=(4 if row else 0, 0))
            var = tk.StringVar()
            setattr(self, attr, var)
            cb = ttk.Combobox(sig_f, textvariable=var,
                              state="readonly", width=26)
            cb["values"] = []
            cb.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(0, 2))
            self._gps_signal_combos.append(cb)
        sig_f.columnconfigure(0, weight=1)

        # Map style
        map_f = tk.LabelFrame(left, text=" Map Style ", bg=PANEL_BG,
                              fg=ACCENT2, font=("Consolas", 8, "bold"),
                              bd=1, relief="solid", padx=6, pady=6)
        map_f.pack(fill="x", padx=8, pady=(0, 4))
        self._gps_map_style_var = tk.StringVar(value="Satellite")
        for val in ("Satellite", "OpenStreetMap"):
            tk.Radiobutton(map_f, text=val, variable=self._gps_map_style_var,
                           value=val, bg=PANEL_BG, fg=TEXT_FG,
                           selectcolor=DARK_BG,
                           activebackground=PANEL_BG, activeforeground=TEXT_FG,
                           font=("Consolas", 9)).pack(anchor="w")

        # Overlay signals list
        ov_f = tk.LabelFrame(left, text=" Hover Overlay Signals ",
                             bg=PANEL_BG, fg=ACCENT2,
                             font=("Consolas", 8, "bold"),
                             bd=1, relief="solid", padx=6, pady=6)
        ov_f.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        add_row = tk.Frame(ov_f, bg=PANEL_BG)
        add_row.pack(fill="x", pady=(0, 4))
        self._gps_ov_pick_var = tk.StringVar()
        self._gps_ov_pick = ttk.Combobox(add_row,
                                          textvariable=self._gps_ov_pick_var,
                                          state="readonly", width=22)
        self._gps_ov_pick["values"] = []
        self._gps_ov_pick.pack(side="left", fill="x", expand=True)
        ttk.Button(add_row, text="＋", width=3,
                   command=self._gps_add_overlay).pack(side="left", padx=(3, 0))

        self._gps_ov_listbox = tk.Listbox(
            ov_f, bg=DARK_BG, fg=ACCENT2, selectbackground=SEL_BG,
            font=("Consolas", 8), height=6, relief="flat", bd=0,
            activestyle="none")
        self._gps_ov_listbox.pack(fill="both", expand=True)
        ttk.Button(ov_f, text="✕ Remove",
                   command=self._gps_remove_overlay).pack(fill="x", pady=(4, 0))

        self._gps_overlay_signals: list = []

        ttk.Button(left, text="📍  Load Track",
                   command=self._gps_load_track).pack(
                       fill="x", padx=8, pady=(4, 8), ipady=6)

        # Right: map area
        right = tk.Frame(outer, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)

        self._gps_map_holder = tk.Frame(right, bg=DARK_BG)
        self._gps_map_holder.pack(fill="both", expand=True, padx=6,
                                  pady=(6, 0))

        tk.Label(self._gps_map_holder,
                 text="Load a BLF with GPS signals to display the track",
                 bg=DARK_BG, fg=MUTED,
                 font=("Consolas", 11)).place(relx=0.5, rely=0.5,
                                              anchor="center")

        # Playback bar (hidden until track loaded)
        self._gps_play_bar = tk.Frame(right, bg=PANEL_BG, pady=5, padx=8)

        btn_frame = tk.Frame(self._gps_play_bar, bg=PANEL_BG)
        btn_frame.pack(side="left", padx=(0, 10))
        self._gps_play_btn = tk.Button(
            btn_frame, text="▶", width=3,
            bg=ACCENT, fg=TEXT_FG, activebackground=ACCENT2,
            relief="flat", bd=0, font=("Consolas", 11),
            command=self._gps_play)
        self._gps_play_btn.pack(side="left", padx=(0, 2))
        tk.Button(btn_frame, text="⏹", width=3,
                  bg=PANEL_BG, fg=TEXT_FG, activebackground=SEL_BG,
                  relief="flat", bd=0, font=("Consolas", 11),
                  command=self._gps_stop).pack(side="left")

        tk.Label(self._gps_play_bar, text="Speed:", bg=PANEL_BG, fg=MUTED,
                 font=("Consolas", 8)).pack(side="left", padx=(0, 4))
        self._gps_speed_var = tk.StringVar(value="1×")
        spd = ttk.Combobox(self._gps_play_bar, textvariable=self._gps_speed_var,
                           values=["0.5×", "1×", "2×", "5×", "10×"],
                           state="readonly", width=5)
        spd.pack(side="left", padx=(0, 10))
        spd.bind("<<ComboboxSelected>>", self._gps_speed_changed)

        self._gps_seeker_var = tk.DoubleVar(value=0.0)
        self._gps_seeker = tk.Scale(
            self._gps_play_bar, variable=self._gps_seeker_var,
            from_=0.0, to=1.0, orient="horizontal", resolution=0.001,
            bg=PANEL_BG, fg=TEXT_FG, troughcolor=DARK_BG,
            highlightthickness=0, sliderrelief="flat", bd=0,
            showvalue=False, command=self._gps_on_seek)
        self._gps_seeker.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self._gps_time_lbl = tk.Label(
            self._gps_play_bar, text="0.000 s",
            bg=PANEL_BG, fg=ACCENT3, font=("Consolas", 9), width=14)
        self._gps_time_lbl.pack(side="left")

        self._gps_tooltip = tk.Label(
            right, text="", bg=DARK_BG, fg=TEXT_FG,
            font=("Consolas", 8), justify="left",
            relief="flat", bd=0, padx=8, pady=5,
            highlightbackground=MUTED, highlightthickness=1)

        # Internal state
        self._gps_track:          list  = []
        self._gps_map_widget            = None
        self._gps_playing:        bool  = False
        self._gps_play_idx:       int   = 0
        self._gps_play_after_id         = None
        self._gps_play_speed:     float = 1.0
        self._gps_car_marker            = None

    # ── Overlay list ──────────────────────────────────────────────────────

    def _gps_add_overlay(self):
        sig = self._gps_ov_pick_var.get()
        if sig and sig not in self._gps_overlay_signals:
            self._gps_overlay_signals.append(sig)
            self._gps_ov_listbox.insert("end", sig)

    def _gps_remove_overlay(self):
        sel = self._gps_ov_listbox.curselection()
        if sel:
            self._gps_overlay_signals.pop(sel[0])
            self._gps_ov_listbox.delete(sel[0])

    # ── Track loading ─────────────────────────────────────────────────────

    def _gps_load_track(self):
        try:
            import tkintermapview  # noqa: F401
        except ImportError:
            messagebox.showwarning(
                "tkintermapview missing",
                "Install the map widget:\n\n    pip install tkintermapview")
            return

        slot    = self.slot_a if self._gps_slot_var.get() == "A" else self.slot_b
        lat_sig = self._gps_lat_var.get().strip()
        lon_sig = self._gps_lon_var.get().strip()

        if not lat_sig or not lon_sig:
            sigs    = slot.cache.available
            ov_slot = (self.slot_a if self._gps_ov_slot_var.get() == "A"
                       else self.slot_b)
            if not sigs:
                messagebox.showwarning("GPS",
                    "No decoded signals found.\n"
                    "Load a BLF and import a DBC first.")
                return
            for cb in self._gps_signal_combos:
                cb["values"] = sigs
            self._gps_ov_pick["values"] = ov_slot.cache.available or sigs
            messagebox.showinfo("GPS",
                "Select Latitude and Longitude signals, then click Load Track.")
            return

        lat_data = slot.cache.series.get(lat_sig)
        lon_data = slot.cache.series.get(lon_sig)
        if lat_data is None or lon_data is None:
            messagebox.showerror("GPS",
                "Could not find data for the selected signals.")
            return

        lat_ts, lat_vals = lat_data
        lon_vals = self._gps_interp_at(lat_ts, lon_data[0], lon_data[1])

        track = [
            (ts, lat, lon)
            for ts, lat, lon in zip(lat_ts, lat_vals, lon_vals)
            if -90 <= lat <= 90 and -180 <= lon <= 180
            and (abs(lat) > 0.001 or abs(lon) > 0.001)
        ]

        if not track:
            messagebox.showerror("GPS",
                "No valid GPS coordinates found in the selected signals.")
            return

        self._gps_track = track
        self._gps_build_map(track)

    @staticmethod
    def _gps_interp_at(ts_ref: list, other_ts: list, other_vals: list) -> list:
        """Interpolate *other_vals* at each timestamp in *ts_ref*."""
        out = []
        for t in ts_ref:
            i = bisect.bisect_left(other_ts, t)
            if i == 0:               out.append(other_vals[0])
            elif i >= len(other_ts): out.append(other_vals[-1])
            else:
                t0, t1 = other_ts[i-1], other_ts[i]
                v0, v1 = other_vals[i-1], other_vals[i]
                frac = (t - t0) / (t1 - t0) if t1 != t0 else 0.0
                out.append(v0 + frac * (v1 - v0))
        return out

    @staticmethod
    def _gps_interp_value(series: tuple, ts: float) -> float:
        """Return an interpolated signal value at timestamp *ts*."""
        sig_ts, sig_vals = series
        i = bisect.bisect_left(sig_ts, ts)
        if i == 0:               return sig_vals[0]
        if i >= len(sig_ts):     return sig_vals[-1]
        t0, t1 = sig_ts[i-1], sig_ts[i]
        v0, v1 = sig_vals[i-1], sig_vals[i]
        frac = (ts - t0) / (t1 - t0) if t1 != t0 else 0.0
        return v0 + frac * (v1 - v0)

    # ── Map ───────────────────────────────────────────────────────────────

    def _gps_build_map(self, track: list):
        import tkintermapview

        self._gps_stop()
        for w in self._gps_map_holder.winfo_children():
            w.destroy()
        self._gps_map_widget = self._gps_car_marker = None

        map_widget = tkintermapview.TkinterMapView(
            self._gps_map_holder, corner_radius=0)
        map_widget.pack(fill="both", expand=True)

        if self._gps_map_style_var.get() == "Satellite":
            map_widget.set_tile_server(
                "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
                max_zoom=22)

        lats = [p[1] for p in track]
        lons = [p[2] for p in track]
        map_widget.set_position((min(lats) + max(lats)) / 2,
                                (min(lons) + max(lons)) / 2)

        span = max(max(lats) - min(lats), max(lons) - min(lons))
        zoom = next(
            (z for thr, z in ((0.0005, 20), (0.001, 19), (0.005, 18),
                               (0.01, 17), (0.05, 15), (0.1, 14),
                               (0.5, 12), (1.0, 11), (5.0, 9))
             if span <= thr), 22)
        map_widget.set_zoom(zoom)
        map_widget.set_path([(p[1], p[2]) for p in track],
                            color=str(ACCENT), width=3)

        ts0, lat0, lon0 = track[0]
        self._gps_car_marker = map_widget.set_marker(
            lat0, lon0, text="🚗", font=("Consolas", 14),
            text_color=ACCENT3,
            marker_color_circle=ACCENT3,
            marker_color_outside=ACCENT)

        map_widget.canvas.bind("<Motion>",
                               lambda e: self._gps_on_hover(e, map_widget))
        map_widget.canvas.bind("<Leave>",
                               lambda e: self._gps_tooltip.place_forget())

        self._gps_map_widget = map_widget
        t_start, t_end = track[0][0], track[-1][0]
        self._gps_seeker.config(
            from_=t_start, to=t_end,
            resolution=max(0.001, (t_end - t_start) / 10_000))
        self._gps_seeker_var.set(t_start)
        self._gps_time_lbl.config(text=f"{t_start:.3f} s")
        self._gps_play_idx = 0
        self._gps_play_bar.pack(side="bottom", fill="x", padx=6, pady=(2, 6))

    # ── Playback ──────────────────────────────────────────────────────────

    def _gps_play(self):
        if not self._gps_track or self._gps_map_widget is None:
            return
        if self._gps_play_idx >= len(self._gps_track) - 1:
            self._gps_play_idx = 0
        self._gps_playing = True
        self._gps_play_btn.config(text="⏸", command=self._gps_pause)
        self._gps_tick()

    def _gps_pause(self):
        self._gps_playing = False
        self._gps_play_btn.config(text="▶", command=self._gps_play)
        if self._gps_play_after_id:
            self.after_cancel(self._gps_play_after_id)
            self._gps_play_after_id = None

    def _gps_stop(self):
        self._gps_pause()
        self._gps_play_idx = 0
        if self._gps_track:
            ts = self._gps_track[0][0]
            self._gps_seeker_var.set(ts)
            self._gps_time_lbl.config(text=f"{ts:.3f} s")
            self._gps_move_car(0)
        self._gps_tooltip.place_forget()

    def _gps_speed_changed(self, event=None):
        raw = self._gps_speed_var.get().replace("×", "")
        try:   self._gps_play_speed = float(raw)
        except ValueError: self._gps_play_speed = 1.0

    def _gps_on_seek(self, val):
        t = float(val)
        self._gps_time_lbl.config(text=f"{t:.3f} s")
        ts_list = [p[0] for p in self._gps_track]
        idx = max(0, min(bisect.bisect_left(ts_list, t),
                         len(self._gps_track) - 1))
        self._gps_play_idx = idx
        self._gps_move_car(idx)

    def _gps_tick(self):
        if not self._gps_playing:
            return
        idx   = self._gps_play_idx
        track = self._gps_track
        if idx >= len(track) - 1:
            self._gps_pause()
            return
        self._gps_move_car(idx)
        ts = track[idx][0]
        self._gps_seeker_var.set(ts)
        self._gps_time_lbl.config(text=f"{ts:.3f} s")
        self._gps_play_idx += 1
        dt    = track[idx + 1][0] - track[idx][0]
        delay = max(16, int(dt * 1000 / self._gps_play_speed))
        self._gps_play_after_id = self.after(delay, self._gps_tick)

    # ── Marker / tooltip ──────────────────────────────────────────────────

    def _gps_move_car(self, idx: int):
        if not self._gps_track or self._gps_car_marker is None:
            return
        ts, lat, lon = self._gps_track[idx]
        self._gps_car_marker.set_position(lat, lon)

        if not self._gps_overlay_signals:
            self._gps_tooltip.place_forget()
            return

        ov_slot = (self.slot_a if self._gps_ov_slot_var.get() == "A"
                   else self.slot_b)
        lines = [f"t = {ts:.3f} s"]
        for sig_name in self._gps_overlay_signals:
            series = ov_slot.cache.series.get(sig_name)
            if series is not None:
                v     = self._gps_interp_value(series, ts)
                label = ov_slot.cache.labels.get(sig_name, sig_name)
                lines.append(f"{label} = {v:.4g}")

        self._gps_tooltip.config(text="\n".join(lines))
        self._gps_tooltip.update_idletasks()
        tw = self._gps_tooltip.winfo_reqwidth()
        th = self._gps_tooltip.winfo_reqheight()

        cx, cy = self._gps_latlon_to_canvas(lat, lon)
        if cx is None:
            self._gps_tooltip.place_forget()
            return

        holder = self._gps_map_holder
        wx = holder.winfo_rootx() - self.winfo_rootx() + cx
        wy = holder.winfo_rooty() - self.winfo_rooty() + cy
        tx = max(4, min(wx - tw // 2, self.winfo_width() - tw - 4))
        ty = wy - th - 28
        if ty < 4: ty = wy + 28
        ty = max(4, min(ty, self.winfo_height() - th - 4))
        self._gps_tooltip.place(x=tx, y=ty)
        self._gps_tooltip.lift()

    def _gps_latlon_to_canvas(self, lat: float, lon: float):
        mw = self._gps_map_widget
        if mw is None:
            return None, None
        try:
            zoom      = round(mw.zoom)
            tile_size = mw.tile_size
            ul_x, ul_y = mw.upper_left_tile_pos
            n     = 2 ** zoom
            tx    = n * (lon + 180.0) / 360.0
            lat_r = math.radians(lat)
            ty    = n * (1.0 - math.log(
                math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0
            return (tx - ul_x) * tile_size, (ty - ul_y) * tile_size
        except Exception:
            return None, None

    def _gps_on_hover(self, event, map_widget):
        if self._gps_playing or not self._gps_track:
            return
        try:
            lat_cur, lon_cur = map_widget.convert_canvas_coords_to_decimal_coords(
                event.x, event.y)
        except Exception:
            return

        best_idx, best_dist = 0, float("inf")
        for i, (_, lat, lon) in enumerate(self._gps_track):
            d = (lat - lat_cur) ** 2 + (lon - lon_cur) ** 2
            if d < best_dist:
                best_dist, best_idx = d, i

        if best_dist ** 0.5 > 0.0005:
            self._gps_tooltip.place_forget()
            return

        ts, lat, lon = self._gps_track[best_idx]
        ov_slot = (self.slot_a if self._gps_ov_slot_var.get() == "A"
                   else self.slot_b)

        lines = [f"  t = {ts:.3f} s",
                 f"  lat = {lat:.6f}",
                 f"  lon = {lon:.6f}"]
        for sig_name in self._gps_overlay_signals:
            series = ov_slot.cache.series.get(sig_name)
            if series is not None:
                v     = self._gps_interp_value(series, ts)
                label = ov_slot.cache.labels.get(sig_name, sig_name)
                lines.append(f"  {label} = {v:.4g}")

        self._gps_tooltip.config(text="\n".join(lines))
        self._gps_tooltip.update_idletasks()
        tw = self._gps_tooltip.winfo_reqwidth()
        th = self._gps_tooltip.winfo_reqheight()

        holder = self._gps_map_holder
        cx = holder.winfo_rootx() - self.winfo_rootx() + event.x
        cy = holder.winfo_rooty() - self.winfo_rooty() + event.y
        offset = 16
        wx = (cx + offset if cx + offset + tw < self.winfo_width() - 4
              else cx - offset - tw)
        wy = (cy + offset if cy + offset + th < self.winfo_height() - 4
              else cy - offset - th)
        self._gps_tooltip.place(x=wx, y=wy)
        self._gps_tooltip.lift()
