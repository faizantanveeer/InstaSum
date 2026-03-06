import { useState } from 'react'
import { ArrowUpDown, Check, LayoutGrid, List, Search, SlidersHorizontal } from 'lucide-react'
import copy from '../copy'

export default function GridToolbar({
  keyword,
  onKeywordChange,
  viewMode,
  onViewModeChange,
  sortBy,
  onSortByChange,
  statusFilter,
  onStatusFilterChange,
}) {
  const [filtersOpen, setFiltersOpen] = useState(false)

  const filterOptions = [
    { value: 'all', label: copy.toolbar.filterOptions.all },
    { value: 'processed', label: copy.toolbar.filterOptions.processed },
    { value: 'pending', label: copy.toolbar.filterOptions.pending },
    { value: 'failed', label: copy.toolbar.filterOptions.failed },
  ]

  return (
    <div className="grid-toolbar">
      <div className="toolbar-search">
        <Search size={16} />
        <input
          type="text"
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
          placeholder={copy.toolbar.keywordPlaceholder}
          aria-label={copy.toolbar.keywordAria}
        />
      </div>

      <div className="toolbar-right">
        <div className="view-toggle" role="group" aria-label={copy.toolbar.viewMode}>
          <button
            type="button"
            className={viewMode === 'grid' ? 'active' : ''}
            onClick={() => onViewModeChange('grid')}
            aria-label={copy.toolbar.gridView}
            title={copy.toolbar.gridView}
          >
            <LayoutGrid size={20} />
          </button>
          <button
            type="button"
            className={viewMode === 'list' ? 'active' : ''}
            onClick={() => onViewModeChange('list')}
            aria-label={copy.toolbar.listView}
            title={copy.toolbar.listView}
          >
            <List size={20} />
          </button>
        </div>

        <label className="sort-select">
          <ArrowUpDown size={16} />
          <span className="sort-inline-label">{copy.toolbar.sortLabel}</span>
          <select value={sortBy} onChange={(event) => onSortByChange(event.target.value)} aria-label={copy.toolbar.sortLabel} title={copy.toolbar.sortLabel}>
            <option value="newest">{copy.toolbar.sortOptions.newest}</option>
            <option value="oldest">{copy.toolbar.sortOptions.oldest}</option>
            <option value="likes">{copy.toolbar.sortOptions.likes}</option>
            <option value="views">{copy.toolbar.sortOptions.views}</option>
            <option value="processed">{copy.toolbar.sortOptions.processed}</option>
          </select>
        </label>

        <div className="popover-wrap">
          <button type="button" className="filter-button" onClick={() => setFiltersOpen((value) => !value)}>
            <SlidersHorizontal size={16} />
            <span>{copy.toolbar.filterLabel}</span>
          </button>
          {filtersOpen ? (
            <div className="popover-menu filter-popover">
              <div className="filter-popover-head">{copy.toolbar.filterHeading}</div>
              {filterOptions.map((option) => (
                <button
                  type="button"
                  key={option.value}
                  className={statusFilter === option.value ? 'is-selected' : ''}
                  onClick={() => {
                    onStatusFilterChange(option.value)
                    setFiltersOpen(false)
                  }}
                >
                  <Check size={16} />
                  <span>{option.label}</span>
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  )
}
