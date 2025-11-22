from .registry import register_cleaner
from .default import basic_clean


@register_cleaner("wikipedia")
def clean_wikipedia(raw_content: str, suffix: str) -> str:
    """Wikipedia-specific cleaner (currently base clean only)."""
    return basic_clean(raw_content, suffix)
