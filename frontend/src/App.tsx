import { useCallback, useEffect, useState } from 'react'
import {
  ApiError,
  confirmProduct,
  describeError,
  getConfig,
  getResults,
  getSession,
  startAnalysis,
  type AppConfig,
  type NgramCount,
  type ProductDetails,
  type Results,
  type SessionCreated,
  type SessionState,
} from './api'
import { AppFooter } from './components/AppFooter'
import { AppHeader } from './components/AppHeader'
import { ErrorBanner } from './components/ErrorBanner'
import { loadChart } from './components/lazyChart'
import { ProgressStep } from './components/ProgressStep'
import { ResultsStep } from './components/ResultsStep'
import { ReviewStep } from './components/ReviewStep'
import { type Step } from './components/Stepper'
import { UploadStep } from './components/UploadStep'
import { useExtraction } from './hooks/useExtraction'
import { clearSessionId, loadSessionId, saveSessionId } from './sessionStore'

// Used until the config arrives, or if it never does.
const DEFAULT_SECONDS_PER_REVIEW = 2.5
const DEFAULT_MAX_ASPECTS = 10

interface SessionInfo {
  id: string
  filename: string
  reviewCount: number
  skippedEmpty: number
  ngrams: NgramCount[]
}

interface RestoreState {
  status: 'idle' | 'loading' | 'failed'
  error: string | null
}

const RESTORE_IDLE: RestoreState = { status: 'idle', error: null }

