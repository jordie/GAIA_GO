"""
Wrapper Core - Hot-reloadable modules for Claude Code wrapper.

This package contains all the logic that can be reloaded without
restarting the wrapper session.

Features:
- Auto-response to permission prompts
- Dangerous command detection
- Session state tracking
- Integration with session_assigner

Usage:
    from wrapper_core import reload_all, get_version

    # Reload all modules after code update
    reload_all()

    # Check module versions
    print(get_version())
"""

import importlib
from datetime import datetime

__version__ = "2.0.0"
__reload_count__ = 0
__last_reload__ = datetime.now().isoformat()

# Module list for reload
_MODULES = [
    "wrapper_core.config",
    "wrapper_core.state",
    "wrapper_core.extractors",
    "wrapper_core.handlers",
]


def reload_all():
    """Reload all wrapper_core modules. Returns success status."""
    global __reload_count__, __last_reload__

    errors = []
    for module_name in _MODULES:
        try:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        except Exception as e:
            errors.append(f"{module_name}: {e}")

    if not errors:
        __reload_count__ += 1
        __last_reload__ = datetime.now().isoformat()
        return True, f"Reloaded {len(_MODULES)} modules"
    else:
        return False, f"Errors: {'; '.join(errors)}"


def get_version():
    """Get version info for all modules."""
    return {
        "core_version": __version__,
        "reload_count": __reload_count__,
        "last_reload": __last_reload__,
        "modules": _MODULES,
    }


# Import submodules for convenience
from . import config, extractors, handlers, state
