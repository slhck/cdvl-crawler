"""
Tests for cdvl_crawler.utils module
"""

import json
import os
from unittest.mock import patch

import pytest

from cdvl_crawler.utils import (
    load_config,
    load_jsonl,
    parse_id_list,
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


class TestParseIdList:
    """Tests for parse_id_list()"""

    def test_single_and_ranges(self):
        assert parse_id_list("5, 1,10-12") == [1, 5, 10, 11, 12]

    def test_removes_duplicates(self):
        assert parse_id_list("3,3,2-4") == [2, 3, 4]

    @pytest.mark.parametrize("text", ["", "abc", "0", "5-3", "1,,x"])
    def test_invalid(self, text):
        with pytest.raises(ValueError):
            parse_id_list(text)


class TestLoadJsonl:
    """Tests for load_jsonl()"""

    def test_missing_file(self, temp_dir):
        assert load_jsonl(temp_dir / "missing.jsonl") == []

    def test_skips_invalid_lines(self, temp_dir):
        path = temp_dir / "data.jsonl"
        path.write_text('{"id": 1}\nnot json\n\n{"id": 2}\n')
        assert [r["id"] for r in load_jsonl(path)] == [1, 2]
