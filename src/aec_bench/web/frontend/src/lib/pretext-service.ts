// ABOUTME: Shared singleton service wrapping @chenglou/pretext for text measurement.
// ABOUTME: Provides font preset mappings, cached prepare/layout calls, and min-width binary search.

import {
  prepare,
  prepareWithSegments,
  layout,
  walkLineRanges,
  clearCache as pretextClearCache,
  type PreparedText,
} from "@chenglou/pretext";

// ---------------------------------------------------------------------------
// Font presets
// ---------------------------------------------------------------------------

export type FontPreset = "body" | "mono" | "heading";

export const FONT_STRINGS: Record<FontPreset, string> = {
  body: "15px 'Plus Jakarta Sans', sans-serif",
  mono: "13.12px 'JetBrains Mono', monospace",
  heading: "15.2px 'Outfit', sans-serif",
};

export const LINE_HEIGHTS: Record<FontPreset, number> = {
  body: 24,
  mono: 19.68,
  heading: 19.76,
};

// ---------------------------------------------------------------------------
// Prepare cache — keyed by "<font>::<text>"
// A separate cache per prepare variant is not needed because the key encodes
// all inputs that affect the PreparedText shape.
// ---------------------------------------------------------------------------

const prepareCache = new Map<string, PreparedText>();
// walkLineRanges requires PreparedTextWithSegments; cache those separately.
const prepareWithSegmentsCache = new Map<
  string,
  ReturnType<typeof prepareWithSegments>
>();

// ---------------------------------------------------------------------------
// Font-readiness state
// ---------------------------------------------------------------------------

let _fontsReady = false;

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export function getDefaultLineHeight(font: FontPreset): number {
  return LINE_HEIGHTS[font];
}

/**
 * Returns true once waitForFonts() has resolved successfully.
 */
export function isFontsReady(): boolean {
  return _fontsReady;
}

/**
 * Waits for all registered document fonts to be loaded.
 * Safe to call multiple times; resolves immediately after first success.
 */
export async function waitForFonts(): Promise<void> {
  if (_fontsReady) return;
  await document.fonts.ready;
  // Explicitly load each font string we rely on to make sure they are active.
  await Promise.all(
    Object.values(FONT_STRINGS).map((f) => document.fonts.load(f)),
  );
  _fontsReady = true;
}

/**
 * Measures the height (px) and line count for `text` laid out at `maxWidth`
 * using the given font string and line height.
 *
 * Returns { height: 0, lineCount: 0 } for empty text.
 * The prepare step is cached: identical (text, font) inputs reuse the same
 * PreparedText. The layout step always runs with the provided maxWidth and lineHeight.
 */
export function measureText(
  text: string,
  font: FontPreset,
  maxWidth: number,
  lineHeight: number,
): { height: number; lineCount: number } {
  if (text === "") return { height: 0, lineCount: 0 };

  const fontString = FONT_STRINGS[font];
  const cacheKey = `${fontString}::${text}`;

  let prepared = prepareCache.get(cacheKey);
  if (prepared === undefined) {
    const options = font === "mono" ? { whiteSpace: "pre-wrap" as const } : undefined;
    prepared = prepare(text, fontString, options);
    prepareCache.set(cacheKey, prepared);
  }

  return layout(prepared, maxWidth, lineHeight);
}

/**
 * Finds the minimum bubble width for `text` that keeps the same line count as
 * rendering at `maxWidth`.
 *
 * For single-line text, uses walkLineRanges to get the exact line width.
 * For multi-line text, performs a binary search between 50px and maxWidth.
 *
 * Returns 0 for empty text.
 */
export function measureMinWidth(
  text: string,
  font: FontPreset,
  maxWidth: number,
  lineHeight: number,
): number {
  if (text === "") return 0;

  const fontString = FONT_STRINGS[font];
  const segsCacheKey = `${fontString}::${text}`;

  let prepared = prepareWithSegmentsCache.get(segsCacheKey);
  if (prepared === undefined) {
    const options = font === "mono" ? { whiteSpace: "pre-wrap" as const } : undefined;
    prepared = prepareWithSegments(text, fontString, options);
    prepareWithSegmentsCache.set(segsCacheKey, prepared);
  }

  const baseResult = layout(prepared, maxWidth, lineHeight);

  if (baseResult.lineCount <= 1) {
    // Single-line: walk to find exact rendered width of that one line.
    let exactWidth = 0;
    walkLineRanges(prepared, maxWidth, (line) => {
      exactWidth = line.width;
    });
    return exactWidth;
  }

  // Multi-line: binary search for smallest width that preserves same lineCount.
  const MIN_BUBBLE_WIDTH_PX = 50; // No bubble is ever rendered narrower than this
  const targetLineCount = baseResult.lineCount;
  let lo = MIN_BUBBLE_WIDTH_PX;
  let hi = maxWidth;

  while (hi - lo > 1) {
    const mid = Math.floor((lo + hi) / 2);
    const result = layout(prepared, mid, lineHeight);
    if (result.lineCount <= targetLineCount) {
      hi = mid;
    } else {
      lo = mid;
    }
  }

  return hi;
}

/**
 * Clears the prepare caches maintained by this service and resets the
 * pretext-internal cache.
 */
export function clearCache(): void {
  prepareCache.clear();
  prepareWithSegmentsCache.clear();
  pretextClearCache();
}
