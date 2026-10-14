// Admission's offline tests (packet S25 ruling 7), run by `claude plugin test plugin`, which
// runs no model: the host's process, session and log faked.
import { test, expect } from 'claude-code/testing'

// The plugin as installed: hooks.json names one module, session.ts, which carries admission's
// hooks beside the band (2.1.296 loads one module per plugin), so only the process.run calls
// that run `admission record` are counted; the band's `mod start` is answered and left out.

const ARGV = ['agentik-session', 'admission', 'record', '--session', 'sess-1']
const LIMITS = [{ kind: 'five_hour', percentUsed: 41.5, resetsAt: '2026-10-12T14:05:00Z' }]
const SPAWN = { tool_use_id: 'toolu_01', prompt: 'the whole task, never sent', description: 'read the packet',
  subagentType: 'general-purpose', provider: { plugin: 'engine', tier: 'core' }, model: 'opus',
  parentModel: 'claude-opus-5-5', background: false, fork: false }
const USAGE = { input_tokens: 1, output_tokens: 2, cache_read_input_tokens: 3,
  cache_creation_input_tokens: 4, model: 'claude-opus-5-5' }

type Call = { argv: string[], stdin: any, timeoutMs: unknown, raw: any }

// The world beneath the module: `process.run` answers `record` as `mode` says and `admit` as
// `answer` says (packet S26), keeping each call (`calls` the records, `admits` the admits,
// `order` the admits and the stubs' `next` in turn). `hang` names the reads that never answer
// (fix round 1, F2); with any, a short wait (the module's 1 s bound) passes at once, and the
// band's 5 s tick never comes. An `admit` that hangs passes its bound at once (3 s; 6 s
// before fix round 1, F4), and `sleeps` keeps every wait asked.
type Answer = 'admitted' | 'deferred' | 'denied' | 'reject' | 'hang' | 'refused'
const ANSWER_TEXT = 'admission: not started. The five-hour window is at 88% and resets at 14:05.'
const ADMIT = ['agentik-session', 'admission', 'admit', '--session', 'sess-1']
const world = (on: any, mode: 'ok' | 'reject' | 'timeout' | 'refused' = 'ok', hang: string[] = [],
  answer: Answer = 'admitted') => {
  const calls: Call[] = []
  const admits: Call[] = []
  const order: string[] = []
  const logs: string[] = []
  const sleeps: number[] = []
  const never = () => new Promise(() => {})
  on('session.id', () => hang.includes('session.id') ? never() : ({ value: 'sess-1' }))
  on('session.usage', () => hang.includes('session.usage') ? never()
    : ({ value: { startedAt: 0, context: { tokens: 1000, window: 200000, percent: 1 }, rateLimits: LIMITS } }))
  on('ui.log', ($: any, e: any) => { logs.push(String(e.text ?? '')); return hang.includes('ui.log') ? never() : { value: undefined } })
  on('clock.sleep', ($: any, e: any) => (sleeps.push(Number(e.ms)), (hang.length && Number(e.ms) <= 1000)
    || (answer === 'hang' && [3000, 6000].includes(Number(e.ms))) ? { value: undefined } : never()))
  on('ui.invalidate', () => ({ value: undefined }))
  on('process.run', ($: any, e: any) => {
    if (e.argv?.[1] !== 'admission') return { value: { exitCode: 1, stdout: '', stderr: '',
      isStdoutTruncated: false, isStderrTruncated: false } }
    const init = e.init ?? e
    const call = { argv: e.argv, stdin: JSON.parse(String(init.stdin ?? 'null')), timeoutMs: init.timeoutMs, raw: e }
    if (e.argv?.[2] === 'admit') {
      admits.push(call)
      order.push('admit')
      if (answer === 'reject') throw new Error('ENOENT: agentik-session not found')
      if (answer === 'hang') return never()
      const refused = answer === 'refused'
      const verdict = refused ? null : { verdict: answer, mode: 'observe',
        text: answer === 'admitted' ? '' : ANSWER_TEXT, peak: 95.5 }
      return { value: { exitCode: refused ? 3 : 0, stdout: verdict ? JSON.stringify(verdict) : '',
        stderr: refused ? 'agentik-session: the admission ledger stayed locked past 2 s' : '',
        isStdoutTruncated: false, isStderrTruncated: false } }
    }
    calls.push(call)
    if (mode === 'reject') throw new Error('ENOENT: agentik-session not found')
    if (mode === 'timeout') {
      return new Promise((_, reject) => setTimeout(() => reject(new Error('timed out after 5000 ms')), 30))
    }
    return { value: { exitCode: mode === 'refused' ? 3 : 0, stdout: '',
      stderr: mode === 'refused' ? 'agentik-session: the admission ledger stayed locked past 2 s' : '',
      isStdoutTruncated: false, isStderrTruncated: false } }
  })
  return { calls, admits, order, logs, sleeps }
}

