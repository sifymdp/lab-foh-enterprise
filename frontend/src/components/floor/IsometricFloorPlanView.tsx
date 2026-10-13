import React, { useMemo, useState } from 'react'
import type { Floor } from '../../types'

interface SpatialAnalysis {
  heat_points?: Array<{
    id: string
    x: number
    y: number
    radius: number
    intensity: number
    label: string
    type: string
  }>
  traffic_flows?: Array<{
    id: string
    name: string
    type: string
    color: string
    points: Array<[number, number]>
  }>
  tracked_people?: Array<{
    id: string
    x: number
    y: number
    role: string
    confidence: number
    activity: string
    table_id?: string
  }>
  cctv_camera?: {
    origin: [number, number]
    target: [number, number]
    fps: number
    coverage_pct: number
  }
}

interface IsometricFloorPlanViewProps {
  floor: Floor
  tables: any[]
  spatialAnalysis?: SpatialAnalysis
  selectedTableId?: string | null
  onSelectTable?: (tableId: string) => void
  onAddTable?: (payload: any) => Promise<any>
  cctvOnline?: boolean
}

// 3D Isometric Screen Coordinate Math: 2D (x, y, z) -> (isoX, isoY)
function toIso(x: number, y: number, z: number = 0, originX: number = 540, originY: number = 135): [number, number] {
  const scale = 0.72
  const isoX = originX + (x - y) * 0.866 * scale
  const isoY = originY + (x + y) * 0.5 * scale - z * scale
  return [isoX, isoY]
}

