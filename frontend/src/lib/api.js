// Canal 1: operaciones de negocio. Frontend -> API Gateway -> Lambda -> DynamoDB.
// El frontend nunca toca DynamoDB; la identidad viaja en el JWT (RNF-03, RNF-13).
import { config } from './config'
import { getAccessToken } from './auth'
import { notifyDataChanged } from './events'

export class ApiError extends Error {
  constructor(status, code, message, fields) {
    super(message)
    this.status = status
    this.code = code
    this.fields = fields
  }
}

async function request(method, path, { body, query } = {}) {
  const token = await getAccessToken()
  if (!token) throw new ApiError(401, 'UNAUTHORIZED', 'Tu sesión expiró. Inicia sesión de nuevo.')
  const qs = query
    ? '?' + new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== '')).toString()
    : ''
  let response
  try {
    response = await fetch(config.apiUrl + path + qs, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { 'Content-Type': 'application/json' } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'No hay conexión con el servidor.')
  }
  const text = await response.text()
  let data = null
  try {
    data = text ? JSON.parse(text) : null
  } catch {
    /* respuesta no JSON */
  }
  if (!response.ok) {
    const e = data?.error
    // 401 de API Gateway no trae cuerpo estandar
    throw new ApiError(
      response.status,
      e?.code || 'ERROR',
      e?.message || (response.status === 401 ? 'Tu sesión expiró. Inicia sesión de nuevo.' : 'Ocurrió un error. Intenta de nuevo.'),
      e?.fields,
    )
  }
  if (method !== 'GET') notifyDataChanged()
  return data
}

export const api = {
  me: () => request('GET', '/me'),
  updateMe: (body) => request('PUT', '/me', { body }),
  getPreferences: () => request('GET', '/me/preferences'),
  savePreferences: (body) => request('PUT', '/me/preferences', { body }),
  dashboard: () => request('GET', '/dashboard'),

  listTrips: () => request('GET', '/trips'),
  getTrip: (id) => request('GET', `/trips/${id}`),
  createTrip: (body) => request('POST', '/trips', { body }),
  updateTrip: (id, body) => request('PATCH', `/trips/${id}`, { body }),
  deleteTrip: (id) => request('DELETE', `/trips/${id}`),

  saveItinerary: (id, days, exists) =>
    request(exists ? 'PUT' : 'POST', `/trips/${id}/itinerary`, { body: { days } }),

  listReservations: (query) => request('GET', '/reservations', { query }),
  createReservation: (body) => request('POST', '/reservations', { body }),
  updateReservation: (id, body) => request('PATCH', `/reservations/${id}`, { body }),

  wallet: () => request('GET', '/wallet'),
  topUp: (amountCOP) => request('POST', '/wallet/topup', { body: { amountCOP } }),
  purchase: (body) => request('POST', '/purchases', { body }),

  // Historial: se lee de la memoria del agente (AgentCore Memory) a traves de la Lambda `conversations`
  conversations: () => request('GET', '/conversations'),
  conversation: (id) => request('GET', `/conversations/${id}`),
  deleteConversation: (id) => request('DELETE', `/conversations/${id}`),

  fx: (from, to, amount = 1) => request('GET', '/fx', { query: { from, to, amount } }),
  transport: (origin, destination) => request('GET', '/transport', { query: { origin, destination } }),
}
