import { api } from '../api'
import { money, pct, tone } from '../format'
import { useAsync } from '../useAsync'

export function PortfolioView({ portfolioId }: { portfolioId: string }) {
  const { data, error, loading } = useAsync(() => api.portfolio(portfolioId), portfolioId)

  if (loading) return <p className="muted">Loading prices…</p>
  if (error) return <p className="error">Couldn't load portfolio: {error}</p>
  if (!data) return null

  return (
    <section>
      <div className="stats">
        <Stat label="Market value" value={money(data.total_value)} />
        <Stat label="Cost basis" value={money(data.total_cost)} />
        <Stat
          label="Unrealized gain"
          value={`${money(data.total_gain)} (${pct(data.total_gain_pct)})`}
          className={tone(data.total_gain)}
        />
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Type</th>
              <th className="num">Shares</th>
              <th className="num">Cost / share</th>
              <th className="num">Price</th>
              <th className="num">Market value</th>
              <th className="num">Gain</th>
            </tr>
          </thead>
          <tbody>
            {data.holdings.map((h) => (
              <tr key={h.symbol}>
                <td className="sym">{h.symbol}</td>
                <td>
                  <span className={`tag ${h.type}`}>{h.type.toUpperCase()}</span>
                </td>
                <td className="num">{h.shares}</td>
                <td className="num">{money(h.cost_basis)}</td>
                <td className="num">{money(h.price)}</td>
                <td className="num">{money(h.market_value)}</td>
                <td className={`num ${tone(h.gain)}`}>
                  {money(h.gain)} <small>{pct(h.gain_pct)}</small>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

export function Stat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${className}`}>{value}</div>
    </div>
  )
}
