// AI Skills by Domain — the 7 tracked categories from the ai_keywords taxonomy.
// Counts and quotes come live from snapshot.top_ai_skills.domains, computed
// over active US PM postings that require AI (see pipeline/scripts/aggregate.py).
const DOMAINS = [
  {
    slug: 'model_fluency',
    name: 'Model Fluency',
    def: "The ability to reason about what AI models can and can't do — the conceptual foundation every AI PM needs before building anything",
  },
  {
    slug: 'ai_building',
    name: 'AI Building Blocks',
    def: 'The ability to understand and spec the technical components that power AI features — from prompts and RAG to embeddings and fine-tuning',
  },
  {
    slug: 'agentic_systems',
    name: 'Agentic Systems',
    def: 'The ability to design products where AI takes multi-step actions autonomously — the defining shift from assistive tools to autonomous product experiences',
  },
  {
    slug: 'evals',
    name: 'Evals & Quality',
    def: 'The ability to define what "good" looks like for an AI feature and build the systems to measure it — increasingly the core PM accountability in AI products',
  },
  {
    slug: 'ai_safety',
    name: 'AI Safety',
    def: 'The ability to identify risks in AI behavior and ship products that are trustworthy, fair, and compliant — a fast-growing PM specialty at AI-first companies',
  },
  {
    slug: 'ai_deployment',
    name: 'AI Deployment',
    def: 'The ability to own AI systems in production — understanding reliability, latency, cost, and what it takes to keep an AI product healthy at scale',
  },
  {
    slug: 'ai_product_vision',
    name: 'AI Product Vision',
    def: 'The ability to set a long-term AI direction for a product — translating model capabilities into a coherent strategy, roadmap, and competitive positioning',
  },
]

function DomainCard({ domain, domainData, wide }) {
  const count = domainData?.count ?? 0
  const quote = domainData?.quote || null
  const company = domainData?.company || null
  const hasSignal = count > 0

  return (
    <div className={`domain-card${wide ? ' domain-card-wide' : ''}`}>
      <div className="domain-header">
        <h3 className="domain-name">{domain.name}</h3>
        {hasSignal && (
          <div className="domain-count-block">
            <div className="domain-count-num">{count.toLocaleString()}</div>
            <div className="domain-count-label">postings</div>
          </div>
        )}
      </div>

      <p className="domain-def">{domain.def}</p>

      {hasSignal && quote && (
        <>
          <hr className="domain-rule" />
          <div className="domain-quotebox">
            <p className="domain-quote">&ldquo;{quote}&rdquo;</p>
            {company && <p className="domain-quote-cite">— {company}</p>}
          </div>
        </>
      )}

      {!hasSignal && (
        <>
          <hr className="domain-rule" />
          <span className="nodata-label">No signal yet · tracking early mentions</span>
        </>
      )}
    </div>
  )
}

export default function SkillsPanel({ snapshot }) {
  const tas = snapshot?.top_ai_skills || {}
  const domains = tas.domains || []
  const dataMap = Object.fromEntries(domains.map((d) => [d.slug, d]))
  const activeAiTotal = tas.active_ai_total ?? null
  const withSignal = domains.filter((d) => (d.count || 0) > 0).length

  // Rank cards by posting count — most in-demand domains first.
  // Stable sort keeps the declared DOMAINS order for ties (incl. zero-signal).
  const orderedDomains = [...DOMAINS].sort(
    (a, b) => (dataMap[b.slug]?.count ?? 0) - (dataMap[a.slug]?.count ?? 0)
  )

  return (
    <section>
      <div className="section-header">
        <span className="section-title">III. AI Skills by Domain</span>
        <span className="section-meta">7 categories · ranked by demand</span>
      </div>
      <p className="domain-intro">
        How often each AI competency appears across
        {activeAiTotal != null ? ` ${activeAiTotal.toLocaleString()} ` : ' '}
        active US PM postings that require AI skills. A posting can span several
        domains, so counts overlap and aren&rsquo;t expected to sum.
        {withSignal > 0 && withSignal < 7
          ? ` ${withSignal} of 7 categories show signal so far; the rest are tracked as more data accumulates.`
          : ''}
      </p>
      <div className="domain-grid">
        {orderedDomains.map((d, i) => (
          <DomainCard
            key={d.slug}
            domain={d}
            domainData={dataMap[d.slug]}
            wide={i === orderedDomains.length - 1}
          />
        ))}
      </div>
    </section>
  )
}
