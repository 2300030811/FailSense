# SQL Debug Env — Complete Build Guide for Copilot
# Based on actual openenv-core API (verified by inspecting the library)
# Meta PyTorch OpenEnv Hackathon

---

## STEP 0 — BEFORE WRITING ANY CODE (DO THIS FIRST)

Run this command in your terminal to generate the official scaffold:

```bash
pip install openenv-core uv --break-system-packages
openenv init sql_debug_env
cd sql_debug_env
```

This creates 17 files. You will REPLACE some of them. Do not delete the ones
you are not replacing — especially Dockerfile, openenv.yaml, pyproject.toml,
server/__init__.py, uv.lock.

---

## WHAT YOU ARE BUILDING

An environment where an AI agent solves 3 SQL tasks:
- Task 1 (easy): Fix a broken SQL query that has typos
- Task 2 (medium): Write a 3-table JOIN query from a description
- Task 3 (hard): Optimize a slow query to use an index

The agent submits SQL. The server executes it against SQLite and scores it.

---

## FILES TO REPLACE/CREATE

After running `openenv init`, replace or create these files exactly:

---

## FILE 1: models.py  (REPLACE the generated one)

```python
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
    """Internal episode state — extends BaseState which has episode_id + step_count."""
    current_task_id: str = Field(default="fix_query")
    best_score: float = Field(default=0.0)
```

---

## FILE 2: server/task_registry.py  (CREATE this new file)

