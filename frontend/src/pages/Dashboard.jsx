import { Link } from 'react-router-dom'
import { Bot, CloudSun, Luggage, Plane, Ticket, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { useLoad } from '../lib/hooks'
import { useAuth } from '../auth-context'
import { formatCOP } from '../lib/format'
import { ReservationRow, TripCard } from '../components/cards'
import { Alert, Empty, Loading } from '../components/Common'

const QUICK = [
  { to: '/chat', label: 'Asistente IA', icon: Bot },
  { to: '/flights', label: 'Buscar vuelos', icon: Plane },
  { to: '/weather', label: 'Ver clima', icon: CloudSun },
  { to: '/trips/new', label: 'Nuevo viaje', icon: Luggage },
]

export default function Dashboard() {
  const { user } = useAuth()
  const { data, error, loading } = useLoad(() => api.dashboard())
  const name = (user?.email || '').split('@')[0]

  return (
    <div className="stack">
      <div className="hero-card stack">
        <h1 style={{ color: '#fff' }}>Hola, {name} 👋</h1>
        <p>Organiza tu próximo viaje con agentes de vuelos, clima y hoteles.</p>
        <div><Link className="btn" to="/chat" style={{ background: '#fff', color: '#0037b0' }}><Bot size={16} /> Planear con el asistente</Link></div>
      </div>

      <div className="grid cols-3">
        {QUICK.map(({ to, label, icon: Icon }) => (
          <Link key={to} to={to} className="card row" style={{ textDecoration: 'none', color: 'inherit' }}>
            <Icon size={22} color="var(--primary)" /> <strong>{label}</strong>
          </Link>
        ))}
      </div>

      {error && <Alert>{error}</Alert>}
      {loading ? <Loading rows={3} /> : data && (
        <>
          <div className="grid cols-3">
            <div className="card"><div className="small muted"><Wallet size={14} /> Saldo del monedero</div><div className="kpi num">{formatCOP(data.walletBalanceCOP)}</div><Link className="small" to="/wallet">Recargar</Link></div>
            <div className="card"><div className="small muted"><Luggage size={14} /> Viajes</div><div className="kpi">{data.counts.trips}</div><Link className="small" to="/trips">Ver todos</Link></div>
            <div className="card"><div className="small muted"><Ticket size={14} /> Reservas activas</div><div className="kpi">{data.counts.reservations}</div><span className="small muted">{formatCOP(data.totalReservedCOP)} reservados</span></div>
          </div>

          <div className="section-title"><h2>Próximos viajes</h2><Link className="small" to="/trips">Ver todos</Link></div>
          {data.upcomingTrips.length === 0 ? (
            <Empty icon={Luggage} title="Aún no tienes viajes próximos">Cuéntale al asistente a dónde quieres ir o crea uno manualmente.</Empty>
          ) : (
            <div className="grid cols-2">{data.upcomingTrips.map((t) => <TripCard key={t.id} trip={t} />)}</div>
          )}

          <div className="section-title"><h2>Reservas recientes</h2><Link className="small" to="/reservations">Ver todas</Link></div>
          {data.recentReservations.length === 0 ? (
            <Empty icon={Ticket} title="Sin reservas todavía" />
          ) : (
            <div className="stack">{data.recentReservations.map((r) => <ReservationRow key={r.id} reservation={r} />)}</div>
          )}
        </>
      )}
    </div>
  )
}
