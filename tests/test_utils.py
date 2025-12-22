"""
Tests for cdvl_crawler.utils module
"""

import json
import os
from unittest.mock import patch

import pytest

from cdvl_crawler.utils import (
    load_config,
    parse_content_disposition,
    get_credentials,
    require_license_acceptance,
)


class TestLoadConfig:
    """Tests for load_config()"""

    def test_returns_defaults_when_no_path(self):
        config = load_config(None)
        assert config["max_concurrent_requests"] == 5
        assert "video_base_url" in config["endpoints"]

    def test_merges_config_with_defaults(self, temp_dir):
        """Config file values merge with defaults, not replace them"""
        config_path = temp_dir / "config.json"
        config_path.write_text('{"headers": {"X-Custom": "value"}}')

        config = load_config(str(config_path))
        assert config["headers"]["X-Custom"] == "value"
        assert "User-Agent" in config["headers"]  # Default preserved

    def test_raises_on_invalid_json(self, temp_dir):
        bad_config = temp_dir / "bad.json"
        bad_config.write_text("{ invalid }")
        with pytest.raises(json.JSONDecodeError):
            load_config(str(bad_config))


class TestParseContentDisposition:
    """Tests for parse_content_disposition()"""

    def test_parses_filename_formats(self):
        # Standard format
        assert parse_content_disposition('filename="video.mp4"') == "video.mp4"
        # Without quotes
        assert parse_content_disposition("filename=video.mp4") == "video.mp4"
        # RFC 5987 encoded
        assert (
            parse_content_disposition("filename*=UTF-8''video%20file.mp4")
            == "video file.mp4"
        )
        # Empty/None
        assert parse_content_disposition("") is None
        assert parse_content_disposition(None) is None


class TestGetCredentials:
    """Tests for get_credentials()"""

    def test_priority_order(self):
        """Config > env vars > prompt"""
        # Config takes priority
        config = {"username": "config@test.com", "password": "configpass"}
        with patch.dict(
            os.environ, {"CDVL_USERNAME": "env@test.com", "CDVL_PASSWORD": "envpass"}
        ):
            username, password = get_credentials(config)
            assert username == "config@test.com"

        # Env vars used when config empty
        with patch.dict(
            os.environ, {"CDVL_USERNAME": "env@test.com", "CDVL_PASSWORD": "envpass"}
        ):
            username, password = get_credentials({})
            assert username == "env@test.com"

    def test_raises_on_empty_credentials(self):
        with patch("builtins.input", return_value=""):
            with patch("getpass.getpass", return_value=""):
                with pytest.raises(ValueError):
                    get_credentials({})


class TestRequireLicenseAcceptance:
    """Tests for require_license_acceptance()"""

    def test_auto_accept(self):
        assert require_license_acceptance(auto_accept=True) is True

    def test_user_response(self):
        with patch("builtins.print"):
            with patch("builtins.input", return_value="yes"):
                assert require_license_acceptance(auto_accept=False) is True
            with patch("builtins.input", return_value="no"):
                assert require_license_acceptance(auto_accept=False) is False
