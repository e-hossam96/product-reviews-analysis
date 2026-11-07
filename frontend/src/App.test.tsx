import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { StrictMode } from 'react'
import { describe, expect, it } from 'vitest'
import App from './App'
import { loadSessionId, saveSessionId } from './sessionStore'
import {
  PRODUCT,
  SESSION_ID,
  deferred,
  installFakeBackend,
  job,
  sessionState,
  type FakeOptions,
} from './test/fakeBackend'

const CSV = () => new File(['id,text\n1,Great screen'], 'reviews.csv', { type: 'text/csv' })

async function upload(user: ReturnType<typeof userEvent.setup>, file: File = CSV()) {
  await user.upload(await screen.findByLabelText(/choose a csv file/i), file)
}

function setup(options: FakeOptions = {}) {
  const backend = installFakeBackend(options)
  const user = userEvent.setup()
  render(<App pollIntervalMs={5} />)
  return { backend, user }
}

const confirmButton = () => screen.getByRole('button', { name: /confirm and analyze 6 reviews/i })
const chips = () => within(screen.getByRole('list', { name: 'Aspects' }))

describe('the whole flow', () => {
  it('goes from upload to results and offers the CSV', async () => {
    const gate = deferred()
    const { backend, user } = setup({
      jobs: [
        job('running', 2),
        async () => {
          await gate.promise
          return job('completed', 6)
        },
      ],
    })

    // the limits come from the backend before anything is chosen
    expect(await screen.findByText(/up to 100 reviews and 10 mb/i)).toBeInTheDocument()

    await upload(user)
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(
      screen.getByText(/6 reviews loaded from reviews.csv \(1 empty rows skipped\)/),
    ).toBeInTheDocument()
    expect(chips().getByText('screen')).toBeInTheDocument()
    expect(chips().getByText('battery life')).toBeInTheDocument()

    // add an aspect by typing, and another by clicking a phrase of the cloud
    await user.type(screen.getByLabelText(/add an aspect/i), 'Price{Enter}')
    await user.click(screen.getByRole('button', { name: 'battery life' })) // already there
    expect(screen.getByRole('status')).toHaveTextContent(/already in the list/)

    await user.click(confirmButton())
    expect(await screen.findByText('2 of 6 reviews scored')).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: /analysis progress/i })).toHaveValue(2)
    gate.resolve()

    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
    expect(screen.getByText(/5 of 6 reviews analyzed\. 1 could not be scored/)).toBeInTheDocument()
    const row = screen.getByRole('row', { name: /^screen/ })
    expect(within(row).getByText('4.50')).toBeInTheDocument()
    expect(
      within(screen.getByRole('row', { name: /^battery life/ })).getByText('–'),
    ).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: /average score/i })).toBeInTheDocument()

    const link = screen.getByRole('link', { name: /download csv/i })
    expect(link).toHaveAttribute('href', `/api/v1/sessions/${SESSION_ID}/export.csv`)
    expect(link).toHaveAttribute('download')

    // the backend saw exactly the confirmed details
    const put = backend.calls.find((call) => call.method === 'PUT')
    expect(put?.body).toEqual({
      product: { name: 'Galaxy S24', aspects: ['screen', 'battery life', 'price'] },
    })
    const order = backend.paths().filter((path, i, all) => all.indexOf(path) === i)
    expect(order).toEqual([
      'GET /config',
      'POST /sessions',
      `POST /sessions/${SESSION_ID}/extract`,
      `PUT /sessions/${SESSION_ID}/product`,
      `POST /sessions/${SESSION_ID}/analyze`,
      `GET /sessions/${SESSION_ID}/job`,
      `GET /sessions/${SESSION_ID}/results`,
    ])
  })

  it('lets the user go back and edit without extracting again', async () => {
    const { backend, user } = setup({ jobs: [job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByRole('heading', { name: 'Galaxy S24' })

    await user.click(screen.getByRole('button', { name: /edit the aspects/i }))
    expect(screen.getByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(chips().getByText('screen')).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(1)
  })

  it('starts over from the results', async () => {
    const { user } = setup({ jobs: [job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByRole('heading', { name: 'Galaxy S24' })

    await user.click(screen.getByRole('button', { name: /start over/i }))
    expect(await screen.findByText(/choose a csv file or drop it here/i)).toBeInTheDocument()
  })
})

describe('upload problems', () => {
  it('shows what the server did not like and stays on the page', async () => {
    const { user } = setup({
      uploadError: { status: 422, detail: "Missing required column 'text'. Found columns: id" },
    })
    await upload(user)
    expect(await screen.findByRole('alert')).toHaveTextContent("Missing required column 'text'")
    expect(screen.getByText(/choose a csv file or drop it here/i)).toBeInTheDocument()
  })

  it('refuses a file that is not a CSV without calling the server', async () => {
    const backend = installFakeBackend()
    const user = userEvent.setup({ applyAccept: false })
    render(<App pollIntervalMs={5} />)
    await upload(user, new File(['hello'], 'notes.txt', { type: 'text/plain' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Please choose a .csv file.')
    expect(backend.count('POST', '/sessions')).toBe(0)
  })

  it('refuses a file over the size limit without calling the server', async () => {
    const backend = installFakeBackend()
    const user = userEvent.setup()
    render(<App pollIntervalMs={5} />)
    await screen.findByText(/up to 100 reviews/i) // config loaded
    const big = new File(['x'], 'big.csv', { type: 'text/csv' })
    Object.defineProperty(big, 'size', { value: 11 * 1024 * 1024 })
    await upload(user, big)
    expect(await screen.findByRole('alert')).toHaveTextContent(/larger than the 10 MB limit/)
    expect(backend.count('POST', '/sessions')).toBe(0)
  })
})

describe('when suggesting product details goes wrong', () => {
  it('offers to try again', async () => {
    const { user } = setup({ extractFailures: 1 })
    await upload(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      /language model server is unreachable/,
    )
    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByDisplayValue(PRODUCT.name)).toBeInTheDocument()
  })

  it('lets the user type the details in instead', async () => {
    const { backend, user } = setup({ extractFailures: 5, jobs: [job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /enter the details manually/i }))

    expect(confirmButton()).toBeDisabled() // nothing to confirm yet
    await user.type(screen.getByLabelText(/product name/i), 'My Phone')
    expect(confirmButton()).toBeDisabled() // still no aspect
    await user.type(screen.getByLabelText(/add an aspect/i), 'camera{Enter}')
    expect(confirmButton()).toBeEnabled()

    await user.click(confirmButton())
    await screen.findByRole('heading', { name: 'Galaxy S24' })
    const put = backend.calls.find((call) => call.method === 'PUT')
    expect(put?.body).toEqual({ product: { name: 'My Phone', aspects: ['camera'] } })
  })

  it('sends the name with its spaces cleaned up', async () => {
    const { backend, user } = setup({ jobs: [job('completed', 6)] })
    await upload(user)
    const name = await screen.findByLabelText(/product name/i)
    await user.clear(name)
    await user.type(name, '  My   Phone  ')
    await user.click(confirmButton())
    await screen.findByRole('heading', { name: 'Galaxy S24' })
    const put = backend.calls.find((call) => call.method === 'PUT')
    expect(put?.body).toEqual({
      product: { name: 'My Phone', aspects: ['screen', 'battery life'] },
    })
  })

  it('keeps the form when "Suggest again" replaces the suggestion', async () => {
    const { backend, user } = setup()
    await upload(user)
    await screen.findByDisplayValue('Galaxy S24')
    await user.clear(screen.getByLabelText(/product name/i))
    await user.type(screen.getByLabelText(/product name/i), 'Edited')
    await user.click(screen.getByRole('button', { name: /suggest again/i }))
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(2)
  })

  it('shows a server refusal when confirming and lets the user retry', async () => {
    const { user } = setup({
      analyzeError: { status: 409, detail: 'An analysis is already running for this session' },
    })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/already running/)
    expect(confirmButton()).toBeEnabled()
  })
})

describe('while the analysis runs', () => {
  it('reports failed reviews and the time left', async () => {
    const gate = deferred()
    const { user } = setup({
      jobs: [
        job('running', 3, { failed: 2 }),
        async () => {
          await gate.promise
          return job('completed', 6)
        },
      ],
    })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    expect(
      await screen.findByText(/3 of 6 reviews scored · 2 could not be scored/),
    ).toBeInTheDocument()
    expect(screen.getByText(/time left: under a minute/i)).toBeInTheDocument()
    gate.resolve()
    await screen.findByRole('heading', { name: 'Galaxy S24' })
  })

  it('offers a retry when the analysis stops, and recovers', async () => {
    const { backend, user } = setup({
      jobs: [
        job('failed', 3, { error: 'The language model server stopped responding' }),
        job('completed', 6),
      ],
    })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))

    expect(
      await screen.findByRole('heading', { name: /the analysis stopped/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('alert')[0]).toHaveTextContent(/stopped responding/)
    expect(screen.getByText(/3 of 6 reviews were processed/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/analyze`)).toBe(2)
  })

  it('stops the analysis on request and stops polling', async () => {
    const { backend, user } = setup({ jobs: [job('running', 2)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByText(/2 of 6 reviews scored/)

    await user.click(screen.getByRole('button', { name: /stop analysis/i }))
    expect(
      await screen.findByRole('heading', { name: /the analysis stopped/i }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('alert')[0]).toHaveTextContent(/you stopped the analysis/i)
    expect(backend.count('POST', `/sessions/${SESSION_ID}/job/stop`)).toBe(1)

    const polls = backend.count('GET', `/sessions/${SESSION_ID}/job`)
    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(backend.count('GET', `/sessions/${SESSION_ID}/job`)).toBe(polls)
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
  })

  it('carries on when there was nothing left to stop', async () => {
    const gate = deferred()
    const { user } = setup({
      jobs: [
        job('running', 5),
        async () => {
          await gate.promise
          return job('completed', 6)
        },
      ],
      stop: { status: 409, detail: 'No analysis is running for this session' },
    })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByText(/5 of 6 reviews scored/)
    await user.click(screen.getByRole('button', { name: /stop analysis/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/no analysis is running/i)
    gate.resolve()
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
  })

  it('goes back to the aspects from a failed analysis', async () => {
    const { user } = setup({ jobs: [job('failed', 0, { error: 'Every review failed' })] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await user.click(await screen.findByRole('button', { name: /edit the aspects/i }))
    expect(screen.getByDisplayValue('Galaxy S24')).toBeInTheDocument()
  })

  it('shrugs off a couple of failed polls', async () => {
    const offline = new TypeError('Failed to fetch')
    const { user } = setup({ jobs: [offline, offline, job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
  })

  it('gives up after three failed polls, and checks again on request', async () => {
    const offline = new TypeError('Failed to fetch')
    const { backend, user } = setup({ jobs: [offline, offline, offline, job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))

    expect(await screen.findByRole('heading', { name: /lost contact/i })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot reach the server/i)
    await user.click(screen.getByRole('button', { name: /check again/i }))

    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/analyze`)).toBe(1) // not started twice
  })
})

describe('React StrictMode', () => {
  it('still runs the flow once per action', async () => {
    const backend = installFakeBackend({ jobs: [job('running', 1), job('completed', 6)] })
    const user = userEvent.setup()
    render(
      <StrictMode>
        <App pollIntervalMs={5} />
      </StrictMode>,
    )
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()

    // effects run twice in development, but only reads may repeat
    expect(backend.count('POST', '/sessions')).toBe(1)
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(1)
    expect(backend.count('POST', `/sessions/${SESSION_ID}/analyze`)).toBe(1)
  })
})

describe('remembering the session', () => {
  it('stores the session id after an upload', async () => {
    const { user } = setup()
    await upload(user)
    await screen.findByDisplayValue('Galaxy S24')
    expect(loadSessionId()).toBe(SESSION_ID)
  })

  it('offers "Start over" everywhere except the upload page', async () => {
    const { user } = setup()
    expect(screen.queryByRole('button', { name: /start over/i })).not.toBeInTheDocument()
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /start over/i }))
    expect(await screen.findByText(/choose a csv file or drop it here/i)).toBeInTheDocument()
    expect(loadSessionId()).toBeNull()
  })

  it('forgets the session when the user starts over from the results', async () => {
    const { user } = setup({ jobs: [job('completed', 6)] })
    await upload(user)
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByRole('heading', { name: 'Galaxy S24' })
    await user.click(screen.getByRole('button', { name: /start over/i }))
    expect(loadSessionId()).toBeNull()
  })
})

describe('after a page reload', () => {
  function reload(options: FakeOptions) {
    saveSessionId(SESSION_ID)
    return setup(options)
  }

  it('says it is restoring, then asks the model if no details were saved yet', async () => {
    const { backend } = reload({ sessions: [sessionState()] })
    expect(screen.getByText(/restoring your session/i)).toBeInTheDocument()
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(screen.getByText(/6 reviews loaded from reviews.csv\./)).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(1)
  })

  it('shows the saved suggestion without asking the model again', async () => {
    const { backend } = reload({ sessions: [sessionState({ product: PRODUCT })] })
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(chips().getByText('battery life')).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(0)
  })

  it('shows the details the user had confirmed', async () => {
    const { backend } = reload({
      sessions: [
        sessionState({
          product: { name: 'My Phone', aspects: ['camera'] },
          product_confirmed: true,
        }),
      ],
    })
    expect(await screen.findByDisplayValue('My Phone')).toBeInTheDocument()
    expect(chips().getByText('camera')).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(0)
  })

  it('goes back to the progress screen while the analysis is running', async () => {
    const { backend } = reload({
      sessions: [
        sessionState({ product: PRODUCT, product_confirmed: true, job: job('running', 2) }),
      ],
      jobs: [job('running', 3), job('completed', 6)],
    })
    expect(await screen.findByText('3 of 6 reviews scored')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/analyze`)).toBe(0) // not started again
  })

  it('shows the results straight away when the analysis had finished', async () => {
    const { backend, user } = reload({
      sessions: [
        sessionState({ product: PRODUCT, product_confirmed: true, job: job('completed', 6) }),
      ],
    })
    expect(await screen.findByRole('heading', { name: 'Galaxy S24' })).toBeInTheDocument()
    expect(backend.count('GET', `/sessions/${SESSION_ID}/results`)).toBe(1)
    expect(backend.count('GET', `/sessions/${SESSION_ID}/job`)).toBe(0)

    await user.click(screen.getByRole('button', { name: /edit the aspects/i }))
    expect(screen.getByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(chips().getByText('screen')).toBeInTheDocument()
  })

  it('shows an analysis that had stopped, with its error', async () => {
    reload({
      sessions: [
        sessionState({
          product: PRODUCT,
          product_confirmed: true,
          job: job('failed', 3, { error: 'The language model server stopped responding' }),
        }),
      ],
      jobs: [job('failed', 3, { error: 'The language model server stopped responding' })],
    })
    expect(
      await screen.findByRole('heading', { name: /the analysis stopped/i }),
    ).toBeInTheDocument()
  })

  it('starts fresh when the session has expired', async () => {
    reload({ sessions: ['missing'] })
    expect(await screen.findByText(/choose a csv file or drop it here/i)).toBeInTheDocument()
    expect(loadSessionId()).toBeNull()
  })

  it('lets the user try again when the server cannot be reached', async () => {
    const { user } = reload({
      sessions: [new TypeError('Failed to fetch'), sessionState({ product: PRODUCT })],
    })
    expect(await screen.findByRole('heading', { name: /could not restore/i })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent(/cannot reach the server/i)
    expect(loadSessionId()).toBe(SESSION_ID) // kept, because the session may still be fine

    await user.click(screen.getByRole('button', { name: /try again/i }))
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
  })

  it('lets the user give up on a session that cannot be restored', async () => {
    const { user } = reload({ sessions: [new TypeError('Failed to fetch')] })
    await screen.findByRole('heading', { name: /could not restore/i })
    await user.click(screen.getByRole('button', { name: /start over/i }))
    expect(await screen.findByText(/choose a csv file or drop it here/i)).toBeInTheDocument()
    expect(loadSessionId()).toBeNull()
  })

  it('asks the model only once under React StrictMode', async () => {
    saveSessionId(SESSION_ID)
    const backend = installFakeBackend({ sessions: [sessionState()] })
    render(
      <StrictMode>
        <App pollIntervalMs={5} />
      </StrictMode>,
    )
    expect(await screen.findByDisplayValue('Galaxy S24')).toBeInTheDocument()
    expect(backend.count('POST', `/sessions/${SESSION_ID}/extract`)).toBe(1)
  })
})

describe('the note about stored responses', () => {
  it('is shown when tracing is on', async () => {
    setup({ tracing: true })
    expect(await screen.findByRole('note')).toHaveTextContent('LLM Tracing On')
  })

  it('is not shown when tracing is off', async () => {
    setup({ tracing: false })
    await screen.findByText(/up to 100 reviews/i) // the config has arrived
    expect(screen.queryByRole('note')).not.toBeInTheDocument()
  })
})
