import { ChevronLeft, ChevronRight } from 'lucide-react'
import copy from '../copy'

function buildPageItems(page, totalPages) {
  const pages = []
  const windowSize = 2
  const start = Math.max(1, page - windowSize)
  const end = Math.min(totalPages, page + windowSize)

  if (start > 1) {
    pages.push(1)
    if (start > 2) pages.push('ellipsis-left')
  }

  for (let i = start; i <= end; i += 1) {
    pages.push(i)
  }

  if (end < totalPages) {
    if (end < totalPages - 1) pages.push('ellipsis-right')
    pages.push(totalPages)
  }

  return pages
}

export default function PaginationBar({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pages = buildPageItems(page, totalPages)

  return (
    <nav className="pagination-bar" aria-label={copy.pagination.aria}>
      <button type="button" onClick={() => onPageChange(page - 1)} disabled={page <= 1} aria-label={copy.pagination.previousAria}>
        <ChevronLeft size={18} />
        <span>{copy.pagination.previous}</span>
      </button>

      <div className="page-buttons">
        {pages.map((item) => {
          if (typeof item === 'string') {
            return <span key={item} className="page-ellipsis">{copy.pagination.ellipsis}</span>
          }

          return (
            <button
              type="button"
              key={item}
              className={item === page ? 'active' : ''}
              onClick={() => onPageChange(item)}
            >
              {item}
            </button>
          )
        })}
      </div>

      <button type="button" onClick={() => onPageChange(page + 1)} disabled={page >= totalPages} aria-label={copy.pagination.nextAria}>
        <span>{copy.pagination.next}</span>
        <ChevronRight size={18} />
      </button>
    </nav>
  )
}
