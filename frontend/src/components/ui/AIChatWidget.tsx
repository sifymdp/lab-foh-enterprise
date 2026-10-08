import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { aiApi, type AIProviderStatus, type ChatAction, type ChatMessage, type RAGCitation } from '../../api/extensions'
import { useAuth } from '../../context/AuthContext'
import { useFloor } from '../../context/FloorContext'

interface ChatEntry extends ChatMessage {
  actions?: ChatAction[]
  error?: boolean
  citations?: RAGCitation[]
  feedbackGiven?: 'HELPFUL' | 'UNHELPFUL' | 'INCORRECT'
}

const getDomainBadgeStyle = (domain: string) => {
  switch (domain.toUpperCase()) {
    case 'RESTAURANT_SOP':
      return { bg: '#eff6ff', color: '#1d4ed8' }
    case 'CUSTOMER_EXPERIENCE':
      return { bg: '#fef3c7', color: '#b45309' }
    case 'KITCHEN':
      return { bg: '#fee2e2', color: '#b91c1c' }
    case 'TABLE_LIFECYCLE':
      return { bg: '#e0f2fe', color: '#0369a1' }
    case 'PREDICTIVE_OPERATIONS':
      return { bg: '#f3e8ff', color: '#7e22ce' }
    case 'MANAGER_DECISIONS':
      return { bg: '#fce7f3', color: '#be185d' }
    case 'MAINTENANCE':
      return { bg: '#ffedd5', color: '#c2410c' }
    case 'SUPPLIER_INVENTORY':
      return { bg: '#ecfdf5', color: '#047857' }
    case 'COMPLIANCE_SAFETY':
      return { bg: '#fef9c3', color: '#a16207' }
    case 'RESTAURANT_LAYOUT':
      return { bg: '#e0e7ff', color: '#4338ca' }
    case 'CROSS_BRANCH':
      return { bg: '#ccfbf1', color: '#0f766e' }
    case 'MENU':
      return { bg: '#f0fdf4', color: '#15803d' }
    default:
      return { bg: '#f1f5f9', color: '#475569' }
  }
}

const OWNER_SUGGESTIONS = [
  "What is today's revenue?",
  "What are customers complaining about most?",
  "Why were kitchen orders delayed?",
  "What should we prepare for tonight?",
  "What problems has Table 12 had recently?",
  "Have we solved a kitchen overload problem before?",
  "Compare turnover across branches",
  "Which tables are free right now?",
]

const OPERATIONAL_SUGGESTIONS = [
  "What is the table cleaning SOP?",
  "What are customers complaining about most?",
  "Why were kitchen orders delayed?",
  "What should we prepare for tonight?",
  "What problems has Table 12 had recently?",
  "What is the allergen procedure?",
  "Why was Table 18 moved?",
  "Which tables are free right now?",
]

