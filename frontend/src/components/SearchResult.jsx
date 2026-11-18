import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { TOOL_LABELS } from '../lib/agent'
import { Alert, Loading } from './Common'
import { UiRenderer } from './cards'

/** Resultado de una busqueda al agente: componentes visuales + resumen en texto. */
export default function SearchResult({ search, only, onBook, empty }) {
  const { loading, ui, text, error, tool, done } = search
  const blocks = only ? ui.filter((u) => only.includes(u.component)) : ui
  return (
    <div className="stack" aria-live="polite">
      {loading && (
        <div className="row"><span className="spinner" /> <span className="muted">{TOOL_LABELS[tool] || 'El asistente está trabajando'}…</span></div>
      )}
      {loading && blocks.length === 0 && <Loading rows={2} />}
      {error && <Alert>{error}</Alert>}
      {blocks.map((b, i) => <UiRenderer key={i} component={b.component} data={b.data} onBook={onBook} />)}
      {text && (
        <div className="card flat">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ a: (props) => <a {...props} target="_blank" rel="noopener noreferrer" /> }}>{text}</ReactMarkdown>
        </div>
      )}
      {done && !error && blocks.length === 0 && !text && <Alert kind="info">{empty || 'No se encontraron resultados.'}</Alert>}
    </div>
  )
}
