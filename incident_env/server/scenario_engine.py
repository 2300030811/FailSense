"""
Scenario Engine for the Incident Response Environment.

Generates deterministic, realistic production incident scenarios across
three difficulty tiers. Each scenario includes ground truth, simulated logs,
health metrics, service topology, and progressive hints.

All scenarios are seeded for full reproducibility.
"""

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Scenario:
    """Complete incident scenario with ground truth and display data."""
    task_id: str
    variant_id: int
    scenario_name: str
    severity: str
    root_cause_service: str
    root_cause_category: str
    root_cause_keywords: List[str]
    remediation: str
    acceptable_remediations: List[str]
    affected_services: List[str]
    incident_summary: str
    service_topology: str
    log_entries: str
    metrics_snapshot: str
    timeline: str
    hints: List[str]


ECOMMERCE_TOPOLOGY = """\
Service Dependency Map (e-commerce platform):
  [client] -> [api-gateway] -> [auth-service] -> [auth-db]
                    |-> [user-service] -> [user-db]
                    |-> [product-service] -> [product-db]
                    |         |-> [cache-service]
                    |-> [order-service] -> [order-db]
                    |         |-> [payment-service] -> [payment-provider]
                    |-> [inventory-service] -> [inventory-db]
                    |-> [notification-service] -> [email-api, sms-api]
All inter-service calls use gRPC. Databases are PostgreSQL.
cache-service is Redis. payment-provider and email-api are external."""


def _ts(h, m, off):
    t = h*3600 + m*60 + off
    return f"2024-06-15 {(t//3600)%24:02d}:{(t%3600)//60:02d}:{t%60:02d}.{(off*137)%1000:03d}"


TASK_IDS = ["single_service_failure", "cascading_failure", "performance_degradation"]


def _build_task1_v0():
    """user-db connection pool exhaustion."""
    logs = "\n".join([
        f"[{_ts(14,20,0)}] user-db         INFO   Connection pool: active=95/100 idle=5",
        f"[{_ts(14,20,30)}] user-db         WARN   Pool nearing capacity: active=99/100 waiting=12",
        f"[{_ts(14,20,45)}] user-db         ERROR  Pool EXHAUSTED: active=100/100 idle=0 waiting=47",
        f"[{_ts(14,20,46)}] user-service    ERROR  Failed to acquire DB connection: pool exhausted | timeout=5000ms | trace_id=tr-8a3f",
        f"[{_ts(14,20,47)}] api-gateway     ERROR  Upstream: user-service returned 503 | path=/api/users/123",
        f"[{_ts(14,20,50)}] user-service    ERROR  ConnectionPoolTimeoutError | active=100 | pool=user-db:5432",
        f"[{_ts(14,20,55)}] api-gateway     ERROR  Circuit breaker OPEN for user-service | failures=10",
        f"[{_ts(14,21,0)}] product-service  INFO   Health check OK | latency_p99=12ms",
        f"[{_ts(14,21,0)}] order-service    INFO   Health check OK | latency_p99=45ms",
        f"[{_ts(14,21,5)}] user-service    FATAL  Service degraded | failed_requests_last_60s=234",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|Status\n"
        "--------------------|----|----|-----------|----------|--------\n"
        "api-gateway         |34% |55% |245ms      |15.2%     |degraded\n"
        "user-service        |12% |61% |N/A        |100.0%    |DOWN\n"
        "user-db             |89% |78% |N/A        |0.0%      |overloaded\n"
        "product-service     |22% |45% |12ms       |0.1%      |healthy\n"
        "order-service       |19% |44% |45ms       |0.3%      |healthy\n"
        "auth-service        |8%  |42% |8ms        |0.0%      |healthy\n"
        "payment-service     |11% |39% |89ms       |0.0%      |healthy"
    )
    timeline = (
        "14:20:00  user-db pool at 95%\n"
        "14:20:30  user-db pool at 99%, 12 waiting\n"
        "14:20:45  user-db pool EXHAUSTED (100/100)\n"
        "14:20:46  user-service starts returning 503\n"
        "14:20:55  api-gateway circuit breaker OPEN\n"
        "14:21:05  user-service DOWN"
    )
    return Scenario(
        task_id="single_service_failure", variant_id=0,
        scenario_name="Database Connection Pool Exhaustion",
        severity="P1_critical",
        root_cause_service="user-db",
        root_cause_category="resource_exhaustion",
        root_cause_keywords=["connection", "pool", "exhaust", "capacity", "100"],
        remediation="increase_resources",
        acceptable_remediations=["restart_service", "scale_horizontally"],
        affected_services=["user-db", "user-service", "api-gateway"],
        incident_summary="ALERT [P1] user-service: 100% error rate\nTriggered: 14:20:46 UTC\nImpact: All user API endpoints returning 503\nOn-call: You",
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "Look at which service first showed errors in the timeline.",
            "user-db metrics show high CPU. Check connection pool stats.",
            "user-db pool reached 100/100 before user-service started failing.",
        ],
    )


