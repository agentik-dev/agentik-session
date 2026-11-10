const go = async (topic, r = agent(`design ${topic}`, { label: 'design', model: 'fable' })) => r
await parallel(['a', 'b', 'c', 'd', 'e', 'f'].map(t => () => go(t)))
