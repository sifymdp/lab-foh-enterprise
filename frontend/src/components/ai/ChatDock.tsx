import { useEffect, useRef, useState } from 'react'
import { aiApi, type ChatMessage } from '../../api/extensions'

const SUGGESTIONS = [
  'How is the floor looking?',
  'Which tables are open?',
  'Anything need cleaning?',
]

const GREETING: ChatMessage = {
  role: 'assistant',
  content: "Hi! Ask me about the floor — open tables, what needs cleaning, or tonight's alerts.",
}

export function ChatDock() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState<ChatMessage[]>([GREETING])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [offline, setOffline] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, open])

  async function send(text: string) {
    const question = text.trim()
    if (!question || busy) return
    // History excludes the canned greeting — it isn't part of the conversation.
    const history = messages.filter((m) => m !== GREETING)
    setMessages((prev) => [...prev, { role: 'user', content: question }])
    setInput('')
    setBusy(true)
    try {
      const res = await aiApi.chat(question, history)
      setOffline(!res.aiGenerated)
      setMessages((prev) => [...prev, { role: 'assistant', content: res.reply }])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: "I couldn't reach the server just now — try again in a moment." },
      ])
    } finally {
      setBusy(false)
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        className="chat-fab"
        onClick={() => setOpen(true)}
        aria-label="Open floor assistant"
      >
        <span aria-hidden>💬</span>
        Assistant
      </button>
    )
  }

  return (
    <section className="chat-dock" aria-label="Floor assistant">
      <header className="chat-dock__head">
        <div>
          <strong>Floor Assistant</strong>
          <span className="chat-dock__sub">
            {offline ? 'Answering from live floor data' : 'AI · live floor data'}
          </span>
        </div>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => setOpen(false)}
          aria-label="Close floor assistant"
        >
          ✕
        </button>
      </header>

      <div className="chat-dock__body" ref={scrollRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-msg chat-msg--${m.role}`}>
            {m.content}
          </div>
        ))}
        {busy && <div className="chat-msg chat-msg--assistant chat-msg--typing">Thinking…</div>}
      </div>

      {messages.length <= 1 && (
        <div className="chat-dock__suggestions">
          {SUGGESTIONS.map((s) => (
            <button key={s} type="button" className="chat-chip" onClick={() => send(s)}>
              {s}
            </button>
          ))}
        </div>
      )}

      <form
        className="chat-dock__form"
        onSubmit={(e) => {
          e.preventDefault()
          send(input)
        }}
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the floor…"
          aria-label="Message"
          disabled={busy}
        />
        <button type="submit" className="btn btn-primary btn-sm" disabled={busy || !input.trim()}>
          Send
        </button>
      </form>
    </section>
  )
}
