const DIRECTION_BADGE = {
  rising:  { label: '↑', color: '#1a7a4a' },
  falling: { label: '↓', color: '#c0392b' },
  flat:    { label: '→', color: '#6080a0' },
  new:     { label: 'new', color: '#7b2fc0' },
}

export default function SkillsPanel({ snapshot }) {
  const data = snapshot?.top_ai_skills
  if (!data?.skills?.length) return null

  const top = data.skills[0].count

  return (
    <section style={{ marginBottom: '2rem' }}>
      <h2 style={{ fontSize: '1rem', fontWeight: 600, color: '#1a2a3a', marginBottom: '0.25rem' }}>
        Top AI Skills in PM Postings
      </h2>
      <div style={{ fontSize: '0.75rem', color: '#6080a0', marginBottom: '0.75rem' }}>
        {data.total_ai_postings_today} AI-mentioning PM postings today
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {data.skills.map((skill) => {
          const badge = DIRECTION_BADGE[skill.direction] || DIRECTION_BADGE.flat
          const barWidth = top > 0 ? (skill.count / top) * 100 : 0
          return (
            <div key={skill.keyword}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.2rem' }}>
                <span style={{ fontSize: '0.85rem', color: '#1a2a3a' }}>
                  {skill.rank}. {skill.keyword}
                  <span style={{ marginLeft: '0.4rem', fontSize: '0.75rem', color: badge.color, fontWeight: 600 }}>
                    {badge.label}
                  </span>
                </span>
                <span style={{ fontSize: '0.8rem', color: '#4a6080' }}>{skill.count}</span>
              </div>
              <div style={{ background: '#e0e8f0', borderRadius: 4, height: 6 }}>
                <div style={{
                  background: '#1a4a7a',
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
