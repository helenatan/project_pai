function fmtNum(n) {
  return n != null ? n.toLocaleString() : '—'
}

function delta(current, avg) {
  if (current == null || avg == null || avg === 0) {
    return { text: '— no prior period', cls: '' }
  }
  const diff = current - avg
  const pct = ((diff / avg) * 100).toFixed(1)
  const sign = diff >= 0 ? '+' : ''
  return { text: `${sign}${pct}% vs 7-day avg`, cls: diff >= 0 ? 'up' : 'down' }
}

export default function HeroMetrics({ snapshot }) {
  if (!snapshot) return null

  const aiRate = snapshot.ai_penetration_rate != null
    ? parseFloat(parseFloat(snapshot.ai_penetration_rate).toFixed(1))
    : null

  const d1 = delta(snapshot.total_postings, snapshot.total_postings_7day_avg)
  const d2 = delta(snapshot.new_postings_today, snapshot.new_postings_7day_avg)
  const d3 = delta(aiRate, snapshot.ai_penetration_7day_avg)

  return (
    <section className="hero-metrics">
      <div className="metric-cell">
        <div className="metric-label">Active PM openings (US)</div>
        <div className="metric-value">{fmtNum(snapshot.total_postings)}</div>
        <div className={`metric-delta ${d1.cls}`}>{d1.text}</div>
      </div>
      <div className="metric-cell">
        <div className="metric-label">New PM jobs posted today</div>
        <div className="metric-value">{fmtNum(snapshot.new_postings_today)}</div>
        <div className={`metric-delta ${d2.cls}`}>{d2.text}</div>
      </div>
      <div className="metric-cell">
        <div className="metric-label">AI skill requirement rate</div>
        <div className="metric-value ai-rate">{aiRate != null ? `${aiRate}%` : '—'}</div>
        <div className={`metric-delta ${d3.cls}`}>{d3.text}</div>
      </div>
    </section>
  )
}
