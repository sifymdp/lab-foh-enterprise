import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function OwnerDashboard() {
  const [dailySummary, setDailySummary] = useState<any>(null)
  const [paymentSummary, setPaymentSummary] = useState<any>(null)
  const [cashierSummaries, setCashierSummaries] = useState<any[]>([])
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
      const [daily, pay, cashiers, shifts, staff, floor] = await Promise.all([
        api.getDailyRevenue(selectedDate),
        api.getPaymentMethodSummary(selectedDate),
        api.getCashierSummary(selectedDate),
        api.getShiftSummary(selectedDate),
        api.getUsers().then(users => users.filter(u => u.isActive).length),
        api.getFloor().then(f => f.tables)
      ])

      setDailySummary(daily)
      setPaymentSummary(pay)
      setCashierSummaries(cashiers)
      setShiftSummaries(shifts)
      setActiveStaffCount(staff)

      if (floor) {
        setTableStats({
          total: floor.length,
          available: floor.filter((t: any) => t.status === 'AVAILABLE').length,
          reserved: floor.filter((t: any) => t.status === 'RESERVED').length,
          seated: floor.filter((t: any) => t.status === 'SEATED' || t.status === 'ACTIVE').length,
          cleaning: floor.filter((t: any) => t.status === 'CLEANING').length
        })
      }
    } catch (err) {
      console.error('Failed to load dashboard statistics', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem' }}>Owner Administration Dashboard</h2>

      {loading ? (
        <p>Loading overview statistics...</p>
      ) : (
        <div>
          {/* Main Financial KPI row */}
          {dailySummary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '2rem' }}>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <span className="muted">Total Revenue (Net)</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--success)', marginTop: '0.35rem' }}>
                  ₹{Number(dailySummary.netRevenue ?? 0).toFixed(2)}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <span className="muted">Total Bills / Paid</span>
                <h3 style={{ fontSize: '2rem', marginTop: '0.35rem' }}>
                  {dailySummary.totalBills ?? 0} / {dailySummary.paidBills ?? 0}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <span className="muted">Pending Bills</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--accent)', marginTop: '0.35rem' }}>
                  {dailySummary.pendingBills ?? 0}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <span className="muted">Discounts Applied</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--danger)', marginTop: '0.35rem' }}>
                  -₹{Number(dailySummary.discountTotal ?? 0).toFixed(2)}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <span className="muted">Tax / Service Charge</span>
                <h3 style={{ fontSize: '1.7rem', marginTop: '0.35rem' }}>
                  ₹{(Number(dailySummary.taxTotal ?? 0) + Number(dailySummary.serviceChargeTotal ?? 0)).toFixed(2)}
                </h3>
              </div>
            </div>
          )}

          {/* Table Operations & Payment Summaries */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
            {/* Operational Summary */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
              <h3 style={{ marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Operational Summary</h3>
              {tableStats && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Total Dining Tables</span>
                    <h4 style={{ fontSize: '1.5rem', marginTop: '0.25rem' }}>{tableStats.total}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Available Tables</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--success)', marginTop: '0.25rem' }}>{tableStats.available}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Active Seated</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--accent)', marginTop: '0.25rem' }}>{tableStats.seated}</h4>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px' }}>
                    <span className="muted">Active Staff Online</span>
                    <h4 style={{ fontSize: '1.5rem', color: 'var(--primary)', marginTop: '0.25rem' }}>{activeStaffCount}</h4>
                  </div>
                </div>
              )}
            </div>

            {/* Payment Method Distribution */}
            {paymentSummary && (
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
                <h3 style={{ marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Payment Methods Distribution</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>Cash</span>
                    <br />
                    <strong>₹{Number(paymentSummary.cash ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>Card</span>
                    <br />
                    <strong>₹{Number(paymentSummary.card ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>UPI</span>
                    <br />
                    <strong>₹{Number(paymentSummary.upi ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>QR</span>
                    <br />
                    <strong>₹{Number(paymentSummary.qr ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>Online / PG</span>
                    <br />
                    <strong>₹{Number(paymentSummary.online ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ background: 'var(--surface-2)', padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--primary)' }}>
                    <span className="muted" style={{ fontSize: '0.8rem' }}>Total Settled</span>
                    <br />
                    <strong style={{ color: 'var(--primary)' }}>₹{Number(paymentSummary.total ?? 0).toFixed(2)}</strong>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Cashiers performance */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)', marginBottom: '2rem' }}>
            <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Today's Cashier Sales</h3>
            {cashierSummaries.length === 0 ? (
              <p className="panel-empty-hint">No sales summaries for today.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '0.5rem' }}>Cashier</th>
                    <th style={{ padding: '0.5rem' }}>Bills Paid</th>
                    <th style={{ padding: '0.5rem' }}>Total Sales</th>
                  </tr>
                </thead>
                <tbody>
                  {cashierSummaries.map((c, idx) => (
                    <tr key={c.cashierId || idx} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.5rem' }}>{c.cashierName || 'Staff'}</td>
                      <td style={{ padding: '0.5rem' }}>{c.billsCount ?? 0}</td>
                      <td style={{ padding: '0.5rem', fontWeight: 600 }}>₹{Number(c.totalAmount ?? 0).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* cashier shift discrepancies */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
            <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Reconciled Cashier Shifts</h3>
            {shiftSummaries.length === 0 ? (
              <p className="panel-empty-hint">No active cashier shifts today.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '0.5rem' }}>Cashier</th>
                    <th style={{ padding: '0.5rem' }}>Float</th>
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
