# src/kg/module6_analysis/utils/constants.py

"""
Shared constants for Module 6 analysis.

This module now loads the canonical JSON schema dynamically from:
    schema/schema_keys.json

This prevents hard-coding and ensures all modules remain synchronized
with the authoritative schema file.
"""

from __future__ import annotations
import os
import json
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Load SCHEMA_KEYS dynamically (but never crash if missing)
# ─────────────────────────────────────────────────────────────────────────────

def _load_schema_keys() -> list[str]:
    """
    Load the top-level keys used by JSON records, if a schema file is available.

    For backwards compatibility this function is intentionally forgiving:
    if no schema can be found or parsed, it returns an empty list rather than
    raising an exception. This keeps Module 6 usable for arbitrary topics.
    """
    env_path = os.getenv("KG_SCHEMA_PATH")
    graph_name = os.getenv("KG_GRAPH_NAME")

    candidates: list[Path] = []
    if env_path:
        candidates.append(Path(env_path))
    if graph_name:
        # Newer topic-agnostic layout
        candidates.append(Path("data") / graph_name / "config" / "schema_keys.json")
        # Legacy layout (cancer project)
        candidates.append(Path("data") / graph_name / "schema" / "schema_keys.json")

    for schema_path in candidates:
        if not schema_path.exists():
            continue
        try:
            data = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Failed to parse schema keys from {schema_path}: {e}")
            return []

        if not isinstance(data, dict):
            print(f"[WARN] schema_keys.json must contain an object, got {type(data)} at {schema_path}")
            return []

        return list(data.keys())

    # No schema configured; this is expected for many topics.
    return []


# The (optional) list of schema keys for all modules.
SCHEMA_KEYS: list[str] = _load_schema_keys()


# ─────────────────────────────────────────────────────────────────────────────
# Node type identifiers
# ─────────────────────────────────────────────────────────────────────────────

NODE_TYPES = {
    "disease": "disease",
    "symptom": "symptom",
    "treatment": "treatment",
    "gene": "gene",
    "diagnosis": "diagnosis",
    "cause": "cause",
    "risk_factor": "risk_factor",
    "subtype": "subtype",
}

# ─────────────────────────────────────────────────────────────────────────────
# Edge type definitions
# ─────────────────────────────────────────────────────────────────────────────

EDGE_TYPES = {
    "has_symptom": ("disease", "symptom"),
    "treated_with": ("disease", "treatment"),
    "associated_gene": ("disease", "gene"),
    "has_diagnosis": ("disease", "diagnosis"),
    "has_cause": ("disease", "cause"),
    "has_risk_factor": ("disease", "risk_factor"),
    "has_subtype": ("disease", "subtype"),
}

# ─────────────────────────────────────────────────────────────────────────────
# Visualization colors
# ─────────────────────────────────────────────────────────────────────────────

COLOR_BY_TYPE = {
    "disease": "#1f77b4",
    "gene": "#9467bd",
    "treatment": "#2ca02c",
    "symptom": "#d62728",
    "diagnosis": "#17becf",
    "risk_factor": "#ff7f0e",
    "cause": "#8c564b",
    "subtype": "#7f7f7f",
}

# Default cap for large graph safety
MAX_NODES_DEFAULT = 10_000
