#!/usr/bin/env python3
"""
Module 6 – Graph Construction & Analysis
-------------------------------------------------------
Loads combined records for any topic, builds a heterogeneous graph, and runs
connectivity, community detection (with consensus), centrality, link
prediction, node property prediction, traversal demos, and optional
statistical validation. Exports GraphML, PyVis HTML, CSVs, and an enhanced
Markdown report. Configurable via CLI (input path, output dir, seeds,
validation, enhanced viz, memory monitor, betweenness sampling, limits).
"""

from __future__ import annotations

import argparse
import gc
import sys
import time
import warnings
from pathlib import Path
from typing import Any, Dict, List

import networkx as nx
from src.kg.utils.paths import resolve_base_dir

# Optional memory monitoring
try:  # pragma: no cover
    import psutil
except Exception:  # pragma: no cover
    psutil = None

# ──────────────────────────────────────────────────────────────────────────────
# Imports from refactored submodules
# ──────────────────────────────────────────────────────────────────────────────

from .loader.records_loader import load_records
from .build.graph_builder import build_graph, BuildStats

from .analytics.connectivity import connectivity_summary
from .analytics.communities import detect_communities, consensus_community_detection
from .analytics.centrality import compute_centrality
from .analytics.link_prediction import link_prediction, improved_link_prediction
from .analytics.node_property import neighbor_majority_predict
from .analytics.traversal import traversal_demo, shortest_path_demos
from .analytics.statistics import statistical_validation

from .viz.pyvis_basic import export_pyvis_with_legend
from .viz.pyvis_enhanced import enhanced_pyvis_visualization

from .report.report_enhanced import generate_enhanced_report
from .report.csv_export import (
    export_centrality_dual_csvs,
    export_linkpred_csv,
)
from .utils.config_loader import load_graph_config, build_color_maps


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Module 6 – Build and analyse the knowledge graph.")
    p.add_argument(
        "--input",
        help="Path to combined JSON (top-level list) OR a directory of per-entity JSONs. If omitted, defaults to {base}/combined/all_entities_matched.json (or all_diseases_matched.json) when --graph-name/--data-location is provided.",
    )
    p.add_argument(
        "--graph-name",
        help="Graph/topic name (uses data/{graph-name} as base when --input not given).",
    )
    p.add_argument(
        "--data-location",
        help="Explicit data directory (overrides --graph-name).",
    )
    p.add_argument(
        "--outdir",
        help="Output directory (default: {base}/analysis when graph/data specified, else data/analysis)",
    )
    p.add_argument(
        "--viz-html",
        default="graph.html",
        help="Filename for PyVis HTML under outdir",
    )
    p.add_argument(
        "--graphml",
        default="graph.graphml",
        help="Filename for GraphML under outdir",
    )
    p.add_argument(
        "--topk",
        type=int,
        default=25,
        help="Top-k rows to include in tables & report summaries",
    )
    p.add_argument(
        "--betweenness-sample",
        type=int,
        default=0,
        help="If >0, approximate betweenness using K-node sample for speed",
    )
    p.add_argument(
        "--seed",
        action="append",
        default=[],
        help="Add a seed node for traversal & shortest-path demos (repeatable)",
    )
    p.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed for community detection",
    )
    p.add_argument(
        "--max-nodes",
        type=int,
        default=0,
        help="Limit analysis to the first N records (0 = no limit)",
    )
    p.add_argument(
        "--memory-monitor",
        action="store_true",
        help="Enable memory usage monitoring and GC logging",
    )
    p.add_argument(
        "--validation",
        action="store_true",
        help="Perform statistical validation and enhanced link prediction",
    )
    p.add_argument(
        "--enhanced-viz",
        action="store_true",
        help="Use enhanced visualization with centrality-based node sizing",
    )
    return p.parse_args()


# ──────────────────────────────────────────────────────────────────────────────
# Memory utilities
# ──────────────────────────────────────────────────────────────────────────────


def optimize_memory() -> None:
    """Force garbage collection and optionally log process memory usage."""
    gc.collect()
    if psutil is not None:
        proc = psutil.Process()
        mem_mb = proc.memory_info().rss / 1024 / 1024
        print(f"[MEMORY] After GC: {mem_mb:.1f} MB")


# ──────────────────────────────────────────────────────────────────────────────
# Main orchestration
# ──────────────────────────────────────────────────────────────────────────────


