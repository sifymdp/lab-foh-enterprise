import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, normalizeKitchenOrder } from '../api/client'
import { useSocket } from '../context/SocketContext'
import type { KitchenOrder, KitchenStation } from '../types'
import { KDSSwitch } from '../components/kds/KDSSwitch'
import { StationFilter, matchItemStation, getItemDisplayStation } from '../components/kds/StationFilter'
import { OrderDetailModal } from '../components/kds/OrderDetailModal'
import { elapsedSeconds, formatElapsed, formatTime } from '../lib/formatters'
import '../styles/kds.css'

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string; border: string; dot: string }> = {
  RECEIVED: { label: 'Received', color: '#b45309', bg: '#fef3c7', border: '#fde68a', dot: '#f59e0b' },
  CONFIRMED: { label: 'Confirmed', color: '#b45309', bg: '#fef3c7', border: '#fde68a', dot: '#f59e0b' },
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
  CONFIRMED: { label: 'Start Preparing →', nextStatus: 'PREPARING' },
  PREPARING: { label: 'Mark Ready ✓', nextStatus: 'READY' },
  READY: { label: 'Mark Served ★', nextStatus: 'SERVED' },
}

function ElapsedTimer({ order }: { order: KitchenOrder }) {
  const [elapsed, setElapsed] = useState(0)
  const isReady = order.status === 'READY'
  const estMins = isReady ? 3 : (order.estimated_prep_time_minutes || 15)
  const estSeconds = estMins * 60

  useEffect(() => {
    const startFrom = isReady ? (order.ready_at || order.placed_at) : (order.preparation_started_at || order.placed_at)
    const endAt = order.served_at || (isReady ? null : order.ready_at) || null

    const update = () => {
      setElapsed(elapsedSeconds(startFrom, endAt))
    }
    update()
    if (endAt) return
    const id = setInterval(update, 1000)
    return () => clearInterval(id)
  }, [order.placed_at, order.preparation_started_at, order.ready_at, order.served_at, isReady])

  const isLate = order.status !== 'SERVED' && elapsed > estSeconds
  const overdueMins = Math.floor((elapsed - estSeconds) / 60)
  const remainingSeconds = Math.max(0, estSeconds - elapsed)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
      <span
        style={{
          fontSize: '0.74rem',
          color: '#64748b',
          fontWeight: 600,
          background: 'rgba(0,0,0,0.04)',
          padding: '2px 6px',
          borderRadius: '4px',
        }}
        title={`Placed at ${formatTime(order.placed_at)}`}
      >
        📥 {formatTime(order.placed_at) || 'Just now'}
      </span>
      {isReady ? (
        <span
          style={{
            fontSize: '0.74rem',
            color: isLate ? '#b91c1c' : '#15803d',
            fontWeight: 700,
            background: isLate ? '#fee2e2' : '#dcfce7',
            padding: '2px 6px',
            borderRadius: '4px',
            border: isLate ? '1px solid #f87171' : '1px solid #bbf7d0',
          }}
          title="Serve target window: 3 minutes"
        >
          {isLate
            ? `⚠️ Overdue +${overdueMins}m`
            : `⏳ Serve within 3m (${formatElapsed(remainingSeconds)} left)`}
        </span>
      ) : (
        <span
          style={{
            fontSize: '0.74rem',
            color: '#0369a1',
            fontWeight: 600,
            background: '#e0f2fe',
            padding: '2px 6px',
            borderRadius: '4px',
          }}
          title="Estimated food preparation duration"
        >
          ⏳ Est: {estMins}m
        </span>
      )}
      <span
        className={`kds-elapsed-badge ${isLate ? 'is-late' : elapsed > estSeconds * 0.75 ? 'is-warning' : ''}`}
        title={isReady ? 'Duration waiting for waiter pickup' : 'Elapsed preparation duration'}
        style={isLate ? { animation: 'pulse 1.5s infinite', background: '#fee2e2', color: '#b91c1c', border: '1px solid #f87171', fontWeight: 800 } : {}}
      >
        ⏱ {formatElapsed(elapsed)} {isLate ? `(🚨 +${overdueMins}m late)` : ''}
      </span>
    </div>
  )
}

interface OrderCardProps {
  order: KitchenOrder
  selectedStation: KitchenStation
  onCardClick: (order: KitchenOrder) => void
  onQuickAction: (orderId: string, nextStatus: string) => void
  busy: boolean
}

function getStationTagClass(st?: string | null): string {
  if (!st) return 'station-tag--main'
  const s = st.toUpperCase()
  if (s.includes('NORTH')) return 'station-tag--north'
  if (s.includes('SOUTH')) return 'station-tag--south'
  if (s.includes('TANDOOR') || s.includes('GRILL')) return 'station-tag--grill'
  if (s.includes('CHINESE') || s.includes('WOK') || s.includes('ASIAN') || s.includes('FRY')) return 'station-tag--asian'
  if (s.includes('PIZZA') || s.includes('ITALIAN')) return 'station-tag--pizza'
  if (s.includes('BAR') || s.includes('DRINK')) return 'station-tag--bar'
  if (s.includes('DESSERT') || s.includes('SWEET')) return 'station-tag--dessert'
  return 'station-tag--main'
}

