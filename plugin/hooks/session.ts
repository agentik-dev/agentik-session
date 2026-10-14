// The session plugin's hooks module (design/mod-r1.md §6 S1, packet M1): one read-only band
// above the prompt. At session.start it runs `agentik-session mod start` (5 s), which writes
// mod.json and prints the session's directory; the band reads meter.json and respawn.json
// there and draws one line, and admission's band.json a second (packet S27b). It writes no
// file, keeps no figure a decision reads, and needs no sibling plugin. The classic hooks in
// hooks.json decide everything; this only shows.
//
// It is the plugin's one module (2.1.296 loads one per plugin and one unmatched hook per
// event), and it carries admission's code too, under its own heading below (packet S25
// ruling 1: the engine follows `$` into a function of this same file only, never across an
// import, so admission's handlers cannot live in a sibling file). Its session.start and
// turn.complete run the band's part and admission's, each part's failure caught so neither
// skips the other or `next`; admission's other four hooks are registered once. Its one
// session.measure handler runs the measure's part (packet M2, below admission's heading) and
// admission's reading, each bounded and caught, after `next`.
import type { EngineInterface, Register } from 'claude-code'

const STALE_S = 120
const EVERY_MS = 5000
const MAX_TRIES = 24      // `mod start` retried while the dir is unknown: 2 min of ticks
const NO_METER = 'session: no meter · agentik-session doctor'
// agentik-r1 §6.3 c11 (packet ruling 7): the tool by its new name; when that is not on PATH
// (the run rejects, not found), its old name, the alias until r2.
const TOOL = 'agentik-session'
const OLD_TOOL = 'claude-session'
const notFound = (err: any): boolean => /ENOENT|not found/i.test(String(err?.message ?? err))
async function runTool($: EngineInterface, argv: string[], opts: any): Promise<any> {
  try {
    return await $.process.run(argv, opts)
  } catch (err) {
    if (argv[0] !== TOOL || !notFound(err)) throw err
    return await $.process.run([OLD_TOOL, ...argv.slice(1)], opts)
  }
}

const clip = (line: string, columns: number): string =>
  columns > 0 && line.length > columns ? line.slice(0, Math.max(1, columns - 1)) + '…' : line

const pct = (n: unknown): string => `${Math.round(Number(n))}%`

export const bandLine = (meter: string | null, respawn: boolean, nowMs: number): string => {
  let m: any = null
  try { m = meter === null ? null : JSON.parse(meter) } catch { m = null }
  if (!m || typeof m !== 'object' || m.zone === undefined) return NO_METER
  let line = `session: ctx ${pct(m.pct_context)} · turns ${pct(m.pct_turns)} · ${m.zone}`
  if (respawn) line += ' · respawn marked'
  const age = Math.floor((nowMs - Date.parse(String(m.ts))) / 1000)
  if (Number.isFinite(age) && age > STALE_S) line += ` · ${age}s old`
  return line
}

// ---- Admission's line (design/admission-r1.md §3.5, packet S27b): it shows. ----
// `agentik-session admission` rewrites <state>/admission/band.json inside the ledger's lock at
// every record and admit; the band draws it under the session's line. This is the twin of
// Python's band_line (one fixture in session.test.ts pins both): a part with no figure is
// left out, `observe` is last while the mode is, and the age past 120 s follows it; the
// reset reads `week resets` when band.json's bound is the seven-day one.
const ISO = /^\d{4}-\d{2}-\d{2}T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/
const fig = (v: unknown): number | null => typeof v === 'number' && Number.isFinite(v) ? v : null
const whole = (n: number): string => String(Math.round(n))

// A band time, as written: HH and MM from the string's own digits (band.json's resetsAt is
// local with its offset), and its instant; null unless a strict zoned ISO string.
const wall = (v: unknown): [string, string, number] | null => {
  const m = typeof v === 'string' ? ISO.exec(v) : null
  const t = m ? Date.parse(String(v)) : NaN
  return m && Number.isFinite(t) ? [m[1], m[2], t] : null
}

// band.json beside the sessions: `<state>/sessions/<id>` is what `mod start` prints.
const bandPath = (d: string): string => {
  const m = /^(.*)\/sessions\/[^/]+\/?$/.exec(d)
  return m ? `${m[1]}/admission/band.json` : ''
}

