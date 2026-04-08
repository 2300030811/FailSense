"""FastAPI application for Incident Response Environment."""

import sys
import os

# Ensure the parent directory (incident_env/) is on the path so that
# `models` and `server.incident_env_environment` resolve when running
# from the incident_env/ directory (e.g. during openenv validate).
_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _parent not in sys.path:
    sys.path.insert(0, _parent)

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("openenv-core is required") from e

try:
    from ..models import IncidentAction, IncidentObservation
    from .incident_env_environment import IncidentEnvironment
except (ModuleNotFoundError, ImportError):
    from models import IncidentAction, IncidentObservation
    from server.incident_env_environment import IncidentEnvironment

app = create_app(
    IncidentEnvironment,
    IncidentAction,
    IncidentObservation,
    env_name="incident_env",
    max_concurrent_envs=4,
)


@app.get("/")
def read_root():
    return {
        "message": "IncidentEnv — Production Incident Response for AI Agents",
        "status": "running",
        "documentation": "https://github.com/2300030811/FailSense",
        "endpoints": {
            "health": "/health",
            "environment": "/v1/env"
        }
    }


def main(host: str = "0.0.0.0", port: int = None):
    import argparse
    import uvicorn
    if port is None:
        parser = argparse.ArgumentParser()
        parser.add_argument("--port", type=int, default=7860)
        args = parser.parse_args()
        port = args.port
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
