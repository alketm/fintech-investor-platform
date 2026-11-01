import { type FormEvent, type ReactNode, useEffect, useState } from 'react'
import {
  api,
  type BacktestResult,
  type EarningsStudyResult,
  type EventAggregate,
  type EventStudyResult,
  type LargeMoveStudyResult,
  type LongShortResult,
  type LongShortStrategy,
  type MoveGroup,
  type PathPoint,
  type StrategyStats,
  type SymbolGroup,
} from '../api'
import { LineChart } from '../components/LineChart'
import { money, pct, tone } from '../format'
import { Stat } from './PortfolioView'

export function StrategyView() {
  const [symbols, setSymbols] = useState<SymbolGroup[] | null>(null)
  useEffect(() => {
    api.strategySymbols().then(setSymbols, () => setSymbols(null))
  }, [])
  return (
    <section className="grid-2">
      <Backtest symbols={symbols} />
      <EventStudy symbols={symbols} />
    </section>
  )
}

/** Holdings and sector ETFs grouped in one select; falls back to free text if the list can't load. */
function SymbolSelect({ groups, value, onChange }: {
  groups: SymbolGroup[] | null
  value: string
  onChange: (symbol: string) => void
}) {
  if (!groups) return <input value={value} onChange={(e) => onChange(e.target.value.toUpperCase())} required />
  const seen = new Set<string>()
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}>
      {groups.map((g) => (
        <optgroup key={g.label} label={g.label}>
          {g.symbols
            .filter((s) => !seen.has(s.symbol) && seen.add(s.symbol))
            .map((s) => (
              <option key={s.symbol} value={s.symbol}>
                {s.symbol} · {s.name}
              </option>
            ))}
        </optgroup>
      ))}
    </select>
  )
}

function useRunner<T>() {
  const [result, setResult] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const run = async (fn: () => Promise<T>) => {
    setBusy(true)
    setError(null)
    try {
      setResult(await fn())
    } catch (e) {
      setResult(null)
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }
  const reset = () => {
    setResult(null)
    setError(null)
  }
  return { result, error, busy, run, reset }
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label>
      {label}
      {children}
    </label>
  )
}

function NumberInput({ value, onChange, min, max, step }: {
  value: number
  onChange: (n: number) => void
  min?: number
  max?: number
  step?: number
}) {
  return <input type="number" value={value} min={min} max={max} step={step} onChange={(e) => onChange(Number(e.target.value))} />
}

interface TileOption<T extends string> {
  id: T
  tag: string
  title: string
  description: string
}

/** A radio group drawn as selectable tiles: native radios keep keyboard and screen-reader behavior. */
function Tiles<T extends string>({ name, legend, options, value, onChange }: {
  name: string
  legend: string
  options: TileOption<T>[]
  value: T
  onChange: (id: T) => void
}) {
  return (
    <fieldset className="tiles span-all">
      <legend>{legend}</legend>
      {options.map((o) => (
        <label key={o.id} className={`tile ${o.id === value ? 'selected' : ''}`}>
          <input type="radio" name={name} value={o.id} checked={o.id === value} onChange={() => onChange(o.id)} />
          <span className="tile-tag">{o.tag}</span>
          <span className="tile-title">{o.title}</span>
          <span className="tile-desc">{o.description}</span>
        </label>
      ))}
    </fieldset>
  )
}

// --- backtests ------------------------------------------------------------------------------------------

type BacktestKind = 'buy_and_hold' | LongShortStrategy

const STRATEGIES: TileOption<BacktestKind>[] = [
  {
    id: 'buy_and_hold',
    tag: 'Benchmark',
    title: 'Buy and hold',
    description: 'Buy on the start date and hold to the end.',
  },
  {
    id: 'moving_average',
    tag: 'Long-short · trend',
    title: 'Moving-average crossover',
    description: 'Long when the fast average is above the slow one, short when below.',
  },
  {
    id: 'time_series_momentum',
    tag: 'Long-short · momentum',
    title: 'Time-series momentum',
    description: 'Each month, long after a rising trailing year, short after a falling one.',
  },
  {
    id: 'rsi_mean_reversion',
    tag: 'Long-short · mean reversion',
    title: 'RSI mean reversion',
    description: 'Buy when oversold, short when overbought, exit at the midline.',
  },
  {
    id: 'policy_uncertainty',
    tag: 'Long-short · macro',
    title: 'Policy-rate uncertainty',
    description: 'Kansas City Fed index: short when policy uncertainty spikes, long when it is unusually low.',
  },
]

