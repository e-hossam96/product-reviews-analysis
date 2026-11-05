import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { RESULTS, SESSION_ID } from '../test/fakeBackend'
import { ResultsStep } from './ResultsStep'

const renderResults = (handlers = { onEdit: vi.fn(), onRestart: vi.fn() }) =>
  render(<ResultsStep sessionId={SESSION_ID} results={RESULTS} {...handlers} />)

describe('ResultsStep', () => {
  // Keep this first: the chart's code loads once per page, so only the first render waits.
  it('shows a placeholder while the chart loads, then the chart', async () => {
    renderResults()
    expect(screen.getByRole('status', { name: /loading chart/i })).toBeInTheDocument()
    expect(await screen.findByRole('img', { name: /average score/i })).toBeInTheDocument()
    expect(screen.queryByRole('status', { name: /loading chart/i })).not.toBeInTheDocument()
  })

  it('shows the numbers in a table whatever the chart does', () => {
    renderResults()
    const table = screen.getByRole('table')
    const screenRow = within(table).getByRole('row', { name: /^screen/ })
    expect(within(screenRow).getByText('4.50')).toBeInTheDocument()
    expect(within(table).getByRole('row', { name: /^battery life/ })).toHaveTextContent('–')
  })

  it('links to the CSV download', () => {
    renderResults()
    expect(screen.getByRole('link', { name: /download csv/i })).toHaveAttribute(
      'href',
      `/api/v1/sessions/${SESSION_ID}/export.csv`,
    )
  })

  it('calls back for editing and for starting over', async () => {
    const handlers = { onEdit: vi.fn(), onRestart: vi.fn() }
    renderResults(handlers)
    await userEvent.click(screen.getByRole('button', { name: /edit the aspects/i }))
    await userEvent.click(screen.getByRole('button', { name: /upload another file/i }))
    expect(handlers.onEdit).toHaveBeenCalledOnce()
    expect(handlers.onRestart).toHaveBeenCalledOnce()
  })
})
