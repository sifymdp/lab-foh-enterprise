import { useEffect, useState } from 'react'
import { api } from '../api/client'

export function HealthGuardianPage() {
  const [status, setStatus] = useState<any | null>(null)
  const [audits, setAudits] = useState<any[]>([])
  const [incidents, setIncidents] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [triggering, setTriggering] = useState(false)
  const [resolvingId, setResolvingId] = useState<string | null>(null)
  const [resolveNotes, setResolveNotes] = useState('')

  const loadData = () => {
    setLoading(true)
    Promise.all([
      api.getHealthGuardianStatus().catch(() => null),
      api.getHealthGuardianAudits(10).catch(() => []),
      api.getHealthGuardianIncidents().catch(() => []),
    ])
      .then(([statusRes, auditsRes, incidentsRes]) => {
        setStatus(statusRes)
        setAudits(auditsRes || [])
        setIncidents(incidentsRes || [])
      })
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadData()
    const timer = setInterval(loadData, 30000)
    return () => clearInterval(timer)
  }, [])

  const handleTriggerAudit = async () => {
    setTriggering(true)
    try {
      await api.triggerHealthGuardianAudit()
      loadData()
    } catch (err) {
      console.error('Failed to trigger audit', err)
    } finally {
      setTriggering(false)
    }
  }

  const handleResolveIncident = async (incidentId: string) => {
    try {
      await api.resolveHealthGuardianIncident(incidentId, resolveNotes || 'Manually resolved by administrator')
      setResolvingId(null)
      setResolveNotes('')
      loadData()
    } catch (err) {
      console.error('Failed to resolve incident', err)
    }
  }

  const overallStatus = status?.overall_status || 'UNKNOWN'
  const isHealthy = overallStatus === 'HEALTHY'

  return (
    <div className="page-container" style={{ padding: '1.25rem' }}>
      <header style={{ marginBottom: '1.25rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Backend Health Guardian</h1>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: 700,
                padding: '0.2rem 0.6rem',
                borderRadius: 6,
                background: isHealthy ? '#dcfce7' : '#fee2e2',
                color: isHealthy ? '#16a34a' : '#dc2626',
              }}
            >
              {overallStatus}
            </span>
            {loading && <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Probing subsystems...</span>}
          </div>
          <p className="muted" style={{ margin: 0, fontSize: '0.875rem' }}>
            Autonomous 12-hour comprehensive diagnostics • Allowlisted safe self-recovery • Reliability ledger
          </p>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleTriggerAudit}
          disabled={triggering}
        >
          {triggering ? 'Running Comprehensive Audit...' : '⚡ Run Comprehensive Audit Now'}
        </button>
      </header>

      {/* Schedule Banner */}
      <div className="guardian-header-banner">
        <div>
          <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Autonomous Audit Cycle</div>
          <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8' }}>
            Persistent Every 12 Hours
          </div>
          <div style={{ fontSize: '0.8rem', color: '#cbd5e1', marginTop: 4 }}>
            Last Audit:{' '}
            {status?.last_audit_at ? new Date(status.last_audit_at).toLocaleString() : 'Pending initial run'}{' '}
            • Next Scheduled: {status?.next_scheduled_run ? new Date(status.next_scheduled_run).toLocaleString() : 'Calculating...'}
          </div>
        </div>

        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Active Incidents</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 700, color: (status?.open_incidents_count || 0) > 0 ? '#f87171' : '#4ade80' }}>
            {status?.open_incidents_count ?? 0}
          </div>
        </div>
      </div>

      {/* Component Probes Grid */}
      <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Monitored Subsystems</h3>
      <div className="guardian-card-grid">
        {(status?.components || []).map((comp: any) => {
          const pass = comp.status === 'PASS'
          const warn = comp.status === 'WARN'
          return (
            <div
              key={comp.component}
              className={`guardian-card ${pass ? 'guardian-card--pass' : warn ? 'guardian-card--warn' : 'guardian-card--fail'}`}
            >
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                  <strong style={{ fontSize: '0.95rem' }}>{comp.component.replace(/_/g, ' ')}</strong>
                  <span
                    style={{
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      padding: '2px 6px',
                      borderRadius: 4,
                      background: pass ? '#dcfce7' : warn ? '#fef3c7' : '#fee2e2',
                      color: pass ? '#15803d' : warn ? '#b45309' : '#b91c1c',
                    }}
                  >
                    {comp.status}
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-muted)' }}>{comp.message}</p>
              </div>

              <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-soft)', borderTop: '1px solid var(--border)', paddingTop: 6 }}>
                Probe Latency: <strong>{comp.latency_ms}ms</strong>
              </div>
            </div>
          )
        })}
      </div>

      {/* Active Incidents & Recovery Section */}
      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>Operational Incidents & Self-Recovery Ledger</h3>
        {incidents.length === 0 ? (
          <div style={{ padding: '1.5rem', background: 'var(--surface)', borderRadius: 10, border: '1px solid var(--border)', color: 'var(--text-muted)' }}>
            ✓ Zero active incidents. All subsystems operating within normal parameters.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', background: 'var(--surface)', borderRadius: 10, border: '1px solid var(--border)' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                  <th style={{ padding: '0.75rem 1rem' }}>Component</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Severity</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Category</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Description</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Recovery Actions</th>
                  <th style={{ padding: '0.75rem 1rem' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <tr key={inc.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{inc.component}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span style={{ color: inc.severity === 'CRITICAL' ? '#dc2626' : '#ea580c', fontWeight: 600 }}>
                        {inc.severity}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem', color: 'var(--text-muted)' }}>{inc.error_category}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>{inc.description}</td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      <span style={{ fontWeight: 600, color: inc.status === 'RESOLVED' ? '#16a34a' : '#d97706' }}>
                        {inc.status}
                      </span>
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {inc.recovery_logs?.length > 0
                        ? inc.recovery_logs.map((r: any) => `${r.action_name}: ${r.status}`).join(', ')
                        : 'None'}
                    </td>
                    <td style={{ padding: '0.75rem 1rem' }}>
                      {inc.status !== 'RESOLVED' && (
                        <button
                          type="button"
                          className="btn btn-sm btn-secondary"
                          onClick={() => setResolvingId(inc.id)}
                        >
                          Resolve
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Recent Audits Table */}
      <div style={{ marginTop: '2rem' }}>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>12-Hour Audit History</h3>
        <div style={{ overflowX: 'auto', background: 'var(--surface)', borderRadius: 10, border: '1px solid var(--border)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: 'var(--surface-2)', borderBottom: '1px solid var(--border)', textAlign: 'left' }}>
                <th style={{ padding: '0.75rem 1rem' }}>Audit ID</th>
                <th style={{ padding: '0.75rem 1rem' }}>Type</th>
                <th style={{ padding: '0.75rem 1rem' }}>Overall Status</th>
                <th style={{ padding: '0.75rem 1rem' }}>Execution Time</th>
                <th style={{ padding: '0.75rem 1rem' }}>Duration</th>
                <th style={{ padding: '0.75rem 1rem' }}>Next Scheduled Run</th>
              </tr>
            </thead>
            <tbody>
              {audits.map((a) => (
                <tr key={a.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace' }}>{a.id}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>{a.audit_type}</td>
                  <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{a.overall_status}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>{a.started_at ? new Date(a.started_at).toLocaleString() : ''}</td>
                  <td style={{ padding: '0.75rem 1rem' }}>{a.duration_ms}ms</td>
                  <td style={{ padding: '0.75rem 1rem' }}>{a.next_scheduled_run ? new Date(a.next_scheduled_run).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Resolve Incident Dialog */}
      {resolvingId && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 9999 }}>
          <div style={{ background: 'var(--surface)', padding: '1.5rem', borderRadius: 12, maxWidth: 440, width: '100%' }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Resolve Operational Incident</h3>
            <p className="muted" style={{ marginBottom: '1rem' }}>Provide administrator acknowledgement notes:</p>
            <textarea
              className="form-input"
              rows={3}
              value={resolveNotes}
              onChange={(e) => setResolveNotes(e.target.value)}
              placeholder="e.g. Manually restarted dependency and verified stream."
              style={{ width: '100%', marginBottom: '1rem' }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button type="button" className="btn btn-ghost" onClick={() => setResolvingId(null)}>
                Cancel
              </button>
              <button type="button" className="btn btn-primary" onClick={() => handleResolveIncident(resolvingId)}>
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
