import sys, pathlib
# Ensure backend/app is on import path for pytest collection
backend_app = pathlib.Path(__file__).parent / 'backend' / 'app'
if str(backend_app) not in sys.path:
    sys.path.insert(0, str(backend_app))
