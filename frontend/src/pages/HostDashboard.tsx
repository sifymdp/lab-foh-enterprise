import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'

export function HostDashboard() {
  const [tableStats, setTableStats] = useState<any>(null)
  const [reservations, setReservations] = useState<any[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [floor, resList] = await Promise.all([
        api.getFloor().then(f => f.tables),
        api.getSessions().then(s => s.filter(session => session.status === 'RESERVED')) // fetch reservation sessions
      ])

      if (floor) {
        setTableStats({
          total: floor.length,
          available: floor.filter((t: any) => t.status === 'AVAILABLE').length,
          reserved: floor.filter((t: any) => t.status === 'RESERVED').length,
          seated: floor.filter((t: any) => t.status === 'SEATED' || t.status === 'ACTIVE').length,
          cleaning: floor.filter((t: any) => t.status === 'CLEANING').length
        })
      }
      // Set reservations list
      setReservations(resList)
    } catch (err) {
      console.error('Failed to load host Stand statistics', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', maxWidth: '1000px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2>FOH Host Stand Overview</h2>
        <span className="role-badge role-host">Host stand</span>
      </div>

      {loading ? (
        <p>Loading stand statistics...</p>
      ) : (
        <div>
          {/* KPI Seating Grid */}
          {tableStats && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1.5rem', marginBottom: '2rem' }}>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Available Tables</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--success)', marginTop: '0.25rem' }}>
                  {tableStats.available}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Reserved Tables</span>
                <h3 style={{ fontSize: '2rem', color: '#eab308', marginTop: '0.25rem' }}>
                  {tableStats.reserved}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Seated Dining Guests</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--primary)', marginTop: '0.25rem' }}>
                  {tableStats.seated}
                </h3>
              </div>
              <div style={{ background: 'var(--bg-elevated)', padding: '1.25rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
                <span className="muted">Cleaning Tables</span>
                <h3 style={{ fontSize: '2rem', color: 'var(--text-soft)', marginTop: '0.25rem' }}>
                  {tableStats.cleaning}
                </h3>
              </div>
            </div>
          )}

          {/* Quick links & active reservations */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
            {/* Quick Actions Panel */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1.25rem' }}>FOH Actions</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <Link to="/floor" className="btn btn-primary btn-block" style={{ textDecoration: 'none' }}>
                  Open Interactive Floor Plan ◫
                </Link>
                <Link to="/reservations" className="btn btn-secondary btn-block" style={{ textDecoration: 'none' }}>
                  View Reservations Stand 📅
                </Link>
              </div>
            </div>

            {/* Active Seating / Reserved */}
            <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)' }}>
              <h3 style={{ marginBottom: '1rem' }}>Active Reservations</h3>
              {reservations.length === 0 ? (
                <p className="panel-empty-hint">No active reservations at this time.</p>
              ) : (
                <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                  {reservations.map((r, idx) => (
                    <div key={idx} style={{ borderBottom: '1px solid var(--border)', padding: '0.5rem 0', fontSize: '0.9rem' }}>
                      <p>Guest: <strong>{r.guestName || 'Walk-in'}</strong> ({r.partySize} guests)</p>
                      <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>Table: {r.tableId.replace('t-', '')} | Seated at: {new Date(r.seatedAt).toLocaleTimeString()}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
