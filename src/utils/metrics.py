from prometheus_client import Counter, Histogram

# --- REST API HTTP metrics ---
api_requests_total = Counter(
    "api_requests_total",
    "Total API requests processed",
    ["endpoint", "method", "status"]
)

api_request_duration_seconds = Histogram(
    "api_request_duration_seconds",
    "API request processing time in seconds",
    ["endpoint"]
)

# --- Specialist Agent metrics ---
agent_success_total = Counter(
    "agent_success_total",
    "Successful executions of specialist travel agents",
    ["agent_name"]
)

agent_failure_total = Counter(
    "agent_failure_total",
    "Failed executions of specialist travel agents",
    ["agent_name"]
)
