import { Link, useLocation } from 'react-router-dom'
import { formatPrice, type Product } from '../api'

// Used for the full catalogue and for search results the chat put on the page.
export type CardProduct = Pick<Product, 'product_id' | 'name' | 'price' | 'image_url' | 'description'>

export default function ProductCard({ product }: { product: CardProduct }) {
  // Remember the list (incl. ?q= search) so the product page's back link returns to it.
  const location = useLocation()
  return (
    <Link to={`/products/${product.product_id}`} state={{ from: location.pathname + location.search }} className="product-card">
      <div className="product-card-image">
        <img src={product.image_url} alt={product.name} loading="lazy" />
      </div>
      <div className="product-card-body">
        <h3>{product.name}</h3>
        <p className="price">{formatPrice(product.price)}</p>
        <p className="product-card-desc">{product.description}</p>
      </div>
    </Link>
  )
}
