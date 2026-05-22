import { useEffect, useState } from 'react'
import { supabase } from './lib/supabase'
import Header from './components/Header'
import RampNotice from './components/RampNotice'
import Digest from './components/Digest'
import HeroMetrics from './components/HeroMetrics'
import VolumeChart from './components/VolumeChart'
import SkillsPanel from './components/SkillsPanel'
import CompaniesPanel from './components/CompaniesPanel'
import AICompaniesPanel from './components/AICompaniesPanel'
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

  if (error) {
    return (
      <div className="page">
        <Header />
        <p className="state-msg error">Failed to load data: {error}</p>
      </div>
    )
  }

  if (!snapshots) {
    return (
      <div className="page">
        <Header />
        <p className="state-msg">Loading…</p>
      </div>
    )
  }

  if (!snapshots.length) {
    return (
      <div className="page">
        <Header />
        <p className="state-msg">No snapshots recorded yet.</p>
      </div>
    )
  }

  const today = snapshots.at(-1)
  const latestDigest = snapshots.filter((s) => s.summary_text).at(-1)
  const dayN = Math.floor(
    (new Date(today.snapshot_date) - new Date(snapshots[0].snapshot_date)) / 86_400_000
  ) + 1

  return (
    <div className="page">
      <Header today={today} dayN={dayN} />
      <RampNotice dayN={dayN} />
      <Digest snapshot={latestDigest} />
      <HeroMetrics snapshot={today} />
      <VolumeChart snapshots={snapshots} />
      <CompaniesPanel snapshot={today} />
      <SkillsPanel snapshot={today} />
      <AICompaniesPanel snapshot={today} />
      <Footer snapshot={today} dayN={dayN} />
    </div>
  )
}
