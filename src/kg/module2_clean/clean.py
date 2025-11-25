"""
Module 2 – Cleaning / Preprocessing (Revised)
--------------------------------------------
Converts raw HTML or plain-text files (from Module 1) into normalized,
clean text suitable for LLM-based entity extraction (Module 3).

Strict trimming rules (per specification):

  - Always remove everything BEFORE the line containing "- Patient Handouts"
    (inclusive of that line).
  - Always remove everything AFTER AND INCLUDING the first occurrence of
    "## Start Here".

These rules are applied on the cleaned text representation. For sources that
do not contain these markers, the cleaner behaves conservatively.

Outputs:
    data/processed/*.txt          (normalized text)
    data/processed/metadata.jsonl (checksum + provenance)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, Any

import hashlib
import html as html_lib
import re
import time
import pkgutil
import importlib

from src.kg.module2_clean.sources.registry import REGISTERED_CLEANERS
import src.kg.module2_clean.sources as cleaner_pkg

# Auto-discover all cleaner modules at runtime
for _, module_name, _ in pkgutil.iter_modules(cleaner_pkg.__path__):
    importlib.import_module(f"src.kg.module2_clean.sources.{module_name}")

from bs4 import BeautifulSoup
from slugify import slugify

from src.kg.utils.paths import resolve_base_dir

# ---------------------------------------------------------------------------
# Paths (configured at runtime)
# ---------------------------------------------------------------------------

BASE_DIR: Path | None = None
RAW_DIR: Path | None = None
RAW_META_PATH: Path | None = None
OUT_DIR: Path | None = None
META_PATH: Path | None = None


def configure_paths(base_dir: Path) -> None:
    """Initialize module-level paths for the selected graph/topic."""
    global BASE_DIR, RAW_DIR, RAW_META_PATH, OUT_DIR, META_PATH
    BASE_DIR = base_dir
    RAW_DIR = BASE_DIR / "raw"
    RAW_META_PATH = RAW_DIR / "metadata.jsonl"
    OUT_DIR = BASE_DIR / "processed"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    META_PATH = OUT_DIR / "metadata.jsonl"


def require_paths() -> tuple[Path, Path, Path, Path]:
    """Return configured paths or raise if unset."""
    if not all([BASE_DIR, RAW_DIR, RAW_META_PATH, OUT_DIR, META_PATH]):
        raise RuntimeError("Paths not configured. Call configure_paths(...) first.")
    # TYPE CHECK: mypy ignore; runtime ensures non-None
    return RAW_DIR, RAW_META_PATH, OUT_DIR, META_PATH  # type: ignore


#
#   Logging/etc
#

def log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"[{ts}] {msg}")


def checksum(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ---------------------------------------------------------------------------
# File-level processing
# ---------------------------------------------------------------------------

def derive_name_and_source(stem: str) -> (str, str):
    """
    Derive entity prefix and source suffix from filename stem.

    Expected pattern from Module 1:
        {slug}_{source}
    """
    s = stem.lower()
    if "_" in s:
        disease_part, source_part = s.rsplit("_", 1)
    elif "-" in s:
        disease_part, source_part = s.rsplit("-", 1)
    else:
        disease_part, source_part = s, "unknown"

    entity = slugify(disease_part) or "unknown"
    source = slugify(source_part) or "unknown"
    return entity, source


def process_file(raw_path: Path) -> Dict[str, Any]:
    """
    Process a single raw file into cleaned text and write metadata.
    """
    _, _, out_dir, meta_path = require_paths()
    try:
        raw_content = raw_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log(f"[ERROR] Failed to read {raw_path}: {e}")
        return {
            "source_filename": raw_path.name,
            "error": f"read_failed: {e}",
        }

    # Determine source based on filename
    _, source = derive_name_and_source(raw_path.stem)

    # Run through registered cleaner (or fallback)
    cleaner_fn = REGISTERED_CLEANERS.get(source, REGISTERED_CLEANERS.get("default"))
    cleaned = cleaner_fn(raw_content, raw_path.suffix.lower())

    entity, source = derive_name_and_source(raw_path.stem)
    out_name = f"{entity}_-_{source}.txt"
    out_path = out_dir / out_name

    try:
        out_path.write_text(cleaned, encoding="utf-8")
    except Exception as e:
        log(f"[ERROR] Failed to write cleaned file for {raw_path.name}: {e}")
        return {
            "source_filename": raw_path.name,
            "processed_filename": out_name,
            "error": f"write_failed: {e}",
        }

    record: Dict[str, Any] = {
        "source_filename": raw_path.name,
        "processed_filename": out_name,
        "entity_slug": entity,
        "source_slug": source,
        "raw_checksum": checksum(raw_content),
        "clean_checksum": checksum(cleaned),
        "clean_length": len(cleaned),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    try:
        with meta_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        log(f"[WARN] Failed to append metadata for {raw_path.name}: {e}")

    log(f"[OK] {raw_path.name} → {out_name}")
    return record


def process_all(raw_dir: Path | None = None) -> None:
    """Iterate through all files in raw_dir and clean them."""
    if raw_dir is None:
        raw_dir = require_paths()[0]
    if not raw_dir.exists():
        log(f"[ERROR] Raw directory not found: {raw_dir}")
        return

    log("[INFO] Starting cleaning process...")
    n_total = 0
    n_processed = 0

    for path in sorted(raw_dir.glob("*")):
        if not path.is_file():
            continue

        n_total += 1
        rec = process_file(path)
        if "error" not in rec:
            n_processed += 1

    log(f"[INFO] Cleaning complete. Processed {n_processed}/{n_total} files.")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Module 2 – clean/preprocess raw text for any graph topic.")
    p.add_argument(
        "--graph-name",
        help="Name of the graph/topic (uses data/{graph-name} as base).",
    )
    p.add_argument(
        "--data-location",
        help="Explicit data directory (takes precedence over --graph-name).",
    )
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base = resolve_base_dir(args.graph_name, args.data_location, create=True)
    configure_paths(base)
    process_all()
