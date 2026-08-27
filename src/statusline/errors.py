"""Error-handling helpers shared across the package."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def handle_exception(
    default: Any, *exceptions: type[BaseException]
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that returns a copy of ``default`` instead of raising.

    Copies ``default`` to avoid aliasing a shared mutable value across calls.

    Args:
        default (Any): Value to return (copied) when the wrapped function raises.
        *exceptions (type[BaseException]): Exception types to catch.

    Returns:
        Callable[[Callable[..., Any]], Callable[..., Any]]: A decorator for
            the target function.

    Examples:
        @handle_exception(0, ValueError)
        def parse(value): ...
    """

    def decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return fn(*args, **kwargs)
            except exceptions:
                return copy.copy(default)

        return wrapper

    return decorate
