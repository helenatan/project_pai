function Delta({ current, avg, unit = '' }) {
  if (current == null || avg == null) return null
  const diff = current - avg
  const pct = avg !== 0 ? ((diff / avg) * 100).toFixed(1) : null
  const sign = diff >= 0 ? '+' : ''
  const color = diff >= 0 ? '#1a7a4a' : '#c0392b'
  return (
    <span style={{ fontSize: '0.8rem', color, marginLeft: '0.5rem' }}>
      {sign}{pct}% vs 7-day avg
    </span>
  )
}

function MetricCard({ label, value, unit, avg }) {
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #d0dce8',
      borderRadius: 8,
      padding: '1.25rem 1.5rem',
      flex: 1,
      minWidth: 200,
    }}>
      <div style={{ fontSize: '0.75rem', color: '#6080a0', fontWeight: 600, marginBottom: '0.4rem' }}>
        {label}
      </div>
      <div style={{ fontSize: '2rem', fontWeight: 700, color: '#1a2a3a', lineHeight: 1.1 }}>
        {value != null ? `${value.toLocaleString()}${unit}` : '—'}
      </div>
      <Delta current={value} avg={avg} />
    </div>
  )
}

export default function HeroMetrics({ snapshot }) {
  return (
    <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '2rem' }}>
      <MetricCard
        label="ACTIVE PM OPENINGS (US)"
        value={snapshot?.total_postings}
        unit=""
        avg={snapshot?.total_postings_7day_avg}
      />
      <MetricCard
        label="NEW PM JOBS TODAY"
        value={snapshot?.new_postings_today}
        unit=""
        avg={snapshot?.new_postings_7day_avg}
      />
      <MetricCard
        label="AI SKILL REQUIREMENT RATE"
        value={snapshot?.ai_penetration_rate != null
          ? parseFloat(snapshot.ai_penetration_rate.toFixed(1))
          : null}
        unit="%"
        avg={snapshot?.ai_penetration_7day_avg}
      />
    </div>
  )
}
