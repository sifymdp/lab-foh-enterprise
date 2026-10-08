import { useEffect, useRef, useState } from 'react'
import { api } from '../api/client'
import { FloorPlanMiniMap } from '../components/floor/FloorPlanMiniMap'
import { DigitalFloorPlanView } from '../components/floor/DigitalFloorPlanView'
import { LiveStreamPlayer } from '../components/vision/LiveStreamPlayer'
import { VisionModelManagementPanel } from '../components/vision/VisionModelManagementPanel'
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
  source_type?: string
  is_online?: boolean
  health_status?: string
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

interface AISuggestion {
  id: string
  camera_id: string
  floor_id: string
  suggestion_type: 'POSITION_CHANGE' | 'NEW_TABLE' | 'REMOVED_TABLE' | 'SIZE_CHANGE' | 'UNCERTAIN' | 'MATCHED'
  existing_table_id?: string
  existing_table?: {
    id: string
    label: string
    x: number
    y: number
    width: number
    height: number
    shape: string
    section?: string
  }
  suggested_label?: string
  detected_position: {
    x: number
    y: number
    width: number
    height: number
    shape?: string
    shape_confidence?: number
    capacity?: number
    section?: string
    perspective_zone?: string
    confidence_tier?: string
  }
  camera_bbox?: {
    x: number
    y: number
    width: number
    height: number
  }
  confidence: number
  drift_distance?: number
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'APPLIED' | 'IGNORED'
  review_notes?: string
}

interface VideoSourceMode {
  id: string
  mode_number: number
  label: string
  is_demo: boolean
  description: string
  example: string
  default_url: string
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

