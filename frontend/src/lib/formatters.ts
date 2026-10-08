/**
 * Formats raw station enum strings (e.g. 'CONTINENTAL_GRILL', 'INDIAN_GRAVY')
 * into human-readable Title Case strings (e.g. 'Continental Grill', 'Indian Gravy').
 */
export function formatStationName(station?: string | null): string {
  if (!station) return ''
  return station
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

/**
 * Returns a CSS class name for styling station badges based on station type.
 */
export function getStationBadgeClass(station?: string | null): string {
  if (!station) return ''
  const s = station.toUpperCase()
  if (s.includes('GRILL')) return 'drawer-item-station--grill'
  if (s.includes('PIZZA')) return 'drawer-item-station--pizza'
  if (s.includes('BAR')) return 'drawer-item-station--bar'
  if (s.includes('DESSERT')) return 'drawer-item-station--dessert'
  if (s.includes('TANDOOR')) return 'drawer-item-station--tandoor'
  if (s.includes('FRY')) return 'drawer-item-station--fry'
  return ''
}

/**
 * Safely parses any date string (ISO with or without 'Z') into a UTC Date object.
 * Prevents timezone offset shifts where UTC dates are parsed as local time.
 */
export function parseUtcDate(iso?: string | null): Date {
  if (!iso) return new Date()
  let formatted = iso.trim().replace(' ', 'T')
  if (!formatted.endsWith('Z') && !formatted.includes('+') && !formatted.includes('-', 11)) {
    formatted += 'Z'
  }
  const d = new Date(formatted)
  return isNaN(d.getTime()) ? new Date() : d
}

/**
 * Returns elapsed seconds between two timestamps safely in UTC.
 */
export function elapsedSeconds(from?: string | null, to?: string | null): number {
  if (!from) return 0
  const start = parseUtcDate(from).getTime()
  const end = to ? parseUtcDate(to).getTime() : Date.now()
  return Math.max(0, Math.floor((end - start) / 1000))
}

/**
 * Formats elapsed seconds into mm:ss or hh:mm:ss.
 */
export function formatElapsed(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) {
    return `${h}h ${String(m).padStart(2, '0')}m`
  }
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * Normalizes ISO date strings and formats them into a clean 12-hour time format (e.g. "03:54 PM").
 * Handles missing 'Z' suffix so UTC vs Local timezone shifts are eliminated.
 */
export function formatTime(iso?: string | null): string {
  if (!iso) return ''
  const date = parseUtcDate(iso)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
