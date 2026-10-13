import React, { useState } from 'react'
import { api } from '../../api/client'
import type { Floor } from '../../types'

interface DigitalTwinSimulationModalProps {
  floor: Floor
  isOpen: boolean
  onClose: () => void
}

export const DigitalTwinSimulationModal: React.FC<DigitalTwinSimulationModalProps> = ({
  floor,
  isOpen,
  onClose,
}) => {
  const [scenarioType, setScenarioType] = useState('CAPACITY_STRESS')
  const [scenarioName, setScenarioName] = useState('Patio Weather Closure')
  const [arrivalSurgePct, setArrivalSurgePct] = useState(25)
  const [staffCount, setStaffCount] = useState(3)
  const [selectedTables, setSelectedTables] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<any | null>(null)

  if (!isOpen) return null

  const handleTableToggle = (tableId: string) => {
    setSelectedTables((prev) =>
      prev.includes(tableId) ? prev.filter((id) => id !== tableId) : [...prev, tableId]
    )
  }

  const handleRunSimulation = async () => {
    setLoading(true)
    try {
      const data = await api.createSimulation({
        floor_id: floor.id,
        name: scenarioName,
        scenario_type: scenarioType,
        assumptions: {
          disabled_table_ids: selectedTables,
          arrival_surge_pct: arrivalSurgePct,
          staff_count: staffCount,
        },
      })
      setResult(data.results)
    } catch (err) {
      console.error('Failed to run simulation', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.75)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem',
      }}
    >
      <div
        style={{
          background: '#0f172a',
          color: '#f8fafc',
          border: '1px solid rgba(168, 85, 247, 0.4)',
          borderRadius: 12,
          maxWidth: 780,
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: '1.5rem',
          boxShadow: '0 20px 50px rgba(0, 0, 0, 0.5)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <span style={{ fontSize: '1.5rem' }}>🧪</span>
            <div>
              <h3 style={{ margin: 0, color: '#c084fc', fontSize: '1.2rem' }}>
                What-If Scenario Simulation Sandbox
              </h3>
              <p style={{ margin: 0, fontSize: '0.8rem', color: '#94a3b8' }}>
                Calibrated mathematical model • Zero writes to live production records
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: '1.25rem', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        {/* Inputs */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: 4 }}>
              Scenario Name
            </label>
            <input
              type="text"
              className="form-input"
              value={scenarioName}
              onChange={(e) => setScenarioName(e.target.value)}
              style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '0.45rem', borderRadius: 6 }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: 4 }}>
              Scenario Type
            </label>
            <select
              value={scenarioType}
              onChange={(e) => setScenarioType(e.target.value)}
              style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '0.45rem', borderRadius: 6 }}
            >
              <option value="SECTION_CLOSURE">Section / Table Closure</option>
              <option value="SURGE_ARRIVAL">Customer Arrival Surge</option>
              <option value="STAFF_BOTTLENECK">Staffing Variation</option>
              <option value="CAPACITY_STRESS">Full Capacity Stress Test</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: 4 }}>
              Arrival Surge (% increase)
            </label>
            <input
              type="number"
              value={arrivalSurgePct}
              onChange={(e) => setArrivalSurgePct(Number(e.target.value))}
              style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '0.45rem', borderRadius: 6 }}
            />
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: 4 }}>
              Available Floor Staff
            </label>
            <input
              type="number"
              value={staffCount}
              onChange={(e) => setStaffCount(Number(e.target.value))}
              style={{ width: '100%', background: '#1e293b', border: '1px solid #334155', color: '#fff', padding: '0.45rem', borderRadius: 6 }}
            />
          </div>
        </div>

        {/* Table Selector */}
        <div style={{ marginBottom: '1.25rem' }}>
          <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: 6 }}>
            Select Tables to Simulate as Unavailable / Closed ({selectedTables.length} selected):
          </label>
          <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', maxHeight: 110, overflowY: 'auto' }}>
            {floor.tables.map((t) => {
              const isSelected = selectedTables.includes(t.id)
              return (
                <button
                  key={t.id}
                  type="button"
                  onClick={() => handleTableToggle(t.id)}
                  style={{
                    padding: '0.25rem 0.6rem',
                    borderRadius: 6,
                    fontSize: '0.78rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: isSelected ? '#ef4444' : '#1e293b',
                    color: isSelected ? '#fff' : '#94a3b8',
                    border: isSelected ? '1px solid #ef4444' : '1px solid #334155',
                  }}
                >
                  Table {t.number}
                </button>
              )
            })}
          </div>
        </div>

        <button
          type="button"
          className="btn btn-primary"
          style={{ width: '100%', background: '#a855f7', fontWeight: 700, padding: '0.65rem' }}
          onClick={handleRunSimulation}
          disabled={loading}
        >
          {loading ? 'Evaluating Model...' : '🚀 Run What-If Simulation'}
        </button>

        {/* Results */}
        {result && (
          <div style={{ marginTop: '1.5rem', background: '#1e293b', padding: '1.25rem', borderRadius: 8, border: '1px solid rgba(168, 85, 247, 0.3)' }}>
            <h4 style={{ margin: '0 0 0.8rem 0', color: '#c084fc', fontSize: '1rem' }}>
              Simulation Outcomes & Projections
            </h4>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.8rem', marginBottom: '1rem' }}>
              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: 6, textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Capacity Loss</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#f87171' }}>
                  {result.simulation.capacity_loss_percent}%
                </div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: 6, textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Est. Peak Wait Time</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fbbf24' }}>
                  {result.simulation.estimated_peak_wait_min} min
                </div>
              </div>

              <div style={{ background: '#0f172a', padding: '0.75rem', borderRadius: 6, textAlign: 'center' }}>
                <div style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Workload Pressure</div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#38bdf8' }}>
                  {result.simulation.workload_pressure_score} / 100
                </div>
              </div>
            </div>

            {result.simulation.recommended_actions?.length > 0 && (
              <div>
                <strong style={{ fontSize: '0.82rem', color: '#f8fafc' }}>Actionable Guidance:</strong>
                <ul style={{ margin: '0.4rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.8rem', color: '#cbd5e1' }}>
                  {result.simulation.recommended_actions.map((act: string, idx: number) => (
                    <li key={idx}>{act}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
