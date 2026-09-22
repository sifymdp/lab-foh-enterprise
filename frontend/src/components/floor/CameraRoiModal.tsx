import { useEffect, useRef, useState } from 'react'
import { api } from '../../api/client'
import { useFloor } from '../../context/FloorContext'
import type { RectBounds, Table } from '../../types'

interface CameraRoiModalProps {
  table: Table
  onClose: () => void
}

// Widest we'll ever display the snapshot at, in CSS pixels. The camera frame
// itself might be much bigger (e.g. 960x540 or higher) — we shrink it to fit
// on screen, then convert coordinates back to real frame pixels when saving.
const MAX_DISPLAY_WIDTH = 720

const DEFAULT_BOX_SIZE = 160
const LASSO_PADDING = 18

interface LassoPoint {
  x: number
  y: number
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function boundsFromLasso(points: LassoPoint[], width: number, height: number): RectBounds | null {
  if (!points.length) return null
  const minX = Math.min(...points.map((point) => point.x))
  const maxX = Math.max(...points.map((point) => point.x))
  const minY = Math.min(...points.map((point) => point.y))
  const maxY = Math.max(...points.map((point) => point.y))
  const x = clamp(minX - LASSO_PADDING, 0, width)
  const y = clamp(minY - LASSO_PADDING, 0, height)
  const right = clamp(maxX + LASSO_PADDING, x + 40, width)
  const bottom = clamp(maxY + LASSO_PADDING, y + 40, height)
  return {
    x,
    y,
    width: right - x,
    height: bottom - y,
  }
}

function lassoFromRect(rect: RectBounds): LassoPoint[] {
  return [
    { x: rect.x, y: rect.y },
    { x: rect.x + rect.width, y: rect.y },
    { x: rect.x + rect.width, y: rect.y + rect.height },
    { x: rect.x, y: rect.y + rect.height },
  ]
}

export function CameraRoiModal({ table, onClose }: CameraRoiModalProps) {
  const { updateTable, refresh } = useFloor()

  // --- Camera URL step ---------------------------------------------------
  const [cameraUrl, setCameraUrl] = useState(table.cameraUrl ?? '')
  const [savingUrl, setSavingUrl] = useState(false)
  const [urlError, setUrlError] = useState<string | null>(null)

  // --- Snapshot + ROI lasso step ------------------------------------------
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null)
  const [displayWidth, setDisplayWidth] = useState(MAX_DISPLAY_WIDTH)
  const [loadingSnapshot, setLoadingSnapshot] = useState(false)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)

  // The saved ROI remains a rectangular crop for the backend, but managers draw
  // it with a lasso. We convert displayed pixels to real frame pixels on save.
  const [box, setBox] = useState<RectBounds>({ x: 40, y: 40, width: DEFAULT_BOX_SIZE, height: DEFAULT_BOX_SIZE })
  const [lassoPoints, setLassoPoints] = useState<LassoPoint[]>([])
  const [lassoing, setLassoing] = useState(false)
  const [hasDraftRoi, setHasDraftRoi] = useState(false)
  const [savingRoi, setSavingRoi] = useState(false)
  const [roiSaved, setRoiSaved] = useState(false)

  const objectUrlRef = useRef<string | null>(null)
  const imageFrameRef = useRef<HTMLDivElement>(null)
  const boxRef = useRef(box)
  const lassoPointsRef = useRef<LassoPoint[]>([])

  useEffect(() => {
    boxRef.current = box
  }, [box])

  useEffect(() => {
    lassoPointsRef.current = lassoPoints
  }, [lassoPoints])

  // Clean up the temporary blob URL when the modal closes, so we don't leak memory.
  useEffect(() => {
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
    }
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  async function handleSaveCameraUrl() {
    setSavingUrl(true)
    setUrlError(null)
    try {
      await updateTable(table.id, { cameraUrl: cameraUrl.trim() || null })
    } catch (e) {
      setUrlError(e instanceof Error ? e.message : 'Could not save camera URL')
    } finally {
      setSavingUrl(false)
    }
  }

  async function handleLoadSnapshot() {
    setLoadingSnapshot(true)
    setSnapshotError(null)
    setRoiSaved(false)
    try {
      const url = await api.getCameraSnapshot(table.id)
      objectUrlRef.current = url
      setSnapshotUrl(url)
    } catch (e) {
      setSnapshotError(e instanceof Error ? e.message : 'Could not load a snapshot')
    } finally {
      setLoadingSnapshot(false)
    }
  }

  function handleImageLoaded(img: HTMLImageElement) {
    const natural = { width: img.naturalWidth, height: img.naturalHeight }
    setNaturalSize(natural)
    const shownWidth = Math.min(MAX_DISPLAY_WIDTH, natural.width)
    setDisplayWidth(shownWidth)
    const scale = shownWidth / natural.width

    // If this table already has a saved ROI (in real frame pixels), show it
    // scaled down to display size. Otherwise start with a default box in the middle.
    if (table.roiCoords) {
      const savedBox = {
        x: table.roiCoords.x * scale,
        y: table.roiCoords.y * scale,
        width: table.roiCoords.width * scale,
        height: table.roiCoords.height * scale,
      }
      const savedLasso = lassoFromRect(savedBox)
      boxRef.current = savedBox
      setBox(savedBox)
      setLassoPoints(savedLasso)
      lassoPointsRef.current = savedLasso
      setHasDraftRoi(false)
    } else {
      const defaultBox = {
        x: shownWidth / 2 - DEFAULT_BOX_SIZE / 2,
        y: (shownWidth * (natural.height / natural.width)) / 2 - DEFAULT_BOX_SIZE / 2,
        width: DEFAULT_BOX_SIZE,
        height: DEFAULT_BOX_SIZE,
      }
      boxRef.current = defaultBox
      setBox(defaultBox)
      setLassoPoints([])
      lassoPointsRef.current = []
      setHasDraftRoi(false)
    }
  }

  function applyLassoPoint(clientX: number, clientY: number) {
    const frame = imageFrameRef.current
    if (!frame || !naturalSize) return
    const rect = frame.getBoundingClientRect()
    // Map pointer position into display space (displayWidth x displayHeight)
    // so lasso points, the SVG overlay, and the saved box all share one
    // coordinate system even when the container renders smaller on screen.
    const frameWidth = displayWidth
    const frameHeight = displayHeight
    const toDisplayX = frameWidth / Math.max(rect.width, 1)
    const toDisplayY = frameHeight / Math.max(rect.height, 1)
    const nextPoint = {
      x: clamp((clientX - rect.left) * toDisplayX, 0, frameWidth),
      y: clamp((clientY - rect.top) * toDisplayY, 0, frameHeight),
    }
    setLassoPoints((current) => {
      const previous = current[current.length - 1]
      if (previous && Math.hypot(previous.x - nextPoint.x, previous.y - nextPoint.y) < 8) {
        return current
      }
      const next = [...current, nextPoint]
      lassoPointsRef.current = next
      const nextBounds = boundsFromLasso(next, frameWidth, frameHeight)
      if (nextBounds) {
        boxRef.current = nextBounds
        setBox(nextBounds)
        setHasDraftRoi(true)
      }
      return next
    })
    setRoiSaved(false)
  }

  function handleLassoStart(e: React.PointerEvent<HTMLDivElement>) {
    if (!naturalSize) return
    e.preventDefault()
    e.stopPropagation()
    e.currentTarget.setPointerCapture(e.pointerId)
    setLassoing(true)
    setLassoPoints([])
    lassoPointsRef.current = []
    setHasDraftRoi(false)
    applyLassoPoint(e.clientX, e.clientY)
  }

  function handleLassoMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!lassoing) return
    applyLassoPoint(e.clientX, e.clientY)
  }

  function handleLassoEnd(e: React.PointerEvent<HTMLDivElement>) {
    if (!lassoing) return
    e.currentTarget.releasePointerCapture(e.pointerId)
    setLassoing(false)
  }

  function clearLasso() {
    setLassoPoints([])
    lassoPointsRef.current = []
    setHasDraftRoi(false)
    if (!naturalSize) return
    const defaultBox = {
      x: displayWidth / 2 - DEFAULT_BOX_SIZE / 2,
      y: displayHeight / 2 - DEFAULT_BOX_SIZE / 2,
      width: DEFAULT_BOX_SIZE,
      height: DEFAULT_BOX_SIZE,
    }
    boxRef.current = defaultBox
    setBox(defaultBox)
    setRoiSaved(false)
  }

  async function handleSaveRoi() {
    if (!naturalSize) return
    if (!hasDraftRoi && lassoPointsRef.current.length === 0) {
      setSnapshotError('Draw a lasso around the table before saving the ROI.')
      return
    }
    setSavingRoi(true)
    setSnapshotError(null)
    try {
      // Convert from display-space pixels back to real camera-frame pixels
      // before saving — the backend matches detections in that raw space.
      const scaleX = naturalSize.width / displayWidth
      const scaleY = naturalSize.height / Math.max(displayHeight, 1)
      const currentBox = boxRef.current
      const realRoi: RectBounds = {
        x: Math.round(currentBox.x * scaleX),
        y: Math.round(currentBox.y * scaleY),
        width: Math.round(currentBox.width * scaleX),
        height: Math.round(currentBox.height * scaleY),
      }
      await updateTable(table.id, { roiCoords: realRoi })
      await refresh()
      setHasDraftRoi(false)
      setRoiSaved(true)
    } catch (e) {
      setSnapshotError(e instanceof Error ? e.message : 'Could not save the ROI')
    } finally {
      setSavingRoi(false)
    }
  }

  const displayHeight = naturalSize ? displayWidth * (naturalSize.height / naturalSize.width) : 0
  const canSaveRoi = Boolean(hasDraftRoi || lassoPoints.length > 0)

  return (
    <div
      role="presentation"
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.55)',
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: '#fff',
          borderRadius: 12,
          padding: 24,
          maxWidth: MAX_DISPLAY_WIDTH + 80,
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          zIndex: 10001,
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <h3 style={{ margin: '0 0 4px' }}>Camera / ROI — Table {table.number}</h3>
          <button type="button" className="btn-icon" onClick={onClose} aria-label="Close">×</button>
        </div>
        <p className="muted" style={{ fontSize: 13, margin: '0 0 16px' }}>
          Set the camera stream for this table, then lasso the table area in the frame.
          Only detections inside the saved region will count toward this table.
        </p>

        {/* Step A — camera URL */}
        <div className="panel-section">
          <h3 style={{ fontSize: 14 }}>1. Camera stream URL</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              className="input"
              style={{ flex: 1 }}
              placeholder="rtsp://... or a video file path"
              value={cameraUrl}
              onChange={(e) => setCameraUrl(e.target.value)}
            />
            <button type="button" className="btn btn-secondary" onClick={handleSaveCameraUrl} disabled={savingUrl}>
              {savingUrl ? 'Saving…' : 'Save URL'}
            </button>
          </div>
          {urlError && <p className="form-error">{urlError}</p>}
        </div>

        {/* Step B — snapshot + ROI lasso */}
        <div className="panel-section">
          <h3 style={{ fontSize: 14 }}>2. Lasso the region of interest</h3>
          <button type="button" className="btn btn-secondary" onClick={handleLoadSnapshot} disabled={loadingSnapshot}>
            {loadingSnapshot ? 'Loading…' : snapshotUrl ? 'Reload snapshot' : 'Load snapshot'}
          </button>
          {snapshotUrl && naturalSize && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 10 }}>
              {lassoPoints.length > 0 && (
                <button type="button" className="btn btn-secondary btn-sm" onClick={clearLasso}>
                  Clear lasso
                </button>
              )}
            </div>
          )}
          {snapshotError && <p className="form-error">{snapshotError}</p>}

          {snapshotUrl && (
            <div
              ref={imageFrameRef}
              onPointerDown={handleLassoStart}
              onPointerMove={handleLassoMove}
              onPointerUp={handleLassoEnd}
              onPointerCancel={handleLassoEnd}
              style={{
                position: 'relative',
                marginTop: 12,
                width: displayWidth,
                height: displayHeight || undefined,
                userSelect: 'none',
                overflow: 'hidden',
                touchAction: 'none',
                cursor: 'crosshair',
              }}
            >
              <img
                src={snapshotUrl}
                alt="Camera snapshot"
                width={displayWidth}
                style={{ display: 'block', borderRadius: 6 }}
                onLoad={(e) => handleImageLoaded(e.currentTarget)}
              />

              {lassoPoints.length > 0 && (
                <svg
                  aria-hidden="true"
                  viewBox={`0 0 ${displayWidth} ${displayHeight}`}
                  style={{
                    position: 'absolute',
                    inset: 0,
                    width: '100%',
                    height: '100%',
                    pointerEvents: 'none',
                  }}
                >
                  <polygon
                    points={lassoPoints.map((point) => `${point.x},${point.y}`).join(' ')}
                    fill="rgba(34, 197, 94, 0.16)"
                    stroke="none"
                  />
                  <polyline
                    points={lassoPoints.map((point) => `${point.x},${point.y}`).join(' ')}
                    fill="none"
                    stroke="#16a34a"
                    strokeWidth="3"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
          )}

          {snapshotUrl && naturalSize && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 12 }}>
              <button type="button" className="btn btn-primary" onClick={handleSaveRoi} disabled={savingRoi || !canSaveRoi}>
                {savingRoi ? 'Saving…' : 'Save ROI'}
              </button>
              {roiSaved && <span style={{ color: '#16a34a', fontSize: 13 }}>Saved ✓</span>}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
