from typing import Type, Optional, Any, Callable

VIEW_REGISTRY: dict[str, Any] = {}

def register_view(name: str) -> Callable[[Type[Any]], Type[Any]]:
    """Decorator to register a setup view in the decoupled navigation registry."""
    def decorator(cls: Type[Any]) -> Type[Any]:
        VIEW_REGISTRY[name] = cls
        return cls
    return decorator

def get_view(name: str) -> Optional[Any]:
    """Retrieves a registered setup view by identifier."""
    return VIEW_REGISTRY.get(name)
