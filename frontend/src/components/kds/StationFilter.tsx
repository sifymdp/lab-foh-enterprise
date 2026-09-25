import type { KitchenOrder, KitchenStation } from '../../types'

export interface StationFilterProps {
  selectedStation: KitchenStation
  onStationChange: (station: KitchenStation) => void
  orders?: KitchenOrder[]
  layout?: 'vertical' | 'horizontal'
  className?: string
}

export const STATIONS: Array<{
  label: string
  sublabel: string
  value: KitchenStation
  icon: string
  color: string
}> = [
  { label: 'ALL SECTIONS', sublabel: 'Entire Kitchen Queue', value: 'ALL', icon: '🍳', color: '#64748b' },
  { label: 'MAIN KITCHEN', sublabel: 'Mains & Curries', value: 'MAIN KITCHEN', icon: '👨‍🍳', color: '#0284c7' },
  { label: 'GRILL', sublabel: 'Steaks & BBQ', value: 'GRILL', icon: '🥩', color: '#ea580c' },
  { label: 'FRY', sublabel: 'Deep Fry & Appetizers', value: 'FRY', icon: '🍟', color: '#eab308' },
  { label: 'PIZZA', sublabel: 'Oven & Flatbreads', value: 'PIZZA', icon: '🍕', color: '#dc2626' },
  { label: 'BAR', sublabel: 'Drinks & Cocktails', value: 'BAR', icon: '🍸', color: '#8b5cf6' },
  { label: 'DESSERT', sublabel: 'Sweets & Pastry', value: 'DESSERT', icon: '🍨', color: '#ec4899' },
]

export function StationFilter({
  selectedStation,
  onStationChange,
  orders = [],
  layout = 'vertical',
  className = '',
}: StationFilterProps) {
  // Count active pending / in-prep items for each station
  const activeOrders = orders.filter(
    (o) => o.status === 'RECEIVED' || o.status === 'PREPARING'
  )

  const getStationCount = (stationVal: KitchenStation): number => {
    if (activeOrders.length === 0) return 0
    if (stationVal === 'ALL') {
      return activeOrders.reduce(
        (sum, order) =>
          sum + (order.items || []).reduce((s: number, i: any) => s + (i.quantity || 1), 0),
        0
      )
    }

    return activeOrders.reduce((sum, order) => {
      const matchItems = (order.items || []).filter((i: any) => {
        const itemStation = (i.station || 'MAIN KITCHEN').toUpperCase()
        if (stationVal === 'MAIN KITCHEN') {
          return itemStation === 'MAIN KITCHEN' || !i.station
        }
        return itemStation === stationVal.toUpperCase()
      })
      return sum + matchItems.reduce((s: number, i: any) => s + (i.quantity || 1), 0)
    }, 0)
  }

  const totalActiveItems = getStationCount('ALL')

  return (
    <div
      className={`kds-station-nav ${
        layout === 'vertical' ? 'kds-station-nav--vertical' : 'kds-station-nav--horizontal'
      } ${className}`}
    >
      <div className="kds-station-nav__header">
        <div className="kds-station-nav__title-row">
          <span className="kds-station-nav__icon">👨‍🍳</span>
          <h3 className="kds-station-nav__title">Prep Stations</h3>
        </div>
        <p className="kds-station-nav__subtitle">
          {selectedStation === 'ALL'
            ? `${totalActiveItems} active item${totalActiveItems !== 1 ? 's' : ''}`
            : `Active: ${selectedStation}`}
        </p>
      </div>

      <div
        className="kds-station-nav__list"
        role="tablist"
        aria-label="Kitchen Prep Stations"
      >
        {STATIONS.map((station) => {
          const isActive = selectedStation === station.value
          const count = getStationCount(station.value)

          return (
            <button
              key={station.value}
              type="button"
              role="tab"
              aria-selected={isActive}
              className={`kds-station-tile ${isActive ? 'kds-station-tile--active' : ''}`}
              onClick={() => onStationChange(station.value)}
              title={`${station.label} (${station.sublabel}) — ${count} items pending`}
            >
              <span className="kds-station-tile__icon">{station.icon}</span>
              <span className="kds-station-tile__name">{station.label}</span>

              <div className="kds-station-tile__meta">
                <span
                  className={`kds-station-tile__badge ${
                    count > 0 ? 'kds-station-tile__badge--active-items' : ''
                  }`}
                >
                  {count}
                </span>
                {isActive && (
                  <span className="kds-station-tile__check" aria-hidden="true">✓</span>
                )}
              </div>
            </button>
          )
        })}
      </div>

      {layout === 'vertical' && selectedStation !== 'ALL' && (
        <div className="kds-station-nav__footer">
          <button
            type="button"
            className="kds-station-nav__reset-btn"
            onClick={() => onStationChange('ALL')}
          >
            ↺ All Stations
          </button>
        </div>
      )}
    </div>
  )
}