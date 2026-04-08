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
import textwrap
from typing import Dict, List, Optional

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
            print(f"[DEBUG] Failed to parse LLM response: {text[:200]}", flush=True)
            return _fallback_policy()
        except Exception as e:
            err_str = str(e).lower()
            if ("rate" in err_str or "429" in err_str) and attempt < retries - 1:
                wait = 2 ** (attempt + 1)
                print(f"[DEBUG] Rate limited, retrying in {wait}s (attempt {attempt+1}/{retries})", flush=True)
                time.sleep(wait)
                continue
            print(f"[DEBUG] LLM call failed: {e}", flush=True)
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
        print(f"[DEBUG] Task {task_id} crashed: {e}", flush=True)
        score = 0.0

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)

    return score


async def main() -> None:
    # Log config for debugging
    key_masked = f"{API_KEY[:8]}...{API_KEY[-4:]}" if len(API_KEY) > 12 else "(empty)"
    print(f"[CONFIG] base_url={API_BASE_URL} model={MODEL_NAME} key={key_masked}", flush=True)

    client: Optional[OpenAI] = None
    if API_KEY and len(API_KEY) > 5:
        client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)
    else:
        print("[DEBUG] No API key found. Running fallback policy (no LLM calls).", flush=True)

    all_scores: Dict[str, float] = {}

    for task_id in TASK_IDS:
        env_url = os.getenv("ENV_URL")
        if env_url:
            print(f"[CONFIG] Connecting to remote environment at {env_url}", flush=True)
            env = IncidentEnv(base_url=env_url)
        else:
            print(f"[CONFIG] Starting local environment from image {IMAGE_NAME}", flush=True)
            env = await IncidentEnv.from_docker_image(IMAGE_NAME)

        try:
            score = await run_task(env, client, task_id)
            all_scores[task_id] = score
        finally:
            await env.close()

    print("\n[SUMMARY]", flush=True)
    for tid, sc in all_scores.items():
        print(f"  {tid}: {sc:.2f}", flush=True)
    avg = sum(all_scores.values()) / len(all_scores) if all_scores else 0.0
    print(f"  average: {avg:.2f}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())