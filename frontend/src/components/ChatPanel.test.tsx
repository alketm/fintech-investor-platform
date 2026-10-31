import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from './ChatPanel'

const agents = [
  { id: 'advisor', name: 'Investment advisor', description: 'Main agent' },
  { id: 'news', name: 'News analyst', description: 'Recent headlines' },
]

function mockFetch(reply: string) {
  const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
    const body = url === '/api/agents' ? agents : { reply }
    return new Response(JSON.stringify(body), { status: 200 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => vi.unstubAllGlobals())

describe('ChatPanel', () => {
  it('sends the selected agent, thread and view context', async () => {
    const fetchMock = mockFetch('**Hello** there')
    render(<ChatPanel view="analysis" portfolioId="ira" onClose={() => {}} />)

    await screen.findByRole('option', { name: 'News analyst' })
    fireEvent.change(screen.getByLabelText('Agent'), { target: { value: 'news' } })
    fireEvent.change(screen.getByLabelText('Message'), { target: { value: 'Any VOO news?' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send' }))

    expect(await screen.findByText('Hello')).toBeInTheDocument()
    const [, init] = fetchMock.mock.calls.find(([url]) => url === '/api/chat')!
    expect(JSON.parse(init!.body as string)).toEqual({
      agent: 'news',
      messages: [{ role: 'user', content: 'Any VOO news?' }],
      context: { view: 'analysis', portfolio_id: 'ira' },
    })
  })
})
