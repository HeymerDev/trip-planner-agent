import { useState } from 'react'
import { Plus } from 'lucide-react'
import { api } from '../lib/api'
import { useLoad } from '../lib/hooks'
import { formatCOP, formatDate } from '../lib/format'
import { Alert, Loading, errorText, useToast } from '../components/Common'

const QUICK = [100000, 500000, 1000000, 2000000]
const TYPE_LABEL = { TOPUP: 'Recarga', PURCHASE: 'Compra', REFUND: 'Reembolso' }

export default function Wallet() {
  const { data, error, loading } = useLoad(() => api.wallet())
  const [amount, setAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const toast = useToast()

  async function topUp(value) {
    setBusy(true)
    setErr('')
    try {
      await api.topUp(Number(value))
      toast(`Recargaste ${formatCOP(value)}`)
      setAmount('')
    } catch (e) {
      setErr(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      <div className="page-head"><div><h1>Monedero</h1><p className="sub">Saldo simulado para comprar vuelos, hoteles y actividades. No usa tarjetas ni dinero real.</p></div></div>
      {error && <Alert>{error}</Alert>}
      {loading ? <Loading rows={2} /> : (
        <>
          <div className="wallet-hero">
            <div className="small" style={{ opacity: 0.85 }}>Saldo disponible</div>
            <div className="kpi num">{formatCOP(data.balanceCOP)}</div>
          </div>
          <section className="card stack">
            <h2>Recargar</h2>
            <div className="chips">{QUICK.map((q) => <button key={q} className="chip" disabled={busy} onClick={() => topUp(q)}>+ {formatCOP(q)}</button>)}</div>
            <form className="row wrap" onSubmit={(e) => { e.preventDefault(); topUp(amount) }}>
              <div className="field grow">
                <label htmlFor="amt" className="sr-only">Otro monto en COP</label>
                <input id="amt" type="number" min="1000" max="10000000" step="1000" placeholder="Otro monto (1.000 – 10.000.000)" value={amount} onChange={(e) => setAmount(e.target.value)} />
              </div>
              <button className="btn btn-primary" disabled={busy || !amount}><Plus size={16} /> Recargar</button>
            </form>
            {err && <Alert>{err}</Alert>}
            <p className="small muted">Recarga simulada: solo suma un monto. No se solicita ningún dato de pago.</p>
          </section>
          <section className="card">
            <h2 style={{ marginBottom: 8 }}>Movimientos</h2>
            {data.transactions.length === 0 ? <p className="muted">Aún no hay movimientos.</p> : data.transactions.map((t) => (
              <div className="txn" key={t.id}>
                <div><strong>{t.title || TYPE_LABEL[t.type]}</strong><div className="small muted">{TYPE_LABEL[t.type]} · {formatDate(t.createdAt.slice(0, 10))}</div></div>
                <span className={`num ${t.amountCOP >= 0 ? 'pos' : 'neg'}`}>{t.amountCOP >= 0 ? '+' : ''}{formatCOP(t.amountCOP)}</span>
              </div>
            ))}
          </section>
        </>
      )}
    </div>
  )
}
