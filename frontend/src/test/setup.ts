import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// jsdom has no ResizeObserver, which the chart's container needs.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
} as unknown as typeof ResizeObserver

afterEach(() => {
  cleanup()
  globalThis.sessionStorage?.clear() // not present in node-environment tests
  vi.unstubAllGlobals()
})