export function AIChatWidget() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { refresh } = useFloor()
  const isOwner = user?.role === 'OWNER'
  const suggestions = isOwner ? OWNER_SUGGESTIONS : OPERATIONAL_SUGGESTIONS
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [messages, setMessages] = useState<ChatEntry[]>([])
  const [busy, setBusy] = useState(false)
  const [providerStatus, setProviderStatus] = useState<AIProviderStatus | null>(null)
  const [showConfig, setShowConfig] = useState(false)
  const [apiKeyInput, setApiKeyInput] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<'openrouter' | 'groq' | 'gemini' | 'openai'>('openrouter')
  const [selectedModel, setSelectedModel] = useState('openai/gpt-4o-mini')
  const [savingKey, setSavingKey] = useState(false)
  const [configMessage, setConfigMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [openCitations, setOpenCitations] = useState<Record<number, boolean>>({})

  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFeedback = async (index: number, type: 'HELPFUL' | 'UNHELPFUL') => {
    setMessages((prev) =>
      prev.map((m, i) => (i === index ? { ...m, feedbackGiven: type } : m))
    )
    try {
      await aiApi.submitRAGFeedback(undefined, type)
    } catch {
      // optimistic state retained
    }
  }

  const loadProviderStatus = async () => {
    try {
      const status = await aiApi.getProviderStatus()
      setProviderStatus(status)
      if (status.provider) {
        const p = status.provider.toLowerCase()
        if (p.includes('openrouter')) setSelectedProvider('openrouter')
        else if (p.includes('groq')) setSelectedProvider('groq')
        else if (p.includes('gemini')) setSelectedProvider('gemini')
        else if (p.includes('openai')) setSelectedProvider('openai')
      }
      if (status.model) {
        setSelectedModel(status.model)
      }
    } catch {
      // Fallback if network or auth error
      setProviderStatus({ connected: false, provider: null, model: null })
    }
  }

  useEffect(() => {
    if (open) {
      void loadProviderStatus()
      inputRef.current?.focus()
    }
  }, [open])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy, showConfig])

  async function handleSaveKey(e: React.FormEvent) {
    e.preventDefault()
    if (!apiKeyInput.trim()) return
    setSavingKey(true)
    setConfigMessage(null)
    try {
      const res = await aiApi.configureKey({
        provider: selectedProvider,
        api_key: apiKeyInput.trim(),
        model: selectedProvider === 'openrouter' ? selectedModel : undefined,
      })
      setConfigMessage({ type: 'success', text: res.message || 'Key saved & activated!' })
      setApiKeyInput('')
      await loadProviderStatus()
      setTimeout(() => setShowConfig(false), 1500)
    } catch (err) {
      setConfigMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to save API key',
      })
    } finally {
      setSavingKey(false)
    }
  }

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
        { role: 'assistant', content: res.reply, actions: res.actions, citations: res.citations },
      ])
      // Execute any validated UI navigation actions
      const navAction = res.actions?.find((a) => a.type === 'NAVIGATE' && a.route)
      if (navAction?.route) {
        let targetUrl = navAction.route
        const qParams = navAction.filter || navAction.params
        if (qParams && typeof qParams === 'object') {
          const qs = new URLSearchParams(qParams as Record<string, string>).toString()
          if (qs) targetUrl += `?${qs}`
        }
        navigate(targetUrl)
      }
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
            width: 400,
            maxWidth: 'calc(100vw - 32px)',
            height: 560,
            maxHeight: 'calc(100vh - 120px)',
            display: 'flex',
            flexDirection: 'column',
            background: '#ffffff',
            borderRadius: 16,
            border: '1px solid #e2e8f0',
            boxShadow: '0 20px 50px rgba(15, 23, 42, 0.25)',
            overflow: 'hidden',
            zIndex: 1000,
          }}
        >
          {/* Header */}
          <div
            style={{
              padding: '12px 16px',
              background: 'linear-gradient(135deg, #1e293b, #0f172a)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              borderBottom: '1px solid #334155',
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <strong style={{ fontSize: 15, letterSpacing: '-0.01em' }}>✦ FOH Assistant</strong>
                <button
                  type="button"
                  onClick={() => setShowConfig((v) => !v)}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    padding: '2px 8px',
                    borderRadius: 999,
                    fontSize: 11,
                    fontWeight: 500,
                    cursor: 'pointer',
                    border: providerStatus?.connected
                      ? '1px solid rgba(74, 222, 128, 0.4)'
                      : '1px solid rgba(251, 191, 36, 0.4)',
                    background: providerStatus?.connected
                      ? 'rgba(34, 197, 94, 0.15)'
                      : 'rgba(245, 158, 11, 0.15)',
                    color: providerStatus?.connected ? '#86efac' : '#fde047',
                  }}
                  title="Click to configure AI API Key"
                >
                  <span
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: providerStatus?.connected ? '#22c55e' : '#f59e0b',
                    }}
                  />
                  {providerStatus?.connected
                    ? `${providerStatus.provider?.toUpperCase()} AI`
                    : 'Local Intelligence'}
                  <span style={{ opacity: 0.7, fontSize: 10 }}>⚙</span>
                </button>
              </div>
              <div style={{ fontSize: 11.5, color: '#94a3b8', marginTop: 2 }}>
                {providerStatus?.connected
                  ? `Active Model: ${providerStatus.model || 'LLM'}`
                  : 'Instant table control & command parsing'}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <button
                type="button"
                onClick={() => setMessages([])}
                aria-label="Clear chat"
                title="Clear conversation"
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: '#94a3b8',
                  width: 28,
                  height: 28,
                  borderRadius: 8,
                  cursor: 'pointer',
                  fontSize: 13,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                ⟲
              </button>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close assistant"
                style={{
                  background: 'rgba(255,255,255,0.08)',
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
          </div>

          {/* Config Drawer */}
          {showConfig && (
            <div
              style={{
                background: '#f8fafc',
                borderBottom: '1px solid #e2e8f0',
                padding: '12px 14px',
                fontSize: 12.5,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span style={{ fontWeight: 600, color: '#0f172a' }}>⚙ AI Provider Key Setup</span>
                <button
                  type="button"
                  onClick={() => setShowConfig(false)}
                  style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748b' }}
                >
                  ✕
                </button>
              </div>

              <p style={{ margin: '0 0 10px', color: '#64748b', fontSize: 11.5, lineHeight: 1.4 }}>
                Enter your API key below to activate conversational intelligence instantly without restarting the server.
              </p>

              <form onSubmit={handleSaveKey}>
                <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                  {(['openrouter', 'groq', 'gemini', 'openai'] as const).map((prov) => (
                    <button
                      key={prov}
                      type="button"
                      onClick={() => setSelectedProvider(prov)}
                      style={{
                        flex: prov === 'openrouter' ? '1 1 100%' : '1 1 auto',
                        padding: '5px 8px',
                        borderRadius: 6,
                        fontSize: 11,
                        fontWeight: 600,
                        textTransform: 'capitalize',
                        cursor: 'pointer',
                        border: selectedProvider === prov ? '1.5px solid #2563eb' : '1px solid #cbd5e1',
                        background: selectedProvider === prov ? '#eff6ff' : '#ffffff',
                        color: selectedProvider === prov ? '#1d4ed8' : '#475569',
                      }}
                    >
                      {prov === 'openrouter' ? '⚡ OpenRouter (Recommended Gateway)' : prov === 'groq' ? 'Groq (Free)' : prov}
                    </button>
                  ))}
                </div>

                {selectedProvider === 'openrouter' && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: '#475569' }}>Selected Model:</span>
                      <span style={{ fontSize: 10, color: '#64748b' }}>Multi-Model Gateway</span>
                    </div>
                    <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
                      {[
                        { id: 'openai/gpt-4o-mini', label: 'GPT-4o Mini' },
                        { id: 'anthropic/claude-3.5-haiku', label: 'Claude 3.5 Haiku' },
                        { id: 'meta-llama/llama-3.3-70b-instruct', label: 'Llama 3.3 70B' },
                      ].map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => setSelectedModel(m.id)}
                          style={{
                            padding: '3px 6px',
                            borderRadius: 4,
                            fontSize: 10.5,
                            cursor: 'pointer',
                            border: selectedModel === m.id ? '1px solid #2563eb' : '1px solid #cbd5e1',
                            background: selectedModel === m.id ? '#dbeafe' : '#ffffff',
                            color: selectedModel === m.id ? '#1e40af' : '#64748b',
                          }}
                        >
                          {m.label}
                        </button>
                      ))}
                    </div>
                    <input
                      aria-label="Model identifier"
                      type="text"
                      value={selectedModel}
                      onChange={(e) => setSelectedModel(e.target.value)}
                      placeholder="e.g. openai/gpt-4o-mini"
                      style={{
                        width: '100%',
                        padding: '4px 8px',
                        fontSize: 11,
                        borderRadius: 6,
                        border: '1px solid #cbd5e1',
                        outline: 'none',
                        marginBottom: 6,
                        boxSizing: 'border-box',
                      }}
                    />
                  </div>
                )}

                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    id="ai-widget-api-key"
                    name="aiApiKey"
                    aria-label="AI Provider API Key"
                    type="password"
                    value={apiKeyInput}
                    onChange={(e) => setApiKeyInput(e.target.value)}
                    placeholder={
                      selectedProvider === 'openrouter'
                        ? 'sk-or-v1-...'
                        : selectedProvider === 'groq'
                        ? 'gsk_...'
                        : selectedProvider === 'gemini'
                        ? 'AIzaSy...'
                        : 'sk-...'
                    }
                    style={{
                      flex: 1,
                      padding: '6px 10px',
                      fontSize: 12,
                      borderRadius: 6,
                      border: '1px solid #cbd5e1',
                      outline: 'none',
                    }}
                  />
                  <button
                    type="submit"
                    disabled={savingKey || !apiKeyInput.trim()}
                    style={{
                      padding: '6px 12px',
                      background: '#2563eb',
                      color: '#fff',
                      border: 'none',
                      borderRadius: 6,
                      fontSize: 12,
                      fontWeight: 500,
                      cursor: savingKey || !apiKeyInput.trim() ? 'not-allowed' : 'pointer',
                      opacity: savingKey || !apiKeyInput.trim() ? 0.6 : 1,
                    }}
                  >
                    {savingKey ? 'Saving…' : 'Save & Connect'}
                  </button>
                </div>
              </form>

              {configMessage && (
                <div
                  style={{
                    marginTop: 8,
                    padding: '6px 8px',
                    borderRadius: 6,
                    fontSize: 11.5,
                    background: configMessage.type === 'success' ? '#ecfdf5' : '#fef2f2',
                    color: configMessage.type === 'success' ? '#166534' : '#b91c1c',
                    border: configMessage.type === 'success' ? '1px solid #86efac' : '1px solid #fca5a5',
                  }}
                >
                  {configMessage.text}
                </div>
              )}

              <div style={{ marginTop: 6, fontSize: 11, color: '#94a3b8' }}>
                {selectedProvider === 'openrouter' ? (
                  <>
                    Tip: Get your OpenRouter API key at{' '}
                    <a
                      href="https://openrouter.ai/keys"
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: '#2563eb', textDecoration: 'underline' }}
                    >
                      openrouter.ai/keys
                    </a>
                  </>
                ) : selectedProvider === 'groq' ? (
                  <>
                    Tip: Get a free high-speed Groq key at{' '}
                    <a
                      href="https://console.groq.com/keys"
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: '#2563eb', textDecoration: 'underline' }}
                    >
                      console.groq.com
                    </a>
                  </>
                ) : (
                  'Tip: Enter a valid API key with model inference access.'
                )}
              </div>
            </div>
          )}

          {/* Messages Area */}
          <div ref={scrollRef} style={{ flex: 1, overflowY: 'auto', padding: 14 }}>
            {messages.length === 0 && (
              <div>
                <div
                  style={{
                    padding: 12,
                    background: '#f8fafc',
                    borderRadius: 12,
                    border: '1px solid #e2e8f0',
                    marginBottom: 12,
                  }}
                >
                  <p style={{ fontSize: 13, color: '#334155', margin: '0 0 6px', fontWeight: 500 }}>
                    👋 Welcome! How can I help with the floor today?
                  </p>
                  <p style={{ fontSize: 12, color: '#64748b', margin: 0, lineHeight: 1.45 }}>
                    You can manage tables in plain English: seat guests, change table statuses (billing, paid, cleaning, free), check shift metrics, or run KDS commands.
                  </p>
                </div>

                <div style={{ fontSize: 11.5, fontWeight: 600, color: '#64748b', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Quick Actions
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {suggestions.map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => void send(s)}
                      style={{
                        padding: '6px 10px',
                        borderRadius: 999,
                        border: '1px solid #e2e8f0',
                        background: '#ffffff',
                        color: '#1e293b',
                        fontSize: 12,
                        cursor: 'pointer',
                        boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                        transition: 'all 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#93c5fd'
                        e.currentTarget.style.background = '#eff6ff'
                        e.currentTarget.style.color = '#1d4ed8'
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#e2e8f0'
                        e.currentTarget.style.background = '#ffffff'
                        e.currentTarget.style.color = '#1e293b'
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
                    fontSize: 13,
                    lineHeight: 1.45,
                    whiteSpace: 'pre-wrap',
                    background: msg.role === 'user' ? '#2563eb' : msg.error ? '#fef2f2' : '#f1f5f9',
                    color: msg.role === 'user' ? '#fff' : msg.error ? '#b91c1c' : '#0f172a',
                    border: msg.error ? '1px solid #fca5a5' : 'none',
                    boxShadow: msg.role === 'user' ? '0 1px 2px rgba(37,99,235,0.2)' : 'none',
                  }}
                >
                  {msg.content}
                </div>
                {msg.actions && msg.actions.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6, maxWidth: '85%' }}>
                    {msg.actions.map((action, j) => (
                      <span
                        key={j}
                        onClick={() => {
                          if (action.route) navigate(action.route)
                        }}
                        style={{
                          fontSize: 11.5,
                          padding: '4px 10px',
                          borderRadius: 8,
                          background: action.ok ? '#ecfdf5' : '#fff7ed',
                          border: `1px solid ${action.ok ? '#86efac' : '#fdba74'}`,
                          color: action.ok ? '#166534' : '#c2410c',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          cursor: action.route ? 'pointer' : 'default',
                        }}
                      >
                        <span>{action.ok ? '✓' : '⚠'}</span>
                        <span>{action.summary}</span>
                        {action.route && <span style={{ opacity: 0.7, fontSize: 10 }}>↗</span>}
                      </span>
                    ))}
                  </div>
                )}

                {msg.role === 'assistant' && !msg.error && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6, maxWidth: '85%' }}>
                    {/* Source Citations Accordion */}
                    {msg.citations && msg.citations.length > 0 && (
                      <div style={{ fontSize: 11.5 }}>
                        <button
                          type="button"
                          onClick={() => setOpenCitations((p) => ({ ...p, [i]: !p[i] }))}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            borderRadius: 6,
                            padding: '3px 8px',
                            color: '#475569',
                            cursor: 'pointer',
                            fontSize: 11,
                            fontWeight: 500,
                          }}
                        >
                          <span>📚</span>
                          <span>{msg.citations.length} Grounded Source{msg.citations.length > 1 ? 's' : ''}</span>
                          <span style={{ fontSize: 9 }}>{openCitations[i] ? '▲' : '▼'}</span>
                        </button>
                        {openCitations[i] && (
                          <div style={{ marginTop: 4, display: 'flex', flexDirection: 'column', gap: 4 }}>
                            {msg.citations.map((c, idx) => (
                              <div
                                key={idx}
                                style={{
                                  background: '#ffffff',
                                  border: '1px solid #cbd5e1',
                                  borderRadius: 6,
                                  padding: '6px 8px',
                                  fontSize: 11,
                                  boxShadow: '0 1px 2px rgba(0,0,0,0.03)',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                                  <span style={{ fontWeight: 600, color: '#0f172a' }}>{c.title}</span>
                                  <span
                                    style={{
                                      fontSize: 9.5,
                                      padding: '1px 5px',
                                      borderRadius: 4,
                                      background: getDomainBadgeStyle(c.domain).bg,
                                      color: getDomainBadgeStyle(c.domain).color,
                                      fontWeight: 600,
                                    }}
                                  >
                                    {c.domain}
                                  </span>
                                </div>
                                <div style={{ color: '#475569', fontSize: 10.5, lineHeight: 1.35 }}>
                                  {c.snippet}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Feedback Buttons */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, color: '#94a3b8' }}>
                      {msg.feedbackGiven ? (
                        <span style={{ color: '#16a34a', display: 'flex', alignItems: 'center', gap: 4 }}>
                          ✓ Feedback recorded
                        </span>
                      ) : (
                        <>
                          <span style={{ fontSize: 10 }}>Helpful?</span>
                          <button
                            type="button"
                            onClick={() => void handleFeedback(i, 'HELPFUL')}
                            title="Helpful"
                            style={{
                              background: 'transparent',
                              border: 'none',
                              cursor: 'pointer',
                              padding: '1px 3px',
                              fontSize: 12,
                            }}
                          >
                            👍
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleFeedback(i, 'UNHELPFUL')}
                            title="Not helpful"
                            style={{
                              background: 'transparent',
                              border: 'none',
                              cursor: 'pointer',
                              padding: '1px 3px',
                              fontSize: 12,
                            }}
                          >
                            👎
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                )}
              </div>
            ))}

            {busy && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 4px', color: '#64748b', fontSize: 12.5 }}>
                <span
                  style={{
                    display: 'inline-block',
                    width: 14,
                    height: 14,
                    border: '2px solid #cbd5e1',
                    borderTopColor: '#2563eb',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                  }}
                />
                Assistant is thinking…
              </div>
            )}
          </div>

          {/* Footer Input */}
          <form
            onSubmit={(e) => {
              e.preventDefault()
              void send(input)
            }}
            style={{ display: 'flex', gap: 8, padding: 12, borderTop: '1px solid #e2e8f0', background: '#fff' }}
          >
            <input
              ref={inputRef}
              id="ai-widget-chat-input"
              name="aiWidgetMessage"
              aria-label="Ask AI Assistant"
              type="text"
              className="input"
              style={{
                flex: 1,
                padding: '8px 12px',
                fontSize: 13,
                borderRadius: 8,
                border: '1px solid #cbd5e1',
                outline: 'none',
              }}
              placeholder="e.g. Sent bill to T1, or Seat 4 at T2"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              style={{
                padding: '8px 16px',
                borderRadius: 8,
                background: '#2563eb',
                color: '#fff',
                border: 'none',
                fontWeight: 600,
                fontSize: 13,
                cursor: busy || !input.trim() ? 'not-allowed' : 'pointer',
                opacity: busy || !input.trim() ? 0.5 : 1,
              }}
            >
              Send
            </button>
          </form>
        </div>
      )}

      {/* Floating Action Button */}
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
          background: 'linear-gradient(135deg, #2563eb, #7c3aed)',
          color: '#fff',
          fontSize: 22,
          boxShadow: '0 10px 25px rgba(37, 99, 235, 0.4)',
          zIndex: 1000,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'transform 0.15s ease',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'scale(1.05)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'scale(1)'
        }}
      >
        {open ? '✕' : '✦'}
      </button>
    </>
  )
}
