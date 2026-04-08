"""
Top-level server/app.py — required by openenv validate.

Re-exports the FastAPI `app` instance from the incident_env package so the
validator can find it at the conventional `server/app.py` location.
"""

import sys
import os

# Ensure the repo root is on sys.path so that `incident_env` is importable.
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from incident_env.server.app import app  # noqa: E402, F401

if __name__ == "__main__":
    from incident_env.server.app import main
    main()
