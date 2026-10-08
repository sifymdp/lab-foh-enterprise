import { useState } from 'react'
import type { KitchenOrder } from '../../types'

interface CompletedOrdersPanelProps {
  orders: KitchenOrder[]
}

export function CompletedOrdersPanel({ orders }: CompletedOrdersPanelProps) {
  const [expanded, setExpanded] = useState(false)

  // Get only SERVED orders
  const completedOrders = orders.filter((o) => o.status === 'SERVED')

  // If no completed orders, don't show anything
  if (completedOrders.length === 0) {
    return null
  }

  // Sort by most recent first
  const sorted = [...completedOrders].sort(
    (a, b) => new Date(b.served_at || '').getTime() - new Date(a.served_at || '').getTime()
  )

  // Show only last 10 orders
  const recent = sorted.slice(0, 10)

  return (
    <div className="kds-completed-panel">
      <button
        type="button"
        className="completed-panel__toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="toggle-icon">{expanded ? '▼' : '▶'}</span>
        <span className="toggle-text">Completed Orders ({completedOrders.length})</span>
      </button>

      {expanded && (
        <div className="completed-panel__content">
          <div className="completed-orders-list">
            {recent.map((order) => {
              // Calculate prep time (from placed to served)
              const placedTime = new Date(order.placed_at).getTime()
              const servedTime = new Date(order.served_at || '').getTime()
              const prepTimeSeconds = Math.floor((servedTime - placedTime) / 1000)
              const prepMinutes = Math.floor(prepTimeSeconds / 60)
              const prepSecs = prepTimeSeconds % 60

              return (
                <div key={order.id} className="completed-order-item">
                  <div className="completed-order__info">
                    <strong>Order #{order.id.slice(0, 8)}</strong>
                    <span className="completed-order__table">
                      Table {order.table_number}
                    </span>
                  </div>
                  <div className="completed-order__time">
                    <small>Prep time: {String(prepMinutes).padStart(2, '0')}:{String(prepSecs).padStart(2, '0')}</small>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
