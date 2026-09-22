import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'

export function KitchenDashboard() {
  const { user } = useAuth()
  const [orders, setOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    fetchKitchenOrders()
    const timer = setInterval(fetchKitchenOrders, 10000)
    return () => clearInterval(timer)
  }, [])

  const fetchKitchenOrders = async () => {
    try {
      const res = await api.getKitchenOrders()
      setOrders(res)
    } catch (err: any) {
      console.error('Failed to load kitchen queue', err)
    }
  }

  const handleUpdateStatus = async (orderId: string, nextStatus: string) => {
    try {
      setLoading(true)
      setError('')
      setSuccessMessage('')
      await api.updateOrderStatus(orderId, { status: nextStatus })
      setSuccessMessage(`Order status updated to ${nextStatus}!`)
      fetchKitchenOrders()
    } catch (err: any) {
      setError(err.message || 'Status transition failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>Kitchen queue</h2>
        <span className="role-badge role-chef">{user?.role} Stand</span>
      </div>

      {error && <div className="form-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {successMessage && <div style={{ color: 'var(--success)', fontWeight: 600, marginBottom: '1rem' }}>{successMessage}</div>}

      <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <h3 style={{ marginBottom: '1.25rem' }}>Active Kitchen Orders</h3>
        {orders.length === 0 ? (
          <p className="panel-empty-hint">No active food orders in the queue.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            {orders.map((o) => (
              <div key={o.id} style={{ background: 'var(--surface-2)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <strong style={{ fontSize: '1.1rem' }}>Table {o.tableId ? String(o.tableId).replace('t-', '') : (o.table_id ? String(o.table_id).replace('t-', '') : 'N/A')}</strong>
                    <span className={`role-badge role-${(o.status || '').toLowerCase()}`} style={{ fontSize: '0.75rem' }}>
                      {o.status}
                    </span>
                  </div>
                  <div style={{ marginBottom: '1rem' }}>
                    {(o.items || []).map((item: any, idx: number) => (
                      <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', margin: '0.25rem 0', fontSize: '0.92rem' }}>
                        <span>{item.menuItemName || item.menu_item_name || item.menuItemId || item.menu_item_id || 'Item'} <strong>x{item.quantity}</strong></span>
                      </div>
                    ))}
                  </div>
                </div>

                <div style={{ borderTop: '1px dashed var(--border)', paddingTop: '0.75rem', marginTop: '0.5rem' }}>
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {o.status === 'RECEIVED' && (
                      <>
                        <button className="btn btn-primary btn-sm" style={{ flex: 1, background: 'var(--accent)' }} onClick={() => handleUpdateStatus(o.id, 'CONFIRMED')} disabled={loading}>
                          Confirm
                        </button>
                        <button className="btn btn-primary btn-sm" style={{ flex: 1 }} onClick={() => handleUpdateStatus(o.id, 'PREPARING')} disabled={loading}>
                          Prepare
                        </button>
                      </>
                    )}
                    {o.status === 'CONFIRMED' && (
                      <button className="btn btn-primary btn-block btn-sm" onClick={() => handleUpdateStatus(o.id, 'PREPARING')} disabled={loading}>
                        Start Preparing
                      </button>
                    )}
                    {o.status === 'PREPARING' && (
                      <button className="btn btn-primary btn-block btn-sm" style={{ background: 'var(--success)' }} onClick={() => handleUpdateStatus(o.id, 'READY')} disabled={loading}>
                        Mark Ready 🍳
                      </button>
                    )}
                    {o.status === 'READY' && (
                      <button className="btn btn-primary btn-block btn-sm" style={{ background: 'var(--primary)' }} onClick={() => handleUpdateStatus(o.id, 'SERVED')} disabled={loading}>
                        Serve Orders 🍽
                      </button>
                    )}
                  </div>

                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
