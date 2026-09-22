import { STATUS_CONFIG } from '../../services/tableConfig'
import type { TableStatus } from '../../types'

const ORDER: TableStatus[] = [
  'AVAILABLE',
  'RESERVED',
  'SEATED',
  'ACTIVE',
  'BILLING',
  'PAID',
  'CLEANING',
]

export function StatusLegend() {
  return (
    <div className="status-legend" aria-label="Table status legend">
      <span className="status-legend__title">Status</span>
      <div className="status-legend__chips">
        {ORDER.map((status) => {
          const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.AVAILABLE
          return (
            <span key={status} className="legend-chip">
              <span
                className="legend-chip__dot"
                style={{ backgroundColor: cfg.border }}
              />
              {cfg.label}
            </span>
          )
        })}
      </div>
    </div>
  )
}
