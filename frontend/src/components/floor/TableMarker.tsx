import { useEffect, useState } from 'react'
import { OCCUPIED_STATUSES, STATUS_CONFIG } from '../../services/tableConfig'
import { useGlobalPointerDrag } from '../../lib/useGlobalPointerDrag'
import type { DiningSession, Table } from '../../types'
import { OccupancyTimer } from './OccupancyTimer'

export interface TableReservationInfo {
  id: string
  guestName: string
  partySize: number
  reservedFor: string
}

interface TableMarkerProps {
  table: Table
  session?: DiningSession
  reservation?: TableReservationInfo
  hasWaiterCall?: boolean
  waiterCallState?: 'CALLING' | 'ON_IT' | boolean
  cashCallState?: 'CALLING' | 'ON_IT' | boolean
  isHighlighted?: boolean
  isDimmed?: boolean
  pendingOrdersCount?: number
  selected: boolean
  editable: boolean
  onSelect: (id: string) => void
  onPatch: (id: string, patch: Partial<Pick<Table, 'x' | 'y' | 'width' | 'height'>>) => void
}

export function TableMarker({
  table,
  session,
  reservation,
  hasWaiterCall,
  waiterCallState,
  cashCallState,
  isHighlighted,
  isDimmed,
  pendingOrdersCount,
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

  const isCalling = waiterCallState === 'CALLING' || (waiterCallState === true && hasWaiterCall) || (hasWaiterCall && !waiterCallState)
  const isOnIt = waiterCallState === 'ON_IT'
  const isCashCalling = cashCallState === 'CALLING' || cashCallState === true
  const isCashOnIt = cashCallState === 'ON_IT'

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
        isCalling ? 'table-marker--waiter-calling' : '',
        isOnIt ? 'table-marker--waiter-on-it' : '',
        isCashCalling ? 'table-marker--cash-calling' : '',
        isCashOnIt ? 'table-marker--cash-on-it' : '',
        isHighlighted ? 'table-marker--highlighted' : '',
        isDimmed ? 'table-marker--dimmed' : '',
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
      {isCalling && (
        <span
          className="table-marker__waiter-call"
          style={{
            position: 'absolute',
            top: -12,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#ef4444',
            color: '#ffffff',
            fontSize: '10px',
            fontWeight: 800,
            padding: '2px 9px',
            borderRadius: '999px',
            boxShadow: '0 2px 10px rgba(239, 68, 68, 0.8)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            zIndex: 20,
            whiteSpace: 'nowrap',
          }}
          title="Customer requested assistance - BLINKING"
        >
          🔔 CALL WAITER
        </span>
      )}
      {isOnIt && (
        <span
          className="table-marker__waiter-call"
          style={{
            position: 'absolute',
            top: -12,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#f59e0b',
            color: '#ffffff',
            fontSize: '10px',
            fontWeight: 800,
            padding: '2px 9px',
            borderRadius: '999px',
            boxShadow: '0 2px 8px rgba(245, 158, 11, 0.6)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            zIndex: 20,
            whiteSpace: 'nowrap',
          }}
          title="Staff is on the way / attending"
        >
          🏃 ON THE WAY
        </span>
      )}
      {isCashCalling && (
        <span
          className="table-marker__waiter-call"
          style={{
            position: 'absolute',
            top: -12,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#10b981',
            color: '#ffffff',
            fontSize: '10px',
            fontWeight: 800,
            padding: '2px 9px',
            borderRadius: '999px',
            boxShadow: '0 2px 10px rgba(16, 185, 129, 0.85)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            zIndex: 22,
            whiteSpace: 'nowrap',
          }}
          title="Customer requested cash payment - BLINKING"
        >
          💵 CASH PAYMENT
        </span>
      )}
      {isCashOnIt && (
        <span
          className="table-marker__waiter-call"
          style={{
            position: 'absolute',
            top: -12,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#0284c7',
            color: '#ffffff',
            fontSize: '10px',
            fontWeight: 800,
            padding: '2px 9px',
            borderRadius: '999px',
            boxShadow: '0 2px 8px rgba(2, 132, 199, 0.7)',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
            zIndex: 22,
            whiteSpace: 'nowrap',
          }}
          title="Staff is collecting cash payment"
        >
          🏃 COLLECTING CASH
        </span>
      )}
      {Boolean(pendingOrdersCount && pendingOrdersCount > 0) && (
        <span
          style={{
            position: 'absolute',
            top: -10,
            right: -6,
            background: '#f59e0b',
            color: '#ffffff',
            fontSize: '9px',
            fontWeight: 800,
            padding: '2px 6px',
            borderRadius: '999px',
            boxShadow: '0 2px 6px rgba(245, 158, 11, 0.5)',
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
            zIndex: 15,
            whiteSpace: 'nowrap',
          }}
          title={`${pendingOrdersCount} orders waiting for waiter approval`}
        >
          ⏳ {pendingOrdersCount} NEW
        </span>
      )}
      {(table.status === 'RESERVED' || reservation) && (
        <span
          style={{
            position: 'absolute',
            bottom: -8,
            left: '50%',
            transform: 'translateX(-50%)',
            background: '#2563eb',
            color: '#ffffff',
            fontSize: '9px',
            fontWeight: 700,
            padding: '2px 7px',
            borderRadius: '999px',
            boxShadow: '0 2px 6px rgba(37, 99, 235, 0.4)',
            display: 'flex',
            alignItems: 'center',
            gap: '3px',
            zIndex: 10,
            whiteSpace: 'nowrap',
            maxWidth: '120px',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
          title={reservation ? `Reserved: ${reservation.guestName} (${reservation.partySize}p)` : 'Reserved'}
        >
          📅 {reservation ? reservation.guestName : 'RESERVED'}
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
