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
        """Generate the complete HTML page"""
        # Prepare video data for the table
        video_data_json = self.escape_json(videos)

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CDVL Video Library</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .modal {{
            display: none;
            opacity: 0;
            transition: opacity 0.3s ease-in-out;
        }}
        .modal.active {{
            display: flex;
            opacity: 1;
        }}
        .modal.active > div {{
            animation: slideDown 0.3s ease-out;
        }}
        @keyframes slideDown {{
            from {{
                transform: translateY(-50px);
                opacity: 0;
            }}
            to {{
                transform: translateY(0);
                opacity: 1;
            }}
        }}
        .table-container {{
            overflow-x: auto;
        }}
        .sortable:hover {{
            background-color: #f3f4f6;
            cursor: pointer;
        }}
    </style>
</head>
<body class="bg-gray-50">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8">
            <h1 class="text-4xl font-bold text-gray-900 mb-2">CDVL Video Library</h1>
            <p class="text-gray-600">Browse and search the Consumer Digital Video Library</p>
        </header>

        <!-- Search and Actions Bar (Sticky) -->
        <div class="sticky top-0 z-40 bg-gray-50 pb-4 -mx-4 px-4 pt-0">
            <div class="bg-white rounded-lg shadow-md p-4">
                <div class="flex flex-col md:flex-row gap-4 items-center justify-between">
                    <div class="flex-1 w-full relative">
                        <input
                            type="text"
                            id="searchInput"
                            placeholder="Search videos by title, ID, filename, or description..."
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                        >
                        <div id="searchSpinner" class="hidden absolute right-3 top-1/2 -translate-y-1/2">
                            <svg class="animate-spin h-5 w-5 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                        </div>
                    </div>
                    <div class="flex gap-2">
                        <span id="videoCount" class="text-sm text-gray-600 px-3 py-2">
                            {len(videos)} videos
                        </span>
                        <button
                            id="downloadButton"
                            class="hidden bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors font-medium"
                            onclick="generateDownloadCommand()"
                        >
                            Generate Download Command
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Table -->
        <div class="bg-white rounded-lg shadow-sm overflow-hidden mt-4">
            <div class="table-container">
                <table class="w-full">
                    <thead class="bg-gray-100 border-b border-gray-200">
                        <tr>
                            <th class="px-4 py-3 text-left w-12">
                                <input
                                    type="checkbox"
                                    id="selectAll"
                                    class="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                                    onchange="toggleSelectAll(this.checked)"
                                >
                            </th>
                            <th class="px-4 py-3 text-left font-semibold text-gray-700 sortable" onclick="sortTable('id')">
                                ID <span class="sort-indicator"></span>
                            </th>
                            <th class="px-4 py-3 text-left font-semibold text-gray-700 sortable" onclick="sortTable('title')">
                                Title <span class="sort-indicator"></span>
                            </th>
                            <th class="px-4 py-3 text-left font-semibold text-gray-700 sortable" onclick="sortTable('filename')">
                                Filename <span class="sort-indicator"></span>
                            </th>
                            <th class="px-4 py-3 text-left font-semibold text-gray-700 sortable" onclick="sortTable('file_size')">
                                File Size <span class="sort-indicator"></span>
                            </th>
                            <th class="px-4 py-3 text-left font-semibold text-gray-700">
                                Description
                            </th>
                        </tr>
                    </thead>
                    <tbody id="videoTableBody" class="divide-y divide-gray-200">
                        <!-- Populated by JavaScript -->
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <!-- Command Modal -->
    <div id="commandModal" class="modal fixed inset-0 bg-black bg-opacity-60 items-center justify-center z-[60] p-4 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl max-w-2xl w-full">
            <div class="bg-gradient-to-r from-green-600 to-emerald-600 px-6 py-5 flex justify-between items-center rounded-t-xl shadow-lg">
                <h2 class="text-2xl font-bold text-white">Download Command</h2>
                <button
                    onclick="closeCommandModal()"
                    class="text-white hover:text-gray-200 transition-colors"
                    title="Close"
                >
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
            <div class="px-6 py-6">
                <p class="text-gray-700 mb-4">Click the command below to copy it to your clipboard:</p>
                <div class="relative">
                    <input
                        id="commandInput"
                        type="text"
                        readonly
                        class="w-full px-4 py-3 font-mono text-sm bg-gray-50 border-2 border-gray-300 rounded-lg focus:border-green-500 focus:ring-2 focus:ring-green-200 cursor-pointer transition-all"
                        onclick="selectAndCopyCommand()"
                    >
                    <div id="copyFeedback" class="hidden absolute right-3 top-3 bg-green-600 text-white px-3 py-1 rounded-md text-sm font-semibold">
                        Copied!
                    </div>
                </div>
                <p class="text-sm text-gray-500 mt-3">Run this command in your terminal to download the selected video(s).</p>
            </div>
        </div>
    </div>

    <!-- Video Modal -->
    <div id="videoModal" class="modal fixed inset-0 bg-black bg-opacity-60 items-center justify-center z-50 p-4 backdrop-blur-sm">
        <div class="bg-white rounded-xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div class="sticky top-0 bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-5 flex justify-between items-center rounded-t-xl shadow-lg z-10">
                <h2 id="modalTitle" class="text-2xl font-bold text-white"></h2>
                <button
                    onclick="closeModal()"
                    class="text-white hover:text-gray-200 transition-colors"
                    title="Close"
                >
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
            <div id="modalContent" class="px-6 py-6">
                <!-- Populated by JavaScript -->
            </div>
        </div>
    </div>

    <script>
        // Video data
        const videos = {video_data_json};
        let filteredVideos = [...videos];
        let sortState = {{ column: 'id', ascending: true }};
        let selectedVideoIds = new Set();
        let searchTimeout = null;

        // Initialize
        document.addEventListener('DOMContentLoaded', () => {{
            renderTable();
            updateDownloadButton();
            checkHashAndOpenModal();
        }});

        // Handle hash changes (browser back/forward)
        window.addEventListener('hashchange', () => {{
            checkHashAndOpenModal();
        }});

        // Check URL hash and open modal if present
        function checkHashAndOpenModal() {{
            const hash = window.location.hash;
            if (hash && hash.startsWith('#')) {{
                const videoId = parseInt(hash.substring(1));
                if (!isNaN(videoId)) {{
                    const video = videos.find(v => v.id === videoId);
                    if (video) {{
                        openModal(videoId);
                    }}
                }}
            }}
        }}

        // Helper function to clean video paragraphs (remove unwanted content)
        function getCleanParagraphs(video) {{
            return (video.paragraphs || [])
                .filter(p => p && p.trim() && !p.includes('TagBuilder') && !p.includes('Click here to generate'));
        }}

        // Helper function to convert relative URLs to absolute
        function makeAbsoluteUrl(url) {{
            if (!url) return url;
            // If URL starts with http:// or https://, it's already absolute
            if (url.startsWith('http://') || url.startsWith('https://')) {{
                return url;
            }}
            // If URL starts with //, it's protocol-relative
            if (url.startsWith('//')) {{
                return 'https:' + url;
            }}
            // Otherwise, it's relative - prefix with CDVL base URL
            const baseUrl = 'https://www.cdvl.org';
            return url.startsWith('/') ? baseUrl + url : baseUrl + '/' + url;
        }}

        // Debounce utility
        function debounce(func, delay) {{
            return function(...args) {{
                clearTimeout(searchTimeout);
                searchTimeout = setTimeout(() => func.apply(this, args), delay);
            }};
        }}

        // Search functionality with debounce
        function performSearch(query) {{
            // Show spinner
            document.getElementById('searchSpinner').classList.remove('hidden');

            // Filter videos
            filteredVideos = videos.filter(video => {{
                const searchText = [
                    video.id.toString(),
                    video.title || '',
                    video.filename || '',
                    (video.paragraphs || []).join(' ')
                ].join(' ').toLowerCase();
                return searchText.includes(query);
            }});

            // Render and hide spinner
            renderTable();
            updateVideoCount();
            document.getElementById('searchSpinner').classList.add('hidden');
        }}

        document.getElementById('searchInput').addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase();

            // Show spinner immediately for visual feedback
            document.getElementById('searchSpinner').classList.remove('hidden');

            // Debounced search
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {{
                performSearch(query);
            }}, 300); // 300ms delay
        }});

        // Render table
        function renderTable() {{
            const tbody = document.getElementById('videoTableBody');
            tbody.innerHTML = '';

            filteredVideos.forEach(video => {{
                const row = document.createElement('tr');
                row.className = 'hover:bg-gray-50 transition-colors';
                row.id = `video-${{video.id}}`;

                const description = getCleanParagraphs(video).join(' ');
                const excerpt = description.length > 150
                    ? description.substring(0, 150).split(' ').slice(0, -1).join(' ') + '...'
                    : description;

                row.innerHTML = `
                    <td class="px-4 py-3">
                        <input
                            type="checkbox"
                            class="video-checkbox rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                            data-video-id="${{video.id}}"
                            ${{selectedVideoIds.has(video.id) ? 'checked' : ''}}
                            onchange="toggleVideoSelection(${{video.id}}, this.checked)"
                        >
                    </td>
                    <td class="px-4 py-3">
                        <a href="#" onclick="openModal(${{video.id}}); return false;" class="text-blue-600 hover:text-blue-800 font-medium">
                            ${{video.id}}
                        </a>
                    </td>
                    <td class="px-4 py-3">
                        <a href="#" onclick="openModal(${{video.id}}); return false;" class="text-blue-600 hover:text-blue-800 hover:underline">
                            ${{video.title || 'Untitled'}}
                        </a>
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600 font-mono">
                        ${{video.filename || 'N/A'}}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600">
                        ${{video.file_size || 'N/A'}}
                    </td>
                    <td class="px-4 py-3 text-sm text-gray-600">
                        ${{excerpt || 'No description'}}
                    </td>
                `;
                tbody.appendChild(row);
            }});
        }}

        // Sort table
        function sortTable(column) {{
            if (sortState.column === column) {{
                sortState.ascending = !sortState.ascending;
            }} else {{
                sortState.column = column;
                sortState.ascending = true;
            }}

            filteredVideos.sort((a, b) => {{
                let aVal = a[column] || '';
                let bVal = b[column] || '';

                // Handle numeric sorting for id
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

            renderTable();
            updateSortIndicators();
        }}

        function updateSortIndicators() {{
            document.querySelectorAll('.sort-indicator').forEach(el => el.textContent = '');
            const header = event.target.closest('th');
            if (header) {{
                const indicator = header.querySelector('.sort-indicator');
                if (indicator) {{
                    indicator.textContent = sortState.ascending ? ' ↑' : ' ↓';
                }}
            }}
        }}

        // Selection management
        function toggleSelectAll(checked) {{
            filteredVideos.forEach(video => {{
                if (checked) {{
                    selectedVideoIds.add(video.id);
                }} else {{
                    selectedVideoIds.delete(video.id);
                }}
            }});
            renderTable();
            updateDownloadButton();
        }}

        function toggleVideoSelection(videoId, checked) {{
            if (checked) {{
                selectedVideoIds.add(videoId);
            }} else {{
                selectedVideoIds.delete(videoId);
                document.getElementById('selectAll').checked = false;
            }}
            updateDownloadButton();
        }}

        function updateDownloadButton() {{
            const button = document.getElementById('downloadButton');
            if (selectedVideoIds.size > 0) {{
                button.classList.remove('hidden');
                button.textContent = `Generate Download Command (${{selectedVideoIds.size}})`;
            }} else {{
                button.classList.add('hidden');
            }}
        }}

        function updateVideoCount() {{
            const count = document.getElementById('videoCount');
            count.textContent = `${{filteredVideos.length}} of ${{videos.length}} videos`;
        }}

        // Download command generation
        function generateDownloadCommand() {{
            const videoIds = Array.from(selectedVideoIds).sort((a, b) => a - b);
            const command = `uvx cdvl-crawler download ${{videoIds.join(',')}}`;
            showCommandModal(command);
        }}

        // Modal functionality
        function openModal(videoId) {{
            const video = videos.find(v => v.id === videoId);
            if (!video) return;

            // Update URL hash
            if (window.location.hash !== `#${{videoId}}`) {{
                window.history.pushState(null, '', `#${{videoId}}`);
            }}

            document.getElementById('modalTitle').textContent = video.title || 'Video Details';

            const modalContent = document.getElementById('modalContent');
            modalContent.innerHTML = `
                <div class="space-y-6">
                    <!-- Metadata Card -->
                    <div class="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-5 border border-blue-100">
                        <h3 class="text-lg font-bold text-gray-800 mb-4 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                            </svg>
                            Video Information
                        </h3>
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div class="bg-white rounded-md p-3 shadow-sm">
                                <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Video ID</div>
                                <div class="text-lg font-bold text-gray-900">#${{video.id}}</div>
                            </div>
                            ${{video.file_size ? `
                            <div class="bg-white rounded-md p-3 shadow-sm">
                                <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">File Size</div>
                                <div class="text-lg font-semibold text-gray-900">${{video.file_size}}</div>
                            </div>
                            ` : ''}}
                            ${{video.filename ? `
                            <div class="bg-white rounded-md p-3 shadow-sm md:col-span-2">
                                <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Filename</div>
                                <div class="text-sm font-mono text-gray-900 break-all">${{video.filename}}</div>
                            </div>
                            ` : ''}}
                        </div>
                    </div>

                    <!-- Description Section -->
                    <div class="bg-white rounded-lg border border-gray-200 p-5">
                        <h3 class="text-lg font-bold text-gray-800 mb-3 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path>
                            </svg>
                            Description
                        </h3>
                        <div class="space-y-3">
                            ${{getCleanParagraphs(video)
                                .map(p => `<p class="text-gray-700 leading-relaxed">${{p}}</p>`)
                                .join('') || '<p class="text-gray-700">No description available</p>'
                            }}
                        </div>
                    </div>

                    <!-- Related Links -->
                    ${{video.links && video.links.length > 0 ? `
                    <div class="bg-green-50 rounded-lg border border-green-200 p-5">
                        <h3 class="text-lg font-bold text-gray-800 mb-3 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"></path>
                            </svg>
                            Related Links
                        </h3>
                        <ul class="space-y-2">
                            ${{video.links.map(link => `
                                <li class="flex items-start">
                                    <svg class="w-4 h-4 mr-2 mt-1 text-green-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"></path>
                                    </svg>
                                    <a href="${{makeAbsoluteUrl(link.href)}}" target="_blank" class="text-blue-600 hover:text-blue-800 hover:underline break-all">
                                        ${{link.text}}
                                    </a>
                                </li>
                            `).join('')}}
                        </ul>
                    </div>
                    ` : ''}}

                    <!-- Media -->
                    ${{video.media && video.media.length > 0 ? `
                    <div class="bg-purple-50 rounded-lg border border-purple-200 p-5">
                        <h3 class="text-lg font-bold text-gray-800 mb-3 flex items-center">
                            <svg class="w-5 h-5 mr-2 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"></path>
                            </svg>
                            Media
                        </h3>
                        <ul class="space-y-2">
                            ${{video.media.map(m => `
                                <li class="bg-white rounded-md p-3 flex items-center">
                                    <span class="px-2 py-1 bg-purple-100 text-purple-700 rounded text-xs font-semibold mr-3">${{m.type}}</span>
                                    <span class="text-sm text-gray-700 break-all">${{m.src}}</span>
                                </li>
                            `).join('')}}
                        </ul>
                    </div>
                    ` : ''}}

                    <!-- URL and Metadata Footer -->
                    <div class="bg-gray-50 rounded-lg border border-gray-200 p-5">
                        <div class="space-y-3">
                            <div>
                                <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Source URL</div>
                                <a href="${{video.url}}" target="_blank" class="text-blue-600 hover:text-blue-800 hover:underline break-all text-sm">
                                    ${{video.url}}
                                </a>
                            </div>
                            <div>
                                <div class="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">Extracted At</div>
                                <div class="text-sm text-gray-600">${{video.extracted_at}}</div>
                            </div>
                        </div>
                    </div>

                    <!-- Action Button -->
                    <div class="sticky bottom-0 bg-white pt-4 pb-2 border-t border-gray-200 -mx-6 px-6">
                        <button
                            onclick="downloadSingleVideo(${{video.id}})"
                            class="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white px-6 py-3 rounded-lg transition-all font-semibold shadow-lg hover:shadow-xl transform hover:-translate-y-0.5"
                        >
                            <svg class="w-5 h-5 inline-block mr-2 -mt-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-3m-1 4l-3 3m0 0l-3-3m3 3V4"></path>
                            </svg>
                            Generate Download Command for This Video
                        </button>
                    </div>
                </div>
            `;

            document.getElementById('videoModal').classList.add('active');
        }}

        function closeModal() {{
            document.getElementById('videoModal').classList.remove('active');
            // Clear URL hash
            if (window.location.hash) {{
                window.history.pushState(null, '', window.location.pathname);
            }}
        }}

        function downloadSingleVideo(videoId) {{
            const command = `uvx cdvl-crawler download ${{videoId}}`;
            showCommandModal(command);
        }}

        // Command modal functionality
        function showCommandModal(command) {{
            const input = document.getElementById('commandInput');
            input.value = command;
            document.getElementById('commandModal').classList.add('active');
        }}

        function closeCommandModal() {{
            document.getElementById('commandModal').classList.remove('active');
        }}

        function selectAndCopyCommand() {{
            const input = document.getElementById('commandInput');
            input.select();
            input.setSelectionRange(0, 99999); // For mobile devices

            navigator.clipboard.writeText(input.value).then(() => {{
                // Show feedback
                const feedback = document.getElementById('copyFeedback');
                feedback.classList.remove('hidden');
                setTimeout(() => {{
                    feedback.classList.add('hidden');
                }}, 2000);
            }}).catch(err => {{
                console.error('Failed to copy:', err);
            }});
        }}

        // Close modals on escape key
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') {{
                closeModal();
                closeCommandModal();
            }}
        }});

        // Close modals on backdrop click
        document.getElementById('videoModal').addEventListener('click', (e) => {{
            if (e.target.id === 'videoModal') {{
                closeModal();
            }}
        }});

        document.getElementById('commandModal').addEventListener('click', (e) => {{
            if (e.target.id === 'commandModal') {{
                closeCommandModal();
            }}
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
