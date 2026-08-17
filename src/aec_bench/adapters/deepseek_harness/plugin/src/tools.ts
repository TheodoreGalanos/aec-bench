import { createConnection } from 'node:net'

export const name = '@aec-bench/dsh-tools'
export const inject = ['tools']
export const TOOL_GATEWAY_PROTOCOL = 'aec-bench/deepseek-tools/2'

const SOCKET_ENV = 'DSH_TOOLS_SOCKET'
const TOKEN_ENV = 'DSH_TOOLS_TOKEN'
const MANIFEST_ENV = 'DSH_TOOLS'
const MAX_RESPONSE_BYTES = 2 * 1024 * 1024
const REQUEST_TIMEOUT_MS = 120_000

interface SessionEvent {
  readonly type: string
  readonly data?: Record<string, unknown>
}

interface ToolExecution {
  readonly callId: string
  readonly signal: AbortSignal
  readonly agent?: {
    readonly id: string
    readonly session: { readonly events: readonly SessionEvent[] }
  }
  concludeTurn(): void
}

interface ToolDefinition {
  readonly name: string
  readonly description: string
  readonly parameters: Record<string, unknown>
  readonly output: {
    readonly schema: Record<string, unknown>
    render(args: unknown, value: ToolResult): Array<{ type: 'text', text: string }>
  }
  execute(args: unknown, exec: ToolExecution): Promise<ToolResult>
}

interface CordisContext {
  readonly tools: {
    register(definition: ToolDefinition): unknown
  }
}

interface ToolManifest {
  readonly name: string
  readonly description: string
  readonly parameters: Record<string, unknown>
}

interface ToolGatewayConfig {
  readonly socketPath: string
  readonly capability: string
  readonly tools: readonly ToolManifest[]
}

interface ToolIdentity {
  readonly sessionId: string
  readonly toolCallId: string
  readonly modelTurn: number
}

interface ToolGatewayResponse {
  readonly protocol: typeof TOOL_GATEWAY_PROTOCOL
  readonly status: 'ok' | 'error'
  readonly result?: ToolResult
  readonly disposition?: 'continue' | 'conclude-turn'
  readonly error?: { readonly code: string; readonly message: string }
}

export type ToolResult = unknown

export function apply(ctx: CordisContext): void {
  const config = readConfig(process.env)
  delete process.env[SOCKET_ENV]
  delete process.env[TOKEN_ENV]
  delete process.env[MANIFEST_ENV]
  for (const tool of config.tools) ctx.tools.register(createGatewayTool(config, tool))
}

export function readConfig(environment: NodeJS.ProcessEnv): ToolGatewayConfig {
  const socketPath = environment[SOCKET_ENV]
  const capability = environment[TOKEN_ENV]
  const manifestValue = environment[MANIFEST_ENV]
  if (socketPath === undefined || socketPath.length === 0) throw new Error(`${SOCKET_ENV} is required`)
  if (capability === undefined || capability.length === 0) throw new Error(`${TOKEN_ENV} is required`)
  if (manifestValue === undefined || manifestValue.length === 0) throw new Error(`${MANIFEST_ENV} is required`)
  let parsed: unknown
  try {
    parsed = JSON.parse(manifestValue)
  } catch {
    throw new Error(`${MANIFEST_ENV} must contain a JSON array`)
  }
  if (!Array.isArray(parsed) || parsed.length === 0 || !parsed.every(isToolManifest)) {
    throw new Error(`${MANIFEST_ENV} contains an invalid tool manifest`)
  }
  const names = parsed.map(tool => tool.name)
  if (new Set(names).size !== names.length) throw new Error(`${MANIFEST_ENV} contains duplicate tools`)
  return { socketPath, capability, tools: parsed }
}

export function createGatewayTool(config: ToolGatewayConfig, tool: ToolManifest): ToolDefinition {
  return {
    name: tool.name,
    description: tool.description,
    parameters: tool.parameters,
    output: {
      schema: {},
      render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
    },
    async execute(args, exec) {
      const agent = exec.agent
      if (agent === undefined) throw new Error(`${tool.name} requires an active agent`)
      const response = await requestGatewayTool(
        config,
        tool.name,
        asArguments(args),
        {
          sessionId: agent.id,
          toolCallId: String(exec.callId),
          modelTurn: currentModelTurn(agent.session.events),
        },
        exec.signal,
      )
      if (response.status === 'error') return { status: 'error', error: response.error }
      if (response.disposition !== 'continue' && response.disposition !== 'conclude-turn') {
        throw new Error('tool response disposition is invalid')
      }
      const result = response.result ?? { status: 'error', error: { code: 'missing_result' } }
      if (response.disposition === 'conclude-turn') exec.concludeTurn()
      return result
    },
  }
}

export function currentModelTurn(events: readonly SessionEvent[]): number {
  for (let index = events.length - 1; index >= 0; index -= 1) {
    const event = events[index]
    if (event?.type !== 'step/start') continue
    const step = event.data?.['step']
    if (typeof step === 'number' && Number.isSafeInteger(step) && step > 0) return step
  }
  throw new Error('tool gateway could not resolve the current model turn')
}

