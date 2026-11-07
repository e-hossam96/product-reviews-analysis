import type { ReactNode } from 'react'
import { setPreference, useThemePreference, type ThemePreference } from '../theme'
import { MonitorIcon, MoonIcon, SunIcon } from './icons'

const OPTIONS: { value: ThemePreference; label: string; icon: ReactNode }[] = [
  { value: 'system', label: 'Match system theme', icon: <MonitorIcon /> },
  { value: 'light', label: 'Light theme', icon: <SunIcon /> },
  { value: 'dark', label: 'Dark theme', icon: <MoonIcon /> },
]

export function ThemeToggle() {
  const preference = useThemePreference()
  return (
    <div className="theme-toggle" role="group" aria-label="Color theme">
      {OPTIONS.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-label={option.label}
          title={option.label}
          aria-pressed={preference === option.value}
          onClick={() => setPreference(option.value)}
        >
          {option.icon}
        </button>
      ))}
    </div>
  )
}
