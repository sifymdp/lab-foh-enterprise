import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { useFloor } from '../../context/FloorContext'
import type { Table } from '../../types'

interface SeatGuestModalProps {
  table: Table
  onClose: () => void
}

export function SeatGuestModal({ table, onClose }: SeatGuestModalProps) {
  const { seatGuest } = useFloor()
  const [guestName, setGuestName] = useState('')
  const [partySize, setPartySize] = useState(2)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const overCapacity = partySize > table.capacity

  useEffect(() => {
    document.body.classList.add('foh-modal-open')
    return () => document.body.classList.remove('foh-modal-open')
  }, [])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (overCapacity) return
    setLoading(true)
    setError(null)
    try {
      await seatGuest(table.id, partySize, guestName.trim() || undefined)
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not seat guests')
    } finally {
      setLoading(false)
    }
  }

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
      <div className="modal modal--seat" onClick={(e) => e.stopPropagation()}>
        <h3 id="seat-guest-title">Seat guests — Table {table.number}</h3>
        <p className="muted">
          Capacity: {table.capacity} · Current: {table.status}
        </p>
        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Guest name (optional)</span>
            <input
              type="text"
              className="input"
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              placeholder="Walk-in or reservation name"
            />
          </label>
          <label className="field">
            <span>Party size</span>
            <input
              type="number"
              className="input"
              min={1}
              max={20}
              value={partySize}
              onChange={(e) => setPartySize(Number(e.target.value))}
              autoFocus
            />
          </label>
          {overCapacity && (
            <p className="form-error">Party size exceeds table capacity ({table.capacity}).</p>
          )}
          {error && <p className="form-error">{error}</p>}
          <div className="modal-actions">
            <button type="button" className="btn btn-ghost" onClick={onClose}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary"
              disabled={loading || overCapacity || partySize < 1}
            >
              {loading ? 'Seating…' : 'Confirm seating'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  )
}
