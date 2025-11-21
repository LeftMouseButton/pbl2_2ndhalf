# src/kg/module6_analysis/loader/records_loader.py

"""
Record loading utilities for Module 6.

This module loads records from either:
1. A combined JSON file with a top-level "records" (preferred) or "diseases" list.
2. A directory of individual JSON files (one per entity).

Each JSON object must contain at least "disease_name" or "name".
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict


def _load_combined(path: Path) -> List[Dict]:
    """
    Load a combined JSON file containing: {"records": [ ... ]} (preferred) or {"diseases": [...]}.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    records = None
    if isinstance(data, dict) and "records" in data:
        records = data["records"]
    elif isinstance(data, dict) and "diseases" in data:
        records = data["diseases"]
    if isinstance(records, list):
        normalized = []
        for rec in records:
            if isinstance(rec, dict):
                if "disease_name" not in rec and "name" in rec:
                    rec["disease_name"] = rec.get("name")
                normalized.append(rec)
        return normalized
    raise ValueError("Combined file must contain a top-level 'records' or 'diseases' list.")


def _load_dir(path: Path) -> List[Dict]:
    """
    Load multiple JSON files from a directory.
    """
    records: List[Dict] = []

    for p in sorted(path.glob("*.json")):
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict):
                if "disease_name" not in obj and obj.get("name"):
                    obj["disease_name"] = obj.get("name")
                if obj.get("disease_name"):
                    records.append(obj)
            else:
                records.append(obj)
        except json.JSONDecodeError:
            print(f"[WARN] Skipping invalid JSON: {p}")

    if not records:
        raise ValueError(f"No valid disease JSON files found in directory: {path}")

    return records


def load_records(input_path: str) -> List[Dict]:
    """
    Unified entry point.

    Parameters
    ----------
    input_path : str
        Either a JSON file path or a directory containing JSON files.

    Returns
    -------
    List[dict]
        A list of disease records.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(path)

    if path.is_dir():
        return _load_dir(path)

    return _load_combined(path)
