import re
from .registry import register_cleaner
from .default import basic_clean


BOILERPLATE_PATTERNS = [
    r"^An official website of the United States government$",
    r"^Here’s how you know$",
    r"^Official websites use .gov",
    r"^Secure .gov websites use HTTPS",
    r"^A lock \( \) or https:// means",
    r"^Share sensitive information only",
    r"^See also$",
    r"^External links$",
    r"^References$",
    r"^Navigation menu$",
    r"^Search$",
    r"^Skip to main content$",
]


def normalize_text(text: str) -> str:
    text = text.replace("\u00A0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_boilerplate_lines(text: str) -> str:
    lines = [ln.rstrip() for ln in text.split("\n")]
    cleaned = []
    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            cleaned.append("")
            continue
        if any(re.match(p, stripped, re.IGNORECASE) for p in BOILERPLATE_PATTERNS):
            continue
        cleaned.append(ln)
    return "\n".join(cleaned)


def apply_global_trimming_rules(text: str) -> str:
    lines = text.split("\n")
    cut_index = None
    for i, line in enumerate(lines):
        if re.search(r"^\s*-\s*patient handouts\s*$", line, flags=re.IGNORECASE):
            cut_index = i
            break
    if cut_index is not None:
        lines = lines[cut_index + 1 :]
    trimmed = "\n".join(lines)
    match = re.search(
        r"^##\s*Start Here\s*$", trimmed, flags=re.IGNORECASE | re.MULTILINE
    )
    if match:
        start_pos = match.start()
        trimmed = trimmed[:start_pos]
    trimmed = normalize_text(trimmed)
    return trimmed


@register_cleaner("medlineplus")
def clean_medlineplus(raw_content: str, suffix: str) -> str:
    text = basic_clean(raw_content, suffix)
    text = strip_boilerplate_lines(text)
    text = apply_global_trimming_rules(text)
    return text