function OrderCard({ order, selectedStation, onCardClick, onQuickAction, busy }: OrderCardProps) {
  const [confirmingNext, setConfirmingNext] = useState(false)
  const cfg = STATUS_CONFIG[order.status] ?? STATUS_CONFIG.RECEIVED
  const next = NEXT_ACTION[order.status]
  const srcKey = (order.source || 'WAITER').toUpperCase()
  const src = SOURCE_LABELS[srcKey] ?? SOURCE_LABELS.WAITER

  const estMins = order.estimated_prep_time_minutes || 15
  const isOverdue = order.status !== 'SERVED' && elapsedSeconds(order.preparation_started_at || order.placed_at, order.ready_at || order.served_at) > estMins * 60

  const items = order.items || []
  const totalItemCount = items.reduce((sum: number, i: any) => sum + (i.quantity || 1), 0)

  return (
    <div
      className={`kds-order-card kds-order-card--${order.status.toLowerCase()} ${isOverdue ? 'is-overdue' : ''}`}
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
        {order.notes && (
          <div className="kds-order-card__table-instructions">
            <span className="kds-order-card__table-notes-icon">📝</span>
            <div className="kds-order-card__table-notes-text">
              <strong>Chef Instructions:</strong> {order.notes}
            </div>
          </div>
        )}
        <div className="kds-order-card__item-list">
          {items.map((item: any, idx: number) => {
            const displayStation = getItemDisplayStation(item)
            const isStationMatch =
              selectedStation !== 'ALL' && matchItemStation(item, selectedStation)
            const isOtherStation = selectedStation !== 'ALL' && !isStationMatch

            return (
              <div
                key={item.id || idx}
                className={`kds-order-card__item-row ${
                  isStationMatch
                    ? 'kds-order-card__item-row--station-match'
                    : isOtherStation
                    ? 'kds-order-card__item-row--other-station'
                    : ''
                }`}
              >
                <div className="kds-order-card__item-main">
                  <span className="kds-order-card__item-qty">{item.quantity}×</span>
                  <span className="kds-order-card__item-name">{item.item_name}</span>
                  {isStationMatch && (
                    <span className="kds-order-card__prep-badge">🔥 Prep</span>
                  )}
                  <span
                    className={`kds-order-card__station-tag ${getStationTagClass(displayStation)}`}
                  >
                    {displayStation}
                  </span>
                </div>

                {/* Preparation Note from customer/staff */}
                {item.notes && (
                  <div className="kds-order-card__item-notes">
                    <span>📝</span>
                    <span><strong>Note:</strong> {item.notes}</span>
                  </div>
                )}

                {/* Allergy Flag Alert */}
                {item.allergy_flag && (
                  <div className="kds-order-card__allergy-badge">
                    <span>⚠️ Allergen Alert</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      <div className="kds-order-card__footer">
        <span className="kds-order-card__count-hint">
          {totalItemCount} item{totalItemCount !== 1 ? 's' : ''} total
        </span>
        {next && (
          !confirmingNext ? (
            <button
              type="button"
              className="kds-order-card__action-btn"
              style={{ background: cfg.color }}
              disabled={busy}
              onClick={(e) => {
                e.stopPropagation()
                setConfirmingNext(true)
              }}
            >
              {busy ? 'Updating…' : next.label}
            </button>
          ) : (
            <div style={{ display: 'flex', gap: '4px' }}>
              <button
                type="button"
                className="kds-order-card__action-btn"
                style={{ background: '#16a34a', color: '#fff', fontWeight: 700 }}
                disabled={busy}
                onClick={(e) => {
                  e.stopPropagation()
                  onQuickAction(order.id, next.nextStatus)
                  setConfirmingNext(false)
                }}
              >
                {busy ? 'Updating…' : `Confirm: ${next.nextStatus}? ✓`}
              </button>
              <button
                type="button"
                className="kds-order-card__action-btn"
                style={{ background: '#e2e8f0', color: '#475569', padding: '0 8px' }}
                onClick={(e) => {
                  e.stopPropagation()
                  setConfirmingNext(false)
                }}
              >
                ✕
              </button>
            </div>
          )
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
  const filteredOrders =
    station === 'ALL'
      ? orders
      : orders.filter((order) =>
          (order.items || []).some((item: any) => matchItemStation(item, station)),
        )

  const receivingCount = orders.filter((o) => o.status === 'RECEIVED' || o.status === 'CONFIRMED').length
  const preparingCount = orders.filter((o) => o.status === 'PREPARING').length
  const readyCount = orders.filter((o) => o.status === 'READY').length

  const overdueOrders = useMemo(() => {
    return orders.filter((o) => {
      if (o.status === 'SERVED') return false
      const estSec = (o.estimated_prep_time_minutes || 15) * 60
      const el = elapsedSeconds(o.preparation_started_at || o.placed_at, o.ready_at || o.served_at)
      return el > estSec
    })
  }, [orders])

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

      {/* Overdue Chef Alert Banner */}
      {overdueOrders.length > 0 && (
        <div className="kds-overdue-alert-banner" role="alert">
          <span className="kds-overdue-icon">🚨</span>
          <div className="kds-overdue-content">
            <strong>CHEF ATTENTION: {overdueOrders.length} Order{overdueOrders.length > 1 ? 's' : ''} OVERDUE!</strong>
            <span>
              {overdueOrders.map(o => `Table ${o.table_number || o.table_id} (#${o.id.slice(-6).toUpperCase()})`).join(', ')} exceeded preparation time. Expedite now!
            </span>
          </div>
        </div>
      )}

      {actionError && (
        <div className="kds-alert-banner kds-alert-banner--error" role="alert">
          <span>⚠️ {actionError}</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => setActionError(null)}>
            Dismiss
          </button>
        </div>
      )}

      {/* Main Kitchen Workspace: Vertical Station Sidebar + Orders Area */}
      <div className="kds-main-layout">
        <aside className="kds-station-sidebar">
          <StationFilter
            selectedStation={station}
            onStationChange={setStation}
            orders={orders}
            layout="vertical"
          />
        </aside>

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
                  selectedStation={station}
                  onCardClick={setSelectedOrder}
                  onQuickAction={handleStatusChange}
                  busy={busyIds.has(order.id)}
                />
              ))}
            </div>
          )}
        </main>
      </div>

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
