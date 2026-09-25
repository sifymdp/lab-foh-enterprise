import { useState } from 'react'
import { API_URL, getToken } from '../../api/client'
import type { KitchenOrder } from '../../types'

interface SpeechRecognitionEventLike extends Event {
  results: ArrayLike<{ 0: { transcript: string } }>
}

interface SpeechRecognitionLike {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}

interface SpeechWindow extends Window {
  SpeechRecognition?: new () => SpeechRecognitionLike
  webkitSpeechRecognition?: new () => SpeechRecognitionLike
}

interface AIOperationsPanelProps {
  orders: KitchenOrder[]
}

async function aiRequest<T>(path: string, body?: object): Promise<T> {
  const token = getToken()
  const base = API_URL || ''
  const url = `${base}${path}`

  let response: Response
  try {
    response = await fetch(url, {
      method: body ? 'POST' : 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token || ''}`,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  } catch {
    // If initial fetch network error, fallback to direct backend port
    response = await fetch(`http://127.0.0.1:8000${path}`, {
      method: body ? 'POST' : 'GET',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token || ''}`,
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    })
  }

  // If Vite dev server returned 404, fallback directly to FastAPI
  if (response.status === 404 && !url.includes(':8000')) {
    try {
      const fallback = await fetch(`http://127.0.0.1:8000${path}`, {
        method: body ? 'POST' : 'GET',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token || ''}`,
        },
        ...(body ? { body: JSON.stringify(body) } : {}),
      })
      if (fallback.ok) {
        return (await fallback.json()) as T
      }
    } catch {
      // Ignore fallback error and process response normally
    }
  }

  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = (await response.json()) as { detail?: string | Array<{ msg?: string }> }
      detail =
        typeof errorBody.detail === 'string'
          ? errorBody.detail
          : Array.isArray(errorBody.detail)
          ? errorBody.detail.map((item) => item.msg || 'Invalid request').join(', ')
          : ''
    } catch {
      // Keep the status fallback when the server did not return JSON.
    }
    throw new Error(
      detail
        ? `AI request failed (${response.status}): ${detail}`
        : `AI request failed (${response.status})`
    )
  }
  return response.json() as Promise<T>
}

export function AIOperationsPanel({ orders }: AIOperationsPanelProps) {
  const [command, setCommand] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [routing, setRouting] = useState<string | null>(null)
  const [forecast, setForecast] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [listening, setListening] = useState(false)

  const run = async (action: () => Promise<void>) => {
    setBusy(true)
    setMessage(null)
    try {
      await action()
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'AI operation failed')
    } finally {
      setBusy(false)
    }
  }

  const routeOrders = () =>
    run(async () => {
      const items = orders.flatMap((order: any) =>
        (order.items || []).map((item: any) => item.item_name)
      )
      const result = await aiRequest<{
        routes: Array<{ item: string; station: string }>
        recommended_order: string[]
      }>('/ai/station-routing', { items })
      setRouting(
        `${result.routes.length} item(s) balanced. Prep priority sequence: ${
          result.recommended_order.join(' → ') || 'Standard line'
        }`
      )
    })

  const loadForecast = () =>
    run(async () => {
      const result = await aiRequest<{
        forecast: Array<{ item_name: string; forecast_quantity: number }>
      }>('/ai/demand-forecast', { horizon_days: 1 })
      const top = result.forecast
        .slice(0, 3)
        .map((item) => `${item.item_name}: ${item.forecast_quantity}`)
      setForecast(
        top.length ? `Tomorrow's predicted high-demand: ${top.join(' • ')}` : 'Not enough order volume yet'
      )
    })

  const sendVoiceCommand = () =>
    run(async () => {
      if (!command.trim()) return
      const result = await aiRequest<{ message: string }>('/ai/voice-command', {
        command,
        execute: true,
      })
      setMessage(result.message)
      setCommand('')
    })

  const startListening = () => {
    const speechWindow = window as SpeechWindow
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Recognition) {
      setMessage('Speech input is not supported in this browser. Please type the command.')
      return
    }
    const recognition = new Recognition()
    recognition.continuous = false
    recognition.interimResults = false
    recognition.lang = 'en-US'
    setListening(true)
    recognition.onresult = (event) => {
      setCommand(event.results[0][0].transcript)
      setListening(false)
    }
    recognition.onerror = () => {
      setListening(false)
      setMessage('Could not hear clearly. Please try again or type.')
    }
    recognition.onend = () => setListening(false)
    recognition.start()
  }

  return (
    <section className="kds-ai-panel" aria-label="AI kitchen copilot">
      <div className="kds-ai-panel__heading">
        <div className="kds-ai-panel__title-box">
          <div className="kds-ai-panel__badge">
            <span>✨</span>
            <span>AI COPILOT</span>
          </div>
          <h3 className="kds-ai-panel__title">Smart Kitchen Intelligence</h3>
          <p className="kds-ai-panel__subtitle">
            Autonomous line balancing, bottleneck scans & hands-free kitchen voice dispatch
          </p>
        </div>

        <button
          type="button"
          className="kds-ai-btn kds-ai-btn--warning"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const result = await aiRequest<{ delayed_orders: Array<unknown> }>('/ai/anomalies')
              setMessage(
                result.delayed_orders.length
                  ? `⚠️ Alert: ${result.delayed_orders.length} order(s) exceeding preparation target time`
                  : '✅ All active orders are on schedule — no delays detected'
              )
            })
          }
        >
          <span className="kds-ai-btn__icon">⏱️</span>
          <span>{busy ? 'Scanning Line…' : 'Scan Bottlenecks'}</span>
        </button>
      </div>

      <div className="kds-ai-panel__actions">
        <div className="kds-ai-panel__quick-tools">
          <button
            type="button"
            className="kds-ai-btn"
            disabled={busy}
            onClick={routeOrders}
          >
            <span className="kds-ai-btn__icon">🧭</span>
            <span>Auto-Route Stations</span>
          </button>

          <button
            type="button"
            className="kds-ai-btn"
            disabled={busy}
            onClick={loadForecast}
          >
            <span className="kds-ai-btn__icon">📈</span>
            <span>Forecast Rush Demand</span>
          </button>
        </div>

        <div className="kds-ai-panel__voice-group">
          <div className="kds-ai-voice-bar">
            <span className="kds-ai-voice-label">🎙️ Quick Dispatch:</span>
            <div className="kds-ai-input-wrap">
              <input
                className="kds-ai-input"
                value={command}
                onChange={(event) => {
                  setCommand(event.target.value)
                  setMessage(null)
                }}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') void sendVoiceCommand()
                }}
                placeholder="e.g. 'Rush Table 4' or 'Ready 1234'…"
                aria-label="Voice command text"
              />
              <button
                type="button"
                className={`kds-ai-mic-btn ${listening ? 'kds-ai-mic-btn--listening' : ''}`}
                disabled={busy || listening}
                onClick={startListening}
                title={listening ? 'Listening to voice command…' : 'Click to speak command'}
                aria-label="Start voice input"
              >
                {listening ? '🔴 Listening…' : '🎙️'}
              </button>
            </div>
            <button
              type="button"
              className="kds-ai-btn kds-ai-btn--primary"
              disabled={busy || !command.trim()}
              onClick={sendVoiceCommand}
            >
              <span>⚡ Execute</span>
            </button>
          </div>
        </div>
      </div>

      {(message || routing || forecast) && (
        <div className="kds-ai-panel__results">
          {message && (
            <div className="kds-ai-result-item kds-ai-result-item--message">
              <span>🧠</span>
              <span>{message}</span>
            </div>
          )}
          {routing && (
            <div className="kds-ai-result-item kds-ai-result-item--routing">
              <span>🧭</span>
              <span>{routing}</span>
            </div>
          )}
          {forecast && (
            <div className="kds-ai-result-item kds-ai-result-item--forecast">
              <span>📈</span>
              <span>{forecast}</span>
            </div>
          )}
          <button
            type="button"
            className="kds-ai-result-clear"
            onClick={() => {
              setMessage(null)
              setRouting(null)
              setForecast(null)
            }}
            title="Clear notification"
          >
            ✕
          </button>
        </div>
      )}
    </section>
  )
}
