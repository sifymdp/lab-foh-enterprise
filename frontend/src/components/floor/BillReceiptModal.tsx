import { useState } from 'react'
import { createPortal } from 'react-dom'
import { billingApi, type Bill } from '../../api/extensions'


interface BillReceiptModalProps {
  sessionId: string
  tableNumber: string
  guestName?: string
  bill: Bill
  loading: boolean
  onClose: () => void
  onMarkPaid: (method: 'CASH' | 'UPI' | 'CARD') => void
  onSendToTable: () => void
  sendState: 'idle' | 'sending' | 'sent'
}

const CATEGORY_ORDER = ['Starters', 'Mains', 'Drinks', 'Desserts']
const CATEGORY_ICONS: Record<string, string> = {
  Starters: '🥣',
  Mains: '🍽️',
  Drinks: '🍷',
  Desserts: '🧁',
}

function groupByCategory(items: Bill['items']) {
  const groups = new Map<string, Bill['items']>()
  for (const item of items) {
    const cat = item.category || 'Mains'
    const list = groups.get(cat) ?? []
    list.push(item)
    groups.set(cat, list)
  }
  const ordered = CATEGORY_ORDER.filter((c) => groups.has(c))
  const rest = [...groups.keys()].filter((c) => !ordered.includes(c)).sort()
  return [...ordered, ...rest].map((category) => ({ category, items: groups.get(category)! }))
}

function printReceipt(tableNumber: string, guestName: string | undefined, bill: Bill) {
  const groups = groupByCategory(bill.items)
  const win = window.open('', '_blank', 'width=420,height=640')
  if (!win) return
  const rows = groups
    .map(
      (g) => `
      <div class="cat">${CATEGORY_ICONS[g.category] ?? '•'} ${g.category.toUpperCase()}</div>
      ${g.items
        .map(
          (i) => `<div class="row"><span>${i.quantity}× ${i.itemName}</span><span>₹${i.lineTotal.toFixed(2)}</span></div>`,
        )
        .join('')}
    `,
    )
    .join('')
  win.document.write(`
    <html><head><title>Receipt — Table ${tableNumber}</title>
    <style>
      body { font-family: 'Courier New', monospace; padding: 20px; color: #111; }
      h1 { text-align: center; font-size: 1.1rem; margin: 0 0 4px; }
      .sub { text-align: center; font-size: 0.8rem; margin-bottom: 16px; }
      .meta { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px; }
      hr { border: none; border-top: 1px dashed #999; margin: 12px 0; }
      .cat { font-weight: 700; margin: 12px 0 4px; font-size: 0.85rem; }
      .row { display: flex; justify-content: space-between; font-size: 0.85rem; padding: 2px 0; }
      .total-row { display: flex; justify-content: space-between; font-weight: 700; font-size: 1rem; }
    </style></head>
    <body>
      <h1>FOH RESTAURANT</h1>
      <div class="sub">Table ${tableNumber}${guestName ? ' · ' + guestName : ''}</div>
      <div class="meta"><span>${new Date(bill.generatedAt).toLocaleString()}</span><span>Bill #${bill.id.slice(0, 8)}</span></div>
      <hr />
      ${rows}
      <hr />
      <div class="row"><span>Subtotal</span><span>₹${bill.subtotal.toFixed(2)}</span></div>
      <div class="total-row"><span>TOTAL</span><span>₹${bill.total.toFixed(2)}</span></div>
    </body></html>
  `)
  win.document.close()
  win.focus()
  win.print()
}

