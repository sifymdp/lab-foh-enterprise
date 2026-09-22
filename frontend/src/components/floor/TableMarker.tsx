import { useEffect, useState } from 'react'
import { OCCUPIED_STATUSES, STATUS_CONFIG } from '../../services/tableConfig'
import { useGlobalPointerDrag } from '../../lib/useGlobalPointerDrag'
import type { DiningSession, Table } from '../../types'
import { OccupancyTimer } from './OccupancyTimer'

interface TableMarkerProps {
  table: Table
  session?: DiningSession
  selected: boolean
  editable: boolean
  onSelect: (id: string) => void
  onPatch: (id: string, patch: Partial<Pick<Table, 'x' | 'y' | 'width' | 'height'>>) => void
}

export function TableMarker({
  table,
  session,
  selected,
  editable,
  onSelect,
  onPatch,
}: TableMarkerProps) {
  const [live, setLive] = useState(table)

  useEffect(() => {
    setLive(table)
  }, [table.x, table.y, table.width, table.height, table.id])

  const style = STATUS_CONFIG[table.status] ?? STATUS_CONFIG.AVAILABLE
  const isCircle = table.shape === 'CIRCLE'
  const showTimer = session && OCCUPIED_STATUSES.includes(table.status)

  const rect = { x: live.x, y: live.y, width: live.width, height: live.height }

  const { startMove, startResizeSE, startResizeE, startResizeS, dragging } = useGlobalPointerDrag(
    rect,
    (next) => {
      const w = isCircle ? Math.max(next.width, next.height) : next.width
      const h = isCircle ? w : next.height
      setLive((t) => ({ ...t, x: next.x, y: next.y, width: w, height: h }))
    },
    (next) => {
      const w = isCircle ? Math.max(next.width, next.height) : next.width
      const h = isCircle ? w : next.height
      onPatch(table.id, { x: next.x, y: next.y, width: w, height: h })
    },
    editable,
  )

  const showHandles = editable && (selected || dragging)

  return (
    <button
      type="button"
      className={[
        'table-marker',
        isCircle ? 'table-marker--circle' : 'table-marker--rect',
        selected ? 'table-marker--selected' : '',
        editable ? 'table-marker--editable' : '',
        dragging ? 'table-marker--dragging' : '',
      ]
        .filter(Boolean)
        .join(' ')}
      style={{
        left: live.x,
        top: live.y,
        width: live.width,
        height: live.height,
        transform: table.rotation ? `rotate(${table.rotation}deg)` : undefined,
        backgroundColor: style.bg,
        borderColor: style.border,
        color: style.text,
      }}
      onPointerDown={(e) => {
        if ((e.target as HTMLElement).classList.contains('resize-handle')) return
        e.stopPropagation()
        e.preventDefault()
        onSelect(table.id)
        if (editable) startMove(e)
      }}
      aria-label={`Table ${table.number}, ${style.label}`}
    >
      <span
        className="table-marker__status-dot"
        style={{ backgroundColor: style.border }}
        aria-hidden
      />
      <span className="table-marker__number">T{table.number}</span>
      <span className="table-marker__capacity">
        <span className="table-marker__guests" aria-hidden>
          👤
        </span>
        {table.capacity}
      </span>
      {showTimer && session && (
        <span className="table-marker__timer">
          <OccupancyTimer seatedAt={session.seatedAt} />
        </span>
      )}
      {table.status === 'BILLING' && (
        <span
          style={{
            position: 'absolute',
            bottom: -6,
            right: -6,
            background: '#8b5cf6',
            color: '#ffffff',
            fontSize: '9px',
            fontWeight: 800,
            padding: '2px 6px',
            borderRadius: '999px',
            boxShadow: '0 2px 5px rgba(0,0,0,0.25)',
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
            zIndex: 10,
          }}
        >
          🧾 BILLING
        </span>
      )}
      {showHandles && (
        <>
          <span className="resize-handle resize-handle--se" onPointerDown={startResizeSE} />
          {!isCircle && (
            <>
              <span className="resize-handle resize-handle--e" onPointerDown={startResizeE} />
              <span className="resize-handle resize-handle--s" onPointerDown={startResizeS} />
            </>
          )}
        </>
      )}
    </button>
  )
}
