"""
Grading functions for the 3 incident response tasks.
All graders are deterministic: same action + same scenario = same score.
Returns (score: float, info: dict) where score is in [0.0, 1.0].

Scoring dimensions:
  severity:              0.10  (exact match)
  root_cause_service:    0.25  (exact match)
  root_cause_category:   0.15  (exact + close match)
  root_cause_description:0.15  (keyword matching)
  remediation:           0.15  (exact + acceptable)
  affected_services:     0.20  (IoU: intersection/union)
  TOTAL:                 1.00
"""

from typing import Dict, List, Set, Tuple

from .scenario_engine import Scenario

# Close-match groups for categories
_CATEGORY_GROUPS = {
    "resource_exhaustion": {"resource_exhaustion", "memory_leak"},
    "memory_leak": {"memory_leak", "resource_exhaustion"},
    "config_error": {"config_error", "deployment_regression"},
    "deployment_regression": {"deployment_regression", "config_error", "code_bug"},
    "code_bug": {"code_bug", "deployment_regression"},
    "network_failure": {"network_failure", "dependency_failure"},
    "dependency_failure": {"dependency_failure", "network_failure"},
    "data_corruption": {"data_corruption"},
}


def _iou(predicted: Set[str], actual: Set[str]) -> float:
    """Intersection over Union for service sets."""
    if not predicted and not actual:
        return 1.0
    if not predicted or not actual:
        return 0.0
    intersection = predicted & actual
    union = predicted | actual
    return len(intersection) / len(union)


def _keyword_score(text: str, keywords: List[str]) -> float:
    """Fraction of keywords found in text (case-insensitive)."""
    if not keywords:
        return 1.0
    text_lower = text.lower()
    found = sum(1 for kw in keywords if kw.lower() in text_lower)
    return found / len(keywords)


def grade_action(action_dict: dict, scenario: Scenario, step: int) -> Tuple[float, Dict]:
    """Grade an agent's incident response action against the scenario ground truth.

    Args:
        action_dict: The action fields from the agent.
        scenario: The scenario with ground truth.
        step: Current step number (1-indexed, for step penalty).

    Returns:
        (score, info) where score in [0.0, 1.0].
    """
    info = {}
    score = 0.0

    # --- 1. Severity (0.10) ---
    agent_sev = action_dict.get("severity", "").strip().lower()
    expected_sev = scenario.severity.lower()
    if agent_sev == expected_sev:
        score += 0.10
        info["severity"] = "exact_match"
    else:
        info["severity"] = f"wrong: got={agent_sev} expected={expected_sev}"

    # --- 2. Root cause service (0.25) ---
    agent_svc = action_dict.get("root_cause_service", "").strip().lower()
    expected_svc = scenario.root_cause_service.lower()
    if agent_svc == expected_svc:
        score += 0.25
        info["root_cause_service"] = "exact_match"
    else:
        info["root_cause_service"] = f"wrong: got={agent_svc} expected={expected_svc}"

    # --- 3. Root cause category (0.15) ---
    agent_cat = action_dict.get("root_cause_category", "").strip().lower()
    expected_cat = scenario.root_cause_category.lower()
    if agent_cat == expected_cat:
        score += 0.15
        info["root_cause_category"] = "exact_match"
    elif agent_cat in _CATEGORY_GROUPS.get(expected_cat, set()):
        score += 0.08
        info["root_cause_category"] = f"close_match: got={agent_cat} expected={expected_cat}"
    else:
        info["root_cause_category"] = f"wrong: got={agent_cat} expected={expected_cat}"

    # --- 4. Root cause description (0.15) — keyword matching ---
    agent_desc = action_dict.get("root_cause_description", "")
    kw_score = _keyword_score(agent_desc, scenario.root_cause_keywords)
    desc_points = round(0.15 * kw_score, 4)
    score += desc_points
    info["description_keywords"] = f"{kw_score:.0%} ({int(kw_score * len(scenario.root_cause_keywords))}/{len(scenario.root_cause_keywords)} keywords)"

    # --- 5. Remediation (0.15) ---
    agent_rem = action_dict.get("remediation", "").strip().lower()
    expected_rem = scenario.remediation.lower()
    acceptable = {r.lower() for r in scenario.acceptable_remediations}
    if agent_rem == expected_rem:
        score += 0.15
        info["remediation"] = "exact_match"
    elif agent_rem in acceptable:
        score += 0.10
        info["remediation"] = f"acceptable_alternative: {agent_rem}"
    else:
        info["remediation"] = f"wrong: got={agent_rem} expected={expected_rem}"

    # --- 6. Affected services (0.20) — IoU ---
    agent_svcs_raw = action_dict.get("affected_services", "")
    agent_svcs = {s.strip().lower() for s in agent_svcs_raw.split(",") if s.strip()}
    expected_svcs = {s.lower() for s in scenario.affected_services}
    iou_val = _iou(agent_svcs, expected_svcs)
    svc_points = round(0.20 * iou_val, 4)
    score += svc_points
    info["affected_services_iou"] = f"{iou_val:.0%}"
    if agent_svcs != expected_svcs:
        info["affected_services_detail"] = {
            "missing": list(expected_svcs - agent_svcs),
            "extra": list(agent_svcs - expected_svcs),
        }

    # --- Step penalty: -0.08 per step beyond first ---
    if step > 1:
        penalty = round(0.08 * (step - 1), 4)
        score = max(0.0, score - penalty)
        info["step_penalty"] = penalty

    score = round(min(max(score, 0.0), 1.0), 4)
    info["total_score"] = score
    return score, info
