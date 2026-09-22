import { STATUS_CONFIG, getNextStatuses } from '../../services/tableConfig'
import type { TableStatus } from '../../types'

interface StatusActionsProps {
  current: TableStatus
  onSelect: (status: TableStatus) => void
  disabled?: boolean
  loading?: boolean
}

export function StatusActions({
  current,
  onSelect,
  disabled,
  loading,
}: StatusActionsProps) {
  const next = getNextStatuses(current)

  if (next.length === 0) {
    return <p className="muted panel-empty-hint">No further changes from this state.</p>
  }

  return (
    <div className="status-actions">
      {next.map((status) => {
        const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.AVAILABLE
        return (
          <button
            key={status}
            type="button"
            className="status-action-btn"
            style={{
              borderColor: cfg.border,
              color: cfg.text,
              backgroundColor: cfg.bg,
            }}
            disabled={disabled || loading}
            onClick={() => onSelect(status)}
          >
            <span className="status-action-btn__arrow">→</span>
            {cfg.label}
          </button>
        )
      })}
    </div>
  )
}