```python
"""
Task definitions for the SQL Debug environment.
Each task has DDL, seed data, a broken/reference query, and reference results.
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class Task:
    task_id: str
    difficulty: str
    description: str
    ddl: str
    seed_sql: str
    reference_query: str
    reference_result: List[Any]
    broken_query: Optional[str] = None
    explain_plan: Optional[str] = None


TASK_1 = Task(
    task_id="fix_query",
    difficulty="easy",
    description=(
        "Fix the broken SQL query below. It has exactly 2 bugs: wrong column names.\n"
        "The correct query should find the name and email of all customers from 'Mumbai', "
        "ordered by name ascending.\n\n"
        "Table: customers(id INTEGER, name TEXT, email TEXT, city TEXT, age INTEGER)"
    ),
    ddl="""CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL,
    age INTEGER NOT NULL
);""",
    seed_sql="""INSERT INTO customers VALUES
(1, 'Aarav Shah', 'aarav@example.com', 'Mumbai', 28),
(2, 'Priya Patel', 'priya@example.com', 'Delhi', 34),
(3, 'Rohan Mehta', 'rohan@example.com', 'Mumbai', 22),
(4, 'Neha Singh', 'neha@example.com', 'Bangalore', 29),
(5, 'Amit Kumar', 'amit@example.com', 'Mumbai', 41),
(6, 'Divya Nair', 'divya@example.com', 'Chennai', 31);""",
    broken_query="SELECT nme, emal FROM customers WHERE city = 'Mumbai' ORDER BY name ASC;",
    reference_query="SELECT name, email FROM customers WHERE city = 'Mumbai' ORDER BY name ASC;",
    reference_result=[
        ("Aarav Shah", "aarav@example.com"),
        ("Amit Kumar", "amit@example.com"),
        ("Rohan Mehta", "rohan@example.com"),
    ],
)


TASK_2 = Task(
    task_id="write_join",
    difficulty="medium",
    description=(
        "Write a SQL query from scratch using the schema below.\n\n"
        "Tables:\n"
        "  customers(id, name, email, city)\n"
        "  products(id, name, price, category)\n"
        "  orders(id, customer_id, product_id, quantity, order_date)\n\n"
        "Task: Find each customer's name and their total amount spent "
        "(quantity * price). Only include customers who spent MORE than 500 total. "
        "Order by total_spent descending.\n"
        "Return exactly these columns: customer_name, total_spent"
    ),
    ddl="""CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    category TEXT NOT NULL
);
CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    order_date TEXT NOT NULL
);""",
    seed_sql="""INSERT INTO customers VALUES
(1, 'Aarav Shah', 'aarav@example.com', 'Mumbai'),
(2, 'Priya Patel', 'priya@example.com', 'Delhi'),
(3, 'Rohan Mehta', 'rohan@example.com', 'Mumbai'),
(4, 'Neha Singh', 'neha@example.com', 'Bangalore');
INSERT INTO products VALUES
(1, 'Laptop', 800.0, 'Electronics'),
(2, 'Phone', 300.0, 'Electronics'),
(3, 'Desk', 200.0, 'Furniture'),
(4, 'Chair', 150.0, 'Furniture');
INSERT INTO orders VALUES
(1, 1, 1, 1, '2024-01-15'),
(2, 1, 2, 2, '2024-01-16'),
(3, 2, 3, 3, '2024-02-01'),
(4, 2, 4, 1, '2024-02-03'),
(5, 3, 2, 1, '2024-02-10'),
(6, 4, 1, 2, '2024-03-01'),
(7, 4, 4, 3, '2024-03-05');""",
    reference_query="""SELECT c.name AS customer_name, SUM(o.quantity * p.price) AS total_spent
FROM orders o
JOIN customers c ON o.customer_id = c.id
JOIN products p ON o.product_id = p.id
GROUP BY c.id, c.name
HAVING SUM(o.quantity * p.price) > 500
ORDER BY total_spent DESC;""",
    reference_result=[
        ("Neha Singh", 2050.0),
        ("Aarav Shah", 1400.0),
        ("Priya Patel", 750.0),
    ],
)


TASK_3 = Task(
    task_id="optimize_query",
    difficulty="hard",
    description=(
        "The query below is slow — it does a FULL TABLE SCAN on the events table (50k rows).\n"
        "An index exists on (event_type, created_at). Rewrite the query so it uses this index.\n\n"
        "Table: events(id, user_id, event_type, created_at, payload)\n"
        "Index: idx_events_type_date ON events(event_type, created_at)\n\n"
        "Task: Return user_id and count of 'purchase' events for users with more than 3 "
        "purchase events in the last 30 days. Order by purchase_count descending.\n"
        "Return columns: user_id, purchase_count\n\n"
        "REQUIREMENT: Your query's EXPLAIN QUERY PLAN must NOT say 'SCAN TABLE events'.\n"
        "HINT: Put your WHERE clause BEFORE GROUP BY and make sure event_type filter is present."
    ),
    ddl="""CREATE TABLE events (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    payload TEXT
);
CREATE INDEX idx_events_type_date ON events(event_type, created_at);
CREATE INDEX idx_events_user ON events(user_id);""",
    seed_sql="",  # seeded programmatically in environment.py
    broken_query="""SELECT user_id, COUNT(*) as purchase_count
FROM events
GROUP BY user_id
HAVING SUM(CASE WHEN event_type = 'purchase' AND created_at >= date('now', '-30 days') THEN 1 ELSE 0 END) > 3
ORDER BY purchase_count DESC;""",
    explain_plan="SCAN TABLE events  (this is the problem — fix it)",
    reference_query="""SELECT user_id, COUNT(*) as purchase_count
FROM events
WHERE event_type = 'purchase'
  AND created_at >= date('now', '-30 days')
GROUP BY user_id
HAVING COUNT(*) > 3
ORDER BY purchase_count DESC;""",
    reference_result=[],  # computed live from DB
)


TASKS = {t.task_id: t for t in [TASK_1, TASK_2, TASK_3]}
```

---

## FILE 3: server/graders.py  (CREATE this new file)

