"""Request-local progress reporting; no shared mutable request state."""
from contextvars import ContextVar
from typing import Callable, Optional

progress_listener: ContextVar[Optional[Callable[[str], None]]] = ContextVar("progress_listener", default=None)


def report_stage(stage: str) -> None:
    listener = progress_listener.get()
    if listener is not None:
        listener(stage)
