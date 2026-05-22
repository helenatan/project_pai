// AI Skills by Domain — the 7 tracked categories from the ai_keywords taxonomy.
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

function fmtEst(n) {
  if (n == null) return null
  return `~${Math.round(n).toLocaleString()}`
}

function DomainCard({ domain, domainData, scaleFactor, wide }) {
  const rawCount = domainData?.count ?? 0
  const domainEst = scaleFactor != null && rawCount > 0
    ? fmtEst(rawCount * scaleFactor)
    : rawCount > 0 ? String(rawCount) : null

  const quote = domainData?.quote || null
  const company = domainData?.company || null
  const hasSignal = rawCount > 0

  return (
    <div className={`domain-card${wide ? ' domain-card-wide' : ''}`}>
      <div className="domain-header">
        <h3 className="domain-name">{domain.name}</h3>
        {domainEst != null && (
          <div className="domain-count-block">
            <div className="domain-count-num">{domainEst}</div>
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
  const domainQuotes = snapshot?.top_ai_skills?.domain_quotes || []
  const quotesMap = Object.fromEntries(domainQuotes.map((d) => [d.slug, d]))

  // Fall back to keyword-level signal count if domain_quotes not yet populated
  const skills = snapshot?.top_ai_skills?.skills || []
  const countByKeyword = Object.fromEntries(skills.map((s) => [s.keyword, s.count]))
  const FALLBACK_KWS = DOMAINS.flatMap((d) => {
    // rough fallback: map slug back to a known keyword
    const map = {
      model_fluency: ['llm', 'large language model', 'generative ai', 'machine learning'],
      ai_building: ['prompt engineering', 'rag', 'embeddings'],
      agentic_systems: ['agentic', 'ai agent'],
      evals: ['ai evaluation', 'hallucination'],
      ai_safety: ['ai safety', 'responsible ai'],
      ai_deployment: ['mlops', 'ai platform'],
      ai_product_vision: ['ai strategy', 'ai roadmap'],
    }
    return (map[d.slug] || []).map((kw) => ({ slug: d.slug, kw }))
  })

  const withSignal = domainQuotes.length > 0
    ? domainQuotes.filter((d) => d.count > 0).length
    : DOMAINS.filter((d) =>
        FALLBACK_KWS.filter((x) => x.slug === d.slug).some((x) => (countByKeyword[x.kw] || 0) > 0)
      ).length

  // Scale raw sample counts up to estimated active-market total
  const sampleAiCount = snapshot?.top_ai_skills?.total_ai_postings_today
  const estimatedAiTotal = snapshot?.total_postings != null && snapshot?.ai_penetration_rate != null
    ? Math.round(snapshot.total_postings * snapshot.ai_penetration_rate / 100)
    : null
  const scaleFactor = estimatedAiTotal != null && sampleAiCount > 0
    ? estimatedAiTotal / sampleAiCount
    : null

  // Rank cards by posting count — most in-demand domains first.
  // Stable sort keeps the declared DOMAINS order for ties (incl. zero-signal).
  const orderedDomains = [...DOMAINS].sort(
    (a, b) => (quotesMap[b.slug]?.count ?? 0) - (quotesMap[a.slug]?.count ?? 0)
  )

  return (
    <section>
      <div className="section-header">
        <span className="section-title">III. AI Skills by Domain</span>
        <span className="section-meta">7 tracked categories</span>
      </div>
      <p className="domain-intro">
        PM job descriptions reveal which AI competencies employers actually require.
        {' '}{withSignal} of 7 categories show signal in the latest snapshot
        {estimatedAiTotal != null
          ? ` (~${estimatedAiTotal.toLocaleString()} active openings estimated to mention AI skills)`
          : ''}; the rest are tracked and will build signal as more data accumulates.
      </p>
      <div className="domain-grid">
        {orderedDomains.map((d, i) => (
          <DomainCard
            key={d.slug}
            domain={d}
            domainData={quotesMap[d.slug]}
            scaleFactor={scaleFactor}
            wide={i === orderedDomains.length - 1}
          />
        ))}
      </div>
    </section>
  )
}
