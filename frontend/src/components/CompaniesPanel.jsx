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

export default function CompaniesPanel({ snapshot }) {
  const data = snapshot?.top_employers_ai_skills
  if (!data?.companies?.length) return null

  const companies = data.companies.map((co) => ({
    ...co,
    totalCount: co.total_count ?? co.count ?? 0,
  }))
  const maxTotal = Math.max(...companies.map((c) => c.totalCount), 1)

  return (
    <section className="count-bar-section">
      <div className="section-header">
        <span className="section-title">II. Top Companies Hiring PMs</span>
        <span className="section-meta">
          Active PM openings, all sources · week ending {data.window_end}
        </span>
      </div>

      <div className="co-table co-table-simple">
        <span />
        <span className="co-th total">Total PM openings</span>
        <div className="co-table-rule" />
        {companies.map((co) => {
          const w = (co.totalCount / maxTotal) * 100
          return (
            <Fragment key={co.company}>
              <span className="co-rank">{co.rank}</span>
              <div className="co-main">
                <div className="co-name-row">
                  <span className="co-name">{formatCompany(co.company)}</span>
                  <span className="co-total-num">{co.totalCount.toLocaleString()}</span>
                </div>
                <div className="co-bar-track">
                  <div className="co-bar-total" style={{ width: `${w}%` }} />
                </div>
              </div>
            </Fragment>
          )
        })}
      </div>
    </section>
  )
}
