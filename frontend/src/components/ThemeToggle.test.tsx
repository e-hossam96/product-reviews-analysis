import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { THEME_KEY, setPreference } from '../theme'
import { ThemeToggle } from './ThemeToggle'

afterEach(() => {
  setPreference('system')
})

describe('ThemeToggle', () => {
  it('follows the system until a theme is picked', () => {
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Match system theme' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('pins the chosen theme on the page and remembers it', async () => {
    const user = userEvent.setup()
    render(<ThemeToggle />)

    await user.click(screen.getByRole('button', { name: 'Dark theme' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark theme' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )

    await user.click(screen.getByRole('button', { name: 'Match system theme' }))
    expect(document.documentElement.dataset.theme).toBeUndefined()
    expect(localStorage.getItem(THEME_KEY)).toBeNull()
  })
})
