"""Provider-neutral SaaS to ITSM synchronization primitives."""

from .core import SyncConfig, build_plan, normalize_name

__all__ = ["SyncConfig", "build_plan", "normalize_name"]
