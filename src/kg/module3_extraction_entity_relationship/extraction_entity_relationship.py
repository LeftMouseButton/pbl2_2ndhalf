#!/usr/bin/env python3
"""
extraction_entity_relationship.py
---------------------------------
Uses the Google AI Studio API (Gemini 2.0 Flash) to perform
structured entity and relationship extraction for knowledge-graph population.

MODIFIED:
    ✔ Each source file is processed separately (no grouping!)
    ✔ Output filename includes "_<source>" suffix
        Example:
            suisei_-_wikipedia.txt → suisei_wikipedia.json
            suisei_-_other.txt     → suisei_other.json
    ✔ Streaming mode for Gemini responses
    ✔ Output-size prediction + dynamic chunking of long inputs
    ✔ Truncation detection + simple auto-repair
    ✔ Pretty-printed streaming progress
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

# Approximate token budgeting (very rough but sufficient for risk prediction)
MAX_TOKENS_PER_REQUEST = 1048000      # approximate limit for input+output
MAX_OUTPUT_TOKENS = 8100           # cap for generated JSON
IDEAL_CHUNK_TOKENS = 20000          # target per chunk (input side)


# ────────────────────────────────────────────────────────────── #
# DATA STRUCTURES
# ────────────────────────────────────────────────────────────── #

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


# ────────────────────────────────────────────────────────────── #
# SIMPLE TOKEN ESTIMATION + CHUNKING + PROGRESS
# ────────────────────────────────────────────────────────────── #

def estimate_tokens(text: str) -> int:
    """
    Very rough token estimator for Gemini-style models.
    Assumes ~4 characters per token on average.
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def predict_output_risk(prompt: str) -> float:
    """
    Return a risk score in [0,1] of truncation.
    0 = safe, 1 = almost guaranteed truncation.
    """
    tok = estimate_tokens(prompt)
    ratio = tok / MAX_TOKENS_PER_REQUEST
    return min(1.0, ratio)


def dynamic_chunk_text(text: str) -> list[str]:
    """
    Split long text into chunks based on approximate token count.
    Tries to break on newline boundaries.
    """
    total_tokens = estimate_tokens(text)
    if total_tokens <= IDEAL_CHUNK_TOKENS:
        return [text]

    lines = text.split("\n")
    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for line in lines:
        t = estimate_tokens(line)
        # If adding this line would overshoot, finalize current chunk
        if current_tokens + t > IDEAL_CHUNK_TOKENS and current:
            chunks.append("\n".join(current))
            current = [line]
            current_tokens = t
        else:
            current.append(line)
            current_tokens += t

    if current:
        chunks.append("\n".join(current))

    return chunks


def print_stream_progress(start_time: float, total_chunks: int, total_chars: int):
    elapsed = time.time() - start_time
    speed = total_chars / (elapsed + 1e-5)
    msg = (
        f"\r⏳ Streamed {total_chunks} chunks "
        f"({total_chars} chars, {speed:.1f} chars/sec)"
    )
    print(msg, end="", flush=True)


# ────────────────────────────────────────────────────────────── #
# JSON truncation detection + auto-repair
# ────────────────────────────────────────────────────────────── #

def is_truncated_json(text: str) -> bool:
    """Detect simple truncation patterns."""
    if text.endswith("..."):
        return True
    # obvious missing closing braces/brackets
    if text.count("{") > text.count("}"):
        return True
    if text.count("[") > text.count("]"):
        return True
    return False


def attempt_json_repair(text: str) -> str:
    """
    Try to fix simple truncation:
      - remove trailing '...'
      - close missing braces/brackets at the end
    """
    text = text.rstrip()

    if text.endswith("..."):
        text = text[:-3].rstrip()

    # Add missing closing brackets/braces
    while text.count("{") > text.count("}"):
        text += "}"
    while text.count("[") > text.count("]"):
        text += "]"

    return text


# ────────────────────────────────────────────────────────────── #
# LOAD SCHEMA, PROMPT, EXAMPLE
# ────────────────────────────────────────────────────────────── #

def load_schema(schema_path: Path) -> str:
    if not schema_path.exists():
        sys.exit(f"❌ Schema file not found at {schema_path}")
    try:
        schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        sys.exit(f"❌ Failed to parse schema JSON: {e}")
    return json.dumps(schema_json, indent=2, ensure_ascii=False)


