// The session id is kept in sessionStorage: it survives a page reload but not a closed
// tab, and it is never shared between tabs. Storage can be unavailable (private mode,
// blocked cookies), in which case the app simply forgets the session on reload.
const KEY = 'reviews-analysis.session'

export function loadSessionId(): string | null {
  try {
    return window.sessionStorage.getItem(KEY)
  } catch {
    return null
  }
}

export function saveSessionId(id: string): void {
  try {
    window.sessionStorage.setItem(KEY, id)
  } catch {
    // nothing to do: restoring after a reload just won't work
  }
}

export function clearSessionId(): void {
  try {
    window.sessionStorage.removeItem(KEY)
  } catch {
    // see above
  }
}
