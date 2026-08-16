# RAN Frontend — Telco O-RAN Anomaly Dashboard

React webapp for the Telco/O-RAN anomaly detection use case. Polls `ran-chatbot-service` for
recently detected RAN cell anomalies and lets an operator chat about them in natural language.

This is an independent, standalone webapp — a twin of [`hub/frontend`](../frontend/FRONTEND.md)
(the NOC dashboard) built the same way, against a different (thinner) BFF: separate codebase,
separate Helm Deployment/Service/Route, own `ranFrontend.enabled` toggle, no shared runtime code
path with `hub/frontend` or `hub/chatbot-service`.

## Quick Start

```bash
# Terminal 1: port-forward the RAN chatbot BFF
oc port-forward -n hub svc/hub-ran-chatbot-service 8008:8003

# Terminal 2: run the dev server
cd hub/ran-frontend
npm install
npm run dev
# Open http://localhost:5174
```

The Vite dev server proxies `/api/*` to `localhost:8008` automatically.

## Tech Stack

- React 19 + Vite 6
- Plain CSS (dark, telecom-purple theme)
- nginx (production container)
- No external UI framework, no router

## Architecture

```
┌──────────────┐       /api/*        ┌──────────────────────┐
│   Browser    │ ───────────────────► │  nginx (ran-frontend) │
│  React SPA   │                      │  proxy to BFF          │
└──────────────┘                      └────────┬───────────────┘
                                                │
                                                ▼
                                       ┌──────────────────────┐
                                       │ ran-chatbot-service   │
                                       │ (FastAPI BFF)         │
                                       └──────────────────────┘
```

In development, Vite's built-in proxy replaces nginx.

## BFF Endpoints Consumed

| Endpoint | Method | Interval | What it drives |
|----------|--------|----------|----------------|
| `/api/anomalies` | GET | 10s poll (4s for ~75s after a demo trigger; an immediate refetch after Clear) | Header metrics, anomaly list panel |
| `/api/anomalies` | DELETE | User action | "Clear" button on the anomaly list panel |
| `/api/chat` | POST | User action | Chat panel |
| `/api/demo/trigger` | POST | User action | Demo Mode panel |

`ran-chatbot-service` is deliberately thin — it has no `/api/summary` or `/api/integrations`
equivalent, so this webapp has no matching panels either. See
[`docs/telco-oran-anomaly-detection.md`](../../docs/telco-oran-anomaly-detection.md) for the full
picture of what feeds `ran-chatbot-service`, and
[`docs/RAN-DEMO-SCRIPT.md`](../../docs/RAN-DEMO-SCRIPT.md) for a full demo-recording walkthrough
of the Demo Mode panel.

### Dependency status (`_deps`)

Both BFF endpoints include a `_deps` field, same convention as `hub/frontend`:

```jsonc
// Kafka connected — anomaly data is live
{ "_deps": { "status": "ok" }, "count": 2, "anomalies": [...] }

// Kafka unreachable — buffer may be stale/empty
{ "_deps": { "status": "degraded", "unavailable": ["kafka"] }, "count": 0, "anomalies": [] }
```

`_deps.status === "degraded"` shows an amber banner at the top of the page, and the header's
"Kafka Feed" metric switches to "Unavailable". `/api/chat` can additionally report `llm`
unavailable if the model endpoint is unreachable — that's annotated inline on the affected chat
reply instead.

### Clearing the anomaly list

The "Clear" button on the anomaly panel calls `DELETE /api/anomalies`, which empties
`ran-chatbot-service`'s in-memory buffer immediately. This is a process-local reset, not a
database delete: it does **not** survive a `ran-chatbot-service` restart or Kafka reconnect, since
the buffer re-seeds itself from the last ~50 messages on `ran-anomalies-enriched` (7-day retention)
every time it (re)connects. Useful for getting a clean slate before a demo recording — see
[`docs/RAN-DEMO-SCRIPT.md`](../../docs/RAN-DEMO-SCRIPT.md).

## Project Structure

```
hub/ran-frontend/
├── package.json          # Dependencies (react, vite)
├── vite.config.js        # Dev server + API proxy
├── index.html            # SPA entry
├── Containerfile         # Multi-stage build (node → nginx)
├── nginx.conf            # Reverse proxy for /api/* -> hub-ran-chatbot-service
└── src/
    ├── main.jsx          # React root
    ├── App.jsx           # Layout orchestrator
    ├── styles.css        # Dark, purple-accented theme
    ├── hooks/
    │   └── usePolling.js # Polls /api/anomalies; exposes speedUpPolling() + refetchNow()
    └── components/
        ├── ErrorBoundary.jsx  # Render-error fallback
        ├── DegradedBanner.jsx # Amber banner for _deps.status: "degraded"
        ├── HeaderMetrics.jsx  # Anomalies tracked, cells affected, Kafka status
        ├── DemoTrigger.jsx    # Demo Mode: inject a synthetic reading into the real pipeline
        ├── AnomalyTable.jsx   # Recent anomalies + "Clear" button (DELETE /api/anomalies)
        └── ChatPanel.jsx      # RAN chat, parses the reply's Summary/Root Cause/
                                #   Recommended Fix/Model Output sections
```

## Build & Deploy

```bash
# Build container image
make build-ran-frontend-image

# Push to registry
podman push quay.io/rh-ai-quickstart/noc-ran-frontend:0.1.5

# Deploy with Helm, turning on the RAN demo stack (detector + this webapp)
make helm-install ENABLE_RAN_ANOMALY=true
```

The Helm chart creates a Deployment, Service, and OpenShift Route with TLS edge termination,
gated behind `ranFrontend.enabled` (default `false`, same as `ranAnomalyDetector.enabled`) so a
fresh install doesn't deploy a webapp with an empty dashboard and a demo trigger that has no
visible effect. `make ... ENABLE_RAN_ANOMALY=true` enables both together; it can still be toggled
independently via `--set ranFrontend.enabled=true/false`.

## Environment Variables

| Variable | Where | Purpose |
|----------|-------|---------|
| `VITE_RAN_CHATBOT_URL` | Dev only | Override BFF target (default: relative `/api/*`) |

In production, nginx handles the proxy — no env vars needed at runtime.
