#!/usr/bin/env python3
"""
combine_json_files.py
---------------------
Combines all .json files in data/json/ into a single structured JSON file,
optionally performing ontology-based normalization before combining.

Features:
    ✅ Auto-detects all ontology files (.obo and .owl) in 'ontologies/' folder
    ✅ Uses fuzzy string matching for local normalization
    ✅ Writes clean all_entities.json (optionally lowercase)
    ✅ Writes ontology_mapping.json grouped by file and key
    ✅ Prints & saves normalization summary (JSON + console)
    ✅ Exports unmatched terms to unmatched_terms.txt
    ✅ Supports --no-normalize and --no-lowercase flags
    ✅ Displays top 10 unmatched terms with closest ontology suggestions
"""

import json
import argparse
import math
from pathlib import Path
from rapidfuzz import process, fuzz
from statistics import mean
from datetime import datetime
from collections import OrderedDict, Counter

from src.kg.utils.paths import resolve_base_dir

try:
    from pronto import Ontology
except ImportError:
    raise SystemExit("❌ Please install dependencies: pip install pronto owlready2 rapidfuzz")

# --- Configuration (set at runtime) ----------------------------------------
BASE_DIR: Path | None = None
INPUT_DIR: Path | None = None
OUTPUT_DIR: Path | None = None
ONTOLOGY_DIR: Path | None = None
SCHEMA_PATH: Path | None = None

OUTPUT_FILE: Path | None = None
MAPPING_FILE: Path | None = None
STATS_FILE: Path | None = None
UNMATCHED_FILE: Path | None = None


def configure_paths(
    base_dir: Path,
    input_dir: Path | None = None,
    ontology_dir: Path | None = None,
    output_dir: Path | None = None,
    schema_path: Path | None = None,
) -> None:
    """Initialize module-level paths for a given graph/topic."""
    global BASE_DIR, INPUT_DIR, OUTPUT_DIR, ONTOLOGY_DIR, OUTPUT_FILE, MAPPING_FILE, STATS_FILE, UNMATCHED_FILE, SCHEMA_PATH
    BASE_DIR = base_dir
    INPUT_DIR = Path(input_dir) if input_dir else BASE_DIR / "json"
    OUTPUT_DIR = Path(output_dir) if output_dir else BASE_DIR / "combined"
    ONTOLOGY_DIR = Path(ontology_dir) if ontology_dir else BASE_DIR / "ontologies"
    SCHEMA_PATH = Path(schema_path) if schema_path else BASE_DIR / "schema" / "schema_keys.json"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = OUTPUT_DIR / "all_entities.json"
    MAPPING_FILE = OUTPUT_DIR / "ontology_mapping.json"
    STATS_FILE = OUTPUT_DIR / "normalization_stats.json"
    UNMATCHED_FILE = OUTPUT_DIR / "unmatched_terms.txt"


def require_paths() -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    if not all([INPUT_DIR, OUTPUT_DIR, ONTOLOGY_DIR, OUTPUT_FILE, MAPPING_FILE, STATS_FILE, UNMATCHED_FILE, SCHEMA_PATH]):
        raise RuntimeError("Paths not configured. Call configure_paths(...) first.")
    return INPUT_DIR, OUTPUT_DIR, ONTOLOGY_DIR, OUTPUT_FILE, MAPPING_FILE, STATS_FILE, UNMATCHED_FILE  # type: ignore

FUZZY_CUTOFF = 85
TOP_UNMATCHED_DISPLAY = 10

# --- Ontology Loading -----------------------------------------------------
def detect_ontologies():
    """Automatically detect ontology files in ontologies/ folder."""
    _, _, ontology_dir, _, _, _, _ = require_paths()
    if not ontology_dir.exists():
        print("⚠️  Ontology directory not found:", ontology_dir)
        return []
    files = [f for f in ontology_dir.glob("*") if f.suffix in (".obo", ".owl")]
    if not files:
        print("⚠️  No ontology files found in 'ontologies/' folder.")
    else:
        print(f"🔎 Found {len(files)} ontology file(s):")
        for f in files:
            print("   •", f.name)
    return files

def load_obo(path: Path, term_dict: dict):
    from pronto import Ontology
    print(f"📘 Parsing OBO ontology: {path.name}")
    ont = Ontology(path)
    for term in ont.terms():
        labels = [term.name] if term.name else []
        labels += [s.description for s in term.synonyms]
        for label in labels:
            if label:
                term_dict[label.lower()] = {"id": term.id, "name": term.name}
    return term_dict

