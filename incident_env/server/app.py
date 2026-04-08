"""FastAPI application for Incident Response Environment."""

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


def main(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
