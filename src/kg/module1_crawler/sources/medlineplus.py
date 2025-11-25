from typing import Dict, Any, Optional
from datetime import datetime, timezone
import re
import html
import xml.etree.ElementTree as ET
import requests

from .registry import register_source


@register_source("medlineplus", reliability=0.8)
def crawl_medlineplus_for_name(cfg, session, helpers: Dict[str, Any], entity_name: str) -> None:
    if not cfg.enabled_sources["medlineplus"]:
        return

    log = helpers["log"]
    checksum = helpers["checksum"]
    slugify_name = helpers["slugify_name"]
    save_file = helpers["save_file"]
    write_metadata = helpers["write_metadata"]
    http_get_with_retries = helpers["http_get_with_retries"]

    MEDLINEPLUS_SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"
    _TAG_RE = re.compile(r"<[^>]+>")

    def _clean_text(x: str) -> str:
        if not x:
            return ""
        x = html.unescape(x)
        x = _TAG_RE.sub("", x)
        return re.sub(r"\s+", " ", x).strip()

    def _norm(s: str) -> str:
        s = s.lower()
        s = _TAG_RE.sub("", s)
        s = html.unescape(s)
        s = re.sub(r"[^a-z0-9\s]+", " ", s)
        return re.sub(r"\s+", " ", s).strip()

    def _token_join(s: str) -> str:
        return _norm(s).replace(" ", "")

    def medlineplus_search(name: str) -> Optional[Dict[str, Any]]:
        params = {
            "db": "healthTopics",
            "term": name,
            "retmax": 8,
            "rettype": "brief",
        }
        r, status = http_get_with_retries(MEDLINEPLUS_SEARCH_URL, params=params, session=session, cfg=cfg)
        if r is None:
            log(f"[WARN] MedlinePlus query failed for '{name}' (no response)")
            return None
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            log(f"[WARN] MedlinePlus HTTP error for '{name}': {e}")
            return None
        try:
            root = ET.fromstring(r.text)
        except Exception as e:
            log(f"[WARN] MedlinePlus XML parse error for '{name}': {e}")
            return None
        docs = []
        for doc in root.findall(".//document"):
            url = doc.attrib.get("url", "")
            rank = int(doc.attrib.get("rank", "999999"))
            title, alt_titles, full_summary = "", [], ""
            for content in doc.findall("content"):
                cname = (content.attrib.get("name") or "").lower()
                text = _clean_text("".join(content.itertext()))
                if cname == "title":
                    title = text
                elif cname == "alttitle":
                    alt_titles.append(text)
                elif cname == "fullsummary":
                    full_summary = text
            if url:
                docs.append(
                    {
                        "url": url,
                        "rank": rank,
                        "title": title,
                        "alt_titles": alt_titles,
                        "summary": full_summary,
                    }
                )
        if not docs:
            log(f"[INFO] No MedlinePlus results for '{name}'")
            return None
        q_norm = _norm(name)
        q_join = _token_join(name)
        qualifiers = {
            "male",
            "female",
            "men",
            "women",
            "pregnancy",
            "pediatric",
            "child",
            "children",
        }
        query_has_qualifier = any(q in q_norm.split() for q in qualifiers)

        def score(doc: Dict[str, Any]) -> float:
            s = 0.0
            urlkey = re.search(r"/([^/]+)\.html?$", doc["url"].lower())
            urlkey = urlkey.group(1) if urlkey else ""
            if urlkey == q_join:
                s += 120.0
            if not query_has_qualifier and urlkey.startswith(
                (
                    "male",
                    "female",
                    "pregnancy",
                    "child",
                    "pediatric",
                    "men",
                    "women",
                )
            ):
                s -= 60.0
            title_norm = _norm(doc["title"])
            if title_norm == q_norm:
                s += 100.0
            elif q_norm and q_norm in title_norm:
                s += 35.0
            for at in doc["alt_titles"]:
                at_norm = _norm(at)
                if at_norm == q_norm:
                    s += 40.0
                elif q_norm and q_norm in at_norm:
                    s += 15.0
            if q_norm and q_norm in _norm(doc["summary"]):
                s += 10.0
            s += max(0.0, 30.0 - min(doc["rank"], 30))
            return s

        for d in docs:
            d["score"] = score(d)
        return max(docs, key=lambda d: d["score"])

    def fetch_medlineplus_html(url: str):
        r, status = http_get_with_retries(url, session=session, cfg=cfg)
        if r is None:
            log(f"[WARN] MedlinePlus fetch failed for {url} (no response)")
            return "", status
        try:
            r.raise_for_status()
        except requests.HTTPError as e:
            log(f"[WARN] MedlinePlus HTTP error for {url}: {e}")
            return "", r.status_code
        return r.text, r.status_code

    slug = slugify_name(entity_name)
    out_path = cfg.raw_dir / f"{slug}_medlineplus.html"
    if out_path.exists():
        log(f"[SKIP] MedlinePlus already exists: {out_path}")
        return

    best = medlineplus_search(entity_name)
    if not best or not best.get("url"):
        return

    html_doc, status = fetch_medlineplus_html(best["url"])
    if not html_doc:
        return

    save_file(html_doc, out_path)
    meta = {
        "name": entity_name,
        "slug": slug,
        "source_type": "medlineplus",
        "url": best["url"],
        "path": str(out_path),
        "crawl_timestamp": datetime.now(timezone.utc).isoformat(),
        "checksum": checksum(html_doc),
        "http_status": status,
        "n_bytes": len(html_doc.encode("utf-8")),
        "source_details": {
            "title": best.get("title", ""),
            "alt_titles": best.get("alt_titles", []),
            "summary_snippet": (best.get("summary") or "")[:400],
            "score": best.get("score"),
            "rank": best.get("rank"),
        },
        "license": "Public domain (U.S. NIH / NLM)",
    }
    write_metadata(meta)
    log(f"[SOURCE] Downloaded from: {best['url']}")
