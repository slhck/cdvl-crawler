"""
Pytest fixtures for cdvl-crawler tests
"""

import json
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_video_data():
    """Sample video data for testing"""
    return {
        "id": 42,
        "url": "https://www.cdvl.org/members-section/view-file/42",
        "title": "Test Video",
        "paragraphs": ["This is a test video description."],
        "filename": "test_video.mp4",
        "file_size": "100 MB",
        "links": [{"text": "Related", "href": "/related"}],
        "media": [{"type": "video", "src": "/video.mp4"}],
        "extracted_at": "2024-01-01T00:00:00",
        "content_type": "video",
    }


@pytest.fixture
def sample_videos_jsonl(temp_dir, sample_video_data):
    """Create a sample videos.jsonl file"""
    jsonl_path = temp_dir / "videos.jsonl"
    with open(jsonl_path, "w") as f:
        f.write(json.dumps(sample_video_data) + "\n")
        # Add a second video
        video2 = sample_video_data.copy()
        video2["id"] = 43
        video2["title"] = "Another Video"
        f.write(json.dumps(video2) + "\n")
    return jsonl_path


@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "username": "test@example.com",
        "password": "testpass",
        "endpoints": {
            "video_base_url": "https://www.cdvl.org/members-section/view-file/",
            "dataset_base_url": "https://www.cdvl.org/members-section/search",
        },
        "headers": {
            "User-Agent": "Test Agent",
        },
        "max_concurrent_requests": 5,
    }


@pytest.fixture
def config_file(temp_dir, sample_config):
    """Create a sample config.json file"""
    config_path = temp_dir / "config.json"
    with open(config_path, "w") as f:
        json.dump(sample_config, f)
    return config_path
