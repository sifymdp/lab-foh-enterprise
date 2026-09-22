import { useState } from 'react'
import type { KitchenOrder, KitchenStation } from '../../types'
import { OrderCard } from './OrderCard'

interface KDSBoardProps {
  orders: KitchenOrder[]
  selectedStation: KitchenStation
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
}

export function KDSBoard({ orders, selectedStation, onStatusChange }: KDSBoardProps) {
  const [allExpanded, setAllExpanded] = useState<boolean | undefined>(undefined)

  // Filter orders by station if not "ALL"
  const filteredOrders = selectedStation === 'ALL'
    ? orders
    : orders.filter((order) =>
        (order.items || []).some((item: any) => item.station === selectedStation || !item.station)
      )

  // Split orders into 3 columns by status
  const received = filteredOrders.filter((o) => o.status === 'RECEIVED')
  const preparing = filteredOrders.filter((o) => o.status === 'PREPARING')
  const ready = filteredOrders.filter((o) => o.status === 'READY')

  return (
    <div className="kds-board-container">
      {/* High-density view control toolbar */}
      <div className="kds-toolbar">
        <div className="kds-toolbar__info">
          <span className="kds-toolbar__title">⚡ High-Density Queue</span>
          <span className="kds-toolbar__hint">Showing {filteredOrders.length} active orders • Click any order bar to slide open details</span>
        </div>
        <div className="kds-toolbar__actions">
          <button
            type="button"
            className={`kds-toolbar-btn ${allExpanded === false ? 'kds-toolbar-btn--active' : ''}`}
            onClick={() => setAllExpanded(false)}
          >
            ↕ Collapse All
          </button>
          <button
            type="button"
            className={`kds-toolbar-btn ${allExpanded === true ? 'kds-toolbar-btn--active' : ''}`}
            onClick={() => setAllExpanded(true)}
          >
            ↕ Expand All
          </button>
        </div>
      </div>

      <div className="kds-board">
        {/* RECEIVED COLUMN */}
        <div className="kds-column kds-column--received">
          <div className="column-header">
            <h2>RECEIVED</h2>
            <span className="column-count">{received.length}</span>
          </div>
          <div className="column-cards">
            {received.length === 0 ? (
              <p className="column-empty">No orders</p>
            ) : (
              received.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                  forceExpand={allExpanded}
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
          <div className="column-cards">
            {preparing.length === 0 ? (
              <p className="column-empty">No orders</p>
            ) : (
              preparing.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                  forceExpand={allExpanded}
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
          <div className="column-cards">
            {ready.length === 0 ? (
              <p className="column-empty">No orders</p>
            ) : (
              ready.map((order) => (
                <OrderCard
                  key={order.id}
                  order={order}
                  onStatusChange={onStatusChange}
                  forceExpand={allExpanded}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}