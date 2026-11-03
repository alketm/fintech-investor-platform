import asyncio
from types import SimpleNamespace

import pytest

from alko_backend.agents import AGENTS, AgentRunner
from alko_backend.audit import RequestAudit

from .conftest import USAGE_TOTAL, FakeClaude, text_block, thinking_block, tool_use


def test_every_delegate_and_server_is_defined():
    advisor = AGENTS["advisor"]
    assert advisor.servers == ()
    assert set(advisor.delegates) == set(AGENTS) - {"advisor"}
    for agent in AGENTS.values():
        assert not (agent.servers and agent.delegates)


def test_focused_agent_sees_only_its_server_tools(pool):
    runner = AgentRunner(FakeClaude({}), pool)
    assert [t["name"] for t in runner.tools_for(AGENTS["stocks"])] == ["get_quote"]
    assert {t["name"] for t in runner.tools_for(AGENTS["advisor"])} == {
        f"ask_{a}" for a in AGENTS["advisor"].delegates
    }


async def test_focused_agent_calls_mcp_tool(pool):
    claude = FakeClaude(
        {
            "Stock analyst": [
                [tool_use("t1", "get_quote", {"symbol": "AAPL"})],
                [text_block("AAPL is $200.")],
            ]
        }
    )
    result = await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "AAPL price?"}])

    assert result.text == "AAPL is $200."
    assert pool.calls == [("mcp_stocks", "get_quote", {"symbol": "AAPL"})]
    tool_result = claude.requests[1]["messages"][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1" and '"price": 200.0' in tool_result["content"]
    assert claude.requests[0]["fallbacks"] == "default"


async def test_advisor_delegates_to_specialist(pool):
    claude = FakeClaude(
        {
            "Investment advisor": [
                [tool_use("a1", "ask_stocks", {"question": "Price of AAPL?"})],
                [text_block("Your AAPL is worth $200/share.")],
            ],
            "Stock analyst": [
                [tool_use("s1", "get_quote", {"symbol": "AAPL"})],
                [text_block("AAPL: $200")],
            ],
        }
    )
    result = await AgentRunner(claude, pool).run("advisor", [{"role": "user", "content": "How is AAPL?"}])

    assert result.text == "Your AAPL is worth $200/share."
    assert [c["tool"] for c in result.tool_calls] == ["ask_stocks", "get_quote"]
    delegated = claude.requests[-1]["messages"][-1]["content"][0]
    assert delegated["content"] == "AAPL: $200" and delegated["is_error"] is False


async def test_unknown_tool_is_reported_as_error(pool):
    claude = FakeClaude(
        {
            "Stock analyst": [
                [tool_use("t1", "made_up", {})],
                [text_block("Sorry.")],
            ]
        }
    )
    await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "?"}])
    assert claude.requests[1]["messages"][-1]["content"][0]["is_error"] is True


async def test_agent_cannot_run_another_agents_tool(pool):
    claude = FakeClaude(
        {
            "Stock analyst": [
                [tool_use("t1", "backtest_buy_and_hold", {"symbol": "AAPL"})],
                [text_block("Sorry.")],
            ]
        }
    )
    audit = RequestAudit(agent="stocks", question="?")
    await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "?"}], audit=audit)

    assert pool.calls == []
    assert claude.requests[1]["messages"][-1]["content"][0]["is_error"] is True
    assert audit.tool_calls[0]["denied"] is True and audit.tool_calls[0]["server"] is None


async def test_agents_cannot_delegate_outside_their_list(pool):
    claude = FakeClaude(
        {
            "Stock analyst": [[tool_use("t1", "ask_advisor", {"question": "?"})], [text_block("Sorry.")]],
            "Investment advisor": [
                [tool_use("a1", "ask_advisor", {"question": "?"})],
                [text_block("Sorry.")],
            ],
        }
    )
    for agent in ("stocks", "advisor"):
        audit = RequestAudit(agent=agent, question="?")
        await AgentRunner(claude, pool).run(agent, [{"role": "user", "content": "?"}], audit=audit)
        assert [c["agent"] for c in audit.model_calls] == [agent, agent]
        assert audit.tool_calls[0]["denied"] is True


