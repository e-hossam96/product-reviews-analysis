import { describe, expect, it } from 'vitest'
import { MAX_ASPECT_LENGTH, addAspect, collapseSpaces, normalizeAspect } from './aspects'

describe('normalizeAspect', () => {
  it('lowercases and collapses whitespace like the backend does', () => {
    expect(normalizeAspect('  Battery   Life ')).toBe('battery life')
    expect(collapseSpaces('  Galaxy \t S24 ')).toBe('Galaxy S24')
  })
})

describe('addAspect', () => {
  it('adds a normalized aspect', () => {
    expect(addAspect(['screen'], ' Battery  Life ', 5)).toEqual({
      aspects: ['screen', 'battery life'],
      error: null,
    })
  })

  it('ignores empty input without an error', () => {
    expect(addAspect(['screen'], '   ', 5)).toEqual({ aspects: ['screen'], error: null })
  })

  it('rejects a duplicate, whatever its case', () => {
    const result = addAspect(['battery life'], 'Battery Life', 5)
    expect(result.aspects).toEqual(['battery life'])
    expect(result.error).toMatch(/already in the list/)
  })

  it('rejects an aspect that is too long', () => {
    const result = addAspect([], 'x'.repeat(MAX_ASPECT_LENGTH + 1), 5)
    expect(result.aspects).toEqual([])
    expect(result.error).toMatch(/at most 40 characters/)
  })

  it('stops at the maximum number of aspects', () => {
    const result = addAspect(['a', 'b'], 'c', 2)
    expect(result.aspects).toEqual(['a', 'b'])
    expect(result.error).toMatch(/at most 2 aspects/)
  })
})
