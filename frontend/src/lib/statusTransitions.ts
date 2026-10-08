export {
  STATUS_TRANSITIONS,
  getNextStatuses,
  isValidTransition,
} from '../services/tableConfig'

import { STATUS_CONFIG } from '../services/tableConfig'

export const STATUS_LABELS = Object.fromEntries(
  Object.entries(STATUS_CONFIG).map(([k, v]) => [k, v.label]),
) as Record<keyof typeof STATUS_CONFIG, string>
