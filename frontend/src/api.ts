// Types and fetch helpers for the FastAPI backend (backend/main.py).

export interface SizeStock {
  size: string
  quantity: number
}

export interface Product {
  product_id: string
  name: string
  garment_type: string
  description: string
  colors: string[]
  search_tags: string[]
  image_file_path: string
  image_url: string
  price: number
  inventory: SizeStock[]
  total_stock: number
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    throw new Error(res.status === 404 ? 'Not found' : `Request failed (${res.status})`)
  }
  return res.json() as Promise<T>
}

export function fetchProducts(query?: string): Promise<Product[]> {
  const params = query ? `?q=${encodeURIComponent(query)}` : ''
  return getJson<Product[]>(`/api/products${params}`)
}

export function fetchProduct(productId: string): Promise<Product> {
  return getJson<Product>(`/api/products/${encodeURIComponent(productId)}`)
}

export function formatPrice(price: number): string {
  return `$${price.toFixed(2)}`
}
