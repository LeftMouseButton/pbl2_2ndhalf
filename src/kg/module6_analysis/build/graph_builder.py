# src/kg/module6_analysis/build/graph_builder.py

"""
Graph construction utilities for Module 6.

This module is responsible ONLY for:
  - building a NetworkX graph from disease JSON records
  - assigning node labels and types
  - creating typed edges between entities
  - returning basic build statistics

It deliberately does NOT perform any analysis (centrality, communities, etc.),
keeping a clean separation of concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
from typing import Any, Dict, List, Tuple, Optional

import re
import networkx as nx

from ..utils.constants import NODE_TYPES
from ..utils.normalize import _norm
from ..utils.config_loader import EdgeTypeConfig


@dataclass
class BuildStats:
    n_nodes: int
    n_edges: int
    types: Counter


def _add_node(G: nx.Graph, name: str, ntype: str, **attrs: Any) -> None:
    key = _norm(name)
    if not key:
        return

    if key in G:
        if not G.nodes[key].get("label"):
            G.nodes[key]["label"] = (name or "").strip()
        if "type" not in G.nodes[key]:
            G.nodes[key]["type"] = ntype
        for k, v in attrs.items():
            G.nodes[key].setdefault(k, v)
    else:
        G.add_node(
            key,
            label=(name or "").strip(),
            type=ntype,
            **attrs,
        )


def _add_edge(G: nx.Graph, a: str, b: str, etype: str, weight: float | None = None) -> None:
    if not a or not b:
        return

    u = _norm(a)
    v = _norm(b)
    if not u or not v:
        return

    if G.has_edge(u, v):
        # preserve the max weight if multiple contributions exist
        existing = G[u][v].get("weight")
        if weight is not None:
            if existing is None or weight > existing:
                G[u][v]["weight"] = weight
    else:
        attrs = {"type": etype}
        if weight is not None:
            attrs["weight"] = weight
        G.add_edge(u, v, **attrs)


def _slugify(text: str) -> str:
    """
    Create a stable slug identifier for graph nodes.

    Mirrors the behavior of module1_crawler.slugify_name() so that
    entity IDs and relationship endpoints like "hoshimachi_suisei"
    line up correctly.
    """
    if not isinstance(text, str):
        text = str(text)
    s = text.strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = s.replace("-", "_")
    s = re.sub(r"[^\w_]+", "", s)
    return s or "unknown"


def _add_graph_document_record(
    G: nx.Graph,
    rec: Dict[str, Any],
    edge_cfg: Optional[Dict[str, EdgeTypeConfig]] = None,
) -> None:
    """
    Build graph nodes/edges from a graph-style record:
        { "entities": [...], "relationships": [...] }

    Behavior (topic-agnostic):
      - Node IDs are slugified from entity IDs/names.
      - Node labels come from entity.name (or id) and are preserved.
      - Attributes are flattened so that both values and confidences are stored:
            attr -> value
            attr_confidence -> confidence
      - A top-level entity "confidence" is stored as node["confidence"].
      - Relationships use:
            edge["type"]      = relation name
            edge["confidence"] = relationship confidence
            edge["weight"]     = relationship confidence   (for weighted analysis)
        and relationship properties are flattened similarly to node attributes.
      - If edges.ini is available, it is used to infer node types for nodes
        that appear only in relationships.
    """
    entities = rec.get("entities") or []
    rels = rec.get("relationships") or []

    # Index entities by slug so we can align them with relationship endpoints.
    ent_by_slug: Dict[str, Dict[str, Any]] = {}
    for ent in entities:
        ent_id = ent.get("id") or ent.get("name")
        if not ent_id:
            continue
        slug = _slugify(ent_id)
        if slug not in ent_by_slug:
            ent_by_slug[slug] = ent

    def ensure_node(
        slug: str,
        *,
        fallback_label: Optional[str] = None,
        fallback_type: Optional[str] = None,
    ) -> None:
        """
        Ensure that a node with the given slug exists.

        If an entity definition is available, use it to populate attributes;
        otherwise, create a minimal node using fallbacks.
        """
        if G.has_node(slug):
            # Fill in missing basic attributes if we can.
            ndata = G.nodes[slug]
            if fallback_type and not ndata.get("type"):
                ndata["type"] = fallback_type
            if fallback_label and not ndata.get("label"):
                ndata["label"] = fallback_label
            return

        ent = ent_by_slug.get(slug)
        if ent:
            ntype = ent.get("type", "entity")
            label = ent.get("name") or ent.get("id") or slug
            attrs: Dict[str, Any] = {
                "type": ntype,
                "label": label,
            }
            # Top-level confidence
            conf = ent.get("confidence")
            if isinstance(conf, (int, float)):
                attrs["confidence"] = float(conf)

            # Flatten nested attributes: key -> value, key_confidence -> confidence
            ent_attrs = ent.get("attributes") or {}
            if isinstance(ent_attrs, dict):
                for key, payload in ent_attrs.items():
                    if not isinstance(payload, dict):
                        continue
                    val = payload.get("value")
                    conf_attr = payload.get("confidence")
                    attrs[key] = val
                    if conf_attr is not None:
                        attrs[f"{key}_confidence"] = conf_attr
        else:
            # No entity definition: synthesize a minimal node.
            label = fallback_label or slug.replace("_", " ").title()
            ntype = fallback_type or "entity"
            attrs = {
                "type": ntype,
                "label": label,
            }

        G.add_node(slug, **attrs)

    # First, add all entity-defined nodes.
    for slug in ent_by_slug.keys():
        ensure_node(slug)

    # Then, add edges and any missing nodes referenced only in relationships.
    for rel in rels:
        src_raw = rel.get("source")
        tgt_raw = rel.get("target")
        if not (src_raw and tgt_raw):
            continue

        src = str(src_raw)
        tgt = str(tgt_raw)

        relation = rel.get("relation") or rel.get("type") or "related"
        edge_type_cfg: Optional[EdgeTypeConfig] = (edge_cfg or {}).get(relation)
        src_type = edge_type_cfg.source_type if edge_type_cfg else None
        tgt_type = edge_type_cfg.target_type if edge_type_cfg else None

        # Ensure endpoints exist; if they are not part of entities, infer type/label.
        ensure_node(src, fallback_type=src_type)
        ensure_node(tgt, fallback_type=tgt_type)

        # Build edge attributes.
        eattrs: Dict[str, Any] = {"type": relation}
        e_conf = rel.get("confidence")
        if isinstance(e_conf, (int, float)):
            eattrs["confidence"] = float(e_conf)
            eattrs["weight"] = float(e_conf)

        props = rel.get("properties") or {}
        if isinstance(props, dict):
            for key, payload in props.items():
                if not isinstance(payload, dict):
                    continue
                val = payload.get("value")
                conf_prop = payload.get("confidence")
                eattrs[key] = val
                if conf_prop is not None:
                    eattrs[f"{key}_confidence"] = conf_prop

        if G.has_edge(src, tgt):
            # Preserve max weight if multiple relationships aggregate on the same pair.
            if "weight" in eattrs:
                new_w = eattrs["weight"]
                existing_w = G[src][tgt].get("weight")
                if existing_w is None or (isinstance(new_w, (int, float)) and new_w > existing_w):
                    G[src][tgt]["weight"] = new_w
            continue

        G.add_edge(src, tgt, **eattrs)


def build_graph(
    records: List[Dict[str, Any]],
    node_config: Optional[Dict[str, Any]] = None,
    edge_config: Optional[Dict[str, EdgeTypeConfig]] = None,
) -> Tuple[nx.Graph, BuildStats]:
    """
    Build a heterogeneous graph from combined JSON records.

    For new topic-agnostic graphs (VTubers, games, etc.) this function expects
    at least one record with explicit "entities" and "relationships" fields
    and constructs the graph directly from that information. Legacy disease-
    style records are still supported via the older NODE_TYPES-based branch.
    """
    G = nx.Graph()

    for rec in records:
        # Graph-style record with explicit entities/relationships (topic-agnostic).
        if "entities" in rec and "relationships" in rec:
            _add_graph_document_record(G, rec, edge_cfg=edge_config)
            continue

        disease = (rec.get("disease_name") or rec.get("name") or "").strip()
        if not disease:
            continue
        edge_weights = rec.get("_edge_weights", {})

        # Disease node
        _add_node(G, disease, NODE_TYPES["disease"])

        # Treatments
        trt_weights = {w["value"]: w.get("weight") for w in edge_weights.get("treatments", [])} if edge_weights else {}
        for trt in (rec.get("treatments") or []):
            _add_node(G, trt, NODE_TYPES["treatment"])
            _add_edge(G, disease, trt, "treated_with", trt_weights.get(trt))

        # Genes
        gene_weights = {w["value"]: w.get("weight") for w in edge_weights.get("related_genes", [])} if edge_weights else {}
        for gen in (rec.get("related_genes") or []):
            _add_node(G, gen, NODE_TYPES["gene"])
            _add_edge(G, disease, gen, "associated_gene", gene_weights.get(gen))

        # Diagnosis
        diag_weights = {w["value"]: w.get("weight") for w in edge_weights.get("diagnosis", [])} if edge_weights else {}
        for diag in (rec.get("diagnosis") or []):
            _add_node(G, diag, NODE_TYPES["diagnosis"])
            _add_edge(G, disease, diag, "has_diagnosis", diag_weights.get(diag))

        # Causes
        cause_weights = {w["value"]: w.get("weight") for w in edge_weights.get("causes", [])} if edge_weights else {}
        for cause in (rec.get("causes") or []):
            _add_node(G, cause, NODE_TYPES["cause"])
            _add_edge(G, disease, cause, "has_cause", cause_weights.get(cause))

        # Risk factors
        rf_weights = {w["value"]: w.get("weight") for w in edge_weights.get("risk_factors", [])} if edge_weights else {}
        for rf in (rec.get("risk_factors") or []):
            _add_node(G, rf, NODE_TYPES["risk_factor"])
            _add_edge(G, disease, rf, "has_risk_factor", rf_weights.get(rf))

        # Subtypes
        st_weights = {w["value"]: w.get("weight") for w in edge_weights.get("subtypes", [])} if edge_weights else {}
        for st in (rec.get("subtypes") or []):
            _add_node(G, st, NODE_TYPES["subtype"])
            _add_edge(G, disease, st, "has_subtype", st_weights.get(st))

    types_counter = Counter(nx.get_node_attributes(G, "type").values())
    stats = BuildStats(
        n_nodes=G.number_of_nodes(),
        n_edges=G.number_of_edges(),
        types=types_counter,
    )

    return G, stats
