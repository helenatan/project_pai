import {
  AreaChart, Area, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

export default function VolumeChart({ snapshots }) {
  if (!snapshots?.length) return null

  const first = new Date(snapshots[0].snapshot_date)
  const chartData = snapshots.map((s) => {
    const dayN = Math.floor((new Date(s.snapshot_date) - first) / 86_400_000) + 1
    return {
      dayLabel: `Day ${dayN}`,
      total_postings: s.total_postings,
      total_postings_7day_avg: s.total_postings_7day_avg != null
        ? parseFloat(parseFloat(s.total_postings_7day_avg).toFixed(0))
        : null,
    }
  })

  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#1a2a3a', marginBottom: '0.75rem' }}>
        PM Job Volume Trend
      </h2>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="volumeFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#1a4a7a" stopOpacity={0.15} />
              <stop offset="95%" stopColor="#1a4a7a" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="dayLabel" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <Tooltip />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Area
            type="monotone"
            dataKey="total_postings_7day_avg"
            stroke="#1a4a7a"
            fill="url(#volumeFill)"
            strokeWidth={2.2}
            name="7-day rolling average"
            dot={false}
          />
          <Line
            type="monotone"
            dataKey="total_postings"
            stroke="#1a4a7a"
            strokeOpacity={0.2}
            strokeDasharray="4 3"
            strokeWidth={1}
            dot={false}
            name="Daily count"
          />
        </AreaChart>
      </ResponsiveContainer>
    </section>
  )
}
