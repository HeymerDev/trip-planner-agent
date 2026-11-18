import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { api } from './lib/api'
import { getSession, signIn, signOut, signUp, userFromSession } from './lib/auth'

const AuthContext = createContext(null)
export const useAuth = () => useContext(AuthContext)

export function AuthProvider({ children }) {
  const [state, setState] = useState({ status: 'loading', user: null })

  const adopt = useCallback((session) => {
    const user = userFromSession(session)
    setState({ status: 'authed', user })
    // Guarda el correo en el perfil (el access token no lo trae); no bloquea el acceso si falla.
    api.updateMe({ email: user.email }).catch(() => {})
  }, [])

  useEffect(() => {
    getSession().then((session) => (session ? adopt(session) : setState({ status: 'anon', user: null })))
  }, [adopt])

  const value = useMemo(
    () => ({
      ...state,
      async login(email, password) {
        adopt(await signIn(email, password))
      },
      async register(email, password) {
        await signUp(email, password)
        adopt(await signIn(email, password))
      },
      logout() {
        signOut()
        setState({ status: 'anon', user: null })
      },
    }),
    [state, adopt],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