```python
"""
Grading functions for the 3 SQL tasks.
All functions are pure and deterministic: same SQL in = same score out.
Returns (score: float, info: dict) where score is in [0.0, 1.0].
"""

import sqlite3
from typing import Any, Dict, List, Tuple


def _run_sql(conn: sqlite3.Connection, sql: str) -> Tuple[bool, List[Any], str]:
    """Execute SQL safely. Returns (success, rows, error_message)."""
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return True, cur.fetchall(), ""
    except Exception as e:
        return False, [], str(e)


def grade_task1(sql: str, conn: sqlite3.Connection, task) -> Tuple[float, Dict]:
    """
    Fix the query task.
    +0.20 — SQL contains SELECT keyword (basic structure)
    +0.30 — SQL executes without error
    +0.50 — rows exactly match reference (order matters)
    """
    score, info = 0.0, {}

    if not sql or not sql.strip():
        return 0.0, {"error": "empty SQL"}

    if "SELECT" in sql.upper():
        score += 0.20
        info["has_select"] = True

    ok, rows, err = _run_sql(conn, sql)
    if not ok:
        info["execution_error"] = err
        return round(score, 4), info

    score += 0.30
    info["execution"] = "success"

    agent = [tuple(str(v) for v in r) for r in rows]
    ref = [tuple(str(v) for v in r) for r in task.reference_result]

    if agent == ref:
        score += 0.50
        info["match"] = "exact"
    elif sorted(agent) == sorted(ref):
        score += 0.25
        info["match"] = "unordered"
    else:
        info["match"] = "wrong"
        info["expected"] = ref
        info["got"] = agent[:5]  # show first 5 rows only

    return round(min(score, 1.0), 4), info


def grade_task2(sql: str, conn: sqlite3.Connection, task) -> Tuple[float, Dict]:
    """
    Write join query task.
    +0.10 — contains JOIN
    +0.10 — contains GROUP BY
    +0.10 — executes without error
    +0.20 — returns columns named customer_name and total_spent
    +0.20 — correct number of rows
    +0.30 — exact data match (order-sensitive, floats rounded to 2dp)
    """
    score, info = 0.0, {}

    if not sql or not sql.strip():
        return 0.0, {"error": "empty SQL"}

    u = sql.upper()
    if "JOIN" in u:
        score += 0.10
        info["has_join"] = True
    if "GROUP BY" in u:
        score += 0.10
        info["has_group_by"] = True

    ok, _, err = _run_sql(conn, sql)
    if not ok:
        info["execution_error"] = err
        return round(score, 4), info

    score += 0.10
    info["execution"] = "success"

    # Re-run to get column names
    cur = conn.cursor()
    cur.execute(sql)
    col_names = [d[0].lower() for d in cur.description]
    rows = cur.fetchall()

    if "customer_name" in col_names and "total_spent" in col_names:
        score += 0.20
        info["columns"] = "correct"
    else:
        info["columns"] = f"got {col_names}"
        return round(score, 4), info

    ref = task.reference_result
    if len(rows) == len(ref):
        score += 0.20
        info["row_count"] = "correct"
    else:
        info["row_count"] = f"got {len(rows)}, expected {len(ref)}"
        return round(score, 4), info

    def norm(row):
        return tuple(round(v, 2) if isinstance(v, float) else v for v in row)

    if [norm(r) for r in rows] == [norm(r) for r in ref]:
        score += 0.30
        info["match"] = "exact"
    elif sorted([str(norm(r)) for r in rows]) == sorted([str(norm(r)) for r in ref]):
        score += 0.15
        info["match"] = "unordered"
    else:
        info["match"] = "wrong"
        info["expected"] = [norm(r) for r in ref]
        info["got"] = [norm(r) for r in rows]

    return round(min(score, 1.0), 4), info


def grade_task3(sql: str, conn: sqlite3.Connection, task) -> Tuple[float, Dict]:
    """
    Optimize query task.
    +0.10 — SQL contains SELECT
    +0.15 — executes without error
    +0.35 — result matches reference query output
    +0.40 — EXPLAIN QUERY PLAN does not say 'SCAN TABLE EVENTS'
    """
    score, info = 0.0, {}

    if not sql or not sql.strip():
        return 0.0, {"error": "empty SQL"}

    if "SELECT" in sql.upper():
        score += 0.10

    ok, rows, err = _run_sql(conn, sql)
    if not ok:
        info["execution_error"] = err
        return round(score, 4), info

    score += 0.15
    info["execution"] = "success"
    info["rows_returned"] = len(rows)

    # Compare to reference
    ok2, ref_rows, _ = _run_sql(conn, task.reference_query)
    if ok2:
        agent_s = [tuple(str(v) for v in r) for r in rows]
        ref_s = [tuple(str(v) for v in r) for r in ref_rows]
        if agent_s == ref_s:
            score += 0.35
            info["match"] = "exact"
        elif sorted(agent_s) == sorted(ref_s):
            score += 0.18
            info["match"] = "unordered"
        else:
            info["match"] = "wrong"

    # Check EXPLAIN QUERY PLAN
    try:
        cur = conn.cursor()
        cur.execute(f"EXPLAIN QUERY PLAN {sql}")
        plan = " ".join(str(r) for r in cur.fetchall()).upper()
        info["explain"] = plan[:200]
        if "SCAN TABLE EVENTS" not in plan:
            score += 0.40
            info["optimization"] = "PASSED — no full table scan"
        else:
            info["optimization"] = "FAILED — still scanning full table"
    except Exception as e:
        info["explain_error"] = str(e)

    return round(min(score, 1.0), 4), info


GRADER_MAP = {
    "fix_query": grade_task1,
    "write_join": grade_task2,
    "optimize_query": grade_task3,
}
```

