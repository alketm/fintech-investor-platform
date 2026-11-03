import json
import stat
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from alko_backend import audit as audit_module
from alko_backend.audit import AuditStore, RequestAudit, estimate_cost, summarize_usage

from .conftest import fake_response, text_block, thinking_block


def tokens(input=0, output=0, cache_read=0, cache_write=0):
    return {
        "input_tokens": input,
        "output_tokens": output,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
    }


def usage(input=0, output=0, cache_read=0, cache_write=0, **extra):
    return SimpleNamespace(
        input_tokens=input,
        output_tokens=output,
        cache_read_input_tokens=cache_read,
        cache_creation_input_tokens=cache_write,
        **extra,
    )


@pytest.fixture
def store(tmp_path):
    store = AuditStore(tmp_path / "audit" / "audit.db")
    store.init()
    return store


def _saved(store, agent="advisor", started_at=None, model="claude-opus-5-5", question="How is AAPL?"):
    audit = RequestAudit(agent=agent, question=question)
    if started_at:
        audit.started_at = started_at
    audit.guardrail = {"outcome": "answer", "category": "in_scope", "source": "classifier", "reason": "ok"}
    response = fake_response([thinking_block("Think."), text_block("Hi")], "end_turn", model)
    audit.record_model_call(agent, 0, 0, "claude-opus-5-5", response, 12)
    audit.record_tool_call(agent, 0, "get_quote", "mcp_stocks", {"symbol": "AAPL"}, "{}", False, False, 3)
    audit.finish("Hi", "ok")
    store.save(audit)
    return audit


@pytest.mark.parametrize(
    "counts, expected",
    [
        (tokens(input=1_000_000), 4.00),
        (tokens(output=1_000_000), 20.00),
        (tokens(cache_read=1_000_000), 0.20),
        (tokens(cache_write=1_000_000), 5.00),
        (tokens(input=1000, output=500, cache_read=2000, cache_write=400), 0.004 + 0.01 + 0.0004 + 0.002),
    ],
)
def test_estimate_cost_by_token_type(counts, expected):
    assert estimate_cost("claude-opus-5-5", counts) == pytest.approx(expected)


def test_unknown_model_has_no_cost_rather_than_zero():
    assert estimate_cost("claude-unknown", tokens(input=1000)) is None
    assert estimate_cost(None, tokens(input=1000)) is None


def test_fallback_prices_each_attempt_at_its_own_model():
    iterations = [
        SimpleNamespace(type="message", model="claude-opus-5-5", **vars(usage(output=1_000_000))),
        SimpleNamespace(type="fallback_message", model="claude-sonnet-5-5", **vars(usage(output=1_000_000))),
    ]
    summary = summarize_usage(usage(output=1_000_000, iterations=iterations), "claude-sonnet-5-5")
    assert summary["output_tokens"] == 2_000_000  # top-level usage covers only the returned attempt
    assert summary["est_cost_usd"] == pytest.approx(20.00 + 10.00)


def test_unknown_model_in_any_attempt_leaves_cost_unpriced():
    iterations = [
        SimpleNamespace(type="message", model="claude-opus-5-5", **vars(usage(output=1000))),
        SimpleNamespace(type="fallback_message", model="claude-unknown", **vars(usage(output=1000))),
    ]
    assert summarize_usage(usage(iterations=iterations), "claude-unknown")["est_cost_usd"] is None


def test_fallback_is_flagged_on_the_model_call():
    response = fake_response([text_block("Hi")], "end_turn", "claude-sonnet-5-5")
    response.usage = usage(
        output=10, iterations=[SimpleNamespace(type="fallback_message", **vars(usage(output=10)))]
    )
    audit = RequestAudit(agent="advisor", question="?")
    audit.record_model_call("advisor", 0, 0, "claude-opus-5-5", response, 1)
    call = audit.model_calls[0]
    assert call["fallback_used"] is True and call["served_model"] == "claude-sonnet-5-5"
    assert call["requested_model"] == "claude-opus-5-5"


def test_database_is_owner_only(store):
    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


def test_save_and_get_full_record(store):
    audit = _saved(store)
    record = store.get(audit.id)
    assert record["question"] == "How is AAPL?" and record["reply"] == "Hi" and record["status"] == "ok"
    assert record["guardrail_outcome"] == "answer" and record["duration_ms"] >= 0
    assert record["model_calls"][0]["thinking"] == "Think."
    assert record["model_calls"][0]["api_request_id"] == "req_test"
    assert record["tool_calls"][0]["input"] == '{"symbol": "AAPL"}'
    assert store.get("missing") is None


def test_purge_removes_expired_requests_with_children(store):
    old = datetime.now(UTC) - timedelta(days=91)
    expired = _saved(store, started_at=old.isoformat())
    recent = _saved(store, started_at=(datetime.now(UTC) - timedelta(days=89)).isoformat())

    store.init(retention_days=90)

    assert store.get(expired.id) is None and store.get(recent.id) is not None
    assert [r["id"] for r in store.recent()] == [recent.id]
    with audit_module.closing(store._connect()) as db:
        assert db.execute("SELECT COUNT(*) FROM model_calls").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0] == 1


async def test_failed_flush_is_logged_and_does_not_raise(store, caplog):
    store.path.unlink()
    store.path.mkdir()  # can't be opened as a database
    await store.flush(RequestAudit(agent="advisor", question="?"))
    assert "Could not write audit record" in caplog.text


def test_usage_report_totals_and_unpriced(store):
    _saved(store, agent="advisor")
    _saved(store, agent="stocks", model="claude-unknown")

    report = store.usage(days=30)
    [day] = report["by_day"]
    assert day["requests"] == 2 and day["input_tokens"] == 200 and day["unpriced_calls"] == 1
    assert day["est_cost_usd"] == pytest.approx(estimate_cost("claude-opus-5-5", tokens(100, 10, 5, 2)))
    assert [a["agent"] for a in report["by_agent"]] == ["advisor", "stocks"]
    assert {m["model"] for m in report["by_model"]} == {"claude-opus-5-5", "claude-unknown"}
    assert report["guardrail"] == [{"outcome": "answer", "source": "classifier", "requests": 2}]


def test_usage_report_respects_the_window(store):
    _saved(store, started_at=(datetime.now(UTC) - timedelta(days=10)).isoformat())
    assert store.usage(days=30)["by_day"] and not store.usage(days=5)["by_day"]


def test_cli_commands(store, capsys):
    audit = _saved(store)

    assert audit_module.main(["usage", "--days", "7"], path=store.path) == 0
    assert json.loads(capsys.readouterr().out)["by_agent"][0]["agent"] == "advisor"

    assert audit_module.main(["list", "--limit", "5"], path=store.path) == 0
    [row] = json.loads(capsys.readouterr().out)
    assert row["id"] == audit.id and row["tokens"] == 117

    assert audit_module.main(["show", audit.id], path=store.path) == 0
    assert json.loads(capsys.readouterr().out)["model_calls"][0]["thinking"] == "Think."

    assert audit_module.main(["show", "missing"], path=store.path) == 1


def test_cli_reports_missing_database(tmp_path, capsys):
    assert audit_module.main(["list"], path=tmp_path / "none.db") == 1
    assert "No audit database" in capsys.readouterr().err
