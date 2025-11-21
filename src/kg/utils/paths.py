"""
Utility helpers for resolving data directories for different graph topics.

All modules accept either:
  - --graph-name (e.g., "cancer", "pokemon")
  - --data-location (e.g., "data/cancer", "demos/pokemon")

Exactly one of these must be provided by the caller. This helper resolves the
base directory and can optionally create it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def resolve_base_dir(graph_name: Optional[str], data_location: Optional[str], *, create: bool = False) -> Path:
    """
    Resolve the base directory from either graph_name or data_location.

    Priority:
        1) data_location (explicit path)
        2) graph_name    (joined under data/{graph_name})

    Raises:
        SystemExit if neither is provided.
    """
    if data_location:
        base = Path(data_location)
    elif graph_name:
        base = Path("data") / graph_name
    else:
        raise SystemExit("Please provide either --graph-name or --data-location.")

    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base.resolve()
