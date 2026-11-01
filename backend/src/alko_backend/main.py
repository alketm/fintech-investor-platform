"""FastAPI app: REST API for the frontend, MCP servers and agents started in the lifespan."""

from contextlib import AsyncExitStack, asynccontextmanager
from typing import Literal

import anthropic
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from alko_backend.agents import AGENTS, AgentRunner
from alko_backend.config import SECTOR_ETFS, load_env_file
from alko_backend.mcp_pool import McpPool, ToolError
from alko_backend.portfolios import analyze, describe_for_agent, load_portfolios, value_portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_env_file()
    async with AsyncExitStack() as stack:
        pool = McpPool()
        await pool.start(stack)
        app.state.pool = pool
        app.state.runner = AgentRunner(anthropic.AsyncAnthropic(), pool)
        app.state.portfolios = load_portfolios()
        yield


app = FastAPI(title="Alko Investment Advisor API", lifespan=lifespan)


def _portfolio(request: Request, portfolio_id: str) -> dict:
    portfolio = request.app.state.portfolios.get(portfolio_id)
    if portfolio is None:
        raise HTTPException(404, f"Unknown portfolio {portfolio_id!r}")
    return portfolio


async def _valued(request: Request, portfolio_id: str) -> dict:
    pool = request.app.state.pool

    async def quote(symbol: str) -> float:
        return (await pool.call_json("mcp_stocks", "get_quote", {"symbol": symbol}))["price"]

    try:
        return await value_portfolio(_portfolio(request, portfolio_id), quote)
    except ToolError as e:
        raise HTTPException(502, f"Price lookup failed: {e}") from e


@app.get("/api/health")
async def health(request: Request):
    return {
        "status": "ok",
        "mcp_servers": {
            name: [t.name for t in tools] for name, tools in request.app.state.pool.tools.items()
        },
    }


@app.get("/api/portfolios")
async def list_portfolios(request: Request):
    return [
        {"id": p["id"], "name": p["name"], "account_type": p["account_type"]}
        for p in request.app.state.portfolios.values()
    ]


@app.get("/api/portfolios/{portfolio_id}")
async def get_portfolio(portfolio_id: str, request: Request):
    return await _valued(request, portfolio_id)


@app.get("/api/portfolios/{portfolio_id}/analysis")
async def get_analysis(portfolio_id: str, request: Request):
    return analyze(await _valued(request, portfolio_id))


class BacktestRequest(BaseModel):
    symbol: str
    start: str
    end: str
    initial_capital: float = 10_000.0


class EventStudyRequest(BaseModel):
    symbol: str
    event_date: str
    benchmark: str = "SPY"
    window: int = Field(5, ge=1, le=30)


class LongShortRequest(BaseModel):
    strategy: Literal[
        "moving_average",
        "time_series_momentum",
        "rsi_mean_reversion",
        "policy_uncertainty",
        "consumer_sentiment",
    ]
    symbol: str
    start: str
    end: str
    initial_capital: float = Field(10_000.0, gt=0)
    cost_bps: float = Field(5.0, ge=0)
    params: dict[str, float] = {}


LONG_SHORT_TOOLS = {
    "moving_average": ("backtest_moving_average", {"fast", "slow"}),
    "time_series_momentum": ("backtest_time_series_momentum", {"lookback_days", "skip_days"}),
    "rsi_mean_reversion": ("backtest_rsi_mean_reversion", {"period", "lower", "upper", "exit_level"}),
    "policy_uncertainty": ("backtest_policy_uncertainty", {"lookback_days", "threshold", "signal_lag_days"}),
    "consumer_sentiment": ("backtest_consumer_sentiment", {"ma_months", "release_lag_months"}),
}
INTEGER_PARAMS = {
    "fast",
    "slow",
    "lookback_days",
    "skip_days",
    "period",
    "signal_lag_days",
    "ma_months",
    "release_lag_months",
}


class EarningsStudyRequest(BaseModel):
    symbol: str
    benchmark: str = "SPY"
    window: int = Field(5, ge=1, le=20)
    max_events: int = Field(12, ge=1, le=40)


class LargeMoveStudyRequest(BaseModel):
    symbol: str
    threshold_sigma: float = Field(2.5, gt=0)
    benchmark: str = "SPY"
    window: int = Field(10, ge=1, le=30)
    lookback_years: int = Field(5, ge=1, le=20)


