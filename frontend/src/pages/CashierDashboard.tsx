import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export function CashierDashboard() {
  const [bills, setBills] = useState<any[]>([])
  const [ownRevenue, setOwnRevenue] = useState<any>(null)
  const [currentShift, setCurrentShift] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [selectedDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [allBills, ownRev, shift] = await Promise.all([
        api.getBills().catch(() => []),
        api.getOwnRevenue(selectedDate).catch(() => null),
        api.getCurrentShift().catch(() => null)
      ])
      setBills(Array.isArray(allBills) ? allBills : [])
      setOwnRevenue(ownRev)
      setCurrentShift(shift)
    } catch (err) {
      console.error('Failed to load cashier dashboard', err)
    } finally {
      setLoading(false)
    }
  }

  const todayBills = bills.filter((b) => b && b.status !== 'PAID')

  const getOpeningCash = (s: any) => {
    if (!s) return 0
    return Number(s.openingCash ?? s.opening_cash ?? 0)
  }

  const getCashSales = (s: any) => {
    if (!s) return 0
    return Number(s.cashSales ?? s.cash_sales ?? 0)
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ margin: 0 }}>Cashier Terminal Stand</h2>
          <p style={{ margin: '0.25rem 0 0', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Live cash drawer, billing queue, and shift reconciliation
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <Link to="/payments" className="btn btn-primary btn-sm">
            💳 Open Payment Terminal
          </Link>
          <span className="role-badge role-cashier">Cashier stand</span>
        </div>
      </div>

      {loading ? (
        <p>Loading cashier terminal statistics...</p>
      ) : (
        <div>
          {/* Shift status banner */}
          <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: '1.5rem', fontSize: '0.92rem' }}>
            {currentShift ? (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--success)', fontWeight: 600 }}>
                  🟢 Shift is Active. Opened Float: ₹{getOpeningCash(currentShift).toFixed(2)}. Process payments using the payments terminal tab.
                </span>
                <Link to="/shifts" className="btn btn-secondary btn-sm">
                  Shift Details & Close
                </Link>
              </div>
            ) : (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--danger)', fontWeight: 600 }}>
                  🔴 No Active Shift currently open for your cashier terminal.
                </span>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  onClick={async () => {
                    try {
                      const s = await api.startShift({ opening_cash: 2000, notes: 'Quick start from dashboard' })
                      setCurrentShift(s)
                    } catch (err) {
                      console.error('Failed to start shift', err)
                    }
                  }}
                >
                  ⚡ Start Shift (₹2,000 Float)
                </button>
              </div>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
            {/* Left Panel: Active Bills */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h3 style={{ margin: 0 }}>Active Unpaid Bills ({todayBills.length})</h3>
                <Link to="/billing" style={{ fontSize: '0.85rem', color: 'var(--primary)' }}>
                  View All Bills &rarr;
                </Link>
              </div>
              {todayBills.length === 0 ? (
                <p className="panel-empty-hint">No active bills awaiting payment at this branch.</p>
              ) : (
                <div style={{ maxHeight: '350px', overflowY: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '2px solid var(--border)' }}>
                        <th style={{ padding: '0.50rem' }}>Bill #</th>
                        <th style={{ padding: '0.50rem' }}>Total</th>
                        <th style={{ padding: '0.50rem' }}>Status</th>
                        <th style={{ padding: '0.50rem', textAlign: 'right' }}>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {todayBills.map((b) => (
                        <tr key={b.id} style={{ borderBottom: '1px solid var(--border)' }}>
                          <td style={{ padding: '0.50rem', fontWeight: 600 }}>
                            {b.billNumber || b.bill_number || `#${b.id.substring(0, 8)}`}
                          </td>
                          <td style={{ padding: '0.50rem', fontWeight: 600 }}>
                            ₹{Number(b.total || 0).toFixed(2)}
                          </td>
                          <td style={{ padding: '0.50rem' }}>
                            <span className={`role-badge role-${(b.status || 'open').toLowerCase()}`} style={{ fontSize: '0.7rem' }}>
                              {b.status}
                            </span>
                          </td>
                          <td style={{ padding: '0.50rem', textAlign: 'right' }}>
                            <Link to={`/billing/${b.id}`} className="btn btn-secondary btn-sm" style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}>
                              View & Pay
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Right Panel: Personal Sales & Shifts */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Own Sales Methods */}
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <h3 style={{ marginBottom: '1rem' }}>My Personal Sales (Today)</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.9rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>💵 Cash:</span>
                    <strong>₹{Number(ownRevenue?.cash ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>💳 Card:</span>
                    <strong>₹{Number(ownRevenue?.card ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>📱 UPI:</span>
                    <strong>₹{Number(ownRevenue?.upi ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>📱 QR:</span>
                    <strong>₹{Number(ownRevenue?.qr ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>🌐 Online:</span>
                    <strong>₹{Number(ownRevenue?.online ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1.1rem', borderTop: '1px solid var(--border)', paddingTop: '0.5rem', marginTop: '0.25rem' }}>
                    <span>Total Sales:</span>
                    <span style={{ color: 'var(--primary)' }}>₹{Number(ownRevenue?.total ?? 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Current Shift Summary */}
              {currentShift && (
                <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                  <h3 style={{ marginBottom: '1rem' }}>Current Shift Details</h3>
                  <div style={{ fontSize: '0.9rem' }}>
                    <p style={{ margin: '0.25rem 0' }}>
                      Shift opened:{' '}
                      <strong>
                        {currentShift.openedAt || currentShift.opened_at
                          ? new Date(currentShift.openedAt || currentShift.opened_at).toLocaleString()
                          : 'Active Today'}
                      </strong>
                    </p>
                    <p style={{ margin: '0.25rem 0' }}>
                      Opening Float: <strong>₹{getOpeningCash(currentShift).toFixed(2)}</strong>
                    </p>
                    <p style={{ margin: '0.25rem 0' }}>
                      Expected Till Cash:{' '}
                      <strong style={{ color: 'var(--success)' }}>
                        ₹{(getOpeningCash(currentShift) + getCashSales(currentShift)).toFixed(2)}
                      </strong>
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