export const admissionLine = (band: string | null, nowMs: number): string | null => {
  let b: any = null
  try { b = band === null ? null : JSON.parse(band) } catch { b = null }
  if (!b || typeof b !== 'object' || Array.isArray(b)) return null
  const P = fig(b.P), peak = fig(b.peak), c = fig(b.ceiling)
  const parts = [P === null ? '5h no reading' : `5h ${whole(P)}%` + (peak !== null ? ` → ${whole(peak)}%` : '')]
  if (c !== null) parts.push(`ceiling ${String(c)}`)
  const w = wall(b.resetsAt)
  if (w) {
    const left = Math.max(0, Math.floor((w[2] - nowMs) / 60000))
    const word = b.bound === 'seven_day' ? 'week resets' : 'resets'
    parts.push(`${word} ${w[0]}:${w[1]} (${Math.floor(left / 60)}h${String(left % 60).padStart(2, '0')})`)
  }
  const running = fig(b.running), room = fig(b.room)
  const helpers: string[] = []
  if (running !== null) helpers.push(`${whole(running)} ${whole(running) === '1' ? 'helper' : 'helpers'}`)
  if (room !== null) helpers.push(`room for ${whole(room)}`)
  if (helpers.length) parts.push(helpers.join(', '))
  const d = fig(b.deferred), p7 = fig(b.P7)
  if (d !== null) parts.push(`${whole(d)} deferred`)
  if (p7 !== null) parts.push(`7d ${whole(p7)}%`)
  if (b.mode === 'observe') parts.push('observe')
  const a = wall(b.at)
  const age = a ? Math.floor((nowMs - a[2]) / 1000) : NaN
  if (Number.isFinite(age) && age > STALE_S) parts.push(`${age}s old`)
  return parts.join(' · ')
}

// ---- Admission (design/admission-r1.md §3.1, packet S25): it observes. ----
// Six hooks hand what they see to `agentik-session admission record` through runTool
// (5 s), which keeps one line per event on the machine's admission ledger; the policy lives
// in the tool, this is glue. They never refuse and never rewrite: every hook returns what
// `next` settled to, a failed record is one debug line, and a spawn's prompt and a
// message's text are never sent. They write no file and need no sibling plugin.
const LIMIT_MS = 5000
const BOUND_MS = 1000
const DEBUG = { to: 'debug' as const }
const LATE = Symbol('late')

const str = (v: unknown): string | null => (typeof v === 'string' ? v : null)
const bool = (v: unknown): boolean | null => (typeof v === 'boolean' ? v : null)
const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)
const list = (v: unknown): unknown[] => (Array.isArray(v) ? v : [])
// One reading per window, by the fields the types name (SessionRateLimit), read defensively.
const limits = (v: unknown): unknown[] =>
  list(v).map((r: any) => ({ kind: str(r?.kind), percentUsed: num(r?.percentUsed),
    resetsAt: str(r?.resetsAt) }))

const admissionArgv = (id: unknown): string[] =>
  [TOOL, 'admission', 'record', '--session', String(id)]
const exited = (fields: Record<string, unknown>, r: any): string | null =>
  Number(r?.exitCode) === 0 ? null
    : `admission: record ${fields.kind}: exit ${r?.exitCode}: ${String(r?.stderr ?? '').trim()}`.slice(0, 300)
const failed = (fields: Record<string, unknown>, err: any): string =>
  `admission: record ${fields.kind}: ${String(err?.message ?? err)}`.slice(0, 300)

// A host call raced against a short wait (fix round 1, F2): one that never answers leaves
// LATE after BOUND_MS, never a hung hook. A refused clock leaves the call unbounded.
async function within<T>($: EngineInterface, call: () => Promise<T>,
  ms = BOUND_MS): Promise<T | typeof LATE> {
  let wait: Promise<typeof LATE>
  try { wait = $.clock.sleep(ms).then(() => LATE, () => new Promise<typeof LATE>(() => {})) }
  catch { wait = new Promise<typeof LATE>(() => {}) }
  return Promise.race([(async () => call())(), wait])
}

