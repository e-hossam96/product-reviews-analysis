import { LinkedInIcon } from './icons'

const AUTHOR = 'Hossam Gamal Mostafa'
const LINKEDIN_URL = 'https://www.linkedin.com/in/e-hossam96'
const LINKEDIN_HANDLE = 'in/e-hossam96'

export function AppFooter() {
  return (
    <footer className="app-footer">
      <p className="footer-credit">
        Developed by <strong>{AUTHOR}</strong>
      </p>
      <a
        className="footer-link"
        href={LINKEDIN_URL}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={`${AUTHOR} on LinkedIn (opens in a new tab)`}
      >
        <LinkedInIcon />
        <span>{LINKEDIN_HANDLE}</span>
      </a>
    </footer>
  )
}
