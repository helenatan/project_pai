import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Header from './components/Header'
import Digest from './components/Digest'
import HeroMetrics from './components/HeroMetrics'
import VolumeChart from './components/VolumeChart'
import AIPenetrationChart from './components/AIPenetrationChart'
import SkillsPanel from './components/SkillsPanel'
import CompaniesPanel from './components/CompaniesPanel'
import RampNotice from './components/RampNotice'
import Footer from './components/Footer'

const COLUMNS = [
  'snapshot_date',
  'data_quality_status',
  'total_postings',
  'total_postings_7day_avg',
  'new_postings_today',
  'new_postings_7day_avg',
  'ai_penetration_rate',
  'ai_penetration_7day_avg',
  'top_ai_skills',
  'top_employers_ai_skills',
  'summary_text',
  'digest_generated_at',
].join(',')

export default function App() {
  const [snapshots, setSnapshots] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    supabase
      .from('daily_snapshots')
      .select(COLUMNS)
      .order('snapshot_date', { ascending: true })
      .limit(365)
      .then(({ data, error }) => {
        if (error) setError(error.message)
        else setSnapshots(data)
      })
  }, [])

  const today = snapshots?.at(-1)
  const latestDigest = snapshots?.filter((s) => s.summary_text).at(-1)
  const hasPartialData = today?.data_quality_status === 'partial'

  const containerStyle = {
    maxWidth: 860,
    margin: '0 auto',
    padding: '2rem 1.5rem',
    fontFamily: "'Inter', system-ui, -apple-system, sans-serif",
    color: '#1a2a3a',
  }

  if (error) {
    return (
      <div style={containerStyle}>
        <Header />
        <p style={{ color: '#c0392b' }}>Failed to load data: {error}</p>
      </div>
    )
  }

  if (!snapshots) {
    return (
      <div style={containerStyle}>
        <Header />
        <p style={{ color: '#6080a0' }}>Loading...</p>
      </div>
    )
  }

  return (
    <div style={containerStyle}>
      <Header />
      <RampNotice snapshots={snapshots} />
      {hasPartialData && (
        <div style={{
          background: '#fff3f0',
          border: '1px solid #f0a080',
          borderRadius: 6,
          padding: '0.5rem 0.9rem',
          marginBottom: '1rem',
          fontSize: '0.8rem',
          color: '#7a3010',
        }}>
          Today's data may be incomplete. One or more sources encountered issues.
        </div>
      )}
      <Digest snapshot={latestDigest} />
      <HeroMetrics snapshot={today} />
      <VolumeChart snapshots={snapshots} />
      <AIPenetrationChart snapshots={snapshots} />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2rem' }}>
        <SkillsPanel snapshot={today} />
        <CompaniesPanel snapshot={today} />
      </div>
      <Footer snapshot={today} />
    </div>
  )
}
