import { vi } from 'vitest'
import type { AppConfig, JobState, ProductDetails, Results, SessionState } from '../api'

export const SESSION_ID = 'sess-token-abc123'

export const CONFIG: AppConfig = {
  max_rows: 100,
  max_upload_mb: 10,
  max_aspects: 10,
  estimated_seconds_per_review: 2.5,
  tracing_enabled: false,
}

export const NGRAMS = [
  { ngram: 'battery life', count: 6 },
  { ngram: 'screen', count: 4 },
  { ngram: 'price', count: 2 },
]

export const sessionState = (overrides: Partial<SessionState> = {}): SessionState => ({
  filename: 'reviews.csv',
  review_count: 6,
  top_ngrams: NGRAMS,
  product: null,
  product_confirmed: false,
  job: null,
  ...overrides,
})

export const PRODUCT: ProductDetails = { name: 'Galaxy S24', aspects: ['screen', 'battery life'] }

export const RESULTS: Results = {
  product_name: 'Galaxy S24',
  review_count: 6,
  analyzed_count: 5,
  failed_count: 1,
  aspects: [
    {
      aspect: 'screen',
      mean_score: 4.5,
      mention_count: 4,
      distribution: { '1': 0, '2': 0, '3': 0, '4': 2, '5': 2 },
    },
    {
      aspect: 'battery life',
      mean_score: null,
      mention_count: 0,
      distribution: { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 },
    },
  ],
}

export const job = (status: JobState['status'], done: number, extra: Partial<JobState> = {}) =>
  ({ job_id: 'job1', status, done, total: 6, failed: 0, error: null, ...extra }) satisfies JobState

/** A job poll answer, a network failure, or a function that answers later. */
export type JobStep = JobState | Error | (() => Promise<JobState>)

/** An answer to "where does this session stand?", or a failure. */
export type SessionStep = SessionState | 'missing' | Error

export interface FakeOptions {
  tracing?: boolean
  /** answers to GET /sessions/{id}, in order; the last one repeats */
  sessions?: SessionStep[]
  uploadError?: { status: number; detail: unknown }
  /** how many extract calls fail before one succeeds */
  extractFailures?: number
  jobs?: JobStep[]
  analyzeError?: { status: number; detail: unknown }
}

export interface RecordedCall {
  method: string
  path: string
  body?: unknown
}

export function deferred<T = void>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((r) => {
    resolve = r
  })
  return { promise, resolve }
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

/** Replaces fetch with an in-memory version of the backend API. */
export function installFakeBackend(options: FakeOptions = {}) {
  const calls: RecordedCall[] = []
  const jobs = options.jobs ?? [job('running', 2), job('completed', 6)]
  let jobIndex = 0
  let sessionIndex = 0
  const sessions = options.sessions ?? [sessionState()]
  let extractFailures = options.extractFailures ?? 0
  const sessionPrefix = `/sessions/${SESSION_ID}`

  const handler = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const method = init?.method ?? 'GET'
    const path = String(input).replace('/api/v1', '')
    const body = typeof init?.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
    calls.push({ method, path, body })

    if (method === 'GET' && path === '/config') {
      return json({ ...CONFIG, tracing_enabled: options.tracing ?? false })
    }

    if (method === 'POST' && path === '/sessions') {
      if (options.uploadError) {
        return json({ detail: options.uploadError.detail }, options.uploadError.status)
      }
      return json(
        {
          session_id: SESSION_ID,
          review_count: 6,
          skipped_empty: 1,
          top_ngrams: NGRAMS,
        },
        201,
      )
    }

    if (method === 'GET' && path === sessionPrefix) {
      const step = sessions[Math.min(sessionIndex++, sessions.length - 1)]
      if (step instanceof Error) throw step
      if (step === 'missing') return json({ detail: 'Session not found or expired' }, 404)
      return json(step)
    }

    if (method === 'POST' && path === `${sessionPrefix}/extract`) {
      if (extractFailures > 0) {
        extractFailures--
        return json({ detail: 'The language model server is unreachable.' }, 503)
      }
      return json({ product: PRODUCT })
    }

    if (method === 'PUT' && path === `${sessionPrefix}/product`) {
      return json({ product: (body as { product: ProductDetails }).product, confirmed: true })
    }

    if (method === 'POST' && path === `${sessionPrefix}/analyze`) {
      if (options.analyzeError) {
        return json({ detail: options.analyzeError.detail }, options.analyzeError.status)
      }
      return json({ job_id: 'job1' }, 202)
    }

    if (method === 'GET' && path === `${sessionPrefix}/job`) {
      const step = jobs[Math.min(jobIndex++, jobs.length - 1)]
      const value = typeof step === 'function' ? await step() : step
      if (value instanceof Error) throw value
      return json(value)
    }

    if (method === 'GET' && path === `${sessionPrefix}/results`) return json(RESULTS)

    return json({ detail: `unexpected ${method} ${path}` }, 404)
  }

  vi.stubGlobal('fetch', vi.fn(handler))
  return {
    calls,
    paths: () => calls.map((call) => `${call.method} ${call.path}`),
    count: (method: string, path: string) =>
      calls.filter((call) => call.method === method && call.path === path).length,
  }
}
