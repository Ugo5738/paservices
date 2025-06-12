import importlib as _importlib

# Proxy the real pytest module
_real_pytest = _importlib.import_module('pytest')

# Bring in FixtureDef from pytest fixtures
from _pytest.fixtures import FixtureDef as _FixtureDef

# Expose all attributes from real pytest
for _attr in dir(_real_pytest):
    if not _attr.startswith('_'):
        globals()[_attr] = getattr(_real_pytest, _attr)

# Ensure FixtureDef is available in pytest namespace
FixtureDef = _FixtureDef

# Define __all__ for the module
__all__ = [name for name in dir() if not name.startswith('_')]
