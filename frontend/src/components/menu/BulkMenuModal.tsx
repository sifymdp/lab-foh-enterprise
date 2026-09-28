import { useEffect, useRef, useState } from 'react'
import {
  menuApi,
  type MenuImportDetail,
  type MenuImportItem,
  type MenuImportSummary,
  type MenuVersion,
} from '../../api/extensions'
import { humanizeApiError } from '../../lib/apiErrors'

interface BulkMenuModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
  branchId?: string
}

type TabType = 'IMPORT' | 'HISTORY' | 'VERSIONS'
type FilterType = 'ALL' | 'NEW' | 'UPDATED' | 'UNCHANGED' | 'WARNINGS' | 'ERRORS' | 'MISSING'

export function BulkMenuModal({ isOpen, onClose, onSuccess, branchId }: BulkMenuModalProps) {
  const [activeTab, setActiveTab] = useState<TabType>('IMPORT')

  // Import flow state
  const [step, setStep] = useState<'UPLOAD' | 'ANALYSIS' | 'PREVIEW' | 'SUCCESS'>('UPLOAD')
  const [file, setFile] = useState<File | null>(null)
  const [uploading, setUploading] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [approving, setApproving] = useState(false)
  const [error, setError] = useState('')
  const [activeFilter, setActiveFilter] = useState<FilterType>('ALL')

  // Analysis / Preview data
  const [currentImport, setCurrentImport] = useState<MenuImportSummary | null>(null)
  const [previewData, setPreviewData] = useState<MenuImportDetail | null>(null)
  const [deactivateMissing, setDeactivateMissing] = useState(false)
  const [approvedVersion, setApprovedVersion] = useState<MenuVersion | null>(null)

  // History & Versions data
  const [historyList, setHistoryList] = useState<MenuImportSummary[]>([])
  const [versionsList, setVersionsList] = useState<MenuVersion[]>([])
  const [loadingHistory, setLoadingHistory] = useState(false)
  const [loadingVersions, setLoadingVersions] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  // Load history when tab clicked
  useEffect(() => {
    if (!isOpen) return
    if (activeTab === 'HISTORY') {
      setLoadingHistory(true)
      menuApi
        .listImportHistory()
        .then(setHistoryList)
        .catch((e) => setError(humanizeApiError(e)))
        .finally(() => setLoadingHistory(false))
    } else if (activeTab === 'VERSIONS') {
      setLoadingVersions(true)
      menuApi
        .listVersions()
        .then(setVersionsList)
        .catch((e) => setError(humanizeApiError(e)))
        .finally(() => setLoadingVersions(false))
    }
  }, [activeTab, isOpen])

  if (!isOpen) return null

  // ── Handlers ──

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0]
      if (droppedFile.name.endsWith('.xlsx') || droppedFile.name.endsWith('.xls')) {
        setFile(droppedFile)
        setError('')
      } else {
        setError('Please upload an Excel spreadsheet (.xlsx or .xls)')
      }
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
      setError('')
    }
  }

  const handleUploadAndAnalyze = async () => {
    if (!file) return
    setUploading(true)
    setAnalyzing(true)
    setError('')
    try {
      const summary = await menuApi.uploadExcel(file, branchId)
      setCurrentImport(summary)
      // Fetch full preview
      const preview = await menuApi.getImportPreview(summary.id, 'ALL')
      setPreviewData(preview)
      setStep('PREVIEW')
    } catch (e) {
      setError(humanizeApiError(e))
    } finally {
      setUploading(false)
      setAnalyzing(false)
    }
  }

  const handleFilterChange = async (filter: FilterType) => {
    setActiveFilter(filter)
    if (!currentImport) return
    setError('')
    try {
      const preview = await menuApi.getImportPreview(currentImport.id, filter)
      setPreviewData(preview)
    } catch (e) {
      setError(humanizeApiError(e))
    }
  }

  const handleApprove = async () => {
    if (!currentImport) return
    setApproving(true)
    setError('')
    try {
      const ver = await menuApi.approveImport(currentImport.id, deactivateMissing)
      setApprovedVersion(ver)
      setStep('SUCCESS')
      onSuccess()
    } catch (e) {
      setError(humanizeApiError(e))
    } finally {
      setApproving(false)
    }
  }

  const handleReject = async () => {
    if (!currentImport) return
    if (!confirm('Are you sure you want to reject this import? No changes will be made to your live menu.')) return
    try {
      await menuApi.rejectImport(currentImport.id)
      resetImport()
    } catch (e) {
      setError(humanizeApiError(e))
    }
  }

  const resetImport = () => {
    setStep('UPLOAD')
    setFile(null)
    setCurrentImport(null)
    setPreviewData(null)
    setDeactivateMissing(false)
    setApprovedVersion(null)
    setError('')
    setActiveFilter('ALL')
  }

  // ── Render Helpers ──

  const summary = previewData?.summary || currentImport
  const items = previewData?.items || []
  const missingItems = previewData?.missingItems || []

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(8px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 24,
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !approving && !analyzing) onClose()
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 1100,
          maxHeight: '92vh',
          backgroundColor: '#fff',
          borderRadius: 20,
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.3)',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          border: '1px solid #e2e8f0',
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            padding: '20px 28px',
            borderBottom: '1px solid #f1f5f9',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
            color: '#fff',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 22 }}>📊</span>
              <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0, letterSpacing: '-0.02em' }}>
                Smart Bulk Menu Management
              </h2>
              <span
                style={{
                  fontSize: 11,
                  padding: '3px 8px',
                  backgroundColor: 'rgba(56, 189, 248, 0.2)',
                  color: '#38bdf8',
                  borderRadius: 12,
                  fontWeight: 600,
                  border: '1px solid rgba(56, 189, 248, 0.3)',
                }}
              >
                Excel Engine 2.0
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 13, color: '#94a3b8' }}>
              Add 100+ items, edit prices, detect duplicates & update live floor catalog with zero downtime
            </p>
          </div>

          <button
            onClick={onClose}
            disabled={approving || analyzing}
            style={{
              background: 'rgba(255, 255, 255, 0.1)',
              border: 'none',
              color: '#cbd5e1',
              width: 34,
              height: 34,
              borderRadius: 10,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 18,
              transition: 'all 0.2s',
            }}
          >
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            borderBottom: '1px solid #e2e8f0',
            backgroundColor: '#f8fafc',
            padding: '0 28px',
            gap: 24,
          }}
        >
          <button
            onClick={() => setActiveTab('IMPORT')}
            style={{
              padding: '14px 4px',
              border: 'none',
              background: 'none',
              fontSize: 14,
              fontWeight: activeTab === 'IMPORT' ? 700 : 500,
              color: activeTab === 'IMPORT' ? '#2563eb' : '#64748b',
              borderBottom: activeTab === 'IMPORT' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
            }}
          >
            📥 Import & Validate
          </button>

          <button
            onClick={() => setActiveTab('HISTORY')}
            style={{
              padding: '14px 4px',
              border: 'none',
              background: 'none',
              fontSize: 14,
              fontWeight: activeTab === 'HISTORY' ? 700 : 500,
              color: activeTab === 'HISTORY' ? '#2563eb' : '#64748b',
              borderBottom: activeTab === 'HISTORY' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
            }}
          >
            🕒 Import History
          </button>

          <button
            onClick={() => setActiveTab('VERSIONS')}
            style={{
              padding: '14px 4px',
              border: 'none',
              background: 'none',
              fontSize: 14,
              fontWeight: activeTab === 'VERSIONS' ? 700 : 500,
              color: activeTab === 'VERSIONS' ? '#2563eb' : '#64748b',
              borderBottom: activeTab === 'VERSIONS' ? '3px solid #2563eb' : '3px solid transparent',
              cursor: 'pointer',
            }}
          >
            🏷️ Menu Versions
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div
            style={{
              backgroundColor: '#fef2f2',
              borderLeft: '4px solid #ef4444',
              padding: '12px 20px',
              margin: '16px 28px 0',
              borderRadius: 8,
              fontSize: 13,
              color: '#b91c1c',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>⚠️ {error}</div>
            <button
              onClick={() => setError('')}
              style={{ background: 'none', border: 'none', color: '#b91c1c', cursor: 'pointer', fontWeight: 'bold' }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Main Content Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px 28px' }}>
          {activeTab === 'IMPORT' && (
            <>
              {/* Step 1: Upload Screen */}
              {step === 'UPLOAD' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  {/* Action banner with templates */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
                      gap: 16,
                    }}
                  >
                    <div
                      style={{
                        padding: 18,
                        borderRadius: 14,
                        border: '1px solid #e2e8f0',
                        backgroundColor: '#f8fafc',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, color: '#1e293b' }}>
                          📄 Blank Excel Template
                        </div>
                        <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>
                          Clean schema template with headers & sample dishes
                        </div>
                      </div>
                      <button
                        onClick={() => menuApi.downloadTemplate()}
                        style={{
                          padding: '8px 14px',
                          backgroundColor: '#fff',
                          border: '1px solid #cbd5e1',
                          borderRadius: 8,
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#0f172a',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                        }}
                      >
                        ⬇ Template
                      </button>
                    </div>

                    <div
                      style={{
                        padding: 18,
                        borderRadius: 14,
                        border: '1px solid #e2e8f0',
                        backgroundColor: '#f0fdf4',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 14, color: '#166534' }}>
                          📥 Export Current Live Menu
                        </div>
                        <div style={{ fontSize: 12, color: '#15803d', marginTop: 2 }}>
                          Download active branch items to edit prices & add rows
                        </div>
                      </div>
                      <button
                        onClick={() => menuApi.downloadCurrentMenu(branchId)}
                        style={{
                          padding: '8px 14px',
                          backgroundColor: '#16a34a',
                          border: 'none',
                          borderRadius: 8,
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#fff',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          boxShadow: '0 1px 3px rgba(22, 163, 74, 0.3)',
                        }}
                      >
                        ⬇ Export Menu
                      </button>
                    </div>
                  </div>

                  {/* Dropzone */}
                  <div
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={handleFileDrop}
                    onClick={() => fileInputRef.current?.click()}
                    style={{
                      border: '2px dashed #94a3b8',
                      borderRadius: 18,
                      padding: '48px 24px',
                      textAlign: 'center',
                      backgroundColor: file ? '#f0f9ff' : '#f8fafc',
                      borderColor: file ? '#38bdf8' : '#cbd5e1',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".xlsx,.xls"
                      style={{ display: 'none' }}
                      onChange={handleFileSelect}
                    />

                    <div style={{ fontSize: 48, marginBottom: 12 }}>
                      {file ? '📊' : '☁️'}
                    </div>

                    <div style={{ fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                      {file ? file.name : 'Click to select or drag & drop updated Excel file'}
                    </div>

                    <div style={{ fontSize: 13, color: '#64748b', marginTop: 6 }}>
                      {file
                        ? `${(file.size / 1024).toFixed(1)} KB — Ready to analyze`
                        : 'Supports standard .xlsx or .xls spreadsheets (up to 15MB)'}
                    </div>

                    {file && (
                      <div style={{ marginTop: 16 }}>
                        <span
                          style={{
                            padding: '4px 12px',
                            backgroundColor: '#e0f2fe',
                            color: '#0284c7',
                            borderRadius: 20,
                            fontSize: 12,
                            fontWeight: 600,
                          }}
                        >
                          ✓ File Selected
                        </span>
                      </div>
                    )}
                  </div>

                  {/* Validation Rules Card */}
                  <div
                    style={{
                      padding: 18,
                      backgroundColor: '#f1f5f9',
                      borderRadius: 12,
                      fontSize: 12,
                      color: '#475569',
                      lineHeight: 1.6,
                    }}
                  >
                    <strong>💡 Smart Import Engine Highlights:</strong>
                    <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                      <li>
                        <strong>Item Code</strong> is used as primary matching key. Matching rows will update
                        existing items, new codes will create new items.
                      </li>
                      <li>
                        <strong>Fuzzy Duplicate Detection</strong> warns if a dish name is suspiciously similar to
                        an existing item (e.g. <em>Chicken Biriyani</em> vs <em>Chicken Biryani</em>).
                      </li>
                      <li>
                        <strong>Zero Order Disruption</strong>: Historical orders and bills are 100% preserved. Missing
                        items are never hard-deleted.
                      </li>
                    </ul>
                  </div>

                  {/* Footer Action */}
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                    <button
                      onClick={onClose}
                      style={{
                        padding: '10px 18px',
                        backgroundColor: '#f1f5f9',
                        border: 'none',
                        borderRadius: 10,
                        fontWeight: 600,
                        fontSize: 14,
                        color: '#475569',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleUploadAndAnalyze}
                      disabled={!file || uploading}
                      style={{
                        padding: '10px 22px',
                        backgroundColor: file && !uploading ? '#2563eb' : '#94a3b8',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 10,
                        fontWeight: 600,
                        fontSize: 14,
                        cursor: file && !uploading ? 'pointer' : 'not-allowed',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        boxShadow: '0 2px 8px rgba(37, 99, 235, 0.3)',
                      }}
                    >
                      {uploading ? '⏳ Analyzing Excel...' : '🚀 Analyze & Preview Changes'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 2: Preview & Approval Screen */}
              {step === 'PREVIEW' && summary && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  {/* Analysis Summary Cards */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                      gap: 12,
                    }}
                  >
                    <div style={cardStyle('#f8fafc', '#334155')}>
                      <div style={cardLabelStyle}>Total Rows</div>
                      <div style={cardValueStyle('#0f172a')}>{summary.totalRows}</div>
                    </div>

                    <div style={cardStyle('#ecfdf5', '#059669')}>
                      <div style={cardLabelStyle}>New Items</div>
                      <div style={cardValueStyle('#059669')}>+{summary.newCount}</div>
                    </div>

                    <div style={cardStyle('#eff6ff', '#2563eb')}>
                      <div style={cardLabelStyle}>Updated</div>
                      <div style={cardValueStyle('#2563eb')}>↻ {summary.updatedCount}</div>
                    </div>

                    <div style={cardStyle('#f8fafc', '#64748b')}>
                      <div style={cardLabelStyle}>Unchanged</div>
                      <div style={cardValueStyle('#64748b')}>— {summary.unchangedCount}</div>
                    </div>

                    <div style={cardStyle(summary.warningCount > 0 ? '#fffbeb' : '#f8fafc', '#d97706')}>
                      <div style={cardLabelStyle}>Duplicates / Warn</div>
                      <div style={cardValueStyle(summary.warningCount > 0 ? '#d97706' : '#94a3b8')}>
                        ⚠️ {summary.warningCount}
                      </div>
                    </div>

                    <div style={cardStyle(summary.errorCount > 0 ? '#fef2f2' : '#f8fafc', '#dc2626')}>
                      <div style={cardLabelStyle}>Errors</div>
                      <div style={cardValueStyle(summary.errorCount > 0 ? '#dc2626' : '#94a3b8')}>
                        ✕ {summary.errorCount}
                      </div>
                    </div>

                    <div style={cardStyle('#faf5ff', '#9333ea')}>
                      <div style={cardLabelStyle}>Missing in File</div>
                      <div style={cardValueStyle('#9333ea')}>{summary.deactivatedCount}</div>
                    </div>
                  </div>

                  {/* Filter Pills */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: '#475569', marginRight: 4 }}>
                      Filter rows:
                    </span>
                    {(['ALL', 'NEW', 'UPDATED', 'UNCHANGED', 'WARNINGS', 'ERRORS', 'MISSING'] as FilterType[]).map(
                      (f) => {
                        const active = activeFilter === f
                        return (
                          <button
                            key={f}
                            onClick={() => handleFilterChange(f)}
                            style={{
                              padding: '6px 12px',
                              borderRadius: 20,
                              fontSize: 12,
                              fontWeight: 600,
                              border: active ? '1px solid #2563eb' : '1px solid #e2e8f0',
                              backgroundColor: active ? '#eff6ff' : '#fff',
                              color: active ? '#1d4ed8' : '#64748b',
                              cursor: 'pointer',
                            }}
                          >
                            {f === 'ALL' && `All Rows (${summary.totalRows})`}
                            {f === 'NEW' && `New Items (${summary.newCount})`}
                            {f === 'UPDATED' && `Updated (${summary.updatedCount})`}
                            {f === 'UNCHANGED' && `Unchanged (${summary.unchangedCount})`}
                            {f === 'WARNINGS' && `Duplicates / Warn (${summary.warningCount})`}
                            {f === 'ERRORS' && `Errors (${summary.errorCount})`}
                            {f === 'MISSING' && `Missing in File (${summary.deactivatedCount})`}
                          </button>
                        )
                      }
                    )}

                    {summary.errorCount > 0 && (
                      <button
                        onClick={() => menuApi.downloadErrorReport(summary.id)}
                        style={{
                          marginLeft: 'auto',
                          padding: '6px 12px',
                          borderRadius: 8,
                          fontSize: 12,
                          fontWeight: 600,
                          backgroundColor: '#fee2e2',
                          color: '#b91c1c',
                          border: '1px solid #fca5a5',
                          cursor: 'pointer',
                        }}
                      >
                        ⬇ Download Error Report
                      </button>
                    )}
                  </div>

                  {/* Table View of Rows */}
                  {activeFilter === 'MISSING' ? (
                    /* Missing Items Table */
                    <div
                      style={{
                        border: '1px solid #e2e8f0',
                        borderRadius: 12,
                        overflow: 'hidden',
                        maxHeight: 340,
                        overflowY: 'auto',
                      }}
                    >
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead style={{ backgroundColor: '#f8fafc', position: 'sticky', top: 0, zIndex: 1 }}>
                          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                            <th style={thStyle}>Code</th>
                            <th style={thStyle}>Existing Item Name</th>
                            <th style={thStyle}>Category</th>
                            <th style={thStyle}>Price</th>
                            <th style={thStyle}>Current Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {missingItems.length === 0 ? (
                            <tr>
                              <td colSpan={5} style={{ padding: 24, textAlign: 'center', color: '#94a3b8' }}>
                                No missing items. All current active menu items are present in your Excel.
                              </td>
                            </tr>
                          ) : (
                            missingItems.map((item) => (
                              <tr key={item.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                <td style={tdStyle}>{item.itemCode || '—'}</td>
                                <td style={{ ...tdStyle, fontWeight: 600 }}>{item.name}</td>
                                <td style={tdStyle}>{item.category}</td>
                                <td style={tdStyle}>₹{item.price.toFixed(2)}</td>
                                <td style={tdStyle}>
                                  <span style={badgeStyle('#f1f5f9', '#475569')}>
                                    {item.available ? 'Live (Available)' : 'Sold Out'}
                                  </span>
                                </td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    /* Normal Items Table */
                    <div
                      style={{
                        border: '1px solid #e2e8f0',
                        borderRadius: 12,
                        overflow: 'hidden',
                        maxHeight: 340,
                        overflowY: 'auto',
                      }}
                    >
                      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                        <thead style={{ backgroundColor: '#f8fafc', position: 'sticky', top: 0, zIndex: 1 }}>
                          <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                            <th style={{ ...thStyle, width: 50 }}>Row</th>
                            <th style={{ ...thStyle, width: 90 }}>Code</th>
                            <th style={thStyle}>Item Name</th>
                            <th style={thStyle}>Category</th>
                            <th style={{ ...thStyle, width: 100 }}>Action</th>
                            <th style={thStyle}>Details / Changes</th>
                          </tr>
                        </thead>
                        <tbody>
                          {items.length === 0 ? (
                            <tr>
                              <td colSpan={6} style={{ padding: 24, textAlign: 'center', color: '#94a3b8' }}>
                                No items found matching this filter.
                              </td>
                            </tr>
                          ) : (
                            items.map((row) => (
                              <tr
                                key={row.id}
                                style={{
                                  borderBottom: '1px solid #f1f5f9',
                                  backgroundColor:
                                    row.status === 'ERROR'
                                      ? '#fef2f2'
                                      : row.status === 'WARNING'
                                      ? '#fffbeb'
                                      : '#fff',
                                }}
                              >
                                <td style={{ ...tdStyle, color: '#94a3b8', fontWeight: 600 }}>{row.rowNumber}</td>
                                <td style={{ ...tdStyle, fontWeight: 600 }}>{row.itemCode || '—'}</td>
                                <td style={{ ...tdStyle, fontWeight: 600, color: '#0f172a' }}>{row.itemName}</td>
                                <td style={tdStyle}>{row.category}</td>
                                <td style={tdStyle}>{renderActionBadge(row.action)}</td>
                                <td style={tdStyle}>{renderRowDetails(row)}</td>
                              </tr>
                            ))
                          )}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {/* Deactivation Option for Missing Items */}
                  {summary.deactivatedCount > 0 && (
                    <div
                      style={{
                        padding: 14,
                        backgroundColor: '#faf5ff',
                        borderRadius: 12,
                        border: '1px solid #e9d5ff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 600, fontSize: 13, color: '#6b21a8' }}>
                          📦 {summary.deactivatedCount} existing items are missing from your uploaded Excel
                        </div>
                        <div style={{ fontSize: 12, color: '#7e22ce', marginTop: 2 }}>
                          Choose whether to soft-deactivate them from the live menu. Historical orders remain intact.
                        </div>
                      </div>
                      <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', fontWeight: 600, fontSize: 13 }}>
                        <input
                          type="checkbox"
                          checked={deactivateMissing}
                          onChange={(e) => setDeactivateMissing(e.target.checked)}
                          style={{ width: 16, height: 16, accentColor: '#9333ea' }}
                        />
                        Deactivate missing items
                      </label>
                    </div>
                  )}

                  {/* Approval Warning if Errors Exist */}
                  {summary.errorCount > 0 && (
                    <div
                      style={{
                        padding: 12,
                        backgroundColor: '#fff1f2',
                        borderRadius: 10,
                        border: '1px solid #fecdd3',
                        fontSize: 13,
                        color: '#be123c',
                      }}
                    >
                      ⚠️ <strong>{summary.errorCount} row(s) contain errors.</strong> Error rows cannot be
                      imported. You can download the error report, fix them in Excel, or proceed to import only the valid rows.
                    </div>
                  )}

                  {/* Bottom Action Bar */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingTop: 12,
                      borderTop: '1px solid #f1f5f9',
                    }}
                  >
                    <div style={{ display: 'flex', gap: 10 }}>
                      <button
                        onClick={resetImport}
                        style={{
                          padding: '10px 16px',
                          backgroundColor: '#f1f5f9',
                          border: 'none',
                          borderRadius: 8,
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#475569',
                          cursor: 'pointer',
                        }}
                      >
                        ↺ Upload New File
                      </button>

                      <button
                        onClick={handleReject}
                        style={{
                          padding: '10px 16px',
                          backgroundColor: '#fee2e2',
                          border: 'none',
                          borderRadius: 8,
                          fontSize: 13,
                          fontWeight: 600,
                          color: '#b91c1c',
                          cursor: 'pointer',
                        }}
                      >
                        ✕ Reject & Cancel
                      </button>
                    </div>

                    <button
                      onClick={handleApprove}
                      disabled={approving}
                      style={{
                        padding: '12px 28px',
                        backgroundColor: '#16a34a',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 10,
                        fontWeight: 700,
                        fontSize: 14,
                        cursor: approving ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        boxShadow: '0 4px 12px rgba(22, 163, 74, 0.3)',
                      }}
                    >
                      {approving ? '⏳ Applying to Menu...' : '✓ Approve & Apply to Live Menu'}
                    </button>
                  </div>
                </div>
              )}

              {/* Step 3: Success Screen */}
              {step === 'SUCCESS' && approvedVersion && (
                <div style={{ textAlign: 'center', padding: '40px 20px' }}>
                  <div style={{ fontSize: 60, marginBottom: 16 }}>🎉</div>
                  <h3 style={{ fontSize: 24, fontWeight: 700, color: '#0f172a', margin: 0 }}>
                    Menu Import Completed Successfully!
                  </h3>
                  <p style={{ color: '#64748b', fontSize: 14, marginTop: 8 }}>
                    Your live restaurant menu has been updated atomically. All POS stations, QR table ordering, and KDS
                    screens reflect the changes instantly.
                  </p>

                  <div
                    style={{
                      maxWidth: 480,
                      margin: '24px auto',
                      padding: 20,
                      backgroundColor: '#f8fafc',
                      borderRadius: 14,
                      border: '1px solid #e2e8f0',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                      <span style={{ color: '#64748b', fontSize: 13 }}>Menu Version Release</span>
                      <strong style={{ color: '#2563eb', fontSize: 14 }}>{approvedVersion.versionTag}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ color: '#64748b', fontSize: 13 }}>New Items Added</span>
                      <strong style={{ color: '#16a34a', fontSize: 14 }}>+{approvedVersion.newItemsCount}</strong>
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <span style={{ color: '#64748b', fontSize: 13 }}>Existing Items Updated</span>
                      <strong style={{ color: '#2563eb', fontSize: 14 }}>↻ {approvedVersion.updatedItemsCount}</strong>
                    </div>
                    {approvedVersion.deactivatedItemsCount > 0 && (
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ color: '#64748b', fontSize: 13 }}>Missing Items Deactivated</span>
                        <strong style={{ color: '#9333ea', fontSize: 14 }}>{approvedVersion.deactivatedItemsCount}</strong>
                      </div>
                    )}
                    <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid #e2e8f0', paddingTop: 8 }}>
                      <span style={{ color: '#64748b', fontSize: 13 }}>Total Active Items in Catalog</span>
                      <strong style={{ color: '#0f172a', fontSize: 14 }}>{approvedVersion.totalItems}</strong>
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'center', gap: 12, marginTop: 24 }}>
                    {currentImport && (
                      <button
                        onClick={() => menuApi.downloadImportReport(currentImport.id)}
                        style={{
                          padding: '10px 18px',
                          backgroundColor: '#f1f5f9',
                          border: '1px solid #cbd5e1',
                          borderRadius: 10,
                          fontSize: 14,
                          fontWeight: 600,
                          color: '#334155',
                          cursor: 'pointer',
                        }}
                      >
                        ⬇ Download Full Audit Report
                      </button>
                    )}
                    <button
                      onClick={onClose}
                      style={{
                        padding: '10px 24px',
                        backgroundColor: '#2563eb',
                        color: '#fff',
                        border: 'none',
                        borderRadius: 10,
                        fontSize: 14,
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      View Live Menu
                    </button>
                  </div>
                </div>
              )}
            </>
          )}

          {/* History Tab */}
          {activeTab === 'HISTORY' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                  Menu Excel Import History
                </h3>
                <span style={{ fontSize: 12, color: '#64748b' }}>Last 50 operations</span>
              </div>

              {loadingHistory ? (
                <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>Loading import history...</div>
              ) : historyList.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>No bulk imports recorded yet.</div>
              ) : (
                <div style={{ border: '1px solid #e2e8f0', borderRadius: 12, overflow: 'hidden' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead style={{ backgroundColor: '#f8fafc' }}>
                      <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                        <th style={thStyle}>Date</th>
                        <th style={thStyle}>File Name</th>
                        <th style={thStyle}>Uploaded By</th>
                        <th style={thStyle}>Rows</th>
                        <th style={thStyle}>New / Updated</th>
                        <th style={thStyle}>Status</th>
                        <th style={thStyle}>Report</th>
                      </tr>
                    </thead>
                    <tbody>
                      {historyList.map((rec) => (
                        <tr key={rec.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                          <td style={tdStyle}>{new Date(rec.createdAt).toLocaleString()}</td>
                          <td style={{ ...tdStyle, fontWeight: 600 }}>{rec.fileName}</td>
                          <td style={tdStyle}>{rec.uploadedBy || 'System'}</td>
                          <td style={tdStyle}>{rec.totalRows}</td>
                          <td style={tdStyle}>
                            <span style={{ color: '#16a34a', fontWeight: 600 }}>+{rec.newCount}</span> /{' '}
                            <span style={{ color: '#2563eb', fontWeight: 600 }}>↻ {rec.updatedCount}</span>
                          </td>
                          <td style={tdStyle}>
                            <span
                              style={badgeStyle(
                                rec.status === 'APPROVED' ? '#dcfce7' : rec.status === 'REJECTED' ? '#fee2e2' : '#fef3c7',
                                rec.status === 'APPROVED' ? '#15803d' : rec.status === 'REJECTED' ? '#b91c1c' : '#b45309'
                              )}
                            >
                              {rec.status}
                            </span>
                          </td>
                          <td style={tdStyle}>
                            <button
                              onClick={() => menuApi.downloadImportReport(rec.id)}
                              style={{
                                padding: '4px 10px',
                                fontSize: 12,
                                border: '1px solid #cbd5e1',
                                backgroundColor: '#fff',
                                borderRadius: 6,
                                cursor: 'pointer',
                              }}
                            >
                              ⬇ Report
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}

          {/* Versions Tab */}
          {activeTab === 'VERSIONS' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                  Immutable Menu Release Timeline
                </h3>
                <span style={{ fontSize: 12, color: '#64748b' }}>Version snapshots</span>
              </div>

              {loadingVersions ? (
                <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>Loading versions...</div>
              ) : versionsList.length === 0 ? (
                <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>No menu versions released yet.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  {versionsList.map((ver) => (
                    <div
                      key={ver.id}
                      style={{
                        padding: 16,
                        borderRadius: 12,
                        border: '1px solid #e2e8f0',
                        backgroundColor: '#f8fafc',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <span
                            style={{
                              padding: '2px 8px',
                              backgroundColor: '#2563eb',
                              color: '#fff',
                              borderRadius: 6,
                              fontWeight: 700,
                              fontSize: 12,
                            }}
                          >
                            {ver.versionTag}
                          </span>
                          <strong style={{ fontSize: 14, color: '#0f172a' }}>{ver.notes || 'Menu Version Release'}</strong>
                        </div>
                        <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                          Released on {new Date(ver.createdAt).toLocaleString()} by {ver.creatorName || 'Manager'}
                        </div>
                      </div>

                      <div style={{ display: 'flex', gap: 16, textAlign: 'right' }}>
                        <div>
                          <div style={{ fontSize: 11, color: '#64748b' }}>Total Dishes</div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: '#0f172a' }}>{ver.totalItems}</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 11, color: '#64748b' }}>Changes</div>
                          <div style={{ fontSize: 13, fontWeight: 600, color: '#16a34a' }}>
                            +{ver.newItemsCount} / ↻{ver.updatedItemsCount}
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Inline Styles & Render Helpers ──────────────────────────────────────────

const cardStyle = (bg: string, borderColor: string): React.CSSProperties => ({
  padding: '12px 14px',
  backgroundColor: bg,
  borderRadius: 12,
  border: `1px solid ${borderColor}25`,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
})

const cardLabelStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
  color: '#64748b',
}

const cardValueStyle = (color: string): React.CSSProperties => ({
  fontSize: 20,
  fontWeight: 800,
  color,
})

const thStyle: React.CSSProperties = {
  padding: '10px 14px',
  fontSize: 12,
  fontWeight: 700,
  color: '#475569',
}

const tdStyle: React.CSSProperties = {
  padding: '10px 14px',
}

const badgeStyle = (bg: string, color: string): React.CSSProperties => ({
  padding: '3px 8px',
  borderRadius: 12,
  fontSize: 11,
  fontWeight: 700,
  backgroundColor: bg,
  color,
  display: 'inline-block',
})

function renderActionBadge(action: string) {
  switch (action) {
    case 'NEW':
      return <span style={badgeStyle('#dcfce7', '#15803d')}>+ NEW</span>
    case 'UPDATED':
      return <span style={badgeStyle('#dbeafe', '#1e40af')}>↻ UPDATE</span>
    case 'UNCHANGED':
      return <span style={badgeStyle('#f1f5f9', '#64748b')}>— UNCHANGED</span>
    case 'POSSIBLE_DUPLICATE':
      return <span style={badgeStyle('#fef3c7', '#b45309')}>⚠️ DUPLICATE</span>
    case 'ERROR':
      return <span style={badgeStyle('#fee2e2', '#b91c1c')}>✕ ERROR</span>
    default:
      return <span style={badgeStyle('#f1f5f9', '#64748b')}>{action}</span>
  }
}

function renderRowDetails(row: MenuImportItem) {
  if (row.action === 'ERROR') {
    return <span style={{ color: '#dc2626', fontWeight: 600 }}>{row.errorMessage}</span>
  }

  if (row.action === 'POSSIBLE_DUPLICATE') {
    return (
      <div style={{ color: '#d97706', fontSize: 12 }}>
        ⚠️ Matches existing: <strong>{row.similarityMatch}</strong> ({Math.round((row.similarityScore || 0) * 100)}% similarity)
      </div>
    )
  }

  if (row.action === 'UPDATED' && row.oldValues && row.newValues) {
    const diffs: string[] = []
    if (Math.abs(row.newValues.price - row.oldValues.price) > 0.001) {
      diffs.push(`Price: ₹${row.oldValues.price} → ₹${row.newValues.price}`)
    }
    if (row.newValues.category !== row.oldValues.category) {
      diffs.push(`Category: ${row.oldValues.category} → ${row.newValues.category}`)
    }
    if (row.newValues.available !== row.oldValues.available) {
      diffs.push(`Available: ${row.oldValues.available ? 'YES' : 'NO'} → ${row.newValues.available ? 'YES' : 'NO'}`)
    }
    if (row.newValues.name !== row.oldValues.name) {
      diffs.push(`Name: ${row.oldValues.name} → ${row.newValues.name}`)
    }
    return (
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {diffs.map((d, i) => (
          <span key={i} style={{ padding: '2px 6px', backgroundColor: '#eff6ff', color: '#1d4ed8', borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
            {d}
          </span>
        ))}
      </div>
    )
  }

  if (row.action === 'NEW' && row.newValues) {
    return <span style={{ color: '#16a34a' }}>₹{row.newValues.price} — Ready to insert</span>
  }

  return <span style={{ color: '#94a3b8' }}>No changes</span>
}
