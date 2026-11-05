export type Step = 'upload' | 'review' | 'progress' | 'results'

const STEPS: { id: Step; label: string }[] = [
  { id: 'upload', label: 'Upload' },
  { id: 'review', label: 'Review' },
  { id: 'progress', label: 'Analyze' },
  { id: 'results', label: 'Results' },
]

export function Stepper({ current }: { current: Step }) {
  const currentIndex = STEPS.findIndex((step) => step.id === current)
  return (
    <ol className="stepper" aria-label="Progress">
      {STEPS.map((step, index) => (
        <li
          key={step.id}
          className={index === currentIndex ? 'current' : index < currentIndex ? 'done' : ''}
          aria-current={index === currentIndex ? 'step' : undefined}
        >
          <span className="step-number">{index + 1}</span>
          {step.label}
        </li>
      ))}
    </ol>
  )
}
