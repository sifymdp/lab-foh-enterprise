import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import '../styles/customer-booking.css'

import { FloorPlanCanvas } from '../components/floor/FloorPlanCanvas'
import type { CanvasSelection } from '../components/floor/FloorPlanCanvas'
import type { Floor } from '../types'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

type Booking = {
  id: string
  tableId: string
  tableNumber?: string | null
  partySize: number
  reservedFor: string
  status: string
  paymentStatus: string
  expiresAt?: string | null
}

type Availability = {
  available: boolean
  message: string
  best_table?: {
    id: string
    number: string
    capacity: number
  }
  best_time?: string
  availability_score?: number
  available_tables?: Array<{
    id: string
    number: string
    capacity: number
  }>
  unavailable_tables?: Array<{
    id: string
    number: string
    status: 'BOOKED' | 'RESERVED'
  }>
}

function formatCustomerBookingTime(value: string): string {
  const dateValue = new Date(value)

  const year = dateValue.getUTCFullYear()
  const month = dateValue.getUTCMonth() + 1
  const day = dateValue.getUTCDate()

  const hours = dateValue.getUTCHours()
  const minutes = String(dateValue.getUTCMinutes()).padStart(2, '0')

  const period = hours >= 12 ? 'PM' : 'AM'
  const displayHour = hours % 12 || 12

  return `${month}/${day}/${year}, ${displayHour}:${minutes} ${period}`
}

function formatCountdown(totalSeconds: number | null): string {
  if (totalSeconds === null || totalSeconds <= 0) {
    return '00:00'
  }

  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60

  return `${String(minutes).padStart(2, '0')}:${String(
    seconds,
  ).padStart(2, '0')}`
}

function normalizeCustomerFloor(value: Floor): Floor {
  return {
    ...value,

    sections: value.sections.map((section) => {
      const points = (
        section as Floor['sections'][number] & {
          points?: { x: number; y: number }[]
        }
      ).points

      if (!points?.length) {
        return section
      }

      const xs = points.map((point) => point.x)
      const ys = points.map((point) => point.y)

      const x = Math.min(...xs)
      const y = Math.min(...ys)

      return {
        ...section,

        bounds: {
          x,
          y,
          width: Math.max(...xs) - x,
          height: Math.max(...ys) - y,
        },
      }
    }),
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token =
    localStorage.getItem('customer_access_token') ||
    localStorage.getItem('foh_access_token')

  const response = await fetch(`${API}${path}`, {
    ...options,

    headers: {
      'Content-Type': 'application/json',

      ...(token
        ? {
            Authorization: `Bearer ${token}`,
          }
        : {}),

      ...options.headers,
    },
  })

  const body = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new Error(body.detail || 'Request failed')
  }

  return body as T
}

