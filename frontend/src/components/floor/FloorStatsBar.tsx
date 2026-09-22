import type { FloorStats } from '../../types'

interface FloorStatsBarProps {
  stats: FloorStats
}

const ITEMS = [
  { key: 'total', label: 'Tables', icon: '⊞', mod: '' },
  { key: 'available', label: 'Available', icon: '○', mod: 'available' },
  { key: 'occupied', label: 'Occupied', icon: '●', mod: 'occupied' },
  { key: 'reserved', label: 'Reserved', icon: '◐', mod: 'reserved' },
  { key: 'cleaning', label: 'Cleaning', icon: '◎', mod: 'cleaning' },
  { key: 'occupancyRate', label: 'Occupancy', icon: '%', mod: 'rate', suffix: '%' },
  { key: 'avgOccupiedMinutes', label: 'Avg seated', icon: '⏱', mod: 'avg', suffix: ' min' },
] as const

export function FloorStatsBar({ stats }: FloorStatsBarProps) {
  return (
    <div className="floor-stats-bar" aria-label="Shift overview">
      {ITEMS.map((item) => {
        const { key, label, icon, mod } = item
        const suffix = 'suffix' in item ? item.suffix : undefined
        const raw = stats[key as keyof FloorStats]
        const display = suffix ? `${raw}${suffix}` : raw
        return (
          <div key={key} className={`stat-card stat-card--${mod}`}>
            <span className="stat-card__icon" aria-hidden>{icon}</span>
            <div className="stat-card__body">
              <span className="stat-value">{display}</span>
              <span className="stat-label">{label}</span>
            </div>
          </div>
        )
      })}
    </div>
  )
}
