import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../AuthContext'
import { logout } from '../auth'
import { useBag } from '../BagContext'

const MAIN_LINKS = [
  { to: '/', label: 'Home', end: true },
  { to: '/products', label: 'Products', end: false },
  { to: '/about', label: 'About Us', end: false },
]

export default function NavBar() {
  const { user, setUser } = useAuth()
  const { count } = useBag()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout().catch(() => null)
    setUser(null)
    navigate('/')
  }

  return (
    <header className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="brand">
          Campus Customs
        </Link>
        <nav className="nav-links" aria-label="Main">
          {MAIN_LINKS.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end}>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <nav className="nav-account" aria-label="Account">
          {user ? (
            <>
              <span className="nav-greeting">Hi, {user.first_name || user.name}</span>
              <button className="nav-text-button" onClick={handleLogout}>
                Log out
              </button>
            </>
          ) : (
            <>
              <NavLink to="/login">Log in</NavLink>
              <NavLink to="/signup">Create account</NavLink>
            </>
          )}
          <NavLink to="/bag" aria-label={`Bag, ${count} ${count === 1 ? 'item' : 'items'}`}>
            Bag{count > 0 && <span className="bag-count">{count}</span>}
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
