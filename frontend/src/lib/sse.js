// Parser incremental de Server-Sent Events: acumula texto y entrega cada payload `data:` ya como JSON.

export function createSseParser(onEvent) {
  let buffer = ''
  const dispatch = (block) => {
    const data = block
      .split('\n')
      .filter((line) => line.startsWith('data:'))
      .map((line) => line.slice(5).replace(/^ /, ''))
      .join('\n')
    if (!data || data === '[DONE]') return
    let parsed
    try {
      parsed = JSON.parse(data)
    } catch {
      return // linea que no es JSON: se ignora
    }
    // Algunos servidores serializan dos veces (un JSON dentro de un string)
    if (typeof parsed === 'string') {
      try {
        parsed = JSON.parse(parsed)
      } catch {
        /* era texto plano */
      }
    }
    onEvent(parsed)
  }
  return {
    push(chunk) {
      buffer += chunk.replace(/\r\n/g, '\n')
      let index
      while ((index = buffer.indexOf('\n\n')) !== -1) {
        dispatch(buffer.slice(0, index))
        buffer = buffer.slice(index + 2)
      }
    },
    flush() {
      if (buffer.trim()) dispatch(buffer)
      buffer = ''
    },
  }
}

/** Traduce un evento del Orchestrator a una accion de la interfaz. */
export function interpretEvent(event) {
  if (!event || typeof event !== 'object') return null
  if (event.ui?.component) return { type: 'ui', component: event.ui.component, data: event.ui.data }
  if (event.error) return { type: 'error', message: String(event.error) }
  const inner = event.event
  if (!inner) return null
  const text = inner.contentBlockDelta?.delta?.text
  if (text) return { type: 'text', text }
  const tool = inner.contentBlockStart?.start?.toolUse?.name
  if (tool) return { type: 'tool', name: tool }
  if (inner.messageStop) return { type: 'stop' }
  return null
}