def _build_task1_v1():
    """auth-service JWT secret mismatch after deployment."""
    logs = "\n".join([
        f"[{_ts(10,15,0)}] auth-service     INFO   Deployment v2.4.1 started | commit=a3f8c21",
        f"[{_ts(10,15,8)}] auth-service     INFO   Service started on port 8082 | version=v2.4.1",
        f"[{_ts(10,15,12)}] auth-service     ERROR  JWT verification failed: signature mismatch | trace_id=tr-1a2b",
        f"[{_ts(10,15,14)}] auth-service     ERROR  JWT verification failed: signature mismatch | rate=47/s",
        f"[{_ts(10,15,15)}] api-gateway      ERROR  Mass auth failures | 401_rate=98.7% | window=60s",
        f"[{_ts(10,15,20)}] api-gateway      WARN   Session invalidation storm: 2341 users logged out in 30s",
        f"[{_ts(10,15,25)}] notification-svc WARN   Password-reset email spike: 156/min (normal: 3/min)",
        f"[{_ts(10,15,30)}] auth-service     ERROR  JWT failures cumulative=4891",
        f"[{_ts(10,15,32)}] auth-service     WARN   All pre-v2.4.1 tokens failing verification",
        f"[{_ts(10,15,18)}] user-service     INFO   Health check OK | latency_p99=15ms",
        f"[{_ts(10,15,18)}] product-service  INFO   Health check OK | latency_p99=11ms",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|Status\n"
        "--------------------|----|----|-----------|----------|--------\n"
        "api-gateway         |41% |58% |34ms       |98.7%     |critical\n"
        "auth-service        |67% |55% |12ms       |98.7%     |critical\n"
        "user-service        |14% |42% |15ms       |0.0%      |healthy\n"
        "product-service     |19% |45% |11ms       |0.0%      |healthy\n"
        "order-service       |11% |38% |34ms       |2.1%      |healthy"
    )
    timeline = (
        "10:15:00  auth-service deployment v2.4.1 begins\n"
        "10:15:08  auth-service v2.4.1 online\n"
        "10:15:12  First JWT verification failure\n"
        "10:15:15  98.7% auth failures\n"
        "10:15:20  Mass session invalidation (2341 users)"
    )
    return Scenario(
        task_id="single_service_failure", variant_id=1,
        scenario_name="JWT Secret Mismatch After Deployment",
        severity="P1_critical",
        root_cause_service="auth-service",
        root_cause_category="config_error",
        root_cause_keywords=["jwt", "secret", "mismatch", "config", "deployment", "signature"],
        remediation="rollback_deployment",
        acceptable_remediations=["fix_config"],
        affected_services=["auth-service", "api-gateway"],
        incident_summary="ALERT [P1] auth-service: 98.7% authentication failure\nTriggered: 10:15:15 UTC\nImpact: All authenticated requests failing 401\nNote: Deployed v2.4.1 at 10:15:00\nOn-call: You",
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "What changed right before errors started? Check the timeline.",
            "auth-service deployed at 10:15:00, errors at 10:15:12.",
            "JWT signature mismatch = new deployment has different JWT_SECRET.",
        ],
    )


