import { useSyncExternalStore } from 'react'

// The page follows the operating system or browser setting by default. The user can pin
// light or dark instead; that choice is kept in localStorage and applied as
// <html data-theme="…">, which the stylesheet reads. index.html applies a saved choice
// before the first paint so the page does not flash the wrong colors.
export type ThemePreference = 'system' | 'light' | 'dark'
export type ColorScheme = 'light' | 'dark'

export const THEME_KEY = 'reviews-analysis.theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

const listeners = new Set<() => void>()
const notify = () => listeners.forEach((listener) => listener())

function darkQuery(): MediaQueryList | null {
  return typeof window !== 'undefined' && typeof window.matchMedia === 'function'
    ? window.matchMedia(DARK_QUERY)
    : null
}

export function loadPreference(): ThemePreference {
  try {
    const saved = window.localStorage.getItem(THEME_KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    return 'system'
  }
}

export function systemScheme(): ColorScheme {
  return darkQuery()?.matches ? 'dark' : 'light'
}

export function resolveScheme(preference: ThemePreference): ColorScheme {
  return preference === 'system' ? systemScheme() : preference
}

export function applyPreference(preference: ThemePreference): void {
  const root = document.documentElement
  if (preference === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = preference
  }
}

export function setPreference(preference: ThemePreference): void {
  try {
    if (preference === 'system') {
      window.localStorage.removeItem(THEME_KEY)
    } else {
      window.localStorage.setItem(THEME_KEY, preference)
    }
  } catch {
    // storage blocked: the choice lasts until the page is reloaded
  }
  current = preference
  applyPreference(preference)
  notify()
}

let current: ThemePreference | null = null
const getPreference = () => (current ??= loadPreference())

function subscribe(listener: () => void) {
  listeners.add(listener)
  const query = darkQuery()
  query?.addEventListener('change', listener)
  // another tab changed the choice
  const onStorage = (event: StorageEvent) => {
    if (event.key !== THEME_KEY) return
    current = loadPreference()
    applyPreference(current)
    listener()
  }
  window.addEventListener('storage', onStorage)
  return () => {
    listeners.delete(listener)
    query?.removeEventListener('change', listener)
    window.removeEventListener('storage', onStorage)
  }
}

/** The user's choice: system, light or dark. */
export function useThemePreference(): ThemePreference {
  return useSyncExternalStore(subscribe, getPreference, () => 'system')
}

/** The scheme actually on screen, following the system when the choice is "system". */
export function useColorScheme(): ColorScheme {
  return useSyncExternalStore(
    subscribe,
    () => resolveScheme(getPreference()),
    () => 'light',
  )
}
