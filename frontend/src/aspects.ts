// These limits and rules mirror the backend (ProductDetails). The server stays the
// authority; this only keeps the form from sending something it would reject.
export const MAX_ASPECT_LENGTH = 40
export const MAX_NAME_LENGTH = 100

export function collapseSpaces(raw: string): string {
  return raw.split(/\s+/).filter(Boolean).join(' ')
}

export function normalizeAspect(raw: string): string {
  return collapseSpaces(raw).toLowerCase()
}

export interface AddResult {
  aspects: string[]
  /** why nothing was added, or null when it worked or the input was empty */
  error: string | null
}

export function addAspect(current: string[], raw: string, max: number): AddResult {
  const aspect = normalizeAspect(raw)
  if (aspect === '') {
    return { aspects: current, error: null }
  }
  if (aspect.length > MAX_ASPECT_LENGTH) {
    return {
      aspects: current,
      error: `An aspect can have at most ${MAX_ASPECT_LENGTH} characters.`,
    }
  }
  if (current.includes(aspect)) {
    return { aspects: current, error: `"${aspect}" is already in the list.` }
  }
  if (current.length >= max) {
    return { aspects: current, error: `You can use at most ${max} aspects.` }
  }
  return { aspects: [...current, aspect], error: null }
}