export async function requestGatewayTool(
  config: ToolGatewayConfig,
  toolName: string,
  argumentsValue: Readonly<Record<string, unknown>>,
  identity: ToolIdentity,
  signal: AbortSignal,
): Promise<ToolGatewayResponse> {
  if (signal.aborted) {
    await requestGatewayCancellation(config, identity).catch(() => undefined)
    throw new Error('tool request cancelled')
  }
  const payload = JSON.stringify({
    protocol: TOOL_GATEWAY_PROTOCOL,
    capability: config.capability,
    operation: 'invoke',
    tool: toolName,
    arguments: argumentsValue,
    metadata: {
      deepseek_session_id: identity.sessionId,
      deepseek_tool_call_id: identity.toolCallId,
      aec_model_turn: identity.modelTurn,
    },
  }) + '\n'

  return new Promise<ToolGatewayResponse>((resolve, reject) => {
    const socket = createConnection(config.socketPath)
    let settled = false
    let received = Buffer.alloc(0)
    const finish = (error: Error | null, response?: ToolGatewayResponse): void => {
      if (settled) return
      settled = true
      signal.removeEventListener('abort', cancel)
      socket.destroy()
      if (error !== null) reject(error)
      else if (response !== undefined) resolve(response)
    }
    const cancel = (): void => {
      if (settled) return
      settled = true
      signal.removeEventListener('abort', cancel)
      socket.destroy()
      void requestGatewayCancellation(config, identity).then(
        () => reject(new Error('tool request cancelled')),
        () => reject(new Error('tool request cancelled')),
      )
    }
    signal.addEventListener('abort', cancel, { once: true })
    if (signal.aborted) {
      cancel()
      return
    }
    socket.setTimeout(REQUEST_TIMEOUT_MS, () => finish(new Error('tool request timed out')))
    socket.once('connect', () => socket.write(payload))
    socket.on('data', chunk => {
      received = Buffer.concat([received, chunk])
      if (received.length > MAX_RESPONSE_BYTES) {
        finish(new Error('tool response is too large'))
        return
      }
      const newline = received.indexOf(0x0a)
      if (newline < 0) return
      try {
        finish(null, parseResponse(received.subarray(0, newline).toString('utf8')))
      } catch (error: unknown) {
        finish(error instanceof Error ? error : new Error('invalid tool response'))
      }
    })
    socket.once('error', error => finish(error))
    socket.once('end', () => {
      if (!settled) finish(new Error('tool authority closed without a response'))
    })
  })
}

export async function requestGatewayCancellation(
  config: ToolGatewayConfig,
  identity: ToolIdentity,
): Promise<ToolGatewayResponse> {
  const payload = JSON.stringify({
    protocol: TOOL_GATEWAY_PROTOCOL,
    capability: config.capability,
    operation: 'cancel',
    metadata: {
      deepseek_session_id: identity.sessionId,
      deepseek_tool_call_id: identity.toolCallId,
      aec_model_turn: identity.modelTurn,
    },
  }) + '\n'

  return new Promise<ToolGatewayResponse>((resolve, reject) => {
    const socket = createConnection(config.socketPath)
    let settled = false
    let received = Buffer.alloc(0)
    const finish = (error: Error | null, response?: ToolGatewayResponse): void => {
      if (settled) return
      settled = true
      socket.destroy()
      if (error !== null) reject(error)
      else if (response !== undefined) resolve(response)
    }
    socket.setTimeout(REQUEST_TIMEOUT_MS, () => finish(new Error('tool cancellation request timed out')))
    socket.once('connect', () => socket.write(payload))
    socket.on('data', chunk => {
      received = Buffer.concat([received, chunk])
      if (received.length > MAX_RESPONSE_BYTES) {
        finish(new Error('tool cancellation response is too large'))
        return
      }
      const newline = received.indexOf(0x0a)
      if (newline < 0) return
      try {
        finish(null, parseResponse(received.subarray(0, newline).toString('utf8')))
      } catch (error: unknown) {
        finish(error instanceof Error ? error : new Error('invalid tool cancellation response'))
      }
    })
    socket.once('error', error => finish(error))
    socket.once('end', () => {
      if (!settled) finish(new Error('tool authority closed without a cancellation response'))
    })
  })
}

function parseResponse(value: string): ToolGatewayResponse {
  const parsed: unknown = JSON.parse(value)
  if (typeof parsed !== 'object' || parsed === null) throw new Error('tool response must be an object')
  const response = parsed as Partial<ToolGatewayResponse>
  if (response.protocol !== TOOL_GATEWAY_PROTOCOL || (response.status !== 'ok' && response.status !== 'error')) {
    throw new Error('tool response protocol is invalid')
  }
  if (response.disposition !== undefined
    && response.disposition !== 'continue'
    && response.disposition !== 'conclude-turn') {
    throw new Error('tool response disposition is invalid')
  }
  return response as ToolGatewayResponse
}

function isToolManifest(value: unknown): value is ToolManifest {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const manifest = value as Partial<ToolManifest>
  return typeof manifest.name === 'string' && /^[A-Za-z_][A-Za-z0-9_]{0,127}$/.test(manifest.name)
    && typeof manifest.description === 'string' && manifest.description.length > 0
    && typeof manifest.parameters === 'object' && manifest.parameters !== null && !Array.isArray(manifest.parameters)
}

function asArguments(value: unknown): Readonly<Record<string, unknown>> {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error('tool arguments must be an object')
  }
  return value as Readonly<Record<string, unknown>>
}
