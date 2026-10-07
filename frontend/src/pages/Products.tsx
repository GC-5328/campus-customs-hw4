import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchProducts, type Product } from '../api'
import { useChat } from '../ChatContext'
import ProductCard from '../components/ProductCard'
import { filterProducts, TYPE_SHORTCUTS } from '../productSearch'

export default function Products() {
  const { pageResults, setPageResults } = useChat()
  const [products, setProducts] = useState<Product[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // The search lives in the URL (?q=hoodie) so Back and shared links keep it.
  const [searchParams, setSearchParams] = useSearchParams()
  const query = searchParams.get('q') ?? ''
  const visible = useMemo(() => (products ? filterProducts(products, query) : null), [products, query])

  function setQuery(value: string) {
    setSearchParams(value ? { q: value } : {}, { replace: true })
  }

  useEffect(() => {
    fetchProducts()
      .then(setProducts)
      .catch((err: Error) => setError(err.message))
  }, [])

  // Search results from the chat agent replace the full catalogue until cleared.
  if (pageResults) {
    return (
      <section>
        <div className="results-header">
          <div>
            <p className="eyebrow">From chat</p>
            <h1>{pageResults.title}</h1>
            <p className="muted">
              {pageResults.products.length} {pageResults.products.length === 1 ? 'item' : 'items'}
            </p>
          </div>
          <button className="button button-secondary" onClick={() => setPageResults(null)}>
            Show all products
          </button>
        </div>
        <div className="product-grid results-grid" key={pageResults.id}>
          {pageResults.products.map((p) => (
            <ProductCard key={p.product_id} product={p} />
          ))}
        </div>
      </section>
    )
  }

  return (
    <section>
      <h1>Products</h1>
      {error && <p className="error">Couldn't load products: {error}. Is the backend running?</p>}
      {!error && !products && <p className="muted">Loading products…</p>}
      {products && visible && (
        <>
          <div className="search-bar">
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name or type — e.g. hoodie, crewneck, Game shirt"
              aria-label="Search products"
            />
            {query && (
              <button className="search-clear" onClick={() => setQuery('')} aria-label="Clear search">
                ×
              </button>
            )}
          </div>
          <div className="type-chips" role="group" aria-label="Filter by type">
            {TYPE_SHORTCUTS.map((t) => (
              <button
                key={t.query}
                className={`chip${query === t.query ? ' active' : ''}`}
                onClick={() => setQuery(query === t.query ? '' : t.query)}
              >
                {t.label}
              </button>
            ))}
          </div>
          <p className="muted" aria-live="polite">
            {query ? `${visible.length} of ${products.length} items match “${query}”` : `${products.length} items`}
          </p>
          {visible.length === 0 ? (
            <div className="empty-state">
              <p>No products match “{query}”.</p>
              <p className="muted">Try a type like “hoodie” or “tee”, or ask the chat.</p>
              <button className="button button-secondary" onClick={() => setQuery('')}>
                Show all products
              </button>
            </div>
          ) : (
            <div className="product-grid">
              {visible.map((p) => (
                <ProductCard key={p.product_id} product={p} />
              ))}
            </div>
          )}
        </>
      )}
    </section>
  )
}
