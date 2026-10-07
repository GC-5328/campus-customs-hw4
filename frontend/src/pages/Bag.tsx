import { Link } from 'react-router-dom'
import { formatPrice } from '../api'
import { useBag } from '../BagContext'

export default function Bag() {
  const { items, count, subtotal, remove } = useBag()

  if (items.length === 0) {
    return (
      <section className="bag bag-empty">
        <h1>Your bag is empty.</h1>
        <Link to="/products" className="button">
          Shop Bulldog Blue
        </Link>
      </section>
    )
  }

  return (
    <section className="bag">
      <h1>Your bag</h1>
      <ul className="bag-list">
        {items.map((item) => (
          <li key={`${item.product_id}-${item.size}`} className="bag-item">
            <Link to={`/products/${item.product_id}`} className="bag-item-image">
              <img src={item.image_url} alt={item.name} />
            </Link>
            <div className="bag-item-info">
              <Link to={`/products/${item.product_id}`} className="bag-item-name">
                {item.name}
              </Link>
              <p className="muted">
                Size {item.size} · Qty {item.quantity}
              </p>
            </div>
            <div className="bag-item-side">
              <p>{formatPrice(item.price * item.quantity)}</p>
              <button className="text-button" onClick={() => remove(item.product_id, item.size)}>
                Remove
              </button>
            </div>
          </li>
        ))}
      </ul>
      <div className="bag-total">
        <span>
          Subtotal ({count} {count === 1 ? 'item' : 'items'})
        </span>
        <strong>{formatPrice(subtotal)}</strong>
      </div>
      <p className="muted bag-note">Pay and pick up at Campus Customs, 57 Broadway, New Haven. Online checkout is coming soon.</p>
    </section>
  )
}
