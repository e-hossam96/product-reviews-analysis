import { useState } from 'react'
import type { NgramCount } from '../api'
import { normalizeAspect } from '../aspects'
import { plural } from '../format'

interface Props {
  ngrams: NgramCount[]
  selected: string[]
  onPick: (ngram: string) => void
}

/** How many phrases show before "Show all". */
export const VISIBLE_PHRASES = 24

/** The most frequent phrases, ranked, each with its review count and a bar for its share. */
export function PhraseList({ ngrams, selected, onPick }: Props) {
  const [showAll, setShowAll] = useState(false)

  if (ngrams.length === 0) {
    return <p className="muted">No repeated phrases were found. Add the aspects by hand.</p>
  }
  const ranked = [...ngrams].sort((a, b) => b.count - a.count)
  const top = ranked[0].count
  const shown = showAll ? ranked : ranked.slice(0, VISIBLE_PHRASES)

  return (
    <>
      <ul className="phrases" aria-label="Frequent phrases">
        {shown.map(({ ngram, count }) => (
          <li key={ngram}>
            <button
              type="button"
              className="phrase"
              aria-label={`${ngram}, in ${plural(count, 'review')}`}
              aria-pressed={selected.includes(normalizeAspect(ngram))}
              onClick={() => onPick(ngram)}
            >
              <span className="phrase-text">{ngram}</span>
              <span className="phrase-count">{count}</span>
              <span className="phrase-bar" style={{ width: `${(count / top) * 100}%` }} />
            </button>
          </li>
        ))}
      </ul>
      {ranked.length > VISIBLE_PHRASES && (
        <button type="button" className="link-button" onClick={() => setShowAll(!showAll)}>
          {showAll ? 'Show fewer' : `Show all ${ranked.length} phrases`}
        </button>
      )}
    </>
  )
}
