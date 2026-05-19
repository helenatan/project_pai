import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'

export default function AIPenetrationChart({ snapshots }) {
  if (!snapshots?.length) return null

  const first = new Date(snapshots[0].snapshot_date)
  const chartData = snapshots.map((s) => {
    const dayN = Math.floor((new Date(s.snapshot_date) - first) / 86_400_000) + 1
    return {
      dayLabel: `Day ${dayN}`,
      ai_penetration_rate: s.ai_penetration_rate != null
        ? parseFloat(parseFloat(s.ai_penetration_rate).toFixed(1))
        : null,
      ai_penetration_7day_avg: s.ai_penetration_7day_avg != null
        ? parseFloat(parseFloat(s.ai_penetration_7day_avg).toFixed(1))
        : null,
    }
  })

  const maxRate = Math.max(...snapshots.map((s) => s.ai_penetration_rate ?? 0))
  const yMax = Math.ceil((maxRate + 10) / 10) * 10

  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#1a2a3a', marginBottom: '0.75rem' }}>
        AI Skill Requirement Rate
      </h2>
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
          <XAxis dataKey="dayLabel" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis
            tickFormatter={(v) => `${v}%`}
            domain={[0, yMax]}
            tick={{ fontSize: 11 }}
            width={48}
          />
          <Tooltip formatter={(v) => `${parseFloat(v).toFixed(1)}%`} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine
            y={40}
            stroke="#a06010"
            strokeDasharray="3 4"
            strokeOpacity={0.3}
          />
          <Line
            type="monotone"
            dataKey="ai_penetration_rate"
            stroke="#a06010"
            strokeWidth={2.2}
            dot={false}
            name="AI requirement rate"
          />
          <Line
            type="monotone"
            dataKey="ai_penetration_7day_avg"
            stroke="#a06010"
            strokeOpacity={0.4}
            strokeDasharray="4 3"
            strokeWidth={1.5}
            dot={false}
            name="7-day avg"
          />
        </LineChart>
      </ResponsiveContainer>
    </section>
  )
}
