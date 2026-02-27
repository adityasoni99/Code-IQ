import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getTutorialsConfig, listTutorials, type TutorialListItem } from '../api/client'

export function TutorialsPage() {
  const [tutorials, setTutorials] = useState<TutorialListItem[]>([])
  const [outputDir, setOutputDir] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([listTutorials(), getTutorialsConfig()])
      .then(([list, config]) => {
        setTutorials(list)
        setOutputDir(config.output_dir)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-slate-600">Loading tutorials…</div>
  if (error) return <div className="text-red-600">{error}</div>

  return (
    <div className="max-w-4xl mx-auto">
      <h1 className="text-2xl font-semibold text-slate-800 mb-4">Browse tutorials</h1>
      <p className="text-slate-600 mb-2">
        Tutorials are read from the configured output directory (default: <code className="rounded bg-slate-200 px-1">out/</code>).
        {outputDir != null && (
          <span className="block mt-1 font-medium text-slate-700">Tutorials from: <strong>{outputDir}</strong></span>
        )}
      </p>
      <p className="text-slate-500 text-sm mb-6">Click a card to open.</p>
      {tutorials.length === 0 ? (
        <p className="text-slate-500">No tutorials found. Run a job to generate tutorials.</p>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {tutorials.map((t) => (
            <Link
              key={t.slug}
              to={`/tutorials/${encodeURIComponent(t.slug)}/view`}
              className="block p-4 rounded-lg border border-slate-200 bg-white hover:border-slate-300 hover:shadow-sm transition"
            >
              <h2 className="font-medium text-slate-800">{t.name}</h2>
              <p className="text-sm text-slate-500 mt-1">View tutorial</p>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