const PARAMS: Record<
  LongShortStrategy,
  { key: string; label: string; value: number; min?: number; max?: number; step?: number }[]
> = {
  moving_average: [
    { key: 'fast', label: 'Fast average (days)', value: 50, min: 2 },
    { key: 'slow', label: 'Slow average (days)', value: 200, min: 3 },
  ],
  time_series_momentum: [
    { key: 'lookback_days', label: 'Lookback (days)', value: 252, min: 2 },
    { key: 'skip_days', label: 'Skip latest (days)', value: 21, min: 0 },
  ],
  rsi_mean_reversion: [
    { key: 'period', label: 'RSI period', value: 14, min: 2 },
    { key: 'lower', label: 'Go long below', value: 30, min: 1, max: 99 },
    { key: 'upper', label: 'Go short above', value: 70, min: 1, max: 99 },
    { key: 'exit_level', label: 'Exit at', value: 50, min: 1, max: 99 },
  ],
  policy_uncertainty: [
    { key: 'lookback_days', label: 'Lookback (days)', value: 252, min: 20 },
    { key: 'threshold', label: 'Threshold (std devs)', value: 0.5, min: 0, step: 0.25 },
    { key: 'signal_lag_days', label: 'Signal lag (days)', value: 1, min: 0 },
  ],
}

const defaults = (kind: LongShortStrategy) => Object.fromEntries(PARAMS[kind].map((p) => [p.key, p.value]))

function Backtest({ symbols }: { symbols: SymbolGroup[] | null }) {
  const [kind, setKind] = useState<BacktestKind>('buy_and_hold')
  const [form, setForm] = useState({ symbol: 'VTI', start: '2020-01-01', end: '2025-01-01', initial_capital: 10000, cost_bps: 5 })
  const [params, setParams] = useState<Record<string, number>>({})
  const hold = useRunner<BacktestResult>()
  const longShort = useRunner<LongShortResult>()
  const busy = hold.busy || longShort.busy

  const choose = (next: BacktestKind) => {
    setKind(next)
    setParams(next === 'buy_and_hold' ? {} : defaults(next))
    hold.reset()
    longShort.reset()
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (kind === 'buy_and_hold') {
      const { symbol, start, end, initial_capital } = form
      hold.run(() => api.backtest({ symbol, start, end, initial_capital }))
    } else {
      longShort.run(() => api.longShort({ strategy: kind, ...form, params }))
    }
  }

  return (
    <div className="card">
      <h3>Backtest</h3>
      <form className="form" onSubmit={submit}>
        <Tiles name="strategy" legend="Strategy" options={STRATEGIES} value={kind} onChange={choose} />
        <Field label="Symbol">
          <SymbolSelect groups={symbols} value={form.symbol} onChange={(symbol) => setForm({ ...form, symbol })} />
        </Field>
        <Field label="Start">
          <input type="date" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} required />
        </Field>
        <Field label="End">
          <input type="date" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} required />
        </Field>
        <Field label="Initial capital">
          <NumberInput value={form.initial_capital} min={1} onChange={(n) => setForm({ ...form, initial_capital: n })} />
        </Field>
        {kind !== 'buy_and_hold' && (
          <>
            <Field label="Cost (bps per trade)">
              <NumberInput value={form.cost_bps} min={0} step={0.5} onChange={(n) => setForm({ ...form, cost_bps: n })} />
            </Field>
            {PARAMS[kind].map((p) => (
              <Field key={p.key} label={p.label}>
                <NumberInput
                  value={params[p.key] ?? p.value}
                  min={p.min}
                  max={p.max}
                  step={p.step}
                  onChange={(n) => setParams({ ...params, [p.key]: n })}
                />
              </Field>
            ))}
          </>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Running…' : 'Run backtest'}
        </button>
      </form>
      {(hold.error || longShort.error) && <p className="error">{hold.error || longShort.error}</p>}
      {kind === 'buy_and_hold' && hold.result && <BuyAndHoldResult result={hold.result} />}
      {kind !== 'buy_and_hold' && longShort.result && <LongShortView result={longShort.result} />}
    </div>
  )
}

