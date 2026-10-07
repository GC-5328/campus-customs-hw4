// Chat client for the FastAPI agent routes (backend/main.py):
//   POST /api/chat          message + page context (+ history for guests) -> reply and product cards
//   GET  /api/chat/history  saved chat for the logged-in shopper

import type { SizeStock } from './api'

export type ChatRole = 'user' | 'assistant'

export interface ProductCard {
  product_id: string
  name: string
  garment_type: string
  description: string
  price: number
  image_url: string
  colors: string[]
  inventory: SizeStock[]
}

export interface ChatMessage {
  role: ChatRole
  content: string
  products?: ProductCard[]
  pageTitle?: string | null
  local?: boolean // greeting bubbles shown by the site, never sent to the agent
}

// page_title set => the agent ran a catalogue search and `products` should be
// shown as a results grid on the page (see ChatWidget + pages/Products.tsx).
export interface ChatReply {
  reply: string
  products: ProductCard[]
  page_title: string | null
}

// Where the shopper is; the server checks product ids before the agent sees them.
export interface PageContext {
  path: string
  results_title?: string | null
}

interface StoredChatMessage {
  id: number
  role: ChatRole
  content: string
  products: ProductCard[]
  page_title: string | null
  created_at: string
}

const MAX_HISTORY = 20

export async function fetchChatHistory(): Promise<ChatMessage[]> {
  const res = await fetch('/api/chat/history')
  if (!res.ok) return []
  const data = (await res.json()) as { messages: StoredChatMessage[] }
  return data.messages.map((m) => ({ role: m.role, content: m.content, products: m.products, pageTitle: m.page_title }))
}

export async function sendChatMessage(message: string, history: ChatMessage[], page: PageContext): Promise<ChatReply> {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      // Only used for guests; logged-in history is read from the database.
      history: history.filter((m) => !m.local).slice(-MAX_HISTORY).map(({ role, content }) => ({ role, content })),
      page,
    }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Please try again.')
  }
  return res.json() as Promise<ChatReply>
}
