"""Provider registry — import adapters here and register them."""
from .base import DocumentProvider
from .local_fs import LocalFileSystemProvider

REGISTRY: dict[str, type[DocumentProvider]] = {
    "local": LocalFileSystemProvider,
}


def get_provider(name: str, **kwargs) -> DocumentProvider:
    """Instantiate a provider by its registered name."""
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown provider '{name}'. Available: {list(REGISTRY)}"
        )
    return REGISTRY[name](**kwargs)
