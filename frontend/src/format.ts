export function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return 'under a minute'
  }
  return `about ${Math.round(seconds / 60)} min`
}

// Bars run from red (1) through amber (3) to green (5). Each of these is at least 4.5:1
// against white, and the colors in between stay above 3:1 (checked in theme.test.ts).
const SCORE_ANCHORS: [number, [number, number, number]][] = [
  [1, [0xc6, 0x28, 0x28]],
  [3, [0xa1, 0x5c, 0x00]],
  [5, [0x2e, 0x7d, 0x32]],
]
const NEUTRAL = '#7c8aa0'

const hex = (value: number) => Math.round(value).toString(16).padStart(2, '0')

export function scoreColor(mean: number | null): string {
  if (mean === null) {
    return NEUTRAL
  }
  const score = Math.max(1, Math.min(5, mean))
  const upper = SCORE_ANCHORS.findIndex(([anchor]) => score <= anchor)
  const [from, to] = [SCORE_ANCHORS[Math.max(upper - 1, 0)], SCORE_ANCHORS[Math.max(upper, 1)]]
  const share = (score - from[0]) / (to[0] - from[0])
  const [r, g, b] = from[1].map((channel, i) => channel + (to[1][i] - channel) * share)
  return `#${hex(r)}${hex(g)}${hex(b)}`
}

export function truncate(text: string, max: number): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text
}
