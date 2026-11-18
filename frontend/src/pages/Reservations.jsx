import { useState } from 'react'
import { Plus, Ticket } from 'lucide-react'
import { api } from '../lib/api'
import { useLoad } from '../lib/hooks'
import { STATUS_LABELS } from '../lib/format'
import { ReservationRow } from '../components/cards'
import ReservationActions from '../components/ReservationActions'
import ReservationForm from '../components/ReservationForm'
import { Alert, Empty, Loading } from '../components/Common'

export default function Reservations() {
  const { data, error, loading } = useLoad(() => api.listReservations())
  const { data: tripData } = useLoad(() => api.listTrips())
  const [status, setStatus] = useState('')
  const [tripId, setTripId] = useState('')
  const [adding, setAdding] = useState(false)

  const trips = tripData?.trips || []
  const tripName = (id) => trips.find((t) => t.id === id)?.name
  const all = data?.reservations || []
  const list = all.filter((r) => (!status || r.status === status) && (!tripId || r.tripId === tripId))

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>Reservas</h1><p className="sub">Las reservas son <strong>simuladas</strong>: se guardan en la base de datos, sin cobro real.</p></div>
        <button className="btn btn-primary" onClick={() => setAdding(true)} disabled={!trips.length}><Plus size={16} /> Nueva reserva</button>
      </div>

      <div className="row wrap">
        <div className="chips" role="group" aria-label="Filtrar por estado">
          <button className={`chip ${status === '' ? 'active' : ''}`} onClick={() => setStatus('')}>Todas</button>
          {Object.entries(STATUS_LABELS).map(([k, v]) => (
            <button key={k} className={`chip ${status === k ? 'active' : ''}`} onClick={() => setStatus(k)}>{v}</button>
          ))}
        </div>
        {trips.length > 1 && (
          <select aria-label="Filtrar por viaje" value={tripId} onChange={(e) => setTripId(e.target.value)} style={{ width: 'auto' }}>
            <option value="">Todos los viajes</option>
            {trips.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
        )}
      </div>

      {error && <Alert>{error}</Alert>}
      {loading ? <Loading /> : list.length === 0 ? (
        <Empty icon={Ticket} title="No hay reservas">Reserva un vuelo u hotel desde sus pantallas o pídeselo al asistente.</Empty>
      ) : (
        <div className="stack">
          {list.map((r) => (
            <div key={r.id} className="stack" style={{ gap: 6 }}>
              {r.tripId && <span className="small muted">Viaje: {tripName(r.tripId) || r.tripId}</span>}
              {!r.tripId && <span className="small muted">Sin viaje asociado</span>}
              <ReservationRow reservation={r} actions={<ReservationActions reservation={r} trips={trips} />} />
            </div>
          ))}
        </div>
      )}
      {adding && <ReservationForm trips={trips} onClose={() => setAdding(false)} />}
    </div>
  )
}