const noContent = (calls: Call[]) => {
  for (const c of calls) {
    expect(Object.keys(c.stdin)).not.toContain('prompt')
    expect(Object.keys(c.stdin)).not.toContain('message')
    expect(JSON.stringify(c.raw)).not.toContain('never sent')
    expect(JSON.stringify(c.raw)).not.toContain('secret text')
  }
}

test('a measure with rateLimits in changed records one reading', async (t: any, on: any) => {
  const { calls } = world(on)
  on('session.measure', ($: any, e: any) => ({ changed: e.changed }))
  await t.session.measure({ context: { window: 200000 }, rateLimits: LIMITS, changed: ['rateLimits', 'context'] })
  expect(calls.length).toBe(1)
  expect(calls[0].argv).toEqual(ARGV)
  expect(calls[0].stdin).toEqual({ kind: 'reading', rateLimits: LIMITS })
  expect(calls[0].timeoutMs).toBe(5000)
})

test('a measure without rateLimits in changed records nothing', async (t: any, on: any) => {
  const { calls } = world(on)
  on('session.measure', ($: any, e: any) => ({ changed: e.changed }))
  await t.session.measure({ context: { window: 200000 }, rateLimits: LIMITS, changed: ['context'] })
  expect(calls.length).toBe(0)
})

for (const mode of ['ok', 'reject', 'timeout', 'refused'] as const) {
  test(`agent.spawn passes e to next unchanged, the record call ${mode}`, async (t: any, on: any) => {
    const { calls, logs } = world(on, mode)
    const seen: any[] = []
    on('agent.spawn', ($: any, e: any) => { seen.push(e); return { model: 'claude-opus-5-5', agentId: 'a1' } })
    const r: any = await t.agent.spawn(SPAWN)
    expect(seen.length).toBe(1)
    expect(seen[0]).toEqual(SPAWN)
    expect(r.model).toBe('claude-opus-5-5')
    expect(r.deny).toBeUndefined()
    expect(calls.length).toBe(1)
    expect(calls[0].stdin).toEqual({ kind: 'spawn', subagentType: 'general-purpose', model: 'opus',
      parentModel: 'claude-opus-5-5', background: false, fork: false, description: 'read the packet',
      tool_use_id: 'toolu_01', agentId: 'a1', context: { tokens: 1000, window: 200000, percent: 1 },
      rateLimits: LIMITS })
    expect(logs.filter(l => l.startsWith('admission: record spawn')).length).toBe(mode === 'ok' ? 0 : 1)
    noContent(calls)
  })
}

// Fix round 1, F1: a spawn refused beneath started nothing, so nothing is recorded.
test('a spawn refused beneath records nothing, and the refusal passes up', async (t: any, on: any) => {
  const { calls } = world(on)
  on('agent.spawn', ($: any, e: any) => ({ deny: 'refused below' }))
  let r: any
  try { r = await t.agent.spawn(SPAWN) } catch (err) { r = { thrown: String(err) } }
  expect(r.model).toBeUndefined()
  expect(calls.length).toBe(0)
})

