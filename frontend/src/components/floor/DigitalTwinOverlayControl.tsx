import React from 'react'

export interface DigitalTwinOverlaySettings {
  showOccupancy: boolean
  showKitchen: boolean
  showVision: boolean
  showDiscrepancies: boolean
}

interface DigitalTwinOverlayControlProps {
  settings: DigitalTwinOverlaySettings
  onToggle: (key: keyof DigitalTwinOverlaySettings) => void
  onOpenReplay: () => void
  onOpenSimulation: () => void
  syncHash?: string
  lastSyncTime?: string
  floating?: boolean
  onClose?: () => void
}

export const DigitalTwinOverlayControl: React.FC<DigitalTwinOverlayControlProps> = ({
  settings,
  onToggle,
  onOpenReplay,
  onOpenSimulation,
  syncHash,
  lastSyncTime,
  floating = false,
  onClose,
}) => {
  return (
    <div className={`twin-hud-header ${floating ? 'twin-hud-header--floating' : ''}`}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', gap: '0.75rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
          <span className="twin-hud-badge">
            <span className="twin-pulse-dot" />
            Digital Twin Live Telemetry
          </span>
          {syncHash && (
            <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
              Hash: <strong style={{ color: '#0284c7' }}>#{syncHash}</strong>
              {lastSyncTime && ` • Synced at ${new Date(lastSyncTime).toLocaleTimeString()}`}
            </span>
          )}
        </div>

        {onClose && (
          <button
            type="button"
            className="twin-hud-close-btn"
            onClick={onClose}
            title="Hide overlays toolbar"
            aria-label="Hide overlays"
          >
            ✕
          </button>
        )}
      </div>

      <div className="twin-overlay-toolbar" style={{ marginTop: floating ? '0.35rem' : undefined }}>
        <button
          type="button"
          className={`twin-overlay-btn ${settings.showOccupancy ? 'twin-overlay-btn--active' : ''}`}
          onClick={() => onToggle('showOccupancy')}
          title="Toggle table occupancy duration badges"
        >
          ⏱️ Durations
        </button>

        <button
          type="button"
          className={`twin-overlay-btn ${settings.showKitchen ? 'twin-overlay-btn--active' : ''}`}
          onClick={() => onToggle('showKitchen')}
          title="Toggle kitchen prep bottleneck badges"
        >
          🍳 Kitchen Load
        </button>

        <button
          type="button"
          className={`twin-overlay-btn ${settings.showVision ? 'twin-overlay-btn--active' : ''}`}
          onClick={() => onToggle('showVision')}
          title="Toggle CCTV camera confidence metrics"
        >
          📷 CCTV Confidence
        </button>

        <button
          type="button"
          className={`twin-overlay-btn ${settings.showDiscrepancies ? 'twin-overlay-btn--active' : ''}`}
          onClick={() => onToggle('showDiscrepancies')}
          title="Toggle CCTV ↔ FOH discrepancy flags"
        >
          🚨 Discrepancies
        </button>

        <div style={{ width: 1, height: 20, background: 'rgba(148, 163, 184, 0.3)', margin: '0 4px' }} />

        <button
          type="button"
          className="twin-overlay-btn"
          style={{ background: 'rgba(56, 189, 248, 0.15)', color: '#0284c7', borderColor: 'rgba(56, 189, 248, 0.4)' }}
          onClick={onOpenReplay}
        >
          ⏪ Historical Replay
        </button>

        <button
          type="button"
          className="twin-overlay-btn"
          style={{ background: 'rgba(168, 85, 247, 0.15)', color: '#9333ea', borderColor: 'rgba(168, 85, 247, 0.4)' }}
          onClick={onOpenSimulation}
        >
          🧪 What-If Simulation
        </button>
      </div>
    </div>
  )
}

