// The band's offline tests (mod-r1 §7 criterion 6, packet M1 ruling 7), run by
// `claude plugin test plugin`, which runs no model: the host's process, files and clock faked.
import { test, expect } from 'claude-code/testing'

const DIR = '/state/sessions/sess-1'
const NOW = Date.parse('2026-10-12T12:00:00+00:00')
const METER = JSON.stringify({ pct_context: 62.4, pct_turns: 31, zone: 'notice', ts: '2026-10-12T11:59:30+00:00' })
const OLD = JSON.stringify({ pct_context: 62.4, pct_turns: 31, zone: 'notice', ts: '2026-10-12T11:57:00+00:00' })
const PROPS = (columns: number, hasSurvey = false) => ({ component: 'AbovePrompt', surface: 'terminal',
  props: { hasSurvey, bodyColumns: columns, scroll: { offset: 0, bodyRows: 3 } } })

// The one fixture both twins read (packet S27b ruling 7): tests/test_band.py reads these
// two lines and NOW above, and asserts Python's band_line gives BAND_LINE for BAND at NOW.
const BAND = '{"P": 72, "peak": 91.2, "ceiling": 97, "resetsAt": "2026-10-12T13:12:00+00:00", "running": 3, "room": 2, "deferred": 1, "P7": 41, "mode": "observe", "at": "2026-10-12T11:59:30+00:00"}'
const BAND_LINE = '5h 72% → 91% · ceiling 97 · resets 13:12 (1h12) · 3 helpers, room for 2 · 1 deferred · 7d 41% · observe'
// The weekly reset bounds the horizon (the owner, 2026-10-14): the line says `week resets`.
const BAND_WEEK = '{"P": 72, "peak": 91.2, "ceiling": 97, "resetsAt": "2026-10-12T13:17:00+00:00", "bound": "seven_day", "running": 3, "room": 2, "deferred": 1, "P7": 41, "mode": "observe", "at": "2026-10-12T11:59:30+00:00"}'
const BAND_WEEK_LINE = '5h 72% → 91% · ceiling 97 · week resets 13:17 (1h17) · 3 helpers, room for 2 · 1 deferred · 7d 41% · observe'
const BAND_JSON = '/state/admission/band.json'

const ARGV = ['agentik-session', 'mod', 'start', '--session', 'sess-1']
const NO_METER = 'session: no meter · agentik-session doctor'

const band = async (t: any, on: any, files: Record<string, string>, columns = 120, ran = 0) => {
  on('session.start', ($: any, e: any) => e)
  on('session.id', () => ({ value: 'sess-1' }))
  on('process.run', ($: any, e: any) => ({ value: { code: JSON.stringify(e.argv) === JSON.stringify(ARGV) ? ran : 9, stdout: ran === 0 ? JSON.stringify({ dir: DIR }) : '', stderr: '' } }))
  on('fs.read', ($: any, e: any) => {
    if (!(e.path in files)) throw new Error(`ENOENT ${e.path}`)
    return { value: files[e.path] }
  })
  on('clock.now', () => ({ value: NOW }))
  on('clock.sleep', () => new Promise(() => {}))
  on('ui.invalidate', () => ({ value: undefined }))
  await t.session.start({ cwd: '/repo' })
  const tree: any = await t.ui.render(PROPS(columns))
  return tree.children[0].children[0] as string
}

test('the band reads ctx, turns and the zone from meter.json', async (t: any, on: any) => {
  expect(await band(t, on, { [`${DIR}/meter.json`]: METER })).toBe('session: ctx 62% · turns 31% · notice')
})

test('no meter.json: no meter, and where to look', async (t: any, on: any) => {
  expect(await band(t, on, {})).toBe('session: no meter · agentik-session doctor')
})

test('mod start failing: no meter', async (t: any, on: any) => {
  expect(await band(t, on, { [`${DIR}/meter.json`]: METER }, 120, 1)).toBe('session: no meter · agentik-session doctor')
})

test('meter.json past 120 s: its age', async (t: any, on: any) => {
  expect(await band(t, on, { [`${DIR}/meter.json`]: OLD })).toBe('session: ctx 62% · turns 31% · notice · 180s old')
})

test('the line fits bodyColumns', async (t: any, on: any) => {
  const line = await band(t, on, { [`${DIR}/meter.json`]: OLD, [`${DIR}/respawn.json`]: '{}' }, 30)
  expect(line.length).toBeLessThanOrEqual(30)
  expect(line).toStartWith('session: ctx 62%')
})

test('respawn.json present: respawn marked', async (t: any, on: any) => {
  expect(await band(t, on, { [`${DIR}/meter.json`]: METER, [`${DIR}/respawn.json`]: '{}' }))
    .toBe('session: ctx 62% · turns 31% · notice · respawn marked')
})