async def _tool(request: Request, server: str, tool: str, args: dict) -> dict:
    try:
        return await request.app.state.pool.call_json(server, tool, args)
    except ToolError as e:
        raise HTTPException(422, str(e)) from e


@app.get("/api/strategy/symbols")
async def strategy_symbols(request: Request):
    """Symbols the strategy page offers: each portfolio's holdings, then the sector ETFs."""
    groups = [
        {
            "label": f"{p['name']} holdings",
            "symbols": [{"symbol": h["symbol"], "name": h["type"].upper()} for h in p["holdings"]],
        }
        for p in request.app.state.portfolios.values()
    ]
    groups.append(
        {"label": "Sector ETFs", "symbols": [{"symbol": s, "name": n} for s, n in SECTOR_ETFS.items()]}
    )
    return groups


@app.post("/api/strategy/backtest")
async def backtest(body: BacktestRequest, request: Request):
    return await _tool(request, "mcp_backtest", "backtest_buy_and_hold", body.model_dump())


@app.post("/api/strategy/event-study")
async def event_study(body: EventStudyRequest, request: Request):
    return await _tool(request, "mcp_event_study", "run_event_study", body.model_dump())


@app.post("/api/strategy/long-short")
async def long_short(body: LongShortRequest, request: Request):
    tool, allowed = LONG_SHORT_TOOLS[body.strategy]
    unknown = set(body.params) - allowed
    if unknown:
        raise HTTPException(422, f"Unknown parameters for {body.strategy}: {', '.join(sorted(unknown))}")
    params = {k: int(v) if k in INTEGER_PARAMS else v for k, v in body.params.items()}
    args = body.model_dump(exclude={"strategy", "params"}) | params
    return await _tool(request, "mcp_backtest", tool, args)


@app.post("/api/strategy/event-study/earnings")
async def earnings_study(body: EarningsStudyRequest, request: Request):
    return await _tool(request, "mcp_event_study", "run_earnings_event_study", body.model_dump())


@app.post("/api/strategy/event-study/large-moves")
async def large_move_study(body: LargeMoveStudyRequest, request: Request):
    return await _tool(request, "mcp_event_study", "run_large_move_event_study", body.model_dump())


@app.get("/api/agents")
async def list_agents():
    return [{"id": a.id, "name": a.name, "description": a.description} for a in AGENTS.values()]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatContext(BaseModel):
    view: Literal["portfolio", "analysis", "strategy"] | None = None
    portfolio_id: str | None = None


class ChatRequest(BaseModel):
    agent: str = "advisor"
    messages: list[ChatMessage] = Field(min_length=1)
    context: ChatContext = ChatContext()


def _context_text(request: Request, ctx: ChatContext) -> str:
    portfolios = request.app.state.portfolios
    lines = [f"[App context] The user is on the {ctx.view or 'unknown'} view."]
    if ctx.portfolio_id in portfolios:
        lines.append(f"Selected portfolio: {portfolios[ctx.portfolio_id]['name']}.")
    lines.append("Portfolios:\n" + "\n\n".join(describe_for_agent(p) for p in portfolios.values()))
    return "\n".join(lines)


@app.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    if body.agent not in AGENTS:
        raise HTTPException(404, f"Unknown agent {body.agent!r}")
    if body.messages[-1].role != "user":
        raise HTTPException(422, "The last message must be from the user")

    messages = [m.model_dump() for m in body.messages]
    # App context goes on the latest user turn, after the cached system prompt and history.
    messages[-1]["content"] = [
        {"type": "text", "text": _context_text(request, body.context)},
        {"type": "text", "text": messages[-1]["content"]},
    ]
    try:
        result = await request.app.state.runner.run(body.agent, messages)
    except anthropic.AuthenticationError as e:
        raise HTTPException(500, "Claude API authentication failed; check ANTHROPIC_API_KEY") from e
    except anthropic.RateLimitError as e:
        raise HTTPException(429, "Claude API rate limit reached; try again shortly") from e
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"Claude API error: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise HTTPException(502, "Could not reach the Claude API") from e
    return {"agent": body.agent, "reply": result.text, "tool_calls": result.tool_calls}


def run() -> None:
    import uvicorn

    uvicorn.run("alko_backend.main:app", host="127.0.0.1", port=8000)
