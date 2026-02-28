"""
Lightweight plugin hook system for picoagent.
Hooks are synchronous or async callables registered by name.
"""
import asyncio
from collections import defaultdict
from typing import Callable, Any

_hooks: dict[str, list[Callable]] = defaultdict(list)

def register(event: str, fn: Callable) -> None:
    """Register a hook for an event."""
    _hooks[event].append(fn)

def unregister(event: str, fn: Callable) -> None:
    """Unregister a hook."""
    if fn in _hooks[event]:
        _hooks[event].remove(fn)

async def fire(event: str, **kwargs: Any) -> list[Any]:
    """Fire all hooks for an event. Returns list of results."""
    results = []
    for fn in _hooks.get(event, []):
        try:
            result = fn(**kwargs)
            if asyncio.iscoroutine(result):
                result = await result
            results.append(result)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Hook {event}/{fn.__name__} raised: {e}")
    return results

def clear(event: str | None = None) -> None:
    """Clear hooks for an event, or all hooks if event is None."""
    if event is None:
        _hooks.clear()
    else:
        _hooks[event].clear()
