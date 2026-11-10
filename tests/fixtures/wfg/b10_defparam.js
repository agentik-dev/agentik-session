const run = (r = agent('review the diff', { label: 'review', model: 'opus' })) => r
let n = 0
while (n++ < 20) await run()
