import { useCallback, useEffect, useState } from 'react'
import { useSocket } from '../context/SocketContext'
import { api, normalizeKitchenOrder } from '../api/client'
import { KDSBoard } from '../components/kds/KDSBoard'
import { CompletedOrdersPanel } from '../components/kds/CompletedOrdersPanel'
import type { KitchenOrder } from '../types/kitchen'
import '../styles/kds.css'
import { KDSSwitch } from '../components/kds/KDSSwitch'
import { AIOperationsPanel } from '../components/kds/AIOperationsPanel'

export function KDSPage() {
  const { on } = useSocket()
  const [orders, setOrders] = useState<KitchenOrder[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Load orders from the backend
  const fetchOrders = useCallback(async () => {
    try {
      setError(null)
      const data = await api.getKitchenOrders()
      setOrders(data)
      setLoading(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load orders')
      setLoading(false)
    }
  }, [])

  // Load orders on page load
  useEffect(() => {
    fetchOrders()
  }, [fetchOrders])

  // Listen for real-time order updates via WebSocket
  useEffect(() => {
    // When a new order is placed
    const unsubOrderPlaced = on('order_placed', () => {
      fetchOrders()
    })

    // When an order status changes
    const unsubStatusUpdated = on('order_status_updated', (payload) => {
      const updated = normalizeKitchenOrder(payload as Record<string, unknown>)
      setOrders((previous) => previous.map((order) => order.id === updated.id ? updated : order))
    })

    // When an order is marked served
    const unsubOrderServed = on('order_served', () => {
      fetchOrders()
    })

    return () => {
      unsubOrderPlaced()
      unsubStatusUpdated()
      unsubOrderServed()
    }
  }, [on, fetchOrders])

  // Polling fallback: refresh orders every 15 seconds
  // (in case WebSocket connection drops)
  useEffect(() => {
    const interval = setInterval(() => {
      fetchOrders()
    }, 15000)

    return () => clearInterval(interval)
  }, [fetchOrders])

  // When chef clicks the status button, update the order
  const handleStatusChange = async (orderId: string, newStatus: string) => {
    try {
      await api.updateOrderStatus(orderId, newStatus)
      // After successful update, refresh orders
      await fetchOrders()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update status'
      setActionError(message)
    }
  }

  return (
    <div className="kds-page-wrap">
      {/* Page Title */}
      <header className="kds-top-bar">
        <div className="kds-top-bar__left">
          <div className="kds-title-group">
            <h2>⚡ High-Density KDS Board</h2>
            <span className="kds-view-pill">Order Staging</span>
          </div>
          <p className="muted">Multi-column live order lifecycle & AI workload management</p>
        </div>
        <div className="kds-top-bar__right">
          <KDSSwitch currentView="kds" />
        </div>
      </header>
      {actionError && (
        <div className="kds-action-error" role="alert">
          <span>{actionError}</span>
          <button type="button" onClick={() => setActionError(null)} aria-label="Dismiss error">Dismiss</button>
        </div>
      )}

      {/* Error Message (if something went wrong) */}
      {error && (
        <div className="kds-error">
          <strong>⚠️ Error:</strong> {error}
          <button type="button" onClick={() => fetchOrders()}>
            Retry
          </button>
        </div>
      )}

      {/* Loading State */}
      {loading && !error && (
        <div className="kds-loading">
          <p>Loading orders...</p>
        </div>
      )}

      {/* Main Content */}
      {!loading && (
        <>
          <AIOperationsPanel orders={orders} />
          <KDSBoard
            orders={orders}
            selectedStation="ALL"
            onStatusChange={handleStatusChange}
          />
          {/* Completed Orders (Collapsed by default) */}
          <CompletedOrdersPanel orders={orders} />
        </>
      )}
    </div>
  )
}