import { afterEach, describe, expect, it, vi } from 'vitest'
import { clearSessionId, loadSessionId, saveSessionId } from './sessionStore'

afterEach(() => {
  vi.restoreAllMocks()
})

describe('sessionStore', () => {
  it('remembers, reports and forgets the session id', () => {
    expect(loadSessionId()).toBeNull()
    saveSessionId('abc')
    expect(loadSessionId()).toBe('abc')
    clearSessionId()
    expect(loadSessionId()).toBeNull()
  })

  it('keeps working when storage is blocked', () => {
    const blocked = () => {
      throw new DOMException('blocked', 'SecurityError')
    }
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(blocked)
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(blocked)
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(blocked)

    expect(loadSessionId()).toBeNull()
    expect(() => saveSessionId('abc')).not.toThrow()
    expect(() => clearSessionId()).not.toThrow()
  })
})
