from typing import Dict, Any
from datetime import datetime, timezone
from urllib.parse import urljoin

from .registry import register_source


@register_source("hololivewiki", reliability=0.6)
def crawl_hololivewiki(cfg, session, helpers: Dict[str, Any], entity_name: str) -> None:
    """
    Hololive Fan Wiki crawler.

    This version:
      - Fetches the raw HTML page for the given entity.
      - Saves the HTML *unmodified* into cfg.raw_dir as
        {slug}_hololivewiki.txt (for backward compatibility with
        existing pipelines that expect .txt suffixes).
      - Leaves any parsing / cleaning / table extraction to the cleaner.
    """

    if not cfg.enabled_sources.get("hololivewiki", False):
        return

    log = helpers["log"]
    checksum = helpers["checksum"]
    slugify_name = helpers["slugify_name"]
    save_file = helpers["save_file"]
    write_metadata = helpers["write_metadata"]
    http_get_with_retries = helpers["http_get_with_retries"]

    BASE_URL = "https://hololive.wiki/wiki/"

    # ---------------------------------------------------------------
    # URL builder (MediaWiki format: spaces → underscores)
    # ---------------------------------------------------------------
    def build_url(name: str) -> str:
        slug = name.replace(" ", "_")
        return urljoin(BASE_URL, slug)

    # ---------------------------------------------------------------
    # Fetch raw HTML
    # ---------------------------------------------------------------
    def fetch_page(url: str):
        params = {}  # Hololive wiki: no special API params for HTML
        r, status = http_get_with_retries(url, params=params, session=session, cfg=cfg)
        if r is None:
            log(f"[WARN] HololiveWiki fetch failed for '{entity_name}' (no response)")
            return "", {"http_status": status}

        try:
            r.raise_for_status()
        except Exception as e:
            log(f"[WARN] HololiveWiki HTTP error for '{entity_name}': {e}")
            return "", {"http_status": r.status_code}

        html = r.text
        return html, {"http_status": r.status_code}

    # ---------------------------------------------------------------
    # Main process
    # ---------------------------------------------------------------
    slug = slugify_name(entity_name)

    # NOTE:
    #  We intentionally keep the .txt suffix for backward compatibility
    #  with existing pipelines / glob patterns, even though the content
    #  is now HTML.
    out_path = cfg.raw_dir / f"{slug}_hololivewiki.txt"

    if out_path.exists():
        log(f"[SKIP] HololiveWiki already exists: {out_path}")
        return

    url = build_url(entity_name)
    raw_html, details = fetch_page(url)

    if not raw_html:
        log(f"[WARN] No HololiveWiki content for '{entity_name}'")
        return

    # Save the HTML exactly as returned by the site
    save_file(raw_html, out_path)

    meta = {
        "name": entity_name,
        "slug": slug,
        "source_type": "hololivewiki",
        "url": url,
        "path": str(out_path),
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum(raw_html),
        "http_status": details.get("http_status"),
        "n_bytes": len(raw_html.encode("utf-8")),
        "source_details": {},
        "license": "CC-BY-SA 4.0",  # Hololive wiki is CC-BY-SA like Wikipedia
    }
    write_metadata(meta)

    log(f"[SOURCE] Downloaded from: {url}")
