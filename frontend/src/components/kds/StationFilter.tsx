import type { KitchenOrder, KitchenStation } from '../../types'

export interface StationFilterProps {
  selectedStation: KitchenStation
  onStationChange: (station: KitchenStation) => void
  orders?: KitchenOrder[]
  layout?: 'vertical' | 'horizontal'
  className?: string
}

export function matchItemStation(item: any, stationVal: KitchenStation | string): boolean {
  if (!stationVal || stationVal === 'ALL') return true
  const st = String(item?.station || '').toUpperCase()
  const name = String(item?.item_name || '').toLowerCase()
  const cat = String(item?.category || '').toLowerCase()
  const sUpper = String(stationVal).toUpperCase()

  // 1. Direct station string match
  if (st && (st === sUpper || st.includes(sUpper) || sUpper.includes(st))) return true

  // 2. North Indian (Curries, Gravies, Dal, Biryani, Naan, Paneer)
  if (sUpper.includes('NORTH')) {
    if (st.includes('NORTH') || st.includes('GRAVY') || cat.includes('north')) return true
    if (
      /makhani|butter chicken|dal|bukhara|paneer|lababdar|awadhi|biryani|naan|roti|kulcha|gosht|korma|curry|masala|sheermal|galouti|paratha/i.test(
        name
      )
    ) {
      return true
    }
    return false
  }

  // 3. South Indian (Dosa, Idli, Vada, Chettinad, Parotta, Meen Pollichathu)
  if (sUpper.includes('SOUTH')) {
    if (st.includes('SOUTH') || cat.includes('south')) return true
    if (
      /dosa|idli|vada|chettinad|parotta|sambar|rasam|uttapam|podi|pollichathu|meen|malabar|ghee roast|curry leaf/i.test(
        name
      )
    ) {
      return true
    }
    return false
  }

  // 4. Tandoor & Kebab (Tikka, Kebabs, Grills, Charcoal)
  if (sUpper.includes('TANDOOR') || sUpper.includes('KEBAB') || sUpper.includes('GRILL')) {
    if (
      st.includes('TANDOOR') ||
      st.includes('KEBAB') ||
      st.includes('GRILL') ||
      cat.includes('tandoor') ||
      cat.includes('starter') ||
      cat.includes('kebab')
    ) {
      return true
    }
    if (/tikka|kebab|tandoor|sheekh|galouti|chaat|paneer tikka|murgh tikka|charcoal/i.test(name)) {
      return true
    }
    return false
  }

  // 5. Chinese & Pan-Asian (Dim Sum, Noodles, Wok, Hakka, Kung Pao)
  if (sUpper.includes('CHINESE') || sUpper.includes('ASIAN') || sUpper.includes('WOK')) {
    if (
      st.includes('CHINESE') ||
      st.includes('ASIAN') ||
      st.includes('WOK') ||
      cat.includes('chinese') ||
      cat.includes('asian')
    ) {
      return true
    }
    if (
      /dim sum|noodles|hakka|fried rice|manchurian|kung pao|lotus stem|wonton|edamame|chilli garlic|sea bass|schezwan/i.test(
        name
      )
    ) {
      return true
    }
    return false
  }

  // 6. Italian & Pizza (Wood-Fired Pizza, Pasta, Risotto, Continental)
  if (sUpper.includes('PIZZA') || sUpper.includes('ITALIAN') || sUpper.includes('CONTINENTAL')) {
    if (
      st.includes('PIZZA') ||
      st.includes('ITALIAN') ||
      st.includes('CONTINENTAL') ||
      cat.includes('pizza') ||
      cat.includes('pasta') ||
      cat.includes('italian') ||
      cat.includes('continental')
    ) {
      return true
    }
    if (
      /pizza|pasta|margherita|burrata|risotto|alfredo|fettuccine|lasagna|burger|fries|sandwich|penne/i.test(
        name
      )
    ) {
      return true
    }
    return false
  }

  // 7. Bar & Drinks (Cocktails, Spirits, Gin, Tonic, Brews, Beverages)
  if (sUpper.includes('BAR') || sUpper.includes('DRINK') || sUpper.includes('BEVERAGE')) {
    if (
      st.includes('BAR') ||
      st.includes('DRINK') ||
      st.includes('BEVERAGE') ||
      cat.includes('bar') ||
      cat.includes('drink') ||
      cat.includes('beverage')
    ) {
      return true
    }
    if (
      /gin|tonic|whiskey|vodka|rum|beer|wine|cocktail|mocktail|macallan|saffron gin|lassi|shake|coffee|tea|soda|cooler|juice/i.test(
        name
      )
    ) {
      return true
    }
    return false
  }

  // 8. Dessert & Sweets (Mithai, Kulfi, Halwa, Pastries, Ice Cream)
  if (sUpper.includes('DESSERT') || sUpper.includes('SWEET')) {
    if (
      st.includes('DESSERT') ||
      st.includes('SWEET') ||
      st.includes('BAKERY') ||
      cat.includes('dessert') ||
      cat.includes('sweet') ||
      cat.includes('pastry')
    ) {
      return true
    }
    if (/jamun|rasmalai|ice cream|kulfi|halwa|brownie|cake|tiramisu|sweet|mithai/i.test(name)) {
      return true
    }
    return false
  }

  // 9. Main Kitchen fallback
  if (sUpper === 'MAIN KITCHEN') {
    return true
  }

  return false
}

