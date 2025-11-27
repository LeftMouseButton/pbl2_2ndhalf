"""
Auto-repair validator for Module 3 JSON outputs.
Validated files are written to data/{graph_name}/json_validated/ (originals left untouched).

Usage:
    python -m src.kg.module4_validate_json.validate_json --data-location data/my_graph
    python -m src.kg.module4_validate_json.validate_json data/my_graph/json
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.kg.utils.paths import resolve_base_dir

# ---------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------

SCHEMA_CONFIG: Dict[str, Any] | None = None


def load_schema(schema_path: Path) -> dict:
    """Load and return the JSON schema for validation."""
    try:
        schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        sys.exit(f"❌ Schema file not found at {schema_path}")
    except json.JSONDecodeError as e:
        sys.exit(f"❌ Failed to parse schema JSON: {e}")

    if not isinstance(schema_json, dict):
        sys.exit("❌ Schema file must contain a JSON object at the root level.")
    return schema_json


def configure_schema(schema_path: Path) -> None:
    """Load schema file into memory."""
    global SCHEMA_CONFIG
    SCHEMA_CONFIG = load_schema(schema_path)


def require_schema_config() -> dict:
    if SCHEMA_CONFIG is None:
        raise RuntimeError("Schema not configured.")
    return SCHEMA_CONFIG


def resolve_schema_path(base_dir: Path, override: str | None) -> Path:
    """Resolve schema path using override → data/{graph}/config → config_default fallback."""
    if override:
        path = Path(override)
        if not path.exists():
            sys.exit(f"❌ Schema file not found at override path: {path}")
        return path

    candidates = [
        base_dir / "config" / "schema_keys.json",
        Path("config_default") / "schema_keys.json",
    ]
    for cand in candidates:
        if cand.exists():
            if cand == candidates[1]:
                print(f"⚠️  Schema not found in graph config, using fallback {cand}")
            return cand

    sys.exit("❌ schema_keys.json not found in graph config or config_default/.")


# ---------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------

def _ensure_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except Exception:
        return float(default)


def _normalize_value_conf(entry: Any, template: dict) -> dict:
    """
    Normalize an attribute/properties entry to {"value": ..., "confidence": ...}
    using defaults from the schema template.
    """
    default_value = template.get("value", "")
    default_conf = _ensure_float(template.get("confidence", 0.0), 0.0)

    if isinstance(entry, dict):
        return {
            "value": entry.get("value", default_value),
            "confidence": _ensure_float(entry.get("confidence", default_conf), default_conf),
        }

    if entry is None:
        return {"value": default_value, "confidence": default_conf}

    return {"value": entry, "confidence": default_conf}


def normalize_entities(raw_entities: Any) -> List[Dict[str, Any]]:
    """Repair entity entries based on schema in data/{graph}/config/schema_keys.json."""
    schema = require_schema_config()
    entity_schema = schema.get("entities", {}) or {}

    if isinstance(raw_entities, dict):
        raw_entities = [raw_entities]
    entities = raw_entities if isinstance(raw_entities, list) else []
    fixed: List[Dict[str, Any]] = []

    for ent in entities:
        if not isinstance(ent, dict):
            continue
        ent_type = str(ent.get("type", "") or "").strip()
        ent_schema = entity_schema.get(ent_type, {})
        attrs_schema = ent_schema.get("attributes", {}) or {}

        attrs = ent.get("attributes") if isinstance(ent.get("attributes"), dict) else {}
        for attr_name, attr_template in attrs_schema.items():
            attrs[attr_name] = _normalize_value_conf(
                attrs.get(attr_name),
                attr_template if isinstance(attr_template, dict) else {},
            )

        ent["attributes"] = attrs
        ent["confidence"] = _ensure_float(ent.get("confidence"), ent_schema.get("confidence", 0.0))
        ent["id"] = ent.get("id", "") or ""
        ent["name"] = ent.get("name", "") or ""
        ent["type"] = ent_type

        fixed.append(ent)
    return fixed


def normalize_relationships(raw_rels: Any) -> List[Dict[str, Any]]:
    """Repair relationship entries based on schema in data/{graph}/config/schema_keys.json."""
    schema = require_schema_config()
    rel_schema = schema.get("relationships", {}) or {}

    if isinstance(raw_rels, dict):
        raw_rels = [raw_rels]
    rels = raw_rels if isinstance(raw_rels, list) else []
    fixed: List[Dict[str, Any]] = []

    for rel in rels:
        if not isinstance(rel, dict):
            continue
        rel_type = str(rel.get("relation", "") or "").strip()
        rel_cfg = rel_schema.get(rel_type, {})
        props_schema = rel_cfg.get("properties", {}) or {}

        props = rel.get("properties") if isinstance(rel.get("properties"), dict) else {}
        for prop_name, prop_template in props_schema.items():
            props[prop_name] = _normalize_value_conf(
                props.get(prop_name),
                prop_template if isinstance(prop_template, dict) else {},
            )

        rel["properties"] = props
        rel["confidence"] = _ensure_float(rel.get("confidence"), rel_cfg.get("confidence", 0.0))
        rel["source"] = rel.get("source", "") or ""
        rel["target"] = rel.get("target", "") or ""
        rel["relation"] = rel_type

        fixed.append(rel)
    return fixed


def normalize_document(data: dict) -> dict:
    """Apply schema-aware repairs to a single JSON document."""
    if not isinstance(data, dict):
        return {}

    data = dict(data)  # shallow copy to avoid mutating original
    data["entities"] = normalize_entities(data.get("entities"))
    data["relationships"] = normalize_relationships(data.get("relationships"))
    return data


def validate_file(path: Path, output_dir: Path):
    print(f"🔍 Validating {path.name}...")
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"❌ {path.name}: Invalid JSON — {e}")
        return False

    fixed = normalize_document(data)
    out_path = output_dir / path.name
    out_path.write_text(json.dumps(fixed, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"✅ {path.name}: Validated -> {out_path}")
    return True


def validate_all(target: Path, output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)

    if target.is_file():
        return validate_file(target, output_dir)
    if target.is_dir():
        files = [f for f in sorted(target.glob("*.json")) if f.name != "metadata_unknown.json"]
        if not files:
            print(f"No JSON files found in {target}")
            return False
        ok = [validate_file(f, output_dir) for f in files]
        print(f"\nSummary: {sum(ok)}/{len(files)} passed (and fixed if needed). Output dir: {output_dir}")
        return all(ok)

    print(f"Path not found: {target}")
    return False


# ---------------------------------------------------------------------
# CLI Entry
# ---------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Validate and auto-repair extracted JSON files.")
    p.add_argument(
        "target",
        nargs="?",
        help="File or directory to validate (default: {base}/json).",
    )
    p.add_argument("--graph-name", help="Graph/topic name (uses data/{graph} as base).")
    p.add_argument("--data-location", help="Explicit data directory (overrides --graph-name).")
    p.add_argument("--schema-path", help="Path to schema_keys.json (default: {base}/config/schema_keys.json).")
    p.add_argument("--output-dir", help="Directory to write validated JSON (default: {base}/json_validated).")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    base_dir = resolve_base_dir(args.graph_name, args.data_location, create=True)
    target_path = Path(args.target) if args.target else base_dir / "json"

    schema_path = resolve_schema_path(base_dir, args.schema_path)
    output_dir = Path(args.output_dir) if args.output_dir else base_dir / "json_validated"

    # If schema defines node_types (graph schema), skip validation—assume structured elsewhere
    try:
        schema_json = json.loads(schema_path.read_text(encoding="utf-8"))
        if isinstance(schema_json, dict) and "node_types" in schema_json:
            print(f"Schema uses node_types; skipping Module 4 validation for graph-style schema: {schema_path}")
            sys.exit(0)
    except Exception as e:
        print(f"⚠️  Could not parse schema at {schema_path}: {e}")

    configure_schema(schema_path)

    start = datetime.datetime.now()
    ok = validate_all(target_path, output_dir)
    print(f"\nCompleted in {(datetime.datetime.now() - start).total_seconds():.2f}s")
    sys.exit(0 if ok else 1)