def _build_task1_v2():
    """inventory-db disk full."""
    logs = "\n".join([
        f"[{_ts(16,40,0)}] inventory-db     WARN   Disk usage 94% on /data/pgdata | 50GB total",
        f"[{_ts(16,42,0)}] inventory-db     WARN   Disk usage 97%",
        f"[{_ts(16,43,0)}] inventory-db     ERROR  FATAL: could not write WAL: No space left on device",
        f"[{_ts(16,43,1)}] inventory-db     ERROR  PANIC: disk_free=0B",
        f"[{_ts(16,43,2)}] inventory-svc    ERROR  DB write failed: disk full | sku=SKU-7234",
        f"[{_ts(16,43,4)}] order-service    ERROR  Inventory reservation failed | order=ord-5521",
        f"[{_ts(16,43,8)}] api-gateway      WARN   order-service 500 for POST /api/orders",
        f"[{_ts(16,43,15)}] inventory-svc    ERROR  All writes failing | failed_last_60s=89",
        f"[{_ts(16,43,20)}] order-service    WARN   73% orders failing at inventory step",
        f"[{_ts(16,43,10)}] product-service  INFO   Health check OK",
        f"[{_ts(16,43,10)}] user-service     INFO   Health check OK",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|Disk |Status\n"
        "--------------------|----|----|-----------|----------|-----|--------\n"
        "inventory-db        |91% |82% |N/A        |100.0%    |100% |DOWN\n"
        "inventory-service   |45% |59% |N/A        |100.0%    |N/A  |DOWN\n"
        "order-service       |31% |47% |234ms      |73.0%     |N/A  |degraded\n"
        "api-gateway         |28% |51% |156ms      |12.3%     |N/A  |degraded\n"
        "product-service     |20% |44% |14ms       |0.1%      |N/A  |healthy\n"
        "user-service        |16% |43% |11ms       |0.0%      |N/A  |healthy"
    )
    timeline = (
        "16:40:00  inventory-db disk at 94%\n"
        "16:42:00  inventory-db disk at 97%\n"
        "16:43:00  inventory-db disk FULL - WAL failure\n"
        "16:43:02  inventory-service writes failing\n"
        "16:43:04  order-service cannot place orders\n"
        "16:43:20  73% order failures"
    )
    return Scenario(
        task_id="single_service_failure", variant_id=2,
        scenario_name="Database Disk Full",
        severity="P1_critical",
        root_cause_service="inventory-db",
        root_cause_category="resource_exhaustion",
        root_cause_keywords=["disk", "full", "space", "WAL", "write", "storage"],
        remediation="increase_resources",
        acceptable_remediations=["restart_service", "clear_cache"],
        affected_services=["inventory-db", "inventory-service", "order-service", "api-gateway"],
        incident_summary="ALERT [P1] order-service: 73% order failure rate\nTriggered: 16:43:20 UTC\nImpact: Most orders failing at inventory step\nOn-call: You",
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "Order failures at 'inventory' step. Look upstream.",
            "inventory-service 500s because of DB write failures.",
            "inventory-db disk is 100% full - WAL write failures.",
        ],
    )