export function getItemDisplayStation(item: any): string {
  if (item?.station && item.station !== 'MAIN KITCHEN') return item.station
  if (matchItemStation(item, 'SOUTH INDIAN')) return 'SOUTH INDIAN'
  if (matchItemStation(item, 'NORTH INDIAN')) return 'NORTH INDIAN'
  if (matchItemStation(item, 'TANDOOR')) return 'TANDOOR'
  if (matchItemStation(item, 'CHINESE_WOK')) return 'CHINESE & ASIAN'
  if (matchItemStation(item, 'PIZZA')) return 'ITALIAN & PIZZA'
  if (matchItemStation(item, 'BAR')) return 'BAR & DRINKS'
  if (matchItemStation(item, 'DESSERT')) return 'DESSERT'
  return 'MAIN KITCHEN'
}

export const STATIONS: Array<{
  label: string
  sublabel: string
  value: KitchenStation
  icon: string
  color: string
}> = [
  { label: 'ALL SECTIONS', sublabel: 'Entire Kitchen Queue', value: 'ALL', icon: '🍳', color: '#64748b' },
  { label: 'NORTH INDIAN', sublabel: 'Curries, Gravies & Naan', value: 'NORTH INDIAN', icon: '🍛', color: '#ea580c' },
  { label: 'SOUTH INDIAN', sublabel: 'Dosa, Idli, Vada & Meals', value: 'SOUTH INDIAN', icon: '🥞', color: '#0284c7' },
  { label: 'TANDOOR & KEBAB', sublabel: 'Tikka, Kebabs & Charcoal', value: 'TANDOOR', icon: '🍢', color: '#dc2626' },
  { label: 'CHINESE & ASIAN', sublabel: 'Dim Sum, Noodles & Wok', value: 'CHINESE_WOK', icon: '🥢', color: '#eab308' },
  { label: 'ITALIAN & PIZZA', sublabel: 'Wood-Fired Pizza & Pasta', value: 'PIZZA', icon: '🍕', color: '#b45309' },
  { label: 'BAR & DRINKS', sublabel: 'Cocktails, Spirits & Beverages', value: 'BAR', icon: '🍸', color: '#8b5cf6' },
  { label: 'DESSERT & SWEETS', sublabel: 'Mithai, Kulfi & Pastries', value: 'DESSERT', icon: '🍨', color: '#ec4899' },
  { label: 'MAIN KITCHEN', sublabel: 'General Prep & Hot Line', value: 'MAIN KITCHEN', icon: '👨‍🍳', color: '#475569' },
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
      const matchItems = (order.items || []).filter((i: any) =>
        matchItemStation(i, stationVal)
      )
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