function BuyAndHoldResult({ result }: { result: BacktestResult }) {
  return (
    <div className="stats compact">
      <Stat label="Total return" value={pct(result.total_return_pct)} className={tone(result.total_return_pct)} />
      <Stat label="CAGR" value={pct(result.cagr_pct)} className={tone(result.cagr_pct)} />
      <Stat label="Volatility (ann.)" value={`${result.annualized_volatility_pct.toFixed(2)}%`} />
      <Stat label="Max drawdown" value={pct(result.max_drawdown_pct)} className="neg" />
      <Stat label="Final value" value={money(result.final_value)} />
      <Stat label="Period" value={`${result.start} → ${result.end}`} />
    </div>
  )
}

const STAT_ROWS: { key: keyof StrategyStats; label: string; show: (v: number | null) => string; colored?: boolean }[] = [
  { key: 'total_return_pct', label: 'Total return', show: (v) => pct(v), colored: true },
  { key: 'cagr_pct', label: 'CAGR', show: (v) => pct(v), colored: true },
  { key: 'annualized_volatility_pct', label: 'Volatility (ann.)', show: (v) => (v == null ? '—' : `${v.toFixed(2)}%`) },
  { key: 'sharpe_ratio', label: 'Sharpe (0% rf)', show: (v) => (v == null ? '—' : v.toFixed(2)) },
  { key: 'max_drawdown_pct', label: 'Max drawdown', show: (v) => pct(v) },
  { key: 'final_value', label: 'Final value', show: (v) => (v == null ? '—' : money(v)) },
]

