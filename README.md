# CDVL Crawler

[![PyPI version](https://img.shields.io/pypi/v/cdvl-crawler.svg)](https://pypi.org/project/cdvl-crawler)

Python tools for crawling and downloading videos from the [CDVL](https://cdvl.org) (Consumer Digital Video Library) research video repository.

**Contents:**

- [What This Does](#what-this-does)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Crawling Metadata](#crawling-metadata)
  - [Downloading Videos](#downloading-videos)
- [Output Format](#output-format)
  - [Video Records](#video-records)
  - [Dataset Records](#dataset-records)
- [Configuration File (`config.json`)](#configuration-file-configjson)
  - [Configuration Options](#configuration-options)
- [API](#api)
- [Privacy \& Ethics](#privacy--ethics)
- [License](#license)

## What This Does

This package provides a unified command-line tool for working with CDVL:

**`cdvl-crawler`** with two subcommands:

- **`crawl`** - Crawls and extracts metadata from all videos and datasets on CDVL
- **`download`** - Downloads individual videos by their ID

Features:

- **Automatic Login**: Handles authentication automatically with username/password
- **Parallel Crawling**: Concurrent requests for efficient data collection
- **Smart Enumeration**: Automatically discovers videos and datasets by ID
- **Auto-Resume**: Continues from the last crawled ID if interrupted
- **Structured Output**: JSONL format for easy data processing
- **Progress Tracking**: Real-time progress bars showing success/empty/failed counts
- **Download Management**: Handles large file downloads with progress indicators

## Requirements

- Python 3.9 or higher
- An active CDVL account with username and password

## Installation

Install [with `uvx`](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx cdvl-crawler --help
uvx cdvl-crawler crawl --help
uvx cdvl-crawler download --help
```

Or install with `pipx`:

```bash
pipx install cdvl-crawler
```

Or, with pip:

```bash
pip3 install --user cdvl-crawler
```

We assume you will be using `uvx`, otherwise just run `cdvl-crawler` directly without `uvx` after installing from `pipx` or `pip`.

## Usage

Before using the tool, you need to provide your CDVL credentials. The tool supports three methods for providing credentials (in order of priority):

1. **Config file**: Create a `config.json` file in your working directory (automatically detected) or specify with `--config` that contains `username` and `password`
2. **Environment variables**: Set `CDVL_USERNAME` and `CDVL_PASSWORD`
3. **Interactive prompt**: The tool will ask for credentials if not found via other methods

**Note**: If a `config.json` file exists in your current directory, it will be automatically loaded. You don't need to specify `--config` unless you want to use a different file.

Choose the method that best suits your workflow. For example:

```bash
# Using environment variables (no config file needed)
export CDVL_USERNAME="your.email@example.com"
export CDVL_PASSWORD="your_password"
uvx cdvl-crawler crawl

# Using config.json (automatically detected if in current directory)
# Just create config.json:
# {
#   "username": "your.email@example.com",
#   "password": "your_password_here"
# }

# and run:
uvx cdvl-crawler crawl
```

### Crawling Metadata

To crawl all videos and datasets:

```bash
# Basic usage (outputs to current directory)
uvx cdvl-crawler crawl

# Save to specific directory
uvx cdvl-crawler crawl --output-dir ./data
```

**Available options:**

- `--output-dir DIR` - Directory to save output files (default: current directory)
- `--start-video-id N` - Starting video ID for crawling (default: 1 or resume from last)
- `--start-dataset-id N` - Starting dataset ID for crawling (default: 1 or resume from last)
- `--max-concurrent N` - Maximum number of concurrent requests (default: 5)
- `--max-failures N` - Stop after N consecutive empty/failed responses (default: 10)
- `--delay SECONDS` - Delay between request batches in seconds (default: 0.1)

The crawler will automatically:

1. Log in with your credentials (from config, env vars, or prompt)
2. Crawl videos and datasets in parallel
3. Save metadata to `videos.jsonl` and `datasets.jsonl` in the output directory
4. Resume from the last ID if run again

Example output:

```
2025-10-09 15:30:03 - INFO - ✓ Login successful!
2025-10-09 15:30:03 - INFO - Starting crawlers in parallel...
Videos:   12543 | Success: 8432 | Empty: 3891 | Failed: 220
Datasets:   142 | Success:   98 | Empty:   34 | Failed:  10
```

To start fresh, delete the output files before running:

```bash
rm ./data/videos.jsonl ./data/datasets.jsonl
uvx cdvl-crawler crawl --output-dir ./data
```

To resume, just run it again - it will automatically continue from where it left off.

### Downloading Videos

Download videos by their ID:

```bash
# Download a single video (to current directory)
uvx cdvl-crawler download 42

# Download to specific directory
uvx cdvl-crawler download 42 --output-dir ./downloads

# Download multiple videos (comma-separated)
uvx cdvl-crawler download 1,5,10,20 --output-dir ./videos

# Get download URL without downloading
uvx cdvl-crawler download 42 --dry-run

# Download to specific filename (single video only)
uvx cdvl-crawler download 42 --output my_video.avi
```

For more options:

```bash
uvx cdvl-crawler download --help
```

## Output Format

Output files use JSON Lines format (one JSON object per line).

### Video Records

```json
{
  "id": 5,
  "url": "https://www.cdvl.org/members-section/view-file/?videoid=5",
  "title": "Introduction to Video Quality",
  "text": "Full text content...",
  "paragraphs": ["Paragraph 1...", "Paragraph 2..."],
  "links": [{"text": "Download", "href": "/path/to/file"}],
  "media": [{"type": "video", "src": "/path/to/video.mp4"}],
  "html": "<div>Raw HTML...</div>",
  "extracted_at": "2025-10-09T15:30:00+00:00",
  "content_type": "video"
}
```

### Dataset Records

```json
{
  "id": 7,
  "url": "https://www.cdvl.org/members-section/search?dataset=7",
  "title": "Mobile Quality Dataset",
  "text": "Full text content...",
  "paragraphs": ["Description..."],
  "links": [{"text": "Download", "href": "/download/dataset7.zip"}],
  "tables_count": 2,
  "html": "<div>Raw HTML...</div>",
  "extracted_at": "2025-10-09T15:30:00+00:00",
  "content_type": "dataset"
}
```

Here are some processing examples using `jq`.

Count records:

```bash
wc -l videos.jsonl datasets.jsonl
```

View first record:

```bash
head -n 1 videos.jsonl | jq .
```

Extract all titles:

```bash
jq -r '.title' videos.jsonl
```

Filter by keyword:

```bash
jq 'select(.text | contains("codec"))' videos.jsonl
```

Convert to CSV:

```bash
jq -r '[.id, .title, .url] | @csv' videos.jsonl > videos.csv
```

## Configuration File (`config.json`)

Configuration is **optional**. The tool has sensible defaults built-in, and you can use:

- Environment variables for authentication (see [Usage](#usage) above)
- Command-line options for crawling parameters (see `--help`)
- Interactive prompts if credentials are not found

**Auto-detection**: If a file named `config.json` exists in your current directory, it will be automatically loaded. You can override this with `--config path/to/other.json`.

If you want to customize settings permanently or override defaults, create a `config.json` file:

1. Download `config.example.json` from the repository
2. Rename it to `config.json`
3. Edit `config.json` with your settings:

```json
{
  "username": "your.email@example.com",
  "password": "your_password_here",
  "endpoints": {
    "video_base_url": "https://www.cdvl.org/members-section/view-file/",
    "dataset_base_url": "https://www.cdvl.org/members-section/search"
  },
  "output": {
    "videos_file": "videos.jsonl",
    "datasets_file": "datasets.jsonl"
  },
  "start_video_id": 1,
  "start_dataset_id": 1,
  "max_concurrent_requests": 5,
  "max_consecutive_failures": 10,
  "request_delay": 0.1
}
```

### Configuration Options

All settings are optional with sensible defaults. CLI options override config file values.

| Setting                    | Default                              | CLI Option            | Description                              |
| -------------------------- | ------------------------------------ | --------------------- | ---------------------------------------- |
| `username`                 | (from env `CDVL_USERNAME` or prompt) | -                     | Your CDVL account email                  |
| `password`                 | (from env `CDVL_PASSWORD` or prompt) | -                     | Your CDVL account password               |
| `start_video_id`           | 1                                    | `--start-video-id`    | Starting video ID for crawling           |
| `start_dataset_id`         | 1                                    | `--start-dataset-id`  | Starting dataset ID for crawling         |
| `max_concurrent_requests`  | 5                                    | `--max-concurrent`    | Number of parallel requests              |
| `max_consecutive_failures` | 10                                   | `--max-failures`      | Stop after N consecutive empty responses |
| `request_delay`            | 0.1                                  | `--delay`             | Delay between request batches (seconds)  |
| `videos_file`              | videos.jsonl                         | -                     | Output filename for video metadata       |
| `datasets_file`            | datasets.jsonl                       | -                     | Output filename for dataset metadata     |
| `endpoints.video_base_url` | cdvl.org members section             | -                     | Base URL for video pages                 |
| `endpoints.dataset_base_url` | cdvl.org members section           | -                     | Base URL for dataset pages               |
| `headers`                  | Browser-like headers                 | -                     | HTTP headers (User-Agent, Accept, etc.)  |

## API

You can also use the package programmatically:

```python
import asyncio
from cdvl_crawler import CDVLCrawler, CDVLDownloader

# Crawl videos and datasets
async def crawl():
    # Config file is optional - will use env vars or prompt
    crawler = CDVLCrawler(config_path=None, output_dir="./data")
    await crawler.crawl()

# Download a specific video
async def download():
    # Config file is optional - will use env vars or prompt
    downloader = CDVLDownloader(config_path=None, output_dir="./downloads")
    await downloader._init_session()
    await downloader._login()

    url = await downloader.get_download_link(42)
    if url:
        await downloader.download_file(url, "output.avi")

    await downloader._close_session()

# Run
asyncio.run(crawl())
asyncio.run(download())
```

## Privacy & Ethics

- **Rate Limiting**: Use reasonable delays to avoid server strain (default: 0.1s between batches)
- **Credentials**: Keep your `config.json` secure and never share credentials
- **Usage Policies**: Respect CDVL's terms of service and usage policies
- **Personal Use**: Only use your own account credentials

## License

The MIT License (MIT)

Copyright (c) 2025 Werner Robitza

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
