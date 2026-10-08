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

interface StatusLegendProps {
  selectedStatus?: TableStatus | null
  onSelectStatus?: (status: TableStatus | null) => void
  statusCounts?: Partial<Record<TableStatus, number>>
}

export function StatusLegend({ selectedStatus, onSelectStatus, statusCounts }: StatusLegendProps) {
  const totalTables = statusCounts
    ? Object.values(statusCounts).reduce((sum, n) => sum + (n || 0), 0)
    : undefined
  const isAll = !selectedStatus

  return (
    <div className="status-legend" aria-label="Table status legend" style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
      <span className="status-legend__title" style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: '#64748b', letterSpacing: '0.05em' }}>
        STATUS:
      </span>
      <div className="status-legend__chips" style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
        {/* 'All' option chip */}
        <button
          type="button"
          className={`legend-chip ${isAll ? 'legend-chip--active' : ''}`}
          onClick={() => onSelectStatus?.(null)}
          style={{
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            fontSize: '0.75rem',
            fontWeight: isAll ? 700 : 500,
            color: isAll ? '#1d4ed8' : 'var(--text-muted, #475569)',
            padding: '0.25rem 0.65rem',
            background: isAll ? '#ffffff' : 'var(--surface-2, #f1f5f9)',
            border: isAll ? '2px solid #2563eb' : '1px solid #e2e8f0',
            borderRadius: '999px',
            boxShadow: isAll ? '0 0 0 2px rgba(37, 99, 235, 0.2), 0 2px 6px rgba(0, 0, 0, 0.06)' : 'none',
            transition: 'all 0.15s ease',
          }}
          title="Show all tables"
        >
          <span
            className="legend-chip__dot"
            style={{ backgroundColor: isAll ? '#2563eb' : '#64748b', width: 8, height: 8, borderRadius: '50%' }}
          />
          <span>All</span>
          {typeof totalTables === 'number' && (
            <span
              style={{
                marginLeft: 2,
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '1px 5px',
                borderRadius: 999,
                backgroundColor: isAll ? '#2563eb' : 'rgba(0,0,0,0.08)',
                color: isAll ? '#ffffff' : 'inherit',
              }}
            >
              {totalTables}
            </span>
          )}
        </button>

        {ORDER.map((status) => {
          const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.AVAILABLE
          const isSelected = selectedStatus === status
          const count = statusCounts ? statusCounts[status] || 0 : undefined

          return (
            <button
              key={status}
              type="button"
              className={`legend-chip ${isSelected ? 'legend-chip--active' : ''}`}
              onClick={() => onSelectStatus?.(isSelected ? null : status)}
              style={{
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
                fontSize: '0.75rem',
                fontWeight: isSelected ? 700 : 500,
                color: isSelected ? cfg.border : 'var(--text-muted, #475569)',
                padding: '0.25rem 0.65rem',
                background: isSelected ? `${cfg.bg || '#ffffff'}` : 'var(--surface-2, #f1f5f9)',
                border: isSelected ? `2px solid ${cfg.border}` : '1px solid #e2e8f0',
                borderRadius: '999px',
                boxShadow: isSelected ? `0 0 0 2px ${cfg.border}33, 0 2px 6px rgba(0,0,0,0.08)` : 'none',
                transition: 'all 0.15s ease',
              }}
              title={`Click to check / highlight ${cfg.label} tables`}
            >
              <span
                className="legend-chip__dot"
                style={{ backgroundColor: cfg.border, width: 8, height: 8, borderRadius: '50%' }}
              />
              <span>{cfg.label}</span>
              {typeof count === 'number' && (
                <span
                  style={{
                    marginLeft: 2,
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    padding: '1px 5px',
                    borderRadius: 999,
                    backgroundColor: isSelected ? cfg.border : 'rgba(0,0,0,0.08)',
                    color: isSelected ? '#ffffff' : 'inherit',
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
