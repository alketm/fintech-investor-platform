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
  symbol: 'XLK',
  rule: 'Long when the 20-day average is above the 100-day average, short when below.',
  parameters: { fast: 20, slow: 100, cost_bps: 5 },
  start: '2020-01-02',
  end: '2024-12-31',
  trading_days: 1257,
  strategy: stats,
  buy_and_hold: { ...stats, total_return_pct: 80, final_value: 18000 },
  benchmark: { ...stats, symbol: 'SPY', total_return_pct: 90, final_value: 19000 },
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
    { date: '2020-01-03', strategy: 10000, buy_and_hold: 10000, benchmark: 10000 },
    { date: '2024-12-27', strategy: 12500, buy_and_hold: 18000, benchmark: 19000 },
  ],
  assumptions: 'Signals at a close trade from the next day.',
}

const symbols = [
  { label: 'Brokerage holdings', symbols: [{ symbol: 'NVDA', name: 'STOCK' }, { symbol: 'VTI', name: 'ETF' }] },
  { label: 'IRA holdings', symbols: [{ symbol: 'VTI', name: 'ETF' }, { symbol: 'SCHD', name: 'ETF' }] },
  { label: 'Sector ETFs', symbols: [{ symbol: 'XLK', name: 'Technology' }, { symbol: 'XLE', name: 'Energy' }] },
]

