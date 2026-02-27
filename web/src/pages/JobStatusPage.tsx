import { useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useJobPolling } from '../hooks/useJobPolling'

function progressPercent(progress: NonNullable<{
  step?: number
  total_steps?: number
  step_current?: number
  step_total?: number
  completed?: number
  total?: number
}> | null): number | null {
  if (!progress) return null
  if (progress.step != null && progress.total_steps != null && progress.total_steps > 0) {
    const step = progress.step
    const totalSteps = progress.total_steps
    const stepCurrent = progress.step_current
    const stepTotal = progress.step_total
    if (stepTotal != null && stepTotal > 1 && stepCurrent != null && stepCurrent >= 1) {
      const fraction = (step - 1 + stepCurrent / stepTotal) / totalSteps
      return Math.round(fraction * 100)
    }
    return Math.round((step / totalSteps) * 100)
  }
  if (progress.completed != null && progress.total != null && progress.total > 0) {
    return Math.round((progress.completed / progress.total) * 100)
  }
  return null
}

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
        <div className="rounded-xl border border-red-200 bg-red-50/80 p-6">
          <h1 className="text-xl font-semibold text-red-700 mb-2">Job failed</h1>
          <p className="text-slate-700 mb-4 whitespace-pre-wrap">{job.error || 'Unknown error'}</p>
          <Link to="/" className="text-slate-600 hover:underline">Create a new job</Link>
        </div>
      </div>
    )
  }

  const progress = job.progress
  const isRecursive = job.mode === 'recursive'
  const percent = progressPercent(progress ?? null)
  const stepName = progress?.step_name || 'Processing…'
  const stepLabel =
    progress?.step != null && progress?.total_steps != null
      ? `Step ${progress.step} of ${progress.total_steps}`
      : null
  const detail = progress?.detail || null

  return (
    <div className="max-w-xl mx-auto py-8">
      <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-800 mb-6 text-center">
          Job {job.job_id.slice(0, 8)}…
        </h1>

        <div className="flex flex-col items-center gap-6">
          <div className="w-12 h-12 rounded-full border-2 border-slate-200 border-t-slate-600 animate-spin" />

          <div className="w-full">
            <div
              className="h-2 w-full rounded-full bg-slate-100 overflow-hidden transition-all duration-500"
              role="progressbar"
              aria-valuenow={percent ?? 0}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-500 ease-out"
                style={{ width: percent != null ? `${Math.min(100, percent)}%` : '0%' }}
              />
            </div>
          </div>

          <p className="text-slate-700 font-medium text-center">{stepName}</p>

          <div className="flex flex-wrap justify-center gap-4 text-sm text-slate-500">
            {stepLabel != null && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-2 h-2 rounded-full bg-blue-400" aria-hidden />
                {stepLabel}
              </span>
            )}
            {detail != null && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-400" aria-hidden />
                {detail}
              </span>
            )}
          </div>

          {percent != null && (
            <p className="text-2xl font-bold text-slate-800">{percent}%</p>
          )}

          {isRecursive && progress && (progress.total ?? 0) > 0 && (
            <div className="w-full space-y-2 pt-2 border-t border-slate-100">
              <div className="flex justify-between text-sm text-slate-600">
                <span>Folders: {progress.completed ?? 0} / {progress.total ?? 0}</span>
                {progress.current_folder && (
                  <span className="truncate max-w-[12rem]" title={progress.current_folder}>
                    {progress.current_folder}
                  </span>
                )}
              </div>
              <div className="h-1.5 bg-slate-100 rounded overflow-hidden">
                <div
                  className="h-full bg-slate-400 transition-all"
                  style={{
                    width: `${((progress.completed ?? 0) / (progress.total ?? 1)) * 100}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>

        <p className="text-sm text-slate-500 text-center mt-6">
          When complete, you will be redirected to the viewer.
        </p>
      </div>
    </div>
  )
}
