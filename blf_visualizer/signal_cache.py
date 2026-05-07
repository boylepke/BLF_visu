"""
signal_cache.py — Pre-computes per-signal time-series from decoded BLF messages.

After build() completes, cache.series["MsgName.SigName"] contains a
(timestamps_list, values_list) tuple ready for plotting or GPS interpolation.
"""

import collections

from blf_visualizer.dbc_parser import DBCParser


class SignalCache:
    """
    Holds decoded signal time-series for one recording slot.

    Attributes
    ----------
    series : dict[str, tuple[list, list]]
        ``{"MsgName.SigName": (ts_list, val_list)}``
    labels : dict[str, str]
        ``{"MsgName.SigName": "MsgName · SigName [unit]"}``
    """

    def __init__(self):
        self.series: dict = {}
        self.labels: dict = {}

    def build(self, messages: list, dbc: DBCParser, progress_cb=None):
        """
        Decode every message in *messages* using *dbc*.
        *progress_cb(frac)* is called with 0→1 if supplied.
        """
        self.series.clear()
        self.labels.clear()
        buf   = collections.defaultdict(lambda: ([], []))
        total = len(messages)

        for i, msg in enumerate(messages):
            dbc_msg = dbc.messages.get(msg.arb_id)
            if not dbc_msg:
                continue
            for sig_name, sig in dbc_msg.signals.items():
                try:
                    val = sig.decode(msg.data)
                except Exception:
                    continue
                full = f"{dbc_msg.name}.{sig_name}"
                buf[full][0].append(msg.timestamp)
                buf[full][1].append(val)
            if progress_cb and i % 2000 == 0:
                progress_cb(i / total)

        # Labels for every declared signal (even those without data)
        for msg in dbc.messages.values():
            for sig_name, sig in msg.signals.items():
                full = f"{msg.name}.{sig_name}"
                unit = f" [{sig.unit}]" if sig.unit else ""
                self.labels[full] = f"{msg.name} · {sig_name}{unit}"

        for full, (ts, vals) in buf.items():
            self.series[full] = (ts, vals)

        if progress_cb:
            progress_cb(1.0)

    @property
    def available(self) -> list:
        """Sorted list of signal names that have decoded data."""
        return sorted(self.series.keys())
