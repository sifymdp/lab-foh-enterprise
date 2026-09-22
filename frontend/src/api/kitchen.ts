import { API_URL, getToken } from './client'

// Get all kitchen orders
export async function getKitchenOrders(): Promise<any[]> {
  const token = getToken()

  const response = await fetch(`${API_URL}/orders/kitchen`, {
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })

  if (!response.ok) {
    const text = await response.text()
    console.error('Kitchen orders error:', response.status, text)

    throw new Error(
      `Failed to load kitchen orders: ${response.status}`
    )
  }

  return response.json()
}


// Update order status
export async function updateOrderStatus(
  orderId: string,
  newStatus: string
): Promise<any> {

  const token = getToken()

  const response = await fetch(
    `${API_URL}/orders/${orderId}/status`,
    {
      method: 'PATCH',

      headers: {
        'Content-Type': 'application/json',
        ...(token
          ? { Authorization: `Bearer ${token}` }
          : {}),
      },

      body: JSON.stringify({
        status: newStatus,
      }),
    }
  )

  if (!response.ok) {

    const text = await response.text()

    console.error(
      'Update order status error:',
      response.status,
      text
    )

    throw new Error(
      `Failed to update order status: ${response.status}`
    )
  }

  return response.json()
}