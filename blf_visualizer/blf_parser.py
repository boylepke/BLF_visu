"""
blf_parser.py — Binary Logging Format (BLF) parser.

Supports CAN, CAN-FD (regular + 64-byte), CAN error frames,
and both compressed (zlib) and uncompressed LOG_CONTAINER objects.
"""

import struct
import datetime
import collections
import zlib

from blf_visualizer.constants import (
    FILE_SIGNATURE_PREFIX, OBJECT_SIGNATURE,
    OBJ_CAN_MESSAGE, OBJ_CAN_MESSAGE2,
    OBJ_CAN_ERROR, OBJ_CAN_ERROR_EXT,
    OBJ_LOG_CONTAINER,
    OBJ_CAN_FD_MESSAGE, OBJ_CAN_FD_MESSAGE_64,
    COMPRESSION_ZLIB,
)


# ── Low-level helpers ──────────────────────────────────────────────────────

def _up(fmt: str, data: bytes, offset: int = 0):
    return struct.unpack_from(fmt, data, offset)[0]

def _align4(n: int) -> int:
    return (n + 3) & ~3

def _fd_dlc_to_len(dlc: int) -> int:
    table = [0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64]
    return table[dlc] if dlc < len(table) else 8


# ── Data classes ───────────────────────────────────────────────────────────

class BLFParseError(Exception):
    """Raised when the file is not a valid or parseable BLF."""


class BLFMessage:
    """One decoded CAN / CAN-FD frame."""

    __slots__ = ("timestamp", "channel", "arb_id", "is_extended",
                 "dlc", "data", "is_fd", "is_error", "raw_type")

    def __init__(self, ts, ch, arb_id, is_ext, dlc, data,
                 is_fd=False, is_error=False, raw_type=0):
        self.timestamp   = ts
        self.channel     = ch
        self.arb_id      = arb_id
        self.is_extended = is_ext
        self.dlc         = dlc
        self.data        = data
        self.is_fd       = is_fd
        self.is_error    = is_error
        self.raw_type    = raw_type

    @property
    def data_str(self) -> str:
        return " ".join(f"{b:02X}" for b in self.data)

    @property
    def timestamp_str(self) -> str:
        return f"{self.timestamp:.6f}"


# ── Parser ─────────────────────────────────────────────────────────────────