---

## FILE 4: server/sql_debug_env_environment.py  (REPLACE the generated one)

```python
"""
SQL Debug Environment server implementation.
Handles 3 SQL tasks with in-memory SQLite databases.
"""

import random
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from ..models import SqlDebugAction, SqlDebugObservation, SqlDebugState
    from .task_registry import TASKS, Task
    from .graders import GRADER_MAP
except ImportError:
    from models import SqlDebugAction, SqlDebugObservation, SqlDebugState
    from server.task_registry import TASKS, Task
    from server.graders import GRADER_MAP

MAX_STEPS = 5


class SqlDebugEnvironment(Environment):
    """
    SQL debugging environment backed by in-memory SQLite.
    One fresh DB per episode. Agent submits SQL, gets scored reward.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = SqlDebugState(episode_id=str(uuid.uuid4()))
        self._conn: Optional[sqlite3.Connection] = None
        self._current_task: Optional[Task] = None

    def reset(self, seed=None, episode_id=None, task_id: str = "fix_query", **kwargs) -> SqlDebugObservation:
        """Start a new episode. task_id chooses which of the 3 tasks to run."""
        if task_id not in TASKS:
            task_id = "fix_query"

        task = TASKS[task_id]
        self._current_task = task

        # Fresh in-memory SQLite DB for every episode
        if self._conn:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = sqlite3.connect(":memory:")

        # Create tables
        for stmt in task.ddl.strip().split(";"):
            s = stmt.strip()
            if s:
                self._conn.execute(s)
        self._conn.commit()

        # Seed data
        if task.task_id == "optimize_query":
            self._seed_events(self._conn)
        else:
            for stmt in task.seed_sql.strip().split(";"):
                s = stmt.strip()
                if s:
                    self._conn.execute(s)
            self._conn.commit()

        self._state = SqlDebugState(
            episode_id=episode_id or str(uuid.uuid4()),
            step_count=0,
            current_task_id=task_id,
            best_score=0.0,
        )

        return SqlDebugObservation(
            task_id=task_id,
            task_description=task.description,
            schema_info=task.ddl.strip(),
            broken_query=task.broken_query,
            explain_plan=task.explain_plan,
            reward=0.0,
            done=False,
            metadata={"message": "Episode started. Submit your SQL."},
        )

    def step(self, action: SqlDebugAction, timeout_s=None, **kwargs) -> SqlDebugObservation:
        """Execute agent's SQL, grade it, return observation with reward."""
        if self._conn is None or self._current_task is None:
            raise RuntimeError("Call reset() before step()")

        self._state.step_count += 1
        task = self._current_task
        grader = GRADER_MAP[task.task_id]

        score, grading_info = grader(action.sql_query, self._conn, task)

        # Step penalty: -0.05 per step beyond the first
        if self._state.step_count > 1:
            penalty = round(0.05 * (self._state.step_count - 1), 4)
            score = round(max(0.0, score - penalty), 4)
            grading_info["step_penalty"] = penalty

        if score > self._state.best_score:
            self._state.best_score = score

        done = score >= 0.95 or self._state.step_count >= MAX_STEPS

        # Get query result for observation
        query_result = None
        error_message = None
        try:
            cur = self._conn.cursor()
            cur.execute(action.sql_query)
            query_result = [list(r) for r in cur.fetchall()]
        except Exception as e:
            error_message = str(e)

        return SqlDebugObservation(
            task_id=task.task_id,
            task_description=task.description,
            schema_info=task.ddl.strip(),
            broken_query=task.broken_query,
            explain_plan=task.explain_plan,
            query_result=query_result,
            error_message=error_message,
            grading_info=grading_info,
            reward=score,
            done=done,
            metadata={"step": self._state.step_count, "best_score": self._state.best_score},
        )

    @property
    def state(self) -> SqlDebugState:
        return self._state

    def _seed_events(self, conn: sqlite3.Connection):
        """Generate 500 event rows with fixed seed for reproducibility."""
        rng = random.Random(42)
        event_types = ["purchase", "view", "click", "login", "logout"]
        base = datetime(2024, 3, 1)
        rows = [
            (
                i,
                rng.randint(1, 30),
                rng.choices(event_types, weights=[20, 40, 25, 10, 5])[0],
                (base - timedelta(days=rng.randint(0, 45))).strftime("%Y-%m-%d"),
                None,
            )
            for i in range(1, 501)
        ]
        conn.executemany("INSERT INTO events VALUES (?,?,?,?,?)", rows)
        conn.commit()
```

