import { useCallback, useRef, useState } from 'react'
import { describeError, extractProduct, type ProductDetails } from '../api'

type Status = 'idle' | 'loading' | 'failed'

export interface Suggestion {
  product: ProductDetails
  /** changes with every new suggestion, so a form can be reset with it as its key */
  version: number
}

/** Asks the backend to suggest product details, ignoring answers that arrive late. */
export function useExtraction() {
  const latestRun = useRef(0)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [suggestion, setSuggestion] = useState<Suggestion | null>(null)

  const start = useCallback(async (sessionId: string) => {
    const run = ++latestRun.current
    setStatus('loading')
    setError(null)
    try {
      const product = await extractProduct(sessionId)
      if (run !== latestRun.current) return
      setSuggestion((previous) => ({ product, version: (previous?.version ?? 0) + 1 }))
      setStatus('idle')
    } catch (e) {
      if (run !== latestRun.current) return
      setError(describeError(e))
      setStatus('failed')
    }
  }, [])

  /** Give up on a suggestion and let the user type the details in. */
  const skip = useCallback(() => {
    latestRun.current++
    setStatus('idle')
    setError(null)
  }, [])

  /** Use details that are already saved on the server, without asking the model. */
  const provide = useCallback((product: ProductDetails) => {
    latestRun.current++
    setSuggestion((previous) => ({ product, version: (previous?.version ?? 0) + 1 }))
    setStatus('idle')
    setError(null)
  }, [])

  const reset = useCallback(() => {
    latestRun.current++
    setStatus('idle')
    setError(null)
    setSuggestion(null)
  }, [])

  return { status, error, suggestion, start, skip, provide, reset }
}
