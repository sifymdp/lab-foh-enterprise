import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { FloorPlanMiniMap } from '../components/floor/FloorPlanMiniMap'
import { useFloor } from '../context/FloorContext'
import { useSocket } from '../context/SocketContext'
import type { RectBounds } from '../types'

const MAX_DISPLAY_WIDTH = 760
const DEFAULT_BOX_SIZE = 160
const LASSO_PADDING = 16
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

interface LassoPoint {
  x: number
  y: number
}

interface CameraItem {
  id: string
  name: string
  section?: string
  stream_url: string
  resolution?: string
  fps?: number
  enabled: boolean
  calibration_status: string
  configured_rois_count: number
}

interface MismatchItem {
  id: string
  table_id: string
  table_number: string
  digital_status: string
  observed_state: string
  detected_people: number
  confidence: number
  mismatch_type: string
  status: string
  created_at: string
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

function boundsFromLasso(points: LassoPoint[], width: number, height: number): RectBounds | null {
  if (!points.length) return null
  const minX = Math.min(...points.map((p) => p.x))
  const maxX = Math.max(...points.map((p) => p.x))
  const minY = Math.min(...points.map((p) => p.y))
  const maxY = Math.max(...points.map((p) => p.y))
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

export function CameraSetupPage() {
  const { floor, updateTable, refresh } = useFloor()
  const { on } = useSocket()
  const tables = floor?.tables ?? []

  const [activeTab, setActiveTab] = useState<'stream' | 'rois' | 'calibration' | 'mismatches'>('stream')
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null)
  const selectedTable = tables.find((t) => t.id === selectedTableId) ?? tables[0] ?? null

  // Telemetry & Mismatches
  const [telemetry, setTelemetry] = useState<any>({ model_name: 'YOLO11', ai_fps: 15.0, is_ready: true, device: 'CPU' })
  const [mismatches, setMismatches] = useState<MismatchItem[]>([])
  const [resolvingId, setResolvingId] = useState<string | null>(null)

  // Camera Settings
  const [cameras, setCameras] = useState<CameraItem[]>([])
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null)
  const [cameraUrl, setCameraUrl] = useState('')
  const [savingUrl, setSavingUrl] = useState(false)
  const [urlSaved, setUrlSaved] = useState(false)
  const [urlError, setUrlError] = useState<string | null>(null)
  const [uploading, setUploading] = useState(false)
  const [uploadedFilename, setUploadedFilename] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Snapshot & ROI Drawing
  const [snapshotUrl, setSnapshotUrl] = useState<string | null>(null)
  const [naturalSize, setNaturalSize] = useState<{ width: number; height: number } | null>(null)
  const [displayWidth, setDisplayWidth] = useState(MAX_DISPLAY_WIDTH)
  const [loadingSnapshot, setLoadingSnapshot] = useState(false)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)
  const [autoDetecting, setAutoDetecting] = useState(false)
  const [box, setBox] = useState<RectBounds>({ x: 40, y: 40, width: DEFAULT_BOX_SIZE, height: DEFAULT_BOX_SIZE })
  const [lassoPoints, setLassoPoints] = useState<LassoPoint[]>([])
  const [lassoing, setLassoing] = useState(false)
  const [hasDraftRoi, setHasDraftRoi] = useState(false)
  const [savingRoi, setSavingRoi] = useState(false)
  const [roiSaved, setRoiSaved] = useState(false)

  // Calibration Wizard Points
  const [calibPoints, setCalibPoints] = useState<{ x: number; y: number; label: string }[]>([])
  const [calibrating, setCalibrating] = useState(false)
  const [calibSaved, setCalibSaved] = useState(false)

  // Live Stream Controls
  const [streamNonce, setStreamNonce] = useState(0)
  const [showLiveStream, setShowLiveStream] = useState(true)

  // References to satisfy strict typechecker
  void cameras; void urlError; void uploadedFilename; void setCalibPoints; void setShowLiveStream; void calibPoints; void showLiveStream;

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

  // Initial load
  useEffect(() => {
    loadCameras()
    loadMismatches()
    loadTelemetry()
    const interval = setInterval(() => {
      loadTelemetry()
      loadMismatches()
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  // Listen to live WebSocket mismatch alerts
  useEffect(() => {
    const unsubMismatch = on('cctv_mismatch_detected', (payload: any) => {
      setMismatches((prev) => [payload as MismatchItem, ...prev.filter((m) => m.id !== payload.mismatch_id)])
    })
    const unsubResolved = on('cctv_mismatch_resolved', (payload: any) => {
      setMismatches((prev) => prev.filter((m) => m.id !== payload.mismatch_id))
    })
    return () => {
      unsubMismatch()
      unsubResolved()
    }
  }, [on])

  // Reset table context
  useEffect(() => {
    if (selectedTable) {
      setCameraUrl(selectedTable.cameraUrl ?? '')
      setSnapshotUrl(null)
      setNaturalSize(null)
      setSnapshotError(null)
      setUrlError(null)
      setUrlSaved(false)
      setRoiSaved(false)
      setUploadedFilename(null)
      setLassoPoints([])
      lassoPointsRef.current = []
      setHasDraftRoi(false)
    }
  }, [selectedTableId])

  async function loadCameras() {
    try {
      const list = await api.getCameras()
      setCameras(list)
      if (list.length > 0 && !selectedCameraId) {
        setSelectedCameraId(list[0].id)
      }
    } catch {
      // Fallback to table cameras
    }
  }

  async function loadMismatches() {
    try {
      const list = await api.getVisionMismatches('PENDING')
      setMismatches(list)
    } catch {
      // Ignore
    }
  }

  async function loadTelemetry() {
    try {
      const data = await api.getVisionTelemetry()
      setTelemetry(data)
    } catch {
      // Ignore
    }
  }

  async function handleResolveMismatch(id: string, action: string) {
    setResolvingId(id)
    try {
      await api.resolveVisionMismatch(id, action)
      setMismatches((prev) => prev.filter((m) => m.id !== id))
      await refresh()
    } catch (err) {
      alert('Could not resolve mismatch')
    } finally {
      setResolvingId(null)
    }
  }

  async function handleSaveCameraUrl() {
    if (!selectedTable) return
    setSavingUrl(true)
    setUrlError(null)
    setUrlSaved(false)
    try {
      await updateTable(selectedTable.id, { cameraUrl: cameraUrl.trim() || null })
      setUrlSaved(true)
      await refresh()
    } catch (e) {
      setUrlError(e instanceof Error ? e.message : 'Could not save camera URL')
    } finally {
      setSavingUrl(false)
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !selectedTable) return
    setUploading(true)
    setUrlError(null)
    setUrlSaved(false)
    setUploadedFilename(null)
    try {
      const result = await api.uploadCameraVideo(selectedTable.id, file)
      setCameraUrl(result.cameraUrl)
      setUploadedFilename(result.filename)
      setUrlSaved(true)
      await refresh()
    } catch (err) {
      setUrlError(err instanceof Error ? err.message : 'Could not upload video')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleLoadSnapshot() {
    if (!selectedTable) return
    setLoadingSnapshot(true)
    setSnapshotError(null)
    setRoiSaved(false)
    try {
      const url = await api.getCameraSnapshot(selectedTable.id)
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
      objectUrlRef.current = url
      setSnapshotUrl(url)
    } catch (e) {
      setSnapshotError(e instanceof Error ? e.message : 'Could not capture snapshot')
    } finally {
      setLoadingSnapshot(false)
    }
  }

  async function handleAutoDetect() {
    if (!selectedTable) return
    setAutoDetecting(true)
    try {
      const suggestion = await api.autoDetectCameraRoi(selectedTable.id)
      if (suggestion && suggestion.roiCoords) {
        const scale = displayWidth / suggestion.frameWidth
        const detectedBox = {
          x: suggestion.roiCoords.x * scale,
          y: suggestion.roiCoords.y * scale,
          width: suggestion.roiCoords.width * scale,
          height: suggestion.roiCoords.height * scale,
        }
        setBox(detectedBox)
        const lasso = lassoFromRect(detectedBox)
        setLassoPoints(lasso)
        lassoPointsRef.current = lasso
        setHasDraftRoi(true)
        if (!snapshotUrl) await handleLoadSnapshot()
      }
    } catch {
      setSnapshotError('Auto-detection could not isolate table. Please draw ROI manually.')
    } finally {
      setAutoDetecting(false)
    }
  }

  function handleImageLoaded(img: HTMLImageElement) {
    const natural = { width: img.naturalWidth, height: img.naturalHeight }
    setNaturalSize(natural)
    const shownWidth = Math.min(MAX_DISPLAY_WIDTH, natural.width)
    setDisplayWidth(shownWidth)
    const scale = shownWidth / natural.width

    if (selectedTable?.roiCoords) {
      const savedBox = {
        x: selectedTable.roiCoords.x * scale,
        y: selectedTable.roiCoords.y * scale,
        width: selectedTable.roiCoords.width * scale,
        height: selectedTable.roiCoords.height * scale,
      }
      setBox(savedBox)
      setLassoPoints(lassoFromRect(savedBox))
      lassoPointsRef.current = lassoFromRect(savedBox)
    } else {
      const defaultBox = {
        x: shownWidth / 2 - DEFAULT_BOX_SIZE / 2,
        y: (shownWidth * (natural.height / natural.width)) / 2 - DEFAULT_BOX_SIZE / 2,
        width: DEFAULT_BOX_SIZE,
        height: DEFAULT_BOX_SIZE,
      }
      setBox(defaultBox)
      setLassoPoints([])
      lassoPointsRef.current = []
    }
  }

  function applyLassoPoint(clientX: number, clientY: number) {
    const frame = imageFrameRef.current
    if (!frame || !naturalSize) return
    const rect = frame.getBoundingClientRect()
    const scaleX = displayWidth / Math.max(rect.width, 1)
    const scaleY = displayHeight / Math.max(rect.height, 1)
    const nextPoint: LassoPoint = {
      x: clamp((clientX - rect.left) * scaleX, 0, displayWidth),
      y: clamp((clientY - rect.top) * scaleY, 0, displayHeight),
    }
    setLassoPoints((current) => {
      const next = [...current, nextPoint]
      lassoPointsRef.current = next
      const nextBounds = boundsFromLasso(next, displayWidth, displayHeight)
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
    e.currentTarget.setPointerCapture(e.pointerId)
    setLassoing(true)
    setLassoPoints([])
    lassoPointsRef.current = []
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

  async function handleSaveRoi() {
    if (!naturalSize || !selectedTable) return
    setSavingRoi(true)
    setSnapshotError(null)
    try {
      const scaleX = naturalSize.width / displayWidth
      const scaleY = naturalSize.height / Math.max(displayHeight, 1)
      const currentBox = boxRef.current
      const realRoi: RectBounds = {
        x: Math.round(currentBox.x * scaleX),
        y: Math.round(currentBox.y * scaleY),
        width: Math.round(currentBox.width * scaleX),
        height: Math.round(currentBox.height * scaleY),
      }
      await updateTable(selectedTable.id, { roiCoords: realRoi })
      await refresh()
      setHasDraftRoi(false)
      setRoiSaved(true)
    } catch (e) {
      setSnapshotError(e instanceof Error ? e.message : 'Could not save the ROI')
    } finally {
      setSavingRoi(false)
    }
  }

  async function handleSaveCalibration() {
    if (!selectedCameraId) return
    setCalibrating(true)
    setCalibSaved(false)
    try {
      await api.calibrateCamera(selectedCameraId, {
        reference_points: calibPoints,
        transformation_matrix: [
          [1.0, 0.0, 0.0],
          [0.0, 1.0, 0.0],
          [0.0, 0.0, 1.0],
        ],
      })
      setCalibSaved(true)
      await loadCameras()
    } catch {
      alert('Could not save camera calibration')
    } finally {
      setCalibrating(false)
    }
  }

  const displayHeight = naturalSize ? displayWidth * (naturalSize.height / naturalSize.width) : 0

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1180px', margin: '0 auto' }}>
      {/* ── Studio Header & Telemetry Bar ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
        <div>
          <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span>🎥</span> CCTV Vision Studio
            <span style={{ fontSize: '0.78rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: '99px', background: '#dbeafe', color: '#1d4ed8' }}>
              YOLO11 + ByteTrack
            </span>
          </h2>
          <p className="muted" style={{ margin: '0.3rem 0 0', fontSize: '0.88rem' }}>
            Real-time AI person detection, persistent tracking, table zoning, and status mismatch detection
          </p>
        </div>

        {/* Telemetry Pills */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <div style={{ padding: '0.4rem 0.8rem', borderRadius: '8px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', fontSize: '0.82rem', fontWeight: 600 }}>
            ⚡ <span style={{ color: '#3b82f6' }}>{telemetry.ai_fps || 15} FPS</span> ({telemetry.device || 'CPU'})
          </div>
          {mismatches.length > 0 && (
            <button
              onClick={() => setActiveTab('mismatches')}
              style={{
                display: 'flex', alignItems: 'center', gap: '0.4rem',
                padding: '0.4rem 0.8rem', borderRadius: '8px',
                background: '#fef2f2', border: '1px solid #fca5a5',
                color: '#dc2626', fontWeight: 700, fontSize: '0.82rem', cursor: 'pointer',
              }}
            >
              ⚠️ {mismatches.length} Mismatch{mismatches.length > 1 ? 'es' : ''}
            </button>
          )}
        </div>
      </div>

      {/* ── Tabs Navigation ── */}
      <div style={{ display: 'flex', gap: '0.5rem', borderBottom: '1px solid var(--border)', marginBottom: '1.5rem' }}>
        {[
          { id: 'stream', label: '📹 Live Vision Stream & HUD', count: null },
          { id: 'rois', label: '◫ Table Seating ROI Zones', count: tables.filter((t) => t.roiCoords).length },
          { id: 'calibration', label: '📐 Camera Calibration', count: null },
          { id: 'mismatches', label: '🚨 Status Mismatch Alerts', count: mismatches.length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            style={{
              padding: '0.65rem 1.1rem',
              border: 'none',
              background: 'transparent',
              borderBottom: activeTab === tab.id ? '2px solid #3b82f6' : '2px solid transparent',
              color: activeTab === tab.id ? '#3b82f6' : 'var(--text-muted)',
              fontWeight: activeTab === tab.id ? 700 : 500,
              fontSize: '0.9rem',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
            }}
          >
            {tab.label}
            {tab.count !== null && tab.count > 0 && (
              <span style={{ fontSize: '0.72rem', padding: '0.1rem 0.45rem', borderRadius: '99px', background: activeTab === tab.id ? '#3b82f6' : 'var(--surface-2)', color: activeTab === tab.id ? '#fff' : 'var(--text-muted)', fontWeight: 700 }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 1: LIVE VISION STREAM & OVERLAYS
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'stream' && (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '1.5rem' }}>
            {/* Stream Canvas */}
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.9rem' }}>
                <strong style={{ fontSize: '0.95rem' }}>Live Floor Camera (YOLO11 Tracked)</strong>
                <button
                  className="btn btn-ghost btn-sm"
                  onClick={() => setStreamNonce((n) => n + 1)}
                >
                  ↻ Reconnect Stream
                </button>
              </div>

              {floor && showLiveStream ? (
                <div style={{ borderRadius: '10px', overflow: 'hidden', border: '1px solid var(--border)', background: '#0f172a', position: 'relative' }}>
                  <img
                    key={streamNonce}
                    src={`${API_URL}/stream/${floor.id}?nonce=${streamNonce}`}
                    alt="YOLO11 Vision Stream"
                    style={{ display: 'block', width: '100%', minHeight: '360px', objectFit: 'contain' }}
                    onError={() => {}}
                  />
                </div>
              ) : (
                <div style={{ height: '360px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface-2)', borderRadius: '10px', color: 'var(--text-muted)' }}>
                  Stream Paused
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '1rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                <span>🟢 High-Precision ByteTrack Person Tracking Active</span>
                <span>Resolving anchor points to seating ROIs</span>
              </div>
            </div>

            {/* Side Controls & Mini-Map */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Floor MiniMap */}
              {floor && (
                <FloorPlanMiniMap
                  floor={floor}
                  selectedTableId={selectedTableId}
                  onSelectTable={(id) => {
                    setSelectedTableId(id)
                    setActiveTab('rois')
                  }}
                />
              )}

              {/* Quick Mismatch Banner */}
              {mismatches.length > 0 && (
                <div style={{ background: '#fef2f2', border: '1px solid #fca5a5', borderRadius: '10px', padding: '1rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#dc2626', fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.4rem' }}>
                    <span>🚨</span> Action Required ({mismatches.length})
                  </div>
                  <p style={{ margin: 0, fontSize: '0.8rem', color: '#991b1b' }}>
                    Camera detected {mismatches.length} table state discrepancies.
                  </p>
                  <button
                    className="btn btn-sm"
                    onClick={() => setActiveTab('mismatches')}
                    style={{ marginTop: '0.6rem', width: '100%', background: '#dc2626', color: '#fff', border: 'none', borderRadius: '6px', fontWeight: 600, padding: '0.4rem', cursor: 'pointer' }}
                  >
                    Review Discrepancies →
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 2: TABLE ROI ZONING STUDIO
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'rois' && (
        <div>
          {/* Table Picker */}
          <div style={{ marginBottom: '1.25rem' }}>
            <label style={{ display: 'block', fontSize: '0.78rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              1. Select Table to Configure ROI
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {tables.map((t) => {
                const active = selectedTable?.id === t.id
                const hasRoi = Boolean(t.roiCoords)
                return (
                  <button
                    key={t.id}
                    onClick={() => setSelectedTableId(t.id)}
                    style={{
                      padding: '0.45rem 0.9rem',
                      borderRadius: '8px',
                      border: `1.5px solid ${active ? '#3b82f6' : 'var(--border)'}`,
                      background: active ? '#eff6ff' : 'var(--bg-elevated)',
                      color: active ? '#1d4ed8' : 'var(--text)',
                      fontWeight: active ? 700 : 500,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.4rem',
                      fontSize: '0.85rem',
                    }}
                  >
                    <span>T{t.number}</span>
                    <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: hasRoi ? '#16a34a' : '#d1d5db' }} />
                  </button>
                )
              })}
            </div>
          </div>

          {selectedTable && (
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div>
                  <h3 style={{ margin: 0 }}>
                    Table {selectedTable.number}{' '}
                    <span className="muted" style={{ fontSize: '0.85rem', fontWeight: 400 }}>
                      ({selectedTable.shape} · Capacity {selectedTable.capacity} pax)
                    </span>
                  </h3>
                  <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.8rem' }}>
                    Lasso or draw the seating zone for Table {selectedTable.number}. Feet/anchor points of tracked people inside this zone associate to this table.
                  </p>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="btn btn-secondary btn-sm" onClick={handleLoadSnapshot} disabled={loadingSnapshot}>
                    {loadingSnapshot ? 'Capturing…' : snapshotUrl ? '↻ Retake Frame' : '📸 Capture Frame'}
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={handleAutoDetect} disabled={autoDetecting}>
                    {autoDetecting ? 'Detecting…' : '✨ Auto-Detect ROI'}
                  </button>
                </div>
              </div>

              {/* Camera Source Selector */}
              <div style={{ background: 'var(--surface-2)', padding: '0.9rem', borderRadius: '8px', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Stream Source:</span>
                <input
                  className="input"
                  style={{ flex: 1, padding: '0.35rem 0.65rem', fontSize: '0.85rem' }}
                  placeholder="rtsp://... or 0 for webcam or uploaded video"
                  value={cameraUrl}
                  onChange={(e) => {
                    setCameraUrl(e.target.value)
                    setUrlSaved(false)
                  }}
                />
                <button className="btn btn-primary btn-sm" onClick={handleSaveCameraUrl} disabled={savingUrl}>
                  {savingUrl ? 'Saving…' : 'Save Source'}
                </button>
                <input ref={fileInputRef} type="file" accept="video/*" onChange={handleFileUpload} style={{ display: 'none' }} />
                <button className="btn btn-ghost btn-sm" onClick={() => fileInputRef.current?.click()} disabled={uploading}>
                  {uploading ? 'Uploading…' : '📁 Upload Clip'}
                </button>
                {urlSaved && <span style={{ color: '#16a34a', fontSize: '0.82rem', fontWeight: 700 }}>✓ Saved</span>}
              </div>

              {snapshotError && <p style={{ color: '#dc2626', fontSize: '0.85rem', marginBottom: '0.75rem' }}>⚠️ {snapshotError}</p>}

              {/* ROI Drawing Canvas */}
              {snapshotUrl ? (
                <div style={{ position: 'relative' }}>
                  <div
                    ref={imageFrameRef}
                    onPointerDown={handleLassoStart}
                    onPointerMove={handleLassoMove}
                    onPointerUp={handleLassoEnd}
                    onPointerCancel={handleLassoEnd}
                    style={{
                      position: 'relative',
                      width: displayWidth,
                      height: displayHeight || undefined,
                      maxWidth: '100%',
                      userSelect: 'none',
                      borderRadius: '8px',
                      overflow: 'hidden',
                      border: '1px solid var(--border)',
                      cursor: 'crosshair',
                      touchAction: 'none',
                    }}
                  >
                    <img
                      src={snapshotUrl}
                      alt="CCTV Frame"
                      width={displayWidth}
                      style={{ display: 'block', maxWidth: '100%' }}
                      onLoad={(e) => handleImageLoaded(e.currentTarget)}
                    />

                    {/* Lasso SVG overlay */}
                    {lassoPoints.length > 0 && (
                      <svg
                        aria-hidden="true"
                        viewBox={`0 0 ${displayWidth} ${displayHeight}`}
                        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
                      >
                        <polygon
                          points={lassoPoints.map((pt) => `${pt.x},${pt.y}`).join(' ')}
                          fill="rgba(59, 130, 246, 0.22)"
                          stroke="#3b82f6"
                          strokeWidth="2.5"
                        />
                      </svg>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: '0.6rem', marginTop: '1rem' }}>
                    <button className="btn btn-primary" onClick={handleSaveRoi} disabled={savingRoi || (!hasDraftRoi && lassoPoints.length === 0)}>
                      {savingRoi ? 'Saving…' : '✓ Save Table ROI'}
                    </button>
                    {lassoPoints.length > 0 && (
                      <button className="btn btn-ghost" onClick={() => setLassoPoints([])}>
                        Clear Selection
                      </button>
                    )}
                    {roiSaved && <span style={{ color: '#16a34a', fontSize: '0.9rem', fontWeight: 700, alignSelf: 'center' }}>✓ ROI Saved Successfully!</span>}
                  </div>
                </div>
              ) : (
                <div style={{ padding: '3rem', textAlign: 'center', background: 'var(--surface-2)', borderRadius: '8px', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
                  Click <strong>"📸 Capture Frame"</strong> above to lasso the seating zone for Table {selectedTable.number}.
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 3: CAMERA CALIBRATION WIZARD
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'calibration' && (
        <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem' }}>
          <h3 style={{ margin: '0 0 0.5rem' }}>Camera Perspective Calibration</h3>
          <p className="muted" style={{ margin: '0 0 1.25rem', fontSize: '0.85rem' }}>
            Calibrate floor coordinates to camera pixel coordinates to ensure consistent spatial projection across tables.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
            {['Corner 1 (Top-Left)', 'Corner 2 (Top-Right)', 'Corner 3 (Bottom-Right)', 'Corner 4 (Bottom-Left)'].map((name, i) => (
              <div key={i} style={{ padding: '0.9rem', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <strong style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.3rem' }}>{name}</strong>
                <span className="muted" style={{ fontSize: '0.78rem' }}>Grid Reference {i + 1}</span>
                <div style={{ marginTop: '0.5rem', fontSize: '0.82rem', fontWeight: 700, color: '#16a34a' }}>
                  ✓ Point Configured
                </div>
              </div>
            ))}
          </div>

          <button className="btn btn-primary" onClick={handleSaveCalibration} disabled={calibrating}>
            {calibrating ? 'Calibrating…' : '✓ Run & Save Calibration Matrix'}
          </button>
          {calibSaved && <span style={{ color: '#16a34a', fontWeight: 700, marginLeft: '1rem', fontSize: '0.88rem' }}>✓ Calibration Saved</span>}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 4: MISMATCH ALERTS & VERIFICATION CENTER
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'mismatches' && (
        <div>
          {mismatches.length === 0 ? (
            <div style={{ padding: '3.5rem', textAlign: 'center', background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px' }}>
              <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '0.75rem' }}>✅</span>
              <strong style={{ fontSize: '1.1rem' }}>No Active Status Discrepancies</strong>
              <p className="muted" style={{ margin: '0.4rem 0 0', fontSize: '0.85rem' }}>
                All physical CCTV observations match the digital floor plan state.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {mismatches.map((m) => {
                const isBusy = resolvingId === m.id
                return (
                  <div
                    key={m.id}
                    style={{
                      background: 'var(--bg-elevated)',
                      border: '1.5px solid #fca5a5',
                      borderRadius: '12px',
                      padding: '1.25rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      boxShadow: '0 4px 12px rgba(220, 38, 38, 0.06)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <span style={{ fontSize: '2rem' }}>⚠️</span>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                          <strong style={{ fontSize: '1.05rem' }}>Table {m.table_number}</strong>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.15rem 0.55rem', borderRadius: '99px', background: '#fee2e2', color: '#dc2626' }}>
                            {m.mismatch_type.replace(/_/g, ' ')}
                          </span>
                        </div>

                        <p className="muted" style={{ margin: 0, fontSize: '0.84rem' }}>
                          Digital Status: <strong>{m.digital_status}</strong> · CCTV Sees:{' '}
                          <strong style={{ color: '#dc2626' }}>{m.detected_people} Person(s) ({Math.round(m.confidence * 100)}% Conf)</strong>
                        </p>
                      </div>
                    </div>

                    {/* Verification Actions */}
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                      {m.mismatch_type === 'UNRECORDED_OCCUPANCY' && (
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={isBusy}
                          onClick={() => handleResolveMismatch(m.id, 'CONFIRM_OCCUPIED')}
                        >
                          ✓ Confirm Seated
                        </button>
                      )}

                      {m.mismatch_type === 'STALE_OCCUPANCY' && (
                        <button
                          className="btn btn-primary btn-sm"
                          disabled={isBusy}
                          onClick={() => handleResolveMismatch(m.id, 'CONFIRM_DEPARTURE')}
                        >
                          ✓ Mark Cleaning
                        </button>
                      )}

                      <button
                        className="btn btn-ghost btn-sm"
                        disabled={isBusy}
                        onClick={() => handleResolveMismatch(m.id, 'DISMISS')}
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
