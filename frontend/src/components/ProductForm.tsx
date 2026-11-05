import { useState } from 'react'
import { describeError, type NgramCount, type ProductDetails } from '../api'
import { MAX_NAME_LENGTH, addAspect, collapseSpaces } from '../aspects'
import { formatDuration } from '../format'
import { AspectEditor } from './AspectEditor'
import { ErrorBanner } from './ErrorBanner'
import { WordCloud } from './WordCloud'

interface Props {
  initial: ProductDetails
  ngrams: NgramCount[]
  maxAspects: number
  reviewCount: number
  secondsPerReview: number
  onSuggestAgain: () => void
  onSubmit: (product: ProductDetails) => Promise<void>
}

export function ProductForm({
  initial,
  ngrams,
  maxAspects,
  reviewCount,
  secondsPerReview,
  onSuggestAgain,
  onSubmit,
}: Props) {
  const [name, setName] = useState(initial.name)
  const [aspects, setAspects] = useState(initial.aspects)
  const [notice, setNotice] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const cleanName = collapseSpaces(name)
  const canSubmit = cleanName !== '' && aspects.length > 0 && !submitting

  function handlePick(ngram: string) {
    const result = addAspect(aspects, ngram, maxAspects)
    setAspects(result.aspects)
    setNotice(result.error)
  }

  async function handleSubmit() {
    setError(null)
    setSubmitting(true)
    try {
      await onSubmit({ name: cleanName, aspects })
    } catch (e) {
      setError(describeError(e))
      setSubmitting(false)
    }
  }

  return (
    <>
      <section className="card">
        <h2>Frequent phrases</h2>
        <p className="muted">
          The phrases that appear in the most reviews. Click one to add it as an aspect.
        </p>
        <WordCloud ngrams={ngrams} selected={aspects} onPick={handlePick} />
        {notice && (
          <p className="banner warn" role="status">
            {notice}
          </p>
        )}
      </section>

      <section className="card">
        <h2>Product details</h2>
        <p className="muted">
          Check what the model found and correct it. Each review is scored on these aspects.
        </p>
        <label className="field">
          <span>Product name</span>
          <input
            value={name}
            maxLength={MAX_NAME_LENGTH}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <div className="field">
          <span>Aspects</span>
          <AspectEditor aspects={aspects} max={maxAspects} onChange={setAspects} />
        </div>
        <ErrorBanner message={error} />
        <div className="actions">
          <button type="button" disabled={!canSubmit} onClick={() => void handleSubmit()}>
            {submitting ? 'Starting…' : `Confirm and analyze ${reviewCount} reviews`}
          </button>
          <button
            type="button"
            className="secondary"
            disabled={submitting}
            onClick={onSuggestAgain}
          >
            Suggest again
          </button>
        </div>
        <p className="muted small">
          Scoring takes {formatDuration(reviewCount * secondsPerReview)}.
        </p>
      </section>
    </>
  )
}
