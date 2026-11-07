import { useEffect, useEffectEvent, useRef, useState } from 'react'
import { describeError, getJob, stopAnalysis, type JobState } from '../api'

const MAX_POLL_FAILURES = 3

/** Polls the session's job until it completes or fails, and lets the user stop it. */
export function useJobPolling(
  sessionId: string,
  pollIntervalMs: number,
  onCompleted: () => Promise<void>,
) {
  const [job, setJob] = useState<JobState | null>(null)
  const [pollError, setPollError] = useState<string | null>(null)
  const [stopping, setStopping] = useState(false)
  const [stopError, setStopError] = useState<string | null>(null)
  const [pollRun, setPollRun] = useState(0)
  // Set the moment a stop is asked for, so a poll answer already on its way cannot
  // overwrite the stopped job. Cleared again only if the stop request fails.
  const halted = useRef(false)
  const complete = useEffectEvent(onCompleted)

  useEffect(() => {
    let cancelled = false
    let misses = 0
    let timer: ReturnType<typeof setTimeout> | undefined
    const ignored = () => cancelled || halted.current

    async function tick() {
      try {
        const next = await getJob(sessionId)
        if (ignored()) return
        misses = 0
        setJob(next)
        if (next.status === 'completed') {
          await complete() // a failure here is retried like a failed poll
          return
        }
        if (next.status === 'failed') return
      } catch (e) {
        if (ignored()) return
        misses += 1
        if (misses >= MAX_POLL_FAILURES) {
          setPollError(describeError(e))
          return
        }
      }
      timer = setTimeout(() => void tick(), pollIntervalMs)
    }

    void tick()
    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [sessionId, pollIntervalMs, pollRun])

  async function stop() {
    halted.current = true
    setStopError(null)
    setStopping(true)
    try {
      setJob(await stopAnalysis(sessionId))
    } catch (e) {
      // e.g. it finished just now: poll again, which shows the outcome
      halted.current = false
      setStopError(describeError(e))
      setPollRun((run) => run + 1)
    } finally {
      setStopping(false)
    }
  }

  return { job, pollError, stopping, stopError, stop }
}