function LongShortView({ result }: { result: LongShortResult }) {
  const a = result.activity
  return (
    <div className="result">
      <p className="muted rule">{result.rule}</p>
      <table>
        <thead>
          <tr>
            <th>{result.start} → {result.end}</th>
            <th className="num">Strategy</th>
            <th className="num">Buy and hold</th>
          </tr>
        </thead>
        <tbody>
          {STAT_ROWS.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              {[result.strategy, result.buy_and_hold].map((s, i) => (
                <td key={i} className={`num ${row.colored ? tone(s[row.key]) : ''}`}>
                  {row.show(s[row.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <LineChart
        dates={result.equity_curve.map((p) => p.date)}
        series={[
          { label: 'Strategy', values: result.equity_curve.map((p) => p.strategy), className: 'series-a' },
          { label: 'Buy and hold', values: result.equity_curve.map((p) => p.buy_and_hold), className: 'series-b' },
        ]}
        format={(n) => money(n).replace(/\.\d+$/, '')}
      />
      {result.uncertainty && (
        <div className="stats compact">
          <Stat
            label={`KC PRU on ${result.uncertainty.value_date ?? '—'}`}
            value={result.uncertainty.value_at_end == null ? '—' : `${result.uncertainty.value_at_end.toFixed(2)} pts`}
          />
          <Stat label="Z-score at end" value={result.uncertainty.zscore_at_end?.toFixed(2) ?? '—'} />
          <Stat
            label="High / low / neutral"
            value={`${result.uncertainty.pct_days_high} / ${result.uncertainty.pct_days_low} / ${result.uncertainty.pct_days_neutral}%`}
          />
        </div>
      )}
      <div className="stats compact">
        <Stat label="Position changes" value={String(a.position_changes)} />
        <Stat label="Long / short / flat" value={`${a.pct_days_long} / ${a.pct_days_short} / ${a.pct_days_flat}%`} />
        <Stat label="Win rate" value={a.win_rate_pct == null ? '—' : `${a.win_rate_pct}% of ${a.closed_trades}`} />
        <Stat label="Costs paid" value={money(a.total_costs)} />
        <Stat label="Position now" value={a.current_position} />
      </div>
      <p className="muted small">{result.assumptions}</p>
    </div>
  )
}

// --- event studies --------------------------------------------------------------------------------------

type StudyKind = 'single' | 'earnings' | 'large_moves'

const STUDIES: TileOption<StudyKind>[] = [
  { id: 'single', tag: 'One event', title: 'Single date', description: 'Abnormal returns around a date you choose.' },
  {
    id: 'earnings',
    tag: 'Recurring',
    title: 'Earnings announcements',
    description: 'Average reaction to past earnings, split into beats and misses.',
  },
  {
    id: 'large_moves',
    tag: 'Detected',
    title: 'Large daily moves',
    description: 'What tends to follow unusually big up or down days.',
  },
]

function EventStudy({ symbols }: { symbols: SymbolGroup[] | null }) {
  const [kind, setKind] = useState<StudyKind>('single')
  const [symbol, setSymbol] = useState('NVDA')
  const [benchmark, setBenchmark] = useState('SPY')
  const [eventDate, setEventDate] = useState('2024-05-23')
  const [window, setWindow] = useState(5)
  const [maxEvents, setMaxEvents] = useState(12)
  const [sigma, setSigma] = useState(2.5)
  const [years, setYears] = useState(5)
  const single = useRunner<EventStudyResult>()
  const earnings = useRunner<EarningsStudyResult>()
  const moves = useRunner<LargeMoveStudyResult>()
  const busy = single.busy || earnings.busy || moves.busy
  const error = single.error || earnings.error || moves.error

  const choose = (next: StudyKind) => {
    setKind(next)
    setWindow(next === 'large_moves' ? 10 : 5)
    ;[single, earnings, moves].forEach((r) => r.reset())
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (kind === 'single') single.run(() => api.eventStudy({ symbol, event_date: eventDate, benchmark, window }))
    if (kind === 'earnings') earnings.run(() => api.earningsStudy({ symbol, benchmark, window, max_events: maxEvents }))
    if (kind === 'large_moves')
      moves.run(() => api.largeMoveStudy({ symbol, threshold_sigma: sigma, benchmark, window, lookback_years: years }))
  }

  return (
    <div className="card">
      <h3>Event study · market model</h3>
      <form className="form" onSubmit={submit}>
        <Tiles name="event-type" legend="Event type" options={STUDIES} value={kind} onChange={choose} />
        <Field label="Symbol">
          <SymbolSelect groups={symbols} value={symbol} onChange={setSymbol} />
        </Field>
        {kind === 'single' && (
          <Field label="Event date">
            <input type="date" value={eventDate} onChange={(e) => setEventDate(e.target.value)} required />
          </Field>
        )}
        <Field label="Benchmark">
          <input value={benchmark} onChange={(e) => setBenchmark(e.target.value.toUpperCase())} required />
        </Field>
        <Field label={kind === 'large_moves' ? 'Days after (window)' : 'Window (± days)'}>
          <NumberInput value={window} min={1} max={30} onChange={setWindow} />
        </Field>
        {kind === 'earnings' && (
          <Field label="Past announcements">
            <NumberInput value={maxEvents} min={1} max={40} onChange={setMaxEvents} />
          </Field>
        )}
        {kind === 'large_moves' && (
          <>
            <Field label="Threshold (× volatility)">
              <NumberInput value={sigma} min={0.5} step={0.5} onChange={setSigma} />
            </Field>
            <Field label="Lookback (years)">
              <NumberInput value={years} min={1} max={20} onChange={setYears} />
            </Field>
          </>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Running…' : 'Run event study'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {kind === 'single' && single.result && <SingleEventView result={single.result} />}
      {kind === 'earnings' && earnings.result && <EarningsView result={earnings.result} />}
      {kind === 'large_moves' && moves.result && <LargeMovesView result={moves.result} />}
    </div>
  )
}

function ArBars({ rows, highlightDay = 0 }: { rows: { day: number; label?: string; ar: number; car: number }[]; highlightDay?: number }) {
  const maxAbs = Math.max(...rows.map((r) => Math.abs(r.ar)), 0.01)
  return (
    <table>
      <thead>
        <tr>
          <th>Day</th>
          {rows.some((r) => r.label) && <th>Date</th>}
          <th className="num">Abnormal</th>
          <th className="ar-col" />
          <th className="num">CAR</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.day} className={r.day === highlightDay ? 'highlight' : ''}>
            <td>{r.day}</td>
            {r.label && <td>{r.label}</td>}
            <td className={`num ${tone(r.ar)}`}>{pct(r.ar)}</td>
            <td className="ar-col">
              <span className="ar-track">
                <span className={`ar-bar ${tone(r.ar)}`} style={{ width: `${(Math.abs(r.ar) / maxAbs) * 50}%` }} />
              </span>
            </td>
            <td className={`num ${tone(r.car)}`}>{pct(r.car)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

const pathRows = (path: PathPoint[]) => path.map((p) => ({ day: p.day, ar: p.abnormal_return_pct, car: p.car_pct }))

function SingleEventView({ result }: { result: EventStudyResult }) {
  return (
    <div className="result">
      <div className="stats compact">
        <Stat label="CAR" value={pct(result.car_pct)} className={tone(result.car_pct)} />
        <Stat label="t-stat" value={result.car_t_stat?.toFixed(2) ?? '—'} />
        <Stat label="Beta" value={result.beta.toFixed(2)} />
        <Stat label="Event day" value={result.event_day} />
      </div>
      <ArBars rows={result.series.map((p) => ({ day: p.day, label: p.date, ar: p.abnormal_return_pct, car: p.car_pct }))} />
    </div>
  )
}

function AggregateTable({ groups }: { groups: [string, EventAggregate | MoveGroup | null][] }) {
  const moveCols = groups.some(([, g]) => g && 'pct_continuing' in g)
  return (
    <table>
      <thead>
        <tr>
          <th />
          <th className="num">Events</th>
          {moveCols && <th className="num">Avg move</th>}
          <th className="num">Avg CAR</th>
          <th className="num">t-stat</th>
          <th className="num">{moveCols ? 'Continuing' : 'Positive'}</th>
        </tr>
      </thead>
      <tbody>
        {groups.map(([name, g]) => (
          <tr key={name}>
            <td>{name}</td>
            {g ? (
              <>
                <td className="num">{g.events}</td>
                {moveCols && <td className={`num ${tone((g as MoveGroup).average_move_pct)}`}>{pct((g as MoveGroup).average_move_pct)}</td>}
                <td className={`num ${tone(g.average_car_pct)}`}>{pct(g.average_car_pct)}</td>
                <td className="num">{g.t_stat?.toFixed(2) ?? '—'}</td>
                <td className="num">{moveCols ? (g as MoveGroup).pct_continuing : g.pct_positive}%</td>
              </>
            ) : (
              <td className="muted" colSpan={moveCols ? 5 : 4}>
                no events
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function EarningsView({ result }: { result: EarningsStudyResult }) {
  return (
    <div className="result">
      <AggregateTable groups={[['All', result.aggregate], ['EPS beats', result.beats], ['EPS misses', result.misses]]} />
      <h4>Average abnormal return by day ({result.aggregate.events} announcements)</h4>
      <ArBars rows={pathRows(result.aggregate.average_path)} />
      <h4>Announcements</h4>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Reported</th>
              <th>Timing</th>
              <th className="num">Surprise</th>
              <th className="num">Day 0</th>
              <th className="num">CAR −1..+1</th>
            </tr>
          </thead>
          <tbody>
            {[...result.events].reverse().map((e) => (
              <tr key={e.announced}>
                <td>{e.announced}</td>
                <td className="muted">{e.timing}</td>
                <td className={`num ${tone(e.surprise_pct)}`}>{pct(e.surprise_pct, 1)}</td>
                <td className={`num ${tone(e.day0_abnormal_pct)}`}>{pct(e.day0_abnormal_pct)}</td>
                <td className={`num ${tone(e.car_m1_p1_pct)}`}>{pct(e.car_m1_p1_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{result.note}</p>
    </div>
  )
}

function LargeMovesView({ result }: { result: LargeMoveStudyResult }) {
  return (
    <div className="result">
      <p className="muted rule">
        Moves above {result.threshold_sigma}× the prior 60-day volatility since {result.since}; CAR over the next{' '}
        {result.window} days.
      </p>
      <AggregateTable groups={[['Up moves', result.up_moves], ['Down moves', result.down_moves]]} />
      <p className="muted small">
        After up moves: {result.up_moves?.read ?? 'no events'} · After down moves:{' '}
        {result.down_moves?.read ?? 'no events'} (|t| ≥ 2 counts as significant)
      </p>
      <h4>Events</h4>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th className="num">Move</th>
              <th className="num">× vol</th>
              <th className="num">Next {result.window}d CAR</th>
            </tr>
          </thead>
          <tbody>
            {[...result.events].reverse().map((e) => (
              <tr key={e.date}>
                <td>{e.date}</td>
                <td className={`num ${tone(e.return_pct)}`}>{pct(e.return_pct)}</td>
                <td className="num">{Math.abs(e.sigma_multiple).toFixed(1)}</td>
                <td className={`num ${tone(e.post_car_pct)}`}>{pct(e.post_car_pct)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small">{result.note}</p>
    </div>
  )
}