async def test_delegation_stops_at_max_depth(pool):
    claude = FakeClaude({})
    audit = RequestAudit(agent="advisor", question="?")
    text, is_error = await AgentRunner(claude, pool)._execute(
        AGENTS["advisor"], "ask_stocks", {"question": "?"}, 1, [], audit
    )
    assert is_error is True and "Unknown tool" in text
    assert claude.requests == [] and audit.tool_calls[0]["denied"] is True


async def test_budget_stops_specialists_too(pool):
    claude = FakeClaude({"Investment advisor": [[tool_use("a1", "ask_stocks", {"question": "?"})]]})
    audit = RequestAudit(agent="advisor", question="?")
    runner = AgentRunner(claude, pool, max_request_tokens=USAGE_TOTAL)
    result = await runner.run("advisor", [{"role": "user", "content": "?"}], audit=audit)

    assert result.status == "budget_exceeded" and "token limit" in result.text
    assert len(claude.requests) == 1  # neither the specialist nor the advisor called the model again
    assert audit.tool_calls[0]["tool"] == "ask_stocks" and audit.tool_calls[0]["is_error"] is True


async def test_requests_summarized_thinking_and_passes_blocks_back_unchanged(pool):
    first = [thinking_block("Look it up."), tool_use("t1", "get_quote", {"symbol": "AAPL"})]
    claude = FakeClaude({"Stock analyst": [first, [text_block("AAPL is $200.")]]})
    await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "AAPL?"}])

    assert claude.requests[0]["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert claude.requests[1]["messages"][1] == {"role": "assistant", "content": first}


async def test_refusal_and_turn_limit_statuses(pool):
    claude = FakeClaude(
        {"Stock analyst": [[tool_use(f"t{i}", "get_quote", {"symbol": "AAPL"})] for i in range(12)]}
    )
    result = await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "?"}])
    assert result.status == "turn_limit"

    claude = FakeClaude({"Stock analyst": [[]]})
    original = claude.beta.messages.create

    async def refuse(**kwargs):
        response = await original(**kwargs)
        response.stop_reason = "refusal"
        response.stop_details = SimpleNamespace(category="cyber")
        return response

    claude.beta.messages.create = refuse
    audit = RequestAudit(agent="stocks", question="?")
    result = await AgentRunner(claude, pool).run("stocks", [{"role": "user", "content": "?"}], audit=audit)
    assert result.status == "refusal" and audit.model_calls[0]["refusal_category"] == "cyber"


async def test_failed_specialist_keeps_every_record_and_waits_for_the_others(pool):
    claude = FakeClaude(
        {
            "Investment advisor": [
                [
                    tool_use("a1", "ask_stocks", {"question": "?"}),
                    tool_use("a2", "ask_backtest", {"question": "?"}),
                ]
            ],
            "Stock analyst": [RuntimeError("stocks failed")],
            "Backtest analyst": [[text_block("Done.")]],
        }
    )
    original = claude.beta.messages.create

    async def slow_backtest(**kwargs):
        if "Backtest analyst" in kwargs["system"][0]["text"]:
            await asyncio.sleep(0.02)
        return await original(**kwargs)

    claude.beta.messages.create = slow_backtest
    audit = RequestAudit(agent="advisor", question="?")
    with pytest.raises(RuntimeError, match="stocks failed"):
        await AgentRunner(claude, pool).run("advisor", [{"role": "user", "content": "?"}], audit=audit)

    # The specialist that was still running has finished and is on record when the error surfaces.
    assert [c["agent"] for c in audit.model_calls] == ["advisor", "backtest"]
    tools = {t["tool"]: t for t in audit.tool_calls}
    assert tools["ask_backtest"]["is_error"] is False
    assert tools["ask_stocks"]["is_error"] is True and "stocks failed" in tools["ask_stocks"]["result"]
