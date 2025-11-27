#!/usr/bin/env python3
"""
Main pipeline launcher for Knowledge Graph build process.

Runs sequentially:
1. Module 1 – Crawler
2. Module 2 – Clean
3. Module 3 – Entity & Relationship Extraction
4. Module 4 – JSON Validation
5. Module 5 – Combine JSON Files for Analysis
6. Utilities: Predict Token Count – Ensure token count is within LLM limits
7. Module 6 – Read combined JSON file, analyse, export results.
"""

import argparse
import subprocess
import sys
import datetime
from pathlib import Path


def run_step(description: str, command: list[str]):
    """Run one pipeline step, print status, and stop on error."""
    print("\n" + "=" * 80)
    print(f"[{datetime.datetime.now().isoformat()}] 🚀 Starting: {description}")
    print("=" * 80)
    print(" ".join(command))
    print("-" * 80)

    try:
        result = subprocess.run(command, check=True)
        print(f"\n✅ Completed: {description}\n")
        return result.returncode
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ERROR in {description}")
        print(f"Command failed with return code {e.returncode}")
        sys.exit(e.returncode)
    except Exception as e:
        print(f"\n❌ Unexpected error in {description}: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Knowledge graph pipeline launcher.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--graph-name", help="Graph/topic name (uses data/{graph-name} as base).")
    group.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=[],  # no sources enabled by default
        help="Sources to use in the crawler.",
    )
    parser.add_argument(
        "--allow-extra-nodes",
        action="store_true",
        help="Allow LLM to introduce nodes/edges beyond schema (relaxes Module 3 schema constraints).",
    )
    parser.add_argument("--seed", action="append", default=[], help="Seed(s) for Module 6 traversal/shortest-path demos.")
    args = parser.parse_args()

    base_dir = Path(args.data_location) if args.data_location else Path("data") / args.graph_name
    base_dir = base_dir.resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    combined_dir = base_dir / "combined"
    analysis_dir = base_dir / "analysis"

    steps = [
        (
            "Module 1: Crawler",
            [
                "python",
                "-m",
                "src.kg.module1_crawler.crawler",
                "--data-location",
                str(base_dir),
                "--sources",
                *args.sources,
            ],
        ),
        (
            "Module 2: Clean",
            ["python", "-m", "src.kg.module2_clean.clean", "--data-location", str(base_dir)],
        ),
        (
            "Module 3: Entity & Relationship Extraction",
            [
                "python",
                "-m",
                "src.kg.module3_extraction_entity_relationship.extraction_entity_relationship",
                "--data-location",
                str(base_dir),
                "--all",
            ]
            + (["--allow-extra-nodes"] if args.allow_extra_nodes else []),
        ),
        (
            "Module 4: Validate Extracted JSON",
            [
                "python",
                "-m",
                "src.kg.module4_validate_json.validate_json",
                "--data-location",
                str(base_dir),
            ],
        ),
        (
            "Module 5: Combine JSON Files for Analysis",
            [
                "python",
                "-m",
                "src.kg.module5_prepare_for_analysis.combine_json_files",
                "--graph-name",
                str(args.graph_name),
            ],
        ),
        (
            "Utilities: Predict Token Count",
            [
                "python",
                "-m",
                "src.kg.utils.tokencount_predictor",
                "--input_path",
                str(combined_dir / "all_entities.json"),
            ],
        ),
        (
            "Module 6: Graph Construction & Analysis",
            [
                "python",
                "-m",
                "src.kg.module6_analysis.analyse",
                "--graph-name",
                str(args.graph_name),
                "--validation",
                "--enhanced-viz",
                *sum([["--seed", s] for s in args.seed[:2]], []),
            ],
        ),
    ]
    

    print("\n" + "#" * 80)
    print("#               KNOWLEDGE GRAPH PIPELINE LAUNCHER")
    print("#" * 80)

    for desc, cmd in steps:
        run_step(desc, cmd)

    print("\n🎉 All modules completed successfully! The data is ready for analysis.\n")


if __name__ == "__main__":
    main()
