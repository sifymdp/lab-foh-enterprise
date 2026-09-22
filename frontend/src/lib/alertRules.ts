import type { Role } from '../types'

const ALERT_TOAST_ROLES: Record<string, Role[]> = {
  DIRTY_ALERT: ['WAITER'],
  DEPARTURE_ALERT: ['MANAGER'],
  WALKOUT_ALERT: ['WAITER', 'HOST', 'MANAGER', 'OWNER'],
  WAIT_ALERT: ['HOST', 'WAITER'],
  SEATING_SUGGESTION: ['HOST'],
  SHIFT_REPORT: ['MANAGER', 'OWNER'],
}

export function shouldShowAlertToast(eventType: string, userRole: Role): boolean {
  const allowed = ALERT_TOAST_ROLES[eventType]
  if (!allowed) return userRole === 'MANAGER' || userRole === 'OWNER'
  return allowed.includes(userRole)
}

export function shouldCountAlertBadge(eventType: string, userRole: Role): boolean {
  return shouldShowAlertToast(eventType, userRole)
}
