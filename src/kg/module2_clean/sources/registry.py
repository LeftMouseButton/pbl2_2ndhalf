from typing import Callable, Dict

REGISTERED_CLEANERS: Dict[str, Callable[[str, str], str]] = {}

def register_cleaner(source_slug: str):
    """
    Decorator used by cleaning modules to register custom
    source-specific transformations without editing clean.py.
    """
    def wrapper(fn):
        REGISTERED_CLEANERS[source_slug] = fn
        return fn
    return wrapper
