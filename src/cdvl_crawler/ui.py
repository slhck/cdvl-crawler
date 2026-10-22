"""
Terminal output helpers: shared console, logging, progress bars and messages
"""

import asyncio
import contextlib
import logging
import os
import sys
import threading
from typing import Callable, Iterator

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.theme import Theme

THEME = Theme(
    {
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "muted": "dim",
        "accent": "bold magenta",
    }
)

# Shared console, so that log messages render above live progress bars
console = Console(theme=THEME, highlight=False)


class ConsoleHandler(logging.Handler):
    """Log handler that prints messages with a colored prefix per level"""

    PREFIXES = {
        logging.DEBUG: "[muted]·[/muted]",
        logging.INFO: "[info]›[/info]",
        logging.WARNING: "[warning]![/warning]",
        logging.ERROR: "[error]✗[/error]",
        logging.CRITICAL: "[error]✗[/error]",
    }

    def emit(self, record: logging.LogRecord) -> None:
        try:
            prefix = self.PREFIXES.get(record.levelno, "")
            style = "muted" if record.levelno < logging.INFO else None
            console.print(prefix, escape(self.format(record)), style=style)
        except Exception:
            self.handleError(record)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging to render through the shared rich console"""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[ConsoleHandler()],
        force=True,
    )
    # Keep third-party debug output out of verbose mode
    for name in ("asyncio", "aiohttp", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def print_banner(version: str) -> None:
    """Print the application banner"""
    console.print(
        Panel.fit(
            f"[accent]CDVL Crawler[/accent] [muted]v{version}[/muted]\n"
            "[info]Consumer Digital Video Library[/info] — crawl, download, explore",
            border_style="magenta",
            padding=(1, 4),
        )
    )


def success(message: str) -> None:
    console.print(f"[success]✓[/success] {message}")


def error(message: str) -> None:
    console.print(f"[error]✗[/error] {message}")


def warning(message: str) -> None:
    console.print(f"[warning]![/warning] {message}")


def info(message: str) -> None:
    console.print(f"[info]›[/info] {message}")


def crawl_progress() -> Progress:
    """Create a progress display for crawling (one task per content type)"""
    return Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold]{task.description:<9}"),
        BarColumn(bar_width=30, pulse_style="magenta"),
        TextColumn("ID [cyan]{task.fields[current_id]}[/cyan]"),
        TextColumn(
            "[green]{task.fields[success]} found[/green] "
            "[muted]{task.fields[empty]} empty[/muted] "
            "[red]{task.fields[failed]} failed[/red]"
        ),
        TimeElapsedColumn(),
        console=console,
    )


def download_progress() -> Progress:
    """Create a progress display for file downloads"""
    return Progress(
        SpinnerColumn(style="magenta"),
        TextColumn("[bold]{task.description}", justify="left"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        DownloadColumn(binary_units=True),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    )


@contextlib.contextmanager
def on_keypress(keys: str, callback: Callable[[], None]) -> Iterator[bool]:
    """Call a function when one of the given keys is pressed

    Must be used inside a running event loop. Yields False if stdin is not a
    terminal, in which case no keys are read.
    """
    if not sys.stdin.isatty():
        yield False
        return

    loop = asyncio.get_running_loop()

    if os.name == "nt":
        import msvcrt

        done = threading.Event()

        def poll() -> None:
            while not done.wait(0.1):
                while msvcrt.kbhit():
                    if msvcrt.getwch() in keys:
                        loop.call_soon_threadsafe(callback)

        thread = threading.Thread(target=poll, daemon=True)
        thread.start()
        try:
            yield True
        finally:
            done.set()
            thread.join()
        return

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def on_readable() -> None:
        if os.read(fd, 1).decode(errors="ignore") in keys:
            callback()

    # Read single keys without echo; Ctrl+C still raises KeyboardInterrupt
    tty.setcbreak(fd)
    loop.add_reader(fd, on_readable)
    try:
        yield True
    finally:
        loop.remove_reader(fd)
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
