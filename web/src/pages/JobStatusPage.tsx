import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useJobPolling } from '../hooks/useJobPolling'

export function JobStatusPage() {
  const { id } = useParams<{ id: string }>()
  const { data: job, isLoading, error } = useJobPolling(id)

  useEffect(() => {
    if (job?.status === 'completed') {
      window.location.href = `/jobs/${id}/view`
    }
  }, [job?.status, id])

  if (isLoading && !job) {
    return (
      <div className="max-w-xl mx-auto text-center py-12">
        <div className="animate-spin w-8 h-8 border-2 border-slate-300 border-t-slate-600 rounded-full mx-auto mb-4" />
        <p className="text-slate-600">Loading job…</p>
      </div>
    )
  }

  if (error || !job) {
    return (
      <div className="max-w-xl mx-auto py-8">
        <p className="text-red-600 mb-4">{error instanceof Error ? error.message : 'Job not found'}</p>
        <Link to="/" className="text-slate-600 hover:underline">Back to home</Link>
      </div>
    )
  }

  if (job.status === 'failed') {
    return (
      <div className="max-w-xl mx-auto py-8">
        <h1 className="text-xl font-semibold text-red-700 mb-2">Job failed</h1>
        <p className="text-slate-700 mb-4 whitespace-pre-wrap">{job.error || 'Unknown error'}</p>
        <Link to="/" className="text-slate-600 hover:underline">Create a new job</Link>
      </div>
    )
  }

  const progress = job.progress
  const isRecursive = job.mode === 'recursive'

  return (
    <div className="max-w-xl mx-auto py-8">
      <h1 className="text-xl font-semibold text-slate-800 mb-4">Job {job.job_id.slice(0, 8)}…</h1>
      <div className="flex items-center gap-3 mb-4">
        <div className="animate-spin w-5 h-5 border-2 border-slate-300 border-t-slate-600 rounded-full" />
        <span className="text-slate-600 capitalize">{job.status}</span>
      </div>
      {isRecursive && progress && progress.total > 0 && (
        <div className="space-y-2 mb-4">
          <div className="flex justify-between text-sm text-slate-600">
            <span>Folders: {progress.completed} / {progress.total}</span>
            {progress.current_folder && <span>{progress.current_folder}</span>}
          </div>
          <div className="h-2 bg-slate-200 rounded overflow-hidden">
            <div
              className="h-full bg-slate-600 transition-all"
              style={{ width: `${(progress.completed / progress.total) * 100}%` }}
            />
          </div>
        </div>
      )}
      <p className="text-sm text-slate-500">When complete, you will be redirected to the viewer.</p>
    </div>
  )
}
