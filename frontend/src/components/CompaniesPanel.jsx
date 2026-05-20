const COMPANY_NAMES = {
  openai: 'OpenAI',
  mongodb: 'MongoDB',
  xai: 'xAI',
  deepmind: 'DeepMind',
  'google deepmind': 'Google DeepMind',
  github: 'GitHub',
  youcom: 'You.com',
  'you.com': 'You.com',
  zoominfo: 'ZoomInfo',
  coreweave: 'CoreWeave',
  elevenlabs: 'ElevenLabs',
  llamaindex: 'LlamaIndex',
  langchain: 'LangChain',
  thinkingmachines: 'Thinking Machines',
  blackforestlabs: 'Black Forest Labs',
}
const NAME_ACRONYMS = new Set(['ai', 'ml', 'hr', 'api'])

function formatCompany(name) {
  if (!name) return ''
  const key = name.toLowerCase().trim()
  if (COMPANY_NAMES[key]) return COMPANY_NAMES[key]
  return key
    .split(' ')
    .map((w) => (NAME_ACRONYMS.has(w) ? w.toUpperCase() : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(' ')
}

export default function CompaniesPanel({ snapshot }) {
  const data = snapshot?.top_employers_ai_skills
  if (!data?.companies?.length) return null

  // Support new schema (total_count + ai_count) and old schema (count only)
  const companies = data.companies.map((co) => ({
    ...co,
    totalCount: co.total_count ?? co.count,
    aiCount:    co.ai_count    ?? co.count,
    aiPct:      co.ai_pct      ?? 100,
  }))

  const maxTotal = Math.max(...companies.map((c) => c.totalCount))
  const hasTotal = data.companies[0]?.total_count != null

  return (
    <section className="count-bar-section">
      <div className="section-header">
        <span className="section-title">IV. Top Companies Hiring PMs</span>
        <span className="section-meta">
          Window ending {data.window_end} · ranked by total PM openings
        </span>
      </div>
      <div className="co-list">
        <div className="panel-subtitle">
          {hasTotal
            ? 'Total PM openings (7-day) · amber = AI-requiring · % shown is AI share'
            : 'PM postings mentioning AI skills · 7-day window'}
        </div>
        {companies.map((co) => {
          const totalBarPct = maxTotal > 0 ? (co.totalCount / maxTotal) * 100 : 0
          const aiBarPct    = maxTotal > 0 ? (co.aiCount    / maxTotal) * 100 : 0

          return (
            <div className="co-row" key={co.company}>
              <span className="co-rank">{co.rank}</span>
              <div className="co-bar-area">
                <span className="co-name">{formatCompany(co.company)}</span>
                <div className="bar-track" style={{ position: 'relative', overflow: 'hidden' }}>
                  {/* total PM bar (muted blue) */}
                  <div className="bar-fill blue-faint" style={{ width: `${totalBarPct}%`, position: 'absolute', left: 0, top: 0, height: '100%' }} />
                  {/* AI-requiring portion (amber, drawn on top) */}
                  <div className="bar-fill amber" style={{ width: `${aiBarPct}%`, position: 'absolute', left: 0, top: 0, height: '100%' }} />
                </div>
              </div>
              <div className="co-count-col">
                {hasTotal ? (
                  <>
                    <div className="count-number" style={{ color: 'var(--signal-amber)' }}>{co.aiCount}</div>
                    <div className="count-label">of {co.totalCount}</div>
                    <div className="count-pct">{co.aiPct}%</div>
                  </>
                ) : (
                  <>
                    <div className="count-number" style={{ color: 'var(--signal-blue)' }}>{co.aiCount}</div>
                    <div className="count-label">jobs</div>
                  </>
                )}
              </div>
            </div>
          )
        })}
        {hasTotal && (
          <div className="co-legend">
            <span><span className="legend-swatch amber-swatch" />AI-requiring</span>
            <span><span className="legend-swatch blue-faint-swatch" />Other PM roles</span>
          </div>
        )}
      </div>
    </section>
  )
}
