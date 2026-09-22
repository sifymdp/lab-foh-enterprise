/**
 * API client — uses mock store until FastAPI backend is connected.
 * Set VITE_USE_MOCK=false and VITE_API_URL when backend is ready.
 */
import type {
  AuthUser,
  AuditLog,
  CameraRoiSuggestion,
  CameraSnapshotAnalysis,
  CreateTablePayload,
  CreateUserPayload,
  DiningSession,
  Floor,
  LoginResponse,
  RectBounds,
  SeatGuestPayload,
  Table,
  TableStatus,
  User,
} from '../types'
import type { KitchenOrder } from '../types/kitchen'
import { humanizeApiError } from '../lib/apiErrors'
import * as mock from '../mock/store'

export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
export const API_URL = import.meta.env.VITE_API_URL || (typeof window !== 'undefined' && window.location.port === '5173' ? '' : 'http://127.0.0.1:8000')

type ApiSection = {
  id: string
  name: string
  color: string
  bounds?: RectBounds
  points?: { x: number; y: number }[]
  description?: string
  outdoors?: boolean
  smokingAllowed?: boolean
}

type ApiFloorLabel = Floor['labels'][number]

type ApiFloorPayload = Omit<Floor, 'sections'> & {
  sections: Array<{
    id: string
    name: string
    color: string
    points: { x: number; y: number }[]
    description?: string
    outdoors?: boolean
    smokingAllowed?: boolean
  }>
  labels: ApiFloorLabel[]
}

function pointsToBounds(points: { x: number; y: number }[]): RectBounds {
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const minX = Math.min(...xs)
  const minY = Math.min(...ys)
  return {
    x: minX,
    y: minY,
    width: Math.max(...xs) - minX,
    height: Math.max(...ys) - minY,
  }
}

function boundsToPoints(bounds: RectBounds): { x: number; y: number }[] {
  const { x, y, width, height } = bounds
  return [
    { x, y },
    { x: x + width, y },
    { x: x + width, y: y + height },
    { x, y: y + height },
  ]
}

function normalizeFloor(floor: Floor & { sections?: ApiSection[] }): Floor {
  return {
    ...floor,
    sections: (floor.sections ?? []).map((s) => {
      const sec = s as ApiSection
      return {
        id: sec.id,
        name: sec.name,
        color: sec.color,
        bounds: sec.bounds ?? (sec.points?.length ? pointsToBounds(sec.points) : { x: 0, y: 0, width: 100, height: 100 }),
        description: sec.description,
        outdoors: sec.outdoors,
        smokingAllowed: sec.smokingAllowed,
      }
    }),
  }
}

function toApiFloorPayload(floor: Floor): ApiFloorPayload {
  return {
    ...floor,
    sections: floor.sections.map((section) => ({
      id: section.id,
      name: section.name,
      color: section.color,
      points: boundsToPoints(section.bounds),
      description: section.description,
      outdoors: section.outdoors,
      smokingAllowed: section.smokingAllowed,
    })),
    labels: floor.labels,
  }
}

export function getToken(): string | null {
  return localStorage.getItem('foh_access_token')
}

