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
  const token = localStorage.getItem('customer_access_token')

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

  const loggedIn = Boolean(
    localStorage.getItem('customer_access_token'),
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
    LOAD FLOOR OR BOOKINGS
  */

  useEffect(() => {
    if (
      loggedIn &&
      location.pathname === '/customer/booking'
    ) {
      request<Floor>('/customer/layout')
        .then((value) => {
          setFloor(normalizeCustomerFloor(value))
        })
        .catch((e) => {
          setError(e.message)
        })
    }

    if (
      loggedIn &&
      location.pathname === '/customer/bookings'
    ) {
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
      <main className="login-page">
        <section className="login-panel">
          <div className="login-form">
            <span className="brand-mark lg">
              FOH
            </span>

            <h1>Reserve your table</h1>

            <p className="muted">
              Sign in with your email or mobile number
              to book directly with the restaurant.
            </p>

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
                    : ''
                }
                value={email}
                onChange={(e) =>
                  setEmail(e.target.value)
                }
              />
            </label>

            {developmentOtp && (
              <p className="form-error">
                Development OTP: {developmentOtp}
              </p>
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
        <section className="panel">
          <h1>Temporary table booking</h1>

          <h2>
            Table{' '}
            {pendingBooking.tableNumber ||
              pendingBooking.tableId}
          </h2>

          <p>
            {formatCustomerBookingTime(
              pendingBooking.reservedFor,
            )}
          </p>

          <p>
            {pendingBooking.partySize} guests
          </p>

          <h2>
            Hold expires in{' '}
            {formatCountdown(secondsLeft)}
          </h2>

          <p className="muted">
            Your table is temporarily reserved.
            Confirm your booking before the timer
            expires.
          </p>

          <button
            className="btn btn-primary"
            onClick={confirmBooking}
            disabled={busy}
          >
            {busy
              ? 'Confirming...'
              : 'Confirm and pay'}
          </button>

          <button
            className="btn btn-secondary"
            onClick={() => {
              setPendingBooking(null)
            }}
            disabled={busy}
          >
            Back to booking
          </button>

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
          <h1>My bookings</h1>

          <button
            className="btn btn-secondary"
            onClick={() =>
              navigate('/customer/booking')
            }
          >
            Book a table
          </button>
        </header>

        {error && (
          <p className="form-error">
            {error}
          </p>
        )}

        {bookings.length === 0 && (
          <section className="panel">
            <p className="muted">
              You do not have any bookings yet.
            </p>
          </section>
        )}

        {bookings.map((booking) => (
          <article
            className="panel"
            key={booking.id}
          >
            <h2>
              Table{' '}
              {booking.tableNumber ||
                booking.tableId}
            </h2>

            <p>
              {formatCustomerBookingTime(
                booking.reservedFor,
              )}{' '}
              · {booking.partySize} guests
            </p>

            <p>
              <strong>
                Booking: {booking.status}
              </strong>
            </p>

            <p>
              Payment:{' '}
              <strong>
                {booking.paymentStatus}
              </strong>
            </p>

            {[
              'PENDING',
              'CONFIRMED',
            ].includes(booking.status) && (
              <button
                className="btn btn-secondary"
                onClick={() =>
                  cancel(booking.id)
                }
                disabled={busy}
              >
                Cancel booking
              </button>
            )}
          </article>
        ))}
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
          <h1>Book a table</h1>

          <p className="muted">
            Choose a time, see the floor, and
            select an available table.
          </p>
        </div>

        <button
          className="btn btn-secondary"
          onClick={() =>
            navigate('/customer/bookings')
          }
        >
          My bookings
        </button>
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