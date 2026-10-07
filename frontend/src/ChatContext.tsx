import { createContext, useContext } from 'react'
import type { ProductCard } from './chat'

// Search results the chat agent put on the page (shown on the Products page).
export interface PageResults {
  id: number
  title: string
  products: ProductCard[]
}

interface ChatControls {
  isOpen: boolean
  setOpen: (open: boolean) => void
  pageResults: PageResults | null
  setPageResults: (results: PageResults | null) => void
}

export const ChatContext = createContext<ChatControls>({
  isOpen: false,
  setOpen: () => {},
  pageResults: null,
  setPageResults: () => {},
})

export function useChat(): ChatControls {
  return useContext(ChatContext)
}
