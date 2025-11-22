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
# Load SCHEMA_KEYS dynamically from schema/schema_keys.json
# ─────────────────────────────────────────────────────────────────────────────

def _load_schema_keys() -> list[str]:
    """
    Load the top-level keys used by all disease JSON records.

    Returns
    -------
    List[str]
        The ordered list of schema keys, extracted from the JSON file.

    Raises
    ------
    FileNotFoundError
    JSONDecodeError
    ValueError
    """
    # Resolution order (aligned with other modules):
    #   1) Explicit env var KG_SCHEMA_PATH
    #   2) Env var KG_GRAPH_NAME -> data/{graph}/schema/schema_keys.json
    #   3) Direct path at data/{graph}/schema/schema_keys.json if KG_GRAPH_NAME unset and cwd encodes it
    env_path = os.getenv("KG_SCHEMA_PATH")
    graph_name = os.getenv("KG_GRAPH_NAME")

    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    if graph_name:
        candidates.append(Path("data") / graph_name / "schema" / "schema_keys.json")

    # If neither env var is set, require a graph name to be provided.
    if not graph_name and not env_path:
        raise FileNotFoundError("Schema file not found. Set KG_SCHEMA_PATH or KG_GRAPH_NAME.")

    schema_path = next((p for p in candidates if p and p.exists()), None)
    if schema_path is None:
        raise FileNotFoundError(
            "Schema file not found. Set KG_SCHEMA_PATH or KG_GRAPH_NAME, "
            "or ensure data/{graph_name}/schema/schema_keys.json exists."
        )

    data = json.loads(schema_path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError(f"schema_keys.json must contain a JSON object, got: {type(data)}")

    # The schema keys are simply the key names of the object
    return list(data.keys())


# The authoritative list of schema keys for all modules
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
