import { type FormEvent, useState } from 'react'
import { api, type BacktestResult, type EventStudyResult } from '../api'
import { money, pct, tone } from '../format'
import { Stat } from './PortfolioView'

export function StrategyView() {
  return (
    <section className="grid-2">
      <Backtest />
      <EventStudy />
    </section>
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
  return { result, error, busy, run }
}

function Backtest() {
  const [form, setForm] = useState({ symbol: 'SPY', start: '2020-01-01', end: '2025-01-01', initial_capital: 10000 })
  const { result, error, busy, run } = useRunner<BacktestResult>()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    run(() => api.backtest(form))
  }

  return (
    <div className="card">
      <h3>Backtest · buy and hold</h3>
      <form className="form" onSubmit={submit}>
        <label>
          Symbol
          <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} required />
        </label>
        <label>
          Start
          <input type="date" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} required />
        </label>
        <label>
          End
          <input type="date" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} required />
        </label>
        <label>
          Initial capital
          <input
            type="number"
            min={1}
            value={form.initial_capital}
            onChange={(e) => setForm({ ...form, initial_capital: Number(e.target.value) })}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Running…' : 'Run backtest'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <div className="stats compact">
          <Stat label="Total return" value={pct(result.total_return_pct)} className={tone(result.total_return_pct)} />
          <Stat label="CAGR" value={pct(result.cagr_pct)} className={tone(result.cagr_pct)} />
          <Stat label="Volatility (ann.)" value={`${result.annualized_volatility_pct.toFixed(2)}%`} />
          <Stat label="Max drawdown" value={pct(result.max_drawdown_pct)} className="neg" />
          <Stat label="Final value" value={money(result.final_value)} />
          <Stat label="Period" value={`${result.start} → ${result.end}`} />
        </div>
      )}
    </div>
  )
}

function EventStudy() {
  const [form, setForm] = useState({ symbol: 'NVDA', event_date: '2024-05-23', benchmark: 'SPY', window: 5 })
  const { result, error, busy, run } = useRunner<EventStudyResult>()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    run(() => api.eventStudy(form))
  }
  const maxAbs = result ? Math.max(...result.series.map((p) => Math.abs(p.abnormal_return_pct)), 0.01) : 1

  return (
    <div className="card">
      <h3>Event study · market model</h3>
      <form className="form" onSubmit={submit}>
        <label>
          Symbol
          <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value.toUpperCase() })} required />
        </label>
        <label>
          Event date
          <input type="date" value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })} required />
        </label>
        <label>
          Benchmark
          <input value={form.benchmark} onChange={(e) => setForm({ ...form, benchmark: e.target.value.toUpperCase() })} required />
        </label>
        <label>
          Window (± days)
          <input
            type="number"
            min={1}
            max={30}
            value={form.window}
            onChange={(e) => setForm({ ...form, window: Number(e.target.value) })}
          />
        </label>
        <button type="submit" disabled={busy}>
          {busy ? 'Running…' : 'Run event study'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
      {result && (
        <>
          <div className="stats compact">
            <Stat label="CAR" value={pct(result.car_pct)} className={tone(result.car_pct)} />
            <Stat label="t-stat" value={result.car_t_stat?.toFixed(2) ?? '—'} />
            <Stat label="Beta" value={result.beta.toFixed(2)} />
            <Stat label="Event day" value={result.event_day} />
          </div>
          <table>
            <thead>
              <tr>
                <th>Day</th>
                <th>Date</th>
                <th className="num">Abnormal</th>
                <th className="ar-col" />
                <th className="num">CAR</th>
              </tr>
            </thead>
            <tbody>
              {result.series.map((p) => (
                <tr key={p.day} className={p.day === 0 ? 'highlight' : ''}>
                  <td>{p.day}</td>
                  <td>{p.date}</td>
                  <td className={`num ${tone(p.abnormal_return_pct)}`}>{pct(p.abnormal_return_pct)}</td>
                  <td className="ar-col">
                    <span className="ar-track">
                      <span
                        className={`ar-bar ${tone(p.abnormal_return_pct)}`}
                        style={{ width: `${(Math.abs(p.abnormal_return_pct) / maxAbs) * 50}%` }}
                      />
                    </span>
                  </td>
                  <td className={`num ${tone(p.car_pct)}`}>{pct(p.car_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  )
}
