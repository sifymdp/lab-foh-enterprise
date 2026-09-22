import { useState } from 'react'
import type { KitchenOrder } from '../../types'

interface StatusButtonProps {
  order: KitchenOrder
  onStatusChange: (orderId: string, newStatus: string) => Promise<void>
}

export function StatusButton({ order, onStatusChange }: StatusButtonProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Decide what button to show based on current status
  let buttonLabel = ''
  let nextStatus = ''

  if (order.status === 'RECEIVED') {
    buttonLabel = 'START PREPARING'
    nextStatus = 'PREPARING'
  } else if (order.status === 'PREPARING') {
    buttonLabel = 'MARK AS READY'
    nextStatus = 'READY'
  } else if (order.status === 'READY') {
    // Kitchen can't mark as SERVED - that's the waiter's job
    return null
  }

  const handleClick = async () => {
    setIsLoading(true)
    setError(null)
    try {
      await onStatusChange(order.id, nextStatus)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update status')
      setIsLoading(false)
    }
  }

  return (
    <>
      <button
        type="button"
        className="kds-button"
        onClick={handleClick}
        disabled={isLoading}
      >
        {isLoading ? '⏳ Updating...' : buttonLabel}
      </button>
      {error && <span role="alert">{error}</span>}
    </>
  )
}