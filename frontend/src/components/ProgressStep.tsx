import { useState } from 'react'
import { describeError, type JobState } from '../api'
import { formatDuration } from '../format'
import { useJobPolling } from '../hooks/useJobPolling'
import { ErrorBanner } from './ErrorBanner'

interface Props {
  sessionId: string
  pollIntervalMs: number
  secondsPerReview: number
  /** called once the job is complete; should fetch and show the results */
  onCompleted: () => Promise<void>
  onEdit: () => void
  /** start the analysis again */
  onRetry: () => Promise<void>
  /** poll again without starting a new analysis */
  onRecheck: () => void
}

export function ProgressStep({
  sessionId,
  pollIntervalMs,
  secondsPerReview,
  onCompleted,
  onEdit,
  onRetry,
  onRecheck,
}: Props) {
  const { job, pollError, stopping, stopError, stop } = useJobPolling(
    sessionId,
    pollIntervalMs,
    onCompleted,
  )

  if (pollError) {
    return (
      <section className="card">
        <h2>Lost contact with the server</h2>
        <ErrorBanner message={pollError} />
        <div className="actions">
          <button type="button" onClick={onRecheck}>
            Check again
          </button>
        </div>
      </section>
    )
  }

  if (job?.status === 'failed') {
    return <FailedJob job={job} onRetry={onRetry} onEdit={onEdit} />
  }

  const total = job?.total ?? 0
  const done = job?.done ?? 0
  const remainingSeconds = (total - done) * secondsPerReview

  return (
    <section className="card" aria-busy="true">
      <h2>Analyzing your reviews</h2>
      <progress aria-label="Analysis progress" value={done} max={total > 0 ? total : undefined} />
      <p role="status">
        {job ? `${done} of ${total} reviews scored` : 'Starting…'}
        {job && job.failed > 0 && ` · ${job.failed} could not be scored`}
      </p>
      {job && total > done && (
        <p className="muted small">Time left: {formatDuration(remainingSeconds)}.</p>
      )}
      <ErrorBanner message={stopError} />
      <div className="actions">
        <button
          type="button"
          className="secondary"
          disabled={!job || stopping}
          onClick={() => void stop()}
        >
          {stopping ? 'Stopping…' : 'Stop analysis'}
        </button>
      </div>
    </section>
  )
}

interface FailedJobProps {
  job: JobState
  onRetry: () => Promise<void>
  onEdit: () => void
}

function FailedJob({ job, onRetry, onEdit }: FailedJobProps) {
  const [retrying, setRetrying] = useState(false)
  const [retryError, setRetryError] = useState<string | null>(null)

  async function handleRetry() {
    setRetryError(null)
    setRetrying(true)
    try {
      await onRetry()
    } catch (e) {
      setRetryError(describeError(e))
      setRetrying(false)
    }
  }

  return (
    <section className="card">
      <h2>The analysis stopped</h2>
      <ErrorBanner message={job.error ?? 'The analysis failed.'} />
      <p className="muted">
        {job.done} of {job.total} reviews were processed before it stopped.
      </p>
      <ErrorBanner message={retryError} />
      <div className="actions">
        <button type="button" disabled={retrying} onClick={() => void handleRetry()}>
          {retrying ? 'Starting…' : 'Try again'}
        </button>
        <button type="button" className="secondary" disabled={retrying} onClick={onEdit}>
          Edit the aspects
        </button>
      </div>
    </section>
  )
}
