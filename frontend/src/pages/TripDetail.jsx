import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { Bot, CalendarPlus, Pencil, Plus, Save, Trash2, TriangleAlert, Users } from 'lucide-react'
import { api } from '../lib/api'
import { useLoad } from '../lib/hooks'
import { TRIP_STATUS_LABELS, formatCOP, formatDate, tripDays } from '../lib/format'
import { ItineraryAgenda, ReservationRow } from '../components/cards'
import ReservationActions from '../components/ReservationActions'
import ReservationForm from '../components/ReservationForm'
import { Alert, Badge, Empty, Loading, errorText, useToast } from '../components/Common'

function BudgetCard({ budget }) {
  const total = Math.max(budget.budgetCOP, budget.reservedCOP + budget.plannedActivitiesCOP, 1)
  return (
    <section className="card stack" aria-label="Presupuesto del viaje">
      <div className="row between"><h2>Presupuesto</h2><span className="kpi num" style={{ fontSize: 22 }}>{formatCOP(budget.budgetCOP)}</span></div>
      <div className="progress" role="img" aria-label="Distribución del presupuesto">
        <span className="p1" style={{ width: `${(budget.reservedCOP / total) * 100}%` }} />
        <span className="p2" style={{ width: `${(budget.plannedActivitiesCOP / total) * 100}%` }} />
      </div>
      <div className="grid cols-3">
        <div><div className="small muted">Reservado</div><strong className="num">{formatCOP(budget.reservedCOP)}</strong></div>
        <div><div className="small muted">Actividades planeadas</div><strong className="num">{formatCOP(budget.plannedActivitiesCOP)}</strong></div>
        <div><div className="small muted">Disponible</div><strong className="num" style={{ color: budget.remainingCOP < 0 ? 'var(--error)' : undefined }}>{formatCOP(budget.remainingCOP)}</strong></div>
      </div>
      {Object.keys(budget.reservedByKind || {}).length > 0 && (
        <div className="small muted">
          {Object.entries(budget.reservedByKind).map(([k, v]) => `${{ FLIGHT: 'Vuelos', HOTEL: 'Hoteles', ACTIVITY: 'Actividades' }[k]}: ${formatCOP(v)}`).join(' · ')}
        </div>
      )}
      {budget.overBudget && <Alert kind="warn"><TriangleAlert size={14} style={{ verticalAlign: -2 }} /> Superas el presupuesto en {formatCOP(-budget.remainingCOP)}.</Alert>}
    </section>
  )
}

