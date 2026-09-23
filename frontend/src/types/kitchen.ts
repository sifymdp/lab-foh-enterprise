export interface KitchenOrder {
  id: string
  table_id: string
  table_number?: string
  status: 'RECEIVED' | 'PREPARING' | 'READY' | 'SERVED'
  placed_at: string
  preparation_started_at?: string | null
  ready_at?: string | null
  served_at?: string | null
  items: KitchenOrderItem[]
  table?: {
    id: string
    name: string
  }
  floor?: {
    id: string
    name: string
  }
  source?: string
}

export interface KitchenOrderItem {
  id: string
  item_id?: string
  item_name: string
  quantity: number
  station?: string | null
}

export type KitchenStation =
  | 'ALL'
  | 'MAIN KITCHEN'
  | 'GRILL'
  | 'FRY'
  | 'PIZZA'
  | 'BAR'
  | 'DESSERT'
  | 'TANDOOR'
  | 'INDIAN_GRAVY'
  | 'SOUTH_INDIAN'
  | 'CHINESE_WOK'
  | 'CONTINENTAL_GRILL'
  | 'COLD_KITCHEN_SALAD'
  | 'BAKERY_CONFECTIONERY'
  | 'SWEETS_MITHAI'
  | 'BEVERAGE_BAR'

export interface CookingTimePrediction {
  estimated_minutes: number
  confidence: number
  based_on_orders: number
  reason: string
  station?: string
  workload?: number
  complexity?: string
  breakdown?: {
    base_time: number
    quantity_factor: number
    workload_factor: number
    rush_factor: number
  }
}