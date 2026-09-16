// ABOUTME: Verifies spawn attribution across concurrent native delegation hooks.
// ABOUTME: Checks unchanged tool outcomes and ignores unrelated child creation.

import assert from 'node:assert/strict'
import test from 'node:test'
import { apply } from '../dist/subagent-trace.js'

test('concurrent child creation retains the correct parent call', async () => {
  const hooks = new Map()
  apply({ on: (event, callback) => hooks.set(event, callback) })
  const recorded = []
  const parent = { id: 'parent', header: {}, append: (type, data) => recorded.push({ type, ...data }) }
  const call = id => ({ name: 'subagent', callId: id, agent: { session: parent } })
  const create = id => hooks.get('session/created')({ id, header: { parentSession: 'parent' } })
  let releaseFirst
  const gate = new Promise(resolve => { releaseFirst = resolve })
  const firstResult = { content: 'first' }
  const first = hooks.get('tools/execute')(call('a'), async () => {
    await gate
    create('child-a')
    return firstResult
  })
  const error = new Error('child failed')
  await assert.rejects(hooks.get('tools/execute')(call('b'), async () => {
    create('child-b')
    throw error
  }), caught => caught === error)
  releaseFirst()
  assert.equal(await first, firstResult)
  create('unrelated')
  await hooks.get('tools/execute')({ ...call('c'), name: 'read' }, async () => create('not-delegated'))
  assert.deepEqual(recorded, [
    { type: 'aec/subagent-spawn', child_session_id: 'child-b', parent_tool_call_id: 'b' },
    { type: 'aec/subagent-spawn', child_session_id: 'child-a', parent_tool_call_id: 'a' },
  ])
})
