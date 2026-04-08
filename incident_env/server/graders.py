"""
Grading functions for the 3 incident response tasks.
All graders are deterministic: same action + same scenario = same score.
Returns (score: float, info: dict) where score is in [0.0, 1.0].

Scoring dimensions:
  severity:              0.10  (exact match)
  root_cause_service:    0.25  (exact match + alias resolution)
  root_cause_category:   0.15  (exact + close match)
  root_cause_description:0.15  (keyword matching)
  remediation:           0.15  (exact + acceptable)
  affected_services:     0.20  (IoU: intersection/union + alias resolution)
  TOTAL:                 1.00
"""

from typing import Dict, List, Set, Tuple

from .scenario_engine import Scenario

# ═══════════════════════════════════════════════════════════════════════
#  Service Name Aliasing — normalize common variations
# ═══════════════════════════════════════════════════════════════════════

_SERVICE_ALIASES: Dict[str, str] = {
    # notification variants
    "notification-svc": "notification-service",
    "notification_svc": "notification-service",
    "notification_service": "notification-service",
    "notif-service": "notification-service",
    "notif-svc": "notification-service",
    # inventory variants
    "inventory-svc": "inventory-service",
    "inventory_service": "inventory-service",
    "inventory_svc": "inventory-service",
    # auth variants
    "auth-svc": "auth-service",
    "auth_service": "auth-service",
    "auth_svc": "auth-service",
    # user variants
    "user-svc": "user-service",
    "user_service": "user-service",
    "user_svc": "user-service",
    "users-service": "user-service",
    # product variants
    "product-svc": "product-service",
    "product_service": "product-service",
    "product_svc": "product-service",
    "products-service": "product-service",
    # order variants
    "order-svc": "order-service",
    "order_service": "order-service",
    "order_svc": "order-service",
    "orders-service": "order-service",
    # payment variants
    "payment-svc": "payment-service",
    "payment_service": "payment-service",
    "payment_svc": "payment-service",
    # cache variants
    "cache-svc": "cache-service",
    "cache_service": "cache-service",
    "cache_svc": "cache-service",
    "redis": "cache-service",
    "redis-cache": "cache-service",
    # db variants
    "userdb": "user-db",
    "user_db": "user-db",
    "productdb": "product-db",
    "product_db": "product-db",
    "orderdb": "order-db",
    "order_db": "order-db",
    "inventorydb": "inventory-db",
    "inventory_db": "inventory-db",
    "authdb": "auth-db",
    "auth_db": "auth-db",
    # gateway variants
    "gateway": "api-gateway",
    "api_gateway": "api-gateway",
    "apigateway": "api-gateway",
    # provider variants
    "payment_provider": "payment-provider",
    "email_api": "email-api",
    "sms_api": "sms-api",
    # analytics
    "analytics-svc": "analytics-service",
    "analytics_service": "analytics-service",
    "analytics_svc": "analytics-service",
}


def _normalize_service(name: str) -> str:
    """Normalize a service name using alias table."""
    name = name.strip().lower().replace(" ", "-")
    return _SERVICE_ALIASES.get(name, name)


def _normalize_service_set(raw: str) -> Set[str]:
    """Parse and normalize a comma-separated service list."""
    return {_normalize_service(s) for s in raw.split(",") if s.strip()}


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
        info["severity"] = "correct"
    else:
        # Partial credit for adjacent severity
        sev_order = ["p4_low", "p3_medium", "p2_high", "p1_critical"]
        if agent_sev in sev_order and expected_sev in sev_order:
            distance = abs(sev_order.index(agent_sev) - sev_order.index(expected_sev))
            if distance == 1:
                score += 0.04
                info["severity"] = f"close: got={agent_sev} expected={expected_sev} (+0.04)"
            else:
                info["severity"] = f"wrong: got={agent_sev} expected={expected_sev}"
        else:
            info["severity"] = f"wrong: got={agent_sev} expected={expected_sev}"

    # --- 2. Root cause service (0.25) with alias normalization ---
    agent_svc = _normalize_service(action_dict.get("root_cause_service", ""))
    expected_svc = _normalize_service(scenario.root_cause_service)
    if agent_svc == expected_svc:
        score += 0.25
        info["root_cause_service"] = "correct"
    else:
        info["root_cause_service"] = f"wrong: got={agent_svc} expected={expected_svc}"

    # --- 3. Root cause category (0.15) ---
    agent_cat = action_dict.get("root_cause_category", "").strip().lower()
    expected_cat = scenario.root_cause_category.lower()
    if agent_cat == expected_cat:
        score += 0.15
        info["root_cause_category"] = "correct"
    elif agent_cat in _CATEGORY_GROUPS.get(expected_cat, set()):
        score += 0.08
        info["root_cause_category"] = f"close: got={agent_cat} expected={expected_cat} (+0.08)"
    else:
        info["root_cause_category"] = f"wrong: got={agent_cat} expected={expected_cat}"

    # --- 4. Root cause description (0.15) — keyword matching ---
    agent_desc = action_dict.get("root_cause_description", "")
    kw_score = _keyword_score(agent_desc, scenario.root_cause_keywords)
    desc_points = round(0.15 * kw_score, 4)
    score += desc_points
    matched = int(kw_score * len(scenario.root_cause_keywords))
    total_kw = len(scenario.root_cause_keywords)
    info["description_keywords"] = f"{matched}/{total_kw} keywords matched ({kw_score:.0%})"

    # --- 5. Remediation (0.15) ---
    agent_rem = action_dict.get("remediation", "").strip().lower()
    expected_rem = scenario.remediation.lower()
    acceptable = {r.lower() for r in scenario.acceptable_remediations}
    if agent_rem == expected_rem:
        score += 0.15
        info["remediation"] = "correct"
    elif agent_rem in acceptable:
        score += 0.10
        info["remediation"] = f"acceptable: {agent_rem} (+0.10)"
    else:
        info["remediation"] = f"wrong: got={agent_rem} expected={expected_rem} (also accepted: {', '.join(acceptable)})"

    # --- 6. Affected services (0.20) — IoU with alias normalization ---
    agent_svcs_raw = action_dict.get("affected_services", "")
    agent_svcs = _normalize_service_set(agent_svcs_raw)
    expected_svcs = {_normalize_service(s) for s in scenario.affected_services}
    iou_val = _iou(agent_svcs, expected_svcs)
    svc_points = round(0.20 * iou_val, 4)
    score += svc_points
    info["affected_services_iou"] = f"{iou_val:.0%}"
    missing = expected_svcs - agent_svcs
    extra = agent_svcs - expected_svcs
    if missing or extra:
        info["affected_services_detail"] = {
            "missing": sorted(missing) if missing else [],
            "extra": sorted(extra) if extra else [],
        }

    # --- Step penalty: -0.08 per step beyond first ---
    if step > 1:
        penalty = round(0.08 * (step - 1), 4)
        score = max(0.0, score - penalty)
        info["step_penalty"] = f"-{penalty:.2f}"

    score = round(min(max(score, 0.0), 1.0), 4)
    info["total_score"] = score
    return score, info
