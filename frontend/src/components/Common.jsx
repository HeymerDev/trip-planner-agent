import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'
import { STATUS_LABELS } from '../lib/format'

export const Spinner = () => <div className="spinner" role="status" aria-label="Cargando" />

export function Loading({ rows = 3 }) {
  return (
    <div className="stack" aria-busy="true">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton" />
      ))}
    </div>
  )
}

export function Empty({ icon: Icon, title, children }) {
  return (
    <div className="empty card flat">
      {Icon && <Icon size={36} aria-hidden="true" />}
      <h3>{title}</h3>
      {children && <p className="small" style={{ marginTop: 6 }}>{children}</p>}
    </div>
  )
}

export const Alert = ({ kind = 'error', children }) => (
  <div className={`alert ${kind}`} role={kind === 'error' ? 'alert' : 'status'}>
    {children}
  </div>
)

export const Badge = ({ kind = '', icon: Icon, children }) => (
  <span className={`badge ${kind}`}>
    {Icon && <Icon size={13} aria-hidden="true" />}
    {children}
  </span>
)

// Etiqueta visible de estado de reserva (RF-52): Simulada / Pendiente / Confirmada / Cancelada.
const STATUS_KIND = { SIMULADA: 'neutral', PENDIENTE: 'warn', CONFIRMADA: 'ok', CANCELADA: 'danger' }
export const StatusBadge = ({ status }) => (
  <Badge kind={STATUS_KIND[status] || ''}>{STATUS_LABELS[status] || status}</Badge>
)

export function Modal({ title, onClose, children, wide }) {
  const ref = useRef(null)
  useEffect(() => {
    const onKey = (e) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    ref.current?.focus()
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title} tabIndex={-1} ref={ref} style={wide ? { maxWidth: 720 } : undefined}>
        <div className="row between" style={{ marginBottom: 14 }}>
          <h2>{title}</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Cerrar">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  )
}

// ---- Avisos (toast) ----
const ToastContext = createContext(() => {})
export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }) {
  const [toast, setToast] = useState(null)
  const timer = useRef()
  const show = useCallback((message, kind = '') => {
    setToast({ message, kind })
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setToast(null), 4200)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      {toast && (
        <div className={`toast ${toast.kind}`} role="status">
          {toast.message}
        </div>
      )}
    </ToastContext.Provider>
  )
}

/** Mensaje de un error de la API, incluyendo los campos invalidos. */
export function errorText(error) {
  if (!error) return ''
  const fields = error.fields ? Object.values(error.fields).join(' ') : ''
  return fields ? `${error.message} ${fields}` : error.message || 'Ocurrió un error.'
}