def load_prompt(prompt_path: Path, schema_content: str | None) -> str:
    if not prompt_path.exists():
        sys.exit(f"❌ Prompt file not found at {prompt_path}")
    prompt_text = prompt_path.read_text(encoding="utf-8").strip()

    # If no schema content is provided, return the raw prompt text only.
    if schema_content is None:
        return f"{prompt_text}\n\n"

    if "{SCHEMA_JSON}" in prompt_text:
        return prompt_text.replace("{SCHEMA_JSON}", schema_content)
    return f"{prompt_text}\n\nSchema:\n{schema_content}"


def load_example(example_path: Path) -> str:
    if not example_path.exists():
        sys.exit(f"❌ Example JSON missing: {example_path}")
    return example_path.read_text(encoding="utf-8")


# ────────────────────────────────────────────────────────────── #
# FIND FILES
# ────────────────────────────────────────────────────────────── #

IGNORE_FILENAMES = {"metadata_-_unknown.txt"}


def find_related_files(entity: str, processed_dir: Path):
    """Return ALL files for this entity, e.g. suisei_-_wikipedia.txt, suisei_-_other.txt."""
    files = [
        f
        for f in processed_dir.glob(f"{entity}_-*.txt")
        if f.name not in IGNORE_FILENAMES
    ]
    if not files:
        print(f"⚠️ No matching files found for '{entity}_-*.txt'.")
    return sorted(files)


# ────────────────────────────────────────────────────────────── #
# PROCESS ONE FILE (STREAMING + CHUNKING)
# ────────────────────────────────────────────────────────────── #

