import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import {
  OUTPUT_COMMIT_PROTOCOL,
  apply,
  createCommitOutputTool,
  requestOutputCommit,
} from '../dist/index.js'

test('plugin consumes endpoint environment before model tools can inherit it', () => {
  process.env.AEC_BENCH_COMMIT_SOCKET = '/tmp/commit.sock'
  process.env.AEC_BENCH_COMMIT_TOKEN = 'secret'
  let registered

  apply({ tools: { register: tool => { registered = tool } } })

  assert.equal(registered.name, 'aec_commit_output')
  assert.equal(process.env.AEC_BENCH_COMMIT_SOCKET, undefined)
  assert.equal(process.env.AEC_BENCH_COMMIT_TOKEN, undefined)
})

async function withEndpoint(response, action) {
  const directory = await mkdtemp(join(tmpdir(), 'aec-dsh-plugin-test-'))
  const socketPath = join(directory, 'commit.sock')
  let request
  const server = createServer(client => {
    let payload = ''
    client.setEncoding('utf8')
    client.on('data', chunk => {
      payload += chunk
      if (!payload.includes('\n')) return
      request = JSON.parse(payload.slice(0, payload.indexOf('\n')))
      if (response !== undefined) client.end(`${JSON.stringify(response)}\n`)
    })
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(socketPath, resolve)
  })
  try {
    await action({ socketPath, request: () => request })
  } finally {
    await new Promise(resolve => server.close(resolve))
    await rm(directory, { recursive: true, force: true })
  }
}

function execution(concludeTurn) {
  return {
    callId: 'commit-2',
    signal: new AbortController().signal,
    agent: {
      id: 'root-session',
      session: {
        events: [
          { type: 'step/start', data: { turn: 1, step: 1 } },
          { type: 'step/start', data: { turn: 1, step: 2 } },
        ],
      },
    },
    concludeTurn,
  }
}

test('accepted authority response concludes the turn with fixed no-argument schema', async () => {
  const accepted = { protocol: OUTPUT_COMMIT_PROTOCOL, status: 'accepted', commit_receipt_id: 'receipt-1' }
  await withEndpoint(accepted, async endpoint => {
    let conclusions = 0
    const tool = createCommitOutputTool({ socketPath: endpoint.socketPath, capability: 'secret' })

    const result = await tool.execute({}, execution(() => { conclusions += 1 }))

    assert.deepEqual(result, accepted)
    assert.equal(conclusions, 1)
    assert.deepEqual(tool.parameters, {
      type: 'object',
      properties: {},
      required: [],
      additionalProperties: false,
    })
    assert.equal(endpoint.request().request_id, 'dsh:root-session:commit-2')
    assert.equal(endpoint.request().metadata.aec_model_turn, 2)
    assert.equal(endpoint.request().capability, 'secret')
    assert.equal('path' in endpoint.request(), false)
  })
})

test('rejected authority response remains nonterminal', async () => {
  const rejected = { protocol: OUTPUT_COMMIT_PROTOCOL, status: 'rejected', diagnostics: [] }
  await withEndpoint(rejected, async endpoint => {
    let conclusions = 0
    const tool = createCommitOutputTool({ socketPath: endpoint.socketPath, capability: 'secret' })

    const result = await tool.execute({}, execution(() => { conclusions += 1 }))

    assert.deepEqual(result, rejected)
    assert.equal(conclusions, 0)
  })
})

test('cancellation closes an in-flight endpoint request', async () => {
  await withEndpoint(undefined, async endpoint => {
    const controller = new AbortController()
    const pending = requestOutputCommit(
      { socketPath: endpoint.socketPath, capability: 'secret' },
      { sessionId: 'root', toolCallId: 'commit-1', modelTurn: 1 },
      controller.signal,
    )
    controller.abort()

    await assert.rejects(pending, /cancelled/)
  })
})
