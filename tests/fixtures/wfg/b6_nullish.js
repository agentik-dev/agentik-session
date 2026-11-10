const L = ['a', 'b']
L[11] ??= 'z'; L[10] ??= 'y'; L[9] ??= 'x'; L[8] ??= 'w'; L[7] ??= 'v'; L[6] ??= 'u'; L[5] ??= 't'; L[4] ??= 's'; L[3] ??= 'r'; L[2] ??= 'q'
await parallel(L.map(k => () => agent(`area ${k}`, { label: 'x', model: 'opus' })))
