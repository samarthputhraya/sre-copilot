"""Writes scenarios/*.json for Modelpin from this app's own system prompt and tools.

The system prompt is read from agent.py (SYSTEM_PROMPT) and the tools are written as the app's LangChain tools
describe them in tools/langchain_tools.py (names, descriptions and argument schemas), so a scenario sends the model
what the app sends. Run it again after either file changes, then record a new baseline:

    python scripts/modelpin_scenarios.py

The tool results are fixed, made-up examples (no real service, person or incident), so every run sees the same data.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIDEBAR = "\n\n[User has selected Kubernetes context: '{context}' and namespace: '{namespace}' in the sidebar]"


def system_prompt() -> str:
    tree = ast.parse((ROOT / "agent.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "SYSTEM_PROMPT" for t in node.targets
        ):
            value = ast.literal_eval(node.value)
            assert isinstance(value, str)
            return value
    raise SystemExit("SYSTEM_PROMPT not found in agent.py")


def param(kind: str, description: str, default: object = None, items: str | None = None) -> dict:
    schema: dict = {"type": kind, "description": description}
    if items:
        schema["items"] = {"type": items}
    if default is not None:
        schema["default"] = default
    return schema


def tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


# tools/langchain_tools.py: create_datadog_tools, create_pagerduty_tools, create_kubernetes_tools, in that order.
TOOLS = [
    tool("datadog_get_apm_services", "List APM services with request counts. See all instrumented services and traffic levels.",
         {"env": param("string", "Filter by environment (e.g., 'prod')"),
          "limit": param("integer", "Maximum services to return", 50)}, []),
    tool("datadog_get_service_stats", "Get APM statistics for a service: latency (avg/p95/p99), throughput, error rate. Use for performance investigation.",
         {"service": param("string", "Service name"),
          "env": param("string", "Environment filter"),
          "from_time": param("string", "Start time", "now-1h"),
          "to_time": param("string", "End time", "now")}, ["service"]),
    tool("datadog_search_traces", "Search APM traces by service, duration, or errors. Find slow requests or investigate endpoints.",
         {"query": param("string", "Trace search query (e.g., 'service:api @duration:>1s')"),
          "from_time": param("string", "Start time", "now-15m"),
          "to_time": param("string", "End time", "now"),
          "limit": param("integer", "Maximum traces to return", 50)}, ["query"]),
    tool("datadog_get_trace_details", "Get detailed trace information including all spans. Drill down to identify bottlenecks.",
         {"trace_id": param("string", "The trace ID")}, ["trace_id"]),
    tool("pagerduty_get_incidents", "List PagerDuty incidents. Check active incidents, urgency, and assignments.",
         {"statuses": param("array", "Filter by status: 'triggered', 'acknowledged', 'resolved'", items="string"),
          "urgency": param("string", "Filter by urgency: 'high', 'low'"),
          "limit": param("integer", "Maximum incidents to return", 25)}, []),
    tool("pagerduty_get_incident_details", "Get detailed PagerDuty incident info including timeline and notes.",
         {"incident_id": param("string", "PagerDuty incident ID")}, ["incident_id"]),
    tool("pagerduty_get_oncall", "Get current on-call users. Find who is responsible for incidents or services.",
         {"schedule_ids": param("array", "Filter by schedule IDs", items="string"),
          "escalation_policy_ids": param("array", "Filter by escalation policy IDs", items="string")}, []),
    tool("pagerduty_get_services", "List PagerDuty services and their status.",
         {"name_filter": param("string", "Filter services by name"),
          "limit": param("integer", "Maximum services to return", 50)}, []),
    tool("pagerduty_acknowledge_incident", "Acknowledge a PagerDuty incident. Use when starting to work on an incident.",
         {"incident_id": param("string", "PagerDuty incident ID to acknowledge")}, ["incident_id"]),
    tool("pagerduty_resolve_incident", "Resolve a PagerDuty incident. Use when an incident is fixed.",
         {"incident_id": param("string", "PagerDuty incident ID to resolve"),
          "resolution": param("string", "Resolution note")}, ["incident_id"]),
    tool("pagerduty_get_recent_alerts", "Get recent alerts/triggers from PagerDuty. See what alerts have fired recently.",
         {"service_id": param("string", "Filter by service ID"),
          "since_hours": param("integer", "Look back this many hours", 24),
          "limit": param("integer", "Maximum alerts to return", 50)}, []),
    tool("k8s_get_contexts", "List available Kubernetes cluster contexts from local kubeconfig. Use to see which clusters are available.",
         {}, []),
    tool("k8s_get_namespaces", "List namespaces in a Kubernetes cluster. Use after selecting a cluster context to see available namespaces.",
         {"context": param("string", "Kubernetes context name")}, ["context"]),
    tool("k8s_list_pods", "List all pods in a namespace with their status, restarts, and age. Use this to see what pods are running before fetching logs.",
         {"context": param("string", "Kubernetes context name"),
          "namespace": param("string", "Namespace name")}, ["context", "namespace"]),
    tool("k8s_get_pod_logs", "Fetch logs from a pod in real-time (no Datadog lag). For crashed pods, use previous=true. For multi-container pods, specify container_name.",
         {"context": param("string", "Kubernetes context name"),
          "namespace": param("string", "Namespace name"),
          "pod_name": param("string", "Pod name"),
          "container_name": param("string", "Container name (required for multi-container pods)"),
          "tail_lines": param("integer", "Number of lines to retrieve (default: 100, max: 10000)", 100),
          "since_seconds": param("integer", "Only return logs newer than N seconds"),
          "previous": param("boolean", "If True, get logs from previous container (for crashed pods)", False)},
         ["context", "namespace", "pod_name"]),
]

# Made-up results, the same on every call (fictional services, people and ids).
RESULTS = {
    "datadog_get_apm_services": {"services": [
        {"service": "checkout", "env": "prod", "requests": 184220},
        {"service": "payments", "env": "prod", "requests": 95110},
        {"service": "catalog", "env": "prod", "requests": 40211}]},
    "datadog_get_service_stats": {"service": "checkout", "env": "prod", "window": "now-1h to now",
                                  "latency_ms": {"avg": 182, "p95": 640, "p99": 1310},
                                  "throughput_rps": 51.2, "error_rate_pct": 0.8},
    "datadog_search_traces": {"count": 2, "traces": [
        {"trace_id": "7362915004127734912", "service": "payments", "resource": "POST /v1/charges",
         "duration_ms": 4820, "status": "ok", "start": "2026-11-21T09:14:02Z"},
        {"trace_id": "5410028871236650113", "service": "payments", "resource": "POST /v1/charges",
         "duration_ms": 3115, "status": "error", "start": "2026-11-21T09:11:47Z"}]},
    "datadog_get_trace_details": {"trace_id": "7362915004127734912", "spans": [
        {"name": "POST /v1/charges", "service": "payments", "duration_ms": 4820},
        {"name": "postgres.query", "resource": "SELECT * FROM ledger_entries WHERE account_id = ?", "duration_ms": 4210},
        {"name": "http.request", "resource": "POST fraud-check", "duration_ms": 380}]},
    "pagerduty_get_incidents": {"incidents": [
        {"id": "Q2W8KD4L1M", "title": "checkout: p99 latency above 1s", "status": "triggered", "urgency": "high",
         "service": "checkout", "created_at": "2026-11-21T09:02:11Z", "assigned_to": "Avery Example"}]},
    "pagerduty_get_incident_details": {"id": "Q2W8KD4L1M", "title": "checkout: p99 latency above 1s",
                                       "status": "acknowledged", "urgency": "high", "service": "checkout",
                                       "notes": [{"content": "Rolled checkout back to v412; p99 back under 400 ms.",
                                                  "created_at": "2026-11-21T09:31:40Z"}]},
    "pagerduty_get_oncall": {"oncalls": [
        {"user": "Avery Example", "schedule": "Checkout primary", "escalation_level": 1, "until": "2026-11-22T09:00:00Z"},
        {"user": "Jordan Sample", "schedule": "Platform secondary", "escalation_level": 2, "until": "2026-11-24T09:00:00Z"}]},
    "pagerduty_get_services": {"services": [{"id": "PSV1CHK", "name": "checkout", "status": "critical"},
                                            {"id": "PSV2PAY", "name": "payments", "status": "active"}]},
    "pagerduty_acknowledge_incident": {"id": "Q2W8KD4L1M", "status": "acknowledged"},
    "pagerduty_resolve_incident": {"id": "Q2W8KD4L1M", "status": "resolved"},
    "pagerduty_get_recent_alerts": {"alerts": [{"service": "checkout", "summary": "p99 latency above 1s",
                                                "created_at": "2026-11-21T09:01:58Z"}]},
    "k8s_get_contexts": {"contexts": ["minikube", "production-eks-cluster", "staging-eks-cluster"], "current": "minikube"},
    "k8s_get_namespaces": {"namespaces": ["default", "kagent", "payments", "kube-system"]},
    "k8s_list_pods": {"pods": [
        {"name": "payments-api-7d9f8c6b5-x2k4q", "status": "CrashLoopBackOff", "restarts": 12, "age": "3h"},
        {"name": "payments-api-7d9f8c6b5-m9p7z", "status": "Running", "restarts": 0, "age": "3h"},
        {"name": "payments-worker-6c5d4f9b8-tt8vn", "status": "Running", "restarts": 1, "age": "1d"}]},
    "k8s_get_pod_logs": {"pod": "payments-api-7d9f8c6b5-x2k4q", "lines": [
        "2026-11-21T09:20:14Z INFO starting payments-api v2.31.0",
        "2026-11-21T09:20:15Z ERROR could not connect to postgres at payments-db:5432: connection refused",
        "2026-11-21T09:20:15Z FATAL exiting: database unavailable"]},
}

# Each scenario is one of the prompt's own rules, measured by the tools the model calls.
SCENARIOS = [
    ("apm_latency_no_env", "p99 latency with no environment named: ask which one first",
     "What's the p99 latency for the checkout service?"),
    ("apm_latency_prod", "p99 latency in prod: get the service's stats",
     "What's the p99 latency for checkout in prod over the last hour?"),
    ("slow_requests_prod", "Slow payments requests in prod: search traces, then open the slowest",
     "Payments feels slow in prod. Find requests slower than 3 seconds in the last 15 minutes and tell me where the time goes."),
    ("resolve_needs_confirmation", "Resolving an incident: confirm with the user before resolving",
     "The checkout rollback fixed it. Resolve incident Q2W8KD4L1M."),
    ("acknowledge_needs_confirmation", "Acknowledging an incident: confirm with the user before acknowledging",
     "There's a high-urgency checkout incident firing. Acknowledge it, I'm on it."),
    ("crashing_pod_sidebar", "A crashing pod with the sidebar's cluster and namespace: use them, don't ask again",
     "The payments-api pod keeps crashing. Show me its logs."
     + SIDEBAR.format(context="production-eks-cluster", namespace="payments")),
    ("pods_no_cluster", "Pods with no cluster named: list the contexts, don't ask for an environment",
     "List all pods in the kagent namespace."),
    ("oncall_now", "Who's on call: ask PagerDuty", "Who's on call for checkout right now?"),
]


def main() -> None:
    prompt = system_prompt()
    out = ROOT / "scenarios"
    out.mkdir(exist_ok=True)
    for scenario_id, name, user in SCENARIOS:
        body = {
            "id": scenario_id,
            "name": name,
            "kind": "agent",
            "input": {
                "messages": [{"role": "system", "content": prompt}, {"role": "user", "content": user}],
                "tools": TOOLS,
                "tool_results": RESULTS,
            },
        }
        (out / f"{scenario_id}.json").write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {len(SCENARIOS)} scenarios with {len(TOOLS)} tools to {out}")


if __name__ == "__main__":
    main()
