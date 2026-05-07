"""
BLF Visualizer — entry point.

Usage:
    python main.py
    python main.py recording_a.blf
    python main.py recording_a.blf recording_b.blf
"""

from blf_visualizer.app import App

if __name__ == "__main__":
    App().mainloop()
