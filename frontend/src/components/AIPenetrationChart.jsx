import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

export default function AIPenetrationChart({ snapshots }) {
  if (!snapshots?.length) return null

  const first = new Date(snapshots[0].snapshot_date)
  const data = snapshots.map((s) => {
    const dayN = Math.floor((new Date(s.snapshot_date) - first) / 86_400_000) + 1
    return {
      dayLabel: `Day ${dayN}`,
      'AI requirement rate': s.ai_penetration_rate != null
        ? parseFloat(parseFloat(s.ai_penetration_rate).toFixed(1))
        : null,
      '7-day rolling average': s.ai_penetration_7day_avg != null
        ? parseFloat(parseFloat(s.ai_penetration_7day_avg).toFixed(1))
        : null,
    }
  })

  const enoughData = snapshots.filter((s) => s.ai_penetration_rate != null).length >= 2

  return (
    <section>
      <div className="section-header">
        <span className="section-title">II. AI Requirement Rate</span>
        <span className="section-meta">% of PM postings mentioning AI · Daily</span>
      </div>
      {enoughData ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <XAxis dataKey="dayLabel" tick={{ fontSize: 10, fill: '#6b6560' }} stroke="#d8d2c8" />
              <YAxis
                tickFormatter={(v) => `${v}%`} domain={[0, 100]}
                tick={{ fontSize: 10, fill: '#6b6560' }} stroke="#d8d2c8" width={44}
              />
              <Tooltip formatter={(v) => `${parseFloat(v).toFixed(1)}%`} />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line
                type="monotone" dataKey="AI requirement rate"
                stroke="#a06010" strokeWidth={2.2} dot={{ r: 2.5, fill: '#a06010' }}
              />
              <Line
                type="monotone" dataKey="7-day rolling average"
                stroke="#a06010" strokeOpacity={0.45} strokeDasharray="4 3"
                strokeWidth={1.5} dot={false} connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="baseline-stub">
          <div className="stub-track"><div className="stub-dot amber" style={{ bottom: '42%' }} /></div>
          <div className="stub-label">
            <strong>Trend accumulates from tomorrow</strong>
            The AI requirement rate trend appears once more than one day of signal has accumulated.
          </div>
        </div>
      )}
    </section>
  )
}
