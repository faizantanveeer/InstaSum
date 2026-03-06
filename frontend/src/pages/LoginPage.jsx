import { useEffect, useState } from 'react'
import { AlertCircle, Loader2 } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import copy from '../copy'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

export default function LoginPage() {
  const { authenticated, login } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [keepSignedIn, setKeepSignedIn] = useState(true)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    document.title = copy.titles.login
    if (authenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [authenticated, navigate])

  const validate = () => {
    const next = {}
    if (!email.trim()) next.email = copy.errors.required
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = copy.errors.invalidEmail
    if (!password.trim()) next.password = copy.errors.required
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    if (!validate()) return

    setSubmitting(true)
    try {
      await login(email.trim(), password)
      toast(copy.toasts.loginSuccess, 'success')
      const redirectPath = location.state?.from || '/dashboard'
      navigate(redirectPath, { replace: true })
    } catch (error) {
      const message =
        error.status === 401 ? copy.errors.loginWrong
          : error.status === 429 ? copy.errors.rateLimited
            : error.message || copy.errors.genericServer
      toast(message, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthLayout
      mode="login"
      title={copy.auth.login.title}
      subtitle={copy.auth.login.subtitle}
      googleLabel={copy.auth.login.google}
      dividerText={copy.auth.login.divider}
      switchText={copy.auth.login.switchText}
      switchAction={copy.auth.login.switchAction}
      onGoogleClick={() => toast(copy.auth.login.googleToast, 'info')}
    >
      <form onSubmit={onSubmit} className="auth-form-react">
        <label htmlFor="email">{copy.auth.login.emailLabel}</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={copy.auth.login.emailPlaceholder}
        />
        {errors.email && (
          <div className="field-error"><AlertCircle size={14} /> {errors.email}</div>
        )}

        <label htmlFor="password">{copy.auth.login.passwordLabel}</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={copy.auth.login.passwordPlaceholder}
        />
        {errors.password && (
          <div className="field-error"><AlertCircle size={14} /> {errors.password}</div>
        )}

        <div className="auth-form-row">
          <label className="auth-checkbox">
            <input
              type="checkbox"
              checked={keepSignedIn}
              onChange={(event) => setKeepSignedIn(event.target.checked)}
            />
            <span>{copy.auth.login.rememberMe}</span>
          </label>
          <button
            type="button"
            className="link-btn auth-inline-link"
            onClick={() => toast(copy.auth.login.forgotPasswordToast, 'info')}
          >
            {copy.auth.login.forgotPassword}
          </button>
        </div>

        <button type="submit" className="btn-primary auth-submit-btn" disabled={submitting}>
          {submitting ? <Loader2 size={20} className="spin" /> : null}
          <span>{submitting ? copy.auth.login.submitting : copy.auth.login.submit}</span>
        </button>
      </form>
    </AuthLayout>
  )
}
