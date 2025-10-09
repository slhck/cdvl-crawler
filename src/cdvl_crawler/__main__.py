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
        help="Stop after N consecutive empty/failed responses (default: 10)",
    )
    crawl_parser.add_argument(
        "--delay",
        type=float,
        help="Delay between request batches in seconds (default: 0.1)",
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


async def run_crawler(args):
    """Run the crawler"""
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

    crawler = CDVLCrawler(
        config_path=args.config, output_dir=args.output_dir, overrides=overrides
    )
    await crawler.crawl()


async def run_downloader(args):
    """Run the downloader with parsed arguments"""
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
                    download_url, args.output if len(video_ids) == 1 else None
                )
                if success:
                    success_count += 1

        print(f"\n✓ Successfully processed {success_count}/{len(video_ids)} video(s)")
        sys.exit(0 if success_count == len(video_ids) else 1)

    finally:
        await downloader._close_session()


if __name__ == "__main__":
    main()
