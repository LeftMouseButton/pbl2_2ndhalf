# src/kg/module6_analysis/report/report_enhanced.py

"""
Enhanced Markdown report generation for Module 6.

This module produces a detailed, academic-style report including:

- Executive summary
- Graph statistics (size, density, degree stats)
- Connectivity summary (components, giant component, isolates)
- Community analysis (sizes, leaders)
- Centrality analysis (top-k hubs)
- Link prediction summary (top suggested edges)
- Statistical validation (degree distribution, correlations)
- Node property prediction performance
- Traversal demos (BFS/DFS) and shortest paths
- Brief biological interpretation section

The output is a Markdown string; no files are written here.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple, Optional

import networkx as nx

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None

desc_community = """```
Meaning
- Automatic grouping of nodes into clusters based on connectivity.

Purpose
- Reveals natural subgroups—e.g., fandom communities, content “neighborhoods,” or thematic clusters.

What can be learned
- Which entities tend to appear in similar contexts
- Which content types “bundle” together
```\n"""
desc_centrality_degree= """```
Meaning
- Measures how many direct connections a node has.

Purpose
- Identifies hubs — nodes that link to many others.

What can be learned
- Influential individuals
- Popular items or frequently referenced content
```\n"""
desc_centrality_betweenness= """```
Meaning
- Measures how often a node lies on shortest paths between others.

Purpose
- Identifies “bridges” that connect different communities or knowledge areas.

What can be learned
- Which nodes act as connectors
- Importance beyond raw popularity

Example
- “Hololive agency has high betweenness” → agency connects VTubers with events and sponsors.
```\n"""
desc_centrality_eigenvector= """```
Meaning
- Measures influence based on the influence of neighbors (like Google PageRank).

Purpose
- Shows nodes embedded in highly important regions of the graph.

What can be learned
- Which VTubers are connected to other high-profile nodes
- Whether centrality spreads through a network of key players
```\n"""
desc_centrality_weighted= """```
Meaning
- The same centrality measures, but incorporating confidence values.
- Confidence values are determined from user-input source reliability parameter (per source), and LLM-decided extraction confidence values (per attribute).

Purpose
- Improve accuracy of information when input data is suboptimal.
```\n"""
desc_linkprediction= """```
Meaning
- Predictions of edges that should exist but were not found in the input text.

Purpose
- Guides data collection, curation, and expansion of the graph.

What can be learned
- Potential VTuber collaborations
- Likely relationships not captured in text
- Areas where the graph is incomplete

Example
- Predicting Korone ↔ Pekora with score 0.650 suggests a strong expected link (shared content, games, history).
```\n"""
desc_statisticalvalidation= """```
Meaning
- Mathematical tests verifying how well the graph fits expected distributions (e.g., power law).

Purpose
- Confirms whether the graph behaves like a natural human-generated network.

What can be learned
- Whether the network resembles real social/knowledge networks
- Whether centrality correlations are strong or weak
- Whether graph structure is meaningful, not random

Example
- AIC comparison showing power-law fit → hierarchically structured VTuber ecosystems.
- Spearman: whether nodes rank similarly across different centrality metrics.
- - eg: If high-degree nodes also tend to have high betweenness → Spearman ρ is high.
```\n"""
desc_nodepropertyprediction= """```
Meaning
- Predicts unknown attributes using neighbors.

Purpose
- Shows whether the graph contains enough structure to infer missing information.

What can be learned
- Whether metadata can be inferred for incomplete pages
- Which node types cluster strongly by property
- How effective future GNNs might be on the dataset

Example
- Low accuracy (~14%) → current graph is too small for strong inferences; need more data.
```\n"""
desc_traversal_bfs= """```
Meaning: Layer-by-layer expansion from a seed node.
Purpose: Shows local neighborhoods and nearby relationships.
Learning: Which nodes are conceptually close even if not adjacent.

Example:
BFS from Fubuki reaches many music releases and events within 3 steps.
```\n"""
desc_traversal_dfs= """```
Meaning: Follows long chains of connectivity.
Purpose: Reveals narrative or sequential connections.
Learning: What long relationship chains look like in the graph.

Example:
DFS reveals long chains linking Fubuki → Mio → Suisei → Tetris → comet → AZKi.
```\n"""
desc_traversal_shortestpath= """```
Meaning: Minimal number of hops between key nodes.
Purpose: Shows how tightly clusters are linked.
Learning: Central connectors between major VTubers.

Example:
Shortest path “Fubuki → Hololive → Suisei” indicates the agency bridges them cleanly.
```\n"""

def _topk_dict(
    scores: Dict[str, float],
    G: nx.Graph,
    giant: Optional[nx.Graph],
    k: int,
) -> List[Dict[str, Any]]:
    """
    Convert a centrality dictionary into a list of top-k rows with labels and types.
    """
    if not scores:
        return []

    # Use ranking over the provided scores; giant is for degree context only
    items = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
    rows: List[Dict[str, Any]] = []
    for node, score in items:
        label = G.nodes[node].get("label", node)
        ntype = G.nodes[node].get("type")
        rows.append({
            "node": node,
            "label": label,
            "type": ntype,
            "score": score,
        })
    return rows


def _fmt_table(rows: List[Dict[str, Any]], cols: List[str]) -> str:
    """
    Format a list of dicts as a simple Markdown table.
    """
    if not rows:
        return "(none)"

    header = "| " + " | ".join(cols) + " |\n"
    header += "|" + "---|" * len(cols) + "\n"

    lines: List[str] = []
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")

    return header + "\n".join(lines)


def generate_enhanced_report(
    G: nx.Graph,
    stats: Any,
    connectivity: Dict[str, Any],
    cent: Dict[str, Dict[str, Dict[str, float]]],
    node2comm: Dict[str, int],
    comms: List[Set[str]],
    linkpred_rows: List[Dict[str, Any]],
    traversal_texts: Tuple[str, str],
    shortest_paths: List[str],
    top_k: int,
    npp_result: Optional[Dict[str, Any]] = None,
    validation_results: Optional[Dict[str, Any]] = None,
    title: str = "Knowledge Graph Analysis Report",
) -> str:
    """
    Build a detailed Markdown report string.

    Parameters
    ----------
    G : nx.Graph
        The full knowledge graph.
    stats : Any
        Typically BuildStats (with attributes: n_nodes, n_edges, types),
        but any object with equivalent attributes or keys is accepted.
    connectivity : Dict[str, Any]
        Output of connectivity_summary().
    cent : Dict[str, Dict[str, Dict[str, float]]]
        Centralities from compute_centrality(), keyed by "unweighted" and "weighted".
    node2comm : Dict[str, int]
        Node → community mapping.
    comms : List[Set[str]]
        List of communities (sets of node IDs).
    linkpred_rows : List[Dict[str, Any]]
        Link prediction results.
    traversal_texts : Tuple[str, str]
        (bfs_text, dfs_text) from traversal_demo().
    shortest_paths : List[str]
        Output of shortest_path_demos().
    top_k : int
        How many top nodes to show in tables (upper bound, clipped internally).
    npp_result : Optional[Dict[str, Any]]
        Node property prediction result (accuracy, n_holdout, preds).
    validation_results : Optional[Dict[str, Any]]
        Statistical validation output from statistical_validation().
    title : str
        Report title.

    Returns
    -------
    markdown : str
        The full report as Markdown.
    """
    validation_results = validation_results or {}

    # Handle stats as dataclass or dict-like
    if hasattr(stats, "n_nodes"):
        n_nodes = stats.n_nodes
        n_edges = stats.n_edges
        types_counter = stats.types
    else:
        n_nodes = stats["n_nodes"]
        n_edges = stats["n_edges"]
        types_counter = stats["types"]

    by_type = " | ".join(f"{t}: {c}" for t, c in types_counter.most_common())

    # Connectivity
    giant = connectivity.get("giant", G)
    giant_fraction = connectivity.get("giant_fraction", 0.0)

    # Graph-level measures
    avg_deg = (2 * n_edges) / n_nodes if n_nodes else 0.0
    density = nx.density(G)

    cent_unw = cent.get("unweighted", cent)
    cent_w = cent.get("weighted", {})

    # Centrality statistics (if NumPy available)
    if np is not None and cent_unw and cent_unw.get("degree"):
        deg_values = list(cent_unw["degree"].values())
        deg_stats = {
            "mean": float(np.mean(deg_values)),
            "std": float(np.std(deg_values)),
            "max": float(max(deg_values)),
            "min": float(min(deg_values)),
        }

        comm_sizes = [len(c) for c in comms] if comms else []
        if comm_sizes:
            comm_stats = {
                "mean_size": float(np.mean(comm_sizes)),
                "std_size": float(np.std(comm_sizes)),
                "largest": int(max(comm_sizes)),
                "smallest": int(min(comm_sizes)),
            }
        else:
            comm_stats = {}
    else:
        deg_stats = {}
        comm_stats = {}

    bfs_text, dfs_text = traversal_texts

    # Top-k central nodes
    k_eff = min(top_k, 20)
    top_deg = _topk_dict(cent_unw.get("degree", {}), G, giant, k_eff)
    top_btw = _topk_dict(cent_unw.get("betweenness", {}), G, giant, k_eff)
    top_eig = _topk_dict(cent_unw.get("eigenvector", {}), G, giant, k_eff)

    top_deg_w = _topk_dict(cent_w.get("degree", {}), G, giant, k_eff)
    top_btw_w = _topk_dict(cent_w.get("betweenness", {}), G, giant, k_eff)
    top_eig_w = _topk_dict(cent_w.get("eigenvector", {}), G, giant, k_eff)

    # Community leaders table
    leaders: List[Dict[str, Any]] = []
    max_preview = min(12, len(comms))
    for cid, cset in enumerate(comms[:max_preview]):
        # Leader = node with highest degree inside giant if present
        def _deg(node: str) -> int:
            if node in giant:
                return giant.degree(node)
            return G.degree(node)

        if not cset:
            continue

        leader_node = max(cset, key=_deg)
        if leader_node in giant:
            leader_label = giant.nodes[leader_node].get("label", leader_node)
        else:
            leader_label = G.nodes[leader_node].get("label", leader_node)

        leaders.append({
            "community": cid,
            "leader": leader_label,
            "size": len(cset),
        })

    leaders_table = _fmt_table(leaders, ["community", "leader", "size"])
    degree_table = _fmt_table(top_deg, ["label", "type", "score"])
    betw_table = _fmt_table(top_btw, ["label", "type", "score"])
    eig_table = _fmt_table(top_eig, ["label", "type", "score"])

    # Determine link prediction table columns
    lp_table_md = ""
    if linkpred_rows:
        first = linkpred_rows[0]
        # Enhanced or basic ensemble key
        ensemble_key = "ensemble_score" if "ensemble_score" in first else "ensemble"
        cols = ["u", "type_u", "v", "type_v", ensemble_key]

        # Build preview rows (top_k)
        preview_rows: List[Dict[str, Any]] = []
        for r in linkpred_rows[:top_k]:
            preview_rows.append({
                "u": r.get("u"),
                "type_u": r.get("type_u"),
                "v": r.get("v"),
                "type_v": r.get("type_v"),
                ensemble_key: f"{r.get(ensemble_key, 0.0):.3f}",
            })

        lp_table_md = _fmt_table(preview_rows, cols)
    else:
        lp_table_md = "(none)"

    # ──────────────────────────────────────────────────────────────────────
    # Begin assembling Markdown
    # ──────────────────────────────────────────────────────────────────────
    sections: List[str] = []

    # Title + Executive Summary
    sections.append(f"# {title}\n")

    # Graph Summary
    sections.append("## Graph Summary\n")
    sections.append(f"- Nodes: **{n_nodes}**\n")
    sections.append(f"- Edges: **{n_edges}**\n")
    sections.append(f"- Types: {by_type}\n")
    sections.append(
        f"- Connected components: **{connectivity['n_components']}**; "
        f"giant component size: **{connectivity['giant_nodes']}** "
        f"({giant_fraction:.2%} of nodes)\n"
    )
    sections.append(f"- Average degree: **{avg_deg:.2f}**\n")
    sections.append(f"- Graph density: **{density:.4f}**\n")
    sections.append(f"- **{len(comms)}** communities detected\n")
    if comm_stats:
        sections.append(
            f"- Community sizes – mean: **{comm_stats.get('mean_size', 0.0):.1f}**, "
            f"largest: **{comm_stats.get('largest', 0)}**, "
            f"smallest: **{comm_stats.get('smallest', 0)}**\n"
        )

    if connectivity.get("isolates"):
        iso_preview = ", ".join(connectivity["isolates"][:10])
        sections.append(f"- Isolates (preview): {iso_preview}\n")

    sections.append("\n")

    # Community Detection
    sections.append("## Community Detection\n")
    sections.append(desc_community)
    sections.append(f"- Detected **{len(comms)}** communities.\n\n")
    sections.append(leaders_table + "\n\n")

    # Centrality
    sections.append("## Centrality (Top Hubs)\n")
    sections.append("### Degree (Unweighted)\n")
    sections.append(desc_centrality_degree)
    sections.append(degree_table + "\n\n")
    sections.append("### Betweenness (Unweighted)\n")
    sections.append(desc_centrality_betweenness)
    sections.append(betw_table + "\n\n")
    sections.append("### Eigenvector (Unweighted)\n")
    sections.append(desc_centrality_eigenvector)
    sections.append(eig_table + "\n\n")

    if top_deg_w or top_btw_w or top_eig_w:
        sections.append("### Degree (Weighted)\n")
        sections.append(desc_centrality_weighted)
        sections.append(_fmt_table(top_deg_w, ["label", "type", "score"]) + "\n\n")
        sections.append("### Betweenness (Weighted)\n")
        sections.append(_fmt_table(top_btw_w, ["label", "type", "score"]) + "\n\n")
        sections.append("### Eigenvector (Weighted)\n")
        sections.append(_fmt_table(top_eig_w, ["label", "type", "score"]) + "\n\n")

    # Link Prediction
    sections.append("## Link Prediction (Top Suggestions)\n")
    sections.append(desc_linkprediction)
    sections.append(lp_table_md + "\n\n")

    # Statistical Validation
    sections.append("## Statistical Validation\n")
    sections.append(desc_statisticalvalidation)

    if validation_results:
        dd = validation_results.get("degree_distribution", {})
        if "favors_power_law" in dd:
            if dd["favors_power_law"]:
                sections.append(
                    "- Degree distribution is **more consistent with a power-law** "
                    "than a simple exponential (AIC comparison).\n"
                )
            else:
                sections.append(
                    "- Degree distribution does **not strongly support a power-law** "
                    "over an exponential model (AIC comparison).\n"
                )

        corr_unw = validation_results.get("centrality_correlations", {})
        if "degree_betweenness" in corr_unw:
            db = corr_unw["degree_betweenness"]
            sections.append(
                f"- Spearman correlation (degree vs betweenness): "
                f"**r = {db['correlation']:.3f}**, p = {db['p_value']:.3g}\n"
            )
        if "degree_eigenvector" in corr_unw:
            de = corr_unw["degree_eigenvector"]
            sections.append(
                f"- Spearman correlation (degree vs eigenvector): "
                f"**r = {de['correlation']:.3f}**, p = {de['p_value']:.3g}\n"
            )
        corr_w = validation_results.get("centrality_correlations_weighted", {})
        if "degree_betweenness" in corr_w:
            dbw = corr_w["degree_betweenness"]
            sections.append(
                f"- Weighted Spearman (degree vs betweenness): "
                f"**r = {dbw['correlation']:.3f}**, p = {dbw['p_value']:.3g}\n"
            )
        if "degree_eigenvector" in corr_w:
            dew = corr_w["degree_eigenvector"]
            sections.append(
                f"- Weighted Spearman (degree vs eigenvector): "
                f"**r = {dew['correlation']:.3f}**, p = {dew['p_value']:.3g}\n"
            )
    else:
        sections.append("- Statistical validation was not performed.\n")

    sections.append("\n")

    # Node Property Prediction
    sections.append("## Node Property Prediction\n")
    sections.append(desc_nodepropertyprediction)
    if npp_result:
        sections.append(
            f"- Neighbor-majority accuracy: "
            f"**{npp_result['accuracy']:.2%}** on "
            f"{npp_result['n_holdout']} hidden nodes.\n"
        )
    else:
        sections.append("- Node property prediction was not computed.\n")

    sections.append("\n")

    # Traversal & Shortest Paths
    sections.append("## Traversal & Shortest Paths\n")

    if bfs_text:
        sections.append("### BFS (depth ≤ 3) from seeds\n")
        sections.append(desc_traversal_bfs)
        sections.append("```text\n" + bfs_text.strip() + "\n```\n\n")

    if dfs_text:
        sections.append("### DFS (preorder) from seeds\n")
        sections.append(desc_traversal_dfs)
        sections.append("```text\n" + dfs_text.strip() + "\n```\n\n")

    if shortest_paths:
        sections.append("### Shortest paths among seeds\n")
        sections.append(desc_traversal_shortestpath)
        sections.append("```text\n")
        for p in shortest_paths:
            sections.append(p + "\n")
        sections.append("```\n")
    else:
        sections.append("_No valid seed pairs or no paths found._\n")

    sections.append("\n")

    # Interpretation (high-level)
    sections.append("## Interpretation (High-Level)\n")

    if giant_fraction > 0.8:
        sections.append(
            "- The graph is densely connected, with many entities linked through shared contextual relationships.\n"
        )
    else:
        sections.append(
            "- Multiple sizable components suggest distinct subnetworks that may "
            "reflect different themes, domains, or disconnected data sources.\n"
        )

    if len(comms) > 10:
        sections.append(
            "- The rich community structure points to multiple functional clusters "
            "within the graph (e.g., related concepts, co-occurring attributes, or "
            "entities that frequently appear together).\n"
        )

    # Highlight top link prediction if available
    if linkpred_rows:
        top_lp = linkpred_rows[0]
        ensemble_key = "ensemble_score" if "ensemble_score" in top_lp else "ensemble"
        score_val = float(top_lp.get(ensemble_key, 0.0))
        sections.append(
            f"- The highest-scoring predicted relation is between "
            f"**{top_lp.get('u')}** and **{top_lp.get('v')}** "
            f"({top_lp.get('type_u')}–{top_lp.get('type_v')}), "
            f"with ensemble score ≈ **{score_val:.3f}**. "
            "This edge is a strong candidate for follow-up curation.\n"
        )

    sections.append("\n---\nGenerated by Module 6 (enhanced analysis).\n")

    return "".join(sections)
