import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Role } from '../types'

const ROLES: Role[] = ['OWNER', 'MANAGER', 'HOST', 'WAITER', 'CASHIER', 'CHEF']

export function UsersPage() {
  const [users, setUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [showForm, setShowForm] = useState(false)
  const [editingUser, setEditingUser] = useState<any | null>(null)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('WAITER')
  const [status, setStatus] = useState('ACTIVE')
  const [branchId, setBranchId] = useState('')

  useEffect(() => {
    load()
  }, [])

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(null), 4000)
  }

  async function load() {
    setLoading(true)
    setError(null)
    try {
      setUsers(await api.getUsers())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    try {
      if (editingUser) {
        await api.updateUser(editingUser.id, {
          name,
          email,
          role,
          status,
          branch_id: branchId || null
        })
        showSuccess('User updated successfully')
      } else {
        await api.createUser({
          name,
          email,
          password,
          role,
          branch_id: branchId || null,
          status,
        } as any)
        showSuccess('New staff user account created')
      }
      setShowForm(false)
      setName('')
      setEmail('')
      setPassword('')
      setRole('WAITER')
      setStatus('ACTIVE')
      setBranchId('')
      setEditingUser(null)
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save user')
    }
  }

  async function handleUnlockUser(userId: string) {
    try {
      await api.unlockUserAccount(userId)
      showSuccess('Brute-force lockout reset successfully')
      load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unlock failed')
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2>Staff Accounts Management</h2>
          <p className="muted">Activate, deactivate, suspend, or unlock team accounts and assign branches</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => {
          setEditingUser(null)
          setName('')
          setEmail('')
          setPassword('')
          setRole('WAITER')
          setStatus('ACTIVE')
          setBranchId('')
          setShowForm(true)
        }}>
          + Create User
        </button>
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

      {loading && !successMsg ? (
        <div className="page-loading inline">
          <div className="spinner" />
          <p>Refreshing users list...</p>
        </div>
      ) : (
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ padding: '0.75rem' }}>Name</th>
                <th style={{ padding: '0.75rem' }}>Email</th>
                <th style={{ padding: '0.75rem' }}>Role</th>
                <th style={{ padding: '0.75rem' }}>Branch</th>
                <th style={{ padding: '0.75rem' }}>Status</th>
                <th style={{ padding: '0.75rem' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }} className={u.status !== 'ACTIVE' ? 'inactive' : ''}>
                  <td style={{ padding: '0.75rem' }}><strong>{u.name}</strong></td>
                  <td style={{ padding: '0.75rem' }}>{u.email}</td>
                  <td style={{ padding: '0.75rem' }}>
                    <span className={`role-badge role-${u.role.toLowerCase()}`}>
                      {u.role}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem', color: 'var(--text-muted)' }}>
                    {u.branchId ? (u.branchId === 'branch-demo' ? 'Main (Chennai)' : u.branchId) : 'Org-Wide'}
                  </td>
                  <td style={{ padding: '0.75rem' }}>
                    <span style={{
                      color: u.status === 'SUSPENDED' ? 'var(--danger)' : u.status === 'INACTIVE' ? 'var(--text-soft)' : 'var(--success)',
                      fontWeight: 600
                    }}>
                      {u.status}
                    </span>
                  </td>
                  <td style={{ padding: '0.75rem', display: 'flex', gap: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => {
                        setEditingUser(u)
                        setName(u.name)
                        setEmail(u.email)
                        setRole(u.role)
                        setStatus(u.status)
                        setBranchId(u.branchId || '')
                        setShowForm(true)
                      }}
                    >
                      Edit
                    </button>
                    {u.status === 'ACTIVE' && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--accent)' }}
                        onClick={() => handleUnlockUser(u.id)}
                      >
                        🔓 Reset Locks
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showForm && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal" style={{ width: '450px' }}>
            <h3>{editingUser ? 'Edit Staff Member' : 'Create Staff Member'}</h3>
            <form onSubmit={handleSave}>
              <label className="field">
                <span>Name</span>
                <input
                  className="input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </label>
              <label className="field">
                <span>Email</span>
                <input
                  type="email"
                  className="input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              {!editingUser && (
                <label className="field">
                  <span>Password</span>
                  <input
                    type="password"
                    className="input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={6}
                  />
                </label>
              )}
              <label className="field">
                <span>Role</span>
                <select
                  className="input"
                  value={role}
                  onChange={(e) => setRole(e.target.value as Role)}
                >
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Account Status</span>
                <select
                  className="input"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="ACTIVE">ACTIVE</option>
                  <option value="INACTIVE">INACTIVE</option>
                  <option value="SUSPENDED">SUSPENDED</option>
                </select>
              </label>
              <label className="field">
                <span>Branch Assignment</span>
                <select
                  className="input"
                  value={branchId}
                  onChange={(e) => setBranchId(e.target.value)}
                >
                  <option value="">Organization-wide (All Branches)</option>
                  <option value="branch-demo">Main Branch (Chennai)</option>
                  <option value="branch-bangalore">Bangalore Branch</option>
                </select>
              </label>
              <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
                <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