def load_owl(path: Path, term_dict: dict):
    from owlready2 import get_ontology
    print(f"📗 Parsing OWL ontology: {path.name}")
    onto = get_ontology(str(path)).load()
    for cls in onto.classes():
        label = cls.label.first() if hasattr(cls, "label") and cls.label else cls.name
        if label:
            term_dict[label.lower()] = {"id": cls.iri, "name": label}
    return term_dict

def load_ontologies():
    """Load all ontology files (.obo or .owl) found in ontologies/, grouped by type."""
    term_dict_disease = {}
    term_dict_gene = {}
    ontology_files = detect_ontologies()

    for path in ontology_files:
        fname = path.name.lower()
        try:
            if path.suffix == ".obo":
                from pronto import Ontology
                ont = Ontology(path)
                for term in ont.terms():
                    labels = [term.name] if term.name else []
                    labels += [s.description for s in term.synonyms]
                    for label in labels:
                        if not label:
                            continue
                        label_lower = label.lower()
                        # classify by ontology filename
                        if any(x in fname for x in ["hgnc", "gene", "ensembl", "ncbi"]):
                            term_dict_gene[label_lower] = {"id": term.id, "name": term.name}
                        else:
                            term_dict_disease[label_lower] = {"id": term.id, "name": term.name}

            elif path.suffix == ".owl":
                from owlready2 import get_ontology
                onto = get_ontology(str(path)).load()
                for cls in onto.classes():
                    label = cls.label.first() if hasattr(cls, "label") and cls.label else cls.name
                    if not label:
                        continue
                    label_lower = label.lower()
                    if any(x in fname for x in ["hgnc", "gene", "ensembl", "ncbi"]):
                        term_dict_gene[label_lower] = {"id": cls.iri, "name": label}
                    else:
                        term_dict_disease[label_lower] = {"id": cls.iri, "name": label}
        except Exception as e:
            print(f"❌ Failed to load {path.name}: {e}")

    has_gene_ont = len(term_dict_gene) > 0
    has_disease_ont = len(term_dict_disease) > 0
    print(
        f"✅ Loaded {len(term_dict_disease)} disease terms "
        f"and {len(term_dict_gene)} gene terms "
        f"from {len(ontology_files)} file(s)"
    )
    if not has_gene_ont:
        print("⚠️  No gene ontology detected — related_genes will not be normalized.\n")
    elif not has_disease_ont:
        print("⚠️  No disease ontology detected — disease fields will not be normalized.\n")

    return {"disease": term_dict_disease, "gene": term_dict_gene}, ontology_files



# --- Normalization --------------------------------------------------------
def normalize_term(term, term_dict):
    """Return ontology match info for a single term."""
    if not term or not term_dict:
        return {"original": term, "normalized": term, "id": None, "score": 0, "matched": False}

    match, score, _ = process.extractOne(term.lower(), term_dict.keys(), scorer=fuzz.token_sort_ratio)
    if score >= FUZZY_CUTOFF:
        entry = term_dict[match]
        return {"original": term, "normalized": entry["name"], "id": entry["id"], "score": score, "matched": True}
    else:
        return {"original": term, "normalized": term, "id": None, "score": score, "matched": False}

