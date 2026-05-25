import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
function fmtDate(dateStr) {
  const [, m, d] = dateStr.split('-').map(Number)
  return `${MONTHS[m - 1]} ${d}`
}

function getColors(theme) {
  return theme === 'dark'
    ? { accent: '#E04A14', grid: '#242220', axis: '#5C5850' }
    : { accent: '#C8390A', grid: '#E8E5E0', axis: '#AAAAAA' }
}

function AITooltip({ active, payload, label, theme }) {
  if (!active || !payload?.length) return null
  const isDark = theme === 'dark'
  const ratePt = payload.find((p) => p.dataKey === 'AI requirement rate')
  const avgPt = payload.find((p) => p.dataKey === '7-day avg')
  const rate = ratePt?.value
  const activeTotal = ratePt?.payload?.totalPostings
  const impliedCount = rate != null && activeTotal != null
    ? Math.round(rate / 100 * activeTotal)
    : null

  return (
    <div style={{
      background: isDark ? '#1A1916' : '#fff',
      border: `1px solid ${isDark ? '#2C2A26' : '#D8D5D0'}`,
      borderRadius: 2,
      padding: '0.5rem 0.75rem',
      fontSize: '0.72rem',
      lineHeight: 1.65,
      color: isDark ? '#E8E3D8' : '#1A1A1A',
      fontFamily: "'Libre Franklin', sans-serif",
    }}>
      <div style={{ fontWeight: 700, marginBottom: '0.1rem' }}>{label}</div>
      {rate != null && (
        <div style={{ color: isDark ? '#E04A14' : '#C8390A' }}>
          {parseFloat(rate).toFixed(1)}% AI requirement rate
          {impliedCount != null && (
            <span style={{ color: isDark ? '#5C5850' : '#888', marginLeft: '0.35rem' }}>
              (~{impliedCount.toLocaleString()} of {activeTotal.toLocaleString()})
            </span>
          )}
        </div>
      )}
      {avgPt?.value != null && (
        <div style={{ color: isDark ? '#5C5850' : '#AAAAAA' }}>
          7-day avg: {parseFloat(avgPt.value).toFixed(1)}%
        </div>
      )}
    </div>
  )
}

export default function AIPenetrationChart({ snapshots, theme }) {
  if (!snapshots?.length) return null

  const c = getColors(theme)
  const data = snapshots.map((s) => ({
    dayLabel: fmtDate(s.snapshot_date),
    'AI requirement rate': s.ai_penetration_rate != null
      ? parseFloat(parseFloat(s.ai_penetration_rate).toFixed(1))
      : null,
    '7-day avg': s.ai_penetration_7day_avg != null
      ? parseFloat(parseFloat(s.ai_penetration_7day_avg).toFixed(1))
      : null,
    totalPostings: s.total_postings ?? null,
  }))

  const enoughData = snapshots.filter((s) => s.ai_penetration_rate != null).length >= 2

  return (
    <section className="section-block">
      <div className="section-rule">
        <span className="section-title">AI Requirement Rate</span>
        <span className="section-meta">% of active PM openings estimated to require AI · Daily</span>
      </div>
      {enoughData ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke={c.grid} strokeWidth={1} />
              <XAxis
                dataKey="dayLabel"
                tick={{ fontSize: 10, fill: c.axis, fontFamily: 'Libre Franklin, sans-serif' }}
                axisLine={{ stroke: c.grid }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tickFormatter={(v) => `${v}%`}
                domain={[0, 'auto']}
                tick={{ fontSize: 10, fill: c.axis, fontFamily: 'Libre Franklin, sans-serif' }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip content={<AITooltip theme={theme} />} />
              <Legend
                wrapperStyle={{ fontSize: 11, fontFamily: 'Libre Franklin, sans-serif', color: c.axis }}
              />
              <Line
                type="monotone"
                dataKey="AI requirement rate"
                stroke={c.accent}
                strokeWidth={2}
                dot={{ r: 2, fill: c.accent }}
                activeDot={{ r: 4 }}
              />
              <Line
                type="monotone"
                dataKey="7-day avg"
                stroke={c.accent}
                strokeOpacity={0.4}
                strokeDasharray="4 3"
                strokeWidth={1.5}
                dot={false}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="baseline-stub">
          <div className="stub-track"><div className="stub-dot" /></div>
          <div className="stub-label">
            <strong>Trend accumulates from tomorrow</strong>
            The AI requirement rate trend appears once more than one day of signal has accumulated.
          </div>
        </div>
      )}
    </section>
  )
}
