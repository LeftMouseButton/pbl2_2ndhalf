#!/usr/bin/env python3
"""
combine_json_files.py
---------------------

Topic-agnostic JSON combiner and ontology normalizer for ANY knowledge graph.

Features:
    ✔ Reads JSON from data/{graph}/json_validated/
    ✔ Supports both graph-documents ({entities:[], relationships:[]})
      and single-entity JSON objects
    ✔ Auto-detects ANY ontology in data/{graph}/ontologies/
    ✔ Performs fuzzy text-based ontology normalization on ALL attributes
      across ALL entity types
    ✔ Skips normalization automatically if no ontology files exist
    ✔ Produces:
         - combined/all_entities.json
         - combined/ontology_mapping.json
         - combined/normalization_stats.json
         - combined/unmatched_terms.txt
"""

import json
import argparse
import math
from pathlib import Path
from rapidfuzz import process, fuzz
from statistics import mean
from datetime import datetime
from collections import OrderedDict, defaultdict

from src.kg.utils.paths import resolve_base_dir

try:
    from pronto import Ontology
except ImportError:
    raise SystemExit("❌ Missing dependency: pip install pronto owlready2 rapidfuzz")

###############################################################################
# PATH CONFIGURATION
###############################################################################

BASE_DIR: Path | None = None
INPUT_DIR: Path | None = None
OUTPUT_DIR: Path | None = None
ONTOLOGY_DIR: Path | None = None
OUTPUT_FILE: Path | None = None
MAPPING_FILE: Path | None = None
STATS_FILE: Path | None = None
UNMATCHED_FILE: Path | None = None


def configure_paths(base_dir: Path):
    """
    Configure directory layout for a given graph.
    Uses the new topic-agnostic directory structure:

        data/{graph}/json_validated/
        data/{graph}/ontologies/
        data/{graph}/combined/
    """
    global BASE_DIR, INPUT_DIR, OUTPUT_DIR, ONTOLOGY_DIR
    global OUTPUT_FILE, MAPPING_FILE, STATS_FILE, UNMATCHED_FILE

    BASE_DIR = base_dir
    INPUT_DIR = BASE_DIR / "json_validated"
    OUTPUT_DIR = BASE_DIR / "combined"
    ONTOLOGY_DIR = BASE_DIR / "ontologies"

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE = OUTPUT_DIR / "all_entities.json"
    MAPPING_FILE = OUTPUT_DIR / "ontology_mapping.json"
    STATS_FILE = OUTPUT_DIR / "normalization_stats.json"
    UNMATCHED_FILE = OUTPUT_DIR / "unmatched_terms.txt"


###############################################################################
# ONTOLOGY LOADING
###############################################################################

def detect_ontologies():
    """Find .obo or .owl ontology files in data/{graph}/ontologies/."""
    if not ONTOLOGY_DIR.exists():
        print("⚠️  No ontology directory found:", ONTOLOGY_DIR)
        return []

    files = [p for p in ONTOLOGY_DIR.glob("*") if p.suffix in (".obo", ".owl")]
    if not files:
        print("ℹ️  No ontology files found — skipping normalization.")
    else:
        print(f"🔎 Found {len(files)} ontology file(s):")
        for f in files:
            print("   •", f.name)
    return files


def load_obo(path: Path, term_dict: dict):
    print(f"📘 Parsing OBO ontology: {path.name}")
    ont = Ontology(path)
    for term in ont.terms():
        labels = []
        if term.name:
            labels.append(term.name)
        labels.extend(s.description for s in term.synonyms)
        for label in labels:
            if label:
                term_dict[label.lower()] = {
                    "id": term.id,
                    "name": term.name
                }
    return term_dict


def load_owl(path: Path, term_dict: dict):
    from owlready2 import get_ontology
    print(f"📗 Parsing OWL ontology: {path.name}")
    onto = get_ontology(str(path)).load()
    for cls in onto.classes():
        label = cls.label.first() if hasattr(cls, "label") and cls.label else cls.name
        if label:
            term_dict[label.lower()] = {
                "id": cls.iri,
                "name": label
            }
    return term_dict


