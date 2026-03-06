import copy from '../copy'

export default function BrandLogo({ compact = false, className = '' }) {
  const classes = ['brand-logo', compact ? 'compact' : '', className].filter(Boolean).join(' ')

  return (
    <div className={classes}>
      <span className="brand-mark" aria-hidden="true">
        <span className="brand-mark-frame">
          <span className="brand-mark-core" />
        </span>
        <span className="brand-mark-accent" />
      </span>
      {!compact ? <span className="brand-wordmark">{copy.brand.name}</span> : null}
    </div>
  )
}
