import { useState, type ChangeEvent, type DragEvent } from 'react'
import { createSession, describeError, type AppConfig, type SessionCreated } from '../api'
import { ErrorBanner } from './ErrorBanner'
import { UploadIcon } from './icons'

const BYTES_PER_MB = 1024 * 1024

interface Props {
  config: AppConfig | null
  onUploaded: (created: SessionCreated, filename: string) => void
}

function validateFile(file: File, config: AppConfig | null): string | null {
  if (!file.name.toLowerCase().endsWith('.csv')) {
    return 'Please choose a .csv file.'
  }
  if (config && file.size > config.max_upload_mb * BYTES_PER_MB) {
    return `The file is larger than the ${config.max_upload_mb} MB limit.`
  }
  return null
}

export function UploadStep({ config, onUploaded }: Props) {
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function upload(file: File) {
    const invalid = validateFile(file, config)
    setError(invalid)
    if (invalid) return

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
    if (file) void upload(file)
  }

  function handleDragOver(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(true)
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    const file = event.dataTransfer.files[0]
    if (file && !busy) void upload(file)
  }

  const dropzoneClass = ['dropzone', dragging && 'dragging', busy && 'busy']
    .filter(Boolean)
    .join(' ')

  return (
    <section className="card">
      <h2>Upload your reviews</h2>
      <p>
        Choose a CSV file with a <code>text</code> column, one review per row, all about the same
        product.
        {config && ` Up to ${config.max_rows} reviews and ${config.max_upload_mb} MB.`}
      </p>
      <label
        className={dropzoneClass}
        onDragOver={handleDragOver}
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
        <span className="dropzone-icon">
          <UploadIcon />
        </span>
        <span className="dropzone-title">
          {busy ? 'Uploading…' : 'Choose a CSV file or drop it here'}
        </span>
      </label>
      <ErrorBanner message={error} />
    </section>
  )
}