def load_all_ontologies():
    """
    Topic-agnostic ontology loader.
    - Loads all classes/labels as a flat dictionary.
    - No special handling for gene/disease.
    """
    ontology_files = detect_ontologies()
    if not ontology_files:
        return {}, ontology_files

    term_dict = {}

    for path in ontology_files:
        try:
            if path.suffix == ".obo":
                load_obo(path, term_dict)
            elif path.suffix == ".owl":
                load_owl(path, term_dict)
        except Exception as e:
            print(f"❌ Failed to load {path.name}: {e}")

    print(f"✔ Loaded {len(term_dict)} ontology terms.")
    return term_dict, ontology_files


###############################################################################
# SOURCE WEIGHTS
###############################################################################

def load_source_weights():
    """
    Load source weights from config/sources.json.

    Expected format:
    {
      "wikipedia": { "enabled": true, "weight": 0.7 },
      "medlineplus": { "enabled": true, "weight": 1.0 }
    }
    """
    cfg_path = Path("config") / "sources.json"
    if not cfg_path.exists():
        print(f"ℹ️  No source weight config found at {cfg_path} — skipping source weighting.")
        return {}

    try:
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"⚠️  Failed to read {cfg_path}: {e}")
        return {}

    weights: dict[str, float] = {}
    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        w = cfg.get("weight")
        if isinstance(w, (int, float)):
            weights[name.lower()] = float(w)

    if weights:
        print(f"✔ Loaded {len(weights)} source weight(s) from {cfg_path}")
    else:
        print(f"ℹ️  No valid weights found in {cfg_path} — skipping source weighting.")

    return weights


def infer_source_name(json_path: Path, data, source_weights: dict[str, float]) -> str | None:
    """
    Try to infer which source produced this JSON so we can look up its weight.

    Priority:
      1. Explicit fields in JSON (source, source_name, source_id, meta.*)
      2. Filename heuristics (e.g., 'wikipedia_foo.json')
    """
    if not source_weights:
        return None

    candidates: list[str] = []

    if isinstance(data, dict):
        for key in ("source", "source_name", "source_id"):
            val = data.get(key)
            if isinstance(val, str):
                candidates.append(val)

        meta = data.get("meta") or {}
        if isinstance(meta, dict):
            for key in ("source", "source_name", "source_id"):
                val = meta.get(key)
                if isinstance(val, str):
                    candidates.append(val)

    # Try direct matches against config keys
    for c in candidates:
        key = c.lower()
        if key in source_weights:
            return key

    # Fallback: infer from filename
    stem = json_path.stem.lower()
    for key in source_weights.keys():
        k = key.lower()
        if (
            stem == k
            or stem.startswith(k + "_")
            or stem.endswith("_" + k)
            or f"_{k}_" in stem
        ):
            return key

    return None


def apply_weight_to_confidence(conf, weight: float):
    """
    Multiply a single confidence value by a weight and clamp to [0.0, 1.0].
    """
    if conf is None:
        return None
    try:
        new_val = float(conf) * float(weight)
    except (TypeError, ValueError):
        return conf
    return round(max(0.0, min(1.0, new_val)), 4)


def apply_source_weight_to_graph_document(doc: dict, weight: float):
    """
    Apply source weight to ALL confidence fields in a graph document:
      • entity.confidence
      • entity.attributes[*].confidence
      • relationship.confidence
      • relationship.properties[*].confidence
    """
    if weight is None or weight == 1.0:
        return

    for ent in doc.get("entities", []):
        if isinstance(ent, dict):
            ent["confidence"] = apply_weight_to_confidence(
                ent.get("confidence"), weight
            )
            attrs = ent.get("attributes", {})
            if isinstance(attrs, dict):
                for payload in attrs.values():
                    if isinstance(payload, dict):
                        payload["confidence"] = apply_weight_to_confidence(
                            payload.get("confidence"), weight
                        )

    for rel in doc.get("relationships", []):
        if isinstance(rel, dict):
            rel["confidence"] = apply_weight_to_confidence(
                rel.get("confidence"), weight
            )
            props = rel.get("properties", {})
            if isinstance(props, dict):
                for payload in props.values():
                    if isinstance(payload, dict):
                        payload["confidence"] = apply_weight_to_confidence(
                            payload.get("confidence"), weight
                        )


