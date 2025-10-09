"""CDVL Crawler - Tools for crawling and downloading videos from cdvl.org"""

import importlib.metadata

from cdvl_crawler.crawler import CDVLCrawler
from cdvl_crawler.downloader import CDVLDownloader

__version__ = importlib.metadata.version("cdvl_crawler")

__all__ = ["CDVLCrawler", "CDVLDownloader"]
