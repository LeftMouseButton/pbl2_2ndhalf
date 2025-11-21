"""
Module 1 – Web Crawler (topic-agnostic)
---------------------------------------
Delegates source-specific crawling to submodules under src/kg/module1_crawler/sources.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import hashlib
import json
import re
import time

import requests

import pkgutil
import importlib
from src.kg.module1_crawler.sources.registry import REGISTERED_SOURCES
import src.kg.module1_crawler.sources as sources_pkg

# Auto-load all crawler modules from the sources package
for _, module_name, _ in pkgutil.iter_modules(sources_pkg.__path__):
    importlib.import_module(f"src.kg.module1_crawler.sources.{module_name}")

from src.kg.utils.paths import resolve_base_dir


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class CrawlerConfig:
    base_dir: Path
    raw_dir: Path
    names_file: Path
    metadata_path: Path
    enabled_sources: Dict[str, bool]

    user_agent: str = "DSGT-KG-Crawler/2.0 (+https://example.org)"
    timeout: int = 20
    max_retries: int = 3
    backoff_initial: float = 1.0
    backoff_factor: float = 2.0
    sleep_between_requests: float = 1.0

    


CONFIG: CrawlerConfig | None = None
SESSION: requests.Session | None = None

SOURCE_RELIABILITY = {
    name: meta["reliability"]
    for name, meta in REGISTERED_SOURCES.items()
}


# =============================================================================
# Utilities
# =============================================================================


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}")


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def require_config() -> CrawlerConfig:
    if CONFIG is None:
        raise RuntimeError("Crawler config not initialized. Call initialize_config().")
    return CONFIG


def load_names(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"{path} not found")
    with path.open("r", encoding="utf-8") as f:
        names = [line.strip() for line in f if line.strip()]
    if not names:
        raise ValueError(f"No names found in {path}")
    return names


def slugify_name(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = s.replace("-", "_")
    s = re.sub(r"[^\w_]+", "", s)
    return s or "unknown"


def write_metadata(record: Dict[str, Any], meta_path: Optional[Path] = None) -> None:
    cfg = require_config()
    target = meta_path or cfg.metadata_path
    with target.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_file(content: str, path: Path) -> None:
    path.write_text(content, encoding="utf-8")
    log(f"Saved: {path}")


def http_get_with_retries(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    backoff_initial: Optional[float] = None,
    backoff_factor: Optional[float] = None,
    session: Optional[requests.Session] = None,
    cfg: Optional[CrawlerConfig] = None,
) -> Tuple[Optional[requests.Response], Optional[int]]:
    cfg = cfg or require_config()
    delay = backoff_initial or cfg.backoff_initial
    max_retries = max_retries or cfg.max_retries
    timeout = timeout or cfg.timeout
    backoff_factor = backoff_factor or cfg.backoff_factor
    last_status = None

    for attempt in range(1, max_retries + 1):
        try:
            sess = session or SESSION
            if sess is None:
                raise RuntimeError("HTTP session not initialized.")
            r = sess.get(url, params=params, timeout=timeout)
            last_status = r.status_code
            if 500 <= r.status_code < 600:
                log(f"HTTP {r.status_code} for {url} (attempt {attempt}); retrying in {delay:.1f}s")
            else:
                return r, last_status
        except requests.RequestException as e:
            log(f"Request error for {url} (attempt {attempt}): {e}")
        if attempt < max_retries:
            time.sleep(delay)
            delay *= backoff_factor
    log(f"Giving up on {url} after {max_retries} attempts")
    return None, last_status


# =============================================================================
# Crawl orchestration
# =============================================================================


def crawl_all() -> None:
    cfg = require_config()
    names = load_names(cfg.names_file)
    log(f"Loaded {len(names)} names from {cfg.names_file}")

    helpers = {
        "log": log,
        "checksum": checksum,
        "slugify_name": slugify_name,
        "save_file": save_file,
        "write_metadata": write_metadata,
        "http_get_with_retries": http_get_with_retries,
        "SOURCE_RELIABILITY": SOURCE_RELIABILITY,
    }

    # AUTO-GENERATED SOURCE PIPELINE (dynamic)
    source_pipeline = []
    for src_name, meta in REGISTERED_SOURCES.items():
        if cfg.enabled_sources.get(src_name, meta["enabled_by_default"]):
            source_pipeline.append((src_name, True, meta["fn"]))
        else:
            source_pipeline.append((src_name, False, meta["fn"]))

    for name in names:
        log(f"=== Processing entry: {name} ===")
        for label, enabled, fn in source_pipeline:
            if not enabled:
                continue
            try:
                fn(cfg, SESSION, helpers, name)
            except Exception as e:
                log(f"[ERROR] {label} crawl failed for '{name}': {e}")

    log("Crawl complete.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Module 1 – topic-agnostic web crawler.")
    p.add_argument("--graph-name", help="Name of the graph/topic (uses data/{graph-name} as base).")
    p.add_argument("--data-location", help="Explicit data directory (takes precedence over --graph-name).")
    p.add_argument("--names-file", help="Optional override for the names.txt file (defaults to {base}/names.txt).")
    all_sources = list(REGISTERED_SOURCES.keys())
    p.add_argument(
        "--sources",
        nargs="+",
        choices=all_sources,
        default=[],  # no sources enabled by default
        help="Sources to crawl for this topic.",
    )
    return p.parse_args()


def initialize_config(args: argparse.Namespace) -> None:
    global CONFIG, SESSION

    base_dir = resolve_base_dir(args.graph_name, args.data_location, create=True)
    raw_dir = base_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    names_path = Path(args.names_file) if args.names_file else base_dir / "names.txt"
    metadata_path = raw_dir / "metadata.jsonl"

    enabled = {}
    for src in REGISTERED_SOURCES.keys():
        enabled[src] = (src in args.sources)

    CONFIG = CrawlerConfig(
        base_dir=base_dir,
        raw_dir=raw_dir,
        names_file=names_path,
        metadata_path=metadata_path,
        enabled_sources=enabled,
    )

    SESSION = requests.Session()
    SESSION.headers.update({"User-Agent": CONFIG.user_agent})


if __name__ == "__main__":
    args = parse_args()
    initialize_config(args)
    crawl_all()
