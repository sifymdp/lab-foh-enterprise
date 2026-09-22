import { STATUS_CONFIG } from '../services/tableConfig'
import type { TableStatus } from '../types'

export const STATUS_COLORS = Object.fromEntries(
  Object.entries(STATUS_CONFIG).map(([k, v]) => [k, v.border]),
) as Record<TableStatus, string>

export { STATUS_CONFIG }