def normalize_entity_lists(data, ontology_dicts, stats, mapping_dict, filename, lowercase=True):
    """Normalize entity lists using field-appropriate ontologies with safe fallbacks."""
    mapping_dict[filename] = mapping_dict.get(filename, {})
    term_dict_disease = ontology_dicts.get("disease", {}) or {}
    term_dict_gene = ontology_dicts.get("gene", {}) or {}

    for key in ["causes", "risk_factors", "symptoms", "diagnosis", "treatments", "related_genes", "subtypes"]:
        if key not in data or not isinstance(data[key], list):
            continue

        new_values = []
        key_mappings = []

        # choose ontology dictionary by field type
        if key == "related_genes":
            if len(term_dict_gene) == 0:
                # no gene ontology → skip normalization
                for item in data[key]:
                    if isinstance(item, str):
                        value = item.lower() if lowercase else item
                        new_values.append(value)
                        key_mappings.append({
                            "original": item,
                            "normalized": value,
                            "id": None,
                            "score": 0,
                            "matched": False,
                            "skipped": True
                        })
                data[key] = new_values
                mapping_dict[filename][key] = key_mappings
                continue
            field_dict = term_dict_gene
        else:
            field_dict = term_dict_disease

        for item in data[key]:
            if not isinstance(item, str):
                new_values.append(item)
                continue

            original_item = item

            # ---------------------------------------------------------------
            # Strip typical gene mutation suffixes before normalization
            # e.g., "msh3 gene mutation" -> "msh3"
            #       "pten gene"          -> "pten"
            #       "msh6 mutation"      -> "msh6"
            # ---------------------------------------------------------------
            if key == "related_genes" and isinstance(item, str):
                cleaned = item.lower()
                for suf in [
                    " gene mutation",
                    " mutation",
                    " gene",
                    " variant",
                ]:
                    if cleaned.endswith(suf):
                        cleaned = cleaned[: -len(suf)]
                item = cleaned.strip()

            # Perform ontology match using the cleaned term
            result = normalize_term(item, field_dict)
            result["original"] = original_item  # keep full original text in mapping

            key_mappings.append(result)
            stats["total"] += 1
            stats["scores"].append(result["score"])

            if result["matched"]:
                stats["matched"] += 1
                value = result["normalized"]    # ontology canonical label
            else:
                stats["unmatched"] += 1
                stats["unmatched_terms"].add(original_item)
                value = original_item           # fall back to original string

            # keep lowercase behavior consistent with rest of pipeline
            new_values.append(value.lower() if lowercase else value)


        data[key] = new_values
        mapping_dict[filename][key] = key_mappings

    return data

def _ontology_match_strength(match_info):
    """
    Derive ontology match strength M in [0.3, 1.0] from mapping info.
    """
    if not match_info:
        return 0.4
    if match_info.get("matched"):
        return 1.0
    score = match_info.get("score", 0)
    if score >= 90:
        return 0.7  # synonym-level
    if score >= 70:
        return 0.5  # partial fuzzy
    return 0.4

def _source_reliability(rec):
    if isinstance(rec, dict):
        vals = list(rec.values())
        if vals:
            try:
                return sum(float(v) for v in vals) / len(vals)
            except Exception:
                return 0.5
    return 0.5

def _compute_weights(values, mapping_infos, reliability_map):
    """
    Compute per-value edge weights using multi-factor formula:
      w = log(1+f) * C * M * S
    where f = frequency, C = extraction confidence (default 1.0),
          M = ontology match strength, S = source reliability (avg).
    """
    weights = []
    freq = Counter(values)
    S = _source_reliability(reliability_map)
    for idx, val in enumerate(values):
        f = freq.get(val, 1)
        C = 1.0
        m_info = mapping_infos[idx] if idx < len(mapping_infos) else {}
        M = _ontology_match_strength(m_info)
        w = math.log(1 + f) * C * M * S
        weights.append({
            "value": val,
            "weight": w,
            "f": f,
            "C": C,
            "M": M,
            "S": S,
        })
    return weights

