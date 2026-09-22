import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export function WaiterDashboard() {
  const [assignedTables, setAssignedTables] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchTables()
  }, [])

  const fetchTables = async () => {
    try {
      setLoading(true)
      const res = await api.getFloor()
      setAssignedTables(res.tables || [])
    } catch (err) {
      console.error('Failed to load floor tables', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '900px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>Waiter Service Dashboard</h2>
        <span className="role-badge role-waiter">Waiter stand</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '2rem' }}>
        {/* Left Side: Actions */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '1rem' }}>Waiter Actions</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Link to="/floor" className="btn btn-primary btn-block" style={{ textDecoration: 'none' }}>
              Open Interactive Seating Plan ◫
            </Link>
            <Link to="/billing" className="btn btn-secondary btn-block" style={{ textDecoration: 'none' }}>
              View Billing Details $
            </Link>
          </div>
        </div>

        {/* Right Side: Floor Tables Summary */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
          <h3 style={{ marginBottom: '1rem' }}>Dining Tables Overview</h3>
          {loading ? (
            <p>Loading table layouts...</p>
          ) : assignedTables.length === 0 ? (
            <p className="panel-empty-hint">No tables found.</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
              {assignedTables.map((t) => (
                <div
                  key={t.id}
                  style={{
                    background: 'var(--surface-2)',
                    padding: '0.75rem',
                    borderRadius: '8px',
                    border: '1px solid var(--border)',
                    textAlign: 'center'
                  }}
                >
                  <strong>Table {t.number}</strong>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Cap: {t.capacity} | {t.type}
                  </div>
                  <div style={{ marginTop: '0.5rem' }}>
                    <span className={`role-badge role-${t.status.toLowerCase()}`} style={{ fontSize: '0.7rem' }}>
                      {t.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
