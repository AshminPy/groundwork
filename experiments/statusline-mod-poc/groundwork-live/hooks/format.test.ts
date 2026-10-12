import { describe, expect, test } from 'claude-code/testing'
import { clean, duration, line } from './format'

const row = (id: string, status: string, type = 'Explore') => ({ id, type, description: 'task', status })

describe('groundwork-live line', () => {
  test('nothing running gives no line', () => {
    expect(line([], 1000, new Map())).toBeUndefined()
    expect(line([row('a', 'completed'), row('b', 'failed'), row('c', 'idle')], 1000, new Map())).toBeUndefined()
  })

  test('one running agent shows its type and elapsed time', () => {
    const seen = new Map<string, number>()
    expect(line([row('a', 'running')], 10_000, seen)).toBe('agents 1: Explore 0s')
    expect(line([row('a', 'running')], 52_000, seen)).toBe('agents 1: Explore 42s')
    expect(line([row('a', 'running')], 135_000, seen)).toBe('agents 1: Explore 2m05s')
  })

  test('shows at most three and counts the rest', () => {
    const rows = ['a', 'b', 'c', 'd', 'e'].map(id => row(id, 'running'))
    expect(line(rows, 0, new Map())).toBe('agents 5: Explore 0s · Explore 0s · Explore 0s +2')
  })

  test('forgets an agent once it stops, so the map does not grow', () => {
    const seen = new Map<string, number>()
    line([row('a', 'running'), row('b', 'running')], 0, seen)
    expect(seen.size).toBe(2)
    line([row('b', 'running')], 5000, seen)
    expect([...seen.keys()]).toEqual(['b'])
    line([], 9000, seen)
    expect(seen.size).toBe(0)
  })

  test('strips control characters and shortens long labels', () => {
    expect(clean('Ex\u001b[31mplore\u0007')).toBe('Ex[31mplore')
    expect(clean('x'.repeat(40))).toBe('x'.repeat(17) + '…')
    expect(line([row('a', 'running', '\u001b]0;pwned\u0007agent')], 0, new Map())).toBe('agents 1: ]0;pwnedagent 0s')
  })

  test('duration never goes negative', () => {
    expect(duration(-5000)).toBe('0s')
    expect(duration(59_400)).toBe('59s')
    expect(duration(60_000)).toBe('1m00s')
  })
})
