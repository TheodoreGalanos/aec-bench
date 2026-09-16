// AEC-Bench's explicit Prime extension carries call identity into the kernel.
// The IPython hook removes this transport comment before Python or magic parsing.
export default function (pi) {
  pi.on("tool_call", (event, ctx) => {
    if (event.toolName !== "ipython" || typeof event.input.code !== "string") return;
    const identity = Buffer.from(JSON.stringify({
      parent_session_id: ctx.sessionManager.getSessionId(),
      parent_tool_call_id: event.toolCallId,
    })).toString("base64");
    // Keep a leading %%bash line intact for Prime's shell-settings transform.
    event.input.code = `${event.input.code}\n# aec-bench-prime-call ${identity}\n`;
  });
}