export const IsometricFloorPlanView: React.FC<IsometricFloorPlanViewProps> = ({
  floor,
  tables = [],
  spatialAnalysis,
  selectedTableId,
  onSelectTable,
  onAddTable,
  cctvOnline = true,
}) => {
  // Theme & Material Modes
  const [materialMode, setMaterialMode] = useState<'LIGHT_ARCHITECTURAL' | 'CYBER_HUD'>('LIGHT_ARCHITECTURAL')
  const [showTags, setShowTags] = useState(true)
  const [showOrbs, setShowOrbs] = useState(true)
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [showFlows, setShowFlows] = useState(true)
  const [showPeople, setShowPeople] = useState(true)
  const [hoveredTableId, setHoveredTableId] = useState<string | null>(null)

  // Quick Table Construction Modal
  const [showConstructModal, setShowConstructModal] = useState(false)
  const [newTableNum, setNewTableNum] = useState('')
  const [newTableType, setNewTableType] = useState<'BOOTH' | 'STANDARD' | 'ROUND' | 'BAR'>('BOOTH')
  const [newTableCapacity, setNewTableCapacity] = useState(4)
  const [constructing, setConstructing] = useState(false)

  const isLight = materialMode === 'LIGHT_ARCHITECTURAL'

  const floorW = floor.width || 1050
  const floorH = floor.height || 680

  const originX = 550
  const originY = 130

  // Building Footprint Vertices
  const fP0 = toIso(0, 0, 0, originX, originY)
  const fP1 = toIso(floorW, 0, 0, originX, originY)
  const fP2 = toIso(floorW, floorH, 0, originX, originY)
  const fP3 = toIso(0, floorH, 0, originX, originY)

  // Exterior Surrounding Landscaping (Grass & Parking)
  const extPad = 140
  const lP0 = toIso(-extPad, -extPad, 0, originX, originY)
  const lP1 = toIso(floorW + extPad, -extPad, 0, originX, originY)
  const lP2 = toIso(floorW + extPad, floorH + extPad, 0, originX, originY)
  const lP3 = toIso(-extPad, floorH + extPad, 0, originX, originY)

  // Exterior Architectural Cutaway Walls (Height = 110)
  const wallH = 110
  const wTop0 = toIso(0, 0, wallH, originX, originY)
  const wTop1 = toIso(floorW, 0, wallH, originX, originY)
  const wTop3 = toIso(0, floorH, wallH, originX, originY)

  // Spatial Analysis Data
  const heatPoints = spatialAnalysis?.heat_points || []
  const trafficFlows = spatialAnalysis?.traffic_flows || []
  const trackedPeople = spatialAnalysis?.tracked_people || []

  // Pre-calculate tables & massive 3D models
  const isoTables = useMemo(() => {
    return tables.map((t: any, index: number) => {
      const x = t.x ?? 120 + (index % 4) * 160
      const y = t.y ?? 100 + Math.floor(index / 4) * 140
      const w = t.width ?? 95
      const h = t.height ?? 75

      // Style determination
      const isRound = t.shape === 'CIRCLE'
      const isBooth = t.type === 'BOOTH' || (!isRound && (index % 3 === 0))
      const isBar = t.type === 'BAR'

      const centerTop = toIso(x + w / 2, y + h / 2, 34, originX, originY)
      const centerFloor = toIso(x + w / 2, y + h / 2, 0, originX, originY)

      return {
        table: t,
        x,
        y,
        w,
        h,
        isRound,
        isBooth,
        isBar,
        centerTop,
        centerFloor,
        isOccupied: t.status in ['SEATED', 'ACTIVE', 'BILLING'],
        hasBottleneck: t.kitchen?.has_bottleneck,
        duration: t.occupancy?.duration_minutes || 0,
        tagNum: index + 1,
      }
    })
  }, [tables, originX, originY])

  // Active or hovered table for top-left inspector
  const activeTable = isoTables.find((it) => it.table.id === (selectedTableId || hoveredTableId)) || isoTables[0]

  const handleConstructTable = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newTableNum) return
    setConstructing(true)
    try {
      const sectionId = floor.sections?.[0]?.id || 'sec-default'
      const shape = newTableType === 'ROUND' ? 'CIRCLE' : 'RECTANGLE'
      const type = newTableType === 'ROUND' ? 'STANDARD' : newTableType

      // Place newly constructed table in a clean open slot
      const existingCount = tables.length
      const posX = 140 + (existingCount % 4) * 170
      const posY = 120 + Math.floor(existingCount / 4) * 150

      if (onAddTable) {
        await onAddTable({
          floor_id: floor.id,
          section_id: sectionId,
          number: newTableNum,
          capacity: newTableCapacity,
          type,
          shape,
          x: posX,
          y: posY,
          width: newTableType === 'BOOTH' ? 100 : newTableType === 'ROUND' ? 75 : 90,
          height: newTableType === 'BOOTH' ? 80 : newTableType === 'ROUND' ? 75 : 70,
          rotation: 0,
        })
      }
      setNewTableNum('')
      setShowConstructModal(false)
    } catch (err) {
      console.error('Failed to construct 3D table', err)
    } finally {
      setConstructing(false)
    }
  }

  return (
    <div
      className={`iso-digital-twin-container ${isLight ? 'iso-digital-twin-container--light' : ''}`}
      style={{ position: 'relative', width: '100%', userSelect: 'none', overflow: 'hidden' }}
    >
      {/* ── TOP-LEFT TELEMETRY INSPECTOR (Matching Reference Image) ── */}
      {activeTable && (
        <div className="iso-telemetry-inspector-card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <span style={{ fontSize: '0.9rem' }}>🏷️</span>
              <strong style={{ fontSize: '0.9rem', color: isLight ? '#0f172a' : '#f8fafc' }}>
                Tag {activeTable.tagNum} • Table #{activeTable.table.number}
              </strong>
            </div>
            <span
              style={{
                fontSize: '0.68rem',
                padding: '2px 8px',
                borderRadius: 4,
                background: activeTable.isOccupied ? '#dcfce7' : '#f1f5f9',
                color: activeTable.isOccupied ? '#15803d' : '#64748b',
                fontWeight: 700,
                border: activeTable.isOccupied ? '1px solid #bbf7d0' : '1px solid #e2e8f0',
              }}
            >
              {activeTable.table.status}
            </span>
          </div>

          <div className="iso-telemetry-row">
            <div>
              <div className="iso-telemetry-stat-label">Status</div>
              <div className="iso-telemetry-stat-value" style={{ color: activeTable.isOccupied ? '#16a34a' : '#0284c7' }}>
                {activeTable.isOccupied ? 'Active' : 'Open'}
              </div>
            </div>
            <div>
              <div className="iso-telemetry-stat-label">Device Type</div>
              <div className="iso-telemetry-stat-value" style={{ color: isLight ? '#0f172a' : '#f4f4f5', fontSize: '0.85rem' }}>
                {activeTable.isBooth ? 'Booth' : activeTable.isRound ? 'Round' : 'Table'}
              </div>
            </div>
            <div>
              <div className="iso-telemetry-stat-label">{activeTable.isOccupied ? 'Duration' : 'Battery'}</div>
              <div
                className="iso-telemetry-stat-value"
                style={{ color: activeTable.duration > 60 ? '#dc2626' : activeTable.isOccupied ? '#0284c7' : '#16a34a' }}
              >
                {activeTable.isOccupied ? `${activeTable.duration}m` : '98%'}
              </div>
            </div>
          </div>

          <div className="iso-telemetry-btn-row">
            <button
              type="button"
              className="iso-telemetry-action-btn"
              onClick={() => onSelectTable?.(activeTable.table.id)}
            >
              📈 More Data
            </button>
            <button
              type="button"
              className="iso-telemetry-action-btn"
              onClick={() => onSelectTable?.(activeTable.table.id)}
            >
              🔗 Analytics
            </button>
          </div>
        </div>
      )}

      {/* ── TOP-RIGHT CCTV CAMERA STREAM BADGE ── */}
      <div
        style={{
          position: 'absolute',
          top: 14,
          right: 14,
          zIndex: 20,
          background: isLight ? 'rgba(255, 255, 255, 0.92)' : 'rgba(15, 23, 42, 0.88)',
          padding: '0.45rem 0.85rem',
          borderRadius: 8,
          border: isLight ? '1px solid #cbd5e1' : '1px solid rgba(56, 189, 248, 0.3)',
          display: 'flex',
          alignItems: 'center',
          gap: '0.55rem',
          fontSize: '0.75rem',
          color: isLight ? '#0f172a' : '#f8fafc',
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
          backdropFilter: 'blur(8px)',
        }}
      >
        <span className="twin-pulse-dot" style={{ backgroundColor: cctvOnline ? '#22c55e' : '#ef4444' }} />
        <span>
          Optical CCTV: <strong>{cctvOnline ? 'ACTIVE (1080p @ 25fps)' : 'OFFLINE'}</strong>
        </span>
      </div>

      {/* ── BOTTOM-LEFT CONTROLS TOOLBAR (Matching Reference Image) ── */}
      <div className="iso-bottom-controls-bar">
        <button
          type="button"
          className="iso-bottom-ctrl-btn"
          onClick={() => setMaterialMode(isLight ? 'CYBER_HUD' : 'LIGHT_ARCHITECTURAL')}
          title="Switch between Light Architectural Model and Dark Cyber HUD"
        >
          <span style={{ fontSize: '1rem' }}>🌓</span>
          <span>Material mode</span>
        </button>

        <button
          type="button"
          className={`iso-bottom-ctrl-btn ${showOrbs ? 'iso-bottom-ctrl-btn--active' : ''}`}
          onClick={() => setShowOrbs(!showOrbs)}
          title="Toggle Localization Beacons & Tracking Orbs"
        >
          <span style={{ fontSize: '1rem' }}>📍</span>
          <span>Localization</span>
        </button>

        <button
          type="button"
          className={`iso-bottom-ctrl-btn ${showTags ? 'iso-bottom-ctrl-btn--active' : ''}`}
          onClick={() => setShowTags(!showTags)}
          title="Toggle 3D Floating Tags"
        >
          <span style={{ fontSize: '1rem' }}>🏷️</span>
          <span>Labels</span>
        </button>

        <button
          type="button"
          className={`iso-bottom-ctrl-btn ${showHeatmap ? 'iso-bottom-ctrl-btn--active' : ''}`}
          onClick={() => setShowHeatmap(!showHeatmap)}
          title="Toggle Thermal Occupancy Radiance"
        >
          <span style={{ fontSize: '1rem' }}>🌡️</span>
          <span>Heatmap</span>
        </button>

        <button
          type="button"
          className={`iso-bottom-ctrl-btn ${showFlows ? 'iso-bottom-ctrl-btn--active' : ''}`}
          onClick={() => setShowFlows(!showFlows)}
          title="Toggle Traffic Flow Lines"
        >
          <span style={{ fontSize: '1rem' }}>🌊</span>
          <span>Flows</span>
        </button>

        <button
          type="button"
          className={`iso-bottom-ctrl-btn ${showPeople ? 'iso-bottom-ctrl-btn--active' : ''}`}
          onClick={() => setShowPeople(!showPeople)}
          title="Toggle Tracked Staff & Guest Avatars"
        >
          <span style={{ fontSize: '1rem' }}>👤</span>
          <span>Staff/Guests</span>
        </button>

        <button
          type="button"
          className="iso-bottom-ctrl-btn"
          style={{ color: '#0284c7' }}
          onClick={() => setShowConstructModal(true)}
          title="Construct a new 3D Table Live on the Floor"
        >
          <span style={{ fontSize: '1rem' }}>🏗️</span>
          <span>+ Construct Table</span>
        </button>
      </div>

      {/* ── MAIN 3D ISOMETRIC SVG CANVAS ── */}
      <svg
        viewBox="0 0 1150 720"
        style={{
          width: '100%',
          height: 'auto',
          minHeight: 580,
          background: isLight
            ? 'radial-gradient(circle at 50% 32%, #f8fafc 0%, #e2e8f0 100%)'
            : 'radial-gradient(circle at 50% 36%, #0b1329 0%, #030712 100%)',
          borderRadius: 12,
          display: 'block',
          transition: 'background 0.3s ease',
        }}
      >
        <defs>
          {/* Lighting & Shading Gradients */}
          <linearGradient id="wall-white-face" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="60%" stopColor="#f1f5f9" />
            <stop offset="100%" stopColor="#e2e8f0" />
          </linearGradient>

          <linearGradient id="wall-white-side" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#e2e8f0" />
            <stop offset="100%" stopColor="#cbd5e1" />
          </linearGradient>

          {/* Plush Red Banquette Velvet Gradients (Matching Reference Photo) */}
          <linearGradient id="booth-velvet-red" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#f43f5e" />
            <stop offset="45%" stopColor="#e11d48" />
            <stop offset="85%" stopColor="#be123c" />
            <stop offset="100%" stopColor="#9f1239" />
          </linearGradient>

          <linearGradient id="booth-cushion-red" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#fb7185" />
            <stop offset="100%" stopColor="#be123c" />
          </linearGradient>

          {/* Cyan / Turquoise Accent Panels on Booths */}
          <linearGradient id="booth-teal-wing" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stopColor="#2dd4bf" />
            <stop offset="100%" stopColor="#0d9488" />
          </linearGradient>

          {/* Wood Dining Table Surface */}
          <linearGradient id="wood-table-top" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#fed7aa" />
            <stop offset="50%" stopColor="#fdba74" />
            <stop offset="100%" stopColor="#fb923c" />
          </linearGradient>

          {/* White Marble Table Surface for Contemporary Look */}
          <linearGradient id="marble-table-top" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#ffffff" />
            <stop offset="70%" stopColor="#f1f5f9" />
            <stop offset="100%" stopColor="#e2e8f0" />
          </linearGradient>

          {/* Golden Beacon Spheres (Matching Reference Image Orbs) */}
          <radialGradient id="golden-orb" cx="35%" cy="35%" r="65%">
            <stop offset="0%" stopColor="#fef08a" />
            <stop offset="35%" stopColor="#facc15" />
            <stop offset="70%" stopColor="#eab308" />
            <stop offset="100%" stopColor="#ca8a04" />
          </radialGradient>

          {/* Thermal Radiant Filter */}
          <radialGradient id="heat-intense" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="#ef4444" stopOpacity="0.88" />
            <stop offset="40%" stopColor="#f97316" stopOpacity="0.7" />
            <stop offset="70%" stopColor="#eab308" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#22c55e" stopOpacity="0" />
          </radialGradient>

          <filter id="heat-blur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="28" />
          </filter>
        </defs>

        {/* ── LAYER 1: Exterior Environment (Grass Lawns & Parking Lot) ── */}
        <g id="iso-exterior-landscaping">
          {/* Outer Grass Area */}
          <polygon
            points={`${lP0[0]},${lP0[1]} ${lP1[0]},${lP1[1]} ${lP2[0]},${lP2[1]} ${lP3[0]},${lP3[1]}`}
            fill={isLight ? '#4ade80' : '#052e16'}
            opacity={isLight ? '0.85' : '0.4'}
          />

          {/* Parking Lot / Asphalt Road on Front-Left */}
          {(() => {
            const p0 = toIso(-extPad, floorH * 0.1, 0, originX, originY)
            const p1 = toIso(-15, floorH * 0.1, 0, originX, originY)
            const p2 = toIso(-15, floorH + extPad, 0, originX, originY)
            const p3 = toIso(-extPad, floorH + extPad, 0, originX, originY)

            return (
              <g>
                <polygon
                  points={`${p0[0]},${p0[1]} ${p1[0]},${p1[1]} ${p2[0]},${p2[1]} ${p3[0]},${p3[1]}`}
                  fill={isLight ? '#64748b' : '#0f172a'}
                />
                {/* White Parking Stalls Marking Line */}
                <line x1={p1[0] - 30} y1={p1[1]} x2={p2[0] - 30} y2={p2[1]} stroke="#ffffff" strokeWidth="2" strokeDasharray="16 12" opacity="0.85" />
              </g>
            )
          })()}

          {/* Exterior White Sidewalk Curb */}
          <polygon
            points={`${toIso(-12, -12, 0, originX, originY)[0]},${toIso(-12, -12, 0, originX, originY)[1]} ${toIso(floorW + 12, -12, 0, originX, originY)[0]},${toIso(floorW + 12, -12, 0, originX, originY)[1]} ${toIso(floorW + 12, floorH + 12, 0, originX, originY)[0]},${toIso(floorW + 12, floorH + 12, 0, originX, originY)[1]} ${toIso(-12, floorH + 12, 0, originX, originY)[0]},${toIso(-12, floorH + 12, 0, originX, originY)[1]}`}
            fill={isLight ? '#e2e8f0' : '#1e293b'}
            stroke={isLight ? '#cbd5e1' : '#334155'}
            strokeWidth="1.5"
          />
        </g>

        {/* ── LAYER 2: Architectural White Cutaway Walls & Polished Tile Floor ── */}
        <g id="iso-building-shell">
          {/* Building Polished Floor Plate */}
          <polygon
            points={`${fP0[0]},${fP0[1]} ${fP1[0]},${fP1[1]} ${fP2[0]},${fP2[1]} ${fP3[0]},${fP3[1]}`}
            fill={isLight ? '#f8fafc' : '#091024'}
            stroke={isLight ? '#cbd5e1' : 'rgba(56, 189, 248, 0.4)'}
            strokeWidth="2"
          />

          {/* Interior Floor Tile Grid Lines */}
          <g opacity={isLight ? '0.35' : '0.18'}>
            {Array.from({ length: 16 }).map((_, i) => {
              const xPos = (floorW / 16) * (i + 1)
              const start = toIso(xPos, 0, 0, originX, originY)
              const end = toIso(xPos, floorH, 0, originX, originY)
              return <line key={`gx-${i}`} x1={start[0]} y1={start[1]} x2={end[0]} y2={end[1]} stroke={isLight ? '#94a3b8' : '#38bdf8'} strokeWidth="0.8" />
            })}
            {Array.from({ length: 12 }).map((_, i) => {
              const yPos = (floorH / 12) * (i + 1)
              const start = toIso(0, yPos, 0, originX, originY)
              const end = toIso(floorW, yPos, 0, originX, originY)
              return <line key={`gy-${i}`} x1={start[0]} y1={start[1]} x2={end[0]} y2={end[1]} stroke={isLight ? '#94a3b8' : '#38bdf8'} strokeWidth="0.8" />
            })}
          </g>

          {/* Left Exterior White Wall */}
          <polygon
            points={`${fP0[0]},${fP0[1]} ${fP3[0]},${fP3[1]} ${wTop3[0]},${wTop3[1]} ${wTop0[0]},${wTop0[1]}`}
            fill={isLight ? 'url(#wall-white-face)' : '#111827'}
            stroke={isLight ? '#cbd5e1' : '#1e293b'}
            strokeWidth="1.5"
          />

          {/* Back Exterior White Wall */}
          <polygon
            points={`${fP0[0]},${fP0[1]} ${fP1[0]},${fP1[1]} ${wTop1[0]},${wTop1[1]} ${wTop0[0]},${wTop0[1]}`}
            fill={isLight ? 'url(#wall-white-side)' : '#0f172a'}
            stroke={isLight ? '#cbd5e1' : '#1e293b'}
            strokeWidth="1.5"
          />

          {/* Wall Cutaway Parapet Caps (Crisp Charcoal/White Top Strip) */}
          <line x1={wTop0[0]} y1={wTop0[1]} x2={wTop1[0]} y2={wTop1[1]} stroke={isLight ? '#ffffff' : '#38bdf8'} strokeWidth="4" />
          <line x1={wTop0[0]} y1={wTop0[1]} x2={wTop3[0]} y2={wTop3[1]} stroke={isLight ? '#ffffff' : '#38bdf8'} strokeWidth="4" />

          {/* Central Section Partition Wall (Matching Reference Photo with Red/Teal Panels) */}
          {(() => {
            const partX1 = floorW * 0.32
            const partX2 = floorW * 0.72
            const partY = floorH * 0.52
            const partH = 42

            const pb0 = toIso(partX1, partY, 0, originX, originY)
            const pb1 = toIso(partX2, partY, 0, originX, originY)
            const pt0 = toIso(partX1, partY, partH, originX, originY)
            const pt1 = toIso(partX2, partY, partH, originX, originY)

            return (
              <g>
                {/* Partition Face */}
                <polygon
                  points={`${pb0[0]},${pb0[1]} ${pb1[0]},${pb1[1]} ${pt1[0]},${pt1[1]} ${pt0[0]},${pt0[1]}`}
                  fill={isLight ? '#ffffff' : '#1e293b'}
                  stroke={isLight ? '#cbd5e1' : '#334155'}
                  strokeWidth="1.2"
                />
                {/* Red Upholstered Acoustic Panel Inset (Matching photo) */}
                <polygon
                  points={`${pb0[0] + 10},${pb0[1] - 4} ${pb1[0] - 10},${pb1[1] - 4} ${pt1[0] - 10},${pt1[1] + 6} ${pt0[0] + 10},${pt0[1] + 6}`}
                  fill="url(#booth-velvet-red)"
                  stroke="#be123c"
                  strokeWidth="0.8"
                />
                {/* Teal End-Cap Accent Strip */}
                <line x1={pb0[0]} y1={pb0[1]} x2={pt0[0]} y2={pt0[1]} stroke="#0d9488" strokeWidth="4" />
                <line x1={pb1[0]} y1={pb1[1]} x2={pt1[0]} y2={pt1[1]} stroke="#0d9488" strokeWidth="4" />
              </g>
            )
          })()}

          {/* Glass Curtain Windows along Front Facade */}
          {(() => {
            const gw0 = toIso(floorW * 0.15, floorH, 0, originX, originY)
            const gw1 = toIso(floorW * 0.85, floorH, 0, originX, originY)
            const gwt0 = toIso(floorW * 0.15, floorH, 50, originX, originY)
            const gwt1 = toIso(floorW * 0.85, floorH, 50, originX, originY)

            return (
              <g opacity="0.6">
                <polygon
                  points={`${gw0[0]},${gw0[1]} ${gw1[0]},${gw1[1]} ${gwt1[0]},${gwt1[1]} ${gwt0[0]},${gwt0[1]}`}
                  fill="rgba(56, 189, 248, 0.15)"
                  stroke="#475569"
                  strokeWidth="1"
                />
                {/* Window Mullions */}
                <line x1={(gw0[0] + gw1[0]) / 2} y1={(gw0[1] + gw1[1]) / 2} x2={(gwt0[0] + gwt1[0]) / 2} y2={(gwt0[1] + gwt1[1]) / 2} stroke="#334155" strokeWidth="1.5" />
              </g>
            )
          })()}
        </g>

        {/* ── LAYER 3: Optional Thermal Occupancy Heatmap ── */}
        {showHeatmap && (
          <g id="iso-thermal-radiance" filter="url(#heat-blur)">
            {heatPoints.map((hp) => {
              const [hX, hY] = toIso(hp.x, hp.y, 0, originX, originY)
              return (
                <ellipse
                  key={hp.id}
                  cx={hX}
                  cy={hY}
                  rx={hp.radius * 1.3}
                  ry={hp.radius * 0.75}
                  fill="url(#heat-intense)"
                />
              )
            })}
          </g>
        )}

        {/* ── LAYER 4: Animated Directional Flow Trajectories ── */}
        {showFlows && (
          <g id="iso-flow-lines">
            {trafficFlows.map((flow) => {
              if (flow.points.length < 2) return null
              const isoPts = flow.points.map((pt) => toIso(pt[0], pt[1], 2, originX, originY))
              const d = isoPts.reduce((acc, curr, idx) => (idx === 0 ? `M ${curr[0]} ${curr[1]}` : `${acc} L ${curr[0]} ${curr[1]}`), '')

              const color = flow.type === 'STAFF' ? '#f59e0b' : '#0284c7'

              return (
                <g key={flow.id}>
                  <path d={d} fill="none" stroke={color} strokeWidth="6" strokeLinecap="round" opacity="0.22" />
                  <path
                    d={d}
                    fill="none"
                    stroke={color}
                    strokeWidth="2.4"
                    strokeDasharray="8 6"
                    strokeLinecap="round"
                    className="animated-flow-line"
                    opacity="0.9"
                  />
                </g>
              )
            })}
          </g>
        )}

        {/* ── LAYER 5: MASSIVE 3D FURNITURE MODELS (Booths, Tables, Chairs, Stools) ── */}
        <g id="iso-furniture-layer">
          {isoTables.map(({ table, x, y, w, h, isRound, isBooth, isBar, centerTop, centerFloor, isOccupied, tagNum }) => {
            const isSelected = selectedTableId === table.id
            const isHovered = hoveredTableId === table.id

            return (
              <g
                key={table.id}
                onClick={() => onSelectTable?.(table.id)}
                onMouseEnter={() => setHoveredTableId(table.id)}
                onMouseLeave={() => setHoveredTableId(null)}
                style={{ cursor: 'pointer' }}
              >
                {/* ── 1. PLUSH BOOTH BANQUETTES WITH RED VELVET & TEAL WINGS ── */}
                {isBooth && (
                  <g id={`booth-${table.id}`}>
                    {/* Contact Ground Shadow */}
                    <polygon
                      points={`${toIso(x - 12, y - 10, 0, originX, originY)[0]},${toIso(x - 12, y - 10, 0, originX, originY)[1]} ${toIso(x + w + 12, y - 10, 0, originX, originY)[0]},${toIso(x + w + 12, y - 10, 0, originX, originY)[1]} ${toIso(x + w + 12, y + h + 10, 0, originX, originY)[0]},${toIso(x + w + 12, y + h + 10, 0, originX, originY)[1]} ${toIso(x - 12, y + h + 10, 0, originX, originY)[0]},${toIso(x - 12, y + h + 10, 0, originX, originY)[1]}`}
                      fill="rgba(0,0,0,0.25)"
                    />

                    {/* North Banquette Backrest (High Back Crimson Velvet) */}
                    {(() => {
                      const nb0 = toIso(x, y - 10, 0, originX, originY)
                      const nb1 = toIso(x + w, y - 10, 0, originX, originY)
                      const nt0 = toIso(x, y - 10, 48, originX, originY)
                      const nt1 = toIso(x + w, y - 10, 48, originX, originY)
                      const ns0 = toIso(x, y + 8, 20, originX, originY)
                      const ns1 = toIso(x + w, y + 8, 20, originX, originY)

                      return (
                        <g>
                          {/* Backrest Cushion */}
                          <polygon
                            points={`${ns0[0]},${ns0[1]} ${ns1[0]},${ns1[1]} ${nt1[0]},${nt1[1]} ${nt0[0]},${nt0[1]}`}
                            fill="url(#booth-velvet-red)"
                            stroke="#9f1239"
                            strokeWidth="1"
                          />
                          {/* Seat Cushion */}
                          <polygon
                            points={`${nb0[0]},${nb0[1]} ${nb1[0]},${nb1[1]} ${ns1[0]},${ns1[1]} ${ns0[0]},${ns0[1]}`}
                            fill="url(#booth-cushion-red)"
                            stroke="#be123c"
                            strokeWidth="1"
                          />
                          {/* Teal Wing Accent on Edge */}
                          <line x1={ns0[0]} y1={ns0[1]} x2={nt0[0]} y2={nt0[1]} stroke="url(#booth-teal-wing)" strokeWidth="3" />
                          <line x1={ns1[0]} y1={ns1[1]} x2={nt1[0]} y2={nt1[1]} stroke="url(#booth-teal-wing)" strokeWidth="3" />
                        </g>
                      )
                    })()}

                    {/* Central Dining Table in Booth */}
                    {(() => {
                      const tb0 = toIso(x + 10, y + 14, 28, originX, originY)
                      const tb1 = toIso(x + w - 10, y + 14, 28, originX, originY)
                      const tb2 = toIso(x + w - 10, y + h - 14, 28, originX, originY)
                      const tb3 = toIso(x + 10, y + h - 14, 28, originX, originY)

                      return (
                        <g>
                          {/* Table Pedestal Base */}
                          <line x1={centerFloor[0]} y1={centerFloor[1]} x2={centerTop[0]} y2={centerTop[1] + 4} stroke="#334155" strokeWidth="4" />
                          {/* Tabletop Surface */}
                          <polygon
                            points={`${tb0[0]},${tb0[1]} ${tb1[0]},${tb1[1]} ${tb2[0]},${tb2[1]} ${tb3[0]},${tb3[1]}`}
                            fill={isLight ? 'url(#wood-table-top)' : '#334155'}
                            stroke={isSelected ? '#0284c7' : isHovered ? '#10b981' : '#b45309'}
                            strokeWidth={isSelected ? '2.5' : '1.2'}
                          />
                          {/* Table Place Settings / Menus on Surface */}
                          <circle cx={centerTop[0] - 14} cy={centerTop[1]} r="4" fill="#ffffff" stroke="#cbd5e1" strokeWidth="0.8" />
                          <circle cx={centerTop[0] + 14} cy={centerTop[1]} r="4" fill="#ffffff" stroke="#cbd5e1" strokeWidth="0.8" />
                        </g>
                      )
                    })()}

                    {/* South Banquette Backrest (Facing North) */}
                    {(() => {
                      const sb0 = toIso(x, y + h - 8, 20, originX, originY)
                      const sb1 = toIso(x + w, y + h - 8, 20, originX, originY)
                      const st0 = toIso(x, y + h + 10, 48, originX, originY)
                      const st1 = toIso(x + w, y + h + 10, 48, originX, originY)
                      const sf0 = toIso(x, y + h + 10, 0, originX, originY)
                      const sf1 = toIso(x + w, y + h + 10, 0, originX, originY)

                      return (
                        <g>
                          {/* Seat Cushion */}
                          <polygon
                            points={`${sb0[0]},${sb0[1]} ${sb1[0]},${sb1[1]} ${st1[0]},${st1[1]} ${st0[0]},${st0[1]}`}
                            fill="url(#booth-cushion-red)"
                            stroke="#be123c"
                            strokeWidth="1"
                          />
                          {/* Outer Back Face */}
                          <polygon
                            points={`${st0[0]},${st0[1]} ${st1[0]},${st1[1]} ${sf1[0]},${sf1[1]} ${sf0[0]},${sf0[1]}`}
                            fill="url(#booth-velvet-red)"
                            stroke="#9f1239"
                            strokeWidth="1"
                          />
                          {/* Teal Wing Accent on Edge */}
                          <line x1={st0[0]} y1={st0[1]} x2={sf0[0]} y2={sf0[1]} stroke="url(#booth-teal-wing)" strokeWidth="3" />
                          <line x1={st1[0]} y1={st1[1]} x2={sf1[0]} y2={sf1[1]} stroke="url(#booth-teal-wing)" strokeWidth="3" />
                        </g>
                      )
                    })()}
                  </g>
                )}

                {/* ── 2. ROUND CAFE TABLE WITH OTTOMAN PUFF STOOLS ── */}
                {isRound && !isBooth && (
                  <g id={`round-${table.id}`}>
                    {/* Central Table Floor Shadow */}
                    <ellipse cx={centerFloor[0]} cy={centerFloor[1]} rx="24" ry="12" fill="rgba(0,0,0,0.2)" />
                    {/* Pedestal Stem */}
                    <line x1={centerFloor[0]} y1={centerFloor[1]} x2={centerTop[0]} y2={centerTop[1]} stroke="#475569" strokeWidth="4" />

                    {/* Circular Tabletop */}
                    <ellipse
                      cx={centerTop[0]}
                      cy={centerTop[1]}
                      rx="26"
                      ry="14"
                      fill={isLight ? 'url(#marble-table-top)' : '#334155'}
                      stroke={isSelected ? '#0284c7' : isHovered ? '#10b981' : '#94a3b8'}
                      strokeWidth={isSelected ? '2.5' : '1.2'}
                    />

                    {/* 4 Circular Ottoman Puff Stools around Table (Matching Reference Photo) */}
                    {[
                      toIso(x + w / 2, y + 4, 16, originX, originY), // North
                      toIso(x + w - 4, y + h / 2, 16, originX, originY), // East
                      toIso(x + w / 2, y + h - 4, 16, originX, originY), // South
                      toIso(x + 4, y + h / 2, 16, originX, originY), // West
                    ].map((sPos, sIdx) => (
                      <g key={`stool-${sIdx}`}>
                        {/* Stool Body Cylinder */}
                        <line x1={sPos[0]} y1={sPos[1]} x2={sPos[0]} y2={sPos[1] + 12} stroke="#18181b" strokeWidth="14" strokeLinecap="round" />
                        {/* Stool Top Cushion */}
                        <ellipse cx={sPos[0]} cy={sPos[1]} rx="8" ry="4.5" fill="#27272a" stroke="#52525b" strokeWidth="0.8" />
                      </g>
                    ))}
                  </g>
                )}

                {/* ── 3. STANDARD DINING TABLE WITH 4 INDIVIDUAL CHAIRS ── */}
                {!isBooth && !isRound && !isBar && (
                  <g id={`standard-${table.id}`}>
                    {/* Table Contact Shadow */}
                    <polygon
                      points={`${toIso(x, y, 0, originX, originY)[0]},${toIso(x, y, 0, originX, originY)[1]} ${toIso(x + w, y, 0, originX, originY)[0]},${toIso(x + w, y, 0, originX, originY)[1]} ${toIso(x + w, y + h, 0, originX, originY)[0]},${toIso(x + w, y + h, 0, originX, originY)[1]} ${toIso(x, y + h, 0, originX, originY)[0]},${toIso(x, y + h, 0, originX, originY)[1]}`}
                      fill="rgba(0,0,0,0.22)"
                    />

                    {/* 4 Table Legs */}
                    <line x1={toIso(x + 6, y + 6, 0, originX, originY)[0]} y1={toIso(x + 6, y + 6, 0, originX, originY)[1]} x2={toIso(x + 6, y + 6, 30, originX, originY)[0]} y2={toIso(x + 6, y + 6, 30, originX, originY)[1]} stroke="#475569" strokeWidth="2.5" />
                    <line x1={toIso(x + w - 6, y + 6, 0, originX, originY)[0]} y1={toIso(x + w - 6, y + 6, 0, originX, originY)[1]} x2={toIso(x + w - 6, y + 6, 30, originX, originY)[0]} y2={toIso(x + w - 6, y + 6, 30, originX, originY)[1]} stroke="#475569" strokeWidth="2.5" />
                    <line x1={toIso(x + w - 6, y + h - 6, 0, originX, originY)[0]} y1={toIso(x + w - 6, y + h - 6, 0, originX, originY)[1]} x2={toIso(x + w - 6, y + h - 6, 30, originX, originY)[0]} y2={toIso(x + w - 6, y + h - 6, 30, originX, originY)[1]} stroke="#475569" strokeWidth="2.5" />
                    <line x1={toIso(x + 6, y + h - 6, 0, originX, originY)[0]} y1={toIso(x + 6, y + h - 6, 0, originX, originY)[1]} x2={toIso(x + 6, y + h - 6, 30, originX, originY)[0]} y2={toIso(x + 6, y + h - 6, 30, originX, originY)[1]} stroke="#475569" strokeWidth="2.5" />

                    {/* Rectangular Tabletop Surface */}
                    <polygon
                      points={`${toIso(x, y, 30, originX, originY)[0]},${toIso(x, y, 30, originX, originY)[1]} ${toIso(x + w, y, 30, originX, originY)[0]},${toIso(x + w, y, 30, originX, originY)[1]} ${toIso(x + w, y + h, 30, originX, originY)[0]},${toIso(x + w, y + h, 30, originX, originY)[1]} ${toIso(x, y + h, 30, originX, originY)[0]},${toIso(x, y + h, 30, originX, originY)[1]}`}
                      fill={isLight ? 'url(#wood-table-top)' : '#334155'}
                      stroke={isSelected ? '#0284c7' : isHovered ? '#10b981' : '#b45309'}
                      strokeWidth={isSelected ? '2.5' : '1.2'}
                    />

                    {/* 4 Dining Chairs with Backrests surrounding Table */}
                    {[
                      { cX: x + w * 0.3, cY: y - 10, isNorth: true },
                      { cX: x + w * 0.7, cY: y - 10, isNorth: true },
                      { cX: x + w * 0.3, cY: y + h + 10, isNorth: false },
                      { cX: x + w * 0.7, cY: y + h + 10, isNorth: false },
                    ].map((chair, cIdx) => {
                      const cSeat = toIso(chair.cX, chair.cY, 16, originX, originY)
                      const cBackTop = toIso(chair.cX, chair.cY + (chair.isNorth ? -6 : 6), 36, originX, originY)

                      return (
                        <g key={`chair-${cIdx}`}>
                          {/* Chair Seat */}
                          <ellipse cx={cSeat[0]} cy={cSeat[1]} rx="6" ry="3.5" fill="#475569" stroke="#334155" strokeWidth="0.8" />
                          {/* Chair Backrest */}
                          <line x1={cSeat[0]} y1={cSeat[1]} x2={cBackTop[0]} y2={cBackTop[1]} stroke="#64748b" strokeWidth="2.5" />
                          <line x1={cBackTop[0] - 5} y1={cBackTop[1]} x2={cBackTop[0] + 5} y2={cBackTop[1]} stroke="#94a3b8" strokeWidth="2" />
                        </g>
                      )
                    })}
                  </g>
                )}

                {/* ── 4. GOLDEN BEACON DETECTION ORBS (Matching Reference Image) ── */}
                {showOrbs && (
                  <g id={`orb-${table.id}`}>
                    {/* Shadow on Floor below Orb */}
                    <ellipse cx={centerFloor[0] - 8} cy={centerFloor[1] + 8} rx="6" ry="3" fill="rgba(0,0,0,0.3)" />
                    {/* Floating Golden Orb */}
                    <circle
                      cx={centerTop[0] - 12}
                      cy={centerTop[1] - 18}
                      r="8"
                      fill="url(#golden-orb)"
                      stroke="#fef08a"
                      strokeWidth="1.2"
                      style={{ filter: 'drop-shadow(0 0 8px rgba(250, 204, 21, 0.7))' }}
                    />
                  </g>
                )}

                {/* ── 5. FLOATING 3D TAG BADGES (Matching "Tag 1", "Tag 2", "Tag 3") ── */}
                {showTags && (
                  <g transform={`translate(${centerTop[0]}, ${centerTop[1] - 38})`}>
                    {/* Stem Line down to table */}
                    <line x1="0" y1="0" x2="0" y2="18" stroke={isLight ? '#94a3b8' : 'rgba(255, 255, 255, 0.5)'} strokeWidth="1" strokeDasharray="2 2" />

                    {/* Tag Badge Pill Container */}
                    <g transform="translate(-32, -14)">
                      <rect
                        width="64"
                        height="20"
                        rx="5"
                        fill={isLight ? '#ffffff' : 'rgba(24, 24, 27, 0.92)'}
                        stroke={isOccupied ? '#16a34a' : isSelected ? '#0284c7' : isLight ? '#cbd5e1' : 'rgba(255, 255, 255, 0.3)'}
                        strokeWidth="1.4"
                        style={{ filter: isLight ? 'drop-shadow(0 2px 4px rgba(15,23,42,0.1))' : 'drop-shadow(0 4px 6px rgba(0,0,0,0.5))' }}
                      />
                      <circle cx="8" cy="10" r="3" fill={isOccupied ? '#16a34a' : '#0284c7'} />
                      <text x="16" y="14" fill={isLight ? '#0f172a' : '#ffffff'} fontSize="9" fontWeight="700">
                        Tag {tagNum}
                      </text>
                    </g>
                  </g>
                )}
              </g>
            )
          })}
        </g>

        {/* ── LAYER 6: Tracked Staff & Guest Figures ── */}
        {showPeople && (
          <g id="iso-tracked-avatars">
            {trackedPeople.map((person) => {
              const [pX, pY] = toIso(person.x, person.y, 0, originX, originY)
              const isChef = person.role === 'CHEF'
              const color = isChef ? '#ffffff' : person.role === 'SERVER' ? '#f59e0b' : '#0284c7'

              return (
                <g key={person.id} transform={`translate(${pX}, ${pY})`}>
                  <ellipse cx="0" cy="0" rx="9" ry="4.5" fill="none" stroke={color} strokeWidth="1.2" opacity="0.8" />
                  <g transform="translate(0, -22)">
                    <ellipse cx="0" cy="10" rx="5" ry="3" fill={color} />
                    <rect x="-4" y="2" width="8" height="9" rx="2" fill={color} />
                    <circle cx="0" cy="0" r="3.5" fill="#fed7aa" />
                  </g>
                </g>
              )
            })}
          </g>
        )}
      </svg>

      {/* ── QUICK TABLE CONSTRUCTION MODAL ── */}
      {showConstructModal && (
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(6px)',
            zIndex: 40,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1rem',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: 12,
              padding: '1.5rem',
              maxWidth: 420,
              width: '100%',
              boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
              color: '#0f172a',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>
                🏗️ Construct 3D Furniture Model
              </h3>
              <button
                type="button"
                onClick={() => setShowConstructModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer', color: '#64748b' }}
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConstructTable}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Table Number / Identifier
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 15, B2, C1"
                  value={newTableNum}
                  onChange={(e) => setNewTableNum(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    borderRadius: 6,
                    border: '1px solid #cbd5e1',
                    fontSize: '0.9rem',
                  }}
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: 6 }}>
                  3D Seating Style
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  {[
                    { id: 'BOOTH', label: '🛋️ Plush Booth', sub: 'Red Banquettes & Teal Wings' },
                    { id: 'STANDARD', label: '🪑 Dining Table', sub: 'Wood Table + 4 Chairs' },
                    { id: 'ROUND', label: '🔘 Round Bistro', sub: 'Round + Ottoman Puffs' },
                    { id: 'BAR', label: '🍸 Service Bar', sub: 'Long Counter Bar' },
                  ].map((style) => (
                    <button
                      key={style.id}
                      type="button"
                      onClick={() => setNewTableType(style.id as any)}
                      style={{
                        padding: '0.6rem',
                        borderRadius: 8,
                        border: newTableType === style.id ? '2px solid #0284c7' : '1px solid #cbd5e1',
                        background: newTableType === style.id ? '#f0f9ff' : '#f8fafc',
                        cursor: 'pointer',
                        textAlign: 'left',
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#0f172a' }}>{style.label}</div>
                      <div style={{ fontSize: '0.68rem', color: '#64748b' }}>{style.sub}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#475569', marginBottom: 4 }}>
                  Capacity / Seats
                </label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={newTableCapacity}
                  onChange={(e) => setNewTableCapacity(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '0.5rem 0.75rem',
                    borderRadius: 6,
                    border: '1px solid #cbd5e1',
                    fontSize: '0.9rem',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => setShowConstructModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={constructing}
                  className="btn btn-primary"
                  style={{ background: '#0284c7' }}
                >
                  {constructing ? 'Constructing...' : '✨ Construct in 3D'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
