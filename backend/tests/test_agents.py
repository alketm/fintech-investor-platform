from alko_backend.agents import AGENTS, AgentRunner

from .conftest import FakeClaude, text_block, tool_use


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
