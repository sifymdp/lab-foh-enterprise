import { useState, useEffect } from 'react'
import { voiceReceptionistApi, type VoiceSimulationResponse } from '../../api/extensions'

interface Props {
  isOpen: boolean
  onClose: () => void
}

const PRESET_CALLS = [
  {
    title: 'Alex Morgan — 4 Guests (Booth)',
    text: "Hi there, I'd like to reserve a table for four guests tonight at 7:30 PM under the name Alex Morgan. We'd love a booth if available!",
  },
  {
    title: 'Sarah Connor — 2 Guests (Anniversary)',
    text: "Hello! My name is Sarah Connor. Can I book a romantic table for 2 tomorrow at 8:00 PM? We are celebrating our anniversary.",
  },
  {
    title: 'David Miller — 6 Guests (Family & High Chair)',
    text: "Hi, this is David Miller. I need a table for 6 people tonight at 6:30 PM. We will have a toddler so we need a high chair.",
  },
  {
    title: 'Elena Rostova — 2 Guests (Window)',
    text: "Good afternoon! Could you reserve a table for 2 tonight at 7:00 PM for Elena Rostova? Window seating would be wonderful.",
  },
]

export function VoiceReceptionistModal({ isOpen, onClose }: Props) {
  const [transcript, setTranscript] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [callResult, setCallResult] = useState<VoiceSimulationResponse | null>(null)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const [isListening, setIsListening] = useState(false)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const handleSpeak = (text: string) => {
    if (!('speechSynthesis' in window)) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.pitch = 1.05
    utterance.onstart = () => setIsSpeaking(true)
    utterance.onend = () => setIsSpeaking(false)
    utterance.onerror = () => setIsSpeaking(false)
    window.speechSynthesis.speak(utterance)
  }

  const handleSimulateCall = async (textToUse?: string) => {
    const callText = (textToUse ?? transcript).trim()
    if (!callText) {
      setError('Please type or select a caller query.')
      return
    }

    setLoading(true)
    setError(null)
    setCallResult(null)

    try {
      const res = await voiceReceptionistApi.simulateCall(callText)
      setCallResult(res)
      if (res.voice_response) {
        handleSpeak(res.voice_response)
      }
    } catch (err: any) {
      setError(err.message || 'Call simulation failed')
    } finally {
      setLoading(false)
    }
  }

  const startVoiceRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SpeechRecognition) {
      alert('Speech Recognition is not supported by your browser. Please type your message.')
      return
    }

    try {
      const recognition = new SpeechRecognition()
      recognition.lang = 'en-US'
      recognition.continuous = false
      recognition.interimResults = false

      recognition.onstart = () => setIsListening(true)
      recognition.onend = () => setIsListening(false)
      recognition.onerror = () => setIsListening(false)
      recognition.onresult = (event: any) => {
        const spokenText = event.results[0][0].transcript
        setTranscript(spokenText)
        handleSimulateCall(spokenText)
      }
      recognition.start()
    } catch (e) {
      setIsListening(false)
    }
  }

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(4px)',
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
    >
      <div
        style={{
          backgroundColor: '#fff',
          borderRadius: 20,
          width: '100%',
          maxWidth: 680,
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
          border: '1px solid #e2e8f0',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
            color: '#fff',
            padding: '20px 24px',
            borderTopLeftRadius: 20,
            borderTopRightRadius: 20,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
          }}
        >
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 24 }}>📞</span>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>AI Voice Receptionist Studio</h2>
              <span
                style={{
                  background: 'rgba(34, 197, 94, 0.2)',
                  color: '#4ade80',
                  border: '1px solid rgba(34, 197, 94, 0.4)',
                  fontSize: 11,
                  padding: '2px 8px',
                  borderRadius: 999,
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    backgroundColor: '#22c55e',
                    display: 'inline-block',
                  }}
                />
                Live Line Ready
              </span>
            </div>
            <p style={{ margin: '4px 0 0', fontSize: 12, color: '#94a3b8' }}>
              Simulate telephone table reservations handled automatically by the AI Receptionist.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'rgba(255,255,255,0.1)',
              border: 'none',
              color: '#fff',
              fontSize: 20,
              width: 32,
              height: 32,
              borderRadius: 8,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            ×
          </button>
        </div>

        <div style={{ padding: 24 }}>
          {/* Presets */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 12, fontWeight: 700, color: '#475569', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Quick Caller Presets (1-Click Test)
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 8 }}>
              {PRESET_CALLS.map((preset, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => {
                    setTranscript(preset.text)
                    handleSimulateCall(preset.text)
                  }}
                  style={{
                    textAlign: 'left',
                    background: '#f8fafc',
                    border: '1px solid #e2e8f0',
                    borderRadius: 10,
                    padding: '10px 12px',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = '#0f766e'
                    e.currentTarget.style.background = '#f0fdfa'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = '#e2e8f0'
                    e.currentTarget.style.background = '#f8fafc'
                  }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: '#0f172a' }}>{preset.title}</div>
                  <div style={{ fontSize: 11, color: '#64748b', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    "{preset.text}"
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Caller Transcript Input */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <label style={{ fontSize: 12, fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Caller Speech / Transcript
              </label>
              <button
                type="button"
                onClick={startVoiceRecognition}
                style={{
                  background: isListening ? '#ef4444' : '#f1f5f9',
                  color: isListening ? '#fff' : '#0f172a',
                  border: '1px solid #cbd5e1',
                  borderRadius: 6,
                  padding: '4px 8px',
                  fontSize: 12,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                  fontWeight: 600,
                }}
              >
                <span>{isListening ? '🔴' : '🎙️'}</span>
                {isListening ? 'Listening…' : 'Speak into Mic'}
              </button>
            </div>
            <textarea
              rows={3}
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              placeholder="e.g. 'Hello, I would like to book a table for 4 tonight at 7:30 PM under the name Alex Morgan...'"
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: 10,
                border: '1px solid #cbd5e1',
                fontSize: 13,
                fontFamily: 'inherit',
                boxSizing: 'border-box',
              }}
            />
            <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
              <button
                type="button"
                disabled={loading || !transcript.trim()}
                onClick={() => handleSimulateCall()}
                style={{
                  flex: 1,
                  background: '#0f172a',
                  color: '#fff',
                  border: 'none',
                  borderRadius: 10,
                  padding: '10px 16px',
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  opacity: loading ? 0.7 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                }}
              >
                {loading ? 'Processing Call…' : '📞 Simulate Incoming Phone Call'}
              </button>
            </div>
            {error && (
              <p style={{ margin: '8px 0 0', color: '#dc2626', fontSize: 12, fontWeight: 500 }}>
                {error}
              </p>
            )}
          </div>

          {/* Active Call Conversation Output */}
          {callResult && (
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 14,
                padding: 18,
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#0f172a', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>🎧</span> Call Dialogue &amp; Booking Outcome
                </span>
                <span
                  style={{
                    backgroundColor: callResult.success ? '#dcfce7' : '#fee2e2',
                    color: callResult.success ? '#166534' : '#991b1b',
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '3px 8px',
                    borderRadius: 6,
                  }}
                >
                  {callResult.status}
                </span>
              </div>

              {/* Caller bubble */}
              <div
                style={{
                  background: '#fff',
                  border: '1px solid #e2e8f0',
                  borderRadius: '12px 12px 12px 2px',
                  padding: '10px 14px',
                  marginBottom: 10,
                  fontSize: 13,
                  color: '#334155',
                }}
              >
                <div style={{ fontSize: 11, fontWeight: 700, color: '#64748b', marginBottom: 2 }}>Caller:</div>
                "{callResult.parsed_details.raw_transcript}"
              </div>

              {/* AI bubble */}
              <div
                style={{
                  background: '#042f2e',
                  color: '#f0fdfa',
                  borderRadius: '12px 12px 2px 12px',
                  padding: '12px 16px',
                  marginBottom: 14,
                  fontSize: 13,
                  lineHeight: 1.5,
                  boxShadow: '0 4px 10px rgba(15, 118, 110, 0.15)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#5eead4' }}>🤖 AI Voice Receptionist:</span>
                  <button
                    type="button"
                    onClick={() => handleSpeak(callResult.voice_response)}
                    style={{
                      background: 'rgba(255,255,255,0.15)',
                      border: 'none',
                      color: '#fff',
                      fontSize: 11,
                      padding: '2px 8px',
                      borderRadius: 4,
                      cursor: 'pointer',
                      fontWeight: 600,
                    }}
                  >
                    {isSpeaking ? '🔊 Speaking…' : '▶ Speak Aloud'}
                  </button>
                </div>
                "{callResult.voice_response}"
              </div>

              {/* Extracted Details Pill Grid */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                  gap: 8,
                  fontSize: 12,
                }}
              >
                <div style={{ background: '#fff', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Guest Name</span>
                  <b style={{ color: '#0f172a' }}>{callResult.parsed_details.guest_name}</b>
                </div>
                <div style={{ background: '#fff', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Party Size</span>
                  <b style={{ color: '#0f172a' }}>{callResult.parsed_details.party_size} guests</b>
                </div>
                <div style={{ background: '#fff', padding: '8px 10px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ color: '#64748b', display: 'block', fontSize: 10 }}>Date &amp; Time</span>
                  <b style={{ color: '#0f172a' }}>{callResult.parsed_details.date} @ {callResult.parsed_details.time}</b>
                </div>
                {callResult.table_number && (
                  <div style={{ background: '#ecfdf5', padding: '8px 10px', borderRadius: 8, border: '1px solid #a7f3d0' }}>
                    <span style={{ color: '#065f46', display: 'block', fontSize: 10 }}>Allocated Table</span>
                    <b style={{ color: '#047857' }}>Table {callResult.table_number} ✓</b>
                  </div>
                )}
              </div>

              {callResult.parsed_details.special_requests && (
                <div style={{ marginTop: 8, fontSize: 12, color: '#475569', background: '#fff', padding: '6px 10px', borderRadius: 8, border: '1px solid #e2e8f0' }}>
                  <span style={{ color: '#64748b' }}>Special Requests:</span> <b>{callResult.parsed_details.special_requests}</b>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
