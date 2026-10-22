"""
Interactive menu mode, started when the CLI runs without a subcommand
"""

import asyncio
import os
import webbrowser
from pathlib import Path
from typing import Any, Dict, Optional

import questionary
from rich.table import Table

from cdvl_crawler import commands
from cdvl_crawler.exporter import CDVLExporter
from cdvl_crawler.ui import console, error, info, print_banner, warning
from cdvl_crawler.utils import (
    load_config,
    load_jsonl,
    parse_id_list,
    require_license_acceptance,
)

STYLE = questionary.Style(
    [
        ("qmark", "fg:#d670d6 bold"),
        ("question", "bold"),
        ("pointer", "fg:#d670d6 bold"),
        ("highlighted", "fg:#d670d6 bold"),
        ("selected", "fg:#5fd75f"),
        ("answer", "fg:#5fafff bold"),
        ("instruction", "fg:#808080"),
    ]
)

# Maximum number of search results offered for selection
MAX_SEARCH_RESULTS = 50

CRAWL = "Crawl metadata of videos and datasets"
DOWNLOAD = "Download videos"
SITE = "Generate a searchable HTML site"
EXPORT = "Export metadata to CSV"
STATUS = "Show status"
QUIT = "Quit"


class Cancelled(Exception):
    """Raised when the user aborts a prompt (for example, with Ctrl+C)"""


def ask(question: Any) -> Any:
    """Ask a questionary question and raise Cancelled if the user aborts"""
    answer = question.ask()
    if answer is None:
        raise Cancelled
    return answer


def ask_text(message: str, default: str = "", **kwargs: Any) -> str:
    return ask(questionary.text(message, default=default, style=STYLE, **kwargs))


def ask_path(message: str, default: str) -> str:
    return ask(questionary.path(message, default=default, style=STYLE))


def ask_confirm(message: str, default: bool = True) -> bool:
    return ask(questionary.confirm(message, default=default, style=STYLE))


def ask_int(message: str, default: Optional[int] = None) -> Optional[int]:
    """Ask for a positive integer; an empty answer returns None"""

    def validate(text: str) -> bool | str:
        if not text.strip() or (text.strip().isdigit() and int(text) > 0):
            return True
        return "Enter a positive number or leave empty"

    answer = ask_text(
        message, default="" if default is None else str(default), validate=validate
    )
    return int(answer) if answer.strip() else None


def describe_jsonl(path: Path) -> str:
    """Summarize a JSONL file as record count and last ID"""
    records = load_jsonl(path)
    if not records:
        return "[muted]not found[/muted]"
    last_id = max(r.get("id", 0) for r in records)
    return f"[green]{len(records)}[/green] records, last ID [cyan]{last_id}[/cyan]"