// Fix round 1, F2: a read that never answers is bounded, so `next` is always reached.
test('a usage read that never answers: next is reached, the spawn recorded without readings', async (t: any, on: any) => {
  const { calls } = world(on, 'ok', ['session.usage'])
  const seen: any[] = []
  on('agent.spawn', ($: any, e: any) => { seen.push(e); return { model: 'claude-opus-5-5', agentId: 'a1' } })
  const r: any = await t.agent.spawn(SPAWN)
  expect(seen.length).toBe(1)
  expect(r.agentId).toBe('a1')
  expect(calls.length).toBe(1)
  expect(calls[0].stdin.context).toBeNull()
  expect(calls[0].stdin.rateLimits).toEqual([])
})

test('an id read and a log that never answer: next is reached, nothing recorded', async (t: any, on: any) => {
  const { calls, logs } = world(on, 'ok', ['session.id', 'ui.log'])
  const seen: any[] = []
  on('agent.spawn', ($: any, e: any) => { seen.push(e); return { model: 'claude-opus-5-5', agentId: 'a1' } })
  const r: any = await t.agent.spawn(SPAWN)
  expect(seen.length).toBe(1)
  expect(r.agentId).toBe('a1')
  expect(calls.length).toBe(0)
  expect(logs.filter(l => l.startsWith('admission: record spawn')).length).toBe(1)
})

test('SendMessage records resume, its target only, and calls next', async (t: any, on: any) => {
  const { calls } = world(on)
  const seen: any[] = []
  on('tool.call', ($: any, e: any) => { seen.push(e); return { result: 'sent' } })
  const call = { tool: 'SendMessage', tool_use_id: 'toolu_02', to: 'a1', message: 'secret text', summary: 'go on' }
  await t.tool.call(call)
  expect(seen.length).toBe(1)
  expect(seen[0].to).toBe('a1')
  expect(seen[0].message).toBe('secret text')
  expect(calls.map(c => c.stdin)).toEqual([{ kind: 'resume', to: 'a1' }])
  noContent(calls)
})

test('another tool call records nothing', async (t: any, on: any) => {
  const { calls } = world(on)
  on('tool.call', ($: any, e: any) => ({ result: 'ok' }))
  await t.tool.call({ tool: 'Read', tool_use_id: 'toolu_03', file_path: '/repo/x' })
  expect(calls.length).toBe(0)
})

test('turn.complete with agentId records done; without one, nothing', async (t: any, on: any) => {
  const { calls } = world(on)
  on('turn.complete', ($: any, e: any) => ({ text: e.answer }))
  const turn = { answer: 'the report', durationMs: 1200, isAborted: false, turnId: 'turn-1', reason: 'answer', usage: USAGE }
  await t.turn.complete({ ...turn, agentId: 'a1' })
  await t.turn.complete(turn)
  expect(calls.map(c => c.stdin)).toEqual([{ kind: 'done', agentId: 'a1', durationMs: 1200, usage: USAGE }])
  expect(JSON.stringify(calls[0].raw)).not.toContain('the report')
})

test('session.start records start; session.end records end under the ending id', async (t: any, on: any) => {
  const { calls } = world(on)
  on('session.start', ($: any, e: any) => ({ cwd: e.cwd }))
  on('session.end', ($: any, e: any) => ({ sessionId: e.sessionId }))
  await t.session.start({ cwd: '/repo', surface: null, isInteractive: false })
  await t.session.end({ reason: 'exit', sessionId: 'sess-0', resume: { id: 'sess-0' } })
  expect(calls.map(c => c.stdin)).toEqual([{ kind: 'start', interactive: false }, { kind: 'end', reason: 'exit' }])
  expect(calls[1].argv).toEqual(['agentik-session', 'admission', 'record', '--session', 'sess-0'])
})

// ---- Packet S26: admit is called before `next`, and `next(e)` follows whatever it answers ----

