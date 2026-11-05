import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { AspectEditor } from './AspectEditor'

function Harness({ initial = ['screen'], max = 3 }: { initial?: string[]; max?: number }) {
  const [aspects, setAspects] = useState(initial)
  return <AspectEditor aspects={aspects} max={max} onChange={setAspects} />
}

const chips = () =>
  screen.getAllByRole('listitem').map((item) => item.textContent?.replace('×', '').trim())

describe('AspectEditor', () => {
  it('adds a normalized aspect with Enter and clears the input', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    const input = screen.getByLabelText(/add an aspect/i)
    await user.type(input, '  Battery   LIFE {Enter}')
    expect(chips()).toEqual(['screen', 'battery life'])
    expect(input).toHaveValue('')
    expect(screen.getByText('2 of 3 aspects')).toBeInTheDocument()
  })

  it('adds with the button too', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.type(screen.getByLabelText(/add an aspect/i), 'price')
    await user.click(screen.getByRole('button', { name: 'Add' }))
    expect(chips()).toEqual(['screen', 'price'])
  })

  it('removes an aspect', async () => {
    const user = userEvent.setup()
    render(<Harness initial={['screen', 'price']} />)
    await user.click(screen.getByRole('button', { name: 'Remove screen' }))
    expect(chips()).toEqual(['price'])
  })

  it('refuses a duplicate and says why', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.type(screen.getByLabelText(/add an aspect/i), 'SCREEN{Enter}')
    expect(chips()).toEqual(['screen'])
    expect(screen.getByRole('status')).toHaveTextContent(/already in the list/)
  })

  it('refuses to go over the maximum', async () => {
    const user = userEvent.setup()
    render(<Harness initial={['a', 'b', 'c']} max={3} />)
    await user.type(screen.getByLabelText(/add an aspect/i), 'd{Enter}')
    expect(chips()).toEqual(['a', 'b', 'c'])
    expect(screen.getByRole('status')).toHaveTextContent(/at most 3 aspects/)
  })

  it('ignores an empty submit quietly', async () => {
    const user = userEvent.setup()
    render(<Harness />)
    await user.type(screen.getByLabelText(/add an aspect/i), '   {Enter}')
    expect(chips()).toEqual(['screen'])
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
