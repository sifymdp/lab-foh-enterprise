import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ordersApi, type Order } from '../api/extensions'
import { useSocket } from '../context/SocketContext'
import { formatTime } from '../lib/formatters'
import { PhoneFrameContainer } from '../components/common/PhoneFrameContainer'

function ReadyServeTimer({ readyAt }: { readyAt?: string | null }) {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  const readyMs = readyAt ? new Date(readyAt).getTime() : now
  const validReadyMs = isNaN(readyMs) ? now : readyMs
  const elapsedSeconds = Math.max(0, Math.floor((now - validReadyMs) / 1000))
  const targetSeconds = 3 * 60 // 3 minutes = 180s
  const remainingSeconds = targetSeconds - elapsedSeconds

  if (remainingSeconds > 0) {
    const mins = Math.floor(remainingSeconds / 60)
    const secs = remainingSeconds % 60
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          fontWeight: 700,
          color: remainingSeconds <= 60 ? '#d97706' : '#15803d',
          fontSize: '0.8rem',
        }}
      >
        <span>⏳ Serve within: {mins}:{secs.toString().padStart(2, '0')}</span>
      </span>
    )
  }

  const overdueSecs = Math.abs(remainingSeconds)
  const overdueMins = Math.floor(overdueSecs / 60)
  const overdueRemSecs = overdueSecs % 60
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '4px',
        fontWeight: 800,
        color: '#b91c1c',
        fontSize: '0.8rem',
      }}
    >
      <span>⚠️ Overdue +{overdueMins}m {overdueRemSecs.toString().padStart(2, '0')}s</span>
    </span>
  )
}

function ReadyFoodCard({
  order,
  onMarkServed,
  isLoading,
}: {
  order: Order
  onMarkServed: (orderId: string, tableNumber?: string | null) => void
  isLoading: boolean
}) {
  const tableNum =
    order.tableNumber ||
    (order as any).table_number ||
    (order.tableId ? String(order.tableId).replace('tbl-', '').replace('t-', '') : 'N/A')

  return (
    <div
      style={{
        background: '#f0fdf4',
        border: '2px solid #22c55e',
        borderRadius: '12px',
        padding: '12px 14px',
        marginBottom: '10px',
        boxShadow: '0 4px 12px rgba(34, 197, 94, 0.15)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.3rem' }}>🛎️</span>
          <div>
            <strong style={{ fontSize: '1.05rem', color: '#14532d' }}>Table {tableNum}</strong>
            <div style={{ fontSize: '0.72rem', color: '#166534', fontWeight: 700 }}>Food Ready to Serve!</div>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <ReadyServeTimer readyAt={order.readyAt || (order as any).ready_at || order.placedAt} />
          <div style={{ fontSize: '0.68rem', color: '#4b5563', marginTop: '2px' }}>Estimate: 3 mins</div>
        </div>
      </div>

      <div
        style={{
          background: '#ffffff',
          borderRadius: '8px',
          padding: '8px 10px',
          marginBottom: '10px',
          border: '1px solid #bbf7d0',
          fontSize: '0.78rem',
          color: '#374151',
        }}
      >
        <div style={{ fontWeight: 600, color: '#1e293b', marginBottom: '4px' }}>Items to Serve:</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {(order.items || []).map((it, idx) => (
            <span
              key={idx}
              style={{
                background: '#e0f2fe',
                color: '#0369a1',
                borderRadius: '6px',
                padding: '2px 8px',
                fontWeight: 600,
                fontSize: '0.75rem',
              }}
            >
              {it.quantity}× {it.itemName}
            </span>
          ))}
        </div>
        {order.notes && (
          <div style={{ fontSize: '0.72rem', color: '#6b7280', marginTop: '4px', fontStyle: 'italic' }}>
            Note: {order.notes}
          </div>
        )}
      </div>

      <button
        type="button"
        disabled={isLoading}
        onClick={() => onMarkServed(order.id, tableNum)}
        style={{
          width: '100%',
          padding: '10px',
          borderRadius: '8px',
          background: '#16a34a',
          color: '#ffffff',
          border: 'none',
          fontWeight: 800,
          fontSize: '0.88rem',
          cursor: isLoading ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          boxShadow: '0 2px 6px rgba(22, 163, 74, 0.3)',
          transition: 'all 0.15s ease',
        }}
      >
        {isLoading ? 'Updating...' : '✓ Mark as Served'}
      </button>
    </div>
  )
}

