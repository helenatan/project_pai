export default function Digest({ snapshot }) {
  if (!snapshot?.summary_text) return null

  const digestDate = snapshot.digest_generated_at
    ? new Date(snapshot.digest_generated_at).toLocaleDateString('en-US', {
        month: 'long', day: 'numeric', year: 'numeric',
      })
    : snapshot.snapshot_date

  return (
    <section className="signal">
      <div className="signal-kicker">
        Weekly Signal<br />{digestDate}
      </div>
      <p className="signal-body">{snapshot.summary_text}</p>
    </section>
  )
}
