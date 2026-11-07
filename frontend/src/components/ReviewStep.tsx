import type { NgramCount, ProductDetails } from '../api'
import type { ExtractionState } from '../hooks/useExtraction'
import { ErrorBanner } from './ErrorBanner'
import { ProductForm } from './ProductForm'

interface Props {
  maxAspects: number
  secondsPerReview: number
  filename: string
  reviewCount: number
  skippedEmpty: number
  ngrams: NgramCount[]
  /** details the user already confirmed, when coming back from the results */
  confirmed: ProductDetails | null
  extraction: ExtractionState
  onSuggestAgain: () => void
  onEnterManually: () => void
  onSubmit: (product: ProductDetails) => Promise<void>
}

const EMPTY: ProductDetails = { name: '', aspects: [] }

export function ReviewStep({
  maxAspects,
  secondsPerReview,
  filename,
  reviewCount,
  skippedEmpty,
  ngrams,
  confirmed,
  extraction,
  onSuggestAgain,
  onEnterManually,
  onSubmit,
}: Props) {
  return (
    <>
      <p className="summary">
        {reviewCount} reviews loaded from {filename}
        {skippedEmpty > 0 && ` (${skippedEmpty} empty rows skipped)`}.
      </p>

      {extraction.status === 'loading' && (
        <section className="card" aria-busy="true">
          <h2>Reading your reviews…</h2>
          <p className="muted">
            The model is looking for the product name and the aspects customers talk about. This can
            take up to a minute.
          </p>
          <div className="spinner" role="status" aria-label="Loading" />
        </section>
      )}

      {extraction.status === 'failed' && (
        <section className="card">
          <h2>Could not suggest product details</h2>
          <ErrorBanner message={extraction.error} />
          <div className="actions">
            <button type="button" onClick={onSuggestAgain}>
              Try again
            </button>
            <button type="button" className="secondary" onClick={onEnterManually}>
              Enter the details manually
            </button>
          </div>
        </section>
      )}

      {extraction.status === 'idle' && (
        <ProductForm
          key={extraction.suggestion?.version ?? 0}
          initial={confirmed ?? extraction.suggestion?.product ?? EMPTY}
          ngrams={ngrams}
          maxAspects={maxAspects}
          reviewCount={reviewCount}
          secondsPerReview={secondsPerReview}
          onSuggestAgain={onSuggestAgain}
          onSubmit={onSubmit}
        />
      )}
    </>
  )
}
