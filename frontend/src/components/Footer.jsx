function fmtDate(d) {
  if (!d) return ''
  return new Date(d + 'T00:00:00').toLocaleDateString('en-US', {
    month: 'long', day: 'numeric', year: 'numeric',
  })
}

export default function Footer({ snapshot }) {
  const date = fmtDate(snapshot?.snapshot_date)

  return (
    <>
      <footer className="footer" id="methodology">
        <div className="footer-methodology">
          <span className="footer-mlabel">Methodology &amp; Limitations</span>

          <p className="footer-mblock">
            <strong>Sources.</strong> Postings are pulled daily at 6&nbsp;am PT (14:00 UTC) by a
            scheduled GitHub Actions workflow. We index four sources, all of which return
            <em>&nbsp;complete job descriptions</em>: <em>Greenhouse</em>, <em>Ashby</em>, and
            <em>&nbsp;Lever</em> &mdash; the applicant-tracking systems behind 50 curated employer
            boards we follow directly (Anthropic, OpenAI, xAI, Google DeepMind, Stripe, MongoDB,
            Databricks, Scale&nbsp;AI, Figma, Notion, Cohere, Perplexity, ElevenLabs, and
            similar) &mdash; plus <em>JSearch</em>, a commercial PM job feed we query with
            &ldquo;product manager in united states&rdquo; across the first three result pages.
            Every active opening on this dashboard, and every AI-skill match, is computed
            across all four. The internal split between &ldquo;employer boards&rdquo; and
            &ldquo;feed&rdquo; is only about how we decide a posting is still open: employer
            boards are re-scraped every day, so we track each posting&rsquo;s
            <code>&nbsp;last_seen_date</code>; JSearch is a point-in-time fetch, so we infer
            still-open from a recent <code>posted_date</code>. We previously ingested Adzuna
            but removed it in May&nbsp;2026 because its descriptions are truncated to
            ~500&nbsp;characters, which generated unreliable AI signal.
          </p>

          <p className="footer-mblock">
            <strong>What we don&rsquo;t cover.</strong> Most large enterprises post on their own
            applicant tracking systems (Workday, SuccessFactors, iCIMS, Taleo) or fully
            self-hosted career sites and are not directly indexed here. Well-known examples
            outside our coverage include Apple, Amazon, Meta, Google, Microsoft, Netflix, Tesla,
            Salesforce, Adobe, Oracle, IBM, Walmart, and most Fortune&nbsp;500 employers. Some
            of their postings may still appear via the JSearch feed, but coverage of this group
            is partial and inconsistent. LinkedIn is also excluded &mdash; it offers no public API.
          </p>

          <p className="footer-mblock">
            <strong>Active openings.</strong> An opening is counted as active if either
            (a)&nbsp;an employer-board posting was last re-confirmed within the past 7 days, or
            (b)&nbsp;an employer-board posting was newly scraped within the past 7 days and not
            yet re-confirmed, or (c)&nbsp;a JSearch posting&rsquo;s <code>posted_date</code> falls
            within the past 45 days. We use 45 (rather than the common 30-day rule of thumb)
            because PM postings &mdash; especially senior and AI-leaning roles &mdash; routinely
            stay open longer than the generic average, and our corpus skews toward those.
            JSearch isn&rsquo;t re-verified once ingested, so this window is an assumption
            rather than ground truth. Records are deduplicated by
            the pair (normalized company name, lowercased raw title) so the same role appearing
            on multiple sources is counted once. Only PM-titled roles are included; a role
            qualifies if its raw title matches one of seven PM tiers we track &mdash; CPO, VP,
            Director, Staff&nbsp;PM, Senior&nbsp;PM, PM, or APM &mdash; via substring patterns
            applied to the lowercased title.
          </p>

          <p className="footer-mblock">
            <strong>AI skill detection.</strong> Every active opening in this dashboard comes
            from a source that returns a complete job description, so the &ldquo;% requiring AI
            skills&rdquo; statistic is computed over the same population as the active-openings
            count &mdash; no separate sample. A posting is flagged as &ldquo;requires AI&rdquo;
            if its full description contains at least one of 56 hand-curated keywords across 7
            domains (Model Fluency, AI&nbsp;Building Blocks, Agentic Systems,
            Evals&nbsp;&amp;&nbsp;Quality, AI&nbsp;Safety, AI&nbsp;Deployment,
            AI&nbsp;Product&nbsp;Vision). Matching is case-insensitive on word boundaries against
            the description text, never against the job title.
          </p>

          <p className="footer-mblock">
            <strong>Known limits.</strong> Tracks postings, not hires &mdash; a high opening
            count reflects hiring intent, not confirmed roles filled. Because most of our
            curated employer boards are AI-forward companies, the &ldquo;% requiring AI
            skills&rdquo; rate this dashboard reports is higher than the same rate would be
            across the entire US PM job market. US-only is enforced at the query level for
            JSearch, but employer-board postings rely on a location heuristic and may
            occasionally include international roles. Day-over-day comparisons can be noisy;
            rolling averages and trend deltas are suppressed until at least two weeks of
            history has accumulated.
          </p>
        </div>
        <div className="footer-meta">
          <div className="footer-label">Cite this data</div>
          <div className="footer-cite">
            The PM-AI Hiring Index<br />
            {date || ''}<br /><br />
            <span style={{ color: 'var(--ink-faint)' }}>Built by Helena · Updated daily at 6 am PT</span>
          </div>
        </div>
      </footer>
    </>
  )
}
