# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CDVL Crawler is a Python CLI tool for crawling and downloading videos from the CDVL (Consumer Digital Video Library) research repository. The tool provides two main operations:

1. **Crawling**: Systematically extracts metadata from all videos and datasets on cdvl.org
2. **Downloading**: Downloads individual videos by ID

## Development Commands

**Setup and run with uv (recommended):**
```bash
# Run the CLI
uv run cdvl-crawler --help
uv run cdvl-crawler crawl --help
uv run cdvl-crawler crawl
uv run cdvl-crawler crawl --output-dir ./data
uv run cdvl-crawler crawl --output-dir ./data --max-concurrent 10 --delay 0.2
uv run cdvl-crawler download 42
uv run cdvl-crawler download 42 --output-dir ./downloads

# Install dependencies
uv sync

# Lock dependencies
uv lock
```

**Type checking:**
```bash
uv run mypy src/
```

**Linting and formatting:**
```bash
# Check code
uv run ruff check src/

# Format code
uv run ruff format src/
```

**Testing:**
Note: No test suite exists yet. Tests should be added using pytest when implemented.

## Code Architecture

### Entry Point and CLI (`__main__.py`)

- Uses `argparse` with subcommands (`crawl`, `download`)
- All commands use `asyncio.run()` to execute async functions
- Handles CLI argument parsing and validation before delegating to main classes
- Supports `--output-dir` option to specify where files are saved (default: current directory)
- **Config file auto-detection**: If `config.json` exists in current directory, it's automatically loaded
- Config file (`--config`) is optional; credentials can come from env vars or user prompt
- Crawl command supports CLI options for all parameters:
  - `--start-video-id`, `--start-dataset-id`: Override starting IDs
  - `--max-concurrent`: Control parallelism (default: 5)
  - `--max-failures`: Control when to stop after consecutive failures (default: 10)
  - `--delay`: Control rate limiting between batches (default: 0.1s)
- CLI options override config file values, which override built-in defaults

### Core Components

**1. CDVLCrawler (`crawler.py`)**

Main class for metadata extraction:
- **Session Management**: Creates aiohttp session, handles CSRF-protected login
- **Parallel Crawling**: Uses `asyncio.Semaphore` to limit concurrent requests
- **Auto-Resume**: Reads last ID from JSONL output files to continue where it left off
- **Progress Tracking**: Uses `tqdm` with separate progress bars for videos and datasets
- **Content Parsing**: Uses BeautifulSoup with lxml parser to extract structured data from HTML
- **Output**: Appends to JSONL files with thread-safe locks in configurable output directory

Constructor: `CDVLCrawler(config_path=None, output_dir=".", overrides=None)`
- `config_path`: Optional path to config file
- `output_dir`: Directory for output files (default: current directory)
- `overrides`: Dict of config values to override (typically from CLI args)

Key methods:
- `_fetch_video()` / `_fetch_dataset()`: Fetch single item by ID
- `_parse_content()`: Extract structured data from HTML (titles, paragraphs, links, media, tables)
- `_crawl_videos()` / `_crawl_datasets()`: Main crawling loops with batch processing
- `_get_last_id_from_jsonl()`: Resume functionality

**2. CDVLDownloader (`downloader.py`)**

Main class for video downloads:
- **Form Submission**: Extracts CSRF tokens from video page, submits form to generate download link
- **URL Extraction**: Parses download table from response HTML
- **File Download**: Streams files with progress bars, handles Content-Disposition headers, saves to configurable output directory
- **Session Reuse**: Login once, download multiple videos in sequence

Constructor: `CDVLDownloader(config_path=None, output_dir=".")`
- `config_path`: Optional path to config file
- `output_dir`: Directory for downloaded files (default: current directory)

Key methods:
- `get_download_link()`: Scrape video page, submit form, extract download URL
- `download_file()`: Stream download with progress bar, auto-detect filename, save to output_dir

**3. Utilities (`utils.py`)**

Shared authentication and HTTP functionality:
- `get_default_config()`: Returns hardcoded defaults (endpoints, headers, crawling parameters)
- `load_config()`: Loads config from JSON file; deep-merges with defaults; returns defaults if no file
- `get_credentials()`: Retrieves credentials with priority: config file → env vars (CDVL_USERNAME, CDVL_PASSWORD) → interactive prompt
- `login_to_cdvl()`: Two-step login process: fetch login page to get CSRF tokens, submit login form with tokens
- `create_session()`: Creates aiohttp session with configured headers and timeouts
- `parse_content_disposition()`: Extracts filename from HTTP headers (supports RFC 5987 encoding)

