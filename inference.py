"""
inference.py — Baseline inference script for IncidentEnv
Mandatory stdout format: [START], [STEP], [END] lines per the hackathon spec.

Uses OpenAI Client for all LLM calls.
Runs all 3 tasks: single_service_failure, cascading_failure, performance_degradation.
"""

import asyncio
import json
import os
import re
import sys
import textwrap
from typing import Dict, List, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from dotenv import load_dotenv
from openai import OpenAI

from incident_env import IncidentAction, IncidentEnv

load_dotenv()

API_BASE_URL: str = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY: str = os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY") or ""
MODEL_NAME: str = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")
LOCAL_IMAGE_NAME: str = os.getenv("LOCAL_IMAGE_NAME", "incident_env:latest")
IMAGE_NAME: str = os.getenv("IMAGE_NAME", LOCAL_IMAGE_NAME)

BENCHMARK = "incident_env"
MAX_STEPS = 5
TEMPERATURE = 0.15
MAX_TOKENS = 1200
SUCCESS_THRESHOLD = 0.5
TASK_IDS = ["single_service_failure", "cascading_failure", "performance_degradation"]
ENV_URL_VARS = ("ENV_URL", "OPENENV_URL", "OPENENV_BASE_URL")
REMOTE_ENV_URL_VARS = ("HF_SPACE_URL", "SPACE_URL")
LOCAL_ENV_CANDIDATES = (
    "http://127.0.0.1:7860",
    "http://localhost:7860",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
)
DEFAULT_REMOTE_ENV_URL = "https://Mahesh811-incident-env.hf.space"


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
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


def _debug(msg: str) -> None:
    """Write diagnostics to stderr to keep stdout parser-friendly."""
    print(msg, file=sys.stderr, flush=True)


def _find_env_url_from_env() -> Optional[str]:
    """Return first explicit environment URL if configured."""
    for name in ENV_URL_VARS:
        value = os.getenv(name, "").strip()
        if value:
            _debug(f"[DEBUG] Using {name}={value}")
            return value
    return None


def _is_url_reachable(base_url: str, timeout_s: float = 2.0) -> bool:
    """Best-effort reachability probe for an OpenEnv server endpoint."""
    base = base_url.rstrip("/")
    for path in ("/health", "/"):
        try:
            req = urllib_request.Request(f"{base}{path}", method="GET")
            with urllib_request.urlopen(req, timeout=timeout_s) as response:
                if 200 <= response.status < 500:
                    return True
        except urllib_error.HTTPError as http_err:
            if 400 <= http_err.code < 500:
                return True
        except Exception:
            continue
    return False


def _remote_env_candidates() -> List[str]:
    """Collect remote env URLs in priority order with de-duplication."""
    seen = set()
    candidates: List[str] = []

    for name in REMOTE_ENV_URL_VARS:
        value = os.getenv(name, "").strip()
        if value and value not in seen:
            candidates.append(value)
            seen.add(value)

    if DEFAULT_REMOTE_ENV_URL not in seen:
        candidates.append(DEFAULT_REMOTE_ENV_URL)

    return candidates


async def _create_environment() -> IncidentEnv:
    """Create env client from URL first; fallback to Docker only when needed."""
    explicit_url = _find_env_url_from_env()
    if explicit_url:
        return IncidentEnv(base_url=explicit_url)

    for candidate in LOCAL_ENV_CANDIDATES:
        if _is_url_reachable(candidate):
            _debug(f"[DEBUG] Using running local environment at {candidate}")
            return IncidentEnv(base_url=candidate)

    for candidate in _remote_env_candidates():
        if _is_url_reachable(candidate, timeout_s=4.0):
            _debug(f"[DEBUG] Using remote environment at {candidate}")
            return IncidentEnv(base_url=candidate)

    _debug(f"[DEBUG] No URL environment found. Falling back to Docker image {IMAGE_NAME}")
    return await IncidentEnv.from_docker_image(IMAGE_NAME)


# ═══════════════════════════════════════════════════════════════════════
#  Enhanced System Prompt with SRE reasoning tactics
# ═══════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = textwrap.dedent("""\
You are an expert Site Reliability Engineer (SRE) responding to production incidents.
You will receive incident data: alerts, logs, metrics, service topology, and timeline.

REASONING FRAMEWORK — follow this EVERY time:
1. TIMELINE FIRST: Read the timeline chronologically. The FIRST service anomaly is likely the root cause.
2. DISTINGUISH SYMPTOM vs CAUSE: Downstream failures are SYMPTOMS, not the root cause.
   Example: If user-service fails because user-db pool exhausted, the root cause is user-db, NOT user-service.
