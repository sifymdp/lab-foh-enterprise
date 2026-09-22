import { useState } from 'react'
import type { KitchenOrder } from '../../types'
import { OrderDetailModal } from './OrderDetailModal'

interface OrderCardProps {
  order: KitchenOrder
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
  forceExpand?: boolean
}

export function OrderCard({ order, onStatusChange }: OrderCardProps) {
  const [showModal, setShowModal] = useState(false)

  const itemsPreviewText = (order.items || []).map((i: any) => `${i.quantity}x ${i.item_name}`).join(', ')
  const totalItemCount = (order.items || []).reduce((sum: number, i: any) => sum + i.quantity, 0)

  // Determine status button text
  let actionLabel = ''
  if (order.status === 'RECEIVED') actionLabel = 'START PREPARING'
  else if (order.status === 'PREPARING') actionLabel = 'MARK AS READY'

  return (
    <>
      <div
        className={`kds-card-strip kds-card-strip--${order.status.toLowerCase()}`}
        onClick={() => setShowModal(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setShowModal(true) } }}
        style={{ cursor: 'pointer' }}
      >
        {/* Top Main Strip Bar */}
        <div className="card-strip__main">
          <div className="card-strip__left">
            <span className="card-strip__order-id">#{order.id.slice(-6).toUpperCase()}</span>
            <span className="card-strip__table-badge">Table {order.table_number || order.table_id}</span>
          </div>

          <div className="card-strip__right">
            <button
              type="button"
              className="card-strip__slide-btn"
              onClick={(e) => { e.stopPropagation(); setShowModal(true) }}
              aria-label="View order details"
              title="View order details"
            >
              <span className="slide-chevron">👁</span>
            </button>
          </div>
        </div>

        {/* Sub Item Preview Bar */}
        <div className="card-strip__preview">
          <span className="card-strip__item-count">{totalItemCount} item{totalItemCount !== 1 ? 's' : ''}</span>
          <span className="card-strip__item-text" title={itemsPreviewText}>{itemsPreviewText}</span>
        </div>

        {/* Action Button Bar */}
        {actionLabel && (
          <div className="card-strip__action-bar">
            <button
              type="button"
              className="kds-button"
              onClick={(e) => { e.stopPropagation(); setShowModal(true) }}
            >
              {actionLabel}
            </button>
          </div>
        )}
      </div>

      {/* Order Detail Popup Modal */}
      {showModal && (
        <OrderDetailModal
          order={order}
          onClose={() => setShowModal(false)}
          onStatusChange={onStatusChange}
        />
      )}
    </>
  )
}