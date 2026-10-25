"""Shared test setup.

The pipeline worker must stay off in tests: `with TestClient(app)` runs the app
lifespan, and a live worker would claim the very jobs these tests create and
fail them on missing media. Tests that care about the worker set the flag
themselves (see test_worker.py).
"""

import os

os.environ["WORKER_ENABLED"] = "false"
