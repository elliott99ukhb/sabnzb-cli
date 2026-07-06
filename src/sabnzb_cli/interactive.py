"""Interactive, keyboard-driven full-screen mode.

Uses only the standard library (termios/tty/select) to read single keypresses
without blocking the periodic refresh, so it stays dependency-light.
"""

from __future__ import annotations

import select
import sys
import termios
import time
import tty
from typing import List, Optional

from rich.console import Console
from rich.live import Live

from .client import SabClient, SabError
from .dashboard import SpeedHistory, build_app_layout
from .format import to_float

# Escape sequences for the arrow keys (after the leading ESC).
_ARROWS = {"[A": "up", "[B": "down", "[C": "right", "[D": "left"}


def _read_key(timeout: float) -> Optional[str]:
    """Return a single logical keypress, or None if nothing arrived in time."""
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    ch = sys.stdin.read(1)
    if ch == "\x1b":  # ESC — maybe the start of an arrow-key sequence
        ready, _, _ = select.select([sys.stdin], [], [], 0.02)
        if ready:
            seq = sys.stdin.read(2)
            return _ARROWS.get(seq, "esc")
        return "esc"
    return ch


class InteractiveApp:
    def __init__(self, console: Console, client: SabClient, interval: float,
                 show_history: bool) -> None:
        self.console = console
        self.client = client
        self.interval = interval
        self.show_history = show_history

        self.speed = SpeedHistory()
        self.selected = 0
        self.slots: List[dict] = []
        self.queue: dict = {}
        self.history: Optional[dict] = None
        self.message = ""
        self.error: Optional[str] = None
        # A pending delete confirmation: (nzo_id, name) or None.
        self.confirm: Optional[tuple[str, str]] = None

    # --- Data ------------------------------------------------------------
    def poll(self) -> None:
        try:
            self.queue = self.client.get_queue()
            self.slots = self.queue.get("slots") or []
            if self.show_history:
                self.history = self.client.get_history(limit=12)
            self.speed.add(to_float(self.queue.get("kbpersec")))
            self.error = None
        except SabError as exc:
            self.error = str(exc)
        self._clamp()

    def _clamp(self) -> None:
        if not self.slots:
            self.selected = 0
        else:
            self.selected = max(0, min(self.selected, len(self.slots) - 1))

    def _current(self) -> Optional[dict]:
        if self.slots and 0 <= self.selected < len(self.slots):
            return self.slots[self.selected]
        return None

    # --- Rendering -------------------------------------------------------
    def _render(self, live: Live) -> None:
        footer = self.message
        if self.confirm is not None:
            footer = f"Delete '{self.confirm[1]}'?  y = yes   n = cancel"
        elif self.error:
            footer = self.error
        live.update(
            build_app_layout(
                self.client.config, self.queue, self.history, self.speed,
                selected=self.selected, message=footer, interactive=True,
                confirm=self.confirm is not None,
            )
        )
        live.refresh()

    # --- Actions ---------------------------------------------------------
    def _act(self, description: str, fn) -> None:
        """Run an API action, capturing errors into the status message."""
        try:
            fn()
            self.message = description
        except SabError as exc:
            self.message = f"Error: {exc}"
        self.poll()

    def _toggle_item(self) -> None:
        slot = self._current()
        if not slot:
            return
        nzo = slot.get("nzo_id")
        if not nzo:
            self.message = "This item has no id; cannot control it."
            return
        name = str(slot.get("filename") or slot.get("name") or nzo)
        if str(slot.get("status", "")).lower() == "paused":
            self._act(f"Resumed '{name}'", lambda: self.client.resume_item(nzo))
        else:
            self._act(f"Paused '{name}'", lambda: self.client.pause_item(nzo))

    def _toggle_all(self) -> None:
        if self.queue.get("paused"):
            self._act("Resumed the queue", self.client.resume)
        else:
            self._act("Paused the queue", self.client.pause)

    def _request_delete(self) -> None:
        slot = self._current()
        if not slot:
            return
        nzo = slot.get("nzo_id")
        if not nzo:
            self.message = "This item has no id; cannot delete it."
            return
        name = str(slot.get("filename") or slot.get("name") or nzo)
        self.confirm = (nzo, name)

    def _do_delete(self) -> None:
        assert self.confirm is not None
        nzo, name = self.confirm
        self.confirm = None
        self._act(f"Deleted '{name}'", lambda: self.client.delete_item(nzo))

    def _prompt_add(self, live: Live, fd: int, old_settings) -> None:
        """Drop out of raw mode to read a path/URL, then add it."""
        live.stop()
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        try:
            target = input("Add .nzb (file path or URL, blank to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            target = ""
        tty.setcbreak(fd)
        live.start(refresh=True)
        if not target:
            self.message = "Add cancelled."
            return
        self._act(f"Added: {target}", lambda: self.client.add(target))

    # --- Main loop -------------------------------------------------------
    def run(self) -> int:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        self.poll()
        try:
            tty.setcbreak(fd)
            with Live(console=self.console, screen=True, auto_refresh=False,
                      transient=True) as live:
                last_poll = time.monotonic()
                while True:
                    self._render(live)
                    key = _read_key(0.15)
                    if key is not None and self._handle(key, live, fd, old_settings):
                        break
                    now = time.monotonic()
                    if now - last_poll >= self.interval:
                        self.poll()
                        last_poll = now
        except KeyboardInterrupt:
            pass
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return 0

    def _handle(self, key: str, live: Live, fd: int, old_settings) -> bool:
        """Handle a keypress. Returns True to quit."""
        # A pending confirmation swallows the next keypress.
        if self.confirm is not None:
            if key in ("y", "Y"):
                self._do_delete()
            else:
                self.confirm = None
                self.message = "Delete cancelled."
            return False

        if key in ("q", "Q"):
            return True
        if key in ("up", "k"):
            self.selected = max(0, self.selected - 1)
        elif key in ("down", "j"):
            self.selected = min(max(0, len(self.slots) - 1), self.selected + 1)
        elif key == "p":
            self._toggle_item()
        elif key == "P" or key == " ":
            self._toggle_all()
        elif key in ("d", "D"):
            self._request_delete()
        elif key in ("a", "A"):
            self._prompt_add(live, fd, old_settings)
        elif key in ("r", "R"):
            self.poll()
            self.message = "Refreshed."
        return False
