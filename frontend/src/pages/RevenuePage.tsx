import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'

export function RevenuePage() {
  const { user } = useAuth()
  const [dailySummary, setDailySummary] = useState<any>(null)
  const [paymentSummary, setPaymentSummary] = useState<any>(null)
  const [cashierSummaries, setCashierSummaries] = useState<any[]>([])
  const [shiftSummaries, setShiftSummaries] = useState<any[]>([])
  const [ownRevenue, setOwnRevenue] = useState<any>(null)
  const [selectedDate, setSelectedDate] = useState(new Date().toISOString().split('T')[0])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchData()
  }, [selectedDate])

  const fetchData = async () => {
    try {
      setLoading(true)
      setError('')
      if (user?.role === 'OWNER' || user?.role === 'MANAGER') {
        const [daily, pay, cashiers, shifts] = await Promise.all([
          api.getDailyRevenue(selectedDate),
          api.getPaymentMethodSummary(selectedDate),
          api.getCashierSummary(selectedDate),
          api.getShiftSummary(selectedDate),
        ])
        setDailySummary(daily)
        setPaymentSummary(pay)
        setCashierSummaries(cashiers)
        setShiftSummaries(shifts)
      } else if (user?.role === 'CASHIER') {
        const own = await api.getOwnRevenue(selectedDate)
        setOwnRevenue(own)
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load revenue report')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>Revenue & Financial Summaries</h2>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className="muted">Select Date:</span>
          <input
            className="input"
            type="date"
            style={{ maxWidth: '160px', minHeight: '36px' }}
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
          />
        </div>
      </div>

      {error && <div className="form-error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {loading ? (
        <p>Loading reports...</p>
      ) : user?.role === 'OWNER' || user?.role === 'MANAGER' ? (
        /* Owner / Manager View */
        <div>
          {/* Top Row cards */}
          {dailySummary && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Net Revenue</span>
                <h3 style={{ fontSize: '1.8rem', color: 'var(--success)', marginTop: '0.25rem' }}>
                  ₹{Number(dailySummary.netRevenue ?? 0).toFixed(2)}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Total Bills Created</span>
                <h3 style={{ fontSize: '1.8rem', marginTop: '0.25rem' }}>
                  {dailySummary.totalBills ?? 0}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Paid / Pending</span>
                <h3 style={{ fontSize: '1.5rem', marginTop: '0.25rem' }}>
                  {dailySummary.paidBills ?? 0} / {dailySummary.pendingBills ?? 0}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Gross / Discounts</span>
                <h3 style={{ fontSize: '1.4rem', marginTop: '0.25rem' }}>
                  ₹{Number(dailySummary.grossRevenue ?? 0).toFixed(2)} / ₹{Number(dailySummary.discountTotal ?? 0).toFixed(2)}
                </h3>
              </div>
            </div>
          )}

          {/* Middle Grid: Payment Methods & Cashiers */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem', marginBottom: '2rem' }}>
            {/* Payment Summary */}
            {paymentSummary && (
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <h3 style={{ marginBottom: '1.25rem' }}>Payment Methods Summary</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <span>💵 Cash:</span>
                    <strong>₹{Number(paymentSummary.cash ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <span>💳 Card:</span>
                    <strong>₹{Number(paymentSummary.card ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <span>📱 UPI:</span>
                    <strong>₹{Number(paymentSummary.upi ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <span>📱 QR:</span>
                    <strong>₹{Number(paymentSummary.qr ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                    <span>🌐 Online:</span>
                    <strong>₹{Number(paymentSummary.online ?? 0).toFixed(2)}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1.1rem', paddingTop: '0.5rem' }}>
                    <span>Total Sales:</span>
                    <span>₹{Number(paymentSummary.total ?? 0).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            )}

            {/* Cashiers performance */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1rem' }}>Cashier Summaries</h3>
              {cashierSummaries.length === 0 ? (
                <p className="panel-empty-hint">No billing records for selected date.</p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)' }}>
                      <th style={{ padding: '0.5rem' }}>Cashier</th>
                      <th style={{ padding: '0.5rem' }}>Bills</th>
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
          </div>

          {/* Bottom Grid: Cashier Shift Summary */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: '1rem' }}>Active Shifts Reconciliation</h3>
            {shiftSummaries.length === 0 ? (
              <p className="panel-empty-hint">No shifts registered on this date.</p>
            ) : (
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)' }}>
                    <th style={{ padding: '0.5rem' }}>Cashier</th>
                    <th style={{ padding: '0.5rem' }}>Status</th>
                    <th style={{ padding: '0.5rem' }}>Opening float</th>
                    <th style={{ padding: '0.5rem' }}>Expected Till</th>
                    <th style={{ padding: '0.5rem' }}>Actual Count</th>
                    <th style={{ padding: '0.5rem' }}>Difference</th>
                  </tr>
                </thead>
                <tbody>
                  {shiftSummaries.map((s, idx) => (
                    <tr key={s.shiftId || idx} style={{ borderBottom: '1px solid var(--border)' }}>
                      <td style={{ padding: '0.5rem' }}>{s.cashierName || 'Cashier'}</td>
                      <td style={{ padding: '0.5rem' }}>
                        <span className={`role-badge role-${(s.status || '').toLowerCase()}`} style={{ fontSize: '0.7rem' }}>
                          {s.status || 'CLOSED'}
                        </span>
                      </td>
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
      ) : (
        /* Cashier View */
        <div style={{ maxWidth: '600px', margin: '0 auto' }}>
          {ownRevenue ? (
            <div style={{ background: 'var(--bg-elevated)', padding: '2rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1.5rem', textAlign: 'center' }}>My Sales Summary</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <span>💵 Cash:</span>
                  <strong>₹{Number(ownRevenue.cash ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <span>💳 Card:</span>
                  <strong>₹{Number(ownRevenue.card ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <span>📱 UPI:</span>
                  <strong>₹{Number(ownRevenue.upi ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <span>📱 QR:</span>
                  <strong>₹{Number(ownRevenue.qr ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>
                  <span>🌐 Online:</span>
                  <strong>₹{Number(ownRevenue.online ?? 0).toFixed(2)}</strong>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '1.2rem', paddingTop: '0.5rem' }}>
                  <span>My Total Sales:</span>
                  <span style={{ color: 'var(--primary)' }}>₹{Number(ownRevenue.total ?? 0).toFixed(2)}</span>
                </div>
              </div>
            </div>
          ) : (
            <p className="panel-empty-hint" style={{ textAlign: 'center' }}>No personal sales records found for this date.</p>
          )}
        </div>
      )}
    </div>
  )
}
