import { useState, type ChangeEvent, type DragEvent } from 'react'
import { createSession, describeError, type AppConfig, type SessionCreated } from '../api'
import { ErrorBanner } from './ErrorBanner'

interface Props {
  config: AppConfig | null
  onUploaded: (created: SessionCreated, filename: string) => void
}

export function UploadStep({ config, onUploaded }: Props) {
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFile(file: File) {
    setError(null)
    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please choose a .csv file.')
      return
    }
    if (config && file.size > config.max_upload_mb * 1024 * 1024) {
      setError(`The file is larger than the ${config.max_upload_mb} MB limit.`)
      return
    }
    setBusy(true)
    try {
      onUploaded(await createSession(file), file.name)
    } catch (e) {
      setError(describeError(e))
    } finally {
      setBusy(false)
    }
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    event.target.value = '' // lets the same file be chosen again after an error
    if (file) {
      void handleFile(file)
    }
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file && !busy) {
      void handleFile(file)
    }
  }

  return (
    <section className="card">
      <h2>Upload your reviews</h2>
      <p>
        Choose a CSV file with a <code>text</code> column, one review per row, all about the same
        product.
        {config && ` Up to ${config.max_rows} reviews and ${config.max_upload_mb} MB.`}
      </p>
      <label
        className={`dropzone${dragging ? ' dragging' : ''}${busy ? ' busy' : ''}`}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          type="file"
          accept=".csv,text/csv"
          className="visually-hidden"
          disabled={busy}
          onChange={handleChange}
        />
        <span className="dropzone-title">
          {busy ? 'Uploading…' : 'Choose a CSV file or drop it here'}
        </span>
      </label>
      <ErrorBanner message={error} />
    </section>
  )
}
