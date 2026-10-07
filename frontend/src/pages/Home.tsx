import { Link } from 'react-router-dom'

// One featured product photo (white-background web copy), not a collage.
const FEATURED = {
  id: 'champion-reverse-weave-hoodie-1',
  image: '/media/products/champion-reverse-weave-hoodie-1.jpg?v=web2',
  alt: 'Navy Champion Reverse Weave hoodie with white arched YALE lettering',
}

export default function Home() {
  return (
    <section className="hero">
      <h1>Officially licensed Yale gear.</h1>
      <p className="hero-sub">Casual comfort, classic Bulldog pride.</p>
      <Link to="/products" className="button button-large">
        Shop Bulldog Blue
      </Link>
      <Link to={`/products/${FEATURED.id}`} className="hero-image" aria-label="See the featured hoodie">
        <img src={FEATURED.image} alt={FEATURED.alt} />
      </Link>
    </section>
  )
}
