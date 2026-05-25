import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid,
} from 'recharts'

const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
function fmtDate(dateStr) {
  const [, m, d] = dateStr.split('-').map(Number)
  return `${MONTHS[m - 1]} ${d}`
}

function getColors(theme) {
  return theme === 'dark'
    ? {
        ai: '#E04A14',
        aiSoft: 'rgba(224,74,20,0.85)',
        other: '#5C5850',
        otherFill: 'rgba(140,134,124,0.30)',
        grid: '#242220',
        axis: '#7A746A',
        bg: '#1A1916',
        tooltipBg: '#1A1916',
        tooltipBorder: '#2C2A26',
        tooltipText: '#E8E3D8',
        legend: '#B8AFA3',
      }
    : {
        ai: '#C8390A',
        aiSoft: 'rgba(200,57,10,0.85)',
        other: '#1a4a7a',
        otherFill: 'rgba(26,74,122,0.22)',
        grid: '#E8E5E0',
        axis: '#6B6B6B',
        bg: '#FFFFFF',
        tooltipBg: '#FFFFFF',
        tooltipBorder: '#D8D5D0',
        tooltipText: '#1A1A1A',
        legend: '#4A4A4A',
      }
}

function VolumeTooltip({ active, payload, label, theme }) {
  if (!active || !payload?.length) return null
  const c = getColors(theme)
  const d = payload[0]?.payload
  const rate = d?._aiRate != null ? Math.round(Number(d._aiRate)) : null
  const total = d?._total
  return (
    <div style={{
      background: c.tooltipBg,
      border: `1px solid ${c.tooltipBorder}`,
      borderRadius: 2,
      padding: '0.5rem 0.75rem',
      fontSize: '0.78rem',
      lineHeight: 1.65,
      color: c.tooltipText,
      fontFamily: "'Libre Franklin', sans-serif",
      fontVariantNumeric: 'tabular-nums',
      boxShadow: theme === 'dark' ? '0 4px 12px rgba(0,0,0,0.4)' : '0 4px 12px rgba(0,0,0,0.08)',
    }}>
      <div style={{ fontWeight: 700, marginBottom: '0.2rem' }}>
        {label}{total != null ? ` · ${total.toLocaleString()} total` : ''}
      </div>
      {payload.map((p) => (
        <div key={p.dataKey} style={{ color: p.color }}>
          {p.name}: {p.value != null ? Math.round(p.value).toLocaleString() : '—'}
        </div>
      ))}
      {rate != null && (
        <div style={{ color: c.legend, marginTop: '0.15rem', fontStyle: 'italic' }}>
          {rate}% require AI
        </div>
      )}
    </div>
  )
}

// Stacked area chart: total active PM openings split into AI-required (accent)
// and other (faint neutral). Reading is intuitive — the height of the whole
// stack is volume; the AI share is the accent band on top.
export default function VolumeChart({ snapshots, theme }) {
  if (!snapshots?.length) return null

  const c = getColors(theme)

  const data = snapshots.map((s) => {
    const total = s.total_postings ?? 0
    const aiRate = s.ai_penetration_rate
    const ai = s.top_ai_skills?.active_ai_total != null
      ? s.top_ai_skills.active_ai_total
      : aiRate != null ? Math.round(total * (Number(aiRate) / 100)) : 0
    return {
      dayLabel: fmtDate(s.snapshot_date),
      'Require AI': ai,
      'Other PM openings': Math.max(0, total - ai),
      _total: total,
      _aiRate: aiRate,
    }
  })

  const enoughData = snapshots.length >= 2
  const totals = data.map((d) => d._total).filter((v) => v != null)
  const ymax = totals.length ? Math.ceil(Math.max(...totals) * 1.15 / 50) * 50 : 'auto'

  return (
    <section className="section-block">
      <div className="section-rule">
        <span className="section-title">Hiring Volume &amp; AI Demand</span>
        <span className="section-meta">Daily · stacked: AI-required share within total active openings</span>
      </div>
      {enoughData ? (
        <div className="chart-wrap">
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }} stackOffset="none">
              <defs>
                <linearGradient id="aiStack" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor={c.ai} stopOpacity={0.95} />
                  <stop offset="100%" stopColor={c.ai} stopOpacity={0.75} />
                </linearGradient>
                <linearGradient id="otherStack" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"  stopColor={c.other} stopOpacity={theme === 'dark' ? 0.40 : 0.35} />
                  <stop offset="100%" stopColor={c.other} stopOpacity={theme === 'dark' ? 0.20 : 0.15} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke={c.grid} strokeWidth={1} />
              <XAxis
                dataKey="dayLabel"
                tick={{ fontSize: 11, fill: c.axis, fontFamily: 'Libre Franklin, sans-serif' }}
                axisLine={{ stroke: c.grid }}
                tickLine={false}
                interval="preserveStartEnd"
              />
              <YAxis
                tick={{ fontSize: 11, fill: c.axis, fontFamily: 'Libre Franklin, sans-serif' }}
                axisLine={false}
                tickLine={false}
                width={50}
                domain={[0, ymax]}
                tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toLocaleString()}
              />
              <Tooltip content={<VolumeTooltip theme={theme} />} />
              <Legend
                wrapperStyle={{ fontSize: 12, fontFamily: 'Libre Franklin, sans-serif', color: c.legend, paddingTop: 8 }}
              />
              <Area
                type="monotone"
                dataKey="Other PM openings"
                stackId="1"
                stroke={c.other}
                strokeOpacity={theme === 'dark' ? 0.45 : 0.5}
                strokeWidth={1.2}
                fill="url(#otherStack)"
              />
              <Area
                type="monotone"
                dataKey="Require AI"
                stackId="1"
                stroke={c.ai}
                strokeWidth={1.6}
                fill="url(#aiStack)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="baseline-stub">
          <div className="stub-track"><div className="stub-dot" /></div>
          <div className="stub-label">
            <strong>Baseline established — trend begins here</strong>
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
