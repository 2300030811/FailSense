---
title: Incident Env
emoji: 🚒
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
tags:
  - openenv
---

# 🚒 IncidentEnv — Production Incident Response for AI Agents

[![OpenEnv](https://img.shields.io/badge/OpenEnv-compatible-blue)](https://github.com/meta-pytorch/OpenEnv)
[![HF Space](https://img.shields.io/badge/🤗-Live%20Space-yellow)](https://huggingface.co/spaces/Mahesh811/incident-env)
[![Baseline](https://img.shields.io/badge/Baseline-0.93%20avg-brightgreen)]()

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv)-compatible reinforcement-learning environment
where AI agents learn to **triage production incidents** in a realistic
e-commerce microservices architecture with **17 interconnected services**.

---

## 🎯 Motivation

Production incident triage is one of the most valuable and challenging tasks in
software engineering. On-call SREs must rapidly:

1. **Correlate** logs, metrics, and alerts from dozens of services
2. **Trace** cascading failures back to the root cause
3. **Distinguish** symptoms from causes and red herrings from real signals
4. **Recommend** the correct remediation under time pressure

This environment simulates exactly that. Every grader is **deterministic** — no
fuzzy scoring, no LLM-as-judge. Success requires genuine reasoning about
distributed systems.

**Why this matters:** There is no existing OpenEnv for SRE incident response. This fills a real gap for training and evaluating agents on a task that directly impacts production reliability.

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  AI Agent   │────→│  IncidentEnv │────→│ Scenario Engine  │
│(inference.py)│←────│   (server)   │←────│ (12 variants)    │
└─────────────┘     └──────────────┘     └─────────────────┘
                           │
                    ┌──────┴──────┐
                    │   Grader    │
                    │ (6 scoring  │
                    │  dimensions)│
                    └─────────────┘
```

**Flow:** `reset(task_id)` → agent receives observation → agent submits `IncidentAction` → grader scores on 6 dimensions → feedback returned → repeat up to 5 steps.

---

## 📋 Tasks

| Task ID | Difficulty | Description | Example Scenarios |
|---------|-----------|-------------|-------------------|
| `single_service_failure` | 🟢 Easy | Single service outage with clear signals | DB pool exhaustion, JWT config error, disk full, certificate expiry |
| `cascading_failure` | 🟡 Medium | Multi-service cascade requiring upstream tracing | Payment retry storm, cache OOM → DB overload, circuit breaker misconfiguration |
| `performance_degradation` | 🔴 Hard | Subtle perf issue masked by red herrings | Memory leak over hours, N+1 query regression, connection pool leak, RAID degradation |

Each task type draws from **12 unique scenario variants**, ensuring diverse evaluation across runs with different root causes, affected services, and failure patterns.

---

## 🎮 Action Space

The agent submits a structured diagnosis via `IncidentAction`:

```python
class IncidentAction(Action):
    severity: str              # "P1_critical" | "P2_high" | "P3_medium" | "P4_low"
    root_cause_service: str    # e.g. "user-db", "payment-service"
    root_cause_category: str   # e.g. "resource_exhaustion", "config_error", "memory_leak"
    root_cause_description: str  # Free-text explanation with evidence
    remediation: str           # e.g. "increase_resources", "rollback_deployment", "fix_config"
    affected_services: str     # e.g. "user-db,user-service,api-gateway"
```

**Allowed values:**
- **severity**: `P1_critical`, `P2_high`, `P3_medium`, `P4_low`
- **root_cause_category**: `config_error`, `memory_leak`, `resource_exhaustion`, `network_failure`, `dependency_failure`, `code_bug`, `deployment_regression`, `data_corruption`
- **remediation**: `restart_service`, `rollback_deployment`, `scale_horizontally`, `fix_config`, `increase_resources`, `enable_circuit_breaker`, `failover`, `clear_cache`, `repair_data`

---

## 👁️ Observation Space

The agent receives everything an on-call SRE would see when paged:

```python
class IncidentObservation(Observation):
    task_description: str      # What the agent needs to do
    incident_summary: str      # PagerDuty-style alert
    service_topology: str      # ASCII dependency diagram (17 services)
    log_entries: str           # Structured logs with timestamps, levels, messages
    metrics_snapshot: str      # CPU, memory, latency, error rate per service
    timeline: str              # Chronological event sequence
    feedback: str              # (step 2+) Structured ✓/✗/~ per-dimension feedback
    hint: str                  # (step 3+) Progressive hints to guide convergence
```

**Feedback format** (step 2+):
```
Diagnosis feedback:
  ✓ severity: correct (P1_critical)
  ✗ root_cause_service: wrong — expected 'order-db', got 'order-service'
  ~ root_cause_category: partial — acceptable but not exact
  ✗ remediation: wrong — expected 'increase_resources'
```

This structured feedback gives the agent actionable signal for self-correction.

---

## 📊 Reward Function (1.0 max)

| Dimension | Weight | Method |
|-----------|--------|--------|
| Severity | 0.10 | Exact match (P1/P2/P3/P4) |
| Root cause service | 0.25 | Exact match with alias normalization |
| Root cause category | 0.15 | Exact (0.15) or semantically close (0.08) |
| Description quality | 0.15 | Keyword coverage (fraction of key terms found) |
| Remediation | 0.15 | Exact (0.15) or acceptable alternative (0.10) |
| Affected services | 0.20 | IoU (intersection ÷ union) of service sets |

**Step penalty:** −0.08 per step beyond the first.  
**Episode termination:** Score ≥ 0.90 **or** step 5 reached.

### Reward Properties
- ✅ **Partial credit**: Every field contributes independently — agents get signal even with partial answers
- ✅ **Varying signal**: Scores range from 0.0 to 1.0 with meaningful gradations, not sparse binary
- ✅ **Penalizes bad behavior**: Step penalty discourages unnecessary iterations
- ✅ **Service name aliasing**: `notif-svc` matches `notification-service` (robust to naming variants)

---

## 🚀 Setup & Usage

### Prerequisites
- Python 3.10+
- Docker (for containerized execution)
- `pip install openenv-core[core] openai python-dotenv`

### Build & Run Locally
```bash
# Build the Docker image
docker build -t incident_env:latest .

# Run the environment server
docker run -p 7860:7860 incident_env:latest
```

### Run the Baseline Agent
```bash
# Set required environment variables
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export HF_TOKEN="your_huggingface_token"

# Optional: connect to remote HF Space instead of local Docker
export ENV_URL="https://Mahesh811-incident-env.hf.space"

# Run inference
python inference.py
```

### Deploy to Hugging Face Spaces
```bash
# 1. Create a new Space on huggingface.co (Docker SDK)
# 2. Push the repo as the Space content
# 3. The Space builds from the root Dockerfile
# 4. Tag the Space with "openenv"

# Or use openenv CLI:
openenv push --repo-id YOUR_USERNAME/incident-env
```

### Validate Before Submission
```bash
# From the incident_env/ directory:
cd incident_env
openenv validate

# Expected output:
# [OK] incident: Ready for multi-mode deployment
```

---

## 📈 Baseline Scores

Tested with **Qwen/Qwen2.5-72B-Instruct** via Hugging Face Inference API:

| Task | Score | Steps | Notes |
|------|-------|-------|-------|
| `single_service_failure` | **0.95** | 1 | Nailed on first attempt |
| `cascading_failure` | **0.90** | 2 | Self-corrected using feedback |
| `performance_degradation` | **0.94** | 1 | Correctly identified subtle root cause |
| **Average** | **0.93** | — | — |

### Why the Hard Task is Hard
- No explicit `ERROR` logs for the root cause service
- Red herring alerts from unrelated services (security scans, weekly reports)
- Must correlate **time-series trends** (memory growth, connection count) over hours
- Must distinguish deployment **correlation** from **causation**
- Multiple plausible root causes require careful evidence analysis

---

## ⚙️ Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | LLM API endpoint |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |
| `HF_TOKEN` | Yes | — | Hugging Face API key for inference |
| `LOCAL_IMAGE_NAME` | No | `incident_env:latest` | Docker image name for local runs |
| `ENV_URL` | No | — | Remote environment URL (skips local Docker) |

---

## 🗂️ Project Structure

```
FailSense/
├── inference.py              # Baseline inference script (root, as required)
├── Dockerfile                # HF Space container (port 7860)
├── openenv.yaml              # OpenEnv spec metadata
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── uv.lock                   # Dependency lockfile
└── incident_env/             # OpenEnv environment package
    ├── __init__.py            # Package exports
    ├── client.py              # IncidentEnv client (remote/Docker)
    ├── models.py              # Pydantic Action/Observation/State models
    ├── openenv.yaml           # Inner OpenEnv spec
    ├── pyproject.toml         # Package config with server entry point
    ├── uv.lock                # Inner lockfile
    └── server/
        ├── app.py             # FastAPI application (create_app + main)
        ├── incident_env_environment.py  # Environment logic (step/reset/state)
        ├── graders.py         # 6-dimension deterministic grading
        └── scenario_engine.py # 12-variant scenario generation
```

---

## 📜 License

MIT
