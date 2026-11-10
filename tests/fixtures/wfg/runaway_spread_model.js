export const meta = {
  name: 'removal-trial',
  description: 'Opus only: map, plan, trial, check, pack',
  phases: [
    { title: 'Map', detail: 'three readers over the old engine', model: 'opus' },
    { title: 'Plan', detail: 'the rows in order', model: 'opus' },
    { title: 'Trial', detail: 'move, delete, make it green', model: 'opus' },
    { title: 'Check', detail: 'three checkers, each with a reproduction', model: 'opus' },
    { title: 'Pack', detail: 'fix what was reproduced, write the note', model: 'opus' },
  ],
}
const O = { model: 'opus' }
const CL = '/tmp/example/clone'
const COMMON = `You work in the clone ${CL}. Report as verified only what you ran.`
const MAPS = [
  ['uses', `Inventory the old engine and everything that still reaches it.`],
  ['starts', `List every start that still goes through the old engine.`],
  ['tests', `List the tests that leave with it and those that must move.`],
]
phase('Map')
const maps = await parallel(MAPS.map(m => () => agent(`${COMMON}\nYour label: map-${m[0]}. Read only. ${m[1]}\nReturn at most 40 lines.`, { label: `map:${m[0]}`, phase: 'Map', ...O })))

phase('Plan')
const plan = await agent(`${COMMON}
Your label: plan. Three maps follow.
${maps.map((m, i) => `=== ${MAPS[i][0]}\n${m || '(no report: read the clone yourself)'}`).join('\n')}
Write the plan to ${CL}/plan.md.`, { label: 'plan', phase: 'Plan', ...O })

phase('Trial')
const t1 = await agent(`${COMMON}\nYour label: trial-moves. Build the rows before the deletion.`, { label: 'trial:moves', phase: 'Trial', ...O })
const t2 = await agent(`${COMMON}\nYour label: trial-delete. Delete the old engine's packages.\nBefore: ${t1}`, { label: 'trial:delete', phase: 'Trial', ...O })
const t3 = await agent(`${COMMON}\nYour label: trial-green. Make the whole repo build and pass.\nBefore: ${t2}`, { label: 'trial:green', phase: 'Trial', ...O })

phase('Check')
const FIND = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: {
  title: { type: 'string' }, file: { type: 'string' }, repro: { type: 'string' } }, required: ['title', 'file', 'repro'] } }, checked: { type: 'string' } }, required: ['findings', 'checked'] }
const CHECKS = [
  ['build', `The whole repo builds, vets and passes its tests with the race detector.`],
  ['wire', `The wire is unchanged: the same methods and types as before.`],
  ['dead', `Nothing dead is left: no file, test or doc still names the old engine.`],
]
const checks = await parallel(CHECKS.map(c => () => agent(`${COMMON}\nYour label: check-${c[0]}. You are a checker: change nothing. ${c[1]}`, { label: `check:${c[0]}`, phase: 'Check', schema: FIND, ...O })))
const findings = checks.filter(Boolean).flatMap(c => c.findings)

phase('Pack')
const pack = await agent(`${COMMON}
Your label: pack. Fix each finding below, then write the patch series and the note.
${findings.length ? findings.map((f, i) => `${i + 1}. ${f.title} (${f.file})\n   repro: ${f.repro}`).join('\n') : '(none)'}`, { label: 'pack', phase: 'Pack', ...O })
return { plan: (plan || '').slice(0, 3000), moves: t1, del: t2, green: t3, findings: findings.length, note: pack }
