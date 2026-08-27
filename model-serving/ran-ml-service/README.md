# ran-ml-service

Mantis time-series ML predictor for TelecomTS anomaly detection (TASK=detect) and root cause analysis (TASK=classify).

## Endpoints

- `POST /v1/detect` — Binary anomaly detection on a 128x18 KPI window
- `GET /health` — Liveness probe
- `GET /ready` — Readiness probe (model loaded)

## Configuration

| Env Var | Description |
|---------|-------------|
| `TASK` | `detect` or `classify` |
| `MANTIS_MODEL_PATH` | Local path to `.pt` weights file |
| `MLFLOW_MODEL_URI` | MLflow model URI (alternative to local path) |
| `PORT` | HTTP port (default: 8080) |
