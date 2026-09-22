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
 * Normalizes ISO date strings and formats them into a clean 12-hour time format (e.g. "03:54 PM").
 * Handles missing 'Z' suffix so UTC vs Local timezone shifts are eliminated.
 */
export function formatTime(iso?: string | null): string {
  if (!iso) return ''
  let formatted = iso.trim().replace(' ', 'T')
  // If missing timezone offset or Z, append 'Z' for consistent UTC parsing
  if (!formatted.endsWith('Z') && !formatted.includes('+') && !formatted.includes('-', 11)) {
    formatted += 'Z'
  }
  const date = new Date(formatted)
  if (isNaN(date.getTime())) return ''
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}
