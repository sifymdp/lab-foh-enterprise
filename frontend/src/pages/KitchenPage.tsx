import { useCallback, useEffect, useRef, useState } from 'react'
import { api, normalizeKitchenOrder } from '../api/client'
import { useSocket } from '../context/SocketContext'
import type { KitchenOrder, KitchenStation } from '../types'
import { KDSSwitch } from '../components/kds/KDSSwitch'
import { StationFilter } from '../components/kds/StationFilter'
import { OrderDetailModal } from '../components/kds/OrderDetailModal'
import '../styles/kds.css'

function elapsedSeconds(from: string, to?: string | null): number {
  const start = new Date(from).getTime()
  const end = to ? new Date(to).getTime() : Date.now()
  return Math.max(0, Math.floor((end - start) / 1000))
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; dot: string }> = {
  RECEIVED: { label: 'Received', color: '#b45309', bg: '#fef3c7', border: '#fde68a', dot: '#f59e0b' },
  PREPARING: { label: 'Preparing', color: '#1d4ed8', bg: '#dbeafe', border: '#bfdbfe', dot: '#3b82f6' },
  READY: { label: 'Ready', color: '#15803d', bg: '#dcfce7', border: '#bbf7d0', dot: '#22c55e' },
  SERVED: { label: 'Served', color: '#475569', bg: '#f1f5f9', border: '#e2e8f0', dot: '#94a3b8' },
}

const SOURCE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  WAITER: { label: 'Waiter', color: '#6d28d9', bg: '#ede9fe' },
  QR: { label: 'QR Guest', color: '#0369a1', bg: '#e0f2fe' },
  BOT: { label: 'AI Bot', color: '#047857', bg: '#d1fae5' },
}

const NEXT_ACTION: Record<string, { label: string; nextStatus: string }> = {
  RECEIVED: { label: 'Start Preparing →', nextStatus: 'PREPARING' },
  PREPARING: { label: 'Mark Ready ✓', nextStatus: 'READY' },
  READY: { label: 'Mark Served ★', nextStatus: 'SERVED' },
}

function ElapsedTimer({ order }: { order: KitchenOrder }) {
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const startFrom = order.preparation_started_at ?? order.placed_at
    const endAt = order.served_at ?? order.ready_at ?? null

    if (endAt) {
      setElapsed(elapsedSeconds(startFrom, endAt))
      return
    }

    setElapsed(elapsedSeconds(startFrom))
    const id = setInterval(() => setElapsed(elapsedSeconds(startFrom)), 1000)
    return () => clearInterval(id)
  }, [order.placed_at, order.preparation_started_at, order.ready_at, order.served_at])

  const isLate = elapsed > 15 * 60
  const isMed = elapsed > 8 * 60

  return (
    <span
      className={`kds-elapsed-badge ${isLate ? 'is-late' : isMed ? 'is-warning' : ''}`}
      title={`Elapsed time since order round started`}
    >
      ⏱ {formatElapsed(elapsed)}
    </span>
  )
}

interface OrderCardProps {
  order: KitchenOrder
  onCardClick: (order: KitchenOrder) => void
  onQuickAction: (orderId: string, nextStatus: string) => void
  busy: boolean
}

