import { Link } from 'react-router-dom'
import copy from '../copy'
import BrandLogo from './BrandLogo'
import ThemeToggleButton from './ThemeToggleButton'

export default function AuthLayout({
  mode,
  title,
  subtitle,
  googleLabel,
  dividerText,
  switchText,
  switchAction,
  onGoogleClick,
  children,
}) {
  const isLogin = mode === 'login'

  return (
    <div className="auth-page">
      <div className="auth-theme-corner">
        <ThemeToggleButton />
      </div>

      <div className="auth-shell">
        <section className="auth-hero-panel">
          <BrandLogo className="auth-brand-lockup" />

          <div className="auth-hero-copy">
            <span className="auth-kicker">{copy.auth.panel.kicker}</span>
            <h1 className="auth-stacked-headline">
              {copy.auth.panel.tagline.map((line) => (
                <span key={line}>{line}</span>
              ))}
            </h1>
          </div>

          <div className="auth-feature-list auth-stat-list">
            {copy.auth.panel.stats.map((item) => (
              <div className="auth-feature-item auth-stat-item" key={item.label}>
                <div>
                  <strong>{item.value}</strong>
                  <span>{item.label}</span>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="auth-form-panel">
          <div className="auth-form-head">
            <BrandLogo compact className="auth-form-mark" />
            <div>
              <h2>{title}</h2>
              <p>{subtitle}</p>
            </div>
          </div>

          <button type="button" className="auth-social-btn" onClick={onGoogleClick}>
            <span className="auth-social-mark" aria-hidden="true">{copy.auth.googleMark}</span>
            <span>{googleLabel}</span>
            <span className="auth-soon-badge">{copy.auth.soonBadge}</span>
          </button>

          <div className="auth-divider">
            <span>{dividerText}</span>
          </div>

          {children}

          <p className="auth-switch">
            {switchText}{' '}
            <Link to={isLogin ? '/signup' : '/login'}>
              {switchAction}
            </Link>
          </p>
        </section>
      </div>
    </div>
  )
}
