import React from 'react'

export interface PaginationProps {
  currentPage: number
  totalItems: number
  pageSize: number
  onPageChange: (page: number) => void
  onPageSizeChange?: (size: number) => void
  pageSizeOptions?: number[]
  itemName?: string
  className?: string
  style?: React.CSSProperties
}

export function Pagination({
  currentPage,
  totalItems,
  pageSize,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [10, 25, 50, 100],
  itemName = 'items',
  className = '',
  style = {},
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize))
  const safeCurrentPage = Math.min(Math.max(1, currentPage), totalPages)

  const startItem = totalItems === 0 ? 0 : (safeCurrentPage - 1) * pageSize + 1
  const endItem = Math.min(safeCurrentPage * pageSize, totalItems)

  // Generate page numbers with smart ellipsis
  const getPageNumbers = () => {
    const pages: (number | 'ellipsis')[] = []
    if (totalPages <= 7) {
      for (let i = 1; i <= totalPages; i++) pages.push(i)
    } else {
      pages.push(1)
      if (safeCurrentPage > 3) {
        pages.push('ellipsis')
      }

      const start = Math.max(2, safeCurrentPage - 1)
      const end = Math.min(totalPages - 1, safeCurrentPage + 1)

      for (let i = start; i <= end; i++) {
        pages.push(i)
      }

      if (safeCurrentPage < totalPages - 2) {
        pages.push('ellipsis')
      }
      pages.push(totalPages)
    }
    return pages
  }

  const pageNumbers = getPageNumbers()

  if (totalItems === 0) return null

  return (
    <div
      className={`pagination-container ${className}`}
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: '0.85rem',
        padding: '0.85rem 1rem',
        background: 'var(--surface-2, #f8fafc)',
        border: '1px solid var(--border, #e2e8f0)',
        borderRadius: '10px',
        marginTop: '1rem',
        fontSize: '0.84rem',
        userSelect: 'none',
        ...style,
      }}
    >
      {/* Left: Summary info & Page size selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--text-muted, #64748b)' }}>
          Showing <strong style={{ color: 'var(--text, #0f172a)' }}>{startItem}</strong>–<strong style={{ color: 'var(--text, #0f172a)' }}>{endItem}</strong> of{' '}
          <strong style={{ color: 'var(--text, #0f172a)' }}>{totalItems}</strong> {itemName}
        </span>

        {onPageSizeChange && pageSizeOptions && pageSizeOptions.length > 1 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <label htmlFor="pagination-page-size" style={{ fontSize: '0.78rem', color: 'var(--text-muted, #64748b)' }}>Per page:</label>
            <select
              id="pagination-page-size"
              aria-label="Items per page"
              value={pageSize}
              onChange={(e) => {
                const newSize = Number(e.target.value)
                onPageSizeChange(newSize)
                onPageChange(1)
              }}
              style={{
                padding: '0.25rem 0.5rem',
                borderRadius: '6px',
                border: '1px solid var(--border, #cbd5e1)',
                background: '#ffffff',
                fontSize: '0.8rem',
                color: 'var(--text, #0f172a)',
                cursor: 'pointer',
              }}
            >
              {pageSizeOptions.map((opt) => (
                <option key={opt} value={opt}>
                  {opt}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Right: Page navigation buttons */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', flexWrap: 'wrap' }}>
        {/* First Button */}
        <button
          type="button"
          onClick={() => onPageChange(1)}
          disabled={safeCurrentPage === 1}
          style={{
            padding: '0.3rem 0.6rem',
            borderRadius: '6px',
            border: '1px solid var(--border, #cbd5e1)',
            background: safeCurrentPage === 1 ? 'transparent' : '#ffffff',
            color: safeCurrentPage === 1 ? 'var(--text-muted, #94a3b8)' : 'var(--text, #0f172a)',
            cursor: safeCurrentPage === 1 ? 'not-allowed' : 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
          title="First Page"
        >
          « First
        </button>

        {/* Previous Button */}
        <button
          type="button"
          onClick={() => onPageChange(safeCurrentPage - 1)}
          disabled={safeCurrentPage === 1}
          style={{
            padding: '0.3rem 0.65rem',
            borderRadius: '6px',
            border: '1px solid var(--border, #cbd5e1)',
            background: safeCurrentPage === 1 ? 'transparent' : '#ffffff',
            color: safeCurrentPage === 1 ? 'var(--text-muted, #94a3b8)' : 'var(--text, #0f172a)',
            cursor: safeCurrentPage === 1 ? 'not-allowed' : 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
          title="Previous Page"
        >
          ‹ Prev
        </button>

        {/* Page Number Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          {pageNumbers.map((p, idx) => {
            if (p === 'ellipsis') {
              return (
                <span
                  key={`ellipsis-${idx}`}
                  style={{
                    padding: '0.2rem 0.4rem',
                    color: 'var(--text-muted, #94a3b8)',
                    fontSize: '0.8rem',
                  }}
                >
                  …
                </span>
              )
            }

            const isActive = p === safeCurrentPage
            return (
              <button
                key={p}
                type="button"
                onClick={() => onPageChange(p)}
                style={{
                  minWidth: '30px',
                  height: '30px',
                  padding: '0 0.35rem',
                  borderRadius: '6px',
                  border: isActive ? 'none' : '1px solid var(--border, #cbd5e1)',
                  background: isActive ? 'var(--primary, #2563eb)' : '#ffffff',
                  color: isActive ? '#ffffff' : 'var(--text, #0f172a)',
                  cursor: 'pointer',
                  fontSize: '0.8rem',
                  fontWeight: isActive ? 700 : 500,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: isActive ? '0 1px 3px rgba(37, 99, 235, 0.3)' : 'none',
                }}
              >
                {p}
              </button>
            )
          })}
        </div>

        {/* Next Button */}
        <button
          type="button"
          onClick={() => onPageChange(safeCurrentPage + 1)}
          disabled={safeCurrentPage === totalPages}
          style={{
            padding: '0.3rem 0.65rem',
            borderRadius: '6px',
            border: '1px solid var(--border, #cbd5e1)',
            background: safeCurrentPage === totalPages ? 'transparent' : '#ffffff',
            color: safeCurrentPage === totalPages ? 'var(--text-muted, #94a3b8)' : 'var(--text, #0f172a)',
            cursor: safeCurrentPage === totalPages ? 'not-allowed' : 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
          title="Next Page"
        >
          Next ›
        </button>

        {/* Last Button */}
        <button
          type="button"
          onClick={() => onPageChange(totalPages)}
          disabled={safeCurrentPage === totalPages}
          style={{
            padding: '0.3rem 0.6rem',
            borderRadius: '6px',
            border: '1px solid var(--border, #cbd5e1)',
            background: safeCurrentPage === totalPages ? 'transparent' : '#ffffff',
            color: safeCurrentPage === totalPages ? 'var(--text-muted, #94a3b8)' : 'var(--text, #0f172a)',
            cursor: safeCurrentPage === totalPages ? 'not-allowed' : 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
          }}
          title="Last Page"
        >
          Last »
        </button>
      </div>
    </div>
  )
}
