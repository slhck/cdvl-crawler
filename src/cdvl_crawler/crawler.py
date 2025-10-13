"""
CDVL Research Video Crawler
Crawls videos and datasets from cdvl.org with authentication
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Literal, Optional, cast

import aiohttp
from bs4 import BeautifulSoup
from tqdm import tqdm

from cdvl_crawler.types import (
    DatasetData,
    LinkDict,
    MediaDict,
    PartialContentData,
    VideoData,
)
from cdvl_crawler.utils import (
    create_session,
    get_credentials,
    load_config,
    login_to_cdvl,
)

logger = logging.getLogger(__name__)


class CDVLCrawler:
    """Crawler for CDVL videos and datasets"""

    def __init__(
        self,
        config_path: Optional[str] = None,
        output_dir: str = ".",
        overrides: Optional[Dict[str, Any]] = None,
    ):
        """Initialize crawler with configuration

        Args:
            config_path: Optional path to config file
            output_dir: Directory for output files (default: current directory)
            overrides: Dict of config values to override (e.g., from CLI args)
        """
        self.config = load_config(config_path)
        # Apply overrides from CLI args
        if overrides:
            self.config.update(overrides)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[aiohttp.ClientSession] = None
        self.video_lock = Lock()
        self.dataset_lock = Lock()

        # Progress bars
        self.video_pbar: Optional[tqdm] = None
        self.dataset_pbar: Optional[tqdm] = None

        # Statistics
        self.stats = {
            "videos": {"success": 0, "failed": 0, "empty": 0},
            "datasets": {"success": 0, "failed": 0, "empty": 0},
        }

    async def _init_session(self):
        """Initialize aiohttp session"""
        if self.session is None:
            self.session = await create_session(self.config, timeout_seconds=30)

    async def _close_session(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def _login(self) -> bool:
        """Perform login to CDVL and establish session"""
        try:
            username, password = get_credentials(self.config)
        except ValueError as e:
            logger.error(f"Credential error: {e}")
            return False

        if self.session is None:
            logger.error("Session not initialized")
            return False

        return await login_to_cdvl(self.session, username, password)

    def _parse_content(
        self, html: str, content_type: Literal["video", "dataset"]
    ) -> Optional[PartialContentData]:
        """Parse HTML content and extract structured data"""
        try:
            soup = BeautifulSoup(html, "lxml")

            # Find the main content div
            selector = "body > div.main-container.container-fluid > div > div"
            content_div = soup.select_one(selector)

            if not content_div:
                logger.debug(f"No content found for selector: {selector}")
                return None

            # Check if content is empty or minimal
            text_content = content_div.get_text(strip=True)
            if not text_content or len(text_content) < 10:
                return None

            # Filter out error pages
            if (
                "Something went wrong" in text_content
                or "Please go back and" in text_content
            ):
                return None

            # Extract all paragraphs (required field)
            paragraphs = [
                p.get_text(strip=True)
                for p in content_div.find_all("p")
                if p.get_text(strip=True)
            ]

            # Return None if no paragraphs found (no useful content)
            if not paragraphs:
                return None

            # Extract structured data
            data: PartialContentData = {
                "paragraphs": paragraphs,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
                "content_type": content_type,
            }

            # Try to extract more specific fields
            # Title - find first non-empty header
            title_text = ""
            for header in content_div.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                title_text = header.get_text(strip=True)
                if title_text:  # Skip empty headers
                    break
            if title_text:
                data["title"] = title_text

            # All links
            links: list[LinkDict] = []
            for a in content_div.find_all("a", href=True):
                href = a["href"]
                # BeautifulSoup can return str or list, ensure we get a string
                href_str = href if isinstance(href, str) else " ".join(href)
                link: LinkDict = {"text": a.get_text(strip=True), "href": href_str}
                links.append(link)
            if links:
                data["links"] = links

            # Tables (if any)
            tables = content_div.find_all("table")
            if tables:
                data["tables_count"] = len(tables)

            # Images/videos
            media: list[MediaDict] = []
            for tag in content_div.find_all(["img", "video", "source"]):
                src = tag.get("src")
                if src:
                    # BeautifulSoup can return str or list, ensure we get a string
                    src_str = src if isinstance(src, str) else " ".join(src)
                    media_item: MediaDict = {"type": tag.name, "src": src_str}
                    media.append(media_item)
            if media:
                data["media"] = media

            # File size - look for "Size of upload video:" pattern
            for p in content_div.find_all("p"):
                strong = p.find("strong")
                if strong and "Size of upload video:" in strong.get_text():
                    # Extract text after the strong tag
                    size_text = p.get_text(strip=True)
                    # Remove the "Size of upload video:" prefix
                    size_text = size_text.replace("Size of upload video:", "").strip()
                    if size_text:
                        data["file_size"] = size_text
                    break

            # Filename - look for download button
            for button in content_div.find_all("button", class_="btn"):
                button_text = button.get_text(strip=True)
                if button_text.startswith("Download "):
                    filename = button_text.replace("Download ", "").strip()
                    if filename:
                        data["filename"] = filename
                    break

            return data

        except Exception as e:
            logger.error(f"Error parsing content: {e}")
            return None

    def _get_last_id_from_jsonl(self, filepath: str) -> int:
        """Get the last ID from a JSONL file"""
        try:
            if not Path(filepath).exists():
                return 0

            last_id = 0
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        if "id" in data:
                            last_id = max(last_id, data["id"])
                    except json.JSONDecodeError:
                        continue

            return last_id
        except Exception as e:
            logger.warning(f"Error reading last ID from {filepath}: {e}")
            return 0

    def _append_to_jsonl(self, filepath: str, data: Dict[str, Any], lock: Lock):
        """Append data to JSONL file atomically"""
        try:
            with lock:
                with open(filepath, "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Error writing to {filepath}: {e}")

    async def _fetch_video(self, video_id: int) -> Optional[VideoData]:
        """Fetch a single video by ID"""
        if self.session is None:
            logger.error("Session not initialized")
            return None

        url = f"{self.config['endpoints']['video_base_url']}?videoid={video_id}"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.debug(f"Video {video_id}: HTTP {response.status}")
                    return None

                html = await response.text()
                partial_data = self._parse_content(html, "video")

                if partial_data:
                    # Convert to dict, add id and url, then cast to VideoData
                    complete_data = dict(partial_data)
                    complete_data["id"] = video_id
                    complete_data["url"] = url
                    return cast(VideoData, complete_data)
                else:
                    return None

        except asyncio.TimeoutError:
            logger.warning(f"Video {video_id}: Timeout")
            return None
        except Exception as e:
            logger.error(f"Video {video_id}: Error - {e}")
            return None

    async def _fetch_dataset(self, dataset_id: int) -> Optional[DatasetData]:
        """Fetch a single dataset by ID"""
        if self.session is None:
            logger.error("Session not initialized")
            return None

        url = f"{self.config['endpoints']['dataset_base_url']}?dataset={dataset_id}"

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.debug(f"Dataset {dataset_id}: HTTP {response.status}")
                    return None

                html = await response.text()
                partial_data = self._parse_content(html, "dataset")

                if partial_data:
                    # Convert to dict, add id and url, then cast to DatasetData
                    complete_data = dict(partial_data)
                    complete_data["id"] = dataset_id
                    complete_data["url"] = url
                    return cast(DatasetData, complete_data)
                else:
                    return None

        except asyncio.TimeoutError:
            logger.warning(f"Dataset {dataset_id}: Timeout")
            return None
        except Exception as e:
            logger.error(f"Dataset {dataset_id}: Error - {e}")
            return None

    async def _crawl_videos(self, start_id: int = 1, max_concurrent: int = 5):
        """Crawl all videos with parallel requests and sequential scanning"""
        logger.info("Starting video crawler...")
        output_file = str(self.output_dir / self.config["output"]["videos_file"])
        consecutive_failures = 0
        max_failures = self.config.get("max_consecutive_failures", 1000)
        max_video_id = self.config.get("max_video_id")

        current_id = start_id
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create progress bar
        self.video_pbar = tqdm(
            desc="Videos", unit="video", position=0, leave=True, dynamic_ncols=True
        )

        async def fetch_with_semaphore(vid_id):
            async with semaphore:
                return await self._fetch_video(vid_id)

        try:
            while True:
                # Check if we've hit the consecutive failures limit
                if consecutive_failures >= max_failures:
                    logger.info(
                        f"No videos found after {consecutive_failures} consecutive attempts. Stopping."
                    )
                    break

                # Determine batch size, respecting max_video_id if set
                batch_size = max_concurrent
                if max_video_id is not None:
                    # Don't go beyond max_video_id
                    if current_id > max_video_id:
                        logger.info(f"Reached max_video_id limit: {max_video_id}")
                        break
                    # Adjust batch size if we're near the limit
                    batch_size = min(batch_size, max_video_id - current_id + 1)

                # Fetch batch
                tasks = [
                    fetch_with_semaphore(current_id + i) for i in range(batch_size)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, (Exception, BaseException)):
                        self.stats["videos"]["failed"] += 1
                        consecutive_failures += 1
                    elif result is None:
                        self.stats["videos"]["empty"] += 1
                        consecutive_failures += 1
                    elif isinstance(result, dict):
                        # Success!
                        self._append_to_jsonl(output_file, result, self.video_lock)
                        self.stats["videos"]["success"] += 1
                        consecutive_failures = 0  # Reset on success
                    else:
                        # Unexpected result type
                        self.stats["videos"]["failed"] += 1
                        consecutive_failures += 1

                    # Update progress bar
                    self.video_pbar.update(1)
                    self.video_pbar.set_postfix(
                        success=self.stats["videos"]["success"],
                        empty=self.stats["videos"]["empty"],
                        failed=self.stats["videos"]["failed"],
                    )

                current_id += batch_size

                # Add small delay to be respectful
                await asyncio.sleep(self.config.get("request_delay", 0.1))

        finally:
            if self.video_pbar is not None:
                self.video_pbar.close()

    async def _crawl_datasets(self, start_id: int = 1, max_concurrent: int = 5):
        """Crawl all datasets with parallel requests and sequential scanning"""
        logger.info("Starting dataset crawler...")
        output_file = str(self.output_dir / self.config["output"]["datasets_file"])
        consecutive_failures = 0
        max_failures = self.config.get("max_consecutive_failures", 1000)
        max_dataset_id = self.config.get("max_dataset_id")

        current_id = start_id
        semaphore = asyncio.Semaphore(max_concurrent)

        # Create progress bar
        self.dataset_pbar = tqdm(
            desc="Datasets", unit="dataset", position=1, leave=True, dynamic_ncols=True
        )

        async def fetch_with_semaphore(ds_id):
            async with semaphore:
                return await self._fetch_dataset(ds_id)

        try:
            while True:
                # Check if we've hit the consecutive failures limit
                if consecutive_failures >= max_failures:
                    logger.info(
                        f"No datasets found after {consecutive_failures} consecutive attempts. Stopping."
                    )
                    break

                # Determine batch size, respecting max_dataset_id if set
                batch_size = max_concurrent
                if max_dataset_id is not None:
                    # Don't go beyond max_dataset_id
                    if current_id > max_dataset_id:
                        logger.info(f"Reached max_dataset_id limit: {max_dataset_id}")
                        break
                    # Adjust batch size if we're near the limit
                    batch_size = min(batch_size, max_dataset_id - current_id + 1)

                # Fetch batch
                tasks = [
                    fetch_with_semaphore(current_id + i) for i in range(batch_size)
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Process results
                for i, result in enumerate(results):
                    if isinstance(result, (Exception, BaseException)):
                        self.stats["datasets"]["failed"] += 1
                        consecutive_failures += 1
                    elif result is None:
                        self.stats["datasets"]["empty"] += 1
                        consecutive_failures += 1
                    elif isinstance(result, dict):
                        # Success!
                        self._append_to_jsonl(output_file, result, self.dataset_lock)
                        self.stats["datasets"]["success"] += 1
                        consecutive_failures = 0  # Reset on success
                    else:
                        # Unexpected result type
                        self.stats["datasets"]["failed"] += 1
                        consecutive_failures += 1

                    # Update progress bar
                    self.dataset_pbar.update(1)
                    self.dataset_pbar.set_postfix(
                        success=self.stats["datasets"]["success"],
                        empty=self.stats["datasets"]["empty"],
                        failed=self.stats["datasets"]["failed"],
                    )

                current_id += batch_size

                # Add small delay to be respectful
                await asyncio.sleep(self.config.get("request_delay", 0.1))

        finally:
            if self.dataset_pbar is not None:
                self.dataset_pbar.close()

    async def crawl(self):
        """Main crawl function - runs both crawlers in parallel"""
        await self._init_session()

        try:
            # Perform login first
            if not await self._login():
                logger.error("Login failed. Exiting.")
                return

            # Create output files if they don't exist
            videos_file = str(self.output_dir / self.config["output"]["videos_file"])
            datasets_file = str(
                self.output_dir / self.config["output"]["datasets_file"]
            )
            Path(videos_file).touch()
            Path(datasets_file).touch()

            # Determine starting IDs (resume from last crawled ID)

            last_video_id = self._get_last_id_from_jsonl(videos_file)
            last_dataset_id = self._get_last_id_from_jsonl(datasets_file)

            # Start from last ID + 1, or use config default
            start_video_id = max(
                last_video_id + 1, self.config.get("start_video_id", 1)
            )
            start_dataset_id = max(
                last_dataset_id + 1, self.config.get("start_dataset_id", 1)
            )

            if last_video_id > 0:
                logger.info(
                    f"Resuming video crawl from ID {start_video_id} (last: {last_video_id})"
                )
            if last_dataset_id > 0:
                logger.info(
                    f"Resuming dataset crawl from ID {start_dataset_id} (last: {last_dataset_id})"
                )

            max_concurrent = self.config.get("max_concurrent_requests", 5)

            logger.info("Starting crawlers in parallel...")
            await asyncio.gather(
                self._crawl_videos(start_video_id, max_concurrent),
                self._crawl_datasets(start_dataset_id, max_concurrent),
            )

            logger.info("\n" + "=" * 60)
            logger.info("CRAWL COMPLETE")
            logger.info("=" * 60)
            logger.info(
                f"Videos: {self.stats['videos']['success']} successful, "
                f"{self.stats['videos']['empty']} empty, "
                f"{self.stats['videos']['failed']} failed"
            )
            logger.info(
                f"Datasets: {self.stats['datasets']['success']} successful, "
                f"{self.stats['datasets']['empty']} empty, "
                f"{self.stats['datasets']['failed']} failed"
            )
            logger.info("\nOutput files:")
            logger.info(f"  - {videos_file}")
            logger.info(f"  - {datasets_file}")

        finally:
            await self._close_session()
