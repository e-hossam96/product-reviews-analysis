import { useState, type FormEvent } from 'react'
import { MAX_ASPECT_LENGTH, addAspect } from '../aspects'

interface Props {
  aspects: string[]
  max: number
  onChange: (aspects: string[]) => void
}

export function AspectEditor({ aspects, max, onChange }: Props) {
  const [draft, setDraft] = useState('')
  const [error, setError] = useState<string | null>(null)

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const result = addAspect(aspects, draft, max)
    setError(result.error)
    if (result.error === null) {
      onChange(result.aspects)
      setDraft('')
    }
  }

  return (
    <div className="aspect-editor">
      <ul className="chips" aria-label="Aspects">
        {aspects.map((aspect) => (
          <li key={aspect} className="chip">
            {aspect}
            <button
              type="button"
              aria-label={`Remove ${aspect}`}
              onClick={() => onChange(aspects.filter((item) => item !== aspect))}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      <form className="inline-form" onSubmit={handleSubmit}>
        <label className="visually-hidden" htmlFor="new-aspect">
          Add an aspect
        </label>
        <input
          id="new-aspect"
          value={draft}
          maxLength={MAX_ASPECT_LENGTH + 10}
          placeholder="Add an aspect, for example “battery life”"
          onChange={(event) => setDraft(event.target.value)}
        />
        <button type="submit" className="secondary">
          Add
        </button>
      </form>
      <p className="muted small">
        {aspects.length} of {max} aspects
      </p>
      {error && (
        <p className="banner warn" role="status">
          {error}
        </p>
      )}
    </div>
  )
}
