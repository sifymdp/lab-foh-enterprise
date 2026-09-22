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
  onClose: () => void
  onSeatGuests: () => void
  onTakeOrder?: () => void
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

export function TableDetailPanel({ floor, table, onClose, onSeatGuests, onTakeOrder }: TableDetailPanelProps) {
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

  const session = sessions
    .filter(
      (s) =>
        (s.tableId === table.id || (s as any).table_id === table.id) &&
        ['SEATED', 'ACTIVE', 'BILLING', 'PAID'].includes(s.status),
    )
    .sort((a, b) => new Date(b.seatedAt).getTime() - new Date(a.seatedAt).getTime())[0]
  const section = floor.sections.find((s) => s.id === table.sectionId)
  const editable = user ? canEditFloor(user.role) : false
  const canSeat = user ? canSeatGuests(user.role) : false
  const showOrders = ['ACTIVE', 'BILLING', 'PAID'].includes(table.status)

  useEffect(() => {
    if (!showOrders) return
    let cancelled = false
    setOrdersLoading(true)
    ordersApi.list({ tableId: table.id })
      .then((data) => { if (!cancelled) setOrders(data) })
      .catch(() => { if (!cancelled) setOrders([]) })
      .finally(() => { if (!cancelled) setOrdersLoading(false) })
    return () => { cancelled = true }
  }, [table.id, showOrders])

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

  const items = aggregateItems(orders)
  const runningTotal = items.reduce((sum, i) => sum + i.price * i.qty, 0)

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
    } catch (e) {
      setStatusError(e instanceof Error ? e.message : 'Status update failed')
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
        {['SEATED', 'ACTIVE', 'OCCUPIED'].includes(table.status) && onTakeOrder && (
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={onTakeOrder}
            style={{ fontWeight: 700 }}
          >
            🍽️ Take Order
          </button>
        )}
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