for (const answer of ['admitted', 'deferred', 'denied', 'reject', 'hang', 'refused'] as const) {
  test(`agent.spawn calls admit before next; next(e) unchanged when admit is ${answer}`, async (t: any, on: any) => {
    const { calls, admits, order, logs } = world(on, 'ok', [], answer)
    const seen: any[] = []
    on('agent.spawn', ($: any, e: any) => { order.push('next'); seen.push(e); return { model: 'claude-opus-5-5', agentId: 'a1' } })
    const r: any = await t.agent.spawn(SPAWN)
    expect(order).toEqual(['admit', 'next'])
    expect(seen.length).toBe(1)
    expect(seen[0]).toEqual(SPAWN)
    expect(r.model).toBe('claude-opus-5-5')
    expect(r.deny).toBeUndefined()
    expect(admits.length).toBe(1)
    expect(admits[0].argv).toEqual(ADMIT)
    expect(admits[0].timeoutMs).toBe(3000)
    expect(admits[0].stdin).toEqual({ subagentType: 'general-purpose', model: 'opus',
      parentModel: 'claude-opus-5-5', background: false, fork: false, tool_use_id: 'toolu_01',
      rateLimits: LIMITS, resume: false })
    expect(calls.map(c => c.stdin.kind)).toEqual(['spawn'])
    expect(logs.filter(l => l.startsWith('admission: admit')).length).toBe(1)
    noContent(admits)
  })

  test(`SendMessage calls admit with resume before next; next(e) unchanged when admit is ${answer}`, async (t: any, on: any) => {
    const { calls, admits, order, logs } = world(on, 'ok', [], answer)
    const seen: any[] = []
    on('tool.call', ($: any, e: any) => { order.push('next'); seen.push(e); return { result: 'sent' } })
    const call = { tool: 'SendMessage', tool_use_id: 'toolu_02', to: 'a1', message: 'secret text', summary: 'go on' }
    const r: any = await t.tool.call(call)
    expect(order).toEqual(['admit', 'next'])
    expect(seen.length).toBe(1)
    expect(seen[0].message).toBe('secret text')
    expect(r.result).toBe('sent')
    expect(admits.map(c => c.stdin)).toEqual([{ subagentType: null, model: null, parentModel: null,
      background: null, fork: null, tool_use_id: 'toolu_02', rateLimits: LIMITS, resume: true }])
    expect(calls.map(c => c.stdin)).toEqual([{ kind: 'resume', to: 'a1' }])
    expect(logs.filter(l => l.startsWith('admission: admit')).length).toBe(1)
    noContent(admits)
  })
}

test('an admit answer is logged with its verdict and text', async (t: any, on: any) => {
  const { logs } = world(on, 'ok', [], 'deferred')
  on('agent.spawn', ($: any, e: any) => ({ model: 'claude-opus-5-5', agentId: 'a1' }))
  await t.agent.spawn(SPAWN)
  expect(logs.filter(l => l.startsWith('admission: admit'))).toEqual(
    [`admission: admit deferred (observe, peak 95.5): ${ANSWER_TEXT}`])
})

// Fix round 1, F4: admit's whole call is one 3 s bound, so a hung admit, after the usage
// read's 1 s, keeps `next` within about 5 s; `next(e)` still follows.
test('a hung admit is cut at 3 s, one bound for the whole call, and next follows', async (t: any, on: any) => {
  const { order, logs, sleeps } = world(on, 'ok', [], 'hang')
  on('agent.spawn', ($: any, e: any) => { order.push('next'); return { model: 'claude-opus-5-5', agentId: 'a1' } })
  const r: any = await t.agent.spawn(SPAWN)
  expect(order).toEqual(['admit', 'next'])
  expect(r.model).toBe('claude-opus-5-5')
  expect(Math.max(...sleeps)).toBe(3000)
  expect(logs.filter(l => l.startsWith('admission: admit'))).toEqual(['admission: admit: no answer in 3000 ms'])
})
