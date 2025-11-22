from typing import Optional
import re

from bs4 import BeautifulSoup

from .registry import register_cleaner


def fix_mojibake(text: str) -> str:
    MOJIBAKE_MAP = {
        "â": "’",
        "â": "-",
        "â": "-",
        "â": "‘",
        "â": "“",
        "â": "”",
        "â": "–",
        "â": "—",
        "â¢": "•",
        "â¦": "…",
        "Â": "",
    }
    for bad, good in MOJIBAKE_MAP.items():
        text = text.replace(bad, good)
    return text


def normalize_text(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = fix_mojibake(text)
    return text.strip()


def html_block_to_text(root) -> str:
    blocks = []
    for tag in root.find_all(["h1", "h2", "h3", "p", "li"], recursive=True):
        txt = tag.get_text(" ", strip=True)
        if not txt:
            continue
        name = tag.name.lower()
        if name == "h1":
            blocks.append(f"# {txt}")
        elif name == "h2":
            blocks.append(f"## {txt}")
        elif name == "h3":
            blocks.append(f"### {txt}")
        elif name == "li":
            blocks.append(f"- {txt}")
        else:
            blocks.append(txt)
    text = "\n\n".join(blocks)
    text = normalize_text(text)
    return text.strip()


def clean_html_to_text(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "lxml")
    for tag in soup(
        [
            "script",
            "style",
            "aside",
            "nav",
            "footer",
            "header",
            "form",
            "noscript",
            "svg",
        ]
    ):
        tag.decompose()
    main = soup.find(attrs={"role": "main"}) or soup.find("main") or soup.body or soup
    text = html_block_to_text(main)
    return text


def clean_plain_text(content: str) -> str:
    text = normalize_text(content)
    return text.strip()


def basic_clean(raw_content: str, suffix: str) -> str:
    """Determine HTML vs plain text and run the appropriate base cleaner."""
    if suffix.lower() == ".html":
        return clean_html_to_text(raw_content)
    return clean_plain_text(raw_content)


@register_cleaner("default")
def clean_default(raw_content: str, suffix: str) -> str:
    """Fallback cleaner with base cleaning."""
    return basic_clean(raw_content, suffix)
