import type { ColorScheme } from './theme'

export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return 'under a minute'
  }
  return `about ${Math.round(seconds / 60)} min`
}

export function plural(count: number, word: string): string {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

export function formatScore(mean: number | null, digits = 2): string {
  return mean === null ? '–' : mean.toFixed(digits)
}

// The average score has a direction (bad, neutral, good), so the bars use a diverging
// scale: red for 1, a neutral gray for 3, blue for 5, one stop per whole score.
// Red and blue stay apart for colorblind readers, unlike red and green. The gray
// midpoint is the most recessive stop: lightest in the light theme, dimmest in the dark
// theme. Every stop, and every blend between them, is at least 3:1 against the card
// (checked in theme.test.ts).
export const SCORE_STOPS: Record<ColorScheme, string[]> = {
  light: ['#b8323a', '#d0646a', '#8a8f99', '#5a8fd8', '#2463c4'],
  dark: ['#f07878', '#c9787c', '#6f7686', '#6f9ad6', '#6aa8ff'],
}
const NEUTRAL: Record<ColorScheme, string> = { light: '#7c8aa0', dark: '#8b97ac' }

const toRgb = (color: string) => [1, 3, 5].map((i) => parseInt(color.slice(i, i + 2), 16))
const hex = (value: number) => Math.round(value).toString(16).padStart(2, '0')

export function scoreColor(mean: number | null, scheme: ColorScheme = 'light'): string {
  if (mean === null) {
    return NEUTRAL[scheme]
  }
  const stops = SCORE_STOPS[scheme]
  const position = Math.max(0, Math.min(stops.length - 1, mean - 1))
  const lower = Math.min(Math.floor(position), stops.length - 2)
  const share = position - lower
  const [from, to] = [toRgb(stops[lower]), toRgb(stops[lower + 1])]
  const [r, g, b] = from.map((channel, i) => channel + (to[i] - channel) * share)
  return `#${hex(r)}${hex(g)}${hex(b)}`
}

/** Break a label into at most `maxLines` lines of about `maxChars` characters, at spaces
 *  where possible. Words longer than a line are cut, and text that does not fit ends
 *  with an ellipsis. */
export function wrapLabel(text: string, maxChars: number, maxLines: number): string[] {
  const width = Math.max(1, Math.floor(maxChars))
  const lines: string[] = []
  let line = ''
  for (const word of text.trim().split(/\s+/)) {
    let rest = word
    while (rest) {
      const joined = line ? `${line} ${rest}` : rest
      if (joined.length <= width) {
        line = joined
        rest = ''
      } else if (line) {
        lines.push(line)
        line = ''
      } else {
        lines.push(rest.slice(0, width))
        rest = rest.slice(width)
      }
    }
  }
  if (line) lines.push(line)
  if (lines.length <= maxLines) return lines
  const kept = lines.slice(0, maxLines)
  const last = kept[maxLines - 1]
  kept[maxLines - 1] = `${last.length >= width ? last.slice(0, width - 1) : last}…`
  return kept
}
