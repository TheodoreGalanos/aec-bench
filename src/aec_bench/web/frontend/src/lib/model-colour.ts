// ABOUTME: Shared model→colour mapping for consistent badge colouring across the UI.
// ABOUTME: Uses CSS var hex equivalents; kept in sync with theme.css --model-* tokens.

export function modelColour(model: string): string {
  if (model.includes("sonnet-4")) return "#3cb2b1";
  if (model.includes("sonnet")) return "#89c925";
  if (model.includes("haiku")) return "#2d4a5e";
  if (model.includes("gpt") && model.includes("mini")) return "#e4572e";
  return "#4a6741";
}
