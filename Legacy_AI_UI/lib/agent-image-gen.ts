/**
 * Heuristic for "this agent generates images itself" — there's no dedicated
 * capability flag or tool in the catalog for it (the model produces the image
 * inline), so the only signal available anywhere in the app is the agent's
 * own name/description text, same as what's shown on its picker card.
 */
export function looksLikeImageGenAgent(...texts: Array<string | null | undefined>): boolean {
  const combined = texts.filter(Boolean).join(' ')
  return /\bimage\b/i.test(combined) && /\bgenerat/i.test(combined)
}

/** Truncates a long user prompt for display inside the ImageGeneration widget. */
export function truncatePromptForDisplay(prompt: string | null | undefined, maxLength = 80): string | undefined {
  if (!prompt) return undefined
  return prompt.length > maxLength ? `${prompt.slice(0, maxLength - 3)}...` : prompt
}
