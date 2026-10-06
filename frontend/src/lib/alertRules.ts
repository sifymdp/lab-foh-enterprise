import type { Role } from '../types'

export const RECEIVED_ALERT_MINUTES = 5
export const PREPARATION_ALERT_MINUTES = 15
export const READY_ALERT_MINUTES = 5

const ALERT_TOAST_ROLES: Record<string, Role[]> = {
  DIRTY_ALERT: ['WAITER'],
  DEPARTURE_ALERT: ['MANAGER'],
  WALKOUT_ALERT: ['WAITER', 'HOST', 'MANAGER', 'OWNER'],
  WAIT_ALERT: ['HOST', 'WAITER'],
  SEATING_SUGGESTION: ['HOST'],
  SHIFT_REPORT: ['MANAGER', 'OWNER'],
  KITCHEN_ORDER_WAITING: ['CHEF', 'MANAGER', 'OWNER'],
  KITCHEN_PREPARATION_DELAY: ['CHEF', 'MANAGER', 'OWNER'],
  FOOD_READY: ['WAITER', 'HOST', 'MANAGER', 'OWNER'],
  FOOD_WAITING: ['WAITER', 'HOST', 'MANAGER', 'OWNER'],
}

export function shouldShowAlertToast(eventType: string, userRole: Role): boolean {
  const allowed = ALERT_TOAST_ROLES[eventType]
  if (!allowed) return userRole === 'MANAGER' || userRole === 'OWNER'
  return allowed.includes(userRole)
}

export function shouldCountAlertBadge(eventType: string, userRole: Role): boolean {
  return shouldShowAlertToast(eventType, userRole)
}