def _build_task2_v0():
    """payment-service retry storm cascade."""
    logs = "\n".join([
        f"[{_ts(9,30,5)}] payment-service  WARN   Provider latency spike: p99=4200ms (normal: 200ms)",
        f"[{_ts(9,30,8)}] payment-service  ERROR  Provider timeout 5000ms | order=ord-8801 | retry=1/3",
        f"[{_ts(9,30,10)}] payment-service  WARN   Retrying ord-8801 (2/3) | backoff=0ms",
        f"[{_ts(9,30,11)}] payment-service  ERROR  Provider timeout | retry=2/3",
        f"[{_ts(9,30,12)}] payment-service  WARN   Retrying ord-8801 (3/3) | backoff=0ms",
        f"[{_ts(9,30,13)}] payment-service  ERROR  FAILED after 3 retries | total_time=15034ms | NO BACKOFF",
        f"[{_ts(9,30,13)}] payment-service  WARN   Thread pool: 48/50 busy with retries | queue=234",
        f"[{_ts(9,30,15)}] order-service    ERROR  Payment failed for ord-8801",
        f"[{_ts(9,30,18)}] notification-svc INFO   Sending order-failed email | ord-8801",
        f"[{_ts(9,30,20)}] payment-service  ERROR  Thread pool EXHAUSTED: 50/50 | queued=567",
        f"[{_ts(9,30,25)}] order-service    ERROR  89 orders failed in 60s at payment step",
        f"[{_ts(9,30,28)}] notification-svc WARN   Queue depth critical: 412 pending (normal: 5)",
        f"[{_ts(9,30,32)}] email-api        WARN   Rate limit: 450/500 per minute",
        f"[{_ts(9,30,35)}] sms-api          ERROR  Rate limit EXCEEDED: 429",
        f"[{_ts(9,30,38)}] user-service     INFO   Health check OK | latency_p99=14ms",
        f"[{_ts(9,30,38)}] product-service  INFO   Health check OK | latency_p99=12ms",
        f"[{_ts(9,30,30)}] api-gateway      WARN   POST /api/orders: 67% failures | p99=15400ms",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|Threads |Status\n"
        "--------------------|----|----|-----------|----------|--------|--------\n"
        "payment-service     |94% |87% |15034ms    |98.2%     |50/50   |DOWN\n"
        "payment-provider    | -  | -  |4200ms+    |timeout   |  -     |external\n"
        "order-service       |55% |62% |8900ms     |67.0%     |78/100  |critical\n"
        "notification-svc    |78% |71% |890ms      |4.5%      |45/60   |degraded\n"
        "api-gateway         |38% |56% |15400ms    |67.0%     |34/100  |critical\n"
        "email-api           | -  | -  | -         |0.0%      |  -     |rate-limited\n"
        "sms-api             | -  | -  | -         |100.0%    |  -     |rate-limited\n"
        "user-service        |14% |42% |14ms       |0.0%      |12/100  |healthy\n"
        "product-service     |18% |44% |12ms       |0.0%      |8/100   |healthy"
    )
    timeline = (
        "09:30:00  payment-provider slow (maintenance)\n"
        "09:30:08  payment-service first timeout - aggressive retries NO BACKOFF\n"
        "09:30:13  Thread pool 48/50 blocked on retries\n"
        "09:30:20  Thread pool EXHAUSTED 50/50\n"
        "09:30:25  89 orders failed in 60s\n"
        "09:30:28  notification queue flooded\n"
        "09:30:35  sms-api rate limit exceeded"
    )
    return Scenario(
        task_id="cascading_failure", variant_id=0,
        scenario_name="Payment Retry Storm Cascade",
        severity="P1_critical",
        root_cause_service="payment-service",
        root_cause_category="code_bug",
        root_cause_keywords=["retry", "backoff", "thread", "pool", "exhaust", "storm", "no backoff"],
        remediation="enable_circuit_breaker",
        acceptable_remediations=["restart_service", "fix_config"],
        affected_services=["payment-service", "payment-provider", "order-service",
                           "notification-service", "email-api", "sms-api", "api-gateway"],
        incident_summary=(
            "ALERT [P1] payment-service: 98.2% error rate, threads exhausted\n"
            "ALERT [P1] order-service: 67% failure rate\n"
            "ALERT [P2] notification-svc: queue depth critical\n"
            "ALERT [P2] sms-api: rate limit exceeded\n"
            "Impact: Most orders failing. Notifications overwhelmed.\nOn-call: You"
        ),
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "Multiple services failing. Check timestamps to find the cascade origin.",
            "payment-provider is slow, but payment-service retries WITHOUT backoff.",
            "Root cause: payment-service retry logic (no backoff). Thread pool exhaustion cascaded everywhere.",
        ],
    )


