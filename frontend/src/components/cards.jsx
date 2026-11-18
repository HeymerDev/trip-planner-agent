// Componentes visuales dirigidos por los agentes (Agent-Driven UI): el agente devuelve datos
// estructurados y estos componentes los pintan (vuelos, clima, hoteles, viajes, itinerario, reservas).
import {
  ArrowRight, BedDouble, Bus, CalendarDays, Cloud, CloudFog, CloudLightning, CloudRain, CloudSun,
  ExternalLink, Landmark, Plane, Snowflake, Sparkles, Sun, Users, Wallet,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge, StatusBadge } from './Common'
import {
  KIND_LABELS, TRIP_STATUS_LABELS, destinationGradient, durationMinutes, formatCOP, formatDate, formatDayLong,
  formatMoney, safeUrl,
} from '../lib/format'

// -------------------------------------------------------------------------------- Vuelos

export function FlightCards({ data, onBook }) {
  const flights = Array.isArray(data?.flights) ? data.flights : []
  if (!flights.length) return null
  const priced = flights.filter((f) => typeof f.price === 'number')
  const cheapest = priced.length ? Math.min(...priced.map((f) => f.price)) : null
  const fastest = Math.min(...flights.map((f) => durationMinutes(f.duration)))

  return (
    <div className="stack">
      <div className="row between">
        <h3>
          <Plane size={16} style={{ verticalAlign: -2 }} /> {data.origin} <ArrowRight size={14} style={{ verticalAlign: -2 }} /> {data.destination}
        </h3>
        <span className="small muted">
          {formatDate(data.departDate)}
          {data.returnDate ? ` · regreso ${formatDate(data.returnDate)}` : ''}
        </span>
      </div>
      <div className="grid cols-2">
        {flights.map((f, i) => {
          const isCheapest = cheapest !== null && f.price === cheapest && priced.length > 1
          const isFastest = durationMinutes(f.duration) === fastest && flights.length > 1 && Number.isFinite(fastest)
          const link = safeUrl(f.buyLink)
          return (
            <article key={i} className={`card flight-card ${isCheapest ? 'best' : ''}`}>
              {(isCheapest || isFastest) && (
                <div className="ribbon row" style={{ gap: 6 }}>
                  {isCheapest && <Badge kind="ok" icon={Sparkles}>Más barato</Badge>}
                  {isFastest && <Badge icon={Sparkles}>Más rápido</Badge>}
                </div>
              )}
              <div className="flight-top">
                <div className="row">
                  <div className="airline-logo"><Plane size={20} /></div>
                  <div>
                    <h3>{f.airline || 'Aerolínea'}</h3>
                    <span className="small muted">
                      {f.stops === 0 ? 'Directo' : f.stops == null ? 'Escalas: ver detalle' : `${f.stops} escala${f.stops > 1 ? 's' : ''}`}
                    </span>
                  </div>
                </div>
                <div className="right">
                  <div className="price num">{f.price != null ? formatMoney(f.price, f.currency || data.currency || 'USD') : '—'}</div>
                  {f.priceLevel && (
                    <Badge kind={f.priceLevel === 'low' ? 'ok' : f.priceLevel === 'high' ? 'warn' : 'neutral'}>
                      {{ low: 'Precio bajo', typical: 'Precio típico', high: 'Precio alto' }[f.priceLevel] || f.priceLevel}
                    </Badge>
                  )}
                </div>
              </div>
              <div className="flight-times">
                <span className="t">{f.departure || '—'}</span>
                <div className="flight-line"><span>{f.duration || ''}</span></div>
                <span className="t">{f.arrival || '—'}</span>
              </div>
              <div className="row wrap">
                {onBook && (
                  <button className="btn btn-primary btn-sm" onClick={() => onBook({ kind: 'FLIGHT', flight: f, data })}>
                    <Wallet size={15} /> Reservar (simulado)
                  </button>
                )}
                {link && (
                  <a className="btn btn-sm" href={link} target="_blank" rel="noopener noreferrer">
                    Ver en Google Flights <ExternalLink size={14} />
                  </a>
                )}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------------- Clima

const WEATHER_ICONS = { sun: Sun, partly: CloudSun, cloud: Cloud, rain: CloudRain, storm: CloudLightning, fog: CloudFog, snow: Snowflake }

export function WeatherCards({ data }) {
  const days = Array.isArray(data?.days) ? data.days : []
  if (!days.length) return null
  return (
    <div className="stack">
      <h3>Clima en {data.city}</h3>
      <div className="grid cols-3">
        {days.map((d, i) => {
          const Icon = WEATHER_ICONS[d.icon] || CloudSun
          return (
            <article key={i} className="card wcard">
              <span className="small muted cap">{formatDayLong(d.date)}</span>
              <Icon size={40} className="ico" aria-hidden="true" />
              <div className="temp num">
                {d.maxC != null ? `${Math.round(d.maxC)}°` : '—'}
                <span className="muted small"> / {d.minC != null ? `${Math.round(d.minC)}°` : '—'}</span>
              </div>
              <span className="small">{d.condition || ''}</span>
              <div className="row wrap" style={{ justifyContent: 'center' }}>
                {d.rainProbability != null && (
                  <Badge kind={d.rainProbability >= 50 ? 'warn' : 'neutral'} icon={CloudRain}>{Math.round(d.rainProbability)}% lluvia</Badge>
                )}
                {d.humidity != null && <Badge kind="neutral">{Math.round(d.humidity)}% humedad</Badge>}
              </div>
            </article>
          )
        })}
      </div>
    </div>
  )
}

// -------------------------------------------------------------------------------- Hoteles

export function HotelCards({ data, onBook }) {
  const hotels = Array.isArray(data?.hotels) ? data.hotels : []
  if (!hotels.length) return null
  return (
    <div className="stack">
      <h3><BedDouble size={16} style={{ verticalAlign: -2 }} /> Hoteles en {data.city}</h3>
      <div className="grid cols-2">
        {hotels.map((h, i) => (
          <article key={i} className="card hotel-card">
            <div className="row between" style={{ alignItems: 'flex-start' }}>
              <div>
                <h3>{h.name}</h3>
                <span className="small muted">{h.area}</span>
                {h.stars ? <div className="stars" aria-label={`${h.stars} estrellas`}>{'★'.repeat(Math.round(h.stars))}</div> : null}
              </div>
              <div className="right">
                <div className="price num">{h.pricePerNight != null ? formatMoney(h.pricePerNight, h.currency || 'USD') : '—'}</div>
                <span className="small muted">por noche</span>
                {h.rating != null && <div><Badge kind="ok">{h.rating} ★</Badge></div>}
              </div>
            </div>
            {Array.isArray(h.highlights) && h.highlights.length > 0 && (
              <div className="chips">{h.highlights.slice(0, 4).map((t, k) => <Badge key={k} kind="neutral">{t}</Badge>)}</div>
            )}
            <div className="row wrap">
              {onBook && (
                <button className="btn btn-primary btn-sm" onClick={() => onBook({ kind: 'HOTEL', hotel: h, data })}>
                  <Wallet size={15} /> Reservar (simulado)
                </button>
              )}
              {(h.bookingLinks || []).map((l, k) => {
                const url = safeUrl(l.url)
                return url ? (
                  <a key={k} className="btn btn-sm" href={url} target="_blank" rel="noopener noreferrer">
                    {l.label || 'Reservar'} <ExternalLink size={14} />
                  </a>
                ) : null
              })}
            </div>
            <span className="small muted">Precios observados anteriormente, no en vivo.</span>
          </article>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------------- Viajes

export function TripCard({ trip, budget, onOpen, children }) {
  const days = Math.round((new Date(trip.endDate) - new Date(trip.startDate)) / 86400000) + 1
  return (
    <article className="card trip-card">
      <div className="trip-hero" style={{ background: destinationGradient(trip.destination) }}>
        <Badge kind="ok" icon={Sparkles}>{TRIP_STATUS_LABELS[trip.status] || trip.status}</Badge>
        <span className="overline">{trip.origin} → {trip.destination}</span>
        <h3>{trip.name}</h3>
        <span className="small"><CalendarDays size={13} style={{ verticalAlign: -2 }} /> {formatDate(trip.startDate, { day: 'numeric', month: 'short' })} – {formatDate(trip.endDate)} · {days} días</span>
      </div>
      <div className="trip-body">
        <div className="row wrap">
          <Badge kind="neutral" icon={Users}>{trip.travelers} viajero{trip.travelers > 1 ? 's' : ''}</Badge>
          {trip.id && <span className="small muted">ID {trip.id}</span>}
        </div>
        <div className="budget-box row between">
          <div>
            <div className="small muted">Presupuesto</div>
            <div className="kpi num" style={{ fontSize: 22 }}>{formatCOP(trip.budgetCOP)}</div>
            {budget && <div className="small muted">Reservado {formatCOP(budget.reservedCOP)}</div>}
          </div>
          {onOpen && <button className="btn btn-sm" onClick={() => onOpen(trip)}>Ver detalles <ArrowRight size={14} /></button>}
          {!onOpen && trip.id && <Link className="btn btn-sm" to={`/trips/${trip.id}`}>Ver detalles <ArrowRight size={14} /></Link>}
        </div>
        {children}
      </div>
    </article>
  )
}

export function TripList({ data }) {
  const trips = data?.trips || []
  if (!trips.length) return <div className="alert info">Aún no tienes viajes guardados.</div>
  return <div className="grid cols-2">{trips.map((t) => <TripCard key={t.id} trip={t} />)}</div>
}

// ------------------------------------------------------------------------------ Itinerario

export function ItineraryAgenda({ days, renderItemActions }) {
  if (!Array.isArray(days) || !days.length) return null
  return (
    <div className="agenda">
      {days.map((day) => (
        <section key={day.date} className="agenda-day" aria-label={formatDayLong(day.date)}>
          <h4>{formatDayLong(day.date)}</h4>
          {(day.items || []).length === 0 && <p className="small muted">Sin actividades.</p>}
          {(day.items || []).map((item, i) => (
            <div key={i} className="agenda-item">
              <span className="agenda-time">{item.time || '—'}</span>
              <div>
                <strong>{item.title}</strong>
                <div className="small muted">{[item.place, item.notes].filter(Boolean).join(' · ')}</div>
              </div>
              <div className="right small">
                {item.costCOP > 0 ? <span className="num">{formatCOP(item.costCOP)}</span> : <span className="muted">Gratis</span>}
                {renderItemActions?.(day, item, i)}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}

export function ItineraryBlock({ data }) {
  return (
    <div className="stack">
      <h3><CalendarDays size={16} style={{ verticalAlign: -2 }} /> Itinerario</h3>
      <ItineraryAgenda days={data?.days} />
    </div>
  )
}

// -------------------------------------------------------------------------------- Reservas

const KIND_ICON = { FLIGHT: Plane, HOTEL: BedDouble, ACTIVITY: Landmark }

export function ReservationRow({ reservation: r, actions }) {
  const Icon = KIND_ICON[r.kind] || Landmark
  const link = safeUrl(r.link)
  return (
    <article className="res-row">
      <div className={`res-icon ${r.kind === 'HOTEL' ? 'hotel' : r.kind === 'ACTIVITY' ? 'activity' : ''}`}><Icon size={22} /></div>
      <div className="grow">
        <div className="row wrap" style={{ gap: 8 }}>
          <strong>{r.title}</strong>
          <StatusBadge status={r.status} />
          {r.paid && <Badge kind="neutral" icon={Wallet}>Pagada con monedero</Badge>}
        </div>
        <div className="small muted">
          {KIND_LABELS[r.kind]} · {formatDate(r.createdAt?.slice(0, 10))}
          {r.originalPrice && r.originalCurrency ? ` · ${formatMoney(r.originalPrice, r.originalCurrency)}` : ''}
        </div>
        {link && <a className="small" href={link} target="_blank" rel="noopener noreferrer">Enlace del proveedor <ExternalLink size={12} /></a>}
        {actions}
      </div>
      <div className="price num right" style={{ fontSize: 18 }}>{formatCOP(r.priceCOP)}</div>
    </article>
  )
}

export function ReservationBlock({ data }) {
  const list = data?.reservations || (data?.reservation ? [data.reservation] : [])
  if (!list.length) return <div className="alert info">No hay reservas para mostrar.</div>
  return (
    <div className="stack">
      {list.map((r) => <ReservationRow key={r.id} reservation={r} />)}
      {data?.balanceCOP != null && (
        <div className="alert info">Reserva simulada: no hubo cobro real. Saldo del monedero: <strong>{formatCOP(data.balanceCOP)}</strong></div>
      )}
    </div>
  )
}

// -------------------------------------------------------------------------------- Monedero

export function WalletBlock({ data }) {
  return (
    <div className="stack">
      <div className="wallet-hero">
        <div className="small" style={{ opacity: 0.85 }}>Saldo del monedero (simulado)</div>
        <div className="kpi num">{formatCOP(data?.balanceCOP)}</div>
      </div>
      {(data?.transactions || []).slice(0, 5).map((t) => (
        <div className="txn" key={t.id}>
          <div><strong>{t.title || t.type}</strong><div className="small muted">{formatDate(t.createdAt?.slice(0, 10))}</div></div>
          <span className={`num ${t.amountCOP >= 0 ? 'pos' : 'neg'}`}>{t.amountCOP >= 0 ? '+' : ''}{formatCOP(t.amountCOP)}</span>
        </div>
      ))}
    </div>
  )
}

// ----------------------------------------------------------------------------------- Extras

export function CurrencyBlock({ data }) {
  return (
    <div className="card soft row between">
      <div>
        <div className="small muted">Conversión de divisas</div>
        <div className="kpi num" style={{ fontSize: 22 }}>
          {formatMoney(data.amount, data.from)} = {formatMoney(data.result, data.to)}
        </div>
        <div className="small muted">1 {data.from} = {Number(data.rate).toLocaleString('es-CO')} {data.to} · {data.source}</div>
      </div>
    </div>
  )
}

export function TransportBlock({ data }) {
  const bus = data.recommendation === 'BUS'
  return (
    <div className="card stack">
      <div className="row between">
        <h3>{data.origin} → {data.destination}</h3>
        <Badge kind="ok" icon={bus ? Bus : Plane}>Recomendado: {bus ? 'bus' : 'avión'}</Badge>
      </div>
      <p>{data.reason}</p>
      <div className="grid cols-2">
        <div className="card soft"><Bus size={18} /> <strong>Bus</strong><div className="num">~{data.bus.hours} h · ~{formatCOP(data.bus.estimatedCostCOP)}</div></div>
        <div className="card soft"><Plane size={18} /> <strong>Avión</strong><div className="num">~{data.flight.hours} h puerta a puerta</div></div>
      </div>
      <p className="small muted">{data.assumptions}</p>
    </div>
  )
}

// --------------------------------------------------------------------------------- Despacho

/** Elige el componente visual segun el `component` que emitio el agente. */
export function UiRenderer({ component, data, onBook }) {
  switch (component) {
    case 'flights': return <FlightCards data={data} onBook={onBook} />
    case 'weather': return <WeatherCards data={data} />
    case 'hotels': return <HotelCards data={data} onBook={onBook} />
    case 'trip': return <TripCard trip={data.trip} budget={data.budget} />
    case 'trips': return <TripList data={data} />
    case 'itinerary': return <ItineraryBlock data={data} />
    case 'reservation':
    case 'reservations': return <ReservationBlock data={data} />
    case 'wallet': return <WalletBlock data={data} />
    case 'currency': return <CurrencyBlock data={data} />
    case 'transport': return <TransportBlock data={data} />
    default: return null
  }
}
