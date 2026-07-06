"""Command-line entry point for sabnzb-cli."""

from __future__ import annotations

import argparse
import sys
import time
from typing import List, Optional

from rich.console import Console

from . import __version__
from .client import PRIORITY_MAP, SabClient, SabError
from .config import Config, ConfigError, load_config, write_starter_config
from .dashboard import (
    SpeedHistory,
    build_app_layout,
    render_dashboard,
    render_error,
)
from .format import to_float


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sabnzb-cli",
        description="Interactive command-line dashboard for a SABnzbd instance.",
    )
    parser.add_argument("command", nargs="?",
                        choices=["pause", "resume", "add"],
                        help="One-off action. 'add' uploads .nzb files/URLs; "
                             "'pause'/'resume' control the whole queue.")
    parser.add_argument("targets", nargs="*",
                        help="For 'add': one or more .nzb file paths or URLs.")
    parser.add_argument("-1", "--once", action="store_true",
                        help="Print a single snapshot and exit.")
    parser.add_argument("-i", "--interval", type=float, default=1.0,
                        help="Refresh interval in seconds (default: 1.0).")
    parser.add_argument("-c", "--config", metavar="PATH",
                        help="Path to a config JSON file.")
    parser.add_argument("--no-history", action="store_true",
                        help="Hide the recent-history section.")
    parser.add_argument("--no-interactive", action="store_true",
                        help="Live view without keyboard control.")
    parser.add_argument("--cat", help="Category for 'add'.")
    parser.add_argument("--priority", choices=sorted(PRIORITY_MAP),
                        help="Priority for 'add'.")
    parser.add_argument("--init", action="store_true",
                        help="Write a starter config file and exit.")
    parser.add_argument("--version", action="version",
                        version=f"sabnzb-cli {__version__}")
    return parser


def _fetch(client: SabClient, show_history: bool):
    queue = client.get_queue()
    history = None if not show_history else client.get_history(limit=12)
    return queue, history


def _run_once(console: Console, client: SabClient, show_history: bool) -> int:
    speed_history = SpeedHistory()
    try:
        queue, history = _fetch(client, show_history)
    except SabError as exc:
        console.print(render_error(str(exc)))
        return 1
    speed_history.add(to_float(queue.get("kbpersec")))
    console.print(render_dashboard(client.config, queue, history, speed_history))
    return 0


def _run_plain_live(console: Console, client: SabClient, interval: float,
                    show_history: bool) -> int:
    from rich.live import Live

    speed_history = SpeedHistory()
    with Live(console=console, screen=True, auto_refresh=False,
              transient=True) as live:
        while True:
            try:
                queue, history = _fetch(client, show_history)
                speed_history.add(to_float(queue.get("kbpersec")))
                live.update(build_app_layout(client.config, queue, history,
                                             speed_history, interactive=False))
            except SabError as exc:
                live.update(render_error(str(exc)))
            live.refresh()
            time.sleep(max(0.1, interval))


def _cmd_add(console: Console, client: SabClient, targets: List[str],
             cat: Optional[str], priority: Optional[str]) -> int:
    if not targets:
        console.print(render_error("Nothing to add. Usage: "
                                   "sabnzb-cli add <file.nzb|URL> ..."))
        return 1
    failures = 0
    for target in targets:
        try:
            client.add(target, cat=cat, priority=priority)
            console.print(f"[green]Added:[/green] {target}")
        except SabError as exc:
            console.print(render_error(f"Failed to add {target}: {exc}"))
            failures += 1
    return 1 if failures else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    console = Console()

    if args.init:
        try:
            path = write_starter_config()
        except ConfigError as exc:
            console.print(render_error(str(exc)))
            return 1
        console.print(f"[green]Wrote starter config to[/green] {path}")
        console.print("Edit it with your SABnzbd host and API key, then run "
                      "[bold]sabnzb-cli[/bold].")
        return 0

    try:
        config: Config = load_config(args.config)
    except ConfigError as exc:
        console.print(render_error(str(exc)))
        return 1

    client = SabClient(config)

    if args.command == "add":
        return _cmd_add(console, client, args.targets, args.cat, args.priority)

    if args.command in ("pause", "resume"):
        try:
            getattr(client, args.command)()
        except SabError as exc:
            console.print(render_error(str(exc)))
            return 1
        console.print(f"[green]Queue {args.command}d.[/green]")
        return 0

    show_history = not args.no_history

    try:
        if args.once:
            return _run_once(console, client, show_history)
        # Interactive keyboard control needs a real terminal on both ends.
        interactive = (not args.no_interactive
                       and sys.stdin.isatty() and sys.stdout.isatty())
        if interactive:
            from .interactive import InteractiveApp

            return InteractiveApp(console, client, args.interval,
                                  show_history).run()
        return _run_plain_live(console, client, args.interval, show_history)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
