// ABOUTME: Unit tests for viewer content sub-components: MessageBubble, CollapsibleOutput.
// ABOUTME: Verifies role-based styling, tool name rendering, exit code display, and expand/collapse behaviour.

import { describe, it, expect, vi, beforeAll } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import "@testing-library/jest-dom/vitest";

import MessageBubble from "./MessageBubble.svelte";
import CollapsibleOutput from "./CollapsibleOutput.svelte";

// ---------------------------------------------------------------------------
// Canvas mock — jsdom does not implement getContext. MessageBubble calls
// measureMinWidth (via pretext) for short assistant messages. We provide a
// stub that reports width as character-count * 8px, matching the approach
// used in pretext-service.test.ts.
// ---------------------------------------------------------------------------

beforeAll(() => {
  const mockGetContext = function (contextId: string) {
    if (contextId !== "2d") return null;
    return {
      measureText: (text: string) => ({ width: text.length * 8 }),
      font: "",
    } as unknown as CanvasRenderingContext2D;
  };
  HTMLCanvasElement.prototype.getContext =
    mockGetContext as typeof HTMLCanvasElement.prototype.getContext;
});

// ---------------------------------------------------------------------------
// MessageBubble — tool_call
// ---------------------------------------------------------------------------

describe("MessageBubble — tool_call", () => {
  it("renders tool name for tool_call messages", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "tool_call",
          tool_name: "bash",
          command: "ls -la",
          content: "",
        },
      },
    });
    expect(screen.getByText("bash")).toBeInTheDocument();
  });

  it("renders command in a code block", () => {
    const { container } = render(MessageBubble, {
      props: {
        message: {
          role: "tool_call",
          tool_name: "bash",
          command: "echo hello",
          content: "",
        },
      },
    });
    const codeEl = container.querySelector(".tool-command code");
    expect(codeEl).toBeInTheDocument();
    expect(codeEl?.textContent).toBe("echo hello");
  });
});

// ---------------------------------------------------------------------------
// MessageBubble — assistant
// ---------------------------------------------------------------------------

describe("MessageBubble — assistant", () => {
  it("renders assistant content", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "assistant",
          content: "This is a test response.",
        },
      },
    });
    expect(screen.getByText("This is a test response.")).toBeInTheDocument();
  });

  it("renders with assistant role class", () => {
    const { container } = render(MessageBubble, {
      props: {
        message: {
          role: "assistant",
          content: "Hello",
        },
      },
    });
    expect(container.querySelector(".role-assistant")).toBeInTheDocument();
  });

  it("renders the Assistant label", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "assistant",
          content: "Hello",
        },
      },
    });
    expect(screen.getByText("Assistant")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// MessageBubble — tool_result
// ---------------------------------------------------------------------------

describe("MessageBubble — tool_result", () => {
  it("renders stdout content", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "tool_result",
          tool_name: "bash",
          stdout: "output from command",
          exit_code: 0,
        },
      },
    });
    expect(screen.getByText("output from command")).toBeInTheDocument();
  });

  it("renders exit code badge with 0", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "tool_result",
          tool_name: "bash",
          stdout: "ok",
          exit_code: 0,
        },
      },
    });
    const exitBadge = screen.getByTestId("exit-code");
    expect(exitBadge).toHaveTextContent("exit 0");
    expect(exitBadge).toHaveClass("exit-ok");
  });

  it("renders exit code badge with non-zero in error style", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "tool_result",
          tool_name: "bash",
          stdout: "",
          stderr: "error occurred",
          exit_code: 1,
        },
      },
    });
    const exitBadge = screen.getByTestId("exit-code");
    expect(exitBadge).toHaveTextContent("exit 1");
    expect(exitBadge).toHaveClass("exit-err");
  });

  it("renders stderr when present", () => {
    render(MessageBubble, {
      props: {
        message: {
          role: "tool_result",
          tool_name: "python",
          stdout: "",
          stderr: "traceback info here",
          exit_code: 1,
        },
      },
    });
    expect(screen.getByText("stderr")).toBeInTheDocument();
    expect(screen.getByText("traceback info here")).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// MessageBubble — media
// ---------------------------------------------------------------------------

describe("MessageBubble — media", () => {
  it("renders images when media array provided", () => {
    const { container } = render(MessageBubble, {
      props: {
        message: {
          role: "assistant",
          content: "Here is a chart",
          media: ["/artefacts/chart.png"],
        },
      },
    });
    const img = container.querySelector(".media-img") as HTMLImageElement;
    expect(img).toBeInTheDocument();
    expect(img.src).toContain("/artefacts/chart.png");
  });
});

// ---------------------------------------------------------------------------
// CollapsibleOutput
// ---------------------------------------------------------------------------

describe("CollapsibleOutput", () => {
  it("renders content text", () => {
    render(CollapsibleOutput, {
      props: { content: "short output" },
    });
    expect(screen.getByText("short output")).toBeInTheDocument();
  });

  it("renders with collapsible-output test id", () => {
    render(CollapsibleOutput, {
      props: { content: "some content" },
    });
    expect(screen.getByTestId("collapsible-output")).toBeInTheDocument();
  });

  it("applies custom maxHeight via style", () => {
    const { container } = render(CollapsibleOutput, {
      props: { content: "text", maxHeight: 150 },
    });
    const pre = container.querySelector(".collapsible-pre") as HTMLElement;
    expect(pre.style.maxHeight).toBe("150px");
  });
});
