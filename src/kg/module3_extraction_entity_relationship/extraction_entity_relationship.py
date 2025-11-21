#!/usr/bin/env python3
"""
extraction_entity_relationship.py
---------------------------------
Uses the Google AI Studio API (Gemini 2.5 Flash Live) to perform
structured entity and relationship extraction for knowledge-graph population.

Modes:
  • Single disease:
      python extraction_entity_relationship.py --disease breast-cancer
  • Batch (all diseases):
      python extraction_entity_relationship.py --all
  • Re-run cached results:
      python extraction_entity_relationship.py --all --force
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

# ────────────────────────────────────────────────────────────────────────────── #
# CONFIGURATION
# ────────────────────────────────────────────────────────────────────────────── #

MODEL_NAME = "gemini-2.5-flash-lite"
MAX_RETRIES = 3


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
# LOAD CONFIG / SCHEMA / PROMPT
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
# HELPERS
# ────────────────────────────────────────────────────────────────────────────── #

def find_related_files(disease: str, processed_dir: Path):
    files = [f for f in processed_dir.glob(f"{disease}_-*.txt")]
    if not files:
        print(f"⚠️ No matching files found for prefix '{disease}_-'. Skipping.")
    return files


def upload_files(files):
    uploaded = []
    for path in files:
        print(f"⬆️ Uploading {path.name} ...")
        uploaded.append(genai.upload_file(path))
    return uploaded


def extract_prefixes(processed_dir: Path):
    """Collect unique prefixes (entity names) from processed text folder."""
    names = {p.name.split("_-_")[0] for p in processed_dir.glob("*.txt") if "_-_" in p.name}
    return sorted(names)


def process_once(disease: str, model, prompt_content: str, example_json: str, paths: ExtractionPaths):
    disease_files = find_related_files(disease, paths.processed_dir)
    if not disease_files:
        return False

    combined_text = ""
    reliability_map = {}
    for path in disease_files:
        reliability = 0.5
        meta_path = paths.processed_dir / "metadata.jsonl"
        if meta_path.exists():
            try:
                for line in meta_path.read_text(encoding="utf-8").splitlines():
                    rec = json.loads(line)
                    if rec.get("processed_filename") == path.name:
                        reliability = float(rec.get("source_reliability", reliability))
                        break
            except Exception:
                pass
        print(f"📖 Reading {path.name} ...")
        reliability_map[path.name] = reliability
        combined_text += f"\n\n--- SOURCE: {path.name} ---\n"
        combined_text += path.read_text(encoding="utf-8")

    full_prompt = f"{prompt_content}\n\nExample JSON:\n{example_json}\n\nInput Text:\n{combined_text}"

    print(f"🧠 Sending extraction request for '{disease}' to {MODEL_NAME}...")
    try:
        response = model.generate_content(
            contents=[full_prompt],
            generation_config={"temperature": 0.2},
        )
    except Exception as e:
        print(f"❌ API error for {disease}: {e}")
        return False

    text = (response.text or "").strip()
    if not text:
        print(f"❌ Empty response for {disease}.")
        return False

    try:
        if text.startswith("```"):
            text = text.lstrip("`").removeprefix("json").strip()
        if text.endswith("```"):
            text = text.rstrip("`").strip()
        data = json.loads(text)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON for {disease}. Output preview:\n{text[:400]}...\n")
        return False

    # Attach reliability map to output for downstream weighting
    if isinstance(data, dict):
        data["source_reliability"] = reliability_map

    out_path = paths.output_dir / f"{disease}.json"
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Saved extraction: {out_path}")
    return True


def process_with_retry(disease: str, model, prompt_content: str, example_json: str, paths: ExtractionPaths):
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 Attempt {attempt}/{MAX_RETRIES} for {disease}")
        ok = process_once(disease, model, prompt_content, example_json, paths)
        if ok:
            return True, attempt
        if attempt < MAX_RETRIES:
            wait = 5 * attempt
            print(f"⏳ Retrying in {wait}s...")
            time.sleep(wait)
    return False, MAX_RETRIES

# ────────────────────────────────────────────────────────────────────────────── #
# MAIN
# ────────────────────────────────────────────────────────────────────────────── #


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Entity/relationship extraction for any graph topic.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--entity", "--disease", dest="entity", help="Entity prefix (before '_-').")
    g.add_argument("--all", action="store_true", help="Process all entities in processed/.")
    p.add_argument("--force", action="store_true", help="Re-run even if JSON already exists.")
    p.add_argument("--graph-name", help="Graph/topic name (uses data/{graph-name} as base).")
    p.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    p.add_argument("--schema-path", help="Path to schema_keys.json (default: {base}/schema/schema_keys.json).")
    p.add_argument("--example-path", help="Path to example_entity_extraction.json (default: {base}/schema/example_entity_extraction.json).")
    p.add_argument("--prompt-path", help="Path to prompt template (default: {base}/schema/prompt.txt).")
    p.add_argument("--output-dir", help="Directory to write extracted JSON (default: {base}/json).")
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

    schema_path = Path(args.schema_path) if args.schema_path else base_dir / "schema" / "schema_keys.json"
    example_json_path = Path(args.example_path) if args.example_path else base_dir / "schema" / "example_entity_extraction.json"
    prompt_path = Path(args.prompt_path) if args.prompt_path else base_dir / "schema" / "prompt.txt"

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
    results = {}

    targets = [args.entity] if args.entity else extract_prefixes(PATHS.processed_dir)
    if not targets:
        sys.exit(f"❌ No files found in {PATHS.processed_dir}.")

    print(f"🔍 Target entities: {', '.join(targets)}")

    for disease in targets:
        out_path = PATHS.output_dir / f"{disease}.json"
        if out_path.exists() and not args.force:
            print(f"⚡ Skipping cached result for {disease} (use --force to re-run).")
            results[disease] = ("SKIPPED", 0)
            continue

        print("\n" + "=" * 80)
        print(f"🧩 Processing entity group: {disease}")
        print("=" * 80)
        success, attempts = process_with_retry(disease, model, prompt_content, example_json, PATHS)
        results[disease] = ("SUCCESS" if success else "FAILED", attempts)

    print("\n" + "#" * 80)
    print("📊 SUMMARY")
    print("#" * 80)
    for disease, (status, attempts) in results.items():
        emoji = {"SUCCESS": "✅", "FAILED": "❌", "SKIPPED": "⚡"}[status]
        attempts_str = f"(Attempts: {attempts})" if attempts else ""
        print(f"{disease:<30} {emoji} {status:<8} {attempts_str}")
    print("#" * 80)

    failed = [d for d, (s, _) in results.items() if s == "FAILED"]
    if failed:
        print(f"⚠️ {len(failed)} entries failed after {MAX_RETRIES} attempts: {', '.join(failed)}")
    else:
        print("🎉 All extractions completed successfully or were cached.")


if __name__ == "__main__":
    main()
