import { NavLink, Outlet, useLocation } from 'react-router-dom'
import {
  Bot, BedDouble, CloudSun, Home, LogOut, Luggage, MoreHorizontal, PlusCircle, Plane, SlidersHorizontal, Sparkles, Ticket, Wallet,
} from 'lucide-react'
import { useAuth } from '../auth-context'

const NAV = [
  { to: '/', label: 'Inicio', icon: Home, end: true },
  { to: '/chat', label: 'Asistente IA', icon: Bot },
  { to: '/trips', label: 'Mis viajes', icon: Luggage, match: (p) => p.startsWith('/trips') && p !== '/trips/new' },
  { to: '/trips/new', label: 'Nuevo viaje', icon: PlusCircle },
  { to: '/flights', label: 'Vuelos', icon: Plane },
  { to: '/weather', label: 'Clima', icon: CloudSun },
  { to: '/hotels', label: 'Hoteles', icon: BedDouble },
  { to: '/reservations', label: 'Reservas', icon: Ticket },
  { to: '/wallet', label: 'Monedero', icon: Wallet },
  { to: '/preferences', label: 'Preferencias', icon: SlidersHorizontal },
]

const MOBILE = [
  { to: '/', label: 'Inicio', icon: Home, end: true },
  { to: '/chat', label: 'Asistente', icon: Bot },
  { to: '/trips', label: 'Viajes', icon: Luggage },
  { to: '/reservations', label: 'Reservas', icon: Ticket },
  { to: '/more', label: 'Más', icon: MoreHorizontal },
]

function Brand() {
  return (
    <NavLink to="/" className="brand" aria-label="TripPlanner AI, inicio">
      <span className="brand-mark"><Sparkles size={18} /></span>
      TripPlanner AI
    </NavLink>
  )
}

export default function Layout() {
  const { user, logout } = useAuth()
  const { pathname } = useLocation()
  const initial = (user?.email || '?')[0].toUpperCase()
  return (
    <div className="app">
      <nav className="sidebar" aria-label="Navegación principal">
        <Brand />
        {NAV.map(({ to, label, icon: Icon, end, match }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `navlink ${(match ? match(pathname) : isActive) ? 'active' : ''}`}>
            <Icon size={20} aria-hidden="true" /> {label}
          </NavLink>
        ))}
        <div className="spacer" />
        <div className="small muted" style={{ padding: '0 14px', wordBreak: 'break-all' }}>{user?.email}</div>
        <button className="navlink" style={{ border: 0, background: 'none', cursor: 'pointer' }} onClick={logout}>
          <LogOut size={20} aria-hidden="true" /> Cerrar sesión
        </button>
      </nav>

      <div className="shell">
        <header className="topbar">
          <Brand />
          <div className="row">
            <span className="small muted" style={{ maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{user?.email}</span>
            <span className="avatar" aria-hidden="true">{initial}</span>
          </div>
        </header>
        <main className="main" id="contenido">
          <Outlet />
        </main>
      </div>

      <nav className="bottomnav" aria-label="Navegación móvil">
        {MOBILE.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} className={({ isActive }) => `navlink ${isActive || (to === '/trips' && pathname.startsWith('/trips')) ? 'active' : ''}`}>
            <Icon size={22} aria-hidden="true" /> {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

/** Menu "Mas" (movil): accesos que no caben en la barra inferior. */
export function MorePage() {
  const { logout } = useAuth()
  const extra = NAV.filter((n) => ['/trips/new', '/flights', '/weather', '/hotels', '/wallet', '/preferences'].includes(n.to))
  return (
    <div className="stack">
      <div className="page-head"><h1>Más opciones</h1></div>
      <div className="grid cols-2">
        {extra.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className="card row" style={{ textDecoration: 'none', color: 'inherit' }}>
            <Icon size={22} color="var(--primary)" /> <strong>{label}</strong>
          </NavLink>
        ))}
      </div>
      <button className="btn btn-danger" onClick={logout}><LogOut size={16} /> Cerrar sesión</button>
    </div>
  )
}
