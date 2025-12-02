#!/usr/bin/env python3
"""
CLI entry point for CDVL Crawler
"""

import argparse
import asyncio
import logging
import os
import sys

from cdvl_crawler.crawler import CDVLCrawler
from cdvl_crawler.downloader import CDVLDownloader
from cdvl_crawler.exporter import CDVLExporter
from cdvl_crawler.generator import CDVLSiteGenerator
from cdvl_crawler.utils import require_license_acceptance

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for CDVL CLI"""
    parser = argparse.ArgumentParser(
        prog="cdvl-crawler",
        description="Tools for crawling and downloading videos from CDVL",
        formatter_class=argparse.RawDescriptionHelpFormatter,
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
    subparsers.required = True

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

  # Download multiple videos (comma-separated)
  cdvl-crawler download 1,5,10,20

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
        help="Video ID(s) to download (comma-separated for multiple)",
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

    # If no config specified, check if config.json exists in current directory
    if args.config is None and os.path.exists("config.json"):
        args.config = "config.json"
        logger.info("Found config.json in current directory")

    # Run the appropriate command
    if args.command == "crawl":
        asyncio.run(run_crawler(args))
    elif args.command == "download":
        asyncio.run(run_downloader(args))
    elif args.command == "generate-site":
        run_generator(args)
    elif args.command == "export":
        run_exporter(args)


async def run_crawler(args):
    """Run the crawler"""
    # Check license acceptance
    if not require_license_acceptance(auto_accept=args.accept_license):
        logger.error("License agreement not accepted. Exiting.")
        sys.exit(1)

    # Build overrides dict from CLI arguments
    overrides = {}
    if args.start_video_id is not None:
        overrides["start_video_id"] = args.start_video_id
    if args.start_dataset_id is not None:
        overrides["start_dataset_id"] = args.start_dataset_id
    if args.max_concurrent is not None:
        overrides["max_concurrent_requests"] = args.max_concurrent
    if args.max_failures is not None:
        overrides["max_consecutive_failures"] = args.max_failures
    if args.delay is not None:
        overrides["request_delay"] = args.delay
    if args.probe_step is not None:
        overrides["probe_step"] = args.probe_step
    if args.max_probe_attempts is not None:
        overrides["max_probe_attempts"] = args.max_probe_attempts
    if args.max_video_id is not None:
        overrides["max_video_id"] = args.max_video_id
    if args.max_dataset_id is not None:
        overrides["max_dataset_id"] = args.max_dataset_id

    crawler = CDVLCrawler(
        config_path=args.config, output_dir=args.output_dir, overrides=overrides
    )
    await crawler.crawl()


async def run_downloader(args):
    """Run the downloader with parsed arguments"""
    # Check license acceptance
    if not require_license_acceptance(auto_accept=args.accept_license):
        logger.error("License agreement not accepted. Exiting.")
        sys.exit(1)

    # Parse video IDs
    try:
        video_ids = [int(id.strip()) for id in args.video_ids.split(",")]
        if not all(vid > 0 for vid in video_ids):
            logger.error("Video IDs must be positive integers")
            sys.exit(1)
    except ValueError:
        logger.error(
            "Invalid video ID format. Use comma-separated integers (e.g., 1,5,10)"
        )
        sys.exit(1)

    # Validate output parameter
    if args.output and len(video_ids) > 1:
        logger.error("--output can only be used with a single video ID")
        sys.exit(1)

    # Download all selected videos
    downloader = CDVLDownloader(config_path=args.config, output_dir=args.output_dir)
    await downloader._init_session()

    try:
        # Login once for all downloads
        if not await downloader._login():
            logger.error("Login failed. Exiting.")
            sys.exit(1)

        print(f"\nDownloading {len(video_ids)} video(s)...\n")

        success_count = 0
        for i, video_id in enumerate(video_ids, 1):
            print(f"\n[{i}/{len(video_ids)}] Processing video ID {video_id}...")

            # Get download link
            download_url = await downloader.get_download_link(video_id)
            if not download_url:
                logger.error(f"Failed to get download link for video {video_id}")
                continue

            if args.dry_run:
                # Just print the URL
                print(f"Video {video_id}: {download_url}")
                success_count += 1
            else:
                # Download the file
                success = await downloader.download_file(
                    download_url,
                    output_path=args.output if len(video_ids) == 1 else None,
                    video_id=video_id,
                    enable_resume=not args.no_resume,
                )
                if success:
                    success_count += 1

        print(f"\n✓ Successfully processed {success_count}/{len(video_ids)} video(s)")
        sys.exit(0 if success_count == len(video_ids) else 1)

    finally:
        await downloader._close_session()


def run_generator(args):
    """Run the static site generator"""
    generator = CDVLSiteGenerator(input_file=args.input, output_file=args.output)

    if generator.generate():
        print(f"\n✓ Static site generated successfully: {args.output}")
        print("  Open the file in your browser to view the video library")
        sys.exit(0)
    else:
        logger.error("Failed to generate static site")
        sys.exit(1)


def run_exporter(args):
    """Run the CSV exporter"""
    # Parse columns if provided
    columns = None
    if args.columns:
        columns = [col.strip() for col in args.columns.split(",")]

    exporter = CDVLExporter(
        input_file=args.input, output_file=args.output, columns=columns
    )

    if exporter.export():
        print(f"\n✓ Export successful: {args.output}")
        sys.exit(0)
    else:
        logger.error("Failed to export data")
        sys.exit(1)


if __name__ == "__main__":
    main()
