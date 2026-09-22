import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { BillSummary } from '../types'

export function PaymentsPage() {
  const { user } = useAuth()
  const [openBills, setOpenBills] = useState<BillSummary[]>([])
  const [selectedBillId, setSelectedBillId] = useState('')
  const [selectedBillDetail, setSelectedBillDetail] = useState<any>(null)
  const [currentShift, setCurrentShift] = useState<any>(null)
  const [paymentMethod, setPaymentMethod] = useState<'CASH' | 'CARD' | 'UPI' | 'QR' | 'ONLINE'>('CASH')
  const [transactionId, setTransactionId] = useState('')
  const [amount, setAmount] = useState<number>(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    fetchOpenBills()
    if (user?.role === 'CASHIER') {
      api.getCurrentShift().then((shift) => {
        setCurrentShift(shift)
      })
    }
  }, [user])

  const fetchOpenBills = async () => {
    try {
      setLoading(true)
      const res = await api.getBills()
      // Filter only OPEN bills
      setOpenBills(res.filter((b) => b.status === 'OPEN' || b.status === 'READY_FOR_PAYMENT'))
    } catch (err: any) {
      setError(err.message || 'Failed to load bills')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectBill = async (billId: string) => {
    setSelectedBillId(billId)
    if (!billId) {
      setSelectedBillDetail(null)
      setAmount(0)
      return
    }
    try {
      const res = await api.getBillDetail(billId)
      setSelectedBillDetail(res)
      setAmount(res.total)
    } catch (err: any) {
      setError(err.message || 'Failed to load bill details')
    }
  }

  const handlePay = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedBillId || !selectedBillDetail) return

    if (user?.role === 'CASHIER' && !currentShift) {
      setError('You must start a cashier shift before processing payments!')
      return
    }

    try {
      setError('')
      setSuccessMessage('')
      setLoading(true)

      const payload = {
        method: paymentMethod,
        amount: amount,
        transaction_id: transactionId || null,
        shift_id: currentShift?.id || null,
      }

      await api.processPayment(selectedBillId, payload)
      setSuccessMessage(`Payment of ₹${amount.toFixed(2)} recorded successfully via ${paymentMethod}!`)
      setSelectedBillId('')
      setSelectedBillDetail(null)
      setTransactionId('')
      setAmount(0)
      fetchOpenBills()
    } catch (err: any) {
      setError(err.message || 'Payment processing failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem' }}>Payments Terminal</h2>

      {user?.role === 'CASHIER' && (
        <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
          {currentShift ? (
            <span style={{ color: 'var(--success)', fontWeight: 600 }}>
              🟢 Shift Active (Opened at {new Date(currentShift.openedAt).toLocaleTimeString()}) — Float: ₹{currentShift.openingCash?.toFixed(2) || '2,000.00'}
            </span>
          ) : (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ color: 'var(--danger)', fontWeight: 600 }}>
                🔴 No active shift started.
              </span>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={async () => {
                  try {
                    const s = await api.startShift({ opening_cash: 1000, notes: 'Quick start from payment terminal' })
                    setCurrentShift(s)
                    setSuccessMessage('Shift started with ₹1,000 float!')
                  } catch (err: any) {
                    setError(err.message || 'Failed to start shift')
                  }
                }}
              >
                ⚡ Start Shift (₹1,000 Float)
              </button>
            </div>
          )}
        </div>
      )}


      {error && <div className="form-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {successMessage && <div style={{ color: 'var(--success)', fontWeight: 600, marginBottom: '1rem' }}>{successMessage}</div>}

      <div style={{ background: 'var(--bg-elevated)', padding: '2rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
        <form onSubmit={handlePay}>
          <div className="field">
            <span>Select Unpaid Bill</span>
            <select
              className="input"
              value={selectedBillId}
              onChange={(e) => handleSelectBill(e.target.value)}
              required
            >
              <option value="">Choose an open bill...</option>
              {openBills.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.id.substring(0, 8)}... - ₹{Number(b.total || 0).toFixed(2)}
                </option>
              ))}
            </select>
          </div>

          {selectedBillDetail && (
            <div style={{ margin: '1.5rem 0', padding: '1rem', background: 'var(--surface-2)', borderRadius: '8px', border: '1px solid var(--border)' }}>
              <h4 style={{ marginBottom: '0.5rem' }}>Bill Details Summary</h4>
              <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>
                Bill ID: <strong>{selectedBillDetail.id}</strong>
              </p>
              {selectedBillDetail.tableNumber && (
                <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>
                  Table: <strong>{selectedBillDetail.tableNumber}</strong>
                </p>
              )}
              <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>
                Grand Total: <strong style={{ color: 'var(--primary)', fontSize: '1.1rem' }}>₹{Number(selectedBillDetail.total || 0).toFixed(2)}</strong>
              </p>
            </div>
          )}

          <div className="field">
            <span>Payment Method</span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '0.5rem' }}>
              {(['CASH', 'CARD', 'UPI', 'QR', 'ONLINE'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  className={`btn ${paymentMethod === m ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ minHeight: '38px', padding: '0 0.5rem', fontSize: '0.85rem' }}
                  onClick={() => setPaymentMethod(m)}
                >
                  {m}
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span>Amount Recieved (₹)</span>
            <input
              className="input"
              type="number"
              step="0.01"
              value={amount || ''}
              onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
              required
              disabled={!selectedBillDetail}
            />
          </div>

          <div className="field">
            <span>Transaction ID / Safe Ref</span>
            <input
              className="input"
              type="text"
              placeholder="E.g. UPI Ref, Card authorization ID"
              value={transactionId}
              onChange={(e) => setTransactionId(e.target.value)}
              disabled={paymentMethod === 'CASH'}
            />
            <p style={{ fontSize: '0.75rem', color: 'var(--text-soft)', marginTop: '0.25rem' }}>
              * Do NOT input full card numbers, CVV or sensitive credentials.
            </p>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-block"
            style={{ marginTop: '1.5rem' }}
            disabled={loading || !selectedBillId || (user?.role === 'CASHIER' && !currentShift)}
          >
            {loading ? 'Processing Payment...' : 'Record Payment & Mark PAID'}
          </button>
        </form>
      </div>
    </div>
  )
}
