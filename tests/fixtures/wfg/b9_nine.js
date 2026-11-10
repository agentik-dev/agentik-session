await parallel([1, 2, 3, 4, 5, 6, 7, 8, 9].map(i => () => agent('p', { label: 'a', model: 'opus' })))
