from .registry import register_cleaner
from .default import basic_clean
from bs4 import BeautifulSoup
from bs4.element import Tag
import re


@register_cleaner("hololivewiki")
def clean_hololivewiki(raw_content: str, suffix: str) -> str:
    """
    HololiveWiki cleaner v2 — robust, safe, properly cleaning HTML.

    Output format (Option A):
        ### INFOBOX ###
        ...
        ### END INFOBOX ###

        ### TABLE: Singles ###
        ...
        ### END TABLE ###

        <Plain, readable cleaned article text>
    """

    lower = raw_content.lower()
    looks_like_html = "<html" in lower or "<table" in lower or "<!doctype" in lower

    if not looks_like_html:
        return _clean_legacy_text(raw_content, suffix)

    # Parse HTML
    soup = BeautifulSoup(raw_content, "lxml")

    # 1. Extract infobox + tables
    infobox_block = _extract_infobox_from_html(soup)
    tables_block = _extract_discography_tables_from_html(soup)

    # 2. Remove extracted DOM elements
    _remove_infobox_from_html(soup)
    _remove_discography_tables_from_html(soup)

    # 3. Strip nav/footer/scripts before text extraction
    _strip_non_content_elements(soup)

    # 4. Convert HTML → plaintext
    text = soup.get_text("\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    # 5. Run base cleaner on the plaintext (NOT raw HTML)
    cleaned_body = basic_clean(text, suffix)
    cleaned_body = re.sub(r"\n{3,}", "\n\n", cleaned_body).strip()

    # 6. Assemble final output
    parts = []
    if infobox_block:
        parts.append(infobox_block)
    if tables_block:
        parts.append(tables_block)
    if cleaned_body:
        parts.append(cleaned_body)

    final = "\n\n".join(p.strip() for p in parts if p.strip())
    final = final.replace("[expand]", "").replace("[collapse]", "")
    final = re.sub(r"\n{3,}", "\n\n", final).strip()

    return final


# ======================================================================
# Legacy fallback (plaintext)
# ======================================================================

def _clean_legacy_text(raw_content: str, suffix: str) -> str:
    cleaned = basic_clean(raw_content, suffix)
    lines = cleaned.split("\n")

    infobox_pairs = []
    inline_kv = re.compile(r"^(?P<key>[A-Za-z0-9 \-/]+)\s*:\s*(?P<val>.+)$")
    stacked_key = None

    for line in lines[:120]:
        stripped = line.strip()

        m = inline_kv.match(stripped)
        if m:
            infobox_pairs.append((m.group("key"), m.group("val")))
            continue

        if stacked_key is None:
            if 1 <= len(stripped) <= 40 and re.match(r"^[A-Za-z0-9 \-_/]+$", stripped):
                stacked_key = stripped
        else:
            if stripped:
                infobox_pairs.append((stacked_key, stripped))
            stacked_key = None

    infobox = ""
    if infobox_pairs:
        out = ["### INFOBOX ###"]
        for k, v in infobox_pairs:
            out.append(f"{k}: {v}")
        out.append("### END INFOBOX ###\n")
        infobox = "\n".join(out)

    body = "\n".join(lines)
    body = body.replace("[expand]", "").replace("[collapse]", "")
    body = re.sub(r"\n{3,}", "\n\n", body).strip()

    return (infobox + body).strip()


# ======================================================================
# Strip non-content HTML elements
# ======================================================================

from bs4.element import Tag

def _strip_non_content_elements(soup: BeautifulSoup) -> None:
    """
    Remove obviously non-content tags: scripts, styles, navboxes, panels, etc.
    This version is 100% safe against NoneType errors.
    """

    # Remove script/style/noscript safely
    for tagname in ["script", "style", "noscript"]:
        for elem in list(soup.find_all(tagname)):
            if isinstance(elem, Tag):
                try:
                    elem.decompose()
                except Exception:
                    pass

    # Remove elements by ID safely
    ids_to_remove = {"mw-navigation", "mw-panel", "footer", "catlinks"}

    for ident in ids_to_remove:
        elem = soup.find(id=ident)
        if isinstance(elem, Tag):
            try:
                elem.decompose()
            except Exception:
                pass

    # Remove navboxes/metadata safely
    for div in list(soup.find_all("div")):

        # ---- HARD GUARD 1: Must be a Tag ----
        if not isinstance(div, Tag):
            continue

        # ---- HARD GUARD 2: Must have .get ----
        if not hasattr(div, "get"):
            continue

        # ---- SAFE ACCESS TO div.get("class") ----
        try:
            classes = div.get("class", [])
            if classes is None:
                classes = []
        except Exception:
            # If call fails, skip safely
            continue

        # ---- Identify navbox-like classes ----
        if any(c in classes for c in ["navbox", "vertical-navbox", "metadata"]):
            try:
                div.decompose()
            except Exception:
                pass



# ======================================================================
# INFOBOX extraction + removal
# ======================================================================

def _extract_infobox_from_html(soup: BeautifulSoup) -> str:
    table = soup.find("table", class_=lambda c: c and "infobox" in c)
    if not isinstance(table, Tag):
        return ""

    rows = table.find_all("tr")
    pairs = []
    started = False

    for tr in rows:
        if not isinstance(tr, Tag):
            continue

        cells = tr.find_all(["th", "td"])
        if not cells:
            continue

        if not started and len(cells) == 1:
            started = True
            continue
        started = True

        if len(cells) >= 2:
            try:
                key = cells[0].get_text(" ", strip=True)
                val = " ".join(c.get_text(" ", strip=True) for c in cells[1:])
            except Exception:
                continue

            key = re.sub(r"\s+", " ", key)
            val = re.sub(r"\s+", " ", val)

            if key and val and key.lower() not in {"details"}:
                pairs.append((key, val))

    if not pairs:
        return ""

    out = ["### INFOBOX ###"]
    for k, v in pairs:
        out.append(f"{k}: {v}")
    out.append("### END INFOBOX ###")

    return "\n".join(out)


def _remove_infobox_from_html(soup: BeautifulSoup):
    table = soup.find("table", class_=lambda c: c and "infobox" in c)
    if isinstance(table, Tag):
        try:
            table.decompose()
        except:
            pass


# ======================================================================
# Discography tables extraction + removal
# ======================================================================

_DISC_TABLE_TITLES = {
    "Singles",
    "Collab Singles",
    "Collaboration Singles",
    "Albums",
    "Collab Albums",
    "Solo Covers",
    "Collab Covers",
    "Made for Fubuki",
    "From Foxtail-Grass Studio",
    "From DOVA-SYNDROME",
}


def _extract_discography_tables_from_html(soup: BeautifulSoup) -> str:
    blocks = []
    tables = list(soup.find_all("table"))

    for table in tables:
        # HARD GUARDS
        if not isinstance(table, Tag):
            continue
        if not hasattr(table, "get"):
            continue

        # SAFE get
        try:
            classes = table.get("class", [])
            classes = classes or []
        except:
            continue

        # Match collapsible wikitable
        if "mw-collapsible" not in classes or "wikitable" not in classes:
            continue

        title = _disc_table_title(table)
        if not title:
            continue

        # Inner wikitable
        try:
            inner = table.find("table", class_="wikitable") or table
        except:
            continue
        if not isinstance(inner, Tag):
            continue

        try:
            text = inner.get_text("\n", strip=True)
        except:
            continue

        text = re.sub(r"\n{3,}", "\n\n", text).strip()

        block = (
            f"### TABLE: {title} ###\n"
            f"{text}\n"
            f"### END TABLE ###"
        )
        blocks.append(block)

    return "\n\n".join(blocks)


def _disc_table_title(table: Tag) -> str:
    # Try bold label
    first_tr = table.find("tr")
    if isinstance(first_tr, Tag):
        bold = first_tr.find("b")
        if isinstance(bold, Tag):
            cand = bold.get_text(" ", strip=True)
            cand = re.sub(r"\s+", " ", cand)
            if cand in _DISC_TABLE_TITLES:
                return cand

    # Try caption
    caption = table.find("caption")
    if isinstance(caption, Tag):
        cand = caption.get_text(" ", strip=True)
        cand = re.sub(r"\s+", " ", cand)
        if cand in _DISC_TABLE_TITLES:
            return cand

    return ""


def _remove_discography_tables_from_html(soup: BeautifulSoup):
    tables = list(soup.find_all("table"))

    for table in tables:
        # HARD GUARDS
        if not isinstance(table, Tag):
            continue
        if not hasattr(table, "get"):
            continue

        # SAFE class access
        try:
            classes = table.get("class", [])
            classes = classes or []
        except:
            continue

        if "mw-collapsible" not in classes or "wikitable" not in classes:
            continue

        title = _disc_table_title(table)
        if not title:
            continue

        try:
            table.decompose()
        except:
            pass