export function BillReceiptModal({
  sessionId,
  tableNumber,
  guestName,
  bill,
  loading,
  onClose,
  onMarkPaid,
  onSendToTable,
  sendState,
}: BillReceiptModalProps) {
  const groups = groupByCategory(bill.items)
  const isPaid = bill.status === 'PAID'
  const [payView, setPayView] = useState<'idle' | 'upi' | 'card'>('idle')
  const [upiQr, setUpiQr] = useState<{ upiLink: string; amount: number } | null>(null)

  const openUpi = async () => {
    setPayView('upi')
    const data = await billingApi.getUpiQr(sessionId)
    setUpiQr(data)
  }

  return createPortal(
    <>
    <div
      role="presentation"
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', zIndex: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        style={{ background: '#fff', borderRadius: 16, padding: 0, maxWidth: 420, width: '100%', maxHeight: '85vh', overflowY: 'auto' }}
      >
        <div style={{ padding: '24px 24px 16px', textAlign: 'center', borderBottom: '1px dashed #cbd5e1' }}>
          <div style={{ fontSize: 22, marginBottom: 4 }}>🍽️ FOH RESTAURANT</div>
          <div style={{ fontSize: 13, color: '#64748b' }}>
            Table {tableNumber}{guestName ? ` · Guest: ${guestName}` : ''}
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 6, display: 'flex', justifyContent: 'space-between' }}>
            <span>{new Date(bill.generatedAt).toLocaleString()}</span>
            <span>Bill #{bill.id.slice(0, 8)}</span>
          </div>
        </div>

        <div style={{ padding: '16px 24px' }}>
          {groups.map((g) => (
            <div key={g.category} style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: '#475569', marginBottom: 6 }}>
                {CATEGORY_ICONS[g.category] ?? '•'} {g.category.toUpperCase()}
              </div>
              {g.items.map((i) => (
                <div key={`${i.itemName}-${i.quantity}`} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, padding: '3px 0' }}>
                  <span>{i.quantity}× {i.itemName}</span>
                  <span>₹{i.lineTotal.toFixed(2)}</span>
                </div>
              ))}
            </div>
          ))}

          <div style={{ borderTop: '1px dashed #cbd5e1', paddingTop: 10, marginTop: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 14, color: '#64748b' }}>
              <span>Subtotal</span><span>₹{bill.subtotal.toFixed(2)}</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 700, fontSize: 16, marginTop: 4 }}>
              <span>Total</span><span>₹{bill.total.toFixed(2)}</span>
            </div>
          </div>

          <div style={{ textAlign: 'center', margin: '16px 0', fontSize: 13, fontWeight: 700, color: isPaid ? '#0f766e' : '#b45309' }}>
            {isPaid ? `✅ PAID${bill.paymentMethod ? ` · via ${bill.paymentMethod}` : ''}` : '⏳ AWAITING PAYMENT'}
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={() => printReceipt(tableNumber, guestName, bill)}>
              🖨️ Print
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ flex: 1 }}
              onClick={onSendToTable}
              disabled={sendState === 'sending'}
            >
              {sendState === 'sent' ? '✓ Sent' : sendState === 'sending' ? 'Sending…' : '📤 Send to table'}
            </button>
          </div>

          {!isPaid && (
            <div style={{ marginTop: 8 }}>
              <p style={{ fontSize: 12, color: '#64748b', margin: '0 0 8px' }}>How is the guest paying?</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button type="button" className="btn btn-secondary" style={{ justifyContent: 'flex-start', gap: 10 }} onClick={openUpi} disabled={loading}>
                  📱&nbsp; UPI — show QR to scan
                </button>
                <button type="button" className="btn btn-secondary" style={{ justifyContent: 'flex-start', gap: 10 }} onClick={() => setPayView('card')} disabled={loading}>
                  💳&nbsp; Card
                </button>
                <button type="button" className="btn btn-secondary" style={{ justifyContent: 'flex-start', gap: 10 }} onClick={() => onMarkPaid('CASH')} disabled={loading}>
                  💵&nbsp; Cash — mark paid now
                </button>
              </div>
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <button type="button" className="btn btn-ghost btn-block" onClick={onClose}>Close</button>
          </div>
        </div>
      </div>
    </div>

    {payView === 'upi' && (
      <div
        role="presentation"
        onClick={() => setPayView('idle')}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <div onClick={(e) => e.stopPropagation()} style={{ background: '#fff', borderRadius: 20, padding: 32, maxWidth: 360, width: '90%', textAlign: 'center' }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 20 }}>Scan to pay</h2>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#0f766e', margin: '4px 0 20px' }}>
            {upiQr ? `₹${upiQr.amount.toFixed(2)}` : '…'}
          </div>
          {upiQr ? (
            <img
              src={`https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=${encodeURIComponent(upiQr.upiLink)}`}
              alt="UPI QR"
              width={240}
              height={240}
              style={{ borderRadius: 14, marginBottom: 16 }}
            />
          ) : (
            <p style={{ color: '#64748b' }}>Loading QR…</p>
          )}
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => { onMarkPaid('UPI'); setPayView('idle') }}
          >
            Payment received — Mark Paid
          </button>
          <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 8 }} onClick={() => setPayView('idle')}>
            Cancel
          </button>
        </div>
      </div>
    )}

    {payView === 'card' && (
      <div
        role="presentation"
        onClick={() => setPayView('idle')}
        style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', backdropFilter: 'blur(4px)', zIndex: 300, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <div onClick={(e) => e.stopPropagation()} style={{ background: '#fff', borderRadius: 20, padding: 32, maxWidth: 360, width: '90%', textAlign: 'center' }}>
          <h2 style={{ margin: '0 0 4px', fontSize: 20 }}>Card payment</h2>
          <div style={{ fontSize: 24, fontWeight: 700, color: '#0f766e', margin: '4px 0 20px' }}>
            ₹{bill.total.toFixed(2)}
          </div>
          <p style={{ color: '#64748b', fontSize: 14, marginBottom: 20 }}>
            Process the payment on your card terminal, then confirm below.
          </p>
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => { onMarkPaid('CARD'); setPayView('idle') }}
          >
            Payment received — Mark Paid
          </button>
          <button type="button" className="btn btn-ghost btn-block" style={{ marginTop: 8 }} onClick={() => setPayView('idle')}>
            Cancel
          </button>
        </div>
      </div>
    )}
    </>,
    document.body,
  )
}

     