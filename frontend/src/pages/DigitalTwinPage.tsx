import React, { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useFloor } from '../context/FloorContext'
import { DigitalTwinOverlayControl, type DigitalTwinOverlaySettings } from '../components/floor/DigitalTwinOverlayControl'
import { DigitalTwinReplayModal } from '../components/floor/DigitalTwinReplayModal'
import { DigitalTwinSimulationModal } from '../components/floor/DigitalTwinSimulationModal'
import { FloorPlanCanvas } from '../components/floor/FloorPlanCanvas'
import { IsometricFloorPlanView } from '../components/floor/IsometricFloorPlanView'

export function DigitalTwinPage() {
  const { floor, sessions, addTable } = useFloor()
  const [twinSnapshot, setTwinSnapshot] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [showReplay, setShowReplay] = useState(false)
  const [showSimulation, setShowSimulation] = useState(false)
  const [viewMode, setViewMode] = useState<'3D' | '2D'>('3D')
  const [selectedTableId, setSelectedTableId] = useState<string | null>(null)
  const [showOverlays, setShowOverlays] = useState(false)
  const [settings, setSettings] = useState<DigitalTwinOverlaySettings>({
    showOccupancy: true,
    showKitchen: true,
    showVision: true,
    showDiscrepancies: true,
  })

  const loadSnapshot = () => {
    if (!floor?.id) return
    setLoading(true)
    api
      .getDigitalTwinSnapshot(floor.id)
      .then((data) => setTwinSnapshot(data))
      .catch((err) => console.error('Failed to load twin snapshot', err))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadSnapshot()
    const timer = setInterval(loadSnapshot, 15000)
    return () => clearInterval(timer)
  }, [floor?.id])

  const twinOverlayMap = React.useMemo(() => {
    if (!twinSnapshot?.tables) return {}
    const map: Record<string, import('../components/floor/TableMarker').TableTwinOverlayData> = {}
    twinSnapshot.tables.forEach((t: any) => {
      map[t.id] = {
        durationMinutes: settings.showOccupancy ? t.occupancy?.duration_minutes : undefined,
        hasBottleneck: settings.showKitchen ? t.kitchen?.has_bottleneck : false,
        activeOrders: settings.showKitchen ? t.kitchen?.active_orders_count : 0,
        visionConfidence: settings.showVision && t.vision ? t.vision.confidence : undefined,
        detectedPeople: settings.showVision && t.vision ? t.vision.detected_people : 0,
        hasMismatch: settings.showDiscrepancies ? Boolean(t.discrepancy) : false,
      }
    })
    return map
  }, [twinSnapshot, settings])

  const kpis = twinSnapshot?.kpis || {}
  const selectedTable = twinSnapshot?.tables?.find((t: any) => t.id === selectedTableId)

  return (
    <div className="page-container" style={{ padding: '1.25rem' }}>
      <header style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Restaurant Digital Twin</h1>
            <span className="twin-hud-badge" style={{ fontSize: '0.75rem' }}>
              <span className="twin-pulse-dot" /> Live Telemetry
            </span>
            {loading && <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Syncing...</span>}
          </div>
          <p className="muted" style={{ margin: 0, fontSize: '0.875rem' }}>
            Authoritative FOH synchronization • Computer-vision observations • Operational sandbox
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* 3D vs 2D View Switcher */}
          <div className="twin-view-mode-toggle">
            <button
              type="button"
              className={`twin-view-mode-btn ${viewMode === '3D' ? 'twin-view-mode-btn--active' : ''}`}
              onClick={() => setViewMode('3D')}
              title="3D Isometric Cutaway View with Heatmap, Flow Lines & Spatial Tracking"
            >
              🧊 3D Isometric Twin
            </button>
            <button
              type="button"
              className={`twin-view-mode-btn ${viewMode === '2D' ? 'twin-view-mode-btn--active' : ''}`}
              onClick={() => setViewMode('2D')}
              title="2D Top-Down Floor Canvas HUD"
            >
              🗺️ 2D Floor Plan
            </button>
            <button
              type="button"
              className={`twin-view-mode-btn ${showOverlays ? 'twin-view-mode-btn--active' : ''}`}
              onClick={() => setShowOverlays((v) => !v)}
              title={showOverlays ? 'Hide Telemetry Controls' : 'Show Telemetry & Overlays'}
              style={showOverlays ? { background: '#0284c7', color: '#fff', borderColor: '#0284c7' } : {}}
            >
              📊 {showOverlays ? 'Hide Overlays' : 'Overlays'}
            </button>
          </div>

          <button type="button" className="btn btn-secondary" onClick={loadSnapshot}>
            🔄 Refresh Snapshot
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => setShowReplay(true)}>
            ⏪ Historical Replay
          </button>
          <button
            type="button"
            className="btn btn-primary"
            style={{ background: '#a855f7' }}
            onClick={() => setShowSimulation(true)}
          >
            🧪 What-If Simulation
          </button>
        </div>
      </header>

      {/* KPI Telemetry Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.8rem', marginBottom: '1.25rem' }}>
        <div style={{ background: 'var(--surface)', padding: '0.9rem', borderRadius: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Seat Utilization</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#0284c7' }}>
            {kpis.utilization_rate ?? 0}%
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {kpis.occupied_tables ?? 0} of {kpis.total_tables ?? 0} tables seated
          </div>
        </div>

        <div style={{ background: 'var(--surface)', padding: '0.9rem', borderRadius: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Active Guests</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: '#16a34a' }}>
            {kpis.active_guests ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            of {kpis.total_capacity ?? 0} total capacity
          </div>
        </div>

        <div style={{ background: 'var(--surface)', padding: '0.9rem', borderRadius: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>CCTV Discrepancies</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: (kpis.pending_discrepancies || 0) > 0 ? '#dc2626' : '#16a34a' }}>
            {kpis.pending_discrepancies ?? 0}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {(kpis.pending_discrepancies || 0) > 0 ? 'Requires host review' : 'No mismatches'}
          </div>
        </div>

        <div style={{ background: 'var(--surface)', padding: '0.9rem', borderRadius: 10, border: '1px solid var(--border)' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Sync Health</div>
          <div style={{ fontSize: '1.1rem', fontWeight: 700, color: '#059669', marginTop: 4 }}>
            100% In-Sync
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
            Hash: #{twinSnapshot?.sync?.reconciliation_hash ?? '---'}
          </div>
        </div>
      </div>

      {/* Main Digital Twin Canvas */}
      {floor && (
        <div className="floor-display-wrapper floor-display-wrapper--twin-mode" style={{ minHeight: 560, position: 'relative' }}>
          {showOverlays && (
            <DigitalTwinOverlayControl
              floating={true}
              onClose={() => setShowOverlays(false)}
              settings={settings}
              onToggle={(k) => setSettings((prev) => ({ ...prev, [k]: !prev[k] }))}
              onOpenReplay={() => setShowReplay(true)}
              onOpenSimulation={() => setShowSimulation(true)}
              syncHash={twinSnapshot?.sync?.reconciliation_hash}
              lastSyncTime={twinSnapshot?.sync?.synchronized_at}
            />
          )}

          <div style={{ padding: '0.75rem', overflow: 'hidden' }}>
            {viewMode === '3D' ? (
              <IsometricFloorPlanView
                floor={floor}
                tables={twinSnapshot?.tables || floor.tables}
                spatialAnalysis={twinSnapshot?.spatial_analysis}
                selectedTableId={selectedTableId}
                onSelectTable={(id) => setSelectedTableId(id === selectedTableId ? null : id)}
                onAddTable={async (payload) => {
                  await addTable(payload)
                  loadSnapshot()
                }}
                cctvOnline={Boolean(twinSnapshot?.cameras?.[0]?.is_online ?? true)}
              />
            ) : (
              <div style={{ overflow: 'auto' }}>
                <FloorPlanCanvas
                  floor={floor}
                  sessions={sessions}
                  twinOverlayMap={twinOverlayMap}
                  editable={false}
                  selection={selectedTableId ? { type: 'table', id: selectedTableId } : null}
                  onSelect={(sel) => setSelectedTableId(sel?.type === 'table' ? sel.id : null)}
                  onTableChange={() => {}}
                  onSectionChange={() => {}}
                  onLabelChange={() => {}}
                />
              </div>
            )}
          </div>

          {/* Selected Station Inspector Bottom Sheet / Bar */}
          {selectedTable && (
            <div
              style={{
                margin: '0.75rem',
                padding: '0.85rem 1.25rem',
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: 10,
                color: '#0f172a',
                boxShadow: '0 4px 16px rgba(15, 23, 42, 0.08)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#0284c7' }}>
                  Table #{selectedTable.number}
                </div>
                <span
                  style={{
                    padding: '2px 8px',
                    borderRadius: 6,
                    fontSize: '0.75rem',
                    fontWeight: 700,
                    background:
                      selectedTable.status === 'SEATED' || selectedTable.status === 'ACTIVE'
                        ? '#dcfce7'
                        : selectedTable.status === 'CLEANING'
                        ? '#fef9c3'
                        : '#f1f5f9',
                    color:
                      selectedTable.status === 'SEATED' || selectedTable.status === 'ACTIVE'
                        ? '#15803d'
                        : selectedTable.status === 'CLEANING'
                        ? '#a16207'
                        : '#475569',
                    border: '1px solid #e2e8f0',
                  }}
                >
                  {selectedTable.status}
                </span>
                <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                  Capacity: {selectedTable.capacity} guests
                </span>
                {selectedTable.occupancy?.duration_minutes > 0 && (
                  <span style={{ fontSize: '0.8rem', color: '#0284c7', fontWeight: 600 }}>
                    ⏱️ Occupied for {selectedTable.occupancy.duration_minutes}m
                  </span>
                )}
                {selectedTable.kitchen?.active_orders_count > 0 && (
                  <span style={{ fontSize: '0.8rem', color: '#b45309', fontWeight: 600 }}>
                    🍳 {selectedTable.kitchen.active_orders_count} orders in kitchen
                  </span>
                )}
                {selectedTable.vision && (
                  <span style={{ fontSize: '0.8rem', color: '#047857', fontWeight: 600 }}>
                    📹 Optical CCTV: {selectedTable.vision.detected_people} detected ({Math.round(selectedTable.vision.confidence * 100)}% conf)
                  </span>
                )}
              </div>
              <button
                type="button"
                className="btn btn-sm"
                style={{ background: '#f8fafc', color: '#475569', border: '1px solid #cbd5e1' }}
                onClick={() => setSelectedTableId(null)}
              >
                ✕ Close Inspector
              </button>
            </div>
          )}
        </div>
      )}

      {floor && (
        <DigitalTwinReplayModal
          floorId={floor.id}
          isOpen={showReplay}
          onClose={() => setShowReplay(false)}
        />
      )}

      {floor && (
        <DigitalTwinSimulationModal
          floor={floor}
          isOpen={showSimulation}
          onClose={() => setShowSimulation(false)}
        />
      )}
    </div>
  )
}
