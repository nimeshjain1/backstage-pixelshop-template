"""${{ values.serviceName }} — ${{ values.description }}

Cost driver: ${{ values.primaryCostDriver }}
Scaffolded from the pixelshop-python-service template.
"""

import os
import time

from fastapi import FastAPI
from prometheus_client import Counter, Histogram, make_asgi_app

SERVICE_NAME = "${{ values.serviceName }}"
COST_DRIVER = "${{ values.primaryCostDriver }}"

# The sabotage switch. Flip to "false" during the demo and watch compute cost climb.
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"

app = FastAPI(title=SERVICE_NAME, description="${{ values.description }}")

# --- Metering -------------------------------------------------------------
# The billing exporter scrapes these. Every metric here is a line item on the
# homemade cloud bill: usage x price sheet = cost.

requests_total = Counter(
    "pixelshop_requests_total",
    "Requests handled",
    ["service", "endpoint", "status"],
)
work_seconds = Histogram(
    "pixelshop_work_seconds",
    "CPU-bound work per request, in seconds. Priced per CPU-hour.",
    ["service", "operation"],
)
billable_units = Counter(
    "pixelshop_billable_units_total",
    "Countable billable events: DB queries, stored bytes, API calls.",
    ["service", "unit"],
)
cache_lookups = Counter(
    "pixelshop_cache_lookups_total",
    "Cache hits and misses. A collapsing hit rate is the tell for a cost anomaly.",
    ["service", "result"],
)

app.mount("/metrics", make_asgi_app())

# --- Clients --------------------------------------------------------------
{%- if values.usesDatabase %}
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pixelshop:pixelshop@postgres:5432/pixelshop")
{%- endif %}
{%- if values.usesCache %}
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

_cache: dict[str, bytes] = {}


def cache_get(key: str) -> bytes | None:
    if not CACHE_ENABLED:
        cache_lookups.labels(SERVICE_NAME, "disabled").inc()
        return None
    hit = _cache.get(key)
    cache_lookups.labels(SERVICE_NAME, "hit" if hit else "miss").inc()
    return hit


def cache_set(key: str, value: bytes) -> None:
    if CACHE_ENABLED:
        _cache[key] = value
{%- endif %}


# --- Health ---------------------------------------------------------------

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": SERVICE_NAME}


@app.get("/readyz")
def readyz():
    return {"status": "ready", "service": SERVICE_NAME, "cache_enabled": CACHE_ENABLED}


# --- Business logic -------------------------------------------------------
# Replace the body of do_work() with what this service actually does.
# Keep the metering calls: they are what makes the service visible to
# Spend Detective.

@app.post("/work")
def do_work(key: str = "default"):
    started = time.perf_counter()

{%- if values.usesCache %}
    cached = cache_get(key)
    if cached is not None:
        requests_total.labels(SERVICE_NAME, "/work", "200").inc()
        work_seconds.labels(SERVICE_NAME, "cached").observe(time.perf_counter() - started)
        return {"result": "from-cache", "service": SERVICE_NAME}
{%- endif %}

    # --- expensive work goes here ---
    result = _expensive_operation(key)
    # --------------------------------

{%- if values.usesCache %}
    cache_set(key, result)
{%- endif %}

{%- if values.primaryCostDriver == "database" %}
    billable_units.labels(SERVICE_NAME, "db_query").inc()
{%- elif values.primaryCostDriver == "storage" %}
    billable_units.labels(SERVICE_NAME, "stored_bytes").inc(len(result))
{%- elif values.primaryCostDriver == "third_party_api" %}
    billable_units.labels(SERVICE_NAME, "api_call").inc()
{%- endif %}

    requests_total.labels(SERVICE_NAME, "/work", "200").inc()
    work_seconds.labels(SERVICE_NAME, "computed").observe(time.perf_counter() - started)
    return {"result": "computed", "service": SERVICE_NAME}


def _expensive_operation(key: str) -> bytes:
    """Stand-in for real work. Burns CPU so the meter reads something honest."""
    acc = 0
    for i in range(2_000_000):
        acc = (acc + i * i) % 1_000_003
    return f"{key}:{acc}".encode()
