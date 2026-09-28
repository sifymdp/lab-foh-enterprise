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
  const [updating, setUpdating] = useState(false)

  const items = order.items || []
  const totalItemCount = items.reduce((sum: number, i: any) => sum + (i.quantity || 1), 0)
  const itemsPreviewText = items.map((i: any) => `${i.quantity}x ${i.item_name}`).join(', ')

  // Determine button text & next status
  let buttonLabel = ''
  let nextStatus = ''
  let btnClass = 'kds-button--received'

  if (order.status === 'RECEIVED') {
    buttonLabel = 'START PREPARING'
    nextStatus = 'PREPARING'
    btnClass = 'kds-button--received'
  } else if (order.status === 'PREPARING') {
    buttonLabel = 'MARK AS READY'
    nextStatus = 'READY'
    btnClass = 'kds-button--preparing'
  } else if (order.status === 'READY') {
    buttonLabel = 'MARK AS SERVED'
    nextStatus = 'SERVED'
    btnClass = 'kds-button--ready'
  }

  const handleQuickAdvance = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!nextStatus || updating) return
    setUpdating(true)
    try {
      await onStatusChange(order.id, nextStatus)
    } finally {
      setUpdating(false)
    }
  }

  const tableText = order.table_number ? `Table ${order.table_number}` : `Table ${order.table_id || '?'}`
  const orderIdText = `#${order.id.slice(-6).toUpperCase()}`

  return (
    <>
      <div
        className={`kds-card-strip kds-card-strip--${order.status.toLowerCase()}`}
        onClick={() => setShowModal(true)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            setShowModal(true)
          }
        }}
        style={{ cursor: 'pointer' }}
      >
        {/* Top Header Row */}
        <div className="card-strip__main">
          <div className="card-strip__left">
            <span className="card-strip__order-id">{orderIdText}</span>
            <span className="card-strip__table-badge">{tableText}</span>
          </div>

          <div className="card-strip__right">
            <button
              type="button"
              className="card-strip__slide-btn"
              onClick={(e) => {
                e.stopPropagation()
                setShowModal(true)
              }}
              aria-label="View order details"
              title="View order details"
            >
              👁
            </button>
          </div>
        </div>

        {/* Dish Items Preview Bar */}
        <div className="card-strip__preview">
          <span className="card-strip__item-count">
            {totalItemCount} item{totalItemCount !== 1 ? 's' : ''}
          </span>
          <span className="card-strip__item-text" title={itemsPreviewText}>
            {itemsPreviewText}
          </span>
        </div>

        {/* Action Button Bar */}
        {buttonLabel && (
          <div className="card-strip__action-bar">
            <button
              type="button"
              className={`kds-button ${btnClass}`}
              onClick={handleQuickAdvance}
              disabled={updating}
            >
              {updating ? 'UPDATING...' : buttonLabel}
            </button>
          </div>
        )}
      </div>

      {/* Order Detail Modal */}
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