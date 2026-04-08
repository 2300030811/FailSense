"""
Client for Incident Response Env — connects to the server via WebSocket.
Inherits from OpenEnv EnvClient: from_docker_image(), reset(), step(), close().
"""

from typing import Any, Dict

from openenv.core import EnvClient
from openenv.core.client_types import StepResult

try:
    from .models import IncidentAction, IncidentObservation, IncidentState
except ImportError:
    from models import IncidentAction, IncidentObservation, IncidentState


class IncidentEnv(EnvClient[IncidentAction, IncidentObservation, IncidentState]):
    """Client for the Incident Response environment.

    Usage (async):
        env = await IncidentEnv.from_docker_image("incident_env:latest")
        result = await env.reset(task_id="single_service_failure")
        result = await env.step(IncidentAction(
            severity="P1_critical",
            root_cause_service="user-db",
            root_cause_category="resource_exhaustion",
            root_cause_description="Connection pool exhausted",
            remediation="increase_resources",
            affected_services="user-db,user-service,api-gateway",
        ))
        await env.close()
    """

    def _step_payload(self, action: IncidentAction) -> Dict[str, Any]:
        return {
            "severity": action.severity,
            "root_cause_service": action.root_cause_service,
            "root_cause_category": action.root_cause_category,
            "root_cause_description": action.root_cause_description,
            "remediation": action.remediation,
            "affected_services": action.affected_services,
        }

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[IncidentObservation]:
        obs_data = payload.get("observation", {})
        observation = IncidentObservation(
            task_id=obs_data.get("task_id", ""),
            task_description=obs_data.get("task_description", ""),
            incident_summary=obs_data.get("incident_summary", ""),
            service_topology=obs_data.get("service_topology", ""),
            log_entries=obs_data.get("log_entries", ""),
            metrics_snapshot=obs_data.get("metrics_snapshot", ""),
            timeline=obs_data.get("timeline", ""),
            feedback=obs_data.get("feedback"),
            hint=obs_data.get("hint"),
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

    def _parse_state(self, payload: Dict[str, Any]) -> IncidentState:
        return IncidentState(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
            current_task_id=payload.get("current_task_id", "single_service_failure"),
            best_score=payload.get("best_score", 0.0),
            scenario_seed=payload.get("scenario_seed", 42),
            hint_level=payload.get("hint_level", 0),
            attempts=payload.get("attempts", 0),
        )