function ItineraryEditor({ trip, itinerary, onClose }) {
  const toast = useToast()
  const existing = Object.fromEntries((itinerary?.days || []).map((d) => [d.date, d.items]))
  const [days, setDays] = useState(() => tripDays(trip.startDate, trip.endDate).map((date) => ({ date, items: (existing[date] || []).map((i) => ({ ...i })) })))
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const patch = (di, ii, k, v) => setDays(days.map((d, a) => (a !== di ? d : { ...d, items: d.items.map((it, b) => (b === ii ? { ...it, [k]: v } : it)) })))
  const add = (di) => setDays(days.map((d, a) => (a === di ? { ...d, items: [...d.items, { time: '', title: '', place: '', costCOP: 0, notes: '' }] } : d)))
  const remove = (di, ii) => setDays(days.map((d, a) => (a === di ? { ...d, items: d.items.filter((_, b) => b !== ii) } : d)))

  async function save() {
    setBusy(true)
    setError('')
    try {
      const clean = days.map((d) => ({ ...d, items: d.items.filter((i) => i.title.trim()).map((i) => ({ ...i, costCOP: Number(i.costCOP) || 0 })) }))
      await api.saveItinerary(trip.id, clean, Boolean(itinerary))
      toast('Itinerario guardado')
      onClose()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      {days.map((day, di) => (
        <section key={day.date} className="agenda-day">
          <h4>{formatDate(day.date, { weekday: 'long', day: 'numeric', month: 'long' })}</h4>
          {day.items.map((it, ii) => (
            <div key={ii} className="form-grid" style={{ gridTemplateColumns: '90px 1fr 110px auto', alignItems: 'end', margin: '8px 0' }}>
              <input aria-label="Hora" type="time" value={it.time} onChange={(e) => patch(di, ii, 'time', e.target.value)} />
              <input aria-label="Actividad" placeholder="Actividad" value={it.title} onChange={(e) => patch(di, ii, 'title', e.target.value)} />
              <input aria-label="Costo en COP" type="number" min="0" step="1000" value={it.costCOP} onChange={(e) => patch(di, ii, 'costCOP', e.target.value)} />
              <button className="icon-btn" aria-label="Quitar actividad" onClick={() => remove(di, ii)}><Trash2 size={16} /></button>
              <input aria-label="Lugar" placeholder="Lugar (opcional)" value={it.place} onChange={(e) => patch(di, ii, 'place', e.target.value)} style={{ gridColumn: '2 / 4' }} />
            </div>
          ))}
          <button className="btn btn-sm" onClick={() => add(di)}><Plus size={14} /> Agregar actividad</button>
        </section>
      ))}
      {error && <Alert>{error}</Alert>}
      <div className="row wrap">
        <button className="btn btn-primary" onClick={save} disabled={busy}><Save size={16} /> {busy ? 'Guardando…' : 'Guardar itinerario'}</button>
        <button className="btn" onClick={onClose}>Cancelar</button>
      </div>
    </div>
  )
}

export default function TripDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const { data, error, loading } = useLoad(() => api.getTrip(id), [id])
  const { data: all } = useLoad(() => api.listTrips())
  const [editing, setEditing] = useState(false)
  const [adding, setAdding] = useState(false)

  if (loading) return <Loading />
  if (error || !data) return <Alert>{error || 'No se encontró el viaje.'}</Alert>
  const { trip, itinerary, reservations, budget } = data
  const trips = all?.trips || []
  const askItinerary = `Genera y guarda un itinerario para mi viaje a ${trip.destination} (id ${trip.id}) del ${trip.startDate} al ${trip.endDate} para ${trip.travelers} personas con presupuesto de ${trip.budgetCOP} COP. Consulta el clima y adapta las actividades.`

  return (
    <div className="stack">
      <div className="page-head">
        <div><h1>{trip.name}</h1><p className="sub">{trip.origin} → {trip.destination} · {formatDate(trip.startDate)} – {formatDate(trip.endDate)}</p></div>
        <div className="row wrap">
          <Link className="btn" to={`/trips/${trip.id}/edit`}><Pencil size={16} /> Editar</Link>
          <button className="btn" onClick={() => navigate('/trips')}>Volver</button>
        </div>
      </div>

      <div className="row wrap">
        <Badge kind="ok">{TRIP_STATUS_LABELS[trip.status] || trip.status}</Badge>
        <Badge kind="neutral" icon={Users}>{trip.travelers} viajero{trip.travelers > 1 ? 's' : ''}</Badge>
        {trip.notes && <span className="small muted">{trip.notes}</span>}
      </div>
      <BudgetCard budget={budget} />

      <div className="section-title">
        <h2>Itinerario</h2>
        <div className="row wrap">
          <Link className="btn btn-sm" to={`/chat?prompt=${encodeURIComponent(askItinerary)}`}><Bot size={14} /> Generar con el asistente</Link>
          {!editing && <button className="btn btn-sm" onClick={() => setEditing(true)}><CalendarPlus size={14} /> {itinerary ? 'Editar' : 'Crear manualmente'}</button>}
        </div>
      </div>
      {editing ? (
        <ItineraryEditor trip={trip} itinerary={itinerary} onClose={() => setEditing(false)} />
      ) : itinerary ? (
        <ItineraryAgenda days={itinerary.days} />
      ) : (
        <Empty icon={CalendarPlus} title="Sin itinerario todavía">Créalo a mano o pídele al asistente que lo genere según el clima y tu presupuesto.</Empty>
      )}

      <div className="section-title">
        <h2>Reservas</h2>
        <button className="btn btn-sm" onClick={() => setAdding(true)}><Plus size={14} /> Agregar reserva</button>
      </div>
      {reservations.length === 0 ? (
        <Empty title="No hay reservas en este viaje">Reserva vuelos u hoteles desde las pantallas de búsqueda o con el asistente.</Empty>
      ) : (
        <div className="stack">
          {reservations.map((r) => <ReservationRow key={r.id} reservation={r} actions={<ReservationActions reservation={r} trips={trips} />} />)}
        </div>
      )}
      {adding && <ReservationForm trips={trips} tripId={trip.id} onClose={() => setAdding(false)} />}
    </div>
  )
}
