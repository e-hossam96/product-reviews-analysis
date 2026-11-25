import { Stepper, type Step } from './Stepper'
import { ThemeToggle } from './ThemeToggle'

const TRACING_NOTICE = 'Model responses are logged for debugging.'

interface Props {
  step: Step
  tracingEnabled: boolean
  onRestart: () => void
}

export function AppHeader({ step, tracingEnabled, onRestart }: Props) {
  return (
    <header className="app-header">
      <div className="app-bar">
        <h1 className="wordmark">Product reviews analysis</h1>
        <div className="header-actions">
          {step !== 'upload' && (
            <button type="button" className="secondary" onClick={onRestart}>
              Start over
            </button>
          )}
          <ThemeToggle />
        </div>
      </div>
      <Stepper current={step} />
      {tracingEnabled && (
        <p className="notice muted small" role="note">
          {TRACING_NOTICE}
        </p>
      )}
    </header>
  )
}
