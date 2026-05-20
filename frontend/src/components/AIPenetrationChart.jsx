import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
function fmtDate(dateStr) {
  const [, m, d] = dateStr.split('-').map(Number)
  return `${MONTHS[m - 1]} ${d}`
}

function AITooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null
  const ratePt       = payload.find((p) => p.dataKey === 'AI requirement rate')
  const avgPt        = payload.find((p) => p.dataKey === '7-day rolling average')
  const rate         = ratePt?.value
  const activeTotal  = ratePt?.payload?.totalPostings
  const impliedCount = rate != null && activeTotal != null
    ? Math.round(rate / 100 * activeTotal)
    : null

  return (
    <div style={{
      background: '#fff', border: '1px solid #d8d2c8', borderRadius: 5,
      padding: '0.45rem 0.65rem', fontSize: '0.76rem', lineHeight: 1.65,
      boxShadow: '0 2px 6px rgba(0,0,0,0.08)',
    }}>
      <div style={{ fontWeight: 600, color: '#1a1714', marginBottom: '0.1rem' }}>{label}</div>
      {rate != null && (
        <div style={{ color: '#a06010' }}>
          {parseFloat(rate).toFixed(1)}% AI requirement rate
          {impliedCount != null && (
            <span style={{ color: '#6b6560', marginLeft: '0.35rem' }}>
              (~{impliedCount.toLocaleString()} of {activeTotal.toLocaleString()} active openings)
            </span>
          )}
        </div>
      )}
      {avgPt?.value != null && (
        <div style={{ color: '#a06010', opacity: 0.55 }}>
          7-day avg: {parseFloat(avgPt.value).toFixed(1)}%
        </div>
      )}
    </div>
  )
}

export default function AIPenetrationChart({ snapshots }) {
  if (!snapshots?.length) return null

  const data = snapshots.map((s) => ({
    dayLabel: fmtDate(s.snapshot_date),
    'AI requirement rate': s.ai_penetration_rate != null
      ? parseFloat(parseFloat(s.ai_penetration_rate).toFixed(1))
      : null,
    '7-day rolling average': s.ai_penetration_7day_avg != null
      ? parseFloat(parseFloat(s.ai_penetration_7day_avg).toFixed(1))
      : null,
    totalPostings: s.total_postings ?? null,
  }))

  const enoughData = snapshots.filter((s) => s.ai_penetration_rate != null).length >= 2

  return (
    <section>
      <div className="section-header">
        <span className="section-title">II. AI Requirement Rate</span>
        <span className="section-meta">% of active PM openings estimated to require AI · Daily</span>
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
              <Tooltip content={<AITooltip />} />
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
