import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { QrCodeSvg } from '../components/ui/QrCodeSvg'
import type { BillDetail } from '../types'

const fmt = (val: any): string => {
  if (val === null || val === undefined || val === '') return '0.00'
  const num = typeof val === 'number' ? val : parseFloat(String(val))
  return isNaN(num) ? '0.00' : num.toFixed(2)
}

export function TablePayPage() {
  const { billId } = useParams<{ billId: string }>()
  const navigate = useNavigate()

  const [bill, setBill] = useState<BillDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [successMessage, setSuccessMessage] = useState('')

  useEffect(() => {
    if (!billId) {
      setError('No bill specified.')
      setLoading(false)
      return
    }
    fetchBill(billId)
    // Poll every 4 seconds for live payment confirmation from POS/cashier
    const interval = setInterval(() => {
      fetchBill(billId, true)
    }, 4000)
    return () => clearInterval(interval)
  }, [billId])

  const fetchBill = async (id: string, silent = false) => {
    try {
      if (!silent) setLoading(true)
      const res = await api.getBillDetail(id)
      if (res) {
        setBill(res)
        if (res.status === 'PAID') {
          setSuccessMessage('Payment completed successfully!')
        }
      } else {
        if (!silent) setError('Bill details not found.')
      }
    } catch (err: any) {
      if (!silent) setError(err.message || 'Failed to load bill.')
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const handleSimulatePay = async () => {
    if (!bill || bill.status === 'PAID') return
    setConfirming(true)
    try {
      const txId = `UPI-${Date.now().toString().slice(-6)}`
      await api.processPayment(bill.id, {
        method: 'QR',
        amount: Number(bill.total || 0),
        transaction_id: txId,
      })
      setSuccessMessage('Payment successful! Your table bill has been settled.')
      fetchBill(bill.id)
    } catch (err: any) {
      setError(err.message || 'Failed to process payment.')
    } finally {
      setConfirming(false)
    }
  }

  const handlePrintReceipt = () => {
    window.print()
  }

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', fontFamily: 'system-ui, -apple-system, sans-serif' }}>
        <div className="spinner" style={{ width: 40, height: 40, border: '4px solid #cbd5e1', borderTopColor: '#0f766e', borderRadius: '50%', animation: 'spin 1s linear infinite', marginBottom: '1rem' }} />
        <p style={{ color: '#64748b', fontSize: '0.95rem' }}>Loading live table invoice &amp; payment QR...</p>
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
      </div>
    )
  }

  if (error && !bill) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: '#f8fafc', padding: '1.5rem', textAlign: 'center', fontFamily: 'system-ui, sans-serif' }}>
        <div style={{ background: '#fff', border: '1px solid #fee2e2', borderRadius: '16px', padding: '2rem', maxWidth: '440px', boxShadow: '0 4px 20px rgba(0,0,0,0.06)' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>⚠️</div>
          <h2 style={{ fontSize: '1.25rem', margin: '0 0 0.5rem', color: '#b91c1c' }}>Bill Not Found</h2>
          <p style={{ color: '#64748b', fontSize: '0.875rem', marginBottom: '1.5rem' }}>{error}</p>
          <button
            type="button"
            onClick={() => navigate('/billing')}
            style={{ padding: '0.6rem 1.25rem', background: '#0f172a', color: '#fff', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 600 }}
          >
            ← Back to Billing
          </button>
        </div>
      </div>
    )
  }

  const billNo = bill?.billNumber || bill?.id?.slice(0, 8) || '001'
  const tableNo = bill?.tableNumber || '1'
  const isPaid = bill?.status === 'PAID'

  const upiQrPayload = (bill as any)?.upiQrPayload || bill?.upi_qr_payload ||
    `upi://pay?pa=foh.dining@icici&pn=FOH+Luxury+Pavilion&am=${fmt(bill?.total)}&cu=INR&tn=Table-${tableNo}-Bill-${billNo}`

  const discountVal = Number(bill?.discountAmount ?? (bill as any)?.discount_amount ?? 0)
  const discountReasonVal = bill?.discountReason ?? (bill as any)?.discount_reason
  const serviceChargeVal = Number(bill?.serviceChargeAmount ?? (bill as any)?.service_charge_amount ?? 0)
  const taxVal = Number(bill?.taxAmount ?? (bill as any)?.tax_amount ?? 0)

  return (
    <div style={{ minHeight: '100vh', background: 'linear-gradient(180deg, #0f172a 0%, #1e293b 220px, #f8fafc 220px)', fontFamily: 'system-ui, -apple-system, sans-serif', padding: '1.5rem 1rem 4rem' }}>
      <div style={{ maxWidth: '540px', margin: '0 auto' }}>
        {/* ── Header Branding ── */}
        <div style={{ textAlign: 'center', color: '#fff', marginBottom: '1.5rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(255,255,255,0.12)', padding: '0.35rem 0.85rem', borderRadius: '99px', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.5rem' }}>
            <span>🍽️</span> FOH LUXURY RESTAURANT &amp; BAR
          </div>
          <h1 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.02em' }}>Table {tableNo} — Live Bill &amp; Pay</h1>
          <p style={{ margin: '0.35rem 0 0', opacity: 0.8, fontSize: '0.85rem' }}>
            Bill #{billNo} • {bill?.generatedAt ? new Date(bill.generatedAt).toLocaleTimeString() : 'Just now'}
          </p>
        </div>

        {successMessage && (
          <div style={{ background: '#dcfce7', border: '1px solid #bbf7d0', color: '#15803d', padding: '0.75rem 1rem', borderRadius: '12px', marginBottom: '1rem', textAlign: 'center', fontWeight: 700, fontSize: '0.9rem' }}>
            ✓ {successMessage}
          </div>
        )}

        {/* ── Main Invoice & QR Card ── */}
        <div style={{ background: '#fff', borderRadius: '20px', boxShadow: '0 10px 40px rgba(0,0,0,0.12)', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
          {/* Status Banner */}
          <div
            style={{
              padding: '0.85rem 1.25rem',
              textAlign: 'center',
              fontWeight: 700,
              fontSize: '0.9rem',
              background: isPaid ? '#dcfce7' : '#fef3c7',
              color: isPaid ? '#15803d' : '#b45309',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
            }}
          >
            {isPaid ? (
              <><span>✓</span> Payment Completed &amp; Verified</>
            ) : (
              <><span>●</span> Ready for Payment — Scan QR or Pay via UPI</>
            )}
          </div>

          {/* Amount Due Display */}
          <div style={{ padding: '1.75rem 1.5rem 1.25rem', textAlign: 'center', borderBottom: '1px dashed #cbd5e1' }}>
            <div style={{ fontSize: '0.8rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
              {isPaid ? 'Total Amount Paid' : 'Grand Total Due'}
            </div>
            <div style={{ fontSize: '2.5rem', fontWeight: 900, color: '#0f172a', margin: '0.2rem 0' }}>
              ₹{fmt(bill?.total)}
            </div>
            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
              Includes Subtotal + 5% GST + 10% Service Charge
            </div>
          </div>

          {/* ── Dynamic QR Code Section ── */}
          {!isPaid ? (
            <div style={{ padding: '1.5rem', textAlign: 'center', background: '#fafafa' }}>
              <div style={{ display: 'inline-block', background: '#fff', padding: '1rem', borderRadius: '16px', boxShadow: '0 4px 16px rgba(0,0,0,0.06)', border: '1px solid #e2e8f0' }}>
                <QrCodeSvg value={upiQrPayload} size={220} />
              </div>

              <div style={{ margin: '1rem 0 0.5rem', fontSize: '0.95rem', fontWeight: 800, color: '#1e293b' }}>
                Scan to Pay with Any UPI App
              </div>
              <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', justifyContent: 'center', gap: '0.4rem', flexWrap: 'wrap' }}>
                <span>Google Pay</span> • <span>PhonePe</span> • <span>Paytm</span> • <span>BHIM</span> • <span>Cred</span>
              </div>

              {/* 1-Tap Mobile UPI Direct Pay Button */}
              <div style={{ marginTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <a
                  href={upiQrPayload}
                  style={{
                    display: 'block',
                    padding: '0.85rem',
                    background: '#0f766e',
                    color: '#fff',
                    borderRadius: '12px',
                    fontWeight: 700,
                    textDecoration: 'none',
                    fontSize: '0.95rem',
                    boxShadow: '0 4px 12px rgba(15,118,110,0.25)',
                  }}
                >
                  📱 Pay with Installed UPI App
                </a>

                <button
                  type="button"
                  onClick={handleSimulatePay}
                  disabled={confirming}
                  style={{
                    padding: '0.65rem',
                    background: '#f1f5f9',
                    color: '#334155',
                    border: '1px solid #cbd5e1',
                    borderRadius: '10px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: '0.82rem',
                  }}
                >
                  {confirming ? 'Processing…' : '✓ Confirm / Mark Paid (Staff / Demo)'}
                </button>
              </div>
            </div>
          ) : (
            <div style={{ padding: '2rem 1.5rem', textAlign: 'center', background: '#f0fdf4' }}>
              <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>🎉</div>
              <h3 style={{ margin: '0 0 0.35rem', fontSize: '1.25rem', color: '#15803d', fontWeight: 800 }}>Thank You for Dining With Us!</h3>
              <p style={{ margin: '0 0 1.25rem', fontSize: '0.85rem', color: '#166534' }}>
                Your payment of <strong>₹{fmt(bill?.total)}</strong> has been settled and receipt recorded.
              </p>
              <button
                type="button"
                onClick={handlePrintReceipt}
                style={{
                  padding: '0.75rem 1.5rem',
                  background: '#15803d',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                }}
              >
                🖨 Print / Save Receipt
              </button>
            </div>
          )}

          {/* ── Itemized Order Charges Breakdown ── */}
          <div style={{ padding: '1.25rem 1.5rem', borderTop: '1px solid #e2e8f0' }}>
            <h4 style={{ margin: '0 0 0.75rem', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
              Itemized Order Summary
            </h4>

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid #e2e8f0', color: '#64748b', fontSize: '0.75rem' }}>
                  <th style={{ padding: '4px 0', textAlign: 'left' }}>Item</th>
                  <th style={{ padding: '4px 0', textAlign: 'center' }}>Qty</th>
                  <th style={{ padding: '4px 0', textAlign: 'right' }}>Rate</th>
                  <th style={{ padding: '4px 0', textAlign: 'right' }}>Amount</th>
                </tr>
              </thead>
              <tbody>
                {(bill?.items || []).map((item, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '8px 0', fontWeight: 600, color: '#1e293b' }}>{item.name}</td>
                    <td style={{ padding: '8px 0', textAlign: 'center', color: '#64748b' }}>{item.quantity || 1}</td>
                    <td style={{ padding: '8px 0', textAlign: 'right', color: '#64748b' }}>
                      ₹{fmt(item.unitPrice ?? (item as any).unit_price ?? (Number(item.subtotal || 0) / Math.max(item.quantity || 1, 1)))}
                    </td>
                    <td style={{ padding: '8px 0', textAlign: 'right', fontWeight: 700, color: '#0f172a' }}>
                      ₹{fmt(item.subtotal)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Calculations Breakdown */}
            <div style={{ background: '#f8fafc', padding: '0.85rem 1rem', borderRadius: '10px', marginTop: '0.75rem', fontSize: '0.82rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem', color: '#475569' }}>
                <span>Subtotal:</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(bill?.subtotal)}</span>
              </div>

              {discountVal > 0 && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem', color: '#dc2626' }}>
                  <span>Discount {discountReasonVal ? `(${discountReasonVal})` : ''}:</span>
                  <span style={{ fontWeight: 700 }}>-₹{fmt(discountVal)}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.3rem', color: '#475569' }}>
                <span>Service Charge (10%):</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(serviceChargeVal)}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.4rem', color: '#475569' }}>
                <span>GST / Tax (5%):</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(taxVal)}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #cbd5e1', paddingTop: '0.5rem', fontWeight: 800, fontSize: '0.95rem', color: '#0f172a' }}>
                <span>Grand Total:</span>
                <span style={{ color: '#0f766e', fontSize: '1.05rem' }}>₹{fmt(bill?.total)}</span>
              </div>
            </div>
          </div>

          {/* Footer Info */}
          <div style={{ padding: '1rem 1.5rem', background: '#f8fafc', borderTop: '1px solid #e2e8f0', textAlign: 'center', fontSize: '0.72rem', color: '#64748b' }}>
            GSTIN: 29ABCDE1234F1Z5 • FSSAI Lic No: 11223344556677<br />
            Powered by FOH Intelligent POS &amp; Table Automation
          </div>
        </div>

        {/* Back Link */}
        <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
          <button
            type="button"
            onClick={() => navigate('/billing')}
            style={{ background: 'none', border: 'none', color: '#64748b', fontSize: '0.85rem', cursor: 'pointer', textDecoration: 'underline' }}
          >
            ← Back to Billing Management
          </button>
        </div>
      </div>
    </div>
  )
}
