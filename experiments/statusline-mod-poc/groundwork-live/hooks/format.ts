// Pure formatting for the groundwork-live status line: no engine calls, so it is testable on its own.

export type Row = { id: string; type: string; description: string; status: string }

const MAX_SHOWN = 3
const MAX_LABEL = 18

/** Strips control characters (an agent type or description is text we do not control) and shortens. */
export const clean = (s: string, max = MAX_LABEL): string => {
  const t = s.replace(/[\u0000-\u001f\u007f-\u009f]/g, '').trim()
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

export const duration = (ms: number): string => {
  const s = Math.max(0, Math.round(ms / 1000))
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m${String(s % 60).padStart(2, '0')}s`
}

/**
 * One line naming the running subagents with how long each has run, or undefined when none runs.
 * `seen` maps an agent id to when it was first seen running; it is pruned here, so it never grows.
 */
export function line(rows: readonly Row[], now: number, seen: Map<string, number>): string | undefined {
  const live = rows.filter(r => r.status === 'running' || r.status === 'pending')
  for (const id of [...seen.keys()]) if (!live.some(r => r.id === id)) seen.delete(id)
  for (const r of live) if (!seen.has(r.id)) seen.set(r.id, now)
  if (live.length === 0) return undefined
  const shown = live
    .slice(0, MAX_SHOWN)
    .map(r => `${clean(r.type || r.description || 'agent')} ${duration(now - (seen.get(r.id) ?? now))}`)
  const more = live.length > MAX_SHOWN ? ` +${live.length - MAX_SHOWN}` : ''
  return `agents ${live.length}: ${shown.join(' · ')}${more}`
}
