import type { On } from 'claude-code'
import { expect, test } from 'claude-code/testing'

import { COMPACT_INSTRUCTIONS, isRetired } from './register'

const HOUR = 60 * 60 * 1000
const EVENT = '<side-sessions-event>\nSession "mockup v2" ended its turn: 已出三张图,见 D:/screenshots/x\n</side-sessions-event>'

type Call = { server: string; tool: string; args: Record<string, unknown> }

type Opts = {
  idleMs: number
  tokens: number
  title?: string
  lastAssistant?: string
  store?: Record<string, unknown>
  sendFails?: boolean
  compactSkips?: boolean
  compactThrowsOnce?: boolean
  lead?: boolean
}
type Compact = { instructions?: string }

function engine(on: On, opts: Opts) {
  const calls: Call[] = []
  const now = 10 * HOUR
  const store: Record<string, unknown> = { 'lastEnd:old-session-id': now - opts.idleMs, ...(opts.store ?? {}) }
  on('clock.now', () => ({ value: now }))
  on('session.id', () => ({ value: 'old-session-id' }))
  on('store.get', (_, e) => ({ value: store[e.key] }))
  on('store.set', (_, e) => {
    store[e.key] = e.value
    return { value: undefined }
  })
  on('store.keys', () => ({ value: Object.keys(store) }))
  on('store.delete', (_, e) => {
    delete store[e.key]
    return { value: undefined }
  })
  const timers: number[] = []
  on('clock.after', (_, e) => {
    timers.push(e.ms)
    return { value: undefined }
  })
  on('session.usage', () => ({
    value: { startedAt: 0, context: { tokens: opts.tokens, window: 1_000_000, percent: Math.round(opts.tokens / 10_000) }, rateLimits: [] },
  }))
  on('session.messages', () => ({
    value: [
      { role: 'user', text: '继续做 HUD mockup', toolUses: [] },
      {
        role: 'assistant',
        text: opts.lastAssistant ?? 'HANDOVER:三张图已出,下一步是贴进 Sheet。',
        toolUses: opts.lead ? [{ tool_use_id: 'tu1', tool: 'mcp__ccd_session__start_session', input: {} }] : [],
      },
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
    if (c.tool === 'send_message' && opts.sendFails) {
      return { value: { isError: true, content: [{ type: 'text', text: 'no such session' }] } }
    }
    return { value: { isError: false, content: [{ type: 'text', text: 'ok' }] } }
  })
  on('prompt.submit', (_, e) => ({ text: e.text }))
  const compacts: Compact[] = []
  on('session.compact', (_, e) => {
    compacts.push({ instructions: e.instructions })
    if (opts.compactThrowsOnce && compacts.length === 1) throw new Error('a turn is running')
    if (opts.compactSkips) return { skip: 'vetoed by test' }
    return { messages: [{ role: 'assistant', text: '压缩摘要:HANDOVER 三张图已出。', toolUses: [] }], tokensBefore: opts.tokens, tokensAfter: 120_000 }
  })
  on('turn.start', (_, e) => ({ turnId: e.turnId }))
  on('turn.complete', (_, e) => ({ text: e.answer }))
  return { calls, store, compacts, timers }
}
const PEER = { kind: 'peer' } as const
const RELAYED = { id: 'local_11111111-2222-3333-4444-555555555555', title: '修HUD·续', at: 10 * HOUR - 30 * 60 * 1000, reason: 'cold-event' }

test('a cold session relays an automated event into a fresh continuation and drops it', async ($, on) => {
  const { calls } = engine(on, { idleMs: 2 * HOUR, tokens: 434_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

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
  const { calls } = engine(on, { idleMs: 5 * 60 * 1000, tokens: 434_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a typed prompt is never relayed, however cold the session', async ($, on) => {
  const { calls } = engine(on, { idleMs: 3 * HOUR, tokens: 434_000 })

  const r = await $.prompt.submit({ text: '继续', wait: false, origin: { kind: 'composer' } })

  expect(r.text).toBe('继续')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a tiny cold context is not worth a relay', async ($, on) => {
  const { calls } = engine(on, { idleMs: 3 * HOUR, tokens: 20_000 })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a continuation of a continuation counts up', async ($, on) => {
  const { calls } = engine(on, { idleMs: 2 * HOUR, tokens: 434_000, title: '修HUD·续_🗡️ 翼德已就位 · 2026-10-27' })

  await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(calls.find(c => c.tool === 'start_session')?.args.title).toBe('修HUD·续2')
})

test('a relay is remembered in the store so later events find it', async ($, on) => {
  const { store } = engine(on, { idleMs: 2 * HOUR, tokens: 434_000 })

  await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  const saved = store['relay:old-session-id'] as { id: string; title: string }
  expect(saved.id).toBe('local_11111111-2222-3333-4444-555555555555')
  expect(saved.title).toBe('修HUD·续')
})

test('a second event to an already-relayed cold session is forwarded, not a second continuation', async ($, on) => {
  const { calls } = engine(on, {
    idleMs: 2 * HOUR,
    tokens: 434_000,
    store: { 'relay:old-session-id': RELAYED },
  })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('已原文转发过去')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
  const fwd = calls.find(c => c.tool === 'send_message')
  expect(fwd?.server).toBe('ccd_session_mgmt')
  expect(fwd?.args.session_id).toBe('local_11111111-2222-3333-4444-555555555555')
  expect(String(fwd?.args.message)).toContain('已出三张图')
})

test('when the earlier continuation is gone, a new one is opened', async ($, on) => {
  const { calls } = engine(on, {
    idleMs: 2 * HOUR,
    tokens: 434_000,
    sendFails: true,
    store: { 'relay:old-session-id': { ...RELAYED, id: 'local_dead' } },
  })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('新开的续篇')
  expect(calls.find(c => c.tool === 'start_session')).toBeDefined()
})

test('a retired lead drops the event without opening anything', async ($, on) => {
  const { calls } = engine(on, {
    idleMs: 2 * HOUR,
    tokens: 474_000,
    lastAssistant: '本会话到此交接(上下文已过 400K)。新 lead 从记忆文件 extraction-beacon-redesign-worksite.md 接手,子会话都已改向它回报。',
  })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('已声明交接 / 退役')
  expect(r.drop).toContain('已出三张图')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
  expect(calls.find(c => c.tool === 'send_message')).toBeUndefined()
})

test('retirement markers must be about this session itself', () => {
  expect(isRetired('本 session 可归档。')).toBe(true)
  expect(isRetired('本会话到此交接(上下文已过 400K)')).toBe(true)
  expect(isRetired('handover 已写进 jungle-planet-worksite.md,收尾。')).toBe(true)
  expect(isRetired('lead 太大了,换新 lead 接手')).toBe(true)
  expect(isRetired('子会话 C 已被接替,D 收口完成;下一步我继续验收 E。')).toBe(false)
  expect(isRetired('HANDOVER:三张图已出,下一步是贴进 Sheet。')).toBe(false)
})

const TURN = { answer: '做完了', durationMs: 1, isAborted: false, turnId: 't1', reason: 'answer' } as const

test('the end of a turn compacts a fat session in place with the keep-list', async ($, on) => {
  const { calls, compacts, store } = engine(on, { idleMs: 60 * 1000, tokens: 434_000 })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(1)
  expect(compacts[0]?.instructions).toBe(COMPACT_INSTRUCTIONS)
  expect(typeof store['compactedAt:old-session-id']).toBe('number')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a slim session is never compacted', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 200_000 })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(0)
})

test('two turn ends within two minutes compact only once', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 434_000, store: { 'compactedAt:old-session-id': 10 * HOUR - 60 * 1000 } })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(0)
})

test('a session still fat minutes after a compaction is compacted again, unattended', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 434_000, store: { 'compactedAt:old-session-id': 10 * HOUR - 10 * 60 * 1000 } })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(1)
})

