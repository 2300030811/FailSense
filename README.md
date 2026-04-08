---
title: Incident Env
emoji: 🚒
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# IncidentEnv — Production Incident Response for AI Agents

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv) reinforcement-learning environment
where AI agents learn to **triage production incidents** in a realistic
e-commerce microservices architecture.

## Motivation

Production incident triage is one of the most valuable and challenging tasks in
software engineering. On-call SREs must rapidly:

1. **Correlate** logs, metrics, and alerts from dozens of services
2. **Trace** cascading failures back to the root cause
3. **Distinguish** symptoms from causes and red herrings from real signals
4. **Recommend** the correct remediation under time pressure

This environment simulates exactly that. Every grader is deterministic — no
fuzzy scoring, no LLM-as-judge. Success requires genuine reasoning about
distributed systems.

## Architecture

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

## Tasks

| Task | Difficulty | Description | Example Scenario |
|------|-----------|-------------|------------------|
| `single_service_failure` | Easy | Single service outage | DB pool exhaustion, JWT config error, disk full |
| `cascading_failure` | Medium | Multi-service cascade | Payment retry storm, cache OOM → DB overload |
| `performance_degradation` | Hard | Subtle perf issue + red herrings | Memory leak over hours, N+1 query regression |

## Action Space

```python
class IncidentAction(Action):
    severity: str           # "P1_critical" | "P2_high" | "P3_medium" | "P4_low"
    root_cause_service: str # e.g. "user-db"
    root_cause_category: str # e.g. "resource_exhaustion"
    root_cause_description: str # Free-text explanation
    remediation: str        # e.g. "increase_resources"
    affected_services: str  # e.g. "user-db,user-service,api-gateway"
```

## Observation Space

The agent receives everything an SRE would see when paged:

- **Incident Summary**: PagerDuty-style alert
- **Service Topology**: ASCII dependency diagram (17 services)
- **Log Entries**: Structured logs from all services (timestamps, levels, messages)
- **Metrics Snapshot**: CPU, memory, latency, error rate per service
- **Timeline**: Chronological event sequence
- **Feedback** (step 2+): What was wrong with the previous diagnosis
- **Hint** (step 3+): Progressive hints to guide convergence

## Reward Function (1.0 max)

| Dimension | Weight | Method |
|-----------|--------|--------|
| Severity | 0.10 | Exact match |
| Root cause service | 0.25 | Exact match |
| Root cause category | 0.15 | Exact (0.15) or close match (0.08) |
| Description quality | 0.15 | Keyword matching (fraction of key terms found) |
| Remediation | 0.15 | Exact (0.15) or acceptable alternative (0.10) |
| Affected services | 0.20 | IoU (intersection ÷ union) |

**Step penalty**: -0.08 per step beyond the first. Episode ends on score ≥0.90 or step 5.

## Setup

### Prerequisites
- Python 3.10+
- Docker
- `pip install openenv-core[core] openai python-dotenv`

### Build & Run
```bash
# Build the Docker image
docker build -t incident_env:latest .

# Run locally
docker run -p 8000:8000 incident_env:latest
```

### Run the Baseline Agent
```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export HF_TOKEN="your_huggingface_token"
export MODEL_NAME="Qwen/Qwen2.5-72B-Instruct"
export LOCAL_IMAGE_NAME="incident_env:latest"

python inference.py
```

### Deploy to Hugging Face Spaces
```bash
# 1. Create a new Space on huggingface.co (Docker SDK)
# 2. Push the incident_env/ directory as the Space repo
# 3. The Space will build from incident_env/server/Dockerfile
# 4. Tag the Space with "openenv"

# Or use openenv CLI:
openenv push --repo-id YOUR_USERNAME/incident-env
```

### Validate Before Submission
```bash
# Run the pre-submission validator
./validate-submission.sh https://YOUR_USERNAME-incident-env.hf.space .
```

## Expected Baseline Scores

| Task | Expected Score (Qwen2.5-72B) |
|------|------------------------------|
| single_service_failure | 0.90 - 1.00 |
| cascading_failure | 0.80 - 0.95 |
| performance_degradation | 0.85 - 0.95 |

The hard task genuinely challenges frontier models because:
- No explicit ERROR logs for the root cause
- Red herring alerts from unrelated services
- Must correlate time-series trends (memory growth) over hours
- Must distinguish deployment correlation from causation

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_BASE_URL` | No | `https://router.huggingface.co/v1` | LLM endpoint |
| `MODEL_NAME` | No | `Qwen/Qwen2.5-72B-Instruct` | Model identifier |
| `HF_TOKEN` | Yes | — | Hugging Face API key |
| `LOCAL_IMAGE_NAME` | No | `incident_env:latest` | Docker image name |
