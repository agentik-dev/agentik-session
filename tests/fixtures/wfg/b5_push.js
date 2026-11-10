const L = ['a']
L['push']('b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l')
await parallel(L.map(k => () => agent(`area ${k}`, { label: 'x', model: 'opus' })))
