export default function RampNotice({ snapshots }) {
  if (!snapshots?.length) return null

  const daysSinceLaunch = Math.floor(
    (Date.now() - new Date(snapshots[0].snapshot_date)) / 86_400_000
  ) + 1

  return (
    <div style={{
      background: '#fffbe6',
      border: '1px solid #e8d870',
      borderRadius: 6,
      padding: '0.75rem 1rem',
      marginBottom: '1.5rem',
      fontSize: '0.82rem',
      color: '#5a4a00',
    }}>
      <strong>Day {daysSinceLaunch} of data collection.</strong> Rolling averages and trend signals
      strengthen over time. Directional signals before Day 14 should be interpreted cautiously.
    </div>
  )
}
