import { useEffect, useState } from 'react'
import { Save } from 'lucide-react'
import { api } from '../lib/api'
import { Alert, Loading, errorText, useToast } from '../components/Common'

const ACTIVITIES = [
  ['cultura', 'Cultura'], ['playa', 'Playa'], ['gastronomia', 'Gastronomía'], ['aventura', 'Aventura'],
  ['naturaleza', 'Naturaleza'], ['nocturna', 'Vida nocturna'], ['compras', 'Compras'], ['relax', 'Relax'],
]

export default function Preferences() {
  const toast = useToast()
  const [form, setForm] = useState(null)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    Promise.all([api.getPreferences(), api.me()])
      .then(([p, me]) => {
        setForm({ defaultBudgetCOP: p.defaultBudgetCOP ?? '', activities: p.activities || [], airlines: (p.airlines || []).join(', '), restrictions: p.restrictions || '' })
        setName(me.name || '')
      })
      .catch((e) => setError(errorText(e)))
  }, [])

  const toggle = (key) => setForm({ ...form, activities: form.activities.includes(key) ? form.activities.filter((a) => a !== key) : [...form.activities, key] })

  async function save(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api.savePreferences({
        defaultBudgetCOP: form.defaultBudgetCOP === '' ? undefined : Number(form.defaultBudgetCOP),
        activities: form.activities,
        airlines: form.airlines.split(',').map((s) => s.trim()).filter(Boolean),
        restrictions: form.restrictions,
      })
      await api.updateMe({ name })
      toast('Preferencias guardadas')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  if (!form) return error ? <Alert>{error}</Alert> : <Loading />
  return (
    <form className="stack" onSubmit={save}>
      <div className="page-head"><div><h1>Preferencias</h1><p className="sub">Se guardan en tu cuenta y ayudan a personalizar viajes e itinerarios.</p></div></div>
      <section className="card stack">
        <div className="field"><label htmlFor="pn">Tu nombre</label><input id="pn" value={name} maxLength={80} onChange={(e) => setName(e.target.value)} /></div>
        <div className="field"><label htmlFor="pb">Presupuesto habitual (COP)</label><input id="pb" type="number" min="0" step="50000" value={form.defaultBudgetCOP} onChange={(e) => setForm({ ...form, defaultBudgetCOP: e.target.value })} /></div>
        <div className="field">
          <span className="label" id="acts">Tipo de actividades</span>
          <div className="chips" role="group" aria-labelledby="acts">
            {ACTIVITIES.map(([k, v]) => <button type="button" key={k} className="chip" aria-pressed={form.activities.includes(k)} onClick={() => toggle(k)}>{v}</button>)}
          </div>
        </div>
        <div className="field"><label htmlFor="pa">Aerolíneas favoritas (separadas por coma)</label><input id="pa" value={form.airlines} onChange={(e) => setForm({ ...form, airlines: e.target.value })} placeholder="LATAM, Avianca" /></div>
        <div className="field"><label htmlFor="pr">Restricciones o notas</label><textarea id="pr" maxLength={300} value={form.restrictions} onChange={(e) => setForm({ ...form, restrictions: e.target.value })} placeholder="Sin escalas, viajo con niños, dieta vegetariana…" /></div>
      </section>
      {error && <Alert>{error}</Alert>}
      <div><button className="btn btn-primary" disabled={busy}><Save size={16} /> {busy ? 'Guardando…' : 'Guardar preferencias'}</button></div>
    </form>
  )
}
