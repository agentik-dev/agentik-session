await parallel([1, 2, 3].map(i => () => parallel([1, 2, 3].map(j => () => agent('p', { label: 'a', model: 'opus' })))))
