const assert = require('node:assert/strict')
const test = require('node:test')
const fs = require('node:fs')
const path = require('node:path')
const ts = require('../node_modules/typescript')

function loadQueue() {
  const sourcePath = path.join(__dirname, '..', 'src', 'utils', 'ai-process-queue.ts')
  const source = fs.readFileSync(sourcePath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText
  const module = { exports: {} }
  new Function('exports', 'require', 'module', '__filename', '__dirname', output)(
    module.exports,
    require,
    module,
    sourcePath,
    path.dirname(sourcePath),
  )
  return module.exports
}

test('runSequentially waits for each item before starting the next item', async () => {
  const { runSequentially } = loadQueue()
  const events = []
  let releaseFirst
  const firstFinished = new Promise((resolve) => { releaseFirst = resolve })

  const execution = runSequentially(['first', 'second'], async (item) => {
    events.push(`start:${item}`)
    if (item === 'first') {
      await firstFinished
    }
    events.push(`end:${item}`)
    return item
  })

  await Promise.resolve()
  assert.deepEqual(events, ['start:first'])
  releaseFirst()
  assert.deepEqual(await execution, [
    { status: 'fulfilled', value: 'first' },
    { status: 'fulfilled', value: 'second' },
  ])
  assert.deepEqual(events, ['start:first', 'end:first', 'start:second', 'end:second'])
})

test('runSequentially keeps processing later items after an item fails', async () => {
  const { runSequentially } = loadQueue()
  const processed = []

  const results = await runSequentially(['first', 'second'], async (item) => {
    processed.push(item)
    if (item === 'first') throw new Error('failed')
    return 'complete'
  })

  assert.deepEqual(processed, ['first', 'second'])
  assert.equal(results[0].status, 'rejected')
  assert.equal(results[1].status, 'fulfilled')
})
