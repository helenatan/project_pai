import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

export default function VolumeChart({ snapshots }) {
  if (!snapshots?.length) return null

  const first = new Date(snapshots[0].snapshot_date)
  const data = snapshots.map((s) => {
    const dayN = Math.floor((new Date(s.snapshot_date) - first) / 86_400_000) + 1
    return {
      dayLabel: `Day ${dayN}`,
      'Active openings': s.total_postings,
      '7-day rolling average': s.total_postings_7day_avg != null
        ? Math.round(s.total_postings_7day_avg)
        : null,
    }
  })

  const enoughData = snapshots.length >= 2

  return (
    <section>
      <div className="section-header">
        <span className="section-title">I. PM Hiring Volume</span>
        <span className="section-meta">Active US postings · Daily</span>
      </div>
      {enoughData ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1a4a7a" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#1a4a7a" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="dayLabel" tick={{ fontSize: 10, fill: '#6b6560' }} stroke="#d8d2c8" />
              <YAxis tick={{ fontSize: 10, fill: '#6b6560' }} stroke="#d8d2c8" width={56} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area
                type="monotone" dataKey="Active openings"
                stroke="#1a4a7a" fill="url(#volumeFill)" strokeWidth={2.2}
                dot={{ r: 2.5, fill: '#1a4a7a' }}
              />
              <Line
                type="monotone" dataKey="7-day rolling average"
                stroke="#1a4a7a" strokeOpacity={0.45} strokeDasharray="4 3"
                strokeWidth={1.5} dot={false} connectNulls
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="baseline-stub">
          <div className="stub-track"><div className="stub-dot" /></div>
          <div className="stub-label">
            <strong>Trend accumulates from tomorrow</strong>
            The daily volume trend and 7-day rolling average appear once more than one day of
            data has accumulated.
          </div>
        </div>
      )}
    </section>
  )
}
