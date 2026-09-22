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
  const response = await fetch(`${API_URL}${path}`, {
    method: body ? 'POST' : 'GET',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken() || ''}`,
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  })
  if (!response.ok) {
    let detail = ''
    try {
      const errorBody = await response.json() as { detail?: string | Array<{ msg?: string }> }
      detail = typeof errorBody.detail === 'string'
        ? errorBody.detail
        : Array.isArray(errorBody.detail)
          ? errorBody.detail.map((item) => item.msg || 'Invalid request').join(', ')
          : ''
    } catch {
      // Keep the status fallback when the server did not return JSON.
    }
    throw new Error(detail ? `AI request failed (${response.status}): ${detail}` : `AI request failed (${response.status})`)
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

  const routeOrders = () => run(async () => {
    const items = orders.flatMap((order: any) => (order.items || []).map((item: any) => item.item_name))
    const result = await aiRequest<{ routes: Array<{ item: string; station: string }>; recommended_order: string[] }>(
      '/ai/station-routing',
      { items },
    )
    setRouting(`${result.routes.length} items routed. Priority: ${result.recommended_order.join(' → ') || 'none'}`)
  })

  const loadForecast = () => run(async () => {
    const result = await aiRequest<{ forecast: Array<{ item_name: string; forecast_quantity: number }> }>(
      '/ai/demand-forecast',
      { horizon_days: 1 },
    )
    const top = result.forecast.slice(0, 3).map((item) => `${item.item_name}: ${item.forecast_quantity}`)
    setForecast(top.length ? `Next-day demand: ${top.join(' • ')}` : 'Not enough order history yet')
  })

  const sendVoiceCommand = () => run(async () => {
    if (!command.trim()) return
    const result = await aiRequest<{ message: string }>('/ai/voice-command', { command, execute: true })
    setMessage(result.message)
    setCommand('')
  })

  const startListening = () => {
    const speechWindow = window as SpeechWindow
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition
    if (!Recognition) {
      setMessage('Speech input is not supported by this browser. Type the command instead.')
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
      setMessage('Could not hear a command. Please try again or type it.')
    }
    recognition.onend = () => setListening(false)
    recognition.start()
  }

  return (
    <section className="kds-ai-panel" aria-label="AI kitchen operations">
      <div className="kds-ai-panel__heading">
        <div>
          <h2>AI Operations</h2>
          <p>Routing, forecasting, delay detection and hands-free control</p>
        </div>
        <button type="button" disabled={busy} onClick={() => run(async () => {
          const result = await aiRequest<{ delayed_orders: Array<unknown> }>('/ai/anomalies')
          setMessage(result.delayed_orders.length ? `${result.delayed_orders.length} delayed order(s) detected` : 'No delayed orders detected')
        })}>
          {busy ? 'Working…' : 'Check delays'}
        </button>
      </div>
      <div className="kds-ai-panel__actions">
        <button type="button" disabled={busy} onClick={routeOrders}>Route active items</button>
        <button type="button" disabled={busy} onClick={loadForecast}>Forecast demand</button>
        <label className="kds-ai-panel__voice">
          <span>Voice command</span>
          <input
            value={command}
            onChange={(event) => {
              setCommand(event.target.value)
              setMessage(null)
            }}
            onKeyDown={(event) => { if (event.key === 'Enter') void sendVoiceCommand() }}
            placeholder="ready order 1234"
            aria-label="Voice command text"
          />
          <button type="button" disabled={busy || listening} onClick={startListening} aria-label="Start voice input">
            {listening ? 'Listening…' : '🎙️'}
          </button>
          <button type="button" disabled={busy || !command.trim()} onClick={sendVoiceCommand}>Run</button>
        </label>
      </div>
      {(message || routing || forecast) && (
        <div className="kds-ai-panel__results">
          {message && <p>🧠 {message}</p>}
          {routing && <p>🧭 {routing}</p>}
          {forecast && <p>📈 {forecast}</p>}
        </div>
      )}
    </section>
  )
}
