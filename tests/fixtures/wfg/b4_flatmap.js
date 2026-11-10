await parallel([() => agent('p', { label: 'a', model: 'opus' })].flatMap(f => [f, f, f, f, f, f, f, f, f, f, f, f]))
