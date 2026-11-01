import { useState } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { api, type View } from './api'
import { ChatPanel } from './components/ChatPanel'
import { useAsync } from './useAsync'
import { AnalysisView } from './views/AnalysisView'
import { PortfolioView } from './views/PortfolioView'
import { StrategyView } from './views/StrategyView'

const VIEWS: { path: string; view: View; label: string }[] = [
  { path: '/portfolio', view: 'portfolio', label: 'Portfolio' },
  { path: '/analysis', view: 'analysis', label: 'Analysis' },
  { path: '/strategy', view: 'strategy', label: 'Strategies' },
]

export default function App() {
  const location = useLocation()
  const current = VIEWS.find((v) => location.pathname.startsWith(v.path)) ?? VIEWS[0]
  const view = current.view
  const portfolios = useAsync(api.portfolios, 'portfolios')
  const [portfolioId, setPortfolioId] = useState('brokerage')
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className={`app ${chatOpen ? 'with-chat' : ''}`}>
      <aside className="sidebar">
        <div className="brand">Alko Investment Advisor</div>
        <nav aria-label="Views">
          {VIEWS.map((v) => (
            <NavLink key={v.path} to={v.path}>
              {v.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="content">
        <header className="topbar">
          <h1>{current.label}</h1>
          <div className="topbar-actions">
            {view !== 'strategy' && (
              <select value={portfolioId} onChange={(e) => setPortfolioId(e.target.value)} aria-label="Portfolio">
                {(portfolios.data ?? []).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            )}
            <button onClick={() => setChatOpen((o) => !o)}>{chatOpen ? 'Hide chat' : 'Ask an agent'}</button>
          </div>
        </header>

        <main>
          {portfolios.error && <p className="error">Backend unreachable: {portfolios.error}</p>}
          <Routes>
            <Route path="/" element={<Navigate to="/portfolio" replace />} />
            <Route path="/portfolio" element={<PortfolioView portfolioId={portfolioId} />} />
            <Route path="/analysis" element={<AnalysisView portfolioId={portfolioId} />} />
            <Route path="/strategy" element={<StrategyView />} />
          </Routes>
        </main>
      </div>

      {chatOpen && <ChatPanel view={view} portfolioId={portfolioId} onClose={() => setChatOpen(false)} />}
    </div>
  )
}
