import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

const HOUR = 60 * 60 * 1000
const EVENT = '<side-sessions-event>\nSession "mockup v2" ended its turn: 已出三张图,见 D:/screenshots/x\n</side-sessions-event>'

type Call = { server: string; tool: string; args: Record<string, unknown> }

function engine(on: On, opts: { idleMs: number; tokens: number; title?: string }) {
  const calls: Call[] = []
  const now = 10 * HOUR
  on('clock.now', () => ({ value: now }))
  on('session.id', () => ({ value: 'old-session-id' }))
  on('store.get', () => ({ value: now - opts.idleMs }))
  on('store.set', () => ({ value: undefined }))
  on('store.keys', () => ({ value: [] }))
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: opts.tokens, window: 1_000_000, percent: Math.round(opts.tokens / 10_000) }, rateLimits: [] },
  }))
  on('session.messages', () => ({
    value: [
      { role: 'user', text: '继续做 HUD mockup', toolUses: [] },
      { role: 'assistant', text: 'HANDOVER:三张图已出,下一步是贴进 Sheet。', toolUses: [] },
    ],
  }))
  on('session.append', (_, e, next) => next(e))
  on('ui.toast', () => ({ value: undefined }))
  on('mcp.call', (_, e) => {
    const c = e as unknown as Call
    calls.push({ server: c.server, tool: c.tool, args: c.args })
    if (c.tool === 'get_session') {
      return { value: { isError: false, content: [{ type: 'text', text: JSON.stringify({ sessionId: 'old-session-id', title: opts.title ?? '修HUD_🗡️ 翼德已就位 · 2026-10-27' }) }] } }
    }
    if (c.tool === 'start_session') {
      return { value: { isError: false, content: [{ type: 'text', text: 'Started session local_11111111-2222-3333-4444-555555555555 (name relay-x)' }] } }
    }
    return { value: { isError: false, content: [{ type: 'text', text: 'ok' }] } }
  })
  on('prompt.submit', (_, e) => ({ text: e.text }))
  return calls
}

test('a cold session relays an automated event into a fresh continuation and drops it', async ($, on) => {
  const calls = engine(on, { idleMs: 2 * HOUR, tokens: 434_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: { kind: 'unclassified' } })

  expect(r.drop).toContain('session-relay')
  expect(r.drop).toContain('修HUD·续')
  const start = calls.find(c => c.tool === 'start_session')
  expect(start?.server).toBe('ccd_session')
  expect(start?.args.initiation).toBe('user_asked')
  expect(start?.args.context).toBe('fresh')
  expect(start?.args.title).toBe('修HUD·续')
  expect(String(start?.args.prompt)).toContain('HANDOVER:三张图已出')
  expect(String(start?.args.prompt)).toContain('已出三张图')
  expect(String(start?.args.background).length).toBeGreaterThan(80)
  const detach = calls.find(c => c.tool === 'detach_session')
  expect(detach?.server).toBe('ccd_session_mgmt')
  expect(detach?.args.session_id).toBe('local_11111111-2222-3333-4444-555555555555')
})

test('a warm session lets the event through untouched', async ($, on) => {
  const calls = engine(on, { idleMs: 5 * 60 * 1000, tokens: 434_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: { kind: 'unclassified' } })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a typed prompt is never relayed, however cold the session', async ($, on) => {
  const calls = engine(on, { idleMs: 3 * HOUR, tokens: 434_000 })

  const r = await $.prompt.submit({ text: '继续', wait: false, origin: { kind: 'composer' } })

  expect(r.text).toBe('继续')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a tiny cold context is not worth a relay', async ($, on) => {
  const calls = engine(on, { idleMs: 3 * HOUR, tokens: 20_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: { kind: 'unclassified' } })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a continuation of a continuation counts up', async ($, on) => {
  const calls = engine(on, { idleMs: 2 * HOUR, tokens: 434_000, title: '修HUD·续_🗡️ 翼德已就位 · 2026-10-27' })

  await $.prompt.submit({ text: EVENT, wait: false, origin: { kind: 'unclassified' } })

  expect(calls.find(c => c.tool === 'start_session')?.args.title).toBe('修HUD·续2')
})
