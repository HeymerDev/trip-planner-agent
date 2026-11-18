import { useCallback, useEffect, useState } from 'react'
import { errorText } from '../components/Common'
import { newSessionId, streamChat } from './agent'
import { useDataRefresh } from './events'

/** Carga datos de la API y los recarga cuando cambian los datos de negocio (chat o formularios). */
export function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: '', loading: true })
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback(async () => {
    try {
      const data = await loader()
      setState({ data, error: '', loading: false })
    } catch (e) {
      setState((s) => ({ ...s, error: errorText(e), loading: false }))
    }
  }, deps)
  useEffect(() => {
    run()
  }, [run])
  useDataRefresh(run)
  return { ...state, reload: run }
}

/**
 * Consulta puntual al Orchestrator para las pantallas de Vuelos, Clima y Hoteles: la busqueda la hacen
 * los agentes especialistas por A2A y la pantalla pinta los componentes que el agente devuelve.
 */
export function useAgentSearch() {
  const [state, setState] = useState({ loading: false, ui: [], text: '', error: '', tool: '', done: false })
  const run = useCallback(async (prompt) => {
    setState({ loading: true, ui: [], text: '', error: '', tool: '', done: false })
    await streamChat({
      prompt,
      sessionId: newSessionId(),
      onText: (t) => setState((s) => ({ ...s, text: s.text + t })),
      onTool: (name) => setState((s) => ({ ...s, tool: name })),
      onUi: (u) => setState((s) => ({ ...s, ui: [...s.ui, u] })),
      onError: (message) => setState((s) => ({ ...s, error: message })),
    })
    setState((s) => ({ ...s, loading: false, tool: '', done: true }))
  }, [])
  return { ...state, run }
}

export const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}
