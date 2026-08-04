"""
RAN Chatbot Entrypoint (Telco O-RAN)
=====================================
Thin conversational BFF for the Telco O-RAN anomaly detection and root cause
analysis use case. Delegates all domain logic (anomaly detection, root cause
analysis, recommended fix retrieval) to upstream services — this service only
handles the conversational interface and reply formatting.

Anomaly data is currently backed by a stub (see kafka.py) pending the
ran-rca-service that will publish enriched anomalies to the
`ran-anomalies-enriched` Kafka topic.

Endpoints:
  GET  /health   - Liveness probe
  GET  /ready     - Readiness probe (Kafka + LLM dependency status)
  POST /api/chat  - RAN anomaly chat backed by an LLM with anomaly context
"""

from __future__ import annotations

import logging
import socket

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .chat import build_chat_context, call_model, format_chat_reply
from .config import APP_VERSION, CORS_ORIGINS, KAFKA_BOOTSTRAP, MODEL_API_URL, MODEL_NAME
from .kafka import fetch_recent_anomalies
from .probes import probe_http
from .utils import build_deps, normalize_session_id, utc_now

logger = logging.getLogger(__name__)

# ── App State ─────────────────────────────────────────────────────
MAX_CHAT_SESSIONS = 100
chat_sessions: dict[str, list[dict[str, str]]] = {}

app = FastAPI(
    title="RAN Chatbot BFF",
    version=APP_VERSION,
    description="Thin conversational entrypoint for the Telco O-RAN anomaly detection and root cause analysis use case",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response Models ───────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(max_length=1000)
    session_id: str | None = None


# ── Endpoints ─────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ran-chatbot-bff", "version": APP_VERSION}


@app.get("/ready")
async def ready():
    """Readiness probe — reports dependency status but always passes.

    The BFF gracefully degrades when dependencies are unavailable (fallback
    chat, anomaly stub), so it can always serve useful traffic. Dependency
    status is informational.
    """
    checks: dict[str, bool] = {}

    try:
        host, port = KAFKA_BOOTSTRAP.split(",")[0].rsplit(":", 1)
        sock = socket.create_connection((host, int(port)), timeout=2)
        sock.close()
        checks["kafka"] = True
    except OSError:
        checks["kafka"] = False

    llm_probe = await probe_http(MODEL_API_URL, timeout=2.0)
    checks["llm"] = llm_probe["reachable"]

    return {"status": "ready", "checks": checks}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    msg = req.message.strip()
    if not msg:
        return {"reply": "Please enter a question.", "session_id": normalize_session_id(req.session_id)}

    session_id = normalize_session_id(req.session_id)
    if session_id not in chat_sessions and len(chat_sessions) >= MAX_CHAT_SESSIONS:
        oldest = next(iter(chat_sessions))
        del chat_sessions[oldest]
    history = chat_sessions.setdefault(session_id, [])

    anomalies, kafka_ok = fetch_recent_anomalies()

    prompt = build_chat_context(msg, anomalies, history)
    raw_reply, model_source = await call_model(prompt)
    reply = format_chat_reply(msg, raw_reply, anomalies)

    history.append({"role": "user", "content": msg})
    history.append({"role": "assistant", "content": reply})
    if len(history) > 20:
        del history[:-20]

    # Anything other than a genuine live reply (unreachable, disabled, empty, or an
    # http-<code> error) means the operator got a deterministic fallback, not a real
    # model answer, so it should be surfaced as degraded rather than "ok".
    llm_ok = model_source == "live"
    _deps = build_deps({"kafka": kafka_ok, "llm": llm_ok})

    return {
        "_deps": _deps,
        "session_id": session_id,
        "timestamp": utc_now(),
        "reply": reply,
        "model": {
            "name": MODEL_NAME,
            "source": model_source,
        },
        "context": {
            "anomaly_count": len(anomalies),
        },
    }


# ── Entrypoint ────────────────────────────────────────────────────


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8003)
