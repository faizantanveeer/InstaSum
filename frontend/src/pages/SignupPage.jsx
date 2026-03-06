import { useEffect, useState } from 'react'
import { AlertCircle, CheckCircle, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import AuthLayout from '../components/AuthLayout'
import copy from '../copy'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'

export default function SignupPage() {
  const { authenticated, signup } = useAuth()
  const { toast } = useToast()
  const navigate = useNavigate()

  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    document.title = copy.titles.signup
    if (authenticated) {
      navigate('/dashboard', { replace: true })
    }
  }, [authenticated, navigate])

  const validate = () => {
    const next = {}
    if (!email.trim()) next.email = copy.errors.required
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) next.email = copy.errors.invalidEmail
    if (!password.trim()) next.password = copy.errors.required
    if (password.length > 0 && password.length < 8) next.password = copy.errors.passwordTooShort
    if (confirmPassword && confirmPassword !== password) next.confirmPassword = copy.errors.passwordsMismatch
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const onSubmit = async (event) => {
    event.preventDefault()
    if (!validate()) return

    setSubmitting(true)
    try {
      await signup(email.trim(), password, confirmPassword)
      toast(copy.toasts.signupSuccess, 'success')
      navigate('/dashboard', { replace: true })
    } catch (error) {
      const message =
        error.status === 409 ? copy.errors.emailExists
          : error.status === 429 ? copy.errors.rateLimited
            : error.message || copy.errors.genericServer
      toast(message, 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const passwordStrength = !password
    ? ''
    : password.length < 8
      ? copy.auth.signup.passwordStrength.short
      : password.length < 12
        ? copy.auth.signup.passwordStrength.medium
        : copy.auth.signup.passwordStrength.strong

  const passwordsMatch = Boolean(confirmPassword) && confirmPassword === password

  return (
    <AuthLayout
      mode="signup"
      title={copy.auth.signup.title}
      subtitle={copy.auth.signup.subtitle}
      googleLabel={copy.auth.signup.google}
      dividerText={copy.auth.signup.divider}
      switchText={copy.auth.signup.switchText}
      switchAction={copy.auth.signup.switchAction}
      onGoogleClick={() => toast(copy.auth.signup.googleToast, 'info')}
    >
      <form onSubmit={onSubmit} className="auth-form-react">
        <label htmlFor="fullName">{copy.auth.signup.fullNameLabel}</label>
        <input
          id="fullName"
          type="text"
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
          placeholder={copy.auth.signup.fullNamePlaceholder}
        />

        <label htmlFor="email">{copy.auth.signup.emailLabel}</label>
        <input
          id="email"
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder={copy.auth.signup.emailPlaceholder}
        />
        {errors.email && (
          <div className="field-error"><AlertCircle size={14} /> {errors.email}</div>
        )}

        <label htmlFor="password">{copy.auth.signup.passwordLabel}</label>
        <input
          id="password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder={copy.auth.signup.passwordPlaceholder}
        />
        {passwordStrength ? <div className="field-note">{passwordStrength}</div> : null}
        {errors.password && (
          <div className="field-error"><AlertCircle size={14} /> {errors.password}</div>
        )}

        <label htmlFor="confirmPassword">{copy.auth.signup.confirmLabel}</label>
        <input
          id="confirmPassword"
          type="password"
          value={confirmPassword}
          onChange={(event) => setConfirmPassword(event.target.value)}
          placeholder={copy.auth.signup.confirmPlaceholder}
        />
        {passwordsMatch ? (
          <div className="field-note success-only">
            <CheckCircle size={14} />
          </div>
        ) : null}
        {!passwordsMatch && errors.confirmPassword && (
          <div className="field-error"><AlertCircle size={14} /> {errors.confirmPassword}</div>
        )}

        <button type="submit" className="btn-primary auth-submit-btn" disabled={submitting}>
          {submitting ? <Loader2 size={20} className="spin" /> : null}
          <span>{submitting ? copy.auth.signup.submitting : copy.auth.signup.submit}</span>
        </button>
      </form>
    </AuthLayout>
  )
}
