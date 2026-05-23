// Minimum days of data before we show day-over-day deltas. Below this we
// don't have a real prior period; comparing to a 1-2 day "average" is noise.
const MIN_DAYS_FOR_DELTA = 14

function fmtNum(n) {
  return n != null ? n.toLocaleString() : '—'
}

function fmtPct(n) {
  return n != null ? `${Math.round(Number(n))}%` : '—'
}

function delta(current, avg, daysOfData) {
  if (daysOfData != null && daysOfData < MIN_DAYS_FOR_DELTA) {
    return { text: 'No prior period yet', cls: 'muted' }
  }
  if (current == null || avg == null || avg === 0) {
    return { text: '— no prior period', cls: '' }
  }
  const diff = current - avg
  const pct = ((diff / avg) * 100).toFixed(1)
  const sign = diff >= 0 ? '+' : ''
  return { text: `${sign}${pct}% vs 7-day avg`, cls: diff >= 0 ? 'up' : 'down' }
}

export default function HeroMetrics({ snapshot, daysOfData }) {
  if (!snapshot) return null

  const aiRate = snapshot.ai_penetration_rate ?? snapshot.top_ai_skills?.active_ai_rate
  const aiCount = snapshot.top_ai_skills?.active_ai_total
  const totalActive = snapshot.total_postings

  const d1 = delta(snapshot.total_postings, snapshot.total_postings_7day_avg, daysOfData)
  const d2 = delta(aiRate, snapshot.ai_penetration_7day_avg, daysOfData)

  return (
    <section className="hero-metrics hero-metrics-2">
      <div className="metric-cell">
        <div className="metric-label">Active PM openings (US)</div>
        <div className="metric-value">{fmtNum(totalActive)}</div>
        <div className={`metric-delta ${d1.cls}`}>{d1.text}</div>
      </div>
      <div className="metric-cell">
        <div className="metric-label">% Requiring AI Skills</div>
        <div className="metric-value ai-rate">{fmtPct(aiRate)}</div>
        <div className={`metric-delta ${d2.cls}`}>
          {aiCount != null && totalActive != null
            ? `${fmtNum(aiCount)} of ${fmtNum(totalActive)} openings`
            : d2.text}
        </div>
      </div>
    </section>
  )
}
