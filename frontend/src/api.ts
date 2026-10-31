export type View = 'portfolio' | 'analysis' | 'strategy'

export interface PortfolioSummary {
  id: string
  name: string
  account_type: string
}

export interface Holding {
  symbol: string
  type: 'stock' | 'etf'
  shares: number
  cost_basis: number
  price: number
  market_value: number
  cost: number
  gain: number
  gain_pct: number | null
}

export interface Portfolio extends PortfolioSummary {
  holdings: Holding[]
  total_value: number
  total_cost: number
  total_gain: number
  total_gain_pct: number | null
}

export interface Weight {
  symbol: string
  type: string
  weight_pct: number
  gain: number
  gain_pct: number | null
}

export interface Analysis {
  id: string
  name: string
  total_value: number
  by_holding: Weight[]
  by_type: { type: string; weight_pct: number }[]
  largest_position: Weight | null
  top3_weight_pct: number
}

export interface BacktestResult {
  symbol: string
  start: string
  end: string
  trading_days: number
  total_return_pct: number
  cagr_pct: number
  annualized_volatility_pct: number
  max_drawdown_pct: number
  initial_capital: number
  final_value: number
}

export interface EventStudyResult {
  symbol: string
  benchmark: string
  event_day: string
  alpha: number
  beta: number
  estimation_days: number
  series: { day: number; date: string; abnormal_return_pct: number; car_pct: number }[]
  car_pct: number
  car_t_stat: number | null
}

export interface AgentInfo {
  id: string
  name: string
  description: string
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // body was not JSON
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  portfolios: () => request<PortfolioSummary[]>('/api/portfolios'),
  portfolio: (id: string) => request<Portfolio>(`/api/portfolios/${id}`),
  analysis: (id: string) => request<Analysis>(`/api/portfolios/${id}/analysis`),
  agents: () => request<AgentInfo[]>('/api/agents'),
  backtest: (body: { symbol: string; start: string; end: string; initial_capital: number }) =>
    post<BacktestResult>('/api/strategy/backtest', body),
  eventStudy: (body: { symbol: string; event_date: string; benchmark: string; window: number }) =>
    post<EventStudyResult>('/api/strategy/event-study', body),
  chat: (body: {
    agent: string
    messages: ChatMessage[]
    context: { view: View; portfolio_id: string }
  }) => post<{ reply: string }>('/api/chat', body),
}
