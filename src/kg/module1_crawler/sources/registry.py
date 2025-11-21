# Registry for crawler sources
REGISTERED_SOURCES = {}

def register_source(name: str, reliability: float = 0.5, enabled_by_default: bool = False):
    """
    Decorator that registers crawler functions together with reliability
    and default-enabled flags. This enables fully automatic integration
    with crawler.py without manual edits.
    """
    def wrapper(fn):
        REGISTERED_SOURCES[name] = {
            "fn": fn,
            "reliability": reliability,
            "enabled_by_default": enabled_by_default,
        }
        return fn
    return wrapper
