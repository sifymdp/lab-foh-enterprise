import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { CashierShift } from '../types'

export function CashierShiftPage() {
  const { user } = useAuth()
  const [currentShift, setCurrentShift] = useState<CashierShift | null>(null)
  const [shiftsHistory, setShiftsHistory] = useState<CashierShift[]>([])
  const [openingCash, setOpeningCash] = useState('1000')
  const [closingCash, setClosingCash] = useState('')
  const [actualCash, setActualCash] = useState('')
  const [notes, setNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetchCurrentShift()
    fetchShiftsHistory()
  }, [])

  const fetchCurrentShift = async () => {
    try {
      const res = await api.getCurrentShift()
      setCurrentShift(res)
    } catch (err: any) {
      console.error('Failed to get current shift', err)
    }
  }

  const fetchShiftsHistory = async () => {
    try {
      setLoading(true)
      const res = user?.role === 'CASHIER' ? await api.getMyShifts() : await api.getShifts()
      setShiftsHistory(res)
    } catch (err: any) {
      setError(err.message || 'Failed to load shifts')
    } finally {
      setLoading(false)
    }
  }

  const handleStartShift = async (e: React.FormEvent) => {
    e.preventDefault()
    const cash = parseFloat(openingCash)
    if (isNaN(cash) || cash < 0) {
      setError('Opening cash must be a positive number')
      return
    }
    try {
      setError('')
      setMessage('')
      setLoading(true)
      const res = await api.startShift({ opening_cash: cash, notes: notes || undefined })
      setCurrentShift(res)
      setMessage('Cashier shift started successfully!')
      setNotes('')
      fetchShiftsHistory()
    } catch (err: any) {
      setError(err.message || 'Failed to start shift')
    } finally {
      setLoading(false)
    }
  }

  const handleEndShift = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentShift) return
    const closing = parseFloat(closingCash)
    const actual = parseFloat(actualCash)
    if (isNaN(closing) || closing < 0 || isNaN(actual) || actual < 0) {
      setError('Declared cash fields must be positive numbers')
      return
    }
    try {
      setError('')
      setMessage('')
      setLoading(true)
      await api.endShift(currentShift.id, {
        closing_cash: closing,
        actual_cash: actual,
        notes: notes || undefined,
      })
      setCurrentShift(null)
      setMessage('Shift closed successfully. Reconciliation completed.')
      setClosingCash('')
      setActualCash('')
      setNotes('')
      fetchCurrentShift()
      fetchShiftsHistory()
    } catch (err: any) {
      setError(err.message || 'Failed to close shift')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1000px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem' }}>Cashier Shift stand</h2>

      {error && <div className="form-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {message && <div style={{ color: 'var(--success)', fontWeight: 600, marginBottom: '1rem' }}>{message}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Left column: Start or End Shift */}
        <div>
          {user?.role === 'CASHIER' ? (
            currentShift ? (
              /* End Shift Form */
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <h3 style={{ marginBottom: '1rem' }}>Active Shift - Close Terminal</h3>
                <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', marginBottom: '1rem', fontSize: '0.9rem' }}>
                  <p>Shift ID: <strong>{currentShift.id.substring(0, 8)}...</strong></p>
                  <p>Opened At: <strong>{new Date(currentShift.openedAt || (currentShift as any).opened_at).toLocaleString()}</strong></p>
                  <p>Opening Cash: <strong>₹{Number(currentShift.openingCash ?? (currentShift as any).opening_cash ?? 0).toFixed(2)}</strong></p>
                  <div style={{ borderTop: '1px dashed var(--border)', marginTop: '0.5rem', paddingTop: '0.5rem' }}>
                    <p>Current Sales:</p>
                    <p style={{ margin: '0.25rem 0' }}>💵 Cash: ₹{Number(currentShift.cashSales ?? (currentShift as any).cash_sales ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0' }}>💳 Card: ₹{Number(currentShift.cardSales ?? (currentShift as any).card_sales ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0' }}>📱 UPI: ₹{Number(currentShift.upiSales ?? (currentShift as any).upi_sales ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0' }}>📱 QR: ₹{Number(currentShift.qrSales ?? (currentShift as any).qr_sales ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0' }}>🌐 Online: ₹{Number(currentShift.onlineSales ?? (currentShift as any).online_sales ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0', color: 'var(--danger)' }}>Refunds: ₹{Number(currentShift.refundTotal ?? (currentShift as any).refund_total ?? 0).toFixed(2)}</p>
                    <p style={{ margin: '0.25rem 0', fontWeight: 'bold' }}>
                      Expected Till Cash: ₹{(
                        Number(currentShift.openingCash ?? (currentShift as any).opening_cash ?? 0) +
                        Number(currentShift.cashSales ?? (currentShift as any).cash_sales ?? 0) -
                        Number(currentShift.refundTotal ?? (currentShift as any).refund_total ?? 0)
                      ).toFixed(2)}
                    </p>
                  </div>
                </div>

                <form onSubmit={handleEndShift}>
                  <div className="field">
                    <span>Declared Closing Cash (Total Till Balance)</span>
                    <input
                      className="input"
                      type="number"
                      placeholder="Declare total cash left in register"
                      value={closingCash}
                      onChange={(e) => setClosingCash(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <span>Actual Physical Cash Counted</span>
                    <input
                      className="input"
                      type="number"
                      placeholder="Count physical cash bills"
                      value={actualCash}
                      onChange={(e) => setActualCash(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <span>Shift Close Remarks</span>
                    <input
                      className="input"
                      type="text"
                      placeholder="Shortages, overages explanation"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
                    {loading ? 'Reconciling Shift...' : 'Reconcile & Close Shift'}
                  </button>
                </form>
              </div>
            ) : (
              /* Start Shift Form */
              <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <h3 style={{ marginBottom: '1rem' }}>Open Cashier Shift</h3>
                <form onSubmit={handleStartShift}>
                  <div className="field">
                    <span>Opening Cash Drawer (₹)</span>
                    <input
                      className="input"
                      type="number"
                      value={openingCash}
                      onChange={(e) => setOpeningCash(e.target.value)}
                      required
                    />
                  </div>
                  <div className="field">
                    <span>Shift Opening Remarks</span>
                    <input
                      className="input"
                      type="text"
                      placeholder="E.g. standard float of ₹1000"
                      value={notes}
                      onChange={(e) => setNotes(e.target.value)}
                    />
                  </div>
                  <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
                    {loading ? 'Opening...' : 'Start Active Shift'}
                  </button>
                </form>
              </div>
            )
          ) : (
            <div style={{ background: 'var(--bg-elevated)', padding: '2rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', textAlign: 'center' }}>
              <h3>Shift Administration</h3>
              <p className="muted" style={{ marginTop: '0.5rem' }}>
                Managers and Owners can audit cashier shift logs and reconcile discrepancies on the right panel.
              </p>
            </div>
          )}
        </div>

        {/* Right column: Shift logs */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '1rem' }}>Shift Reconciliation Logs</h3>
          {shiftsHistory.length === 0 ? (
            <p className="panel-empty-hint">No shift logs found.</p>
          ) : (
            <div style={{ maxHeight: '500px', overflowY: 'auto' }}>
              {shiftsHistory.map((s) => (
                <div key={s.id} style={{ borderBottom: '1px solid var(--border)', padding: '0.75rem 0' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{s.cashierName}</strong>
                    <span className={`role-badge role-${s.status.toLowerCase()}`} style={{ fontSize: '0.7rem' }}>
                      {s.status}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    <p>Opened: {new Date(s.openedAt || (s as any).opened_at).toLocaleString()}</p>
                    {(s.closedAt || (s as any).closed_at) && <p>Closed: {new Date(s.closedAt || (s as any).closed_at).toLocaleString()}</p>}
                    <p>Opening Float: ₹{Number(s.openingCash ?? (s as any).opening_cash ?? 0).toFixed(2)} | Cash Sales: ₹{Number(s.cashSales ?? (s as any).cash_sales ?? 0).toFixed(2)}</p>
                    {s.status === 'CLOSED' && (
                      <>
                        <p style={{ fontWeight: 'bold' }}>
                          Expected: ₹{Number(s.expectedCash ?? (s as any).expected_cash ?? 0).toFixed(2)} | Actual: ₹{Number(s.actualCash ?? (s as any).actual_cash ?? 0).toFixed(2)}
                        </p>
                        {s.difference !== null && s.difference !== undefined && (
                          <p style={{
                            fontWeight: 'bold',
                            color: Number(s.difference) < 0 ? 'var(--danger)' : Number(s.difference) > 0 ? 'var(--success)' : 'inherit'
                          }}>
                            Diff: {Number(s.difference) >= 0 ? '+' : ''}₹{Number(s.difference).toFixed(2)}
                          </p>
                        )}
                      </>
                    )}
                    {s.notes && <p style={{ fontStyle: 'italic', marginTop: '0.25rem' }}>Note: {s.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
