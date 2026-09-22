import { useEffect, useRef, useState } from 'react'
import type { KitchenOrder } from '../../types'
import { formatTime, formatStationName, getStationBadgeClass } from '../../lib/formatters'

interface OrderDetailModalProps {
  order: KitchenOrder
  onClose: () => void
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
  busy?: boolean
}

const STATUS_CONFIG: Record<string, { label: string; dot: string; actionLabel: string; nextStatus: string; actionColor: string }> = {
  RECEIVED:  { label: 'Received',  dot: '#f59e0b', actionLabel: 'Start Preparing', nextStatus: 'PREPARING', actionColor: '#d97706' },
  PREPARING: { label: 'Preparing', dot: '#3b82f6', actionLabel: 'Mark Ready',      nextStatus: 'READY',     actionColor: '#2563eb' },
  READY:     { label: 'Ready',     dot: '#16a34a', actionLabel: 'Mark Served',     nextStatus: 'SERVED',    actionColor: '#16a34a' },
  SERVED:    { label: 'Served',    dot: '#94a3b8', actionLabel: '',                nextStatus: '',          actionColor: '#64748b' },
}

const SOURCE_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  WAITER: { label: 'Waiter', color: '#7c3aed', bg: 'rgba(124, 58, 237, 0.15)' },
  QR:     { label: 'QR/Guest', color: '#0891b2', bg: 'rgba(8, 145, 178, 0.15)' },
  BOT:    { label: 'Bot', color: '#059669', bg: 'rgba(5, 150, 105, 0.15)' },
}

export function OrderDetailModal({ order, onClose, onStatusChange, busy }: OrderDetailModalProps) {
  const overlayRef = useRef<HTMLDivElement>(null)
  const [confirming, setConfirming] = useState(false)
  const cfg = STATUS_CONFIG[order.status] ?? STATUS_CONFIG.RECEIVED
  const src = order.source ? SOURCE_LABELS[order.source] : null
  const totalItemCount = (order.items || []).reduce((sum: number, i: any) => sum + i.quantity, 0)

  // Close on Escape key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [onClose])

  // Close when clicking the overlay backdrop
  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === overlayRef.current) onClose()
  }

  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => { document.body.style.overflow = '' }
  }, [])

  const handleActionClick = () => {
    setConfirming(true)
  }

  const handleConfirmYes = async () => {
    await onStatusChange(order.id, cfg.nextStatus)
    setConfirming(false)
    onClose()
  }

  const handleConfirmNo = () => {
    setConfirming(false)
  }

  return (
    <div className="odm-overlay" ref={overlayRef} onClick={handleOverlayClick}>
      <div className={`odm-panel odm-panel--${order.status.toLowerCase()}`}>
        {/* Close Button */}
        <button type="button" className="odm-close" onClick={onClose} aria-label="Close">✕</button>

        {/* Header */}
        <div className="odm-header">
          <div className="odm-header__top">
            <span className="odm-dot" style={{ background: cfg.dot }} />
            <span className="odm-order-id">#{order.id.slice(-6).toUpperCase()}</span>
            <span className="odm-status-badge" style={{ background: cfg.dot }}>
              {cfg.label}
            </span>
          </div>
          <div className="odm-header__badges">
            <span className="odm-table-badge">Table {order.table_number || order.table_id}</span>
            {src && (
              <span className="odm-source-badge" style={{ color: src.color, background: src.bg, border: `1px solid ${src.color}33` }}>
                {src.label}
              </span>
            )}
            <span className="odm-item-count">{totalItemCount} item{totalItemCount !== 1 ? 's' : ''}</span>
          </div>
        </div>

        {/* Timestamps */}
        <div className="odm-timestamps">
          <div className="odm-ts-item odm-ts--placed">
            <span className="odm-ts-icon">📥</span>
            <span className="odm-ts-label">Placed</span>
            <span className="odm-ts-value">{formatTime(order.placed_at)}</span>
          </div>
          {order.preparation_started_at && (
            <div className="odm-ts-item odm-ts--started">
              <span className="odm-ts-icon">👨‍🍳</span>
              <span className="odm-ts-label">Started</span>
              <span className="odm-ts-value">{formatTime(order.preparation_started_at)}</span>
            </div>
          )}
          {order.ready_at && (
            <div className="odm-ts-item odm-ts--ready">
              <span className="odm-ts-icon">✅</span>
              <span className="odm-ts-label">Ready</span>
              <span className="odm-ts-value">{formatTime(order.ready_at)}</span>
            </div>
          )}
          {order.served_at && (
            <div className="odm-ts-item odm-ts--served">
              <span className="odm-ts-icon">🍽</span>
              <span className="odm-ts-label">Served</span>
              <span className="odm-ts-value">{formatTime(order.served_at)}</span>
            </div>
          )}
        </div>

        {/* Items List */}
        <div className="odm-items">
          <div className="odm-items-title">Order Items</div>
          {(order.items || []).map((item: any) => (
            <div key={item.id} className="odm-item-row">
              <span className="odm-item-qty">{item.quantity}x</span>
              <span className="odm-item-name">{item.item_name}</span>
              {item.station && (
                <span className={`odm-item-station ${getStationBadgeClass(item.station)}`}>
                  {formatStationName(item.station)}
                </span>
              )}
            </div>
          ))}
        </div>

        {/* Action / Confirmation Section */}
        {cfg.nextStatus && !confirming && (
          <div className="odm-action">
            <button
              type="button"
              className="odm-action-btn"
              style={{ background: cfg.actionColor }}
              disabled={busy}
              onClick={handleActionClick}
            >
              {busy ? '⏳ Updating...' : cfg.actionLabel}
            </button>
          </div>
        )}

        {cfg.nextStatus && confirming && (
          <div className="odm-confirm">
            <div className="odm-confirm-icon">⚠️</div>
            <p className="odm-confirm-text">
              Are you sure you want to <strong>{cfg.actionLabel.toLowerCase()}</strong> this order?
            </p>
            <div className="odm-confirm-actions">
              <button
                type="button"
                className="odm-confirm-yes"
                style={{ background: cfg.actionColor }}
                disabled={busy}
                onClick={() => void handleConfirmYes()}
              >
                {busy ? '⏳ Updating...' : `Yes, ${cfg.actionLabel}`}
              </button>
              <button
                type="button"
                className="odm-confirm-no"
                onClick={handleConfirmNo}
                disabled={busy}
              >
                No, Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
