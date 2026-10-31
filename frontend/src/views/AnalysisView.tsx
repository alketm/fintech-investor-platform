import { api } from '../api'
import { money, pct, tone, weight } from '../format'
import { useAsync } from '../useAsync'
import { Stat } from './PortfolioView'

export function AnalysisView({ portfolioId }: { portfolioId: string }) {
  const { data, error, loading } = useAsync(() => api.analysis(portfolioId), portfolioId)

  if (loading) return <p className="muted">Analyzing…</p>
  if (error) return <p className="error">Couldn't load analysis: {error}</p>
  if (!data) return null

  return (
    <section>
      <div className="stats">
        <Stat label="Market value" value={money(data.total_value)} />
        <Stat
          label="Largest position"
          value={data.largest_position ? `${data.largest_position.symbol} · ${weight(data.largest_position.weight_pct)}` : '—'}
        />
        <Stat label="Top 3 weight" value={weight(data.top3_weight_pct)} />
      </div>

      <div className="grid-2">
        <div className="card">
          <h3>Allocation by holding</h3>
          <Bars rows={data.by_holding.map((h) => ({ label: h.symbol, value: h.weight_pct, kind: h.type }))} />
        </div>
        <div className="card">
          <h3>Allocation by asset type</h3>
          <Bars rows={data.by_type.map((t) => ({ label: t.type.toUpperCase(), value: t.weight_pct, kind: t.type }))} />
          <h3 className="spaced">Unrealized gain by position</h3>
          <table>
            <tbody>
              {data.by_holding.map((h) => (
                <tr key={h.symbol}>
                  <td className="sym">{h.symbol}</td>
                  <td className={`num ${tone(h.gain)}`}>{money(h.gain)}</td>
                  <td className={`num ${tone(h.gain_pct)}`}>{pct(h.gain_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function Bars({ rows }: { rows: { label: string; value: number; kind: string }[] }) {
  return (
    <ul className="bars">
      {rows.map((r) => (
        <li key={r.label}>
          <span className="bar-label">{r.label}</span>
          <span className="bar-track">
            <span className={`bar-fill ${r.kind}`} style={{ width: `${r.value}%` }} />
          </span>
          <span className="bar-value">{weight(r.value)}</span>
        </li>
      ))}
    </ul>
  )
}
