import { useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'

interface UserSessionItem {
  id: string
  userId: string
  userName: string
  role: string
  device: string
  loginTime: string
  lastActivity: string
  status: string
}

export function StaffSessionsPage() {
  const [sessions, setSessions] = useState<UserSessionItem[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Filter States
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedDate, setSelectedDate] = useState('')
  const [selectedTimePeriod, setSelectedTimePeriod] = useState('ALL')
  const [selectedRole, setSelectedRole] = useState('ALL')
  const [selectedStatus, setSelectedStatus] = useState('ALL')

  useEffect(() => {
    loadSessions()
  }, [])

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(null), 4000)
  }

  const loadSessions = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.listActiveSessions()
      setSessions(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to retrieve active sessions')
    } finally {
      setLoading(false)
    }
  }

  const handleRevokeSession = async (sessId: string) => {
    try {
      await api.forceLogoutSession(sessId)
      showSuccess('Client session terminated successfully')
      loadSessions()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Session revocation failed')
    }
  }

  // Quick Date Preset Helpers
  const setQuickDate = (type: 'today' | 'yesterday' | 'all') => {
    if (type === 'all') {
      setSelectedDate('')
      return
    }
    const d = new Date()
    if (type === 'yesterday') {
      d.setDate(d.getDate() - 1)
    }
    const yyyy = d.getFullYear()
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const dd = String(d.getDate()).padStart(2, '0')
    setSelectedDate(`${yyyy}-${mm}-${dd}`)
  }

  const handleResetFilters = () => {
    setSearchQuery('')
    setSelectedDate('')
    setSelectedTimePeriod('ALL')
    setSelectedRole('ALL')
    setSelectedStatus('ALL')
  }

  const isFiltered = Boolean(
    searchQuery.trim() ||
    selectedDate ||
    selectedTimePeriod !== 'ALL' ||
    selectedRole !== 'ALL' ||
    selectedStatus !== 'ALL'
  )

  // Filter & Search Logic
  const filteredSessions = useMemo(() => {
    return sessions.filter((s) => {
      // 1. Universal Search Match (Name, Role, Device, ID, formatted times)
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const loginStr = new Date(s.loginTime).toLocaleString().toLowerCase()
        const actStr = new Date(s.lastActivity).toLocaleString().toLowerCase()
        const matchesName = (s.userName || '').toLowerCase().includes(q)
        const matchesRole = (s.role || '').toLowerCase().includes(q)
        const matchesDevice = (s.device || '').toLowerCase().includes(q)
        const matchesLoginTime = loginStr.includes(q)
        const matchesActTime = actStr.includes(q)
        const matchesId = (s.id || '').toLowerCase().includes(q)

        if (!matchesName && !matchesRole && !matchesDevice && !matchesLoginTime && !matchesActTime && !matchesId) {
          return false
        }
      }

      // 2. Date Match (YYYY-MM-DD)
      if (selectedDate) {
        const loginDate = new Date(s.loginTime)
        const yyyy = loginDate.getFullYear()
        const mm = String(loginDate.getMonth() + 1).padStart(2, '0')
        const dd = String(loginDate.getDate()).padStart(2, '0')
        const sDateStr = `${yyyy}-${mm}-${dd}`
        if (sDateStr !== selectedDate) {
          return false
        }
      }

      // 3. Time Period Match
      if (selectedTimePeriod !== 'ALL') {
        const loginHour = new Date(s.loginTime).getHours()
        if (selectedTimePeriod === 'MORNING') {
          // 06:00 - 11:59
          if (loginHour < 6 || loginHour >= 12) return false
        } else if (selectedTimePeriod === 'AFTERNOON') {
          // 12:00 - 16:59
          if (loginHour < 12 || loginHour >= 17) return false
        } else if (selectedTimePeriod === 'EVENING') {
          // 17:00 - 21:59
          if (loginHour < 17 || loginHour >= 22) return false
        } else if (selectedTimePeriod === 'NIGHT') {
          // 22:00 - 05:59
          if (loginHour >= 6 && loginHour < 22) return false
        }
      }

      // 4. Role Match
      if (selectedRole !== 'ALL') {
        if ((s.role || '').toUpperCase() !== selectedRole.toUpperCase()) {
          return false
        }
      }

      // 5. Status Match
      if (selectedStatus !== 'ALL') {
        if ((s.status || '').toUpperCase() !== selectedStatus.toUpperCase()) {
          return false
        }
      }

      return true
    })
  }, [sessions, searchQuery, selectedDate, selectedTimePeriod, selectedRole, selectedStatus])

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1280px', margin: '0 auto' }}>
      {/* ── Page Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700 }}>Active Login Sessions</h2>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.95rem' }}>
            Monitor staff logged-in devices, search session logs by date & time, and revoke sessions instantly
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
          <button className="btn btn-secondary btn-sm" onClick={loadSessions} disabled={loading}>
            {loading ? '↻ Refreshing…' : '↻ Refresh Sessions'}
          </button>
        </div>
      </div>

      {/* ── Alerts ── */}
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

      {/* ── Search & Filter Control Panel ── */}
      <div style={{
        background: 'var(--bg-elevated)',
        padding: '1.25rem',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow-sm)',
        marginBottom: '1.5rem',
      }}>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1rem',
          alignItems: 'flex-end',
        }}>
          {/* 1. Name / Keyword Search */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-muted)' }}>
              🔍 Search Staff Name or Device
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type="text"
                className="input-field"
                placeholder="e.g. Alex, Chrome, Waiter..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{ width: '100%', padding: '0.55rem 0.75rem', paddingRight: searchQuery ? '2rem' : '0.75rem' }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: '0.5rem',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'none',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.9rem',
                  }}
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>
          </div>

          {/* 2. Login Date Filter */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.35rem' }}>
              <label style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                📅 Login Date
              </label>
              <div style={{ display: 'flex', gap: '0.3rem' }}>
                <button
                  type="button"
                  onClick={() => setQuickDate('today')}
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border)',
                    background: selectedDate === new Date().toISOString().split('T')[0] ? 'var(--primary)' : 'var(--surface-2)',
                    color: selectedDate === new Date().toISOString().split('T')[0] ? '#fff' : 'inherit',
                    cursor: 'pointer',
                  }}
                >
                  Today
                </button>
                <button
                  type="button"
                  onClick={() => setQuickDate('yesterday')}
                  style={{
                    fontSize: '0.72rem',
                    padding: '0.1rem 0.4rem',
                    borderRadius: '4px',
                    border: '1px solid var(--border)',
                    background: 'var(--surface-2)',
                    cursor: 'pointer',
                  }}
                >
                  Yesterday
                </button>
              </div>
            </div>
            <input
              type="date"
              className="input-field"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              style={{ width: '100%', padding: '0.55rem 0.75rem' }}
            />
          </div>

          {/* 3. Time Period Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-muted)' }}>
              ⏰ Login Time of Day
            </label>
            <select
              className="input-field"
              value={selectedTimePeriod}
              onChange={(e) => setSelectedTimePeriod(e.target.value)}
              style={{ width: '100%', padding: '0.55rem 0.75rem' }}
            >
              <option value="ALL">All Hours (24 Hours)</option>
              <option value="MORNING">🌅 Morning (06:00 AM - 12:00 PM)</option>
              <option value="AFTERNOON">☀️ Afternoon (12:00 PM - 05:00 PM)</option>
              <option value="EVENING">🌆 Evening (05:00 PM - 10:00 PM)</option>
              <option value="NIGHT">🌙 Night / Late (10:00 PM - 06:00 AM)</option>
            </select>
          </div>

          {/* 4. Role Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-muted)' }}>
              🎭 Staff Role
            </label>
            <select
              className="input-field"
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              style={{ width: '100%', padding: '0.55rem 0.75rem' }}
            >
              <option value="ALL">All Roles</option>
              <option value="OWNER">Owner</option>
              <option value="MANAGER">Manager</option>
              <option value="HOST">Host</option>
              <option value="CASHIER">Cashier</option>
              <option value="WAITER">Waiter</option>
              <option value="CHEF">Chef</option>
            </select>
          </div>

          {/* 5. Status Filter */}
          <div>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.35rem', color: 'var(--text-muted)' }}>
              ⚡ Session Status
            </label>
            <select
              className="input-field"
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={{ width: '100%', padding: '0.55rem 0.75rem' }}
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">🟢 Active</option>
              <option value="REVOKED">🔴 Revoked / Logged Out</option>
            </select>
          </div>
        </div>

        {/* ── Active Filter Bar & Results Count ── */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginTop: '1rem',
          paddingTop: '0.75rem',
          borderTop: '1px solid var(--border)',
          flexWrap: 'wrap',
          gap: '0.5rem',
          fontSize: '0.875rem',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <span style={{ color: 'var(--text-muted)' }}>
              Showing <strong>{filteredSessions.length}</strong> of <strong>{sessions.length}</strong> total sessions
            </span>
            {isFiltered && (
              <span style={{
                background: 'var(--primary-soft)',
                color: 'var(--primary)',
                padding: '0.2rem 0.6rem',
                borderRadius: '12px',
                fontSize: '0.75rem',
                fontWeight: 600,
              }}>
                Filtered
              </span>
            )}
          </div>

          {isFiltered && (
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={handleResetFilters}
              style={{ fontSize: '0.8rem', color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              ✕ Reset All Filters
            </button>
          )}
        </div>
      </div>

      {/* ── Sessions Data Table ── */}
      <div style={{
        background: 'var(--bg-elevated)',
        padding: '1.5rem',
        borderRadius: 'var(--radius)',
        border: '1px solid var(--border)',
        boxShadow: 'var(--shadow-sm)',
        overflowX: 'auto',
      }}>
        {loading && sessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-muted)' }}>
            <div className="spinner" style={{ margin: '0 auto 0.75rem' }} />
            <p>Loading active sessions...</p>
          </div>
        ) : filteredSessions.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <p style={{ fontSize: '1.1rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
              No sessions found matching your criteria.
            </p>
            {isFiltered && (
              <button className="btn btn-secondary btn-sm" onClick={handleResetFilters}>
                Clear Search & Filters
              </button>
            )}
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                <th style={{ padding: '0.75rem', width: '180px' }}>Staff Member</th>
                <th style={{ padding: '0.75rem', width: '110px' }}>Role</th>
                <th style={{ padding: '0.75rem' }}>Device User-Agent</th>
                <th style={{ padding: '0.75rem', width: '180px' }}>Login Date & Time</th>
                <th style={{ padding: '0.75rem', width: '180px' }}>Last Activity</th>
                <th style={{ padding: '0.75rem', width: '100px' }}>Status</th>
                <th style={{ padding: '0.75rem', width: '120px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.map((s) => {
                const loginDateObj = new Date(s.loginTime)
                const lastActObj = new Date(s.lastActivity)

                return (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    {/* Staff Name */}
                    <td style={{ padding: '0.75rem' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text)' }}>{s.userName || 'Unknown Staff'}</div>
                      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontFamily: 'monospace' }}>
                        ID: {(s.id || '').substring(0, 8)}…
                      </span>
                    </td>

                    {/* Role Badge */}
                    <td style={{ padding: '0.75rem' }}>
                      <span className={`role-badge role-${(s.role || '').toLowerCase()}`}>
                        {s.role || 'Staff'}
                      </span>
                    </td>

                    {/* Device / User Agent */}
                    <td style={{ padding: '0.75rem', fontSize: '0.8rem', color: 'var(--text-muted)', maxWidth: '300px', wordBreak: 'break-word' }}>
                      {s.device || 'Standard Web Browser'}
                    </td>

                    {/* Login Timestamp */}
                    <td style={{ padding: '0.75rem', whiteSpace: 'nowrap' }}>
                      <div style={{ fontWeight: 500 }}>
                        {loginDateObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {loginDateObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                    </td>

                    {/* Last Activity */}
                    <td style={{ padding: '0.75rem', whiteSpace: 'nowrap' }}>
                      <div style={{ fontWeight: 500 }}>
                        {lastActObj.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                      </div>
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                        {lastActObj.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                      </div>
                    </td>

                    {/* Status */}
                    <td style={{ padding: '0.75rem' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '0.35rem',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        color: s.status === 'ACTIVE' ? 'var(--success)' : 'var(--danger)',
                        background: s.status === 'ACTIVE' ? 'rgba(22, 163, 74, 0.1)' : 'rgba(220, 38, 38, 0.1)',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '6px',
                      }}>
                        <span>{s.status === 'ACTIVE' ? '●' : '○'}</span>
                        {s.status}
                      </span>
                    </td>

                    {/* Action button */}
                    <td style={{ padding: '0.75rem', textAlign: 'right' }}>
                      {s.status === 'ACTIVE' ? (
                        <button
                          className="btn btn-ghost btn-sm"
                          style={{ color: 'var(--danger)', fontWeight: 600 }}
                          onClick={() => handleRevokeSession(s.id)}
                        >
                          Force Logout
                        </button>
                      ) : (
                        <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Logged Out</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
