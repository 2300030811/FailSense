"""
Incident Response Environment server implementation.
Manages episode state, generates scenarios, grades agent actions.
"""

import uuid
from typing import Optional

from openenv.core.env_server.interfaces import Environment

try:
    from ..models import IncidentAction, IncidentObservation, IncidentState
    from .scenario_engine import Scenario, generate_scenario, get_task_description, TASK_IDS
    from .graders import grade_action
except ImportError:
    from models import IncidentAction, IncidentObservation, IncidentState
    from server.scenario_engine import Scenario, generate_scenario, get_task_description, TASK_IDS
    from server.graders import grade_action

MAX_STEPS = 5


class IncidentEnvironment(Environment):
    """Production incident response environment.

    Agent receives logs, metrics, and topology for a simulated incident
    and must diagnose root cause, severity, and recommend remediation.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = IncidentState(episode_id=str(uuid.uuid4()))
        self._scenario: Optional[Scenario] = None

    def reset(self, seed=None, episode_id=None, task_id: str = "single_service_failure", **kwargs) -> IncidentObservation:
        """Start a new episode. task_id selects the task, seed selects the variant."""
        if task_id not in TASK_IDS:
            task_id = "single_service_failure"

        actual_seed = seed if seed is not None else 42
        self._scenario = generate_scenario(task_id, actual_seed)

        self._state = IncidentState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_task_id=task_id,
            best_score=0.0,
            scenario_seed=actual_seed,
            hint_level=0,
            attempts=0,
        )

        return IncidentObservation(
            task_id=task_id,
            task_description=get_task_description(task_id),
            incident_summary=self._scenario.incident_summary,
            service_topology=self._scenario.service_topology,
            log_entries=self._scenario.log_entries,
            metrics_snapshot=self._scenario.metrics_snapshot,
            timeline=self._scenario.timeline,
            feedback=None,
            hint=None,
            grading_info={},
            reward=0.0,
            done=False,
            metadata={"message": "Incident detected. Analyze and respond.", "scenario": self._scenario.scenario_name},
        )

    def step(self, action: IncidentAction, timeout_s=None, **kwargs) -> IncidentObservation:
        """Grade agent's incident response and return feedback."""
        if self._scenario is None:
            raise RuntimeError("Call reset() before step()")

        self._state.step_count += 1
        self._state.attempts += 1

        # Build action dict for grading
        action_dict = {
            "severity": action.severity,
            "root_cause_service": action.root_cause_service,
            "root_cause_category": action.root_cause_category,
            "root_cause_description": action.root_cause_description,
            "remediation": action.remediation,
            "affected_services": action.affected_services,
        }

        score, grading_info = grade_action(action_dict, self._scenario, self._state.step_count)

        if score > self._state.best_score:
            self._state.best_score = score

        done = score >= 0.90 or self._state.step_count >= MAX_STEPS

        # Build feedback
        feedback_parts = []
        if grading_info.get("root_cause_service", "").startswith("wrong"):
            feedback_parts.append(f"Incorrect root cause service. You said '{action.root_cause_service}'.")
        if grading_info.get("severity", "").startswith("wrong"):
            feedback_parts.append(f"Severity assessment incorrect.")
        if grading_info.get("remediation", "").startswith("wrong"):
            feedback_parts.append(f"Remediation '{action.remediation}' is not appropriate.")
        if "missing" in str(grading_info.get("affected_services_detail", "")):
            feedback_parts.append("You missed some affected services.")
        if not feedback_parts and score < 0.90:
            feedback_parts.append("Partially correct. Improve your analysis.")
        if score >= 0.90:
            feedback_parts.append("Excellent diagnosis! All key elements correct.")
        feedback = " ".join(feedback_parts) if feedback_parts else None

        # Progressive hint (on step 2+)
        hint = None
        if self._state.step_count >= 2 and not done:
            hint_idx = min(self._state.step_count - 2, len(self._scenario.hints) - 1)
            hint = self._scenario.hints[hint_idx]
            self._state.hint_level = hint_idx + 1

        return IncidentObservation(
            task_id=self._state.current_task_id,
            task_description=get_task_description(self._state.current_task_id),
            incident_summary=self._scenario.incident_summary,
            service_topology=self._scenario.service_topology,
            log_entries=self._scenario.log_entries,
            metrics_snapshot=self._scenario.metrics_snapshot,
            timeline=self._scenario.timeline,
            feedback=feedback,
            hint=hint,
            grading_info=grading_info,
            reward=score,
            done=done,
            metadata={
                "step": self._state.step_count,
                "best_score": self._state.best_score,
                "scenario": self._scenario.scenario_name,
            },
        )

    @property
    def state(self) -> IncidentState:
        return self._state
