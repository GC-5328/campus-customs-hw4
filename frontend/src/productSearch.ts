// Client-side product filtering for the Products search bar.
// Every word the shopper types must match the product's name, type, or tags.

import type { Product } from './api'

// Shopper words -> catalogue wording (mirrors backend/tools.py SYNONYMS).
const SYNONYMS: Record<string, string> = { tee: 't-shirt', tshirt: 't-shirt', hoody: 'hoodie', sweater: 'sweat' }

export const TYPE_SHORTCUTS = [
  { label: 'Hoodies', query: 'hoodie' },
  { label: 'Crewnecks', query: 'crewneck' },
  { label: 'Tees', query: 'tee' },
  { label: 'Quarter-zips', query: 'quarter-zip' },
  { label: 'Jackets', query: 'jacket' },
]

function words(query: string): string[] {
  return query
    .toLowerCase()
    .split(/\s+/)
    .map((w) => w.replace(/^[^a-z0-9$]+|[^a-z0-9]+$/g, ''))
    .filter(Boolean)
    .map((w) => (w.length > 3 && w.endsWith('s') && !w.endsWith('ss') ? w.slice(0, -1) : w))
    .map((w) => SYNONYMS[w] ?? w)
}

function haystack(p: Product): string {
  return `${p.name} ${p.garment_type} ${p.search_tags.join(' ')}`.toLowerCase().replace(/-/g, ' ')
}

export function filterProducts(products: Product[], query: string): Product[] {
  const terms = words(query).map((w) => w.replace(/-/g, ' '))
  if (terms.length === 0) return products
  return products.filter((p) => {
    const text = haystack(p)
    return terms.every((t) => text.includes(t))
  })
}
