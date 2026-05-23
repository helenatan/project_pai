import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
function fmtDate(dateStr) {
  const [, m, d] = dateStr.split('-').map(Number)
  return `${MONTHS[m - 1]} ${d}`
}

// Section I: stacked area chart. Total openings is split into two stacks:
//   amber  = openings that require AI skills (active_ai_total)
//   blue   = openings that don't
// They sum visually to total_postings. Reading is intuitive: the height of
// the whole stack is volume; the amber share is the AI demand. One axis,
// no axis-mapping decoding required.
export default function VolumeChart({ snapshots }) {
  if (!snapshots?.length) return null

  const data = snapshots.map((s) => {
    const total = s.total_postings ?? 0
    const aiRate = s.ai_penetration_rate
    const ai = (s.top_ai_skills?.active_ai_total != null)
      ? s.top_ai_skills.active_ai_total
      : (aiRate != null ? Math.round(total * (Number(aiRate) / 100)) : 0)
    return {
      dayLabel: fmtDate(s.snapshot_date),
      'Require AI': ai,
      'Other PM openings': Math.max(0, total - ai),
      _total: total,
      _aiRate: aiRate,
    }
  })

  const enoughData = snapshots.length >= 2
  const opens = data.map((d) => d._total).filter((v) => v != null)
  const ymax = opens.length ? Math.ceil(Math.max(...opens) * 1.15 / 50) * 50 : 'auto'

  return (
    <section>
      <div className="section-header">
        <span className="section-title">I. Hiring Volume &amp; AI Demand Over Time</span>
        <span className="section-meta">Daily · stacked: AI-required (amber) within total active openings</span>
      </div>
      {enoughData ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 8, right: 18, left: 0, bottom: 0 }} stackOffset="none">
              <defs>
                <linearGradient id="aiFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor="#a06010" stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#a06010" stopOpacity={0.7} />
                </linearGradient>
                <linearGradient id="otherFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor="#1a4a7a" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#1a4a7a" stopOpacity={0.15} />
                </linearGradient>
              </defs>
              <XAxis dataKey="dayLabel" tick={{ fontSize: 10, fill: '#6b6560' }} stroke="#d8d2c8" />
              <YAxis
                tick={{ fontSize: 10, fill: '#6b6560' }}
                stroke="#d8d2c8"
                width={50}
                domain={[0, ymax]}
              />
              <Tooltip
                formatter={(v, name) => [v, name]}
                labelFormatter={(label, payload) => {
                  if (!payload || !payload.length) return label
                  const d = payload[0]?.payload
                  const rate = d?._aiRate != null ? `${Math.round(Number(d._aiRate))}% require AI` : null
                  return `${label}${rate ? ` · ${rate}` : ''}`
                }}
              />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Area
                type="monotone"
                dataKey="Require AI"
                stackId="1"
                stroke="#a06010"
                strokeWidth={1.5}
                fill="url(#aiFill)"
              />
              <Area
                type="monotone"
                dataKey="Other PM openings"
                stackId="1"
                stroke="#1a4a7a"
                strokeOpacity={0.5}
                strokeWidth={1.2}
                fill="url(#otherFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="baseline-stub">
          <div className="stub-track"><div className="stub-dot" /></div>
          <div className="stub-label">
            <strong>Baseline established &mdash; trend begins here</strong>
            Today&rsquo;s snapshot: <strong>{snapshots.at(-1)?.total_postings?.toLocaleString()}</strong> active
            US PM openings,
            with <strong>{Math.round(Number(snapshots.at(-1)?.ai_penetration_rate ?? 0))}%</strong> requiring
            AI skills. The daily trend appears once we&rsquo;ve accumulated more than one day.
          </div>
        </div>
      )}
    </section>
  )
}