---

## FILE 5: client.py  (REPLACE the generated one)

```python
"""
Client for SQL Debug Env — connects to the server via WebSocket.
Inherits from OpenEnv EnvClient which provides from_docker_image(), reset(), step(), close().
"""

from typing import Dict, Any

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
```

---

## FILE 6: server/app.py  (REPLACE the generated one)

```python
"""FastAPI application for SQL Debug Env."""

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:
    raise ImportError("openenv-core is required") from e

try:
    from ..models import SqlDebugAction, SqlDebugObservation
    from .sql_debug_env_environment import SqlDebugEnvironment
except ModuleNotFoundError:
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


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    main(port=args.port)
```

---

## FILE 7: __init__.py  (REPLACE the generated one)

```python
"""SQL Debug Env — OpenEnv environment for SQL task solving."""

from .client import SqlDebugEnv
from .models import SqlDebugAction, SqlDebugObservation, SqlDebugState

__all__ = [
    "SqlDebugAction",
    "SqlDebugObservation",
    "SqlDebugState",
    "SqlDebugEnv",
]
```

---

## FILE 8: pyproject.toml  (REPLACE with this — adds openai and requests)

```toml
[build-system]
requires = ["setuptools>=45", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "openenv-sql_debug_env"
version = "0.1.0"
description = "SQL Debug Env — OpenEnv environment for SQL debugging tasks"
requires-python = ">=3.10"
dependencies = [
    "openenv-core[core]>=0.2.2",
    "openai>=1.0.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
]

[project.scripts]
server = "sql_debug_env.server.app:main"

[tool.setuptools]
include-package-data = true
packages = ["sql_debug_env", "sql_debug_env.server"]
package-dir = { "sql_debug_env" = ".", "sql_debug_env.server" = "server" }
```

---

## FILE 9: inference.py  (CREATE at project root — MANDATORY filename)

CRITICAL RULES FOR THIS FILE:
- Must be named exactly `inference.py` at the root of the project
- Must use OpenAI client (not direct API calls)
- Must print EXACTLY the [START] [STEP] [END] lines — judges parse these automatically
- Must be async
- Must complete all 3 tasks in under 20 minutes
- score field in [END] must be normalized to [0.0, 1.0]

```python
"""
inference.py — Baseline inference script for SQL Debug Env
Mandatory stdout format: [START], [STEP], [END] lines per the hackathon spec.
"""

import asyncio
import os
import re
import textwrap
from typing import List, Optional

from openai import OpenAI

# Import env client from the package
try:
    from sql_debug_env import SqlDebugEnv, SqlDebugAction
except ImportError:
    # fallback for running from inside the package directory
    from __init__ import SqlDebugEnv  # type: ignore
    from models import SqlDebugAction  # type: ignore

# ── Mandatory env vars ───────────────────────────────────────────────────────
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY: str = os.getenv("HF_TOKEN") or os.getenv("API_KEY", "")
MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-Coder-32B-Instruct")
LOCAL_IMAGE_NAME: str = os.getenv("LOCAL_IMAGE_NAME", "sql_debug_env:latest")

# ── Episode config ───────────────────────────────────────────────────────────
BENCHMARK = "sql_debug_env"
MAX_STEPS = 5
TEMPERATURE = 0.1
MAX_TOKENS = 512
SUCCESS_THRESHOLD = 0.5  # score >= this = success
TASK_IDS = ["fix_query", "write_join", "optimize_query"]


# ── Mandatory stdout log functions ───────────────────────────────────────────
def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    # action must be a single line, no newlines
    action_clean = action.replace("\n", " ").replace("\r", " ")[:200]
    error_val = error.replace("\n", " ")[:100] if error else "null"
    print(
        f"[STEP] step={step} action={action_clean} "
        f"reward={reward:.2f} done={str(done).lower()} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.2f} rewards={rewards_str}",
        flush=True,
    )


# ── SQL extractor ────────────────────────────────────────────────────────────
def extract_sql(text: str) -> str:
    """Extract SQL from model response. Looks for ```sql blocks first."""
    m = re.search(r"```sql\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"```\s*(SELECT.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    m = re.search(r"(SELECT\s+.+?;)", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return text.strip()


# ── Prompts ──────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert SQL developer. You write correct, efficient SQLite queries.

    Rules:
    1. Output your SQL inside a ```sql code block — nothing else outside it.
    2. Use only SQLite-compatible syntax.
    3. If fixing a broken query, find ALL bugs and fix them in one shot.
    4. If writing from scratch, read the schema carefully first.
    5. Do not write explanations outside the code block.

    Example correct output:
    ```sql
    SELECT name, email FROM customers WHERE city = 'Mumbai' ORDER BY name ASC;
    ```
""").strip()


