import { useEffect, useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import type { RefundRequest } from '../types'

export function RefundsPage() {
  const { user } = useAuth()
  const [requests, setRequests] = useState<RefundRequest[]>([])
  const [selectedRequest, setSelectedRequest] = useState<RefundRequest | null>(null)
  const [billId, setBillId] = useState('')
  const [paymentId, setPaymentId] = useState('')
  const [requestType, setRequestType] = useState<'REFUND' | 'DISCOUNT' | 'CANCELLATION'>('REFUND')
  const [amount, setAmount] = useState('')
  const [reason, setReason] = useState('')
  const [resolutionNotes, setResolutionNotes] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetchRequests()
  }, [])

  const fetchRequests = async () => {
    try {
      setLoading(true)
      const res = await api.getRefundRequests()
      setRequests(res)
    } catch (err: any) {
      setError(err.message || 'Failed to load requests')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectRequest = (req: RefundRequest) => {
    setSelectedRequest(req)
    setResolutionNotes('')
  }

  const handleCreateRequest = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!billId || !reason) return
    const amt = amount ? parseFloat(amount) : null
    if (amt !== null && (isNaN(amt) || amt < 0)) {
      setError('Amount must be positive')
      return
    }
    try {
      setError('')
      setMessage('')
      setLoading(true)
      await api.createRefundRequest({
        bill_id: billId,
        payment_id: paymentId || null,
        request_type: requestType,
        amount: amt,
        reason: reason,
      })
      setMessage('Approval request submitted successfully!')
      setBillId('')
      setPaymentId('')
      setAmount('')
      setReason('')
      fetchRequests()
    } catch (err: any) {
      setError(err.message || 'Failed to submit request')
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async () => {
    if (!selectedRequest) return
    try {
      setError('')
      setMessage('')
      setLoading(true)
      const res = await api.approveRefund(selectedRequest.id, {
        resolution_notes: resolutionNotes || undefined,
      })
      setMessage('Request approved and executed!')
      setSelectedRequest(res)
      fetchRequests()
    } catch (err: any) {
      setError(err.message || 'Failed to approve request')
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    if (!selectedRequest) return
    try {
      setError('')
      setMessage('')
      setLoading(true)
      const res = await api.rejectRefund(selectedRequest.id, {
        resolution_notes: resolutionNotes || undefined,
      })
      setMessage('Request rejected successfully.')
      setSelectedRequest(res)
      fetchRequests()
    } catch (err: any) {
      setError(err.message || 'Failed to reject request')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1100px', margin: '0 auto' }}>
      <h2 style={{ marginBottom: '1.5rem' }}>Refunds & Approvals stand</h2>

      {error && <div className="form-error" style={{ marginBottom: '1rem' }}>{error}</div>}
      {message && <div style={{ color: 'var(--success)', fontWeight: 600, marginBottom: '1rem' }}>{message}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        {/* Left panel: Create request (Cashier) or list requests (Admin) */}
        <div>
          {/* Create Request Form */}
          {(user?.role === 'CASHIER' || user?.role === 'WAITER') && (
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', marginBottom: '2rem' }}>
              <h3 style={{ marginBottom: '1.5rem' }}>New Approval Request</h3>
              <form onSubmit={handleCreateRequest}>
                <div className="field">
                  <span>Request Type</span>
                  <select
                    className="input"
                    value={requestType}
                    onChange={(e) => setRequestType(e.target.value as any)}
                  >
                    <option value="REFUND">Refund Payment</option>
                    <option value="DISCOUNT">High-Value Discount</option>
                    <option value="CANCELLATION">Bill Cancellation</option>
                  </select>
                </div>
                <div className="field">
                  <span>Bill ID</span>
                  <input
                    className="input"
                    type="text"
                    placeholder="Enter bill UUID"
                    value={billId}
                    onChange={(e) => setBillId(e.target.value)}
                    required
                  />
                </div>
                {requestType === 'REFUND' && (
                  <div className="field">
                    <span>Payment ID (Optional)</span>
                    <input
                      className="input"
                      type="text"
                      placeholder="Enter payment UUID"
                      value={paymentId}
                      onChange={(e) => setPaymentId(e.target.value)}
                    />
                  </div>
                )}
                {requestType !== 'CANCELLATION' && (
                  <div className="field">
                    <span>Amount (₹)</span>
                    <input
                      className="input"
                      type="number"
                      placeholder="Leave blank for full amount"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                    />
                  </div>
                )}
                <div className="field">
                  <span>Justification Reason</span>
                  <input
                    className="input"
                    type="text"
                    placeholder="Provide explanation for management review"
                    value={reason}
                    onChange={(e) => setReason(e.target.value)}
                    required
                  />
                </div>
                <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
                  {loading ? 'Submitting...' : 'Submit to Management'}
                </button>
              </form>
            </div>
          )}

          {/* List Requests */}
          <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: '1rem' }}>Approval Queue</h3>
            {requests.length === 0 ? (
              <p className="panel-empty-hint">No requests in queue.</p>
            ) : (
              <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                  <thead>
                    <tr style={{ borderBottom: '2px solid var(--border)' }}>
                      <th style={{ padding: '0.5rem' }}>Type</th>
                      <th style={{ padding: '0.5rem' }}>Requester</th>
                      <th style={{ padding: '0.5rem' }}>Status</th>
                      <th style={{ padding: '0.5rem' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {requests.map((r) => (
                      <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                        <td style={{ padding: '0.5rem', fontWeight: 600 }}>{r.requestType}</td>
                        <td style={{ padding: '0.5rem' }}>{r.requesterName}</td>
                        <td style={{ padding: '0.5rem' }}>
                          <span className={`role-badge role-${r.status.toLowerCase()}`} style={{ fontSize: '0.75rem' }}>
                            {r.status}
                          </span>
                        </td>
                        <td style={{ padding: '0.5rem' }}>
                          <button className="btn btn-ghost btn-sm" onClick={() => handleSelectRequest(r)}>
                            Review
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* Right panel: Details & Management Review */}
        <div>
          {selectedRequest ? (
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1.5rem' }}>Request Review</h3>

              <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem', fontSize: '0.9rem' }}>
                <p style={{ margin: '0.5rem 0' }}>Type: <strong>{selectedRequest.requestType}</strong></p>
                <p style={{ margin: '0.5rem 0' }}>Bill ID: <strong>{selectedRequest.billId}</strong></p>
                {selectedRequest.amount !== null && (
                  <p style={{ margin: '0.5rem 0' }}>Amount: <strong style={{ color: 'var(--primary)' }}>₹{selectedRequest.amount.toFixed(2)}</strong></p>
                )}
                <p style={{ margin: '0.5rem 0' }}>Requester: <strong>{selectedRequest.requesterName}</strong></p>
                <p style={{ margin: '0.5rem 0' }}>Reason: <strong>{selectedRequest.reason}</strong></p>
                <p style={{ margin: '0.5rem 0' }}>Submitted: <strong>{new Date(selectedRequest.createdAt).toLocaleString()}</strong></p>
                <p style={{ margin: '0.5rem 0' }}>Status:
                  <span className={`role-badge role-${selectedRequest.status.toLowerCase()}`} style={{ marginLeft: '0.5rem' }}>
                    {selectedRequest.status}
                  </span>
                </p>
              </div>

              {selectedRequest.status === 'PENDING' ? (
                user?.role === 'OWNER' || user?.role === 'MANAGER' ? (

                  <div>
                    {selectedRequest.requestedBy === user?.id && (
                      <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                        * You cannot approve your own request.
                      </p>
                    )}
                    <div className="field">
                      <span>Resolution/Approval Notes</span>
                      <input
                        className="input"
                        type="text"
                        placeholder="Explain approval or reject reason..."
                        value={resolutionNotes}
                        onChange={(e) => setResolutionNotes(e.target.value)}
                      />
                    </div>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                      <button
                        className="btn btn-primary"
                        style={{ flex: 1, background: 'var(--success)' }}
                        onClick={handleApprove}
                        disabled={loading || selectedRequest.requestedBy === user?.id}
                      >
                        Approve & Apply
                      </button>
                      <button
                        className="btn btn-secondary"
                        style={{ flex: 1, borderColor: 'var(--danger)', color: 'var(--danger)' }}
                        onClick={handleReject}
                        disabled={loading || selectedRequest.requestedBy === user?.id}
                      >
                        Reject Request
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="muted" style={{ fontStyle: 'italic' }}>
                    Awaiting manager or owner review. You do not have permissions to resolve this request.
                  </p>
                )
              ) : (
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginTop: '1rem', fontSize: '0.9rem' }}>
                  <p>Resolved: <strong>{selectedRequest.resolvedAt ? new Date(selectedRequest.resolvedAt).toLocaleString() : ''}</strong></p>
                  {selectedRequest.resolutionNotes && (
                    <p>Notes: <strong>{selectedRequest.resolutionNotes}</strong></p>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div style={{ background: 'var(--bg-elevated)', padding: '3rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', textAlign: 'center', color: 'var(--text-muted)' }}>
              <p>Select a request from the queue to review justification details and apply approval actions.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
