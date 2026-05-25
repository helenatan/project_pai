import { Fragment, useEffect, useState } from 'react'

const COMPANY_NAMES = {
  openai: 'OpenAI', mongodb: 'MongoDB', xai: 'xAI', deepmind: 'DeepMind',
  'google deepmind': 'Google DeepMind', github: 'GitHub', youcom: 'You.com',
  'you.com': 'You.com', zoominfo: 'ZoomInfo', coreweave: 'CoreWeave',
  elevenlabs: 'ElevenLabs', llamaindex: 'LlamaIndex', langchain: 'LangChain',
  thinkingmachines: 'Thinking Machines', blackforestlabs: 'Black Forest Labs',
  doordash: 'DoorDash', mastec: 'MasTec', mclane: 'McLane Company',
  'mclane company': 'McLane Company', aldi: 'ALDI',
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

function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function PostingsDrawer({ company, onClose }) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [onClose])

  const postings = company?.postings || []
  const extra = (company?.total_count || 0) - postings.length

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div>
            <div className="drawer-eyebrow">Active PM openings</div>
            <h3 className="drawer-title">{formatCompany(company.company)}</h3>
            <div className="drawer-sub">
              {company.total_count} open · {company.ai_count} require AI ({company.ai_rate}%)
            </div>
          </div>
          <button className="drawer-close" onClick={onClose} aria-label="Close">×</button>
        </div>
        <ul className="drawer-list">
          {postings.map((p, i) => {
            const titleText = p.title || '—'
            const titleEl = p.url ? (
              <a className="drawer-item-link" href={p.url} target="_blank" rel="noopener noreferrer">
                {titleText}
                <span className="drawer-item-arrow" aria-hidden>↗</span>
              </a>
            ) : (
              <span>{titleText}</span>
            )
            return (
              <li key={i} className="drawer-item">
                <div className="drawer-item-title">
                  {titleEl}
                  {p.has_ai && <span className="drawer-ai-tag" title="Requires AI skills">AI</span>}
                </div>
                <div className="drawer-item-meta">
                  {[p.location, p.source ? `via ${p.source}` : null, fmtDate(p.posted_date)]
                    .filter(Boolean).join(' · ')}
                </div>
              </li>
            )
          })}
          {!postings.length && (
            <li className="drawer-item drawer-empty">No posting details available.</li>
          )}
        </ul>
        {extra > 0 && (
          <p className="drawer-foot">
            Showing {postings.length} of {company.total_count} openings. Older roles in the
            same active window are not displayed.
          </p>
        )}
      </div>
    </div>
  )
}

export default function CompaniesPanel({ snapshot }) {
  const data = snapshot?.top_employers_ai_skills
  const [open, setOpen] = useState(null)
  if (!data?.companies?.length) return null

  const companies = data.companies.map((co) => ({
    ...co,
    totalCount: co.total_count ?? co.count ?? 0,
    aiCount: co.ai_count ?? 0,
    aiRate: co.ai_rate ?? 0,
  }))
  const maxTotal = Math.max(...companies.map((c) => c.totalCount), 1)

  return (
    <section className="count-bar-section">
      <div className="section-rule">
        <span className="section-title">Where PMs Are Hiring</span>
        <span className="section-meta">
          Ranked by active PM openings · click a row for details · snapshot as of {data.window_end}
        </span>
      </div>

      <div className="co-table-combined">
        <span />
        <span />
        <span className="co-th total">Total</span>
        <span className="co-th ai">Require AI</span>
        <span className="co-th rate">% AI</span>
        <div className="co-table-rule" />
        {companies.map((co) => {
          const w = (co.totalCount / maxTotal) * 100
          const wAiInside = co.totalCount > 0 ? (co.aiCount / co.totalCount) * w : 0
          const aiPct = Math.round(co.aiRate)
          return (
            <Fragment key={co.company}>
              <span className="co-rank">{co.rank}</span>
              <div
                className="co-main co-main-clickable"
                onClick={() => setOpen(co)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setOpen(co) }}
              >
                <div className="co-name-row">
                  <span className="co-name">{formatCompany(co.company)}</span>
                </div>
                <div className="co-bar-track">
                  <div className="co-bar-total-fill" style={{ width: `${w}%` }} />
                  <div className="co-bar-ai-fill"    style={{ width: `${wAiInside}%` }} />
                </div>
              </div>
              <span className="co-num">{co.totalCount.toLocaleString()}</span>
              <span className="co-num co-num-ai">{co.aiCount.toLocaleString()}</span>
              <span className="co-num co-num-rate">{aiPct}%</span>
            </Fragment>
          )
        })}
      </div>

      {open && <PostingsDrawer company={open} onClose={() => setOpen(null)} />}
    </section>
  )
}