export default function App({ pollIntervalMs = 1000 }: { pollIntervalMs?: number }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [step, setStep] = useState<Step>('upload')
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [confirmed, setConfirmed] = useState<ProductDetails | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  // Bumping this remounts ProgressStep, which starts polling afresh.
  const [pollRun, setPollRun] = useState(0)
  const [restore, setRestore] = useState<RestoreState>(() =>
    loadSessionId() ? { status: 'loading', error: null } : RESTORE_IDLE,
  )
  const [restoreRun, setRestoreRun] = useState(0)
  const extraction = useExtraction()
  const {
    start: startExtraction,
    skip: skipExtraction,
    provide: provideSuggestion,
    reset: resetExtraction,
  } = extraction

  const secondsPerReview = config?.estimated_seconds_per_review ?? DEFAULT_SECONDS_PER_REVIEW
  const maxAspects = config?.max_aspects ?? DEFAULT_MAX_ASPECTS
  const pollAgain = () => setPollRun((run) => run + 1)

  useEffect(() => {
    let cancelled = false
    getConfig()
      .then((loaded) => {
        if (!cancelled) setConfig(loaded)
      })
      .catch(() => {
        // The limits are only a hint on the upload page; the server enforces them.
      })
    return () => {
      cancelled = true
    }
  }, [])

  // Put the screen back where the user left it, after a reload.
  const applyRestored = useCallback(
    (id: string, state: SessionState, loadedResults: Results | null) => {
      setSession({
        id,
        filename: state.filename ?? 'your file',
        reviewCount: state.review_count,
        skippedEmpty: 0, // not stored on the server
        ngrams: state.top_ngrams,
      })
      setConfirmed(state.product_confirmed ? state.product : null)
      setResults(loadedResults)
      if (loadedResults) {
        setStep('results')
      } else if (state.job) {
        setPollRun((run) => run + 1)
        setStep('progress') // running, or stopped: the progress screen shows which
      } else {
        setStep('review')
        if (state.product) {
          provideSuggestion(state.product)
        } else {
          void startExtraction(id)
        }
      }
      setRestore(RESTORE_IDLE)
    },
    [provideSuggestion, startExtraction],
  )

  useEffect(() => {
    const id = loadSessionId()
    if (!id) return
    let cancelled = false

    async function restoreSession(sessionId: string) {
      try {
        const state = await getSession(sessionId)
        if (cancelled) return
        const finished = state.job?.status === 'completed'
        const loadedResults = finished ? await getResults(sessionId) : null
        if (cancelled) return
        applyRestored(sessionId, state, loadedResults)
      } catch (e) {
        if (cancelled) return
        if (e instanceof ApiError && e.status === 404) {
          clearSessionId() // it expired: start fresh
          setRestore(RESTORE_IDLE)
          return
        }
        setRestore({ status: 'failed', error: describeError(e) })
      }
    }

    void restoreSession(id)
    return () => {
      cancelled = true
    }
  }, [restoreRun, applyRestored])

  const handleUploaded = useCallback(
    (created: SessionCreated, filename: string) => {
      saveSessionId(created.session_id)
      setSession({
        id: created.session_id,
        filename,
        reviewCount: created.review_count,
        skippedEmpty: created.skipped_empty,
        ngrams: created.top_ngrams,
      })
      setConfirmed(null)
      setResults(null)
      setStep('review')
      void startExtraction(created.session_id)
    },
    [startExtraction],
  )

  async function handleConfirm(product: ProductDetails) {
    if (!session) return
    const saved = await confirmProduct(session.id, product)
    await startAnalysis(session.id)
    void loadChart().catch(() => {
      // fetched early so it is ready for the results; a failure shows up there
    })
    setConfirmed(saved)
    pollAgain()
    setStep('progress')
  }

  function handleSuggestAgain() {
    if (!session) return
    setConfirmed(null)
    void startExtraction(session.id)
  }

  const handleCompleted = useCallback(async () => {
    if (!session) return
    setResults(await getResults(session.id))
    setStep('results')
  }, [session])

  async function handleRetry() {
    if (!session) return
    await startAnalysis(session.id)
    pollAgain()
  }

  function handleRestart() {
    clearSessionId()
    resetExtraction()
    setSession(null)
    setConfirmed(null)
    setResults(null)
    setRestore(RESTORE_IDLE)
    setStep('upload')
  }

  function handleRetryRestore() {
    setRestore({ status: 'loading', error: null })
    setRestoreRun((run) => run + 1)
  }

  const ready = restore.status === 'idle'

  return (
    <div className="app">
      <AppHeader
        step={step}
        tracingEnabled={config?.tracing_enabled ?? false}
        onRestart={handleRestart}
      />
      <main>
        {restore.status === 'loading' && (
          <section className="card" aria-busy="true">
            <h2>Restoring your session…</h2>
            <div className="spinner" role="status" aria-label="Loading" />
          </section>
        )}

        {restore.status === 'failed' && (
          <section className="card">
            <h2>Could not restore your session</h2>
            <ErrorBanner message={restore.error} />
            <div className="actions">
              <button type="button" onClick={handleRetryRestore}>
                Try again
              </button>
              <button type="button" className="secondary" onClick={handleRestart}>
                Start over
              </button>
            </div>
          </section>
        )}

        {ready && step === 'upload' && <UploadStep config={config} onUploaded={handleUploaded} />}

        {ready && step === 'review' && session && (
          <ReviewStep
            maxAspects={maxAspects}
            secondsPerReview={secondsPerReview}
            filename={session.filename}
            reviewCount={session.reviewCount}
            skippedEmpty={session.skippedEmpty}
            ngrams={session.ngrams}
            confirmed={confirmed}
            extraction={extraction}
            onSuggestAgain={handleSuggestAgain}
            onEnterManually={skipExtraction}
            onSubmit={handleConfirm}
          />
        )}

        {ready && step === 'progress' && session && (
          <ProgressStep
            key={pollRun}
            sessionId={session.id}
            pollIntervalMs={pollIntervalMs}
            secondsPerReview={secondsPerReview}
            onCompleted={handleCompleted}
            onEdit={() => setStep('review')}
            onRetry={handleRetry}
            onRecheck={pollAgain}
          />
        )}

        {ready && step === 'results' && session && results && (
          <ResultsStep sessionId={session.id} results={results} onEdit={() => setStep('review')} />
        )}
      </main>
      <AppFooter />
    </div>
  )
}
