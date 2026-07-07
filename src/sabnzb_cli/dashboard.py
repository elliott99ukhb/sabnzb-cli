"""Rich-based rendering of the SABnzbd dashboard.

Two presentations share the same panel builders:
  * ``build_app_layout`` — a full-screen, app-like ``Layout`` (title bar, speed
    graph, queue + history, status/key bar) used for the live and interactive
    modes.
  * ``render_dashboard`` — a simple stacked ``Group`` used for ``--once``
    snapshots, which scales to content instead of filling the screen.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Deque, Dict, List, Optional

from rich import box
from rich.align import Align
from rich.console import Console, ConsoleOptions, Group, RenderResult
from rich.layout import Layout
from rich.measure import Measurement
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .config import Config
from .format import (
    format_completed,
    human_size_mb,
    human_speed,
    sparkline,
    to_float,
    truncate,
)

# Keep enough samples to fill a very wide terminal; the graph itself renders
# only as many columns as the current window provides.
SPEED_HISTORY_LEN = 400


class SpeedHistory:
    """Rolling window of recent speed samples (KB/s) for the sparkline."""

    def __init__(self, maxlen: int = SPEED_HISTORY_LEN) -> None:
        self._samples: Deque[float] = deque(maxlen=maxlen)

    def add(self, kbps: float) -> None:
        self._samples.append(max(0.0, kbps))

    @property
    def samples(self) -> List[float]:
        return list(self._samples)

    @property
    def peak(self) -> float:
        return max(self._samples) if self._samples else 0.0


class SpeedGraph:
    """A sparkline that expands to fill whatever width it is rendered into."""

    def __init__(self, samples: List[float], style: str = "green") -> None:
        self._samples = samples
        self._style = style

    def __rich_console__(self, console: Console,
                         options: ConsoleOptions) -> RenderResult:
        width = options.max_width
        line = sparkline(self._samples, width=width, pad=True)
        yield Text(line or "(collecting…)", style=self._style)

    def __rich_measure__(self, console: Console,
                         options: ConsoleOptions) -> Measurement:
        # Advertise that we can use the full available width.
        return Measurement(1, options.max_width)


def _status_style(queue: Dict[str, Any]) -> tuple[str, str]:
    """Return (label, rich-style) for the current queue state."""
    if queue.get("paused"):
        return "PAUSED", "yellow"
    status = str(queue.get("status", "")).lower()
    slots = queue.get("slots") or []
    if status == "downloading" and slots:
        return "DOWNLOADING", "green"
    if slots:
        return (status.upper() or "QUEUED"), "cyan"
    return "IDLE", "grey62"


# --- Individual panels ---------------------------------------------------

def render_app_bar(config: Config, queue: Dict[str, Any]) -> Panel:
    label, style = _status_style(queue)
    kbps = to_float(queue.get("kbpersec"))

    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)

    title = Text("  SABnzbd Monitor", style="bold white")
    host = Text(config.netloc, style="grey70")
    right = Text()
    right.append("● ", style=style)
    right.append(label, style=f"bold {style}")
    right.append("   ↓ ")
    right.append(human_speed(kbps), style="bold green")
    right.append("  ")

    grid.add_row(title, host, right)
    return Panel(grid, box=box.HEAVY, style=style, padding=(0, 0))


def render_speed_panel(speed_history: SpeedHistory,
                       queue: Dict[str, Any]) -> Panel:
    samples = speed_history.samples
    current = samples[-1] if samples else 0.0

    disk_free = to_float(queue.get("diskspace1"))
    disk_total = to_float(queue.get("diskspacetotal1"))
    used_pct = (disk_total - disk_free) / disk_total * 100 if disk_total > 0 else 0.0

    line1 = SpeedGraph(samples, style="green")

    line2 = Text()
    line2.append("now ", style="grey62")
    line2.append(human_speed(current), style="bold green")
    line2.append("   peak ", style="grey62")
    line2.append(human_speed(speed_history.peak), style="bold")
    line2.append("      disk ", style="grey62")
    if disk_total > 0:
        bar_w = 16
        filled = int(round(used_pct / 100 * bar_w))
        bar_style = "red" if used_pct >= 90 else "cyan"
        line2.append("[")
        line2.append("█" * filled, style=bar_style)
        line2.append("░" * (bar_w - filled), style="grey42")
        line2.append("] ")
        line2.append(f"{disk_free:.0f}/{disk_total:.0f} GB ({used_pct:.0f}% used)")
    else:
        line2.append("unavailable", style="grey62")

    return Panel(Group(line1, Text(), line2), title="Download speed",
                 border_style="green", box=box.ROUNDED)


def _progress_bar(pct: float, width: int = 22) -> Text:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100 * width))
    style = "green" if pct >= 100 else "cyan"
    bar = Text()
    bar.append("█" * filled, style=style)
    bar.append("░" * (width - filled), style="grey42")
    bar.append(f" {pct:3.0f}%")
    return bar


def render_queue(queue: Dict[str, Any], selected: Optional[int] = None,
                 name_width: int = 38) -> Panel:
    slots = queue.get("slots") or []
    if not slots:
        return Panel(Align.center(Text("Queue is empty.", style="grey62"),
                                  vertical="middle"),
                     title="Queue", border_style="cyan", box=box.ROUNDED)

    table = Table(expand=True, box=None, pad_edge=False, header_style="bold grey70")
    table.add_column(" ", width=2, style="cyan")
    table.add_column("#", justify="right", style="grey62", width=3)
    table.add_column("Name", no_wrap=True, ratio=1)
    table.add_column("Size", justify="right", width=9)
    table.add_column("Progress", width=27)
    table.add_column("ETA", justify="right", width=9)
    table.add_column("Status", width=12)

    for i, slot in enumerate(slots):
        is_sel = selected is not None and i == selected
        name = truncate(str(slot.get("filename") or slot.get("name") or "?"),
                        name_width)
        size = human_size_mb(to_float(slot.get("mb")))
        pct = to_float(slot.get("percentage"))
        eta = str(slot.get("timeleft") or "—")
        status = str(slot.get("status") or "")
        status_style = "green" if status.lower() == "downloading" else (
            "yellow" if status.lower() == "paused" else "white")
        table.add_row(
            "▶" if is_sel else "",
            str(i + 1),
            name,
            size,
            _progress_bar(pct),
            eta,
            Text(status, style=status_style),
            style="on grey23" if is_sel else None,
        )

    return Panel(table, title=f"Queue ({len(slots)})", border_style="cyan",
                 box=box.ROUNDED)


def render_history(history_data: Dict[str, Any], limit: int = 12,
                   name_width: int = 34) -> Panel:
    slots = (history_data.get("slots") or [])[:limit]
    if not slots:
        return Panel(Align.center(Text("No recent history.", style="grey62"),
                                  vertical="middle"),
                     title="Recent", border_style="magenta", box=box.ROUNDED)

    table = Table(expand=True, box=None, pad_edge=False, header_style="bold grey70")
    table.add_column("Name", no_wrap=True, ratio=1)
    table.add_column("Status", width=10)
    table.add_column("When", justify="right", width=7)

    for slot in slots:
        name = truncate(str(slot.get("name") or "?"), name_width)
        status = str(slot.get("status") or "")
        low = status.lower()
        if low == "completed":
            status_text = Text(status, style="green")
        elif low == "failed":
            status_text = Text(status, style="bold red")
        else:
            status_text = Text(status, style="yellow")
        when = format_completed(slot.get("completed"))
        table.add_row(name, status_text, when)

    return Panel(table, title="Recent", border_style="magenta", box=box.ROUNDED)


def render_footer(message: str = "", interactive: bool = False,
                  confirm: bool = False) -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="right")

    if interactive:
        keys = Text()
        for key, desc in (
            ("↑/↓", "select"), ("p", "pause item"), ("d", "delete"),
            ("P", "pause all"), ("a", "add nzb"), ("r", "refresh"),
            ("q", "quit"),
        ):
            keys.append(f" {key} ", style="bold black on grey70")
            keys.append(f" {desc}   ", style="grey70")
    else:
        keys = Text(" live view — press Ctrl-C to quit ", style="grey70")

    msg_style = "bold yellow" if confirm else "bold cyan"
    msg = Text(message, style=msg_style)
    grid.add_row(keys, msg)
    return Panel(grid, box=box.HEAVY, border_style="grey42", padding=(0, 0))


# --- Composed presentations ---------------------------------------------

def build_app_layout(
    config: Config,
    queue: Dict[str, Any],
    history_data: Optional[Dict[str, Any]],
    speed_history: SpeedHistory,
    selected: Optional[int] = None,
    message: str = "",
    interactive: bool = False,
    confirm: bool = False,
) -> Layout:
    root = Layout(name="root")
    sections = [
        Layout(render_app_bar(config, queue), name="header", size=3),
        Layout(render_speed_panel(speed_history, queue), name="speed", size=5),
    ]

    body = Layout(name="body", ratio=1)
    if history_data is not None:
        body.split_row(
            Layout(render_queue(queue, selected), name="queue", ratio=2),
            Layout(render_history(history_data), name="history", ratio=1),
        )
    else:
        body.update(render_queue(queue, selected))
    sections.append(body)

    sections.append(
        Layout(render_footer(message, interactive, confirm),
               name="footer", size=3)
    )
    root.split_column(*sections)
    return root


def render_dashboard(
    config: Config,
    queue: Dict[str, Any],
    history_data: Optional[Dict[str, Any]],
    speed_history: SpeedHistory,
) -> Group:
    """Simple stacked layout for one-shot ``--once`` snapshots."""
    parts = [
        render_app_bar(config, queue),
        render_speed_panel(speed_history, queue),
        render_queue(queue),
    ]
    if history_data is not None:
        parts.append(render_history(history_data))
    return Group(*parts)


def render_error(message: str) -> Panel:
    return Panel(Text(message, style="red"), title="Error", border_style="red")