def main() -> None:
    args = parse_args()
    base_dir: Path | None = None
    if args.graph_name or args.data_location:
        base_dir = resolve_base_dir(args.graph_name, args.data_location, create=True)

    if args.input:
        input_path = Path(args.input)
    else:
        if base_dir is None:
            raise SystemExit("Please provide --input or --graph-name/--data-location to locate the dataset.")
        combined_dir = base_dir / "combined"
        candidates = [
            combined_dir / "all_entities_matched.json",
            combined_dir / "all_diseases_matched.json",
            combined_dir / "all_entities.json",
            combined_dir / "all_diseases.json",
        ]
        input_path = next((p for p in candidates if p.exists()), None)
        if input_path is None:
            raise SystemExit(f"Could not find a combined JSON file in {combined_dir}.")

    outdir = Path(args.outdir) if args.outdir else (base_dir / "analysis" if base_dir else Path("data/analysis"))
    outdir.mkdir(parents=True, exist_ok=True)

    graph_label = args.graph_name or (base_dir.name if base_dir else input_path.stem)

    # Load per-topic config if available (nodes.ini / edges.ini)
    node_cfg: Dict[str, Any] = {}
    edge_cfg: Dict[str, Any] = {}
    color_by_type: Dict[str, str] = {}
    edge_color_map: Dict[str, str] = {}
    if base_dir is not None:
        node_cfg, edge_cfg = load_graph_config(base_dir)
        color_by_type, edge_color_map = build_color_maps(node_cfg, edge_cfg)

    start_time = time.time()

    print(f"📥 Loading records from {input_path}")
    print("📥 Loading records …")
    records = load_records(str(input_path))

    if args.max_nodes > 0:
        records = records[: args.max_nodes]
        print(f"📏 Limited to {args.max_nodes} records for memory management")

    if args.memory_monitor:
        print("🔍 Memory monitoring enabled")
    if args.validation:
        print("📊 Statistical validation and enhanced link prediction enabled")
    if args.enhanced_viz:
        print("🎨 Enhanced visualization enabled")

    # Build graph
    print("🧱 Building graph …")
    G, build_stats = build_graph(records, node_config=node_cfg, edge_config=edge_cfg)
    print(
        f"✅ Graph built: {build_stats.n_nodes} nodes, "
        f"{build_stats.n_edges} edges. Types: {build_stats.types}"
    )

    # Connectivity
    print("🔗 Connectivity analysis …")
    conn = connectivity_summary(G)
    print(
        f"   Components: {conn['n_components']} | "
        f"Giant: {conn['giant_nodes']} ({conn['giant_fraction']:.2%}) | "
        f"Isolates: {conn['n_isolates']}"
    )

    # Communities (standard first)
    print("🧩 Community detection …")
    node2comm, comms = detect_communities(G, random_state=args.random_state)
    print(f"   Detected communities (initial): {len(comms)}")

    # Consensus communities if validation or enhanced viz requested
    if args.validation or args.enhanced_viz:
        print("🧩 Refining via consensus community detection …")
        node2comm, comms = consensus_community_detection(G, random_state=args.random_state)
        print(f"   Consensus communities: {len(comms)}")

    # Centrality
    print("📈 Centrality metrics …")
    cent_unweighted = compute_centrality(G, k_sample=args.betweenness_sample, use_weights=False)
    cent_weighted = compute_centrality(G, k_sample=args.betweenness_sample, use_weights=True)
    cent = {"unweighted": cent_unweighted, "weighted": cent_weighted}

    if args.memory_monitor:
        optimize_memory()

    # Console top-5 central nodes
    def _print_top5(name: str, scores: Dict[str, float]) -> None:
        top5 = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
        print(f"   Top 5 by {name}:")
        for i, (node, score) in enumerate(top5, start=1):
            label = G.nodes[node].get("label", node)
            print(f"   {i:>2}. {label} ({score:.4f})")

    _print_top5("degree (unweighted)", cent_unweighted["degree"])
    _print_top5("betweenness (unweighted)", cent_unweighted["betweenness"])
    _print_top5("eigenvector (unweighted)", cent_unweighted["eigenvector"])

    # Link prediction
    print("🔮 Link prediction …")
    # TODO: Make link prediction fully config-driven using edges.ini
    if args.validation:
        lp_rows = improved_link_prediction(G, limit=4000)
        print("   Using enhanced link prediction with expanded edge types.")
    else:
        lp_rows = link_prediction(G, limit=4000)
        print("   Using basic local-similarity link prediction.")

    if lp_rows:
        print("   Top 5 link suggestions:")
        for i, r in enumerate(lp_rows[:5], start=1):
            ensemble_key = "ensemble_score" if "ensemble_score" in r else "ensemble"
            score = r.get(ensemble_key, 0.0)
            print(
                f"   {i:>2}. {r['u']} ↔ {r['v']} "
                f"[{r['type_u']}–{r['type_v']}] "
                f"{ensemble_key}={score:.3f}"
            )

    # Node property prediction
    print("🏷️ Node property prediction (neighbor-majority holdout) …")
    npp = neighbor_majority_predict(G, holdout_frac=0.1, seed=0)
    print(f"   Accuracy: {npp['accuracy']:.2%} on {npp['n_holdout']} hidden nodes")

    # Statistical validation
    validation_results: Dict[str, Any] = {}
    if args.validation:
        print("📊 Performing statistical validation …")
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            validation_results = statistical_validation(G, node2comm, cent)
        print(f"   Validation complete ({len(validation_results)} sections).")

    # Traversal demos
    print("🧭 Traversal demos (BFS/DFS, shortest paths) …")
    bfs_txt, dfs_txt = traversal_demo(G, args.seed)
    sp_txts = shortest_path_demos(G, args.seed)

    # GraphML export (sanitized to avoid unsupported types)
    graphml_path = outdir / args.graphml
    try:
        # remove list/dict attributes not supported by GraphML
        G_graphml = G.copy()
        for n, attrs in list(G_graphml.nodes(data=True)):
            bad_keys = [k for k, v in attrs.items() if isinstance(v, (list, dict)) or v is None]
            for k in bad_keys:
                del G_graphml.nodes[n][k]
        for u, v, attrs in list(G_graphml.edges(data=True)):
            bad_keys = [k for k, v in attrs.items() if isinstance(v, (list, dict)) or v is None]
            for k in bad_keys:
                del G_graphml.edges[u, v][k]
        nx.write_graphml(G_graphml, graphml_path)
        print(f"💾 Saved GraphML → {graphml_path}")
    except TypeError as e:
        print(f"[WARN] GraphML export skipped due to unsupported types: {e}")

    # PyVis visualization
    html_path = outdir / args.viz_html
    if args.enhanced_viz:
        enhanced_pyvis_visualization(
            G,
            html_path,
            centrality=cent,
            node2comm=node2comm,
            title=f"Enhanced {graph_label} Knowledge Graph",
            color_by_type=color_by_type or None,
            edge_color_map=edge_color_map or None,
        )
    else:
        export_pyvis_with_legend(
            G,
            html_path,
            node2comm=node2comm,
            color_by_type=color_by_type or None,
        )
    print(f"🌐 Saved interactive HTML → {html_path}")

    # CSV exports
    centrality_csv_dir = outdir
    export_centrality_dual_csvs(cent_unweighted, cent_weighted, centrality_csv_dir)

    linkpred_csv = outdir / "link_predictions.csv"
    export_linkpred_csv(lp_rows, linkpred_csv)

    # Simple communities CSV (node → community)
    communities_csv = outdir / "communities.csv"
    communities_csv.parent.mkdir(parents=True, exist_ok=True)
    try:
        import csv

        with open(communities_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["node", "label", "type", "community"])
            writer.writeheader()
            for n in G.nodes():
                writer.writerow(
                    {
                        "node": n,
                        "label": G.nodes[n].get("label", n),
                        "type": G.nodes[n].get("type", ""),
                        "community": node2comm.get(n, -1),
                    }
                )
        print(f"💾 Saved communities CSV → {communities_csv}")
    except Exception as e:  # pragma: no cover
        print(f"[WARN] Failed to write communities.csv: {e}")

    # Markdown report (enhanced format)
    print("📝 Rendering report …")
    report_md = generate_enhanced_report(
        G=G,
        stats=build_stats,
        connectivity=conn,
        cent=cent,
        node2comm=node2comm,
        comms=comms,
        linkpred_rows=lp_rows,
        traversal_texts=(bfs_txt, dfs_txt),
        shortest_paths=sp_txts,
        top_k=args.topk,
        npp_result=npp,
        validation_results=validation_results,
        title=f"Enhanced {graph_label} Knowledge Graph Analysis Report",
    )

    report_path = outdir / "report_module6.md"
    report_path.write_text(report_md, encoding="utf-8")
    print(f"📄 Saved report → {report_path}")

    elapsed = time.time() - start_time
    print(f"⏱️ Total execution time: {elapsed:.1f}s")
    print("✔️ Module 6 complete.")


if __name__ == "__main__":
    main()
    
