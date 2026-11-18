import { useState } from 'react'
import { api } from '../lib/api'
import { KIND_LABELS } from '../lib/format'
import { Alert, Modal, useToast } from './Common'

/** Registro manual de una reserva (vuelo, hotel o actividad) asociada a un viaje. Sin cobro. */
export default function ReservationForm({ trips, tripId, onClose }) {
  const toast = useToast()
  const [f, setF] = useState({ tripId: tripId || '', kind: 'ACTIVITY', title: '', priceCOP: '', status: 'SIMULADA', link: '' })
  const [error, setError] = useState('')
  const [fields, setFields] = useState({})
  const [busy, setBusy] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const fe = (k) => fields[k] && <span className="field-error">{fields[k]}</span>

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    setFields({})
    try {
      await api.createReservation({ ...f, priceCOP: Number(f.priceCOP), link: f.link || undefined })
      toast('Reserva registrada (simulada)')
      onClose()
    } catch (err) {
      setError(err.message)
      setFields(err.fields || {})
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Nueva reserva" onClose={onClose}>
      <form className="stack" onSubmit={submit} noValidate>
        {!tripId && (
          <div className="field">
            <label htmlFor="rf-trip">Viaje</label>
            <select id="rf-trip" value={f.tripId} onChange={set('tripId')} required>
              <option value="">Elige un viaje…</option>
              {trips.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            {fe('tripId')}
          </div>
        )}
        <div className="form-grid two">
          <div className="field">
            <label htmlFor="rf-kind">Tipo</label>
            <select id="rf-kind" value={f.kind} onChange={set('kind')}>
              {Object.entries(KIND_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field">
            <label htmlFor="rf-status">Estado</label>
            <select id="rf-status" value={f.status} onChange={set('status')}>
              <option value="SIMULADA">Simulada</option>
              <option value="PENDIENTE">Pendiente</option>
            </select>
          </div>
        </div>
        <div className="field"><label htmlFor="rf-title">Título</label><input id="rf-title" value={f.title} onChange={set('title')} placeholder="Tour Islas del Rosario" required />{fe('title')}</div>
        <div className="field"><label htmlFor="rf-price">Precio (COP)</label><input id="rf-price" type="number" min="0" step="1000" value={f.priceCOP} onChange={set('priceCOP')} required />{fe('priceCOP')}</div>
        <div className="field"><label htmlFor="rf-link">Enlace (opcional)</label><input id="rf-link" type="url" value={f.link} onChange={set('link')} placeholder="https://…" />{fe('link')}</div>
        <p className="small muted">Registra la reserva sin cobrar. Para pagar con el monedero usa el botón “Reservar” en Vuelos, Hoteles o el asistente.</p>
        {error && <Alert>{error}</Alert>}
        <button className="btn btn-primary" disabled={busy || !f.tripId}>{busy ? 'Guardando…' : 'Guardar reserva'}</button>
      </form>
    </Modal>
  )
}
