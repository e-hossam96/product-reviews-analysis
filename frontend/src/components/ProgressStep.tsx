import { useEffect, useEffectEvent, useState } from 'react'
import { describeError, getJob, type JobState } from '../api'
import { formatDuration } from '../format'
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

const MAX_POLL_FAILURES = 3

export function ProgressStep({
  sessionId,
  pollIntervalMs,
  secondsPerReview,
  onCompleted,
  onEdit,
  onRetry,
  onRecheck,
}: Props) {
  const [job, setJob] = useState<JobState | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const [retryError, setRetryError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)
  const complete = useEffectEvent(onCompleted)

  useEffect(() => {
    // everything the polling loop changes lives in one object
    const poll = {
      cancelled: false,
      misses: 0, // consecutive failed polls
      timer: undefined as ReturnType<typeof setTimeout> | undefined,
    }

    async function tick() {
      try {
        const next = await getJob(sessionId)
        if (poll.cancelled) return
        poll.misses = 0
        setJob(next)
        if (next.status === 'completed') {
          await complete() // a failure here is retried like a failed poll
          return
        }
        if (next.status === 'failed') return
      } catch (e) {
        if (poll.cancelled) return
        poll.misses += 1
        if (poll.misses >= MAX_POLL_FAILURES) {
          setPollError(describeError(e))
          return
        }
      }
      poll.timer = setTimeout(() => void tick(), pollIntervalMs)
    }

    void tick()
    return () => {
      poll.cancelled = true
      clearTimeout(poll.timer)
    }
  }, [sessionId, pollIntervalMs])

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
    </section>
  )
}
