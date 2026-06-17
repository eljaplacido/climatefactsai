"""
API data models package.

Re-exports all models so that `from api.models import Article` works
whether Python resolves the package (api/models/) or the legacy module (api/models.py).
"""

import importlib
import sys
from pathlib import Path

# The original models live in api/models.py which is shadowed by this package.
# Load it directly as a module from the file path.
_models_file = Path(__file__).resolve().parent.parent / "models.py"
_spec = importlib.util.spec_from_file_location("api._models_file", str(_models_file))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Re-export every public name from that module
from api.models.quota import *  # noqa: F403

for _name in dir(_mod):
    if not _name.startswith("_"):
        globals()[_name] = getattr(_mod, _name)

del _models_file, _spec, _mod, _name, importlib, sys, Path
