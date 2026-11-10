const R = await parallel([
  () => agent('read a', { label: 'a', model: 'opus' }),
  () => agent('read b', { label: 'b', model: 'opus' }),
  () => agent('read c', { label: 'c', model: 'opus' }),
  () => agent('read d', { label: 'd', model: 'opus' }),
])
const AREAS = ['x', 'y']
const more = await parallel(AREAS.map(a => () => agent(`area ${a}`, { label: `m:${a}`, model: 'opus' })))
return { n: R.length + more.length }