def build_prompt(obs_data: dict, step: int, prev_error: str = "") -> str:
    parts = [
        f"Step {step}/{MAX_STEPS}",
        f"\nTask:\n{obs_data.get('task_description', '')}",
        f"\nSchema:\n{obs_data.get('schema_info', '')}",
    ]
    if obs_data.get("broken_query"):
        parts.append(f"\nBroken query to fix or optimize:\n{obs_data['broken_query']}")
    if obs_data.get("explain_plan"):
        parts.append(f"\nEXPLAIN QUERY PLAN (shows the problem):\n{obs_data['explain_plan']}")
    if prev_error:
        parts.append(f"\nYour previous query caused this error: {prev_error}")
        parts.append("Fix it and try again.")
    parts.append("\nWrite the correct SQL query now:")
    return "\n".join(parts)


# ── LLM call ─────────────────────────────────────────────────────────────────
def call_llm(client: OpenAI, prompt: str) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        print(f"[DEBUG] LLM call failed: {e}", flush=True)
        return ""


# ── Run one task episode ─────────────────────────────────────────────────────
async def run_task(env: SqlDebugEnv, client: OpenAI, task_id: str) -> float:
    """Run one full episode for a task. Returns final score in [0, 1]."""
    rewards: List[float] = []
    steps_taken = 0
    best_score = 0.0
    success = False
    prev_error = ""

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task_id)
        obs = result.observation

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            obs_dict = {
                "task_description": obs.task_description,
                "schema_info": obs.schema_info,
                "broken_query": obs.broken_query,
                "explain_plan": obs.explain_plan,
            }
            prompt = build_prompt(obs_dict, step, prev_error)
            response = call_llm(client, prompt)
            sql = extract_sql(response) or "SELECT 1;"

            result = await env.step(SqlDebugAction(sql_query=sql))
            obs = result.observation
            reward = result.reward or 0.0
            done = result.done
            error = obs.error_message

            rewards.append(reward)
            steps_taken = step
            prev_error = error or ""

            if reward > best_score:
                best_score = reward

            log_step(step=step, action=sql, reward=reward, done=done, error=error)

            if done:
                break

        score = round(best_score, 2)
        success = score >= SUCCESS_THRESHOLD

    except Exception as e:
        print(f"[DEBUG] Task {task_id} crashed: {e}", flush=True)
        score = 0.0

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


