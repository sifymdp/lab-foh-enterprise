export type Role = 'OWNER' | 'MANAGER' | 'HOST' | 'WAITER' | 'CASHIER' | 'CHEF'


export type BillStatus = 'DRAFT' | 'OPEN' | 'READY_FOR_PAYMENT' | 'PAID' | 'CANCELLED' | 'REFUNDED'
export type PaymentStatus = 'PENDING' | 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'REFUNDED'
export type PaymentMethod = 'CASH' | 'CARD' | 'UPI' | 'QR' | 'ONLINE'

export interface BillItem {
  name: string
  quantity: number
  unitPrice: number
  subtotal: number
}

export interface BillDetail {
  id: string
  billNumber: string | null
  sessionId: string | null
  tableNumber: string | null
  items: BillItem[]
  subtotal: number
  discountAmount: number
  discountReason: string | null
  serviceChargeAmount: number
  taxAmount: number
  total: number
  status: BillStatus
  createdBy: string | null
  createdByName: string | null
  generatedAt: string
  paidAt: string | null
  notes: string | null
  upi_qr_payload?: string
  tax_rate?: number
  service_charge_rate?: number
}

export interface BillSummary {
  id: string
  sessionId: string
  subtotal: number
  discountAmount: number
  serviceChargeAmount: number
  taxAmount: number
  total: number
  status: BillStatus
}

export interface PaymentRecord {
  paymentId: string
  billId: string
  method: PaymentMethod
  amount: number
  paymentStatus: PaymentStatus
  transactionId: string | null
  paidAt: string
}

export interface CashierShift {
  id: string
  cashierId: string
  cashierName: string
  branchId: string | null
  openingCash: number
  closingCash: number | null
  cashSales: number
  cardSales: number
  upiSales: number
  qrSales: number
  onlineSales: number
  refundTotal: number
  discountTotal: number
  expectedCash: number | null
  actualCash: number | null
  difference: number | null
  openedAt: string
  closedAt: string | null
  status: 'OPEN' | 'CLOSED'
  notes: string | null
}

export interface RefundRequest {
  id: string
  billId: string
  paymentId: string | null
  requestType: 'REFUND' | 'DISCOUNT' | 'CANCELLATION'
  amount: number | null
  reason: string
  status: 'PENDING' | 'APPROVED' | 'REJECTED'
  requestedBy: string
  requesterName: string
  approvedBy: string | null
  createdAt: string
  resolvedAt: string | null
  resolutionNotes: string | null
}

export interface PaymentMethodSummary {
  cash: number
  card: number
  upi: number
  qr: number
  online: number
  total: number
}

export interface DailyRevenueSummary {
  date: string
  totalBills: number
  paidBills: number
  pendingBills: number
  cancelledBills: number
  refundedBills: number
  grossRevenue: number
  discountTotal: number
  taxTotal: number
  serviceChargeTotal: number
  netRevenue: number
  paymentMethods: PaymentMethodSummary
}

export interface CashierSummary {
  cashierId: string
  cashierName: string
  billsCount: number
  totalAmount: number
}

export interface AuditLog {
  id: string
  userId: string | null
  userName?: string | null
  userEmail?: string | null
  userRole?: string | null
  action: string
  resourceType: string
  resourceId: string | null
  oldValue: string | null
  newValue: string | null
  createdAt: string
}


export type TableStatus =
  | 'AVAILABLE'
  | 'RESERVED'
  | 'BOOKED'
  | 'SEATED'
  | 'ACTIVE'
  | 'OCCUPIED'
  | 'BILLING'
  | 'PAID'
  | 'CLEANING'
  | 'MAINTENANCE'

export type TableType = 'STANDARD' | 'BOOTH' | 'BAR' | 'VIP'

export type TableShape = 'CIRCLE' | 'RECTANGLE'

export type FloorLabelKind = 'ENTRANCE' | 'KITCHEN' | 'BAR' | 'CUSTOM'

export interface RectBounds {
  x: number
  y: number
  width: number
  height: number
}

export interface User {
  id: string
  name: string
  email: string
  role: Role
  isActive: boolean
}

export interface AuthUser {
  id: string
  name: string
  email: string
  role: Role
  permissions?: string[]
}

export interface Section {
  id: string
  name: string
  color: string
  bounds: RectBounds
  description?: string
  outdoors?: boolean
  smokingAllowed?: boolean
}

export interface FloorLabel {
  id: string
  kind: FloorLabelKind
  text: string
  bounds: RectBounds
}

export interface Table {
  id: string
  sectionId: string
  number: string
  capacity: number
  type: TableType
  shape: TableShape
  status: TableStatus
  x: number
  y: number
  width: number
  height: number
  rotation: number
  cameraUrl?: string | null
  roiCoords?: RectBounds | null
}

export interface CameraRoiSuggestion {
  frameWidth: number
  frameHeight: number
  sampledFrames: number
  method: string
  confidence: number
  roiCoords: RectBounds
  candidates: RectBounds[]
}

export interface CameraSceneDetection {
  label: 'clean' | 'dirty' | 'occupied'
  confidence: number
  bounds: RectBounds
}

export interface CameraSnapshotAnalysis {
  frameWidth: number
  frameHeight: number
  roiUsed?: RectBounds | null
  roiLabel?: 'clean' | 'dirty' | 'occupied' | null
  roiConfidence?: number | null
  sceneSummary: Record<'clean' | 'dirty' | 'occupied', number>
  sceneDetections: CameraSceneDetection[]
}

export interface DiningSession {
  id: string
  tableId: string
  guestName?: string
  partySize: number
  seatedAt: string
  status: TableStatus
}

export interface Floor {
  id: string
  name: string
  width: number
  height: number
  sections: Section[]
  labels: FloorLabel[]
  tables: Table[]
}

export interface FloorStats {
  total: number
  available: number
  occupied: number
  reserved: number
  cleaning: number
  occupancyRate: number
  avgOccupiedMinutes: number
}

export interface CreateTablePayload {
  number: string
  capacity: number
  sectionId: string
  type: TableType
  shape: TableShape
  x?: number
  y?: number
  width?: number
  height?: number
}

export interface CreateSectionPayload {
  name: string
  color?: string
  bounds?: RectBounds
}

export interface CreateLabelPayload {
  kind: FloorLabelKind
  text: string
  bounds?: RectBounds
}

export interface LoginResponse {
  accessToken: string
  expiresAt: string
  user: AuthUser
}

export interface SeatGuestPayload {
  tableId: string
  partySize: number
  guestName?: string
}

export interface CreateUserPayload {
  name: string
  email: string
  password: string
  role: Role
}

export * from './kitchen'
