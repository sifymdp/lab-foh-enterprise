import React, { useState, useEffect, useRef, useCallback } from 'react'

interface LiveStreamPlayerProps {
  floorId: string
  cameraId?: string | null
  cameraUrl: string
  sourceType: string
  modeLabel?: string
  minHeight?: number | string
  showLegend?: boolean
  className?: string
  style?: React.CSSProperties
}

export function LiveStreamPlayer({
  floorId,
  cameraId,
  cameraUrl,
  sourceType,
  modeLabel,
  minHeight = 380,
  showLegend = true,
  className = '',
  style = {},
}: LiveStreamPlayerProps) {
  // Default to 'canvas' hardware-accelerated direct frame renderer
  // which works across 100% of browsers (including Brave Shields and Chromium)
  const [streamMode, setStreamMode] = useState<'canvas' | 'mjpeg' | 'poll'>('canvas')
  const [status, setStatus] = useState<'connecting' | 'live' | 'error' | 'reconnecting'>('connecting')
  const [nonce, setNonce] = useState(0)
  const [pollFrameUrl, setPollFrameUrl] = useState<string | null>(null)
  const [retryCount, setRetryCount] = useState(0)
  const [useDirectBackend, setUseDirectBackend] = useState(false)
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [fpsCounter, setFpsCounter] = useState(25)

  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const imgRef = useRef<HTMLImageElement>(null)
  const retryTimerRef = useRef<any>(null)
  const pollTimerRef = useRef<any>(null)
  const activeReqRef = useRef<AbortController | null>(null)
  const mountedRef = useRef(true)

  // Determine base path: prefer direct port 8000 on development to completely bypass proxy buffering
  const backendOrigin = typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? `http://${window.location.hostname}:8000`
    : ''
  const baseHost = useDirectBackend ? '' : (backendOrigin || '')
  const encodedUrl = encodeURIComponent(cameraUrl || '')
  const mjpegSrc = `${baseHost}/stream/${floorId}?camera_id=${cameraId || ''}&stream_url=${encodedUrl}&source_type=${sourceType || 'RTSP'}&nonce=${nonce}`
  const singleFrameSrc = `${baseHost}/stream/${floorId}/frame?camera_id=${cameraId || ''}&stream_url=${encodedUrl}&source_type=${sourceType || 'RTSP'}`

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
      if (activeReqRef.current) activeReqRef.current.abort()
    }
  }, [])

  // Reset state when stream parameters change
  useEffect(() => {
    setStatus('connecting')
    setRetryCount(0)
    setNonce((n) => n + 1)
  }, [floorId, cameraId, cameraUrl, sourceType, streamMode, useDirectBackend])

  // ══════════════════════════════════════════════════════════════════════════
  // 1. PRIMARY ENGINE: Continuous Canvas Frame Stream (Universal, Brave/Chrome immune)
  // ══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (streamMode !== 'canvas') return

    let active = true
    let isFetching = false
    let lastFrameTime = performance.now()
    let frameTimes: number[] = []

    const pumpNextFrame = async () => {
      if (!active || !mountedRef.current || isFetching) return
      isFetching = true

      const controller = new AbortController()
      activeReqRef.current = controller

      try {
        const url = `${singleFrameSrc}&nonce=${nonce}&t=${Date.now()}`
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

          // Measure FPS
          const now = performance.now()
          const delta = now - lastFrameTime
          lastFrameTime = now
          if (delta > 0) {
            frameTimes.push(1000 / delta)
            if (frameTimes.length > 10) frameTimes.shift()
            const avgFps = Math.round(frameTimes.reduce((a, b) => a + b, 0) / frameTimes.length)
            setFpsCounter(avgFps)
          }

          setStatus('live')
          setRetryCount(0)
          isFetching = false

          if (active && mountedRef.current) {
            requestAnimationFrame(() => setTimeout(pumpNextFrame, 32))
          }
        }

        img.onerror = () => {
          isFetching = false
          if (active && mountedRef.current) {
            setTimeout(pumpNextFrame, 400)
          }
        }

        img.src = URL.createObjectURL(blob)
      } catch (err: any) {
        isFetching = false
        if (err.name !== 'AbortError' && active && mountedRef.current) {
          setStatus('reconnecting')
          setTimeout(pumpNextFrame, 1200)
        }
      }
    }

    pumpNextFrame()

    return () => {
      active = false
      if (activeReqRef.current) activeReqRef.current.abort()
    }
  }, [streamMode, singleFrameSrc, nonce])

  // ══════════════════════════════════════════════════════════════════════════
  // 2. SECONDARY ENGINE: Native MJPEG <img> Stream
  // ══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (streamMode !== 'mjpeg') return

    let active = true
    const checkFrameRendered = () => {
      if (!active || !mountedRef.current) return
      if (imgRef.current && imgRef.current.naturalWidth > 0) {
        setStatus('live')
        setRetryCount(0)
      }
    }

    const interval = setInterval(checkFrameRendered, 200)
    const graceTimer = setTimeout(() => {
      if (active && mountedRef.current) {
        setStatus((prev) => (prev === 'connecting' ? 'live' : prev))
      }
    }, 1000)

    return () => {
      active = false
      clearInterval(interval)
      clearTimeout(graceTimer)
    }
  }, [mjpegSrc, streamMode])

  // ══════════════════════════════════════════════════════════════════════════
  // 3. TERTIARY ENGINE: Discrete Snapshot Polling (5 FPS)
  // ══════════════════════════════════════════════════════════════════════════
  useEffect(() => {
    if (streamMode !== 'poll') return

    let isPolling = true

    async function fetchNextFrame() {
      if (!isPolling || !mountedRef.current) return
      try {
        const controller = new AbortController()
        activeReqRef.current = controller
        const res = await fetch(`${singleFrameSrc}&t=${Date.now()}`, {
          signal: controller.signal,
          cache: 'no-store',
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const blob = await res.blob()
        if (mountedRef.current && isPolling) {
          const objectUrl = URL.createObjectURL(blob)
          setPollFrameUrl((prev) => {
            if (prev) URL.revokeObjectURL(prev)
            return objectUrl
          })
          setStatus('live')
        }
      } catch (err: any) {
        if (err.name !== 'AbortError' && mountedRef.current && isPolling) {
          setStatus('error')
        }
      } finally {
        if (isPolling && mountedRef.current) {
          pollTimerRef.current = setTimeout(fetchNextFrame, 200)
        }
      }
    }

    fetchNextFrame()

    return () => {
      isPolling = false
      if (pollTimerRef.current) clearTimeout(pollTimerRef.current)
      if (activeReqRef.current) activeReqRef.current.abort()
    }
  }, [streamMode, singleFrameSrc])

  // Handlers
  const handleImageLoaded = useCallback(() => {
    if (!mountedRef.current) return
    setStatus('live')
    setRetryCount(0)
  }, [])

  const handleImageError = useCallback(() => {
    if (!mountedRef.current) return
    const nextRetry = retryCount + 1
    setRetryCount(nextRetry)

    if (nextRetry >= 2 && streamMode === 'mjpeg') {
      console.warn('[LiveStreamPlayer] MJPEG failed, switching to Canvas Engine')
      setStreamMode('canvas')
      setStatus('connecting')
      return
    }

    setStatus('reconnecting')
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    retryTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setNonce((n) => n + 1)
    }, 1500)
  }, [retryCount, streamMode])

  const handleManualReconnect = () => {
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current)
    setStatus('connecting')
    setRetryCount(0)
    setNonce((n) => n + 1)
  }

  const handleToggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {})
      setIsFullscreen(true)
    } else {
      document.exitFullscreen().catch(() => {})
      setIsFullscreen(false)
    }
  }

  return (
    <div
      ref={containerRef}
      className={`live-stream-player-container ${className}`}
      style={{
        borderRadius: '12px',
        overflow: 'hidden',
        border: '1px solid var(--border, #334155)',
        background: '#090d16',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        minHeight: typeof minHeight === 'number' ? `${minHeight}px` : minHeight,
        boxShadow: '0 8px 24px rgba(0, 0, 0, 0.45)',
        ...style,
      }}
    >
      {/* Top Stream Header HUD */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 10,
          padding: '8px 12px',
          background: 'linear-gradient(to bottom, rgba(9, 13, 22, 0.92) 0%, rgba(9, 13, 22, 0) 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          pointerEvents: 'none',
        }}
      >
        {/* Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', pointerEvents: 'auto' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '20px',
              fontSize: '0.72rem',
              fontWeight: 700,
              letterSpacing: '0.04em',
              background:
                status === 'live'
                  ? 'rgba(34, 197, 94, 0.2)'
                  : status === 'reconnecting'
                  ? 'rgba(234, 179, 8, 0.2)'
                  : status === 'error'
                  ? 'rgba(239, 68, 68, 0.2)'
                  : 'rgba(56, 189, 248, 0.2)',
              color:
                status === 'live'
                  ? '#4ade80'
                  : status === 'reconnecting'
                  ? '#fde047'
                  : status === 'error'
                  ? '#f87171'
                  : '#38bdf8',
              border: `1px solid ${
                status === 'live'
                  ? 'rgba(34, 197, 94, 0.5)'
                  : status === 'reconnecting'
                  ? 'rgba(234, 179, 8, 0.5)'
                  : status === 'error'
                  ? 'rgba(239, 68, 68, 0.5)'
                  : 'rgba(56, 189, 248, 0.5)'
              }`,
              backdropFilter: 'blur(6px)',
            }}
          >
            <span
              style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                background: 'currentColor',
                display: 'inline-block',
                boxShadow: status === 'live' ? '0 0 8px #4ade80' : 'none',
              }}
            />
            {status === 'live'
              ? `LIVE (${fpsCounter || 25} FPS)`
              : status === 'reconnecting'
              ? `RECONNECTING (${retryCount})`
              : status === 'error'
              ? 'STREAM OFFLINE'
              : 'CONNECTING...'}
          </div>

          {modeLabel && (
            <span
              style={{
                fontSize: '0.72rem',
                color: '#94a3b8',
                background: 'rgba(30, 41, 59, 0.75)',
                padding: '3px 8px',
                borderRadius: '6px',
                border: '1px solid rgba(51, 65, 85, 0.6)',
              }}
            >
              {modeLabel}
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', pointerEvents: 'auto' }}>
          {/* Renderer Engine Toggle */}
          <button
            type="button"
            title="Cycle between Canvas Engine (Hardware Accelerated), Native MJPEG, and Polling"
            onClick={() => {
              if (streamMode === 'canvas') setStreamMode('mjpeg')
              else if (streamMode === 'mjpeg') setStreamMode('poll')
              else setStreamMode('canvas')
            }}
            style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(71, 85, 105, 0.7)',
              color: '#e2e8f0',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            {streamMode === 'canvas' ? '🚀 Canvas Stream' : streamMode === 'mjpeg' ? '⚡ Native MJPEG' : '🔄 Polling'}
          </button>

          {/* Direct Backend Toggle */}
          <button
            type="button"
            title={useDirectBackend ? 'Switch to Vite Relative Proxy' : 'Switch to Direct Backend Port 8000'}
            onClick={() => setUseDirectBackend((b) => !b)}
            style={{
              background: useDirectBackend ? 'rgba(59, 130, 246, 0.3)' : 'rgba(30, 41, 59, 0.8)',
              border: `1px solid ${useDirectBackend ? 'rgba(59, 130, 246, 0.6)' : 'rgba(71, 85, 105, 0.7)'}`,
              color: useDirectBackend ? '#60a5fa' : '#cbd5e1',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              cursor: 'pointer',
            }}
          >
            {useDirectBackend ? ':8000 Direct' : 'Proxy'}
          </button>

          {/* Reconnect Button */}
          <button
            type="button"
            title="Force stream reconnection"
            onClick={handleManualReconnect}
            style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(71, 85, 105, 0.7)',
              color: '#e2e8f0',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              cursor: 'pointer',
            }}
          >
            ↻ Reconnect
          </button>

          {/* Fullscreen Button */}
          <button
            type="button"
            title="Toggle Fullscreen"
            onClick={handleToggleFullscreen}
            style={{
              background: 'rgba(30, 41, 59, 0.8)',
              border: '1px solid rgba(71, 85, 105, 0.7)',
              color: '#e2e8f0',
              padding: '3px 8px',
              borderRadius: '6px',
              fontSize: '0.72rem',
              cursor: 'pointer',
            }}
          >
            {isFullscreen ? '⤓ Normal' : '⛶ Full'}
          </button>
        </div>
      </div>

      {/* Main Video Surface — Hardware Accelerated Canvas */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
          minHeight: '340px',
          background: '#090d16',
        }}
      >
        {/* 1. Canvas Renderer (Default & Ultra-Reliable) */}
        <canvas
          ref={canvasRef}
          style={{
            display: streamMode === 'canvas' ? 'block' : 'none',
            width: '100%',
            height: '100%',
            minHeight: '340px',
            objectFit: 'contain',
            background: '#090d16',
          }}
        />

        {/* 2. MJPEG Renderer */}
        {streamMode === 'mjpeg' && (
          <img
            ref={imgRef}
            key={`mjpeg_${floorId}_${cameraUrl}_${sourceType}_${nonce}_${useDirectBackend}`}
            src={mjpegSrc}
            alt="AI Vision Candidate Detection"
            style={{
              display: 'block',
              width: '100%',
              height: '100%',
              minHeight: '340px',
              objectFit: 'contain',
              background: '#090d16',
            }}
            onLoad={handleImageLoaded}
            onError={handleImageError}
          />
        )}

        {/* 3. Single Frame Polling Renderer */}
        {streamMode === 'poll' && pollFrameUrl && (
          <img
            src={pollFrameUrl}
            alt="AI Vision Candidate Detection (Poll)"
            style={{
              display: 'block',
              width: '100%',
              height: '100%',
              minHeight: '340px',
              objectFit: 'contain',
              background: '#090d16',
            }}
          />
        )}

        {/* Non-intrusive floating connecting pill */}
        {status === 'connecting' && (
          <div
            style={{
              position: 'absolute',
              top: '48px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: 'rgba(15, 23, 42, 0.88)',
              backdropFilter: 'blur(8px)',
              padding: '6px 14px',
              borderRadius: '20px',
              border: '1px solid rgba(56, 189, 248, 0.4)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              zIndex: 5,
              pointerEvents: 'none',
              boxShadow: '0 4px 16px rgba(0, 0, 0, 0.4)',
            }}
          >
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                border: '2px solid rgba(56, 189, 248, 0.25)',
                borderTopColor: '#38bdf8',
                animation: 'spin 1s linear infinite',
              }}
            />
            <span style={{ fontSize: '0.76rem', color: '#e2e8f0', fontWeight: 500 }}>
              Buffering live video feed...
            </span>
          </div>
        )}

        {/* Error / Reconnecting Banner */}
        {status === 'reconnecting' && (
          <div
            style={{
              position: 'absolute',
              top: '52px',
              left: '16px',
              right: '16px',
              background: 'rgba(234, 179, 8, 0.92)',
              color: '#0f172a',
              padding: '8px 14px',
              borderRadius: '8px',
              fontSize: '0.78rem',
              fontWeight: 600,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              zIndex: 8,
              boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            }}
          >
            <span>⚠️ Video stream establishing connection (Attempt #{retryCount})...</span>
            <button
              type="button"
              onClick={handleManualReconnect}
              style={{
                background: '#0f172a',
                color: '#ffffff',
                border: 'none',
                padding: '3px 10px',
                borderRadius: '6px',
                fontSize: '0.72rem',
                cursor: 'pointer',
              }}
            >
              Retry Now
            </button>
          </div>
        )}

        {status === 'error' && (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              background: 'rgba(15, 23, 42, 0.9)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              zIndex: 6,
              padding: '1.5rem',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: '2rem' }}>📡</div>
            <strong style={{ color: '#f87171', fontSize: '0.95rem' }}>Stream Feed Temporarily Offline</strong>
            <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8', maxWidth: '380px' }}>
              Unable to receive frames from source: <code>{cameraUrl || 'Default'}</code>.
            </p>
            <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={handleManualReconnect}
              >
                ↻ Reconnect Stream
              </button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => setStreamMode((m) => (m === 'canvas' ? 'mjpeg' : 'canvas'))}
              >
                Switch Engine ({streamMode === 'canvas' ? 'MJPEG' : 'Canvas'})
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Legend Overlay at Bottom */}
      {showLegend && (
        <div
          style={{
            position: 'absolute',
            bottom: '10px',
            left: '10px',
            right: '10px',
            background: 'rgba(15, 23, 42, 0.88)',
            backdropFilter: 'blur(6px)',
            padding: '0.5rem 0.75rem',
            borderRadius: '8px',
            display: 'flex',
            gap: '1rem',
            fontSize: '0.74rem',
            color: '#ffffff',
            flexWrap: 'wrap',
            alignItems: 'center',
            border: '1px solid rgba(51, 65, 85, 0.7)',
            zIndex: 10,
          }}
        >
          <span>🟢 Green: Matched Table</span>
          <span>🔴 Red: Positional Drift</span>
          <span>🔵 Blue: Candidate New Table</span>
          <span>🟡 Yellow: Size / Uncertain</span>
          <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.7rem' }}>
            ByteTrack & YOLO11 Active
          </span>
        </div>
      )}
    </div>
  )
}