// One record call, under `id` or the session's own id; it never throws: a non-zero exit, a
// rejection or a timeout is one debug line, and the id read and the log are each bounded.
async function record($: EngineInterface, fields: Record<string, unknown>, id: string | null = null,
  timeoutMs = LIMIT_MS): Promise<void> {
  try {
    const who = id ?? await within($, () => $.session.id())
    if (who === LATE) throw new Error(`no session id in ${BOUND_MS} ms`)
    const r = await runTool($, admissionArgv(who), { stdin: JSON.stringify(fields), timeoutMs })
    const line = exited(fields, r)
    if (line) await within($, () => $.ui.log(line, DEBUG))
  } catch (err) { try { await within($, () => $.ui.log(failed(fields, err), DEBUG)) } catch { /* nothing */ } }
}

// session.start's part, after `next`: `start`, and whether the session is interactive.
async function admitStart($: EngineInterface, e: unknown): Promise<void> {
  await record($, { kind: 'start', interactive: bool((e as any)?.isInteractive) })
}

// turn.complete's part, after `next`: a helper's turn (it carries agentId) is `done`.
async function admitDone($: EngineInterface, e: unknown): Promise<void> {
  const x: any = e
  if (!str(x?.agentId)) return
  await record($, { kind: 'done', agentId: str(x.agentId), durationMs: num(x.durationMs),
    usage: x.usage && typeof x.usage === 'object' ? x.usage : null })
}

// The verdict, observed (design/admission-r1.md §3.3, packet S26 ruling 6): before `next`,
// `agentik-session admission admit` decides the spawn or the resume and appends its verdict
// line. In observe the answer is one debug line and `next(e)` always follows, whatever it
// says: a refusal, an exit, a rejection or a late answer is a debug line too. The whole call
// (the id read, the run and the answer's log) is raced against ADMIT_MS, the lock waiting at
// most 2 s, so the usage read, admit and a late line keep `next` within about 5 s (fix round
// 1, F4). S27a makes it refuse.
const ADMIT_MS = 3000
const admitArgv = (id: unknown): string[] =>
  [TOOL, 'admission', 'admit', '--session', String(id)]

async function admitCall($: EngineInterface, fields: Record<string, unknown>,
  say: (line: string) => Promise<void>): Promise<void> {
  const who = await within($, () => $.session.id())
  if (who === LATE) throw new Error(`no session id in ${BOUND_MS} ms`)
  const r: any = await runTool($, admitArgv(who), { stdin: JSON.stringify(fields), timeoutMs: ADMIT_MS })
  if (Number(r?.exitCode) !== 0) {
    await say(`admission: admit: exit ${r?.exitCode}: ${String(r?.stderr ?? '').trim()}`)
    return
  }
  let a: any = null
  try { a = JSON.parse(String(r?.stdout ?? '')) } catch { a = null }
  const text = str(a?.text)
  await say(`admission: admit ${str(a?.verdict) ?? 'unreadable'} (${str(a?.mode) ?? '?'}, peak `
    + `${num(a?.peak) ?? '-'})${text ? `: ${text}` : ''}`)
}

async function admit($: EngineInterface, fields: Record<string, unknown>): Promise<void> {
  const say = async (line: string): Promise<void> => {
    try { await within($, () => $.ui.log(line.slice(0, 300), DEBUG)) } catch { /* nothing */ }
  }
  try {
    const r = await within($, () => admitCall($, fields, say), ADMIT_MS)
    if (r === LATE) await say(`admission: admit: no answer in ${ADMIT_MS} ms`)
  } catch (err: any) { await say(`admission: admit: ${String(err?.message ?? err)}`) }
}

// The usage read before `next`, bounded: a late or refused read is no reading.
async function usageNow($: EngineInterface): Promise<any> {
  try { const u = await within($, () => $.session.usage()); return u === LATE ? null : u } catch { return null }
}

// ---- The measure (design/mod-r1.md §2 row M2, §6 S2; packet M2): it records. ----
// Every session.measure hands the engine's figures to `agentik-session measure record`
// (5 s), which writes measure.json beside meter.json; `status` and `doctor` print the drift.
// Nothing that decides reads it. Only the four figures are sent, never a message's text.
const measureArgv = (id: unknown): string[] =>
  [TOOL, 'measure', 'record', '--session', String(id)]

