"""
CDVL Video Downloader
Downloads individual videos from cdvl.org by ID or comma-separated IDs
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

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

    def __init__(self, config_path: Optional[str] = None, output_dir: str = "."):
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

    async def _probe_range_support(self, url: str) -> tuple[bool, Optional[int]]:
        """Check if server supports HTTP range requests.

        Uses a GET request with Range header instead of HEAD, since some servers
        (like CDVL) don't support HEAD requests for download URLs.

        Returns:
            Tuple of (supports_ranges, content_length)
        """
        if self.session is None:
            return False, None

        try:
            # Use GET with Range: bytes=0-0 to probe for range support
            # This requests just the first byte, which is efficient
            headers = {"Range": "bytes=0-0"}
            async with self.session.get(url, headers=headers) as response:
                if response.status == 206:
                    # Server supports range requests
                    # Content-Range header format: "bytes 0-0/total_size"
                    content_range = response.headers.get("Content-Range", "")
                    content_length: Optional[int] = None
                    if "/" in content_range:
                        try:
                            total_str = content_range.split("/")[-1]
                            if total_str != "*":
                                content_length = int(total_str)
                        except ValueError:
                            pass

                    logger.debug(
                        f"Range support: True (206), Content-Length: {content_length}"
                    )
                    # Consume the response body to allow connection reuse
                    await response.read()
                    return True, content_length

                elif response.status == 200:
                    # Server ignored the Range header, doesn't support ranges
                    content_length_str = response.headers.get("Content-Length")
                    content_length = (
                        int(content_length_str) if content_length_str else None
                    )
                    logger.debug(
                        f"Range support: False (200), Content-Length: {content_length}"
                    )
                    # Important: we need to NOT consume the full body here
                    # Just close/cancel the response
                    return False, content_length

                else:
                    logger.debug(f"Range probe failed: HTTP {response.status}")
                    return False, None

        except Exception as e:
            logger.debug(f"Range probe error: {e}")
            return False, None

    def _save_partial_metadata(
        self,
        meta_path: Path,
        video_id: int,
        content_length: Optional[int],
        filename: str,
    ) -> None:
        """Save metadata for partial download validation."""
        metadata = {
            "video_id": video_id,
            "content_length": content_length,
            "filename": filename,
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
        meta_path.write_text(json.dumps(metadata, indent=2))

    def _load_partial_metadata(self, meta_path: Path) -> Optional[dict[str, Any]]:
        """Load partial download metadata.

        Returns:
            Metadata dict or None if invalid/missing.
        """
        if not meta_path.exists():
            return None

        try:
            return json.loads(meta_path.read_text())
        except (json.JSONDecodeError, OSError) as e:
            logger.debug(f"Failed to load metadata: {e}")
            return None

    def _validate_partial_file(
        self,
        partial_path: Path,
        meta_path: Path,
        video_id: int,
        expected_length: Optional[int],
    ) -> tuple[bool, int]:
        """Validate if a partial file can be resumed.

        Returns:
            Tuple of (is_valid, partial_size)
        """
        if not partial_path.exists():
            return False, 0

        partial_size = partial_path.stat().st_size
        if partial_size == 0:
            return False, 0

        metadata = self._load_partial_metadata(meta_path)
        if metadata is None:
            logger.debug("No valid metadata found for partial file")
            return False, 0

        # Check video_id matches
        if metadata.get("video_id") != video_id:
            logger.debug(
                f"Video ID mismatch: expected {video_id}, got {metadata.get('video_id')}"
            )
            return False, 0

        # Check partial size is less than expected total
        if expected_length is not None and partial_size >= expected_length:
            logger.debug(
                f"Partial file size ({partial_size}) >= expected ({expected_length})"
            )
            return False, 0

        return True, partial_size

    def _format_bytes(self, size: int) -> str:
        """Format bytes as human-readable string."""
        size_float = float(size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_float < 1024:
                return f"{size_float:.2f} {unit}"
            size_float /= 1024
        return f"{size_float:.2f} PB"

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

    async def download_file(
        self,
        url: str,
        output_path: Optional[str] = None,
        video_id: Optional[int] = None,
        enable_resume: bool = True,
    ) -> bool:
        """Download a file from URL with optional resume support.

        Args:
            url: Download URL
            output_path: Optional output filename (relative to output_dir or absolute)
            video_id: Video ID for partial file validation (required for resume)
            enable_resume: Whether to attempt resuming partial downloads

        Returns:
            True if download completed successfully
        """
        if self.session is None:
            logger.error("Session not initialized")
            return False

        # Probe for range support and get content length
        supports_ranges = False
        expected_length: Optional[int] = None

        if enable_resume and video_id is not None:
            supports_ranges, expected_length = await self._probe_range_support(url)
            if supports_ranges:
                logger.info("Server supports range requests")
            else:
                logger.info("Server does not support range requests")

        try:
            # For resume support, we need to check partial files based on video_id
            # We'll determine the final filename from the GET response's Content-Disposition

            # Check if there's an existing partial file for this video_id
            # We use a video_id-based naming scheme for partial files to enable resume
            # even when we don't know the final filename yet
            partial_by_id: Optional[Path] = None
            meta_by_id: Optional[Path] = None
            resume_from = 0

            if enable_resume and video_id is not None and supports_ranges:
                # Look for partial file based on video_id pattern
                partial_by_id = self.output_dir / f".cdvl_partial_{video_id}.tmp"
                meta_by_id = self.output_dir / f".cdvl_partial_{video_id}.meta"

                is_valid, partial_size = self._validate_partial_file(
                    partial_by_id, meta_by_id, video_id, expected_length
                )
                if is_valid and partial_size > 0:
                    resume_from = partial_size
                    if expected_length:
                        percent = (partial_size / expected_length) * 100
                        logger.info(
                            f"Partial download found ({self._format_bytes(partial_size)} / "
                            f"{self._format_bytes(expected_length)}), resuming from {percent:.1f}%..."
                        )
                    else:
                        logger.info(
                            f"Partial download found ({self._format_bytes(partial_size)}), "
                            "attempting to resume..."
                        )

            # Prepare request headers for range request
            headers: dict[str, str] = {}
            if resume_from > 0:
                headers["Range"] = f"bytes={resume_from}-"

            # Use longer timeout for downloads - no total timeout, but with read timeout
            # to detect stalled connections (300s = 5 min inactivity before timeout)
            download_timeout = aiohttp.ClientTimeout(
                total=None,  # No total timeout - downloads can take hours
                sock_read=300,  # 5 min read timeout to detect stalled connections
            )

            async with self.session.get(
                url, headers=headers, timeout=download_timeout
            ) as response:
                # Check response status
                if resume_from > 0:
                    if response.status == 206:
                        logger.info("Resume accepted by server (206 Partial Content)")
                    elif response.status == 200:
                        # Server ignored range request, start from beginning
                        logger.warning(
                            "Server returned 200 instead of 206, "
                            "restarting download from beginning"
                        )
                        resume_from = 0
                    elif response.status == 416:
                        # Range not satisfiable - partial file is invalid
                        logger.warning(
                            "Range not satisfiable (416), "
                            "restarting download from beginning"
                        )
                        resume_from = 0
                        # Delete invalid partial file
                        if partial_by_id and partial_by_id.exists():
                            partial_by_id.unlink()
                        if meta_by_id and meta_by_id.exists():
                            meta_by_id.unlink()
                        # Retry without range header
                        return await self.download_file(
                            url, output_path, video_id, enable_resume=False
                        )
                    else:
                        logger.error(f"Download failed: HTTP {response.status}")
                        return False
                elif response.status != 200:
                    logger.error(f"Download failed: HTTP {response.status}")
                    return False

                # Get filename from Content-Disposition header (from GET response)
                content_disp = response.headers.get("Content-Disposition", "")
                parsed_filename = parse_content_disposition(content_disp)

                # Determine final filename
                final_path: Path
                if output_path:
                    output_path_obj = Path(output_path)
                    if output_path_obj.is_absolute():
                        final_path = output_path_obj
                    else:
                        final_path = self.output_dir / output_path
                elif parsed_filename:
                    final_path = self.output_dir / parsed_filename
                    logger.info(f"Filename from server: {parsed_filename}")
                else:
                    # Fallback: use video_id if available
                    if video_id is not None:
                        final_path = self.output_dir / f"cdvl_video_{video_id}.bin"
                    else:
                        # Last resort: Extract from URL
                        url_parts = url.rstrip("/").split("/")
                        if len(url_parts) >= 3:
                            url_video_id = url_parts[-3]
                            final_path = (
                                self.output_dir / f"cdvl_video_{url_video_id}.bin"
                            )
                        else:
                            final_path = self.output_dir / "cdvl_video_unknown.bin"

                logger.info(f"Target file: {final_path}")

                # Get content length for this response
                response_length_str = response.headers.get("Content-Length")
                response_length: Optional[int] = None
                if response_length_str:
                    response_length = int(response_length_str)

                # Calculate total size
                total_size = expected_length
                if total_size is None and response_length is not None:
                    total_size = resume_from + response_length

                if total_size:
                    logger.info(f"Total size: {self._format_bytes(total_size)}")

                # Determine which partial file to use
                # If resuming, use the video_id-based partial file
                # Otherwise, create a new one based on video_id or fallback
                if resume_from > 0 and partial_by_id:
                    partial_path = partial_by_id
                    meta_path = meta_by_id
                elif video_id is not None:
                    partial_path = self.output_dir / f".cdvl_partial_{video_id}.tmp"
                    meta_path = self.output_dir / f".cdvl_partial_{video_id}.meta"
                else:
                    partial_path = final_path.with_suffix(
                        final_path.suffix + ".partial"
                    )
                    meta_path = final_path.with_suffix(
                        final_path.suffix + ".partial.meta"
                    )

                # Save metadata for potential future resume
                if video_id is not None and meta_path:
                    self._save_partial_metadata(
                        meta_path, video_id, total_size, final_path.name
                    )

                # Download with progress bar
                chunk_size = 1024 * 1024  # 1 MB chunks
                bytes_written = resume_from

                # Open in append mode if resuming, write mode otherwise
                file_mode = "ab" if resume_from > 0 else "wb"

                with open(partial_path, file_mode) as f:
                    with tqdm(
                        total=total_size,
                        initial=resume_from,
                        unit="B",
                        unit_scale=True,
                        unit_divisor=1024,
                        desc=final_path.name,
                        disable=not total_size,
                    ) as pbar:
                        async for chunk in response.content.iter_chunked(chunk_size):
                            f.write(chunk)
                            bytes_written += len(chunk)
                            if total_size:
                                pbar.update(len(chunk))

            # Verify file size
            final_size = partial_path.stat().st_size
            if total_size is not None:
                if final_size == total_size:
                    logger.info(
                        f"Download complete. Size verified: {self._format_bytes(final_size)}"
                    )
                else:
                    logger.warning(
                        f"Size mismatch: expected {self._format_bytes(total_size)}, "
                        f"got {self._format_bytes(final_size)}"
                    )

            # Rename partial file to final name
            if final_path.exists():
                final_path.unlink()
            partial_path.rename(final_path)

            # Clean up metadata file
            if meta_path and meta_path.exists():
                meta_path.unlink()

            logger.info(f"✓ Downloaded to: {final_path}")
            return True

        except Exception as e:
            # Include exception type in log for better debugging
            # (asyncio.TimeoutError has no message, so type is essential)
            logger.error(f"Download error ({type(e).__name__}): {e}")
            # Keep partial file and metadata for potential resume
            return False
