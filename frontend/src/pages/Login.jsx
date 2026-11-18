import { useState } from 'react'
import { Navigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { useAuth } from '../auth-context'
import { Alert } from '../components/Common'

export default function Login() {
  const { status, login, register } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (status === 'authed') return <Navigate to="/" replace />

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await (mode === 'login' ? login(email.trim(), password) : register(email.trim(), password))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login">
      <div className="login-card stack">
        <div className="login-brand">
          <span className="brand-mark"><Sparkles size={26} /></span>
          <h1>TripPlanner AI</h1>
          <p className="muted">Tu compañero de viaje con agentes de inteligencia artificial</p>
        </div>
        <form className="card stack" onSubmit={submit} noValidate>
          <h2>{mode === 'login' ? 'Inicia sesión' : 'Crea tu cuenta'}</h2>
          <div className="field">
            <label htmlFor="email">Correo electrónico</label>
            <input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="password">Contraseña</label>
            <input id="password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={password} onChange={(e) => setPassword(e.target.value)} />
            {mode === 'register' && <span className="small muted">Mínimo 8 caracteres, con mayúscula, minúscula y número.</span>}
          </div>
          {error && <Alert>{error}</Alert>}
          <button className="btn btn-primary btn-block" disabled={busy || !email || !password}>
            {busy ? 'Un momento…' : mode === 'login' ? 'Entrar' : 'Crear cuenta y entrar'}
          </button>
          <button type="button" className="btn btn-ghost btn-block" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? '¿Primera vez? Crea una cuenta' : 'Ya tengo cuenta'}
          </button>
        </form>
      </div>
    </div>
  )
}
