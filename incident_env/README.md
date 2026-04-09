---
title: IncidentEnv
colorFrom: red
colorTo: orange
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
  - incident-response
  - sre
  - reinforcement-learning
---

# IncidentEnv — Production Incident Response Environment

An OpenEnv reinforcement-learning environment where AI agents learn to triage
production incidents in a realistic microservices architecture.

## Why Incident Response?

Production incident triage is one of the highest-stakes, most cognitively
demanding tasks in software engineering. SREs must rapidly correlate logs,
metrics, and service dependencies to identify root causes under pressure.
This environment simulates that exact workflow with deterministic, reproducible
grading — no fuzzy scoring, no LLM-as-judge.

## Tasks

| Task | Difficulty | Description |
|------|-----------|-------------|
| `single_service_failure` | Easy | Diagnose a clear single-service outage |
| `cascading_failure` | Medium | Trace a multi-service cascade to root cause |
| `performance_degradation` | Hard | Find subtle perf issue with red herrings |

## Action Space

| Field | Type | Description |
|-------|------|-------------|
| `severity` | `str` | P1_critical \| P2_high \| P3_medium \| P4_low |
| `root_cause_service` | `str` | Name of the root-cause service |
| `root_cause_category` | `str` | Failure type (config_error, memory_leak, etc.) |
| `root_cause_description` | `str` | Free-text explanation |
| `remediation` | `str` | Fix action (restart_service, rollback, etc.) |
| `affected_services` | `str` | Comma-separated list of all affected services |

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | `str` | Active task identifier |
| `task_description` | `str` | Full instructions for the agent |
| `incident_summary` | `str` | PagerDuty-style alert summary |
| `service_topology` | `str` | ASCII service dependency diagram |
| `log_entries` | `str` | Structured logs from all services |
| `metrics_snapshot` | `str` | Health metrics table per service |
| `timeline` | `str` | Chronological event summary |
| `feedback` | `str?` | Feedback on previous action (step 2+) |
| `hint` | `str?` | Progressive hint (step 3+) |
| `grading_info` | `dict` | Detailed score breakdown |
| `reward` | `float` | Score 0.0-1.0 |
| `done` | `bool` | Episode complete? |

## Reward Function

Multi-dimensional scoring (all tasks):

| Dimension | Weight | Scoring |
|-----------|--------|---------|
| Severity assessment | 0.10 | Exact match |
| Root cause service | 0.25 | Exact match (most important!) |
| Root cause category | 0.15 | Exact=full, close match=partial |
| Description quality | 0.15 | Keyword matching |
| Remediation | 0.15 | Exact=full, acceptable alt=partial |
| Affected services | 0.20 | IoU (intersection/union) |

**Step penalty:** -0.08 per step beyond the first (max 5 steps).

## Quick Start

```python
import asyncio
from incident_env import IncidentAction, IncidentEnv

async def main():
    env = await IncidentEnv.from_docker_image("incident_env:latest")
    try:
        result = await env.reset(task_id="single_service_failure")
        print(result.observation.incident_summary)

        result = await env.step(IncidentAction(
            severity="P1_critical",
            root_cause_service="user-db",
            root_cause_category="resource_exhaustion",
            root_cause_description="Connection pool exhausted at 100/100",
            remediation="increase_resources",
            affected_services="user-db,user-service,api-gateway",
        ))
        print(f"Reward: {result.reward}")
    finally:
        await env.close()

asyncio.run(main())
```

## Building

```bash
docker build -t incident_env:latest .
docker run -p 8000:8000 incident_env:latest
```

## Baseline Agent

```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export HF_TOKEN="your_token"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export LOCAL_IMAGE_NAME="incident_env:latest"
python inference.py
```

## Project Structure

```
incident_env/
├── __init__.py               ← Package exports
├── client.py                 ← IncidentEnv WebSocket client
├── models.py                 ← Action / Observation / State schemas
├── openenv.yaml              ← OpenEnv manifest
├── pyproject.toml            ← Dependencies
├── README.md                 ← This file (HF Space README)
└── server/
    ├── Dockerfile            ← Container build
    ├── app.py                ← FastAPI + WebSocket server
    ├── incident_env_environment.py ← Core environment logic
    ├── scenario_engine.py    ← 7 scenario variants across 3 tasks
    └── graders.py            ← Multi-dimensional scoring
```
