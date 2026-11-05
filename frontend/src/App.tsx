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
import { ErrorBanner } from './components/ErrorBanner'
import { loadChart } from './components/lazyChart'
import { ProgressStep } from './components/ProgressStep'
import { ResultsStep } from './components/ResultsStep'
import { ReviewStep } from './components/ReviewStep'
import { Stepper, type Step } from './components/Stepper'
import { UploadStep } from './components/UploadStep'
import { useExtraction } from './hooks/useExtraction'
import { clearSessionId, loadSessionId, saveSessionId } from './sessionStore'

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

const SECONDS_PER_REVIEW_FALLBACK = 2.5

// Shown whenever the backend reports that tracing is on.
const TRACING_NOTICE = 'LLM Tracing On'

export default function App({ pollIntervalMs = 1000 }: { pollIntervalMs?: number }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [step, setStep] = useState<Step>('upload')
  const [session, setSession] = useState<SessionInfo | null>(null)
  const [confirmed, setConfirmed] = useState<ProductDetails | null>(null)
  const [results, setResults] = useState<Results | null>(null)
  const [pollRun, setPollRun] = useState(0)
  const [restore, setRestore] = useState<RestoreState>(() => ({
    status: loadSessionId() ? 'loading' : 'idle',
    error: null,
  }))
  const [restoreRun, setRestoreRun] = useState(0)
  const extraction = useExtraction()
  const {
    start: startExtraction,
    skip: skipExtraction,
    provide: provideSuggestion,
    reset: resetExtraction,
  } = extraction

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
      setRestore({ status: 'idle', error: null })
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
          setRestore({ status: 'idle', error: null })
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
    setPollRun((run) => run + 1)
    setStep('progress')
  }

  function handleSuggestAgain() {
    if (!session) return
    setConfirmed(null)
    void startExtraction(session.id)
  }

  const handleCompleted = useCallback(async () => {
    if (!session) return
    const loaded = await getResults(session.id)
    setResults(loaded)
    setStep('results')
  }, [session])

  async function handleRetry() {
    if (!session) return
    await startAnalysis(session.id)
    setPollRun((run) => run + 1)
  }

  function handleRestart() {
    clearSessionId()
    resetExtraction()
    setSession(null)
    setConfirmed(null)
    setResults(null)
    setRestore({ status: 'idle', error: null })
    setStep('upload')
  }

  function handleRetryRestore() {
    setRestore({ status: 'loading', error: null })
    setRestoreRun((run) => run + 1)
  }

  return (
    <div className="app">
      <header>
        <div className="app-title">
          <h1>Product reviews analysis</h1>
          {step !== 'upload' && (
            <button type="button" className="link-button" onClick={handleRestart}>
              Start over
            </button>
          )}
        </div>
        <Stepper current={step} />
        {config?.tracing_enabled && (
          <p className="notice" role="note">
            <span aria-hidden="true">ⓘ</span> {TRACING_NOTICE}
          </p>
        )}
      </header>
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

        {restore.status === 'idle' && step === 'upload' && (
          <UploadStep config={config} onUploaded={handleUploaded} />
        )}

        {restore.status === 'idle' && step === 'review' && session && (
          <ReviewStep
            config={config}
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

        {restore.status === 'idle' && step === 'progress' && session && (
          <ProgressStep
            key={pollRun}
            sessionId={session.id}
            pollIntervalMs={pollIntervalMs}
            secondsPerReview={config?.estimated_seconds_per_review ?? SECONDS_PER_REVIEW_FALLBACK}
            onCompleted={handleCompleted}
            onEdit={() => setStep('review')}
            onRetry={handleRetry}
            onRecheck={() => setPollRun((run) => run + 1)}
          />
        )}

        {restore.status === 'idle' && step === 'results' && session && results && (
          <ResultsStep
            sessionId={session.id}
            results={results}
            onEdit={() => setStep('review')}
            onRestart={handleRestart}
          />
        )}
      </main>
    </div>
  )
}
