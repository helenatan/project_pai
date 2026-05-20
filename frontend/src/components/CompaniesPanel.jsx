const DIRECTION = {
  up:   { label: '▲ up',   cls: 'dir-rising' },
  down: { label: '▼ down', cls: 'dir-falling' },
  flat: { label: '■ flat', cls: 'dir-flat' },
  new:  { label: '★ new',  cls: 'dir-new' },
}

// Known brands whose casing a plain title-case would mangle.
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

  const top = data.companies[0].count || 1

  return (
    <section className="count-bar-section">
      <div className="section-header">
        <span className="section-title">IV. Top Companies Hiring AI PMs</span>
        <span className="section-meta">Window ending {data.window_end} · By JD keyword</span>
      </div>
      <div className="co-list">
        <div className="panel-subtitle">PM postings mentioning AI skills · 7-day window</div>
        {data.companies.map((co) => {
          const dir = DIRECTION[co.direction] || DIRECTION.flat
          return (
            <div className="co-row" key={co.company}>
              <span className="co-rank">{co.rank}</span>
              <div className="co-bar-area">
                <span className="co-name">{formatCompany(co.company)}</span>
                <div className="bar-track">
                  <div className="bar-fill blue" style={{ width: `${(co.count / top) * 100}%` }} />
                </div>
              </div>
              <div className="co-count-col">
                <div className="count-number" style={{ color: 'var(--signal-blue)' }}>{co.count}</div>
                <div className="count-label">jobs</div>
                <div className={`dir-badge ${dir.cls}`}>{dir.label}</div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