def process_single_source_file(
    entity: str,
    src_path: Path,
    model,
    prompt_content: str,
    example_json: str,
    paths: ExtractionPaths,
):
    """
    Process a single source file independently, with streaming and dynamic chunking.

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

    raw_text = src_path.read_text(encoding="utf-8")
    total_tokens = estimate_tokens(raw_text)
    print(f"🧮 Approx input tokens for this file: {total_tokens}")

    text_chunks = dynamic_chunk_text(raw_text)
    num_chunks = len(text_chunks)
    print(f"🧩 Will process in {num_chunks} chunk(s).")

    chunk_results = []

    for i, chunk_text in enumerate(text_chunks, 1):
        print("\n" + "-" * 80)
        print(f"🔹 Chunk {i}/{num_chunks} for {entity} [{source}]")
        print("-" * 80)

        combined_text = (
            f"--- SOURCE: {src_path.name} (CHUNK {i}/{num_chunks}) ---\n{chunk_text}"
        )

        full_prompt = (
            f"{prompt_content}\n\n"
            f"Example JSON:\n{example_json}\n\n"
            f"Input Text:\n{combined_text}"
        )

        # Risk prediction
        risk = predict_output_risk(full_prompt)
        print(f"📈 Truncation risk estimate for this chunk: {risk * 100:.1f}%")

        # STREAMING CALL
        try:
            print(f"🧠 Streaming extraction for chunk {i}/{num_chunks}...")
            start_time = time.time()

            stream = model.generate_content(
                contents=[full_prompt],
                generation_config={
                    "temperature": 0.2,
                    "response_mime_type": "application/json",
                    "max_output_tokens": MAX_OUTPUT_TOKENS,
                },
                stream=True,
            )
        except Exception as e:
            print(f"❌ Streaming API error for {src_path.name} (chunk {i}): {e}")
            return False

        streamed_chunks: list[str] = []
        total_chars = 0
        chunk_counter = 0

        for chunk in stream:
            if hasattr(chunk, "text") and chunk.text:
                streamed_chunks.append(chunk.text)
                total_chars += len(chunk.text)
                chunk_counter += 1
                print_stream_progress(start_time, chunk_counter, total_chars)

        print()  # newline after progress line

        text_output = "".join(streamed_chunks).strip()
        if not text_output:
            print(f"❌ Empty streamed response for chunk {i} of {src_path.name}")
            return False

        # Strip ``` fences if present
        if text_output.startswith("```"):
            text_output = text_output.lstrip("`").removeprefix("json").strip()
        if text_output.endswith("```"):
            text_output = text_output.rstrip("`").strip()

        # Detect truncation
        if is_truncated_json(text_output):
            print("⚠️ WARNING: Streamed JSON appears truncated. Attempting auto-repair...")
            repaired = attempt_json_repair(text_output)
            try:
                chunk_data = json.loads(repaired)
                print("🔧 Auto-repair succeeded for this chunk.")
            except Exception:
                print("❌ Auto-repair failed; JSON still malformed for this chunk.")
                print("   Will fail this file so outer retry can handle it.")
                return False
        else:
            try:
                chunk_data = json.loads(text_output)
            except json.JSONDecodeError:
                print("❌ Invalid JSON for this chunk.")
                print(text_output[:400] + "...\n")
                return False

        chunk_results.append(chunk_data)

    # Merge chunk results into a single graph document
    if len(chunk_results) == 1:
        final = chunk_results[0]
    else:
        print(f"\n🔗 Merging {len(chunk_results)} chunk results...")
        final = {
            "entities": [],
            "relationships": [],
        }
        for part in chunk_results:
            if isinstance(part, dict):
                ents = part.get("entities", [])
                rels = part.get("relationships", [])
                if isinstance(ents, list):
                    final["entities"].extend(ents)
                if isinstance(rels, list):
                    final["relationships"].extend(rels)

    # Save final output JSON
    out_path.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ Saved extraction: {out_path}")
    return True


def process_with_retry_file(
    entity: str,
    src_path: Path,
    model,
    prompt_content: str,
    example_json: str,
    paths: ExtractionPaths,
):
    """Retry wrapper for a single source file."""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 Attempt {attempt}/{MAX_RETRIES} for file {src_path.name}")
        ok = process_single_source_file(
            entity, src_path, model, prompt_content, example_json, paths
        )
        if ok:
            return True
        if attempt < MAX_RETRIES:
            wait = 5 * attempt
            print(f"⏳ Retrying in {wait}s...")
            time.sleep(wait)
    return False


# ────────────────────────────────────────────────────────────── #
# MAIN
# ────────────────────────────────────────────────────────────── #

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Entity/relationship extraction for any graph topic."
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--entity", dest="entity", help="Entity/topic prefix (before '_-').")
    g.add_argument("--all", action="store_true", help="Process all entities in processed/.")
    p.add_argument("--force", action="store_true", help="Re-run even if JSON already exists.")
    p.add_argument("--graph-name", help="Graph/topic name (uses data/{graph-name} as base).")
    p.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    p.add_argument("--schema-path", help="Path to schema_keys.json.")
    p.add_argument(
        "--example-path",
        help="Path to example_entity_extraction.json.",
    )
    p.add_argument("--prompt-path", help="Path to prompt template.")
    p.add_argument("--output-dir", help="Directory to write extracted JSON.")
    p.add_argument(
        "--allow-extra-nodes",
        action="store_true",
        help="Allow LLM to introduce nodes/edges beyond schema (omit schema JSON from prompt).",
    )
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

    schema_path = (
        Path(args.schema_path)
        if args.schema_path
        else base_dir / "config" / "schema_keys.json"
    )
    example_json_path = (
        Path(args.example_path)
        if args.example_path
        else base_dir / "config" / "llm_schema_example.json"
    )
    prompt_path = (
        Path(args.prompt_path)
        if args.prompt_path
        else base_dir / "config" / "prompt.ini"
    )

    PATHS = ExtractionPaths(
        base_dir=base_dir,
        processed_dir=processed_dir,
        output_dir=output_dir,
        schema_path=schema_path,
        example_json_path=example_json_path,
        prompt_path=prompt_path,
    )

    schema_content = load_schema(PATHS.schema_path)

    # If extra nodes/edges are allowed, do not inject schema JSON into the prompt.
    if args.allow_extra_nodes:
        prompt_content = load_prompt(PATHS.prompt_path, None)
    else:
        prompt_content = load_prompt(PATHS.prompt_path, schema_content)
    example_json = load_example(PATHS.example_json_path)

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("❌ Missing GOOGLE_API_KEY environment variable.")
    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(MODEL_NAME)

    # Determine processing targets
    if args.entity:
        targets = [args.entity]
    else:
        targets = {
            p.name.split("_-_")[0]
            for p in processed_dir.glob("*_-_*.txt")
            if p.name not in IGNORE_FILENAMES
        }
    targets = sorted(targets)

    if not targets:
        sys.exit(f"❌ No matching processed files found in {processed_dir}")

    print(f"🔍 Targets: {', '.join(targets)}")

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

            ok = process_with_retry_file(
                entity, f, model, prompt_content, example_json, PATHS
            )
            if not ok:
                print(f"❌ FAILED after retries: {f.name}")

    print("\n🎉 DONE — all sources processed separately with streaming + chunking.")


if __name__ == "__main__":
    main()