export function normalizeKitchenOrder(order: Record<string, unknown>): KitchenOrder {
  return {
    ...order,
    id: String(order.id ?? ''),
    table_id: String(order.table_id ?? order.tableId ?? ''),
    table_number: String(order.table_number ?? order.tableNumber ?? ''),
    placed_at: String(order.placed_at ?? order.placedAt ?? ''),
    status: String(order.status ?? 'RECEIVED') as KitchenOrder['status'],
    preparation_started_at: (order.preparation_started_at ?? order.preparationStartedAt ?? null) as string | null,
    ready_at: (order.ready_at ?? order.readyAt ?? null) as string | null,
    served_at: (order.served_at ?? order.servedAt ?? null) as string | null,
    items: Array.isArray(order.items)
      ? order.items.map((item) => {
          const value = item as Record<string, unknown>
          return {
            id: String(value.id ?? ''),
            item_name: String(value.item_name ?? value.itemName ?? 'Unknown item'),
            quantity: Number(value.quantity ?? 0),
            unit_price: Number(value.unit_price ?? value.unitPrice ?? 0),
            station: (value.station ?? null) as string | null,
          }
        })
      : [],
  }
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken()
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const isPublicRoute = typeof window !== 'undefined' && (
    window.location.pathname.startsWith('/pay/') ||
    window.location.pathname.startsWith('/table-pay/') ||
    window.location.pathname.startsWith('/book') ||
    window.location.pathname.startsWith('/customer/') ||
    window.location.pathname === '/login'
  )
  if (res.status === 401 && path !== '/auth/login' && !isPublicRoute) {
    localStorage.removeItem('foh_access_token')
    localStorage.removeItem('foh_token_expires')
    sessionStorage.setItem('foh_session_expired', '1')
    window.location.href = '/login'
    throw new Error('Your session has expired. Please log in again.')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = typeof body.detail === 'string'
      ? body.detail
      : (Array.isArray(body.detail) ? body.detail[0]?.msg : undefined)
    const err = new Error(detail || humanizeApiError(null, res.status) || res.statusText)
      ; (err as Error & { status: number }).status = res.status
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  getBillingBills(): Promise<Array<{ id: string; sessionId: string; subtotal: number; discountAmount: number; serviceChargeAmount: number; taxAmount: number; total: number; status: string }>> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/billing/bills')
  },
  login(email: string, password: string): Promise<LoginResponse> {
    if (USE_MOCK) return mock.mockLogin(email, password)
    return apiFetch('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })
  },

  getMe(): Promise<AuthUser> {
    const token = getToken()
    if (!token) throw new Error('No token')
    if (USE_MOCK) return mock.mockGetMe(token)
    return apiFetch('/auth/me')
  },

  getFloor(): Promise<Floor> {
    if (USE_MOCK) return mock.mockGetFloor()
    return apiFetch<Floor & { sections?: ApiSection[] }>('/floors/current').then(normalizeFloor)
  },

  updateFloor(floor: Floor): Promise<Floor> {
    if (USE_MOCK) return mock.mockUpdateFloor(floor)
    return apiFetch<Floor & { sections?: ApiSection[] }>('/floors/current', {
      method: 'PUT',
      body: JSON.stringify(toApiFloorPayload(floor)),
    }).then(normalizeFloor)
  },

  updateTable(tableId: string, patch: Partial<Table>): Promise<Table> {
    if (USE_MOCK) return mock.mockUpdateTable(tableId, patch)
    return apiFetch(`/tables/${tableId}`, {
      method: 'PUT',
      body: JSON.stringify(patch),
    })
  },

  patchTableStatus(tableId: string, status: TableStatus): Promise<Table> {
    if (USE_MOCK) return mock.mockPatchTableStatus(tableId, status)
    return apiFetch(`/tables/${tableId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    })
  },

  addTable(payload: CreateTablePayload): Promise<Table> {
    if (USE_MOCK) return mock.mockAddTable(payload)
    return apiFetch('/tables', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  deleteTable(tableId: string): Promise<void> {
    if (USE_MOCK) return mock.mockDeleteTable(tableId)
    return apiFetch(`/tables/${tableId}`, { method: 'DELETE' })
  },

  resetFloorLayout(): Promise<Floor> {
    if (USE_MOCK) return mock.mockResetFloorLayout()
    return apiFetch('/floors/current/reset', { method: 'POST' })
  },

  createSession(payload: SeatGuestPayload): Promise<DiningSession> {
    if (USE_MOCK) return mock.mockCreateSession(payload)
    return apiFetch('/sessions/seat', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  closeSession(sessionId: string): Promise<DiningSession> {
    if (USE_MOCK) return mock.mockCloseSession(sessionId)
    return apiFetch(`/sessions/${sessionId}/close`, { method: 'POST' })
  },

  getSessions(): Promise<DiningSession[]> {
    if (USE_MOCK) return mock.mockGetSessions()
    return apiFetch('/sessions')
  },

  getOrders(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/orders')
  },

  getUsers(): Promise<User[]> {
    if (USE_MOCK) return mock.mockGetUsers()
    return apiFetch('/users')
  },

  createUser(payload: CreateUserPayload): Promise<User> {
    if (USE_MOCK) return mock.mockCreateUser(payload)
    return apiFetch('/users', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  setUserActive(userId: string, isActive: boolean): Promise<User> {
    if (USE_MOCK) return mock.mockSetUserActive(userId, isActive)
    return apiFetch(`/users/${userId}/active`, {
      method: 'PATCH',
      body: JSON.stringify({ isActive }),
    })
  },

  // Returns a browser-local object URL pointing at one JPEG frame from the
  // table's camera. Caller is responsible for revoking it (URL.revokeObjectURL)
  // when done, to avoid leaking memory.
  async getCameraSnapshot(tableId: string): Promise<string> {
    if (USE_MOCK) return mock.mockGetCameraSnapshot(tableId)
    const token = getToken()
    const res = await fetch(`${API_URL}/tables/${tableId}/camera/snapshot`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || 'Could not load camera snapshot')
    }
    const blob = await res.blob()
    return URL.createObjectURL(blob)
  },

  async uploadCameraVideo(tableId: string, file: File): Promise<{ cameraUrl: string; filename: string }> {
    if (USE_MOCK) {
      return { cameraUrl: `/mock/uploads/${file.name}`, filename: file.name }
    }
    const token = getToken()
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${API_URL}/tables/${tableId}/camera/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData,
    })
    if (!res.ok) {
      const body = await res.json().catch(() => ({}))
      throw new Error(body.detail || 'Could not upload video')
    }
    return res.json()
  },

  async autoDetectCameraRoi(tableId: string): Promise<CameraRoiSuggestion> {
    if (USE_MOCK) return mock.mockAutoDetectCameraRoi(tableId)
    return apiFetch<CameraRoiSuggestion>(`/tables/${tableId}/camera/auto-roi`, {
      method: 'POST',
    })
  },

  async analyzeCameraSnapshot(tableId: string, roiCoords?: RectBounds | null): Promise<CameraSnapshotAnalysis> {
    if (USE_MOCK) return mock.mockAnalyzeCameraSnapshot(tableId, roiCoords)
    return apiFetch<CameraSnapshotAnalysis>(`/tables/${tableId}/camera/analyze-snapshot`, {
      method: 'POST',
      body: JSON.stringify({ roiCoords: roiCoords ?? null }),
    })
  },

  // ── Upgraded FOH endpoints ──────────────────────────────────────────────────
  getBills(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/billing/bills')
  },

  getReadySessions(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/billing/ready-sessions')
  },

  createBill(payload: { session_id: string; notes?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({ id: 'mock-bill' })
    return apiFetch('/billing/bills', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getBillDetail(billId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve(null)
    return apiFetch(`/billing/bills/${billId}`)
  },

  processPayment(billId: string, payload: { method: string; amount: number; transaction_id?: string | null; shift_id?: string | null }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/billing/bills/${billId}/pay`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  cancelBill(billId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/billing/bills/${billId}/cancel`, {
      method: 'POST',
    })
  },

  applyDiscount(billId: string, payload: { percent: number; reason: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/billing/bills/${billId}/discount`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  startShift(payload: { opening_cash: number; notes?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({ id: 'mock-shift', status: 'OPEN' })
    return apiFetch('/cashier-shifts/start', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  endShift(shiftId: string, payload: { closing_cash: number; actual_cash: number; notes?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/cashier-shifts/${shiftId}/end`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  getCurrentShift(): Promise<any> {
    if (USE_MOCK) return Promise.resolve(null)
    return apiFetch('/cashier-shifts/current')
  },

  getMyShifts(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/cashier-shifts/my')
  },

  getShifts(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/cashier-shifts')
  },

  createRefundRequest(payload: { bill_id: string; payment_id?: string | null; request_type: string; amount?: number | null; reason: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/refunds', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  approveRefund(requestId: string, payload: { resolution_notes?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/refunds/${requestId}/approve`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  rejectRefund(requestId: string, payload: { resolution_notes?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/refunds/${requestId}/reject`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    })
  },

  getRefundRequests(status?: string): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    const query = status ? `?status=${status}` : ''
    return apiFetch(`/refunds${query}`)
  },

  async getDailyRevenue(date?: string, branchId?: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    const params = new URLSearchParams()
    if (date) params.append('date', date)
    if (branchId) params.append('branch_id', branchId)
    const query = params.toString() ? `?${params.toString()}` : ''
    const res: any = await apiFetch(`/revenue/daily${query}`)
    if (!res) return null
    return {
      ...res,
      netRevenue: Number(res.net_revenue ?? res.netRevenue ?? 0),
      grossRevenue: Number(res.gross_revenue ?? res.grossRevenue ?? 0),
      discountTotal: Number(res.discount_total ?? res.discountTotal ?? 0),
      taxTotal: Number(res.tax_total ?? res.taxTotal ?? 0),
      serviceChargeTotal: Number(res.service_charge_total ?? res.serviceChargeTotal ?? 0),
      totalBills: Number(res.total_bills ?? res.totalBills ?? 0),
      paidBills: Number(res.paid_bills ?? res.paidBills ?? 0),
      pendingBills: Number(res.pending_bills ?? res.pendingBills ?? 0),
      cancelledBills: Number(res.cancelled_bills ?? res.cancelledBills ?? 0),
      refundedBills: Number(res.refunded_bills ?? res.refundedBills ?? 0),
    }
  },

  async getPaymentMethodSummary(date?: string, branchId?: string, cashierId?: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    const params = new URLSearchParams()
    if (date) params.append('date', date)
    if (branchId) params.append('branch_id', branchId)
    if (cashierId) params.append('cashier_id', cashierId)
    const query = params.toString() ? `?${params.toString()}` : ''
    const res: any = await apiFetch(`/revenue/payment-methods${query}`)
    if (!res) return { cash: 0, card: 0, upi: 0, qr: 0, online: 0, total: 0 }
    return {
      cash: Number(res.cash ?? 0),
      card: Number(res.card ?? 0),
      upi: Number(res.upi ?? 0),
      qr: Number(res.qr ?? 0),
      online: Number(res.online ?? 0),
      total: Number(res.total ?? 0),
    }
  },

  async getOwnRevenue(date?: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    const query = date ? `?date=${date}` : ''
    const res: any = await apiFetch(`/revenue/own${query}`)
    if (!res) return { cash: 0, card: 0, upi: 0, qr: 0, online: 0, total: 0 }
    return {
      cash: Number(res.cash ?? 0),
      card: Number(res.card ?? 0),
      upi: Number(res.upi ?? 0),
      qr: Number(res.qr ?? 0),
      online: Number(res.online ?? 0),
      total: Number(res.total ?? 0),
    }
  },

  async getCashierSummary(date?: string, branchId?: string): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    const params = new URLSearchParams()
    if (date) params.append('date', date)
    if (branchId) params.append('branch_id', branchId)
    const query = params.toString() ? `?${params.toString()}` : ''
    const list = await apiFetch(`/revenue/cashier${query}`)
    if (!Array.isArray(list)) return []
    return list.map((c: any) => ({
      ...c,
      cashierId: c.cashier_id ?? c.cashierId ?? '',
      cashierName: c.cashier_name ?? c.cashierName ?? 'Staff',
      billsCount: Number(c.bills_count ?? c.billsCount ?? 0),
      totalAmount: Number(c.total_amount ?? c.totalAmount ?? 0),
    }))
  },

  async getShiftSummary(date?: string): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    const query = date ? `?date=${date}` : ''
    const list = await apiFetch(`/revenue/shifts${query}`)
    if (!Array.isArray(list)) return []
    return list.map((s: any) => ({
      ...s,
      shiftId: s.shift_id ?? s.shiftId ?? s.id ?? '',
      cashierName: s.cashier_name ?? s.cashierName ?? 'Cashier',
      opening_cash: Number(s.opening_cash ?? s.openingCash ?? 0),
      expected_cash: s.expected_cash != null ? Number(s.expected_cash) : (s.expectedCash != null ? Number(s.expectedCash) : null),
      actual_cash: s.actual_cash != null ? Number(s.actual_cash) : (s.actualCash != null ? Number(s.actualCash) : null),
      difference: s.difference != null ? Number(s.difference) : null,
    }))
  },

  getAuditLogs(params?: {
    resource_type?: string
    action?: string
    start_date?: string
    end_date?: string
    search?: string
    limit?: number
  }): Promise<AuditLog[]> {
    if (USE_MOCK) return Promise.resolve([])
    const query = params
      ? '?' +
        Object.entries(params)
          .filter(([_, v]) => v !== undefined && v !== '' && v !== null)
          .map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`)
          .join('&')
      : ''
    return apiFetch(`/audit-logs${query}`)
  },

  getAuditLogById(id: string): Promise<AuditLog> {
    if (USE_MOCK) return Promise.resolve({} as any)
    return apiFetch(`/audit-logs/${id}`)
  },

  getKitchenOrders(): Promise<KitchenOrder[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch<Record<string, unknown>[]>('/orders/kitchen').then((data) =>
      (data || []).map(normalizeKitchenOrder)
    )
  },

  updateOrderStatus(orderId: string, payload: { status: string; notes?: string } | string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    const body = typeof payload === 'string' ? { status: payload } : payload
    return apiFetch(`/orders/${orderId}/status`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }).then((data) => normalizeKitchenOrder(data as Record<string, unknown>))
  },

  predictCookingTime(
    itemName: string,
    quantity: number = 1,
    station: string = 'INDIAN_GRAVY',
    workload: number = 0
  ): Promise<any> {
    const params = new URLSearchParams({
      item_name: itemName,
      quantity: String(quantity),
      station: station,
      current_workload: String(workload),
    })
    return apiFetch(`/orders/predict-time?${params}`)
  },

  analyzeModificationImpact(
    orderId: string,
    modificationText: string
  ): Promise<any> {
    return apiFetch(`/ai/orders/${orderId}/modification-impact`, {
      method: 'POST',
      body: JSON.stringify({ modification_text: modificationText }),
    })
  },

  // ── Dynamic RBAC ──
  getRoles(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/rbac/roles')
  },

  createCustomRole(payload: { name: string; permissions: string[] }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/rbac/roles', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  deleteCustomRole(roleName: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/rbac/roles/${encodeURIComponent(roleName)}`, {
      method: 'DELETE'
    })
  },

  getPermissionsMatrix(): Promise<any> {
    if (USE_MOCK) return Promise.resolve({ permissions: [], roles: [], matrix: [] })
    return apiFetch('/rbac/permissions/matrix')
  },

  toggleMatrixPermission(payload: { role_name: string; permission: string; enabled: boolean }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/rbac/permissions/matrix', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  bulkToggleMatrixPermissions(payload: { role_name: string; permissions: string[]; enabled: boolean }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/rbac/permissions/bulk', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  createTemporaryPermission(payload: { user_id: string; permission: string; start_time: string; end_time: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/rbac/temporary', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  listTemporaryPermissions(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/rbac/temporary')
  },

  cancelTemporaryPermission(permId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/rbac/temporary/${permId}/cancel`, {
      method: 'POST'
    })
  },

  getEffectivePermissions(userId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({ effective: [], rolePermissions: [], directPermissions: [], temporaryPermissions: [] })
    return apiFetch(`/rbac/effective/${userId}`)
  },

  toggleDirectPermission(payload: { user_id: string; permission: string; action: string; reason?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/rbac/direct-permission', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },

  listPermissionHistory(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/rbac/history')
  },

  listActiveSessions(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/rbac/sessions')
  },

  forceLogoutSession(sessionId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/rbac/sessions/${sessionId}/revoke`, {
      method: 'POST'
    })
  },

  unlockUserAccount(userId: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/rbac/users/${userId}/unlock`, {
      method: 'POST'
    })
  },

  updateUser(userId: string, payload: { name: string; email: string; role: string; status: string; branch_id?: string | null }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/users/${userId}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },

  // ── Dynamic Settings ──
  getBillingSettings(): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/billing')
  },

  updateBillingSettings(payload: { currency: string; tax_rate: number; service_charge_rate: number; receipt_header?: string; receipt_footer?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/billing', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },

  getPaymentSettings(): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/payments')
  },

  updatePaymentSettings(payload: { CASH: boolean; CARD: boolean; UPI: boolean; QR: boolean; ONLINE: boolean }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/payments', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },

  getDiscountSettings(): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/discounts')
  },

  updateDiscountSettings(payload: { cashier_max_discount: number; manager_max_discount: number; approval_above_percent: number; approval_above_amount: number }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/settings/discounts', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },

  getInsights(partySize = 2): Promise<any> {
    if (USE_MOCK) return Promise.resolve(null)
    return apiFetch(`/insights/operational?party_size=${partySize}`)
  },

  getWaitTime(partySize = 2): Promise<any> {
    if (USE_MOCK) return Promise.resolve(null)
    return apiFetch(`/insights/wait-time?party_size=${partySize}`)
  },

  // ── Vision & CCTV API ───────────────────────────────────────────────────
  getCameras(): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch('/vision/cameras')
  },

  createCamera(payload: { name: string; stream_url: string; section?: string; floor_id?: string; resolution?: string }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch('/vision/cameras', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  calibrateCamera(cameraId: string, payload: { reference_points: any[]; transformation_matrix?: number[][] }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/vision/cameras/${cameraId}/calibrate`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getCameraRois(cameraId: string): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch(`/vision/cameras/${cameraId}/rois`)
  },

  saveTableRoi(cameraId: string, payload: { table_id: string; polygon_points?: any[]; bounds?: any; active?: boolean }): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/vision/cameras/${cameraId}/rois`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  getVisionMismatches(statusFilter = 'PENDING'): Promise<any[]> {
    if (USE_MOCK) return Promise.resolve([])
    return apiFetch(`/vision/mismatches?status_filter=${statusFilter}`)
  },

  resolveVisionMismatch(mismatchId: string, action: string, notes?: string): Promise<any> {
    if (USE_MOCK) return Promise.resolve({})
    return apiFetch(`/vision/mismatches/${mismatchId}/resolve`, {
      method: 'POST',
      body: JSON.stringify({ action, notes }),
    })
  },

  getVisionTelemetry(): Promise<any> {
    if (USE_MOCK) return Promise.resolve({ model_name: 'YOLO11', ai_fps: 0, is_ready: false })
    return apiFetch('/vision/telemetry')
  },
}