**4. Type Definitions (`types.py`)**

TypedDict definitions for structured data:
- `VideoData` / `DatasetData`: Complete records with id, url, and parsed content
- `PartialContentData`: Intermediate data during parsing (before id/url added)
- `LinkDict`, `MediaDict`: Nested structures for links and media elements

### Authentication Flow

CDVL uses ASP.NET Core Identity with anti-forgery tokens:

1. GET `/login` → Extract `__RequestVerificationToken` and `ufprt` tokens from hidden inputs
2. POST `/login` with form data including tokens → Establishes session cookie
3. Verify `.AspNetCore.Identity.Application` cookie exists
4. Use session for all subsequent requests

### Data Flow

**Crawling:**
```
Config → CDVLCrawler → Login → Parallel fetch batches → Parse HTML →
Extract structured data → Append to JSONL (thread-safe)
```

**Downloading:**
```
Config → CDVLDownloader → Login → Get video page → Extract form tokens →
Submit form → Parse download table → Stream file with progress
```

### Output Format

**JSONL files** (one JSON object per line):
- `videos.jsonl`: One record per successfully crawled video
- `datasets.jsonl`: One record per successfully crawled dataset

Each record contains:
- `id`, `url`, `title`, `text`, `paragraphs`, `links`, `media`, `html`, `extracted_at`, `content_type`
- Optional: `tables_count` (for datasets with tables)

## Configuration

Configuration is **optional** with multiple layers of defaults and overrides:

**Priority order (highest to lowest):**
1. CLI arguments (e.g., `--max-concurrent 10`)
2. Config file values (auto-detected `config.json` or via `--config path`)
3. Built-in defaults (hardcoded in `utils.py`)

**Config file loading:**
- If `config.json` exists in current directory, it's automatically loaded
- Use `--config path` to specify a different config file
- If no config file exists and none specified, uses built-in defaults

**Built-in defaults:**
- Endpoints: CDVL members section URLs
- Headers: Browser-like User-Agent, Accept headers
- Crawling: 5 concurrent, 10 max failures, 0.1s delay
- Output: videos.jsonl, datasets.jsonl

**Credentials** (separate priority):
1. Config file (`username`, `password`) - auto-detected or via `--config`
2. Environment variables (`CDVL_USERNAME`, `CDVL_PASSWORD`)
3. Interactive prompt

**Config file** (optional) can override any defaults:
- CDVL credentials (`username`, `password`)
- Endpoint URLs (`endpoints.video_base_url`, `endpoints.dataset_base_url`)
- Headers (`headers.User-Agent`, etc.)
- Crawling parameters (`max_concurrent_requests`, `max_consecutive_failures`, `request_delay`)
- Output filenames (`output.videos_file`, `output.datasets_file`)

The `config.example.json` file serves as a template.

**Note**: Output directory is always specified via `--output-dir` CLI option (default: current directory).

## Important Implementation Details

- **Async/await**: Entire codebase is async using aiohttp
- **Thread safety**: Uses `threading.Lock` for JSONL file writes (needed because tqdm updates happen from different async tasks)
- **BeautifulSoup typing**: Some methods return `str | list` for attributes, code includes type guards
- **Error handling**: Distinguishes between "empty" (valid response, no content), "failed" (HTTP error), and exceptions
- **Rate limiting**: Uses `asyncio.sleep()` between batches to avoid server strain
- **Consecutive failures**: Stops crawling after N consecutive empty/failed responses (configurable)

## Package Structure

```
src/cdvl_crawler/
├── __init__.py        # Package exports (CDVLCrawler, CDVLDownloader)
├── __main__.py        # CLI entry point
├── crawler.py         # CDVLCrawler class
├── downloader.py      # CDVLDownloader class
├── types.py           # TypedDict definitions
├── utils.py           # Shared utilities
└── py.typed           # PEP 561 marker for type checking
```

Entry point is defined in `pyproject.toml`: `cdvl-crawler = "cdvl_crawler.__main__:main"`