def apply_source_weight_to_single_entity(ent: dict, weight: float):
    """
    Apply source weight to a single-entity JSON object that follows the
    entity schema (ent.confidence + ent.attributes[*].confidence).
    """
    if weight is None or weight == 1.0 or not isinstance(ent, dict):
        return

    ent["confidence"] = apply_weight_to_confidence(ent.get("confidence"), weight)

    attrs = ent.get("attributes")
    if isinstance(attrs, dict):
        for payload in attrs.values():
            if isinstance(payload, dict):
                payload["confidence"] = apply_weight_to_confidence(
                    payload.get("confidence"), weight
                )


###############################################################################
# NORMALIZATION
###############################################################################

FUZZY_CUTOFF = 85


def normalize_value(value: str, term_dict: dict):
    """Normalize a single value using fuzzy match on ANY ontology term."""
    if not isinstance(value, str) or not value.strip():
        return value, {"matched": False, "score": 0, "id": None, "normalized": value}

    match, score, _ = process.extractOne(value.lower(), term_dict.keys(), scorer=fuzz.token_sort_ratio)
    if score >= FUZZY_CUTOFF:
        entry = term_dict[match]
        return entry["name"], {
            "matched": True,
            "score": score,
            "id": entry["id"],
            "normalized": entry["name"]
        }
    else:
        return value, {
            "matched": False,
            "score": score,
            "id": None,
            "normalized": value
        }


###############################################################################
# COMBINATION LOGIC
###############################################################################

def is_graph_format(j):
    """Detect LLM-style graph document with entities + relationships."""
    return isinstance(j, dict) and "entities" in j and "relationships" in j


