import { useEffect, useState, useMemo } from 'react'
import { api } from '../api/client'
import type { AuditLog } from '../types'

const ACTION_COLORS: Record<string, { bg: string; text: string; icon: string }> = {
  LOGIN_SUCCESS:               { bg: '#dcfce7', text: '#16a34a', icon: '🔑' },
  LOGIN_FAILED:                { bg: '#fee2e2', text: '#dc2626', icon: '⚠️' },
  LOGIN_LOCKOUT_ATTEMPT:       { bg: '#fee2e2', text: '#991b1b', icon: '🚫' },
  ACCOUNT_LOCKED:              { bg: '#fef3c7', text: '#d97706', icon: '🔒' },
  ACCOUNT_UNLOCKED:            { bg: '#dbeafe', text: '#2563eb', icon: '🔓' },
  LOGOUT:                      { bg: '#f3f4f6', text: '#4b5563', icon: '🚪' },
  FORCE_LOGOUT:                { bg: '#fee2e2', text: '#dc2626', icon: '⚡' },
  GRANT_ROLE_PERMISSION:       { bg: '#ede9fe', text: '#7c3aed', icon: '🛡️' },
  REVOKE_ROLE_PERMISSION:      { bg: '#ffe4e6', text: '#e11d48', icon: '🗑️' },
  BULK_GRANT_ROLE_PERMISSIONS: { bg: '#ede9fe', text: '#6d28d9', icon: '⚡' },
  BULK_REVOKE_ROLE_PERMISSIONS:{ bg: '#ffe4e6', text: '#be123c', icon: '✕' },
  GRANT_TEMPORARY:             { bg: '#fef3c7', text: '#b45309', icon: '⏱️' },
  STATUS_CHANGE:               { bg: '#e0f2fe', text: '#0284c7', icon: '◫' },
  BILL_PAID:                   { bg: '#dcfce7', text: '#15803d', icon: '💰' },
}

