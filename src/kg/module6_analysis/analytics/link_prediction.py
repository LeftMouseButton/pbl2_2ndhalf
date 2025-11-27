# src/kg/module6_analysis/analytics/link_prediction.py

"""
Link prediction utilities for Module 6.

This module contains two predictors:

1) link_prediction()
   - Original Module 6 local-similarity predictor, using:
       • Jaccard coefficient
       • Adamic–Adar
       • Preferential Attachment
   - Generates only disease ↔ {gene, treatment, symptom} candidates.
   - Uses ensemble = sum of normalized metrics.

2) improved_link_prediction()
   - Generalized predictor that considers ALL plausible edge types,
     as defined by get_plausible_edge_types() or provided via config.
   - Computes the same similarity metrics but separately for each
     type of conceptual relation.
   - Normalizes each metric and aggregates with a 3-metric average.

Both predictors return a **sorted list of dictionaries**, compatible
with the original analyse.py report and CSV exporters.
"""

from __future__ import annotations

import itertools
from typing import Dict, List, Tuple, Any, Set, Optional

import networkx as nx

from ..utils.constants import MAX_NODES_DEFAULT


def get_plausible_edge_types() -> Dict[Tuple[str, str], str]:
    """
    Default biomedical edge-type mapping between node categories.

    For legacy cancer graphs that do not provide a config/edges.ini, this
    mapping is used as a fallback. When a per-topic config is present,
    analyse.py will pass a custom mapping into the link prediction
    functions instead.

    Returns
    -------
    Dict[(ntype_u, ntype_v), str]
        Mapping from sorted (node_type_u, node_type_v) to edge type string.
    """
    return {
        ("disease", "gene"):        "associated_gene",
        ("disease", "treatment"):   "treated_with",
        ("disease", "symptom"):     "has_symptom",
        ("disease", "diagnosis"):   "has_diagnosis",
        ("disease", "cause"):       "has_cause",
        ("disease", "risk_factor"): "has_risk_factor",
        ("disease", "subtype"):     "has_subtype",

        ("gene", "gene"):           "interacts_with",
        ("treatment", "treatment"): "contraindicated_with",
        ("symptom", "symptom"):     "correlated_with",
        ("gene", "treatment"):      "targets",
        ("gene", "symptom"):        "contributes_to",
    }

# ─────────────────────────────────────────────────────────────────────────────
# 1) BASIC LOCAL-SIMILARITY LINK PREDICTION (ORIGINAL)
# ─────────────────────────────────────────────────────────────────────────────

