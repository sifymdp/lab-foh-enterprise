import { useEffect, useRef, useState } from 'react'
import { aiApi, type ChatAction, type ChatMessage } from '../../api/extensions'
import { useFloor } from '../../context/FloorContext'

interface ChatEntry extends ChatMessage {
  actions?: ChatAction[]
  error?: boolean
}

const SUGGESTIONS = [
  'Which tables are free right now?',
  'Seat a party of 4',
  "What are today's shift stats?",
  'Any reservations coming up?',
]

export function AIChatWidget() {
  const { refresh } = useFloor()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [busy, setBusy] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  async function send(text: string) {
    const trimmed = text.trim()
    if (!trimmed || busy) return
    const history = [...messages, { role: 'user' as const, content: trimmed }]
    setMessages(history)
    setInput('')
    setBusy(true)
    try {
      const res = await aiApi.chat(history.map(({ role, content }) => ({ role, content })))
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.reply, actions: res.actions },
      ])
      if (res.actions?.some((a) => a.ok)) {
        // The assistant changed floor state — pull the fresh floor plan.
        void refresh()
      }
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: e instanceof Error ? e.message : 'Something went wrong. Please try again.',
          error: true,
        },
      ])
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      {open && (
        <div
          style={{
            position: 'fixed',
            bottom: 92,
            right: 20,
            width: 380,
            maxWidth: 'calc(100vw - 32px)',
            height: 540,
            maxHeight: 'calc(100vh - 120px)',
            display: 'flex',
            flexDirection: 'column',
            background: '#fff',
            borderRadius: 16,
            border: '1px solid #e2e8f0',
            boxShadow: '0 20px 50px rgba(15, 23, 42, 0.25)',
            overflow: 'hidden',
            zIndex: 1000,
          }}
        >
          <div
            style={{
              padding: '14px 16px',
              background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <strong style={{ fontSize: 15 }}>✦ FOH Assistant</strong>
              <div style={{ fontSize: 12, opacity: 0.85 }}>
                Ask about tables, or tell me what to change
              </div>
            </div>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
              style={{
                background: 'rgba(255,255,255,0.15)',
                border: 'none',
                color: '#fff',
                width: 28,
                height: 28,
                borderRadius: 8,
                cursor: 'pointer',
                fontSize: 14,
                lineHeight: 1,
              }}
            >
              ✕
            </button>
          </div>

          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
            {messages.length === 0 && (
              <div>
                <p style={{ fontSize: 13, color: '#64748b', margin: '4px 0 10px' }}>
                  I can answer questions about the floor and make changes for you — seat guests,
                  reserve or free tables, 86 menu items, send staff alerts, and more.
                </p>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {SUGGESTIONS.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void send(s)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 999,
                        border: '1px solid #dbeafe',
                        background: '#eff6ff',
                        color: '#1d4ed8',
                        fontSize: 12,
                        cursor: 'pointer',
                      }}
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 10,
                }}
              >
                <div
                  style={{
                    maxWidth: '85%',
                    padding: '8px 12px',
                    borderRadius: 12,
                    fontSize: 13.5,
                    lineHeight: 1.45,
                    whiteSpace: 'pre-wrap',
                    background: msg.role === 'user' ? '#2563eb' : msg.error ? '#fef2f2' : '#f1f5f9',
                    color: msg.role === 'user' ? '#fff' : msg.error ? '#b91c1c' : '#0f172a',
                    border: msg.error ? '1px solid #fca5a5' : 'none',
                  }}
                >
                  {msg.content}
                </div>
                {msg.actions && msg.actions.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                    {msg.actions.map((action, j) => (
                      <span
                        key={j}
                        style={{
                          fontSize: 12,
                          padding: '4px 10px',
                          borderRadius: 999,
                          background: action.ok ? '#ecfdf5' : '#fff7ed',
                          border: `1px solid ${action.ok ? '#86efac' : '#fdba74'}`,
                          color: action.ok ? '#166534' : '#c2410c',
                        }}
                      >
                        {action.ok ? '✓' : '⚠'} {action.summary}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {busy && (
              <div style={{ fontSize: 13, color: '#94a3b8', padding: '4px 2px' }}>
                Assistant is thinking…
              </div>
            )}
          </div>

          <form
            onSubmit={(e) => {
              e.preventDefault()
              void send(input)
            }}
            style={{ display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #e2e8f0' }}
          >
            <input
              ref={inputRef}
              type="text"
              className="input"
              style={{ flex: 1 }}
              placeholder="e.g. Reserve T5 for Priya at 7:30, party of 3"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button type="submit" className="btn btn-primary" disabled={busy || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      )}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close FOH Assistant' : 'Open FOH Assistant'}
        title="FOH Assistant"
        style={{
          position: 'fixed',
          bottom: 24,
          right: 20,
          width: 56,
          height: 56,
          borderRadius: '50%',
          border: 'none',
          cursor: 'pointer',
          background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)',
          color: '#fff',
          fontSize: 24,
          boxShadow: '0 10px 25px rgba(59, 130, 246, 0.45)',
          zIndex: 1000,
        }}
      >
        {open ? '✕' : '✦'}
      </button>
    </>
  )
}
