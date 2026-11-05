import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from './App'
import { installFakeBackend, job } from './test/fakeBackend'

const loadChart = vi.hoisted(() => vi.fn())

vi.mock('./components/lazyChart', () => ({ loadChart }))

describe('chart prefetch', () => {
  it('starts loading the chart when the analysis starts, not when the results arrive', async () => {
    loadChart.mockResolvedValue({ default: () => <p>chart</p> })
    installFakeBackend({ jobs: [job('running', 1)] }) // never finishes
    const user = userEvent.setup()
    render(<App pollIntervalMs={5} />)

    expect(loadChart).not.toHaveBeenCalled()
    await user.upload(
      await screen.findByLabelText(/choose a csv file/i),
      new File(['id,text\n1,hi'], 'reviews.csv', { type: 'text/csv' }),
    )
    await user.click(await screen.findByRole('button', { name: /confirm and analyze/i }))
    await screen.findByText(/of 6 reviews scored/)
    expect(loadChart).toHaveBeenCalledOnce()
  })
})