export function WaiterDashboard() {
  const navigate = useNavigate()
  const { on } = useSocket()

  const [activeTab, setActiveTab] = useState<'pending' | 'tables' | 'kitchen'>('pending')
  const [tableFilter, setTableFilter] = useState<'ALL' | 'AVAILABLE' | 'OCCUPIED' | 'BILLING'>('ALL')
  const [assignedTables, setAssignedTables] = useState<any[]>([])
  const [pendingOrders, setPendingOrders] = useState<Order[]>([])
  const [recentOrders, setRecentOrders] = useState<Order[]>([])
  const [loadingTables, setLoadingTables] = useState(false)
  const [loadingOrders, setLoadingOrders] = useState(false)
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const readyOrders = useMemo(
    () => recentOrders.filter((o) => o.status === 'READY'),
    [recentOrders]
  )

  const playReadyChime = useCallback(() => {
    try {
      const AudioCtx = window.AudioContext || (window as any).webkitAudioContext
      if (!AudioCtx) return
      const ctx = new AudioCtx()
      const osc = ctx.createOscillator()
      const gain = ctx.createGain()
      osc.type = 'sine'
      osc.frequency.setValueAtTime(587.33, ctx.currentTime) // D5
      osc.frequency.setValueAtTime(880, ctx.currentTime + 0.12) // A5
      gain.gain.setValueAtTime(0.25, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5)
      osc.connect(gain)
      gain.connect(ctx.destination)
      osc.start()
      osc.stop(ctx.currentTime + 0.5)
    } catch {
      // Audio autoplay policy
    }
  }, [])

  const showToast = (text: string, type: 'success' | 'error' = 'success') => {
    setStatusMessage({ text, type })
    setTimeout(() => setStatusMessage(null), 4000)
  }

  const fetchTables = useCallback(async () => {
    try {
      setLoadingTables(true)
      const res = await api.getFloor()
      setAssignedTables(res.tables || [])
    } catch (err) {
      console.error('Failed to load floor tables', err)
    } finally {
      setLoadingTables(false)
    }
  }, [])

  const fetchOrders = useCallback(async () => {
    try {
      setLoadingOrders(true)
      const [pending, all] = await Promise.all([
        ordersApi.list({ approvalStatus: 'PENDING' }),
        ordersApi.list(),
      ])
      setPendingOrders(pending || [])
      setRecentOrders((all || []).filter((o) => o.approvalStatus === 'APPROVED' && o.status !== 'CANCELLED'))
    } catch (err) {
      console.error('Failed to load orders', err)
    } finally {
      setLoadingOrders(false)
    }
  }, [])

  useEffect(() => {
    fetchTables()
    fetchOrders()

    const interval = setInterval(() => {
      fetchOrders()
    }, 8000)
    return () => clearInterval(interval)
  }, [fetchTables, fetchOrders])

  // Real-time socket listeners
  useEffect(() => {
    const unsub1 = on('order.pending_approval', (data: any) => {
      fetchOrders()
      showToast(`🔔 New Order from Table ${data?.tableNumber || data?.tableId || ''} awaiting approval!`)
    })
    const unsub2 = on('order.approved', () => fetchOrders())
    const unsub3 = on('order.rejected', () => fetchOrders())
    const unsub4 = on('order_placed', () => fetchOrders())
    const unsub5 = on('order_status_updated', (data: any) => {
      fetchOrders()
      if (data?.status === 'READY') {
        playReadyChime()
        showToast(`🍽️ FOOD READY: Table ${data?.tableNumber || data?.tableId || ''} is ready to serve! Please collect within 3 mins.`, 'success')
      }
    })
    const unsub6 = on('table_updated', () => fetchTables())
    const unsub7 = on('ai_alert', (data: any) => {
      if (data?.eventType === 'FOOD_READY') {
        playReadyChime()
        showToast(`🍽️ FOOD READY: ${data.message || 'Food is ready to serve! (Estimate: 3 mins)'}`, 'success')
        fetchOrders()
      } else if (data?.eventType === 'FOOD_WAITING') {
        showToast(`⚠️ FOOD OVERDUE: ${data.message}`, 'error')
        fetchOrders()
      }
    })
    const unsub8 = on('food_ready', (data: any) => {
      playReadyChime()
      showToast(`🍽️ FOOD READY: Table ${data?.tableNumber || data?.tableId || ''} is ready! Please collect and serve within 3 mins.`, 'success')
      fetchOrders()
    })

    return () => {
      unsub1()
      unsub2()
      unsub3()
      unsub4()
      unsub5()
      unsub6()
      unsub7()
      unsub8()
    }
  }, [on, fetchOrders, fetchTables, playReadyChime])

  const handleMarkServed = async (orderId: string, tableNumber?: string | null) => {
    setActionLoadingId(orderId)
    try {
      await ordersApi.updateStatus(orderId, 'SERVED')
      showToast(`✓ Table ${tableNumber || ''} order marked as SERVED!`, 'success')
      await fetchOrders()
      await fetchTables()
    } catch (err: any) {
      showToast(err?.message || 'Failed to update order status', 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleApprove = async (orderId: string, tableNumber?: string | null) => {
    setActionLoadingId(orderId)
    try {
      await ordersApi.approve(orderId)
      showToast(`✓ Order approved for Table ${tableNumber || ''}! Dispatched to Kitchen.`, 'success')
      await fetchOrders()
      await fetchTables()
    } catch (err: any) {
      showToast(err?.message || 'Failed to approve order', 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleReject = async (orderId: string, tableNumber?: string | null) => {
    const reason = window.prompt(
      `Reject order for Table ${tableNumber || ''}?\nEnter rejection reason:`,
      'Item temporarily unavailable'
    )
    if (reason === null) return

    setActionLoadingId(orderId)
    try {
      await ordersApi.reject(orderId, reason)
      showToast(`Order rejected for Table ${tableNumber || ''}.`, 'error')
      await fetchOrders()
      await fetchTables()
    } catch (err: any) {
      showToast(err?.message || 'Failed to reject order', 'error')
    } finally {
      setActionLoadingId(null)
    }
  }

  const filteredTables = assignedTables.filter((t) => {
    if (tableFilter === 'AVAILABLE') return t.status === 'AVAILABLE'
    if (tableFilter === 'OCCUPIED') return ['ACTIVE', 'SEATED', 'OCCUPIED'].includes(t.status)
    if (tableFilter === 'BILLING') return t.status === 'BILLING'
    return true
  })

  return (
    <PhoneFrameContainer
      title="Waiter Mobile Stand"
      roleSubtitle="Table Service & Live Order Approvals"
      roleBadge="WAITER"
      badgeColor="#c2410c"
      onRefresh={() => {
        fetchOrders()
        fetchTables()
      }}
      activeTabCount={pendingOrders.length}
    >
      {/* Toast Alert Banner */}
      {statusMessage && (
        <div
          style={{
            position: 'sticky',
            top: '8px',
            zIndex: 9999,
            padding: '10px 14px',
            borderRadius: '8px',
            fontWeight: 700,
            fontSize: '0.82rem',
            marginBottom: '10px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
            background: statusMessage.type === 'success' ? '#15803d' : '#b91c1c',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
        >
          <span>{statusMessage.text}</span>
          <button
            onClick={() => setStatusMessage(null)}
            style={{ background: 'none', border: 'none', color: '#fff', fontSize: '1rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>
      )}

      {/* ─── READY TO SERVE BANNER / QUEUE ─── */}
      {readyOrders.length > 0 && (
        <div style={{ marginBottom: '1.2rem' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 12px',
              background: '#dcfce7',
              border: '1.5px solid #22c55e',
              borderRadius: '10px',
              marginBottom: '8px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ fontSize: '1.1rem' }}>🛎️</span>
              <strong style={{ fontSize: '0.85rem', color: '#15803d' }}>
                Food Ready to Serve ({readyOrders.length})
              </strong>
            </div>
            <span style={{ fontSize: '0.72rem', color: '#166534', fontWeight: 700 }}>
              Target: 3 mins
            </span>
          </div>

          {readyOrders.map((ro) => (
            <ReadyFoodCard
              key={ro.id}
              order={ro}
              isLoading={actionLoadingId === ro.id}
              onMarkServed={handleMarkServed}
            />
          ))}
        </div>
      )}

      {/* ─── SEGMENTED PHONE TABS BAR ─── */}
      <div
        style={{
          display: 'flex',
          background: 'var(--surface-2)',
          borderRadius: '12px',
          padding: '4px',
          marginBottom: '1rem',
          border: '1px solid var(--border)',
          gap: '4px',
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab('pending')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'pending' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'pending' ? '#ffffff' : 'transparent',
            color: activeTab === 'pending' ? '#c2410c' : 'var(--text-muted)',
            boxShadow: activeTab === 'pending' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>🔔 Approvals</span>
          {pendingOrders.length > 0 && (
            <span
              style={{
                background: '#dc2626',
                color: '#ffffff',
                fontSize: '0.68rem',
                fontWeight: 800,
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              {pendingOrders.length}
            </span>
          )}
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('tables')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'tables' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'tables' ? '#ffffff' : 'transparent',
            color: activeTab === 'tables' ? '#0f172a' : 'var(--text-muted)',
            boxShadow: activeTab === 'tables' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>🍽️ Tables</span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-soft)' }}>
            ({assignedTables.length})
          </span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('kitchen')}
          style={{
            flex: 1,
            padding: '8px 4px',
            border: 'none',
            borderRadius: '9px',
            fontSize: '0.82rem',
            fontWeight: activeTab === 'kitchen' ? 800 : 600,
            cursor: 'pointer',
            background: activeTab === 'kitchen' ? '#ffffff' : 'transparent',
            color: activeTab === 'kitchen' ? '#0f172a' : 'var(--text-muted)',
            boxShadow: activeTab === 'kitchen' ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            transition: 'all 0.15s ease',
          }}
        >
          <span>🍳 Kitchen</span>
          {readyOrders.length > 0 ? (
            <span
              style={{
                background: '#16a34a',
                color: '#ffffff',
                fontSize: '0.68rem',
                fontWeight: 800,
                padding: '1px 6px',
                borderRadius: '10px',
              }}
            >
              🛎️ {readyOrders.length} Ready
            </span>
          ) : recentOrders.length > 0 ? (
            <span style={{ fontSize: '0.72rem', color: '#16a34a', fontWeight: 700 }}>
              ({recentOrders.length})
            </span>
          ) : null}
        </button>
      </div>

      {/* ─── TAB 1: PENDING ORDERS AWAITING WAITER APPROVAL ─── */}
      {activeTab === 'pending' && (
        <div>
          {pendingOrders.length > 0 && (
            <div
              style={{
                background: '#fef3c7',
                border: '1px solid #fde68a',
                borderRadius: '8px',
                padding: '8px 12px',
                marginBottom: '10px',
                fontSize: '0.8rem',
                color: '#92400e',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>⚠️ Review guest orders before kitchen prep</span>
              <span style={{ fontWeight: 800 }}>{pendingOrders.length} pending</span>
            </div>
          )}

          {loadingOrders && pendingOrders.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem 0' }}>
              Checking for pending orders...
            </p>
          ) : pendingOrders.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '2.5rem 1rem',
                background: '#ffffff',
                borderRadius: '14px',
                border: '1px dashed var(--border)',
              }}
            >
              <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>✅</div>
              <strong style={{ display: 'block', fontSize: '1rem', color: 'var(--text)', marginBottom: '4px' }}>
                All Clear!
              </strong>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem', maxWidth: '300px', margin: '0 auto' }}>
                No customer orders currently awaiting approval. When a guest orders via QR code, it pops up right here!
              </p>
              <div style={{ marginTop: '1.25rem' }}>
                <button
                  type="button"
                  onClick={() => setActiveTab('tables')}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.82rem', padding: '6px 14px' }}
                >
                  View Dining Tables Overview →
                </button>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {pendingOrders.map((order) => {
                const tableNum =
                  order.tableNumber ||
                  (order as any).table_number ||
                  (order.tableId ? String(order.tableId).replace('tbl-', '').replace('t-', '') : 'N/A')
                const itemCount = (order.items || []).reduce((acc, i) => acc + (i.quantity || 1), 0)
                const totalAmount = (order.items || []).reduce(
                  (acc, i) => acc + (i.unitPrice || (i as any).unit_price || 0) * (i.quantity || 1),
                  0
                )
                const isSubmitting = actionLoadingId === order.id

                return (
                  <div
                    key={order.id}
                    style={{
                      background: '#ffffff',
                      borderRadius: '14px',
                      border: '1.5px solid #fde68a',
                      padding: '12px',
                      boxShadow: '0 2px 6px rgba(0,0,0,0.05)',
                    }}
                  >
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span
                          style={{
                            background: '#0284c7',
                            color: '#ffffff',
                            fontWeight: 800,
                            padding: '3px 8px',
                            borderRadius: '6px',
                            fontSize: '0.85rem',
                          }}
                        >
                          Table {tableNum}
                        </span>
                        <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                          {formatTime(order.placedAt || (order as any).placed_at) || 'Just now'}
                        </span>
                      </div>
                      <span
                        style={{
                          background: '#fef3c7',
                          color: '#92400e',
                          fontWeight: 700,
                          fontSize: '0.7rem',
                          padding: '2px 6px',
                          borderRadius: '4px',
                        }}
                      >
                        QR GUEST
                      </span>
                    </div>

                    {/* Customer Notes */}
                    {order.notes && (
                      <div
                        style={{
                          background: '#fef2f2',
                          border: '1px solid #fecaca',
                          borderRadius: '6px',
                          padding: '5px 8px',
                          fontSize: '0.78rem',
                          color: '#991b1b',
                          marginBottom: '8px',
                        }}
                      >
                        <strong>Note:</strong> {order.notes}
                      </div>
                    )}

                    {/* Items List */}
                    <div
                      style={{
                        background: 'var(--surface-2)',
                        borderRadius: '8px',
                        padding: '8px 10px',
                        marginBottom: '10px',
                      }}
                    >
                      <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '4px' }}>
                        ITEMS ({itemCount}):
                      </div>
                      {(order.items || []).map((item, idx) => (
                        <div
                          key={item.id || idx}
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'flex-start',
                            fontSize: '0.82rem',
                            padding: '3px 0',
                            borderBottom: idx < (order.items || []).length - 1 ? '1px dashed var(--border)' : 'none',
                          }}
                        >
                          <div style={{ flex: 1, paddingRight: '6px' }}>
                            <strong style={{ color: '#1e293b', marginRight: '4px' }}>{item.quantity}×</strong>
                            <span>{item.itemName || (item as any).item_name}</span>
                            {item.notes && (
                              <div style={{ fontSize: '0.72rem', color: '#d97706', fontStyle: 'italic' }}>
                                ↳ {item.notes}
                              </div>
                            )}
                          </div>
                          <span style={{ fontWeight: 600, color: '#475569', fontSize: '0.8rem' }}>
                            ₹{(((item.unitPrice || (item as any).unit_price || 0) * (item.quantity || 1))).toFixed(2)}
                          </span>
                        </div>
                      ))}
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginTop: '6px',
                          paddingTop: '6px',
                          borderTop: '1px solid var(--border)',
                        }}
                      >
                        <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Total</span>
                        <strong style={{ fontSize: '0.95rem', color: '#0f172a' }}>₹{totalAmount.toFixed(2)}</strong>
                      </div>
                    </div>

                    {/* Action Buttons - Large Touch Targets */}
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        style={{
                          flex: 2,
                          background: '#16a34a',
                          borderColor: '#16a34a',
                          padding: '10px 12px',
                          fontSize: '0.85rem',
                          fontWeight: 700,
                          borderRadius: '8px',
                          minHeight: '44px',
                        }}
                        disabled={isSubmitting}
                        onClick={() => handleApprove(order.id, tableNum)}
                      >
                        {isSubmitting ? 'Approving...' : '✓ Approve & Send to Kitchen'}
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        style={{
                          flex: 1,
                          borderColor: '#dc2626',
                          color: '#dc2626',
                          padding: '10px 8px',
                          fontSize: '0.82rem',
                          borderRadius: '8px',
                          minHeight: '44px',
                        }}
                        disabled={isSubmitting}
                        onClick={() => handleReject(order.id, tableNum)}
                      >
                        ✕ Reject
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* ─── TAB 2: DINING TABLES OVERVIEW ─── */}
      {activeTab === 'tables' && (
        <div>
          {/* Quick Filter Pills */}
          <div style={{ display: 'flex', gap: '6px', overflowX: 'auto', paddingBottom: '8px', marginBottom: '10px' }}>
            {(['ALL', 'AVAILABLE', 'OCCUPIED', 'BILLING'] as const).map((filter) => (
              <button
                key={filter}
                type="button"
                onClick={() => setTableFilter(filter)}
                style={{
                  padding: '5px 11px',
                  borderRadius: '999px',
                  border: '1px solid',
                  borderColor: tableFilter === filter ? 'var(--primary)' : 'var(--border)',
                  background: tableFilter === filter ? 'var(--primary-soft)' : '#ffffff',
                  color: tableFilter === filter ? 'var(--primary)' : 'var(--text-muted)',
                  fontSize: '0.75rem',
                  fontWeight: 600,
                  whiteSpace: 'nowrap',
                  cursor: 'pointer',
                }}
              >
                {filter === 'ALL' ? 'All Tables' : filter.charAt(0) + filter.slice(1).toLowerCase()}
              </button>
            ))}
          </div>

          {loadingTables ? (
            <p style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '2rem 0' }}>Loading tables...</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
              {filteredTables.map((t) => {
                const isOccupied = ['ACTIVE', 'SEATED', 'OCCUPIED'].includes(t.status)
                const isBilling = t.status === 'BILLING'
                const isCleaning = t.status === 'CLEANING'

                return (
                  <div
                    key={t.id}
                    onClick={() => navigate('/floor')}
                    style={{
                      background: isBilling ? '#fffbeb' : isOccupied ? '#f0fdf4' : isCleaning ? '#f3f4f6' : '#ffffff',
                      border: isBilling ? '1.5px solid #f59e0b' : isOccupied ? '1.5px solid #22c55e' : '1px solid var(--border)',
                      borderRadius: '12px',
                      padding: '12px 10px',
                      textAlign: 'center',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      minHeight: '90px',
                    }}
                  >
                    <div>
                      <strong style={{ fontSize: '1rem', color: '#0f172a' }}>Table {t.number}</strong>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        Cap: {t.capacity} guests
                      </div>
                    </div>
                    <div style={{ marginTop: '8px' }}>
                      <span
                        className={`role-badge role-${(t.status || 'available').toLowerCase()}`}
                        style={{ fontSize: '0.68rem', padding: '3px 8px', borderRadius: '4px' }}
                      >
                        {t.status}
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          <div style={{ marginTop: '1rem', textAlign: 'center' }}>
            <Link
              to="/floor"
              className="btn btn-secondary btn-block"
              style={{ textDecoration: 'none', fontSize: '0.85rem', padding: '10px' }}
            >
              Open Full Interactive Seating Plan ◫
            </Link>
          </div>
        </div>
      )}

      {/* ─── TAB 3: KITCHEN TRACKER ─── */}
      {activeTab === 'kitchen' && (
        <div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginBottom: '10px' }}>
            Live kitchen preparation tracker for floor service:
          </div>

          {recentOrders.length === 0 ? (
            <div
              style={{
                textAlign: 'center',
                padding: '2.5rem 1rem',
                background: '#ffffff',
                borderRadius: '14px',
                border: '1px dashed var(--border)',
              }}
            >
              <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>👨‍🍳</div>
              <strong style={{ display: 'block', fontSize: '0.95rem' }}>No Active Kitchen Orders</strong>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                When you approve orders, they will appear here as they are prepared by the chef.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentOrders.map((ro) => {
                const tableNum =
                  ro.tableNumber ||
                  (ro as any).table_number ||
                  (ro.tableId ? String(ro.tableId).replace('tbl-', '').replace('t-', '') : 'N/A')
                const isReady = ro.status === 'READY'
                const isPreparing = ro.status === 'PREPARING'

                return (
                  <div
                    key={ro.id}
                    style={{
                      background: isReady ? '#f0fdf4' : '#ffffff',
                      border: isReady ? '1.5px solid #22c55e' : '1px solid var(--border)',
                      borderRadius: '10px',
                      padding: '10px 12px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
                        <strong style={{ fontSize: '0.9rem' }}>Table {tableNum}</strong>
                        {isReady ? (
                          <span
                            style={{
                              background: '#dcfce7',
                              color: '#15803d',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.72rem',
                              fontWeight: 700,
                            }}
                          >
                            🛎️ READY TO SERVE
                          </span>
                        ) : (
                          <span
                            style={{
                              background: isPreparing ? '#dbeafe' : '#fef3c7',
                              color: isPreparing ? '#1d4ed8' : '#b45309',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              fontSize: '0.7rem',
                              fontWeight: 700,
                            }}
                          >
                            {ro.status}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {(ro.items || []).length} items • {formatTime(ro.placedAt || (ro as any).placed_at)}
                      </div>
                      {isReady && (
                        <div style={{ marginTop: '4px' }}>
                          <ReadyServeTimer readyAt={ro.readyAt || (ro as any).ready_at || ro.placedAt} />
                        </div>
                      )}
                    </div>
                    {isReady ? (
                      <button
                        type="button"
                        disabled={actionLoadingId === ro.id}
                        onClick={() => handleMarkServed(ro.id, tableNum)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          background: '#16a34a',
                          color: '#ffffff',
                          border: 'none',
                          fontWeight: 700,
                          fontSize: '0.78rem',
                          cursor: actionLoadingId === ro.id ? 'not-allowed' : 'pointer',
                          whiteSpace: 'nowrap',
                          boxShadow: '0 2px 4px rgba(22, 163, 74, 0.25)',
                        }}
                      >
                        {actionLoadingId === ro.id ? 'Saving...' : '✓ Serve'}
                      </button>
                    ) : (
                      <span
                        style={{
                          fontSize: '0.72rem',
                          color: 'var(--text-muted)',
                        }}
                      >
                        {isPreparing ? 'Cooking...' : 'Queued'}
                      </span>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}

      {/* Quick Bottom Bar on Mobile */}
      <div
        style={{
          marginTop: '1.5rem',
          paddingTop: '1rem',
          borderTop: '1px solid var(--border)',
          display: 'flex',
          justifyContent: 'space-around',
        }}
      >
        <Link
          to="/floor"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>◫</span>
          <span>Seating Plan</span>
        </Link>
        <Link
          to="/billing"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>$</span>
          <span>Bills / POS</span>
        </Link>
        <Link
          to="/kitchen"
          style={{ textDecoration: 'none', color: 'var(--text-muted)', fontSize: '0.78rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}
        >
          <span style={{ fontSize: '1.2rem' }}>🍳</span>
          <span>Kitchen KDS</span>
        </Link>
      </div>
    </PhoneFrameContainer>
  )
}
