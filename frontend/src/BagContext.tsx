import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

// A simple shopping bag kept in the browser (localStorage). There's no online
// checkout yet; the Bag page sends shoppers to pay and pick up at 57 Broadway.

export interface BagItem {
  product_id: string
  name: string
  price: number
  image_url: string
  size: string
  quantity: number
}

interface BagState {
  items: BagItem[]
  count: number
  subtotal: number
  add: (item: Omit<BagItem, 'quantity'>, maxQuantity: number) => boolean
  remove: (productId: string, size: string) => void
}

const STORAGE_KEY = 'cc_bag'
const BagContext = createContext<BagState | null>(null)

function load(): BagItem[] {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(saved) ? saved : []
  } catch {
    return []
  }
}

export function BagProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<BagItem[]>(load)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items))
  }, [items])

  // Returns false if the bag already holds every unit in stock for that size.
  const add = useCallback((item: Omit<BagItem, 'quantity'>, maxQuantity: number) => {
    const existing = items.find((i) => i.product_id === item.product_id && i.size === item.size)
    if ((existing?.quantity ?? 0) >= maxQuantity) return false
    setItems((prev) =>
      existing
        ? prev.map((i) => (i === existing ? { ...i, quantity: i.quantity + 1 } : i))
        : [...prev, { ...item, quantity: 1 }],
    )
    return true
  }, [items])

  const remove = useCallback((productId: string, size: string) => {
    setItems((prev) => prev.filter((i) => !(i.product_id === productId && i.size === size)))
  }, [])

  const value = useMemo(
    () => ({
      items,
      count: items.reduce((n, i) => n + i.quantity, 0),
      subtotal: items.reduce((n, i) => n + i.quantity * i.price, 0),
      add,
      remove,
    }),
    [items, add, remove],
  )
  return <BagContext.Provider value={value}>{children}</BagContext.Provider>
}

export function useBag(): BagState {
  const bag = useContext(BagContext)
  if (!bag) throw new Error('useBag must be used inside <BagProvider>')
  return bag
}
