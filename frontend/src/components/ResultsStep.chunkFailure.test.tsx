import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { RESULTS, SESSION_ID } from '../test/fakeBackend'
import { ResultsStep } from './ResultsStep'

// Simulates the chart's file being gone, as after a new release while the page was open.
vi.mock('./lazyChart', () => ({
  loadChart: () => Promise.reject(new Error('Failed to fetch dynamically imported module')),
}))

describe('ResultsStep when the chart cannot be loaded', () => {
  it('says so and still shows the numbers', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {}) // React logs the caught error
    render(<ResultsStep sessionId={SESSION_ID} results={RESULTS} onEdit={() => {}} />)

    expect(await screen.findByRole('alert')).toHaveTextContent(/chart could not be loaded/i)
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /download csv/i })).toBeInTheDocument()
  })
})
