import type { NgramCount } from '../api'
import { normalizeAspect } from '../aspects'

interface Props {
  ngrams: NgramCount[]
  selected: string[]
  onPick: (ngram: string) => void
}

const MIN_REM = 0.9
const MAX_REM = 2.4

export function WordCloud({ ngrams, selected, onPick }: Props) {
  if (ngrams.length === 0) {
    return <p className="muted">No repeated phrases were found. Add the aspects by hand.</p>
  }
  const counts = ngrams.map((item) => item.count)
  const min = Math.min(...counts)
  const max = Math.max(...counts)

  return (
    <ul className="cloud" aria-label="Frequent phrases">
      {ngrams.map(({ ngram, count }) => {
        const share = max === min ? 0.5 : Math.sqrt((count - min) / (max - min))
        const size = MIN_REM + share * (MAX_REM - MIN_REM)
        const isSelected = selected.includes(normalizeAspect(ngram))
        return (
          <li key={ngram}>
            <button
              type="button"
              className="cloud-word"
              style={{ fontSize: `${size.toFixed(2)}rem` }}
              aria-pressed={isSelected}
              title={`In ${count} review${count === 1 ? '' : 's'}`}
              onClick={() => onPick(ngram)}
            >
              {ngram}
            </button>
          </li>
        )
      })}
    </ul>
  )
}
