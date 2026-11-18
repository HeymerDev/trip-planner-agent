import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bot, Luggage, Pencil, Plus, Trash2 } from 'lucide-react'
import { api } from '../lib/api'
import { useLoad, todayISO } from '../lib/hooks'
import { TripCard } from '../components/cards'
import { Alert, Empty, Loading, Modal, errorText, useToast } from '../components/Common'

const phase = (t, today) => (t.endDate < today ? 'past' : t.startDate <= today ? 'now' : 'next')

export default function Trips() {
  const { data, error, loading } = useLoad(() => api.listTrips())
  const [tab, setTab] = useState('all')
  const [toDelete, setToDelete] = useState(null)
  const toast = useToast()
  const navigate = useNavigate()
  const today = todayISO()

  const trips = data?.trips || []
  const counts = { next: 0, now: 0, past: 0 }
  trips.forEach((t) => counts[phase(t, today)]++)
  const shown = tab === 'all' ? trips : trips.filter((t) => phase(t, today) === tab)

  const remove = async () => {
    try {
      await api.deleteTrip(toDelete.id)
      toast('Viaje eliminado')
    } catch (e) {
      toast(errorText(e), 'error')
    }
    setToDelete(null)
  }

  const TABS = [['all', 'Todos'], ['next', `Próximos (${counts.next})`], ['now', `En curso (${counts.now})`], ['past', `Pasados (${counts.past})`]]
  return (
    <div className="stack">
      <div className="page-head">
        <div>
          <h1>Mis viajes</h1>
          <p className="sub">{counts.next} próximos · {counts.past} pasados</p>
        </div>
        <div className="row wrap">
          <Link className="btn" to="/chat?prompt=Quiero planear un viaje nuevo"><Bot size={16} /> Pedir al asistente</Link>
          <Link className="btn btn-primary" to="/trips/new"><Plus size={16} /> Crear viaje</Link>
        </div>
      </div>
      <div className="chips" role="tablist" aria-label="Filtrar viajes">
        {TABS.map(([key, label]) => (
          <button key={key} role="tab" aria-selected={tab === key} className={`chip ${tab === key ? 'active' : ''}`} onClick={() => setTab(key)}>{label}</button>
        ))}
      </div>
      {error && <Alert>{error}</Alert>}
      {loading ? <Loading /> : shown.length === 0 ? (
        <Empty icon={Luggage} title="Aún no hay viajes aquí">Crea uno con el formulario o pídeselo al asistente.</Empty>
      ) : (
        <div className="grid cols-2">
          {shown.map((t) => (
            <TripCard key={t.id} trip={t} onOpen={() => navigate(`/trips/${t.id}`)}>
              <div className="row wrap">
                <Link className="btn btn-sm" to={`/trips/${t.id}/edit`}><Pencil size={14} /> Editar</Link>
                <button className="btn btn-sm btn-danger" onClick={() => setToDelete(t)}><Trash2 size={14} /> Eliminar</button>
              </div>
            </TripCard>
          ))}
        </div>
      )}
      {toDelete && (
        <Modal title="Eliminar viaje" onClose={() => setToDelete(null)}>
          <div className="stack">
            <p>¿Eliminar <strong>{toDelete.name}</strong> y su itinerario? Las reservas quedarán sin viaje asociado.</p>
            <div className="row wrap">
              <button className="btn btn-danger" onClick={remove}>Sí, eliminar</button>
              <button className="btn" onClick={() => setToDelete(null)}>Cancelar</button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}
