// Crear / editar viaje de forma manual (el asistente puede hacer lo mismo por chat).
import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Compass, Save, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { todayISO } from '../lib/hooks'
import { TRIP_STATUS_LABELS } from '../lib/format'
import { Alert, Loading, errorText, useToast } from '../components/Common'

const EMPTY = { name: '', origin: '', destination: '', startDate: '', endDate: '', travelers: 1, budgetCOP: '', notes: '', status: 'PLANEADO' }

export default function TripForm() {
  const { id } = useParams()
  const editing = Boolean(id)
  const navigate = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState(EMPTY)
  const [loading, setLoading] = useState(editing)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [fields, setFields] = useState({})

  useEffect(() => {
    if (!editing) return
    api.getTrip(id)
      .then(({ trip }) => setForm({ ...EMPTY, ...trip }))
      .catch((e) => setError(errorText(e)))
      .finally(() => setLoading(false))
  }, [id, editing])

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const fieldError = (k) => fields[k] && <span className="field-error">{fields[k]}</span>

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    setFields({})
    const body = {
      name: form.name || undefined,
      origin: form.origin,
      destination: form.destination,
      startDate: form.startDate,
      endDate: form.endDate,
      travelers: Number(form.travelers),
      budgetCOP: Number(form.budgetCOP),
      notes: form.notes || undefined,
      ...(editing ? { status: form.status } : {}),
    }
    try {
      const trip = editing ? await api.updateTrip(id, body) : await api.createTrip(body)
      toast(editing ? 'Viaje actualizado' : 'Viaje creado')
      navigate(`/trips/${trip.id}`)
    } catch (err) {
      setError(err.message)
      setFields(err.fields || {})
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <Loading />
  return (
    <form className="stack" onSubmit={submit} noValidate>
      <div className="page-head">
        <div>
          <span className="badge"><Compass size={13} /> Modo manual</span>
          <h1 style={{ marginTop: 8 }}>{editing ? 'Editar viaje' : 'Nuevo viaje'}</h1>
          <p className="sub">Ingresa los datos de tu viaje. Después podrás agregar itinerario y reservas.</p>
        </div>
      </div>

      <section className="card stack">
        <h2>Destino y fechas</h2>
        <div className="field"><label htmlFor="name">Nombre del viaje (opcional)</label><input id="name" value={form.name} onChange={set('name')} placeholder="Vacaciones en Cartagena" maxLength={120} />{fieldError('name')}</div>
        <div className="form-grid two">
          <div className="field"><label htmlFor="origin">Origen</label><input id="origin" value={form.origin} onChange={set('origin')} placeholder="Bogotá" required />{fieldError('origin')}</div>
          <div className="field"><label htmlFor="destination">Destino</label><input id="destination" value={form.destination} onChange={set('destination')} placeholder="Cartagena" required />{fieldError('destination')}</div>
          <div className="field"><label htmlFor="start">Salida</label><input id="start" type="date" min={editing ? undefined : todayISO()} value={form.startDate} onChange={set('startDate')} required />{fieldError('startDate')}</div>
          <div className="field"><label htmlFor="end">Regreso</label><input id="end" type="date" min={form.startDate || todayISO()} value={form.endDate} onChange={set('endDate')} required />{fieldError('endDate')}</div>
        </div>
      </section>

      <section className="card stack">
        <h2><Wallet size={18} style={{ verticalAlign: -3 }} /> Viajeros y presupuesto</h2>
        <div className="form-grid two">
          <div className="field"><label htmlFor="travelers">Viajeros</label><input id="travelers" type="number" min="1" max="20" value={form.travelers} onChange={set('travelers')} required />{fieldError('travelers')}</div>
          <div className="field"><label htmlFor="budget">Presupuesto total (COP)</label><input id="budget" type="number" min="0" step="50000" value={form.budgetCOP} onChange={set('budgetCOP')} placeholder="5000000" required />{fieldError('budgetCOP')}</div>
        </div>
        {editing && (
          <div className="field">
            <label htmlFor="status">Estado del viaje</label>
            <select id="status" value={form.status} onChange={set('status')}>
              {Object.entries(TRIP_STATUS_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
        )}
      </section>

      <section className="card stack">
        <h2>Notas</h2>
        <div className="field"><label htmlFor="notes" className="sr-only">Notas</label><textarea id="notes" value={form.notes} onChange={set('notes')} placeholder="Recordatorios, documentos, preferencias…" maxLength={1000} />{fieldError('notes')}</div>
      </section>

      {error && <Alert>{error}</Alert>}
      <div className="row wrap">
        <button className="btn btn-primary" disabled={saving}><Save size={16} /> {saving ? 'Guardando…' : 'Guardar viaje'}</button>
        <button type="button" className="btn" onClick={() => navigate(-1)}>Cancelar</button>
      </div>
    </form>
  )
}