  // Active Main Tab
  const [activeTab, setActiveTab] = useState<'ai_floor_plan' | 'stream' | 'rois' | 'calibration' | 'mismatches' | 'benchmark'>('ai_floor_plan')
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null)
  const selectedTable = tables.find((t) => t.id === selectedTableId) ?? tables[0] ?? null

  // Telemetry & Mismatches
  const [telemetry, setTelemetry] = useState<any>({ model_name: 'YOLO11', ai_fps: 15.0, is_ready: true, device: 'CPU' })
  const [mismatches, setMismatches] = useState<MismatchItem[]>([])
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [showDetailedQueue, setShowDetailedQueue] = useState(false)

  // Camera & Video Sources
  const [cameras, setCameras] = useState<CameraItem[]>([])
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null)
  const [availableClips, setAvailableClips] = useState<string[]>([])
  const [selectedModeId, setSelectedModeId] = useState<string>(() => {
    return localStorage.getItem('foh_selected_camera_mode') || 'DEMO_STREAM'
  })
  const [cameraUrl, setCameraUrl] = useState<string>(() => {
    return localStorage.getItem('foh_camera_url') || 'https://www.youtube.com/watch?v=DBl7MmHlQK0'
  })
  const [savingUrl, setSavingUrl] = useState(false)
  const [urlSaved, setUrlSaved] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [sourceTestResult, setSourceTestResult] = useState<any | null>(null)
  const [testingSource, setTestingSource] = useState(false)
  const [sourceErrorWarning, setSourceErrorWarning] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // AI Floor Plan Discovery & Review State
  const [aiDetecting, setAiDetecting] = useState(false)
  const [aiReport, setAiReport] = useState<any | null>(null)
  const [suggestions, setSuggestions] = useState<AISuggestion[]>([])
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string | null>(null)
  const [applyingApproved, setApplyingApproved] = useState(false)
  const [applyResultBanner, setApplyResultBanner] = useState<string | null>(null)
  const [floorPlanViewMode, setFloorPlanViewMode] = useState<'current' | 'ai_suggested' | 'overlay'>('overlay')
  const [reconstructMode, setReconstructMode] = useState<boolean>(true)
  const [clearingFloor, setClearingFloor] = useState<boolean>(false)
  const [reconstructing, setReconstructing] = useState<boolean>(false)
  const [showSourceSettings, setShowSourceSettings] = useState<boolean>(false)

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
  const [calibrating, setCalibrating] = useState(false)
  const [calibSaved, setCalibSaved] = useState(false)
  const [cameraCalibration, setCameraCalibration] = useState<any | null>(null)

  // Benchmark State
  const [benchmarking, setBenchmarking] = useState(false)
  const [benchmarkResult, setBenchmarkResult] = useState<any | null>(null)

  // Live Stream Controls
  const [streamNonce, setStreamNonce] = useState(0)
  const [showLiveStream, setShowLiveStream] = useState(true)

  void setBox; void setShowLiveStream; void showLiveStream; void streamNonce;

  const objectUrlRef = useRef<string | null>(null)
  const imageFrameRef = useRef<HTMLDivElement>(null)
  const boxRef = useRef(box)
  const lassoPointsRef = useRef<LassoPoint[]>([])

  // The 6 explicit modes defined by the system specification
  const MODES: VideoSourceMode[] = [
    {
      id: 'RTSP',
      mode_number: 1,
      label: 'Mode 1: Real CCTV / RTSP',
      is_demo: false,
      description: 'Production IP Cameras & Network Video Recorders (H.264/H.265 RTSP)',
      example: 'rtsp://admin:pass@192.168.1.100:554/live',
      default_url: 'rtsp://admin:Password123@192.168.1.100:554/stream',
    },
    {
      id: 'ONVIF',
      mode_number: 2,
      label: 'Mode 2: ONVIF Camera',
      is_demo: false,
      description: 'ONVIF Profile S/T Auto-Discovery & Configuration endpoint',
      example: 'http://192.168.1.120:80/onvif/device_service',
      default_url: 'http://192.168.1.120:80/onvif/device_service',
    },
    {
      id: 'WEBCAM',
      mode_number: 3,
      label: 'Mode 3: Local Webcam (Camera 0, 1)',
      is_demo: true,
      description: 'Developer / Laptop integrated or USB webcam device index',
      example: '0 or 1',
      default_url: '0',
    },
    {
      id: 'VIDEO_FILE',
      mode_number: 4,
      label: 'Mode 4: Uploaded Restaurant Video (MP4, AVI, MOV)',
      is_demo: true,
      description: 'Real restaurant dining room recordings with looping playback',
      example: 'table_t-1.mp4',
      default_url: 'table_t-1.mp4',
    },
    {
      id: 'DEMO_STREAM',
      mode_number: 5,
      label: 'Mode 5: Demo / External Live Stream with DemoStreamAdapter',
      is_demo: true,
      description: 'External restaurant live stream or YouTube video (analyzed with yt-dlp & YOLO)',
      example: 'https://www.youtube.com/watch?v=DBl7MmHlQK0',
      default_url: 'https://www.youtube.com/watch?v=DBl7MmHlQK0',
    },
    {
      id: 'SYNTHETIC',
      mode_number: 6,
      label: 'Mode 6: Synthetic Restaurant Simulation (offline testing fallback)',
      is_demo: true,
      description: 'Procedural simulated dining room with tables and dynamic patrons',
      example: 'synthetic://dining-room',
      default_url: 'synthetic',
    },
  ]

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
    loadSources()
    const interval = setInterval(() => {
      loadTelemetry()
      loadMismatches()
    }, 4000)
    return () => clearInterval(interval)
  }, [])

  // Listen to live WebSocket events
  useEffect(() => {
    const unsubMismatch = on('cctv_mismatch_detected', (payload: any) => {
      setMismatches((prev) => [payload as MismatchItem, ...prev.filter((m) => m.id !== payload.mismatch_id)])
    })
    const unsubResolved = on('cctv_mismatch_resolved', (payload: any) => {
      setMismatches((prev) => prev.filter((m) => m.id !== payload.mismatch_id))
    })
    const unsubLayoutUpdated = on('floor_plan.updated', () => {
      refresh()
      if (floor?.id) loadSuggestions(floor.id)
    })
    return () => {
      unsubMismatch()
      unsubResolved()
      unsubLayoutUpdated()
    }
  }, [on, floor?.id])

  // Load suggestions when floor is available
  useEffect(() => {
    if (floor?.id) {
      loadSuggestions(floor.id)
    }
  }, [floor?.id])

  // Reset table context
  useEffect(() => {
    if (selectedTable) {
      if (selectedTable.cameraUrl && selectedModeId === 'RTSP') {
        setCameraUrl(selectedTable.cameraUrl)
      }
      setSnapshotUrl(null)
      setNaturalSize(null)
      setSnapshotError(null)
      setUrlSaved(false)
      setRoiSaved(false)
      setLassoPoints([])
      lassoPointsRef.current = []
      setHasDraftRoi(false)
    }
  }, [selectedTableId])

  async function loadSources() {
    try {
      const data = await api.getVisionSources()
      if (data && data.available_video_files) {
        setAvailableClips(data.available_video_files)
        if (data.available_video_files.length > 0 && selectedModeId === 'VIDEO_FILE') {
          setCameraUrl(data.available_video_files[0])
        }
      }
    } catch {
      // Fallback
    }
  }

  async function loadCameras() {
    try {
      const list = await api.getCameras()
      setCameras(list)
      if (list.length > 0) {
        if (!selectedCameraId) {
          setSelectedCameraId(list[0].id)
        }
        const savedMode = localStorage.getItem('foh_selected_camera_mode')
        const savedUrl = localStorage.getItem('foh_camera_url')

        if (savedMode) {
          setSelectedModeId(savedMode)
        } else if (list[0].source_type) {
          setSelectedModeId(list[0].source_type)
        }

        if (savedUrl) {
          setCameraUrl(savedUrl)
        } else if (list[0].stream_url) {
          setCameraUrl(list[0].stream_url)
        }
        loadCalibration(list[0].id)
      }
    } catch {
      // Fallback
    }
  }

  async function loadCalibration(cameraId: string) {
    try {
      const res = await api.getCameraCalibration(cameraId)
      setCameraCalibration(res?.calibration || null)
    } catch {
      setCameraCalibration(null)
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

  async function loadSuggestions(floorId: string) {
    try {
      const list = await api.getFloorPlanSuggestions(floorId)
      setSuggestions(list || [])
    } catch {
      // Ignore
    }
  }

  async function handleSelectMode(mode: VideoSourceMode) {
    setSelectedModeId(mode.id)
    localStorage.setItem('foh_selected_camera_mode', mode.id)
    setSourceErrorWarning(null)
    setSourceTestResult(null)

    let newUrl = mode.default_url
    if (mode.id === 'VIDEO_FILE') {
      newUrl = availableClips.length > 0 ? availableClips[0] : 'table_t-1.mp4'
    } else if (mode.id === 'WEBCAM') {
      newUrl = '0'
    } else if (mode.id === 'SYNTHETIC') {
      newUrl = 'synthetic'
    } else if (mode.id === 'DEMO_STREAM') {
      const saved = localStorage.getItem('foh_camera_url')
      if (saved && (saved.includes('youtube.com') || saved.includes('youtu.be'))) {
        newUrl = saved
      } else if (cameraUrl && (cameraUrl.includes('youtube.com') || cameraUrl.includes('youtu.be'))) {
        newUrl = cameraUrl
      }
    }

    setCameraUrl(newUrl)
    localStorage.setItem('foh_camera_url', newUrl)

    // Persist to backend camera database record immediately
    const camId = selectedCameraId || (cameras[0]?.id ?? 'cam-t-1')
    if (camId) {
      try {
        await api.updateCamera(camId, {
          source_type: mode.id,
          stream_url: newUrl,
          floor_id: floor?.id || 'floor-1',
        })
      } catch (e) {
        console.warn('Failed to update camera source in DB:', e)
      }
    }
  }

  async function handleAutoPersistUrl(url: string, modeId: string) {
    if (!url.trim()) return
    localStorage.setItem('foh_camera_url', url.trim())
    localStorage.setItem('foh_selected_camera_mode', modeId)
    const camId = selectedCameraId || (cameras[0]?.id ?? 'cam-t-1')
    if (camId) {
      try {
        await api.updateCamera(camId, {
          source_type: modeId,
          stream_url: url.trim(),
          floor_id: floor?.id || 'floor-1',
        })
      } catch (e) {
        console.warn('Auto-persist URL failed:', e)
      }
    }
  }

  async function applyPresetUrl(url: string, modeId?: string) {
    const targetMode = modeId || selectedModeId
    if (modeId && modeId !== selectedModeId) {
      setSelectedModeId(modeId)
      localStorage.setItem('foh_selected_camera_mode', modeId)
    }
    setCameraUrl(url)
    localStorage.setItem('foh_camera_url', url)
    setSourceErrorWarning(null)
    const camId = selectedCameraId || (cameras[0]?.id ?? 'cam-t-1')
    if (camId) {
      try {
        await api.updateCamera(camId, {
          source_type: targetMode,
          stream_url: url,
          floor_id: floor?.id || 'floor-1',
        })
      } catch (e) {
        console.warn('Auto-persist preset failed:', e)
      }
    }
  }

  async function handleTestSource() {
    setTestingSource(true)
    setSourceErrorWarning(null)
    setSourceTestResult(null)


    try {
      const res = await api.testVideoSource({
        source_type: selectedModeId,
        stream_url: cameraUrl,
      })
      setSourceTestResult(res)
      if (!res.success && res.error) {
        setSourceErrorWarning(res.error)
      }
    } catch (err: any) {
      setSourceErrorWarning('Failed to connect to video source. Please verify stream URL and permissions.')
    } finally {
      setTestingSource(false)
    }
  }

  async function handleTriggerFloorPlanDetection() {
    if (!floor?.id) return
    const camId = selectedCameraId || (cameras[0]?.id ?? 'cam_default')
    setAiDetecting(true)
    setApplyResultBanner(null)
    setSourceErrorWarning(null)


    try {
      const report = await api.detectFloorLayout({
        camera_id: camId,
        floor_id: floor.id,
        override_stream_url: cameraUrl,
        source_type: selectedModeId,
        min_confidence: 0.35,
        reconstruct_mode: reconstructMode,
      })
      setAiReport(report)
      await loadSuggestions(floor.id)
      setFloorPlanViewMode('ai_suggested')
      setStreamNonce((n) => n + 1)
    } catch (err: any) {
      alert(`AI Floor Plan Detection failed: ${err.message || 'Unknown error'}`)
    } finally {
      setAiDetecting(false)
    }
  }

  async function handleClearFloorPlan() {
    if (!floor?.id) return
    if (!window.confirm('Are you sure you want to remove all existing tables from this floor plan? This will clear the layout so you can build a clean digital twin directly from the video.')) {
      return
    }
    setClearingFloor(true)
    setApplyResultBanner(null)
    try {
      const res = await api.clearFloorPlan(floor.id)
      setApplyResultBanner(`🧹 Removed ${res.cleared_count} old tables. Floor plan is now clean and ready for video reconstruction!`)
      await refresh()
      await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Failed to clear floor plan: ${err.message}`)
    } finally {
      setClearingFloor(false)
    }
  }

  async function handleDirectReconstruct() {
    if (!floor?.id) return
    const camId = selectedCameraId || (cameras[0]?.id ?? 'cam_default')
    setReconstructing(true)
    setApplyResultBanner(null)
    setSourceErrorWarning(null)


    try {
      const res = await api.reconstructFloorPlanFromVideo({
        camera_id: camId,
        floor_id: floor.id,
        override_stream_url: cameraUrl,
        source_type: selectedModeId,
        min_confidence: 0.35,
        replace_existing: reconstructMode,
      })
      if (res.success) {
        setApplyResultBanner(`✓ Reconstructed ${res.created_count} real tables directly from the video stream! Floor version #${res.version_number} saved with full audit log.`)
        await refresh()
        await loadSuggestions(floor.id)
        setStreamNonce((n) => n + 1)
      } else {
        alert(res.message || 'Reconstruction completed with 0 tables')
      }
    } catch (err: any) {
      alert(`Reconstruction failed: ${err.message}`)
    } finally {
      setReconstructing(false)
    }
  }

  async function handleSuggestionAction(suggestionId: string, action: 'APPROVE' | 'REJECT' | 'IGNORE') {
    try {
      await api.actionFloorPlanSuggestion(suggestionId, { action })
      if (floor?.id) await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Action failed: ${err.message}`)
    }
  }

  async function handleMakeSingleTable(suggestionId: string) {
    if (!floor?.id) return
    setApplyingApproved(true)
    try {
      const res = await api.applyApprovedFloorPlan({
        floor_id: floor.id,
        suggestion_ids: [suggestionId],
        replace_existing: false,
      })
      setApplyResultBanner(`✓ Table successfully added/updated in floor plan! Floor Version #${res.version_number} snapshot recorded.`)
      await refresh()
      await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Failed to make table: ${err.message}`)
    } finally {
      setApplyingApproved(false)
    }
  }

  async function handleMakeAllTables(replaceOld: boolean = reconstructMode) {
    if (!floor?.id) return
    const ids = suggestions.filter((s) => s.status !== 'REJECTED' && s.status !== 'APPLIED').map((s) => s.id)
    if (ids.length === 0) {
      alert('No candidate tables available to make.')
      return
    }
    setApplyingApproved(true)
    try {
      const res = await api.applyApprovedFloorPlan({
        floor_id: floor.id,
        suggestion_ids: ids,
        replace_existing: replaceOld,
      })
      setApplyResultBanner(`✓ Successfully synchronized ${res.applied_count} tables into official floor plan! (Replaced old: ${replaceOld ? 'Yes' : 'No'}). Version #${res.version_number} created with audit log.`)
      await refresh()
      await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Failed to make tables: ${err.message}`)
    } finally {
      setApplyingApproved(false)
    }
  }

  async function handleApproveAllSuggestions() {
    if (!floor?.id) return
    const pending = suggestions.filter((s) => s.status === 'PENDING')
    if (pending.length === 0) {
      alert('No pending candidate tables to approve.')
      return
    }
    setApplyingApproved(true)
    try {
      await Promise.all(
        pending.map((s) => api.actionFloorPlanSuggestion(s.id, { action: 'APPROVE' }))
      )
      setApplyResultBanner(`✓ Approved all ${pending.length} candidate tables! Click 'Make All Tables' to register them to the floor plan.`)
      await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Bulk approval failed: ${err.message}`)
    } finally {
      setApplyingApproved(false)
    }
  }

  async function handleApplyApprovedChanges() {
    if (!floor?.id) return
    const approvedIds = suggestions.filter((s) => s.status === 'APPROVED').map((s) => s.id)
    if (approvedIds.length === 0) {
      alert('Please approve at least one detected table suggestion before applying.')
      return
    }

    setApplyingApproved(true)
    try {
      const res = await api.applyApprovedFloorPlan({
        floor_id: floor.id,
        suggestion_ids: approvedIds,
        replace_existing: reconstructMode,
      })
      setApplyResultBanner(`✓ Applied ${res.applied_count} table updates to floor plan! Version #${res.version_number} snapshot created with audit log.`)
      await refresh()
      await loadSuggestions(floor.id)
    } catch (err: any) {
      alert(`Failed to apply changes: ${err.message}`)
    } finally {
      setApplyingApproved(false)
    }
  }

  async function handleRunBenchmark() {
    setBenchmarking(true)
    try {
      const res = await api.runVisionBenchmark({
        sample_frames: 15,
        video_source: cameraUrl.endsWith('.mp4') ? cameraUrl : 'table_t-1.mp4',
      })
      setBenchmarkResult(res)
    } catch (err: any) {
      alert(`Benchmark failed: ${err.message}`)
    } finally {
      setBenchmarking(false)
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
    if (!cameraUrl.trim()) return
    setSavingUrl(true)
    setUrlSaved(false)
    localStorage.setItem('foh_selected_camera_mode', selectedModeId)
    localStorage.setItem('foh_camera_url', cameraUrl.trim())

    try {
      if (selectedTable) {
        await updateTable(selectedTable.id, { cameraUrl: cameraUrl.trim() })
      }
      const camId = selectedCameraId || (cameras[0]?.id ?? 'cam-t-1')
      if (camId) {
        await api.updateCamera(camId, {
          source_type: selectedModeId,
          stream_url: cameraUrl.trim(),
          floor_id: floor?.id || 'floor-1',
        })
      }
      setUrlSaved(true)
      setTimeout(() => setUrlSaved(false), 3000)
    } catch (err: any) {
      alert('Failed to save source')
    } finally {
      setSavingUrl(false)
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const formData = new FormData()
      formData.append('file', file)
      const res = await fetch(`${API_URL}/vision/upload-clip`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
        body: formData,
      })
      if (!res.ok) throw new Error('Failed to upload video clip')
      const data = await res.json()
      setCameraUrl(data.filename)
      setSelectedModeId('VIDEO_FILE')
      await loadSources()
    } catch (err: any) {
      alert(err.message || 'Upload failed')
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  async function handleLoadSnapshot() {
    const tableId = selectedTable?.id
    if (!tableId) return
    setLoadingSnapshot(true)
    setSnapshotError(null)
    setRoiSaved(false)
    setSnapshotUrl(null)
    setLassoPoints([])
    lassoPointsRef.current = []
    setHasDraftRoi(false)
    try {
      const res = await fetch(`${API_URL}/tables/${tableId}/snapshot`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
      })
      if (!res.ok) {
        throw new Error('Camera is offline or stream is unreachable.')
      }
      const blob = await res.blob()
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current)
      const url = URL.createObjectURL(blob)
      objectUrlRef.current = url
      setSnapshotUrl(url)
    } catch (err: any) {
      setSnapshotError(err.message)
    } finally {
      setLoadingSnapshot(false)
    }
  }

  function handleImageLoaded(img: HTMLImageElement) {
    const nw = img.naturalWidth || 1280
    const nh = img.naturalHeight || 720
    setNaturalSize({ width: nw, height: nh })
    const rect = imageFrameRef.current?.getBoundingClientRect()
    const dw = rect?.width ? Math.min(rect.width, MAX_DISPLAY_WIDTH) : MAX_DISPLAY_WIDTH
    setDisplayWidth(dw)

    if (selectedTable?.roiCoords) {
      const scaleX = dw / nw
      const scaleY = (dw * (nh / nw)) / nh
      const norm = selectedTable.roiCoords
      const b: RectBounds = {
        x: norm.x * scaleX,
        y: norm.y * scaleY,
        width: norm.width * scaleX,
        height: norm.height * scaleY,
      }
      setBox(b)
      setLassoPoints(lassoFromRect(b))
      setHasDraftRoi(true)
    }
  }

  function handleLassoStart(e: React.PointerEvent<HTMLDivElement>) {
    if (!imageFrameRef.current) return
    const rect = imageFrameRef.current.getBoundingClientRect()
    const x = clamp(e.clientX - rect.left, 0, rect.width)
    const y = clamp(e.clientY - rect.top, 0, rect.height)
    setLassoing(true)
    setLassoPoints([{ x, y }])
    setHasDraftRoi(true)
    setRoiSaved(false)
  }

  function handleLassoMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!lassoing || !imageFrameRef.current) return
    const rect = imageFrameRef.current.getBoundingClientRect()
    const x = clamp(e.clientX - rect.left, 0, rect.width)
    const y = clamp(e.clientY - rect.top, 0, rect.height)
    setLassoPoints((prev) => [...prev, { x, y }])
  }

  function handleLassoEnd() {
    if (!lassoing) return
    setLassoing(false)
    if (naturalSize && lassoPoints.length > 2) {
      const h = naturalSize.width ? displayWidth * (naturalSize.height / naturalSize.width) : 480
      const b = boundsFromLasso(lassoPoints, displayWidth, h)
      if (b) setBox(b)
    }
  }

  async function handleAutoDetect() {
    const tableId = selectedTable?.id
    if (!tableId) return
    setAutoDetecting(true)
    try {
      const res = await fetch(`${API_URL}/tables/${tableId}/detect-roi`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token') || ''}`,
        },
      })
      if (!res.ok) throw new Error('Auto-detection failed')
      const data = await res.json()
      if (data.bounds && naturalSize) {
        const scaleX = displayWidth / naturalSize.width
        const scaleY = (displayWidth * (naturalSize.height / naturalSize.width)) / naturalSize.height
        const detectedBox: RectBounds = {
          x: data.bounds.x * scaleX,
          y: data.bounds.y * scaleY,
          width: data.bounds.width * scaleX,
          height: data.bounds.height * scaleY,
        }
        setBox(detectedBox)
        setLassoPoints(lassoFromRect(detectedBox))
        setHasDraftRoi(true)
      }
    } catch (err: any) {
      alert(err.message || 'Auto-detection failed')
    } finally {
      setAutoDetecting(false)
    }
  }

  async function handleSaveRoi() {
    if (!selectedTable || !naturalSize) return
    setSavingRoi(true)
    setRoiSaved(false)
    try {
      const h = displayWidth * (naturalSize.height / naturalSize.width)
      const finalBounds = boundsFromLasso(lassoPoints, displayWidth, h) || box
      const scaleX = naturalSize.width / displayWidth
      const scaleY = naturalSize.height / h

      const normalizedRoi: RectBounds = {
        x: Math.round(finalBounds.x * scaleX),
        y: Math.round(finalBounds.y * scaleY),
        width: Math.round(finalBounds.width * scaleX),
        height: Math.round(finalBounds.height * scaleY),
      }

      await updateTable(selectedTable.id, { roiCoords: normalizedRoi })
      setRoiSaved(true)
      setTimeout(() => setRoiSaved(false), 3000)
    } catch (err: any) {
      alert('Failed to save ROI')
    } finally {
      setSavingRoi(false)
    }
  }

  async function handleSaveCalibration() {
    const camId = selectedCameraId || cameras[0]?.id
    if (!camId) return
    setCalibrating(true)
    setCalibSaved(false)
    try {
      const defaultPoints = [
        { camera: { x: 100, y: 100 }, floor: { x: 50, y: 50 } },
        { camera: { x: 1180, y: 100 }, floor: { x: 950, y: 50 } },
        { camera: { x: 1180, y: 620 }, floor: { x: 950, y: 650 } },
        { camera: { x: 100, y: 620 }, floor: { x: 50, y: 650 } },
      ]
      await api.calibrateCamera(camId, { reference_points: defaultPoints })
      setCalibSaved(true)
      await loadCalibration(camId)
      setTimeout(() => setCalibSaved(false), 3000)
    } catch (err: any) {
      alert('Calibration calculation failed')
    } finally {
      setCalibrating(false)
    }
  }

  const activeMode = MODES.find((m) => m.id === selectedModeId) || MODES[3]
  const displayHeight = naturalSize && naturalSize.width ? displayWidth * (naturalSize.height / naturalSize.width) : 480
  const pendingCount = suggestions.filter((s) => s.status === 'PENDING').length
  const approvedCount = suggestions.filter((s) => s.status === 'APPROVED').length

  return (
    <div className="camera-setup-page" style={{ padding: '1.25rem 0' }}>
      {/* ══════════════════════════════════════════════════════════════════════
          HERO HEADER & TELEMETRY
      ══════════════════════════════════════════════════════════════════════ */}
      <div style={{ marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
              <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, color: 'var(--text, #0f172a)' }}>
                AI Floor Plan & Vision Sync
              </h1>
              {activeMode.is_demo && (
                <span className="vision-header-badge demo-source-badge">
                  <span>🧪</span> DEMO SOURCE
                </span>
              )}
            </div>
            <p className="muted" style={{ margin: '0.3rem 0 0', fontSize: '0.85rem' }}>
              Vision-Assisted Dynamic Floor Plan Reconstruction and Table-State Synchronization
            </p>
          </div>

          {/* Telemetry Pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
            <div style={{ background: 'var(--surface-2, #f1f5f9)', padding: '0.35rem 0.75rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 600, border: '1px solid var(--border)' }}>
              Model: <strong style={{ color: '#2563eb' }}>{telemetry?.model_name || 'YOLO11'}</strong>
            </div>
            <div style={{ background: 'var(--surface-2, #f1f5f9)', padding: '0.35rem 0.75rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 600, border: '1px solid var(--border)' }}>
              Inference: <strong style={{ color: '#16a34a' }}>{telemetry?.ai_fps?.toFixed(1) || '15.0'} FPS</strong>
            </div>
            <div style={{ background: 'var(--surface-2, #f1f5f9)', padding: '0.35rem 0.75rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 600, border: '1px solid var(--border)' }}>
              Tracker: <strong style={{ color: '#0891b2' }}>{telemetry?.tracker || 'BYTETRACK'}</strong>
            </div>
            <div style={{ background: (telemetry?.camera_health?.OFFLINE ?? 0) > 0 ? '#fee2e2' : '#dcfce7', color: (telemetry?.camera_health?.OFFLINE ?? 0) > 0 ? '#dc2626' : '#15803d', padding: '0.35rem 0.75rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 700, border: '1px solid currentColor' }}>
              ● {(telemetry?.camera_health?.OFFLINE ?? 0) > 0 ? `${telemetry.camera_health.OFFLINE} OFFLINE` : 'CAM ONLINE'}
            </div>
            {mismatches.length > 0 && (
              <div style={{ background: '#fee2e2', color: '#dc2626', padding: '0.35rem 0.75rem', borderRadius: '8px', fontSize: '0.78rem', fontWeight: 700, border: '1px solid #fca5a5' }}>
                🚨 {mismatches.length} Mismatches
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          COMPACT VIDEO INPUT CONTROLS & EXPANDABLE SETTINGS (TOP RIGHT BUTTON)
      ══════════════════════════════════════════════════════════════════════ */}
      <div
        style={{
          background: 'var(--bg-elevated, #ffffff)',
          border: '1px solid var(--border, #e2e8f0)',
          borderRadius: '12px',
          padding: showSourceSettings ? '1.25rem' : '0.75rem 1.25rem',
          marginBottom: '1.25rem',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
          transition: 'all 0.25s ease',
        }}
      >
        {/* Compact Summary Header Bar */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
              <span style={{ fontSize: '1.3rem' }}>🎥</span>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <strong style={{ fontSize: '0.92rem', color: '#0f172a' }}>
                    {activeMode.label}
                  </strong>
                  <span
                    style={{
                      fontSize: '0.7rem',
                      background: sourceTestResult?.success ? '#dcfce7' : '#e0f2fe',
                      color: sourceTestResult?.success ? '#166534' : '#0369a1',
                      padding: '2px 8px',
                      borderRadius: '4px',
                      fontWeight: 700,
                    }}
                  >
                    ● {sourceTestResult?.status || 'CONFIGURED'}
                  </span>
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', maxWidth: '460px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  Stream Source: <code style={{ fontSize: '0.72rem' }}>{cameraUrl || activeMode.default_url}</code>
                </div>
              </div>
            </div>

            {sourceTestResult && (
              <div style={{ fontSize: '0.75rem', display: 'flex', gap: '0.6rem', alignItems: 'center', background: 'var(--surface-2)', padding: '0.25rem 0.65rem', borderRadius: '6px', border: '1px solid var(--border)' }}>
                <span>Res: {sourceTestResult.resolution || '1280x720'}</span>
                <span>FPS: {sourceTestResult.fps || 24}</span>
                <span>Latency: {sourceTestResult.latency_ms || 42}ms</span>
              </div>
            )}
          </div>

          {/* Right Corner Action Controls & Settings Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            {!showSourceSettings && (
              <>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={handleTestSource}
                  disabled={testingSource}
                  style={{ fontSize: '0.78rem', padding: '0.4rem 0.75rem' }}
                >
                  {testingSource ? 'Testing…' : '🔍 Test Link'}
                </button>

                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={handleTriggerFloorPlanDetection}
                  disabled={aiDetecting}
                  style={{
                    fontSize: '0.8rem',
                    padding: '0.4rem 0.95rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.35rem',
                    fontWeight: 700,
                  }}
                >
                  {aiDetecting ? 'Analyzing…' : '✨ Re-Detect Layout'}
                </button>
              </>
            )}

            {/* The Settings Toggle Button in Right Corner */}
            <button
              type="button"
              onClick={() => setShowSourceSettings((prev) => !prev)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.45rem',
                fontSize: '0.84rem',
                fontWeight: 700,
                padding: '0.45rem 1.05rem',
                borderRadius: '8px',
                cursor: 'pointer',
                background: showSourceSettings ? '#f1f5f9' : 'linear-gradient(135deg, #1e293b, #0f172a)',
                color: showSourceSettings ? '#0f172a' : '#ffffff',
                border: showSourceSettings ? '1.5px solid #cbd5e1' : 'none',
                boxShadow: showSourceSettings ? 'none' : '0 2px 6px rgba(15, 23, 42, 0.25)',
              }}
            >
              <span>⚙️</span>
              <span>{showSourceSettings ? 'Close Settings ✕' : 'Video Source Settings'}</span>
              <span style={{ fontSize: '0.72rem', opacity: 0.8 }}>{showSourceSettings ? '▲' : '▼'}</span>
            </button>
          </div>
        </div>

        {/* Expandable Settings Full Body */}
        {showSourceSettings && (
          <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
              <div>
                <strong style={{ fontSize: '0.92rem', textTransform: 'uppercase', letterSpacing: '0.04em', color: 'var(--text-muted, #64748b)' }}>
                  Select Video Input Mode & State
                </strong>
                <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.78rem' }}>
                  Choose a physical camera or offline demo mode to connect to the computer vision pipeline.
                </p>
              </div>

              {sourceTestResult && (
                <div style={{ fontSize: '0.8rem', display: 'flex', gap: '0.75rem', alignItems: 'center', background: 'var(--surface-2)', padding: '0.35rem 0.75rem', borderRadius: '8px', border: '1px solid var(--border)' }}>
                  <span style={{ color: sourceTestResult.success ? '#16a34a' : '#dc2626', fontWeight: 700 }}>
                    ● {sourceTestResult.status}
                  </span>
                  <span>Res: {sourceTestResult.resolution || '1280x720'}</span>
                  <span>FPS: {sourceTestResult.fps || 24}</span>
                  <span>Latency: {sourceTestResult.latency_ms || 42}ms</span>
                </div>
              )}
            </div>

        {/* 6 Explicit Mode Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
          {MODES.map((mode) => {
            const isSelected = selectedModeId === mode.id
            let statusPill = <span className="mode-status-pill mode-status-pill--standby">STANDBY</span>
            if (mode.id === 'SYNTHETIC') {
              statusPill = <span className="mode-status-pill mode-status-pill--online">● SIMULATION READY</span>
            } else if (mode.id === 'VIDEO_FILE') {
              statusPill = <span className="mode-status-pill mode-status-pill--online">● READY ({availableClips.length || 1} CLIPS)</span>
            } else if (mode.id === 'WEBCAM') {
              statusPill = <span className="mode-status-pill mode-status-pill--online">● READY (CAM 0, 1)</span>
            } else if (mode.id === 'DEMO_STREAM') {
              statusPill = <span className="mode-status-pill mode-status-pill--demo">🧪 DEMO READY</span>
            } else if (isSelected && sourceTestResult?.success) {
              statusPill = <span className="mode-status-pill mode-status-pill--online">● ONLINE</span>
            } else if (isSelected) {
              statusPill = <span className="mode-status-pill mode-status-pill--online">● SELECTED</span>
            }

            return (
              <div
                key={mode.id}
                className={`mode-card ${isSelected ? 'mode-card--active' : ''}`}
                onClick={() => handleSelectMode(mode)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem' }}>
                  <strong style={{ fontSize: '0.88rem', color: isSelected ? '#1d4ed8' : 'var(--text)' }}>
                    {mode.label}
                  </strong>
                  {statusPill}
                </div>
                <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--text-muted)', lineHeight: 1.35 }}>
                  {mode.description}
                </p>
              </div>
            )
          })}
        </div>

        {/* Selected Mode Configuration & Instant Analysis Action */}
        <div style={{ background: 'var(--surface-2, #f8fafc)', border: '1px solid var(--border)', borderRadius: '10px', padding: '1rem', marginTop: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.65rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 700, color: '#1e293b' }}>
              Active Configuration: {activeMode.label}
            </span>
            <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
              Example Link: <code>{activeMode.example}</code>
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.65rem', alignItems: 'center', flexWrap: 'wrap' }}>
            {selectedModeId === 'VIDEO_FILE' ? (
              <div style={{ display: 'flex', gap: '0.5rem', flex: 1, minWidth: '280px' }}>
                <select
                  id="camera-video-file-select"
                  name="videoFile"
                  aria-label="Select Video Clip"
                  className="input"
                  style={{ flex: 1, padding: '0.45rem 0.75rem', fontSize: '0.85rem' }}
                  value={cameraUrl}
                  onChange={(e) => setCameraUrl(e.target.value)}
                >
                  {availableClips.map((clip) => (
                    <option key={clip} value={clip}>
                      📁 {clip}
                    </option>
                  ))}
                </select>
                <input
                  id="camera-video-file-input"
                  name="videoFileInput"
                  aria-label="Upload Video Clip"
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                >
                  {uploading ? 'Uploading…' : '⬆ Upload New Clip'}
                </button>
              </div>
            ) : selectedModeId === 'WEBCAM' ? (
              <select
                id="camera-webcam-device-select"
                name="webcamDevice"
                aria-label="Select Webcam Device"
                className="input"
                style={{ flex: 1, minWidth: '240px', padding: '0.45rem 0.75rem', fontSize: '0.85rem' }}
                value={cameraUrl}
                onChange={(e) => setCameraUrl(e.target.value)}
              >
                <option value="0">Camera 0 (Default Integrated Webcam)</option>
                <option value="1">Camera 1 (External USB Device)</option>
                <option value="2">Camera 2 (Secondary Angle)</option>
              </select>
            ) : selectedModeId === 'SYNTHETIC' ? (
              <input
                id="camera-synthetic-url"
                name="syntheticUrl"
                aria-label="Synthetic Camera URL"
                className="input"
                style={{ flex: 1, minWidth: '240px', padding: '0.45rem 0.75rem', fontSize: '0.85rem', background: '#e2e8f0' }}
                value="synthetic://dining-room-simulation"
                disabled
              />
            ) : (
              <input
                id="camera-source-url"
                name="cameraUrl"
                aria-label="Camera Stream URL"
                className="input"
                style={{ flex: 1, minWidth: '260px', padding: '0.45rem 0.75rem', fontSize: '0.85rem' }}
                placeholder={activeMode.default_url}
                value={cameraUrl}
                onChange={(e) => {
                  const val = e.target.value
                  setCameraUrl(val)
                  setSourceErrorWarning(null)
                  localStorage.setItem('foh_camera_url', val.trim())
                }}
                onBlur={() => {
                  if (cameraUrl.trim()) {
                    void handleAutoPersistUrl(cameraUrl.trim(), selectedModeId)
                  }
                }}
              />
            )}

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleTestSource}
              disabled={testingSource}
            >
              {testingSource ? 'Testing…' : '🔍 Test Link'}
            </button>

            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleSaveCameraUrl}
              disabled={savingUrl}
            >
              {savingUrl ? 'Saving…' : 'Save Source'}
            </button>

            {/* Reconstruct vs Synchronize Switch */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', background: reconstructMode ? '#eff6ff' : 'var(--surface-2)', border: reconstructMode ? '1.5px solid #3b82f6' : '1px solid var(--border)', borderRadius: '8px', padding: '0.35rem 0.65rem' }}>
              <input
                id="reconstructToggle"
                name="reconstructToggle"
                aria-label="Wipe old floor plan & build clean from video"
                type="checkbox"
                checked={reconstructMode}
                onChange={(e) => setReconstructMode(e.target.checked)}
                style={{ cursor: 'pointer' }}
              />
              <label htmlFor="reconstructToggle" style={{ fontSize: '0.78rem', fontWeight: 700, color: reconstructMode ? '#1e40af' : 'var(--text)', cursor: 'pointer', userSelect: 'none' }}>
                Wipe old floor plan & build clean from video
              </label>
            </div>

            {/* Direct Instant Action to Reconstruct Floor Plan from Video */}
            <button
              type="button"
              className="btn btn-primary"
              onClick={handleDirectReconstruct}
              disabled={reconstructing || aiDetecting}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.55rem 1.25rem',
                fontWeight: 800,
                background: 'linear-gradient(135deg, #16a34a, #15803d)',
                border: 'none',
                color: '#ffffff',
                boxShadow: '0 2px 8px rgba(22, 163, 74, 0.35)',
                cursor: 'pointer',
              }}
            >
              {reconstructing ? 'Reconstructing from Video…' : '⚡ Reconstruct Floor Plan from Video'}
            </button>

            {/* Analyze & Propose for Review */}
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleTriggerFloorPlanDetection}
              disabled={aiDetecting || reconstructing}
              style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', padding: '0.5rem 0.9rem', fontWeight: 600 }}
            >
              {aiDetecting ? 'Analyzing Frames…' : '🔍 Scan & Review Tables'}
            </button>

            {urlSaved && <span style={{ color: '#16a34a', fontSize: '0.82rem', fontWeight: 700 }}>✓ Saved</span>}
          </div>

          {/* Quick presets for active mode */}
          <div style={{ marginTop: '0.65rem', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', fontSize: '0.78rem' }}>
            <span style={{ color: 'var(--text-muted)', fontWeight: 600 }}>Quick Presets / Links:</span>
            {selectedModeId === 'RTSP' && (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                  onClick={() => setCameraUrl('rtsp://admin:Password123@192.168.1.100:554/stream')}
                >
                  🔗 rtsp://192.168.1.100 (Default CCTV)
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                  onClick={() => setCameraUrl('rtsp://viewer:guest@10.0.0.50:554/h264')}
                >
                  🔗 rtsp://10.0.0.50 (Alternate Angle)
                </button>
              </>
            )}
            {selectedModeId === 'ONVIF' && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                onClick={() => setCameraUrl('http://192.168.1.120:80/onvif/device_service')}
              >
                🔗 http://192.168.1.120:80/onvif
              </button>
            )}
            {selectedModeId === 'WEBCAM' && (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl === '0' ? 700 : 400 }}
                  onClick={() => setCameraUrl('0')}
                >
                  📷 Camera 0 (Laptop Integrated)
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl === '1' ? 700 : 400 }}
                  onClick={() => setCameraUrl('1')}
                >
                  📷 Camera 1 (External USB)
                </button>
              </>
            )}
            {selectedModeId === 'VIDEO_FILE' && (
              availableClips.map((clip) => (
                <button
                  key={clip}
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl === clip ? 700 : 400 }}
                  onClick={() => setCameraUrl(clip)}
                >
                  🎬 {clip}
                </button>
              ))
            )}
            {selectedModeId === 'DEMO_STREAM' && (
              <>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl.includes('Sgt05K7f9TA') ? 700 : 400 }}
                  onClick={() => applyPresetUrl('https://www.youtube.com/live/Sgt05K7f9TA?si=7m6ACIFo1r0vuW9x', 'DEMO_STREAM')}
                >
                  🔴 YouTube: Live Dining Stream
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl.includes('DBl7MmHlQK0') ? 700 : 400 }}
                  onClick={() => applyPresetUrl('https://www.youtube.com/watch?v=DBl7MmHlQK0', 'DEMO_STREAM')}
                >
                  ▶️ YouTube: Restaurant CCTV Feed
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl === 'table_t-1.mp4' ? 700 : 400 }}
                  onClick={() => applyPresetUrl('table_t-1.mp4', 'VIDEO_FILE')}
                >
                  🎬 Sample MP4 (table_t-1.mp4)
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', fontWeight: cameraUrl === 'synthetic' ? 700 : 400 }}
                  onClick={() => applyPresetUrl('synthetic', 'SYNTHETIC')}
                >
                  🎮 Synthetic Simulation
                </button>
              </>
            )}
            {selectedModeId === 'SYNTHETIC' && (
              <span style={{ color: '#16a34a', fontWeight: 600 }}>
                ✓ Synthetic procedural dining room with 4 physical tables (T1 square, T2 round, T3 rectangle, T4 square) + patrons
              </span>
            )}
          </div>

          {/* Warning notice if external stream fails */}
          {sourceErrorWarning && (
            <div style={{ marginTop: '0.75rem', background: '#fffbeb', border: '1px solid #fcd34d', borderRadius: '8px', padding: '0.65rem 0.9rem', fontSize: '0.82rem', color: '#92400e', display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <span>⚠️</span>
              <div>
                <strong>Stream Notice:</strong> {sourceErrorWarning}
              </div>
            </div>
          )}
        </div>
      </div>
    )}
  </div>

      {/* ══════════════════════════════════════════════════════════════════════
          TABS NAVIGATION
      ══════════════════════════════════════════════════════════════════════ */}
      <div style={{ display: 'flex', gap: '0.4rem', borderBottom: '1px solid var(--border)', marginBottom: '1.25rem', overflowX: 'auto' }}>
        {[
          { id: 'ai_floor_plan', label: '✨ AI Floor Plan Discovery & Review', badge: pendingCount > 0 ? pendingCount : null },
          { id: 'stream', label: '🎥 Live Vision Stream & Occupancy' },
          { id: 'rois', label: '🎯 Table ROI Zoning Studio' },
          { id: 'calibration', label: '📐 Camera Calibration' },
          { id: 'mismatches', label: '🚨 CCTV ↔ FOH Mismatches', badge: mismatches.length > 0 ? mismatches.length : null },
          { id: 'benchmark', label: '🧠 AI Model Hub & Registry' },
        ].map((tab) => {
          const active = activeTab === tab.id
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              style={{
                padding: '0.65rem 1.1rem',
                border: 'none',
                background: 'transparent',
                borderBottom: `2.5px solid ${active ? '#3b82f6' : 'transparent'}`,
                color: active ? '#2563eb' : 'var(--text-muted)',
                fontWeight: active ? 700 : 500,
                fontSize: '0.88rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.4rem',
                whiteSpace: 'nowrap',
              }}
            >
              <span>{tab.label}</span>
              {tab.badge !== null && tab.badge !== undefined && (
                <span style={{ background: '#dc2626', color: '#ffffff', fontSize: '0.72rem', padding: '0.1rem 0.45rem', borderRadius: '99px', fontWeight: 700 }}>
                  {tab.badge}
                </span>
              )}
            </button>
          )
        })}
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 1: AI FLOOR PLAN DISCOVERY, SPLIT-SCREEN & TABLE CREATION
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'ai_floor_plan' && (
        <div>
          {/* Action Header Banner */}
          <div style={{ background: 'var(--bg-elevated, #ffffff)', border: '1px solid var(--border, #e2e8f0)', borderRadius: '12px', padding: '1.25rem', marginBottom: '1.25rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>
                  AI Table Layout Discovery & Dynamic Digital Twin
                </h3>
                <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.82rem' }}>
                  YOLO11 + OpenCV Tabletop contour detection maps physical candidate tables into digital floor coordinates via homography perspective calibration.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleTriggerFloorPlanDetection}
                  disabled={aiDetecting}
                  style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 1.1rem' }}
                >
                  {aiDetecting ? 'Analyzing Frames…' : '✨ Re-Detect Layout'}
                </button>

                {approvedCount > 0 && (
                  <button
                    type="button"
                    className="btn btn-success"
                    onClick={handleApplyApprovedChanges}
                    disabled={applyingApproved}
                    style={{ background: '#16a34a', color: '#ffffff', border: 'none', borderRadius: '8px', padding: '0.55rem 1.1rem', fontWeight: 700, cursor: 'pointer' }}
                  >
                    {applyingApproved ? 'Applying Updates…' : `⚡ Apply Approved Tables (${approvedCount})`}
                  </button>
                )}
              </div>
            </div>

            {applyResultBanner && (
              <div style={{ marginTop: '1rem', background: '#dcfce7', border: '1px solid #86efac', borderRadius: '8px', padding: '0.75rem 1rem', color: '#166534', fontWeight: 600, fontSize: '0.88rem' }}>
                {applyResultBanner}
              </div>
            )}

            {/* Summary Counters */}
            {aiReport && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                <div style={{ background: 'var(--surface-2)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem' }}>
                  Existing Tables: <strong>{aiReport.existing_tables_count}</strong>
                </div>
                <div style={{ background: 'var(--surface-2)', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem' }}>
                  Candidate Detections: <strong>{aiReport.detected_candidates_count}</strong>
                </div>
                <div style={{ background: '#dcfce7', color: '#166534', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 700 }}>
                  ✓ Matched: {aiReport.matched_count}
                </div>
                <div style={{ background: '#fee2e2', color: '#991b1b', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 700 }}>
                  ⚠ Positional Drift: {aiReport.position_drift_count}
                </div>
                <div style={{ background: '#dbeafe', color: '#1e40af', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 700 }}>
                  + Possible New Tables: {aiReport.new_table_count}
                </div>
                <div style={{ background: '#fef3c7', color: '#92400e', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem', fontWeight: 700 }}>
                  ⤢ Size Changes: {aiReport.size_change_count}
                </div>
                {aiReport.uncertain_count > 0 && (
                  <div style={{ background: '#f3f4f6', color: '#4b5563', padding: '0.4rem 0.8rem', borderRadius: '8px', fontSize: '0.82rem' }}>
                    ? Uncertain: {aiReport.uncertain_count}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Split Screen Review View */}
          <div className="ai-split-screen">
            {/* Left Column: Live Camera Detection Stream */}
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                <strong style={{ fontSize: '0.9rem', color: 'var(--text)' }}>
                  📹 Live Camera Feed & Candidate Detection
                </strong>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Source: {activeMode.label}
                </span>
              </div>

              {floor ? (
                <LiveStreamPlayer
                  floorId={floor.id}
                  cameraId={selectedCameraId}
                  cameraUrl={cameraUrl}
                  sourceType={selectedModeId}
                  modeLabel={activeMode.label}
                  minHeight={380}
                  showLegend={true}
                />
              ) : (
                <div style={{ height: '360px', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--surface-2)', borderRadius: '10px' }}>
                  No Floor Selected
                </div>
              )}
            </div>

            {/* Right Column: Digital Floor Plan with Comparison Modes */}
            <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                  <strong style={{ fontSize: '0.9rem', color: 'var(--text)' }}>
                    🗺 Digital Twin Floor Plan
                  </strong>
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    onClick={handleClearFloorPlan}
                    disabled={clearingFloor}
                    style={{ fontSize: '0.74rem', color: '#dc2626', border: '1px solid #fca5a5', padding: '0.2rem 0.55rem', borderRadius: '6px', fontWeight: 600, cursor: 'pointer' }}
                    title="Remove all old tables to start fresh"
                  >
                    {clearingFloor ? 'Clearing…' : '🧹 Clear Old Layout'}
                  </button>
                </div>

                {/* View Mode Switcher */}
                <div className="mode-toggle-group">
                  <button
                    type="button"
                    className={`mode-toggle-btn ${floorPlanViewMode === 'current' ? 'active' : ''}`}
                    onClick={() => setFloorPlanViewMode('current')}
                  >
                    Current Layout
                  </button>
                  <button
                    type="button"
                    className={`mode-toggle-btn ${floorPlanViewMode === 'ai_suggested' ? 'active' : ''}`}
                    onClick={() => setFloorPlanViewMode('ai_suggested')}
                  >
                    AI Suggested
                  </button>
                  <button
                    type="button"
                    className={`mode-toggle-btn ${floorPlanViewMode === 'overlay' ? 'active' : ''}`}
                    onClick={() => setFloorPlanViewMode('overlay')}
                  >
                    Overlay Comparison
                  </button>
                </div>
              </div>

              {floor && (
                <div style={{ background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '10px', padding: '0.85rem', position: 'relative' }}>
                  <DigitalFloorPlanView
                    floor={floor}
                    suggestions={suggestions}
                    viewMode={floorPlanViewMode}
                    selectedTableId={selectedTableId}
                    selectedSuggestionId={selectedSuggestionId}
                    onSelectTable={(id) => setSelectedTableId(id)}
                    onSelectSuggestion={(id) => {
                      setSelectedSuggestionId(id)
                      const s = suggestions.find((x) => x.id === id)
                      if (s?.existing_table_id) setSelectedTableId(s.existing_table_id)
                    }}
                    onApproveSuggestion={(id) => handleSuggestionAction(id, 'APPROVE')}
                    onRejectSuggestion={(id) => handleSuggestionAction(id, 'REJECT')}
                    onIgnoreSuggestion={(id) => handleSuggestionAction(id, 'IGNORE')}
                    onMakeSingleTable={(id) => handleMakeSingleTable(id)}
                    onApproveAll={handleApproveAllSuggestions}
                    onMakeAllTables={(replaceOld) => handleMakeAllTables(replaceOld ?? true)}
                    isApplying={applyingApproved}
                  />
                </div>
              )}
            </div>
          </div>

          {/* AI Suggestions Detailed Review Feed (Collapsible) */}
          <div style={{ marginTop: '1.5rem', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '12px', padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: showDetailedQueue ? '1rem' : 0, flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span>📋 Detailed Table Review Queue ({suggestions.length} Items)</span>
                  <span style={{ fontSize: '0.72rem', background: '#dcfce7', color: '#166534', padding: '2px 8px', borderRadius: '6px', fontWeight: 700 }}>
                    {approvedCount} Approved
                  </span>
                  <span style={{ fontSize: '0.72rem', background: '#fef3c7', color: '#92400e', padding: '2px 8px', borderRadius: '6px', fontWeight: 700 }}>
                    {pendingCount} Pending
                  </span>
                </h3>
                <span className="muted" style={{ fontSize: '0.8rem' }}>
                  Tip: You can now review, approve, deny, and commit all tables directly on the Digital Twin canvas above!
                </span>
              </div>

              {suggestions.length > 0 && (
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    onClick={() => setShowDetailedQueue((prev) => !prev)}
                    style={{ fontSize: '0.8rem', padding: '0.4rem 0.85rem', fontWeight: 600 }}
                  >
                    {showDetailedQueue ? '▲ Hide Table Cards' : '▼ Expand Detailed Cards'}
                  </button>
                </div>
              )}
            </div>

            {showDetailedQueue && suggestions.length === 0 ? (
              <div style={{ padding: '2.5rem', textAlign: 'center', background: 'var(--bg-elevated)', border: '1px dashed var(--border)', borderRadius: '12px', color: 'var(--text-muted)' }}>
                Select a video mode above and click <strong>"⚡ Analyze Source & Perform Table Detection"</strong> to automatically discover and map tables.
              </div>
            ) : showDetailedQueue && (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))', gap: '1rem' }}>
                {suggestions.map((s) => {
                  let cardClass = 'ai-candidate-card--matched'
                  if (s.suggestion_type === 'POSITION_CHANGE') cardClass = 'ai-candidate-card--drift'
                  else if (s.suggestion_type === 'NEW_TABLE') cardClass = 'ai-candidate-card--new'
                  else if (s.suggestion_type === 'SIZE_CHANGE') cardClass = 'ai-candidate-card--size'
                  else if (s.suggestion_type === 'UNCERTAIN') cardClass = 'ai-candidate-card--uncertain'

                  const isSelected = selectedSuggestionId === s.id

                  return (
                    <div
                      key={s.id}
                      id={`suggestion-card-${s.id}`}
                      className={`ai-candidate-card ${cardClass}`}
                      onClick={() => {
                        setSelectedSuggestionId(s.id)
                        if (s.existing_table_id) setSelectedTableId(s.existing_table_id)
                      }}
                      style={{
                        cursor: 'pointer',
                        outline: isSelected ? '2px solid #2563eb' : undefined,
                        boxShadow: isSelected ? '0 0 0 4px rgba(37, 99, 235, 0.2)' : undefined,
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                        <div>
                          <strong style={{ fontSize: '0.95rem' }}>
                            {s.existing_table ? `Table ${s.existing_table.label}` : s.suggested_label || 'New Table Candidate'}
                          </strong>
                          <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                            Shape: <strong>{s.detected_position?.shape || 'UNKNOWN'}</strong> ({Math.round((s.detected_position?.shape_confidence || 0.85) * 100)}% Conf)
                            {' • '}
                            Pos: ({s.detected_position?.x}, {s.detected_position?.y})
                          </div>
                        </div>

                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: 700,
                            padding: '0.15rem 0.5rem',
                            borderRadius: '99px',
                            background:
                              s.status === 'APPROVED' ? '#dcfce7' : s.status === 'REJECTED' ? '#fee2e2' : s.status === 'APPLIED' ? '#e0e7ff' : '#fef3c7',
                            color:
                              s.status === 'APPROVED' ? '#166534' : s.status === 'REJECTED' ? '#991b1b' : s.status === 'APPLIED' ? '#3730a3' : '#92400e',
                          }}
                        >
                          {s.status}
                        </span>
                      </div>

                      <p style={{ margin: '0.4rem 0 0.75rem', fontSize: '0.82rem', color: 'var(--text, #334155)', lineHeight: 1.4 }}>
                        {s.suggestion_type === 'POSITION_CHANGE' && (
                          <span>
                            📍 Physical furniture appears <strong>{s.drift_distance || 32}px away</strong> from digital coordinates. Recommend adjusting floor plan position.
                          </span>
                        )}
                        {s.suggestion_type === 'NEW_TABLE' && (
                          <span>
                            ✨ Unregistered physical table detected at coordinates ({s.detected_position?.x}, {s.detected_position?.y}). Recommend adding to floor plan.
                          </span>
                        )}
                        {s.suggestion_type === 'SIZE_CHANGE' && (
                          <span>
                            ⤢ Table dimensions appear altered compared to recorded capacity.
                          </span>
                        )}
                        {s.suggestion_type === 'UNCERTAIN' && (
                          <span>
                            ❓ Vision detection confidence is moderate ({Math.round(s.confidence * 100)}%). Manual verification advised.
                          </span>
                        )}
                        {s.suggestion_type === 'REMOVED_TABLE' && (
                          <span>
                            ⚠️ Table absent from camera frame. Possible removal or camera blind spot.
                          </span>
                        )}
                      </p>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.65rem', borderTop: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                          <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                            Confidence:{' '}
                            <strong style={{ color: s.confidence >= 0.80 ? '#16a34a' : s.confidence >= 0.55 ? '#ca8a04' : '#dc2626' }}>
                              {Math.round(s.confidence * 100)}%
                            </strong>
                          </span>
                          {s.detected_position?.perspective_zone && (
                            <span style={{ fontSize: '0.68rem', background: 'var(--surface-2, #f1f5f9)', color: 'var(--text)', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 700 }}>
                              {s.detected_position.perspective_zone} ZONE
                            </span>
                          )}
                          {s.detected_position?.confidence_tier && (
                            <span style={{ fontSize: '0.68rem', background: s.detected_position.confidence_tier === 'HIGH' ? '#dcfce7' : s.detected_position.confidence_tier === 'MEDIUM' ? '#fef3c7' : '#fee2e2', color: s.detected_position.confidence_tier === 'HIGH' ? '#166534' : s.detected_position.confidence_tier === 'MEDIUM' ? '#92400e' : '#991b1b', padding: '0.1rem 0.4rem', borderRadius: '4px', fontWeight: 700 }}>
                              {s.detected_position.confidence_tier}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center' }}>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => handleMakeSingleTable(s.id)}
                            disabled={applyingApproved || s.status === 'APPLIED'}
                            style={{
                              background: s.status === 'APPLIED' ? '#94a3b8' : '#2563eb',
                              color: '#ffffff',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '0.25rem 0.65rem',
                              fontSize: '0.78rem',
                              fontWeight: 700,
                              cursor: s.status === 'APPLIED' ? 'default' : 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.25rem',
                            }}
                          >
                            {s.status === 'APPLIED' ? '✓ In Floor Plan' : '➕ Make Table'}
                          </button>

                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => handleSuggestionAction(s.id, 'APPROVE')}
                            style={{
                              background: s.status === 'APPROVED' ? '#16a34a' : 'var(--surface-2)',
                              color: s.status === 'APPROVED' ? '#ffffff' : 'var(--text)',
                              border: '1px solid var(--border)',
                              borderRadius: '6px',
                              padding: '0.25rem 0.6rem',
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            ✓ Approve
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => handleSuggestionAction(s.id, 'REJECT')}
                            style={{
                              background: s.status === 'REJECTED' ? '#dc2626' : 'var(--surface-2)',
                              color: s.status === 'REJECTED' ? '#ffffff' : 'var(--text)',
                              border: '1px solid var(--border)',
                              borderRadius: '6px',
                              padding: '0.25rem 0.6rem',
                              fontSize: '0.78rem',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            ✕ Reject
                          </button>
                          <button
                            type="button"
                            className="btn btn-sm"
                            onClick={() => handleSuggestionAction(s.id, 'IGNORE')}
                            style={{
                              background: 'transparent',
                              color: 'var(--text-muted)',
                              border: 'none',
                              padding: '0.25rem 0.5rem',
                              fontSize: '0.78rem',
                              cursor: 'pointer',
                            }}
                          >
                            Ignore
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 2: LIVE VISION STREAM & OVERLAYS
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
                <LiveStreamPlayer
                  floorId={floor.id}
                  cameraId={selectedCameraId}
                  cameraUrl={cameraUrl}
                  sourceType={selectedModeId}
                  modeLabel={activeMode.label}
                  minHeight={440}
                  showLegend={true}
                />
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
          TAB 3: TABLE ROI ZONING STUDIO
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
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
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

              {snapshotError && <p style={{ color: '#dc2626', fontSize: '0.85rem', marginBottom: '0.75rem' }}>⚠️ {snapshotError}</p>}

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
          TAB 4: CAMERA PERSPECTIVE CALIBRATION WIZARD
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'calibration' && (
        <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h3 style={{ margin: 0 }}>Camera Homography & Perspective Calibration</h3>
              <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                Maps camera pixel coordinates (X_cam, Y_cam) to digital floor plan coordinates (X_floor, Y_floor) via 3x3 perspective transformation matrix.
              </p>
            </div>
            {cameraCalibration && (
              <span style={{ background: '#dcfce7', color: '#166534', padding: '0.35rem 0.75rem', borderRadius: '8px', fontWeight: 700, fontSize: '0.82rem' }}>
                ✓ Camera Status: CALIBRATED
              </span>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            {[
              { name: 'Corner 1 (Top-Left)', cam: '(100, 100)', floor: '(50, 50)' },
              { name: 'Corner 2 (Top-Right)', cam: '(1180, 100)', floor: '(950, 50)' },
              { name: 'Corner 3 (Bottom-Right)', cam: '(1180, 620)', floor: '(950, 650)' },
              { name: 'Corner 4 (Bottom-Left)', cam: '(100, 620)', floor: '(50, 650)' },
            ].map((p, i) => (
              <div key={i} style={{ padding: '0.9rem', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <strong style={{ fontSize: '0.85rem', display: 'block', marginBottom: '0.3rem' }}>{p.name}</strong>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Camera: {p.cam}</div>
                <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>Floor: {p.floor}</div>
                <div style={{ marginTop: '0.5rem', fontSize: '0.82rem', fontWeight: 700, color: '#16a34a' }}>
                  ✓ Reference Pair Ready
                </div>
              </div>
            ))}
          </div>

          <button className="btn btn-primary" onClick={handleSaveCalibration} disabled={calibrating}>
            {calibrating ? 'Computing Homography…' : '✓ Run & Save Homography Matrix'}
          </button>
          {calibSaved && <span style={{ color: '#16a34a', fontWeight: 700, marginLeft: '1rem', fontSize: '0.88rem' }}>✓ Calibration Saved & Stored in Database!</span>}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 5: CCTV ↔ FOH MISMATCHES & DEPARTURE MONITORING
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'mismatches' && (
        <div>
          <div style={{ marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700 }}>
                Continuous Occupancy & State Discrepancy Verification
              </h3>
              <p className="muted" style={{ margin: '0.2rem 0 0', fontSize: '0.82rem' }}>
                Business Authority Rule: Digital FOH is authority. Vision observations surface discrepancies for human verification without blindly altering financial states.
              </p>
            </div>
            <button className="btn btn-ghost btn-sm" onClick={loadMismatches}>
              ↻ Refresh
            </button>
          </div>

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
                const isWalkout = m.mismatch_type.includes('WALKOUT') || m.mismatch_type.includes('UNPAID')
                return (
                  <div
                    key={m.id}
                    style={{
                      background: 'var(--bg-elevated)',
                      border: `1.5px solid ${isWalkout ? '#f87171' : '#fca5a5'}`,
                      borderRadius: '12px',
                      padding: '1.25rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      boxShadow: '0 4px 12px rgba(220, 38, 38, 0.06)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <span style={{ fontSize: '2rem' }}>{isWalkout ? '🛑' : '⚠️'}</span>
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.25rem' }}>
                          <strong style={{ fontSize: '1.05rem' }}>Table {m.table_number}</strong>
                          <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.15rem 0.55rem', borderRadius: '99px', background: '#fee2e2', color: '#dc2626' }}>
                            {m.mismatch_type.replace(/_/g, ' ')}
                          </span>
                        </div>

                        <p className="muted" style={{ margin: 0, fontSize: '0.84rem' }}>
                          Digital Status: <strong>{m.digital_status}</strong> · CCTV Observation:{' '}
                          <strong style={{ color: '#dc2626' }}>{m.detected_people} Person(s) ({Math.round(m.confidence * 100)}% Conf)</strong>
                        </p>
                      </div>
                    </div>

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

      {/* ══════════════════════════════════════════════════════════════════════
          TAB 6: AI MODEL HUB & PLUGGABLE REGISTRY
      ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === 'benchmark' && (
        <div>
          <VisionModelManagementPanel cameraId={selectedCameraId || 'default'} />

          <div style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: '12px', padding: '1.5rem', marginTop: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Vision Model Comparative Benchmark</h3>
              <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                Measures Precision, Recall, mAP@0.5, FPS, latency, and error rates on available restaurant video clips.
              </p>
            </div>

            <button
              type="button"
              className="btn btn-primary"
              onClick={handleRunBenchmark}
              disabled={benchmarking}
              style={{ padding: '0.5rem 1.1rem' }}
            >
              {benchmarking ? 'Benchmarking Models…' : '🚀 Run Comparative Benchmark'}
            </button>
          </div>

          {benchmarkResult ? (
            <div>
              <div style={{ overflowX: 'auto', marginBottom: '1.5rem' }}>
                <table className="benchmark-table">
                  <thead>
                    <tr>
                      <th>Model Architecture</th>
                      <th>Task Focus</th>
                      <th>Inference Latency</th>
                      <th>Throughput (FPS)</th>
                      <th>Precision</th>
                      <th>Recall</th>
                      <th>mAP @ 0.5</th>
                      <th>False Positives</th>
                      <th>False Negatives</th>
                    </tr>
                  </thead>
                  <tbody>
                    {benchmarkResult.benchmarks?.map((bm: any, idx: number) => (
                      <tr key={idx} style={{ background: idx === 0 ? 'rgba(59, 130, 246, 0.04)' : undefined }}>
                        <td>
                          <strong>{bm.model_name}</strong>
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{bm.weights_path}</div>
                        </td>
                        <td>{bm.task}</td>
                        <td><strong>{bm.metrics?.inference_latency_ms} ms</strong></td>
                        <td><strong style={{ color: '#16a34a' }}>{bm.metrics?.fps} FPS</strong></td>
                        <td>{(bm.metrics?.precision * 100).toFixed(1)}%</td>
                        <td>{(bm.metrics?.recall * 100).toFixed(1)}%</td>
                        <td><strong>{(bm.metrics?.mAP_50 * 100).toFixed(1)}%</strong></td>
                        <td>{bm.metrics?.false_positives}</td>
                        <td>{bm.metrics?.false_negatives}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '1rem', fontSize: '0.85rem' }}>
                <strong>Recommendation:</strong> {benchmarkResult.recommendation}
              </div>
            </div>
          ) : (
            <div style={{ padding: '2.5rem', textAlign: 'center', background: 'var(--surface-2)', borderRadius: '8px', border: '1px dashed var(--border)', color: 'var(--text-muted)' }}>
              Click <strong>"🚀 Run Comparative Benchmark"</strong> to evaluate YOLO11 against the custom table-state model on real restaurant footage.
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  )
}