export function AIBookingPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const customerToken = localStorage.getItem('customer_access_token')
  const staffToken = localStorage.getItem('foh_access_token')
  const loggedIn = Boolean(customerToken || staffToken)

  const isLoginPage = location.pathname === '/customer/login'
  const isBookingsList = location.pathname === '/customer/bookings'
  const isBookingView = !isLoginPage && !isBookingsList

  const [customerContact, setCustomerContact] = useState<string>(
    () => localStorage.getItem('customer_contact') || '',
  )

  const [email, setEmail] = useState('')
  const [contactMode, setContactMode] = useState<'email' | 'mobile'>(
    'email',
  )

  const [code, setCode] = useState('')
  const [developmentOtp, setDevelopmentOtp] = useState('')

  const [date, setDate] = useState(
    new Date().toISOString().slice(0, 10),
  )

  const [time, setTime] = useState('19:00')
  const [guests, setGuests] = useState(2)
  const [guestName, setGuestName] = useState('')

  const [result, setResult] = useState<Availability | null>(
    null,
  )

  const [floor, setFloor] = useState<Floor | null>(null)

  const [selection, setSelection] =
    useState<CanvasSelection>(null)

  const [bookings, setBookings] = useState<Booking[]>([])

  const [pendingBooking, setPendingBooking] =
    useState<Booking | null>(null)

  const [secondsLeft, setSecondsLeft] =
    useState<number | null>(null)

  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const emailInputRef = useRef<HTMLInputElement>(null)

  /*
    LOAD FLOOR OR BOOKINGS & INITIAL AVAILABILITY
  */

  useEffect(() => {
    if (loggedIn && isBookingView) {
      request<Floor>('/customer/layout')
        .then((value) => {
          setFloor(normalizeCustomerFloor(value))
        })
        .catch((e) => {
          setError(e.message)
        })

      // Immediately query live availability so interactive tables and AI suggestions load right away
      void checkAvailability(date, time, guests)
    }

    if (loggedIn && isBookingsList) {
      request<Booking[]>('/customer/bookings')
        .then((value) => {
          setBookings(value)
        })
        .catch((e) => {
          setError(e.message)
        })
    }
  }, [location.pathname, loggedIn])

  /*
    TEMPORARY BOOKING COUNTDOWN
  */

  useEffect(() => {
    if (!pendingBooking?.expiresAt) {
      setSecondsLeft(null)
      return
    }

    const updateTimer = () => {
      const expiryTime = new Date(
        pendingBooking.expiresAt!,
      ).getTime()

      const now = Date.now()

      const seconds = Math.max(
        0,
        Math.floor((expiryTime - now) / 1000),
      )

      setSecondsLeft(seconds)

      if (seconds <= 0) {
        setPendingBooking(null)

        setError(
          'Your temporary booking has expired. Please choose a table again.',
        )
      }
    }

    updateTimer()

    const timer = window.setInterval(
      updateTimer,
      1000,
    )

    return () => {
      window.clearInterval(timer)
    }
  }, [pendingBooking])

  /*
    SEND OTP
  */

  const sendOtp = async () => {
    const contact = (
      emailInputRef.current?.value || email
    ).trim()

    const valid =
      contactMode === 'email'
        ? contact.includes('@')
        : /^\+[1-9]\d{7,14}$/.test(
            contact.replace(/[ ()-]/g, ''),
          )

    if (!valid) {
      setError(
        contactMode === 'email'
          ? 'Enter a valid email address.'
          : 'Enter a mobile number with country code, for example +919876543210.',
      )

      return
    }

    setEmail(contact)
    setBusy(true)
    setError('')

    try {
      const response = await request<{
        development_otp?: string
      }>('/customer/auth/request-otp', {
        method: 'POST',

        body: JSON.stringify({
          contact,
        }),
      })

      setDevelopmentOtp(
        response.development_otp ?? '',
      )
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not send code',
      )
    } finally {
      setBusy(false)
    }
  }

  /*
    VERIFY OTP
  */

  const verify = async () => {
    setBusy(true)
    setError('')

    try {
      const response = await request<{
        access_token: string
      }>('/customer/auth/verify-otp', {
        method: 'POST',

        body: JSON.stringify({
          contact: email,
          code,
        }),
      })

      localStorage.setItem(
        'customer_access_token',
        response.access_token,
      )
      localStorage.setItem('customer_contact', email)
      setCustomerContact(email)

      navigate('/customer/booking')
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not verify code',
      )
    } finally {
      setBusy(false)
    }
  }

  const handleLogout = () => {
    localStorage.removeItem('customer_access_token')
    localStorage.removeItem('customer_contact')
    setCustomerContact('')
    navigate('/customer/login')
  }

  /*
    CHECK AVAILABILITY
  */

  const checkAvailability = async (
    requestedDate = date,
    requestedTime = time,
    requestedGuests = guests,
  ) => {
    setBusy(true)
    setError('')

    try {
      const response = await request<Availability>(
        '/customer/availability',
        {
          method: 'POST',

          body: JSON.stringify({
            requested_date: requestedDate,
            requested_time: requestedTime,
            guests: requestedGuests,
          }),
        },
      )

      setResult(response)
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not check availability',
      )
    } finally {
      setBusy(false)
    }
  }

  const search = () => {
    void checkAvailability()
  }

  /*
    FLOOR AVAILABILITY
  */

  const availableIds = new Set(
    result?.available_tables?.map(
      (table) => table.id,
    ) ?? [],
  )

  const unavailableById = new Map(
    result?.unavailable_tables?.map(
      (table) => [table.id, table.status],
    ) ?? [],
  )

  const displayFloor =
    floor && result
      ? {
          ...floor,

          tables: floor.tables.map((table) => ({
            ...table,

            status: (availableIds.has(table.id)
              ? 'AVAILABLE'
              : (unavailableById.get(table.id) as any) ??
                'RESERVED') as import('../types').TableStatus,
          })),
        }
      : floor

  /*
    CREATE TEMPORARY HOLD
  */

  const hold = async (tableId: string) => {
    setBusy(true)
    setError('')

    try {
      const booking = await request<Booking>(
        '/customer/holds',
        {
          method: 'POST',

          body: JSON.stringify({
            requested_date: date,
            requested_time: time,
            guests,
            table_id: tableId,
            guest_name: guestName || email,
          }),
        },
      )

      /*
        IMPORTANT:

        The booking is NOT confirmed here.

        It remains a temporary PENDING booking.
      */

      setPendingBooking(booking)
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not temporarily hold table',
      )
    } finally {
      setBusy(false)
    }
  }

  /*
    CONFIRM / PAY BOOKING

    Currently this calls the existing confirm API.

    Your backend development mode marks payment as PAID.
  */

  const confirmBooking = async () => {
    if (!pendingBooking) {
      return
    }

    setBusy(true)
    setError('')

    try {
      const confirmed = await request<Booking>(
        `/customer/bookings/${pendingBooking.id}/confirm`,
        {
          method: 'POST',
        },
      )

      setBookings((current) => [
        confirmed,
        ...current,
      ])

      setPendingBooking(null)

      navigate('/customer/bookings')
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not confirm booking',
      )
    } finally {
      setBusy(false)
    }
  }

  /*
    CANCEL BOOKING
  */

  const cancel = async (id: string) => {
    setBusy(true)
    setError('')

    try {
      const updated = await request<Booking>(
        `/customer/bookings/${id}/cancel`,
        {
          method: 'POST',
        },
      )

      setBookings((current) =>
        current.map((booking) =>
          booking.id === id
            ? updated
            : booking,
        ),
      )
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'Could not cancel booking',
      )
    } finally {
      setBusy(false)
    }
  }

  /*
    CUSTOMER LOGIN PAGE
  */

  if (
    !loggedIn ||
    location.pathname === '/customer/login'
  ) {
    return (
      <main className="customer-login-page">
        <section className="customer-login-panel">
          <div className="customer-login-card">
            <span className="brand-mark lg">
              FOH
            </span>

            <h1>Reserve your table</h1>

            <p className="muted">
              Sign in with your email or mobile number
              to book directly with the restaurant.
            </p>

            {loggedIn && customerContact && (
              <div
                style={{
                  marginBottom: '1.25rem',
                  padding: '1rem',
                  background: 'rgba(59, 130, 246, 0.12)',
                  border: '1px solid rgba(59, 130, 246, 0.35)',
                  borderRadius: '16px',
                  textAlign: 'center',
                }}
              >
                <p
                  style={{
                    margin: '0 0 0.75rem 0',
                    color: '#93c5fd',
                    fontSize: '0.9rem',
                  }}
                >
                  You are currently signed in as{' '}
                  <strong>{customerContact}</strong>
                </p>
                <div
                  style={{
                    display: 'flex',
                    gap: '10px',
                    justifyContent: 'center',
                  }}
                >
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() =>
                      navigate('/customer/booking')
                    }
                  >
                    Continue to Booking →
                  </button>
                  <button
                    className="btn btn-secondary btn-sm"
                    onClick={handleLogout}
                    style={{ color: '#f87171' }}
                  >
                    Sign Out
                  </button>
                </div>
              </div>
            )}

            <div
              className="contact-switch"
              role="group"
              aria-label="Choose login method"
            >
              <button
                className={`btn btn-sm ${
                  contactMode === 'email'
                    ? 'btn-primary'
                    : 'btn-secondary'
                }`}
                onClick={() => {
                  setContactMode('email')
                  setEmail('')
                  setError('')
                }}
              >
                Email
              </button>

              <button
                className={`btn btn-sm ${
                  contactMode === 'mobile'
                    ? 'btn-primary'
                    : 'btn-secondary'
                }`}
                onClick={() => {
                  setContactMode('mobile')
                  setEmail('')
                  setError('')
                }}
              >
                Mobile
              </button>
            </div>

            <label className="field">
              <span>
                {contactMode === 'email'
                  ? 'Email address'
                  : 'Mobile number'}
              </span>

              <input
                ref={emailInputRef}
                className="input"
                type={
                  contactMode === 'email'
                    ? 'email'
                    : 'tel'
                }
                autoComplete={
                  contactMode === 'email'
                    ? 'email'
                    : 'tel'
                }
                placeholder={
                  contactMode === 'mobile'
                    ? '+91 9876543210'
                    : 'name@example.com'
                }
                value={email}
                onChange={(e) =>
                  setEmail(e.target.value)
                }
              />
            </label>

            {developmentOtp && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  background: 'rgba(34, 197, 94, 0.14)',
                  border: '1px solid rgba(34, 197, 94, 0.4)',
                  borderRadius: '12px',
                  margin: '12px 0',
                }}
              >
                <span
                  style={{
                    color: '#4ade80',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                  }}
                >
                  🔑 Code:{' '}
                  <strong
                    style={{
                      color: '#fff',
                      letterSpacing: '2px',
                      fontSize: '1.05rem',
                      marginLeft: '6px',
                    }}
                  >
                    {developmentOtp}
                  </strong>
                </span>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  style={{
                    padding: '4px 10px',
                    fontSize: '0.75rem',
                  }}
                  onClick={() => setCode(developmentOtp)}
                >
                  Fill Code
                </button>
              </div>
            )}

            <label className="field">
              <span>Verification code</span>

              <input
                className="input"
                inputMode="numeric"
                value={code}
                onChange={(e) =>
                  setCode(e.target.value)
                }
                placeholder="6 digits"
              />
            </label>

            <button
              className="btn btn-secondary btn-block"
              onClick={sendOtp}
              disabled={busy}
            >
              Send code
            </button>

            <button
              className="btn btn-primary btn-block"
              onClick={verify}
              disabled={
                busy ||
                code.length !== 6
              }
            >
              Verify and continue
            </button>

            {error && (
              <p className="form-error">
                {error}
              </p>
            )}

            <div
              style={{
                marginTop: '1.5rem',
                textAlign: 'center',
                fontSize: '0.85rem',
                borderTop: '1px solid rgba(255,255,255,0.08)',
                paddingTop: '1rem',
              }}
            >
              <span style={{ color: '#94a3b8' }}>
                Restaurant Staff?{' '}
              </span>
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                style={{
                  color: '#60a5fa',
                  textDecoration: 'underline',
                  padding: '0 4px',
                  fontWeight: 600,
                }}
                onClick={() => navigate('/login')}
              >
                Sign in to Host Stand →
              </button>
            </div>
          </div>
        </section>
      </main>
    )
  }

  /*
    TEMPORARY BOOKING CONFIRMATION PAGE
  */

  if (pendingBooking) {
    return (
      <main className="customer-page">
        <section className="customer-hold-card">
          <h1 style={{ fontSize: '1.5rem', marginBottom: '0.5rem', color: 'var(--text, #0f172a)' }}>
            Temporary Table Hold
          </h1>
          <p className="muted" style={{ marginBottom: '1.25rem' }}>
            Your table is temporarily reserved. Confirm your booking before the timer expires.
          </p>

          <div
            style={{
              background: 'var(--surface-2, #f8f9fb)',
              border: '1px solid var(--border, #e2e8f0)',
              borderRadius: '12px',
              padding: '1.25rem',
              marginBottom: '1.25rem',
            }}
          >
            <h2 style={{ margin: '0 0 0.5rem 0', fontSize: '1.35rem', color: 'var(--text, #0f172a)' }}>
              Table {pendingBooking.tableNumber || pendingBooking.tableId}
            </h2>
            <p style={{ margin: '0 0 0.25rem 0', color: 'var(--text-muted, #64748b)' }}>
              🕒 {formatCustomerBookingTime(pendingBooking.reservedFor)} · 👥 {pendingBooking.partySize} guests
            </p>
          </div>

          <div className="customer-hold-timer">
            ⏱ Hold expires in {formatCountdown(secondsLeft)}
          </div>

          <div style={{ display: 'flex', gap: '10px', justifyContent: 'center', marginTop: '1.5rem', flexWrap: 'wrap' }}>
            <button
              className="btn btn-primary"
              onClick={confirmBooking}
              disabled={busy}
              style={{ minWidth: '160px' }}
            >
              {busy ? 'Confirming...' : '✓ Confirm Booking'}
            </button>

            <button
              className="btn btn-secondary"
              onClick={() => {
                setPendingBooking(null)
              }}
              disabled={busy}
            >
              Back to Booking
            </button>
          </div>

          {error && (
            <p className="form-error">
              {error}
            </p>
          )}
        </section>
      </main>
    )
  }

  /*
    MY BOOKINGS PAGE
  */

  if (
    location.pathname === '/customer/bookings'
  ) {
    return (
      <main className="customer-page">
        <header>
          <div>
            <h1>📋 My Table Bookings</h1>
            <p className="muted">View your current and previous table reservations.</p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            {customerContact && (
              <span
                style={{
                  fontSize: '0.85rem',
                  color: '#94a3b8',
                  background: 'rgba(255,255,255,0.06)',
                  padding: '6px 12px',
                  borderRadius: '12px',
                }}
              >
                👤 {customerContact}
              </span>
            )}
            <button
              className="btn btn-primary"
              onClick={() =>
                navigate('/customer/booking')
              }
            >
              🍽️ Book a table
            </button>
            <button
              className="btn btn-secondary"
              onClick={handleLogout}
              style={{ color: '#f87171' }}
            >
              Sign Out
            </button>
            {staffToken && (
              <button
                className="btn btn-secondary"
                onClick={() => navigate('/dashboard')}
              >
                ⚡ Host Stand
              </button>
            )}
          </div>
        </header>

        {error && (
          <p className="form-error">
            {error}
          </p>
        )}

        {bookings.length === 0 && (
          <section className="panel" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
            <p className="muted" style={{ fontSize: '1.05rem', marginBottom: '1rem' }}>
              You do not have any table bookings yet.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => navigate('/customer/booking')}
            >
              🍽️ Reserve a Table Now
            </button>
          </section>
        )}

        {bookings.map((booking) => {
          const badgeClass =
            booking.status === 'CONFIRMED'
              ? 'customer-badge--confirmed'
              : booking.status === 'CANCELLED'
              ? 'customer-badge--cancelled'
              : 'customer-badge--pending'

          return (
            <article
              className="customer-booking-card"
              key={booking.id}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '0.4rem' }}>
                  <strong style={{ fontSize: '1.2rem', color: 'var(--text, #0f172a)' }}>
                    Table {booking.tableNumber || booking.tableId}
                  </strong>
                  <span className={`customer-badge ${badgeClass}`}>
                    {booking.status}
                  </span>
                </div>

                <p style={{ color: 'var(--text-muted, #64748b)', margin: '0 0 0.25rem 0' }}>
                  🕒 {formatCustomerBookingTime(booking.reservedFor)} · 👥 {booking.partySize} guests
                </p>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-soft, #94a3b8)', margin: 0 }}>
                  Payment: <strong>{booking.paymentStatus}</strong>
                </p>
              </div>

              {[
                'PENDING',
                'CONFIRMED',
              ].includes(booking.status) && (
                <button
                  className="btn btn-secondary btn-sm"
                  style={{ color: 'var(--danger, #dc2626)', borderColor: 'var(--border-strong, #cbd5e1)' }}
                  onClick={() =>
                    cancel(booking.id)
                  }
                  disabled={busy}
                >
                  Cancel booking
                </button>
              )}
            </article>
          )
        })}
      </main>
    )
  }

  /*
    MAIN CUSTOMER BOOKING PAGE
  */

  return (
    <main className="customer-page">
      <header>
        <div>
          <h1>🍽️ Book a Table</h1>

          <p className="muted">
            Choose a date & time, see live table availability on the floor plan, and
            select an available table.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {customerContact && (
            <span
              style={{
                fontSize: '0.85rem',
                color: '#94a3b8',
                background: 'rgba(255,255,255,0.06)',
                padding: '6px 12px',
                borderRadius: '12px',
              }}
            >
              👤 {customerContact}
            </span>
          )}
          <button
            className="btn btn-secondary"
            onClick={() =>
              navigate('/customer/bookings')
            }
          >
            📋 My bookings
          </button>
          <button
            className="btn btn-secondary"
            onClick={handleLogout}
            style={{ color: '#f87171' }}
          >
            Sign Out
          </button>
          {staffToken && (
            <button
              className="btn btn-primary"
              onClick={() => navigate('/dashboard')}
            >
              ⚡ Host Stand
            </button>
          )}
        </div>
      </header>

      <section className="panel">
        <div className="customer-grid">
          <label className="field">
            <span>Date</span>

            <input
              className="input"
              type="date"
              value={date}
              onChange={(e) => {
                const nextDate =
                  e.target.value

                setDate(nextDate)
                setSelection(null)

                void checkAvailability(
                  nextDate,
                  time,
                  guests,
                )
              }}
            />
          </label>

          <label className="field">
            <span>Time</span>

            <input
              className="input"
              type="time"
              value={time}
              onChange={(e) => {
                const nextTime =
                  e.target.value

                setTime(nextTime)
                setSelection(null)

                void checkAvailability(
                  date,
                  nextTime,
                  guests,
                )
              }}
            />
          </label>

          <label className="field">
            <span>Guests</span>

            <input
              className="input"
              type="number"
              min="1"
              max="50"
              value={guests}
              onChange={(e) => {
                const nextGuests =
                  Number(e.target.value)

                setGuests(nextGuests)
                setSelection(null)

                void checkAvailability(
                  date,
                  time,
                  nextGuests,
                )
              }}
            />
          </label>

          <label className="field">
            <span>Name for booking</span>

            <input
              className="input"
              value={guestName}
              onChange={(e) =>
                setGuestName(e.target.value)
              }
            />
          </label>
        </div>

        <button
          className="btn btn-primary"
          onClick={search}
          disabled={busy}
        >
          {busy
            ? 'Updating tables…'
            : 'Check availability'}
        </button>

        {error && (
          <p className="form-error">
            {error}
          </p>
        )}
      </section>

      {displayFloor && (
        <section className="panel customer-layout">
          <div className="customer-layout__header">
            <div>
              <h2>
                Choose from the floor plan
              </h2>

              <p className="muted">
                {result
                  ? 'Available tables are shown for your selected time.'
                  : 'Check availability to see which tables are free.'}
              </p>
            </div>

            {selection?.type === 'table' &&
              result &&
              availableIds.has(selection.id) && (
                <button
                  className="btn btn-primary btn-sm"
                  onClick={() =>
                    hold(selection.id)
                  }
                  disabled={busy}
                >
                  Choose table
                </button>
              )}
          </div>

          <FloorPlanCanvas
            floor={displayFloor}
            sessions={[]}
            editable={false}
            selection={selection}
            onSelect={setSelection}
            onTableChange={() => undefined}
            onSectionChange={() => undefined}
            onLabelChange={() => undefined}
          />
        </section>
      )}

      {result && (
        <section className="panel">
          <h2>
            {result.available
              ? 'AI recommendation'
              : 'No table is currently available'}
          </h2>

          <p>{result.message}</p>

          {result.best_table && (
            <p>
              Table{' '}
              {result.best_table.number},{' '}
              {result.best_table.capacity} seats
              at {result.best_time}.
              Availability score:{' '}
              {result.availability_score}%
            </p>
          )}

          <div className="customer-options">
            {(result.available_tables ?? []).map(
              (table) => (
                <article
                  className="option"
                  key={table.id}
                >
                  <strong>
                    Table {table.number}
                  </strong>

                  <span>
                    {table.capacity} seats
                  </span>

                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      setSelection({
                        type: 'table',
                        id: table.id,
                      })

                      void hold(table.id)
                    }}
                    disabled={busy}
                  >
                    Choose table
                  </button>
                </article>
              ),
            )}
          </div>
        </section>
      )}
    </main>
  )
}