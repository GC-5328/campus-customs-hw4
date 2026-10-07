import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { formatPrice } from '../api'
import { useAuth } from '../AuthContext'
import { useChat } from '../ChatContext'
import { fetchChatHistory, sendChatMessage, type ChatMessage, type PageContext, type ProductCard } from '../chat'

// How many cards to show inside the chat when the full results are on the page.
const CHAT_PREVIEW_COUNT = 3

function greeting(firstName: string | null, returning: boolean): ChatMessage {
  const content = returning
    ? `Welcome back, ${firstName}! Your earlier chat is above. What can I help you find today?`
    : `Hi${firstName ? ` ${firstName}` : ''}! Looking for something? Ask me about hoodies, tees, sizes, or what's in stock.`
  return { role: 'assistant', content, local: true }
}

function ChatProductCard({ product }: { product: ProductCard }) {
  const sizes = product.inventory.filter((s) => s.quantity > 0).map((s) => s.size)
  return (
    <Link to={`/products/${product.product_id}`} className="chat-product">
      <img src={product.image_url} alt={product.name} loading="lazy" />
      <span className="chat-product-text">
        <span className="chat-product-name">{product.name}</span>
        <span className="chat-product-meta">
          {formatPrice(product.price)} · {sizes.length ? sizes.join(' ') : 'Sold out'}
        </span>
      </span>
    </Link>
  )
}

export default function ChatWidget() {
  const { isOpen, setOpen, pageResults, setPageResults } = useChat()
  const { user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [messages, setMessages] = useState<ChatMessage[]>([greeting(null, false)])
  const [input, setInput] = useState('')
  const [waiting, setWaiting] = useState(false)
  const listRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, waiting, isOpen])

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  // Logged in: load the saved chat. Logged out / guest: start fresh (kept only for this visit).
  const userId = user?.id ?? null
  const firstName = user ? user.first_name || user.name : null
  useEffect(() => {
    if (userId === null) {
      setMessages([greeting(null, false)])
      return
    }
    let cancelled = false
    fetchChatHistory().then((saved) => {
      if (!cancelled) setMessages(saved.length ? [...saved, greeting(firstName, true)] : [greeting(firstName, false)])
    })
    return () => {
      cancelled = true
    }
  }, [userId, firstName])

  // Sent with every message so the agent knows what "this" refers to.
  function currentPage(): PageContext {
    const onResults = location.pathname === '/products' && pageResults
    return { path: location.pathname, results_title: onResults ? pageResults.title : null }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const text = input.trim()
    if (!text || waiting) return

    const history = messages
    setMessages([...messages, { role: 'user', content: text }])
    setInput('')
    setWaiting(true)
    try {
      const { reply, products, page_title } = await sendChatMessage(text, history, currentPage())
      setMessages((prev) => [...prev, { role: 'assistant', content: reply, products, pageTitle: page_title }])
      if (page_title && products.length > 0) showOnPage(page_title, products)
    } catch (err) {
      setMessages((prev) => [...prev, { role: 'assistant', content: (err as Error).message }])
    } finally {
      setWaiting(false)
      inputRef.current?.focus()
    }
  }

  // A catalogue search from the agent: render its matches as the Products page grid.
  function showOnPage(title: string, products: ProductCard[]) {
    setPageResults({ id: Date.now(), title, products })
    if (location.pathname !== '/products') navigate('/products')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  if (!isOpen) {
    return (
      <button className="chat-launcher" onClick={() => setOpen(true)} aria-label="Ask Campus Customs" title="Ask Campus Customs">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path
            d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8a2.5 2.5 0 0 1-2.5 2.5H10l-4.2 3.6c-.5.4-1.3.1-1.3-.6V16A2.5 2.5 0 0 1 4 13.5v-8Z"
            fill="currentColor"
          />
        </svg>
      </button>
    )
  }

  return (
    <section className="chat-panel" aria-label="Chat with Campus Customs">
      <header className="chat-header">
        <span>Ask Campus Customs</span>
        <button onClick={() => setOpen(false)} aria-label="Close chat">
          ×
        </button>
      </header>
      <div className="chat-messages" ref={listRef}>
        {messages.map((m, i) => (
          <div key={i} className={`chat-turn ${m.role}`}>
            <div className={`chat-bubble ${m.role}`}>{m.content}</div>
            {m.products && m.products.length > 0 && (
              <div className="chat-products">
                {(m.pageTitle ? m.products.slice(0, CHAT_PREVIEW_COUNT) : m.products).map((p) => (
                  <ChatProductCard key={p.product_id} product={p} />
                ))}
                {m.pageTitle && (
                  <button className="chat-see-all" onClick={() => showOnPage(m.pageTitle!, m.products!)}>
                    See all {m.products.length} on the page →
                  </button>
                )}
              </div>
            )}
          </div>
        ))}
        {waiting && (
          <div className="chat-bubble assistant typing" aria-label="Assistant is typing">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>
      <form className="chat-input" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message…"
          aria-label="Message"
          maxLength={2000}
        />
        <button type="submit" disabled={!input.trim() || waiting}>
          Send
        </button>
      </form>
    </section>
  )
}
