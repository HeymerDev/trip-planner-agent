import { describe, expect, it } from 'vitest'
import { createSseParser, interpretEvent } from './sse'
import { durationMinutes, safeUrl } from './format'

const collect = () => {
  const events = []
  return { events, parser: createSseParser((e) => events.push(e)) }
}

describe('parser SSE', () => {
  it('une eventos partidos en varios chunks', () => {
    const { events, parser } = collect()
    parser.push('data: {"event":{"contentBlockDelta":{"delta":{"te')
    parser.push('xt":"Hola"}}}}\n\ndata: {"ui":{"component":"trip","data":{}}}\n\n')
    expect(events).toHaveLength(2)
    expect(interpretEvent(events[0])).toEqual({ type: 'text', text: 'Hola' })
    expect(interpretEvent(events[1])).toMatchObject({ type: 'ui', component: 'trip' })
  })
  it('tolera CRLF, lineas basura y JSON doblemente serializado', () => {
    const { events, parser } = collect()
    parser.push('data: no-json\r\n\r\ndata: "{\\"error\\":\\"fallo\\"}"\r\n\r\n')
    parser.flush()
    expect(events).toEqual([{ error: 'fallo' }])
  })
  it('flush entrega el ultimo bloque sin linea en blanco', () => {
    const { events, parser } = collect()
    parser.push('data: {"event":{"messageStop":{}}}')
    parser.flush()
    expect(interpretEvent(events[0])).toEqual({ type: 'stop' })
  })
  it('reconoce el inicio de una herramienta', () => {
    expect(interpretEvent({ event: { contentBlockStart: { start: { toolUse: { name: 'ask_flights' } } } } })).toEqual({ type: 'tool', name: 'ask_flights' })
    expect(interpretEvent({ event: { metadata: {} } })).toBeNull()
  })
})

describe('helpers', () => {
  it('safeUrl solo permite http(s)', () => {
    expect(safeUrl('https://x.com/a?b=1')).toBe('https://x.com/a?b=1')
    expect(safeUrl('javascript:alert(1)')).toBeNull()
    expect(safeUrl('no es url')).toBeNull()
  })
  it('durationMinutes', () => {
    expect(durationMinutes('1 h 32 min')).toBe(92)
    expect(durationMinutes('45 min')).toBe(45)
    expect(durationMinutes(null)).toBe(Infinity)
  })
})