const measureFields = (e: unknown): Record<string, unknown> => {
  const x: any = e
  const c: any = x?.context && typeof x.context === 'object' ? x.context : null
  return {
    context: c ? { tokens: num(c.tokens), window: num(c.window), percent: num(c.percent) } : null,
    rateLimits: limits(x?.rateLimits),
    cost: x?.cost && typeof x.cost === 'object' ? { usd: num(x.cost.usd) } : null,
    changed: list(x?.changed).map(str),
  }
}

// One measure call; it never throws: a non-zero exit, a rejection or a late answer is one
// debug line, and the id read, the call and the log are each bounded.
async function measured($: EngineInterface, e: unknown): Promise<void> {
  const say = async (line: string): Promise<void> => {
    try { await within($, () => $.ui.log(line.slice(0, 300), DEBUG)) } catch { /* nothing */ }
  }
  try {
    const who = await within($, () => $.session.id())
    if (who === LATE) throw new Error(`no session id in ${BOUND_MS} ms`)
    const r: any = await within($, () => runTool($, measureArgv(who),
      { stdin: JSON.stringify(measureFields(e)), timeoutMs: LIMIT_MS }), LIMIT_MS + BOUND_MS)
    if (r === LATE) throw new Error(`no answer in ${LIMIT_MS + BOUND_MS} ms`)
    if (Number(r?.exitCode) !== 0) await say(`measure: record: exit ${r?.exitCode}: ${String(r?.stderr ?? '').trim()}`)
  } catch (err: any) { await say(`measure: record: ${String(err?.message ?? err)}`) }
}

