import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import {
  TOOL_GATEWAY_PROTOCOL,
  apply,
  createGatewayTool,
  requestGatewayTool,
} from '../dist/tools.js'

const readTool = {
  name: 'read_workspace_file',
  description: 'Read one visible file.',
  parameters: {
    type: 'object',
    properties: { path: { type: 'string' } },
    required: ['path'],
    additionalProperties: false,
  },
}

const submitTool = {
  name: 'submit_checkpoint',
  description: 'Submit one checkpoint.',
  parameters: {
    type: 'object',
    properties: { checkpoint_id: { type: 'string' } },
    required: ['checkpoint_id'],
    additionalProperties: false,
  },
}

test('plugin registers only manifest tools and consumes private environment', () => {
  process.env.DSH_TOOLS_SOCKET = '/tmp/tools.sock'
  process.env.DSH_TOOLS_TOKEN = 'secret'
  process.env.DSH_TOOLS = JSON.stringify([readTool, submitTool])
  const registered = []

  apply({ tools: { register: tool => { registered.push(tool.name) } } })

  assert.deepEqual(registered, ['read_workspace_file', 'submit_checkpoint'])
  assert.equal(process.env.DSH_TOOLS_SOCKET, undefined)
  assert.equal(process.env.DSH_TOOLS_TOKEN, undefined)
  assert.equal(process.env.DSH_TOOLS, undefined)
})

async function withEndpoint(response, action) {
  const directory = await mkdtemp(join(tmpdir(), 'aec-dsh-tools-test-'))
  const socketPath = join(directory, 'tools.sock')
  let request
  const requests = []
  const server = createServer(client => {
    let payload = ''
    client.setEncoding('utf8')
    client.on('data', chunk => {
      payload += chunk
      if (!payload.includes('\n')) return
      request = JSON.parse(payload.slice(0, payload.indexOf('\n')))
      requests.push(request)
      if (request.operation === 'cancel') {
        client.end(`${JSON.stringify({
          protocol: TOOL_GATEWAY_PROTOCOL,
          status: 'ok',
          result: { outcome: 'unknown' },
        })}\n`)
      } else if (response !== undefined) client.end(`${JSON.stringify(response)}\n`)
    })
  })
  await new Promise((resolve, reject) => {
    server.once('error', reject)
    server.listen(socketPath, resolve)
  })
  try {
    await action({ socketPath, request: () => request, requests: () => requests })
  } finally {
    await new Promise(resolve => server.close(resolve))
    await rm(directory, { recursive: true, force: true })
  }
}

function execution(concludeTurn) {
  return {
    callId: 'tool-2',
    signal: new AbortController().signal,
    agent: {
      id: 'root-session',
      session: { events: [{ type: 'step/start', data: { turn: 1, step: 2 } }] },
    },
    concludeTurn,
  }
}

test('generic conclude-turn disposition concludes for any tool name', async () => {
  const completed = {
    protocol: TOOL_GATEWAY_PROTOCOL,
    status: 'ok',
    result: { status: 'observed' },
    disposition: 'conclude-turn',
  }
  await withEndpoint(completed, async endpoint => {
    let conclusions = 0
    const tool = createGatewayTool(
      { socketPath: endpoint.socketPath, capability: 'secret', tools: [readTool] },
      readTool,
    )

    const result = await tool.execute({ path: 'instruction.md' }, execution(() => { conclusions += 1 }))

    assert.deepEqual(result, { status: 'observed' })
    assert.equal(conclusions, 1)
    assert.equal(endpoint.request().tool, 'read_workspace_file')
    assert.deepEqual(endpoint.request().arguments, { path: 'instruction.md' })
    assert.equal(endpoint.request().operation, 'invoke')
    assert.equal('request_id' in endpoint.request(), false)
  })
})

test('world tool uses the supplied tuple schema and keeps the turn active', async () => {
  const assignmentTool = {
    name: 'request_duty_assignment',
    description: 'Request one ordered duty assignment.',
    parameters: {
      type: 'object',
      properties: { ordered_pump_ids: { type: 'array', items: { type: 'string' } } },
      required: ['ordered_pump_ids'],
      additionalProperties: false,
    },
  }
  const accepted = {
    protocol: TOOL_GATEWAY_PROTOCOL,
    status: 'ok',
    result: { status: 'accepted' },
    disposition: 'continue',
  }
  await withEndpoint(accepted, async endpoint => {
    let conclusions = 0
    const tool = createGatewayTool(
      { socketPath: endpoint.socketPath, capability: 'secret', tools: [assignmentTool] },
      assignmentTool,
    )

    const result = await tool.execute(
      { ordered_pump_ids: ['P-101', 'P-102'] },
      execution(() => { conclusions += 1 }),
    )

    assert.deepEqual(result, { status: 'accepted' })
    assert.equal(conclusions, 0)
    assert.deepEqual(endpoint.request().arguments, { ordered_pump_ids: ['P-101', 'P-102'] })
  })
})

test('generic JSON result can be a scalar', async () => {
  const completed = {
    protocol: TOOL_GATEWAY_PROTOCOL,
    status: 'ok',
    result: 'observed',
    disposition: 'continue',
  }
  await withEndpoint(completed, async endpoint => {
    const tool = createGatewayTool(
      { socketPath: endpoint.socketPath, capability: 'secret', tools: [readTool] },
      readTool,
    )

    const result = await tool.execute({ path: 'instruction.md' }, execution(() => assert.fail('unexpected conclusion')))

    assert.equal(result, 'observed')
    assert.deepEqual(tool.output.schema, {})
  })
})

test('cancellation closes an in-flight tool request', async () => {
  await withEndpoint(undefined, async endpoint => {
    const controller = new AbortController()
    const pending = requestGatewayTool(
      { socketPath: endpoint.socketPath, capability: 'secret', tools: [readTool] },
      'read_workspace_file',
      {},
      { sessionId: 'root', toolCallId: 'tool-1', modelTurn: 1 },
      controller.signal,
    )
    controller.abort()

    await assert.rejects(pending, /cancelled/)
    assert.equal(endpoint.requests().some(request => request.operation === 'cancel'), true)
  })
})
