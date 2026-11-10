const AREAS = ['commons', 'transport', 'deploy']
const ROLE = 'Report only what you ran.'
phase('Map')
const maps = await parallel(AREAS.map(a => () =>
  agent(`${ROLE} Area ${a} of ${AREAS.length}: ${AREAS.join(', ')}`,
    { label: `map:${a}`, phase: 'Map', model: 'opus' })))
const lines = []
for (const m of maps) { lines.push(String(m.ok).replace(/\s+/g, ' ')) }
maps.forEach(m => lines.push('x'))
const half = maps.filter(Boolean).length / 2
let check = null
try {
  check = await agent(`check ${lines.join('\n')} ${half}`, { label: 'check', model: 'opus' })
} catch (e) {
  check = null
}
const extra = check ? await agent('extra', { label: 'extra', model: 'sonnet' }) : null
if (!extra) {
  await agent('fallback', { label: 'fallback', model: 'haiku' })
}
const { ok } = await agent('page', {
  label: 'page',
  model: 'claude-opus-5-5[1m]',
})
return { ok, n: AREAS.length }
