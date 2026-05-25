// Minimum days of snapshot history before we show day-over-day deltas. Below
// this we don't have a real prior period; comparing to a 1-2 day "average"
// is noise and would mislead readers.
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
    return { text: '— no prior period', cls: 'muted' }
  }
  const diff = current - avg
  const pct = ((diff / avg) * 100).toFixed(1)
  const sign = diff >= 0 ? '+' : ''
  return { text: `${sign}${pct}% vs 7-day avg`, cls: diff >= 0 ? 'up' : 'down' }
}

export default function HeroMetrics({ snapshot, daysOfData }) {
  if (!snapshot) return null

  const totalActive = snapshot.total_postings
  const aiRate = snapshot.ai_penetration_rate ?? snapshot.top_ai_skills?.active_ai_rate
  const aiCount = snapshot.top_ai_skills?.active_ai_total

  const d1 = delta(totalActive, snapshot.total_postings_7day_avg, daysOfData)

  const aiSubtitleText = aiCount != null && totalActive != null
    ? `${fmtNum(aiCount)} of ${fmtNum(totalActive)} openings`
    : null

  return (
    <div className="metrics-band">
      <div className="metrics-grid">
        <div className="metric-cell">
          <div className="metric-label">Active PM Openings (US)</div>
          <div className="metric-value">{fmtNum(totalActive)}</div>
          <div className={`metric-delta ${d1.cls}`}>{d1.text}</div>
        </div>
        <div className="metric-cell">
          <div className="metric-label">% Requiring AI Skills</div>
          <div className="metric-value accent">{fmtPct(aiRate)}</div>
          {aiSubtitleText
            ? <div className="metric-delta amber">{aiSubtitleText}</div>
            : <div className="metric-delta muted">No data yet</div>}
        </div>
      </div>
    </div>
  )
}
