/**
 * Extended API client — new endpoints for menu, orders, reservations, AI, QR
 * Drop this into src/api/extensions.ts and import in your existing client.ts
 */

const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function humanizeStatus(status: number, detail?: string): string {
  if (status === 401) return 'Your session has expired. Please log in again.'
  if (status === 403) return 'You do not have permission to do this.'
  if (status === 404) return 'The requested item was not found.'
  if (status === 500) return 'Something went wrong. Please try again.'
  return detail ?? 'Something went wrong. Please try again.'
}

function getToken(): string | null {
  return localStorage.getItem('foh_access_token')
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  if (USE_MOCK) {
    throw new Error('This page requires VITE_USE_MOCK=false and a running backend API.')
  }
  const token = getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  if (res.status === 401) {
    localStorage.removeItem('foh_access_token')
    localStorage.removeItem('foh_token_expires')
    sessionStorage.setItem('foh_session_expired', '1')
    window.location.href = '/login'
    throw new Error('Your session has expired. Please log in again.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string' ? body.detail : undefined
    throw new Error(humanizeStatus(res.status, detail))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ─── Menu ────────────────────────────────────────────────────────────────────

export interface MenuItem {
  id: string
  name: string
  description?: string
  price: number
  category: string
  available: boolean
  displayOrder: number
}

export const menuApi = {
  list: () => apiFetch<MenuItem[]>('/menu/all'),
  listPublic: () => apiFetch<MenuItem[]>('/menu'),
  create: (data: Omit<MenuItem, 'id'>) =>
    apiFetch<MenuItem>('/menu/items', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: string, data: Partial<MenuItem>) =>
    apiFetch<MenuItem>(`/menu/items/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  remove: (id: string) =>
    apiFetch<void>(`/menu/items/${id}`, { method: 'DELETE' }),
  toggle: (id: string, available: boolean) => {
    // The API determines the next state server-side; retain the caller's
    // desired state in the public API for compatibility with existing views.
    void available
    return apiFetch<MenuItem>(`/menu/items/${id}/toggle`, { method: 'PATCH' })
  },
}

// ─── Orders ──────────────────────────────────────────────────────────────────

export interface OrderItem { id: string; itemName: string; category?: string; unitPrice: number; quantity: number }
export interface Order {
  id: string; sessionId: string; tableId: string
  tableNumber?: string | null
  placedAt: string; status: string
  source?: 'bot' | 'waiter' | string
  approvalStatus?: 'PENDING' | 'APPROVED' | 'REJECTED' | string
  notes?: string | null
  items: OrderItem[]
}

export const ordersApi = {
  list: (params?: { tableId?: string; sessionId?: string; approvalStatus?: string }) => {
    const q = new URLSearchParams()
    if (params?.tableId) q.set('table_id', params.tableId)
    if (params?.sessionId) q.set('session_id', params.sessionId)
    if (params?.approvalStatus) q.set('approval_status', params.approvalStatus)
    return apiFetch<Order[]>(`/orders?${q}`)
  },
  place: (tableId: string, items: { menuItemId: string; quantity: number }[], sessionId?: string) =>
    apiFetch<Order>('/orders', {
      method: 'POST',
      body: JSON.stringify({ tableId, items, sessionId }),
    }),
  approve: (orderId: string) =>
    apiFetch<Order>(`/orders/${orderId}/approve`, { method: 'POST' }),
  reject: (orderId: string, reason?: string) =>
    apiFetch<Order>(`/orders/${orderId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
}

// ─── Billing ─────────────────────────────────────────────────────────────────

export interface BillItem { itemName: string; category?: string; unitPrice: number; quantity: number; lineTotal: number }
export interface Bill {
  id: string; sessionId: string; subtotal: number; total: number
  status: string; generatedAt: string; paidAt?: string; paymentMethod?: string; items: BillItem[]
}

export const billingApi = {
  requestBill: (sessionId: string) =>
    apiFetch<Bill>(`/sessions/${sessionId}/request-bill`, { method: 'POST' }),
  getBill: (sessionId: string) =>
    apiFetch<Bill>(`/sessions/${sessionId}/bill`),
  getUpiQr: (sessionId: string) =>
    apiFetch<{ upiLink: string; amount: number }>(`/sessions/${sessionId}/upi-qr`),
  markPaid: (sessionId: string, method: 'CASH' | 'UPI' | 'CARD' = 'CASH') =>
    apiFetch<Bill>(`/sessions/${sessionId}/mark-paid`, { method: 'POST', body: JSON.stringify({ method }) }),
}

// ─── Reservations ─────────────────────────────────────────────────────────────

export interface Reservation {
  id: string; tableId: string; guestName: string
  partySize: number; reservedFor: string; reservedUntil: string
  status: string; notes?: string
}

export const reservationsApi = {
  list: () => apiFetch<Reservation[]>('/reservations'),
  create: (data: {
    tableId: string; guestName: string; partySize: number
    reservedFor: string; reservedUntil: string; notes?: string
  }) => apiFetch<Reservation>('/reservations', { method: 'POST', body: JSON.stringify(data) }),
  release: (id: string) =>
    apiFetch<Reservation>(`/reservations/${id}/release`, { method: 'POST' }),
}

// ─── AI ───────────────────────────────────────────────────────────────────────

export interface AIEventMetadata {
  alert_category?: string
  severity?: string
  table_id?: string
  table_number?: string
  session_id?: string
  unpaid_total?: number
  item_count?: number
  guest_name?: string
  party_size?: number
  items?: Array<{
    item_name: string
    unit_price: number
    quantity: number
    line_total: number
  }>
  detected_at?: string
  reason?: string
  resolution?: string
  resolved_at?: string
  notes?: string
}

export interface AIEvent {
  id: string
  tableId?: string
  eventType: string
  message: string
  targetRole?: string
  createdAt: string
  resolved: boolean
  acknowledged?: boolean
  metadata?: AIEventMetadata | null
}
export interface SeatingResponse { suggestion: string; partySize: number }
export interface ShiftReport { reportDate: string; content: string; stats: Record<string, unknown> }
export interface ChatMessage { role: 'user' | 'assistant'; content: string }
export interface ChatAction { tool: string; summary: string; ok: boolean }
export interface ChatResponse { reply: string; aiGenerated?: boolean; actions?: ChatAction[] }

export const aiApi = {
  suggestSeating: (partySize: number) =>
    apiFetch<SeatingResponse>('/ai/seating-suggest', {
      method: 'POST', body: JSON.stringify({ partySize }),
    }),
  getAlerts: (resolved = false) =>
    apiFetch<AIEvent[]>(`/ai/events?resolved=${resolved}`),
  resolveAlert: (id: string) =>
    apiFetch<{ id: string; resolved: boolean }>(`/ai/events/${id}/resolve`, { method: 'PATCH' }),
  acknowledgeAlert: (id: string) =>
    apiFetch<AIEvent>(`/ai/events/${id}/acknowledge`, { method: 'PATCH' }),
  getShiftReport: (date?: string) =>
    apiFetch<ShiftReport>(`/ai/reports/shift${date ? `?date=${date}` : ''}`),
  chat: (input: string | ChatMessage[], history: ChatMessage[] = []) => {
    if (Array.isArray(input)) {
      return apiFetch<ChatResponse>('/ai/chat', {
        method: 'POST', body: JSON.stringify({ messages: input }),
      })
    }
    return apiFetch<ChatResponse>('/ai/chat', {
      method: 'POST', body: JSON.stringify({ message: input, history }),
    })
  },
}

// ─── Loss Prevention ──────────────────────────────────────────────────────────

export const lossPreventionApi = {
  resolve: (
    eventId: string,
    resolution: 'PAID_COUNTER' | 'FALSE_ALARM' | 'LOGGED_UNRECOVERED',
    notes?: string
  ) =>
    apiFetch<{
      event_id: string
      resolved: boolean
      resolution: string
      resolved_at: string
    }>('/ai/loss-prevention/resolve', {
      method: 'POST',
      body: JSON.stringify({ event_id: eventId, resolution, notes }),
    }),
  simulate: (tableIdentifier: string) =>
    apiFetch<{
      success: boolean
      event_id: string
      table_number: string
      unpaid_total: number
      message: string
    }>('/ai/loss-prevention/simulate', {
      method: 'POST',
      body: JSON.stringify({ table_identifier: tableIdentifier }),
    }),
  getSummary: () =>
    apiFetch<{
      total_incidents: number
      active_alerts: number
      active_exposure: number
      prevented_amount: number
      unrecovered_amount: number
      recent_incidents: Array<{
        id: string
        table_number?: string
        unpaid_total: number
        created_at: string
        resolved: boolean
        resolution?: string
        guest_name?: string
      }>
    }>('/ai/loss-prevention/summary'),
}

// ─── QR ───────────────────────────────────────────────────────────────────────

export const qrApi = {
  printUrl: (tableId: string) => `${API_URL}/tables/${tableId}/qr`,
  rotate: (tableId: string) =>
    apiFetch<{ token: string; message: string }>(`/tables/${tableId}/qr/rotate`, { method: 'POST' }),
}

// ─── Voice Receptionist ──────────────────────────────────────────────────────

export interface VoiceSimulationResponse {
  success: boolean
  status: 'CONFIRMED' | 'UNAVAILABLE'
  voice_response: string
  table_id?: string | null
  table_number?: string | null
  reservation_id?: string | null
  parsed_details: {
    guest_name: string
    party_size: number
    date: string
    time: string
    special_requests?: string | null
    phone?: string
    raw_transcript: string
  }
  suggested_alternative_time?: string
}

export const voiceReceptionistApi = {
  simulateCall: (transcript: string, callerPhone?: string) =>
    apiFetch<VoiceSimulationResponse>('/voice/simulate-call', {
      method: 'POST',
      body: JSON.stringify({ transcript, caller_phone: callerPhone }),
    }),
  parseOnly: (transcript: string) =>
    apiFetch<any>('/voice/parse-only', {
      method: 'POST',
      body: JSON.stringify({ transcript }),
    }),
}
