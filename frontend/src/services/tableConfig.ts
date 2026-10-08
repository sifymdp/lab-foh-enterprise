import type { TableStatus, TableType } from '../types'

export interface StatusStyle {
  label: string
  bg: string
  border: string
  text: string
}

export const DEFAULT_STATUS_STYLE: StatusStyle = {
  label: 'Unknown',
  bg: '#f1f5f9',
  border: '#94a3b8',
  text: '#475569',
}

/** Status colours for canvas tiles (implementation guide §4.2) */
const RAW_STATUS_CONFIG: Record<TableStatus | string, StatusStyle> = {
  AVAILABLE: {
    label: 'Available',
    bg: '#ecfdf5',
    border: '#22c55e',
    text: '#166534',
  },
  RESERVED: {
    label: 'Reserved',
    bg: '#eff6ff',
    border: '#3b82f6',
    text: '#1e40af',
  },
  SEATED: {
    label: 'Seated',
    bg: '#fff7ed',
    border: '#f97316',
    text: '#9a3412',
  },
  ACTIVE: {
    label: 'Active',
    bg: '#fefce8',
    border: '#eab308',
    text: '#854d0e',
  },
  OCCUPIED: {
    label: 'Active',
    bg: '#fefce8',
    border: '#eab308',
    text: '#854d0e',
  },
  BILLING: {
    label: 'Billing',
    bg: '#faf5ff',
    border: '#a855f7',
    text: '#6b21a8',
  },
  PAID: {
    label: 'Paid',
    bg: '#f0fdfa',
    border: '#14b8a6',
    text: '#115e59',
  },
  CLEANING: {
    label: 'Cleaning',
    bg: '#f8fafc',
    border: '#94a3b8',
    text: '#475569',
  },
  MAINTENANCE: {
    label: 'Maintenance',
    bg: '#fef2f2',
    border: '#ef4444',
    text: '#991b1b',
  },
}

export const STATUS_CONFIG: Record<TableStatus, StatusStyle> = new Proxy(RAW_STATUS_CONFIG, {
  get(target, prop: string | symbol) {
    if (typeof prop === 'string') {
      const upper = prop.toUpperCase()
      if (upper === 'OCCUPIED') return target.ACTIVE
      if (upper in target) return (target as any)[upper]
    }
    return (target as any)[prop] || DEFAULT_STATUS_STYLE
  },
}) as Record<TableStatus, StatusStyle>

export function getStatusStyle(status?: string | null): StatusStyle {
  if (!status) return RAW_STATUS_CONFIG.AVAILABLE
  const upper = String(status).toUpperCase()
  if (upper === 'OCCUPIED') return RAW_STATUS_CONFIG.ACTIVE
  return RAW_STATUS_CONFIG[upper] || DEFAULT_STATUS_STYLE
}

// Mirrors STATUS_TRANSITIONS in backend/app/core/status_machine.py — the API
// rejects anything not listed there, so these must stay in sync.
export const STATUS_TRANSITIONS: Record<TableStatus, TableStatus[]> = {
  AVAILABLE: ['RESERVED', 'SEATED', 'MAINTENANCE'],
  RESERVED: ['AVAILABLE', 'SEATED', 'MAINTENANCE'],
  BOOKED: ['AVAILABLE', 'SEATED', 'MAINTENANCE'],
  SEATED: ['ACTIVE', 'BILLING', 'CLEANING', 'AVAILABLE'],
  ACTIVE: ['BILLING', 'CLEANING', 'AVAILABLE'],
  OCCUPIED: ['BILLING', 'CLEANING', 'AVAILABLE'],
  BILLING: ['PAID', 'CLEANING', 'AVAILABLE'],
  PAID: ['CLEANING'],
  CLEANING: ['AVAILABLE', 'SEATED', 'MAINTENANCE'],
  MAINTENANCE: ['AVAILABLE', 'CLEANING'],
}

export function getNextStatuses(current: TableStatus): TableStatus[] {
  return STATUS_TRANSITIONS[current] ?? []
}

export function isValidTransition(from: TableStatus, to: TableStatus): boolean {
  return getNextStatuses(from).includes(to)
}

export const SECTION_ICONS: Record<string, string> = {
  Indoor: '🏠',
  Outdoor: '☀️',
  Bar: '🍸',
  VIP: '⭐',
}

export const TABLE_TYPE_LABELS: Record<TableType, string> = {
  STANDARD: 'Standard',
  BOOTH: 'Booth',
  BAR: 'Bar',
  VIP: 'VIP',
}

/** Tables in these statuses count as occupied for stats */
export const OCCUPIED_STATUSES: TableStatus[] = [
  'SEATED',
  'ACTIVE',
  'BILLING',
  'PAID',
]
