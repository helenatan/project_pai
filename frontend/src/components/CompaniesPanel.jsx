const DIRECTION_BADGE = {
  up:   { label: '↑', color: '#1a7a4a' },
  down: { label: '↓', color: '#c0392b' },
  flat: { label: '→', color: '#6080a0' },
  new:  { label: 'new', color: '#7b2fc0' },
}

export default function CompaniesPanel({ snapshot }) {
  const data = snapshot?.top_employers_ai_skills
  if (!data?.companies?.length) return null

  const top = data.companies[0].count

  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#1a2a3a', marginBottom: '0.25rem' }}>
        Top Companies Hiring PMs with AI Skills
      </h2>
      <div style={{ fontSize: '0.75rem', color: '#6080a0', marginBottom: '0.75rem' }}>
        7-day rolling window ending {data.window_end}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {data.companies.map((co) => {
          const badge = DIRECTION_BADGE[co.direction] || DIRECTION_BADGE.flat
          const barWidth = top > 0 ? (co.count / top) * 100 : 0
          return (
            <div key={co.company}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#1a2a3a', textTransform: 'capitalize' }}>
                  {co.rank}. {co.company}
                  <span style={{ marginLeft: '0.4rem', fontSize: '0.75rem', color: badge.color, fontWeight: 600 }}>
                    {badge.label}
                  </span>
                </span>
                <span style={{ fontSize: '0.8rem', color: '#4a6080' }}>{co.count}</span>
              </div>
              <div style={{ background: '#e0e8f0', borderRadius: 4, height: 6 }}>
                <div style={{
                  background: '#a06010',
                  width: `${barWidth}%`,
                  height: '100%',
                  borderRadius: 4,
                  transition: 'width 0.3s',
                }} />
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
