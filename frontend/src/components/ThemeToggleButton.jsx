import { Moon, Sun } from 'lucide-react'
import copy from '../copy'
import { useTheme } from '../contexts/ThemeContext'

export default function ThemeToggleButton({ className = '' }) {
  const { isDark, toggleTheme } = useTheme()

  return (
    <button
      type="button"
      className={['theme-toggle-btn', className].filter(Boolean).join(' ')}
      onClick={toggleTheme}
      aria-label={isDark ? copy.sidebar.themeToLight : copy.sidebar.themeToDark}
      title={isDark ? copy.sidebar.themeToLight : copy.sidebar.themeToDark}
    >
      {isDark ? <Sun size={20} /> : <Moon size={20} />}
    </button>
  )
}
