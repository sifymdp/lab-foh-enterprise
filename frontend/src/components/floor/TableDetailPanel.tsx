import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/client'
import { ordersApi, type Order } from '../../api/extensions'
import { useAuth } from '../../context/AuthContext'
import { useFloor } from '../../context/FloorContext'
import { ConfirmDialog } from '../ui/ConfirmDialog'
import { canEditFloor, canSeatGuests } from '../../lib/permissions'
import { STATUS_CONFIG } from '../../services/tableConfig'
import type { Floor, Table, TableType, BillDetail } from '../../types'
import { OccupancyTimer } from './OccupancyTimer'
import { PrintQRButton } from './PrintQRButton'
import { StatusActions } from './StatusActions'

interface TableDetailPanelProps {
  floor: Floor
  table: Table
  hasWaiterCall?: boolean
  waiterCallState?: 'CALLING' | 'ON_IT' | boolean
  hasCashCall?: boolean
  cashCallState?: 'CALLING' | 'ON_IT' | boolean
  cashCallInfo?: { guestName?: string; amount?: number; message?: string }
  reservation?: { id: string; guestName: string; partySize: number; reservedFor: string }
  onDismissWaiterCall?: () => void
  onOnItWaiterCall?: () => void
  onResolveWaiterCall?: () => void
  onOnItCashCall?: () => void
  onResolveCashCall?: () => void
  onClose: () => void
  onSeatGuests: () => void
  onTakeOrder?: () => void
}

function aggregateItems(orders: Order[]) {
  const map = new Map<string, { name: string; price: number; qty: number; notes?: string }>()
  for (const order of orders) {
    for (const item of order.items) {
      const key = `${item.itemName}-${item.unitPrice}-${item.notes || ''}`
      const existing = map.get(key)
      if (existing) existing.qty += item.quantity
      else map.set(key, { name: item.itemName, price: item.unitPrice, qty: item.quantity, notes: item.notes || undefined })
    }
  }
  return [...map.values()]
}

