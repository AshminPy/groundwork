import type { Register } from 'claude-code'
import { line } from './format'

// groundwork-live: ONE optional status line that lists running subagents and how long each has run.
// It is a complement to Groundwork's statusLine, which Claude Code gives no data about subagents.
// Read-only by construction: it hooks no tool call, permission check, prompt or agent spawn
// (nothing here can deny, rewrite or delay anything), and it uses only $.agent.list, $.clock and $.ui.status.
const EVERY_MS = 2000

export const register: Register = on => {
  let timer: { cancel: () => void } | undefined
  let last: string | undefined = '\u0000' // never a real line, so the first tick always writes
  const seen = new Map<string, number>()

  on('session.start', async ($, e, next) => {
    const result = await next(e)
    timer?.cancel()
    timer = $.clock.every(EVERY_MS, async () => {
      const [rows, now] = [await $.agent.list(), await $.clock.now()]
      const text = line(rows, now, seen)
      if (text !== last) {
        last = text
        $.ui.status(text)
      }
    })
    return result
  })

  on('session.end', async ($, e, next) => {
    timer?.cancel()
    $.ui.status(undefined)
    return next(e)
  })
}
