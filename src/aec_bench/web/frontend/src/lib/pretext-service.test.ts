// ABOUTME: Unit tests for the shared pretext service singleton.
// ABOUTME: Mocks Canvas since jsdom does not provide a real rendering context.

import { describe, it, expect, beforeAll, beforeEach } from "vitest";
import {
  FONT_STRINGS,
  LINE_HEIGHTS,
  measureText,
  measureMinWidth,
  clearCache,
  getDefaultLineHeight,
  isFontsReady,
  type FontPreset,
} from "./pretext-service";

// ---------------------------------------------------------------------------
// Canvas mock — jsdom provides HTMLCanvasElement but getContext returns null.
// Pretext uses canvas.measureText internally; we return a stub that reports
// width as character-count * 8px (a rough approximation sufficient for tests).
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

beforeEach(() => {
  clearCache();
});

// ---------------------------------------------------------------------------
// FONT_STRINGS
// ---------------------------------------------------------------------------

describe("FONT_STRINGS", () => {
  it("maps body to Plus Jakarta Sans", () => {
    expect(FONT_STRINGS.body).toContain("Plus Jakarta Sans");
    expect(FONT_STRINGS.body).toContain("15px");
  });

  it("maps mono to JetBrains Mono", () => {
    expect(FONT_STRINGS.mono).toContain("JetBrains Mono");
    expect(FONT_STRINGS.mono).toContain("13.12px");
  });

  it("maps heading to Outfit", () => {
    expect(FONT_STRINGS.heading).toContain("Outfit");
    expect(FONT_STRINGS.heading).toContain("15.2px");
  });

  it("has entries for all three presets", () => {
    const presets: FontPreset[] = ["body", "mono", "heading"];
    for (const preset of presets) {
      expect(FONT_STRINGS[preset]).toBeTruthy();
    }
  });
});

// ---------------------------------------------------------------------------
// LINE_HEIGHTS
// ---------------------------------------------------------------------------

describe("LINE_HEIGHTS", () => {
  it("has correct default for body", () => {
    expect(LINE_HEIGHTS.body).toBe(24);
  });

  it("has correct default for mono", () => {
    expect(LINE_HEIGHTS.mono).toBe(19.68);
  });

  it("has correct default for heading", () => {
    expect(LINE_HEIGHTS.heading).toBe(19.76);
  });
});

// ---------------------------------------------------------------------------
// getDefaultLineHeight
// ---------------------------------------------------------------------------

describe("getDefaultLineHeight", () => {
  it("returns correct value for each preset", () => {
    expect(getDefaultLineHeight("body")).toBe(24);
    expect(getDefaultLineHeight("mono")).toBe(19.68);
    expect(getDefaultLineHeight("heading")).toBe(19.76);
  });
});

// ---------------------------------------------------------------------------
// measureText
// ---------------------------------------------------------------------------

describe("measureText", () => {
  it("returns zero height and zero lineCount for empty string", () => {
    const result = measureText("", "body", 400, 24);
    expect(result.height).toBe(0);
    expect(result.lineCount).toBe(0);
  });

  it("returns positive height and lineCount for non-empty text", () => {
    const result = measureText("Hello world", "body", 400, 24);
    expect(result.height).toBeGreaterThan(0);
    expect(result.lineCount).toBeGreaterThan(0);
  });

  it("returns greater height for longer text at the same width", () => {
    const shortText = "Hi";
    const longText =
      "This is a much longer piece of text that should wrap across multiple lines " +
      "when rendered at a narrow container width, producing more total height.";
    const short = measureText(shortText, "body", 300, 24);
    const long = measureText(longText, "body", 300, 24);
    expect(long.height).toBeGreaterThanOrEqual(short.height);
  });

  it("returns greater height at narrower width for the same text", () => {
    const text =
      "This sentence will wrap more at narrow widths than at wide widths.";
    const wide = measureText(text, "body", 800, 24);
    const narrow = measureText(text, "body", 150, 24);
    expect(narrow.height).toBeGreaterThanOrEqual(wide.height);
  });

  it("handles mono preset without throwing", () => {
    const result = measureText("const x = 42;\nconst y = 0;", "mono", 400, 19.68);
    expect(result.height).toBeGreaterThan(0);
  });

  it("handles heading preset without throwing", () => {
    const result = measureText("Section Title", "heading", 400, 19.76);
    expect(result.height).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// measureMinWidth
// ---------------------------------------------------------------------------

describe("measureMinWidth", () => {
  it("returns zero for empty string", () => {
    const result = measureMinWidth("", "body", 400, 24);
    expect(result).toBe(0);
  });

  it("returns a value <= maxWidth", () => {
    const result = measureMinWidth("Hello world", "body", 400, 24);
    expect(result).toBeLessThanOrEqual(400);
  });

  it("returns a smaller width for short text than for long text", () => {
    const shortWidth = measureMinWidth("Hi", "body", 400, 24);
    const longWidth = measureMinWidth(
      "This is a much longer sentence that takes up more horizontal space",
      "body",
      400,
      24,
    );
    expect(shortWidth).toBeLessThanOrEqual(longWidth);
  });

  it("returns a positive value for non-empty text", () => {
    const result = measureMinWidth("Hello", "body", 400, 24);
    expect(result).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// isFontsReady
// ---------------------------------------------------------------------------

describe("isFontsReady", () => {
  it("returns false by default in jsdom (no fonts loaded)", () => {
    expect(isFontsReady()).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// clearCache
// ---------------------------------------------------------------------------

describe("clearCache", () => {
  it("does not throw when called on an empty cache", () => {
    expect(() => clearCache()).not.toThrow();
  });

  it("does not throw when called after measurements", () => {
    measureText("some text", "body", 400, 24);
    expect(() => clearCache()).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Caching — same inputs return identical results
// ---------------------------------------------------------------------------

describe("caching", () => {
  it("returns identical results for the same inputs on repeated calls", () => {
    const first = measureText("Hello world", "body", 400, 24);
    const second = measureText("Hello world", "body", 400, 24);
    expect(second.height).toBe(first.height);
    expect(second.lineCount).toBe(first.lineCount);
  });

  it("returns identical min-width results for repeated calls", () => {
    const first = measureMinWidth("Hello world", "body", 400, 24);
    const second = measureMinWidth("Hello world", "body", 400, 24);
    expect(second).toBe(first);
  });
});
