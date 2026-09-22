/**
 * Browser-native Web Audio API synthesizer for restaurant alerts.
 * Generates an attention-grabbing warning tone without requiring external audio assets.
 */

let audioCtx: AudioContext | null = null

function getAudioContext(): AudioContext | null {
  if (typeof window === 'undefined') return null
  if (!audioCtx) {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    if (AudioContextClass) {
      audioCtx = new AudioContextClass()
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume().catch(() => {})
  }
  return audioCtx
}

/**
 * Play high-urgency alternating two-tone alarm for walkouts.
 */
export function playWalkoutAlarm(): void {
  try {
    const ctx = getAudioContext()
    if (!ctx) return

    const now = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sawtooth'
    // Two rapid high-pitch beeps: 880Hz -> 660Hz -> 880Hz
    osc.frequency.setValueAtTime(880, now)
    osc.frequency.setValueAtTime(659.25, now + 0.12)
    osc.frequency.setValueAtTime(880, now + 0.24)
    osc.frequency.setValueAtTime(659.25, now + 0.36)

    gain.gain.setValueAtTime(0.3, now)
    gain.gain.exponentialRampToValueAtTime(0.01, now + 0.5)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(now)
    osc.stop(now + 0.5)
  } catch (err) {
    console.warn('[SoundAlert] Audio playback error:', err)
  }
}

/**
 * Play a softer notification chime for regular alerts.
 */
export function playChime(): void {
  try {
    const ctx = getAudioContext()
    if (!ctx) return

    const now = ctx.currentTime
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()

    osc.type = 'sine'
    osc.frequency.setValueAtTime(523.25, now) // C5
    osc.frequency.exponentialRampToValueAtTime(783.99, now + 0.18) // G5

    gain.gain.setValueAtTime(0.2, now)
    gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4)

    osc.connect(gain)
    gain.connect(ctx.destination)

    osc.start(now)
    osc.stop(now + 0.4)
  } catch (err) {
    console.warn('[SoundAlert] Audio playback error:', err)
  }
}
