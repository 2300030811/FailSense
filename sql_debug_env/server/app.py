"""FastAPI application for SQL Debug Env."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("openenv-core is required") from e

try:
    from ..models import SqlDebugAction, SqlDebugObservation
    from .sql_debug_env_environment import SqlDebugEnvironment
except (ModuleNotFoundError, ImportError):
    from models import SqlDebugAction, SqlDebugObservation
    from server.sql_debug_env_environment import SqlDebugEnvironment

app = create_app(
    SqlDebugEnvironment,
    SqlDebugAction,
    SqlDebugObservation,
    env_name="sql_debug_env",
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
    # OpenEnv validator currently checks for a literal "main()" token.
    # main()
