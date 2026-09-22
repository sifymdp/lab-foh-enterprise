import type { DiningSession, Floor, FloorStats } from '../types'

export function computeFloorStats(floor: Floor, sessions: DiningSession[] = []): FloorStats {
  const total = floor.tables.length
  const available = floor.tables.filter((t) => t.status === 'AVAILABLE').length
  const reserved = floor.tables.filter((t) => t.status === 'RESERVED').length
  const cleaning = floor.tables.filter((t) => t.status === 'CLEANING').length
  const occupied = floor.tables.filter((t) =>
    ['SEATED', 'ACTIVE'].includes(t.status),
  ).length
  const occupancyRate = total > 0 ? Math.round((occupied / total) * 100) : 0

  const now = Date.now()
  let totalMinutes = 0
  let count = 0
  for (const table of floor.tables) {
    if (!['SEATED', 'ACTIVE', 'BILLING', 'PAID'].includes(table.status)) continue
    const session = sessions.find(
      (s) => s.tableId === table.id && !['CLEANING', 'AVAILABLE'].includes(s.status),
    )
    if (session) {
      totalMinutes += (now - new Date(session.seatedAt).getTime()) / 60000
      count++
    }
  }
  const avgOccupiedMinutes = count > 0 ? Math.round(totalMinutes / count) : 0

  return { total, available, occupied, reserved, cleaning, occupancyRate, avgOccupiedMinutes }
}
