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
    +0.20 - SQL contains SELECT keyword (basic structure)
    +0.30 - SQL executes without error
    +0.50 - rows exactly match reference (order matters)
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
    +0.10 - contains JOIN
    +0.10 - contains GROUP BY
    +0.10 - executes without error
    +0.20 - returns columns named customer_name and total_spent
    +0.20 - correct number of rows
    +0.30 - exact data match (order-sensitive, floats rounded to 2dp)
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
    +0.10 - SQL contains SELECT
    +0.15 - executes without error
    +0.35 - result matches reference query output
    +0.40 - EXPLAIN QUERY PLAN does not say 'SCAN TABLE EVENTS'
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
            info["optimization"] = "PASSED - no full table scan"
        else:
            info["optimization"] = "FAILED - still scanning full table"
    except Exception as e:
        info["explain_error"] = str(e)

    return round(min(score, 1.0), 4), info


GRADER_MAP = {
    "fix_query": grade_task1,
    "write_join": grade_task2,
    "optimize_query": grade_task3,
}
