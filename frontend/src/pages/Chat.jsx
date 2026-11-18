import { useCallback, useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { ArrowUp, Brain, Check, Menu, MessageSquare, MessageSquarePlus, Sparkles, Square, Trash2, X } from 'lucide-react'
import { TOOL_LABELS, newSessionId, streamChat } from '../lib/agent'
import { api } from '../lib/api'
import { UiRenderer } from '../components/cards'
import BookingModal from '../components/BookingModal'
import { Alert, Modal, errorText, useToast } from '../components/Common'

const SCENARIO =
  'Quiero organizar unas vacaciones de cuatro días en Cartagena. Salgo desde Bogotá, viajo con dos personas más y tengo un presupuesto de 5 millones de pesos. Quiero conocer el clima, encontrar vuelos y organizar algunas actividades turísticas.'

const SUGGESTIONS = [
  { label: 'Planear un viaje a Cartagena', prompt: SCENARIO },
  { label: '¿Bus o avión de Medellín a Manizales?', prompt: '¿Me conviene ir en bus o en avión de Medellín a Manizales?' },
  { label: 'Mis viajes y reservas', prompt: 'Muéstrame mis viajes y mis reservas.' },
  { label: '¿Cuánto es 300 USD en pesos?', prompt: '¿Cuántos pesos colombianos son 300 dólares hoy?' },
]

// Las conversaciones se guardan en la MEMORIA del agente (AgentCore Memory) y se leen por la API:
// sobreviven a cerrar el navegador, cambiar de dispositivo o limpiar datos.
const blankChat = () => ({ id: newSessionId(), title: 'Nueva conversación', messages: [] })

function groupByDate(items) {
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const today = startOfDay(new Date())
  const DAY = 86400000
  const groups = [['Hoy', []], ['Ayer', []], ['Últimos 7 días', []], ['Anteriores', []]]
  for (const item of items) {
    const age = (today - startOfDay(new Date(item.updatedAt))) / DAY
    groups[age < 1 ? 0 : age < 2 ? 1 : age < 8 ? 2 : 3][1].push(item)
  }
  return groups.filter(([, list]) => list.length)
}

function ConversationList({ history, currentId, onOpen, onNew, onDelete, onClose }) {
  return (
    <aside className="conv-panel" aria-label="Conversaciones">
      <div className="row between">
        <strong>Conversaciones</strong>
        {onClose && <button className="icon-btn conv-close" aria-label="Cerrar lista" onClick={onClose}><X size={16} /></button>}
      </div>
      <button className="btn btn-primary btn-sm" onClick={onNew}><MessageSquarePlus size={15} /> Nueva conversación</button>
      <div className="conv-scroll">
        {history.length === 0 && <p className="small muted">Aún no tienes conversaciones guardadas.</p>}
        {groupByDate(history).map(([label, list]) => (
          <div key={label}>
            <div className="conv-group">{label}</div>
            {list.map((h) => (
              <div key={h.id} className={`conv-item ${h.id === currentId ? 'active' : ''}`}>
                <button className="conv-open" onClick={() => onOpen(h.id)} title={h.title}>
                  <MessageSquare size={15} aria-hidden="true" />
                  <span>{h.title}</span>
                </button>
                <button className="conv-del" aria-label={`Eliminar ${h.title}`} title="Eliminar" onClick={() => onDelete(h)}>
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}

function appendText(message, text) {
  const blocks = message.blocks.slice()
  const last = blocks[blocks.length - 1]
  if (last?.type === 'text') blocks[blocks.length - 1] = { ...last, text: last.text + text }
  else blocks.push({ type: 'text', text })
  return { ...message, blocks }
}

function Markdown({ children }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{ a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}
    >
      {children}
    </ReactMarkdown>
  )
}

function AssistantMessage({ message, streaming, onBook }) {
  const last = message.blocks[message.blocks.length - 1]
  return (
    <div className="msg assistant">
      <div className="ui-stack">
        {message.blocks.map((block, i) => {
          if (block.type === 'text')
            return <div className="bubble" key={i}><Markdown>{block.text}</Markdown></div>
          if (block.type === 'ui')
            return <UiRenderer key={i} component={block.component} data={block.data} onBook={onBook} />
          if (block.type === 'error') return <Alert key={i}>{block.message}</Alert>
          const working = streaming && i === message.blocks.length - 1
          return (
            <span className="tool-chip" key={i}>
              {working ? <span className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> : <Check size={14} />}
              {TOOL_LABELS[block.name] || block.name}
            </span>
          )
        })}
        {streaming && (!last || last.type === 'ui') && (
          <div className="bubble"><span className="typing" aria-label="El asistente está escribiendo"><i /><i /><i /></span></div>
        )}
      </div>
    </div>
  )
}

export default function Chat() {
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const [chat, setChat] = useState(blankChat)
  const [history, setHistory] = useState([])
  const [booting, setBooting] = useState(true)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [booking, setBooking] = useState(null)
  const [confirmDelete, setConfirmDelete] = useState(null)
  const [panelOpen, setPanelOpen] = useState(false)
  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const sentPrompt = useRef(false)

  const refreshHistory = useCallback(async () => {
    try {
      const { conversations } = await api.conversations()
      setHistory(conversations)
      return conversations
    } catch {
      return []
    }
  }, [])

  const openConversation = useCallback(async (id) => {
    setPanelOpen(false)
    try {
      const c = await api.conversation(id)
      setChat({ id: c.id, title: c.title, messages: c.messages })
    } catch (e) {
      toast(errorText(e), 'error')
    }
  }, [toast])

  // Al entrar: carga el historial guardado en la memoria y abre la conversacion mas reciente
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const list = await refreshHistory()
      if (!cancelled && !params.get('prompt') && list.length) await openConversation(list[0].id)
      if (!cancelled) setBooting(false)
    })()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [chat.messages, streaming, booting])

  const patchLast = useCallback((fn) => {
    setChat((c) => {
      const messages = c.messages.slice()
      messages[messages.length - 1] = fn(messages[messages.length - 1])
      return { ...c, messages }
    })
  }, [])

  const send = useCallback(
    async (text) => {
      const prompt = text.trim()
      if (!prompt || streaming) return
      setInput('')
      setStreaming(true)
      setChat((c) => ({
        ...c,
        title: c.messages.length ? c.title : prompt.slice(0, 70),
        messages: [...c.messages, { role: 'user', text: prompt }, { role: 'assistant', blocks: [] }],
      }))
      const controller = new AbortController()
      abortRef.current = controller
      await streamChat({
        prompt,
        sessionId: chat.id,
        signal: controller.signal,
        onText: (t) => patchLast((m) => appendText(m, t)),
        onTool: (name) => patchLast((m) => ({ ...m, blocks: [...m.blocks, { type: 'tool', name }] })),
        onUi: ({ component, data }) => patchLast((m) => ({ ...m, blocks: [...m.blocks, { type: 'ui', component, data }] })),
        onError: (message) => patchLast((m) => ({ ...m, blocks: [...m.blocks, { type: 'error', message }] })),
      })
      setStreaming(false)
      abortRef.current = null
      refreshHistory() // la conversacion ya quedo guardada en la memoria del agente
    },
    [chat.id, patchLast, refreshHistory, streaming],
  )

  // Prompt precargado desde otras pantallas (por ejemplo "Generar con el asistente" en un viaje)
  useEffect(() => {
    const initial = params.get('prompt')
    if (initial && !sentPrompt.current) {
      sentPrompt.current = true
      setParams({}, { replace: true })
      setChat(blankChat())
      setTimeout(() => send(initial), 0)
    }
  }, [params, setParams, send])

  const newChat = () => {
    abortRef.current?.abort()
    setStreaming(false)
    setPanelOpen(false)
    setChat(blankChat())
  }

  const removeConversation = async () => {
    const target = confirmDelete
    setConfirmDelete(null)
    try {
      await api.deleteConversation(target.id)
      toast('Conversación eliminada de la memoria')
      const list = await refreshHistory()
      if (target.id === chat.id) {
        if (list.length) await openConversation(list[0].id)
        else setChat(blankChat())
      }
    } catch (e) {
      toast(errorText(e), 'error')
    }
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send(input)
    }
  }

  const panel = (onClose) => (
    <ConversationList history={history} currentId={chat.id} onOpen={openConversation} onNew={newChat}
      onDelete={setConfirmDelete} onClose={onClose} />
  )
  return (
    <div className="chat-layout">
      <div className="conv-desktop">{panel(null)}</div>
      {panelOpen && (
        <div className="conv-drawer" role="dialog" aria-modal="true" aria-label="Conversaciones">
          <div className="conv-backdrop" onClick={() => setPanelOpen(false)} />
          <div className="conv-sheet">{panel(() => setPanelOpen(false))}</div>
        </div>
      )}
      <div className="chat-wrap">
        <div className="row between wrap" style={{ marginBottom: 10 }}>
          <div className="row" style={{ minWidth: 0 }}>
            <button className="icon-btn conv-toggle" aria-label="Ver conversaciones" onClick={() => setPanelOpen(true)}><Menu size={18} /></button>
            <span className="badge ok"><Sparkles size={13} /> Asistente autónomo</span>
          </div>
          <button className="btn btn-sm conv-toggle" onClick={newChat}><MessageSquarePlus size={15} /> Nueva</button>
        </div>

      <div className="chat-scroll" ref={scrollRef} aria-live="polite">
        {booting ? (
          <div className="row muted"><span className="spinner" /> Cargando tus conversaciones…</div>
        ) : chat.messages.length === 0 ? (
          <div className="stack">
            <div className="hero-card stack">
              <h2>¿A dónde quieres ir?</h2>
              <p>Cuéntame tu viaje y coordino a mis agentes de vuelos, clima y hoteles. También puedo crear tu viaje, armar el itinerario y registrar reservas simuladas.</p>
            </div>
            <p className="small muted"><Brain size={14} style={{ verticalAlign: -2 }} /> Tus conversaciones se guardan en la memoria del agente: puedes cerrar la aplicación y retomarlas después.</p>
            <div className="chips">
              {SUGGESTIONS.map((s) => <button key={s.label} className="chip" onClick={() => send(s.prompt)}>{s.label}</button>)}
            </div>
          </div>
        ) : (
          chat.messages.map((m, i) =>
            m.role === 'user' ? (
              <div className="msg user" key={i}><div className="bubble">{m.text}</div></div>
            ) : (
              <AssistantMessage key={i} message={m} streaming={streaming && i === chat.messages.length - 1} onBook={setBooking} />
            ),
          )
        )}
      </div>

      <div className="composer">
        <textarea
          aria-label="Escribe tu mensaje"
          placeholder="Escribe tu solicitud de viaje…"
          rows={1}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
        />
        {streaming ? (
          <button className="send" onClick={() => abortRef.current?.abort()} aria-label="Detener"><Square size={18} /></button>
        ) : (
          <button className="send" onClick={() => send(input)} disabled={!input.trim()} aria-label="Enviar"><ArrowUp size={22} /></button>
        )}
      </div>
      {booking && <BookingModal request={booking} onClose={() => setBooking(null)} />}
      {confirmDelete && (
        <Modal title="Eliminar conversación" onClose={() => setConfirmDelete(null)}>
          <div className="stack">
            <p>Se borrará de la memoria del agente: <strong>{confirmDelete.title}</strong>. Tus viajes y reservas no se modifican.</p>
            <div className="row wrap">
              <button className="btn btn-danger" onClick={removeConversation}>Sí, eliminar</button>
              <button className="btn" onClick={() => setConfirmDelete(null)}>Cancelar</button>
            </div>
          </div>
        </Modal>
      )}
      </div>
    </div>
  )
}
