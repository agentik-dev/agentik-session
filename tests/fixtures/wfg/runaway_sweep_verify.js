export const meta = {
  name: 'sweep-and-verify',
  description: 'Six finders, each finding checked, then one page',
  phases: [
    { title: 'Sweep', detail: 'six finders, each a different angle' },
    { title: 'Verify', detail: 'each finding checked against the repos' },
    { title: 'Page', detail: 'one page for the owner' },
  ],
}
const OUT = '/tmp/example/briefs/s2'
const COMMON = `
You are read only: change no file in any repo. Write only under ${OUT}/<your label>/.
The owner's ask, verbatim: "look for anything held twice."
`
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, kind: { type: 'string', description: 'code | concept | record' },
  evidence: { type: 'string', description: 'the command run and what it showed' } },
  required: ['title', 'kind', 'evidence'] } } }, required: ['findings'] }
const ANGLES = [
  ['code', 'Code held twice. Compare file names, function names and test names.'],
  ['concept', 'One concept computed in two places.'],
  ['record', 'Records held twice. Compare the ledgers and the designs.'],
  ['tooling', 'Tooling held twice: makefiles, scripts, gates.'],
  ['effort', 'Work done twice, from git log of the last 21 days.'],
  ['roles', 'Roles held twice between two sessions.'],
]
const VERD = { type: 'object', properties: { real: { type: 'boolean' }, corrected: { type: 'string' } }, required: ['real', 'corrected'] }

const swept = await pipeline(ANGLES,
  a => agent(`${COMMON}\nYour label: ${a[0]}. Your angle: ${a[1]}\nReturn at most ten findings, largest first.`, { label: `sweep:${a[0]}`, phase: 'Sweep', schema: FIND }),
  (r, a) => r ? parallel(r.findings.map((f, i) => () => agent(`${COMMON}\nYour label: v-${a[0]}-${i}. Check this claim by running the evidence yourself.\n${f.title} [${f.kind}]\nevidence: ${f.evidence}`, { label: `verify:${a[0]}-${i}`, phase: 'Verify', schema: VERD }).then(v => v && v.real ? { ...f, ...v } : null))) : [])
const real = swept.filter(Boolean).flat().filter(Boolean).filter(f => f.real)
log(`${real.length} verified`)

const upg = await agent(`${COMMON}\nYour label: upgrade-data. A separate question, from the code alone.`, { label: 'upgrade-data', phase: 'Page' })

const page = await agent(`${COMMON}\nYour label: page. Write one page, at most 70 lines, to ${OUT}/page.md:\n${real.map((f, i) => `${i + 1}. ${f.title}: ${f.corrected}`).join('\n')}`, { label: 'page', phase: 'Page' })
return { count: real.length, page, upgrade: upg }
