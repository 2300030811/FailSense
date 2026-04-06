"""Quick local sanity checks for SQL Debug Env."""

try:
    from sql_debug_env.models import SqlDebugAction
    from sql_debug_env.server.sql_debug_env_environment import SqlDebugEnvironment
except ImportError:
    from models import SqlDebugAction
    from server.sql_debug_env_environment import SqlDebugEnvironment


def run() -> int:
    env = SqlDebugEnvironment()
    passed = True

    # Task 1: correct query should score high
    obs = env.reset(task_id="fix_query")
    print("task1_reset:", obs.task_id)
    obs = env.step(
        SqlDebugAction(
            sql_query='SELECT name, email FROM customers WHERE city = "Mumbai" ORDER BY name ASC;'
        )
    )
    print("task1_reward:", obs.reward)
    if not (obs.reward is not None and obs.reward >= 0.8):
        print("GRADER FAILED: fix_query reward too low")
        passed = False

    # Task 2: wrong query should score low
    obs = env.reset(task_id="write_join")
    print("task2_reset:", obs.task_id)
    obs = env.step(SqlDebugAction(sql_query="SELECT 1;"))
    print("task2_reward:", obs.reward)
    if not (obs.reward is not None and obs.reward < 0.5):
        print("GRADER FAILED: write_join wrong query reward too high")
        passed = False

    if passed:
        print("PASS")
        return 0

    print("FAIL")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
