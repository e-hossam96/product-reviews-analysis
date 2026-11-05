import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ChartBoundary } from './ChartBoundary'

function Bomb(): never {
  throw new Error('boom')
}

describe('ChartBoundary', () => {
  it('shows its children when nothing goes wrong', () => {
    render(
      <ChartBoundary>
        <p>chart</p>
      </ChartBoundary>,
    )
    expect(screen.getByText('chart')).toBeInTheDocument()
  })

  it('replaces a crashing child with a message', () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <ChartBoundary>
        <Bomb />
      </ChartBoundary>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(/reload the page/i)
  })
})
