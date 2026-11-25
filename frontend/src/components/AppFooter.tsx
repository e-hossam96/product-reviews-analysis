const AUTHOR = 'Hossam Gamal Mostafa'
const LINKEDIN_URL = 'https://www.linkedin.com/in/e-hossam96'

export function AppFooter() {
  return (
    <footer className="app-footer">
      <p>
        Built by <span>{AUTHOR}</span> ·{' '}
        <a
          href={LINKEDIN_URL}
          target="_blank"
          rel="noopener noreferrer"
          aria-label={`${AUTHOR} on LinkedIn (opens in a new tab)`}
        >
          LinkedIn
        </a>
      </p>
    </footer>
  )
}
