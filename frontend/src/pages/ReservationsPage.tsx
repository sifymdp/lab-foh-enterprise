import { useCallback, useEffect, useMemo, useState } from 'react'
import { reservationsApi, type Reservation } from '../api/extensions'
import { ReleaseCountdown } from '../components/reservations/ReleaseCountdown'
import { ConfirmDialog } from '../components/ui/ConfirmDialog'
import { EmptyState } from '../components/ui/EmptyState'
import { Pagination } from '../components/ui/Pagination'
import { humanizeApiError } from '../lib/apiErrors'
import { useFloor } from '../context/FloorContext'

interface FormState {
  tableId: string; guestName: string; partySize: string
  reservedFor: string; reservedUntil: string; notes: string
}

const EMPTY_FORM: FormState = {
  tableId: '', guestName: '', partySize: '2',
  reservedFor: '', reservedUntil: '', notes: '',
}

export function ReservationsPage() {
  const { floor } = useFloor()
  const [reservations, setReservations] = useState<Reservation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState<string | null>(null)
  const [releaseTarget, setReleaseTarget] = useState<{ id: string; guestName: string } | null>(null)

  // Search & Filter & Pagination state
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  // Reset page on search or filter change
  useEffect(() => {
    setCurrentPage(1)
  }, [search, statusFilter])

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await reservationsApi.list()
      setReservations(data)
    } catch (e) {
      setError(humanizeApiError(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const handleCreated = () => load()
    window.addEventListener('foh:reservation-created', handleCreated)
    return () => window.removeEventListener('foh:reservation-created', handleCreated)
  }, [load])

  useEffect(() => {
    if (!toast) return
    const t = setTimeout(() => setToast(null), 3000)
    return () => clearTimeout(t)
  }, [toast])

  const handleCreate = async () => {
    if (!form.tableId || !form.guestName || !form.reservedFor || !form.reservedUntil) return
    setSaving(true)
    setError('')
    try {
      await reservationsApi.create({
        tableId: form.tableId,
        guestName: form.guestName,
        partySize: parseInt(form.partySize),
        reservedFor: new Date(form.reservedFor).toISOString(),
        reservedUntil: new Date(form.reservedUntil).toISOString(),
        notes: form.notes || undefined,
      })
      setShowForm(false)
      setForm(EMPTY_FORM)
      setToast('Reservation created successfully')
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create')
    } finally {
      setSaving(false)
    }
  }

  const handleRelease = async (id: string) => {
    try {
      const updated = await reservationsApi.release(id)
      setReservations((prev) => prev.map((r) => (r.id === id ? updated : r)))
      setReleaseTarget(null)
    } catch (e) {
      setError(humanizeApiError(e))
    }
  }

  const statusColor: Record<string, string> = {
    PENDING: '#1a73e8', SEATED: '#1e6b3c', RELEASED: '#888', CANCELLED: '#c00',
  }

  const filteredReservations = useMemo(() => {
    let list = [...reservations].sort(
      (a, b) => new Date(a.reservedFor).getTime() - new Date(b.reservedFor).getTime(),
    )
    if (statusFilter !== 'ALL') {
      list = list.filter((r) => r.status === statusFilter)
    }
    const q = search.trim().toLowerCase()
    if (q) {
      list = list.filter((r) => {
        const table = floor?.tables.find((t) => t.id === r.tableId)
        const tableNum = table?.number?.toLowerCase() ?? ''
        const guest = r.guestName.toLowerCase()
        return tableNum.includes(q) || guest.includes(q)
      })
    }
    return list
  }, [reservations, statusFilter, search, floor?.tables])

  const paginatedReservations = useMemo(() => {
    const start = (currentPage - 1) * pageSize
    return filteredReservations.slice(start, start + pageSize)
  }, [filteredReservations, currentPage, pageSize])

  const availableTables = floor?.tables.filter((t) =>
    t.status === 'AVAILABLE' || t.status === 'RESERVED'
  ) ?? []

  if (loading) return <div className="page-loading"><div className="spinner" /></div>

  return (
    <div style={{ padding: '0 24px 40px' }}>
      {toast && (
        <div style={{
          position: 'fixed', top: 16, right: 16, zIndex: 1000,
          padding: '12px 16px', background: '#1e6b3c', color: '#fff',
          borderRadius: 8, boxShadow: '0 4px 12px rgba(0,0,0,0.2)', fontSize: 14,
        }}>
          {toast}
        </div>
      )}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', padding: '24px 0 20px' }}>
        <div>
          <h2 style={{ margin: 0 }}>Reservations</h2>
          <p className="muted" style={{ margin: '4px 0 0' }}>Tables auto-release if guests don't arrive by the reserved time</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => window.dispatchEvent(new CustomEvent('foh:open-voice-receptionist'))}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          >
            <span>📞</span> AI Voice Receptionist
          </button>
          <button className="btn btn-primary" onClick={() => setShowForm(true)}>+ New reservation</button>
        </div>
      </div>

      {error && (
        <div style={{ background: '#fee', border: '1px solid #fcc', borderRadius: 8, padding: '10px 16px', marginBottom: 16, color: '#c00', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>{error}</span>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => load()}>Retry</button>
        </div>
      )}

      {/* Search & Filter Toolbar */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.75rem',
        marginBottom: '1rem',
        background: 'var(--bg-elevated, #ffffff)',
        padding: '0.75rem 1rem',
        borderRadius: '10px',
        border: '1px solid var(--border, #e2e8f0)',
      }}>
        <input
          id="reservations-search-input"
          name="reservationSearch"
          aria-label="Search guest name or table"
          type="search"
          placeholder="Search guest or table #…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            padding: '0.45rem 0.85rem',
            borderRadius: '6px',
            border: '1px solid var(--border, #cbd5e1)',
            minWidth: '220px',
            fontSize: '0.85rem',
          }}
        />

        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
          {[
            ['ALL', 'All'],
            ['PENDING', 'Pending'],
            ['SEATED', 'Seated'],
            ['RELEASED', 'Released'],
            ['CANCELLED', 'Cancelled'],
          ].map(([status, label]) => {
            const isActive = statusFilter === status
            return (
              <button
                key={status}
                type="button"
                onClick={() => setStatusFilter(status)}
                style={{
                  padding: '0.3rem 0.75rem',
                  borderRadius: '6px',
                  border: isActive ? 'none' : '1px solid var(--border, #cbd5e1)',
                  background: isActive ? 'var(--primary, #2563eb)' : '#ffffff',
                  color: isActive ? '#ffffff' : 'var(--text, #0f172a)',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: isActive ? 700 : 500,
                }}
              >
                {label}
              </button>
            )
          })}
        </div>
      </div>

      {filteredReservations.length === 0 ? (
        <EmptyState
          icon="📅"
          title={reservations.length === 0 ? 'No upcoming reservations.' : 'No reservations match your filter.'}
          message={reservations.length === 0 ? 'Click "New reservation" to hold a table.' : 'Try adjusting your search query or filter.'}
        />
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {paginatedReservations.map((r) => {
              const table = floor?.tables.find((t) => t.id === r.tableId)
              return (
                <div key={r.id} style={{
                  display: 'flex', alignItems: 'center', gap: 16, padding: '14px 16px',
                  background: '#fff', border: '1px solid #eee', borderRadius: 10,
                  opacity: ['RELEASED', 'CANCELLED'].includes(r.status) ? 0.6 : 1,
                }}>
                  <div style={{
                    width: 40, height: 40, borderRadius: 8, background: '#f5f5f5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontWeight: 700, fontSize: 14,
                  }}>
                    {table?.number ?? '?'}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontWeight: 500, fontSize: 14 }}>{r.guestName}</span>
                      <span style={{ fontSize: 12, color: '#666' }}>· Party of {r.partySize}</span>
                      <span style={{
                        fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 10,
                        background: `${statusColor[r.status]}20`,
                        color: statusColor[r.status],
                      }}>{r.status}</span>
                    </div>
                    <p style={{ margin: '3px 0 0', fontSize: 12, color: '#888' }}>
                      Arrives {new Date(r.reservedFor).toLocaleString()}
                    </p>
                    {r.status === 'PENDING' && (
                      <p style={{ margin: '2px 0 0', fontSize: 12 }}>
                        <ReleaseCountdown until={r.reservedUntil} />
                      </p>
                    )}
                    {r.notes && <p style={{ margin: '2px 0 0', fontSize: 12, color: '#aaa' }}>{r.notes}</p>}
                  </div>
                  {r.status === 'PENDING' && (
                    <button
                      type="button"
                      onClick={() => setReleaseTarget({ id: r.id, guestName: r.guestName })}
                      style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid #ddd', background: '#fff', fontSize: 12, cursor: 'pointer' }}
                    >
                      Release
                    </button>
                  )}
                </div>
              )
            })}
          </div>

          <Pagination
            currentPage={currentPage}
            totalItems={filteredReservations.length}
            pageSize={pageSize}
            onPageChange={setCurrentPage}
            onPageSizeChange={setPageSize}
            pageSizeOptions={[5, 10, 20, 50]}
            itemName="reservations"
          />
        </>
      )}

      <ConfirmDialog
        open={!!releaseTarget}
        message={`Release reservation for ${releaseTarget?.guestName ?? 'this guest'}? The table will become available.`}
        confirmLabel="Release"
        onConfirm={() => releaseTarget && handleRelease(releaseTarget.id)}
        onCancel={() => setReleaseTarget(null)}
      />

      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 100, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, width: '100%', maxWidth: 460, boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
            <h3 style={{ margin: '0 0 20px', fontSize: 18 }}>New reservation</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label htmlFor="res-form-table" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Table *</label>
                <select
                  id="res-form-table"
                  name="reservationTable"
                  aria-label="Reservation Table"
                  className="input"
                  value={form.tableId}
                  onChange={(e) => setForm((f) => ({ ...f, tableId: e.target.value }))}
                  style={{ width: '100%' }}
                >
                  <option value="">Select a table</option>
                  {availableTables.map((t) => (
                    <option key={t.id} value={t.id}>Table {t.number} (capacity {t.capacity})</option>
                  ))}
                </select>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label htmlFor="res-form-guest-name" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Guest name *</label>
                  <input
                    id="res-form-guest-name"
                    name="guestName"
                    aria-label="Guest name"
                    className="input"
                    value={form.guestName}
                    onChange={(e) => setForm((f) => ({ ...f, guestName: e.target.value }))}
                    placeholder="Smith"
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label htmlFor="res-form-party-size" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Party size</label>
                  <input
                    id="res-form-party-size"
                    name="partySize"
                    aria-label="Party size"
                    className="input"
                    type="number"
                    min="1"
                    max="20"
                    value={form.partySize}
                    onChange={(e) => setForm((f) => ({ ...f, partySize: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label htmlFor="res-form-reserved-for" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Arrival time *</label>
                  <input
                    id="res-form-reserved-for"
                    name="reservedFor"
                    aria-label="Arrival time"
                    className="input"
                    type="datetime-local"
                    value={form.reservedFor}
                    onChange={(e) => setForm((f) => ({ ...f, reservedFor: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </div>
                <div>
                  <label htmlFor="res-form-reserved-until" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Auto-release at *</label>
                  <input
                    id="res-form-reserved-until"
                    name="reservedUntil"
                    aria-label="Auto-release time"
                    className="input"
                    type="datetime-local"
                    value={form.reservedUntil}
                    onChange={(e) => setForm((f) => ({ ...f, reservedUntil: e.target.value }))}
                    style={{ width: '100%' }}
                  />
                </div>
              </div>
              <div>
                <label htmlFor="res-form-notes" style={{ fontSize: 13, fontWeight: 500, display: 'block', marginBottom: 4 }}>Notes</label>
                <input
                  id="res-form-notes"
                  name="reservationNotes"
                  aria-label="Reservation notes"
                  className="input"
                  value={form.notes}
                  onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
                  placeholder="Window seat preferred…"
                  style={{ width: '100%' }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, marginTop: 20, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => setShowForm(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleCreate} disabled={saving || !form.tableId || !form.guestName || !form.reservedFor || !form.reservedUntil}>
                {saving ? 'Creating…' : 'Create reservation'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
