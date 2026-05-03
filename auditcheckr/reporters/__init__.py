"""Reporter registry."""
from .base import ReporterBase
from .json_reporter import JsonReporter
from .html_reporter import HtmlReporter

REGISTRY: dict[str, type[ReporterBase]] = {
    "json": JsonReporter,
    "html": HtmlReporter,
}


def get_reporter(name: str) -> ReporterBase:
    if name not in REGISTRY:
        raise ValueError(f"Unknown reporter '{name}'. Available: {list(REGISTRY)}")
    return REGISTRY[name]()