// ---- Packet S27b: admission's line under the session's, from band.json ----
const lines = async (t: any, on: any, files: Record<string, string>, columns = 120,
                     hasSurvey = false, below: any = undefined) => {
  if (below !== undefined) on('ui.render', () => below)
  await band(t, on, files, columns)
  return t.ui.render(PROPS(columns, hasSurvey))
}
const texts = (tree: any): any[] => (tree.children as any[]).map(c => c.type === 'Text' ? c.children[0] : c)

test('the band draws band.json as a second line, the text Python draws from the same file', async (t: any, on: any) => {
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: BAND })
  expect(texts(tree)).toEqual(['session: ctx 62% · turns 31% · notice', BAND_LINE])
})

test('the seven-day reset bounding the horizon: week resets, as Python draws it', async (t: any, on: any) => {
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: BAND_WEEK })
  expect(texts(tree)).toEqual(['session: ctx 62% · turns 31% · notice', BAND_WEEK_LINE])
})

test('the second line is cut to bodyColumns: 80', async (t: any, on: any) => {
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: BAND }, 80)
  expect(texts(tree)[1]).toBe('5h 72% → 91% · ceiling 97 · resets 13:12 (1h12) · 3 helpers, room for 2 · 1 def…')
})

test('no band.json, or an unreadable one: the session line alone', async (t: any, on: any) => {
  expect(texts(await lines(t, on, { [`${DIR}/meter.json`]: METER })))
    .toEqual(['session: ctx 62% · turns 31% · notice'])
})

test('band.json unparseable: the session line alone', async (t: any, on: any) => {
  expect(texts(await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: '{not json' })))
    .toEqual(['session: ctx 62% · turns 31% · notice'])
})

test('no reading: 5h no reading', async (t: any, on: any) => {
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER,
    [BAND_JSON]: JSON.stringify({ mode: 'observe', at: '2026-10-12T11:57:00+00:00' }) })
  expect(texts(tree)[1]).toBe('5h no reading · observe · 180s old')
})

test('while hasSurvey: neither line, and what next gives', async (t: any, on: any) => {
  const survey = { type: 'Text', props: {}, children: ['survey: how was it?'] }
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: BAND }, 120, true, survey)
  expect(tree).toMatchObject(survey) // the engine (2.1.299) tags a node with its plugin: `part`
})

test('another mod\'s line is kept under the two', async (t: any, on: any) => {
  const other = { type: 'Text', props: {}, children: ['other: its own line'] }
  const tree: any = await lines(t, on, { [`${DIR}/meter.json`]: METER, [BAND_JSON]: BAND }, 120, false, other)
  expect(texts(tree)).toEqual(['session: ctx 62% · turns 31% · notice', BAND_LINE, 'other: its own line'])
})

// Fix round 1: the classic SessionStart hook makes the session dir after the module's
// session.start has run, so `mod start` is retried on every 5 s tick until it answers.
const retrying = async (t: any, on: any, failures: number) => {
  const argvs: string[] = []
  const sleepers: Array<(v: unknown) => void> = []
  on('session.start', ($: any, e: any) => e)
  on('session.id', () => ({ value: 'sess-1' }))
  on('process.run', ($: any, e: any) => {
    // The module records admission's lines too (packet S25): only `mod start` is counted.
    if (e.argv?.[1] === 'admission') return { value: { exitCode: 0, stdout: '', stderr: '' } }
    argvs.push(JSON.stringify(e.argv))
    return { value: argvs.length <= failures
      ? { code: 1, stdout: '', stderr: 'agentik-session: no session sess-1' }
      : { code: 0, stdout: JSON.stringify({ dir: DIR }), stderr: '' } }
  })
  on('fs.read', ($: any, e: any) => {
    if (e.path !== `${DIR}/meter.json`) throw new Error(`ENOENT ${e.path}`)
    return { value: METER }
  })
  on('clock.now', () => ({ value: NOW }))
  // Only the band's 5 s tick is driven; admission's 1 s bounds (fix round 1, F2) never pass.
  on('clock.sleep', ($: any, e: any) => Number(e.ms) === 5000
    ? new Promise(resolve => { sleepers.push(resolve) }) : new Promise(() => {}))
  on('ui.invalidate', () => ({ value: undefined }))
  await t.session.start({ cwd: '/repo' })
  const tick = async () => {
    sleepers.shift()?.({ value: undefined })
    await new Promise(resolve => setTimeout(resolve, 20))
  }
  const draw = async () => ((await t.ui.render(PROPS(120))) as any).children[0].children[0] as string
  return { argvs, tick, draw }
}

test('mod start failing twice: the third try, on the second tick, draws the meter', async (t: any, on: any) => {
  const { argvs, tick, draw } = await retrying(t, on, 2)
  expect(await draw()).toBe(NO_METER)
  await tick()
  expect(await draw()).toBe(NO_METER)
  await tick()
  expect(await draw()).toBe('session: ctx 62% · turns 31% · notice')
  expect(argvs).toEqual([JSON.stringify(ARGV), JSON.stringify(ARGV), JSON.stringify(ARGV)])
  await tick()
  expect(argvs.length).toBe(3)
})

