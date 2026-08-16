import { createConnection } from 'node:net';
export const name = '@aec-bench/dsh-output-commit';
export const inject = ['tools'];
export const OUTPUT_COMMIT_PROTOCOL = 'aec-bench/output-commit/1';
const SOCKET_ENV = 'AEC_BENCH_COMMIT_SOCKET';
const TOKEN_ENV = 'AEC_BENCH_COMMIT_TOKEN';
const MAX_RESPONSE_BYTES = 64 * 1024;
const REQUEST_TIMEOUT_MS = 10_000;
export function apply(ctx) {
    const config = readConfig(process.env);
    delete process.env[SOCKET_ENV];
    delete process.env[TOKEN_ENV];
    ctx.tools.register(createCommitOutputTool(config));
}
export function readConfig(environment) {
    const socketPath = environment[SOCKET_ENV];
    const capability = environment[TOKEN_ENV];
    if (socketPath === undefined || socketPath.length === 0) {
        throw new Error(`${SOCKET_ENV} is required`);
    }
    if (capability === undefined || capability.length === 0) {
        throw new Error(`${TOKEN_ENV} is required`);
    }
    return { socketPath, capability };
}
export function createCommitOutputTool(config) {
    return {
        name: 'aec_commit_output',
        description: 'Commit the exact task output artifact after its final review.',
        parameters: {
            type: 'object',
            properties: {},
            required: [],
            additionalProperties: false,
        },
        output: {
            schema: { type: 'object', additionalProperties: true },
            render: (_args, value) => [{ type: 'text', text: JSON.stringify(value) }],
        },
        async execute(_args, exec) {
            const agent = exec.agent;
            if (agent === undefined)
                throw new Error('aec_commit_output requires an active agent');
            const response = await requestOutputCommit(config, {
                sessionId: agent.id,
                toolCallId: String(exec.callId),
                modelTurn: currentModelTurn(agent.session.events),
            }, exec.signal);
            if (response.status === 'accepted')
                exec.concludeTurn();
            return response;
        },
    };
}
export function currentModelTurn(events) {
    for (let index = events.length - 1; index >= 0; index -= 1) {
        const event = events[index];
        if (event?.type !== 'step/start')
            continue;
        const step = event.data?.['step'];
        if (typeof step === 'number' && Number.isSafeInteger(step) && step > 0)
            return step;
    }
    throw new Error('aec_commit_output could not resolve the current model turn');
}
export async function requestOutputCommit(config, identity, signal) {
    if (signal.aborted)
        throw new Error('output commit request cancelled');
    const payload = JSON.stringify({
        protocol: OUTPUT_COMMIT_PROTOCOL,
        capability: config.capability,
        request_id: `dsh:${identity.sessionId}:${identity.toolCallId}`,
        operation: 'commit',
        metadata: {
            deepseek_session_id: identity.sessionId,
            deepseek_tool_call_id: identity.toolCallId,
            aec_model_turn: identity.modelTurn,
        },
    }) + '\n';
    return new Promise((resolve, reject) => {
        const socket = createConnection(config.socketPath);
        let settled = false;
        let received = Buffer.alloc(0);
        const finish = (error, response) => {
            if (settled)
                return;
            settled = true;
            signal.removeEventListener('abort', cancel);
            socket.destroy();
            if (error !== null)
                reject(error);
            else if (response !== undefined)
                resolve(response);
        };
        const cancel = () => finish(new Error('output commit request cancelled'));
        signal.addEventListener('abort', cancel, { once: true });
        if (signal.aborted) {
            cancel();
            return;
        }
        socket.setTimeout(REQUEST_TIMEOUT_MS, () => finish(new Error('output commit request timed out')));
        socket.once('connect', () => socket.write(payload));
        socket.on('data', chunk => {
            received = Buffer.concat([received, chunk]);
            if (received.length > MAX_RESPONSE_BYTES) {
                finish(new Error('output commit response is too large'));
                return;
            }
            const newline = received.indexOf(0x0a);
            if (newline < 0)
                return;
            try {
                finish(null, parseResponse(received.subarray(0, newline).toString('utf8')));
            }
            catch (error) {
                finish(error instanceof Error ? error : new Error('invalid output commit response'));
            }
        });
        socket.once('error', error => finish(error));
        socket.once('end', () => {
            if (!settled)
                finish(new Error('output commit authority closed without a response'));
        });
    });
}
function parseResponse(payload) {
    const value = JSON.parse(payload);
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
        throw new Error('output commit response must be an object');
    }
    const response = value;
    if (response['protocol'] !== OUTPUT_COMMIT_PROTOCOL) {
        throw new Error('output commit response has an unsupported protocol');
    }
    if (!['accepted', 'rejected', 'error'].includes(String(response['status']))) {
        throw new Error('output commit response has an invalid status');
    }
    return response;
}
