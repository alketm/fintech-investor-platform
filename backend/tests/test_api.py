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
    assert client.get("/api/health").json()["mcp_servers"]["mcp_stocks"] == ["get_quote"]


def test_portfolios(client):
    assert [p["id"] for p in client.get("/api/portfolios").json()] == ["brokerage", "ira"]
    ira = client.get("/api/portfolios/ira").json()
    assert ira["total_value"] > 0 and len(ira["holdings"]) == 5
    assert client.get("/api/portfolios/nope").status_code == 404


def test_strategy_symbols_lists_holdings_then_sector_etfs(client):
    groups = client.get("/api/strategy/symbols").json()
    assert [g["label"] for g in groups][-1] == "Sector ETFs"
    holdings = {s["symbol"] for g in groups[:-1] for s in g["symbols"]}
    assert {"AAPL", "NVDA", "VTI", "SCHD", "JNJ"} <= holdings and len(holdings) == 10
    sectors = [s["symbol"] for s in groups[-1]["symbols"]]
    assert sectors == ["XLY", "XLE", "XLF", "XLV", "XLI", "XLB", "XLRE", "XLK"]


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


def test_load_env_file_does_not_override(tmp_path, monkeypatch):
    from alko_backend.config import load_env_file

    env = tmp_path / ".env"
    env.write_text("# comment\nALKO_TEST_A='from file'\nALKO_TEST_B=from file\n")
    monkeypatch.setenv("ALKO_TEST_B", "from shell")
    monkeypatch.delenv("ALKO_TEST_A", raising=False)
    load_env_file(env)
    import os

    assert os.environ["ALKO_TEST_A"] == "from file"
    assert os.environ["ALKO_TEST_B"] == "from shell"
    monkeypatch.delenv("ALKO_TEST_A")


def test_long_short_endpoint_maps_strategy_and_params(client, pool):
    r = client.post(
        "/api/strategy/long-short",
        json={
            "strategy": "moving_average",
            "symbol": "SPY",
            "start": "2020-01-01",
            "end": "2024-01-01",
            "params": {"fast": 20.0, "slow": 100},
        },
    )
    assert r.status_code == 200
    server, tool, args = pool.calls[-1]
    assert (server, tool) == ("mcp_backtest", "backtest_moving_average")
    assert args["fast"] == 20 and isinstance(args["fast"], int) and args["cost_bps"] == 5.0
    bad = client.post(
        "/api/strategy/long-short",
        json={
            "strategy": "rsi_mean_reversion",
            "symbol": "SPY",
            "start": "2020-01-01",
            "end": "2024-01-01",
            "params": {"fast": 5},
        },
    )
    assert bad.status_code == 422 and "fast" in bad.json()["detail"]


def test_event_study_endpoints(client, pool):
    assert client.post("/api/strategy/event-study/earnings", json={"symbol": "AAPL"}).status_code == 200
    assert pool.calls[-1][:2] == ("mcp_event_study", "run_earnings_event_study")
    assert (
        client.post("/api/strategy/event-study/large-moves", json={"symbol": "AAPL", "window": 5}).status_code
        == 200
    )
    assert pool.calls[-1][1] == "run_large_move_event_study" and pool.calls[-1][2]["threshold_sigma"] == 2.5
    assert client.post("/api/strategy/event-study/credit-spread", json={"symbol": "XLF"}).status_code == 200
    _, tool, args = pool.calls[-1]
    assert tool == "run_credit_spread_event_study"
    assert (args["threshold"], args["ma_days"], args["window"], args["lookback_years"]) == (1.25, 21, 10, 10)
    bad = client.post("/api/strategy/event-study/credit-spread", json={"symbol": "XLF", "threshold": 0.9})
    assert bad.status_code == 422


def test_long_short_policy_uncertainty_maps_params(client, pool):
    r = client.post(
        "/api/strategy/long-short",
        json={
            "strategy": "policy_uncertainty",
            "symbol": "SPY",
            "start": "2020-01-01",
            "end": "2024-01-01",
            "params": {"ma_days": 21.0, "short_above": 1.5, "signal_lag_days": 2},
        },
    )
    assert r.status_code == 200
    _, tool, args = pool.calls[-1]
    assert tool == "backtest_policy_uncertainty"
    assert (
        args["signal_lag_days"] == 2
        and isinstance(args["signal_lag_days"], int)
        and args["short_above"] == 1.5
    )
    assert args["ma_days"] == 21 and isinstance(args["ma_days"], int)


def test_long_short_consumer_sentiment_maps_params(client, pool):
    r = client.post(
        "/api/strategy/long-short",
        json={
            "strategy": "consumer_sentiment",
            "symbol": "XLY",
            "start": "2015-01-01",
            "end": "2025-01-01",
            "params": {"ma_months": 3.0, "release_lag_months": 1, "short_below_pct": 94.5, "exit_pct": 96},
        },
    )
    assert r.status_code == 200
    _, tool, args = pool.calls[-1]
    assert tool == "backtest_consumer_sentiment"
    assert args["ma_months"] == 3 and isinstance(args["ma_months"], int) and args["release_lag_months"] == 1
    assert args["short_below_pct"] == 94.5 and args["exit_pct"] == 96


def test_long_short_vix_volatility_maps_params(client, pool):
    r = client.post(
        "/api/strategy/long-short",
        json={
            "strategy": "vix_volatility",
            "symbol": "XLK",
            "start": "2020-01-01",
            "end": "2025-01-01",
            "params": {"window_days": 20.0, "short_above": 2.0, "long_below": 1.7, "exit_level": 1.8},
        },
    )
    assert r.status_code == 200
    _, tool, args = pool.calls[-1]
    assert tool == "backtest_vix_volatility"
    assert args["window_days"] == 20 and isinstance(args["window_days"], int) and args["exit_level"] == 1.8
