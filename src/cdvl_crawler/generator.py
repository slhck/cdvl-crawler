"""
Static site generator for CDVL video metadata
"""

import json
import logging
import os
from pathlib import Path

from cdvl_crawler.types import VideoData

logger = logging.getLogger(__name__)


class CDVLSiteGenerator:
    """Generate a static HTML site from videos.jsonl"""

    def __init__(
        self, input_file: str = "videos.jsonl", output_file: str = "index.html"
    ):
        """
        Initialize the site generator

        Args:
            input_file: Path to videos.jsonl file
            output_file: Path to output HTML file
        """
        self.input_file = input_file
        self.output_file = output_file

    def load_videos(self) -> list[VideoData]:
        """Load and parse videos from JSONL file"""
        videos: list[VideoData] = []
        if not os.path.exists(self.input_file):
            logger.error(f"Input file not found: {self.input_file}")
            return videos

        with open(self.input_file, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    video = json.loads(line)
                    videos.append(video)
                except json.JSONDecodeError as e:
                    logger.warning(f"Failed to parse line {line_num}: {e}")

        logger.info(f"Loaded {len(videos)} videos from {self.input_file}")
        return videos

    def truncate_text(self, text: str, max_length: int = 150) -> str:
        """Truncate text to max_length and add ellipsis if needed"""
        if len(text) <= max_length:
            return text
        return text[:max_length].rsplit(" ", 1)[0] + "..."

    def escape_json(self, data: list[VideoData]) -> str:
        """Escape JSON for embedding in HTML"""
        return json.dumps(data).replace("<", "\\u003c").replace(">", "\\u003e")

    def generate_html(self, videos: list[VideoData]) -> str:
        """Generate the complete HTML page with brutalist design"""
        # Prepare video data for the table
        video_data_json = self.escape_json(videos)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CDVL // VIDEO ARCHIVE</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@300;400;500&family=Space+Grotesk:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0a0a;
            --bg-secondary: #141414;
            --bg-tertiary: #1a1a1a;
            --text-primary: #fafafa;
            --text-secondary: #d0d0d0;
            --text-muted: #999999;
            --accent-pink: #e85d8c;
            --accent-cyan: #00f5d4;
            --accent-cyan-light: #66fff0;
            --accent-yellow: #ffe66d;
            --accent-blue: #4361ee;
            --border-color: #444444;
            --border-highlight: #666666;
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'DM Mono', monospace;
            background-color: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.6;
            min-height: 100vh;
        }}

        /* Header */
        .header {{
            border-bottom: 3px solid var(--border-color);
            padding: 40px 24px;
            background: var(--bg-secondary);
        }}

        .header-content {{
            max-width: 1400px;
            margin: 0 auto;
        }}

        .title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: clamp(32px, 6vw, 64px);
            font-weight: 700;
            letter-spacing: -0.02em;
            margin-bottom: 8px;
            display: flex;
            align-items: baseline;
            flex-wrap: wrap;
            gap: 16px;
        }}

        .title-main {{
            color: var(--text-primary);
        }}

        .title-accent {{
            color: var(--accent-blue);
        }}

        .subtitle {{
            font-size: 14px;
            color: var(--text-muted);
            letter-spacing: 0.05em;
            text-transform: uppercase;
        }}

        /* Search Bar */
        .search-section {{
            position: sticky;
            top: 0;
            z-index: 100;
            background: var(--bg-primary);
            border-bottom: 2px solid var(--border-color);
            padding: 16px 24px;
        }}

        .search-container {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr auto auto;
            gap: 16px;
            align-items: center;
        }}

        @media (max-width: 768px) {{
            .search-container {{
                grid-template-columns: 1fr;
            }}
        }}

        .search-box {{
            position: relative;
        }}

        .search-input {{
            width: 100%;
            padding: 16px 20px;
            padding-left: 48px;
            font-family: 'DM Mono', monospace;
            font-size: 14px;
            background: var(--bg-tertiary);
            border: 2px solid var(--border-color);
            color: var(--text-primary);
            outline: none;
            transition: border-color 0.2s, box-shadow 0.2s;
        }}

        .search-input::placeholder {{
            color: var(--text-muted);
        }}

        .search-input:focus {{
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 4px rgba(0, 245, 212, 0.15);
        }}

        .search-icon {{
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
        }}

        .search-spinner {{
            position: absolute;
            right: 16px;
            top: 50%;
            transform: translateY(-50%);
            width: 20px;
            height: 20px;
            border: 2px solid var(--border-color);
            border-top-color: var(--accent-cyan);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            display: none;
        }}

        .search-spinner.active {{
            display: block;
        }}

        @keyframes spin {{
            to {{ transform: translateY(-50%) rotate(360deg); }}
        }}

        .stats {{
            font-size: 12px;
            color: var(--text-secondary);
            padding: 8px 16px;
            border: 1px solid var(--border-color);
            background: var(--bg-secondary);
            white-space: nowrap;
        }}

        .stats-number {{
            color: var(--accent-cyan);
            font-weight: 500;
        }}

        .download-btn {{
            padding: 16px 24px;
            font-family: 'DM Mono', monospace;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            background: var(--accent-blue);
            color: #fff;
            border: none;
            cursor: pointer;
            transition: transform 0.1s, box-shadow 0.2s;
            display: none;
        }}

        .download-btn:hover {{
            transform: translate(-2px, -2px);
            box-shadow: 4px 4px 0 var(--accent-cyan);
        }}

        .download-btn.visible {{
            display: block;
        }}

        /* Table Container */
        .table-section {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}

        .table-wrapper {{
            overflow-x: auto;
            border: 2px solid var(--border-color);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        thead {{
            background: var(--bg-tertiary);
            border-bottom: 2px solid var(--border-color);
        }}

        th {{
            padding: 16px 12px;
            text-align: left;
            font-weight: 500;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-secondary);
            white-space: nowrap;
            user-select: none;
        }}

        th.sortable {{
            cursor: pointer;
            transition: color 0.2s;
        }}

        th.sortable:hover {{
            color: var(--accent-cyan);
        }}

        th .sort-arrow {{
            margin-left: 4px;
            opacity: 0.5;
        }}

        th.sorted .sort-arrow {{
            opacity: 1;
            color: var(--accent-cyan);
        }}

        tbody tr {{
            border-bottom: 1px solid var(--border-color);
            transition: background-color 0.15s;
        }}

        tbody tr:hover {{
            background: var(--bg-secondary);
        }}

        tbody tr.selected {{
            background: rgba(255, 45, 106, 0.1);
            border-left: 3px solid var(--accent-blue);
        }}

        td {{
            padding: 12px;
            vertical-align: top;
        }}

        a {{
            color: var(--accent-cyan);
            text-decoration: none;
            transition: color 0.15s;
        }}

        a:hover {{
            color: var(--accent-cyan-light);
        }}

        /* Custom Checkbox */
        .checkbox-cell {{
            width: 48px;
            text-align: center;
        }}

        .custom-checkbox {{
            position: relative;
            width: 20px;
            height: 20px;
            cursor: pointer;
        }}

        .custom-checkbox input {{
            position: absolute;
            opacity: 0;
            width: 100%;
            height: 100%;
            cursor: pointer;
        }}

        .checkmark {{
            position: absolute;
            top: 0;
            left: 0;
            width: 20px;
            height: 20px;
            background: var(--bg-tertiary);
            border: 2px solid var(--border-color);
            transition: all 0.15s;
        }}

        .custom-checkbox:hover .checkmark {{
            border-color: var(--accent-blue);
        }}

        .custom-checkbox input:checked ~ .checkmark {{
            background: var(--accent-blue);
            border-color: var(--accent-blue);
        }}

        .checkmark:after {{
            content: '';
            position: absolute;
            display: none;
            left: 6px;
            top: 2px;
            width: 5px;
            height: 10px;
            border: solid #000;
            border-width: 0 2px 2px 0;
            transform: rotate(45deg);
        }}

        .custom-checkbox input:checked ~ .checkmark:after {{
            display: block;
        }}

        /* Cell Styles */
        .id-cell {{
            font-weight: 500;
            color: var(--accent-cyan);
        }}

        .id-link {{
            color: var(--accent-cyan);
            text-decoration: none;
            padding: 4px 8px;
            border: 1px solid transparent;
            transition: all 0.15s;
        }}

        .id-link:hover {{
            color: var(--accent-cyan-light);
            border-color: var(--accent-cyan);
            background: rgba(0, 245, 212, 0.1);
        }}

        .title-cell {{
            max-width: 300px;
        }}

        .title-link {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.15s;
        }}

        .title-link:hover {{
            color: var(--accent-cyan-light);
        }}

        .filename-cell {{
            font-size: 11px;
            color: var(--text-muted);
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        .size-cell {{
            color: var(--text-secondary);
            white-space: nowrap;
        }}

        .desc-cell {{
            color: var(--text-muted);
            font-size: 12px;
            max-width: 300px;
            line-height: 1.5;
        }}

        /* Modal */
        .modal-backdrop {{
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.9);
            z-index: 1000;
            display: none;
            align-items: flex-start;
            justify-content: center;
            padding: 40px 24px;
            overflow-y: auto;
        }}

        .modal-backdrop.active {{
            display: flex;
        }}

        .modal {{
            background: var(--bg-secondary);
            border: 2px solid var(--border-color);
            width: 100%;
            max-width: 800px;
            position: relative;
        }}

        .modal-header {{
            padding: 24px;
            border-bottom: 2px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
        }}

        .modal-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1.3;
        }}

        .modal-close {{
            background: none;
            border: 2px solid var(--border-color);
            color: var(--text-secondary);
            width: 40px;
            height: 40px;
            cursor: pointer;
            font-size: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.15s;
            flex-shrink: 0;
        }}

        .modal-close:hover {{
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }}

        .modal-body {{
            padding: 24px;
        }}

        .modal-section {{
            margin-bottom: 24px;
        }}

        .modal-section:last-child {{
            margin-bottom: 0;
        }}

        .section-label {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.15em;
            color: var(--text-muted);
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .section-label::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: var(--border-color);
        }}

        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
        }}

        .metadata-item {{
            padding: 16px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
        }}

        .metadata-key {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}

        .metadata-value {{
            font-size: 14px;
            color: var(--text-primary);
            word-break: break-all;
        }}

        .metadata-value.highlight {{
            color: var(--accent-cyan);
            font-weight: 500;
        }}

        .description-text {{
            color: var(--text-secondary);
            font-size: 13px;
            line-height: 1.8;
        }}

        .description-text p {{
            margin-bottom: 12px;
        }}

        .description-text p:last-child {{
            margin-bottom: 0;
        }}

        .links-list {{
            list-style: none;
        }}

        .links-list li {{
            padding: 8px 0;
            border-bottom: 1px dashed var(--border-color);
        }}

        .links-list li:last-child {{
            border-bottom: none;
        }}

        .links-list a {{
            color: var(--accent-cyan);
            text-decoration: none;
            transition: color 0.15s;
            font-size: 13px;
        }}

        .links-list a:hover {{
            color: var(--accent-cyan-light);
        }}

        .media-list {{
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}

        .media-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
        }}

        .media-type {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            padding: 4px 8px;
            background: var(--accent-blue);
            color: #fff;
        }}

        .media-src {{
            font-size: 12px;
            color: var(--text-muted);
            word-break: break-all;
        }}

        .source-link {{
            color: var(--accent-cyan);
            font-size: 12px;
            text-decoration: none;
            word-break: break-all;
            transition: color 0.15s;
        }}

        .source-link:hover {{
            color: var(--accent-cyan-light);
        }}

        .modal-footer {{
            padding: 24px;
            border-top: 2px solid var(--border-color);
            background: var(--bg-tertiary);
        }}

        .modal-download-btn {{
            width: 100%;
            padding: 16px 24px;
            font-family: 'DM Mono', monospace;
            font-size: 13px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            background: var(--accent-blue);
            color: #fff;
            border: none;
            cursor: pointer;
            transition: transform 0.1s, box-shadow 0.2s;
        }}

        .modal-download-btn:hover {{
            transform: translate(-2px, -2px);
            box-shadow: 4px 4px 0 var(--accent-cyan);
        }}

        /* Command Modal */
        .command-modal .modal {{
            max-width: 600px;
        }}

        .command-input {{
            width: 100%;
            padding: 16px;
            font-family: 'DM Mono', monospace;
            font-size: 13px;
            background: var(--bg-primary);
            border: 2px solid var(--border-color);
            color: var(--accent-cyan);
            cursor: pointer;
            transition: border-color 0.2s;
        }}

        .command-input:hover {{
            border-color: var(--accent-cyan);
        }}

        .command-input-wrapper {{
            position: relative;
        }}

        .copy-feedback {{
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            padding: 4px 10px;
            background: var(--accent-cyan);
            color: #000;
            font-size: 11px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            opacity: 0;
            transition: opacity 0.15s;
            pointer-events: none;
        }}

        .copy-feedback.visible {{
            opacity: 1;
        }}

        .command-hint {{
            margin-top: 16px;
            font-size: 11px;
            color: var(--text-muted);
        }}

        /* Empty State */
        .empty-state {{
            padding: 80px 24px;
            text-align: center;
        }}

        .empty-icon {{
            font-size: 48px;
            margin-bottom: 16px;
            opacity: 0.3;
        }}

        .empty-text {{
            color: var(--text-muted);
            font-size: 14px;
        }}

        /* Keyboard Hints */
        .kbd {{
            display: inline-block;
            padding: 2px 6px;
            font-size: 10px;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            color: var(--text-secondary);
            margin-left: 4px;
        }}

        /* Footer */
        .footer {{
            border-top: 2px solid var(--border-color);
            padding: 24px;
            text-align: center;
            background: var(--bg-secondary);
        }}

        .footer-text {{
            font-size: 11px;
            color: var(--text-muted);
            letter-spacing: 0.05em;
        }}

        .footer-link {{
            color: var(--accent-cyan);
            text-decoration: none;
        }}

        .footer-link:hover {{
            color: var(--accent-cyan-light);
        }}

        .disclaimer-text {{
            font-size: 11px;
            color: var(--text-muted);
            margin-top: 12px;
        }}
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <h1 class="title">
                <span class="title-main">CDVL</span>
                <span class="title-accent">//</span>
                <span class="title-main">VIDEO ARCHIVE</span>
            </h1>
            <p class="subtitle">Consumer Digital Video Library // Metadata Browser</p>
            <p class="disclaimer-text">Not affiliated with cdvl.org. Independent metadata browser.</p>
        </div>
    </header>

    <!-- Search Section -->
    <div class="search-section">
        <div class="search-container">
            <div class="search-box">
                <svg class="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="M21 21l-4.35-4.35"></path>
                </svg>
                <input
                    type="text"
                    id="searchInput"
                    class="search-input"
                    placeholder="Search by ID, title, filename, or description... (press / to focus)"
                    autocomplete="off"
                >
                <div id="searchSpinner" class="search-spinner"></div>
            </div>
            <div id="videoStats" class="stats">
                <span class="stats-number">{len(videos)}</span> videos loaded
            </div>
            <button id="downloadBtn" class="download-btn" onclick="generateDownloadCommand()">
                Download Selected
            </button>
        </div>
    </div>

    <!-- Table Section -->
    <div class="table-section">
        <div class="table-wrapper">
            <table>
                <thead>
                    <tr>
                        <th class="checkbox-cell">
                            <label class="custom-checkbox">
                                <input type="checkbox" id="selectAll" onchange="toggleSelectAll(this.checked)">
                                <span class="checkmark"></span>
                            </label>
                        </th>
                        <th class="sortable" onclick="sortTable('id')" data-column="id">
                            ID <span class="sort-arrow">↕</span>
                        </th>
                        <th class="sortable" onclick="sortTable('title')" data-column="title">
                            Title <span class="sort-arrow">↕</span>
                        </th>
                        <th class="sortable" onclick="sortTable('filename')" data-column="filename">
                            Filename <span class="sort-arrow">↕</span>
                        </th>
                        <th class="sortable" onclick="sortTable('file_size')" data-column="file_size">
                            Size <span class="sort-arrow">↕</span>
                        </th>
                        <th>Description</th>
                    </tr>
                </thead>
                <tbody id="videoTableBody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <!-- Footer -->
    <footer class="footer">
        <p class="footer-text">
            Generated by <a href="https://github.com/slhck/cdvl-crawler" class="footer-link" target="_blank">cdvl-crawler</a>
            // Not affiliated with cdvl.org
        </p>
    </footer>

    <!-- Video Detail Modal -->
    <div id="videoModal" class="modal-backdrop">
        <div class="modal">
            <div class="modal-header">
                <h2 id="modalTitle" class="modal-title"></h2>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div id="modalBody" class="modal-body">
                <!-- Populated by JavaScript -->
            </div>
            <div class="modal-footer">
                <button id="modalDownloadBtn" class="modal-download-btn">
                    Generate Download Command
                </button>
            </div>
        </div>
    </div>

    <!-- Command Modal -->
    <div id="commandModal" class="modal-backdrop command-modal">
        <div class="modal">
            <div class="modal-header">
                <h2 class="modal-title">Download Command</h2>
                <button class="modal-close" onclick="closeCommandModal()">&times;</button>
            </div>
            <div class="modal-body">
                <p class="section-label">Click to copy</p>
                <div class="command-input-wrapper">
                    <input
                        type="text"
                        id="commandInput"
                        class="command-input"
                        readonly
                        onclick="copyCommand()"
                    >
                    <div id="copyFeedback" class="copy-feedback">Copied</div>
                </div>
                <p class="command-hint">
                    Run this command in your terminal to download the selected video(s).
                    Requires <a target="_blank" href="https://docs.astral.sh/uv/"><code>uv</code></a>.
                </p>
            </div>
        </div>
    </div>

    <script>
        // Video data
        const videos = {video_data_json};
        // Pre-compute search index for faster filtering
        const searchIndex = new Map(videos.map(video => [
            video.id,
            [video.id.toString(), video.title || '', video.filename || '', (video.paragraphs || []).join(' ')].join(' ').toLowerCase()
        ]));
        let filteredVideos = [...videos];
        let sortState = {{ column: 'id', ascending: true }};
        let selectedVideoIds = new Set();
        let searchTimeout = null;
        let currentModalVideoId = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            renderTable();
            updateUI();
            checkHashAndOpenModal();

            // Keyboard shortcuts
            document.addEventListener('keydown', handleKeyboard);
        }});

        window.addEventListener('hashchange', checkHashAndOpenModal);

        function handleKeyboard(e) {{
            if (e.key === 'Escape') {{
                closeModal();
                closeCommandModal();
            }}
            if (e.key === '/' && !e.ctrlKey && !e.metaKey) {{
                const active = document.activeElement;
                if (active.tagName !== 'INPUT') {{
                    e.preventDefault();
                    document.getElementById('searchInput').focus();
                }}
            }}
        }}

        function checkHashAndOpenModal() {{
            const hash = window.location.hash;
            if (hash && hash.startsWith('#')) {{
                const videoId = parseInt(hash.substring(1));
                if (!isNaN(videoId)) {{
                    const video = videos.find(v => v.id === videoId);
                    if (video) openModal(videoId);
                }}
            }}
        }}

        function getCleanParagraphs(video) {{
            return (video.paragraphs || [])
                .filter(p => p && p.trim() && !p.includes('TagBuilder') && !p.includes('Click here to generate'));
        }}

        function makeAbsoluteUrl(url) {{
            if (!url) return url;
            if (url.startsWith('http://') || url.startsWith('https://')) return url;
            if (url.startsWith('//')) return 'https:' + url;
            const baseUrl = 'https://www.cdvl.org';
            return url.startsWith('/') ? baseUrl + url : baseUrl + '/' + url;
        }}

        function escapeHtml(text) {{
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }}

        // Search with debounce
        document.getElementById('searchInput').addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            document.getElementById('searchSpinner').classList.add('active');

            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                if (!query) {{
                    filteredVideos = [...videos];
                }} else {{
                    filteredVideos = videos.filter(video => searchIndex.get(video.id).includes(query));
                }}
                renderTable();
                updateUI();
                document.getElementById('searchSpinner').classList.remove('active');
            }}, 150);
        }});

        // Render table
        function renderTable() {{
            const tbody = document.getElementById('videoTableBody');

            if (filteredVideos.length === 0) {{
                tbody.innerHTML = `
                    <tr>
                        <td colspan="6">
                            <div class="empty-state">
                                <div class="empty-icon">∅</div>
                                <p class="empty-text">No videos match your search</p>
                            </div>
                        </td>
                    </tr>
                `;
                return;
            }}

            tbody.innerHTML = filteredVideos.map(video => {{
                const description = getCleanParagraphs(video).join(' ');
                const excerpt = description.length > 120
                    ? description.substring(0, 120).split(' ').slice(0, -1).join(' ') + '...'
                    : description;
                const isSelected = selectedVideoIds.has(video.id);

                return `
                    <tr id="video-${{video.id}}" class="${{isSelected ? 'selected' : ''}}">
                        <td class="checkbox-cell">
                            <label class="custom-checkbox">
                                <input
                                    type="checkbox"
                                    ${{isSelected ? 'checked' : ''}}
                                    onchange="toggleVideoSelection(${{video.id}}, this.checked)"
                                >
                                <span class="checkmark"></span>
                            </label>
                        </td>
                        <td class="id-cell">
                            <a href="#" class="id-link" onclick="openModal(${{video.id}}); return false;">
                                #${{video.id}}
                            </a>
                        </td>
                        <td class="title-cell">
                            <a href="#" class="title-link" onclick="openModal(${{video.id}}); return false;">
                                ${{escapeHtml(video.title || 'Untitled')}}
                            </a>
                        </td>
                        <td class="filename-cell" title="${{escapeHtml(video.filename || '')}}">
                            ${{escapeHtml(video.filename || '—')}}
                        </td>
                        <td class="size-cell">
                            ${{escapeHtml(video.file_size || '—')}}
                        </td>
                        <td class="desc-cell">
                            ${{escapeHtml(excerpt || 'No description')}}
                        </td>
                    </tr>
                `;
            }}).join('');
        }}

        // Sort
        function sortTable(column) {{
            const th = document.querySelector(`th[data-column="${{column}}"]`);

            // Update sort state
            if (sortState.column === column) {{
                sortState.ascending = !sortState.ascending;
            }} else {{
                sortState.column = column;
                sortState.ascending = true;
            }}

            // Sort data
            filteredVideos.sort((a, b) => {{
                let aVal = a[column] || '';
                let bVal = b[column] || '';

                if (column === 'id') {{
                    aVal = parseInt(aVal);
                    bVal = parseInt(bVal);
                }} else {{
                    aVal = aVal.toString().toLowerCase();
                    bVal = bVal.toString().toLowerCase();
                }}

                if (aVal < bVal) return sortState.ascending ? -1 : 1;
                if (aVal > bVal) return sortState.ascending ? 1 : -1;
                return 0;
            }});

            // Update UI
            document.querySelectorAll('th.sortable').forEach(el => {{
                el.classList.remove('sorted');
                el.querySelector('.sort-arrow').textContent = '↕';
            }});

            if (th) {{
                th.classList.add('sorted');
                th.querySelector('.sort-arrow').textContent = sortState.ascending ? '↑' : '↓';
            }}

            renderTable();
        }}

        // Selection
        function toggleSelectAll(checked) {{
            filteredVideos.forEach(video => {{
                if (checked) {{
                    selectedVideoIds.add(video.id);
                }} else {{
                    selectedVideoIds.delete(video.id);
                }}
            }});
            renderTable();
            updateUI();
        }}

        function toggleVideoSelection(videoId, checked) {{
            if (checked) {{
                selectedVideoIds.add(videoId);
            }} else {{
                selectedVideoIds.delete(videoId);
                document.getElementById('selectAll').checked = false;
            }}

            const row = document.getElementById(`video-${{videoId}}`);
            if (row) {{
                row.classList.toggle('selected', checked);
            }}

            updateUI();
        }}

        function updateUI() {{
            // Update stats
            const stats = document.getElementById('videoStats');
            if (filteredVideos.length === videos.length) {{
                stats.innerHTML = `<span class="stats-number">${{videos.length}}</span> videos`;
            }} else {{
                stats.innerHTML = `<span class="stats-number">${{filteredVideos.length}}</span> of ${{videos.length}} videos`;
            }}

            // Update download button
            const btn = document.getElementById('downloadBtn');
            if (selectedVideoIds.size > 0) {{
                btn.classList.add('visible');
                btn.textContent = `Download (${{selectedVideoIds.size}})`;
            }} else {{
                btn.classList.remove('visible');
            }}
        }}

        // Modal
        function openModal(videoId) {{
            const video = videos.find(v => v.id === videoId);
            if (!video) return;

            currentModalVideoId = videoId;

            if (window.location.hash !== `#${{videoId}}`) {{
                window.history.pushState(null, '', `#${{videoId}}`);
            }}

            document.getElementById('modalTitle').textContent = video.title || `Video #${{video.id}}`;

            const body = document.getElementById('modalBody');
            body.innerHTML = `
                <div class="modal-section">
                    <div class="section-label">Metadata</div>
                    <div class="metadata-grid">
                        <div class="metadata-item">
                            <div class="metadata-key">Video ID</div>
                            <div class="metadata-value highlight">#${{video.id}}</div>
                        </div>
                        ${{video.file_size ? `
                        <div class="metadata-item">
                            <div class="metadata-key">File Size</div>
                            <div class="metadata-value">${{escapeHtml(video.file_size)}}</div>
                        </div>
                        ` : ''}}
                        ${{video.filename ? `
                        <div class="metadata-item" style="grid-column: 1 / -1;">
                            <div class="metadata-key">Filename</div>
                            <div class="metadata-value">${{escapeHtml(video.filename)}}</div>
                        </div>
                        ` : ''}}
                    </div>
                </div>

                <div class="modal-section">
                    <div class="section-label">Description</div>
                    <div class="description-text">
                        ${{getCleanParagraphs(video)
                            .map(p => `<p>${{escapeHtml(p)}}</p>`)
                            .join('') || '<p>No description available</p>'
                        }}
                    </div>
                </div>

                ${{video.links && video.links.length > 0 ? `
                <div class="modal-section">
                    <div class="section-label">Related Links</div>
                    <ul class="links-list">
                        ${{video.links.map(link => `
                            <li>
                                <a href="${{makeAbsoluteUrl(link.href)}}" target="_blank" rel="noopener">
                                    ${{escapeHtml(link.text)}}
                                </a>
                            </li>
                        `).join('')}}
                    </ul>
                </div>
                ` : ''}}

                ${{video.media && video.media.length > 0 ? `
                <div class="modal-section">
                    <div class="section-label">Media</div>
                    <div class="media-list">
                        ${{video.media.map(m => `
                            <div class="media-item">
                                <span class="media-type">${{escapeHtml(m.type)}}</span>
                                <span class="media-src">${{escapeHtml(m.src)}}</span>
                            </div>
                        `).join('')}}
                    </div>
                </div>
                ` : ''}}

                <div class="modal-section">
                    <div class="section-label">Source</div>
                    <a href="${{video.url}}" target="_blank" rel="noopener" class="source-link">
                        ${{escapeHtml(video.url)}}
                    </a>
                    ${{video.extracted_at ? `
                    <p style="margin-top: 8px; font-size: 11px; color: var(--text-muted);">
                        Extracted: ${{escapeHtml(video.extracted_at)}}
                    </p>
                    ` : ''}}
                </div>
            `;

            document.getElementById('modalDownloadBtn').onclick = () => {{
                showCommandModal(`uvx cdvl-crawler download ${{video.id}}`);
            }};

            document.getElementById('videoModal').classList.add('active');
        }}

        function closeModal() {{
            document.getElementById('videoModal').classList.remove('active');
            currentModalVideoId = null;
            if (window.location.hash) {{
                window.history.pushState(null, '', window.location.pathname);
            }}
        }}

        // Command modal
        function generateDownloadCommand() {{
            const ids = Array.from(selectedVideoIds).sort((a, b) => a - b);
            const command = `uvx cdvl-crawler download ${{ids.join(',')}}`;
            showCommandModal(command);
        }}

        function showCommandModal(command) {{
            document.getElementById('commandInput').value = command;
            document.getElementById('copyFeedback').classList.remove('visible');
            document.getElementById('commandModal').classList.add('active');
        }}

        function closeCommandModal() {{
            document.getElementById('commandModal').classList.remove('active');
        }}

        function copyCommand() {{
            const input = document.getElementById('commandInput');
            input.select();
            input.setSelectionRange(0, 99999);

            navigator.clipboard.writeText(input.value).then(() => {{
                const feedback = document.getElementById('copyFeedback');
                feedback.classList.add('visible');
                setTimeout(() => feedback.classList.remove('visible'), 2000);
            }});
        }}

        // Close modals on backdrop click
        document.getElementById('videoModal').addEventListener('click', (e) => {{
            if (e.target.id === 'videoModal') closeModal();
        }});

        document.getElementById('commandModal').addEventListener('click', (e) => {{
            if (e.target.id === 'commandModal') closeCommandModal();
        }});
    </script>
</body>
</html>
"""
        return html

    def generate(self) -> bool:
        """
        Generate the static site

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Generating static site from {self.input_file}")

        # Load videos
        videos = self.load_videos()
        if not videos:
            logger.error("No videos loaded, cannot generate site")
            return False

        # Generate HTML
        html = self.generate_html(videos)

        # Write output
        try:
            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

            logger.info(f"✓ Generated static site: {self.output_file}")
            logger.info(f"  Videos included: {len(videos)}")
            logger.info(f"  File size: {output_path.stat().st_size / 1024:.1f} KB")
            return True

        except Exception as e:
            logger.error(f"Failed to write output file: {e}")
            return False
