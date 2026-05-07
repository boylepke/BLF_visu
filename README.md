# BLF Visualizer

Desktop tool for inspecting, comparing, and plotting CAN / CAN-FD recordings stored in Vector BLF files.

## Features

- **Dual recording** — load two BLF files (A & B) side by side
- **DBC decoding** — import a DBC per slot; signals decoded inline in the message table
- **Signal Plot** — stacked or overlaid plots, shared time cursor, reference lines
- **GPS Track Map** — render lat/lon signals on an interactive map with animated playback
- **CSV export** — export filtered, DBC-decoded messages per slot
- **Live filter** — filter messages by text, channel, or Arb ID

## Requirements

| Dependency | Required | Purpose |
|---|---|---|
| Python 3.10+ | ✅ | `tkinter` is bundled with standard Python builds |
| `matplotlib` | Optional | Signal Comparison tab |
| `tkintermapview` | Optional | GPS Track Map tab |

## Quick start

```bash
git clone https://github.com/yourusername/blf_visualizer.git
cd blf_visualizer

# install optional dependencies
pip install matplotlib tkintermapview

# launch
python main.py
python main.py recording_a.blf
python main.py recording_a.blf recording_b.blf
```

## Project layout

```
blf_visualizer/
├── main.py                  ← entry point  (python main.py)
├── requirements.txt
├── README.md
├── .gitignore
└── blf_visualizer/
    ├── constants.py         90  lines — BLF object-type constants
    ├── theme.py            100  lines — colours, column defs, apply_style()
    ├── blf_parser.py       185  lines — BLFParser + BLFMessage
    ├── dbc_parser.py       130  lines — DBCParser + DBCSignal
    ├── signal_cache.py      70  lines — SignalCache (decoded time-series)
    ├── recording_slot.py   310  lines — RecordingSlot (state + widgets)
    ├── plot_tab.py         290  lines — PlotTabMixin (Signal Comparison tab)
    ├── gps_tab.py          360  lines — GpsTabMixin (GPS Track Map tab)
    └── app.py              120  lines — App (main window shell)
```

## Where to look when you want to change something

| Goal | File |
|---|---|
| Support a new BLF object type | `constants.py` → `blf_parser.py` → `_parse_object` |
| Extend DBC parsing (e.g. attributes) | `dbc_parser.py` |
| Change colours, fonts, or column widths | `theme.py` |
| Add a column to the message table | `theme.py` (COLS / COL_LABELS / COL_WIDTH) + `recording_slot.py` → `_populate_tree` |
| Add a new plot style | `plot_tab.py` → `_do_plot` |
| Change map tile server | `gps_tab.py` → `_gps_build_map` |
| Add a fourth tab | create `blf_visualizer/my_tab.py` with a mixin, inherit in `app.py` |