3. IGNORE RED HERRINGS: Some alerts are unrelated (weekly reports, security scans, normal TTL churn).
   If an alert doesn't connect to the failure chain, ignore it.
4. CHECK DEPLOYMENTS: If a deployment happened right before issues, it's likely the cause.
5. LOOK AT TRENDS: For performance issues, memory/connections growing linearly = leak.
6. CASCADE TRACING: For multi-service failures, trace errors UPSTREAM to the origin.

You must respond with a JSON object containing exactly these fields:
{
  "severity": "P1_critical|P2_high|P3_medium|P4_low",
  "root_cause_service": "name of the service that is the PRIMARY root cause",
  "root_cause_category": "config_error|memory_leak|resource_exhaustion|network_failure|dependency_failure|code_bug|deployment_regression|data_corruption",
  "root_cause_description": "detailed explanation of what went wrong and why — include specific evidence from logs/metrics",
  "remediation": "ONE of: restart_service, rollback_deployment, scale_horizontally, fix_config, increase_resources, enable_circuit_breaker, failover, clear_cache, repair_data",
  "affected_services": "comma-separated list of ALL affected services including downstream"
}

CRITICAL RULES:
1. Output ONLY the JSON object. No markdown, no explanation, no code blocks.
2. Identify the ROOT CAUSE, not just the most visible symptom.
3. In your description, reference SPECIFIC evidence (timestamps, metric values, log messages).
4. Include ALL affected services (including downstream), not just the root cause.
5. Use the EXACT service names from the logs and topology.
6. The "remediation" field MUST be EXACTLY one of these 9 values: restart_service, rollback_deployment, scale_horizontally, fix_config, increase_resources, enable_circuit_breaker, failover, clear_cache, repair_data. Do NOT invent other values.
7. The "root_cause_category" MUST be EXACTLY one of: config_error, memory_leak, resource_exhaustion, network_failure, dependency_failure, code_bug, deployment_regression, data_corruption.
8. On RETRY: carefully read the feedback. Fix ONLY the fields marked ✗ (wrong). Keep fields marked ✓ (correct) unchanged.
""").strip()



# ═══════════════════════════════════════════════════════════════════════
#  Prompt building with conversation history
# ═══════════════════════════════════════════════════════════════════════

def build_initial_prompt(obs) -> str:
    """Build the first observation prompt."""
    parts = [
        "=== INCIDENT TRIAGE ===",
        f"\n--- TASK ---\n{obs.task_description}",
        f"\n--- ALERT ---\n{obs.incident_summary}",
        f"\n--- SERVICE TOPOLOGY ---\n{obs.service_topology}",
        f"\n--- LOGS ---\n{obs.log_entries}",
        f"\n--- METRICS ---\n{obs.metrics_snapshot}",
        f"\n--- TIMELINE ---\n{obs.timeline}",
        "\nAnalyze this incident step by step, then provide your diagnosis as a JSON object.",
    ]
    return "\n".join(parts)


def build_retry_prompt(obs, step: int, prev_action: Dict, prev_feedback: str = "", prev_hint: str = "") -> str:
    """Build a follow-up prompt incorporating feedback from the previous attempt."""
    parts = [
        f"=== INCIDENT TRIAGE — RETRY (Step {step}/{MAX_STEPS}) ===",
        f"\nYour previous diagnosis was INCORRECT. Here's what went wrong:",
        f"\n--- FEEDBACK ---\n{prev_feedback}",
    ]
    if prev_hint:
        parts.append(f"\n--- HINT ---\n{prev_hint}")

    parts.append(f"\nYour previous answer was:")
    parts.append(json.dumps(prev_action, indent=2))

    parts.append("\n--- REMINDER: KEY DATA ---")
    parts.append(f"Timeline:\n{obs.timeline}")
    parts.append(f"\nMetrics:\n{obs.metrics_snapshot}")

    parts.append(
        "\nUSE the feedback and hint above to CORRECT your diagnosis. "
        "Focus on the fields marked ✗ (wrong). "
        "Provide your corrected diagnosis as a JSON object."
    )
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════
#  LLM interaction
# ═══════════════════════════════════════════════════════════════════════

def parse_llm_response(text: str) -> Dict[str, str]:
    """Extract JSON from LLM response."""
    # Try to find JSON in code blocks first
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON
    m = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # Fallback: try to parse the whole thing
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return {}


def call_llm(client: Optional[OpenAI], messages: List[Dict], retries: int = 3) -> Dict[str, str]:
    """Call the LLM with full conversation history."""
    if client is None:
        return _fallback_policy()

    import time
    for attempt in range(retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            text = (resp.choices[0].message.content or "").strip()
            parsed = parse_llm_response(text)
            if parsed:
                return parsed
            _debug(f"[DEBUG] Failed to parse LLM response: {text[:200]}")
            return _fallback_policy()
        except Exception as e:
            err_str = str(e).lower()
            if ("rate" in err_str or "429" in err_str) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                _debug(f"[DEBUG] Rate limited, retrying in {wait}s (attempt {attempt+1}/{retries})")
                time.sleep(wait)
                continue
            _debug(f"[DEBUG] LLM call failed: {e}")
            return _fallback_policy()


def _fallback_policy() -> Dict[str, str]:
    """Fallback when LLM is unavailable."""
    return {
        "severity": "P1_critical",
        "root_cause_service": "user-service",
        "root_cause_category": "resource_exhaustion",
        "root_cause_description": "Service failure detected",
        "remediation": "restart_service",
        "affected_services": "user-service,api-gateway",
    }


# ═══════════════════════════════════════════════════════════════════════
#  Task runner with conversation memory
# ═══════════════════════════════════════════════════════════════════════

async def run_task(env: IncidentEnv, client: Optional[OpenAI], task_id: str) -> float:
    rewards: List[float] = []
    steps_taken = 0
    best_score = 0.0
    success = False

    log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)

    try:
        result = await env.reset(task_id=task_id)
        obs = result.observation

        # Conversation history for multi-turn reasoning
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_initial_prompt(obs)},
        ]

        prev_action_dict = None

        for step in range(1, MAX_STEPS + 1):
            if result.done:
                break

            # Build prompt: initial for step 1, retry for step 2+
            if step > 1 and prev_action_dict:
                retry_prompt = build_retry_prompt(
                    obs, step,
                    prev_action_dict,
                    obs.feedback or "",
                    obs.hint or "",
                )
                messages.append({"role": "user", "content": retry_prompt})

            action_dict = call_llm(client, messages)
            prev_action_dict = action_dict

            # Add assistant response to conversation history
            messages.append({"role": "assistant", "content": json.dumps(action_dict)})

            action = IncidentAction(
                severity=action_dict.get("severity", "P1_critical"),
                root_cause_service=action_dict.get("root_cause_service", "unknown"),
                root_cause_category=action_dict.get("root_cause_category", "code_bug"),
                root_cause_description=action_dict.get("root_cause_description", ""),
                remediation=action_dict.get("remediation", "restart_service"),
                affected_services=action_dict.get("affected_services", ""),
            )

            result = await env.step(action)
            obs = result.observation
            reward = result.reward or 0.0
            done = result.done

            rewards.append(reward)
            steps_taken = step

            if reward > best_score:
                best_score = reward

            action_summary = f"svc={action.root_cause_service} cat={action.root_cause_category} rem={action.remediation}"
            log_step(step=step, action=action_summary, reward=reward, done=done, error=None)

            if done:
                break

        score = round(best_score, 2)
        success = score >= SUCCESS_THRESHOLD

    except Exception as e:
        _debug(f"[DEBUG] Task {task_id} crashed: {e}")
        score = round(best_score, 2)
        success = score >= SUCCESS_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    # Log config for debugging
    key_masked = f"{API_KEY[:8]}...{API_KEY[-4:]}" if len(API_KEY) > 12 else "(empty)"
    _debug(f"[DEBUG] base_url={API_BASE_URL} model={MODEL_NAME} key={key_masked}")

    client: Optional[OpenAI] = None
    if API_KEY and len(API_KEY) > 5:
        try:
            client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
        except Exception as e:
            _debug(f"[DEBUG] Failed to initialize OpenAI client: {e}")
            client = None
    else:
        _debug("[DEBUG] No API key found. Running fallback policy (no LLM calls).")

    all_scores: Dict[str, float] = {}

    for task_id in TASK_IDS:
        env: Optional[IncidentEnv] = None
        try:
            env = await _create_environment()
        except Exception as e:
            _debug(f"[DEBUG] Environment init failed for task {task_id}: {e}")
            log_start(task=task_id, env=BENCHMARK, model=MODEL_NAME)
            log_end(success=False, steps=0, score=0.0, rewards=[])
            all_scores[task_id] = 0.0
            continue

        try:
            score = await run_task(env, client, task_id)
            all_scores[task_id] = score
        finally:
            if env is not None:
                try:
                    await env.close()
                except Exception as e:
                    _debug(f"[DEBUG] Failed to close environment cleanly: {e}")

    avg = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
    _debug(f"[DEBUG] Summary average={avg:.2f} scores={all_scores}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        _debug(f"[FATAL] Unhandled error in inference.py: {e}")