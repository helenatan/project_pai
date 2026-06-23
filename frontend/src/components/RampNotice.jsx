function fmtNum(n) {
  return n != null ? n.toLocaleString() : '—'
}

export default function RampNotice({ snapshot }) {
  if (!snapshot) return null

  const total = snapshot.total_postings
  const tas = snapshot.top_ai_skills || {}
  const aiTotal = tas.active_ai_total
  const aiRate = tas.active_ai_rate ?? snapshot.ai_penetration_rate

  return (
    <div className="ramp-notice">
      <span className="ramp-icon">Notes</span>
      <div className="ramp-text">
        <p>
          <strong>Today.</strong>{' '}
          {total != null && (
            <>{fmtNum(total)} distinct US <strong>Product Manager</strong> openings seen in our
            trailing tracking window — job-feed postings from the last 45 days plus curated company
            boards re-confirmed within 7. This measures recent posting volume, not a verified
            count of roles live right now.</>
          )}
          {aiTotal != null && aiRate != null && (
            <> Of those, <strong>{fmtNum(aiTotal)} ({Math.round(Number(aiRate))}%)</strong> explicitly require AI skills.</>
          )}
        </p>
        <p className="ramp-pointer">
          For how these numbers are computed and what they don't capture, see{' '}
          <a href="#methodology" className="ramp-link">Methodology &amp; Limitations</a>{' '}
          at the bottom of the page.
        </p>
      </div>
    </div>
  )
}