export function TableDetailPanel({
  floor,
  table,
  hasWaiterCall,
  waiterCallState,
  hasCashCall,
  cashCallState,
  cashCallInfo,
  reservation,
  onDismissWaiterCall,
  onOnItWaiterCall,
  onResolveWaiterCall,
  onOnItCashCall,
  onResolveCashCall,
  onClose,
  onSeatGuests,
  onTakeOrder,
}: TableDetailPanelProps) {
  const navigate = useNavigate()
  const { user } = useAuth()
  const { sessions, changeStatus, closeSession, updateTable, deleteTable, refresh } = useFloor()
  const [statusLoading, setStatusLoading] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [layoutError, setLayoutError] = useState<string | null>(null)
  const [orders, setOrders] = useState<Order[]>([])
  const [ordersLoading, setOrdersLoading] = useState(false)
  const [bill, setBill] = useState<BillDetail | null>(null)
  const [showBill, setShowBill] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [confirmPaid, setConfirmPaid] = useState(false)
  const [billingLoading, setBillingLoading] = useState(false)

  const session = ['AVAILABLE', 'CLEANING', 'MAINTENANCE'].includes(table.status)
    ? null
    : sessions
        .filter(
          (s) =>
            (s.tableId === table.id || (s as any).table_id === table.id) &&
            !s.closedAt &&
            ['SEATED', 'ACTIVE', 'BILLING'].includes(s.status),
        )
        .sort((a, b) => new Date(b.seatedAt).getTime() - new Date(a.seatedAt).getTime())[0] || null
  const section = floor.sections.find((s) => s.id === table.sectionId)
  const editable = user ? canEditFloor(user.role) : false
  const canSeat = user ? canSeatGuests(user.role) : false
  const showOrders = ['ACTIVE', 'BILLING', 'PAID'].includes(table.status)

  useEffect(() => {
    let cancelled = false
    if (!session?.id) {
      setOrders([])
      setOrdersLoading(false)
      return
    }
    setOrdersLoading(true)
    ordersApi.list({ sessionId: session.id })
      .then((data) => { if (!cancelled) setOrders(data) })
      .catch(() => { if (!cancelled) setOrders([]) })
      .finally(() => { if (!cancelled) setOrdersLoading(false) })
    return () => { cancelled = true }
  }, [table.id, session?.id])

  // Fetch or sync real live bill for this table session
  useEffect(() => {
    let cancelled = false
    api.getReadySessions()
      .then((readyList: any[]) => {
        if (cancelled) return
        const match = (readyList || []).find((r: any) => 
          (session?.id && (r.sessionId === session.id || r.session_id === session.id)) ||
          r.tableId === table.id || r.table_id === table.id ||
          String(r.tableNumber || r.table_number) === String(table.number)
        )
        const hasBill = match?.hasBill ?? match?.has_bill
        const billId = match?.billId || match?.bill_id
        if (match && hasBill && billId) {
          api.getBillDetail(billId).then((b: any) => {
            if (!cancelled) setBill(b)
          }).catch(() => {})
        }
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [session?.id, table.id, table.number, table.status])

  const pendingOrders = orders.filter((o) => o.approvalStatus === 'PENDING')
  const approvedOrders = orders.filter((o) => o.approvalStatus !== 'REJECTED')
  const items = aggregateItems(approvedOrders)
  const runningTotal = items.reduce((sum, i) => sum + i.price * i.qty, 0)
  const [actionLoadingId, setActionLoadingId] = useState<string | null>(null)

  const handleApproveOrder = async (orderId: string) => {
    setActionLoadingId(orderId)
    try {
      await ordersApi.approve(orderId)
      setOrders((prev) => prev.map((o) => (o.id === orderId ? { ...o, approvalStatus: 'APPROVED' } : o)))
      await refresh()
    } catch {
      alert('Could not approve order')
    } finally {
      setActionLoadingId(null)
    }
  }

  const handleRejectOrder = async (orderId: string) => {
    const reason = window.prompt('Reason for rejecting order (optional):', 'Item unavailable')
    if (reason === null) return
    setActionLoadingId(orderId)
    try {
      await ordersApi.reject(orderId, reason)
      setOrders((prev) => prev.map((o) => (o.id === orderId ? { ...o, approvalStatus: 'REJECTED' } : o)))
      await refresh()
    } catch {
      alert('Could not reject order')
    } finally {
      setActionLoadingId(null)
    }
  }

  async function handleStatus(next: typeof table.status) {
    setStatusLoading(true)
    setStatusError(null)
    try {
      await changeStatus(table.id, next)
      await refresh()
      if (next === 'BILLING') {
        const ready = await api.getReadySessions().catch(() => [])
        const match = (ready || []).find((r: any) => 
          (session?.id && (r.sessionId === session.id || r.session_id === session.id)) ||
          r.tableId === table.id || r.table_id === table.id ||
          String(r.tableNumber || r.table_number) === String(table.number)
        )
        const targetBillId = match?.billId || match?.bill_id
        if (targetBillId) {
          const b = await api.getBillDetail(targetBillId).catch(() => null)
          if (b) setBill(b)
        }
        ordersApi.list({ tableId: table.id }).then(setOrders).catch(() => {})
      }
    } catch (e: any) {
      const msg = e?.message || 'Status update failed'
      setStatusError(typeof msg === 'string' ? msg : 'Status update failed. Please try again.')
    } finally {
      setStatusLoading(false)
    }
  }

  const handleOpenDedicatedBill = async () => {
    setBillingLoading(true)
    try {
      if (bill?.id) {
        navigate(`/billing/${bill.id}`)
        return
      }
      const ready = await api.getReadySessions().catch(() => [])
      const match = (ready || []).find((r: any) => 
        (session?.id && (r.sessionId === session.id || r.session_id === session.id)) || 
        r.tableId === table.id || r.table_id === table.id ||
        String(r.tableNumber || r.table_number) === String(table.number)
      )
      const targetBillId = match?.billId || match?.bill_id
      if (targetBillId) {
        navigate(`/billing/${targetBillId}`)
        return
      }
      if (session?.id) {
        const created = await api.createBill({ session_id: session.id }).catch(() => null)
        if (created?.id) {
          navigate(`/billing/${created.id}`)
          return
        }
      }
      navigate('/billing')
    } finally {
      setBillingLoading(false)
    }
  }

  const handleViewBill = async () => {
    setBillingLoading(true)
    try {
      if (bill?.id) {
        setShowBill(true)
        return
      }
      const ready = await api.getReadySessions().catch(() => [])
      const match = (ready || []).find((r: any) => 
        (session?.id && (r.sessionId === session.id || r.session_id === session.id)) || 
        r.tableId === table.id || r.table_id === table.id ||
        String(r.tableNumber || r.table_number) === String(table.number)
      )
      const targetBillId = match?.billId || match?.bill_id
      const hasBill = match?.hasBill ?? match?.has_bill
      if (hasBill && targetBillId) {
        const b = await api.getBillDetail(targetBillId)
        setBill(b)
        setShowBill(true)
      } else if (session?.id) {
        const created = await api.createBill({ session_id: session.id })
        setBill(created)
        setShowBill(true)
      }
    } catch {
      handleOpenDedicatedBill()
    } finally {
      setBillingLoading(false)
    }
  }

  const handleMarkPaid = async () => {
    if (!session) return
    setBillingLoading(true)
    try {
      if (bill?.id) {
        await api.processPayment(bill.id, {
          method: 'CASH',
          amount: Number(bill.total || 0),
          transaction_id: `POS-CASH-${Date.now().toString().slice(-6)}`,
        })
      }
      await changeStatus(table.id, 'PAID')
      setConfirmPaid(false)
      setShowBill(false)
      await refresh()
    } catch (err: any) {
      setStatusError(err.message || 'Failed to mark bill paid')
    } finally {
      setBillingLoading(false)
    }
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setShowBill(false)
        setConfirmDelete(false)
        setConfirmPaid(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <aside className="table-panel">
      <div className="panel-header">
        <div>
          <p className="panel-eyebrow">{section?.name ?? 'Floor'}</p>
          <h2>Table {table.number}</h2>
        </div>
        <button type="button" className="btn-icon" onClick={onClose} aria-label="Close">×</button>
      </div>

      {(() => {
        const cfg = STATUS_CONFIG[table.status] ?? STATUS_CONFIG.AVAILABLE
        return (
          <div
            className="status-banner"
            style={{
              backgroundColor: cfg.bg,
              borderColor: cfg.border,
              color: cfg.text,
            }}
          >
            {cfg.label}
            {session && (
              <span className="status-banner__timer">
                <OccupancyTimer seatedAt={session.seatedAt} />
              </span>
            )}
          </div>
        )
      })()}

      {/* ── Real-Time Waiter Call Alert ── */}
      {hasWaiterCall && (
        <div style={{
          background: waiterCallState === 'ON_IT' ? '#fffbeb' : '#fef2f2',
          border: `1.5px solid ${waiterCallState === 'ON_IT' ? '#f59e0b' : '#f87171'}`,
          borderRadius: '10px',
          padding: '12px 14px',
          margin: '10px 0',
          boxShadow: waiterCallState === 'ON_IT' ? '0 2px 8px rgba(245,158,11,0.2)' : '0 2px 8px rgba(239,68,68,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.3rem' }}>{waiterCallState === 'ON_IT' ? '🏃' : '🙋'}</span>
              <div>
                <strong style={{ color: waiterCallState === 'ON_IT' ? '#b45309' : '#dc2626', fontSize: '0.85rem', display: 'block', textTransform: 'uppercase' }}>
                  {waiterCallState === 'ON_IT' ? `Staff Attending Table ${table.number}` : `A Guest at Table ${table.number} Needs Help`}
                </strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {waiterCallState === 'ON_IT' ? 'Staff is on the way / assisting table' : 'Customer requested assistance'}
                </span>
              </div>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '999px',
                background: waiterCallState === 'ON_IT' ? '#fef3c7' : '#fee2e2',
                color: waiterCallState === 'ON_IT' ? '#92400e' : '#991b1b',
              }}
            >
              {waiterCallState === 'ON_IT' ? 'ON IT' : 'NEEDS HELP'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
            {waiterCallState !== 'ON_IT' ? (
              onOnItWaiterCall && (
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{
                    flex: 1,
                    background: '#f59e0b',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    fontWeight: 700,
                    padding: '8px 12px',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 2px 4px rgba(245,158,11,0.3)',
                  }}
                  onClick={onOnItWaiterCall}
                >
                  🏃 I'm on it
                </button>
              )
            ) : (
              (onResolveWaiterCall || onDismissWaiterCall) && (
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{
                    flex: 1,
                    background: '#ffffff',
                    color: '#16a34a',
                    border: '1.5px solid #16a34a',
                    borderRadius: '8px',
                    fontWeight: 700,
                    padding: '8px 12px',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 1px 3px rgba(0,0,0,0.06)',
                  }}
                  onClick={onResolveWaiterCall || onDismissWaiterCall}
                >
                  ✓ Mark resolved
                </button>
              )
            )}
          </div>
        </div>
      )}

      {/* ── Real-Time Cash Payment Request Alert ── */}
      {hasCashCall && (
        <div style={{
          background: cashCallState === 'ON_IT' ? '#f0f9ff' : '#ecfdf5',
          border: `1.5px solid ${cashCallState === 'ON_IT' ? '#0284c7' : '#10b981'}`,
          borderRadius: '10px',
          padding: '12px 14px',
          margin: '10px 0',
          boxShadow: cashCallState === 'ON_IT' ? '0 2px 8px rgba(2,132,199,0.25)' : '0 2px 8px rgba(16,185,129,0.25)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.3rem' }}>{cashCallState === 'ON_IT' ? '🏃' : '💵'}</span>
              <div>
                <strong style={{ color: cashCallState === 'ON_IT' ? '#0369a1' : '#047857', fontSize: '0.85rem', display: 'block', textTransform: 'uppercase' }}>
                  {cashCallState === 'ON_IT'
                    ? `Collecting Cash from ${(cashCallInfo?.guestName || session?.guestName || 'Guest').toUpperCase()}`
                    : `💵 ${(cashCallInfo?.guestName || session?.guestName || 'Guest').toUpperCase()} at Table ${table.number} wants to pay ₹${(cashCallInfo?.amount || (bill?.total ? Number(bill.total) : runningTotal > 0 ? runningTotal * 1.155 : 0)).toFixed(2)} in cash`}
                </strong>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>
                  {cashCallState === 'ON_IT'
                    ? `Staff attending table to collect ₹${(cashCallInfo?.amount || (bill?.total ? Number(bill.total) : runningTotal > 0 ? runningTotal * 1.155 : 0)).toFixed(2)} in cash`
                    : 'Customer requested waiter to pay by cash'}
                </span>
              </div>
            </div>
            <span
              style={{
                fontSize: '0.7rem',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '999px',
                background: cashCallState === 'ON_IT' ? '#e0f2fe' : '#d1fae5',
                color: cashCallState === 'ON_IT' ? '#0284c7' : '#065f46',
              }}
            >
              {cashCallState === 'ON_IT' ? 'COLLECTING' : 'CASH'}
            </span>
          </div>

          <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
            {cashCallState !== 'ON_IT' ? (
              onOnItCashCall && (
                <button
                  type="button"
                  className="btn btn-sm"
                  style={{
                    flex: 1,
                    background: '#0284c7',
                    color: '#fff',
                    border: 'none',
                    borderRadius: '8px',
                    fontWeight: 700,
                    padding: '8px 12px',
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    boxShadow: '0 2px 4px rgba(2,132,199,0.3)',
                  }}
                  onClick={onOnItCashCall}
                >
                  🏃 I'm on it
                </button>
              )
            ) : (
              <button
                type="button"
                className="btn btn-sm"
                style={{
                  flex: 1,
                  background: '#dc2626',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '8px',
                  fontWeight: 700,
                  padding: '8px 12px',
                  cursor: 'pointer',
                  fontSize: '0.84rem',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '6px',
                  boxShadow: '0 2px 4px rgba(220,38,38,0.3)',
                }}
                disabled={billingLoading}
                onClick={async () => {
                  setBillingLoading(true)
                  try {
                    if (bill?.id) {
                      const { api: clientApi } = await import('../../api/client')
                      await clientApi.processPayment(bill.id, {
                        method: 'CASH',
                        amount: Number(bill.total || 0),
                        transaction_id: `POS-CASH-${Date.now().toString().slice(-6)}`,
                      })
                    }
                    if (onResolveCashCall) {
                      await onResolveCashCall()
                    }
                    await changeStatus(table.id, 'PAID')
                    await refresh()
                  } catch (err: any) {
                    setStatusError(err.message || 'Failed to process cash payment')
                  } finally {
                    setBillingLoading(false)
                  }
                }}
              >
                💵 Paid by Cash
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── Pending Orders Awaiting Waiter Approval ── */}
      {pendingOrders.length > 0 && (
        <div style={{
          background: '#fffbeb',
          border: '1.5px solid #fcd34d',
          borderRadius: '10px',
          padding: '10px 12px',
          margin: '10px 0',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
            <strong style={{ color: '#b45309', fontSize: '0.85rem' }}>
              ⏳ {pendingOrders.length} Order{pendingOrders.length > 1 ? 's' : ''} Need Approval
            </strong>
            <span style={{ fontSize: '0.7rem', background: '#fef3c7', color: '#92400e', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
              WAITER REVIEW
            </span>
          </div>
          {pendingOrders.map((po) => (
            <div key={po.id} style={{ background: '#ffffff', borderRadius: '8px', padding: '8px 10px', marginBottom: '8px', border: '1px solid #fde68a' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: '3px' }}>
                <span>Order #{po.id.slice(-4)}</span>
                <span>{po.items.reduce((acc, i) => acc + i.quantity, 0)} items</span>
              </div>
              <div style={{ fontSize: '0.76rem', color: '#64748b', marginBottom: '6px' }}>
                {po.items.map((i) => `${i.quantity}× ${i.itemName}`).join(', ')}
              </div>
              {po.notes && (
                <div style={{ fontSize: '0.75rem', color: '#b45309', fontStyle: 'italic', marginBottom: '6px' }}>
                  Note: {po.notes}
                </div>
              )}
              <div style={{ display: 'flex', gap: '6px' }}>
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  style={{ flex: 1, background: '#16a34a', borderColor: '#16a34a', padding: '4px 8px', fontSize: '0.78rem' }}
                  disabled={actionLoadingId === po.id}
                  onClick={() => handleApproveOrder(po.id)}
                >
                  ✓ Approve (Send to Kitchen)
                </button>
                <button
                  type="button"
                  className="btn btn-sm btn-ghost"
                  style={{ color: '#dc2626', borderColor: '#fca5a5', padding: '4px 8px', fontSize: '0.78rem' }}
                  disabled={actionLoadingId === po.id}
                  onClick={() => handleRejectOrder(po.id)}
                >
                  ✕ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Reservation / Booking Notice ── */}
      {reservation && (
        <div style={{
          background: '#eff6ff',
          border: '1.5px solid #93c5fd',
          borderRadius: '10px',
          padding: '10px 12px',
          margin: '10px 0',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <span style={{ fontWeight: 700, fontSize: '0.85rem', color: '#1e40af' }}>📅 Reserved: {reservation.guestName}</span>
            <span style={{ fontSize: '0.75rem', background: '#dbeafe', color: '#1d4ed8', padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
              {reservation.partySize} guests
            </span>
          </div>
          <div style={{ fontSize: '0.76rem', color: '#475569', marginBottom: '8px' }}>
            Time: {new Date(reservation.reservedFor).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </div>
          {!session && canSeat && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              style={{ width: '100%', background: '#2563eb', borderColor: '#2563eb' }}
              onClick={onSeatGuests}
            >
              Seat Reserved Guest
            </button>
          )}
        </div>
      )}

      <dl className="detail-list">
        <div>
          <dt>Capacity</dt>
          <dd>
            {editable ? (
              <input type="number" min={1} max={20} className="input input-sm" value={table.capacity}
                onChange={(e) => updateTable(table.id, { capacity: Number(e.target.value) })} />
            ) : `${table.capacity} guests`}
          </dd>
        </div>
        {editable && (
          <>
            <div>
              <dt>Type</dt>
              <dd>
                <select className="input" value={table.type}
                  onChange={(e) => updateTable(table.id, { type: e.target.value as TableType })}>
                  <option value="STANDARD">Standard</option>
                  <option value="BOOTH">Booth</option>
                  <option value="BAR">Bar</option>
                  <option value="VIP">VIP</option>
                </select>
              </dd>
            </div>
          </>
        )}
        {session && (
          <>
            {session.guestName && <div><dt>Guest</dt><dd>{session.guestName}</dd></div>}
            <div><dt>Party size</dt><dd>{session.partySize} guests</dd></div>
          </>
        )}
      </dl>

      {/* Prominent Order Taking Action for Seated/Active Tables */}
      {['SEATED', 'ACTIVE', 'OCCUPIED'].includes(table.status) && onTakeOrder && (
        <div style={{ margin: '14px 0 10px' }}>
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={onTakeOrder}
            style={{
              padding: '11px 16px',
              fontSize: '0.92rem',
              fontWeight: 800,
              background: '#2563eb',
              borderColor: '#2563eb',
              boxShadow: '0 2px 6px rgba(37,99,235,0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '8px',
            }}
          >
            <span style={{ fontSize: '1.15rem' }}>🍽️</span>
            <span>{items.length > 0 ? '+ Add More Items (Food & Drinks)' : '🍽️ Take Order (Food & Drinks)'}</span>
          </button>
        </div>
      )}

      {showOrders && (
        <div className="panel-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
            <h3 style={{ margin: 0 }}>Order summary</h3>
            {items.length > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, background: 'var(--surface-2)', padding: '2px 6px', borderRadius: 4 }}>
                {items.length} dishes
              </span>
            )}
          </div>
          {ordersLoading ? (
            <p className="muted" style={{ fontSize: 13 }}>Loading orders…</p>
          ) : items.length === 0 ? (
            <p className="muted" style={{ fontSize: 13 }}>No orders placed yet.</p>
          ) : (
            <div>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', fontSize: 13 }}>
                {items.map((i) => (
                  <li key={i.name} style={{ padding: '4px 0', display: 'flex', justifyContent: 'space-between', color: '#475569' }}>
                    <span>{i.qty}× {i.name}</span>
                    <span style={{ fontWeight: 600 }}>₹{(i.price * i.qty).toFixed(2)}</span>
                  </li>
                ))}
              </ul>
              <div style={{ marginTop: 8, paddingTop: 6, borderTop: '1px dashed var(--border)', fontSize: 13 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
                  <span>Subtotal:</span>
                  <span>₹{runningTotal.toFixed(2)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 800, marginTop: 4, color: 'var(--primary)', fontSize: 14 }}>
                  <span>Estimated Total (w/ tax):</span>
                  <span>₹{(runningTotal * 1.155).toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {statusError && <p className="form-error">{statusError}</p>}

      <div className="panel-section">
        <h3>Update status</h3>
        <StatusActions current={table.status} onSelect={handleStatus} loading={statusLoading} />
      </div>

      {editable && (
        <div className="panel-section">
          <a href="/camera-setup" className="btn btn-secondary btn-block" style={{ textAlign: 'center', textDecoration: 'none' }}>
            Configure camera / ROI
          </a>
          <button
            type="button"
            className="btn btn-ghost btn-block layout-delete-btn"
            style={{ marginTop: 8 }}
            onClick={() => setConfirmDelete(true)}
          >
            Remove table from layout
          </button>
          {layoutError && <p className="form-error">{layoutError}</p>}
        </div>
      )}

      <div className="panel-actions" style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {['AVAILABLE', 'SEATED'].includes(table.status) && (
          <PrintQRButton tableId={table.id} tableNumber={table.number} />
        )}
        
        {/* Real Billing Integration Buttons */}
        {session && (table.status === 'BILLING' || items.length > 0) && (
          <>
            <button
              type="button"
              className="btn btn-primary btn-block"
              onClick={handleOpenDedicatedBill}
              disabled={billingLoading}
              style={{ fontWeight: 800 }}
            >
              🧾 Open Bill &amp; Settlement {bill?.total ? `(₹${Number(bill.total).toFixed(2)})` : runningTotal > 0 ? `(₹${(runningTotal * 1.155).toFixed(2)})` : ''}
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-block"
              onClick={handleViewBill}
              disabled={billingLoading}
            >
              🖨️ Quick Bill Invoice
            </button>
            {bill?.id && (
              <button
                type="button"
                className="btn btn-ghost btn-block"
                onClick={() => window.open(`/pay/${bill.id}`, '_blank')}
                style={{ fontSize: '0.85rem' }}
              >
                ↗ Open Customer Table Pay Tab
              </button>
            )}
          </>
        )}

        {canSeat && ['AVAILABLE', 'RESERVED'].includes(table.status) && (
          <button type="button" className="btn btn-primary btn-block" onClick={onSeatGuests}>
            Seat guests here
          </button>
        )}
        {session && (
          <button type="button" className="btn btn-secondary btn-block" onClick={() => closeSession(session.id)}>
            Release table
          </button>
        )}
      </div>

      {showBill && bill && (
        <div role="presentation" onClick={() => setShowBill(false)}
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div role="dialog" aria-modal="true" onClick={(e) => e.stopPropagation()}
            style={{ background: '#fff', borderRadius: 16, padding: 24, maxWidth: 440, width: '92%', boxShadow: 'var(--shadow-lg)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <div>
                <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 800 }}>Bill #{bill.billNumber || bill.id.slice(0, 8)}</h3>
                <p className="muted" style={{ margin: 0, fontSize: '0.82rem' }}>Table {table.number} • {bill.status}</p>
              </div>
              <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '3px 8px', borderRadius: 6, background: bill.status === 'PAID' ? '#dcfce7' : '#fef3c7', color: bill.status === 'PAID' ? '#15803d' : '#b45309' }}>
                {bill.status}
              </span>
            </div>

            <ul style={{ margin: '0 0 12px', padding: 0, listStyle: 'none', fontSize: 13, maxHeight: 180, overflowY: 'auto' }}>
              {(bill.items || []).map((i, idx) => (
                <li key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)' }}>
                  <span>{i.quantity}× {i.name}</span>
                  <span style={{ fontWeight: 600 }}>₹{Number(i.subtotal || 0).toFixed(2)}</span>
                </li>
              ))}
            </ul>
            <div style={{ borderTop: '1.5px solid #e2e8f0', paddingTop: 8, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b' }}>
                <span>Subtotal:</span><span>₹{Number(bill.subtotal || 0).toFixed(2)}</span>
              </div>
              {Number(bill.discountAmount || 0) > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', color: '#b91c1c' }}>
                  <span>Discount ({bill.discountReason || 'Special'}):</span><span>-₹{Number(bill.discountAmount).toFixed(2)}</span>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b' }}>
                <span>Service Charge (10%):</span><span>₹{Number(bill.serviceChargeAmount || 0).toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', color: '#64748b' }}>
                <span>GST Tax (5%):</span><span>₹{Number(bill.taxAmount || 0).toFixed(2)}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 900, marginTop: 4, paddingTop: 6, borderTop: '1px solid #111', fontSize: 16, color: 'var(--primary)' }}>
                <span>Grand Total:</span><span>₹{Number(bill.total || 0).toFixed(2)}</span>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end', flexWrap: 'wrap' }}>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowBill(false)}>Close</button>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => {
                  setShowBill(false)
                  navigate(`/billing/${bill.id}`)
                }}
              >
                🧾 Full Settlement Page
              </button>
              {bill.status !== 'PAID' && (
                <button type="button" className="btn btn-primary btn-sm" onClick={() => setConfirmPaid(true)} disabled={billingLoading}>
                  Quick Mark Paid
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDelete}
        message={`Remove table ${table.number} from the floor plan?`}
        confirmLabel="Remove"
        onConfirm={async () => {
          setLayoutError(null)
          try {
            await deleteTable(table.id)
            setConfirmDelete(false)
            onClose()
          } catch (e) {
            setLayoutError(e instanceof Error ? e.message : 'Could not remove table')
            setConfirmDelete(false)
          }
        }}
        onCancel={() => setConfirmDelete(false)}
      />
      <ConfirmDialog
        open={confirmPaid}
        message={`Mark Table ${table.number} as paid?`}
        confirmLabel="Mark paid"
        onConfirm={handleMarkPaid}
        onCancel={() => setConfirmPaid(false)}
      />
    </aside>
  )
}
