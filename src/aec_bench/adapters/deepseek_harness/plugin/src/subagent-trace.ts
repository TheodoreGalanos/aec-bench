// ABOUTME: Records the tool call that creates each native DeepSeek child session.
// ABOUTME: Uses public Cordis hooks and preserves tool results, errors, and cancellation.

import { AsyncLocalStorage } from 'node:async_hooks'

export const name = '@aec-bench/dsh-subagent-trace'
export const inject = ['tools']

interface Session {
  readonly id: string
  readonly header: { readonly parentSession?: string }
  append(type: string, data: Record<string, string>): unknown
}

interface Execution {
  readonly name: string
  readonly callId: string
  readonly agent?: { readonly session: Session }
}

interface CordisContext {
  on(event: 'tools/execute', callback: (exec: Execution, next: () => Promise<unknown>) => Promise<unknown>): unknown
  on(event: 'session/created', callback: (session: Session) => void): unknown
}

export function apply(ctx: CordisContext): void {
  const calls = new AsyncLocalStorage<Execution>()
  ctx.on('tools/execute', (exec, next) =>
    exec.name === 'subagent' ? calls.run(exec, next) : next())
  ctx.on('session/created', child => {
    const call = calls.getStore()
    const parent = call?.agent?.session
    if (parent === undefined || call === undefined || child.header.parentSession !== parent.id) return
    parent.append('aec/subagent-spawn', {
      child_session_id: child.id,
      parent_tool_call_id: call.callId,
    })
  })
}