def link_prediction(
    G: nx.Graph,
    limit: int = 2000,
    plausible_edges: Optional[Dict[Tuple[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    """
    Original Module 6 link prediction based on local similarity metrics,
    optionally restricted to a set of plausible type-pairs.

    If `plausible_edges` is provided (typically derived from config/edges.ini),
    only node pairs whose (sorted) type pair appears as a key in that mapping
    are considered. Otherwise, the legacy biomedical filter is used:
    disease ↔ {gene, treatment, symptom}.

    Parameters
    ----------
    G : nx.Graph
    limit : int
        Max number of candidate pairs to evaluate.

    Returns
    -------
    List[dict]
        Sorted by descending ensemble score.
    """
    results: List[Dict[str, Any]] = []

    # --- Plausibility filter ------------------------------------------------
    def plausible(u: str, v: str) -> bool:
        tu = G.nodes[u].get("type")
        tv = G.nodes[v].get("type")

        # Config-driven mode: restrict strictly to type pairs from edges.ini
        if plausible_edges is not None:
            if tu is None or tv is None:
                return False
            key = tuple(sorted((tu, tv)))
            return key in plausible_edges

        # Legacy biomedical mode (disease ↔ {gene, treatment, symptom})
        return (
            (tu == "disease" and tv in {"gene", "treatment", "symptom"}) or
            (tv == "disease" and tu in {"gene", "treatment", "symptom"})
        )

    # --- Generate candidate pairs (distance ≥2, ≤3, no existing edge) -------
    lengths = dict(nx.all_pairs_shortest_path_length(G, cutoff=3))
    candidates: Set[Tuple[str, str]] = set()

    for u, dists in lengths.items():
        for v, dist in dists.items():
            if u < v and dist >= 2 and not G.has_edge(u, v) and plausible(u, v):
                candidates.add((u, v))
                if len(candidates) >= limit:
                    break
        if len(candidates) >= limit:
            break

    # --- Compute similarity metrics -----------------------------------------
    jac = {(u, v): s for u, v, s in nx.jaccard_coefficient(G, candidates)}
    aa  = {(u, v): s for u, v, s in nx.adamic_adar_index(G, candidates)}
    pa  = {(u, v): s for u, v, s in nx.preferential_attachment(G, candidates)}

    # --- Build result entries ------------------------------------------------
    for (u, v) in candidates:
        results.append({
            "u": G.nodes[u].get("label", u),
            "v": G.nodes[v].get("label", v),
            "type_u": G.nodes[u].get("type"),
            "type_v": G.nodes[v].get("type"),
            "jaccard": jac.get((u, v), 0.0),
            "adamic_adar": aa.get((u, v), 0.0),
            "pref_attach": pa.get((u, v), 0.0),
        })

    # --- Normalize and produce ensemble -------------------------------------
    if results:
        for key in ("jaccard", "adamic_adar", "pref_attach"):
            vals = [r[key] for r in results]
            lo, hi = min(vals), max(vals)
            rng = hi - lo if hi > lo else 1.0

            for r in results:
                r[f"{key}_n"] = (r[key] - lo) / rng

        for r in results:
            r["ensemble"] = (
                r["jaccard_n"] +
                r["adamic_adar_n"] +
                r["pref_attach_n"]
            )

        results.sort(key=lambda r: r["ensemble"], reverse=True)

    return results


# ─────────────────────────────────────────────────────────────────────────────
# 2) IMPROVED MULTI-TYPE LINK PREDICTION
# ─────────────────────────────────────────────────────────────────────────────

def improved_link_prediction(
    G: nx.Graph,
    limit: int = 2000,
    plausible_edges: Optional[Dict[Tuple[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    """
    Enhanced link prediction supporting ALL plausible edge types defined by
    `plausible_edges` (typically derived from config/edges.ini). If no mapping
    is provided, the default biomedical mapping from get_plausible_edge_types()
    is used.

    Parameters
    ----------
    G : nx.Graph
    limit : int
        Maximum number of node-pair evaluations (across all types).

    Returns
    -------
    List[dict]
        Sorted by descending ensemble_score.
    """
    if plausible_edges is None:
        plausible_edges = get_plausible_edge_types()
    results: List[Dict[str, Any]] = []

    # Group candidate pairs by conceptual edge type
    candidates_by_type: Dict[Tuple[str, str], List[Tuple[str, str]]] = {}

    node_list = list(G.nodes())

    # --- Build candidates for *all* plausible edges -------------------------
    for u, v in itertools.combinations(node_list, 2):
        if G.has_edge(u, v):
            continue

        tu = G.nodes[u].get("type")
        tv = G.nodes[v].get("type")

        if tu is None or tv is None:
            continue
        key = tuple(sorted((tu, tv)))
        if key in plausible_edges:
            candidates_by_type.setdefault(key, []).append((u, v))

    # If no candidates at all, return empty
    if not candidates_by_type:
        return []

    # --- Evaluate each edge type subset -------------------------------------
    n_types = len(candidates_by_type)
    per_type_limit = max(1, limit // n_types)

    for key, pairs in candidates_by_type.items():
        # Cap number per type
        pairs = pairs[:per_type_limit]

        # Compute similarity metrics
        jac = {(u, v): s for u, v, s in nx.jaccard_coefficient(G, pairs)}
        aa  = {(u, v): s for u, v, s in nx.adamic_adar_index(G, pairs)}
        pa  = {(u, v): s for u, v, s in nx.preferential_attachment(G, pairs)}

        edge_type = plausible_edges[key]  # resolved human-readable type

        # Build rows
        for (u, v) in pairs:
            results.append({
                "u": G.nodes[u].get("label", u),
                "v": G.nodes[v].get("label", v),
                "type_u": G.nodes[u].get("type"),
                "type_v": G.nodes[v].get("type"),
                "edge_type": edge_type,
                "jaccard": jac.get((u, v), 0.0),
                "adamic_adar": aa.get((u, v), 0.0),
                "pref_attach": pa.get((u, v), 0.0),
            })

    # --- Normalize + ensemble ------------------------------------------------
    if results:
        for metric in ("jaccard", "adamic_adar", "pref_attach"):
            vals = [r[metric] for r in results]
            lo, hi = min(vals), max(vals)
            rng = hi - lo if hi > lo else 1.0

            for r in results:
                r[f"{metric}_normalized"] = (r[metric] - lo) / rng

        for r in results:
            r["ensemble_score"] = (
                r["jaccard_normalized"] +
                r["adamic_adar_normalized"] +
                r["pref_attach_normalized"]
            ) / 3.0

        results.sort(key=lambda r: r["ensemble_score"], reverse=True)

    return results
