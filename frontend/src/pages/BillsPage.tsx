import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { BillSummary } from '../types'

interface ReadySession {
  session_id: string
  table_id: string
  table_number: string
  guest_name: string | null
  party_size: number
  started_at: string
  order_count: number
  items: Array<{
    name: string
    quantity: number
    unit_price: number
    subtotal: number
  }>
  subtotal: number
  estimated_tax: number
  estimated_service_charge: number
  estimated_total: number
  has_bill: boolean
  bill_id: string | null
}

// Bulletproof currency / number formatter — never throws on undefined/null
const fmt = (val: any): string => {
  if (val === null || val === undefined || val === '') return '0.00'
  const num = typeof val === 'number' ? val : parseFloat(String(val))
  return isNaN(num) ? '0.00' : num.toFixed(2)
}

export function BillsPage() {
  const { user } = useAuth()
  const navigate = useNavigate()

  const [bills, setBills] = useState<BillSummary[]>([])
  const [loading, setLoading] = useState(false)
  const [readySessions, setReadySessions] = useState<ReadySession[]>([])
  const [readyLoading, setReadyLoading] = useState(false)

  // Manual Creation
  const [sessionId, setSessionId] = useState('')
  const [notes, setNotes] = useState('')
  const [creatingBill, setCreatingBill] = useState(false)

  // Search & Filters for History
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'PAID' | 'CANCELLED'>('ALL')
  const [expandedSessionId, setExpandedSessionId] = useState<string | null>(null)

  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    fetchBills()
    fetchReadySessions()
  }, [user])

  const fetchReadySessions = async () => {
    try {
      setReadyLoading(true)
      const res = await api.getReadySessions().catch(() => null)
      if (Array.isArray(res) && res.length > 0) {
        setReadySessions(res)
        return
      }

      // Fallback: build from active sessions + orders
      const [sessions, orders, existingBills] = await Promise.all([
        api.getSessions().catch(() => []),
        api.getOrders().catch(() => []),
        api.getBills().catch(() => []),
      ])

      const active = (sessions || []).filter((s: any) => s && s.status !== 'PAID' && s.status !== 'CLEANING')
      const mapped: ReadySession[] = active.map((s: any) => {
        const sessionOrders = (orders || []).filter((o: any) => o && (o.sessionId === s.id || o.session_id === s.id))
        const itemsList: Array<{ name: string; quantity: number; unit_price: number; subtotal: number }> = []
        let subtotal = 0

        sessionOrders.forEach((ord: any) => {
          ;(ord.items || []).forEach((it: any) => {
            const name = it.name || it.itemName || it.item_name || 'Dish Item'
            const qty = Number(it.quantity || 1)
            const price = Number(it.unitPrice || it.unit_price || it.price || 0)
            const lineSub = qty * price
            subtotal += lineSub
            itemsList.push({ name, quantity: qty, unit_price: price, subtotal: lineSub })
          })
        })

        const matchedBill = (existingBills || []).find((b: any) => b && (b.sessionId === s.id || b.session_id === s.id))
        const tax = Math.round(subtotal * 0.05 * 100) / 100
        const svc = Math.round(subtotal * 0.10 * 100) / 100
        const total = Math.round((subtotal + tax + svc) * 100) / 100

        return {
          session_id: s.id,
          table_id: s.tableId || s.table_id || '',
          table_number: String(s.tableId || s.table_id || '').replace('t-', ''),
          guest_name: s.guestName || s.guest_name || 'Walk-in',
          party_size: Number(s.partySize || s.party_size || 2),
          started_at: s.seatedAt || s.started_at || new Date().toISOString(),
          order_count: sessionOrders.length,
          items: itemsList,
          subtotal: Math.round(subtotal * 100) / 100,
          estimated_tax: tax,
          estimated_service_charge: svc,
          estimated_total: total,
          has_bill: !!matchedBill,
          bill_id: matchedBill ? matchedBill.id : null,
        }
      })

      setReadySessions(mapped)
    } catch {
      // Graceful ignore
    } finally {
      setReadyLoading(false)
    }
  }

  const fetchBills = async () => {
    try {
      setLoading(true)
      const res = await api.getBills()
      setBills(Array.isArray(res) ? res : [])
    } catch (err: any) {
      setError(err.message || 'Failed to fetch bills')
    } finally {
      setLoading(false)
    }
  }

  // Create bill and immediately navigate to dedicated bill detail page
  const handleCreateBillForSession = async (targetSessionId: string, customNotes?: string) => {
    try {
      setCreatingBill(true)
      setError('')
      setMessage('')
      const res = await api.createBill({ session_id: targetSessionId, notes: customNotes || undefined })
      // Navigate directly to the newly created bill inspection page
      navigate(`/billing/${res.id}`)
    } catch (err: any) {
      setError(err.message || 'Failed to create bill')
    } finally {
      setCreatingBill(false)
    }
  }

  const handleCreateManualBill = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sessionId) return
    await handleCreateBillForSession(sessionId, notes)
  }

  // Filtered bills
  const filteredBills = bills.filter((b: any) => {
    const idStr = String(b.id || '').toLowerCase()
    const tableStr = String(b.tableNumber || b.table_number || '').toLowerCase()
    const matchQuery = !searchQuery.trim() ||
      idStr.includes(searchQuery.toLowerCase()) ||
      tableStr.includes(searchQuery.toLowerCase())

    const statusMatch =
      statusFilter === 'ALL' ||
      (statusFilter === 'OPEN' && (b.status === 'OPEN' || b.status === 'READY_FOR_PAYMENT' || b.status === 'DRAFT')) ||
      (statusFilter === 'PAID' && b.status === 'PAID') ||
      (statusFilter === 'CANCELLED' && (b.status === 'CANCELLED' || b.status === 'REFUNDED'))

    return matchQuery && statusMatch
  })

  const openBillsCount = bills.filter((b: any) => b.status === 'OPEN' || b.status === 'READY_FOR_PAYMENT').length
  const paidBillsCount = bills.filter((b: any) => b.status === 'PAID').length
  const totalRevenue = bills.filter((b: any) => b.status === 'PAID').reduce((acc, b: any) => acc + Number(b.total || 0), 0)

  return (
    <div style={{ padding: '1.75rem 1.5rem', maxWidth: '1380px', margin: '0 auto' }}>
      {/* ── Page Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '1.55rem', fontWeight: 800 }}>Billing &amp; QR Payments</h1>
          <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.88rem' }}>
            Process served table orders, generate itemized bills with automated rates &amp; taxes, and manage settlements.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => { fetchBills(); fetchReadySessions(); }}
            disabled={loading || readyLoading}
          >
            {loading || readyLoading ? 'Refreshing…' : '🔄 Refresh Queue'}
          </button>
        </div>
      </div>

      {/* ── Metric Summary Cards ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1.75rem' }}>
        <div style={{ background: 'var(--bg-elevated)', borderRadius: '12px', border: '1px solid var(--border)', padding: '1.15rem 1.25rem', boxShadow: 'var(--shadow-sm)' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Active Tables Ready</span>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: readySessions.length > 0 ? 'var(--primary)' : 'inherit' }}>
            {readySessions.length}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Served orders ready for bill</span>
        </div>

        <div style={{ background: 'var(--bg-elevated)', borderRadius: '12px', border: '1px solid var(--border)', padding: '1.15rem 1.25rem', boxShadow: 'var(--shadow-sm)' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Open Bills Awaiting Pay</span>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: openBillsCount > 0 ? '#b45309' : 'inherit' }}>
            {openBillsCount}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Generated &amp; ready to settle</span>
        </div>

        <div style={{ background: 'var(--bg-elevated)', borderRadius: '12px', border: '1px solid var(--border)', padding: '1.15rem 1.25rem', boxShadow: 'var(--shadow-sm)' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Paid Bills</span>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#15803d' }}>
            {paidBillsCount}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Completed settlements</span>
        </div>

        <div style={{ background: 'var(--bg-elevated)', borderRadius: '12px', border: '1px solid var(--border)', padding: '1.15rem 1.25rem', boxShadow: 'var(--shadow-sm)' }}>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 600 }}>Total Settled Revenue</span>
          <div style={{ fontSize: '1.75rem', fontWeight: 800, marginTop: '0.35rem', color: '#15803d' }}>
            ₹{fmt(totalRevenue)}
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Lifetime paid revenue</span>
        </div>
      </div>

      {error && <div style={{ background: '#fef2f2', border: '1px solid #fecaca', padding: '0.85rem 1.25rem', borderRadius: '10px', color: '#b91c1c', marginBottom: '1.25rem', fontWeight: 600 }}>⚠️ {error}</div>}
      {message && <div style={{ background: '#f0fdf4', border: '1px solid #bbf7d0', padding: '0.85rem 1.25rem', borderRadius: '10px', color: '#15803d', marginBottom: '1.25rem', fontWeight: 600 }}>✓ {message}</div>}

      {/* ── 1. SERVED ORDERS READY FOR BILLING (Top Queue) ── */}
      <div style={{ background: 'var(--bg-elevated)', borderRadius: '16px', border: '1px solid var(--border)', padding: '1.5rem', marginBottom: '2rem', boxShadow: 'var(--shadow-sm)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.85rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.4rem' }}>🛎️</span>
            <div>
              <h2 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Tables &amp; Served Orders Ready for Billing</h2>
              <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.82rem' }}>
                Active tables with placed/served orders — click any table to inspect its full itemized rates, taxes, and payment gateway.
              </p>
            </div>
          </div>
          <span style={{ fontSize: '0.78rem', fontWeight: 700, padding: '0.25rem 0.75rem', borderRadius: '99px', background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
            {readySessions.length} Active Tables
          </span>
        </div>

        {readySessions.length === 0 ? (
          <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.9rem', background: 'var(--surface-1)', borderRadius: '10px' }}>
            🎉 No active seated dining sessions requiring bills right now.
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: '1.25rem' }}>
            {readySessions.map((session) => {
              const isExpanded = expandedSessionId === session.session_id
              const sessionItems = session.items || []

              return (
                <div
                  key={session.session_id}
                  style={{
                    background: 'var(--surface-2)',
                    border: session.has_bill ? '1.5px solid var(--primary-soft)' : '1px solid var(--border)',
                    borderRadius: '12px',
                    padding: '1.15rem',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: '0.85rem',
                    boxShadow: 'var(--shadow-xs)',
                    transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                  }}
                >
                  <div>
                    {/* Header Row */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <span style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--primary)' }}>
                          Table {session.table_number || '1'}
                        </span>
                        <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                          ({session.guest_name || 'Walk-in'} • {session.party_size || 2} guests)
                        </span>
                      </div>

                      {session.has_bill ? (
                        <span style={{ fontSize: '0.72rem', fontWeight: 800, padding: '0.2rem 0.55rem', borderRadius: '6px', background: '#dbeafe', color: '#1d4ed8' }}>
                          Bill Ready
                        </span>
                      ) : (
                        <span style={{ fontSize: '0.72rem', fontWeight: 800, padding: '0.2rem 0.55rem', borderRadius: '6px', background: '#ffedd5', color: '#c2410c' }}>
                          Ready to Bill
                        </span>
                      )}
                    </div>

                    {/* Rate & Tax Calculations Summary */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface)', padding: '0.65rem 0.85rem', borderRadius: '8px', margin: '0.65rem 0', border: '1px solid var(--border)' }}>
                      <div>
                        <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)' }}>{sessionItems.length} order items</div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>+5% GST &amp; 10% Service Tax</div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '1.2rem', fontWeight: 900, color: 'var(--text)' }}>
                          ₹{fmt(session.estimated_total)}
                        </div>
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Subtotal: ₹{fmt(session.subtotal)}</div>
                      </div>
                    </div>

                    {/* Toggle Order Items View */}
                    <button
                      type="button"
                      onClick={() => setExpandedSessionId(isExpanded ? null : session.session_id)}
                      style={{ background: 'none', border: 'none', color: 'var(--primary)', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', padding: 0 }}
                    >
                      {isExpanded ? '▲ Hide item details' : `▼ View item breakdown (${sessionItems.length})`}
                    </button>

                    {isExpanded && (
                      <div style={{ marginTop: '0.5rem', background: 'var(--surface)', borderRadius: '8px', padding: '0.6rem 0.85rem', fontSize: '0.8rem', border: '1px solid var(--border)' }}>
                        {sessionItems.map((it, idx) => (
                          <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', borderBottom: idx === sessionItems.length - 1 ? 'none' : '1px dashed var(--border)' }}>
                            <span>{it.name} <span className="muted">×{it.quantity} @ ₹{fmt(it.unit_price)}</span></span>
                            <strong>₹{fmt(it.subtotal)}</strong>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Direct Navigation Actions */}
                  <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.35rem' }}>
                    {session.has_bill && session.bill_id ? (
                      <button
                        type="button"
                        className="btn btn-primary btn-block"
                        style={{ fontSize: '0.88rem', fontWeight: 700, padding: '0.55rem' }}
                        onClick={() => navigate(`/billing/${session.bill_id}`)}
                      >
                        Inspect &amp; Settle Bill →
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-primary btn-block"
                        style={{ fontSize: '0.88rem', fontWeight: 700, padding: '0.55rem', background: 'var(--accent)' }}
                        disabled={creatingBill}
                        onClick={() => handleCreateBillForSession(session.session_id)}
                      >
                        {creatingBill ? 'Generating…' : '⚡ Generate & Inspect Bill →'}
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── 2. QUICK BILL GENERATION & BILLS HISTORY ── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 340px) 1fr', gap: '1.75rem', alignItems: 'start' }}>
        {/* Left Side: Create Manual Bill for a Table */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.35rem', borderRadius: '16px', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ margin: '0 0 0.4rem', fontSize: '1.05rem', fontWeight: 700 }}>Quick Bill Generator</h3>
          <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.8rem' }}>
            Select any seated dining session to generate a full itemized invoice.
          </p>

          <form onSubmit={handleCreateManualBill}>
            <div className="field">
              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>Dining Table Session</span>
              <select
                className="input"
                value={sessionId}
                onChange={(e) => setSessionId(e.target.value)}
                style={{ fontSize: '0.85rem' }}
                required
              >
                <option value="">-- Choose active session --</option>
                {readySessions.map((s) => (
                  <option key={s.session_id} value={s.session_id}>
                    Table {s.table_number || '1'} ({s.guest_name || 'Walk-in'} - ₹{fmt(s.estimated_total)})
                  </option>
                ))}
              </select>
            </div>

            <div className="field">
              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>Reference / Billing Notes</span>
              <input
                className="input"
                type="text"
                placeholder="e.g. VIP guest, Split bill, Corporate..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                style={{ fontSize: '0.85rem' }}
              />
            </div>

            <button
              type="submit"
              className="btn btn-primary btn-block"
              disabled={!sessionId || creatingBill}
              style={{ fontSize: '0.88rem', fontWeight: 700, padding: '0.6rem' }}
            >
              {creatingBill ? 'Generating…' : 'Generate & Open Bill →'}
            </button>
          </form>
        </div>

        {/* Right Side: Full Bills Registry & History List */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: '16px', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: 700 }}>Bills History &amp; Registry</h3>
              <p className="muted" style={{ margin: '0.15rem 0 0', fontSize: '0.82rem' }}>
                Click any bill to inspect its itemized charges, calculate discounts, print receipts, and settle payments.
              </p>
            </div>
            <span style={{ fontSize: '0.8rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: '6px', background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
              {filteredBills.length} of {bills.length} bills
            </span>
          </div>

          {/* Search Bar & Status Filter Tabs */}
          <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '200px' }}>
              <input
                type="text"
                className="input"
                placeholder="🔍 Search by Bill # or Table..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ fontSize: '0.85rem', padding: '0.5rem 0.75rem' }}
              />
            </div>

            <div style={{ display: 'flex', gap: '0.35rem' }}>
              {(['ALL', 'OPEN', 'PAID', 'CANCELLED'] as const).map((status) => {
                const isActive = statusFilter === status
                return (
                  <button
                    key={status}
                    type="button"
                    onClick={() => setStatusFilter(status)}
                    style={{
                      padding: '0.45rem 0.75rem',
                      borderRadius: '8px',
                      border: isActive ? '1.5px solid var(--primary)' : '1px solid var(--border)',
                      background: isActive ? 'var(--primary-soft)' : 'var(--surface-2)',
                      color: isActive ? 'var(--primary)' : 'var(--text-muted)',
                      fontWeight: 700,
                      fontSize: '0.78rem',
                      cursor: 'pointer',
                    }}
                  >
                    {status}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Bills Table */}
          {filteredBills.length === 0 ? (
            <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: 'var(--text-muted)', background: 'var(--surface-1)', borderRadius: '12px' }}>
              <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>🧾</span>
              <p style={{ margin: 0, fontWeight: 600 }}>No bills matching the current filters.</p>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.8rem' }}>Try clearing the search or switching status tabs.</p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.88rem' }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid var(--border)', color: 'var(--text-muted)', fontSize: '0.78rem', textTransform: 'uppercase' }}>
                    <th style={{ padding: '0.65rem 0.5rem' }}>Bill #</th>
                    <th style={{ padding: '0.65rem 0.5rem' }}>Table</th>
                    <th style={{ padding: '0.65rem 0.5rem' }}>Total</th>
                    <th style={{ padding: '0.65rem 0.5rem' }}>Status</th>
                    <th style={{ padding: '0.65rem 0.5rem', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredBills.map((b: any) => {
                    const billId = b?.id ? String(b.id) : 'N/A'
                    const isPaid = b?.status === 'PAID'
                    const isCancelled = b?.status === 'CANCELLED'

                    return (
                      <tr
                        key={billId}
                        style={{
                          borderBottom: '1px solid var(--border)',
                          cursor: 'pointer',
                          transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-2)')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        onClick={() => navigate(`/billing/${billId}`)}
                      >
                        <td style={{ padding: '0.75rem 0.5rem', fontWeight: 700, color: 'var(--primary)' }}>
                          #{billId.substring(0, 8)}
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem' }}>
                          <span style={{ fontWeight: 600 }}>
                            {b.tableNumber ? `Table ${b.tableNumber}` : 'Dine-In'}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', fontWeight: 800, fontSize: '0.95rem' }}>
                          ₹{fmt(b?.total)}
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem' }}>
                          <span
                            style={{
                              fontSize: '0.72rem',
                              padding: '0.2rem 0.55rem',
                              borderRadius: '6px',
                              fontWeight: 800,
                              background: isPaid ? '#dcfce7' : isCancelled ? '#fee2e2' : '#fef3c7',
                              color: isPaid ? '#15803d' : isCancelled ? '#b91c1c' : '#b45309',
                            }}
                          >
                            {isPaid ? '✓ PAID' : isCancelled ? '✕ CANCELLED' : '● OPEN'}
                          </span>
                        </td>
                        <td style={{ padding: '0.75rem 0.5rem', textAlign: 'right' }}>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            style={{ padding: '0.35rem 0.75rem', fontSize: '0.78rem', fontWeight: 700 }}
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/billing/${billId}`)
                            }}
                          >
                            Inspect Bill →
                          </button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
