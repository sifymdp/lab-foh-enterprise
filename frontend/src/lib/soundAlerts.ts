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
 * Play a crisp, realistic restaurant service bell ding-ding for waiter calls and cash payment requests.
 */
export function playWaiterBell(): void {
  try {
    const ctx = getAudioContext()
    if (!ctx) return

    const now = ctx.currentTime

    // Two strikes: strike 1 at 0s, strike 2 at 0.16s
    const strikes = [now, now + 0.16]

    strikes.forEach((t) => {
      // Primary chime tone (High pure crystal bell - 1760 Hz / A6)
      const osc1 = ctx.createOscillator()
      const gain1 = ctx.createGain()
      osc1.type = 'sine'
      osc1.frequency.setValueAtTime(1760, t)
      osc1.frequency.exponentialRampToValueAtTime(1750, t + 0.5)

      gain1.gain.setValueAtTime(0.35, t)
      gain1.gain.exponentialRampToValueAtTime(0.001, t + 0.5)

      osc1.connect(gain1)
      gain1.connect(ctx.destination)
      osc1.start(t)
      osc1.stop(t + 0.5)

      // Metallic shimmer overtone (3520 Hz)
      const osc2 = ctx.createOscillator()
      const gain2 = ctx.createGain()
      osc2.type = 'triangle'
      osc2.frequency.setValueAtTime(3520, t)

      gain2.gain.setValueAtTime(0.15, t)
      gain2.gain.exponentialRampToValueAtTime(0.001, t + 0.25)

      osc2.connect(gain2)
      gain2.connect(ctx.destination)
      osc2.start(t)
      osc2.stop(t + 0.25)
    })
  } catch (err) {
    console.warn('[SoundAlert] Waiter bell playback error:', err)
  }
}
