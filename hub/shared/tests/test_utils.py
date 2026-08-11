"""Unit tests for utils.py: dependency envelope, session id normalization, timestamps."""

from datetime import datetime

from shared.utils import build_deps, normalize_session_id, utc_now


class TestUtcNow:
    def test_returns_iso_formatted_utc_timestamp(self):
        value = utc_now()
        parsed = datetime.fromisoformat(value)
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0


class TestNormalizeSessionId:
    def test_returns_provided_id(self):
        assert normalize_session_id("session-123") == "session-123"

    def test_strips_whitespace(self):
        assert normalize_session_id("  session-123  ") == "session-123"

    def test_generates_id_when_missing(self):
        assert normalize_session_id(None)

    def test_generates_id_when_blank(self):
        assert normalize_session_id("   ")


class TestBuildDeps:
    def test_all_ok(self):
        assert build_deps({"kafka": True, "servicenow": True}) == {"status": "ok"}

    def test_empty_checks(self):
        assert build_deps({}) == {"status": "ok"}

    def test_single_failure(self):
        result = build_deps({"kafka": True, "servicenow": False})
        assert result == {"status": "degraded", "unavailable": ["servicenow"]}

    def test_multiple_failures_sorted(self):
        result = build_deps({"llm": False, "kafka": False, "probes": True})
        assert result == {"status": "degraded", "unavailable": ["kafka", "llm"]}

    def test_all_down(self):
        result = build_deps({"kafka": False, "servicenow": False})
        assert result == {"status": "degraded", "unavailable": ["kafka", "servicenow"]}
