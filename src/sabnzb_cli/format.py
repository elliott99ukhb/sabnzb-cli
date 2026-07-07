"""Small parsing/formatting helpers shared by the dashboard."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from urllib.parse import unquote, urlparse

_SPARK_CHARS = "▁▂▃▄▅▆▇█"

# Characters that a shell (and a terminal's drag-to-insert) backslash-escapes
# in a bare path. Notably this excludes letters and digits, so a typed Windows
# server path like ``C:\dl\file.nzb`` is left intact.
_ESCAPED_CHAR = re.compile(r"\\([ !\"#$&'()*;<>?\[\]\\^`{|}~])")


def clean_input_path(raw: str) -> str:
    """Normalise a path that may have been dragged into the terminal.

    Dragging a file into macOS Terminal / iTerm2 inserts its path, but with
    spaces and punctuation backslash-escaped, sometimes wrapped in quotes, and
    occasionally as a ``file://`` URL. Turn any of those back into a plain path,
    while leaving http(s) URLs and ordinary typed input untouched.
    """
    text = raw.strip()
    if not text:
        return ""
    # Some shells quote a dragged path; drop a matching outer quote pair.
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1]
    if text.startswith(("http://", "https://")):
        return text
    if text.startswith("file://"):
        return unquote(urlparse(text).path)
    return _ESCAPED_CHAR.sub(r"\1", text)


def to_float(value: object, default: float = 0.0) -> float:
    """Best-effort float conversion for the loosely-typed SABnzbd fields."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def human_speed(kbps: float) -> str:
    """Format a KB/s value as a human-readable transfer rate."""
    if kbps <= 0:
        return "0 KB/s"
    if kbps < 1024:
        return f"{kbps:.0f} KB/s"
    mbps = kbps / 1024
    if mbps < 1024:
        return f"{mbps:.1f} MB/s"
    return f"{mbps / 1024:.2f} GB/s"


def human_size_mb(mb: float) -> str:
    """Format a size given in megabytes."""
    if mb < 1024:
        return f"{mb:.0f} MB"
    gb = mb / 1024
    if gb < 1024:
        return f"{gb:.2f} GB"
    return f"{gb / 1024:.2f} TB"


def truncate(text: str, width: int) -> str:
    if width <= 1:
        return text[:width]
    if len(text) <= width:
        return text
    return text[: width - 1] + "…"


def sparkline(samples: list[float], width: Optional[int] = None,
              pad: bool = False) -> str:
    """Render a list of numbers as a Unicode block sparkline.

    When ``pad`` is set and there are fewer samples than ``width``, the line is
    left-padded with the baseline block so it always spans the full ``width``,
    with the most recent samples kept on the right.
    """
    if not samples and not (pad and width):
        return ""
    data = samples[-width:] if width else samples
    peak = max(data) if data else 0.0
    if peak <= 0:
        line = _SPARK_CHARS[0] * len(data)
    else:
        scale = len(_SPARK_CHARS) - 1
        line = "".join(
            _SPARK_CHARS[min(scale, int(round((v / peak) * scale)))] for v in data
        )
    if pad and width and len(line) < width:
        line = _SPARK_CHARS[0] * (width - len(line)) + line
    return line


def format_completed(ts: object) -> str:
    """Turn a unix timestamp into a short 'HH:MM' / date string."""
    epoch = to_float(ts, default=0.0)
    if epoch <= 0:
        return "—"
    try:
        dt = datetime.fromtimestamp(epoch)
    except (OverflowError, OSError, ValueError):
        return "—"
    now = datetime.now()
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    return dt.strftime("%b %d")