test('mod start never answering: 24 tries, then the doctor line', async (t: any, on: any) => {
  const { argvs, tick, draw } = await retrying(t, on, 1000)
  for (let i = 0; i < 30; i++) await tick()
  expect(argvs.length).toBe(24)
  expect(await draw()).toBe(NO_METER)
})

// Packet M2: every session.measure sends one `measure record` (the four figures, never a
// message's text), and admission's reading beside it when a window moved; either call
// rejecting or hanging still reaches `next`, and the hook answers what `next` settled to.
const MEASURED = ['agentik-session', 'measure', 'record', '--session', 'sess-1']
const READING = ['agentik-session', 'admission', 'record', '--session', 'sess-1']
const LIMITS = [{ kind: 'five_hour', percentUsed: 41.5, resetsAt: '2026-10-12T14:05:00Z' }]
const MEASURE_IN = { context: { tokens: 20000, window: 200000, percent: 10 }, rateLimits: LIMITS,
  cost: { usd: 1.25 }, prompt: 'never sent', message: 'secret text' }

const measuring = (on: any, fail: Record<string, 'reject' | 'hang'> = {}) => {
  const calls: Array<{ argv: string[], stdin: any, raw: any }> = []
  const seen: any[] = []
  const hangs = Object.values(fail).includes('hang')
  on('session.id', () => ({ value: 'sess-1' }))
  on('ui.log', () => ({ value: undefined }))
  // A bound passes after 30 ms only when a call hangs; otherwise no wait ever ends.
  on('clock.sleep', () => hangs
    ? new Promise(resolve => setTimeout(() => resolve({ value: undefined }), 30)) : new Promise(() => {}))
  on('process.run', ($: any, e: any) => {
    const init = e.init ?? e
    calls.push({ argv: e.argv, stdin: JSON.parse(String(init.stdin ?? 'null')), raw: e })
    const how = fail[String(e.argv?.[1])]
    if (how === 'reject') throw new Error('ENOENT: agentik-session not found')
    if (how === 'hang') return new Promise(() => {})
    return { value: { exitCode: 0, stdout: '', stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('session.measure', ($: any, e: any) => { seen.push(e); return { changed: e.changed } })
  return { calls, seen }
}

const argvs = (calls: Array<{ argv: string[] }>) => calls.map(c => JSON.stringify(c.argv)).sort()

test('a measure without rateLimits changed sends one measure record and no reading', async (t: any, on: any) => {
  const { calls, seen } = measuring(on)
  const r: any = await t.session.measure({ ...MEASURE_IN, changed: ['context'] })
  expect(seen.length).toBe(1)
  expect(r.changed).toEqual(['context'])
  expect(argvs(calls)).toEqual([JSON.stringify(MEASURED)])
  expect(calls[0].stdin).toEqual({ context: { tokens: 20000, window: 200000, percent: 10 },
    rateLimits: LIMITS, cost: { usd: 1.25 }, changed: ['context'] })
  expect(JSON.stringify(calls[0].raw)).not.toContain('never sent')
  expect(JSON.stringify(calls[0].raw)).not.toContain('secret text')
})

test('a measure with rateLimits changed sends the measure record and admission\'s reading', async (t: any, on: any) => {
  const { calls, seen } = measuring(on)
  await t.session.measure({ ...MEASURE_IN, changed: ['rateLimits', 'context'] })
  expect(seen.length).toBe(1)
  expect(argvs(calls)).toEqual([JSON.stringify(READING), JSON.stringify(MEASURED)].sort())
  const m = calls.find(c => c.argv[1] === 'measure')!
  expect(Object.keys(m.stdin).sort()).toEqual(['changed', 'context', 'cost', 'rateLimits'])
  for (const c of calls) {
    expect(JSON.stringify(c.raw)).not.toContain('never sent')
    expect(JSON.stringify(c.raw)).not.toContain('secret text')
  }
})

for (const verb of ['measure', 'admission'] as const) {
  for (const how of ['reject', 'hang'] as const) {
    test(`the ${verb} call ${how === 'reject' ? 'rejecting' : 'hanging'}: next is reached and the other call is sent`, async (t: any, on: any) => {
      const { calls, seen } = measuring(on, { [verb]: how })
      const r: any = await t.session.measure({ ...MEASURE_IN, changed: ['rateLimits'] })
      expect(seen.length).toBe(1)
      expect(r.changed).toEqual(['rateLimits'])
      expect(argvs(calls)).toEqual([JSON.stringify(READING), JSON.stringify(MEASURED)].sort())
    })
  }
}
