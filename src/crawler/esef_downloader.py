"""
Download and cache ESEF report packages (zip files containing the XHTML +
iXBRL + taxonomy extension) discovered via filings_index.py.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import requests

from config.settings import DATA_RAW_DIR
from src.crawler.filings_index import FilingRecord


def _cache_path_for(record: FilingRecord) -> Path:
    key = f"{record.entity_name}_{record.period_end}".replace(" ", "_")
    digest = hashlib.sha1(record.package_url.encode()).hexdigest()[:8]
    return DATA_RAW_DIR / f"{key}_{digest}.zip"


def download_filing(record: FilingRecord, force: bool = False) -> Path:
    """
    Download the ESEF zip package for a filing, with simple on-disk caching
    so re-running the crawler doesn't re-fetch unchanged filings.
    """
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    dest = _cache_path_for(record)

    if dest.exists() and not force:
        return dest

    resp = requests.get(record.package_url, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest
