import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import copy from './copy'
import { useAuth } from './contexts/AuthContext'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const SignupPage = lazy(() => import('./pages/SignupPage'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))

function FullscreenLoader() {
  return (
    <div className="fullscreen-center" role="status" aria-label={copy.loading.page}>
      <Loader2 className="spin" size={24} />
    </div>
  )
}

function ProtectedRoute({ children }) {
  const { authenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <FullscreenLoader />
  }

  if (!authenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  }

  return children
}

function RootRedirect() {
  const { authenticated, loading } = useAuth()
  if (loading) return <FullscreenLoader />
  return <Navigate to={authenticated ? '/dashboard' : '/login'} replace />
}

export default function App() {
  return (
    <Suspense fallback={<FullscreenLoader />}>
      <Routes>
        <Route path="/" element={<RootRedirect />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route
          path="/dashboard"
          element={(
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          )}
        />
        <Route
          path="/profile/:username"
          element={(
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          )}
        />
        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </Suspense>
  )
}
