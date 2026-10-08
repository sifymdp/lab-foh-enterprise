import { useEffect, useState } from 'react'
import { api } from '../api/client'

type Bill = Awaited<ReturnType<typeof api.getBillingBills>>[number]

export function BillingPage() {
  const [bills, setBills] = useState<Bill[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { api.getBillingBills().then(setBills).catch((e: Error) => setError(e.message)) }, [])
  const revenue = bills.filter((b) => b.status === 'PAID').reduce((sum, b) => sum + b.total, 0)
  return <main className="page-stack"><div className="page-heading"><div><p className="eyebrow">Revenue control</p><h2>Billing</h2><p className="muted">Server-calculated totals, tax, service charge and payment state.</p></div></div><div className="stats-grid"><div className="stat-card"><span>Paid revenue</span><strong>${revenue.toFixed(2)}</strong></div><div className="stat-card"><span>Total bills</span><strong>{bills.length}</strong></div><div className="stat-card"><span>Open bills</span><strong>{bills.filter((b) => b.status === 'OPEN').length}</strong></div></div>{error && <p className="error-text">{error}</p>}<section className="panel"><h3>Recent bills</h3><div className="table-wrap"><table><thead><tr><th>Bill</th><th>Subtotal</th><th>Discount</th><th>Tax</th><th>Total</th><th>Status</th></tr></thead><tbody>{bills.map((b) => <tr key={b.id}><td>#{b.id.slice(0, 8)}</td><td>${b.subtotal.toFixed(2)}</td><td>${b.discountAmount.toFixed(2)}</td><td>${b.taxAmount.toFixed(2)}</td><td><strong>${b.total.toFixed(2)}</strong></td><td>{b.status}</td></tr>)}</tbody></table>{!bills.length && !error && <p className="muted">No bills yet.</p>}</div></section></main>
}
