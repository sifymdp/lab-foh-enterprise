export interface KitchenOrder {
  id: string
  table_id: string
  table_number?: string
  status: 'RECEIVED' | 'CONFIRMED' | 'PREPARING' | 'READY' | 'SERVED'
  placed_at: string
  received_at?: string | null
  preparing_at?: string | null
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
  notes?: string | null
  approval_status?: string
  estimated_prep_time_minutes?: number
}

export interface KitchenOrderItem {
  id: string
  item_id?: string
  item_name: string
  quantity: number
  unit_price?: number
  station?: string | null
  notes?: string | null
  allergy_flag?: boolean
  item_status?: string
  prep_time_minutes?: number
}

export type KitchenStation =
  | 'ALL'
  | 'MAIN KITCHEN'
  | 'NORTH INDIAN'
  | 'SOUTH INDIAN'
  | 'TANDOOR'
  | 'CHINESE_WOK'
  | 'PIZZA'
  | 'BAR'
  | 'DESSERT'
  | 'GRILL'
  | 'FRY'
  | 'INDIAN_GRAVY'
  | 'SOUTH_INDIAN'
  | 'NORTH_INDIAN'
  | 'CONTINENTAL_GRILL'
  | 'COLD_KITCHEN_SALAD'
  | 'BAKERY_CONFECTIONERY'
  | 'SWEETS_MITHAI'
  | 'BEVERAGE_BAR'
  | string

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