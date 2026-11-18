import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth-context'
import Layout, { MorePage } from './components/Layout'
import { Loading } from './components/Common'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Chat from './pages/Chat'
import { Flights, Hotels, Weather } from './pages/Search'
import Trips from './pages/Trips'
import TripForm from './pages/TripForm'
import TripDetail from './pages/TripDetail'
import Reservations from './pages/Reservations'
import Wallet from './pages/Wallet'
import Preferences from './pages/Preferences'

function Protected({ children }) {
  const { status } = useAuth()
  if (status === 'loading') return <div style={{ padding: 24 }}><Loading rows={2} /></div>
  return status === 'authed' ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="chat" element={<Chat />} />
        <Route path="flights" element={<Flights />} />
        <Route path="weather" element={<Weather />} />
        <Route path="hotels" element={<Hotels />} />
        <Route path="trips" element={<Trips />} />
        <Route path="trips/new" element={<TripForm />} />
        <Route path="trips/:id" element={<TripDetail />} />
        <Route path="trips/:id/edit" element={<TripForm />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="wallet" element={<Wallet />} />
        <Route path="preferences" element={<Preferences />} />
        <Route path="more" element={<MorePage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
