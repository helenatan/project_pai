export default function Footer({ snapshot }) {
  const lastUpdated = snapshot?.snapshot_date
    ? new Date(snapshot.snapshot_date).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : null

  return (
    <footer style={{
      borderTop: '1px solid #d0dce8',
      marginTop: '3rem',
      paddingTop: '1.5rem',
      fontSize: '0.78rem',
      color: '#6080a0',
      lineHeight: 1.7,
    }}>
      <p>
        <strong>Methodology:</strong> Job volume (total active PM postings, new postings) sourced from
        Adzuna. AI skill rates, top skills, and top companies sourced from full-text job descriptions
        across JSearch and a curated set of AI-native employer boards (Anthropic, OpenAI, DeepMind, xAI,
        Databricks, Scale, and others). AI detection uses keyword matching against a curated list of
        AI-related terms in the job description text, not job titles. Results reflect keyword presence
        in postings, not verified role requirements.
      </p>
      <p>
        <strong>Data sources:</strong> Adzuna &middot; JSearch via RapidAPI &middot; Greenhouse public
        boards &middot; Ashby public boards &middot; Updated daily at 6am PT.
      </p>
      {lastUpdated && (
        <p>Last updated: {lastUpdated}</p>
      )}
      <p>
        PM Adaptation Index &mdash; built to track how AI is reshaping the product management profession.
      </p>
    </footer>
  )
}
