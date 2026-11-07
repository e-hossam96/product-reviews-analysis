import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { AppFooter } from './AppFooter'

describe('AppFooter', () => {
  it('credits the developer and links to their LinkedIn in a new tab', () => {
    render(<AppFooter />)
    expect(screen.getByText('Hossam Gamal Mostafa')).toBeInTheDocument()

    const link = screen.getByRole('link', { name: /LinkedIn/ })
    expect(link).toHaveAttribute('href', 'https://www.linkedin.com/in/e-hossam96')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', 'noopener noreferrer')
  })
})