def _build_task2_v1():
    """cache-service OOM causing DB overload cascade."""
    logs = "\n".join([
        f"[{_ts(11,0,0)}] cache-service    INFO   Memory: 3.2GB/4GB (80%) | hit_ratio=94%",
        f"[{_ts(11,5,0)}] cache-service    WARN   Memory: 3.8GB/4GB (95%) | hit_ratio=71%",
        f"[{_ts(11,8,0)}] cache-service    ERROR  OOM: maxmemory reached | hit_ratio=23%",
        f"[{_ts(11,8,2)}] cache-service    FATAL  OOMKilled by container runtime | limit=4GB",
        f"[{_ts(11,8,3)}] product-service  WARN   Cache MISS rate 98% | falling through to DB",
        f"[{_ts(11,8,5)}] product-db       WARN   Connections: 95/100 | query_queue=234 | avg=340ms",
        f"[{_ts(11,8,8)}] product-db       ERROR  Connection limit: 99/100 | slow_queries=156",
        f"[{_ts(11,8,10)}] product-service  ERROR  DB query timeout 5000ms",
        f"[{_ts(11,8,15)}] api-gateway      ERROR  product-service timeout 8900ms",
        f"[{_ts(11,8,20)}] order-service    WARN   Product lookup slow: 6s avg",
        f"[{_ts(11,8,22)}] user-service     INFO   Health check OK | latency_p99=14ms",
        f"[{_ts(11,8,22)}] auth-service     INFO   Health check OK | latency_p99=8ms",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|Status\n"
        "--------------------|----|----|-----------|----------|--------\n"
        "cache-service       |0%  |0%  |N/A        |100.0%    |DOWN (OOMKilled)\n"
        "product-service     |88% |72% |8900ms     |34.5%     |critical\n"
        "product-db          |96% |85% |5000ms+    |12.0%     |overloaded\n"
        "order-service       |35% |52% |6200ms     |8.3%      |degraded\n"
        "api-gateway         |42% |57% |9200ms     |18.4%     |degraded\n"
        "user-service        |14% |42% |14ms       |0.0%      |healthy\n"
        "auth-service        |9%  |39% |8ms        |0.0%      |healthy"
    )
    timeline = (
        "11:00:00  cache-service memory 80%, hit ratio 94%\n"
        "11:05:00  cache-service memory 95%, hit ratio 71%\n"
        "11:08:00  cache-service OOM, hit ratio 23%\n"
        "11:08:02  cache-service OOMKilled\n"
        "11:08:03  product-service cache miss rate 98%\n"
        "11:08:05  product-db overwhelmed (95/100 connections)\n"
        "11:08:15  api-gateway latency spikes to 9200ms"
    )
    return Scenario(
        task_id="cascading_failure", variant_id=1,
        scenario_name="Cache OOM → Database Overload Cascade",
        severity="P1_critical",
        root_cause_service="cache-service",
        root_cause_category="resource_exhaustion",
        root_cause_keywords=["OOM", "memory", "cache", "evict", "killed", "miss"],
        remediation="restart_service",
        acceptable_remediations=["increase_resources", "scale_horizontally"],
        affected_services=["cache-service", "product-service", "product-db", "order-service", "api-gateway"],
        incident_summary=(
            "ALERT [P1] cache-service: OOMKilled - DOWN\n"
            "ALERT [P1] product-service: 34.5% error rate, p99=8900ms\n"
            "ALERT [P2] product-db: overloaded (96% CPU)\n"
            "Impact: Product catalog slow/unavailable.\nOn-call: You"
        ),
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "Which service went DOWN first? Check the timeline.",
            "cache-service was OOMKilled. Without cache, all reads hit product-db.",
            "Root cause: cache-service OOM. Restart it to restore the cache layer.",
        ],
    )


