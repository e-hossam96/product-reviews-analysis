import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PhraseList, VISIBLE_PHRASES } from './PhraseList'

const NGRAMS = [
  { ngram: 'price', count: 2 },
  { ngram: 'battery life', count: 20 },
  { ngram: 'screen', count: 5 },
]

const phrase = (name: string) => screen.getByRole('button', { name: new RegExp(`^${name},`) })

describe('PhraseList', () => {
  it('ranks phrases by how many reviews contain them and shows the count', () => {
    render(<PhraseList ngrams={NGRAMS} selected={[]} onPick={() => {}} />)
    const names = screen.getAllByRole('button').map((button) => button.textContent)
    expect(names).toEqual(['battery life20', 'screen5', 'price2'])
    expect(phrase('screen')).toHaveAccessibleName('screen, in 5 reviews')
  })

  it('marks phrases that are already aspects', () => {
    render(<PhraseList ngrams={NGRAMS} selected={['screen']} onPick={() => {}} />)
    expect(phrase('screen')).toHaveAttribute('aria-pressed', 'true')
    expect(phrase('price')).toHaveAttribute('aria-pressed', 'false')
  })

  it('reports the phrase that was clicked', async () => {
    const onPick = vi.fn()
    render(<PhraseList ngrams={NGRAMS} selected={[]} onPick={onPick} />)
    await userEvent.click(phrase('price'))
    expect(onPick).toHaveBeenCalledWith('price')
  })

  it('shows the top phrases first and the rest on request', async () => {
    const many = Array.from({ length: VISIBLE_PHRASES + 6 }, (_, i) => ({
      ngram: `phrase ${i}`,
      count: 100 - i,
    }))
    render(<PhraseList ngrams={many} selected={[]} onPick={() => {}} />)
    expect(screen.queryByRole('button', { name: /^phrase 29,/ })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Show all 30 phrases' }))
    expect(phrase('phrase 29')).toBeInTheDocument()
  })

  it('explains an empty list', () => {
    render(<PhraseList ngrams={[]} selected={[]} onPick={() => {}} />)
    expect(screen.getByText(/no repeated phrases/i)).toBeInTheDocument()
  })
})
