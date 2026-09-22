import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { QrCodeSvg } from '../components/ui/QrCodeSvg'
import type { BillDetail } from '../types'

// Bulletproof currency / number formatter — never throws on undefined/null
const fmt = (val: any): string => {
  if (val === null || val === undefined || val === '') return '0.00'
  const num = typeof val === 'number' ? val : parseFloat(String(val))
  return isNaN(num) ? '0.00' : num.toFixed(2)
}

export function BillDetailPage() {
  const { billId } = useParams<{ billId: string }>()
  const navigate = useNavigate()
  const { user } = useAuth()

  const [bill, setBill] = useState<BillDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  // Payment Processing & Settlement
  const [paymentMethod, setPaymentMethod] = useState<'QR' | 'UPI' | 'CASH' | 'CARD' | 'ONLINE'>('UPI')
  const [transactionRef, setTransactionRef] = useState('')
  const [processingPayment, setProcessingPayment] = useState(false)
  const [showQrModal, setShowQrModal] = useState(false)
  const [copiedUpi, setCopiedUpi] = useState(false)

  // Discounts
  const [discountPercent, setDiscountPercent] = useState('')
  const [discountReason, setDiscountReason] = useState('')
  const [applyingDiscount, setApplyingDiscount] = useState(false)
  const [cancelReason, setCancelReason] = useState('')
  const [festivalPresets, setFestivalPresets] = useState<any[]>([])
  const [activeFestivalId, setActiveFestivalId] = useState<string | null>(null)
  const [cashierMaxDisc, setCashierMaxDisc] = useState(5.0)

  useEffect(() => {
    if (billId) {
      fetchBill(billId)
      fetchDiscountRules()
    }
  }, [billId])

  // Non-blocking bill fetcher — never unmounts the UI on updates or recalculations
  const fetchBill = async (id: string, silent = false) => {
    try {
      if (!silent) {
        if (!bill) setLoading(true)
        else setRefreshing(true)
      }
      setError('')
      const res = await api.getBillDetail(id)
      setBill(res)
    } catch (err: any) {
      if (!silent) setError(err.message || 'Failed to load bill details.')
    } finally {
      if (!silent) {
        setLoading(false)
        setRefreshing(false)
      }
    }
  }

  const fetchDiscountRules = async () => {
    try {
      const disc = await api.getDiscountSettings()
      if (disc) {
        if (Array.isArray(disc.festival_presets)) {
          setFestivalPresets(disc.festival_presets.filter((p: any) => p.active !== false))
        }
        setActiveFestivalId(disc.active_festival_id || null)
        setCashierMaxDisc(Number(disc.cashier_max_discount ?? 5.0))
      }
    } catch {
      setFestivalPresets([
        { id: 'diwali', name: 'Diwali Festival', percent: 15.0, icon: '🪔', active: true },
        { id: 'newyear', name: 'New Year Special', percent: 20.0, icon: '🎉', active: true },
        { id: 'eid', name: 'Eid Mubarak', percent: 15.0, icon: '🌙', active: true },
        { id: 'christmas', name: 'Christmas Special', percent: 20.0, icon: '🎄', active: true },
        { id: 'weekend', name: 'Weekend Happy Hours', percent: 10.0, icon: '⭐', active: true },
        { id: 'anniversary', name: 'Anniversary Discount', percent: 25.0, icon: '🎂', active: true },
      ])
    }
  }

  // Instant client-side calculator for instantaneous 0ms feedback
  const computeOptimisticBill = (currentBill: BillDetail, percentVal: number, reasonVal: string): BillDetail => {
    const subtotal = Number(currentBill.subtotal || 0)
    const discountAmount = percentVal > 0 ? Math.round((subtotal * percentVal / 100) * 100) / 100 : 0
    const taxable = Math.max(subtotal - discountAmount, 0)
    const serviceChargeAmount = Math.round((taxable * 0.10) * 100) / 100
    const taxAmount = Math.round(((taxable + serviceChargeAmount) * 0.05) * 100) / 100
    const total = Math.round((taxable + serviceChargeAmount + taxAmount) * 100) / 100
    const billNo = currentBill.billNumber || currentBill.id.slice(0, 8)
    const upi_qr_payload = `upi://pay?pa=foh.dining@icici&pn=FOH+Fine+Dining&am=${total.toFixed(2)}&cu=INR&tn=Bill-${billNo}`

    return {
      ...currentBill,
      discountAmount,
      discountReason: percentVal > 0 ? reasonVal : null,
      serviceChargeAmount,
      taxAmount,
      total,
      upi_qr_payload,
    }
  }

  // Pro 1-Click direct discount applier — instantaneous optimistic update + silent sync
  const handleApplyDiscountDirect = async (percentVal: number, reasonVal: string) => {
    if (!bill) return
    const prevBill = bill
    try {
      setApplyingDiscount(true)
      setError('')
      
      // 1. Instant local optimistic calculation (0ms screen glitch!)
      const optimistic = computeOptimisticBill(prevBill, percentVal, reasonVal)
      setBill(optimistic)

      if (percentVal === 0) {
        setMessage('✓ Offer removed. Bill recalculated to standard subtotal.')
      } else {
        setMessage(`✓ Applied ${reasonVal} (${percentVal}% off)! Total updated.`)
      }

      setDiscountPercent('')
      setDiscountReason('')

      // 2. Persist with backend in background
      const res = await api.applyDiscount(bill.id, {
        percent: percentVal,
        reason: reasonVal,
      })

      if (res.status === 'PENDING') {
        setMessage('Discount exceeds auto-threshold and has been submitted for manager approval.')
      }

      // 3. Silent background reconcile
      await fetchBill(bill.id, true)
    } catch (err: any) {
      // Revert if failed
      setBill(prevBill)
      setError(err.message || 'Failed to apply discount.')
    } finally {
      setApplyingDiscount(false)
      setTimeout(() => setMessage(''), 4000)
    }
  }

  const handleCustomDiscountSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!bill || !discountPercent) return
    const pct = parseFloat(discountPercent)
    if (isNaN(pct) || pct < 0 || pct > 100) {
      setError('Discount percentage must be between 0 and 100%')
      return
    }
    await handleApplyDiscountDirect(pct, discountReason || `Custom Discount (${pct}%)`)
  }

  const handleSettlePayment = async () => {
    if (!bill) return
    setProcessingPayment(true)
    setError('')
    setMessage('')
    try {
      const txId = transactionRef.trim() || `TXN-${paymentMethod}-${Date.now().toString().slice(-6)}`
      await api.processPayment(bill.id, {
        method: paymentMethod,
        amount: Number(bill.total || 0),
        transaction_id: txId,
      })
      setMessage(`✓ Bill #${bill.billNumber || bill.id.slice(0, 8)} paid and settled successfully via ${paymentMethod}!`)
      setTransactionRef('')
      setShowQrModal(false)
      await fetchBill(bill.id, true)
    } catch (err: any) {
      setError(err.message || 'Payment settlement failed. Please retry.')
    } finally {
      setProcessingPayment(false)
    }
  }

  const handleCancelBill = async () => {
    if (!bill) return
    if (!window.confirm('Are you sure you want to cancel this bill?')) return
    try {
      setError('')
      setMessage('')
      if (user?.role === 'CASHIER') {
        await api.createRefundRequest({
          bill_id: bill.id,
          request_type: 'CANCELLATION',
          reason: cancelReason || 'Cashier requested cancellation',
        })
        setMessage('Bill cancellation request submitted for manager approval.')
      } else {
        await api.cancelBill(bill.id)
        setMessage('Bill cancelled successfully.')
      }
      setCancelReason('')
      await fetchBill(bill.id)
    } catch (err: any) {
      setError(err.message || 'Failed to cancel bill.')
    }
  }

  const handlePrintReceipt = () => {
    if (!bill) return
    const printWindow = window.open('', '_blank', 'width=440,height=700')
    if (printWindow) {
      const billNo = bill.billNumber || bill.id.slice(0, 8)
      const itemsList = bill.items || []
      printWindow.document.write(`
        <!DOCTYPE html>
        <html>
          <head>
            <meta charset="utf-8" />
            <title>Tax Invoice #${billNo}</title>
            <style>
              body { font-family: 'Courier New', Courier, monospace, sans-serif; padding: 18px; font-size: 13px; color: #111; max-width: 360px; margin: 0 auto; }
              .header { text-align: center; margin-bottom: 12px; }
              .header h2 { margin: 0 0 4px; font-size: 17px; font-weight: bold; }
              .header p { margin: 2px 0; font-size: 11px; color: #444; }
              .divider { border-top: 1px dashed #555; margin: 10px 0; }
              .item-table { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 12px; }
              .item-table th { text-align: left; font-size: 11px; padding: 4px 0; border-bottom: 1px solid #444; }
              .item-table td { padding: 4px 0; }
              .summary-row { display: flex; justify-content: space-between; margin: 4px 0; font-size: 12px; }
              .total-row { display: flex; justify-content: space-between; font-weight: bold; font-size: 16px; margin-top: 8px; padding-top: 6px; border-top: 1.5px solid #111; }
              .footer { text-align: center; margin-top: 20px; font-size: 10px; color: #555; }
              .status-badge { display: inline-block; padding: 2px 8px; font-size: 11px; font-weight: bold; border: 1px solid #111; margin: 6px 0; }
            </style>
          </head>
          <body>
            <div class="header">
              <h2>FOH LUXURY DINING</h2>
              <p>5-Star Gourmet &amp; Hospitality Lounge</p>
              <p>GSTIN: 29ABCDE1234F1Z5 • FSSAI: 11223344556677</p>
              <div class="divider"></div>
              <p><strong>TAX INVOICE &amp; RECEIPT</strong></p>
              <p>Bill: #${billNo} • Table: ${bill.tableNumber ? `Table ${bill.tableNumber}` : 'Dine-In'}</p>
              <p>Date: ${new Date(bill.generatedAt || Date.now()).toLocaleString()}</p>
              ${bill.createdByName ? `<p>Cashier: ${bill.createdByName}</p>` : ''}
              <div class="status-badge">${bill.status === 'PAID' ? '✓ PAID / SETTLED' : 'OPEN / UNPAID'}</div>
            </div>
            <div class="divider"></div>
            <table class="item-table">
              <thead>
                <tr>
                  <th>ITEM</th>
                  <th style="text-align:center;">QTY</th>
                  <th style="text-align:right;">RATE</th>
                  <th style="text-align:right;">AMOUNT</th>
                </tr>
              </thead>
              <tbody>
                ${itemsList.map(item => `
                  <tr>
                    <td>${item.name || 'Dish'}</td>
                    <td style="text-align:center;">${item.quantity || 1}</td>
                    <td style="text-align:right;">₹${fmt(Number(item.subtotal || 0) / Math.max(item.quantity || 1, 1))}</td>
                    <td style="text-align:right;">₹${fmt(item.subtotal)}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
            <div class="divider"></div>
            <div class="summary-row"><span>Subtotal:</span><span>₹${fmt(bill.subtotal)}</span></div>
            ${Number(bill.discountAmount || 0) > 0 ? `<div class="summary-row" style="color:#b91c1c;"><span>Discount (${bill.discountReason || 'Staff'}):</span><span>-₹${fmt(bill.discountAmount)}</span></div>` : ''}
            <div class="summary-row"><span>Service Charge (10%):</span><span>₹${fmt(bill.serviceChargeAmount)}</span></div>
            <div class="summary-row"><span>GST Tax (5%):</span><span>₹${fmt(bill.taxAmount)}</span></div>
            <div class="total-row"><span>GRAND TOTAL:</span><span>₹${fmt(bill.total)}</span></div>
            <div class="divider"></div>
            <div class="summary-row"><span>Payment Status:</span><strong>${bill.status}</strong></div>
            ${bill.paidAt ? `<div class="summary-row"><span>Paid At:</span><span>${new Date(bill.paidAt).toLocaleTimeString()}</span></div>` : ''}
            <div class="footer">
              <p>Thank you for dining with us!</p>
              <p>For inquiries: dining@fohluxury.com</p>
            </div>
            <script>window.print();</script>
          </body>
        </html>
      `)
      printWindow.document.close()
    }
  }

  const upiQrPayload = bill?.upi_qr_payload ||
    `upi://pay?pa=foh.dining@icici&pn=FOH+Fine+Dining&am=${fmt(bill?.total)}&cu=INR&tn=Bill-${bill?.billNumber || bill?.id?.slice(0, 8) || '001'}`

  const copyUpi = () => {
    navigator.clipboard.writeText(upiQrPayload)
    setCopiedUpi(true)
    setTimeout(() => setCopiedUpi(false), 2500)
  }

  if (loading) {
    return (
      <div style={{ maxWidth: '1100px', margin: '2rem auto', padding: '2rem', textAlign: 'center' }}>
        <div style={{ fontSize: '2.5rem', marginBottom: '1rem', animation: 'spin 1.5s linear infinite' }}>🔄</div>
        <h3 style={{ margin: 0, fontWeight: 700 }}>Loading Bill Details…</h3>
        <p className="muted" style={{ marginTop: '0.4rem' }}>Fetching real-time rates, taxes, and order items.</p>
      </div>
    )
  }

  if (error && !bill) {
    return (
      <div style={{ maxWidth: '800px', margin: '3rem auto', padding: '2rem', textAlign: 'center', background: 'var(--bg-elevated)', borderRadius: '16px', border: '1px solid var(--border)' }}>
        <span style={{ fontSize: '3rem', display: 'block', marginBottom: '0.75rem' }}>⚠️</span>
        <h3 style={{ color: '#b91c1c', margin: '0 0 0.5rem' }}>Failed to Load Bill</h3>
        <p className="muted" style={{ margin: '0 0 1.5rem' }}>{error}</p>
        <button className="btn btn-primary" onClick={() => navigate('/billing')}>
          ← Back to Billing List
        </button>
      </div>
    )
  }

  if (!bill) return null

  const isPaid = bill.status === 'PAID'
  const isCancelled = bill.status === 'CANCELLED'
  const hasActiveDiscount = Number(bill.discountAmount || 0) > 0

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '1.75rem 1.25rem' }}>
      {/* ── Top Breadcrumb & Page Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <button
            type="button"
            onClick={() => navigate('/billing')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              background: 'transparent',
              border: 'none',
              color: 'var(--primary)',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '0.9rem',
              padding: '0.2rem 0',
              marginBottom: '0.5rem',
            }}
          >
            ← Back to Billing Queue
          </button>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0, fontSize: '1.65rem', fontWeight: 800 }}>
              Bill #{bill.billNumber || bill.id.substring(0, 8)}
            </h1>
            <span
              style={{
                fontSize: '0.85rem',
                fontWeight: 800,
                padding: '0.25rem 0.75rem',
                borderRadius: '99px',
                background: isPaid ? '#dcfce7' : isCancelled ? '#fee2e2' : '#fef3c7',
                color: isPaid ? '#15803d' : isCancelled ? '#b91c1c' : '#b45309',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.35rem',
              }}
            >
              {isPaid ? '✓ PAID & SETTLED' : isCancelled ? '✕ CANCELLED' : '● OPEN FOR PAYMENT'}
            </span>
          </div>
          <p className="muted" style={{ margin: '0.3rem 0 0', fontSize: '0.88rem' }}>
            {bill.tableNumber ? `Table ${bill.tableNumber}` : 'Standard Dine-in'} • Created{' '}
            {bill.generatedAt ? new Date(bill.generatedAt).toLocaleString() : 'Just now'}
            {bill.createdByName ? ` by ${bill.createdByName}` : ''}
          </p>
        </div>

        {/* Header Action Buttons */}
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => fetchBill(bill.id)}
            disabled={refreshing}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span style={{ display: 'inline-block', transform: refreshing ? 'rotate(180deg)' : 'none', transition: 'transform 0.3s ease' }}>
              🔄
            </span>
            {refreshing ? 'Refreshing…' : 'Refresh'}
          </button>
          <button className="btn btn-secondary btn-sm" onClick={handlePrintReceipt}>
            🖨️ Print Invoice Receipt
          </button>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => window.open(`/pay/${bill.id}`, '_blank')}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
          >
            <span>↗ Customer Table Pay Screen</span>
          </button>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '0.85rem 1.25rem', borderRadius: '10px', color: '#b91c1c', marginBottom: '1.25rem', fontWeight: 600 }}>
          ⚠️ {error}
        </div>
      )}
      {message && (
        <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '0.85rem 1.25rem', borderRadius: '10px', color: '#15803d', marginBottom: '1.25rem', fontWeight: 600 }}>
          {message}
        </div>
      )}

      {/* ── Main Two-Column Layout ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(350px, 1.35fr) minmax(320px, 1fr)', gap: '1.75rem', alignItems: 'start' }}>
        {/* ── LEFT COLUMN: ITEM DETAILS, FINANCIAL BREAKDOWN & FESTIVAL OFFERS (UTILIZING EMPTY SPACE) ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* Itemized Order Breakdown Card */}
          <div style={{ background: 'var(--bg-elevated)', borderRadius: '16px', border: '1px solid var(--border)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Itemized Charges &amp; Rates</h2>
                <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.8rem' }}>
                  Ordered dishes, quantities, and rates for {bill.tableNumber ? `Table ${bill.tableNumber}` : 'Dine-In'}
                </p>
              </div>
              <span style={{ fontSize: '0.78rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: '6px', background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                {(bill.items || []).length} items
              </span>
            </div>

            {/* Table of items */}
            <div style={{ overflowX: 'auto', marginBottom: '1.25rem' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)', color: 'var(--text-muted)', fontSize: '0.78rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.6rem 0.5rem', textAlign: 'left' }}>Item</th>
                    <th style={{ padding: '0.6rem 0.5rem', textAlign: 'center' }}>Qty</th>
                    <th style={{ padding: '0.6rem 0.5rem', textAlign: 'right' }}>Rate (₹)</th>
                    <th style={{ padding: '0.6rem 0.5rem', textAlign: 'right' }}>Amount (₹)</th>
                  </tr>
                </thead>
                <tbody>
                  {(bill.items || []).map((item, idx) => {
                    const unitPrice = Number(item.subtotal || 0) / Math.max(item.quantity || 1, 1)
                    return (
                      <tr
                        key={idx}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          background: idx % 2 === 0 ? 'transparent' : 'var(--surface-1)',
                        }}
                      >
                        <td style={{ padding: '0.65rem 0.5rem', fontWeight: 600 }}>
                          {item.name || 'Dish Item'}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', textAlign: 'center' }}>
                          <span style={{ fontWeight: 700, padding: '0.15rem 0.45rem', borderRadius: '4px', background: 'var(--surface-2)' }}>
                            {item.quantity || 1}
                          </span>
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', textAlign: 'right', color: 'var(--text-muted)' }}>
                          ₹{fmt(unitPrice)}
                        </td>
                        <td style={{ padding: '0.65rem 0.5rem', textAlign: 'right', fontWeight: 700 }}>
                          ₹{fmt(item.subtotal)}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>

            {/* Financial Summary Calculation Breakdown */}
            <div style={{ background: 'var(--surface-2)', borderRadius: '12px', padding: '1.25rem', border: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.88rem' }}>
                <span className="muted">Items Subtotal:</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(bill.subtotal)}</span>
              </div>

              {hasActiveDiscount && (
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.88rem', color: '#b91c1c' }}>
                  <span>Discount {bill.discountReason ? `(${bill.discountReason})` : ''}:</span>
                  <span style={{ fontWeight: 700 }}>-₹{fmt(bill.discountAmount)}</span>
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem', fontSize: '0.88rem' }}>
                <span className="muted">Service Charge (10%):</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(bill.serviceChargeAmount)}</span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.75rem', fontSize: '0.88rem' }}>
                <span className="muted">GST / Government Tax (5%):</span>
                <span style={{ fontWeight: 600 }}>₹{fmt(bill.taxAmount)}</span>
              </div>

              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  paddingTop: '0.75rem',
                  borderTop: '2px solid var(--border)',
                }}
              >
                <div>
                  <span style={{ fontWeight: 800, fontSize: '1.1rem' }}>Grand Total</span>
                  <p className="muted" style={{ margin: 0, fontSize: '0.72rem' }}>Inclusive of all taxes &amp; service charges</p>
                </div>
                <div style={{ fontSize: '1.65rem', fontWeight: 900, color: 'var(--primary)' }}>
                  ₹{fmt(bill.total)}
                </div>
              </div>
            </div>

            {/* Notes if any */}
            {bill.notes && (
              <div style={{ marginTop: '1rem', padding: '0.75rem 1rem', background: 'var(--surface-1)', borderRadius: '8px', border: '1px dashed var(--border)', fontSize: '0.85rem' }}>
                <span style={{ fontWeight: 700, color: 'var(--text-muted)' }}>Special Notes: </span>
                <span>{bill.notes}</span>
              </div>
            )}
          </div>

          {/* ── DEDICATED FESTIVAL OFFERS & STAFF DISCOUNTS CARD (Fills remaining empty space) ── */}
          {!isPaid && !isCancelled && (
            <div style={{ background: 'var(--bg-elevated)', borderRadius: '16px', border: '1.5px solid var(--border)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.85rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.65rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontSize: '1.35rem' }}>🎉</span>
                  <div>
                    <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800 }}>
                      Festival Offers &amp; Special Discounts
                    </h3>
                    <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.8rem' }}>
                      Click any active offer below to immediately apply discount rates to the bill and payment gateway.
                    </p>
                  </div>
                </div>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.55rem', borderRadius: '6px', background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                  Auto-Approved Offers
                </span>
              </div>

              {/* Active Discount Banner if applied */}
              {hasActiveDiscount && (
                <div
                  style={{
                    background: '#f0fdf4',
                    border: '1.5px solid #86efac',
                    borderRadius: '10px',
                    padding: '0.75rem 1rem',
                    marginBottom: '1rem',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '0.5rem',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <span style={{ fontSize: '1.15rem' }}>✅</span>
                    <div>
                      <div style={{ fontWeight: 800, color: '#15803d', fontSize: '0.9rem' }}>
                        Active Discount: {bill.discountReason || 'Special Discount'}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#166534' }}>
                        Reduced bill total by <strong>₹{fmt(bill.discountAmount)}</strong>!
                      </div>
                    </div>
                  </div>

                  <button
                    type="button"
                    className="btn btn-secondary btn-sm"
                    style={{ background: '#fff', borderColor: '#fca5a5', color: '#b91c1c', fontWeight: 700, fontSize: '0.78rem' }}
                    onClick={() => handleApplyDiscountDirect(0, 'Removed discount')}
                    disabled={applyingDiscount}
                  >
                    ✕ Remove Offer
                  </button>
                </div>
              )}

              {/* 1-Click Festival Offer Cards / Buttons */}
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.5rem', textTransform: 'uppercase' }}>
                  1-Click Instant Promotional Offers (Click to toggle on/off):
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '0.65rem' }}>
                  {festivalPresets.map((preset) => {
                    const isCurrentlyActive = hasActiveDiscount && (
                      bill.discountReason?.toLowerCase().includes(preset.name.toLowerCase()) || 
                      bill.discountReason?.toLowerCase().includes(preset.id.toLowerCase())
                    )
                    const isDefault = activeFestivalId === preset.id

                    return (
                      <button
                        key={preset.id}
                        type="button"
                        onClick={() => {
                          if (isCurrentlyActive) {
                            handleApplyDiscountDirect(0, 'Removed discount')
                          } else {
                            handleApplyDiscountDirect(preset.percent, `Festival: ${preset.name}`)
                          }
                        }}
                        disabled={applyingDiscount}
                        style={{
                          padding: '0.85rem',
                          borderRadius: '12px',
                          border: isCurrentlyActive
                            ? '2px solid #16a34a'
                            : isDefault
                            ? '1.5px solid #d97706'
                            : '1px solid var(--border)',
                          background: isCurrentlyActive
                            ? 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)'
                            : isDefault
                            ? '#fffbeb'
                            : 'var(--surface-2)',
                          color: isCurrentlyActive ? '#15803d' : isDefault ? '#b45309' : 'inherit',
                          cursor: 'pointer',
                          textAlign: 'left',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '0.3rem',
                          transition: 'all 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
                          boxShadow: isCurrentlyActive ? '0 4px 12px rgba(34,197,94,0.22)' : 'var(--shadow-sm)',
                          transform: isCurrentlyActive ? 'scale(1.02)' : 'none',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 800, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                            <span>{preset.icon}</span> <span>{preset.name}</span>
                          </span>
                          <span
                            style={{
                              fontSize: '0.75rem',
                              fontWeight: 900,
                              padding: '0.2rem 0.45rem',
                              borderRadius: '6px',
                              background: isCurrentlyActive ? '#16a34a' : 'var(--primary)',
                              color: '#fff',
                              letterSpacing: '0.02em',
                            }}
                          >
                            {preset.percent}% OFF
                          </span>
                        </div>
                        <div style={{ fontSize: '0.74rem', fontWeight: 600, color: isCurrentlyActive ? '#166534' : 'var(--text-muted)' }}>
                          {isCurrentlyActive ? '✓ Applied • Click to Remove' : 'Tap to apply instantly'}
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Custom Discount Input Form */}
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '0.4rem' }}>
                  Or Apply Custom Discount % (Staff Threshold: {cashierMaxDisc}%):
                </label>
                <form onSubmit={handleCustomDiscountSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="100"
                    placeholder="Disc %"
                    className="input"
                    value={discountPercent}
                    onChange={(e) => setDiscountPercent(e.target.value)}
                    style={{ width: '95px', fontSize: '0.85rem' }}
                  />
                  <input
                    type="text"
                    placeholder="Reason / voucher note (e.g. VIP guest, Manager approval)..."
                    className="input"
                    value={discountReason}
                    onChange={(e) => setDiscountReason(e.target.value)}
                    style={{ flex: 1, fontSize: '0.85rem' }}
                  />
                  <button
                    type="submit"
                    className="btn btn-secondary btn-sm"
                    disabled={!discountPercent || applyingDiscount}
                    style={{ fontWeight: 700, padding: '0 1rem' }}
                  >
                    {applyingDiscount ? 'Applying…' : 'Apply Discount'}
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>

        {/* ── RIGHT COLUMN: PAYMENT SETTLEMENT & ACTIONS ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {/* PAID Status Card */}
          {isPaid ? (
            <div style={{ background: '#f0fdf4', border: '1.5px solid #86efac', borderRadius: '16px', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={{ width: '42px', height: '42px', borderRadius: '50%', background: '#22c55e', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontSize: '1.4rem' }}>
                  ✓
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: '#15803d' }}>
                    Payment Completed &amp; Settled
                  </h3>
                  <p style={{ margin: '0.15rem 0 0', fontSize: '0.82rem', color: '#166534' }}>
                    This bill has been verified and settled in full.
                  </p>
                </div>
              </div>

              <div style={{ background: '#fff', borderRadius: '10px', padding: '1rem', border: '1px solid #bbf7d0', fontSize: '0.85rem', display: 'flex', flexDirection: 'column', gap: '0.4rem', marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="muted">Settled Amount:</span>
                  <span style={{ fontWeight: 800, color: '#15803d' }}>₹{fmt(bill.total)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span className="muted">Paid At:</span>
                  <span style={{ fontWeight: 600 }}>{bill.paidAt ? new Date(bill.paidAt).toLocaleString() : 'Today'}</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '0.6rem' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ flex: 1, borderColor: '#86efac', background: '#fff' }}
                  onClick={handlePrintReceipt}
                >
                  🖨️ Print Receipt
                </button>
                <button
                  className="btn btn-primary btn-sm"
                  style={{ flex: 1 }}
                  onClick={() => window.open(`/pay/${bill.id}`, '_blank')}
                >
                  ↗ View Receipt Page
                </button>
              </div>
            </div>
          ) : !isCancelled ? (
            /* OPEN FOR PAYMENT: SETTLEMENT CARD */
            <div style={{ background: 'var(--bg-elevated)', borderRadius: '16px', border: '1px solid var(--border)', padding: '1.5rem', boxShadow: 'var(--shadow-sm)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.65rem' }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Payment Gateway &amp; Settle</h3>
                <span style={{ fontSize: '0.75rem', fontWeight: 800, padding: '0.2rem 0.5rem', borderRadius: '4px', background: '#fef3c7', color: '#b45309' }}>
                  Awaiting Payment
                </span>
              </div>

              {/* Payment Method Selector */}
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: '0.5rem', color: 'var(--text-muted)' }}>
                  Select Settlement Method:
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.5rem' }}>
                  {(['UPI', 'CASH', 'CARD'] as const).map((method) => {
                    const isSelected = paymentMethod === method
                    return (
                      <button
                        key={method}
                        type="button"
                        onClick={() => setPaymentMethod(method)}
                        style={{
                          padding: '0.6rem 0.4rem',
                          borderRadius: '8px',
                          border: isSelected ? '2px solid var(--primary)' : '1px solid var(--border)',
                          background: isSelected ? 'var(--primary-soft)' : 'var(--surface-2)',
                          color: isSelected ? 'var(--primary)' : 'inherit',
                          fontWeight: 700,
                          fontSize: '0.85rem',
                          cursor: 'pointer',
                          textAlign: 'center',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {method === 'UPI' ? '📱 UPI / QR' : method === 'CASH' ? '💵 Cash Drawer' : '💳 POS Card'}
                      </button>
                    )
                  })}
                </div>
              </div>

              {/* Dynamic Instant UPI QR Display if UPI selected */}
              {paymentMethod === 'UPI' && (
                <div style={{ background: 'var(--surface-2)', borderRadius: '12px', border: '1px solid var(--border)', padding: '1.25rem', textAlign: 'center', marginBottom: '1.25rem' }}>
                  <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                    Customer Dynamic UPI QR Code (₹{fmt(bill.total)})
                  </p>
                  <div style={{ display: 'inline-block', padding: '10px', background: '#fff', borderRadius: '12px', boxShadow: 'var(--shadow-sm)' }}>
                    <QrCodeSvg value={upiQrPayload} size={170} />
                  </div>
                  <div style={{ marginTop: '0.75rem', display: 'flex', justifyContent: 'center', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={copyUpi}
                      style={{ fontSize: '0.78rem' }}
                    >
                      {copiedUpi ? '✓ UPI Link Copied' : '📋 Copy UPI Link'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary btn-sm"
                      onClick={() => setShowQrModal(true)}
                      style={{ fontSize: '0.78rem' }}
                    >
                      🔍 Enlarge QR
                    </button>
                  </div>
                </div>
              )}

              {/* Transaction Reference (Optional for Card/UPI/Cash) */}
              <div style={{ marginBottom: '1.25rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-muted)' }}>
                  Transaction / Slip Reference (Optional):
                </label>
                <input
                  type="text"
                  className="input"
                  placeholder={`e.g. ${paymentMethod === 'CASH' ? 'Drawer #1' : 'UTR/RRN 12345678'}`}
                  value={transactionRef}
                  onChange={(e) => setTransactionRef(e.target.value)}
                  style={{ fontSize: '0.85rem' }}
                />
              </div>

              {/* Settle Payment Button — prominently reflects discounted bill.total */}
              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={handleSettlePayment}
                disabled={processingPayment}
                style={{ padding: '0.85rem 1rem', fontSize: '1rem', fontWeight: 800 }}
              >
                {processingPayment ? 'Processing Settlement…' : `✓ Settle & Complete Payment (₹${fmt(bill.total)})`}
              </button>

              {/* Cancel Bill Section */}
              <div style={{ marginTop: '1.25rem', borderTop: '1px solid var(--border)', paddingTop: '1rem' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input
                    className="input"
                    type="text"
                    placeholder="Cancellation reason..."
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    style={{ flex: 1, fontSize: '0.8rem' }}
                  />
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ color: 'var(--danger)', fontSize: '0.8rem' }}
                    onClick={handleCancelBill}
                  >
                    Cancel Bill
                  </button>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ background: '#fee2e2', border: '1px solid #fecaca', borderRadius: '16px', padding: '1.5rem', color: '#b91c1c', textAlign: 'center' }}>
              <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>✕</span>
              <h3 style={{ margin: '0 0 0.35rem', fontWeight: 800 }}>Bill Cancelled</h3>
              <p style={{ margin: 0, fontSize: '0.85rem' }}>This bill has been cancelled and cannot accept payments.</p>
            </div>
          )}


        </div>
      </div>

      {/* ── QR CODE FULLSCREEN MODAL ── */}
      {showQrModal && (
        <div
          className="modal-backdrop"
          role="dialog"
          aria-modal="true"
          onClick={() => setShowQrModal(false)}
          style={{ background: 'rgba(15, 23, 42, 0.75)', backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'fixed', inset: 0, zIndex: 1000 }}
        >
          <div
            className="modal"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: '400px', width: '90%', borderRadius: '16px', padding: '1.75rem', textAlign: 'center', background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <span style={{ fontWeight: 800, fontSize: '1rem' }}>
                {bill.tableNumber ? `Table ${bill.tableNumber}` : 'Dining Bill'}
              </span>
              <button
                type="button"
                onClick={() => setShowQrModal(false)}
                style={{ background: 'none', border: 'none', fontSize: '1.25rem', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                ✕
              </button>
            </div>

            <p style={{ margin: '0 0 0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
              Scan with GPay, PhonePe, Paytm, or BHIM
            </p>
            <div style={{ fontSize: '1.5rem', fontWeight: 900, color: 'var(--primary)', marginBottom: '1rem' }}>
              ₹{fmt(bill.total)}
            </div>

            <div style={{ display: 'inline-block', padding: '12px', background: '#fff', borderRadius: '12px', boxShadow: 'var(--shadow-sm)' }}>
              <QrCodeSvg value={upiQrPayload} size={220} />
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1.25rem' }}>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                style={{ flex: 1 }}
                onClick={copyUpi}
              >
                {copiedUpi ? '✓ Copied' : '📋 Copy Link'}
              </button>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ flex: 1 }}
                onClick={() => {
                  setShowQrModal(false)
                  window.open(`/pay/${bill.id}`, '_blank')
                }}
              >
                ↗ Full Tab
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
