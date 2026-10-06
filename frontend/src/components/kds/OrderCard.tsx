import { useEffect, useState } from 'react'
import type { KitchenOrder } from '../../types'
import { OrderDetailModal } from './OrderDetailModal'
import { elapsedSeconds, formatElapsed, formatTime } from '../../lib/formatters'
import { RECEIVED_ALERT_MINUTES, PREPARATION_ALERT_MINUTES, READY_ALERT_MINUTES } from '../../lib/alertRules'

interface OrderCardProps {
  order: KitchenOrder
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
  forceExpand?: boolean
}

export function OrderCard({ order, onStatusChange }: OrderCardProps) {
  const [showModal, setShowModal] = useState(false)
  const [updating, setUpdating] = useState(false)
  const [confirmingNext, setConfirmingNext] = useState(false)
  const [elapsed, setElapsed] = useState(0)

  const estMins = order.estimated_prep_time_minutes || PREPARATION_ALERT_MINUTES
  const estSeconds = estMins * 60

  const isReceived = order.status === 'RECEIVED' || order.status === 'CONFIRMED'
  const isPreparing = order.status === 'PREPARING'
  const isReady = order.status === 'READY'
  const isServed = order.status === 'SERVED'

  // Dynamic calculation based strictly on backend timestamps
  let startTimestamp = order.placed_at
  let endTimestamp: string | null = null

  if (isReceived) {
    startTimestamp = order.received_at || order.placed_at
    endTimestamp = order.preparing_at || order.ready_at || order.served_at || null
  } else if (isPreparing) {
    startTimestamp = order.preparing_at || order.preparation_started_at || order.placed_at
    endTimestamp = order.ready_at || order.served_at || null
  } else if (isReady) {
    startTimestamp = order.ready_at || order.placed_at
    endTimestamp = order.served_at || null
  } else if (isServed) {
    startTimestamp = order.ready_at || order.placed_at
    endTimestamp = order.served_at || null
  }

  useEffect(() => {
    const tick = () => {
      setElapsed(elapsedSeconds(startTimestamp, endTimestamp))
    }
    tick()
    if (endTimestamp) return
    const interval = setInterval(tick, 1000)
    return () => clearInterval(interval)
  }, [startTimestamp, endTimestamp])

  const isWaitingTooLong = isReceived && elapsed >= RECEIVED_ALERT_MINUTES * 60
  const isPrepDelayed = isPreparing && elapsed > estSeconds
  const isFoodWaiting = isReady && elapsed >= READY_ALERT_MINUTES * 60
  const isOverdue = isWaitingTooLong || isPrepDelayed || isFoodWaiting
  const overdueMins = isPrepDelayed ? Math.floor((elapsed - estSeconds) / 60) : Math.floor(elapsed / 60)

  const items = order.items || []
  const totalItemCount = items.reduce((sum: number, i: any) => sum + (i.quantity || 1), 0)
  const itemsPreviewText = items.map((i: any) => `${i.quantity}x ${i.item_name}`).join(', ')

  // Determine button text & next status
  let buttonLabel = ''
  let nextStatus = ''
  let btnClass = 'kds-button--received'
  let confirmLabel = ''

  if (isReceived) {
    buttonLabel = 'START PREPARING'
    nextStatus = 'PREPARING'
    btnClass = 'kds-button--received'
    confirmLabel = 'Confirm: Start Prep? ✓'
  } else if (isPreparing) {
    buttonLabel = 'MARK AS READY'
    nextStatus = 'READY'
    btnClass = 'kds-button--preparing'
    confirmLabel = 'Confirm: Mark Ready? ✓'
  } else if (isReady) {
    buttonLabel = 'MARK AS SERVED'
    nextStatus = 'SERVED'
    btnClass = 'kds-button--ready'
    confirmLabel = 'Confirm: Mark Served? ★'
  }

  const handleConfirmedAdvance = async (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!nextStatus || updating) return
    setUpdating(true)
    try {
      await onStatusChange(order.id, nextStatus)
      setConfirmingNext(false)
    } finally {
      setUpdating(false)
    }
  }

  const tableText = order.table_number ? `Table ${order.table_number}` : `Table ${order.table_id || '?'}`
  const orderIdText = `#${order.id.slice(-6).toUpperCase()}`

  return (
    <>
      <div
        className={`kds-card-strip kds-card-strip--${order.status.toLowerCase()} ${isOverdue ? 'is-overdue' : ''}`}
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

          <div className="card-strip__right" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              className={`kds-order-duration-badge ${isOverdue ? 'is-overdue-badge' : ''}`}
              title={
                isReceived
                  ? `Received at ${formatTime(order.received_at || order.placed_at)} | Waiting: ${formatElapsed(elapsed)}`
                  : isPreparing
                  ? `Prep started at ${formatTime(order.preparing_at || order.preparation_started_at || order.placed_at)} | Expected: ${estMins}m`
                  : isReady
                  ? `Ready at ${formatTime(order.ready_at || order.placed_at)} | Waiting for pickup: ${formatElapsed(elapsed)}`
                  : `Served at ${formatTime(order.served_at || order.ready_at || order.placed_at)}`
              }
            >
              ⏱ {formatElapsed(elapsed)}
            </span>
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

        {/* Timing & Estimate Bar */}
        <div className="card-strip__timing-bar" style={{ display: 'flex', flexDirection: 'column', gap: '3px', fontSize: '0.74rem', padding: '0 0.5rem', marginBottom: '0.35rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#64748b' }}>
            {isReceived && (
              <>
                <span>📥 Received: {formatTime(order.received_at || order.placed_at) || 'Just now'}</span>
                <span>⏳ Waiting: {formatElapsed(elapsed)}</span>
              </>
            )}
            {isPreparing && (
              <>
                <span>🔥 Prep time: {formatElapsed(elapsed)}</span>
                <span style={{ fontWeight: 600, color: isPrepDelayed ? '#dc2626' : '#0369a1' }}>
                  ⏳ Expected: {estMins}:00
                </span>
              </>
            )}
            {isReady && (
              <>
                <span>🛎️ Ready for: {formatElapsed(elapsed)}</span>
                <span style={{ color: '#16a34a', fontWeight: 600 }}>🍽️ Ready to serve</span>
              </>
            )}
            {isServed && (
              <>
                <span>✓ Served at {formatTime(order.served_at || order.ready_at)}</span>
                <span>Total: {formatElapsed(elapsed)}</span>
              </>
            )}
          </div>

          {/* Time-Based Alert Banners */}
          {isWaitingTooLong && (
            <div style={{ background: '#fef2f2', border: '1px solid #f87171', color: '#b91c1c', padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              ⚠️ ORDER WAITING: Waiting for {Math.floor(elapsed / 60)}m. Please start prep!
            </div>
          )}
          {isPrepDelayed && (
            <div style={{ background: '#fef2f2', border: '1px solid #f87171', color: '#b91c1c', padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              ⚠️ PREPARATION DELAY: {Math.floor(elapsed / 60)}m (+{overdueMins}m late). Check order!
            </div>
          )}
          {isReady && !isFoodWaiting && (
            <div style={{ background: '#f0fdf4', border: '1px solid #86efac', color: '#15803d', padding: '2px 6px', borderRadius: '4px', fontWeight: 600, fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              🍽️ Waiting for waiter to collect
            </div>
          )}
          {isFoodWaiting && (
            <div style={{ background: '#fffbeb', border: '1px solid #fcd34d', color: '#b45309', padding: '2px 6px', borderRadius: '4px', fontWeight: 700, fontSize: '0.7rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
              ⚠️ FOOD WAITING: Ready for {Math.floor(elapsed / 60)}m. Waiter pickup needed!
            </div>
          )}
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

        {/* Action Button Bar with Confirmation */}
        {buttonLabel && (
          <div className="card-strip__action-bar" onClick={(e) => e.stopPropagation()}>
            {!confirmingNext ? (
              <button
                type="button"
                className={`kds-button ${btnClass}`}
                onClick={(e) => {
                  e.stopPropagation()
                  setConfirmingNext(true)
                }}
                disabled={updating}
              >
                {updating ? 'UPDATING...' : buttonLabel}
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '6px', width: '100%' }}>
                <button
                  type="button"
                  className="kds-button kds-button--confirm"
                  onClick={handleConfirmedAdvance}
                  disabled={updating}
                  style={{ flex: 1, background: '#16a34a', color: '#fff', fontWeight: 700 }}
                >
                  {updating ? 'UPDATING...' : confirmLabel}
                </button>
                <button
                  type="button"
                  className="kds-button kds-button--cancel"
                  onClick={(e) => {
                    e.stopPropagation()
                    setConfirmingNext(false)
                  }}
                  disabled={updating}
                  style={{ padding: '0.4rem 0.75rem', background: '#e2e8f0', color: '#475569' }}
                  title="Cancel"
                >
                  ✕
                </button>
              </div>
            )}
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