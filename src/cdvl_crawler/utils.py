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

# CDVL Database Content User License Agreement
CDVL_LICENSE = """
The owner of the CDVL would like you to read and accept the following terms.

================================================================================
DATABASE CONTENT USER CLICK-THROUGH AGREEMENT
(for individuals who use the video clips posted on the website)
================================================================================

Carefully read the following agreement. To use this website and any content
posted or otherwise included thereon, you must accept and agree to be bound by
this agreement.

Unless otherwise indicated by you at the time of acceptance, this agreement
shall be considered legally binding on you as an individual.

Database Content User License:

NTIA/ITS hereby grants permission for you (or your organization) to use the
Consumer Digital Video Library Website ("CDVL Web") and any video clips or
other content posted thereon ("Website Content"), solely for internal research
and development purposes to process and assess audio and/or video quality. You
will not use, copy, reproduce, distribute, modify, prepare derivative works,
transmit, broadcast, display, sell, license or otherwise exploit the Website
Content for any other purpose whatsoever. You shall not distribute any Website
Content to any third party. You agree to destroy any and all copies of Website
Content, if any are made, upon conclusion of the relevant audio or video
processing and/or testing.

NTIA/ITS reserves the right to withdraw permission to use any Website Content
at anytime for any reason.

IN NO EVENT SHALL NTIA/ITS BE LIABLE TO ANY PART FOR DIRECT, INDIRECT, SPECIAL,
INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF THE
USE OF THE WEBSITE OR ANY VIDEO CLIP OR DOCUMENTATION POSTED OR OTHERWISE
INCLUDED THEREON, EVEN IF NTIA/ITS HAS BEEN ADVISED OF THE POSSIBLITY OF SUCH
DAMAGE. NTIA/ITS SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT
LIMTIED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
PARTICULAR PURPOSE. THE WEBSITE CONTENT, INCLUDING ANY VIDEO CLIPS POSTED OR
OTHERWISE INCLUDED THEREON, IS PROVIDED HEREUNDER ON AN "AS-IS" BASIS FOR
INTERNAL USES CONSISTENT WITH THE TERMS OF THIS AGREEMENT.

You agree to defend, indemnify and hold harmless NTIA/ITS and the U.S.
Department of Commerce and their officers, employees and agents from and against
any and all claims, damages, losses, liabilities, costs, and expense (including
but not limited to reasonable attorneys' fees) arising from (1) your violation
of any term of this Agreement; or, (2) your use of the Website Content outside
the scope of this Agreement. This defense and indemnification obligation will
survive the expiration or termination of this Agreement.

You agree that the laws of the United States as interpreted and applied by the
Federal courts in the District of Columbia shall apply to this Agreement,
regardless of the conflict of laws provisions thereof, that this Agreement
constitutes the entire understanding between you and NTIA/ITS with respect to
the Website Content. If any provision of this Agreement is deemed invalid by a
court of competent jurisdiction, the invalidity of such provision shall not
affect the validity of the remaining provisions of this Agreement, which shall
remain in full force and effect. No waiver of any term of this Agreement shall
be deemed a further or continuing waiver of such term or any other term.

You shall use reasonable efforts to acknowledge the CDVL and NTIA/ITS in any
publication that is based upon the use of the CDVL Web.

You agree that this Agreement may be assigned by NTIA/ITS to any third party
who assumes the management of the CDVL Web.

================================================================================
"""


def require_license_acceptance(auto_accept: bool = False) -> bool:
    """
    Display CDVL license agreement and require user acceptance

    Args:
        auto_accept: If True, automatically accept the license without prompting

    Returns:
        True if license was accepted, False otherwise
    """
    if auto_accept:
        logger.info("License automatically accepted via --accept-license flag")
        return True

    print(CDVL_LICENSE)
    print("\nBy using this tool to access CDVL content, you agree to the terms above.")

    while True:
        response = (
            input("\nDo you accept these terms? Type 'yes' or 'no': ").strip().lower()
        )
        if response in ("yes", "y"):
            logger.info("License accepted by user")
            return True
        elif response in ("no", "n"):
            logger.info("License rejected by user")
            return False
        else:
            print("Please answer 'yes' or 'no'")


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
        "max_consecutive_failures": 1000,  # Stop after 1000 consecutive empty/failed responses
        "request_delay": 0.1,
        "max_video_id": None,  # Optional: Stop crawling videos at this ID
        "max_dataset_id": None,  # Optional: Stop crawling datasets at this ID
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
            if (
                key in config
                and isinstance(config[key], dict)
                and isinstance(value, dict)
            ):
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
                cookies = session.cookie_jar.filter_cookies(URL("https://www.cdvl.org"))
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
