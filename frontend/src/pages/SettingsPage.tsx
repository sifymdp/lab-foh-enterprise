import { useEffect, useState } from 'react'
import { api } from '../api/client'

interface FestivalPreset {
  id: string
  name: string
  percent: number
  icon: string
  active: boolean
}

export function SettingsPage() {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  const [billingSettings, setBillingSettings] = useState({
    currency: 'INR',
    tax_rate: 5.0,
    service_charge_rate: 10.0,
    receipt_header: '',
    receipt_footer: ''
  })

  const [paymentSettings, setPaymentSettings] = useState({
    CASH: true,
    CARD: true,
    UPI: true,
    QR: true,
    ONLINE: true
  })

  const [discountSettings, setDiscountSettings] = useState<{
    cashier_max_discount: number
    manager_max_discount: number
    approval_above_percent: number
    approval_above_amount: number
    active_festival_id: string | null
    festival_presets: FestivalPreset[]
  }>({
    cashier_max_discount: 5.0,
    manager_max_discount: 30.0,
    approval_above_percent: 5.0,
    approval_above_amount: 500.0,
    active_festival_id: 'diwali',
    festival_presets: [
      { id: 'diwali', name: 'Diwali Festival', percent: 15.0, icon: '🪔', active: true },
      { id: 'newyear', name: 'New Year Special', percent: 20.0, icon: '🎉', active: true },
      { id: 'eid', name: 'Eid Mubarak', percent: 15.0, icon: '🌙', active: true },
      { id: 'christmas', name: 'Christmas Special', percent: 20.0, icon: '🎄', active: true },
      { id: 'weekend', name: 'Weekend Happy Hours', percent: 10.0, icon: '⭐', active: true },
      { id: 'anniversary', name: 'Anniversary Discount', percent: 25.0, icon: '🎂', active: true }
    ]
  })

  // State for adding a new festival preset
  const [newFestName, setNewFestName] = useState('')
  const [newFestPercent, setNewFestPercent] = useState('')
  const [newFestIcon, setNewFestIcon] = useState('✨')
  const [showAddPreset, setShowAddPreset] = useState(false)

  useEffect(() => {
    loadSettings()
  }, [])

  const showSuccess = (msg: string) => {
    setSuccessMsg(msg)
    setTimeout(() => setSuccessMsg(null), 4000)
  }

  const loadSettings = async () => {
    setLoading(true)
    setError(null)
    try {
      const [bill, pay, disc] = await Promise.all([
        api.getBillingSettings(),
        api.getPaymentSettings(),
        api.getDiscountSettings()
      ])
      if (bill) setBillingSettings(bill)
      if (pay) setPaymentSettings(pay)
      if (disc) {
        setDiscountSettings({
          cashier_max_discount: Number(disc.cashier_max_discount ?? 5.0),
          manager_max_discount: Number(disc.manager_max_discount ?? 30.0),
          approval_above_percent: Number(disc.approval_above_percent ?? 5.0),
          approval_above_amount: Number(disc.approval_above_amount ?? 500.0),
          active_festival_id: disc.active_festival_id || 'diwali',
          festival_presets: Array.isArray(disc.festival_presets) && disc.festival_presets.length > 0
            ? disc.festival_presets
            : [
              { id: 'diwali', name: 'Diwali Festival', percent: 15.0, icon: '🪔', active: true },
              { id: 'newyear', name: 'New Year Special', percent: 20.0, icon: '🎉', active: true },
              { id: 'eid', name: 'Eid Mubarak', percent: 15.0, icon: '🌙', active: true },
              { id: 'christmas', name: 'Christmas Special', percent: 20.0, icon: '🎄', active: true },
              { id: 'weekend', name: 'Weekend Happy Hours', percent: 10.0, icon: '⭐', active: true },
              { id: 'anniversary', name: 'Anniversary Discount', percent: 25.0, icon: '🎂', active: true }
            ]
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to retrieve settings')
    } finally {
      setLoading(false)
    }
  }

  const handleSaveSettings = async () => {
    try {
      setLoading(true)
      await Promise.all([
        api.updateBillingSettings(billingSettings),
        api.updatePaymentSettings(paymentSettings),
        api.updateDiscountSettings(discountSettings)
      ])
      showSuccess('Settings, festival discount rules, and business thresholds saved successfully')
      loadSettings()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save configuration')
    } finally {
      setLoading(false)
    }
  }

  // Festival Preset Management Helpers
  const handleTogglePreset = (id: string) => {
    setDiscountSettings(prev => ({
      ...prev,
      festival_presets: prev.festival_presets.map(p =>
        p.id === id ? { ...p, active: !p.active } : p
      )
    }))
  }

  const handleUpdatePresetPercent = (id: string, newPct: number) => {
    setDiscountSettings(prev => ({
      ...prev,
      festival_presets: prev.festival_presets.map(p =>
        p.id === id ? { ...p, percent: isNaN(newPct) ? 0 : newPct } : p
      )
    }))
  }

  const handleDeletePreset = (id: string) => {
    setDiscountSettings(prev => ({
      ...prev,
      festival_presets: prev.festival_presets.filter(p => p.id !== id),
      active_festival_id: prev.active_festival_id === id ? null : prev.active_festival_id
    }))
  }

  const handleAddPreset = (e: React.FormEvent) => {
    e.preventDefault()
    if (!newFestName.trim() || !newFestPercent) return
    const pct = parseFloat(newFestPercent)
    if (isNaN(pct) || pct <= 0 || pct > 100) {
      setError('Festival discount percentage must be between 1 and 100%')
      return
    }

    const newId = newFestName.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Date.now()
    const newPreset: FestivalPreset = {
      id: newId,
      name: newFestName.trim(),
      percent: pct,
      icon: newFestIcon || '✨',
      active: true
    }

    setDiscountSettings(prev => ({
      ...prev,
      festival_presets: [...prev.festival_presets, newPreset]
    }))

    setNewFestName('')
    setNewFestPercent('')
    setNewFestIcon('✨')
    setShowAddPreset(false)
  }

  return (
    <div style={{ padding: '1.75rem', maxWidth: '1100px', margin: '0 auto' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <h2 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700 }}>Settings & Business Rules</h2>
          <p className="muted" style={{ margin: '0.35rem 0 0' }}>
            Configure billing parameters, festival discount presets, threshold limits, and active payment terminals
          </p>
        </div>
        <button className="btn btn-primary" onClick={handleSaveSettings} disabled={loading}>
          {loading ? 'Saving…' : 'Save All Settings'}
        </button>
      </div>

      {successMsg && (
        <div style={{ background: 'var(--accent-soft)', color: 'var(--accent)', padding: '0.75rem 1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', fontWeight: 600, marginBottom: '1.5rem' }}>
          ✓ {successMsg}
        </div>
      )}

      {error && (
        <div style={{ background: 'var(--primary-soft)', color: 'var(--primary)', padding: '0.75rem 1rem', borderRadius: 'var(--radius)', border: '1px solid var(--primary)', fontWeight: 600, marginBottom: '1.5rem' }}>
          ⚠ Error: {error}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
        {/* ── Section 1: Festival & Promotional Default Discounts ── */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border)', paddingBottom: '0.75rem', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.5rem' }}>
            <div>
              <h3 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span>🎉</span> Festival & Promotional Discount Presets
              </h3>
              <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.85rem' }}>
                Preset festival discounts allow cashiers and managers to apply verified promo discounts in 1 click during billing while keeping manual discount control.
              </p>
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => setShowAddPreset(!showAddPreset)}
            >
              {showAddPreset ? '✕ Cancel' : '+ Add New Festival'}
            </button>
          </div>

          {/* Add New Preset Form */}
          {showAddPreset && (
            <form onSubmit={handleAddPreset} style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', border: '1px solid var(--border)', marginBottom: '1.25rem' }}>
              <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.95rem' }}>Create New Festival Promo Preset</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr 120px auto', gap: '0.75rem', alignItems: 'center' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Icon</label>
                  <select
                    className="input"
                    value={newFestIcon}
                    onChange={(e) => setNewFestIcon(e.target.value)}
                    style={{ padding: '0.45rem' }}
                  >
                    <option value="🪔">🪔 Diwali</option>
                    <option value="🎉">🎉 Party</option>
                    <option value="🌙">🌙 Moon/Eid</option>
                    <option value="🎄">🎄 Tree</option>
                    <option value="⭐">⭐ Star</option>
                    <option value="🎂">🎂 Cake</option>
                    <option value="🎆">🎆 Firework</option>
                    <option value="🏷️">🏷️ Promo</option>
                    <option value="✨">✨ Sparkle</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Festival / Promo Name</label>
                  <input
                    type="text"
                    className="input"
                    placeholder="e.g. Pongal Celebration, Holi Special..."
                    value={newFestName}
                    onChange={(e) => setNewFestName(e.target.value)}
                    required
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>Discount %</label>
                  <input
                    type="number"
                    step="0.5"
                    min="1"
                    max="100"
                    className="input"
                    placeholder="e.g. 15"
                    value={newFestPercent}
                    onChange={(e) => setNewFestPercent(e.target.value)}
                    required
                  />
                </div>
                <div style={{ alignSelf: 'flex-end' }}>
                  <button type="submit" className="btn btn-primary btn-sm">
                    Add Preset
                  </button>
                </div>
              </div>
            </form>
          )}

          {/* Active Festival Selector */}
          <div style={{ background: 'var(--surface-2)', padding: '1rem', borderRadius: '8px', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div>
              <strong style={{ fontSize: '0.9rem' }}>🌟 Default Active Festival on Checkout:</strong>
              <div className="muted" style={{ fontSize: '0.8rem' }}>Highlights this festival discount automatically for cashier staff</div>
            </div>
            <select
              className="input"
              value={discountSettings.active_festival_id || ''}
              onChange={(e) => setDiscountSettings({ ...discountSettings, active_festival_id: e.target.value || null })}
              style={{ minWidth: '220px', padding: '0.45rem' }}
            >
              <option value="">-- No Default Highlight --</option>
              {discountSettings.festival_presets.filter(p => p.active).map(p => (
                <option key={p.id} value={p.id}>
                  {p.icon} {p.name} ({p.percent}%)
                </option>
              ))}
            </select>
          </div>

          {/* Preset Cards Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
            {discountSettings.festival_presets.map((preset) => {
              const isDefault = discountSettings.active_festival_id === preset.id

              return (
                <div
                  key={preset.id}
                  style={{
                    background: preset.active ? 'var(--surface-2)' : 'var(--bg-elevated)',
                    border: isDefault ? '2px solid var(--primary)' : '1px solid var(--border)',
                    borderRadius: '8px',
                    padding: '1rem',
                    opacity: preset.active ? 1 : 0.6,
                    position: 'relative',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '1.5rem' }}>{preset.icon}</span>
                      <strong style={{ fontSize: '1rem' }}>{preset.name}</strong>
                    </div>
                    {isDefault && (
                      <span style={{ background: 'var(--primary)', color: '#fff', fontSize: '0.7rem', padding: '0.15rem 0.45rem', borderRadius: '4px', fontWeight: 600 }}>
                        DEFAULT
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', marginTop: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                      <span className="muted" style={{ fontSize: '0.85rem' }}>Discount:</span>
                      <input
                        type="number"
                        step="0.5"
                        min="0"
                        max="100"
                        className="input"
                        value={preset.percent}
                        onChange={(e) => handleUpdatePresetPercent(preset.id, parseFloat(e.target.value))}
                        style={{ width: '70px', padding: '0.25rem 0.4rem', textAlign: 'center', fontWeight: 700 }}
                      />
                      <span style={{ fontWeight: 700 }}>%</span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={preset.active}
                          onChange={() => handleTogglePreset(preset.id)}
                        />
                        <span>{preset.active ? 'Enabled' : 'Disabled'}</span>
                      </label>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ color: 'var(--danger)', padding: '0.2rem 0.4rem', fontSize: '0.8rem' }}
                        onClick={() => handleDeletePreset(preset.id)}
                        title="Delete Preset"
                      >
                        🗑
                      </button>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* ── Section 2: Discount Control Thresholds ── */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🛡️</span> Manual Discount Thresholds & Approval Rules
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1.5rem' }}>
            <label className="field">
              <span>Cashier Auto-Discount Limit (%)</span>
              <input
                type="number"
                step="0.5"
                className="input"
                value={discountSettings.cashier_max_discount}
                onChange={(e) => setDiscountSettings({ ...discountSettings, cashier_max_discount: parseFloat(e.target.value) || 0 })}
              />
              <span className="muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>Cashiers can apply up to this % without manager pin</span>
            </label>

            <label className="field">
              <span>Manager Auto-Discount Limit (%)</span>
              <input
                type="number"
                step="0.5"
                className="input"
                value={discountSettings.manager_max_discount}
                onChange={(e) => setDiscountSettings({ ...discountSettings, manager_max_discount: parseFloat(e.target.value) || 0 })}
              />
              <span className="muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>Maximum % a manager can authorize directly</span>
            </label>

            <label className="field">
              <span>Require Manager Approval Above (%)</span>
              <input
                type="number"
                step="0.5"
                className="input"
                value={discountSettings.approval_above_percent}
                onChange={(e) => setDiscountSettings({ ...discountSettings, approval_above_percent: parseFloat(e.target.value) || 0 })}
              />
              <span className="muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>Triggers authorization request if exceeded</span>
            </label>

            <label className="field">
              <span>Require Manager Approval Above Amount (₹)</span>
              <input
                type="number"
                step="10"
                className="input"
                value={discountSettings.approval_above_amount}
                onChange={(e) => setDiscountSettings({ ...discountSettings, approval_above_amount: parseFloat(e.target.value) || 0 })}
              />
              <span className="muted" style={{ fontSize: '0.75rem', marginTop: '0.2rem' }}>High-value discount cash limit</span>
            </label>
          </div>
        </div>

        {/* ── Section 3: Billing & Taxes ── */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🧾</span> General Billing & Taxes
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(230px, 1fr))', gap: '1.5rem', marginBottom: '1.5rem' }}>
            <label className="field">
              <span>Currency Symbol</span>
              <input
                type="text"
                className="input"
                value={billingSettings.currency}
                onChange={(e) => setBillingSettings({ ...billingSettings, currency: e.target.value })}
              />
            </label>
            <label className="field">
              <span>GST / Tax Rate (%)</span>
              <input
                type="number"
                step="0.1"
                className="input"
                value={billingSettings.tax_rate}
                onChange={(e) => setBillingSettings({ ...billingSettings, tax_rate: parseFloat(e.target.value) || 0 })}
              />
            </label>
            <label className="field">
              <span>Service Charge Rate (%)</span>
              <input
                type="number"
                step="0.1"
                className="input"
                value={billingSettings.service_charge_rate}
                onChange={(e) => setBillingSettings({ ...billingSettings, service_charge_rate: parseFloat(e.target.value) || 0 })}
              />
            </label>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
            <label className="field">
              <span>Receipt Header Message</span>
              <input
                type="text"
                className="input"
                value={billingSettings.receipt_header}
                onChange={(e) => setBillingSettings({ ...billingSettings, receipt_header: e.target.value })}
              />
            </label>
            <label className="field">
              <span>Receipt Footer Message</span>
              <input
                type="text"
                className="input"
                value={billingSettings.receipt_footer}
                onChange={(e) => setBillingSettings({ ...billingSettings, receipt_footer: e.target.value })}
              />
            </label>
          </div>
        </div>

        {/* ── Section 4: Enabled Payment Terminals ── */}
        <div style={{ background: 'var(--bg-elevated)', padding: '1.5rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', boxShadow: 'var(--shadow-sm)' }}>
          <h3 style={{ borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>💳</span> Payment Methods & Checkout Terminals
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem' }}>
            {['CASH', 'CARD', 'UPI', 'QR', 'ONLINE'].map((key) => (
              <label key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', background: 'var(--surface-2)', padding: '1rem', borderRadius: 'var(--radius)', border: '1px solid var(--border)', cursor: 'pointer' }}>
                <span style={{ fontWeight: 600, marginBottom: '0.5rem' }}>
                  {key === 'CASH' ? '💵 Cash' : key === 'CARD' ? '💳 Card' : key === 'UPI' ? '📱 UPI' : key === 'QR' ? '📱 QR Code' : '🌐 Online'}
                </span>
                <input
                  type="checkbox"
                  checked={(paymentSettings as any)[key]}
                  onChange={(e) => setPaymentSettings({ ...paymentSettings, [key]: e.target.checked })}
                  style={{ width: '20px', height: '20px' }}
                />
              </label>
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button className="btn btn-primary" onClick={handleSaveSettings} disabled={loading}>
            {loading ? 'Saving…' : 'Save All Settings & Rules'}
          </button>
        </div>
      </div>
    </div>
  )
}