test('a vetoed compaction neither throws nor stops the next turn end from trying again', async ($, on) => {
  const { compacts, store } = engine(on, { idleMs: 60 * 1000, tokens: 434_000, compactSkips: true })

  await $.turn.complete(TURN)
  await $.turn.complete({ ...TURN, turnId: 't2' })

  expect(compacts.length).toBe(2)
  expect(store['compactedAt:old-session-id']).toBeUndefined()
})

test('a prompt never triggers compaction (the host forbids it there) and still goes through', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 434_000 })

  const r = await $.prompt.submit({ text: '继续', wait: false, origin: { kind: 'composer' } })

  expect(r.text).toBe('继续')
  expect(compacts.length).toBe(0)
})

test('a long turn still running is never judged cold, however long ago the last turn ended', async ($, on) => {
  const { calls } = engine(on, { idleMs: 3 * HOUR, tokens: 434_000, store: { 'running:old-session-id': 10 * HOUR - 90 * 60 * 1000 } })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('a running mark left over for hours is not trusted', async ($, on) => {
  const { calls } = engine(on, { idleMs: 9 * HOUR, tokens: 434_000, store: { 'running:old-session-id': 10 * HOUR - 8 * HOUR } })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('新开的续篇')
  expect(calls.filter(c => c.tool === 'start_session').length).toBe(1)
})

test('the start and end of a turn set and clear the running mark', async ($, on) => {
  const { store } = engine(on, { idleMs: 60 * 1000, tokens: 200_000 })

  await $.turn.start({ text: '继续', turnId: 't1' })
  expect(store['running:old-session-id']).toBe(10 * HOUR)
  await $.turn.complete(TURN)
  expect(store['running:old-session-id']).toBeUndefined()
})

test('three events arriving at once open exactly one continuation and forward the other two', async ($, on) => {
  const { calls } = engine(on, { idleMs: 2 * HOUR, tokens: 434_000 })

  const rs = await Promise.all([
    $.prompt.submit({ text: EVENT + ' A', wait: false, origin: PEER }),
    $.prompt.submit({ text: EVENT + ' B', wait: false, origin: PEER }),
    $.prompt.submit({ text: EVENT + ' C', wait: false, origin: PEER }),
  ])

  expect(calls.filter(c => c.tool === 'start_session').length).toBe(1)
  expect(calls.filter(c => c.tool === 'send_message').length).toBe(2)
  for (const r of rs) expect(r.drop).toContain('session-relay')
})

test('an event arriving while a continuation is being opened is queued, not a second continuation', async ($, on) => {
  const { calls, store } = engine(on, {
    idleMs: 2 * HOUR,
    tokens: 434_000,
    store: { 'relay:old-session-id': { title: '', id: '', at: 10 * HOUR - 30 * 1000, reason: 'pending' }, 'relayQueue:old-session-id': [] },
  })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('排队')
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
  expect((store['relayQueue:old-session-id'] as string[]).length).toBe(1)
})

test('after a relay, an event to the old session is forwarded even when it looks warm', async ($, on) => {
  const { calls } = engine(on, { idleMs: 5 * 60 * 1000, tokens: 434_000, store: { 'relay:old-session-id': RELAYED } })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.drop).toContain('已原文转发过去')
  expect(calls.find(c => c.tool === 'send_message')?.args.session_id).toBe(RELAYED.id)
  expect(calls.find(c => c.tool === 'start_session')).toBeUndefined()
})

test('once the person speaks in the old session again, its events pass through to it', async ($, on) => {
  const { calls } = engine(on, {
    idleMs: 5 * 60 * 1000,
    tokens: 434_000,
    store: { 'relay:old-session-id': RELAYED, 'userAt:old-session-id': 10 * HOUR - 60 * 1000 },
  })

  const r = await $.prompt.submit({ text: EVENT, wait: false, origin: PEER })

  expect(r.text).toBe(EVENT)
  expect(calls.find(c => c.tool === 'send_message')).toBeUndefined()
})

test('a typed prompt records that the person is here', async ($, on) => {
  const { store } = engine(on, { idleMs: 3 * HOUR, tokens: 434_000 })

  await $.prompt.submit({ text: '继续', wait: false, origin: { kind: 'composer' } })

  expect(store['userAt:old-session-id']).toBe(10 * HOUR)
})

test('a compaction refused at the turn end is retried a few seconds later', async ($, on) => {
  const { compacts, timers } = engine(on, { idleMs: 60 * 1000, tokens: 434_000, compactThrowsOnce: true })

  await $.turn.complete(TURN)

  expect(compacts.length).toBeGreaterThanOrEqual(1)
  expect(timers).toContain(5000)
})

test('a lead (it started side sessions) is compacted in place from 200K', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 230_000, lead: true })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(1)
})

test('an ordinary session at 230K is left alone', async ($, on) => {
  const { compacts } = engine(on, { idleMs: 60 * 1000, tokens: 230_000 })

  await $.turn.complete(TURN)

  expect(compacts.length).toBe(0)
})
