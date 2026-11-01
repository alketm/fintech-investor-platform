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

export interface SymbolGroup {
  label: string
  symbols: { symbol: string; name: string }[]
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
  sharpe_ratio: number | null
  max_drawdown_pct: number
  initial_capital: number
  final_value: number
  /** Buying and holding the benchmark (SPY) over the same days; null if it had no data. */
  benchmark: BenchmarkStats | null
  equity_curve: { date: string; buy_and_hold: number; benchmark?: number }[]
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

export type LongShortStrategy =
  | 'moving_average'
  | 'time_series_momentum'
  | 'rsi_mean_reversion'
  | 'policy_uncertainty'
  | 'consumer_sentiment'
  | 'vix_volatility'

export interface StrategyStats {
  total_return_pct: number
  cagr_pct: number | null
  annualized_volatility_pct: number
  sharpe_ratio: number | null
  max_drawdown_pct: number
  final_value: number
}

export interface BenchmarkStats extends StrategyStats {
  symbol: string
}

export interface LongShortResult {
  symbol: string
  rule: string
  parameters: Record<string, number | string>
  start: string
  end: string
  trading_days: number
  strategy: StrategyStats
  buy_and_hold: StrategyStats
  benchmark: BenchmarkStats | null
  activity: {
    position_changes: number
    pct_days_long: number
    pct_days_short: number
    pct_days_flat: number
    closed_trades: number
    win_rate_pct: number | null
    total_costs: number
    current_position: 'long' | 'short' | 'flat'
  }
  equity_curve: { date: string; strategy: number; buy_and_hold: number; benchmark?: number }[]
  assumptions: string
  uncertainty?: {
    source: string
    value_at_end: number | null
    value_date: string | null
    zscore_at_end: number | null
    pct_days_high: number | null
    pct_days_low: number | null
    pct_days_neutral: number | null
  }
  sentiment?: {
    source: string
    reading_month: string | null
    value_at_end: number | null
    moving_average_at_end: number | null
    ratio_pct_at_end: number | null
    signal_at_end: 'long' | 'short' | 'flat' | null
  }
  volatility?: {
    source: string
    date: string | null
    vix_at_end: number | null
    realized_vol_at_end: number | null
    ratio_at_end: number | null
    signal_at_end: 'long' | 'short' | 'flat' | null
    median_ratio: number | null
  }
}

export interface PathPoint {
  day: number
  abnormal_return_pct: number
  car_pct: number
}

export interface EventAggregate {
  events: number
  average_car_pct: number
  median_car_pct: number
  pct_positive: number
  t_stat: number | null
  car_days: string
  average_path: PathPoint[]
}

export interface EarningsStudyResult {
  symbol: string
  benchmark: string
  window: number
  aggregate: EventAggregate
  beats: EventAggregate | null
  misses: EventAggregate | null
  events: {
    announced: string
    timing: string
    day0: string
    eps_estimate: number | null
    eps_actual: number | null
    surprise_pct: number | null
    day0_abnormal_pct: number
    car_m1_p1_pct: number
    car_window_pct: number
  }[]
  skipped: { date: string; reason: string }[]
  note: string
}

export interface MoveGroup extends EventAggregate {
  average_move_pct: number
  pct_continuing: number
  read: string | null
}

export interface LargeMoveStudyResult {
  symbol: string
  benchmark: string
  threshold_sigma: number
  window: number
  since: string
  up_moves: MoveGroup | null
  down_moves: MoveGroup | null
  events: {
    date: string
    return_pct: number
    sigma_multiple: number
    direction: 'up' | 'down'
    day0_abnormal_pct: number
    post_car_pct: number
  }[]
  note: string
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
  strategySymbols: () => request<SymbolGroup[]>('/api/strategy/symbols'),
  backtest: (body: { symbol: string; start: string; end: string; initial_capital: number }) =>
    post<BacktestResult>('/api/strategy/backtest', body),
  eventStudy: (body: { symbol: string; event_date: string; benchmark: string; window: number }) =>
    post<EventStudyResult>('/api/strategy/event-study', body),
  longShort: (body: {
    strategy: LongShortStrategy
    symbol: string
    start: string
    end: string
    initial_capital: number
    cost_bps: number
    params: Record<string, number>
  }) => post<LongShortResult>('/api/strategy/long-short', body),
  earningsStudy: (body: { symbol: string; benchmark: string; window: number; max_events: number }) =>
    post<EarningsStudyResult>('/api/strategy/event-study/earnings', body),
  largeMoveStudy: (body: {
    symbol: string
    threshold_sigma: number
    benchmark: string
    window: number
    lookback_years: number
  }) => post<LargeMoveStudyResult>('/api/strategy/event-study/large-moves', body),
  chat: (body: {
    agent: string
    messages: ChatMessage[]
    context: { view: View; portfolio_id: string }
  }) => post<{ reply: string }>('/api/chat', body),
}
