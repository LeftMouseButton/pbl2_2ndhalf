from typing import Dict, Any
from datetime import datetime, timezone

from .registry import register_source


@register_source("wikipedia", reliability=0.6)
def crawl_wikipedia_for_name(cfg, session, helpers: Dict[str, Any], entity_name: str) -> None:
    if not cfg.enabled_sources["wikipedia"]:
        return

    log = helpers["log"]
    checksum = helpers["checksum"]
    slugify_name = helpers["slugify_name"]
    save_file = helpers["save_file"]
    write_metadata = helpers["write_metadata"]
    http_get_with_retries = helpers["http_get_with_retries"]

    WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"

    def fetch_wikipedia_page(title: str):
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": True,
            "redirects": 1,
            "titles": title.replace(" ", "_"),
        }
        r, status = http_get_with_retries(WIKIPEDIA_API, params=params, session=session, cfg=cfg)
        if r is None:
            log(f"[WARN] Wikipedia fetch failed for '{title}' (no response)")
            return "", {"http_status": status}
        try:
            r.raise_for_status()
        except Exception as e:
            log(f"[WARN] Wikipedia HTTP error for '{title}': {e}")
            return "", {"http_status": r.status_code}
        try:
            data = r.json()
        except ValueError as e:
            log(f"[WARN] Wikipedia JSON parse error for '{title}': {e}")
            return "", {"http_status": r.status_code}
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            log(f"[INFO] Wikipedia: no pages found for '{title}'")
            return "", {"http_status": r.status_code}
        page = next(iter(pages.values()))
        extract = page.get("extract") or ""
        pageid = page.get("pageid")
        normalized_title = page.get("title")
        details = {
            "http_status": r.status_code,
            "pageid": pageid,
            "normalized_title": normalized_title,
        }
        return extract, details

    slug = slugify_name(entity_name)
    out_path = cfg.raw_dir / f"{slug}_wikipedia.txt"
    if out_path.exists():
        log(f"[SKIP] Wikipedia already exists: {out_path}")
        return

    text, details = fetch_wikipedia_page(entity_name)
    if not text:
        log(f"[WARN] No Wikipedia extract for '{entity_name}'")
        return

    save_file(text, out_path)
    meta = {
        "name": entity_name,
        "slug": slug,
        "source_type": "wikipedia",
        "source_reliability": cfg.source_reliability.get("wikipedia", 0.6)
        if hasattr(cfg, "source_reliability")
        else helpers["SOURCE_RELIABILITY"].get("wikipedia", 0.6),
        "url": f"https://en.wikipedia.org/wiki/{entity_name.replace(' ', '_')}",
        "path": str(out_path),
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum(text),
        "http_status": details.get("http_status"),
        "n_bytes": len(text.encode("utf-8")),
        "source_details": {
            "pageid": details.get("pageid"),
            "normalized_title": details.get("normalized_title"),
        },
        "license": "CC-BY-SA 4.0",
    }
    write_metadata(meta)
    log(f"[SOURCE] Downloaded from: {meta['url']}")
