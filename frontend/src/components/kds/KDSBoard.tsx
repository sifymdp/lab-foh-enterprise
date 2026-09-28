import { useMemo } from 'react'
import type { KitchenOrder, KitchenStation } from '../../types'
import { OrderCard } from './OrderCard'
import { matchItemStation } from './StationFilter'

interface KDSBoardProps {
  orders: KitchenOrder[]
  selectedStation?: KitchenStation
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
}

export function KDSBoard({ orders, selectedStation = 'ALL', onStatusChange }: KDSBoardProps) {
  // Station filtering
  const filteredOrders = useMemo(() => {
    if (selectedStation === 'ALL') return orders
    return orders.filter((order) =>
      (order.items || []).some((item: any) => matchItemStation(item, selectedStation))
    )
  }, [orders, selectedStation])

  const received = useMemo(() => filteredOrders.filter((o) => o.status === 'RECEIVED'), [filteredOrders])
  const preparing = useMemo(() => filteredOrders.filter((o) => o.status === 'PREPARING'), [filteredOrders])
  const ready = useMemo(() => filteredOrders.filter((o) => o.status === 'READY'), [filteredOrders])

  return (
    <div className="kds-board-container">
      <div className="kds-board">
        {/* RECEIVED COLUMN */}
        <div className="kds-column kds-column--received">
          <div className="column-header">
            <h2>RECEIVED</h2>
            <span className="column-count">{received.length}</span>
          </div>
          <div className="order-cards-list">
            {received.length === 0 ? (
              <div className="empty-column-hint">No orders waiting</div>
            ) : (
              received.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                />
              ))
            )}
          </div>
        </div>

        {/* PREPARING COLUMN */}
        <div className="kds-column kds-column--preparing">
          <div className="column-header">
            <h2>PREPARING</h2>
            <span className="column-count">{preparing.length}</span>
          </div>
          <div className="order-cards-list">
            {preparing.length === 0 ? (
              <div className="empty-column-hint">Kitchen is clear</div>
            ) : (
              preparing.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                />
              ))
            )}
          </div>
        </div>

        {/* READY COLUMN */}
        <div className="kds-column kds-column--ready">
          <div className="column-header">
            <h2>READY</h2>
            <span className="column-count">{ready.length}</span>
          </div>
          <div className="order-cards-list">
            {ready.length === 0 ? (
              <div className="empty-column-hint">No dishes ready</div>
            ) : (
              ready.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}