def _build_task3_v0():
    """Slow memory leak in product-service after deployment with red herrings."""
    logs = "\n".join([
        f"[{_ts(8,0,0)}] product-service  INFO   Deployment v3.1.0 | commit=b7e2d41",
        f"[{_ts(8,0,5)}] product-service  INFO   Healthy | mem=512MB/2GB | p99=12ms | gc_avg=2ms",
        f"[{_ts(9,0,0)}] product-service  INFO   OK | mem=680MB/2GB | p99=18ms | gc_avg=4ms",
        f"[{_ts(10,0,0)}] product-service  INFO   OK | mem=890MB/2GB | p99=34ms | gc_avg=12ms",
        f"[{_ts(10,0,5)}] analytics-svc    WARN   Report slow: 45s (normal: 12s) <-- weekly spike, NOT related",
        f"[{_ts(11,0,0)}] product-service  INFO   OK | mem=1.2GB/2GB | p99=89ms | gc_avg=45ms",
        f"[{_ts(11,0,3)}] order-service    WARN   product-service slow: 234ms for GET /products/456",
        f"[{_ts(11,30,5)}] user-service     WARN   Unusual login: 3 fails from 10.0.0.45 <-- security scan, NOT related",
        f"[{_ts(12,0,0)}] product-service  WARN   Memory pressure: 1.6GB/2GB (80%) | gc every 8s | gc_avg=120ms",
        f"[{_ts(12,0,5)}] api-gateway      WARN   product-service p99=340ms > 200ms SLA",
        f"[{_ts(12,30,0)}] product-service  WARN   Memory: 1.8GB/2GB (90%) | p99=450ms | gc_avg=200ms",
        f"[{_ts(13,0,0)}] product-service  ERROR  GC overhead 42% time in GC | heap=1.92GB/2GB",
        f"[{_ts(13,0,3)}] product-service  WARN   Request queue: 89 pending (normal: 5) | avg=890ms",
        f"[{_ts(13,0,5)}] api-gateway      ERROR  product-service timeout | circuit_breaker=HALF_OPEN",
        f"[{_ts(13,0,8)}] order-service    WARN   12% product lookups failing",
        f"[{_ts(13,0,10)}] auth-service     INFO   Health check OK | p99=8ms",
        f"[{_ts(13,0,10)}] user-service     INFO   Health check OK | p99=14ms",
        f"[{_ts(13,0,10)}] payment-service  INFO   Health check OK | p99=82ms",
    ])
    metrics = (
        "Service             |CPU |Mem      |Latency_p99|Error_Rate|GC_Pause|Status\n"
        "--------------------|----|---------|-----------|---------  -|--------|--------\n"
        "product-service     |78% |96% ^^^  |890ms ^^^  |2.1%      |200ms   |critical\n"
        "api-gateway         |35% |54%      |890ms      |4.2%      |N/A     |degraded\n"
        "order-service       |29% |48%      |234ms      |12.0%     |N/A     |degraded\n"
        "analytics-svc       |45% |62%      |N/A        |0.0%      |N/A     |healthy\n"
        "user-service        |14% |42%      |14ms       |0.0%      |N/A     |healthy\n"
        "auth-service        |9%  |38%      |8ms        |0.0%      |N/A     |healthy\n"
        "payment-service     |12% |41%      |82ms       |0.0%      |N/A     |healthy\n\n"
        "TREND (product-service memory since deploy):\n"
        "  08:00  512MB  ████░░░░░░░░  25%\n"
        "  09:00  680MB  ██████░░░░░░  34%\n"
        "  10:00  890MB  ████████░░░░  45%\n"
        "  11:00  1.2GB  ██████████░░  60%\n"
        "  12:00  1.6GB  ████████████  80%\n"
        "  13:00  1.9GB  ████████████  96% <- current"
    )
    timeline = (
        "08:00  product-service deployed v3.1.0 - mem 512MB, p99 12ms\n"
        "09:00  mem: 680MB, p99: 18ms\n"
        "10:00  mem: 890MB, p99: 34ms\n"
        "10:00  [RED HERRING] analytics-svc report slow (normal weekly)\n"
        "11:00  mem: 1.2GB, p99: 89ms - order-service notices\n"
        "11:30  [RED HERRING] user-svc security scan alert\n"
        "12:00  mem: 1.6GB (80%), GC pauses 120ms, SLA breached\n"
        "13:00  mem: 1.92GB (96%), GC overhead 42%, circuit breaker tripped"
    )
    return Scenario(
        task_id="performance_degradation", variant_id=0,
        scenario_name="Memory Leak After Deployment",
        severity="P2_high",
        root_cause_service="product-service",
        root_cause_category="memory_leak",
        root_cause_keywords=["memory", "leak", "GC", "garbage", "heap", "growing", "v3.1.0", "gradual"],
        remediation="restart_service",
        acceptable_remediations=["rollback_deployment", "increase_resources"],
        affected_services=["product-service", "order-service", "api-gateway"],
        incident_summary=(
            "ALERT [P2] product-service: p99=890ms (SLA: 200ms)\n"
            "ALERT [P3] order-service: 12% product lookups failing\n"
            "ALERT [P3] analytics-svc: report slow (45s vs 12s normal)\n"
            "Duration: 5h+ (gradually worsening)\n"
            "Note: Multiple alerts - identify the root cause.\nOn-call: You"
        ),
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "Gradual degradation. Look at trends over time, not just current state.",
            "product-service memory climbed since 08:00 deploy. analytics-svc is a red herring.",
            "Memory leak in v3.1.0: 512MB->1.9GB in 5hrs causing GC pressure and latency.",
        ],
    )


