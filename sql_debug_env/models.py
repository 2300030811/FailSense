"""
Data models for the SQL Debug Env Environment.
Actions, Observations, and State for SQL task solving.
"""

from typing import Any, List, Optional

from pydantic import Field
from openenv.core.env_server.types import Action, Observation, State as BaseState


class SqlDebugAction(Action):
    """Action: submit a SQL query string."""

    sql_query: str = Field(..., description="The SQL query to execute and grade")


class SqlDebugObservation(Observation):
    """Observation returned after reset() or step()."""

    task_id: str = Field(default="", description="Current task: fix_query | write_join | optimize_query")
    task_description: str = Field(default="", description="Full natural language task description")
    schema_info: str = Field(default="", description="CREATE TABLE DDL for all tables in the DB")
    broken_query: Optional[str] = Field(default=None, description="Provided for task1 and task3")
    explain_plan: Optional[str] = Field(default=None, description="EXPLAIN QUERY PLAN output for task3")
    query_result: Optional[List[Any]] = Field(default=None, description="Rows returned by agent's last SQL")
    error_message: Optional[str] = Field(default=None, description="SQL execution error if any")
    grading_info: dict = Field(default_factory=dict, description="Breakdown of how score was calculated")


class SqlDebugState(BaseState):
    """Internal episode state - extends BaseState which has episode_id + step_count."""

    current_task_id: str = Field(default="fix_query")
    best_score: float = Field(default=0.0)
