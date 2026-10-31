"""Agent definitions and the Claude tool-use loop.

The advisor reaches data only through focused agents (its `ask_<agent>` tools); each focused agent reaches
data only through the tools of its own MCP server(s).
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any, Protocol

import anthropic

from alko_backend.config import EFFORT, MAX_AGENT_TURNS, MODEL

COMMON_RULES = """\
You are part of Alko Investment Advisor, an assistant for the owner's own brokerage and IRA portfolios \
(US stocks and ETFs).
- Ground every number in a tool result from this conversation; say so when data is missing or stale.
- State the assumptions and limits of any analysis. Never present future returns as certain.
- You give analysis and options for the owner to decide on; you cannot and do not place trades.
- Be concise. Use short markdown: bullets and small tables, no long preambles."""


@dataclass(frozen=True)
class AgentSpec:
    id: str
    name: str
    description: str
    instructions: str
    servers: tuple[str, ...] = ()
    delegates: tuple[str, ...] = ()

    @property
    def system(self) -> str:
        return f"{COMMON_RULES}\n\nYour role: {self.name}. {self.instructions}"


FOCUSED_AGENTS = [
    AgentSpec(
        "etf",
        "ETF analyst",
        "ETF facts, holdings, sectors, performance and risk.",
        "Explain and compare ETFs: costs, holdings and overlap, sector exposure, performance and risk. "
        "Pass all the funds you are comparing in one tool call, and say which window the numbers cover.",
        servers=("etf",),
    ),
    AgentSpec(
        "stocks",
        "Stock analyst",
        "Quotes and company basics.",
        "Report current prices and market data for stocks and ETFs.",
        servers=("stocks",),
    ),
    AgentSpec(
        "news",
        "News analyst",
        "Recent headlines and analyst ratings.",
        "Summarize recent news and sell-side analyst views (consensus, price targets, upgrades and downgrades) "
        "for tickers, and flag what may matter for a holder. Treat analyst targets as opinions, not forecasts.",
        servers=("news",),
    ),
    AgentSpec(
        "financials",
        "Financial statements analyst",
        "Statements, growth, financial health, efficiency and valuation ratios.",
        "Analyze companies from their financial statements: growth, profitability, balance-sheet health, "
        "efficiency and valuation. Start with the overview or the analysis tools and pull full statements only "
        "when needed. Say which fiscal year the figures are from, and flag metrics that are not meaningful for "
        "the company's industry (for example banks).",
        servers=("financials",),
    ),
    AgentSpec(
        "backtest",
        "Backtest analyst",
        "Historical strategy backtests.",
        "Run backtests and explain the results and their limits (look-ahead, survivorship, costs).",
        servers=("backtest",),
    ),
    AgentSpec(
        "event_study",
        "Event study analyst",
        "Abnormal returns around events.",
        "Run event studies and interpret abnormal returns and their statistical significance.",
        servers=("event_study",),
    ),
]

ADVISOR = AgentSpec(
    "advisor",
    "Investment advisor",
    "Main agent: portfolio-level questions, delegates to the specialists.",
    "You are the main advisor. You know the owner's portfolios from the context. For any market data, news, "
    "fundamentals, backtest or event study, ask the relevant specialist with the ask_<agent> tools - ask "
    "several in parallel when the question spans domains - then synthesize one answer.",
    delegates=tuple(a.id for a in FOCUSED_AGENTS),
)

AGENTS: dict[str, AgentSpec] = {a.id: a for a in [ADVISOR, *FOCUSED_AGENTS]}


class ToolPool(Protocol):
    def anthropic_tools(self, server: str) -> list[dict]: ...
    def server_for_tool(self, tool_name: str) -> str | None: ...
    async def call(self, server: str, tool: str, args: dict) -> tuple[str, bool]: ...


@dataclass
class AgentResult:
    text: str
    tool_calls: list[dict] = field(default_factory=list)


class AgentRunner:
    def __init__(self, client: anthropic.AsyncAnthropic, pool: ToolPool, model: str = MODEL) -> None:
        self.client = client
        self.pool = pool
        self.model = model

    def tools_for(self, spec: AgentSpec) -> list[dict]:
        tools = [t for server in spec.servers for t in self.pool.anthropic_tools(server)]
        for d in spec.delegates:
            target = AGENTS[d]
            tools.append(
                {
                    "name": f"ask_{d}",
                    "description": f"Ask the {target.name}: {target.description} Returns its written answer.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Self-contained question"}
                        },
                        "required": ["question"],
                        "additionalProperties": False,
                    },
                }
            )
        return tools

    async def run(self, agent_id: str, messages: list[dict], depth: int = 0) -> AgentResult:
        spec = AGENTS[agent_id]
        tools = self.tools_for(spec)
        messages = list(messages)
        calls: list[dict] = []

        for _ in range(MAX_AGENT_TURNS):
            response = await self.client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                system=[{"type": "text", "text": spec.system, "cache_control": {"type": "ephemeral"}}],
                tools=tools,
                messages=messages,
                output_config={"effort": EFFORT},
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
            )
            if response.stop_reason == "refusal":
                return AgentResult("I can't help with that request.", calls)
            if response.stop_reason != "tool_use":
                text = "".join(b.text for b in response.content if b.type == "text").strip()
                return AgentResult(text, calls)

            uses = [b for b in response.content if b.type == "tool_use"]
            results = await asyncio.gather(*(self._execute(u.name, u.input, depth, calls) for u in uses))
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": u.id, "content": text, "is_error": is_error}
                        for u, (text, is_error) in zip(uses, results, strict=True)
                    ],
                }
            )

        return AgentResult(
            "I stopped after too many steps without finishing. Try a narrower question.", calls
        )

    async def _execute(self, name: str, args: Any, depth: int, calls: list[dict]) -> tuple[str, bool]:
        calls.append({"tool": name, "input": args, "depth": depth})
        if name.startswith("ask_") and name[4:] in AGENTS:
            question = args.get("question") if isinstance(args, dict) else None
            if not isinstance(question, str) or not question.strip():
                return "Invalid input: 'question' must be a non-empty string.", True
            sub = await self.run(name[4:], [{"role": "user", "content": question}], depth + 1)
            calls.extend(sub.tool_calls)
            return sub.text, False

        server = self.pool.server_for_tool(name)
        if server is None:
            return f"Unknown tool {name!r}.", True
        try:
            return await self.pool.call(server, name, args)
        except Exception as e:  # report tool failures to the model instead of failing the request
            return f"Tool {name} failed: {e}", True