class InteractiveSession:
    """Menu-driven session that runs commands until the user quits"""

    def __init__(self, config_path: Optional[str], version: str):
        self.config_path = config_path
        self.version = version
        self.config: Dict[str, Any] = load_config(config_path)
        self.license_accepted = False
        self.output_dir = "."

    def run(self) -> int:
        print_banner(self.version)
        self.show_status()

        actions = {
            CRAWL: self.crawl,
            DOWNLOAD: self.download,
            SITE: self.generate_site,
            EXPORT: self.export,
            STATUS: self.show_status,
        }

        while True:
            console.print()
            try:
                choice = ask(
                    questionary.select(
                        "What would you like to do?",
                        choices=[*actions, questionary.Separator(), QUIT],
                        style=STYLE,
                    )
                )
            except Cancelled:
                choice = QUIT
            if choice == QUIT:
                console.print("[muted]Bye![/muted]")
                return 0

            try:
                actions[choice]()
            except Cancelled:
                warning("Cancelled")
            except KeyboardInterrupt:
                console.print()
                warning("Interrupted")

    def show_status(self) -> None:
        """Print where credentials come from and what has been crawled so far"""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()

        table.add_row(
            "Config file",
            f"[cyan]{self.config_path}[/cyan]"
            if self.config_path
            else "[muted]none (using defaults)[/muted]",
        )
        if self.config.get("username"):
            credentials = f"[green]{self.config['username']}[/green] (config file)"
        elif os.environ.get("CDVL_USERNAME"):
            credentials = f"[green]{os.environ['CDVL_USERNAME']}[/green] (environment)"
        else:
            credentials = "[yellow]will be asked on login[/yellow]"
        table.add_row("Credentials", credentials)

        output = Path(self.output_dir)
        for label, key in (("Videos", "videos_file"), ("Datasets", "datasets_file")):
            filename = self.config["output"][key]
            table.add_row(
                label,
                f"{describe_jsonl(output / filename)} [muted]({filename})[/muted]",
            )

        console.print(table)

    def ensure_license(self) -> bool:
        """Ask for license acceptance once per session"""
        if not self.license_accepted:
            self.license_accepted = require_license_acceptance()
            if not self.license_accepted:
                error("The license must be accepted to access CDVL content")
        return self.license_accepted

    def crawl(self) -> None:
        if not self.ensure_license():
            return

        self.output_dir = ask_path("Output directory:", self.output_dir)
        overrides: Dict[str, Any] = {}

        if ask_confirm("Customize crawl settings?", default=False):
            concurrent = ask_int(
                "Concurrent requests:", self.config["max_concurrent_requests"]
            )
            if concurrent:
                overrides["max_concurrent_requests"] = concurrent
            overrides["request_delay"] = float(
                ask_text(
                    "Delay between batches (seconds):",
                    str(self.config["request_delay"]),
                    validate=lambda t: _is_float(t) or "Enter a number",
                )
            )
            max_failures = ask_int(
                "Stop after this many consecutive misses:",
                self.config["max_consecutive_failures"],
            )
            if max_failures:
                overrides["max_consecutive_failures"] = max_failures
            overrides["max_video_id"] = ask_int(
                "Maximum video ID (empty for no limit):", self.config["max_video_id"]
            )
            overrides["max_dataset_id"] = ask_int(
                "Maximum dataset ID (empty for no limit):",
                self.config["max_dataset_id"],
            )

        info("Already crawled IDs are skipped, so a stopped crawl can be resumed.")
        asyncio.run(commands.crawl(self.config_path, self.output_dir, overrides))

    def download(self) -> None:
        videos_file = Path(self.output_dir) / self.config["output"]["videos_file"]
        records = load_jsonl(videos_file)

        how = "Enter video IDs"
        if records:
            how = ask(
                questionary.select(
                    "How do you want to choose videos?",
                    choices=["Search crawled metadata", "Enter video IDs"],
                    style=STYLE,
                )
            )

        if how == "Search crawled metadata":
            video_ids = self.search_videos(records)
        else:
            text = ask_text(
                "Video IDs (for example 42 or 1,5,10-12):",
                validate=_validate_ids,
            )
            video_ids = parse_id_list(text)

        if not video_ids:
            warning("No videos selected")
            return

        target_dir = ask_path("Download directory:", self.output_dir)
        resume = ask_confirm("Resume partial downloads?", default=True)

        if not self.ensure_license():
            return
        asyncio.run(
            commands.download(self.config_path, target_dir, video_ids, resume=resume)
        )

    def search_videos(self, records: list[Dict[str, Any]]) -> list[int]:
        """Search crawled videos by title, filename or description and pick some"""
        while True:
            query = ask_text("Search (title, filename or description):").lower()
            matches = [
                r
                for r in records
                if query
                in " ".join(
                    [
                        r.get("title", ""),
                        r.get("filename", ""),
                        *r.get("paragraphs", []),
                    ]
                ).lower()
            ]
            if matches:
                break
            warning(f"No videos match '{query}'")

        if len(matches) > MAX_SEARCH_RESULTS:
            warning(
                f"{len(matches)} matches, showing the first {MAX_SEARCH_RESULTS}. "
                "Refine the search to see more."
            )
            matches = matches[:MAX_SEARCH_RESULTS]

        choices = [
            questionary.Choice(
                title=f"{r['id']:>5}  {r.get('title', '(untitled)')}"
                + (f"  ({r['file_size']})" if r.get("file_size") else ""),
                value=r["id"],
            )
            for r in matches
        ]
        return ask(
            questionary.checkbox(
                "Select videos to download:",
                choices=choices,
                style=STYLE,
                instruction="(space to select, enter to confirm)",
            )
        )

    def generate_site(self) -> None:
        default_input = str(
            Path(self.output_dir) / self.config["output"]["videos_file"]
        )
        input_file = ask_path("Input JSONL file:", default_input)
        output_file = ask_path("Output HTML file:", "index.html")

        if commands.generate_site(input_file, output_file) and ask_confirm(
            "Open in browser?", default=True
        ):
            webbrowser.open(Path(output_file).resolve().as_uri())

    def export(self) -> None:
        default_input = str(
            Path(self.output_dir) / self.config["output"]["videos_file"]
        )
        input_file = ask_path("Input JSONL file:", default_input)
        records = load_jsonl(input_file)
        if not records:
            error(f"No records found in {input_file}")
            return

        output_file = ask_path(
            "Output CSV file:", str(Path(input_file).with_suffix(".csv"))
        )

        columns = CDVLExporter(input_file, output_file)._get_all_columns(records)
        selected = ask(
            questionary.checkbox(
                "Columns to export:",
                choices=[questionary.Choice(c, checked=True) for c in columns],
                style=STYLE,
                validate=lambda s: bool(s) or "Select at least one column",
            )
        )

        commands.export(
            input_file, output_file, None if len(selected) == len(columns) else selected
        )


def _is_float(text: str) -> bool:
    try:
        return float(text) >= 0
    except ValueError:
        return False


def _validate_ids(text: str) -> bool | str:
    try:
        parse_id_list(text)
        return True
    except ValueError:
        return "Enter IDs like 42, 1,5,10 or 10-20"


def run_interactive(config_path: Optional[str], version: str) -> int:
    """Run the interactive menu and return an exit code"""
    return InteractiveSession(config_path, version).run()
