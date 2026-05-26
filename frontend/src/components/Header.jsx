export default function Header({ theme, onToggle }) {
  const isDark = theme === 'dark'
  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="site-logo">The PM-AI Hiring Index</div>
        <button
          className="theme-toggle"
          onClick={onToggle}
          aria-label={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {isDark ? 'Dark mode' : 'Light mode'}
        </button>
      </div>
    </header>
  )
}
