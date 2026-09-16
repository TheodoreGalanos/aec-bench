// Exercise the packaged extension and startup hook in an installed Prime kernel.
// Only the rlm.run host boundary is replaced; no model or credentials are used.
import assert from "node:assert/strict";
import { mkdir, readFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { join } from "node:path";

const [primeRoot, python, root, hookPath] = process.argv.slice(2);
const { KernelManager } = await import(pathToFileURL(join(primeRoot, "dist/core/kernel/index.js")));
const { DefaultResourceLoader } = await import(pathToFileURL(join(primeRoot, "dist/core/resource-loader.js")));
const loader = new DefaultResourceLoader({
  cwd: root, agentDir: join(root, "state"), noExtensions: true, additionalExtensionPaths: [hookPath],
  noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true,
});
await loader.reload();
const loaded = loader.getExtensions();
assert.deepEqual(loaded.errors, []);
assert.equal(loaded.extensions.length, 1);
const handler = loaded.extensions[0].handlers.get("tool_call")[0];
const tag = (callId, code, sessionId = "root") => {
  const event = { toolName: "ipython", toolCallId: callId, input: { code } };
  handler(event, { sessionManager: { getSessionId: () => sessionId } });
  return event.input.code;
};
const calls = [];
const kernel = new KernelManager({
  python,
  cwd: root,
  env: {
    IPYTHONDIR: join(root, "spawn-hook/ipython"),
    AEC_BENCH_PRIME_SESSION_ROOT: join(root, "sessions"),
  },
  hostHandlers: {
    "rlm.run": async (request) => {
      calls.push(request.prompt);
      const directory = join(root, "sessions", request.prompt);
      await mkdir(directory, { recursive: true });
      if (request.prompt === "slow") await new Promise((resolve) => setTimeout(resolve, 100));
      return { rlm_child_id: request.prompt, session_dir: directory, name: request.prompt, model: "test" };
    },
  },
});
async function execute(callId, code) {
  console.log(`Executing ${callId}`);
  const result = await kernel.execute(tag(callId, code));
  assert.equal(result.status, "ok", JSON.stringify(result));
  return result;
}
try {
  console.log("Starting Prime kernel");
  await kernel.start();
  assert.equal((await execute("expression", "40 + 2")).result, "42");
  assert.equal((await execute("suppressed-expression", "40 + 2;")).result, undefined);
  assert.ok(tag("bash", "%%bash\nprintf 'magic-ok'\n").startsWith("%%bash\n"));
  assert.equal((await execute("bash", "%%bash\nprintf 'magic-ok'\n")).stdout, "magic-ok");
  await execute("origin", `import asyncio, rlm
gate = asyncio.Event()
async def later():
    await gate.wait()
    return await rlm.run("delayed")
pending = asyncio.create_task(later())`);
  await execute("next", `gate.set()
await asyncio.gather(rlm.run("slow"), rlm.run("fast"), pending)`);
  for (const [child, callId] of [["delayed", "origin"], ["slow", "next"], ["fast", "next"]]) {
    const evidence = JSON.parse(await readFile(join(root, "sessions", child, "aec-spawn.json"), "utf8"));
    assert.deepEqual(evidence, { parent_session_id: "root", parent_tool_call_id: callId, rlm_child_id: child });
  }
  assert.deepEqual(calls.sort(), ["delayed", "fast", "slow"]);
  const failure = await kernel.execute(tag("failed-cell", "raise ValueError('expected')"));
  assert.equal(failure.status, "error");
  assert.equal(failure.error.ename, "ValueError");
  console.log("Prime kernel hook: expression, bash magic, concurrent and delayed spawns, and Python error passed");
} finally {
  await kernel.dispose();
}
