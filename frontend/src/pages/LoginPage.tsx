import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

const DEMO_ACCOUNTS = [
  { email: 'owner@gmail.com', password: 'Owner@1234', role: 'Owner' },
  { email: 'manager@gmail.com', password: 'Manager@1234', role: 'Manager' },
  { email: 'host@gmail.com', password: 'Host@1234', role: 'Host' },
  { email: 'cashier@gmail.com', password: 'Cashier@1234', role: 'Cashier' },
  { email: 'waiter@gmail.com', password: 'Waiter@1234', role: 'Waiter' },
  { email: 'chef@gmail.com', password: 'Chef@1234', role: 'Chef' },
]


export function LoginPage() {
  const { user, login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('owner@gmail.com')
  const [password, setPassword] = useState('Owner@1234')
  const [error, setError] = useState<string | null>(
    sessionStorage.getItem('foh_session_expired') ? 'Your session expired. Please log in.' : null,
  )
  const [loading, setLoading] = useState(false)

  if (user) return <Navigate to="/dashboard" replace />

  async function doLogin(targetEmail: string, targetPass: string) {
    setLoading(true)
    setError(null)
    sessionStorage.removeItem('foh_session_expired')
    try {
      await login(targetEmail.trim(), targetPass.trim())
      navigate('/dashboard')
    } catch (err: any) {
      const msg = err?.message || ''
      if (
        msg.includes('Failed to fetch') ||
        msg.includes('NetworkError') ||
        msg.includes('Failed to load') ||
        msg.includes('ECONNREFUSED') ||
        msg.includes('connection refused')
      ) {
        setError('Backend server is not reachable at http://127.0.0.1:8000. Please check server status.')
      } else {
        setError(msg || 'Invalid email or password')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await doLogin(email, password)
  }

  function quickLogin(demoEmail: string, demoPass: string) {
    setEmail(demoEmail)
    setPassword(demoPass)
    doLogin(demoEmail, demoPass)
  }

  return (
    <div className="login-page">
      <div className="login-hero">
        <span className="brand-mark lg">FOH</span>
        <h2>Your host stand, digital</h2>
        <p>
          Visualize the floor in real time, seat guests faster, and keep every table status in
          sync — like leading table management tools built for busy dining rooms.
        </p>
        <ul>
          <li>Live floor plan with color-coded tables</li>
          <li>One-tap seating and status updates</li>
          <li>Shift overview at a glance</li>
        </ul>
      </div>

      <div className="login-panel">
        <div className="login-card">
          <div className="login-brand">
            <span className="brand-mark">FOH</span>
            <h1>Sign in</h1>
            <p>Host stand · Table management</p>
          </div>

          <form onSubmit={handleSubmit} className="login-form">
            <label className="field">
              <span>Email</span>
              <input
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
                required
              />
            </label>
            <label className="field">
              <span>Password</span>
              <input
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            {error && <p className="form-error">{error}</p>}
            <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
              {loading ? 'Signing in…' : 'Continue to Dashboard'}
            </button>
          </form>

          <div className="demo-accounts" style={{ marginTop: '1.5rem' }}>
            <p className="demo-label" style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: '0.5rem' }}>
              Quick Demo Logins
            </p>
            <div className="demo-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.5rem' }}>
              {DEMO_ACCOUNTS.map((a) => (
                <button
                  key={a.email}
                  type="button"
                  className="btn btn-ghost btn-sm"
                  style={{ padding: '0.25rem', minHeight: '32px', fontSize: '0.8rem' }}
                  onClick={() => quickLogin(a.email, a.password)}
                >
                  {a.role}
                </button>
              ))}
            </div>
          </div>

          <div
            style={{
              marginTop: '1.25rem',
              paddingTop: '1rem',
              borderTop: '1px solid var(--border, #e2e8f0)',
              textAlign: 'center',
            }}
          >
            <p
              style={{
                fontSize: '0.825rem',
                color: 'var(--text-muted, #64748b)',
                margin: '0 0 0.5rem 0',
              }}
            >
              Looking to reserve a table as a guest?
            </p>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ width: '100%', fontWeight: 600 }}
              onClick={() => navigate('/customer/booking')}
            >
              🍽️ Open Customer Booking & Login →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