export function AuditLogsPage() {
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Search & Filter state
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('ALL')
  const [resourceFilter, setResourceFilter] = useState('ALL')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [datePreset, setDatePreset] = useState<'ALL' | 'TODAY' | 'YESTERDAY' | 'WEEK' | 'MONTH'>('ALL')

  // Detail Modal for specific record
  const [selectedRecord, setSelectedRecord] = useState<AuditLog | null>(null)

  // Format Date as local YYYY-MM-DDTHH:mm (no UTC shift)
  const toLocalStr = (d: Date) => {
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
  }

  useEffect(() => {
    fetchLogs()
  }, [startDate, endDate, actionFilter, resourceFilter])

  const fetchLogs = async () => {
    try {
      setLoading(true)
      setError('')
      const params: any = {}
      if (actionFilter !== 'ALL') params.action = actionFilter
      if (resourceFilter !== 'ALL') params.resource_type = resourceFilter
      // Send the local datetime string directly — no UTC conversion
      if (startDate) params.start_date = startDate
      if (endDate) params.end_date = endDate

      const res = await api.getAuditLogs(params)
      setLogs(res)
    } catch (err: any) {
      setError(err.message || 'Failed to load audit logs')
    } finally {
      setLoading(false)
    }
  }

  // Handle Quick Date Presets
  const applyDatePreset = (preset: 'ALL' | 'TODAY' | 'YESTERDAY' | 'WEEK' | 'MONTH') => {
    setDatePreset(preset)
    const now = new Date()

    if (preset === 'ALL') {
      setStartDate('')
      setEndDate('')
      return
    }

    if (preset === 'TODAY') {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0)
      setStartDate(toLocalStr(start))
      setEndDate(toLocalStr(now))
      return
    }

    if (preset === 'YESTERDAY') {
      const start = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 0, 0, 0)
      const end = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 23, 59, 59)
      setStartDate(toLocalStr(start))
      setEndDate(toLocalStr(end))
      return
    }

    if (preset === 'WEEK') {
      const start = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      setStartDate(toLocalStr(start))
      setEndDate(toLocalStr(now))
      return
    }

    if (preset === 'MONTH') {
      const start = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      setStartDate(toLocalStr(start))
      setEndDate(toLocalStr(now))
      return
    }
  }

  // Unique actions and resources for filter dropdowns
  const availableActions = useMemo(() => {
    const set = new Set<string>()
    logs.forEach((l) => set.add(l.action))
    return Array.from(set).sort()
  }, [logs])

  const availableResources = useMemo(() => {
    const set = new Set<string>()
    logs.forEach((l) => {
      if (l.resourceType) set.add(l.resourceType)
    })
    return Array.from(set).sort()
  }, [logs])

  // Filter logs locally by search keyword
  const filteredLogs = useMemo(() => {
    if (!search.trim()) return logs
    const q = search.toLowerCase()
    return logs.filter((l) => {
      return (
        l.action.toLowerCase().includes(q) ||
        (l.resourceType && l.resourceType.toLowerCase().includes(q)) ||
        (l.resourceId && l.resourceId.toLowerCase().includes(q)) ||
        (l.userName && l.userName.toLowerCase().includes(q)) ||
        (l.userEmail && l.userEmail.toLowerCase().includes(q)) ||
        (l.userRole && l.userRole.toLowerCase().includes(q)) ||
        (l.newValue && l.newValue.toLowerCase().includes(q)) ||
        (l.oldValue && l.oldValue.toLowerCase().includes(q))
      )
    })
  }, [logs, search])

  // Export filtered logs to CSV
  const handleExportCSV = () => {
    if (!filteredLogs.length) return
    const headers = ['Timestamp', 'Actor Name', 'Actor Email', 'Actor Role', 'Action', 'Resource Type', 'Resource ID', 'Old Value', 'New Value']
    const rows = filteredLogs.map((l) => [
      new Date(l.createdAt).toLocaleString(),
      l.userName || 'System',
      l.userEmail || '-',
      l.userRole || '-',
      l.action,
      l.resourceType,
      l.resourceId || '-',
      l.oldValue ? JSON.stringify(l.oldValue) : '-',
      l.newValue ? JSON.stringify(l.newValue) : '-',
    ])

    const csvContent = [headers.join(','), ...rows.map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))].join('\n')
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.setAttribute('href', url)
    link.setAttribute('download', `audit_logs_${new Date().toISOString().slice(0, 10)}.csv`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  // Parse JSON safely
  const tryFormatJson = (val: string | null | undefined) => {
    if (!val) return null
    try {
      const parsed = JSON.parse(val)
      return JSON.stringify(parsed, null, 2)
    } catch {
      return val
    }
  }

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1180px', margin: '0 auto' }}>

      {/* ── Page Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: '0 0 0.25rem' }}>System Audit Logs</h2>
          <p className="muted" style={{ margin: 0, fontSize: '0.86rem' }}>
            Comprehensive immutable activity trail of role assignments, user access, and operational events
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.6rem' }}>
          <button className="btn btn-ghost btn-sm" onClick={handleExportCSV} disabled={!filteredLogs.length}>
            📥 Export CSV
          </button>
          <button className="btn btn-primary btn-sm" onClick={fetchLogs} disabled={loading}>
            {loading ? 'Refreshing…' : '↻ Refresh Trail'}
          </button>
        </div>
      </div>

      {/* ── Date & Time Filter Bar ── */}
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        padding: '1.25rem',
        marginBottom: '1.5rem',
        boxShadow: 'var(--shadow-sm)',
      }}>
        {/* Presets + Custom Date Range */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', marginBottom: '1rem' }}>
          {/* Presets */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-muted)', marginRight: '0.3rem', textTransform: 'uppercase' }}>
              Time Range:
            </span>
            {(['ALL', 'TODAY', 'YESTERDAY', 'WEEK', 'MONTH'] as const).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => applyDatePreset(p)}
                style={{
                  padding: '0.35rem 0.75rem',
                  borderRadius: '6px',
                  border: datePreset === p ? '1.5px solid #3b82f6' : '1px solid var(--border)',
                  background: datePreset === p ? '#eff6ff' : 'var(--surface-2)',
                  color: datePreset === p ? '#1d4ed8' : 'var(--text)',
                  fontWeight: datePreset === p ? 700 : 500,
                  fontSize: '0.78rem',
                  cursor: 'pointer',
                  transition: 'all 0.12s',
                }}
              >
                {p === 'ALL' ? 'All Time' : p === 'TODAY' ? 'Today' : p === 'YESTERDAY' ? 'Yesterday' : p === 'WEEK' ? 'Past 7 Days' : 'Past 30 Days'}
              </button>
            ))}
          </div>

          {/* Custom Date Inputs */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>From:</span>
              <input
                type="datetime-local"
                className="input"
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.5rem', width: '190px' }}
                value={startDate}
                onChange={(e) => {
                  setStartDate(e.target.value)
                  setDatePreset('ALL')
                }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontWeight: 600 }}>To:</span>
              <input
                type="datetime-local"
                className="input"
                style={{ fontSize: '0.78rem', padding: '0.3rem 0.5rem', width: '190px' }}
                value={endDate}
                onChange={(e) => {
                  setEndDate(e.target.value)
                  setDatePreset('ALL')
                }}
              />
            </div>
            {(startDate || endDate) && (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setStartDate('')
                  setEndDate('')
                  setDatePreset('ALL')
                }}
                style={{ fontSize: '0.75rem', padding: '0.2rem 0.4rem', color: '#dc2626' }}
              >
                Clear
              </button>
            )}
          </div>
        </div>

        {/* Search & Dropdown Filters */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: '0.75rem' }}>
          <input
            className="input"
            type="text"
            placeholder="🔍 Search actions, actors, emails, resource IDs, change diffs…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ width: '100%', fontSize: '0.86rem' }}
          />

          {/* Action Filter */}
          <select
            className="input"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            style={{ fontSize: '0.84rem', minWidth: '160px' }}
          >
            <option value="ALL">All Actions ({availableActions.length})</option>
            {availableActions.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>

          {/* Resource Filter */}
          <select
            className="input"
            value={resourceFilter}
            onChange={(e) => setResourceFilter(e.target.value)}
            style={{ fontSize: '0.84rem', minWidth: '150px' }}
          >
            <option value="ALL">All Resources ({availableResources.length})</option>
            {availableResources.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div style={{
          padding: '0.75rem 1rem', borderRadius: '8px', marginBottom: '1.25rem',
          background: '#fef2f2', border: '1px solid #fca5a5', color: '#dc2626', fontSize: '0.86rem',
        }}>
          {error}
        </div>
      )}

      {/* ── Audit Logs Table ── */}
      <div style={{
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border)',
        borderRadius: '12px',
        overflow: 'hidden',
        boxShadow: 'var(--shadow-sm)',
      }}>
        <div style={{
          padding: '0.75rem 1.25rem',
          borderBottom: '1px solid var(--border)',
          background: 'var(--surface-2)',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            Showing {filteredLogs.length} Audit Events
          </span>
          <span className="muted" style={{ fontSize: '0.78rem' }}>
            Click any row or "View Details" to inspect the specific record
          </span>
        </div>

        {loading ? (
          <div style={{ padding: '3.5rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <div className="spinner" style={{ margin: '0 auto 0.75rem' }} />
            Loading audit records from database…
          </div>
        ) : filteredLogs.length === 0 ? (
          <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <span style={{ fontSize: '2rem', display: 'block', marginBottom: '0.5rem' }}>📋</span>
            No audit records matched your filter criteria.
          </div>
        ) : (
          <div style={{ maxHeight: '650px', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.84rem' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '0.65rem 1rem', width: '180px' }}>Date & Time</th>
                  <th style={{ padding: '0.65rem 1rem' }}>Actor</th>
                  <th style={{ padding: '0.65rem 1rem' }}>Action</th>
                  <th style={{ padding: '0.65rem 1rem' }}>Target Resource</th>
                  <th style={{ padding: '0.65rem 1rem' }}>Changes Summary</th>
                  <th style={{ padding: '0.65rem 1rem', textAlign: 'center', width: '100px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.map((log) => {
                  const actionStyle = ACTION_COLORS[log.action] ?? { bg: '#f3f4f6', text: '#374151', icon: '📝' }
                  const formattedDate = new Date(log.createdAt)

                  return (
                    <tr
                      key={log.id}
                      onClick={() => setSelectedRecord(log)}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        cursor: 'pointer',
                        transition: 'background 0.12s',
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--surface-2)')}
                      onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                      {/* Date & Time */}
                      <td style={{ padding: '0.75rem 1rem', whiteSpace: 'nowrap' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text)' }}>
                          {formattedDate.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
                        </div>
                        <div className="muted" style={{ fontSize: '0.75rem' }}>
                          {formattedDate.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </div>
                      </td>

                      {/* Actor */}
                      <td style={{ padding: '0.75rem 1rem' }}>
                        {log.userName ? (
                          <div>
                            <span style={{ fontWeight: 600, color: 'var(--text)' }}>{log.userName}</span>
                            {log.userRole && (
                              <span style={{
                                marginLeft: '0.4rem', fontSize: '0.68rem', fontWeight: 700,
                                padding: '0.05rem 0.35rem', borderRadius: '4px', background: '#e0e7ff', color: '#4338ca',
                              }}>
                                {log.userRole}
                              </span>
                            )}
                            <div className="muted" style={{ fontSize: '0.72rem' }}>{log.userEmail}</div>
                          </div>
                        ) : log.userId ? (
                          <span className="muted" style={{ fontFamily: 'monospace', fontSize: '0.78rem' }}>{log.userId}</span>
                        ) : (
                          <span style={{ color: '#6b7280', fontStyle: 'italic' }}>System automated</span>
                        )}
                      </td>

                      {/* Action */}
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                          padding: '0.2rem 0.55rem', borderRadius: '6px',
                          background: actionStyle.bg, color: actionStyle.text,
                          fontWeight: 700, fontSize: '0.78rem',
                        }}>
                          <span>{actionStyle.icon}</span>
                          <span>{log.action}</span>
                        </span>
                      </td>

                      {/* Target Resource */}
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <div style={{ fontWeight: 600 }}>{log.resourceType}</div>
                        {log.resourceId && (
                          <code style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                            {log.resourceId.length > 20 ? `${log.resourceId.slice(0, 18)}…` : log.resourceId}
                          </code>
                        )}
                      </td>

                      {/* Changes Summary */}
                      <td style={{ padding: '0.75rem 1rem', maxWidth: '300px' }}>
                        {log.newValue ? (
                          <div style={{
                            fontSize: '0.76rem', color: '#16a34a', background: '#f0fdf4',
                            padding: '0.25rem 0.5rem', borderRadius: '4px', overflow: 'hidden',
                            textOverflow: 'ellipsis', whiteSpace: 'nowrap', border: '1px solid #dcfce7',
                          }}>
                            {log.newValue}
                          </div>
                        ) : log.oldValue ? (
                          <div style={{
                            fontSize: '0.76rem', color: '#dc2626', background: '#fef2f2',
                            padding: '0.25rem 0.5rem', borderRadius: '4px', overflow: 'hidden',
                            textOverflow: 'ellipsis', whiteSpace: 'nowrap', border: '1px solid #fee2e2',
                          }}>
                            {log.oldValue}
                          </div>
                        ) : (
                          <span className="muted" style={{ fontSize: '0.75rem' }}>No payload diff</span>
                        )}
                      </td>

                      {/* Action Button */}
                      <td style={{ padding: '0.75rem 1rem', textAlign: 'center' }}>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedRecord(log)
                          }}
                          style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem' }}
                        >
                          👁 Details
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

      {/* ══════════════════════════════════════════════════════════
          SPECIFIC RECORD INSPECTION MODAL
      ══════════════════════════════════════════════════════════ */}
      {selectedRecord && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" onClick={() => setSelectedRecord(null)}>
          <div
            className="modal"
            style={{ maxWidth: '640px', maxHeight: '90vh', overflowY: 'auto' }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
              <div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: '0.35rem',
                  padding: '0.25rem 0.65rem', borderRadius: '6px',
                  background: (ACTION_COLORS[selectedRecord.action] ?? { bg: '#f3f4f6' }).bg,
                  color: (ACTION_COLORS[selectedRecord.action] ?? { text: '#374151' }).text,
                  fontWeight: 700, fontSize: '0.82rem', marginBottom: '0.5rem',
                }}>
                  <span>{(ACTION_COLORS[selectedRecord.action] ?? { icon: '📝' }).icon}</span>
                  <span>{selectedRecord.action}</span>
                </span>
                <h3 style={{ margin: 0, fontSize: '1.1rem' }}>Audit Event Record</h3>
              </div>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => setSelectedRecord(null)}
                style={{ fontSize: '1.2rem', padding: '0.2rem 0.5rem' }}
              >
                ✕
              </button>
            </div>

            {/* Event Metadata Grid */}
            <div style={{
              display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem',
              background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.25rem',
            }}>
              <div>
                <span className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700 }}>
                  Date & Time
                </span>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginTop: '0.15rem' }}>
                  {new Date(selectedRecord.createdAt).toLocaleString(undefined, {
                    dateStyle: 'full',
                    timeStyle: 'medium',
                  })}
                </div>
              </div>

              <div>
                <span className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700 }}>
                  Actor (User)
                </span>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginTop: '0.15rem' }}>
                  {selectedRecord.userName ? `${selectedRecord.userName} (${selectedRecord.userRole || 'User'})` : 'System Process'}
                </div>
                {selectedRecord.userEmail && (
                  <div className="muted" style={{ fontSize: '0.75rem' }}>{selectedRecord.userEmail}</div>
                )}
              </div>

              <div>
                <span className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700 }}>
                  Resource Type
                </span>
                <div style={{ fontWeight: 600, fontSize: '0.88rem', marginTop: '0.15rem' }}>
                  {selectedRecord.resourceType}
                </div>
              </div>

              <div>
                <span className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700 }}>
                  Resource Target ID
                </span>
                <div style={{ fontFamily: 'monospace', fontSize: '0.8rem', marginTop: '0.15rem' }}>
                  {selectedRecord.resourceId || 'N/A'}
                </div>
              </div>

              <div style={{ gridColumn: 'span 2' }}>
                <span className="muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700 }}>
                  Audit Log Record ID
                </span>
                <div style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  {selectedRecord.id}
                </div>
              </div>
            </div>

            {/* Change Payload Diff */}
            <div style={{ marginBottom: '1.25rem' }}>
              <h4 style={{ margin: '0 0 0.6rem', fontSize: '0.9rem' }}>Recorded Payload Changes</h4>

              {/* New Value */}
              {selectedRecord.newValue && (
                <div style={{ marginBottom: '0.75rem' }}>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#16a34a', textTransform: 'uppercase' }}>
                    + New / Applied State
                  </span>
                  <pre style={{
                    background: '#f0fdf4', border: '1px solid #bbf7d0', color: '#166534',
                    padding: '0.75rem', borderRadius: '6px', fontSize: '0.78rem',
                    maxHeight: '180px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                  }}>
                    {tryFormatJson(selectedRecord.newValue)}
                  </pre>
                </div>
              )}

              {/* Old Value */}
              {selectedRecord.oldValue && (
                <div>
                  <span style={{ fontSize: '0.75rem', fontWeight: 700, color: '#dc2626', textTransform: 'uppercase' }}>
                    - Previous / Old State
                  </span>
                  <pre style={{
                    background: '#fef2f2', border: '1px solid #fecaca', color: '#991b1b',
                    padding: '0.75rem', borderRadius: '6px', fontSize: '0.78rem',
                    maxHeight: '180px', overflowY: 'auto', whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                  }}>
                    {tryFormatJson(selectedRecord.oldValue)}
                  </pre>
                </div>
              )}

              {!selectedRecord.newValue && !selectedRecord.oldValue && (
                <div className="muted" style={{ fontSize: '0.82rem', fontStyle: 'italic', padding: '0.5rem 0' }}>
                  No payload diff recorded for this system action.
                </div>
              )}
            </div>

            {/* Modal Actions */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => setSelectedRecord(null)}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
