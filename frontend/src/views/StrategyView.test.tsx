import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { StrategyView } from './StrategyView'

const stats = {
  total_return_pct: 25,
  cagr_pct: 5,
  annualized_volatility_pct: 15,
  sharpe_ratio: 0.4,
  max_drawdown_pct: -20,
  final_value: 12500,
}

const longShort = {
  symbol: 'SPY',
  rule: 'Long when the 20-day average is above the 100-day average, short when below.',
  parameters: { fast: 20, slow: 100, cost_bps: 5 },
  start: '2020-01-02',
  end: '2024-12-31',
  trading_days: 1257,
  strategy: stats,
  buy_and_hold: { ...stats, total_return_pct: 80, final_value: 18000 },
  activity: {
    position_changes: 12,
    pct_days_long: 70,
    pct_days_short: 30,
    pct_days_flat: 0,
    closed_trades: 11,
    win_rate_pct: 45.5,
    total_costs: 60,
    current_position: 'long',
  },
  equity_curve: [
    { date: '2020-01-03', strategy: 10000, buy_and_hold: 10000 },
    { date: '2024-12-27', strategy: 12500, buy_and_hold: 18000 },
  ],
  assumptions: 'Signals at a close trade from the next day.',
}

afterEach(() => vi.unstubAllGlobals())

describe('StrategyView', () => {
  it('runs a long-short backtest with the chosen strategy and parameters', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify(longShort)))
    vi.stubGlobal('fetch', fetchMock)
    render(<StrategyView />)

    fireEvent.click(screen.getByRole('radio', { name: /Moving-average crossover/ }))
    fireEvent.change(screen.getByLabelText('Fast average (days)'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Slow average (days)'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Run backtest' }))

    expect(await screen.findByText(longShort.rule)).toBeInTheDocument()
    expect(screen.getByText('+80.00%')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Strategy vs Buy and hold' })).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/strategy/long-short')
    expect(JSON.parse(init!.body as string)).toMatchObject({
      strategy: 'moving_average',
      symbol: 'SPY',
      cost_bps: 5,
      params: { fast: 20, slow: 100 },
    })
  })

  it('shows strategies and event types as tiles with one selected', () => {
    render(<StrategyView />)
    const strategy = screen.getByRole('group', { name: 'Strategy' })
    expect(within(strategy).getAllByRole('radio')).toHaveLength(4)
    expect(within(strategy).getByRole('radio', { name: /Buy and hold/ })).toBeChecked()
    expect(within(screen.getByRole('group', { name: 'Event type' })).getAllByRole('radio')).toHaveLength(3)
  })

  it('shows inputs that match the chosen event study', () => {
    render(<StrategyView />)
    expect(screen.getByLabelText('Event date')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: /Large daily moves/ }))
    expect(screen.getByRole('radio', { name: /Large daily moves/ })).toBeChecked()
    expect(screen.queryByLabelText('Event date')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Threshold (× volatility)')).toBeInTheDocument()
    expect(screen.getByLabelText('Days after (window)')).toHaveValue(10)
  })
})