// ---- The band ----
// The session's id and directory live here, not in $.state (no declared state contract);
// session.start sets them afresh, at a session's start and at every reload of the module.
let sid = ''
let dir = ''
let tries = 0

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    const r = await next(e)
    dir = ''
    tries = 0
    try {
      try { sid = String(await $.session.id()) } catch { sid = '' }
      // The classic SessionStart hook may make the session dir after this hook has run (fix
      // round 1): a failed `mod start` leaves dir unknown, and each 5 s tick tries again.
      const start = async (): Promise<void> => {
        if (dir || !sid || tries >= MAX_TRIES) return
        tries += 1
        try {
          const p: any = await runTool($, [TOOL, 'mod', 'start', '--session', sid],
            { timeoutMs: EVERY_MS })
          dir = String(JSON.parse(String(p?.stdout ?? '')).dir ?? '')
        } catch { dir = '' }
      }
      await start()
      await $.ui.invalidate('ui.render')
      void (async () => {
        for (;;) { await $.clock.sleep(EVERY_MS); await start(); await $.ui.invalidate('ui.render') }
      })()
    } catch { /* the band's failure skips neither admission's part nor the answer */ }
    try { await admitStart($, e) } catch { /* admission never throws; nor does this */ }
    return r
  })
  on('turn.complete', async ($, e, next) => {
    const r = await next(e)
    try {
      if (!dir && sid && tries < MAX_TRIES) {
        tries += 1
        try {
          const p: any = await runTool($, [TOOL, 'mod', 'start', '--session', sid],
            { timeoutMs: EVERY_MS })
          dir = String(JSON.parse(String(p?.stdout ?? '')).dir ?? '')
        } catch { dir = '' }
      }
      await $.ui.invalidate('ui.render')
    } catch { /* the band's failure skips neither admission's part nor the answer */ }
    try { await admitDone($, e) } catch { /* admission never throws; nor does this */ }
    return r
  })
  // Two lines, the session's and admission's, in one column (packet S27b ruling 3). While a
  // survey holds the band it draws neither and gives what `next` gives; otherwise it adds
  // to that: another mod's tree is kept under the two, and only core's own (an `engine`
  // ref, which draws nothing here without a survey) is left out, as M1's band left it.
  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const props: any = (e as any).props ?? {}
    if (props.hasSurvey === true) return next(e)
    let below: any = null
    try { below = await next(e) } catch { below = null }
    const columns = Number(props.bodyColumns ?? 0)
    const rows: string[] = []
    if (!dir) rows.push(NO_METER)
    else {
      let meter: string | null = null
      let respawn = false
      let band: string | null = null
      try { meter = String(await $.fs.read(`${dir}/meter.json`)) } catch { meter = null }
      try { await $.fs.read(`${dir}/respawn.json`); respawn = true } catch { respawn = false }
      const at = bandPath(dir)
      if (at) { try { band = String(await $.fs.read(at)) } catch { band = null } }
      const now = Number(await $.clock.now())
      rows.push(bandLine(meter, respawn, now))
      const line = admissionLine(band, now)
      if (line !== null) rows.push(line)
    }
    const kids: any[] = rows.map(l => ({ type: 'Text', props: {}, children: [clip(l, columns)] }))
    if (below && typeof below === 'object' && below.type !== 'engine') kids.push(below)
    return { type: 'Box', props: { flexDirection: 'column' }, children: kids }
  })

  // ---- Admission's other four hooks (above: its part of session.start and turn.complete) ----
  // session.measure carries the measure's part too (packet M2): every measure is recorded,
  // and admission's reading only when a window moved. The two run side by side after `next`,
  // each raced against its bound and caught, so neither waits on or skips the other.
  on('session.measure', async ($, e, next) => {
    const r = await next(e)
    const parts: Array<() => Promise<void>> = [() => measured($, e)]
    if (list((e as any)?.changed).includes('rateLimits')) {
      parts.push(() => record($, { kind: 'reading', rateLimits: limits((e as any).rateLimits) }))
    }
    await Promise.all(parts.map(async part => {
      try { await within($, part, LIMIT_MS + 2 * BOUND_MS) } catch { /* each part never throws */ }
    }))
    return r
  })
  // agentId comes from the spawn's result, so the spawn is recorded after `next`; a usage
  // read past its bound records the spawn without readings. A spawn refused beneath started
  // nothing (next's answer has no model), so it is not recorded (fix round 1, F1).
  // Packet S26: the spawn is admitted (observed) before `next`, from the same usage read.
  on('agent.spawn', async ($, e, next) => {
    const x: any = e
    const usage: any = await usageNow($)
    await admit($, {
      subagentType: str(x.subagentType), model: str(x.model), parentModel: str(x.parentModel),
      background: bool(x.background), fork: bool(x.fork), tool_use_id: str(x.tool_use_id),
      rateLimits: limits(usage?.rateLimits), resume: false,
    })
    const r: any = await next(e)
    if (str(r?.model) === null) return r
    await record($, {
      kind: 'spawn', subagentType: str(x.subagentType), model: str(x.model),
      parentModel: str(x.parentModel), background: bool(x.background), fork: bool(x.fork),
      description: str(x.description), tool_use_id: str(x.tool_use_id), agentId: str(r?.agentId),
      context: usage?.context ? { tokens: num(usage.context.tokens),
        window: num(usage.context.window), percent: num(usage.context.percent) } : null,
      rateLimits: limits(usage?.rateLimits),
    })
    return r
  }).catch(($, e, next) => next(e))
  // A resume reaches a helper through SendMessage and raises no agent.spawn: its target only.
  // Packet S26: it is admitted (observed) before `next` with `resume: true`, the call's id and
  // the window's readings only (the message is never sent).
  on('tool.call', { tool: 'SendMessage' }, async ($, e, next) => {
    const usage: any = await usageNow($)
    await admit($, { subagentType: null, model: null, parentModel: null, background: null,
      fork: null, tool_use_id: str((e as any).tool_use_id), rateLimits: limits(usage?.rateLimits),
      resume: true })
    const r = await next(e)
    await record($, { kind: 'resume', to: str((e as any).to) })
    return r
  }).catch(($, e, next) => next(e))
  // The end runs first, inside session.end's one short bound, under the ending session's
  // id (a /clear goes on under another); the tool sweeps its open spawns in the same lock.
  on('session.end', async ($, e, next) => {
    const left = Number((next as any).budget?.remainingMs)
    const ms = Number.isFinite(left) && left > 0 ? Math.min(LIMIT_MS, left) : LIMIT_MS
    await record($, { kind: 'end', reason: str((e as any).reason) }, str((e as any).sessionId), ms)
    return next(e)
  })
}
