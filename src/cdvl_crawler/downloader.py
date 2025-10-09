"""
CDVL Video Downloader
Downloads individual videos from cdvl.org by ID or comma-separated IDs
"""

import logging
from pathlib import Path
from typing import Optional

import aiohttp
from bs4 import BeautifulSoup
from tqdm import tqdm

from cdvl_crawler.utils import (
    create_session,
    get_credentials,
    load_config,
    login_to_cdvl,
    parse_content_disposition,
)

logger = logging.getLogger(__name__)


class CDVLDownloader:
    """Download individual videos from CDVL"""

    def __init__(
        self, config_path: Optional[str] = None, output_dir: str = "."
    ):
        """Initialize downloader with configuration"""
        self.config = load_config(config_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.session: Optional[aiohttp.ClientSession] = None

    async def _init_session(self):
        """Initialize aiohttp session"""
        if self.session is None:
            self.session = await create_session(self.config, timeout_seconds=300)

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

    async def get_download_link(self, video_id: int) -> Optional[str]:
        """Get the download link for a video by submitting the form"""
        if self.session is None:
            logger.error("Session not initialized")
            return None

        # Use video_base_url from config (supports custom endpoints)
        video_url = f"{self.config['endpoints']['video_base_url']}?videoid={video_id}"

        try:
            logger.info(f"Fetching video page for ID {video_id}...")

            # Get the video page to extract form tokens
            async with self.session.get(video_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to fetch video page: HTTP {response.status}")
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                # Find the download manager form
                # Look for form with "generate a download manager link" button
                forms = soup.find_all("form")
                target_form = None

                for form in forms:
                    # Type ignore needed for BeautifulSoup's find method with lambda
                    button = form.find(  # type: ignore[call-overload]
                        "button",
                        string=lambda text: text
                        and "download manager link" in text.lower(),
                    )
                    if button:
                        target_form = form
                        break

                if not target_form:
                    logger.error("Could not find download manager form")
                    return None

                # Extract form data
                video_id_input = target_form.find("input", {"name": "videoId"})
                dist_type_input = target_form.find(
                    "input", {"name": "distributionType"}
                )
                token_input = target_form.find(
                    "input", {"name": "__RequestVerificationToken"}
                )
                ufprt_input = target_form.find("input", {"name": "ufprt"})

                if not video_id_input or not token_input:
                    logger.error("Missing required form fields")
                    return None

                video_id_value = video_id_input.get("value")
                dist_type_value = (
                    dist_type_input.get("value", "") if dist_type_input else ""
                )
                verification_token = token_input.get("value")
                ufprt_token = ufprt_input.get("value") if ufprt_input else ""

                logger.info("Generating download link...")

            # Submit the form to generate download link
            form_data = aiohttp.FormData()
            form_data.add_field("videoId", video_id_value)
            form_data.add_field("distributionType", dist_type_value)
            form_data.add_field("__RequestVerificationToken", verification_token)
            if ufprt_token:
                form_data.add_field("ufprt", ufprt_token)

            async with self.session.post(
                video_url, data=form_data, allow_redirects=True
            ) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to generate download link: HTTP {response.status}"
                    )
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, "lxml")

                # Find the download table
                download_table = soup.find("table", {"class": "downloadTable"})
                if not download_table:
                    logger.error("Download table not found in response")
                    return None

                # Extract the download URL (from "Other" row)
                rows = download_table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2 and "Other" in cells[0].get_text():
                        download_url = cells[1].get_text(strip=True)
                        logger.info(f"✓ Download link generated: {download_url}")
                        return download_url

                # Fallback: try to find any GetFileDownload URL
                for row in rows:
                    cells = row.find_all("td")
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if "GetFileDownload" in text:
                            # Extract URL from wget/curl command if needed
                            parts = text.split()
                            for part in parts:
                                if "GetFileDownload" in part:
                                    logger.info(f"✓ Download link generated: {part}")
                                    return part

                logger.error("Could not extract download URL from table")
                return None

        except Exception as e:
            logger.error(f"Error getting download link: {e}")
            return None

    async def download_file(self, url: str, output_path: Optional[str] = None) -> bool:
        """Download a file from URL"""
        if self.session is None:
            logger.error("Session not initialized")
            return False

        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"Download failed: HTTP {response.status}")
                    return False

                # Determine filename
                filename: str
                if output_path:
                    # If output_path is an absolute path, use it as-is
                    # Otherwise, join with output_dir
                    output_path_obj = Path(output_path)
                    if output_path_obj.is_absolute():
                        filename = output_path
                    else:
                        filename = str(self.output_dir / output_path)
                else:
                    # Try to get filename from Content-Disposition header
                    content_disp = response.headers.get("Content-Disposition", "")
                    parsed_filename = parse_content_disposition(content_disp)

                    if parsed_filename:
                        filename = str(self.output_dir / parsed_filename)
                    else:
                        # Fallback: Extract from URL (use UUID part)
                        url_parts = url.rstrip("/").split("/")
                        if len(url_parts) >= 3:
                            video_id = url_parts[-3]
                            filename = str(
                                self.output_dir / f"cdvl_video_{video_id}.bin"
                            )
                        else:
                            filename = str(
                                self.output_dir / "cdvl_video_unknown.bin"
                            )

                    logger.info(f"Filename: {filename}")

                # Get total size if available
                total_size_str = response.headers.get("Content-Length")
                total_size: Optional[int] = None
                if total_size_str:
                    total_size = int(total_size_str)
                    logger.info(
                        f"Downloading {filename} ({total_size / 1024 / 1024:.2f} MB)..."
                    )
                else:
                    logger.info(f"Downloading {filename}...")

                # Download with progress bar
                chunk_size = 1024 * 1024  # 1 MB chunks

                with open(filename, "wb") as f:
                    with tqdm(
                        total=total_size,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=filename,
                        disable=not total_size,  # Disable if size unknown
                    ) as pbar:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            f.write(chunk)
                            if total_size:
                                pbar.update(len(chunk))

                logger.info(f"✓ Downloaded to: {filename}")
                return True

        except Exception as e:
            logger.error(f"Download error: {e}")
            return False
