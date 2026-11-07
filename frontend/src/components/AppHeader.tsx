import { BarChartIcon, InfoIcon } from './icons'
import { Stepper, type Step } from './Stepper'
import { ThemeToggle } from './ThemeToggle'

const TRACING_NOTICE = 'LLM Tracing On'

interface Props {
  step: Step
  tracingEnabled: boolean
  onRestart: () => void
}

export function AppHeader({ step, tracingEnabled, onRestart }: Props) {
  return (
    <header className="app-header">
      <div className="app-title">
        <div className="brand">
          <span className="brand-mark">
            <BarChartIcon />
          </span>
          <div>
            <h1>Product reviews analysis</h1>
            <p className="brand-tagline">See what customers say about each aspect</p>
          </div>
        </div>
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
        <p className="notice" role="note">
          <InfoIcon />
          {TRACING_NOTICE}
        </p>
      )}
    </header>
  )
}
