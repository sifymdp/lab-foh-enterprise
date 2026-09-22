import { useMemo, useState } from 'react'
import { useFloor } from '../context/FloorContext'
import { SessionCard } from '../components/sessions/SessionCard'
import { EmptyState } from '../components/ui/EmptyState'

type Filter = 'ACTIVE' | 'ALL' | 'CLOSED'

export function SessionsPage() {
  const { floor, sessions, loading, changeStatus, closeSession, refresh } = useFloor()
  const [filter, setFilter] = useState<Filter>('ACTIVE')
  const [search, setSearch] = useState('')

  const filtered = useMemo(() => {
    let list = [...sessions].sort(
      (a, b) => new Date(b.seatedAt).getTime() - new Date(a.seatedAt).getTime(),
    )
    if (filter === 'ACTIVE') {
      list = list.filter((s) => !['CLEANING', 'AVAILABLE'].includes(s.status))
    } else if (filter === 'CLOSED') {
      list = list.filter((s) => s.status === 'CLEANING')
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter((s) => {
        const table = floor?.tables.find((t) => t.id === s.tableId)
        const tableNum = table?.number?.toLowerCase() ?? ''
        const guest = s.guestName?.toLowerCase() ?? ''
        return tableNum.includes(q) || guest.includes(q)
      })
    }
    return list
  }, [sessions, filter, search, floor?.tables])

  const counts = useMemo(() => {
    const active = sessions.filter((s) => !['CLEANING', 'AVAILABLE'].includes(s.status)).length
    const closed = sessions.filter((s) => s.status === 'CLEANING').length
    return { active, closed, all: sessions.length }
  }, [sessions])

  if (loading) {
    return (
      <div className="page-loading">
        <div className="spinner" />
        <p>Loading sessions…</p>
      </div>
    )
  }

  return (
    <div className="sessions-page">
      <div className="page-header">
        <div>
          <h2>Sessions</h2>
          <p className="muted">Track guests, orders, and billing</p>
        </div>
      </div>

      <div className="sessions-summary">
        <div className="sessions-summary__stat">
          <span className="sessions-summary__value">{counts.active}</span>
          <span className="sessions-summary__label">In service</span>
        </div>
        <div className="sessions-summary__stat">
          <span className="sessions-summary__value">{counts.closed}</span>
          <span className="sessions-summary__label">Cleaning</span>
        </div>
        <div className="sessions-summary__stat">
          <span className="sessions-summary__value">{counts.all}</span>
          <span className="sessions-summary__label">Total today</span>
        </div>
      </div>

      <div className="sessions-toolbar">
        <input
          type="search"
          className="input sessions-search"
          placeholder="Search table # or guest name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="session-filters">
          {(
            [
              ['ACTIVE', `Active (${counts.active})`],
              ['CLOSED', `Cleaning (${counts.closed})`],
              ['ALL', `All (${counts.all})`],
            ] as const
          ).map(([f, label]) => (
            <button key={f} type="button" className={`filter-chip ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="☰"
          title={filter === 'ACTIVE' ? 'No active sessions right now.' : 'No sessions match this view.'}
          message="Seat guests from the Floor plan page."
        />
      ) : (
        <div className="sessions-list">
          {filtered.map((session) => {
            const table = floor?.tables.find((t) => t.id === session.tableId)
            const section = table ? floor?.sections.find((s) => s.id === table.sectionId) : undefined
            return (
              <SessionCard
                key={session.id}
                session={session}
                table={table}
                sectionName={section?.name}
                onAdvance={(tableId, status) => changeStatus(tableId, status)}
                onRelease={closeSession}
                onRefresh={refresh}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
