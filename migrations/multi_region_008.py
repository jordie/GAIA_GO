#!/usr/bin/env python3
"""
Compatibility shim for migration module naming.

Older code imports `migrations.multi_region_008`, while the actual migration
file is `008_multi_region.py`. This shim loads the real module by path and
re-exports its public functions.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_module_path = Path(__file__).with_name("008_multi_region.py")
_spec = spec_from_file_location("migrations.008_multi_region", _module_path)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load migration module from {_module_path}")

_module = module_from_spec(_spec)
_spec.loader.exec_module(_module)

migrate = _module.migrate
rollback = getattr(_module, "rollback", None)

__all__ = ["migrate", "rollback"]
