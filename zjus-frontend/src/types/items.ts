export interface GameItem {
  id: string
  name: string
  category: string
  description: string
  price: number
  sell_price: number
  tags: string[]
  effects: Record<string, number>
}

export interface ItemsState {
  version?: string | number
  economy?: Record<string, unknown>
  items: GameItem[]
  owned: string[]
  bonuses: Record<string, number>
  updated_at?: number
}
