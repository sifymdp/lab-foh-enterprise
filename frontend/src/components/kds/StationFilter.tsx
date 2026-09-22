import type { KitchenStation } from '../../types'

interface StationFilterProps {
  selectedStation: KitchenStation
  onStationChange: (station: KitchenStation) => void
}

const STATIONS: Array<{ label: string; value: KitchenStation }> = [
  { label: 'ALL', value: 'ALL' },
  { label: 'MAIN KITCHEN', value: 'MAIN KITCHEN' },
  { label: 'GRILL', value: 'GRILL' },
  { label: 'FRY', value: 'FRY' },
  { label: 'PIZZA', value: 'PIZZA' },
  { label: 'BAR', value: 'BAR' },
  { label: 'DESSERT', value: 'DESSERT' },
]

export function StationFilter({ selectedStation, onStationChange }: StationFilterProps) {
  return (
    <div className="kds-station-filter">
      <label>Menu Selection:</label>
      <div className="station-buttons">
        {STATIONS.map((station) => (
          <button
            key={station.label}
            className={`station-btn ${selectedStation === station.value ? 'active' : ''}`}
            onClick={() => onStationChange(station.value)}
          >
            {station.label}
          </button>
        ))}
      </div>
    </div>
  )
}