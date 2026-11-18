// Canal 2: interaccion agentica. El navegador llama DIRECTO al Orchestrator en AgentCore Runtime
// (HTTP streaming, sin API Gateway) con el JWT de Cognito. El runtime valida el token.
import { config } from './config'
import { getAccessToken } from './auth'
import { notifyDataChanged } from './events'
import { createSseParser, interpretEvent } from './sse'

// Tools del Orchestrator que escriben datos: al terminar, las pantallas abiertas se recargan.
const WRITE_TOOLS = new Set([
  'create_trip', 'update_trip', 'create_itinerary', 'update_itinerary',
  'create_reservation', 'update_reservation', 'top_up_wallet',
])

export const TOOL_LABELS = {
  ask_flights: 'Consultando vuelos',
  ask_weather: 'Consultando el clima',
  ask_hotels: 'Buscando hoteles',
  create_trip: 'Creando el viaje',
  get_trips: 'Revisando tus viajes',
  update_trip: 'Actualizando el viaje',
  create_itinerary: 'Guardando el itinerario',
  update_itinerary: 'Actualizando el itinerario',
  create_reservation: 'Registrando la reserva',
  get_reservations: 'Revisando tus reservas',
  update_reservation: 'Actualizando la reserva',
  get_wallet: 'Consultando tu monedero',
  top_up_wallet: 'Recargando el monedero',
  convert_currency: 'Convirtiendo divisas',
  compare_transport: 'Comparando bus y avión',
}

export const newSessionId = () => crypto.randomUUID() // 36 caracteres (el runtime exige >= 33)

/**
 * Envia un mensaje al Orchestrator y entrega la respuesta por streaming.
 * handlers: onText(delta), onTool(name), onUi({component,data}), onError(message)
 * Devuelve cuando el stream termina. Se puede cancelar con `signal`.
 */
export async function streamChat({ prompt, sessionId, signal, onText, onTool, onUi, onError }) {
  const token = await getAccessToken()
  if (!token) {
    onError?.('Tu sesión expiró. Inicia sesión de nuevo.')
    return
  }

  let wrote = false
  let response
  try {
    response = await fetch(config.agentUrl, {
      method: 'POST',
      signal,
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
        'X-Amzn-Bedrock-AgentCore-Runtime-Session-Id': sessionId,
      },
      body: JSON.stringify({ prompt }),
    })
  } catch (e) {
    if (e.name !== 'AbortError') onError?.('No se pudo conectar con el asistente.')
    return
  }

  if (!response.ok) {
    const reason =
      response.status === 401 || response.status === 403
        ? 'Tu sesión no es válida para el asistente. Inicia sesión de nuevo.'
        : response.status === 429
          ? 'Demasiadas solicitudes. Espera un momento.'
          : 'El asistente no está disponible en este momento. Intenta de nuevo.'
    onError?.(reason)
    return
  }

  const parser = createSseParser((raw) => {
    const action = interpretEvent(raw)
    if (!action) return
    if (action.type === 'text') onText?.(action.text)
    else if (action.type === 'tool') {
      if (WRITE_TOOLS.has(action.name)) wrote = true
      onTool?.(action.name)
    } else if (action.type === 'ui') onUi?.({ component: action.component, data: action.data })
    else if (action.type === 'error') onError?.(action.message)
  })

  try {
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.flush()
  } catch (e) {
    if (e.name !== 'AbortError') onError?.('Se interrumpió la conexión con el asistente.')
  } finally {
    if (wrote) notifyDataChanged()
  }
}
