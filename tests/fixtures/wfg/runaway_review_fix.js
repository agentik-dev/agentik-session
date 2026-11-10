export const meta = {
  name: 'review-built-branches',
  description: 'One review of code per built branch, each finding verified, then the fix',
  phases: [
    { title: 'Finish', detail: 'finish two branches', model: 'opus' },
    { title: 'Review', detail: 'one reviewer per branch' },
    { title: 'Verify', detail: 'each finding refuted or kept' },
    { title: 'Fix', detail: 'confirmed findings fixed, then the gate', model: 'opus' },
  ],
}
const B = '/tmp/example/briefs'
const COMMON = `
House rules: read ${B}/RULES.md first; it binds you. Your scratch folder is ${B}/<your label>/.
`
const ITEMS = [
  { key: 'alpha', wt: '/tmp/example/wt/alpha', base: 'main', brief: `${B}/alpha.md`, finish: '' },
  { key: 'beta', wt: '/tmp/example/wt/beta', base: 'main', brief: `${B}/beta.md`, finish: '' },
  { key: 'gamma', wt: '/tmp/example/wt/gamma', base: 'main', brief: `${B}/gamma.md`,
    finish: `Your label: finish-gamma. A builder stopped at its turn limit in this worktree: finish it.` },
  { key: 'delta', wt: '/tmp/example/wt/delta', base: 'main', brief: `${B}/delta.md`, finish: '' },
  { key: 'epsilon', wt: '/tmp/example/wt/epsilon', base: 'main', brief: `${B}/epsilon.md`,
    finish: `Your label: finish-epsilon. Read ${B}/handback-epsilon.md: one last fold is owed.` },
]
const DONE = new Set(['review:alpha', 'review:beta'])
const M = l => DONE.has(l) ? {} : { model: 'opus' }
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, file: { type: 'string' }, repro: { type: 'string' } }, required: ['title', 'file', 'repro'] } } }, required: ['findings'] }
const VERD = { type: 'object', properties: { real: { type: 'boolean' }, why: { type: 'string' } }, required: ['real', 'why'] }

const out = await pipeline(ITEMS,
  it => it.finish ? agent(`${COMMON}\nWorktree: ${it.wt}.\n${it.finish}`, { label: `finish:${it.key}`, phase: 'Finish', model: 'opus' }) : 'built already',
  (fin, it) => agent(`${COMMON}
Your label: review-${it.key}. You give branch ${it.key} its one review of code. Worktree ${it.wt}; its brief: ${it.brief}.
Find correctness bugs, each with a reproduction you ran.`, { label: `review:${it.key}`, phase: 'Review', schema: FIND, ...M(`review:${it.key}`) }),
  (rev, it) => rev ? parallel(rev.findings.map((f, i) => () => agent(`${COMMON}
Your label: verify-${it.key}-${i}. A reviewer reports this against branch ${it.key}. Try to refute it.
${f.title} (${f.file})
repro: ${f.repro}`, { label: `verify:${it.key}-${i}`, phase: 'Verify', schema: VERD, ...M(`verify:${it.key}-${i}`) }).then(v => ({ ...f, real: !!(v && v.real), why: v ? v.why : 'verifier died' })))) : [],
  (vs, it) => {
    const real = (vs || []).filter(Boolean).filter(v => v.real)
    return agent(`${COMMON}
Your label: fix-${it.key}. Worktree ${it.wt}. ${real.length ? `Fix each confirmed finding below with a test:\n${real.map((f, i) => `${i + 1}. ${f.title}`).join('\n')}` : 'No confirmed finding: run the gate only.'}
Return: one line per finding, the gate line, the head sha.`, { label: `fix:${it.key}`, phase: 'Fix', model: 'opus' }).then(r => ({ key: it.key, confirmed: real.length, fix: r }))
  })
return out
