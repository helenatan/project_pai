export default function Digest({ snapshot }) {
  if (!snapshot?.summary_text) return null

  const date = snapshot.digest_generated_at
    ? new Date(snapshot.digest_generated_at).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : snapshot.snapshot_date

  return (
    <div className="digest">
      <span className="digest-label">Digest</span>
      <p className="digest-text">
        <span className="digest-date">Weekly digest — {date}</span>
        {snapshot.summary_text}
      </p>
    </div>
  )
}
