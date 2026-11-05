import { describe, expect, it } from 'vitest'
import html from '../index.html?raw'
import css from './index.css?raw'
import { scoreColor } from './format'
import { contrastRatio } from './test/contrast'

const root = /:root\s*\{([^}]*)\}/.exec(css)?.[1] ?? ''
const tokens: Record<string, string> = Object.fromEntries(
  [...root.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)].map((match) => [match[1], match[2]]),
)

// [text color, background] pairs that really occur in the app: WCAG AA needs 4.5:1
const TEXT_PAIRS: [string, string][] = [
  ['text', 'bg'],
  ['text', 'card'],
  ['muted', 'bg'],
  ['muted', 'card'],
  ['accent', 'card'], // links, secondary buttons, selected phrases
  ['accent', 'bg'],
  ['accent', 'accent-soft'], // chips, selected phrases
  ['text', 'accent-soft'],
  ['accent-text', 'accent'], // primary buttons, current step
  ['accent-text', 'accent-hover'],
  ['danger-text', 'danger-bg'],
  ['warn-text', 'warn-bg'],
  ['info-text', 'info-bg'],
]

// [outline or border color, what it sits on]: controls and focus rings need 3:1
const UI_PAIRS: [string, string][] = [
  ['border-strong', 'card'], // input borders, drop zone
  ['border-strong', 'bg'],
  ['accent', 'card'], // focus ring, outlined buttons
  ['accent', 'bg'],
]

describe('light theme', () => {
  it('defines every color the pairs below rely on', () => {
    const names = new Set([...TEXT_PAIRS, ...UI_PAIRS].flat())
    for (const name of names) {
      expect(tokens[name], `--${name}`).toMatch(/^#[0-9a-f]{6}$/i)
    }
  })

  it.each(TEXT_PAIRS)('%s text on %s is easy to read (4.5:1)', (foreground, background) => {
    expect(contrastRatio(tokens[foreground], tokens[background])).toBeGreaterThanOrEqual(4.5)
  })

  it.each(UI_PAIRS)('%s stands out against %s (3:1)', (outline, background) => {
    expect(contrastRatio(tokens[outline], tokens[background])).toBeGreaterThanOrEqual(3)
  })

  it('keeps every chart bar color visible on a white card', () => {
    for (let mean = 1; mean <= 5.0001; mean += 0.1) {
      expect(
        contrastRatio(scoreColor(mean), tokens.card),
        `mean ${mean.toFixed(1)}`,
      ).toBeGreaterThanOrEqual(3)
    }
  })

  it('is light only: no dark variant, and the browser is told so', () => {
    expect(css).toMatch(/color-scheme:\s*light\s*;/)
    expect(css).not.toMatch(/prefers-color-scheme:\s*dark/)
    expect(html).toMatch(/<meta name="color-scheme" content="light"/)
  })

  it('uses the theme for the chart, not the library defaults', () => {
    expect(css).toMatch(/\.recharts-cartesian-axis-tick-value[^{]*\{\s*fill:\s*var\(--text\)/)
  })
})
