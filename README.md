# CDVL Crawler

[![PyPI version](https://img.shields.io/pypi/v/cdvl-crawler.svg)](https://pypi.org/project/cdvl-crawler)

Python tools for crawling and downloading videos from the [CDVL](https://cdvl.org) (Consumer Digital Video Library) research video repository.

**Contents:**

- [Disclaimer](#disclaimer)
- [What This Does](#what-this-does)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
  - [Crawling Metadata](#crawling-metadata)
  - [Downloading Videos](#downloading-videos)
  - [Generating Static Site](#generating-static-site)
  - [Exporting to CSV](#exporting-to-csv)
- [Output Format](#output-format)
  - [Video Records](#video-records)
  - [Dataset Records](#dataset-records)
- [Configuration File (`config.json`)](#configuration-file-configjson)
  - [Configuration Options](#configuration-options)
- [API](#api)
- [Development](#development)
- [License](#license)

## Disclaimer

> [!CAUTION]
>
> This software is provided as-is as a general-purpose tool for interacting with the CDVL web content. The author provides this tool solely as software code and has no control over how it is used, no relationship with CDVL, and no obligation to enforce any third-party terms of service or licenses. You, the user, are solely and independently responsible for:
>
> - Obtaining proper authorization to access CDVL
> - Complying with all applicable terms of service, license agreements, and usage policies
> - Understanding and accepting the CDVL Database Content User License Agreement
> - Your own actions and use of any content accessed through this tool
> - Any legal consequences arising from your use of this tool
>
> While this tool displays the CDVL license agreement for user convenience, this does not constitute legal advice, license enforcement, or any guarantee of compliance. Displaying the license is informational only and does not create any legal relationship between the author and CDVL or the user.
> Under no circumstances shall the author be held liable for any direct, indirect, incidental, special, consequential, or exemplary damages arising from your use or misuse of this tool. This includes, but is not limited to, any violation of terms of service, breach of license agreements, unauthorized access, or any other legal issues.
>
> Do not download more content than you would reasonably access manually through a web browser. Only use your own account credentials – never use credentials that do not belong to you. Respect the intellectual property rights and usage restrictions of content providers.
> Specifically, have a look at the [License page](https://www.cdvl.org/license/) before use.
>
> By using this tool, you acknowledge that you have read, understood, and agree to this disclaimer. If you do not agree, do not use this software.

## What This Does

This package provides a unified command-line tool for working with CDVL:

**`cdvl-crawler`** with three subcommands:

- **`crawl`** - Crawls and extracts metadata from all videos and datasets on CDVL
- **`download`** - Downloads individual videos by their ID
- **`generate-site`** - Generates a searchable, interactive HTML site from crawled metadata
- **`export`** - Exports JSONL data to CSV format for use in spreadsheets

Features:

- **Automatic Login**: Handles authentication automatically with username/password
- **Parallel Crawling**: Concurrent requests for efficient data collection
- **Smart Enumeration**: Automatically discovers videos and datasets by ID
- **Auto-Resume**: Continues from the last crawled ID if interrupted
- **Structured Output**: JSONL format for easy data processing
- **Progress Tracking**: Real-time progress bars showing success/empty/failed counts
- **Download Management**: Handles large file downloads with progress indicators
- **Static Site Generator**: Creates a beautiful, searchable HTML interface for browsing videos

## Requirements

- Python 3.9 or higher
- An active CDVL account with username and password

## Installation

Install [with `uvx`](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uvx cdvl-crawler --help
uvx cdvl-crawler crawl --help
uvx cdvl-crawler download --help
uvx cdvl-crawler generate-site --help
uvx cdvl-crawler export --help
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

# Accept license automatically (useful for automation/scripts)
uvx cdvl-crawler crawl --accept-license

# Crawl with custom concurrency and delays
uvx cdvl-crawler crawl --max-concurrent 10 --delay 0.2

# Crawl up to specific ID limits
uvx cdvl-crawler crawl --max-video-id 3000 --max-dataset-id 500

# Adjust failure threshold (stop after N consecutive failures)
uvx cdvl-crawler crawl --max-failures 2000

# Advanced: customize ID gap probing
uvx cdvl-crawler crawl --probe-step 50 --max-probe-attempts 40
```

For more options, run:

```bash
uvx cdvl-crawler crawl --help
```

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

# Accept license automatically (useful for automation/scripts)
uvx cdvl-crawler download 42 --accept-license

# Download multiple videos (comma-separated)
uvx cdvl-crawler download 1,5,10,20 --output-dir ./videos

# Get download URL without downloading
uvx cdvl-crawler download 42 --dry-run

# Download to specific filename (single video only)
uvx cdvl-crawler download 42 --output my_video.avi

# Disable resume capability (always download from beginning)
uvx cdvl-crawler download 42 --no-resume
```

Downloads include automatic file size verification and support for resuming interrupted downloads (if the server supports HTTP range requests).

For more options:

```bash
uvx cdvl-crawler download --help
```

### Generating Static Site

After crawling metadata, you can generate a beautiful, interactive HTML site to browse the video library:

```bash
# Generate site from videos.jsonl to index.html
uvx cdvl-crawler generate-site

# Specify custom input and output files
uvx cdvl-crawler generate-site -i ./data/videos.jsonl -o ./website/index.html
```

For more options:

```bash
uvx cdvl-crawler generate-site --help
```

### Exporting to CSV

After crawling metadata, you can export it to CSV format for use in spreadsheets or data analysis tools:

```bash
# Export all columns (default)
uvx cdvl-crawler export -i videos.jsonl -o videos.csv

# Export specific columns
uvx cdvl-crawler export -i videos.jsonl -o videos.csv --columns id,title,filename

# Export datasets
uvx cdvl-crawler export -i datasets.jsonl -o datasets.csv --columns id,title,url
```

Available columns depend on the data, but typically include: `id`, `url`, `title`, `content_type`, `filename`, `file_size`, `paragraphs`, `links`, `media`, `tables_count`, `extracted_at`.

For more options:

```bash
uvx cdvl-crawler export --help
```

## Output Format

Output files use JSON Lines format (one JSON object per line).

### Video Records

```json
{
  "id": 5,
  "url": "https://www.cdvl.org/members-section/view-file/?videoid=5",
  "paragraphs": [
    "Description:Pan over a children's ball pit, seen from above using a crane.",
    "Dataset:NTIA Source Scenes",
    "Audio Specifications:16-bit stereo PCM. Talk in English with balls rustling.",
    "Video Specification:The camera was a professional HDTV camera..."
  ],
  "extracted_at": "2025-10-09T15:30:00+00:00",
  "content_type": "video",
  "title": "NTIA children's ball pit from above, part 1, 525-line",
  "links": [{"text": "NTIA T1.801.01", "href": "/members-section/search?dataset=3"}],
  "media": [{"type": "img", "src": "/uploads/thumbnails/thumb_1.jpg"}],
  "filename": "ntia_bpit1-525_original.avi",
  "file_size": "242.50 MB"
}
```

Required fields:

- `id`: Video ID number
- `url`: Source URL on CDVL
- `paragraphs`: Structured list of text content from the page
- `extracted_at`: Timestamp when data was extracted (ISO 8601 format)
- `content_type`: Always "video" for videos

Optional fields:

- `title`: Video title
- `links`: Related links found on the page
- `media`: Images and media elements
- `filename`: Download filename (if available)
- `file_size`: File size (if available)

### Dataset Records

```json
{
  "id": 7,
  "url": "https://www.cdvl.org/members-section/search?dataset=7",
  "paragraphs": ["Description of the dataset...", "Additional information..."],
  "extracted_at": "2025-10-09T15:30:00+00:00",
  "content_type": "dataset",
  "title": "Mobile Quality Dataset",
  "links": [{"text": "Video 123", "href": "/members-section/view-file/?videoid=123"}],
  "tables_count": 2
}
```

Required fields:

- `id`: Dataset ID number
- `url`: Source URL on CDVL
- `paragraphs`: Structured list of text content from the page
- `extracted_at`: Timestamp when data was extracted (ISO 8601 format)
- `content_type`: Always "dataset" for datasets

Optional fields:

- `title`: Dataset title
- `links`: Related links found on the page
- `tables_count`: Number of tables in the dataset page

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

Filter by keyword in paragraphs:

```bash
jq 'select(.paragraphs | join(" ") | contains("codec"))' videos.jsonl
```

Convert to CSV (or use `cdvl-crawler export`):

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
  "max_video_id": null,
  "max_dataset_id": null,
  "max_concurrent_requests": 5,
  "max_consecutive_failures": 1000,
  "request_delay": 0.1,
  "probe_step": 100,
  "max_probe_attempts": 20
}
```

### Configuration Options

All settings are optional with sensible defaults. CLI options override config file values.

| Setting                    | Default                              | CLI Option            | Description                                      |
| -------------------------- | ------------------------------------ | --------------------- | ------------------------------------------------ |
| `username`                 | (from env `CDVL_USERNAME` or prompt) | -                     | Your CDVL account email                          |
| `password`                 | (from env `CDVL_PASSWORD` or prompt) | -                     | Your CDVL account password                       |
| `start_video_id`           | 1                                    | `--start-video-id`    | Starting video ID for crawling                   |
| `start_dataset_id`         | 1                                    | `--start-dataset-id`  | Starting dataset ID for crawling                 |
| `max_video_id`             | None                                 | `--max-video-id`      | Maximum video ID to crawl (optional)             |
| `max_dataset_id`           | None                                 | `--max-dataset-id`    | Maximum dataset ID to crawl (optional)           |
| `max_concurrent_requests`  | 5                                    | `--max-concurrent`    | Number of parallel requests                      |
| `max_consecutive_failures` | 1000                                 | `--max-failures`      | Stop after N consecutive empty/failed responses  |
| `request_delay`            | 0.1                                  | `--delay`             | Delay between request batches (seconds)          |
| `probe_step`               | 100                                  | `--probe-step`        | How far ahead to jump when probing for ID gaps   |
| `max_probe_attempts`       | 20                                   | `--max-probe-attempts`| Max probe attempts (20*100=2000 ID range)        |
| `videos_file`              | videos.jsonl                         | -                     | Output filename for video metadata               |
| `datasets_file`            | datasets.jsonl                       | -                     | Output filename for dataset metadata             |
| `endpoints.video_base_url` | cdvl.org members section             | -                     | Base URL for video pages                         |
| `endpoints.dataset_base_url` | cdvl.org members section           | -                     | Base URL for dataset pages                       |
| `headers`                  | Browser-like headers                 | -                     | HTTP headers (User-Agent, Accept, etc.)          |

## API

You can also use the package programmatically:

```python
import asyncio
from cdvl_crawler import CDVLCrawler, CDVLDownloader, CDVLExporter, CDVLSiteGenerator

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

# Generate static site
def generate_site():
    generator = CDVLSiteGenerator(
        input_file="./data/videos.jsonl",
        output_file="./website/index.html"
    )
    success = generator.generate()
    print(f"Site generated: {success}")

# Export to CSV
def export_to_csv():
    exporter = CDVLExporter(
        input_file="./data/videos.jsonl",
        output_file="./data/videos.csv",
        columns=["id", "title", "filename"]  # None for all columns
    )
    success = exporter.export()
    print(f"Exported: {success}")

# Run
asyncio.run(crawl())
asyncio.run(download())
generate_site()
export_to_csv()
```

## Development

To set up a development environment:

```bash
# Clone the repository
git clone https://github.com/slhck/cdvl-crawler.git
cd cdvl-crawler

# Install dependencies (including dev dependencies)
uv sync --dev
```

### Running Tests

```bash
# Run all tests
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_utils.py -v

# Run with coverage (if pytest-cov is installed)
uv run pytest tests/ --cov=cdvl_crawler
```

### Linting and Formatting

```bash
# Check code style
uv run ruff check src/ tests/

# Auto-fix issues
uv run ruff check --fix src/ tests/

# Format code
uv run ruff format src/ tests/
```

### Type Checking

```bash
uv run mypy src/
```

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
