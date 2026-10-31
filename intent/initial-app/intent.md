# Intent: Initial application

**Status:** accepted
**Owner:** alketm

## Problem
There is no single place to see my brokerage and IRA holdings, analyze them, test strategy ideas, and ask an
AI advisor questions grounded in live market data.

## Proposed outcome
A browser application backed by an API server and a set of AI agents:
- Frontend server hosting the UI with three views: **Portfolio**, **Portfolio analysis**, **Strategy**
  (backtests and event studies).
- From every view, a chatbot that can talk to the main **investment advisor** agent or any focused agent.
- Backend server hosting the APIs and running the agents.
- Agents get data only through MCP servers, one per domain: **ETFs**, **Stocks**, **News**,
  **Financial statements**, **Backtests**, **Event studies**. Each starts with one simple tool.

## Affected users and systems
- Single user (the owner) to start.
- Two portfolios: **Brokerage** and **IRA**. Stocks and ETFs only.

## Constraints
- Separate MCP server per domain to keep code focused.
- Market data from a free source to start (yfinance); swappable later.
- Agent output is information and analysis, not executed trades. The app never places orders.

## Open questions
- Where holdings come from long term (manual file today; broker import later?).
- Persisting chat history.
- Authentication once more than one user exists.
