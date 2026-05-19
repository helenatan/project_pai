export default function Digest({ snapshot }) {
  if (!snapshot?.summary_text) return null

  const digestDate = snapshot.digest_generated_at
    ? new Date(snapshot.digest_generated_at).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : snapshot.snapshot_date

  return (
    <section style={{
      background: '#f0f4f8',
      borderLeft: '4px solid #1a4a7a',
      borderRadius: '0 8px 8px 0',
      padding: '1.25rem 1.5rem',
      marginBottom: '2rem',
    }}>
      <div style={{ fontSize: '0.75rem', color: '#6080a0', marginBottom: '0.5rem', fontWeight: 600 }}>
        WEEKLY DIGEST &mdash; {digestDate}
      </div>
      <p style={{ margin: 0, color: '#1a2a3a', lineHeight: 1.7, fontSize: '0.975rem' }}>
        {snapshot.summary_text}
      </p>
    </section>
  )
}
