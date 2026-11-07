import { describe, expect, it } from 'vitest'
import { SCORE_STOPS, formatDuration, scoreColor, truncate, wrapLabel } from './format'

describe('wrapLabel', () => {
  it('keeps a label that fits on one line', () => {
    expect(wrapLabel('screen', 12, 3)).toEqual(['screen'])
  })

  it('breaks at spaces', () => {
    expect(wrapLabel('wireless charging speed', 12, 3)).toEqual(['wireless', 'charging', 'speed'])
    expect(wrapLabel('battery life', 12, 3)).toEqual(['battery life'])
  })

  it('cuts a word longer than a line', () => {
    expect(wrapLabel('noisecancellation', 8, 3)).toEqual(['noisecan', 'cellatio', 'n'])
  })

  it('ends with an ellipsis when the label needs more lines than allowed', () => {
    expect(wrapLabel('one two three four five', 5, 2)).toEqual(['one', 'two…'])
    expect(wrapLabel('aaaaa bbbbb ccccc', 5, 2)).toEqual(['aaaaa', 'bbbb…'])
  })

  it('always shows at least one character per line', () => {
    expect(wrapLabel('ab', 0, 3)).toEqual(['a', 'b'])
  })
})

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
  it('runs from red at 1 through neutral gray at 3 to blue at 5, in both themes', () => {
    expect([1, 2, 3, 4, 5].map((score) => scoreColor(score))).toEqual(SCORE_STOPS.light)
    expect([1, 2, 3, 4, 5].map((score) => scoreColor(score, 'dark'))).toEqual(SCORE_STOPS.dark)
  })

  it('blends between neighbouring stops', () => {
    expect(scoreColor(2.5)).toBe('#ad7a82') // halfway from #d0646a to #8a8f99
  })

  it('stays inside the range for odd input', () => {
    expect(scoreColor(0)).toBe(scoreColor(1))
    expect(scoreColor(9)).toBe(scoreColor(5))
  })

  it('uses a neutral color when nothing was scored', () => {
    expect(scoreColor(null)).toBe('#7c8aa0')
  })
})
