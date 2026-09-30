import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFloor } from '../../context/FloorContext'
import type { Table } from '../../types'

interface SeatGuestModalProps {
  table: Table
  onClose: () => void
  initialGuestName?: string
  initialPartySize?: number
}

export function SeatGuestModal({
  table,
  onClose,
  initialGuestName,
  initialPartySize,
}: SeatGuestModalProps) {
  const { seatGuest, sessions } = useFloor()

  // Look for any existing session for this table to prefill if present
  const existingSession = sessions.find(
    (s) =>
      (s.tableId === table.id || (s as any).table_id === table.id) &&
      !s.closedAt &&
      ['SEATED', 'ACTIVE', 'OCCUPIED'].includes(s.status),
  )

  const [guestName, setGuestName] = useState(
    initialGuestName || existingSession?.guestName || '',
  )
  const [partySize, setPartySize] = useState(
    initialPartySize || existingSession?.partySize || Math.min(table.capacity, 2) || 2,
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const overCapacity = partySize > table.capacity

  useEffect(() => {
    document.body.classList.add('foh-modal-open')
    return () => document.body.classList.remove('foh-modal-open')
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const name = guestName.trim()
    if (!name) {
      setError('Please enter the guest name or party identifier.')
      return
    }
    if (overCapacity) return
    setLoading(true)
    setError(null)
    try {
      await seatGuest(table.id, partySize, name)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not seat guests')
    } finally {
      setLoading(false)
    }
  }

  const QUICK_SIZES = [1, 2, 3, 4, 5, 6, 8]

  return createPortal(
    <div
      className="modal-backdrop modal-backdrop--seat"
      role="dialog"
      aria-modal="true"
      aria-labelledby="seat-guest-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal modal--seat" style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
          <span style={{ fontSize: '1.8rem' }}>👥</span>
          <div>
            <h3 id="seat-guest-title" style={{ margin: 0, fontSize: '1.25rem' }}>
              Seat Table #{table.number}
            </h3>
            <p className="muted" style={{ margin: '2px 0 0', fontSize: '0.82rem' }}>
              Capacity: <strong>{table.capacity} guests</strong> · Section: {table.sectionId || 'Main'}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} style={{ marginTop: '16px' }}>
          <label className="field" style={{ marginBottom: '14px' }}>
            <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text)' }}>
              Guest Name / Reservation Party <span style={{ color: '#ef4444' }}>*</span>
            </span>
            <input
              type="text"
              className="input"
              value={guestName}
              onChange={(e) => {
                setGuestName(e.target.value)
                if (error) setError(null)
              }}
              placeholder="e.g. Rahul Sharma, Walk-in, VIP"
              autoFocus
              required
              style={{ fontSize: '0.95rem', padding: '10px 12px' }}
            />
          </label>

          <label className="field" style={{ marginBottom: '10px' }}>
            <span style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text)' }}>
              Number of People (Party Size) <span style={{ color: '#ef4444' }}>*</span>
            </span>
            
            {/* Quick Pills */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', margin: '6px 0 10px' }}>
              {QUICK_SIZES.map((sz) => (
                <button
                  type="button"
                  key={sz}
                  onClick={() => setPartySize(sz)}
                  style={{
                    flex: '1 0 36px',
                    minWidth: '38px',
                    padding: '8px 0',
                    textAlign: 'center',
                    fontWeight: 700,
                    fontSize: '0.9rem',
                    borderRadius: '8px',
                    border: '1.5px solid',
                    borderColor: partySize === sz ? '#2563eb' : 'var(--border, #cbd5e1)',
                    background: partySize === sz ? '#2563eb' : 'var(--surface-2, #f8fafc)',
                    color: partySize === sz ? '#ffffff' : 'var(--text, #1e293b)',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {sz}
                </button>
              ))}
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: '42px', height: '42px', fontSize: '1.2rem', padding: 0 }}
                onClick={() => setPartySize((p) => Math.max(1, p - 1))}
              >
                −
              </button>
              <input
                type="number"
                className="input"
                min={1}
                max={30}
                value={partySize}
                onChange={(e) => setPartySize(Math.max(1, Number(e.target.value) || 1))}
                style={{ textAlign: 'center', fontWeight: 800, fontSize: '1.1rem', flex: 1 }}
              />
              <button
                type="button"
                className="btn btn-secondary"
                style={{ width: '42px', height: '42px', fontSize: '1.2rem', padding: 0 }}
                onClick={() => setPartySize((p) => p + 1)}
              >
                +
              </button>
            </div>
          </label>

          {overCapacity && (
            <p className="form-error" style={{ margin: '8px 0 0' }}>
              ⚠️ Party size ({partySize}) exceeds table capacity ({table.capacity}).
            </p>
          )}
          {error && <p className="form-error" style={{ margin: '8px 0 0' }}>{error}</p>}

          <div className="modal-actions" style={{ marginTop: '20px', display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
            <button type="button" className="btn btn-ghost" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || overCapacity || partySize < 1 || !guestName.trim()}
              style={{ padding: '10px 20px', fontWeight: 700 }}
            >
              {loading ? 'Seating…' : '✓ Confirm & Activate Table'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
