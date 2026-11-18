// Pantallas de Vuelos, Clima y Hoteles: formulario -> Orchestrator (A2A + MCP) -> tarjetas.
import { useState } from 'react'
import { ArrowLeftRight, BedDouble, Bus, CloudSun, Search as SearchIcon } from 'lucide-react'
import { api } from '../lib/api'
import { useAgentSearch, todayISO } from '../lib/hooks'
import SearchResult from '../components/SearchResult'
import BookingModal from '../components/BookingModal'
import { TransportBlock } from '../components/cards'
import { Alert, errorText } from '../components/Common'

const ONLY = 'Responde solo con esa consulta; no crees viajes, itinerarios ni reservas.'

export function Flights() {
  const search = useAgentSearch()
  const [f, setF] = useState({ origin: 'Bogotá', destination: 'Cartagena', depart: '', ret: '', pax: 1 })
  const [booking, setBooking] = useState(null)
  const [transport, setTransport] = useState(null)
  const [tErr, setTErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const valid = f.origin && f.destination && f.depart && (!f.ret || f.ret >= f.depart)

  const submit = (e) => {
    e.preventDefault()
    search.run(
      `Busca vuelos ${f.ret ? 'de ida y vuelta' : 'solo de ida'} de ${f.origin} a ${f.destination}, saliendo el ${f.depart}` +
        `${f.ret ? ` y regresando el ${f.ret}` : ''}, para ${f.pax} pasajero(s). Usa únicamente el agente de vuelos. ${ONLY}`,
    )
  }
  const compare = async () => {
    setTErr('')
    try {
      setTransport(await api.transport(f.origin, f.destination))
    } catch (e) {
      setTErr(errorText(e))
    }
  }

  return (
    <div className="stack">
      <div className="page-head"><div><h1>Vuelos</h1><p className="sub">Compara opciones reales con tarjetas y reserva de forma simulada.</p></div></div>
      <form className="card stack" onSubmit={submit}>
        <div className="form-grid two">
          <div className="field"><label htmlFor="fo">Origen</label><input id="fo" value={f.origin} onChange={set('origin')} required /></div>
          <div className="field"><label htmlFor="fd">Destino</label><input id="fd" value={f.destination} onChange={set('destination')} required /></div>
          <div className="field"><label htmlFor="fs">Fecha de salida</label><input id="fs" type="date" min={todayISO()} value={f.depart} onChange={set('depart')} required /></div>
          <div className="field"><label htmlFor="fr">Regreso (opcional)</label><input id="fr" type="date" min={f.depart || todayISO()} value={f.ret} onChange={set('ret')} /></div>
          <div className="field"><label htmlFor="fp">Pasajeros</label><input id="fp" type="number" min="1" max="9" value={f.pax} onChange={set('pax')} /></div>
        </div>
        <div className="row wrap">
          <button className="btn btn-primary" disabled={!valid || search.loading}><SearchIcon size={16} /> {search.loading ? 'Buscando…' : 'Buscar vuelos'}</button>
          <button type="button" className="btn" onClick={compare} disabled={!f.origin || !f.destination}><Bus size={16} /> ¿Bus o avión?</button>
          <button type="button" className="icon-btn" aria-label="Invertir origen y destino" onClick={() => setF({ ...f, origin: f.destination, destination: f.origin })}><ArrowLeftRight size={16} /></button>
        </div>
      </form>
      {tErr && <Alert>{tErr}</Alert>}
      {transport && <TransportBlock data={transport} />}
      {(search.loading || search.done) && <SearchResult search={search} only={['flights']} onBook={setBooking} empty="No encontré vuelos para esa búsqueda." />}
      {booking && <BookingModal request={booking} onClose={() => setBooking(null)} />}
    </div>
  )
}

export function Weather() {
  const search = useAgentSearch()
  const [f, setF] = useState({ city: 'Cartagena', start: '', end: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const valid = f.city && f.start && (!f.end || f.end >= f.start)
  const submit = (e) => {
    e.preventDefault()
    search.run(
      `Dame el clima en ${f.city} ${f.end && f.end !== f.start ? `del ${f.start} al ${f.end}` : `el ${f.start}`}. ` +
        `Usa únicamente el agente de clima. ${ONLY}`,
    )
  }
  return (
    <div className="stack">
      <div className="page-head"><div><h1>Clima</h1><p className="sub">Pronóstico por día hasta 16 días hacia adelante.</p></div></div>
      <form className="card stack" onSubmit={submit}>
        <div className="form-grid two">
          <div className="field"><label htmlFor="wc">Ciudad</label><input id="wc" value={f.city} onChange={set('city')} required /></div>
          <div />
          <div className="field"><label htmlFor="ws">Desde</label><input id="ws" type="date" min={todayISO()} value={f.start} onChange={set('start')} required /></div>
          <div className="field"><label htmlFor="we">Hasta (opcional, máx. 4 días)</label><input id="we" type="date" min={f.start || todayISO()} value={f.end} onChange={set('end')} /></div>
        </div>
        <div><button className="btn btn-primary" disabled={!valid || search.loading}><CloudSun size={16} /> {search.loading ? 'Consultando…' : 'Consultar clima'}</button></div>
      </form>
      {(search.loading || search.done) && <SearchResult search={search} only={['weather']} empty="No hay pronóstico disponible para esas fechas." />}
    </div>
  )
}

export function Hotels() {
  const search = useAgentSearch()
  const [f, setF] = useState({ city: 'Cartagena', checkin: '', checkout: '', guests: 2 })
  const [booking, setBooking] = useState(null)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const valid = f.city && f.checkin && f.checkout && f.checkout > f.checkin
  const submit = (e) => {
    e.preventDefault()
    search.run(
      `Busca hoteles en ${f.city} del ${f.checkin} al ${f.checkout} para ${f.guests} personas. Usa únicamente el agente de hospedaje. ${ONLY}`,
    )
  }
  return (
    <div className="stack">
      <div className="page-head"><div><h1>Hoteles</h1><p className="sub">Alojamientos reales con enlace de reserva.</p></div></div>
      <form className="card stack" onSubmit={submit}>
        <div className="form-grid two">
          <div className="field"><label htmlFor="hc">Ciudad</label><input id="hc" value={f.city} onChange={set('city')} required /></div>
          <div className="field"><label htmlFor="hg">Personas</label><input id="hg" type="number" min="1" max="12" value={f.guests} onChange={set('guests')} /></div>
          <div className="field"><label htmlFor="hi">Entrada</label><input id="hi" type="date" min={todayISO()} value={f.checkin} onChange={set('checkin')} required /></div>
          <div className="field"><label htmlFor="ho">Salida</label><input id="ho" type="date" min={f.checkin || todayISO()} value={f.checkout} onChange={set('checkout')} required /></div>
        </div>
        <div><button className="btn btn-primary" disabled={!valid || search.loading}><BedDouble size={16} /> {search.loading ? 'Buscando…' : 'Buscar hoteles'}</button></div>
      </form>
      {(search.loading || search.done) && <SearchResult search={search} only={['hotels']} onBook={setBooking} empty="No encontré hoteles para esa búsqueda." />}
      {booking && <BookingModal request={booking} onClose={() => setBooking(null)} />}
    </div>
  )
}
