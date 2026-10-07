import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { fetchProduct, formatPrice, type Product, type SizeStock } from '../api'
import { useBag } from '../BagContext'
import { useChat } from '../ChatContext'

const LOW_STOCK = 5 // same threshold as the agent's check_stock

function stockLabel(quantity: number): string {
  if (quantity === 0) return 'Sold out'
  return quantity <= LOW_STOCK ? `Only ${quantity} left` : `${quantity} left`
}

function SizePicker({ sizes, selected, onSelect }: { sizes: SizeStock[]; selected: string | null; onSelect: (size: string) => void }) {
  const inStock = sizes.filter((s) => s.quantity > 0)

  if (inStock.length === 0) {
    return <p className="out-of-stock">Sold out in every size right now.</p>
  }

  return (
    <div className="size-pills" role="radiogroup" aria-label="Choose a size">
      {sizes.map((s) => {
        const soldOut = s.quantity === 0
        return (
          <button
            key={s.size}
            type="button"
            role="radio"
            aria-checked={selected === s.size}
            aria-label={`${s.size}, ${stockLabel(s.quantity)}`}
            disabled={soldOut}
            className={`size-pill${soldOut ? ' sold-out' : ''}${selected === s.size ? ' selected' : ''}`}
            onClick={() => onSelect(s.size)}
          >
            <span className="size">{s.size}</span>
            <span className="qty">{stockLabel(s.quantity)}</span>
          </button>
        )
      })}
    </div>
  )
}

function AddToBag({ product, size }: { product: Product; size: string | null }) {
  const { add } = useBag()
  const [status, setStatus] = useState<'idle' | 'added' | 'limit'>('idle')
  const stock = product.inventory.find((s) => s.size === size)?.quantity ?? 0

  useEffect(() => setStatus('idle'), [size])

  function handleAdd() {
    if (!size) return
    const ok = add(
      { product_id: product.product_id, name: product.name, price: product.price, image_url: product.image_url, size },
      stock,
    )
    setStatus(ok ? 'added' : 'limit')
  }

  return (
    <div className="add-to-bag">
      <button type="button" className="button button-large button-block" disabled={!size} onClick={handleAdd}>
        Add to bag
      </button>
      <p className="add-status" aria-live="polite" key={status}>
        {!size && 'Select a size.'}
        {size && status === 'idle' && `Size ${size}: ${stock} left${stock <= LOW_STOCK ? ', grab it soon' : ''}.`}
        {status === 'added' && (
          <>
            Added size {size} to your bag. <Link to="/bag">View bag</Link>
          </>
        )}
        {status === 'limit' && <span className="out-of-stock">You have all {stock} in size {size} in your bag.</span>}
      </p>
    </div>
  )
}

export default function ProductDetail() {
  const { productId } = useParams<{ productId: string }>()
  const { pageResults } = useChat()
  const location = useLocation()
  // Back to wherever the card was clicked: chat results, a search (?q=), or the full list.
  const from = (location.state as { from?: string } | null)?.from
  const searched = from?.startsWith('/products?') ? new URLSearchParams(from.split('?')[1]).get('q') : null
  const back = pageResults
    ? { to: '/products', label: `← Back to ${pageResults.title}` }
    : searched
      ? { to: from!, label: `← Back to “${searched}”` }
      : { to: '/products', label: '← All products' }

  const [product, setProduct] = useState<Product | null>(null)
  const [size, setSize] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!productId) return
    setProduct(null)
    setSize(null)
    setError(null)
    fetchProduct(productId)
      .then(setProduct)
      .catch((err: Error) => setError(err.message))
  }, [productId])

  const backLink = (
    <Link to={back.to} className="back-link">
      {back.label}
    </Link>
  )

  if (error) {
    return (
      <section>
        {backLink}
        <p className="error">{error === 'Not found' ? "We couldn't find that product." : error}</p>
      </section>
    )
  }

  if (!product) return <p className="muted">Loading…</p>

  return (
    <section>
      {backLink}
      <div className="product-detail">
        <div className="product-detail-image">
          <img src={product.image_url} alt={product.name} />
        </div>
        <div className="product-detail-info">
          <h1>{product.name}</h1>
          <p className="detail-price">{formatPrice(product.price)}</p>
          <p className="detail-description">{product.description}</p>
          {product.colors.length > 0 && <p className="muted detail-colors">{product.colors.join(' · ')}</p>}

          {product.inventory.length > 0 && (
            <div className="detail-sizes">
              <h2>Size</h2>
              <SizePicker sizes={product.inventory} selected={size} onSelect={setSize} />
            </div>
          )}
          <AddToBag product={product} size={size} />
        </div>
      </div>
    </section>
  )
}
