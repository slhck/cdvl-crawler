"""
Shared utilities for CDVL crawler and downloader
"""

import getpass
import json
import logging
import os
import re
from typing import Any, Dict, Optional, Tuple
from urllib.parse import unquote

import aiohttp
from bs4 import BeautifulSoup
from yarl import URL

logger = logging.getLogger(__name__)


def get_default_config() -> Dict[str, Any]:
    """Get default configuration with hardcoded sensible values"""
    return {
        "endpoints": {
            "video_base_url": "https://www.cdvl.org/members-section/view-file/",
            "dataset_base_url": "https://www.cdvl.org/members-section/search",
        },
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        },
        "output": {
            "videos_file": "videos.jsonl",
            "datasets_file": "datasets.jsonl",
        },
        "start_video_id": 1,
        "start_dataset_id": 1,
        "max_concurrent_requests": 5,
        "max_consecutive_failures": 10,
        "request_delay": 0.1,
    }


def load_config(config_path: Optional[str]) -> Dict[str, Any]:
    """Load configuration from JSON file (optional)

    If no config file is provided, returns default config with hardcoded values.
    Config file values override defaults.
    """
    # Start with defaults
    config = get_default_config()

    if not config_path:
        return config

    try:
        with open(config_path, "r") as f:
            user_config = json.load(f)
        logger.info(f"Loaded configuration from {config_path}")

        # Deep merge: user config overrides defaults
        # For nested dicts like endpoints and headers, merge individually
        for key, value in user_config.items():
            if key in config and isinstance(config[key], dict) and isinstance(value, dict):
                config[key].update(value)
            else:
                config[key] = value

        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        logger.error(
            "Use environment variables CDVL_USERNAME and CDVL_PASSWORD or create config.json based on config.example.json"
        )
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in config file: {e}")
        raise


def get_credentials(config: Dict[str, Any]) -> Tuple[str, str]:
    """
    Get credentials from config, environment variables, or user prompt

    Priority:
    1. Config file (username/password keys)
    2. Environment variables (CDVL_USERNAME, CDVL_PASSWORD)
    3. Interactive user prompt

    Args:
        config: Configuration dictionary (may not contain credentials)

    Returns:
        Tuple of (username, password)
    """
    username = config.get("username", "")
    password = config.get("password", "")

    # Try environment variables if not in config
    if not username:
        username = os.environ.get("CDVL_USERNAME", "")
        if username:
            logger.info("Using username from CDVL_USERNAME environment variable")

    if not password:
        password = os.environ.get("CDVL_PASSWORD", "")
        if password:
            logger.info("Using password from CDVL_PASSWORD environment variable")

    # Prompt user if still missing
    if not username:
        logger.info("No credentials found in config or environment variables")
        username = input("Enter CDVL username (email): ").strip()

    if not password:
        password = getpass.getpass("Enter CDVL password: ").strip()

    if not username or not password:
        raise ValueError("Username and password are required")

    return username, password


def get_headers(config: Dict[str, Any]) -> Dict[str, str]:
    """Get request headers from config"""
    return config.get("headers", {})


async def create_session(
    config: Dict[str, Any], timeout_seconds: int = 30
) -> aiohttp.ClientSession:
    """Create an aiohttp session with configured headers and timeout"""
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    return aiohttp.ClientSession(headers=get_headers(config), timeout=timeout)


async def login_to_cdvl(
    session: aiohttp.ClientSession, username: str, password: str
) -> bool:
    """
    Perform login to CDVL and establish session

    Args:
        session: Active aiohttp ClientSession
        username: CDVL username
        password: CDVL password

    Returns:
        True if login successful, False otherwise
    """
    login_url = "https://www.cdvl.org/login"

    if not username or not password:
        logger.error("Username and password required")
        return False

    try:
        logger.info("Fetching login page to get CSRF tokens...")

        # First, get the login page to extract tokens
        async with session.get(login_url) as response:
            if response.status != 200:
                logger.error(f"Failed to fetch login page: HTTP {response.status}")
                return False

            html = await response.text()
            soup = BeautifulSoup(html, "lxml")

            # Extract the __RequestVerificationToken
            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            if not token_input:
                logger.error("Could not find __RequestVerificationToken on login page")
                return False

            verification_token = token_input.get("value")

            # Extract ufprt token (fingerprint token)
            ufprt_input = soup.find("input", {"name": "ufprt"})
            ufprt_token = ufprt_input.get("value") if ufprt_input else ""

            logger.info("Extracted CSRF tokens successfully")

        # Prepare login form data
        form_data = aiohttp.FormData()
        form_data.add_field("loginModel.RedirectUrl", "/members-section/")
        form_data.add_field("loginModel.Username", username)
        form_data.add_field("loginModel.Password", password)
        form_data.add_field("__RequestVerificationToken", verification_token)
        if ufprt_token:
            form_data.add_field("ufprt", ufprt_token)

        logger.info(f"Logging in as {username}...")

        # Submit login form
        async with session.post(
            login_url, data=form_data, allow_redirects=True
        ) as response:
            # Check if login was successful
            # Successful login typically redirects to /members-section/
            final_url = str(response.url)

            if response.status == 200 and "members-section" in final_url:
                logger.info("✓ Login successful!")

                # Verify we have session cookies
                cookies = session.cookie_jar.filter_cookies(
                    URL("https://www.cdvl.org")
                )
                if ".AspNetCore.Identity.Application" in [
                    c.key for c in cookies.values()
                ]:
                    logger.info("✓ Session cookies established")
                    return True
                else:
                    logger.warning(
                        "Login appeared successful but no session cookie found"
                    )
                    return False
            else:
                logger.error(f"Login failed: HTTP {response.status}, URL: {final_url}")
                # Try to extract error message
                html = await response.text()
                soup = BeautifulSoup(html, "lxml")
                error_div = soup.find("div", {"class": "alert-danger"})
                if error_div:
                    logger.error(f"Error message: {error_div.get_text(strip=True)}")
                return False

    except Exception as e:
        logger.error(f"Login error: {e}")
        return False


def parse_content_disposition(content_disp: str) -> Optional[str]:
    """
    Parse filename from Content-Disposition header

    Args:
        content_disp: Content-Disposition header value

    Returns:
        Extracted filename or None if not found
    """
    if not content_disp:
        return None

    # Try to find filename*= (RFC 5987 encoding)
    if "filename*=" in content_disp:
        # Format: filename*=UTF-8''filename.ext
        match = re.search(
            r"filename\*=(?:UTF-8''|[^']*'[^']*')(.+)", content_disp, re.IGNORECASE
        )
        if match:
            filename = unquote(match.group(1))
            return filename.strip("\"'")

    # Try to find filename= (standard)
    if "filename=" in content_disp:
        match = re.search(r'filename="?([^";\n]+)"?', content_disp, re.IGNORECASE)
        if match:
            filename = match.group(1)
            return unquote(filename.strip("\"'"))

    return None
