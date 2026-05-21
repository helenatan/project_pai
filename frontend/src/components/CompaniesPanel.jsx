import { Fragment } from 'react'

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

  const hasTotal = data.companies[0]?.total_count != null
  const companies = data.companies.map((co) => ({
    ...co,
    totalCount: co.total_count ?? co.count,
    aiCount:    co.ai_count    ?? co.count,
    aiPct:      co.ai_pct,
  }))
  const maxTotal = Math.max(...companies.map((c) => c.totalCount))

  return (
    <section className="count-bar-section">
      <div className="section-header">
        <span className="section-title">IV. Top Companies Hiring PMs</span>
        <span className="section-meta">
          Window ending {data.window_end} · ranked by total PM openings
        </span>
      </div>

      {hasTotal ? (
        <>
          <div className="co-table">
            <span />
            <span className="co-th">Total PM openings</span>
            <span className="co-th ai">Require AI</span>
            <span className="co-th ai">% of total</span>
            <div className="co-table-rule" />
            {companies.map((co) => {
              const totalW = maxTotal > 0 ? (co.totalCount / maxTotal) * 100 : 0
              const aiW    = maxTotal > 0 ? (co.aiCount / maxTotal) * 100 : 0
              return (
                <Fragment key={co.company}>
                  <span className="co-rank">{co.rank}</span>
                  <div className="co-main">
                    <div className="co-name-row">
                      <span className="co-name">{formatCompany(co.company)}</span>
                      <span className="co-total-num">{co.totalCount}</span>
                    </div>
                    <div className="co-bar-track">
                      <div className="co-bar-total" style={{ width: `${totalW}%` }} />
                      <div className="co-bar-ai" style={{ width: `${aiW}%` }} />
                    </div>
                  </div>
                  <span className="co-ai-num">{co.aiCount}</span>
                  <span className="co-ai-num">{co.aiPct}%</span>
                </Fragment>
              )
            })}
          </div>
          <div className="co-bar-legend">
            <span><span className="sw" style={{ background: 'var(--signal-amber)' }} />Require AI</span>
            <span><span className="sw" style={{ background: '#c2cedb' }} />Other PM roles</span>
          </div>
        </>
      ) : (
        <div className="co-list">
          <div className="panel-subtitle">
            PM postings mentioning AI skills · 7-day window · total PM openings appear after the next data refresh
          </div>
          {companies.map((co) => {
            const aiW = maxTotal > 0 ? (co.aiCount / maxTotal) * 100 : 0
            return (
              <div className="co-row" key={co.company}>
                <span className="co-rank">{co.rank}</span>
                <div className="co-bar-area">
                  <span className="co-name">{formatCompany(co.company)}</span>
                  <div className="bar-track">
                    <div className="bar-fill amber" style={{ width: `${aiW}%` }} />
                  </div>
                </div>
                <div className="co-count-col">
                  <div className="count-number" style={{ color: 'var(--signal-amber)' }}>{co.aiCount}</div>
                  <div className="count-label">AI jobs</div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
