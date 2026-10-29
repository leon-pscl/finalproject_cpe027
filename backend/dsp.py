"""Top-level stub to expose dsp module for tests expecting a flat import path.
This re-exports everything from the actual `app.dsp` package.
"""
from app import dsp as _dsp
# Re-export public names
globals().update({name: getattr(_dsp, name) for name in dir(_dsp) if not name.startswith('_')})
