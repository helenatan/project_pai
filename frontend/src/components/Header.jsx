function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}

export default function Header({ today, dayN }) {
  return (
    <header className="masthead">
      <div className="masthead-top">
        <span className="issue-meta">
          Vol. 1 &nbsp;·&nbsp; Day {dayN ?? '—'} &nbsp;·&nbsp; {fmtDate(today?.snapshot_date)}
        </span>
        <span className="issue-meta">United States &nbsp;·&nbsp; Updated daily at 6 am PT</span>
      </div>
      <h1 className="publication-name">The PM Adaptation Index</h1>
      <p className="publication-sub">
        An empirical observatory tracking how AI is reshaping the product management profession
      </p>
      <hr className="masthead-rule" />
      <div className="masthead-bottom">
        <div className="narrative-badge">
          <span className="dot" />
          Day {dayN ?? '—'} of continuous tracking
        </div>
        <span className="issue-meta">Data quality: {today?.data_quality_status || 'unknown'}</span>
      </div>
    </header>
  )
}