function OrderCard({ order, onCardClick, onQuickAction, busy }: OrderCardProps) {
  const cfg = STATUS_CONFIG[order.status] ?? STATUS_CONFIG.RECEIVED
  const next = NEXT_ACTION[order.status]
  const srcKey = (order.source || 'WAITER').toUpperCase()
  const src = SOURCE_LABELS[srcKey] ?? SOURCE_LABELS.WAITER

  const items = order.items || []
  const totalItemCount = items.reduce((sum: number, i: any) => sum + (i.quantity || 1), 0)

  return (
    <div
      className={`kds-order-card kds-order-card--${order.status.toLowerCase()}`}
      onClick={() => onCardClick(order)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onCardClick(order)
        }
      }}
    >
      <div className="kds-order-card__header">
        <div className="kds-order-card__ident">
          <span className="kds-order-card__dot" style={{ background: cfg.dot }} />
          <strong className="kds-order-card__id">#{order.id.slice(-6).toUpperCase()}</strong>
          <span className="kds-order-card__table">Table {order.table_number || '?'}</span>
        </div>
        <div className="kds-order-card__badges">
          <span className="kds-source-badge" style={{ color: src.color, background: src.bg }}>
            {src.label}
          </span>
          <ElapsedTimer order={order} />
        </div>
      </div>

      <div className="kds-order-card__body">
        <div className="kds-order-card__item-list">
          {items.map((item: any, idx: number) => (
            <div key={item.id || idx} className="kds-order-card__item-row">
              <span className="kds-order-card__item-qty">{item.quantity}×</span>
              <span className="kds-order-card__item-name">{item.item_name}</span>
              {item.station && (
                <span className="kds-order-card__station-tag">{item.station}</span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="kds-order-card__footer">
        <span className="kds-order-card__count-hint">
          {totalItemCount} item{totalItemCount !== 1 ? 's' : ''} total
        </span>
        {next && (
          <button
            type="button"
            className="kds-order-card__action-btn"
            style={{ background: cfg.color }}
            disabled={busy}
            onClick={(e) => {
              e.stopPropagation()
              onQuickAction(order.id, next.nextStatus)
            }}
          >
            {busy ? 'Updating…' : next.label}
          </button>
        )}
      </div>
    </div>
  )
}

export function KitchenPage() {
  const { on } = useSocket()
  const [orders, setOrders] = useState<KitchenOrder[]>([])
  const [station, setStation] = useState<KitchenStation>('ALL')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set())
  const [selectedOrder, setSelectedOrder] = useState<KitchenOrder | null>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadOrders = useCallback(async () => {
    try {
      const data = await api.getKitchenOrders()
      setOrders(data || [])
      setError(null)
    } catch (e) {
      setError((e as Error).message || 'Failed to load kitchen orders')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    loadOrders()
  }, [loadOrders])

  useEffect(() => {
    pollRef.current = setInterval(() => loadOrders(), 12_000)
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [loadOrders])

  useEffect(() => {
    const unsub1 = on('order_placed', () => loadOrders())
    const unsub2 = on('order_status_updated', (payload) => {
      const updated = normalizeKitchenOrder(payload as Record<string, unknown>)
      setOrders((prev) => {
        if (updated.status === 'SERVED') return prev.filter((o) => o.id !== updated.id)
        const exists = prev.some((o) => o.id === updated.id)
        if (exists) return prev.map((o) => (o.id === updated.id ? updated : o))
        return [updated, ...prev]
      })
      setSelectedOrder((current) => {
        if (current && current.id === updated.id) {
          if (updated.status === 'SERVED') return null
          return updated
        }
        return current
      })
    })
    const unsub3 = on('order_served', () => loadOrders())
    return () => {
      unsub1()
      unsub2()
      unsub3()
    }
  }, [on, loadOrders])

  const handleStatusChange = async (orderId: string, newStatus: string) => {
    setBusyIds((s) => new Set(s).add(orderId))
    setActionError(null)
    try {
      const updated = await api.updateOrderStatus(orderId, newStatus)
      setOrders((prev) => {
        if (updated.status === 'SERVED') return prev.filter((o) => o.id !== orderId)
        return prev.map((o) => (o.id === orderId ? updated : o))
      })
      if (updated.status === 'SERVED') {
        setSelectedOrder(null)
      } else {
        setSelectedOrder(updated)
      }
    } catch (e) {
      setActionError(e instanceof Error ? e.message : 'Unable to update order status.')
    } finally {
      setBusyIds((s) => {
        const n = new Set(s)
        n.delete(orderId)
        return n
      })
    }
  }

  // Filter orders by station if selected
  const filteredOrders = station === 'ALL'
    ? orders
    : orders.filter((order) =>
        (order.items || []).some(
          (item: any) => item.station === station || !item.station,
        ),
      )

  const receivingCount = orders.filter((o) => o.status === 'RECEIVED').length
  const preparingCount = orders.filter((o) => o.status === 'PREPARING').length
  const readyCount = orders.filter((o) => o.status === 'READY').length

  return (
    <div className="kds-page-wrap">
      {/* Top Header */}
      <header className="kds-top-bar">
        <div className="kds-top-bar__left">
          <div className="kds-title-group">
            <h2>🍳 Kitchen Display System</h2>
            <span className="kds-view-pill">Live Station Queue</span>
          </div>
          <p className="muted">Real-time order line preparation and dispatch</p>
        </div>

        <div className="kds-top-bar__right">
          <div className="kds-stat-pills">
            <div className="kds-stat-pill kds-stat-pill--received">
              <span className="kds-stat-pill__num">{receivingCount}</span>
              <span className="kds-stat-pill__lbl">Received</span>
            </div>
            <div className="kds-stat-pill kds-stat-pill--preparing">
              <span className="kds-stat-pill__num">{preparingCount}</span>
              <span className="kds-stat-pill__lbl">Preparing</span>
            </div>
            <div className="kds-stat-pill kds-stat-pill--ready">
              <span className="kds-stat-pill__num">{readyCount}</span>
              <span className="kds-stat-pill__lbl">Ready</span>
            </div>
          </div>

          <KDSSwitch currentView="kitchen" />
        </div>
      </header>

      {actionError && (
        <div className="kds-alert-banner kds-alert-banner--error" role="alert">
          <span>⚠️ {actionError}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setActionError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Station Filter Bar */}
      <div className="kds-station-filter-container">
        <StationFilter selectedStation={station} onStationChange={setStation} />
      </div>

      {/* Content Area */}
      <main className="kds-content-area">
        {loading ? (
          <div className="kds-loading-box">
            <div className="spinner" />
            <p>Syncing kitchen line orders…</p>
          </div>
        ) : error ? (
          <div className="kds-error-box">
            <p className="form-error">⚠️ {error}</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => loadOrders()}>
              Retry
            </button>
          </div>
        ) : filteredOrders.length === 0 ? (
          <div className="kds-empty-box">
            <div className="kds-empty-icon">🍽️</div>
            <h3>Kitchen Line Clear!</h3>
            <p className="muted">
              No pending orders{station !== 'ALL' ? ` at station "${station}"` : ''}. All dishes served.
            </p>
          </div>
        ) : (
          <div className="kds-cards-grid">
            {filteredOrders.map((order) => (
              <OrderCard
                key={order.id}
                order={order}
                onCardClick={setSelectedOrder}
                onQuickAction={handleStatusChange}
                busy={busyIds.has(order.id)}
              />
            ))}
          </div>
        )}
      </main>

      {/* Order Detail Modal */}
      {selectedOrder && (
        <OrderDetailModal
          order={selectedOrder}
          onClose={() => setSelectedOrder(null)}
          onStatusChange={handleStatusChange}
          busy={busyIds.has(selectedOrder.id)}
        />
      )}
    </div>
  )
}
