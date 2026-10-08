import { useCallback, useEffect, useRef, useState } from 'react'
import type { Table } from '../../types'

/**
 * Resolves the backend origin for stream requests.
 * On dev (localhost), targets port 8000 directly to bypass Vite's proxy.
 */
function getBackendOrigin(): string {
  if (
    typeof window !== 'undefined' &&
    (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
  ) {
    return `http://${window.location.hostname}:8000`
  }
  return ''
}

interface LiveStreamPopupProps {
  /** The currently selected table (or null to hide the popup) */
  table: Table | null
  /** The floor ID that owns the stream */
  floorId: string
  /** Called when the user closes the popup */
  onClose: () => void
}

type StreamSize = 'compact' | 'medium' | 'large'

const SIZE_DIMENSIONS: Record<StreamSize, { width: number; height: number }> = {
  compact: { width: 320, height: 180 },
  medium: { width: 480, height: 270 },
  large: { width: 640, height: 360 },
}

export function LiveStreamPopup({ table, floorId, onClose }: LiveStreamPopupProps) {
  const [size, setSize] = useState<StreamSize>('medium')
  const [isMinimized, setIsMinimized] = useState(false)
  const [status, setStatus] = useState<'connecting' | 'live' | 'error'>('connecting')
  const [isHudVisible, setIsHudVisible] = useState(true)
  const [fps, setFps] = useState(0)

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const mountedRef = useRef(true)
  const activeReqRef = useRef<AbortController | null>(null)
  const prevTableRef = useRef<string | null>(null)

  // Reset when table changes
  useEffect(() => {
    if (table && table.id !== prevTableRef.current) {
      setStatus('connecting')
      setIsMinimized(false)
      prevTableRef.current = table.id
    }
  }, [table])

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (activeReqRef.current) activeReqRef.current.abort()
    }
  }, [])

  // ── Canvas Frame Pump (same reliable engine as LiveStreamPlayer) ──
  useEffect(() => {
    if (!table || isMinimized) return

    let active = true
    let lastFrameTime = performance.now()
    const frameTimes: number[] = []

    const baseHost = getBackendOrigin()
    const savedUrl = encodeURIComponent(table.cameraUrl || localStorage.getItem('foh_camera_url') || '')
    const savedMode = localStorage.getItem('foh_selected_camera_mode') || 'DEMO_STREAM'
    const frameSrc = `${baseHost}/stream/${floorId}/frame?_table=${table.id}&stream_url=${savedUrl}&source_type=${savedMode}`

    async function pumpNextFrame() {
      if (!active || !mountedRef.current) return

      const controller = new AbortController()
      activeReqRef.current = controller

      try {
        const url = `${frameSrc}&t=${Date.now()}`
        const res = await fetch(url, { signal: controller.signal, cache: 'no-store' })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        if (!active || !mountedRef.current) return

        const objectUrl = URL.createObjectURL(blob)
        const img = new Image()

        img.onload = () => {
          if (!active || !mountedRef.current) {
            URL.revokeObjectURL(objectUrl)
            return
          }
          const canvas = canvasRef.current
          if (canvas) {
            const ctx = canvas.getContext('2d')
            if (ctx) {
              if (canvas.width !== img.naturalWidth || canvas.height !== img.naturalHeight) {
                canvas.width = img.naturalWidth || 960
                canvas.height = img.naturalHeight || 540
              }
              ctx.drawImage(img, 0, 0)
            }
          }
          URL.revokeObjectURL(objectUrl)

          // FPS measurement
          const now = performance.now()
          const delta = now - lastFrameTime
          lastFrameTime = now
          if (delta > 0) {
            frameTimes.push(1000 / delta)
            if (frameTimes.length > 10) frameTimes.shift()
            const avg = Math.round(frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length)
            setFps(avg)
          }

          setStatus('live')

          if (active && mountedRef.current) {
            requestAnimationFrame(() => setTimeout(pumpNextFrame, 32))
          }
        }

        img.onerror = () => {
          URL.revokeObjectURL(objectUrl)
          if (active && mountedRef.current) {
            setTimeout(pumpNextFrame, 400)
          }
        }

        img.src = objectUrl
      } catch (err: any) {
        if (err.name !== 'AbortError' && active && mountedRef.current) {
          setStatus('error')
          // Retry after a short delay
          setTimeout(pumpNextFrame, 2000)
        }
      }
    }

    pumpNextFrame()

    return () => {
      active = false
      if (activeReqRef.current) activeReqRef.current.abort()
    }
  }, [table?.id, floorId, isMinimized])

  const cycleSizes: StreamSize[] = ['compact', 'medium', 'large']
  const nextSize = useCallback(() => {
    setSize((prev) => {
      const idx = cycleSizes.indexOf(prev)
      return cycleSizes[(idx + 1) % cycleSizes.length]
    })
  }, [])

  const handleRetry = useCallback(() => {
    setStatus('connecting')
  }, [])

  if (!table) return null

  const dims = SIZE_DIMENSIONS[size]

  return (
    <div
      className={`live-stream-popup ${isMinimized ? 'live-stream-popup--minimized' : ''}`}
      style={isMinimized ? undefined : { width: dims.width }}
    >
      {/* ── Header Bar ── */}
      <div className="live-stream-popup__header">
        <div className="live-stream-popup__header-left">
          <span
            className="live-stream-popup__live-dot"
            style={status === 'live' ? undefined : { background: '#f59e0b', animation: 'none' }}
          />
          <span className="live-stream-popup__title">
            {isMinimized ? `T${table.number}` : `Live · Table ${table.number}`}
          </span>
          {!isMinimized && (
            <>
              <span className="live-stream-popup__badge">YOLO11</span>
              {status === 'live' && fps > 0 && (
                <span className="live-stream-popup__fps-badge">{fps} FPS</span>
              )}
            </>
          )}
        </div>
        <div className="live-stream-popup__header-actions">
          {!isMinimized && (
            <>
              <button
                type="button"
                className="live-stream-popup__action-btn"
                onClick={() => setIsHudVisible((v) => !v)}
                title={isHudVisible ? 'Hide HUD overlay' : 'Show HUD overlay'}
              >
                {isHudVisible ? '◉' : '○'}
              </button>
              <button
                type="button"
                className="live-stream-popup__action-btn"
                onClick={nextSize}
                title={`Resize (${size})`}
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
                </svg>
              </button>
            </>
          )}
          <button
            type="button"
            className="live-stream-popup__action-btn"
            onClick={() => setIsMinimized((v) => !v)}
            title={isMinimized ? 'Expand' : 'Minimize'}
          >
            {isMinimized ? '▢' : '▁'}
          </button>
          <button
            type="button"
            className="live-stream-popup__action-btn live-stream-popup__close-btn"
            onClick={onClose}
            title="Close stream"
          >
            ✕
          </button>
        </div>
      </div>

      {/* ── Stream Content ── */}
      {!isMinimized && (
        <div
          className="live-stream-popup__body"
          style={{ height: dims.height }}
        >
          {/* Hardware-accelerated canvas renderer */}
          <canvas
            ref={canvasRef}
            className="live-stream-popup__canvas"
          />

          {/* Loading state */}
          {status === 'connecting' && (
            <div className="live-stream-popup__loading">
              <div className="live-stream-popup__loading-spinner" />
              <span>Connecting to stream…</span>
            </div>
          )}

          {/* Error state */}
          {status === 'error' && (
            <div className="live-stream-popup__error">
              <span className="live-stream-popup__error-icon">⚠</span>
              <span>Stream reconnecting…</span>
              <button
                type="button"
                className="btn btn-sm"
                onClick={handleRetry}
                style={{ marginTop: 6, fontSize: '0.75rem', padding: '4px 12px', background: '#334155', color: '#e2e8f0', border: 'none', borderRadius: '6px', cursor: 'pointer' }}
              >
                Retry
              </button>
            </div>
          )}

          {/* Table info overlay */}
          {status === 'live' && isHudVisible && (
            <div className="live-stream-popup__table-overlay">
              <span className="live-stream-popup__overlay-pill">
                T{table.number}
              </span>
              <span className={`live-stream-popup__overlay-status live-stream-popup__overlay-status--${table.status.toLowerCase()}`}>
                {table.status}
              </span>
              <span className="live-stream-popup__overlay-cap">
                👤 {table.capacity}
              </span>
            </div>
          )}

          {/* Subtle scan-line effect for a live-CCTV feel */}
          {status === 'live' && (
            <div className="live-stream-popup__scanlines" />
          )}
        </div>
      )}

      {/* ── Footer ── */}
      {!isMinimized && (
        <div className="live-stream-popup__footer">
          <span className="live-stream-popup__footer-text">
            {size === 'compact' ? '320×180' : size === 'medium' ? '480×270' : '640×360'}
          </span>
          <span className="live-stream-popup__footer-text">
            Canvas Engine · AI Vision
          </span>
        </div>
      )}
    </div>
  )
}
