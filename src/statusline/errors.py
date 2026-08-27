"""Error-handling helpers shared across the package."""

from __future__ import annotations

import copy
import functools
from typing import TYPE_CHECKING, ParamSpec, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

P = ParamSpec("P")
R = TypeVar("R")
D = TypeVar("D")


def handle_exception(
    default: D, *exceptions: type[BaseException]
) -> Callable[[Callable[P, R]], Callable[P, R | D]]:
    """Decorator that returns a copy of ``default`` instead of raising.

    Copies ``default`` to avoid aliasing a shared mutable value across calls.

    Args:
        default (D): Value to return (copied) when the wrapped function raises.
        *exceptions (type[BaseException]): Exception types to catch.

    Returns:
        Callable[[Callable[P, R]], Callable[P, R | D]]: A decorator for the
            target function; the wrapped function returns its own result or
            a copy of ``default``.

    Examples:
        @handle_exception(0, ValueError)
        def parse(value): ...
    """

    def decorate(fn: Callable[P, R]) -> Callable[P, R | D]:
        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | D:
            try:
                return fn(*args, **kwargs)
            except exceptions:
                return copy.copy(default)

        return wrapper

    return decorate