# ── Main: run all 3 tasks ────────────────────────────────────────────────────
async def main() -> None:
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    all_scores = {}

    for task_id in TASK_IDS:
        # Each task gets a fresh env connection (fresh Docker container state)
        env = await SqlDebugEnv.from_docker_image(LOCAL_IMAGE_NAME)
        try:
            score = await run_task(env, client, task_id)
            all_scores[task_id] = score
        finally:
            await env.close()

    print("\n[SUMMARY]", flush=True)
    for tid, sc in all_scores.items():
        print(f"  {tid}: {sc:.2f}", flush=True)
    avg = sum(all_scores.values()) / len(all_scores)
    print(f"  average: {avg:.2f}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
```

---

## FILE 10: openenv.yaml  (KEEP the generated one — it's already correct)

The generated file looks like this — do NOT change it:
```yaml
spec_version: 1
name: sql_debug_env
type: space
runtime: fastapi
app: server.app:app
port: 8000
```

---

## FILE 11: server/Dockerfile  (KEEP the generated one — it's already correct)

The generated Dockerfile uses `ghcr.io/meta-pytorch/openenv-base:latest` and `uv sync`.
Do NOT replace it with a custom Python slim Dockerfile.

---

## STEP-BY-STEP BUILD SEQUENCE FOR COPILOT

### Step 1 — Scaffold (run in terminal, not Copilot)
```bash
pip install openenv-core uv --break-system-packages
openenv init sql_debug_env
cd sql_debug_env
```

### Step 2 — Tell Copilot to create files in this exact order:

Paste to Copilot Chat one at a time:

1. "Replace models.py with the content from FILE 1 in my spec. Do not change field names."
2. "Create server/task_registry.py with the content from FILE 2. Do not simplify or shorten the seed data."
3. "Create server/graders.py with the content from FILE 3. The scoring logic must match exactly."
4. "Replace server/sql_debug_env_environment.py with FILE 4. Keep the try/except import block."
5. "Replace client.py with FILE 5. The _parse_result method must match the field names in models.py."
6. "Replace server/app.py with FILE 6."
7. "Replace __init__.py with FILE 7."
8. "Replace pyproject.toml with FILE 8."
9. "Create inference.py at the project root with FILE 9. This file must be named exactly inference.py."

### Step 3 — Install and test locally (terminal)
```bash
uv sync
# Test the server starts
uvicorn server.app:app --port 8000 &
sleep 3
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task_id":"fix_query"}'
# Kill test server
kill %1
```

### Step 4 — Build Docker (terminal)
```bash
docker build -t sql_debug_env:latest .
docker run -d -p 8000:8000 --name sql_test sql_debug_env:latest
sleep 5
curl -X POST http://localhost:8000/reset -H "Content-Type: application/json" -d '{"task_id":"fix_query"}'
docker stop sql_test && docker rm sql_test
```

### Step 5 — Run inference.py (terminal)
```bash
docker run -d -p 8000:8000 --name sql_env sql_debug_env:latest
sleep 5
export API_BASE_URL="https://router.huggingface.co/v1"
export HF_TOKEN="your_actual_token_here"
export MODEL_NAME="Qwen/Qwen2.5-Coder-32B-Instruct"
export LOCAL_IMAGE_NAME="sql_debug_env:latest"
python inference.py
docker stop sql_env && docker rm sql_env
```

You should see [START], [STEP], [END] lines printed. Check that scores are numbers between 0 and 1.

### Step 6 — Deploy to Hugging Face (terminal)
```bash
openenv push --repo-id YOUR_HF_USERNAME/sql-debug-env
```

### Step 7 — Run the validator (terminal)
```bash
curl -fsSL https://raw.githubusercontent.com/meta-pytorch/OpenEnv/main/scripts/validate-submission.sh \
  -o validate.sh && chmod +x validate.sh
./validate.sh https://YOUR_HF_USERNAME-sql-debug-env.hf.space .
```

All 3 checks must say PASSED.

---

## THINGS COPILOT MUST NOT DO

1. Do NOT change the class name `SqlDebugEnv` — inference.py imports it by this name
2. Do NOT change field names in models.py — client.py reads them by exact name in _parse_result
3. Do NOT replace the Dockerfile — the generated one is correct
4. Do NOT change openenv.yaml — the generated one is correct
5. Do NOT make the environment sync — inference.py uses await
6. Do NOT remove the try/except import blocks — they handle both local and Docker module paths
7. Do NOT add print statements inside graders — they must be pure functions
8. Do NOT change the [START][STEP][END] format in inference.py — judges parse these automatically
9. Do NOT use `pip install` inside the Dockerfile — it uses `uv sync` from pyproject.toml
10. Do NOT import sqlite3 anywhere except graders.py and environment.py

---

## QUICK SANITY CHECK

After building, paste this to Copilot:
"Write a file called test_local.py that:
1. Imports SqlDebugEnvironment from server.sql_debug_env_environment
2. Creates an instance: env = SqlDebugEnvironment()
3. Calls obs = env.reset(task_id='fix_query') and prints obs.task_id
4. Calls obs = env.step(SqlDebugAction(sql_query='SELECT name, email FROM customers WHERE city = \"Mumbai\" ORDER BY name ASC')) and prints obs.reward
5. Asserts obs.reward >= 0.8 or prints GRADER FAILED
6. Does the same for task_id='write_join' with a wrong query and asserts reward < 0.5
7. Prints PASS or FAIL at the end"
