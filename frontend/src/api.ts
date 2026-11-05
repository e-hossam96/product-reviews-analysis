export const API_BASE = '/api/v1'

export interface ProductDetails {
  name: string
  aspects: string[]
}

export interface NgramCount {
  ngram: string
  count: number
}

export interface AppConfig {
  max_rows: number
  max_upload_mb: number
  max_aspects: number
  estimated_seconds_per_review: number
  tracing_enabled: boolean
}

export interface SessionCreated {
  session_id: string
  review_count: number
  skipped_empty: number
  top_ngrams: NgramCount[]
}

/** Where a session stands; lets a reloaded page pick up where the user left off. */
export interface SessionState {
  filename: string | null
  review_count: number
  top_ngrams: NgramCount[]
  product: ProductDetails | null
  product_confirmed: boolean
  job: JobState | null
}

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed'

export interface JobState {
  job_id: string
  status: JobStatus
  done: number
  total: number
  failed: number
  error: string | null
}

export interface AspectResult {
  aspect: string
  mean_score: number | null
  mention_count: number
  /** score ("1".."5") -> number of mentions; JSON object keys are strings */
  distribution: Record<string, number>
}

export interface Results {
  product_name: string
  review_count: number
  analyzed_count: number
  failed_count: number
  aspects: AspectResult[]
}

export class ApiError extends Error {
  readonly status: number

  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

/** A readable message from a failed response. Never shows raw HTML or stack traces. */
async function errorMessage(res: Response): Promise<string> {
  if (res.status === 429) {
    return 'Too many requests. Please wait a minute and try again.'
  }
  if (res.status === 413) {
    return 'The file is too large.'
  }
  try {
    const body: unknown = await res.json()
    const detail = isRecord(body) ? body.detail : undefined
    if (typeof detail === 'string') {
      return detail
    }
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (isRecord(item) && typeof item.msg === 'string' ? item.msg : null))
        .filter((msg): msg is string => msg !== null)
      if (messages.length > 0) {
        return messages.join('; ')
      }
    }
  } catch {
    // the body was not JSON (for example an nginx error page)
  }
  return `The server returned an error (${res.status}). Please try again.`
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, init)
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection and try again.', 0)
  }
  if (!res.ok) {
    throw new ApiError(await errorMessage(res), res.status)
  }
  return (await res.json()) as T
}

export function describeError(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
}

const sessionPath = (id: string) => `/sessions/${encodeURIComponent(id)}`

export function getConfig(): Promise<AppConfig> {
  return request<AppConfig>('/config')
}

export function createSession(file: File): Promise<SessionCreated> {
  const form = new FormData()
  form.append('file', file)
  return request<SessionCreated>('/sessions', { method: 'POST', body: form })
}

export function getSession(sessionId: string): Promise<SessionState> {
  return request<SessionState>(sessionPath(sessionId))
}

export async function extractProduct(sessionId: string): Promise<ProductDetails> {
  const body = await request<{ product: ProductDetails }>(`${sessionPath(sessionId)}/extract`, {
    method: 'POST',
  })
  return body.product
}

export async function confirmProduct(
  sessionId: string,
  product: ProductDetails,
): Promise<ProductDetails> {
  const body = await request<{ product: ProductDetails }>(`${sessionPath(sessionId)}/product`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ product }),
  })
  return body.product
}

export function startAnalysis(sessionId: string): Promise<{ job_id: string }> {
  return request<{ job_id: string }>(`${sessionPath(sessionId)}/analyze`, { method: 'POST' })
}

export function getJob(sessionId: string): Promise<JobState> {
  return request<JobState>(`${sessionPath(sessionId)}/job`)
}

export function getResults(sessionId: string): Promise<Results> {
  return request<Results>(`${sessionPath(sessionId)}/results`)
}

/** A plain link works for the download: same origin, and the session id is in the path. */
export function exportUrl(sessionId: string): string {
  return `${API_BASE}${sessionPath(sessionId)}/export.csv`
}
