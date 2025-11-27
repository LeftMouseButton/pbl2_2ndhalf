from __future__ import annotations

"""
Config loading utilities for topic-agnostic Module 6.

This module reads per-graph configuration from:

    data/{graph}/config/nodes.ini
    data/{graph}/config/edges.ini

and exposes:
    - structured node/edge type configs
    - simple, deterministic color maps for node and edge types

The INI formats are intentionally lightweight. Examples:

    # nodes.ini
    vtuber: name, synonyms, description
    agency: name
    game: name, genre, developer

    # edges.ini
    belongs_to: vtuber -> agency
    collaborated_with: vtuber -> vtuber | hours, times
    played: vtuber -> game | hours_streamed
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class NodeTypeConfig:
    """Configuration for a single node type."""

    type_name: str
    attributes: List[str]


@dataclass
class EdgeTypeConfig:
    """Configuration for a single edge / relation type."""

    relation: str
    source_type: str
    target_type: str
    properties: List[str]


def _parse_nodes_ini(path: Path) -> Dict[str, NodeTypeConfig]:
    """
    Parse nodes.ini into a mapping: node_type -> NodeTypeConfig.
    Lines support comments (#) and must follow:

        node_type: attr1, attr2, attr3
    """
    cfg: Dict[str, NodeTypeConfig] = {}

    if not path.exists():
        print(f"[INFO] No nodes.ini found at {path} – proceeding without node-type config.")
        return cfg

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            print(f"[WARN] Skipping invalid nodes.ini line (missing ':'): {raw}")
            continue

        left, right = line.split(":", 1)
        ntype = left.strip()
        attrs = [a.strip() for a in right.split(",") if a.strip()]

        if not ntype:
            print(f"[WARN] Skipping nodes.ini line with empty type: {raw}")
            continue

        cfg[ntype] = NodeTypeConfig(type_name=ntype, attributes=attrs)

    return cfg


def _parse_edges_ini(path: Path) -> Dict[str, EdgeTypeConfig]:
    """
    Parse edges.ini into mapping: relation_name -> EdgeTypeConfig.
    Format:

        relation: source_type -> target_type
        relation: source_type -> target_type | prop1, prop2
    """
    cfg: Dict[str, EdgeTypeConfig] = {}

    if not path.exists():
        print(f"[INFO] No edges.ini found at {path} – proceeding without edge-type config.")
        return cfg

    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        if ":" not in line:
            print(f"[WARN] Skipping invalid edges.ini line (missing ':'): {raw}")
            continue

        left, rest = line.split(":", 1)
        relation = left.strip()
        if not relation:
            print(f"[WARN] Skipping edges.ini line with empty relation: {raw}")
            continue

        # Split "source_type -> target_type | props"
        parts = rest.split("|", 1)
        arrow_part = parts[0].strip()
        props_part = parts[1].strip() if len(parts) > 1 else ""

        if "->" not in arrow_part:
            print(f"[WARN] Skipping edges.ini line (missing '->'): {raw}")
            continue

        src_str, tgt_str = arrow_part.split("->", 1)
        src_type = src_str.strip()
        tgt_type = tgt_str.strip()
        if not src_type or not tgt_type:
            print(f"[WARN] Skipping edges.ini line with empty source/target: {raw}")
            continue

        props = [p.strip() for p in props_part.split(",") if p.strip()] if props_part else []

        cfg[relation] = EdgeTypeConfig(
            relation=relation,
            source_type=src_type,
            target_type=tgt_type,
            properties=props,
        )

    return cfg


def load_graph_config(base_dir: Path) -> Tuple[Dict[str, NodeTypeConfig], Dict[str, EdgeTypeConfig]]:
    """
    Load node/edge type configuration for a given graph base directory.

    Parameters
    ----------
    base_dir : Path
        Typically data/{graph-name}.
    """
    config_dir = base_dir / "config"
    nodes_path = config_dir / "nodes.ini"
    edges_path = config_dir / "edges.ini"

    node_cfg = _parse_nodes_ini(nodes_path)
    edge_cfg = _parse_edges_ini(edges_path)

    if not node_cfg:
        print(f"[INFO] No node-type definitions loaded from {nodes_path}.")
    if not edge_cfg:
        print(f"[INFO] No edge-type definitions loaded from {edges_path}.")

    return node_cfg, edge_cfg


NODE_COLOR_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]

EDGE_COLOR_PALETTE = [
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#a65628",
    "#f781bf",
    "#999999",
]


def build_color_maps(
    node_cfg: Dict[str, NodeTypeConfig],
    edge_cfg: Dict[str, EdgeTypeConfig],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """
    Construct simple color maps for node and edge types.

    Returns
    -------
    (color_by_type, edge_color_map)
    """
    color_by_type: Dict[str, str] = {}
    edge_color_map: Dict[str, str] = {}

    # Node types: deterministic mapping based on sorted type names
    for i, ntype in enumerate(sorted(node_cfg.keys())):
        color_by_type[ntype] = NODE_COLOR_PALETTE[i % len(NODE_COLOR_PALETTE)]

    # Edge types: deterministic mapping based on sorted relation names
    for i, relation in enumerate(sorted(edge_cfg.keys())):
        edge_color_map[relation] = EDGE_COLOR_PALETTE[i % len(EDGE_COLOR_PALETTE)]

    return color_by_type, edge_color_map