class BLFParser:
    """Parse a BLF file and return :class:`BLFMessage` objects."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.messages: list = []
        self.stats:    dict = {}

    def parse(self, progress_cb=None) -> list:
        """
        Parse the file.  *progress_cb(frac)* is called with 0→1 if supplied.
        Returns the list of :class:`BLFMessage` objects.
        """
        with open(self.filepath, "rb") as fh:
            raw = fh.read()

        if len(raw) < 8:
            raise BLFParseError("File too small.")
        if raw[:4] != FILE_SIGNATURE_PREFIX:
            raise BLFParseError(
                f"Not a valid BLF file.\n"
                f"Expected: {FILE_SIGNATURE_PREFIX!r}\n"
                f"Found:    {raw[:8]!r}  ({raw[:8].hex(' ').upper()})")

        self._parse_file_header(raw)
        self.messages = []

        try:
            hdr_sz = _up("<I", raw, 4)
            offset = hdr_sz if 0x40 <= hdr_sz <= 0x1000 else 0x90
        except Exception:
            offset = 0x90

        file_size = len(raw)
        n = 0
        while offset < file_size - 32:
            idx = raw.find(OBJECT_SIGNATURE, offset)
            if idx == -1:
                break
            offset = idx
            try:
                offset, msgs = self._parse_object(raw, offset)
                self.messages.extend(msgs)
                n += len(msgs)
            except struct.error:
                offset += 4
            if progress_cb and n % 500 == 0:
                progress_cb(offset / file_size)

        if self.messages:
            t0 = self.messages[0].timestamp
            for m in self.messages:
                m.timestamp -= t0

        self._build_stats()
        if progress_cb:
            progress_cb(1.0)
        return self.messages

    # ── Header ────────────────────────────────────────────────────

    def _parse_file_header(self, raw: bytes):
        self.stats["blf_version"] = "LOGG"

        def _read_dt(off: int):
            if off + 16 > len(raw):
                return None
            s = struct.unpack_from("<8H", raw, off)
            if not (1990 <= s[0] <= 2100):
                return None
            try:
                return datetime.datetime(
                    s[0], max(1, min(s[1], 12)), max(1, min(s[3], 31)),
                    min(s[4], 23), min(s[5], 59), min(s[6], 59),
                    min(s[7], 999) * 1000).isoformat(sep=" ")
            except ValueError:
                return None

        self.stats["start_time"] = _read_dt(0x28) or "unknown"
        self.stats["end_time"]   = _read_dt(0x38) or "unknown"

    # ── Object dispatch ───────────────────────────────────────────

    def _parse_object(self, raw: bytes, offset: int):
        if raw[offset:offset + 4] != OBJECT_SIGNATURE:
            return offset + 1, []

        hdr_size  = _up("<H", raw, offset + 4)
        obj_size  = _up("<I", raw, offset + 8)
        obj_type  = _up("<I", raw, offset + 12)
        timestamp = ((_up("<I", raw, offset + 28) << 32)
                     | _up("<I", raw, offset + 24)) / 1e9

        data_end = offset + obj_size
        if obj_size < hdr_size or data_end > len(raw):
            return offset + max(obj_size, 4), []

        obj_data   = raw[offset + hdr_size: data_end]
        new_offset = offset + _align4(obj_size)
        msgs       = []

        if obj_type == OBJ_LOG_CONTAINER:
            msgs = self._parse_container(obj_data)
        elif obj_type in (OBJ_CAN_MESSAGE, OBJ_CAN_MESSAGE2):
            m = self._parse_can(obj_data, timestamp, obj_type)
            if m: msgs = [m]
        elif obj_type == OBJ_CAN_FD_MESSAGE:
            m = self._parse_canfd(obj_data, timestamp)
            if m: msgs = [m]
        elif obj_type == OBJ_CAN_FD_MESSAGE_64:
            m = self._parse_canfd64(obj_data, timestamp)
            if m: msgs = [m]
        elif obj_type in (OBJ_CAN_ERROR, OBJ_CAN_ERROR_EXT):
            m = self._parse_error(obj_data, timestamp, obj_type)
            if m: msgs = [m]

        return new_offset, msgs

    # ── Container ─────────────────────────────────────────────────

    def _parse_container(self, data: bytes) -> list:
        if len(data) < 16:
            return []
        compression = _up("<H", data, 0)
        try:
            inner = (zlib.decompress(data[16:])
                     if compression == COMPRESSION_ZLIB
                     else data[16:])
        except Exception:
            return []
        msgs, off = [], 0
        while off < len(inner) - 32:
            idx = inner.find(OBJECT_SIGNATURE, off)
            if idx == -1:
                break
            off = idx
            try:
                off, m = self._parse_object(inner, off)
                msgs.extend(m)
            except struct.error:
                off += 4
        return msgs

    # ── Frame parsers ─────────────────────────────────────────────

    def _parse_can(self, data: bytes, ts: float, obj_type: int):
        if len(data) < 8: return None
        ch     = _up("<H", data, 0)
        dlc    = min(_up("<B", data, 3), 8)
        arb_id = _up("<I", data, 4)
        is_ext = bool(arb_id & 0x80000000)
        arb_id &= 0x1FFFFFFF
        return BLFMessage(ts, ch, arb_id, is_ext, dlc,
                          data[8: 8 + dlc], raw_type=obj_type)

    def _parse_canfd(self, data: bytes, ts: float):
        if len(data) < 12: return None
        ch     = _up("<H", data, 0)
        dlc    = _up("<B", data, 3)
        arb_id = _up("<I", data, 4)
        length = _fd_dlc_to_len(dlc)
        is_ext = bool(arb_id & 0x80000000)
        arb_id &= 0x1FFFFFFF
        return BLFMessage(ts, ch, arb_id, is_ext, dlc,
                          data[12: 12 + length],
                          is_fd=True, raw_type=OBJ_CAN_FD_MESSAGE)

    def _parse_canfd64(self, data: bytes, ts: float):
        if len(data) < 32: return None
        ch     = _up("<B", data, 0)
        dlc    = _up("<B", data, 1) & 0x0F
        arb_id = _up("<I", data, 4)
        length = _fd_dlc_to_len(dlc)
        is_ext = bool(arb_id & 0x80000000)
        arb_id &= 0x1FFFFFFF
        return BLFMessage(ts, ch, arb_id, is_ext, dlc,
                          data[32: 32 + length],
                          is_fd=True, raw_type=OBJ_CAN_FD_MESSAGE_64)

    def _parse_error(self, data: bytes, ts: float, obj_type: int):
        if len(data) < 2: return None
        ch = _up("<H", data, 0)
        return BLFMessage(ts, ch, 0, False, 0, b"",
                          is_error=True, raw_type=obj_type)

    # ── Statistics ────────────────────────────────────────────────

    def _build_stats(self):
        self.stats.update(
            total=len(self.messages),
            id_counts=collections.Counter(m.arb_id  for m in self.messages),
            ch_counts=collections.Counter(m.channel for m in self.messages),
            duration=(self.messages[-1].timestamp - self.messages[0].timestamp
                      if self.messages else 0.0),
        )
