import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  confirmProduct,
  createSession,
  describeError,
  exportUrl,
  getJob,
  getSession,
  startAnalysis,
} from './api'

function respond(body: BodyInit | null, status: number, headers: HeadersInit = {}) {
  const fetchMock = vi.fn(async () => new Response(body, { status, headers }))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const respondJson = (body: unknown, status = 200) =>
  respond(JSON.stringify(body), status, { 'Content-Type': 'application/json' })

async function failure(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise
  } catch (e) {
    expect(e).toBeInstanceOf(ApiError)
    return e as ApiError
  }
  throw new Error('expected the request to fail')
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('error messages', () => {
  it('uses the detail string the backend sends', async () => {
    respondJson({ detail: "Missing required column 'text'." }, 422)
    const error = await failure(createSession(new File(['x'], 'a.csv')))
    expect(error.message).toBe("Missing required column 'text'.")
    expect(error.status).toBe(422)
  })

  it('joins the messages of a validation error list', async () => {
    respondJson(
      { detail: [{ msg: 'String should have at least 1 character' }, { msg: 'Too short' }] },
      422,
    )
    const error = await failure(confirmProduct('abc', { name: '', aspects: [] }))
    expect(error.message).toBe('String should have at least 1 character; Too short')
  })

  it('explains rate limiting', async () => {
    respondJson({ error: 'Rate limit exceeded: 5 per 1 minute' }, 429)
    expect((await failure(startAnalysis('abc'))).message).toMatch(/wait a minute/)
  })

  it('never shows an HTML error page', async () => {
    respond('<html><body>502 Bad Gateway</body></html>', 502, { 'Content-Type': 'text/html' })
    const error = await failure(getJob('abc'))
    expect(error.message).toBe('The server returned an error (502). Please try again.')
  })

  it('reports an unreachable server', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const error = await failure(getJob('abc'))
    expect(error.status).toBe(0)
    expect(error.message).toMatch(/Cannot reach the server/)
  })

  it('describes any error, not only API ones', () => {
    expect(describeError(new Error('boom'))).toBe('boom')
    expect(describeError('weird')).toMatch(/Something went wrong/)
  })
})

describe('requests', () => {
  it('uploads the file as multipart form data under "file"', async () => {
    const fetchMock = respondJson(
      { session_id: 's', review_count: 1, skipped_empty: 0, top_ngrams: [] },
      201,
    )
    const file = new File(['id,text\n1,hi'], 'reviews.csv', { type: 'text/csv' })
    await createSession(file)

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/v1/sessions')
    expect(init.method).toBe('POST')
    expect((init.body as FormData).get('file')).toBe(file)
  })

  it('sends the product as JSON and returns the normalized one', async () => {
    const fetchMock = respondJson({ product: { name: 'X', aspects: ['a'] }, confirmed: true })
    const saved = await confirmProduct('abc', { name: ' X ', aspects: ['A'] })

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/v1/sessions/abc/product')
    expect(init.method).toBe('PUT')
    expect(JSON.parse(init.body as string)).toEqual({ product: { name: ' X ', aspects: ['A'] } })
    expect(saved).toEqual({ name: 'X', aspects: ['a'] })
  })

  it('encodes the session id in the path', async () => {
    const fetchMock = respondJson({})
    await getJob('a/b c')
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe(
      '/api/v1/sessions/a%2Fb%20c/job',
    )
  })

  it('reads where a session stands', async () => {
    const state = {
      filename: 'reviews.csv',
      review_count: 3,
      top_ngrams: [],
      product: null,
      product_confirmed: false,
      job: null,
    }
    const fetchMock = respondJson(state)
    expect(await getSession('abc')).toEqual(state)
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe('/api/v1/sessions/abc')
  })

  it('builds the download link', () => {
    expect(exportUrl('abc')).toBe('/api/v1/sessions/abc/export.csv')
  })
})
