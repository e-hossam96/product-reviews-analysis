import { describe, expect, it } from 'vitest'
import { formatDuration, scoreColor, truncate } from './format'

describe('formatDuration', () => {
  it('says "under a minute" below one minute', () => {
    expect(formatDuration(0)).toBe('under a minute')
    expect(formatDuration(59)).toBe('under a minute')
  })

  it('rounds to whole minutes', () => {
    expect(formatDuration(60)).toBe('about 1 min')
    expect(formatDuration(250)).toBe('about 4 min')
  })
})

describe('truncate', () => {
  it('keeps short text and shortens long text with an ellipsis', () => {
    expect(truncate('screen', 16)).toBe('screen')
    expect(truncate('wireless charging speed', 16)).toBe('wireless chargi…')
    expect(truncate('a'.repeat(16), 16)).toBe('a'.repeat(16))
  })
})

describe('scoreColor', () => {
  it('runs from red at 1 through amber at 3 to green at 5', () => {
    expect(scoreColor(1)).toBe('#c62828')
    expect(scoreColor(3)).toBe('#a15c00')
    expect(scoreColor(5)).toBe('#2e7d32')
  })

  it('blends between those colors', () => {
    expect(scoreColor(2)).toBe('#b44214') // halfway from red to amber
    expect(scoreColor(4)).toBe('#686d19') // halfway from amber to green
  })

  it('stays inside the range for odd input', () => {
    expect(scoreColor(0)).toBe(scoreColor(1))
    expect(scoreColor(9)).toBe(scoreColor(5))
  })

  it('uses a neutral color when nothing was scored', () => {
    expect(scoreColor(null)).toBe('#7c8aa0')
  })
})
