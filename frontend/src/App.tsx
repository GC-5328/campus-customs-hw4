import { useEffect, useState } from 'react'
import { Route, Routes, useLocation } from 'react-router-dom'
import { AuthContext } from './AuthContext'
import { BagProvider } from './BagContext'
import { ChatContext, type PageResults } from './ChatContext'
import { fetchCurrentUser, type User } from './auth'
import ChatWidget from './components/ChatWidget'
import NavBar from './components/NavBar'
import About from './pages/About'
import Bag from './pages/Bag'
import CreateAccount from './pages/CreateAccount'
import Home from './pages/Home'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import ProductDetail from './pages/ProductDetail'
import Products from './pages/Products'

export default function App() {
  const location = useLocation()
  const [chatOpen, setChatOpen] = useState(false)
  const [user, setUser] = useState<User | null>(null)
  const [pageResults, setPageResults] = useState<PageResults | null>(null)

  useEffect(() => {
    fetchCurrentUser().then(setUser).catch(() => setUser(null))
  }, [])

  return (
    <AuthContext.Provider value={{ user, setUser }}>
      <BagProvider>
      <ChatContext.Provider value={{ isOpen: chatOpen, setOpen: setChatOpen, pageResults, setPageResults }}>
        <NavBar />
        {/* key: 200ms fade-in on each route change */}
        <main className="page" key={location.pathname}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/products" element={<Products />} />
            <Route path="/products/:productId" element={<ProductDetail />} />
            <Route path="/about" element={<About />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<CreateAccount />} />
            <Route path="/bag" element={<Bag />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="site-footer">
          <p>Campus Customs · 57 Broadway, New Haven · Officially licensed Yale gear since 1975</p>
        </footer>
        <ChatWidget />
      </ChatContext.Provider>
      </BagProvider>
    </AuthContext.Provider>
  )
}
