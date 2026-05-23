function fmtNum(n) {
  return n != null ? n.toLocaleString() : '—'
}

// Editorial commentary block at the top of the dashboard.
// Holds the "Today" headline and a pointer to the Methodology & Limitations
// section in the footer. Reuses the .ramp-notice styling for visual continuity.
export default function RampNotice({ snapshot }) {
  if (!snapshot) return null

  const total = snapshot.total_postings
  const tas = snapshot.top_ai_skills || {}
  const aiTotal = tas.active_ai_total
  const aiRate = tas.active_ai_rate ?? snapshot.ai_penetration_rate

  return (
    <div className="ramp-notice">
      <span className="ramp-icon">NOTES</span>
      <div className="ramp-text">
        <p>
          <strong>Today.</strong>{' '}
          {total != null ? (
            <>
              {fmtNum(total)} active US <strong>Product Manager</strong> openings indexed across
              the job feeds and curated company boards we currently track.
            </>
          ) : null}
          {aiTotal != null && aiRate != null ? (
            <> Of those, <strong>{fmtNum(aiTotal)} ({Math.round(Number(aiRate))}%)</strong> explicitly require AI skills.</>
          ) : null}
        </p>
        <p className="ramp-pointer">
          For how these numbers are computed, the sources behind them, and what they don&rsquo;t
          capture, see{' '}
          <a href="#methodology" className="ramp-link">Methodology &amp; Limitations</a>{' '}
          at the bottom of the page.
        </p>
      </div>
    </div>
  )
}
