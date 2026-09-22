import {
  createContext, useCallback, useContext, useEffect,
  useMemo, useRef, useState, type ReactNode,
} from 'react'

type EventHandler = (payload: unknown) => void

export type ConnectionStatusType = 'connected' | 'reconnecting' | 'disconnected'

interface SocketContextValue {
  connected: boolean
  status: ConnectionStatusType
  joinFloor: (floorId: string) => void
  on: (event: string, handler: EventHandler) => () => void
}

const SocketContext = createContext<SocketContextValue | null>(null)
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const SOCKET_URL = (import.meta.env.VITE_SOCKET_URL || 'http://127.0.0.1:8000').replace('http', 'ws')

export function SocketProvider({ children }: { children: ReactNode }) {
  const [connected, setConnected] = useState(USE_MOCK)
  const [status, setStatus] = useState<ConnectionStatusType>(USE_MOCK ? 'connected' : 'reconnecting')
  const listenersRef = useRef(new Map<string, Set<EventHandler>>())
  const wsRef = useRef<WebSocket | null>(null)
  const floorIdRef = useRef<string>('floor-1')
  const retryDelayRef = useRef<number>(1000)
  const retryTimerRef = useRef<any>(null)
  const connectRef = useRef<(floorId: string) => void>(() => undefined)
  const recentEventsRef = useRef<Set<string>>(new Set())

  const emit = useCallback((event: string, payload: unknown) => {
    // Deduplication check if payload has an event ID
    if (payload && typeof payload === 'object' && 'id' in payload) {
      const key = `${event}:${(payload as any).id}`
      if (recentEventsRef.current.has(key)) return
      recentEventsRef.current.add(key)
      if (recentEventsRef.current.size > 200) {
        const first = recentEventsRef.current.values().next().value
        if (first) recentEventsRef.current.delete(first)
      }
    }
    listenersRef.current.get(event)?.forEach((h) => h(payload))
  }, [])

  const connect = useCallback((floorId: string) => {
    if (USE_MOCK) {
      setConnected(true)
      setStatus('connected')
      return
    }

    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current)
      retryTimerRef.current = null
    }

    const token = localStorage.getItem('foh_access_token')
    const url = `${SOCKET_URL}/ws/${floorId}${token ? `?token=${token}` : ''}`
    
    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('[WS] Connected to', url)
        setConnected(true)
        setStatus('connected')
        retryDelayRef.current = 1000 // Reset backoff on success
      }

      ws.onclose = () => {
        setConnected(false)
        setStatus('reconnecting')
        // Exponential backoff with jitter
        const delay = Math.min(retryDelayRef.current, 10000)
        retryDelayRef.current = Math.min(retryDelayRef.current * 1.5, 10000)
        retryTimerRef.current = setTimeout(() => {
          connectRef.current(floorIdRef.current)
        }, delay)
      }

      ws.onerror = () => {
        setConnected(false)
        setStatus('reconnecting')
      }

      ws.onmessage = (e) => {
        try {
          const { event, data } = JSON.parse(e.data)
          emit(event, data)
        } catch {
          /* ignore ping/non-json */
        }
      }
    } catch {
      setConnected(false)
      setStatus('disconnected')
    }
  }, [emit])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    if (USE_MOCK) return
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send('ping')
      }
    }, 25_000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    connect(floorIdRef.current)
    return () => {
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  const joinFloor = useCallback((floorId: string) => {
    floorIdRef.current = floorId
    wsRef.current?.close()
    connect(floorId)
  }, [connect])

  const on = useCallback((event: string, handler: EventHandler) => {
    const listeners = listenersRef.current
    if (!listeners.has(event)) listeners.set(event, new Set())
    listeners.get(event)!.add(handler)
    return () => listeners.get(event)?.delete(handler)
  }, [])

  const value = useMemo(() => ({ connected, status, joinFloor, on }), [connected, status, joinFloor, on])
  return <SocketContext.Provider value={value}>{children}</SocketContext.Provider>
}

export function useSocket() {
  const ctx = useContext(SocketContext)
  if (!ctx) throw new Error('useSocket must be used within SocketProvider')
  return ctx
}
