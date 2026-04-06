"""
Client for SQL Debug Env - connects to the server via WebSocket.
Inherits from OpenEnv EnvClient which provides from_docker_image(), reset(), step(), close().
"""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

try:
    from .models import SqlDebugAction, SqlDebugObservation, SqlDebugState
except ImportError:
    from models import SqlDebugAction, SqlDebugObservation, SqlDebugState


class SqlDebugEnv(EnvClient[SqlDebugAction, SqlDebugObservation, SqlDebugState]):
    """
    Client for the SQL Debug environment.

    Usage (async):
        env = await SqlDebugEnv.from_docker_image("sql_debug_env:latest")
        result = await env.reset(task_id="fix_query")
        result = await env.step(SqlDebugAction(sql_query="SELECT ..."))
        await env.close()
    """

    def _step_payload(self, action: SqlDebugAction) -> Dict[str, Any]:
        """Convert action to JSON for the server."""
        return {"sql_query": action.sql_query}

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[SqlDebugObservation]:
        """Parse server JSON response into StepResult."""
        obs_data = payload.get("observation", {})

        observation = SqlDebugObservation(
            task_id=obs_data.get("task_id", ""),
            task_description=obs_data.get("task_description", ""),
            schema_info=obs_data.get("schema_info", ""),
            broken_query=obs_data.get("broken_query"),
            explain_plan=obs_data.get("explain_plan"),
            query_result=obs_data.get("query_result"),
            error_message=obs_data.get("error_message"),
            grading_info=obs_data.get("grading_info", {}),
            done=payload.get("done", False),
            reward=payload.get("reward", 0.0),
            metadata=obs_data.get("metadata", {}),
        )

        return StepResult(
            observation=observation,
            reward=payload.get("reward", 0.0),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> SqlDebugState:
        """Parse server state JSON into SqlDebugState."""
        return SqlDebugState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_task_id=payload.get("current_task_id", "fix_query"),
            best_score=payload.get("best_score", 0.0),
        )
