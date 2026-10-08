import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { api } from '../api/client'
import { useSocket } from './SocketContext'
import type {
  CreateTablePayload,
  DiningSession,
  Floor,
  Table,
  TableStatus,
} from '../types'

interface FloorContextValue {
  floor: Floor | null
  sessions: DiningSession[]
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
  updateTable: (tableId: string, patch: Partial<Table>) => Promise<void>
  changeStatus: (tableId: string, status: TableStatus) => Promise<void>
  seatGuest: (tableId: string, partySize: number, guestName?: string) => Promise<DiningSession>
  closeSession: (sessionId: string) => Promise<void>
  saveFloor: (floor: Floor) => Promise<void>
  addTable: (payload: CreateTablePayload) => Promise<Table>
  deleteTable: (tableId: string) => Promise<void>
  resetFloorLayout: () => Promise<Floor>
}

const FloorContext = createContext<FloorContextValue | null>(null)

export function FloorProvider({ children }: { children: ReactNode }) {
  const [floor, setFloor] = useState<Floor | null>(null)
  const [sessions, setSessions] = useState<DiningSession[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setError(null)
    try {
      const [f, s] = await Promise.all([api.getFloor(), api.getSessions()])
      setFloor(f)
      setSessions(s)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load floor')
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    refresh().finally(() => setLoading(false))
  }, [refresh])

  const { on, joinFloor } = useSocket()

  useEffect(() => {
    if (floor?.id) joinFloor(floor.id)
  }, [floor?.id, joinFloor])

  useEffect(() => {
    const applyTableUpdate = (payload: unknown) => {
      const patch = payload as Partial<Table> & { id: string }
      setFloor((prev) =>
        prev
          ? {
              ...prev,
              tables: prev.tables.map((t) =>
                t.id === patch.id ? { ...t, ...patch, status: (patch.status ?? t.status) as Table['status'] } : t,
              ),
            }
          : prev,
      )
      if (patch.status) {
        setSessions((prev) =>
          prev.map((s) => (s.tableId === patch.id ? { ...s, status: patch.status as Table['status'] } : s)),
        )
      }
    }

    const unsubTable = on('table_updated', applyTableUpdate)
    const unsubTableLegacy = on('table:updated', applyTableUpdate)
    const unsubSession = on('session:created', (payload) => {
      const session = payload as DiningSession
      setSessions((prev) => (prev.some((s) => s.id === session.id) ? prev : [...prev, session]))
    })
    return () => {
      unsubTable()
      unsubTableLegacy()
      unsubSession()
    }
  }, [on])

  const updateTable = useCallback(
    async (tableId: string, patch: Partial<Table>) => {
      const updated = await api.updateTable(tableId, patch)
      setFloor((prev) =>
        prev
          ? { ...prev, tables: prev.tables.map((t) => (t.id === tableId ? updated : t)) }
          : prev,
      )
    },
    [],
  )

  const changeStatus = useCallback(async (tableId: string, status: TableStatus) => {
    const updated = await api.patchTableStatus(tableId, status)
    setFloor((prev) =>
      prev
        ? { ...prev, tables: prev.tables.map((t) => (t.id === tableId ? updated : t)) }
        : prev,
    )
    setSessions((prev) =>
      prev.map((s) => (s.tableId === tableId ? { ...s, status } : s)),
    )
  }, [])

  const seatGuest = useCallback(
    async (tableId: string, partySize: number, guestName?: string) => {
    const session = await api.createSession({ tableId, partySize, guestName })
    setSessions((prev) => [...prev, session])
    setFloor((prev) =>
      prev
        ? {
            ...prev,
            tables: prev.tables.map((t) =>
              t.id === tableId ? { ...t, status: 'SEATED' as const } : t,
            ),
          }
        : prev,
    )
    return session
  },
  [])

  const closeSession = useCallback(async (sessionId: string) => {
    const session = await api.closeSession(sessionId)
    setSessions((prev) => prev.map((s) => (s.id === sessionId ? session : s)))
    setFloor((prev) =>
      prev
        ? {
            ...prev,
            tables: prev.tables.map((t) =>
              t.id === session.tableId ? { ...t, status: 'CLEANING' as const } : t,
            ),
          }
        : prev,
    )
  }, [])

  const saveFloor = useCallback(async (next: Floor) => {
    const saved = await api.updateFloor(next)
    setFloor(saved)
  }, [])

  const addTable = useCallback(async (payload: CreateTablePayload) => {
    const table = await api.addTable(payload)
    setFloor((prev) => (prev ? { ...prev, tables: [...prev.tables, table] } : prev))
    return table
  }, [])

  const deleteTable = useCallback(async (tableId: string) => {
    await api.deleteTable(tableId)
    setFloor((prev) =>
      prev ? { ...prev, tables: prev.tables.filter((t) => t.id !== tableId) } : prev,
    )
    setSessions((prev) => prev.filter((s) => s.tableId !== tableId))
  }, [])

  const resetFloorLayout = useCallback(async () => {
    const floor = await api.resetFloorLayout()
    setFloor(floor)
    setSessions([])
    return floor
  }, [])

  const value = useMemo(
    () => ({
      floor,
      sessions,
      loading,
      error,
      refresh,
      updateTable,
      changeStatus,
      seatGuest,
      closeSession,
      saveFloor,
      addTable,
      deleteTable,
      resetFloorLayout,
    }),
    [
      floor,
      sessions,
      loading,
      error,
      refresh,
      updateTable,
      changeStatus,
      seatGuest,
      closeSession,
      saveFloor,
      addTable,
      deleteTable,
      resetFloorLayout,
    ],
  )

  return <FloorContext.Provider value={value}>{children}</FloorContext.Provider>
}

export function useFloor() {
  const ctx = useContext(FloorContext)
  if (!ctx) throw new Error('useFloor must be used within FloorProvider')
  return ctx
}
