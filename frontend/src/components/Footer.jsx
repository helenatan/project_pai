function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}

export default function Footer({ snapshot, dayN }) {
  const date = fmtDate(snapshot?.snapshot_date)

  return (
    <>
      <hr className="rule-thin" />
      <footer className="footer">
        <div className="footer-methodology">
          <span className="footer-mlabel">Methodology &amp; Limitations</span>
          Job volume (total active PM postings, new postings) sourced from Adzuna. AI skill rates,
          top skills, and top companies sourced from full-text job descriptions across JSearch and a
          curated set of AI-native employer boards (Anthropic, OpenAI, DeepMind, xAI, Databricks,
          Scale, and others). AI detection uses keyword matching against a curated list of AI-related
          terms in the job description text, not job titles. Results reflect keyword presence in
          postings, not verified role requirements. The AI requirement rate reflects the JSearch +
          employer-board corpus, which is intentionally skewed toward AI-first companies; it is not a
          rate across all US PM postings. LinkedIn and internal career pages excluded. Tracks
          postings, not hires.
        </div>
        <div className="footer-meta">
          <div className="footer-label">Cite this data</div>
          <div className="footer-cite">
            The PM Adaptation Index<br />
            {dayN != null ? `Day ${dayN}` : ''}{date ? ` · ${date}` : ''}<br /><br />
            <span style={{ color: 'var(--ink-faint)' }}>Built by Helena · Updated daily at 6 am PT</span>
          </div>
        </div>
      </footer>
    </>
  )
}
