import { useEffect, useState } from 'react'
import { billingApi, ordersApi, type Order } from '../../api/extensions'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { getNextStatuses, STATUS_CONFIG } from '../../services/tableConfig'
import { OccupancyTimer } from '../floor/OccupancyTimer'
import type { DiningSession, Table, TableStatus } from '../../types'

interface SessionCardProps {
  session: DiningSession
  table?: Table
  sectionName?: string
  onAdvance: (tableId: string, status: TableStatus) => void
  onRelease: (sessionId: string) => void
  onRefresh?: () => void
}

function aggregateItems(orders: Order[]) {
  const map = new Map<string, { name: string; price: number; qty: number }>()
  for (const order of orders) {
    for (const item of order.items) {
      const key = `${item.itemName}-${item.unitPrice}`
      const existing = map.get(key)
      if (existing) existing.qty += item.quantity
      else map.set(key, { name: item.itemName, price: item.unitPrice, qty: item.quantity })
    }
  }
  return [...map.values()]
}

export function SessionCard({
  session,
  table,
  sectionName,
  onAdvance,
  onRelease,
  onRefresh,
}: SessionCardProps) {
  const status = session.status as TableStatus
  const cfg = STATUS_CONFIG[status] ?? STATUS_CONFIG.AVAILABLE
  const next = getNextStatuses(status)
  const primaryNext = next[0]

  const [orders, setOrders] = useState<Order[]>([])
  const [loadingOrders, setLoadingOrders] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [confirmPaid, setConfirmPaid] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoadingOrders(true)
    ordersApi.list({ sessionId: session.id })
      .then((data) => { if (!cancelled) setOrders(data) })
      .catch(() => { if (!cancelled) setOrders([]) })
      .finally(() => { if (!cancelled) setLoadingOrders(false) })
    return () => { cancelled = true }
  }, [session.id])

  const items = aggregateItems(orders)
  const total = items.reduce((sum, i) => sum + i.price * i.qty, 0)

  const handleRequestBill = async () => {
    setActionLoading(true)
    try {
      await billingApi.requestBill(session.id)
      onAdvance(session.tableId, 'BILLING')
      onRefresh?.()
    } finally {
      setActionLoading(false)
    }
  }

  const handleMarkPaid = async () => {
    setActionLoading(true)
    try {
      await billingApi.markPaid(session.id)
      setConfirmPaid(false)
      onRefresh?.()
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <article className="session-card" style={{ borderLeftColor: cfg.border }}>
      <div className="session-card__main">
        <div className="session-card__header">
          <span className="session-table-badge">T{table?.number ?? '?'}</span>
          {sectionName && <span className="session-section-tag">{sectionName}</span>}
          <span className="session-status-pill" style={{ backgroundColor: cfg.bg, color: cfg.text, borderColor: cfg.border }}>
            {cfg.label}
          </span>
        </div>
        <h3 className="session-card__title">
          {session.guestName || 'Walk-in'}
          <span className="muted"> · party of {session.partySize}</span>
        </h3>
        <p className="session-card__meta">
          <OccupancyTimer seatedAt={session.seatedAt} /> seated
          {table && <span> · {table.capacity} seats</span>}
        </p>

        {loadingOrders ? (
          <p className="muted" style={{ fontSize: 12 }}>Loading orders…</p>
        ) : items.length === 0 ? (
          <p className="muted" style={{ fontSize: 12 }}>No orders placed yet.</p>
        ) : (
          <ul style={{ margin: '8px 0 0', padding: 0, listStyle: 'none', fontSize: 13 }}>
            {items.map((i) => (
              <li key={i.name} style={{ color: '#475569' }}>
                {i.qty}× {i.name} — £{(i.price * i.qty).toFixed(2)}
              </li>
            ))}
            <li style={{ fontWeight: 700, marginTop: 4, color: '#0f172a' }}>
              Total so far: £{total.toFixed(2)}
            </li>
          </ul>
        )}
      </div>

      <div className="session-card__actions">
        {status === 'ACTIVE' && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={handleRequestBill} disabled={actionLoading || items.length === 0}>
            Request Bill
          </button>
        )}
        {status === 'BILLING' && (
          <button type="button" className="btn btn-primary btn-sm" onClick={() => setConfirmPaid(true)} disabled={actionLoading}>
            Mark Paid
          </button>
        )}
        {primaryNext && !['CLEANING', 'AVAILABLE', 'BILLING'].includes(status) && (
          <button type="button" className="btn btn-primary btn-sm" onClick={() => onAdvance(session.tableId, primaryNext)}>
            → {(STATUS_CONFIG[primaryNext] ?? STATUS_CONFIG.AVAILABLE).label}
          </button>
        )}
        {!['CLEANING', 'AVAILABLE'].includes(status) && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => onRelease(session.id)}>
            Release table
          </button>
        )}
      </div>

      <ConfirmDialog
        open={confirmPaid}
        message={`Mark Table ${table?.number ?? '?'} as paid? This advances the table to cleaning.`}
        confirmLabel="Mark paid"
        onConfirm={handleMarkPaid}
        onCancel={() => setConfirmPaid(false)}
      />
    </article>
  )
}
