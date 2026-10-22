#!/usr/bin/env python3
"""
CLI entry point for CDVL Crawler
"""

import argparse
import asyncio
import importlib.metadata
import logging
import os
import sys

from cdvl_crawler import commands
from cdvl_crawler.ui import console, error, setup_logging
from cdvl_crawler.utils import parse_id_list, require_license_acceptance

logger = logging.getLogger(__name__)

VERSION = importlib.metadata.version("cdvl_crawler")


def main():
    """Main entry point for CDVL CLI"""
    parser = argparse.ArgumentParser(
        prog="cdvl-crawler",
        description="Tools for crawling and downloading videos from CDVL. "
        "Run without a command to start the interactive menu.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show debug output"
    )

    # Add config argument at top level
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        help="Path to config file (optional if using environment variables)",
    )

    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Crawl command
    crawl_parser = subparsers.add_parser(
        "crawl",
        help="Crawl and extract metadata from all videos and datasets",
        description="Systematically crawls and extracts metadata from all videos and datasets on CDVL",
    )
    crawl_parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save output files (default: current directory)",
    )
    crawl_parser.add_argument(
        "--start-video-id",
        type=int,
        help="Starting video ID for crawling (default: 1 or resume from last)",
    )
    crawl_parser.add_argument(
        "--start-dataset-id",
        type=int,
        help="Starting dataset ID for crawling (default: 1 or resume from last)",
    )
    crawl_parser.add_argument(
        "--max-concurrent",
        type=int,
        help="Maximum number of concurrent requests (default: 5)",
    )
    crawl_parser.add_argument(
        "--max-failures",
        type=int,
        help="Stop after N consecutive empty/failed responses (default: 1000)",
    )
    crawl_parser.add_argument(
        "--delay",
        type=float,
        help="Delay between request batches in seconds (default: 0.1)",
    )
    crawl_parser.add_argument(
        "--probe-step",
        type=int,
        help="How far ahead to jump when probing for ID gaps (default: 100)",
    )
    crawl_parser.add_argument(
        "--max-probe-attempts",
        type=int,
        help="Max probe attempts before giving up (default: 20, meaning 20*100=2000 ID range)",
    )
    crawl_parser.add_argument(
        "--max-video-id",
        type=int,
        help="Maximum video ID to crawl to (optional, no limit by default)",
    )
    crawl_parser.add_argument(
        "--max-dataset-id",
        type=int,
        help="Maximum dataset ID to crawl to (optional, no limit by default)",
    )
    crawl_parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Automatically accept the CDVL license agreement without prompting",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download",
        help="Download videos by ID",
        description="Download individual videos from CDVL by their ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download single video
  cdvl-crawler download 42

  # Download multiple videos (comma-separated, ranges allowed)
  cdvl-crawler download 1,5,10-20

  # Get download URL without downloading
  cdvl-crawler download 42 --dry-run

  # Download to specific file (single video only)
  cdvl-crawler download 42 --output myvideo.avi

  # Download with custom config
  cdvl-crawler download 42 --config myconfig.json
        """,
    )
    download_parser.add_argument(
        "video_ids",
        type=str,
        help="Video ID(s) to download (comma-separated, ranges allowed, e.g. 1,5,10-12)",
    )
    download_parser.add_argument(
        "--dry-run", action="store_true", help="Print download URL without downloading"
    )
    download_parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output filename (default: auto-detect from server, only works with single video)",
    )
    download_parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save downloaded files (default: current directory)",
    )
    download_parser.add_argument(
        "--accept-license",
        action="store_true",
        help="Automatically accept the CDVL license agreement without prompting",
    )
    download_parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Disable resume capability (always download from beginning)",
    )

    # Generate site command
    site_parser = subparsers.add_parser(
        "generate-site",
        help="Generate a static HTML site from videos.jsonl",
        description="Generate a searchable, sortable HTML table of all videos",
    )
    site_parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="videos.jsonl",
        help="Input JSONL file (default: videos.jsonl)",
    )
    site_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="index.html",
        help="Output HTML file (default: index.html)",
    )

    # Export command
    export_parser = subparsers.add_parser(
        "export",
        help="Export JSONL data to CSV format",
        description="Convert JSONL metadata files to CSV format for use in spreadsheets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Export all columns (default)
  cdvl-crawler export -i videos.jsonl -o videos.csv

  # Export specific columns
  cdvl-crawler export -i videos.jsonl -o videos.csv --columns id,title,filename

  # Export datasets
  cdvl-crawler export -i datasets.jsonl -o datasets.csv --columns id,title,url
        """,
    )
    export_parser.add_argument(
        "-i",
        "--input",
        type=str,
        default="videos.jsonl",
        help="Input JSONL file (default: videos.jsonl)",
    )
    export_parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="videos.csv",
        help="Output CSV file (default: videos.csv)",
    )
    export_parser.add_argument(
        "--columns",
        type=str,
        help="Comma-separated list of columns to export (default: all columns)",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    # If no config specified, check if config.json exists in current directory
    if args.config is None and os.path.exists("config.json"):
        args.config = "config.json"
        logger.debug("Found config.json in current directory")

    try:
        if args.command is None:
            if not sys.stdin.isatty():
                parser.print_help()
                sys.exit(2)
            from cdvl_crawler.interactive import run_interactive

            sys.exit(run_interactive(args.config, VERSION))
        elif args.command == "crawl":
            ok = asyncio.run(run_crawler(args))
        elif args.command == "download":
            ok = asyncio.run(run_downloader(args))
        elif args.command == "generate-site":
            ok = commands.generate_site(args.input, args.output)
        else:
            columns = (
                [col.strip() for col in args.columns.split(",")]
                if args.columns
                else None
            )
            ok = commands.export(args.input, args.output, columns)
    except KeyboardInterrupt:
        console.print()
        error("Interrupted")
        sys.exit(130)

    sys.exit(0 if ok else 1)


def check_license(accept: bool) -> None:
    """Exit unless the license agreement is accepted"""
    if not require_license_acceptance(auto_accept=accept):
        error("License agreement not accepted. Exiting.")
        sys.exit(1)


async def run_crawler(args) -> bool:
    """Run the crawler"""
    check_license(args.accept_license)

    # Map CLI arguments to config keys
    option_keys = {
        "start_video_id": "start_video_id",
        "start_dataset_id": "start_dataset_id",
        "max_concurrent": "max_concurrent_requests",
        "max_failures": "max_consecutive_failures",
        "delay": "request_delay",
        "probe_step": "probe_step",
        "max_probe_attempts": "max_probe_attempts",
        "max_video_id": "max_video_id",
        "max_dataset_id": "max_dataset_id",
    }
    overrides = {
        key: getattr(args, arg)
        for arg, key in option_keys.items()
        if getattr(args, arg) is not None
    }

    return await commands.crawl(args.config, args.output_dir, overrides)


async def run_downloader(args) -> bool:
    """Run the downloader with parsed arguments"""
    check_license(args.accept_license)

    try:
        video_ids = parse_id_list(args.video_ids)
    except ValueError:
        error("Invalid video IDs. Use positive integers and ranges (e.g., 1,5,10-12)")
        sys.exit(1)

    if args.output and len(video_ids) > 1:
        error("--output can only be used with a single video ID")
        sys.exit(1)

    return await commands.download(
        args.config,
        args.output_dir,
        video_ids,
        output=args.output,
        dry_run=args.dry_run,
        resume=not args.no_resume,
    )


if __name__ == "__main__":
    main()
