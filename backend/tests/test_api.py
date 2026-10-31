from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from alko_backend import main
from alko_backend.agents import AgentRunner
from alko_backend.portfolios import load_portfolios

from .conftest import FakeClaude, text_block


@pytest.fixture
def client(pool):
    claude = FakeClaude({"Investment advisor": [[text_block("Hello from the advisor.")]]})

    @asynccontextmanager
    async def fake_lifespan(app):
        app.state.pool = pool
        app.state.runner = AgentRunner(claude, pool)
        app.state.portfolios = load_portfolios()
        yield

    original = main.app.router.lifespan_context
    main.app.router.lifespan_context = fake_lifespan
    with TestClient(main.app) as c:
        c.claude = claude
        yield c
    main.app.router.lifespan_context = original


def test_health_lists_servers(client):
    assert client.get("/api/health").json()["mcp_servers"]["stocks"] == ["get_quote"]


def test_portfolios(client):
    assert [p["id"] for p in client.get("/api/portfolios").json()] == ["brokerage", "ira"]
    ira = client.get("/api/portfolios/ira").json()
    assert ira["total_value"] > 0 and len(ira["holdings"]) == 5
    assert client.get("/api/portfolios/nope").status_code == 404


def test_analysis(client):
    analysis = client.get("/api/portfolios/brokerage/analysis").json()
    assert {t["type"] for t in analysis["by_type"]} == {"stock", "etf"}


def test_backtest_passes_through_tool_result(client):
    r = client.post(
        "/api/strategy/backtest", json={"symbol": "SPY", "start": "2020-01-01", "end": "2021-01-01"}
    )
    assert r.json() == {"total_return_pct": 42.0}


def test_chat_adds_app_context(client):
    r = client.post(
        "/api/chat",
        json={
            "agent": "advisor",
            "messages": [{"role": "user", "content": "Hi"}],
            "context": {"view": "portfolio", "portfolio_id": "ira"},
        },
    )
    assert r.status_code == 200 and r.json()["reply"] == "Hello from the advisor."
    sent = client.claude.requests[0]["messages"][-1]["content"]
    assert "portfolio view" in sent[0]["text"] and "Selected portfolio: IRA" in sent[0]["text"]
    assert sent[1]["text"] == "Hi"


def test_chat_rejects_unknown_agent_and_assistant_last(client):
    assert (
        client.post(
            "/api/chat", json={"agent": "x", "messages": [{"role": "user", "content": "a"}]}
        ).status_code
        == 404
    )
    bad = {"messages": [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]}
    assert client.post("/api/chat", json=bad).status_code == 422
