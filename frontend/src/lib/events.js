// Aviso global "los datos cambiaron" para que las pantallas abiertas se recarguen (CA-6):
// lo emiten tanto la UI (cada escritura a la API) como el chat (cuando una Tool de negocio escribe).
import { useEffect } from 'react'

const bus = new EventTarget()
const EVENT = 'tripplanner:data-changed'

export const notifyDataChanged = () => bus.dispatchEvent(new Event(EVENT))

/** Ejecuta `callback` cuando cambian los datos de negocio (se desuscribe sola). */
export function useDataRefresh(callback) {
  useEffect(() => {
    const handler = () => callback()
    bus.addEventListener(EVENT, handler)
    return () => bus.removeEventListener(EVENT, handler)
  }, [callback])
}
