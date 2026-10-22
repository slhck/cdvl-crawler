"""
Command implementations shared by the CLI and the interactive mode
"""

import logging
from typing import Any, Dict, Optional

from cdvl_crawler.crawler import CDVLCrawler
from cdvl_crawler.downloader import CDVLDownloader
from cdvl_crawler.exporter import CDVLExporter
from cdvl_crawler.generator import CDVLSiteGenerator
from cdvl_crawler.ui import console, error, info, success

logger = logging.getLogger(__name__)


async def crawl(
    config_path: Optional[str],
    output_dir: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> bool:
    """Crawl metadata of all videos and datasets"""
    crawler = CDVLCrawler(
        config_path=config_path, output_dir=output_dir, overrides=overrides
    )
    return await crawler.crawl()


async def download(
    config_path: Optional[str],
    output_dir: str,
    video_ids: list[int],
    output: Optional[str] = None,
    dry_run: bool = False,
    resume: bool = True,
) -> bool:
    """Download videos by ID

    Returns:
        True if all videos were processed successfully
    """
    downloader = CDVLDownloader(config_path=config_path, output_dir=output_dir)
    await downloader._init_session()

    try:
        if not await downloader._login():
            error("Login failed")
            return False

        failed: list[int] = []
        for i, video_id in enumerate(video_ids, 1):
            console.rule(
                f"[accent]Video {video_id}[/accent] [muted]({i}/{len(video_ids)})[/muted]",
                style="magenta",
            )

            with console.status("[info]Generating download link...[/info]"):
                download_url = await downloader.get_download_link(video_id)
            if not download_url:
                error(f"Failed to get download link for video {video_id}")
                failed.append(video_id)
                continue

            if dry_run:
                console.print(f"[bold]{video_id}[/bold]: [cyan]{download_url}[/cyan]")
                continue

            if not await downloader.download_file(
                download_url,
                output_path=output if len(video_ids) == 1 else None,
                video_id=video_id,
                enable_resume=resume,
            ):
                failed.append(video_id)

        console.print()
        done = len(video_ids) - len(failed)
        if failed:
            error(
                f"Processed {done}/{len(video_ids)} video(s); failed: "
                + ", ".join(str(v) for v in failed)
            )
            return False
        success(f"Processed {done}/{len(video_ids)} video(s)")
        return True

    finally:
        await downloader._close_session()


def generate_site(input_file: str, output_file: str) -> bool:
    """Generate the static HTML site from video metadata"""
    with console.status("[info]Generating site...[/info]"):
        ok = CDVLSiteGenerator(
            input_file=input_file, output_file=output_file
        ).generate()
    if ok:
        success(f"Static site generated: [cyan]{output_file}[/cyan]")
        info("Open the file in your browser to view the video library")
    else:
        error("Failed to generate static site")
    return ok


def export(input_file: str, output_file: str, columns: Optional[list[str]]) -> bool:
    """Export JSONL metadata to CSV"""
    ok = CDVLExporter(
        input_file=input_file, output_file=output_file, columns=columns
    ).export()
    if ok:
        success(f"Export successful: [cyan]{output_file}[/cyan]")
    else:
        error("Failed to export data")
    return ok
