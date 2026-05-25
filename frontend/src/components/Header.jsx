export default function Header({ theme, onToggle }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="site-brand">
          <div className="site-logo">The PM-AI Hiring Index</div>
          <div className="site-tagline">Product Manager hiring, measured against AI demand</div>
        </div>
        <div className="header-right">
          <div className="header-dateline">Updated daily · 6 a.m. PT</div>
          <button className="theme-toggle" onClick={onToggle} aria-label="Toggle color mode">
            {theme === 'dark' ? '◐ Light' : '◑ Dark'}
          </button>
        </div>
      </div>
    </header>
  )
}
