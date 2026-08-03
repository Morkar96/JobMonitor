"""Simple JSON-file storage for tracking which job URLs we've already seen,
per site, so re-runs only report genuinely new postings."""

import json
import os
from datetime import datetime, timezone

from config import STORAGE_PATH


def _ensure_dir():
    os.makedirs(os.path.dirname(STORAGE_PATH), exist_ok=True)


def load() -> dict:
    _ensure_dir()
    if not os.path.exists(STORAGE_PATH):
        return {}
    with open(STORAGE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save(data: dict):
    _ensure_dir()
    with open(STORAGE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_first_run(data: dict, site_name: str) -> bool:
    return site_name not in data


def get_seen_urls(data: dict, site_name: str) -> set:
    return set(data.get(site_name, {}).get("seen_urls", []))


def update_site(data: dict, site_name: str, all_urls: set):
    existing = data.get(site_name, {})
    seen = set(existing.get("seen_urls", [])) | all_urls
    data[site_name] = {
        "seen_urls": sorted(seen),
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "first_seen": existing.get("first_seen", datetime.now(timezone.utc).isoformat()),
    }
