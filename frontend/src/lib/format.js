// Formato de dinero, fechas y estados.

const cop = new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 })
export const formatCOP = (value) => cop.format(Number(value) || 0)

export function formatMoney(value, currency = 'COP') {
  if (value === null || value === undefined) return '—'
  if (currency === 'COP') return formatCOP(value)
  return new Intl.NumberFormat('es-CO', { style: 'currency', currency, maximumFractionDigits: 2 }).format(value)
}

// Las fechas vienen como AAAA-MM-DD: se parsean como locales para evitar el desfase por zona horaria.
export function parseDate(iso) {
  const [y, m, d] = String(iso).split('-').map(Number)
  return new Date(y, m - 1, d)
}

export const formatDate = (iso, opts = { day: 'numeric', month: 'short', year: 'numeric' }) =>
  iso ? parseDate(iso).toLocaleDateString('es-CO', opts) : '—'

export const formatDayLong = (iso) =>
  parseDate(iso).toLocaleDateString('es-CO', { weekday: 'long', day: 'numeric', month: 'long' })

export function nights(start, end) {
  return Math.max(1, Math.round((parseDate(end) - parseDate(start)) / 86400000))
}

export function tripDays(start, end) {
  const days = []
  for (let d = parseDate(start); d <= parseDate(end); d = new Date(d.getFullYear(), d.getMonth(), d.getDate() + 1)) {
    days.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`)
  }
  return days
}

export const STATUS_LABELS = {
  SIMULADA: 'Simulada',
  PENDIENTE: 'Pendiente',
  CONFIRMADA: 'Confirmada',
  CANCELADA: 'Cancelada',
}

export const KIND_LABELS = { FLIGHT: 'Vuelo', HOTEL: 'Hotel', ACTIVITY: 'Actividad' }

export const TRIP_STATUS_LABELS = {
  PLANEADO: 'Planeado',
  CONFIRMADO: 'Confirmado',
  FINALIZADO: 'Finalizado',
  CANCELADO: 'Cancelado',
}

export const newKey = (prefix) => `${prefix}-${crypto.randomUUID()}`

/** Solo URLs http(s): los enlaces vienen del modelo y no deben poder ser `javascript:`. */
export function safeUrl(url) {
  try {
    const u = new URL(String(url))
    return u.protocol === 'https:' || u.protocol === 'http:' ? u.href : null
  } catch {
    return null
  }
}

/** "1 h 32 min" -> 92 (minutos), para marcar el vuelo mas rapido. */
export function durationMinutes(text) {
  if (!text) return Infinity
  const h = /(\d+)\s*h/.exec(text)
  const m = /(\d+)\s*m/.exec(text)
  const total = (h ? Number(h[1]) * 60 : 0) + (m ? Number(m[1]) : 0)
  return total || Infinity
}

/** Gradiente estable por destino para las tarjetas de viaje (sin imagenes externas). */
export function destinationGradient(name = '') {
  let hash = 0
  for (const ch of name) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0
  const hue = hash % 360
  return `linear-gradient(135deg, hsl(${hue} 70% 38%), hsl(${(hue + 40) % 360} 75% 52%))`
}