def create_matched_only_dataset(combined, mapping_file: Path, output_dir: Path, schema_path: Path):
    """
    Create a filtered dataset containing only ontology-matched terms,
    using schema/schema_keys.json to preserve field order and empty placeholders.
    """
    matched_file = output_dir / "all_entities_matched.json"
    matched_combined = {"records": []}

    # --- Load ontology mapping ---------------------------------------------------
    if not mapping_file.exists():
        print(f"⚠️  Ontology mapping file not found at: {mapping_file}")
        return

    with open(mapping_file, "r", encoding="utf-8") as f:
        mapping_data = json.load(f)

    # --- Load schema to determine keys -----------------------------------------
    schema_keys = []
    node_graph_mode = False
    if Path(schema_path).exists():
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_json = json.load(f)
                # If schema uses node_types (graph-centric), just carry through records without pruning
                if isinstance(schema_json, dict) and "node_types" in schema_json:
                    node_graph_mode = True
                else:
                    schema_keys = list(schema_json.keys())
                print(f"✅ Loaded schema keys from {schema_path}")
        except Exception as e:
            print(f"⚠️  Failed to read schema file ({schema_path}): {e}")
    if node_graph_mode:
        matched_combined["records"] = combined.get("records", [])
        matched_file.write_text(json.dumps(matched_combined, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"📄 Created matched-only dataset (pass-through) → {matched_file}")
        return
    if not schema_keys:
        print(f"⚠️  Schema file not found or empty at {schema_path}, using dynamic keys")
        all_possible = set()
        for fd in mapping_data.values():
            all_possible |= set(fd.keys())
        schema_keys = sorted(list(all_possible))

    # --- Build matched-only dataset ---------------------------------------------
    for filename, file_data in mapping_data.items():
        # find original record
        original = next((d for d in combined["records"] if d.get("_source_file") == filename), None)
        if not original:
            continue

        entity_name = original.get("disease_name") or original.get("name")
        if not entity_name:
            continue

        new_entry = OrderedDict()
        # Keep both for backwards compatibility
        new_entry["name"] = entity_name
        if original.get("disease_name"):
            new_entry["disease_name"] = original.get("disease_name")

        # pass through auxiliary metadata if present
        for aux_key in ["_source_file", "source_reliability", "_edge_weights"]:
            if aux_key in original:
                new_entry[aux_key] = original[aux_key]

        has_matched = False

        for key in schema_keys:
            if key in ("disease_name", "name"):
                continue
            matched_terms = []
            for m in file_data.get(key, []):
                if m.get("matched") is True:
                    norm = (m.get("normalized") or "").strip()
                    if norm:
                        matched_terms.append(norm.lower())
            new_entry[key] = matched_terms  # preserve empty
            if matched_terms:
                has_matched = True

        if has_matched:
            matched_combined["records"].append(new_entry)

    # --- Write output ------------------------------------------------------------
    if not matched_combined["records"]:
        print("⚠️  No matched entries found — check ontology_mapping.json or normalization output.")
    else:
        with open(matched_file, "w", encoding="utf-8") as f:
            json.dump(matched_combined, f, indent=2, ensure_ascii=False)
        print(f"📄 Created matched-only dataset → {matched_file}")


# --- Combination Logic ----------------------------------------------------
def combine_json_files(no_normalize=False, lowercase=True):
    input_dir, output_dir, _, output_file, mapping_file, stats_file, unmatched_file = require_paths()
    schema_path = SCHEMA_PATH or Path("schema/schema_keys.json")
    schema_json = {}
    graph_mode = False
    if schema_path.exists():
        try:
            schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
            if isinstance(schema_json, dict) and "node_types" in schema_json:
                graph_mode = True
                print("ℹ️  Detected node_types in schema — skipping ontology normalization.")
        except Exception as e:
            print(f"⚠️  Could not parse schema file at {schema_path}: {e}")
    combined = {"records": []}
    mapping_dict = {}
    stats = {"total": 0, "matched": 0, "unmatched": 0, "scores": [], "unmatched_terms": set()}

    schema_path = BASE_DIR / "schema" / "schema_keys.json" if BASE_DIR else output_dir.parent / "schema" / "schema_keys.json"
    ontology_dicts, ontology_files = ({}, []) if no_normalize or graph_mode else load_ontologies()

    json_files = sorted(input_dir.glob("*.json"))
    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    for file in json_files:
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            # Graph-style schema: accept entire document as-is
            if graph_mode and isinstance(data, dict):
                data["_source_file"] = file.name
                combined["records"].append(data)
                print(f"✅ Added {file.name} (graph schema)")
                continue

            if isinstance(data, dict) and (data.get("disease_name") or data.get("name")):
                # tag source filename so matched-only export can join correctly
                data["_source_file"] = file.name
                # normalize primary name key to lower for consistency
                primary_name = data.get("disease_name") or data.get("name")
                if lowercase and isinstance(primary_name, str):
                    primary_name = primary_name.lower()
                # use topic-agnostic primary name field
                if primary_name:
                    data["name"] = primary_name

                if not no_normalize and not graph_mode:
                    data = normalize_entity_lists(data, ontology_dicts, stats, mapping_dict, file.name, lowercase=lowercase)
                elif lowercase:
                    for key in ["causes", "risk_factors", "symptoms", "diagnosis", "treatments", "related_genes", "subtypes"]:
                        if key in data and isinstance(data[key], list):
                            data[key] = [v.lower() if isinstance(v, str) else v for v in data[key]]

                # compute edge weights using mapping_dict and source reliability metadata
                weights = {}
                if not graph_mode:
                    reliability_map = data.get("source_reliability", {})
                    for key in ["causes", "risk_factors", "symptoms", "diagnosis", "treatments", "related_genes", "subtypes"]:
                        if key in data and isinstance(data[key], list):
                            mapping_infos = mapping_dict.get(file.name, {}).get(key, [])
                            weights[key] = _compute_weights(data[key], mapping_infos, reliability_map)
                    if weights:
                        data["_edge_weights"] = weights

                combined["records"].append(data)
                print(f"✅ Added {file.name}{' (no normalization)' if no_normalize else ''}")
            else:
                print(f"⚠️ Skipping {file.name} (missing primary name field)")
        except json.JSONDecodeError as e:
            print(f"❌ Error reading {file.name}: {e}")

    # Write clean combined output
    output_file.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")

    if no_normalize or graph_mode:
        print(f"\n📦 Combined {len(combined['records'])} files → {output_file}")
        print("⚙️  Normalization skipped (--no-normalize or graph schema)")
        return

    # Write ontology mapping
    mapping_file.write_text(json.dumps(mapping_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- Export matched-only dataset ---------------------------------
    create_matched_only_dataset(combined, mapping_file, output_dir, schema_path=schema_path)

    # --- Summary ----------------------------------------------------------
    if stats["total"] > 0:
        avg_score = mean(stats["scores"])
        match_rate = (stats["matched"] / stats["total"]) * 100
        summary = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ontology_files": [str(x) for x in ontology_files],
            "total_terms_processed": stats["total"],
            "matched_terms": stats["matched"],
            "unmatched_terms": stats["unmatched"],
            "match_rate_percent": round(match_rate, 2),
            "average_match_score": round(avg_score, 2),
            "lowercase_enabled": lowercase,
            "output_file": str(output_file),
            "ontology_mapping_file": str(mapping_file),
            "unmatched_terms_file": str(unmatched_file),
        }

        print("\n📊 Normalization Summary")
        print("────────────────────────────")
        print(f"Total terms processed : {summary['total_terms_processed']}")
        print(f"Matched to ontology   : {summary['matched_terms']} ({match_rate:.1f}%)")
        print(f"Unmatched terms       : {summary['unmatched_terms']}")
        print(f"Average match score   : {avg_score:.1f}")
        print(f"Ontologies loaded     : {len(ontology_files)}")

        stats_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

        if stats["unmatched_terms"]:
            sorted_terms = sorted(stats["unmatched_terms"], key=str.lower)
            unmatched_file.write_text("\n".join(sorted_terms), encoding="utf-8")
            print(f"\n🧾 Summary saved to {stats_file}")
            print(f"🧠 Ontology mapping saved to {mapping_file}")
            print(f"🚫 Unmatched terms saved to {unmatched_file}")

            print("\n🔍 Top Unmatched Terms (with closest ontology suggestions):")
            print("────────────────────────────────────────────────────────────")
            sample_terms = sorted_terms[:TOP_UNMATCHED_DISPLAY]
            # use the combined dictionaries for fuzzy suggestion search
            combined_terms = {}
            combined_terms.update(ontology_dicts.get("disease", {}))
            combined_terms.update(ontology_dicts.get("gene", {}))

            for term in sample_terms:
                if not combined_terms:
                    print(f"• {term}  →  (no ontology data available)")
                    continue

                suggestion, score, _ = process.extractOne(term.lower(), combined_terms.keys(), scorer=fuzz.token_sort_ratio)
                best = combined_terms.get(suggestion, {"id": "—", "name": suggestion})
                print(f"• {term}  →  {best['name']}  (score: {score:.1f}, id: {best['id']})")

        else:
            print(f"\n🧾 Summary saved to {stats_file}")
            print(f"🧠 Ontology mapping saved to {mapping_file}")
            print("✅ All terms matched to ontology!")
    else:
        print("\n📊 No terms found for normalization.")

    print(f"\n📦 Combined {len(combined['records'])} files → {output_file}")

# --- CLI Entry Point ------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Combine and optionally normalize JSON files using local ontologies (topic-agnostic)."
    )
    parser.add_argument("--no-normalize", action="store_true", help="Skip ontology normalization.")
    parser.add_argument("--no-lowercase", action="store_true", help="Preserve original capitalization.")
    parser.add_argument("--graph-name", help="Graph/topic name (uses data/{graph} as base).")
    parser.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    parser.add_argument("--input-dir", help="Override input directory (default: {base}/json).")
    parser.add_argument("--ontology-dir", help="Override ontology directory (default: {base}/ontologies).")
    parser.add_argument("--output-dir", help="Override output directory (default: {base}/combined).")
    args = parser.parse_args()

    base_dir = resolve_base_dir(args.graph_name, args.data_location, create=True)
    configure_paths(base_dir, input_dir=args.input_dir, ontology_dir=args.ontology_dir, output_dir=args.output_dir)

    combine_json_files(no_normalize=args.no_normalize, lowercase=not args.no_lowercase)
