// Reserva simulada de un vuelo u hotel mostrado por los agentes: elige el viaje, convierte el precio a COP
// y paga con el monedero (compra atomica e idempotente) o solo registra la reserva. No hay datos de tarjeta.
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CheckCircle2, Wallet } from 'lucide-react'
import { api } from '../lib/api'
import { formatCOP, formatMoney, newKey, nights as nightsBetween } from '../lib/format'
import { Alert, Loading, Modal, errorText } from './Common'

export default function BookingModal({ request, onClose }) {
  const { kind, flight, hotel, data } = request
  const unit = kind === 'FLIGHT' ? flight.price : hotel.pricePerNight
  const currency = (kind === 'FLIGHT' ? flight.currency : hotel.currency) || data.currency || 'USD'

  const [trips, setTrips] = useState(null)
  const [wallet, setWallet] = useState(null)
  const [rate, setRate] = useState(currency === 'COP' ? 1 : null)
  const [tripId, setTripId] = useState('')
  const [qty, setQty] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [shortfall, setShortfall] = useState(0)
  const [done, setDone] = useState(null)
  const key = useRef(newKey('buy')) // misma clave en reintentos: nunca cobra dos veces

  useEffect(() => {
    Promise.all([api.listTrips(), api.wallet(), currency === 'COP' ? Promise.resolve(null) : api.fx(currency, 'COP', 1)])
      .then(([t, w, fx]) => {
        setTrips(t.trips)
        setWallet(w)
        if (fx) setRate(fx.rate)
        if (t.trips.length === 1) setTripId(t.trips[0].id)
      })
      .catch((e) => setError(errorText(e)))
  }, [currency])

  const trip = trips?.find((t) => t.id === tripId)

  // Cantidad: pasajeros (vuelo) o noches (hotel); se sugiere desde el viaje elegido.
  useEffect(() => {
    if (!trip) return
    if (kind === 'FLIGHT') setQty(trip.travelers)
    else setQty(data.checkin && data.checkout ? nightsBetween(data.checkin, data.checkout) : nightsBetween(trip.startDate, trip.endDate))
  }, [trip, kind, data.checkin, data.checkout])

  const totalCOP = useMemo(() => (rate && unit != null ? Math.round(unit * rate * qty) : null), [rate, unit, qty])
  const title = kind === 'FLIGHT' ? `${data.origin} → ${data.destination} · ${flight.airline || ''} ${flight.departure || ''}`.trim() : hotel.name

  const body = () => ({
    tripId,
    kind,
    title,
    priceCOP: totalCOP,
    originalPrice: Number((unit * qty).toFixed(2)),
    originalCurrency: currency,
    fxRate: rate,
    link: (kind === 'FLIGHT' ? flight.buyLink : hotel.bookingLinks?.[0]?.url) || undefined,
    details:
      kind === 'FLIGHT'
        ? { airline: flight.airline, departure: flight.departure, arrival: flight.arrival, duration: flight.duration, stops: flight.stops, departDate: data.departDate, returnDate: data.returnDate, passengers: qty }
        : { name: hotel.name, area: hotel.area, stars: hotel.stars, rating: hotel.rating, nights: qty, checkin: data.checkin, checkout: data.checkout, pricePerNight: hotel.pricePerNight },
  })

  async function submit(pay, topUpFirst = 0) {
    setBusy(true)
    setError('')
    setShortfall(0)
    try {
      if (topUpFirst) await api.topUp(topUpFirst)
      if (pay) {
        const res = await api.purchase({ ...body(), idempotencyKey: key.current })
        setDone({ paid: true, reservation: res.reservation, balance: res.balanceCOP })
      } else {
        const res = await api.createReservation(body())
        setDone({ paid: false, reservation: res })
      }
    } catch (e) {
      if (e.code === 'INSUFFICIENT_FUNDS') {
        const missing = totalCOP - (wallet?.balanceCOP || 0)
        setShortfall(Math.max(1000, Math.ceil(missing / 50000) * 50000))
      }
      if (e.code === 'DUPLICATE') setDone({ paid: true, duplicate: true })
      else setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <Modal title="Reserva simulada" onClose={onClose}>
        <div className="stack" style={{ alignItems: 'center', textAlign: 'center' }}>
          <CheckCircle2 size={52} color="var(--green)" />
          <h3>{done.duplicate ? 'Esta compra ya estaba registrada' : done.paid ? '¡Compra simulada realizada!' : 'Reserva registrada'}</h3>
          {done.balance != null && <p>Saldo del monedero: <strong>{formatCOP(done.balance)}</strong></p>}
          <p className="small muted">Es una simulación: no hubo ningún cobro real y no se guardaron datos de tarjeta.</p>
          <div className="row wrap" style={{ justifyContent: 'center' }}>
            <Link className="btn btn-primary" to="/reservations" onClick={onClose}>Ver mis reservas</Link>
            <button className="btn" onClick={onClose}>Seguir explorando</button>
          </div>
        </div>
      </Modal>
    )
  }

  const insufficient = wallet && totalCOP != null && wallet.balanceCOP < totalCOP
  return (
    <Modal title={kind === 'FLIGHT' ? 'Reservar vuelo' : 'Reservar hotel'} onClose={onClose}>
      {!trips || !wallet || (currency !== 'COP' && !rate) ? (
        error ? <Alert>{error}</Alert> : <Loading rows={2} />
      ) : trips.length === 0 ? (
        <div className="stack">
          <Alert kind="info">Para reservar primero necesitas un viaje al que asociarla.</Alert>
          <Link className="btn btn-primary" to="/trips/new" onClick={onClose}>Crear un viaje</Link>
        </div>
      ) : (
        <div className="stack">
          <div className="card soft">
            <strong>{title}</strong>
            <div className="small muted">{kind === 'FLIGHT' ? 'Vuelo' : `${hotel.area || ''}`}</div>
          </div>
          <div className="form-grid two">
            <div className="field">
              <label htmlFor="bk-trip">Asociar al viaje</label>
              <select id="bk-trip" value={tripId} onChange={(e) => setTripId(e.target.value)}>
                <option value="">Elige un viaje…</option>
                {trips.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="bk-qty">{kind === 'FLIGHT' ? 'Pasajeros' : 'Noches'}</label>
              <input id="bk-qty" type="number" min="1" max="30" value={qty} onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))} />
            </div>
          </div>
          <div className="card flat">
            <div className="row between"><span className="muted">Precio {kind === 'FLIGHT' ? 'por pasajero' : 'por noche'}</span><span className="num">{formatMoney(unit, currency)}</span></div>
            {currency !== 'COP' && <div className="row between small muted"><span>Tasa de cambio</span><span className="num">1 {currency} = {Number(rate).toLocaleString('es-CO')} COP</span></div>}
            <div className="row between" style={{ marginTop: 8 }}><strong>Total</strong><span className="price num">{totalCOP != null ? formatCOP(totalCOP) : '—'}</span></div>
            <div className="row between small"><span className="muted"><Wallet size={13} style={{ verticalAlign: -2 }} /> Saldo del monedero</span><span className="num">{formatCOP(wallet.balanceCOP)}</span></div>
          </div>
          {insufficient && !shortfall && <Alert kind="warn">Tu saldo no alcanza para esta compra. Puedes recargar el monedero (simulado).</Alert>}
          {error && <Alert>{error}</Alert>}
          {shortfall > 0 && (
            <button className="btn btn-primary" disabled={busy || !tripId} onClick={() => submit(true, shortfall)}>
              Recargar {formatCOP(shortfall)} y comprar
            </button>
          )}
          <button className="btn btn-primary btn-block" disabled={busy || !tripId || totalCOP == null} onClick={() => submit(true)}>
            {busy ? 'Procesando…' : `Comprar con el monedero · ${totalCOP != null ? formatCOP(totalCOP) : ''}`}
          </button>
          <button className="btn btn-block" disabled={busy || !tripId || totalCOP == null} onClick={() => submit(false)}>
            Solo registrar la reserva (sin pagar)
          </button>
          <p className="small muted">Simulación: la reserva queda como <strong>Simulada</strong>. No se solicitan ni guardan datos de tarjeta.</p>
        </div>
      )}
    </Modal>
  )
}