/** Serves the symbol list, and `result` for every other request. */
function stubFetch(result: unknown = longShort) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) =>
    new Response(JSON.stringify(url === '/api/strategy/symbols' ? symbols : result)),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('StrategyView', () => {
  it('runs a long-short backtest with the chosen strategy and parameters', async () => {
    const fetchMock = stubFetch()
    render(<StrategyView />)

    const [backtestSymbol] = await screen.findAllByRole('combobox', { name: 'Symbol' })
    fireEvent.change(backtestSymbol, { target: { value: 'XLK' } })
    fireEvent.click(screen.getByRole('radio', { name: /Moving-average crossover/ }))
    fireEvent.change(screen.getByLabelText('Fast average (days)'), { target: { value: '20' } })
    fireEvent.change(screen.getByLabelText('Slow average (days)'), { target: { value: '100' } })
    fireEvent.click(screen.getByRole('button', { name: 'Run backtest' }))

    expect(await screen.findByText(longShort.rule)).toBeInTheDocument()
    expect(screen.getByText('+80.00%')).toBeInTheDocument()
    expect(screen.getByText('+90.00%')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'SPY buy & hold' })).toBeInTheDocument()
    expect(
      screen.getByRole('img', { name: 'Long-short strategy vs XLK buy and hold vs SPY buy and hold' }),
    ).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls.find(([u]) => u === '/api/strategy/long-short')!
    expect(url).toBe('/api/strategy/long-short')
    expect(JSON.parse(init!.body as string)).toMatchObject({
      strategy: 'moving_average',
      symbol: 'XLK',
      cost_bps: 5,
      params: { fast: 20, slow: 100 },
    })
  })

  it('compares buy and hold with SPY in a table and chart', async () => {
    const curve = [
      { date: '2020-01-03', buy_and_hold: 10000, benchmark: 10000 },
      { date: '2024-12-27', buy_and_hold: 26000, benchmark: 19000 },
    ]
    stubFetch({
      ...stats,
      symbol: 'XLK',
      start: '2020-01-02',
      end: '2024-12-31',
      trading_days: 1258,
      initial_capital: 10000,
      total_return_pct: 160,
      benchmark: { ...stats, symbol: 'SPY', total_return_pct: 90 },
      equity_curve: curve,
    })
    render(<StrategyView />)
    fireEvent.click(screen.getByRole('button', { name: 'Run backtest' }))
    expect(await screen.findByRole('img', { name: 'XLK buy and hold vs SPY buy and hold' })).toBeInTheDocument()
    expect(screen.getByText('+160.00%')).toBeInTheDocument()
    expect(screen.getByText('+90.00%')).toBeInTheDocument()
  })

  it('offers holdings and sector ETFs as grouped symbols, without duplicates', async () => {
    stubFetch()
    render(<StrategyView />)
    const [backtestSymbol, eventSymbol] = await screen.findAllByRole('combobox', { name: 'Symbol' })
    expect(backtestSymbol).toHaveValue('VTI')
    expect(eventSymbol).toHaveValue('NVDA')
    const options = within(backtestSymbol).getAllByRole('option').map((o) => o.getAttribute('value'))
    expect(options).toEqual(['NVDA', 'VTI', 'SCHD', 'XLK', 'XLE'])
    expect(backtestSymbol.querySelectorAll('optgroup')[2]).toHaveAttribute('label', 'Sector ETFs')
  })

  it('shows strategies and event types as tiles with one selected', () => {
    stubFetch()
    render(<StrategyView />)
    const strategy = screen.getByRole('group', { name: 'Strategy' })
    expect(within(strategy).getAllByRole('radio')).toHaveLength(7)
    expect(within(strategy).getByRole('radio', { name: /Buy and hold/ })).toBeChecked()
    expect(within(screen.getByRole('group', { name: 'Event type' })).getAllByRole('radio')).toHaveLength(3)
  })

  it('sets the consumer sentiment strategy to the last 10 years with monthly parameters', () => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-10-31T12:00:00Z'))
    stubFetch()
    render(<StrategyView />)
    fireEvent.click(screen.getByRole('radio', { name: /Consumer sentiment bands/ }))
    expect(screen.getByLabelText('Start')).toHaveValue('2016-10-31')
    expect(screen.getByLabelText('End')).toHaveValue('2026-10-31')
    expect(screen.getByLabelText('Moving average (months)')).toHaveValue(3)
    expect(screen.getByLabelText('Go long above (% of avg)')).toHaveValue(97)
    expect(screen.getByLabelText('Go short below (% of avg)')).toHaveValue(95)
    expect(screen.getByLabelText('Back to neutral at (% of avg)')).toHaveValue(96)
    vi.useRealTimers()
  })

  it('shows the Monetary Policy Uncertainty thresholds as parameters', () => {
    stubFetch()
    render(<StrategyView />)
    fireEvent.click(screen.getByRole('radio', { name: /Monetary Policy Uncertainty/ }))
    expect(screen.getByLabelText('Moving average (days)')).toHaveValue(21)
    expect(screen.getByLabelText('Go short above (× avg)')).toHaveValue(1.4)
    expect(screen.getByLabelText('Go long below (× avg)')).toHaveValue(1.2)
    expect(screen.getByLabelText('Back to neutral at (× avg)')).toHaveValue(1.3)
  })

  it('shows the VIX strategy thresholds as parameters', () => {
    stubFetch()
    render(<StrategyView />)
    fireEvent.click(screen.getByRole('radio', { name: /VIX vs realized volatility/ }))
    expect(screen.getByLabelText('Realized vol window (days)')).toHaveValue(20)
    expect(screen.getByLabelText('Go short above (× realized)')).toHaveValue(2)
    expect(screen.getByLabelText('Go long below (× realized)')).toHaveValue(1.7)
    expect(screen.getByLabelText('Back to neutral at (× realized)')).toHaveValue(1.8)
  })

  it('shows inputs that match the chosen event study', () => {
    stubFetch()
    render(<StrategyView />)
    expect(screen.getByLabelText('Event date')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: /Large daily moves/ }))
    expect(screen.getByRole('radio', { name: /Large daily moves/ })).toBeChecked()
    expect(screen.queryByLabelText('Event date')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Threshold (× volatility)')).toBeInTheDocument()
    expect(screen.getByLabelText('Days after (window)')).toHaveValue(10)
  })
})