def _build_task3_v1():
    """N+1 query regression after ORM refactor - no errors, just latency."""
    logs = "\n".join([
        f"[{_ts(14,0,0)}] order-service    INFO   Deployment v2.8.0 | changelog='ORM refactor'",
        f"[{_ts(14,0,5)}] order-service    INFO   Healthy | p99=45ms | queries=3/request",
        f"[{_ts(14,5,0)}] order-service    INFO   OK | p99=890ms | queries=234/s | NO ERRORS",
        f"[{_ts(14,5,2)}] order-db         WARN   Query rate: 2340/s (normal: 45/s) | SELECT on order_items",
        f"[{_ts(14,5,5)}] order-db         WARN   Connections: 88/100 | avg_query=23ms (normal: 2ms)",
        f"[{_ts(14,5,8)}] order-db         INFO   Slow query log: 156 queries>100ms | pattern: individual lookups",
        f"[{_ts(14,8,0)}] order-service    WARN   GET /api/orders/list: 2300ms (was 40ms) | correct data returned",
        f"[{_ts(14,8,5)}] api-gateway      WARN   order-service p99=3400ms for /api/orders/*",
        f"[{_ts(14,8,10)}] cache-service    INFO   Hit ratio 91% | normal operation",
        f"[{_ts(14,8,10)}] user-service     INFO   Health check OK | p99=14ms",
        f"[{_ts(14,8,10)}] product-service  INFO   Health check OK | p99=13ms",
        f"[{_ts(14,10,0)}] order-db         ERROR  Pool warning: 97/100 active",
        f"[{_ts(14,10,5)}] order-service    WARN   156 queries/request (was 3) - N+1 query pattern",
        f"[{_ts(14,10,8)}] order-service    INFO   v2.8.0 changed ORM from batch to individual entity loading",
    ])
    metrics = (
        "Service             |CPU |Mem |Latency_p99|Error_Rate|DB_QPS |Status\n"
        "--------------------|----|----|-----------|----------|-------|--------\n"
        "order-service       |71% |68% |3400ms ^^^ |0.0%      |2340   |degraded\n"
        "order-db            |92% |78% |23ms       |0.0%      |2340   |overloaded\n"
        "api-gateway         |32% |53% |3400ms     |0.3%      |N/A    |degraded\n"
        "product-service     |19% |44% |13ms       |0.0%      |8      |healthy\n"
        "user-service        |15% |42% |14ms       |0.0%      |5      |healthy\n"
        "cache-service       |16% |65% |2ms        |0.0%      |N/A    |healthy\n\n"
        "BEFORE/AFTER deploy:\n"
        "  Pre  v2.8.0: p99=45ms   QPS=45   queries/req=3\n"
        "  Post v2.8.0: p99=3400ms QPS=2340 queries/req=156"
    )
    timeline = (
        "14:00  order-service deployed v2.8.0 (ORM refactor)\n"
        "14:00  latency 45ms, 3 queries/request\n"
        "14:05  latency 890ms, DB queries 2340/s - NO ERRORS\n"
        "14:08  /api/orders/list: 2300ms (was 40ms)\n"
        "14:10  156 queries/request (was 3) - N+1 pattern confirmed"
    )
    return Scenario(
        task_id="performance_degradation", variant_id=1,
        scenario_name="N+1 Query Regression After ORM Refactor",
        severity="P2_high",
        root_cause_service="order-service",
        root_cause_category="deployment_regression",
        root_cause_keywords=["N+1", "query", "ORM", "deployment", "regression", "156", "batch"],
        remediation="rollback_deployment",
        acceptable_remediations=["restart_service"],
        affected_services=["order-service", "order-db", "api-gateway"],
        incident_summary=(
            "ALERT [P2] order-service: p99=3400ms (SLA: 200ms)\n"
            "ALERT [P3] order-db: CPU 92%, connection pool near capacity\n"
            "Impact: Order listing extremely slow. No hard errors.\n"
            "Note: v2.8.0 deployed at 14:00.\nOn-call: You"
        ),
        service_topology=ECOMMERCE_TOPOLOGY,
        log_entries=logs, metrics_snapshot=metrics, timeline=timeline,
        hints=[
            "No errors anywhere. What changed recently?",
            "v2.8.0 deployed at 14:00. Query rate went from 45/s to 2340/s.",
            "N+1 pattern: 156 individual queries per request instead of 3 batch queries. Rollback.",
        ],
    )


