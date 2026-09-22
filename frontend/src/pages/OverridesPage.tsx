import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function OverridesPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [tempPerms, setTempPerms] = useState<any[]>([])
  const [permHistory, setPermHistory] = useState<any[]>([])
  const [users, setUsers] = useState<any[]>([])

  const [showTempForm, setShowTempForm] = useState(false)
  const [tempUserId, setTempUserId] = useState('')
  const [tempPermission, setTempPermission] = useState('')
  const [tempStartTime, setTempStartTime] = useState('')
  const [tempEndTime, setTempEndTime] = useState('')

  const [showDirectForm, setShowDirectForm] = useState(false)
  const [directUserId, setDirectUserId] = useState('')
  const [directPermission, setDirectPermission] = useState('')
  const [directAction, setDirectAction] = useState('GRANT')
  const [directReason, setDirectReason] = useState('')

  const staticPermissions = [
    'tables.view', 'tables.manage', 'tables.assign',
    'booking.view', 'reservations.manage',
    'billing.view', 'billing.create', 'billing.discount',
    'payment.view', 'payment.checkout', 'payment.refund', 'payment.approve',
    'cashier.shift.view', 'cashier.shift.manage',
    'revenue.view_own', 'revenue.view_branch', 'revenue.view_all',
    'audit.view'
  ]

  useEffect(() => {
    loadData()
  }, [])

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(null), 4000)
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [temps, history, ulist] = await Promise.all([
        api.listTemporaryPermissions(),
        api.listPermissionHistory(),
        api.getUsers()
      ])
      setTempPerms(temps)
      setPermHistory(history)
      setUsers(ulist)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to retrieve overrides')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateTempPerm = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.createTemporaryPermission({
        user_id: tempUserId,
        permission: tempPermission,
        start_time: tempStartTime,
        end_time: tempEndTime
      })
      setShowTempForm(false)
      showSuccess('Temporary override permission granted')
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Temporary grant failed')
    }
  }

  const handleCancelTemp = async (permId: string) => {
    try {
      await api.cancelTemporaryPermission(permId)
      showSuccess('Temporary override cancelled')
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancellation failed')
    }
  }

  const handleDirectPermission = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.toggleDirectPermission({
        user_id: directUserId,
        permission: directPermission,
        action: directAction,
        reason: directReason
      })
      setShowDirectForm(false)
      showSuccess('Direct override instruction processed')
      loadData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Direct override action failed')
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2>Permission Overrides & Access History</h2>
          <p className="muted">Monitor and adjust time-bound clearance and explicit override constraints</p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button className="btn btn-ghost" onClick={() => setShowDirectForm(true)}>⚡ Direct Override</button>
          <button className="btn btn-primary" onClick={() => setShowTempForm(true)}>+ Temporary Grant</button>
        </div>
      </div>

      {successMsg && (
        <div style={{ background: 'var(--accent-soft)', color: 'var(--accent)', padding: '0.75rem 1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', fontWeight: 600, marginBottom: '1rem' }}>
          ✓ {successMsg}
        </div>
      )}

      {error && (
        <div style={{ background: 'var(--primary-soft)', color: 'var(--primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius)', border: '1px solid var(--primary)', fontWeight: 600, marginBottom: '1rem' }}>
          ⚠ Error: {error}
        </div>
      )}

      {loading && !successMsg && (
        <p style={{ color: 'var(--text-muted)' }}>Refreshing permissions history logs...</p>
      )}

      {/* Active Overrides */}
      <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)', marginBottom: '2rem' }}>
        <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Active Temporary Clearances</h3>
        {tempPerms.length === 0 ? (
          <p className="panel-empty-hint">No active temporary permission override records found.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ padding: '0.75rem' }}>User</th>
                <th style={{ padding: '0.75rem' }}>Permission</th>
                <th style={{ padding: '0.75rem' }}>Start Clearance</th>
                <th style={{ padding: '0.75rem' }}>End Expiration</th>
                <th style={{ padding: '0.75rem' }}>Status</th>
                <th style={{ padding: '0.75rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tempPerms.map((p) => (
                <tr key={p.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.75rem' }}>
                    <strong>{p.userName}</strong>
                  </td>
                  <td style={{ padding: '0.75rem' }}><code style={{ color: 'var(--primary)' }}>{p.permission}</code></td>
                  <td style={{ padding: '0.75rem' }}>{new Date(p.startTime).toLocaleString()}</td>
                  <td style={{ padding: '0.75rem' }}>{new Date(p.endTime).toLocaleString()}</td>
                  <td style={{ padding: '0.75rem' }}>
                    <span style={{ color: p.status === 'ACTIVE' ? 'var(--success)' : 'var(--text-soft)', fontWeight: 600 }}>
                      {p.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem' }}>
                    {p.status === 'ACTIVE' && (
                      <button className="btn btn-ghost btn-sm" style={{ color: 'var(--danger)' }} onClick={() => handleCancelTemp(p.id)}>
                        Revoke Override
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* History log */}
      <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
        <h3 style={{ marginBottom: '1rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem' }}>Clearance & Override Log</h3>
        {permHistory.length === 0 ? (
          <p className="panel-empty-hint">No override history events recorded.</p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ padding: '0.75rem' }}>User</th>
                <th style={{ padding: '0.75rem' }}>Event Action</th>
                <th style={{ padding: '0.75rem' }}>Permission Name</th>
                <th style={{ padding: '0.75rem' }}>Modified By</th>
                <th style={{ padding: '0.75rem' }}>Timestamp</th>
                <th style={{ padding: '0.75rem' }}>Reason</th>
              </tr>
            </thead>
            <tbody>
              {permHistory.map((h) => (
                <tr key={h.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.75rem' }}>{h.userName}</td>
                  <td style={{ padding: '0.75rem', fontWeight: 600 }}>
                    <span style={{ color: h.action.includes('GRANT') ? 'var(--success)' : 'var(--danger)' }}>{h.action}</span>
                  </td>
                  <td style={{ padding: '0.75rem' }}><code>{h.permission || h.role || '-'}</code></td>
                  <td style={{ padding: '0.75rem' }}>{h.changedBy}</td>
                  <td style={{ padding: '0.75rem' }}>{new Date(h.timestamp).toLocaleString()}</td>
                  <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>{h.reason || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modals */}
      {showTempForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ width: '450px' }}>
            <h3>Grant Temporary Permission</h3>
            <form onSubmit={handleCreateTempPerm}>
              <label className="field">
                <span>Select Staff User</span>
                <select className="input" value={tempUserId} onChange={(e) => setTempUserId(e.target.value)} required>
                  <option value="">-- Choose Staff User --</option>
                  {users.map(u => (
                    <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Target Permission Code</span>
                <select className="input" value={tempPermission} onChange={(e) => setTempPermission(e.target.value)} required>
                  <option value="">-- Choose Permission --</option>
                  {staticPermissions.map((p: string) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Start Clearance Time</span>
                <input type="datetime-local" className="input" value={tempStartTime} onChange={(e) => setTempStartTime(e.target.value)} required />
              </label>
              <label className="field">
                <span>Expiry Expiration Time</span>
                <input type="datetime-local" className="input" value={tempEndTime} onChange={(e) => setTempEndTime(e.target.value)} required />
              </label>
              <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowTempForm(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Grant Access</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showDirectForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ width: '450px' }}>
            <h3>Direct User Permission Override</h3>
            <form onSubmit={handleDirectPermission}>
              <label className="field">
                <span>Select Staff User</span>
                <select className="input" value={directUserId} onChange={(e) => setDirectUserId(e.target.value)} required>
                  <option value="">-- Choose Staff User --</option>
                  {users.filter(x => x.role !== 'OWNER').map(u => (
                    <option key={u.id} value={u.id}>{u.name} ({u.role})</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Select Permission Code</span>
                <select className="input" value={directPermission} onChange={(e) => setDirectPermission(e.target.value)} required>
                  <option value="">-- Choose Permission --</option>
                  {staticPermissions.map((p: string) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Action Instruction</span>
                <select className="input" value={directAction} onChange={(e) => setDirectAction(e.target.value)}>
                  <option value="GRANT">GRANT (Explicit Allow Override)</option>
                  <option value="REVOKE">REVOKE (Explicit Block Override)</option>
                </select>
              </label>
              <label className="field">
                <span>Reason for Override</span>
                <input className="input" placeholder="e.g. Regular manager backup cover" value={directReason} onChange={(e) => setDirectReason(e.target.value)} required />
              </label>
              <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowDirectForm(false)}>Cancel</button>
                <button type="submit" className="btn btn-primary">Save Instruction</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
