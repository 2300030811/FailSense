"""
Data models for the Incident Response Environment.
Actions, Observations, and State for production incident triage.

The agent acts as an on-call SRE who must:
1. Assess severity
2. Identify the root-cause service
3. Categorize the failure mode
4. Recommend remediation
5. List all affected services
"""

from typing import List, Optional

from pydantic import Field
from openenv.core.env_server.types import Action, Observation, State as BaseState


class IncidentAction(Action):
    """Agent's incident response submission.

    Each step, the agent submits a structured diagnosis and remediation plan.
    All fields are required and scored independently by the grader.
    """

    severity: str = Field(
        ...,
        description=(
            "Incident severity level. One of: "
            "P1_critical | P2_high | P3_medium | P4_low"
        ),
    )
    root_cause_service: str = Field(
        ...,
        description="Name of the service that is the PRIMARY root cause (e.g. 'user-db')",
    )
    root_cause_category: str = Field(
        ...,
        description=(
            "Failure category. One of: "
            "config_error | memory_leak | resource_exhaustion | "
            "network_failure | dependency_failure | code_bug | "
            "deployment_regression | data_corruption"
        ),
    )
    root_cause_description: str = Field(
        ...,
        description="Free-text explanation of what went wrong and why",
    )
    remediation: str = Field(
        ...,
        description=(
            "Recommended fix action. One of: "
            "restart_service | rollback_deployment | scale_horizontally | "
            "fix_config | increase_resources | enable_circuit_breaker | "
            "failover | clear_cache | repair_data"
        ),
    )
    affected_services: str = Field(
        ...,
        description="Comma-separated list of ALL affected services including downstream (e.g. 'api-gateway,user-service,user-db')",
    )


class IncidentObservation(Observation):
    """Observation returned after reset() or step().

    Contains everything an SRE would see when paged:
    alert summary, service topology, logs, metrics, and timeline.
    After step 1, also includes feedback and progressive hints.
    """

    task_id: str = Field(default="", description="Current task: single_service_failure | cascading_failure | performance_degradation")
    task_description: str = Field(default="", description="High-level task instructions")
    incident_summary: str = Field(default="", description="PagerDuty-style alert that triggered the page")
    service_topology: str = Field(default="", description="ASCII diagram of service dependencies")
    log_entries: str = Field(default="", description="Structured log entries from all services, chronologically ordered")
    metrics_snapshot: str = Field(default="", description="Service health metrics table (CPU, memory, latency, error rate)")
    timeline: str = Field(default="", description="Chronological summary of key events")
    feedback: Optional[str] = Field(default=None, description="Feedback on agent's previous diagnosis attempt")
    hint: Optional[str] = Field(default=None, description="Progressive hint (revealed on step 2+)")
    grading_info: dict = Field(default_factory=dict, description="Detailed score breakdown")


class IncidentState(BaseState):
    """Internal episode state — extends BaseState (has episode_id + step_count)."""

    current_task_id: str = Field(default="single_service_failure")
    best_score: float = Field(default=0.0)
    scenario_seed: int = Field(default=42)
    hint_level: int = Field(default=0)
    attempts: int = Field(default=0)
