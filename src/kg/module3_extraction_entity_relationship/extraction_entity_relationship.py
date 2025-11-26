#!/usr/bin/env python3
"""
extraction_entity_relationship.py
---------------------------------
Uses the Google AI Studio API (Gemini 2.5 Flash Live) to perform
structured entity and relationship extraction for knowledge-graph population.

MODIFIED:
    ✔ Each source file is processed separately (no grouping!)
    ✔ Output filename includes "_<source>" suffix
        Example:
            suisei_-_wikipedia.txt → suisei_wikipedia.json
            suisei_-_other.txt     → suisei_other.json
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from src.kg.utils.paths import resolve_base_dir

MODEL_NAME = "gemini-2.0-flash"
MAX_RETRIES = 3


# ────────────────────────────────────────────────────────────────────────────── #
# DATA STRUCTURES
# ────────────────────────────────────────────────────────────────────────────── #

@dataclass
class ExtractionPaths:
    base_dir: Path
    processed_dir: Path
    output_dir: Path
    schema_path: Path
    example_json_path: Path
    prompt_path: Path


PATHS: ExtractionPaths | None = None


def require_paths() -> ExtractionPaths:
    if PATHS is None:
        raise RuntimeError("Paths not initialized. Call main() to configure.")
    return PATHS


# ────────────────────────────────────────────────────────────────────────────── #
# LOAD SCHEMA, PROMPT, EXAMPLE
# ────────────────────────────────────────────────────────────────────────────── #

def load_schema(schema_path: Path) -> str:
    if not schema_path.exists():
        sys.exit(f"❌ Schema file not found at {schema_path}")
    try:
        schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"❌ Failed to parse schema JSON: {e}")
    return json.dumps(schema_json, indent=2, ensure_ascii=False)


def load_prompt(prompt_path: Path, schema_content: str) -> str:
    if not prompt_path.exists():
        sys.exit(f"❌ Prompt file not found at {prompt_path}")
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()
    if "{SCHEMA_JSON}" in prompt_text:
        return prompt_text.replace("{SCHEMA_JSON}", schema_content)
    return f"{prompt_text}\n\nSchema:\n{schema_content}"


def load_example(example_path: Path) -> str:
    if not example_path.exists():
        sys.exit(f"❌ Example JSON missing: {example_path}")
    return example_path.read_text(encoding="utf-8")


# ────────────────────────────────────────────────────────────────────────────── #
# FIND FILES
# ────────────────────────────────────────────────────────────────────────────── #

def find_related_files(entity: str, processed_dir: Path):
    """Return ALL files for this entity, e.g. suisei_-_wikipedia.txt, suisei_-_other.txt."""
    files = [f for f in processed_dir.glob(f"{entity}_-*.txt")]
    if not files:
        print(f"⚠️ No matching files found for '{entity}_-*.txt'.")
    return sorted(files)


# ────────────────────────────────────────────────────────────────────────────── #
# PROCESS ONE FILE (NEW BEHAVIOR)
# ────────────────────────────────────────────────────────────────────────────── #

def process_single_source_file(entity: str, src_path: Path, model, prompt_content: str,
                               example_json: str, paths: ExtractionPaths):
    """
    NEW: Process each file independently.
    Input:  suisei_-_wikipedia.txt
    Output: suisei_wikipedia.json
    """

    # Extract source name: part after "_-_"
    try:
        source = src_path.name.split("_-_", 1)[1].replace(".txt", "")
    except Exception:
        source = "unknown"

    output_filename = f"{entity}_{source}.json"
    out_path = paths.output_dir / output_filename

    print(f"\n📄 Processing file: {src_path.name}")
    print(f"➡️  Output JSON will be: {output_filename}")

    text = src_path.read_text(encoding="utf-8")
    combined_text = f"--- SOURCE: {src_path.name} ---\n{text}"

    full_prompt = (
        f"{prompt_content}\n\n"
        f"Example JSON:\n{example_json}\n\n"
        f"Input Text:\n{combined_text}"
    )

    # ---- Send to model ----
    try:
        print(f"🧠 LLM extracting for {entity} [{source}] ...")
        response = model.generate_content(
            contents=[full_prompt],
            generation_config={
            "temperature": 0.2,
            "response_mime_type": "application/json",
            },
        )
    except Exception as e:
        print(f"❌ API error for {src_path.name}: {e}")
        return False

    text = (response.text or "").strip()
    if not text:
        print(f"❌ Empty response for {src_path.name}")
        return False

    # Remove ```json fences
    try:
        if text.startswith("```"):
            text = text.lstrip("`").removeprefix("json").strip()
        if text.endswith("```"):
            text = text.rstrip("`").strip()

        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON for {src_path.name}. Output begins:\n{text[:300]}...\n")
        return False

    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Saved: {out_path}")
    return True


def process_with_retry_file(entity: str, src_path: Path, model, prompt_content: str,
                            example_json: str, paths: ExtractionPaths):
    """Retry wrapper for a single source file."""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 Attempt {attempt}/{MAX_RETRIES} for file {src_path.name}")
        ok = process_single_source_file(entity, src_path, model, prompt_content, example_json, paths)
        if ok:
            return True
        if attempt < MAX_RETRIES:
            wait = 5 * attempt
            print(f"⏳ Retrying in {wait}s...")
            time.sleep(wait)
    return False


# ────────────────────────────────────────────────────────────────────────────── #
# MAIN
# ────────────────────────────────────────────────────────────────────────────── #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Entity/relationship extraction for any graph topic.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--entity", dest="entity", help="Entity/topic prefix (before '_-').")
    g.add_argument("--all", action="store_true", help="Process all entities in processed/.")
    p.add_argument("--force", action="store_true", help="Re-run even if JSON already exists.")
    p.add_argument("--graph-name", help="Graph/topic name (uses data/{graph-name} as base).")
    p.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    p.add_argument("--schema-path", help="Path to schema_keys.json.")
    p.add_argument("--example-path", help="Path to example_entity_extraction.json.")
    p.add_argument("--prompt-path", help="Path to prompt template.")
    p.add_argument("--output-dir", help="Directory to write extracted JSON.")
    return p.parse_args()


def main():
    global PATHS
    args = parse_args()

    base_dir = resolve_base_dir(args.graph_name, args.data_location, create=True)
    processed_dir = base_dir / "processed"
    if not processed_dir.exists():
        sys.exit(f"❌ Processed directory not found: {processed_dir}")

    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "json"
    output_dir.mkdir(parents=True, exist_ok=True)

    schema_path = Path(args.schema_path) if args.schema_path else base_dir / "config" / "schema_keys.json"
    example_json_path = Path(args.example_path) if args.example_path else base_dir / "config" / "llm_schema_example.json"
    prompt_path = Path(args.prompt_path) if args.prompt_path else base_dir / "config" / "prompt.ini"

    PATHS = ExtractionPaths(
        base_dir=base_dir,
        processed_dir=processed_dir,
        output_dir=output_dir,
        schema_path=schema_path,
        example_json_path=example_json_path,
        prompt_path=prompt_path,
    )

    schema_content = load_schema(PATHS.schema_path)
    prompt_content = load_prompt(PATHS.prompt_path, schema_content)
    example_json = load_example(PATHS.example_json_path)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("❌ Missing GOOGLE_API_KEY environment variable.")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(MODEL_NAME)

    # Determine processing targets
    targets = [args.entity] if args.entity else {
        p.name.split("_-_")[0] for p in processed_dir.glob("*_-_*.txt")
    }
    targets = sorted(targets)

    # ---- MAIN LOOP ----
    for entity in targets:
        print("\n" + "=" * 80)
        print(f"🧩 Processing group '{entity}' (each file separately)")
        print("=" * 80)

        source_files = find_related_files(entity, processed_dir)
        if not source_files:
            continue

        for f in source_files:
            # deduce output filename
            src_suffix = f.name.split("_-_")[1].replace(".txt", "")
            out_path = PATHS.output_dir / f"{entity}_{src_suffix}.json"

            if out_path.exists() and not args.force:
                print(f"⚡ Skipping cached: {out_path.name}")
                continue

            ok = process_with_retry_file(entity, f, model, prompt_content, example_json, PATHS)
            if not ok:
                print(f"❌ FAILED after retries: {f.name}")

    print("\n🎉 DONE — all sources processed separately.")


if __name__ == "__main__":
    main()