# ═══════════════════════════════════════════════════════════════════════
#  Registry
# ═══════════════════════════════════════════════════════════════════════

_TASK_VARIANTS = {
    "single_service_failure": [_build_task1_v0, _build_task1_v1, _build_task1_v2],
    "cascading_failure": [_build_task2_v0, _build_task2_v1],
    "performance_degradation": [_build_task3_v0, _build_task3_v1],
}


def generate_scenario(task_id: str, seed: int = 42) -> Scenario:
    """Generate a deterministic scenario. seed % num_variants selects the variant."""
    if task_id not in _TASK_VARIANTS:
        raise ValueError(f"Unknown task_id: {task_id}. Must be one of {TASK_IDS}")
    builders = _TASK_VARIANTS[task_id]
    return builders[seed % len(builders)]()


def get_task_description(task_id: str) -> str:
    """Human-readable task instructions for the agent."""
    descs = {
        "single_service_failure": (
            "You are an on-call SRE. A single service has failed.\n"
            "Identify: severity, root cause service, failure category,\n"
            "what went wrong, remediation, and all affected services."
        ),
        "cascading_failure": (
            "You are an on-call SRE. Multiple services are failing due to a cascade.\n"
            "Only ONE is the root cause. Trace the cascade back.\n"
            "IMPORTANT: Don't mistake a SYMPTOM for the root cause."
        ),
        "performance_degradation": (
            "You are an on-call SRE investigating subtle performance degradation.\n"
            "No explicit errors. Some alerts are RED HERRINGS.\n"
            "Look at TRENDS, not just current state. Correlate timestamps."
        ),
    }
    return descs.get(task_id, "Unknown task.")
