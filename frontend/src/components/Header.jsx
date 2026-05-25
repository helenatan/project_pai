export default function Header({ theme, onToggle }) {
  return (
    <header className="site-header">
      <div className="header-inner">
        <div className="site-logo">How AI Is Reshaping PM Hiring</div>
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
