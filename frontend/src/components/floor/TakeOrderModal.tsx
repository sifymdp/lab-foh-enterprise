import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { menuApi, ordersApi, type MenuItem } from '../../api/extensions'
import { useFloor } from '../../context/FloorContext'
import type { Table } from '../../types'

interface TakeOrderModalProps {
  table: Table
  onClose: () => void
}

export function TakeOrderModal({ table, onClose }: TakeOrderModalProps) {
  const { sessions, refresh } = useFloor()
  const [menuItems, setMenuItems] = useState<MenuItem[]>([])
  const [menuLoading, setMenuLoading] = useState(true)
  const [quantities, setQuantities] = useState<Record<string, number>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const session = sessions.find(
    (s) => (s.tableId === table.id || (s as any).table_id === table.id) && !s.closedAt && ['SEATED', 'ACTIVE', 'OCCUPIED'].includes(s.status),
  )

  useEffect(() => {
    document.body.classList.add('foh-modal-open')
    return () => document.body.classList.remove('foh-modal-open')
  }, [])

  useEffect(() => {
    let cancelled = false
    setMenuLoading(true)
    menuApi
      .listPublic()
      .then((items) => {
        if (!cancelled) setMenuItems(items.filter((i) => i.available))
      })
      .catch(() => {
        if (!cancelled) setError('Could not load menu')
      })
      .finally(() => {
        if (!cancelled) setMenuLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const selectedItems = useMemo(
    () =>
      Object.entries(quantities)
        .filter(([, qty]) => qty > 0)
        .map(([menuItemId, quantity]) => ({ menuItemId, quantity })),
    [quantities],
  )

  const total = useMemo(() => {
    return selectedItems.reduce((sum, line) => {
      const item = menuItems.find((m) => m.id === line.menuItemId)
      return sum + (item ? item.price * line.quantity : 0)
    }, 0)
  }, [selectedItems, menuItems])

  function setQty(itemId: string, qty: number) {
    setQuantities((prev) => ({ ...prev, [itemId]: Math.max(0, qty) }))
  }

  async function handleSubmit() {
    if (selectedItems.length === 0) return
    setSubmitting(true)
    setError(null)
    try {
      await ordersApi.place(table.id, selectedItems, session?.id)
      await refresh()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not place order')
    } finally {
      setSubmitting(false)
    }
  }

  return createPortal(
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="take-order-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="modal" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 480 }}>
        <h3 id="take-order-title">Take order — Table {table.number}</h3>

        {menuLoading ? (
          <p className="muted" style={{ fontSize: 13 }}>Loading menu…</p>
        ) : (
          <div style={{ maxHeight: 320, overflowY: 'auto', margin: '12px 0' }}>
            {menuItems.map((item) => (
              <div
                key={item.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 0',
                  borderBottom: '1px solid #e2e8f0',
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{item.name}</div>
                  <div className="muted" style={{ fontSize: 12 }}>₹{item.price.toFixed(2)}</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ width: 28, height: 28, padding: 0 }}
                    onClick={() => setQty(item.id, (quantities[item.id] ?? 0) - 1)}
                  >
                    −
                  </button>
                  <span style={{ minWidth: 20, textAlign: 'center' }}>{quantities[item.id] ?? 0}</span>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    style={{ width: 28, height: 28, padding: 0 }}
                    onClick={() => setQty(item.id, (quantities[item.id] ?? 0) + 1)}
                  >
                    +
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ fontWeight: 700, fontSize: 14, margin: '8px 0' }}>
          Total: ₹{total.toFixed(2)}
        </div>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={submitting || selectedItems.length === 0}
            onClick={handleSubmit}
          >
            {submitting ? 'Placing…' : 'Place order'}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  )
}