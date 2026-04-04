"""OpenLLMetry-style instrumentation adapter."""

from __future__ import annotations


class OpenLLMetryAdapter:
    """Capture lightweight trace metadata with optional Traceloop support."""

    def __init__(self):
        try:
            from traceloop.sdk import Traceloop  # noqa: F401

            self.available = True
        except ImportError:
            self.available = False

    def instrument_fork(self, fork_handle: int) -> dict:
        return {
            "fork_handle": fork_handle,
            "available": self.available,
            "trace_name": f"openlvm-fork-{fork_handle}",
        }
