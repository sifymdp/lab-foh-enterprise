import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function ManagerDashboard() {

  const [dailySummary, setDailySummary] = useState<any>(null)
  const [paymentSummary, setPaymentSummary] = useState<any>(null)
  const [shiftSummaries, setShiftSummaries] = useState<any[]>([])
  const [activeStaffCount, setActiveStaffCount] = useState(0)
  const [tableStats, setTableStats] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [selectedDate] = useState(new Date().toISOString().split('T')[0])

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [daily, pay, shifts, staff, floor] = await Promise.all([
        api.getDailyRevenue(selectedDate),
        api.getPaymentMethodSummary(selectedDate),
        api.getShiftSummary(selectedDate),
        api.getUsers().then(users => users.filter(u => u.isActive).length),
        api.getFloor().then(f => f.tables)
      ])

      setDailySummary(daily)
      setPaymentSummary(pay)
      setShiftSummaries(shifts)
      setActiveStaffCount(staff)

      if (floor) {
        const stats = {
          total: floor.length,
          available: floor.filter((t: any) => t.status === 'AVAILABLE').length,
          reserved: floor.filter((t: any) => t.status === 'RESERVED').length,
          seated: floor.filter((t: any) => t.status === 'SEATED' || t.status === 'ACTIVE').length,
          cleaning: floor.filter((t: any) => t.status === 'CLEANING').length
        }
        setTableStats(stats)
      }
    } catch (err) {
      console.error('Failed to load manager dashboard data', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>Manager Branch stand</h2>
        <span className="role-badge role-manager">Assigned Branch</span>
      </div>

      {loading ? (
        <p>Loading branch overview...</p>
      ) : (
        <div>
          {/* Main Financial KPI row */}
          {dailySummary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem' }}>
              <div style={{ background: 'var(--bg-elevated)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Branch Net Revenue</span>
                <h3 style={{ fontSize: '1.8rem', color: 'var(--success)', marginTop: '0.25rem' }}>
                  ₹{Number(dailySummary.netRevenue ?? 0).toFixed(2)}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Total Bills / Paid</span>
                <h3 style={{ fontSize: '1.8rem', marginTop: '0.25rem' }}>
                  {dailySummary.totalBills ?? 0} / {dailySummary.paidBills ?? 0}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Branch Discounts</span>
                <h3 style={{ fontSize: '1.8rem', color: 'var(--danger)', marginTop: '0.25rem' }}>
                  -₹{Number(dailySummary.discountTotal ?? 0).toFixed(2)}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Tax + Service Charge</span>
                <h3 style={{ fontSize: '1.5rem', marginTop: '0.25rem' }}>
                  ₹{(Number(dailySummary.taxTotal ?? 0) + Number(dailySummary.serviceChargeTotal ?? 0)).toFixed(2)}
                </h3>
              </div>
            </div>
          )}

          {/* Operational & Payment summaries */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
            {/* Operational Summary */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1.25rem' }}>Floor Seating Overview</h3>
              {tableStats && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Tables Total</span>
                    <h4 style={{ fontSize: '1.5rem', marginTop: '0.25rem' }}>{tableStats.total}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Available Tables</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--success)', marginTop: '0.25rem' }}>{tableStats.available}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Occupied Seated</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--primary)', marginTop: '0.25rem' }}>{tableStats.seated}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Staff Online</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--accent)', marginTop: '0.25rem' }}>{activeStaffCount}</h4>
                  </div>
                </div>
              )}
            </div>

            {/* Payment Summary */}
            {paymentSummary && (
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <h3 style={{ marginBottom: '1.25rem' }}>Today's Payment Methods</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.25rem' }}>
                    <span>💵 Cash:</span>
                    <strong>₹{Number(paymentSummary.cash ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.25rem' }}>
                    <span>💳 Card:</span>
                    <strong>₹{Number(paymentSummary.card ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.25rem' }}>
                    <span>📱 UPI:</span>
                    <strong>₹{Number(paymentSummary.upi ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.25rem' }}>
                    <span>📱 QR:</span>
                    <strong>₹{Number(paymentSummary.qr ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifySelf: 'stretch', justifyContent: 'space-between', paddingBottom: '0.25rem' }}>
                    <span>🌐 Online:</span>
                    <strong>₹{Number(paymentSummary.online ?? 0).toFixed(2)}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* cashier shift discrepancies */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: '1rem' }}>Active Shifts Reconciliation</h3>
            {shiftSummaries.length === 0 ? (
              <p className="panel-empty-hint">No active cashier shifts today.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '0.5rem' }}>Cashier</th>
                    <th style={{ padding: '0.5rem' }}>Opening float</th>
                    <th style={{ padding: '0.5rem' }}>Expected Till</th>
                    <th style={{ padding: '0.5rem' }}>Counted Till</th>
                    <th style={{ padding: '0.5rem' }}>Discrepancy / Diff</th>
                  </tr>
                </thead>
                <tbody>
                  {shiftSummaries.map((s, idx) => (
                    <tr key={s.shiftId || idx} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.5rem' }}>{s.cashierName || 'Cashier'}</td>
                      <td style={{ padding: '0.5rem' }}>₹{Number(s.opening_cash ?? 0).toFixed(2)}</td>
                      <td style={{ padding: '0.5rem' }}>{s.expected_cash != null ? `₹${Number(s.expected_cash).toFixed(2)}` : '-'}</td>
                      <td style={{ padding: '0.5rem' }}>{s.actual_cash != null ? `₹${Number(s.actual_cash).toFixed(2)}` : '-'}</td>
                      <td style={{
                        padding: '0.5rem',
                        fontWeight: 600,
                        color: s.difference != null && s.difference < 0 ? 'var(--danger)' : s.difference != null && s.difference > 0 ? 'var(--success)' : 'inherit'
                      }}>
                        {s.difference != null ? `${s.difference >= 0 ? '+' : ''}₹${Number(s.difference).toFixed(2)}` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
