import type { Role, AuthUser } from '../types'

/**
 * Checks if a user has a specific permission code.
 * Owners always have every permission.
 */
export function hasPermission(user: AuthUser | null | undefined, perm: string): boolean {
  if (!user) return false
  if (user.role === 'OWNER') return true
  if (user.permissions && Array.isArray(user.permissions)) {
    return user.permissions.includes(perm)
  }
  return false
}

export function canEditFloor(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'floor.edit') || hasPermission(user, 'tables.manage')
  return role === 'OWNER' || role === 'MANAGER'
}

export function canManageUsers(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'users.view') || hasPermission(user, 'users.create') || hasPermission(user, 'roles.view')
  return role === 'OWNER' || role === 'MANAGER'
}

export function canSeatGuests(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'tables.assign') || hasPermission(user, 'booking.create') || hasPermission(user, 'reservations.manage')
  return role === 'OWNER' || role === 'MANAGER' || role === 'HOST'
}

export function canChangeStatus(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'tables.manage') || hasPermission(user, 'tables.assign')
  return role === 'OWNER' || role === 'MANAGER' || role === 'HOST' || role === 'WAITER'
}

export function canManageMenu(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'menu.manage') || hasPermission(user, 'kitchen.manage')
  return role === 'OWNER' || role === 'MANAGER'
}

export function canViewReports(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'reports.view') || hasPermission(user, 'revenue.view_branch') || hasPermission(user, 'revenue.view_own')
  return role === 'OWNER' || role === 'MANAGER'
}

export function canProcessBilling(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'billing.view') || hasPermission(user, 'billing.create') || hasPermission(user, 'payment.create')
  return role === 'OWNER' || role === 'MANAGER' || role === 'CASHIER'
}

export function canViewRevenue(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'revenue.view_branch') || hasPermission(user, 'revenue.view_own') || hasPermission(user, 'revenue.view_all')
  return role === 'OWNER' || role === 'MANAGER'
}

export function canViewAuditLogs(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'audit.view')
  return role === 'OWNER' || role === 'MANAGER'
}

export function isKitchenStaff(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'kitchen.view') || hasPermission(user, 'kitchen.update') || hasPermission(user, 'orders.view')
  return role === 'CHEF' || role === 'OWNER' || role === 'MANAGER'
}

export function isChef(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'kitchen.manage') || hasPermission(user, 'kitchen.update')
  return role === 'CHEF' || role === 'OWNER' || role === 'MANAGER'
}

export function isCashier(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'payment.create') || hasPermission(user, 'cashier.shift.start') || hasPermission(user, 'billing.create')
  return role === 'CASHIER' || role === 'OWNER' || role === 'MANAGER'
}

export function isHost(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'tables.assign') || hasPermission(user, 'booking.view')
  return role === 'HOST' || role === 'OWNER' || role === 'MANAGER'
}

export function isWaiter(role: Role, user?: AuthUser | null): boolean {
  if (user) return hasPermission(user, 'orders.create') || hasPermission(user, 'orders.view')
  return role === 'WAITER' || role === 'OWNER' || role === 'MANAGER'
}
