// AI Skills by Domain — the 7 tracked categories from the ai_keywords taxonomy.
// Keyword lists mirror pipeline/data/ai_keywords.csv; per-keyword counts come
// live from snapshot.top_ai_skills.skills.
const DOMAINS = [
  {
    slug: 'model_fluency',
    name: 'Model Fluency',
    def: "The ability to reason about what AI models can and can't do — the conceptual foundation every AI PM needs before building anything",
    keywords: ['large language model', 'llm', 'generative ai', 'gen ai', 'foundation model', 'foundation models', 'multimodal', 'machine learning', 'natural language processing', 'nlp', 'computer vision'],
  },
  {
    slug: 'ai_building',
    name: 'AI Building Blocks',
    def: 'The ability to understand and spec the technical components that power AI features — from prompts and RAG to embeddings and fine-tuning',
    keywords: ['prompt engineering', 'context window', 'retrieval augmented generation', 'rag', 'fine-tuning', 'fine tuning', 'embeddings', 'vector database', 'vector search', 'conversational ai'],
  },
  {
    slug: 'agentic_systems',
    name: 'Agentic Systems',
    def: 'The ability to design products where AI takes multi-step actions autonomously — the defining shift from assistive tools to autonomous product experiences',
    keywords: ['agentic', 'agentic ai', 'ai agent', 'ai agents', 'multi-agent', 'agentic workflows', 'agent orchestration', 'tool use'],
  },
  {
    slug: 'evals',
    name: 'Evals & Quality',
    def: 'The ability to define what "good" looks like for an AI feature and build the systems to measure it — increasingly the core PM accountability in AI products',
    keywords: ['ai evaluation', 'ai evals', 'model evaluation', 'evaluation framework', 'hallucination', 'human in the loop', 'human-in-the-loop', 'ai product metrics'],
  },
  {
    slug: 'ai_safety',
    name: 'AI Safety',
    def: 'The ability to identify risks in AI behavior and ship products that are trustworthy, fair, and compliant — a fast-growing PM specialty at AI-first companies',
    keywords: ['responsible ai', 'ai safety', 'ai governance', 'ai ethics', 'trust and safety', 'red teaming', 'ai bias', 'guardrails'],
  },
  {
    slug: 'ai_deployment',
    name: 'AI Deployment',
    def: 'The ability to own AI systems in production — understanding reliability, latency, cost, and what it takes to keep an AI product healthy at scale',
    keywords: ['ai platform', 'ai infrastructure', 'mlops', 'ml ops', 'llmops', 'ai workflows', 'ai automation', 'intelligent automation'],
  },
  {
    slug: 'ai_product_vision',
    name: 'AI Product Vision',
    def: 'The ability to set a long-term AI direction for a product — translating model capabilities into a coherent strategy, roadmap, and competitive positioning',
    keywords: ['ai product strategy', 'ai strategy', 'ai roadmap'],
  },
]

const ACRONYMS = new Set(['ai', 'llm', 'llms', 'nlp', 'rag', 'ml', 'mlops', 'llmops', 'api'])

function formatKeyword(kw) {
  const s = kw
    .split(' ')
    .map((w) => (ACRONYMS.has(w) ? w.toUpperCase() : w))
    .join(' ')
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function DomainCard({ domain, countByKeyword, wide }) {
  const withData = domain.keywords
    .map((kw) => ({ kw, count: countByKeyword[kw] || 0 }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count)

  const topCount = withData.length ? withData[0].count : 0
  const shown = withData.slice(0, 3)
  const shownKws = new Set(shown.map((x) => x.kw))
  const rest = domain.keywords.filter((kw) => !shownKws.has(kw))

  return (
    <div className={`domain-card${wide ? ' domain-card-wide' : ''}`}>
      <h3 className="domain-name">{domain.name}</h3>
      <p className="domain-def">{domain.def}</p>
      <hr className="domain-rule" />
      {withData.length > 0 ? (
        <>
          {shown.map((x, i) => (
            <div className="skill-row" key={x.kw}>
              <span className="skill-rank">{i + 1}</span>
              <div className="skill-bar-area">
                <span className="skill-label">{formatKeyword(x.kw)}</span>
                <div className="bar-track">
                  <div className="bar-fill amber" style={{ width: `${(x.count / topCount) * 100}%` }} />
                </div>
              </div>
              <div className="skill-count-col">
                <div className="count-number" style={{ color: 'var(--signal-amber)' }}>{x.count}</div>
                <div className="count-label">jobs</div>
              </div>
            </div>
          ))}
          {rest.length > 0 && (
            <div className="domain-tracked">
              <span className="tracked-label">Also tracking</span>
              <div className="kw-pills">
                {rest.map((kw) => <span className="kw-pill" key={kw}>{kw}</span>)}
              </div>
            </div>
          )}
        </>
      ) : (
        <div>
          <span className="nodata-label">No signal yet · Tracking</span>
          <div className="kw-pills">
            {domain.keywords.map((kw) => <span className="kw-pill" key={kw}>{kw}</span>)}
          </div>
        </div>
      )}
    </div>
  )
}

export default function SkillsPanel({ snapshot }) {
  const skills = snapshot?.top_ai_skills?.skills || []
  const countByKeyword = {}
  skills.forEach((s) => { countByKeyword[s.keyword] = s.count })

  const withSignal = DOMAINS.filter(
    (d) => d.keywords.some((kw) => (countByKeyword[kw] || 0) > 0)
  ).length
  const totalAi = snapshot?.top_ai_skills?.total_ai_postings_today

  return (
    <section>
      <div className="section-header">
        <span className="section-title">III. AI Skills by Domain</span>
        <span className="section-meta">7 tracked categories</span>
      </div>
      <p className="domain-intro">
        PM job descriptions reveal which AI competencies employers actually require.
        {' '}{withSignal} of 7 categories show signal in the latest snapshot
        {totalAi != null ? ` (${totalAi} AI-mentioning PM postings)` : ''}; the rest are
        tracked and will build signal as more data accumulates.
      </p>
      <div className="domain-grid">
        {DOMAINS.map((d, i) => (
          <DomainCard
            key={d.slug}
            domain={d}
            countByKeyword={countByKeyword}
            wide={i === DOMAINS.length - 1}
          />
        ))}
      </div>
    </section>
  )
}
