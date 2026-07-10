# ${{ values.serviceName }}

${{ values.description }}

| | |
|---|---|
| Owner | ${{ values.owner }} |
| Tier | ${{ values.tier }} |
| Cost driver | ${{ values.primaryCostDriver }} |

Part of the **PixelShop** demo environment monitored by Spend Detective.

## Run locally

```bash
docker build -t ${{ values.serviceName }} .
docker run -p 8080:8080 ${{ values.serviceName }}
```

- `GET /healthz` — liveness
- `GET /readyz` — readiness, reports cache state
- `POST /work` — the service's main operation
- `GET /metrics` — Prometheus metrics, scraped by the billing exporter

## Cost metering

Every request records CPU-seconds and billable units. The billing exporter
multiplies these by a price sheet to produce cost per service per hour.

{%- if values.usesCache %}

## Demo sabotage switch

Set `CACHE_ENABLED=false` and restart. Every request now does full work
instead of reading from cache, tripling CPU cost. This is the anomaly
Spend Detective is built to catch.
{%- endif %}

## Where to add your logic

Replace `_expensive_operation()` in `app/main.py`. Keep the metering calls.

