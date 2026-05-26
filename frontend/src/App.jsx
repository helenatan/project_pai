import { useEffect, useState, useCallback } from 'react'
import { supabase } from './lib/supabase'
import Header from './components/Header'
import Digest from './components/Digest'
import HeroMetrics from './components/HeroMetrics'
import VolumeChart from './components/VolumeChart'
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

function getInitialTheme() {
  try {
    const saved = localStorage.getItem('pai-theme')
    if (saved) return saved
  } catch {}
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export default function App() {
  const [snapshots, setSnapshots] = useState(null)
  const [error, setError] = useState(null)
  const [theme, setTheme] = useState(getInitialTheme)

  const toggleTheme = useCallback(() => {
    setTheme(t => {
      const next = t === 'dark' ? 'light' : 'dark'
      try { localStorage.setItem('pai-theme', next) } catch {}
      return next
    })
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

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
  const daysOfData = snapshots?.length ?? 0

  const lastUpdated = today?.snapshot_date
    ? new Date(today.snapshot_date + 'T00:00:00').toLocaleDateString('en-US', {
        weekday: 'long', month: 'long', day: 'numeric', year: 'numeric',
      })
    : null

  if (error) {
    return (
      <>
        <Header theme={theme} onToggle={toggleTheme} />
        <div className="page">
          <p className="state-msg error">Failed to load data: {error}</p>
        </div>
      </>
    )
  }

  if (!snapshots) {
    return (
      <>
        <Header theme={theme} onToggle={toggleTheme} />
        <div className="page">
          <p className="state-msg">Loading…</p>
        </div>
      </>
    )
  }

  if (!snapshots.length) {
    return (
      <>
        <Header theme={theme} onToggle={toggleTheme} />
        <div className="page">
          <p className="state-msg">No snapshots recorded yet.</p>
        </div>
      </>
    )
  }

  return (
    <>
      <Header theme={theme} onToggle={toggleTheme} />
      <div className="page">
        <h1 className="hed">How AI Is Reshaping PM Hiring</h1>
        <p className="dek">
          An empirical observatory built on daily job postings — tracking how much of US product
          manager hiring now requires AI skills, updated every morning.
        </p>

        <div className="byline">
          <span><span className="live-dot" />Live data</span>
          {lastUpdated && <span>Data as of {lastUpdated}</span>}
          <span>Sources: Adzuna · JSearch · Greenhouse</span>
        </div>

        {hasPartialData && (
          <div className="data-warning">
            Today's data may be incomplete — one or more sources encountered issues.
          </div>
        )}

        <RampNotice snapshot={today} />
        <Digest snapshot={latestDigest} />
        <HeroMetrics snapshot={today} daysOfData={daysOfData} />
        <VolumeChart snapshots={snapshots} theme={theme} />
        <CompaniesPanel snapshot={today} />
        <SkillsPanel snapshot={today} />
        <Footer snapshot={today} />
      </div>
    </>
  )
}
