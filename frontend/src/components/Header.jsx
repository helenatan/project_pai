function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}

export default function Header({ today }) {
  return (
    <header className="masthead">
      <div className="masthead-top">
        <span className="issue-meta">
          Vol. 1 &nbsp;·&nbsp; {fmtDate(today?.snapshot_date)}
        </span>
        <span className="issue-meta">United States &nbsp;·&nbsp; Updated daily at 6 am PT</span>
      </div>
      <h1 className="publication-name">The PM-AI Hiring Index</h1>
      <p className="publication-sub">
        A daily index tracking where product managers are being hired — and how much of that hiring now demands AI skills
      </p>
    </header>
  )
}
