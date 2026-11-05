import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { WordCloud } from './WordCloud'

const NGRAMS = [
  { ngram: 'battery life', count: 20 },
  { ngram: 'screen', count: 5 },
  { ngram: 'price', count: 2 },
]

const fontSize = (name: string) => parseFloat(screen.getByRole('button', { name }).style.fontSize)

describe('WordCloud', () => {
  it('sizes phrases by how many reviews contain them', () => {
    render(<WordCloud ngrams={NGRAMS} selected={[]} onPick={() => {}} />)
    expect(fontSize('battery life')).toBeGreaterThan(fontSize('screen'))
    expect(fontSize('screen')).toBeGreaterThan(fontSize('price'))
    expect(fontSize('battery life')).toBeLessThanOrEqual(2.4)
    expect(fontSize('price')).toBeGreaterThanOrEqual(0.9)
  })

  it('uses a middle size when every count is equal', () => {
    render(
      <WordCloud
        ngrams={[
          { ngram: 'a', count: 3 },
          { ngram: 'b', count: 3 },
        ]}
        selected={[]}
        onPick={() => {}}
      />,
    )
    expect(fontSize('a')).toBe(fontSize('b'))
  })

  it('marks phrases that are already aspects', () => {
    render(<WordCloud ngrams={NGRAMS} selected={['screen']} onPick={() => {}} />)
    expect(screen.getByRole('button', { name: 'screen' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'price' })).toHaveAttribute('aria-pressed', 'false')
  })

  it('reports the phrase that was clicked', async () => {
    const onPick = vi.fn()
    render(<WordCloud ngrams={NGRAMS} selected={[]} onPick={onPick} />)
    await userEvent.click(screen.getByRole('button', { name: 'price' }))
    expect(onPick).toHaveBeenCalledWith('price')
  })

  it('explains an empty cloud', () => {
    render(<WordCloud ngrams={[]} selected={[]} onPick={() => {}} />)
    expect(screen.getByText(/no repeated phrases/i)).toBeInTheDocument()
  })
})
