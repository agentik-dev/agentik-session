export const meta = {
  name: 'area-status',
  description: 'Four readers, one checker, one page: six Opus agents, each model named',
  phases: [
    { title: 'Map', detail: 'one reader per area', model: 'opus' },
    { title: 'Check', detail: 'one checker over the four maps', model: 'opus' },
    { title: 'Page', detail: 'one page for the owner', model: 'opus' },
  ],
}
const CONTEXT = `Background: a product split into libraries. Report as verified only what you ran.`
const MAP = { type: 'object', properties: { area: { type: 'string' }, claims: { type: 'array', items: { type: 'string' } } }, required: ['area', 'claims'] }
const AREAS = [
  { key: 'commons', ask: `the service commons: does each module have one home?` },
  { key: 'transport', ask: `the transport: is the handshake in one place?` },
  { key: 'deploy', ask: `the deployment code: which copy does the product build against?` },
  { key: 'inventory', ask: `the inventory: what still lives only in the product?` },
]
phase('Map')
const maps = await parallel(AREAS.map(a => () =>
  agent(`${CONTEXT}\n\nYour area: ${a.ask}\n\nReturn the structured map. Keep each string short.`,
    { label: `map:${a.key}`, phase: 'Map', schema: MAP, model: 'opus' })))
const good = maps.filter(Boolean)

phase('Check')
const checked = await agent(`${CONTEXT}\n\nFour areas were mapped. Rerun the evidence behind each claim:\n${good.map(m => `- ${m.area}: ${m.claims.join('; ')}`).join('\n')}`,
  { label: 'check', phase: 'Check', model: 'opus' })

phase('Page')
const page = await agent(`${CONTEXT}\n\nWrite one status page from the checked maps:\n${checked}`,
  { label: 'page', phase: 'Page', model: 'opus' })
return { areas: good.length, page }