def combine_json_files():
    if not INPUT_DIR.exists():
        print(f"❌ Input directory not found: {INPUT_DIR}")
        return

    json_files = sorted(INPUT_DIR.glob("*.json"))
    if not json_files:
        print(f"ℹ️ No JSON files found in {INPUT_DIR}")
        return

    ontology_terms, ontology_files = load_all_ontologies()
    do_normalize = len(ontology_terms) > 0

    # NEW: load per-source weights
    source_weights = load_source_weights()

    combined = {"records": []}
    mapping_dict = {}
    stats = {
        "total": 0,
        "matched": 0,
        "unmatched": 0,
        "scores": [],
        "unmatched_terms": [],
    }

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"❌ Failed to read {jf.name}: {e}")
            continue

        # Determine source and weight for this file
        source_name = infer_source_name(jf, data, source_weights) if source_weights else None
        source_weight = source_weights.get(source_name) if source_name else None

        # --------------------------------------------------------
        # GRAPH MODE (LLM extraction: entities + relationships)
        # --------------------------------------------------------
        if is_graph_format(data):
            print(f"📄 Processing graph document: {jf.name}")
            data["_source_file"] = jf.name
            if source_name:
                data["_source"] = source_name

            if do_normalize:
                mapping_dict[jf.name] = normalize_graph_document(
                    data, ontology_terms, stats
                )

            # Apply source weight BEFORE merging duplicates
            if source_weight is not None:
                apply_source_weight_to_graph_document(data, source_weight)

            # If entity IDs already exist across previous documents, merge them
            merge_graph_into_combined(combined, data)

            continue

        # --------------------------------------------------------
        # SINGLE-ENTITY MODE (fallback)
        # --------------------------------------------------------
        if isinstance(data, dict) and "name" in data:
            print(f"📄 Processing single entity: {jf.name}")
            data["_source_file"] = jf.name
            if source_name:
                data["_source"] = source_name

            if do_normalize:
                mapping_dict[jf.name] = normalize_single_entity(
                    data, ontology_terms, stats
                )

            # Apply source weight BEFORE merging duplicates
            if source_weight is not None:
                apply_source_weight_to_single_entity(data, source_weight)

            merge_single_entity_into_combined(combined, data)

            continue

        print(f"⚠️ Skipped {jf.name} (unrecognized format)")

    # --------------------------------------------------------
    # WRITE OUTPUTS
    # --------------------------------------------------------
    OUTPUT_FILE.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✔ Combined → {OUTPUT_FILE}")

    if do_normalize:
        MAPPING_FILE.write_text(json.dumps(mapping_dict, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"✔ Mapping → {MAPPING_FILE}")

        write_stats(stats, ontology_files)

    return combined


###############################################################################
# NORMALIZATION FOR GRAPH DOCUMENTS
###############################################################################

def normalize_graph_document(doc, ontology_terms, stats):
    """
    Normalize ALL attributes inside:
      • entities[*].attributes[*].value
      • relationship properties[*].value
    """
    mapping = {"entities": {}, "relationships": {}}

    # --- Entities ---
    for ent in doc.get("entities", []):
        ent_map = {}
        for attr, payload in ent.get("attributes", {}).items():
            val = payload.get("value")
            if isinstance(val, str):
                new_val, info = normalize_value(val, ontology_terms)
                payload["value"] = new_val

                ent_map[attr] = info
                update_stats(info, stats)
            else:
                ent_map[attr] = {"matched": False, "score": 0, "id": None}

        mapping["entities"][ent["id"]] = ent_map

    # --- Relationships ---
    for rel in doc.get("relationships", []):
        rel_map = {}
        for prop, payload in rel.get("properties", {}).items():
            val = payload.get("value")
            if isinstance(val, str):
                new_val, info = normalize_value(val, ontology_terms)
                payload["value"] = new_val

                rel_map[prop] = info
                update_stats(info, stats)
            else:
                rel_map[prop] = {"matched": False, "score": 0, "id": None}

        mapping["relationships"][f"{rel['source']}->{rel['relation']}->{rel['target']}"] = rel_map

    return mapping


###############################################################################
# NORMALIZATION FOR SINGLE ENTITY MODE
###############################################################################

def normalize_single_entity(ent, ontology_terms, stats):
    """
    Fallback for single-entity JSON (less common now).
    Normalizes all string values in a flat JSON object.
    """
    mapping = {}

    for key, val in ent.items():
        if isinstance(val, str):
            new_val, info = normalize_value(val, ontology_terms)
            ent[key] = new_val
            mapping[key] = info
            update_stats(info, stats)

        elif isinstance(val, list):
            mapping[key] = []
            for v in val:
                if isinstance(v, str):
                    new_val, info = normalize_value(v, ontology_terms)
                    mapping[key].append(info)
                    update_stats(info, stats)
                else:
                    mapping[key].append({"matched": False, "score": 0, "id": None})

    return mapping


###############################################################################
# DUPLICATE MERGING LOGIC
###############################################################################

def merge_confidence(c_old, c_new):
    """
    Merge two confidence values.
    Rule:
        new_confidence = min(1.0, (avg of both) + 0.05 bonus)
    """
    if c_old is None:
        return c_new
    if c_new is None:
        return c_old
    merged = ((c_old + c_new) / 2) + 0.05
    return round(min(1.0, merged), 4)


def merge_attributes(existing_attrs, new_attrs):
    """
    Merge attributes for a single entity.
    Both have structure:
        attr: { "value": ..., "confidence": ... }
    """

    for key, payload in new_attrs.items():
        if key in existing_attrs:
            # duplicate attribute
            old = existing_attrs[key]
            new = payload

            # If same value → merge confidence
            if old["value"] == new["value"]:
                old["confidence"] = merge_confidence(
                    old.get("confidence"), new.get("confidence")
                )
            else:
                # Different values → keep both? No: keep first, but note as alias
                # Add new value as fallback attribute with suffix "_altN"
                alt_key = key + "_alt"
                suffix = 1
                while alt_key + str(suffix) in existing_attrs:
                    suffix += 1
                existing_attrs[alt_key + str(suffix)] = new
        else:
            # completely new attribute
            existing_attrs[key] = payload

    return existing_attrs


def merge_relationship_properties(existing_props, new_props):
    """
    Same logic as attributes but applied to relationship properties.
    """
    for key, payload in new_props.items():
        if key in existing_props:
            old = existing_props[key]
            new = payload

            if old["value"] == new["value"]:
                old["confidence"] = merge_confidence(
                    old.get("confidence"), new.get("confidence")
                )
            else:
                alt_key = key + "_alt"
                suffix = 1
                while alt_key + str(suffix) in existing_props:
                    suffix += 1
                existing_props[alt_key + str(suffix)] = new
        else:
            existing_props[key] = payload

    return existing_props


###############################################################################
# MERGE ENTIRE GRAPH DOCUMENT INTO "combined"
###############################################################################

def merge_graph_into_combined(combined, new_doc):
    """
    Merges the entities and relationships from a new graph-document
    into the global combined["records"].

    combined["records"] format:
        [
            {
               "entities": [...],
               "relationships": [...]
            },
            ...
        ]
    """

    # If first document, add as-is
    if not combined["records"]:
        combined["records"].append(new_doc)
        return

    # Always merge into the *first* record (global graph)
    base = combined["records"][0]

    existing_ents = {ent["id"]: ent for ent in base["entities"]}
    existing_rels = {
        (rel["source"], rel["relation"], rel["target"]): rel
        for rel in base["relationships"]
    }

    # ========== ENTITIES ==========
    for ent in new_doc["entities"]:
        ent_id = ent["id"]

        if ent_id in existing_ents:
            base_ent = existing_ents[ent_id]

            # Merge entity confidence
            base_ent["confidence"] = merge_confidence(
                base_ent.get("confidence"), ent.get("confidence")
            )

            # Merge attributes
            base_ent["attributes"] = merge_attributes(
                base_ent.get("attributes", {}),
                ent.get("attributes", {})
            )

        else:
            # New entity
            base["entities"].append(ent)
            existing_ents[ent_id] = ent

    # ========== RELATIONSHIPS ==========
    for rel in new_doc["relationships"]:
        key = (rel["source"], rel["relation"], rel["target"])
        if key in existing_rels:
            base_rel = existing_rels[key]

            # Merge relationship confidence
            base_rel["confidence"] = merge_confidence(
                base_rel.get("confidence"), rel.get("confidence")
            )

            # Merge relationship properties
            base_rel["properties"] = merge_relationship_properties(
                base_rel.get("properties", {}),
                rel.get("properties", {})
            )

        else:
            # New relationship
            base["relationships"].append(rel)
            existing_rels[key] = rel


def merge_single_entity_into_combined(combined, ent):
    """
    Merge a single-entity JSON into the combined KG.
    Treat as entity with no relationships.
    """
    if not combined["records"]:
        combined["records"].append({"entities": [ent], "relationships": []})
        return

    base = combined["records"][0]
    existing = {e["id"]: e for e in base["entities"]}

    ent_id = ent["id"]
    if ent_id in existing:
        base_ent = existing[ent_id]

        base_ent["confidence"] = merge_confidence(
            base_ent.get("confidence"), ent.get("confidence")
        )

        base_ent["attributes"] = merge_attributes(
            base_ent.get("attributes", {}),
            ent.get("attributes", {})
        )
    else:
        base["entities"].append(ent)


###############################################################################
# STATS
###############################################################################

def update_stats(info, stats):
    stats["total"] += 1
    stats["scores"].append(info["score"])
    if info["matched"]:
        stats["matched"] += 1
    else:
        stats["unmatched"] += 1
        stats["unmatched_terms"].append(info["normalized"])


def write_stats(stats, ontology_files):
    match_rate = (stats["matched"] / stats["total"]) * 100 if stats["total"] else 0
    avg_score = mean(stats["scores"]) if stats["scores"] else 0

    summary = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ontology_files": [str(x) for x in ontology_files],
        "total_values_normalized": stats["total"],
        "matched_terms": stats["matched"],
        "unmatched_terms": stats["unmatched"],
        "match_rate_percent": round(match_rate, 2),
        "average_fuzzy_score": round(avg_score, 2),
        "unmatched_values": stats["unmatched_terms"],
    }

    STATS_FILE.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    UNMATCHED_FILE.write_text("\n".join(stats["unmatched_terms"]), encoding="utf-8")

    print("📊 Normalization Stats:")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


###############################################################################
# CLI
###############################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine + Normalize topic-agnostic KG JSON files")
    parser.add_argument("--graph-name", required=True, help="Graph/topic name under data/")
    args = parser.parse_args()

    base_dir = resolve_base_dir(args.graph_name, None, create=True)
    configure_paths(base_dir)

    combine_json_files()
