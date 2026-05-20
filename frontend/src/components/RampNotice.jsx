const BASELINE_TARGET = 112

export default function RampNotice({ dayN }) {
  if (dayN == null || dayN >= BASELINE_TARGET) return null

  const pct = Math.min(100, Math.max(0.9, (dayN / BASELINE_TARGET) * 100))

  return (
    <div className="ramp-notice">
      <span className="ramp-icon">NOTE</span>
      <div className="ramp-text">
        <strong>Day {dayN} of data collection.</strong> Rolling averages, 7-day trends, and
        directional signals require at least 7 days of data. Signals before Day 14 should be
        interpreted cautiously — early trend comparisons may read as <em>new</em> with no prior
        period to compare against.
        <div className="ramp-progress">
          <div className="ramp-bar-wrap"><div className="ramp-bar" style={{ width: `${pct}%` }} /></div>
          <span className="ramp-bar-label">Day {dayN} of {BASELINE_TARGET} to full baseline</span>
        </div>
      </div>
    </div>
  )
}
