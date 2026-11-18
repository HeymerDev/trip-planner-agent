import { useState } from 'react'
import { Ban, Clock, FileCheck2, Move } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP } from '../lib/format'
import { Modal, errorText, useToast } from './Common'

/** Acciones sobre una reserva: pendiente/simulada, reasociar a otro viaje, cancelar (con reembolso). */
export default function ReservationActions({ reservation: r, trips = [] }) {
  const toast = useToast()
  const [moving, setMoving] = useState(false)
  const [target, setTarget] = useState(r.tripId || '')
  const [confirmCancel, setConfirmCancel] = useState(false)
  const [busy, setBusy] = useState(false)

  const run = async (body, message) => {
    setBusy(true)
    try {
      await api.updateReservation(r.id, body)
      toast(message)
    } catch (e) {
      toast(errorText(e), 'error')
    } finally {
      setBusy(false)
      setMoving(false)
      setConfirmCancel(false)
    }
  }

  if (r.status === 'CANCELADA' || r.status === 'CONFIRMADA') return null
  return (
    <>
      <div className="res-actions">
        {r.status === 'SIMULADA' ? (
          <button className="btn btn-sm" disabled={busy} onClick={() => run({ status: 'PENDIENTE' }, 'Reserva marcada como pendiente')}><Clock size={14} /> Marcar pendiente</button>
        ) : (
          <button className="btn btn-sm" disabled={busy} onClick={() => run({ status: 'SIMULADA' }, 'Reserva marcada como simulada')}><FileCheck2 size={14} /> Marcar simulada</button>
        )}
        <button className="btn btn-sm" disabled={busy} onClick={() => setMoving(true)}><Move size={14} /> Cambiar de viaje</button>
        <button className="btn btn-sm btn-danger" disabled={busy} onClick={() => setConfirmCancel(true)}><Ban size={14} /> Cancelar</button>
      </div>

      {moving && (
        <Modal title="Asociar a otro viaje" onClose={() => setMoving(false)}>
          <div className="stack">
            <div className="field">
              <label htmlFor="mv">Viaje</label>
              <select id="mv" value={target} onChange={(e) => setTarget(e.target.value)}>
                <option value="">Elige un viaje…</option>
                {trips.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <button className="btn btn-primary" disabled={!target || target === r.tripId || busy} onClick={() => run({ tripId: target }, 'Reserva asociada al viaje')}>Guardar</button>
          </div>
        </Modal>
      )}
      {confirmCancel && (
        <Modal title="Cancelar reserva" onClose={() => setConfirmCancel(false)}>
          <div className="stack">
            <p>¿Cancelar <strong>{r.title}</strong>?{r.paid ? ` Se reembolsarán ${formatCOP(r.priceCOP)} a tu monedero.` : ''}</p>
            <div className="row wrap">
              <button className="btn btn-danger" disabled={busy} onClick={() => run({ status: 'CANCELADA' }, r.paid ? 'Reserva cancelada y reembolsada' : 'Reserva cancelada')}>Sí, cancelar</button>
              <button className="btn" onClick={() => setConfirmCancel(false)}>Volver</button>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}
