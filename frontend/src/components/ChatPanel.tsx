import { type FormEvent, useEffect, useRef, useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { type AgentInfo, api, type ChatMessage, type View } from '../api'

interface Props {
  view: View
  portfolioId: string
  onClose: () => void
}

/** Chat with the advisor or a focused agent. Each agent keeps its own thread. */
export function ChatPanel({ view, portfolioId, onClose }: Props) {
  const [agents, setAgents] = useState<AgentInfo[]>([])
  const [agent, setAgent] = useState('advisor')
  const [threads, setThreads] = useState<Record<string, ChatMessage[]>>({})
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    api.agents().then(setAgents, (e: Error) => setError(e.message))
  }, [])

  const messages = threads[agent] ?? []

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ behavior: 'smooth' })
  }, [messages.length, busy])

  const send = async (e: FormEvent) => {
    e.preventDefault()
    const text = input.trim()
    if (!text || busy) return
    const next: ChatMessage[] = [...messages, { role: 'user', content: text }]
    setThreads((t) => ({ ...t, [agent]: next }))
    setInput('')
    setBusy(true)
    setError(null)
    try {
      const { reply } = await api.chat({ agent, messages: next, context: { view, portfolio_id: portfolioId } })
      setThreads((t) => ({ ...t, [agent]: [...next, { role: 'assistant', content: reply }] }))
    } catch (err) {
      // Drop the unanswered question so the thread stays user/assistant alternating.
      setThreads((t) => ({ ...t, [agent]: messages }))
      setInput(text)
      setError((err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const current = agents.find((a) => a.id === agent)

  return (
    <aside className="chat" aria-label="Chat">
      <header className="chat-head">
        <select value={agent} onChange={(e) => setAgent(e.target.value)} aria-label="Agent" disabled={busy}>
          {(agents.length ? agents : [{ id: 'advisor', name: 'Investment advisor', description: '' }]).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <button className="ghost" onClick={onClose} aria-label="Close chat">
          ✕
        </button>
      </header>
      {current?.description && <p className="chat-desc">{current.description}</p>}

      <div className="chat-log">
        {messages.length === 0 && (
          <p className="muted">Ask about your {view === 'strategy' ? 'strategy ideas' : 'portfolio'}. The agent sees which view you're on.</p>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === 'assistant' ? <Markdown remarkPlugins={[remarkGfm]}>{m.content}</Markdown> : m.content}
          </div>
        ))}
        {busy && <div className="msg assistant muted">Thinking…</div>}
        <div ref={endRef} />
      </div>

      {error && <p className="error chat-error">{error}</p>}
      <form className="chat-input" onSubmit={send}>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) send(e)
          }}
          placeholder="Message…"
          rows={2}
          aria-label="Message"
        />
        <button type="submit" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </aside>
  )
}
