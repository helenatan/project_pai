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
  doordash: 'DoorDash',
  mastec: 'MasTec',
  mclane: 'McLane Company',
  'mclane company': 'McLane Company',
  aldi: 'ALDI',
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

export default function AICompaniesPanel({ snapshot }) {
  const tas = snapshot?.top_ai_skills
  const employers = tas?.top_ai_employers
  const windowEnd = tas?.top_ai_employers_window_end
  if (!employers?.length) return null

  const maxCount = Math.max(...employers.map((c) => c.count), 1)

  return (
    <section className="count-bar-section">
      <div className="section-header">
        <span className="section-title">IV. Top Companies Hiring AI PMs</span>
        <span className="section-meta">
          Active AI PM openings, all sources{windowEnd ? ` · week ending ${windowEnd}` : ''}
        </span>
      </div>

      <div className="co-table co-table-simple">
        <span />
        <span className="co-th ai">AI PM postings</span>
        <div className="co-table-rule" />
        {employers.map((co) => {
          const w = (co.count / maxCount) * 100
          return (
            <Fragment key={co.company}>
              <span className="co-rank">{co.rank}</span>
              <div className="co-main">
                <div className="co-name-row">
                  <span className="co-name">{formatCompany(co.company)}</span>
                  <span className="co-total-num">{co.count.toLocaleString()}</span>
                </div>
                <div className="co-bar-track">
                  <div className="co-bar-ai" style={{ width: `${w}%` }} />
                </div>
              </div>
            </Fragment>
          )
        })}
      </div>
    </section>
  )
}
