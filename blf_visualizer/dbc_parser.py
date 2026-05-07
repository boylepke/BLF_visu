"""
dbc_parser.py — Minimal DBC (CAN database) parser.

Supports BO_ message definitions, SG_ signal definitions (Intel / Motorola,
signed / unsigned), and VAL_ value-table entries.
"""

import re


class DBCSignal:
    """One signal within a DBC message definition."""

    __slots__ = ("name", "start_bit", "length", "byte_order", "is_signed",
                 "factor", "offset", "min", "max", "unit", "values")

    def __init__(self, name, start_bit, length, byte_order, is_signed,
                 factor, offset, mn, mx, unit):
        self.name       = name
        self.start_bit  = start_bit
        self.length     = length
        self.byte_order = byte_order   # "1" = Intel/LE, "0" = Motorola/BE
        self.is_signed  = is_signed
        self.factor     = factor
        self.offset     = offset
        self.min        = mn
        self.max        = mx
        self.unit       = unit
        self.values: dict = {}

    def _extract_bits(self, data: bytes) -> int:
        if self.byte_order == "1":          # Intel / little-endian
            value = 0
            for i in range(self.length):
                bp = self.start_bit + i
                bi, bj = bp >> 3, bp & 7
                if bi < len(data) and (data[bi] >> bj) & 1:
                    value |= (1 << i)
            return value
        else:                               # Motorola / big-endian
            abs_msb = (self.start_bit >> 3) * 8 + (7 - (self.start_bit & 7))
            value = 0
            for i in range(self.length):
                ab = abs_msb + i
                bi = ab >> 3
                bj = 7 - (ab & 7)
                if bi < len(data) and (data[bi] >> bj) & 1:
                    value |= (1 << (self.length - 1 - i))
            return value

    def decode(self, data: bytes) -> float:
        """Return the physical (scaled + offset) value."""
        raw = self._extract_bits(data)
        if self.is_signed and raw >= (1 << (self.length - 1)):
            raw -= (1 << self.length)
        return raw * self.factor + self.offset

    def decode_str(self, data: bytes) -> str:
        raw  = self._extract_bits(data)
        phys = self.decode(data)
        unit = f" {self.unit}" if self.unit else ""
        if self.values:
            label = self.values.get(int(raw))
            if label:
                return f"{label} ({phys:.4g}{unit})"
        return f"{phys:.4g}{unit}"


class DBCMessage:
    """DBC message definition (one BO_ block)."""

    __slots__ = ("msg_id", "name", "dlc", "signals")

    def __init__(self, msg_id: int, name: str, dlc: int):
        self.msg_id  = msg_id
        self.name    = name
        self.dlc     = dlc
        self.signals: dict = {}


class DBCParser:
    """Parse a *.dbc file into :class:`DBCMessage` / :class:`DBCSignal` objects."""

    _RE_MSG = re.compile(r'^BO_\s+(\d+)\s+(\w+)\s*:\s*(\d+)\s+\w+')
    _RE_SIG = re.compile(
        r'^\s+SG_\s+(\w+)\s*(?:M|m\d+|)?\s*:\s*'
        r'(\d+)\|(\d+)@([01])([+-])\s*'
        r'\(([^,]+),([^)]+)\)\s*\[([^|]+)\|([^\]]+)\]\s*"([^"]*)"\s*(.*)')
    _RE_VAL = re.compile(
        r'^VAL_\s+(\d+)\s+(\w+)\s+((?:\d+\s+"[^"]*"\s*)+);?')

    def __init__(self):
        self.messages: dict = {}

    def parse_file(self, path: str):
        """Parse *path* and populate :attr:`messages`."""
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()

        current_msg = None
        for line in lines:
            m = self._RE_MSG.match(line)
            if m:
                msg_id = int(m.group(1)) & 0x1FFFFFFF
                current_msg = DBCMessage(msg_id, m.group(2), int(m.group(3)))
                self.messages[msg_id] = current_msg
                continue

            s = self._RE_SIG.match(line)
            if s and current_msg:
                sig = DBCSignal(
                    s.group(1),
                    int(s.group(2)), int(s.group(3)),
                    s.group(4), s.group(5) == "-",
                    float(s.group(6)), float(s.group(7)),
                    float(s.group(8)), float(s.group(9)),
                    s.group(10))
                current_msg.signals[sig.name] = sig
                continue

            v = self._RE_VAL.match(line)
            if v:
                msg_id   = int(v.group(1)) & 0x1FFFFFFF
                sig_name = v.group(2)
                pairs    = re.findall(r'(\d+)\s+"([^"]*)"', v.group(3))
                msg = self.messages.get(msg_id)
                if msg:
                    sig = msg.signals.get(sig_name)
                    if sig:
                        sig.values = {int(k): lbl for k, lbl in pairs}

    def decode_message(self, arb_id: int, data: bytes) -> dict:
        """Return ``{signal_name: float}`` for *arb_id*, or ``{}``."""
        msg = self.messages.get(arb_id)
        if not msg:
            return {}
        out = {}
        for name, sig in msg.signals.items():
            try:
                out[name] = sig.decode(data)
            except Exception:
                pass
        return out
