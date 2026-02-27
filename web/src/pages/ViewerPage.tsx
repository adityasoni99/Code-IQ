import { useParams } from 'react-router-dom'
import { useJobPolling } from '../hooks/useJobPolling'
import { TutorialViewer } from '../components/viewer/TutorialViewer'
import { HierarchicalViewer } from '../components/viewer/HierarchicalViewer'
import { Link } from 'react-router-dom'

export function ViewerPage() {
  const { id } = useParams<{ id: string }>()
  const hash = typeof window !== 'undefined' ? window.location.hash.slice(1) : ''
  const { data: job, isLoading, error } = useJobPolling(id, { refetchInterval: 0 })

  if (isLoading && !job) {
    return <div className="text-slate-600">Loading job…</div>
  }
  if (error || !job) {
    return (
      <div>
        <p className="text-red-600">{error instanceof Error ? error.message : 'Job not found'}</p>
        <Link to="/">Back to home</Link>
      </div>
    )
  }
  if (job.status !== 'completed') {
    return (
      <div>
        <p className="text-slate-600">Job not completed yet. Status: {job.status}</p>
        <Link to={`/jobs/${id}`}>View progress</Link>
      </div>
    )
  }

  const result = job.result || {}
  const projectName = result.final_output_dir
    ? result.final_output_dir.split(/[/\\]/).filter(Boolean).pop() || 'tutorial'
    : 'tutorial'
  const isRecursive = job.mode === 'recursive'

  if (isRecursive) {
    return <HierarchicalViewer jobId={id!} initialSlug={hash || undefined} />
  }

  return <TutorialViewer jobId={id!} projectName={projectName} basePath="" />
}
